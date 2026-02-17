from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from src.database.core import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True)
    # Human-readable business ID (e.g., CASE20260105ABCD1234)
    case_id = Column(String, unique=True, nullable=False, index=True)
    # Link to Mongo
    mongo_case_id = Column(String, nullable=True, unique=True, index=True)

    # Searchable Metadata (Keep this! It's fast for lists)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="open", index=True)
    case_type = Column(String, default="routine", index=True)
    chief_complaint = Column(String) # Short text for the dashboard list view
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    doctor = relationship("User", foreign_keys=[doctor_id])
