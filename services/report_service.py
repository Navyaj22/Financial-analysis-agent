"""PDF (ReportLab) and CSV exports."""
from __future__ import annotations

import io
from typing import List
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle, KeepTogether)

from services import metrics_service as ms  # noqa: E402

DISCLAIMER = ("This report is generated for educational and informational purposes only. It is not financial, "
              "investment, tax or legal advice and does not recommend buying or selling any security. Data may be "
              "delayed, incomplete or inaccurate. Past performance does not guarantee future results.")
METHODOLOGY = [
    "Prices: split/dividend-adjusted daily closes from Yahoo Finance via yfinance (or a synthetic sample in demo mode).",
    "Period return = (last close / first close - 1) x 100.",
    "Daily return = (close_t / close_t-1 - 1) x 100.",
    "Annualized volatility = standard deviation of daily returns (sample, ddof=1) x sqrt(252).",
    "Maximum drawdown = minimum of (close / running maximum - 1) x 100.",
    "Moving averages are simple rolling means of closes (20 and 50 trading days).",
    "News sentiment uses a transparent keyword lexicon and is approximate; headlines are not independently verified.",
    "All figures are computed in Python (pandas/NumPy); any LLM text is labelled as interpretation.",
]
NAVY = colors.HexColor("#0B2545")


def _f(v, suffix="", d=2):
    return "N/A" if v is None else f"{v:,.{d}f}{suffix}"


def _chart_png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _charts(result) -> List[io.BytesIO]:
    df = ms.add_computed_columns(result.history)
    t, cur = result.analysis.ticker, result.analysis.currency
    out = []
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    ax.plot(df.index, df["Close"], label="Close", color="#0B2545", lw=1.4)
    ax.plot(df.index, df["MA20"], label="MA20", color="#E07A00", lw=1)
    ax.plot(df.index, df["MA50"], label="MA50", color="#2A9D8F", lw=1)
    ax.set(title=f"{t} adjusted close with moving averages", xlabel="Date", ylabel=f"Price ({cur})")
    ax.legend(); ax.grid(alpha=.3); fig.autofmt_xdate()
    out.append(_chart_png(fig))
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    r = df["DailyReturnPct"].dropna()
    ax.bar(r.index, r, color=["#2A9D8F" if x >= 0 else "#C8553D" for x in r], width=1.0)
    ax.set(title=f"{t} daily returns", xlabel="Date", ylabel="Return (%)"); ax.grid(alpha=.3); fig.autofmt_xdate()
    out.append(_chart_png(fig))
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    ax.bar(df.index, df["Volume"], color="#6C757D", width=1.0)
    ax.set(title=f"{t} trading volume", xlabel="Date", ylabel="Shares"); ax.grid(alpha=.3); fig.autofmt_xdate()
    out.append(_chart_png(fig))
    return out


