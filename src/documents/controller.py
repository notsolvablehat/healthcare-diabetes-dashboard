# src/documents/controller.py
"""API endpoints for personal documents module."""

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.supabase import SupabaseClient

from .models import (
    DocumentConfirmRequest,
    DocumentListResponse,
    DownloadUrlResponse,
    PersonalDocumentResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from .services import (
    confirm_upload,
    delete_document,
    get_download_url,
    get_my_documents,
    generate_upload_url,
)

router = APIRouter(prefix="/documents", tags=["personal-documents"])


@router.get("", response_model=DocumentListResponse)
def get_documents_endpoint(
    user: CurrentUser,
    db: DbSession,
):
    """
    Get all personal documents for the authenticated user.
    
    Returns documents sorted by creation date (newest first).
    Only the document owner can access their documents.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to patients"
        )
    
    return get_my_documents(db=db, user_id=user.user_id)


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=http_status.HTTP_201_CREATED)
def request_upload_url_endpoint(
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
    request: UploadUrlRequest,
):
    """
    Generate a signed upload URL for a personal document.
    
    This is step 1 of the two-step upload process:
    1. Request upload URL (this endpoint)
    2. Upload file directly to Supabase using the signed URL
    3. Confirm upload with document ID
    
    Allowed file types:
    - PDF: application/pdf
    - Images: image/png, image/jpeg, image/jpg, image/webp
    
    Document categories:
    - insurance: Health insurance cards, policy documents
    - identity: Government IDs (Aadhar, PAN, Driver's License)
    - bill: Hospital invoices, payment receipts
    - prescription: Manual uploads of physical prescriptions
    - other: General documents
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can upload personal documents"
        )
    
    return generate_upload_url(db=db, supabase=supabase, user_id=user.user_id, request=request)


@router.post("/{document_id}/confirm", response_model=PersonalDocumentResponse)
def confirm_upload_endpoint(
    document_id: str,
    user: CurrentUser,
    db: DbSession,
    request: DocumentConfirmRequest,
):
    """
    Confirm that document upload was successful.
    
    This is step 3 of the upload process, called after uploading
    the file directly to Supabase Storage using the signed URL.
    
    Updates the document record with file size and marks it as confirmed.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can confirm document uploads"
        )
    
    return confirm_upload(
        db=db,
        user_id=user.user_id,
        document_id=document_id,
        request=request,
    )


@router.get("/{document_id}/download", response_model=DownloadUrlResponse)
def get_download_url_endpoint(
    document_id: str,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
):
    """
    Generate a signed download URL for a personal document.
    
    The URL expires after 1 hour (3600 seconds).
    Use this URL to fetch the actual file from storage.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can download personal documents"
        )
    
    return get_download_url(db=db, supabase=supabase, user_id=user.user_id, document_id=document_id)


@router.delete("/{document_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: str,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
):
    """
    Delete a personal document.
    
    Removes the document from both the database and Supabase Storage.
    Only the document owner can delete their documents.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can delete personal documents"
        )
    
    delete_document(db=db, supabase=supabase, user_id=user.user_id, document_id=document_id)
