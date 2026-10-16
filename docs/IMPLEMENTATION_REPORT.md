# JanaМен implementation report

This is the initial MVP implementation record. The subsequent [backend upgrade report](BACKEND_UPGRADE_REPORT.md) supersedes test counts and API details below, including document revisions, pagination, request limits and patched dependencies.

Completed 16 October 2026. The existing FastAPI/SQLAlchemy architecture and HTML/CSS/JavaScript frontend were retained. No external AI service, database service, 1C connection, Documentolog connection, deployment, or paid service was introduced.

Initial source inspection found a clean Git working tree and an already functioning modular backend. The initial report and design contract were written before the application changes: `IMPLEMENTATION_PLAN.md` and `API_CONTRACT.md`. Git advanced through user-owned commits while work continued; those commits and history were preserved. Final refinements and evidence can be reviewed in the working tree.

**What changed and why**

| Files / area | Result |
|---|---|
| `app/config.py`, `.env.example` | Explicit demo mode; production secret validation; no public signing key; bounded configuration; redacted settings errors. Published demo-password authentication is rejected in production. The private `.env` was not overwritten. |
| `alembic.ini`, `migrations/`, `app/migrate.py`, `app/database.py` | Versioned, forward-only schema upgrades; complete legacy-schema adoption; duplicate-record checks; foreign-key enforcement; explicit rollback; startup revision check. |
| `app/models/` | SQLAlchemy 2 native typed mappings; session table; source approval metadata; unique enrollment and lesson-progress indexes. |
| `app/services/auth_service.py`, `app/routers/auth.py`, `app/create_user.py` | Real credentials, current database roles, persisted revocable JWT sessions, logout, failed-login limiting, password-hash upgrades, trusted local account/profile provisioning. |
| `app/schemas/`, `app/errors.py`, routers | Bounded request/response schemas, stable redacted errors with request IDs, no unknown identity/role fields, accurate UTC timestamps, positive identifiers, OpenAPI response/error contracts. |
| Request service and manager APIs | Unique request codes; owner/direct-report/HR scope; no self-review; conditional Pending transitions and atomic leave debit/history/notification/audit; HR queue matches HR scope. |
| Academy service and APIs | Explicit persistent self-enrollment/HR assignment; serialized enrollment/progress updates; idempotent enrollment; validated quiz indices; actual lesson counts; stored scores and completion timestamps; completion notification once. |
| Notification APIs | Owner-only read/unread updates, read-all, bounded list, accurate unread count independent of list limit. |
| AI and knowledge services/admin APIs | Draft→review→approval lifecycle; editing invalidates approval; active/approved role-filtered sources; conservative unique-token coverage; exact citations and source fetches; safe fallback; persisted minimal audit metadata without raw questions. |
| Integration adapters | Truthful UNCONNECTED status, zero sync count, no fabricated last-sync. Optional local references are explicitly MOCK; no external registration occurs. |
| `static/index.html`, `static/js/app.js`, CSS/i18n | Existing layout/pages retained. Real sign-in/out; persona selector only pre-fills an email; no automatic login on 401; repaired Team/HR navigation; review modal replacing unsupported native prompt; dynamic dashboard/profile learning results; source click listeners; HR draft/approval UI; real account counts; truthful integration labels; narrow header fixes. |
| Seed and test fixtures | Synthetic data only; explicit non-production seeding; one consistent second-course lesson count; each test owns its database/startup engine and authenticated sessions. No destructive reset command. |
| Requirements, `pyproject.toml`, smoke script | Exact validated runtime/dev dependency set, formatter/linter/type-check configuration, configurable smoke target, actual balance/revocation assertions. |
| Docker files | Non-root container, localhost Compose exposure, persistence limited to `/data`; rebuilt source is no longer masked by a persistent `/app` volume. Docker execution remains unverified. |
| Documentation/evidence | Setup, schema, permissions, complete endpoint listing, OpenAPI JSON, examples, limitations, screenshots, and clean-start smoke output. |

See `CHANGED_FILES.md` for the complete file manifest. Original project documents and the unused static design reference were preserved.

**Architecture and schema**

The application remains a modular monolith: validated HTTP routes → domain services → typed SQLAlchemy models → SQLite. Authentication checks signature, required claims, session validity, expiry and active user; authorization then uses the current database role and record scope. Browser role selection and JWT role claims do not grant privileges. Tokens stay in browser memory.

