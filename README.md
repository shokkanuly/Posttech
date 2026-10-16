# JanaМен — employee HR workspace

A modular FastAPI/SQLAlchemy MVP with the original HTML/CSS/JavaScript frontend. It supports real credential login, revocable bearer sessions, employee/manager/HR scopes, read-only profiles, transactional requests and history, notifications, courses and persisted results, and approved-document HR assistance.

The demo uses synthetic users and sample documents. **1C:ZUP and Documentolog are unconnected.** AI Jana returns exact approved source text using conservative keyword retrieval; no external model or paid service is required.

## Local setup

Tested with Python 3.14. Direct dependencies are pinned in `requirements.txt`; development checks are in `requirements-dev.txt`. Run commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

# Explicit local demo configuration; this preserves an existing .env and database.
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

Open [the workspace](http://127.0.0.1:8000), [interactive API docs](http://127.0.0.1:8000/docs), or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json). An empty/known unsafe development signing key is replaced by a process-local random key; restarting the server requires signing in again.

Alternatively, create `.env` from `.env.example` **only if `.env` does not already exist**. Merge the relevant settings into an existing file rather than replacing it. Environment variables override file settings. The implementation work does not alter the existing private `.env` or `janamen.db`.

| Synthetic demo account | Email | Password |
|---|---|---|
| Employee | aruzhan@janapost.kz | Value of `DEMO_PASSWORD` above |
| Manager | timur@janapost.kz | Same demo password |
| HR administrator | aigerim@janapost.kz | Same demo password |

The role selector only pre-fills a demo email and signs out the current session. A password is still required. The server ignores client-selected roles and loads permissions from the authenticated database user. There is no automatic login on an expired or revoked token. Tokens are held in browser memory, not local storage.

Seeding is allowed only in explicit non-production demo mode, requires a 12+ character synthetic password, and skips databases containing users. For a fresh rehearsal, choose a **new database filename**, then run migrate and seed. There is no automatic destructive reset.

## Existing databases and migrations

`python -m app.migrate` and `alembic upgrade head` apply forward-only migrations:

- `0001_baseline`: creates the original schema for new databases or adopts a complete legacy schema without changing its existing rows.
- `0002_sessions_and_approvals`: adds revocable sessions, explicit knowledge approval metadata, and unique enrollment/progress indexes.

Startup checks the revision and stops with the migration command if it is missing. A partial legacy schema or duplicate enrollment/progress records stops the migration for operator review; records are never silently deleted or merged. Existing knowledge documents become drafts until HR reviews and approves them. Existing password hashes remain valid and are upgraded after successful login. Old bearer tokens have no persisted session and must be replaced through login.

Before migrating valuable data, make an operator-controlled backup. Migration rehearsal was performed on a copy of the existing database; the original file was not migrated or reset. See `docs/IMPLEMENTATION_REPORT.md` for actual validation results.

## Frontend integration and demonstration

The API and assets share one origin; no frontend build step is needed. `static/js/app.js` uses `/api/v1`. For a separate development frontend, configure an explicit `ALLOWED_ORIGINS` JSON list and proxy `/api/v1` to this backend. Wildcard origins are rejected. The supported frontend is served at `/`; the old `janamen_preview.html` is an unused static design reference.

1. Sign in as the employee. Open Profile and check the local read-only fields, leave balance, and learning summary.
2. Open My requests → New request. Submit vacation dates and a handover note. Open Details to see the Pending status and submission event.
3. Sign out, then sign in as the manager. Open Team & approvals, approve the in-scope request through the review modal, and add an optional comment. Repeated or conflicting reviews return 409. Requests outside the manager’s team return 403.
4. Sign back in as the employee. Open Notifications and the request history. Approval deducts leave atomically and persists the approval event and notification. External registration remains unconnected.
5. Open Jana Academy, finish the final security lesson, and submit its quiz. Check course completion, result, notification, profile progress and the refreshed dashboard card. Catalog courses can be explicitly enrolled in; viewing them never creates assignments.
6. Ask AI Jana “How do I request vacation?” and click the source button. The modal fetches the exact approved section and version, including apostrophes safely.
7. Ask “What is the pet insurance policy?” or “How many unused vacation days can I carry over into next year?” Both should fall back. Asking for another employee’s salary should be refused.
8. Sign in as HR. Open HR administration, save a draft document and section, review its text, then approve it. Draft/inactive documents are excluded from AI. Editing source content requires reapproval. HR-only sources are unavailable to employee accounts.

## API contracts

See `docs/API_CONTRACT.md` for the complete endpoint list, permission matrix, validation rules, schemas and error format. The generated OpenAPI document is the machine-readable reference.

Example local demo login:

```bash
curl -sS http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"aruzhan@janapost.kz","password":"Password123!"}'
```

Use the returned token as `Authorization: Bearer <token>` for these examples:

```http
POST /api/v1/requests
Content-Type: application/json
Authorization: Bearer <token>

{"type":"Vacation","start_date":"2026-11-23","end_date":"2026-11-25","reason":"Synthetic demo request"}
```

```http
POST /api/v1/ai/chat
Content-Type: application/json
Authorization: Bearer <token>

{"question":"How do I request vacation?"}
```

A validation error has this stable shape, without raw request input:

```json
{"detail":"Invalid input","error":{"code":"validation_error","message":"Invalid input","fields":[{"location":["body","amount"],"message":"Input should be greater than 0"}]},"request_id":"..."}
```

## Checks

```bash
python -m pytest -q
ruff check app tests migrations smoke_test.py
ruff format --check app tests migrations smoke_test.py
python -m mypy app
node --check static/js/app.js
node --check static/js/i18n.js

# Mutates only the server/database selected by the operator; use a disposable demo.
JANAMEN_BASE_URL=http://127.0.0.1:8000 DEMO_PASSWORD='Password123!' python smoke_test.py
```

Tests use their own SQLite files, migrations, startup engines and real authenticated sessions. They cover role/record scope, validation, revocation, conflicting approvals, balance integrity, transaction rollback, migration preservation/failures, notification ownership, enrollment concurrency, progress, knowledge approval, sources/fallback and the critical API journey. Browser interaction evidence is separate from API tests.

## Configuration and non-demo accounts

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite URL; tested database for this MVP |
| `ENVIRONMENT` | `development`, `test`, or `production` |
| `SECRET_KEY` | Production: independently generated random environment secret, at least 32 characters; never use published demo/test values |
| `DEMO_MODE` | Defaults false; rejected in production; controls synthetic seeding and account hints |
| `DEMO_PASSWORD` | Required only when seeding a local demo; never a production password |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1–1440, defaults 60 |
| `ALLOWED_ORIGINS` | Optional explicit JSON list; empty means same-origin only |
| `AI_CONFIDENCE_THRESHOLD` | Normalized coverage threshold; minimum safety floor 0.75, defaults 0.8 |
| `AI_PROVIDER` | Only `grounded_knowledge` is supported |
| `HR_SUPPORT_EMAIL` | Escalation contact; configure the real approved helpdesk before deployment |
| `ENABLE_MOCK_INTEGRATIONS` | Defaults false; optional local mock references are explicitly prefixed MOCK and never connect externally |

Production rejects an empty/known demo signing key and demo mode. Put it behind HTTPS before using authenticated accounts remotely. Provision non-demo users through the trusted local command, which prompts for the password without placing it in command history:

```bash
python -m app.create_user --email admin@example.test --name 'Synthetic HR Admin' \
  --role hr_admin --employee-code SAMPLE-ADMIN --company 'Sample company' \
  --department 'HR' --position 'Administrator' --location 'Sample office' \
  --hire-date 2026-10-16 --leave-balance 0
```

Use operator-supplied profile values. `--manager-email` can link an employee to an existing active manager. This command creates local records; it does not verify them with 1C.

## Docker

```bash
docker compose up --build -d
curl http://127.0.0.1:8000/health
```

Compose reads explicit demo/environment settings from `.env` or the shell, binds localhost, runs migrations, and persists only `/data`. Source and assets remain in the image so rebuilds take effect. The container runs as a non-root user. Docker execution was not validated in this environment because its daemon was unavailable. An old volume previously mounted over `/app` needs an operator-managed migration/ownership check; do not delete it to force an update.

## Boundaries and limitations

This is a single-organization hackathon MVP, not a production HR system. No real 1C, Documentolog, payroll disbursement, electronic signatures, SSO, password reset, refresh tokens, certificate files, or external AI provider are connected. Audit is append-only through application endpoints, not a tamper-proof database. The login limiter is process-local; multiple workers need a shared gateway/rate limiter. Session and audit retention cleanup is an operator concern. SQLite concurrency correctness is tested at small scale, not load-tested for enterprise use.

AI uses lexical coverage rather than semantic understanding; unfamiliar paraphrases may safely fall back. HR must review source accuracy, authorization and personal-data content before approval. Document versions are edited in place, not retained as an immutable revision archive. RU/KZ localization remains partial scaffolding. UI notifications refresh on relevant page actions rather than a push connection.

Architecture, database schema and remaining risks are documented in `ARCHITECTURE.md` and `docs/IMPLEMENTATION_REPORT.md`.
