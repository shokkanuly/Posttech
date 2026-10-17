"""Unconnected 1C boundary. Leave exclusions are explicit local HR configuration.

No production calendar or official policy is fetched from 1C.
"""

from datetime import date

from app.config import settings
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
        """Calendar days minus explicitly configured excluded dates."""
        last = end or start
        span = (last - start).days + 1
        excluded = sum(start <= day <= last for day in set(settings.LEAVE_EXCLUDED_DATES))
        return float(max(span - excluded, 0))


one_c_adapter = OneCZupAdapter()
