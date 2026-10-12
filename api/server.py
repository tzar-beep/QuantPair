"""QuantPair HTTP API - a thin JSON layer over the research engine.

Run:  .venv\\Scripts\\python -m uvicorn api.server:app --port 8000
Single-user local research tool: state lives in process memory.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import PlainTextResponse, Response  # noqa: E402

from quantpair.analytics.market import drawdown, log_returns, rolling_volatility  # noqa: E402
from quantpair.backtesting.metrics import sharpe_ratio  # noqa: E402
from quantpair.config import (  # noqa: E402
    BENCHMARK,
    UNIVERSE_PRESETS,
    BacktestConfig,
    CostConfig,
    DiscoveryConfig,
    ExperimentConfig,
    StrategyConfig,
    WalkForwardConfig,
    _from_dict,
)
from quantpair.data import providers  # noqa: E402
from quantpair.data.market_data import DataFetchError, fetch_prices, load_snapshot, save_snapshot, snapshot_info  # noqa: E402
from quantpair.data.validation import clean_prices  # noqa: E402
from quantpair.reporting.exports import csv_bytes, load_experiments, make_experiment, save_experiment, to_jsonable  # noqa: E402
from quantpair.reporting.research_report import build_report  # noqa: E402
from quantpair.research.live import live_reading  # noqa: E402
from quantpair.research.ml_reversion import MLConfig, run_ml_study  # noqa: E402
from quantpair.research.pair_selection import select_pairs  # noqa: E402
from quantpair.research.spread_model import (  # noqa: E402
    compute_spread,
    fit_ou,
    kalman_hedge_ratio,
    rolling_hedge_ratio,
    rolling_zscore,
)
from quantpair.risk.metrics import (  # noqa: E402
    exposure_concentration,
    historical_var_es,
    pair_attribution,
    rolling_sharpe,
    tail_summary,
)
from quantpair.risk.regimes import regime_performance, volatility_regime  # noqa: E402
from quantpair.risk.stress_testing import cost_stress, pair_scenarios, volatility_stress  # noqa: E402
from quantpair.strategy.pairs_strategy import build_pair_signals  # noqa: E402
from quantpair.validation.robustness import (  # noqa: E402
    buy_and_hold,
    parameter_grid,
    relationship_stability_warning,
    research_warnings,
    run_grid,
)
from quantpair.validation.walk_forward import (  # noqa: E402
    chronological_split,
    discover_many,
    run_pipeline,
    split_evaluation,
    walk_forward,
)

providers.load_env_file()
app = FastAPI(title="QuantPair API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
S: dict = {"cfg": ExperimentConfig()}


# ---------- helpers
def J(obj):
    return to_jsonable(obj)


def series(*cols: tuple[str, pd.Series], step: int = 1) -> list[dict]:
    """Merge named series into [{date, a, b, ...}] rows for charts."""
    df = pd.concat({k: v for k, v in cols}, axis=1).iloc[::step]
    out = []
    for t, row in df.iterrows():
        rec = {"date": str(t)[:10]}
        for k, v in row.items():
            rec[k] = None if pd.isna(v) else round(float(v), 6)
        out.append(rec)
    return out


def records(df: pd.DataFrame) -> list[dict]:
    return J(df.replace([np.inf, -np.inf], np.nan).astype(object).where(df.notna(), None).to_dict("records"))


def need_data() -> pd.DataFrame:
    if "prices" not in S:
        raise HTTPException(409, "No market data loaded. Load data first.")
    return S["prices"]


def splits() -> dict:
    c = S["cfg"]
    return chronological_split(need_data().index, c.train_frac, c.val_frac)


def universe() -> list[str]:
    p = need_data()
    return [t for t in S["cfg"].universe if t in p.columns]


def windows_for(segment: str, custom: dict | None = None):
    sp = splits()
    if segment == "train":
        return sp["train"], sp["train"]
    if segment == "validation":
        return sp["train"], sp["validation"]
    if segment == "test":
        return (sp["train"][0], sp["validation"][1]), sp["test"]
    if not custom:
        raise HTTPException(422, "Custom segment needs fit/eval dates.")
    return ((pd.Timestamp(custom["fit_start"]), pd.Timestamp(custom["fit_end"])),
            (pd.Timestamp(custom["eval_start"]), pd.Timestamp(custom["eval_end"])))


def discovery_for(fit) -> object:
    c = S["cfg"]
    return discover_many(need_data(), universe(), c.discovery, [fit])[0]


def apply_cfg(body: dict) -> ExperimentConfig:
    c = S["cfg"]
    try:
        for key, cls in (("discovery", DiscoveryConfig), ("strategy", StrategyConfig),
                         ("walkforward", WalkForwardConfig)):
            if body.get(key):
                setattr(c, key, cls(**{**asdict(getattr(c, key)), **body[key]}))
        if body.get("backtest"):
            b = {**asdict(c.backtest), **body["backtest"]}
            b["costs"] = CostConfig(**{**asdict(c.backtest.costs), **(body["backtest"].get("costs") or {})})
            c.backtest = BacktestConfig(**b)
        for k in ("train_frac", "val_frac"):
            if k in body:
                setattr(c, k, float(body[k]))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"Invalid settings: {exc}") from exc
    return c


def status() -> dict:
    base = {"config": asdict(S["cfg"]), "presets": UNIVERSE_PRESETS, "snapshot": snapshot_info(),
            "loaded": "prices" in S}
    if "prices" in S:
        p, rep, meta = S["prices"], S["report"], S["meta"]
        sp = splits()
        base.update(data={"source": meta.source, "is_snapshot": meta.is_snapshot, "retrieved_at": meta.retrieved_at,
                          "failed": meta.failed, "tickers": list(p.columns), "start": rep.start, "end": rep.end,
                          "sessions": rep.n_dates, "common_dates": rep.common_dates, "errors": rep.n_errors,
                          "warnings": rep.n_warnings},
                    splits={k: [str(v[0])[:10], str(v[1])[:10]] for k, v in sp.items()})
        d = S.get("discovery")
        if d is not None:
            base["discovery"] = {"window": d.window, "n_tested": d.n_tested, "n_significant": d.n_significant,
                                 "n_eligible": d.n_eligible, "n_tickers": len(d.tickers)}
        if "bt" in S:
            base["last_backtest"] = {"segment": S["bt"]["segment"], "metrics": J(S["bt"]["pipe"].backtest.metrics)}
        if "wf" in S:
            w = S["wf"]
            base["walkforward"] = {"windows": len(w.windows), "trades": int(w.windows["n_trades"].sum()),
                                   "return": float(w.equity.iloc[-1] / S["cfg"].backtest.initial_capital - 1)}
    return J(base)


# ---------- meta & data
@app.get("/api/status")
def get_status():
    return status()


@app.post("/api/config")
def post_config(body: dict):
    if "universe" in body:
        S["cfg"].universe = [t.strip().upper() for t in body["universe"] if t.strip()]
    if "start" in body:
        S["cfg"].start = body["start"]
    if "end" in body:
        S["cfg"].end = body["end"] or None
    apply_cfg(body)
    return status()


@app.post("/api/config/reset")
def reset_config():
    S["cfg"] = ExperimentConfig()
    return status()


@app.post("/api/data/load")
def load(body: dict):
    c = S["cfg"]
    if body.get("universe"):
        c.universe = [t.strip().upper() for t in body["universe"] if t.strip()]
    c.start = body.get("start", c.start)
    c.end = body.get("end", c.end) or None
    try:
        if body.get("source") == "snapshot":
            data = load_snapshot()
        elif body.get("source") == "alpaca":
            data = providers.fetch_prices_alpaca(list(dict.fromkeys(c.universe + [BENCHMARK])), c.start, c.end)
        else:
            data = fetch_prices(list(dict.fromkeys(c.universe + [BENCHMARK])), c.start, c.end)
    except DataFetchError as exc:
        raise HTTPException(502, str(exc)) from exc
    prices, rep = clean_prices(data.prices, min_obs=c.discovery.min_obs)
    if data.is_snapshot:
        prices = prices.loc[c.start:c.end] if c.end else prices.loc[c.start:]
    for k in ("discovery", "bt", "wf", "grid", "split", "ml"):
        S.pop(k, None)
    S.update(prices=prices, report=rep, meta=data)
    return status()


@app.post("/api/data/snapshot")
def snapshot():
    if "meta" not in S or S["meta"].is_snapshot:
        raise HTTPException(409, "Load live data first.")
    return {"path": str(save_snapshot(S["meta"]))}


@app.get("/api/data/quality")
def quality():
    need_data()
    rep = S["report"]
    return {"summary": records(rep.summary.astype({c: str for c in ("first", "last")})),
            "issues": records(rep.issues_frame())}


@app.get("/api/data/prices")
def prices(tickers: str):
    p = need_data()
    cols = [t for t in tickers.split(",") if t in p.columns]
    norm = {t: 100 * p[t] / p[t].dropna().iloc[0] for t in cols}
    return series(*norm.items(), step=2)


# ---------- data providers & live quotes
@app.get("/api/providers")
def provider_status():
    return providers.key_status()


@app.post("/api/providers/keys")
def provider_keys(body: dict):
    """Set API keys. Values are kept server-side; responses only ever contain masked hints."""
    mapping = {"alpaca_key_id": "ALPACA_API_KEY_ID", "alpaca_secret": "ALPACA_API_SECRET_KEY", "finnhub_key": "FINNHUB_API_KEY"}
    values = {env: body[k] for k, env in mapping.items() if k in body}
    try:
        providers.set_keys(values, persist=bool(body.get("persist")))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return providers.key_status()


@app.post("/api/providers/test")
def provider_test(body: dict):
    try:
        return providers.test_connection(body.get("provider", "auto"))
    except DataFetchError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/api/live")
def live(pairs: str, provider: str = "auto"):
    """Live quotes and indicative spread z-scores for 'Y/X,Y2/X2' using the current model and daily history."""
    p, c = need_data(), S["cfg"]
    plist = [tuple(x.split("/")) for x in pairs.split(",") if "/" in x][:12]
    if not plist:
        raise HTTPException(422, "Pass pairs as Y/X, comma separated.")
    syms = sorted({t for pr in plist for t in pr})
    missing = [t for t in syms if t not in p.columns]
    if missing:
        raise HTTPException(422, f"No daily history loaded for: {', '.join(missing)}")
    try:
        quotes = providers.latest_quotes(syms, provider)
    except DataFetchError as exc:
        raise HTTPException(502, str(exc)) from exc
    d = S.get("discovery")
    fit = (pd.Timestamp(d.window[0]), pd.Timestamp(d.window[1])) if d else splits()["train"]
    rows = []
    for y, x in plist:
        if y not in quotes or x not in quotes:
            rows.append({"pair": f"{y}/{x}", "error": "no quote"})
            continue
        r = live_reading(p, y, x, quotes[y].price, quotes[x].price, c.strategy, fit)
        rows.append({**r.__dict__, "time_y": quotes[y].time, "time_x": quotes[x].time})
    return J({"provider": next(iter(quotes.values())).source if quotes else provider, "rows": rows,
              "entry_z": c.strategy.entry_z, "exit_z": c.strategy.exit_z,
              "quotes": {k: {"price": q.price, "time": q.time} for k, q in quotes.items()}})


# ---------- discovery
@app.post("/api/discovery")
def discovery(body: dict):
    p = need_data()
    c = apply_cfg(body)
    if body.get("universe"):
        c.universe = body["universe"]
    win = splits()["train"] if not body.get("window") else (pd.Timestamp(body["window"][0]),
                                                            pd.Timestamp(body["window"][1]))
    res = discover_many(p, universe(), c.discovery, [win])[0]
    S["discovery"] = res
    return discovery_table()


@app.get("/api/discovery")
def discovery_table():
    res = S.get("discovery")
    if res is None:
        return {"ran": False}
    cols = ["pair", "y", "x", "n_obs", "return_corr", "price_corr", "beta", "intercept", "trend", "eg_stat",
            "eg_pvalue", "q_value", "adf_pvalue_naive", "half_life", "half_life_note", "beta_cv", "evidence",
            "stability", "history", "score", "raw_pass", "fdr_pass", "hl_ok", "eligible", "status"]
    t = res.table
    t = t[t["status"] == "tested"] if "status" in t else t.iloc[0:0]
    return J({"ran": True, "window": res.window, "n_candidates": res.n_candidates, "n_tested": res.n_tested,
              "n_raw": int(t["raw_pass"].sum()) if len(t) else 0, "n_significant": res.n_significant,
              "n_eligible": res.n_eligible, "excluded": res.excluded, "tickers": res.tickers,
              "alpha": S["cfg"].discovery.coint_alpha, "q": S["cfg"].discovery.fdr_q,
              "rows": records(t[[k for k in cols if k in t]])})


@app.get("/api/pair")
def pair(y: str, x: str):
    p, res, c = need_data(), S.get("discovery"), S["cfg"]
    if res is None:
        raise HTTPException(409, "Run discovery first.")
    row = res.table.set_index("pair").loc[f"{y}/{x}"]
    w = p.loc[res.window[0]:res.window[1], [y, x]].dropna()
    sp = compute_spread(w[y], w[x], row.beta, row.intercept, row.get("trend", 0.0))
    z = rolling_zscore(sp, c.strategy.lookback)
    rb = rolling_hedge_ratio(w[y], w[x], c.discovery.stability_window, c.discovery.use_intercept)["beta"]
    ou = fit_ou(sp)
    warn = []
    if not row.fdr_pass:
        warn.append("Not significant after FDR correction - treat any pattern as likely noise.")
    if not row.hl_ok:
        warn.append(f"Half-life outside the tradeable band or unreliable ({row.half_life_note}).")
    if row.beta_cv > 0.25:
        warn.append(f"Hedge ratio unstable over rolling windows (CV {row.beta_cv:.2f}).")
    return J({"stats": {k: row.get(k) for k in ("beta", "intercept", "trend", "eg_pvalue", "q_value", "adf_pvalue_naive",
                                                 "half_life", "beta_cv", "n_obs", "return_corr", "price_corr",
                                                 "fdr_pass", "eligible")},
              "ou": asdict(ou), "window": res.window, "warnings": warn,
              "prices": series((y, 100 * w[y] / w[y].iloc[0]), (x, 100 * w[x] / w[x].iloc[0]), step=2),
              "spread": series(("spread", sp), ("mean", sp * 0 + sp.mean()), ("upper", sp * 0 + sp.mean() + 2 * sp.std()),
                               ("lower", sp * 0 + sp.mean() - 2 * sp.std()), step=2),
              "z": series(("z", z), step=2),
              "beta": series(("rolling", rb), ("static", rb * 0 + row.beta), step=2)})


@app.get("/api/correlation")
def correlation():
    p, res = need_data(), S.get("discovery")
    if res is None:
        raise HTTPException(409, "Run discovery first.")
    corr = log_returns(p.loc[res.window[0]:res.window[1], res.tickers]).corr().round(3)
    return {"tickers": list(corr.columns), "matrix": J(corr.values.tolist())}


# ---------- strategy lab
@app.post("/api/signals")
def signals(body: dict):
    p, res = need_data(), S.get("discovery")
    if res is None:
        raise HTTPException(409, "Run discovery first.")
    c = apply_cfg(body)
    strat = replace(c.strategy, use_trend=c.discovery.coint_trend == "ct" and c.strategy.hedge_method == "static_ols")
    fit = (pd.Timestamp(res.window[0]), pd.Timestamp(res.window[1]))
    seg = body.get("segment", "validation")
    ev = fit if seg == "discovery" else splits()["validation"]
    sig = build_pair_signals(p, body["y"], body["x"], strat, fit, ev)
    f = sig.frame
    from quantpair.backtesting.engine import run_backtest
    m = run_backtest(p, [sig], c.backtest, *ev).metrics
    yy, xx = p[body["y"]].loc[:ev[1]], p[body["x"]].loc[:ev[1]]
    rol = rolling_hedge_ratio(yy, xx, strat.hedge_window, strat.use_intercept)["beta"].loc[ev[0]:]
    kal = kalman_hedge_ratio(yy, xx, strat.kalman_delta, use_intercept=strat.use_intercept)["beta"].loc[ev[0]:]
    ev_rows = f[f["event"] != ""]
    return J({"in_sample": ev[0] <= fit[1], "fit": res.window, "eval": [str(ev[0])[:10], str(ev[1])[:10]],
              "series": series(("spread", f["spread"]), ("z", f["z"]), ("position", f["position"].astype(float))),
              "betas": series(("rolling", rol), ("kalman", kal), ("active", f["beta"]), step=2),
              "events": [{"date": str(t)[:10], "event": e, "z": None if pd.isna(z) else float(z)}
                         for t, e, z in zip(ev_rows.index, ev_rows["event"], ev_rows["z"])],
              "counts": f["event"].value_counts().drop("", errors="ignore").to_dict(),
              "time_in_position": float((f["position"] != 0).mean()), "metrics": m})


# ---------- backtest
@app.post("/api/backtest")
def backtest(body: dict):
    p, c = need_data(), apply_cfg(body)
    seg = body.get("segment", "validation")
    fit, ev = windows_for(seg, body.get("custom"))
    disc = discovery_for(fit)
    if seg != "test":
        S["discovery"] = disc
    sel = body.get("selection", "fdr")
    manual = body.get("manual") or []
    pairs = disc.table[disc.table["pair"].isin(manual)] if sel == "manual" else None
    pipe = run_pipeline(p, universe(), fit, ev, c.discovery, c.strategy, c.backtest,
                        int(body.get("top_k", c.walkforward.top_k)), "fdr" if sel == "manual" else sel,
                        discovery=disc, pairs=pairs)
    bench = buy_and_hold(p, BENCHMARK, ev[0], ev[1], c.backtest.initial_capital)
    S["bt"] = {"pipe": pipe, "segment": seg, "bench": bench, "selection": sel}
    S.pop("cost_stress", None)
    return backtest_result()


@app.get("/api/backtest")
def backtest_result():
    if "bt" not in S:
        return {"ran": False}
    bt = S["bt"]
    pipe, r = bt["pipe"], bt["pipe"].backtest
    k0 = r.config.initial_capital
    cols = [("net", (r.equity / k0 - 1) * 100), ("gross", (r.gross_equity / k0 - 1) * 100)]
    if bt["bench"] is not None:
        cols.append(("benchmark", (bt["bench"] / k0 - 1) * 100))
    dd = drawdown(pd.concat([pd.Series([k0], index=[r.equity.index[0] - pd.Timedelta(days=1)]), r.equity])).iloc[1:]
    act = r.returns[r.returns != 0] * 100
    hist = []
    if len(act) > 1:
        cnt, edges = np.histogram(act, bins=40)
        hist = [{"bin": round(float((edges[i] + edges[i + 1]) / 2), 4), "count": int(cnt[i])} for i in range(len(cnt))]
    att = pair_attribution(r.pair_pnl, r.pair_gross_pnl, r.pair_costs).reset_index(names="pair") if r.pairs else pd.DataFrame()
    trades = r.trades.copy()
    for col in ("signal_date", "entry_date", "exit_date"):
        if col in trades:
            trades[col] = trades[col].astype(str).str[:10].replace("NaT", None)
    return J({"ran": True, "segment": seg_label(bt["segment"]), "selection": bt["selection"],
              "in_sample": pipe.in_sample, "fit": [str(pipe.fit_window[0])[:10], str(pipe.fit_window[1])[:10]],
              "eval": [str(pipe.eval_window[0])[:10], str(pipe.eval_window[1])[:10]],
              "pairs": list(pipe.selected["pair"]) if len(pipe.selected) else [],
              "metrics": r.metrics, "equity": series(*cols), "drawdown": series(("drawdown", dd * 100)),
              "histogram": hist, "attribution": records(att) if len(att) else [],
              "cum_pair": series(*[(k, r.pair_pnl[k].cumsum()) for k in r.pairs]) if r.pairs else [],
              "trades": records(trades), "config": asdict(r.config),
              "warnings": research_warnings(r) + relationship_stability_warning(pipe.selected)})


def seg_label(s: str) -> str:
    return {"train": "In-sample (train)", "validation": "Validation", "test": "Final test", "custom": "Custom"}.get(s, s)


# ---------- risk
@app.get("/api/risk")
def risk(level: float = 0.95, window: int = 0, roll: int = 63, regime_window: int = 63):
    if "bt" not in S:
        raise HTTPException(409, "Run a backtest first.")
    p, r, pipe = need_data(), S["bt"]["pipe"].backtest, S["bt"]["pipe"]
    ve = historical_var_es(r.returns, level, window or None)
    reg_perf, reg_series = [], []
    if BENCHMARK in p:
        reg = volatility_regime(p[BENCHMARK], regime_window)
        reg_perf = records(regime_performance(r.returns, reg))
        rr = reg.shift(1).reindex(r.returns.index)
        reg_series = [{"date": str(t)[:10], "high": v == "high-vol"} for t, v in rr.items()]
    conc = exposure_concentration(r.pair_gross_exposure)
    budget = r.config.alloc_per_pair * r.config.initial_capital
    scen = [row | {"pair": s.name} for s in pipe.signals
            for row in records(pair_scenarios(s, budget, borrow_bps=r.config.costs.borrow_bps_annual))]
    return J({"var": ve, "tail": tail_summary(r.returns), "max_drawdown": r.metrics["max_drawdown"],
              "drawdown": series(("drawdown", drawdown(r.equity) * 100)),
              "rolling": series(("vol", rolling_volatility(r.returns, roll) * 100),
                                ("sharpe", rolling_sharpe(r.returns, roll, r.config.risk_free_rate))),
              "exposure": series(("gross", r.exposure["gross_pct"] * 100), ("net", r.exposure["net_pct"] * 100),
                                 ("max_pair_share", conc["max_share"] * 100)),
              "costs": series(*[(k, r.costs[k].cumsum()) for k in r.costs]),
              "attribution": records(pair_attribution(r.pair_pnl, r.pair_gross_pnl, r.pair_costs)
                                     .reset_index(names="pair")) if r.pairs else [],
              "regimes": reg_perf, "regime_series": reg_series, "scenarios": scen,
              "vol_stress": records(volatility_stress(r.returns, (1.0, 1.5, 2.0, 3.0), level)),
              "cost_stress": records(S["cost_stress"]) if "cost_stress" in S else None})


@app.post("/api/risk/cost-stress")
def risk_cost(body: dict):
    if "bt" not in S:
        raise HTTPException(409, "Run a backtest first.")
    pipe = S["bt"]["pipe"]
    S["cost_stress"] = cost_stress(need_data(), pipe.signals, pipe.backtest.config, *pipe.eval_window,
                                   tuple(body.get("multipliers", (1.0, 2.0, 3.0))))
    return records(S["cost_stress"])


# ---------- validation
@app.post("/api/splits")
def split_eval(body: dict):
    p, c = need_data(), apply_cfg(body)
    t = split_evaluation(p, universe(), splits(), c.discovery, c.strategy, c.backtest, c.walkforward.top_k,
                         body.get("selection", "fdr"), bool(body.get("include_test")))
    S["split"] = t
    return records(t)


@app.post("/api/walkforward")
def wf(body: dict):
    p, c = need_data(), apply_cfg(body)
    res = walk_forward(p, universe(), c.discovery, c.strategy, c.backtest, c.walkforward,
                       final_test_start=splits()["test"][0])
    S["wf"] = res
    return wf_result()


@app.get("/api/walkforward")
def wf_result():
    if "wf" not in S:
        return {"ran": False}
    res, k0, p = S["wf"], S["cfg"].backtest.initial_capital, need_data()
    cols = [("strategy", (res.equity / k0 - 1) * 100)]
    bh = buy_and_hold(p, BENCHMARK, res.equity.index[0], res.equity.index[-1], k0)
    if bh is not None:
        cols.append(("benchmark", (bh / k0 - 1) * 100))
    w = res.windows
    traded = w[w["n_trades"] > 0]
    return J({"ran": True, "windows": records(w.astype({k: str for k in ("train_start", "train_end", "test_start", "test_end")})),
              "equity": series(*cols, step=2), "test_start": splits()["test"][0],
              "summary": {"windows": len(w), "with_pairs": int((w["pairs"] != "—").sum()), "trades": int(w["n_trades"].sum()),
                          "return": float(res.equity.iloc[-1] / k0 - 1), "sharpe": sharpe_ratio(res.returns),
                          "profitable": int((traded["return"] > 0).sum()), "traded": len(traded)}})


@app.post("/api/robustness")
def robustness(body: dict):
    p, c = need_data(), apply_cfg(body)
    sp = splits()
    grid = parameter_grid(c.strategy, body.get("entries", [1.5, 2.0, 2.5]), body.get("exits", [0.0, 0.5]),
                          body.get("lookbacks", [40, 60]))
    if not grid:
        raise HTTPException(422, "No valid parameter combinations.")
    disc = discovery_for(sp["train"])
    pairs = select_pairs(disc.table, c.walkforward.top_k, body.get("selection", "fdr"))
    if pairs.empty:
        return {"pairs": [], "rows": [], "note": "No pairs pass the selection rule on the training split."}
    out = run_grid(p, pairs, sp["train"], sp["validation"], grid, c.backtest, tuple(body.get("costs", [1.0, 2.0])))
    S["grid"] = out
    return J({"pairs": list(pairs["pair"]), "rows": records(out)})


@app.post("/api/ml")
def ml(body: dict):
    p, c = need_data(), apply_cfg(body)
    sp = splits()
    disc = discovery_for(sp["train"])
    t = disc.table[disc.table["status"] == "tested"]
    if body.get("source", "eligible") == "eligible":
        t = t[t["eligible"]]
    pairs = t.sort_values("score", ascending=False).head(int(body.get("n_pairs", 5)))
    if pairs.empty:
        raise HTTPException(422, "No pairs available for this source.")
    try:
        mr = run_ml_study(p, pairs, c.strategy, c.backtest, sp["train"], sp["validation"],
                          p[BENCHMARK] if BENCHMARK in p else None,
                          MLConfig(int(body.get("horizon", 10)), float(body.get("min_abs_z", 1.0)),
                                   float(body.get("threshold", 0.5))))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return J({"pairs": list(pairs["pair"]), "summary": mr.summary, "importance": records(mr.importance),
              "comparison": records(mr.comparison)})


# ---------- reports
def _report() -> str:
    c, meta, rep = S["cfg"], S["meta"], S["report"]
    data_info = {"source": meta.source, "retrieved_at": meta.retrieved_at, "range": f"{rep.start} → {rep.end}",
                 "sessions": rep.n_dates, "tickers": ", ".join(S["prices"].columns)}
    d, bt = S.get("discovery"), S.get("bt")
    metrics = {"segment": bt["segment"], **bt["pipe"].backtest.metrics} if bt else None
    return build_report(c.to_dict(), data_info, d.table if d else None, bt["pipe"].selected if bt else None, metrics,
                        historical_var_es(bt["pipe"].backtest.returns) if bt else None, S.get("split"),
                        S["wf"].windows if "wf" in S else None,
                        research_warnings(bt["pipe"].backtest) if bt else [], "See findings above.")


@app.get("/api/report.md", response_class=PlainTextResponse)
def report():
    need_data()
    return _report()


@app.get("/api/export/{name}.csv")
def export(name: str):
    src = {"discovery": lambda: S["discovery"].table, "trades": lambda: S["bt"]["pipe"].backtest.trades,
           "equity": lambda: S["bt"]["pipe"].backtest.exposure.assign(equity=S["bt"]["pipe"].backtest.equity),
           "walkforward": lambda: S["wf"].windows, "robustness": lambda: S["grid"]}
    try:
        df = src[name]()
    except KeyError as exc:
        raise HTTPException(404, f"{name} not available - run it first.") from exc
    return Response(csv_bytes(df), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


@app.get("/api/export/summary.json")
def export_json():
    return status()


@app.get("/api/experiments")
def experiments():
    return J(load_experiments()[::-1])


@app.post("/api/experiments")
def save_exp():
    need_data()
    bt = S.get("bt")
    rec = make_experiment(S["cfg"].to_dict(), {"range": f"{S['report'].start} → {S['report'].end}"},
                          {"segment": bt["segment"] if bt else None,
                           "metrics": bt["pipe"].backtest.metrics if bt else None,
                           "selected_pairs": list(bt["pipe"].selected["pair"]) if bt else []})
    save_experiment(rec)
    return J(rec)


@app.post("/api/experiments/{exp_id}/load")
def load_exp(exp_id: str):
    rec = next((h for h in load_experiments() if h["id"] == exp_id), None)
    if rec is None:
        raise HTTPException(404, "Experiment not found.")
    S["cfg"] = _from_dict(ExperimentConfig, rec["config"])
    return status()
