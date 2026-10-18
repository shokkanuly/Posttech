# 05 — Data Model, Identifiers, and Mapping

## 1. Identity rules

- Each JanaМен employee has an internal immutable `employee_id` (UUID preferred).
- A provider employee reference is stored separately and namespaced by provider/configuration. An employee number is not assumed globally unique unless the owner confirms its uniqueness scope.
- Never match records by name, transliteration, email, or department alone. These may be used only as review hints, not automatic identity resolution.
- Keep a stable mapping table and record mapping creation/update audit events.

## 2. Suggested tables

Adapt to the current ORM/database conventions. Do not create parallel schemas if equivalent tables already exist.

### `employees`

- `id UUID PRIMARY KEY`
- `employee_number TEXT NULL`
- `full_name TEXT NOT NULL`
- `department_id UUID NULL`
- `manager_employee_id UUID NULL`
- `job_title TEXT NULL`
- `employment_status TEXT NOT NULL`
- `email TEXT NULL` (only if approved)
- `source_provider TEXT NOT NULL`
- `source_updated_at TIMESTAMPTZ NULL`
- `last_synced_at TIMESTAMPTZ NULL`
- `record_freshness TEXT NOT NULL` (`FRESH`, `STALE`, `UNAVAILABLE`, `UNKNOWN`)
- `created_at`, `updated_at`

Store the canonical internal user/auth account separately if authentication has different lifecycle/permissions. Avoid granting login access solely because a row was imported from 1C.

### `external_id_mappings`

- `id UUID PRIMARY KEY`
- `provider TEXT NOT NULL` (`onec`, `documentolog`)
- `entity_type TEXT NOT NULL` (`employee`, `department`, `document`, `hr_transaction`)
- `internal_id UUID NOT NULL`
- `external_id TEXT NOT NULL`
- `source_key_type TEXT NULL` (document what the ID represents)
- `created_at TIMESTAMPTZ NOT NULL`
- `last_verified_at TIMESTAMPTZ NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'`

Constraints: unique `(provider, entity_type, external_id)` and, where one-to-one identity is intended, unique `(provider, entity_type, internal_id)`. If multiple external references per internal entity are legitimate, model that explicitly rather than removing all constraints.

### `leave_balances`

- `id UUID PRIMARY KEY`
- `employee_id UUID NOT NULL`
- `leave_type TEXT NOT NULL`
- `available_days NUMERIC(8,2) NOT NULL`
- `period_start DATE NULL`, `period_end DATE NULL`
- `as_of TIMESTAMPTZ NOT NULL`
- `retrieved_at TIMESTAMPTZ NOT NULL`
- `source_provider TEXT NOT NULL`
- `source_version TEXT NULL`
- `freshness TEXT NOT NULL`
- unique/index policy based on employee + leave type + period/as-of rules confirmed with HR.

Do not default missing values to `0`. A missing or stale balance must be a separate state.

### `requests`

- `id UUID PRIMARY KEY`
- `request_number TEXT UNIQUE`
- `request_type TEXT NOT NULL` (e.g. `VACATION`)
- `employee_id UUID NOT NULL`
- `manager_employee_id UUID NULL` (snapshot or reference per policy)
- `start_date DATE NULL`, `end_date DATE NULL`
- `reason TEXT NULL` (PII-sensitive; restrict visibility and retention)
- `request_status TEXT NOT NULL`
- `approval_status TEXT NOT NULL`
- `document_status TEXT NOT NULL`
- `hr_processing_status TEXT NOT NULL`
- `idempotency_key_hash TEXT NULL`
- `correlation_id UUID NOT NULL`
- `version INTEGER NOT NULL DEFAULT 1`
- timestamps and actor IDs

Do not store the raw idempotency key unless required. Use a hash or scoped key table.

### `request_events` (append-only)

- `id UUID PRIMARY KEY`
- `request_id UUID NOT NULL`
- `event_type TEXT NOT NULL`
- `actor_type TEXT NOT NULL`
- `actor_id UUID NULL`
- `from_state JSONB NULL`, `to_state JSONB NULL`
- `reason_code TEXT NULL`
- `metadata JSONB NOT NULL DEFAULT '{}'` (redacted; allowlist fields)
- `occurred_at TIMESTAMPTZ NOT NULL`
- `correlation_id UUID NOT NULL`

### `external_documents`

- `id UUID PRIMARY KEY`
- `request_id UUID NOT NULL`
- `provider TEXT NOT NULL`
- `external_document_id TEXT NULL`
- `status TEXT NOT NULL`
- `document_url TEXT NULL`
- `download_link_metadata JSONB NULL` (avoid long-lived secrets; protect URLs)
- `token_secret_ref TEXT NULL` or encrypted storage reference if needed
- `submitted_at TIMESTAMPTZ NULL`
- `completed_at TIMESTAMPTZ NULL`
- `last_provider_event_at TIMESTAMPTZ NULL`
- `last_reconciled_at TIMESTAMPTZ NULL`
- `submission_payload_digest TEXT NULL`
- `created_at`, `updated_at`

Never render provider URLs to users without request-level authorization. Avoid storing a Documentolog bearer token as plaintext. Prefer secret-manager references or an envelope-encrypted field with narrowly scoped access.

### `integration_jobs` / transactional outbox

