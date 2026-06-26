import pandas as pd
import numpy as np
import config

def classify_ratio(x):
    if pd.isna(x):
        return "Unknown"
    if x < config.PRICING['PROFITABILITY_THRESHOLDS']['EXCELLENT']:
        return "Excellent"
    elif x < config.PRICING['PROFITABILITY_THRESHOLDS']['GOOD']:
        return "Good"
    elif x <= config.PRICING['PROFITABILITY_THRESHOLDS']['MARGINAL']:
        return "Marginal"
    else:
        return "Loss-Making"

def run_pricing_pipeline(df):
    """Calculates pricing metrics and returns insights."""
    df_pricing = df.copy()
    
    # 1. Convert Date
    if "Date" in df_pricing.columns:
        df_pricing["Date"] = pd.to_datetime(df_pricing["Date"], errors="coerce")

    # 2. Numeric Conversion
    numeric_cols = ["Written_Premium", "Claim_Amount", "Total_Expense"]
    for col in numeric_cols:
        if col in df_pricing.columns:
            df_pricing[col] = pd.to_numeric(df_pricing[col], errors="coerce")

    # 3. Handle Missing/Zero Premium
    if "Written_Premium" in df_pricing.columns:
        df_pricing = df_pricing.dropna(subset=["Written_Premium"])
        premium_safe = df_pricing["Written_Premium"].replace(0, np.nan)
    else:
        premium_safe = np.nan

    
    # 4. Metrics
    if "Claim_Amount" in df_pricing.columns:
        df_pricing["Loss_Ratio"] = df_pricing["Claim_Amount"] / premium_safe
    else:
        df_pricing["Loss_Ratio"] = np.nan
        
    if "Total_Expense" in df_pricing.columns:
        df_pricing["Expense_Ratio"] = df_pricing["Total_Expense"] / premium_safe
    else:
        df_pricing["Expense_Ratio"] = np.nan
        
    df_pricing["Combined_Ratio"] = df_pricing["Loss_Ratio"] + df_pricing["Expense_Ratio"]

    # Absolute Profit Calculation
    if "Claim_Amount" in df_pricing.columns and "Total_Expense" in df_pricing.columns:
        df_pricing["Underwriting_Profit"] = df_pricing["Written_Premium"] - df_pricing["Claim_Amount"] - df_pricing["Total_Expense"]
    else:
        df_pricing["Underwriting_Profit"] = np.nan

    # 5. Profitability Classification
    df_pricing["Profitability_Tier"] = df_pricing["Combined_Ratio"].apply(classify_ratio)
    
    # KPIs
    kpis = {
        "Total_Premium": df_pricing['Written_Premium'].sum() if 'Written_Premium' in df_pricing.columns else 0,
        "Total_Claims": df_pricing['Claim_Amount'].sum() if 'Claim_Amount' in df_pricing.columns else 0,
        "Total_Expenses": df_pricing['Total_Expense'].sum() if 'Total_Expense' in df_pricing.columns else 0,
        "Underwriting_Profit": df_pricing['Underwriting_Profit'].sum() if 'Underwriting_Profit' in df_pricing.columns else 0,
    }
    
    return {
        "df_pricing": df_pricing,
        "kpis": kpis
    }
