# Backend upgrade and API verification

Latest follow-up: [RU/KK localization and three role demo accounts](LOCALIZATION_AND_DEMO.md), including the current **266 backend + 5 frontend tests**. The 244-test results below describe this earlier backend pass.

Completed 16 October 2026. The existing FastAPI / SQLAlchemy / SQLite modular monolith and HTML/CSS/JavaScript frontend were retained. This pass started from the previously implemented MVP with 81 passing tests. Existing Git changes were preserved; no commit, deployment, destructive database operation, or paid service was performed.

## Result

- **244 tests passed in 75.54 seconds**, with one upstream TestClient deprecation warning.
- All **35 paths / 38 documented HTTP operations** have an actual authorized success case. Every protected operation is tested anonymously and with revoked, malformed, and deactivated sessions. Administrative operations additionally reject employee and manager access.
- Ruff lint/format, mypy including untyped function bodies, JavaScript syntax checks, dependency compatibility, and whitespace checks passed.
- OSV matched advisories in three original runtime pins. Updated AnyIO **4.13.0 → 4.14.2**, IDNA **3.11 → 3.15**, Starlette **1.0.0 → 1.3.1**. A subsequent OSV query checked **41 runtime/development pins with zero advisory matches**. This is an advisory check, not proof that every vulnerability or exploit path has been eliminated.
- Migration rehearsal on a backup copy preserved **5 users, 6 requests, 2 documents and 6 source chunks**, with zero foreign-key violations and zero model/schema differences. The original `.env` and `janamen.db` checksums remained unchanged.
- All ten live API smoke steps passed against an isolated demo server. Browser verification passed for HR sign-in, paginated management, creating/reviewing/approving a source, grounded chat, opening the cited revision, and logout. Final browser console inspection found no errors or warnings.

## Fixes and safeguards

| Area / files | Change and evidence |
|---|---|
| `app/schemas/common.py`, ID fields in routers/JSON schemas | IDs are bounded to positive signed 64-bit values before SQL execution; JSON IDs must be actual integers. New regression tests first reproduced 500 / OverflowError on 11 oversized-ID operations, then passed with 422. |
| `app/schemas/knowledge.py` | Approval/activity/synthetic flags use strict JSON booleans. The previous API accepted strings and integers as approval flags; regression tests reproduced 200 responses and now require 422. |
| `app/services/knowledge_service.py`, knowledge model, migration `0003_knowledge_revisions` | Monotonic document revision; all source/approval writes serialize through the parent row. Approval requires the revision HR reviewed. Stale concurrent edits return 409 without changing approval/content; injected audit failure rolls back content, approval and revision. |
| AI service/schemas/source route | Citations carry `document_revision`; fetching a stale revision after reapproval returns 409. Approved/active/role filtering remains mandatory. Source text and document metadata load together; audit stores revision/content hash, without raw questions or source text. Retrieval streams rows and retains only the best two matches. Historical source text is not archived. |
| `app/services/auth_service.py`, auth route | Limiter reservations count concurrent in-flight attempts as well as recent failures. A pre-fix unit test demonstrated the sixth simultaneous attempt bypassing the five-attempt limit. Reservations release on success and error. Explicit zero token lifetime now expires immediately instead of selecting the default TTL. |
| `app/middleware.py`, config, errors/main | Bodies are bounded before JSON parsing, including streams without Content-Length. Default 256 KiB; over-limit returns 413, malformed Content-Length returns 400. Unexpected 500 responses receive no-store/nosniff/request-ID headers and redact exception contents. Outdated-schema readiness returns 503. |
| `app/pagination.py`, collection routers/services | Nine collections use bounded limit/offset and deterministic ordering. Array response shapes remain compatible. The frontend follows pages, and refuses to combine results across changed sessions. |
| Academy/request/dashboard services | Batched course/enrollment/lesson loading, SQL aggregates for learning/counts, SQL joins for manager scope, eager request/profile/reviewer loading. Catalog regression check performs at most three SELECTs rather than a query for each course/lesson group. |
| Request service | Missing, inactive or incorrectly assigned managers no longer receive request notices. Active HR administrators receive the fallback notice; the requester sees the actual destination. Without another authorized reviewer, the request stays pending with explicit contact-HR guidance. Approval scope and no-self-review rules remain in force. |
| `static/js/app.js` | Existing pages/layout retained. Approval submits the source revision loaded for review, including when documents and chunks arrive in separate page requests. Source links request the cited revision. Collection consumers load subsequent pages. |
| Requirements, `dependency_audit.py` | Patched dependency pins; repeatable OSV check with nonzero exit on findings or incomplete checks. Only public package names/versions are transmitted. |
| Tests, OpenAPI and documentation | Added endpoint matrix, malformed-input/body limits, stale/concurrent knowledge writes, rollback, citation changes, pagination, limiter concurrency, readiness, migration preservation and bounded query tests. Corrected README claims about official 1C data, automatic role login, integration connections, OS testing, localization and audit immutability. |

