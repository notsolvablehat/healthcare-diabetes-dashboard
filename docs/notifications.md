# Notifications Module Documentation

## Overview
The notifications module provides a persistent, polling-based notification system for both patients and doctors. It is integrated directly into the main dashboards for unread counts and offers separate endpoints for listing and management.

---

## 1. Badge Integration (Unread Count)

### **Option A: Via Dashboard (Recommended)**
The unread count is included in the dashboard response. Use this to set the initial badge state on page load.

- **Endpoint**: `GET /patient/dashboard` OR `GET /doctor/dashboard`
- **Field**: `notifications_unread` (integer)

```json
{
  "user_info": { ... },
  "notifications_unread": 3,  // <--- Use this for the red badge
  "cases": { ... }
}
```

### **Option B: Polling Endpoint**
Use this to update the badge periodically (e.g., every 60 seconds) without re-fetching the entire dashboard.

- **Endpoint**: `GET /notifications/unread-count`
- **Response**:
```json
{
  "count": 5
}
```

---

## 2. listing Notifications

Fetch the full list of notifications when the user clicks the bell icon.

- **Endpoint**: `GET /notifications`
- **Query Params**:
  - `page` (default: 1)
  - `limit` (default: 20)
  - `unread_only` (default: false) - Set `true` to show only unread items.

**Response:**
```json
{
  "total": 50,
  "unread_count": 5,
  "page": 1,
  "limit": 20,
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "case_status_changed",
      "title": "Case Approved",
      "message": "Your case #CASE123 has been approved by Dr. Smith.",
      "link": "/cases/CASE123",
      "is_read": false,
      "created_at": "2026-01-18T10:00:00Z"
    }
  ]
}
```

---

## 3. Marking as Read

### **Mark Single Item**
Call this when the user clicks/views a specific notification.

- **Endpoint**: `PATCH /notifications/{notification_id}/read`
- **Response**: `200 OK`

### **Mark All Read**
Call this if you have a "Mark all as read" button.

- **Endpoint**: `PATCH /notifications/read-all`
- **Response**: `200 OK`

---

## 4. Notification Types & Actions

Handle user clicks based on the `link` field provided in the notification object.

| Type | Audience | Trigger Trigger | Recommended Action |
|------|----------|-----------------|--------------------|
| `case_status_changed` | Patient | Case status update | Navigate to `link` (Case Details) |
| `doctor_assigned` | Patient | Doctor assigned | Navigate to `/my-doctors` |
| `report_analyzed` | Patient | AI Analysis done | Navigate to `link` (Report Details) |
| `doctor_note_added` | Patient | Note added to case | Navigate to `link` (Case Details) |
| `new_case_assigned` | Doctor | New case created | Navigate to `link` (Case Details) |
| `new_report_uploaded` | Doctor | Patient upload | Navigate to `link` (Report Details) |
| `case_needs_approval` | Doctor | Status -> Under Review | Navigate to `link` (Case Details) |

---

## 5. Frontend Implementation Checklist

- [ ] **Initial Load**: Get `notifications_unread` from Dashboard API.
- [ ] **Polling**: Poll `GET /notifications/unread-count` every 60s to update badge.
- [ ] **Dropdown**: On bell click, fetch `GET /notifications`.
- [ ] **Interaction**: On item click:
    1. Call `PATCH /notifications/{id}/read` (optimistic UI update).
    2. Navigate to `notification.link`.
- [ ] **Styling**:
    - Use `is_read: false` to highlight unread items (e.g., light blue background).
    - Display `created_at` using relative time (e.g., "5 mins ago").
