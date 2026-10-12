"""Module F - chronological splits, research pipeline and walk-forward testing.

Information discipline: pair discovery and hedge fitting use only the fit
window; signals in the evaluation window use rolling statistics of past data
only; execution lags signals by >= 1 session. Splits are never shuffled.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, replace

import pandas as pd

from quantpair.backtesting.engine import BacktestResult, run_backtest
from quantpair.config import BacktestConfig, DiscoveryConfig, StrategyConfig, WalkForwardConfig
from quantpair.research.pair_selection import DiscoveryResult, discover_pairs, select_pairs
from quantpair.strategy.pairs_strategy import PairSignals, build_pair_signals


def chronological_split(index: pd.DatetimeIndex, train_frac: float = 0.6,
                        val_frac: float = 0.2) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    n = len(index)
    i1, i2 = int(n * train_frac), int(n * (train_frac + val_frac))
    if not (2 <= i1 < i2 < n - 1):
        raise ValueError("Split fractions leave an empty or tiny segment.")
    return {"train": (index[0], index[i1 - 1]), "validation": (index[i1], index[i2 - 1]),
            "test": (index[i2], index[-1])}


@dataclass
class PipelineResult:
    discovery: DiscoveryResult
    selected: pd.DataFrame
    signals: list[PairSignals]
    backtest: BacktestResult
    fit_window: tuple
    eval_window: tuple

    @property
    def in_sample(self) -> bool:
        return pd.Timestamp(self.eval_window[0]) <= pd.Timestamp(self.fit_window[1])


def build_signals(prices: pd.DataFrame, pairs: pd.DataFrame, strat: StrategyConfig,
                  fit_window: tuple, eval_window: tuple) -> list[PairSignals]:
    return [build_pair_signals(prices, r.y, r.x, strat, fit_window, eval_window)
            for r in pairs.itertuples()]


def run_pipeline(prices: pd.DataFrame, universe: list[str], fit_window: tuple, eval_window: tuple,
                 disc: DiscoveryConfig, strat: StrategyConfig, bt: BacktestConfig,
                 top_k: int = 5, selection: str = "fdr", discovery: DiscoveryResult | None = None,
                 pairs: pd.DataFrame | None = None) -> PipelineResult:
    """Discover on fit window -> select -> signals -> backtest on eval window.

    The traded spread uses the same deterministic terms the pairs were selected
    with: a trend-cointegration discovery trades a detrended static spread.
    """
    strat = replace(strat, use_trend=disc.coint_trend == "ct" and strat.hedge_method == "static_ols")
    cols = [t for t in universe if t in prices.columns]
    if discovery is None:
        discovery = discover_pairs(prices[cols], disc, *fit_window)
    selected = pairs if pairs is not None else select_pairs(discovery.table, top_k, selection)
    signals = build_signals(prices, selected, strat, fit_window, eval_window)
    res = run_backtest(prices, signals, bt, *eval_window)
    return PipelineResult(discovery, selected, signals, res, fit_window, eval_window)


def split_evaluation(prices: pd.DataFrame, universe: list[str], splits: dict, disc, strat, bt,
                     top_k: int, selection: str, include_test: bool = False) -> pd.DataFrame:
    """In-sample / validation / (optional) final-test table for one configuration.

    The final test refits discovery on train+validation. Look at it once,
    after choosing parameters on validation - repeated peeking turns it into
    another validation set.
    """
    tr, va, te = splits["train"], splits["validation"], splits["test"]
    base = run_pipeline(prices, universe, tr, tr, disc, strat, bt, top_k, selection)
    runs = [("In-sample (train)", base),
            ("Validation", run_pipeline(prices, universe, tr, va, disc, strat, bt, top_k, selection,
                                        discovery=base.discovery))]
    if include_test:
        runs.append(("Final test", run_pipeline(prices, universe, (tr[0], va[1]), te, disc, strat,
                                                bt, top_k, selection)))
    rows = []
    for name, r in runs:
        m = r.backtest.metrics
        rows.append({"segment": name, "fit": f"{str(r.fit_window[0])[:10]} → {str(r.fit_window[1])[:10]}",
                     "eval": f"{str(r.eval_window[0])[:10]} → {str(r.eval_window[1])[:10]}",
                     "pairs": ", ".join(r.selected["pair"]) if len(r.selected) else "—",
                     **{k: m[k] for k in ("total_return", "cagr", "sharpe", "max_drawdown",
                                          "n_trades", "total_costs")}})
    return pd.DataFrame(rows)


@dataclass
class WalkForwardResult:
    windows: pd.DataFrame
    equity: pd.Series
    returns: pd.Series
    trades: pd.DataFrame
    runs: list[PipelineResult]


_DISC_CACHE: dict = {}


def _disc_key(window: pd.DataFrame, disc: DiscoveryConfig) -> tuple:
    return (int(pd.util.hash_pandas_object(window, index=True).sum()), tuple(window.columns), repr(disc))


def discover_many(prices: pd.DataFrame, cols: list[str], disc: DiscoveryConfig, fits: list[tuple],
                  n_jobs: int | None = None, progress: Callable[[float, str], None] | None = None
                  ) -> list[DiscoveryResult]:
    """Discovery for many independent fit windows: cached, and run in parallel processes.

    Windows do not depend on each other, so parallelism cannot leak information
    between them; results are identical to a serial run (tested).
    """
    windows = [prices[cols].loc[f[0]:f[1]] for f in fits]
    keys = [_disc_key(w, disc) for w in windows]
    todo = list(dict.fromkeys(k for k in keys if k not in _DISC_CACHE))
    first = {k: windows[keys.index(k)] for k in todo}
    n_jobs = n_jobs or min(8, max(1, (os.cpu_count() or 2) - 1))
    if len(_DISC_CACHE) > 512:
        _DISC_CACHE.clear()
    if n_jobs > 1 and len(todo) > 1:
        try:
            with ProcessPoolExecutor(min(n_jobs, len(todo))) as ex:
                futs = {ex.submit(discover_pairs, first[k], disc): k for k in todo}
                for done, f in enumerate(as_completed(futs), 1):
                    _DISC_CACHE[futs[f]] = f.result()
                    if progress:
                        progress(done / len(todo), f"discovery {done}/{len(todo)} windows")
        except (BrokenProcessPool, OSError):
            pass  # environments that cannot spawn workers fall back to serial below
    remaining = [k for k in todo if k not in _DISC_CACHE]
    if remaining:
        for done, k in enumerate(remaining, 1):
            _DISC_CACHE[k] = discover_pairs(first[k], disc)
            if progress:
                progress(done / len(remaining), f"discovery {done}/{len(remaining)} windows")
    return [_DISC_CACHE[k] for k in keys]


def walk_forward(prices: pd.DataFrame, universe: list[str], disc: DiscoveryConfig,
                 strat: StrategyConfig, bt: BacktestConfig, wf: WalkForwardConfig,
                 final_test_start=None,
                 progress: Callable[[float, str], None] | None = None,
                 n_jobs: int | None = None) -> WalkForwardResult:
    """Rolling (or expanding) re-discovery and out-of-sample trading.

    Each window: discover/fit on [train], trade on the following [test]
    sessions, liquidate at window end, carry equity to the next window.
    Discovery for all windows runs first (parallel, cached); trading is then
    simulated sequentially because capital carries over.
    """
    dates = prices.index
    tr, te = wf.train_days, wf.test_days
    if tr + 2 > len(dates):
        raise ValueError(f"Need more than {tr} sessions for a {tr}-day training window.")
    bt = replace(bt, close_at_end=True)
    plan, i = [], tr
    while i < len(dates) - 1:
        j = min(i + te, len(dates))
        plan.append(((dates[0 if wf.expanding else i - tr], dates[i - 1]), (dates[i], dates[j - 1])))
        i = j
    cols = [t for t in universe if t in prices.columns]
    discs = discover_many(prices, cols, disc, [f for f, _ in plan], n_jobs,
                          (lambda f, m: progress(0.9 * f, m)) if progress else None)
    capital, rows, runs, eqs, rets, trades = bt.initial_capital, [], [], [], [], []
    for (fit, ev), dres in zip(plan, discs):
        if progress:
            progress(0.9 + 0.1 * len(rows) / len(plan), f"trading window {len(rows) + 1}/{len(plan)}")
        r = run_pipeline(prices, universe, fit, ev, disc, strat, replace(bt, initial_capital=capital),
                         wf.top_k, wf.selection, discovery=dres)
        m = r.backtest.metrics
        rows.append({"window": len(rows) + 1, "train_start": fit[0].date(), "train_end": fit[1].date(),
                     "test_start": ev[0].date(), "test_end": ev[1].date(),
                     "n_tested": r.discovery.n_tested, "n_significant": r.discovery.n_significant,
                     "pairs": ", ".join(r.selected["pair"]) if len(r.selected) else "—",
                     "start_equity": capital, "return": m["total_return"], "sharpe": m["sharpe"],
                     "max_drawdown": m["max_drawdown"], "n_trades": m["n_trades"],
                     "costs": m["total_costs"],
                     "final_test": final_test_start is not None and ev[1] >= pd.Timestamp(final_test_start)})
        capital = float(r.backtest.equity.iloc[-1])
        eqs.append(r.backtest.equity)
        rets.append(r.backtest.returns)
        if len(r.backtest.trades):
            trades.append(r.backtest.trades.assign(window=len(rows)))
        runs.append(r)
    return WalkForwardResult(pd.DataFrame(rows), pd.concat(eqs), pd.concat(rets),
                             pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(), runs)
