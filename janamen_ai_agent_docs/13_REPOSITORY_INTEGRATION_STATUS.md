# Current repository integration status — 18 October 2026

Latest follow-up: [precommit review evidence](../docs/evidence/integration-precommit-2026-10-18/REVIEW.md), [implementation overview](../docs/INTEGRATION_IMPLEMENTATION_REPORT.md), [acceptance records](../docs/INTEGRATION_ACCEPTANCE_RESULTS.md) and [repeatable isolated demo](../docs/INTEGRATION_DEMO_RUNBOOK.md). Durable signed-call quotas now separate business requests from health probes within gateway v3, preserving existing business counts. Recovery/remapping authorization, audit and immutable-key/payload checks were rerun on a dedicated disposable PostgreSQL database. Exact counts, selected targets and availability observations belong to the session evidence. The supplied [blueprint](reference/integration_blueprint_2026-10-18.md) is design context, with actual implementation/evidence taking precedence.

This is the follow-up to the supplied 17 October QA baseline. The source is the existing `codex/fix-plan` branch combined with `main` at `0ec30d2`, not a new gateway implementation. See [the PR5 integration report](../docs/PR5_INTEGRATION_REPORT.md) for actual test commands, results, screenshots and remaining gates.

## Implemented in this repository

- Separate FastAPI MOCK gateway, existing HMAC headers/helper and durable nonce checks, canonical document contracts, persistent jobs/callbacks, internal Compose network and URL switch.
- Signed mock employee-code snapshots, source/as-of metadata and explicit HR mapping resolution for existing accounts.
- Durable audited HR recovery with immutable job keys/payloads, generation checks and reconciliation before retry; known missing accepted jobs require investigation.
- Employee-scoped initial submission keys, including profile requests and compatibility with the previous advance/vacation hash contract.
- Versioned gateway store/SQLite backup rehearsal; core schema guards and a single merged head `0011_merge_profile_updates` that upgrades either deployed migration branch without resetting rows.
- Local approval-based profile contacts, marked leave calendars and personal current-user HR answers from main. Profile contact changes never create vendor document jobs.
- Modal containment, repeatable synthetic smoke, explicit policy precedence and source provenance, default-off external provider and source-only quote selection.

The baseline's F04/F05/F06/F07 implementation work already exists. F08/F09/F10/F11 have the scoped improvements described in the fix-plan and PR5 reports; broader production/semantic/mobile/governance claims remain open. Historical 400-test results in this pack remain historical; current merged-source results are in the linked report.

## Live capabilities remain gated

The provider sources in this pack do not establish a customer sandbox, authorization, legal/privacy approval or a verified vendor API contract. There is no approved installation metadata for live 1C reads/writes, and no verified Documentolog signing/webhook contract. Keep both connectors MOCK and external AI disabled unless separately approved. The existing internal HMAC must not be presented as proof of authenticity of vendor-originated webhooks.

CI YAML is saved as an inactive template because current GitHub authentication cannot publish workflows. Do not invent credentials, broaden permission scopes or silently enable outbound systems to close that item.

## Executed verification

The combined source passed **484 tests on SQLite** and **484 on PostgreSQL17**, plus five frontend locale tests, Ruff, mypy over83 app sources, dependency consistency and JavaScript syntax. Both deployment-history upgrades and a fresh Docker MOCK registration were exercised. The existing deprecation warning is retained. These are local/disposable test results, not production or live-vendor certification. See the linked PR5 report for command evidence.
