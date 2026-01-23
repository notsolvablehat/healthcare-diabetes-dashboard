# Reports Module Documentation

## Overview
The reports module manages medical document uploads, storage, and retrieval using Supabase Storage. It implements a secure two-step upload process with signed URLs, supports automatic AI-powered data extraction, and maintains access control between patients and their assigned doctors. The module handles both PDF documents and medical images (PNG, JPEG, WebP).

---

## 1. Core Concepts

### **Two-Step Upload Process**
1. **Request Upload URL**: Generate a signed URL for direct upload to Supabase Storage.
2. **Confirm Upload**: After file upload completes, confirm the operation and trigger AI extraction.

### **File Types Supported**
- **PDF**: Medical reports, lab results, prescriptions (`application/pdf`)
- **Images**: X-rays, scans, photos (`image/png`, `image/jpeg`, `image/jpg`, `image/webp`)

### **Access Control**
- **Patients**: Can upload and view their own reports.
- **Doctors**: Can upload and view reports for their assigned patients.
- **Admins**: Full access to all reports.

### **AI Integration**
- Upon confirmation, reports are automatically analyzed in the background.
- Extracted medical data (test results, diagnoses, medications) is stored in MongoDB.
- Analysis results are linked via `mongo_analysis_id`.

---

## 2. Database Schema (PostgreSQL)

### **`Report` (SQLAlchemy)**
Table: `reports`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Primary key (UUID). |
| `case_id` | `String` | Foreign key to `cases.case_id` (optional - can be null). |
| `patient_id` | `String` | Foreign key to `users.id` (Patient). |
| `uploaded_by` | `String` | Foreign key to `users.id` (Uploader). |
| `file_name` | `String` | Original filename. |
| `file_type` | `String` | File category: `pdf` or `image`. |
| `content_type` | `String` | MIME type (e.g., `application/pdf`). |
| `storage_path` | `String` | Path in Supabase Storage bucket. |
| `file_size_bytes` | `Integer` | File size in bytes (optional). |
| `description` | `Text` | User-provided description (optional). |
| `mongo_analysis_id` | `String` | Reference to AI analysis in MongoDB (optional). |
| `created_at` | `DateTime` | Timestamp of upload. |

**Indexes:**
- `case_id` - Fast lookup by case
- `patient_id` - Fast lookup by patient

---

## 3. API Endpoints

### **Get All My Reports**
Get all reports for the authenticated user (patients see their own, doctors see all assigned patients' reports).

- **Endpoint**: `GET /reports`
- **Auth**: Required (Patient or Doctor)
- **Response (Patient View)**:
```json
{
  "total": 3,
  "reports": [
    {
      "id": "report-uuid-1",
      "case_id": "CASE20260118ABC123",
      "patient_id": "patient-uuid-123",
      "patient_name": "John Doe",
      "uploaded_by": "patient-uuid-123",
      "file_name": "lab_results_jan2026.pdf",
      "file_type": "pdf",
      "content_type": "application/pdf",
      "storage_path": "patient-uuid-123/20260121_143022_report1.pdf",
      "file_size_bytes": 2547812,
      "description": "Blood test results",
      "created_at": "2026-01-21T14:30:22Z"
    }
  ]
}
```

**Response (Doctor View)**:
```json
{
  "total": 15,
  "reports": [
    {
      "id": "report-uuid-1",
      "case_id": "CASE20260118XYZ456",
      "patient_id": "patient-uuid-456",
      "patient_name": "Jane Smith",
      "uploaded_by": "patient-uuid-456",
      "file_name": "xray_chest.png",
      "file_type": "image",
      "content_type": "image/png",
      "storage_path": "patient-uuid-456/20260120_100000_report2.png",
      "file_size_bytes": 1234567,
      "description": "Chest X-ray",
      "created_at": "2026-01-20T10:00:00Z"
    },
    {
      "id": "report-uuid-2",
      "case_id": null,
      "patient_id": "patient-uuid-789",
      "patient_name": "Robert Johnson",
      "uploaded_by": "doctor-uuid-123",
      "file_name": "prescription.pdf",
      "file_type": "pdf",
      "content_type": "application/pdf",
      "storage_path": "patient-uuid-789/20260119_153000_report3.pdf",
      "file_size_bytes": 456789,
      "description": "Monthly prescription",
      "created_at": "2026-01-19T15:30:00Z"
    }
  ]
}
```

**Response Fields:**
- `patient_name`: Patient's full name - included for easy identification (especially useful for doctors viewing multiple patients' reports)
- Reports are sorted by creation date (most recent first)

