"""
CRIP — Agent 4: Time Series Intelligence Agent
agents/forecasting.py

Drop this file into the agents/ folder.
The orchestrator imports it as:
    from agents.forecasting import run_forecasting_pipeline

Input:  df_pricing (DataFrame) — output of run_pricing_pipeline()
Output: dict matching the pattern of existing pipeline functions
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")
import config

# ── Column name mapping ────────────────────────────────────────────────────────
# Handles variations across different teammates' naming conventions
DATE_COLS    = ["Date", "date", "Policy_Date", "Inception_Date"]
PREMIUM_COLS = ["Written_Premium", "Premium", "written_premium"]
CLAIM_COLS   = ["Claim_Amount", "claim_amount", "Claims"]
COUNT_COLS   = ["Claim_Count", "claim_count", "Num_Claims"]
PRODUCT_COLS = ["Product_Type", "product_type", "Product"]
INFLATION_COLS = ["Inflation_Rate", "inflation_rate", "Inflation"]
SEGMENT_COLS   = ["Customer_Segment", "customer_segment", "Segment"]
CHANNEL_COLS   = ["Distribution_Channel", "distribution_channel", "Channel"]
ML_CLAIM_COLS  = ["Expected_Claim_Amount_ML", "expected_claim_amount_ml"]

PRODUCT_WEIGHTS = config.FORECASTING['PRODUCT_WEIGHTS']


def _find_col(df, candidates, default=None):
    for c in candidates:
        if c in df.columns:
            return c
    return default


def _prepare_df(df_pricing):
    """
    Standardise the pricing dataframe into the columns
    this agent needs. Handles missing columns gracefully.
    """
    df = df_pricing.copy()

    # Resolve date column
    date_col = _find_col(df, DATE_COLS)
    if date_col:
        df["_Date"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        # No date column — generate a synthetic monthly sequence
        df["_Date"] = pd.date_range(
            start="2023-01-01", periods=len(df), freq="D"
        )

    # Resolve financial columns
    prem_col  = _find_col(df, PREMIUM_COLS)
    claim_col = _find_col(df, CLAIM_COLS)
    count_col = _find_col(df, COUNT_COLS)
    prod_col  = _find_col(df, PRODUCT_COLS)
    inf_col   = _find_col(df, INFLATION_COLS)
    seg_col   = _find_col(df, SEGMENT_COLS)
    chan_col  = _find_col(df, CHANNEL_COLS)
    ml_col    = _find_col(df, ML_CLAIM_COLS)

    df["_Premium"]   = df[prem_col].fillna(0)  if prem_col  else 0.0
    df["_Claims"]    = df[claim_col].fillna(0) if claim_col else 0.0
    df["_Count"]     = df[count_col].fillna(0) if count_col else 1.0
    df["_Product"]   = df[prod_col]             if prod_col  else "Unknown"
    df["_Inflation"] = df[inf_col].fillna(0)    if inf_col   else 0.0
    df["_Segment"]   = df[seg_col]              if seg_col   else "Unknown"
    df["_Channel"]   = df[chan_col]             if chan_col  else "Unknown"
    df["_ML_Claim"]  = df[ml_col].fillna(0)     if ml_col    else 0.0

    return df


def _aggregate_monthly(df):
    """Group by calendar month and sum financials."""
    df["_Month"] = df["_Date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        df.groupby("_Month")
        .agg(
            Written_Premium=("_Premium", "sum"),
            Claim_Amount   =("_Claims",  "sum"),
            Claim_Count    =("_Count",   "sum"),
            Policy_Count   =("_Premium", "count"),
            Inflation_Rate =("_Inflation", "mean"),
            ML_Expected_Claims=("_ML_Claim", "sum"),
        )
        .reset_index()
        .rename(columns={"_Month": "Month"})
        .sort_values("Month")
        .reset_index(drop=True)
    )
    return monthly


def _seasonal_factors(monthly):
    """
    Monthly seasonal index relative to annual mean (100 = average month).
    Requires at least 12 months; falls back to flat 100 for shorter series.
    """
    df = monthly.copy()
    df["month_num"] = pd.to_datetime(df["Month"]).dt.month

    if len(df) < 12:
        return {m: 1.0 for m in range(1, 13)}

    avg_by_month = df.groupby("month_num")["Claim_Amount"].mean()
    overall_avg  = df["Claim_Amount"].mean()
    return (avg_by_month / overall_avg).to_dict() if overall_avg > 0 else {m: 1.0 for m in range(1, 13)}


def _linear_forecast(series, periods):
    """
    Fit a linear trend + monthly seasonal index.
    Returns arrays: (fitted, future_values, lower_80, upper_80).
    """
    n     = len(series)
    x     = np.arange(n)
    y     = series.values.astype(float)
    slope, intercept = np.polyfit(x, y, 1)
    std   = float(np.std(y - (intercept + slope * x)))

    # Seasonal factors from monthly data
    months_idx = np.arange(n) % 12
    monthly_avg = np.array([y[months_idx == m].mean() if any(months_idx == m) else y.mean()
                             for m in range(12)])
    overall_avg = y.mean() if y.mean() != 0 else 1
    sf_by_idx   = monthly_avg / overall_avg

    fitted = (intercept + slope * x) * sf_by_idx[x % 12]
    future_x = np.arange(n, n + periods)
    future_sf = sf_by_idx[future_x % 12]
    future    = (intercept + slope * future_x) * future_sf
    ci_mult   = config.FORECASTING['LINEAR_CI_MULT']  # 80% CI

    return (
        fitted,
        future,
        future - ci_mult * std * (1 + np.arange(periods) * 0.02),
        future + ci_mult * std * (1 + np.arange(periods) * 0.02),
    )


def _prophet_forecast(monthly, col, periods):
    """
    Try Prophet; fall back to linear model if not installed.
    Returns a unified DataFrame: ds, yhat, yhat_lower, yhat_upper.
    """
    df_ts = monthly[["Month", col]].copy()
    df_ts.columns = ["ds", "y"]
    df_ts["ds"]   = pd.to_datetime(df_ts["ds"])

    try:
        from prophet import Prophet
        m = Prophet(**config.FORECASTING['PROPHET_PARAMS'])
        
        has_inflation = "Inflation_Rate" in monthly.columns and monthly["Inflation_Rate"].sum() != 0
        if has_inflation:
            m.add_regressor('Inflation_Rate')
            df_ts['Inflation_Rate'] = monthly['Inflation_Rate']
            
        m.fit(df_ts)
        future   = m.make_future_dataframe(periods=periods, freq="MS")
        
        if has_inflation:
            # Merge historical inflation back in for accurate historical fit
            future = future.merge(df_ts[['ds', 'Inflation_Rate']], on='ds', how='left')
            # Fill future dates with last known inflation
            last_inflation = df_ts['Inflation_Rate'].iloc[-1]
            future['Inflation_Rate'] = future['Inflation_Rate'].fillna(last_inflation)
            
        forecast = m.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    except ImportError:
        pass  # Fall through to linear

    # Linear fallback
    fitted, future_vals, lower, upper = _linear_forecast(df_ts["y"], periods)
    last_date    = pd.to_datetime(df_ts["ds"].iloc[-1])
    future_dates = pd.date_range(last_date + pd.DateOffset(months=1), periods=periods, freq="MS")
    hist_rows = [{"ds": r["ds"], "yhat": f, "yhat_lower": f * 0.9, "yhat_upper": f * 1.1}
                 for r, f in zip(df_ts.to_dict("records"), fitted)]
    future_rows = [{"ds": d, "yhat": v, "yhat_lower": lo, "yhat_upper": hi}
                   for d, v, lo, hi in zip(future_dates, future_vals, lower, upper)]
    return pd.DataFrame(hist_rows + future_rows)


def _yoy_growth(monthly):
    """Year-over-year % change for premium and claims. Needs ≥13 months."""
    if len(monthly) < 13:
        return pd.DataFrame()
    df = monthly.set_index("Month")
    result = pd.DataFrame(index=df.index)
    for col, out in [("Written_Premium", "Premium_YoY"), ("Claim_Amount", "Claims_YoY")]:
        prev = df[col].shift(12)
        result[out] = ((df[col] - prev) / prev.replace(0, np.nan) * 100).round(2)
    return result.dropna().reset_index()


def _claim_frequency(monthly):
    """Claim frequency = (Claim_Count / Policy_Count) × 100"""
    df = monthly.copy()
    df["Claim_Frequency"] = (
        df["Claim_Count"] / df["Policy_Count"].replace(0, np.nan) * 100
    ).fillna(0).round(4)
    return df[["Month", "Claim_Frequency"]]


def _claim_severity(monthly):
    """Claim severity = Claim_Amount / Claim_Count"""
    df = monthly.copy()
    df["Claim_Severity"] = (
        df["Claim_Amount"] / df["Claim_Count"].replace(0, np.nan)
    ).fillna(0).round(2)
    return df[["Month", "Claim_Severity"]]


def _seasonal_analysis(monthly):
    """Average claims and premium by calendar month with seasonal index."""
    df = monthly.copy()
    df["Month_Num"]  = pd.to_datetime(df["Month"]).dt.month
    df["Month_Name"] = pd.to_datetime(df["Month"]).dt.strftime("%b")

    seasonal = (
        df.groupby(["Month_Num", "Month_Name"])
        .agg(Avg_Premium=("Written_Premium", "mean"),
             Avg_Claims =("Claim_Amount",    "mean"))
        .reset_index()
        .sort_values("Month_Num")
    )
    for col in ["Avg_Premium", "Avg_Claims"]:
        mean_val = seasonal[col].mean()
        seasonal[f"{col}_Index"] = (
            (seasonal[col] / mean_val * 100).round(1) if mean_val > 0 else 100.0
        )
    return seasonal


def _product_breakdown(df, monthly):
    """Loss ratio and claim exposure by product type."""
    gb = df.groupby("_Product").agg(
        Total_Premium=("_Premium", "sum"),
        Total_Claims=("_Claims", "sum"),
    ).reset_index()
    gb["Loss_Ratio"] = (gb["Total_Claims"] / gb["Total_Premium"].replace(0, np.nan) * 100).round(2)
    gb.rename(columns={"_Product": "Product"}, inplace=True)
    return gb.sort_values("Total_Claims", ascending=False).reset_index(drop=True)

def _segment_breakdown(df):
    """Loss ratio and claim exposure by customer segment."""
    gb = df.groupby("_Segment").agg(
        Total_Premium=("_Premium", "sum"),
        Total_Claims=("_Claims", "sum"),
    ).reset_index()
    gb["Loss_Ratio"] = (gb["Total_Claims"] / gb["Total_Premium"].replace(0, np.nan) * 100).round(2)
    gb.rename(columns={"_Segment": "Customer_Segment"}, inplace=True)
    return gb.sort_values("Total_Claims", ascending=False).reset_index(drop=True)

def _channel_breakdown(df):
    """Loss ratio and claim exposure by distribution channel."""
    gb = df.groupby("_Channel").agg(
        Total_Premium=("_Premium", "sum"),
        Total_Claims=("_Claims", "sum"),
    ).reset_index()
    gb["Loss_Ratio"] = (gb["Total_Claims"] / gb["Total_Premium"].replace(0, np.nan) * 100).round(2)
    gb.rename(columns={"_Channel": "Distribution_Channel"}, inplace=True)
    return gb.sort_values("Total_Claims", ascending=False).reset_index(drop=True)


def run_forecasting_pipeline(df_pricing, forecast_periods=12):
    """
    Main entry point called by orchestrator.py:
        from agents.forecasting import run_forecasting_pipeline
        forecast_results = run_forecasting_pipeline(df_pricing)

    Args:
        df_pricing:       DataFrame from run_pricing_pipeline()
        forecast_periods: Months ahead to forecast (default 12)

    Returns dict with keys:
        monthly_df        - monthly aggregated DataFrame
        claims_forecast   - DataFrame (ds, yhat, yhat_lower, yhat_upper)
        premium_forecast  - DataFrame (ds, yhat, yhat_lower, yhat_upper)
        freq_df           - claim frequency by month
        sev_df            - claim severity by month
        yoy_df            - year-over-year growth DataFrame
        seasonal_df       - seasonal index by calendar month
        product_df        - product-level breakdown
        segment_df        - segment-level breakdown
        channel_df        - channel-level breakdown
        kpis              - dict of summary KPIs
        forecast_periods  - int
    """
    df      = _prepare_df(df_pricing)
    monthly = _aggregate_monthly(df)

    # Guard: need at least 3 months to forecast
    if len(monthly) < 3:
        empty_fc = pd.DataFrame(columns=["ds", "yhat", "yhat_lower", "yhat_upper"])
        return {
            "monthly_df":       monthly,
            "claims_forecast":  empty_fc,
            "premium_forecast": empty_fc,
            "freq_df":          pd.DataFrame(),
            "sev_df":           pd.DataFrame(),
            "yoy_df":           pd.DataFrame(),
            "seasonal_df":      pd.DataFrame(),
            "product_df":       pd.DataFrame(),
            "segment_df":       pd.DataFrame(),
            "channel_df":       pd.DataFrame(),
            "kpis":             {},
            "forecast_periods": forecast_periods,
        }

    claims_fc  = _prophet_forecast(monthly, "Claim_Amount",    forecast_periods)
    premium_fc = _prophet_forecast(monthly, "Written_Premium", forecast_periods)
    freq_df    = _claim_frequency(monthly)
    sev_df     = _claim_severity(monthly)
    yoy_df      = _yoy_growth(monthly)
    seasonal_df = _seasonal_analysis(monthly)
    product_df  = _product_breakdown(df, monthly)
    segment_df  = _segment_breakdown(df)
    channel_df  = _channel_breakdown(df)

    # Next-month forecast values
    last_hist   = monthly["Month"].max()
    future_fc   = claims_fc[pd.to_datetime(claims_fc["ds"]) > pd.to_datetime(last_hist)]
    future_prem = premium_fc[pd.to_datetime(premium_fc["ds"]) > pd.to_datetime(last_hist)]

    next_claims  = float(future_fc.iloc[0]["yhat"])  if len(future_fc)  > 0 else 0.0
    next_premium = float(future_prem.iloc[0]["yhat"]) if len(future_prem) > 0 else 0.0

    # YoY from most recent period
    latest_yoy = yoy_df.iloc[-1].to_dict() if not yoy_df.empty else {}

    kpis = {
        "Total_Premium":           round(float(monthly["Written_Premium"].sum()), 2),
        "Total_Claims":            round(float(monthly["Claim_Amount"].sum()),    2),
        "Avg_Monthly_Premium":     round(float(monthly["Written_Premium"].mean()), 2),
        "Avg_Monthly_Claims":      round(float(monthly["Claim_Amount"].mean()),    2),
        "Avg_Claim_Severity":      round(float(sev_df["Claim_Severity"].mean()),   2),
        "Avg_Claim_Frequency":     round(float(freq_df["Claim_Frequency"].mean()), 4),
        "Next_Month_Claims_Fc":    round(next_claims,  2),
        "Next_Month_Premium_Fc":   round(next_premium, 2),
        "Premium_YoY":             latest_yoy.get("Premium_YoY", None),
        "Claims_YoY":              latest_yoy.get("Claims_YoY",  None),
        "Total_ML_Expected_Claims": round(float(monthly["ML_Expected_Claims"].sum()), 2) if "ML_Expected_Claims" in monthly else 0.0,
        "Data_Months":             len(monthly),
        "Forecast_Periods":        forecast_periods,
    }

    return {
        "monthly_df":       monthly,
        "claims_forecast":  claims_fc,
        "premium_forecast": premium_fc,
        "freq_df":          freq_df,
        "sev_df":           sev_df,
        "yoy_df":           yoy_df,
        "seasonal_df":      seasonal_df,
        "product_df":       product_df,
        "segment_df":       segment_df,
        "channel_df":       channel_df,
        "kpis":             kpis,
        "forecast_periods": forecast_periods,
    }
