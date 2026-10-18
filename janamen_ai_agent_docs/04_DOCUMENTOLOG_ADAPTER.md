# 04 — Documentolog Business Adapter Specification

## 1. Role and important live-side effect

Documentolog owns the external electronic-document/signature lifecycle. JanaМен creates the request and controls whether it is eligible for signing; Documentolog owns the resulting document ID, signing status, and provider-returned artifacts/links.

**Critical:** the public Documentolog Business API documentation describes a combined create/access-token flow in which a document is created, and says a document cannot be created as a draft; creation sends it to the recipient immediately. It also says the sender (`sSender`) must be a signer. Therefore, the live operation is an externally visible side effect, not a harmless “prepare draft” call. Do not call it until approval, signer/recipient information, document bytes, and final sending consent are verified. Confirm any alternative workflow with Documentolog before assuming it exists.

Official public guide: <https://documentolog.com/en/integrations-business/api>

## 2. Provider API facts documented publicly

These facts come from the linked public guide and still must be checked against the customer account/contract:

- API access is obtained in the Documentolog Business account's Integrations → API Documentolog area; the guide describes access to the API under a Business plan.
- Document creation/token request is documented at `POST https://apibusiness.documentolog.com/json/external/oauth/token` with an `api-key` header and JSON request body.
- The response example contains `status`, `data.access_token`, `scope`, and `token_type`; the guide says the access token is valid for 30 days and is passed as `Authorization: Bearer <token>` for API access.
- The documented request contains `aAttachments`, `sSetWebhookUrl`, `iSendToRecipient`, `mRecipient`, `mPhonesForSms`, `iRecipientSignatureRequired`, `mAvailableSignatureMethodsForRecipient`, `mAvailableSignatureMethods`, and `sSender`.
- Recipient identifiers may be IIN, BIN, phone number, or email in the public guide. Use the identifier and signing route explicitly approved by the organization; treat identifiers as sensitive.
- Document formats listed include doc/docx, xls/xlsx, ppt/pptx, pdf, rar/zip, rtf, TIFF, JPEG/JPG, PNG, and GDoc. The filename before the extension must not exceed 32 characters per the guide.
- The webhook examples include `document_sent`, `signer_signed`, `signer_declined`, and `document_completed`. All use the same `doc_id` for a document; signer events include signer name and recipient identifier. The completion event can contain document and download links (including variants with EDS).
- The guide's webhook retry schedule is 5, 15, 30, 60, 120, 240, 480, 960, and 1440 minutes, after which it marks the event failed and stops retrying.
- The guide says links in the completion payload require the same access token in a Bearer authorization header to download. Do not treat them as public URLs or expose them to the browser without authorization controls.
- The guide lists limitations including no draft creation and mandatory sender signature. It also describes an iframe signing flow and `postMessage` signals.

The public guide does **not** establish that a cryptographically signed webhook, universal polling endpoint, idempotency header, or custom customer-specific state API is available. Ask Documentolog to confirm each item rather than assuming it.

## 3. Internal adapter contract

Use an internal normalized contract so domain services never depend on the public API's `s`/`i`/`m` field naming.

```python
class DocumentAdapter(Protocol):
    async def submit_document(
        self, payload: "DocumentSubmission", idempotency_key: str
    ) -> "DocumentSubmissionResult": ...

    async def get_document_status(
        self, external_document_id: str
    ) -> "DocumentStatusResult": ...

    async def verify_webhook(
        self, headers: Mapping[str, str], raw_body: bytes
    ) -> "WebhookVerificationResult": ...
```

`get_document_status` and `verify_webhook` may have restricted real implementations until the provider confirms supported mechanisms. Do not fabricate endpoints or signature schemes. A capability registry may declare `webhook_signature_verification`, `status_polling`, `idempotent_create`, and `document_download` as `SUPPORTED`, `UNSUPPORTED`, or `NOT_CONFIRMED`.

`DocumentSubmission`

- `janamen_request_id: UUID`
- `correlation_id: UUID`
- `document_type: str` (mapped via approved document-type catalogue)
- `title: str`
- `attachment_url: str` (short-lived, HTTPS, provider-reachable, access-controlled)
- `sender_identifier: str` (IIN/BIN or approved sender identity; sensitive)
- `recipients: list[DocumentRecipient]`
- `sender_signs: bool` (must be true for the public flow unless vendor confirms otherwise)
- `recipient_signature_required: bool`
- `recipient_signing_methods: list[str]`
- `sender_signing_methods: list[str]`
- `send_now_confirmed: bool`

`DocumentRecipient`

- `recipient_identifier: str` (sensitive)
- `display_name: str | None`
- `phone_for_sms: str | None` (sensitive; only for approved SMS path)
- `signing_required: bool`

`DocumentSubmissionResult`

