# src/dashboards/models.py
"""Pydantic response schemas for dashboard endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field

# ============================================================================
# Common Models
# ============================================================================

class PaginationInfo(BaseModel):
    """Pagination metadata."""
    page: int
    limit: int
    total: int
    total_pages: int


class AlertItem(BaseModel):
    """Alert for frontend toasters."""
    type: str  # "warning", "info", "critical"
    title: str
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AIStats(BaseModel):
    """Minimal AI usage stats."""
    chat_count: int = 0
    analyses_count: int = 0


# ============================================================================
# Patient Dashboard Models
# ============================================================================

class PatientUserInfo(BaseModel):
    """Patient user info for dashboard."""
    user_id: str
    name: str | None
    email: str
    last_profile_update: datetime | None = None


class DoctorSummaryItem(BaseModel):
    """Assigned doctor summary."""
    doctor_id: str
    name: str | None
    email: str
    specialisation: str


class CaseSummaryItem(BaseModel):
    """Case summary for listing."""
    case_id: str
    status: str
    chief_complaint: str | None
    created_at: datetime


class CasesSummary(BaseModel):
    """Cases with pagination and counts."""
    open: int = 0
    under_review: int = 0
    closed: int = 0
    approved: int = 0
    total: int = 0
    items: list[CaseSummaryItem] = Field(default_factory=list)
    pagination: PaginationInfo | None = None


class ReportSummaryItem(BaseModel):
    """Report summary for listing."""
    report_id: str
    file_name: str
    file_type: str
    created_at: datetime


class ReportsSummary(BaseModel):
    """Reports with pagination."""
    total: int = 0
    items: list[ReportSummaryItem] = Field(default_factory=list)
    pagination: PaginationInfo | None = None


class WeightReading(BaseModel):
    """Weight history point for charts."""
    date: date
    value: float  # kg


class GlucoseReading(BaseModel):
    """Glucose reading for charts."""
    date: date
    fasting: float | None = None
    post_meal: float | None = None


class BloodPressureReading(BaseModel):
    """Blood pressure reading for charts."""
    date: date
    systolic: int
    diastolic: int


class HealthCharts(BaseModel):
    """Health metrics for patient charts."""
    weight_history: list[WeightReading] = Field(default_factory=list)
    glucose_readings: list[GlucoseReading] = Field(default_factory=list)
    blood_pressure: list[BloodPressureReading] = Field(default_factory=list)
    last_profile_update: datetime | None = None


class PatientDashboardResponse(BaseModel):
    """Complete patient dashboard response."""
    user_info: PatientUserInfo
    assigned_doctors: list[DoctorSummaryItem] = Field(default_factory=list)
    cases: CasesSummary
    reports: ReportsSummary
    health_charts: HealthCharts
    alerts: list[AlertItem] = Field(default_factory=list)
    ai_stats: AIStats
    notifications_unread: int = 0


# ============================================================================
# Doctor Dashboard Models
# ============================================================================

class DoctorUserInfo(BaseModel):
    """Doctor user info for dashboard."""
    user_id: str
    name: str | None
    email: str
    specialisation: str


class PatientStats(BaseModel):
    """Doctor's patient stats."""
    active: int = 0
    max: int = 10
    load_percentage: float = 0.0


class PatientSummaryItem(BaseModel):
    """Assigned patient summary."""
    patient_id: str
    name: str | None
    email: str
    gender: str | None
    date_of_birth: date | None


class CaseWithPatient(BaseModel):
    """Case with patient info for doctor view."""
    case_id: str
    status: str
    chief_complaint: str | None
    patient_name: str | None
    patient_id: str
    created_at: datetime


class PendingApprovalItem(BaseModel):
    """Case pending doctor approval."""
    case_id: str
    patient_name: str | None
    patient_id: str
    chief_complaint: str | None
    created_at: datetime


class DoctorDashboardResponse(BaseModel):
    """Complete doctor dashboard response."""
    user_info: DoctorUserInfo
    patient_stats: PatientStats
    cases: CasesSummary
    pending_approvals: list[PendingApprovalItem] = Field(default_factory=list)
    alerts: list[AlertItem] = Field(default_factory=list)
    ai_stats: AIStats
    notifications_unread: int = 0
