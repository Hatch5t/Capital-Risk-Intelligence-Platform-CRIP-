import pandas as pd
import numpy as np
import config

# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def classify_ratio(x):
    """Classify combined ratio into profitability tiers."""
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


def get_profitability_color(combined_ratio):
    """Return color based on combined ratio thresholds."""
    if pd.isna(combined_ratio):
        return "#808080"  # Gray for unknown
    elif combined_ratio < 0.80:
        return "#2ecc71"  # Green - profitable
    elif combined_ratio <= 0.95:
        return "#f39c12"  # Amber - monitor
    else:
        return "#e74c3c"  # Red - loss-making


def generate_rate_recommendation(product_name, combined_ratio, target_cr=0.85):
    """Generate actionable pricing recommendation based on combined ratio."""
    if pd.isna(combined_ratio):
        return f"⚠️ {product_name}: Insufficient data for pricing recommendation. Review data quality."
    
    if combined_ratio <= target_cr:
        margin = (target_cr - combined_ratio) * 100
        return f"✅ {product_name}: CR {combined_ratio:.2f} — Profitable. {margin:.1f}pp margin above target CR {target_cr}. Consider competitive positioning."
    
    elif combined_ratio <= 1.0:
        # Calculate required premium increase to achieve target CR
        # If CR = Claims + Expenses / Premium, and we want new_CR = target_cr
        # new_Premium = (Claims + Expenses) / target_cr
        # increase_pct = (new_Premium / old_Premium - 1) * 100 = (CR / target_cr - 1) * 100
        increase_pct = ((combined_ratio / target_cr) - 1) * 100
        urgency = "→ suggest" if combined_ratio <= 0.95 else "→ recommend"
        return f"⚠️ {product_name}: CR {combined_ratio:.2f} {urgency} {increase_pct:.0f}-{increase_pct + 3:.0f}% premium increase to achieve target CR of {target_cr}."
    
    else:
        # Loss-making: CR > 1.0
        increase_pct = ((combined_ratio / target_cr) - 1) * 100
        return f"🚨 {product_name}: CR {combined_ratio:.2f} — LOSS-MAKING. Urgent action required: {increase_pct:.0f}-{increase_pct + 5:.0f}% premium increase or portfolio review needed."


