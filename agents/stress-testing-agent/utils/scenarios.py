"""
Stress scenario definitions and multiplier application.
Each scenario maps to a dict of multipliers applied to portfolio inputs.
"""

SCENARIO_CONFIG = {
    "s1": {
        "label":        "Scenario 1 — Claims +20%",
        "description":  "Moderate shock: claims increase by 20%",
        "claim_mult":   1.20,
        "mkt_mult":     1.00,
        "cat_mult":     1.00,
    },
    "s2": {
        "label":        "Scenario 2 — Claims +40%",
        "description":  "Severe shock: claims increase by 40%",
        "claim_mult":   1.40,
        "mkt_mult":     1.00,
        "cat_mult":     1.00,
    },
    "s3": {
        "label":        "Scenario 3 — Market Risk +25%",
        "description":  "Market stress: market risk score increases by 25%",
        "claim_mult":   1.00,
        "mkt_mult":     1.25,
        "cat_mult":     1.00,
    },
    "s4": {
        "label":        "Scenario 4 — Combined Shock",
        "description":  "Combined: claims +40% and market risk +25%",
        "claim_mult":   1.40,
        "mkt_mult":     1.25,
        "cat_mult":     1.00,
    },
    "s5": {
        "label":        "Scenario 5 — Catastrophic Event",
        "description":  "Catastrophe (Flood / Cyclone / Earthquake): extreme multi-risk shock",
        "claim_mult":   1.60,
        "mkt_mult":     1.30,
        "cat_mult":     1.50,
    },
}


def apply_scenario(portfolio: dict, scenario_id: str) -> dict:
    """
    Apply a stress scenario to the raw portfolio inputs.

    Args:
        portfolio: dict with keys matching CRIP portfolio fields.
        scenario_id: one of 's1' .. 's5'.

    Returns:
        dict with stressed values for claim_amount, market_risk,
        catastrophe_risk, and the original multipliers used.
    """
    cfg = SCENARIO_CONFIG[scenario_id]

    stressed_claim = portfolio["claim_amount"] * cfg["claim_mult"]
    stressed_mkt   = min(100, portfolio["market_risk"] * cfg["mkt_mult"])
    stressed_cat   = min(100, portfolio["catastrophe_risk"] * cfg["cat_mult"])

    return {
        "scenario_id":      scenario_id,
        "label":            cfg["label"],
        "claim_mult":       cfg["claim_mult"],
        "mkt_mult":         cfg["mkt_mult"],
        "cat_mult":         cfg["cat_mult"],
        "stressed_claim":   stressed_claim,
        "stressed_mkt":     stressed_mkt,
        "stressed_cat":     stressed_cat,
    }


def apply_all_scenarios(portfolio: dict) -> dict:
    """
    Apply all 5 scenarios and return results keyed by scenario id.
    Useful for comparison charts.
    """
    return {sid: apply_scenario(portfolio, sid) for sid in SCENARIO_CONFIG}
