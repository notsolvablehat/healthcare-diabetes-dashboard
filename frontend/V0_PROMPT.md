# v0 Prompt: Healthcare & Diabetes Dashboard Frontend

## Overview
Create a modern, professional healthcare dashboard built with **React 18 + TypeScript**, **TailwindCSS**, and **shadcn/ui components**. This is a patient-doctor management platform focused on diabetes monitoring.

The system has **two primary user roles**:
- **Patients**: View their cases, upload medical reports, see assigned doctors
- **Doctors**: Manage patients, create/review cases, add clinical notes, approve cases

---

## Tech Stack Requirements
- **Framework**: React 18 with TypeScript (strict mode)
- **Styling**: TailwindCSS v3
- **Components**: shadcn/ui (use their Dialog, Table, Form, Card, Button, Input, Select, Tabs, Toast, Badge, Avatar, Dropdown Menu)
- **Routing**: React Router v6
- **State Management**: React Query (TanStack Query) for server state
- **Forms**: React Hook Form + Zod for validation
- **Icons**: Lucide React

---

## Authentication System

The backend uses **JWT Bearer tokens** (HS256). Store tokens in httpOnly cookies or localStorage.

### Auth Endpoints

**POST `/auth/register`** → Returns `201 Created`
```json
// Request
{ "email": "user@example.com", "password": "securepass123", "role": "patient" | "doctor" }
// Response (201 Created)
{ "access_token": "eyJhbG...", "token_type": "bearer" }
```

**POST `/auth/login`**
```json
// Request
{ "email": "user@example.com", "password": "securepass123" }
// Response (200)
{ "access_token": "eyJhbG...", "is_onboarded": false, "role": "patient" | "doctor" }
```

**GET `/users/me`** (Requires Auth Header: `Authorization: Bearer <token>`)
```json
// Response
{ "id": "uuid", "email": "user@example.com", "role": "patient", "is_onboarded": true }
```

---

## Onboarding Flow

After login, check `is_onboarded`. If `false`, redirect to an onboarding wizard.

**POST `/users/onboard`** (Requires Auth)
```json
// Patient Onboarding
{
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1990-01-15",
  "gender": "male",
  "phone_number": "+1234567890",
  "address": "123 Main St",
  "emergency_contact_name": "Jane Doe",
  "emergency_contact_phone": "+0987654321",
  "medical_history": ["Type 2 Diabetes", "Hypertension"],
  "allergies": ["Penicillin"]
}

// Doctor Onboarding
{
  "first_name": "Dr. Jane",
  "last_name": "Smith",
  "phone_number": "+1234567890",
  "specialisation": "Endocrinology",
  "license_number": "MED123456",
  "hospital_affiliation": "City Hospital",
  "max_patients": 50
}
```

---

## User Profile APIs

**GET `/users/profile`** - Returns full profile of logged-in user

**POST `/users/update-profile`** - Update profile fields (phone, address, etc.)

**GET `/users/patient-profile/{patient_id}`** - Doctor can view assigned patient's medical history

---

## Doctor-Patient Assignments

**POST `/assignments/assign`** (Doctor only)
```json
// Request
{ "patient_email": "patient@example.com", "speciality_required": "Endocrinology" }
// Response (200)
{ "message": "Assignment successful", "patient_id": "uuid", "doctor_id": "uuid" }
```

**POST `/assignments/revoke`** (Doctor only)
```json
// Request
{ "patient_email": "patient@example.com", "reason": "Patient transferred to specialist" }
// Response (200)
{ "message": "Access revoked successfully" }
```

**GET `/assignments/my-patients`** (Doctor only)
```typescript
// Response Model: MyPatients
{
  "doctor_id": "string",
  "count": 5,
  "patients": [
    {
      "user_id": "string",
      "patient_id": "string", 
      "name": "John Doe",
      "email": "patient@example.com",
      "gender": "male",
      "date_of_birth": "1990-01-15"
    }
  ]
}
```

**GET `/assignments/doctors`** (Patient only)
```typescript
// Response Model: MyDoctors
{
  "patient_id": "string",
  "count": 2,
  "doctors": [
    {
      "user_id": "string",
      "doctor_id": "string",
      "name": "Dr. Jane Smith",
      "email": "doctor@example.com",
      "specialisation": "Endocrinology",
      "department": "Diabetes Care"
    }
  ]
}
```

