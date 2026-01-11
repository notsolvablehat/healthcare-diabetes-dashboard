import pandas as pd
import xgboost as xgb

# Load model
model_path = "src/ml_model/diabetes_xgboost_model.json"

loaded_xgb_model = xgb.XGBClassifier()
loaded_xgb_model.load_model(model_path)

print(f"XGBoost Model loaded from {model_path}")

# Sample diabetic input
sample_input_xgb = {
    "gender": 1,                # Male
    "age": 56.0,
    "hypertension": 1,
    "heart_disease": 0,
    "smoking_history": 2,       # Former smoker
    "bmi": 31.4,
    "HbA1c_level": 7.8,
    "blood_glucose_level": 198
}

# Convert to DataFrame (REQUIRED)
X_sample = pd.DataFrame([sample_input_xgb])

# Predict
prediction = loaded_xgb_model.predict(X_sample)
probability = loaded_xgb_model.predict_proba(X_sample)

print("Prediction:", prediction[0])                 # 0 or 1
print("Diabetes probability:", probability[0][1])   # confidence