**Benefits:**
- Single API call for all reports
- No need for N+1 queries to fetch patient names
- Ready for frontend filtering/searching by patient name

---

### **Generate Upload URL**
Request a signed URL for uploading a report directly to Supabase Storage.

- **Endpoint**: `POST /reports/upload-url`
- **Auth**: Required (Patient or Doctor)
- **Request Body**:
```json
{
  "filename": "lab_results_2026.pdf",
  "content_type": "application/pdf",
  "patient_id": "patient-uuid-123",
  "case_id": "CASE20260118ABC123",
  "description": "Blood test results from annual checkup"
}
```

**Request Fields:**
- `filename`: Original filename with extension (required)
- `content_type`: MIME type (required) - must be one of allowed types
- `patient_id`: Patient UUID (required)
- `case_id`: Case to link report to (optional)
- `description`: Brief description of the report (optional)

**Response (Success)**:
```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "upload_url": "https://supabase-storage.example.com/signed-upload-url...",
  "storage_path": "patient-uuid-123/20260121_143022_550e8400.pdf",
  "expires_in": 3600
}
```

**Usage Flow:**
1. Call this endpoint to get a signed URL
2. Upload the file directly to the `upload_url` using PUT/POST
3. Call the confirmation endpoint with the `report_id`

**Error Cases:**
- `403`: User doesn't have access to upload for this patient
- `400`: Invalid content type or invalid case_id

---

### **Confirm Upload**
Confirm that file upload was successful and trigger AI analysis.

- **Endpoint**: `POST /reports/{report_id}/confirm`
- **Auth**: Required (Must be the uploader)
- **Request Body**:
```json
{
  "storage_path": "patient-uuid-123/20260121_143022_550e8400.pdf",
  "file_size_bytes": 2547812
}
```

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "case_id": "CASE20260118ABC123",
  "patient_id": "patient-uuid-123",
  "uploaded_by": "doctor-uuid-456",
  "file_name": "lab_results_2026.pdf",
  "file_type": "pdf",
  "content_type": "application/pdf",
  "storage_path": "patient-uuid-123/20260121_143022_550e8400.pdf",
  "file_size_bytes": 2547812,
  "description": "Blood test results from annual checkup",
  "created_at": "2026-01-21T14:30:22Z"
}
```

**Side Effects:**
- Triggers background AI extraction job
- Sends notifications to all doctors assigned to the patient
- Updates file size in database

**Error Cases:**
- `404`: Report not found or user not authorized to confirm

---

### **Get Reports by Case**
List all reports attached to a specific case.

- **Endpoint**: `GET /reports/case/{case_id}`
- **Auth**: Required (Patient or assigned Doctor)
- **Response**:
```json
{
  "total": 3,
  "reports": [
    {
      "id": "report-uuid-1",
      "case_id": "CASE20260118ABC123",
      "patient_id": "patient-uuid-123",
      "uploaded_by": "patient-uuid-123",
      "file_name": "xray_chest.png",
      "file_type": "image",
      "content_type": "image/png",
      "storage_path": "patient-uuid-123/20260121_100000_report1.png",
      "file_size_bytes": 1234567,
      "description": "Chest X-ray",
      "created_at": "2026-01-21T10:00:00Z"
    }
  ]
}
```

---

### **Get Reports by Patient**
List all reports for a specific patient.

- **Endpoint**: `GET /reports/patient/{patient_id}`
- **Auth**: Required (Patient themselves or assigned Doctor)
- **Response**:
```json
{
  "total": 15,
  "reports": [
    {
      "id": "report-uuid-1",
      "case_id": null,
      "patient_id": "patient-uuid-123",
      "uploaded_by": "patient-uuid-123",
      "file_name": "prescription_jan2026.pdf",
      "file_type": "pdf",
      "content_type": "application/pdf",
      "storage_path": "patient-uuid-123/20260110_120000_report2.pdf",
      "file_size_bytes": 98765,
      "description": "Monthly prescription refill",
      "created_at": "2026-01-10T12:00:00Z"
    }
  ]
}
```

---

### **Get Single Report**
Retrieve metadata for a specific report.

- **Endpoint**: `GET /reports/{report_id}`
- **Auth**: Required (Patient or assigned Doctor)
- **Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "case_id": "CASE20260118ABC123",
  "patient_id": "patient-uuid-123",
  "uploaded_by": "doctor-uuid-456",
  "file_name": "lab_results_2026.pdf",
  "file_type": "pdf",
  "content_type": "application/pdf",
  "storage_path": "patient-uuid-123/20260121_143022_550e8400.pdf",
  "file_size_bytes": 2547812,
  "description": "Blood test results",
  "created_at": "2026-01-21T14:30:22Z"
}
```

