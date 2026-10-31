# Agentic AI Engineering — Student Support Agent System

A comprehensive, production-grade conversational AI system for university student support, divided into two progressive phases:
- **Assignment 1:** Intelligent Student Support Agent (Autonomous ReAct Loop, 5 Tools, TF-IDF RAG, Persistent Memory, Tracing)
- **Assignment 2:** Safe & Production-Aware Agent Architecture (Authentication, Deterministic RBAC, Human-in-the-Loop Approvals, Immutable Audit Logging, Parameterized SQL)

---

## Global System Specifications

- **Active Degree Programs:** Exclusively restricted to:
  1. `Big Data Analytics (BDA)`
  2. `AI & Data Science`
- **Monetary Currency:** Strictly Indian Rupees (**₹ / INR**) across all database records, tool payloads, agent prompts, and UI components.
- **LLM Backbone:** Groq API running `qwen/qwen3.8-27b` with native function/tool calling.
- **API Key Security:** All configuration files utilize the safe placeholder `GROQ_API_KEY=Your api_key`. Pre-storage regex filters prevent any secrets or credentials from persisting in memory or audit trails.

---

## Project Structure

```
agent/
├── README.md                           # Master documentation for both assignments
├── assignment_1/                       # Assignment 1 Implementation (Baseline Autonomous Agent)
│   ├── .env.example                    # Environment variable template
│   ├── .env                            # Active environment configuration
│   ├── agent.py                        # Autonomous ReAct agent loop
│   ├── app.py                          # Streamlit UI with direct student switching
│   ├── config.py                       # Groq client & system configurations
│   ├── database.py                     # SQLite database schema & operations
│   ├── evaluation.py                   # Automated benchmark evaluation harness
│   ├── memory.py                       # Persistent memory & sensitive regex filtering
│   ├── requirements.txt                # Python package dependencies
│   ├── retrieval.py                    # TF-IDF RAG engine for student handbook
│   ├── tools.py                        # 5 standard tool definitions & dispatchers
│   ├── tracing.py                      # Observability & latency/token telemetry
│   ├── data/
│   │   ├── seed_demo_data.py           # Database seeder (BDA & AI & DS in ₹ INR)
│   │   ├── student_handbook.md         # Official institutional handbook with dates & policies
│   │   └── student_support.db          # Seeded SQLite database
│   └── tests/
│       ├── test_agent.py               # ReAct loop & prompt structure tests
│       ├── test_memory.py              # Cross-session memory & sanitization tests
│       ├── test_retrieval.py           # RAG chunking & cosine similarity tests
│       └── test_tools.py               # Tool schema & execution tests
│
└── assignment_2/                       # Assignment 2 Implementation (Production-Aware Agent)
    ├── .env.example                    # Environment variable template
    ├── .env                            # Active environment configuration
    ├── agent.py                        # ReAct agent loop with security wrappers
    ├── app.py                          # Streamlit portal (Sign-up, Login, Student & Approver UI)
    ├── approval.py                     # Human-in-the-loop approval workflow engine
    ├── audit.py                        # Append-only audit logger with redaction
    ├── auth.py                         # User authentication (PBKDF2/SHA-256 hashed)
    ├── authorization.py                # Deterministic RBAC & access control matrix
    ├── config.py                       # Configuration validation & client setup
    ├── database.py                     # Parameterized SQL schema & security tables
    ├── evaluation.py                   # Comparative benchmark harness (A1 vs A2)
    ├── memory.py                       # Student-isolated persistent memory
    ├── requirements.txt                # Python package dependencies
    ├── retrieval.py                    # TF-IDF RAG handbook retriever
    ├── tools.py                        # RBAC-guarded tools & approval triggers
    ├── tracing.py                      # Observability & audit-linked telemetry
    ├── data/
    │   ├── seed_demo_data.py           # Seeder for auth, approvals, students & INR fees
    │   ├── student_handbook.md         # Institutional policy & academic calendar
    │   └── student_support.db          # Seeded SQLite database
    ├── reports/
    │   ├── Assignment_1_Intelligent_Student_Support_Agent_Report.md
    │   └── Assignment_2_Safe_and_Production_Aware_Agent_Report.md
    └── tests/
        ├── test_agent.py               # Agent loop & safeguard tests
        ├── test_approval.py            # Approval creation, execution & anti-replay tests
        ├── test_audit.py               # Tamper-evident logging & masking tests
        ├── test_authorization.py       # RBAC & IDOR cross-student boundary tests
        ├── test_evaluation.py          # Benchmark harness tests
        ├── test_memory.py              # Memory CRUD & sanitization tests
        └── test_privacy.py             # SQL injection & secret leak prevention tests
```

---

## Assignment 1: Intelligent Student Support Agent

### 1. Architectural Highlights
- **ReAct Agent Loop:** Iterative Thought $\to$ Action $\to$ Observation cycle. Evaluates user intent, dynamically binds tools, and generates concrete responses.
- **5 Production Tools:**
  1. `check_fee_status`: Real-time fee balance, amounts paid, due dates in **₹ INR**.
  2. `check_scholarship_status`: Scholarship program name, validity, and awarded amount in **₹ INR**.
  3. `create_support_request`: Generates unique ticket numbers across categories (`academic`, `financial`, `technical`, etc.).
  4. `get_course_change_information`: Program-specific change policies restricted to **Big Data Analytics (BDA)** and **AI & Data Science**.
  5. `search_handbook`: Semantic TF-IDF search for session dates, exam schedules, and academic rules.
