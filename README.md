# JanaMen (JanaМен) — Digital HR Workspace

[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose%20Ready-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/Hackathon-PostTech%20%C3%97%20Terricon%20Valley%202026-forestgreen.svg)]()

> **PostTech × Terricon Valley Hackathon 2026 — Challenge 02: Digital HR**  
> A unified, role-based self-service HR platform for Jana Post employees, managers, and HR administrators.

---

## 1. Executive Summary

JanaMen replaces fragmented enterprise spreadsheets, messengers, and disconnected HR portals with a unified employee workspace:

1. **Personalized Dashboard & Profile**: Read-only official HR data, live leave balance ring, and daily task snapshots.
2. **End-to-End Request Workflow**: Vacation and advance payment submissions with backend balance validation, manager review queues, approval event history, and mock Documentolog registration.
3. **Server-Enforced RBAC**: Real backend authorization ensuring employees cannot approve requests or view team scopes, and managers only access direct reports.
4. **Jana Academy (LMS)**: Persistent course progression, interactive compliance quizzes, instant score calculation, and completion certificates.
5. **AI Jana (Evidence-Grounded RAG Assistant)**: Corporate HR policy Q&A grounded strictly in approved documentation with verifiable citations, zero-hallucination safe fallbacks, and privacy protection guardrails.
6. **Persistent Notifications & Auditability**: Real-time alerts on request updates and course milestones, backed by an immutable system audit log.
7. **Documented Enterprise Boundaries**: Clear architectural adapters for future live integrations with **1C:ZUP 3.1** and **Documentolog (ЭДО)**.

---

## 2. Quick Start & Setup

The platform can be run locally using Python or via Docker Compose.

### Option A: Local Run (Zero-Config SQLite)

```bash
# 1. Clone repository and navigate to workspace
cd "/Users/aibek/post tech "

# 2. (Optional) Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy configuration template
cp .env.example .env

# 5. Seed the database with synthetic demo data
python3 -m app.seed

# 6. Start the server
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **`http://127.0.0.1:8000`** in your browser.  
Interactive Swagger API documentation is available at **`http://127.0.0.1:8000/docs`**.

---

### Option B: Docker Compose

```bash
# Start containerized application
docker compose up --build -d

# Check health status
curl http://localhost:8000/health
```

---

## 3. Demo Test Accounts

Deterministic synthetic accounts with real backend passwords (no actual personal employee data):

| Role | Persona Name | Email | Password | Scope & Key Data |
| :--- | :--- | :--- | :--- | :--- |
| **Employee** | Aruzhan Sadykova | `aruzhan@janapost.kz` | `Password123!` | Product Operations · 18.5 leave days · Reports to Timur K. |
| **Manager** | Timur Kasymov | `timur@janapost.kz` | `Password123!` | Operations Team Lead · Manages Aruzhan S., Dana M., Ruslan A. |
| **HR Admin** | Aigerim Nurlanova | `aigerim@janapost.kz` | `Password123!` | People Operations Director · Access to knowledge base & audit logs |

> **Convenience Feature**: The topbar includes an instant **Persona Switcher** that performs a real login (`POST /api/v1/auth/login`), obtains a signed JWT token, and refreshes the view without manual logout/login steps.

---

## 4. 10-Step Demonstration Script (Judging Walkthrough)

Follow this step-by-step path to evaluate all hackathon criteria:

### Step 1: Employee Login & Dashboard
- Open `http://127.0.0.1:8000`.
- Verify the active persona is **Aruzhan Sadykova** (Employee).
- Note the leave balance ring showing **18.5 days available**, current open requests, and learning progress.

### Step 2: Employee Profile & 1C:ZUP Master Data
- Click **My profile** in the sidebar.
- Observe official HR fields: Employee Code `JP-10428`, Company `Jana Post Kazakhstan`, Department `Product Operations`, Manager `Timur Kasymov`.
- Notice the **"Official HR data · Read-only"** badge; profile data is authoritative and protected from tampering.

### Step 3: Submit a Vacation Request
- Click **My requests** -> click **＋ New request** (or click "Request time off ↗" on Overview).
- Select **Vacation**, pick Start Date `2026-11-23` and End Date `2026-11-25` (3 days), enter reason `"Shymbulak family trip"`.
- Click **Submit request ↗**.
- A toast confirms submission, and a new request `REQ-1045` appears in **Pending** status.
- Click **Details ↗** on the request to inspect the audit timeline (`SUBMITTED by Aruzhan Sadykova`).

### Step 4: Manager Review & Approval
- Switch the persona dropdown in the topbar to **Persona: Manager (Timur K.)**.
- The navigation automatically reveals the **Team & approvals** workspace.
- Navigate to **Team & approvals**; observe pending requests from direct reports.
- Click **Approve** on Aruzhan's request, enter optional comment `"Approved. Enjoy your break."`.
- The request transitions to **Approved**, and an external Documentolog tracking URN is assigned (`DOCLOG-2026-1045`).

