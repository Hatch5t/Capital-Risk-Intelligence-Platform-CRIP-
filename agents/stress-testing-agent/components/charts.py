"""
Plotly chart components for the Stress Testing Agent.
All functions return a plotly Figure object ready to pass to st.plotly_chart().
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.scenarios import apply_scenario, apply_all_scenarios, SCENARIO_CONFIG
from utils.calculations import (
    compute_base_metrics,
    compute_stressed_metrics,
    compute_capital_impact,
    compute_solvency,
)
from utils.formatting import vulnerability_color

COLORS = {
    "base":     "#1D4ED8",
    "stressed": "#DC2626",
    "capital":  "#D97706",
    "safe":     "#16A34A",
    "neutral":  "#6B7280",
}


def render_scenario_comparison_chart(portfolio: dict) -> go.Figure:
    """
    Grouped bar chart: base vs stressed Combined Ratio across all 5 scenarios.
    """
    base = compute_base_metrics(portfolio)
    labels, base_crs, stressed_crs = [], [], []

    for sid, sc in apply_all_scenarios(portfolio).items():
        stress = compute_stressed_metrics(portfolio, sc)
        short  = SCENARIO_CONFIG[sid]["label"].split("—")[0].strip()
        labels.append(short)
        base_crs.append(base["combined_ratio"])
        stressed_crs.append(stress["stressed_cr"])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Base CR", x=labels, y=base_crs,
        marker_color=COLORS["base"],
        text=[f"{v:.1f}%" for v in base_crs],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Stressed CR", x=labels, y=stressed_crs,
        marker_color=COLORS["stressed"],
        text=[f"{v:.1f}%" for v in stressed_crs],
        textposition="outside",
    ))
    fig.add_hline(y=100, line_dash="dash", line_color="#374151",
                  annotation_text="100% breakeven", annotation_position="bottom right")

    fig.update_layout(
        title="Combined Ratio — Base vs Stressed (all scenarios)",
        barmode="group",
        yaxis_title="Combined Ratio (%)",
        xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=40, r=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
    )
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig


def render_solvency_bars(portfolio: dict, scenario: dict) -> go.Figure:
    """
    Horizontal bar chart showing stressed risk scores by category.
    """
    categories = ["Insurance", "Market", "Credit", "Operational", "Catastrophe"]
    scores = [
        portfolio["insurance_risk"],
        scenario["stressed_mkt"],
        portfolio["credit_risk"],
        portfolio["operational_risk"],
        scenario["stressed_cat"],
    ]
    colors = [
        COLORS["base"] if s < 40 else COLORS["capital"] if s < 70 else COLORS["stressed"]
        for s in scores
    ]

    fig = go.Figure(go.Bar(
        x=scores,
        y=categories,
        orientation="h",
        marker_color=colors,
        text=[f"{round(s)}/100" for s in scores],
        textposition="outside",
    ))
    fig.add_vline(x=70, line_dash="dash", line_color="#DC2626",
                  annotation_text="High-risk threshold (70)", annotation_position="top right")

    fig.update_layout(
        title="Risk Scores Under Stress",
        xaxis=dict(range=[0, 110], title="Score (0–100)"),
        yaxis_title="",
        margin=dict(t=60, b=40, l=100, r=60),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
    )
    fig.update_xaxes(gridcolor="#F3F4F6")
    return fig


def render_capital_waterfall(
    portfolio: dict,
    capital_impact: dict,
    solvency: dict,
) -> go.Figure:
    """
    Waterfall chart: starting capital → deductions → remaining capital.
    """
    fig = go.Figure(go.Waterfall(
        name="Capital",
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Starting Capital", "Claim Loss", "Market Risk", "Cat Risk", "Remaining Capital"],
        y=[
            portfolio["capital_reserve"],
            -capital_impact["claim_impact"],
            -capital_impact["market_impact"],
            -capital_impact["cat_impact"],
            0,
        ],
        text=[
            f"₹{round(portfolio['capital_reserve'])} Cr",
            f"-₹{round(capital_impact['claim_impact'])} Cr",
            f"-₹{round(capital_impact['market_impact'])} Cr",
            f"-₹{round(capital_impact['cat_impact'])} Cr",
            f"₹{round(solvency['remaining_capital'])} Cr",
        ],
        textposition="outside",
        connector={"line": {"color": "#D1D5DB"}},
        increasing={"marker": {"color": COLORS["safe"]}},
        decreasing={"marker": {"color": COLORS["stressed"]}},
        totals={"marker": {"color": COLORS["base"] if solvency["is_solvent"] else COLORS["stressed"]}},
    ))

    fig.update_layout(
        title="Capital Waterfall",
        yaxis_title="₹ Crores",
        margin=dict(t=60, b=40, l=60, r=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
    )
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig


def render_product_vulnerability_chart(vuln_df: pd.DataFrame) -> go.Figure:
    """
    Bubble/scatter chart: Claim Exposure vs Capital At Risk,
    bubble size = vulnerability score, colour = vulnerability label.
    """
    colors = [vulnerability_color(v) for v in vuln_df["Vulnerability"]]

    fig = go.Figure()
    for _, row in vuln_df.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["Claim Exposure (₹ Cr)"]],
            y=[row["Capital At Risk (₹ Cr)"]],
            mode="markers+text",
            name=row["Product"],
            text=[row["Product"]],
            textposition="top center",
            marker=dict(
                size=row["Vulnerability Score"] * 0.8 + 15,
                color=vulnerability_color(row["Vulnerability"]),
                opacity=0.75,
                line=dict(width=1, color="white"),
            ),
        ))

    fig.update_layout(
        title="Product Exposure Map",
        xaxis_title="Claim Exposure (₹ Cr)",
        yaxis_title="Capital At Risk (₹ Cr)",
        showlegend=False,
        margin=dict(t=60, b=60, l=60, r=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12),
    )
    fig.update_xaxes(gridcolor="#F3F4F6")
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig
