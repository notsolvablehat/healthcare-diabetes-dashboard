# src/sharing/models.py
"""Pydantic models for document sharing module."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Type of resource being shared."""
    REPORT = "report"
    DOCUMENT = "document"


class CreateShareLinkRequest(BaseModel):
    """Request to create a shareable link."""
    resource_type: ResourceType = Field(..., description="Type of resource to share")
    resource_id: str = Field(..., description="ID of the report or document")
    expires_in_hours: int = Field(24, ge=1, le=168, description="Expiry time in hours (max 7 days)")


class ShareLinkResponse(BaseModel):
    """Response after creating a share link."""
    share_link: str = Field(..., description="Full shareable URL")
    token: str = Field(..., description="Access token")
    expires_at: datetime = Field(..., description="When the link expires")


class SharedLinkInfo(BaseModel):
    """Information about a shared link."""
    id: str
    token: str
    resource_type: ResourceType
    resource_id: str
    resource_name: str | None = None
    views: int
    expires_at: datetime
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ManageLinksResponse(BaseModel):
    """Response for listing shared links."""
    count: int
    links: list[SharedLinkInfo]


class AccessTokenResponse(BaseModel):
    """Response for accessing a shared link."""
    resource_type: ResourceType
    resource_name: str
    download_url: str
    expires_in: int = 300  # 5 minutes
