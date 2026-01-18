# src/schemas/notifications.py
"""SQLAlchemy model for notifications table."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text

from src.database.core import Base


class Notification(Base):
    """Notification database model."""

    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # 'case_approved', 'new_report', etc.
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String, nullable=True)  # e.g., '/cases/ABC123'
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Notification {self.id} - {self.type}>"
