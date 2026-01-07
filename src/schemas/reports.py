from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.database.core import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=True, index=True)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)

    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # 'pdf' | 'image'
    content_type = Column(String, nullable=False)  # mime type
    storage_path = Column(String, nullable=False)  # path in Supabase bucket
    file_size_bytes = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])
