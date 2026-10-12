import numpy as np
import pandas as pd
import pytest

from quantpair.backtesting.engine import run_backtest
from quantpair.backtesting.metrics import sharpe_ratio
from quantpair.config import BacktestConfig, CostConfig
from tests.conftest import manual_signals

DATES = pd.bdate_range("2024-01-01", periods=6)
ZERO = CostConfig(0, 0, 0)
N = 50_000 / 150   # shares per leg: budget 50k / (P_y 100 + beta 1 * P_x 50)


def px(y):
    return pd.DataFrame({"Y": y, "X": [50.0] * len(y)}, index=DATES[:len(y)])


def cfg(**kw):
    return BacktestConfig(**({"initial_capital": 100_000, "alloc_per_pair": 0.5, "costs": ZERO} | kw))


def test_zero_position_zero_pnl():
    r = run_backtest(px([100, 101, 99, 120, 80, 100.0]), [manual_signals(DATES, "Y", "X", [0] * 6)], cfg())
    assert (r.equity == 100_000).all() and r.metrics["n_trades"] == 0 and r.metrics["sharpe"] is None


def test_hand_calculated_trade_and_lag():
    r = run_backtest(px([100, 100, 100, 110, 110, 110.0]),
                     [manual_signals(DATES, "Y", "X", [0, 1, 1, 1, 0, 0])], cfg())
    t = r.trades.iloc[0]
    assert t.entry_date == DATES[2] and t.exit_date == DATES[5] and t.signal_date == DATES[1]
    assert np.isclose(t.shares_y, N) and np.isclose(t.shares_x, -N)
    assert np.isclose(r.equity.iloc[-1], 100_000 + 10 * N) and np.isclose(t.net_pnl, 10 * N)


def test_signal_day_move_not_credited():
    r = run_backtest(px([100, 110, 110, 110, 110, 110.0]),     # jump on the signal day itself
                     [manual_signals(DATES, "Y", "X", [0, 1, 1, 1, 0, 0])], cfg())
    assert np.isclose(r.equity.iloc[-1], 100_000)


def test_costs_both_legs_and_net_below_gross():
    c = CostConfig(fee_bps=10, slippage_bps=0, borrow_bps_annual=0)
    r = run_backtest(px([100, 100, 100, 110, 110, 110.0]),
                     [manual_signals(DATES, "Y", "X", [0, 1, 1, 1, 0, 0])], cfg(costs=c))
    expected = (50_000 + N * 110 + N * 50) * 10 / 1e4     # entry both legs + exit both legs
    assert np.isclose(r.metrics["total_costs"], expected)
    assert np.isclose(r.equity.iloc[-1], 100_000 + 10 * N - expected)
    assert r.metrics["net_pnl"] < r.metrics["gross_pnl"]
    assert np.isclose(r.trades.iloc[0].costs, expected)


def test_borrow_charged_on_short_leg_only():
    c = CostConfig(0, 0, borrow_bps_annual=252)            # 1 bp per session
    r = run_backtest(px([100.0] * 6), [manual_signals(DATES, "Y", "X", [1] * 6)], cfg(costs=c))
    assert r.costs["borrow"].iloc[1] == 0                   # entered at close of day 1
    assert np.isclose(r.costs["borrow"].iloc[2], N * 50 * 1e-4)


def test_capital_limit_and_equity_identity():
    p = pd.DataFrame({"Y": [100, 100, 101, 103, 102, 104.0], "X": [50.0] * 6,
                      "A": [20, 20, 21, 19, 20, 22.0]}, index=DATES)
    s = [manual_signals(DATES, "Y", "X", [1] * 6), manual_signals(DATES, "A", "X", [1] * 6)]
    r = run_backtest(p, s, cfg(alloc_per_pair=0.6, max_gross_leverage=1.0))
    assert r.skipped_entries >= 1 and (r.exposure["gross_pct"] <= 1.0 + 1e-9).all()
    assert r.trades["pair"].tolist() == ["Y/X"]
    assert np.allclose(r.equity.diff().iloc[1:], r.pair_pnl.sum(axis=1).iloc[1:])


def test_end_of_test_policy():
    p = px([100, 100, 101, 102, 103, 104.0])
    r = run_backtest(p, [manual_signals(DATES, "Y", "X", [1] * 6)], cfg())
    assert r.trades.iloc[0].exit_reason == "end_of_test" and r.exposure["gross"].iloc[-1] == 0
    r2 = run_backtest(p, [manual_signals(DATES, "Y", "X", [1] * 6)], cfg(close_at_end=False))
    assert bool(r2.trades.iloc[0].open) and r2.exposure["gross"].iloc[-1] > 0


def test_invalid_lag_rejected():
    with pytest.raises(ValueError):
        BacktestConfig(execution_lag=0)


def test_sharpe_zero_vol_and_value():
    assert sharpe_ratio(pd.Series([0.001] * 50)) is None
    r = pd.Series(np.tile([0.01, -0.005], 25))
    assert np.isclose(sharpe_ratio(r), r.mean() / r.std() * np.sqrt(252))
