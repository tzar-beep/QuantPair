# QuantPair

A research workstation for **cointegration-based pairs trading**. It answers one question honestly: *can a statistical relationship between two instruments be turned into a strategy that survives costs and unseen data?* Positive, negative and inconclusive results are all reported as they are.

## Research question
Which instrument pairs are cointegrated on past data, does their spread mean-revert, and does a threshold strategy built on that spread remain profitable **after transaction costs** and **out of sample**?

## Pipeline
1. **Data:** adjusted daily closes from Yahoo Finance (`yfinance`), validated and never interpolated.
2. **Discovery:** test every unordered pair with Engle–Granger, apply Benjamini–Hochberg FDR control, estimate half-life, check hedge-ratio stability, and rank transparently.
3. **Spread model:** OLS hedge ratio (static or rolling) and a rolling z-score built only from past data.
4. **Signals:** entry, exit, stop and max-holding state machine.
5. **Backtest:** custom daily engine that trades both legs with lagged execution, fees, slippage, borrow costs and capital limits.
6. **Validation:** chronological train/validation/test split, walk-forward re-discovery, parameter and cost robustness, and benchmark comparison.
7. **Risk:** drawdown, rolling volatility and Sharpe, exposure and concentration, P&L and cost attribution, historical VaR/ES, and stress scenarios.
8. **Reports:** Markdown report, CSV and JSON exports, and a reproducible experiment log.

## Architecture
```
web/                       Next.js app: landing page (/) and research terminal (/app/*), hand-built SVG charts
api/server.py              FastAPI JSON layer over the engine (single-user, in-memory session)
app.py                     legacy Streamlit entry
views/                     8 pages: overview, pair_discovery, strategy_lab, backtesting,
                           risk, walk_forward, reports, settings_data
ui/                        state.py (session + caching), runs.py (jobs), components.py (styling)
src/quantpair/
  config.py                dataclass configs (JSON round-trip)
  data/                    market_data.py (yfinance, snapshots), validation.py (quality checks)
  analytics/market.py      returns, volatility, correlation, drawdown
  research/                spread_model.py (OLS, z-score, half-life, OU), pair_selection.py (EG, BH, ranking)
  strategy/                signals.py, position_sizing.py, pairs_strategy.py
  backtesting/             engine.py, costs.py, metrics.py
  risk/                    metrics.py (VaR/ES, attribution), stress_testing.py
  validation/              walk_forward.py, robustness.py
  reporting/               exports.py (CSV/JSON/experiment log), research_report.py
tests/                     pytest suite (synthetic deterministic data, no network)
```
The engine has no Streamlit dependency and is fully testable on its own.

## Setup (Windows PowerShell)
Prerequisites: Python 3.11+ (developed on 3.12) and internet access for live data.
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd web; npm install; cd ..
```

## Run
The primary interface is a Next.js web app (landing page + research terminal) built with Tailwind and hand-built SVG charts, talking to a FastAPI layer over the engine. Prerequisite: Node.js 20+.

Terminal 1 (engine API):
```powershell
.\.venv\Scripts\python -m uvicorn api.server:app --port 8000
```
Terminal 2 (web, first time run `npm install` inside `web/`):
```powershell
npm --prefix web run dev
```
Open http://localhost:3000 for the landing page, or http://localhost:3000/app for the terminal.

### Real-time data (optional API keys)
Yahoo needs no key. For keyed history and live quotes, open **Data → Data provider**:
- **Alpaca** (free at alpaca.markets): adjusted daily history and real-time last trades (IEX feed on the free plan).
- **Finnhub** (free at finnhub.io): real-time quotes.

Keys are kept on the API server, shown only masked, and, if "Remember" is ticked, saved to a gitignored `.env` (`ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `FINNHUB_API_KEY`). The **Live** page polls quotes for a watchlist of pairs and shows the live spread, an indicative z-score against the daily-close window, and the signal state.

The original Streamlit interface still works: `streamlit run app.py`.
Open http://localhost:8501. On **Research Overview**, click **Run first analysis**. This downloads data, discovers pairs on the training split and backtests the selected pairs on the validation split.

## Using it
| Task | Where |
|---|---|
| Download / refresh / validate data, edit the universe, save an offline snapshot, clear the cache | **Settings & Data** |
| Discover pairs (universe, window, α, FDR q, half-life band, rank weights); diagnostics per pair | **Pair Discovery** |
| Explore signals for one pair; save parameters to the experiment | **Strategy Lab** |
| Backtest top-k FDR, raw-p (exploratory) or manual pairs on validation, train, final test or custom dates | **Backtesting** |
| VaR/ES, exposure, attribution, cost/volatility/spread stress | **Risk Analytics** |
| IS/validation/test table, walk-forward, robustness grid | **Walk-Forward Validation** |
| Markdown report, CSV/JSON exports, experiment log and reproduction | **Research Reports** |

