# Integration implementation — 18 October 2026

This is a historical session record. Observed services, ports and availability are not guaranteed for future runs.

The existing MOCK vertical slice is preserved and verified. This follow-up adds durable gateway admission limits, generated private demo credentials, a repeatable registration/outage command and independent PostgreSQL application-worker evidence. It does not implement undocumented vendor APIs.

## Baseline and source references

Started from clean branch `codex/fix-plan`, commit `eafbaa7c73fe639ad14f1d0131ff5cf4bf19d872`; changes are saved on `codex/integration-blueprint-hardening`. The supplied 17 October 400-test QA report is older than the current repository. The merged-source report already documented 484 tests, request submission keys, audited recovery/remapping, safe constraints, repeatable smoke and gateway v2 migrations. Those features were inspected and tested, not rebuilt.

Inspected the local `janamen_ai_agent_docs` pack, blueprint Markdown/DOCX and pasted agent prompt as design/context documents. The user's request and repository state determine the work. A byte-identical Markdown copy is saved at [reference/integration_blueprint_2026-10-18.md](../../../janamen_ai_agent_docs/reference/integration_blueprint_2026-10-18.md); source checksums are in [provenance evidence](source-provenance.json). Its proposed field names/receipt examples are not a mandate to break existing canonical contracts.

Graph discovery and source inspection confirmed the application service, signing helper, outbox, profile sync, recovery, admin/internal routes, gateway models/config/runtime/connectors, migrations, Compose and integration tests. Runtime: Python3.14.0, Node24.14.1, PostgreSQL17. Core head stays **`0011_merge_profile_updates`**. Initial tracked worktree was clean. Existing local settings select Gemini and no gateway; those private settings were left unchanged. Tests explicitly select offline AI, and the new isolated runtime selects `grounded_knowledge` with Gemini disabled. No live provider was contacted.

## Delivered behavior and changed files

| Files | Result |
|---|---|
| `app/gateway/config.py`, `models.py`, `runtime.py`, `main.py` | Per verified key ID, fixed UTC-minute admission quota, default600. Atomic database upsert and nonce consumption prevent concurrent over-admission; counters survive restarts. Rejections preserve no business effects, return safe429/Retry-After/no-store, and do not grow the nonce store. Authentication failure logs contain only category/status. Existing HMAC bytes and keys remain unchanged |
| `app/gateway/migrate.py` | Additive independent gateway **v3** table for quota state. v1/v2 job/reference/callback/nonce retention and future-version refusal remain tested |
| `app/gateway/configure_mock.py`, `docker-compose.yml`, `.env.example` | Random demo password, private exclusive env creation, unique generated Compose project, explicit offline AI, small synthetic seed and configurable gateway quota. Invalid ports/project names and production invocation are refused. Existing credentials/files are never overwritten |
| `app/integrations/demo_smoke.py` | Non-production local-only HTTP journey using real synthetic bearer sessions. Stable submission key, fresh unused date, repeated submit/approval, single debit, one MOCK reference/registration notice, privilege denials, session logout and explicit gateway-offline mode. No row deletion or reset |
| `tests/test_integration_hardening.py` | OpenSSL-derived golden vectors; exact skew boundaries; durable/concurrent quota, replay rollback and key isolation; v2 upgrade; input/log redaction/size rejection; private env/no overwrite/production guard; repeated pending smoke; callback audit fault rollback and one set of terminal effects |
| `tests/test_outbox_processes.py` | Two separate application processes prove PostgreSQL SKIP LOCKED; a process crash after committed gateway acceptance but before local ack proves stable-key recovery to one job/document/notice. The transport seam uses a real persisted local gateway runtime; signed HTTP is separately exercised |
| `docs/INTEGRATIONS.md`, `gateway-openapi.json`, `RECOVERY_AND_OPERATIONS.md` | Updated actual contract, admission semantics, internal schema snapshot, v3 deployment/rollback boundary and generated credential instructions |
| `docs/ci/quality.yml`, `docs/ci/README.md` | Inactive CI template additionally builds an isolated MOCK deployment and runs the integration smoke twice. Existing PostgreSQL matrix automatically includes the separate-process cases. No active workflow/permission was changed |
| `README.md`, `janamen_ai_agent_docs/13_REPOSITORY_INTEGRATION_STATUS.md`, source reference and the three `INTEGRATION_*` documents | Link current implementation, all 30 acceptance statuses, repeatable runbook and limitations; retain historical QA provenance |
| `docs/evidence/integration-2026-10-18/` | Exact command/exits, baseline/final logs and JUnit, runtime counts/security probes, environment summary, scoped secret/log scan and review notes. Credentials, raw runtime logs, databases and private environment files stay outside Git |

## Architecture retained

Browser → application bearer auth and database-owned scopes → request transaction/history/audit/notifications → immutable outbox → separate signed worker → private gateway → persisted mock registration → signed callback or reconciliation. Approval stays `Approved` during external failure. Registration status remains separate. Employee snapshots are local read-only projections with source/as-of/freshness; unknown mappings enter HR review and do not create accounts. Profile contact approvals remain local and create no vendor document task.

