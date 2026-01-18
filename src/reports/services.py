import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from supabase import Client

from src.reports.models import (
    FileType,
    ReportResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Assignment

# Bucket name for medical reports
BUCKET_NAME = "medical-reports"

# Allowed MIME types
ALLOWED_CONTENT_TYPES = {
    "application/pdf": FileType.PDF,
    "image/png": FileType.IMAGE,
    "image/jpeg": FileType.IMAGE,
    "image/jpg": FileType.IMAGE,
    "image/webp": FileType.IMAGE,
}


def get_file_type(content_type: str) -> FileType:
    """Get FileType enum from content type."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}. Allowed: {list(ALLOWED_CONTENT_TYPES.keys())}")
    return ALLOWED_CONTENT_TYPES[content_type]


def check_patient_access(db: Session, user_id: str, user_role: str, patient_id: str) -> bool:
    """
    Check if a user can access a patient's reports.
    - Patients can access their own reports
    - Doctors can access reports of assigned patients
    """
    # Patient accessing their own reports
    if user_role == "patient" and user_id == patient_id:
        return True

    # Doctor accessing assigned patient's reports
    if user_role == "doctor":
        stmt = select(Assignment).filter(
            Assignment.doctor_user_id == user_id,
            Assignment.patient_user_id == patient_id,
            Assignment.is_active
        )
        assignment = db.scalars(stmt).first()
        return assignment is not None

    return False


class ReportService:
    def generate_upload_url(
        self,
        supabase: Client,
        db: Session,
        user_id: str,
        user_role: str,
        request: UploadUrlRequest,
    ) -> UploadUrlResponse:
        """
        Generate a signed upload URL for Supabase Storage.
        Also creates a pending report record in the database.
        """
        # Validate content type
        file_type = get_file_type(request.content_type)

        # Access control check
        if not check_patient_access(db, user_id, user_role, request.patient_id):
            raise PermissionError("You do not have access to upload reports for this patient.")

        # Generate unique storage path
        report_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_extension = request.filename.split(".")[-1] if "." in request.filename else ""
        storage_path = f"{request.patient_id}/{timestamp}_{report_id}.{file_extension}"

        # Generate signed upload URL (valid for 1 hour)
        expires_in = 3600
        signed_url_response = supabase.storage.from_(BUCKET_NAME).create_signed_upload_url(
            path=storage_path
        )

        # Create report record in database
        # Handle empty case_id as None to avoid FK violation
        case_id = request.case_id if request.case_id else None

        report = ReportORM(
            id=report_id,
            case_id=case_id,
            patient_id=request.patient_id,
            uploaded_by=user_id,
            file_name=request.filename,
            file_type=file_type.value,
            content_type=request.content_type,
            storage_path=storage_path,
            description=request.description,
            created_at=datetime.utcnow(),
        )

        try:
            db.add(report)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Check if it's a FK violation for case_id
            if "case_id" in str(e.orig):
                raise ValueError(f"Invalid case_id: '{request.case_id}' does not exist.") from e
            raise ValueError(f"Database integrity error: {e.orig}") from e

        return UploadUrlResponse(
            report_id=report_id,
            upload_url=signed_url_response["signed_url"],
            storage_path=storage_path,
            expires_in=expires_in,
        )

    def confirm_upload(
        self,
        db: Session,
        user_id: str,
        report_id: str,
        file_size_bytes: int | None = None,
    ) -> ReportResponse | None:
        """
        Confirm an upload and update file size if provided.
        """
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()

        if not report:
            return None

        # Only the uploader can confirm
        if report.uploaded_by != user_id:
            return None

        if file_size_bytes:
            report.file_size_bytes = file_size_bytes
            db.commit()
            db.refresh(report)

        # Notify assigned doctors
        from src.notifications.services import notify_new_report_uploaded
        from src.schemas.users.users import Assignment, User

        # Get patient name
        patient_user = db.query(User).filter(User.id == report.patient_id).first()
        patient_name = patient_user.name if patient_user else "Patient"

        # Get assigned doctors
        assignments = db.query(Assignment).filter(
            Assignment.patient_user_id == report.patient_id,
            Assignment.is_active == True
        ).all()

        for assignment in assignments:
            notify_new_report_uploaded(
                db, 
                assignment.doctor_user_id, 
                patient_name, 
                report.id, 
                report.file_name
            )

        return ReportResponse.model_validate(report)

    def get_reports_by_case(
        self,
        db: Session,
        user_id: str,
        user_role: str,
        case_id: str,
    ) -> list[ReportResponse]:
        """Get all reports linked to a specific case."""
        reports = db.query(ReportORM).filter(ReportORM.case_id == case_id).all()

        if not reports:
            return []

        # Check access using the first report's patient_id
        patient_id = reports[0].patient_id
        if not check_patient_access(db, user_id, user_role, patient_id):
            return []

        return [ReportResponse.model_validate(r) for r in reports]

    def get_reports_by_patient(
        self,
        db: Session,
        user_id: str,
        user_role: str,
        patient_id: str,
    ) -> list[ReportResponse]:
        """Get all reports for a specific patient."""
        if not check_patient_access(db, user_id, user_role, patient_id):
            return []

        reports = db.query(ReportORM).filter(ReportORM.patient_id == patient_id).all()
        return [ReportResponse.model_validate(r) for r in reports]

    def generate_download_url(
        self,
        supabase: Client,
        db: Session,
        user_id: str,
        user_role: str,
        report_id: str,
    ) -> dict | None:
        """Generate a signed download URL for a report."""
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()

        if not report:
            return None

        # Access control
        if not check_patient_access(db, user_id, user_role, report.patient_id):
            return None

        # Generate signed download URL (valid for 1 hour)
        expires_in = 3600
        signed_url_response = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            path=report.storage_path,
            expires_in=expires_in,
        )

        return {
            "report_id": report_id,
            "download_url": signed_url_response["signedURL"],
            "expires_in": expires_in,
        }

    def get_report_by_id(
        self,
        db: Session,
        user_id: str,
        user_role: str,
        report_id: str,
    ) -> ReportResponse | None:
        """Get a single report by ID with access control."""
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()

        if not report:
            return None

        if not check_patient_access(db, user_id, user_role, report.patient_id):
            return None

        return ReportResponse.model_validate(report)


report_service = ReportService()
