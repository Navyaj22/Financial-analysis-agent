"""Agent 2 - Financial Data Analyst. Pulls prices/info and computes KPIs with pandas/NumPy."""
from __future__ import annotations

from typing import Callable, Tuple

import pandas as pd

from config.settings import Settings
from models.schemas import AnalysisRequest, FinancialAnalysis
from services import financial_data_service as fds
from services import metrics_service as ms

Emit = Callable[[str], None]

DEMO_RATIOS = {"P/E (trailing)": 28.4, "P/B": 7.1, "Debt-to-Equity": 62.0,
               "Revenue growth (%)": 8.5, "Profit margin (%)": 21.3}


def _fmt(v, suffix="", d=2):
    return "N/A" if v is None else f"{v:,.{d}f}{suffix}"


def run(request: AnalysisRequest, settings: Settings, demo: bool, emit: Emit) -> Tuple[FinancialAnalysis, pd.DataFrame]:
    limits = []
    if demo:
        emit("Demo mode: loading synthetic price history")
        hist, note = fds.load_demo_history(request.start_date, request.end_date, settings)
        info = {"longName": "Demo Corp (SYNTHETIC SAMPLE)", "currency": "USD"}
        ratios = {k: None for k in fds.RATIO_MAP}
        ratios.update(DEMO_RATIOS)
        limits += ["DEMO MODE: prices, company profile and ratios are synthetic and NOT real market data.", note]
    else:
        emit(f"Downloading price history for {request.ticker}")
        hist = fds.fetch_history(request.ticker, request.start_date, request.end_date, settings,
                                 on_retry=lambda n, e: emit(f"Attempt {n} failed ({e}); retrying"))
        emit(f"{len(hist)} trading days retrieved; fetching company info")
        info = fds.fetch_company_info(request.ticker, settings)
        ratios = fds.extract_ratios(info)
        if not info:
            limits.append("Company information was unavailable; profile and ratios are shown as N/A.")

    if len(hist) < 30:
        limits.append(f"Only {len(hist)} trading days available; moving averages/volatility may be unreliable.")
    missing = [k for k, v in ratios.items() if v is None]
    if missing:
        limits.append("Not available from the data source (shown as N/A): " + ", ".join(missing) + ".")
    limits.append("Ratios are the provider's latest snapshot and may not align with the selected period or reporting dates.")
    limits.append("Prices are split/dividend-adjusted and in the listing currency; no currency conversion is applied.")

    emit("Computing KPIs (return, volatility, drawdown, moving averages, volume trend)")
    k = ms.compute_kpis(hist)
    cur = str(info.get("currency") or "N/A")
    obs = []
    if k["period_return_pct"] is not None:
        obs.append(f"The adjusted closing price moved from {_fmt(k['start_price'])} to {_fmt(k['end_price'])} "
                   f"{cur}, a period return of {_fmt(k['period_return_pct'], '%')}.")
    if k["annualized_volatility_pct"] is not None:
        obs.append(f"Annualized volatility was {_fmt(k['annualized_volatility_pct'], '%', 1)} "
                   f"(daily return standard deviation x sqrt(252)).")
    if k["max_drawdown_pct"] is not None:
        obs.append(f"The deepest peak-to-trough decline in the period was {_fmt(k['max_drawdown_pct'], '%')}.")
    if k["ma20_latest"] is not None and k["ma50_latest"] is not None:
        rel = "above" if k["ma20_latest"] > k["ma50_latest"] else "below"
        obs.append(f"The latest 20-day moving average ({_fmt(k['ma20_latest'])}) is {rel} the 50-day average "
                   f"({_fmt(k['ma50_latest'])}).")
    if k["volume_trend_pct"] is not None:
        obs.append(f"Average volume over the last 20 sessions is {_fmt(k['volume_trend_pct'], '%', 1)} versus the earlier period.")

    last_date = hist.index[-1].strftime("%Y-%m-%d")
    profile = {"Sector": info.get("sector"), "Industry": info.get("industry"), "Country": info.get("country"),
               "Website": info.get("website"),
               "Business summary": (info.get("longBusinessSummary") or "")[:700] or None}
    name = str(info.get("longName") or info.get("shortName") or request.ticker)
    emit("Financial analysis ready")
    return FinancialAnalysis(
        ticker=request.ticker, company_name=name, currency=cur, period_start=request.start_date,
        period_end=request.end_date, latest_price=k["end_price"], latest_price_date=last_date,
        retrieved_at=fds.now_iso(), kpis=k, ratios=ratios,
        profile={a: (str(b) if b else None) for a, b in profile.items()},
        observations=obs, limitations=limits, is_demo=demo), hist
