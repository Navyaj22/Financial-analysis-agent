import pandas as pd
import streamlit as st

from components import charts
from services import metrics_service as ms


def _f(v, suffix="", d=2):
    return "N/A" if v is None else f"{v:,.{d}f}{suffix}"


def render_dashboard(result, pdf_bytes: bytes, hist_csv: bytes, metrics_csv: bytes):
    a, rs, rp, df = result.analysis, result.research, result.report, result.history
    k = a.kpis
    if a.is_demo:
        st.warning("DEMO MODE — all prices, headlines and ratios are synthetic and NOT real market data.")

    st.subheader(f"{a.company_name} · {a.ticker}")
    st.caption(f"Analysis period {a.period_start} → {a.period_end} · Latest price as of {a.latest_price_date} · "
               f"Data retrieved {a.retrieved_at} · Completed in {result.total_seconds:.1f}s")
    c = st.columns(4)
    c[0].metric("Latest price", f"{_f(a.latest_price)} {a.currency}", help=f"As of {a.latest_price_date}")
    c[1].metric("Period return", _f(k.get("period_return_pct"), "%"))
    c[2].metric("Annualized volatility", _f(k.get("annualized_volatility_pct"), "%", 1))
    c[3].metric("Max drawdown", _f(k.get("max_drawdown_pct"), "%"))

    left, right = st.columns(2)
    with left:
        st.markdown("**Key market developments**")
        for e in rs.key_events or ["No news available."]:
            st.markdown(f"- {e}")
    with right:
        st.markdown("**Important risks & data limitations**")
        for e in (rs.risks[:3] + a.limitations[:3] + rs.limitations[:1]):
            st.markdown(f"- {e}")

    t1, t2, t3, t4, t5 = st.tabs(["📈 Charts", "🔢 KPIs", "📰 News & sentiment", "💡 Insights & risks", "📄 Report"])
    with t1:
        o1, o2 = st.columns(2)
        ma20 = o1.checkbox("Show 20-day MA", True)
        ma50 = o2.checkbox("Show 50-day MA", True)
        st.plotly_chart(charts.price_chart(df, a.ticker, a.currency, ma20, ma50), use_container_width=True)
        st.plotly_chart(charts.returns_chart(df, a.ticker), use_container_width=True)
        if df["Volume"].notna().any():
            st.plotly_chart(charts.volume_chart(df, a.ticker), use_container_width=True)
        else:
            st.info("Volume data unavailable.")
        st.plotly_chart(charts.drawdown_chart(df, a.ticker), use_container_width=True)
    with t2:
        cols = st.columns(4)
        for i, (lab, key, suf, d) in enumerate([("Avg daily return", "avg_daily_return_pct", "%", 3),
                                               ("Best day", "best_day_pct", "%", 2), ("Worst day", "worst_day_pct", "%", 2),
                                               ("Volume trend", "volume_trend_pct", "%", 1)]):
            cols[i].metric(lab, _f(k.get(key), suf, d))
        rows = [("Start price", _f(k.get("start_price"))), ("End price", _f(k.get("end_price"))),
                ("MA20 (latest)", _f(k.get("ma20_latest"))), ("MA50 (latest)", _f(k.get("ma50_latest"))),
                ("Average volume", _f(k.get("avg_volume"), "", 0)), ("Trading days", _f(k.get("trading_days"), "", 0))]
        rows += [(n, _f(v)) for n, v in a.ratios.items()]
        st.dataframe(pd.DataFrame(rows, columns=["Metric", "Value"]), hide_index=True, use_container_width=True)
        st.caption("Computed in Python (pandas/NumPy). Unavailable values are shown as N/A, never estimated.")
    with t3:
        cnt = rs.sentiment_counts
        s = st.columns(4)
        s[0].metric("Positive", cnt.get("positive", 0)); s[1].metric("Negative", cnt.get("negative", 0))
        s[2].metric("Neutral", cnt.get("neutral", 0)); s[3].metric("Overall", rs.overall_sentiment.title())
        st.caption(f"News retrieved {rs.retrieved_at}. Sentiment is keyword-based and approximate.")
        for n in rs.news:
            tag = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}[n.sentiment]
            link = f"[{n.title}]({n.url})" if n.url else n.title
            st.markdown(f"{tag} {link}  \n<small>{n.publisher} · {n.published or 'date n/a'}</small>", unsafe_allow_html=True)
        if not rs.news:
            st.info("No news items available.")
    with t4:
        st.markdown("**Computed observations**")
        for o in a.observations:
            st.markdown(f"- {o}")
        st.markdown("**Possible catalysts (interpretation)**")
        for o in rs.catalysts or ["None identified in available headlines."]:
            st.markdown(f"- {o}")
        st.markdown("**Possible risks (interpretation)**")
        for o in rs.risks or ["None identified in available headlines."]:
            st.markdown(f"- {o}")
        st.markdown("**Data limitations**")
        for o in a.limitations + rs.limitations:
            st.markdown(f"- {o}")
    with t5:
        st.caption(f"Generated {rp.generated_at} · Narrative: {rp.narrative_source} · "
                   f"Sources: {'synthetic sample' if a.is_demo else 'Yahoo Finance (yfinance)'}"
                   f"{'' if a.is_demo else ', news per links above'}")
        for sec in rp.sections:
            st.markdown(f"### {sec.title}")
            for p in sec.paragraphs:
                st.markdown(p)
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Download PDF report", pdf_bytes, f"{a.ticker}_analysis_report.pdf", "application/pdf")
        d2.download_button("⬇️ Download CSV (history)", hist_csv, f"{a.ticker}_history.csv", "text/csv")
        d3.download_button("⬇️ Download CSV (metrics)", metrics_csv, f"{a.ticker}_metrics.csv", "text/csv")
    st.caption("Educational and informational use only. Not financial advice.")