The original request/status/balance concurrency, history, notification ownership, persistent enrollment/progress, JWT role forgery, private-record scope, AI fallback and end-to-end tests remain in the passing suite. No frontend framework or backend service replacement was introduced.

## Architecture and schema

Validated routes → domain services → SQLAlchemy 2 models → SQLite, within one process. Authentication validates JWT signature/claims, persisted non-revoked session, session expiry and active user. Every request derives role from the current database user. Managers see direct reports; HR has organization scope; employees see their own private records.

The 13 existing tables remain: users, sessions, profiles, requests/events, courses/lessons/enrollments/progress, notifications, knowledge documents/chunks and audit. The additive migration introduces `knowledge_documents.revision INTEGER NOT NULL DEFAULT 1`; approved existing sources retain their state and text. Approval/content changes increment it transactionally. [Full schema and architecture](../ARCHITECTURE.md).

## API contract and examples

[Every endpoint and access rule](ENDPOINTS.md), [request/response contract](API_CONTRACT.md), and [generated OpenAPI](openapi.json). The exported OpenAPI is tested against the application so schema drift fails the suite.

```http
GET /api/v1/requests?limit=25&offset=0&status=Pending
Authorization: Bearer <employee-token>
```

Returns an array scoped to the authenticated employee; fetch successive pages until a page contains fewer than 25 records. Supported collections: requests, manager requests/team, courses, notifications, admin documents/chunks/audit, AI document summaries. Defaults: limit 50, maximum 100; offset 0–1000000.

```http
PATCH /api/v1/admin/knowledge/documents/1
Authorization: Bearer <hr-token>
Content-Type: application/json

{"is_approved":true,"expected_revision":3}
```

Use the revision returned alongside the complete source content reviewed by HR. Missing precondition gives 422; stale precondition gives 409. Reload and review after a conflict. Other document/chunk writes also accept optional `expected_revision` to prevent overwriting concurrent edits.

```http
GET /api/v1/ai/sources/1?revision=4
Authorization: Bearer <employee-token>
```

Uses `document_revision` from the AI citation. A changed, reapproved source returns 409; an unapproved/inactive/inaccessible source returns 404. The response never bypasses source access checks.

Errors consistently contain `detail`, `error: {code,message,fields}`, and `request_id`. Inputs/SQL/secrets are omitted. Body limit failures add 413 `payload_too_large`; pagination and identifier violations give 422.

## Setup, environment and frontend

Run from the repository root. For a separate synthetic demo database:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export ENVIRONMENT=development
export DEMO_MODE=true
export DEMO_PASSWORD='Password123!'
export DATABASE_URL=sqlite:///./janamen-demo.db
export ACCESS_TOKEN_EXPIRE_MINUTES=60
export AI_CONFIDENCE_THRESHOLD=0.8
export ENABLE_MOCK_INTEGRATIONS=false
python -m app.migrate
python -m app.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Choose an unused demo filename for a fresh rehearsal; do not delete existing files. For an existing real database, take an operator-controlled backup before explicitly choosing its URL and applying migrations. This implementation did not migrate the original database.

