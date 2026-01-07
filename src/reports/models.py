from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FileType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"


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
    uploaded_by: str
    file_name: str
    file_type: FileType
    content_type: str
    storage_path: str
    file_size_bytes: int | None = None
    description: str | None = None
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
