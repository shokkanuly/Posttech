# API endpoints

35 paths / 38 operations. Every operation has an automated authorized HTTP success case in `tests/test_api_matrix.py`. All protected operations are also tested without a token and with revoked, malformed, and deactivated sessions.

See `API_CONTRACT.md` for payloads, pagination, scope and revision checks; `openapi.json` contains detailed schemas.

| Method | Path | Access |
|---|---|---|
| GET | `/api/v1/config` | Public |
| POST | `/api/v1/auth/login` | Public |
| POST | `/api/v1/auth/logout` | Authenticated; owner/record scope applies |
| GET | `/api/v1/me` | Authenticated; owner/record scope applies |
| GET | `/api/v1/me/profile` | Authenticated; owner/record scope applies |
| GET | `/api/v1/me/dashboard` | Authenticated; owner/record scope applies |
| GET | `/api/v1/requests` | Authenticated; owner/record scope applies |
| POST | `/api/v1/requests` | Authenticated; owner/record scope applies |
| GET | `/api/v1/requests/{request_id}` | Authenticated; owner/record scope applies |
| POST | `/api/v1/requests/{request_id}/approve` | Manager direct reports / HR |
| POST | `/api/v1/requests/{request_id}/reject` | Manager direct reports / HR |
| GET | `/api/v1/courses` | Authenticated; owner/record scope applies |
| POST | `/api/v1/courses/{course_id}/enroll` | Authenticated; owner/record scope applies |
| GET | `/api/v1/courses/{course_id}` | Authenticated; owner/record scope applies |
| GET | `/api/v1/courses/lessons/{lesson_id}` | Authenticated; owner/record scope applies |
| POST | `/api/v1/courses/lessons/{lesson_id}/quiz` | Authenticated; owner/record scope applies |
| GET | `/api/v1/notifications` | Authenticated; owner/record scope applies |
| PATCH | `/api/v1/notifications/{notification_id}` | Authenticated; owner/record scope applies |
| POST | `/api/v1/notifications/read-all` | Authenticated; owner/record scope applies |
| GET | `/api/v1/notifications/unread-count` | Authenticated; owner/record scope applies |
| POST | `/api/v1/ai/chat` | Authenticated; owner/record scope applies |
| GET | `/api/v1/ai/suggestions` | Authenticated; owner/record scope applies |
| GET | `/api/v1/ai/sources/{chunk_id}` | Authenticated; owner/record scope applies |
| GET | `/api/v1/ai/documents` | Authenticated; owner/record scope applies |
| GET | `/api/v1/manager/requests` | Manager direct reports / HR |
| GET | `/api/v1/manager/team` | Manager direct reports / HR |
| GET | `/api/v1/admin/knowledge/documents` | HR administrator |
| POST | `/api/v1/admin/knowledge/documents` | HR administrator |
| PATCH | `/api/v1/admin/knowledge/documents/{document_id}` | HR administrator |
| GET | `/api/v1/admin/knowledge` | HR administrator |
| POST | `/api/v1/admin/knowledge` | HR administrator |
| PATCH | `/api/v1/admin/knowledge/{chunk_id}` | HR administrator |
| POST | `/api/v1/admin/enrollments` | HR administrator |
| GET | `/api/v1/admin/integrations` | HR administrator |
| GET | `/api/v1/admin/audit` | HR administrator |
| GET | `/api/v1/admin/summary` | HR administrator |
| GET | `/health` | Public |
| GET | `/` | Public |

### Recovery commands (HR administrator)

- `POST /api/v1/admin/integrations/queue/{task_id}/retry`: reason and expected retry counter; durable recovery intent with stale-command protection.
- `POST /api/v1/admin/integrations/reviews/{employee_code}/resolve`: reason, observed review timestamp, optional existing employee account; fresh signed snapshot required.
- Machine gateway: signed `POST /v1/documents/{idempotency_key}/retry` with existing job ID and generation key. MOCK only.
- Employee submission: optional `Idempotency-Key` on `POST /api/v1/requests`, employee-scoped and immutable-body checked.

See [operational contracts](RECOVERY_AND_OPERATIONS.md) and the regenerated [OpenAPI snapshot](openapi.json).
