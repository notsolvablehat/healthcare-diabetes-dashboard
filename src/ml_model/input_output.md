## Input and Output Specification for the XGBoost Diabetes Model

### Expected Input

The model expects a **2D tabular input** containing **exactly 8 features**, provided as a **Pandas DataFrame or NumPy array** with **one row per patient**.

* Shape:

  ```
  (n_samples, 8)
  ```
* Feature **order, names, and data types must exactly match** those used during training.

### Feature Schema (in required order)

1. **gender**

   * Type: `int`
   * Encoding:

     * `0` → Female
     * `1` → Male
     * `2` → Other
   * Must use the **same LabelEncoder** as training.

2. **age**

   * Type: `float`
   * Units: years

3. **hypertension**

   * Type: `int`
   * Values:

     * `0` → No
     * `1` → Yes

4. **heart_disease**

   * Type: `int`
   * Values:

     * `0` → No
     * `1` → Yes

5. **smoking_history**

   * Type: `int`
   * Encoding: `0–4`
   * Must use the **same LabelEncoder** as training.

6. **bmi**

   * Type: `float`
   * Units: kg/m²

7. **HbA1c_level**

   * Type: `float`
   * Units: percentage (%)

8. **blood_glucose_level**

   * Type: `int`
   * Units: mg/dL

### Preprocessing Requirements

* All categorical features (**gender**, **smoking_history**) must be encoded using the **same encoders used during model training**.
* Feature scaling is **not required**.
* Missing values may be provided as `NaN`; the model handles them internally.
* Input must be wrapped as a **DataFrame or 2D array**. A flat list is invalid.

---

### Expected Output

The model produces **two outputs**:

1. **Binary prediction**

   * Type: `numpy.ndarray`
   * Shape:

     ```
     (n_samples,)
     ```
   * Values:

     * `0` → No diabetes detected
     * `1` → Diabetes detected

2. **Prediction probability**

   * Obtained via `predict_proba`
   * Type: `numpy.ndarray`
   * Shape:

     ```
     (n_samples, 2)
     ```
   * Interpretation:

     * `[:, 0]` → Probability of **no diabetes**
     * `[:, 1]` → Probability of **diabetes**

### Example Output

```python
Prediction: [1]
Diabetes probability: 0.92
```

This indicates a **high likelihood of diabetes** for the input sample.

---

### Important Notes

* The model predicts **likelihood**, not a medical diagnosis.
* Predictions with probabilities near **0.5** should be treated as **inconclusive**.
* Feature order mismatches or incorrect encodings will produce **invalid predictions** without necessarily raising errors.
