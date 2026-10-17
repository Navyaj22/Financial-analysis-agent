"""News retrieval (yfinance news; optional NewsAPI), sanitisation and keyword sentiment."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.settings import Settings
from models.schemas import NewsItem

POSITIVE = {"beat", "beats", "surge", "surges", "record", "growth", "upgrade", "upgrades", "gain", "gains",
            "rally", "profit", "strong", "raises", "outperform", "approval", "approved", "partnership",
            "buyback", "launch", "launches", "expands", "soars", "boost"}
NEGATIVE = {"miss", "misses", "plunge", "plunges", "lawsuit", "probe", "investigation", "downgrade",
            "downgrades", "recall", "decline", "declines", "loss", "losses", "layoffs", "cuts", "weak",
            "fraud", "tariff", "tariffs", "fine", "fined", "falls", "drop", "drops", "warning", "risk"}
CATALYST_WORDS = {"earnings", "launch", "launches", "partnership", "upgrade", "approval", "approved",
                  "buyback", "guidance", "expands", "acquisition", "record", "raises"}
RISK_WORDS = {"lawsuit", "probe", "investigation", "downgrade", "recall", "layoffs", "tariff", "tariffs",
              "fine", "fined", "warning", "decline", "declines", "miss", "misses", "fraud", "cuts"}
INJECTION_RE = re.compile(
    r"(ignore (all|any|the|previous|prior)|disregard (all|any|the|previous)|system prompt|you are now|"
    r"new instructions|assistant\s*:|<\s*/?\s*system)", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def sanitize_text(text: Any, max_len: int = 400) -> str:
    """Strip HTML/control chars, collapse whitespace, truncate."""
    s = html.unescape(str(text or ""))
    s = TAG_RE.sub(" ", s)
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION_RE.search(text or ""))


def _words(text: str) -> set:
    return set(re.findall(r"[a-z']+", text.lower()))


def score_sentiment(text: str) -> str:
    w = _words(text)
    pos, neg = len(w & POSITIVE), len(w & NEGATIVE)
    return "positive" if pos > neg else "negative" if neg > pos else "neutral"


def flag_catalyst(text: str) -> bool:
    return bool(_words(text) & CATALYST_WORDS)


def flag_risk(text: str) -> bool:
    return bool(_words(text) & RISK_WORDS)


def _safe_url(u: Any) -> str:
    u = str(u or "").strip()
    return u if u.startswith(("http://", "https://")) else ""


def _parse_yf_item(item: Dict[str, Any]) -> Optional[NewsItem]:
    c = item.get("content") if isinstance(item.get("content"), dict) else item
    title = sanitize_text(c.get("title"), 200)
    if not title or looks_like_injection(title):
        return None
    url = ""
    for k in ("canonicalUrl", "clickThroughUrl"):
        if isinstance(c.get(k), dict) and c[k].get("url"):
            url = _safe_url(c[k]["url"])
            break
    url = url or _safe_url(c.get("link") or c.get("url"))
    prov = c.get("provider")
    publisher = sanitize_text(prov.get("displayName") if isinstance(prov, dict) else c.get("publisher"), 80) or "Unknown"
    pub: Optional[str] = None
    if c.get("pubDate"):
        pub = sanitize_text(c["pubDate"], 40)[:10]
    elif c.get("providerPublishTime"):
        pub = datetime.fromtimestamp(int(c["providerPublishTime"]), tz=timezone.utc).strftime("%Y-%m-%d")
    summary = sanitize_text(c.get("summary"), 300)
    if looks_like_injection(summary):
        summary = ""
    return NewsItem(title=title, publisher=publisher, url=url, published=pub, summary=summary,
                    sentiment=score_sentiment(f"{title} {summary}"))


def _fetch_yfinance(ticker: str) -> List[NewsItem]:
    import yfinance as yf
    out = []
    for it in (yf.Ticker(ticker).news or []):
        n = _parse_yf_item(it)
        if n:
            out.append(n)
    return out


def _fetch_newsapi(query: str, settings: Settings, limit: int) -> List[NewsItem]:
    import requests
    r = requests.get("https://newsapi.org/v2/everything",
                     params={"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": limit,
                             "apiKey": settings.newsapi_key},
                     timeout=settings.request_timeout)
    r.raise_for_status()
    out = []
    for a in r.json().get("articles", []):
        title = sanitize_text(a.get("title"), 200)
        if not title or looks_like_injection(title):
            continue
        summary = sanitize_text(a.get("description"), 300)
        if looks_like_injection(summary):
            summary = ""
        out.append(NewsItem(title=title, publisher=sanitize_text((a.get("source") or {}).get("name"), 80) or "Unknown",
                            url=_safe_url(a.get("url")), published=sanitize_text(a.get("publishedAt"), 10),
                            summary=summary, sentiment=score_sentiment(f"{title} {summary}")))
    return out


def fetch_news(ticker: str, settings: Settings, limit: int = 10) -> List[NewsItem]:
    """Raises on total failure of every source; returns [] if sources worked but found nothing."""
    items: List[NewsItem] = []
    errors = []
    try:
        items += _fetch_yfinance(ticker)
    except Exception as exc:
        errors.append(exc)
    if settings.newsapi_key:
        try:
            items += _fetch_newsapi(ticker, settings, limit)
        except Exception as exc:
            errors.append(exc)
    seen, uniq = set(), []
    for n in items:
        k = n.url or n.title
        if k not in seen:
            seen.add(k)
            uniq.append(n)
    if not uniq and errors:
        raise errors[0]
    uniq.sort(key=lambda n: n.published or "", reverse=True)
    return uniq[:limit]


def demo_news() -> List[NewsItem]:
    rows = [
        ("Demo Corp beats quarterly earnings expectations with record revenue", "positive"),
        ("Demo Corp announces partnership to expand cloud offerings", "positive"),
        ("Analysts debate valuation after strong rally in Demo Corp shares", "neutral"),
        ("Regulators open investigation into Demo Corp data practices", "negative"),
        ("Demo Corp faces tariff headwinds in overseas supply chain", "negative"),
        ("Demo Corp to present at industry conference next month", "neutral"),
    ]
    return [NewsItem(title=t, publisher="SYNTHETIC SAMPLE", url="", published=None,
                     summary="Synthetic headline for demo mode only.", sentiment=s, synthetic=True)
            for t, s in rows]
