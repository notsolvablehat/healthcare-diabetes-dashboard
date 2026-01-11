"""
XGBoost Diabetes Prediction Model wrapper.
"""
import pandas as pd
import xgboost as xgb

from src.ai.models import ExtractedFeatures, PredictionResult


class DiabetesPredictor:
    """
    Wrapper for the pre-trained XGBoost diabetes classification model.
    The model predicts diabetes likelihood based on 8 features:
    - gender (encoded: 0=Female, 1=Male, 2=Other)
    - age (float, years)
    - hypertension (0/1)
    - heart_disease (0/1)
    - smoking_history (encoded: 0-4)
    - bmi (float, kg/m²)
    - HbA1c_level (float, %)
    - blood_glucose_level (int, mg/dL)
    """

    MODEL_PATH = "src/ml_model/diabetes_xgboost_model.json"
    FEATURE_ORDER = [
        "gender",
        "age",
        "hypertension",
        "heart_disease",
        "smoking_history",
        "bmi",
        "HbA1c_level",
        "blood_glucose_level",
    ]

    def __init__(self):
        self.model = xgb.XGBClassifier()
        self.model.load_model(self.MODEL_PATH)

    def predict(self, features: ExtractedFeatures) -> PredictionResult:
        """
        Run diabetes prediction on extracted features.
        Args:
            features: ExtractedFeatures object with 8 required features
        Returns:
            PredictionResult with label and confidence
        """
        # Create feature dict in correct order
        feature_dict = {
            "gender": features.gender,
            "age": features.age,
            "hypertension": features.hypertension,
            "heart_disease": features.heart_disease,
            "smoking_history": features.smoking_history,
            "bmi": features.bmi,
            "HbA1c_level": features.HbA1c_level,
            "blood_glucose_level": features.blood_glucose_level,
        }

        # Convert to DataFrame (required by XGBoost)
        df = pd.DataFrame([feature_dict], columns=self.FEATURE_ORDER)

        # Get prediction and probability
        prediction = self.model.predict(df)[0]
        probabilities = self.model.predict_proba(df)[0]

        # Map prediction to label
        label = "diabetes" if prediction == 1 else "no_diabetes"
        confidence = float(probabilities[1]) if prediction == 1 else float(probabilities[0])

        return PredictionResult(
            label=label,
            confidence=round(confidence, 4)
        )


# Singleton instance
diabetes_predictor = DiabetesPredictor()
