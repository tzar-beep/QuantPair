"""Live spread monitor: today's quotes against yesterday's model.

The hedge ratio, intercept and the z-score's mean/std come only from daily
closes already in the dataset (strictly before the live quote), exactly as a
trader would have them before the open. The live z-score is therefore
indicative: it compares an intraday spread with a daily-close distribution.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantpair.config import StrategyConfig
from quantpair.research.spread_model import fit_hedge_ratio, kalman_hedge_ratio, rolling_hedge_ratio


@dataclass
class LiveReading:
    pair: str
    price_y: float
    price_x: float
    beta: float
    intercept: float
    spread: float
    z: float | None
    mean: float
    std: float
    signal: str
    history_end: str


def live_reading(prices: pd.DataFrame, y: str, x: str, py: float, px: float, cfg: StrategyConfig,
                 fit_window: tuple) -> LiveReading:
    df = prices[[y, x]].dropna()
    if len(df) < cfg.lookback + 2:
        raise ValueError("Not enough daily history for the z-score window.")
    if cfg.hedge_method == "rolling_ols":
        hr = rolling_hedge_ratio(df[y], df[x], cfg.hedge_window, cfg.use_intercept).iloc[-1]
        beta, alpha = float(hr["beta"]), float(hr["intercept"])
        spreads = df[y] - alpha - beta * df[x]
    elif cfg.hedge_method == "kalman":
        kh = kalman_hedge_ratio(df[y], df[x], cfg.kalman_delta, use_intercept=cfg.use_intercept)
        beta, alpha = float(kh["beta"].iloc[-1]), float(kh["intercept"].iloc[-1])
        spreads = df[y] - kh["intercept"] - kh["beta"] * df[x]
    else:
        fit = fit_hedge_ratio(df[y].loc[fit_window[0]:fit_window[1]], df[x].loc[fit_window[0]:fit_window[1]],
                              cfg.use_intercept)
        beta, alpha = fit.beta, fit.intercept
        spreads = df[y] - alpha - beta * df[x]
    hist = spreads.dropna().iloc[-cfg.lookback:]
    mean, std = float(hist.mean()), float(hist.std(ddof=1))
    s = py - alpha - beta * px
    z = (s - mean) / std if std > 1e-12 and np.isfinite(std) else None
    if z is None:
        signal = "insufficient data"
    elif cfg.stop_z is not None and abs(z) >= cfg.stop_z:
        signal = "beyond stop"
    elif z <= -cfg.entry_z:
        signal = "long spread"
    elif z >= cfg.entry_z:
        signal = "short spread"
    elif abs(z) <= cfg.exit_z:
        signal = "inside exit band"
    else:
        signal = "no signal"
    return LiveReading(f"{y}/{x}", py, px, beta, alpha, s, z, mean, std, signal, str(df.index[-1].date()))
