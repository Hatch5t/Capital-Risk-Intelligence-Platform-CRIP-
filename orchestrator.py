import streamlit as st
import pandas as pd
import time
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from agents.data_governance   import run_governance_pipeline
from agents.pricing           import run_pricing_pipeline
from agents.risk_intelligence import run_risk_pipeline
from agents.forecasting       import run_forecasting_pipeline   # ← Agent 4
from agents.stress_testing    import run_stress_pipeline        # ← Agent 5
from agents.report_agent import (run_report_pipeline,create_report_dataframe) # <- Agent 6
from agents.chat_agent import init_chat_history, get_chat_history, append_chat_message, generate_chat_response, build_chat_context

# At the top of the page — runs every rerun but only creates the list once
init_chat_history()

# Display existing messages
for msg in get_chat_history():
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle new input
if user_input := st.chat_input("Ask about solvency, risks, findings…"):
    append_chat_message("user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    context = build_chat_context(st.session_state.report_results)
    reply = generate_chat_response(user_input, context)

    append_chat_message("assistant", reply)
    with st.chat_message("assistant"):
        st.markdown(reply)

st.set_page_config(
    page_title="CRIP Unified Orchestrator",
    layout="wide",
    page_icon="cube"
)

st.markdown("""
<style>
/* Custom CSS for Metric Cards */
div[data-testid="stMetric"] {
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(128, 128, 128, 0.2);
    padding: 15px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
}
</style>
""", unsafe_allow_html=True)

loader_text = st.empty()
loader_bar = st.empty()

loader_text.markdown("<h1 style='text-align: center; margin-top: 15vh;'>Loading AI Agents...</h1>", unsafe_allow_html=True)
bar = loader_bar.progress(0)

bar.progress(10)
from agents.data_governance   import run_governance_pipeline
bar.progress(30)
from agents.pricing           import run_pricing_pipeline
bar.progress(50)
from agents.risk_intelligence import run_risk_pipeline
bar.progress(70)
from agents.forecasting       import run_forecasting_pipeline   # ← Agent 4
from agents.stress_testing    import run_stress_pipeline        # ← Agent 5
from agents.chat_agent        import generate_chat_response, build_chat_context     # ← Agent 6
bar.progress(100)
import plotly.express as px

time.sleep(0.5)
loader_text.empty()
loader_bar.empty()

@st.cache_data(show_spinner=False)
def get_gov_results(df): return run_governance_pipeline(df)

@st.cache_data(show_spinner=False)
def get_pricing_results(df): return run_pricing_pipeline(df)

@st.cache_data(show_spinner=False)
def get_risk_results(df): return run_risk_pipeline(df)

@st.cache_data(show_spinner=False)
def get_forecast_results(df, periods): return run_forecasting_pipeline(df, forecast_periods=periods)

@st.cache_data(show_spinner=False)
def get_stress_results(df, scenario): return run_stress_pipeline(df, scenario_id=scenario)

st.title("CRIP: Comprehensive Risk Intelligence Platform")
st.markdown("Upload a raw insurance dataset to automatically orchestrate all AI agents.")

# ── Sidebar settings ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h1 style='text-align: left; font-size: 3rem; font-weight: 900; color: var(--primary-color); margin-top: -5rem; margin-bottom: 1rem; letter-spacing: 4px; pointer-events: none;'>CRIP</h1>", unsafe_allow_html=True)
    st.header("Configuration")
    if st.button("Open Config File", use_container_width=True):
        try:
            import os
            os.startfile("config.py")
        except Exception as e:
            st.error(f"Could not open file: {e}")
            
    st.divider()
    
    st.header("Appearance")
    dark_mode = st.toggle("🌙 Dark Mode")
    if dark_mode:
        st.markdown(
            """
            <style>
            html {
                filter: invert(1) hue-rotate(180deg);
            }
            /* Exclude specific elements like charts and images from inversion so they look normal */
            img, video, iframe, [data-testid="stImage"], .stPlotlyChart {
                filter: invert(1) hue-rotate(180deg);
            }
            </style>
            """,
            unsafe_allow_html=True
        )

    
    st.header("Forecasting Settings")
    forecast_periods = st.slider("Forecast horizon (months)", 3, 24, 12)

    st.divider()
    st.header("⚡ Stress Testing Settings")
    SCENARIO_LABELS = {
        "s1": "S1 — Claims +20% (Moderate)",
        "s2": "S2 — Claims +40% (Severe)",
        "s3": "S3 — Market Risk +25%",
        "s4": "S4 — Combined Shock",
        "s5": "S5 — Catastrophic Event",
    }
    selected_scenario = st.selectbox(
        "Stress scenario",
        options=list(SCENARIO_LABELS.keys()),
        format_func=lambda x: SCENARIO_LABELS[x],
        index=3,
    )

# ── File upload ───────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload Raw Dataset (.csv or .xlsx)", type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file)
    else:
        df_raw = pd.read_excel(uploaded_file)

    st.success(f"Dataset '{uploaded_file.name}' loaded — {len(df_raw):,} rows and {len(df_raw.columns):,} columns.")

    if st.button("🚀 Run All Agents", type="primary"):
        st.session_state.agents_run = True

    if st.session_state.get("agents_run", False):
        st.divider()

        # ── Agent 1: Data Governance ──────────────────────────────────────────
        with st.status("🛡️ Agent 1: Data Governance Running...", expanded=True) as status1:
            st.write("Profiling dataset, detecting anomalies, imputing missing values...")
            time.sleep(0.5)
            gov_results = get_gov_results(df_raw)
            df_clean    = gov_results["df_clean"]
            status1.update(label=f"Data Governance complete — {len(df_clean):,} clean rows.", state="complete", expanded=False)

        # ── Agent 2: Pricing & Profitability ──────────────────────────────────
        with st.status("📈 Agent 2: Pricing & Profitability Running...", expanded=True) as status2:
            st.write("Calculating Loss Ratios, Expense Ratios, Underwriting Profit...")
            time.sleep(0.5)
            pricing_results = get_pricing_results(df_clean)
            df_pricing      = pricing_results["df_pricing"]
            kpis            = pricing_results["kpis"]
            status2.update(label="Pricing Analysis complete!", state="complete", expanded=False)

        # ── Agent 3: Risk Intelligence & ML ──────────────────────────────────
        with st.status("🛡️ Agent 3: Risk Intelligence & ML Running...", expanded=True) as status3:
            st.write("Calculating Risk Scores, Training XGBoost, running Monte Carlo...")
            time.sleep(0.5)
            risk_results       = get_risk_results(df_pricing)
            df_risk            = risk_results["df_risk"]
            feature_importance = risk_results["feature_importance"]
            portfolio_metrics  = risk_results["portfolio_metrics"]

            os.makedirs("reports", exist_ok=True)
            
            try:
                df_risk.to_csv("reports/risk_intelligence_dataset.csv", index=False)
                
                summary_path = "reports/risk_summary_report.xlsx"
                with pd.ExcelWriter(summary_path) as writer:
                    pd.DataFrame([portfolio_metrics]).T.reset_index()\
                      .rename(columns={0: "Value", "index": "Metric"})\
                      .to_excel(writer, sheet_name="Portfolio Metrics", index=False)
                    if "Product_Type" in df_risk.columns:
                        risk_cols = [c for c in ["Insurance_Risk", "Market_Risk", "Credit_Risk",
                                                 "Operational_Risk", "Hazard_Score"] if c in df_risk.columns]
                        df_risk.groupby("Product_Type")[risk_cols].mean().reset_index()\
                               .to_excel(writer, sheet_name="Risks by Product", index=False)
                    feature_importance.to_excel(writer, sheet_name="ML Feature Importance", index=False)
            except PermissionError:
                st.error("⚠️ Could not save reports. Please close `risk_intelligence_dataset.csv` or `risk_summary_report.xlsx` if they are open in Excel.")
                if "Model Governance & Validation Standards" in df_risk.columns:
                    df_risk["Model Governance & Validation Standards"].value_counts()\
                           .reset_index().rename(columns={"index": "Status",
                                                          "Model Governance & Validation Standards": "Count"})\
                           .to_excel(writer, sheet_name="Model Governance", index=False)
            status3.update(label="Risk Intelligence & ML complete!", state="complete", expanded=False)

        # ── Agent 4: Forecasting ──────────────────────────────────────────────
        with st.status(f"📊 Agent 4: Time Series Forecasting Running... (Horizon: {forecast_periods}M)", expanded=True) as status4:
            st.write("Forecasting claims & premiums...")
            time.sleep(0.5)
            forecast_results = get_forecast_results(df_pricing, forecast_periods)
            fkpis = forecast_results["kpis"]
            if fkpis:
                msg = f"Forecasting complete — Next month claims: ₹{fkpis.get('Next_Month_Claims_Fc', 0):,.0f}"
            else:
                msg = "Forecasting complete — insufficient date range."
            status4.update(label=msg, state="complete", expanded=False)

        # ── Agent 5: Stress Testing ───────────────────────────────────────────
        with st.status(f"⚡ Agent 5: Stress Testing Running... ({SCENARIO_LABELS[selected_scenario]})", expanded=True) as status5:
            st.write("Running scenario simulations...")
            time.sleep(0.5)
            stress_results = get_stress_results(df_risk, selected_scenario)
            sol = stress_results["solvency_ratio"]
            if stress_results["is_solvent"]:
                msg = f"Stress Testing complete — Solvency ratio: {sol:.1f}% — Capital adequate."
                state_val = "complete"
            else:
                msg = f"Stress Testing complete — Solvency ratio: {sol:.1f}% — Capital shortfall!"
                state_val = "error"
            status5.update(label=msg, state=state_val, expanded=False)
        # ── Agent 6: Actuarial Report ───────────────────────────────────────────
        with st.status("Agent 6: Actuarial Valuation Report Running...", expanded=True) as status6:
            st.write("Generating actuarial valuation report...")
            time.sleep(1)
            report_results = run_report_pipeline(
                gov_results,
                pricing_results,
                risk_results,
                forecast_results,
                stress_results
            )
            # Store in session_state so the chat tab can access it anytime
            st.session_state["report_results"] = report_results
            st.session_state["chat_history"]   = []   # reset chat on new run
            time.sleep(0.5)
            status6.update(label="Actuarial Valuation Report Generated!", state="complete", expanded=False)

        report_df = create_report_dataframe(report_results)
        st.download_button(
            label="⬇️ Download Actuarial Report Summary",
            data=report_df.to_csv(index=False).encode("utf-8"),
            file_name="actuarial_report_summary.csv",
            mime="text/csv",
        )

        st.toast("Pipeline execution complete!")
        st.success("All AI Agents have successfully completed their analysis.")

        st.divider()

        # ── Sidebar chat — rendered HERE so session_state is already populated ──
        with st.sidebar:
            st.divider()
            st.markdown("### 🤖 Chief Risk Officer Assistant")
            st.caption("Ask me anything about the generated risk reports.")

            if "sb_chat_history" not in st.session_state:
                st.session_state["sb_chat_history"] = []

            _sb_ctx = build_chat_context(report_results)

            # Quick-question buttons
            _sb_quick = [
                "What is our overall Capital Adequacy?",
                "Which product is most profitable?",
                "Summarise all open findings.",
                "What is the forecast for next month?",
            ]
            for _sq in _sb_quick:
                if st.button(_sq, key=f"sb_quick_{_sq[:20]}", use_container_width=True):
                    st.session_state["sb_chat_history"].append({"role": "user", "content": _sq})
                    with st.spinner("Thinking…"):
                        _sb_reply = generate_chat_response(_sq, _sb_ctx)
                    st.session_state["sb_chat_history"].append({"role": "assistant", "content": _sb_reply})
                    st.rerun()

            # Conversation history
            for _sb_msg in st.session_state["sb_chat_history"]:
                with st.chat_message(_sb_msg["role"]):
                    st.markdown(_sb_msg["content"])

            # Free-text input
            _sb_input = st.chat_input("Ask about solvency, risks, findings…", key="sb_chat_input")
            if _sb_input:
                st.session_state["sb_chat_history"].append({"role": "user", "content": _sb_input})
                with st.spinner("Thinking…"):
                    _sb_reply = generate_chat_response(_sb_input, _sb_ctx)
                st.session_state["sb_chat_history"].append({"role": "assistant", "content": _sb_reply})
                st.rerun()

            # Clear button
            if st.session_state.get("sb_chat_history"):
                if st.button("🗑️ Clear chat", key="sb_clear", use_container_width=True):
                    st.session_state["sb_chat_history"] = []
                    st.rerun()
        
        # ── Results tabs ──────────────────────────────────────────────────────
        st.header("📊 Final Agent Reports")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🛡️ Data Governance",
            "📈 Pricing & Profitability",
            "🔮 Risk Intelligence & ML",
            "📊 Time Series Forecast",
            "⚡ Stress Testing",
            "📋 Actuarial Report",
        ])

        # ── Tab 1: Data Governance ────────────────────────────────────────────
        with tab1:
            st.subheader("Data Cleaning Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Original Rows",     gov_results["summary"]["total_rows"])
            c2.metric("Cleaned Rows",      len(df_clean))
            c3.metric("Anomalies Flagged", len(gov_results["anomalies"]))
            st.write("Missing Values Found Before Cleaning:")
            if not gov_results["missing_df"].empty:
                st.dataframe(gov_results["missing_df"])
            else:
                st.info("No missing values.")
            st.write("Cleaned Dataset Preview:")
            st.dataframe(df_clean.head(50))

        # ── Tab 2: Pricing ────────────────────────────────────────────────────
        with tab2:
            st.subheader("Financial KPIs")
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("Total Premium",   f"₹{kpis['Total_Premium']:,.0f}")
            pc2.metric("Total Claims",    f"₹{kpis['Total_Claims']:,.0f}")
            pc3.metric("Total Expenses",  f"₹{kpis['Total_Expenses']:,.0f}")
            dc = "normal" if kpis["Underwriting_Profit"] > 0 else "inverse"
            pc4.metric("Underwriting Profit", f"₹{kpis['Underwriting_Profit']:,.0f}",
                       delta=f"₹{kpis['Underwriting_Profit']:,.0f}", delta_color=dc)

            st.write("Profitability Classification Distribution:")
            st.dataframe(df_pricing.groupby("Profitability_Tier").size()
                         .reset_index(name="Count"), use_container_width=True)

            if "Product_Type" in df_pricing.columns:
                st.subheader("📊 Loss Ratio by Product")
                lr_df = df_pricing.groupby("Product_Type")["Loss_Ratio"].mean().reset_index()
                st.plotly_chart(px.bar(lr_df, x='Product_Type', y='Loss_Ratio', color_discrete_sequence=['#0f4c81']), use_container_width=True)
                
                st.subheader("💰 Profit by Product")
                prof_df = df_pricing.groupby("Product_Type")["Underwriting_Profit"].sum().reset_index()
                st.plotly_chart(px.bar(prof_df, x='Product_Type', y='Underwriting_Profit', color_discrete_sequence=['#0f4c81']), use_container_width=True)

            st.subheader("AI Pricing Insights")
            if "Product_Type" in df_pricing.columns:
                for _, row in df_pricing.groupby("Product_Type")["Combined_Ratio"].mean().reset_index().iterrows():
                    product, ratio = row["Product_Type"], row["Combined_Ratio"]
                    if ratio > 1:
                        st.error(f"**{product}**: Combined Ratio {ratio:.2f} → Underpriced. Immediate rate action required.")
                    elif ratio < 0.80:
                        st.success(f"**{product}**: Combined Ratio {ratio:.2f} → Highly Profitable.")
                    else:
                        st.warning(f"**{product}**: Combined Ratio {ratio:.2f} → Monitor Pricing.")
            else:
                st.info("Product Type data not available for AI Pricing Insights.")

            st.subheader("Pricing Dataset Preview")
            csv = df_pricing.to_csv(index=False).encode('utf-8')
            st.download_button("Download Pricing Data", data=csv, file_name="pricing_data.csv", mime="text/csv")
            st.dataframe(df_pricing.head(50))

        # ── Tab 3: Risk Intelligence ──────────────────────────────────────────
        with tab3:
            st.subheader("⚠️ Composite Risk Scores (Actuarial)")
            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            rc1.metric("Avg Insurance Risk",   f"{df_risk['Insurance_Risk'].mean():.1f}/10")
            rc2.metric("Avg Market Risk",      f"{df_risk['Market_Risk'].mean():.1f}/10")
            rc3.metric("Avg Credit Risk",      f"{df_risk['Credit_Risk'].mean():.1f}/10")
            rc4.metric("Avg Operational Risk", f"{df_risk['Operational_Risk'].mean():.1f}/10")
            rc5.metric("Avg CAT Risk",         f"{df_risk['Hazard_Score'].mean():.1f}/10")

            st.subheader("🔮 XGBoost Feature Importance")
            st.plotly_chart(px.bar(feature_importance, x='Importance', y='Feature', orientation='h', color_discrete_sequence=['#0f4c81']), use_container_width=True)

            st.subheader("🏛️ Capital Adequacy & Monte Carlo (VaR)")
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("VaR (99%)",         f"₹{portfolio_metrics['VaR_99']:,.0f}")
            mc2.metric("Expected Shortfall", f"₹{portfolio_metrics['Expected_Shortfall']:,.0f}")
            mc3.metric("Solvency Ratio",     f"{portfolio_metrics['Solvency_Ratio']:.1f}%")
            mc4.metric("Model AUC",          f"{portfolio_metrics['AUC']:.2f}")

            gov_cols     = ["Policy_ID", "Expected_Claim_Amount_ML", "AUC", "KS Statistic",
                            "Brier Score", "PSI", "Model Governance & Validation Standards"]
            display_cols = [c for c in gov_cols if c in df_risk.columns]
            csv_risk = df_risk.to_csv(index=False).encode('utf-8')
            st.download_button("Download Risk Output", data=csv_risk, file_name="risk_data.csv", mime="text/csv")
            st.dataframe(df_risk[display_cols].head(50))

        # ── Tab 4: Forecasting ────────────────────────────────────────────────
        with tab4:
            fk = forecast_results["kpis"]
            st.subheader(f"📊 Time Series Forecast — Next {forecast_periods} Months")
            st.caption("Derived from the pricing data produced by Agent 2. "
                       "Forecasts use Prophet where available, linear trend otherwise.")

            if fk:
                fc1, fc2, fc3, fc4 = st.columns(4)
                fc1.metric("Avg Monthly Premium", f"₹{fk.get('Avg_Monthly_Premium', 0):,.0f}")
                fc2.metric("Avg Monthly Claims",  f"₹{fk.get('Avg_Monthly_Claims',  0):,.0f}")
                fc3.metric("Next Month Claims Fc",  f"₹{fk.get('Next_Month_Claims_Fc', 0):,.0f}")
                fc4.metric("Next Month Premium Fc", f"₹{fk.get('Next_Month_Premium_Fc', 0):,.0f}")

                yoy = forecast_results["yoy_df"]
                if not yoy.empty:
                    st.markdown("#### Year-over-Year Growth (Latest Period)")
                    y1, y2 = st.columns(2)
                    latest = yoy.iloc[-1]
                    y1.metric("Premium YoY", f"{latest.get('Premium_YoY', 0):.1f}%",
                              delta=f"{latest.get('Premium_YoY', 0):.1f}pp")
                    y2.metric("Claims YoY",  f"{latest.get('Claims_YoY', 0):.1f}%",
                              delta=f"{latest.get('Claims_YoY', 0):.1f}pp",
                              delta_color="inverse")

            # Claims forecast chart
            st.markdown("#### Claims Forecast")
            fc_df = forecast_results["claims_forecast"]
            monthly = forecast_results["monthly_df"]
            if not fc_df.empty and not monthly.empty:
                last_hist = pd.to_datetime(monthly["Month"].max())
                hist_fc   = fc_df[pd.to_datetime(fc_df["ds"]) <= last_hist]
                fut_fc    = fc_df[pd.to_datetime(fc_df["ds"]) >  last_hist]

                chart_data = pd.DataFrame({
                    "Actual Claims":    monthly.set_index("Month")["Claim_Amount"],
                }).join(
                    pd.DataFrame({
                        "Forecast":     fc_df.set_index("ds")["yhat"],
                        "Upper Bound":  fc_df.set_index("ds")["yhat_upper"],
                        "Lower Bound":  fc_df.set_index("ds")["yhat_lower"],
                    }),
                    how="outer",
                )
                fig = px.line(chart_data, title="Claims Forecast", color_discrete_sequence=px.colors.qualitative.Plotly)
                st.plotly_chart(fig, use_container_width=True)

            # Premium forecast chart
            st.markdown("#### Premium Forecast")
            pfc_df = forecast_results["premium_forecast"]
            if not pfc_df.empty and not monthly.empty:
                pchart  = pd.DataFrame({
                    "Actual Premium":  monthly.set_index("Month")["Written_Premium"],
                }).join(
                    pd.DataFrame({
                        "Forecast": pfc_df.set_index("ds")["yhat"],
                        "Upper Bound":  pfc_df.set_index("ds")["yhat_upper"],
                        "Lower Bound":  pfc_df.set_index("ds")["yhat_lower"],
                    }),
                    how="outer",
                )
                fig_p = px.line(pchart, title="Premium Forecast", color_discrete_sequence=px.colors.qualitative.Plotly)
                st.plotly_chart(fig_p, use_container_width=True)

            # Seasonal index
            sea = forecast_results["seasonal_df"]
            if not sea.empty:
                st.markdown("#### Seasonal Index (100 = annual average)")
                sea_chart = sea.set_index("Month_Name")[["Avg_Claims_Index", "Avg_Premium_Index"]].reset_index()
                fig_sea = px.bar(sea_chart, x="Month_Name", y=["Avg_Claims_Index", "Avg_Premium_Index"], barmode="group")
                st.plotly_chart(fig_sea, use_container_width=True)

            # Claim frequency & severity
            freq = forecast_results["freq_df"]
            sev  = forecast_results["sev_df"]
            if not freq.empty and not sev.empty:
                st.markdown("#### Claim Frequency & Severity")
                fs1, fs2 = st.columns(2)
                with fs1:
                    st.caption("Claim Frequency (%)")
                    st.plotly_chart(px.line(freq, x="Month", y="Claim_Frequency"), use_container_width=True)
                with fs2:
                    st.caption("Claim Severity (avg cost per claim)")
                    st.plotly_chart(px.line(sev, x="Month", y="Claim_Severity"), use_container_width=True)

            # Product breakdown
            prod_df = forecast_results["product_df"]
            if not prod_df.empty:
                st.markdown("#### Product-Level Breakdown")
                st.dataframe(prod_df.style.format({
                    "Total_Premium": "₹{:,.0f}",
                    "Total_Claims":  "₹{:,.0f}",
                    "Loss_Ratio":    "{:.1f}%",
                }), use_container_width=True, hide_index=True)

            # Monthly aggregation table
            st.markdown("#### Monthly Aggregation")
            st.dataframe(forecast_results["monthly_df"], use_container_width=True, hide_index=True)

        # ── Tab 5: Stress Testing ─────────────────────────────────────────────
        with tab5:
            sr  = stress_results["scenario_result"]
            skp = stress_results["kpis"]

            st.subheader(f"{stress_results['scenario_label']}")
            st.caption("Results derived from the cleaned & enriched portfolio from Agents 1–3.")

            st.markdown("#### Stressed Financial Metrics")
            sm1, sm2, sm3, sm4 = st.columns(4)
            sm1.metric("Stressed Claims",
                       f"₹{sr['stressed_claim']:,.0f}",
                       delta=f"+{sr['stressed_claim'] - stress_results['portfolio']['claim_amount']:,.0f}",
                       delta_color="inverse")
            sm2.metric("Stressed Loss Ratio",
                       f"{sr['stressed_lr']:.1f}%",
                       delta=f"+{sr['stressed_lr'] - skp['Base_Loss_Ratio']:.1f}pp",
                       delta_color="inverse")
            sm3.metric("Stressed Combined Ratio",
                       f"{sr['stressed_cr']:.1f}%",
                       delta=f"+{sr['stressed_cr'] - skp['Base_Combined_Ratio']:.1f}pp",
                       delta_color="inverse")
            sm4.metric("Underwriting P&L",
                       f"₹{sr['stressed_uw']:,.0f}",
                       delta="Loss" if sr["stressed_uw"] < 0 else "Profit",
                       delta_color="inverse" if sr["stressed_uw"] < 0 else "normal")

            st.markdown("#### Capital Impact")
            cm1, cm2, cm3, cm4 = st.columns(4)
            cm1.metric("Capital Consumed",  f"₹{sr['capital_consumed']:,.0f}")
            cm2.metric("Remaining Capital", f"₹{sr['remaining_capital']:,.0f}")
            cm3.metric("Solvency Ratio",    f"{sr['solvency_ratio']:.1f}%")
            cm4.metric("Capital Shortfall",
                       f"₹{sr['shortfall']:,.0f}" if sr["shortfall"] > 0 else "None")

            if not stress_results["is_solvent"]:
                st.error(f"Capital shortfall of ₹{sr['shortfall']:,.0f} under "
                         f"**{stress_results['scenario_label']}**. "
                         f"Solvency ratio: {sr['solvency_ratio']:.1f}%. Immediate review required.")
            else:
                st.success(f"Capital adequate under **{stress_results['scenario_label']}**. "
                           f"Solvency ratio: {sr['solvency_ratio']:.1f}%. "
                           f"Buffer: ₹{sr['remaining_capital']:,.0f}.")

            st.markdown("#### All Scenarios Comparison")
            all_sc = stress_results["all_scenarios"].copy()

            def color_cr(val):
                if val > 110: return "background-color:#FEF2F2;color:#991B1B;font-weight:600"
                if val > 100: return "background-color:#FFFBEB;color:#92400E;font-weight:600"
                return "background-color:#F0FDF4;color:#166534;font-weight:600"

            def color_sol(val):
                if val < 50: return "background-color:#FEF2F2;color:#991B1B;font-weight:600"
                if val < 75: return "background-color:#FFFBEB;color:#92400E;font-weight:600"
                return "background-color:#F0FDF4;color:#166534;font-weight:600"

            st.dataframe(
                all_sc.style
                .map(color_cr,  subset=["Stressed CR (%)"])
                .map(color_sol, subset=["Solvency Ratio (%)"])
                .format({
                    "Base CR (%)":        "{:.1f}%",
                    "Stressed CR (%)":    "{:.1f}%",
                    "Stressed LR (%)":    "{:.1f}%",
                    "Capital Consumed":   "₹{:,.0f}",
                    "Solvency Ratio (%)": "{:.1f}%",
                    "Shortfall":          "₹{:,.0f}",
                }),
                use_container_width=True, hide_index=True,
            )

            st.markdown("#### Product Vulnerability")

            def color_vuln(val):
                if val == "High":   return "background-color:#FEF2F2;color:#991B1B;font-weight:600"
                if val == "Medium": return "background-color:#FFFBEB;color:#92400E;font-weight:600"
                return "background-color:#F0FDF4;color:#166534;font-weight:600"

            st.dataframe(
                stress_results["product_vuln"].style
                .map(color_vuln, subset=["Vulnerability"])
                .format({
                    "Claim Exposure":      "₹{:,.0f}",
                    "Capital At Risk":     "₹{:,.0f}",
                    "Vulnerability Score": "{:.1f}",
                }),
                use_container_width=True, hide_index=True,
            )

            st.markdown("#### Scenario Comparison — Combined Ratio")
            fig_cr = px.bar(all_sc, x="Scenario", y=["Base CR (%)", "Stressed CR (%)"], barmode="group", title="Combined Ratio Comparison")
            st.plotly_chart(fig_cr, use_container_width=True)

            st.markdown("#### Solvency Ratio by Scenario")
            fig_sol = px.bar(all_sc, x="Scenario", y="Solvency Ratio (%)", title="Solvency Ratio Comparison", color_discrete_sequence=["#0f4c81"])
            st.plotly_chart(fig_sol, use_container_width=True)

        # ── Save Context for Chat ─────────────────────────────────────────────
        dashboard_context = {
            "Cleaned Rows": len(df_clean),
            "Anomalies Flagged": len(gov_results.get("anomalies", [])),
            "Overall Combined Ratio": f"{(df_pricing['Combined_Ratio'].mean()) * 100:.1f}%" if "Combined_Ratio" in df_pricing.columns else "N/A",
            "Loss Making Products Count": len(df_pricing[df_pricing["Combined_Ratio"] > 1.0]) if "Combined_Ratio" in df_pricing.columns else 0,
            "High Risk Claims Detected": len(df_risk[df_risk["Hazard_Score"] > 0.7]) if "Hazard_Score" in df_risk.columns else 0,
            "Value at Risk (99%)": f"₹{portfolio_metrics.get('VaR_99', 0):.0f}",
        }
        if fkpis:
            dashboard_context["Next Month Claims Forecast"] = f"₹{fkpis.get('Next_Month_Claims_Fc', 0):.0f}"
        dashboard_context["Stress Scenario Solvency"] = f"{stress_results['solvency_ratio']:.1f}%"
        
        st.session_state.dashboard_context = dashboard_context

       # ── Tab 6: Final Report ────────────────────────────────────────────────
        with tab6:
            st.title("📋 Actuarial Capital Validation & Risk Assessment Report")
            st.caption(
                f"Reporting Date: {report_results['metadata']['report_date']}  |  "
                f"Generated By: CRIP AI Platform  |  Model Version: v1.0"
            )

            # ── KPI banner ────────────────────────────────────────────────────
            col1,col2,col3,col4,col5,col6 = st.columns(6)
            col1.metric("Rating",    report_results["portfolio_rating"])
            col2.metric("Health",    f"{report_results['health_score']}/100")
            col3.metric("Solvency",  f"{report_results['capital_validation']['solvency']:.1f}%")
            col4.metric("VaR",       f"₹{report_results['capital_validation']['var']:,.0f}")
            col5.metric("AUC",       f"{report_results['model_validation']['auc']:.2f}")
            col6.metric("Outlook",   report_results.get("portfolio_outlook", "Stable"))
            st.divider()

            # ── Score breakdown ───────────────────────────────────────────────
            with st.expander("🏅 Health Score Breakdown (How the rating was calculated)", expanded=False):
                sb = report_results.get("score_breakdown", {})
                if sb:
                    sb_df = pd.DataFrame(list(sb.items()), columns=["Pillar / Metric", "Value"])
                    st.table(sb_df)
                    st.caption(
                        "Score = Underwriting (25) + Capital Adequacy (20) + "
                        "Portfolio Quality (15) + Stress Resilience (15) + "
                        "Model & Data Quality (15) + Trend & Forecast (10) = 100 pts  |  "
                        "Rating scale: Exceptional (≥88) → Strong (≥75) → Satisfactory (≥62) "
                        "→ Moderate (≥48) → Weak (≥35) → Critical (≥20) → Distressed"
                    )

            # ── Executive Summary ─────────────────────────────────────────────
            st.subheader("Executive Summary ↩")
            st.write(report_results["executive_summary"])

            st.subheader("Key Findings")
            _bad_words = ("shortfall", "loss-making", "critical", "below", "failed", "pressure")
            for finding in report_results["key_findings"]:
                if any(w in finding.lower() for w in _bad_words):
                    st.error(finding)
                else:
                    st.success(finding)

            st.divider()

            # ── Business Insights ──────────────────────────────────────────
            st.subheader("💡 Business Insights")
            bi = report_results.get("business_insights", {})

            # Rate adequacy table
            if "rate_adequacy" in bi and bi["rate_adequacy"]:
                with st.expander("📊 Rate Adequacy by Product", expanded=True):
                    ra_df = pd.DataFrame(bi["rate_adequacy"])
                    def _color_action(val):
                        if "Immediate" in str(val):   return "background-color:#FEE2E2;color:#991B1B;font-weight:600"
                        if "recommended" in str(val): return "background-color:#FEF3C7;color:#92400E;font-weight:600"
                        if "adequate" in str(val):    return "background-color:#D1FAE5;color:#166534;font-weight:600"
                        return "background-color:#EFF6FF;color:#1E40AF;font-weight:600"
                    def _color_chg(val):
                        try:
                            v = float(val)
                            if v > 10:  return "color:#991B1B;font-weight:600"
                            if v > 0:   return "color:#92400E;font-weight:600"
                            return "color:#166534;font-weight:600"
                        except: return ""
                    st.dataframe(
                        ra_df.style
                        .map(_color_action, subset=["Action"])
                        .map(_color_chg,    subset=["Rate Change Needed (%)"])
                        .format({"Current CR (%)": "{:.1f}%", "Rate Change Needed (%)": "{:+.1f}%"}),
                        use_container_width=True, hide_index=True
                    )

            # Profitability concentration
            pc = bi.get("profitability_concentration", {})
            if pc:
                with st.expander("📈 Profitability Concentration", expanded=True):
                    pc1, pc2, pc3 = st.columns(3)
                    pc1.metric("Policies generating 80% of profit",
                               f"Top {pc['top_policies_pct']}%")
                    pc2.metric("Loss-making policies",
                               f"{pc['loss_making_count']} ({pc['loss_making_pct']}%)")
                    pc3.metric("Profit drag from loss-making",
                               f"₹{abs(pc['loss_making_drag']):,.0f}")
                    if pc["loss_making_count"] > 0:
                        st.info(
                            f"Removing the {pc['loss_making_count']} loss-making policies "
                            f"would increase portfolio profit to ₹{pc['profit_ex_losers']:,.0f}."
                        )

            # Cross-subsidisation
            cs = bi.get("cross_subsidization", {})
            if cs.get("is_cross_subsidizing"):
                with st.expander("🔄 Cross-Subsidisation", expanded=True):
                    losers  = cs["loss_making_products"]
                    winners = cs["profitable_products"]
                    csc1, csc2 = st.columns(2)
                    with csc1:
                        st.markdown("**Profitable products (subsidising)**")
                        for prod, val in winners.items():
                            st.success(f"{prod}: ₹{val:,.0f}")
                    with csc2:
                        st.markdown("**Loss-making products (subsidised)**")
                        for prod, val in losers.items():
                            st.error(f"{prod}: ₹{val:,.0f}")

            # Frequency vs severity
            fs = bi.get("frequency_severity", {})
            if fs:
                with st.expander("🔬 Frequency vs Severity Analysis"):
                    fs1, fs2, fs3 = st.columns(3)
                    fs1.metric("Primary Claims Driver", fs["primary_driver"])
                    fs2.metric("Avg Claim Frequency",   f"{fs['avg_frequency']:.1%}")
                    fs3.metric("Avg Claim Severity",    f"₹{fs['avg_severity']:,.0f}")
                    st.caption(
                        f"Frequency trend: **{fs['freq_trend']}** | "
                        f"Severity trend: **{fs['sev_trend']}**"
                    )

            # Pricing gap
            pg = bi.get("pricing_gap", {})
            if pg:
                with st.expander("📉 Pricing Gap Analysis"):
                    pg1, pg2, pg3 = st.columns(3)
                    pg1.metric("Avg Premium Growth",  f"{pg['avg_premium_growth_pct']:.1f}%")
                    pg2.metric("Avg Claims Growth",   f"{pg['avg_claims_growth_pct']:.1f}%",
                               delta=f"{pg['gap_pp']:+.1f}pp gap", delta_color="inverse")
                    pg3.metric("Gap Widening?", "Yes ⚠️" if pg["widening"] else "No ✅")
                    if pg["widening"]:
                        st.warning(
                            f"Claims are growing {pg['gap_pp']:.1f}pp faster than premium. "
                            "Proactive rate action is required to prevent margin erosion."
                        )
                    else:
                        st.success("Premium growth is outpacing claims growth. Pricing is healthy.")

            # Expense efficiency
            ee = bi.get("expense_efficiency", {})
            if ee:
                with st.expander("💰 Expense Efficiency by Product"):
                    ee_df = pd.DataFrame(
                        list(ee["by_product"].items()),
                        columns=["Product", "Expense Ratio (%)"]
                    )
                    st.dataframe(ee_df, use_container_width=True, hide_index=True)
                    st.caption(
                        f"Portfolio avg: **{ee['portfolio_avg']:.1f}%** | "
                        f"Most efficient: **{ee['most_efficient']}** | "
                        f"Least efficient: **{ee['least_efficient']}**"
                    )

            st.divider()

            # ── Report Metadata ───────────────────────────────────────────────
            with st.expander("📄 Report Metadata", expanded=True):
                meta = report_results["metadata"]
                st.table(pd.DataFrame(
                    [(k, str(v)) for k, v in meta.items()],
                    columns=["Field", "Value"]
                ))

            st.divider()

            # ── Data Validation ───────────────────────────────────────────────
            with st.expander("🛡️ Data Validation Results", expanded=True):
                dv = report_results["data_validation"]
                # Only show scalar fields
                scalar_fields = {k: v for k, v in dv.items()
                                 if not isinstance(v, (list, dict))}
                st.table(pd.DataFrame(
                    [(k, str(v)) for k, v in scalar_fields.items()],
                    columns=["Validation Metric", "Result"]
                ))
                status = dv.get("status", "PASS")
                if status == "PASS":
                    st.success("Data quality assessment indicates the portfolio data is suitable "
                               "for actuarial analysis. No material quality concerns identified.")
                else:
                    st.error("Data quality requires review. Flagged records should be investigated "
                             "before submission.")

            st.divider()

            # ── Pricing Assessment ────────────────────────────────────────────
            with st.expander("📈 Pricing Assessment"):
                pa = report_results["pricing_assessment"]

                # KPI metrics
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Written Premium",  f"₹{pa.get('premium',0):,.0f}")
                c2.metric("Total Claims",      f"₹{pa.get('claims',0):,.0f}")
                c3.metric("Combined Ratio",    f"{pa.get('combined_ratio',0):.2f}%")
                c4.metric("Underwriting Profit",f"₹{pa.get('profit',0):,.0f}")

                col_l, col_r = st.columns(2)
                with col_l:
                    st.metric("Loss Ratio",    f"{pa.get('loss_ratio',0):.2f}%")
                with col_r:
                    st.metric("Expense Ratio", f"{pa.get('expense_ratio',0):.2f}%")

                cr_ok = pa.get("combined_ratio", 100) < 100
                if cr_ok:
                    st.success(pa.get("interpretation",""))
                else:
                    st.error(pa.get("interpretation",""))

                # Product breakdown table
                prod_tbl = pa.get("product_table", [])
                if prod_tbl:
                    st.markdown("##### Product Line Performance")
                    prod_display = pd.DataFrame([{
                        "Product":       p.get("Product_Type",""),
                        "Premium (₹)":   f"₹{p.get('Premium',0):,.0f}",
                        "Share":         f"{p.get('Prem_Share',0):.1f}%",
                        "Claims (₹)":    f"₹{p.get('Claims',0):,.0f}",
                        "Loss Ratio":    f"{p.get('LR',0):.1f}%",
                        "Combined Ratio":f"{p.get('CR',0):.1f}%",
                        "Profit (₹)":    f"₹{p.get('Profit',0):,.0f}",
                    } for p in prod_tbl])
                    st.dataframe(prod_display, use_container_width=True, hide_index=True)
                    if pa.get("product_commentary"):
                        st.warning(pa["product_commentary"])

                # Tier distribution
                tier_dist = pa.get("tier_dist", {})
                if tier_dist:
                    st.markdown("##### Profitability Tier Distribution")
                    tier_order = ["Excellent","Good","Marginal","Loss-Making"]
                    total = sum(tier_dist.values())
                    tier_display = pd.DataFrame([{
                        "Tier":    t,
                        "Count":   f"{tier_dist.get(t,0):,}",
                        "% Share": f"{tier_dist.get(t,0)/max(total,1)*100:.1f}%",
                    } for t in tier_order if t in tier_dist])
                    st.dataframe(tier_display, use_container_width=True, hide_index=True)
                    if pa.get("tier_commentary"):
                        st.info(pa["tier_commentary"])

                # Channel & segment
                ch  = pa.get("channel_mix", {})
                seg = pa.get("segment_mix", {})
                ps  = pa.get("policy_status", {})
                if ch or seg or ps:
                    st.markdown("##### Portfolio Composition")
                    mix_cols = st.columns(3)
                    if ch:
                        total_ch = sum(ch.values())
                        with mix_cols[0]:
                            st.markdown("**Distribution Channel**")
                            for k, v in sorted(ch.items(), key=lambda x: -x[1]):
                                st.write(f"• {k}: **{v/total_ch*100:.1f}%** ({v:,})")
                    if seg:
                        total_seg = sum(seg.values())
                        with mix_cols[1]:
                            st.markdown("**Customer Segment**")
                            for k, v in sorted(seg.items(), key=lambda x: -x[1]):
                                st.write(f"• {k}: **{v/total_seg*100:.1f}%** ({v:,})")
                    if ps:
                        total_ps = sum(ps.values())
                        with mix_cols[2]:
                            st.markdown("**Policy Status**")
                            for k, v in sorted(ps.items(), key=lambda x: -x[1]):
                                st.write(f"• {k}: **{v/total_ps*100:.1f}%** ({v:,})")

            st.divider()

            # ── Capital Validation ────────────────────────────────────────────
            with st.expander("🏦 Capital Validation"):
                cv = report_results["capital_validation"]
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("VaR (99%)",             f"₹{cv.get('var',0):,.0f}")
                c2.metric("Expected Shortfall",    f"₹{cv.get('expected_shortfall',0):,.0f}")
                c3.metric("Solvency Ratio",        f"{cv.get('solvency',0):.1f}%")
                c4.metric("Capital Adequacy Ratio",f"{cv.get('capital_adequacy',0):.2f}x")
                sol = cv.get("solvency", 0)
                if sol > 150:
                    st.success(cv.get("validation",""))
                elif sol > 120:
                    st.warning(cv.get("validation",""))
                else:
                    st.error(cv.get("validation",""))

            st.divider()

            # ── Model Validation ──────────────────────────────────────────────
            with st.expander("🤖 Model Validation"):
                mv = report_results["model_validation"]
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("AUC Score",      f"{mv.get('auc',0):.4f}")
                c2.metric("KS Statistic",   str(mv.get("ks","N/A")))
                c3.metric("Brier Score",    str(mv.get("brier","N/A")))
                c4.metric("PSI",            str(mv.get("psi","N/A")))
                status = mv.get("status","PASS")
                if status == "PASS":
                    st.success(f"Model Governance Status: **{status}** — metrics within acceptable actuarial governance thresholds.")
                else:
                    st.warning(f"Model Governance Status: **{status}** — review required before regulatory submission.")

                # Feature importance
                fi_list = report_results.get("feature_importance", [])
                if fi_list:
                    st.markdown("##### XGBoost Feature Importance")
                    fi_df = pd.DataFrame(fi_list)
                    if not fi_df.empty:
                        total_imp = fi_df["Importance"].sum() or 1
                        fi_df["% of Total"] = (fi_df["Importance"] / total_imp * 100).round(1)
                        fi_df["Importance"] = fi_df["Importance"].round(4)
                        st.dataframe(fi_df, use_container_width=True, hide_index=True)

            st.divider()

            # ── Risk Dashboard ────────────────────────────────────────────────
            with st.expander("⚠️ Risk Dashboard"):
                rd = report_results["risk_dashboard"]
                scores = rd.get("scores", {
                    "Insurance": rd.get("insurance",0),
                    "Market":    rd.get("market",0),
                    "Credit":    rd.get("credit",0),
                    "Operational":rd.get("operational",0),
                    "Catastrophe":rd.get("cat",0),
                })
                levels = rd.get("levels", {})

                # Score cards
                cols = st.columns(5)
                color_map = {"High":"🔴","Medium":"🟡","Low":"🟢"}
                for i, (cat, val) in enumerate(scores.items()):
                    lv = levels.get(cat, "Medium")
                    cols[i].metric(f"{color_map.get(lv,'')} {cat}", f"{val:.2f}/10", lv)

                dominant = rd.get("dominant","")
                dom_val  = rd.get("dominant_val", 0)
                st.warning(f"**Dominant Risk: {dominant}** ({dom_val:.2f}/10) — "
                           "Continued monitoring and targeted mitigation strategies are recommended.")

                # Per-category commentary
                commentary = rd.get("commentary", {})
                if commentary:
                    st.markdown("##### Risk Category Analysis")
                    for cat, text in commentary.items():
                        lv = levels.get(cat, "Medium")
                        fn = st.error if lv=="High" else st.warning if lv=="Medium" else st.success
                        fn(f"**{cat} Risk:** {text}")

            st.divider()

            # ── Forecast Assessment ───────────────────────────────────────────
            with st.expander("📊 Forecast Assessment"):
                fa = report_results["forecast_assessment"]

                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Next-Month Claims",  f"₹{fa.get('next_claim',0):,.0f}")
                c2.metric("Next-Month Premium", f"₹{fa.get('next_premium',0):,.0f}")
                c3.metric("Forecast LR",        f"{fa.get('fc_loss_ratio',0):.1f}%")
                c4.metric("Avg Severity",       f"₹{fa.get('avg_severity',0):,.0f}")

                cyoy = fa.get("claims_yoy")
                pyoy = fa.get("premium_yoy")
                if isinstance(cyoy, float) and isinstance(pyoy, float):
                    col_l, col_r = st.columns(2)
                    col_l.metric("Claims YoY",  f"{cyoy:+.1f}%",
                                 delta_color="inverse" if cyoy > 0 else "normal")
                    col_r.metric("Premium YoY", f"{pyoy:+.1f}%",
                                 delta_color="normal" if pyoy > 0 else "inverse")

                fc_lr = fa.get("fc_loss_ratio", 100)
                if fc_lr < 80:
                    st.success(fa.get("interpretation",""))
                elif fc_lr < 100:
                    st.warning(fa.get("interpretation",""))
                else:
                    st.error(fa.get("interpretation",""))

                # YoY trend table
                yoy_rows = fa.get("yoy_rows", [])
                if yoy_rows:
                    st.markdown("##### Year-on-Year Growth Trend")
                    yoy_df = pd.DataFrame(yoy_rows,
                        columns=["Month","Premium YoY","Claims YoY","Gap (pp)","Trend"])
                    st.dataframe(yoy_df, use_container_width=True, hide_index=True)

                # Seasonal table
                sea_rows = fa.get("sea_rows", [])
                if sea_rows:
                    st.markdown("##### Seasonal Index (100 = annual average)")
                    sea_df = pd.DataFrame(sea_rows,
                        columns=["Month","Claims Index","Premium Index","Assessment"])
                    st.dataframe(sea_df, use_container_width=True, hide_index=True)

                # Product forecast table
                prod_fc = fa.get("prod_fc_rows", [])
                if prod_fc:
                    st.markdown("##### Product Loss Ratio Analysis")
                    prod_fc_df = pd.DataFrame(prod_fc,
                        columns=["Product","Total Premium","Total Claims","Loss Ratio","Status"])
                    st.dataframe(prod_fc_df, use_container_width=True, hide_index=True)

            st.divider()

            # ── Stress Testing ────────────────────────────────────────────────
            with st.expander("⚡ Stress Testing Assessment"):
                sa = report_results["stress_assessment"]
                c1,c2,c3 = st.columns(3)
                c1.metric("Active Scenario",       sa.get("scenario",""))
                c2.metric("Stressed Combined Ratio",f"{sa.get('combined_ratio',0):.2f}%")
                c3.metric("Solvency Under Stress",  f"{sa.get('solvency',0):.2f}%")
                col_l, col_r = st.columns(2)
                col_l.metric("Capital Consumed",    f"₹{sa.get('capital_consumed',0):,.0f}")
                col_r.metric("Remaining Capital",   f"₹{sa.get('remaining_capital',0):,.0f}")
                if report_results.get("is_solvent", True):
                    st.success("Portfolio demonstrates capital resilience under the selected stress scenario.")
                else:
                    st.error("Capital shortfall identified. Immediate capital remediation action is required.")

                # All scenarios table
                all_sc = report_results.get("all_scenarios", [])
                if all_sc:
                    st.markdown("##### All Scenarios — Comparative Analysis")
                    sc_df = pd.DataFrame([{
                        "Scenario":          s.get("Label",""),
                        "Stressed CR (%)":   f"{s.get('Stressed CR (%)',0):.1f}%",
                        "Solvency (%)":      f"{s.get('Solvency Ratio (%)',0):.1f}%",
                        "Capital Consumed":  f"₹{s.get('Capital Consumed',0):,.0f}",
                        "Shortfall":         f"₹{s.get('Shortfall',0):,.0f}" if s.get('Shortfall',0) > 0 else "—",
                        "Solvent":           "✅" if s.get("Is Solvent", True) else "❌",
                    } for s in all_sc])
                    st.dataframe(sc_df, use_container_width=True, hide_index=True)
                    st.error("Stress testing demonstrates that catastrophic events remain "
                             "the largest threat to capital adequacy.")

            st.divider()

            # ── Chart Interpretations ─────────────────────────────────────────
            with st.expander("📊 Chart Interpretations"):
                commentary = report_results["chart_commentary"]
                labels = {
                    "loss_ratio":         "📊 Loss Ratio by Product",
                    "profitability":      "💰 Portfolio Profitability",
                    "feature_importance": "🤖 Feature Importance (XGBoost)",
                    "forecast":           "📈 Claims & Premium Forecast",
                    "stress_testing":     "⚡ Stress Testing Scenarios",
                }
                for key, label in labels.items():
                    text = commentary.get(key, "")
                    if text:
                        st.markdown(f"### {label}")
                        st.info(text)
                        st.divider()

            # ── Findings Register ─────────────────────────────────────────────
            st.subheader("🔎 Validation Findings Register")
            fr = report_results.get("findings_register", [])
            if fr:
                fr_df = pd.DataFrame([{
                    "ID":             f.get("ID",""),
                    "Finding":        f.get("Finding",""),
                    "Severity":       f.get("Severity",""),
                    "Recommendation": f.get("Recommendation",""),
                } for f in fr])
                st.dataframe(fr_df, use_container_width=True, hide_index=True)
            st.divider()

            # ── Management Action Plan ────────────────────────────────────────
            st.subheader("📋 Management Action Plan")
            for i, action in enumerate(report_results["management_actions"], start=1):
                st.success(f"Priority {i}: {action}")
            st.divider()

            # ── Actuarial Opinion ─────────────────────────────────────────────
            st.subheader("📜 Actuarial Opinion")
            st.info(report_results["actuarial_opinion"])
            st.divider()

            # ── Final Conclusion ──────────────────────────────────────────────
            st.subheader("🏆 Final Conclusion")
            col_r, col_h = st.columns([1,1])
            col_r.metric("Portfolio Rating", report_results["portfolio_rating"])
            col_h.metric("Health Score",     f"{report_results['health_score']}/100")
            final = report_results.get("final_conclusion","")
            if report_results.get("is_solvent", True):
                st.success(final)
            else:
                st.error(final)
            for cb in report_results.get("conclusion_bullets", []):
                st.write(f"• {cb}")
            st.divider()

            # ── Download ──────────────────────────────────────────────────────
            if report_results.get("report_bytes"):
                left, right = st.columns([8, 2])
                with right:
                    st.download_button(
                        "📥 Download Full Actuarial Report (PDF)",
                        data=report_results["report_bytes"],
                        file_name=report_results.get("report_filename", "CRIP_Actuarial_Report.pdf"),
                        mime="application/pdf",
                    )
            else:
                st.warning("PDF generation failed — check logs for details.")

            st.markdown("---")

            st.markdown("---")

            st.caption(
                "This report has been generated automatically by the CRIP AI Actuarial "
                "Reporting Engine. Results are intended for analytical decision support "
                "and should be reviewed by qualified actuarial professionals before "
                "regulatory submission."
            )