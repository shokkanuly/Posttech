"""Regression checks added during the full-project QA review."""

import pytest

from app.config import settings
from app.integrations import gemini, outbox
from app.models import EmployeeProfile, IntegrationOutbox, Notification, Request, RequestEvent
from app.models.enums import RequestStatus
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.audit_service import audit_service
from app.services.knowledge_conflicts import has_conflicting_numeric_claims
from app.services.notification_service import notification_service


def approved_claim(db, language, title, content, access="all", approved=True):
    document = KnowledgeDocument(
        title="Synthetic QA policy",
        language=language,
        is_synthetic=True,
        is_approved=approved,
    )
    document.chunks.append(
        KnowledgeChunk(section_title=title, content=content, access_level=access)
    )
    db.add(document)
    db.commit()


def test_numeric_conflict_check_preserves_equivalent_and_complementary_claims():
    assert not has_conflicting_numeric_claims(["Leave is 24 days.", "Leave is 24.0 days."])
    assert not has_conflicting_numeric_claims(["Leave is 24 days.", "Apply 14 days ahead."])
    assert has_conflicting_numeric_claims(["Leave is 24 days.", "Leave is 40 days."])


@pytest.mark.parametrize("provider_enabled", [False, True])
@pytest.mark.parametrize(
    "language,question,claim",
    [
        ("en", "Qacheckpolicy vacation days?", "Qacheckpolicy vacation days are {} calendar days."),
        ("ru", "Qacheckpolicy отпуск дней?", "Qacheckpolicy отпуск составляет {} дней."),
        ("kk", "Qacheckpolicy демалыс күндері?", "Qacheckpolicy демалыс ұзақтығы {} күн."),
    ],
)
def test_conflicting_approved_numbers_fall_back_before_provider(
    client, db_session, employee_headers, monkeypatch, provider_enabled, language, question, claim
):
    # The third passage must still be checked when an answer would cite only two.
    for days in (24, 24, 40):
        approved_claim(db_session, language, "Qacheckpolicy vacation", claim.format(days))
    calls = []
    monkeypatch.setattr(gemini, "enabled", lambda: provider_enabled)
    monkeypatch.setattr(gemini, "generate_grounded_answer", lambda *args: calls.append(args))
    result = client.post(
        "/api/v1/ai/chat",
        headers={**employee_headers, "Accept-Language": language},
        json={"question": question},
    )
    assert result.status_code == 200
    answer = result.json()
    assert answer["answer_status"] == "fallback"
    assert answer["sources"] == []
    assert answer["escalation_guidance"]
    assert calls == []


@pytest.mark.parametrize("access,approved", [("hr_admin", True), ("all", False)])
def test_unreadable_conflict_cannot_influence_employee_answer(
    client, db_session, employee_headers, access, approved
):
    approved_claim(db_session, "en", "Qacheckpolicy", "Qacheckpolicy vacation days are 24 days.")
    approved_claim(
        db_session,
        "en",
        "Qacheckpolicy",
        "Qacheckpolicy vacation days are 40 days.",
        access,
        approved,
    )
    answer = client.post(
        "/api/v1/ai/chat",
        headers=employee_headers,
        json={"question": "Qacheckpolicy vacation days?"},
    ).json()
    assert answer["answer_status"] == "grounded"
    assert "40" not in answer["answer"]


@pytest.mark.parametrize("failure_stage", ["enqueue", "notification", "audit"])
def test_failed_approval_rolls_back_outbox_and_all_business_effects(
    client, db_session, employee_headers, manager_headers, monkeypatch, failure_stage
):
    monkeypatch.setattr(settings, "INTEGRATION_GATEWAY_URL", "http://gateway.invalid")
    created = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={"type": "Vacation", "start_date": "2026-12-07", "end_date": "2026-12-08"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    before_notifications = db_session.query(Notification).count()
    profile = db_session.query(EmployeeProfile).filter_by(user_id=3).one()
    before_balance = profile.leave_balance_days
    original_enqueue = outbox.enqueue

    def fail(*args, **kwargs):
        if failure_stage == "enqueue":
            original_enqueue(*args, **kwargs)
            args[0].flush()
        raise RuntimeError("synthetic transaction failure")

    target, name = {
        "enqueue": (outbox, "enqueue"),
        "notification": (notification_service, "create_notification"),
        "audit": (audit_service, "log_event"),
    }[failure_stage]
    monkeypatch.setattr(target, name, fail)
    result = client.post(f"/api/v1/requests/{rid}/approve", headers=manager_headers)
    assert result.status_code == 500
    assert "synthetic transaction failure" not in result.text
    db_session.expire_all()
    request = db_session.get(Request, rid)
    assert request.status == RequestStatus.PENDING
    assert request.integration_status is None
    assert request.charged_leave_days is None
    assert db_session.query(IntegrationOutbox).filter_by(request_id=rid).count() == 0
    assert db_session.query(Notification).count() == before_notifications
    assert db_session.query(RequestEvent).filter_by(request_id=rid).count() == 1
    assert (
        db_session.query(EmployeeProfile).filter_by(user_id=3).one().leave_balance_days
        == before_balance
    )
