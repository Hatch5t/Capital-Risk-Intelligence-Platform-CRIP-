import pandas as pd
import numpy as np
import json
import os
import subprocess
import tempfile
from datetime import datetime

# ─────────────────────────────────────────────────────────────────
# Module-level formatters (used by _build_docx_js)
# ─────────────────────────────────────────────────────────────────
def _s(v, fmt="{:,.2f}", fallback="N/A"):
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)): return fallback
        return fmt.format(float(v))
    except Exception: return str(v)

def _inr(v):  return _s(v, "\u20b9{:,.0f}")
def _pct(v):  return _s(v, "{:.2f}%")
def _num(v):  return _s(v, "{:,.0f}")
def _f4(v):   return _s(v, "{:.4f}")


# ─────────────────────────────────────────────────────────────────
# Portfolio Health Score  (unchanged)
# ─────────────────────────────────────────────────────────────────
def calculate_health_score(
    gov_results,
    pricing_results,
    risk_results,
    forecast_results,
    stress_results
):
    """
    Multi-dimensional health score across 6 pillars (100 pts total).
    Each pillar has graduated scoring — not binary pass/fail.

    Pillar 1 — Underwriting Profitability (25 pts)
    Pillar 2 — Capital Adequacy (20 pts)
    Pillar 3 — Portfolio Quality / Loss-Making Tier (15 pts)
    Pillar 4 — Stress Resilience (15 pts)
    Pillar 5 — Model & Data Quality (15 pts)
    Pillar 6 — Trend & Forecast (10 pts)
    """
    score = 0
    breakdown = {}

    pk  = pricing_results["kpis"]
    pm  = risk_results["portfolio_metrics"]
    fk  = forecast_results["kpis"]
    df_p = pricing_results.get("df_pricing", pd.DataFrame())

    # ── Pillar 1: Underwriting Profitability (25 pts) ─────────────
    prem = pk["Total_Premium"]
    cr   = (pk["Total_Claims"] + pk["Total_Expenses"]) / max(prem, 1)
    if cr < 0.75:
        p1 = 25
    elif cr < 0.85:
        p1 = 20
    elif cr < 0.95:
        p1 = 14
    elif cr < 1.00:
        p1 = 7
    else:
        p1 = 0
    score += p1
    breakdown["Underwriting (CR)"] = f"{p1}/25 (CR={cr*100:.1f}%)"

    # ── Pillar 2: Capital Adequacy (20 pts) ───────────────────────
    sol = pm["Solvency_Ratio"]
    if sol > 250:
        p2 = 20
    elif sol > 200:
        p2 = 17
    elif sol > 150:
        p2 = 13
    elif sol > 120:
        p2 = 7
    else:
        p2 = 0
    score += p2
    breakdown["Capital Adequacy"] = f"{p2}/20 (Solvency={sol:.1f}%)"

    # ── Pillar 3: Portfolio Quality — Loss-Making Tier (15 pts) ──
    p3 = 0
    if not df_p.empty and "Profitability_Tier" in df_p.columns:
        td = df_p["Profitability_Tier"].value_counts()
        total = len(df_p)
        loss_pct = td.get("Loss-Making", 0) / max(total, 1) * 100
        if loss_pct < 10:
            p3 = 15
        elif loss_pct < 20:
            p3 = 11
        elif loss_pct < 35:
            p3 = 6
        elif loss_pct < 50:
            p3 = 2
        else:
            p3 = 0
    else:
        p3 = 8  # neutral if no tier data
    score += p3
    breakdown["Portfolio Quality"] = f"{p3}/15 (loss-making tier)"

    # ── Pillar 4: Stress Resilience (15 pts) ──────────────────────
    stress_sol = stress_results.get("solvency_ratio", 0)
    is_sol     = stress_results.get("is_solvent", False)
    if not is_sol:
        p4 = 0
    elif stress_sol > 80:
        p4 = 15
    elif stress_sol > 75:
        p4 = 11
    elif stress_sol > 60:
        p4 = 6
    elif stress_sol > 50:
        p4 = 3
    else:
        p4 = 0
    score += p4
    breakdown["Stress Resilience"] = f"{p4}/15 (stress solvency={stress_sol:.1f}%)"

    # ── Pillar 5: Model & Data Quality (15 pts) ───────────────────
    auc  = pm.get("AUC", 0)
    anomalies  = len(gov_results["anomalies"])
    clean_rows = len(gov_results["df_clean"])
    anom_rate  = anomalies / max(clean_rows, 1)

    # AUC sub-score (0-8)
    if auc >= 0.95:
        auc_sub = 8
    elif auc >= 0.90:
        auc_sub = 7
    elif auc >= 0.80:
        auc_sub = 5
    elif auc >= 0.70:
        auc_sub = 2
    else:
        auc_sub = 0

    # Data quality sub-score (0-7)
    if anom_rate < 0.03:
        dq_sub = 7
    elif anom_rate < 0.05:
        dq_sub = 5
    elif anom_rate < 0.10:
        dq_sub = 3
    else:
        dq_sub = 1

    p5 = auc_sub + dq_sub
    score += p5
    breakdown["Model & Data Quality"] = f"{p5}/15 (AUC={auc:.4f}, anomaly={anom_rate*100:.1f}%)"

    # ── Pillar 6: Trend & Forecast (10 pts) ───────────────────────
    cyoy = fk.get("Claims_YoY",  None)
    pyoy = fk.get("Premium_YoY", None)
    p6 = 5  # neutral default

    if isinstance(cyoy, float) and isinstance(pyoy, float):
        gap = cyoy - pyoy  # positive = claims growing faster than premium (bad)
        fc_lr = fk.get("Next_Month_Claims_Fc", 0) / max(fk.get("Next_Month_Premium_Fc", 1), 1) * 100

        trend_score = 5  # neutral
        if gap < -5:
            trend_score = 7   # premium growing much faster than claims — very good
        elif gap < 0:
            trend_score = 6   # premium growing slightly faster
        elif gap < 3:
            trend_score = 5   # broadly stable
        elif gap < 8:
            trend_score = 3   # claims outpacing premium
        else:
            trend_score = 1   # claims growing much faster — bad

        fc_score = 3 if fc_lr < 80 else 2 if fc_lr < 95 else 1 if fc_lr < 105 else 0

        p6 = min(10, trend_score + fc_score)

    score += p6
    breakdown["Trend & Forecast"] = f"{p6}/10 (YoY gap={f'{cyoy-pyoy:.1f}pp' if isinstance(cyoy,float) and isinstance(pyoy,float) else 'N/A'})"

    return round(min(score, 100), 1)


def get_score_breakdown(gov_results, pricing_results, risk_results,
                         forecast_results, stress_results):
    """Returns the per-pillar breakdown for display purposes."""
    # Re-run the same logic to expose breakdown — call calculate_health_score
    # which now logs internally. We just return a simplified version here.
    pk  = pricing_results["kpis"]
    pm  = risk_results["portfolio_metrics"]
    fk  = forecast_results["kpis"]
    df_p = pricing_results.get("df_pricing", pd.DataFrame())

    cr  = (pk["Total_Claims"] + pk["Total_Expenses"]) / max(pk["Total_Premium"], 1)
    sol = pm["Solvency_Ratio"]
    auc = pm.get("AUC", 0)
    anom = len(gov_results["anomalies"]) / max(len(gov_results["df_clean"]), 1) * 100
    stress_sol = stress_results.get("solvency_ratio", 0)

    loss_pct = 0
    if not df_p.empty and "Profitability_Tier" in df_p.columns:
        loss_pct = df_p["Profitability_Tier"].value_counts().get("Loss-Making",0) / max(len(df_p),1) * 100

    cyoy = fk.get("Claims_YoY", None)
    pyoy = fk.get("Premium_YoY", None)
    gap  = (cyoy - pyoy) if isinstance(cyoy,float) and isinstance(pyoy,float) else None

    return {
        "Combined Ratio":      f"{cr*100:.2f}%",
        "Solvency Ratio":      f"{sol:.1f}%",
        "Loss-Making Policies":f"{loss_pct:.1f}%",
        "Stress Solvency":     f"{stress_sol:.1f}%",
        "Model AUC":           f"{auc:.4f}",
        "Anomaly Rate":        f"{anom:.1f}%",
        "YoY Claims vs Prem Gap": f"{gap:+.1f}pp" if gap is not None else "N/A",
    }


# ─────────────────────────────────────────────────────────────────
# Portfolio Rating  — aligned to actuarial credit rating conventions
# ─────────────────────────────────────────────────────────────────
def assign_portfolio_rating(health_score):
    """
    Insurance portfolio performance rating — aligned to actuarial
    and IRDAI internal assessment conventions.

    Not a credit rating. This is an underwriting health classification
    used internally by actuarial committees and management.
    """
    if health_score >= 88:
        return "Exceptional"        # Outstanding across all pillars
    elif health_score >= 75:
        return "Strong"             # Above average — minor concerns only
    elif health_score >= 62:
        return "Satisfactory"       # Meets regulatory expectations
    elif health_score >= 48:
        return "Moderate"           # Notable weaknesses — action needed
    elif health_score >= 35:
        return "Weak"               # Material concerns — urgent action
    elif health_score >= 20:
        return "Critical"           # Multiple failures — remediation required
    return "Distressed"             # Immediate regulatory intervention


def assign_portfolio_outlook(health_score, is_solvent, stress_sol):
    """
    Three-point outlook scale used alongside the portfolio rating.
    Positive / Stable / Negative — based on trend and stress resilience.
    """
    if not is_solvent:
        return "Negative"
    if health_score >= 75 and stress_sol >= 80:
        return "Positive"
    elif health_score >= 55 and stress_sol >= 65:
        return "Stable"
    else:
        return "Negative"


# ─────────────────────────────────────────────────────────────────
# Executive Summary  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_executive_summary(
    gov_results,
    pricing_results,
    risk_results,
    forecast_results,
    stress_results
):
    pricing = pricing_results["kpis"]

    premium  = pricing["Total_Premium"]
    claims   = pricing["Total_Claims"]
    expenses = pricing["Total_Expenses"]
    profit   = pricing["Underwriting_Profit"]

    combined_ratio = (
        (claims + expenses) / premium
        if premium > 0 else 0
    )

    solvency    = risk_results["portfolio_metrics"]["Solvency_Ratio"]
    auc         = risk_results["portfolio_metrics"]["AUC"]
    var_99      = risk_results["portfolio_metrics"]["VaR_99"]

    next_claims  = forecast_results["kpis"].get("Next_Month_Claims_Fc", 0)
    next_premium = forecast_results["kpis"].get("Next_Month_Premium_Fc", 0)
    claims_yoy   = forecast_results["kpis"].get("Claims_YoY", None)
    premium_yoy  = forecast_results["kpis"].get("Premium_YoY", None)

    scenario   = stress_results["scenario_label"]
    is_solvent = stress_results["is_solvent"]

    # Performance descriptor from actual CR
    if combined_ratio < 0.80:
        perf = "excellent profitability"
    elif combined_ratio < 0.95:
        perf = "good underwriting profitability"
    elif combined_ratio < 1.00:
        perf = "marginal underwriting performance"
    else:
        perf = "underwriting losses"

    # YoY clause only if data exists
    yoy_clause = ""
    if isinstance(claims_yoy, float) and isinstance(premium_yoy, float):
        yoy_clause = (
            f" Claims have {'declined' if claims_yoy < 0 else 'grown'} "
            f"{abs(claims_yoy):.1f}% year-on-year and premium has "
            f"{'contracted' if premium_yoy < 0 else 'grown'} {abs(premium_yoy):.1f}%."
        )

    stress_clause = (
        f" Portfolio remained solvent under {scenario}."
        if is_solvent else
        f" Capital shortfall identified under {scenario} — management action required."
    )

    summary = (
        f"The insurance portfolio was analysed across data governance, pricing, "
        f"risk intelligence, forecasting and stress testing dimensions. "
        f"The portfolio generated total premium of ₹{premium:,.0f} and underwriting "
        f"{'profit' if profit >= 0 else 'loss'} of ₹{abs(profit):,.0f}. "
        f"The current combined ratio stands at {combined_ratio:.2%}, indicating {perf}. "
        f"Current solvency ratio is {solvency:.1f}% and VaR (99%) is ₹{var_99:,.0f}. "
        f"The predictive model achieved AUC of {auc:.4f}."
        f"{yoy_clause} "
        f"Forecasting indicates next month expected premium of ₹{next_premium:,.0f} "
        f"and expected claims of ₹{next_claims:,.0f}. "
        f"Stress testing under {scenario} was performed to assess capital resilience."
        f"{stress_clause} "
        f"Overall portfolio performance remains "
        f"{'stable' if solvency > 120 else 'under pressure'}."
    )

    return summary


# ─────────────────────────────────────────────────────────────────
# Actuarial Opinion  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_actuarial_opinion(
    pricing_results,
    risk_results,
    stress_results
):
    pricing = pricing_results["kpis"]
    premium = pricing["Total_Premium"]

    combined_ratio = (
        pricing["Total_Claims"] + pricing["Total_Expenses"]
    ) / max(premium, 1)

    solvency = risk_results["portfolio_metrics"]["Solvency_Ratio"]
    auc      = risk_results["portfolio_metrics"]["AUC"]
    is_sol   = stress_results["is_solvent"]
    scenario = stress_results["scenario_label"]

    if combined_ratio < 1 and solvency > 150:
        pricing_line = (
            f"Current premium levels are adequate with a combined ratio of "
            f"{combined_ratio*100:.2f}%, demonstrating profitable underwriting."
        )
    elif combined_ratio < 1:
        pricing_line = (
            f"Premium levels are generally sufficient at a combined ratio of "
            f"{combined_ratio*100:.2f}%, though capital headroom is limited."
        )
    else:
        pricing_line = (
            f"Premium levels are insufficient. The combined ratio of "
            f"{combined_ratio*100:.2f}% indicates claims and expenses exceed premium income."
        )

    if solvency > 200:
        capital_line = (
            f"Capital adequacy is robust at {solvency:.1f}%, "
            f"materially above the 150% regulatory threshold."
        )
    elif solvency > 150:
        capital_line = (
            f"Capital adequacy is satisfactory at {solvency:.1f}%, "
            f"above the minimum regulatory threshold."
        )
    else:
        capital_line = (
            f"Capital adequacy is a concern at {solvency:.1f}%. "
            f"Management should review capital planning."
        )

    model_line = (
        f"The predictive model achieves AUC of {auc:.4f}, "
        f"{'meeting' if auc >= 0.80 else 'below'} the 0.80 actuarial governance threshold."
    )

    stress_line = (
        f"The organisation is capable of absorbing {scenario} while maintaining solvency."
        if is_sol else
        f"The organisation cannot absorb {scenario} without a capital shortfall — "
        f"immediate remediation is required."
    )

    return (
        f"Based on the available portfolio experience, risk profile and stress testing results: "
        f"{pricing_line} "
        f"{capital_line} "
        f"{model_line} "
        f"{stress_line}"
    )


