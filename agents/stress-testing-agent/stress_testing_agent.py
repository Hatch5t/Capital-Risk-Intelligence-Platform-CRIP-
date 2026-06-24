"""
CRIP - Capital & Risk Intelligence Platform
Agent 5: Stress Testing Agent
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from utils.scenarios import apply_scenario, SCENARIO_CONFIG
from utils.calculations import (
    compute_base_metrics,
    compute_stressed_metrics,
    compute_capital_impact,
    compute_solvency,
    compute_product_vulnerability,
)
from utils.formatting import fmt_cr, fmt_pct, fmt_ratio
from components.charts import (
    render_scenario_comparison_chart,
    render_solvency_bars,
    render_capital_waterfall,
    render_product_vulnerability_chart,
)

st.set_page_config(
    page_title="CRIP | Stress Testing Agent",
    page_icon="⚡",
    layout="wide",
)

# ── Styling ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stMetric label  { font-size: 12px !important; color: #6b7280; }
    .stMetric value  { font-size: 22px !important; }
    .section-header  { font-size: 13px; font-weight: 600; color: #374151;
                       text-transform: uppercase; letter-spacing: 0.06em;
                       margin-bottom: 0.5rem; margin-top: 1.5rem; }
    .alert-danger    { background:#FEF2F2; border-left:4px solid #DC2626;
                       padding:12px 16px; border-radius:6px; color:#991B1B; }
    .alert-success   { background:#F0FDF4; border-left:4px solid #16A34A;
                       padding:12px 16px; border-radius:6px; color:#166534; }
    .agent-badge     { background:#FEF3C7; color:#92400E; font-size:12px;
                       font-weight:600; padding:3px 10px; border-radius:20px;
                       display:inline-block; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<span class="agent-badge">⚡ Agent 5</span>', unsafe_allow_html=True)
st.title("Stress Testing Agent")
st.caption("Scenario analysis under adverse conditions · Capital impact · Solvency assessment")
st.divider()

# ── Sidebar: Portfolio Inputs ──────────────────────────────────────────────────
with st.sidebar:
    st.header("Portfolio Inputs")
    st.caption("Enter portfolio figures or load from upstream agents.")

    st.subheader("Financials (₹ Cr)")
    claim_amount   = st.number_input("Total Claim Amount",  min_value=0.0, value=850.0,  step=10.0)
    written_premium = st.number_input("Written Premium",    min_value=0.0, value=1200.0, step=10.0)
    total_expense  = st.number_input("Total Expense",       min_value=0.0, value=220.0,  step=10.0)
    capital_reserve = st.number_input("Capital Reserve",    min_value=0.0, value=500.0,  step=10.0)

    st.subheader("Risk Scores (0–100)")
    insurance_risk   = st.slider("Insurance Risk",   0, 100, 42)
    market_risk      = st.slider("Market Risk",      0, 100, 35)
    credit_risk      = st.slider("Credit Risk",      0, 100, 28)
    operational_risk = st.slider("Operational Risk", 0, 100, 22)
    catastrophe_risk = st.slider("Catastrophe Risk", 0, 100, 55)

    st.subheader("Distribution")
    region       = st.selectbox("Region",   ["All", "North", "South", "East", "West"])
    product_type = st.selectbox("Product",  ["All", "Motor", "Health", "Property", "Travel", "Fire", "Marine"])

portfolio = {
    "claim_amount":    claim_amount,
    "written_premium": written_premium,
    "total_expense":   total_expense,
    "capital_reserve": capital_reserve,
    "insurance_risk":  insurance_risk,
    "market_risk":     market_risk,
    "credit_risk":     credit_risk,
    "operational_risk": operational_risk,
    "catastrophe_risk": catastrophe_risk,
    "region":          region,
    "product_type":    product_type,
}

# ── Scenario Selection ─────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Select Stress Scenario</p>', unsafe_allow_html=True)

scenario_cols = st.columns(5)
scenario_labels = {
    "s1": ("📈", "Scenario 1", "Claims +20%"),
    "s2": ("📈", "Scenario 2", "Claims +40%"),
    "s3": ("📉", "Scenario 3", "Market Risk +25%"),
    "s4": ("💥", "Scenario 4", "Combined Shock"),
    "s5": ("🌊", "Scenario 5", "Catastrophic Event"),
}

if "selected_scenario" not in st.session_state:
    st.session_state.selected_scenario = "s1"

for col, (sid, (icon, name, desc)) in zip(scenario_cols, scenario_labels.items()):
    with col:
        is_active = st.session_state.selected_scenario == sid
        border = "2px solid #1D4ED8" if is_active else "1px solid #E5E7EB"
        bg = "#EFF6FF" if is_active else "#FFFFFF"
        st.markdown(
            f'<div style="border:{border};background:{bg};border-radius:10px;'
            f'padding:14px 10px;text-align:center;cursor:pointer;">'
            f'<div style="font-size:24px">{icon}</div>'
            f'<div style="font-weight:600;font-size:13px;margin:4px 0">{name}</div>'
            f'<div style="font-size:11px;color:#6B7280">{desc}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button(f"Select", key=f"btn_{sid}", use_container_width=True):
            st.session_state.selected_scenario = sid
            st.rerun()

selected_scenario = st.session_state.selected_scenario
st.divider()

# ── Run Analysis ───────────────────────────────────────────────────────────────
run_col, _ = st.columns([1, 4])
with run_col:
    run = st.button("▶  Run Stress Test", type="primary", use_container_width=True)

if run or st.session_state.get("results_computed"):
    st.session_state.results_computed = True

    base   = compute_base_metrics(portfolio)
    sc     = apply_scenario(portfolio, selected_scenario)
    stress = compute_stressed_metrics(portfolio, sc)
    capital = compute_capital_impact(portfolio, stress)
    solvency = compute_solvency(portfolio, capital)

    sc_info = SCENARIO_CONFIG[selected_scenario]
    st.success(f"**Scenario: {sc_info['label']}** — {sc_info['description']}")

    # ── Scenario Results ───────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Scenario Results</p>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta_claim = stress["stressed_claim"] - portfolio["claim_amount"]
        st.metric("Stressed Claims",
                  fmt_cr(stress["stressed_claim"]),
                  delta=f"+{fmt_cr(delta_claim)}",
                  delta_color="inverse")
    with c2:
        st.metric("Stressed Loss Ratio",
                  fmt_pct(stress["stressed_lr"]),
                  delta=f"+{fmt_pct(stress['stressed_lr'] - base['loss_ratio'])}pp",
                  delta_color="inverse")
    with c3:
        st.metric("Stressed Combined Ratio",
                  fmt_pct(stress["stressed_cr"]),
                  delta=f"+{fmt_pct(stress['stressed_cr'] - base['combined_ratio'])}pp",
                  delta_color="inverse")
    with c4:
        uw_delta = stress["stressed_uw"] - base["underwriting_profit"]
        st.metric("Underwriting P&L",
                  fmt_cr(stress["stressed_uw"]),
                  delta=fmt_cr(uw_delta),
                  delta_color="inverse")

    st.divider()

    # ── Capital Impact ─────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Capital Impact</p>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Capital Consumed",  fmt_cr(capital["total_consumed"]))
    with c2:
        st.metric("Remaining Capital", fmt_cr(solvency["remaining_capital"]))
    with c3:
        st.metric("Solvency Ratio",    fmt_pct(solvency["solvency_ratio"]))
    with c4:
        st.metric("Capital Shortfall", fmt_cr(solvency["shortfall"]) if solvency["shortfall"] > 0 else "None")

    # Alert
    if solvency["shortfall"] > 0:
        st.markdown(
            f'<div class="alert-danger">⚠️ <strong>Capital Shortfall: {fmt_cr(solvency["shortfall"])}</strong> — '
            f'Solvency ratio drops to {fmt_pct(solvency["solvency_ratio"])}. '
            f'Immediate capital infusion or risk mitigation is required.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="alert-success">✅ <strong>Capital Adequate</strong> — '
            f'Solvency ratio remains at {fmt_pct(solvency["solvency_ratio"])} '
            f'with {fmt_cr(solvency["remaining_capital"])} buffer available.</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Solvency Analysis</p>', unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        fig_sol = render_solvency_bars(portfolio, sc)
        st.plotly_chart(fig_sol, use_container_width=True)

    with col_right:
        fig_waterfall = render_capital_waterfall(portfolio, capital, solvency)
        st.plotly_chart(fig_waterfall, use_container_width=True)

    st.markdown('<p class="section-header">Scenario Comparison — Combined Ratio</p>', unsafe_allow_html=True)
    fig_cr = render_scenario_comparison_chart(portfolio)
    st.plotly_chart(fig_cr, use_container_width=True)

    st.divider()

    # ── Product Vulnerability ──────────────────────────────────────────────────
    st.markdown('<p class="section-header">Product Vulnerability Analysis</p>', unsafe_allow_html=True)
    vuln_df = compute_product_vulnerability(portfolio, stress, capital)
    fig_vuln = render_product_vulnerability_chart(vuln_df)
    col_left, col_right = st.columns([2, 3])

    with col_left:
        def style_vuln(val):
            colors = {"High": "background-color:#FEF2F2;color:#991B1B;font-weight:600",
                      "Medium": "background-color:#FFFBEB;color:#92400E;font-weight:600",
                      "Low": "background-color:#F0FDF4;color:#166534;font-weight:600"}
            return colors.get(val, "")
        st.dataframe(
            vuln_df.style.applymap(style_vuln, subset=["Vulnerability"]),
            use_container_width=True,
            hide_index=True,
        )

    with col_right:
        st.plotly_chart(fig_vuln, use_container_width=True)

    st.divider()

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Export Results</p>', unsafe_allow_html=True)
    results_dict = {
        "scenario": sc_info["label"],
        "stressed_claims":       stress["stressed_claim"],
        "stressed_loss_ratio":   stress["stressed_lr"],
        "stressed_combined_ratio": stress["stressed_cr"],
        "stressed_uw_profit":    stress["stressed_uw"],
        "capital_consumed":      capital["total_consumed"],
        "remaining_capital":     solvency["remaining_capital"],
        "solvency_ratio":        solvency["solvency_ratio"],
        "capital_shortfall":     solvency["shortfall"],
    }
    results_df = pd.DataFrame([results_dict])

    col1, col2 = st.columns(2)
    with col1:
        csv = results_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download Results CSV", csv, "stress_test_results.csv", "text/csv")
    with col2:
        vuln_csv = vuln_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download Vulnerability CSV", vuln_csv, "product_vulnerability.csv", "text/csv")

    # Pass results to Executive Reporting Agent
    st.session_state["stress_test_results"] = {
        "scenario_label":         sc_info["label"],
        "base_metrics":           base,
        "stressed_metrics":       stress,
        "capital_impact":         capital,
        "solvency":               solvency,
        "product_vulnerability":  vuln_df.to_dict("records"),
    }
