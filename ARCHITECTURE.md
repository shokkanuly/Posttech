# JanaМен (Janamen) Architecture & Enterprise Design

## 1. Executive Architecture Summary

**JanaМен** is a unified Digital HR self-service platform designed for the **Jana Post × Terricon Valley Hackathon 2026 (Challenge 02: Digital HR)**. 
It replaces fragmented systems and channels with a centralized, responsive web platform that integrates:
- Authoritative, read-only employee profiles and balances (1C:ZUP integration boundary).
- Self-service requests with full audit history (Documentolog integration boundary).
- Role-based approvals strictly enforced on the backend.
- Compliance and mandatory learning with persistent progress tracking (Jana Academy).
- Evidence-grounded corporate policy assistance with strict citations and zero-hallucination safe fallbacks (AI Jana).
- Real-time persistent notifications and immutable system audit logging.

---

## 2. System Context & Component Architecture

```mermaid
graph TD
    User["Web Browser Client (SPA)<br/>Employee / Manager / HR Admin"]

    subgraph JanaMen_Core ["JanaMen Digital HR Platform (FastAPI Modular Monolith)"]
        Gateway["REST API Router (/api/v1)"]
        AuthMiddleware["JWT Bearer Authentication & RBAC Filter"]
        AuditService["Immutable Audit Trail & Event Logger"]

        subgraph Modules ["Domain Business Modules"]
            AuthModule["Auth & Identity Service"]
            ProfileModule["Profile & Dashboard Service"]
            RequestModule["Request State-Machine & Approval Service"]
            AcademyModule["Jana Academy LMS & Quiz Engine"]
            NotificationModule["Persistent Notification Service"]
            AIModule["AI Jana RAG Retrieval & Guardrail Engine"]
        end

        subgraph IntegrationAdapters ["Integration Boundary Adapters (Mocked)"]
            OneCAdapter["1C:ZUP Adapter<br/>• OData Catalog_Employees<br/>• InfoRegister_LeaveBalances"]
            DocLogAdapter["Documentolog Adapter<br/>• REST /documents/incoming_hr_request<br/>• URN Tracking: urn:doclog:janapost:hr"]
        end
    end

    subgraph DataStore ["Relational Persistence"]
        DB[(PostgreSQL / SQLite via SQLAlchemy Engine)]
    end

    subgraph ExternalSystems ["Future Production Corporate Ecosystem"]
        OneCSystem["1C:Enterprise (ЗУП 3.1)<br/>Master Payroll & Cadres"]
        DocLogSystem["Documentolog (ЭДО / SED)<br/>Corporate Electronic Document Flow & EDS"]
    end

    User -->|HTTPS / REST + JWT| Gateway
    Gateway --> AuthMiddleware
    AuthMiddleware --> Modules
    Modules --> AuditService
    Modules --> DB
    AuditService --> DB
    ProfileModule -.-> OneCAdapter
    RequestModule -.-> DocLogAdapter
    OneCAdapter -.->|Future OData| OneCSystem
    DocLogAdapter -.->|Future REST / EDS| DocLogSystem
```

---

## 3. Security & Access Control Model (RBAC)

Authorization is strictly enforced **on the server** across all endpoints. The UI visibility toggles serve only as visual ergonomics; any direct or unauthorized API request returns standard HTTP 403 Forbidden or 401 Unauthorized.

| Feature / Action | Employee (`employee`) | Manager (`manager`) | HR Administrator (`hr_admin`) |
| :--- | :---: | :---: | :---: |
| **View Own Profile & Balances** | Allowed (Read-Only) | Allowed (Read-Only) | Allowed (Read-Only) |
| **Submit Requests** | Allowed (Self) | Allowed (Self) | Allowed (Self) |
| **Approve / Reject Requests** | **DENIED (403)** | Allowed (**Direct Reports Only**) | Allowed (Company Scope) |
| **Access Team Approvals Queue** | **DENIED (403)** | Allowed | Allowed |
| **Access HR Admin & Knowledge** | **DENIED (403)** | **DENIED (403)** | Allowed |
| **View System Audit Logs** | **DENIED (403)** | **DENIED (403)** | Allowed |
| **Inspect Integration Telemetry** | **DENIED (403)** | **DENIED (403)** | Allowed |
| **Complete Courses & Quizzes** | Allowed | Allowed | Allowed |
| **Query AI Jana Knowledge** | Allowed (Public Chunks) | Allowed (Public Chunks) | Allowed (All Chunks) |

### IDOR & Scope Prevention
1. **Reporting Hierarchy Check**: When a manager calls `/requests/{id}/approve` or `/requests/{id}/reject`, the system verifies `EmployeeProfile.manager_id == current_user.id`. A manager cannot approve another manager's reports.
2. **Requester Identity Derivation**: When creating a request, `user_id` is extracted strictly from the validated JWT token claims (`sub`), never from client input.
3. **Official HR Data Immutability**: Core employee fields (position, employee code, leave balance) cannot be modified via client update requests.

---

## 4. Relational Database Schema

