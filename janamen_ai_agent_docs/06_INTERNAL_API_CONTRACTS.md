# 06 — JanaМен Internal API Contracts

These contracts describe desired semantics and examples; they are **not assertions that these exact route names already exist**. Current repository routes/schemas/OpenAPI are authoritative. Before adding an endpoint, inspect `app/routers/`, `app/schemas/`, `docs/openapi.json` and tests to extend the existing route instead of creating a duplicate API.

## Current contract constraints from QA

- Current auth is revocable DB-backed bearer sessions; roles are loaded/validated server-side. Never accept an employee ID or role in body as authorization authority.
- Request creation currently validates normal API inputs but has a reproduced gap for client submission idempotency: two identical advance submissions created two separate requests. This must be fixed before claiming full request idempotency.
- Manager approval, audit/history/notification and app outbox insertion occur in a single transaction; external calls happen later in the worker.
- Current document integration statuses include `NOT_REQUIRED`, `PENDING`, `SENT`, `REGISTERED`, `FAILED`, and `DEAD` as applicable. Use current schema names and meanings; don't silently replace them with the generic labels below.
- Document job request to the internal gateway uses signed machine auth. Gateway `POST /v1/documents` returns `202` for persisted async work. This route is internal, not a public vendor endpoint.
- Current callback path is an internal app route (see `app/routers/internal.py:documentolog_status`); inspect its actual URL/schema before changing it.

## Semantics to preserve

### Request create idempotency (required gap fix)

For a client-generated idempotency key scoped to the authenticated employee and operation:

- same key + same normalized business payload -> return original request/result without additional side effects;
- same key + different normalized payload -> `409 IDEMPOTENCY_KEY_REUSED`;
- concurrent duplicate calls -> exactly one request and one set of balance/history/notification/audit/outbox effects;
- same opaque key from a different employee must not expose or retrieve another employee's request.

Proposed header vocabulary (adapt to existing conventions):

```http
Idempotency-Key: <client-generated-uuid>
Content-Type: application/json
```

Do not implement only in frontend memory; persist key/digest with database uniqueness.

### Authorization

- Derive identity from validated DB-backed session.
- Verify request ownership, assigned-manager scope, HR role and active account on every protected read/write.
- Frontend visibility is not authorization.
- Gateway machine-auth routes must reject user bearer tokens; callback auth is independent of front-end roles.

### Integration status

Expose safe operational status using existing admin/status endpoints if present. At minimum authorized operators need to distinguish:

- mock vs unconnected vs verified live mode;
- last successful sync/snapshot freshness;
- pending/running/failed/dead jobs;
- last safe error code and correlation ID;
- supported/disabled/unverified capabilities.

Do not reveal private base URLs, credentials, IIN/BIN, full provider payloads, tokens or signed-document URLs to ordinary users.

### Outbox and gateway

- Approval/business transaction only persists the immutable work snapshot; no provider network call inside the transaction.
- Retry the same logical operation with original immutable idempotency key and payload.
- Validate acknowledgement/event against expected request, job and key.
- Duplicate callback is acknowledged safely but adds no second state transition, audit event, notification or external registration.
- A failed registration does not reverse manager approval automatically.
- A timeout after possible remote acceptance enters reconciliation; no blind repeat-create.

### 1C profile snapshot

Current path consumes signed mock employee-code snapshots and maps existing profiles only. When a real read adapter is approved, normalize provider field differences at the adapter edge and preserve source, as-of timestamp, freshness, external mapping and controlled HR review. Unknown employee codes must not create user accounts automatically.

## Illustrative future API shapes (not a mandate to add new paths)

The earlier integration design proposed endpoints such as request create/list/detail, integration status, manual sync, reconciliation, replay and Documentolog webhook receiver. Treat these as semantic examples only. Use current route names and align tests/OpenAPI if equivalent operations already exist. Any new replay/remapping endpoint must be HR-only and auditable. Provider webhook paths must remain disabled until the real vendor auth scheme is confirmed.

Example safe error shape:

```json
{
  "error": {
    "code": "INTEGRATION_OUTCOME_UNKNOWN",
    "message": "The external operation may have been accepted. Its status must be reconciled before another submission.",
    "correlation_id": "<uuid>",
    "retryable": false
  }
}
```

Do not include stack traces or provider raw bodies. `retryable: false` means no blind automatic repeat; it may still permit a separate operator-controlled reconciliation action.

## Status model guidance

The target design separates business approval, document registration/signature, and official HR processing. Use existing schema names where equivalent; add fields/enums through migration only if a real requirement is missing.

- `request_status` — business request lifecycle.
- `approval_status` — manager/HR decision lifecycle, if separately represented.
- `sync_status` / `document_status` — integration delivery/registration/signature where actually supported.
- `hr_processing_status` — official 1C processing, only after a real 1C contract exists.

`REGISTERED` means the mock connector registered a document/job, not that a real document has been signed. `APPROVED` means the manager approved; it does not mean official 1C processing completed. Do not mark `COMPLETED` until all steps required by the approved request-type policy have evidence.
