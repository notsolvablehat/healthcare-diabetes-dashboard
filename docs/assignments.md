# Assignments Module Documentation

## Overview
The assignments module manages the relationship between doctors and patients in the system. It handles automatic doctor assignment based on specialization and workload, tracks active assignments, and allows for access revocation. The module ensures optimal load distribution across doctors while maintaining active patient-doctor relationships.

---

## 1. Core Concepts

### **Doctor-Patient Assignment**
- Assignments link doctors to patients based on required medical specialization.
- Each doctor has a maximum patient capacity (`max_patients` field).
- The system automatically assigns patients to doctors with the lowest current workload.
- Only active assignments are counted toward a doctor's patient load.

### **Assignment States**
- **Active** (`is_active=True`): Doctor currently has access to patient records and cases.
- **Revoked** (`is_active=False`): Access has been terminated (discharge, transfer, etc.).

---

## 2. Database Schema (PostgreSQL)

### **`Assignment` (SQLAlchemy)**
Table: `doctor_patient_assignments`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Primary key (UUID). |
| `doctor_user_id` | `String` | Foreign key to `users.id` (Doctor). |
| `patient_user_id` | `String` | Foreign key to `users.id` (Patient). |
| `is_active` | `Boolean` | Whether the assignment is currently active. |
| `assigned_at` | `DateTime` | Timestamp of when the assignment was created. |
| `revoked_at` | `DateTime` | Timestamp of when access was revoked (null if active). |

**Constraints:**
- Unique partial index on `(doctor_user_id, patient_user_id)` where `is_active = True`.
- This ensures a doctor can only have one active assignment with a patient at a time.

---

## 3. API Endpoints

### **Get All Specialities**
Fetch all available doctor specializations in the system.

- **Endpoint**: `GET /assignments/specialities`
- **Auth**: Not required (Public endpoint)
- **Response**:
```json
{
  "count": 8,
  "specialities": [
    "Cardiology",
    "Dermatology",
    "Emergency Medicine",
    "General Practice",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "Psychiatry"
  ]
}
```

**Use Cases:**
- Display dropdown options when assigning patients to doctors.
- Show available specializations on patient registration forms.
- Filter doctors by specialization in the UI.

---

### **Get Patient by Email (Doctor View)**
Fetch complete patient information by email if the patient is assigned to the logged-in doctor.

- **Endpoint**: `GET /assignments/get-my-patient/{patient_email}`
- **Auth**: Required (Doctor role only)
- **Path Parameter**: `patient_email` - Email address of the patient
- **Response**:
```json
{
  "user_id": "patient-uuid-123",
  "patient_id": "PAT123456",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "username": "johndoe",
  "is_onboarded": true,
  "created_at": "2025-06-15T10:00:00Z",
  "date_of_birth": "1985-05-15",
  "gender": "male",
  "phone_number": "+1234567890",
  "address": "123 Main St, City, State 12345",
  "blood_group": "O+",
  "height_cm": 175.5,
  "weight_kg": 72.3,
  "allergies": ["Penicillin", "Peanuts"],
  "current_medications": ["Lisinopril 10mg daily"],
  "medical_history": ["Hypertension", "Type 2 Diabetes"],
  "emergency_contact_name": "Jane Doe",
  "emergency_contact_phone": "+1234567891"
}
```

**Use Cases:**
- Look up patient details by email when creating a case
- Verify patient information before assignment
- Quick patient profile access from email reference

**Error Cases:**
- `400`: User is required
- `403`: Only doctors can access this endpoint
- `404`: Patient not found or not assigned to the requesting doctor

---

### **Get My Patients (Doctor View)**
Fetch all patients currently assigned to the logged-in doctor, including historical assignments.

- **Endpoint**: `GET /assignments/patient`
- **Auth**: Required (Doctor role)
- **Response**:
```json
{
  "doctor_id": "550e8400-e29b-41d4-a716-446655440000",
  "count": 12,
  "patients": [
    {
      "user_id": "patient-uuid-1",
      "patient_id": "PAT123456",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "gender": "male",
      "date_of_birth": "1985-05-15"
    }
  ],
  "history": [
    {
      "user_id": "patient-uuid-2",
      "patient_id": "PAT789012",
      "name": "Jane Smith",
      "email": "jane.smith@example.com",
      "gender": "female",
      "date_of_birth": "1992-08-22",
      "assigned_at": "2025-09-10T08:00:00Z",
      "revoked_at": "2026-01-15T10:30:00Z",
      "reason": "Treatment completed"
    },
    {
      "user_id": "patient-uuid-3",
      "patient_id": "PAT345678",
      "name": "Robert Johnson",
      "email": "robert.johnson@example.com",
      "gender": "male",
      "date_of_birth": "1978-03-14",
      "assigned_at": "2025-06-20T14:15:00Z",
      "revoked_at": "2025-09-08T16:00:00Z",
      "reason": "Transfer to another facility"
    }
  ]
}
```

