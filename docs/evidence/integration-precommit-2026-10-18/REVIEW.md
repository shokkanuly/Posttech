# Five-check precommit verification — 18 October 2026

Source baseline: `860e07c0196f42ac83a39d62137067e4f24d91b8`, branch `codex/integration-blueprint-hardening`. This follow-up implements the requested health-quota isolation and documentation cleanup, verifies the existing recovery backend, and records fresh executions before committing. These are local MOCK results, not production or real-vendor certification.

## 1. Git and private-data checks — PASS

`git status --short`, `git check-ignore -v .env.gateway`, `git ls-files .env.gateway` and `git diff --check` were executed. `.gitignore` matches `.env.gateway`; no such file is tracked. The default path does not currently exist in this checkout. Actual generated files are mode-0600 private files in the session directory outside Git. Docker's context also excludes `.env.gateway`. See [git-safety.json](git-safety.json).

The staged patch and the original and new `runtime-journey.json` were checked for known generated/private provider values, bearer/JWT tokens and selected secret formats. Runtime records contain synthetic request/reference IDs, counters, schema/source hashes and session deployment metadata; no passwords, signing keys, bearer tokens, database credentials or employee free text. [The final scan](secret-scan.json) records scope and result. Raw diagnostics stay outside Git; copied failure diagnostics redact bearer/JWT strings and known private values.

The broader scan found nine synthetic session-token occurrences in two already-tracked historical QA failure logs. Those current files are now redacted. Earlier Git commits retain the old synthetic diagnostics; shared history was not rewritten or force-pushed. Two exact intentionally invalid test strings are classified as fixtures, not credentials. The final scan checks staged added content and the entire current tree, and separately counts removed historical token lines.

## 2. Recovery/remapping backend — PASS for MOCK

- `POST /api/v1/admin/integrations/queue/{task_id}/retry` depends on `require_role(UserRole.HR_ADMIN)` in `app/routers/admin.py`. `queue_retry` validates state/version, writes durable retry intent and `INTEGRATION_RETRY_REQUESTED` with the authenticated actor and reason in the same transaction. The worker reconciles first, keeps the original key/payload and generation, and refuses blind replay of known missing accepted jobs.
- `POST /api/v1/admin/integrations/reviews/{employee_code}/resolve` has the same HR dependency. It checks the observed review version, obtains a fresh signed snapshot, maps an existing account and writes `INTEGRATION_REVIEW_RESOLVED` with actor/reason. It does not create accounts or match by name.
- Strengthened tests verify persisted actor/reason/counter audit, unchanged document key/payload after recovery, anonymous/employee/manager mapping denial, stale/duplicate commands and one registration/notice. Fresh PostgreSQL recovery suite: **12 passed**. See [recovery.txt](recovery.txt) and [recovery.xml](recovery.xml).

QA073, QA077, QA110 and QA127 now point to current evidence. Their update changes checklist totals to PASS144 / FAIL1 / PARTIAL14 / NOT VERIFIED2 / NOT APPLICABLE1. Other entries retain their documented scope; no new browser/mobile pass is claimed. FIX_PLAN records the verified MOCK recovery and remaining production gates.

## 3. Independent health quota — PASS

Signed `GET /health` now has `GATEWAY_HEALTH_REQUESTS_PER_MINUTE`, default60, independent from the default600 business quota. Both use durable per-key fixed UTC-minute buckets and atomic nonce consumption. The server selects the health budget from the exact method/path, not a client-selected flag. Health remains private, signed and replay-protected; other routes/methods cannot borrow its capacity.

Existing v3 business key hashes and counters are preserved; health uses additional namespaced rows in the same table. No data reset, new column or schema revision is needed. Tests cover both quotas under concurrency, restart, replay, exhaustion in both directions and method/route isolation. A running-container probe sent two signed health requests and verified the business quota was unchanged. See [runtime-journey.json](runtime-journey.json).

Core source/runtime head: **`0011_merge_profile_updates`**. Gateway source/runtime schema: **v3**. Captured runtime hashes match the checkout's gateway main/runtime/config sources.

## 4. Executed verification — PASS

