"""Future 1C boundary. No employee data is fetched or verified externally."""

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


one_c_adapter = OneCZupAdapter()
