# JanaМен — AI Agent Project and Integration Documentation

> Repository update, 18 October 2026: this pack contains the historical QA baseline. The existing fix-plan work and integration with the latest main branch are recorded in [13_REPOSITORY_INTEGRATION_STATUS.md](13_REPOSITORY_INTEGRATION_STATUS.md). Read that status before treating the tasks below as unimplemented.

This pack combines the initial integration specifications with the supplied **JanaМен full-project QA report dated 17 October 2026**. It is designed as repo context for a coding agent working on the existing application.

## Start here

1. [`TASK_FOR_AGENT.md`](TASK_FOR_AGENT.md) — exact assignment and implementation order.
2. [`AGENTS.md`](AGENTS.md) — development, safety and evidence rules.
3. [`00_CURRENT_PROJECT_STATE.md`](00_CURRENT_PROJECT_STATE.md) — what the app already contains, what was tested, and actual 1C/Documentolog status.
4. [`12_QA_REMEDIATION_PLAN.md`](12_QA_REMEDIATION_PLAN.md) — prioritized tasks based on the QA findings.
5. [`01_PROJECT_BRIEF.md`](01_PROJECT_BRIEF.md) and [`02_ARCHITECTURE.md`](02_ARCHITECTURE.md).
6. [`03_1C_ZUP_ADAPTER.md`](03_1C_ZUP_ADAPTER.md) and [`04_DOCUMENTOLOG_ADAPTER.md`](04_DOCUMENTOLOG_ADAPTER.md).
7. [`05_DATA_MODEL_AND_MAPPING.md`](05_DATA_MODEL_AND_MAPPING.md), [`06_INTERNAL_API_CONTRACTS.md`](06_INTERNAL_API_CONTRACTS.md), [`07_SYNC_RELIABILITY_RUNBOOK.md`](07_SYNC_RELIABILITY_RUNBOOK.md).
8. [`08_SECURITY_PRIVACY.md`](08_SECURITY_PRIVACY.md), [`09_TEST_PLAN.md`](09_TEST_PLAN.md), [`10_IMPLEMENTATION_TASKS.md`](10_IMPLEMENTATION_TASKS.md), [`11_OPEN_QUESTIONS.md`](11_OPEN_QUESTIONS.md).
9. [`SOURCES.md`](SOURCES.md) and [`INTEGRATION_ENV_REFERENCE.md`](INTEGRATION_ENV_REFERENCE.md).
10. Full supplied report: [`reference/qa_report_2026-10-17.pdf`](reference/qa_report_2026-10-17.pdf).

## Critical distinction: existing work vs planned work

**Existing and tested locally:** FastAPI app, static HTML/CSS/JS UI, DB-backed bearer auth, request and manager workflow, notification/audit/event writes, versioned app migrations 0001–0006, app-side transactional outbox, HMAC-signed internal gateway, durable mock document jobs, signed callbacks and reconciliation, mock employee-code snapshot sync, offline/source-grounded AI path and extensive tests.

**Not established as live:** connection to real 1C:ЗУП, connection to real Documentolog, real document-signing lifecycle, official 1C write-back/payroll payment, production inbound mTLS, live Gemini use, production backup/restore, HA/capacity and mobile accessibility.

Do not rebuild existing pieces because a planning doc describes them as a target. Inspect source and extend current paths.

## QA baseline

Report status: **NEEDS WORK**. Checklist summary: 140 PASS, 2 FAIL, 17 PARTIAL, 2 NOT VERIFIED, 1 NOT APPLICABLE, 0 BLOCKED. Reported full suite: 400 tests passed on SQLite and 400 on PostgreSQL 17 (one warning in each run). These are historical results; rerun on the current checkout.

Highest-priority fixes: initial submission idempotency for duplicate advance requests, authorized audited HR recovery/remapping, DB integrity/gateway schema lifecycle, keyboard modal focus, repeatable smoke testing, data governance/AI conflict coverage, CI/operations and localization.

## Environment configuration caution

`INTEGRATION_ENV_REFERENCE.md` is vocabulary only. **Do not overwrite the actual project's `.env.example`** with the generic placeholder values from an earlier plan. Inspect the current config and reuse its names and validation.

## Live integration gates

- 1C deployment/configuration, service contract, auth, object metadata and leave policy semantics are unknown. Current HR sync is mock snapshot based.
- Documentolog is currently represented by an internal mock registration gateway. The current HMAC authenticates app↔gateway calls and callbacks; it does not automatically authenticate vendor-originated webhooks.
- Only enable real adapters after vendor/customer contract tests, data governance approval, TLS/mTLS, credentials, idempotency/reconciliation and support runbooks are verified.