- `id UUID PRIMARY KEY`
- `provider TEXT NOT NULL`
- `operation TEXT NOT NULL`
- `aggregate_type TEXT NOT NULL`
- `aggregate_id UUID NOT NULL`
- `idempotency_key TEXT NOT NULL` (internal key; avoid including PII)
- `correlation_id UUID NOT NULL`
- `payload JSONB NOT NULL` (only minimum required data; secrets/large files excluded)
- `status TEXT NOT NULL` (`PENDING`, `RUNNING`, `RETRY_WAIT`, `SUCCEEDED`, `FAILED`, `UNKNOWN_OUTCOME`, `DEAD_LETTER`)
- `attempt_count INTEGER NOT NULL DEFAULT 0`
- `next_attempt_at TIMESTAMPTZ NULL`
- `last_error_code TEXT NULL`
- `last_error_safe_message TEXT NULL`
- `lease_until TIMESTAMPTZ NULL`
- timestamps

Use a unique constraint on a properly scoped idempotency key + operation where appropriate. Job consumers must be safe if a lease expires and a job is executed again.

### `integration_events`

Stores webhook ingestion/deduplication metadata: provider, event fingerprint, external document ID, event type, payload digest, received timestamp, validation status, processing status, redacted metadata. Unique constraint on provider + event fingerprint. If exact provider event ID exists later, use that as primary dedupe key.

### `sync_cursors`

Store provider/resource cursor, last successful page timestamp, last full reconciliation timestamp, and run status. Update cursors only after corresponding records are committed.

### `audit_events`

Capture actor/action/target/time/correlation ID/result. Do not store credentials, full IIN, full phone, full bearer URL/token, or unnecessary copies of documents.

## 3. Mapping contract

| JanaМен concept | 1C:ZUP source (to confirm) | Documentolog source | Rules |
|---|---|---|---|
| `employee_id` | Internal JanaМен UUID, linked to stable 1C key | usually not used | Never reuse for an external key |
| `external_employee_id` | Stable 1C employee reference, exact property unknown | recipient reference may be IIN/phone/email; not a substitute for employee ID | Keep separate by domain/namespace |
| `employee_number` | 1C employee number/code (property unknown) | n/a | Preserve as string, including leading zeros |
| `full_name` | Approved 1C field mapping | signer name may appear in webhook | Employee source controls authoritative display; webhook name is not identity proof |
| `department` | 1C unit reference/name (structure unknown) | n/a | Use mapped external department ID where possible |
| `manager` | 1C manager link or approved HR mapping | signer may be manager but must map explicitly | Manager approval permissions derive from authorized app/HR mapping, not name equality |
| `employment_status` | 1C employment status mapping | n/a | Map to documented internal enum; unknown values quarantine/alert |
| `leave_balance_days` | Confirmed 1C balance operation/report/register | n/a | Numeric decimal; keep `as_of`, leave type, period, freshness |
| `janamen_request_id` | Sent as correlation/metadata if provider operation supports it | Persist as local relation; include in safe metadata if supported | UUID and correlation ID are internal anchors |
| `external_document_id` | Optional reference in official HR transaction if supported | `doc_id` from webhook, or verified create response mapping | Never invent the external document ID from a URL |
| `document_status` | n/a | normalized webhook state | A signed document is not automatically a completed 1C transaction |
| `official_hr_reference` | Returned/queryable 1C transaction reference | n/a | Only set after provider confirms accepted/posted/complete per contract |

## 4. Time and numeric rules

- Transport timestamps: ISO 8601 with timezone/offset; normalize instants to UTC.
- Vacation start/end: use `DATE` unless the confirmed HR API contract requires time-of-day. Do not turn an all-day date into a UTC timestamp that can shift the calendar day.
- Use `Decimal` / SQL `NUMERIC` for leave days and money, never binary float for persisted HR amounts.
- Preserve provider source timestamp and JanaМен retrieval timestamp separately.
- If provider does not supply a source version or update time, store `NULL`; do not synthesize one and present it as authoritative.

## 5. Field ownership / update rules

| Field | Owner | JanaМен behavior |
|---|---|---|
| Legal employee identity and official employment fields | 1C/HR source of truth (confirm) | Read-only cache; correct upstream or through approved HR process |
| Current manager/department | 1C/HR source of truth (confirm) | Import and audit changes; no name-based inference |
| Leave balance | Confirmed 1C calculation/source | Read-only and freshness-tagged |
| Request narrative/date selection | JanaМен until submitted/approved | Version and audit edits; freeze critical fields at handoff |
| Internal approvals | JanaМен or mandated upstream workflow (confirm) | Keep role-authorized event history |
| Signature and official signed artifacts | Documentolog | Reflect verified provider events; secure downloads |
| Official HR record/reference | 1C | Mark complete only on verified transaction outcome |

## Existing schema caution (QA baseline 2026-10-17)

The current repo already has app models and versioned migrations `0001..0006`; inspect `app/models/`, `app/database.py` and `migrations/` before adding any table. Existing request/profile/integration models may already cover the proposed entity. Avoid duplicate tables and state columns.

The QA report found that API validation protects typical calls, but direct database writes can still accept negative leave balances, reversed request dates and unknown request status. Design guarded migrations after a preflight report of existing data; do not silently repair production or unknown data. The internal gateway's initial `create_all` initialization is separate from the app migration chain and needs a deliberate versioned upgrade plan before gateway schema changes.

Initial request-creation idempotency is also absent for advance requests: add a persisted employee-scoped key/body digest and uniqueness protection in the existing model/service path rather than assuming document idempotency already protects it.