**Response Fields:**
- `patients`: Currently active patient assignments.
- `history`: Previously assigned patients, sorted by most recently revoked first.

---

### **Get My Doctors (Patient View)**
Fetch all doctors currently assigned to the logged-in patient, including historical assignments.

- **Endpoint**: `GET /assignments/doctors`
- **Auth**: Required (Patient role)
- **Response**:
```json
{
  "patient_id": "patient-uuid-123",
  "count": 2,
  "doctors": [
    {
      "user_id": "doctor-uuid-1",
      "doctor_id": "DOC987654",
      "name": "Dr. Sarah Smith",
      "email": "sarah.smith@hospital.com",
      "specialisation": "Cardiology",
      "department": "Internal Medicine"
    }
  ],
  "history": [
    {
      "user_id": "doctor-uuid-2",
      "doctor_id": "DOC123456",
      "name": "Dr. John Williams",
      "email": "john.williams@hospital.com",
      "specialisation": "General Practice",
      "department": "Primary Care",
      "assigned_at": "2025-11-15T09:30:00Z",
      "revoked_at": "2026-01-10T14:20:00Z",
      "reason": "Patient discharged"
    },
    {
      "user_id": "doctor-uuid-3",
      "doctor_id": "DOC789012",
      "name": "Dr. Emily Chen",
      "email": "emily.chen@hospital.com",
      "specialisation": "Neurology",
      "department": "Specialty Care",
      "assigned_at": "2025-08-20T11:00:00Z",
      "revoked_at": "2025-11-14T16:45:00Z",
      "reason": "Transfer to another facility"
    }
  ]
}
```

**Response Fields:**
- `doctors`: Currently active doctor assignments.
- `history`: Previously assigned doctors, sorted by most recently revoked first.

---

### **Assign Patient to Doctor**
Automatically assigns a patient to the most suitable doctor based on specialization and current workload.

- **Endpoint**: `POST /assignments/assign`
- **Auth**: Required (Doctor or Admin role)
- **Request Body**:
```json
{
  "patient_email": "patient@example.com",
  "speciality_required": "Cardiology"
}
```

**Response (Success)**:
```json
{
  "status": "success",
  "assigned_doctor": "DOC123456",
  "specialization": "Cardiology",
  "current_load": 8
}
```

**Response (Already Assigned)**:
```json
{
  "message": "This patient is already assigned to doctor DOC123456"
}
```
*Status Code: 226 IM Used*

**Error Cases**:
- `404`: Patient not found or no doctors available with required specialization.
- `400`: User is not fully onboarded as a patient.
- `409`: All specialists are currently fully booked.

---

### **Revoke Patient Access**
Revoke a doctor's access to a patient's records.

- **Endpoint**: `POST /assignments/revoke`
- **Auth**: Required (Doctor or Admin role)
- **Request Body**:

**For Doctors (revoking own access)**:
```json
{
  "patient_email": "patient@example.com",
  "reason": "Patient discharged"
}
```

