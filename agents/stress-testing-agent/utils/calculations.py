"""
Core actuarial and risk calculations for the Stress Testing Agent.

All monetary values are in ₹ Crores (Cr).
Ratios are expressed as percentages (e.g. 85.0 means 85%).
"""

import pandas as pd
from utils.scenarios import apply_scenario, apply_all_scenarios

PRODUCT_WEIGHTS = {
    "Motor":    0.30,
    "Health":   0.25,
    "Property": 0.20,
    "Travel":   0.10,
    "Fire":     0.08,
    "Marine":   0.07,
}


# ── Base (pre-stress) metrics ──────────────────────────────────────────────────

def compute_base_metrics(portfolio: dict) -> dict:
    """
    Compute baseline (unstressed) portfolio metrics.

    Returns:
        loss_ratio, expense_ratio, combined_ratio, underwriting_profit,
        claim_severity (avg claim per policy, if claim_count present).
    """
    premium = portfolio["written_premium"]
    claim   = portfolio["claim_amount"]
    expense = portfolio["total_expense"]

    loss_ratio         = (claim / premium * 100) if premium > 0 else 0.0
    expense_ratio      = (expense / premium * 100) if premium > 0 else 0.0
    combined_ratio     = loss_ratio + expense_ratio
    underwriting_profit = premium - claim - expense

    return {
        "loss_ratio":          round(loss_ratio, 2),
        "expense_ratio":       round(expense_ratio, 2),
        "combined_ratio":      round(combined_ratio, 2),
        "underwriting_profit": round(underwriting_profit, 2),
    }


# ── Stressed metrics ───────────────────────────────────────────────────────────

def compute_stressed_metrics(portfolio: dict, scenario: dict) -> dict:
    """
    Compute stressed financial metrics from a scenario dict
    (output of apply_scenario).

    Returns:
        stressed_claim, stressed_lr, stressed_cr, stressed_uw,
        lr_delta, cr_delta, uw_delta.
    """
    premium         = portfolio["written_premium"]
    expense         = portfolio["total_expense"]
    base            = compute_base_metrics(portfolio)
    stressed_claim  = scenario["stressed_claim"]

    stressed_lr = (stressed_claim / premium * 100) if premium > 0 else 0.0
    stressed_cr = stressed_lr + base["expense_ratio"]
    stressed_uw = premium - stressed_claim - expense

    return {
        "stressed_claim": round(stressed_claim, 2),
        "stressed_lr":    round(stressed_lr, 2),
        "stressed_cr":    round(stressed_cr, 2),
        "stressed_uw":    round(stressed_uw, 2),
        "lr_delta":       round(stressed_lr - base["loss_ratio"], 2),
        "cr_delta":       round(stressed_cr - base["combined_ratio"], 2),
        "uw_delta":       round(stressed_uw - base["underwriting_profit"], 2),
    }


# ── Capital impact ─────────────────────────────────────────────────────────────

def compute_capital_impact(portfolio: dict, stressed_metrics: dict) -> dict:
    """
    Estimate capital consumed under stress across three channels:
      1. Claim losses (UW loss becomes capital drain)
      2. Market risk impact (% of capital at risk from stressed mkt score)
      3. Catastrophe risk impact (% of capital at risk from stressed cat score)

    The weighting coefficients (0.40, 0.25) represent typical capital
    sensitivity assumptions — adjust to match your internal capital model.

    Returns:
        claim_impact, market_impact, cat_impact, total_consumed.
    """
    capital = portfolio["capital_reserve"]

    claim_impact  = max(0.0, -stressed_metrics["stressed_uw"])
    market_impact = (portfolio["market_risk"] / 100) * capital * 0.40
    cat_impact    = (portfolio["catastrophe_risk"] / 100) * capital * 0.25
    total         = claim_impact + market_impact + cat_impact

    return {
        "claim_impact":  round(claim_impact, 2),
        "market_impact": round(market_impact, 2),
        "cat_impact":    round(cat_impact, 2),
        "total_consumed": round(total, 2),
    }


