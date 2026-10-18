# Recovery and operations

This runbook applies to JanaМен's canonical **MOCK** gateway. It does not describe a 1C or Documentolog vendor API. Keep `INTEGRATION_GATEWAY_URL` empty to disable gateway delivery. The gateway has no host port and runs on Compose's internal `integration` network. TLS configuration remains available for a future approved deployment; the local Compose demo is not evidence of production TLS or a live connection.

## HR recovery

The HR integration card displays the observed mode, pending count, failed count and last successful operation. The failed queue exposes recovery only for eligible canonical deliveries. HR must enter a reason; employee and manager accounts receive 403.

`POST /api/v1/admin/integrations/queue/{task_id}/retry` takes `expected_retry_count` and `reason`. A compare-and-set update rejects stale or repeated commands with 409. It queues durable intent; it does not change the business approval, leave debit, original document payload or idempotency key. The worker first queries the gateway by that key:

- Existing pending jobs are reattached; registered jobs are reconciled without another registration.
- Exhausted transient (`DEAD`) gateway jobs receive a signed `POST /v1/documents/{idempotency_key}/retry` containing the existing `gateway_job_id` and a fresh `recovery_key`. The command is idempotent within that generation. Only DEAD jobs can reset attempts.
- Validation rejections and invalid legacy contracts require correction. They are not replayable.
- A missing **known accepted** job stops with an operator incident. Restore/reconcile gateway storage before proceeding. Normal polling also refuses automatic resubmission of such a job.
- If no gateway acceptance was ever recorded, a missing job may be submitted using the same immutable key and payload.

Callbacks are refused while a recovery command is pending reconciliation. Once accepted, the generation is persisted and callbacks from prior generations receive 409. Signed callbacks and polling share the same terminal state transition. Duplicate success does not add another document, leave debit or registration notification. Existing signing headers, method/path/query/body binding, nonce storage and timestamp checks are reused unchanged.

`POST /api/v1/admin/integrations/reviews/{employee_code}/resolve` takes the exact queue `observed_at`, a reason, and optionally an existing `user_id`. It fetches a fresh signed snapshot. HR must verify that the external employee code belongs to that account before choosing it. Resolving manager mappings first can be necessary. No account or role is created. Any unresolved manager/source conflict rolls the command back and retains the review. Stale review versions receive 409.

Mapping changes the existing profile's employee code. Historical queued documents retain their original frozen payload. If the former code later arrives from the source, it requires a new explicit review; matching by a person's name is never automatic. Recovery reasons and mapping decisions appear in the audit trail; integration request bodies, signing keys and employee free text are not logged.

## Submission retry contract

`POST /api/v1/requests` accepts an optional `Idempotency-Key` of 16–80 ASCII letters, digits, `_` or `-`. The same employee and key must have the same canonical validated body. Matching retries return the existing request (including its current status); changed bodies return 409. Concurrent retries create one request and one initial event. A key is scoped to an employee. Requests without a key retain the existing create behavior.

The browser creates a key and reuses it after a failed response while the form body remains unchanged. Successful submission or editing the body starts a new submission. Keys and bearer tokens remain in memory. Reload deliberately requires sign-in; review request history before making a new submission after a reload. Only language preference is stored locally.

## Database upgrades

Back up core and gateway stores before upgrade. Run `python -m app.migrate` for the core. Head `0010_source_metadata` adds submission keys, recovery intent/generations, database domain checks, policy metadata and course provenance. Invalid legacy status/date/balance/amount rows cause an explicit stop for operator review. There is no silent repair. PostgreSQL amounts use `NUMERIC(12,2)`; API amount validation retains the configured limit. SQLite guards inserts and updates with triggers rather than rebuilding referenced parent tables. SQLite is not a fixed-decimal storage engine. Downgrades are forward-only; restore an approved backup to roll back.

