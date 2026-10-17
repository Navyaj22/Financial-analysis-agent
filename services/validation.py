"""Pure input-validation helpers (no network)."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

TICKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-=^]{0,11}$")
MIN_DAYS = 10


def validate_ticker(raw: str) -> str:
    t = (raw or "").strip().upper()
    if not t:
        raise ValueError("Please enter a ticker symbol (e.g. AAPL).")
    if not TICKER_RE.match(t):
        raise ValueError(f"'{raw}' is not a valid ticker. Use letters/digits and . - = ^ only (max 12 chars).")
    return t


def validate_date_range(start: date, end: date, today: Optional[date] = None) -> None:
    today = today or date.today()
    if start >= end:
        raise ValueError("Start date must be before end date.")
    if end > today:
        raise ValueError("End date cannot be in the future.")
    if start < date(1980, 1, 1):
        raise ValueError("Start date must be on or after 1980-01-01.")
    if (end - start).days < MIN_DAYS:
        raise ValueError(f"Date range must span at least {MIN_DAYS} days to compute meaningful metrics.")
