# Integration acceptance — 18 October 2026

Mode: **MOCK**. Core tests own temporary SQLite files or random schemas in a newly created PostgreSQL17 container. Gateway tests own temporary stores. Runtime evidence uses the isolated `janamen-int-20261018` project with synthetic identities. No live 1C, Documentolog or Gemini request was made.

The supplied QA report's 400 tests is historical. The checked-out baseline `eafbaa7` passed 484 tests on each database in this session. The final source adds 11 cases: two signing vectors, durable limits/restart, concurrent limits on both database engines, v2 migration retention, redaction/size limits, private environment generation, repeatable pending demo, callback atomicity and two independent PostgreSQL worker cases. Full commands/exits are in [commands.json](commands.json); actual case results are in the final JUnit XML/logs. `PASS` below means the stated local MOCK assertion, not real-vendor certification.

Commands `S` and `P`: `.venv/bin/python -m pytest -q --junitxml=<evidence>/final-{sqlite,postgresql}.xml`. `P` sets `TEST_DATABASE_URL` from the private isolated test environment; no DSN is committed. The test fixture creates/drops only its own random schema. Case names below are exact pytest function names; parameter instances are recorded in JUnit.

| ID | Scenario | Result | Executed evidence |
|---|---|---|---|
| INT-001 | Valid signed request persists a job | PASS | S/P `test_valid_tampered_old_unknown_retired_and_replayed_signatures`; [running gateway probe](runtime-security.json) |
| INT-002 | Altered signature/raw body rejected without effect | PASS | S/P same case; `test_gateway_security_errors_and_logs_exclude_private_values`; running probe jobs unchanged |
| INT-003 | Expired/future timestamp rejected | PASS | S/P `test_signing_openssl_golden_vectors` (inclusive ±300, reject ±301), existing gateway signature case; running expired probe |
| INT-004 | Durable nonce replay prevention | PASS | S/P `test_gateway_restart_recovers_jobs_and_nonces`; `test_signed_limits_survive_restart_and_reset_per_key_per_minute`; running replay probe |
| INT-005 | Unknown/retired key rejected; intended overlap accepted | PASS | S/P `test_valid_tampered_old_unknown_retired_and_replayed_signatures`; running unknown-key probe; sanitized authentication log regression |
| INT-006 | Same document key/body returns same job/document | PASS | S/P `test_idempotency_persists_and_rejects_changed_body`, `test_concurrent_same_key_creates_one_job_and_document` |
| INT-007 | Same key/changed body conflicts | PASS | S/P `test_idempotency_persists_and_rejects_changed_body` |
| INT-008 | 202 is durable acceptance, separate from registration | PASS | S/P gateway idempotency and `test_signed_full_journey_notifies_exactly_once`; source retains canonical PENDING receipt semantics |
| INT-009 | Callback applies reference/history/audit/notice once | PASS | S/P `test_callback_audit_failure_is_atomic_and_retry_has_one_set_of_effects`; [runtime counts](runtime-journey.json) |
| INT-010 | Unsigned/modified callback denied | PASS | S/P `test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected` |
| INT-011 | Freshly signed semantic duplicate has no extra effects | PASS | S/P `test_callback_audit_failure_is_atomic_and_retry_has_one_set_of_effects`, `test_signed_full_journey_notifies_exactly_once` |
| INT-012 | Gateway outage preserves approval/outbox/profile | PASS | S/P `test_approval_survives_gateway_down_retries_then_dead`; actual [stopped-gateway smoke](outage-pending.txt) |
| INT-013 | Recovery registers original key once | PASS | Actual [recovery smoke](outage-recovered.txt) and runtime document/notice/audit counts; S/P `test_hr_recovery_preserves_document_key_and_rejects_old_callbacks` |
| INT-014 | Transient failures use persisted bounded backoff | PASS | S/P `test_mock_connector_temporary_failure_reaches_dead_without_document`, `test_approval_survives_gateway_down_retries_then_dead`; test time is advanced rather than waiting hours |
| INT-015 | Terminal validation rejection stops; HR sees reason | PASS | S/P `test_validation_failure_not_retried_and_hr_queue_shows_it` |
| INT-016 | Retry exhaustion persists DEAD and HR alert | PASS | S/P temporary connector and gateway-down cases above |
| INT-017 | Lost callback reconciles without duplicate document | PASS | S/P `test_reconciliation_recovers_lost_callback`, `test_callback_retry_is_persistent_and_never_registers_twice` |
| INT-018 | Restart recovers gateway processing lease | PASS | S/P `test_gateway_restart_recovers_jobs_and_nonces`, `test_separate_gateway_processes_claim_one_document`; actual runtime services recreated retaining stores |
| INT-019 | Separate application processes claim safely on PostgreSQL | PASS | P `test_postgresql_independent_workers_and_acceptance_crash[False]` (second returns before locked first ack), `[True]` (process exits after gateway acceptance, retry preserves one job/document); intentionally skipped in S |
| INT-020 | Employee-code snapshot updates source/freshness/balance | PASS | S/P `test_profile_sync_code_matching_and_provisional_balance` |
| INT-021 | Unknown employee/manager quarantined; no account creation | PASS | S/P `test_unmatched_employee_and_manager_go_to_review`; existing audited mapping cases in `test_fix_plan.py` |
| INT-022 | Snapshot survives outage and becomes stale | PASS | S/P `test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage`; actual outage smoke reads profile |
| INT-023 | HR-only throttled audited refresh | PASS | S/P same refresh case; persisted sync/audit behavior is exercised |
| INT-024 | Wrong manager scope denied by backend | PASS | S/P `test_scope_and_hr_queue` and existing request/RBAC matrix cases |
| INT-025 | Employee cannot use manager/HR/machine routes | PASS | S/P `test_all_gateway_endpoints_reject_employee_bearer`, callback case; actual smoke uses real employee bearer denials |
| INT-026 | Serial/concurrent initial submission creates one request | PASS | S/P `test_submission_retry_is_employee_scoped_and_immutable`, `test_concurrent_submission_retries_create_one_request`; repeatable demo checks same ID/key and no second debit |
| INT-027 | Write faults roll back approval and callback effects | PASS | S/P parameterized `test_failed_approval_rolls_back_outbox_and_all_business_effects`, `test_failed_notification_rolls_back_entire_approval`, new callback audit-fault regression |
| INT-028 | Repeated smoke passes without resetting data | PASS | [integration first](smoke-first.txt)/[repeat](smoke-repeat.txt); original [ten-step first](full-smoke-first.txt)/[repeat](full-smoke-repeat.txt) |
| INT-029 | UI reports truthful UNCONNECTED/MOCK mode | PARTIAL | S/P `test_without_gateway_approval_queues_nothing`, `test_admin_card_uses_actual_counts_mode_and_last_success`; actual smoke sees MOCK cards, and schemas reject live mode. UI is unchanged and was not newly exercised in a browser this session; earlier screenshots remain historical |
| INT-030 | Error/log redaction and payload minimization | PASS | S/P `test_gateway_security_errors_and_logs_exclude_private_values`, callback atomicity/private marker, `test_signed_full_journey_notifies_exactly_once`, existing AI boundary tests; [scoped file/container-log scan](log-and-secret-scan.json) |

## Scope and unresolved gates

There are **29 PASS and one PARTIAL** scenario, with no failing automated case claimed as passed. The two PostgreSQL-only cases must run on PostgreSQL to satisfy INT-019; SQLite skips are explicit. Application worker acceptance/crash tests use a local persisted gateway runtime as their transport seam. Full-stack signed HTTP/callback behavior is separately exercised through Docker and API tests.

Security evidence covers the inspected code, synthetic inputs and known secret markers. It is not a general penetration test, exhaustive secret detector or production sign-off. Fixed-window quota permits boundary bursts and each overlapping signing key owns its own quota. Browser/mobile/accessibility revalidation, production TLS/mTLS/rotation, shared user-login throttling, monitoring/HA/load and production restore objectives remain open. The CI template is inactive due to the previously recorded workflow permission limitation; no GitHub Actions result is claimed. Real vendor/API/signature/leave semantics and organizational data approvals require partner input.
