# Frontend Guide: Doctor Report Upload with Patient Selection

## Overview
Doctors can now upload medical reports for their assigned patients. Before uploading, the doctor must select which patient the report is for. This guide explains how to implement this feature on the frontend.

---

## User Flow

1. **Doctor navigates to "Upload Report" page**
2. **System fetches available patients** → Display dropdown/selection list
3. **Doctor selects a patient** from the list
4. **Doctor fills report details** (file, description, case, etc.)
5. **Doctor clicks "Upload"**
6. **System validates** patient is assigned to doctor
7. **Upload proceeds** if valid, or shows error if invalid

---

## API Endpoints

### 1. Get Available Patients (NEW)

**Purpose:** Fetch list of patients the doctor can upload reports for.

```http
GET /reports/available-patients
Authorization: Bearer {doctor_jwt_token}
```

**Response (200 OK):**
```json
{
  "total": 3,
  "patients": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "patient_id": "PAT001",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "gender": "male",
      "date_of_birth": "1990-05-15T00:00:00Z"
    },
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "patient_id": "PAT002",
      "name": "Jane Smith",
      "email": "jane.smith@example.com",
      "gender": "female",
      "date_of_birth": "1985-08-22T00:00:00Z"
    }
  ]
}
```

**Response (403 Forbidden) - If patient tries to access:**
```json
{
  "detail": "Only doctors can access this endpoint. Patients can only upload reports for themselves."
}
```

**When to call:**
- On page load of report upload form (for doctors)
- After doctor logs in and navigates to upload section
- On refresh of upload page

---

### 2. Generate Upload URL (Existing - Enhanced)

**Purpose:** Request signed URL for uploading report file to storage.

```http
POST /reports/upload-url
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "filename": "blood_test_results.pdf",
  "content_type": "application/pdf",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "case_id": "CASE20260118ABC123",
  "description": "Quarterly blood test results"
}
```

**Request Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | string | ✅ | Original filename with extension |
| `content_type` | string | ✅ | MIME type (see allowed types below) |
| `patient_id` | string | ✅ | Patient's `user_id` from available-patients response |
| `case_id` | string | ❌ | Optional case to link report to |
| `description` | string | ❌ | Optional description |

**Allowed Content Types:**
- `application/pdf` - PDF documents
- `image/png` - PNG images
- `image/jpeg` - JPEG images
- `image/jpg` - JPG images
- `image/webp` - WebP images

**Response (201 Created):**
```json
{
  "report_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "upload_url": "https://supabase.co/storage/v1/...",
  "storage_path": "patient-uuid/20260123_143022_7c9e6679.pdf",
  "expires_in": 3600
}
```

**Enhanced Error Response (403 Forbidden) - Unassigned Patient:**
```json
{
  "detail": "You do not have access to upload reports for this patient. The patient (ID: xxx) is not assigned to you. Please check your assigned patients using GET /reports/available-patients"
}
```

**Other Errors:**
- `400 Bad Request` - Invalid content type or invalid case_id
- `401 Unauthorized` - Missing/invalid JWT token

---

### 3. Confirm Upload (Existing - No Changes)

After uploading file to the signed URL, confirm the upload:

```http
POST /reports/{report_id}/confirm
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "storage_path": "patient-uuid/20260123_143022_7c9e6679.pdf",
  "file_size_bytes": 2547812
}
```

---

## Implementation Guide

### Step 1: Fetch Available Patients

Call this when the upload form loads (only for doctors):

```typescript
// TypeScript/JavaScript Example
interface AvailablePatient {
  user_id: string;
  patient_id: string;
  name: string;
  email: string;
  gender?: string;
  date_of_birth?: string;
}

interface AvailablePatientsResponse {
  total: number;
  patients: AvailablePatient[];
}

async function fetchAvailablePatients(): Promise<AvailablePatientsResponse> {
  const response = await fetch('/reports/available-patients', {
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    }
  });
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Only doctors can select patients');
    }
    throw new Error('Failed to fetch patients');
  }
  
  return await response.json();
}
```

