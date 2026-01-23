# src/documents/models.py
"""Pydantic models for personal documents module."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    """Category of personal document."""
    INSURANCE = "insurance"
    IDENTITY = "identity"
    BILL = "bill"
    PRESCRIPTION = "prescription"
    OTHER = "other"


class FileType(str, Enum):
    """Type of file."""
    PDF = "pdf"
    IMAGE = "image"


class UploadUrlRequest(BaseModel):
    """Request to generate upload URL for a personal document."""
    filename: str = Field(..., description="Original filename with extension")
    content_type: str = Field(..., description="MIME type (e.g., image/jpeg, application/pdf)")
    category: DocumentCategory = Field(..., description="Document category")
    description: str | None = Field(None, max_length=500, description="Optional description")


class UploadUrlResponse(BaseModel):
    """Response containing signed upload URL."""
    document_id: str
    upload_url: str
    storage_path: str
    expires_in: int = 3600


class DocumentConfirmRequest(BaseModel):
    """Request to confirm document upload."""
    storage_path: str
    file_size_bytes: int | None = None


class PersonalDocumentResponse(BaseModel):
    """Response model for a personal document."""
    id: str
    user_id: str
    file_name: str
    file_type: FileType
    category: DocumentCategory
    storage_path: str
    file_size_bytes: int | None = None
    description: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response for listing personal documents."""
    count: int
    documents: list[PersonalDocumentResponse]


class DownloadUrlResponse(BaseModel):
    """Response containing signed download URL."""
    document_id: str
    download_url: str
    expires_in: int = 3600