**Error Cases:**
- `404`: Report not found or user not authorized

---

### **Get Download URL**
Generate a signed download URL for a report.

- **Endpoint**: `GET /reports/{report_id}/download`
- **Auth**: Required (Patient or assigned Doctor)
- **Response**:
```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "download_url": "https://supabase-storage.example.com/signed-download-url...",
  "expires_in": 3600
}
```

**Usage:**
- Use the `download_url` to fetch the actual file
- URL expires after 1 hour (3600 seconds)
- For direct browser download, you can redirect to this URL
- Download events are automatically logged to activity history

**Error Cases:**
- `404`: Report not found or user not authorized

---

### **Get Report Activity**
Get complete activity history for a report including all interactions and operations.

- **Endpoint**: `GET /reports/{report_id}/activity`
- **Auth**: Required (Patient or assigned Doctor)
- **Response**:
```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_id": "patient-uuid-123",
  "total_activities": 8,
  "upload_count": 1,
  "analysis_count": 1,
  "extraction_count": 2,
  "explanation_count": 3,
  "download_count": 1,
  "activities": [
    {
      "activity_type": "download",
      "user_id": "doctor-uuid-456",
      "user_role": "doctor",
      "status": "completed",
      "timestamp": "2026-01-22T11:00:00Z",
      "metadata": null,
      "error_message": null
    },
    {
      "activity_type": "explanation_request",
      "user_id": "patient-uuid-123",
      "user_role": "patient",
      "status": "completed",
      "timestamp": "2026-01-22T10:45:00Z",
      "metadata": {
        "selected_text": "HbA1c: 5.2%",
        "question": "What does this value mean?"
      },
      "error_message": null
    },
    {
      "activity_type": "extraction",
      "user_id": "doctor-uuid-456",
      "user_role": "doctor",
      "status": "completed",
      "timestamp": "2026-01-22T10:30:00Z",
      "metadata": {
        "report_type": "Lab Report",
        "lab_results_count": 8,
        "medications_count": 2,
        "diagnoses_count": 1,
        "processing_time_ms": 3542
      },
      "error_message": null
    },
    {
      "activity_type": "extraction",
      "user_id": "system",
      "user_role": "system",
      "status": "completed",
      "timestamp": "2026-01-21T14:31:00Z",
      "metadata": {
        "report_type": "Lab Report",
        "lab_results_count": 8,
        "medications_count": 2,
        "diagnoses_count": 1,
        "processing_time_ms": 4120,
        "triggered_by": "upload_confirmation"
      },
      "error_message": null
    },
    {
      "activity_type": "analysis",
      "user_id": "doctor-uuid-456",
      "user_role": "doctor",
      "status": "completed",
      "timestamp": "2026-01-21T15:00:00Z",
      "metadata": {
        "prediction_label": "no_diabetes",
        "confidence": 0.93,
        "HbA1c_level": 5.2,
        "blood_glucose_level": 95,
        "bmi": 24.5
      },
      "error_message": null
    },
    {
      "activity_type": "upload",
      "user_id": "patient-uuid-123",
      "user_role": "patient",
      "status": "completed",
      "timestamp": "2026-01-21T14:30:22Z",
      "metadata": {
        "file_name": "lab_results_jan2026.pdf",
        "file_size_bytes": 2547812,
        "content_type": "application/pdf"
      },
      "error_message": null
    }
  ]
}
```

