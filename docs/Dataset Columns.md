# CRIP Dataset Columns & Calculations Guide

This document explains the columns present in the original dataset and all the calculated features added during the pipeline processes (Data Governance, Pricing, Risk Intelligence, and Stress Testing).

## 1. Initial/Current Dataset (Raw Data)
These are the standard columns expected in the initial uploaded dataset before processing:

| Column Name | Description |
|---|---|
| `Policy_ID` | Unique identifier for the insurance policy. |
| `Product` / `Product_Type` | The type of insurance product (e.g., Auto, Home, Commercial). |
| `Written_Premium` | Total premium collected for the policy. |
| `Claim_Amount` | Total monetary value of claims filed. |
| `Total_Expense` | Operational expenses associated with the policy. |
| `Sum_Insured` | Total coverage amount for the policy. |
| `Policy_Tenure_Months` | How long the policy has been active. |
| `Underwriting_Exception_Flag` | Flag (0 or 1) indicating if the policy had an underwriting exception. |
| `Claim_Exception_Flag` | Flag (0 or 1) indicating if there was an exception during the claim process. |
| `Date` | Date of policy inception or record. |

---

## 2. Data Governance & Anomaly Additions
Calculated during the data cleaning and governance phase (`data_governance.py`):

| Column Name | Calculation / Description |
|---|---|
| `Calculated_Fraud_Score` | (0-100) Points are added if `Claim_Frequency` > threshold (+20), `Underwriting_Exception_Flag` == 1 (+25), `Claim_Exception_Flag` == 1 (+25), or if `Claim_Amount` is high while `Policy_Tenure_Months` is low (+30). |

---

## 3. Pricing & Profitability Additions
Calculated during the pricing phase (`pricing.py`):

| Column Name | Calculation / Description |
|---|---|
| `Loss_Ratio` | `Claim_Amount` / `Written_Premium` |
| `Expense_Ratio` | `Total_Expense` / `Written_Premium` |
| `Combined_Ratio` | `Loss_Ratio` + `Expense_Ratio` |
| `Underwriting_Profit` | `Written_Premium` - `Claim_Amount` - `Total_Expense` |
| `Profitability_Tier` | Categorical classification based on `Combined_Ratio`: **Excellent** (<0.80), **Good** (<0.95), **Marginal** (0.95 - 1.0), **Loss-Making** (>1.0). |
| `Profitability_Color` | Hex code assigned based on the tier for UI visualization. |

---

## 4. Risk Intelligence & Actuarial Formulas
Calculated in the risk pipeline (`risk_intelligence.py`). *Note: If source data is missing variables like `Claim_Count`, `Exposure_At_Risk`, `Interest_Rate`, or `Market_Volatility_Index`, they are simulated randomly to allow calculations to proceed.*

| Column Name | Calculation / Description |
|---|---|
| `Claim_Frequency` | `Claim_Count` / `Exposure_At_Risk` |
| `Claim_Severity` | `Claim_Amount` / `Claim_Count` |
| `Insurance_Risk` | Weighted sum of normalized `Loss_Ratio`, `Claim_Frequency`, and `Claim_Severity` (scaled 1-10). |
| `Credit_Risk` | Weighted sum of normalized `Premium_Outstanding` and `Days_Past_Due` (scaled 1-10). |
| `Market_Risk` | Weighted sum of normalized `Interest_Rate`, `Market_Volatility_Index`, and `Inflation_Rate` (scaled 1-10). |
| `Operational_Risk` | Weighted sum of normalized `Fraud_Score`, `Exception_Count`, `Processing_Delay_Days`, and inverted `Data_Quality_Score` (scaled 1-10). |
| `Hazard_Score` | (Catastrophe Risk) Weighted sum of state, flood, cyclone, and earthquake zone scores plus coastal flag. |
| `CAT_Risk_Exposure` | `Exposure_At_Risk` * (`Hazard_Score` / 10). |

---

## 5. Machine Learning & Predictive Additions (Risk Intelligence)
Generated via XGBoost Models inside the risk pipeline:

| Column Name | Calculation / Description |
|---|---|
| `Expected_Claim_Amount_ML` | Predicted future claim amount based on tenure, risks, and premiums (using XGBRegressor). |
| `Expected_Loss_Ratio_ML` | `Expected_Claim_Amount_ML` / `Written_Premium` |
| `High_Risk_Prob` | Probability (0.0 - 1.0) that the policy will become Loss-Making (`Loss_Ratio` > 1.0) via XGBClassifier. |

---

## 6. Monte Carlo, Stress Testing, & Governance Validations
Calculated via Monte Carlo simulations and statistical validation checks:

| Column Name | Calculation / Description |
|---|---|
| `VaR (99%)` | Value at Risk. The 99th percentile of simulated portfolio losses across thousands of iterations. |
| `Expected Shortfall` | Average of all simulated portfolio losses that exceed the `VaR (99%)`. |
| `Capital Adequacy` | `Total_Capital` / `VaR (99%)` |
| `Solvency Ratio` | `Capital Adequacy` * 100 (percentage) |
| `AUC` | ROC AUC Score of the XGBClassifier model predicting high risk. |
| `Brier Score` | Brier Score Loss measuring probability calibration. |
| `KS Statistic` | Kolmogorov-Smirnov Statistic (measures model discrimination). |
| `PSI` | Population Stability Index (measures data drift). |
| `Model Governance & Validation Standards` | Categorical output ("Pass", "Monitor", or "Fail") based on thresholds for PSI (e.g. < 0.1) and AUC (e.g. > 0.70). |
