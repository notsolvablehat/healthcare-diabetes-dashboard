# src/dashboards/services.py
"""Business logic for dashboard endpoints."""

from datetime import datetime

from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.dashboards.models import (
    AIStats,
    AlertItem,
    BloodPressureReading,
    CasesSummary,
    CaseSummaryItem,
    CaseWithPatient,
    DoctorDashboardResponse,
    DoctorSummaryItem,
    DoctorUserInfo,
    GlucoseReading,
    HealthCharts,
    PaginationInfo,
    PatientDashboardResponse,
    PatientStats,
    PatientSummaryItem,
    PatientUserInfo,
    PendingApprovalItem,
    ReportsSummary,
    ReportSummaryItem,
    WeightReading,
)
from src.schemas.cases import Case as CaseORM
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Assignment, Doctor, Patient, User


def _calculate_pagination(total: int, page: int, limit: int) -> PaginationInfo:
    """Helper to calculate pagination info."""
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    return PaginationInfo(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages
    )


async def get_patient_dashboard(
    db: Session,
    mongo_db: AsyncDatabase,
    user_id: str,
    cases_page: int = 1,
    cases_limit: int = 5,
    reports_page: int = 1,
    reports_limit: int = 5,
) -> PatientDashboardResponse:
    """Aggregate all data for patient dashboard."""

    # Get user info
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    user_info = PatientUserInfo(
        user_id=user_id,
        name=user.name,
        email=user.email,
        last_profile_update=user.patient_profile.updated_at if hasattr(user.patient_profile, 'updated_at') else None
    )

    # Get assigned doctors
    stmt = (
        select(User, Doctor)
        .join(Doctor, User.id == Doctor.user_id)
        .join(Assignment, Assignment.doctor_user_id == Doctor.user_id)
        .filter(
            Assignment.patient_user_id == user_id,
            Assignment.is_active == True
        )
    )
    doctor_results = db.execute(stmt).all()
    assigned_doctors = [
        DoctorSummaryItem(
            doctor_id=doc.doctor_id,
            name=user_row.name,
            email=user_row.email,
            specialisation=doc.specialisation
        )
        for user_row, doc in doctor_results
    ]

    # Get cases summary and paginated list
    cases_query = db.query(CaseORM).filter(CaseORM.patient_id == user_id)
    total_cases = cases_query.count()

    # Count by status
    status_counts = db.query(
        CaseORM.status, func.count(CaseORM.id)
    ).filter(CaseORM.patient_id == user_id).group_by(CaseORM.status).all()

    status_map = {status: count for status, count in status_counts}

    # Paginated cases
    cases_offset = (cases_page - 1) * cases_limit
    cases_list = cases_query.order_by(CaseORM.created_at.desc()).offset(cases_offset).limit(cases_limit).all()

    cases = CasesSummary(
        open=status_map.get("open", 0),
        under_review=status_map.get("under_review", 0),
        closed=status_map.get("closed", 0),
        approved=status_map.get("approved_by_doctor", 0),
        total=total_cases,
        items=[
            CaseSummaryItem(
                case_id=c.case_id,
                status=c.status,
                chief_complaint=c.chief_complaint,
                created_at=c.created_at
            )
            for c in cases_list
        ],
        pagination=_calculate_pagination(total_cases, cases_page, cases_limit)
    )

    # Get reports summary
    reports_query = db.query(ReportORM).filter(ReportORM.patient_id == user_id)
    total_reports = reports_query.count()

    reports_offset = (reports_page - 1) * reports_limit
    reports_list = reports_query.order_by(ReportORM.created_at.desc()).offset(reports_offset).limit(reports_limit).all()

    reports = ReportsSummary(
        total=total_reports,
        items=[
            ReportSummaryItem(
                report_id=r.id,
                file_name=r.file_name,
                file_type=r.file_type,
                created_at=r.created_at
            )
            for r in reports_list
        ],
        pagination=_calculate_pagination(total_reports, reports_page, reports_limit)
    )

    # Get health charts from MongoDB (case vital signs and lab results)
    health_charts = await _get_patient_health_charts(mongo_db, user_id)

    # Get alerts
    alerts = _get_patient_alerts(user)

    # Get AI stats from MongoDB
    ai_stats = await _get_ai_stats(mongo_db, user_id)

    return PatientDashboardResponse(
        user_info=user_info,
        assigned_doctors=assigned_doctors,
        cases=cases,
        reports=reports,
        health_charts=health_charts,
        alerts=alerts,
        ai_stats=ai_stats
    )


