# 09 — Testing Plan and Evidence Requirements

## Existing verified baseline from QA report (17 Oct 2026)

- 400 tests passed on SQLite + 1 warning.
- Same 400 tests passed on PostgreSQL 17 + 1 warning.
- 5 frontend localization tests passed; JavaScript syntax, Ruff check/format, mypy across 76 app sources and pip dependency consistency passed.
- OSV scanned 50 pinned runtime/dev/optional-ML packages and found 0 advisory matches in the scanned set.
- Docker build/start and a gateway-down/recovery journey passed in the reported isolated test stack.
- All 16 required acceptance scenarios had executed evidence.

These are historical QA results, not a claim that a new checkout/current image passes. Re-run and record current outputs.

## Existing tested integration properties

1. Approval and outbox insertion share a DB transaction.
2. Transaction failure leaves request Pending and does not partially change balance/history/notifications/outbox.
3. External work is dispatched outside the approval transaction.
4. Gateway is authenticated independently from employee bearer roles.
5. HMAC uses method/path-query/timestamp/nonce/body digest; tampered, stale, wrong-key and replayed requests are rejected.
6. Gateway jobs are persistent, idempotent by key, have durable leases/retries, and survive restart scenarios covered by tests.
7. Same idempotency key cannot create multiple mock documents; changed body under same key is rejected.
8. Lost callbacks can be recovered by status reconciliation.
9. Terminal result application validates matching approved request/job/key and does not duplicate audit/history/notification effects.
10. Mock employee-code sync preserves existing profile accounts, source/as-of freshness metadata and last-known snapshot across gateway outage.
11. HR refresh is role-controlled/rate-limited in the tested paths; unmatched mapping is visible for review.
12. App role/object authorization matrix tests every exported OpenAPI operation for anonymous/invalid session and admin role restrictions; this is not a full pentest/browser test.
13. AI source citations/fallbacks work for tested cases; two P1 regressions for numeric policy conflicts and raw question egress were fixed in saved source.

Relevant tests noted in QA report include `tests/test_api_matrix.py`, `tests/test_e2e_journey.py`, `tests/test_gateway_service.py`, `tests/test_integration_gateway.py`, `tests/test_qa_acceptance.py`, `tests/test_reliability.py`, `tests/test_migrations.py`, `tests/test_ai_gemini.py`, `tests/test_merge_regressions.py`, and `tests/frontend_localization.test.cjs`.

## Regression tests required for known findings

### F05 — Initial request idempotency (FAIL)

- Repeat identical advance request sequentially.
- Repeat identical request concurrently from two clients.
- Reuse key with a changed payload.
- Reuse the same key as a different employee.
- Force transaction rollback and retry same key.
- Verify exactly one request, one applicable balance effect, one history/audit/notification set and no duplicate outbox job.

### F04 — HR replay/remapping (PARTIAL)

- Non-HR cannot replay or remap.
- HR mapping decision requires stable key and records before/after mapping in audit.
- Ambiguous external ID is quarantined; no name-only match.
- Replay reconciles an already-registered gateway job and does not create a second document.
- Immutable idempotency key/payload is preserved.
- Audit/database failure prevents partial replay/remap.

### F08/F10 — database and migration lifecycle

- Direct SQL cannot persist negative leave balance, end-before-start request dates or unknown request status after migration.
- Migration preflight reports old invalid rows without silently changing them.
- Gateway schema migration works from empty DB and old persisted mock-job DB.
- Job/nonce/document state survives upgrade and restart.

### F06 — Modal keyboard focus

- Open dialog, Tab through all focusable controls, focus never enters background.
- Shift+Tab wraps to last element.
- Escape closes only where expected.
- Focus returns to opener.
- Background controls are inert while open.

### F07 — Smoke repeatability

- Run smoke scenario twice back-to-back and both pass.
- Test creates or reuses only its synthetic data.
- It refuses unsafe unknown/prod DB target.
- Cleanup cannot delete unrelated user data.

### F03/F09 — AI governance and conflict handling

- Raw questions/private identifiers absent from actual mocked provider HTTP request body.
- External provider cannot be called by default.
- Approved KB content containing private material is not sent until governance rule allows it.
- Literal numeric conflict falls back safely in EN/RU/KK.
- Paraphrased/non-numeric conflict, stale source and conflicting effective dates produce conservative fallback until precedence resolves them.
- Malicious instructions embedded in approved source do not override security or source-grounding constraints.
- Provider timeout/outage keeps safe local/extractive behavior.

### Ops/browser confidence

- Two independent app outbox worker processes claim work safely against PostgreSQL.
- Gateway stopped/restarted; pending work resumes without duplicate registration.
- Callback lost/delayed/duplicated/out of order is recovered safely.
- Backup and restore restores app + gateway records and outstanding jobs.
- Login throttling remains effective across multiple processes or is documented as a limitation.
- Mobile viewport and browser accessibility checks are explicitly recorded.

## Commands

Inspect `pyproject.toml` and current CI/config for exact flags. The QA report lists these basic forms:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pip check
node --check static/js/app.js
node --test tests/frontend_localization.test.cjs
```

For migration tests and any command that alters a DB, use a dedicated disposable DB and explicit settings. Do not run against an unknown database. No live vendor credentials or live network are permitted for the normal test suite.

## Evidence format

For every new QA finding, record: ID, environment/DB type, revision, exact command or reproducible action, exit/result, test artifact, and limitation. Separate code-source verification, mocked contract tests, vendor sandbox tests and production evidence. Do not label these as interchangeable.