# ─────────────────────────────────────────────────────────────────
# Dashboard Metrics  (unchanged)
# ─────────────────────────────────────────────────────────────────
def generate_dashboard_metrics(
    pricing_results,
    risk_results,
    forecast_results,
    stress_results
):
    pricing = pricing_results["kpis"]
    premium = pricing["Total_Premium"]

    combined_ratio = (
        pricing["Total_Claims"] + pricing["Total_Expenses"]
    ) / max(premium, 1)

    return {
        "Premium":          premium,
        "Claims":           pricing["Total_Claims"],
        "Expenses":         pricing["Total_Expenses"],
        "Profit":           pricing["Underwriting_Profit"],
        "Combined_Ratio":   round(combined_ratio * 100, 2),
        "Solvency_Ratio":   risk_results["portfolio_metrics"]["Solvency_Ratio"],
        "VaR":              risk_results["portfolio_metrics"]["VaR_99"],
        "Expected_Shortfall": risk_results["portfolio_metrics"]["Expected_Shortfall"],
        "Forecast_Claims":  forecast_results["kpis"].get("Next_Month_Claims_Fc", 0),
        "Forecast_Premium": forecast_results["kpis"].get("Next_Month_Premium_Fc", 0),
        "Stress_Solvency":  stress_results["solvency_ratio"],
    }


# ─────────────────────────────────────────────────────────────────
# Key Findings  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_key_findings(
    gov_results,
    pricing_results,
    risk_results,
    forecast_results,
    stress_results
):
    findings = []

    # Data Quality
    anomalies  = len(gov_results["anomalies"])
    clean_rows = len(gov_results["df_clean"])
    anom_pct   = anomalies / max(clean_rows, 1) * 100
    findings.append(
        f"{anomalies:,} anomalous records ({anom_pct:.1f}% of dataset) "
        f"identified during data validation."
    )

    # Worst product line
    df_p = pricing_results.get("df_pricing", pd.DataFrame())
    if not df_p.empty and "Product_Type" in df_p.columns and "Loss_Ratio" in df_p.columns:
        worst = df_p.groupby("Product_Type")["Loss_Ratio"].mean().idxmax()
        worst_lr = df_p.groupby("Product_Type")["Loss_Ratio"].mean().max() * 100
        findings.append(
            f"{worst} exhibits the highest loss ratio at {worst_lr:.1f}%."
        )

    # Combined ratio
    pricing = pricing_results["kpis"]
    combined_ratio = (
        pricing["Total_Claims"] + pricing["Total_Expenses"]
    ) / max(pricing["Total_Premium"], 1)

    if combined_ratio < 1:
        findings.append(
            f"Combined Ratio of {combined_ratio*100:.1f}% indicates "
            f"profitable underwriting performance."
        )
    else:
        findings.append(
            f"Combined Ratio of {combined_ratio*100:.1f}% indicates underwriting losses."
        )

    # Solvency
    solvency = risk_results["portfolio_metrics"]["Solvency_Ratio"]
    findings.append(
        f"Current solvency ratio stands at {solvency:.1f}%, "
        f"{'above' if solvency > 150 else 'below'} the 150% regulatory minimum."
    )

    # Capital
    findings.append(
        f"Value at Risk (99%) estimated at "
        f"₹{risk_results['portfolio_metrics']['VaR_99']:,.0f}."
    )
    findings.append(
        f"Expected Shortfall estimated at "
        f"₹{risk_results['portfolio_metrics']['Expected_Shortfall']:,.0f}."
    )

    # Model
    auc = risk_results["portfolio_metrics"]["AUC"]
    findings.append(
        f"Predictive model achieved AUC of {auc:.4f} — "
        f"{'excellent' if auc >= 0.90 else 'acceptable' if auc >= 0.80 else 'below threshold'} "
        f"discrimination."
    )

    # Forecast
    next_claim   = forecast_results["kpis"].get("Next_Month_Claims_Fc",  0)
    next_premium = forecast_results["kpis"].get("Next_Month_Premium_Fc", 0)
    findings.append(
        f"Next month forecast indicates claims of ₹{next_claim:,.0f} "
        f"and premium income of ₹{next_premium:,.0f}."
    )

    # Stress
    findings.append(
        f"Stress testing scenario '{stress_results['scenario_label']}' "
        f"was successfully evaluated."
    )

    if stress_results["is_solvent"]:
        findings.append(
            f"Portfolio remained solvent with solvency ratio of "
            f"{stress_results['solvency_ratio']:.1f}% under the selected stress scenario."
        )
    else:
        findings.append(
            f"Capital shortfall of ₹{stress_results['kpis']['Shortfall']:,.0f} "
            f"identified under the selected stress scenario."
        )

    return findings


# ─────────────────────────────────────────────────────────────────
# Metadata  (unchanged)
# ─────────────────────────────────────────────────────────────────
def generate_metadata(gov_results, forecast_periods, stress_results):
    return {
        "report_name":      "Actuarial Capital Validation & Risk Assessment Report",
        "report_date":      datetime.now().strftime("%d-%m-%Y"),
        "records_analysed": len(gov_results["df_clean"]),
        "forecast_horizon": forecast_periods,
        "stress_scenario":  stress_results["scenario_label"],
        "generated_by":     "CRIP Platform",
    }


# ─────────────────────────────────────────────────────────────────
# Data Validation  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_data_validation_section(gov_results):
    missing_df  = gov_results.get("missing_df", pd.DataFrame())
    missing_cnt = int(missing_df["Missing Count"].sum()) if not missing_df.empty else 0
    raw         = gov_results["summary"]["total_rows"]
    clean       = len(gov_results["df_clean"])
    anom        = len(gov_results["anomalies"])
    dupes       = gov_results.get("duplicates_count", 0)
    anom_pct    = round(anom / max(clean, 1) * 100, 2)
    status      = "REVIEW" if anom_pct > 5 else "PASS"

    return {
        "rows_analysed":   raw,
        "rows_cleaned":    clean,
        "anomalies":       anom,
        "anomaly_pct":     anom_pct,
        "missing_values":  missing_cnt,
        "duplicates":      dupes,
        "status":          status,
    }


# ─────────────────────────────────────────────────────────────────
# Pricing Assessment  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_pricing_assessment(pricing_results):
    kpi = pricing_results["kpis"]
    df  = pricing_results.get("df_pricing", pd.DataFrame())

    prem = kpi["Total_Premium"]
    clm  = kpi["Total_Claims"]
    exp  = kpi["Total_Expenses"]
    prof = kpi["Underwriting_Profit"]
    lr   = clm  / max(prem, 1)
    er   = exp  / max(prem, 1)
    cr   = lr + er

    # Dynamic interpretation
    if cr < 0.80:
        interpretation = (
            f"Excellent underwriting performance. Combined ratio of {cr*100:.2f}% is well "
            f"below the 80% target, indicating strong premium adequacy and disciplined claims "
            f"management. The portfolio has generated an underwriting profit of "
            f"\u20b9{abs(prof):,.0f}, providing a comfortable buffer above breakeven."
        )
    elif cr < 0.95:
        interpretation = (
            f"Good underwriting performance. Combined ratio of {cr*100:.2f}% is within the "
            f"acceptable 80\u201395% band. The portfolio remains profitable at "
            f"\u20b9{abs(prof):,.0f} underwriting profit, though management should monitor "
            f"expense trends to prevent margin erosion."
        )
    elif cr < 1.00:
        interpretation = (
            f"Marginal underwriting performance. Combined ratio of {cr*100:.2f}% is "
            f"approaching breakeven. The \u20b9{abs(prof):,.0f} profit margin is thin and "
            f"susceptible to adverse claims development. Immediate premium review is "
            f"recommended across underperforming product lines."
        )
    else:
        interpretation = (
            f"Underwriting loss recorded. Combined ratio of {cr*100:.2f}% exceeds 100%, "
            f"meaning claims and expenses of \u20b9{clm+exp:,.0f} exceed written premium of "
            f"\u20b9{prem:,.0f} by \u20b9{abs(prof):,.0f}. Urgent repricing and risk "
            f"selection review is required to restore technical profitability."
        )

    # Product breakdown
    product_table = []
    worst_product = best_product = None
    if not df.empty and "Product_Type" in df.columns:
        grp = df.groupby("Product_Type").agg(
            Premium =("Written_Premium", "sum"),
            Claims  =("Claim_Amount",    "sum"),
            Expenses=("Total_Expense",   "sum"),
            Count   =("Written_Premium", "count"),
        ).reset_index()
        grp["LR"]        = (grp["Claims"] / grp["Premium"].replace(0, np.nan) * 100).round(1)
        grp["CR"]        = ((grp["Claims"] + grp["Expenses"]) / grp["Premium"].replace(0, np.nan) * 100).round(1)
        grp["Profit"]    = (grp["Premium"] - grp["Claims"] - grp["Expenses"]).round(0)
        grp["Prem_Share"]= (grp["Premium"] / grp["Premium"].sum() * 100).round(1)
        product_table    = grp.sort_values("Premium", ascending=False).to_dict("records")
        worst_product    = grp.loc[grp["LR"].idxmax(), "Product_Type"]
        best_product     = grp.loc[grp["LR"].idxmin(), "Product_Type"]

    # Profitability tier distribution
    tier_dist = {}
    tier_commentary = ""
    if not df.empty and "Profitability_Tier" in df.columns:
        tier_dist = df["Profitability_Tier"].value_counts().to_dict()
        total    = sum(tier_dist.values())
        good_pct = (tier_dist.get("Excellent",0) + tier_dist.get("Good",0)) / max(total,1) * 100
        loss_pct = tier_dist.get("Loss-Making",0) / max(total,1) * 100
        loss_cnt = tier_dist.get("Loss-Making",0)
        if good_pct >= 70:
            tier_commentary = (
                f"{good_pct:.1f}% of policies are in the Excellent or Good tier, indicating "
                f"a well-priced and broadly profitable portfolio. The {loss_cnt} loss-making "
                f"policies ({loss_pct:.1f}%) represent a manageable tail that should be "
                f"reviewed at renewal."
            )
        elif loss_pct > 30:
            tier_commentary = (
                f"{loss_pct:.1f}% of policies ({loss_cnt} policies) are loss-making, which "
                f"is above the 30% threshold warranting remediation. These policies should "
                f"be subject to non-renewal or significant premium adjustment at next cycle."
            )
        else:
            tier_commentary = (
                f"Portfolio profitability distribution shows {good_pct:.1f}% in profitable "
                f"tiers with {loss_pct:.1f}% loss-making. A targeted re-underwriting "
                f"exercise on Marginal and Loss-Making tiers is recommended."
            )

    # Channel & segment mix
    channel_mix = {}
    segment_mix = {}
    policy_status = {}
    if not df.empty:
        if "Distribution_Channel" in df.columns:
            channel_mix = df["Distribution_Channel"].value_counts().to_dict()
        if "Customer_Segment" in df.columns:
            segment_mix = df["Customer_Segment"].value_counts().to_dict()
        if "Policy_Status" in df.columns:
            policy_status = df["Policy_Status"].value_counts().to_dict()

    # Product commentary
    product_commentary = ""
    if worst_product and best_product:
        worst_lr = next((r["LR"] for r in product_table if r["Product_Type"] == worst_product), 0)
        best_lr  = next((r["LR"] for r in product_table if r["Product_Type"] == best_product),  0)
        product_commentary = (
            f"{worst_product} carries the highest loss ratio at {worst_lr:.1f}%, indicating "
            f"underpricing or adverse claims experience. A full actuarial repricing exercise "
            f"and claims root cause analysis is recommended for this line. "
            f"{best_product} is the best-performing product at {best_lr:.1f}% loss ratio, "
            f"providing cross-subsidy headroom across the portfolio."
        )

    return {
        "combined_ratio":     round(cr * 100, 2),
        "loss_ratio":         round(lr * 100, 2),
        "expense_ratio":      round(er * 100, 2),
        "premium":            prem,
        "claims":             clm,
        "expenses":           exp,
        "profit":             prof,
        "interpretation":     interpretation,
        "product_table":      product_table,
        "worst_product":      worst_product,
        "best_product":       best_product,
        "product_commentary": product_commentary,
        "tier_dist":          tier_dist,
        "tier_commentary":    tier_commentary,
        "channel_mix":        channel_mix,
        "segment_mix":        segment_mix,
        "policy_status":      policy_status,
    }


# ─────────────────────────────────────────────────────────────────
# Capital Validation  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_capital_validation(risk_results):
    pm  = risk_results["portfolio_metrics"]
    sol = pm["Solvency_Ratio"]

    if sol > 200:
        validation = (
            f"Capital position is robust at {sol:.1f}%, "
            f"significantly above the 150% regulatory threshold."
        )
    elif sol > 150:
        validation = (
            f"Capital position is adequate at {sol:.1f}%, "
            f"above the minimum regulatory threshold."
        )
    elif sol > 120:
        validation = (
            f"Capital position is borderline at {sol:.1f}%. "
            f"Capital strengthening is advisable."
        )
    else:
        validation = (
            f"Capital position is insufficient at {sol:.1f}%. "
            f"Immediate capital remediation required."
        )

    return {
        "var":              pm["VaR_99"],
        "expected_shortfall": pm["Expected_Shortfall"],
        "solvency":         sol,
        "capital_adequacy": pm.get("Capital_Adequacy", round(sol / 100, 2)),
        "validation":       validation,
    }


