"""Deterministic synthetic data for unit tests only (never used by the app)."""
import numpy as np
import pandas as pd
import pytest

from quantpair.strategy.pairs_strategy import PairSignals


def make_prices(n=600, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    x = 50 + np.cumsum(rng.normal(0, 1, n))
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.9 * e[t - 1] + rng.normal(0, 1)
    y = 10 + 1.5 * x + e                       # cointegrated with x, half-life ~6.6
    w = 80 + np.cumsum(rng.normal(0, 1, n))    # independent random walk
    return pd.DataFrame({"Y": y, "X": x, "W": w}, index=idx).clip(lower=1)


@pytest.fixture
def prices():
    return make_prices()


def manual_signals(dates, y, x, positions, beta=1.0, name=None):
    f = pd.DataFrame({"position": positions, "event": "", "beta": beta, "intercept": 0.0,
                      "spread": np.nan, "z": np.nan}, index=dates)
    return PairSignals(name or f"{y}/{x}", y, x, f)
