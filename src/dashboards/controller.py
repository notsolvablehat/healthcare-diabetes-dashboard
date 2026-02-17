# src/dashboards/controller.py
"""Dashboard API endpoints for patients and doctors."""

from fastapi import APIRouter, HTTPException, Query, status

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.mongo import MongoDb

from .analytics import get_doctor_analytics, get_patient_analytics
from .analytics_models import DoctorAnalyticsResponse, PatientAnalyticsResponse
from .models import DiabetesDashboardResponse, DoctorDashboardResponse, PatientDashboardResponse
from .services import get_diabetes_dashboard, get_doctor_dashboard, get_patient_dashboard

router = APIRouter(tags=["dashboards"])


@router.get("/patient/dashboard", response_model=PatientDashboardResponse)
async def patient_dashboard(
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
    cases_page: int = Query(1, ge=1, description="Page number for cases"),
    cases_limit: int = Query(5, ge=1, le=50, description="Cases per page"),
    reports_page: int = Query(1, ge=1, description="Page number for reports"),
    reports_limit: int = Query(5, ge=1, le=50, description="Reports per page"),
):
    """
    Get patient dashboard with:
    - User info and assigned doctors
    - Paginated cases with status counts
    - Paginated reports
    - Health charts (weight, glucose, blood pressure)
    - Alerts for frontend toasters
    - AI usage stats
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to patients"
        )

    try:
        return await get_patient_dashboard(
            db=db,
            mongo_db=mongo_db,
            user_id=user.user_id,
            cases_page=cases_page,
            cases_limit=cases_limit,
            reports_page=reports_page,
            reports_limit=reports_limit,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e


@router.get("/doctor/dashboard", response_model=DoctorDashboardResponse)
async def doctor_dashboard(
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
    cases_page: int = Query(1, ge=1, description="Page number for cases"),
    cases_limit: int = Query(10, ge=1, le=50, description="Cases per page"),
):
    """
    Get doctor dashboard with:
    - User info and specialisation
    - Patient stats (active, max, load percentage)
    - Paginated cases with status counts
    - Pending approvals list
    - Alerts for frontend toasters
    - AI usage stats
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to doctors"
        )

    try:
        return await get_doctor_dashboard(
            db=db,
            mongo_db=mongo_db,
            user_id=user.user_id,
            cases_page=cases_page,
            cases_limit=cases_limit,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e


# ============================================================================
# Diabetes Dashboard Endpoints
# ============================================================================

@router.get("/patient/diabetes-dashboard", response_model=DiabetesDashboardResponse)
async def patient_diabetes_dashboard(
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Get diabetes-specific dashboard for the authenticated patient.
    
    Returns diabetes-related data including:
    - Diabetes status (diabetic, at-risk, monitoring)
    - Latest and historical AI predictions
    - HbA1c trends over time
    - Fasting glucose readings
    - BMI history
    - Risk factors assessment
    - Personalized recommendations
    
    Access is granted if:
    - Patient has "diabetes" in their medical history, OR
    - Any AI analysis has predicted diabetes for this patient
    
    Returns empty response with message if no diabetes data exists.
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to patients"
        )

    try:
        return await get_diabetes_dashboard(
            db=db,
            mongo_db=mongo_db,
            patient_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e


@router.get("/patient/{patient_id}/diabetes-dashboard", response_model=DiabetesDashboardResponse)
async def doctor_view_patient_diabetes_dashboard(
    patient_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Get diabetes-specific dashboard for a specific patient (doctor access).
    
    Allows doctors to view diabetes data for their assigned patients.
    
    Returns diabetes-related data including:
    - Diabetes status (diabetic, at-risk, monitoring)
    - Latest and historical AI predictions
    - HbA1c trends over time
    - Fasting glucose readings
    - BMI history
    - Risk factors assessment
    - Personalized recommendations
    
    Access requirements:
    - User must be a doctor
    - Patient must be assigned to this doctor
    
    Returns empty response with message if no diabetes data exists.
    """
    from src.assignments.services import is_patient_assigned_to_doctor
    
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to doctors"
        )

    # Verify patient is assigned to this doctor
    if not is_patient_assigned_to_doctor(db, patient_id=patient_id, doctor_id=user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patient is not assigned to you"
        )


    try:
        return await get_diabetes_dashboard(
            db=db,
            mongo_db=mongo_db,
            patient_id=patient_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/patient/analytics", response_model=PatientAnalyticsResponse)
def patient_analytics(
    user: CurrentUser,
    db: DbSession,
):
    """
    Get analytics data for patient dashboard.
    
    Returns:
    - Appointment statistics (total, upcoming, completed, cancelled, no-show)
    - Appointment trends by month (last 6 months)
    - Appointment breakdown by type (Consultation, Follow-up, Emergency)
    - Next upcoming appointment details
    - Current medications list
    - Vital signs (blood group, height, weight)
    - Reports uploaded by month
    - Cases created by month
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to patients"
        )

    try:
        return get_patient_analytics(db=db, patient_id=user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e


@router.get("/doctor/analytics", response_model=DoctorAnalyticsResponse)
def doctor_analytics(
    user: CurrentUser,
    db: DbSession,
):
    """
    Get analytics data for doctor dashboard.
    
    Returns:
    - Appointment statistics (total, today, upcoming week, completed, cancelled, no-show)
    - Appointment completion rate
    - Appointment trends by month (last 6 months)
    - Appointment breakdown by type (Consultation, Follow-up, Emergency)
    - Patient demographics (gender distribution, age group distribution)
    - Case trends by month
    - Case breakdown by type (initial, follow_up, urgent, routine)
    - Reports analyzed vs pending count
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to doctors"
        )

    try:
        return get_doctor_analytics(db=db, doctor_id=user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
