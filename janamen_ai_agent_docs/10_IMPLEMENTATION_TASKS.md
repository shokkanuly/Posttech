# 10 — Implementation Backlog Based on Existing Code

This backlog replaces the earlier greenfield estimate. Existing domain, authentication, outbox, gateway and mock sync functionality already exists. Focus on gaps and on preparing, but not prematurely enabling, live adapters.

## Phase 0 — Baseline and repository safety

- [ ] Read `00_CURRENT_PROJECT_STATE.md`, `12_QA_REMEDIATION_PLAN.md`, and the attached reference PDF.
- [ ] Inspect the live checkout, `git status`, source paths, config and migrations.
- [ ] Confirm DB target and current running image revision; QA reports an older existing app image on port 8000 relative to the patched review stack on port 18766.
- [ ] Run baseline Python/frontend checks against an explicitly selected disposable/test database.
- [ ] Confirm all live integrations/providers are still off; inspect existing `.env.example` rather than replacing it with placeholder variables.

**Exit:** current source and test state are recorded; no user data or runtime state is altered unintentionally.

## Phase 1 — Close request-submission duplication (P2 / FAIL)

- [ ] Add employee-scoped idempotency to initial request creation.
- [ ] Same key + same canonical body returns original request; same key + changed body returns 409.
- [ ] Add DB uniqueness and safe concurrency handling.
- [ ] Ensure browser retries reuse the same key.
- [ ] Test no duplicate balance, history, notification, audit or outbox effects.

## Phase 2 — Audited HR recovery/remapping (P2 / PARTIAL)

- [ ] Extend current HR review interface/services for explicit mapping resolution using stable external IDs.
- [ ] Add HR-only job replay/remediation operation using existing authorization, audit and outbox/gateway state.
- [ ] Before any replay, reconcile remote gateway status/document reference. Keep the original key and payload.
- [ ] Add tests for unauthorized users, duplicate operation, ambiguous mapping, already registered job, stale mapping and failed audit write.

## Phase 3 — DB/gateway schema hardening (P2 / PARTIAL)

- [ ] Preflight old request/profile rows for reversed date ranges, negative balances and invalid statuses.
- [ ] Add versioned additive database constraints; don't silently rewrite data.
- [ ] Introduce a versioned gateway schema-upgrade mechanism currently missing beyond initial `create_all` behavior.
- [ ] Test existing and fresh disposable databases with job/nonce/document records preserved.

## Phase 4 — Accessibility and stable test runs (P2 / FAIL)

- [ ] Fix modal focus trapping, background inertness and focus restore in `static/js/app.js` modal behavior.
- [ ] Add keyboard regression for Tab/Shift+Tab/Escape.
- [ ] Make smoke test create/use isolated synthetic data and non-colliding scenarios.
- [ ] Run smoke twice; no deletion of unrelated data.

## Phase 5 — AI policy/data governance (P2 / PARTIAL)

- [ ] Preserve the fixed numeric conflict guard and raw-question egress fix.
- [ ] Add provider-boundary tests with redacted transport inspection.
- [ ] Define organization-approved data transmission policy separately from technical flags.
- [ ] Review approved KB material for private data and add curation policy.
- [ ] Add policy source authority/version/effective date; adversarial tests for nonnumeric contradictions, paraphrases, hostile instructions, stale sources, and language conflicts.
- [ ] Continue safe fallback when sources conflict or do not answer; do not overstate semantic detection.

## Phase 6 — CI and operations (P2 / PARTIAL)

- [ ] Add CI for the configured Python suite, Ruff, formatting, mypy, `pip check`, frontend syntax/locales, migrations and secret/dependency checks.
- [ ] Run concurrent app outbox worker processes against PostgreSQL.
- [ ] Verify login rate limiting across multiple processes or add shared enforcement.
- [ ] Version gateway schema changes.
- [ ] Document/test backup and restore for both app and gateway state.
- [ ] Complete mobile/browser/accessibility checks; verify health checks, restart and recovery.
- [ ] Don't claim capacity/HA readiness absent an explicit target and load test.

## Phase 7 — Localization and provenance (P3 / PARTIAL)

- [ ] Translate integration notices and all visible state labels in RU/KK.
- [ ] Give sample course/content explicit item-level provenance.
- [ ] Confirm intended token/session behavior after reload without unsafe token persistence.
- [ ] Ensure localized errors remain safe/redacted.

## Phase 8 — Real 1C:ZUP adapter (external blocker dependent)

- [ ] Obtain exact product/version/configuration, deployment/network path, API metadata/service contract, authentication contract and sandbox.
- [ ] Implement actual employee/department/manager/status reads behind the existing snapshot mapping/sync boundary.
- [ ] Validate leave balance calculation with the HR/1C owner; preserve freshness and last-known snapshot.
- [ ] Quarantine unknown/ambiguous mappings; never match by name.
- [ ] Keep official write-back disabled unless explicitly required, implemented against verified contract and approved by HR/1C owner.

## Phase 9 — Real Documentolog adapter (external blocker dependent)

- [ ] Obtain current business API version, sandbox credentials, confirmed response/webhook schemas, sender/recipient/signature rules, file limits and status lookup semantics.
- [ ] Implement connector behind the existing durable gateway job seam, not a competing outbox.
- [ ] Keep app↔gateway HMAC distinct from vendor callback authentication. Verify vendor-supported callback authenticity or keep live callback processing disabled.
- [ ] Handle timeout-after-remote-acceptance through reconciliation/manual resolution before retry.
- [ ] Test sandbox submission only with a non-sensitive approved document and intended test signers.
- [ ] Rehearse credential rotation, retries, duplicate/out-of-order callbacks and provider outage; obtain formal release approval.

## Pull-request / task completion checklist

- [ ] Change is grounded in inspected current code.
- [ ] Regression test added and actually run.
- [ ] No live provider call/credentials in normal tests.
- [ ] Migration is safe and preflighted.
- [ ] No raw PII, secret or full payload in logs/errors.
- [ ] Existing outbox/gateway/idempotency contract preserved.
- [ ] Docs describe actual behavior, not hoped-for behavior.
- [ ] `12_QA_REMEDIATION_PLAN.md` updated only with evidence.
