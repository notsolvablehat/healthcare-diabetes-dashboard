# case_schema_models.py
# Production-ready Pydantic schemas for Case & Doctor Notes
# Compatible with both MongoDB and PostgreSQL via dual-write pattern

from typing import Optional, List, Literal, Dict, Any
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid

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

class Disposition(str, Enum):
    DISCHARGE = "discharge"
    ADMIT = "admit"
    OBSERVE = "observe"
    TRANSFER = "transfer"

# ============================================================================
# SUBJECTIVE SECTION MODELS (S in SOAP)
# ============================================================================

class HistoryOfPresentIllness(BaseModel):
    """Detailed history of current illness"""
    onset: Optional[str] = None  # "YYYY-MM-DD" or "gradual" or "sudden"
    duration: Optional[str] = None  # e.g. "3 days", "2 weeks"
    
    severity: Optional[Dict[str, Any]] = Field(
        None,
        description="Pain/symptom severity scale 1-10"
    )
    character: Optional[str] = None  # e.g. "sharp", "dull", "burning"
    
    aggravating_factors: Optional[List[str]] = Field(default_factory=list)
    alleviating_factors: Optional[List[str]] = Field(default_factory=list)
    
    associated_symptoms: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    functional_status: Optional[str] = None  # Impact on daily activities
    
    narrative: Optional[str] = None  # Free-text full history (for LLM)
    
    class Config:
        schema_extra = {
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
    snomed_code: Optional[str] = None
    onset: Optional[date] = None
    status: Literal["active", "inactive", "resolved"]
    notes: Optional[str] = None

class CurrentMedication(BaseModel):
    """Currently prescribed medication"""
    name: str
    rxnorm_code: Optional[str] = None
    dosage: Optional[str] = None  # e.g. "10mg"
    frequency: Optional[MedicationFrequency] = None
    duration: Optional[str] = None
    indication: Optional[str] = None
    status: Literal["active", "stopped", "paused"] = "active"

class Allergy(BaseModel):
    """Patient allergy"""
    allergen_type: Literal["drug", "food", "environmental", "other"]
    allergen_name: str
    reaction_type: str  # e.g. "rash", "anaphylaxis", "itching"
    severity: SeverityLevel
    reaction_date: Optional[date] = None

class FamilyHistoryItem(BaseModel):
    """Family medical history"""
    relative: Literal["mother", "father", "sibling", "grandparent", "other"]
    condition: str  # SNOMED CT code + display
    snomed_code: Optional[str] = None
    age_of_onset: Optional[int] = None
    status: Literal["alive", "deceased"]

class SocialHistory(BaseModel):
    """Social and lifestyle history"""
    occupation: Optional[str] = None
    smoking_status: Literal["never", "current", "former"] = "never"
    pack_years: Optional[float] = None
    alcohol_use: Literal["none", "occasional", "regular", "heavy"] = "none"
    drug_use: Literal["none", "current", "former"] = "none"
    living_status: Optional[str] = None

class ReviewOfSystems(BaseModel):
    """System-by-system screening"""
    constitutional: Optional[str] = None
    cardiovascular: Optional[str] = None
    respiratory: Optional[str] = None
    gastrointestinal: Optional[str] = None
    genitourinary: Optional[str] = None
    neurological: Optional[str] = None
    psychiatric_mental: Optional[str] = None
    skin: Optional[str] = None
    other_systems: Optional[str] = None

class SubjectiveSection(BaseModel):
    """Complete Subjective (S) section of SOAP note"""
    chief_complaint: str = Field(..., max_length=500)
    
    history_of_present_illness: Optional[HistoryOfPresentIllness] = None
    past_medical_history: List[PastMedicalHistoryItem] = Field(default_factory=list)
    
    current_medications: List[CurrentMedication] = Field(default_factory=list)
    allergies: List[Allergy] = Field(default_factory=list)
    
    family_history: List[FamilyHistoryItem] = Field(default_factory=list)
    social_history: Optional[SocialHistory] = None
    
    review_of_systems: Optional[ReviewOfSystems] = None

# ============================================================================
# OBJECTIVE SECTION MODELS (O in SOAP)
# ============================================================================

class VitalSigns(BaseModel):
    """Patient vital signs"""
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    
    systolic_bp: Optional[int] = None  # mmHg
    diastolic_bp: Optional[int] = None  # mmHg
    heart_rate: Optional[int] = None  # bpm
    respiratory_rate: Optional[int] = None  # breaths/min
    temperature: Optional[float] = None  # °C or °F
    oxygen_saturation: Optional[float] = None  # %
    
    weight: Optional[float] = None  # kg
    height: Optional[float] = None  # cm
    bmi: Optional[float] = None  # kg/m²

class LabResult(BaseModel):
    """Individual lab test result"""
    test_name: str
    loinc_code: Optional[str] = None
    value: Optional[str] = None  # Can be string or number
    unit: Optional[str] = None
    
    reference_range: Optional[Dict[str, float]] = None  # {"low": 70, "high": 100}
    status: ObservationStatus = ObservationStatus.FINAL
    abnormal: bool = False
    flags: Optional[str] = None  # H (high), L (low), C (critical)
    
    date_collected: Optional[date] = None
    date_received: Optional[date] = None

class ImagingResult(BaseModel):
    """Imaging/Diagnostic study result"""
    study_type: str  # X-ray, CT, MRI, Ultrasound, ECG, etc.
    ordered_date: date
    completed_date: Optional[date] = None
    
    description: str  # Radiologist impression
    findings: Optional[str] = None
    impression: Optional[str] = None
    
    s3_url: Optional[str] = None  # AWS S3 path to image/PDF
    status: Literal["pending", "completed", "interpreted"] = "completed"
    radiologist_name: Optional[str] = None

class ObjectiveSection(BaseModel):
    """Complete Objective (O) section of SOAP note"""
    vital_signs: Optional[VitalSigns] = None
    
    physical_examination: Optional[Dict[str, str]] = None  # System-specific findings
    
    lab_results: List[LabResult] = Field(default_factory=list)
    imaging_results: List[ImagingResult] = Field(default_factory=list)

# ============================================================================
# ASSESSMENT SECTION MODELS (A in SOAP)
# ============================================================================

class Problem(BaseModel):
    """Individual problem/diagnosis in assessment"""
    rank: int = Field(1, ge=1)
    problem_type: ProblemType
    
    condition: str  # Display name
    snomed_code: Optional[str] = None
    icd_code: Optional[str] = None
    
    severity: Optional[SeverityLevel] = None
    status: Literal["confirmed", "suspected", "ruled_out"] = "suspected"
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    
    clinical_reasoning: Optional[str] = None  # Why doctor thinks this
    date_of_onset: Optional[date] = None
    date_last_confirmed: Optional[date] = None

class DifferentialDiagnosis(BaseModel):
    """Differential diagnosis consideration"""
    diagnosis: str
    snomed_code: Optional[str] = None
    likelihood: Literal["high", "moderate", "low"]
    reasoning: Optional[str] = None
    ruled_out: bool = False
    rule_out_reason: Optional[str] = None

class ClinicalImpression(BaseModel):
    """Overall clinical impression"""
    summary: str  # 2-3 sentence summary
    complexity_level: Literal["straightforward", "moderate", "complex"]
    diagnostic_certainty: ConfidenceLevel
    main_concerns: List[str] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)

