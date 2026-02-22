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
    BMIReading,
    CasesSummary,
    CaseSummaryItem,
    CaseWithPatient,
    DiabetesDashboardResponse,
    DiabetesPrediction,
    DiabetesRiskFactor,
    DiabetesTrends,
    DoctorDashboardResponse,
    DoctorSummaryItem,
    DoctorUserInfo,
    FastingGlucoseReading,
    GlucoseReading,
    HbA1cReading,
    HealthCharts,
    PaginationInfo,
    PatientDashboardResponse,
    PatientStats,
    PatientUserInfo,
    PendingApprovalItem,
    ReportsSummary,
    ReportSummaryItem,
    SpecialtyMetric,
    WeightReading,
)
from src.notifications.services import get_unread_count
from src.schemas.cases import Case as CaseORM
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Assignment, Doctor, User


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
            Assignment.is_active
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

    status_map = dict(status_counts)

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

    # Get notifications unread count
    unread_count_response = get_unread_count(db, user_id)

    return PatientDashboardResponse(
        user_info=user_info,
        assigned_doctors=assigned_doctors,
        cases=cases,
        reports=reports,
        health_charts=health_charts,
        alerts=alerts,
        ai_stats=ai_stats,
        notifications_unread=unread_count_response.count
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
        Assignment.is_active
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

    status_map = dict(status_counts)

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

    recent_patients = [
        CaseWithPatient(
            case_id=c.case_id,
            status=c.status,
            chief_complaint=c.chief_complaint,
            patient_name=patient.name,
            patient_id=c.patient_id,
            created_at=c.created_at
        )
        for c, patient in cases_list[:5]
    ]

    specialty_metrics = _get_specialty_metrics_for(doctor.specialisation)

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

    # Get notifications unread count
    unread_count_response = get_unread_count(db, user_id)

    return DoctorDashboardResponse(
        user_info=user_info,
        patient_stats=patient_stats,
        cases=cases,
        recent_patients=recent_patients,
        specialty_metrics=specialty_metrics,
        pending_approvals=pending_approvals,
        alerts=alerts,
        ai_stats=ai_stats,
        notifications_unread=unread_count_response.count
    )


def _get_specialty_metrics_for(specialisation: str | None) -> list[SpecialtyMetric]:
    spec = (specialisation or "").lower()
    if "cardiology" in spec:
        return [
            SpecialtyMetric(value='52%', label='Avg EF', sub='↑ 3% this Q', cls='up'),
            SpecialtyMetric(value='88%', label='Statin Compliance', sub='↑ 5%', cls='up'),
            SpecialtyMetric(value='128/78', label='Avg BP', sub='well controlled', cls='up'),
            SpecialtyMetric(value='0.8', label='Avg Troponin', sub='2 elevated', cls='down')
        ]
    elif "gynecology" in spec or "gynaecology" in spec:
        return [
            SpecialtyMetric(value='3.2', label='Avg AMH (ng/mL)', sub='normal range', cls='neutral'),
            SpecialtyMetric(value='68%', label='PCOS Control Rate', sub='↑ 8%', cls='up'),
            SpecialtyMetric(value='94%', label='Pap Smear Done', sub='screening target', cls='up'),
            SpecialtyMetric(value='12.4', label='Avg Hemoglobin', sub='3 below 10 g/dL', cls='down')
        ]
    elif "orthopedics" in spec or "orthopaedics" in spec:
        return [
            SpecialtyMetric(value='82%', label='Rehab Compliance', sub='↑ 6%', cls='up'),
            SpecialtyMetric(value='3.2', label='Avg Pain Score', sub='↓ 0.8 post-op', cls='up'),
            SpecialtyMetric(value='-1.8', label='Avg T-Score (DEXA)', sub='osteopenia range', cls='down'),
            SpecialtyMetric(value='18d', label='Avg Recovery', sub='under 21d target', cls='up')
        ]
    elif "pediatrics" in spec or "paediatrics" in spec:
        return [
            SpecialtyMetric(value='92%', label='Immunization Rate', sub='↑ 3%', cls='up'),
            SpecialtyMetric(value='54th', label='Avg Growth %ile', sub='on track', cls='neutral'),
            SpecialtyMetric(value='11.8', label='Avg Hemoglobin', sub='4 below 11 g/dL', cls='down'),
            SpecialtyMetric(value='3.1d', label='Avg Illness Duration', sub='↓ 0.5d', cls='up')
        ]
    else:  # General Medicine
        return [
            SpecialtyMetric(value='7.4%', label='Avg HbA1c', sub='↓ 0.3 vs last Q', cls='up'),
            SpecialtyMetric(value='134/82', label='Avg BP', sub='target <140/90', cls='up'),
            SpecialtyMetric(value='86%', label='Med Adherence', sub='↑ 4% this month', cls='up'),
            SpecialtyMetric(value='4.2', label='Avg TSH', sub='in range', cls='neutral')
        ]


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


# ============================================================================
# Diabetes Dashboard
# ============================================================================

async def get_diabetes_dashboard(
    db: Session,
    mongo_db: AsyncDatabase,
    patient_id: str,
) -> DiabetesDashboardResponse:
    """
    Get diabetes-specific dashboard data for a patient.
    
    Access is granted if:
    - Patient has "diabetes" in their medical_history, OR
    - Any AI analysis predicted diabetes for this patient
    """
    from datetime import date as date_type
    
    # Check if patient exists
    user = db.query(User).filter(User.id == patient_id).first()
    if not user:
        raise ValueError("Patient not found")
    
    # Check medical history for diabetes
    has_diabetes_in_history = False
    if user.patient_profile and user.patient_profile.medical_history:
        for condition in user.patient_profile.medical_history:
            if "diabetes" in condition.lower():
                has_diabetes_in_history = True
                break
    
    # Fetch all diabetes analyses from MongoDB
    analyses_collection = mongo_db["report_analysis"]
    
    # Get all analyses with predictions for this patient
    cursor = analyses_collection.find({
        "patient_id": patient_id,
        "prediction": {"$exists": True, "$ne": None}
    }).sort("created_at", -1)
    
    analyses = await cursor.to_list(length=100)
    
    # Check if any prediction indicates diabetes
    has_diabetes_prediction = any(
        a.get("prediction", {}).get("label") == "diabetes" 
        for a in analyses
    )
    
    # If neither condition met, return empty response
    if not has_diabetes_in_history and not has_diabetes_prediction and len(analyses) == 0:
        return DiabetesDashboardResponse(
            has_diabetes_data=False,
            message="No diabetic activity found. Upload medical reports for AI analysis to track diabetes indicators."
        )
    
    # Build prediction history
    prediction_history: list[DiabetesPrediction] = []
    diabetic_count = 0
    total_confidence = 0.0
    
    # Get report names for context
    report_ids = [a.get("report_id") for a in analyses if a.get("report_id")]
    reports_map = {}
    if report_ids:
        reports = db.query(ReportORM).filter(ReportORM.id.in_(report_ids)).all()
        reports_map = {r.id: r.file_name for r in reports}
    
    for analysis in analyses:
        prediction = analysis.get("prediction", {})
        if prediction:
            pred_label = prediction.get("label", "unknown")
            pred_confidence = prediction.get("confidence", 0.0)
            
            prediction_history.append(DiabetesPrediction(
                analysis_id=str(analysis["_id"]),
                report_id=analysis.get("report_id", ""),
                report_name=reports_map.get(analysis.get("report_id")),
                prediction_label=pred_label,
                confidence=pred_confidence,
                analyzed_at=analysis.get("created_at", datetime.utcnow())
            ))
            
            if pred_label == "diabetes":
                diabetic_count += 1
            total_confidence += pred_confidence
    
    # Latest prediction
    latest_prediction = prediction_history[0] if prediction_history else None
    
    # Calculate average confidence
    avg_confidence = total_confidence / len(prediction_history) if prediction_history else None
    
    # Determine diabetes status
    diabetes_status = None
    if has_diabetes_in_history:
        diabetes_status = "diabetic"
    elif diabetic_count > 0:
        if diabetic_count == len(prediction_history):
            diabetes_status = "diabetic"
        else:
            diabetes_status = "at-risk"
    elif len(prediction_history) > 0:
        diabetes_status = "monitoring"
    
    # Extract trends from analyses with extracted_data or extracted_features
    hba1c_readings: list[HbA1cReading] = []
    fasting_glucose_readings: list[FastingGlucoseReading] = []
    bmi_readings: list[BMIReading] = []
    
    # Also check extraction analyses
    extraction_cursor = analyses_collection.find({
        "patient_id": patient_id,
        "extracted_data": {"$exists": True, "$ne": None}
    }).sort("created_at", -1)
    
    extraction_analyses = await extraction_cursor.to_list(length=100)
    
    for analysis in extraction_analyses:
        extracted = analysis.get("extracted_data", {})
        analysis_date = analysis.get("created_at", datetime.utcnow())
        report_id = analysis.get("report_id")
        
        if isinstance(analysis_date, datetime):
            reading_date = analysis_date.date()
        else:
            reading_date = date_type.today()
        
        # Extract lab results
        lab_results = extracted.get("lab_results", [])
        for lab in lab_results:
            test_name = lab.get("test_name", "").lower()
            value_str = lab.get("value", "")
            status = lab.get("status")
            
            try:
                value = float(value_str.replace(",", "").split()[0])
            except (ValueError, IndexError):
                continue
            
            # HbA1c
            if "hba1c" in test_name or "glycosylated" in test_name or "hemoglobin a1c" in test_name:
                hba1c_status = None
                if value < 5.7:
                    hba1c_status = "Normal"
                elif value < 6.5:
                    hba1c_status = "Pre-diabetic"
                else:
                    hba1c_status = "Diabetic"
                    
                hba1c_readings.append(HbA1cReading(
                    date=reading_date,
                    value=value,
                    report_id=report_id,
                    status=hba1c_status
                ))
            
            # Fasting glucose
            elif "fasting" in test_name and ("glucose" in test_name or "sugar" in test_name or "blood" in test_name):
                glucose_status = None
                if value < 100:
                    glucose_status = "Normal"
                elif value < 126:
                    glucose_status = "Pre-diabetic"
                else:
                    glucose_status = "Diabetic"
                    
                fasting_glucose_readings.append(FastingGlucoseReading(
                    date=reading_date,
                    value=value,
                    report_id=report_id,
                    status=glucose_status
                ))
        
        # Extract vital signs for BMI
        vital_signs = extracted.get("vital_signs", {})
        bmi_str = vital_signs.get("bmi", "")
        if bmi_str and bmi_str != "N/A":
            try:
                bmi_value = float(bmi_str.replace(",", "").split()[0])
                bmi_category = None
                if bmi_value < 18.5:
                    bmi_category = "Underweight"
                elif bmi_value < 25:
                    bmi_category = "Normal"
                elif bmi_value < 30:
                    bmi_category = "Overweight"
                else:
                    bmi_category = "Obese"
                    
                bmi_readings.append(BMIReading(
                    date=reading_date,
                    value=bmi_value,
                    report_id=report_id,
                    category=bmi_category
                ))
            except (ValueError, IndexError):
                pass
    
    # Also extract from diabetes analyses (extracted_features)
    for analysis in analyses:
        features = analysis.get("extracted_features", {})
        analysis_date = analysis.get("created_at", datetime.utcnow())
        report_id = analysis.get("report_id")
        
        if isinstance(analysis_date, datetime):
            reading_date = analysis_date.date()
        else:
            reading_date = date_type.today()
        
        # HbA1c from features
        hba1c = features.get("HbA1c_level")
        if hba1c and hba1c > 0:
            hba1c_status = None
            if hba1c < 5.7:
                hba1c_status = "Normal"
            elif hba1c < 6.5:
                hba1c_status = "Pre-diabetic"
            else:
                hba1c_status = "Diabetic"
                
            hba1c_readings.append(HbA1cReading(
                date=reading_date,
                value=hba1c,
                report_id=report_id,
                status=hba1c_status
            ))
        
        # Blood glucose from features
        glucose = features.get("blood_glucose_level")
        if glucose and glucose > 0:
            glucose_status = None
            if glucose < 100:
                glucose_status = "Normal"
            elif glucose < 126:
                glucose_status = "Pre-diabetic"
            else:
                glucose_status = "Diabetic"
                
            fasting_glucose_readings.append(FastingGlucoseReading(
                date=reading_date,
                value=glucose,
                report_id=report_id,
                status=glucose_status
            ))
        
        # BMI from features
        bmi = features.get("bmi")
        if bmi and bmi > 0:
            bmi_category = None
            if bmi < 18.5:
                bmi_category = "Underweight"
            elif bmi < 25:
                bmi_category = "Normal"
            elif bmi < 30:
                bmi_category = "Overweight"
            else:
                bmi_category = "Obese"
                
            bmi_readings.append(BMIReading(
                date=reading_date,
                value=bmi,
                report_id=report_id,
                category=bmi_category
            ))
    
    # Remove duplicates and sort by date
    hba1c_readings = sorted(
        {(r.date, r.value): r for r in hba1c_readings}.values(),
        key=lambda x: x.date,
        reverse=True
    )[:20]
    
    fasting_glucose_readings = sorted(
        {(r.date, r.value): r for r in fasting_glucose_readings}.values(),
        key=lambda x: x.date,
        reverse=True
    )[:20]
    
    bmi_readings = sorted(
        {(r.date, r.value): r for r in bmi_readings}.values(),
        key=lambda x: x.date,
        reverse=True
    )[:20]
    
    # Build risk factors
    risk_factors: list[DiabetesRiskFactor] = []
    
    # Check latest BMI
    if bmi_readings:
        latest_bmi = bmi_readings[0]
        if latest_bmi.value >= 30:
            risk_factors.append(DiabetesRiskFactor(
                factor="Obesity",
                severity="high",
                description=f"BMI of {latest_bmi.value:.1f} indicates obesity, a major risk factor for diabetes."
            ))
        elif latest_bmi.value >= 25:
            risk_factors.append(DiabetesRiskFactor(
                factor="Overweight",
                severity="medium",
                description=f"BMI of {latest_bmi.value:.1f} indicates overweight status."
            ))
    
    # Check latest HbA1c
    if hba1c_readings:
        latest_hba1c = hba1c_readings[0]
        if latest_hba1c.value >= 6.5:
            risk_factors.append(DiabetesRiskFactor(
                factor="Elevated HbA1c",
                severity="high",
                description=f"HbA1c of {latest_hba1c.value:.1f}% indicates diabetic range."
            ))
        elif latest_hba1c.value >= 5.7:
            risk_factors.append(DiabetesRiskFactor(
                factor="Pre-diabetic HbA1c",
                severity="medium",
                description=f"HbA1c of {latest_hba1c.value:.1f}% indicates pre-diabetic range."
            ))
    
    # Check latest fasting glucose
    if fasting_glucose_readings:
        latest_glucose = fasting_glucose_readings[0]
        if latest_glucose.value >= 126:
            risk_factors.append(DiabetesRiskFactor(
                factor="High Fasting Glucose",
                severity="high",
                description=f"Fasting glucose of {latest_glucose.value:.0f} mg/dL indicates diabetic range."
            ))
        elif latest_glucose.value >= 100:
            risk_factors.append(DiabetesRiskFactor(
                factor="Elevated Fasting Glucose",
                severity="medium",
                description=f"Fasting glucose of {latest_glucose.value:.0f} mg/dL indicates pre-diabetic range."
            ))
    
    # Build recommendations based on status and risk factors
    recommendations: list[str] = []
    
    if diabetes_status == "diabetic":
        recommendations.extend([
            "Monitor blood glucose levels daily",
            "Follow your prescribed medication regimen",
            "Maintain a balanced diet low in refined sugars",
            "Exercise regularly - aim for 30 minutes of moderate activity daily",
            "Schedule regular check-ups with your healthcare provider",
            "Get HbA1c tested every 3 months"
        ])
    elif diabetes_status == "at-risk" or diabetes_status == "monitoring":
        recommendations.extend([
            "Monitor blood glucose levels regularly",
            "Maintain a healthy weight through diet and exercise",
            "Limit intake of processed foods and sugars",
            "Stay physically active - 150 minutes of exercise per week",
            "Get HbA1c tested every 6 months",
            "Upload new reports regularly for AI monitoring"
        ])
    else:
        recommendations.extend([
            "Upload medical reports for diabetes screening",
            "Maintain a healthy lifestyle",
            "Get regular health check-ups"
        ])
    
    return DiabetesDashboardResponse(
        has_diabetes_data=True,
        diabetes_status=diabetes_status,
        latest_prediction=latest_prediction,
        prediction_history=prediction_history,
        trends=DiabetesTrends(
            hba1c_readings=hba1c_readings,
            fasting_glucose=fasting_glucose_readings,
            bmi_history=bmi_readings
        ),
        risk_factors=risk_factors,
        recommendations=recommendations,
        total_analyses=len(prediction_history),
        diabetic_predictions_count=diabetic_count,
        average_confidence=avg_confidence
    )


def check_diabetes_access(db: Session, patient_id: str) -> bool:
    """
    Check if a patient has diabetes-related data.
    Used to determine if diabetes dashboard should be accessible.
    """
    user = db.query(User).filter(User.id == patient_id).first()
    if not user:
        return False
    
    # Check medical history
    if user.patient_profile and user.patient_profile.medical_history:
        for condition in user.patient_profile.medical_history:
            if "diabetes" in condition.lower():
                return True
    
    return True  # Allow access for AI prediction check (done in service)
