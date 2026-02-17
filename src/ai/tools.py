"""
LLM Tool Calling Framework - Tool Registry and Executors

This module defines all callable tools that the LLM can invoke during chat conversations.
Each tool is a Python function with Pydantic model validation for inputs and outputs.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.ai.gemini_client import generate_insights
from src.appointments.services import (
    create_appointment as create_appointment_service,
    get_doctor_appointments,
    get_patient_appointments,
    update_appointment_status,
)
from src.appointments.models import (
    AppointmentStatus,
    AppointmentType,
    CreateAppointmentRequest,
    UpdateAppointmentStatusRequest,
)
from src.assignments.services import get_doctors, get_patients, is_patient_assigned_to_doctor
from src.schemas.reports import Report as ReportORM
from src.schemas.users.users import Appointment as AppointmentORM, User

logger = logging.getLogger(__name__)


# ============================================================================
# Tool Input/Output Models
# ============================================================================

class CreateAppointmentInput(BaseModel):
    """Input for create_appointment tool."""
    doctor_name_or_id: str = Field(description="Doctor's name or user ID")
    date: str = Field(description="Date in YYYY-MM-DD format")
    time: str = Field(description="Time in HH:MM format (24-hour)")
    type: str = Field(description="Consultation, Follow-up, or Emergency")
    reason: str | None = Field(default=None, description="Reason for appointment")


class GetLatestReportsInput(BaseModel):
    """Input for get_latest_reports tool."""
    limit: int = Field(default=5, ge=1, le=20, description="Number of reports to return (1-20)")


class ListAppointmentsInput(BaseModel):
    """Input for list_my_appointments tool."""
    start_date: str | None = Field(default=None, description="Filter from this date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="Filter to this date (YYYY-MM-DD)")
    status: str | None = Field(default=None, description="Scheduled, Completed, Cancelled, No-show")


class CancelAppointmentInput(BaseModel):
    """Input for cancel_appointment tool."""
    appointment_id: str = Field(description="Appointment ID to cancel")
    reason: str | None = Field(default=None, description="Cancellation reason")


class GetReportDetailsInput(BaseModel):
    """Input for get_report_details tool."""
    report_id: str = Field(description="Report ID to get details for")


class GetBookedSlotsInput(BaseModel):
    """Input for get_booked_slots tool."""
    doctor_name_or_id: str = Field(description="Doctor's name or user ID")
    date: str = Field(description="Date in YYYY-MM-DD format")


class CheckSymptomsInput(BaseModel):
    """Input for check_symptoms tool."""
    symptoms: str = Field(description="Description of symptoms")
    duration: str | None = Field(default=None, description="Duration of symptoms (e.g., '2 days', '1 week')")
    severity: int | None = Field(default=None, ge=1, le=10, description="Severity on scale 1-10")


class ListDoctorsInput(BaseModel):
    """Input for list_my_doctors tool."""
    limit: int = Field(default=20, ge=1, le=50, description="Max number of doctors to return (1-50)")
    name: str | None = Field(default=None, description="Filter by doctor name (partial match)")


class GetMyProfileInput(BaseModel):
    """Input for get_my_profile tool."""
    pass


class ListPatientsInput(BaseModel):
    """Input for list_my_patients tool."""
    limit: int = Field(default=20, ge=1, le=50, description="Max number of patients to return (1-50)")


# ============================================================================
# Utility Functions
# ============================================================================

def find_doctor_by_name_or_id(db: Session, name_or_id: str) -> User | dict:
    """Find a doctor by name or user ID. Returns User on success, or error dict on ambiguity."""
    # Try exact ID match first
    doctor = db.query(User).filter(
        User.id == name_or_id,
        User.role == "doctor"
    ).first()
    
    if doctor:
        return doctor
    
    # Try name match (case-insensitive)
    doctors = db.query(User).filter(
        User.role == "doctor",
        User.name.ilike(f"%{name_or_id}%")
    ).limit(5).all()
    
    if len(doctors) == 1:
        return doctors[0]
    elif len(doctors) > 1:
        names = ', '.join([f"Dr. {d.name}" for d in doctors])
        return {
            "ambiguous": True,
            "error": f"Multiple doctors match '{name_or_id}': {names}. Please specify the full name."
        }
    
    return None


def safe_parse_date(date_str: str) -> datetime | None:
    """Safely parse a date string, returning None on failure."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def safe_parse_enum(enum_class, value: str, default=None):
    """Safely parse an enum value, trying case-insensitive match."""
    if not value:
        return default
    # Try exact match
    try:
        return enum_class(value)
    except ValueError:
        pass
    # Try case-insensitive match
    for member in enum_class:
        if member.value.lower() == value.lower():
            return member
    return default


