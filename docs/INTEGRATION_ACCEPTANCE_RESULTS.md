# Integration acceptance records

Acceptance results are scoped to an executed source revision and environment. MOCK tests do not establish real vendor connectivity or production readiness. Each session retains its exact commands, exits, test names, database target and observed results in its evidence directory.

- [Initial INT-001 through INT-030 matrix](evidence/integration-2026-10-18/acceptance-results.md): historical implementation session.
- [Latest precommit checks](evidence/integration-precommit-2026-10-18/REVIEW.md): secret exclusion, backend recovery/remapping, independent health quota, dedicated disposable PostgreSQL tests and repeated HTTP demo with outage recovery.

The QA checklist links current evidence for its updated recovery, mapping, idempotency and concurrency entries. INT-029 still requires a fresh browser UI check; backend truth is verified separately. Live vendors, production TLS/mTLS, operational readiness and CI activation remain separate gates.
