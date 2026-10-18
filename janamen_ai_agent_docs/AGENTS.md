# Instructions for AI Coding Agents — JanaМен

## Source-of-truth order

1. Actual checked-out repository code/config/tests.
2. `00_CURRENT_PROJECT_STATE.md`, grounded in the user-supplied QA report dated 17 October 2026.
3. `12_QA_REMEDIATION_PLAN.md` and the detailed integration documents in this pack.
4. Vendor/public docs for vendor contract questions, followed by customer-specific API metadata/contracts.

If documents and current code disagree, do not silently pick one: inspect tests and git history if available, explain the difference, preserve safe behavior, and update the documentation to match the implemented decision.

## Mandatory workflow

1. Inspect `git status`, current commit/revision, settings and source before editing.
2. Confirm actual DB target; destructive operations and migrations are allowed only on explicitly selected development/test databases.
3. Establish current test baseline before modifications.
4. Reuse existing models, auth, request service, outbox, gateway, signing helper and snapshot sync. Do not create a parallel architecture for already implemented functionality.
5. Add a regression test before or alongside each behavior change.
6. Verify focused tests, then full applicable checks; report exact results.
7. Update remediation status only after code/test evidence.

## Existing architecture anchors

- App: `app/main.py`, routes/schemas/services under `app/`.
- Static UI: `static/index.html`, `static/js/app.js`, `static/js/i18n.js`, `static/css/style.css`, `static/locales/catalog.json`. No current JS bundler/package.json is reported.
- App DB/migrations: `app/database.py`, `app/models/`, `app/migrate.py`, `migrations/versions/0001..0006`.
- App integration/outbox: `app/integrations/outbox.py`, `app/integrations/signing.py`, `app/integrations/profile_sync.py`.
- Internal gateway: `app/gateway/main.py`, `app/gateway/runtime.py`, `app/gateway/connectors.py`, `app/gateway/models.py`.
- Request/auth/audit/notification: `app/services/request_service.py`, `app/services/auth_service.py`, `app/services/audit_service.py`, `app/services/notification_service.py`.
- AI/knowledge: `app/services/ai_service.py`, `app/services/knowledge_conflicts.py`, `app/integrations/gemini.py`, `knowledge/`, `ml/`.

Read `00_CURRENT_PROJECT_STATE.md` for tested behavior and open findings.

## Non-negotiable security and reliability

- Mock/offline mode is the safe default. No live 1C, Documentolog, or model provider call in routine automated tests.
- Do not replace real project config with the generic variable names in the integration planning docs. Inspect `app/config.py`, gateway config, Compose and the actual `.env.example` first.
- Never invent 1C endpoints, OData entities, HR field meanings, auth methods, payroll/leave write semantics or provider capabilities.
- Preserve employee privacy: stable external IDs only, least privilege, no raw PII or secret values in logs, errors, metrics or fixtures.
- Raw employee free-text questions must not be sent to Gemini. Provider use stays default-off until approved. Approved knowledge can itself carry PII and needs data governance.
- Existing app↔gateway HMAC is an internal machine-auth protocol, not automatic proof of vendor webhook authenticity.
- Preserve HMAC-SHA256 and durable nonce/replay protection; don't invent cryptographic protocols.
- External create operations with unknown outcome must be reconciled before any repeat attempt. Preserve original immutable idempotency keys and payloads.
- All HR replay/remap actions must be authorized, audited and role-scoped. No name-only employee mapping.
- No request `COMPLETED` status from manager approval or document registration alone. Keep approval, integration/registration and official HR processing meaning distinct.
- Do not claim a real 1C or Documentolog connection, real signing or payroll payment unless a customer-specific verified test establishes it.
- Data changes need safe versioned migrations and preflight conflict handling; never silently repair existing business data.

## QA-derived delivery order

See `12_QA_REMEDIATION_PLAN.md`. At minimum preserve the already-fixed P1 AI regressions, then fix initial request idempotency, audited HR recovery/remapping, DB integrity and gateway migrations, modal focus, repeatable smoke tests, CI/operations, and localization. Live integration remains a later gated phase.

## Done means evidence

A task is done only when code and test evidence exist and documentation matches runtime behavior. Final response must list changed files, actual tests/outcomes, unresolved findings, migration/deployment implications, and live-integration blockers.
