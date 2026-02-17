# src/dashboards/analytics.py
"""Analytics service for dashboard data aggregation."""

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from src.dashboards.analytics_models import (
    AppointmentAnalytics,
    DoctorAnalyticsResponse,
    DoctorAppointmentAnalytics,
    MonthlyCount,
    NextAppointment,
    PatientAnalyticsResponse,
    PatientDemographics,
    TypeCount,
    VitalSigns,
)
from src.schemas.cases import Case as CaseORM
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Appointment, Assignment, Patient, User


def get_patient_analytics(db: Session, patient_id: str) -> PatientAnalyticsResponse:
    """
    Get analytics data for patient dashboard.
    
    Args:
        db: Database session
        patient_id: Patient's user ID
        
    Returns:
        PatientAnalyticsResponse with appointment stats, medications, vitals, and trends
    """
    # Get patient profile for medications and vitals
    user = db.query(User).filter(User.id == patient_id).first()
    if not user or not user.patient_profile:
        raise ValueError("Patient not found")
    
    patient = user.patient_profile
    
    # ========================================================================
    # Appointment Analytics
    # ========================================================================
    appointments_query = db.query(Appointment).filter(Appointment.patient_user_id == patient_id)
    all_appointments = appointments_query.all()
    
    now = datetime.now(timezone.utc)
    
    # Count by status
    total = len(all_appointments)
    upcoming = sum(1 for a in all_appointments if a.status == "Scheduled" and a.start_time > now)
    completed = sum(1 for a in all_appointments if a.status == "Completed")
    cancelled = sum(1 for a in all_appointments if a.status == "Cancelled")
    no_show = sum(1 for a in all_appointments if a.status == "No-show")
    
    # Group by month (last 6 months)
    six_months_ago = now - timedelta(days=180)
    monthly_counts: dict[str, int] = defaultdict(int)
    for appt in all_appointments:
        if appt.created_at >= six_months_ago:
            month_key = appt.created_at.strftime("%Y-%m")
            monthly_counts[month_key] += 1
    
    by_month = [
        MonthlyCount(month=month, count=count)
        for month, count in sorted(monthly_counts.items())
    ]
    
    # Group by type
    type_counts: dict[str, int] = defaultdict(int)
    for appt in all_appointments:
        type_counts[appt.type] += 1
    
    by_type = [
        TypeCount(type=type_name, count=count)
        for type_name, count in type_counts.items()
    ]
    
    # Next upcoming appointment
    next_appt = None
    upcoming_appts = [
        a for a in all_appointments
        if a.status == "Scheduled" and a.start_time > now
    ]
    if upcoming_appts:
        next_appt_orm = min(upcoming_appts, key=lambda a: a.start_time)
        # Get doctor name
        doctor = db.query(User).filter(User.id == next_appt_orm.doctor_user_id).first()
        next_appt = NextAppointment(
            id=next_appt_orm.id,
            doctor_name=doctor.name if doctor else "Unknown",
            start_time=next_appt_orm.start_time,
            type=next_appt_orm.type,
            reason=next_appt_orm.reason
        )
    
    appointment_analytics = AppointmentAnalytics(
        total=total,
        upcoming=upcoming,
        completed=completed,
        cancelled=cancelled,
        no_show=no_show,
        by_month=by_month,
        by_type=by_type,
        next_appointment=next_appt
    )
    
    # ========================================================================
    # Medications from patient profile
    # ========================================================================
    medications = patient.current_medications or []
    
    # ========================================================================
    # Vital Signs from patient profile
    # ========================================================================
    vitals = VitalSigns(
        blood_group=patient.blood_group,
        height_cm=patient.height_cm,
        weight_kg=patient.weight_kg
    )
    
    # ========================================================================
    # Reports by month (last 6 months)
    # ========================================================================
    reports_query = db.query(ReportORM).filter(
        ReportORM.patient_id == patient_id,
        ReportORM.created_at >= six_months_ago
    )
    all_reports = reports_query.all()
    
    reports_monthly: dict[str, int] = defaultdict(int)
    for report in all_reports:
        month_key = report.created_at.strftime("%Y-%m")
        reports_monthly[month_key] += 1
    
    reports_by_month = [
        MonthlyCount(month=month, count=count)
        for month, count in sorted(reports_monthly.items())
    ]
    
    # ========================================================================
    # Cases by month (last 6 months)
    # ========================================================================
    cases_query = db.query(CaseORM).filter(
        CaseORM.patient_id == patient_id,
        CaseORM.created_at >= six_months_ago
    )
    all_cases = cases_query.all()
    
    cases_monthly: dict[str, int] = defaultdict(int)
    for case in all_cases:
        month_key = case.created_at.strftime("%Y-%m")
        cases_monthly[month_key] += 1
    
    cases_by_month = [
        MonthlyCount(month=month, count=count)
        for month, count in sorted(cases_monthly.items())
    ]
    
    return PatientAnalyticsResponse(
        appointments=appointment_analytics,
        medications=medications,
        vitals=vitals,
        reports_by_month=reports_by_month,
        cases_by_month=cases_by_month
    )


