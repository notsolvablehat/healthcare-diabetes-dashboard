from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.core import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
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
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

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
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

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

    specialisation = Column(String, nullable=False, index=True) # Ensure this is indexed for speed
    max_patients = Column(Integer, default=10, nullable=False)

    # Back Reference
    user = relationship("User", back_populates="doctor_profile")

    def __repr__(self) -> str:
        return (
            f"<Doctor(id={self.doctor_id}, "
            f"specialisation={self.specialisation}, "
            f"dob={self.date_of_birth})>"
        )

class Assignment(Base):
    __tablename__ = "doctor_patient_assignments"

    id = Column(String, primary_key=True)

    # Foreign Keys linking to the users table
    doctor_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    patient_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Status control
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit trail
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # ---------------------------------------------------------
    # PARTIAL INDEX CONFIGURATION
    # ---------------------------------------------------------
    __table_args__ = (
        Index(
            'unique_active_assignment',        # Index Name
            'doctor_user_id', 'patient_user_id', # Columns to check
            unique=True,                       # Make it unique
            postgresql_where=(is_active.is_(True)) # ONLY if is_active is True
        ),
    )

    def __repr__(self):
        return f"<Assignment(doc={self.doctor_user_id}, patient={self.patient_user_id}, active={self.is_active})>"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True)

    # Foreign Keys
    doctor_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Appointment details
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    type = Column(String, nullable=False)  # Consultation, Follow-up, Emergency
    status = Column(String, default="Scheduled", nullable=False, index=True)  # Scheduled, Completed, Cancelled, No-show

    # Notes and reasons
    reason = Column(String, nullable=True)  # Patient's reason for appointment
    notes = Column(String, nullable=True)  # Doctor's internal notes
    cancellation_reason = Column(String, nullable=True)  # Reason if cancelled

    # Audit trail
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Indexes for common queries
    __table_args__ = (
        Index('idx_appointments_doctor_time', 'doctor_user_id', 'start_time'),
        Index('idx_appointments_patient_time', 'patient_user_id', 'start_time'),
        Index('idx_appointments_status_time', 'status', 'start_time'),
    )

    def __repr__(self):
        return f"<Appointment(id={self.id}, doctor={self.doctor_user_id}, patient={self.patient_user_id}, status={self.status})>"
