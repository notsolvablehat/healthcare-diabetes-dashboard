from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.sql import func, select

from src.database.core import DbSession
from src.schemas.users.users import Assignment, Doctor, Patient, User
from src.users.services import get_user

from .models import (
    DoctorSummary,
    MyDoctors,
    MyPatients,
    PatientAssignRequest,
    PatientSummary,
    RevokeAccessRequest,
)


def get_patients(user_id: str, db: DbSession) -> MyPatients:
    user = get_user(db ,user_id)

    if str(user.role) != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to access patient records.")

    stmt = select(User, Patient).join(User, Patient.user_id == User.id).join(Assignment, Assignment.patient_user_id == Patient.user_id).filter(Assignment.doctor_user_id == user.id, Assignment.is_active)
    results = db.execute(stmt).all()

    patient_list = []
    for user_row, patient_row in results:
        patient_list.append(PatientSummary(user_id=user_id, patient_id=patient_row.patient_id, name=user_row.name, email=user_row.email, gender=patient_row.gender, date_of_birth=patient_row.date_of_birth))

    return MyPatients(
            doctor_id=user.id,
            count=len(patient_list),
            patients=patient_list
        )

def get_doctors(user_id: str, db: DbSession) -> MyDoctors:
    user = get_user(db, user_id)
    if str(user.role) != "patient" and str(user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view the doctors."
        )

    stmt = (
        select(User, Doctor)
        .join(User, Doctor.user_id == User.id)
        .join(Assignment, Assignment.doctor_user_id == Doctor.user_id)
        .filter(
            Assignment.patient_user_id == user.id,
            Assignment.is_active
        )
    )

    results = db.execute(stmt).all()

    doctor_list = []
    for user_row, doctor_row in results:
        doctor_list.append(
            DoctorSummary(
                user_id=user_row.id,
                doctor_id=doctor_row.doctor_id,
                name=user_row.name,
                email=user_row.email,
                specialisation=doctor_row.specialisation,
                department=getattr(doctor_row, "department", "N/A")
            )
        )

    return MyDoctors(
        patient_id=user.id,
        count=len(doctor_list),
        doctors=doctor_list
    )

def assign_patient(db: DbSession, user_id: str, request_data: PatientAssignRequest):
        user = get_user(db, user_id)
        if user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to make this request.")

        stmt = select(User).filter(User.email == request_data.patient_email)
        patient_user = db.scalars(stmt).first()

        if not patient_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

        if not patient_user.patient_profile:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not fully onboarded as a patient.")

        # Calculate Load
        active_load_subquery = (
            select(Assignment.doctor_user_id, func.count(Assignment.id).label("current_load"))
            .filter(Assignment.is_active)
            .group_by(Assignment.doctor_user_id)
            .subquery()
        )

        # Find Candidates
        stmt = (
            select(Doctor, func.coalesce(active_load_subquery.c.current_load, 0).label("load"))
            .outerjoin(active_load_subquery, Doctor.user_id == active_load_subquery.c.doctor_user_id)
            .filter(Doctor.specialisation == request_data.speciality_required)
        )

        # Note: .all() returns Rows (tuples), which is fine for unpacking below
        candidate_doctors = db.execute(stmt).all()

        if not candidate_doctors:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No doctors found with specialisation {request_data.speciality_required}")

        qualified_doctors = []
        for doc, current_load in candidate_doctors:
            if current_load < doc.max_patients:
                qualified_doctors.append((doc, current_load))

        if not qualified_doctors:
            raise HTTPException(status_code=409, detail="All specialists are currently fully booked.")

        qualified_doctors.sort(key=lambda x: x[1])
        best_doctor = qualified_doctors[0][0]

        # Check Existing Link
        stmt = select(Assignment).filter(
            Assignment.doctor_user_id == best_doctor.user_id,
            Assignment.patient_user_id == patient_user.id,
            Assignment.is_active
        )
        existing_link = db.scalars(stmt).first()

        if existing_link:
            return JSONResponse(
                status_code=status.HTTP_226_IM_USED,
                content={"message": f"This patient is already assigned to doctor {best_doctor.doctor_id}"}
            )

        # 7. Create Assignment
        new_assignment = Assignment(
            id=str(uuid4()),
            doctor_user_id=best_doctor.user_id,
            patient_user_id=patient_user.id,
            is_active=True
        )
        db.add(new_assignment)
        db.commit()
        db.refresh(new_assignment)

        return {
            "status": "success",
            "assigned_doctor": str(best_doctor),
            "specialization": best_doctor.specialisation,
            "current_load": qualified_doctors[0][1] + 1
        }

def revoke_patient_access(db: DbSession, requester_id: str, request_data: RevokeAccessRequest):
    requester = get_user(db, requester_id)

    if requester.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to perform this action.")

    patient_user = db.scalars(select(User).filter(User.email == request_data.patient_email)).first()

    if not patient_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    target_doctor_id = None

    if str(requester.role) == "doctor":
        target_doctor_id = requester.id

    elif str(requester.role) == "admin":
        if not request_data.doctor_identifier:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins must provide a 'doctor_identifier' (email or id) to revoke access.")

        stmt = select(User.id).outerjoin(Doctor, User.id == Doctor.user_id).filter((User.email == request_data.doctor_identifier) | (Doctor.doctor_id == request_data.doctor_identifier))
        target_doctor_id = db.scalars(stmt).first()

        if not target_doctor_id:
                    raise HTTPException(status_code=404, detail="Target doctor not found.")

    stmt = select(Assignment).filter(
        Assignment.patient_user_id == patient_user.id,
        Assignment.doctor_user_id == target_doctor_id,
        Assignment.is_active
    )
    assignment = db.scalars(stmt).first()

    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This doctor has no such patient.")

    assignment.is_active = False
    assignment.revoked_at = datetime.now()

    db.commit()

    return JSONResponse(status_code=status.HTTP_200_OK, content={
        "status": "success",
        "message": f"Access revoked for patient {request_data.patient_email}."
    })
