import numpy as np
import pandas as pd

from quantpair.strategy.position_sizing import hedge_shares
from quantpair.strategy.signals import generate_positions


def run(z, **kw):
    args = {"entry": 2.0, "exit": 0.5, "stop": None, "max_hold": None} | kw
    return generate_positions(pd.Series(z, dtype=float), **args)


def test_orientation_entry_exit_and_no_duplicates():
    out = run([0, -2.1, -2.5, -1.0, -0.4, 0, 2.2, 2.6, 0.4, 0])
    assert out["position"].tolist() == [0, 1, 1, 1, 0, 0, -1, -1, 0, 0]
    assert (out["event"] == "enter_long").sum() == 1 and (out["event"] == "enter_short").sum() == 1


def test_stop_blocks_reentry_until_reset():
    out = run([-2.2, -4.5, -3.0, -2.5, -1.0, -2.3], stop=4.0)
    assert out["position"].tolist() == [1, 0, 0, 0, 0, 1]
    assert out["event"].iloc[1] == "stop"


def test_max_hold_and_nan_keeps_state():
    out = run([-2.2, np.nan, -1.5, -1.5, -1.5], max_hold=3)
    assert out["position"].tolist() == [1, 1, 1, 0, 0] and out["event"].iloc[3] == "max_hold"


def test_no_flip_in_one_bar():
    assert run([-2.2, 2.5, 2.5])["position"].tolist() == [1, 0, -1]


def test_hedge_shares_orientation():
    ny, nx = hedge_shares(1, 1000, 10, 20, 0.5)
    assert ny > 0 and nx < 0 and np.isclose(abs(ny) * 10 + abs(nx) * 20, 1000)
    ny, nx = hedge_shares(-1, 1000, 10, 20, 0.5)
    assert ny < 0 and nx > 0
    ny, nx = hedge_shares(1, 1000, 10, 20, -0.5)       # negative beta: both legs long
    assert ny > 0 and nx > 0 and np.isclose(nx, 0.5 * ny)
