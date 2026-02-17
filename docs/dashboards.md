# Dashboard API Documentation

## Overview

The dashboard module provides comprehensive analytics and summary data for both patients and doctors. There are two types of endpoints:

1. **Main Dashboard Endpoints** - Provide core dashboard data with paginated lists
2. **Analytics Endpoints** - Provide aggregated statistics and trends for charts

---

## Patient Endpoints

### GET `/patient/dashboard`

Main patient dashboard with user info, assigned doctors, paginated cases/reports, health charts, alerts, and AI stats.

**Auth**: Required (Patient only)

**Query Parameters**:
- `cases_page` (int, default: 1) - Page number for cases
- `cases_limit` (int, default: 5, max: 50) - Cases per page
- `reports_page` (int, default: 1) - Page number for reports
- `reports_limit` (int, default: 5, max: 50) - Reports per page

**Response**: `PatientDashboardResponse`
```json
{
  "user_info": {
    "user_id": "uuid",
    "name": "John Doe",
    "email": "john@example.com",
    "last_profile_update": "2026-01-15T10:30:00Z"
  },
  "assigned_doctors": [
    {
      "doctor_id": "DOC123",
      "name": "Dr. Jane Smith",
      "email": "jane@hospital.com",
      "specialisation": "Endocrinology"
    }
  ],
  "cases": {
    "open": 2,
    "under_review": 1,
    "closed": 5,
    "approved": 3,
    "total": 11,
    "items": [...],
    "pagination": {...}
  },
  "reports": {
    "total": 8,
    "items": [...],
    "pagination": {...}
  },
  "health_charts": {
    "weight_history": [{...}],
    "glucose_readings": [{...}],
    "blood_pressure": [{...}]
  },
  "alerts": [{...}],
  "ai_stats": {
    "chat_count": 3,
    "analyses_count": 5
  },
  "notifications_unread": 2
}
```

---

### GET `/patient/analytics`

**NEW** - Analytics data for patient dashboard charts and visualizations.

**Auth**: Required (Patient only)

**Response**: `PatientAnalyticsResponse`
```json
{
  "appointments": {
    "total": 12,
    "upcoming": 3,
    "completed": 7,
    "cancelled": 1,
    "no_show": 1,
    "by_month": [
      {"month": "2025-09", "count": 2},
      {"month": "2025-10", "count": 3},
      {"month": "2025-11", "count": 2},
      {"month": "2025-12", "count": 1},
      {"month": "2026-01", "count": 3},
      {"month": "2026-02", "count": 1}
    ],
    "by_type": [
      {"type": "Consultation", "count": 5},
      {"type": "Follow-up", "count": 6},
      {"type": "Emergency", "count": 1}
    ],
    "next_appointment": {
      "id": "appt-uuid",
      "doctor_name": "Dr. Jane Smith",
      "start_time": "2026-02-20T14:00:00Z",
      "type": "Follow-up",
      "reason": "Diabetes checkup"
    }
  },
  "medications": [
    "Metformin 500mg",
    "Lisinopril 10mg",
    "Atorvastatin 20mg"
  ],
  "vitals": {
    "blood_group": "B+",
    "height_cm": 175.0,
    "weight_kg": 78.0
  },
  "reports_by_month": [
    {"month": "2025-12", "count": 2},
    {"month": "2026-01", "count": 3},
    {"month": "2026-02", "count": 1}
  ],
  "cases_by_month": [
    {"month": "2025-11", "count": 1},
    {"month": "2025-12", "count": 2},
    {"month": "2026-01", "count": 2}
  ]
}
```

**Frontend Usage**:
```typescript
// Fetch analytics data
const analytics = await api.get('/patient/analytics');

// Display vital signs cards
<VitalCard label="Blood Group" value={analytics.vitals.blood_group} />
<VitalCard label="Height" value={`${analytics.vitals.height_cm} cm`} />
<VitalCard label="Weight" value={`${analytics.vitals.weight_kg} kg`} />

// Render appointment status donut chart
<DonutChart data={[
  { label: 'Completed', value: analytics.appointments.completed },
  { label: 'Upcoming', value: analytics.appointments.upcoming },
  { label: 'Cancelled', value: analytics.appointments.cancelled },
  { label: 'No-show', value: analytics.appointments.no_show }
]} />

// Render appointments by month bar chart
<BarChart 
  data={analytics.appointments.by_month}
  xKey="month"
  yKey="count"
  title="Appointments Over Time"
/>

// Display medications list
<MedicationList items={analytics.medications} />

// Show next appointment card
{analytics.appointments.next_appointment && (
  <NextAppointmentCard appointment={analytics.appointments.next_appointment} />
)}
```

---

## Doctor Endpoints

### GET `/doctor/dashboard`

Main doctor dashboard with user info, patient stats, paginated cases, pending approvals, alerts, and AI stats.

**Auth**: Required (Doctor only)

**Query Parameters**:
- `cases_page` (int, default: 1) - Page number for cases
- `cases_limit` (int, default: 10, max: 50) - Cases per page

