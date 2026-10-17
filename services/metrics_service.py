"""Financial metric calculations. All numbers are computed here with pandas/NumPy,
never by the language model.

Conventions
-----------
* Prices are split/dividend-adjusted closes (yfinance auto_adjust=True).
* Daily return  = (Close_t / Close_{t-1} - 1) * 100
* Period return = (Last / First - 1) * 100
* Annualized volatility = stdev(daily returns, ddof=1) * sqrt(252)   [daily returns already in %]
* Max drawdown  = min(Close / running_max - 1) * 100
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _clean(close: pd.Series) -> pd.Series:
    return close.dropna().astype(float)


def daily_returns(close: pd.Series) -> pd.Series:
    c = _clean(close)
    return ((c / c.shift(1) - 1) * 100).dropna()


def period_return(close: pd.Series) -> Optional[float]:
    c = _clean(close)
    if len(c) < 2 or c.iloc[0] <= 0:
        return None
    return float((c.iloc[-1] / c.iloc[0] - 1) * 100)


def annualized_volatility(close: pd.Series) -> Optional[float]:
    r = daily_returns(close)
    if len(r) < 2:
        return None
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def drawdown_series(close: pd.Series) -> pd.Series:
    c = _clean(close)
    return (c / c.cummax() - 1) * 100


def max_drawdown(close: pd.Series) -> Optional[float]:
    c = _clean(close)
    if len(c) < 2:
        return None
    return float(drawdown_series(c).min())


def moving_average(close: pd.Series, window: int) -> pd.Series:
    return _clean(close).rolling(window).mean()


def volume_trend(volume: pd.Series, window: int = 20) -> Optional[float]:
    """% change of the latest `window`-day average volume vs. the average of all earlier days."""
    v = volume.dropna().astype(float)
    if len(v) <= window:
        return None
    base = v.iloc[:-window].mean()
    if base <= 0:
        return None
    return float((v.iloc[-window:].mean() / base - 1) * 100)


def _last(s: pd.Series) -> Optional[float]:
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else None


def compute_kpis(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    close = df["Close"]
    r = daily_returns(close)
    c = _clean(close)
    return {
        "start_price": float(c.iloc[0]) if len(c) else None,
        "end_price": float(c.iloc[-1]) if len(c) else None,
        "period_return_pct": period_return(close),
        "annualized_volatility_pct": annualized_volatility(close),
        "max_drawdown_pct": max_drawdown(close),
        "avg_daily_return_pct": float(r.mean()) if len(r) else None,
        "best_day_pct": float(r.max()) if len(r) else None,
        "worst_day_pct": float(r.min()) if len(r) else None,
        "ma20_latest": _last(moving_average(close, 20)),
        "ma50_latest": _last(moving_average(close, 50)),
        "avg_volume": float(df["Volume"].mean()) if "Volume" in df and df["Volume"].notna().any() else None,
        "volume_trend_pct": volume_trend(df["Volume"]) if "Volume" in df else None,
        "trading_days": float(len(c)),
    }


def add_computed_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["DailyReturnPct"] = (out["Close"] / out["Close"].shift(1) - 1) * 100
    out["MA20"] = moving_average(out["Close"], 20)
    out["MA50"] = moving_average(out["Close"], 50)
    out["DrawdownPct"] = drawdown_series(out["Close"])
    return out


def safe_float(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None