Gateway startup upgrades its independent schema from unversioned v1 through **v3**, preserving jobs, mock documents, callbacks and nonces. v2 adds `recovery_key`; v3 adds the durable `gateway_rate_limits` table. Unknown future schema versions stop startup. Run schema upgrades with one gateway instance before starting additional workers. Back up before deployment; older service versions refuse a v3 store, so rollback requires a compatible service or an approved restore/reconciliation plan. The local gateway job store is SQLite on a persistent volume; this is not an HA deployment.

## Gateway backup and restoration rehearsal

Use the standard SQLite online backup API, not an ordinary file copy of a running WAL database:

```sh
python -m app.gateway.backup --source /data/gateway.db --destination /data/gateway-backup.db
```

The destination must not exist; the command creates a private mode-0600 file and verifies integrity. Store backups under restricted operator access, outside Git, with the deployment's approved retention/encryption policy. The store contains canonical document payloads and employee codes. Signing keys are supplied separately through environment/secret management.

For restoration, stop gateway and integration workers, retain the incident store, and copy an approved backup to a **new** path:

```sh
python -m app.gateway.backup --source /data/gateway-backup.db --destination /data/gateway-restored.db
```

Point `GATEWAY_DATABASE_URL` at the new file, start one gateway, check the version and signed health response, and reconcile queued jobs before enabling workers. Backup age can omit already completed jobs/nonces. Do not clear an idempotency history or blindly replay missing accepted jobs. The acceptance rehearsal restores a fresh disposable file and verifies the same job/reference, one mock document, and retained nonce rejection. It does not establish production RPO/RTO or PostgreSQL disaster recovery. Use the deployment's PostgreSQL backup tooling and verify a separate restore target before production.

## Policy metadata and CI

HR assigns `policy_key`, integer `priority`, optional inclusive `effective_from`/`effective_until`, and `known_conflict`. Changes invalidate approval and increment the document revision. Reapprove after reviewing all content and metadata. Among currently effective, active, approved, role-accessible sources with the same key, higher priority wins; at equal priority the later effective start wins. Equal winners cause fallback. A relevant approved source flagged with a known conflict also causes fallback before an external model is considered. Missing translation does not permit using an older policy instead. Unkeyed legacy documents retain the literal numeric conflict guard. These rules implement explicit HR precedence, not general semantic contradiction detection or automatic policy approval. A draft flag does not globally block another approved document: deactivate affected sources until HR has completed its review if needed.

File imports preserve hashes of unchanged legacy bundles when new metadata has its defaults. Effective dates serialize as JSON dates; non-default policy changes remain part of the fingerprint and require a new bundle ID/version. Newly seeded example courses are marked synthetic. Older courses with unknown provenance are labelled unverified rather than silently classified.

`docs/ci/quality.yml` defines the isolated SQLite/PostgreSQL acceptance suites, lint, typing, dependency consistency, JavaScript syntax and locale tests. It uses read-only repository permissions and disables persisted checkout credentials. The official action versions are documented by [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), and [setup-node](https://github.com/actions/setup-node). Local execution evidence and any observed GitHub run status are reported separately; adding a workflow does not establish that GitHub has executed it.

The template is **inactive**. GitHub rejected publishing `.github/workflows/quality.yml` because the current token lacks `workflow` scope. The complete proposed active version is retained locally on branch `codex/fix-plan-ci-local`; its identical YAML is saved on GitHub as `docs/ci/quality.yml`. After GitHub authentication is authorized for workflow updates, move the template into `.github/workflows/quality.yml` and push. No GitHub CI run is claimed.

## Combined profile-update history

Current head is `0011_merge_profile_updates`, with both `0010_source_metadata` and `0006_profile_updates` as parents. Upgrade from either branch with `python -m app.migrate`; do not rename/stamp one branch over the other. The original `0009` forward path now recognizes valid profile requests; the merge revision refreshes deployed guards and accepts legacy JSON null without changing rows. Contact approvals remain local and do not generate document jobs. See [PR5 report](PR5_INTEGRATION_REPORT.md).
