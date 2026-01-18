"""
AI Analysis Service - Core pipeline orchestration.

Handles the full analysis workflow:
1. Fetch report from Postgres
2. Download file from Supabase
3. Extract features via Gemini
4. Predict with XGBoost
5. Generate narrative via Gemini
6. Save to MongoDB
7. Update Postgres with mongo_analysis_id
"""
import logging
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.orm import Session
from supabase import Client

from src.ai.gemini_client import (
    answer_question,
    extract_features_from_report,
    generate_insights,
    generate_narrative,
)
from src.ai.gemini_client import (
    summarize_case as gemini_summarize_case,
)
from src.ai.ml_models import diabetes_predictor
from src.ai.models import (
    AnalysisDocument,
    AnalyzeReportResponse,
    AskResponse,
    CaseSummaryResponse,
    InsightsResponse,
)
from src.schemas.cases import Case as CaseORM
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Assignment, Patient

logger = logging.getLogger(__name__)

# Supabase bucket name
BUCKET_NAME = "medical-reports"


def check_doctor_patient_access(db: Session, doctor_id: str, patient_id: str) -> bool:
    """Check if a doctor has an active assignment with a patient."""
    assignment = db.query(Assignment).filter(
        Assignment.doctor_user_id == doctor_id,
        Assignment.patient_user_id == patient_id,
        Assignment.is_active
    ).first()
    return assignment is not None


