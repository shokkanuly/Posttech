# JanaМен API contract

Base: `/api/v1`. JSON bodies. Existing response fields remain unless a misleading integration claim must change. Generated OpenAPI at `/openapi.json` is the detailed schema; `/docs` is the interactive reference.

All path identifiers are integers from 1 through 9223372036854775807; IDs and revision preconditions in JSON must be actual integers (strings, floats and booleans are rejected). Oversized IDs return 422 before database access. Document approval/activity/synthetic flags require JSON booleans. Request bodies, including chunked streams, are bounded by `MAX_REQUEST_BODY_BYTES` (default 262144); oversized bodies return 413 `payload_too_large` before JSON decoding. Invalid Content-Length returns 400. Error responses carry no-store and nosniff headers even for unexpected server failures.

Collections `/requests`, `/manager/requests`, `/manager/team`, `/courses`, `/notifications`, `/admin/knowledge`, `/admin/knowledge/documents`, `/admin/audit`, `/ai/documents` accept `limit=1..100` (default 50) and `offset=0..1000000` (default 0). Responses remain arrays. Fetch successive pages until a page contains fewer than `limit` items. Ordering uses stable IDs, with descending created time and ID for requests, notifications and audit. The frontend follows pages automatically. Offset pages are not a snapshot when concurrent inserts occur.

Knowledge documents expose a monotonically increasing `revision`, initially 1; chunk responses include `document_revision`. Every metadata/content/approval change increments the parent revision inside the same transaction. All document/chunk edits and chunk creation accept optional `expected_revision`; a stale value returns 409 and changes nothing. **Approval requires `expected_revision`**, binding approval to the full source text HR reviewed. Example: `PATCH /admin/knowledge/documents/1` with `{"is_approved":true,"expected_revision":3}`. Re-fetch and review all current source content after a conflict. Approval and edits lock the same parent row; only one concurrent write with the same precondition can succeed.

AI citations include `document_revision`; fetch `/ai/sources/{chunk_id}?revision=<cited-revision>` to prevent opening changed content under an old citation. After a changed source is reapproved, stale references return 409; inactive, unapproved or unauthorized sources return 404. Omit revision only when explicitly requesting the latest approved content. Audit records retain citation revision and a content hash, without raw text. Historical source bodies are not archived.

Language: send `Accept-Language: ru-RU` or `kk-KZ` (`kz` is also accepted). Quality weights are respected. The UI defaults to Russian and sends its selected language; API callers without a supported language retain English compatibility. Successful localized routes and errors return `Content-Language` and `Vary: Accept-Language`. Presentation text and validation messages are localized. JSON keys, roles, status/type/action codes, IDs, emails and user-authored text stay unchanged. Language is never an authorization input.

Knowledge document create/patch accepts primary `language` (`en`, `ru`, `kk`) and `translations: {"ru": {"title": "…", "category": "…", "description": "…"}, "kk": {...}}`. Chunk create/patch accepts `translations: {"ru": {"section_title": "…", "content": "…"}, "kk": {...}}`. Values are bounded and unknown fields/language keys rejected. Editing primary metadata/text without replacement translations clears the stale translations; source review, revision and approval rules apply to translations as to the original. Migration `0004_source_translations` adds these columns without modifying existing policy text or approval.

AI only quotes stored sources available in the selected language, with source text, section and document title from the same language. Missing approved translations produce fallback; source fetch returns 404. Citations and source responses include `language`. Open `/ai/sources/{id}?revision=<cited-revision>&language=<cited-language>` to preserve the language and revision actually cited, even after the interface language changes. Explicit source language still requires authentication and source/role checks. User chat and source passages are rendered verbatim.

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
| GET `/manager/team` fields | company, position, department, manager, balance, `used_days`, `pending_days`, `available_days`, learning % | Same scope; days use the 1C:ZUP calendar rule (public holidays not charged) |
| GET `/manager/team/{user_id}` | employee HR card: profile, leave figures, request history with `vacation_days`, assigned courses | Direct report for manager, any employee for HR; out-of-scope and missing both return 404 |
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
| GET `/ai/sources/{id}` | exact document/version/revision/language/section/content; optional `revision`, `language` query | Same approval and role checks as retrieval |
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

Optional retrieval reranking: `AI_RETRIEVAL_MODE=ml` with a locally trained `AI_RETRIEVAL_MODEL_PATH` loads bounded JSON coefficients. Approval/activity/role/language filters and minimum evidence coverage apply before ranking. A missing or invalid artifact falls back to the existing lexical retrieval. The model changes no HTTP schemas, identity rules, source IDs, revisions or language checks. File bundles are imported by an active HR operator as drafts and require the existing explicit approval flow. See `../knowledge/README.md` and `../ml/README.md`.


## Интеграция локальных обновлений — 17.10.2026

- `GET /api/v1/manager/team?limit=100&offset=0`: добавлены компания, руководитель, использованные/ожидающие/доступные дни и прогресс обучения.
- `GET /api/v1/manager/team/{user_id}`: кадровая карточка, последние 100 заявок, назначенные курсы и последние 300 событий. Только непосредственный руководитель или HR; вне области доступа — одинаковый 404. Сотрудник — 403.
- `POST /api/v1/requests`: даты не раньше текущей даты Алматы; начало и окончание не позднее `REQUEST_HORIZON_DAYS`. Аванс ограничен `MAX_ADVANCE_AMOUNT`. Пересечение действующих отпусков — 409, недостаточный остаток с учётом резервов — 400. Конкурирующие резервы сериализованы.
- `vacation_days`: календарные дни минус государственные праздники РК (встроены) и `LEAVE_EXCLUDED_DATES`; `weekend_days` / `holiday_days` — выходные (списываются) и праздники (не списываются) внутри отпуска; детали заявки содержат `leave_days` по дням. `GET /requests/leave-calendar?start_date&end_date` даёт ту же разбивку до подачи и `available_days`. Источник не является 1С.
- `type: "Profile update"` с `profile_changes` (`phone`, `location`, `emergency_contact`) создаёт заявку на изменение контактов; изменения применяются только при одобрении руководителем или HR.
- `POST /api/v1/ai/chat`: дополнительно `engine` и `sources[].relevance`. Gemini выключен по умолчанию. При включении допускает только точные цитаты из доступных источников на выбранном языке и не обходит пороги поиска.

Пример: `GET /api/v1/manager/team/8` с `Authorization: Bearer <TOKEN>` и `Accept-Language: kk-KZ`. Идентификатор берите из списка команды; фиксированный ID в примере не даёт прав.
