"""Parameter-sensitivity analysis, baselines and research warnings.

Grids are evaluated on the validation segment, never the final test. Every
variant tried is counted: the best of N noisy backtests is biased upward, so
the report shows how many were run and how dispersed they were.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from quantpair.backtesting.engine import BacktestResult, run_backtest
from quantpair.config import BacktestConfig, StrategyConfig
from quantpair.validation.walk_forward import build_signals

METRIC_COLS = ("total_return", "sharpe", "max_drawdown", "n_trades", "total_costs")


def parameter_grid(base: StrategyConfig, entries, exits, lookbacks) -> list[StrategyConfig]:
    out = []
    for e, x, lb in itertools.product(entries, exits, lookbacks):
        if 0 <= x < e and (base.stop_z is None or base.stop_z > e):
            out.append(replace(base, entry_z=float(e), exit_z=float(x), lookback=int(lb)))
    return out


def run_grid(prices: pd.DataFrame, pairs: pd.DataFrame, fit_window, eval_window,
             strategies: list[StrategyConfig], bt: BacktestConfig,
             cost_multipliers=(1.0,), progress=None) -> pd.DataFrame:
    rows, total = [], len(strategies) * len(cost_multipliers)
    for k, (s, m) in enumerate(itertools.product(strategies, cost_multipliers)):
        if progress:
            progress((k + 1) / total, f"variant {k + 1}/{total}")
        c = replace(bt.costs, fee_bps=bt.costs.fee_bps * m, slippage_bps=bt.costs.slippage_bps * m)
        res = run_backtest(prices, build_signals(prices, pairs, s, fit_window, eval_window),
                           replace(bt, costs=c), *eval_window)
        rows.append({"entry_z": s.entry_z, "exit_z": s.exit_z, "lookback": s.lookback,
                     "cost_mult": m, **{c_: res.metrics[c_] for c_ in METRIC_COLS}})
    return pd.DataFrame(rows)


def buy_and_hold(prices: pd.DataFrame, ticker: str, start, end, capital: float) -> pd.Series | None:
    if ticker not in prices:
        return None
    s = prices[ticker].loc[start:end].ffill().dropna()
    return None if s.empty else (capital * s / s.iloc[0]).rename(f"{ticker} buy & hold")


def research_warnings(res: BacktestResult, grid: pd.DataFrame | None = None) -> list[str]:
    m, t, w = res.metrics, res.trades, []
    closed = t[~t["open"]] if len(t) else t
    if m["n_trades"] < 10:
        w.append(f"Only {m['n_trades']} closed trades - too few for reliable statistics.")
    if len(closed) >= 3 and m["net_pnl"] > 0:
        top2 = closed["net_pnl"].nlargest(2).sum()
        if top2 > m["net_pnl"]:
            w.append("Net profit depends on the two best trades; without them the strategy loses money.")
    if m["gross_pnl"] > 0 >= m["net_pnl"]:
        w.append("Strategy is profitable before costs but not after - costs consume the edge.")
    if m["max_drawdown"] is not None and m["max_drawdown"] < -0.20:
        w.append(f"Severe drawdown of {m['max_drawdown']:.1%}.")
    if res.skipped_entries:
        w.append(f"{res.skipped_entries} entries skipped by capital/exposure limits.")
    if grid is not None and len(grid) > 1:
        sh = grid["sharpe"].dropna()
        if len(sh) > 1 and (sh.max() > 0 > sh.min()):
            w.append(f"Sharpe changes sign across {len(grid)} tested variants - results are parameter-sensitive.")
        elif len(sh) > 1 and sh.std() > 0.5:
            w.append(f"Sharpe dispersion across variants is high (std {sh.std():.2f}).")
    if not w:
        w.append("No automatic red flags - this is not evidence of robustness on its own.")
    return w


def relationship_stability_warning(selected: pd.DataFrame, cv_limit: float = 0.25) -> list[str]:
    if selected.empty or "beta_cv" not in selected:
        return []
    bad = selected[selected["beta_cv"] > cv_limit]
    return [f"{p}: rolling hedge ratio unstable (CV {cv:.2f})." for p, cv in
            zip(bad["pair"], bad["beta_cv"]) if np.isfinite(cv)]
