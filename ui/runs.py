"""Engine jobs triggered from the UI (shared by several pages)."""
from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from quantpair.config import BENCHMARK
from quantpair.research.pair_selection import DiscoveryResult
from quantpair.validation.robustness import buy_and_hold
from quantpair.validation.walk_forward import run_pipeline
from ui import state

SEGMENTS = ["Validation", "In-sample (train)", "Final test", "Custom"]
SELECTIONS = {"Top-k FDR-significant": "fdr", "Top-k raw p-value (exploratory)": "raw", "Manual pairs": "manual"}


def windows_for(segment: str, custom: tuple | None = None) -> tuple[tuple, tuple]:
    sp = state.splits()
    if segment == "In-sample (train)":
        return sp["train"], sp["train"]
    if segment == "Validation":
        return sp["train"], sp["validation"]
    if segment == "Final test":
        return (sp["train"][0], sp["validation"][1]), sp["test"]
    if custom is None:
        raise ValueError("Custom segment needs explicit windows.")
    return custom


def ensure_discovery(fit: tuple, store: bool = True) -> DiscoveryResult:
    """Reuse the session discovery if it matches window, universe and settings."""
    c, d = state.cfg(), state.get("discovery")
    tickers = state.universe_cols()
    win = (str(pd.Timestamp(fit[0]).date()), str(pd.Timestamp(fit[1]).date()))
    if d and d["result"].window == win and d["tickers"] == tickers and d["config"] == asdict(c.discovery):
        return d["result"]
    if store:
        return state.run_discovery(tickers, c.discovery, fit)
    return state._discover(state.prices()[tickers], asdict(c.discovery), pd.Timestamp(fit[0]), pd.Timestamp(fit[1]))


def run_backtest_job(segment: str, selection: str, top_k: int, manual: list[str] | None = None,
                     custom: tuple | None = None):
    c, p = state.cfg(), state.prices()
    fit, ev = windows_for(segment, custom)
    disc = ensure_discovery(fit, store=segment != "Final test")
    pairs = disc.table[disc.table["pair"].isin(manual or [])] if selection == "manual" else None
    res = run_pipeline(p, state.universe_cols(), fit, ev, c.discovery, c.strategy, c.backtest, top_k,
                       "fdr" if selection == "manual" else selection, discovery=disc, pairs=pairs)
    bench = buy_and_hold(p, BENCHMARK, ev[0], ev[1], c.backtest.initial_capital)
    state.put("backtest", {"pipe": res, "segment": segment, "bench": bench, "selection": selection})
    return res


def conclusion_text() -> str:
    bt, wf = state.get("backtest"), state.get("wf")
    parts = []
    if bt is None:
        parts.append("No backtest has been run, so no conclusion about profitability can be drawn.")
    else:
        m, seg = bt["pipe"].backtest.metrics, bt["segment"]
        sh = m["sharpe"]
        if bt["pipe"].selected.empty:
            parts.append(f"No pairs passed the selection rule on the fit window ({seg}); the strategy held cash. "
                         "Under the configured statistical standard the universe shows no tradeable cointegration.")
        elif m["n_trades"] < 10:
            parts.append(f"The {seg} backtest produced only {m['n_trades']} closed trades: results are inconclusive.")
        elif sh is None or sh <= 0:
            parts.append(f"The {seg} backtest shows no positive risk-adjusted return after costs (Sharpe {sh}).")
        elif bt["pipe"].in_sample:
            parts.append(f"The positive result (Sharpe {sh:.2f}) is in-sample and is not evidence of an edge.")
        else:
            parts.append(f"The {seg} period shows Sharpe {sh:.2f} after modelled costs over {m['n_trades']} trades.")
    if wf is not None:
        w = wf["result"].windows
        traded = w[w["n_trades"] > 0]
        pos = (traded["return"] > 0).mean() if len(traded) else float("nan")
        tot = wf["result"].equity.iloc[-1] / wf["capital"] - 1
        parts.append(f"Walk-forward: {len(w)} windows, {len(traded)} with trades, "
                     f"{'n/a' if pos != pos else f'{pos:.0%}'} of traded windows profitable, "
                     f"cumulative out-of-sample return {tot:.2%}.")
    else:
        parts.append("Walk-forward validation has not been run; robustness is unassessed.")
    parts.append("Historical cointegration does not guarantee future mean reversion; see limitations.")
    return " ".join(parts)
