"""Our canonical gateway contract. These are NOT 1C or Documentolog APIs."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

BACKOFF_SECONDS = (30, 60, 300, 900, 3600, 21600, 43200)
CALLBACK_PATH = "/api/v1/internal/integrations/documentolog/status"
Code = Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")]
IdempotencyKey = Annotated[str, Field(min_length=4, max_length=100, pattern=r"^[A-Za-z0-9_:-]+$")]
JobId = Annotated[str, Field(pattern=r"^job_[a-f0-9]{32}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Period(Contract):
    start: date
    end: date
    days: float = Field(gt=0, le=731)

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start or self.days > (self.end - self.start).days + 1:
            raise ValueError("Invalid period")
        return self


class DocumentRequest(Contract):
    idempotency_key: IdempotencyKey
    kind: Literal["VACATION_REQUEST", "ADVANCE_PAYMENT_REQUEST"]
    request_code: Code
    employee_code: Code
    period: Period | None = None
    # Canonical extension for advance requests; never a payment instruction.
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: Literal["KZT"] | None = None
    approved_by_employee_code: Code
    approved_at: AwareDatetime

    @model_validator(mode="after")
    def correct_kind(self):
        if self.idempotency_key != f"{self.request_code}:v1":
            raise ValueError("Key must identify this request version")
        if self.kind == "VACATION_REQUEST":
            if self.period is None or self.amount is not None or self.currency is not None:
                raise ValueError("Vacation requires only a period")
        elif self.amount is None or self.currency != "KZT" or self.period is not None:
            raise ValueError("Advance requires an amount in KZT")
        return self


class JobStatus(Contract):
    gateway_job_id: JobId
    idempotency_key: IdempotencyKey
    status: Literal["PENDING", "PROCESSING", "REGISTERED", "FAILED", "DEAD"]
    mode: Literal["MOCK"]
    external_ref: str | None = Field(default=None, pattern=r"^MOCK-DOC-[a-f0-9]{32}$")
    occurred_at: AwareDatetime
    error_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,40}$")
    recovery_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @model_validator(mode="after")
    def registration_has_reference(self):
        if self.status == "REGISTERED" and self.external_ref is None:
            raise ValueError("Registration requires an external reference")
        return self


class RegistrationResult(JobStatus):
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
    status: Literal["REGISTERED", "FAILED", "DEAD"]


class RecoveryCommand(Contract):
    gateway_job_id: JobId
    recovery_key: str = Field(pattern=r"^[a-f0-9]{32}$")


class EmployeeSnapshot(Contract):
    employee_code: Code
    full_name: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    department: str = Field(min_length=1, max_length=255)
    position: str = Field(min_length=1, max_length=255)
    manager_employee_code: Code | None = None
    hire_date: date
    leave_balance_days: float = Field(ge=0, le=1000)
    as_of: AwareDatetime
    # Explicit confirmations prevent counting a local approval twice at reconciliation.
    confirmed_request_codes: list[Code] = Field(default_factory=list, max_length=1000)


class EmployeePage(Contract):
    mode: Literal["MOCK"]
    employees: list[EmployeeSnapshot] = Field(max_length=1000)
    next_cursor: AwareDatetime


class GatewayHealth(Contract):
    status: Literal["healthy"]
    mode: Literal["MOCK"]
    one_c: Literal["MOCK", "UNAVAILABLE"]
    documentolog: Literal["MOCK", "UNAVAILABLE"]
    pending_jobs: int = Field(ge=0)
    pending_callbacks: int = Field(ge=0)
    last_success: datetime | None
