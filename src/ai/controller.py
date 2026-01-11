"""
AI Controller - API routes for AI-powered analysis.
"""
import logging

from fastapi import APIRouter, Request, HTTPException, status

from src.ai.models import (
    AnalyzeReportResponse,
    AskRequest,
    AskResponse,
    CaseSummaryResponse,
    InsightsResponse,
    ExtractReportResponse,
    StartChatRequest,
    StartChatResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    ChatListResponse,
    AttachReportsRequest,
)
from src.ai.services import ai_service, extraction_service, chat_service
from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.database.mongo import MongoDb
from src.database.supabase import SupabaseClient
from src.rate_limiting import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# ============================================================================
# Report Extraction Endpoints
# ============================================================================

@router.post("/extract-report/{report_id}", response_model=ExtractReportResponse)
@limiter.limit("10/minute")
async def extract_report(
    request: Request,
    report_id: str,
    user: CurrentUser,
    db: DbSession,
    supabase: SupabaseClient,
    mongo_db: MongoDb,
):
    """
    Extract complete medical data from a report.
    
    Extracts all text, patient info, lab results, diagnoses, medications,
    and stores in MongoDB for later use in chat context.
    """
    logger.info(f"[AI] extract_report called | report_id={report_id} | user={user.user_id}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await extraction_service.extract_report(
        report_id=report_id,
        db=db,
        supabase=supabase,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role or "patient",
    )
    
    logger.info(f"[AI] extract_report complete | report_id={report_id} | type={result.extracted_data.report_type}")
    return result


# ============================================================================
# Chat Endpoints
# ============================================================================

@router.post("/chat/start", response_model=StartChatResponse)
@limiter.limit("10/minute")
async def start_chat(
    request: Request,
    body: StartChatRequest,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Start a new chat session.
    - For patients: automatically uses their own records
    - For doctors: requires patient_id of an assigned patient
    - Optionally attach specific reports to the chat
    """
    logger.info(f"[AI] start_chat called | user={user.user_id} | patient_id={body.patient_id}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await chat_service.start_chat(
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role or "patient",
        patient_id=body.patient_id,
        report_ids=body.report_ids,
    )
    
    logger.info(f"[AI] start_chat complete | chat_id={result.chat_id}")
    return result


@router.post("/chat/{chat_id}/message", response_model=ChatMessageResponse)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    chat_id: str,
    body: ChatMessageRequest,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Send a message in a chat and get AI response.
    
    - Context is built once on first message and reused
    - Title is generated after first message
    - Last 10 messages used for conversation history
    - Can optionally attach more reports with this message
    """
    logger.info(f"[AI] send_message called | chat_id={chat_id} | user={user.user_id} | msg_len={len(body.message)}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await chat_service.send_message(
        chat_id=chat_id,
        message=body.message,
        attach_report_ids=body.attach_report_ids,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
    )
    
    logger.info(f"[AI] send_message complete | chat_id={chat_id} | msg_id={result.message_id}")
    return result


@router.get("/chat/{chat_id}/history", response_model=ChatHistoryResponse)
@limiter.limit("30/minute")
async def get_chat_history(
    request: Request,
    chat_id: str,
    user: CurrentUser,
    mongo_db: MongoDb,
):
    """
    Get full chat history with all messages.
    """
    logger.info(f"[AI] get_chat_history called | chat_id={chat_id} | user={user.user_id}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await chat_service.get_history(
        chat_id=chat_id,
        mongo_db=mongo_db,
        user_id=user.user_id,
    )
    
    logger.info(f"[AI] get_chat_history complete | chat_id={chat_id} | messages={len(result.messages)}")
    return result


@router.get("/chats", response_model=ChatListResponse)
@limiter.limit("30/minute")
async def list_chats(
    request: Request,
    user: CurrentUser,
    mongo_db: MongoDb,
):
    """
    List all chats for the current user.
    """
    logger.info(f"[AI] list_chats called | user={user.user_id}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await chat_service.list_chats(
        mongo_db=mongo_db,
        user_id=user.user_id,
    )
    
    logger.info(f"[AI] list_chats complete | total={result.total}")
    return result


@router.delete("/chat/{chat_id}")
@limiter.limit("10/minute")
async def delete_chat(
    request: Request,
    chat_id: str,
    user: CurrentUser,
    mongo_db: MongoDb,
):
    """
    Delete a chat and all its messages.
    """
    logger.info(f"[AI] delete_chat called | chat_id={chat_id} | user={user.user_id}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await chat_service.delete_chat(
        chat_id=chat_id,
        mongo_db=mongo_db,
        user_id=user.user_id,
    )
    
    logger.info(f"[AI] delete_chat complete | chat_id={chat_id}")
    return result


@router.patch("/chat/{chat_id}/reports")
@limiter.limit("20/minute")
async def update_chat_reports(
    request: Request,
    chat_id: str,
    body: AttachReportsRequest,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb,
):
    """
    Add, remove, or replace attached reports in a chat.
    
    Actions:
    - add: Add new reports to existing
    - remove: Remove specified reports
    - replace: Replace all with new reports
    """
    logger.info(f"[AI] update_chat_reports called | chat_id={chat_id} | action={body.action}")
    
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    result = await chat_service.update_reports(
        chat_id=chat_id,
        report_ids=body.report_ids,
        action=body.action,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
    )
    
    logger.info(f"[AI] update_chat_reports complete | chat_id={chat_id}")
    return result


# ============================================================================
# Legacy Endpoints (kept for compatibility)
# ============================================================================

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
    Analyze a single uploaded report (PDF/Image) - Legacy diabetes prediction.
    """
    logger.info(f"[AI] analyze_report called | report_id={report_id} | user={user.user_id}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    result = await ai_service.analyze_report(
        report_id=report_id,
        db=db,
        supabase=supabase,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] analyze_report complete | report_id={report_id}")
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
    """
    logger.info(f"[AI] summarize_case called | case_id={case_id} | user={user.user_id}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    result = await ai_service.summarize_case(
        case_id=case_id,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] summarize_case complete | case_id={case_id}")
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
    RAG-based Q&A about a patient's medical history (Legacy - use chat instead).
    """
    logger.info(f"[AI] ask called | patient_id={body.patient_id} | user={user.user_id}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    result = await ai_service.ask(
        patient_id=body.patient_id,
        question=body.question,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] ask complete | patient_id={body.patient_id}")
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
    """
    logger.info(f"[AI] get_insights called | patient_id={patient_id} | user={user.user_id}")

    if not user or not user.role or not user.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    result = await ai_service.get_insights(
        patient_id=patient_id,
        db=db,
        mongo_db=mongo_db,
        user_id=user.user_id,
        user_role=user.role,
    )

    logger.info(f"[AI] get_insights complete | patient_id={patient_id}")
    return result

