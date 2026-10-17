"""Trusted local provisioning. Passwords are prompted, never command-line arguments."""

import argparse
from datetime import date
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import settings
from app.database import SessionLocal, engine
from app.migrate import require_current_schema
from app.models.enums import UserRole
from app.models.profile import EmployeeProfile
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.auth_service import auth_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=[r.value for r in UserRole], required=True)
    parser.add_argument("--employee-code", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--department", required=True)
    parser.add_argument("--position", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--hire-date", type=date.fromisoformat, required=True)
    parser.add_argument("--leave-balance", type=float, required=True)
    parser.add_argument("--manager-email")
    args = parser.parse_args()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    except ValidationError:
        parser.error("Invalid email format")
    if len(email) > 255:
        parser.error("Email must fit within 255 characters")
    if not 0 <= args.leave_balance <= 10000:
        parser.error("Leave balance must be finite and between 0 and 10000")
    for key in ("name", "employee_code", "company", "department", "position", "location"):
        if not 1 <= len(getattr(args, key).strip()) <= (50 if key == "employee_code" else 255):
            parser.error(f"Invalid {key}")
    password = getpass("New password (12–256 characters): ")
    if not 12 <= len(password) <= 256 or password != getpass("Confirm password: "):
        parser.error("Passwords must match and contain 12–256 characters")
    if settings.ENVIRONMENT == "production" and password == "Password123!":
        parser.error("The published demo password is not allowed in production")
    require_current_schema(engine)
    with SessionLocal() as db:
        if db.query(User).filter(User.email == email).first():
            parser.error("An account with this email already exists")
        if (
            db.query(EmployeeProfile)
            .filter(EmployeeProfile.employee_code == args.employee_code)
            .first()
        ):
            parser.error("An employee code with this value already exists")
        manager = None
        if args.manager_email:
            manager = (
                db.query(User)
                .filter(
                    User.email == args.manager_email.lower(),
                    User.is_active.is_(True),
                    User.role == UserRole.MANAGER,
                )
                .first()
            )
            if not manager:
                parser.error("Manager must be an existing active manager account")
        user = User(
            email=email,
            full_name=args.name.strip(),
            role=UserRole(args.role),
            password_hash=auth_service.hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(
            EmployeeProfile(
                user_id=user.id,
                employee_code=args.employee_code,
                company=args.company,
                department=args.department,
                position=args.position,
                location=args.location,
                hire_date=args.hire_date,
                leave_balance_days=args.leave_balance,
                manager_id=manager.id if manager else None,
            )
        )
        audit_service.log_event(
            db, action="USER_PROVISIONED_LOCALLY", target_type="user", target_id=str(user.id)
        )
        db.commit()
    print("Account and read-only local HR profile created. No external synchronization occurred.")


if __name__ == "__main__":
    main()