async def get_doctor_dashboard(
    db: Session,
    mongo_db: AsyncDatabase,
    user_id: str,
    cases_page: int = 1,
    cases_limit: int = 10,
) -> DoctorDashboardResponse:
    """Aggregate all data for doctor dashboard."""

    # Get user/doctor info
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.doctor_profile:
        raise ValueError("Doctor not found")

    doctor = user.doctor_profile
    user_info = DoctorUserInfo(
        user_id=user_id,
        name=user.name,
        email=user.email,
        specialisation=doctor.specialisation
    )

    # Get patient stats
    active_patients = db.query(Assignment).filter(
        Assignment.doctor_user_id == user_id,
        Assignment.is_active == True
    ).count()

    max_patients = doctor.max_patients or 10
    load_percentage = (active_patients / max_patients * 100) if max_patients > 0 else 0

    patient_stats = PatientStats(
        active=active_patients,
        max=max_patients,
        load_percentage=round(load_percentage, 1)
    )

    # Get cases with patient names
    cases_query = (
        db.query(CaseORM, User)
        .join(User, CaseORM.patient_id == User.id)
        .filter(CaseORM.doctor_id == user_id)
    )
    total_cases = cases_query.count()

    # Count by status
    status_counts = db.query(
        CaseORM.status, func.count(CaseORM.id)
    ).filter(CaseORM.doctor_id == user_id).group_by(CaseORM.status).all()

    status_map = {status: count for status, count in status_counts}

    # Paginated cases
    cases_offset = (cases_page - 1) * cases_limit
    cases_list = cases_query.order_by(CaseORM.created_at.desc()).offset(cases_offset).limit(cases_limit).all()

    cases = CasesSummary(
        open=status_map.get("open", 0),
        under_review=status_map.get("under_review", 0),
        closed=status_map.get("closed", 0),
        approved=status_map.get("approved_by_doctor", 0),
        total=total_cases,
        items=[
            CaseSummaryItem(
                case_id=c.case_id,
                status=c.status,
                chief_complaint=c.chief_complaint,
                created_at=c.created_at
            )
            for c, _ in cases_list
        ],
        pagination=_calculate_pagination(total_cases, cases_page, cases_limit)
    )

    # Get pending approvals
    pending_query = (
        db.query(CaseORM, User)
        .join(User, CaseORM.patient_id == User.id)
        .filter(
            CaseORM.doctor_id == user_id,
            CaseORM.status == "under_review"
        )
        .order_by(CaseORM.created_at.desc())
        .limit(10)
    )
    pending_list = pending_query.all()

    pending_approvals = [
        PendingApprovalItem(
            case_id=c.case_id,
            patient_name=patient.name,
            patient_id=c.patient_id,
            chief_complaint=c.chief_complaint,
            created_at=c.created_at
        )
        for c, patient in pending_list
    ]

    # Get alerts for doctor
    alerts = _get_doctor_alerts(db, user_id)

    # Get AI stats from MongoDB
    ai_stats = await _get_ai_stats(mongo_db, user_id)

    return DoctorDashboardResponse(
        user_info=user_info,
        patient_stats=patient_stats,
        cases=cases,
        pending_approvals=pending_approvals,
        alerts=alerts,
        ai_stats=ai_stats
    )


