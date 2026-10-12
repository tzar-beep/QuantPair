"""Performance metrics. Unreliable values are returned as None, not guessed.

Formulas (daily returns r_t, N sessions, rf = annual risk-free rate):
  total return     E_N / E_0 - 1
  CAGR             (1 + total)^(252/N) - 1
  ann. vol         std(r) * sqrt(252)
  Sharpe           mean(r - rf/252) / std(r) * sqrt(252)
  Sortino          mean(r - rf/252) / sqrt(mean(min(r - rf/252, 0)^2)) * sqrt(252)
  max drawdown     min_t (E_t / max_{s<=t} E_s - 1)
  Calmar           CAGR / |max drawdown|
  profit factor    sum(winning trade P&L) / |sum(losing trade P&L)|
  turnover         traded notional / average equity / years
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantpair.config import TRADING_DAYS

MIN_OBS_RATIO = 20  # sessions required before Sharpe/Sortino are reported


def sharpe_ratio(returns: pd.Series, rf: float = 0.0) -> float | None:
    r = returns.dropna()
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    if len(r) < MIN_OBS_RATIO or not np.isfinite(sd) or sd < 1e-12:
        return None
    return float((r - rf / TRADING_DAYS).mean() / sd * np.sqrt(TRADING_DAYS))


def sortino_ratio(returns: pd.Series, rf: float = 0.0) -> float | None:
    r = returns.dropna() - rf / TRADING_DAYS
    if len(r) < MIN_OBS_RATIO:
        return None
    dd = np.sqrt((np.minimum(r, 0) ** 2).mean())
    return None if dd < 1e-12 else float(r.mean() / dd * np.sqrt(TRADING_DAYS))


def performance_metrics(equity: pd.Series, returns: pd.Series, initial_capital: float,
                        trades: pd.DataFrame, gross_pnl: float, total_costs: float,
                        traded_notional: float, gross_exposure: pd.Series,
                        net_exposure: pd.Series, rf: float = 0.0) -> dict:
    n = len(returns)
    years = n / TRADING_DAYS
    total = float(equity.iloc[-1] / initial_capital - 1) if n else None
    cagr = (float((1 + total) ** (1 / years) - 1)
            if total is not None and years > 0 and 1 + total > 0 else None)
    vol = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS)) if n > 1 else None
    peak = np.maximum.accumulate(np.r_[initial_capital, equity.to_numpy()])
    mdd = float((np.r_[initial_capital, equity.to_numpy()] / peak - 1).min()) if n else None
    closed = trades[~trades["open"]] if len(trades) else trades
    pnl = closed["net_pnl"] if len(closed) else pd.Series(dtype=float)
    wins, losses = pnl[pnl > 0].sum(), pnl[pnl < 0].sum()
    eq_avg = float(equity.mean()) if n else initial_capital
    return {
        "total_return": total, "cagr": cagr, "ann_vol": vol,
        "sharpe": sharpe_ratio(returns, rf), "sortino": sortino_ratio(returns, rf),
        "max_drawdown": mdd,
        "calmar": cagr / abs(mdd) if cagr is not None and mdd is not None and mdd < -1e-12 else None,
        "n_trades": int(len(closed)),
        "win_rate": float((pnl > 0).mean()) if len(pnl) else None,
        "profit_factor": float(wins / -losses) if losses < 0 else None,
        "avg_trade_return": float(closed["return_on_notional"].mean()) if len(closed) else None,
        "avg_holding_days": float(closed["holding_days"].mean()) if len(closed) else None,
        "gross_pnl": float(gross_pnl), "total_costs": float(total_costs),
        "net_pnl": float(equity.iloc[-1] - initial_capital) if n else 0.0,
        "turnover": float(traded_notional / eq_avg / years) if years > 0 and eq_avg > 0 else None,
        "avg_gross_exposure": float((gross_exposure / equity).mean()) if n else None,
        "avg_net_exposure": float((net_exposure / equity).mean()) if n else None,
        "time_in_market": float((gross_exposure > 0).mean()) if n else None,
        "n_days": n,
    }
