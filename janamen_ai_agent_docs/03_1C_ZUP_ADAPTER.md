# 03 — 1C:ЗУП (1C:ZUP) Adapter Specification

## 1. Purpose and confidence boundary

Intended responsibilities:

- Read the authoritative employee and organization fields approved for JanaМен.
- Read leave balances and their effective/as-of date if the configured 1C system exposes the required calculation.
- In a later, separately approved phase, submit a fully approved HR operation or retrieve the official record/reference after 1C processing, **only if the actual configuration and business process support it**.

**Unknown at planning time:** deployment (cloud/on-premises), product/platform version, exact configuration/localization, service publication, visible OData objects, custom HTTP services, auth mode, network access, employee keys, leave-balance source, approval and posting logic. Do not treat this document as proof that any specific 1C endpoint exists.

## 2. Integration options to discover

1C:Enterprise can provide a standard REST/OData interface when the applied solution is published and objects are made available through it. The standard interface uses OData v3. Publishing and the available objects depend on the real infobase/configuration. Official references:

- REST interface overview: <https://kb.1ci.com/1C_Enterprise_Platform/1C_Enterprise_Platform_Overview/Integration/REST_interface/>
- Publishing standard REST API for an infobase: <https://kb.1ci.com/1C_Enterprise_Platform/FAQ/Development/Integration/Publishing_standard_REST_API_for_your_infobase/?language=en>

Potential implementation patterns, in order of preference after discovery:

1. A customer/vendor-approved purpose-built HTTP service with stable business operations for employees, leave balance, and vacation handoff.
2. Published OData objects for explicitly approved reads, when their semantics meet the required contract.
3. A custom 1C-side extension/service if current metadata does not safely expose required data or an official transaction must be created through business logic.

Do not perform generic CRUD against arbitrary 1C metadata objects as a substitute for understanding HR business logic. For posting documents, leave accruals, or balance calculations, use a supported business operation, not guesses about low-level records.

## 3. Internal adapter interface

The domain layer should code against an internal normalized interface, not 1C endpoint names. A Python protocol can be similar to:

```python
from datetime import datetime, date
from decimal import Decimal
from typing import Protocol, Sequence

class HRAdapter(Protocol):
    async def get_employee(self, external_employee_id: str) -> "EmployeeRecord | None": ...
    async def list_employees_changed_since(
        self, cursor: str | None, limit: int = 500
    ) -> "EmployeePage": ...
    async def get_leave_balance(
        self, external_employee_id: str, leave_type: str, as_of: date | None = None
    ) -> "LeaveBalance": ...
    async def submit_approved_leave(
        self, command: "ApprovedLeaveHandoff", idempotency_key: str
    ) -> "HRTransactionResult": ...
    async def get_transaction_status(
        self, external_reference: str
    ) -> "HRTransactionResult": ...
```

The real adapter may implement only capabilities confirmed by the real contract. Represent unsupported operations explicitly (for example, `CapabilityNotConfigured`) instead of pretending that they succeeded. In mock mode, implement the supported interface deterministically.

### Internal value objects

`EmployeeRecord`

- `external_id: str` — stable employee reference from the configured 1C object/service.
- `employee_number: str | None`
- `full_name: str`
- `department_external_id: str | None`
- `department_name: str | None`
- `job_title: str | None`
- `manager_external_id: str | None`
- `employment_status: enum/string from an approved mapping`
- `email: str | None` — only if approved for the app.
- `effective_at: datetime | None`
- `source_updated_at: datetime | None`
- `source_version: str | None`

`EmployeePage`

- `items: list[EmployeeRecord]`
- `next_cursor: str | None`
- `is_complete_snapshot: bool` — true only if the service contract explicitly says the page run is a full snapshot.

`LeaveBalance`

- `employee_external_id: str`
- `leave_type: str` — normalized from a confirmed mapping.
- `available_days: Decimal`
- `as_of: datetime | date`
- `period_start: date | None`
- `period_end: date | None`
- `source_version: str | None`
- `retrieved_at: datetime`

`ApprovedLeaveHandoff`

- `janamen_request_id: UUID`
- `employee_external_id: str`
- `start_date: date`
- `end_date: date`
- `leave_type: str`
- `approved_by_external_id: str | None`
- `approval_timestamp: datetime`
- `documentolog_document_id: str | None`
- `correlation_id: UUID`

This is an internal command, **not a claim about 1C's field names**. The live adapter maps it only after the 1C administrator confirms the required object, fields, transaction flow, and validation rules.

`HRTransactionResult`

- `state: enum(PENDING, ACCEPTED, COMPLETED, REJECTED, UNKNOWN, UNSUPPORTED)`
- `external_reference: str | None`
- `message_code: str | None`
- `safe_message: str | None`
- `confirmed_at: datetime | None`
- `raw_status_code: str | None` — optional, redacted and provider-specific.

## 4. Data flow

### 1C → JanaМен: employee sync

1. Worker calls the adapter with `cursor` and a page size.
2. Adapter normalizes provider response into `EmployeeRecord`.
3. Sync service validates mandatory fields and approved enums.
4. Resolve internal employee identity through an existing stable ID mapping. Do not match by name.
5. Upsert authoritative fields transactionally, record `source_updated_at`, update the sync cursor only after the page has been committed.
6. Unknown or ambiguous records go to quarantine; do not attach them to an arbitrary internal account.
7. Retain existing employees when an incremental response omits them. Mark a record inactive only from an explicit authoritative status/deletion signal or verified full-snapshot reconciliation.