### Step 2: Display Patient Selection

Show a dropdown/select component with the patients:

```tsx
// React Example
function ReportUploadForm() {
  const [patients, setPatients] = useState<AvailablePatient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const userRole = getCurrentUserRole(); // 'doctor' or 'patient'

  useEffect(() => {
    if (userRole === 'doctor') {
      fetchAvailablePatients()
        .then(data => {
          setPatients(data.patients);
          setLoading(false);
        })
        .catch(error => {
          console.error('Error fetching patients:', error);
          setLoading(false);
        });
    } else {
      // For patients, auto-set to their own user_id
      setSelectedPatientId(getCurrentUserId());
      setLoading(false);
    }
  }, [userRole]);

  return (
    <form onSubmit={handleSubmit}>
      {userRole === 'doctor' && (
        <div className="form-group">
          <label>Select Patient *</label>
          <select
            value={selectedPatientId}
            onChange={(e) => setSelectedPatientId(e.target.value)}
            required
            disabled={loading}
          >
            <option value="">-- Select a patient --</option>
            {patients.map(patient => (
              <option key={patient.user_id} value={patient.user_id}>
                {patient.name} ({patient.patient_id}) - {patient.email}
              </option>
            ))}
          </select>
        </div>
      )}
      
      {/* Other form fields: file input, description, case, etc. */}
    </form>
  );
}
```

### Step 3: Upload Report

Use the selected patient ID when generating upload URL:

```typescript
async function uploadReport(
  file: File,
  patientId: string,
  description?: string,
  caseId?: string
) {
  // Step 1: Get upload URL
  const uploadUrlResponse = await fetch('/reports/upload-url', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      patient_id: patientId,  // Use selected patient's user_id
      case_id: caseId,
      description: description
    })
  });

  if (!uploadUrlResponse.ok) {
    const error = await uploadUrlResponse.json();
    throw new Error(error.detail);
  }

  const { report_id, upload_url, storage_path } = await uploadUrlResponse.json();

  // Step 2: Upload file to signed URL
  const uploadResponse = await fetch(upload_url, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type
    }
  });

  if (!uploadResponse.ok) {
    throw new Error('Failed to upload file to storage');
  }

  // Step 3: Confirm upload
  const confirmResponse = await fetch(`/reports/${report_id}/confirm`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      storage_path: storage_path,
      file_size_bytes: file.size
    })
  });

  if (!confirmResponse.ok) {
    throw new Error('Failed to confirm upload');
  }

  return await confirmResponse.json();
}
```

---

## UI/UX Recommendations

### For Doctors:

1. **Patient Selection Field**
   - Make it the **first field** in the form
   - Use a **searchable dropdown** if there are many patients
   - Display: `Name (Patient ID) - Email` for clarity
   - Show validation error if not selected

2. **Empty State**
   - If doctor has no assigned patients:
   ```
   No patients assigned to you yet.
   Contact administration to get patient assignments.
   ```

3. **Error Handling**
   - If upload fails with "not assigned" error:
   ```
   ⚠️ This patient is no longer assigned to you.
   Please refresh the patient list and select a valid patient.
   [Refresh Patient List Button]
   ```

4. **Loading State**
   - Show spinner while fetching patients
   - Disable submit button until patients are loaded

### For Patients:

1. **No Patient Selection Needed**
   - Hide the patient selection field completely
   - Automatically use their own `user_id` as `patient_id`

2. **Simplified Form**
   - Show: File upload, Description, Case selection (if applicable)

---

## Complete Form Example (React + TypeScript)