class AssessmentSection(BaseModel):
    """Complete Assessment (A) section of SOAP note"""
    problem_list: List[Problem] = Field(default_factory=list, min_items=1)
    differential_diagnoses: List[DifferentialDiagnosis] = Field(default_factory=list)
    clinical_impression: Optional[ClinicalImpression] = None

# ============================================================================
# PLAN SECTION MODELS (P in SOAP)
# ============================================================================

class DiagnosticPlan(BaseModel):
    """Diagnostic test ordered"""
    test_name: str
    test_code: Optional[str] = None
    priority: Literal["urgent", "routine", "when_available"] = "routine"
    rationale: str
    ordered_date: date = Field(default_factory=date.today)
    expected_result_date: Optional[date] = None
    status: Literal["ordered", "pending", "completed", "cancelled"] = "ordered"

class Medication(BaseModel):
    """Medication prescribed"""
    name: str
    rxnorm_code: Optional[str] = None
    dosage: str
    frequency: MedicationFrequency
    route: Route = Route.ORAL
    duration: str  # e.g. "5 days", "2 weeks", "ongoing"
    indication: str
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    instructions: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    status: Literal["prescribed", "active", "stopped", "completed"] = "prescribed"

class NonPharmaceuticalIntervention(BaseModel):
    """Non-drug intervention"""
    intervention: str
    category: Literal["lifestyle", "physical", "behavioral", "diet"]
    instructions: str
    expected_duration: Optional[str] = None
    priority: Literal["high", "medium", "low"] = "medium"

