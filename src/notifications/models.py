# src/notifications/models.py
"""Pydantic schemas for notifications API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    """Notification type enum."""
    # Patient notifications
    CASE_STATUS_CHANGED = "case_status_changed"
    CASE_CREATED = "case_created"  # Doctor created case for patient
    CASE_UPDATED = "case_updated"  # Doctor updated case data
    DOCTOR_ASSIGNED = "doctor_assigned"
    REPORT_ANALYZED = "report_analyzed"
    DOCTOR_NOTE_ADDED = "doctor_note_added"

    # Doctor notifications
    NEW_CASE_ASSIGNED = "new_case_assigned"
    NEW_REPORT_UPLOADED = "new_report_uploaded"
    CASE_NEEDS_APPROVAL = "case_needs_approval"


class NotificationResponse(BaseModel):
    """Single notification response."""
    id: str
    type: str
    title: str
    message: str
    link: str | None = None
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated notifications response."""
    total: int
    unread_count: int
    page: int
    limit: int
    items: list[NotificationResponse] = Field(default_factory=list)


class UnreadCountResponse(BaseModel):
    """Unread count response for badge."""
    count: int
