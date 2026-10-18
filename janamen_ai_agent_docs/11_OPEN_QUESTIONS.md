# 11 — Open Questions, Current Known Gaps, and Go-Live Gates

This file separates project gaps established by the supplied QA report from vendor details not supplied. The coding agent must not infer missing answers.

## A. Existing project issues confirmed by QA (17 October 2026)

- [ ] Initial request idempotency for advance creation: identical duplicate HTTP requests created two business records. Fix before calling request creation fully idempotent.
- [ ] Authorized HR replay/reconciliation and external ID remapping: inspection exists but recovery/resolution actions are missing.
- [ ] Database domain constraints: direct writes can still persist negative balance, reversed dates and unknown request status.
- [ ] Gateway schema lifecycle: initial `create_all` exists; add versioned gateway migrations before schema evolution.
- [ ] Dialog keyboard focus trap/background inertness.
- [ ] Smoke test should succeed on consecutive runs without fixed-date overlap or unsafe cleanup.
- [ ] AI broader semantic conflict/hostile-source evaluation; numeric conflict fix is intentionally limited.
- [ ] AI source data governance: provider default-off and raw user question transport fix do not prove organization approval or that approved source text has no PII.
- [ ] CI, independent worker-process testing, cross-process login throttling assessment, backup/restore, production capacity, mobile browser run and full accessibility coverage.
- [ ] Some integration messages/locales and per-course sample provenance.
- [ ] Runtime/container consistency: the QA report's patched review stack was on port 18766 while pre-existing port 8000 image was not rebuilt.

## B. 1C:ЗУП — required before real connection

- [ ] Exact product/configuration name, localization/release, platform version and deployment mode.
- [ ] Network route/VPN/IP allowlist, TLS certificate chain, inbound/outbound requirements and availability window.
- [ ] Published REST/OData or custom HTTP service? Approved service metadata and actual exposed objects.
- [ ] Authentication/service account, roles/scopes, credential rotation and test infobase.
- [ ] Stable employee key/employee number uniqueness, manager and department mapping, status dictionary, handling of terminated employees.
- [ ] Authoritative leave balance calculation: annual period, leave types, approved/pending requests, partial days/rounding, freshness requirements.
- [ ] Whether the product only reads employee/balance data or must create official 1C leave transactions. Who has approved the business decision?
- [ ] If writing is required: formal API contract, posting sequence, duplicate key, status lookup, cancellation/correction and official transaction reference.
- [ ] Rate limits, page sizes, data retention, support owner, change window, production rollout and rollback.

**Current status:** signed MOCK employee-code snapshots only. Real 1C:ZUP is not verified/connected. Official 1C write-back and payroll payment are not implemented.

## C. Documentolog Business — required before real signing

- [ ] Business account/tariff, customer-specific API contract and sandbox credentials delivered securely.
- [ ] Current production/sandbox hostnames, token lifecycle, scopes/permissions, timeouts and file limits.
- [ ] Actual create response, error schema, document lookup/status-poll API and webhook event schema/version.
- [ ] Whether API supports a stable idempotency key or reliable duplicate lookup/reconciliation.
- [ ] Sender's required identity/signature, signer sequence, legal meaning of statuses, recipient IDs, document templates and approval/sending behavior.
- [ ] Is deferred-send/draft mode supported? Public documentation says the documented create/signing flow sends the document and requires the sender to sign; do not assume otherwise.
- [ ] Vendor-supported webhook authenticity/verification scheme. The current app↔gateway HMAC does **not** verify vendor-originated HTTP unless vendor events pass through a separately verified trusted component.
- [ ] Webhook retries, event identity, duplicates/order guarantees, cancellation, artifact retrieval, signed file access and retention.
- [ ] Data protection/residency, approved recipient PII fields, security/legal approval and operational support contact.

**Current status:** internal mock registration gateway and signed callbacks only. No verified live Documentolog connection or real signing is established by the report.

## D. AI provider and knowledge governance

- [ ] Organization owner has approved whether/when any source text may leave the environment.
- [ ] Provider retention, training usage, data location/residency and contractual commitments reviewed.
- [ ] Approved knowledge source curation checks PII/private data, version/effective date and authoritative precedence.
- [ ] Real provider availability and production HTTP boundary tests, if provider use is approved.
- [ ] Clear fallback and escalation behavior for ambiguous/conflicting policies.

**Current status:** no live provider was called in QA; raw user question egress was fixed in source and provider usage defaults off. This does not prove legal/org approval or absence of private data in approved knowledge.

## E. Production release gates

A live provider can be enabled only after the owner-approved contract, sandbox tests, credentials/secret management, TLS/mTLS and ingress/egress configuration, data governance, idempotency/reconciliation, audited recovery, backup/restore, monitoring, rollback/disable procedure and operational runbook have passed. If any prerequisite remains unknown, keep the capability disabled and explicitly label it MOCK/UNCONNECTED/UNVERIFIED.