# IST timezone for Indian users
IST = ZoneInfo("Asia/Kolkata")


def parse_datetime_from_date_time(date_str: str, time_str: str) -> datetime:
    """Parse date and time strings into a datetime object in IST, then convert to UTC."""
    # Parse date with multiple format support
    date_obj = safe_parse_date(date_str)
    if not date_obj:
        raise ValueError(f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD.")
    
    # Parse time
    time_obj = None
    for fmt in ("%H:%M", "%I:%M %p", "%H:%M:%S"):
        try:
            time_obj = datetime.strptime(time_str, fmt).time()
            break
        except ValueError:
            continue
    if not time_obj:
        raise ValueError(f"Invalid time format: '{time_str}'. Expected HH:MM (24-hour).")
    
    # Combine in IST (user's local timezone) and convert to UTC for storage
    dt_ist = datetime.combine(date_obj.date(), time_obj, tzinfo=IST)
    dt_utc = dt_ist.astimezone(timezone.utc)
    return dt_utc


def check_appointment_overlap(db: Session, doctor_id: str, start_time: datetime, duration_minutes: int = 30) -> dict | None:
    """Check if doctor has overlapping appointments. Returns conflicting slot info or None."""
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    overlapping = db.query(AppointmentORM).filter(
        AppointmentORM.doctor_user_id == doctor_id,
        AppointmentORM.status == AppointmentStatus.SCHEDULED.value,
        AppointmentORM.start_time < end_time,
        AppointmentORM.end_time > start_time
    ).first()
    
    if overlapping:
        return {
            "conflict_start": overlapping.start_time.strftime("%H:%M"),
            "conflict_end": overlapping.end_time.strftime("%H:%M"),
        }
    return None


# ============================================================================
# Tool Implementations
# ============================================================================

def create_appointment(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    Book an appointment with a doctor.
    Only patients can use this tool.
    """
    if user_role != "patient":
        return {
            "success": False,
            "error": "Only patients can book appointments"
        }
    
    try:
        # Validate input
        input_data = CreateAppointmentInput(**kwargs)
        
        # Find doctor
        doctor_result = find_doctor_by_name_or_id(db, input_data.doctor_name_or_id)
        if doctor_result is None:
            return {
                "success": False,
                "error": f"Doctor '{input_data.doctor_name_or_id}' not found. Please check the name and try again."
            }
        if isinstance(doctor_result, dict):  # Ambiguous match
            return {"success": False, **doctor_result}
        doctor = doctor_result
        
        # Verify patient is assigned to this doctor
        if not is_patient_assigned_to_doctor(db, user_id, doctor.id):
            return {
                "success": False,
                "error": f"You are not assigned to Dr. {doctor.name}. You can only book with your assigned doctors."
            }
        
        # Parse datetime (IST -> UTC)
        start_time = parse_datetime_from_date_time(input_data.date, input_data.time)
        
        # Validate not in the past
        now = datetime.now(timezone.utc)
        if start_time < now:
            local_time = start_time.astimezone(IST).strftime('%Y-%m-%d %I:%M %p IST')
            return {
                "success": False,
                "error": f"Cannot book appointment in the past. The requested time ({local_time}) has already passed."
            }
        
        # Check for overlapping appointments (Issue #7)
        overlap = check_appointment_overlap(db, doctor.id, start_time)
        if overlap:
            return {
                "success": False,
                "error": f"Dr. {doctor.name} already has an appointment from {overlap['conflict_start']} to {overlap['conflict_end']}. Please choose a different time."
            }
        
        # Map appointment type with proper error
        apt_type = safe_parse_enum(AppointmentType, input_data.type)
        if not apt_type:
            valid_types = ', '.join([t.value for t in AppointmentType])
            return {
                "success": False,
                "error": f"Invalid appointment type: '{input_data.type}'. Valid types are: {valid_types}"
            }
        
        # Create appointment
        request = CreateAppointmentRequest(
            doctor_id=doctor.id,
            start_time=start_time,
            type=apt_type,
            reason=input_data.reason
        )
        
        result = create_appointment_service(db, user_id, request)
        
        return {
            "success": True,
            "appointment_id": result.id,
            "message": result.message,
            "doctor_name": doctor.name,
            "type": apt_type.value,
            "start_time": start_time.strftime("%Y-%m-%d %H:%M")
        }
    
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"[Tool:create_appointment] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to create appointment: {str(e)}"}


def list_my_appointments(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    List appointments for the current user.
    Works for both patients and doctors.
    """
    try:
        input_data = ListAppointmentsInput(**kwargs)
        
        # Parse dates safely
        start_date = None
        end_date = None
        if input_data.start_date:
            start_date = safe_parse_date(input_data.start_date)
            if not start_date:
                return {"success": False, "error": f"Invalid start_date format: '{input_data.start_date}'. Expected YYYY-MM-DD."}
        if input_data.end_date:
            end_date = safe_parse_date(input_data.end_date)
            if not end_date:
                return {"success": False, "error": f"Invalid end_date format: '{input_data.end_date}'. Expected YYYY-MM-DD."}
        
        # Parse status safely
        apt_status = safe_parse_enum(AppointmentStatus, input_data.status) if input_data.status else None
        
        # Get appointments based on role
        if user_role == "patient":
            result = get_patient_appointments(db, user_id, start_date, end_date, apt_status)
        elif user_role == "doctor":
            result = get_doctor_appointments(db, user_id, start_date, end_date, apt_status)
        else:
            return {"success": False, "error": "Invalid user role"}
        
        # Format response
        appointments = []
        for apt in result.appointments:
            appointments.append({
                "id": apt.id,
                "with": apt.doctor_name if user_role == "patient" else apt.patient_name,
                "start_time": apt.start_time.strftime("%Y-%m-%d %H:%M"),
                "end_time": apt.end_time.strftime("%Y-%m-%d %H:%M"),
                "type": apt.type.value if isinstance(apt.type, AppointmentType) else apt.type,
                "status": apt.status.value if isinstance(apt.status, AppointmentStatus) else apt.status,
                "reason": apt.reason
            })
        
        return {
            "success": True,
            "count": result.count,
            "appointments": appointments
        }
    
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"[Tool:list_my_appointments] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to list appointments: {str(e)}"}


def cancel_appointment(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    Cancel an appointment.
    Only patients can cancel their own appointments.
    """
    if user_role != "patient":
        return {"success": False, "error": "Only patients can cancel appointments"}
    
    try:
        input_data = CancelAppointmentInput(**kwargs)
        
        request = UpdateAppointmentStatusRequest(
            status=AppointmentStatus.CANCELLED,
            cancellation_reason=input_data.reason
        )
        
        result = update_appointment_status(
            db,
            input_data.appointment_id,
            user_id,
            user_role,
            request
        )
        
        return {
            "success": True,
            "appointment_id": result.id,
            "status": result.status,
            "message": f"Appointment cancelled successfully"
        }
    
    except Exception as e:
        logger.error(f"[Tool:cancel_appointment] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to cancel appointment: {str(e)}"}


def get_latest_reports(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    Get summary of latest uploaded reports.
    Works for both patients (own reports) and doctors (assigned patients' reports).
    """
    try:
        input_data = GetLatestReportsInput(**kwargs)
        limit = input_data.limit
        
        # For patients, get their own reports
        if user_role == "patient":
            patient_id = user_id
            reports = db.query(ReportORM).filter(
                ReportORM.patient_id == patient_id
            ).order_by(ReportORM.created_at.desc()).limit(limit).all()
        elif user_role == "doctor":
            # For doctors, get reports from all assigned patients
            from src.schemas.users.users import Assignment
            assignments = db.query(Assignment).filter(
                Assignment.doctor_user_id == user_id,
                Assignment.is_active == True
            ).all()
            patient_ids = [a.patient_user_id for a in assignments]
            if not patient_ids:
                return {"success": True, "count": 0, "reports": [], "message": "No assigned patients found."}
            reports = db.query(ReportORM).filter(
                ReportORM.patient_id.in_(patient_ids)
            ).order_by(ReportORM.created_at.desc()).limit(limit).all()
        else:
            return {"success": False, "error": "Invalid user role"}
        
        # Get patient names for context
        patient_ids_in_reports = list(set(r.patient_id for r in reports))
        patients = db.query(User).filter(User.id.in_(patient_ids_in_reports)).all() if patient_ids_in_reports else []
        patient_names = {p.id: p.name for p in patients}
        
        report_list = []
        for report in reports:
            report_list.append({
                "id": report.id,
                "filename": report.file_name,
                "patient_name": patient_names.get(report.patient_id, "Unknown"),
                "description": report.description or "No description",
                "uploaded_at": report.created_at.strftime("%Y-%m-%d %H:%M"),
                "has_analysis": report.mongo_analysis_id is not None
            })
        
        return {
            "success": True,
            "count": len(report_list),
            "reports": report_list
        }
    
    except Exception as e:
        logger.error(f"[Tool:get_latest_reports] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to get reports: {str(e)}"}


async def get_report_details(
    db: Session,
    user_id: str,
    user_role: str,
    mongo_db=None,
    **kwargs
) -> dict[str, Any]:
    """
    Get detailed extraction from a specific report.
    Requires mongo_db connection.
    """
    try:
        input_data = GetReportDetailsInput(**kwargs)
        
        # Get report from PostgreSQL
        report = db.query(ReportORM).filter(ReportORM.id == input_data.report_id).first()
        if not report:
            return {"success": False, "error": "Report not found"}
        
        # Check access - patients can only see their own, doctors can see assigned patients'
        if user_role == "patient" and report.patient_id != user_id:
            return {"success": False, "error": "Access denied"}
        elif user_role == "doctor":
            if not is_patient_assigned_to_doctor(db, report.patient_id, user_id):
                return {"success": False, "error": "Access denied - patient not assigned to you"}
        
        # Get analysis from MongoDB
        if not report.mongo_analysis_id:
            return {
                "success": False,
                "error": "This report has not been analyzed yet"
            }
        
        if mongo_db is None:
            return {"success": False, "error": "Database connection unavailable for analysis retrieval"}
        
        # Validate ObjectId format
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            obj_id = ObjectId(report.mongo_analysis_id)
        except (InvalidId, TypeError):
            return {"success": False, "error": "Invalid analysis reference. Report may need re-analysis."}
        
        analysis = await mongo_db.report_analysis.find_one({"_id": obj_id})
        
        if not analysis:
            return {"success": False, "error": "Analysis data not found"}
        
        extracted = analysis.get("extracted_data", {})
        
        return {
            "success": True,
            "report_id": input_data.report_id,
            "filename": report.file_name,
            "patient_name": extracted.get("patient_name", "N/A"),
            "report_type": extracted.get("report_type", "N/A"),
            "report_date": extracted.get("report_date", "N/A"),
            "diagnoses": extracted.get("diagnoses", []),
            "medications": extracted.get("medications", []),
            "lab_results": extracted.get("lab_results", [])[:10],
            "recommendations": extracted.get("recommendations", [])
        }
    
    except Exception as e:
        logger.error(f"[Tool:get_report_details] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to get report details: {str(e)}"}


async def get_health_insights(
    db: Session,
    user_id: str,
    user_role: str,
    mongo_db,
    **kwargs
) -> dict[str, Any]:
    """
    Get AI-generated health insights and trends.
    """
    try:
        # For patients, get their own insights
        if user_role == "patient":
            patient_id = user_id
        else:
            return {
                "success": False,
                "error": "Doctors must specify a patient for insights"
            }
        
        # Get patient data
        from src.schemas.users.users import Patient
        patient = db.query(Patient).filter(Patient.user_id == patient_id).first()
        if not patient:
            return {"success": False, "error": "Patient profile not found"}
        
        patient_data = {
            "age": (date.today() - patient.date_of_birth).days // 365,
            "gender": patient.gender,
            "blood_group": patient.blood_group,
            "allergies": patient.allergies,
            "current_medications": patient.current_medications,
            "medical_history": patient.medical_history
        }
        
        # Get recent reports
        reports = db.query(ReportORM).filter(
            ReportORM.patient_id == patient_id
        ).order_by(ReportORM.created_at.desc()).limit(10).all()
        reports_summary = "\n".join([
            f"- {r.file_name} ({r.created_at.strftime('%Y-%m-%d')}): {r.description or 'No description'}"
            for r in reports
        ])
        
        # Generate insights
        insights_result = await generate_insights(patient_data, reports_summary)
        
        return {
            "success": True,
            "insights": insights_result.insights,
            "risk_factors": insights_result.risk_factors,
            "trends": insights_result.trends
        }
    
    except Exception as e:
        logger.error(f"[Tool:get_health_insights] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to generate insights: {str(e)}"}


def get_my_profile(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    Get current user's profile information.
    """
    try:
        if user_role == "patient":
            from src.schemas.users.users import Patient
            profile = db.query(Patient).filter(Patient.user_id == user_id).first()
            if not profile:
                return {"success": False, "error": "Patient profile not found"}
            
            return {
                "success": True,
                "role": "patient",
                "name": profile.name,
                "age": (date.today() - profile.date_of_birth).days // 365 if profile.date_of_birth else None,
                "gender": profile.gender,
                "blood_group": profile.blood_group,
                "allergies": profile.allergies,
                "current_medications": profile.current_medications,
                "medical_history": profile.medical_history
            }
        elif user_role == "doctor":
            # For doctors, just return basic info
            user = db.query(User).filter(User.id == user_id).first()
            return {
                "success": True,
                "role": "doctor",
                "name": user.name if user else "Unknown",
                "email": user.email if user else "Unknown"
            }
        else:
            return {"success": False, "error": "Unknown role"}

    except Exception as e:
        logger.error(f"[Tool:get_my_profile] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to get profile: {str(e)}"}


def list_my_doctors(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    List assigned doctors (for patients).
    """
    if user_role != "patient":
        return {"success": False, "error": "Only patients can list their doctors"}
    
    try:
        input_data = ListDoctorsInput(**kwargs)
        doctors = get_doctors(user_id, db)
        
        doctor_list = []
        for doc_assignment in doctors.doctors:
            # Filter by name if provided
            if input_data.name and input_data.name.lower() not in doc_assignment.name.lower():
                continue
                
            doctor_list.append({
                "id": doc_assignment.user_id,
                "name": doc_assignment.name,
                "specialization": doc_assignment.specialisation,
            })
        
        # Apply limit after filtering
        limited_list = doctor_list[:input_data.limit]
        
        return {
            "success": True,
            "count": len(limited_list),
            "total": len(doctor_list),
            "doctors": limited_list
        }
    
    except Exception as e:
        logger.error(f"[Tool:list_my_doctors] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to list doctors: {str(e)}"}


def list_my_patients(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    List assigned patients (for doctors).
    """
    if user_role != "doctor":
        return {"success": False, "error": "Only doctors can list their patients"}
    
    try:
        input_data = ListPatientsInput(**kwargs)
        patients = get_patients(user_id, db)
        
        patient_list = []
        for patient in patients.patients[:input_data.limit]:
            patient_list.append({
                "id": patient.user_id,
                "name": patient.name,
                "age": (date.today() - patient.date_of_birth).days // 365 if patient.date_of_birth else None,
            })
        
        return {
            "success": True,
            "count": len(patient_list),
            "total": len(patients.patients),
            "patients": patient_list
        }
    
    except Exception as e:
        logger.error(f"[Tool:list_my_patients] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to list patients: {str(e)}"}


def get_booked_slots(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    Get list of booked appointment slots for a doctor on a specific date.
    Patient names are anonymized for non-doctor users.
    """
    try:
        input_data = GetBookedSlotsInput(**kwargs)
        
        # Find doctor
        doctor_result = find_doctor_by_name_or_id(db, input_data.doctor_name_or_id)
        if doctor_result is None:
            return {
                "success": False,
                "error": f"Doctor '{input_data.doctor_name_or_id}' not found"
            }
        if isinstance(doctor_result, dict):  # Ambiguous match
            return {"success": False, **doctor_result}
        doctor = doctor_result
        
        # Parse date
        target_date = datetime.strptime(input_data.date, "%Y-%m-%d").date()
        start_of_day = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_of_day = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        # Query booked appointments
        appointments = db.query(AppointmentORM).filter(
            AppointmentORM.doctor_user_id == doctor.id,
            AppointmentORM.status == AppointmentStatus.SCHEDULED.value,
            AppointmentORM.start_time >= start_of_day,
            AppointmentORM.start_time <= end_of_day
        ).order_by(AppointmentORM.start_time).all()
        
        # Format response
        booked_slots = []
        is_doctor = user_role == "doctor" and user_id == doctor.id
        
        for i, apt in enumerate(appointments):
            # Anonymize patient names for non-doctors
            if is_doctor:
                patient = db.query(User).filter(User.id == apt.patient_user_id).first()
                patient_name = patient.name if patient else "Unknown"
            else:
                patient_name = f"Patient {chr(65 + i)}"  # Patient A, Patient B, etc.
            
            booked_slots.append({
                "start_time": apt.start_time.strftime("%H:%M"),
                "end_time": apt.end_time.strftime("%H:%M"),
                "patient": patient_name,
                "type": apt.type
            })
        
        return {
            "success": True,
            "doctor_name": doctor.name,
            "date": input_data.date,
            "count": len(booked_slots),
            "booked_slots": booked_slots
        }
    
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"[Tool:get_booked_slots] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to get booked slots: {str(e)}"}


async def check_symptoms(
    db: Session,
    user_id: str,
    user_role: str,
    **kwargs
) -> dict[str, Any]:
    """
    Analyze symptoms and provide triage assessment.
    This is informational only and NOT a medical diagnosis.
    """
    try:
        input_data = CheckSymptomsInput(**kwargs)
        
        # Build prompt for Gemini
        from src.ai.gemini_client import client, MODEL_NAME
        from google.genai import types as genai_types
        from pydantic import BaseModel
        
        class TriageResult(BaseModel):
            triage_level: str = Field(description="Emergency, Urgent, Routine, or Self-care")
            possible_conditions: list[str] = Field(description="Possible conditions (informational)")
            recommendations: list[str] = Field(description="Recommended next steps")
        
        severity_str = f"Severity (1-10): {input_data.severity}" if input_data.severity else ""
        duration_str = f"Duration: {input_data.duration}" if input_data.duration else ""
        
        prompt = f"""Analyze these symptoms and provide a triage assessment:

Symptoms: {input_data.symptoms}
{duration_str}
{severity_str}

Provide:
1. Triage level (Emergency/Urgent/Routine/Self-care)
2. Possible conditions (informational only, 2-3 max)
3. Recommended next steps (2-3 clear actions)

IMPORTANT: This is not a diagnosis. Always recommend consulting a healthcare provider for proper evaluation."""
        
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt],
            config={
                "temperature": 0.5,
                "response_mime_type": "application/json",
                "response_json_schema": TriageResult.model_json_schema(),
            }
        )
        
        result = TriageResult.model_validate_json(response.text)
        
        return {
            "success": True,
            "triage_level": result.triage_level,
            "possible_conditions": result.possible_conditions,
            "recommendations": result.recommendations,
            "disclaimer": "⚠️ This is not a medical diagnosis. Please consult a healthcare provider for proper evaluation and treatment."
        }
    
    except Exception as e:
        logger.error(f"[Tool:check_symptoms] Error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to analyze symptoms: {str(e)}"}


# ============================================================================
# Tool Registry
# ============================================================================

# Tool definitions for Gemini function calling
TOOL_DEFINITIONS = {
    "create_appointment": {
        "name": "create_appointment",
        "description": "Book an appointment with a doctor. Only patients can use this.",
        "parameters": CreateAppointmentInput.model_json_schema()
    },
    "list_my_appointments": {
        "name": "list_my_appointments",
        "description": "List appointments for the current user with optional filters.",
        "parameters": ListAppointmentsInput.model_json_schema()
    },
    "cancel_appointment": {
        "name": "cancel_appointment",
        "description": "Cancel an appointment. Only patients can cancel their appointments.",
        "parameters": CancelAppointmentInput.model_json_schema()
    },
    "get_latest_reports": {
        "name": "get_latest_reports",
        "description": "Get a summary of the latest uploaded medical reports. Works for patients (own reports) and doctors (assigned patients' reports).",
        "parameters": GetLatestReportsInput.model_json_schema()
    },
    "get_report_details": {
        "name": "get_report_details",
        "description": "Get detailed extraction data from a specific report.",
        "parameters": GetReportDetailsInput.model_json_schema()
    },
    "get_health_insights": {
        "name": "get_health_insights",
        "description": "Get AI-generated health insights and trends based on medical history.",
        "parameters": {}
    },
    "list_my_doctors": {
        "name": "list_my_doctors",
        "description": "List assigned doctors. Only patients can use this.",
        "parameters": ListDoctorsInput.model_json_schema()
    },
    "list_my_patients": {
        "name": "list_my_patients",
        "description": "List assigned patients. Only doctors can use this.",
        "parameters": ListPatientsInput.model_json_schema()
    },
    "get_booked_slots": {
        "name": "get_booked_slots",
        "description": "Get list of booked appointment slots for a doctor on a specific date.",
        "parameters": GetBookedSlotsInput.model_json_schema()
    },
    "check_symptoms": {
        "name": "check_symptoms",
        "description": "Analyze symptoms and provide triage assessment (informational only, not a diagnosis).",
        "parameters": CheckSymptomsInput.model_json_schema()
    },
    "get_my_profile": {
        "name": "get_my_profile",
        "description": "Get your personal profile details (name, age, allergies, medications, etc).",
        "parameters": GetMyProfileInput.model_json_schema()
    }
}

# Tool handler mapping
TOOL_HANDLERS = {
    "create_appointment": create_appointment,
    "list_my_appointments": list_my_appointments,
    "cancel_appointment": cancel_appointment,
    "get_latest_reports": get_latest_reports,
    "get_report_details": get_report_details,
    "get_health_insights": get_health_insights,
    "list_my_doctors": list_my_doctors,
    "list_my_patients": list_my_patients,
    "get_booked_slots": get_booked_slots,
    "check_symptoms": check_symptoms
}


# ============================================================================
# Tool Executor
# ============================================================================

async def execute_tool(
    tool_name: str,
    tool_args: dict,
    db: Session,
    user_id: str,
    user_role: str,
    mongo_db = None
) -> dict[str, Any]:
    """
    Execute a tool by name with error handling.
    
    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool
        db: Database session
        user_id: Current user ID
        user_role: Current user role (patient/doctor)
        mongo_db: MongoDB connection (optional, needed for some tools)
    
    Returns:
        Tool execution result dict with 'success' and 'error' or data
    """
    try:
        if tool_name not in TOOL_HANDLERS:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
        
        handler = TOOL_HANDLERS[tool_name]
        
        # Add mongo_db to kwargs if the tool needs it
        kwargs = {**tool_args}
        
        # Check if handler is async
        import inspect
        if inspect.iscoroutinefunction(handler):
            if mongo_db is not None:
                result = await handler(db, user_id, user_role, mongo_db=mongo_db, **kwargs)
            else:
                result = await handler(db, user_id, user_role, **kwargs)
        else:
            # Sync handlers don't need mongo_db
            result = handler(db, user_id, user_role, **kwargs)
        
        logger.info(f"[Tool:{tool_name}] Executed successfully | user={user_id}")
        return result
    
    except Exception as e:
        logger.error(f"[Tool:{tool_name}] Execution failed | error={e}", exc_info=True)
        return {
            "success": False,
            "error": f"Tool execution failed: {str(e)}"
        }
