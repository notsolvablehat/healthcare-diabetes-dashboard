# Healthcare & Diabetes Dashboard - Architecture

## 1. Project Overview
**Description:** A FastAPI backend for managing healthcare data, patient-doctor relationships, and diabetes monitoring.
**Version:** 0.1.0
**License:** MIT

### Tech Stack
* **Core:** Python 3.10+, FastAPI 0.128.0
* **Database (Relational):** PostgreSQL (via SQLAlchemy + Pydantic)
* **Database (NoSQL):** MongoDB (pymongo) & Supabase (Auth/Storage)
* **Security:** Passlib (Bcrypt), PyJWT
* **Utilities:** SlowAPI (Rate Limiting), Sentry (Monitoring)

---

## 2. Project Structure
Based on the imports and file organization:

```text
src/
├── assignments/            # [DONE] Doctor-Patient Relationship Logic
│   ├── controller.py       # Routes: /assignments/*
│   ├── models.py           # Pydantic Schemas (Req/Res)
│   └── services.py         # Business Logic (Load balancing, querying)
├── auth/                   # [DONE] Authentication
│   ├── controller.py       # Routes: /auth/*
│   └── services.py         # JWT & CurrentUser dependency
├── users/                  # [DONE] User Profile Management
│   ├── controller.py       # Routes: /users/*
│   └── services.py         # Profile updates & fetching
├── cases/                  # [DONE] Medical Case Management
│   ├── controller.py       # Routes: /cases/*
│   ├── models.py           # Pydantic Schemas
│   └── services.py         # Dual-write: Postgres + MongoDB
├── reports/                # [DONE] File Uploads
│   ├── controller.py       # Routes: /reports/*
│   ├── models.py           # Pydantic Schemas
│   └── services.py         # Supabase Storage integration
├── schemas/                # SQLAlchemy ORM Models
│   ├── users/
│   │   └── users.py        # User, Doctor, Patient, Assignment tables
│   ├── cases.py            # Cases table
│   └── reports.py          # Reports table
├── database/
│   ├── core.py             # PostgreSQL Session & Engine
│   ├── mongo.py            # MongoDB Client
│   └── supabase.py         # Supabase Storage Client
├── api.py                  # Central Router Registration
├── main.py                 # App Entrypoint & Middleware
├── logging.py              # Custom Logging Configuration
└── rate_limiting.py        # SlowAPI Configuration
```

---

## 3. Database Schema (SQLAlchemy)

The system uses a **One-to-One** inheritance strategy for Users profiles, and a **Many-to-Many** link for Assignments.

### Core Tables

1. **`users`**: Central identity table.
* Columns: `id` (UUID), `email`, `hashed_pass`, `role`, `is_onboarded`.


2. **`patients`**: Medical profile.
* **PK/FK:** `user_id` links to `users.id`.
* **Data:** `medical_history`, `allergies` (Postgres Arrays), `emergency_contact`.


3. **`doctors`**: Professional profile.
* **PK/FK:** `user_id` links to `users.id`.
* **Data:** `specialisation` (Indexed), `license`, `max_patients`.


4. **`doctor_patient_assignments`**: The link table.
* **Logic:** Contains a Partial Unique Index (`unique_active_assignment`) ensuring a patient can only have **one active assignment** with a specific doctor at a time.
* **Columns:** `is_active` (Boolean), `revoked_at` (DateTime).


---

## 4. API Status & Roadmap


### ✅ Priority 1 & 2: Foundations (Completed)

* **Auth:** Register, Login, Get Current User.
* **Profiles:** Get Profile, Update Profile, Onboard (Patient/Doctor).
* **Assignments:**
* `POST /assignments/assign`: Assign patient to doctor (Load balanced).
* `POST /assignments/revoke`: Soft-delete assignment.
* `GET /assignments/patient`: List my patients (Doctor view).
* `GET /assignments/doctors`: List my doctors (Patient view).


### ✅ Priority 3: Case Management (Completed)