def flag_data_quality_issues(df, product_col="Product"):
    """Identify and flag data quality issues."""
    flags = []
    
    if product_col in df.columns:
        # Check for unknown/missing products
        unknown_mask = df[product_col].isna() | df[product_col].str.upper().str.contains("UNKNOWN", na=False)
        unknown_count = unknown_mask.sum()
        
        if unknown_count > 0:
            unknown_pct = (unknown_count / len(df)) * 100
            flags.append({
                "issue": "Unknown Product Classification",
                "severity": "High" if unknown_pct > 10 else "Medium",
                "count": unknown_count,
                "percentage": unknown_pct,
                "recommendation": f"⚠️ DATA QUALITY: {unknown_count} policies ({unknown_pct:.1f}%) have unknown product classification. Review source system mapping."
            })
    
    # Check for missing premium values
    if "Written_Premium" in df.columns:
        missing_premium = df["Written_Premium"].isna().sum()
        if missing_premium > 0:
            flags.append({
                "issue": "Missing Premium Data",
                "severity": "High",
                "count": missing_premium,
                "percentage": (missing_premium / len(df)) * 100,
                "recommendation": f"🚨 DATA QUALITY: {missing_premium} records missing premium data."
            })
    
    return flags


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

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
    
    # 6. Assign colors for visualization
    df_pricing["Profitability_Color"] = df_pricing["Combined_Ratio"].apply(get_profitability_color)
    
    # ─────────────────────────────────────────────────────────────────────────
    # KPIs - Enhanced with Ratios
    # ─────────────────────────────────────────────────────────────────────────
    
    total_premium = df_pricing['Written_Premium'].sum() if 'Written_Premium' in df_pricing.columns else 0
    total_claims = df_pricing['Claim_Amount'].sum() if 'Claim_Amount' in df_pricing.columns else 0
    total_expenses = df_pricing['Total_Expense'].sum() if 'Total_Expense' in df_pricing.columns else 0
    underwriting_profit = df_pricing['Underwriting_Profit'].sum() if 'Underwriting_Profit' in df_pricing.columns else 0
    
    # Calculate portfolio-level ratios
    portfolio_loss_ratio = total_claims / total_premium if total_premium > 0 else np.nan
    portfolio_expense_ratio = total_expenses / total_premium if total_premium > 0 else np.nan
    portfolio_combined_ratio = portfolio_loss_ratio + portfolio_expense_ratio if not pd.isna(portfolio_loss_ratio) else np.nan
    
    kpis = {
        # Absolute values (existing)
        "Total_Premium": total_premium,
        "Total_Claims": total_claims,
        "Total_Expenses": total_expenses,
        "Underwriting_Profit": underwriting_profit,
        
        # Ratios (new)
        "Loss_Ratio": round(portfolio_loss_ratio, 4) if not pd.isna(portfolio_loss_ratio) else None,
        "Expense_Ratio": round(portfolio_expense_ratio, 4) if not pd.isna(portfolio_expense_ratio) else None,
        "Combined_Ratio": round(portfolio_combined_ratio, 4) if not pd.isna(portfolio_combined_ratio) else None,
        
        # Policy counts
        "Total_Policies": len(df_pricing),
    }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Profitability Distribution (for donut chart)
    # ─────────────────────────────────────────────────────────────────────────
    
    profitability_distribution = df_pricing["Profitability_Tier"].value_counts().to_dict()
    profitability_distribution_pct = {
        tier: {
            "count": count,
            "percentage": round((count / len(df_pricing)) * 100, 1)
        }
        for tier, count in profitability_distribution.items()
    }
    
    # Color mapping for donut chart
    tier_colors = {
        "Excellent": "#27ae60",   # Dark green
        "Good": "#2ecc71",        # Light green
        "Marginal": "#f39c12",    # Amber
        "Loss-Making": "#e74c3c", # Red
        "Unknown": "#808080"      # Gray
    }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Product-Level Analysis with Colors
    # ─────────────────────────────────────────────────────────────────────────
    
    product_summary = None
    if "Product" in df_pricing.columns:
        product_summary = df_pricing.groupby("Product").agg({
            "Written_Premium": "sum",
            "Claim_Amount": "sum",
            "Total_Expense": "sum",
            "Underwriting_Profit": "sum"
        }).reset_index()
        
        product_summary["Loss_Ratio"] = product_summary["Claim_Amount"] / product_summary["Written_Premium"]
        product_summary["Expense_Ratio"] = product_summary["Total_Expense"] / product_summary["Written_Premium"]
        product_summary["Combined_Ratio"] = product_summary["Loss_Ratio"] + product_summary["Expense_Ratio"]
        product_summary["Profitability_Tier"] = product_summary["Combined_Ratio"].apply(classify_ratio)
        product_summary["Bar_Color"] = product_summary["Combined_Ratio"].apply(get_profitability_color)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Data Quality Flags
    # ─────────────────────────────────────────────────────────────────────────
    
    data_quality_flags = flag_data_quality_issues(df_pricing)
    
    # ─────────────────────────────────────────────────────────────────────────
    # AI Pricing Insights - Actionable Recommendations
    # ─────────────────────────────────────────────────────────────────────────
    
    insights = []
    
    # Data quality warnings first
    for flag in data_quality_flags:
        insights.append(flag["recommendation"])
    
    # Product-specific recommendations
    if product_summary is not None:
        for _, row in product_summary.iterrows():
            recommendation = generate_rate_recommendation(
                product_name=row["Product"],
                combined_ratio=row["Combined_Ratio"],
                target_cr=0.85
            )
            insights.append(recommendation)
    
    # Portfolio-level insight
    if portfolio_combined_ratio:
        if portfolio_combined_ratio < 0.85:
            insights.append(f"📊 Portfolio Summary: Overall CR {portfolio_combined_ratio:.2f} — healthy margin. Focus on growth in profitable segments.")
        elif portfolio_combined_ratio < 1.0:
            insights.append(f"📊 Portfolio Summary: Overall CR {portfolio_combined_ratio:.2f} — profitable but thin margins. Prioritize underperforming segments for rate action.")
        else:
            insights.append(f"📊 Portfolio Summary: Overall CR {portfolio_combined_ratio:.2f} — PORTFOLIO LOSS. Immediate portfolio-wide review required.")
    
    # Loss-making policy concentration warning
    loss_making_count = profitability_distribution.get("Loss-Making", 0)
    loss_making_pct = (loss_making_count / len(df_pricing)) * 100 if len(df_pricing) > 0 else 0
    if loss_making_pct > 30:
        insights.append(f"🚨 ALERT: {loss_making_count} policies ({loss_making_pct:.1f}%) are loss-making. Consider segmentation analysis to identify root causes.")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Chart Configuration Metadata
    # ─────────────────────────────────────────────────────────────────────────
    
    chart_config = {
        "reference_lines": {
            "combined_ratio_breakeven": {
                "y": 1.0,
                "line_dash": "dash",
                "line_color": "#e74c3c",
                "annotation": "Breakeven (CR = 1.0)"
            },
            "target_combined_ratio": {
                "y": 0.85,
                "line_dash": "dot",
                "line_color": "#3498db",
                "annotation": "Target CR (0.85)"
            }
        },
        "color_scale": {
            "profitable": "#2ecc71",    # CR < 0.80
            "monitor": "#f39c12",       # CR 0.80-0.95
            "loss_making": "#e74c3c"    # CR > 0.95
        },
        "tier_colors": tier_colors
    }
    
    return {
        "df_pricing": df_pricing,
        "kpis": kpis,
        "profitability_distribution": profitability_distribution_pct,
        "product_summary": product_summary,
        "data_quality_flags": data_quality_flags,
        "insights": insights,
        "chart_config": chart_config
    }
