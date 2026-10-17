"""Agent 1 - Market Research. Gathers news, classifies sentiment, flags catalysts/risks.
Facts (headline, date, source) are kept separate from interpretations (sentiment/catalyst/risk flags)."""
from __future__ import annotations

from typing import Callable

from config.settings import Settings
from models.schemas import AnalysisRequest, ResearchSummary
from services import news_service as ns
from services.financial_data_service import now_iso

Emit = Callable[[str], None]


def run(request: AnalysisRequest, settings: Settings, demo: bool, emit: Emit) -> ResearchSummary:
    limits = ["News is limited to recent headlines from the provider and is not filtered to the selected date range.",
              "Sentiment is keyword-based and approximate; headlines are not verified by this system."]
    if demo:
        emit("Demo mode: loading synthetic sample headlines")
        news = ns.demo_news()
        limits = ["DEMO MODE: all headlines are synthetic and fictional."] + limits
    else:
        emit(f"Fetching news for {request.ticker}")
        news = ns.fetch_news(request.ticker, settings)
        emit(f"Retrieved {len(news)} unique headlines")
        if not news:
            limits.append("No news items were returned by the configured sources.")
    for n in news:
        n.sentiment = ns.score_sentiment(f"{n.title} {n.summary}")

    emit("Classifying sentiment, catalysts and risks")
    counts = {s: sum(1 for n in news if n.sentiment == s) for s in ("positive", "negative", "neutral")}
    overall = ("positive" if counts["positive"] > counts["negative"]
               else "negative" if counts["negative"] > counts["positive"] else "neutral")

    def tag(n):
        return f"{n.title} ({n.publisher}{', ' + n.published if n.published else ''})"

    events = [tag(n) for n in news[:5]]
    catalysts = [tag(n) for n in news if ns.flag_catalyst(n.title)][:5]
    risks = [tag(n) for n in news if ns.flag_risk(n.title)][:5]
    emit("Research summary ready")
    return ResearchSummary(ticker=request.ticker, retrieved_at=now_iso(), key_events=events, catalysts=catalysts,
                           risks=risks, sentiment_counts=counts, overall_sentiment=overall, news=news,
                           limitations=limits, is_demo=demo)