class Procedure(BaseModel):
    """Medical procedure planned"""
    procedure_name: str
    snomed_code: Optional[str] = None
    indication: str
    scheduled_date: Optional[date] = None
    location: Optional[str] = None
    urgency: Literal["emergency", "urgent", "routine"] = "routine"
    pre_operative_notes: Optional[str] = None
    status: Literal["planned", "scheduled", "completed", "cancelled"] = "planned"

class PatientEducation(BaseModel):
    """Patient education provided"""
    topics: List[str] = Field(default_factory=list)
    education_provided: str
    patient_understanding: Literal["good", "fair", "poor"] = "good"
    education_materials: Optional[List[Dict[str, str]]] = None

class FollowUp(BaseModel):
    """Follow-up plan"""
    schedule_follow_up: bool = True
    follow_up_date: Optional[date] = None
    follow_up_type: Literal["in_person", "phone", "telehealth", "lab_work"] = "in_person"
    follow_up_with: Literal["same_doctor", "specialist", "other"] = "same_doctor"
    follow_up_reason: Optional[str] = None
    urgent_return_criteria: Optional[str] = None

class Referral(BaseModel):
    """Referral to specialist"""
    specialty_needed: str
    reason: str
    urgency: Literal["urgent", "routine"] = "routine"
    referred_to: Optional[str] = None  # Doctor name/ID
    referral_date: date = Field(default_factory=date.today)
    status: Literal["pending", "accepted", "completed", "cancelled"] = "pending"

class Disposition(BaseModel):
    """Patient disposition at end of visit"""
    disposition: Literal["discharge", "admit", "observe", "transfer"]
    disposition_location: str  # home, hospital, ICU, etc.
    discharge_date_time: Optional[datetime] = None
    discharge_instructions: Optional[str] = None
    restrictions: Optional[str] = None

class PlanSection(BaseModel):
    """Complete Plan (P) section of SOAP note"""
    diagnostic_plan: List[DiagnosticPlan] = Field(default_factory=list)
    
    medications: List[Medication] = Field(default_factory=list)
    non_pharmaceutical_interventions: List[NonPharmaceuticalIntervention] = Field(default_factory=list)
    procedures: List[Procedure] = Field(default_factory=list)
    
    patient_education: Optional[PatientEducation] = None
    follow_up: Optional[FollowUp] = None
    referrals: List[Referral] = Field(default_factory=list)
    disposition: Optional[Disposition] = None

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
    linked_to_case_section: Optional[Literal["subjective", "objective", "assessment", "plan"]] = None

class Amendment(BaseModel):
    """Amendment to case"""
    amendment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amended_at: datetime = Field(default_factory=datetime.utcnow)
    amended_by: str  # UUID
    reason: str  # Why amended
    changed_fields: Dict[str, Dict[str, Any]]  # {fieldName: {oldValue, newValue}}