The 13 tables are `users`, `auth_sessions`, `employee_profiles`, `requests`, `request_events`, `courses`, `lessons`, `enrollments`, `lesson_progress`, `notifications`, `knowledge_documents`, `knowledge_chunks`, and `audit_events`. The architecture diagram, key fields, foreign keys, unique pairs and transaction behavior are in `../ARCHITECTURE.md`.

The database is a tested SQLite deployment for one organization. PostgreSQL or multi-tenant correctness is not claimed. Official-field editing is unavailable through employee APIs; displayed records are explicitly local, with 1C unconnected.

**API and examples**

The generated OpenAPI records **35 paths / 38 operations**, including homepage and health. `ENDPOINTS.md` enumerates every method/path and authentication requirement. `API_CONTRACT.md` defines schemas, scope, status transitions, validation and errors; `openapi.json` is the machine-readable contract.

Core operations are credential login/logout; own identity/profile/dashboard; own request list/create/detail; scoped manager/HR queue and review; own notifications; course catalog/enrollment/lesson/quiz; approved knowledge chat/source/document listing; HR document/chunk approval and editing; HR enrollment assignment; HR summary/audit/integration boundaries.

Example request after credential login:

```http
POST /api/v1/requests
Authorization: Bearer <employee-token>
Content-Type: application/json

{"type":"Vacation","start_date":"2026-11-23","end_date":"2026-11-25","reason":"Synthetic demo request"}
```

The returned ID is used with an authorized manager session:

```http
POST /api/v1/requests/5/approve
Authorization: Bearer <manager-token>
Content-Type: application/json

{"action":"approve","comment":"Synthetic manager approval"}
```

AI example:

```http
POST /api/v1/ai/chat
Authorization: Bearer <employee-token>
Content-Type: application/json

{"question":"How do I request vacation?"}
```

Sources contain real chunk/document IDs, titles, sections, versions and synthetic-example flags. `/api/v1/ai/sources/{chunk_id}` fetches the full source under the same access checks. Unsupported detail questions, such as vacation carryover absent from the documents, return fallback rather than a generic answer labeled reliable.

**Setup and frontend connection**

Complete installation, environment variables, test accounts, provisioning, Docker notes and exact frontend walkthrough are in `../README.md`.

For an existing installed environment, run from the repository root:

```bash
export ENVIRONMENT=development
export DEMO_MODE=true
export DEMO_PASSWORD='Password123!'
export DATABASE_URL=sqlite:///./janamen-demo.db
export ACCESS_TOKEN_EXPIRE_MINUTES=60
export AI_CONFIDENCE_THRESHOLD=0.8
export ENABLE_MOCK_INTEGRATIONS=false
.venv/bin/python -m app.migrate
.venv/bin/python -m app.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

This deliberately selects a separate demo database. To restore a fresh rehearsal without deleting data, choose another unused filename and migrate/seed it. To upgrade the existing database instead, make an operator-controlled backup and explicitly select its URL; legacy documents then require HR review/approval. No reset or migration was run against the original `janamen.db` during implementation.

The frontend needs no build step. Open `http://127.0.0.1:8000`, sign in, and use the existing sidebar. It calls same-origin `/api/v1`. For a separate frontend development origin, proxy `/api/v1` or configure an explicit `ALLOWED_ORIGINS` list. Production requires a strong private `SECRET_KEY`, disabled demo mode, private provisioned accounts, and HTTPS. No real secret is included in the examples.

**Initial MVP validation (before the subsequent backend upgrade)**

| Check actually run | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **81 passed in 27.17s** |
| `ruff check app tests migrations smoke_test.py` | Passed |
| `ruff format --check app tests migrations smoke_test.py` | Passed; 61 Python files formatted |
| `python -m mypy app` | Passed; 48 source files checked using native ORM types |
| `node --check static/js/app.js` and `static/js/i18n.js` | Passed |
| `python -m pip check` in project-only virtual environment | No broken requirements |
| HTML ID inspection | 119 unique IDs; no duplicates |
| Fresh working-source snapshot, isolated new database | Migration and seed succeeded; `/health` and homepage returned 200; all smoke steps passed |
| Existing database migration rehearsal | Copy retained 5 users and 6 requests; 0 foreign-key violations; 0 model/schema differences; original database checksum unchanged |
| Browser interaction | Employee sign-in and request creation; manager sign-in, queue and approval modal; source citation opening; unsupported-detail fallback; persisted profile results; HR sign-in, navigation, draft creation and explicit approval; logout |
| Responsive browser checks | Manager page document width equaled viewport at 390 and 360 pixels |
| Final browser console inspected | No errors in the final validation tab |
| Docker container run | **Not run**: local Docker daemon unavailable |

