import numpy as np
import pandas as pd

from quantpair.research.spread_model import (
    estimate_half_life,
    fit_hedge_ratio,
    fit_ou,
    rolling_hedge_ratio,
    rolling_zscore,
)


def test_hedge_ratio_exact():
    x = pd.Series(np.arange(1, 51.0))
    fit = fit_hedge_ratio(2 + 3 * x, x)
    assert np.isclose(fit.beta, 3) and np.isclose(fit.intercept, 2) and np.isclose(fit.r2, 1)
    fit0 = fit_hedge_ratio(3 * x, x, use_intercept=False)
    assert np.isclose(fit0.beta, 3) and fit0.intercept == 0


def test_rolling_hedge_ratio_matches_window_ols(prices):
    rh = rolling_hedge_ratio(prices["Y"], prices["X"], 100)
    w = prices.iloc[100:200]
    assert np.isclose(rh["beta"].iloc[199], fit_hedge_ratio(w["Y"], w["X"]).beta)


def test_zscore_uses_no_future_data(prices):
    s = prices["Y"] - 1.5 * prices["X"]
    z1 = rolling_zscore(s, 30)
    s2 = s.copy()
    s2.iloc[300:] += 1000
    pd.testing.assert_series_equal(z1.iloc[:300], rolling_zscore(s2, 30).iloc[:300])
    assert z1.iloc[:29].isna().all()


def test_zscore_zero_variance_is_nan():
    assert rolling_zscore(pd.Series([5.0] * 50), 10).isna().all()


def test_half_life_ar1_and_invalid_cases():
    rng = np.random.default_rng(1)
    e = np.zeros(5000)
    for t in range(1, 5000):
        e[t] = 0.9 * e[t - 1] + rng.normal()
    hl = estimate_half_life(pd.Series(e))
    assert hl.valid and abs(hl.value - np.log(2) / -np.log(0.9)) < 1.0
    rw = estimate_half_life(pd.Series(np.cumsum(rng.normal(0, 1, 500))))
    assert rw.value is None or not rw.valid
    assert not estimate_half_life(pd.Series(1.01 ** np.arange(300))).valid
    ou = fit_ou(pd.Series(e))
    assert ou.valid and abs(ou.half_life - hl.value) < 1.0 and abs(ou.sigma_eq - 1 / np.sqrt(1 - .81)) < 0.2
