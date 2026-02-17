# src/appointments/services.py
"""Business logic for appointments module."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.assignments.services import is_patient_assigned_to_doctor
from src.notifications.services import (
    notify_appointment_cancelled,
    notify_appointment_completed,
    notify_appointment_created,
)
from src.schemas.users.users import Appointment as AppointmentORM
from src.schemas.users.users import User

from .models import (
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentStatus,
    AppointmentType,
    BookedSlot,
    BookedSlotsResponse,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    UpdateAppointmentStatusRequest,
)


def get_doctor_appointments(
    db: Session,
    doctor_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    status: AppointmentStatus | None = None,
) -> AppointmentListResponse:
    """
    Get all appointments for a doctor with optional filters.
    
    Args:
        db: Database session
        doctor_id: Doctor's user ID
        start_date: Filter appointments from this date
        end_date: Filter appointments to this date
        status: Filter by appointment status
        
    Returns:
        List of appointments with patient names
    """
    query = db.query(AppointmentORM).filter(AppointmentORM.doctor_user_id == doctor_id)
    
    # Apply filters
    if start_date:
        query = query.filter(AppointmentORM.start_time >= start_date)
    if end_date:
        query = query.filter(AppointmentORM.start_time <= end_date)
    if status:
        query = query.filter(AppointmentORM.status == status.value)
    
    # Order by start time (soonest first)
    query = query.order_by(AppointmentORM.start_time.asc())
    
    appointments = query.all()
    
    # Get patient names
    patient_ids = [appt.patient_user_id for appt in appointments]
    patients = db.query(User).filter(User.id.in_(patient_ids)).all() if patient_ids else []
    patient_names = {p.id: p.name for p in patients}
    
    # Build response
    appointment_responses = []
    for appt in appointments:
        appointment_responses.append(AppointmentResponse(
            id=appt.id,
            doctor_id=appt.doctor_user_id,
            doctor_name=None,  # Not needed for doctor view
            patient_id=appt.patient_user_id,
            patient_name=patient_names.get(appt.patient_user_id),
            start_time=appt.start_time,
            end_time=appt.end_time,
            type=AppointmentType(appt.type),
            status=AppointmentStatus(appt.status),
            reason=appt.reason,
            notes=appt.notes,
            cancellation_reason=appt.cancellation_reason,
            created_at=appt.created_at,
            updated_at=appt.updated_at,
        ))
    
    return AppointmentListResponse(
        count=len(appointment_responses),
        appointments=appointment_responses
    )


def get_patient_appointments(
    db: Session,
    patient_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    status: AppointmentStatus | None = None,
) -> AppointmentListResponse:
    """
    Get all appointments for a patient with optional filters.
    
    Args:
        db: Database session
        patient_id: Patient's user ID
        start_date: Filter appointments from this date
        end_date: Filter appointments to this date
        status: Filter by appointment status
        
    Returns:
        List of appointments with doctor names
    """
    query = db.query(AppointmentORM).filter(AppointmentORM.patient_user_id == patient_id)
    
    # Apply filters
    if start_date:
        query = query.filter(AppointmentORM.start_time >= start_date)
    if end_date:
        query = query.filter(AppointmentORM.start_time <= end_date)
    if status:
        query = query.filter(AppointmentORM.status == status.value)
    
    # Order by start time (soonest first)
    query = query.order_by(AppointmentORM.start_time.asc())
    
    appointments = query.all()
    
    # Get doctor names
    doctor_ids = [appt.doctor_user_id for appt in appointments]
    doctors = db.query(User).filter(User.id.in_(doctor_ids)).all() if doctor_ids else []
    doctor_names = {d.id: d.name for d in doctors}
    
    # Build response
    appointment_responses = []
    for appt in appointments:
        appointment_responses.append(AppointmentResponse(
            id=appt.id,
            doctor_id=appt.doctor_user_id,
            doctor_name=doctor_names.get(appt.doctor_user_id),
            patient_id=appt.patient_user_id,
            patient_name=None,  # Not needed for patient view
            start_time=appt.start_time,
            end_time=appt.end_time,
            type=AppointmentType(appt.type),
            status=AppointmentStatus(appt.status),
            reason=appt.reason,
            notes=appt.notes,
            cancellation_reason=appt.cancellation_reason,
            created_at=appt.created_at,
            updated_at=appt.updated_at,
        ))
    
    return AppointmentListResponse(
        count=len(appointment_responses),
        appointments=appointment_responses
    )


def create_appointment(
    db: Session,
    patient_id: str,
    request: CreateAppointmentRequest,
) -> CreateAppointmentResponse:
    """
    Create a new appointment.
    
    Args:
        db: Database session
        patient_id: Patient's user ID
        request: Appointment creation request
        
    Returns:
        Created appointment confirmation
        
    Raises:
        HTTPException: If validation fails
    """
    # Verify patient is assigned to doctor
    if not is_patient_assigned_to_doctor(db, patient_id=patient_id, doctor_id=request.doctor_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this doctor. Please request assignment first."
        )
    
    # Verify doctor exists
    doctor = db.query(User).filter(User.id == request.doctor_id, User.role == "doctor").first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Calculate end time (30 minutes after start)
    end_time = request.start_time + timedelta(minutes=30)
    
    # Check if slot is available (no overlapping appointments for doctor)
    overlapping = db.query(AppointmentORM).filter(
        AppointmentORM.doctor_user_id == request.doctor_id,
        AppointmentORM.status == AppointmentStatus.SCHEDULED.value,
        or_(
            # New appointment starts during existing appointment
            and_(
                AppointmentORM.start_time <= request.start_time,
                AppointmentORM.end_time > request.start_time
            ),
            # New appointment ends during existing appointment
            and_(
                AppointmentORM.start_time < end_time,
                AppointmentORM.end_time >= end_time
            ),
            # New appointment completely contains existing appointment
            and_(
                AppointmentORM.start_time >= request.start_time,
                AppointmentORM.end_time <= end_time
            )
        )
    ).first()
    
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This time slot is not available. Doctor already has an appointment from {overlapping.start_time} to {overlapping.end_time}."
        )
    
    # Validate start time is in the future
    if request.start_time <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment time must be in the future"
        )
    
    # Create appointment
    appointment_id = str(uuid4())
    new_appointment = AppointmentORM(
        id=appointment_id,
        doctor_user_id=request.doctor_id,
        patient_user_id=patient_id,
        start_time=request.start_time,
        end_time=end_time,
        type=request.type.value,
        status=AppointmentStatus.SCHEDULED.value,
        reason=request.reason,
    )
    
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)
    
    # Get patient name for notification
    patient = db.query(User).filter(User.id == patient_id).first()
    patient_name = patient.name if patient else "A patient"
    
    # Notify doctor about new appointment
    try:
        notify_appointment_created(
            db=db,
            doctor_id=request.doctor_id,
            patient_name=patient_name,
            appointment_time=request.start_time,
            appointment_type=request.type.value,
        )
    except Exception as e:
        # Log but don't fail appointment creation if notification fails
        print(f"Failed to send appointment notification: {e}")
    
    return CreateAppointmentResponse(
        id=appointment_id,
        status=AppointmentStatus.SCHEDULED,
        message="Appointment confirmed"
    )


def update_appointment_status(
    db: Session,
    appointment_id: str,
    user_id: str,
    user_role: str,
    request: UpdateAppointmentStatusRequest,
) -> AppointmentResponse:
    """
    Update the status of an appointment.
    
    Args:
        db: Database session
        appointment_id: Appointment ID
        user_id: User making the update
        user_role: Role of user (patient or doctor)
        request: Status update request
        
    Returns:
        Updated appointment
        
    Raises:
        HTTPException: If validation fails
    """
    # Fetch appointment
    appointment = db.query(AppointmentORM).filter(AppointmentORM.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Verify access
    if user_role == "patient":
        if appointment.patient_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own appointments"
            )
        # Patients can only cancel
        if request.status not in [AppointmentStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients can only cancel appointments"
            )
    elif user_role == "doctor":
        if appointment.doctor_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update appointments with your patients"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients and doctors can update appointments"
        )
    
    # Prevent updating completed/cancelled appointments
    if appointment.status in [AppointmentStatus.COMPLETED.value, AppointmentStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update appointment that is already {appointment.status}"
        )
    
    # Update status
    appointment.status = request.status.value
    
    # Update cancellation reason if provided
    if request.status == AppointmentStatus.CANCELLED and request.cancellation_reason:
        appointment.cancellation_reason = request.cancellation_reason
    
    # Update notes (doctor only)
    if user_role == "doctor" and request.notes:
        appointment.notes = request.notes
    
    db.commit()
    db.refresh(appointment)
    
    # Get patient and doctor names for response and notifications
    patient = db.query(User).filter(User.id == appointment.patient_user_id).first()
    doctor = db.query(User).filter(User.id == appointment.doctor_user_id).first()
    doctor_name = doctor.name if doctor else "Your doctor"
    
    # Send notifications to patient for status changes
    try:
        if request.status == AppointmentStatus.COMPLETED:
            notify_appointment_completed(
                db=db,
                patient_id=appointment.patient_user_id,
                doctor_name=doctor_name,
                appointment_time=appointment.start_time,
            )
        elif request.status == AppointmentStatus.CANCELLED:
            notify_appointment_cancelled(
                db=db,
                patient_id=appointment.patient_user_id,
                doctor_name=doctor_name,
                appointment_time=appointment.start_time,
                cancelled_by=user_role,
                reason=request.cancellation_reason,
            )
    except Exception as e:
        # Log but don't fail status update if notification fails
        print(f"Failed to send appointment status notification: {e}")
    
    return AppointmentResponse(
        id=appointment.id,
        doctor_id=appointment.doctor_user_id,
        doctor_name=doctor.name if doctor else None,
        patient_id=appointment.patient_user_id,
        patient_name=patient.name if patient else None,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        type=AppointmentType(appointment.type),
        status=AppointmentStatus(appointment.status),
        reason=appointment.reason,
        notes=appointment.notes,
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


def get_booked_slots(
    db: Session,
    doctor_id: str,
    date: str,  # YYYY-MM-DD format
    user_role: str,
) -> BookedSlotsResponse:
    """
    Get all booked appointment slots for a doctor on a specific date.
    
    Args:
        db: Database session
        doctor_id: Doctor's user ID
        date: Date in YYYY-MM-DD format
        user_role: Role of requesting user (for anonymization)
    
    Returns:
        BookedSlotsResponse with slots and anonymized patient names for non-doctors
        
    Raises:
        HTTPException: If doctor not found or date invalid
    """
    from datetime import datetime
    
    # Verify doctor exists
    doctor = db.query(User).filter(User.id == doctor_id, User.role == "doctor").first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Parse date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    # Define start and end of day
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    # Query appointments for this doctor on this date
    appointments = db.query(AppointmentORM).filter(
        AppointmentORM.doctor_user_id == doctor_id,
        AppointmentORM.start_time >= start_of_day,
        AppointmentORM.start_time <= end_of_day,
        AppointmentORM.status == AppointmentStatus.SCHEDULED.value,  # Only scheduled appointments
    ).order_by(AppointmentORM.start_time.asc()).all()
    
    # Get patient names
    patient_ids = [appt.patient_user_id for appt in appointments]
    patients = db.query(User).filter(User.id.in_(patient_ids)).all() if patient_ids else []
    patient_names = {p.id: p.name for p in patients}
    
    # Build booked slots with anonymization
    booked_slots = []
    for appt in appointments:
        # Anonymize patient name for non-doctors
        if user_role == "doctor":
            patient_name = patient_names.get(appt.patient_user_id, "Unknown Patient")
        else:
            # Anonymize: show only first name initial
            full_name = patient_names.get(appt.patient_user_id, "Anonymous")
            patient_name = f"{full_name[0]}***" if full_name else "Anonymous"
        
        booked_slots.append(BookedSlot(
            appointment_id=appt.id,
            doctor_id=appt.doctor_user_id,
            doctor_name=doctor.name,
            patient_id=appt.patient_user_id,
            patient_name=patient_name,
            start_time=appt.start_time,
            end_time=appt.end_time,
            type=AppointmentType(appt.type),
            status=AppointmentStatus(appt.status),
        ))
    
    return BookedSlotsResponse(
        doctor_id=doctor_id,
        doctor_name=doctor.name,
        date=date,
        booked_slots=booked_slots,
        total_booked=len(booked_slots)
    )