```mermaid
erDiagram
    users ||--o| employee_profiles : "has"
    users ||--o{ requests : "creates"
    users ||--o{ requests : "reviews"
    users ||--o{ enrollments : "enrolled in"
    users ||--o{ notifications : "receives"
    users ||--o{ audit_events : "triggers"
    
    requests ||--o{ request_events : "records history"
    
    courses ||--o{ lessons : "contains"
    courses ||--o{ enrollments : "has"
    enrollments ||--o{ lesson_progress : "tracks"
    lessons ||--o{ lesson_progress : "completed in"
    
    knowledge_documents ||--o{ knowledge_chunks : "indexed into"

    users {
        int id PK
        string email UK
        string password_hash
        string full_name
        enum role
        boolean is_active
        datetime created_at
    }

    employee_profiles {
        int id PK
        int user_id FK,UK
        string employee_code UK
        string company
        string department
        string position
        int manager_id FK
        date hire_date
        float leave_balance_days
        string location
    }

    requests {
        int id PK
        string request_code UK
        int user_id FK
        enum type
        date start_date
        date end_date
        float amount
        text reason
        enum status
        int reviewer_id FK
        text review_comment
        string external_sync_id
        datetime created_at
        datetime updated_at
    }

    request_events {
        int id PK
        int request_id FK
        int actor_id FK
        enum event_type
        text comment
        datetime created_at
    }

    courses {
        int id PK
        string code UK
        string title
        string category
        text description
        int duration_minutes
        boolean is_mandatory
        date due_date
        int total_lessons
        string cover_gradient
    }

    lessons {
        int id PK
        int course_id FK
        int order_index
        string title
        text content_markdown
        string quiz_question
        text quiz_options_json
        int quiz_correct_answer
    }

    enrollments {
        int id PK
        int user_id FK
        int course_id FK
        enum status
        float progress_percent
        float score
        datetime completed_at
    }

    lesson_progress {
        int id PK
        int enrollment_id FK
        int lesson_id FK
        boolean is_completed
        boolean quiz_passed
        datetime completed_at
    }

    notifications {
        int id PK
        int user_id FK
        string title
        text message
        enum type
        boolean is_read
        string reference_type
        string reference_id
        datetime created_at
    }

    knowledge_documents {
        int id PK
        string title
        string category
        string version
        boolean is_active
        datetime updated_at
    }

    knowledge_chunks {
        int id PK
        int document_id FK
        string section_title
        text content
        string tags
        string access_level
    }

    audit_events {
        int id PK
        int actor_id FK
        string action
        string target_type
        string target_id
        text details_json
        string ip_address
        datetime created_at
    }
```

---

## 5. Enterprise Integration Boundaries

### 1C:ZUP (ЗУП 3.1) Architecture Boundary
- **Role**: Authoritative master source for employee identity, reporting line structure, and annual leave entitlement.
- **Access Pattern**: Read-only via secure OData or JSON HTTP Services.
- **Data Flow**:
  1. On login / session sync, JanaMen queries `Catalog_Employees` and `InformationRegister_LeaveBalances`.
  2. Local `employee_profiles.leave_balance_days` mirrors the external balance.
  3. No employee or manager can manually override the balance in JanaMen.

### Documentolog (ЭДО / SED) Architecture Boundary
- **Role**: Formal document registration, official order generation, and corporate e-signature (EDS / ЭЦП) archival.
- **Access Pattern**: Outbound webhook / REST push on final request approval.
- **Data Flow**:
  1. Employee submits request in JanaMen (`status=PENDING`).
  2. Manager reviews and approves request (`status=APPROVED`).
  3. JanaMen's `DocumentologAdapter` generates a tracking URN (`urn:doclog:janapost:hr:2026:{id}`) and external document ID (`DOCLOG-2026-{id}`).
  4. The external reference is permanently recorded on `requests.external_sync_id` and displayed in the audit history.

---

## 6. AI Jana Retrieval-Grounded Architecture (RAG)

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Employee Client
    participant API as /api/v1/ai/chat
    participant Guard as Privacy & Scope Guardrail
    participant Index as Knowledge Chunks Store
    participant Engine as Grounding & Synthesis Engine
    participant Audit as Audit Trail

    Employee->>API: POST /api/v1/ai/chat (question)
    API->>Guard: Check for personal confidential data / unauthorized queries
    alt Asks for private employee data (e.g. salary, disciplinary)
        Guard-->>API: Blocked (Privacy violation)
        API->>Audit: Log AI_QUERY_PRIVACY_BLOCKED
        API-->>Employee: Safe privacy response + HR escalation guidance
    else Valid general HR inquiry
        API->>Index: Keyword & Tag Search across active approved chunks
        Index-->>Engine: Ranked chunks + similarity score
        alt Best match score < Confidence Threshold (0.50)
            Engine-->>API: Insufficient evidence
            API->>Audit: Log AI_QUERY_FALLBACK
            API-->>Employee: Safe fallback banner (No hallucinated rules) + HR contacts
        else High-confidence evidence found
            Engine->>Engine: Synthesize concise answer strictly from cited chunks
            API->>Audit: Log AI_QUERY_GROUNDED_ANSWER
            API-->>Employee: Grounded answer + Clickable source pills (Title, Section, Snippet)
        end
    end
```
