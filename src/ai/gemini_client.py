"""
Gemini 2.5 Flash client for AI operations.

Uses google-genai SDK with async support via client.aio
"""
import json

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, Field

from src.ai.models import ExtractedFeatures, PredictionResult, ReportExtraction

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


class ChatTitleSchema(BaseModel):
    """Schema for chat title generation."""
    title: str = Field(description="Short descriptive title for the chat (max 20 chars)")


# ============================================================================
# Full Report Extraction (General Medical - not diabetes-specific)
# ============================================================================

REPORT_EXTRACTION_PROMPT = """
You are a medical document analyzer. Extract ALL relevant information from this medical report.

IMPORTANT RULES:
1. Extract EVERYTHING you can find in the document
2. If a value is not found, use "N/A" as the value
3. For lab results, extract ALL tests found with their values, units, reference ranges
4. Identify the report type (Lab Report, Prescription, Imaging, Discharge Summary, etc.)
5. Extract all diagnoses, medications, and recommendations mentioned
{keywords_hint}
Extract the complete medical data from this document:
"""


async def extract_report_data(
    file_bytes: bytes,
    mime_type: str,
) -> tuple[ReportExtraction, str]:
    """
    Extract complete medical data from a report using Gemini.
    Uses TF-IDF to identify important keywords first, then includes them
    in the extraction prompt to ensure nothing important is missed.
    Args:
        file_bytes: Raw file bytes (PDF or image)
        mime_type: MIME type of the file
    Returns:
        Tuple of (ReportExtraction structured data, raw_text)
    """
    from src.ai.text_analysis import extract_keywords_tfidf, format_keywords_for_prompt

    # Create file part for multimodal input
    file_part = genai_types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type
    )

    # First, extract raw text
    raw_text_response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            "Extract ALL text from this document verbatim. Include every word, number, and label you can see:",
            file_part
        ],
        config=genai_types.GenerateContentConfig(
            temperature=0.1,
        )
    )
    raw_text = raw_text_response.text

    # Extract important keywords using TF-IDF
    keywords = extract_keywords_tfidf(raw_text, top_n=25)
    keywords_hint = format_keywords_for_prompt(keywords)

    # Build prompt with keywords
    extraction_prompt = REPORT_EXTRACTION_PROMPT.format(keywords_hint=keywords_hint)

    # Then extract structured data with keyword hints
    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[extraction_prompt, file_part],
        config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
            "response_json_schema": ReportExtraction.model_json_schema(),
        }
    )

    extracted = ReportExtraction.model_validate_json(response.text)
    return extracted, raw_text


# ============================================================================
# Chat System Functions
# ============================================================================

CHAT_RESPONSE_PROMPT = """
You are a helpful medical AI assistant. You have access to the patient's medical records.

PATIENT MEDICAL CONTEXT:
{context}

CONVERSATION HISTORY:
{history}

USER MESSAGE: {message}

Provide a helpful, accurate response based on the patient's medical records.
- Be clear and professional
- Only reference information from the provided context
- If information is not available, say so clearly
- Do NOT provide medical advice or diagnoses
- Suggest consulting a doctor for medical decisions
"""


async def generate_chat_response(
    context: str,
    history: list[dict],
    message: str,
) -> str:
    """
    Generate a chat response with medical context and conversation history.
    Args:
        context: Pre-built context from patient reports (built once, reused)
        history: Last 10 messages as list of {"role": "user"|"assistant", "content": str}
        message: Current user message
    Returns:
        Assistant response text
    """
    # Format history
    history_str = ""
    for msg in history[-10:]:  # Limit to last 10 messages
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n\n"

    if not history_str:
        history_str = "(No previous messages)"

    prompt = CHAT_RESPONSE_PROMPT.format(
        context=context[:50000],  # Limit context to ~50k chars
        history=history_str,
        message=message
    )

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config=genai_types.GenerateContentConfig(
            temperature=0.7,
        )
    )

    return response.text


TITLE_GENERATION_PROMPT = """
Based on this conversation, generate a SHORT title (max 50 characters) that describes what the chat is about.

User asked: {question}
Assistant responded: {response}

Generate a concise, descriptive title:
"""


async def generate_chat_title(question: str, response: str) -> str:
    """
    Generate a short title for a chat based on the first Q&A exchange.
    Args:
        question: First user message
        response: First assistant response
    Returns:
        Short title string (max 50 chars)
    """
    prompt = TITLE_GENERATION_PROMPT.format(
        question=question[:500],
        response=response[:500]
    )

    result = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config={
            "temperature": 0.5,
            "response_mime_type": "application/json",
            "response_json_schema": ChatTitleSchema.model_json_schema(),
        }
    )

    title_data = ChatTitleSchema.model_validate_json(result.text)
    return title_data.title[:50]  # Ensure max 50 chars


# ============================================================================
# Legacy Functions (kept for compatibility)
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
    (Legacy function for diabetes prediction)
    """
    prompt = FEATURE_EXTRACTION_PROMPT
    if patient_context:
        prompt += f"\n\nKNOWN PATIENT CONTEXT:\n{json.dumps(patient_context, indent=2)}\n\nDocument:"

    file_part = genai_types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type
    )

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, file_part],
        config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
            "response_json_schema": ExtractedFeatures.model_json_schema(),
        }
    )

    return ExtractedFeatures.model_validate_json(response.text)


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
    """Generate a human-readable narrative explanation of the analysis."""
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
            temperature=0.7,
        )
    )

    return response.text


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
    """Generate an AI summary of an entire medical case."""
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
    """Answer a question about patient data using provided context."""
    prompt = QA_PROMPT.format(context=context, question=question)

    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt],
        config=genai_types.GenerateContentConfig(
            temperature=0.3,
        )
    )

    return response.text


INSIGHTS_PROMPT = """
You are a medical AI assistant analyzing a patient's health data for insights.

PATIENT DATA:
{patient_data}

HISTORICAL REPORTS:
{reports_summary}
{keywords_hint}
Generate health insights including:
1. General health observations
2. Potential risk factors based on the data
3. Trends observed across reports (if multiple)
"""


async def generate_insights(patient_data: dict, reports_summary: str) -> InsightsSchema:
    """Generate health insights for a patient based on their data."""
    from src.ai.text_analysis import extract_keywords_tfidf, format_keywords_for_prompt

    # Extract keywords from reports summary
    keywords = extract_keywords_tfidf(reports_summary, top_n=25)
    keywords_hint = format_keywords_for_prompt(keywords)

    prompt = INSIGHTS_PROMPT.format(
        patient_data=json.dumps(patient_data, indent=2, default=str),
        reports_summary=reports_summary,
        keywords_hint=keywords_hint
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
