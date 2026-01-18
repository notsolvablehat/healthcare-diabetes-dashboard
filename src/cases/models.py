# src/cases/models.py
# Production-ready Pydantic schemas for Case & Doctor Notes
# Compatible with both MongoDB and PostgreSQL via dual-write pattern

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# ENUMS - Standardized values across the system
# ============================================================================

class CaseType(str, Enum):
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    URGENT = "urgent"
    ROUTINE = "routine"
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"

class CaseStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNDER_REVIEW = "under_review"
    APPROVED_BY_DOCTOR = "approved_by_doctor"

class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"

class ProblemType(str, Enum):
    DIAGNOSIS = "diagnosis"
    IMPRESSION = "impression"
    FINDING = "finding"
    RULE_OUT = "rule_out"
    DIFFERENTIAL = "differential"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ObservationStatus(str, Enum):
    PENDING = "pending"
    FINAL = "final"
    PRELIMINARY = "preliminary"
    CORRECTED = "corrected"

class MedicationFrequency(str, Enum):
    ONCE_DAILY = "once daily"
    TWICE_DAILY = "twice daily"
    THREE_TIMES = "three times daily"
    FOUR_TIMES = "four times daily"
    EVERY_6_HOURS = "every 6 hours"
    EVERY_8_HOURS = "every 8 hours"
    EVERY_12_HOURS = "every 12 hours"
    AS_NEEDED = "as needed"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class Route(str, Enum):
    ORAL = "oral"
    IV = "intravenous"
    IM = "intramuscular"
    TOPICAL = "topical"
    INHALED = "inhaled"
    RECTAL = "rectal"
    SUBLINGUAL = "sublingual"

class DispositionType(str, Enum):
    DISCHARGE = "discharge"
    ADMIT = "admit"
    OBSERVE = "observe"
    TRANSFER = "transfer"

# ============================================================================
# SUBJECTIVE SECTION MODELS (S in SOAP)
# ============================================================================

class HistoryOfPresentIllness(BaseModel):
    """Detailed history of current illness"""
    onset: str | None = None  # "YYYY-MM-DD" or "gradual" or "sudden"
    duration: str | None = None  # e.g. "3 days", "2 weeks"

    severity: dict[str, Any] | None = Field(
        None,
        description="Pain/symptom severity scale 1-10"
    )
    character: str | None = None  # e.g. "sharp", "dull", "burning"

    aggravating_factors: list[str] | None = Field(default_factory=list)
    alleviating_factors: list[str] | None = Field(default_factory=list)

    associated_symptoms: list[dict[str, Any]] | None = Field(default_factory=list)
    functional_status: str | None = None  # Impact on daily activities

    narrative: str | None = None  # Free-text full history (for LLM)

    class Config:
        json_schema_extra = {
            "example": {
                "onset": "2025-01-01",
                "duration": "3 days",
                "severity": {"scale": 8, "description": "severe"},
                "character": "sharp, burning pain in chest",
                "aggravating_factors": ["deep breathing", "lying down"],
                "alleviating_factors": ["rest", "antacids"],
                "associated_symptoms": [
                    {"symptom": "shortness of breath", "duration": "3 days", "severity": 7}
                ],
                "functional_status": "Unable to work, limited activity",
                "narrative": "Patient reports acute onset of sharp chest pain..."
            }
        }

class PastMedicalHistoryItem(BaseModel):
    """Previous medical condition"""
    condition: str  # SNOMED CT code + display
    snomed_code: str | None = None
    onset: date | None = None
    status: Literal["active", "inactive", "resolved"]
    notes: str | None = None

class CurrentMedication(BaseModel):
    """Currently prescribed medication"""
    name: str
    rxnorm_code: str | None = None
    dosage: str | None = None  # e.g. "10mg"
    frequency: MedicationFrequency | None = None
    duration: str | None = None
    indication: str | None = None
    status: Literal["active", "stopped", "paused"] = "active"

