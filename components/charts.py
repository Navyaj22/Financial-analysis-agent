"""Plotly chart builders for the dashboard."""
from __future__ import annotations

import plotly.graph_objects as go

from services import metrics_service as ms

LAYOUT = dict(template="plotly_white", hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10), height=380)


def price_chart(df, ticker, currency, show_ma20=True, show_ma50=True):
    d = ms.add_computed_columns(df)
    fig = go.Figure()
    fig.add_scatter(x=d.index, y=d["Close"], name="Close", line=dict(color="#0B2545", width=2),
                    hovertemplate="%{y:,.2f} " + currency)
    if show_ma20:
        fig.add_scatter(x=d.index, y=d["MA20"], name="MA20", line=dict(color="#E07A00", width=1))
    if show_ma50:
        fig.add_scatter(x=d.index, y=d["MA50"], name="MA50", line=dict(color="#2A9D8F", width=1))
    fig.update_layout(title=f"{ticker} adjusted close price", xaxis_title="Date",
                      yaxis_title=f"Price ({currency})", **LAYOUT)
    return fig


def returns_chart(df, ticker):
    r = ms.daily_returns(df["Close"])
    fig = go.Figure(go.Bar(x=r.index, y=r, marker_color=["#2A9D8F" if v >= 0 else "#C8553D" for v in r],
                           hovertemplate="%{y:.2f}%"))
    fig.update_layout(title=f"{ticker} daily returns", xaxis_title="Date", yaxis_title="Daily return (%)", **LAYOUT)
    return fig


def volume_chart(df, ticker):
    fig = go.Figure(go.Bar(x=df.index, y=df["Volume"], marker_color="#6C757D", hovertemplate="%{y:,.0f} shares"))
    fig.update_layout(title=f"{ticker} trading volume", xaxis_title="Date", yaxis_title="Shares traded", **LAYOUT)
    return fig


def drawdown_chart(df, ticker):
    dd = ms.drawdown_series(df["Close"])
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color="#C8553D"), hovertemplate="%{y:.2f}%"))
    fig.update_layout(title=f"{ticker} drawdown from running peak", xaxis_title="Date", yaxis_title="Drawdown (%)", **LAYOUT)
    return fig
