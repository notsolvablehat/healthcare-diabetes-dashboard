# AI Project Context: Healthcare & Diabetes Dashboard

**Last Updated:** 2026-01-03
**Version:** 0.1.0

## 1. Project Overview
This is a **FastAPI** backend for a healthcare management system focused on diabetes monitoring. It connects Patients and Doctors, allowing for case management, medical records usage, and AI-assisted analysis.

### Tech Stack
-   **Framework:** FastAPI (Python 3.10+)
-   **Databases:**
    -   **PostgreSQL:** Relational data (Users, Profiles, Assignments, Case metadata). Used via **SQLAlchemy**.
    -   **MongoDB:** Document data (Medical Cases, Doctor Notes, Audit Trails). Used via **PyMongo**.
    -   **Dual-Write Strategy:** Critical data (Cases) is written to both. Postgres for relational integrity/lists, Mongo for flexible medical documents.
-   **Authentication:** JWT (HS256) with Passlib (Bcrypt).
-   **Storage:** Supabase (for PDF reports/imaging - Pending).
-   **Task Queue:** Celery (Cancelled - using synchronous async endpoints).

## 2. Directory Structure
```text
/
├── APIs.md                     # API Endpoint status and checklist
├── case_schema_models.py       # Pydantic models for the Case system (Single Source of Truth)
├── implementation_guide.md     # DETAILED guide/code for implementing cases
├── src/
│   ├── api.py                  # Router registration
│   ├── main.py                 # Entry point
│   ├── auth/                   # [DONE] Login/Register
│   ├── users/                  # [DONE] Profiles (Patients/Doctors)
│   ├── assignments/            # [DONE] Doctor-Patient relationships (Load balancing logic)
│   ├── cases/                  # [DONE] Medical case management
│   ├── reports/                # [DONE] File uploads via Supabase Storage
│   │   ├── controller.py       # Routes: /reports/*
│   │   ├── models.py           # Pydantic schemas
│   │   └── services.py         # Upload/Download URL generation
│   ├── ai/                     # [DONE] AI-powered analysis
│   │   ├── controller.py       # Routes: /ai/*
│   │   ├── gemini_client.py    # Gemini 2.5 Flash integration
│   │   ├── ml_models.py        # XGBoost diabetes predictor
│   │   ├── models.py           # Pydantic schemas
│   │   └── services.py         # Analysis pipeline orchestration
│   ├── ml_model/               # Pre-trained XGBoost model
│   │   └── diabetes_xgboost_model.json
│   ├── database/
│   │   ├── core.py             # PostgreSQL (SQLAlchemy)
│   │   ├── mongo.py            # MongoDB client
│   │   └── supabase.py         # Supabase Storage client
│   ├── schemas/                # SQLAlchemy models
│       ├── users/              # User/Profile/Assignment tables
│       ├── cases.py            # Cases table
│       └── reports.py          # Reports table
└── ...
```

## 3. Current Status

### ✅ Completed (Foundations)
-   **Authentication:** Registration, Login, JWT handling.
-   **User Management:** Patient/Doctor profiles, Onboarding flow.
-   **Assignments:**
    -   Patients can be assigned to Doctors.
    -   Load balancing logic exists (assign to least loaded doctor).
    -   `src/assignments` is fully implemented.

### ✅ Completed (Case Management)
-   `src/cases` is fully implemented with dual-write to PostgreSQL + MongoDB.
-   SOAP notes, doctor notes, approval workflow.

### ✅ Completed (Reports)
-   `src/reports` is fully implemented.
-   File uploads (PDF, images) via Supabase Storage signed URLs.
-   Access control: Patients access own reports, Doctors access assigned patients' reports.

### ✅ Completed (AI Analysis)
-   `src/ai` is fully implemented with Gemini 2.5 Flash + XGBoost pipeline.
-   Report analysis, case summarization, Q&A, and patient insights.

### ⏳ Future/Roadmap
-   **FHIR Export:** Standardized data export.

## 4. Architecture & Patterns
-   **Controller-Service-Model:**
    -   `controller.py`: HTTP routes, input validation, calls service.
    -   `service.py`: Business logic, DB transactions.
    -   `models.py`: Pydantic schemas (Request/Response).
    -   `src/schemas/`: SQLAlchemy ORM models.
-   **Dependency Injection:**
    -   `db: DbSession` (Postgres)
    -   `user: CurrentUser` (Auth)

## 5. Implementation Instructions (For AI)
If you are asked to implement **Cases**:
1.  **Read `implementation_guide.md`**: It has the code. Copy it.
2.  **Read `case_schema_models.py`**: It has the Pydantic models.
3.  **Create `src/schemas/cases.py`**: Retrieve the SQLAlchemy model definition from the guide.
4.  **Populate `src/cases/`**: Fill the empty files with the code from the guide.
5.  **Verify Imports**: Ensure `src/main.py` or `src/api.py` includes the new router.

## 6. Key Data Models
-   **User:** Base identity.
-   **Patient/Doctor:** 1:1 relationship with User.
-   **Case:**
    -   **Postgres:** ID, Status, PatientID, DoctorID (for fast listing/relational integrity).
    -   **MongoDB:** Detailed SOAP notes (Subjective, Objective, Assessment, Plan), Audit Logs, Doctor Notes.
    -   Link established via `mongo_doc_id` in Postgres table.
