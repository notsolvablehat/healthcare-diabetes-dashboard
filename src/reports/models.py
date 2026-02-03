from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FileType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"


class AvailablePatient(BaseModel):
    """Simplified patient info for report upload selection."""
    user_id: str = Field(..., description="Patient's user ID")
    patient_id: str = Field(..., description="Patient's medical ID")
    name: str = Field(..., description="Patient's full name")
    email: str = Field(..., description="Patient's email")
    gender: str | None = Field(None, description="Patient's gender")
    date_of_birth: datetime | None = Field(None, description="Patient's date of birth")


class AvailablePatientsResponse(BaseModel):
    """Response for listing patients available for report upload."""
    total: int = Field(..., description="Total number of patients")
    patients: list[AvailablePatient] = Field(..., description="List of patients the doctor can upload reports for")


class UploadUrlRequest(BaseModel):
    """Request to generate a signed upload URL."""
    filename: str = Field(..., description="Original filename with extension")
    content_type: str = Field(..., description="MIME type (e.g., 'application/pdf', 'image/png')")
    case_id: str | None = Field(None, description="Optional case to link report to")
    patient_id: str = Field(..., description="Patient the report belongs to")
    description: str | None = Field(None, description="Optional description of the report")


class ReportConfirmRequest(BaseModel):
    """Request to confirm upload and save metadata."""
    storage_path: str = Field(..., description="Path returned from upload-url endpoint")
    file_size_bytes: int | None = Field(None, description="Size of uploaded file in bytes")

class UploadUrlResponse(BaseModel):
    """Response containing signed upload URL."""
    report_id: str = Field(..., description="Generated report ID (use for confirmation)")
    upload_url: str = Field(..., description="Signed URL for direct upload to Supabase")
    storage_path: str = Field(..., description="Path where file will be stored")
    expires_in: int = Field(default=3600, description="URL expiry time in seconds")

class ReportResponse(BaseModel):
    """Report metadata response."""
    id: str
    case_id: str | None = None
    patient_id: str
    patient_name: str | None = None  # Patient name for doctor views
    uploaded_by: str
    file_name: str
    file_type: FileType
    content_type: str
    storage_path: str
    file_size_bytes: int | None = None
    description: str | None = None
    mongo_analysis_id: str | None = None  # MongoDB analysis ID if report has been analyzed
    created_at: datetime

    class Config:
        from_attributes = True


class DownloadUrlResponse(BaseModel):
    """Response containing signed download URL."""
    report_id: str
    download_url: str
    expires_in: int = Field(default=3600, description="URL expiry time in seconds")


class ReportListResponse(BaseModel):
    """Response for listing reports."""
    total: int
    reports: list[ReportResponse]


class ActivityEvent(BaseModel):
    """Single activity event for a report."""
    activity_type: str = Field(..., description="Type: upload, analysis, extraction, explanation_request, download")
    user_id: str = Field(..., description="User who performed the activity")
    user_role: str = Field(..., description="Role: patient, doctor")
    status: str = Field(..., description="Status: completed, failed, in_progress")
    timestamp: datetime = Field(..., description="When the activity occurred")
    metadata: dict | None = Field(None, description="Additional activity-specific data")
    error_message: str | None = Field(None, description="Error message if failed")


class ReportActivityResponse(BaseModel):
    """Response for report activity history."""
    report_id: str
    patient_id: str
    total_activities: int
    activities: list[ActivityEvent] = Field(..., description="Activities sorted by timestamp (newest first)")

    # Summary counts
    upload_count: int = Field(default=0, description="Number of upload events")
    analysis_count: int = Field(default=0, description="Number of analysis attempts")
    extraction_count: int = Field(default=0, description="Number of extraction attempts")
    explanation_count: int = Field(default=0, description="Number of explanation requests")
    download_count: int = Field(default=0, description="Number of download events")


class ExplanationRequest(BaseModel):
    """Request for AI explanation of selected text from a report."""
    selected_text: str = Field(..., min_length=1, max_length=500, description="Text selected from the report")
    question: str | None = Field(None, max_length=200, description="Optional specific question about the text")


class AnalysisStatusResponse(BaseModel):
    """Response indicating if a report has been analyzed."""
    report_id: str
    is_analyzed: bool = Field(..., description="Whether the report has been analyzed")
    analysis_count: int = Field(..., description="Total number of analyses performed")
    latest_analysis_id: str | None = Field(None, description="MongoDB ID of the latest analysis")
    latest_analysis_date: datetime | None = Field(None, description="When the latest analysis was performed")


class AnalysisSummary(BaseModel):
    """Summary of a single analysis."""
    mongo_id: str = Field(..., description="MongoDB document ID")
    status: str = Field(..., description="Analysis status: completed, failed")
    analysis_type: str | None = Field(None, description="Type: extraction or diabetes_analysis")
    created_at: datetime
    processing_time_ms: int | None = None
    # For extraction
    report_type: str | None = None
    lab_results_count: int | None = None
    medications_count: int | None = None
    # For diabetes analysis
    prediction_label: str | None = None
    prediction_confidence: float | None = None


class AnalysesListResponse(BaseModel):
    """Response for listing all analyses of a report."""
    report_id: str
    total_analyses: int
    analyses: list[AnalysisSummary] = Field(..., description="All analyses sorted by date (newest first)")


class AnalysisDetailResponse(BaseModel):
    """Complete analysis data from MongoDB."""
    analysis_id: str = Field(..., description="MongoDB document ID")
    report_id: str
    patient_id: str
    status: str = Field(..., description="Analysis status: completed, failed")
    created_at: datetime
    processing_time_ms: int | None = None

    # Raw text extracted from document
    raw_text: str | None = None

    # Extraction data (if extraction analysis)
    extracted_data: dict | None = Field(None, description="Full extracted medical data")

    # Diabetes prediction data (if diabetes analysis)
    extracted_features: dict | None = Field(None, description="Features used for diabetes prediction")
    prediction: dict | None = Field(None, description="Diabetes prediction results")
    narrative: str | None = Field(None, description="AI-generated narrative explanation")

    # Error information
    error: str | None = Field(None, description="Error message if status is failed")