* `POST /cases/`: Create a new case (Dual write: Postgres + MongoDB).
* `GET /cases/{case_id}`: Fetch case details (Merge Relational + NoSQL data).
* `PATCH /cases/{case_id}`: Update case details.
* `POST /cases/{case_id}/approve`: Doctor approval workflow.

### ✅ Priority 4: Reports (Completed)

* `POST /reports/upload-url`: Generate signed upload URL for Supabase Storage.
* `POST /reports/{id}/confirm`: Confirm upload after frontend uploads file.
* `GET /reports/case/{case_id}`: List reports for a case.
* `GET /reports/patient/{patient_id}`: List all patient reports.
* `GET /reports/{id}/download`: Get signed download URL.

### ✅ Priority 5: AI & Intelligence (Completed)

* `POST /ai/extract-report/{report_id}`: Full medical data extraction with TF-IDF + Gemini.
* `POST /ai/chat/start`: Start chat session with optional report attachment.
* `POST /ai/chat/{id}/message`: Send message, get AI response (context built once).
* `GET /ai/chat/{id}/history`: Get full chat history.
* `GET /ai/chats`: List user's chats.
* `DELETE /ai/chat/{id}`: Delete chat.
* `PATCH /ai/chat/{id}/reports`: Attach/detach reports.
* `POST /ai/analyze-report/{id}`: Legacy diabetes analysis with XGBoost.
* `POST /ai/summarize-case/{id}`: AI case summary.
* `POST /ai/ask`: Legacy Q&A (use chat instead).
* `GET /ai/insights/{patient_id}`: Health insights with TF-IDF keywords.

### ⏳ Priority 6: Extras (Pending)


* **FHIR:** Standardized data export.

---

## 5. Development Guidelines (How to build new features)

### A. The Pattern

All new features must follow the **Controller-Service-Model** separation pattern used in `src/assignments`.

#### 1. Define Models (`models.py` & `schemas/`)

* **SQLAlchemy (`src/schemas/`)**: Define the database table.
* **Pydantic (`src/feature/models.py`)**: Define the Request (Input) and Response (Output) shapes.
* *Example:* `PatientAssignRequest` validates email and speciality before code execution.



#### 2. Implement Service (`services.py`)

* **Strict Logic:** No HTTP imports (`HTTPException` is allowed but prefer custom errors).
* **Dependency:** Functions accept `db: DbSession` and raw data (UUIDs, Pydantic objects).
* **Example Logic (Assignments):**
1. Validate User Role.
2. Check if Patient exists.
3. **Algorithm:** Calculate current load of all doctors with `specialisation`. Sort by `count`. Pick lowest.
4. Commit to DB.



#### 3. Create Controller (`controller.py`)

* **Router:** Use `APIRouter` with tags.
* **Injection:** Inject `db: DbSession` and `user: CurrentUser`.
* **Responsibility:** Call the service, handle exceptions, return the result.
```python
@router.post("/assign")
def assign(user: CurrentUser, data: RequestModel, db: DbSession):
    return service_function(db, user.id, data)

```



### B. Dependency Injection

* **Database:** Always use `db: DbSession`. This ensures the connection opens/closes automatically per request.
* **Auth:** Always use `user: CurrentUser`. This validates the JWT and returns the User ORM object.

### C. Rate Limiting

* Apply the `@limiter.limit("5/minute")` decorator to expensive endpoints (like Login or AI analysis).

### D. Error Handling

* Use `HTTPException` with clear status codes.
* **403:** Role mismatch (e.g., Patient trying to list patients).
* **404:** Resource not found (e.g., Doctor not found).
* **409/226:** Conflict (e.g., Patient already assigned).

---

## 6. Detailed Feature Logic: Assignments

*Reference implementation for future logic.*

**The "Smart Assignment" Algorithm:**

1. **Input:** Patient Email + Required Speciality.
2. **Query:**
* Fetch all doctors with that speciality.
* Subquery: Count `is_active` assignments per doctor.


3. **Filter:** Exclude doctors where `current_load >= max_patients`.
4. **Sort:** Ascending by `current_load`.
5. **Result:** Assign to the 0th index (least loaded).
