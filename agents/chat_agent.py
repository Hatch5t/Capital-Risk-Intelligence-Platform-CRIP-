import os
import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT BUILDER
# Flattens the report_results dict (from run_report_pipeline) into a rich,
# readable string that the LLM can reason over.
# ─────────────────────────────────────────────────────────────────────────────

def build_chat_context(report_results: dict) -> dict:
    """
    Convert the CRIP report_results dict into a flat key→value context
    that is easy to embed in an LLM prompt.
    """
    ctx = {}

    # ── Metadata ─────────────────────────────────────────────────────────────
    meta = report_results.get("metadata", {})
    ctx["Report Date"]        = meta.get("report_date", "N/A")
    ctx["Reporting Period"]   = meta.get("reporting_period", "N/A")
    ctx["Prepared By"]        = meta.get("prepared_by", "N/A")

    # ── Portfolio Summary ─────────────────────────────────────────────────────
    ctx["Portfolio Rating"]   = report_results.get("portfolio_rating", "N/A")
    ctx["Health Score"]       = f"{report_results.get('health_score', 'N/A')}/100"

    # ── Executive Summary ─────────────────────────────────────────────────────
    ctx["Executive Summary"]  = report_results.get("executive_summary", "N/A")

    # ── Key Findings ─────────────────────────────────────────────────────────
    findings = report_results.get("key_findings", [])
    if findings:
        ctx["Key Findings"] = " | ".join(findings)

    # ── Data Validation ───────────────────────────────────────────────────────
    dv = report_results.get("data_validation", {})
    ctx["Data Validation Status"]    = dv.get("status", "N/A")
    ctx["Total Policies"]            = dv.get("total_policies", "N/A")
    ctx["Missing Values (%)"]        = dv.get("missing_values", "N/A")
    ctx["Duplicate Records"]         = dv.get("duplicate_records", "N/A")
    ctx["Anomaly Rate (%)"]          = dv.get("anomaly_rate", "N/A")

    # ── Pricing Assessment ────────────────────────────────────────────────────
    pa = report_results.get("pricing_assessment", {})
    ctx["Combined Ratio"]            = pa.get("combined_ratio", "N/A")
    ctx["Loss Ratio"]                = pa.get("loss_ratio", "N/A")
    ctx["Expense Ratio"]             = pa.get("expense_ratio", "N/A")
    ctx["Pricing Interpretation"]    = pa.get("interpretation", "N/A")

    # ── Capital Validation ────────────────────────────────────────────────────
    cv = report_results.get("capital_validation", {})
    ctx["Solvency Ratio (%)"]        = cv.get("solvency", "N/A")
    ctx["VaR 99% (₹)"]              = cv.get("var", "N/A")
    ctx["Expected Shortfall (₹)"]   = cv.get("expected_shortfall", "N/A")
    ctx["Capital Validation"]        = cv.get("validation", "N/A")

    # ── Model Validation ──────────────────────────────────────────────────────
    mv = report_results.get("model_validation", {})
    ctx["Model AUC"]                 = mv.get("auc", "N/A")
    ctx["KS Statistic"]              = mv.get("ks", "N/A")
    ctx["Brier Score"]               = mv.get("brier", "N/A")
    ctx["PSI"]                       = mv.get("psi", "N/A")
    ctx["Model Validation Status"]   = mv.get("status", "N/A")

    # ── Risk Dashboard ────────────────────────────────────────────────────────
    rd = report_results.get("risk_dashboard", {})
    ctx["Insurance Risk Score"]      = rd.get("insurance", "N/A")
    ctx["Market Risk Score"]         = rd.get("market", "N/A")
    ctx["Credit Risk Score"]         = rd.get("credit", "N/A")
    ctx["Operational Risk Score"]    = rd.get("operational", "N/A")
    ctx["Catastrophe Risk Score"]    = rd.get("cat", "N/A")

    # ── Forecast Assessment ───────────────────────────────────────────────────
    fa = report_results.get("forecast_assessment", {})
    ctx["Forecast Claim Trend"]      = fa.get("claim_trend", "N/A")
    ctx["Forecast Premium Trend"]    = fa.get("premium_trend", "N/A")
    ctx["Forecast Interpretation"]   = fa.get("interpretation", "N/A")
    ctx["Next Month Claims (₹)"]    = fa.get("next_claims", "N/A")
    ctx["Next Month Premiums (₹)"]  = fa.get("next_premiums", "N/A")

    # ── Stress Testing ────────────────────────────────────────────────────────
    st_r = report_results.get("stress_testing", {})
    ctx["Stress Test Scenario"]      = st_r.get("scenario", "N/A")
    ctx["Post-Stress Solvency (%)"]  = st_r.get("post_stress_solvency", "N/A")
    ctx["Capital Shortfall (₹)"]    = st_r.get("capital_shortfall", "N/A")
    ctx["Stress Test Assessment"]    = st_r.get("assessment", "N/A")

    # ── Management Actions ────────────────────────────────────────────────────
    ma = report_results.get("management_actions", [])
    if ma:
        def _fmt_action(a):
            if isinstance(a, dict):
                return f"[{a.get('priority','?')}] {a.get('action','')}"
            return str(a)
        ctx["Management Actions"] = " | ".join(_fmt_action(a) for a in ma)

    # ── Findings Register ─────────────────────────────────────────────────────
    fr = report_results.get("findings_register", [])
    if fr:
        def _fmt_finding(f):
            if isinstance(f, dict):
                return f"{f.get('id','?')} ({f.get('severity','?')}): {f.get('finding','')}"
            return str(f)
        ctx["Findings Register"] = " | ".join(_fmt_finding(f) for f in fr)

    # ── Business Insights ─────────────────────────────────────────────────────
    def _bi_get(obj, key, fallback="N/A"):
        """Safe getter: works on dict, converts list/str to string."""
        if isinstance(obj, dict):
            return obj.get(key, fallback)
        if isinstance(obj, list):
            return " | ".join(str(x) for x in obj) if obj else fallback
        return str(obj) if obj else fallback

    bi = report_results.get("business_insights", {})
    if not isinstance(bi, dict):
        bi = {}

    ra = bi.get("rate_adequacy", {})
    if ra:
        ctx["Rate Adequacy — Action"]        = _bi_get(ra, "action")
        ctx["Rate Adequacy — Worst Product"] = _bi_get(ra, "worst_product")
        ctx["Rate Adequacy — Worst CR"]      = _bi_get(ra, "worst_cr")

    pc = bi.get("profitability_concentration", {})
    if pc:
        ctx["Profitability Concentration"]   = _bi_get(pc, "insight")

    cs = bi.get("cross_subsidisation", {})
    if cs:
        ctx["Cross-Subsidisation"]           = _bi_get(cs, "insight")

    fs = bi.get("freq_vs_severity", {})
    if fs:
        ctx["Frequency vs Severity"]         = _bi_get(fs, "insight")

    pg = bi.get("pricing_gap", {})
    if pg:
        ctx["Pricing Gap"]                   = _bi_get(pg, "insight")

    ee = bi.get("expense_efficiency", {})
    if ee:
        ctx["Expense Efficiency"]            = _bi_get(ee, "insight")

    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI MODEL — cached so it is only created ONCE per session, never on rerun
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _get_gemini_model():
    """
    Load and return the Gemini model exactly once.
    @st.cache_resource keeps the object alive across reruns so Streamlit
    never re-initialises it when the user sends a chat message.
    Returns None if no API key is configured.
    """
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception as e:
        st.warning(f"⚠️ Could not initialise Gemini: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CHAT HISTORY — stored in session_state so it survives reruns
# ─────────────────────────────────────────────────────────────────────────────

def init_chat_history():
    """
    Call this once at the top of your CRO Assistant page.
    Initialises st.session_state.crip_chat_messages if not already present.
    """
    if "crip_chat_messages" not in st.session_state:
        st.session_state.crip_chat_messages = []


def get_chat_history() -> list:
    """Return the current chat message list."""
    return st.session_state.get("crip_chat_messages", [])


def append_chat_message(role: str, content: str):
    """Append a message dict to the persistent chat history."""
    if "crip_chat_messages" not in st.session_state:
        st.session_state.crip_chat_messages = []
    st.session_state.crip_chat_messages.append({"role": role, "content": content})


# ─────────────────────────────────────────────────────────────────────────────
# CHAT RESPONSE GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_chat_response(prompt: str, context: dict) -> str:
    """
    Takes the user prompt and the dashboard context dictionary, and queries
    the cached Gemini model. Includes strict guardrails to prevent answering
    off-topic questions.
    """
    context_str = "\n".join([f"  • {k}: {v}" for k, v in context.items()])

    full_prompt = f"""You are the Chief Risk Officer (CRO) AI Assistant for CRIP — Capital Risk Intelligence Platform.

Your role is to answer questions about the actuarial and risk report generated for the currently loaded insurance portfolio. Use ONLY the data below. Do not make up numbers.

=== CRIP REPORT DATA ===
{context_str}
========================

GUIDELINES:
1. Answer questions about risk metrics, capital adequacy, pricing, model performance, forecasts, stress tests, findings, and business insights using the data above.
2. If a metric is not in the context say: "That metric is not available in the current report."
3. If the question is completely unrelated to insurance risk or this report, politely decline:
   "I am the CRIP Risk Assistant. I can only answer questions about the currently loaded risk report."
4. Keep answers concise, professional, and data-driven. Quote specific numbers.
5. Reference finding IDs (F001, F002…) and priority levels when discussing findings.
6. Interpret metrics in plain English — e.g. Combined Ratio > 1.0 means the product is unprofitable.

User question: {prompt}"""

    # ── Use the cached model ──────────────────────────────────────────────────
    model = _get_gemini_model()
    if model:
        try:
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"❌ Gemini error: {str(e)}"

    # ── Mock fallback (no API key set) ────────────────────────────────────────
    return (
        "**[No API key found]**\n\n"
        f"You asked: *\"{prompt}\"*\n\n"
        "To enable real AI answers:\n"
        "1. Get a **free** Gemini API key from https://aistudio.google.com/app/apikey\n"
        "2. Add `GEMINI_API_KEY=your-key-here` to your `.env` file\n"
        "3. Restart the Streamlit app\n\n"
        "**Current report data available:**\n"
        + "\n".join(f"- **{k}**: {v}" for k, v in context.items())
    )