# Repeatable local MOCK integration demo

This runs JanaМен's existing application → outbox → private gateway → synthetic Documentolog → signed callback/reconciliation path. No vendor account is needed. All employee snapshots and registrations are MOCK. The application and gateway stores are separate; the browser contacts only the application.

## Create a new isolated environment

From the repository, with Docker Desktop running and the Python environment installed:

```sh
.venv/bin/python -m app.gateway.configure_mock \
  --output .env.gateway --web-port 18778 --postgres-port 15448
docker compose --env-file .env.gateway --profile integrations up --build --wait --wait-timeout 180
```

Choose unused ports first. The generated `COMPOSE_PROJECT_NAME=janamen-mock-<random>` owns new named volumes and containers. It does not reuse an existing Compose project by default. For an explicit name, pass `--project-name janamen-mock-your-demo`. Never point this command at an existing non-demo project. The generator refuses existing files, invalid project names/ports and `ENVIRONMENT=production`; it does not rotate existing credentials.

`.env.gateway` is ignored by Git and excluded from the Docker build context. It is created exclusively with mode 0600, random database/demo passwords and independent signing keys. Keep it private and reuse it for this demo. Read the demo password in your private editor for interactive sign-in; do not paste credentials into chat, screenshots or evidence. External AI is disabled. Do not use the repository's historical predictable password with a newly generated environment.

Open [the local demo](http://127.0.0.1:18778). This is a local development deployment using HTTP on the private Compose network, not production TLS/mTLS evidence. The gateway has no published host port. Application and PostgreSQL ports bind only to loopback. Gateway schema startup upgrades to v3; the app migration head is `0011_merge_profile_updates`.

## Synthetic identities

The registration smoke provisions these existing, linked demo identities through `app.provision_demo`, refusing to overwrite conflicting accounts or reporting lines:

| Role | Login | Employee code | Scope |
|---|---|---|---|
| Employee | `employee.demo@example.com` | `DEMO-EMP-001` | Own requests/profile/notifications |
| Manager | `manager.demo@example.com` | `DEMO-MGR-001` | Employee above |
| HR | `hr.demo@example.com` | `DEMO-HR-001` | Integration queues, refresh, mapping/recovery |

Base seed identities remain `aruzhan@janapost.kz` (`JP-10428`), `timur@janapost.kz` (`JP-10201`) and `aigerim@janapost.kz`; the generated environment's password applies. The blueprint's `JP-10311` manager was illustrative. Existing repository codes and fixtures are preserved. Automated scope tests use additional existing synthetic employees; no real employee account is created.

## Register once and repeat

```sh
docker compose --env-file .env.gateway exec -T web \
  python -m app.integrations.demo_smoke --scenario happy
docker compose --env-file .env.gateway exec -T web \
  python -m app.integrations.demo_smoke --scenario happy
```

The command uses actual employee/manager/HR bearer sessions against the loopback application. It finds an unused future non-holiday date, creates a stable submission key, submits twice, approves once and waits for MOCK registration. It checks the same business request ID, expected leave debit, separate `Approved`/`REGISTERED` states, MOCK reference, exactly one registration notification and backend privilege denials. It logs out its sessions. The repeat reuses the saved date/key and verifies no second debit. It never deletes requests, resets a database or calls a real vendor.

Use the same scenario for retry/restart proof. A different scenario intentionally creates another synthetic business request. Existing fixture conflicts or insufficient leave fail clearly; use a new isolated project rather than clearing user records. Provisioning is disabled outside non-production demo mode.

For a browser demonstration, sign in separately as the three roles. Submit as employee, approve as assigned manager, then inspect the employee request and the HR integration card. Show `Approved` independently from the MOCK registration badge/reference. Frontend role preview is presentation; employee credentials must receive a denial from privileged routes.

## Gateway outage and recovery

```sh
docker compose --env-file .env.gateway stop gateway
docker compose --env-file .env.gateway exec -T web \
  python -m app.integrations.demo_smoke --scenario outage --expect-pending
docker compose --env-file .env.gateway start gateway
docker compose --env-file .env.gateway exec -T web \
  python -m app.integrations.demo_smoke --scenario outage
```

During the outage, approval persists and the profile loads from local storage. The employee retains approval while integration is pending. After restart the durable worker retries the same key; the command waits up to 90 seconds. It recovers to one reference/notification without another leave debit. If retries have already exhausted, inspect the HR failed queue; use the audited recovery action with an explicit reason. Do not mutate the payload/key or delete accepted jobs to force a result. Known accepted jobs missing from gateway storage require investigation/restoration, not blind resubmission.

In this session the existing worker and web were also recreated during recovery, retaining both database volumes. Both gateway callbacks were delivered. Exact observed IDs/counts are in [runtime evidence](evidence/integration-2026-10-18/runtime-journey.json).

## Security and verification

```sh
.venv/bin/python -m pytest tests/test_gateway_service.py tests/test_integration_hardening.py -q
.venv/bin/python -m pytest tests/test_outbox_processes.py -q
```

The second command requires `TEST_DATABASE_URL` pointing to an explicitly disposable PostgreSQL database; otherwise its two cases skip. Each owns a random schema and drops only that schema. Never configure production/user storage as a test target. The complete suite also covers recovery authorization, mapping, migration preflight, key rotation, raw-body/query signing, nonce persistence, callback rollback and wrong employee/manager scopes. Read [acceptance results](INTEGRATION_ACCEPTANCE_RESULTS.md) for exact executed commands and limitations.

Signed gateway requests share a durable per-key UTC-minute quota, default 600. `429` includes `Retry-After`; invalid signatures receive 401. The gateway health probe also uses this quota. Configure an operationally suitable limit, retain private networking and monitor safe rejection logs. Fixed-window throttling does not replace an edge/network defense.

## Preserve and stop

```sh
docker compose --env-file .env.gateway --profile integrations stop
```

This retains the generated environment and both stores for the next run. Do not use volume deletion, prune, row removal or credential replacement as a repeatability technique. Back up the independent gateway store using the [existing recovery runbook](RECOVERY_AND_OPERATIONS.md) before any intended deployment upgrade.

The verified session used project `janamen-int-20261018`, ports 18778/15448 and a private mode-0600 environment outside the repository at `/tmp/janamen-integration-20261018/private.env`. That project was explicitly created for this work. It is distinct from the older `janamen-qa-check`/`janamen-gateway-check` projects. The browser demo remains available locally; temporary credentials are not committed.

## Real vendor gate

A demo Documentolog/1C account becomes useful after obtaining approved API contracts, synthetic sandbox access, service scopes, authentication/webhook verification, field/leave mappings and network/TLS requirements from the partner. A generic vendor login does not establish these contracts. Real 1C writes, Documentolog signing and production security remain unverified; neither connector reports CONNECTED.