---

## Case Management (Core Feature)

Cases are medical consultations following the SOAP format (Subjective, Objective, Assessment, Plan).

**POST `/cases`** (Doctor creates case for a patient)
```json
{
  "patient_id": "patient-uuid-or-patient-id",
  "chief_complaint": "Elevated blood sugar levels",
  "encounter_id": "ENC-2026-001",
  "case_type": "routine_checkup",
  "subjective": { "history_of_present_illness": "Patient reports...", "symptoms": ["fatigue", "thirst"] },
  "objective": { "vital_signs": { "blood_pressure": "120/80", "blood_glucose": "180" }, "physical_exam": "..." },
  "assessment": { "diagnosis": ["E11.9 - Type 2 DM"], "severity": "moderate" },
  "plan": { "treatment": "Increase metformin dosage", "follow_up": "2 weeks" }
}
// Response - includes generated case_id like "CASE202601101A2B3C4D"
```

**GET `/cases/{case_id}`**
- Returns full case with SOAP notes merged from PostgreSQL + MongoDB
- Patients see their own cases, Doctors see assigned patients' cases

**GET `/cases/doctor/{doctor_id}/list`** (Doctor view)
- Query params: `skip`, `limit`, `status`
- Returns summary list: case_id, created_at, chief_complaint, status, patient_id

**GET `/cases/patient/{patient_id}/list`** (Patient view)
- Returns their case history

**PATCH `/cases/{case_id}`**
```json
{
  "status": "in_review",
  "subjective": { "updated_field": "new value" },
  "assessment": { "diagnosis": ["Updated diagnosis"] }
}
```

**POST `/cases/{case_id}/approve`** (Doctor only)
```json
{ "approval_notes": "Case reviewed and approved. Continue treatment plan." }
```

**POST `/cases/{case_id}/notes`** (Doctor adds clinical note)
```json
{
  "content": "Patient showing improvement in glucose levels",
  "note_type": "clinical_note",
  "visibility": "doctor_and_patient",
  "linked_to_case_section": "assessment"
}
```

**GET `/cases/{case_id}/notes`** - Get all notes for a case

---

## File Uploads (Reports)

Uses Supabase Storage with signed URLs for secure uploads.

**POST `/reports/upload-url`** (Request upload URL)
```json
{
  "filename": "blood_test_results.pdf",
  "content_type": "application/pdf",
  "patient_id": "patient-uuid",
  "case_id": "case-id", // optional
  "description": "Monthly blood glucose report"
}
// Response
{ "upload_url": "https://supabase.co/storage/...signed-url", "report_id": "report-uuid", "storage_path": "reports/..." }
```

**Frontend Upload Flow**:
1. Call `/reports/upload-url` to get signed URL
2. Upload file directly to Supabase using the signed URL via PUT request
3. Call `/reports/{report_id}/confirm` to confirm upload

**POST `/reports/{report_id}/confirm`**
```json
{ "storage_path": "reports/patient-id/filename.pdf", "file_size_bytes": 1024000 }
```

**GET `/reports/case/{case_id}`** - List reports attached to a case

**GET `/reports/patient/{patient_id}`** - List all patient reports

**GET `/reports/{report_id}/download`** - Get signed download URL

---

## Required Pages

### 1. Auth Pages
- **Login Page**: Email/password form, link to register
- **Register Page**: Email, password, confirm password, role selection (Patient/Doctor)
- **Onboarding Wizard**: Multi-step form based on role (different fields for Patient vs Doctor)

### 2. Dashboard (Role-based)
- **Patient Dashboard**: 
  - Overview cards (Active Cases, Assigned Doctors, Recent Reports)
  - List of recent cases with status badges
  - Quick actions: View reports, Contact doctor

- **Doctor Dashboard**:
  - Overview cards (Total Patients, Open Cases, Pending Approvals)
  - Patient list with search/filter
  - Cases requiring attention
  - Quick actions: Create case, Add patient

