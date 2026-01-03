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

* [ ] **POST** `/cases` (Patient)
* **Input:** `{ symptoms: str, vitals: dict }`.
* Logic: 
1. Create the document in MongoDB first. Get the string _id.
2. Create the row in PostgreSQL with mongo_case_id and patient_id (from CurrentUser).
3. Future Step: Trigger the "NLP Normalization Engine" mentioned in your System Design

* [ ] **GET** `/cases/{case_id}`
* **Action:**
* **Patient:** Returns their own case history.
* **Doctor:** Returns cases from *their assigned* patients only.

* Logic:
1. Fetch the Row from Postgres using case_id.
2. Security Check: If requester is a doctor, is he assigned to this patient? If requester is a patient, is it his case?
3. Take mongo_case_id from the row.
4. Fetch the full JSON from MongoDB.
5. Merge them into one response (Status from SQL + Symptoms from Mongo).

* [ ] **GET** `/cases`
* Logic:
If Patient: SELECT * FROM cases WHERE patient_id = me.
If Doctor: SELECT * FROM cases WHERE doctor_id = me.
Note: Do not fetch MongoDB data here. Just return the SQL summaries (Date, Status, Patient Name) to keep the list fast. Merge and return.

* [ ] **PATCH** `/cases/{case_id}/status` (Doctor)
* **Input:** `{ status: "Closed" | "Accepted" | "Rejeted" }`.
* **Action:** Updates workflow state.
* Logic:
Verify Doctor owns this case.
Update status in PostgreSQL.
Update doctor_notes inside the MongoDB document (append to a notes array).

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
