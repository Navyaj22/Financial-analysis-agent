# 📈 Financial Analysis Agent Crew

AI-powered multi-agent financial research: three specialised agents research a listed company, analyse its price history, and write a professional report, shown on an interactive Streamlit dashboard and exportable as **PDF** and **CSV**.

> **Educational and informational use only. Not financial advice.**

## Features
- **Market Research Agent**: recent headlines (yfinance news; optional NewsAPI), sanitised, with dates + source URLs, keyword sentiment, catalysts and risks. Facts and interpretations are labelled separately.
- **Financial Data Analyst Agent**: prices + company info from Yahoo Finance; all KPIs computed in pandas/NumPy (return, volatility, max drawdown, MAs, volume trend, ratios). Missing values are shown as **N/A**, never invented.
- **Report Writer Agent**: consumes both agents' structured (pydantic) outputs and writes the report. Optional LLM interpretation via CrewAI, clearly labelled.
- **Orchestrator**: runs agents 1 and 2 **concurrently**, then agent 3; tracks real status/events/timings; retries transient failures; degrades gracefully if news fails; skips the writer if data fails.
- **Dashboard**: agent cards, executive summary, Plotly price/MA, returns, volume, drawdown charts, KPI table, news and sentiment, insights, downloads.
- **Demo mode**: synthetic sample data, no internet or keys needed (clearly watermarked as synthetic everywhere).

## Architecture
```
User Input (ticker, dates) → validation (pydantic)
        │
   Orchestrator (orchestration/workflow.py)
   ├─ thread 1: Market Research Agent  → ResearchSummary ┐
   └─ thread 2: Financial Data Analyst → FinancialAnalysis + price DataFrame ┤
                                                          ▼
                                   Report Writer Agent → Report
                                                          ▼
                                  Dashboard (Streamlit) + PDF (ReportLab) + CSV
```
```
app.py                    Streamlit entry point
config/settings.py        env-based settings (no secrets in code)
models/schemas.py         pydantic schemas passed between agents
agents/                   the three agents
orchestration/            workflow.py (executor, status, retries) · crew.py (optional CrewAI LLM)
services/                 data, news, metrics, validation, retry, PDF/CSV
components/               dashboard, charts, agent cards
tests/  data/
```
**Design decisions.** The orchestrator is a small explicit thread-based pipeline so that status, timing, retries and dependencies are real and testable. CrewAI is used for the Report Writer's LLM step (an `Agent`/`Task`/`Crew`) when an API key is set; the numbers always come from Python. News text is sanitised (HTML stripped, length-capped, instruction-like text dropped) and the LLM prompt marks headlines as untrusted data.

## Prerequisites
Python 3.10–3.12 and Git. Internet is needed for live mode only.

## Installation (Windows PowerShell)
```powershell
cd financial-analysis-agent-crew
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If activation is blocked:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env`

## Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `LLM_API_KEY` | Optional. Enables LLM-written interpretation via CrewAI |
| `LLM_MODEL` | Model string, e.g. `gemini/gemini-2.0-flash`, `gpt-4o-mini` |
| `NEWSAPI_KEY` | Optional extra news source |
| `REQUEST_TIMEOUT`, `MAX_RETRIES`, `CACHE_TTL_SECONDS` | Reliability tuning |

To use the LLM narrative also run `pip install -r requirements-llm.txt`. Without a key the report is generated deterministically.

## Run
```powershell
streamlit run app.py
```
Open http://localhost:8501, enter a ticker (AAPL, MSFT, NVDA, RELIANCE.NS…), pick dates, click **Generate Financial Analysis**, then use the **Report** tab to download the PDF/CSV.

### Demo mode (no internet or keys)
Tick **Demo mode** before generating. Uses `data/sample_stock_data.csv` (synthetic, seeded GBM; regenerate with `python data/generate_sample_data.py`).

## Tests
```powershell
pytest
```

## Calculation methods
Adjusted closes (splits/dividends). Period return = (last/first − 1)×100 · Daily return = (Cₜ/Cₜ₋₁ − 1)×100 · Annualized volatility = stdev(daily %, ddof=1)×√252 · Max drawdown = min(C/running max − 1)×100.

## Known limitations
- Yahoo Finance data is unofficial, may be delayed, rate-limited or incomplete; ratios are a latest snapshot, not aligned to the period.
- Prices are in each listing's currency; **currency conversion is not implemented**.
- News is recent-only (not filtered to the date range); sentiment is a simple keyword lexicon.
- The CrewAI/LLM path depends on your provider and model; it falls back to deterministic text on failure.
- yfinance may report network failures as "no data".

## Future enhancements
React frontend, FX conversion, peer comparison, better sentiment model, SEC filings ingestion, scheduled runs.