**Response**: `DoctorDashboardResponse`
```json
{
  "user_info": {
    "user_id": "uuid",
    "name": "Dr. Jane Smith",
    "email": "jane@hospital.com",
    "specialisation": "Endocrinology"
  },
  "patient_stats": {
    "active": 25,
    "max": 50,
    "load_percentage": 50.0
  },
  "cases": {
    "open": 8,
    "under_review": 3,
    "closed": 12,
    "approved": 10,
    "total": 33,
    "items": [...],
    "pagination": {...}
  },
  "pending_approvals": [{...}],
  "alerts": [{...}],
  "ai_stats": {
    "chat_count": 15,
    "analyses_count": 42
  },
  "notifications_unread": 5
}
```

---

### GET `/doctor/analytics`

**NEW** - Analytics data for doctor dashboard charts and visualizations.

**Auth**: Required (Doctor only)

**Response**: `DoctorAnalyticsResponse`
```json
{
  "appointments": {
    "total": 156,
    "today": 4,
    "upcoming_week": 12,
    "completed": 120,
    "cancelled": 15,
    "no_show": 21,
    "by_month": [
      {"month": "2025-09", "count": 22},
      {"month": "2025-10", "count": 28},
      {"month": "2025-11", "count": 25},
      {"month": "2025-12", "count": 20},
      {"month": "2026-01", "count": 30},
      {"month": "2026-02", "count": 11}
    ],
    "by_type": [
      {"type": "Consultation", "count": 65},
      {"type": "Follow-up", "count": 80},
      {"type": "Emergency", "count": 11}
    ],
    "completion_rate": 85.7
  },
  "patient_demographics": {
    "by_gender": [
      {"type": "male", "count": 12},
      {"type": "female", "count": 13}
    ],
    "by_age_group": [
      {"type": "18-30", "count": 5},
      {"type": "31-45", "count": 8},
      {"type": "46-60", "count": 7},
      {"type": "60+", "count": 5}
    ]
  },
  "cases_by_month": [
    {"month": "2025-12", "count": 8},
    {"month": "2026-01", "count": 12},
    {"month": "2026-02", "count": 5}
  ],
  "cases_by_type": [
    {"type": "initial", "count": 10},
    {"type": "follow_up", "count": 12},
    {"type": "urgent", "count": 2},
    {"type": "routine", "count": 1}
  ],
  "reports_analyzed": 38,
  "reports_pending": 7
}
```

**Frontend Usage**:
```typescript
// Fetch analytics data
const analytics = await api.get('/doctor/analytics');

// Display KPI cards
<KPICard label="Today's Appointments" value={analytics.appointments.today} />
<KPICard label="Upcoming Week" value={analytics.appointments.upcoming_week} />
<KPICard label="Completion Rate" value={`${analytics.appointments.completion_rate}%`} />

// Render appointment trends bar chart
<BarChart 
  data={analytics.appointments.by_month}
  xKey="month"
  yKey="count"
  title="Appointments Over Time"
/>

// Render patient gender distribution pie chart
<PieChart 
  data={analytics.patient_demographics.by_gender}
  labelKey="type"
  valueKey="count"
  title="Patients by Gender"
/>

// Render patient age distribution bar chart
<BarChart 
  data={analytics.patient_demographics.by_age_group}
  xKey="type"
  yKey="count"
  title="Patients by Age Group"
/>

// Render case distribution donut chart
<DonutChart 
  data={analytics.cases_by_type}
  labelKey="type"
  valueKey="count"
  title="Cases by Type"
/>

// Display report stats
<ReportStatsCard 
  analyzed={analytics.reports_analyzed}
  pending={analytics.reports_pending}
/>
```

---

## Data Aggregation Logic

### Appointment Analytics
- **Last 6 months**: All monthly counts are based on appointments created in the last 180 days
- **Upcoming**: Appointments with status "Scheduled" and `start_time > now`
- **Today** (Doctor only): Appointments with `start_time` between today 00:00 and 23:59
- **Upcoming Week** (Doctor only): Scheduled appointments in the next 7 days
- **Completion Rate**: `(completed / (total - cancelled)) * 100`

### Patient Demographics (Doctor only)
- **Gender**: Counted from assigned patients' `gender` field
- **Age Groups**: Calculated from `date_of_birth`:
  - 0-17: Under 18
  - 18-30: Young adults
  - 31-45: Adults
  - 46-60: Middle-aged
  - 60+: Seniors

### Case/Report Trends
- **Monthly counts**: Grouped by `created_at` month in YYYY-MM format
- **Last 6 months**: Only includes records from the last 180 days

---

## Error Handling

All endpoints return standard HTTP status codes:

- **200 OK**: Success
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: User role doesn't match endpoint requirements
- **404 Not Found**: User/patient/doctor not found
- **422 Unprocessable Entity**: Invalid request parameters

Error response format:
```json
{
  "detail": "Error message here"
}
```

---

## Notes for Frontend Developers

1. **Combine Both Endpoints**: Use `/patient/dashboard` for the main data and `/patient/analytics` for chart visualizations
2. **Caching**: Analytics data changes slowly - consider caching for 5-10 minutes
3. **Loading States**: Analytics queries can be slow due to aggregations - show skeleton loaders
4. **Empty States**: Handle cases where `by_month` arrays are empty (new users)
5. **Date Formatting**: All dates are in ISO 8601 format with UTC timezone
6. **Medications**: Array of strings from patient profile - display as a simple list
7. **Vital Signs**: May be `null` if not set in patient profile - handle gracefully
