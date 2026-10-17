# JanaМен QA checklist — 17 October 2026

Final-state assessment of all **162** checkbox/numbered acceptance items from the supplied checklist. PASS: 140 / FAIL: 2 / PARTIAL: 17 / NOT VERIFIED: 2 / BLOCKED: 0 / NOT APPLICABLE: 1.

PASS is scoped to the evidence stated. Real vendor connections, production infrastructure and live Gemini are not established by MOCK tests. All 16 required acceptance scenarios are covered by executed tests; broader operational gaps remain.

## PHASE 1: REPOSITORY DISCOVERY

- **QA001 — PASS** — Repository structure and entry points
  Evidence: Inspected [app/main.py](app/main.py), [app/gateway/main.py](app/gateway/main.py), [static/index.html](static/index.html).

- **QA002 — PASS** — Frontend framework and build commands
  Evidence: Inspected [static/js/app.js](static/js/app.js), [static/css/style.css](static/css/style.css), [static/js/i18n.js](static/js/i18n.js). Plain HTML/CSS/JavaScript; no package.json, frontend build or bundler.

- **QA003 — PASS** — Backend framework and startup commands
  Evidence: Inspected [app/main.py](app/main.py), [Dockerfile](Dockerfile).

- **QA004 — PASS** — Database engine, models, and migrations
  Evidence: Inspected [app/database.py](app/database.py), [app/models/request.py](app/models/request.py), [migrations/versions/0006_gateway_runtime.py](migrations/versions/0006_gateway_runtime.py).

- **QA005 — PASS** — Authentication and authorization implementation
  Evidence: Inspected [app/services/auth_service.py](app/services/auth_service.py), [app/routers/auth.py](app/routers/auth.py).

- **QA006 — PASS** — API routes and validation
  Evidence: Inspected [app/routers/requests.py](app/routers/requests.py), [app/schemas/request.py](app/schemas/request.py), [docs/openapi.json](docs/openapi.json).

- **QA007 — PASS** — Background workers and scheduled tasks
  Evidence: Inspected [app/integrations/outbox.py](app/integrations/outbox.py), [app/gateway/runtime.py](app/gateway/runtime.py).

- **QA008 — PASS** — Integration adapters and gateway
  Evidence: Inspected [app/gateway/connectors.py](app/gateway/connectors.py), [app/integrations/profile_sync.py](app/integrations/profile_sync.py).

- **QA009 — PASS** — AI assistant implementation and knowledge sources
  Evidence: Inspected [app/services/ai_service.py](app/services/ai_service.py), [knowledge/README.md](knowledge/README.md).

- **QA010 — PASS** — Unit, integration, and end-to-end tests
  Evidence: Inspected [tests/test_e2e_journey.py](tests/test_e2e_journey.py), [tests/test_gateway_service.py](tests/test_gateway_service.py), [tests/frontend_localization.test.cjs](tests/frontend_localization.test.cjs).

- **QA011 — PASS** — Dockerfiles and Docker Compose
  Evidence: Inspected [Dockerfile](Dockerfile), [docker-compose.yml](docker-compose.yml).

- **QA012 — PARTIAL** — CI configuration and lint/type-check commands
  Evidence: [pyproject.toml](pyproject.toml) defines Ruff/mypy/pytest; no tracked CI workflow or .github directory was found.

- **QA013 — PASS** — README and architecture documentation
  Evidence: Inspected [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md).

- **QA014 — PASS** — Environment variable examples
  Evidence: Inspected [.env.example](.env.example), [app/config.py](app/config.py).

- **QA015 — PASS** — Existing TODOs, placeholders, disconnected services, and mock data
  Evidence: Inspected [app/integrations/documentolog.py](app/integrations/documentolog.py), [app/integrations/one_c_zup.py](app/integrations/one_c_zup.py), [app/gateway/mock_employees.json](app/gateway/mock_employees.json).  Legacy adapters are disconnected simulations; current gateway fixtures are explicitly MOCK. Graph text search found no TODO/FIXME/NotImplementedError matches; absence of markers does not prove completeness.

## PHASE 2: END-TO-END PRODUCT REQUIREMENTS

### Employee workspace

