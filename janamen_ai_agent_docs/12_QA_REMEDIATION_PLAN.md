# 12 — QA Remediation Plan, Ordered by Risk

> Repository update, 18 October 2026: this pack contains the historical QA baseline. The existing fix-plan work and integration with the latest main branch are recorded in [13_REPOSITORY_INTEGRATION_STATUS.md](13_REPOSITORY_INTEGRATION_STATUS.md). Read that status before treating the tasks below as unimplemented.

This backlog is grounded in the 17 October 2026 QA report included in `reference/qa_report_2026-10-17.pdf`. It is a plan, not evidence that work is already complete.

## Stage 0 — Safe baseline and change control

- [ ] Inspect current source and `git status`; preserve unrelated user changes.
- [ ] Confirm which source revision corresponds to the report. QA's patched service on port 18766 and the pre-existing port 8000 container were not the same built image.
- [ ] Re-run focused baseline tests on a disposable DB and record current results before edits.
- [ ] Keep all external connectors in MOCK/offline mode; no live 1C, Documentolog or Gemini call during test runs.
- [ ] Read existing `docs/INTEGRATIONS.md`, `app/config.py`, `docker-compose.yml`, migrations, and `.env.example` before changing configuration.

**Exit evidence:** repository revision, clean/understood worktree, selected disposable DB, baseline commands and outcomes recorded.

## Stage 1 — Close duplicate initial submissions (P2 / FAIL)

Current evidence: identical advance request HTTP payload was submitted twice and yielded two separate `201` responses and request records. Downstream integration idempotency does not protect initial business request creation.

- [ ] Add a client-generated submission key to the request creation contract. Use the existing app conventions if present; do not invent an incompatible duplicate API.
- [ ] Persist the key scoped to authenticated employee and operation; enforce uniqueness at database level.
- [ ] Persist a canonical/normalized request-body digest. Same employee + key + same normalized body returns the original request; same key + different body returns a stable `409`.
- [ ] Reuse the exact same key on browser/network retries; do not mint a new key in a generic retry handler.
- [ ] Cover sequential duplicate, changed payload, concurrent duplicate, another employee using the same key, and transaction rollback.
- [ ] Ensure no duplicate balance debit, notification, history event, audit event, or outbox job.

**Exit evidence:** tests reproduce the old failure before the patch and pass after the patch; database-level uniqueness protects concurrent requests.

## Stage 2 — Safe HR recovery / mapping resolution (P2 / PARTIAL)

Current evidence: HR can inspect failed/dead integration jobs and unknown profile mappings, but authorized replay/remapping does not exist.

- [ ] Design explicit HR-only action endpoints/services using existing admin router and authorization patterns.
- [ ] Resolve unmatched employee records using stable employee codes/external IDs only. No name-only auto-match.
- [ ] Record old mapping, proposed mapping, decision actor, timestamp, reason and source record version in immutable audit history.
- [ ] For DEAD/retry actions, inspect/reconcile gateway job state first. Preserve the original immutable idempotency key and canonical payload. Never create a second remote document just to clear a DEAD marker.
- [ ] `UNKNOWN_OUTCOME` (if/where applicable) must enter lookup/reconciliation/manual review—not blind replay.
- [ ] Require confirmation for any remapping that changes who owns a request or employee snapshot.
- [ ] Add tests for non-HR denial, stale/mismatched job key, already registered document, duplicate replay, ambiguous mapping and audit persistence.

**Exit evidence:** controlled HR recovery demo and adversarial authorization tests.

## Stage 3 — Database invariants and versioned gateway schema (P2 / PARTIAL)

- [ ] Preflight existing persisted data for negative leave balances, reversed dates and unknown request status values.
- [ ] Produce a report of conflicts before migration. Do not silently clean/change existing business rows.
- [ ] Add additive database constraints or enum/validated status constraints with explicit migration and rollback plan.
- [ ] Test constraints against direct SQL writes, not only Pydantic/API paths.
- [ ] Replace gateway's unversioned/initial `create_all`-only schema evolution with a versioned migration strategy compatible with current deployment. Preserve existing job/nonce/document rows.
- [ ] Test upgrade from an existing database as well as fresh initialization; test restart and downgrade/rollback strategy where feasible.

**Exit evidence:** migration tests pass on fresh and existing disposable database snapshots; direct invalid writes are rejected.

## Stage 4 — Accessibility and smoke reliability (P2 / FAIL)

### Dialog focus
- [ ] Trap focus in the top-most open dialog.
- [ ] Make background content inert/unreachable to keyboard interaction while the dialog is open.
- [ ] Restore focus to the element that opened the dialog after close.
- [ ] Verify Tab, Shift+Tab, Escape and nested/stacked modal behavior using keyboard-only testing.
- [ ] Add an automated browser regression test if the current test environment supports one; otherwise document reproducible manual evidence.

