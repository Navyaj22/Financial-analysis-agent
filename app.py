"""Financial Analysis Agent Crew - Streamlit entry point."""
import datetime as dt

import streamlit as st
from pydantic import ValidationError

from components.agent_status import render_agent_cards
from components.dashboard import render_dashboard
from config.settings import get_settings
from models.schemas import AnalysisRequest
from orchestration.workflow import AGENT_NAMES, AnalysisFailed, run_analysis
from models.schemas import AgentStatus
from services.report_service import build_history_csv, build_metrics_csv, build_pdf

st.set_page_config(page_title="Financial Analysis Agent Crew", page_icon="📈", layout="wide")
settings = get_settings()

st.markdown("""<style>
.block-container{padding-top:1.5rem}
.hero{background:linear-gradient(90deg,#0B2545,#13315C);color:#fff;padding:1.2rem 1.5rem;border-radius:12px;margin-bottom:1rem}
.hero h1{margin:0;font-size:1.8rem;color:#fff}.hero p{margin:.2rem 0 0;color:#cfd8e3}
</style>
<div class="hero"><h1>📈 Financial Analysis Agent Crew</h1><p>AI-powered multi-agent financial research</p></div>""",
            unsafe_allow_html=True)
st.info("Educational and informational use only. Not financial advice.", icon="ℹ️")

if "ticker_input" not in st.session_state:
    st.session_state.ticker_input = "AAPL"


def _set(t):
    st.session_state.ticker_input = t


st.markdown("**Research input**")
ex = st.columns([1, 1, 1, 1, 1, 5])
for col, t in zip(ex, ["AAPL", "MSFT", "NVDA", "TSLA", "RELIANCE.NS"]):
    col.button(t, on_click=_set, args=(t,), key=f"ex_{t}")

with st.form("inputs"):
    c1, c2, c3 = st.columns([2, 1, 1])
    ticker = c1.text_input("Company ticker", key="ticker_input", help="e.g. AAPL, MSFT, NVDA, RELIANCE.NS")
    today = dt.date.today()
    start = c2.date_input("Start date", today - dt.timedelta(days=365), max_value=today)
    end = c3.date_input("End date", today, max_value=today)
    demo = st.checkbox("Demo mode (synthetic sample data, no internet or API keys needed)", value=False)
    st.caption("Prices are shown in each stock's listing currency; currency conversion is not supported. "
               + ("LLM narrative: ON." if settings.llm_enabled else "LLM narrative: OFF (deterministic report)."))
    submitted = st.form_submit_button("Generate Financial Analysis", type="primary")

cards = st.empty()

if submitted:
    try:
        request = AnalysisRequest(ticker=ticker, start_date=start, end_date=end)
    except ValidationError as e:
        st.error("; ".join(err["msg"].replace("Value error, ", "") for err in e.errors()))
    else:
        def tick(statuses):
            with cards.container():
                render_agent_cards(statuses)
        tick([AgentStatus(name=n) for n in AGENT_NAMES])
        try:
            result = run_analysis(request, settings, demo=demo, on_tick=tick)
            st.session_state.result = result
            st.session_state.pdf = build_pdf(result)
            st.session_state.hist_csv = build_history_csv(result)
            st.session_state.metrics_csv = build_metrics_csv(result)
        except AnalysisFailed as e:
            st.session_state.pop("result", None)
            st.error(f"Analysis failed: {e}  — Try another ticker/date range, or enable Demo mode.")
            with cards.container():
                render_agent_cards(e.statuses, show_log=True)

result = st.session_state.get("result")
if result is not None:
    with cards.container():
        render_agent_cards(result.statuses, show_log=True)
    render_dashboard(result, st.session_state.pdf, st.session_state.hist_csv, st.session_state.metrics_csv)
