from datetime import date, timedelta
import pytest
from config.settings import get_settings
from models.schemas import AnalysisRequest
from orchestration.workflow import AnalysisFailed, run_analysis
from services.report_service import build_history_csv, build_metrics_csv, build_pdf


@pytest.fixture(scope="module")
def result():
    req = AnalysisRequest(ticker="demo", start_date=date(2025, 1, 2), end_date=date(2025, 12, 30))
    return run_analysis(req, get_settings(), demo=True, poll_interval=0.01)


def test_all_agents_completed(result):
    assert [s.state for s in result.statuses] == ["Completed"] * 3
    assert all(s.events for s in result.statuses)


def test_report_content(result):
    titles = [s.title for s in result.report.sections]
    assert titles[0] == "Executive Summary" and "Risk Assessment" in titles and titles[-1] == "Conclusion"
    assert "DEMO" in result.report.sections[0].paragraphs[0]


def test_pdf_is_multipage(result):
    pdf = build_pdf(result)
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 4


def test_csv(result):
    assert b"DailyReturnPct" in build_history_csv(result)
    assert b"period_return_pct" in build_metrics_csv(result)


def test_live_failure_marks_writer_failed(monkeypatch):
    from services import financial_data_service as fds
    def boom(*a, **k):
        raise fds.DataUnavailableError("no data")
    monkeypatch.setattr(fds, "fetch_history", boom)
    req = AnalysisRequest(ticker="ZZZZ", start_date=date.today() - timedelta(days=100), end_date=date.today())
    with pytest.raises(AnalysisFailed) as e:
        run_analysis(req, get_settings(), demo=False, poll_interval=0.01)
    states = {s.name: s.state for s in e.value.statuses}
    assert states["Financial Data Analyst Agent"] == "Failed" and states["Report Writer Agent"] == "Failed"
