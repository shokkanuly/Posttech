# PR #5 integration and conflict resolution — 18 October 2026

PR [#5](https://github.com/shokkanuly/Posttech/pull/5) could not merge because `main` introduced profile-change requests, leave calendars and personal HR answers after the gateway/fix-plan branch diverged. This change merges `origin/main` at `0ec30d2` into the existing `codex/fix-plan` branch, retaining the earlier signed MOCK gateway, recovery, idempotency and privacy protections. It updates the existing PR; it does not publish or merge changes into `main` automatically.

## What was combined

All nine text conflicts were resolved: README, migration readiness, request model/service, own-profile endpoint, HTML, JavaScript, locales and API matrix. The combined behavior includes:

- Vacation and advance approvals enqueue the existing canonical `REGISTER_DOCUMENT` snapshot with `PENDING` delivery state, HMAC signatures, the original idempotency key and generation-aware reconciliation. Incoming legacy `ONE_C_ORDER` dispatch was not reintroduced.
- Contact-change requests apply locally after authorized manager/HR approval. They retain submission idempotency, history, notifications and audit; they neither debit leave nor create a Documentolog/1C job. The outbox boundary also explicitly rejects unsupported request types.
- Decimal monetary storage, profile snapshot provenance, gateway job fields and charged-leave accounting are retained. Stored charged days remain stable when present; legacy approvals without stored charge metadata continue to use the local calendar fallback. Pending approvals use the current local calendar. No official 1C calendar or write-back is claimed.
- The incoming marked calendar, existing vacation display, personal-record HR answers and new source topics coexist with policy precedence, source-only provider egress, conflict handling and fallback.
- Profile contacts and the read-only HR-source badge remain separate. Request details show the marked leave calendar/profile changes and the actual MOCK integration state. Recovery/policy controls and dialog focus management remain available. Locale dictionaries retain both branches' messages and template rules.
- Existing advance/vacation submission hashes exclude the newly added optional profile field, preserving deployed keys. Contact submissions reuse browser-generated keys across failed responses.

The supplied [integration documentation folder](../janamen_ai_agent_docs/README.md) is now tracked alongside the source, with a [current status note](../janamen_ai_agent_docs/13_REPOSITORY_INTEGRATION_STATUS.md). The historical QA material is retained as historical evidence, not treated as a new live-vendor API contract.

## Migration compatibility

Head: **`0011_merge_profile_updates`**. Its two parents are `0010_source_metadata` and `0006_profile_updates`. Existing revision identities and parent relationships were retained. `0009_domain_checks` has a forward-execution compatibility amendment allowing valid profile-change rows from the other branch; already-deployed constraints are replaced by the new merge revision. Both upgrade paths preserve data without resetting tables.

The merged guard accepts valid vacation/advance/profile shapes, recognizes both SQL NULL and legacy JSON null for absent profile data, and retains negative amount/date/status protections. PostgreSQL checks compare the request type as text, permitting its transactional enum extension without using a new enum literal before commit. SQLite replaces guards without rebuilding referenced parent tables. The new ORM stores absent profile JSON as SQL NULL; existing JSON null rows are accepted without rewriting them.

Acceptance fixtures cover an empty database, an existing main database with pending/approved profile changes and JSON null vacation data, and an existing fix-plan database with the original two-kind guards installed. They repeat upgrades and check request/event/audit/outbox preservation, money precision, legacy job quarantine and rejection of invalid direct writes. Only disposable SQLite files and unique PostgreSQL schemas were used for automated migration tests. The owned synthetic Compose database on port 15440 was upgraded for runtime verification; production/user databases were not reset.

## Verification

| Actual execution | Result | Evidence |
|---|---|---|
| Final full SQLite suite | **484 passed**, 1 existing warning | [log](evidence/merge-integration-2026-10-18/final-sqlite.txt), [command](evidence/merge-integration-2026-10-18/final-sqlite.json) |
| Full PostgreSQL17 suite | **484 passed**, 1 existing warning | [log](evidence/merge-integration-2026-10-18/final-postgresql.txt), [command](evidence/merge-integration-2026-10-18/final-postgresql.json) |
| Seven new PostgreSQL upgrade/workflow cases | **7 passed** | [log](evidence/merge-integration-2026-10-18/migration-postgresql.txt) |
| Ruff, mypy over 83 sources, pip check, JS syntax and locale suite | **PASS; 5 locale tests passed** | [log](evidence/merge-integration-2026-10-18/final-quality.txt) |
| Ten-step Docker API smoke, first/repeat | **PASS twice** | [first](evidence/merge-integration-2026-10-18/smoke-first.txt), [repeat](evidence/merge-integration-2026-10-18/smoke-repeat.txt) |
| Fresh Docker approval-to-MOCK-registration flow | **PASS** | [record](evidence/merge-integration-2026-10-18/runtime-registration.txt) |

The initial full SQLite run passed 482 cases before two additional compatibility/visibility tests were added; the final full run includes both and passed 484. The warning in the suites is the existing Starlette TestClient/httpx deprecation. No dependencies were added.

The first baseline attempt overlapped merge preparation and stopped on merge markers; it is retained as an interrupted run and is not counted as a baseline pass. A clean archive of premerge `3e42d8e` then passed **41 focused baseline tests**. The first combined focused SQLite run passed **45 tests**. PostgreSQL's seven new compatibility cases passed. All reported full-suite results below come from actual executions on the merged source.

Docker Desktop was stopped initially and was started for testing. Only the owned `janamen-qa-check` application/gateway/worker stack was rebuilt. The isolated demo is at `http://127.0.0.1:18766`. Its schema probe reports `0011_merge_profile_updates`; web/database/signed-gateway health checks passed. The original port 8000 app/image was not rebuilt by this change. Smoke used the same existing synthetic scenario twice without another leave debit or deleting requests.

Browser inspection exercised the employee profile's source badge/contact controls, a focus-contained contact dialog (reverse Tab wrap and Escape return), the saved vacation calendar, and a 57-day selected period with three local-calendar holidays/54 charged days and a disabled submit when the balance is insufficient. The HR integration card still exposes MOCK/pending/last success. The available narrow browser viewport also exercised the collapsed navigation. No explicit viewport override or physical device was used; this is not a full mobile/device matrix. See [browser checks](evidence/merge-integration-2026-10-18/browser-checks.json).

Manager contact visibility follows the incoming tested workflow: the current emergency-contact projection is HR-only, while submitted old/new contact changes are visible to the employee and authorized assigned manager/HR reviewers. A new test makes that boundary explicit. This is not a claim that submitted emergency-contact values are universally hidden from managers. Organizational approval of contact-data visibility remains a deployment prerequisite.

## Remaining live-integration gates

The new folder itself confirms the missing customer-specific 1C deployment/service metadata, employee/leave semantics, approved Documentolog sandbox contract, signing/webhook authenticity, credentials and privacy approval. Both vendor connectors therefore remain **MOCK**. No real 1C, Documentolog or Gemini call was made; no vendor API, signing lifecycle or custom cipher was fabricated. Existing header names and signing code were preserved.

Production TLS/mTLS, HA/capacity, approved data policy, production PostgreSQL restore objectives and comprehensive accessibility still require verification. The CI definition remains an inactive [template](ci/quality.yml) because the earlier GitHub token lacks workflow-publication permission; no CI run is claimed. Tests and runtime evidence are stored under [evidence/merge-integration-2026-10-18](evidence/merge-integration-2026-10-18/).

Independent read-only review found no remaining required fixes in the resolved migration/workflow/privacy combination. See [review record](evidence/merge-integration-2026-10-18/review.json).
