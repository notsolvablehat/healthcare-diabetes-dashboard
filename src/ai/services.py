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


# Singleton instance
ai_service = AIService()
