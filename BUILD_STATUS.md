# BUILD_STATUS

## Done (2026-10-13)
- Engine: data validation, Engle–Granger discovery with Benjamini–Hochberg FDR, static/rolling/Kalman hedges, signals, two-leg event-driven backtester, risk (VaR/ES, regimes, stress), walk-forward (parallel + cached), robustness grid, ML reversion filter, trend-cointegration option.
- Data providers: Yahoo (no key), Alpaca (history + live quotes), Finnhub (live quotes). Keys stay server-side, masked in responses, optionally saved to a gitignored `.env`.
- API: FastAPI layer over the engine (`api/server.py`), including `/api/live` for the live spread monitor.
- Web: Next.js landing page (globe, real walk-forward figure, findings) and a 9-page terminal (Overview, Discovery, Strategy, Backtest, Live, Risk, Walk-forward, Reports, Data) with custom SVG charts, headline numbers, mobile menu and loading skeletons.
- Legacy Streamlit UI (`app.py`) still runs.

## Verification (2026-10-13)
- pytest 54/54, ruff clean, TypeScript clean, ESLint clean, `next build` compiles all 12 routes.
- Live provider calls are tested against mocked HTTP only; not yet verified with real keys.

## Decisions
- Price field: adjusted close only. Execution at close t+lag (lag ≥ 1).
- Fixed Engle–Granger orientation; BH over all tested pairs.
- Kalman spread uses the prior (one-step-ahead) state; live z uses only loaded daily closes.
- ML hyper-parameters are fixed (no tuning on validation).

## Outstanding / ideas
- Verify Alpaca/Finnhub with real keys.
- Deploy (web + API) and add README screenshots.
- Per-user keys or rate limiting before any public deployment.

## Resume
```
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python -m uvicorn api.server:app --port 8000
npm --prefix web run dev
```
