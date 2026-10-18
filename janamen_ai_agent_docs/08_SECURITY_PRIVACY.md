# 08 — Security, Privacy, and Audit Requirements

## 1. Threat model

The integration layer handles employee data, possible national identifiers (IIN/BIN), vacation details, HR decisions, signature workflows, API keys/access tokens, and signed documents. Threats include unauthorized access to another employee's request, forged webhook events, duplicate remote document submission, credential leakage, arbitrary file/URL fetches, stale HR data being presented as current, and accidental mutation of official HR records.

## 2. Authentication and authorization

- Authenticate users before returning employee, leave-balance, request, or document information.
- Derive actor ID and roles server-side. Do not trust `employee_id`, `manager_id`, approval status, or role fields supplied by a browser.
- Enforce record/object-level access for every `GET`, `POST`, retry, and download endpoint.
- Employee can see own requests only; manager can act only on requests assigned by an approved mapping/workflow; HR/integration admins have narrower separate capabilities.
- Background workers use service identities and provider-specific least-privilege credentials.
- Approval and external-send operations must check current state in the transaction to guard against race conditions.

## 3. Secrets and tokens

- Keep API keys, passwords, client secrets, bearer tokens, webhook secrets, and private certificates out of Git, frontend bundles, logs, analytics, error trackers, and unencrypted database columns.
- Use a secret manager where available; for local development use untracked `.env` files. `.env.example` may include variable names and blank values only.
- Separate dev/sandbox/live secrets and rotate credentials with an owner/runbook.
- For Documentolog, bearer tokens are scoped to an external document flow per public docs. Store only when needed and protect using a secret manager or envelope encryption; use least privilege and retention limits.
- Ensure HTTP clients do not log authorization headers or full request/response bodies.

## 4. Transport and network

- HTTPS/TLS certificate verification is always on for live calls.
- No `verify=False` workarounds. Fix trust configuration rather than disabling TLS.
- Restrict egress to approved provider endpoints where deployment allows.
- Validate provider URLs before downloading artifacts. Allowlist confirmed Documentolog hostnames; reject `http`, IP-literal, private-network, loopback, link-local, and unapproved domains to mitigate SSRF.
- Attachment URLs shared with Documentolog must be restricted and short-lived where possible, not open public access to all employee documents.
- Limit webhook request body sizes, content types, and processing time.

## 5. Webhook verification

- Verify webhook authenticity using Documentolog's current officially supported method before processing. The public API guide describes payloads/retries but does not specify a cryptographic signature header; this is an unresolved live integration prerequisite.
- Do not invent HMAC header names, signing secrets, algorithms, or provider IP ranges.
- If the provider cannot sign callbacks, obtain a security-approved compensating design in writing and verify whether provider-side network constraints or a supported secret webhook URL can be configured.
- Use constant-time secret comparison where a shared secret is a documented mechanism.
- Deduplicate events and validate that the external document ID maps to an expected request/provider.
- A browser iframe `postMessage` is not proof of an authenticated server-side event. Validate exact origin and source and still wait for a verified backend result.

## 6. PII and data minimization

- Treat IIN, BIN, phone numbers, personal email, full name, leave reason, and signed documents as sensitive data.
- Only transmit the fields needed for the selected integration action.
- Redact identifiers in logs (for example, use internal ID or a one-way stable hash where appropriate). Do not log whole recipient identifiers.
- Avoid duplicating complete signed documents if secure provider retrieval/reference is sufficient. If retention is required, define access policy, encryption, retention, deletion, and audit.
- The document reason may reveal sensitive personal facts; restrict access and avoid putting it into integration error payloads.
- Do not store a document access token inside a query-able event log or analytics event.

## 7. Audit

Record at least:

- request creation/submission/edit/cancel;
- manager/HR approve or reject, actor and reason;
- document submission intent, actual submission result, external ID, outcome-unknown transition, reconciliation result;
- webhook accepted/rejected/duplicate and status transition;
- 1C sync job start/result and mapping/quarantine decisions;
- changes to external ID mappings and integration configuration;
- manual retry/requeue/dead-letter resolution;
- enabling/disabling live writes and who authorized it.

Audit records should be append-only to application roles. Audit payloads must be minimized and redacted. Store correlation IDs to connect logs/jobs/events without leaking PII.

## 8. Fail-closed configuration

- Defaults are mock-only.
- Missing or invalid live credentials prevent the live capability from becoming ready.
- Document submission and 1C write capabilities have independent kill switches.
- Application readiness should clearly report that provider capabilities are disabled/not configured, while keeping mock mode functional where selected.
- Do not offer an admin action that bypasses approval state without explicit audited break-glass policy.

## 9. Security tests required

See `09_TEST_PLAN.md`; include cross-employee data access denial, unauthorized manager approval denial, invalid webhook rejection, duplicate event idempotency, SSRF host rejection, secret redaction, TLS defaults, and live-mode configuration fails closed.
