# src/notifications/services.py
"""Business logic for notifications."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.notifications.models import (
    NotificationListResponse,
    NotificationResponse,
    NotificationType,
    UnreadCountResponse,
)
from src.schemas.notifications import Notification as NotificationORM


def create_notification(
    db: Session,
    user_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    link: str | None = None,
) -> NotificationORM:
    """
    Create a new notification for a user.
    Call this from other services when events occur.
    """
    notification = NotificationORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type=notification_type.value,
        title=title,
        message=message,
        link=link,
        is_read=False,
        created_at=datetime.utcnow(),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notifications(
    db: Session,
    user_id: str,
    page: int = 1,
    limit: int = 20,
    unread_only: bool = False,
) -> NotificationListResponse:
    """Get paginated notifications for a user."""
    query = db.query(NotificationORM).filter(NotificationORM.user_id == user_id)

    if unread_only:
        query = query.filter(NotificationORM.is_read == False)

    total = query.count()
    unread_count = db.query(NotificationORM).filter(
        NotificationORM.user_id == user_id,
        NotificationORM.is_read == False
    ).count()

    offset = (page - 1) * limit
    notifications = query.order_by(NotificationORM.created_at.desc()).offset(offset).limit(limit).all()

    return NotificationListResponse(
        total=total,
        unread_count=unread_count,
        page=page,
        limit=limit,
        items=[NotificationResponse.model_validate(n) for n in notifications],
    )


def get_unread_count(db: Session, user_id: str) -> UnreadCountResponse:
    """Get unread notification count for badge."""
    count = db.query(NotificationORM).filter(
        NotificationORM.user_id == user_id,
        NotificationORM.is_read == False
    ).count()

    return UnreadCountResponse(count=count)


def mark_as_read(db: Session, user_id: str, notification_id: str) -> bool:
    """Mark a single notification as read."""
    notification = db.query(NotificationORM).filter(
        NotificationORM.id == notification_id,
        NotificationORM.user_id == user_id
    ).first()

    if not notification:
        return False

    notification.is_read = True
    db.commit()
    return True


def mark_all_as_read(db: Session, user_id: str) -> int:
    """Mark all notifications as read. Returns count updated."""
    result = db.query(NotificationORM).filter(
        NotificationORM.user_id == user_id,
        NotificationORM.is_read == False
    ).update({"is_read": True})

    db.commit()
    return result


# ============================================================================
# Helper functions for creating specific notification types
# ============================================================================

def notify_case_status_changed(
    db: Session,
    patient_id: str,
    case_id: str,
    new_status: str,
    doctor_name: str | None = None,
) -> NotificationORM:
    """Notify patient when their case status changes."""
    status_messages = {
        "approved_by_doctor": f"Your case #{case_id} has been approved by {doctor_name or 'your doctor'}.",
        "closed": f"Your case #{case_id} has been closed.",
        "under_review": f"Your case #{case_id} is now under review.",
    }
    message = status_messages.get(new_status, f"Your case #{case_id} status changed to {new_status}.")

    return create_notification(
        db=db,
        user_id=patient_id,
        notification_type=NotificationType.CASE_STATUS_CHANGED,
        title="Case Status Updated",
        message=message,
        link=f"/cases/{case_id}",
    )


def notify_doctor_assigned(
    db: Session,
    patient_id: str,
    doctor_name: str,
    specialisation: str,
) -> NotificationORM:
    """Notify patient when a doctor is assigned to them."""
    return create_notification(
        db=db,
        user_id=patient_id,
        notification_type=NotificationType.DOCTOR_ASSIGNED,
        title="Doctor Assigned",
        message=f"Dr. {doctor_name} ({specialisation}) has been assigned to you.",
        link="/my-doctors",
    )


def notify_report_analyzed(
    db: Session,
    patient_id: str,
    report_id: str,
    file_name: str,
) -> NotificationORM:
    """Notify patient when AI analysis is complete."""
    return create_notification(
        db=db,
        user_id=patient_id,
        notification_type=NotificationType.REPORT_ANALYZED,
        title="Report Analysis Complete",
        message=f"AI analysis for '{file_name}' is ready to view.",
        link=f"/reports/{report_id}",
    )


def notify_doctor_note_added(
    db: Session,
    patient_id: str,
    case_id: str,
    doctor_name: str | None = None,
) -> NotificationORM:
    """Notify patient when doctor adds a note."""
    return create_notification(
        db=db,
        user_id=patient_id,
        notification_type=NotificationType.DOCTOR_NOTE_ADDED,
        title="New Doctor Note",
        message=f"{doctor_name or 'Your doctor'} added a note to case #{case_id}.",
        link=f"/cases/{case_id}",
    )


def notify_new_case_assigned(
    db: Session,
    doctor_id: str,
    case_id: str,
    patient_name: str,
    chief_complaint: str,
) -> NotificationORM:
    """Notify doctor when a new case is assigned."""
    return create_notification(
        db=db,
        user_id=doctor_id,
        notification_type=NotificationType.NEW_CASE_ASSIGNED,
        title="New Case Assigned",
        message=f"New case from {patient_name}: {chief_complaint[:50]}...",
        link=f"/cases/{case_id}",
    )


def notify_new_report_uploaded(
    db: Session,
    doctor_id: str,
    patient_name: str,
    report_id: str,
    file_name: str,
) -> NotificationORM:
    """Notify doctor when assigned patient uploads a report."""
    return create_notification(
        db=db,
        user_id=doctor_id,
        notification_type=NotificationType.NEW_REPORT_UPLOADED,
        title="New Report Uploaded",
        message=f"{patient_name} uploaded a new report: {file_name}",
        link=f"/reports/{report_id}",
    )


def notify_case_needs_approval(
    db: Session,
    doctor_id: str,
    case_id: str,
    patient_name: str,
) -> NotificationORM:
    """Notify doctor when a case needs their approval."""
    return create_notification(
        db=db,
        user_id=doctor_id,
        notification_type=NotificationType.CASE_NEEDS_APPROVAL,
        title="Case Needs Approval",
        message=f"Case #{case_id} from {patient_name} is ready for your review.",
        link=f"/cases/{case_id}",
    )

def notify_case_created_for_patient(
    db: Session,
    patient_id: str,
    case_id: str,
    doctor_name: str,
    chief_complaint: str,
) -> NotificationORM:
    """Notify patient when doctor creates a case for them."""
    return create_notification(
        db=db,
        user_id=patient_id,
        notification_type=NotificationType.CASE_CREATED,
        title="New Case Created",
        message=f"Dr. {doctor_name} created a new case for you: {chief_complaint[:50]}{'...' if len(chief_complaint) > 50 else ''}",
        link=f"/cases/{case_id}",
    )


def notify_case_updated(
    db: Session,
    patient_id: str,
    case_id: str,
    doctor_name: str,
) -> NotificationORM:
    """Notify patient when doctor updates their case."""
    return create_notification(
        db=db,
        user_id=patient_id,
        notification_type=NotificationType.CASE_UPDATED,
        title="Case Updated",
        message=f"Dr. {doctor_name} updated your case #{case_id}.",
        link=f"/cases/{case_id}",
    )