# ─────────────────────────────────────────────────────────────────
# Model Validation  — now data-driven (removed debug prints)
# ─────────────────────────────────────────────────────────────────
def generate_model_validation(risk_results):
    pm     = risk_results["portfolio_metrics"]
    df_r   = risk_results.get("df_risk", pd.DataFrame())

    auc   = pm.get("AUC", 0)

    # KS, Brier, PSI live in df_risk columns (set by risk_intelligence.py)
    def _col_val(col_names):
        for col in col_names:
            if col in df_r.columns:
                v = df_r[col].iloc[0] if len(df_r) > 0 else None
                if v is not None and not (isinstance(v, float) and np.isnan(v)):
                    return round(float(v), 4)
        return None

    ks    = _col_val(["KS Statistic", "KS_Statistic"])
    brier = _col_val(["Brier Score",  "Brier_Score"])
    psi   = _col_val(["PSI"])

    # Fall back to portfolio_metrics if df_risk doesn't have them
    if ks    is None: ks    = pm.get("KS_Statistic", pm.get("KS Statistic",   None))
    if brier is None: brier = pm.get("Brier_Score",  pm.get("Brier Score",    None))
    if psi   is None: psi   = pm.get("PSI",                                   None)

    auc_pass   = auc > 0.80
    brier_pass = brier is None or brier < 0.25
    psi_pass   = psi   is None or psi   < 0.10
    status     = "PASS" if (auc_pass and brier_pass and psi_pass) else "REVIEW"

    return {
        "auc":    auc,
        "ks":     round(ks,    4) if ks    is not None else "N/A",
        "brier":  round(brier, 4) if brier is not None else "N/A",
        "psi":    round(psi,   4) if psi   is not None else "N/A",
        "status": status,
    }


# ─────────────────────────────────────────────────────────────────
# Risk Dashboard  (unchanged — already data-driven)
# ─────────────────────────────────────────────────────────────────
def generate_risk_dashboard(df_risk):
    def _mean(col):
        return round(float(df_risk[col].mean()), 2) if col in df_risk.columns else 0.0

    ins  = _mean("Insurance_Risk")
    mkt  = _mean("Market_Risk")
    crd  = _mean("Credit_Risk")
    ops  = _mean("Operational_Risk")
    cat  = _mean("Hazard_Score")

    scores = {"Insurance": ins, "Market": mkt, "Credit": crd,
              "Operational": ops, "Catastrophe": cat}
    dominant   = max(scores, key=scores.get)
    dom_val    = scores[dominant]

    def _level(s): return "High" if s > 6 else "Medium" if s > 3 else "Low"

    # Dynamic per-category commentary based on actual score
    def _commentary(name, val):
        lv = _level(val)
        lines = {
            "Insurance": {
                "High":   f"Insurance risk of {val:.2f}/10 is elevated. Claims frequency and severity are above portfolio norms. Immediate underwriting guideline review and risk selection tightening is recommended.",
                "Medium": f"Insurance risk of {val:.2f}/10 is moderate. Loss experience is within acceptable bands but warrants continued quarterly monitoring of frequency and severity trends.",
                "Low":    f"Insurance risk of {val:.2f}/10 is well-controlled. Current risk selection and pricing appear adequate to contain underwriting losses.",
            },
            "Market": {
                "High":   f"Market risk of {val:.2f}/10 is high. Elevated interest rate and inflation exposure requires an Asset-Liability Management review. Consider duration matching and inflation-linked hedging.",
                "Medium": f"Market risk of {val:.2f}/10 is moderate. Current macro-economic conditions are manageable but the portfolio should be stress-tested against a 200bps rate shock.",
                "Low":    f"Market risk of {val:.2f}/10 is low. The investment portfolio appears well-positioned relative to current market conditions.",
            },
            "Credit": {
                "High":   f"Credit risk of {val:.2f}/10 is high. Premium receivables and days-past-due metrics indicate collection pressure. Implement an escalation protocol for overdue accounts beyond 60 days.",
                "Medium": f"Credit risk of {val:.2f}/10 is moderate. Premium collection performance is acceptable but recovery trends should be tracked monthly.",
                "Low":    f"Credit risk of {val:.2f}/10 is low. Premium recovery is strong and counterparty exposure is well-managed.",
            },
            "Operational": {
                "High":   f"Operational risk of {val:.2f}/10 is high. Fraud detection flags, exception handling backlogs, and processing delays are contributing. Urgent process automation and SIU protocol enhancement is required.",
                "Medium": f"Operational risk of {val:.2f}/10 is moderate. Manual intervention rates and exception counts are within tolerance but should be benchmarked against industry standards.",
                "Low":    f"Operational risk of {val:.2f}/10 is low. Internal controls and processing workflows appear effective.",
            },
            "Catastrophe": {
                "High":   f"Catastrophe risk of {val:.2f}/10 is high. Significant natural peril exposure detected. Review CAT reinsurance programme adequacy and consider purchasing additional aggregate cover or ILW (Industry Loss Warranty) protection.",
                "Medium": f"Catastrophe risk of {val:.2f}/10 is moderate. Current CAT reinsurance programme appears broadly adequate. Validate event retention limits against updated PML estimates.",
                "Low":    f"Catastrophe risk of {val:.2f}/10 is low. The portfolio is well-diversified geographically with limited peak zone concentration.",
            },
        }
        return lines.get(name, {}).get(lv, f"{name} risk at {val:.2f}/10.")

    commentary = {k: _commentary(k, v) for k, v in scores.items()}

    # High risk policy count
    high_risk_pct = 0.0
    if "High_Risk_Prob" in df_risk.columns:
        high_risk_pct = round((df_risk["High_Risk_Prob"] > 0.7).mean() * 100, 1)

    return {
        "insurance":    ins,
        "market":       mkt,
        "credit":       crd,
        "operational":  ops,
        "cat":          cat,
        "scores":       scores,
        "levels":       {k: _level(v) for k, v in scores.items()},
        "dominant":     dominant,
        "dominant_val": dom_val,
        "commentary":   commentary,
        "high_risk_pct":high_risk_pct,
    }


# ─────────────────────────────────────────────────────────────────
# Forecast Assessment  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_forecast_assessment(forecast_results):
    kpi  = forecast_results["kpis"]
    nc   = kpi["Next_Month_Claims_Fc"]
    np_  = kpi["Next_Month_Premium_Fc"]
    cyoy = kpi.get("Claims_YoY",  None)
    pyoy = kpi.get("Premium_YoY", None)
    sev  = kpi.get("Avg_Claim_Severity", 0)
    fc_lr = nc / max(np_, 1) * 100

    parts = []
    if isinstance(cyoy, float):
        parts.append(
            f"Claims have {'declined' if cyoy < 0 else 'grown'} "
            f"{abs(cyoy):.1f}% year-on-year."
        )
    if isinstance(pyoy, float):
        parts.append(
            f"Premium has {'contracted' if pyoy < 0 else 'grown'} "
            f"{abs(pyoy):.1f}% year-on-year."
        )
    if fc_lr < 80:
        parts.append(
            f"Forecast loss ratio of {fc_lr:.1f}% indicates "
            f"continued profitable underwriting next month."
        )
    elif fc_lr < 100:
        parts.append(
            f"Forecast loss ratio of {fc_lr:.1f}% is marginal — "
            f"pricing adequacy should be reviewed."
        )
    else:
        parts.append(
            f"Forecast loss ratio of {fc_lr:.1f}% indicates "
            f"expected underwriting pressure next month."
        )

    # Seasonal peak
    sea = forecast_results.get("seasonal_df", pd.DataFrame())
    if not sea.empty and "Avg_Claims_Index" in sea.columns:
        peak = sea.loc[sea["Avg_Claims_Index"].idxmax(), "Month_Name"]
        low  = sea.loc[sea["Avg_Claims_Index"].idxmin(), "Month_Name"]
        parts.append(
            f"Seasonal analysis indicates peak claims in {peak} "
            f"and lowest activity in {low}."
        )

    interpretation = " ".join(parts) if parts else "Premium and claims remain stable. Future outlook remains positive."

    # Seasonal data
    sea = forecast_results.get("seasonal_df", pd.DataFrame())
    sea_rows = []
    peak_month = low_month = "N/A"
    if not sea.empty and "Avg_Claims_Index" in sea.columns:
        peak_month = sea.loc[sea["Avg_Claims_Index"].idxmax(), "Month_Name"]
        low_month  = sea.loc[sea["Avg_Claims_Index"].idxmin(), "Month_Name"]
        for _, row in sea.iterrows():
            ci = float(row.get("Avg_Claims_Index", 100))
            pi = float(row.get("Avg_Premium_Index", 100))
            flag = "Peak" if ci > 110 else "Low" if ci < 90 else "Average"
            sea_rows.append([
                str(row.get("Month_Name","")),
                f"{ci:.1f}",
                f"{pi:.1f}",
                flag,
            ])

    # YoY data
    yoy_df   = forecast_results.get("yoy_df", pd.DataFrame())
    yoy_rows = []
    if not yoy_df.empty:
        for _, row in yoy_df.tail(12).iterrows():
            cyoy_m = row.get("Claims_YoY", 0)
            pyoy_m = row.get("Premium_YoY", 0)
            gap    = cyoy_m - pyoy_m
            yoy_rows.append([
                str(row.get("Month", ""))[:7],
                f"{pyoy_m:+.1f}%",
                f"{cyoy_m:+.1f}%",
                f"{gap:+.1f}pp",
                "Widening" if gap > 2 else "Stable" if gap > -2 else "Improving",
            ])

    # Product forecast
    prod_fc = forecast_results.get("product_df", pd.DataFrame())
    prod_fc_rows = []
    if not prod_fc.empty:
        for _, row in prod_fc.iterrows():
            lr_v = float(row.get("Loss_Ratio", 0))
            prod_fc_rows.append([
                str(row.get("Product", "")),
                f"\u20b9{float(row.get('Total_Premium',0)):,.0f}",
                f"\u20b9{float(row.get('Total_Claims',0)):,.0f}",
                f"{lr_v:.1f}%",
                "Above Target" if lr_v > 60 else "On Target",
            ])

    # Dynamic interpretation — richer
    parts = []
    if isinstance(cyoy, float) and isinstance(pyoy, float):
        gap = cyoy - pyoy
        if gap > 2:
            parts.append(
                f"Claims are growing faster than premium ({cyoy:+.1f}% vs {pyoy:+.1f}% YoY), "
                f"creating a {gap:.1f}pp pricing gap that will compress margins if sustained. "
                f"Proactive rate action is required to close this gap before the next renewal cycle."
            )
        elif gap < -2:
            parts.append(
                f"Premium growth is outpacing claims growth ({pyoy:+.1f}% vs {cyoy:+.1f}% YoY), "
                f"a favourable {abs(gap):.1f}pp trend that is expected to improve the combined "
                f"ratio over the next 12 months."
            )
        else:
            parts.append(
                f"Premium and claims are growing at similar rates ({pyoy:+.1f}% and "
                f"{cyoy:+.1f}% YoY respectively), indicating a broadly stable pricing position."
            )
    if fc_lr < 80:
        parts.append(
            f"The forecast loss ratio of {fc_lr:.1f}% for next month indicates continued "
            f"profitable underwriting. Forecast claims of \u20b9{nc:,.0f} against forecast "
            f"premium of \u20b9{np_:,.0f} are well within acceptable bounds."
        )
    elif fc_lr < 100:
        parts.append(
            f"Forecast loss ratio of {fc_lr:.1f}% is marginal. At forecast claims of "
            f"\u20b9{nc:,.0f} and premium of \u20b9{np_:,.0f}, the portfolio is near "
            f"breakeven — pricing adequacy should be reviewed immediately."
        )
    else:
        parts.append(
            f"Forecast loss ratio of {fc_lr:.1f}% indicates expected underwriting losses "
            f"next month. Forecast claims of \u20b9{nc:,.0f} are projected to exceed "
            f"premium of \u20b9{np_:,.0f}."
        )
    if peak_month != "N/A":
        parts.append(
            f"Seasonal analysis identifies {peak_month} as the peak claims month and "
            f"{low_month} as the lowest — a pattern that should inform reinsurance "
            f"programme timing and cash flow planning."
        )

    interpretation = " ".join(parts) if parts else "Premium and claims remain stable."

    return {
        "next_claim":      nc,
        "next_premium":    np_,
        "avg_severity":    sev,
        "fc_loss_ratio":   round(fc_lr, 2),
        "claims_yoy":      cyoy,
        "premium_yoy":     pyoy,
        "interpretation":  interpretation,
        "sea_rows":        sea_rows,
        "yoy_rows":        yoy_rows,
        "prod_fc_rows":    prod_fc_rows,
        "peak_month":      peak_month,
        "low_month":       low_month,
    }


# ─────────────────────────────────────────────────────────────────
# Stress Assessment  (unchanged)
# ─────────────────────────────────────────────────────────────────
def generate_stress_assessment(stress_results):
    sr = stress_results["scenario_result"]

    return {
        "scenario":          stress_results["scenario_label"],
        "combined_ratio":    sr["stressed_cr"],
        "solvency":          sr["solvency_ratio"],
        "capital_consumed":  sr["capital_consumed"],
        "remaining_capital": sr["remaining_capital"],
    }