- `state: enum(ACCEPTED, REJECTED, UNKNOWN, UNSUPPORTED)`
- `external_document_id: str | None` (normalize from provider `doc_id` or documented response mapping)
- `access_token: SecretStr | None` (do not persist in ordinary request JSON or logs; encrypted, access-limited storage only if required to resume a session)
- `signing_session_url: str | None` (must have strict user/tenant authorization and safe token handling)
- `safe_message: str | None`
- `correlation_id: UUID`

`ExternalDocumentEvent`

- `provider: Literal["documentolog"]`
- `external_document_id: str`
- `event_type: enum(DOCUMENT_SENT, SIGNER_SIGNED, SIGNER_DECLINED, DOCUMENT_COMPLETED, UNKNOWN)`
- `occurred_at: datetime | None` (if supplied; don't invent if not)
- `recipient_ref_hash: str | None` (prefer hashed/redacted identifier; avoid unnecessary PII)
- `document_url: str | None`
- `download_url: str | None`
- `payload_digest: str`

## 4. Provider request mapping (only fields demonstrated by public docs)

Internal value → public field → notes:

- `attachment_url` → `aAttachments: [url]` → URL must be reachable by provider and safely serve the approved document. Confirm authentication/allowlisting/file-size requirements.
- `webhook_url` → `sSetWebhookUrl` → public URL; webhook authentication/verification contract still needs provider confirmation.
- `send_now_confirmed` → `iSendToRecipient` → docs describe 1=yes and 0=no but also state no draft creation; never use `0` as a delayed-send/draft guarantee without written confirmation.
- `recipients[].recipient_identifier` → `mRecipient` → use only contract-approved identifier types and formats.
- SMS details → `mPhonesForSms` → only populate when the SMS signing process is explicitly selected and all required data is available.
- `recipient_signature_required` → `iRecipientSignatureRequired` → encode as provider's expected 1/0 representation.
- recipient methods → `mAvailableSignatureMethodsForRecipient` → allowed example values: `eds`, `egov-qr`, `adobe-sign`, `sms`.
- sender methods → `mAvailableSignatureMethods` → same example values in public guide.
- sender identifier → `sSender` → guide says IIN or BIN; sender must be a signer.

The documented endpoint is a create/token request, not merely an OAuth handshake that can safely be performed early. Do not request a token for a real document before the domain-level send gate is satisfied.

## 5. Webhook mapping

Documentolog's public examples:

```json
{"event":"document_sent","doc_id":"KZ000000000000000001234567"}
```

```json
{
  "event":"signer_signed",
  "doc_id":"KZ000000000000000001234567",
  "signer":{"name":"Example Name","recipient":"redacted-recipient"}
}
```

Completion may include `document`, `download_all_files`, `download_files`, `download_files_with_eds`, and `download_files_with_eds_ez`. Treat URLs as provider-controlled data: require HTTPS, validate the host against an allowlist, never fetch arbitrary URLs from a user-controlled payload, and attach the required Bearer token only to verified provider domains.

**Webhook event identity:** public examples do not show a unique event ID. Deduplicate with a canonical idempotency fingerprint such as `(provider, doc_id, event, normalized signer recipient hash, payload digest)` and keep the raw-body digest. Make the processing idempotent even when the same callback is delivered more than once. Persist all distinct signer actions; do not deduplicate two different signers just because the event type matches.

**Webhook authentication:** the public guide shows event shapes and retry behavior but does not describe a cryptographic signature header. Do not invent a signature algorithm. Before live webhook go-live, obtain the provider's official webhook verification method. If none is offered, agree a compensating design with provider/security owner (e.g., source-network restrictions where documented, a hard-to-guess endpoint secret if supported, and status reconciliation); do not assume that JSON shape alone authenticates the caller.

## 6. Iframe and browser safety

The public guide documents an iframe URL of the form `https://apibusiness.documentolog.com/external/sign/embedded?sParams=<token>` and messages like `{isDocumentolog:true, type:'sign', success:true|false, signType:'eds'|'egov_gr'}`, as well as `user-close` and `already-signed`.

If implemented:

- Never trust `postMessage` alone as proof of legally complete signing. Verify `event.origin` against the exact confirmed provider origin and validate `event.source`/payload; then rely on the authenticated webhook or other verified server-side provider result.
- The iframe token must be scoped to the current authorized request and delivered only to the entitled user. Never save it to localStorage, analytics, or logs.
- Set a restrictive `Content-Security-Policy`/`frame-src`, `Referrer-Policy: no-referrer`, and avoid third-party scripts on the signing page.
- The signing token appears in the query parameter shown by the public doc; prevent URL/token capture in access logs, browser analytics, error telemetry, and referrer headers as far as the integration design permits.
- Provider iframe origin, postMessage payload, iframe requirements, and token lifecycle must be reverified before production.

## 7. Status mapping

Map provider events to internal document statuses, never directly to overall HR completion:

| Provider event | Internal document status | Meaning |
|---|---|---|
| no external document yet | `NOT_CREATED` | No remote submission attempted |
| create request in progress | `SUBMISSION_PENDING` | Job queued/being sent |
| response timeout after request may have reached provider | `SUBMISSION_UNKNOWN` | Must reconcile before resubmission |
| `document_sent` | `SENT` | Provider says sent to recipient |
| `signer_signed` | `PARTIALLY_SIGNED` | One signer completed a step; more may remain |
| `signer_declined` | `DECLINED` | A signer declined; HR/operator resolution required |
| `document_completed` | `SIGNED` | Provider says all parties have signed |
| validation/permission error | `FAILED` | Known failure; non-retryable until corrected |
| manually cancelled under approved policy | `CANCELLED` | Cancellation confirmed/recorded |

A provider event may arrive out of order. Store each event first, then recompute current state from the event history/state-transition rules. Never let a stale `document_sent` event downgrade a `SIGNED` document.

## 8. Failure modes and recovery

- `401 invalid_client`: incorrect API key; stop retries, alert integration admin, rotate/fix secret.
- `401 unauthorized`: public guide says token may be missing/expired (30-day validity); renew via the documented process only when safe for the existing document session. Do not recreate a document to get a token.
- HTTP `200` with body `status: 0`: treat as logical error, inspect `message` after redaction; do not classify as success solely from the HTTP code.
- Network timeout after create call: `SUBMISSION_UNKNOWN`; check provider UI/API/official status route or contact operator. No blind retry.
- Webhook not received: Documentolog retries on the public schedule through 24 hours/next-day window; JanaМен should independently reconcile pending documents when a supported status read is available or raise a manual check after the configured threshold.
- Download link failure: confirm the same token is attached as Bearer, the token is still valid, host matches allowlist, and access to the specific document is authorized. Don't expose the signed file to another employee.
- Unsupported required signing configuration: stop the submission and route to HR/operator; do not silently drop signatures or recipient requirements.

## 9. Configuration placeholders

```dotenv
DOCUMENTOLOG_ADAPTER=mock
DOCUMENTOLOG_BASE_URL=https://apibusiness.documentolog.com
DOCUMENTOLOG_API_KEY=
DOCUMENTOLOG_WEBHOOK_URL=
DOCUMENTOLOG_SENDER_IDENTIFIER=
DOCUMENTOLOG_ALLOWED_HOSTS=apibusiness.documentolog.com,business.documentolog.com
DOCUMENTOLOG_CONNECT_TIMEOUT_SECONDS=3
DOCUMENTOLOG_READ_TIMEOUT_SECONDS=15
DOCUMENTOLOG_LIVE_SEND_ENABLED=false
DOCUMENTOLOG_WEBHOOK_VERIFICATION_MODE=not_configured
```

The base URL above is the public API host shown in the vendor guide, but do not assume a sandbox uses the same host. Keep environment-specific URL configuration and enforce TLS.

## 10. Go-live checklist

- Confirm account plan, API access, environments, current API spec/version, request/response schemas, file limits, sender/recipient identity rules, signing methods, and supported document types.
- Obtain a vendor-confirmed example response for create success, logical failure, expired token, and duplicate request.
- Confirm whether remote idempotency, status polling/search, cancel, and exact webhook authentication exist.
- Confirm the sender's legal/organizational identity and required signing order.
- Confirm whether the business process can tolerate immediate sending; the public API guide says drafts are not supported.
- Verify hosted attachment URLs cannot be accessed by unauthorized parties and expire or become unusable after a defined period where appropriate.
- Run with test recipients and sample non-sensitive documents before any real employee use.
- Approve a manual recovery runbook for unknown submission outcome and missed webhooks.

## Existing JanaМен implementation status (QA baseline 2026-10-17)

The current integration is a **mock registration gateway**, not a live Documentolog connector and not evidence of actual signing. Preserve these working components:

- App-side `app/integrations/outbox.py`: immutable approval-time payload, stable request idempotency key, PostgreSQL-safe claim pattern, bounded jittered retry, signed gateway request and idempotent terminal result application.
- Internal `app/gateway/main.py` / `runtime.py`: HMAC machine authentication, durable nonce/replay protection, async persisted jobs and leases, persistent retries and callback reconciliation.
- `app/gateway/connectors.py`: deterministic persisted mock document reference for a given logical job; controlled failure/rejection scenarios.
- `app/routers/internal.py`: signed internal callback validation and replay protection.

The current integration statuses include `NOT_REQUIRED`, `PENDING`, `SENT`, `REGISTERED`, `FAILED`, and `DEAD`; use the existing schema/UI meanings. `REGISTERED` is not a claim of signed/completed real Documentolog document. Approval remains approved when registration fails.

The HMAC protocol described in the code authenticates JanaМен-to-internal-gateway calls/callbacks. It is not proof that real Documentolog webhook events can be authenticated. Live vendor connectivity, production inbound mTLS, webhook source authenticity and vendor contract tests are unverified. Do not implement a vendor-shaped HTTP client by guessing endpoints/payloads. Extend the current gateway connector seam once the real contract is supplied.

Important current issue: failure/dead records can be inspected but an audited HR-only replay/reconciliation operation is missing. Implement that without changing immutable keys or blindly recreating remote documents.
