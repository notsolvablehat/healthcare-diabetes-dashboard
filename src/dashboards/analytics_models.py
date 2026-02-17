# src/dashboards/analytics_models.py
"""Pydantic models for dashboard analytics endpoints."""

from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Common Models
# ============================================================================

class MonthlyCount(BaseModel):
    """Count for a specific month."""
    month: str = Field(..., description="Month in YYYY-MM format")
    count: int = Field(..., description="Count for this month")


class TypeCount(BaseModel):
    """Count for a specific type/category."""
    type: str = Field(..., description="Type or category name")
    count: int = Field(..., description="Count for this type")


class NextAppointment(BaseModel):
    """Details of the next upcoming appointment."""
    id: str
    doctor_name: str
    start_time: datetime
    type: str
    reason: str | None = None


# ============================================================================
# Patient Analytics Models
# ============================================================================

class AppointmentAnalytics(BaseModel):
    """Appointment statistics for patient."""
    total: int = 0
    upcoming: int = 0
    completed: int = 0
    cancelled: int = 0
    no_show: int = 0
    by_month: list[MonthlyCount] = Field(default_factory=list)
    by_type: list[TypeCount] = Field(default_factory=list)
    next_appointment: NextAppointment | None = None


class VitalSigns(BaseModel):
    """Latest vital signs from patient profile."""
    blood_group: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None


class PatientAnalyticsResponse(BaseModel):
    """Analytics data for patient dashboard."""
    appointments: AppointmentAnalytics
    medications: list[str] = Field(default_factory=list)
    vitals: VitalSigns
    reports_by_month: list[MonthlyCount] = Field(default_factory=list)
    cases_by_month: list[MonthlyCount] = Field(default_factory=list)


# ============================================================================
# Doctor Analytics Models
# ============================================================================

class DoctorAppointmentAnalytics(BaseModel):
    """Appointment statistics for doctor."""
    total: int = 0
    today: int = 0
    upcoming_week: int = 0
    completed: int = 0
    cancelled: int = 0
    no_show: int = 0
    by_month: list[MonthlyCount] = Field(default_factory=list)
    by_type: list[TypeCount] = Field(default_factory=list)
    completion_rate: float = Field(0.0, description="Percentage of completed appointments")


class PatientDemographics(BaseModel):
    """Demographics of assigned patients."""
    by_gender: list[TypeCount] = Field(default_factory=list)
    by_age_group: list[TypeCount] = Field(default_factory=list)


class DoctorAnalyticsResponse(BaseModel):
    """Analytics data for doctor dashboard."""
    appointments: DoctorAppointmentAnalytics
    patient_demographics: PatientDemographics
    cases_by_month: list[MonthlyCount] = Field(default_factory=list)
    cases_by_type: list[TypeCount] = Field(default_factory=list)
    reports_analyzed: int = 0
    reports_pending: int = 0
