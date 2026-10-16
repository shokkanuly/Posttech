# JanaMen — Digital HR Employee Workspace

[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose%20Ready-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/Hackathon-PostTech%20%C3%97%20Terricon%20Valley%202026-forestgreen.svg)]()

> **Jana Post × Terricon Valley Hackathon 2026 — Challenge 02: Digital HR**  
> A unified, role-based self-service HR platform for Jana Post employees, managers, and HR administrators.

---

## 1. Overview

**JanaMen** is a modular enterprise web application that brings together employee profiles, leave requests, mandatory learning, and evidence-grounded AI assistance into a single, cohesive workspace.

- **Frontend**: Clean, responsive single-page architecture built with semantic HTML5, modern vanilla CSS design tokens, and vanilla JavaScript.
- **Backend**: FastAPI modular monolith with SQLAlchemy 2.0 ORM, Alembic migrations, and role-based access control (RBAC).
- **Security & Authorization**: Server-side enforced access control, PBKDF2-HMAC password hashing, and revocable JWT bearer sessions.
- **Workflow State Machine**: Transactional request creation (vacation and advance payments), balance validations, manager approval queues, and complete audit history.
- **Jana Academy (LMS)**: Course catalog, markdown lesson viewer, interactive quiz evaluation, and persisted progress tracking.
- **AI Jana (Grounded Assistant)**: Question answering grounded strictly in approved corporate documents with precise source citations, privacy guardrails, and safe fallbacks for unverified inquiries.
- **Integration Boundaries**: Documented mock adapter interfaces for future enterprise integrations with **1C:ZUP 3.1** and **Documentolog**.

---

## 2. Local Setup & Quick Start

Tested with Python 3.11 and 3.14 on macOS and Linux.

### Step 1: Virtual Environment & Dependencies

```bash
# Navigate to project root
cd "/path/to/project"

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

### Step 2: Configuration & Database Initialization

```bash
# Set environment variables for local demo
export ENVIRONMENT=development
export DEMO_MODE=true
export DEMO_PASSWORD='Password123!'
export DATABASE_URL=sqlite:///./janamen.db
export ACCESS_TOKEN_EXPIRE_MINUTES=1440
export AI_CONFIDENCE_THRESHOLD=0.50
export ENABLE_MOCK_INTEGRATIONS=true

# Run database migrations
python -m app.migrate

# Seed deterministic synthetic test data
python -m app.seed
```

### Step 3: Start the Application Server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Web Application**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 3. Docker Deployment

```bash
# Build and run containerized services
docker compose up --build -d