class Allergy(BaseModel):
    """Patient allergy"""
    allergen_type: Literal["drug", "food", "environmental", "other"]
    allergen_name: str
    reaction_type: str  # e.g. "rash", "anaphylaxis", "itching"
    severity: SeverityLevel
    reaction_date: date | None = None

class FamilyHistoryItem(BaseModel):
    """Family medical history"""
    relative: Literal["mother", "father", "sibling", "grandparent", "other"]
    condition: str  # SNOMED CT code + display
    snomed_code: str | None = None
    age_of_onset: int | None = None
    status: Literal["alive", "deceased"]

class SocialHistory(BaseModel):
    """Social and lifestyle history"""
    occupation: str | None = None
    smoking_status: Literal["never", "current", "former"] = "never"
    pack_years: float | None = None
    alcohol_use: Literal["none", "occasional", "regular", "heavy"] = "none"
    drug_use: Literal["none", "current", "former"] = "none"
    living_status: str | None = None

class ReviewOfSystems(BaseModel):
    """System-by-system screening"""
    constitutional: str | None = None
    cardiovascular: str | None = None
    respiratory: str | None = None
    gastrointestinal: str | None = None
    genitourinary: str | None = None
    neurological: str | None = None
    psychiatric_mental: str | None = None
    skin: str | None = None
    other_systems: str | None = None

class SubjectiveSection(BaseModel):
    """Complete Subjective (S) section of SOAP note"""
    chief_complaint: str = Field(..., max_length=500)

    history_of_present_illness: HistoryOfPresentIllness | None = None
    past_medical_history: list[PastMedicalHistoryItem] = Field(default_factory=list)

    current_medications: list[CurrentMedication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)

    family_history: list[FamilyHistoryItem] = Field(default_factory=list)
    social_history: SocialHistory | None = None

    review_of_systems: ReviewOfSystems | None = None

# ============================================================================
# OBJECTIVE SECTION MODELS (O in SOAP)
# ============================================================================

class VitalSigns(BaseModel):
    """Patient vital signs"""
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    systolic_bp: int | None = None  # mmHg
    diastolic_bp: int | None = None  # mmHg
    heart_rate: int | None = None  # bpm
    respiratory_rate: int | None = None  # breaths/min
    temperature: float | None = None  # °C or °F
    oxygen_saturation: float | None = None  # %

    weight: float | None = None  # kg
    height: float | None = None  # cm
    bmi: float | None = None  # kg/m²

class LabResult(BaseModel):
    """Individual lab test result"""
    test_name: str
    loinc_code: str | None = None
    value: str | None = None  # Can be string or number
    unit: str | None = None

    reference_range: dict[str, float] | None = None  # {"low": 70, "high": 100}
    status: ObservationStatus = ObservationStatus.FINAL
    abnormal: bool = False
    flags: str | None = None  # H (high), L (low), C (critical)

    date_collected: date | None = None
    date_received: date | None = None

class ImagingResult(BaseModel):
    """Imaging/Diagnostic study result"""
    study_type: str  # X-ray, CT, MRI, Ultrasound, ECG, etc.
    ordered_date: date
    completed_date: date | None = None

    description: str  # Radiologist impression
    findings: str | None = None
    impression: str | None = None

    s3_url: str | None = None  # AWS S3 path to image/PDF
    status: Literal["pending", "completed", "interpreted"] = "completed"
    radiologist_name: str | None = None

class ObjectiveSection(BaseModel):
    """Complete Objective (O) section of SOAP note"""
    vital_signs: VitalSigns | None = None

    physical_examination: dict[str, str] | None = None  # System-specific findings

    lab_results: list[LabResult] = Field(default_factory=list)
    imaging_results: list[ImagingResult] = Field(default_factory=list)

# ============================================================================
# ASSESSMENT SECTION MODELS (A in SOAP)
# ============================================================================

class Problem(BaseModel):
    """Individual problem/diagnosis in assessment"""
    rank: int = Field(1, ge=1)
    problem_type: ProblemType

    condition: str  # Display name
    snomed_code: str | None = None
    icd_code: str | None = None

    severity: SeverityLevel | None = None
    status: Literal["confirmed", "suspected", "ruled_out"] = "suspected"
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    clinical_reasoning: str | None = None  # Why doctor thinks this
    date_of_onset: date | None = None
    date_last_confirmed: date | None = None

