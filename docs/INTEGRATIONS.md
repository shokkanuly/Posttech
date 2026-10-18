# JanaМен integration gateway — implemented MOCK contract

**Current mode: MOCK only. No live 1C:ЗУП or Documentolog connection, document registration, payment or electronic signature.** This implements the canonical contracts in sections 5–7 of the supplied *JanaМен — Integration Design 1C ZUP and Documentolog* design. These endpoints are ours, not vendor APIs.

The older two-step `/v1/1c/orders` → `/v1/documentolog/documents` design has been replaced by the requested asynchronous `/v1/documents` contract. Existing signing primitives and header names are retained. The separate worktree's earlier in-memory simulator implementation was inspected but was not merged: it lacks these endpoints, durable jobs and the snapshot flow.

## Run the isolated MOCK stack

From a configured Python environment:

```bash
python -m app.gateway.configure_mock --web-port 18778 --postgres-port 15448
# Creates .env.gateway with mode0600, generated passwords/keys and a unique Compose project.
# It refuses to overwrite an existing file and never prints the keys.
docker compose --env-file .env.gateway --profile integrations up --build -d
```

Open `http://127.0.0.1:18778`. The usual synthetic seed accounts are `aruzhan@janapost.kz` (employee), `timur@janapost.kz` (manager), `aigerim@janapost.kz` (HR). Their generated password is stored only in the private environment file. The generated environment disables external AI and selects a unique `janamen-mock-*` Compose project. The generator refuses to overwrite files or run in production. Select unused ports before startup. See [the repeatable integration demo runbook](INTEGRATION_DEMO_RUNBOOK.md) for isolated demo accounts, registration assertions and outage/recovery.

`INTEGRATION_GATEWAY_URL` is still the switch. Empty means no new outbox tasks, no profile network reads and no integration delivery. The ordinary default Compose startup does not start the optional integration services. To enable them, use the generated environment and `--profile integrations` together. Setting the URL alone while leaving the gateway offline is allowed: approvals still succeed and delivery retries independently.

Do not commit/share `.env.gateway`; it is excluded by Git and Docker context. `configure_mock` creates new development credentials, not a rotation of an existing deployment. Existing `.env`, databases and running stacks are not changed by that command.

## Actual topology

```mermaid
flowchart LR
  Browser --> Web["JanaМен FastAPI: approval, profile, HR card"]
  Web --> DB[("PostgreSQL: requests, history, notifications, outbox, nonces, sync state")]
  Worker["Separate integration-worker process"] --> DB
  Worker -->|"HMAC; internal MOCK network"| Gateway["Separate FastAPI gateway :9000; no host ports"]
  Gateway --> GDB[("Persistent gateway volume: jobs, nonces, MOCK documents")]
  Gateway --> OneC["MOCK 1C connector: synthetic snapshot fixture"]
  Gateway --> Doc["MOCK Documentolog connector: durable MOCK-DOC reference"]
  Gateway -->|"Signed callback, retried"| Web
  Future["Future real connectors / private network / mTLS ingress"] -.-> Gateway
```

Compose's `integration` network is `internal: true`. The gateway belongs only to that network. Web and worker also reach the app database through the normal app network. The gateway's database is independent: a persisted SQLite WAL database in `gateway_data`, never the application's user tables. Its schema is created by the gateway itself; changes to the application schema use Alembic `0006_gateway_runtime`. The app worker uses PostgreSQL `FOR UPDATE SKIP LOCKED`; gateway claims use conditional updates and expiring leases, including SQLite concurrency tests.

**Transport boundary:** this local MOCK profile uses HTTP on the private Compose network plus HMAC authentication. It does not claim active mTLS. Existing outbound TLS1.3/mTLS client support remains available, including gateway callback client certificate configuration. Production certificate issuance, inbound mTLS termination and handshake deployment are not supplied by this demo; do not expose it as a production integration. Core production settings require HTTPS and a configured client certificate for an enabled gateway.

## Shared signature and anti-replay rules

Reuse `app/integrations/signing.py`, without a custom cipher:

```text
METHOD_UPPER + "\n" + PATH_WITH_QUERY + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + SHA256_HEX(RAW_BODY)
X-Signature = base64(HMAC-SHA256(key, that message))
```