```tsx
import React, { useState, useEffect } from 'react';

interface AvailablePatient {
  user_id: string;
  patient_id: string;
  name: string;
  email: string;
}

export default function ReportUploadPage() {
  const [patients, setPatients] = useState<AvailablePatient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [caseId, setCaseId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const userRole = getCurrentUserRole();
  const currentUserId = getCurrentUserId();

  useEffect(() => {
    if (userRole === 'doctor') {
      loadPatients();
    } else {
      setSelectedPatientId(currentUserId);
    }
  }, []);

  async function loadPatients() {
    try {
      const response = await fetch('/reports/available-patients', {
        headers: { 'Authorization': `Bearer ${getAuthToken()}` }
      });
      
      if (!response.ok) throw new Error('Failed to load patients');
      
      const data = await response.json();
      setPatients(data.patients);
    } catch (err) {
      setError('Failed to load patients. Please try again.');
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (!file) throw new Error('Please select a file');
      if (!selectedPatientId) throw new Error('Please select a patient');

      // Generate upload URL
      const urlResponse = await fetch('/reports/upload-url', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type,
          patient_id: selectedPatientId,
          case_id: caseId || null,
          description: description || null
        })
      });

      if (!urlResponse.ok) {
        const errorData = await urlResponse.json();
        throw new Error(errorData.detail);
      }

      const { report_id, upload_url, storage_path } = await urlResponse.json();

      // Upload file
      const uploadResponse = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type }
      });

      if (!uploadResponse.ok) throw new Error('File upload failed');

      // Confirm upload
      const confirmResponse = await fetch(`/reports/${report_id}/confirm`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          storage_path,
          file_size_bytes: file.size
        })
      });

      if (!confirmResponse.ok) throw new Error('Failed to confirm upload');

      // Success!
      alert('Report uploaded successfully!');
      // Redirect or reset form
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="upload-form">
      <h1>Upload Medical Report</h1>
      
      {error && <div className="error-message">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        {/* Patient Selection (Doctors Only) */}
        {userRole === 'doctor' && (
          <div className="form-group">
            <label>Select Patient *</label>
            <select
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              required
            >
              <option value="">-- Choose a patient --</option>
              {patients.map(patient => (
                <option key={patient.user_id} value={patient.user_id}>
                  {patient.name} ({patient.patient_id}) - {patient.email}
                </option>
              ))}
            </select>
            {patients.length === 0 && (
              <p className="help-text">No patients assigned to you.</p>
            )}
          </div>
        )}

        {/* File Upload */}
        <div className="form-group">
          <label>Report File *</label>
          <input
            type="file"
            accept=".pdf,image/png,image/jpeg,image/jpg,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
        </div>

        {/* Description */}
        <div className="form-group">
          <label>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description of the report..."
          />
        </div>

        {/* Case ID (Optional) */}
        <div className="form-group">
          <label>Link to Case (Optional)</label>
          <input
            type="text"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="CASE20260118ABC123"
          />
        </div>

        {/* Submit */}
        <button type="submit" disabled={loading}>
          {loading ? 'Uploading...' : 'Upload Report'}
        </button>
      </form>
    </div>
  );
}
```

---

## Testing Checklist

### Doctor User:
- [ ] Can see list of assigned patients on form load
- [ ] Patient dropdown is required and shows validation
- [ ] Can successfully upload report for assigned patient
- [ ] Gets clear error when trying to upload for unassigned patient
- [ ] Can refresh patient list if assignment changes

### Patient User:
- [ ] Does NOT see patient selection dropdown
- [ ] Can upload their own reports without selecting patient
- [ ] Gets 403 error if trying to access `/available-patients`

### Edge Cases:
- [ ] Doctor with no patients sees appropriate message
- [ ] Error handling when patient list fails to load
- [ ] File type validation works correctly
- [ ] Large file upload progress indicator
- [ ] Network error handling during 3-step upload process

---

## API Base URL

Remember to configure your API base URL:
```typescript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

---

## Questions or Issues?

If you encounter any problems implementing this feature, check:
1. JWT token is being sent correctly in Authorization header
2. User role is correctly identified (doctor vs patient)
3. patient_id field uses the `user_id` from available-patients response, not `patient_id`
4. Content-Type headers are set correctly for each request

**Backend API Documentation:** See `/docs/reports.md` for full API reference.