**For Admins (revoking any doctor's access)**:
```json
{
  "patient_email": "patient@example.com",
  "doctor_identifier": "DOC123456",  // Can be doctor_id or email
  "reason": "Transfer to another facility"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Access revoked for patient patient@example.com."
}
```

**Error Cases**:
- `403`: Insufficient permissions or admin missing `doctor_identifier`.
- `404`: Patient or doctor not found, or no active assignment exists.

---

## 4. Data Models (Pydantic)

### **`PatientSummary`**
Lightweight representation of a patient for list views.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | User UUID. |
| `patient_id` | `str` | Business ID (e.g., PAT123456). |
| `name` | `str` | Patient's full name. |
| `email` | `EmailStr` | Patient's email. |
| `gender` | `str` | Patient's gender. |
| `date_of_birth` | `date` | Patient's date of birth. |

---

### **`PatientHistoryEntry`**
Historical record of a previously assigned patient.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | User UUID. |
| `patient_id` | `str` | Business ID (e.g., PAT123456). |
| `name` | `str` | Patient's full name. |
| `email` | `EmailStr` | Patient's email. |
| `gender` | `str` | Patient's gender. |
| `date_of_birth` | `date` | Patient's date of birth. |
| `assigned_at` | `datetime` | When the assignment was created. |
| `revoked_at` | `datetime` | When the assignment was revoked. |
| `reason` | `str` | Reason for revocation (optional). |

---

### **`PatientDetailResponse`**
Complete patient information with medical profile (for doctors).

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | User UUID. |
| `patient_id` | `str` | Business ID (e.g., PAT123456). |
| `name` | `str` | Patient's full name. |
| `email` | `EmailStr` | Patient's email. |
| `username` | `str` | Patient's username. |
| `is_onboarded` | `bool` | Whether patient completed profile. |
| `created_at` | `datetime` | Account creation date. |
| `date_of_birth` | `date` | Patient's date of birth. |
| `gender` | `str` | Patient's gender. |
| `phone_number` | `str` | Patient's phone number. |
| `address` | `str` | Patient's address. |
| `blood_group` | `str` | Blood type (optional). |
| `height_cm` | `float` | Height in centimeters (optional). |
| `weight_kg` | `float` | Weight in kilograms (optional). |
| `allergies` | `list[str]` | List of allergies (optional). |
| `current_medications` | `list[str]` | Current medications (optional). |
| `medical_history` | `list[str]` | Medical history (optional). |
| `emergency_contact_name` | `str` | Emergency contact name. |
| `emergency_contact_phone` | `str` | Emergency contact phone. |

---

### **`DoctorSummary`**
Lightweight representation of a doctor for list views.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | User UUID. |
| `doctor_id` | `str` | Business ID (e.g., DOC987654). |
| `name` | `str` | Doctor's full name. |
| `email` | `EmailStr` | Doctor's email. |
| `specialisation` | `str` | Medical specialization. |
| `department` | `str` | Hospital department. |

---

### **`DoctorHistoryEntry`**
Historical record of a previously assigned doctor.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | User UUID. |
| `doctor_id` | `str` | Business ID (e.g., DOC987654). |
| `name` | `str` | Doctor's full name. |
| `email` | `EmailStr` | Doctor's email. |
| `specialisation` | `str` | Medical specialization. |
| `department` | `str` | Hospital department. |
| `assigned_at` | `datetime` | When the assignment was created. |
| `revoked_at` | `datetime` | When the assignment was revoked. |
| `reason` | `str` | Reason for revocation (optional). |

---

### **`PatientAssignRequest`**
Request format for assigning a patient to a doctor.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patient_email` | `EmailStr` | Yes | Email of the patient to assign. |
| `speciality_required` | `str` | Yes | Medical specialization needed. |

---

### **`RevokeAccessRequest`**
Request format for revoking doctor access.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patient_email` | `EmailStr` | Yes | Email of the patient. |
| `doctor_identifier` | `str` | Admin only | Doctor's email or ID (required for admins). |
| `reason` | `str` | No | Reason for revocation (default: "Discharged"). |

---

### **`Specialities`**
Response model for available doctor specializations.

| Field | Type | Description |
|-------|------|-------------|
| `count` | `int` | Total number of unique specializations. |
| `specialities` | `list[str]` | List of specialization names (sorted alphabetically). |

---

## 5. Assignment Algorithm

### **Load-Balanced Assignment**
When a patient is assigned:

1. **Find Candidates**: Query all doctors with the required specialization.
2. **Calculate Load**: Count active assignments for each doctor.
3. **Filter Available**: Only consider doctors below their `max_patients` limit.
4. **Sort by Load**: Prioritize doctors with the lowest current workload.
5. **Assign**: Create assignment with the doctor having the least patients.
6. **Notify**: Send notification to patient about the assigned doctor.

### **Business Rules**
- A patient cannot have multiple active assignments with the same doctor.
- Revoked assignments do not count toward a doctor's patient load.
- If all specialists are at capacity, the request fails with a 409 error.

---

## 6. Frontend Integration Guide

### **Specialities (Public)**
```typescript
// Fetch all available specializations for dropdown/select inputs
const fetchSpecialities = async () => {
  const response = await api.get('/assignments/specialities');
  // response.specialities is an array of strings
  // Use for populating dropdown menus when assigning patients
  
  // Example: Populate a select element
  const selectElement = document.getElementById('specialty-select');
  response.specialities.forEach(specialty => {
    const option = document.createElement('option');
    option.value = specialty;
    option.text = specialty;
    selectElement.appendChild(option);
  });
};
```

### **Doctor Dashboard**
```typescript
// Fetch assigned patients on page load
const fetchMyPatients = async () => {
  const response = await api.get('/assignments/patient');
  
  // Display response.patients in a table/list
  // Show response.count in header: "My Patients (12)"
  
  // Display historical patients in a separate section:
  // - Show as a collapsible "Previous Patients" section
  // - Include assigned_at and revoked_at dates
  // - Display reason for revocation if available
  // - Sort is already handled by API (most recent first)
};

// Get patient details by email
const getPatientByEmail = async (email: string) => {
  try {
    const patient = await api.get(`/assignments/get-my-patient/${encodeURIComponent(email)}`);
    
    // Display complete patient profile:
    // - Basic info: name, email, date of birth, gender
    // - Contact: phone, address
    // - Medical: blood group, height, weight, allergies, medications
    // - Emergency contact information
    
    return patient;
  } catch (error) {
    if (error.status === 404) {
      // Patient not found or not assigned to this doctor
      showError("Patient not found or not assigned to you");
    }
  }
};

// Example: Search patient by email before creating a case
const searchAndCreateCase = async (patientEmail: string) => {
  const patient = await getPatientByEmail(patientEmail);
  
  if (patient) {
    // Pre-fill case creation form with patient data
    navigateTo(`/cases/create?patient_id=${patient.user_id}`);
  }
};

// Example of rendering patient history
const renderPatientHistory = (history) => {
  return history.map(patient => (
    <HistoryCard>
      <h3>{patient.name} ({patient.patient_id})</h3>
      <p>Email: {patient.email}</p>
      <p>Period: {formatDate(patient.assigned_at)} - {formatDate(patient.revoked_at)}</p>
      {patient.reason && <p>Reason: {patient.reason}</p>}
    </HistoryCard>
  ));
};

// Assign new patient
const assignPatient = async (email: string, specialty: string) => {
  const response = await api.post('/assignments/assign', {
    patient_email: email,
    speciality_required: specialty
  });
  // Show success message with assigned doctor info
  // Refresh patient list
};

// Discharge patient
const dischargePatient = async (patientEmail: string) => {
  await api.post('/assignments/revoke', {
    patient_email: patientEmail,
    reason: "Treatment completed"
  });
  // Refresh patient list
};
```

### **Patient Dashboard**
```typescript
// Fetch assigned doctors
const fetchMyDoctors = async () => {
  const response = await api.get('/assignments/doctors');
  
  // Display current doctors as cards showing:
  // - Doctor name, specialization, department
  // - "View Profile" or "Contact" buttons
  
  // Display historical doctors in a separate section:
  // - Show as a collapsible "Previous Doctors" section
  // - Include assigned_at and revoked_at dates
  // - Display reason for revocation if available
  // - Sort is already handled by API (most recent first)
};

// Example of rendering history
const renderDoctorHistory = (history) => {
  return history.map(doctor => (
    <HistoryCard>
      <h3>{doctor.name} - {doctor.specialisation}</h3>
      <p>Department: {doctor.department}</p>
      <p>Period: {formatDate(doctor.assigned_at)} - {formatDate(doctor.revoked_at)}</p>
      {doctor.reason && <p>Reason: {doctor.reason}</p>}
    </HistoryCard>
  ));
};
```

---

## 7. Common Use Cases

### **New Patient Onboarding**
1. Patient registers and completes profile.
2. System or admin triggers assignment with required specialty.
3. Patient receives notification about assigned doctor.
4. Doctor sees new patient in their dashboard.

### **Doctor at Capacity**
1. Doctor reaches `max_patients` limit.
2. System automatically assigns new patients to other doctors with same specialty.
3. Admin can override by increasing `max_patients` or manually assigning.

### **Patient Transfer**
1. Current doctor revokes access with reason "Transfer".
2. Admin or new doctor assigns patient to new doctor.
3. Both notifications are sent to patient.

### **Discharge**
1. Doctor revokes access with reason "Discharged".
2. Assignment is marked inactive but retained for audit purposes.
3. Patient no longer appears in doctor's patient list.

---

## 8. Security & Access Control

| Role | Get Patients | Get Doctors | Assign | Revoke |
|------|-------------|-------------|---------|--------|
| **Patient** | ❌ | ✅ (own) | ❌ | ❌ |
| **Doctor** | ✅ (own) | ❌ | ✅ | ✅ (own) |
| **Admin** | ❌ | ❌ | ✅ | ✅ (any) |

---

## 9. Notifications Integration

The assignments module triggers notifications for:
- **Patient**: When a new doctor is assigned (`notify_doctor_assigned`).
- **Doctor**: When a new patient is assigned (handled via cases module).

See [notifications.md](notifications.md) for polling and display details.