Headers: **`X-Key-Id`, `X-Timestamp`, `X-Nonce`, `X-Signature`**. `Idempotency-Key` also accompanies document POSTs and must match the body. Unknown/retired key, wrong body/path/query signature, clock skew beyond300 seconds or an already seen nonce is rejected with401. Comparison uses `hmac.compare_digest`. Nonces persist in `gateway_nonces` and existing app `integration_nonces`; cleanup retains900 seconds, exceeding the signature window. Replaying captured signed requests remains rejected after a service restart. Retrying a legitimate operation uses a fresh nonce and the same idempotency key.

Each direction has a separate key. Verification maps support overlapping current/previous key IDs during operator-controlled rotation. There is no bearer-token fallback, anonymous health route, browser CORS or public Swagger/OpenAPI route on the gateway. Its container readiness check signs `/health`. Callback `nonce` must equal signed `X-Nonce`. The shared signing helper gained an optional nonce argument solely to bind that field into the body/signature.

Golden vectors in `tests/test_integration_hardening.py` pin UTF-8 bytes, uppercase method, literal encoded path/query, decimal timestamp, LF separators, lowercase hex SHA-256 and Base64 HMAC. They also pin the inclusive ±300-second boundary. The signer itself is unchanged.

All authenticated gateway routes share a durable fixed UTC-minute limit per verified key ID: `GATEWAY_REQUESTS_PER_MINUTE` (default 600, range 1–100000). Admission and nonce consumption commit together before a handler runs. Concurrent processes cannot exceed the bucket; restarts retain counts. Rejected requests return `429`, `Retry-After` seconds until the next minute and `Cache-Control: no-store`, without creating a job or nonce. Invalid/replayed signatures return 401. Rotated key IDs have separate buckets; fixed windows permit a burst across a minute boundary. This controls authenticated callers, including health probes, and is not a public-internet denial-of-service defense. Keep the gateway private. Safe rejection logs contain only the category/status, never headers or bodies.

Gateway startup upgrades its independent store additively to **v3**, creating `gateway_rate_limits` without rewriting jobs, references, callback state or nonces. Deploy one gateway instance for migration first. Core head remains `0011_merge_profile_updates`. An internal [OpenAPI snapshot](gateway-openapi.json) documents our canonical routes; no public schema endpoint is enabled.

No AES/JWE/custom encryption was added. Integration logs contain only technical state/counters/codes; canonical bodies, names, amounts, API keys and callback secrets are not logged or included in validation error responses. State includes the minimum canonical payload needed for restart-safe retries; storage is different from logging. Production storage/access/retention controls remain an operational requirement.

## Canonical gateway endpoints

All endpoints require a valid machine signature, including GETs and `/health`.

| Method | Path | Behavior |
|---|---|---|
| POST | `/v1/documents` | Validate canonical request, enforce matching key/body and persist one job; return202 with job ID/status and `mode: MOCK` |
| GET | `/v1/documents/{idempotency_key}` | Return persisted job/terminal result for reconciliation;404 if unknown |
| GET | `/v1/employees?updated_since=...` | Return canonical synthetic snapshots, `mode: MOCK`, high-water `next_cursor`; query is signed exactly |
| GET | `/v1/employees/{employee_code}` | Return one synthetic canonical snapshot;404 if unknown |
| GET | `/health` | Mode, actual connector availability, pending jobs/callback counts and last successful registration |

Vacation request example (our API, not a vendor document):

```json
{
  "idempotency_key": "REQ-N000005:v1",
  "kind": "VACATION_REQUEST",
  "request_code": "REQ-N000005",
  "employee_code": "JP-10428",
  "period": {"start": "2026-11-23", "end": "2026-11-25", "days": 3},
  "approved_by_employee_code": "JP-10201",
  "approved_at": "2026-10-17T10:15:00Z"
}
```

Codes, dates, charged days and decision metadata are frozen in the outbox at approval. Names, emails, free-text reasons, training and AI data do not travel. For advance requests the explicit **canonical extension** is `kind: ADVANCE_PAYMENT_REQUEST`, `amount` as an exact decimal string, `currency: KZT`, and no vacation `period`. This only registers a synthetic request; it never instructs or executes a payment.

