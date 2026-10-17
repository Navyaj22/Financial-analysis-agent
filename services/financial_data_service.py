"""Historical prices + company info via yfinance, with validation, cleaning, caching, retries."""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from config.settings import Settings
from services.metrics_service import safe_float
from services.retry import with_retries
from services.validation import validate_date_range, validate_ticker  # re-exported

__all__ = ["validate_ticker", "validate_date_range", "DataUnavailableError", "TransientDataError",
           "clean_history", "fetch_history", "fetch_company_info", "load_demo_history", "extract_ratios"]

REQUIRED_COLS = ["Open", "High", "Low", "Close", "Volume"]


class DataUnavailableError(Exception):
    """Permanent: ticker unknown / no rows. Not retried."""


class TransientDataError(Exception):
    """Recoverable: network, timeout, rate limit. Retried."""


class _TTLCache:
    def __init__(self):
        self._d: Dict[Tuple, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key, ttl):
        with self._lock:
            hit = self._d.get(key)
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
        return None

    def set(self, key, value):
        with self._lock:
            self._d[key] = (time.time(), value)

    def clear(self):
        with self._lock:
            self._d.clear()


cache = _TTLCache()


def clean_history(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Normalise a raw price frame: tz-naive date index, sorted, de-duplicated,
    rows without a positive Close removed. Never invents values."""
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return pd.DataFrame(columns=REQUIRED_COLS)
    out = df.copy()
    idx = pd.DatetimeIndex(pd.to_datetime(out.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "Date"
    for c in REQUIRED_COLS:
        if c not in out.columns:
            out[c] = float("nan")
    out = out[REQUIRED_COLS].apply(pd.to_numeric, errors="coerce")
    out = out[out["Close"].notna() & (out["Close"] > 0)]
    out.loc[out["Volume"] < 0, "Volume"] = float("nan")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def fetch_history(ticker: str, start: date, end: date, settings: Settings,
                  on_retry=None) -> pd.DataFrame:
    key = ("hist", ticker, start, end)
    cached = cache.get(key, settings.cache_ttl)
    if cached is not None:
        return cached.copy()

    def _download() -> pd.DataFrame:
        try:
            import yfinance as yf
            raw = yf.Ticker(ticker).history(start=start.isoformat(),
                                            end=(end + timedelta(days=1)).isoformat(),
                                            auto_adjust=True, timeout=settings.request_timeout)
        except Exception as exc:  # network, timeout, rate limit...
            raise TransientDataError(f"Price request failed: {exc}") from exc
        df = clean_history(raw)
        if df.empty:
            raise DataUnavailableError(
                f"No price data returned for '{ticker}' between {start} and {end}. "
                "Check the ticker, date range and internet connection (Yahoo can also rate-limit), or try Demo mode.")
        return df

    df = with_retries(_download, attempts=settings.max_retries, backoff=1.0,
                      retry_on=(TransientDataError,), on_retry=on_retry)
    cache.set(key, df)
    return df.copy()


RATIO_MAP = {
    "P/E (trailing)": ("trailingPE", 1),
    "P/E (forward)": ("forwardPE", 1),
    "P/B": ("priceToBook", 1),
    "Debt-to-Equity": ("debtToEquity", 1),
    "Revenue growth (%)": ("revenueGrowth", 100),
    "Profit margin (%)": ("profitMargins", 100),
    "Operating margin (%)": ("operatingMargins", 100),
    "Return on equity (%)": ("returnOnEquity", 100),
    "Market cap": ("marketCap", 1),
}


def extract_ratios(info: Dict[str, Any]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    for label, (field, mult) in RATIO_MAP.items():
        v = safe_float(info.get(field))
        out[label] = v * mult if v is not None else None
    return out


def fetch_company_info(ticker: str, settings: Settings) -> Dict[str, Any]:
    """Best-effort company info. Failures return {} (metrics shown as N/A)."""
    key = ("info", ticker)
    cached = cache.get(key, settings.cache_ttl)
    if cached is not None:
        return dict(cached)
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    cache.set(key, info)
    return dict(info)


def load_demo_history(start: date, end: date, settings: Settings) -> Tuple[pd.DataFrame, str]:
    """Load the SYNTHETIC sample dataset, sliced to the range when it overlaps."""
    raw = pd.read_csv(settings.sample_data_path, parse_dates=["Date"], index_col="Date")
    df = clean_history(raw)
    sliced = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if len(sliced) >= 10:
        return sliced, "Synthetic sample data sliced to the selected range."
    return df, (f"Selected range {start}..{end} does not overlap enough with the synthetic sample "
                f"({df.index.min().date()}..{df.index.max().date()}); the full sample is shown instead.")


def now_iso() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