# Verify container health
curl http://127.0.0.1:8000/health
```

The container runs as an unprivileged user, binds port 8000, runs database migrations automatically on startup, and stores data in a persistent volume.

---

## 4. Test Accounts & Personas

Deterministic synthetic demo accounts are provided for testing each role:

| Role | Persona Name | Email | Password | Scope & Key Details |
| :--- | :--- | :--- | :--- | :--- |
| **Employee** | Aruzhan Sadykova | `aruzhan@janapost.kz` | `Password123!` | Product Operations · 18.5 leave days · Reports to Timur K. |
| **Manager** | Timur Kasymov | `timur@janapost.kz` | `Password123!` | Operations Team Lead · Manages Aruzhan S., Dana M., Ruslan A. |
| **HR Admin** | Aigerim Nurlanova | `aigerim@janapost.kz` | `Password123!` | People Operations Director · Knowledge management & audit logs |

> **Convenience Feature**: The top navigation bar includes an interactive **Persona Switcher** dropdown. Selecting a persona executes a real authentication call (`POST /api/v1/auth/login`), obtains a signed JWT bearer token, and updates the view according to the user's role.

---

## 5. Demonstration Walkthrough (10-Step Judging Journey)

Follow this step-by-step path to verify all hackathon evaluation criteria:

### Step 1: Employee Login & Dashboard
1. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).
2. The default active persona is **Aruzhan Sadykova** (Employee).
3. Verify the personalized greeting, the annual leave balance ring showing **18.5 days available**, active requests, and learning progress.

### Step 2: Employee Profile & 1C:ZUP Master Data
1. Click **My profile** in the sidebar.
2. View the authoritative employee fields: Employee ID `JP-10428`, Company `Jana Post Kazakhstan`, Department `Product Operations`, Manager `Timur Kasymov`.
3. Note the **"Official HR data · Read-only"** badge. Profile fields are authoritative and cannot be modified by the user.

### Step 3: Request Submission
1. Click **My requests** -> click **＋ New request** (or click "Request time off ↗" on the Overview).
2. Select **Vacation**, pick Start Date `2026-11-23` and End Date `2026-11-25` (3 days), enter reason `"Family holiday"`.
3. Click **Submit request ↗**.
4. The request is created in **Pending** status with request code `REQ-1045` and an initial audit event (`SUBMITTED`).

### Step 4: Manager Review & Approval
1. In the topbar persona switcher, switch to **Persona: Manager (Timur K.)**.
2. Notice that the **Team & approvals** navigation item is now visible.
3. Open **Team & approvals**; observe the pending request queue for direct reports.
4. Click **Approve** on Aruzhan's request, enter an optional note `"Approved by manager Timur"`.
5. The request status updates to **Approved**, and an external Documentolog tracking ID is assigned (`DOCLOG-2026-1045`).

### Step 5: Employee Notification & Balance Synchronization
1. Switch the persona back to **Persona: Employee (Aruzhan S.)**.
2. Click the notification bell or navigate to **Notifications**.
3. Observe the persistent notification: `"Request Approved: Your Vacation request was approved by Timur Kasymov"`.
4. Return to **Overview** or **My profile**; observe that the annual leave balance was automatically deducted by 3 days (from 18.5 to **15.5 days**).

### Step 6: Jana Academy Course & Interactive Quiz
1. Click **Jana Academy** in the sidebar.
2. Open the mandatory course **"Data protection essentials"** (currently at 75% progress).
3. Read Lesson 4: *"Incident Reporting & Escalation"*.
4. In the quiz section, select the correct answer: `"Within 30 minutes"`, then click **Submit Answer**.
5. The quiz is validated by the backend, course progress updates to **100% (Completed)**, a completion notification is issued, and the dashboard reflects the achievement.

### Step 7: AI Jana Grounded Q&A with Source Citation
1. Click **AI Jana** in the sidebar.
2. Click the prompt chip: **"How do I request vacation in the system?"** (or type your own question).
3. AI Jana responds with a grounded answer citing **Employee Request Guide · Vacation Request Workflow**.
4. Click the source pill to open the modal displaying the exact verified policy passage.

### Step 8: AI Jana Safe Fallback (No Hallucinations)
1. In AI Jana, ask: **"What is the reimbursement policy for pet insurance?"**.
2. Because this policy is not present in the approved knowledge base, AI Jana **does not hallucinate or guess**.
3. It triggers a **Safe Fallback** informing the employee that no reliable evidence was found and directs them to contact `hr-support@janapost.kz`.

### Step 9: Server-Enforced RBAC & Security Verification
1. As Employee Aruzhan, attempting to call `/api/v1/manager/requests` or `/api/v1/admin/knowledge` returns **HTTP 403 Forbidden**.
2. Employees cannot approve requests, and managers cannot approve requests outside their reporting line.

### Step 10: Enterprise Integration Telemetry & Audit Logs
1. Switch the persona to **Persona: HR Admin (Aigerim N.)**.
2. Click **HR administration** in the sidebar.
3. View the **Enterprise Integration Boundaries** card showing telemetry for **1C:ZUP 3.1** and **Documentolog**.
4. Review the live **System Audit Trail** showing all timestamped logins, submissions, approvals, and AI queries.

---

## 6. Automated Testing Suite

The repository contains an automated test suite with **76 passed tests**:

```bash
# Run the complete test suite
python -m pytest -q

# Run with verbose output
python -m pytest -v

