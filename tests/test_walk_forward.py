import pandas as pd

from quantpair.config import BacktestConfig, DiscoveryConfig, StrategyConfig, WalkForwardConfig
from quantpair.validation.robustness import parameter_grid, run_grid
from quantpair.validation.walk_forward import chronological_split, run_pipeline, walk_forward

D, S, B = DiscoveryConfig(min_obs=150), StrategyConfig(lookback=20), BacktestConfig()
WF = WalkForwardConfig(train_days=250, test_days=100, top_k=2)
U = ["Y", "X", "W"]


def test_split_chronological_no_overlap(prices):
    sp = chronological_split(prices.index, 0.6, 0.2)
    assert sp["train"][1] < sp["validation"][0] <= sp["validation"][1] < sp["test"][0]


def test_pipeline_selects_on_training_only(prices):
    sp = chronological_split(prices.index)
    r = run_pipeline(prices, U, sp["train"], sp["validation"], D, S, B)
    assert r.discovery.window[1] == str(sp["train"][1].date()) and not r.in_sample
    assert r.backtest.equity.index[0] == sp["validation"][0]
    assert r.signals[0].frame.index[0] >= sp["validation"][0]


def test_walk_forward_chronology_and_no_future_influence(prices):
    a = walk_forward(prices, U, D, S, B, WF)
    w = a.windows
    assert (pd.to_datetime(w["train_end"]) < pd.to_datetime(w["test_start"])).all()
    assert (pd.to_datetime(w["test_start"]).iloc[1:].values > pd.to_datetime(w["test_end"]).iloc[:-1].values).all()
    assert a.equity.index.is_monotonic_increasing and not a.equity.index.duplicated().any()
    altered = prices.copy()
    altered.iloc[450:] *= 1.7
    b = walk_forward(altered, U, D, S, B, WF)
    pd.testing.assert_series_equal(a.runs[0].backtest.equity, b.runs[0].backtest.equity)  # window 1 ends row 349


def test_reproducible(prices):
    pd.testing.assert_series_equal(walk_forward(prices, U, D, S, B, WF).equity,
                                   walk_forward(prices, U, D, S, B, WF).equity)


def test_grid_counts_variants(prices):
    sp = chronological_split(prices.index)
    r = run_pipeline(prices, U, sp["train"], sp["validation"], D, S, B)
    grid = parameter_grid(S, [1.5, 2.0], [0.0, 0.5], [20])
    out = run_grid(prices, r.selected, sp["train"], sp["validation"], grid, B, (1.0, 2.0))
    assert len(out) == 8
    assert (out[out.cost_mult == 2.0]["total_costs"].values >= out[out.cost_mult == 1.0]["total_costs"].values).all()