The202 acknowledgement contains `gateway_job_id` (`job_<32hex>`), `idempotency_key`, `status`, `mode: MOCK`, `occurred_at`, optional `external_ref` and `error_code`. A terminal REGISTERED result must contain `MOCK-DOC-<32hex>`. Empty/malformed2xx responses are delivery errors, never successful registrations. Same key plus the same normalized canonical content returns the original job; same key with different content returns409. The mock connector enforces a second unique idempotency constraint on its durable document row.

## Flow A — approval to asynchronous MOCK registration

1. Existing approval transaction commits Approved + frozen charged days/provisional balance flag + history + notification + immutable outbox snapshot. `INTEGRATION_GATEWAY_URL` determines whether the registration task is added. There is no network call in that transaction.
2. App worker claims due PENDING tasks, signs `POST /v1/documents`, validates the acknowledgement and stores the job ID. Request sync status becomes SENT. Business status stays Approved.
3. Gateway worker claims a durable job using a lease. The MOCK Documentolog connector writes one durable synthetic reference in the same transaction as completion. It cannot call a vendor API.
4. Gateway sends a signed callback to the **existing** `/api/v1/internal/integrations/documentolog/status` route. The app matches the outbox key, approved request and job ID, then atomically updates `external_sync_id`/API alias `external_ref`, sync state, history and exactly one employee registration notice.
5. If a callback is lost, the gateway retries with fresh nonces. The app worker also polls `GET /v1/documents/{key}`; callback and reconciliation use the same idempotent transition, so whichever arrives second does not add another notice.

Callback body adds the explicit mode/error metadata to the design's example:

```json
{
  "nonce": "0123456789abcdef0123456789abcdef",
  "idempotency_key": "REQ-N000005:v1",
  "gateway_job_id": "job_0123456789abcdef0123456789abcdef",
  "status": "REGISTERED",
  "external_ref": "MOCK-DOC-0123456789abcdef0123456789abcdef",
  "occurred_at": "2026-10-17T10:15:04Z",
  "mode": "MOCK",
  "error_code": null
}
```

The nonce and job/reference values shown are illustrative synthetic values, not valid signed messages or credentials.

Request sync states are exposed separately from the Approved business state: **NOT_REQUIRED, PENDING, SENT, REGISTERED, FAILED, DEAD**. Disabled/legacy null state is represented as NOT_REQUIRED in the API. The legacy `external_sync_id` field remains for compatibility; `external_ref`, `sync_status`, `integration_mode` are exposed explicitly. Older legacy-contract pending rows are preserved, parked as DEAD/LEGACY_CONTRACT by the migration, and shown for HR review; they are never silently sent to an incompatible endpoint. Historical SIGNED rows are not relabeled as a registration by this new gateway.

### Failure and restart behavior

- Gateway/network/429/5xx: approval remains Approved. Delivery retries with jitter and the existing30s,60s,5m,15m,1h,6h,12h schedule; after8 consecutive delivery errors the outbox is DEAD and HR is notified.
- Malformed success envelope: `INVALID_ACK`, retried as a gateway error; no false SENT/REGISTERED result.
- Non-transient app delivery4xx: FAILED, no automatic retry; reason appears in the HR queue.
- MOCK Documentolog validation rejection: gateway job FAILED, no connector retry; signed failure callback updates separate sync state. Temporary MOCK connector failure uses backoff and becomes DEAD after8 attempts.
- Callback failure: retry independently; the registered MOCK document is never recreated. Terminal job remains available for GET reconciliation even if callback delivery exhausts attempts.
- Restart mid-job: persistent job/nonce/document rows survive. An expired processing lease can be reclaimed. Fresh-nonce retries with the same key return the same job/reference. Application outbox content never changes when profiles/calendar settings later change.

## Flow B — scheduled/read-only MOCK snapshots

The app integration worker polls snapshots on a configured interval (default900 seconds), using the last successful `updated_since` cursor. `POST /api/v1/admin/integrations/refresh` is HR-only and uses a database-backed cooldown (default60 seconds). An on-demand refresh fetches the full fixture so previously unmatched codes can be reviewed again after mapping.

`apply_snapshot` is the integration's single writer of profile facts. It matches **only employee code**, not email/name; it updates an existing profile and preserves role/login identity. Unknown employee/manager codes go to `integration_reviews` for HR. No arbitrary new user/role is provisioned. Older snapshots and insufficient/conflicting balances are held for review. Integration data does not enter the knowledge base or AI provider.

