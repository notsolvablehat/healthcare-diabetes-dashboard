# src/sharing/controller.py
"""API endpoints for document sharing module."""

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import RedirectResponse

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.supabase import SupabaseClient

from .models import (
    AccessTokenResponse,
    CreateShareLinkRequest,
    ManageLinksResponse,
    ShareLinkResponse,
)
from .services import (
    access_shared_link,
    create_share_link,
    get_my_shared_links,
    revoke_shared_link,
)

router = APIRouter(prefix="/share", tags=["sharing"])


@router.post("/create", response_model=ShareLinkResponse, status_code=http_status.HTTP_201_CREATED)
def create_share_link_endpoint(
    user: CurrentUser,
    db: DbSession,
    request_obj: CreateShareLinkRequest,
    http_request: Request,
):
    """
    Create a shareable link for a report or document.
    
    Generates a unique, time-limited URL that can be shared with anyone.
    The recipient does not need to log in to access the file.
    
    Access control:
    - Only the owner (patient) can create share links
    - Links can be set to expire between 1 hour and 7 days
    - Links can be revoked manually at any time
    
    Supported resources:
    - report: Medical reports uploaded by patients
    - document: Personal documents (insurance, IDs, bills, etc.)
    
    The generated link will track:
    - Number of times accessed (views)
    - Expiration time
    - Active/revoked status
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can create share links"
        )
    
    # Construct base URL from request
    base_url = str(http_request.base_url).rstrip('/')
    
    return create_share_link(
        db=db,
        user_id=user.user_id,
        request=request_obj,
        base_url=base_url,
    )


@router.get("/access/{token}")
def access_shared_link_endpoint(
    token: str,
    db: DbSession,
    supabase: SupabaseClient,
):
    """
    Access a shared file via token (Public endpoint - no authentication required).
    
    This endpoint is publicly accessible and does not require login.
    
    Behavior:
    1. Validates the token exists and is active
    2. Checks if the link has expired
    3. Increments the view counter
    4. Redirects directly to the file for viewing/download (valid for 5 minutes)
    
    Error responses:
    - 404: Link not found
    - 403: Link has been revoked by owner
    - 410: Link has expired
    - 404: Shared file was deleted
    
    The user is redirected to a temporary Supabase Storage URL
    that expires after 5 minutes for security.
    """
    result = access_shared_link(db=db, supabase=supabase, token=token)
    return RedirectResponse(url=result.download_url, status_code=http_status.HTTP_302_FOUND)


@router.get("/manage", response_model=ManageLinksResponse)
def manage_shared_links_endpoint(
    user: CurrentUser,
    db: DbSession,
):
    """
    Get all shared links created by the authenticated user.
    
    Returns a list of all share links with their status:
    - Active/revoked status
    - Expiration time
    - Number of views
    - Associated resource details
    
    Use this endpoint to:
    - Monitor which files have been shared
    - Check how many times links have been accessed
    - Identify expired links
    - Get link IDs for revocation
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can manage share links"
        )
    
    return get_my_shared_links(db=db, user_id=user.user_id)


@router.delete("/{link_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def revoke_shared_link_endpoint(
    link_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """
    Revoke a shared link.
    
    Marks the link as inactive, preventing further access.
    The link will immediately stop working for anyone who has it.
    
    This operation:
    - Sets is_active to False
    - Does not delete the link record (for audit trail)
    - Preserves view count and creation metadata
    
    Only the owner who created the link can revoke it.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can revoke share links"
        )
    
    revoke_shared_link(db=db, user_id=user.user_id, link_id=link_id)
