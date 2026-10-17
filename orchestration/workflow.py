"""Orchestrator: runs Market Research + Data Analyst concurrently, then the Report Writer.
Tracks real per-agent status/events/timings and retries recoverable failures."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, List, Optional

import pandas as pd

from agents import financial_data_analyst_agent, market_research_agent, report_writer_agent
from config.settings import Settings
from models.schemas import AgentStatus, AnalysisRequest, FinancialAnalysis, Report, ResearchSummary
from orchestration.crew import build_narrator
from services.financial_data_service import TransientDataError, now_iso
from services.retry import with_retries

MARKET, ANALYST, WRITER = "Market Research Agent", "Financial Data Analyst Agent", "Report Writer Agent"
AGENT_NAMES = [MARKET, ANALYST, WRITER]


class AnalysisFailed(Exception):
    def __init__(self, message: str, statuses: List[AgentStatus]):
        super().__init__(message)
        self.statuses = statuses


class StatusTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._s = {n: AgentStatus(name=n) for n in AGENT_NAMES}

    def start(self, name):
        with self._lock:
            s = self._s[name]
            s.state, s.started_at, s.message = "Running", time.time(), "Starting"
            s.attempts += 1

    def log(self, name, msg):
        with self._lock:
            s = self._s[name]
            s.events.append(f"{time.strftime('%H:%M:%S')}  {msg}")
            s.message = msg

    def complete(self, name):
        with self._lock:
            s = self._s[name]
            s.state, s.duration_s = "Completed", time.time() - (s.started_at or time.time())
            s.message = s.events[-1].split("  ", 1)[-1] if s.events else "Completed"

    def fail(self, name, err):
        with self._lock:
            s = self._s[name]
            s.state, s.error, s.message = "Failed", str(err), "Failed"
            if s.started_at:
                s.duration_s = time.time() - s.started_at

    def snapshot(self) -> List[AgentStatus]:
        with self._lock:
            return [self._s[n].model_copy(deep=True) for n in AGENT_NAMES]


@dataclass
class CrewResult:
    request: AnalysisRequest
    demo: bool
    research: ResearchSummary
    analysis: FinancialAnalysis
    history: pd.DataFrame
    report: Report
    statuses: List[AgentStatus]
    total_seconds: float
    generated_at: str


def _empty_research(request, reason, demo) -> ResearchSummary:
    return ResearchSummary(ticker=request.ticker, retrieved_at=now_iso(), is_demo=demo,
                           sentiment_counts={"positive": 0, "negative": 0, "neutral": 0},
                           limitations=[f"Market research unavailable: {reason}"])


def run_analysis(request: AnalysisRequest, settings: Settings, demo: bool = False,
                 tracker: Optional[StatusTracker] = None,
                 on_tick: Optional[Callable[[List[AgentStatus]], None]] = None,
                 poll_interval: float = 0.25) -> CrewResult:
    tracker = tracker or StatusTracker()
    t0 = time.time()

    def tick():
        if on_tick:
            on_tick(tracker.snapshot())

    def run_agent(name, fn):
        tracker.start(name)
        try:
            out = with_retries(lambda: fn(lambda m: tracker.log(name, m)), attempts=settings.max_retries,
                               backoff=1.0, retry_on=(TransientDataError,),
                               on_retry=lambda n, e: tracker.log(name, f"Retry {n} after error: {e}"))
            tracker.complete(name)
            return out
        except Exception as exc:
            tracker.fail(name, exc)
            raise

    def wait(futs):
        while not all(f.done() for f in futs):
            tick()
            time.sleep(poll_interval)
        tick()

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_res = ex.submit(run_agent, MARKET, lambda emit: market_research_agent.run(request, settings, demo, emit))
        f_ana = ex.submit(run_agent, ANALYST, lambda emit: financial_data_analyst_agent.run(request, settings, demo, emit))
        tick()
        wait([f_res, f_ana])

    try:
        analysis, history = f_ana.result()
    except Exception as exc:
        tracker.fail(WRITER, "Skipped: Financial Data Analyst Agent failed.")
        tick()
        raise AnalysisFailed(str(exc), tracker.snapshot()) from exc
    try:
        research = f_res.result()
    except Exception as exc:  # degrade gracefully: report still produced, limitation recorded
        research = _empty_research(request, str(exc), demo)

    narrator = build_narrator(settings)
    with ThreadPoolExecutor(max_workers=1) as ex:
        f_w = ex.submit(run_agent, WRITER, lambda emit: report_writer_agent.run(
            research, analysis, history, settings, emit, narrator))
        wait([f_w])
        try:
            report = f_w.result()
        except Exception as exc:
            raise AnalysisFailed(str(exc), tracker.snapshot()) from exc

    return CrewResult(request, demo, research, analysis, history, report, tracker.snapshot(),
                      time.time() - t0, now_iso())
