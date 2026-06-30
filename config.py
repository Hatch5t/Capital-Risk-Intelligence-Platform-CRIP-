# ==========================================
# CRIP - GLOBAL CONFIGURATION
# ==========================================
import os

CONFIG_FILE_PATH = os.path.abspath(__file__)

# Use this file to tweak hyperparameters, weights, and thresholds
# without modifying the underlying agent logic.

# ------------------------------------------
# AGENT 1: DATA GOVERNANCE
# ------------------------------------------
GOVERNANCE = {
    # Strings that should be interpreted as missing values
    "MISSING_STRINGS": ['unknown', 'NA', 'null', 'Null', 'NULL', '?', '??', '???', ' ', '', 'N/A', 'n/a'],
    # Drop columns if the percentage of missing values exceeds this threshold
    "MISSING_DROP_THRESHOLD": 0.80,
    # Drop columns if the ratio of unique values to total rows exceeds this threshold
    "UNIQUE_DROP_THRESHOLD": 0.90,
    # Multiplier for IQR to determine outlier bounds (Q1 - mult*IQR, Q3 + mult*IQR)
    "IQR_MULTIPLIER": 1.5,
    # Contamination parameter for Isolation Forest anomaly detection
    "IFOREST_CONTAMINATION": 0.05,
    # Percentiles used for fraud scoring
    "FRAUD_CLAIM_FREQ_PCTILE": 0.9,
    "FRAUD_HIGH_CLAIM_PCTILE": 0.8,
    "FRAUD_SHORT_TENURE_MONTHS": 12,
}

# ------------------------------------------
# AGENT 2: PRICING
# ------------------------------------------
PRICING = {
    # Thresholds for categorizing the Combined Ratio
    "PROFITABILITY_THRESHOLDS": {
        "EXCELLENT": 0.80,
        "GOOD": 0.95,
        "MARGINAL": 1.00
        # Anything above MARGINAL is considered Loss-Making
    }
}

# ------------------------------------------
# AGENT 3: RISK INTELLIGENCE
# ------------------------------------------
RISK = {
    # Weights for the Insurance Risk composite score
    "INSURANCE_WEIGHTS": {
        "Loss_Ratio": 0.4,
        "Claim_Frequency": 0.3,
        "Claim_Severity": 0.3
    },
    # Weights for the Credit Risk composite score
    "CREDIT_WEIGHTS": {
        "Premium_Outstanding": 0.6,
        "Days_Past_Due": 0.4
    },
    # Weights for the Market Risk composite score
    "MARKET_WEIGHTS": {
        "Interest_Rate": 0.4,
        "Market_Volatility_Index": 0.3,
        "Inflation_Rate": 0.3
    },
    # Weights for the Operational Risk composite score
    "OPERATIONAL_WEIGHTS": {
        "Fraud_Score": 0.35,
        "Exception_Count": 0.25,
        "Processing_Delay_Days": 0.20,
        "Data_Quality_Score": 0.20
    },
    # Weights for the CAT Risk composite score
    "CAT_WEIGHTS": {
        "State_Hazard": 0.30,
        "Flood_Zone": 0.20,
        "Cyclone_Zone": 0.20,
        "Earthquake_Zone": 0.20,
        "Coastal_Flag": 0.10
    },
    
    # XGBoost Parameters for the Claim Amount Regressor
    "XGB_REG_PARAMS": {
        "n_estimators": 100,
        "max_depth": 4,
        "learning_rate": 0.1,
        "random_state": 42
    },
    
    # XGBoost Parameters for the High Risk Classifier
    "XGB_CLF_PARAMS": {
        "n_estimators": 100,
        "max_depth": 3,
        "random_state": 42,
        "use_label_encoder": False,
        "eval_metric": 'logloss'
    },
    
    # Capital Adequacy Parameters
    "NUM_MONTE_CARLO_SIMULATIONS": 1000,
    "CAPITAL_MULTIPLIER": 1.5  # Total Capital = Total Written Premium * Multiplier
}

# ------------------------------------------
# AGENT 4: FORECASTING
# ------------------------------------------
FORECASTING = {
    # Default Product weights (can be overridden if dataset provides them)
    "PRODUCT_WEIGHTS": {
        "Motor": 0.30, 
        "Health": 0.25, 
        "Property": 0.20,
        "Travel": 0.10, 
        "Fire": 0.08, 
        "Marine": 0.07,
    },
    # Hyperparameters for the Prophet Model
    "PROPHET_PARAMS": {
        "yearly_seasonality": True,
        "weekly_seasonality": False,
        "daily_seasonality": False,
        "changepoint_prior_scale": 0.1,
        "interval_width": 0.80,
    },
    # Multiplier for Confidence Intervals in the Linear Fallback model
    "LINEAR_CI_MULT": 1.28  # 1.28 = 80% CI
}

# ------------------------------------------
# AGENT 5: STRESS TESTING
# ------------------------------------------
STRESS_TESTING = {
    # Definitions for each stress testing scenario
    "SCENARIO_CONFIG": {
        "s1": {"label": "Scenario 1 — Claims +20%",        "claim_mult": 1.20, "mkt_mult": 1.00, "cat_mult": 1.00},
        "s2": {"label": "Scenario 2 — Claims +40%",        "claim_mult": 1.40, "mkt_mult": 1.00, "cat_mult": 1.00},
        "s3": {"label": "Scenario 3 — Market Risk +25%",   "claim_mult": 1.00, "mkt_mult": 1.25, "cat_mult": 1.00},
        "s4": {"label": "Scenario 4 — Combined Shock",     "claim_mult": 1.40, "mkt_mult": 1.25, "cat_mult": 1.00},
        "s5": {"label": "Scenario 5 — Catastrophic Event", "claim_mult": 1.60, "mkt_mult": 1.30, "cat_mult": 1.50},
    },
    # Weights used to distribute stress impact across products
    "PRODUCT_WEIGHTS": {
        "Motor": 0.30, 
        "Health": 0.25, 
        "Property": 0.20,
        "Travel": 0.10, 
        "Fire": 0.08, 
        "Marine": 0.07,
    }
}
