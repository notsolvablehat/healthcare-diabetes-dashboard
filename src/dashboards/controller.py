# src/dashboards/controller.py
"""Dashboard API endpoints for patients and doctors."""

from fastapi import APIRouter, HTTPException, Query, status

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.mongo import MongoDb

from .models import DoctorDashboardResponse, PatientDashboardResponse
from .services import get_doctor_dashboard, get_patient_dashboard

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
