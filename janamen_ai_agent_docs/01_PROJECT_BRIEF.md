# 01 — Product and Task Brief

## Product

**JanaМен** is a unified HR self-service platform intended to give employees, managers, and HR teams one place to manage HR requests, track approvals, complete document-signing workflows, and access employee/learning information.

## Current planning stage

The known state from the planning conversation is a front-end prototype with simulated employee, manager, and HR views; request flows; academy/learning; Jana AI; and notifications. The prototype was not a production backend and had no real authentication, durable database, or live vendor integration. The coding agent must inspect the current workspace to verify whether those files are present and must not assume that this specification has already been implemented.

## Task for the coding agent

Build the integration architecture and implement a mock-first, end-to-end HR request workflow that can later connect to:

1. **1C:ZUP** — read employee/organization fields and leave balance; in a later approved phase, submit an approved HR operation or obtain an official HR reference if the real configuration supports the needed operation.
2. **Documentolog Business** — create/send an HR document for signing after the correct approvals, receive webhook lifecycle events, show signing status, and associate the resulting official document reference/files with the JanaМен request.

Start by making both providers work through deterministic mock adapters. Real integration is a separate release gate requiring access and configuration discovery.

## MVP scenario

1. An authenticated employee opens JanaМен and submits a vacation request.
2. Backend validates the employee identity, dates, policy constraints available in the app, and idempotency key. Leave-balance information is shown with an `as_of` timestamp and freshness indicator.
3. The request is stored and a durable event/job is created in the same database transaction.
4. The configured manager reviews and approves or rejects the request. The backend verifies manager authority.
5. After approval, JanaМен assembles the correct document and requires an explicit gate before calling the real Documentolog create/send operation.
6. In mock mode, Documentolog returns a stable fake external document ID and simulated signing session.
7. Document status changes arrive through a mock webhook or deterministic simulator. Duplicate and out-of-order events are safe.
8. JanaМен updates the timeline and integration health; it does not conflate approval, signature, and official HR processing.
9. When the configured authoritative requirements are met, the request can become `COMPLETED`. If official 1C processing is not enabled/verified, display that the request is signed but pending HR processing rather than falsely claiming it is recorded in 1C.

## Users and permissions

- **Employee:** create/read own requests; submit or cancel within allowed state; view own document status and result.
- **Manager:** read only requests assigned to them; approve/reject with reason where required.
- **HR operator:** view permitted HR requests, resolve integration exceptions, execute controlled retry/reconciliation actions.
- **Integration administrator:** configure/diagnose integration connections, inspect health, run sync/reconciliation. This role is separate from ordinary HR access where practical.
- **System worker:** service identity with narrowly scoped actions; no interactive login.

All permissions are enforced server-side and audited.

## Core outcomes

- One stable internal request ID and a traceable cross-system correlation ID.
- Durable workflow state and append-only request events.
- Stable mappings between internal IDs and external IDs.
- Employee/leave data marked fresh, stale, missing, or unavailable; never silently replaced by guessed data.
- Safe processing of repeated jobs and webhooks.
- Operator-visible errors with retryability and recovery instructions.
- A mock demo that works without vendor accounts or secrets.

## Explicit non-goals for the mock MVP

- Do not implement arbitrary writes to 1C.
- Do not invent official HR policy, approval hierarchy, vacation entitlement rules, or payroll logic.
- Do not use real employee IIN, phone numbers, credentials, or documents in mock fixtures.
- Do not pretend mock signatures are legally valid.
- Do not attempt document creation in Documentolog before the final live workflow, signing requirements, and recipient identity are confirmed.

## Success criteria

See [`09_TEST_PLAN.md`](09_TEST_PLAN.md) for testable acceptance criteria and [`11_OPEN_QUESTIONS.md`](11_OPEN_QUESTIONS.md) for decisions required before live deployment.

## Existing product and test baseline

The supplied QA report describes an existing FastAPI backend plus plain static HTML/CSS/JavaScript UI, with employee, manager and HR views; DB-backed authentication; requests, approvals, notifications, audit history; academy course progress; source-grounded AI Jana; integration health/profile snapshot controls; and a separate internal mock gateway. Course progress persistence, authorization matrix behavior, the request path, mock gateway recovery and snapshot outage behavior have test evidence.

As of the report dated 17 October 2026, overall readiness was **NEEDS WORK**, despite 400 passing tests on each of SQLite and PostgreSQL. Real 1C:ЗУП and Documentolog were not connected. See `00_CURRENT_PROJECT_STATE.md` for exact current-vs-planned distinctions and `12_QA_REMEDIATION_PLAN.md` for the next work items.
