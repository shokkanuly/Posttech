# JanaМен QA test results — 17 October 2026

Overall project readiness: **NEEDS WORK**. Final full Python suites: **400 passed on SQLite and 400 passed on PostgreSQL 17**, each with 1 Starlette/httpx deprecation warning; no failed/skipped tests in either full run. **5/5** frontend locale tests pass. Counts are repeated runs of the same suite, not 800 unique tests.

## Environments and safety

- Branch `codex/project-qa`, based on `1ce82f3`; Python 3.14 local virtualenv. No new dependency or destructive application migration was added.
- SQLite app tests own fresh databases; PostgreSQL application tests use fresh random schemas on the pre-existing disposable gateway-check PostgreSQL 17 service. Only the schema created by a test is removed. Gateway persistence tests use their own temporary SQLite stores, matching the MOCK deployment.
- New live HTTP/browser checks use isolated Compose project `janamen-qa-check`: app `http://127.0.0.1:18766`, PostgreSQL loopback 15440, private generated env outside Git. Original user stack on 8000 and its data were untouched.
- The original port8000 stack retains its earlier image. Only the QA stack was rebuilt with the fixes; saving source to GitHub does not update an already-running image.
- Gemini tests intercept provider HTTP with synthetic data and fake keys. **No live Gemini, 1C, Documentolog, email/push or production system was called.** OSV received package names/versions only.

## Executed commands

Commands below were executed from the repository root. `TEST_DATABASE_URL=<private disposable PostgreSQL DSN>` is intentionally redacted; the actual value was loaded privately, not printed. Output files include observed counts and important failures. Saved text outputs have trailing whitespace/final blank lines normalized; result content is retained and known secrets are redacted.

| Run | Exact command (private DSN redacted) | Exit | Evidence |
|---|---|---:|---|
| collection | `.venv/bin/python -m pytest --collect-only -q` | 0 | [collection.txt](docs/evidence/qa-2026-10-17/collection.txt) |
| dependency-audit | `.venv/bin/python dependency_audit.py --requirements requirements-dev.txt --requirements requirements-ml.txt --output docs/evidence/qa-2026-10-17/dependency-advisories.json` | 0 | [dependency-audit.txt](docs/evidence/qa-2026-10-17/dependency-audit.txt) |
| docker-build-start | `docker compose --env-file /tmp/janamen-qa-check.env -p janamen-qa-check --profile integrations up --build -d` | 0 | [docker-build-start.txt](docs/evidence/qa-2026-10-17/docker-build-start.txt) |
| final-docker-build | `docker compose --env-file /tmp/janamen-qa-check.env -p janamen-qa-check --profile integrations up --build -d` | 0 | [final-docker-build.txt](docs/evidence/qa-2026-10-17/final-docker-build.txt) |
| final-format | `.venv/bin/python -m ruff format --check app tests migrations smoke_test.py dependency_audit.py` | 0 | [final-format.txt](docs/evidence/qa-2026-10-17/final-format.txt) |
| final-mypy | `.venv/bin/python -m mypy app` | 0 | [final-mypy.txt](docs/evidence/qa-2026-10-17/final-mypy.txt) |
| final-postgresql | `TEST_DATABASE_URL=<private disposable PostgreSQL DSN> .venv/bin/python -m pytest -q` | 0 | [final-postgresql.txt](docs/evidence/qa-2026-10-17/final-postgresql.txt) |
| final-ruff | `.venv/bin/python -m ruff check app tests migrations smoke_test.py dependency_audit.py` | 0 | [final-ruff.txt](docs/evidence/qa-2026-10-17/final-ruff.txt) |
| final-safe-probes | `env PYTHONPATH=. .venv/bin/python docs/evidence/qa-2026-10-17/safe_probes.py` | 0 | [final-safe-probes.txt](docs/evidence/qa-2026-10-17/final-safe-probes.txt) |
| final-sqlite | `.venv/bin/python -m pytest -q` | 0 | [final-sqlite.txt](docs/evidence/qa-2026-10-17/final-sqlite.txt) |
| format | `.venv/bin/python -m ruff format --check app tests migrations smoke_test.py dependency_audit.py` | 0 | [format.txt](docs/evidence/qa-2026-10-17/format.txt) |
| frontend | `node --test tests/frontend_localization.test.cjs` | 0 | [frontend.txt](docs/evidence/qa-2026-10-17/frontend.txt) |
| full-postgresql | `TEST_DATABASE_URL=<private disposable PostgreSQL DSN> .venv/bin/python -m pytest -q` | 0 | [full-postgresql.txt](docs/evidence/qa-2026-10-17/full-postgresql.txt) |
| full-sqlite | `.venv/bin/python -m pytest -q` | 0 | [full-sqlite.txt](docs/evidence/qa-2026-10-17/full-sqlite.txt) |
| javascript | `node --check static/js/app.js` | 0 | [javascript.txt](docs/evidence/qa-2026-10-17/javascript.txt) |
| live-outage-recovery | `.venv/bin/python /tmp/janamen-qa-live.py` | 0 | [live-outage-recovery.txt](docs/evidence/qa-2026-10-17/live-outage-recovery.txt) |
| mypy | `.venv/bin/python -m mypy app` | 0 | [mypy.txt](docs/evidence/qa-2026-10-17/mypy.txt) |
| pip-check | `.venv/bin/python -m pip check` | 0 | [pip-check.txt](docs/evidence/qa-2026-10-17/pip-check.txt) |
| privacy-and-ai-final | `.venv/bin/python -m pytest -q tests/test_ai_gemini.py tests/test_ai.py tests/test_qa_acceptance.py tests/test_knowledge_files_and_ml.py` | 0 | [privacy-and-ai-final.txt](docs/evidence/qa-2026-10-17/privacy-and-ai-final.txt) |
| privacy-regression-before | `.venv/bin/python -m pytest -q tests/test_ai_gemini.py -k employee_free_text` | 1 | [privacy-regression-before.txt](docs/evidence/qa-2026-10-17/privacy-regression-before.txt) |
| ruff | `.venv/bin/python -m ruff check app tests migrations smoke_test.py dependency_audit.py` | 0 | [ruff.txt](docs/evidence/qa-2026-10-17/ruff.txt) |
| smoke-first | `env JANAMEN_BASE_URL=http://127.0.0.1:18766 .venv/bin/python smoke_test.py` | 0 | [smoke-first.txt](docs/evidence/qa-2026-10-17/smoke-first.txt) |
| smoke-repeat | `env JANAMEN_BASE_URL=http://127.0.0.1:18766 .venv/bin/python smoke_test.py` | 1 | [smoke-repeat.txt](docs/evidence/qa-2026-10-17/smoke-repeat.txt) |
| targeted | `.venv/bin/python -m pytest -q tests/test_qa_acceptance.py tests/test_ai.py tests/test_ai_gemini.py tests/test_knowledge_files_and_ml.py` | 0 | [targeted.txt](docs/evidence/qa-2026-10-17/targeted.txt) |
| transport-logging-final | `.venv/bin/python -m pytest -q tests/test_merge_regressions.py -k gemini_error_logs` | 0 | [transport-logging-final.txt](docs/evidence/qa-2026-10-17/transport-logging-final.txt) |

