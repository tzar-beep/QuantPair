"""Extension A - volatility regimes.

Regime definition: market (SPY) realised volatility over `window` sessions,
annualised, compared with its own *expanding* median up to the same date.
Above the median = "high-vol", otherwise "low-vol". Both quantities use only
data up to t, and strategy returns on day t are matched to the regime known at
the close of t-1, so no future information classifies a past day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quantpair.config import TRADING_DAYS


def volatility_regime(market: pd.Series, window: int = 63, min_history: int = 252) -> pd.Series:
    r = np.log(market.dropna()).diff()
    vol = r.rolling(window, min_periods=window).std() * np.sqrt(TRADING_DAYS)
    thr = vol.expanding(min_periods=min_history).median()
    reg = pd.Series(np.where(vol > thr, "high-vol", "low-vol"), index=vol.index, dtype=object)
    return reg.where(vol.notna() & thr.notna()).rename("regime")


def regime_performance(returns: pd.Series, regime: pd.Series) -> pd.DataFrame:
    """Per-regime statistics of daily strategy returns (regime lagged one day)."""
    reg = regime.shift(1).reindex(returns.index)
    rows = []
    for name, r in returns.groupby(reg):
        sd = r.std()
        rows.append({"regime": name, "days": len(r), "active_days": int((r != 0).sum()),
                     "ann_return": r.mean() * TRADING_DAYS, "ann_vol": sd * np.sqrt(TRADING_DAYS),
                     "sharpe": r.mean() / sd * np.sqrt(TRADING_DAYS) if len(r) >= 20 and sd > 1e-12 else np.nan,
                     "hit_rate": (r[r != 0] > 0).mean() if (r != 0).any() else np.nan,
                     "total_contribution": (1 + r).prod() - 1})
    unclassified = int(reg.isna().sum())
    out = pd.DataFrame(rows)
    out.attrs["unclassified_days"] = unclassified
    return out
