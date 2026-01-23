# Diabetes Dashboard Module Documentation

## Overview
The diabetes dashboard module provides specialized diabetes monitoring and tracking features for patients with diabetes or at risk of developing diabetes. It aggregates data from AI-powered report analysis, medical history, and lab results to provide comprehensive diabetes management insights. The dashboard is accessible to both patients (viewing their own data) and doctors (viewing assigned patients' data).

---

## 1. Core Concepts

### **Access Control (Option C)**
The diabetes dashboard is accessible when either condition is met:
1. **Medical History**: Patient has "diabetes" mentioned in their medical history, OR
2. **AI Prediction**: Any AI analysis has predicted diabetes for this patient

If neither condition is met, the dashboard returns an empty response with a message guiding users to upload reports for analysis.

### **Data Sources**
The dashboard aggregates data from multiple sources:
- **MongoDB `report_analysis` collection**: AI predictions, extracted features, extracted data
- **PostgreSQL `users` table**: Patient medical history, demographics
- **Reports**: Lab results including HbA1c, fasting glucose, BMI from report extractions

### **Diabetes Status Classification**
- **`diabetic`**: Patient has diabetes in medical history OR all predictions indicate diabetes
- **`at-risk`**: Some (but not all) predictions indicate diabetes
- **`monitoring`**: Patient has analyses but no diabetes predictions
- **`null`**: No diabetes-related data available

### **Trends Tracking**
The dashboard tracks three key diabetes indicators over time:
1. **HbA1c Levels**: Glycated hemoglobin measurements (%)
2. **Fasting Glucose**: Blood glucose readings (mg/dL)
3. **BMI**: Body Mass Index values and categories

---

## 2. API Endpoints

### **Get Patient Diabetes Dashboard**
Get diabetes-specific data for the authenticated patient.

- **Endpoint**: `GET /patient/diabetes-dashboard`
- **Auth**: Required (Patient only)
- **Response**:
```json
{
  "has_diabetes_data": true,
  "diabetes_status": "at-risk",
  "latest_prediction": {
    "analysis_id": "65a1b2c3d4e5f6789abcdef0",
    "report_id": "report-uuid-123",
    "report_name": "lab_results_jan2026.pdf",
    "prediction_label": "no_diabetes",
    "confidence": 0.87,
    "analyzed_at": "2026-01-20T15:30:00Z"
  },
  "prediction_history": [
    {
      "analysis_id": "65a1b2c3d4e5f6789abcdef0",
      "report_id": "report-uuid-123",
      "report_name": "lab_results_jan2026.pdf",
      "prediction_label": "no_diabetes",
      "confidence": 0.87,
      "analyzed_at": "2026-01-20T15:30:00Z"
    },
    {
      "analysis_id": "65a1b2c3d4e5f6789abcdef1",
      "report_id": "report-uuid-456",
      "report_name": "health_checkup_dec2025.pdf",
      "prediction_label": "diabetes",
      "confidence": 0.72,
      "analyzed_at": "2025-12-15T10:00:00Z"
    }
  ],
  "trends": {
    "hba1c_readings": [
      {
        "date": "2026-01-20",
        "value": 5.4,
        "report_id": "report-uuid-123",
        "status": "Normal"
      },
      {
        "date": "2025-12-15",
        "value": 6.2,
        "report_id": "report-uuid-456",
        "status": "Pre-diabetic"
      }
    ],
    "fasting_glucose": [
      {
        "date": "2026-01-20",
        "value": 98,
        "report_id": "report-uuid-123",
        "status": "Normal"
      },
      {
        "date": "2025-12-15",
        "value": 115,
        "report_id": "report-uuid-456",
        "status": "Pre-diabetic"
      }
    ],
    "bmi_history": [
      {
        "date": "2026-01-20",
        "value": 26.5,
        "report_id": "report-uuid-123",
        "category": "Overweight"
      },
      {
        "date": "2025-12-15",
        "value": 27.8,
        "report_id": "report-uuid-456",
        "category": "Overweight"
      }
    ]
  },
  "risk_factors": [
    {
      "factor": "Overweight",
      "severity": "medium",
      "description": "BMI of 26.5 indicates overweight status."
    },
    {
      "factor": "Pre-diabetic HbA1c",
      "severity": "medium",
      "description": "Previous HbA1c of 6.2% indicated pre-diabetic range."
    }
  ],
  "recommendations": [
    "Monitor blood glucose levels regularly",
    "Maintain a healthy weight through diet and exercise",
    "Limit intake of processed foods and sugars",
    "Stay physically active - 150 minutes of exercise per week",
    "Get HbA1c tested every 6 months",
    "Upload new reports regularly for AI monitoring"
  ],
  "total_analyses": 2,
  "diabetic_predictions_count": 1,
  "average_confidence": 0.795
}
```

**Response (Empty State)**:
```json
{
  "has_diabetes_data": false,
  "message": "No diabetic activity found. Upload medical reports for AI analysis to track diabetes indicators.",
  "diabetes_status": null,
  "latest_prediction": null,
  "prediction_history": [],
  "trends": {
    "hba1c_readings": [],
    "fasting_glucose": [],
    "bmi_history": []
  },
  "risk_factors": [],
  "recommendations": [
    "Upload medical reports for diabetes screening",
    "Maintain a healthy lifestyle",
    "Get regular health check-ups"
  ],
  "total_analyses": 0,
  "diabetic_predictions_count": 0,
  "average_confidence": null
}
```

**Use Cases:**
- Patient monitoring their diabetes status
- Tracking progress over time
- Viewing risk factors and recommendations
- Understanding AI predictions

**Error Cases:**
- `401`: Not authenticated
- `403`: User is not a patient

---

### **Get Doctor View of Patient Diabetes Dashboard**
Get diabetes-specific data for a specific patient (doctor access only).

- **Endpoint**: `GET /patient/{patient_id}/diabetes-dashboard`
- **Auth**: Required (Doctor only)
- **Path Parameters**:
  - `patient_id` (string): UUID of the patient
- **Response**: Same structure as patient endpoint (see above)

**Access Requirements:**
- User must be a doctor
- Patient must be assigned to the requesting doctor

**Use Cases:**
- Doctor reviewing assigned patient's diabetes status
- Monitoring patient progress between appointments
- Identifying patients needing intervention
- Preparing for patient consultations

**Error Cases:**
- `401`: Not authenticated
- `403`: User is not a doctor OR patient not assigned to doctor
- `404`: Patient not found

---

## 3. Data Models (Pydantic)

### **`DiabetesPrediction`**
Single AI diabetes prediction result.

| Field | Type | Description |
|-------|------|-------------|
| `analysis_id` | `str` | MongoDB analysis document ID. |
| `report_id` | `str` | Report UUID that was analyzed. |
| `report_name` | `str \| None` | Original filename of the report. |
| `prediction_label` | `str` | `"diabetes"` or `"no_diabetes"`. |
| `confidence` | `float` | Prediction confidence (0.0 to 1.0). |
| `analyzed_at` | `datetime` | When the analysis was performed. |

---

### **`HbA1cReading`**
HbA1c (Glycated Hemoglobin) measurement.

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Date of the reading. |
| `value` | `float` | HbA1c percentage value. |
| `report_id` | `str \| None` | Source report UUID. |
| `status` | `str \| None` | `"Normal"` (<5.7%), `"Pre-diabetic"` (5.7-6.4%), `"Diabetic"` (≥6.5%). |

**Clinical Reference:**
- **Normal**: < 5.7%
- **Pre-diabetic**: 5.7% - 6.4%
- **Diabetic**: ≥ 6.5%

---

### **`FastingGlucoseReading`**
Fasting blood glucose measurement.

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Date of the reading. |
| `value` | `float` | Glucose level in mg/dL. |
| `report_id` | `str \| None` | Source report UUID. |
| `status` | `str \| None` | `"Normal"` (<100), `"Pre-diabetic"` (100-125), `"Diabetic"` (≥126). |

**Clinical Reference:**
- **Normal**: < 100 mg/dL
- **Pre-diabetic**: 100 - 125 mg/dL
- **Diabetic**: ≥ 126 mg/dL

---

### **`BMIReading`**
Body Mass Index measurement.

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Date of the reading. |
| `value` | `float` | BMI value (kg/m²). |
| `report_id` | `str \| None` | Source report UUID. |
| `category` | `str \| None` | `"Underweight"`, `"Normal"`, `"Overweight"`, `"Obese"`. |

**BMI Categories:**
- **Underweight**: < 18.5
- **Normal**: 18.5 - 24.9
- **Overweight**: 25.0 - 29.9
- **Obese**: ≥ 30.0

---

### **`DiabetesRiskFactor`**
Identified risk factor for diabetes.

| Field | Type | Description |
|-------|------|-------------|
| `factor` | `str` | Risk factor name (e.g., "Obesity", "Elevated HbA1c"). |
| `severity` | `str` | `"low"`, `"medium"`, or `"high"`. |
| `description` | `str` | Detailed explanation of the risk factor. |

**Common Risk Factors:**
- **Obesity** (BMI ≥ 30): High severity
- **Overweight** (BMI 25-29.9): Medium severity
- **Elevated HbA1c** (≥ 6.5%): High severity
- **Pre-diabetic HbA1c** (5.7-6.4%): Medium severity
- **High Fasting Glucose** (≥ 126 mg/dL): High severity
- **Elevated Fasting Glucose** (100-125 mg/dL): Medium severity

---

### **`DiabetesTrends`**
Historical trends for diabetes indicators.

| Field | Type | Description |
|-------|------|-------------|
| `hba1c_readings` | `list[HbA1cReading]` | HbA1c measurements over time (max 20, newest first). |
| `fasting_glucose` | `list[FastingGlucoseReading]` | Fasting glucose readings (max 20, newest first). |
| `bmi_history` | `list[BMIReading]` | BMI measurements (max 20, newest first). |

---

### **`DiabetesDashboardResponse`**
Complete diabetes dashboard response.

| Field | Type | Description |
|-------|------|-------------|
| `has_diabetes_data` | `bool` | Whether diabetes data exists for this patient. |
| `message` | `str \| None` | Message shown when no data exists. |
| `diabetes_status` | `str \| None` | `"diabetic"`, `"at-risk"`, `"monitoring"`, or `null`. |
| `latest_prediction` | `DiabetesPrediction \| None` | Most recent AI prediction. |
| `prediction_history` | `list[DiabetesPrediction]` | All AI predictions (newest first). |
| `trends` | `DiabetesTrends` | Historical measurements and readings. |
| `risk_factors` | `list[DiabetesRiskFactor]` | Identified risk factors. |
| `recommendations` | `list[str]` | Personalized health recommendations. |
| `total_analyses` | `int` | Total number of analyses performed. |
| `diabetic_predictions_count` | `int` | Number of "diabetes" predictions. |
| `average_confidence` | `float \| None` | Average prediction confidence across all analyses. |

---

## 4. Frontend Integration Guide

### **Fetching Dashboard Data**

```typescript
// Patient viewing their own dashboard
const fetchMyDiabetesDashboard = async () => {
  const response = await api.get('/patient/diabetes-dashboard');
  return response;
};

// Doctor viewing patient's dashboard
const fetchPatientDiabetesDashboard = async (patientId: string) => {
  const response = await api.get(`/patient/${patientId}/diabetes-dashboard`);
  return response;
};
```

### **Handling Empty State**

```typescript
const DiabetesDashboard = ({ patientId }) => {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      const data = patientId 
        ? await fetchPatientDiabetesDashboard(patientId)
        : await fetchMyDiabetesDashboard();
      
      setDashboard(data);
      setLoading(false);
    };
    
    fetchData();
  }, [patientId]);

  if (loading) return <Spinner />;

  if (!dashboard.has_diabetes_data) {
    return (
      <EmptyState>
        <Icon name="file-plus" />
        <h2>No Diabetes Data Available</h2>
        <p>{dashboard.message}</p>
        <button onClick={() => navigate('/reports/upload')}>
          Upload Report
        </button>
      </EmptyState>
    );
  }

  return <DiabetesDashboardView dashboard={dashboard} />;
};
```

### **Displaying Status Badge**

```typescript
const StatusBadge = ({ status }: { status: string | null }) => {
  const statusConfig = {
    diabetic: { color: 'red', label: 'Diabetic', icon: 'alert-circle' },
    'at-risk': { color: 'yellow', label: 'At Risk', icon: 'alert-triangle' },
    monitoring: { color: 'blue', label: 'Monitoring', icon: 'activity' },
  };

  if (!status) return null;

  const config = statusConfig[status];

  return (
    <Badge color={config.color}>
      <Icon name={config.icon} />
      {config.label}
    </Badge>
  );
};
```

### **Rendering Prediction History**

```typescript
const PredictionHistory = ({ predictions }) => {
  return (
    <div className="prediction-timeline">
      {predictions.map((pred) => (
        <PredictionCard key={pred.analysis_id}>
          <div className="prediction-header">
            <h4>{pred.report_name || 'Analysis'}</h4>
            <time>{formatDate(pred.analyzed_at)}</time>
          </div>
          <div className="prediction-result">
            <span className={`label ${pred.prediction_label}`}>
              {pred.prediction_label === 'diabetes' ? 'Diabetes' : 'No Diabetes'}
            </span>
            <ConfidenceMeter value={pred.confidence * 100} />
          </div>
        </PredictionCard>
      ))}
    </div>
  );
};

const ConfidenceMeter = ({ value }) => (
  <div className="confidence-meter">
    <div className="bar" style={{ width: `${value}%` }} />
    <span>{value.toFixed(0)}% confidence</span>
  </div>
);
```

### **Charting Trends**

```typescript
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

const HbA1cChart = ({ readings }) => {
  const data = readings.map(r => ({
    date: formatDate(r.date),
    value: r.value,
    status: r.status
  }));

  return (
    <div className="chart-container">
      <h3>HbA1c Trends</h3>
      <LineChart width={600} height={300} data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={[4, 8]} />
        <Tooltip />
        <Legend />
        <Line 
          type="monotone" 
          dataKey="value" 
          stroke="#8884d8" 
          strokeWidth={2}
          dot={{ r: 5 }}
        />
        {/* Reference lines */}
        <ReferenceLine y={5.7} stroke="green" strokeDasharray="3 3" label="Normal" />
        <ReferenceLine y={6.5} stroke="red" strokeDasharray="3 3" label="Diabetic" />
      </LineChart>
    </div>
  );
};

const GlucoseChart = ({ readings }) => {
  const data = readings.map(r => ({
    date: formatDate(r.date),
    value: r.value,
    status: r.status
  }));

  return (
    <div className="chart-container">
      <h3>Fasting Glucose Trends</h3>
      <LineChart width={600} height={300} data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={[70, 150]} />
        <Tooltip />
        <Legend />
        <Line 
          type="monotone" 
          dataKey="value" 
          stroke="#82ca9d" 
          strokeWidth={2}
          dot={{ r: 5 }}
        />
        <ReferenceLine y={100} stroke="green" strokeDasharray="3 3" label="Normal" />
        <ReferenceLine y={126} stroke="red" strokeDasharray="3 3" label="Diabetic" />
      </LineChart>
    </div>
  );
};

const BMIChart = ({ readings }) => {
  const data = readings.map(r => ({
    date: formatDate(r.date),
    value: r.value,
    category: r.category
  }));

  return (
    <div className="chart-container">
      <h3>BMI History</h3>
      <LineChart width={600} height={300} data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={[15, 40]} />
        <Tooltip />
        <Legend />
        <Line 
          type="monotone" 
          dataKey="value" 
          stroke="#ffc658" 
          strokeWidth={2}
          dot={{ r: 5 }}
        />
        <ReferenceLine y={18.5} stroke="blue" strokeDasharray="3 3" label="Underweight" />
        <ReferenceLine y={25} stroke="green" strokeDasharray="3 3" label="Normal" />
        <ReferenceLine y={30} stroke="orange" strokeDasharray="3 3" label="Overweight" />
      </LineChart>
    </div>
  );
};
```

### **Displaying Risk Factors**

```typescript
const RiskFactorsList = ({ riskFactors }) => {
  const severityConfig = {
    high: { color: 'red', icon: 'alert-circle' },
    medium: { color: 'yellow', icon: 'alert-triangle' },
    low: { color: 'blue', icon: 'info' },
  };

  return (
    <div className="risk-factors">
      <h3>Risk Factors</h3>
      {riskFactors.length === 0 ? (
        <p className="empty-state">No risk factors identified</p>
      ) : (
        <ul>
          {riskFactors.map((risk, index) => {
            const config = severityConfig[risk.severity];
            return (
              <li key={index} className={`severity-${risk.severity}`}>
                <Icon name={config.icon} color={config.color} />
                <div>
                  <strong>{risk.factor}</strong>
                  <p>{risk.description}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
```

### **Displaying Recommendations**

```typescript
const RecommendationsList = ({ recommendations }) => {
  return (
    <div className="recommendations">
      <h3>Recommendations</h3>
      <ul>
        {recommendations.map((rec, index) => (
          <li key={index}>
            <Icon name="check-circle" color="green" />
            {rec}
          </li>
        ))}
      </ul>
    </div>
  );
};
```

### **Complete Dashboard Component**

```typescript
const DiabetesDashboardView = ({ dashboard }) => {
  return (
    <div className="diabetes-dashboard">
      {/* Header with Status */}
      <header>
        <h1>Diabetes Dashboard</h1>
        <StatusBadge status={dashboard.diabetes_status} />
      </header>

      {/* Summary Cards */}
      <div className="summary-cards">
        <SummaryCard 
          title="Total Analyses"
          value={dashboard.total_analyses}
          icon="file-text"
        />
        <SummaryCard 
          title="Diabetic Predictions"
          value={dashboard.diabetic_predictions_count}
          icon="alert-circle"
        />
        <SummaryCard 
          title="Average Confidence"
          value={dashboard.average_confidence 
            ? `${(dashboard.average_confidence * 100).toFixed(1)}%`
            : 'N/A'}
          icon="trending-up"
        />
      </div>

      {/* Latest Prediction */}
      {dashboard.latest_prediction && (
        <section className="latest-prediction">
          <h2>Latest Analysis</h2>
          <PredictionCard prediction={dashboard.latest_prediction} />
        </section>
      )}

      {/* Trends Charts */}
      <section className="trends">
        <h2>Health Trends</h2>
        <div className="charts-grid">
          {dashboard.trends.hba1c_readings.length > 0 && (
            <HbA1cChart readings={dashboard.trends.hba1c_readings} />
          )}
          {dashboard.trends.fasting_glucose.length > 0 && (
            <GlucoseChart readings={dashboard.trends.fasting_glucose} />
          )}
          {dashboard.trends.bmi_history.length > 0 && (
            <BMIChart readings={dashboard.trends.bmi_history} />
          )}
        </div>
      </section>

      {/* Risk Factors */}
      <section className="risk-section">
        <RiskFactorsList riskFactors={dashboard.risk_factors} />
      </section>

      {/* Recommendations */}
      <section className="recommendations-section">
        <RecommendationsList recommendations={dashboard.recommendations} />
      </section>

      {/* Prediction History */}
      {dashboard.prediction_history.length > 0 && (
        <section className="history">
          <h2>Analysis History</h2>
          <PredictionHistory predictions={dashboard.prediction_history} />
        </section>
      )}
    </div>
  );
};
```

---

## 5. Common Use Cases

### **Patient Self-Monitoring**
1. Patient logs into their account
2. Navigates to diabetes dashboard
3. Views current diabetes status
4. Reviews trends in HbA1c, glucose, and BMI
5. Reads personalized recommendations
6. Uploads new lab reports for continued monitoring

### **Doctor Patient Review**
1. Doctor selects patient from their assigned patients list
2. Views patient's diabetes dashboard
3. Reviews prediction history and confidence scores
4. Analyzes trends to identify patterns
5. Uses risk factors to guide treatment decisions
6. Discusses recommendations with patient during consultation

### **Progress Tracking**
1. Patient uploads regular lab reports (monthly/quarterly)
2. AI analyzes each report and updates predictions
3. Dashboard automatically updates with new data
4. Trends show improvement or deterioration over time
5. Risk factors are recalculated based on latest data
6. Recommendations adapt to current status

### **Early Detection**
1. Patient without diabetes uploads routine health checkup
2. AI predicts pre-diabetic risk
3. Dashboard becomes accessible with "at-risk" status
4. Patient receives recommendations for prevention
5. Regular monitoring helps prevent progression to diabetes

---

## 6. Data Extraction & Processing

### **Sources of Diabetes Data**

#### **From AI Predictions (MongoDB `report_analysis`)**
```json
{
  "_id": "65a1b2c3d4e5f6789abcdef0",
  "patient_id": "patient-uuid-123",
  "report_id": "report-uuid-456",
  "prediction": {
    "label": "diabetes",
    "confidence": 0.85
  },
  "extracted_features": {
    "HbA1c_level": 6.8,
    "blood_glucose_level": 132,
    "bmi": 28.5,
    "age": 45,
    "gender": "Male"
  },
  "created_at": "2026-01-20T15:30:00Z"
}
```

#### **From Report Extractions (MongoDB `report_analysis`)**
```json
{
  "_id": "65a1b2c3d4e5f6789abcdef1",
  "patient_id": "patient-uuid-123",
  "report_id": "report-uuid-789",
  "extracted_data": {
    "report_type": "Lab Report",
    "lab_results": [
      {
        "test_name": "HbA1c",
        "value": "5.4%",
        "reference_range": "4.0-5.6%",
        "status": "Normal"
      },
      {
        "test_name": "Fasting Blood Sugar",
        "value": "98 mg/dL",
        "reference_range": "70-100 mg/dL",
        "status": "Normal"
      }
    ],
    "vital_signs": {
      "bmi": "24.5",
      "weight": "70 kg",
      "height": "168 cm"
    }
  },
  "created_at": "2026-01-20T14:00:00Z"
}
```

#### **From Medical History (PostgreSQL `users.patient_profile`)**
```python
patient_profile.medical_history = [
  "Type 2 Diabetes Mellitus",
  "Hypertension",
  "Hyperlipidemia"
]
```

### **Data Aggregation Logic**
1. **Check medical history** for diabetes keywords ("diabetes", "diabetic", "DM")
2. **Query MongoDB** for all analyses with predictions for patient
3. **Extract trends** from both `extracted_features` and `extracted_data`
4. **Deduplicate readings** by date and value
5. **Calculate risk factors** based on latest values
6. **Generate recommendations** based on diabetes status
7. **Return structured response** with all aggregated data

---

## 7. Security & Access Control

| Role | View Own Dashboard | View Others' Dashboard | Data Shown |
|------|-------------------|------------------------|------------|
| **Patient** | ✅ | ❌ | All personal diabetes data |
| **Doctor** | ❌ | ✅ (assigned only) | Full diabetes data for assigned patients |
| **Admin** | ❌ | ❌ | Not implemented |

**Access Validation:**
- Patients can only access their own diabetes dashboard
- Doctors can only access dashboards for patients they're assigned to
- Assignment verification uses `is_patient_assigned_to_doctor()` function
- 403 error returned if access is denied

---

## 8. Clinical Reference Values

### **HbA1c (Glycated Hemoglobin)**
| Range | Status | Action |
|-------|--------|--------|
| < 5.7% | Normal | Maintain healthy lifestyle |
| 5.7% - 6.4% | Pre-diabetic | Lifestyle modifications, regular monitoring |
| ≥ 6.5% | Diabetic | Medical intervention, medication, close monitoring |

### **Fasting Blood Glucose**
| Range (mg/dL) | Status | Action |
|---------------|--------|--------|
| < 100 | Normal | Continue healthy habits |
| 100 - 125 | Pre-diabetic | Diet changes, exercise, monitoring |
| ≥ 126 | Diabetic | Medical treatment required |

### **BMI (Body Mass Index)**
| Range | Category | Diabetes Risk |
|-------|----------|---------------|
| < 18.5 | Underweight | Low |
| 18.5 - 24.9 | Normal | Low |
| 25.0 - 29.9 | Overweight | Moderate |
| ≥ 30.0 | Obese | High |

---

## 9. Recommendations Logic

### **For Diabetic Patients**
```python
recommendations = [
    "Monitor blood glucose levels daily",
    "Follow your prescribed medication regimen",
    "Maintain a balanced diet low in refined sugars",
    "Exercise regularly - aim for 30 minutes of moderate activity daily",
    "Schedule regular check-ups with your healthcare provider",
    "Get HbA1c tested every 3 months"
]
```

### **For At-Risk or Monitoring Patients**
```python
recommendations = [
    "Monitor blood glucose levels regularly",
    "Maintain a healthy weight through diet and exercise",
    "Limit intake of processed foods and sugars",
    "Stay physically active - 150 minutes of exercise per week",
    "Get HbA1c tested every 6 months",
    "Upload new reports regularly for AI monitoring"
]
```

### **For Patients with No Data**
```python
recommendations = [
    "Upload medical reports for diabetes screening",
    "Maintain a healthy lifestyle",
    "Get regular health check-ups"
]
```

---

## 10. Error Handling

### **Common Errors**

| Error | Status Code | Cause | Solution |
|-------|-------------|-------|----------|
| Unauthorized | 401 | Not authenticated | Login required |
| Forbidden (Patient) | 403 | Doctor accessing own dashboard | Use patient endpoint |
| Forbidden (Doctor) | 403 | Patient not assigned | Verify assignment |
| Forbidden (Doctor) | 403 | Non-doctor accessing doctor endpoint | Check user role |
| Not Found | 404 | Patient ID doesn't exist | Verify patient ID |

### **Frontend Error Handling**

```typescript
const fetchDiabetesDashboard = async (patientId?: string) => {
  try {
    const endpoint = patientId 
      ? `/patient/${patientId}/diabetes-dashboard`
      : '/patient/diabetes-dashboard';
    
    const response = await api.get(endpoint);
    return response;
  } catch (error) {
    if (error.status === 401) {
      // Redirect to login
      navigate('/login');
    } else if (error.status === 403) {
      // Show access denied message
      showError('You do not have permission to view this dashboard');
    } else if (error.status === 404) {
      // Patient not found
      showError('Patient not found');
    } else {
      // General error
      showError('Failed to load diabetes dashboard');
    }
    throw error;
  }
};
```

---

## 11. Performance Considerations

### **Query Optimization**
- Limit trend data to most recent 20 readings per metric
- Use MongoDB indexes on `patient_id` and `created_at`
- Cache dashboard data on frontend for 5-10 minutes
- Lazy load prediction history if list is long

### **Data Volume**
- Dashboard aggregates up to 100 analyses per patient
- Trend charts limited to 20 data points each
- Risk factors calculated only from latest readings
- Recommendations are static lists (no heavy computation)

### **Caching Strategy**
```typescript
// Example frontend caching
const useDiabetesDashboard = (patientId?: string) => {
  const queryKey = patientId 
    ? ['diabetes-dashboard', patientId]
    : ['diabetes-dashboard', 'me'];
  
  return useQuery(queryKey, () => fetchDiabetesDashboard(patientId), {
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
  });
};
```

---

## 12. Future Enhancements

### **Potential Features**
- **Export Reports**: PDF export of diabetes dashboard
- **Goal Setting**: Allow patients to set target values for HbA1c, glucose, BMI
- **Medication Tracking**: Track diabetes medications and dosages
- **Alerts**: Automatic alerts when values exceed thresholds
- **Comparison Views**: Compare metrics with healthy population averages
- **Doctor Notes**: Allow doctors to add notes visible on dashboard
- **Family History**: Include family diabetes history in risk calculation
- **Diet & Exercise Logs**: Integrate lifestyle tracking

### **Analytics Ideas**
- Correlation analysis between BMI changes and glucose levels
- Prediction accuracy tracking over time
- Seasonal patterns in glucose readings
- Medication effectiveness analysis

---

## 13. Integration with Other Modules

### **Reports Module**
- Dashboard links to source reports via `report_id`
- Clicking on a reading can open the original report
- Activity logging tracks dashboard views

### **AI Module**
- Dashboard displays results from `/ai/analyze-report` endpoint
- Uses extraction data from `/ai/extract-report` endpoint
- Predictions from diabetes XGBoost model

### **Cases Module**
- Can link diabetes dashboard to specific cases
- Track diabetes progression within case timeline

### **Notifications Module**
- Notify patient when new prediction is available
- Alert doctor if patient's status changes to "diabetic"
- Remind patient to upload reports for monitoring

---

## 14. Testing Checklist

### **Access Control Tests**
- ✅ Patient can access own dashboard
- ✅ Patient cannot access other patients' dashboards
- ✅ Doctor can access assigned patients' dashboards
- ✅ Doctor cannot access unassigned patients' dashboards
- ✅ Non-authenticated users receive 401

### **Data Accuracy Tests**
- ✅ Correct diabetes status classification
- ✅ Predictions sorted by date (newest first)
- ✅ Trends deduplicated and sorted correctly
- ✅ Risk factors calculated from latest values
- ✅ Recommendations match diabetes status

### **Edge Cases**
- ✅ Empty state when no diabetes data
- ✅ Patient with predictions but no trends
- ✅ Patient with trends but no predictions
- ✅ Patient with diabetes in history only
- ✅ Multiple analyses on same date
- ✅ Missing or invalid extracted data

---

## 15. API Summary

| Endpoint | Method | Auth | Access | Purpose |
|----------|--------|------|--------|---------|
| `/patient/diabetes-dashboard` | GET | Required | Patient | Get own diabetes dashboard |
| `/patient/{patient_id}/diabetes-dashboard` | GET | Required | Doctor | Get assigned patient's diabetes dashboard |

**Response Format**: JSON (DiabetesDashboardResponse)  
**Rate Limiting**: Standard API rate limits apply  
**Caching**: Recommended 5-10 minutes client-side cache
