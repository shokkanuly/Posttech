# JanaМен MOCK integration implementation

The application owns authenticated HR requests, approvals, history, audit, notifications and immutable integration outbox events. A separate worker sends signed canonical requests to the private gateway. The gateway persists jobs, mock documents, nonces and callback state. Signed callbacks and reconciliation apply terminal results atomically. Business approval remains independent from registration status; employee snapshots remain available from local storage during outages.

## Current behavior

- Employee-scoped, body-bound submission keys prevent duplicate logical requests. Browser retries reuse the key; callers without a key retain the create contract.
- HR-only recovery queues audited, version-checked intent. The worker reconciles before retry, retains the original payload/key, rejects superseded generations and refuses blind replay of a known accepted job missing from gateway storage.
- HR-only mapping resolution uses fresh signed employee-code snapshots and existing accounts, with stale-command checks and audit. It never matches by name or creates an account.
- Signed business requests and signed `GET /health` have independent durable per-key UTC-minute quotas. Both retain signature, timestamp, nonce and body-size checks. Health probes cannot consume business capacity.
- Synthetic demo configuration generates private credentials and a unique Compose project without overwriting existing files. The repeatable registration and outage command checks stable submission identity, one debit and one registration notice.

Core migration head: **`0011_merge_profile_updates`**. Gateway schema: **v3**. Health quota separation reuses the existing quota table, preserves business hashes/counts and requires no new migration. Back up stores before deployment and retain idempotency/nonce history.

## Verification records

Exact commands/exits, database targets, test counts, selected ports, observed request/reference IDs, availability observations and review details belong to the corresponding session:

- [Initial implementation session](evidence/integration-2026-10-18/implementation-report.md) and [initial acceptance matrix](evidence/integration-2026-10-18/acceptance-results.md).
- [Five-check precommit verification](evidence/integration-precommit-2026-10-18/REVIEW.md).

[Acceptance records](INTEGRATION_ACCEPTANCE_RESULTS.md) distinguish executed MOCK assertions from remaining gates. [The demo runbook](INTEGRATION_DEMO_RUNBOOK.md) contains reusable startup, repeat and outage/recovery instructions. A recorded available deployment is a historical observation, not a promise that it is still running.

## Remaining gates

Real 1C/Documentolog adapters require approved sandbox contracts, credentials, exact field/leave/signature semantics and network/TLS requirements. Production TLS/mTLS, key operations, shared login throttling, monitoring/HA/load, data governance and restore objectives remain unverified. Both connectors remain MOCK. CI is an inactive template pending authorized workflow publication; no Actions execution is implied. Browser/mobile revalidation remains separate from API and database tests.
