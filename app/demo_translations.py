"""Install reviewed translations for exact, known synthetic fixtures only."""

from datetime import datetime, timezone

from app.localization import CATALOG
from app.models.knowledge import KnowledgeDocument
from app.services.audit_service import audit_service

CANONICAL_CHUNKS = {
    "Vacation Request Workflow": (
        "To request vacation, navigate to 'My requests' -> 'New request' -> select 'Vacation'. "
        "Enter your start and end dates and provide a brief handover note. Your direct manager will review the request. "
        "Once approved, the leave days are deducted from your balance in this local demonstration. "
        "Documentolog is unconnected and no official order is submitted."
    ),
    "Leave Balance & Accrual Rules": (
        "Full-time employees at Jana Post accrue 24 calendar days of paid vacation per completed year of service. "
        "Your available balance is displayed on your Overview and My Profile screens. "
        "These are synthetic sample balances; 1C:ZUP is unconnected."
    ),
}

CANONICAL_TAGS = {
    "Vacation Request Workflow": (
        "vacation, leave, time off, отпуск, демалыс, submission, dates, request, how to request, "
        "оформить отпуск, ежегодный отпуск, еңбек демалысы, өтініш беру, арыз, өтініш"
    ),
    "Leave Balance & Accrual Rules": (
        "balance, days, leave days, сколько дней, баланс, қалдық, vacation balance, 1c, "
        "сколько осталось, положено, қанша күн, демалыс, күн, күндерім, қанша, қалдық қанша"
    ),
    "Advance Payment Policy": (
        "advance, advance payment, salary, аванс, жалақы, төлем, money, payment, "
        "выплата аванса, авансқа өтініш, аванс алу, аламын"
    ),
    "Working Hours & Flexible Schedule": (
        "working hours, schedule, time, график работы, жұмыс кестесі, lunch, flexible, "
        "во сколько, начинается, рабочий день, обед, перерыв, жұмыс уақыты, түскі үзіліс"
    ),
    "HR People Support Contacts": (
        "contact, hr, support, help, email, телефон, байланыс, көмек, emergency, escalations, "
        "отдел кадров, связаться, кадр бөлімі, хабарласу, хабарласамын, қалай хабарласуға болады"
    ),
    "Medical & Sick Leave Documentation": (
        "sick, medical, illness, больничный, ауырып қалу, дәрігер, certificate, "
        "оформить больничный, заболел, заболела, болезнь, ауырып қалсам, ауырсам, еңбекке жарамсыздық, ауырғанда"
    ),
    "Course Enrollment & Learning Progress": (
        "course, courses, learning, academy, lesson, quiz, прогресс, обучение, курс, курсы, урок, уроки, "
        "пройти курс, записаться, сабақ, оқу, өту, қалай өтеді, тіркелу, тест, курстан өту, курстан қалай өтуге болады"
    ),
}


def install_demo_translations(db) -> None:
    # Ensure all demo synthetic documents are marked active and approved
    for doc in db.query(KnowledgeDocument).all():
        if doc.title in CATALOG["messages"]:
            doc.is_synthetic = True
            doc.is_approved = True
            doc.is_active = True

        # Sync legacy chunk content and tags if needed
        for chunk in doc.chunks:
            if (
                chunk.section_title in CANONICAL_CHUNKS
                and chunk.content != CANONICAL_CHUNKS[chunk.section_title]
            ):
                chunk.content = CANONICAL_CHUNKS[chunk.section_title]
            if (
                chunk.section_title in CANONICAL_TAGS
                and chunk.tags != CANONICAL_TAGS[chunk.section_title]
            ):
                chunk.tags = CANONICAL_TAGS[chunk.section_title]

    for doc in db.query(KnowledgeDocument).filter_by(is_approved=True).all():
        if doc.language != "en":
            continue
        fields = {"title": doc.title, "category": doc.category, "description": doc.description}
        if any(value and value not in CATALOG["messages"] for value in fields.values()):
            continue
        if not doc.chunks or any(
            chunk.content not in CATALOG["messages"]
            or chunk.section_title not in CATALOG["messages"]
            for chunk in doc.chunks
        ):
            continue

        doc.translations = {
            language: {
                key: CATALOG["messages"][value][language] if value else value
                for key, value in fields.items()
            }
            for language in ("ru", "kk")
        }
        for chunk in doc.chunks:
            chunk.translations = {
                language: {
                    key: CATALOG["messages"][getattr(chunk, key)][language]
                    for key in ("section_title", "content")
                }
                for language in ("ru", "kk")
            }
        doc.revision += 1
        doc.updated_at = datetime.now(timezone.utc)
        audit_service.log_event(
            db,
            action="KNOWLEDGE_DEMO_LOCALIZED",
            actor_id=doc.approved_by_id,
            target_type="knowledge_document",
            target_id=str(doc.id),
            details={"languages": ["ru", "kk"], "revision": doc.revision, "synthetic": True},
        )
