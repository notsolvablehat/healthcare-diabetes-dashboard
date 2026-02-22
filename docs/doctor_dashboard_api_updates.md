# Doctor Dashboard API Updates (Frontend Guide)

The backend `/doctor/dashboard` API endpoint has been updated to dynamically provide specialty-specific metrics and a list of recently assigned patients with their corresponding names and statuses.

## Endpoint Overview

**`GET /doctor/dashboard`**

Returns the aggregated data necessary to render the Doctor Dashboard, tailored automatically to the authenticated doctor's registered specialty (e.g. Cardiology, Pediatrics, General Medicine).

---

## 1. What the API Asks For (Request)

The request parameters remain **unchanged**. You only need to provide authentication headers (the JWT token) and optional pagination queries for the cases list.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cases_page` | `integer` | `1` | The page number for the `cases` list pagination. |
| `cases_limit` | `integer` | `10` | The number of cases to return per page (max: 50). |

*Note: The frontend does NOT need to send the doctor's specialty. The backend automatically identifies the doctor's specialty via the authentication token.*

---

## 2. What the API Returns (Response)

The `DoctorDashboardResponse` has been expanded. Here are the **newly added fields**:

1. **`specialty_metrics`**: A list of 4 metric objects tailored to the doctor's specialty. You no longer need to map these manually on the frontend.
2. **`recent_patients`**: A list of the 5 most recent patients associated with the doctor's cases. It includes the patient's name directly, so you don't have to fetch it separately.

### Full Response Schema Example

```json
{
  "user_info": {
    "user_id": "doc-1234-uuid",
    "name": "Dr. Sharma",
    "email": "dr.sharma@hospital.com",
    "specialisation": "Cardiology"
  },
  "patient_stats": {
    "active": 24,
    "max": 50,
    "load_percentage": 48.0
  },
  "cases": {
    "open": 8,
    "under_review": 3,
    "closed": 13,
    "approved": 2,
    "total": 24,
    "items": [...],      // Paginated items
    "pagination": {...}
  },
  "pending_approvals": [
    {
      "case_id": "case-xyz",
      "patient_name": "Priya Sharma",
      "patient_id": "pat-456",
      "chief_complaint": "Hypertension follow-up, BP 145/92",
      "created_at": "2026-02-22T10:30:00Z"
    }
  ],
  // 🌟 NEW: Specialty metrics automatically mapped based on user_info.specialisation
  "specialty_metrics": [
    { 
      "value": "52%", 
      "label": "Avg EF", 
      "sub": "↑ 3% this Q", 
      "cls": "up" 
    },
    { 
      "value": "88%", 
      "label": "Statin Compliance", 
      "sub": "↑ 5%", 
      "cls": "up" 
    },
    { 
      "value": "128/78", 
      "label": "Avg BP", 
      "sub": "well controlled", 
      "cls": "up" 
    },
    { 
      "value": "0.8", 
      "label": "Avg Troponin", 
      "sub": "2 elevated", 
      "cls": "down" 
    }
  ],
  // 🌟 NEW: The 5 most recent patients from cases to populate the table directly
  "recent_patients": [
    {
      "case_id": "case-abc",
      "status": "open",
      "chief_complaint": "Uncontrolled diabetes, HbA1c 9.2%",
      "patient_name": "Rajesh Kumar",
      "patient_id": "pat-123",
      "created_at": "2026-02-22T09:00:00Z"
    }
  ],
  "alerts": [...],
  "ai_stats": {
    "chat_count": 45,
    "analyses_count": 12
  },
  "notifications_unread": 2
}
```

---

## 3. Frontend Implementation Guide

Because the backend now handles the logic for grouping metrics and joining patient names, you can simplify the frontend components significantly:

### Rendering Specialty Metrics
You no longer need a `<select>` dropdown menu or a hardcoded dictionary mapping strings like `'cardiology'` to metrics. Just iterate over the `specialty_metrics` array:

```tsx
// React Example 
const SpecialtyMetricsGrid = ({ metrics }) => (
  <div className="spec-metrics-grid">
    {metrics.map((metric, idx) => (
      <div key={idx} className="spec-metric">
        <div className="spec-metric-value">{metric.value}</div>
        <div className="spec-metric-label">{metric.label}</div>
        <div className={`spec-metric-sub ${metric.cls}`}>
          {metric.sub}
        </div>
      </div>
    ))}
  </div>
);
```

### Rendering Recent Patients
Previously, the `cases` list didn't include the patient string name easily accessible without extra fetches. You can now use `recent_patients` directly:

```tsx
// React Example
const RecentPatientsTable = ({ patients }) => (
  <table className="data-table">
    <thead>
      <tr>
        <th>Patient</th>
        <th>Condition</th>
        <th>Status</th>
        <th>Time</th>
      </tr>
    </thead>
    <tbody>
      {patients.map(patient => (
        <tr key={patient.case_id}>
          <td>{patient.patient_name}</td>
          <td>{patient.chief_complaint || '-'}</td>
          <td>{patient.status}</td>
          <td>{new Date(patient.created_at).toLocaleTimeString()}</td>
        </tr>
      ))}
    </tbody>
  </table>
);
```
