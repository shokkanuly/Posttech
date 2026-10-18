# Task for the AI Coding Agent — JanaМен Existing Project and Integrations

You are working in an **existing, tested JanaМен codebase**. The supplied QA report (`reference/qa_report_2026-10-17.pdf`) documents implemented functionality and unresolved issues. Your mission is to preserve that work, fix the highest-priority gaps, and prepare a safe path to real 1C:ЗУП and Documentolog integration. This is not a greenfield rewrite.

## Required reading order

1. `AGENTS.md`
2. `00_CURRENT_PROJECT_STATE.md` — actual repository and integration status
3. `12_QA_REMEDIATION_PLAN.md` — prioritized, evidence-based work
4. `01_PROJECT_BRIEF.md` and `02_ARCHITECTURE.md`
5. `03_1C_ZUP_ADAPTER.md` and `04_DOCUMENTOLOG_ADAPTER.md`
6. `05_DATA_MODEL_AND_MAPPING.md`, `06_INTERNAL_API_CONTRACTS.md`, `07_SYNC_RELIABILITY_RUNBOOK.md`
7. `08_SECURITY_PRIVACY.md`, `09_TEST_PLAN.md`, `10_IMPLEMENTATION_TASKS.md`, `11_OPEN_QUESTIONS.md`
8. `SOURCES.md` and `INTEGRATION_ENV_REFERENCE.md`

## Mission

1. Preserve and extend the existing FastAPI + static HTML/CSS/JavaScript app, current database models/migrations, request workflow, authentication, audit, notifications, outbox, signed internal gateway and profile sync.
2. Fix current QA gaps, starting with duplicate initial request submission, safe HR recovery/remapping, DB constraints/migrations, keyboard dialog focus, and smoke-test repeatability.
3. Continue mock-first integration development. Existing mock Documentolog registration and signed mock HR snapshot flow are already implemented; improve them rather than building a duplicate delivery pipeline.
4. Keep real 1C:ZUP and Documentolog connections disabled until actual contracts, credentials, deployment/security controls, HR semantics and approvals have been verified.
5. Preserve the AI privacy fixes and strengthen policy conflict/data governance without claiming that general semantic conflict detection is solved.

## Mandatory first actions

- Inspect `git status` and current repository revision; preserve all unrelated working-tree changes.
- Read `00_CURRENT_PROJECT_STATE.md` and inspect its code paths directly: `app/main.py`, `app/config.py`, `app/services/request_service.py`, `app/integrations/outbox.py`, `app/integrations/profile_sync.py`, `app/integrations/signing.py`, `app/routers/internal.py`, `app/gateway/main.py`, `app/gateway/runtime.py`, `app/gateway/connectors.py`, `app/models/`, `migrations/`, `static/js/app.js`, tests, Compose and `docs/INTEGRATIONS.md`.
- Run baseline tests/checks on an explicitly selected disposable development database. Never migrate, seed, reset, delete from, or smoke-test an unknown/production database.
- Confirm whether the active runtime image contains the reviewed source. The QA report stated the patched review stack used port 18766 and the pre-existing port 8000 stack was not rebuilt; do not assume those runtimes were identical.
- Write a short gap assessment with evidence and implement the smallest compatible change set.

## Existing functionality you must reuse

- DB-backed bearer sessions, server-side role authority, active-user checks and password hashing.
- Request/manager workflow and transactionally stored event history, in-app notification, audit, balance-related effects and outbox enqueue on approval.
- Durable app outbox, worker claiming, bounded jittered retries, signed internal requests, request/job/idempotency-key matching, callback verification and idempotent result application.
- Internal gateway's persisted async jobs, leases, durable nonce replay protection, mock connector and persistent callback retry/reconciliation.
- Mock employee-code snapshot sync, source/as-of metadata, stale snapshot behavior and HR review queue for unknown mapping/balance conflicts.
- Existing request and document idempotency at later workflow stages.

Do not add a second outbox, new request state machine, competing auth system, alternative UI stack, or parallel model tables unless code inspection proves an existing implementation is unsuitable and you document why first.

