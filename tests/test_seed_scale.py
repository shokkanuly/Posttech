"""Company-scale demo data must be repeatable and obey the same rules as the API."""

from itertools import combinations

from app.models.enums import RequestStatus, RequestType
from app.models.profile import EmployeeProfile
from app.models.request import Request
from app.models.user import User
from app.seed_scale import seed_scale
from app.services.request_service import request_service


def test_scale_seed_is_idempotent_and_consistent(db_session, client, manager_headers):
    first = seed_scale(db_session, employees=30)
    assert first["users"] == 37 and first["requests"] > 30
    assert seed_scale(db_session, employees=30) == {"skipped": True}

    for profile in db_session.query(EmployeeProfile).filter(
        EmployeeProfile.employee_code.like("JP-2%")
    ):
        vacations = (
            db_session.query(Request)
            .filter(
                Request.user_id == profile.user_id,
                Request.type == RequestType.VACATION,
                Request.status.in_([RequestStatus.PENDING, RequestStatus.APPROVED]),
            )
            .all()
        )
        for a, b in combinations(vacations, 2):
            assert a.end_date < b.start_date or b.end_date < a.start_date, profile.employee_code
        reserved = request_service.leave_summary(db_session, [profile.user_id])[profile.user_id]
        assert profile.leave_balance_days >= reserved["pending_days"] >= 0

    team = client.get("/api/v1/manager/team", headers=manager_headers).json()
    assert len(team) == 12  # 3 base reports + 9 generated
    generated = next(m for m in team if m["employee_code"].startswith("JP-2"))
    card = client.get(f"/api/v1/manager/team/{generated['user_id']}", headers=manager_headers)
    history = card.json()["history"]
    assert any(item["event"] == "SUBMITTED" for item in history)
    assert [item["at"] for item in history] == sorted((i["at"] for i in history), reverse=True)


def test_history_shows_decisions_with_actor_and_comment(client, manager_headers, db_session):
    aruzhan = db_session.query(User).filter_by(email="aruzhan@janapost.kz").one()
    card = client.get(f"/api/v1/manager/team/{aruzhan.id}", headers=manager_headers).json()
    approved = [h for h in card["history"] if h["event"] == "APPROVED"]
    assert approved and approved[0]["actor"] == "Timur Kasymov"
    assert any(h["kind"] == "learning" for h in card["history"])