**Activity Types:**
- `upload`: Report file was uploaded (logged on confirmation)
- `analysis`: AI diabetes analysis was performed (legacy endpoint)
- `extraction`: Report data extraction was performed (medical data extraction)
- `explanation_request`: User requested AI explanation for selected text
- `download`: Report file was downloaded

**Status Values:**
- `completed`: Operation finished successfully
- `failed`: Operation encountered an error
- `in_progress`: Operation is currently running (rare)

**Use Cases:**
- Track who has accessed a report
- Debug failed extraction/analysis attempts
- Audit trail for compliance
- Monitor system usage patterns
- Identify frequently analyzed reports

**Error Cases:**
- `404`: Report not found or user not authorized

---

### **Request Explanation (Log Activity)**
Log when a user highlights text from a report and requests an explanation.

- **Endpoint**: `POST /reports/{report_id}/explain`
- **Auth**: Required (Patient or assigned Doctor)
- **Request Body**:
```json
{
  "selected_text": "HbA1c: 5.2%",
  "question": "What does this value mean?"
}
```

**Request Fields:**
- `selected_text`: The text highlighted by the user (1-500 characters)
- `question`: Optional specific question about the selected text (max 200 characters)

**Response**:
```json
{
  "status": "logged",
  "message": "Explanation request logged successfully"
}
```

**Use Cases:**
- Track user engagement with reports
- Identify confusing medical terminology
- Analyze which parts of reports need clarification
- Integrate with /ai/ask or chat endpoints for AI-powered explanations

**Note:** This endpoint only logs the request. For AI-generated explanations, use `/ai/ask` or the chat system endpoints.

**Error Cases:**
- `403`: Not authorized to access this report
- `404`: Report not found

---

## 4. Data Models (Pydantic)

### **`UploadUrlRequest`**
Request to generate a signed upload URL.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | `str` | Yes | Original filename with extension. |
| `content_type` | `str` | Yes | MIME type (must be allowed type). |
| `patient_id` | `str` | Yes | Patient the report belongs to. |
| `case_id` | `str` | No | Optional case to link report to. |
| `description` | `str` | No | Brief description of the report. |

**Allowed Content Types:**
- `application/pdf`
- `image/png`
- `image/jpeg`
- `image/jpg`
- `image/webp`

---

### **`UploadUrlResponse`**
Response containing signed upload URL.

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | `str` | Generated UUID for the report. |
| `upload_url` | `str` | Signed URL for direct upload to Supabase. |
| `storage_path` | `str` | Storage path (pass to confirm endpoint). |
| `expires_in` | `int` | URL validity in seconds (default: 3600). |

---

### **`ReportResponse`**
Report metadata response.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Report UUID. |
| `case_id` | `str \| None` | Case UUID if linked. |
| `patient_id` | `str` | Patient UUID. |
| `patient_name` | `str \| None` | Patient name (included for doctors). |
| `uploaded_by` | `str` | Uploader's user ID. |
| `file_name` | `str` | Original filename. |
| `file_type` | `FileType` | `pdf` or `image`. |
| `content_type` | `str` | MIME type. |
| `storage_path` | `str` | Path in storage bucket. |
| `file_size_bytes` | `int \| None` | File size in bytes. |
| `description` | `str \| None` | User description. |
| `created_at` | `datetime` | Upload timestamp. |

---

### **`ActivityEvent`**
Single activity event for a report.

| Field | Type | Description |
|-------|------|-------------|
| `activity_type` | `str` | Type: `upload`, `analysis`, `extraction`, `explanation_request`, `download`. |
| `user_id` | `str` | User who performed the activity. |
| `user_role` | `str` | Role: `patient`, `doctor`, `system`. |
| `status` | `str` | Status: `completed`, `failed`, `in_progress`. |
| `timestamp` | `datetime` | When the activity occurred. |
| `metadata` | `dict \| None` | Additional activity-specific data. |
| `error_message` | `str \| None` | Error message if failed. |