## Observed failures and corrections

- Initial new QA test collection failed (exit 2) because I used the wrong Gemini module import. Corrected to the existing module import before testing behavior; [regression-collection-error.txt](docs/evidence/qa-2026-10-17/regression-collection-error.txt). This was a test authoring error.
- New conflict regression before fix: **6 failed, 5 passed** (exit 1). EN/RU/KK, with and without provider selection, returned grounded instead of fallback. [regression-before.txt](docs/evidence/qa-2026-10-17/regression-before.txt). After the numeric guard, the focused suite passed 75 tests.
- Provider HTTP privacy regressions before fix: **3 failed, 13 deselected** (exit 1): the complete appended synthetic identifiers were in the outbound JSON. [privacy-regression-before.txt](docs/evidence/qa-2026-10-17/privacy-regression-before.txt). After removing raw-query transport and adding approval gating, the focused suite passed 79 tests.
- An early PostgreSQL runner invocation placed --postgres after an argparse remainder parameter and failed before pytest launched. Corrected option order; no database test result is attributed to that failed launch.
- First live 10-step smoke **passed** (exit 0). Immediate rerun **failed** (exit 1) on the reused fixed vacation dates with 409. This remains an open script defect; it is not counted as a backend test failure. [smoke-repeat.txt](docs/evidence/qa-2026-10-17/smoke-repeat.txt).
- The extra evidence probe initially failed its own Ruff check with 3 import-format issues; Ruff fixed those imports. The saved probe was rerun successfully; application logic was unaffected.

## Runtime checks beyond automated suites

- Actual stopped gateway → HTTP 200 approval/Approved, pending 1, profile 200 → recovery → REGISTERED/MOCK with exactly 1 registration notice: [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json). Recovery took seconds; the real multi-hour retry schedule was tested with due-time advancement, not elapsed waiting.
- Final Docker images rebuilt and all 4 services run; DB/web/gateway have healthy probes, worker has no configured healthcheck. Gateway has no published host port and the integration network is internal: [docker-health.json](docs/evidence/qa-2026-10-17/docker-health.json).
- Fresh-disposable SQLite direct-write probes: foreign key and unique employee-code violations rejected; negative balances, reversed dates and unknown statuses accepted by direct SQL. Identical advance submission creates 2 distinct rows. [extra-probes.json](docs/evidence/qa-2026-10-17/extra-probes.json). These observations identify gaps; probe exit 0 means the observations completed, not that the behavior is acceptable. Reproduce with `PYTHONPATH=. .venv/bin/python docs/evidence/qa-2026-10-17/safe_probes.py`.
- Course progress read after the QA process rebuild remained the same across HTTP logout/re-login: [relogin-persistence.json](docs/evidence/qa-2026-10-17/relogin-persistence.json).
- Desktop browser: six employee navigation pages, manager Team, HR Administration, source citation, read-all action, profile MOCK/as-of/read-only, real integration card and HR refresh inspected. Tab escapes an open request modal; reload returns to login. [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json). Browser checks are manual through UI automation, not a complete browser test suite.

## Not executed / not established

- No frontend package manager lint/build command or bundler is configured. JavaScript syntax and locale tests were run; a frontend build is NOT APPLICABLE.
- No mobile-device/viewport run, exhaustive action-button/browser error-state suite, separate simultaneous app-worker process test, production query-plan/load/HA test, backup/restore test or production TLS/mTLS handshake.
- No live provider/model availability test or organization-approved external knowledge data policy. No live enterprise connector, official HR calendar/accrual policy or payment/signature test.
- No CI workflow is configured; all results here were executed locally. Dependency advisory matching found0 affected packages among 50 exact pins on this run; this is not a guarantee against unknown vulnerabilities.
