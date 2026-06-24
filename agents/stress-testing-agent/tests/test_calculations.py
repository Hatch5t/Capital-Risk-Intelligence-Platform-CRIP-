"""
Unit tests for CRIP Stress Testing Agent — calculations module.
Run with: pytest tests/
"""

import pytest
from utils.scenarios import apply_scenario, apply_all_scenarios, SCENARIO_CONFIG
from utils.calculations import (
    compute_base_metrics,
    compute_stressed_metrics,
    compute_capital_impact,
    compute_solvency,
    compute_product_vulnerability,
    compute_all_scenario_comparison,
)

SAMPLE_PORTFOLIO = {
    "claim_amount":    850.0,
    "written_premium": 1200.0,
    "total_expense":   220.0,
    "capital_reserve": 500.0,
    "insurance_risk":  42,
    "market_risk":     35,
    "credit_risk":     28,
    "operational_risk": 22,
    "catastrophe_risk": 55,
    "region":          "All",
    "product_type":    "All",
}


# ── Base metrics ───────────────────────────────────────────────────────────────

class TestBaseMetrics:
    def test_loss_ratio(self):
        base = compute_base_metrics(SAMPLE_PORTFOLIO)
        assert abs(base["loss_ratio"] - 70.83) < 0.1

    def test_expense_ratio(self):
        base = compute_base_metrics(SAMPLE_PORTFOLIO)
        assert abs(base["expense_ratio"] - 18.33) < 0.1

    def test_combined_ratio(self):
        base = compute_base_metrics(SAMPLE_PORTFOLIO)
        assert abs(base["combined_ratio"] - 89.17) < 0.1

    def test_underwriting_profit(self):
        base = compute_base_metrics(SAMPLE_PORTFOLIO)
        assert base["underwriting_profit"] == 130.0

    def test_zero_premium(self):
        p = {**SAMPLE_PORTFOLIO, "written_premium": 0}
        base = compute_base_metrics(p)
        assert base["loss_ratio"] == 0.0
        assert base["expense_ratio"] == 0.0


# ── Scenarios ──────────────────────────────────────────────────────────────────

