# src/documents/services.py
"""Business logic for personal documents module."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from supabase import Client

from src.schemas.users.users import PersonalDocument as PersonalDocumentORM

from .models import (
    DocumentCategory,
    DocumentConfirmRequest,
    DocumentListResponse,
    DownloadUrlResponse,
    FileType,
    PersonalDocumentResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)

# Allowed MIME types for personal documents
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

STORAGE_BUCKET = "medical-reports"  # Using same bucket but different folder structure


def get_my_documents(db: Session, user_id: str) -> DocumentListResponse:
    """
    Get all personal documents for a user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        List of personal documents
    """
    documents = db.query(PersonalDocumentORM).filter(
        PersonalDocumentORM.user_id == user_id
    ).order_by(PersonalDocumentORM.created_at.desc()).all()
    
    return DocumentListResponse(
        count=len(documents),
        documents=[PersonalDocumentResponse.model_validate(doc) for doc in documents]
    )


def generate_upload_url(
    db: Session,
    supabase: Client,
    user_id: str,
    request: UploadUrlRequest,
) -> UploadUrlResponse:
    """
    Generate signed upload URL for personal document.
    
    Args:
        db: Database session
        user_id: User uploading the document
        request: Upload URL request
        
    Returns:
        Upload URL and document ID
        
    Raises:
        HTTPException: If validation fails
    """
    # Validate content type
    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )
    
    # Determine file type
    file_type = FileType.PDF if request.content_type == "application/pdf" else FileType.IMAGE
    
    # Generate document ID
    document_id = str(uuid4())
    
    # Generate storage path: personal-documents/{user_id}/{timestamp}_{doc_id}.{ext}
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_extension = request.filename.split('.')[-1] if '.' in request.filename else 'bin'
    storage_path = f"personal-documents/{user_id}/{timestamp}_{document_id}.{file_extension}"
    
    # Create pending document record
    document = PersonalDocumentORM(
        id=document_id,
        user_id=user_id,
        file_name=request.filename,
        file_type=file_type.value,
        category=request.category.value,
        storage_path=storage_path,
        description=request.description,
        created_at=datetime.utcnow(),
    )
    
    db.add(document)
    db.commit()
    
    # Generate signed upload URL
    try:
        upload_url = supabase.storage.from_(STORAGE_BUCKET).create_signed_upload_url(path=storage_path)
        
        return UploadUrlResponse(
            document_id=document_id,
            upload_url=upload_url["signed_url"],
            storage_path=storage_path,
            expires_in=3600,
        )
    except Exception as e:
        # Rollback document creation if URL generation fails
        db.delete(document)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        ) from e


def confirm_upload(
    db: Session,
    user_id: str,
    document_id: str,
    request: DocumentConfirmRequest,
) -> PersonalDocumentResponse:
    """
    Confirm document upload and update file size.
    
    Args:
        db: Database session
        user_id: User who uploaded
        document_id: Document ID
        request: Confirmation request
        
    Returns:
        Updated document
        
    Raises:
        HTTPException: If document not found or unauthorized
    """
    document = db.query(PersonalDocumentORM).filter(
        PersonalDocumentORM.id == document_id,
        PersonalDocumentORM.user_id == user_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have permission to confirm it"
        )
    
    # Update file size if provided
    if request.file_size_bytes:
        setattr(document, 'file_size_bytes', request.file_size_bytes)
    
    db.commit()
    db.refresh(document)
    
    return PersonalDocumentResponse.model_validate(document)


def get_download_url(
    db: Session,
    supabase: Client,
    user_id: str,
    document_id: str,
) -> DownloadUrlResponse:
    """
    Generate signed download URL for a document.
    
    Args:
        db: Database session
        user_id: User requesting download
        document_id: Document ID
        
    Returns:
        Download URL
        
    Raises:
        HTTPException: If document not found or unauthorized
    """
    document = db.query(PersonalDocumentORM).filter(
        PersonalDocumentORM.id == document_id,
        PersonalDocumentORM.user_id == user_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have permission to access it"
        )
    
    try:
        download_url = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            path=str(document.storage_path),
            expires_in=3600
        )
        
        return DownloadUrlResponse(
            document_id=document_id,
            download_url=download_url["signedURL"],
            expires_in=3600,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        ) from e


def delete_document(
    db: Session,
    supabase: Client,
    user_id: str,
    document_id: str,
) -> None:
    """
    Delete a personal document.
    
    Args:
        db: Database session
        user_id: User requesting deletion
        document_id: Document ID
        
    Raises:
        HTTPException: If document not found or unauthorized
    """
    document = db.query(PersonalDocumentORM).filter(
        PersonalDocumentORM.id == document_id,
        PersonalDocumentORM.user_id == user_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you don't have permission to delete it"
        )
    
    # Delete from storage
    try:
        supabase.storage.from_(STORAGE_BUCKET).remove([str(document.storage_path)])
    except Exception as e:
        # Log error but continue with DB deletion
        print(f"Failed to delete file from storage: {e}")
    
    # Delete from database
    db.delete(document)
    db.commit()