async def _get_patient_health_charts(mongo_db: AsyncDatabase, patient_id: str) -> HealthCharts:
    """Extract health metrics from MongoDB cases for charts."""
    weight_history: list[WeightReading] = []
    glucose_readings: list[GlucoseReading] = []
    blood_pressure: list[BloodPressureReading] = []

    # Query MongoDB cases collection for this patient
    cases_collection = mongo_db["cases"]
    cursor = cases_collection.find(
        {"patient_id": patient_id},
        {"objective": 1, "created_at": 1}
    ).sort("created_at", -1).limit(30)

    async for case_doc in cursor:
        objective = case_doc.get("objective", {})
        if not objective:
            continue

        created_at = case_doc.get("created_at")
        if isinstance(created_at, datetime):
            reading_date = created_at.date()
        else:
            continue

        vital_signs = objective.get("vital_signs", {})
        if vital_signs:
            # Weight
            if vital_signs.get("weight"):
                weight_history.append(WeightReading(
                    date=reading_date,
                    value=float(vital_signs["weight"])
                ))

            # Blood pressure
            if vital_signs.get("systolic_bp") and vital_signs.get("diastolic_bp"):
                blood_pressure.append(BloodPressureReading(
                    date=reading_date,
                    systolic=int(vital_signs["systolic_bp"]),
                    diastolic=int(vital_signs["diastolic_bp"])
                ))

        # Lab results for glucose
        lab_results = objective.get("lab_results", [])
        for lab in lab_results:
            test_name = lab.get("test_name", "").lower()
            if "glucose" in test_name or "blood sugar" in test_name:
                try:
                    value = float(lab.get("value", 0))
                    if "fasting" in test_name:
                        glucose_readings.append(GlucoseReading(
                            date=reading_date,
                            fasting=value
                        ))
                    else:
                        glucose_readings.append(GlucoseReading(
                            date=reading_date,
                            post_meal=value
                        ))
                except (ValueError, TypeError):
                    pass

    return HealthCharts(
        weight_history=weight_history[:10],  # Last 10
        glucose_readings=glucose_readings[:10],
        blood_pressure=blood_pressure[:10],
        last_profile_update=None  # Could be tracked if we add updated_at
    )


def _get_patient_alerts(user: User) -> list[AlertItem]:
    """Generate alerts for patient based on their profile."""
    alerts: list[AlertItem] = []

    if user.patient_profile:
        # Critical allergies
        allergies = user.patient_profile.allergies or []
        if allergies and allergies != ["None"]:
            alerts.append(AlertItem(
                type="warning",
                title="Allergies on Record",
                message=f"Remember: You have allergies to {', '.join(allergies[:3])}."
            ))

        # Medical history - diabetes
        medical_history = user.patient_profile.medical_history or []
        for condition in medical_history:
            if "diabetes" in condition.lower():
                alerts.append(AlertItem(
                    type="info",
                    title="Diabetes Tracking",
                    message="Track your glucose readings regularly. Upload reports for AI analysis."
                ))
                break

    return alerts


def _get_doctor_alerts(db: Session, doctor_id: str) -> list[AlertItem]:
    """Generate alerts for doctor."""
    alerts: list[AlertItem] = []

    # Count pending approvals
    pending_count = db.query(CaseORM).filter(
        CaseORM.doctor_id == doctor_id,
        CaseORM.status == "under_review"
    ).count()

    if pending_count > 0:
        alerts.append(AlertItem(
            type="warning",
            title="Pending Approvals",
            message=f"You have {pending_count} case(s) awaiting your approval."
        ))

    return alerts


async def _get_ai_stats(mongo_db: AsyncDatabase, user_id: str) -> AIStats:
    """Get AI usage stats from MongoDB."""
    chats_collection = mongo_db["chats"]
    chat_count = await chats_collection.count_documents({"user_id": user_id})

    analyses_collection = mongo_db["report_analyses"]
    analyses_count = await analyses_collection.count_documents({"user_id": user_id})

    return AIStats(
        chat_count=chat_count,
        analyses_count=analyses_count
    )