- **QA016 — PASS** — Employee can view their own profile.
  Evidence: [test_get_my_profile](tests/test_auth.py#L42); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

- **QA017 — PASS** — Official HR profile fields are read-only for employees.
  Evidence: [test_local_provisioning_creates_readonly_profile](tests/test_reliability.py#L555); [test_matrix_covers_every_openapi_operation](tests/test_api_matrix.py#L121); no employee profile mutation route exists.

- **QA018 — PASS** — Employee can submit a supported HR request.
  Evidence: [test_create_vacation_request_success](tests/test_requests.py#L11); [test_create_advance_payment_request](tests/test_requests.py#L52); [test_full_hackathon_demo_journey](tests/test_e2e_journey.py#L1); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44)

- **QA019 — PASS** — Input validation rejects invalid or incomplete requests.
  Evidence: [test_body_contracts_reject_missing_malformed_and_extra_input](tests/test_api_matrix.py#L227); [test_request_invalid_inputs](tests/test_reliability.py#L108)

- **QA020 — PASS** — Request is persisted in the database.
  Evidence: [test_create_vacation_request_success](tests/test_requests.py#L11); [test_create_advance_payment_request](tests/test_requests.py#L52); [test_full_hackathon_demo_journey](tests/test_e2e_journey.py#L1); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44)

- **QA021 — PASS** — Employee can see their own request history.
  Evidence: [test_create_vacation_request_success](tests/test_requests.py#L11); [test_create_advance_payment_request](tests/test_requests.py#L52); [test_full_hackathon_demo_journey](tests/test_e2e_journey.py#L1); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44)

- **QA022 — PASS** — Request status and history remain consistent after reload.
  Evidence: [test_create_vacation_request_success](tests/test_requests.py#L11); [test_create_advance_payment_request](tests/test_requests.py#L52); [test_full_hackathon_demo_journey](tests/test_e2e_journey.py#L1); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44)

- **QA023 — PASS** — Employee cannot view another employee's private requests.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132)

- **QA024 — PARTIAL** — Loading, empty, error, and success states are handled.
  Evidence: [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json); [static/js/app.js](static/js/app.js) has errors, empty messages and disabled controls; browser network-error/loading permutations were not exhaustively tested.

- **QA025 — PASS** — Displayed leave balances show their source and synchronization freshness.
  Evidence: [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

### Manager approvals

- **QA026 — PASS** — Manager can see only requests within their authorized scope.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA027 — PASS** — Manager can approve or reject eligible requests.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA028 — PASS** — Unauthorized roles cannot approve requests.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA029 — PASS** — Approval/rejection creates a history record.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA030 — PASS** — Audit events capture important state transitions.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA031 — PASS** — Notifications are created once per relevant event.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA032 — PASS** — Concurrent actions cannot create contradictory final states.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385)

- **QA033 — PASS** — A repeated approval action is handled idempotently.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_review_direct_report_approval](tests/test_requests.py#L66); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184); [test_concurrent_approvals_cannot_overdraw](tests/test_reliability.py#L207); [test_history_shows_decisions_with_actor_and_comment](tests/test_seed_scale.py#L44); [app/services/request_service.py:review_request](app/services/request_service.py#L385) A repeated decision returns 409 with no extra business effects; it does not return a second success.

### Jana Academy

- **QA034 — PASS** — Course catalogue loads from the actual configured source.
  Evidence: [test_list_courses](tests/test_academy.py#L1); [test_course_catalog_uses_bounded_queries](tests/test_backend_hardening.py#L334); server database catalogue, not an external LMS.

- **QA035 — PASS** — Course enrollment or assignment works as designed.
  Evidence: [test_explicit_enrollment_progress_and_persistence](tests/test_reliability.py#L283); [test_concurrent_enrollment_is_idempotent](tests/test_reliability.py#L495)

- **QA036 — PASS** — Lesson progress is persisted.
  Evidence: [test_explicit_enrollment_progress_and_persistence](tests/test_reliability.py#L283); [test_concurrent_enrollment_is_idempotent](tests/test_reliability.py#L495)

- **QA037 — PASS** — Progress survives reload and re-login.
  Evidence: [test_explicit_enrollment_progress_and_persistence](tests/test_reliability.py#L283); [relogin-persistence.json](docs/evidence/qa-2026-10-17/relogin-persistence.json) records actual HTTP re-login and state after the QA web process rebuild.

- **QA038 — PASS** — Completion state is correct.
  Evidence: [test_complete_lesson_quiz_and_finish_course](tests/test_academy.py#L31); [test_course_completion_notifies_once](tests/test_reliability.py#L326)

- **QA039 — PASS** — Course access and progress are scoped to the authenticated employee.
  Evidence: [app/services/academy_service.py:get_enrollment](app/services/academy_service.py#L24); [test_each_operation_has_a_working_authorized_request](tests/test_api_matrix.py#L140); [test_explicit_enrollment_progress_and_persistence](tests/test_reliability.py#L283)

- **QA040 — PARTIAL** — Sample course content is identified as sample content.
  Evidence: [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json); global synthetic-demo footer exists, but course cards have no explicit per-course sample provenance field.

### AI Jana

- **QA041 — PASS** — Assistant retrieves only approved, authorized knowledge sources.
  Evidence: [test_document_approval_lifecycle_and_source_scope](tests/test_reliability.py#L381); [test_import_review_and_ml_citations_preserve_authorization](tests/test_knowledge_files_and_ml.py#L133)

- **QA042 — PASS** — Answers include verifiable source references.
  Evidence: [test_citation_rejects_changed_source_after_reapproval](tests/test_backend_hardening.py#L145); [ai-source.png](docs/evidence/qa-2026-10-17/ai-source.png)

- **QA043 — PASS** — Unsupported questions receive a safe fallback.
  Evidence: [test_ai_safe_fallback_unsupported_question](tests/test_ai.py#L28); [test_ai_safe_fallback_russian](tests/test_ai.py#L93); [test_ai_safe_fallback_kazakh](tests/test_ai.py#L164)

- **QA044 — PARTIAL** — Retrieved content cannot override system security rules.
  Evidence: [test_file_cannot_set_approval_or_disable_source_rules](tests/test_knowledge_files_and_ml.py#L56); [test_valid_quote_does_not_authorize_fabricated_claim](tests/test_merge_regressions.py#L27); exact quotation/role filters are enforced. A comprehensive malicious-approved-source injection evaluation was not executed.

- **QA045 — PARTIAL** — Assistant does not invent company policies or HR contacts.
  Evidence: [test_conflicting_approved_numbers_fall_back_before_provider](tests/test_qa_acceptance.py#L44); [test_unverified_model_answer_falls_back_to_source_text](tests/test_ai_gemini.py#L73); reproduced numeric disagreement now falls back. General semantic contradictions and employer approval of configured HR contact remain unverified.

- **QA046 — PASS** — Private employee records are not leaked to other users.
  Evidence: [test_ai_privacy_guardrail_blocked](tests/test_ai.py#L41); [test_private_questions_never_reach_the_model](tests/test_ai_gemini.py#L99); no employee-record retrieval tool is exposed to the provider.

- **QA047 — PARTIAL** — Sensitive personal data is not sent to an AI provider unless explicitly approved and protected by the system's data policy.
  Evidence: [test_employee_free_text_is_absent_from_provider_http_body](tests/test_ai_gemini.py#L146); [test_provider_requires_explicit_approval_at_http_boundary](tests/test_ai_gemini.py#L126); raw questions stay local and approval defaults off. Actual organizational approval, provider retention/residency and PII in approved source text are NOT VERIFIED.

- **QA048 — PASS** — Provider failures, empty retrieval results, and timeouts are handled.
  Evidence: [test_model_outage_keeps_extractive_answers](tests/test_ai_gemini.py#L93); [test_out_of_scope_question_stays_a_safe_fallback](tests/test_ai_gemini.py#L108); [test_gemini_error_logs_are_redacted](tests/test_merge_regressions.py#L57); provider transport is intercepted; live Gemini remains NOT VERIFIED.

- **QA049 — PASS** — The interface accurately identifies demo or production mode.
  Evidence: [test_production_settings_and_synthetic_boundaries](tests/test_reliability.py#L459); [test_published_demo_password_is_denied_in_production](tests/test_reliability.py#L602); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

- **QA050 — PARTIAL** — Language handling matches the implemented RU/KZ/English requirements.
  Evidence: [test_ai_grounded_answer_russian](tests/test_ai.py#L72); [test_ai_grounded_answer_kazakh](tests/test_ai.py#L135); [test_ai_grounded_answer_vacation](tests/test_ai.py#L4); [test_language_negotiation](tests/test_localization.py#L179); RU/KK frontend and EN/RU/KK backend tested. New integration notifications and some labels remain English in the RU UI.

### Notifications

- **QA051 — PASS** — Correct user receives each notification.
  Evidence: [test_notification_ownership_and_unread](tests/test_reliability.py#L265); [test_course_completion_notifies_once](tests/test_reliability.py#L326); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79)

- **QA052 — PASS** — Unauthorized users cannot read other users' notifications.
  Evidence: [test_notification_ownership_and_unread](tests/test_reliability.py#L265); [test_course_completion_notifies_once](tests/test_reliability.py#L326); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79)

- **QA053 — PASS** — Read/unread status persists.
  Evidence: [test_notification_ownership_and_unread](tests/test_reliability.py#L265); [test_course_completion_notifies_once](tests/test_reliability.py#L326); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79)

- **QA054 — PASS** — Duplicate events do not generate duplicate notifications.
  Evidence: [test_notification_ownership_and_unread](tests/test_reliability.py#L265); [test_course_completion_notifies_once](tests/test_reliability.py#L326); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79)

- **QA055 — PASS** — Failed notification delivery is observable and recoverable.
  Evidence: [test_failed_notification_rolls_back_entire_approval](tests/test_reliability.py#L245); [test_failed_approval_rolls_back_outbox_and_all_business_effects](tests/test_qa_acceptance.py#L89); delivery here means persistent in-app notification rows. A failed write aborts the business transaction and returns an error, allowing the action to be retried; email/push delivery is not implemented.

## PHASE 3: AUTHENTICATION AND AUTHORIZATION

- **QA056 — PASS** — Authentication is required for protected API routes.
  Evidence: [test_every_protected_operation_rejects_anonymous_access](tests/test_api_matrix.py#L174); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA057 — PASS** — Employee, manager, and HR permissions are enforced by the backend.
  Evidence: [test_every_protected_operation_rejects_anonymous_access](tests/test_api_matrix.py#L174); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA058 — PASS** — Role changes cannot be achieved by editing client-side state.
  Evidence: [test_every_protected_operation_rejects_anonymous_access](tests/test_api_matrix.py#L174); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA059 — PASS** — Object-level access checks prevent IDOR vulnerabilities.
  Evidence: [test_every_protected_operation_rejects_anonymous_access](tests/test_api_matrix.py#L174); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA060 — PASS** — Employees cannot access manager or HR endpoints without permission.
  Evidence: [test_every_protected_operation_rejects_anonymous_access](tests/test_api_matrix.py#L174); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA061 — PASS** — Manager scope is enforced server-side.
  Evidence: [test_every_protected_operation_rejects_anonymous_access](tests/test_api_matrix.py#L174); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA062 — PASS** — Session/token expiration and invalid credentials are handled.
  Evidence: [test_all_protected_operations_reject_invalid_sessions](tests/test_api_matrix.py#L196); [test_logout_revokes_current_session_only](tests/test_reliability.py#L27); [test_zero_lifetime_token_expires_instead_of_using_default](tests/test_backend_hardening.py#L235)

- **QA063 — PASS** — Passwords, if supported, are stored using an appropriate password-hashing scheme.
  Evidence: [app/services/auth_service.py:hash_password](app/services/auth_service.py#L73); [test_legacy_password_is_upgraded_after_login](tests/test_reliability.py#L535)

- **QA064 — PASS** — Secrets are not committed to source control.
  Evidence: [secret-scan.json](docs/evidence/qa-2026-10-17/secret-scan.json); scoped current-file and reachable-history scan; private environment files remain ignored. A scan is not proof that every possible secret format is absent.

- **QA065 — PARTIAL** — CORS, CSRF, cookie, and rate-limit settings are reviewed where applicable.
  Evidence: [app/main.py](app/main.py); [test_login_throttle_and_redacted_errors](tests/test_reliability.py#L74); [test_production_settings_and_synthetic_boundaries](tests/test_reliability.py#L459); explicit CORS origins and bearer Authorization reviewed. No auth cookies (cookie CSRF not applicable); login throttle is per-process, not distributed.

- **QA066 — PASS** — Authentication failures do not reveal sensitive information.
  Evidence: [test_login_invalid_password](tests/test_auth.py#L13); [test_login_nonexistent_user](tests/test_auth.py#L21); [test_login_throttle_and_redacted_errors](tests/test_reliability.py#L74)

- **QA067 — PASS** — Logs avoid secrets and unnecessary personal data.
  Evidence: [test_ai_audit_is_persisted_without_raw_questions](tests/test_reliability.py#L362); [test_gemini_error_logs_are_redacted](tests/test_merge_regressions.py#L57); [test_unexpected_error_is_redacted_and_not_cached](tests/test_backend_hardening.py#L192); [log-hygiene.json](docs/evidence/qa-2026-10-17/log-hygiene.json)

## PHASE 4: DOCUMENTOLOG ASYNCHRONOUS INTEGRATION

### Transaction and outbox

- **QA068 — PASS** — Approval and outbox insertion occur in the same database transaction.
  Evidence: [app/services/request_service.py:review_request](app/services/request_service.py#L385); [test_failed_approval_rolls_back_outbox_and_all_business_effects](tests/test_qa_acceptance.py#L89)

- **QA069 — PASS** — If the transaction fails, neither partial approval nor orphan outbox event remains.
  Evidence: [test_failed_approval_rolls_back_outbox_and_all_business_effects](tests/test_qa_acceptance.py#L89) injects failure after enqueue+flush, during notification and during audit; asserts Pending, unchanged balance/history/notification counts, no outbox row.

- **QA070 — PASS** — External network calls do not occur inside the approval transaction.
  Evidence: [app/services/request_service.py:review_request](app/services/request_service.py#L385) only enqueues a snapshot; network delivery is in [app/integrations/outbox.py:dispatch_one](app/integrations/outbox.py#L242).

- **QA071 — PASS** — Approval remains successful if Documentolog or the gateway is unavailable.
  Evidence: [test_approval_survives_gateway_down_retries_then_dead](tests/test_integration_gateway.py#L109); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA072 — PASS** — Worker safely claims pending rows.
  Evidence: [app/integrations/outbox.py:dispatch_one](app/integrations/outbox.py#L242) uses PostgreSQL FOR UPDATE SKIP LOCKED; [app/gateway/runtime.py:process_one](app/gateway/runtime.py#L124) uses conditional durable leases. Intended application Compose database is PostgreSQL.

- **QA073 — PARTIAL** — Concurrent workers cannot process the same event unsafely.
  Evidence: [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124) verifies gateway job/document concurrency; PostgreSQL row-claim SQL inspected. Simultaneous independent application-worker processes were not exercised; SQLite application workers do not gain PostgreSQL row locks.

- **QA074 — PASS** — Delivery attempts and error reasons are recorded.
  Evidence: [app/integrations/outbox.py:_fail](app/integrations/outbox.py#L218); [test_approval_survives_gateway_down_retries_then_dead](tests/test_integration_gateway.py#L109); [test_malformed_ack_is_not_success](tests/test_integration_gateway.py#L135)

- **QA075 — PASS** — Retry behavior uses bounded exponential backoff with jitter.
  Evidence: [app/integrations/outbox.py:_fail](app/integrations/outbox.py#L218) and [app/gateway/runtime.py:process_one](app/gateway/runtime.py#L124) use a bounded increasing schedule with uniform 0.8–1.2 jitter; retry exhaustion executed in tests. Day-long real elapsed schedules were not waited through.

- **QA076 — PASS** — Maximum retries transition to a visible DEAD state.
  Evidence: [test_approval_survives_gateway_down_retries_then_dead](tests/test_integration_gateway.py#L109); [test_mock_connector_temporary_failure_reaches_dead_without_document](tests/test_gateway_service.py#L207)

- **QA077 — PARTIAL** — Dead events can be inspected and safely retried by authorized staff.
  Evidence: [test_validation_failure_not_retried_and_hr_queue_shows_it](tests/test_integration_gateway.py#L145); HR can inspect FAILED/DEAD rows, but there is no authorized replay endpoint/button/runbook. Do not reset rows blindly.

- **QA078 — PASS** — Worker restart does not silently lose jobs.
  Evidence: [test_gateway_restart_recovers_jobs_and_nonces](tests/test_gateway_service.py#L140); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [test_reconciliation_recovers_lost_callback](tests/test_integration_gateway.py#L159); actual Docker rebuild preserved registered records; no production backup/restore claim.

### Idempotency

- **QA079 — PASS** — Each logical event has a stable idempotency key.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [app/models/integration.py](app/models/integration.py) and [app/gateway/models.py](app/gateway/models.py) enforce unique keys.

- **QA080 — PASS** — The same key cannot create multiple external documents.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [app/models/integration.py](app/models/integration.py) and [app/gateway/models.py](app/gateway/models.py) enforce unique keys.

- **QA081 — PASS** — Database uniqueness constraints enforce deduplication.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [app/models/integration.py](app/models/integration.py) and [app/gateway/models.py](app/gateway/models.py) enforce unique keys.

- **QA082 — PASS** — Retries reuse the original key.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [app/models/integration.py](app/models/integration.py) and [app/gateway/models.py](app/gateway/models.py) enforce unique keys.

- **QA083 — PASS** — Duplicate callbacks do not repeat state changes or notifications.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [app/models/integration.py](app/models/integration.py) and [app/gateway/models.py](app/gateway/models.py) enforce unique keys.

- **QA084 — PASS** — Callback processing is safe if the same logical result arrives again.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [test_callback_retry_is_persistent_and_never_registers_twice](tests/test_gateway_service.py#L166); [app/models/integration.py](app/models/integration.py) and [app/gateway/models.py](app/gateway/models.py) enforce unique keys.

### Request signing and callbacks

- **QA085 — PASS** — HMAC-SHA256 signing matches the documented canonical message format.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_query_string_is_signed_and_mock_snapshots_are_canonical](tests/test_gateway_service.py#L184); [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [app/integrations/signing.py](app/integrations/signing.py)

- **QA086 — PASS** — Method, path, timestamp, nonce, and body hash are included consistently.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_query_string_is_signed_and_mock_snapshots_are_canonical](tests/test_gateway_service.py#L184); [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [app/integrations/signing.py](app/integrations/signing.py)

- **QA087 — PASS** — Invalid signatures are rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_query_string_is_signed_and_mock_snapshots_are_canonical](tests/test_gateway_service.py#L184); [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [app/integrations/signing.py](app/integrations/signing.py)

- **QA088 — PASS** — Expired or excessively skewed timestamps are rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_query_string_is_signed_and_mock_snapshots_are_canonical](tests/test_gateway_service.py#L184); [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [app/integrations/signing.py](app/integrations/signing.py)

- **QA089 — PASS** — Reused nonces are rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_query_string_is_signed_and_mock_snapshots_are_canonical](tests/test_gateway_service.py#L184); [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [app/integrations/signing.py](app/integrations/signing.py)

- **QA090 — PASS** — Unknown key IDs are rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_query_string_is_signed_and_mock_snapshots_are_canonical](tests/test_gateway_service.py#L184); [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [app/integrations/signing.py](app/integrations/signing.py)

- **QA091 — PASS** — Signature comparison uses a constant-time comparison.
  Evidence: [app/integrations/signing.py](app/integrations/signing.py) uses hmac.compare_digest; signature rejection/tampering tests execute that verifier.

- **QA092 — PASS** — Callback authorization is independent of frontend roles.
  Evidence: [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [app/routers/internal.py:documentolog_status](app/routers/internal.py#L47) and [app/integrations/outbox.py:apply_result](app/integrations/outbox.py#L131)

- **QA093 — PASS** — Callback payloads are validated before state changes.
  Evidence: [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [app/routers/internal.py:documentolog_status](app/routers/internal.py#L47) and [app/integrations/outbox.py:apply_result](app/integrations/outbox.py#L131)

- **QA094 — PASS** — Callback processing is idempotent and transactional.
  Evidence: [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [app/routers/internal.py:documentolog_status](app/routers/internal.py#L47) and [app/integrations/outbox.py:apply_result](app/integrations/outbox.py#L131)

- **QA095 — PASS** — Secrets are loaded from protected configuration.
  Evidence: [app/config.py](app/config.py); [app/gateway/configure_mock.py](app/gateway/configure_mock.py); [test_invalid_key_errors_hide_input_values](tests/test_gateway_service.py#L225); [test_short_integration_keys_are_refused](tests/test_integration_gateway.py#L66); generated env is outside the repo, mode0600.

- **QA096 — PARTIAL** — HTTPS/mTLS requirements are documented and enforced in the intended deployment.
  Evidence: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md); [app/integrations/outbox.py:_tls](app/integrations/outbox.py#L86) and production config validation. Local MOCK uses internal HTTP+HMAC; inbound mTLS proxy, certificates and production handshake are NOT VERIFIED.

- **QA097 — PASS** — No custom cryptographic algorithm has been invented.
  Evidence: [app/integrations/signing.py](app/integrations/signing.py) uses standard HMAC-SHA256/base64/SHA256, with method/path-query/time/nonce/body digest binding; no custom cipher.

### Mock Documentolog behavior

- **QA098 — PASS** — Mock connector is explicitly labelled MOCK.
  Evidence: [app/gateway/connectors.py](app/gateway/connectors.py); [hr-card.png](docs/evidence/qa-2026-10-17/hr-card.png)

- **QA099 — PASS** — Successful mock registration returns a deterministic external reference.
  Evidence: [app/gateway/connectors.py:register](app/gateway/connectors.py#L26) derives MOCK-DOC from the persisted job ID; repeated key/restart returns the same stored reference. Recreating an empty store is not the same persisted logical job.

- **QA100 — PASS** — The gateway acknowledges accepted work asynchronously.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [app/gateway/main.py:documents](app/gateway/main.py#L95) returns 202; registration runs in the gateway worker.

- **QA101 — PASS** — The mock can simulate temporary failure and validation rejection.
  Evidence: [test_mock_connector_temporary_failure_reaches_dead_without_document](tests/test_gateway_service.py#L207); [test_validation_failure_not_retried_and_hr_queue_shows_it](tests/test_integration_gateway.py#L145)

- **QA102 — PASS** — A successful callback updates the JanaМен request integration state.
  Evidence: [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA103 — PASS** — Employee approval status remains Approved when document registration fails.
  Evidence: [test_approval_survives_gateway_down_retries_then_dead](tests/test_integration_gateway.py#L109); [test_validation_failure_not_retried_and_hr_queue_shows_it](tests/test_integration_gateway.py#L145)

- **QA104 — PASS** — UI distinguishes NOT_REQUIRED, PENDING, SENT, REGISTERED, FAILED, and DEAD as applicable.
  Evidence: [app/schemas/request.py](app/schemas/request.py); [static/js/app.js](static/js/app.js) renders sync_status/external_ref independently of business status; [test_without_gateway_approval_queues_nothing](tests/test_integration_gateway.py#L71); [test_validation_failure_not_retried_and_hr_queue_shows_it](tests/test_integration_gateway.py#L145); [test_admin_card_uses_actual_counts_mode_and_last_success](tests/test_integration_gateway.py#L284). Browser observed REGISTERED/MOCK and pending/failed counters; not every status was visually injected.

- **QA105 — PASS** — Real Documentolog connectivity is not claimed without a verified vendor connection.
  Evidence: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) and [hr-card.png](docs/evidence/qa-2026-10-17/hr-card.png) explicitly state MOCK, with no live vendor registration/signature claim.

## PHASE 5: 1C:ЗУП INTEGRATION

- **QA106 — PASS** — Employee records are matched using a stable employee code, not name alone.
  Evidence: [test_profile_sync_code_matching_and_provisional_balance](tests/test_integration_gateway.py#L211); [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

- **QA107 — PASS** — Synced records identify their source and synchronization timestamp.
  Evidence: [test_profile_sync_code_matching_and_provisional_balance](tests/test_integration_gateway.py#L211); [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

- **QA108 — PASS** — Employee snapshots remain available during temporary gateway outages.
  Evidence: [test_profile_sync_code_matching_and_provisional_balance](tests/test_integration_gateway.py#L211); [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

- **QA109 — PASS** — Stale data is visibly marked.
  Evidence: [test_profile_sync_code_matching_and_provisional_balance](tests/test_integration_gateway.py#L211); [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json); [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json)

- **QA110 — PARTIAL** — Unmatched employee records enter a controlled HR review process.
  Evidence: [test_unmatched_employee_and_manager_go_to_review](tests/test_integration_gateway.py#L235); safe persisted HR review list exists, but resolution/remapping workflow is not implemented.

- **QA111 — PASS** — Read-only 1C access is used where specified.
  Evidence: [app/gateway/connectors.py](app/gateway/connectors.py) reads synthetic snapshot fixtures only. No write-back method or real vendor API is implemented.

- **QA112 — PASS** — Leave balance source and calculation ownership are documented.
  Evidence: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) documents snapshot source balance minus frozen unconfirmed local debits and the explicit source-confirmation extension; [test_snapshot_failure_does_not_confirm_debits_or_overwrite_balance](tests/test_integration_gateway.py#L303)

- **QA113 — PASS** — Failed synchronization can be retried safely.
  Evidence: [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); HR-only, rate-limited refresh and scheduled retry keep last-known snapshot.

- **QA114 — PASS** — No duplicate employees are created by repeated sync.
  Evidence: [test_profile_sync_code_matching_and_provisional_balance](tests/test_integration_gateway.py#L211); [test_unmatched_employee_and_manager_go_to_review](tests/test_integration_gateway.py#L235); existing employee codes only; no account auto-creation.

- **QA115 — PASS** — MOCK and CONNECTED modes are visibly distinguished.
  Evidence: [hr-card.png](docs/evidence/qa-2026-10-17/hr-card.png); [test_admin_card_uses_actual_counts_mode_and_last_success](tests/test_integration_gateway.py#L284); only MOCK or UNCONNECTED is reported, never an unverified CONNECTED state.

- **QA116 — PASS** — Live 1C connectivity is not claimed without a successful integration test.
  Evidence: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md); no live 1C claim; real connectivity remains NOT VERIFIED.

## PHASE 6: DATABASE AND API QUALITY

- **QA117 — PASS** — Migrations apply cleanly in a disposable test database.
  Evidence: [tests/test_migrations.py](tests/test_migrations.py) contains 6 migration cases; the full runs also migrate fresh SQLite databases and fresh PostgreSQL schemas for application tests.

- **QA118 — PARTIAL** — Foreign keys and uniqueness constraints protect data integrity.
  Evidence: [extra-probes.json](docs/evidence/qa-2026-10-17/extra-probes.json) rejects FK and duplicate employee code violations, but direct SQLite writes accept negative balance, reversed dates and unknown request status. API validation protects normal calls; DB CHECK hardening remains.

- **QA119 — PARTIAL** — Important queries have appropriate indexes.
  Evidence: [app/models/request.py](app/models/request.py), [app/models/profile.py](app/models/profile.py), [app/models/integration.py](app/models/integration.py) include ownership/status/code/due indexes; [test_course_catalog_uses_bounded_queries](tests/test_backend_hardening.py#L334). Production query plans/capacity were not benchmarked in this QA run.

- **QA120 — PASS** — API inputs are validated.
  Evidence: [test_body_contracts_reject_missing_malformed_and_extra_input](tests/test_api_matrix.py#L227); [test_all_collections_enforce_pagination_bounds](tests/test_backend_hardening.py#L297)

- **QA121 — PASS** — API errors are consistent and do not leak internals.
  Evidence: [test_unexpected_error_is_redacted_and_not_cached](tests/test_backend_hardening.py#L192); [test_openapi_documents_response_and_error_shapes](tests/test_reliability.py#L485); [test_canonical_validation_does_not_echo_payload](tests/test_gateway_service.py#L196)

- **QA122 — PASS** — Pagination and filtering behave correctly where needed.
  Evidence: [test_collections_have_stable_pagination](tests/test_backend_hardening.py#L280); [test_all_collections_enforce_pagination_bounds](tests/test_backend_hardening.py#L297); [test_each_operation_has_a_working_authorized_request](tests/test_api_matrix.py#L140)

- **QA123 — PASS** — State transitions reject invalid operations.
  Evidence: [test_transition_and_action_validation](tests/test_reliability.py#L156); [test_concurrent_duplicate_approval](tests/test_reliability.py#L184)

- **QA124 — PASS** — Database transactions cover logically atomic updates.
  Evidence: [test_failed_approval_rolls_back_outbox_and_all_business_effects](tests/test_qa_acceptance.py#L89); [test_failed_knowledge_edit_rolls_back_revision](tests/test_backend_hardening.py#L245)

- **QA125 — PASS** — Timezones and dates are handled consistently.
  Evidence: [test_timestamps_are_unambiguous_utc](tests/test_reliability.py#L517); [test_language_negotiation](tests/test_localization.py#L179); UTC serialization and date/exclusion rules tested. Employer approval of the configured calendar is outside this verification.

- **QA126 — PASS** — Sensitive fields are excluded from unnecessary API responses.
  Evidence: [app/schemas/auth.py](app/schemas/auth.py), [app/schemas/profile.py](app/schemas/profile.py); [test_jwt_role_is_never_authority](tests/test_reliability.py#L57); [test_employee_free_text_is_absent_from_provider_http_body](tests/test_ai_gemini.py#L146); secrets/password hashes not serialized in user/profile DTOs.

- **QA127 — FAIL** — Repeated requests do not create unintended duplicate records.
  Evidence: [extra-probes.json](docs/evidence/qa-2026-10-17/extra-probes.json) repeats the identical advance payload twice: HTTP201/201,2 distinct request records. No client request-idempotency contract; vacation overlap and integration keys have separate protection.

## PHASE 7: FRONTEND AND USER EXPERIENCE

- **QA128 — PASS** — Every visible navigation item works.
  Evidence: [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json) covers6 employee primary pages, manager Team and HR Administration. Duplicate navigation controls share the same go() handler; this does not establish every form/action permutation.

- **QA129 — NOT VERIFIED** — Every action button has a real, correctly scoped behavior.
  Evidence: [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json) is a scoped desktop browser check, not exhaustive coverage of every visible button in every role/state.

- **QA130 — PASS** — Forms validate required fields and date ranges.
  Evidence: [static/index.html](static/index.html) has required fields; [static/js/app.js](static/js/app.js) sets dates and displays API errors; [test_create_vacation_request_invalid_dates](tests/test_requests.py#L27); [test_dates_must_be_from_today_to_one_year_ahead](tests/test_request_rules.py#L23)

- **QA131 — PARTIAL** — Errors are visible and actionable.
  Evidence: [static/js/app.js](static/js/app.js) displays error/toast text; browser checked sign-in/source/refresh success. Recovery guidance for raw mapping/connector error codes and all network failures is incomplete.

- **QA132 — PARTIAL** — Loading and empty states exist.
  Evidence: [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json) observed empty failure queue and disabled refresh; startup briefly displays placeholders. Full loading/failure-state browser coverage is not verified.

- **QA133 — PARTIAL** — State remains correct after refresh where persistence is expected.
  Evidence: [relogin-persistence.json](docs/evidence/qa-2026-10-17/relogin-persistence.json) verifies server progress survives. Browser reload clears in-memory token and returns to sign-in, losing current navigation; stored business records persist.

- **QA134 — PASS** — UI status reflects backend truth rather than hard-coded assumptions.
  Evidence: [test_admin_card_uses_actual_counts_mode_and_last_success](tests/test_integration_gateway.py#L284); [hr-card.png](docs/evidence/qa-2026-10-17/hr-card.png)

- **QA135 — NOT VERIFIED** — Mobile layout is usable.
  Evidence: No mobile viewport/device browser session was executed in this run; responsive CSS alone is insufficient evidence.

- **QA136 — FAIL** — Keyboard navigation and accessible labels are present.
  Evidence: [browser-observations.json](docs/evidence/qa-2026-10-17/browser-observations.json) reproduces keyboard focus escaping an open request dialog to footer Home after 12 Tab presses. Labels/dialog roles exist; focus trapping/background inertness is absent.

- **QA137 — PASS** — Mock data is clearly identified.
  Evidence: [ai-source.png](docs/evidence/qa-2026-10-17/ai-source.png), [hr-card.png](docs/evidence/qa-2026-10-17/hr-card.png); source disclaimers, MOCK mode, prototype/synthetic footer.

- **QA138 — PASS** — Role preview controls are never presented as real authentication.
  Evidence: [static/js/app.js:switchRole](static/js/app.js) graph range is stale; verified actual source uses logout(email), clears auth and prefills email. Backend role authority checked by [test_jwt_role_is_never_authority](tests/test_reliability.py#L57). No instant role token is issued.

## PHASE 8: AUTOMATED TEST EXECUTION

- **QA139 — PASS** — Unit tests
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

- **QA140 — PASS** — API/integration tests
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

- **QA141 — PASS** — Database migration tests
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

- **QA142 — NOT APPLICABLE** — Frontend lint and build
  Evidence: Plain JavaScript/CSS served by FastAPI; no configured frontend lint/build command, package.json or bundler. Executed node --check and5 locale tests instead; no frontend build success is claimed.

- **QA143 — PASS** — Backend lint and type checks, if configured
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

- **QA144 — PASS** — End-to-end tests, if configured
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

- **QA145 — PASS** — Dependency/security audit, if available
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

- **QA146 — PASS** — Docker build and service health checks, if safe and configured
  Evidence: [QA_TEST_RESULTS.md](QA_TEST_RESULTS.md) records executed commands, exit codes, scope and limitations; no external production systems used.

## PHASE 9: REQUIRED ACCEPTANCE TESTS

### Acceptance

- **QA147 — PASS** — A valid signed gateway request is accepted.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60)

- **QA148 — PASS** — An invalid signature is rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60)

- **QA149 — PASS** — An expired timestamp is rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60)

- **QA150 — PASS** — A reused nonce is rejected.
  Evidence: [test_valid_tampered_old_unknown_retired_and_replayed_signatures](tests/test_gateway_service.py#L60); [test_gateway_restart_recovers_jobs_and_nonces](tests/test_gateway_service.py#L140)

- **QA151 — PASS** — Repeating a document request with the same idempotency key creates only one document.
  Evidence: [test_idempotency_persists_and_rejects_changed_body](tests/test_gateway_service.py#L106); [test_concurrent_same_key_creates_one_job_and_document](tests/test_gateway_service.py#L124)

- **QA152 — PASS** — Manager approval succeeds while the gateway is offline.
  Evidence: [test_approval_survives_gateway_down_retries_then_dead](tests/test_integration_gateway.py#L109); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA153 — PASS** — The outbox event remains pending and retries after recovery.
  Evidence: [test_reconciliation_recovers_lost_callback](tests/test_integration_gateway.py#L159); [test_gateway_restart_recovers_jobs_and_nonces](tests/test_gateway_service.py#L140); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA154 — PASS** — Exhausted retries become DEAD and are visible to HR.
  Evidence: [test_approval_survives_gateway_down_retries_then_dead](tests/test_integration_gateway.py#L109); [test_validation_failure_not_retried_and_hr_queue_shows_it](tests/test_integration_gateway.py#L145)

- **QA155 — PASS** — A valid callback updates the external reference and integration status.
  Evidence: [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA156 — PASS** — Repeated callback processing does not duplicate notifications.
  Evidence: [test_signed_full_journey_notifies_exactly_once](tests/test_integration_gateway.py#L79); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA157 — PASS** — Employee tokens cannot invoke privileged callbacks or manager/HR operations.
  Evidence: [test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected](tests/test_integration_gateway.py#L174); [test_all_gateway_endpoints_reject_employee_bearer](tests/test_gateway_service.py#L94); [test_all_administrative_operations_check_role](tests/test_api_matrix.py#L183)

- **QA158 — PASS** — Profile and last-known HR snapshot remain available while the gateway is down.
  Evidence: [test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage](tests/test_integration_gateway.py#L249); [docker-journey.json](docs/evidence/qa-2026-10-17/docker-journey.json)

- **QA159 — PASS** — A manager cannot approve requests outside their authorized scope.
  Evidence: [test_scope_and_hr_queue](tests/test_reliability.py#L132); [test_manager_opens_team_member_card_but_not_others](tests/test_employee_directory.py#L30)

- **QA160 — PASS** — A failed transaction leaves no partial approval/outbox state.
  Evidence: [test_failed_approval_rolls_back_outbox_and_all_business_effects](tests/test_qa_acceptance.py#L89)

- **QA161 — PASS** — Course progress persists after reload.
  Evidence: [test_explicit_enrollment_progress_and_persistence](tests/test_reliability.py#L283); [relogin-persistence.json](docs/evidence/qa-2026-10-17/relogin-persistence.json)

- **QA162 — PASS** — AI Jana returns a source-backed answer or a safe fallback.
  Evidence: [test_ai_grounded_answer_vacation](tests/test_ai.py#L4); [test_ai_safe_fallback_unsupported_question](tests/test_ai.py#L28); [test_conflicting_approved_numbers_fall_back_before_provider](tests/test_qa_acceptance.py#L44)
