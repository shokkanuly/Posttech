# 07 — Synchronization, Reliability, and Operations Runbook

## 1. Flows

### Flow A — 1C → JanaМен employee/organization sync

1. Trigger scheduled or admin-requested sync job.
2. Use provider cursor/change marker where actually supported. If not supported, use paginated listing and reconciliation policy.
3. Fetch a bounded page; normalize to internal contract; validate mandatory fields and enums.
4. Resolve stable external IDs; quarantine ambiguous/unmapped items.
5. Upsert rows and mapping records in a transaction.
6. Commit the page, then advance cursor. A failed transaction must not advance it.
7. Save run metrics: records scanned/upserted/quarantined, duration, cursor, last successful completion.
8. After incremental changes, run a full reconciliation only where the provider can return a reliable complete snapshot. Never treat absence in an incremental page as deletion.

Suggested starting interval: every 15 minutes for employee metadata, if the real environment and load permit. This is a design suggestion, not a vendor guarantee; make it configurable. For employee page size, begin with 100–500 and tune against actual limits.

### Flow B — JanaМен → Documentolog after approval

1. Approval service validates state, role, document template, recipient/sender identifiers, and required signing options.
2. In one transaction, persist approval event and create durable document-submission job.
3. Worker acquires job lease and verifies current request is still eligible to send.
4. Generate or retrieve a stable immutable document artifact. Compute and persist a digest; do not change its contents after signature submission.
5. Check `send_now_confirmed` and configuration kill switch.
6. Call Documentolog adapter. In the public API flow, this create/token request may send immediately.
7. If a clear success response arrives, store external document ID and safe metadata. If clear rejection arrives, store normalized error.
8. If timeout/connection reset occurs after the request may have been transmitted, mark `SUBMISSION_UNKNOWN` / `UNKNOWN_OUTCOME`. Reconcile before any resubmission.
9. Ingest webhook events durably; update `document_status` via idempotent state machine.
10. Only mark signed when a verified `document_completed` or equivalent trusted server-side provider result is processed.

### Flow C — JanaМен → 1C official leave transaction (later phase only)

1. Only create a handoff after required manager/HR approvals and required signed documents.
2. Ensure official operation capability is explicitly `SUPPORTED`, `ONEC_WRITE_ENABLED=true` (or equivalent), and deployment release gate is approved.
3. Send a stable idempotency/correlation key only if the 1C contract supports it. Otherwise define a reliable duplicate-check strategy before enabling writes.
4. Store remote reference and status. If outcome is unclear, query the official status route before retrying or create a manual investigation item.
5. Use a configured definition of “complete” from HR/1C admin; do not use HTTP 200 alone if the business operation remains pending/not posted.

## 2. Suggested schedules (configurable)

- Employee/department incremental sync: every 15 minutes as a starting point.
- Leave balance: on demand with a small cache; optionally scheduled refresh based on HR's freshness requirement.
- Pending Documentolog reconciliation: every 2–5 minutes **only if** a status-query capability is confirmed; otherwise monitor webhooks and create manual reconciliation tasks for stale items.
- Retry worker: scan due retry jobs every minute.
- Full employee reconciliation: nightly or per operational agreement, only if the source supports a trustworthy complete listing.

These are initial operational defaults, not external-system SLAs.

## 3. Job state machine

`PENDING → RUNNING → SUCCEEDED`

`RUNNING → RETRY_WAIT` for a transient, safely retryable error.

`RUNNING → FAILED` for a known permanent failure such as invalid payload/credentials.

`RUNNING → UNKNOWN_OUTCOME` if a write might have succeeded but no trustworthy result was received.

`RETRY_WAIT → RUNNING` when due.

`FAILED → PENDING` only after an authorized operator fixes the cause and invokes an audited retry, where retry is safe.

`UNKNOWN_OUTCOME` must go through reconciliation/manual review; do not automatically transition it to `PENDING`.

After bounded attempts, move retryable jobs to `DEAD_LETTER`, preserve error code and recovery instructions, and alert the integration operator.

## 4. Retry strategy

- Use bounded exponential backoff with jitter; an illustrative schedule is 1s, 2s, 4s, then increasing intervals with a configured cap. Do not retry in a tight loop.
- Respect provider `Retry-After` where returned.
- Retry safe reads on timeouts/transient 5xx.
- Retry writes automatically only when idempotency/duplicate detection makes repeated submission safe.
- Never auto-retry validation failures, permission errors, unsupported fields, or unknown-outcome create/write calls.
- Token expiry may be handled by the provider's documented token refresh flow only when it won't duplicate/create a second document.

## 5. Idempotency and duplicates

### Internal HTTP operations

Scope key to `(actor/client, endpoint, key)` and persist the normalized request payload digest and original response. Same key + same payload returns prior result; same key + different payload returns a conflict.

### Jobs

Stable job key derived from operation + aggregate ID + workflow version; keep it free of PII. Enforce uniqueness in the database. Every worker action should be safe to rerun where possible.

### Webhooks

Use provider event ID if vendor supplies it. Public Documentolog examples do not show one, so create a canonical fingerprint from provider, external document ID, event type, normalized signer recipient hash, and canonical payload digest. Store unique constraint. Process events idempotently and do not discard legitimate distinct signer events.

### Remote calls