| Command / scenario | Observed result |
|---|---|
| `.venv/bin/python -m pytest tests/test_gateway_service.py tests/test_integration_hardening.py -q` plus JUnit output | **21 passed**, exit0 — [log](gateway.txt), [JUnit](gateway.xml) |
| `.venv/bin/python -m pytest tests/test_outbox_processes.py -q` plus JUnit, private `TEST_DATABASE_URL` | **2 passed**, exit0 — [log](workers.txt), [JUnit](workers.xml) |
| `.venv/bin/python -m pytest tests/test_fix_plan.py -q` plus JUnit, same disposable test target | **12 passed**, exit0 — [log](recovery.txt) |
| Full SQLite suite | **495 passed, 2 PostgreSQL-only skips**, exit0 — [log](full-sqlite.txt), [JUnit](full-sqlite.xml) |
| Full PostgreSQL17 suite | **497 passed**, exit0 — [log](full-postgresql.txt), [JUnit](full-postgresql.xml) |
| Ruff, mypy, pip consistency, frontend locale tests and JavaScript syntax | **PASS**; mypy84 app sources, 5 locale tests |
| Fresh happy-path first and repeat | **PASS twice**; same request/reference, no second leave debit — [first](smoke-first.txt), [repeat](smoke-repeat.txt) |
| Stop gateway, approve while unavailable, restart and recover | **PASS**; Approved/PENDING becomes REGISTERED with one document/notice — [pending](outage-pending.txt), [recovered](outage-recovered.txt) |
| Read-only core/gateway counts and live health quota proof | **PASS**; two total demo requests, two documents, one registration audit/notice per request, callbacks delivered, quota unchanged by health — [runtime record](runtime-journey.json) |

Every suite retains the existing Starlette/httpx deprecation warning. No dependency was added or authentication bypassed.

The worker test target is a **new dedicated PostgreSQL17 container**, `janamen-disposable-check-b5930545`, database `janamen_verify`, loopback port63407, with tmpfs storage and no pre-existing database/volume mounted. Test credentials are generated privately. It is separate from the synthetic demo's PostgreSQL service and all pre-existing local projects. Each fixture owns a random schema. See [postgres-target.json](postgres-target.json); no DSN or password is committed.

The fresh synthetic demo is project `janamen-mock-precommit-a0210a70`, web port63490, PostgreSQL port63491. Its private environment path and exact observed synthetic IDs are in [demo-target.json](demo-target.json) and the runtime record. These are observations from this session, not instructions or future availability promises. [Cleanup evidence](cleanup.json) records the final owned-service disposition.

Two new audit assertions initially used the wrong current-user DTO and JSON-text storage shape (2 failed/12 passed). They were corrected to use `user.id` and decoded audit details, then the targeted and complete suites passed. Earlier broad runs were interrupted/superseded and are not counted as passing. A runtime counting helper initially assumed freshly provisioned accounts already had an imported snapshot; the helper now handles their documented 24-day synthetic provisioner baseline until sync. The actual smoke's before/after debit assertions already passed. These corrections did not alter application recovery state or loosen authorization.

## 5. Permanent instructions versus session evidence — PASS

The runbook now uses selected-port variables and contains repeatable instructions. Exact project names, ports, temporary file paths, request IDs and execution results live here. The previous implementation report and INT matrix were preserved under their original session's evidence directory; permanent entry points link to session records. A recorded healthy service does not guarantee a running browser demo for the next developer.

Changed source/config: `.env.example`, `docker-compose.yml`, `app/gateway/config.py`, `main.py`, `runtime.py`; tests: `test_integration_hardening.py`, `test_fix_plan.py`; documentation: QA_CHECKLIST, FIX_PLAN, integration overview/acceptance/runbook/contract/schema and repository status. Evidence includes commands, sanitized logs/JUnit, target metadata, runtime counts, source review and final secret scan; two old QA logs have synthetic tokens redacted.

Review scope: primary-agent source/diff review and actually executed local tests. Fixed-window boundary bursts, production TLS/mTLS/key operations, shared user-login throttling, monitoring/load/HA/restore objectives, live partner contracts and fresh browser/mobile checks remain separate gates. CI remains an inactive template. No independent external security certification is claimed.