class TestScenarios:
    def test_s1_claim_multiplier(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s1")
        assert abs(sc["stressed_claim"] - 850 * 1.20) < 0.01

    def test_s2_claim_multiplier(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s2")
        assert abs(sc["stressed_claim"] - 850 * 1.40) < 0.01

    def test_s3_no_claim_change(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s3")
        assert sc["stressed_claim"] == SAMPLE_PORTFOLIO["claim_amount"]

    def test_s3_market_multiplier(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s3")
        assert abs(sc["stressed_mkt"] - 35 * 1.25) < 0.01

    def test_s4_combined(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s4")
        assert abs(sc["stressed_claim"] - 850 * 1.40) < 0.01
        assert abs(sc["stressed_mkt"] - 35 * 1.25) < 0.01

    def test_s5_catastrophe(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s5")
        assert sc["claim_mult"] == 1.60
        assert sc["cat_mult"] == 1.50

    def test_risk_score_capped_at_100(self):
        high_risk = {**SAMPLE_PORTFOLIO, "catastrophe_risk": 80}
        sc = apply_scenario(high_risk, "s5")
        assert sc["stressed_cat"] <= 100

    def test_all_scenarios_returns_five(self):
        all_sc = apply_all_scenarios(SAMPLE_PORTFOLIO)
        assert len(all_sc) == 5

    def test_all_scenario_ids(self):
        all_sc = apply_all_scenarios(SAMPLE_PORTFOLIO)
        assert set(all_sc.keys()) == {"s1", "s2", "s3", "s4", "s5"}


# ── Stressed metrics ───────────────────────────────────────────────────────────

class TestStressedMetrics:
    def setup_method(self):
        self.sc = apply_scenario(SAMPLE_PORTFOLIO, "s2")  # Claims +40%

    def test_stressed_lr_higher_than_base(self):
        base    = compute_base_metrics(SAMPLE_PORTFOLIO)
        stress  = compute_stressed_metrics(SAMPLE_PORTFOLIO, self.sc)
        assert stress["stressed_lr"] > base["loss_ratio"]

    def test_lr_delta_positive_for_claim_shock(self):
        stress = compute_stressed_metrics(SAMPLE_PORTFOLIO, self.sc)
        assert stress["lr_delta"] > 0

    def test_uw_profit_decreases_under_stress(self):
        base   = compute_base_metrics(SAMPLE_PORTFOLIO)
        stress = compute_stressed_metrics(SAMPLE_PORTFOLIO, self.sc)
        assert stress["stressed_uw"] < base["underwriting_profit"]


# ── Capital impact ─────────────────────────────────────────────────────────────

class TestCapitalImpact:
    def test_total_consumed_is_sum_of_parts(self):
        sc      = apply_scenario(SAMPLE_PORTFOLIO, "s4")
        stress  = compute_stressed_metrics(SAMPLE_PORTFOLIO, sc)
        cap     = compute_capital_impact(SAMPLE_PORTFOLIO, stress)
        assert abs(cap["total_consumed"] - (cap["claim_impact"] + cap["market_impact"] + cap["cat_impact"])) < 0.01

    def test_claim_impact_zero_when_uw_positive(self):
        # Use scenario where premium still > stressed claims
        sc      = apply_scenario(SAMPLE_PORTFOLIO, "s1")
        stress  = compute_stressed_metrics(SAMPLE_PORTFOLIO, sc)
        cap     = compute_capital_impact(SAMPLE_PORTFOLIO, stress)
        assert cap["claim_impact"] == 0.0 if stress["stressed_uw"] >= 0 else cap["claim_impact"] >= 0

    def test_no_negative_impacts(self):
        sc      = apply_scenario(SAMPLE_PORTFOLIO, "s5")
        stress  = compute_stressed_metrics(SAMPLE_PORTFOLIO, sc)
        cap     = compute_capital_impact(SAMPLE_PORTFOLIO, stress)
        assert cap["claim_impact"] >= 0
        assert cap["market_impact"] >= 0
        assert cap["cat_impact"] >= 0


# ── Solvency ───────────────────────────────────────────────────────────────────

class TestSolvency:
    def test_solvency_ratio_100_when_no_stress(self):
        no_stress = {"claim_impact": 0, "market_impact": 0, "cat_impact": 0, "total_consumed": 0}
        sol = compute_solvency(SAMPLE_PORTFOLIO, no_stress)
        assert sol["solvency_ratio"] == 100.0

    def test_shortfall_zero_when_solvent(self):
        no_stress = {"claim_impact": 0, "market_impact": 0, "cat_impact": 0, "total_consumed": 0}
        sol = compute_solvency(SAMPLE_PORTFOLIO, no_stress)
        assert sol["shortfall"] == 0.0

    def test_shortfall_positive_when_capital_exhausted(self):
        huge_impact = {"claim_impact": 600, "market_impact": 0, "cat_impact": 0, "total_consumed": 600}
        sol = compute_solvency(SAMPLE_PORTFOLIO, huge_impact)
        assert sol["shortfall"] > 0
        assert not sol["is_solvent"]

    def test_remaining_capital_calculation(self):
        impact = {"claim_impact": 100, "market_impact": 50, "cat_impact": 25, "total_consumed": 175}
        sol = compute_solvency(SAMPLE_PORTFOLIO, impact)
        assert sol["remaining_capital"] == 500 - 175


# ── Product vulnerability ──────────────────────────────────────────────────────

class TestProductVulnerability:
    def setup_method(self):
        sc = apply_scenario(SAMPLE_PORTFOLIO, "s5")
        self.stress  = compute_stressed_metrics(SAMPLE_PORTFOLIO, sc)
        self.capital = compute_capital_impact(SAMPLE_PORTFOLIO, self.stress)

    def test_returns_six_products(self):
        df = compute_product_vulnerability(SAMPLE_PORTFOLIO, self.stress, self.capital)
        assert len(df) == 6

    def test_vulnerability_labels_valid(self):
        df = compute_product_vulnerability(SAMPLE_PORTFOLIO, self.stress, self.capital)
        assert set(df["Vulnerability"].unique()).issubset({"High", "Medium", "Low"})

    def test_claim_exposures_sum_to_total(self):
        df = compute_product_vulnerability(SAMPLE_PORTFOLIO, self.stress, self.capital)
        assert abs(df["Claim Exposure (₹ Cr)"].sum() - self.stress["stressed_claim"]) < 1.0

    def test_sorted_by_vulnerability_score_desc(self):
        df = compute_product_vulnerability(SAMPLE_PORTFOLIO, self.stress, self.capital)
        scores = df["Vulnerability Score"].tolist()
        assert scores == sorted(scores, reverse=True)


# ── All-scenario comparison ────────────────────────────────────────────────────

class TestAllScenarioComparison:
    def test_returns_five_rows(self):
        df = compute_all_scenario_comparison(SAMPLE_PORTFOLIO)
        assert len(df) == 5

    def test_stressed_cr_always_gte_base(self):
        df = compute_all_scenario_comparison(SAMPLE_PORTFOLIO)
        assert (df["Stressed CR (%)"] >= df["Base CR (%)"]).all()

    def test_s5_has_highest_stressed_cr(self):
        df = compute_all_scenario_comparison(SAMPLE_PORTFOLIO)
        s5_cr = df[df["Scenario"] == "S5"]["Stressed CR (%)"].values[0]
        assert s5_cr == df["Stressed CR (%)"].max()
