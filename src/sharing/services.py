# src/sharing/services.py
"""Business logic for document sharing module."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from supabase import Client

from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import PersonalDocument as PersonalDocumentORM
from src.schemas.users.users import SharedLink as SharedLinkORM
from src.schemas.users.users import User

from .models import (
    AccessTokenResponse,
    CreateShareLinkRequest,
    ManageLinksResponse,
    ResourceType,
    ShareLinkResponse,
    SharedLinkInfo,
)

STORAGE_BUCKET = "medical-reports"


def create_share_link(
    db: Session,
    user_id: str,
    request: CreateShareLinkRequest,
    base_url: str,
) -> ShareLinkResponse:
    """
    Create a shareable link for a report or document.
    
    Args:
        db: Database session
        user_id: Owner's user ID
        request: Share link creation request
        base_url: Base URL for constructing share link
        
    Returns:
        Share link details
        
    Raises:
        HTTPException: If resource not found or unauthorized
    """
    # Verify ownership of resource
    if request.resource_type == ResourceType.REPORT:
        resource = db.query(ReportORM).filter(
            ReportORM.id == request.resource_id,
            ReportORM.patient_id == user_id
        ).first()
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found or you don't have permission to share it"
            )
        
        resource_name = resource.file_name
        storage_path = resource.storage_path
        
    elif request.resource_type == ResourceType.DOCUMENT:
        resource = db.query(PersonalDocumentORM).filter(
            PersonalDocumentORM.id == request.resource_id,
            PersonalDocumentORM.user_id == user_id
        ).first()
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or you don't have permission to share it"
            )
        
        resource_name = resource.file_name
        storage_path = resource.storage_path
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource type"
        )
    
    # Generate unique token
    token = secrets.token_urlsafe(32)
    
    # Calculate expiry
    expires_at = datetime.now(timezone.utc) + timedelta(hours=request.expires_in_hours)
    
    # Create shared link
    shared_link = SharedLinkORM(
        id=str(uuid4()),
        token=token,
        user_id=user_id,
        resource_type=request.resource_type.value,
        resource_id=request.resource_id,
        expires_at=expires_at,
        is_active=True,
        views=0,
        created_at=datetime.now(timezone.utc),
    )
    
    db.add(shared_link)
    db.commit()
    
    # Construct share link URL
    share_url = f"{base_url}/share/access/{token}"
    
    return ShareLinkResponse(
        share_link=share_url,
        token=token,
        expires_at=expires_at,
    )


def access_shared_link(
    db: Session,
    supabase: Client,
    token: str,
) -> AccessTokenResponse:
    """
    Access a shared link and get download URL.
    
    Args:
        db: Database session
        supabase: Supabase client
        token: Access token
        
    Returns:
        Download URL for the shared resource
        
    Raises:
        HTTPException: If link is invalid, expired, or inactive
    """
    # Find shared link
    shared_link = db.query(SharedLinkORM).filter(
        SharedLinkORM.token == token
    ).first()
    
    if not shared_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found"
        )
    
    # Check if active
    if not shared_link.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This share link has been revoked"
        )
    
    # Check if expired
    if shared_link.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired"
        )
    
    # Get resource details
    if shared_link.resource_type == "report":
        resource = db.query(ReportORM).filter(
            ReportORM.id == shared_link.resource_id
        ).first()
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared report no longer exists"
            )
        
        resource_name = resource.file_name
        storage_path = resource.storage_path
        
    elif shared_link.resource_type == "document":
        resource = db.query(PersonalDocumentORM).filter(
            PersonalDocumentORM.id == shared_link.resource_id
        ).first()
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared document no longer exists"
            )
        
        resource_name = resource.file_name
        storage_path = resource.storage_path
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource type"
        )
    
    # Increment view count
    shared_link.views += 1
    db.commit()
    
    # Generate temporary download URL (5 minutes)
    try:
        download_url = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            path=str(storage_path),
            expires_in=300
        )
        
        return AccessTokenResponse(
            resource_type=ResourceType(shared_link.resource_type),
            resource_name=resource_name,
            download_url=download_url["signedURL"],
            expires_in=300,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        ) from e


def get_my_shared_links(
    db: Session,
    user_id: str,
) -> ManageLinksResponse:
    """
    Get all shared links created by a user.
    
    Args:
        db: Database session
        user_id: Owner's user ID
        
    Returns:
        List of shared links
    """
    shared_links = db.query(SharedLinkORM).filter(
        SharedLinkORM.user_id == user_id
    ).order_by(SharedLinkORM.created_at.desc()).all()
    
    # Enrich with resource names
    link_infos = []
    for link in shared_links:
        resource_name = None
        
        if link.resource_type == "report":
            resource = db.query(ReportORM).filter(ReportORM.id == link.resource_id).first()
            resource_name = resource.file_name if resource else "Deleted Report"
        elif link.resource_type == "document":
            resource = db.query(PersonalDocumentORM).filter(PersonalDocumentORM.id == link.resource_id).first()
            resource_name = resource.file_name if resource else "Deleted Document"
        
        link_infos.append(SharedLinkInfo(
            id=link.id,
            token=link.token,
            resource_type=ResourceType(link.resource_type),
            resource_id=link.resource_id,
            resource_name=resource_name,
            views=link.views,
            expires_at=link.expires_at,
            is_active=link.is_active,
            created_at=link.created_at,
        ))
    
    return ManageLinksResponse(
        count=len(link_infos),
        links=link_infos,
    )


def revoke_shared_link(
    db: Session,
    user_id: str,
    link_id: str,
) -> None:
    """
    Revoke a shared link.
    
    Args:
        db: Database session
        user_id: Owner's user ID
        link_id: Shared link ID
        
    Raises:
        HTTPException: If link not found or unauthorized
    """
    shared_link = db.query(SharedLinkORM).filter(
        SharedLinkORM.id == link_id,
        SharedLinkORM.user_id == user_id
    ).first()
    
    if not shared_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or you don't have permission to revoke it"
        )
    
    shared_link.is_active = False
    db.commit()
