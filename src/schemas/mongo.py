"""MongoDB schema definitions for various collections."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportActivityLog(BaseModel):
    """Schema for report activity logs in MongoDB."""
    report_id: str = Field(..., description="Report UUID")
    patient_id: str = Field(..., description="Patient UUID")
    user_id: str = Field(..., description="User who performed the activity")
    user_role: str = Field(..., description="Role of the user (patient/doctor)")
    activity_type: str = Field(
        ...,
        description="Type of activity: upload, analysis, extraction, explanation_request, download"
    )
    status: str = Field(
        default="completed",
        description="Status: completed, failed, in_progress"
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional activity-specific data"
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status is failed"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the activity occurred"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
