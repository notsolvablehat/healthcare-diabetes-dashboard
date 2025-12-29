#### **Priority 1: Authentication & Onboarding (Foundations)**

*Essential for users to even enter the app.*

* [x] **POST** `/auth/register`
* **Input:** Email, Password, Role (Doctor/Patient).
* **Action:** Creates `User` row. Returns Token.


* [x] **POST** `/auth/login`
* **Input:** Email, Password.
* **Action:** Validates credentials. Returns Token + `is_onboarded` flag.


* [x] **GET** `/users/me`
* **Action:** Returns currently logged-in user's basic info (`id`, `email`, `role`, `is_onboarded`).


* [x] **POST** `/users/onboard`
* **Input:** Full profile data (DOB, Gender, License/Medical History).
* **Action:** Populates the `patients` or `doctors` table and sets `is_onboarded = True`.



#### **Priority 2: Profile & Relationships (The Logic Layer)**

*Connecting Doctors and Patients.*

* [x] **GET** `/users/profile`
* **Action:** Returns the full profile of the **logged-in** user.


* [x] **POST** `/users/update-profile`
* **Action:** Updates phone, address, etc.


* [x] **POST** `/assignments/assign` (Admin/Doctor)
* **Input:** `{ patient_email: str }` or `{ patient_id: UUID }`.
* **Action:** Creates/Activates a link in `doctor_patient_assignments`.


* [x] **POST** `/assignments/revoke` (Admin/Doctor)
* **Input:** `{ patient_id: UUID, reason: str }`.
* **Action:** Sets `is_active = False` in assignment table.


* [x] **GET** `/assignments/my-patients` (Doctor Only)
* **Action:** Returns list of active patients (Name, Age, Last Visit).


* [x] **GET** `/assignments/doctors` (Patient Only)
* **Action:** Returns list of assigned doctors (Name, Specialization).


* [x] **GET** `/users/patient-profile/{patient_id}` (Secured)
* **Action:** Returns full medical history of a specific patient.



#### **Priority 3: Case Management (The Core Feature)**

*The actual medical consultation workflow.*

* [ ] **POST** `/cases/` (Patient)
* **Input:** `{ symptoms: str, vitals: dict }`.
Step 1: Create CaseDetailsMongo document in MongoDB. Get the returned _id.

Step 2: Create Case row in PostgreSQL with mongo_case_id = str(new_mongo_id).

Why: If Postgres fails, you have an orphan doc in Mongo (low risk). If you did Postgres first, you'd have a null link.


* [ ] **GET** `/cases/{case_id}`
* **Action:**
* **Patient:** Returns their own case history.
* **Doctor:** Returns cases from *their assigned* patients only.




* [ ] **GET** `/cases/{case_id}`
* **Action:** Returns full case details, including AI predictions and attached report links.
Step 1: Fetch row from PostgreSQL (to check permissions/doctor assignment).

Step 2: Take mongo_case_id from that row.

Step 3: Fetch the full JSON from MongoDB.

Step 4: Merge and return.

* [ ] **PATCH** `/cases/{case_id}/status` (Doctor)
* **Input:** `{ status: "Reviewed" | "Closed" }`.
* **Action:** Updates workflow state.



#### **Priority 4: Files & Reports (Supabase Integration)**

*Handling PDF uploads.*

* [ ] **POST** `/reports/upload-url`
* **Input:** `{ filename: str, content_type: str }`.
* **Action:** Generates a **Supabase Signed URL** so the frontend can upload the file directly.


* [ ] **POST** `/reports/link`
* **Input:** `{ case_id: UUID, file_url: str, file_type: str }`.
* **Action:** Saves the file metadata in your DB linked to the Case.


* [ ] **GET** `/reports/{case_id}`
* **Action:** Lists all files attached to a case.



#### **Priority 5: AI & Intelligence (Celery/Background)**

*The "Smart" features.*

* [ ] **POST** `/ai/analyze/{case_id}`
* **Action:** Triggers the Celery task (NLP + Prediction). Returns `{ task_id }`.


* [ ] **POST** `/ai/chat` (RAG Bot)
* **Input:** `{ message: str, context: "patient_history" }`.
* **Action:** Uses LLM to answer questions based on the patient's specific records.


* [ ] **POST** `/feedback/` (Doctor)
* **Input:** `{ case_id: UUID, is_accurate: bool, correction: str }`.
* **Action:** Saves doctor's validation for future model retraining.



#### **Priority 6: Extras (Deliverables)**

*Items mentioned in your Design Doc.*

* [ ] **GET** `/cases/{case_id}/export-fhir`
* 
**Action:** Returns the case data formatted as a standard FHIR JSON bundle.




* [ ] **GET** `/hospital/services`
* **Action:** Returns static list of hospital wards/locations for the "Navigation" feature.