class DifferentialDiagnosis(BaseModel):
    """Differential diagnosis consideration"""
    diagnosis: str
    snomed_code: str | None = None
    likelihood: Literal["high", "moderate", "low"]
    reasoning: str | None = None
    ruled_out: bool = False
    rule_out_reason: str | None = None

class ClinicalImpression(BaseModel):
    """Overall clinical impression"""
    summary: str  # 2-3 sentence summary
    complexity_level: Literal["straightforward", "moderate", "complex"]
    diagnostic_certainty: ConfidenceLevel
    main_concerns: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)

class AssessmentSection(BaseModel):
    """Complete Assessment (A) section of SOAP note"""
    problem_list: list[Problem] = Field(default_factory=list, min_items=1)
    differential_diagnoses: list[DifferentialDiagnosis] = Field(default_factory=list)
    clinical_impression: ClinicalImpression | None = None

# ============================================================================
# PLAN SECTION MODELS (P in SOAP)
# ============================================================================

class DiagnosticPlan(BaseModel):
    """Diagnostic test ordered"""
    test_name: str
    test_code: str | None = None
    priority: Literal["urgent", "routine", "when_available"] = "routine"
    rationale: str
    ordered_date: date = Field(default_factory=date.today)
    expected_result_date: date | None = None
    status: Literal["ordered", "pending", "completed", "cancelled"] = "ordered"

class Medication(BaseModel):
    """Medication prescribed"""
    name: str
    rxnorm_code: str | None = None
    dosage: str
    frequency: MedicationFrequency
    route: Route = Route.ORAL
    duration: str  # e.g. "5 days", "2 weeks", "ongoing"
    indication: str
    start_date: date = Field(default_factory=date.today)
    end_date: date | None = None
    instructions: str | None = None
    warnings: list[str] = Field(default_factory=list)
    status: Literal["prescribed", "active", "stopped", "completed"] = "prescribed"

class NonPharmaceuticalIntervention(BaseModel):
    """Non-drug intervention"""
    intervention: str
    category: Literal["lifestyle", "physical", "behavioral", "diet"]
    instructions: str
    expected_duration: str | None = None
    priority: Literal["high", "medium", "low"] = "medium"

class Procedure(BaseModel):
    """Medical procedure planned"""
    procedure_name: str
    snomed_code: str | None = None
    indication: str
    scheduled_date: date | None = None
    location: str | None = None
    urgency: Literal["emergency", "urgent", "routine"] = "routine"
    pre_operative_notes: str | None = None
    status: Literal["planned", "scheduled", "completed", "cancelled"] = "planned"

class PatientEducation(BaseModel):
    """Patient education provided"""
    topics: list[str] = Field(default_factory=list)
    education_provided: str
    patient_understanding: Literal["good", "fair", "poor"] = "good"
    education_materials: list[dict[str, str]] | None = None

class FollowUp(BaseModel):
    """Follow-up plan"""
    schedule_follow_up: bool = True
    follow_up_date: date | None = None
    follow_up_type: Literal["in_person", "phone", "telehealth", "lab_work"] = "in_person"
    follow_up_with: Literal["same_doctor", "specialist", "other"] = "same_doctor"
    follow_up_reason: str | None = None
    urgent_return_criteria: str | None = None

class Referral(BaseModel):
    """Referral to specialist"""
    specialty_needed: str
    reason: str
    urgency: Literal["urgent", "routine"] = "routine"
    referred_to: str | None = None  # Doctor name/ID
    referral_date: date = Field(default_factory=date.today)
    status: Literal["pending", "accepted", "completed", "cancelled"] = "pending"

class Disposition(BaseModel):
    """Patient disposition at end of visit"""
    disposition: DispositionType
    disposition_location: str  # home, hospital, ICU, etc.
    discharge_date_time: datetime | None = None
    discharge_instructions: str | None = None
    restrictions: str | None = None