class DoctorApproval(BaseModel):
    """Doctor approval workflow"""
    approved: bool = False
    approved_by: Optional[str] = None  # UUID
    approval_date: Optional[datetime] = None
    approval_notes: Optional[str] = None
    requires_patient_signature: bool = False

class PatientConsent(BaseModel):
    """Patient consent tracking"""
    consent_given: bool = False
    consent_date: Optional[datetime] = None
    consent_type: Literal["treatment", "data_sharing", "research"]

class AuditLog(BaseModel):
    """Audit trail entry"""
    action: Literal["created", "updated", "viewed", "approved", "amended", "shared"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    performed_by: str  # UUID
    ip_address: Optional[str] = None
    change_details: Optional[str] = None

class NLPExtraction(BaseModel):
    """NLP-extracted clinical entities"""
    conditions: Optional[List[Dict[str, Any]]] = None  # [{code, display, confidence}]
    medications: Optional[List[Dict[str, Any]]] = None
    lab_values: Optional[List[Dict[str, Any]]] = None
    procedures: Optional[List[Dict[str, Any]]] = None

class AIAnalysis(BaseModel):
    """AI/LLM analysis results"""
    generated: bool = False
    generated_at: Optional[datetime] = None
    model: Optional[str] = None
    summary: Optional[str] = None  # Patient-friendly summary
    key_insights: List[str] = Field(default_factory=list)
    risk_assessment: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    nlp_extracted_entities: Optional[NLPExtraction] = None

# ============================================================================
# MAIN CASE DOCUMENT MODEL
# ============================================================================

class CaseCreate(BaseModel):
    """Request model for creating case"""
    patient_id: str
    doctor_id: str
    encounter_id: Optional[str] = None
    
    case_type: CaseType = CaseType.ROUTINE
    chief_complaint: str = Field(..., max_length=500)
    
    subjective: Optional[SubjectiveSection] = None
    objective: Optional[ObjectiveSection] = None
    assessment: Optional[AssessmentSection] = None
    plan: Optional[PlanSection] = None

class CaseUpdate(BaseModel):
    """Request model for updating case (partial)"""
    status: Optional[CaseStatus] = None
    severity: Optional[SeverityLevel] = None
    
    subjective: Optional[SubjectiveSection] = None
    objective: Optional[ObjectiveSection] = None
    assessment: Optional[AssessmentSection] = None
    plan: Optional[PlanSection] = None

class Case(BaseModel):
    """Complete Case document (MongoDB + response model)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    
    # IDs
    patient_id: str
    doctor_id: str
    encounter_id: Optional[str] = None
    hospital_id: Optional[str] = None
    department_id: Optional[str] = None
    
    # Metadata
    case_type: CaseType = CaseType.ROUTINE
    status: CaseStatus = CaseStatus.OPEN
    severity: Optional[SeverityLevel] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    # SOAP Sections
    subjective: Optional[SubjectiveSection] = None
    objective: Optional[ObjectiveSection] = None
    assessment: Optional[AssessmentSection] = None
    plan: Optional[PlanSection] = None
    
    # Attachments & Notes
    attachments: List[Attachment] = Field(default_factory=list)
    doctor_notes: List[DoctorNote] = Field(default_factory=list)
    amendment_history: List[Amendment] = Field(default_factory=list)
    
    # Workflow
    approvals: Optional[DoctorApproval] = None
    patient_consent: Optional[PatientConsent] = None
    audit_trail: List[AuditLog] = Field(default_factory=list)
    
    # AI/LLM
    ai_analysis: Optional[AIAnalysis] = None
    
    # Metadata
    language: str = "en"
    tags: List[str] = Field(default_factory=list)
    
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
    linked_to_case_section: Optional[Literal["subjective", "objective", "assessment", "plan"]] = None

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
    amendment_history: Optional[List[Dict[str, Any]]] = None
    signature_data: Optional[Dict[str, Any]] = None

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
    cases: List[CaseResponse]

# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response model"""
    status_code: int
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None
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
