# 00 — JanaМен Current Project State (QA baseline: 17 October 2026)

> Repository update, 18 October 2026: this pack contains the historical QA baseline. The existing fix-plan work and integration with the latest main branch are recorded in [13_REPOSITORY_INTEGRATION_STATUS.md](13_REPOSITORY_INTEGRATION_STATUS.md). Read that status before treating the tasks below as unimplemented.

## Why this document exists

This document is the source-of-truth summary of the supplied `17-10_16-05.pdf` QA report. It describes the **existing project**, not a hypothetical greenfield implementation. The coding agent must inspect current repository source to confirm each item before editing, but must not rebuild working components just because another integration specification proposes a different shape.

**Read the full source report:** [`reference/qa_report_2026-10-17.pdf`](reference/qa_report_2026-10-17.pdf).

## Readiness snapshot

**Overall status: NEEDS WORK — not production ready.** QA assessed 162 checklist requirements:

| Status | Count |
|---|---:|
| PASS | 140 |
| FAIL | 2 |
| PARTIAL | 17 |
| NOT VERIFIED | 2 |
| BLOCKED | 0 |
| NOT APPLICABLE | 1 |

These are checklist statuses, not the separate severity labels used for findings. All 16 required acceptance scenarios had executed test evidence in the report.

### Verified test/build evidence in the report

- SQLite: **400 passed, 1 warning**.
- PostgreSQL 17: **400 passed, 1 warning** using the same test set; migrations and API end-to-end tests were included.
- Frontend locale tests: 5 passed. JavaScript syntax checks, Ruff check/format, mypy over 76 application sources, and dependency consistency checks passed.
- OSV checked 50 pinned runtime/development/optional-ML packages and returned 0 advisory matches for the scanned set.
- Docker build/start and gateway-down/recovery journey passed. Four services ran; three exposed configured healthy probes. The gateway had no host port and was internal to the Compose network.
- Browser inspection covered employee pages, manager Team view and HR integration card/source/refresh controls. Course progress survived process rebuild and HTTP re-login.
- Keyboard modal focus failure was reproduced. Mobile and exhaustive browser coverage remain unverified.

The test counts are a **historical baseline from the QA report**, not a guarantee that a later checkout, configuration, database, deployment, or current run has the same state. Re-run the applicable checks before reporting completion.

## Existing repository map

| Area | Actual path(s) | Current behavior reported |
|---|---|---|
| Backend/API | `app/main.py`, `app/routers/`, `app/schemas/`, `app/services/` | FastAPI backend; app owns domain operations and serves the frontend. |
| Frontend | `static/index.html`, `static/js/app.js`, `static/js/i18n.js`, `static/css/style.css`, `static/locales/catalog.json` | Plain HTML/CSS/JavaScript served by FastAPI; no package.json, frontend bundler, or frontend build command. UI languages RU/KK; backend AI language handling EN/RU/KK. |
| Database | `app/database.py`, `app/models/`, `app/migrate.py`, `migrations/versions/0001..0006` | PostgreSQL 17 in Compose and SQLite support. App schema migrations are versioned. Select the target database explicitly before running migrations. |
| Auth/session | `app/services/auth_service.py`, `app/routers/auth.py`, `app/models/session.py` | Revocable database-backed bearer sessions, server-side database role authority, active-user checks, password hashing and legacy-password upgrade. |
| Request workflow | `app/services/request_service.py`, request schemas/models | Request and manager workflow; transaction includes business state, balance-related effects, event history, notification, audit and integration outbox where applicable. |
| Notification/audit | `app/services/notification_service.py`, `app/services/audit_service.py` | Persistent in-app notifications and audit events; email/push delivery is not implemented. |
| App-side integration | `app/integrations/outbox.py`, `app/integrations/profile_sync.py`, `app/integrations/signing.py` | Durable delivery, retry state, HMAC-signed internal requests, callback application, and import of employee-code snapshots. |
| Internal gateway | `app/gateway/main.py`, `app/gateway/runtime.py`, `app/gateway/connectors.py`, `app/gateway/models.py` | Separate internal FastAPI gateway; signed machine authentication with durable nonce/replay protection; persistent async jobs and leases; explicit mock connector. Not a live Documentolog connection. |
| AI/knowledge | `app/services/ai_service.py`, `app/services/knowledge_conflicts.py`, `app/integrations/gemini.py`, `knowledge/`, `ml/` | Offline lexical/TF-IDF retrieval with optional learned reranking; optional approved-source-only Gemini quote selection with explicit default-off operator approval. Not a general unrestricted model assistant. |
| Tests/tooling | `pyproject.toml`, `tests/`, `dependency_audit.py` | Pytest, Ruff, mypy, dependency checks. No tracked CI workflow was found. |
| Deployment | `Dockerfile`, `docker-compose.yml`, `.env.example`, `docs/INTEGRATIONS.md` | Mock profile, internal gateway network and optional URL switches. Generated private config was outside the repo with mode 0600 in the QA setup. |