def get_doctor_analytics(db: Session, doctor_id: str) -> DoctorAnalyticsResponse:
    """
    Get analytics data for doctor dashboard.
    
    Args:
        db: Database session
        doctor_id: Doctor's user ID
        
    Returns:
        DoctorAnalyticsResponse with appointment stats, patient demographics, and case trends
    """
    # ========================================================================
    # Appointment Analytics
    # ========================================================================
    appointments_query = db.query(Appointment).filter(Appointment.doctor_user_id == doctor_id)
    all_appointments = appointments_query.all()
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = now + timedelta(days=7)
    
    # Count by status
    total = len(all_appointments)
    today = sum(1 for a in all_appointments if today_start <= a.start_time < today_end)
    upcoming_week = sum(1 for a in all_appointments if a.status == "Scheduled" and now < a.start_time <= week_end)
    completed = sum(1 for a in all_appointments if a.status == "Completed")
    cancelled = sum(1 for a in all_appointments if a.status == "Cancelled")
    no_show = sum(1 for a in all_appointments if a.status == "No-show")
    
    # Completion rate
    non_cancelled = total - cancelled
    completion_rate = (completed / non_cancelled * 100) if non_cancelled > 0 else 0.0
    
    # Group by month (last 6 months)
    six_months_ago = now - timedelta(days=180)
    monthly_counts: dict[str, int] = defaultdict(int)
    for appt in all_appointments:
        if appt.created_at >= six_months_ago:
            month_key = appt.created_at.strftime("%Y-%m")
            monthly_counts[month_key] += 1
    
    by_month = [
        MonthlyCount(month=month, count=count)
        for month, count in sorted(monthly_counts.items())
    ]
    
    # Group by type
    type_counts: dict[str, int] = defaultdict(int)
    for appt in all_appointments:
        type_counts[appt.type] += 1
    
    by_type = [
        TypeCount(type=type_name, count=count)
        for type_name, count in type_counts.items()
    ]
    
    appointment_analytics = DoctorAppointmentAnalytics(
        total=total,
        today=today,
        upcoming_week=upcoming_week,
        completed=completed,
        cancelled=cancelled,
        no_show=no_show,
        by_month=by_month,
        by_type=by_type,
        completion_rate=round(completion_rate, 1)
    )
    
    # ========================================================================
    # Patient Demographics (for assigned patients)
    # ========================================================================
    # Get all assigned patient IDs
    assigned_patient_ids = db.query(Assignment.patient_user_id).filter(
        Assignment.doctor_user_id == doctor_id,
        Assignment.is_active == True
    ).all()
    patient_ids = [p[0] for p in assigned_patient_ids]
    
    # Get patient profiles
    patients = db.query(Patient).filter(Patient.user_id.in_(patient_ids)).all() if patient_ids else []
    
    # Gender distribution
    gender_counts: dict[str, int] = defaultdict(int)
    for patient in patients:
        gender_counts[patient.gender.lower()] += 1
    
    by_gender = [
        TypeCount(type=gender, count=count)
        for gender, count in gender_counts.items()
    ]
    
    # Age group distribution
    age_group_counts: dict[str, int] = defaultdict(int)
    for patient in patients:
        age = (datetime.now().date() - patient.date_of_birth).days // 365
        if age < 18:
            age_group = "0-17"
        elif age < 31:
            age_group = "18-30"
        elif age < 46:
            age_group = "31-45"
        elif age < 61:
            age_group = "46-60"
        else:
            age_group = "60+"
        age_group_counts[age_group] += 1
    
    by_age_group = [
        TypeCount(type=age_group, count=count)
        for age_group, count in age_group_counts.items()
    ]
    
    patient_demographics = PatientDemographics(
        by_gender=by_gender,
        by_age_group=by_age_group
    )
    
    # ========================================================================
    # Cases by month and type
    # ========================================================================
    cases_query = db.query(CaseORM).filter(
        CaseORM.doctor_id == doctor_id,
        CaseORM.created_at >= six_months_ago
    )
    all_cases = cases_query.all()
    
    cases_monthly: dict[str, int] = defaultdict(int)
    for case in all_cases:
        month_key = case.created_at.strftime("%Y-%m")
        cases_monthly[month_key] += 1
    
    cases_by_month = [
        MonthlyCount(month=month, count=count)
        for month, count in sorted(cases_monthly.items())
    ]
    
    # Cases by type
    case_type_counts: dict[str, int] = defaultdict(int)
    for case in all_cases:
        case_type_counts[case.case_type] += 1
    
    cases_by_type = [
        TypeCount(type=case_type, count=count)
        for case_type, count in case_type_counts.items()
    ]
    
    # ========================================================================
    # Reports analyzed vs pending
    # ========================================================================
    reports_query = db.query(ReportORM).join(
        Assignment,
        and_(
            ReportORM.patient_id == Assignment.patient_user_id,
            Assignment.doctor_user_id == doctor_id,
            Assignment.is_active == True
        )
    )
    all_reports = reports_query.all()
    
    reports_analyzed = sum(1 for r in all_reports if r.mongo_analysis_id is not None)
    reports_pending = sum(1 for r in all_reports if r.mongo_analysis_id is None)
    
    return DoctorAnalyticsResponse(
        appointments=appointment_analytics,
        patient_demographics=patient_demographics,
        cases_by_month=cases_by_month,
        cases_by_type=cases_by_type,
        reports_analyzed=reports_analyzed,
        reports_pending=reports_pending
    )
