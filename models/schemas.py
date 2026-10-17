"""Structured, validated data passed between the orchestrator and agents."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from services.validation import validate_date_range, validate_ticker

Sentiment = Literal["positive", "negative", "neutral"]
AgentState = Literal["Pending", "Running", "Completed", "Failed"]


class AnalysisRequest(BaseModel):
    ticker: str
    start_date: date
    end_date: date

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        return validate_ticker(v)

    @model_validator(mode="after")
    def _dates(self):
        validate_date_range(self.start_date, self.end_date)
        return self


class NewsItem(BaseModel):
    title: str
    publisher: str = "Unknown"
    url: str = ""
    published: Optional[str] = None
    summary: str = ""
    sentiment: Sentiment = "neutral"
    synthetic: bool = False


class ResearchSummary(BaseModel):
    ticker: str
    retrieved_at: str
    key_events: List[str] = Field(default_factory=list)
    catalysts: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    sentiment_counts: Dict[str, int] = Field(default_factory=dict)
    overall_sentiment: Sentiment = "neutral"
    news: List[NewsItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    is_demo: bool = False


class FinancialAnalysis(BaseModel):
    ticker: str
    company_name: str
    currency: str = "N/A"
    period_start: date
    period_end: date
    latest_price: Optional[float] = None
    latest_price_date: Optional[str] = None
    retrieved_at: str
    kpis: Dict[str, Optional[float]] = Field(default_factory=dict)
    ratios: Dict[str, Optional[float]] = Field(default_factory=dict)
    profile: Dict[str, Optional[str]] = Field(default_factory=dict)
    observations: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    is_demo: bool = False


class ReportSection(BaseModel):
    title: str
    paragraphs: List[str]


class Report(BaseModel):
    title: str
    generated_at: str
    narrative_source: str  # "deterministic" or "LLM (model name)"
    sections: List[ReportSection]


class AgentStatus(BaseModel):
    name: str
    state: AgentState = "Pending"
    message: str = "Waiting to start"
    events: List[str] = Field(default_factory=list)
    started_at: Optional[float] = None
    duration_s: Optional[float] = None
    error: Optional[str] = None
    attempts: int = 0
