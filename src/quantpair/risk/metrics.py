"""Module G - portfolio risk analytics on backtest outputs.

VaR/ES convention: historical simulation on daily simple portfolio returns,
reported as positive loss fractions of equity. VaR_a = -quantile(r, 1-a);
ES_a = -mean(r | r <= -VaR_a). Estimated from the chosen window only; with
few observations the tail estimate is noisy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantpair.config import TRADING_DAYS


def historical_var_es(returns: pd.Series, level: float = 0.95, window: int | None = None) -> dict:
    r = returns.dropna()
    if window:
        r = r.iloc[-window:]
    if len(r) < 20:
        return {"var": None, "es": None, "n": len(r), "level": level}
    var = -float(np.quantile(r, 1 - level))
    tail = r[r <= -var]
    return {"var": var, "es": -float(tail.mean()) if len(tail) else var, "n": len(r), "level": level}


def rolling_var(returns: pd.Series, level: float = 0.95, window: int = 250) -> pd.Series:
    return -returns.rolling(window, min_periods=window).quantile(1 - level)


def rolling_sharpe(returns: pd.Series, window: int = 126, rf: float = 0.0) -> pd.Series:
    ex = returns - rf / TRADING_DAYS
    roll = returns.rolling(window, min_periods=window)
    sd = roll.std()
    return ex.rolling(window, min_periods=window).mean() / sd.where(sd > 1e-12) * np.sqrt(TRADING_DAYS)


def exposure_concentration(pair_gross: pd.DataFrame) -> pd.DataFrame:
    """Largest pair share of gross exposure and Herfindahl index (1 = one pair)."""
    tot = pair_gross.sum(axis=1)
    w = pair_gross.div(tot.where(tot > 0), axis=0)
    return pd.DataFrame({"max_share": w.max(axis=1), "herfindahl": (w ** 2).sum(axis=1)})


def pair_attribution(pair_net: pd.DataFrame, pair_gross: pd.DataFrame,
                     pair_costs: pd.DataFrame) -> pd.DataFrame:
    """Per-pair gross P&L, costs, net P&L and share of total portfolio losses."""
    losses = pair_net.clip(upper=0).sum()
    total_loss = losses.sum()
    out = pd.DataFrame({"gross_pnl": pair_gross.sum(), "costs": pair_costs.sum(),
                        "net_pnl": pair_net.sum(), "loss_days_pnl": losses,
                        "share_of_losses": losses / total_loss if total_loss < 0 else np.nan})
    return out.sort_values("net_pnl")


def tail_summary(returns: pd.Series) -> dict:
    r = returns.dropna()
    if len(r) < 20:
        return {}
    sd = r.std()
    return {"worst_day": float(r.min()), "best_day": float(r.max()), "skew": float(r.skew()),
            "excess_kurtosis": float(r.kurt()),
            "days_below_2sd": int((r < r.mean() - 2 * sd).sum()),
            "expected_under_normal": float(len(r) * 0.02275)}
