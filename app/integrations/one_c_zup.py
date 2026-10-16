"""
1C:ZUP Enterprise HR Integration Adapter (Mocked Architecture Boundary)

In the production Jana Post architecture, this adapter connects to 1C:Enterprise (ЗУП 3.1)
via OData or REST HTTP services. Official employee records and leave balances originate in 1C:ZUP
and are treated as strictly READ-ONLY within JanaMen.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.config import settings
from app.schemas.integration import AdapterTelemetry, OneCProfileSyncResponse


class OneCZupAdapter:
    ADAPTER_NAME = "1C:Enterprise (ЗУП 3.1 - Payroll & HR)"
    MODE = "Mock Adapter (Synthetic Architecture Boundary)"

    def __init__(self):
        self.base_url = settings.MOCK_1C_BASE_URL
        self.is_mock = True

    def get_telemetry(self) -> AdapterTelemetry:
        return AdapterTelemetry(
            adapter_name=self.ADAPTER_NAME,
            status="READY_MOCK",
            mode=self.MODE,
            endpoint_template=f"{self.base_url}/odata/standard.odata/Catalog_Employees",
            synced_records_count=128,
            last_sync=datetime.now(timezone.utc),
            supported_operations=[
                "GET /Catalog_Employees(uuid)",
                "GET /InformationRegister_LeaveBalances/SliceLast()",
                "POST /Document_LeaveApplication (Planned Future Phase)",
            ],
            notes="Authoritative master source for employee hierarchy and annual leave balances. Read-only in JanaMen.",
        )

    def fetch_employee_leave_balance(self, employee_code: str) -> Dict[str, Any]:
        """
        Mock retrieval of leave balance from 1C:ZUP Information Register.
        Returns verified synthetic balance for the demo employee.
        """
        synthetic_mapping = {
            "JP-10428": {"balance": 18.5, "external_1c_uuid": "1c-uuid-4492-aruzhan"},
            "JP-10201": {"balance": 24.0, "external_1c_uuid": "1c-uuid-1102-timur"},
            "JP-10332": {"balance": 21.0, "external_1c_uuid": "1c-uuid-9844-dana"},
            "JP-10519": {"balance": 15.0, "external_1c_uuid": "1c-uuid-6213-ruslan"},
        }
        res = synthetic_mapping.get(employee_code, {"balance": 20.0, "external_1c_uuid": f"1c-uuid-{employee_code}"})
        return {
            "employee_code": employee_code,
            "external_id": res["external_1c_uuid"],
            "leave_balance_days": res["balance"],
            "as_of": datetime.now(timezone.utc).isoformat(),
            "source": "1C:ZUP v3.1 Mock Service",
        }

    def verify_sync(self, employee_code: str) -> OneCProfileSyncResponse:
        data = self.fetch_employee_leave_balance(employee_code)
        return OneCProfileSyncResponse(
            employee_code=employee_code,
            external_1c_id=data["external_id"],
            leave_balance_verified=data["leave_balance_days"],
            sync_status="SYNCHRONIZED_READONLY",
            timestamp=datetime.now(timezone.utc),
        )


one_c_adapter = OneCZupAdapter()