## Tests and lint
```powershell
python -m pytest -q
ruff check .
```
The suite contains 54 tests covering data validation, returns, hedge ratios, z-score leakage, half-life, BH correction, discovery-window isolation, signal orientation, hand-computed backtest P&L, costs on both legs, borrow fees, execution lag, capital limits, the equity identity, end-of-test policy, Sharpe edge cases, VaR/ES, walk-forward chronology, future-data invariance, reproducibility, parallel-vs-serial equality, Kalman causality, regime causality, ML label/feature leakage, trend recovery, trend-cointegration detection and trend extrapolation from the fit window only, and the data-provider adapters and live monitor (against mocked HTTP, no keys needed).

## The mathematics, briefly
- **Cointegration.** Two prices can each wander like random walks, yet a combination `y − α − βx` (the *spread*) can stay stationary. The **Engle–Granger** test regresses y on x and checks the residual for a unit root. It uses MacKinnon critical values, which account for β having been estimated. A plain ADF test on that same residual is too lenient, so QuantPair shows it only as a descriptive diagnostic.
- **Multiple testing.** 15 tickers give 105 pairs. At α = 5%, about 5 pairs would pass by luck alone. **Benjamini–Hochberg** sorts the p-values and accepts the pairs with `p(k) ≤ k·q/m`, which controls the expected share of false discoveries at q. This assumes independent or positively dependent tests; pairs that share a leg are dependent, so the control is approximate.
- **Half-life.** QuantPair fits `Δs_t = a + b·s_{t−1} + e`. The spread closes its gap at rate (1+b) per day, so the half-life is `−ln2 / ln(1+b)`. This is only meaningful for −1 < b < 0. Significance comes from the Dickey–Fuller p-value, because the t-statistic of b is not Student-t under a unit root.
- **Ornstein–Uhlenbeck.** `ds = θ(μ − s)dt + σdW` maps to an AR(1) with φ = e^(−θ). The stationary standard deviation is σ/√(2θ). This assumes constant parameters and Gaussian shocks.
- **Z-score.** `z_t = (s_t − mean_w) / std_w` over the trailing window ending at t. It never uses future data.
- **Positions.** Long spread means +1 share of y and −β shares of x, sized so that gross notional equals `alloc × equity`. A negative β gives two legs with the same sign, which is still the correct hedge.
- **Execution.** A signal formed at the close of t trades at the close of t+lag, with lag ≥ 1. It can never earn the move that created it.
- **Metrics.** 252 sessions per year. Sharpe is `mean(r − rf/252)/std(r)·√252`, reported as "—" when there are fewer than 20 observations or zero volatility. Sortino uses downside deviation. Calmar is CAGR/|MaxDD|. Profit factor is gross wins divided by gross losses.
- **VaR/ES.** Historical simulation on daily equity returns. VaR = −quantile(r, 1−a), and ES is the mean loss beyond VaR.

## Key assumptions
- Prices are split- and dividend-adjusted closes; adjusted and unadjusted prices are never mixed. Missing sessions stay missing, and a leg with no price cannot trade that day.
- Pair selection and hedge fitting use only the fit window. The fit window is stored with every result.
- The optional trend term (`coint_trend="ct"`) adds γt to the hedge regression. The traded spread then subtracts the γt extrapolated from the fit window, which assumes the drift rate persists.
- Costs: fee and slippage bps on traded notional, charged per leg; borrow bps per year on short notional, charged daily. Defaults are 1, 5 and 25 bps.
- Capital: each new position gets `alloc_per_pair × equity` of gross exposure, and an entry is rejected if total gross would exceed `max_gross_leverage × equity`. Rejected signals are skipped, not entered late.
- Shares stay fixed while a position is open (no re-hedging). Positions are liquidated at the end of a test, or carried and marked as open if you choose that.
- The risk-free rate defaults to 0 and is configurable.
- Walk-forward liquidates at each window boundary and carries equity forward.

## Known limitations
- Execution is close-to-close with linear costs: no market impact, partial fills, open prices or intraday data. This does not replicate a live broker.
- No interest on cash or margin. Borrow availability and recalls are not modelled, and the borrow fee is a flat rate.
- **Survivorship bias:** the universe is chosen today, so delisted names are missing.
- Yahoo adjusted prices are restated over time, and the provider can rate-limit or change without notice.
- Engle–Granger tests one orientation (y = first ticker), which is chosen deterministically.
- Walk-forward discovery runs in parallel processes and is cached: about 20 s for 15 tickers over 20 windows (91 s serially), and under 1 s for a rerun with only strategy or cost changes. Results are identical to a serial run (tested).
- The ML model uses scikit-learn's HistGradientBoosting (the same model family as XGBoost) to avoid an extra dependency. Hyper-parameters are fixed and untuned.

