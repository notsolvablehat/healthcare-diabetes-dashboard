from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from src.database.core import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()", index=True)
    username = Column(String, unique=True)
    name = Column(String)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_pass = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'doctor', 'patient', 'admin'
    is_onboarded = Column(Boolean, default=False)
    created_at = Column(Date, nullable=False)

    # Relationships
    patient_profile = relationship("Patient", back_populates="user", uselist=False)
    doctor_profile = relationship("Doctor", back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User(email={self.email}, role={self.role}, is_onboarded={self.is_onboarded})>"


class Patient(Base):
    __tablename__ = "patients"

    # The Primary Key is also the Foreign Key to Users (1-to-1 relationship)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)

    # Business ID
    patient_id = Column(String, unique=True, nullable=False, index=True)

    # Demographics
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    address = Column(String, nullable=False)

    # Vitals
    blood_group = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)

    # Medical Arrays (Postgres specific)
    allergies = Column(ARRAY(String), default=[])
    current_medications = Column(ARRAY(String), default=[])
    medical_history = Column(ARRAY(String), default=[])

    # Emergency & Legal
    emergency_contact_name = Column(String, nullable=False)
    emergency_contact_phone = Column(String, nullable=False)
    consent_hipaa = Column(Boolean, nullable=False)

    # Back Reference
    user = relationship("User", back_populates="patient_profile")

    def __repr__(self) -> str:
        return f"<Patient(id={self.patient_id}, dob={self.date_of_birth})>"

class Doctor(Base):
    __tablename__ = "doctors"

    # Primary Key + FK to users (1-to-1)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)

    # Business / Professional IDs
    doctor_id = Column(String, unique=True, nullable=False, index=True)
    license = Column(String, nullable=False)
    specialisation = Column(String, nullable=False)

    # Demographics (same as Patient)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    address = Column(String, nullable=False)

    # Vitals
    blood_group = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)

    # Medical Arrays (Postgres specific)
    allergies = Column(ARRAY(String), default=[])
    current_medications = Column(ARRAY(String), default=[])
    medical_history = Column(ARRAY(String), default=[])

    # Emergency & Legal
    emergency_contact_name = Column(String, nullable=False)
    emergency_contact_phone = Column(String, nullable=False)
    consent_hipaa = Column(Boolean, nullable=False)

    # Back Reference
    user = relationship("User", back_populates="doctor_profile")

    def __repr__(self) -> str:
        return (
            f"<Doctor(id={self.doctor_id}, "
            f"specialisation={self.specialisation}, "
            f"dob={self.date_of_birth})>"
        )
