"""
Pydantic models for AI analysis operations.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# Report Extraction Models (General Medical, not diabetes-specific)
# ============================================================================

class LabResult(BaseModel):
    """Individual lab test result."""
    test_name: str = Field(description="Name of the test (e.g., HbA1c, Cholesterol)")
    value: str = Field(description="Test value as string")
    unit: str = Field(default="N/A", description="Unit of measurement")
    reference_range: str = Field(default="N/A", description="Normal reference range")
    status: str = Field(default="N/A", description="Normal, High, Low, or N/A")


class Medication(BaseModel):
    """Medication entry from prescription/report."""
    name: str = Field(description="Drug name")
    dosage: str = Field(default="N/A", description="Dosage amount")
    frequency: str = Field(default="N/A", description="How often taken")


class VitalSigns(BaseModel):
    """Vital signs extracted from report."""
    blood_pressure: str = Field(default="N/A", description="Blood pressure reading")
    heart_rate: str = Field(default="N/A", description="Heart rate in bpm")
    temperature: str = Field(default="N/A", description="Body temperature")
    weight: str = Field(default="N/A", description="Weight with unit")
    height: str = Field(default="N/A", description="Height with unit")
    bmi: str = Field(default="N/A", description="Body Mass Index")


class ReportExtraction(BaseModel):
    """
    Complete extraction from a medical report.
    All fields have N/A defaults for missing values.
    """
    # Mandatory patient info
    patient_name: str = Field(default="N/A", description="Patient's full name")
    patient_age: str = Field(default="N/A", description="Patient age")
    patient_sex: str = Field(default="N/A", description="Male/Female/Other")
    date_of_birth: str = Field(default="N/A", description="Date of birth if found")

    # Mandatory report info
    report_date: str = Field(default="N/A", description="Date of the report")
    report_type: str = Field(default="N/A", description="Lab Report, Prescription, Imaging, etc.")

    # Vital signs
    vital_signs: VitalSigns = Field(default_factory=VitalSigns)

    # Clinical data
    lab_results: list[LabResult] = Field(default_factory=list, description="All lab test results")
    diagnoses: list[str] = Field(default_factory=list, description="Diagnosed conditions")
    medications: list[Medication] = Field(default_factory=list, description="Prescribed medications")
    recommendations: list[str] = Field(default_factory=list, description="Doctor recommendations")

    # Additional notes
    additional_notes: str = Field(default="N/A", description="Any other relevant information")


# ============================================================================
# Legacy Models (kept for compatibility)
# ============================================================================

class ExtractedFeatures(BaseModel):
    """
    8 features required by the XGBoost diabetes prediction model.
    Extracted from medical reports using Gemini.
    """
    gender: int = Field(
        description="0=Female, 1=Male, 2=Other"
    )
    age: float = Field(
        description="Patient age in years"
    )
    hypertension: int = Field(
        default=0,
        description="0=No, 1=Yes"
    )
    heart_disease: int = Field(
        default=0,
        description="0=No, 1=Yes"
    )
    smoking_history: int = Field(
        default=0,
        description="0-4 encoded smoking status"
    )
    bmi: float = Field(
        description="Body Mass Index in kg/m²"
    )
    HbA1c_level: float = Field(
        description="HbA1c level in percentage"
    )
    blood_glucose_level: int = Field(
        description="Blood glucose level in mg/dL"
    )

    # Additional fields from report (not used in XGBoost but useful)
    raw_text: str | None = Field(
        default=None,
        description="Raw extracted text from report"
    )


class PredictionResult(BaseModel):
    """XGBoost prediction output."""
    label: str = Field(
        description="no_diabetes or diabetes"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Prediction confidence (0-1)"
    )


# ============================================================================
# Report Extraction API Models
# ============================================================================

class ExtractReportResponse(BaseModel):
    """Response for POST /ai/extract-report/{report_id}"""
    report_id: str
    status: str = "completed"
    extracted_data: ReportExtraction
    raw_text: str
    mongo_analysis_id: str | None = None
    processing_time_ms: int = 0
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Chat System Models
# ============================================================================

class StartChatRequest(BaseModel):
    """Request for POST /ai/chat/start"""
    patient_id: str | None = Field(
        default=None,
        description="Required for doctors, auto-filled for patients"
    )
    report_ids: list[str] | None = Field(
        default=None,
        description="Optional: attach specific reports to this chat"
    )


class StartChatResponse(BaseModel):
    """Response for POST /ai/chat/start"""
    chat_id: str
    patient_id: str
    attached_report_ids: list[str]
    created_at: datetime


class ChatMessageRequest(BaseModel):
    """Request for POST /ai/chat/{chat_id}/message"""
    message: str = Field(min_length=1, max_length=2000)
    attach_report_ids: list[str] | None = Field(
        default=None,
        description="Optionally attach more reports with this message"
    )


class ChatMessageResponse(BaseModel):
    """Response for POST /ai/chat/{chat_id}/message"""
    message_id: str
    response: str
    sources: list[str] = Field(
        default_factory=list,
        description="Report IDs used in response"
    )
    title: str | None = Field(
        default=None,
        description="Generated title (only on first message)"
    )
    timestamp: datetime


class AttachReportsRequest(BaseModel):
    """Request for PATCH /ai/chat/{chat_id}/reports"""
    report_ids: list[str]
    action: Literal["add", "remove", "replace"] = "add"


class ChatMessage(BaseModel):
    """Single message in chat history."""
    id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    sources: list[str] | None = None


class ChatHistoryResponse(BaseModel):
    """Response for GET /ai/chat/{chat_id}/history"""
    chat_id: str
    patient_id: str
    title: str | None
    attached_report_ids: list[str]
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime


class ChatListItem(BaseModel):
    """Chat summary for list view."""
    chat_id: str
    patient_id: str
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatListResponse(BaseModel):
    """Response for GET /ai/chats"""
    total: int
    chats: list[ChatListItem]


# ============================================================================
# Legacy API Models (kept for compatibility)
# ============================================================================

class AnalyzeReportResponse(BaseModel):
    """Response for POST /ai/analyze-report/{report_id}"""
    report_id: str
    status: str = "completed"
    extracted_features: ExtractedFeatures
    prediction: PredictionResult
    narrative: str
    mongo_analysis_id: str | None = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class CaseSummaryResponse(BaseModel):
    """Response for POST /ai/summarize-case/{case_id}"""
    case_id: str
    summary: str
    key_findings: list[str]
    recommendations: list[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AskRequest(BaseModel):
    """Request for POST /ai/ask"""
    patient_id: str
    question: str


class AskResponse(BaseModel):
    """Response for POST /ai/ask"""
    answer: str
    sources: list[str] = Field(
        default_factory=list,
        description="Report IDs or document references used"
    )


class InsightsResponse(BaseModel):
    """Response for GET /ai/insights/{patient_id}"""
    patient_id: str
    insights: list[str]
    risk_factors: list[str]
    trends: list[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# MongoDB Document Models
# ============================================================================

class AnalysisDocument(BaseModel):
    """Document schema for MongoDB report_analysis collection."""
    report_id: str
    patient_id: str
    status: str = "completed"
    raw_text: str = ""
    extracted_data: dict = Field(default_factory=dict)
    processing_time_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatDocument(BaseModel):
    """Document schema for MongoDB chats collection."""
    chat_id: str
    user_id: str
    user_role: Literal["patient", "doctor"]
    patient_id: str
    title: str | None = None
    attached_report_ids: list[str] = Field(default_factory=list)
    context: str = Field(default="", description="Pre-built context from reports (set on first message)")
    messages: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