---

### **`ReportActivityResponse`**
Response for report activity history.

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | `str` | Report UUID. |
| `patient_id` | `str` | Patient UUID. |
| `total_activities` | `int` | Total number of activities. |
| `activities` | `list[ActivityEvent]` | Activities sorted by timestamp (newest first). |
| `upload_count` | `int` | Number of upload events. |
| `analysis_count` | `int` | Number of analysis attempts. |
| `extraction_count` | `int` | Number of extraction attempts. |
| `explanation_count` | `int` | Number of explanation requests. |
| `download_count` | `int` | Number of download events. |

---

### **`ExplanationRequest`**
Request for logging when user requests explanation of selected text.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `selected_text` | `str` | Yes | Text selected from the report (1-500 characters). |
| `question` | `str` | No | Optional specific question about the text (max 200 chars). |

---

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | `str` | Generated report ID (use for confirmation). |
| `upload_url` | `str` | Signed URL for direct upload to Supabase. |
| `storage_path` | `str` | Path where file will be stored. |
| `expires_in` | `int` | URL expiry time in seconds (default: 3600). |

---

### **`ReportConfirmRequest`**
Request to confirm upload and save metadata.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `storage_path` | `str` | Yes | Path returned from upload-url endpoint. |
| `file_size_bytes` | `int` | No | Size of uploaded file in bytes. |

---

### **`ReportResponse`**
Report metadata response.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Report UUID. |
| `case_id` | `str` | Linked case ID (nullable). |
| `patient_id` | `str` | Patient UUID. |
| `patient_name` | `str` | Patient's full name (nullable). |
| `uploaded_by` | `str` | Uploader UUID. |
| `file_name` | `str` | Original filename. |
| `file_type` | `FileType` | `pdf` or `image`. |
| `content_type` | `str` | MIME type. |
| `storage_path` | `str` | Path in storage bucket. |
| `file_size_bytes` | `int` | File size in bytes (nullable). |
| `description` | `str` | User description (nullable). |
| `created_at` | `datetime` | Upload timestamp. |
| `file_type` | `FileType` | `pdf` or `image`. |
| `content_type` | `str` | MIME type. |
| `storage_path` | `str` | Path in storage bucket. |
| `file_size_bytes` | `int` | File size in bytes (nullable). |
| `description` | `str` | User description (nullable). |
| `created_at` | `datetime` | Upload timestamp. |

---

### **`DownloadUrlResponse`**
Response containing signed download URL.

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | `str` | Report UUID. |
| `download_url` | `str` | Signed URL for downloading. |
| `expires_in` | `int` | URL expiry time in seconds (default: 3600). |

---

### **`ReportListResponse`**
Response for listing reports.

| Field | Type | Description |
|-------|------|-------------|
| `total` | `int` | Total number of reports. |
| `reports` | `list[ReportResponse]` | Array of report objects. |

---

## 5. Upload Flow Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 1. POST /reports/upload-url
       ▼
┌──────────────────────┐
│   Backend API        │
│  - Validate access   │
│  - Create DB record  │
│  - Generate signed   │
│    URL from Supabase │
└──────┬───────────────┘
       │
       │ 2. Return: report_id, upload_url
       ▼
┌─────────────┐
│   Client    │
│  - Upload    │
│    file to   │
│    signed URL│
└──────┬──────┘
       │
       │ 3. POST /reports/{report_id}/confirm
       ▼