### 1C → JanaМен: leave balance

- Query on demand or with a short configurable cache; do not query 1C for each dashboard component render.
- Store numeric amount as `Decimal`, plus leave type, period, `as_of`, retrieval timestamp, and source version.
- Distinguish `FRESH`, `STALE`, `UNAVAILABLE`, and `NOT_FOUND`. A missing response is not zero days.
- Define staleness threshold in configuration/business requirements. Until then, show the timestamp and avoid a hard-coded promise that a balance is real-time.
- The 1C result is authoritative; a UI display or cached value does not reserve leave in 1C.

### JanaМен → 1C: official operation (later phase)

This write is disabled by default. Before enabling it, require:

- verified object/service and schema;
- documented service account permissions;
- official mapping and date/leave type semantics;
- documented validation/business workflow, including whether and by whom a record must be posted;
- stable idempotency or remote duplicate-detection strategy;
- sandbox tests confirming the transaction and how to query its outcome;
- named HR owner approval.

Do not automatically interpret a manager approval or Documentolog signature as a completed 1C HR transaction.

## 5. HTTP/auth/retry behavior

The actual transport may be OData or a custom service. Isolate this in `onec/live.py` and configuration. Use HTTPX with timeouts, TLS verification, bounded connection pools, and redaction filters. Authentication may be Basic/service credentials, web-server/SSO mechanisms, or a dedicated service credential; determine this with the 1C admin and never guess.

Normalize at least these errors:

- `AUTH_FAILED`: 401/403 or provider's equivalent.
- `VALIDATION_FAILED`: invalid request/field/business rule; don't retry automatically.
- `NOT_FOUND`: mapped external employee/transaction does not exist.
- `RATE_LIMITED`: 429 or explicit provider throttling; respect `Retry-After` if present.
- `TIMEOUT`: remote response not received; read operations can usually retry; writes may have unknown outcome.
- `PROVIDER_UNAVAILABLE`: transient 5xx/network error.
- `CONFLICT`: stale version, duplicate, or business-state conflict.
- `UNKNOWN_OUTCOME`: write may have succeeded but response was lost; reconcile before resubmission.

Do not retry 4xx validation/authentication errors by default. For read timeout/5xx, use a bounded exponential backoff with jitter. For a write timeout, look up by external reference/correlation key if supported; otherwise send to manual reconciliation instead of issuing a blind duplicate.

## 6. Configuration placeholders

```dotenv
INTEGRATION_MODE=mock
ONEC_ADAPTER=mock
ONEC_BASE_URL=
ONEC_AUTH_MODE=
ONEC_USERNAME=
ONEC_PASSWORD=
ONEC_TOKEN_URL=
ONEC_CONNECT_TIMEOUT_SECONDS=3
ONEC_READ_TIMEOUT_SECONDS=10
ONEC_WRITE_ENABLED=false
ONEC_EMPLOYEE_OBJECT=
ONEC_LEAVE_BALANCE_OPERATION=
ONEC_LEAVE_SUBMISSION_OPERATION=
```

Use secret-manager references or secret environment injection in deployed environments. Placeholder names are proposed conventions, not 1C-required names. Do not set live values until the open questions are resolved.

## 7. 1C discovery checklist

Ask the customer/1C admin to confirm:

- Full product name and configuration (specifically 1C:ZUP for Kazakhstan or another localized variant), release/version, platform version.
- Cloud/on-premises/hosted deployment; network route; VPN/IP restrictions; TLS and certificate chain.
- Whether OData is published; base URL; visible metadata; list of permitted entities and properties; allowed methods.
- If a custom HTTP service exists, the OpenAPI/contract and release process for changes.
- Auth scheme, service account, least-privilege roles, account rotation procedure.
- Stable employee key and employee-number uniqueness rules.
- Org-unit / manager semantics and employment-status values.
- Exact leave balance source, accrual period, rounding, approved leave deductions, leave types, stale-data expectations.
- Official vacation handoff format, workflow/posting requirements, external idempotency, official reference and status query.
- Rate limits, batch limits, maintenance windows, audit expectations, sandbox dataset and contacts.

Until this checklist is answered, mock is the only supported execution mode.

## Existing JanaМен implementation status (QA baseline 2026-10-17)

The supplied report establishes that current code implements **signed MOCK employee-code snapshot ingestion**, not a real 1C:ЗУП API connector. The path is `app/integrations/profile_sync.py` plus the mock snapshot source in `app/gateway/`; existing profile records only are updated, and source/as-of/sync metadata is saved. Last-known snapshots remain readable during gateway outages. Unknown employee mappings and balance conflicts enter HR review, but the authorized resolution/remapping workflow is still missing.

Before implementing the future read adapter, extend this existing snapshot/domain boundary. Do not create duplicate profile tables/sync orchestration. Preserve stable employee-code matching and no automatic account provisioning. Live source metadata, auth and endpoints have not been verified. Official 1C write-back is not implemented and must stay disabled until separately approved.

Known gap: HR can inspect unknown mappings but cannot yet safely resolve/remap them; see `12_QA_REMEDIATION_PLAN.md` Stage 2.