# ─────────────────────────────────────────────────────────────────
# Management Actions  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_management_actions(
    pricing_results=None,
    risk_results=None,
    stress_results=None,
    forecast_results=None
):
    actions = []

    # Worst product from actual data
    if pricing_results is not None:
        df_p = pricing_results.get("df_pricing", pd.DataFrame())
        if not df_p.empty and "Product_Type" in df_p.columns and "Loss_Ratio" in df_p.columns:
            worst = df_p.groupby("Product_Type")["Loss_Ratio"].mean().idxmax()
            actions.append(f"Review {worst} pricing strategy — highest loss ratio in portfolio")

    # Solvency action
    if risk_results is not None:
        sol = risk_results["portfolio_metrics"]["Solvency_Ratio"]
        if sol < 150:
            actions.append(
                f"Strengthen capital position — solvency ratio of {sol:.1f}% "
                f"is below the 150% regulatory threshold"
            )
        else:
            actions.append(
                f"Maintain capital buffer — solvency ratio of {sol:.1f}% "
                f"is adequate; review at next quarterly cycle"
            )

    actions.append("Continue quarterly stress testing")

    # Dominant risk category
    if risk_results is not None:
        df_r = risk_results["df_risk"]
        scores = {
            "Market":      df_r["Market_Risk"].mean()      if "Market_Risk"      in df_r.columns else 0,
            "Operational": df_r["Operational_Risk"].mean() if "Operational_Risk" in df_r.columns else 0,
            "Insurance":   df_r["Insurance_Risk"].mean()   if "Insurance_Risk"   in df_r.columns else 0,
            "Catastrophe": df_r["Hazard_Score"].mean()     if "Hazard_Score"     in df_r.columns else 0,
        }
        dominant = max(scores, key=scores.get)
        actions.append(f"Monitor {dominant.lower()} risk exposure — currently the highest-scoring risk category")

    # Claims trend
    if forecast_results is not None:
        cyoy = forecast_results["kpis"].get("Claims_YoY", None)
        if isinstance(cyoy, float) and cyoy > 5:
            actions.append(
                f"Investigate claims growth of {cyoy:.1f}% YoY — "
                f"assess need for reserve strengthening"
            )

    actions.append("Maintain capital buffer")
    actions.append("Strengthen anomaly monitoring and fraud SIU protocols")

    return actions


# ─────────────────────────────────────────────────────────────────
# Findings Register  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_findings_register(
    gov_results=None,
    pricing_results=None,
    risk_results=None,
    stress_results=None
):
    register = []
    fid = 1

    # F001 — Anomalies
    if gov_results is not None:
        anom     = len(gov_results["anomalies"])
        clean    = len(gov_results["df_clean"])
        anom_pct = anom / max(clean, 1) * 100
        register.append({
            "ID":             f"F{fid:03d}",
            "Finding":        f"{anom:,} anomalies identified during data validation ({anom_pct:.1f}% of records)",
            "Severity":       "High" if anom_pct > 10 else "Medium",
            "Recommendation": "Strengthen data capture at source; implement real-time validation at policy inception",
        }); fid += 1

    # F002 — Worst product
    if pricing_results is not None:
        df_p = pricing_results.get("df_pricing", pd.DataFrame())
        if not df_p.empty and "Product_Type" in df_p.columns and "Loss_Ratio" in df_p.columns:
            worst    = df_p.groupby("Product_Type")["Loss_Ratio"].mean().idxmax()
            worst_lr = df_p.groupby("Product_Type")["Loss_Ratio"].mean().max() * 100
            register.append({
                "ID":             f"F{fid:03d}",
                "Finding":        f"{worst} product carries highest loss ratio of {worst_lr:.1f}%",
                "Severity":       "High" if worst_lr > 100 else "Medium",
                "Recommendation": f"Conduct actuarial repricing review for {worst}; apply risk-based surcharges",
            }); fid += 1

    # F003 — Dominant risk
    if risk_results is not None:
        df_r = risk_results["df_risk"]
        scores = {
            "Market":      df_r["Market_Risk"].mean()      if "Market_Risk"      in df_r.columns else 0,
            "Catastrophe": df_r["Hazard_Score"].mean()     if "Hazard_Score"     in df_r.columns else 0,
            "Operational": df_r["Operational_Risk"].mean() if "Operational_Risk" in df_r.columns else 0,
            "Insurance":   df_r["Insurance_Risk"].mean()   if "Insurance_Risk"   in df_r.columns else 0,
        }
        dom   = max(scores, key=scores.get)
        dom_v = scores[dom]
        register.append({
            "ID":             f"F{fid:03d}",
            "Finding":        f"{dom} risk remains the dominant portfolio risk (score: {dom_v:.2f}/10)",
            "Severity":       "High" if dom_v > 6 else "Medium",
            "Recommendation": "Strengthen risk monitoring and consider hedging strategies",
        }); fid += 1

        # F004 — Model AUC
        auc = risk_results["portfolio_metrics"]["AUC"]
        register.append({
            "ID":             f"F{fid:03d}",
            "Finding":        f"Predictive model achieved AUC of {auc:.4f}",
            "Severity":       "Low" if auc >= 0.80 else "High",
            "Recommendation": "Model meets governance standards; schedule annual revalidation" if auc >= 0.80 else "Retrain model — below 0.80 governance threshold",
        }); fid += 1

    # F005 — Stress result
    if stress_results is not None:
        is_sol = stress_results.get("is_solvent", True)
        sol    = stress_results.get("solvency_ratio", 100)
        register.append({
            "ID":             f"F{fid:03d}",
            "Finding":        f"Portfolio {'remained solvent' if is_sol else 'showed capital shortfall'} under stress testing (solvency: {sol:.1f}%)",
            "Severity":       "Low" if is_sol and sol > 75 else "High",
            "Recommendation": "Continue quarterly stress testing" if is_sol else "Initiate capital action plan immediately",
        }); fid += 1

    # Fallback if nothing passed in
    if not register:
        return [
            {"ID":"F001","Finding":"Anomalies identified during data validation","Severity":"Medium","Recommendation":"Continue anomaly monitoring"},
            {"ID":"F002","Finding":"Market risk remains the dominant portfolio risk","Severity":"High","Recommendation":"Strengthen risk monitoring"},
            {"ID":"F003","Finding":"Health product shows highest loss ratio","Severity":"Medium","Recommendation":"Review pricing adequacy"},
            {"ID":"F004","Finding":"Portfolio remained solvent under stress testing","Severity":"Low","Recommendation":"Continue quarterly stress testing"},
        ]

    return register


# ─────────────────────────────────────────────────────────────────
# Chart Commentary  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_chart_commentary(
    pricing_results=None,
    risk_results=None,
    forecast_results=None,
    stress_results=None
):
    # Loss ratio commentary
    lr_comment = "Loss ratio monitoring required across all product lines."
    if pricing_results is not None:
        df_p = pricing_results.get("df_pricing", pd.DataFrame())
        if not df_p.empty and "Product_Type" in df_p.columns and "Loss_Ratio" in df_p.columns:
            grp   = df_p.groupby("Product_Type")["Loss_Ratio"].mean()
            worst = grp.idxmax()
            best  = grp.idxmin()
            lr_comment = (
                f"{worst} exhibits the highest loss ratio at {grp.max()*100:.1f}%. "
                f"{best} is the best-performing product at {grp.min()*100:.1f}%. "
                f"Continued monitoring of {worst} pricing adequacy is recommended."
            )

    # Profitability commentary
    prof_comment = "Portfolio profitability monitoring in progress."
    if pricing_results is not None:
        pk   = pricing_results["kpis"]
        prof = pk["Underwriting_Profit"]
        cr   = (pk["Total_Claims"] + pk["Total_Expenses"]) / max(pk["Total_Premium"], 1)
        prof_comment = (
            f"Portfolio underwriting {'profit' if prof >= 0 else 'loss'} of "
            f"₹{abs(prof):,.0f} reflects a combined ratio of {cr*100:.2f}%. "
            f"{'Overall underwriting profitability remains strong.' if cr < 1 else 'Pricing corrective action is needed.'}"
        )

    # Feature importance commentary
    fi_comment = "Risk and policy characteristics remain the strongest drivers of expected claims."
    if risk_results is not None:
        fi = risk_results.get("feature_importance", pd.DataFrame())
        if not fi.empty:
            top = fi.head(2)["Feature"].tolist()
            fi_comment = (
                f"{top[0]} and {top[1] if len(top) > 1 else 'policy tenure'} are the "
                f"strongest predictors of claim outcomes based on XGBoost feature importance."
            )

    # Forecast commentary
    fc_comment = "Claims and premiums are forecast to remain stable with moderate seasonality."
    if forecast_results is not None:
        fk   = forecast_results["kpis"]
        cyoy = fk.get("Claims_YoY", None)
        nc   = fk.get("Next_Month_Claims_Fc", 0)
        fc_comment = f"Claims forecast at ₹{nc:,.0f} next month."
        if isinstance(cyoy, float):
            fc_comment += f" Claims trend is {'downward' if cyoy < 0 else 'upward'} ({cyoy:+.1f}% YoY)."

    # Stress commentary
    st_comment = "Catastrophic scenarios generate the greatest deterioration in solvency position."
    if stress_results is not None:
        all_sc = stress_results.get("all_scenarios", pd.DataFrame())
        worst_label = "Scenario 5 (Catastrophic Event)"
        if not all_sc.empty and "Label" in all_sc.columns and "Solvency Ratio (%)" in all_sc.columns:
            worst_label = all_sc.loc[all_sc["Solvency Ratio (%)"].idxmin(), "Label"]
        sol = stress_results.get("solvency_ratio", 100)
        st_comment = (
            f"{worst_label} generates the greatest solvency deterioration. "
            f"Under {stress_results['scenario_label']}, solvency ratio is {sol:.1f}%. "
            f"{'Capital remains adequate.' if stress_results.get('is_solvent', True) else 'Capital shortfall identified.'}"
        )

    return {
        "loss_ratio":         lr_comment,
        "profitability":      prof_comment,
        "feature_importance": fi_comment,
        "forecast":           fc_comment,
        "stress_testing":     st_comment,
    }


# ─────────────────────────────────────────────────────────────────
# Final Conclusion  — now data-driven
# ─────────────────────────────────────────────────────────────────
def generate_final_conclusion(
    health_score,
    portfolio_rating,
    risk_results,
    pricing_results=None,
    stress_results=None
):
    solvency = risk_results["portfolio_metrics"]["Solvency_Ratio"]

    cr_ok = True
    if pricing_results is not None:
        pk = pricing_results["kpis"]
        cr = (pk["Total_Claims"] + pk["Total_Expenses"]) / max(pk["Total_Premium"], 1)
        cr_ok = cr < 1.0

    is_sol = stress_results.get("is_solvent", True) if stress_results else True

    if solvency > 150 and cr_ok and is_sol:
        return (
            f"Overall Portfolio Rating: {portfolio_rating}\n\n"
            f"The actuarial assessment indicates that the portfolio remains financially "
            f"strong with a Health Score of {health_score}/100. "
            f"Capital adequacy remains satisfactory at {solvency:.1f}% and stress testing "
            f"demonstrates resilience under all evaluated scenarios. "
            f"The current portfolio is considered suitable for continued underwriting with "
            f"ongoing monitoring of market and catastrophe risks."
        )

    return (
        f"Overall Portfolio Rating: {portfolio_rating}\n\n"
        f"The portfolio requires continued monitoring of solvency, pricing and capital adequacy. "
        f"Health Score of {health_score}/100 reflects areas that need management attention. "
        f"Management actions outlined in this report should be implemented within the current quarter."
    )