def _table(rows, col_widths, header=True):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("FONTSIZE", (0, 0), (-1, -1), 9), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")])]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def build_pdf(result) -> bytes:
    a, rs, rp = result.analysis, result.research, result.report
    ss = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=ss["Title"], textColor=NAVY, fontSize=26, leading=32)
    h1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=NAVY, fontSize=15, spaceBefore=10)
    body = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=5)
    small = ParagraphStyle("S", parent=body, fontSize=8, leading=11, textColor=colors.HexColor("#555555"))
    cell = ParagraphStyle("C", parent=body, fontSize=8.5, leading=11, spaceAfter=0)
    centre = ParagraphStyle("Ce", parent=body, alignment=TA_CENTER, fontSize=12)
    P = lambda t, s=body: Paragraph(escape(str(t)), s)  # noqa: E731

    def section(name):
        sec = next((s for s in rp.sections if s.title == name), None)
        return [P(x) for x in sec.paragraphs] if sec else []

    story = [Spacer(1, 5 * cm), Paragraph("Financial Analysis Report", title),
             Paragraph(escape(f"{a.company_name} ({a.ticker})"), ParagraphStyle("c2", parent=centre, fontSize=18, leading=24)),
             Spacer(1, .5 * cm), P(f"Reporting period: {a.period_start} to {a.period_end}", centre),
             P(f"Generated: {rp.generated_at}", centre),
             P("Financial Analysis Agent Crew - AI-powered multi-agent financial research", centre)]
    if a.is_demo:
        story += [Spacer(1, 1 * cm), P("DEMO MODE - SYNTHETIC DATA - NOT REAL MARKET DATA", ParagraphStyle(
            "d", parent=centre, textColor=colors.HexColor("#C8553D"), fontName="Helvetica-Bold"))]
    story += [Spacer(1, 3 * cm), P(DISCLAIMER, small), PageBreak()]

    story += [Paragraph("1. Executive Summary", h1)] + section("Executive Summary")
    story += [Paragraph("2. Company Overview", h1)] + section("Company Overview")
    story += [Paragraph("3. Historical Price-Performance Analysis", h1)] + section("Financial Performance")

    k = a.kpis
    kpi_rows = [["Metric", "Value"],
                ["Latest price (" + a.currency + ")", f"{_f(a.latest_price)} ({a.latest_price_date})"],
                ["Period return", _f(k.get("period_return_pct"), "%")],
                ["Annualized volatility", _f(k.get("annualized_volatility_pct"), "%", 1)],
                ["Maximum drawdown", _f(k.get("max_drawdown_pct"), "%")],
                ["Avg daily return", _f(k.get("avg_daily_return_pct"), "%", 3)],
                ["Best / worst day", f"{_f(k.get('best_day_pct'), '%')} / {_f(k.get('worst_day_pct'), '%')}"],
                ["MA20 / MA50 (latest)", f"{_f(k.get('ma20_latest'))} / {_f(k.get('ma50_latest'))}"],
                ["Average volume", _f(k.get("avg_volume"), "", 0)],
                ["Volume trend (last 20d vs earlier)", _f(k.get("volume_trend_pct"), "%", 1)]]
    kpi_rows += [[n, _f(v)] for n, v in a.ratios.items()]
    story += [Paragraph("4. Financial KPI Table", h1), _table(kpi_rows, [9 * cm, 7 * cm]), PageBreak()]

    story.append(Paragraph("5. Charts and Visualizations", h1))
    for buf, h in zip(_charts(result), (7.5, 5.6, 5.6)):
        img = Image(buf, width=16.5 * cm, height=h / 7.5 * 7.2 * cm)
        story += [img, Spacer(1, .3 * cm)]
    story.append(PageBreak())

    story.append(Paragraph("6. Market News and Sentiment", h1))
    story += section("Market Sentiment")
    rows = [["Date", "Source", "Headline", "Tone"]]
    for n in rs.news:
        rows.append([n.published or "N/A", Paragraph(escape(n.publisher), cell), Paragraph(escape(n.title), cell), n.sentiment])
    if len(rows) > 1:
        story.append(_table(rows, [2.2 * cm, 3.3 * cm, 9.3 * cm, 1.9 * cm]))
    story += [Paragraph("7. Key Insights and Potential Risks", h1)] + section("Key Insights") + section("Risk Assessment")
    story += [Paragraph("8. Conclusion", h1)] + section("Conclusion")

    story += [PageBreak(), Paragraph("9. Methodology and Data Limitations", h1)]
    story += [P("- " + m) for m in METHODOLOGY] + [P("- " + m) for m in a.limitations + rs.limitations]
    story += [Paragraph("10. Sources and Timestamps", h1),
              P(f"Report narrative: {rp.narrative_source}. Price data retrieved: {a.retrieved_at}. "
                f"News retrieved: {rs.retrieved_at}. Report generated: {rp.generated_at}."),
              P("Price/company data: Yahoo Finance via yfinance." if not a.is_demo else "Price data: synthetic sample (data/sample_stock_data.csv).")]
    for n in rs.news:
        if n.url:
            story.append(P(f"{n.publisher} ({n.published or 'n.d.'}): {n.url}", small))
    story += [Paragraph("11. Disclaimer", h1), P(DISCLAIMER)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, "Educational use only - not financial advice")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                      title=rp.title, author="Financial Analysis Agent Crew").build(story, onFirstPage=lambda c, d: None,
                                                                                    onLaterPages=footer)
    return buf.getvalue()


def build_history_csv(result) -> bytes:
    df = ms.add_computed_columns(result.history)
    return df.round(4).to_csv().encode("utf-8")


def build_metrics_csv(result) -> bytes:
    import pandas as pd
    a = result.analysis
    rows = [("ticker", a.ticker), ("currency", a.currency), ("data_is_synthetic_demo", a.is_demo)]
    rows += [(k, v if v is not None else "N/A") for k, v in a.kpis.items()]
    rows += [(k, v if v is not None else "N/A") for k, v in a.ratios.items()]
    return pd.DataFrame(rows, columns=["metric", "value"]).to_csv(index=False).encode("utf-8")
