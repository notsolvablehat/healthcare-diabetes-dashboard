"""
Gemini 2.5 Flash client for AI operations.

Uses google-genai SDK with async support via client.aio
"""
import json

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, Field

from src.ai.models import ExtractedFeatures, PredictionResult

load_dotenv()

# Initialize Gemini client
# Uses GOOGLE_API_KEY from environment
client = genai.Client()

# Model configuration
MODEL_NAME = "gemini-2.5-flash"


# ============================================================================
# Response Models for Structured JSON Output
# ============================================================================

class CaseSummarySchema(BaseModel):
    """Schema for case summarization JSON response."""
    summary: str = Field(description="A 2-3 sentence overall summary of the patient case.")
    key_findings: list[str] = Field(description="List of key clinical findings from the case.")
    recommendations: list[str] = Field(description="List of recommendations for the healthcare provider.")


class InsightsSchema(BaseModel):
    """Schema for patient insights JSON response."""
    insights: list[str] = Field(description="General health observations based on patient data.")
    risk_factors: list[str] = Field(description="Potential risk factors identified from the data.")
    trends: list[str] = Field(description="Trends observed across multiple reports if available.")


# ============================================================================
# Feature Extraction from Medical Reports
# ============================================================================

FEATURE_EXTRACTION_PROMPT = """
You are a medical document analyzer. Extract clinical features from this medical report for diabetes risk assessment.

IMPORTANT RULES:
1. If a value is not explicitly mentioned, make a reasonable inference based on context or use these defaults:
   - hypertension: 0 (no)
   - heart_disease: 0 (no)
   - smoking_history: 0 (never)
2. For glucose, look for "fasting glucose", "FBS", "blood sugar", or similar terms
3. For HbA1c, look for "HbA1c", "glycated hemoglobin", "A1c", or similar
4. BMI might be calculated from height/weight if not directly stated
5. Gender: 0=Female, 1=Male, 2=Other
6. smoking_history: 0=never, 1=former, 2=current, 3=not current, 4=ever

Analyze this document and extract the features:
"""


async def extract_features_from_report(
    file_bytes: bytes,
    mime_type: str,
    patient_context: dict | None = None
) -> ExtractedFeatures:
    """
    Extract clinical features from a medical report using Gemini.
    Args:
        file_bytes: Raw file bytes (PDF or image)
        mime_type: MIME type of the file
        patient_context: Optional dict with known patient info (age, gender, etc.)
    Returns:
        ExtractedFeatures with 8 diabetes prediction features
    """
    # Build prompt with optional context
    prompt = FEATURE_EXTRACTION_PROMPT
    if patient_context:
        prompt += f"# IF DATA IS NOT AVAILABLE, DO NOT PUT SOME VALUE, INSTEAD PUT `N/A`\n\nKNOWN PATIENT CONTEXT:\n{json.dumps(patient_context, indent=2)}\n\nDocument:"

    # Create file part for multimodal input
    file_part = genai_types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type
    )

    # Call Gemini with async client and JSON schema
    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, file_part],
        config={
            "temperature": 0.1,  # Low temperature for structured extraction
            "response_mime_type": "application/json",
            "response_json_schema": ExtractedFeatures.model_json_schema(),
        }
    )

    # Parse and validate with Pydantic
    return ExtractedFeatures.model_validate_json(response.text)


# ============================================================================
# Narrative Generation
# ============================================================================

NARRATIVE_PROMPT = """
You are a medical AI assistant explaining diabetes risk assessment results to a healthcare provider.

Based on the following analysis, generate a clear, professional narrative explanation:

EXTRACTED FEATURES:
{features}

PREDICTION RESULT:
- Label: {label}
- Confidence: {confidence:.1%}

Write a 2-3 paragraph explanation that:
1. Summarizes the key clinical values (HbA1c, glucose, BMI)
2. Explains the prediction result and confidence level
3. Notes any concerning values or recommendations for follow-up

Keep the tone professional but accessible. Do not provide medical advice, only explain the analysis.
"""


async def generate_narrative(
    features: ExtractedFeatures,
    prediction: PredictionResult
) -> str:
    """
    Generate a human-readable narrative explanation of the analysis.
    Args:
        features: Extracted clinical features
        prediction: XGBoost prediction result
    Returns:
        Narrative text explanation
    """
    # Build feature summary (exclude raw_text)
    feature_dict = features.model_dump(exclude={"raw_text"})
    feature_str = "\n".join(f"- {k}: {v}" for k, v in feature_dict.items())

    prompt = NARRATIVE_PROMPT.format(
        features=feature_str,
        label=prediction.label,
        confidence=prediction.confidence
    )

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config=genai_types.GenerateContentConfig(
            temperature=0.7,  # Slightly higher for natural language
        )
    )

    return response.text


# ============================================================================
# Case Summarization
# ============================================================================

CASE_SUMMARY_PROMPT = """
You are a medical AI assistant summarizing a patient case for a healthcare provider.

CASE DATA:
{case_data}

Generate a structured summary with:
1. A 2-3 sentence overall summary
2. Key findings (bullet points)
3. Recommendations (bullet points)
"""


async def summarize_case(case_data: dict) -> CaseSummarySchema:
    """
    Generate an AI summary of an entire medical case.
    Args:
        case_data: Dictionary containing case details, notes, and reports
    Returns:
        CaseSummarySchema with summary, key_findings, and recommendations
    """
    prompt = CASE_SUMMARY_PROMPT.format(
        case_data=json.dumps(case_data, indent=2, default=str)
    )

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config={
            "temperature": 0.3,
            "response_mime_type": "application/json",
            "response_json_schema": CaseSummarySchema.model_json_schema(),
        }
    )

    return CaseSummarySchema.model_validate_json(response.text)


# ============================================================================
# RAG Question Answering
# ============================================================================

QA_PROMPT = """
You are a medical AI assistant answering questions about a patient's medical history.

PATIENT CONTEXT:
{context}

QUESTION: {question}

Provide a clear, accurate answer based ONLY on the provided context.
If the information is not available in the context, say so clearly.
Do not make up information or provide medical advice.
"""


async def answer_question(context: str, question: str) -> str:
    """
    Answer a question about patient data using provided context.
    Args:
        context: Relevant medical records/notes as text
        question: User's question
    Returns:
        Answer text
    """
    prompt = QA_PROMPT.format(context=context, question=question)

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config=genai_types.GenerateContentConfig(
            temperature=0.3,
        )
    )

    return response.text


# ============================================================================
# Patient Insights
# ============================================================================

INSIGHTS_PROMPT = """
You are a medical AI assistant analyzing a patient's health data for insights.

PATIENT DATA:
{patient_data}

HISTORICAL REPORTS:
{reports_summary}

Generate health insights including:
1. General health observations
2. Potential risk factors based on the data
3. Trends observed across reports (if multiple)
"""


async def generate_insights(patient_data: dict, reports_summary: str) -> InsightsSchema:
    """
    Generate health insights for a patient based on their data.
    Args:
        patient_data: Patient profile information
        reports_summary: Summary of patient's medical reports
    Returns:
        InsightsSchema with insights, risk_factors, and trends lists
    """
    prompt = INSIGHTS_PROMPT.format(
        patient_data=json.dumps(patient_data, indent=2, default=str),
        reports_summary=reports_summary
    )

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config={
            "temperature": 0.5,
            "response_mime_type": "application/json",
            "response_json_schema": InsightsSchema.model_json_schema(),
        }
    )

    return InsightsSchema.model_validate_json(response.text)