### Step 5: Employee Notification & Balance Synchronization
- Switch persona back to **Persona: Employee (Aruzhan S.)**.
- Check the notification bell in the topbar; click **Notifications**.
- Observe the persistent notification: `"Request Approved: Your Vacation request was approved by Timur Kasymov"`.
- Return to **Overview** or **My profile**; observe that the leave balance was automatically deducted by 3 days (from 18.5 to **15.5 days**).

### Step 6: Jana Academy Course & Interactive Quiz
- Click **Jana Academy** in the sidebar.
- Open the mandatory course **"Data protection essentials"** (currently at 75% progress).
- Read Lesson 4: *"Incident Reporting & Escalation"*.
- In the quiz section, select the correct answer: `"Within 30 minutes"`, then click **Submit Answer**.
- The quiz is evaluated in the backend, course progress updates to **100% (Completed)**, a completion certificate notification is created, and the dashboard reflects the achievement.

### Step 7: AI Jana Grounded Q&A with Source Citation
- Click **AI Jana** in the sidebar.
- Click the suggestion chip: **"How do I request vacation in the system?"** (or type your own question).
- AI Jana responds with a grounded answer citing **Employee Request Guide · Vacation Request Workflow**.
- Click the clickable source pill to view the source modal displaying the exact verified policy snippet.

### Step 8: AI Jana Safe Fallback (No Hallucinations)
- In AI Jana, ask: **"What is the pet insurance reimbursement policy?"**.
- Because this policy does not exist in the approved knowledge base, AI Jana **does not hallucinate or guess**.
- It triggers a **Safe Fallback** with guidance to contact HR at `hr-support@janapost.kz`.

### Step 9: Server-Enforced RBAC & Security Verification
- As Employee Aruzhan, try directly visiting `/api/v1/manager/requests` or `/api/v1/admin/knowledge`.
- The server responds with **HTTP 403 Forbidden: Access denied**.
- Employees cannot approve requests, and managers cannot approve requests outside their reporting line.

### Step 10: Enterprise Integration Telemetry & Audit Logs
- Switch persona to **Persona: HR Admin (Aigerim N.)**.
- Click **HR administration** in the sidebar.
- View the **Enterprise Integration Boundaries** card showing telemetry for **1C:ZUP 3.1** and **Documentolog**.
- Review the live **System Audit Trail** showing all timestamped logins, submissions, approvals, and AI queries.

---

## 5. Automated Testing Suite

Comprehensive automated test coverage with **28 tests**:

```bash
# Run backend pytest suite (unit, RBAC, workflows, AI RAG, LMS)
python3 -m pytest -v

# Run the live 10-step judging smoke test runner against the running server
python3 smoke_test.py
```

### Test Suite Summary:
- **`tests/test_auth.py`**: Authentication, incorrect passwords, token decoding, profile serialization.
- **`tests/test_requests.py`**: Vacation & advance payment submissions, date range validation, leave balance checks, approval workflows, event histories.
- **`tests/test_academy.py`**: Course catalog, lesson details, quiz grading, persistent completion.
- **`tests/test_ai.py`**: Grounded answers, citation attribution, safe fallbacks, and privacy protection guardrails.
- **`tests/test_security.py`**: Role-based access control (RBAC), manager scope enforcement, IDOR prevention, token tampering defense.
- **`tests/test_e2e_journey.py`**: End-to-end integration test following the entire employee journey.

---

## 6. Implementation Status Matrix

| Component | Hackathon Prototype Status | Implementation Notes |
| :--- | :---: | :--- |
| **Authentication & RBAC** | **Fully Implemented** | PBKDF2-HMAC password hashing, JWT Bearer tokens, server-side role enforcement. |
| **Employee Profile** | **Fully Implemented** | Read-only authoritative data, department, manager link, leave balance. |
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

## 7. Known Limitations & Architecture Boundaries

1. **Integration Adapters**: Production connections to 1C:ZUP and Documentolog are modeled via mock adapters (`READY_MOCK`) returning synthetic payloads and external IDs. Live enterprise VPN/OData tunnels were not configured per hackathon rules.
2. **AI Provider Fallback**: AI Jana currently operates an offline, deterministic vector/keyword retrieval engine over approved documents, ensuring reliable, verifiable citations and offline competition compliance without external cloud API dependencies.
3. **Data Scope**: All employee records, departments, and policy documents are synthetic demo data created specifically for the Jana Post challenge.

---

## 8. License & Acknowledgements

Created for the **Jana Post × Terricon Valley Hackathon 2026 (Challenge 02: Digital HR)**.
Designed with modern enterprise UX standards, accessible semantic HTML, and clean Python backend architecture.
