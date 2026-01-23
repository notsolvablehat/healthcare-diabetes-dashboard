from datetime import date, datetime

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

class PatientHistoryEntry(BaseModel):
    """
    Historical record of a previously assigned patient.
    """
    user_id: str
    patient_id: str
    name: str | None = "Unknown"
    email: EmailStr
    gender: str
    date_of_birth: date
    assigned_at: datetime
    revoked_at: datetime | None = None
    reason: str | None = None

    class Config:
        from_attributes = True

class MyPatients(BaseModel):
    """
    Used to return the patients for a particular doctor.
    """
    doctor_id: str
    count: int
    patients: list[PatientSummary]
    history: list[PatientHistoryEntry] = []

class DoctorSummary(BaseModel):
    """
    Lightweight summary of a doctor for the patient's list view.
    """
    user_id: str
    doctor_id: str
    name: str | None = None
    email: EmailStr
    specialisation: str
    department: str | None = None

    class Config:
        from_attributes = True

class DoctorHistoryEntry(BaseModel):
    """
    Historical record of a previously assigned doctor.
    """
    user_id: str
    doctor_id: str
    name: str | None = None
    email: EmailStr
    specialisation: str
    department: str | None = None
    assigned_at: datetime
    revoked_at: datetime | None = None
    reason: str | None = None

    class Config:
        from_attributes = True

class MyDoctors(BaseModel):
    """
    Wrapper for returning the list of doctors assigned to a patient.
    """
    patient_id: str
    count: int
    doctors: list[DoctorSummary]
    history: list[DoctorHistoryEntry] = []

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

class Specialities(BaseModel):
    """
    Response model for available doctor specializations.
    """
    count: int
    specialities: list[str]

class PatientDetailResponse(BaseModel):
    """
    Complete patient information for doctors.
    """
    user_id: str
    patient_id: str
    name: str | None = None
    email: EmailStr
    username: str
    is_onboarded: bool
    created_at: datetime

    # Patient profile fields
    date_of_birth: date
    gender: str
    phone_number: str
    address: str
    blood_group: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    allergies: list[str] | None = None
    current_medications: list[str] | None = None
    medical_history: list[str] | None = None
    emergency_contact_name: str
    emergency_contact_phone: str

    class Config:
        from_attributes = True
