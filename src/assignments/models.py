from datetime import date

from pydantic import BaseModel, EmailStr, Field


class PatientSummary(BaseModel):
    """
    A lightweight summary of a patient for list views.
    """
    user_id: str
    patient_id: str
    name: str | None = "Unknown"
    email: EmailStr
    gender: str
    date_of_birth: date

    class Config:
        from_attributes = True

class MyPatients(BaseModel):
    """
    Used to return the patients for a particular doctor.
    """
    doctor_id: str
    count: int
    patients: list[PatientSummary]

class DoctorSummary(BaseModel):
    """
    Lightweight summary of a doctor for the patient's list view.
    """
    user_id: str
    doctor_id: str
    name: str
    email: EmailStr
    specialisation: str
    department: str | None = None

    class Config:
        from_attributes = True

class MyDoctors(BaseModel):
    """
    Wrapper for returning the list of doctors assigned to a patient.
    """
    patient_id: str
    count: int
    doctors: list[DoctorSummary]

class PatientAssignRequest(BaseModel):
    """
    Request format for assigning a patient to a doctor.
    This will be done by doctor or admin.
    """

    patient_email: EmailStr = Field(...)
    speciality_required: str = Field(...)

class RevokeAccessRequest(BaseModel):
    """
    Request format for revoking access of a doctor to its patient.
    Can be revoked by doctor or admin.
    """

    patient_email: EmailStr
    # Optional: Only required if an ADMIN is performing the revoke actions
    doctor_identifier: str | None = None # Can be Doctor's Email or Doctor ID
    reason: str | None = "Discharged"
