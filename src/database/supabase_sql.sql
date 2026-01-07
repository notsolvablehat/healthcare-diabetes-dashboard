CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id VARCHAR PRIMARY KEY,
    name VARCHAR,
    email VARCHAR UNIQUE NOT NULL,
    hashed_pass VARCHAR NOT NULL,
    role VARCHAR NOT NULL CHECK (role IN ('doctor', 'patient', 'admin')),
    is_onboarded BOOLEAN DEFAULT FALSE,
    created_at DATE DEFAULT CURRENT_DATE,
    username VARCHAR UNIQUE NOT NULL
);

CREATE TABLE patients (
    user_id VARCHAR PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    patient_id VARCHAR UNIQUE NOT NULL,  -- Same value as user_id
    date_of_birth DATE NOT NULL,
    gender VARCHAR NOT NULL,
    phone_number VARCHAR NOT NULL,
    address TEXT NOT NULL,
    blood_group VARCHAR,
    height_cm DOUBLE PRECISION,
    weight_kg DOUBLE PRECISION,
    allergies TEXT[],
    current_medications TEXT[],
    medical_history TEXT[],
    emergency_contact_name VARCHAR NOT NULL,
    emergency_contact_phone VARCHAR NOT NULL,
    consent_hipaa BOOLEAN NOT NULL
);

CREATE TABLE doctors (
    user_id VARCHAR PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    doctor_id VARCHAR UNIQUE NOT NULL,  -- Same value as user_id
    license VARCHAR NOT NULL,
    specialisation VARCHAR NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR NOT NULL,
    phone_number VARCHAR NOT NULL,
    address TEXT NOT NULL,
    blood_group VARCHAR,
    height_cm DOUBLE PRECISION,
    weight_kg DOUBLE PRECISION,
    allergies TEXT[],
    current_medications TEXT[],
    medical_history TEXT[],
    emergency_contact_name VARCHAR NOT NULL,
    emergency_contact_phone VARCHAR NOT NULL,
    consent_hipaa BOOLEAN NOT NULL,
    max_patients INTEGER NOT NULL DEFAULT 10
);

CREATE TABLE doctor_patient_assignments (
    id VARCHAR PRIMARY KEY,
    doctor_user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    patient_user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE UNIQUE INDEX unique_active_assignment 
ON doctor_patient_assignments (doctor_user_id, patient_user_id) 
WHERE is_active = TRUE;

CREATE TABLE cases (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR UNIQUE NOT NULL,
    mongo_case_id VARCHAR UNIQUE,
    patient_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR DEFAULT 'open',
    chief_complaint VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_cases_mongo_id ON cases(mongo_case_id);

CREATE TABLE reports (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR REFERENCES cases(case_id) ON DELETE CASCADE,
    patient_id VARCHAR NOT NULL REFERENCES users(id),
    uploaded_by VARCHAR NOT NULL REFERENCES users(id),
    file_name VARCHAR NOT NULL,
    file_type VARCHAR NOT NULL,  -- 'pdf' | 'image'
    content_type VARCHAR NOT NULL,  -- mime type
    storage_path VARCHAR NOT NULL,  -- path in Supabase bucket
    file_size_bytes INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_reports_case ON reports(case_id);
CREATE INDEX idx_reports_patient ON reports(patient_id);