### Repeatable smoke test
- [ ] Stop using fixed vacation dates that cause the second run to collide with a previous request.
- [ ] Prefer a per-run unique disposable fixture or a known synthetic idempotent scenario.
- [ ] Keep cleanup scoped to records created by that test only; do not delete user data.
- [ ] Ensure smoke tests are explicit about environment and refuse to operate on an unknown/prod DB.
- [ ] Run the smoke twice back-to-back and record both results.

**Exit evidence:** focus regression no longer reproduces, and two consecutive isolated smoke runs pass.

## Stage 5 — AI data governance and safer conflict handling (P2 / PARTIAL)

- [ ] Preserve the two already-fixed P1 regressions: numeric conflict fall-back, and no raw user question sent to Gemini HTTP.
- [ ] Add regression tests at the actual provider HTTP boundary; do not rely only on service-level mocks.
- [ ] Keep provider use default-off and approved-source-only until the organization approves data sharing, retention, residency, and source curation.
- [ ] Audit approved knowledge for PII/private source content; raw user questions staying local does not make private retrieved documents safe to transmit.
- [ ] Add HR-controlled policy precedence, version/effective date/source authority metadata.
- [ ] Test paraphrased/non-numeric conflict, contradictory policy sources, stale policy, malicious instructions embedded in approved documents, language mismatch, missing source, and provider outage.
- [ ] When conflict/authority cannot be resolved, return a safe source-based fallback or ask HR; do not invent policy.

**Exit evidence:** documented governance approval plus adversarial regression suite; no claim of complete semantic contradiction solving.

## Stage 6 — CI and production-like operational assurance (P2 / PARTIAL)

- [ ] Add CI for Python tests, Ruff, format check, mypy, dependency consistency, frontend syntax/localization, migration tests and secret checks.
- [ ] Run two independent app outbox worker processes against PostgreSQL; verify no duplicate delivery/effect under races and restarts.
- [ ] Test distributed login rate limiting across workers or document why the deployment architecture provides equivalent protection.
- [ ] Add backup/restore drill for app and gateway state, including outbox, job leases, nonces, idempotency keys, and external references.
- [ ] Add health/readiness checks and an ops runbook for stopped gateway, unavailable database, expired signing key, failed callback and stuck job.
- [ ] Test gateway and app schema upgrades using persisted test data.
- [ ] Complete mobile viewport and browser/accessibility smoke coverage.
- [ ] Do not claim capacity/HA readiness without a documented target and load test.

**Exit evidence:** tracked CI configuration, repeatable operational drills, evidence artifacts and explicit remaining limitations.

## Stage 7 — UI localization and content provenance (P3 / PARTIAL)

- [ ] Translate newly shown integration notices and states for supported UI locales.
- [ ] Ensure every visible status has localized success/pending/error/unavailable copy.
- [ ] Add explicit sample/demo provenance at the course/content item level, not only a global footer.
- [ ] Confirm intended behavior after page reload: session persistence vs sign-in-required behavior. Do not persist bearer secrets in an unsafe storage area just to preserve navigation.
- [ ] Verify localized errors do not leak raw provider payloads or sensitive data.

## Stage 8 — Live vendor gates (BLOCK until separately approved)

### 1C:ZUP
- [ ] Confirm exact version, configuration, deployment, network route and test infobase.
- [ ] Obtain customer-approved metadata/API contract and least-privilege read credentials.
- [ ] Validate employee key, manager/department semantics, status values and authoritative leave calculation with HR/1C owner.
- [ ] Implement actual read adapter only after the contract is verified.
- [ ] Keep official 1C writes disabled until transaction/posting semantics, duplicate protection, cancellation and legal/business approval are agreed.

### Documentolog
- [ ] Obtain vendor/account API contract, sandbox, auth details, response/webhook schema, and documented status lookup path.
- [ ] Confirm create/send and sender-signature behavior before enabling any real submit.
- [ ] Determine how authenticated callback authenticity is verified. The current HMAC protects JanaМен-to-internal-gateway traffic; it does **not automatically authenticate vendor-originated events**.
- [ ] Verify TLS, outbound host allowlist, production inbound mTLS/proxy, secret rotation and data retention.
- [ ] Run a non-sensitive sandbox contract test, failure injection, lost-response reconciliation and duplicate/out-of-order callback tests.
- [ ] Obtain signoff from product/HR/security/legal owners before flipping any live send flag.

**Exit evidence:** owner approvals, successful customer-specific sandbox contract tests, tested rollback/disable switch, operational runbook, no unverified capability exposed as live.

## Definition of done for this remediation pack

A finding is only closed when there is code (if applicable), an automated or reproducible test, a recorded result, and documentation matching runtime behavior. Updating this checklist alone does not close a finding.
