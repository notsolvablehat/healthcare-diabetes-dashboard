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
* **Input:** `{ patient_email: str }` or `{ patient_id: str }`.
* **Action:** Creates/Activates a link in `doctor_patient_assignments`.


* [x] **POST** `/assignments/revoke` (Admin/Doctor)
* **Input:** `{ patient_id: str, reason: str }`.
* **Action:** Sets `is_active = False` in assignment table.


* [x] **GET** `/assignments/my-patients` (Doctor Only)
* **Action:** Returns list of active patients (Name, Age, Last Visit).


* [x] **GET** `/assignments/doctors` (Patient Only)
* **Action:** Returns list of assigned doctors (Name, Specialization).


* [x] **GET** `/users/patient-profile/{patient_id}` (Secured)
* **Action:** Returns full medical history of a specific patient.



#### **Priority 3: Case Management (The Core Feature)**

*The actual medical consultation workflow.*

* [x] **POST** `/cases` (Patient)
* **Input:** `{ symptoms: str, vitals: dict }`.
* Logic: 
1. Create the document in MongoDB first. Get the string _id.
2. Create the row in PostgreSQL with mongo_case_id and patient_id (from CurrentUser).
3. Future Step: Trigger the "NLP Normalization Engine" mentioned in your System Design

* [x] **GET** `/cases/{case_id}`
* **Action:**
* **Patient:** Returns their own case history.
* **Doctor:** Returns cases from *their assigned* patients only.

* Logic:
1. Fetch the Row from Postgres using case_id.
2. Security Check: If requester is a doctor, is he assigned to this patient? If requester is a patient, is it his case?
3. Take mongo_case_id from the row.
4. Fetch the full JSON from MongoDB.
5. Merge them into one response (Status from SQL + Symptoms from Mongo).

* [x] **GET** `/cases`
* Logic:
If Patient: SELECT * FROM cases WHERE patient_id = me.
If Doctor: SELECT * FROM cases WHERE doctor_id = me.
Note: Do not fetch MongoDB data here. Just return the SQL summaries (Date, Status, Patient Name) to keep the list fast. Merge and return.

* [x] **PATCH** `/cases/{case_id}/status` (Doctor)
* **Input:** `{ status: "Closed" | "Accepted" | "Rejeted" }`.
* **Action:** Updates workflow state.
* Logic:
Verify Doctor owns this case.
Update status in PostgreSQL.
Update doctor_notes inside the MongoDB document (append to a notes array).

#### **Priority 4: Files & Reports (Supabase Integration)**

*Handling PDF uploads.*

* [x] **POST** `/reports/upload-url`
* **Input:** `{ filename: str, content_type: str, patient_id: str, case_id?: str, description?: str }`.
* **Action:** Generates a **Supabase Signed URL** for direct frontend upload. Creates pending report record in DB.


* [x] **POST** `/reports/{report_id}/confirm`
* **Input:** `{ storage_path: str, file_size_bytes?: int }`.
* **Action:** Confirms upload and saves file size.


* [x] **GET** `/reports/case/{case_id}`
* **Action:** Lists all files attached to a case.


* [x] **GET** `/reports/patient/{patient_id}`
* **Action:** Lists all reports for a patient.


* [x] **GET** `/reports/{report_id}`
* **Action:** Get single report metadata.


* [x] **GET** `/reports/{report_id}/download`
* **Action:** Generates a signed download URL for viewing/downloading the file.


#### **Priority 5: AI & Intelligence**

*Full AI pipeline with Gemini 2.5 Flash, TF-IDF keyword extraction, and chat system.*

* [x] **POST** `/ai/extract-report/{report_id}`
* **Action:** Extract complete medical data from a report (general, not diabetes-specific).
* **Returns:** `{ extracted_data, raw_text, mongo_analysis_id, processing_time_ms }`
* **Note:** Uses TF-IDF to identify important keywords, then Gemini for structured extraction.
* **Auto-triggered:** Background extraction runs automatically on report upload confirmation.


* [x] **POST** `/ai/chat/start`
* **Input:** `{ patient_id?: str, report_ids?: list[str] }`
* **Action:** Start a new chat session with optional report attachment.
* **Returns:** `{ chat_id, patient_id, attached_report_ids, created_at }`


* [x] **POST** `/ai/chat/{chat_id}/message`
* **Input:** `{ message: str, attach_report_ids?: list[str] }`
* **Action:** Send message and get AI response. Context built once on first message.
* **Returns:** `{ message_id, response, sources, title?, timestamp }`


* [x] **GET** `/ai/chat/{chat_id}/history`
* **Action:** Get full chat history with all messages.
* **Returns:** `{ chat_id, patient_id, title, messages: list, created_at, updated_at }`


* [x] **GET** `/ai/chats`
* **Action:** List all chats for the current user.
* **Returns:** `{ total, chats: list }`


* [x] **DELETE** `/ai/chat/{chat_id}`
* **Action:** Delete a chat and all its messages.


* [x] **PATCH** `/ai/chat/{chat_id}/reports`
* **Input:** `{ report_ids: list[str], action: "add"|"remove"|"replace" }`
* **Action:** Attach or detach reports from a chat.


* [x] **POST** `/ai/analyze-report/{report_id}` *(Legacy)*
* **Action:** Analyze report with XGBoost diabetes prediction.
* **Returns:** `{ extracted_features, prediction, narrative, mongo_analysis_id }`


* [x] **POST** `/ai/summarize-case/{case_id}`
* **Action:** Generate AI summary of an entire case including all reports and doctor notes.
* **Returns:** `{ summary, key_findings: list, recommendations: list }`


* [x] **POST** `/ai/ask` *(Legacy - use chat instead)*
* **Input:** `{ patient_id: str, question: str }`
* **Action:** RAG-based Q&A about a patient's medical history.
* **Returns:** `{ answer: str, sources: list }`


* [x] **GET** `/ai/insights/{patient_id}`
* **Action:** Get AI-generated health insights and trends for a patient.
* **Returns:** `{ insights: list, risk_factors: list, trends: list }`
* **Note:** Uses TF-IDF keyword extraction to highlight important terms.


* [ ] **POST** `/feedback/` (Doctor)
* **Input:** `{ case_id: str, is_accurate: bool, correction: str }`.
* **Action:** Saves doctor's validation for future model improvement.



#### **Priority 6: Extras (Deliverables)**

*Items mentioned in your Design Doc.*

* [ ] **GET** `/cases/{case_id}/export-fhir`
* 
**Action:** Returns the case data formatted as a standard FHIR JSON bundle.




* [ ] **GET** `/hospital/services`
* **Action:** Returns static list of hospital wards/locations for the "Navigation" feature.
