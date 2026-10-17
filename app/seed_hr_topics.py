"""Extra synthetic HR knowledge for AI Jana: leave calendar, life events and procedures.

Facts quoted from the Labour Code of Kazakhstan are marked as such; everything else is a
synthetic company procedure. Idempotent, so an existing demo database gets it on the next
seed run. RU/KK translations live in static/locales/catalog.json (install_demo_translations).
"""

from datetime import datetime, timezone

from app.models.enums import UserRole
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User

TITLE = "Employee Life Events & Procedures Guide (Sample Policy)"

SECTIONS = [
    (
        "Public Holidays & Leave Day Counting",
        "Annual leave is counted in calendar days: weekends inside a vacation are counted, public holidays of Kazakhstan are not. "
        "The public holidays are 1–2 January, 8 March, 21–23 March, 1 May, 7 May, 9 May, 6 July, 30 August, 25 October and 16 December. "
        "When you choose dates in the request form, JanaMen shows a calendar with weekends, holidays, your planned vacations and the days that will be charged.",
        "holiday, holidays, public holiday, weekend, weekends, calendar, праздник, праздники, выходные, выходной, "
        "входят ли, календарь, считаются, мереке, мерекелер, демалыс күндері, күнтізбе, кіре ме, есептеле ме",
    ),
    (
        "Maternity & Childcare Leave",
        "Under the Labour Code of Kazakhstan, maternity leave lasts 126 calendar days (70 before and 56 after birth), "
        "or 140 calendar days after a complicated birth or the birth of two or more children. "
        "Unpaid childcare leave can be granted until the child turns three. "
        "Send the medical certificate to hr-support@janapost.kz: HR registers this leave, it is not requested in JanaMen.",
        "maternity, childcare, pregnancy, decree, декрет, декретный, беременность, роды, уход за ребенком, ребенок, "
        "декреттік, жүктілік, босану, бала күтімі, бала",
    ),
    (
        "Business Trips",
        "A business trip is approved by your direct manager and issued by HR as an order before departure. "
        "Travel, accommodation and daily allowance are covered under the company travel policy. "
        "After returning, submit the expense report with all receipts to accounting.",
        "business trip, travel, trip, командировка, командировки, поездка, суточные, отчёт, авансовый отчёт, "
        "поехать, ехать, іссапар, іссапарға, сапар, барамын, бару, тәуліктік, есеп",
    ),
    (
        "Employment Certificates",
        "To get a certificate of employment or income, email hr-support@janapost.kz with the purpose and the number of copies. "
        "HR prepares the document and notifies you when it is ready to collect.",
        "certificate, employment certificate, income, справка, справку, с места работы, о доходах, получить справку, "
        "анықтама, жұмыс орнынан, табыс туралы, анықтама алу",
    ),
    (
        "Overtime Rules",
        "Overtime is allowed only with your consent and your manager's approval. "
        "Under the Labour Code of Kazakhstan it may not exceed 2 hours a day, 12 hours a month and 120 hours a year, "
        "and it is paid at least one and a half times the regular rate.",
        "overtime, extra hours, сверхурочные, сверхурочная, переработка, сверхурочно, сколько часов, "
        "үстеме, үстеме жұмыс, артық сағат, қосымша сағат",
    ),
    (
        "Resignation Procedure",
        "To resign at your own initiative, notify the employer in writing at least one month in advance, as the Labour Code of Kazakhstan requires. "
        "Submit the written notice to HR; HR arranges your last working day, final settlement and documents.",
        "resign, resignation, quit, увольнение, уволиться, по собственному желанию, заявление на увольнение, "
        "жұмыстан шығу, өз еркімен, өтініш",
    ),
    (
        "Updating Your Contact Details",
        "To change your phone, city or emergency contact, open 'My profile' and click 'Edit contact details'. "
        "The change is sent to your direct manager or HR as a 'Profile update' request and applies only after approval. "
        "Position, department and manager are changed by HR only.",
        "profile, contact, phone, update, change, профиль, изменить, телефон, контакты, экстренный, город, данные, "
        "профильді, өзгерту, телефон, байланыс, деректер",
    ),
]


def add_hr_topics(db) -> None:
    if db.query(KnowledgeDocument.id).filter(KnowledgeDocument.title == TITLE).first():
        return
    approver = db.query(User).filter(User.role == UserRole.HR_ADMIN).order_by(User.id).first()
    if approver is None:
        return
    doc = KnowledgeDocument(
        title=TITLE,
        category="HR Operations",
        description="Leave calendar, family leave, business trips, certificates, overtime, resignation and profile changes.",
        version="1.0",
        is_active=True,
        is_approved=True,
        is_synthetic=True,
        approved_by_id=approver.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()
    db.add_all(
        KnowledgeChunk(
            document_id=doc.id,
            section_title=title,
            content=content,
            tags=tags,
            access_level="all",
        )
        for title, content, tags in SECTIONS
    )
    db.flush()
