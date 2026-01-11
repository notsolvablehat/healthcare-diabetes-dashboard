"""
Pydantic models for AI analysis operations.
"""
from datetime import datetime

from pydantic import BaseModel, Field

# ============================================================================
# Feature Extraction Models
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


# ============================================================================
# Prediction Models
# ============================================================================

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
# API Request/Response Models
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
# Internal Models for MongoDB Storage
# ============================================================================

class AnalysisDocument(BaseModel):
    """Document schema for MongoDB report_analysis collection."""
    report_id: str
    raw_text: str | None = None
    extracted_features: dict
    prediction: dict
    narrative: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Allow arbitrary types for datetime serialization
        json_encoders = {datetime: lambda v: v.isoformat()}