# Run the live 10-step judging smoke test runner against the running server
python smoke_test.py
```

### Test Coverage Highlights:
- **`tests/test_auth.py`**: User authentication, incorrect passwords, token decoding, session revocation.
- **`tests/test_requests.py`**: Vacation & advance payment submissions, date range validation, leave balance checks, approval workflows, event history.
- **`tests/test_academy.py`**: Course catalog, lesson details, quiz grading, persistent completion state.
- **`tests/test_ai.py`**: Grounded answers, source citation attribution, safe fallbacks, privacy protection guardrails.
- **`tests/test_security.py`**: Role-based access control (RBAC), manager scope enforcement, IDOR prevention, token tampering defense.
- **`tests/test_migrations.py`**: Schema migration integrity and version checks.
- **`tests/test_reliability.py`**: Concurrency, transaction rollbacks, and error boundary handling.
- **`tests/test_e2e_journey.py`**: End-to-end integration test following the entire employee journey.

---

## 7. Implementation Status Matrix

| Component | Status | Implementation Details |
| :--- | :---: | :--- |
| **Authentication & RBAC** | **Fully Implemented** | PBKDF2-HMAC password hashing, JWT Bearer tokens, server-side role enforcement. |
| **Employee Profile** | **Fully Implemented** | Read-only authoritative data, department, manager hierarchy, leave balance. |
| **Request Workflows** | **Fully Implemented** | Vacation & advance payment forms, date validation, manager review, status lifecycle. |
| **Request Event History** | **Fully Implemented** | Audit timeline tracking submissions, approvals, rejections, and reviewer comments. |
| **Jana Academy (LMS)** | **Fully Implemented** | Course catalog, lesson markdown reader, interactive quiz, real progress calculation. |
| **AI Jana Assistant** | **Fully Implemented** | Multi-token keyword & tag RAG retrieval, verifiable source citations, safe fallbacks. |
| **Persistent Notifications** | **Fully Implemented** | DB-persisted alerts for requests and academy milestones, unread counters. |
| **Audit Logging** | **Fully Implemented** | Immutable `audit_events` table recording actor, action, timestamp, and details. |
| **Localization (RU / KZ / EN)** | **Fully Implemented** | Client-side i18n dictionary covering Russian, Kazakh, and English. |
| **1C:ZUP Integration** | **Mocked Adapter** | Architecture boundary defined in `app/integrations/one_c_zup.py`. Ready for future OData. |
| **Documentolog Integration** | **Mocked Adapter** | Architecture boundary defined in `app/integrations/documentolog.py`. Assigns tracking URNs. |
| **Digital Signatures (EDS)** | *Planned Future Work* | Legal e-signature integration deferred to post-hackathon enterprise rollout. |
| **Mobile App (iOS/Android)** | *Planned Future Work* | Current release provides a mobile-responsive web application. |

---

## 8. Integration Architecture Boundaries

### 1. 1C:ZUP (ЗУП 3.1)
- **Role**: Authoritative master source for employee records, organizational structure, and annual leave balance accruals.
- **Pattern**: Read-only consumption via secure OData or JSON HTTP services.
- **Implementation**: Defined in `app/integrations/one_c_zup.py` with mock endpoints for `Catalog_Employees` and `InformationRegister_LeaveBalances`.

### 2. Documentolog (Corporate Electronic Document Management)
- **Role**: Formal document registration, official order generation, and corporate e-signature archival.
- **Pattern**: Outbound REST registration upon request approval.
- **Implementation**: Defined in `app/integrations/documentolog.py`, assigning unique tracking URNs (`urn:doclog:janapost:hr:2026:...`) and synchronization status.

---

## 9. Known Boundaries & Limitations

1. **Enterprise Integrations**: Connections to 1C:ZUP and Documentolog are modeled via mock adapters returning synthetic payloads and external identifiers, in accordance with hackathon competition rules.
2. **AI Engine**: AI Jana utilizes deterministic keyword and token-based retrieval over approved corporate documents, ensuring zero hallucinations and offline competition compliance without external cloud dependencies.
3. **Data Scope**: All employee records, departments, and policy documents are synthetic demo data created specifically for the Jana Post challenge.

---

## 10. Repository Structure

```
.
├── ARCHITECTURE.md            # Detailed architecture and enterprise integration design
├── Dockerfile                 # Production container definition
├── README.md                  # Project documentation and quick start guide
├── alembic.ini                # Alembic database migration configuration
├── app/                       # FastAPI backend modular monolith
│   ├── config.py              # Configuration settings and environment variables
│   ├── database.py            # SQLAlchemy engine and session factory
│   ├── integrations/          # Enterprise adapters (1C:ZUP and Documentolog)
│   ├── models/                # SQLAlchemy database models
│   ├── routers/               # API endpoints (/auth, /me, /requests, /courses, /ai, etc.)
│   ├── schemas/               # Pydantic input and response schemas
│   ├── seed.py                # Deterministic synthetic data generator
│   └── services/              # Business logic, state machines, RAG retrieval
├── docker-compose.yml         # Multi-container orchestration definition
├── migrations/                # Versioned database migrations
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development and testing dependencies
├── smoke_test.py              # Automated 10-step judging demonstration test runner
├── static/                    # Frontend client assets
│   ├── css/style.css          # Modern enterprise styling and design tokens
│   ├── index.html             # Responsive single-page application structure
│   └── js/                    # Application controller and localization dictionary
└── tests/                     # Automated pytest suite (76 tests)
```

---

## 11. License & Acknowledgements

Created for the **Jana Post × Terricon Valley Hackathon 2026 (Challenge 02: Digital HR)**.
Designed with modern enterprise UX standards, accessible semantic HTML, and clean Python backend architecture.
