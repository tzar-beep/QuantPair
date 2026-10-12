"""Hypothetical stress scenarios. These are what-if calculations, not forecasts.

They show how a historically cointegrated pair still loses money: spreads can
widen far beyond past ranges, the hedge ratio can drift (relationship break),
reversion can stall while borrow fees accrue, and costs can rise.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from quantpair.backtesting.engine import run_backtest
from quantpair.config import TRADING_DAYS, BacktestConfig
from quantpair.strategy.pairs_strategy import PairSignals
from quantpair.strategy.position_sizing import hedge_shares


def _position(sig: PairSignals, budget: float) -> tuple[float, float, float, float, float]:
    f = sig.frame.dropna(subset=["price_y", "price_x", "beta"])
    if f.empty:
        raise ValueError(f"No priced observations for {sig.name}.")
    last = f.iloc[-1]
    ny, nx = hedge_shares(1, budget, last.price_y, last.price_x, last.beta)
    return ny, nx, last.price_x, last.beta, float(f["spread"].std())


def pair_scenarios(sig: PairSignals, budget: float, spread_shock_sigma: float = 3.0,
                   stall_days: int = 60, beta_error: float = 0.2, x_move: float = 0.10,
                   borrow_bps: float = 25.0) -> pd.DataFrame:
    """Losses (positive = loss, in currency) on one long-spread position of size `budget`."""
    ny, nx, px, beta, s_sd = _position(sig, budget)
    ds_sd = float(sig.frame["spread"].diff().std())
    short_notional = abs(nx) * px if nx < 0 else 0.0
    rows = [
        ("Spread widening", f"Spread moves {spread_shock_sigma:.1f} historical std against the position",
         spread_shock_sigma * s_sd * abs(ny)),
        ("No mean reversion", f"Spread random-walks for {stall_days} sessions (2-sigma adverse) + borrow fees",
         2 * ds_sd * np.sqrt(stall_days) * abs(ny) + short_notional * borrow_bps / 1e4 * stall_days / TRADING_DAYS),
        ("Relationship breakdown", f"True hedge ratio is {beta_error:+.0%} off and x moves {x_move:.0%}",
         abs(beta_error * beta * ny * px * x_move)),
    ]
    out = pd.DataFrame(rows, columns=["scenario", "assumption", "loss"])
    out["loss_pct_of_budget"] = out["loss"] / budget
    return out


def cost_stress(prices: pd.DataFrame, signals: list[PairSignals], cfg: BacktestConfig,
                start, end, multipliers=(1.0, 2.0, 3.0)) -> pd.DataFrame:
    """Re-run the same backtest with fees and slippage scaled up."""
    rows = []
    for m in multipliers:
        c = replace(cfg.costs, fee_bps=cfg.costs.fee_bps * m, slippage_bps=cfg.costs.slippage_bps * m)
        res = run_backtest(prices, signals, replace(cfg, costs=c), start, end)
        rows.append({"cost_multiplier": m, **{k: res.metrics[k] for k in
                     ("total_return", "sharpe", "max_drawdown", "total_costs", "net_pnl")}})
    return pd.DataFrame(rows)


def volatility_stress(returns: pd.Series, factors=(1.0, 1.5, 2.0), level: float = 0.95) -> pd.DataFrame:
    """Scale return deviations around the mean and recompute historical VaR/ES."""
    from quantpair.risk.metrics import historical_var_es
    r = returns.dropna()
    rows = []
    for f in factors:
        scaled = r.mean() + f * (r - r.mean())
        rows.append({"vol_factor": f, **historical_var_es(scaled, level)})
    return pd.DataFrame(rows)
