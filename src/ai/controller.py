"""
AI Controller - API routes for AI-powered analysis.
"""
import logging

from fastapi import APIRouter, Request, HTTPException

from src.ai.models import (
    AnalyzeReportResponse,
    AskRequest,
    AskResponse,
    CaseSummaryResponse,
    InsightsResponse,
)
from src.ai.services import ai_service
from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.mongo import MongoDb
from src.database.supabase import SupabaseClient
from src.rate_limiting import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze-report/{report_id}", response_model=AnalyzeReportResponse)
@limiter.limit("10/minute")
async def analyze_report(
    request: Request,
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
    mongo_db: MongoDb,
):
    """
    Analyze a single uploaded report (PDF/Image).
    Pipeline:
    1. Downloads report from Supabase Storage
    2. Extracts clinical features using Gemini 2.5 Flash
    3. Runs XGBoost diabetes prediction
    4. Generates narrative explanation
    5. Saves analysis to MongoDB
    Returns extracted features, prediction, and narrative explanation.
    """
    logger.info(f"[AI] analyze_report called | report_id={report_id} | user={user.user_id} | role={user.role}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=404, detail="User not found.")


    result = await ai_service.analyze_report(
        report_id=report_id,
        db=db,
        supabase=supabase,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] analyze_report complete | report_id={report_id} | prediction={result.prediction.label} | confidence={result.prediction.confidence:.2%}")
    return result


@router.post("/summarize-case/{case_id}", response_model=CaseSummaryResponse)
@limiter.limit("5/minute")
async def summarize_case(
    request: Request,
    case_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Generate AI summary of an entire case including all reports and doctor notes.
    Returns structured summary with key findings and recommendations.
    """
    logger.info(f"[AI] summarize_case called | case_id={case_id} | user={user.user_id} | role={user.role}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await ai_service.summarize_case(
        case_id=case_id,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] summarize_case complete | case_id={case_id} | findings_count={len(result.key_findings)}")
    return result


@router.post("/ask", response_model=AskResponse)
@limiter.limit("20/minute")
async def ask_question(
    request: Request,
    body: AskRequest,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    RAG-based Q&A about a patient's medical history.
    Uses analyzed reports as context to answer questions.
    """
    logger.info(f"[AI] ask called | patient_id={body.patient_id} | user={user.user_id} | question_len={len(body.question)}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await ai_service.ask(
        patient_id=body.patient_id,
        question=body.question,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] ask complete | patient_id={body.patient_id} | sources_count={len(result.sources)}")
    return result


@router.get("/insights/{patient_id}", response_model=InsightsResponse)
@limiter.limit("10/minute")
async def get_insights(
    request: Request,
    patient_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Get AI-generated health insights and trends for a patient.
    Analyzes all available reports to identify patterns and risk factors.
    """
    logger.info(f"[AI] get_insights called | patient_id={patient_id} | user={user.user_id} | role={user.role}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await ai_service.get_insights(
        patient_id=patient_id,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] get_insights complete | patient_id={patient_id} | insights_count={len(result.insights)} | risks_count={len(result.risk_factors)}")
    return result