class AIService:
    """Service for AI-powered analysis operations."""

    async def analyze_report(
        self,
        report_id: str,
        db: Session,
        supabase: Client,
        mongo_db: AsyncDatabase,
        user_id: str,
        user_role: str,
    ) -> AnalyzeReportResponse:
        """
        Full analysis pipeline for a medical report.
        Steps:
        1. Fetch report metadata from Postgres
        2. Download file from Supabase Storage
        3. Extract features using Gemini
        4. Run XGBoost prediction
        5. Generate narrative explanation
        6. Save full analysis to MongoDB
        7. Update report with mongo_analysis_id
        """
        logger.info(f"[Service] Starting analyze_report pipeline | report_id={report_id}")

        # 1. Fetch report from Postgres
        logger.debug("[Service] Step 1: Fetching report from Postgres")
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
        if not report:
            logger.warning(f"[Service] Report not found | report_id={report_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found"
            )

        logger.info(f"[Service] Report found | file={report.file_name} | type={report.content_type} | patient={report.patient_id}")

        # Access control: Check if user can access this report
        if user_role == "patient" and report.patient_id != user_id:
            logger.warning(f"[Service] Access denied | user={user_id} tried to access patient={report.patient_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only analyze your own reports"
            )

        if user_role == "doctor":
            if not check_doctor_patient_access(db, user_id, report.patient_id):
                logger.warning(f"[Service] Doctor access denied | doctor={user_id} patient={report.patient_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only analyze reports of your assigned patients"
                )

        # 2. Download file from Supabase
        logger.debug(f"[Service] Step 2: Downloading file from Supabase | path={report.storage_path}")
        try:
            file_response = supabase.storage.from_(BUCKET_NAME).download(report.storage_path)
            file_bytes = file_response
            logger.info(f"[Service] File downloaded | size={len(file_bytes)} bytes")
        except Exception as e:
            logger.error(f"[Service] Supabase download failed | error={str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to download report from storage: {str(e)}"
            ) from e

        # Get patient context if available
        patient_context = self._get_patient_context(db, report.patient_id)
        logger.debug(f"[Service] Patient context: {patient_context}")

        # 3. Extract features using Gemini
        logger.info("[Service] Step 3: Extracting features via Gemini 2.5 Flash")
        try:
            features = await extract_features_from_report(
                file_bytes=file_bytes,
                mime_type=report.content_type,
                patient_context=patient_context
            )
            logger.info(f"[Service] Features extracted | HbA1c={features.HbA1c_level} | glucose={features.blood_glucose_level} | bmi={features.bmi}")
        except Exception as e:
            logger.error(f"[Service] Feature extraction failed | error={str(e)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Feature extraction failed: {str(e)}"
            ) from e

        # 4. Run XGBoost prediction
        logger.info("[Service] Step 4: Running XGBoost prediction")
        prediction = diabetes_predictor.predict(features)
        logger.info(f"[Service] Prediction complete | label={prediction.label} | confidence={prediction.confidence:.2%}")

        # 5. Generate narrative explanation
        logger.info("[Service] Step 5: Generating narrative via Gemini")
        try:
            narrative = await generate_narrative(features, prediction)
            logger.info(f"[Service] Narrative generated | length={len(narrative)} chars")
        except Exception as e:
            logger.warning(f"[Service] Narrative generation failed, using fallback | error={str(e)}")
            # Non-fatal: use a default narrative if generation fails
            narrative = f"Analysis complete. Prediction: {prediction.label} with {prediction.confidence:.1%} confidence."

        # 6. Save to MongoDB
        logger.info("[Service] Step 6: Saving analysis to MongoDB")
        analysis_doc = AnalysisDocument(
            report_id=report_id,
            raw_text=features.raw_text,
            extracted_features=features.model_dump(exclude={"raw_text"}),
            prediction=prediction.model_dump(),
            narrative=narrative,
            created_at=datetime.utcnow()
        )

        mongo_result = await mongo_db.report_analysis.insert_one(
            analysis_doc.model_dump()
        )
        mongo_analysis_id = str(mongo_result.inserted_id)
        logger.info(f"[Service] MongoDB document created | _id={mongo_analysis_id}")

        # 7. Update Postgres report with mongo_analysis_id
        logger.debug("[Service] Step 7: Updating Postgres report with mongo_analysis_id")
        report.mongo_analysis_id = mongo_analysis_id
        db.commit()
        logger.info(f"[Service] Postgres updated | report.mongo_analysis_id={mongo_analysis_id}")

        # Notify patient
        from src.notifications.services import notify_report_analyzed
        notify_report_analyzed(db, str(report.patient_id), report.id, report.file_name)

        logger.info(f"[Service] analyze_report pipeline COMPLETE | report_id={report_id}")

        return AnalyzeReportResponse(
            report_id=report_id,
            status="completed",
            extracted_features=features,
            prediction=prediction,
            narrative=narrative,
            mongo_analysis_id=mongo_analysis_id,
            analyzed_at=datetime.utcnow()
        )

    async def summarize_case(
        self,
        case_id: str,
        db: Session,
        mongo_db: AsyncDatabase,
        user_id: str,
        user_role: str,
    ) -> CaseSummaryResponse:
        """
        Generate AI summary of an entire case including reports and notes.
        """
        logger.info(f"[Service] Starting summarize_case | case_id={case_id}")

        # Fetch case from Postgres
        case = db.query(CaseORM).filter(CaseORM.case_id == case_id).first()
        if not case:
            logger.warning(f"[Service] Case not found | case_id={case_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found"
            )

        logger.info(f"[Service] Case found | status={case.status} | patient={case.patient_id}")

        # Access control
        if user_role == "patient" and str(case.patient_id) != user_id:
            logger.warning(f"[Service] Access denied for patient | user={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only summarize your own cases"
            )
        if user_role == "doctor" and str(case.doctor_id) != user_id:
            logger.warning(f"[Service] Access denied for doctor | user={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only summarize cases assigned to you"
            )

        # Fetch case details from MongoDB
        logger.debug(f"[Service] Fetching case from MongoDB | mongo_case_id={case.mongo_case_id}")
        mongo_case = None
        if case.mongo_case_id:
            mongo_case = await mongo_db.cases.find_one({"_id": ObjectId(case.mongo_case_id)})

        # Fetch associated reports
        reports = db.query(ReportORM).filter(ReportORM.case_id == case_id).all()
        logger.info(f"[Service] Found {len(reports)} reports for case")

        # Fetch any existing analyses
        analyses = []
        for report in reports:
            if report.mongo_analysis_id:
                analysis = await mongo_db.report_analysis.find_one(
                    {"_id": ObjectId(report.mongo_analysis_id)}
                )
                if analysis:
                    analyses.append(analysis)
        logger.info(f"[Service] Found {len(analyses)} existing analyses")

        # Build case data for summarization
        case_data = {
            "case_id": case_id,
            "status": case.status,
            "created_at": str(case.created_at),
            "mongo_details": mongo_case,
            "reports_count": len(reports),
            "analyses": [
                {
                    "prediction": a.get("prediction"),
                    "narrative": a.get("narrative"),
                }
                for a in analyses
            ]
        }

        # Generate summary via Gemini
        logger.info("[Service] Generating case summary via Gemini")
        try:
            result = await gemini_summarize_case(case_data)
            logger.info(f"[Service] Summary generated | findings={len(result.key_findings)} | recommendations={len(result.recommendations)}")
        except Exception as e:
            logger.error(f"[Service] Case summarization failed | error={str(e)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Case summarization failed: {str(e)}"
            ) from e

        logger.info(f"[Service] summarize_case COMPLETE | case_id={case_id}")

        return CaseSummaryResponse(
            case_id=case_id,
            summary=result.summary,
            key_findings=result.key_findings,
            recommendations=result.recommendations,
            generated_at=datetime.utcnow()
        )

    async def ask(
        self,
        patient_id: str,
        question: str,
        db: Session,
        mongo_db: AsyncDatabase,
        user_id: str,
        user_role: str,
    ) -> AskResponse:
        """
        RAG-based Q&A about a patient's medical history.
        """
        logger.info(f"[Service] Starting ask | patient_id={patient_id} | question='{question[:50]}...'")

        # Access control
        if user_role == "patient" and patient_id != user_id:
            logger.warning(f"[Service] Access denied | user={user_id} tried to query patient={patient_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only ask about your own records"
            )

        if user_role == "doctor":
            if not check_doctor_patient_access(db, user_id, patient_id):
                logger.warning(f"[Service] Doctor Q&A access denied | doctor={user_id} patient={patient_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only ask about your assigned patients"
                )

        # Build context from patient's reports and analyses
        reports = db.query(ReportORM).filter(ReportORM.patient_id == patient_id).all()
        logger.info(f"[Service] Found {len(reports)} reports for patient")

        context_parts = []
        source_ids = []

        for report in reports:
            if report.mongo_analysis_id:
                analysis = await mongo_db.report_analysis.find_one(
                    {"_id": ObjectId(report.mongo_analysis_id)}
                )
                if analysis:
                    context_parts.append(
                        f"Report {report.id} ({report.file_name}):\n"
                        f"- Features: {analysis.get('extracted_features')}\n"
                        f"- Prediction: {analysis.get('prediction')}\n"
                        f"- Narrative: {analysis.get('narrative')}\n"
                    )
                    source_ids.append(report.id)

        logger.info(f"[Service] Built context from {len(source_ids)} analyzed reports")

        if not context_parts:
            logger.warning(f"[Service] No analyzed reports found for patient={patient_id}")
            return AskResponse(
                answer="No analyzed reports found for this patient. Please analyze some reports first.",
                sources=[]
            )

        context = "\n\n".join(context_parts)
        logger.debug(f"[Service] Context length: {len(context)} chars")

        # Get answer from Gemini
        logger.info("[Service] Getting answer from Gemini")
        try:
            answer = await answer_question(context, question)
            logger.info(f"[Service] Answer received | length={len(answer)} chars")
        except Exception as e:
            logger.error(f"[Service] Q&A failed | error={str(e)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Q&A failed: {str(e)}"
            ) from e

        logger.info(f"[Service] ask COMPLETE | sources={len(source_ids)}")
        return AskResponse(answer=answer, sources=source_ids)

    async def get_insights(
        self,
        patient_id: str,
        db: Session,
        mongo_db: AsyncDatabase,
        user_id: str,
        user_role: str,
    ) -> InsightsResponse:
        """
        Generate AI-powered health insights for a patient.
        """
        logger.info(f"[Service] Starting get_insights | patient_id={patient_id}")

        # Access control
        if user_role == "patient" and patient_id != user_id:
            logger.warning(f"[Service] Access denied | user={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own insights"
            )

        if user_role == "doctor":
            if not check_doctor_patient_access(db, user_id, patient_id):
                logger.warning(f"[Service] Doctor insights access denied | doctor={user_id} patient={patient_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view insights of your assigned patients"
                )

        # Get patient profile
        patient = db.query(Patient).filter(Patient.user_id == patient_id).first()
        patient_data = {}
        if patient:
            patient_data = {
                "medical_history": patient.medical_history,
                "allergies": patient.allergies,
                "gender": patient.gender,
                "date_of_birth": str(patient.date_of_birth) if patient.date_of_birth else None,
            }
            logger.debug("[Service] Patient profile loaded")
        else:
            logger.debug("[Service] No patient profile found")

        # Build reports summary
        reports = db.query(ReportORM).filter(ReportORM.patient_id == patient_id).all()
        logger.info(f"[Service] Found {len(reports)} reports")

        reports_summary_parts = []
        for report in reports:
            if report.mongo_analysis_id:
                analysis = await mongo_db.report_analysis.find_one(
                    {"_id": ObjectId(report.mongo_analysis_id)}
                )
                if analysis:
                    reports_summary_parts.append(
                        f"Date: {report.created_at}\n"
                        f"Prediction: {analysis.get('prediction', {}).get('label')}\n"
                        f"HbA1c: {analysis.get('extracted_features', {}).get('HbA1c_level')}\n"
                        f"Glucose: {analysis.get('extracted_features', {}).get('blood_glucose_level')}\n"
                    )

        reports_summary = "\n---\n".join(reports_summary_parts) if reports_summary_parts else "No analyzed reports available."
        logger.info(f"[Service] Built summary from {len(reports_summary_parts)} analyzed reports")

        # Generate insights
        logger.info("[Service] Generating insights via Gemini")
        try:
            result = await generate_insights(patient_data, reports_summary)
            logger.info(f"[Service] Insights generated | insights={len(result.insights)} | risks={len(result.risk_factors)} | trends={len(result.trends)}")
        except Exception as e:
            logger.error(f"[Service] Insights generation failed | error={str(e)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Insights generation failed: {str(e)}"
            ) from e

        logger.info(f"[Service] get_insights COMPLETE | patient_id={patient_id}")

        return InsightsResponse(
            patient_id=patient_id,
            insights=result.insights,
            risk_factors=result.risk_factors,
            trends=result.trends,
            generated_at=datetime.utcnow()
        )

    def _get_patient_context(self, db: Session, patient_id: str) -> dict | None:
        """Get patient info to provide context for feature extraction."""
        patient = db.query(Patient).filter(Patient.user_id == patient_id).first()
        if not patient:
            return None

        return {
            "gender": patient.gender,
            "date_of_birth": str(patient.date_of_birth) if patient.date_of_birth else None,
            "medical_history": patient.medical_history,
        }


