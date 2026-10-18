"""Which days of a vacation are charged, under the Labour Code of Kazakhstan.

Annual leave is counted in calendar days: weekends inside it are charged, public holidays
are not. The fixed-date public holidays below follow the Law "On holidays in the Republic
of Kazakhstan" and always apply; LEAVE_EXCLUDED_DATES adds extra HR-approved dates.
Religious days off (Orthodox Christmas, Kurban Ait) are days off, not holidays, so they
are charged like weekends.
"""

from datetime import date, timedelta
from typing import Literal

from app.config import settings

HOLIDAYS = {
    (1, 1): "New Year",
    (1, 2): "New Year",
    (3, 8): "International Women's Day",
    (3, 21): "Nauryz",
    (3, 22): "Nauryz",
    (3, 23): "Nauryz",
    (5, 1): "Kazakhstan People's Unity Day",
    (5, 7): "Defender of the Fatherland Day",
    (5, 9): "Victory Day",
    (7, 6): "Capital Day",
    (8, 30): "Constitution Day",
    (10, 25): "Republic Day",
    (12, 16): "Independence Day",
}

DayKind = Literal["workday", "weekend", "holiday"]


def holiday_name(day: date) -> str | None:
    name = HOLIDAYS.get((day.month, day.day))
    if name is None and day in settings.LEAVE_EXCLUDED_DATES:
        return "HR-approved non-working day"
    return name


def day_kind(day: date) -> DayKind:
    if holiday_name(day):
        return "holiday"
    # ponytail: Saturday/Sunday five-day week; shift rosters need a per-employee schedule.
    return "weekend" if day.weekday() >= 5 else "workday"


def breakdown(start: date, end: date | None) -> list[dict]:
    last = end or start
    days = [start + timedelta(days=i) for i in range((last - start).days + 1)]
    return [{"day": d, "kind": day_kind(d), "holiday": holiday_name(d)} for d in days]


def charged_days(start: date, end: date | None) -> float:
    return float(sum(day["kind"] != "holiday" for day in breakdown(start, end)))


if __name__ == "__main__":
    # 26 Nov 2026 – 21 Jan 2027: 57 calendar days, 3 holidays (16 Dec, 1–2 Jan) → 54 charged.
    assert charged_days(date(2026, 11, 26), date(2027, 1, 21)) == 54.0
    assert day_kind(date(2026, 11, 28)) == "weekend" and day_kind(date(2026, 12, 16)) == "holiday"
    assert day_kind(date(2027, 1, 7)) == "workday"  # Orthodox Christmas: a charged day off
    print("ok")
