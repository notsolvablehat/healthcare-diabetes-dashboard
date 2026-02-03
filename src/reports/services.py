import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from supabase import Client

from src.reports.models import (
    AvailablePatient,
    AvailablePatientsResponse,
    FileType,
    ReportResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Assignment, Patient, User

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
    def get_available_patients(self, db: Session, doctor_id: str) -> AvailablePatientsResponse:
        """
        Get list of patients that a doctor can upload reports for.
        Returns only active assignments.
        """
        # Query for active patient assignments
        stmt = (
            select(User, Patient)
            .join(Patient, Patient.user_id == User.id)
            .join(Assignment, Assignment.patient_user_id == Patient.user_id)
            .filter(
                Assignment.doctor_user_id == doctor_id,
                Assignment.is_active == True
            )
            .order_by(User.name)
        )
        
        results = db.execute(stmt).all()
        
        patients = []
        for user_row, patient_row in results:
            patients.append(
                AvailablePatient(
                    user_id=user_row.id,
                    patient_id=patient_row.patient_id,
                    name=user_row.name,
                    email=user_row.email,
                    gender=patient_row.gender,
                    date_of_birth=patient_row.date_of_birth,
                )
            )
        
        return AvailablePatientsResponse(
            total=len(patients),
            patients=patients,
        )

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
            if user_role == "doctor":
                raise PermissionError(
                    f"You do not have access to upload reports for this patient. "
                    f"The patient (ID: {request.patient_id}) is not assigned to you. "
                    f"Please check your assigned patients using GET /reports/available-patients"
                )
            else:
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
            Assignment.is_active
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

    def get_all_my_reports(
        self,
        db: Session,
        user_id: str,
        user_role: str,
    ) -> list[ReportResponse]:
        """
        Get all reports for the authenticated user.
        - Patients: Returns their own reports with their name
        - Doctors: Returns reports for all assigned patients with patient names
        """
        from src.schemas.users.users import Assignment, User

        if user_role == "patient":
            # Get patient's own reports
            reports = db.query(ReportORM).filter(ReportORM.patient_id == user_id).all()

            # Get patient name
            patient_user = db.query(User).filter(User.id == user_id).first()
            patient_name = patient_user.name if patient_user else None

            # Build response with patient name
            report_list = []
            for report in reports:
                report_data = ReportResponse.model_validate(report)
                report_data.patient_name = patient_name
                report_list.append(report_data)

            return report_list

        elif user_role == "doctor":
            # Get all assigned patients
            assignments = db.query(Assignment).filter(
                Assignment.doctor_user_id == user_id,
                Assignment.is_active
            ).all()

            patient_ids = [a.patient_user_id for a in assignments]

            if not patient_ids:
                return []

            # Get reports with patient names via JOIN
            results = db.query(ReportORM, User.name).join(
                User, ReportORM.patient_id == User.id
            ).filter(
                ReportORM.patient_id.in_(patient_ids)
            ).order_by(ReportORM.created_at.desc()).all()

            # Build response with patient names
            report_list = []
            for report_orm, patient_name in results:
                report_data = ReportResponse.model_validate(report_orm)
                report_data.patient_name = patient_name
                report_list.append(report_data)

            return report_list

        # For other roles (admin, etc.), return empty list
        return []


    async def log_activity(
        self,
        mongo_db,
        report_id: str,
        patient_id: str,
        user_id: str,
        user_role: str,
        activity_type: str,
        status: str = "completed",
        metadata: dict | None = None,
        error_message: str | None = None,
    ) -> str:
        """
        Log an activity for a report in MongoDB.
        Returns the inserted activity log ID.

        Activity types:
        - upload: Report file uploaded
        - analysis: AI diabetes analysis performed
        - extraction: Report data extraction performed
        - explanation_request: User requested explanation for selected text
        - download: Report file downloaded
        """
        from src.schemas.mongo import ReportActivityLog

        activity_log = ReportActivityLog(
            report_id=report_id,
            patient_id=patient_id,
            user_id=user_id,
            user_role=user_role,
            activity_type=activity_type,
            status=status,
            metadata=metadata,
            error_message=error_message,
        )

        result = await mongo_db.report_activities.insert_one(
            activity_log.model_dump()
        )

        return str(result.inserted_id)

    async def get_analysis_status(
        self,
        db: Session,
        mongo_db,
        user_id: str,
        user_role: str,
        report_id: str,
    ) -> dict | None:
        """
        Check if a report has been analyzed and get status.
        """
        from src.reports.models import AnalysisStatusResponse

        # Check if report exists and user has access
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
        if not report:
            return None

        if not check_patient_access(db, user_id, user_role, report.patient_id):
            return None

        # Count all analyses for this report
        analyses_count = await mongo_db.report_analysis.count_documents(
            {"report_id": report_id}
        )

        # Get latest analysis
        latest_analysis = await mongo_db.report_analysis.find_one(
            {"report_id": report_id},
            sort=[("created_at", -1)]
        )

        latest_id = None
        latest_date = None
        if latest_analysis:
            latest_id = str(latest_analysis["_id"])
            latest_date = latest_analysis.get("created_at")

        return AnalysisStatusResponse(
            report_id=report_id,
            is_analyzed=analyses_count > 0,
            analysis_count=analyses_count,
            latest_analysis_id=latest_id,
            latest_analysis_date=latest_date,
        ).model_dump()

    async def get_all_analyses(
        self,
        db: Session,
        mongo_db,
        user_id: str,
        user_role: str,
        report_id: str,
    ) -> dict | None:
        """
        Get all analyses performed on a report.
        """
        from src.reports.models import AnalysesListResponse, AnalysisSummary

        # Check if report exists and user has access
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
        if not report:
            return None

        if not check_patient_access(db, user_id, user_role, report.patient_id):
            return None

        # Fetch all analyses, sorted by created_at (newest first)
        cursor = mongo_db.report_analysis.find(
            {"report_id": report_id}
        ).sort("created_at", -1)

        analyses_raw = await cursor.to_list(length=None)

        # Convert to AnalysisSummary models
        analyses = []
        for analysis in analyses_raw:
            # Determine analysis type
            analysis_type = None
            if "extracted_data" in analysis:
                analysis_type = "extraction"
            elif "prediction" in analysis:
                analysis_type = "diabetes_analysis"

            # Extract relevant fields based on type
            summary = AnalysisSummary(
                mongo_id=str(analysis["_id"]),
                status=analysis.get("status", "completed"),
                analysis_type=analysis_type,
                created_at=analysis.get("created_at"),
                processing_time_ms=analysis.get("processing_time_ms"),
            )

            # Add type-specific fields
            if analysis_type == "extraction":
                extracted = analysis.get("extracted_data", {})
                summary.report_type = extracted.get("report_type")
                summary.lab_results_count = len(extracted.get("lab_results", []))
                summary.medications_count = len(extracted.get("medications", []))
            elif analysis_type == "diabetes_analysis":
                prediction = analysis.get("prediction", {})
                summary.prediction_label = prediction.get("label")
                summary.prediction_confidence = prediction.get("confidence")

            analyses.append(summary)

        return AnalysesListResponse(
            report_id=report_id,
            total_analyses=len(analyses),
            analyses=analyses,
        ).model_dump()

    async def get_analysis_by_id(
        self,
        db: Session,
        mongo_db,
        user_id: str,
        user_role: str,
        report_id: str,
        analysis_id: str,
    ) -> dict | None:
        """
        Get detailed data for a specific analysis.
        """
        from bson import ObjectId

        from src.reports.models import AnalysisDetailResponse

        # Check if report exists and user has access
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
        if not report:
            return None

        if not check_patient_access(db, user_id, user_role, report.patient_id):
            return None

        # Fetch specific analysis from MongoDB
        try:
            analysis = await mongo_db.report_analysis.find_one(
                {"_id": ObjectId(analysis_id), "report_id": report_id}
            )
        except Exception:
            # Invalid ObjectId format
            return None

        if not analysis:
            return None

        # Build response with all available data
        return AnalysisDetailResponse(
            analysis_id=str(analysis["_id"]),
            report_id=analysis.get("report_id"),
            patient_id=analysis.get("patient_id"),
            status=analysis.get("status", "completed"),
            created_at=analysis.get("created_at"),
            processing_time_ms=analysis.get("processing_time_ms"),
            raw_text=analysis.get("raw_text"),
            extracted_data=analysis.get("extracted_data"),
            extracted_features=analysis.get("extracted_features"),
            prediction=analysis.get("prediction"),
            narrative=analysis.get("narrative"),
            error=analysis.get("error"),
        ).model_dump()

    async def get_report_activity(
        self,
        db: Session,
        mongo_db,
        user_id: str,
        user_role: str,
        report_id: str,
    ) -> dict | None:
        """
        Get all activity logs for a report.
        Returns activity history with summary counts.
        """
        from src.reports.models import ActivityEvent, ReportActivityResponse

        # First check if report exists and user has access
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
        if not report:
            return None

        if not check_patient_access(db, user_id, user_role, report.patient_id):
            return None

        # Fetch all activities from MongoDB, sorted by timestamp (newest first)
        cursor = mongo_db.report_activities.find(
            {"report_id": report_id}
        ).sort("timestamp", -1)

        activities_raw = await cursor.to_list(length=None)

        # Convert to ActivityEvent models
        activities = [
            ActivityEvent(
                activity_type=act["activity_type"],
                user_id=act["user_id"],
                user_role=act["user_role"],
                status=act["status"],
                timestamp=act["timestamp"],
                metadata=act.get("metadata"),
                error_message=act.get("error_message"),
            )
            for act in activities_raw
        ]

        # Calculate summary counts
        upload_count = sum(1 for a in activities if a.activity_type == "upload")
        analysis_count = sum(1 for a in activities if a.activity_type == "analysis")
        extraction_count = sum(1 for a in activities if a.activity_type == "extraction")
        explanation_count = sum(1 for a in activities if a.activity_type == "explanation_request")
        download_count = sum(1 for a in activities if a.activity_type == "download")

        return ReportActivityResponse(
            report_id=report_id,
            patient_id=report.patient_id,
            total_activities=len(activities),
            activities=activities,
            upload_count=upload_count,
            analysis_count=analysis_count,
            extraction_count=extraction_count,
            explanation_count=explanation_count,
            download_count=download_count,
        ).model_dump()


report_service = ReportService()