### 3. Case Management
- **Case List View**: Filterable/sortable table with status, patient, date, complaint
- **Case Detail View**: 
  - Tabs for SOAP sections (Subjective, Objective, Assessment, Plan)
  - Notes section with add note form
  - Approval workflow buttons (for doctors)
  - Attached reports/files
  - Audit trail timeline

- **Create/Edit Case Form**: 
  - Patient selector (for doctors)
  - Dynamic SOAP form sections
  - File attachment capability

### 4. Patient Management (Doctor View)
- **Patient List**: Search, filter by status
- **Patient Profile View**: Medical history, allergies, assigned cases, reports
- **Assign Patient Modal**: Search by email

### 5. Reports Page
- **Report List**: Grid/list view of uploaded files
- **Upload Modal**: Drag-drop area, file info form
- **Report Viewer**: PDF preview, download button

### 6. Profile/Settings
- **Profile View**: Display user info
- **Edit Profile Form**: Update contact info, medical history (patients), specialization (doctors)

---

## UI/UX Requirements

1. **Color Scheme**: Medical/professional - Use blues, teals, clean whites. Consider a calming healthcare palette.

2. **Status Badges** for cases:
   - `open` → Blue
   - `in_review` → Yellow/Amber
   - `approved_by_doctor` → Green
   - `rejected` → Red
   - `closed` → Gray

3. **Responsive Design**: Mobile-first, works on tablets for doctors doing rounds

4. **Loading States**: Skeleton loaders for data fetching

5. **Error Handling**: Toast notifications for errors, inline form validation

6. **Empty States**: Helpful illustrations/messages when no data exists

7. **Accessibility**: Proper ARIA labels, keyboard navigation, screen reader support

---

## API Integration Notes

- **Base URL**: `http://localhost:8000` (development)
- **Auth Header**: Include `Authorization: Bearer <token>` on all protected routes
- **Error Format**: 
```json
{ "detail": "Error message here" }
```
- **Common Status Codes**: 
  - 200/201: Success
  - 401: Unauthorized (redirect to login)
  - 403: Forbidden (role mismatch)
  - 404: Not found
  - 422: Validation error

---

## Folder Structure Suggestion

```
src/
├── components/
│   ├── ui/          # shadcn components
│   ├── layout/      # Navbar, Sidebar, Footer
│   ├── forms/       # Reusable form components
│   └── common/      # Cards, Badges, Loaders
├── pages/
│   ├── auth/
│   ├── dashboard/
│   ├── cases/
│   ├── patients/
│   ├── reports/
│   ├── ai/          # Future: AI analysis views
│   └── settings/
├── hooks/           # Custom hooks (useCases, useReports, etc.)
├── services/        # API client functions
├── lib/             # Utils, constants, types
└── store/           # Redux store (slices: auth, cases, patients, ui)
```

---

## Future APIs (In Development)

The following features are planned and the UI should accommodate them:

### AI & Intelligence Module
- **POST `/ai/analyze/{case_id}`** - Triggers NLP analysis on case. Returns `{ task_id }` for async polling
- **POST `/ai/chat`** - RAG-based chatbot for patient history queries
  - Input: `{ message: "What's my glucose trend?", context: "patient_history" }`
- **POST `/feedback/`** - Doctor feedback on AI predictions for model retraining

**UI Considerations**: Reserve space for:
- "AI Analysis" button on case detail page
- AI insights panel/card showing predictions
- Chat widget for patient queries
- Feedback thumbs up/down on AI suggestions

### FHIR Export
- **GET `/cases/{case_id}/export-fhir`** - Export case as FHIR JSON bundle for interoperability

**UI Considerations**: Add "Export" dropdown on case detail with FHIR option

### Hospital Services
- **GET `/hospital/services`** - List of hospital wards/locations for navigation

**UI Considerations**: Navigation/wayfinding section in patient dashboard

---

## Start With

Generate the following core components first:
1. **Redux store setup** with auth slice (login/logout/register, token management)
2. **Protected Route wrapper** using Redux auth state
3. **Main layout** with sidebar navigation (role-aware menu items)
4. **Dashboard pages** for both roles
5. **Case list and detail pages**

The design should feel like a modern SaaS medical platform - clean, trustworthy, and professional. Think of apps like Carta, Linear, or modern EHR systems for inspiration.
