"""Explicit, repeatable creation of three linked synthetic demo accounts."""

from datetime import date

from app.config import settings
from app.database import SessionLocal, engine
from app.migrate import require_current_schema
from app.models.academy import Course
from app.models.enums import UserRole
from app.models.profile import EmployeeProfile
from app.models.user import User
from app.services.academy_service import academy_service
from app.services.audit_service import audit_service
from app.services.auth_service import auth_service

DEMO_ACCOUNTS = {
    "employee": "employee.demo@example.com",
    "manager": "manager.demo@example.com",
    "hr_admin": "hr.demo@example.com",
}


def provision_accounts(db) -> dict[str, int]:
    if settings.ENVIRONMENT == "production" or not settings.DEMO_MODE:
        raise RuntimeError("Demo provisioning requires non-production DEMO_MODE")
    if not 12 <= len(settings.DEMO_PASSWORD) <= 256:
        raise RuntimeError("Set a synthetic DEMO_PASSWORD with 12–256 characters")
    result: dict[str, int] = {}
    roles = [
        (UserRole.HR_ADMIN, "Демо Администратор", "DEMO-HR-001", "Кадровый администратор"),
        (UserRole.MANAGER, "Демо Руководитель", "DEMO-MGR-001", "Руководитель команды"),
        (UserRole.EMPLOYEE, "Демо Сотрудник", "DEMO-EMP-001", "Специалист"),
    ]
    for role, name, code, position in roles:
        email = DEMO_ACCOUNTS[role.value]
        user = db.query(User).filter_by(email=email).first()
        if user:
            if (
                user.role != role
                or not user.is_active
                or not user.profile
                or user.profile.employee_code != code
            ):
                raise RuntimeError(
                    "An existing account conflicts with the demo identity; refusing to overwrite it"
                )
            if role == UserRole.EMPLOYEE and user.profile.manager_id != result["manager"]:
                raise RuntimeError(
                    "The existing demo reporting line changed; refusing to overwrite it"
                )
            result[role.value] = user.id
            print(f"Учётная запись уже существует: {email}")
            continue
        if db.query(EmployeeProfile).filter_by(employee_code=code).first():
            raise RuntimeError("Demo employee code is already in use; no records overwritten")
        user = User(
            email=email,
            full_name=name,
            role=role,
            is_active=True,
            password_hash=auth_service.hash_password(settings.DEMO_PASSWORD),
        )
        db.add(user)
        db.flush()
        db.add(
            EmployeeProfile(
                user_id=user.id,
                employee_code=code,
                company="Jana Post Казахстан",
                department="Демонстрационная команда",
                position=position,
                location="Алматы, Казахстан",
                hire_date=date(2026, 10, 1),
                leave_balance_days=24,
                manager_id=result.get("manager") if role == UserRole.EMPLOYEE else None,
            )
        )
        audit_service.log_event(
            db,
            action="USER_PROVISIONED_LOCALLY",
            target_type="user",
            target_id=str(user.id),
            details={"synthetic": True, "role": role.value},
        )
        db.commit()
        result[role.value] = user.id
        print(f"Создана демо-учётная запись: {email} ({role.value})")
    for course in db.query(Course).filter(Course.code.in_(["CRS-SEC-101", "CRS-OPS-202"])).all():
        academy_service.enroll(db, result["employee"], course.id, result["hr_admin"])
    return result


if __name__ == "__main__":
    require_current_schema(engine)
    with SessionLocal() as db:
        provision_accounts(db)
