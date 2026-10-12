"""Module A - return and risk primitives for price series.

Prices and returns are kept distinct: every statistic here takes *returns*
except ``simple_returns``/``log_returns`` (which take prices) and
``drawdown`` (which takes an equity/wealth curve). Annualisation assumes
252 sessions/year and i.i.d. daily returns (vol scales with sqrt(time)).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantpair.config import TRADING_DAYS


def simple_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """r_t = P_t / P_{t-1} - 1. Missing prices give missing returns (no fill)."""
    return prices.pct_change(fill_method=None).iloc[1:]


def log_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """l_t = ln(P_t / P_{t-1}); additive over time."""
    return np.log(prices).diff().iloc[1:]


def cumulative_returns(returns: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Compounded growth of simple returns; missing days count as 0%."""
    return (1 + returns.fillna(0)).cumprod() - 1


def annualized_volatility(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * np.sqrt(periods))


def rolling_volatility(returns: pd.Series | pd.DataFrame, window: int = 63,
                       periods: int = TRADING_DAYS) -> pd.Series | pd.DataFrame:
    return returns.rolling(window, min_periods=window).std() * np.sqrt(periods)


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pairwise Pearson correlation of returns (pairwise-complete observations)."""
    return returns.corr()


def rolling_correlation(a: pd.Series, b: pd.Series, window: int = 63) -> pd.Series:
    return a.rolling(window, min_periods=window).corr(b)


def drawdown(equity: pd.Series) -> pd.Series:
    """Fractional decline from the running peak: E_t / max_{s<=t} E_s - 1 (<= 0)."""
    return equity / equity.cummax() - 1


def max_drawdown(equity: pd.Series) -> float:
    return float(drawdown(equity).min()) if len(equity) else float("nan")


def distribution_stats(returns: pd.Series) -> dict[str, float]:
    r = returns.dropna()
    if r.empty:
        return {"n": 0}
    return {"n": int(len(r)), "mean": float(r.mean()), "std": float(r.std(ddof=1)) if len(r) > 1 else float("nan"),
            "skew": float(r.skew()), "excess_kurtosis": float(r.kurt()),
            "min": float(r.min()), "max": float(r.max())}