## Research extensions
- **Universe presets** (Settings & Data): consumer staples, banks, energy, utilities, and a positive control of near-identical assets.
- **Kalman hedge ratio** (`hedge_method="kalman"`): random-walk coefficients with one-step-ahead (prior) estimates, so the spread at t uses only data before t. Strategy Lab compares static OLS, rolling OLS and Kalman β over time and in a backtest. Caveat: an adaptive hedge can absorb genuine divergence and weaken the reversion signal.
- **Volatility regimes** (Risk Analytics): SPY 63-day realised volatility against its expanding median (past data only). Each day's return is matched to the regime known at the previous close, and the page shows per-regime statistics and shaded equity.
- **ML reversion filter** (Walk-Forward → ML tab): the label is whether z reverts inside the exit band within H sessions, with labels purged at segment ends. Features are causal (z, Δz, spread-volatility ratio, trailing half-life, correlation, β instability, market volatility). The model is compared with a logistic baseline on |z|, with permutation importance, and in a filtered vs unfiltered strategy backtest.

## Findings (live data 2015-01-02 → 2026-10-09, default settings, retrieved 2026-10-11)
Discovery uses the training split (2015–2022) and the backtest uses validation (2022–2024). Walk-forward uses a 2-year train / 6-month test and runs to the present. The ML filter is trained on train and evaluated on validation, using the top-5 pairs by score (exploratory).

| Universe preset | Pairs tested | raw p<.05 | BH-significant | Validation (pairs · Sharpe · trades) | Walk-forward (windows traded · trades · return · Sharpe) | ML AUC vs \|z\| baseline |
|---|---|---|---|---|---|---|
| Default ETFs + large caps | 105 | 10 | 0 | none · cash | 3 · 21 · +0.9% · 0.08 | 0.60 vs 0.71 |
| Consumer staples | 45 | 8 | 1 | PG/MDLZ · 0.30 · 10 | 4 · 26 · +6.3% · 0.54 | 0.66 vs 0.66 |
| US banks | 36 | 3 | 0 | none · cash | 1 · 2 · +0.7% · 0.50 | 0.64 vs 0.70 |
| Energy | 36 | 1 | 0 | none · cash | 3 · 13 · +3.5% · 0.40 | 0.72 vs 0.70 |
| Utilities | 36 | 2 | 0 | none · cash | 4 · 24 · +0.9% · 0.28 | 0.63 vs 0.66 |
| Positive control | 21 | 2 | 2 | GOOGL/GOOG · −0.44 · 20 | 4 · 31 · +0.4% · 0.04 | 0.75 vs 0.54 |

What this shows:
- **Cointegration that survives FDR is rare.** Only consumer staples (PG/MDLZ) and the positive control produce a discovery on the training split. Raw p<.05 counts are close to the 5% of tests expected by chance, which shows why the correction matters.
- **Out-of-sample edges are small and statistically weak.** Walk-forward Sharpe ratios fall between 0.04 and 0.54, from only 2–31 trades over about 10 years. None of this is evidence of a robust strategy.
- **The positive control is informative.** GOOGL/GOOG (share classes) is detected, but trading it loses money: the spread is tiny, so costs dominate. GLD/IAU is *not* detected (p = 0.17), because the expense-ratio difference creates a slow deterministic drift that a constant-only Engle–Granger test reads as non-stationarity. See the trend-term results below.
- **The ML filter does not reliably beat the |z| rule.** It loses on AUC in 4 of 6 universes. In Energy the filtered strategy reached Sharpe 1.25 against −0.19 unfiltered, but that is one validation period, exploratory pairs and the best of 6 universes, so treat it as a hypothesis, not a result.

### Constant vs constant + linear trend (Pair Discovery → "Deterministic terms")
The test regresses `y = α + γt + βx` and uses Engle–Granger with `trend="ct"`. The fitted γ is extrapolated from the fit window when trading.

| Universe | BH-significant (c → ct) | Validation Sharpe (c → ct) | Walk-forward return (c → ct) |
|---|---|---|---|
| Positive control | 2 → 9 of 21 | −0.44 → 0.64 | +0.4% → −4.3% |
| Consumer staples | 1 → 1 of 45 (PG/MDLZ → PEP/HSY) | 0.30 → 0.43 | +6.3% → +4.8% |
| Utilities | 0 → 0 of 36 | cash → cash | +0.9% → +0.2% |

- **It fixes the intended case.** GLD/IAU goes from p = 0.17 to p = 0.001 (q = 0.03) once the fee drift is modelled. Its half-life is about 0.5 days, though, so it fails the tradeability band and is not traded.
- **It also inflates false positives.** Unrelated trending assets (VOO/GOOG, SPY/GOOG) become "cointegrated around a trend". Their good validation result did not survive walk-forward (−4.3%). The default therefore stays constant-only; use the trend option deliberately, for near-identical assets.