## First implementation priorities

1. **Request creation idempotency (P2/F05):** same employee/key/same normalized body returns the original request; same key/different body gives 409; concurrency cannot create duplicates; no duplicated business side effects.
2. **HR recovery and mapping remediation (P2/F04):** HR-authorized, audited mapping decisions and safe replay. Check gateway outcome before retry, preserve immutable idempotency key and payload.
3. **Database invariants/schema lifecycle (P2/F08/F10):** preflight current data, add guarded constraints through migrations, and add a versioned gateway schema-upgrade strategy without losing job/nonce/document data.
4. **UI accessibility (P2/F06):** modal focus trap, inert background, opener focus restore, keyboard regression.
5. **Repeatable safe smoke test (P2/F07):** no hard-coded date collisions; isolated synthetic fixture; running twice succeeds without deleting unrelated user data.
6. **AI governance/consistency (P2/F03/F09):** preserve both fixed P1 regressions; add policy precedence and hostile-source/conflict regressions; never send raw free-text questions to Gemini.
7. **CI/ops/localization (P2/P3/F10/F11):** tracked CI, independent worker tests, backup/restore runbook, multiworker login throttling assessment, mobile checks, locale/provenance fixes.
8. **Vendor live connectors:** only after customer/vendor prerequisites in `11_OPEN_QUESTIONS.md` are closed. The live 1C and Documentolog integrations are not established by the QA report.

## Integration-specific instructions

### 1C:ЗУП

- Current implementation imports signed MOCK employee-code snapshots. This is not a live 1C connector.
- Preserve stable-code matching, existing profile only (no account auto-provisioning), source/as-of metadata, stale-state behavior and HR review for unmatched/ambiguous mappings.
- Do not match by name. Do not invent OData object paths, field names, auth or leave policies.
- Implement actual read-only employee/organization/leave access only after the exact installation and metadata/service contract are confirmed.
- No official 1C writes or payroll payments exist. Keep them disabled until separately approved and tested.

### Documentolog

- Existing flow is a mock registration via internal gateway, not proof of vendor API connection or a real document-signing lifecycle.
- Preserve the existing HMAC-SHA256 request/callback protocol between the app and the internal gateway, durable nonce replay protection, async job handling and safe callback result application.
- This internal HMAC must not be misrepresented as authentication of vendor-originated webhooks.
- No real Documentolog submit is allowed until vendor contract, auth, sender/signing requirements, webhook authenticity, TLS, idempotency/status reconciliation, privacy, and approvals are verified.
- Never blindly repeat a non-idempotent remote create operation after an ambiguous timeout. Reconcile by supported provider lookup or require documented manual resolution.

## AI/knowledge constraints

- The two P1 regressions listed in `00_CURRENT_PROJECT_STATE.md` are already fixed in the reviewed source. Preserve the tests.
- Raw user questions must remain local; only approved source material necessary for an approved quote-selection flow may cross the provider boundary.
- Provider calls default off; operator configuration alone is not proof that corporate/legal approval exists.
- Approved knowledge can itself contain sensitive information. Govern source ingestion and provider transmission separately.
- Numeric conflict handling is conservative and literal; do not claim comprehensive semantic contradiction resolution.

## Required work method

For each finding: reproduce or inspect the current behavior; add a failing regression test when feasible; implement a minimal patch; run focused tests; run the relevant full checks; update code docs and `12_QA_REMEDIATION_PLAN.md` with evidence. Do not mark items complete just by changing prose. Keep test data synthetic. Do not use network/live credentials in normal tests.

## Final report requirements

Return:

- files changed and why;
- tests/commands run with actual outcomes;
- the original QA findings fixed, still open, or not rechecked;
- any migrations and compatibility/recovery implications;
- whether the running container was rebuilt and which environment was tested;
- capabilities demonstrated in MOCK mode vs real vendor connection status;
- all blockers before production/live mode.

Never report production readiness if external data governance, real vendor integrations, mTLS/deployment verification, backups/restore, mobile/accessibility, and other material release gates remain unverified.