class PlanSection(BaseModel):
    """Complete Plan (P) section of SOAP note"""
    diagnostic_plan: list[DiagnosticPlan] = Field(default_factory=list)

    medications: list[Medication] = Field(default_factory=list)
    non_pharmaceutical_interventions: list[NonPharmaceuticalIntervention] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)

    patient_education: PatientEducation | None = None
    follow_up: FollowUp | None = None
    referrals: list[Referral] = Field(default_factory=list)
    disposition: Disposition | None = None

# ============================================================================
# ATTACHMENT & DOCUMENT MODELS
# ============================================================================

class Attachment(BaseModel):
    """File attachment to case"""
    document_type: Literal["pdf_report", "lab_result", "imaging", "prescription", "consultation", "other"]
    file_name: str
    s3_url: str
    mime_type: str  # application/pdf, image/png, etc.
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: str  # UUID of doctor/staff
    is_public_to_patient: bool = False

class DoctorNote(BaseModel):
    """Individual note by doctor"""
    note_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str  # UUID
    content: str  # Markdown supported
    note_type: Literal["progress", "amendment", "clarification", "follow_up_observation"]
    visibility: Literal["doctor_only", "patient_visible", "shared"] = "doctor_only"
    linked_to_case_section: Literal["subjective", "objective", "assessment", "plan"] | None = None

class Amendment(BaseModel):
    """Amendment to case"""
    amendment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amended_at: datetime = Field(default_factory=datetime.utcnow)
    amended_by: str  # UUID
    reason: str  # Why amended
    changed_fields: dict[str, dict[str, Any]]  # {fieldName: {oldValue, newValue}}

class DoctorApproval(BaseModel):
    """Doctor approval workflow"""
    approved: bool = False
    approved_by: str | None = None  # UUID
    approval_date: datetime | None = None
    approval_notes: str | None = None
    requires_patient_signature: bool = False

class PatientConsent(BaseModel):
    """Patient consent tracking"""
    consent_given: bool = False
    consent_date: datetime | None = None
    consent_type: Literal["treatment", "data_sharing", "research"]

