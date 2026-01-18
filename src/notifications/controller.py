# src/notifications/controller.py
"""Notification API endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from src.auth.services import CurrentUser
from src.database.core import DbSession

from .models import NotificationListResponse, UnreadCountResponse
from .services import get_notifications, get_unread_count, mark_all_as_read, mark_as_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Only show unread notifications"),
):
    """
    Get paginated list of notifications for the current user.
    Includes unread count for badge.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    return get_notifications(
        db=db,
        user_id=user.user_id,
        page=page,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_notification_count(user: CurrentUser, db: DbSession):
    """
    Get unread notification count for badge display.
    Lightweight endpoint for polling.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    return get_unread_count(db, user.user_id)


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """Mark a single notification as read."""
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    success = mark_as_read(db, user.user_id, notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    return {"status": "success", "message": "Notification marked as read"}


@router.patch("/read-all")
def mark_all_notifications_read(user: CurrentUser, db: DbSession):
    """Mark all notifications as read."""
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    count = mark_all_as_read(db, user.user_id)
    return {"status": "success", "message": f"Marked {count} notifications as read"}