- **Persistent Memory:** Preserves student context (preferred language, study habits) across conversations.
- **Sensitive Data Filtration:** Regex engine blocks passwords, OTPs, API keys, and payment card details before SQLite persistence.
- **TF-IDF RAG:** Chunks `student_handbook.md` by Markdown headers with cosine similarity scoring.
- **Direct Student Selector UI:** Clean Streamlit dashboard with a sidebar dropdown to instantly test any demo student without an authentication gate.

### 2. How to Run Assignment 1
```bash
# Navigate to Assignment 1 directory
cd assignment_1

# Install dependencies
pip install -r requirements.txt

# Configure your API key in .env
# (Change 'Your api_key' to your active Groq API key)
# GROQ_API_KEY=Your api_key
# GROQ_MODEL=qwen/qwen3.8-27b

# Seed the database
python data/seed_demo_data.py

# Run the test suite (26 unit tests)
pytest tests/ -v

# Run the benchmark evaluation
python evaluation.py

# Launch the Streamlit chat interface
streamlit run app.py
```

---

## Assignment 2: Safe & Production-Aware Agent

### 1. Architectural Highlights
- **Authentication Gateway (`auth.py`):** Explicit Sign-Up and Log-In screens. Passwords are never stored in plaintext (salted SHA-256 hash storage).
- **Deterministic Authorization & RBAC (`authorization.py`):**
  - Enforced directly in Python application code—never delegated to the LLM.
  - Validates `actor_id == target_student_id` for sensitive queries.
  - Completely eliminates Insecure Direct Object References (IDOR); students cannot inspect other students' fees or scholarships.
- **Human-in-the-Loop Approvals (`approval.py`):**
  - High-impact financial operations (such as fee balance adjustments or fee waivers) cannot be executed autonomously by the LLM.
  - Automatically routed to `approval_requests` with status `pending`.
  - Replay protection guarantees transactions cannot be re-executed once processed.
- **Approver Dashboard (`app.py`):**
  - Authorized staff (`ADMIN01`) log in to view pending financial corrections, inspect justification details, and grant or reject requests with audit logging.
- **Immutable Audit Trail (`audit.py`):**
  - Tamper-evident logging of every system action (`ACCESS_ALLOWED`, `ACCESS_DENIED`, `APPROVAL_REQUESTED`, `APPROVAL_RESOLVED`).
  - Sensitive details (passwords, tokens, OTPs) are masked prior to disk write.
- **Parameterized SQL Defense (`database.py`):**
  - 100% parameterized SQLite statements (`?` placeholders). SQL injection payloads are safely sanitized.

### 2. How to Run Assignment 2
```bash
# Navigate to Assignment 2 directory
cd assignment_2

# Install dependencies
pip install -r requirements.txt

# Configure your API key in .env
# (Change 'Your api_key' to your active Groq API key)
# GROQ_API_KEY=Your api_key
# GROQ_MODEL=qwen/qwen3.8-27b

# Seed the database
python data/seed_demo_data.py

# Run the full test suite (99 passing security & unit tests)
pytest tests/ -v

# Run the comparative evaluation benchmark
python evaluation.py

# Launch the secure portal
streamlit run app.py
```

---

## Comparison Matrix: Assignment 1 vs Assignment 2

| Feature / Dimension | Assignment 1 (Baseline) | Assignment 2 (Production-Aware) |
|---|---|---|
| **Access Flow** | Direct dropdown student switcher | Mandatory Sign-Up $\to$ Sign-In authentication |
| **Password Security** | Plaintext demo lookup | Salted SHA-256 hashed passwords |
| **Access Control (RBAC)** | Trust-based (relies on prompt instruction) | Deterministic Python-enforced RBAC |
| **Cross-Student IDOR Defense** | None (student can query any ID) | Strictly blocked (`actor_id == student_id`) |
| **Financial State Modifications** | Direct tool execution | Human-in-the-loop approval workflow |
| **Admin / Approver Governance** | None | Role-based Approver Dashboard (`ADMIN01`) |
| **Action Traceability** | Temporary performance tracing | Immutable, append-only SQLite audit logging |
| **Sensitive Field Masking** | Memory layer rejection | Memory rejection + Audit trail redaction |
| **SQL Injection Mitigation** | Standard queries | 100% Parameterized queries |
| **Test Coverage** | 27 unit & tool tests | 110 comprehensive security & unit tests |

---

## Demo Credentials for Testing

### Student Accounts
| Student ID | Full Name | Program | Password | Initial Fee Balance | Scholarship |
|---|---|---|---|---|---|
| **STU001** | Alice Johnson | Big Data Analytics (BDA) | `student123` | ₹12,000 (Pending) | Merit Scholarship (₹25,000) |
| **STU002** | Bob Smith | AI & Data Science | `student456` | ₹0 (Paid) | Dean's List (₹15,000) |
| **STU003** | Carol Williams | AI & Data Science | `student789` | ₹35,000 (Overdue) | None |

### Administrative / Approver Account (Assignment 2)
| Approver ID | Full Name | Role | Password | Capabilities |
|---|---|---|---|---|
| **ADMIN01** | Dr. Sarah Admin | Approver / Staff | `admin123` | Review & approve fee corrections, view audit logs |

---

## Environment Variable Setup

For both assignments, duplicate `.env.example` into `.env`:
```env
# Groq API Configuration
GROQ_API_KEY=Your api_key
GROQ_MODEL=qwen/qwen3.8-27b
```
Replace `Your api_key` with your valid Groq API key when running live LLM interactions.

