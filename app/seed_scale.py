"""Company-scale synthetic demo data on top of the base seed (DEMO_MODE only).

    python -m app.seed_scale --employees 150

Deterministic (fixed random seed) and idempotent: a second run changes nothing. Every
record is synthetic. Requests respect the same rules as the API: no overlapping
vacations, chargeable days from the 1C:ZUP calendar, pending days within the balance.
"""

import argparse
import json
import random
import time
from datetime import date, datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.integrations.one_c_zup import one_c_adapter
from app.models.academy import Course, Enrollment, LessonProgress
from app.models.audit import AuditEvent
from app.models.enums import (
    EnrollmentStatus,
    NotificationType,
    RequestEventType,
    RequestStatus,
    RequestType,
    UserRole,
)
from app.models.notification import Notification
from app.models.profile import EmployeeProfile
from app.models.request import Request, RequestEvent
from app.models.user import User
from app.seed import seed_database
from app.services.auth_service import auth_service

TODAY = date(2026, 10, 17)
MARKER = "REQ-S"  # request-code prefix of generated data; its presence means "already seeded"

DEPARTMENTS = [  # (department, location, positions)
    ("Sorting Hub Almaty", "Almaty, Kazakhstan", ["Sorting Operator", "Shift Supervisor"]),
    ("Last-mile Delivery Astana", "Astana, Kazakhstan", ["Courier", "Route Planner"]),
    ("Customer Support", "Almaty, Kazakhstan", ["Support Specialist", "Shift Supervisor"]),
    ("IT Platform", "Almaty, Kazakhstan", ["Backend Developer", "QA Engineer"]),
    ("Finance & Accounting", "Astana, Kazakhstan", ["Accountant", "Financial Analyst"]),
    ("Logistics Shymkent", "Shymkent, Kazakhstan", ["Route Planner", "Courier"]),
    ("Warehouse Karaganda", "Karaganda, Kazakhstan", ["Warehouse Keeper", "Forklift Operator"]),
]
TIMUR_TEAM = [  # extra direct reports for the demo manager, in his existing departments
    ("Product Operations", "Almaty, Kazakhstan", ["Product Operations Specialist"]),
    ("Sorting Hub Operations", "Almaty, Kazakhstan", ["Sorting Center Specialist"]),
    ("Operations & Logistics", "Almaty, Kazakhstan", ["Logistics Dispatcher"]),
]
MALE = "Айбек Нурлан Ерлан Данияр Арман Бауыржан Ержан Асхат Дамир Санжар Алихан Максим Олжас Ильяс".split()
FEMALE = "Айгерим Асель Мадина Жанар Гульнара Алия Сабина Камила Анна Мария Динара Томирис Алтынай Жансая".split()
SURNAMES = "Нурлан Ахмет Серик Жумабай Омар Абдрахман Бекмухамед Ибра Тулеген Исмаил Иван Сагинтай Жаксыбек Кенжебек".split()
VACATION_REASONS = [
    "Family vacation",
    "Trip to see relatives",
    "Rest after peak season",
    "Wedding of a relative",
]
ADVANCE_REASONS = ["Medical treatment expenses", "Tuition payment", "Home repair"]
APPROVE_COMMENTS = {
    RequestType.VACATION: "Approved, coverage arranged",
    RequestType.ADVANCE_PAYMENT: "Approved within the monthly limit",
}
REJECT_COMMENTS = {
    RequestType.VACATION: "Declined: peak season, please choose other dates",
    RequestType.ADVANCE_PAYMENT: "Declined: exceeds the monthly limit",
}


def at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc)


def person(rng: random.Random) -> str:
    female = rng.random() < 0.5
    base = rng.choice(SURNAMES)
    surname = (
        base + ("ова" if female else "ов")
        if not base.endswith("ай")
        else base + ("ева" if female else "ев")
    )
    return f"{rng.choice(FEMALE if female else MALE)} {surname}"


