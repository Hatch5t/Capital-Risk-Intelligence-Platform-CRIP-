import streamlit as st
import pandas as pd
import time
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
from agents.chat_agent        import generate_chat_response     # ← Agent 6
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

st.title("CRIP: Capital Risk Intelligence Platform")
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
    
    st.header("Forecasting Settings")
    forecast_periods = st.slider("Forecast horizon (months)", 3, 24, 12)

    st.divider()
    st.header("Stress Testing Settings")
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
    
    # ── Chat Container Placeholder ────────────────────────────────────────────────
    chat_container = st.container()

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

    if st.button("Run Agents", type="primary"):
        st.session_state.agents_run = True

    if st.session_state.get("agents_run", False):
        st.divider()

        # ── Agent 1: Data Governance ──────────────────────────────────────────
        with st.status("Agent 1: Data Governance Running...", expanded=True) as status1:
            st.write("Profiling dataset, detecting anomalies, imputing missing values...")
            time.sleep(0.5)
            gov_results = get_gov_results(df_raw)
            df_clean    = gov_results["df_clean"]
            status1.update(label=f"Data Governance complete — {len(df_clean):,} clean rows.", state="complete", expanded=False)

        # ── Agent 2: Pricing & Profitability ──────────────────────────────────
        with st.status("Agent 2: Pricing & Profitability Running...", expanded=True) as status2:
            st.write("Calculating Loss Ratios, Expense Ratios, Underwriting Profit...")
            time.sleep(0.5)
            pricing_results = get_pricing_results(df_clean)
            df_pricing      = pricing_results["df_pricing"]
            kpis            = pricing_results["kpis"]
            status2.update(label="Pricing Analysis complete!", state="complete", expanded=False)

        # ── Agent 3: Risk Intelligence & ML ──────────────────────────────────
        with st.status("Agent 3: Risk Intelligence & ML Running...", expanded=True) as status3:
            st.write("Calculating Risk Scores, Training XGBoost, running Monte Carlo...")
            time.sleep(0.5)
            risk_results       = get_risk_results(df_pricing)
            df_risk            = risk_results["df_risk"]
            feature_importance = risk_results["feature_importance"]
            portfolio_metrics  = risk_results["portfolio_metrics"]

            os.makedirs("reports", exist_ok=True)
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
                if "Model Governance & Validation Standards" in df_risk.columns:
                    df_risk["Model Governance & Validation Standards"].value_counts()\
                           .reset_index().rename(columns={"index": "Status",
                                                          "Model Governance & Validation Standards": "Count"})\
                           .to_excel(writer, sheet_name="Model Governance", index=False)
            status3.update(label="Risk Intelligence & ML complete!", state="complete", expanded=False)

        # ── Agent 4: Forecasting ──────────────────────────────────────────────
        with st.status(f"Agent 4: Time Series Forecasting Running... (Horizon: {forecast_periods}M)", expanded=True) as status4:
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
        with st.status(f"Agent 5: Stress Testing Running... ({SCENARIO_LABELS[selected_scenario]})", expanded=True) as status5:
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
            
        st.toast("Pipeline execution complete!")
        st.success("All AI Agents have successfully completed their analysis.")

        st.divider()

        # ── Results tabs ──────────────────────────────────────────────────────
        st.header("Reports")
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Data Governance",
            "Pricing & Profitability",
            "Risk Intelligence & ML",
            "Time Series Forecast",
            "Stress Testing",
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
                st.subheader("Loss Ratio by Product")
                lr_df = df_pricing.groupby("Product_Type")["Loss_Ratio"].mean().reset_index()
                st.plotly_chart(px.bar(lr_df, x='Product_Type', y='Loss_Ratio', color_discrete_sequence=['#0f4c81']), use_container_width=True)
                
                st.subheader("Profit by Product")
                prof_df = df_pricing.groupby("Product_Type")["Underwriting_Profit"].sum().reset_index()
                st.plotly_chart(px.bar(prof_df, x='Product_Type', y='Underwriting_Profit', color_discrete_sequence=['#0f4c81']), use_container_width=True)

            st.subheader("AI Pricing Insights")
            for _, row in df_pricing.groupby("Product_Type")["Combined_Ratio"].mean().reset_index().iterrows():
                product, ratio = row["Product_Type"], row["Combined_Ratio"]
                if ratio > 1:
                    st.error(f"**{product}**: Combined Ratio {ratio:.2f} → Underpriced. Immediate rate action required.")
                elif ratio < 0.80:
                    st.success(f"**{product}**: Combined Ratio {ratio:.2f} → Highly Profitable.")
                else:
                    st.warning(f"**{product}**: Combined Ratio {ratio:.2f} → Monitor Pricing.")

            st.subheader("Pricing Dataset Preview")
            csv = df_pricing.to_csv(index=False).encode('utf-8')
            st.download_button("Download Pricing Data", data=csv, file_name="pricing_data.csv", mime="text/csv")
            st.dataframe(df_pricing.head(50))

        # ── Tab 3: Risk Intelligence ──────────────────────────────────────────
        with tab3:
            st.subheader("Composite Risk Scores (Actuarial)")
            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            rc1.metric("Avg Insurance Risk",   f"{df_risk['Insurance_Risk'].mean():.1f}/10")
            rc2.metric("Avg Market Risk",      f"{df_risk['Market_Risk'].mean():.1f}/10")
            rc3.metric("Avg Credit Risk",      f"{df_risk['Credit_Risk'].mean():.1f}/10")
            rc4.metric("Avg Operational Risk", f"{df_risk['Operational_Risk'].mean():.1f}/10")
            rc5.metric("Avg CAT Risk",         f"{df_risk['Hazard_Score'].mean():.1f}/10")

            st.subheader("XGBoost Feature Importance")
            st.plotly_chart(px.bar(feature_importance, x='Importance', y='Feature', orientation='h', color_discrete_sequence=['#0f4c81']), use_container_width=True)

            st.subheader("Capital Adequacy & Monte Carlo (VaR)")
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
            st.subheader(f"Time Series Forecast — Next {forecast_periods} Months")
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
                        "Forecast":     fut_fc.set_index("ds")["yhat"],
                        "Upper Bound":  fut_fc.set_index("ds")["yhat_upper"],
                        "Lower Bound":  fut_fc.set_index("ds")["yhat_lower"],
                    }),
                    how="outer",
                )
                fig = px.line(chart_data, title="Claims Forecast", color_discrete_sequence=px.colors.qualitative.Plotly)
                st.plotly_chart(fig, use_container_width=True)

            # Premium forecast chart
            st.markdown("#### Premium Forecast")
            pfc_df = forecast_results["premium_forecast"]
            if not pfc_df.empty and not monthly.empty:
                fut_pfc = pfc_df[pd.to_datetime(pfc_df["ds"]) > last_hist]
                pchart  = pd.DataFrame({
                    "Actual Premium":  monthly.set_index("Month")["Written_Premium"],
                }).join(
                    pd.DataFrame({"Forecast": fut_pfc.set_index("ds")["yhat"]}),
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
            "Overall Combined Ratio": f"{pricing_summary['combined_ratio'] * 100:.1f}%",
            "Loss Making Products Count": len(pricing_summary['loss_making_products']),
            "High Risk Claims Detected": risk_kpis["high_risk_claims"],
            "Value at Risk (99%)": f"₹{risk_kpis['var_99']:.0f}",
        }
        if fkpis:
            dashboard_context["Next Month Claims Forecast"] = f"₹{fkpis.get('Next_Month_Claims_Fc', 0):.0f}"
        dashboard_context["Stress Scenario Solvency"] = f"{stress_results['solvency_ratio']:.1f}%"
        
        st.session_state.dashboard_context = dashboard_context

# ── Render Chat in Sidebar Container ──────────────────────────────────────────
with chat_container:
    st.divider()
    st.subheader("Chief Risk Officer Assistant")
    
    if "dashboard_context" not in st.session_state:
        st.info("Please upload a dataset and click 'Run Agents' to initialize the chat.")
    else:
        st.markdown("Ask me anything about the generated risk reports.")
        
        # Initialize Chat History
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        # Display History
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat Input
        with st.form("chat_form", clear_on_submit=True):
            prompt = st.text_input("Ask a question about the reports...", label_visibility="collapsed", placeholder="Type your question here...")
            submitted = st.form_submit_button("Send")
            
        if submitted and prompt:
            # Append User Message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # Generate AI Response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = generate_chat_response(prompt, st.session_state.dashboard_context)
                    st.markdown(response)
            
            # Append AI Message
            st.session_state.messages.append({"role": "assistant", "content": response})