Profiles store source mode, original snapshot balance, `as_of` and `synced_at`. A successful source check leaves a truthful freshness record; failed checks retain the last snapshot and expose `is_stale`. Profile/dashboard requests never synchronously call the gateway. Disconnecting a previously synced source also marks that retained snapshot stale. The UI says MOCK and read-only, never official 1C data.

For reconciliation, the **canonical snapshot extension** `confirmed_request_codes` explicitly identifies local approvals already included in the source balance. An approved local request keeps frozen charged days and is provisional until confirmed. Effective local balance is source balance minus still-unconfirmed charged days. A Documentolog registration alone does **not** prove a 1C balance posting and does not clear the provisional adjustment. The default MOCK fixture confirms no approvals. Existing pre-migration approvals retain their legacy balance state; official historical reconciliation requires operator/partner confirmation.

## HR operational display

`GET /api/v1/admin/integrations` uses persisted facts, not hardcoded statistics or a live network request during page load. Each card includes mode (UNCONNECTED or observed MOCK), pending/failed delivery counts, actual last success time, last source error and confirmed synthetic record count. A configured but never successfully observed gateway remains UNCONNECTED. CONNECTED cannot be produced by this MOCK implementation.

HR-only queue and review endpoints:

- `GET /api/v1/admin/integrations/queue`: paginated FAILED/DEAD request codes, safe error code and mode.
- `GET /api/v1/admin/integrations/reviews`: paginated unmatched/conflicting employee codes and reason.
- `POST /api/v1/admin/integrations/refresh`: role checked and rate limited.

Every MOCK reference displayed in a request detail carries a MOCK label. The admin headline changes from UNCONNECTED to observed MOCK and explicitly says no live enterprise connection. Both RU/KK labels are maintained.

## Configuration and verification

Existing settings: `INTEGRATION_GATEWAY_URL`, `INTEGRATION_OUTBOUND_KEY_ID`, `INTEGRATION_OUTBOUND_KEY`, `INTEGRATION_INBOUND_KEYS`, and outbound `INTEGRATION_TLS_CERT/KEY/CA`.

Gateway settings are separately prefixed `GATEWAY_`: MODE (only MOCK accepted), DATABASE_URL, APP_KEY_ID/APP_KEY or JANAMEN_KEYS verification map, CALLBACK_URL/KEY_ID/KEY, optional TLS_CA/CERT/KEY, WORKER_ENABLED/POLL_SECONDS, optional MOCK_EMPLOYEES_FILE. MOCK_ONE_C_UNAVAILABLE and MOCK_DOCUMENTOLOG_FAILURE allow controlled local failure testing; they do not select real connectors.

```bash
python -m pytest -q tests/test_gateway_service.py tests/test_integration_gateway.py tests/test_migrations.py
python -m pytest -q
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/TEST_DB python -m pytest -q
node --test tests/frontend_localization.test.cjs
python -m ruff check app tests migrations smoke_test.py dependency_audit.py
python -m mypy app
```

Tests use isolated databases and synthetic keys. The six acceptance conditions from design section10 map to signature/replay tests, concurrent idempotency/restart tests, gateway-down approval/retry/DEAD tests, callback/reconciliation notification tests, bearer-denial tests, and profile-outage snapshot tests. Actual results for this implementation are recorded in `docs/GATEWAY_IMPLEMENTATION_REPORT.md`; test existence alone is not a claim of execution.

## Still needed for any live connection

Jana Post must provide vendor API documentation, test systems, employee-code mapping and balance-posting confirmation semantics, document types, authorized service accounts and private network/certificate ownership. Real connectors, VPN, inbound mTLS deployment, electronic signatures, production secret/storage/retention operations, automated dead-letter replay and a partner reconciliation schedule are not delivered. This service is a durable **MOCK** integration gateway, not evidence of a live enterprise connection.

## Controlled recovery and store upgrades

The fix-plan follow-up adds audited HR recovery/mapping commands, signed generation-aware retries, and gateway schema v2. See [Recovery and operations](RECOVERY_AND_OPERATIONS.md) for request contracts, lost-store behavior, immutable submission keys and the backup/restore procedure. All connectors remain MOCK; these are JanaМен canonical endpoints, not vendor APIs.