## Existing Documentolog/mock flow (do not rebuild)

1. A manager approval is applied by `app/services/request_service.py:review_request` within a database transaction.
2. An immutable canonical outbox snapshot and stable `request:v1` idempotency key are inserted before the approval transaction commits.
3. `app/integrations/outbox.py` claims due rows (PostgreSQL `FOR UPDATE SKIP LOCKED`), dispatches a signed request, validates acknowledgements, retries within bounds and records terminal failures.
4. App-to-gateway authentication uses the existing `X-Key-Id`, `X-Timestamp`, `X-Nonce`, and `X-Signature` signing helper. Signing binds the method, path/query and raw body digest.
5. `POST /v1/documents` on the internal gateway persists a unique idempotent job and returns `202`; registration is asynchronous.
6. The mock connector creates a unique persisted mock document with a deterministic `MOCK-DOC` reference for the same persisted logical job. It can simulate temporary failure and validation rejection.
7. The gateway persists callbacks with retry; callbacks are signed and use a fresh nonce.
8. The app-side receiver validates signature, body, nonce/replay protection and canonical terminal results. `apply_result` checks the approved request/job/key and applies the terminal result idempotently.
9. Approval remains `Approved` if external registration fails. UI integration status is separate from business approval and can show `NOT_REQUIRED`, `PENDING`, `SENT`, `REGISTERED`, `FAILED`, or `DEAD` as applicable.
10. HR profile sync consumes signed **MOCK** employee-code snapshots, updates existing profiles only, records source/as-of/sync metadata, and sends unknown mapping or balance conflicts to HR review. It does not call live 1C:ZUP.

Relevant source files include `app/integrations/outbox.py`, `app/integrations/profile_sync.py`, `app/integrations/signing.py`, `app/routers/internal.py`, `app/gateway/main.py`, `app/gateway/runtime.py`, and `app/gateway/connectors.py`.

## Implemented and fixed in the saved source

Two P1 cases were reproduced and fixed in the reviewed source:

- Literal numeric conflicts between approved policy claims were labelled as grounded. A conservative numeric conflict guard now causes the relevant cases to fall back safely. General semantic conflict detection is still incomplete.
- Raw employee free-text questions, including synthetic identifiers, reached the mocked Gemini HTTP request. Raw question transport was removed; only approved-source quote-selection data can cross the provider boundary, and provider use requires explicit operator approval which defaults off.

**Important runtime caveat:** the QA report says the patched review stack ran at `http://127.0.0.1:18766`; the pre-existing stack on port 8000 was not rebuilt and retains its earlier image until explicitly updated by an operator. This is historical environment information. Do not assume a running service contains the reviewed source without rebuilding/restarting it through the approved deployment procedure.

## Remaining findings to fix or close

The report labels these issues at P2/P3 severity; priorities below are implementation order recommendations, not new test results.

