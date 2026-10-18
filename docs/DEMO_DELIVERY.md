# Public synthetic demo delivery

This is the delivery plan for a public hackathon demonstration. Use synthetic employees and MOCK integrations only. The team wants a video, presentation, clean repository, documentation and hosted demo. Hosting is a team proposal; this document does not establish an organizer requirement or submission deadline.

## Deliverables and current state

| Deliverable | Current state | Completion evidence |
|---|---|---|
| Source and local Git history | Saved on the integration feature branch | Clean working tree and commit SHA |
| GitHub copy | Integration changes pushed | Remote branch SHA matches local HEAD |
| Backend integration verification | Completed for MOCK scope | [Acceptance index](INTEGRATION_ACCEPTANCE_RESULTS.md) and linked dated evidence |
| Reproducible instructions | Available | [Demo runbook](INTEGRATION_DEMO_RUNBOOK.md) |
| Demo video | Recording script prepared; video not recorded | Final MP4, playback check and submission link |
| Presentation | Seven-slide outline prepared; deck not rendered | PDF and editable deck, checked at presentation resolution |
| Hosted public demo | Not deployed by this delivery plan | Verified HTTPS URL and hosted acceptance record |

GitHub is the source delivery location. Store large video exports in the chosen submission/file platform and link them from the final handoff. Keep credentials out of slides, recordings, repository and evidence.

## Three-minute recording script

Prepare a fresh isolated environment with the runbook. Rehearse first; select an unused valid leave date. Use separate employee, manager and HR browser sessions. Record only the application window, with credentials entered before recording. Put a visible “Synthetic demo · MOCK 1C / Documentolog” caption in the recording. Do not show private environment files, terminal history or personal browser tabs.

| Time | Screen | Talk track |
|---|---|---|
| 0:00–0:20 | Employee dashboard | “JanaMen gives employees one place for HR requests, learning and answers from approved knowledge.” |
| 0:20–0:50 | Employee request form and created request | “An employee submits leave. The backend checks permissions and balance and records the request.” |
| 0:50–1:15 | Assigned manager's queue | “The manager approves within their team scope. Approval and external registration have separate states.” |
| 1:15–1:45 | Employee request detail and notification | “The durable outbox sends the approved request through a private gateway. MOCK Documentolog returns a reference; the employee receives one registration notification.” |
| 1:45–2:15 | Prepared outage scenario, then recovered status | “During a gateway outage the approval stays saved. Delivery resumes after recovery without a second registration.” |
| 2:15–2:35 | HR integration view | “HR can inspect failures and use audited recovery. Backend permissions protect these actions.” |
| 2:35–3:00 | Architecture slide and repository link | “The tested boundary is synthetic. Real vendor APIs require approved contracts and sandbox access. The repository includes repeatable tests and operations documentation.” |

The timing is a rehearsal target, not a verified video. Pre-stage the outage scenario using the runbook; show pending and recovered states with an explicit time-cut caption if recovery is edited. Do not present an API test as a completed browser demonstration. Include exact-one registration and repeat-submission evidence from the runbook as a short caption or appendix, without exposing tokens. If a UI view does not expose a claimed field, show sanitized evidence and label it clearly.

## Seven-slide presentation outline

1. **Problem and audience.** Employees, managers and HR need a shared request history and clear ownership. Describe the problem as the team's case interpretation; avoid unsupported savings figures.
2. **Product journey.** Employee submits → assigned manager approves → employee sees status and notification. Include one real application screenshot with synthetic data.
3. **Working demo.** Show the live journey or play the recording. Keep a local recording available if the network fails.
4. **Architecture.** Browser → FastAPI/PostgreSQL → outbox worker → private gateway → MOCK 1C and Documentolog → signed callback/reconciliation. Label the two stores and private boundary.
5. **Reliability and access.** Submission idempotency, durable retries, separate business/integration states, audited HR recovery and role/object scopes. Reference the dated test evidence; distinguish automated tests from browser checks.
6. **What is proven and what remains.** MOCK backend flow is verified. Live vendor APIs, enterprise rollout and production security remain separate gates. Present only measured results and keep their test environment/date visible.
7. **Delivery and next step.** Repository, runbook, video and verified demo URL when available. Next step: partner-approved sandbox contracts and mappings. Do not place private administrative credentials on the slide.

## Hosting plan

A dedicated public IP is not a visitor requirement. For example, [Render web services](https://render.com/docs/web-services) provide an HTTPS subdomain; a custom domain is optional. A Docker-capable VPS is another deployment shape, with a public IP for administration and a domain/TLS reverse proxy for visitors. Provider selection and budget are still open.

The proposed service layout is:

| Component | Exposure | Persistence |
|---|---|---|
| JanaMen web/API and static UI | Public HTTPS through an edge/reverse proxy | Private PostgreSQL |
| Integration outbox worker | Private, continuously running | Same application PostgreSQL |
| MOCK gateway | Private; reachable by worker and callback path | Its own durable gateway store |
| PostgreSQL | Private; no public database port | Persistent database storage |

Render has [background workers](https://render.com/docs/background-workers), [private services](https://render.com/docs/private-services) and [persistent disks](https://render.com/docs/disks). Its disks require eligible paid services and ordinary service filesystems are ephemeral. This makes it a candidate, not a verified deployment target or cost quotation. A static frontend deployment alone does not host this complete integration journey.

The current Compose setup is for a local demo: loopback bindings, private HTTP and development configuration. It must not simply be exposed to the internet. Before deployment, prepare a reviewed hosting configuration covering HTTPS, trusted proxy/host handling, public request limits, private service routing, strong independent secrets, restricted demo access and persistent storage. Keep external AI disabled. Preserve production guards; do not weaken them to make a demo boot. Public synthetic data does not make privileged shared accounts safe: distribute reviewer access privately and prevent anonymous administrative access.

Required operator inputs: provider/account access, approved spending limit, region, desired availability period, optional domain and who receives reviewer credentials. Supply secrets through the provider or a private environment file, never chat or Git. No server address or public URL exists as a result of this plan.

## Hosted acceptance and handoff

1. Deploy an isolated synthetic dataset; record source SHA, migrations and gateway schema version. Verify persistence after a service restart.
2. Open the HTTPS URL from a separate device/network. Check login, static assets and the employee/manager/HR scopes.
3. Run the documented happy path twice against that isolated demo and verify one request/debit/registration/notification. Repeat outage and recovery. Local evidence does not establish hosted success.
4. Confirm PostgreSQL and gateway are unreachable publicly and secrets are absent from public responses, screenshots and logs.
5. Export and play the final video and PDF; check links and organizer format/time requirements before submission.
6. Record actual URL, source SHA, verification date, expiration/availability window and evidence links in a dated handoff. Keep repeatable instructions separate from session observations.

For this documentation-only change, review links and whitespace; no application behavior changes require rerunning the full backend suite. The prior integration results remain historical evidence, not a new test run.
