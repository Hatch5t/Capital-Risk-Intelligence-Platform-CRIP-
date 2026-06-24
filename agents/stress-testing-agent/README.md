# CRIP — Agent 5: Stress Testing Agent

**Capital & Risk Intelligence Platform**  
AI-Powered Multi-Agent Decision Support System for Insurance Risk Management

---

## Overview

The Stress Testing Agent performs scenario-based capital and solvency analysis on a general insurance portfolio. It is the fifth agent in the CRIP pipeline, receiving outputs from the Risk Intelligence Agent and feeding results to the Executive Reporting Agent.

### Scenarios

| ID | Label | Description |
|----|-------|-------------|
| S1 | Claims +20% | Moderate shock |
| S2 | Claims +40% | Severe shock |
| S3 | Market Risk +25% | Market stress |
| S4 | Combined Shock | Claims +40% + Market +25% |
| S5 | Catastrophic Event | Flood / Cyclone / Earthquake |

### Outputs

- Stressed loss ratio, combined ratio, underwriting P&L
- Capital consumed (claim loss, market risk, catastrophe risk channels)
- Solvency ratio and capital shortfall
- Risk score heatmap by category
- Capital waterfall chart
- Product vulnerability analysis (Motor, Health, Property, Travel, Fire, Marine)
- Downloadable CSV results

---

## Project Structure

```
crip_stress_agent/
├── stress_testing_agent.py     # Main Streamlit app
├── utils/
│   ├── scenarios.py            # Scenario definitions & multipliers
│   ├── calculations.py         # Actuarial & capital calculations
│   └── formatting.py           # Display helpers
├── components/
│   └── charts.py               # Plotly chart components
├── tests/
│   └── test_calculations.py    # Pytest unit tests
├── requirements.txt
└── README.md
```

---

## Setup

```bash
# 1. Clone the repo and navigate to the agent folder
cd crip_stress_agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the Streamlit app
streamlit run stress_testing_agent.py

# 5. Run tests
pytest tests/ -v
```

---

## CRIP Pipeline Integration

### Inputs expected from upstream agents

The agent reads from `st.session_state` for data passed from earlier agents:

| Key | Source Agent | Description |
|-----|-------------|-------------|
| `portfolio_data` | Agent 1 (Data Governance) | Clean validated dataset |
| `risk_results` | Agent 3 (Risk Intelligence) | Composite risk scores |

When running standalone, use the sidebar sliders to enter portfolio values manually.

### Outputs passed to downstream agents

Results are written to `st.session_state["stress_test_results"]` as a dict:

```python
{
    "scenario_label":        str,
    "base_metrics":          dict,   # loss_ratio, combined_ratio, uw_profit
    "stressed_metrics":      dict,   # stressed_claim, stressed_lr, stressed_cr
    "capital_impact":        dict,   # claim_impact, market_impact, cat_impact
    "solvency":              dict,   # remaining_capital, solvency_ratio, shortfall
    "product_vulnerability": list,   # list of dicts per product
}
```

Agent 6 (Executive Reporting) reads `st.session_state["stress_test_results"]` to generate the executive summary and PDF report.

---

## Customisation

### Adjusting capital sensitivity coefficients

In `utils/calculations.py → compute_capital_impact()`:

```python
market_impact = (portfolio["market_risk"] / 100) * capital * 0.40   # ← adjust
cat_impact    = (portfolio["catastrophe_risk"] / 100) * capital * 0.25  # ← adjust
```

Change these weights to match your internal capital model or regulatory requirements.

### Adding a new scenario

In `utils/scenarios.py → SCENARIO_CONFIG`, add:

```python
"s6": {
    "label":       "Scenario 6 — Pandemic",
    "description": "Health claims surge 80%, operational risk +30%",
    "claim_mult":  1.80,
    "mkt_mult":    1.10,
    "cat_mult":    1.00,
},
```

Then add the button in `stress_testing_agent.py`.

---

## Technology Stack

| Tool | Purpose |
|------|---------|
| Python | Core development |
| Streamlit | Web application |
| Pandas | Data manipulation |
| Plotly | Interactive visualisations |
| Pytest | Unit testing |

---

*CRIP — Powering the Future of Insurance Risk Management*