The automated suite covers expired/malformed/revoked sessions, deactivation, forged role claims, unauthorized scope, missing/invalid amounts, nonfinite values, extra fields, request-code exhaustion, invalid/duplicate/competing review actions, rollback on notification failure, migrations and safe failure cases, notification ownership/read status, explicit/concurrent enrollments, persistent progress/results, document approval/access/deactivation, exact sources and fallback, audit redaction/persistence, UTC timestamps, local provisioning and the complete API journey.

The clean-start smoke test used a fresh copy of the working source and a separate server/database, with the validated dependency environment. Its output is saved at `evidence/clean-start-smoke.txt`. A new network-only dependency installation was not used as evidence. An initial system-wide dependency check found unrelated preinstalled Google/protobuf conflicts; those global packages were left unchanged, and project validation was isolated to the required distributions.

The browser checks are separate from pytest, not a claim that a CI browser suite exists. Initial reproducible failures found during implementation were corrected before the final checks: stale official-source expectations, an invalid reserved-domain provisioning example, ORM type inference/import issues, dead Team/HR navigation and the unsupported native review prompt.

**Confirmed bugs fixed**

- Public default signing key and public browser-embedded passwords; no logout revocation; automatic fallback login after 401.
- Sequential request-code collisions with seeded records and resulting persistent HTTP 500s.
- Approval of 30 leave days against an 18.5-day balance; duplicate/conflicting approvals and partial-write risk.
- Missing advance amounts bypassing field validation; fractional amounts rounded away in request summaries; uncontrolled/unknown input and inconsistent error contracts.
- HR pending counts without an accessible company queue; unread flags that could not be cleared back to unread.
- AI source clicks broken by apostrophes, overly permissive repeated-keyword scoring, unsupported-detail answers labeled grounded, and AI audit writes lost on session close.
- Catalog reads creating transient enrollments, incorrect averages for unseeded learners, course metadata disagreeing with actual lessons, missing stored results and stale dashboard/profile cards.
- Hardcoded workforce/compliance values, false synchronization/immutability claims, role navigation outside the bound container, and a review prompt unsupported by the in-app browser.
- Mobile header overflow and ambiguous timezone-less API timestamps.
- Docker volume masking rebuilt source and assets.

**Remaining limitations and risks**

No reproduced blocker remains in the seeded flows exercised above. This is not a claim of exhaustive testing or production HR readiness.

- 1C, Documentolog, payroll payments, signatures and external AI are unconnected. Sample HR policies remain synthetic examples, not official company policy.
- SQLite, a single organization and small concurrent workloads are the validated scope. Requests/knowledge listing and ORM access are not load-tested for enterprise volume.
- Failed-login limiting is process-local. Multiple workers need shared rate limiting and a correctly configured HTTPS proxy. There is no SSO, password-reset workflow, refresh-token rotation or automated session/audit retention job.
- Audit is append-only through the application, not protected from a database administrator. No tamper-proof audit guarantee is made.
- AI uses lexical coverage, not semantic entailment. Unknown paraphrases can fall back; additional real approved policies and question coverage require HR review. Human approval does not automatically detect all personal or inappropriate content in a source.
- Document edits invalidate approval, but prior revisions are not archived immutably. Rich source editing and HR course assignment are available through authenticated APIs rather than a complete management editor.
- Advance amounts retain the existing floating-point workflow storage; real payroll should use fixed-precision or minor-unit monetary storage. No payment is executed.
- Learning score is the percentage of lessons passed; no proctored exam, certificate file or payroll/legal certification is produced.
- RU/KZ localization is partial scaffolding. Notifications refresh through page actions rather than push delivery. Tables can scroll horizontally on narrow screens.
- Docker/Linux execution and a fresh network-only installation were not verified. Previously used `/app` Docker volumes need an operator-managed data/ownership migration rather than deletion.

Evidence screenshots are in `evidence/source-citation.jpg`, `manager-approval.jpg`, `mobile-manager-390.jpg` and `hr-approved-source.jpg`. The local validation preview at `http://127.0.0.1:8765` uses a disposable synthetic database and was left signed out; use the documented setup for a durable local demo.