# ============================================================================
# Report Extraction Service
# ============================================================================

class ExtractionService:
    """Service for extracting data from medical reports."""

    async def extract_report(
        self,
        report_id: str,
        db: Session,
        supabase: Client,
        mongo_db: AsyncDatabase,
        user_id: str,
        user_role: str,
    ):
        """
        Extract complete medical data from a report.
        """
        import time

        from src.ai.gemini_client import extract_report_data
        from src.ai.models import AnalysisDocument, ExtractReportResponse

        start_time = time.time()
        logger.info(f"[Extraction] Starting | report_id={report_id}")

        # Fetch report
        report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Report {report_id} not found")

        # Access control
        if user_role == "patient" and report.patient_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if user_role == "doctor" and not check_doctor_patient_access(db, user_id, report.patient_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Download file
        logger.info(f"[Extraction] Downloading file | path={report.storage_path}")
        try:
            file_bytes = supabase.storage.from_(BUCKET_NAME).download(report.storage_path)
        except Exception as e:
            logger.error(f"[Extraction] Download failed | error={e}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

        # Extract data using Gemini
        logger.info("[Extraction] Calling Gemini for extraction")
        try:
            extracted_data, raw_text = await extract_report_data(file_bytes, report.content_type)
            logger.info(f"[Extraction] Data extracted | type={extracted_data.report_type}")
        except Exception as e:
            logger.error(f"[Extraction] Gemini extraction failed | error={e}")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

        processing_time = int((time.time() - start_time) * 1000)

        # Save to MongoDB
        doc = AnalysisDocument(
            report_id=report_id,
            patient_id=report.patient_id,
            status="completed",
            raw_text=raw_text,
            extracted_data=extracted_data.model_dump(),
            processing_time_ms=processing_time,
            created_at=datetime.utcnow()
        )

        result = await mongo_db.report_analysis.insert_one(doc.model_dump())
        mongo_id = str(result.inserted_id)
        logger.info(f"[Extraction] Saved to MongoDB | _id={mongo_id}")

        # Update Postgres
        report.mongo_analysis_id = mongo_id
        db.commit()

        logger.info(f"[Extraction] COMPLETE | report_id={report_id} | time={processing_time}ms")

        return ExtractReportResponse(
            report_id=report_id,
            status="completed",
            extracted_data=extracted_data,
            raw_text=raw_text,
            mongo_analysis_id=mongo_id,
            processing_time_ms=processing_time,
            extracted_at=datetime.utcnow()
        )

    async def extract_report_background(
        self,
        report_id: str,
        patient_id: str,
        storage_path: str,
        content_type: str,
        supabase: Client,
        mongo_db: AsyncDatabase,
        db: Session,
    ):
        """
        Background task for extracting report data after upload confirmation.
        """
        import time

        from src.ai.gemini_client import extract_report_data
        from src.ai.models import AnalysisDocument

        start_time = time.time()
        logger.info(f"[Background Extraction] Starting | report_id={report_id}")

        try:
            # Download file
            file_bytes = supabase.storage.from_(BUCKET_NAME).download(storage_path)
            logger.info(f"[Background Extraction] Downloaded | size={len(file_bytes)}")

            # Extract
            extracted_data, raw_text = await extract_report_data(file_bytes, content_type)
            processing_time = int((time.time() - start_time) * 1000)

            # Save to MongoDB
            doc = AnalysisDocument(
                report_id=report_id,
                patient_id=patient_id,
                status="completed",
                raw_text=raw_text,
                extracted_data=extracted_data.model_dump(),
                processing_time_ms=processing_time,
                created_at=datetime.utcnow()
            )

            result = await mongo_db.report_analysis.insert_one(doc.model_dump())
            mongo_id = str(result.inserted_id)

            # Update Postgres
            report = db.query(ReportORM).filter(ReportORM.id == report_id).first()
            if report:
                report.mongo_analysis_id = mongo_id
                db.commit()

                # Notify patient
                from src.notifications.services import notify_report_analyzed
                notify_report_analyzed(db, str(report.patient_id), report.id, report.file_name)

            logger.info(f"[Background Extraction] COMPLETE | report_id={report_id} | time={processing_time}ms")

        except Exception as e:
            logger.error(f"[Background Extraction] FAILED | report_id={report_id} | error={e}")
            # Save error status
            try:
                await mongo_db.report_analysis.insert_one({
                    "report_id": report_id,
                    "patient_id": patient_id,
                    "status": "failed",
                    "error": str(e),
                    "created_at": datetime.utcnow()
                })
            except Exception:
                pass


# ============================================================================
# Chat Service
# ============================================================================

class ChatService:
    """Service for chat operations with context stored once."""

    async def start_chat(
        self,
        db: Session,
        mongo_db: AsyncDatabase,
        user_id: str,
        user_role: str,
        patient_id: str | None,
        report_ids: list[str] | None,
    ):
        """Create a new chat session."""
        import uuid

        from src.ai.models import ChatDocument, StartChatResponse

        # Determine patient_id
        if user_role == "patient":
            patient_id = user_id
        elif not patient_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id is required for doctors")
        else:
            # Verify doctor access
            if not check_doctor_patient_access(db, user_id, patient_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this patient")

        # Validate report_ids if provided
        attached_report_ids = []
        if report_ids:
            for rid in report_ids:
                report = db.query(ReportORM).filter(ReportORM.id == rid, ReportORM.patient_id == patient_id).first()
                if report:
                    attached_report_ids.append(rid)

        chat_id = str(uuid.uuid4())
        now = datetime.utcnow()

        doc = ChatDocument(
            chat_id=chat_id,
            user_id=user_id,
            user_role=user_role,
            patient_id=patient_id,
            title=None,
            attached_report_ids=attached_report_ids,
            context="",  # Built on first message
            messages=[],
            created_at=now,
            updated_at=now
        )

        await mongo_db.chats.insert_one(doc.model_dump())
        logger.info(f"[Chat] Created | chat_id={chat_id} | patient={patient_id}")

        return StartChatResponse(
            chat_id=chat_id,
            patient_id=patient_id,
            attached_report_ids=attached_report_ids,
            created_at=now
        )

    async def send_message(
        self,
        chat_id: str,
        message: str,
        attach_report_ids: list[str] | None,
        db: Session,
        mongo_db: AsyncDatabase,
        user_id: str,
    ):
        """Send a message and get AI response."""
        import uuid

        from src.ai.gemini_client import generate_chat_response, generate_chat_title
        from src.ai.models import ChatMessageResponse

        # Fetch chat
        chat = await mongo_db.chats.find_one({"chat_id": chat_id})
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        if chat["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chat")

        # Attach new reports if provided
        if attach_report_ids:
            existing = set(chat.get("attached_report_ids", []))
            for rid in attach_report_ids:
                report = db.query(ReportORM).filter(
                    ReportORM.id == rid,
                    ReportORM.patient_id == chat["patient_id"]
                ).first()
                if report:
                    existing.add(rid)
            await mongo_db.chats.update_one(
                {"chat_id": chat_id},
                {"$set": {"attached_report_ids": list(existing)}}
            )
            chat["attached_report_ids"] = list(existing)

        now = datetime.utcnow()
        messages = chat.get("messages", [])
        is_first_message = len(messages) == 0

        # Build context on first message only
        context = chat.get("context", "")
        if is_first_message or not context:
            logger.info(f"[Chat] Building context for first message | chat_id={chat_id}")
            context = await self._build_context(
                db, mongo_db,
                chat["patient_id"],
                chat.get("attached_report_ids", [])
            )
            await mongo_db.chats.update_one(
                {"chat_id": chat_id},
                {"$set": {"context": context}}
            )

        # Get AI response
        logger.info(f"[Chat] Generating response | chat_id={chat_id}")
        try:
            response_text = await generate_chat_response(context, messages, message)
        except Exception as e:
            logger.error(f"[Chat] Response generation failed | error={e}")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

        # Generate title on first message
        title = None
        if is_first_message:
            try:
                title = await generate_chat_title(message, response_text)
                await mongo_db.chats.update_one(
                    {"chat_id": chat_id},
                    {"$set": {"title": title}}
                )
                logger.info(f"[Chat] Title generated | title={title}")
            except Exception as e:
                logger.warning(f"[Chat] Title generation failed | error={e}")

        # Save messages
        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())

        user_msg = {
            "id": user_msg_id,
            "role": "user",
            "content": message,
            "timestamp": now.isoformat()
        }
        assistant_msg = {
            "id": assistant_msg_id,
            "role": "assistant",
            "content": response_text,
            "sources": chat.get("attached_report_ids", []),
            "timestamp": now.isoformat()
        }

        await mongo_db.chats.update_one(
            {"chat_id": chat_id},
            {
                "$push": {"messages": {"$each": [user_msg, assistant_msg]}},
                "$set": {"updated_at": now}
            }
        )

        logger.info(f"[Chat] Message saved | chat_id={chat_id} | msg_id={assistant_msg_id}")

        return ChatMessageResponse(
            message_id=assistant_msg_id,
            response=response_text,
            sources=chat.get("attached_report_ids", []),
            title=title,
            timestamp=now
        )

    async def get_history(self, chat_id: str, mongo_db: AsyncDatabase, user_id: str):
        """Get full chat history."""
        from src.ai.models import ChatHistoryResponse, ChatMessage

        chat = await mongo_db.chats.find_one({"chat_id": chat_id})
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        if chat["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chat")

        messages = [
            ChatMessage(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]) if isinstance(m["timestamp"], str) else m["timestamp"],
                sources=m.get("sources")
            )
            for m in chat.get("messages", [])
        ]

        return ChatHistoryResponse(
            chat_id=chat_id,
            patient_id=chat["patient_id"],
            title=chat.get("title"),
            attached_report_ids=chat.get("attached_report_ids", []),
            messages=messages,
            created_at=chat["created_at"],
            updated_at=chat["updated_at"]
        )

    async def list_chats(self, mongo_db: AsyncDatabase, user_id: str):
        """List all chats for a user."""
        from src.ai.models import ChatListItem, ChatListResponse

        cursor = mongo_db.chats.find({"user_id": user_id}).sort("updated_at", -1)
        chats = await cursor.to_list(length=100)

        items = [
            ChatListItem(
                chat_id=c["chat_id"],
                patient_id=c["patient_id"],
                title=c.get("title"),
                message_count=len(c.get("messages", [])),
                created_at=c["created_at"],
                updated_at=c["updated_at"]
            )
            for c in chats
        ]

        return ChatListResponse(total=len(items), chats=items)

    async def delete_chat(self, chat_id: str, mongo_db: AsyncDatabase, user_id: str):
        """Delete a chat."""
        chat = await mongo_db.chats.find_one({"chat_id": chat_id})
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        if chat["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chat")

        await mongo_db.chats.delete_one({"chat_id": chat_id})
        logger.info(f"[Chat] Deleted | chat_id={chat_id}")
        return {"status": "deleted", "chat_id": chat_id}

    async def update_reports(
        self,
        chat_id: str,
        report_ids: list[str],
        action: str,
        db: Session,
        mongo_db: AsyncDatabase,
        user_id: str,
    ):
        """Attach/detach reports from a chat."""
        chat = await mongo_db.chats.find_one({"chat_id": chat_id})
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        if chat["user_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chat")

        # Validate report_ids belong to patient
        valid_ids = []
        for rid in report_ids:
            report = db.query(ReportORM).filter(
                ReportORM.id == rid,
                ReportORM.patient_id == chat["patient_id"]
            ).first()
            if report:
                valid_ids.append(rid)

        current = set(chat.get("attached_report_ids", []))

        if action == "add":
            current.update(valid_ids)
        elif action == "remove":
            current -= set(valid_ids)
        elif action == "replace":
            current = set(valid_ids)

        await mongo_db.chats.update_one(
            {"chat_id": chat_id},
            {"$set": {"attached_report_ids": list(current), "updated_at": datetime.utcnow()}}
        )

        logger.info(f"[Chat] Reports updated | chat_id={chat_id} | action={action} | count={len(current)}")
        return {"status": "updated", "attached_report_ids": list(current)}

    async def _build_context(
        self,
        db: Session,
        mongo_db: AsyncDatabase,
        patient_id: str,
        report_ids: list[str],
    ) -> str:
        """Build context from patient reports (called once on first message)."""
        context_parts = []

        # If specific reports attached, use those
        if report_ids:
            for rid in report_ids:
                analysis = await mongo_db.report_analysis.find_one({"report_id": rid})
                if analysis:
                    report = db.query(ReportORM).filter(ReportORM.id == rid).first()
                    context_parts.append(
                        f"=== Report: {report.file_name if report else rid} ===\n"
                        f"Raw Text:\n{analysis.get('raw_text', '')[:5000]}\n\n"
                        f"Extracted Data:\n{analysis.get('extracted_data', {})}\n"
                    )
        else:
            # Use all patient reports
            reports = db.query(ReportORM).filter(ReportORM.patient_id == patient_id).all()
            for report in reports[:10]:  # Limit to 10 reports
                if report.mongo_analysis_id:
                    analysis = await mongo_db.report_analysis.find_one(
                        {"_id": ObjectId(report.mongo_analysis_id)}
                    )
                    if analysis:
                        context_parts.append(
                            f"=== Report: {report.file_name} ===\n"
                            f"Raw Text:\n{analysis.get('raw_text', '')[:5000]}\n\n"
                            f"Extracted Data:\n{analysis.get('extracted_data', {})}\n"
                        )

        return "\n\n".join(context_parts)[:50000]  # Limit total context


# Singleton instances
ai_service = AIService()
extraction_service = ExtractionService()
chat_service = ChatService()

