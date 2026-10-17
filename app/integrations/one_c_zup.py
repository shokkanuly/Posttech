"""Unconnected 1C boundary. Leave days use the local calendar in app.leave_calendar.

No production calendar or official policy is fetched from 1C.
"""

from datetime import date

from app import leave_calendar
from app.schemas.integration import AdapterTelemetry


class OneCZupAdapter:
    def get_telemetry(self):
        return AdapterTelemetry(
            adapter_name="1C:ZUP",
            status="UNCONNECTED",
            mode="Unconnected",
            endpoint_template="Not configured",
            synced_records_count=0,
            last_sync=None,
            supported_operations=[],
            notes="Profiles and leave balances are local records. No 1C credentials, API documentation or connection is configured.",
        )

    @staticmethod
    def vacation_days(start: date, end: date | None) -> float:
        """Calendar days minus public holidays and HR-approved exclusions (local calendar)."""
        return leave_calendar.charged_days(start, end)


one_c_adapter = OneCZupAdapter()
