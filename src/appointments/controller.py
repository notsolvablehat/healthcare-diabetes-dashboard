# src/appointments/controller.py
"""API endpoints for appointments module."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from src.auth.services import CurrentUser
from src.database.core import DbSession

from .models import (
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentStatus,
    BookedSlotsResponse,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    UpdateAppointmentStatusRequest,
)
from .services import (
    create_appointment,
    get_booked_slots,
    get_doctor_appointments,
    get_patient_appointments,
    update_appointment_status,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("/doctor", response_model=AppointmentListResponse)
def get_doctor_appointments_endpoint(
    user: CurrentUser,
    db: DbSession,
    start_date: datetime | None = Query(None, description="Filter from this date"),
    end_date: datetime | None = Query(None, description="Filter to this date"),
    appointment_status: AppointmentStatus | None = Query(None, alias="status", description="Filter by status"),
):
    """
    Get all appointments for the logged-in doctor.
    
    Returns appointments with patient names, ordered by start time (soonest first).
    
    Optional filters:
    - start_date: Show appointments from this date onwards
    - end_date: Show appointments up to this date
    - status: Filter by appointment status (Scheduled, Completed, Cancelled, No-show)
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "doctor":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to doctors"
        )
    
    return get_doctor_appointments(
        db=db,
        doctor_id=user.user_id,
        start_date=start_date,
        end_date=end_date,
        status=appointment_status,
    )


@router.get("/patient", response_model=AppointmentListResponse)
def get_patient_appointments_endpoint(
    user: CurrentUser,
    db: DbSession,
    start_date: datetime | None = Query(None, description="Filter from this date"),
    end_date: datetime | None = Query(None, description="Filter to this date"),
    appointment_status: AppointmentStatus | None = Query(None, alias="status", description="Filter by status"),
):
    """
    Get all appointments for the logged-in patient.
    
    Returns appointments with doctor names, ordered by start time (soonest first).
    
    Optional filters:
    - start_date: Show appointments from this date onwards
    - end_date: Show appointments up to this date
    - status: Filter by appointment status (Scheduled, Completed, Cancelled, No-show)
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to patients"
        )
    
    return get_patient_appointments(
        db=db,
        patient_id=user.user_id,
        start_date=start_date,
        end_date=end_date,
        status=appointment_status,
    )


@router.post("", response_model=CreateAppointmentResponse, status_code=http_status.HTTP_201_CREATED)
def create_appointment_endpoint(
    user: CurrentUser,
    db: DbSession,
    request: CreateAppointmentRequest,
):
    """
    Book a new appointment with a doctor.
    
    Requirements:
    - Patient must be assigned to the doctor
    - Appointment time must be in the future
    - Time slot must be available (no overlapping appointments)
    - Appointment duration is fixed at 30 minutes
    
    Upon successful booking:
    - Appointment is created with status "Scheduled"
    - Doctor is notified (future: notification system)
    - Confirmation is returned
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role != "patient":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients can book appointments"
        )
    
    return create_appointment(
        db=db,
        patient_id=user.user_id,
        request=request,
    )


@router.patch("/{appointment_id}/status", response_model=AppointmentResponse)
def update_appointment_status_endpoint(
    appointment_id: str,
    user: CurrentUser,
    db: DbSession,
    request: UpdateAppointmentStatusRequest,
):
    """
    Update the status of an appointment.
    
    Patient permissions:
    - Can cancel their own scheduled appointments
    
    Doctor permissions:
    - Can mark appointments as Completed, Cancelled, or No-show
    - Can add internal notes
    
    Restrictions:
    - Cannot update appointments that are already Completed or Cancelled
    - Patients cannot mark appointments as Completed or No-show
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if user.role not in ["patient", "doctor"]:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only patients and doctors can update appointments"
        )
    
    return update_appointment_status(
        db=db,
        appointment_id=appointment_id,
        user_id=user.user_id,
        user_role=user.role,
        request=request,
    )


@router.get("/booked-slots", response_model=BookedSlotsResponse)
def get_booked_slots_endpoint(
    user: CurrentUser,
    db: DbSession,
    doctor_id: str = Query(..., description="Doctor's user ID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
):
    """
    Get all booked appointment slots for a doctor on a specific date.
    
    Returns list of scheduled appointments with:
    - Appointment details (time, type, status)
    - Doctor information
    - Patient names (anonymized for non-doctors: e.g., "J***")
    
    Use cases:
    - Patients checking doctor availability before booking
    - Doctors viewing their daily schedule
    - System preventing double-booking
    
    Query parameters:
    - doctor_id: UUID of the doctor
    - date: Target date in YYYY-MM-DD format
    """
    if not user or not user.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return get_booked_slots(
        db=db,
        doctor_id=doctor_id,
        date=date,
        user_role=user.role or "patient",
    )