┌──────────────────────┐
│   Backend API        │
│  - Update DB         │
│  - Trigger AI job    │
│  - Send              │
│    notifications     │
└──────────────────────┘
```

---

## 6. Frontend Integration Guide

### **Patient Upload Flow**
```typescript
// Step 1: Request upload URL
const uploadReport = async (file: File, patientId: string, caseId?: string) => {
  // Request signed URL
  const urlResponse = await api.post('/reports/upload-url', {
    filename: file.name,
    content_type: file.type,
    patient_id: patientId,
    case_id: caseId,
    description: "User provided description"
  });

  const { report_id, upload_url, storage_path } = urlResponse;

  // Step 2: Upload file directly to Supabase
  const uploadResponse = await fetch(upload_url, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type,
    },
  });

  if (!uploadResponse.ok) {
    throw new Error('File upload failed');
  }

  // Step 3: Confirm upload
  const confirmResponse = await api.post(`/reports/${report_id}/confirm`, {
    storage_path: storage_path,
    file_size_bytes: file.size
  });

  return confirmResponse;
};
```

### **Viewing Reports**
```typescript
// Get all reports for current user (patient or doctor)
const fetchMyReports = async () => {
  const response = await api.get('/reports');
  
  // For patients: response.reports contains their own reports
  // For doctors: response.reports contains all assigned patients' reports
  
  // Each report includes patient_name for easy identification
  return response.reports;
};

// Example: Group reports by patient (useful for doctors)
const groupReportsByPatient = (reports) => {
  const grouped = {};
  
  reports.forEach(report => {
    const patientName = report.patient_name || 'Unknown';
    if (!grouped[patientName]) {
      grouped[patientName] = [];
    }
    grouped[patientName].push(report);
  });
  
  return grouped;
};

// Get activity history for a specific report
const fetchReportActivity = async (reportId: string) => {
  const response = await api.get(`/reports/${reportId}/activity`);
  
  return {
    activities: response.activities,
    summary: {
      uploads: response.upload_count,
      analyses: response.analysis_count,
      extractions: response.extraction_count,
      explanations: response.explanation_count,
      downloads: response.download_count
    }
  };
};

// Example: Display activity timeline
const renderActivityTimeline = (activities) => {
  return activities.map(activity => {
    const icon = getActivityIcon(activity.activity_type);
    const color = activity.status === 'failed' ? 'red' : 'green';
    
    return (
      <TimelineItem key={activity.timestamp}>
        <Icon name={icon} color={color} />
        <div>
          <strong>{activity.activity_type}</strong>
          <span>{activity.user_role}</span>
          <time>{formatDate(activity.timestamp)}</time>
          {activity.error_message && (
            <ErrorMessage>{activity.error_message}</ErrorMessage>
          )}
        </div>
      </TimelineItem>
    );
  });
};

const getActivityIcon = (type: string) => {
  const icons = {
    upload: 'upload',
    analysis: 'brain',
    extraction: 'file-text',
    explanation_request: 'help-circle',
    download: 'download'
  };
  return icons[type] || 'activity';
};
```

### **Downloading Reports**// Example: Display reports with patient names
const ReportsListComponent = ({ reports }) => {
  return (
    <div>
      {reports.map(report => (
        <ReportCard key={report.id}>
          <div>
            <h3>{report.file_name}</h3>
            <p>Patient: {report.patient_name}</p>
            <p>Uploaded: {formatDate(report.created_at)}</p>
            <p>{report.description}</p>
          </div>
          <button onClick={() => downloadReport(report.id)}>
            Download
          </button>
        </ReportCard>
      ))}
    </div>
  );
};

// Fetch reports for a case
const fetchCaseReports = async (caseId: string) => {
  const response = await api.get(`/reports/case/${caseId}`);
  return response.reports;
};

// Fetch all patient reports
const fetchPatientReports = async (patientId: string) => {
  const response = await api.get(`/reports/patient/${patientId}`);
  return response.reports;
};

// Download a report
const downloadReport = async (reportId: string, filename: string) => {
  const response = await api.get(`/reports/${reportId}/download`);
  
  // Open in new tab or trigger download
  window.open(response.download_url, '_blank');
  
  // Or use fetch to download
  const fileResponse = await fetch(response.download_url);
  const blob = await fileResponse.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
};
```