def generate_business_insights(pricing_results, risk_results, forecast_results):
    """
    Returns a dict with six insight blocks, each derived entirely from
    actual pipeline results — no hardcoded product names or values.
    """
    bi   = {}
    df   = pricing_results["df_pricing"]
    kpi  = pricing_results["kpis"]
    pm   = risk_results["portfolio_metrics"]
    fkpi = forecast_results["kpis"]
    TARGET_CR = 95.0

    # ── 1. Rate adequacy per product ─────────────────────────────
    if "Product_Type" in df.columns and "Combined_Ratio" in df.columns:
        prod_cr = df.groupby("Product_Type")["Combined_Ratio"].mean() * 100
        rate_rows = []
        for prod, cr in prod_cr.sort_values(ascending=False).items():
            chg    = round((cr / TARGET_CR - 1) * 100, 1)
            action = (
                "Immediate rate increase required"  if chg >  10 else
                "Rate increase recommended"         if chg >   0 else
                "Rates adequate"                    if chg > -5  else
                "Potential rate reduction headroom"
            )
            rate_rows.append({
                "Product":               prod,
                "Current CR (%)":        round(cr, 1),
                "Rate Change Needed (%)": chg,
                "Action":                action,
            })
        bi["rate_adequacy"] = rate_rows

    # ── 2. Profitability concentration (Pareto) ──────────────────
    if "Underwriting_Profit" in df.columns:
        n_total    = len(df)
        profitable = df[df["Underwriting_Profit"] > 0].sort_values(
                         "Underwriting_Profit", ascending=False)
        total_pos  = profitable["Underwriting_Profit"].sum()
        if total_pos > 0:
            cum = profitable["Underwriting_Profit"].cumsum()
            n80 = int((cum <= total_pos * 0.80).sum()) + 1
            pct80 = round(n80 / n_total * 100, 1)
        else:
            pct80 = 100.0
        loss_df  = df[df["Underwriting_Profit"] < 0]
        loss_cnt = len(loss_df)
        loss_amt = loss_df["Underwriting_Profit"].sum()
        bi["profitability_concentration"] = {
            "top_policies_pct":  pct80,
            "profit_threshold":  80,
            "loss_making_count": loss_cnt,
            "loss_making_pct":   round(loss_cnt / n_total * 100, 1),
            "loss_making_drag":  round(float(loss_amt), 0),
            "profit_ex_losers":  round(float(kpi["Underwriting_Profit"] - loss_amt), 0),
        }

    # ── 3. Cross-subsidisation ───────────────────────────────────
    if "Product_Type" in df.columns and "Underwriting_Profit" in df.columns:
        prod_profit = df.groupby("Product_Type")["Underwriting_Profit"].sum()
        winners = prod_profit[prod_profit > 0].sort_values(ascending=False)
        losers  = prod_profit[prod_profit < 0].sort_values()
        bi["cross_subsidization"] = {
            "profitable_products":  {k: round(float(v), 0) for k, v in winners.items()},
            "loss_making_products": {k: round(float(v), 0) for k, v in losers.items()},
            "is_cross_subsidizing": len(losers) > 0 and len(winners) > 0,
        }

    # ── 4. Frequency vs severity driver ──────────────────────────
    freq_df = forecast_results.get("freq_df", pd.DataFrame())
    sev_df  = forecast_results.get("sev_df",  pd.DataFrame())
    if not freq_df.empty and not sev_df.empty:
        avg_freq = freq_df["Claim_Frequency"].mean()
        avg_sev  = sev_df["Claim_Severity"].mean()
        freq_chg = (freq_df["Claim_Frequency"].iloc[-1] -
                    freq_df["Claim_Frequency"].iloc[0]) if len(freq_df) > 1 else 0
        sev_chg  = (sev_df["Claim_Severity"].iloc[-1] -
                    sev_df["Claim_Severity"].iloc[0])  if len(sev_df)  > 1 else 0
        freq_rel = abs(freq_chg) / max(avg_freq, 0.001)
        sev_rel  = abs(sev_chg)  / max(avg_sev,  1.0)
        bi["frequency_severity"] = {
            "avg_frequency": round(float(avg_freq), 3),
            "avg_severity":  round(float(avg_sev),  0),
            "freq_trend":    "increasing" if freq_chg > 0 else "decreasing",
            "sev_trend":     "increasing" if sev_chg  > 0 else "decreasing",
            "primary_driver": "Frequency-driven" if freq_rel >= sev_rel else "Severity-driven",
        }

    # ── 5. Pricing gap ───────────────────────────────────────────
    yoy_df = forecast_results.get("yoy_df", pd.DataFrame())
    if not yoy_df.empty and {"Premium_YoY", "Claims_YoY"}.issubset(yoy_df.columns):
        avg_p = yoy_df["Premium_YoY"].mean()
        avg_c = yoy_df["Claims_YoY"].mean()
        gap   = avg_c - avg_p
        bi["pricing_gap"] = {
            "avg_premium_growth_pct": round(float(avg_p), 1),
            "avg_claims_growth_pct":  round(float(avg_c), 1),
            "gap_pp":                 round(float(gap), 1),
            "widening":               gap > 2.0,
        }

    # ── 6. Expense efficiency per product ────────────────────────
    if "Product_Type" in df.columns and "Expense_Ratio" in df.columns:
        prod_er = df.groupby("Product_Type")["Expense_Ratio"].mean() * 100
        bi["expense_efficiency"] = {
            "by_product":     {k: round(float(v), 1) for k, v in prod_er.items()},
            "portfolio_avg":  round(float(prod_er.mean()), 1),
            "most_efficient": str(prod_er.idxmin()),
            "least_efficient":str(prod_er.idxmax()),
        }

    return bi


def _format_bi_bullets(bi: dict) -> list:
    """
    Converts the business_insights dict into a flat list of plain-English
    sentences suitable for the DOCX bullet list.
    """
    bullets = []

    # Rate adequacy
    for row in bi.get("rate_adequacy", []):
        chg = row["Rate Change Needed (%)"]
        if chg > 0:
            bullets.append(
                f"RATE ACTION — {row['Product']}: Combined Ratio {row['Current CR (%)']:.1f}%. "
                f"A rate increase of {chg:.1f}% is needed to reach the 95% target."
            )
        elif chg < -5:
            bullets.append(
                f"PRICING HEADROOM — {row['Product']}: Combined Ratio {row['Current CR (%)']:.1f}%. "
                f"Rates could be reduced by {abs(chg):.1f}% while remaining profitable."
            )

    # Profitability concentration
    pc = bi.get("profitability_concentration", {})
    if pc:
        bullets.append(
            f"CONCENTRATION: Top {pc['top_policies_pct']}% of policies generate "
            f"80% of underwriting profit."
        )
        if pc["loss_making_count"] > 0:
            bullets.append(
                f"LOSS DRAG: {pc['loss_making_count']} loss-making policies "
                f"({pc['loss_making_pct']}% of portfolio) are reducing profit by "
                f"\u20b9{abs(pc['loss_making_drag']):,.0f}. "
                f"Removing them would increase profit to \u20b9{pc['profit_ex_losers']:,.0f}."
            )

    # Cross-subsidisation
    cs = bi.get("cross_subsidization", {})
    if cs.get("is_cross_subsidizing"):
        losers  = ", ".join(cs["loss_making_products"].keys())
        winners = ", ".join(cs["profitable_products"].keys())
        bullets.append(
            f"CROSS-SUBSIDY: {winners} profits are currently covering losses in {losers}. "
            "This masks the true underwriting deficit in loss-making lines."
        )

    # Frequency vs severity
    fs = bi.get("frequency_severity", {})
    if fs:
        bullets.append(
            f"CLAIMS DRIVER: Loss experience is primarily {fs['primary_driver'].lower()} "
            f"driven (avg frequency: {fs['avg_frequency']:.1%}, avg severity: "
            f"\u20b9{fs['avg_severity']:,.0f}). "
            f"Frequency is {fs['freq_trend']}, severity is {fs['sev_trend']}."
        )

    # Pricing gap
    pg = bi.get("pricing_gap", {})
    if pg:
        if pg["widening"]:
            bullets.append(
                f"PRICING GAP: Claims growing at {pg['avg_claims_growth_pct']:.1f}% vs "
                f"premium at {pg['avg_premium_growth_pct']:.1f}%. "
                f"The {pg['gap_pp']:.1f}pp gap is widening — proactive rate action is required."
            )
        else:
            bullets.append(
                f"PRICING TREND: Premium growing at {pg['avg_premium_growth_pct']:.1f}% vs "
                f"claims at {pg['avg_claims_growth_pct']:.1f}%. Pricing trend is favourable."
            )

    # Expense efficiency
    ee = bi.get("expense_efficiency", {})
    if ee:
        bullets.append(
            f"EXPENSE: Portfolio average expense ratio is {ee['portfolio_avg']:.1f}%. "
            f"Most efficient: {ee['most_efficient']}. "
            f"Least efficient: {ee['least_efficient']} — review operational costs."
        )

    return bullets if bullets else ["No material business insights identified in current dataset."]


# ─────────────────────────────────────────────────────────────────
# DOCX Report Generation  — replaces create_pdf_report
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# PDF Report Generation  (ReportLab — no Node.js required)
# ─────────────────────────────────────────────────────────────────
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from io import BytesIO


# ── Colour palette ────────────────────────────────────────────────
_NAVY   = colors.HexColor("#1E3A5F")
_BLUE   = colors.HexColor("#2D5986")
_LBLUE  = colors.HexColor("#EFF6FF")
_GREEN  = colors.HexColor("#166534")
_LGREEN = colors.HexColor("#F0FDF4")
_AMBER  = colors.HexColor("#D97706")
_LAMBER = colors.HexColor("#FFFBEB")
_RED    = colors.HexColor("#991B1B")
_LRED   = colors.HexColor("#FEF2F2")
_GREY   = colors.HexColor("#374151")
_LGREY  = colors.HexColor("#F8FAFC")
_WHITE  = colors.white
_BLACK  = colors.HexColor("#1A202C")


def _styles():
    """Return a dict of named ParagraphStyles."""
    base = getSampleStyleSheet()
    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title":    ps("rTitle",    fontSize=28, textColor=_NAVY,  leading=34,
                       alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica-Bold"),
        "subtitle": ps("rSub",      fontSize=13, textColor=_BLUE,  leading=18,
                       alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica"),
        "h1":       ps("rH1",       fontSize=14, textColor=_NAVY,  leading=18,
                       spaceBefore=14, spaceAfter=4, fontName="Helvetica-Bold",
                       borderPadding=(0,0,2,0)),
        "h2":       ps("rH2",       fontSize=11, textColor=_BLUE,  leading=15,
                       spaceBefore=8,  spaceAfter=3, fontName="Helvetica-Bold"),
        "body":     ps("rBody",     fontSize=9,  textColor=_GREY,  leading=13,
                       spaceAfter=4,   fontName="Helvetica"),
        "bullet":   ps("rBullet",   fontSize=9,  textColor=_BLACK, leading=13,
                       spaceAfter=3,   fontName="Helvetica",
                       leftIndent=12,  bulletIndent=0),
        "callout":  ps("rCallout",  fontSize=9,  textColor=_BLACK, leading=13,
                       spaceAfter=4,   fontName="Helvetica",
                       leftIndent=8,   rightIndent=8),
        "tbl_hdr":  ps("rTH",       fontSize=8,  textColor=_WHITE, leading=11,
                       fontName="Helvetica-Bold", alignment=TA_CENTER),
        "tbl_cell": ps("rTC",       fontSize=8,  textColor=_BLACK, leading=11,
                       fontName="Helvetica"),
        "tbl_cell_c":ps("rTCC",     fontSize=8,  textColor=_BLACK, leading=11,
                       fontName="Helvetica", alignment=TA_CENTER),
        "cover_kpi_v": ps("rKV",    fontSize=16, textColor=_WHITE, leading=20,
                          fontName="Helvetica-Bold", alignment=TA_CENTER),
        "cover_kpi_l": ps("rKL",    fontSize=8,  textColor=colors.HexColor("#93C5FD"),
                          leading=11, fontName="Helvetica", alignment=TA_CENTER),
        "footer":   ps("rFtr",      fontSize=7,  textColor=colors.HexColor("#94A3B8"),
                       fontName="Helvetica", alignment=TA_RIGHT),
    }


def _kv_table(pairs, st, col_widths=(7*cm, 4*cm, 7.4*cm)):
    """Build a 3-column key/value/notes table."""
    hdr_data = [
        Paragraph("Metric",              st["tbl_hdr"]),
        Paragraph("Value",               st["tbl_hdr"]),
        Paragraph("Notes / Benchmark",   st["tbl_hdr"]),
    ]
    rows = [hdr_data]
    for p in pairs:
        lbl  = str(p[0])
        val  = str(p[1])
        note = str(p[2]) if len(p) > 2 else ""
        # colour value
        vc = _NAVY
        try:
            num = float(val.replace("%","").replace("₹","").replace(",",""))
            if "%" in val and "Combined" in lbl:
                vc = _RED if num > 100 else (_GREEN if num < 80 else _AMBER)
            elif "%" in val and "Solvency" in lbl:
                vc = _GREEN if num > 150 else (_AMBER if num > 100 else _RED)
        except Exception:
            pass
        val_style = ParagraphStyle("_v", parent=st["tbl_cell_c"], textColor=vc,
                                   fontName="Helvetica-Bold")
        rows.append([
            Paragraph(lbl,  st["tbl_cell"]),
            Paragraph(val,  val_style),
            Paragraph(note, ParagraphStyle("_n", parent=st["tbl_cell"],
                                           textColor=colors.HexColor("#6B7280"))),
        ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0),  _NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [_LGREY, _WHITE]),
        ("BACKGROUND",   (1,1), (1,-1),  colors.HexColor("#EFF6FF")),
        ("GRID",         (0,0), (-1,-1), 0.4, colors.HexColor("#CBD5E1")),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))
    return tbl


def _simple_table(rows_data, headers, col_widths, st,
                  sev_col=None):
    """Build a generic table. sev_col=index of severity column for colour coding."""
    sev_c = {"High":_RED,"Medium":_AMBER,"Low":_GREEN,"Critical":colors.HexColor("#7F1D1D")}
    sev_f = {"High":colors.HexColor("#FEE2E2"),"Medium":colors.HexColor("#FEF3C7"),
             "Low": colors.HexColor("#DCFCE7"), "Critical":colors.HexColor("#FEF2F2")}

    hdr = [Paragraph(h, st["tbl_hdr"]) for h in headers]
    rows = [hdr]
    style_cmds = [
        ("BACKGROUND",    (0,0), (-1,0),  _NAVY),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [_LGREY, _WHITE]),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]
    for ri, row in enumerate(rows_data, start=1):
        cells = []
        for ci, cell in enumerate(row):
            cells.append(Paragraph(str(cell), st["tbl_cell"]))
        rows.append(cells)
        # Severity colour row
        if sev_col is not None and sev_col < len(row):
            sev = str(row[sev_col])
            if sev in sev_f:
                style_cmds.append(("BACKGROUND", (sev_col, ri), (sev_col, ri), sev_f[sev]))
                style_cmds.append(("TEXTCOLOR",  (sev_col, ri), (sev_col, ri), sev_c[sev]))
                style_cmds.append(("FONTNAME",   (sev_col, ri), (sev_col, ri), "Helvetica-Bold"))

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _callout(text, st, fill=None, border=None):
    """Shaded callout paragraph."""
    fill   = fill   or _LBLUE
    border = border or _BLUE
    style  = ParagraphStyle("_co", parent=st["callout"],
                            backColor=fill,
                            borderColor=border, borderWidth=0.5,
                            borderPadding=6, borderRadius=2)
    return Paragraph(text, style)


def _section_header(title, st, story):
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=_NAVY, spaceAfter=3))
    story.append(Paragraph(title, st["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"),
                            spaceAfter=4))


def _bullet(text, st):
    return Paragraph(f"• {text}", st["bullet"])


def _cover_banner(items, st):
    """KPI banner — list of (label, value, #hex_color)."""
    w = 18.4 * cm / len(items)
    data = [[
        Paragraph(v, ParagraphStyle("_bv", parent=st["cover_kpi_v"],
                                    textColor=colors.HexColor(c)))
        for _, v, c in items
    ], [
        Paragraph(l, st["cover_kpi_l"]) for l, _, _ in items
    ]]
    tbl = Table(data, colWidths=[w]*len(items),
                rowHeights=[1.1*cm, 0.55*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), _NAVY),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#2D5986")),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    return tbl


