"""Builds per-pair signal frames (spread, z-score, target position).

Hedge methods
* static_ols: alpha, beta fitted once on the fit (training) window and held
  fixed out of sample.
* rolling_ols: alpha_t, beta_t from a trailing window ending at t (no future data).
* kalman: one-step-ahead Kalman-filter estimates (data before t only).
The z-score at t uses spreads up to t; history before the evaluation window
is used as warm-up, which is legitimate past information.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantpair.config import StrategyConfig
from quantpair.research.spread_model import fit_hedge_ratio, kalman_hedge_ratio, rolling_hedge_ratio, rolling_zscore
from quantpair.strategy.signals import generate_positions


@dataclass
class PairSignals:
    name: str
    y: str
    x: str
    frame: pd.DataFrame          # index: signal dates; position, event, beta, intercept, spread, z
    fit_start: str | None = None
    fit_end: str | None = None


def build_pair_signals(prices: pd.DataFrame, y: str, x: str, cfg: StrategyConfig,
                       fit_window: tuple, eval_window: tuple,
                       entry_filter: pd.Series | None = None) -> PairSignals:
    """entry_filter: optional boolean series; False suppresses new entries on that date."""
    eval_end = eval_window[1]
    df = prices[[y, x]].loc[:eval_end].dropna()
    if cfg.hedge_method == "static_ols":
        fit = fit_hedge_ratio(df[y].loc[fit_window[0]:fit_window[1]],
                              df[x].loc[fit_window[0]:fit_window[1]], cfg.use_intercept, cfg.use_trend)
        beta = pd.Series(fit.beta, index=df.index)
        # Trend is folded into a time-varying intercept: alpha_t = a + g*(t - t_fit_start);
        # out of sample it is extrapolated from fit-window parameters only.
        t = np.arange(len(df), dtype=float) - int(df.index.searchsorted(pd.Timestamp(fit_window[0])))
        intercept = pd.Series(fit.intercept + fit.trend * t, index=df.index)
    elif cfg.hedge_method == "kalman":
        kh = kalman_hedge_ratio(df[y], df[x], cfg.kalman_delta, use_intercept=cfg.use_intercept)
        beta, intercept = kh["beta"], kh["intercept"]
    else:
        rh = rolling_hedge_ratio(df[y], df[x], cfg.hedge_window, cfg.use_intercept)
        beta, intercept = rh["beta"], rh["intercept"]
    spread = df[y] - intercept - beta * df[x]
    z = rolling_zscore(spread, cfg.lookback)
    frame = pd.DataFrame({"price_y": df[y], "price_x": df[x], "beta": beta,
                          "intercept": intercept, "spread": spread, "z": z})
    frame = frame.loc[eval_window[0]:eval_end]
    allow = None if entry_filter is None else entry_filter.reindex(frame.index).fillna(False).astype(bool)
    sig = generate_positions(frame["z"], cfg.entry_z, cfg.exit_z, cfg.stop_z, cfg.max_hold, allow)
    frame = frame.join(sig)
    return PairSignals(f"{y}/{x}", y, x, frame, str(fit_window[0])[:10], str(fit_window[1])[:10])
