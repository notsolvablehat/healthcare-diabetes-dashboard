import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.mongo import MongoDb
from src.database.supabase import SupabaseClient
from src.reports.models import (
    AnalysesListResponse,
    AnalysisDetailResponse,
    AnalysisStatusResponse,
    DownloadUrlResponse,
    ExplanationRequest,
    ReportActivityResponse,
    ReportConfirmRequest,
    ReportListResponse,
    ReportResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from src.reports.services import report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportListResponse)
def get_my_reports(
    user: CurrentUser,
    db: DbSession,
):
    """
    Get all reports for the authenticated user.
    - Patients: Returns their own reports
    - Doctors: Returns reports for all assigned patients
    Each report includes patient_name for easy identification.
    """
    reports = report_service.get_all_my_reports(
        db=db,
        user_id=user.user_id,
        user_role=user.role,
    )

    return ReportListResponse(total=len(reports), reports=reports)


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

    # Log upload activity
    await report_service.log_activity(
        mongo_db=mongo_db,
        report_id=report_id,
        patient_id=result.patient_id,
        user_id=user.user_id,
        user_role=user.role,
        activity_type="upload",
        status="completed",
        metadata={
            "file_name": result.file_name,
            "file_size_bytes": result.file_size_bytes,
            "content_type": result.content_type,
        },
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
async def get_download_url(
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
    mongo_db: MongoDb,
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

    # Log download activity
    from src.schemas.reports import Report as ReportORM
    report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
    if report:
        await report_service.log_activity(
            mongo_db=mongo_db,
            report_id=report_id,
            patient_id=report.patient_id,
            user_id=user.user_id,
            user_role=user.role,
            activity_type="download",
            status="completed",
        )

    return DownloadUrlResponse(**result)


@router.get("/{report_id}/activity", response_model=ReportActivityResponse)
async def get_report_activity(
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Get complete activity history for a report.

    Returns all events related to the report including:
    - Upload event (when report was uploaded)
    - Analysis attempts (AI diabetes analysis with timestamps and status)
    - Extraction attempts (report data extraction with timestamps and status)
    - Explanation requests (user-requested explanations for selected text)
    - Download events (when report was downloaded)

    Access control:
    - Patients can view activity for their own reports
    - Doctors can view activity for assigned patients' reports
    """
    result = await report_service.get_report_activity(
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
        report_id=report_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or you are not authorized to view its activity."
        )

    return result


@router.post("/{report_id}/explain", status_code=status.HTTP_200_OK)
async def request_explanation(
    report_id: str,
    request: ExplanationRequest,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Log a user's request for explanation of selected text from a report.

    This endpoint tracks when users highlight text and request AI explanations,
    useful for understanding user engagement and report complexity.

    Access control:
    - Patients can request explanations for their own reports
    - Doctors can request explanations for assigned patients' reports

    Note: This endpoint only logs the request. For AI-generated explanations,
    use the /ai/ask endpoint or the chat system.
    """
    from src.schemas.reports import Report as ReportORM

    # Verify report exists and user has access
    report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    # Access control
    from src.reports.services import check_patient_access
    if not check_patient_access(db, user.user_id, user.role, report.patient_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this report"
        )

    # Log explanation request activity
    await report_service.log_activity(
        mongo_db=mongo_db,
        report_id=report_id,
        patient_id=report.patient_id,
        user_id=user.user_id,
        user_role=user.role,
        activity_type="explanation_request",
        status="completed",
        metadata={
            "selected_text": request.selected_text,
            "question": request.question,
        },
    )

    return {
        "status": "logged",
        "message": "Explanation request logged successfully"
    }


@router.get("/{report_id}/analysis-status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Check if a report has been analyzed.

    Returns:
    - Whether the report has been analyzed
    - Total number of analyses performed
    - Latest analysis ID and date

    Use this endpoint to:
    - Determine if analysis needs to be run
    - Check if re-analysis is needed
    - Get the latest analysis ID for retrieval

    Access control:
    - Patients can check their own reports
    - Doctors can check assigned patients' reports
    """
    result = await report_service.get_analysis_status(
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
        report_id=report_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or you are not authorized to view it."
        )

    return result


@router.get("/{report_id}/analyses", response_model=AnalysesListResponse)
async def get_all_analyses(
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Get all analysis versions for a report.

    Returns a list of all analyses performed on this report, including:
    - Extraction analyses (medical data extraction)
    - Diabetes prediction analyses (legacy)

    Each analysis includes:
    - MongoDB document ID
    - Analysis type and status
    - Processing time
    - Key results (report type, prediction, etc.)
    - Created timestamp

    Sorted by date (newest first).

    Use cases:
    - View analysis history
    - Compare results over time
    - Debug failed analyses
    - Retrieve specific analysis versions

    Access control:
    - Patients can view analyses of their own reports
    - Doctors can view analyses of assigned patients' reports
    """
    result = await report_service.get_all_analyses(
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
        report_id=report_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or you are not authorized to view it."
        )

    return result


@router.get("/{report_id}/analyses/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis_by_id(
    report_id: str,
    analysis_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Get complete analysis data for a specific analysis.

    Returns the full MongoDB document including:
    - Raw extracted text from the report
    - Extracted data (for extraction analyses):
      * Patient information
      * Vital signs
      * Lab results
      * Diagnoses
      * Medications
      * Recommendations
    - Diabetes prediction data (for diabetes analyses):
      * Extracted features
      * Prediction results
      * AI-generated narrative
    - Processing metadata (status, time, errors)

    Use cases:
    - Display extracted lab results
    - Show diabetes prediction details
    - View AI analysis explanations
    - Debug failed analyses
    - Compare different analysis versions

    Access control:
    - Patients can view analyses of their own reports
    - Doctors can view analyses of assigned patients' reports
    """
    result = await report_service.get_analysis_by_id(
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
        report_id=report_id,
        analysis_id=analysis_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found or you are not authorized to view it."
        )

    return result
