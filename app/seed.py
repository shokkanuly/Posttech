import json
from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal, engine
from app.demo_translations import install_demo_translations
from app.models import (
    AuditEvent,
    Course,
    EmployeeProfile,
    Enrollment,
    EnrollmentStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    Lesson,
    LessonProgress,
    Notification,
    NotificationType,
    Request,
    RequestEvent,
    RequestEventType,
    RequestStatus,
    RequestType,
    User,
    UserRole,
)
from app.seed_hr_topics import add_hr_topics
from app.services.auth_service import auth_service


def seed_database(session=None):
    from app.config import settings
    from app.migrate import require_current_schema

    if not settings.DEMO_MODE or settings.ENVIRONMENT == "production":
        raise RuntimeError("Seeding is restricted to explicit non-production DEMO_MODE")
    if len(settings.DEMO_PASSWORD) < 12:
        raise RuntimeError("Set a synthetic DEMO_PASSWORD of at least 12 characters")
    if session is None:
        require_current_schema(engine)
    db = session or SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).count() > 0:
            add_hr_topics(db)
            install_demo_translations(db)
            db.commit()
            print("Database already contains data. Skipping re-seed.")
            return

        print("Seeding database with deterministic synthetic data...")

        # ----------------------------------------------------
        # 1. USERS & PROFILES
        # ----------------------------------------------------
        pwd_hash = auth_service.hash_password(settings.DEMO_PASSWORD)

        # Manager: Timur Kasymov
        timur = User(
            email="timur@janapost.kz",
            password_hash=pwd_hash,
            full_name="Timur Kasymov",
            role=UserRole.MANAGER,
            is_active=True,
        )
        db.add(timur)
        db.flush()

        timur_profile = EmployeeProfile(
            user_id=timur.id,
            employee_code="JP-10201",
            company="Jana Post Kazakhstan",
            department="Operations & Logistics",
            position="Operations Team Lead",
            manager_id=None,
            hire_date=date(2021, 6, 1),
            leave_balance_days=24.0,
            location="Almaty, Kazakhstan",
        )
        db.add(timur_profile)

        # HR Admin: Aigerim Nurlanova
        aigerim = User(
            email="aigerim@janapost.kz",
            password_hash=pwd_hash,
            full_name="Aigerim Nurlanova",
            role=UserRole.HR_ADMIN,
            is_active=True,
        )
        db.add(aigerim)
        db.flush()

        aigerim_profile = EmployeeProfile(
            user_id=aigerim.id,
            employee_code="JP-10100",
            company="Jana Post Kazakhstan",
            department="People Operations / HR",
            position="People Operations Director",
            manager_id=None,
            hire_date=date(2020, 3, 15),
            leave_balance_days=28.0,
            location="Almaty, Kazakhstan",
        )
        db.add(aigerim_profile)

        # Employee (Main Demo Persona): Aruzhan Sadykova
        aruzhan = User(
            email="aruzhan@janapost.kz",
            password_hash=pwd_hash,
            full_name="Aruzhan Sadykova",
            role=UserRole.EMPLOYEE,
            is_active=True,
        )
        db.add(aruzhan)
        db.flush()

        aruzhan_profile = EmployeeProfile(
            user_id=aruzhan.id,
            employee_code="JP-10428",
            company="Jana Post Kazakhstan",
            department="Product Operations",
            position="Product Operations Specialist",
            manager_id=timur.id,  # Reports to Timur
            hire_date=date(2023, 3, 12),
            leave_balance_days=18.5,
            location="Almaty, Kazakhstan",
        )
        db.add(aruzhan_profile)

        # Colleague 1: Dana Maratova (also reports to Timur)
        dana = User(
            email="dana@janapost.kz",
            password_hash=pwd_hash,
            full_name="Dana Maratova",
            role=UserRole.EMPLOYEE,
            is_active=True,
        )
        db.add(dana)
        db.flush()

        dana_profile = EmployeeProfile(
            user_id=dana.id,
            employee_code="JP-10332",
            company="Jana Post Kazakhstan",
            department="Product Operations",
            position="Logistics Dispatcher",
            manager_id=timur.id,
            hire_date=date(2022, 9, 1),
            leave_balance_days=21.0,
            location="Almaty, Kazakhstan",
        )
        db.add(dana_profile)

        # Colleague 2: Ruslan Aliyev (also reports to Timur)
        ruslan = User(
            email="ruslan@janapost.kz",
            password_hash=pwd_hash,
            full_name="Ruslan Aliyev",
            role=UserRole.EMPLOYEE,
            is_active=True,
        )
        db.add(ruslan)
        db.flush()

        ruslan_profile = EmployeeProfile(
            user_id=ruslan.id,
            employee_code="JP-10519",
            company="Jana Post Kazakhstan",
            department="Sorting Hub Operations",
            position="Sorting Center Specialist",
            manager_id=timur.id,
            hire_date=date(2024, 1, 15),
            leave_balance_days=15.0,
            location="Almaty, Kazakhstan",
        )
        db.add(ruslan_profile)
        db.flush()

        # ----------------------------------------------------
        # 2. REQUESTS & EVENTS
        # ----------------------------------------------------
        # REQ-1042: Aruzhan Vacation (Pending - for Manager to review)
        req_1042 = Request(
            request_code="REQ-1042",
            user_id=aruzhan.id,
            type=RequestType.VACATION,
            start_date=date(2026, 10, 26),
            end_date=date(2026, 10, 30),
            amount=None,
            reason="Family trip to Shymbulak / personal recharge",
            status=RequestStatus.PENDING,
            reviewer_id=None,
            review_comment=None,
            external_sync_id=None,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=45),
        )
        db.add(req_1042)
        db.flush()

        db.add(
            RequestEvent(
                request_id=req_1042.id,
                actor_id=aruzhan.id,
                event_type=RequestEventType.SUBMITTED,
                comment="Submitted Vacation request for 26-30 Oct 2026 (5 days).",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            )
        )

        # REQ-1036: Aruzhan Advance Payment (Approved)
        req_1036 = Request(
            request_code="REQ-1036",
            user_id=aruzhan.id,
            type=RequestType.ADVANCE_PAYMENT,
            start_date=date(2026, 10, 12),
            end_date=None,
            amount=150000.0,
            reason="Planned medical dental expenses",
            status=RequestStatus.APPROVED,
            reviewer_id=timur.id,
            review_comment="Approved within monthly standard limit.",
            external_sync_id=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=4),
            updated_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add(req_1036)
        db.flush()

        db.add(
            RequestEvent(
                request_id=req_1036.id,
                actor_id=aruzhan.id,
                event_type=RequestEventType.SUBMITTED,
                comment="Submitted Advance payment request for 150,000 ₸.",
                created_at=datetime.now(timezone.utc) - timedelta(days=4),
            )
        )
        db.add(
            RequestEvent(
                request_id=req_1036.id,
                actor_id=timur.id,
                event_type=RequestEventType.APPROVED,
                comment="Approved within monthly standard limit. Registered in Documentolog.",
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )

        # REQ-1024: Aruzhan Vacation (Approved)
        req_1024 = Request(
            request_code="REQ-1024",
            user_id=aruzhan.id,
            type=RequestType.VACATION,
            start_date=date(2026, 10, 12),
            end_date=date(2026, 10, 13),
            amount=None,
            reason="Personal administrative matters",
            status=RequestStatus.APPROVED,
            reviewer_id=timur.id,
            review_comment="Approved. Handover arranged with Dana M.",
            external_sync_id=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
            updated_at=datetime.now(timezone.utc) - timedelta(days=7),
        )
        db.add(req_1024)
        db.flush()

        db.add(
            RequestEvent(
                request_id=req_1024.id,
                actor_id=aruzhan.id,
                event_type=RequestEventType.SUBMITTED,
                comment="Submitted Vacation request for 12-13 Oct 2026 (2 days).",
                created_at=datetime.now(timezone.utc) - timedelta(days=8),
            )
        )
        db.add(
            RequestEvent(
                request_id=req_1024.id,
                actor_id=timur.id,
                event_type=RequestEventType.APPROVED,
                comment="Approved. Handover arranged with Dana M.",
                created_at=datetime.now(timezone.utc) - timedelta(days=7),
            )
        )

        # REQ-1044: Dana Maratova Vacation (Pending in Timur's team)
        req_1044 = Request(
            request_code="REQ-1044",
            user_id=dana.id,
            type=RequestType.VACATION,
            start_date=date(2026, 10, 26),
            end_date=date(2026, 10, 27),
            amount=None,
            reason="Shift adjustment & personal day",
            status=RequestStatus.PENDING,
            reviewer_id=None,
            review_comment=None,
            external_sync_id=None,
            created_at=datetime.now(timezone.utc) - timedelta(hours=3),
            updated_at=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        db.add(req_1044)
        db.flush()

        db.add(
            RequestEvent(
                request_id=req_1044.id,
                actor_id=dana.id,
                event_type=RequestEventType.SUBMITTED,
                comment="Submitted Vacation request for 26-27 Oct 2026.",
                created_at=datetime.now(timezone.utc) - timedelta(hours=3),
            )
        )

        # ----------------------------------------------------
        # 3. JANA ACADEMY (COURSES, LESSONS & PROGRESS)
        # ----------------------------------------------------
        course1 = Course(
            code="CRS-SEC-101",
            title="Data protection essentials",
            category="Compliance & Security",
            description="Learn the everyday principles for keeping customer and company postal data safe across digital and physical touchpoints.",
            duration_minutes=20,
            is_mandatory=True,
            due_date=date(2026, 10, 30),
            total_lessons=4,
            cover_gradient="linear-gradient(145deg, #d9f27a, #84c99a)",
        )
        db.add(course1)
        db.flush()

        l1 = Lesson(
            course_id=course1.id,
            order_index=1,
            title="1. Introduction to Postal Confidentiality",
            content_markdown="Postal communication and client personal data (full name, phone, delivery address, parcel contents) are protected under the Law on Postal Communications and Law on Personal Data in the Republic of Kazakhstan. Never disclose parcel recipient details to third parties.",
            quiz_question="Can you share a customer's delivery phone number with an unauthorized caller who claims to be a relative?",
            quiz_options_json=json.dumps(
                [
                    "Yes, if they state they are an immediate relative",
                    "No, customer contact details must remain strictly confidential unless authorized in official dispatch systems",
                    "Yes, as long as you do not disclose the parcel value",
                ]
            ),
            quiz_correct_answer=1,
        )
        l2 = Lesson(
            course_id=course1.id,
            order_index=2,
            title="2. Secure Handling of Delivery Addresses",
            content_markdown="Physical waybills, barcode stickers, and digital handheld terminals contain sensitive PII. Unused documents must be placed in designated shredding bins, and terminals must be locked when not in direct physical possession.",
            quiz_question="What is the proper procedure for disposing of misprinted address labels?",
            quiz_options_json=json.dumps(
                [
                    "Toss them in the general waste basket beside the counter",
                    "Place them into the secure locked shredder bin for document destruction",
                    "Take them home to recycle",
                ]
            ),
            quiz_correct_answer=1,
        )
        l3 = Lesson(
            course_id=course1.id,
            order_index=3,
            title="3. Recognizing Phishing & Social Engineering",
            content_markdown="Attackers frequently pose as IT support, HR, or postal clients asking for verification codes or credentials. Always verify IT requests through official internal channels and never share your system password or two-factor SMS codes.",
            quiz_question="You receive an email claiming to be from 'Jana Post IT' asking you to reply with your login password. What should you do?",
            quiz_options_json=json.dumps(
                [
                    "Reply promptly with your password so your account isn't locked",
                    "Forward it to your colleagues to see if they got it too",
                    "Report it immediately to cybersecurity support and do not reply or click links",
                ]
            ),
            quiz_correct_answer=2,
        )
        l4 = Lesson(
            course_id=course1.id,
            order_index=4,
            title="4. Incident Reporting & Escalation",
            content_markdown="If you suspect a data breach, lost terminal, or unauthorized access to an employee workstation, you must report it within 30 minutes to the Security Operations Center (SOC) and your direct manager.",
            quiz_question="Within what timeframe should a suspected data security incident be escalated to the SOC?",
            quiz_options_json=json.dumps(
                [
                    "Within 30 minutes",
                    "Within 7 business days",
                    "Only if customer complaints are received",
                ]
            ),
            quiz_correct_answer=0,
        )
        db.add_all([l1, l2, l3, l4])
        db.flush()

        # Enroll Aruzhan in Course 1 with 3 lessons completed (75% progress!)
        enrollment1 = Enrollment(
            user_id=aruzhan.id,
            course_id=course1.id,
            status=EnrollmentStatus.IN_PROGRESS,
            progress_percent=75.0,
            score=75.0,
        )
        db.add(enrollment1)
        db.flush()

        db.add_all(
            [
                LessonProgress(
                    enrollment_id=enrollment1.id,
                    lesson_id=l1.id,
                    is_completed=True,
                    quiz_passed=True,
                    completed_at=datetime.now(timezone.utc) - timedelta(days=2),
                ),
                LessonProgress(
                    enrollment_id=enrollment1.id,
                    lesson_id=l2.id,
                    is_completed=True,
                    quiz_passed=True,
                    completed_at=datetime.now(timezone.utc) - timedelta(days=1),
                ),
                LessonProgress(
                    enrollment_id=enrollment1.id,
                    lesson_id=l3.id,
                    is_completed=True,
                    quiz_passed=True,
                    completed_at=datetime.now(timezone.utc) - timedelta(hours=4),
                ),
                LessonProgress(
                    enrollment_id=enrollment1.id,
                    lesson_id=l4.id,
                    is_completed=False,
                    quiz_passed=False,
                    completed_at=None,
                ),
            ]
        )

        # Course 2: Working safely with customer data in postal logistics
        course2 = Course(
            code="CRS-OPS-202",
            title="Working safely with customer data",
            category="Customer Experience & Operations",
            description="Practical habits for handling customer information across everyday sorting, transport, and parcel lockers.",
            duration_minutes=25,
            is_mandatory=False,
            due_date=date(2026, 11, 15),
            total_lessons=1,
            cover_gradient="linear-gradient(145deg, #d8e5ff, #9baeea)",
        )
        db.add(course2)
        db.flush()

        cl1 = Lesson(
            course_id=course2.id,
            order_index=1,
            title="1. Parcel Locker Operations & Data Privacy",
            content_markdown="Postamat lockers generate single-use SMS pickup codes. Never disclose pickup PINs over the phone without customer identity verification.",
            quiz_question="Can staff manually trigger parcel locker door releases without verification?",
            quiz_options_json=json.dumps(["No, verification is mandatory", "Yes, anytime"]),
            quiz_correct_answer=0,
        )
        db.add(cl1)
        db.flush()

        enrollment2 = Enrollment(
            user_id=aruzhan.id,
            course_id=course2.id,
            status=EnrollmentStatus.NOT_STARTED,
            progress_percent=0.0,
        )
        db.add(enrollment2)

        # ----------------------------------------------------
        # 4. KNOWLEDGE BASE (APPROVED HR POLICIES & CHUNKS)
        # ----------------------------------------------------
        doc1 = KnowledgeDocument(
            title="Employee Request Guide (Sample Policy)",
            category="HR Operations",
            description="Standard operating procedures for leave requests, advance payments, and time off workflows.",
            version="1.4",
            is_active=True,
            is_approved=True,
            is_synthetic=True,
            approved_by_id=aigerim.id,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(doc1)
        db.flush()

        chunk1 = KnowledgeChunk(
            document_id=doc1.id,
            section_title="Vacation Request Workflow",
            content="To request vacation, navigate to 'My requests' -> 'New request' -> select 'Vacation'. Enter your start and end dates and provide a brief handover note. Your direct manager will review the request. Once approved, the leave days are deducted from your balance in this local demonstration. Documentolog is unconnected and no official order is submitted.",
            tags="vacation, leave, time off, отпуск, демалыс, submission, dates, request, how to request, "
            "оформить отпуск, ежегодный отпуск, еңбек демалысы, өтініш беру, арыз, өтініш",
            access_level="all",
        )
        chunk2 = KnowledgeChunk(
            document_id=doc1.id,
            section_title="Leave Balance & Accrual Rules",
            content="Full-time employees at Jana Post accrue 24 calendar days of paid vacation per completed year of service. Your available balance is displayed on your Overview and My Profile screens. These are synthetic sample balances; 1C:ZUP is unconnected.",
            tags="balance, days, leave days, сколько дней, баланс, қалдық, vacation balance, 1c, "
            "сколько осталось, положено, қанша күн, демалыс, күн, күндерім, қанша, қалдық қанша",
            access_level="all",
        )
        chunk3 = KnowledgeChunk(
            document_id=doc1.id,
            section_title="Advance Payment Policy",
            content="Employees may request an advance payment of up to 50% of their monthly base salary for urgent personal expenses. Requests are submitted through JanaMen under 'Advance payment' and require direct manager approval. Approved amounts are disbursed on the 20th of the month and deducted from the subsequent payroll.",
            tags="advance, advance payment, salary, аванс, жалақы, төлем, money, payment, "
            "выплата аванса, авансқа өтініш, аванс алу, аламын",
            access_level="all",
        )
        chunk4 = KnowledgeChunk(
            document_id=doc1.id,
            section_title="Working Hours & Flexible Schedule",
            content="Official core working hours at Jana Post offices and administrative branches are 09:00 to 18:00 (Almaty time, GMT+5), Monday through Friday, with a lunch break from 13:00 to 14:00. Flexible start times (08:00 - 10:00) require written approval from your department lead.",
            tags="working hours, schedule, time, график работы, жұмыс кестесі, lunch, flexible, "
            "во сколько, начинается, рабочий день, обед, перерыв, жұмыс уақыты, түскі үзіліс",
            access_level="all",
        )
        db.add_all([chunk1, chunk2, chunk3, chunk4])

        doc2 = KnowledgeDocument(
            title="HR Support Directory & Escalation Guide (Sample)",
            category="Employee Support",
            description="Contacts and escalation paths for specialized HR assistance.",
            version="1.1",
            is_active=True,
            is_approved=True,
            is_synthetic=True,
            approved_by_id=aigerim.id,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(doc2)
        db.flush()

        chunk5 = KnowledgeChunk(
            document_id=doc2.id,
            section_title="HR People Support Contacts",
            content="For medical leave certificates, maternity/paternity leave, or confidential employment inquiries not answered in the knowledge base, contact the People Operations Helpdesk at hr-support@janapost.kz or call extension 1040 (internal) / +7 (727) 344-9000. The HR office is located on the 3rd floor (Room 304), Almaty Central Hub.",
            tags="contact, hr, support, help, email, телефон, байланыс, көмек, emergency, escalations, "
            "отдел кадров, связаться, кадр бөлімі, хабарласу, хабарласамын, қалай хабарласуға болады",
            access_level="all",
        )
        chunk6 = KnowledgeChunk(
            document_id=doc2.id,
            section_title="Medical & Sick Leave Documentation",
            content="Sick leave requires an official digital or paper medical certificate (лист о временной нетрудоспособности / еңбекке жарамсыздық парағы) from an accredited clinic. You must notify your manager within 24 hours of falling ill and upload or deliver the certificate upon return.",
            tags="sick, medical, illness, больничный, ауырып қалу, дәрігер, certificate, "
            "оформить больничный, заболел, заболела, болезнь, ауырып қалсам, ауырсам, еңбекке жарамсыздық, ауырғанда",
            access_level="all",
        )
        db.add_all([chunk5, chunk6])

        doc3 = KnowledgeDocument(
            title="Jana Academy & Course Guide (Sample Policy)",
            category="Learning & Development",
            description="Guidelines for enrolling in courses, completing lessons, and tracking learning progress.",
            version="1.0",
            is_active=True,
            is_approved=True,
            is_synthetic=True,
            approved_by_id=aigerim.id,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(doc3)
        db.flush()

        chunk7 = KnowledgeChunk(
            document_id=doc3.id,
            section_title="Course Enrollment & Learning Progress",
            content="All employees have access to courses in Jana Academy. Navigate to 'Jana Academy', select an assigned or available course, and click enroll. Complete each lesson and answer the knowledge check quiz at the end. Your learning progress is automatically saved to your profile upon passing the quiz.",
            tags="course, courses, learning, academy, lesson, quiz, прогресс, обучение, курс, курсы, урок, уроки, "
            "пройти курс, записаться, сабақ, оқу, өту, қалай өтеді, тіркелу, тест, курстан өту, курстан қалай өтуге болады",
            access_level="all",
        )
        db.add(chunk7)

        # ----------------------------------------------------
        # 5. INITIAL NOTIFICATIONS
        # ----------------------------------------------------
        notif1 = Notification(
            user_id=aruzhan.id,
            title="Vacation request is under review",
            message="Your vacation request for 26–30 October (REQ-1042) was sent to your manager Timur Kasymov.",
            type=NotificationType.REQUEST,
            reference_type="request",
            reference_id="REQ-1042",
            is_read=False,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=45),
        )
        notif2 = Notification(
            user_id=aruzhan.id,
            title="Mandatory course assigned",
            message="Data protection essentials (CRS-SEC-101) is due on 30 October 2026.",
            type=NotificationType.ACADEMY,
            reference_type="course",
            reference_id="CRS-SEC-101",
            is_read=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        notif3 = Notification(
            user_id=aruzhan.id,
            title="Previous request approved",
            message="Your advance payment request for 150,000 ₸ (REQ-1036) was approved.",
            type=NotificationType.REQUEST,
            reference_type="request",
            reference_id="REQ-1036",
            is_read=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.add_all([notif1, notif2, notif3])

        # ----------------------------------------------------
        # 6. INITIAL AUDIT LOGS
        # ----------------------------------------------------
        db.add(
            AuditEvent(
                actor_id=aruzhan.id,
                action="REQUEST_SUBMITTED",
                target_type="request",
                target_id="REQ-1042",
                details_json=json.dumps({"type": "Vacation", "days": 5, "start": "2026-10-26"}),
                created_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            )
        )
        db.add(
            AuditEvent(
                actor_id=timur.id,
                action="REQUEST_APPROVED",
                target_type="request",
                target_id="REQ-1036",
                details_json=json.dumps({"type": "Advance payment", "amount": 150000}),
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )

        db.flush()
        add_hr_topics(db)
        install_demo_translations(db)
        db.commit()
        print("Database seeded successfully with deterministic accounts and scenario data!")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {type(e).__name__}")
        raise
    finally:
        if session is None:
            db.close()


if __name__ == "__main__":
    seed_database()
