import pandas as pd
import numpy as np
import os
from sklearn.ensemble import IsolationForest
import config

def load_data(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Please use CSV or Excel.")
    return df

def get_data_summary(df):
    return {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'columns': df.columns.tolist()
    }

def check_missing_values(df):
    missing = df.isnull().sum()
    missing_pct = (missing / len(df)) * 100
    missing_df = pd.DataFrame({'Missing Count': missing, 'Missing %': missing_pct})
    return missing_df[missing_df['Missing Count'] > 0].sort_values(by='Missing Count', ascending=False)

def check_duplicates(df, subset=None):
    duplicates = df[df.duplicated(subset=subset, keep=False)]
    return len(duplicates), duplicates

def clean_data(df):
    df_clean = df.copy()
    
    if 'Product_Type' in df_clean.columns:
        df_clean['Product_Type'] = df_clean['Product_Type'].replace(['unnown', 'Unknown', 'unknown', 'UNKNOWN'], 'Miscellaneous')
        
    missing_strings = config.GOVERNANCE['MISSING_STRINGS']
    df_clean.replace(missing_strings, np.nan, inplace=True)
    
    # Critical Fix: convert financial columns to numeric BEFORE drop logic
    for c in ['Written_Premium', 'Claim_Amount', 'Total_Expense']:
        if c in df_clean.columns:
            df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce')
            
    cols_to_drop = set(['Mystery_Risk_Factor', 'Legacy_System_Code'])
    for col in df_clean.columns:
        if df_clean[col].isnull().mean() > config.GOVERNANCE['MISSING_DROP_THRESHOLD']:
            cols_to_drop.add(col)
            continue
        if df_clean[col].nunique(dropna=True) <= 1:
            cols_to_drop.add(col)
            continue
        is_id_col = str(col).lower().endswith('id') or str(col).lower().endswith('_id')
        if not pd.api.types.is_numeric_dtype(df_clean[col]) and not is_id_col:
            if df_clean[col].count() > 0 and (df_clean[col].nunique(dropna=True) / df_clean[col].count()) > config.GOVERNANCE['UNIQUE_DROP_THRESHOLD']:
                cols_to_drop.add(col)
    
    df_clean.drop(columns=[col for col in cols_to_drop if col in df_clean.columns], inplace=True)
    
    df_clean.dropna(how='all', inplace=True)
    df_clean.dropna(axis=1, how='all', inplace=True)
    
    for col in df_clean.select_dtypes(include=['float64', 'int64']).columns:
        is_id_col = str(col).lower().endswith('id') or str(col).lower().endswith('_id')
        if not is_id_col and df_clean[col].count() > 0:
            Q1 = df_clean[col].quantile(0.25)
            Q3 = df_clean[col].quantile(0.75)
            IQR = Q3 - Q1
            mult = config.GOVERNANCE['IQR_MULTIPLIER']
            df_clean[col] = df_clean[col].clip(lower=Q1 - mult * IQR, upper=Q3 + mult * IQR)
            
    for col in df_clean.columns:
        if df_clean[col].isnull().sum() > 0:
            if pd.api.types.is_numeric_dtype(df_clean[col]):
                df_clean[col] = df_clean[col].fillna(df_clean[col].median())
            else:
                df_clean[col] = df_clean[col].fillna(df_clean[col].mode()[0])
                
    return df_clean

def detect_anomalies_isolation_forest(df, numerical_cols):
    df_subset = df[numerical_cols].fillna(df[numerical_cols].median())
    model = IsolationForest(contamination=config.GOVERNANCE['IFOREST_CONTAMINATION'], random_state=42)
    predictions = model.fit_predict(df_subset)
    anomaly_mask = predictions == -1
    return df[anomaly_mask]

def calculate_fraud_score(df):
    df_scored = df.copy()
    for col in ['Claim_Frequency', 'Claim_Amount', 'Policy_Tenure_Months', 'Underwriting_Exception_Flag', 'Claim_Exception_Flag']:
        if col in df_scored.columns:
            df_scored[col] = pd.to_numeric(df_scored[col], errors='coerce').fillna(0)
    df_scored['Calculated_Fraud_Score'] = 0
    
    if 'Claim_Frequency' in df.columns:
        df_scored.loc[df_scored['Claim_Frequency'] > df_scored['Claim_Frequency'].quantile(config.GOVERNANCE['FRAUD_CLAIM_FREQ_PCTILE']), 'Calculated_Fraud_Score'] += 20
    if 'Underwriting_Exception_Flag' in df.columns:
        df_scored.loc[df_scored['Underwriting_Exception_Flag'] == 1, 'Calculated_Fraud_Score'] += 25
    if 'Claim_Exception_Flag' in df.columns:
        df_scored.loc[df_scored['Claim_Exception_Flag'] == 1, 'Calculated_Fraud_Score'] += 25
    if 'Claim_Amount' in df.columns and 'Policy_Tenure_Months' in df.columns:
        high_claim = df_scored['Claim_Amount'] > df_scored['Claim_Amount'].quantile(config.GOVERNANCE['FRAUD_HIGH_CLAIM_PCTILE'])
        short_tenure = df_scored['Policy_Tenure_Months'] < config.GOVERNANCE['FRAUD_SHORT_TENURE_MONTHS']
        df_scored.loc[high_claim & short_tenure, 'Calculated_Fraud_Score'] += 30
        
    df_scored['Calculated_Fraud_Score'] = df_scored['Calculated_Fraud_Score'].clip(upper=100)
    return df_scored

def run_governance_pipeline(df_raw):
    """Orchestrates all governance steps and returns results."""
    summary = get_data_summary(df_raw)
    missing_df = check_missing_values(df_raw)
    num_dupes, duplicates = check_duplicates(df_raw)
    
    df_clean = clean_data(df_raw)
    
    num_cols = df_clean.select_dtypes(include=['float64', 'int64']).columns.tolist()
    num_cols = [col for col in num_cols if not (str(col).lower().endswith('id') or str(col).lower().endswith('_id'))]
    anomalies = detect_anomalies_isolation_forest(df_clean, num_cols)
    
    df_scored = calculate_fraud_score(df_clean)
    
    return {
        "summary": summary,
        "missing_df": missing_df,
        "duplicates_count": num_dupes,
        "df_clean": df_clean,
        "anomalies": anomalies,
        "df_scored": df_scored
    }
