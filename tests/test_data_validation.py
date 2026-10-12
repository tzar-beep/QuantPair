import numpy as np
import pandas as pd

from quantpair.analytics.market import annualized_volatility, drawdown, log_returns, max_drawdown, simple_returns
from quantpair.data.validation import clean_prices


def test_duplicates_resolved_keep_last_and_reported():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-03", "2024-01-04"])
    df, rep = clean_prices(pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0]}, index=idx), min_obs=1)
    assert list(df["A"]) == [1.0, 3.0, 4.0]
    assert any(i.check == "duplicate_timestamps" for i in rep.issues)


def test_invalid_prices_become_missing_and_are_not_interpolated():
    idx = pd.bdate_range("2024-01-01", periods=5)
    raw = pd.DataFrame({"A": [10, -1, np.nan, 0, 12.0], "B": [1, 2, 3, 4, 5.0]}, index=idx)
    df, rep = clean_prices(raw, min_obs=1)
    assert df["A"].isna().sum() == 3
    assert rep.n_errors == 1
    assert any(i.check == "missing_sessions" for i in rep.issues)


def test_alignment_tz_and_sorting():
    idx = pd.DatetimeIndex(["2024-01-03 16:00", "2024-01-02 16:00"], tz="America/New_York")
    df, rep = clean_prices(pd.DataFrame({"A": [2.0, 1.0], "B": [np.nan, 5.0]}, index=idx), min_obs=1)
    assert df.index.tz is None and list(df.index.day) == [2, 3]
    assert rep.common_dates == 1


def test_insufficient_history_and_empty_ticker():
    idx = pd.bdate_range("2024-01-01", periods=10)
    df, rep = clean_prices(pd.DataFrame({"A": np.arange(1, 11.0), "Z": np.nan}, index=idx), min_obs=50)
    assert "Z" not in df
    assert any(i.check == "insufficient_history" for i in rep.issues)


def test_returns_and_edge_cases():
    r = simple_returns(pd.Series([100.0, 110.0, np.nan, 121.0]))
    assert np.isclose(r.iloc[0], 0.10) and r.isna().sum() == 2   # no forward fill across the gap
    assert np.isclose(log_returns(pd.Series([1.0, np.e])).iloc[0], 1.0)
    assert annualized_volatility(simple_returns(pd.Series([5.0] * 30))) == 0.0
    assert np.isnan(annualized_volatility(pd.Series([0.01])))


def test_drawdown():
    eq = pd.Series([100.0, 120.0, 90.0, 130.0])
    assert np.allclose(drawdown(eq), [0, 0, -0.25, 0])
    assert max_drawdown(eq) == -0.25
