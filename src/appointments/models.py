# src/appointments/models.py
"""Pydantic models for appointments module."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AppointmentType(str, Enum):
    """Type of appointment."""
    CONSULTATION = "Consultation"
    FOLLOW_UP = "Follow-up"
    EMERGENCY = "Emergency"


class AppointmentStatus(str, Enum):
    """Status of appointment."""
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    NO_SHOW = "No-show"


class CreateAppointmentRequest(BaseModel):
    """Request to create a new appointment."""
    doctor_id: str = Field(..., description="UUID of the doctor")
    start_time: datetime = Field(..., description="Start time of appointment")
    type: AppointmentType = Field(..., description="Type of appointment")
    reason: str | None = Field(None, max_length=500, description="Reason for appointment")


class UpdateAppointmentStatusRequest(BaseModel):
    """Request to update appointment status."""
    status: AppointmentStatus = Field(..., description="New status")
    cancellation_reason: str | None = Field(None, max_length=500, description="Reason for cancellation")
    notes: str | None = Field(None, max_length=1000, description="Doctor's notes")


class AppointmentResponse(BaseModel):
    """Single appointment response."""
    id: str
    doctor_id: str
    doctor_name: str | None = None
    patient_id: str
    patient_name: str | None = None
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    status: AppointmentStatus
    reason: str | None = None
    notes: str | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    """Response for listing appointments."""
    count: int
    appointments: list[AppointmentResponse]


class CreateAppointmentResponse(BaseModel):
    """Response after creating an appointment."""
    id: str
    status: AppointmentStatus
    message: str


class BookedSlot(BaseModel):
    """A single booked appointment slot."""
    appointment_id: str
    doctor_id: str
    doctor_name: str
    patient_id: str
    patient_name: str  # Anonymized for non-doctors
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    status: AppointmentStatus


class BookedSlotsResponse(BaseModel):
    """Response for GET /appointments/booked-slots."""
    doctor_id: str
    doctor_name: str
    date: str  # YYYY-MM-DD format
    booked_slots: list[BookedSlot]
    total_booked: int
