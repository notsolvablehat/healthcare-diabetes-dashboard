# Medical Case Models Specification

This document details the models used in the `src/cases/` module, which follows a **dual-database pattern**:
1.  **PostgreSQL (SQLAlchemy)**: Stores relational metadata for fast querying, lists, and filtering.
2.  **MongoDB (Pydantic)**: Stores the complete clinical data (SOAP notes, audit trails, notes) as a JSON document.

---

## 1. Relational Models (PostgreSQL)
Defined in `src/schemas/cases.py`.

### **`Case` (SQLAlchemy)**
The relational representation of a medical case.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Primary key (as UUID string). |
| `case_id` | `String` | Human-readable ID (e.g., `CASE20260118...`). |
| `mongo_case_id` | `String` | Reference to the `_id` in MongoDB. |
| `patient_id` | `String` | Foreign key to `users.id` (Patient). |
| `doctor_id` | `String` | Foreign key to `users.id` (Doctor). |
| `status` | `String` | Current status (`open`, `under_review`, `approved_by_doctor`, `closed`). |
| `chief_complaint` | `String` | Short summary for list views. |
| `created_at` | `DateTime` | Timestamp of creation. |
| `updated_at` | `DateTime` | Timestamp of last update. |

---

## 2. Clinical Data Models (Pydantic / MongoDB)
Defined in `src/cases/models.py`. These models structure the data stored in MongoDB and returned by the API.

### **Core Case Model: `Case`**
The full representation of a case.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Internal UUID. |
| `case_id` | `str` | Yes | Business ID. |
| `patient_id` | `str` | Yes | Patient user ID. |
| `doctor_id` | `str` | Yes | Doctor user ID. |
| `case_type` | `CaseType` | Yes | `initial`, `follow_up`, `urgent`, etc. |
| `status` | `CaseStatus` | Yes | `open`, `under_review`, etc. |
| `subjective` | `SubjectiveSection` | No | S in SOAP. |
| `objective` | `ObjectiveSection` | No | O in SOAP. |
| `assessment` | `AssessmentSection` | No | A in SOAP. |
| `plan` | `PlanSection` | No | P in SOAP. |
| `doctor_notes` | `list[DoctorNote]` | No | Chronological notes. |
| `audit_trail` | `list[AuditLog]` | No | History of actions. |

---

### **SOAP Sections**

#### **`SubjectiveSection`**
- `chief_complaint`: Primary reason for visit.
- `history_of_present_illness`: Symptom onset, duration, character.
- `past_medical_history`: Previous conditions.
- `current_medications`: List of drugs.
- `allergies`: Drug/Food allergies.
- `social_history`: Lifestyle data.

#### **`ObjectiveSection`**
- `vital_signs`: Blood pressure, Heart rate, Temp, Weight, BMI.
- `physical_examination`: Findings per system.
- `lab_results`: Individual test values and units.
- `imaging_results`: Radiology impressions and S3 links.

#### **`AssessmentSection`**
- `problem_list`: Diagnoses with SNOMED/ICD codes.
- `differential_diagnoses`: Possible conditions being explored.
- `clinical_impression`: Overall medical summary.

#### **`PlanSection`**
- `diagnostic_plan`: Tests ordered.
- `medications`: Prescriptions.
- `procedures`: Planned medical procedures.
- `education`: Instructions provided to patient.
- `follow_up`: Date and type of next visit.

---

### **Request Models (API)**

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **`CaseCreate`** | Start a new case | `patient_id`, `chief_complaint`, `case_type` |
| **`CaseUpdate`** | Modify existing case | Optional SOAP sections and `status` |
| **`DoctorNoteCreate`** | Add a note | `case_id`, `content`, `note_type`, `visibility` |
| **`CaseApprovalRequest`**| Approve a case | `approval_notes` |

---

## 3. Enumerations (Common Values)

- **`CaseStatus`**: `open`, `closed`, `under_review`, `approved_by_doctor`.
- **`SeverityLevel`**: `critical`, `high`, `moderate`, `low`.
- **`MedicationFrequency`**: `once daily`, `twice daily`, `as needed`, etc.
- **`ObservationStatus`**: `pending`, `final`, `preliminary`.