### **Display Report List**
```typescript
const ReportsList = ({ reports }) => {
  return (
    <div>
      {reports.map(report => (
        <ReportCard key={report.id}>
          <div className="report-icon">
            {report.file_type === 'pdf' ? <PdfIcon /> : <ImageIcon />}
          </div>
          <div className="report-details">
            <h3>{report.file_name}</h3>
            <p>{report.description}</p>
            <p>Uploaded: {formatDate(report.created_at)}</p>
            <p>Size: {formatFileSize(report.file_size_bytes)}</p>
          </div>
          <button onClick={() => downloadReport(report.id, report.file_name)}>
            Download
          </button>
        </ReportCard>
      ))}
    </div>
  );
};
```

---

## 7. Common Use Cases

### **Patient Self-Upload**
1. Patient visits their dashboard or case details page
2. Clicks "Upload Report" button
3. Selects file and optionally links to a case
4. File is uploaded directly to Supabase Storage
5. Assigned doctors receive notification about new report

### **Doctor Upload for Patient**
1. Doctor viewing patient's profile or case
2. Uploads lab results or diagnostic images on patient's behalf
3. Links report to specific case
4. Patient receives notification about new report

### **Viewing Medical History**
1. Doctor reviews all reports for a patient
2. Filters by case or views all reports
3. Downloads reports to local system for review
4. AI-extracted data is displayed alongside reports

### **Case Documentation**
1. Multiple reports linked to same case
2. Organized chronologically
3. Each report shows uploader, date, and description
4. Complete medical documentation for case

---

## 8. Security & Access Control

| Role | Upload (Self) | Upload (Others) | View (Self) | View (Others) | Download |
|------|---------------|-----------------|-------------|---------------|----------|
| **Patient** | ✅ | ❌ | ✅ | ❌ | ✅ (own) |
| **Doctor** | ✅ | ✅ (assigned) | ✅ | ✅ (assigned) | ✅ (assigned) |
| **Admin** | ✅ | ✅ (all) | ✅ | ✅ (all) | ✅ (all) |

**Access Validation:**
- Patients can only upload/view their own reports
- Doctors can only access reports for patients they're assigned to
- All downloads use signed URLs with 1-hour expiration
- Direct storage access is blocked - all access must go through API

---

## 9. Storage Configuration

### **Bucket Information**
- **Bucket Name**: `medical-reports`
- **Storage Provider**: Supabase Storage
- **URL Expiration**: 3600 seconds (1 hour)
- **File Organization**: `{patient_id}/{timestamp}_{report_id}.{extension}`

### **File Size Limits**
- Configured in Supabase Storage settings
- Recommended: 10MB for images, 50MB for PDFs
- Validation should happen on frontend before upload request

---

## 10. AI Integration

### **Automatic Extraction**
When a report is confirmed:
1. Background task is triggered immediately
2. File is downloaded from Supabase Storage
3. AI service extracts medical data:
   - Test results and values
   - Diagnoses and conditions
   - Medications mentioned
   - Key medical terms
4. Extracted data stored in MongoDB
5. `mongo_analysis_id` field updated in PostgreSQL

### **Analysis Results**
- Access via AI module endpoints (see AI documentation)
- Structured JSON format stored in MongoDB
- Linked to report via `mongo_analysis_id`
- Can be used to auto-populate case fields

---

## 11. Notifications Integration

The reports module triggers notifications for:
- **Doctors**: When a patient uploads a new report (`notify_new_report_uploaded`)
- **Patients**: Notification sent when AI analysis completes (handled by AI module)

See [notifications.md](NOTIFICATIONS.md) for details.

---

## 12. Error Handling

### **Common Errors**

| Error | Status Code | Cause | Solution |
|-------|-------------|-------|----------|
| Invalid content type | 400 | Unsupported file type | Use allowed MIME types only |
| Invalid case_id | 400 | Case doesn't exist | Verify case exists or omit field |
| Permission denied | 403 | No access to patient | Check patient assignment |
| Report not found | 404 | Invalid report_id | Verify report ID |
| Upload URL expired | 400 | URL older than 1 hour | Request new upload URL |

### **Best Practices**
- Always handle upload failures gracefully
- Store `report_id` immediately after getting upload URL
- Implement retry logic for confirmation step
- Show progress indicators during upload
- Validate file type and size on frontend before upload