class AuditLog(BaseModel):
    """Audit trail entry"""
    action: Literal["created", "updated", "viewed", "approved", "amended", "shared", "note_added"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    performed_by: str  # UUID
    ip_address: str | None = None
    change_details: str | None = None

class NLPExtraction(BaseModel):
    """NLP-extracted clinical entities"""
    conditions: list[dict[str, Any]] | None = None  # [{code, display, confidence}]
    medications: list[dict[str, Any]] | None = None
    lab_values: list[dict[str, Any]] | None = None
    procedures: list[dict[str, Any]] | None = None

class AIAnalysis(BaseModel):
    """AI/LLM analysis results"""
    generated: bool = False
    generated_at: datetime | None = None
    model: str | None = None
    summary: str | None = None  # Patient-friendly summary
    key_insights: list[str] = Field(default_factory=list)
    risk_assessment: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    nlp_extracted_entities: NLPExtraction | None = None

# ============================================================================
# MAIN CASE DOCUMENT MODEL
# ============================================================================

class CaseCreate(BaseModel):
    """Request model for creating case"""
    patient_id: str
    doctor_id: str
    encounter_id: str | None = None

    case_type: CaseType = CaseType.ROUTINE
    chief_complaint: str = Field(..., max_length=500)

    subjective: SubjectiveSection | None = None
    objective: ObjectiveSection | None = None
    assessment: AssessmentSection | None = None
    plan: PlanSection | None = None

class CaseUpdate(BaseModel):
    """
    Request model for updating case (partial).
    
    Protected fields NOT allowed:
    - case_id: System generated
    - patient_id: Assignment shouldn't change  
    - doctor_id: Assignment shouldn't change
    - created_at: Historical timestamp
    - updated_at: Automatically managed
    - status: Use dedicated endpoints (approve, close, etc.)
    - audit_trail: Historical record only
    """
    severity: SeverityLevel | None = None

    subjective: SubjectiveSection | None = None
    objective: ObjectiveSection | None = None
    assessment: AssessmentSection | None = None
    plan: PlanSection | None = None

class Case(BaseModel):
    """Complete Case document (MongoDB + response model)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())

    # IDs
    patient_id: str
    doctor_id: str
    encounter_id: str | None = None
    hospital_id: str | None = None
    department_id: str | None = None

    # Metadata
    case_type: CaseType = CaseType.ROUTINE
    status: CaseStatus = CaseStatus.OPEN
    severity: SeverityLevel | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None

    # SOAP Sections
    subjective: SubjectiveSection | None = None
    objective: ObjectiveSection | None = None
    assessment: AssessmentSection | None = None
    plan: PlanSection | None = None

    # Attachments & Notes
    attachments: list[Attachment] = Field(default_factory=list)
    doctor_notes: list[DoctorNote] = Field(default_factory=list)
    amendment_history: list[Amendment] = Field(default_factory=list)

    # Workflow
    approvals: DoctorApproval | None = None
    patient_consent: PatientConsent | None = None
    audit_trail: list[AuditLog] = Field(default_factory=list)

    # AI/LLM
    ai_analysis: AIAnalysis | None = None

    # Metadata
    language: str = "en"
    tags: list[str] = Field(default_factory=list)

    class Config:
        use_enum_values = False
        json_schema_extra = {
            "example": {
                "case_id": "CASE001",
                "patient_id": "pat-uuid-123",
                "doctor_id": "doc-uuid-456",
                "chief_complaint": "Chest pain for 3 days",
                "status": "open"
            }
        }

# ============================================================================
# DOCTOR NOTES SPECIFIC MODELS
# ============================================================================

class DoctorNoteCreate(BaseModel):
    """Create a doctor note"""
    case_id: str
    content: str
    note_type: Literal["progress", "amendment", "clarification", "follow_up_observation"]
    visibility: Literal["doctor_only", "patient_visible", "shared"] = "doctor_only"
    linked_to_case_section: Literal["subjective", "objective", "assessment", "plan"] | None = None

class CaseApprovalRequest(BaseModel):
    """Request model for approving a case"""
    approval_notes: str | None = None


class DoctorNoteAmend(BaseModel):
    """Amend an existing note"""
    note_id: str
    reason: str  # clarification, error_correction, new_information
    amendment_content: str  # New content or diff

class DoctorNoteResponse(BaseModel):
    """Response model for doctor note"""
    note_id: str
    case_id: str
    created_at: datetime
    created_by: str
    content: str
    note_type: str
    visibility: str
    amendment_history: list[dict[str, Any]] | None = None
    signature_data: dict[str, Any] | None = None

# ============================================================================
# COMBINED RESPONSE MODELS
# ============================================================================

class CaseResponse(Case):
    """Complete case response with merged data"""
    total_problems: int = 0
    total_labs: int = 0
    total_medications: int = 0
    approval_status: str = "pending"
    ai_summary_available: bool = False

class PaginatedCaseList(BaseModel):
    """Paginated list of cases"""
    total: int
    page: int
    page_size: int
    cases: list[CaseResponse]

# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response model"""
    status_code: int
    error_type: str
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# VALIDATORS
# ============================================================================

def validate_case_completeness(case: Case) -> float:
    """Calculate case completeness percentage (0-100)"""
    fields = {
        "chief_complaint": bool(case.subjective and case.subjective.chief_complaint),
        "vital_signs": bool(case.objective and case.objective.vital_signs),
        "assessment": bool(case.assessment and case.assessment.problem_list),
        "plan": bool(case.plan and case.plan.diagnostic_plan),
    }
    return (sum(fields.values()) / len(fields)) * 100 if fields else 0

def validate_medical_code_format(code: str, code_type: str) -> bool:
    """Validate medical code format"""
    if code_type == "snomed":
        return len(code) > 0 and code.replace(".", "").isdigit()
    elif code_type == "icd10":
        return len(code) >= 3
    elif code_type == "loinc":
        return len(code) == 5 and code.isalnum()
    return True