def plan_requests(rng: random.Random, balance: float):
    """1–3 decided past requests and 0–2 upcoming ones (mostly awaiting review), no overlaps."""
    plans: list[tuple[RequestType, date, date | None, int | None, str]] = []
    available = balance
    past = [(date(2025, 11, 3), TODAY - timedelta(days=20), rng.randint(1, 3))]
    upcoming = [(TODAY + timedelta(days=3), date(2027, 3, 31), rng.choice([0, 1, 1, 2]))]
    for window_start, window_end, count in past + upcoming:
        future = window_start >= TODAY
        cursor = window_start
        for _ in range(count):
            span = (window_end - cursor).days
            if span < 20:
                break
            cursor += timedelta(days=rng.randint(3, max(4, span // (count + 1))))
            if rng.random() < 0.7:
                end = cursor + timedelta(days=rng.randint(2, 13))
                days = one_c_adapter.vacation_days(cursor, end)
                status = rng.choices(
                    ["Pending", "Approved", "Rejected"], [6, 3, 1] if future else [0, 9, 1]
                )[0]
                if status != "Rejected":
                    if days == 0 or days > available:
                        continue
                    available -= days
                plans.append((RequestType.VACATION, cursor, end, None, status))
                cursor = end + timedelta(days=1)
            else:
                status = rng.choices(
                    ["Pending", "Approved", "Rejected"], [6, 3, 1] if future else [0, 4, 1]
                )[0]
                amount = rng.randrange(30000, 400001, 5000)
                plans.append((RequestType.ADVANCE_PAYMENT, cursor, None, amount, status))
                cursor += timedelta(days=1)
    return plans


def seed_scale(db, employees: int, seed: int = 2026) -> dict:
    if db.query(Request).filter(Request.request_code.like(f"{MARKER}%")).first():
        return {"skipped": True}
    rng = random.Random(seed)
    password_hash = auth_service.hash_password(settings.DEMO_PASSWORD)  # hashed once, reused
    timur = db.query(User).filter_by(email="timur@janapost.kz").one()
    courses = db.query(Course).order_by(Course.id).all()
    counters = {"users": 0, "requests": 0, "events": 0, "lessons": 0}
    serial = iter(range(1, 1_000_000))

    def new_user(name, role, department, location, position, manager_id, index):
        user = User(
            email=f"{'mgr' if role == UserRole.MANAGER else 'emp'}{index:04d}@example.com",
            password_hash=password_hash,
            full_name=name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        hire = date(rng.randint(2016, 2026), rng.randint(1, 12), rng.randint(1, 28))
        hire = min(hire, TODAY - timedelta(days=30))
        db.add(
            EmployeeProfile(
                user_id=user.id,
                employee_code=f"JP-{20000 + index}",
                company="Jana Post Kazakhstan",
                department=department,
                position=position,
                manager_id=manager_id,
                hire_date=hire,
                leave_balance_days=0.0,
                location=location,
            )
        )
        counters["users"] += 1
        return user

    teams = []
    for d_index, (department, location, positions) in enumerate(DEPARTMENTS, start=1):
        manager = new_user(
            person(rng), UserRole.MANAGER, department, location, "Department Manager", None, d_index
        )
        teams.append((manager, department, location, positions))

    for index in range(employees):
        if index < 9:  # the demo manager gets a realistic team of twelve
            manager, (department, location, positions) = timur, TIMUR_TEAM[index % 3]
        else:
            manager, department, location, positions = rng.choice(teams)
        user = new_user(
            person(rng),
            UserRole.EMPLOYEE,
            department,
            location,
            rng.choice(positions),
            manager.id,
            100 + index,
        )
        entitlement = 24.0 + rng.randint(0, 6)
        used = 0.0
        for kind, start, end, amount, status_name in plan_requests(rng, entitlement):
            status = RequestStatus(status_name)
            code = f"{MARKER}{next(serial):06d}"
            created = at(min(start - timedelta(days=rng.randint(7, 30)), TODAY), rng.randint(4, 12))
            # Decisions never land in the future relative to the demo date.
            decided = min(
                created + timedelta(hours=rng.randint(2, 72)), max(created, at(TODAY, 18))
            )
            reason = rng.choice(
                VACATION_REASONS if kind == RequestType.VACATION else ADVANCE_REASONS
            )
            comment = None
            if status != RequestStatus.PENDING:
                comment = (
                    APPROVE_COMMENTS if status == RequestStatus.APPROVED else REJECT_COMMENTS
                )[kind]
            request = Request(
                request_code=code,
                user_id=user.id,
                type=kind,
                start_date=start,
                end_date=end,
                amount=amount,
                reason=reason,
                status=status,
                reviewer_id=manager.id if status != RequestStatus.PENDING else None,
                review_comment=comment,
                external_sync_id=None,
                created_at=created,
                updated_at=decided if status != RequestStatus.PENDING else created,
            )
            db.add(request)
            db.flush()
            db.add(
                RequestEvent(
                    request_id=request.id,
                    actor_id=user.id,
                    event_type=RequestEventType.SUBMITTED,
                    comment=f"Submitted {kind.value} request. {reason}",
                    created_at=created,
                )
            )
            db.add(
                AuditEvent(
                    actor_id=user.id,
                    action="REQUEST_SUBMITTED",
                    target_type="request",
                    target_id=code,
                    details_json=json.dumps({"type": kind.value}),
                    created_at=created,
                )
            )
            counters["requests"] += 1
            counters["events"] += 1
            if status == RequestStatus.PENDING:
                continue
            event = (
                RequestEventType.APPROVED
                if status == RequestStatus.APPROVED
                else RequestEventType.REJECTED
            )
            db.add(
                RequestEvent(
                    request_id=request.id,
                    actor_id=manager.id,
                    event_type=event,
                    comment=comment,
                    created_at=decided,
                )
            )
            db.add(
                AuditEvent(
                    actor_id=manager.id,
                    action=f"REQUEST_{status.value.upper()}",
                    target_type="request",
                    target_id=code,
                    details_json=json.dumps({"new_status": status.value}),
                    created_at=decided,
                )
            )
            db.add(
                Notification(
                    user_id=user.id,
                    title=f"Request {status.value}",
                    message=f"Your {kind.value} request ({code}) was {status.value.lower()} by {manager.full_name}. {comment}",
                    type=NotificationType.REQUEST,
                    is_read=decided.date() < TODAY - timedelta(days=3),
                    reference_type="request",
                    reference_id=code,
                    created_at=decided,
                )
            )
            counters["events"] += 1
            if status == RequestStatus.APPROVED and kind == RequestType.VACATION:
                used += one_c_adapter.vacation_days(start, end)
        db.query(EmployeeProfile).filter_by(user_id=user.id).update(
            {"leave_balance_days": entitlement - used}
        )

        for course in courses:
            if not course.is_mandatory and rng.random() < 0.6:
                continue
            lessons = sorted(course.lessons, key=lambda lesson: lesson.order_index)
            passed = rng.choice([0, 1, 2, 3, len(lessons), len(lessons)])
            passed = min(passed, len(lessons))
            done = passed == len(lessons) and lessons
            assigned = at(TODAY - timedelta(days=rng.randint(10, 120)), 9)
            enrollment = Enrollment(
                user_id=user.id,
                course_id=course.id,
                status=EnrollmentStatus.COMPLETED
                if done
                else EnrollmentStatus.IN_PROGRESS
                if passed
                else EnrollmentStatus.NOT_STARTED,
                progress_percent=round(100 * passed / len(lessons), 1) if lessons else 0.0,
                score=100.0 if done else None,
                completed_at=assigned + timedelta(days=passed + 1) if done else None,
                updated_at=assigned + timedelta(days=passed),
            )
            db.add(enrollment)
            db.flush()
            for step, lesson in enumerate(lessons[:passed], start=1):
                db.add(
                    LessonProgress(
                        enrollment_id=enrollment.id,
                        lesson_id=lesson.id,
                        is_completed=True,
                        quiz_passed=True,
                        completed_at=assigned + timedelta(days=step),
                    )
                )
                counters["lessons"] += 1
            db.add(
                Notification(
                    user_id=user.id,
                    title="Course assigned",
                    message=f"{course.title} ({course.code}) was assigned to you.",
                    type=NotificationType.ACADEMY,
                    is_read=True,
                    reference_type="course",
                    reference_id=course.code,
                    created_at=assigned,
                )
            )
    db.commit()
    return counters


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--employees", type=int, default=150)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if not settings.DEMO_MODE or settings.ENVIRONMENT == "production":
        raise SystemExit("Scale seeding is restricted to non-production DEMO_MODE")
    seed_database()
    started = time.perf_counter()
    with SessionLocal() as db:
        result = seed_scale(db, args.employees, args.seed)
    print(
        json.dumps(
            {**result, "seconds": round(time.perf_counter() - started, 2)}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
