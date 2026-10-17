import streamlit as st

ICON = {"Pending": "⏳", "Running": "🔄", "Completed": "✅", "Failed": "❌"}
DESC = {"Market Research Agent": "News, sentiment, catalysts, risks",
        "Financial Data Analyst Agent": "Prices, KPIs, charts, ratios",
        "Report Writer Agent": "Combines both into the report"}


def render_agent_cards(statuses, show_log=False):
    cols = st.columns(len(statuses))
    for col, s in zip(cols, statuses):
        with col, st.container(border=True):
            st.markdown(f"**{ICON[s.state]} {s.name}**")
            st.caption(DESC.get(s.name, "") + (f" · {s.duration_s:.1f}s" if s.duration_s is not None else ""))
            st.markdown(f"`{s.state}` — {s.message}")
            if s.error:
                st.error(s.error)
            if show_log and s.events:
                with st.expander("Execution log"):
                    for e in s.events:
                        st.text(e)