The current isolated preview is [localhost:8765](http://127.0.0.1:8765/), signed out. It uses a temporary synthetic database, not `janamen.db`.

Environment configuration:

| Variable | Requirement/default |
|---|---|
| `DATABASE_URL` | SQLite URL for the chosen database; default `sqlite:///./janamen.db` |
| `ENVIRONMENT` | development/test/production; default development |
| `SECRET_KEY` | Production requires a strong random value of 32+ characters; development may generate an ephemeral value, invalidating tokens after restart |
| `ALGORITHM` | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1–1440; default 60 |
| `DEMO_MODE`, `DEMO_PASSWORD` | Explicit synthetic development seeding; demo password at least 12 characters; demo mode forbidden in production |
| `ALLOWED_ORIGINS` | Default `[]` for same origin; explicit JSON list for a separate frontend; wildcard rejected |
| `MAX_REQUEST_BODY_BYTES` | Default 262144; allowed range 65536–1048576 |
| `AI_PROVIDER`, `AI_CONFIDENCE_THRESHOLD` | grounded_knowledge; default 0.8, effective minimum 0.75 |
| `HR_SUPPORT_EMAIL` | Fallback contact; default hr-support@janapost.kz |
| `ENABLE_MOCK_INTEGRATIONS` | Default false; optional local simulation only |

Production rejects the published synthetic password. Trusted local account/profile provisioning remains available through `python -m app.create_user --help`, with password entry via getpass. No real secret is included in these files.

Frontend test steps:

1. Open the server root; sign in as `aruzhan@janapost.kz` using the configured synthetic password.
2. Submit a vacation request; select the manager persona, enter the password for `timur@janapost.kz`, and approve it in Team & approvals.
3. Sign back in as the employee; verify the persisted status/history, balance and notification. Complete a lesson and refresh to confirm progress.
4. Sign in as `aigerim@janapost.kz`; create a synthetic document and section, review its full text, and approve it. Updated UI sends the reviewed revision automatically.
5. Ask AI Jana a supported question and open its citation; an unsupported question returns fallback. Logout revokes the session.

## Executed checks and evidence

| Actual command/check | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | 244 passed, one warning, 75.54s; [output](evidence/backend-tests.txt) |
| Ruff check and format on app/tests/migrations/smoke/audit script | Passed; 67 Python files formatted |
| `.venv/bin/python -m mypy app` | Passed, 50 files; check_untyped_defs enabled |
| `node --check static/js/app.js` and i18n.js | Passed |
| `.venv/bin/python -m pip check` | No broken requirements |
| `python dependency_audit.py --output ...` | 41 pins, zero advisory matches; [after](evidence/dependency-audit.json), [before](evidence/dependency-audit-before.json) |
| Migration copy upgraded twice | Rows preserved, FK/model comparisons clean; [evidence](evidence/backend-migration-rehearsal.json) |
| `JANAMEN_BASE_URL=http://127.0.0.1:8765 python smoke_test.py` | All ten steps passed; [output](evidence/backend-upgrade-smoke.txt) |
| Browser HR approval and citation | Confirmed; [approval](evidence/backend-revision-approved.jpg), [citation](evidence/backend-citation-verified.jpg) |
| `git diff --check`; original file checksums | Clean diff; original .env/database unchanged |

Maintainer advisory references: [AnyIO TLS](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6), [AnyIO workers](https://github.com/agronholm/anyio/security/advisories/GHSA-5p39-cfhj-2xmp), [IDNA](https://github.com/kjd/idna/security/advisories/GHSA-65pc-fj4g-8rjx), [Starlette form limits](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq). The before report lists all matching advisory aliases; affected dependency versions do not prove every listed issue was exploitable through this application.

## Remaining limitations

- Tested on macOS/Python 3.14 and SQLite. Docker execution, other operating systems, Python 3.11, PostgreSQL and enterprise load were not verified here.
- The upstream Starlette TestClient warns that its current httpx support is deprecated in favor of httpx2. Existing tests pass; no untested client migration was introduced.
- Single organization and small workloads. The login limiter is process-local; multi-worker/public deployment needs shared rate limiting, HTTPS, operational monitoring, backups and retention. No SSO, password reset, MFA or refresh-token rotation is implemented.
- 1C, Documentolog, payroll payments, EDS and external language models are unconnected. Local HR fields and seeded policies are synthetic. Real integration implementation requires approved documentation/connections.
- AI uses lexical coverage and exact extraction, which cannot establish semantic entailment or HR policy correctness. HR must review approved source content/access levels and remove inappropriate personal data. Historical source bodies are not archived; stale citations fail safely.
- Offset pagination is deterministic for unchanged data; concurrent inserts may shift later pages. The UI loads all pages and is not a virtualized enterprise table.
- Advance amounts still use the legacy Float column; validation limits them to two decimals, but this is not a financial ledger. Pending leave is not reserved, and overlapping dates/working-day policy are not invented.
- Audit is append-only through the application, not tamperproof against database administrators. Rich source editing and HR course assignment remain API features. If no other authorized reviewer exists, a request remains pending until HR provisions one.
- No exhaustive guarantee that every backend bug or security risk is eliminated. The evidence above identifies the tested behavior and operational boundaries.