# ── Solvency ───────────────────────────────────────────────────────────────────

def compute_solvency(portfolio: dict, capital_impact: dict) -> dict:
    """
    Derive post-stress solvency position.

    Solvency ratio = remaining capital / original capital * 100.
    Shortfall is positive when remaining capital is negative.

    Returns:
        remaining_capital, solvency_ratio, shortfall, is_solvent.
    """
    capital         = portfolio["capital_reserve"]
    remaining       = capital - capital_impact["total_consumed"]
    solvency_ratio  = (remaining / capital * 100) if capital > 0 else 0.0
    shortfall       = max(0.0, -remaining)

    return {
        "remaining_capital": round(remaining, 2),
        "solvency_ratio":    round(solvency_ratio, 2),
        "shortfall":         round(shortfall, 2),
        "is_solvent":        remaining >= 0,
    }


# ── Product vulnerability ──────────────────────────────────────────────────────

def compute_product_vulnerability(
    portfolio: dict,
    stressed_metrics: dict,
    capital_impact: dict,
) -> pd.DataFrame:
    """
    Distribute stressed exposures across the 6 insurance products using
    predefined weights, then score each product's vulnerability.

    Vulnerability score = normalised claim exposure + normalised capital at risk.
    Thresholds: High > 55, Medium > 30, Low ≤ 30.

    Returns a DataFrame with columns:
        Product, Claim Exposure (₹ Cr), Capital At Risk (₹ Cr),
        Vulnerability Score, Vulnerability.
    """
    rows = []
    for product, weight in PRODUCT_WEIGHTS.items():
        claim_exp = stressed_metrics["stressed_claim"] * weight
        cap_at_risk = capital_impact["total_consumed"] * weight
        premium = portfolio["written_premium"]
        capital = portfolio["capital_reserve"]

        vuln_score = (
            (claim_exp / premium * 100 if premium > 0 else 0)
            + (cap_at_risk / capital * 50 if capital > 0 else 0)
        )

        if vuln_score > 55:
            vuln_label = "High"
        elif vuln_score > 30:
            vuln_label = "Medium"
        else:
            vuln_label = "Low"

        rows.append({
            "Product":               product,
            "Claim Exposure (₹ Cr)": round(claim_exp, 1),
            "Capital At Risk (₹ Cr)": round(cap_at_risk, 1),
            "Vulnerability Score":   round(vuln_score, 1),
            "Vulnerability":         vuln_label,
        })

    df = pd.DataFrame(rows).sort_values("Vulnerability Score", ascending=False)
    return df.reset_index(drop=True)


# ── All-scenario comparison helper ────────────────────────────────────────────

def compute_all_scenario_comparison(portfolio: dict) -> pd.DataFrame:
    """
    Run all 5 scenarios and return a summary DataFrame for comparison charts.

    Returns columns: Scenario, Label, Stressed CR, Stressed LR,
    Capital Consumed, Solvency Ratio, Shortfall.
    """
    base = compute_base_metrics(portfolio)
    rows = []
    for sid, sc in apply_all_scenarios(portfolio).items():
        stress  = compute_stressed_metrics(portfolio, sc)
        capital = compute_capital_impact(portfolio, stress)
        solvency = compute_solvency(portfolio, capital)
        rows.append({
            "Scenario":         sid.upper(),
            "Label":            sc["label"],
            "Base CR (%)":      base["combined_ratio"],
            "Stressed CR (%)":  stress["stressed_cr"],
            "Stressed LR (%)":  stress["stressed_lr"],
            "Capital Consumed": capital["total_consumed"],
            "Solvency Ratio":   solvency["solvency_ratio"],
            "Shortfall":        solvency["shortfall"],
        })
    return pd.DataFrame(rows)