| Finding | Status in report | Required direction |
|---|---|---|
| External data governance, live connector/TLS and AI-source approval | PARTIAL (P2) | Keep live integrations and external model egress disabled until data-sharing, residency/retention, vendor, mTLS and organizational approvals are verified. Approved knowledge can itself contain private material. |
| HR mapping and dead-job recovery | PARTIAL (P2) | Add authorized, audited mapping resolution and safe replay. Preserve idempotency keys; reconcile gateway state before replaying. |
| Initial advance request submission duplicates | FAIL (P2) | Add employee-scoped client submission idempotency; same key/same normalized body reuses the original request, same key/different body conflicts; handle concurrent repeats. |
| Request dialog keyboard focus | FAIL (P2) | Trap focus in the active dialog, make background inert while open, restore focus to opener; test Tab, Shift+Tab and Escape. |
| Smoke test repeatability | FAIL (P2) | Replace fixed collision-prone dates with isolated disposable fixtures or stable synthetic scenarios; never silently delete user data. |
| Database domain constraints | PARTIAL (P2) | Add guarded, versioned constraints for negative balances, reversed dates and valid status values after preflight detection; do not silently mutate existing rows. |
| Broader AI policy conflict/hostile-source handling | PARTIAL (P2) | Add approved policy precedence/version/effective-date metadata and adversarial fixtures; fall back when conflicting claims cannot be reconciled. |
| CI and production-like operations | PARTIAL (P2) | Add CI; exercise independent worker processes, gateway schema migrations, login throttling under multiple processes, backups/restores, and capacity/recovery. |
| UI language/provenance | PARTIAL (P3) | Translate integration messages, complete locale states, explicitly mark sample course/content provenance, and agree on login/session restoration behavior. |

One reported gap is particularly important for integrations: the gateway initializes its schema using an initial `create_all` path. The app has migrations `0001..0006`, but gateway schema changes need a deliberate versioned upgrade mechanism. Do not assume app migrations automatically migrate gateway tables.

## Local commands from the report

Use only on an explicitly selected development or disposable database and confirm settings before executing:

```bash
# App entry point (report command; database must be migrated first)
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# App-side outbox worker
.venv/bin/python -m app.integrations.outbox

# Gateway entry point; use the repository's configured host/port and mock settings
.venv/bin/python -m uvicorn app.gateway.main:app

# Frontend syntax / locale tests
node --check static/js/app.js
node --test tests/frontend_localization.test.cjs

# Python checks (inspect pyproject.toml for exact configured aliases/options)
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pip check
```

Migration command reported: `.venv/bin/python -m app.migrate`. Before running it, explicitly inspect `DATABASE_URL`/application settings and ensure the destination is development/disposable. Do not run migrations on an unknown or production database. The QA report refers to companion files `QA_TEST_RESULTS.md`, `QA_CHECKLIST.md`, and `FIX_PLAN.md`; they were not separate user-provided attachments in this conversation. The full checklist summary is embedded in the supplied PDF.

## Live capability status

| Capability | Status based on supplied report |
|---|---|
| Employee/manager/HR self-service application | Implemented and extensively tested locally, with the listed UX gaps. |
| Request manager approval and audit/event trail | Implemented and tested. |
| Durable app outbox and internal signed gateway | Implemented and tested in mock environment. |
| Mock Documentolog registration | Implemented and tested. |
| Real Documentolog API/signing connection | NOT VERIFIED / not implemented as a live connection. |
| HR snapshot import | Implemented for signed mock snapshots. |
| Real 1C:ZUP connectivity | NOT VERIFIED / not implemented as a live connection. |
| Official payroll payment or 1C leave write-back | Not implemented; must not be claimed. |
| Gemini live provider usage | No live provider was called in the reported QA run; approved-source-only provider path exists but requires explicit approval and separate verification. |

## Rule for the coding agent

Inspect current code first, compare with this baseline, preserve working behavior, fix the prioritized gaps with regression tests, and update this file when evidence changes. Never report an item as fixed based only on changing documentation.
