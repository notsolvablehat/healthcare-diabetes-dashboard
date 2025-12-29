from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class BloodGroup(str):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    O_POS = "O+"
    O_NEG = "O-"
    AB_POS = "AB+"
    AB_NEG = "AB-"

class PatientOnboarding(BaseModel):
    """
    Data collected during the 'First Time Login' wizard.
    """
    # Demographics
    date_of_birth: date = Field(..., description="Required for medical ID and age calculation")
    gender: Literal["Male", "Female", "Other", "Prefer not to say"] = Field(...)
    phone_number: str = Field(..., description="Crucial for appointment reminders")
    address: str = Field(..., description="Required for prescriptions/billing")

    # Vitals & History
    blood_group: Literal["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"] | None = None
    height_cm: float | None = Field(None, gt=0, description="Height in cm")
    weight_kg: float | None = Field(None, gt=0, description="Weight in kg")

    # Medical Safety
    allergies: list[str] = Field(default_factory=list, description="List of allergens e.g., 'Peanuts', 'Penicillin'")
    current_medications: list[str] = Field(default_factory=list, description="Currently active prescriptions")
    medical_history: list[str] = Field(default_factory=list, description="Past surgeries or chronic conditions")

    # Emergency
    emergency_contact_name: str = Field(...)
    emergency_contact_phone: str = Field(...)

    # Legal
    consent_hipaa: bool = Field(..., description="User must agree to privacy policy")

class UserBase(BaseModel):
    """
    Core attributes shared by all users.
    """
    name: str
    email: EmailStr
    role: Literal["doctor", "patient", "admin"]
    is_onboarded: bool = False # Flag to trigger the onboarding flow
    created_at: date

class PatientProfile(UserBase):
    """
    The complete Patient record.
    Combines UserBase (Auth info) + Onboarding Data (Medical info).
    """
    patient_id: str = Field(...)

    medical_info: PatientOnboarding | None = None

    @property
    def age(self) -> int | None:
        """Calculates age dynamically from DOB"""
        if not self.medical_info or not self.medical_info.date_of_birth:
            return None
        today = date.today()
        return today.year - self.medical_info.date_of_birth.year - (
            (today.month, today.day) < (self.medical_info.date_of_birth.month, self.medical_info.date_of_birth.day)
        )

class DoctorProfile(UserBase):
    """
    The complete Patient record.
    Combines UserBase (Auth info) + Onboarding Data (Medical info).
    """
    doctor_id: str = Field(...)
    license: str = Field(...)
    specialisation: str = Field(...)

    date_of_birth: date | None = None
    gender: str | None = None
    medical_info: PatientOnboarding | None = None

    @property
    def age(self) -> int | None:
        """Calculates age dynamically from DOB"""
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
