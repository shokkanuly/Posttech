# JanaМен fix plan — 17 October 2026

Prioritize the two reproduced P1 defects first; both targeted fixes were implemented and retested. Remaining changes require focused follow-up work, without broad architecture replacement or unreviewed data migration.

| ID | Severity | Final status | Requirement / impact | Minimal fix and acceptance criterion |
|---|---|---|---|---|
| QA-F01 | P1 | FAIL → PASS for reproduced case | Conflicting literal numeric policy claims were labelled grounded. [app/services/knowledge_conflicts.py:has_conflicting_numeric_claims](app/services/knowledge_conflicts.py#L14) | Implemented; 6 conflict regressions plus equivalence/complement/access tests. General semantic contradiction detection remains a separate P2 gap. |
| QA-F02 | P1 | FAIL → PASS for reproduced egress | Raw employee free text containing synthetic identifiers reached Gemini HTTP JSON. [app/integrations/gemini.py:generate_grounded_answer](app/integrations/gemini.py#L50) | Implemented; explicit default-off operator approval, source-only quote selection, retained local coverage/quote verification. Does not scrub PII already placed in approved knowledge. |
| QA-F03 | P2 | PARTIAL | External knowledge data policy and production connector/TLS verification are missing. [app/config.py:Settings](app/config.py#L9) | Not implemented beyond the new safe-default gate. Require partner-approved sources, data-sharing policy, test systems and intended-deployment verification. |
| QA-F04 | P2 | PARTIAL | DEAD delivery and unknown-profile queues lack controlled recovery actions. [app/routers/admin.py](app/routers/admin.py) | Not implemented. Add audited HR-only replay preserving immutable idempotency keys, after reconciling existing gateway state; require explicit mapping decisions. |
| QA-F05 | P2 | FAIL | Identical advance submissions can create duplicate business requests. [app/services/request_service.py:create_request](app/services/request_service.py#L144) | Not implemented. Define a client-generated submission key, employee-scoped unique constraint, immutable-body check and UI key reuse on network retry; test serial/concurrent repeats. |
| QA-F06 | P2 | FAIL | Keyboard focus leaves an open modal. [static/js/app.js](static/js/app.js) | Not implemented. Trap focus in the top dialog, make the background inert, restore opener focus, and verify keyboard/Escape behavior. |
| QA-F07 | P2 | FAIL | Live smoke script is not safely repeatable. [smoke_test.py](smoke_test.py) | Not implemented. Use a fresh disposable fixture per smoke run or explicitly reuse the same known synthetic scenario; do not silently delete user requests. |
| QA-F08 | P2 | PARTIAL | Database domain constraints do not fully protect direct writes. [app/models/request.py:Request](app/models/request.py#L15) | Not implemented. Design additive CHECK/enum/decimal hardening with preflight detection and migration tests; do not silently repair existing rows. |
| QA-F09 | P2 | PARTIAL | Broader AI policy conflicts and hostile-source evaluation are incomplete. [app/services/knowledge_conflicts.py:has_conflicting_numeric_claims](app/services/knowledge_conflicts.py#L14) | Not implemented beyond F01. Establish HR-controlled policy precedence/version/effective-date metadata and adversarial acceptance fixtures; continue safe fallback under ambiguity. |
| QA-F10 | P2 | PARTIAL | Operational coverage remains local and incomplete. [app/gateway/runtime.py:initialize](app/gateway/runtime.py#L75) | Not implemented. Add CI checks and operational tests/runbooks before production deployment; keep initial create_all limitation explicit. |
| QA-F11 | P3 | PARTIAL | Some UI/localization/provenance behavior remains incomplete. [static/js/app.js](static/js/app.js) | Not implemented. Agree intended session recovery behavior, translate integration messages and add explicit sample provenance where content is shown. |

## Next three actions

1. Approve the intended deployment/data policy and enterprise test contracts; retain MOCK/offline modes until those prerequisites are verified.
2. Implement controlled replay/remapping and employee submission idempotency with audit/concurrency acceptance tests.
3. Fix keyboard dialog behavior and repeatable smoke fixtures, add CI, then run mobile and production-like worker/TLS/restore checks.
