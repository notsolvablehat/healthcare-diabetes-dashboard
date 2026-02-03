# Healthcare & Diabetes Dashboard - Complete Project Workflows

**Last Updated:** January 23, 2026  
**Version:** 1.0

This document contains comprehensive Mermaid diagrams showing the complete architecture, data flow, and user workflows for the Healthcare & Diabetes Dashboard system.

---

## Table of Contents
1. [System Architecture Overview](#1-system-architecture-overview)
2. [Database Architecture](#2-database-architecture)
3. [Authentication & Onboarding Flow](#3-authentication--onboarding-flow)
4. [Doctor-Patient Assignment Flow](#4-doctor-patient-assignment-flow)
5. [Medical Case Management Flow](#5-medical-case-management-flow)
6. [Report Upload & AI Analysis Flow](#6-report-upload--ai-analysis-flow)
7. [AI Chat System Flow](#7-ai-chat-system-flow)
8. [Diabetes Dashboard Flow](#8-diabetes-dashboard-flow)
9. [Notification System Flow](#9-notification-system-flow)
10. [Complete User Journey](#10-complete-user-journey)

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Web Application<br/>React/Vue/Angular]
    end
    
    subgraph "API Gateway"
        FastAPI[FastAPI Server<br/>Python 3.10+]
        CORS[CORS Middleware]
        RateLimit[Rate Limiting<br/>SlowAPI]
        Auth[JWT Authentication]
    end
    
    subgraph "Core Modules"
        AuthModule[Auth Module<br/>Login/Register]
        UserModule[Users Module<br/>Profiles]
        AssignModule[Assignments Module<br/>Doctor-Patient Links]
        CaseModule[Cases Module<br/>Medical Records]
        ReportModule[Reports Module<br/>File Management]
        AIModule[AI Module<br/>Analysis & Chat]
        DashModule[Dashboards Module<br/>Analytics]
        NotifModule[Notifications Module<br/>Alerts]
    end
    
    subgraph "Data Layer"
        Postgres[(PostgreSQL<br/>Relational Data)]
        Mongo[(MongoDB<br/>Document Data)]
        Supabase[Supabase Storage<br/>File Storage]
    end
    
    subgraph "External Services"
        Gemini[Google Gemini 2.5<br/>AI Analysis]
        XGBoost[XGBoost Model<br/>Diabetes Prediction]
    end
    
    UI --> FastAPI
    FastAPI --> CORS
    CORS --> RateLimit
    RateLimit --> Auth
    
    Auth --> AuthModule
    Auth --> UserModule
    Auth --> AssignModule
    Auth --> CaseModule
    Auth --> ReportModule
    Auth --> AIModule
    Auth --> DashModule
    Auth --> NotifModule
    
    AuthModule --> Postgres
    UserModule --> Postgres
    AssignModule --> Postgres
    CaseModule --> Postgres
    CaseModule --> Mongo
    ReportModule --> Postgres
    ReportModule --> Supabase
    AIModule --> Mongo
    AIModule --> Gemini
    AIModule --> XGBoost
    DashModule --> Postgres
    DashModule --> Mongo
    NotifModule --> Postgres
    
    style FastAPI fill:#4CAF50
    style Postgres fill:#336791
    style Mongo fill:#47A248
    style Supabase fill:#3ECF8E
    style Gemini fill:#4285F4
```

---

## 2. Database Architecture

```mermaid
erDiagram
    USERS ||--o| PATIENTS : "1:1"
    USERS ||--o| DOCTORS : "1:1"
    USERS ||--o{ NOTIFICATIONS : "has many"
    DOCTORS ||--o{ ASSIGNMENTS : "has many"
    PATIENTS ||--o{ ASSIGNMENTS : "has many"
    PATIENTS ||--o{ CASES : "creates"
    DOCTORS ||--o{ CASES : "manages"
    PATIENTS ||--o{ REPORTS : "owns"
    REPORTS }o--o| CASES : "linked to"
    
    USERS {
        string id PK
        string email UK
        string hashed_password
        string role
        string name
        boolean is_onboarded
        datetime created_at
    }
    
    PATIENTS {
        string user_id PK_FK
        string patient_id UK
        date date_of_birth
        string gender
        array medical_history
        array allergies
        array current_medications
        string emergency_contact
    }
    
    DOCTORS {
        string user_id PK_FK
        string doctor_id UK
        string specialisation
        string license_number
        int max_patients
        string department
    }
    
    ASSIGNMENTS {
        string id PK
        string doctor_user_id FK
        string patient_user_id FK
        boolean is_active
        datetime assigned_at
        datetime revoked_at
    }
    
    CASES {
        string id PK
        string case_id UK
        string mongo_case_id
        string patient_id FK
        string doctor_id FK
        string status
        string chief_complaint
        datetime created_at
        datetime updated_at
    }
    
    REPORTS {
        string id PK
        string patient_id FK
        string case_id FK
        string uploaded_by FK
        string file_name
        string file_type
        string storage_path
        string mongo_analysis_id
        datetime created_at
    }
    
    NOTIFICATIONS {
        string id PK
        string user_id FK
        string type
        string title
        string message
        string link
        boolean is_read
        datetime created_at
    }
```

### MongoDB Collections Structure

```mermaid
graph LR
    subgraph "MongoDB Collections"
        Cases[cases<br/>Clinical SOAP Notes]
        Analysis[report_analysis<br/>AI Extracted Data]
        Chat[chat_sessions<br/>Conversation History]
        
        Cases -->|Contains| SOAP[Subjective<br/>Objective<br/>Assessment<br/>Plan]
        Cases -->|Contains| Notes[Doctor Notes<br/>Audit Trail]
        
        Analysis -->|Contains| Extract[Extracted Data<br/>Lab Results<br/>Diagnoses]
        Analysis -->|Contains| Predict[Diabetes Predictions<br/>Features<br/>Confidence]
        
        Chat -->|Contains| Messages[Message History<br/>Context<br/>Metadata]
        Chat -->|Contains| Reports[Attached Reports<br/>Analysis Links]
    end
    
    style Cases fill:#47A248
    style Analysis fill:#47A248
    style Chat fill:#47A248
```

---

## 3. Authentication & Onboarding Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Postgres
    
    %% Registration
    User->>Frontend: Enter email, password, role
    Frontend->>API: POST /auth/register
    API->>API: Hash password (bcrypt)
    API->>Postgres: Insert into users table
    API->>API: Generate JWT token
    API-->>Frontend: Return token + user info
    Frontend-->>User: Show onboarding prompt
    
    %% Onboarding
    User->>Frontend: Fill profile details
    alt User is Patient
        Frontend->>API: POST /users/onboard<br/>(DOB, medical history, allergies)
        API->>Postgres: Insert into patients table
    else User is Doctor
        Frontend->>API: POST /users/onboard<br/>(specialization, license, max_patients)
        API->>Postgres: Insert into doctors table
    end
    API->>Postgres: Update users.is_onboarded = true
    API-->>Frontend: Profile complete
    Frontend-->>User: Redirect to dashboard
    
    %% Login
    User->>Frontend: Enter credentials
    Frontend->>API: POST /auth/login
    API->>Postgres: Verify email + password
    API->>API: Generate JWT token
    API-->>Frontend: Return token + is_onboarded flag
    alt is_onboarded = false
        Frontend-->>User: Redirect to onboarding
    else is_onboarded = true
        Frontend-->>User: Redirect to dashboard
    end
```

---

## 4. Doctor-Patient Assignment Flow

```mermaid
sequenceDiagram
    participant Patient
    participant Doctor
    participant API
    participant Postgres
    participant Notif as Notification System
    
    %% Patient initiates assignment
    Patient->>API: POST /assignments/assign<br/>{specialization: "Cardiology"}
    API->>Postgres: Query doctors by specialization
    API->>Postgres: COUNT active assignments per doctor
    API->>API: Find doctor with min(patient_count)
    
    alt Doctor available (count < max_patients)
        API->>Postgres: INSERT into assignments<br/>(doctor_id, patient_id, is_active=true)
        API->>Notif: Create notification for patient
        API-->>Patient: Assignment successful
        API->>Notif: Create notification for doctor
        Notif-->>Doctor: New patient assigned
    else All doctors at capacity
        API-->>Patient: Error: No available doctors
    end
    
    %% Doctor views patients
    Doctor->>API: GET /assignments/patient
    API->>Postgres: SELECT patients WHERE<br/>doctor_id = current_user<br/>AND is_active = true
    API-->>Doctor: List of active patients
    
    %% Patient views doctors
    Patient->>API: GET /assignments/doctors
    API->>Postgres: SELECT doctors WHERE<br/>patient_id = current_user<br/>AND is_active = true
    API-->>Patient: List of assigned doctors
    
    %% Revoke assignment
    Doctor->>API: POST /assignments/revoke<br/>{patient_id, reason}
    API->>Postgres: UPDATE assignments<br/>SET is_active=false, revoked_at=now()
    API->>Notif: Create notification for patient
    API-->>Doctor: Revoked successfully
    Notif-->>Patient: Assignment revoked
```

---

## 5. Medical Case Management Flow

```mermaid
sequenceDiagram
    participant Patient
    participant Doctor
    participant API
    participant Postgres
    participant MongoDB
    participant Notif
    
    %% Case Creation
    Patient->>API: POST /cases<br/>{symptoms, vitals, history}
    API->>Postgres: Get assigned doctor_id
    
    alt Has assigned doctor
        API->>MongoDB: Create SOAP document<br/>{subjective, objective, ...}
        MongoDB-->>API: Return mongo_id
        API->>Postgres: INSERT case<br/>(patient_id, doctor_id, mongo_id)
        Postgres-->>API: Return case_id
        API->>Notif: Notify doctor of new case
        API-->>Patient: Case created: CASE20260123XXX
        Notif-->>Doctor: New case assigned
    else No assigned doctor
        API-->>Patient: Error: No doctor assigned
    end
    
    %% View Case Details
    Doctor->>API: GET /cases/{case_id}
    API->>Postgres: SELECT case WHERE id = case_id
    API->>API: Verify doctor_id = current_user
    API->>MongoDB: GET document by mongo_case_id
    API->>API: Merge SQL + NoSQL data
    API-->>Doctor: Complete case with SOAP notes
    
    %% Add Doctor Notes
    Doctor->>API: PATCH /cases/{case_id}<br/>{doctor_notes, assessment, plan}
    API->>Postgres: Verify ownership
    API->>MongoDB: PUSH to doctor_notes array<br/>UPDATE assessment, plan sections
    API->>MongoDB: PUSH to audit_trail
    API->>Postgres: UPDATE updated_at timestamp
    API->>Notif: Notify patient of update
    API-->>Doctor: Notes added successfully
    Notif-->>Patient: Doctor added notes
    
    %% Approve Case
    Doctor->>API: POST /cases/{case_id}/approve<br/>{approval_notes}
    API->>Postgres: UPDATE status = 'approved_by_doctor'
    API->>MongoDB: ADD approval entry to audit_trail
    API->>Notif: Notify patient of approval
    API-->>Doctor: Case approved
    Notif-->>Patient: Case approved by doctor
    
    %% List Cases
    Patient->>API: GET /cases
    API->>Postgres: SELECT cases WHERE patient_id = current_user
    API-->>Patient: List of cases (summary only)
    
    Doctor->>API: GET /cases
    API->>Postgres: SELECT cases WHERE doctor_id = current_user
    API-->>Doctor: List of assigned cases
```

---

## 6. Report Upload & AI Analysis Flow

```mermaid
sequenceDiagram
    participant Doctor
    participant API
    participant Postgres
    participant Supabase
    participant MongoDB
    participant Gemini
    participant XGBoost
    participant Notif
    
    %% Get Available Patients
    Doctor->>API: GET /reports/available-patients
    API->>Postgres: SELECT patients FROM assignments<br/>WHERE doctor_id = current_user<br/>AND is_active = true
    API-->>Doctor: List of patients
    
    %% Generate Upload URL
    Doctor->>API: POST /reports/upload-url<br/>{filename, patient_id, case_id}
    API->>Postgres: Verify patient assignment
    
    alt Patient assigned to doctor
        API->>API: Generate UUID report_id
        API->>Supabase: Create signed upload URL<br/>(valid 1 hour)
        Supabase-->>API: Return upload_url
        API->>Postgres: INSERT report metadata<br/>(pending status)
        API-->>Doctor: {report_id, upload_url, storage_path}
    else Patient not assigned
        API-->>Doctor: Error: Patient not assigned
    end
    
    %% Upload File
    Doctor->>Supabase: PUT {file} to upload_url
    Supabase-->>Doctor: Upload complete
    
    %% Confirm Upload & Trigger AI
    Doctor->>API: POST /reports/{report_id}/confirm<br/>{storage_path, file_size}
    API->>Postgres: UPDATE report.file_size
    API->>Notif: Notify assigned doctors
    API->>API: Trigger background AI extraction
    API-->>Doctor: Upload confirmed
    
    %% Background AI Extraction
    par AI Processing
        API->>Supabase: Download file from storage_path
        Supabase-->>API: Return file bytes
        
        alt File is PDF
            API->>API: Extract text using PyMuPDF
        else File is Image
            API->>API: Extract text using PIL + pytesseract
        end
        
        API->>API: TF-IDF keyword extraction<br/>(medical terms)
        
        API->>Gemini: POST analyze_medical_report<br/>{text, keywords, schema}
        Gemini-->>API: Structured data<br/>{patient_info, lab_results, diagnoses}
        
        API->>MongoDB: INSERT report_analysis<br/>{extracted_data, status="completed"}
        MongoDB-->>API: Return analysis_id
        
        alt Has diabetes indicators
            API->>XGBoost: Predict diabetes<br/>{glucose, BMI, age, etc}
            XGBoost-->>API: {prediction, confidence}
            API->>MongoDB: UPDATE analysis<br/>(add prediction)
        end
        
        API->>Postgres: UPDATE report.mongo_analysis_id
        API->>MongoDB: LOG activity<br/>(extraction completed)
        API->>Notif: Notify patient of analysis
    end
    
    Notif-->>Doctor: Analysis complete
```

---

## 7. AI Chat System Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant MongoDB
    participant Postgres
    participant Supabase
    participant Gemini
    
    %% Start Chat Session
    User->>API: POST /ai/chat/start<br/>{title, report_ids: []}
    
    alt With reports attached
        API->>Postgres: Verify report access
        API->>MongoDB: Get report analyses
        API->>Supabase: Download report files
        API->>API: Extract text + TF-IDF keywords
        API->>API: Build context (once)<br/>{reports, keywords, analyses}
    else Without reports
        API->>API: Initialize empty context
    end
    
    API->>MongoDB: INSERT chat_session<br/>{user_id, context, messages: []}
    MongoDB-->>API: Return session_id
    API-->>User: {session_id, title}
    
    %% Send Message
    User->>API: POST /ai/chat/{session_id}/message<br/>{content: "What are my glucose levels?"}
    API->>MongoDB: GET chat_session + history
    API->>API: Build conversation context<br/>(last 10 messages + report data)
    
    API->>Gemini: POST generate_content<br/>{history, current_message, reports}
    Gemini-->>API: AI response
    
    API->>MongoDB: PUSH user_message to messages[]
    API->>MongoDB: PUSH ai_response to messages[]
    API->>MongoDB: UPDATE last_activity timestamp
    API-->>User: AI response
    
    %% Attach Reports to Existing Chat
    User->>API: PATCH /ai/chat/{session_id}/reports<br/>{report_ids: ["report-123"]}
    API->>Postgres: Verify report access
    API->>MongoDB: Get analyses for new reports
    API->>Supabase: Download report files
    API->>API: Extract text + keywords
    API->>MongoDB: UPDATE chat_session.context<br/>(append new reports)
    API-->>User: Reports attached successfully
    
    %% Get Chat History
    User->>API: GET /ai/chat/{session_id}/history
    API->>MongoDB: GET chat_session.messages
    API-->>User: Full conversation history
    
    %% List All Chats
    User->>API: GET /ai/chats
    API->>MongoDB: FIND chats WHERE user_id = current_user
    API-->>User: List of chat sessions<br/>(title, last_activity, message_count)
    
    %% Delete Chat
    User->>API: DELETE /ai/chat/{session_id}
    API->>MongoDB: DELETE chat_session
    API-->>User: Chat deleted
```

---

## 8. Diabetes Dashboard Flow

```mermaid
flowchart TD
    Start([Patient/Doctor Opens<br/>Diabetes Dashboard]) --> Auth{Authenticated?}
    
    Auth -->|No| Login[Redirect to Login]
    Auth -->|Yes| Role{User Role?}
    
    Role -->|Patient| GetPatientData[GET /patient/diabetes-dashboard]
    Role -->|Doctor| SelectPatient[Select Patient from List]
    SelectPatient --> GetDoctorData[GET /doctor/diabetes-dashboard/{patient_id}]
    
    GetPatientData --> CheckData{Has Diabetes<br/>Data?}
    GetDoctorData --> CheckData
    
    CheckData -->|No| EmptyState[Show Empty State<br/>"Upload reports for analysis"]
    
    CheckData -->|Yes| CheckConditions{Diabetes in<br/>Medical History<br/>OR<br/>AI Prediction?}
    
    CheckConditions -->|No| NoAccess[No diabetes data found]
    
    CheckConditions -->|Yes| FetchData[Fetch Data from:<br/>- MongoDB analyses<br/>- PostgreSQL user data<br/>- Report extractions]
    
    FetchData --> CalculateStatus{Calculate<br/>Diabetes Status}
    
    CalculateStatus -->|All Predictions = Diabetes| Diabetic[Status: DIABETIC]
    CalculateStatus -->|Some Predictions = Diabetes| AtRisk[Status: AT-RISK]
    CalculateStatus -->|No Predictions = Diabetes| Monitoring[Status: MONITORING]
    
    Diabetic --> BuildDashboard[Build Dashboard Data]
    AtRisk --> BuildDashboard
    Monitoring --> BuildDashboard
    
    BuildDashboard --> Aggregation[Aggregate:<br/>- Prediction history<br/>- HbA1c trends<br/>- Glucose trends<br/>- BMI history<br/>- Risk factors<br/>- Recommendations]
    
    Aggregation --> Response[Return Dashboard JSON]
    Response --> Display[Display:<br/>- Status badge<br/>- Latest prediction<br/>- Trend charts<br/>- Risk factors<br/>- Recommendations]
    
    Display --> Actions{User Action}
    
    Actions -->|Upload Report| ReportFlow[Go to Report Upload]
    Actions -->|View Details| DrillDown[Navigate to Report/Analysis]
    Actions -->|Refresh| Start
    
    style Diabetic fill:#ff6b6b
    style AtRisk fill:#ffa500
    style Monitoring fill:#4caf50
    style EmptyState fill:#e0e0e0
```

---

## 9. Notification System Flow

```mermaid
sequenceDiagram
    participant System
    participant NotifService
    participant Postgres
    participant Frontend
    participant User
    
    %% Notification Generation
    Note over System: Event Occurs<br/>(case created, report uploaded, etc.)
    System->>NotifService: create_notification()<br/>{user_id, type, title, message, link}
    NotifService->>Postgres: INSERT notification<br/>(is_read = false)
    NotifService-->>System: Notification created
    
    %% Dashboard Load (Initial Badge)
    User->>Frontend: Open Dashboard
    Frontend->>Postgres: GET /patient/dashboard<br/>OR GET /doctor/dashboard
    Postgres-->>Frontend: {notifications_unread: 3, ...}
    Frontend->>Frontend: Set badge count = 3
    Frontend-->>User: Show red badge (3)
    
    %% Polling for Updates
    loop Every 60 seconds
        Frontend->>Postgres: GET /notifications/unread-count
        Postgres-->>Frontend: {count: 5}
        Frontend->>Frontend: Update badge count = 5
    end
    
    %% Open Notification Dropdown
    User->>Frontend: Click bell icon
    Frontend->>Postgres: GET /notifications?page=1&limit=20
    Postgres-->>Frontend: {total, unread_count, items: [...]}
    Frontend-->>User: Show notification list<br/>(highlight unread)
    
    %% Click Notification
    User->>Frontend: Click notification item
    Frontend->>Postgres: PATCH /notifications/{id}/read
    Postgres->>Postgres: UPDATE is_read = true
    Postgres-->>Frontend: Success
    Frontend->>Frontend: Update badge count -= 1
    Frontend->>Frontend: Navigate to notification.link
    Frontend-->>User: Show target page
    
    %% Mark All Read
    User->>Frontend: Click "Mark all as read"
    Frontend->>Postgres: PATCH /notifications/read-all
    Postgres->>Postgres: UPDATE all unread<br/>SET is_read = true
    Postgres-->>Frontend: Success
    Frontend->>Frontend: Set badge count = 0
    Frontend-->>User: All notifications cleared
```

---

## 10. Complete User Journey

### 10.1 Patient Journey

```mermaid
graph TD
    Start([Patient Signs Up]) --> Register[POST /auth/register<br/>role: patient]
    Register --> Onboard[POST /users/onboard<br/>medical history, allergies]
    Onboard --> Dashboard[View Dashboard<br/>GET /patient/dashboard]
    
    Dashboard --> AssignDoc{Has Assigned<br/>Doctor?}
    
    AssignDoc -->|No| FindDoc[POST /assignments/assign<br/>specialization: Cardiology]
    FindDoc --> WaitApproval[Doctor Auto-Assigned<br/>Via Load Balancing]
    WaitApproval --> AssignDoc
    
    AssignDoc -->|Yes| CreateCase[POST /cases<br/>symptoms, vitals]
    CreateCase --> Notif1[Notification: Case Created]
    Notif1 --> UploadReport[POST /reports/upload-url<br/>Upload medical report]
    
    UploadReport --> ConfirmUpload[POST /reports/{id}/confirm]
    ConfirmUpload --> AIAnalysis[Background: AI Extracts Data]
    AIAnalysis --> Notif2[Notification: Analysis Complete]
    
    Notif2 --> ViewReport[GET /reports/{id}<br/>View analysis results]
    ViewReport --> DiabetesDash[GET /patient/diabetes-dashboard<br/>View diabetes trends]
    
    DiabetesDash --> StartChat[POST /ai/chat/start<br/>Attach reports]
    StartChat --> AskQuestions[POST /ai/chat/{id}/message<br/>"Explain my glucose levels"]
    AskQuestions --> GetResponse[Receive AI explanation]
    
    GetResponse --> DoctorReview{Doctor Added<br/>Notes?}
    DoctorReview -->|Yes| Notif3[Notification: Doctor Notes Added]
    Notif3 --> ViewCase[GET /cases/{case_id}<br/>View updated case]
    
    ViewCase --> Approved{Case<br/>Approved?}
    Approved -->|No| WaitApproval2[Wait for doctor approval]
    Approved -->|Yes| Notif4[Notification: Case Approved]
    Notif4 --> FollowUp[Create follow-up case<br/>if needed]
    FollowUp --> CreateCase
    
    WaitApproval2 --> DoctorReview
    
    style Start fill:#4CAF50
    style Notif1 fill:#FFC107
    style Notif2 fill:#FFC107
    style Notif3 fill:#FFC107
    style Notif4 fill:#FFC107
    style AIAnalysis fill:#2196F3
```

### 10.2 Doctor Journey

```mermaid
graph TD
    Start([Doctor Signs Up]) --> Register[POST /auth/register<br/>role: doctor]
    Register --> Onboard[POST /users/onboard<br/>specialization, license]
    Onboard --> Dashboard[View Dashboard<br/>GET /doctor/dashboard]
    
    Dashboard --> ViewPatients[GET /assignments/patient<br/>View assigned patients]
    ViewPatients --> Notif1[Notification: New Case Assigned]
    
    Notif1 --> ViewCases[GET /cases<br/>List all cases]
    ViewCases --> SelectCase[GET /cases/{case_id}<br/>Review case details]
    
    SelectCase --> ViewReports[GET /reports/patient/{patient_id}<br/>Review patient reports]
    ViewReports --> ViewAnalysis[Check AI analysis<br/>GET /ai/report/{report_id}]
    
    ViewAnalysis --> AvailablePatients[GET /reports/available-patients<br/>Check patients for upload]
    AvailablePatients --> UploadReport{Need to Upload<br/>Report?}
    
    UploadReport -->|Yes| GenerateURL[POST /reports/upload-url<br/>Select patient, upload file]
    GenerateURL --> ConfirmUpload[POST /reports/{id}/confirm<br/>Trigger AI analysis]
    ConfirmUpload --> Notif2[Notification: Analysis Complete]
    
    UploadReport -->|No| AddNotes[PATCH /cases/{case_id}<br/>Add assessment & plan]
    Notif2 --> AddNotes
    
    AddNotes --> Notif3[Notification: Patient notified<br/>of doctor notes]
    Notif3 --> ReviewStatus{Ready for<br/>Approval?}
    
    ReviewStatus -->|No| MoreInfo[Request more info<br/>Update case status]
    MoreInfo --> ViewCases
    
    ReviewStatus -->|Yes| ApproveCase[POST /cases/{case_id}/approve<br/>Add approval notes]
    ApproveCase --> Notif4[Notification: Patient notified<br/>of approval]
    
    Notif4 --> ViewDashboard[GET /doctor/diabetes-dashboard/{patient_id}<br/>Monitor patient health]
    ViewDashboard --> ViewPatients
    
    style Start fill:#2196F3
    style Notif1 fill:#FFC107
    style Notif2 fill:#FFC107
    style Notif3 fill:#FFC107
    style Notif4 fill:#FFC107
    style ApproveCase fill:#4CAF50
```

---

## 11. Module Interaction Map

```mermaid
graph TD
    subgraph "User Entry Points"
        Auth[Auth Module]
        Users[Users Module]
    end
    
    subgraph "Core Healthcare Logic"
        Assign[Assignments Module]
        Cases[Cases Module]
        Reports[Reports Module]
    end
    
    subgraph "Intelligence & Analytics"
        AI[AI Module]
        Dash[Dashboards Module]
    end
    
    subgraph "Communication"
        Notif[Notifications Module]
    end
    
    subgraph "Data Stores"
        PG[(PostgreSQL)]
        MG[(MongoDB)]
        SB[Supabase Storage]
    end
    
    subgraph "External"
        GM[Gemini AI]
        XG[XGBoost]
    end
    
    Auth --> Users
    Users --> Assign
    Assign --> Cases
    Cases --> Reports
    Reports --> AI
    AI --> Dash
    
    Auth --> Notif
    Cases --> Notif
    Reports --> Notif
    AI --> Notif
    
    Auth -.-> PG
    Users -.-> PG
    Assign -.-> PG
    Cases -.-> PG
    Cases -.-> MG
    Reports -.-> PG
    Reports -.-> SB
    AI -.-> MG
    AI -.-> GM
    AI -.-> XG
    Dash -.-> PG
    Dash -.-> MG
    Notif -.-> PG
    
    style Auth fill:#4CAF50
    style AI fill:#2196F3
    style Dash fill:#FF9800
    style Notif fill:#FFC107
```

---

## 12. Data Flow: Report Upload to Diabetes Dashboard

```mermaid
flowchart LR
    subgraph "1. Upload"
        U1[Doctor/Patient<br/>Uploads Report]
        U2[Generate Upload URL]
        U3[Upload to Supabase]
        U4[Confirm Upload]
    end
    
    subgraph "2. AI Processing"
        A1[Download File]
        A2[Extract Text<br/>PDF/Image]
        A3[TF-IDF Keywords]
        A4[Gemini Analysis]
        A5[Extract Features]
        A6{Has Diabetes<br/>Indicators?}
        A7[XGBoost Prediction]
    end
    
    subgraph "3. Storage"
        S1[(PostgreSQL<br/>Report Metadata)]
        S2[(MongoDB<br/>Analysis Data)]
        S3[(Supabase<br/>File Storage)]
    end
    
    subgraph "4. Dashboard"
        D1[Check Access:<br/>Medical History<br/>OR AI Prediction]
        D2[Aggregate Data:<br/>All Reports +<br/>All Analyses]
        D3[Calculate Status:<br/>Diabetic/At-Risk]
        D4[Build Trends:<br/>HbA1c, Glucose, BMI]
        D5[Generate<br/>Recommendations]
        D6[Display Dashboard]
    end
    
    U1 --> U2 --> U3 --> U4
    U4 --> A1
    U3 --> S3
    
    A1 --> A2 --> A3 --> A4
    A4 --> A5 --> A6
    A6 -->|Yes| A7
    A6 -->|No| S2
    A7 --> S2
    
    U4 --> S1
    S2 --> S1
    
    S1 --> D1
    S2 --> D1
    D1 --> D2 --> D3 --> D4 --> D5 --> D6
    
    style A4 fill:#4285F4
    style A7 fill:#FF6B6B
    style D3 fill:#FFA500
    style D6 fill:#4CAF50
```

---

## 13. Security & Access Control Flow

```mermaid
flowchart TD
    Request[Incoming API Request] --> JWT{JWT Token<br/>Present?}
    
    JWT -->|No| Reject1[401 Unauthorized]
    JWT -->|Yes| Validate{Token Valid<br/>& Not Expired?}
    
    Validate -->|No| Reject2[401 Unauthorized]
    Validate -->|Yes| Extract[Extract User Info:<br/>user_id, role, email]
    
    Extract --> RateLimit{Rate Limit<br/>Exceeded?}
    RateLimit -->|Yes| Reject3[429 Too Many Requests]
    RateLimit -->|No| Endpoint{Which Endpoint?}
    
    Endpoint -->|Public| Execute[Execute Request]
    Endpoint -->|Protected| CheckRole{Role Check}
    
    CheckRole -->|Doctor-Only| IsDoctor{User Role<br/>= Doctor?}
    CheckRole -->|Patient-Only| IsPatient{User Role<br/>= Patient?}
    CheckRole -->|Any Authenticated| Execute
    
    IsDoctor -->|No| Reject4[403 Forbidden]
    IsDoctor -->|Yes| CheckAssignment{Resource Belongs<br/>to Assigned Patient?}
    
    IsPatient -->|No| Reject5[403 Forbidden]
    IsPatient -->|Yes| CheckOwnership{Resource Belongs<br/>to User?}
    
    CheckAssignment -->|No| Reject6[403 Forbidden:<br/>Patient not assigned]
    CheckAssignment -->|Yes| Execute
    
    CheckOwnership -->|No| Reject7[403 Forbidden:<br/>Not your resource]
    CheckOwnership -->|Yes| Execute
    
    Execute --> DB[Database Query]
    DB --> Response[200 OK + Data]
    
    style Reject1 fill:#f44336
    style Reject2 fill:#f44336
    style Reject3 fill:#ff9800
    style Reject4 fill:#f44336
    style Reject5 fill:#f44336
    style Reject6 fill:#f44336
    style Reject7 fill:#f44336
    style Response fill:#4CAF50
```

---

## 14. API Request/Response Pattern

```mermaid
sequenceDiagram
    participant Client
    participant Middleware
    participant Controller
    participant Service
    participant Database
    
    Client->>Middleware: HTTP Request + JWT
    
    Note over Middleware: 1. CORS Check<br/>2. Rate Limiting<br/>3. JWT Validation
    
    alt Invalid Request
        Middleware-->>Client: 401/403/429 Error
    else Valid Request
        Middleware->>Controller: Validated Request
    end
    
    Note over Controller: 1. Parse Pydantic Model<br/>2. Extract CurrentUser
    
    alt Validation Failed
        Controller-->>Client: 422 Validation Error
    else Valid Input
        Controller->>Service: Call Service Method
    end
    
    Note over Service: 1. Business Logic<br/>2. Access Control<br/>3. Data Processing
    
    Service->>Database: Query/Update Data
    Database-->>Service: Data Result
    
    alt Service Error
        Service-->>Controller: Raise Exception
        Controller-->>Client: 400/404/500 Error
    else Success
        Service-->>Controller: Return Data
        Controller-->>Client: 200 OK + JSON Response
    end
```

---

## 15. Background Task Processing

```mermaid
flowchart TD
    Trigger[Report Upload Confirmed] --> Background[FastAPI Background Task]
    
    Background --> Download[Download File<br/>from Supabase]
    Download --> Extract{File Type?}
    
    Extract -->|PDF| PyMuPDF[Extract Text<br/>using PyMuPDF]
    Extract -->|Image| Tesseract[OCR using<br/>pytesseract]
    
    PyMuPDF --> TFIDF[TF-IDF Keyword<br/>Extraction]
    Tesseract --> TFIDF
    
    TFIDF --> HighlightTerms[Highlight Important<br/>Medical Terms]
    HighlightTerms --> PreparePrompt[Prepare Gemini Prompt<br/>with Schema]
    
    PreparePrompt --> CallGemini[Call Gemini API<br/>analyze_medical_report]
    CallGemini --> Parse{Response Valid?}
    
    Parse -->|No| Retry{Retry Count<br/>< 3?}
    Retry -->|Yes| CallGemini
    Retry -->|No| LogError[Log Error to MongoDB<br/>status: failed]
    
    Parse -->|Yes| SaveMongo[Save to MongoDB<br/>report_analysis collection]
    SaveMongo --> CheckDiabetes{Has Diabetes<br/>Features?}
    
    CheckDiabetes -->|No| UpdateReport1[Update Report<br/>mongo_analysis_id]
    CheckDiabetes -->|Yes| XGBoostPredict[Run XGBoost<br/>Diabetes Prediction]
    
    XGBoostPredict --> UpdateMongo[Update MongoDB<br/>with prediction]
    UpdateMongo --> UpdateReport2[Update Report<br/>mongo_analysis_id]
    
    UpdateReport1 --> LogActivity1[Log Activity:<br/>extraction_completed]
    UpdateReport2 --> LogActivity2[Log Activity:<br/>analysis_completed]
    
    LogActivity1 --> NotifyUser1[Send Notification:<br/>report_analyzed]
    LogActivity2 --> NotifyUser2[Send Notification:<br/>report_analyzed]
    
    LogError --> NotifyError[Send Notification:<br/>analysis_failed]
    
    style CallGemini fill:#4285F4
    style XGBoostPredict fill:#FF6B6B
    style LogError fill:#f44336
    style NotifyUser1 fill:#4CAF50
    style NotifyUser2 fill:#4CAF50
```

---

## Key Technologies Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | FastAPI | High-performance async Python framework |
| **Authentication** | JWT (HS256) + Passlib | Secure token-based auth with bcrypt hashing |
| **Relational DB** | PostgreSQL + SQLAlchemy | User accounts, assignments, case metadata |
| **Document DB** | MongoDB + PyMongo | Clinical SOAP notes, AI analyses, chat history |
| **File Storage** | Supabase Storage | Medical reports, images (PDF, PNG, JPEG) |
| **AI Analysis** | Google Gemini 2.5 Flash | Medical data extraction, conversational AI |
| **ML Prediction** | XGBoost | Diabetes risk prediction from lab results |
| **Keyword Extraction** | TF-IDF (scikit-learn) | Highlighting important medical terms for AI |
| **Rate Limiting** | SlowAPI | API request throttling |
| **CORS** | FastAPI Middleware | Cross-origin request handling |

---

## Notes for Implementation

1. **All API calls require JWT authentication** except:
   - `/auth/register`
   - `/auth/login`
   - `/assignments/specialities`

2. **Access Control Rules**:
   - Patients can only access their own data
   - Doctors can only access data for assigned patients
   - Assignments are checked at the service layer

3. **Dual-Write Pattern** (Cases):
   - PostgreSQL: Fast queries, relational integrity
   - MongoDB: Flexible clinical data, audit trails

4. **Background Processing**:
   - AI analysis runs asynchronously after report upload
   - No blocking of API responses
   - Notifications sent when processing completes

5. **Data Flow Direction**:
   - Patient creates case → Doctor assigned via workload balancing
   - Reports uploaded → AI extracts → Diabetes prediction (if applicable)
   - All updates trigger notifications to relevant users

---

**End of Document**

*This workflow documentation is maintained alongside code changes. Update diagrams when adding new features or changing flows.*
