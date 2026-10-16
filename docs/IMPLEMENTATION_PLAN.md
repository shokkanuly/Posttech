# JanaМен implementation plan and initial inspection

Baseline: `5c77918`, 16 October 2026. Git was clean before work. Existing ignored SQLite data will be preserved; tests and migration rehearsal will use temporary databases or copies.

The existing stack is FastAPI, Pydantic 2, SQLAlchemy 2, SQLite, JWT, and plain HTML/CSS/JavaScript. Keep it as a modular monolith: routers validate HTTP contracts, services enforce permissions and transactions, models persist domain records. No frontend framework replacement, external AI service, or enterprise connection is needed.

Working: login/password hashing, own profile/dashboard reads, employee and manager request scope, primary request journey/history, persisted notifications, primary course completion, keyword document lookup. Simulated: persona auto-login, static dashboard course card, integration telemetry/references, synthetic policies. Missing or unreliable: versioned migrations, revocable sessions, deployment secrets, atomic transitions/balance debits, stable request identifiers, complete validation, document approval lifecycle, reliable AI fallback/audit persistence, explicit enrollment, isolated tests, standardized errors, accurate documentation.

Implementation order:

1. Versioned Alembic migrations, preserving legacy rows; settings and explicit startup migration command. Add sessions, document approval metadata, enrollment/progress uniqueness. Do not drop/reset databases.
2. Server-backed JWT sessions, logout revocation, bounded login attempts, environment safety checks and error handlers. Browser keeps bearer tokens only in memory; no auto-login on 401.
3. Read-only profile/dashboard and record scopes. HR company queue; managers direct reports only.
4. Collision-safe request codes and atomic pending→approved/rejected transactions, including balance debit, history, notifications, audit. No self-review.
5. Persistent notification read/unread updates and explicit course enrollment/assignment, consistent lesson counts, progress/results and completion notifications.
6. Approved, active, role-filtered document retrieval, conservative answerability/fallback, exact sources, minimal audit metadata, HR document/chunk management.
7. Small frontend integration changes within the existing layout: real login/logout, errors, dynamic dashboard course, source listeners, course results, mobile header. Label unconnected integrations and synthetic examples.
8. Migration, permission, validation, transaction, AI, persistence and browser regression checks; document actual results and limitations.

See [API_CONTRACT.md](API_CONTRACT.md) for the contract fixed before frontend changes. Security-sensitive state changes are tested with independent sessions and concurrent requests where relevant. Migrations are forward-only; restoring a backup is an explicit operator operation, never an automatic startup action.