Submission keys remain employee-scoped and body-bound. Recovery retains immutable payload/key, requires HR authorization/reason/version checks and reconciles the gateway before replay. A known accepted job absent from the store is an incident. Callback generation checks and atomic terminal effects remain intact. The gateway retains existing PENDING/PROCESSING receipt states and `:v1` event keys; no incompatible illustrative `schema_version` field was introduced.

## Actual verification

All commands below exited **0**, except the two corrected invocation mistakes noted afterward. Commands, environment selection and output files are in [commands.json](commands.json).

| Execution | Result | Evidence |
|---|---|---|
| Existing focused gateway/integration/reliability/fix/merge tests | **94 passed** | [baseline-targeted.txt](baseline-targeted.txt) |
| Existing full SQLite / PostgreSQL17 suites | **484 passed each** | [SQLite](baseline-sqlite.txt), [PostgreSQL](baseline-postgresql.txt) |
| Final full SQLite suite | **493 passed, 2 skipped**, one existing deprecation warning | [log](final-sqlite.txt), [JUnit](final-sqlite.xml) |
| Final full PostgreSQL17 suite | **495 passed**, one existing deprecation warning | [log](final-postgresql.txt), [JUnit](final-postgresql.xml) |
| Ruff / changed-file formatting / mypy / pip check / JS syntax | **PASS**, mypy84 application sources | [quality logs](commands.json) |
| Frontend locale suite | **5 passed** | [frontend.txt](frontend.txt) |
| Docker build/start and health | Web/db/gateway healthy; worker running; no gateway published port | [runtime record](runtime-journey.json) |
| New HTTP registration smoke first/repeat | **PASS twice**, same request/reference, no second debit/notice | [first](smoke-first.txt), [repeat](smoke-repeat.txt) |
| Actual gateway stop, approval, service restart and recovery | **PASS**; approval retained, original key registered once | [pending](outage-pending.txt), [recovered](outage-recovered.txt) |
| Existing ten-step application API smoke | **PASS twice** | [first](full-smoke-first.txt), [repeat](full-smoke-repeat.txt) |
| Running gateway signature/schema/size probes | Expected200/401/422/413; no added jobs; no private input echo | [runtime-security.json](runtime-security.json) |
| Scoped nonignored-file and container-log scan | No known generated private values or selected secret/payload markers found | [scan](log-and-secret-scan.json) |

The two SQLite skips are intentionally PostgreSQL-only application worker tests; the same cases pass on PostgreSQL. Test fixtures use disposable unique schemas; no existing schema or volume was reset. Gateway migration tests cover fresh install, unversioned v1, v2 retention and repeated upgrade. Callback fault injection confirms no partial reference/history/notice on audit failure and exactly one set after retry and duplicate delivery.

Two command errors were corrected: the first targeted command named nonexistent `tests/test_integrations.py` (exit4); it was replaced by the actual gateway test files and passed94. Attempting to run the root `smoke_test.py` inside the image failed because Docker does not copy that root helper (exit2). It then ran twice successfully from the host against the isolated port using private credentials. Neither invocation error is reported as a test pass.

The isolated project is **`janamen-int-20261018`**, web `127.0.0.1:18778`, PostgreSQL `127.0.0.1:15448`, with separate new app/gateway volumes and an external mode-0600 private environment. Older `janamen-qa-check` and `janamen-gateway-check` projects were not rebuilt, stopped or reset. The new synthetic demo is left running for review. [Environment metadata](environment.json) contains no credential values.

## Acceptance and remaining gates

[INT-001 through INT-030](acceptance-results.md): **29 PASS, one PARTIAL**. INT-029 is partial because backend mode truth is proven but no new browser/mobile check was performed this session. Existing frontend locale tests pass; historical UI screenshots remain historical. The source and UI architecture were not replaced.

The gateway quota is fixed-window, permits boundary bursts and allocates a separate budget per rotating key ID. It includes signed health checks, so production sizing/monitoring is still required. The new table stores a hash of a public key identifier, not signing secrets. Quota limits apply to the gateway; callback ingress relies on existing machine authentication/body limits/private deployment, and user-login throttling still needs a shared production control. No exhaustive security certification is claimed.

Back up the gateway before deploying v3; start one migrator/gateway before additional workers. Older versions reject a v3 store. Core application migration head does not change. Do not delete nonce/idempotency history to roll back. Production TLS/mTLS, key/certificate operations, HA/capacity, monitoring, legal/data governance and production PostgreSQL restore objectives remain unverified.

CI remains an **inactive template** because prior GitHub authentication lacked workflow-publication scope. It now includes local Docker smoke/build coverage, but no Actions execution, continuous vulnerability scan or general CI secret scanner is claimed. Local dependency consistency and scoped secret checks actually ran. No dependency was added.

Real 1C:ЗУП and Documentolog require partner-approved sandbox contracts/access, exact field/leave semantics, service scopes, supported authentication/webhook/signature behavior and network/TLS requirements. Creating demo vendor accounts is useful once these are available; it is not needed for the completed MOCK work. No CONNECTED label, real document/signature or production readiness is claimed.

## Saving work

Source, documentation, tests and review evidence are saved locally and pushed on [codex/integration-blueprint-hardening](https://github.com/shokkanuly/Posttech/tree/codex/integration-blueprint-hardening). The final chat reports the actual commit and verified remote result. Runtime stores, secrets and private logs remain ignored/outside the repository.
