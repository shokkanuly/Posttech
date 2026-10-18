# 02 — Architecture: Existing System and Safe Target Evolution

## Important implementation rule

This is **not a greenfield architecture**. `00_CURRENT_PROJECT_STATE.md` summarizes the supplied QA report. Inspect current repository code and extend it. Do not create a second outbox, gateway, request workflow, auth system, or profile-sync service just to match a generic target diagram.

## Existing topology grounded in the QA report

```text
Employee / Manager / HR Browser
            |
            | app session/bearer authorization
            v
FastAPI application (app/main.py)
  |-- Auth + server-side roles
  |-- Request workflow / policy validation
  |-- Profiles / HR snapshot view
  |-- Academy / AI / notifications
  |-- Audit and request-event history
  |-- App-side integration outbox
            |
            +-----------------------> PostgreSQL / SQLite (tests)
            |                          requests, profile snapshots,
            |                          events, audit, notifications,
            |                          outbox, mapping/job metadata
            |
            | durable job dispatch over signed internal API
            v
Internal integration gateway (app/gateway/main.py)
  |-- HMAC machine auth + durable nonce/replay protection
  |-- durable async jobs/leases/retries
  |-- MOCK document registration connector
  |-- persistent signed callback retries
            |
            +---- callback/status reconciliation ----> FastAPI app
            |
            +---- persisted mock external document reference

1C:ЗУП: NOT CONNECTED
  Current implemented path: signed MOCK employee-code snapshots
  -> app/integrations/profile_sync.py -> existing profiles only
  -> source/as-of/freshness metadata; unmatched mappings to HR review

Documentolog: NOT CONNECTED
  Current implemented path: app request -> app outbox -> signed internal
  gateway -> persistent MOCK registration -> signed callback/reconciliation
```

The QA report says four Compose services ran in the isolated verification setup, with three configured healthy probes and the gateway internal/no host port. Confirm actual `docker-compose.yml` before relying on any port/service assumptions.

## Current major boundaries

### Domain request transaction

`app/services/request_service.py:review_request` is the business decision path. The approval transition, related balance effects, event history, persistent employee notification, audit and outbox insertion are intended to commit together. External network calls must remain outside this business transaction. Tests inject failure at several write stages to ensure no partial approval/outbox state remains.

### App-side outbox

`app/integrations/outbox.py` stores/dispatches an immutable canonical snapshot using a stable `request:v1` key. It claims due work, uses bounded jittered retries, validates gateway acknowledgment and applies terminal results conditionally/idempotently. PostgreSQL worker claim uses `FOR UPDATE SKIP LOCKED`; independent multi-process application-worker testing remains open in the QA report.

### Internal gateway

`app/gateway/main.py`, `runtime.py`, and related models implement a durable async job API. `POST /v1/documents` is internal to the gateway and returns `202` for durable accepted work; it does not synchronously claim that a vendor document was signed. Machine requests are HMAC-authenticated with method/path-query/time/nonce/body digest binding and durable replay protection. Gateway work uses leases, stored attempts and persistent callbacks. This channel is not a vendor webhook channel.

### Current mock connector

`app/gateway/connectors.py` returns persisted `MOCK-DOC` style references deterministically for the same persisted logical job and supports controlled failure/rejection modes. A new empty store is not the same as recovering the same persisted job. Existing status labels include values such as `NOT_REQUIRED`, `PENDING`, `SENT`, `REGISTERED`, `FAILED`, and `DEAD`; do not overwrite current semantics without compatibility planning.

### Current 1C sync stand-in

`app/integrations/profile_sync.py` consumes signed mock employee-code snapshots, updates existing mapped profiles only, records source and timestamp, and sends unknown mappings/balance conflicts to a persisted HR review view. Profile pages consume local persisted data so gateway outage does not synchronously break the profile view. There is no live 1C API connector or official write-back in the supplied report.

### AI and approved knowledge

`app/services/ai_service.py` and knowledge/ML modules implement local retrieval and grounded answers/fallback. Gemini quote selection is optional and default-off until configured approval. The raw user question is intended to remain local; only limited approved source text may be sent for the quote-selection workflow. A literal numeric conflict guard is fixed but broad semantic contradiction handling is incomplete.

## Evolution principles

1. Reuse the existing project stack: FastAPI + plain HTML/CSS/JS, the existing model/session/request services, app migrations, outbox, HMAC signer, gateway, and profile-sync path.
2. Use provider-neutral adapter methods beneath the current service/gateway seam rather than changing UI/domain logic to provider-specific APIs.
3. Keep external calls asynchronous/durable. Never call the provider from within the request approval transaction.
4. Preserve local stale snapshots during outages and show source/as-of/freshness accurately.
5. Keep approval/business state separate from integration registration and eventual official HR processing. `Registered` is not equivalent to “signed” or “processed in 1C”.
6. Use immutable event keys/payload snapshots for retries. Reconcile ambiguous outcomes before repeat create operations.
7. Provider-specific endpoint URLs, payloads and credentials belong in the actual connector/config layer, not static frontend code.
8. Make live providers fail-closed until environment, security and business prerequisites are signed off.
9. Keep the current internal HMAC protocol, but separately verify how real vendor callbacks are authenticated.
10. Add versioned schema upgrades for gateway state; app migrations 0001–0006 do not prove gateway tables are migrated.

## Intended provider capability evolution

```text
Existing HR snapshot contract
        |
        +-- Mock source (current)
        +-- Future 1C:ZUP read adapter (only after contract verified)
        +-- Future official 1C write adapter (separately approved, OFF by default)

Existing internal document job contract
        |
        +-- Mock registration connector (current)
        +-- Future Documentolog Business connector (only after sandbox/API contract)
```

Do not make the integration gateway public. Production network/TLS/mTLS deployment and vendor ingress are unverified release gates.

## Existing service entrypoints noted by QA

- App: `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` after an explicit development DB migration.
- App outbox worker: `.venv/bin/python -m app.integrations.outbox`.
- Gateway app module: `app.gateway.main:app`; use its current Compose/configured host/port rather than guessing.
- App migration module: `.venv/bin/python -m app.migrate`; target only an explicitly selected development/disposable database.
- Frontend syntax: `node --check static/js/app.js`; localization tests: `node --test tests/frontend_localization.test.cjs`.
