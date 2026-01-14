import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.mongo import MongoDb
from src.database.supabase import SupabaseClient
from src.reports.models import (
    DownloadUrlResponse,
    ReportConfirmRequest,
    ReportListResponse,
    ReportResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from src.reports.services import report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=status.HTTP_201_CREATED)
def generate_upload_url(
    request: UploadUrlRequest,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
):
    """
    Generate a signed upload URL for direct file upload to Supabase Storage.
    - Patients can upload their own reports
    - Doctors can upload reports for their assigned patients
    Returns a signed URL valid for 1 hour, along with the report_id for confirmation.
    """
    try:
        result = report_service.generate_upload_url(
            supabase=supabase,
            db=db,
            user_id=user.user_id,
            user_role=user.role,
            request=request,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


async def run_background_extraction(
    report_id: str,
    patient_id: str,
    storage_path: str,
    content_type: str,
    supabase: SupabaseClient,
    mongo_db: MongoDb,
    db: DbSession,
):
    """Background task to extract report data using AI."""
    from src.ai.services import extraction_service

    try:
        await extraction_service.extract_report_background(
            report_id=report_id,
            patient_id=patient_id,
            storage_path=storage_path,
            content_type=content_type,
            supabase=supabase,
            mongo_db=mongo_db,
            db=db,
        )
    except Exception as e:
        logger.error(f"[Background Extraction] Failed for report {report_id}: {e}")


@router.post("/{report_id}/confirm", response_model=ReportResponse)
async def confirm_upload(
    report_id: str,
    request: ReportConfirmRequest,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
    mongo_db: MongoDb,
    background_tasks: BackgroundTasks,
):
    """
    Confirm that a file was uploaded successfully.
    Call this after uploading the file to Supabase using the signed URL.
    Optionally updates the file size.
    Triggers background AI extraction of medical data from the report.
    """
    result = report_service.confirm_upload(
        db=db,
        user_id=user.user_id,
        report_id=report_id,
        file_size_bytes=request.file_size_bytes,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or you are not authorized to confirm this upload."
        )

    # Trigger background extraction
    logger.info(f"[Reports] Triggering background extraction | report_id={report_id}")
    background_tasks.add_task(
        run_background_extraction,
        report_id=report_id,
        patient_id=result.patient_id,
        storage_path=result.storage_path,
        content_type=result.content_type,
        supabase=supabase,
        mongo_db=mongo_db,
        db=db,
    )

    return result


@router.get("/case/{case_id}", response_model=ReportListResponse)
def get_reports_by_case(
    case_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """
    List all reports attached to a specific case.
    Access is granted to:
    - The patient who owns the case
    - Doctors assigned to the patient
    """
    reports = report_service.get_reports_by_case(
        db=db,
        user_id=user.user_id,
        user_role=user.role,
        case_id=case_id,
    )

    return ReportListResponse(total=len(reports), reports=reports)


@router.get("/patient/{patient_id}", response_model=ReportListResponse)
def get_reports_by_patient(
    patient_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """
    List all reports for a specific patient.
    Access is granted to:
    - The patient themselves
    - Doctors assigned to the patient
    """
    reports = report_service.get_reports_by_patient(
        db=db,
        user_id=user.user_id,
        user_role=user.role,
        patient_id=patient_id,
    )

    return ReportListResponse(total=len(reports), reports=reports)


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """
    Get metadata for a specific report.
    """
    report = report_service.get_report_by_id(
        db=db,
        user_id=user.user_id,
        user_role=user.role,
        report_id=report_id,
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or you are not authorized to view it."
        )

    return report


@router.get("/{report_id}/download", response_model=DownloadUrlResponse)
def get_download_url(
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
):
    """
    Generate a signed download URL for a report.

    Returns a URL valid for 1 hour that can be used to download the file.
    """
    result = report_service.generate_download_url(
        supabase=supabase,
        db=db,
        user_id=user.user_id,
        user_role=user.role,
        report_id=report_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or you are not authorized to download it."
        )

    return DownloadUrlResponse(**result)
