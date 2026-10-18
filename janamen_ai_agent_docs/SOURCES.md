# Vendor Sources and Evidence Notes

These public sources were reviewed while preparing the design. The live implementation must re-check the current version and obtain the customer-specific API contract/approval before relying on a capability.

## 1C:Enterprise platform

- **REST interface overview:** <https://kb.1ci.com/1C_Enterprise_Platform/1C_Enterprise_Platform_Overview/Integration/REST_interface/>
  - Describes the standard REST interface, OData v3, support for data read/write operations, and the role of publication/configuration.
- **Publishing standard REST API for an infobase:** <https://kb.1ci.com/1C_Enterprise_Platform/FAQ/Development/Integration/Publishing_standard_REST_API_for_your_infobase/?language=en>
  - Describes publishing through a web server and inspecting exposed objects; additional objects may need to be configured and the infobase republished.

**What this evidence does not establish:** that the customer's 1C:ZUP has OData enabled, exposes the needed employee/leave objects, supports specific field names, or allows official leave writes through standard OData.

## Documentolog Business

- **Documentolog Business API guide:** <https://documentolog.com/en/integrations-business/api>
  - Public examples cover the documented create/access-token request, bearer token, iframe signing flow, webhook event examples, webhook retry intervals, completion/download links, and listed API limitations (no draft creation and sender must sign).
- **Documentolog 1C extension:** <https://documentolog.com/en/integrations-business/1c>
  - Describes an extension for 1C:Бухгалтерия для Казахстана from version 3.0, including cloud/local variants. This is **not proof** that the extension is compatible with 1C:ZUP or meets JanaМен's HR workflow.

**What this evidence does not establish:** a customer-specific environment, credentials, sandbox parity, remote idempotency, status polling, cancellation, or cryptographic webhook authentication. Obtain official confirmation from Documentolog for those items.

## Supplied project QA baseline

- **Full-project QA report dated 17 October 2026:** [`reference/qa_report_2026-10-17.pdf`](reference/qa_report_2026-10-17.pdf), provided by the user in this conversation. It reports a 162-item checklist, test outcomes, source paths, current mock gateway and snapshot-sync behavior, and remaining findings.
- The QA report refers to companion artifacts named `QA_TEST_RESULTS.md`, `QA_CHECKLIST.md`, and `FIX_PLAN.md`. Those were not separately attached with the PDF in this conversation, so this documentation pack summarizes the report's visible assessment and does not claim to contain their original detailed command logs or artifact contents.
- Treat the test counts as historical evidence from the reported checkout/environment. Re-run the appropriate checks on the actual current repository before marking any task complete.