def _on_page(canvas, doc, report_date):
    """Header + footer on every page."""
    canvas.saveState()
    w, h = A4

    # Header bar
    canvas.setFillColor(_NAVY)
    canvas.rect(1.5*cm, h - 1.2*cm, w - 3*cm, 0.6*cm, fill=1, stroke=0)
    canvas.setFillColor(_WHITE)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(1.7*cm, h - 0.88*cm,
                      "CRIP — Actuarial Capital Validation & Risk Assessment Report")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(w - 1.7*cm, h - 0.88*cm, "STRICTLY CONFIDENTIAL")

    # Footer
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(1.5*cm, 0.8*cm,
                      f"© CRIP Platform — {report_date}  |  For Internal Use Only")
    canvas.drawRightString(w - 1.5*cm, 0.8*cm, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(1.5*cm, 1.1*cm, w - 1.5*cm, 1.1*cm)

    canvas.restoreState()


def create_pdf_report(report_results):
    """
    Generates a professional multi-section PDF report.
    Returns raw bytes — pass directly to st.download_button.
    """
    r   = report_results
    st  = _styles()

    meta = r.get("metadata", {})
    pa   = r.get("pricing_assessment", {})
    cv   = r.get("capital_validation", {})
    mv   = r.get("model_validation", {})
    rd   = r.get("risk_dashboard", {})
    fa   = r.get("forecast_assessment", {})
    sa   = r.get("stress_assessment", {})
    dv   = r.get("data_validation", {})
    fr   = r.get("findings_register", [])
    ma   = r.get("management_actions", [])
    cc   = r.get("chart_commentary", {})
    hs   = r.get("health_score", 0)
    rat  = r.get("portfolio_rating", "N/A")
    all_sc = r.get("all_scenarios", [])
    is_sol  = r.get("is_solvent", True)
    outlook = r.get("portfolio_outlook", "Stable")
    bi_bullets = _format_bi_bullets(r.get("business_insights", {}))
    conc_bullets = r.get("conclusion_bullets", [])
    report_date = meta.get("report_date", "")

    sol_fill   = _LGREEN if is_sol else _LRED
    sol_border = _GREEN  if is_sol else _RED

    buf  = BytesIO()
    doc  = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.8*cm,  bottomMargin=1.5*cm,
        title="CRIP Actuarial Report",
        author="CRIP Platform",
    )

    story = []
    on_page = lambda c, d: _on_page(c, d, report_date)

    # ── COVER ────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph("CRIP", st["title"]))
    story.append(Paragraph("Comprehensive Risk Intelligence Platform", st["subtitle"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=_NAVY, spaceAfter=6))
    story.append(Paragraph("ACTUARIAL CAPITAL VALIDATION", ParagraphStyle(
        "_ct", parent=st["title"], fontSize=20, spaceAfter=2)))
    story.append(Paragraph("& RISK ASSESSMENT REPORT", ParagraphStyle(
        "_ct2", parent=st["title"], fontSize=20, spaceAfter=6)))
    story.append(Paragraph(report_date, ParagraphStyle(
        "_cd", parent=st["subtitle"], textColor=colors.HexColor("#64748B"), spaceAfter=4)))
    story.append(Paragraph(
        "Generated by CRIP AI Platform  |  Model Version: v1.0",
        ParagraphStyle("_cg", parent=st["subtitle"],
                       textColor=colors.HexColor("#94A3B8"), fontSize=8, spaceAfter=8)))
    story.append(Spacer(1, 0.3*cm))
    story.append(_cover_banner([
        ("Rating",   rat,                          "#F59E0B"),
        ("Health",   f"{hs}/100",                  "#34D399"),
        ("Solvency", _pct(cv.get("solvency",0)),   "#60A5FA"),
        ("VaR 99%",  _inr(cv.get("var",0)),        "#F87171"),
        ("AUC",      f"{mv.get('auc',0):.2f}",     "#A78BFA"),
        ("Outlook",  outlook,
                     "#34D399" if outlook == "Positive" else "#F59E0B" if outlook == "Stable" else "#F87171"),
    ], st))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        "STRICTLY CONFIDENTIAL \u2014 FOR INTERNAL USE ONLY",
        ParagraphStyle("_conf", parent=st["body"], textColor=_RED,
                       fontName="Helvetica-Bold", alignment=TA_CENTER)))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ────────────────────────────────────────
    _section_header("Table of Contents", st, story)
    toc_items = [
        ("1.",  "Executive Summary & Key Findings"),
        ("2.",  "Report Metadata"),
        ("3.",  "Data Governance & Validation"),
        ("4.",  "Pricing & Profitability Assessment"),
        ("5.",  "Capital Validation"),
        ("6.",  "Model Validation & Feature Importance"),
        ("7.",  "Risk Dashboard"),
        ("8.",  "Forecast Assessment"),
        ("9.",  "Stress Testing Assessment"),
        ("10.", "Chart Interpretations"),
        ("11.", "Validation Findings Register"),
        ("12.", "Management Action Plan"),
        ("13.", "Actuarial Opinion & Final Conclusion"),
        ("14.", "Disclaimers & Methodology"),
    ]
    toc_data = [[
        Paragraph(num, ParagraphStyle("_tn", parent=st["body"], fontName="Helvetica-Bold",
                                      textColor=_NAVY)),
        Paragraph(title, ParagraphStyle("_tt", parent=st["body"], textColor=_GREY)),
    ] for num, title in toc_items]
    toc_tbl = Table(toc_data, colWidths=[1.5*cm, 17*cm])
    toc_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [_LGREY, _WHITE]),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("GRID",           (0,0), (-1,-1), 0.3, colors.HexColor("#CBD5E1")),
    ]))
    story.append(toc_tbl)
    story.append(PageBreak())

    # ── 1. EXECUTIVE SUMMARY ─────────────────────────────────────
    _section_header("1. Executive Summary", st, story)
    story.append(Paragraph(r.get("executive_summary", ""), st["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Key Findings", st["h2"]))
    for f in r.get("key_findings", []):
        story.append(_bullet(f, st))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Business Insights", st["h2"]))
    story.append(Paragraph(
        "The following insights are derived automatically from portfolio data, "
        "identifying specific commercial actions required.",
        st["body"]))
    for b in bi_bullets:
        story.append(_bullet(b, st))
    story.append(PageBreak())

    # ── 2. REPORT METADATA ───────────────────────────────────────
    _section_header("2. Report Metadata", st, story)
    story.append(_kv_table([
        ("Report Name",      meta.get("report_name",""),     ""),
        ("Report Date",      meta.get("report_date",""),     ""),
        ("Records Analysed", str(meta.get("records_analysed","")), "Post-governance"),
        ("Forecast Horizon", f"{meta.get('forecast_horizon',12)} months", ""),
        ("Stress Scenario",  meta.get("stress_scenario",""), ""),
        ("Generated By",     meta.get("generated_by",""),   ""),
    ], st, (5.5*cm, 6*cm, 6.9*cm)))
    story.append(PageBreak())

    # ── 3. DATA GOVERNANCE ───────────────────────────────────────
    _section_header("3. Data Governance & Validation", st, story)
    story.append(Paragraph(
        "Agent 1 performed data profiling, missing value imputation via median/mode strategy, "
        "IQR-based outlier clipping, Isolation Forest anomaly detection (contamination=5%), "
        "and composite fraud scoring. The governance pipeline ensures all downstream agents "
        "receive a clean, validated dataset.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(_kv_table([
        ("Rows Analysed",      _num(dv.get("rows_analysed","")), "Pre-cleaning record count"),
        ("Rows After Cleaning", _num(dv.get("rows_cleaned","")), "Post-governance record count"),
        ("Anomalies Detected",  str(dv.get("anomalies","")),     f"{dv.get('anomaly_pct',0):.1f}% of dataset — Isolation Forest"),
        ("Missing Cells",       str(dv.get("missing_values","")), "Imputed via median/mode strategy"),
        ("Duplicate Records",   str(dv.get("duplicates","")),    "Identified and resolved"),
        ("Validation Status",   dv.get("status","PASS"),         "PASS = suitable for actuarial use"),
    ], st))
    story.append(Spacer(1, 0.15*cm))
    fill = _LGREEN if dv.get("status","PASS") == "PASS" else _LRED
    bdr  = _GREEN  if dv.get("status","PASS") == "PASS" else _RED
    story.append(_callout(
        "Data quality assessment indicates the portfolio data is suitable for actuarial "
        "analysis. No material quality concerns were identified after cleansing. "
        "Imputed values are flagged for review and anomalous records are isolated "
        "for separate SIU investigation."
        if dv.get("status") == "PASS" else
        "Data quality requires review. Material issues were identified after cleansing. "
        "Flagged records should be investigated before use in regulatory submissions.",
        st, fill, bdr))
    story.append(PageBreak())

    # ── 4. PRICING & PROFITABILITY ───────────────────────────────
    _section_header("4. Pricing & Profitability Assessment", st, story)
    story.append(Paragraph(
        "Agent 2 computed per-policy Loss Ratio, Expense Ratio and Combined Ratio. "
        "Policies are tiered as Excellent (<80%), Good (80\u201395%), "
        "Marginal (95\u2013100%) and Loss-Making (>100%) based on combined ratio. "
        "The analysis covers product-line profitability, distribution channel mix, "
        "and customer segment composition.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))

    # Portfolio summary
    story.append(Paragraph("Portfolio Financial Summary", st["h2"]))
    story.append(_kv_table([
        ("Total Written Premium",  _inr(pa.get("premium",0)),        "Gross premium in period"),
        ("Total Claims Incurred",  _inr(pa.get("claims",0)),         "Paid + outstanding claims"),
        ("Total Expenses",         _inr(pa.get("expenses",0)),       "Underwriting + operational"),
        ("Underwriting Profit",    _inr(pa.get("profit",0)),         "Premium \u2212 Claims \u2212 Expenses"),
        ("Loss Ratio",             _pct(pa.get("loss_ratio",0)),     "Claims / Premium; target < 60%"),
        ("Expense Ratio",          _pct(pa.get("expense_ratio",0)),  "Expenses / Premium; target < 30%"),
        ("Combined Ratio",         _pct(pa.get("combined_ratio",0)), "LR + ER; breakeven = 100%"),
    ], st))
    story.append(Spacer(1, 0.15*cm))
    cr_ok = pa.get("combined_ratio",100) < 100
    story.append(_callout(pa.get("interpretation",""), st,
                          _LGREEN if cr_ok else _LRED, _GREEN if cr_ok else _RED))
    story.append(Spacer(1, 0.2*cm))

    # Product breakdown table
    prod_tbl_data = pa.get("product_table", [])
    if prod_tbl_data:
        story.append(Paragraph("Product Line Performance", st["h2"]))
        story.append(Paragraph(
            "The following table shows gross premium, claims, loss ratio and underwriting "
            "profit by product line. Loss ratios above 60% are highlighted as requiring "
            "pricing review.",
            st["body"]))
        story.append(Spacer(1, 0.1*cm))
        p_rows = []
        for p in prod_tbl_data:
            lr_v = float(p.get("LR", 0))
            cr_v = float(p.get("CR", 0))
            p_rows.append([
                str(p.get("Product_Type","")),
                f"{p.get('Prem_Share',0):.1f}%",
                _inr(p.get("Premium",0)),
                _inr(p.get("Claims",0)),
                f"{lr_v:.1f}%",
                f"{cr_v:.1f}%",
                _inr(p.get("Profit",0)),
            ])
        story.append(_simple_table(
            p_rows,
            ["Product","Share","Premium","Claims","Loss Ratio","Combined Ratio","Profit"],
            [2.8*cm, 1.4*cm, 3*cm, 2.8*cm, 2.2*cm, 2.8*cm, 2.8*cm],
            st, sev_col=None))
        story.append(Spacer(1, 0.1*cm))
        if pa.get("product_commentary"):
            story.append(_callout(pa["product_commentary"], st, _LAMBER, _AMBER))
        story.append(Spacer(1, 0.2*cm))

    # Profitability tier distribution
    tier_dist = pa.get("tier_dist", {})
    if tier_dist:
        story.append(Paragraph("Profitability Tier Distribution", st["h2"]))
        total_pol = sum(tier_dist.values())
        tier_rows = []
        tier_order = ["Excellent","Good","Marginal","Loss-Making"]
        for tier in tier_order:
            cnt = tier_dist.get(tier, 0)
            pct = cnt / max(total_pol, 1) * 100
            action = {
                "Excellent":    "Maintain current pricing strategy",
                "Good":         "Monitor for adverse development",
                "Marginal":     "Premium review recommended at renewal",
                "Loss-Making":  "Non-renewal or significant surcharge required",
            }.get(tier, "")
            tier_rows.append([tier, f"{cnt:,}", f"{pct:.1f}%", action])
        story.append(_simple_table(
            tier_rows,
            ["Profitability Tier","Policy Count","% of Portfolio","Recommended Action"],
            [3.5*cm, 2.5*cm, 2.5*cm, 10*cm],
            st, sev_col=0))
        story.append(Spacer(1, 0.1*cm))
        if pa.get("tier_commentary"):
            story.append(_callout(pa["tier_commentary"], st, _LBLUE, _BLUE))
        story.append(Spacer(1, 0.2*cm))

    # Channel & segment mix
    ch = pa.get("channel_mix", {})
    seg = pa.get("segment_mix", {})
    ps  = pa.get("policy_status", {})
    if ch or seg:
        story.append(Paragraph("Portfolio Composition", st["h2"]))
        mix_rows = []
        if ch:
            total_ch = sum(ch.values())
            dominant_ch = max(ch, key=ch.get)
            mix_rows.append(["Distribution Channel",
                              f"{dominant_ch} dominant ({ch[dominant_ch]/total_ch*100:.1f}%)",
                              " | ".join([f"{k}: {v/total_ch*100:.1f}%" for k,v in sorted(ch.items(), key=lambda x:-x[1])])])
        if seg:
            total_seg = sum(seg.values())
            dominant_seg = max(seg, key=seg.get)
            mix_rows.append(["Customer Segment",
                              f"{dominant_seg} dominant ({seg[dominant_seg]/total_seg*100:.1f}%)",
                              " | ".join([f"{k}: {v/total_seg*100:.1f}%" for k,v in sorted(seg.items(), key=lambda x:-x[1])])])
        if ps:
            total_ps = sum(ps.values())
            lapsed = ps.get("Lapsed",0) + ps.get("Cancelled",0)
            mix_rows.append(["Policy Status",
                              f"Active: {ps.get('Active',0)/total_ps*100:.1f}%",
                              f"Lapsed/Cancelled: {lapsed/total_ps*100:.1f}% \u2014 review retention strategy" if lapsed/total_ps > 0.15 else f"Retention is healthy at {(total_ps-lapsed)/total_ps*100:.1f}% active"])
        story.append(_simple_table(mix_rows, ["Dimension","Headline","Detail"],
                                   [3.5*cm, 4.5*cm, 10.5*cm], st))
    story.append(PageBreak())

    # ── 5. CAPITAL VALIDATION ────────────────────────────────────
    _section_header("5. Capital Validation", st, story)
    story.append(Paragraph(
        "Capital adequacy is assessed using a Monte Carlo simulation (1,000 portfolio-level "
        "scenarios). Value at Risk (VaR) at 99% confidence represents the maximum expected "
        "loss that will not be exceeded in 99 out of 100 scenarios. Expected Shortfall (CVaR) "
        "captures the average loss in the worst 1% of scenarios, providing a more conservative "
        "measure of tail risk. The Capital Adequacy Ratio = Total Capital / VaR.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    sol = cv.get("solvency", 0)
    story.append(_kv_table([
        ("VaR (99%)",              _inr(cv.get("var",0)),              "Maximum loss at 99% confidence"),
        ("Expected Shortfall",     _inr(cv.get("expected_shortfall",0)),"Average tail loss; CVaR metric"),
        ("Solvency Ratio",         _pct(sol),                          "Regulatory minimum: 150%"),
        ("Capital Adequacy Ratio", f"{cv.get('capital_adequacy',0):.2f}x","Capital / VaR; minimum 1.0x"),
        ("Capital Position",       str(cv.get("validation","")),       "Assessment outcome"),
    ], st))
    story.append(Spacer(1, 0.15*cm))
    cap_fill = _LGREEN if sol > 150 else (_LAMBER if sol > 120 else _LRED)
    cap_bdr  = _GREEN  if sol > 150 else (_AMBER  if sol > 120 else _RED)
    story.append(_callout(str(cv.get("validation","")), st, cap_fill, cap_bdr))
    story.append(PageBreak())

    # ── 6. MODEL VALIDATION & FEATURE IMPORTANCE ─────────────────
    _section_header("6. Model Validation & Feature Importance", st, story)
    story.append(Paragraph(
        "The XGBoost predictive model was trained on the cleaned portfolio and validated "
        "on held-out data. Four metrics govern model acceptability under IRDAI AI/ML "
        "governance guidelines: AUC (discrimination), Brier Score (calibration), "
        "KS Statistic (separation), and PSI (population stability). "
        "A model fails governance if AUC < 0.80, Brier > 0.25, or PSI > 0.20.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(_kv_table([
        ("AUC Score",         f"{mv.get('auc',0):.4f}", "Discrimination power; excellent \u2265 0.90"),
        ("KS Statistic",      str(mv.get("ks","N/A")),  "Rank separation; target > 0.30"),
        ("Brier Score",       str(mv.get("brier","N/A")),"Calibration quality; good < 0.25"),
        ("PSI",               str(mv.get("psi","N/A")), "Population stability; stable < 0.10"),
        ("Governance Status", mv.get("status","PASS"),  "PASS = meets actuarial governance standards"),
    ], st))
    story.append(Spacer(1, 0.15*cm))
    auc = mv.get("auc", 0)
    auc_ok = auc > 0.80
    if auc >= 0.99:
        auc_comment = (
            f"The model achieves a near-perfect AUC of {auc:.4f}, indicating exceptional "
            f"discriminatory power between high and low risk policies. This level of "
            f"performance is above the 0.90 'excellent' threshold and supports its use "
            f"in risk-based pricing and underwriting triage decisions."
        )
    elif auc >= 0.90:
        auc_comment = (
            f"AUC of {auc:.4f} indicates excellent model discrimination, well above the "
            f"0.80 governance threshold. The model reliably separates high-risk from "
            f"low-risk policies and is suitable for regulatory capital modelling."
        )
    else:
        auc_comment = (
            f"AUC of {auc:.4f} {'meets' if auc_ok else 'falls below'} the 0.80 governance "
            f"threshold. {'The model is acceptable for current use.' if auc_ok else 'Model retraining with enriched features is recommended before regulatory submission.'}"
        )
    story.append(_callout(auc_comment, st,
                          _LGREEN if auc_ok else _LRED, _GREEN if auc_ok else _RED))
    story.append(Spacer(1, 0.2*cm))

    # Feature importance table
    fi_list = r.get("feature_importance", [])
    if fi_list:
        fi = pd.DataFrame(fi_list) if isinstance(fi_list, list) else fi_list
        story.append(Paragraph("XGBoost Feature Importance", st["h2"]))
        story.append(Paragraph(
            "Feature importance reflects the relative contribution of each variable "
            "to the model's predictive power, measured by mean decrease in impurity "
            "across all trees. Higher values indicate stronger predictive signal. "
            "These should be treated as primary underwriting and pricing variables.",
            st["body"]))
        story.append(Spacer(1, 0.1*cm))
        if isinstance(fi, pd.DataFrame):
            fi_rows = fi.head(10).values.tolist()
        else:
            fi_rows = [[row.get("Feature",""), row.get("Importance",0)] for row in fi[:10]]
        fi_display = []
        total_imp = sum(float(r[1]) for r in fi_rows) or 1
        for i, row in enumerate(fi_rows, 1):
            imp = float(row[1])
            bar = "\u2588" * round(imp * 20) + "\u2591" * (20 - round(imp * 20))
            fi_display.append([
                str(i),
                str(row[0]),
                f"{imp:.4f}",
                f"{imp/total_imp*100:.1f}%",
                bar,
            ])
        story.append(_simple_table(
            fi_display,
            ["Rank","Feature","Importance","% of Total","Relative Weight"],
            [1.2*cm, 5*cm, 2.5*cm, 2.5*cm, 7.3*cm],
            st))
        story.append(Spacer(1, 0.1*cm))
        if fi_display:
            top_feat = fi_display[0][1]
            story.append(_callout(
                f"'{top_feat}' is the single most predictive feature. Variables with "
                f"high importance should receive priority weighting in underwriting "
                f"risk scoring and rate relativities. Features with near-zero importance "
                f"are candidates for removal to reduce model complexity.",
                st, _LBLUE, _BLUE))
    story.append(PageBreak())

    # ── 7. RISK DASHBOARD ────────────────────────────────────────
    _section_header("7. Risk Dashboard", st, story)
    story.append(Paragraph(
        "Five risk dimensions are scored on a 0\u201310 scale using actuarial, financial, "
        "and operational indicators. Scores represent a weighted composite of multiple "
        "sub-indicators normalised to a common scale. "
        "High risk (>6) requires immediate management action; "
        "Medium risk (3\u20136) warrants monitoring; "
        "Low risk (<3) is within acceptable tolerance.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    rd_rows_data = []
    drivers = {"insurance":"Claim freq & severity","market":"Rate & inflation",
               "credit":"Premium collections","operational":"Fraud & exceptions",
               "cat":"Natural peril exposure"}
    rd_scores = {}
    for key, label in [("insurance","Insurance"),("market","Market"),("credit","Credit"),
                       ("operational","Operational"),("cat","Catastrophe")]:
        val = rd.get(key, 0)
        rd_scores[label] = val
        lv  = "High" if val > 6 else "Medium" if val > 3 else "Low"
        bar = "\u2588" * round(val) + "\u2591" * (10 - round(val))
        rd_rows_data.append([label, f"{val:.2f}/10", bar, lv, drivers.get(key,"")])
    story.append(_simple_table(
        rd_rows_data,
        ["Risk Category","Score","Visual Bar","Level","Key Driver"],
        [3.5*cm, 2*cm, 4.5*cm, 2*cm, 6.4*cm],
        st, sev_col=3))
    story.append(Spacer(1, 0.2*cm))

    # Per-category commentary
    story.append(Paragraph("Risk Category Analysis", st["h2"]))
    rd_commentary = rd.get("commentary", {})
    cat_map = {"Insurance":"insurance","Market":"market","Credit":"credit",
               "Operational":"operational","Catastrophe":"cat"}
    for cat_label, cat_key in cat_map.items():
        comment = rd_commentary.get(cat_label, "")
        if comment:
            val = rd.get(cat_key, 0)
            lv  = "High" if val > 6 else "Medium" if val > 3 else "Low"
            f   = {  "High": _LRED,   "Medium": _LAMBER, "Low": _LGREEN}[lv]
            b   = {  "High": _RED,    "Medium": _AMBER,  "Low": _GREEN }[lv]
            story.append(Paragraph(f"{cat_label} Risk", st["h2"]))
            story.append(_callout(comment, st, f, b))
    story.append(PageBreak())

    # ── 8. FORECAST ASSESSMENT ───────────────────────────────────
    _section_header("8. Forecast Assessment", st, story)
    story.append(Paragraph(
        "Agent 4 aggregated the portfolio into a monthly time series and applied linear "
        "trend modelling with seasonal decomposition (Prophet model where available, "
        "linear fallback otherwise) to project claims and premium over 12 months with "
        "80% confidence intervals. The analysis covers YoY growth trends, pricing gap "
        "analysis, seasonal patterns, and product-level loss ratios.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    fc_lr = fa.get("fc_loss_ratio", 0)
    story.append(Paragraph("Forecast KPIs", st["h2"]))
    story.append(_kv_table([
        ("Next-Month Claims Forecast",  _inr(fa.get("next_claim",0)),  "AI time-series projection (80% CI)"),
        ("Next-Month Premium Forecast", _inr(fa.get("next_premium",0)),"AI time-series projection (80% CI)"),
        ("Forecast Loss Ratio",         _pct(fc_lr),                   "Forward-looking LR estimate"),
        ("Avg Claim Severity",          _inr(fa.get("avg_severity",0)),"Mean cost per claim event"),
        ("Claims YoY",  _pct(fa["claims_yoy"])  if isinstance(fa.get("claims_yoy"),float)  else "N/A","Year-on-year trend"),
        ("Premium YoY", _pct(fa["premium_yoy"]) if isinstance(fa.get("premium_yoy"),float) else "N/A","Year-on-year trend"),
    ], st))
    story.append(Spacer(1, 0.15*cm))
    fc_fill = _LGREEN if fc_lr < 80 else (_LAMBER if fc_lr < 100 else _LRED)
    fc_bdr  = _GREEN  if fc_lr < 80 else (_AMBER  if fc_lr < 100 else _RED)
    story.append(_callout(fa.get("interpretation",""), st, fc_fill, fc_bdr))
    story.append(Spacer(1, 0.2*cm))

    # YoY trend table
    yoy_rows = fa.get("yoy_rows", [])
    if yoy_rows:
        story.append(Paragraph("Year-on-Year Growth Trend (Last 12 Months)", st["h2"]))
        story.append(Paragraph(
            "The pricing gap column shows the difference between claims and premium growth. "
            "A positive gap means claims are growing faster than premium \u2014 a warning "
            "signal that requires rate action. A negative gap is favourable.",
            st["body"]))
        story.append(Spacer(1, 0.1*cm))
        story.append(_simple_table(
            yoy_rows,
            ["Month","Premium YoY","Claims YoY","Gap (pp)","Trend"],
            [3*cm, 3*cm, 3*cm, 2.5*cm, 7*cm],
            st))
        story.append(Spacer(1, 0.2*cm))

    # Seasonal table
    sea_rows = fa.get("sea_rows", [])
    if sea_rows:
        story.append(Paragraph("Seasonal Claims & Premium Index", st["h2"]))
        story.append(Paragraph(
            "Index of 100 represents the annual monthly average. Values above 110 indicate "
            "a peak period \u2014 typically associated with monsoon season, festive period, "
            "or natural peril events. Reserve adequacy should account for seasonal loading "
            "in peak months.",
            st["body"]))
        story.append(Spacer(1, 0.1*cm))
        story.append(_simple_table(
            sea_rows,
            ["Month","Claims Index","Premium Index","Assessment"],
            [3*cm, 3.5*cm, 3.5*cm, 8.5*cm],
            st))
        story.append(Spacer(1, 0.2*cm))

    # Product forecast table
    prod_fc_rows = fa.get("prod_fc_rows", [])
    if prod_fc_rows:
        story.append(Paragraph("Product Loss Ratio Analysis", st["h2"]))
        story.append(_simple_table(
            prod_fc_rows,
            ["Product","Total Premium","Total Claims","Loss Ratio","Status"],
            [3.5*cm, 3.5*cm, 3.5*cm, 2.5*cm, 5.4*cm],
            st))
    story.append(PageBreak())

    # ── 9. STRESS TESTING ────────────────────────────────────────
    _section_header("9. Stress Testing Assessment", st, story)
    story.append(Paragraph(
        "Agent 5 applies five regulatory-grade stress scenarios to the portfolio, "
        "ranging from a mild claims shock (S1: +20%) to a full catastrophic event "
        "(S5: +60% claims, +30% market risk, +50% catastrophe exposure). "
        "The portfolio must maintain positive remaining capital under all scenarios. "
        "Solvency below 75% under any scenario triggers a capital adequacy review.",
        st["body"]))
    story.append(Spacer(1, 0.1*cm))
    story.append(Paragraph(f"Primary Scenario: {sa.get('scenario','')}", st["h2"]))
    story.append(_kv_table([
        ("Active Scenario",           sa.get("scenario",""),          "Primary stress test applied"),
        ("Stressed Combined Ratio",   _pct(sa.get("combined_ratio",0)),"Post-shock CR"),
        ("Solvency Under Stress",     _pct(sa.get("solvency",0)),     "Post-shock solvency ratio"),
        ("Capital Consumed",          _inr(sa.get("capital_consumed",0)),"Capital eroded by scenario"),
        ("Remaining Capital",         _inr(sa.get("remaining_capital",0)),"Post-stress capital buffer"),
    ], st))
    story.append(Spacer(1, 0.15*cm))
    stress_sol = sa.get("solvency", 100)
    if stress_sol >= 90:
        st_comment = (
            f"Under {sa.get('scenario','')}, the portfolio maintains a solvency ratio of "
            f"{stress_sol:.1f}%, demonstrating strong capital resilience. The remaining "
            f"capital of {_inr(sa.get('remaining_capital',0))} provides a comfortable "
            f"buffer above regulatory minimum requirements."
        )
    elif stress_sol >= 75:
        st_comment = (
            f"Under {sa.get('scenario','')}, solvency ratio of {stress_sol:.1f}% is above "
            f"the 75% prudential threshold but leaves limited headroom. Management should "
            f"review reinsurance adequacy and consider strengthening the capital position "
            f"before the next stress test cycle."
        )
    else:
        st_comment = (
            f"Capital stress identified under {sa.get('scenario','')}. Solvency ratio of "
            f"{stress_sol:.1f}% is below the 75% prudential threshold. Immediate capital "
            f"remediation is required: explore quota-share reinsurance placement, "
            f"excess of loss programme review, or equity injection."
        )
    story.append(_callout(st_comment, st,
                          _LAMBER if is_sol else _LRED, _AMBER if is_sol else _RED))

    if all_sc:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("All Scenarios \u2014 Comparative Analysis", st["h2"]))
        story.append(Paragraph(
            "The table below compares Combined Ratio and Solvency Ratio across all five "
            "scenarios. Scenarios where solvency falls below 75% are highlighted in red "
            "and require management action.",
            st["body"]))
        story.append(Spacer(1, 0.1*cm))
        sc_rows = []
        for sc in all_sc:
            scr  = sc.get("Stressed CR (%)", 0)
            sol_ = sc.get("Solvency Ratio (%)", 0)
            cap_ = sc.get("Capital Consumed", 0)
            sht_ = sc.get("Shortfall", 0)
            sc_rows.append([
                sc.get("Label",""),
                f"{scr:.1f}%",
                f"{sol_:.1f}%",
                f"\u20b9{cap_:,.0f}",
                f"\u20b9{sht_:,.0f}" if sht_ > 0 else "\u2014",
            ])
        story.append(_simple_table(
            sc_rows,
            ["Scenario","Stressed CR","Solvency","Capital Consumed","Shortfall"],
            [5.5*cm, 2.5*cm, 2.5*cm, 4*cm, 3.9*cm],
            st))
    story.append(PageBreak())

    # ── 10. CHART INTERPRETATIONS ────────────────────────────────
    _section_header("10. Chart Interpretations", st, story)
    story.append(Paragraph(
        "The following interpretations summarise the key takeaways from each "
        "analytical chart generated by the CRIP platform. These are derived "
        "automatically from the underlying data and should be read alongside "
        "the quantitative tables in the preceding sections.",
        st["body"]))
    story.append(Spacer(1, 0.1*cm))
    chart_map = {
        "loss_ratio":         "Loss Ratio by Product",
        "profitability":      "Portfolio Profitability",
        "feature_importance": "Feature Importance (XGBoost)",
        "forecast":           "Claims & Premium Forecast",
        "stress_testing":     "Stress Testing Scenarios",
    }
    for key, label in chart_map.items():
        val = cc.get(key, "")
        if val:
            story.append(Paragraph(label, st["h2"]))
            story.append(_callout(val, st, _LBLUE, _BLUE))
    story.append(PageBreak())

    # ── 11. FINDINGS REGISTER ────────────────────────────────────
    _section_header("11. Validation Findings Register", st, story)
    story.append(Paragraph(
        "The following findings were identified by the CRIP multi-agent analysis. "
        "Each finding is automatically derived from the pipeline outputs and assigned "
        "a severity classification with an actionable recommendation. "
        "Severity levels: High = immediate action required, "
        "Medium = action within the current quarter, Low = routine monitoring.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    if fr:
        fr_data = [[
            f.get("ID",""), f.get("Finding",""),
            f.get("Severity",""), f.get("Recommendation","")
        ] for f in fr]
        story.append(_simple_table(
            fr_data,
            ["ID","Finding","Severity","Recommendation"],
            [1.5*cm, 5.5*cm, 2*cm, 9.4*cm],
            st, sev_col=2))
    story.append(PageBreak())

    # ── 12. MANAGEMENT ACTION PLAN ───────────────────────────────
    _section_header("12. Management Action Plan", st, story)
    story.append(Paragraph(
        "The following priority actions are derived from the integrated analysis "
        "across all five CRIP agents. Each action is directly traceable to a specific "
        "finding in the Validation Findings Register. Actions are ranked by risk "
        "significance and should be assigned to named owners with target completion "
        "dates within the next quarterly review cycle.",
        st["body"]))
    story.append(Spacer(1, 0.15*cm))
    for i, action in enumerate(ma, 1):
        story.append(_bullet(f"Priority {i}: {action}", st))
    story.append(PageBreak())

    # ── 13. ACTUARIAL OPINION ────────────────────────────────────
    _section_header("13. Actuarial Opinion & Final Conclusion", st, story)
    story.append(Paragraph("Independent Actuarial Opinion", st["h2"]))
    story.append(_callout(r.get("actuarial_opinion",""), st, _LBLUE, _BLUE))
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph("Final Conclusion", st["h2"]))
    rating_data = [[
        Paragraph("Overall Portfolio Rating:", ParagraphStyle(
            "_rl", parent=st["body"], fontName="Helvetica-Bold", fontSize=10, textColor=_BLACK)),
        Paragraph(rat, ParagraphStyle(
            "_rv", parent=st["body"], fontName="Helvetica-Bold", fontSize=14,
            textColor=_GREEN if is_sol else _RED)),
        Paragraph(f"Health Score: {hs}/100  |  Outlook: {outlook}", ParagraphStyle(
            "_ro", parent=st["body"], fontSize=9, textColor=_GREY)),
    ]]
    rt = Table(rating_data, colWidths=[5*cm, 3*cm, 10.4*cm])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), sol_fill),
        ("GRID",          (0,0), (-1,-1), 0, _WHITE),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LINEAFTER",     (0,0), (1,-1),  0.5, sol_border),
    ]))
    story.append(rt)
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(r.get("final_conclusion",""), st["body"]))
    story.append(Spacer(1, 0.1*cm))
    for cb in conc_bullets:
        story.append(_bullet(cb, st))
    story.append(PageBreak())

    # ── 14. DISCLAIMERS ──────────────────────────────────────────
    _section_header("14. Disclaimers & Methodology", st, story)
    story.append(Paragraph("Methodology Notes", st["h2"]))
    for note in [
        "Data Governance (Agent 1): IQR outlier clipping; Isolation Forest (contamination=5%); "
        "median/mode imputation; columns >80% missing or \u22641 unique value auto-dropped.",
        "Pricing Analysis (Agent 2): LR = Claims/Premium; ER = Expenses/Premium; CR = LR+ER. "
        "Tiers: Excellent <80%, Good 80\u201395%, Marginal 95\u2013100%, Loss-Making >100%.",
        "Risk Intelligence (Agent 3): XGBoost (100 estimators, depth 4, lr 0.1) for claim "
        "prediction; Monte Carlo (1,000 paths) for VaR/CVaR; feature importance = mean "
        "decrease in impurity across all trees.",
        "Forecasting (Agent 4): Prophet model with yearly seasonality and 80% CI; linear "
        "trend fallback; monthly aggregation with seasonal decomposition.",
        "Stress Testing (Agent 5): S1\u2013S5 from +20% claims to +60% claims / +30% market "
        "/ +50% CAT exposure. Capital adequacy = remaining capital / initial capital reserve.",
    ]:
        story.append(_bullet(note, st))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Disclaimers", st["h2"]))
    for disc in [
        "This report is generated automatically by the CRIP AI platform and is intended "
        "solely for internal use. It does not constitute formal actuarial certification, "
        "legal advice, or investment guidance.",
        "All financial projections and risk scores are model-based estimates subject to "
        "inherent uncertainty. Actual results may differ materially from forward-looking "
        "statements.",
        "The XGBoost predictive model produces probabilistic outputs and should be validated "
        "by a qualified actuary before use in regulatory capital submissions or IRDAI filings.",
        "Currency values are in Indian Rupees (\u20b9). No adjustments for reinsurance "
        "recoverables, tax, or inflation have been applied.",
        f"Report generated: {report_date}. Data quality is a function of the input dataset "
        f"provided to CRIP.",
    ]:
        story.append(_bullet(disc, st))

    # ── BUILD ────────────────────────────────────────────────────
    doc.build(story,
              onFirstPage=on_page,
              onLaterPages=on_page)

    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes

def run_report_pipeline(
    gov_results,
    pricing_results,
    risk_results,
    forecast_results,
    stress_results
):
    health_score     = calculate_health_score(gov_results, pricing_results, risk_results, forecast_results, stress_results)
    portfolio_rating = assign_portfolio_rating(health_score)
    portfolio_outlook = assign_portfolio_outlook(
        health_score,
        stress_results.get("is_solvent", True),
        stress_results.get("solvency_ratio", 0)
    )
    score_breakdown  = get_score_breakdown(gov_results, pricing_results, risk_results, forecast_results, stress_results)

    executive_summary  = generate_executive_summary(gov_results, pricing_results, risk_results, forecast_results, stress_results)
    actuarial_opinion  = generate_actuarial_opinion(pricing_results, risk_results, stress_results)
    dashboard          = generate_dashboard_metrics(pricing_results, risk_results, forecast_results, stress_results)
    metadata           = generate_metadata(gov_results, 12, stress_results)
    data_validation    = generate_data_validation_section(gov_results)
    pricing_assessment = generate_pricing_assessment(pricing_results)
    capital_validation = generate_capital_validation(risk_results)
    model_validation   = generate_model_validation(risk_results)
    risk_dashboard     = generate_risk_dashboard(risk_results["df_risk"])
    forecast_assessment= generate_forecast_assessment(forecast_results)
    stress_assessment  = generate_stress_assessment(stress_results)
    management_actions = generate_management_actions(pricing_results, risk_results, stress_results, forecast_results)
    chart_commentary   = generate_chart_commentary(pricing_results, risk_results, forecast_results, stress_results)
    findings           = generate_key_findings(gov_results, pricing_results, risk_results, forecast_results, stress_results)
    findings_register  = generate_findings_register(gov_results, pricing_results, risk_results, stress_results)
    final_conclusion   = generate_final_conclusion(health_score, portfolio_rating, risk_results, pricing_results, stress_results)
    business_insights  = generate_business_insights(pricing_results, risk_results, forecast_results)

    all_sc = stress_results.get("all_scenarios", pd.DataFrame())

    # Data-driven conclusion bullets
    sol = risk_results["portfolio_metrics"]["Solvency_Ratio"]
    conclusion_bullets = [
        f"The actuarial assessment indicates the portfolio remains financially "
        f"{'strong' if health_score >= 80 else 'stable' if health_score >= 60 else 'under pressure'} "
        f"with a Health Score of {health_score}/100.",
        f"Capital adequacy is {'robust' if sol > 200 else 'satisfactory' if sol > 150 else 'borderline'} "
        f"at {sol:.1f}% and stress testing "
        f"{'demonstrates resilience' if stress_results['is_solvent'] else 'reveals a capital shortfall'} "
        f"under the selected scenario.",
        f"The portfolio is "
        f"{'suitable for continued underwriting' if health_score >= 70 else 'under management review'} "
        f"with ongoing monitoring of market, catastrophe, and operational risks.",
    ]

    report_dict = {
        "metadata":           metadata,
        "health_score":       health_score,
        "portfolio_rating":   portfolio_rating,
        "executive_summary":  executive_summary,
        "key_findings":       findings,
        "findings_register":  findings_register,
        "data_validation":    data_validation,
        "pricing_assessment": pricing_assessment,
        "capital_validation": capital_validation,
        "model_validation":   model_validation,
        "risk_dashboard":     risk_dashboard,
        "forecast_assessment":forecast_assessment,
        "stress_assessment":  stress_assessment,
        "management_actions": management_actions,
        "actuarial_opinion":  actuarial_opinion,
        "chart_commentary":   chart_commentary,
        "dashboard":          dashboard,
        "final_conclusion":   final_conclusion,
        "all_scenarios":      all_sc.to_dict("records") if not all_sc.empty else [],
        "is_solvent":         stress_results.get("is_solvent", True),
        "portfolio_outlook":  portfolio_outlook,
        "business_insights":  business_insights,
        "conclusion_bullets": conclusion_bullets,
        "score_breakdown":    score_breakdown,
        "feature_importance": risk_results.get("feature_importance", pd.DataFrame()).to_dict("records") if not risk_results.get("feature_importance", pd.DataFrame()).empty else [],
    }

    try:
        report_dict["report_bytes"]    = create_pdf_report(report_dict)
        report_dict["report_filename"] = f"CRIP_Actuarial_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_dict["report_mime"]     = "application/pdf"
    except Exception as e:
        report_dict["report_bytes"]    = None
        report_dict["report_filename"] = None
        report_dict["report_mime"]     = None
        report_dict["report_error"]    = str(e)

    return report_dict


# ─────────────────────────────────────────────────────────────────
# Report DataFrame  (unchanged)
# ─────────────────────────────────────────────────────────────────
def create_report_dataframe(report_results):
    rows = []
    rows.append(["Portfolio Rating", report_results["portfolio_rating"]])
    rows.append(["Health Score",     report_results["health_score"]])
    for i, finding in enumerate(report_results["key_findings"], 1):
        rows.append([f"Finding {i}", finding])
    return pd.DataFrame(rows, columns=["Metric", "Value"])