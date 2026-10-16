# JanaМен API contract

Base: `/api/v1`. JSON bodies. Existing response fields remain unless a misleading integration claim must change. Generated OpenAPI at `/openapi.json` is the detailed schema; `/docs` is the interactive reference.

Identity: `Authorization: Bearer <token>`. Login returns a signed JWT with `sub`, `jti`, `iat`, `exp`, and a persisted session. Every protected request verifies signature, expiry, active session and active user, then derives role from the database. Logout revokes the current session. Browser tokens remain in memory. No cookie authentication or refresh token is introduced.

Errors retain a string `detail` for compatibility and add `error: {code, message, fields}` plus `request_id`. Field errors contain location and message, never raw input, credentials or database text. Statuses: 401 unauthenticated, 403 forbidden, 404 missing/not-owned notification, 409 invalid transition/uniqueness conflict, 422 invalid input, 429 login throttled, 503 unavailable database, 500 unexpected error. Request IDs also appear in `X-Request-ID`.

| Method and path | Input / response | Authorization and validation |
|---|---|---|
| GET `/config` | demo mode and synthetic account emails; no passwords | Public; demo hints omitted outside demo mode |
| POST `/auth/login` | `{email,password}` → `{access_token,token_type,expires_in,user}` | Email syntax, bounded nonempty password, throttled failed attempts |
| POST `/auth/logout` | current token → success | Revokes its persisted session |
| GET `/me`, `/me/profile`, `/me/dashboard` | current user, HR fields, balances, course summary, counts | Current user only; no write endpoint for official profile fields |
| GET `/requests` | optional status/type → own requests | Identity comes exclusively from authentication |
| POST `/requests` | `{type,start_date,end_date?,amount?,reason?}` → 201 request | Vacation dates ordered, inclusive calendar days, sufficient balance at submission and approval; advance requires finite positive amount with at most two decimals; bounded reason; reject unknown fields |
| GET `/requests/{id}` | request and immutable application history | Owner, direct manager, or HR; positive ID |
| POST `/requests/{id}/approve`, `/reject` | optional `{action?,comment?}` → detailed request | Manager direct reports or HR; no self-review; action must agree with route; only Pending can transition; conditional database update prevents duplicate actions |
| GET `/manager/requests`, `/manager/team` | queue/team, optional status | Direct reports for manager, company scope for HR |
| GET `/notifications/unread-count` | `{unread}` independent of list limit | Current user only |
| GET `/notifications` | bounded limit → own notifications | Owner scope |
| PATCH `/notifications/{id}` | `{is_read:boolean}` → notification | Owner scope; supports read and unread |
| POST `/notifications/read-all` | count updated | Own notifications only |
| GET `/courses`, `/courses/{id}` | catalog/detail, assigned flag, progress, score, completion timestamp | Authenticated catalog; reads never create enrollments |
| POST `/courses/{id}/enroll` | current user → enrollment/course | Explicit, idempotent self-enrollment; persistent assignment notification |
| GET `/courses/lessons/{id}` | material/options, never correct answer | Authenticated |
| POST `/courses/lessons/{id}/quiz` | `{answer_index:integer}` → pass, progress/result | Assigned course required, index in bounds, serialized enrollment update, completion notification once |
| POST `/ai/chat` | `{question}` → answer, status, sources, escalation | 1–2000 nonblank characters; approved/active documents filtered by database role; no employee records enter retrieval |
| GET `/ai/documents` | Approved document titles/versions visible to this user | Approval, activity and role filtering |
| GET `/ai/sources/{id}` | exact document/version/section/content | Same approval and role checks as retrieval |
| GET/POST `/admin/knowledge/documents` | list/create document metadata | HR only; new documents are drafts |
| PATCH `/admin/knowledge/documents/{id}` | title/category/version/active/approved | HR approval explicit; metadata edits invalidate previous approval unless explicitly reapproved |
| GET/POST `/admin/knowledge` | list/create chunks | HR only; bounded text, existing document, access level all/employee/manager/hr_admin; adding content invalidates approval |
| PATCH `/admin/knowledge/{id}` | section/content/tags/access level | HR only; edits invalidate parent approval |
| POST `/admin/enrollments` | `{user_id,course_id}` → course/enrollment | HR only; existing active employee and course |
| GET `/admin/summary` | Active account, pending request and chunk counts | HR only |
| GET `/admin/audit` | bounded limit → events | HR only; minimal metadata, no auth tokens/raw AI questions |
| GET `/admin/integrations` | unconnected status | HR only; no external connection, fabricated sync count or live last-sync |

Request codes use a separate `REQ-N<database-id>` namespace so legacy display codes cannot collide. Pending leave is not reserved; approval atomically checks and subtracts current balance. Overlapping dates are not a scheduling policy in this prototype. Advance amounts are stored for workflow only; no payroll payment occurs.

Academy score means percentage of lessons successfully passed, not a claim about exam-attempt accuracy. All lessons must pass before completion. Catalog discovery and explicit assignment are separate concepts. No certificate document is promised.

AI is deterministic retrieval of exact approved source text, without an external model. A source must cover the meaningful question terms; repeated generic keywords cannot increase confidence. Unsupported details return fallback even when the broad topic exists. Source references use real chunk/document IDs and versions. Demo documents are explicitly synthetic examples, not official company policy. Audit stores source IDs, answer status and a question hash, not the question or answer.

Configuration: development can use an ephemeral signing key; production requires a strong environment secret, disables demo mode/seeding, and permits only explicitly configured cross-origin access. SQLite is the tested MVP database. 1C and Documentolog remain unconnected boundaries. Migration upgrade is explicit (`python -m app.migrate` or `alembic upgrade head`), with tests for empty and legacy databases; startup checks the revision and fails with actionable guidance if migrations are missing.