Do not assume provider honors JanaМен's idempotency key. A local idempotency key prevents duplicate local jobs but cannot alone prevent duplicate remote creates. For Documentolog unknown-outcome writes, reconcile with a confirmed remote lookup/manual provider dashboard before resending.

## 6. Status freshness and reconciliation

- Persist `last_success_at`, `last_attempt_at`, `last_error_code`, run counts, and freshness state by provider/resource.
- Mark employee records or leave balances stale when configurable freshness threshold is exceeded; do not silently display as current.
- Reconcile local external references against the provider when a confirmed query/exports API exists. Do not build a fake polling endpoint because it's convenient.
- Orphan external records and unmatched callbacks must enter an operator queue, not be attached using employee name or guesswork.
- For Documentolog signed file artifacts, persist received links and download metadata safely; download only from allowlisted hosts with required Bearer token; enforce per-request authorization.

## 7. Error catalogue

| Code | Typical cause | Automatic retry? | Recovery |
|---|---|---|---|
| `AUTH_FAILED` | Invalid/expired credentials or access denied | No until credentials/permissions fixed | Admin fixes secret/role; run connectivity test |
| `RATE_LIMITED` | Provider throttling | Yes, honoring `Retry-After` | Backoff; adjust concurrency if persistent |
| `TIMEOUT` | Read request timeout | Usually yes for reads | Bounded backoff |
| `UNKNOWN_OUTCOME` | Write timed out after possible remote acceptance | No blind retry | Reconcile by external lookup or manual check |
| `VALIDATION_FAILED` | Required field/payload invalid | No | Correct mapping/business data; audited retry |
| `NOT_FOUND` | External ID absent | Usually no | Review mapping or upstream record |
| `CONFLICT` | Duplicate/state/version conflict | Depends on contract | Read current state; reconcile |
| `PROVIDER_UNAVAILABLE` | Network/5xx outage | Yes within budget for safe operations | Backoff and alert if threshold exceeded |
| `WEBHOOK_UNVERIFIED` | Caller authenticity cannot be established | No processing | Reject/quarantine; verify provider contract |
| `MAPPING_AMBIGUOUS` | Cannot uniquely map employee/department/document | No | HR/admin resolves mapping |
| `CAPABILITY_NOT_CONFIGURED` | Required live operation not verified/enabled | No | Complete integration discovery/gates |

## 8. Operator runbook

### Provider unavailable

1. Confirm provider health/network/VPN and certificate chain.
2. Check error code counts and oldest pending job age.
3. Do not switch a live connection silently to mock.
4. Let only safe reads/known-idempotent jobs retry.
5. Communicate visible degraded state to users; preserve their request and approvals.

### Documentolog submission unknown

1. Freeze automatic retry for that job.
2. Search using known external ID if response yielded one; otherwise search Documentolog Business UI using timestamp, sender, recipient, and artifact digest/title according to approved operator procedure.
3. If document exists, attach its confirmed ID and continue workflow.
4. If provider/operator confirms no document was created, record who confirmed it and requeue once with audited action.
5. If outcome cannot be established, keep `SUBMISSION_UNKNOWN` and escalate; never send a second document just to make the error disappear.

### Employee mapping mismatch

1. Stop updating the target internal employee from the ambiguous provider record.
2. Place record in quarantine with minimal safe metadata.
3. HR admin confirms the stable identity.
4. Create/update mapping in an audited operation, then replay the import for that record.

### Bad webhook / repeated webhook

1. If authentication fails, reject and record only safe metadata/digest.
2. If authentic but duplicate, acknowledge safely without repeating side effects.
3. If authentic but out of order, append event and recompute status from event history/transition rules.
4. Alert on repeated invalid callers or unexpected provider schema changes.

## 9. Metrics and alerts

At minimum track:

- sync duration, imported count, quarantined count, last-success age;
- pending job count and oldest-job age by provider/operation;
- attempts per job, dead-letter count, unknown-outcome count;
- webhook accepted/rejected/duplicate counts and processing lag;
- provider latency/error rate by normalized code;
- leave data stale count;
- requests blocked because live capability/configuration is disabled.

Do not put PII or full external payloads in metric labels.

## Current implementation and gaps from QA report (2026-10-17)

### Existing and tested

The app has a transactional outbox, signed app-to-gateway requests, durable gateway jobs/leases, bounded jittered retries, durable nonce replay protection, persistent callback retries and reconciliation when a callback is lost. Repeated document requests with the same stable key create one mock document, and terminal callback processing is idempotent. Approval is separate from registration, and failure to register does not undo manager approval.

Profile sync imports signed MOCK employee-code snapshots, preserves last-known data through outage, records source/as-of freshness, and exposes unknown mappings/balance conflicts for HR review.

### Known operational gaps

- HR can inspect some failures/mappings but cannot yet execute audited safe replay/remapping.
- Independent application worker-process concurrency was not exercised in the QA report.
- Gateway runtime has initial `create_all` schema initialization; versioned gateway upgrades remain necessary.
- Initial advance-request creation still lacks client submission idempotency, even though downstream document operations are idempotent.
- Production 1C/Documentolog connectivity, mTLS, backups/restores, and capacity are unverified.

Use `12_QA_REMEDIATION_PLAN.md` for the ordered fix plan. Never blindly reset a DEAD job. Reconcile by current persisted gateway job/reference first, preserve the original idempotency key/payload, authorize the HR action, and record an audit event.
