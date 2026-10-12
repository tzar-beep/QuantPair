import numpy as np
import pandas as pd

from quantpair.config import BacktestConfig, DiscoveryConfig, StrategyConfig
from quantpair.research.ml_reversion import MLConfig, pair_features, reversion_label, run_ml_study
from quantpair.research.pair_selection import select_pairs
from quantpair.research.spread_model import fit_hedge_ratio, kalman_hedge_ratio
from quantpair.risk.regimes import regime_performance, volatility_regime
from quantpair.strategy.pairs_strategy import build_pair_signals
from quantpair.strategy.signals import generate_positions
from quantpair.validation.walk_forward import _DISC_CACHE, chronological_split, discover_many


def test_kalman_converges_and_is_causal(prices):
    rng = np.random.default_rng(3)
    y_iid = 2 + 1.5 * prices["X"] + rng.normal(0, 1, len(prices))
    kc = kalman_hedge_ratio(y_iid, prices["X"], delta=1e-4)
    assert kc["beta"].iloc[:30].isna().all() and abs(kc["beta"].iloc[-100:].mean() - 1.5) < 0.1
    k = kalman_hedge_ratio(prices["Y"], prices["X"], delta=1e-4)
    alt = prices.copy()
    alt.iloc[400:] *= 2
    k2 = kalman_hedge_ratio(alt["Y"], alt["X"], delta=1e-4)
    pd.testing.assert_frame_equal(k.iloc[:401], k2.iloc[:401])   # prior at t=400 uses data < 400 only


def test_kalman_strategy_runs(prices):
    sp = chronological_split(prices.index)
    sig = build_pair_signals(prices, "Y", "X", StrategyConfig(lookback=20, hedge_method="kalman"),
                             sp["train"], sp["validation"])
    assert sig.frame["beta"].notna().all()


def test_entry_filter_blocks_entries():
    z = pd.Series([-2.5, -1.0, -2.5, 0.0])
    out = generate_positions(z, 2.0, 0.5, allow_entry=pd.Series([False, True, True, True]))
    assert out["position"].tolist() == [0, 0, 1, 0]


def test_regime_causal_and_complete(prices):
    reg = volatility_regime(prices["X"], 21, 100)
    alt = prices["X"].copy()
    alt.iloc[300:] *= np.linspace(1, 3, len(alt) - 300)
    pd.testing.assert_series_equal(reg.iloc[:300], volatility_regime(alt, 21, 100).iloc[:300])
    rets = prices["Y"].pct_change().fillna(0)
    perf = regime_performance(rets, reg)
    assert perf["days"].sum() + perf.attrs["unclassified_days"] == len(rets)


def test_reversion_label():
    lab = reversion_label(pd.Series([2.0, 1.5, 1.2, 0.3, -2.0, -1.0]), horizon=2, exit_z=0.5)
    assert lab.iloc[0] == 0 and lab.iloc[1] == lab.iloc[2] == lab.iloc[3] == 1
    assert lab.iloc[:4].notna().all() and lab.iloc[4:].isna().all()


def test_ml_features_causal_and_study_runs(prices):
    sp = chronological_split(prices.index)
    s = StrategyConfig(lookback=20)
    sig = build_pair_signals(prices, "Y", "X", s, sp["train"], sp["train"])
    f1 = pair_features(sig, prices["W"])
    alt = prices.copy()
    alt.iloc[200:] *= 1.5
    f2 = pair_features(build_pair_signals(alt, "Y", "X", s, sp["train"], sp["train"]), alt["W"])
    # static beta is refit on the (altered) train window, so compare features that do not depend on it
    cols = ["ret_corr60", "mkt_vol21"]
    pd.testing.assert_frame_equal(f1[cols].iloc[:200], f2[cols].iloc[:200])
    pairs = pd.DataFrame({"pair": ["Y/X"], "y": ["Y"], "x": ["X"]})
    res = run_ml_study(prices, pairs, s, BacktestConfig(), sp["train"], sp["validation"], prices["W"],
                       MLConfig(horizon=5))
    assert len(res.comparison) == 2 and res.summary["n_train"] > 50


def test_parallel_discovery_matches_serial(prices):
    d = DiscoveryConfig(min_obs=150)
    fits = [(prices.index[0], prices.index[299]), (prices.index[100], prices.index[399])]
    _DISC_CACHE.clear()
    par = discover_many(prices, ["Y", "X", "W"], d, fits, n_jobs=2)
    _DISC_CACHE.clear()
    ser = discover_many(prices, ["Y", "X", "W"], d, fits, n_jobs=1)
    for a, b in zip(par, ser):
        pd.testing.assert_frame_equal(a.table, b.table)
    assert select_pairs(par[0].table, 3)["pair"].tolist()[0] == "Y/X"


def _drifting_pair(n=800, seed=5):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    x = 100 + np.cumsum(rng.normal(0, 1, n))
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.8 * e[t - 1] + rng.normal(0, 0.3)
    y = 5 + 0.02 * np.arange(n) + 1.0 * x + e        # cointegrated only around a linear trend
    return pd.DataFrame({"Y": y, "X": x}, index=idx)


def test_hedge_fit_recovers_trend():
    p = _drifting_pair()
    fit = fit_hedge_ratio(p["Y"], p["X"], use_trend=True)
    assert abs(fit.trend - 0.02) < 0.002 and abs(fit.beta - 1.0) < 0.05


def test_trend_cointegration_detects_drifting_pair():
    from quantpair.research.pair_selection import discover_pairs
    p = _drifting_pair()
    c = discover_pairs(p, DiscoveryConfig(min_obs=200, coint_trend="c")).table.iloc[0]
    ct = discover_pairs(p, DiscoveryConfig(min_obs=200, coint_trend="ct")).table.iloc[0]
    assert ct.eg_pvalue < 0.01 and ct.eg_pvalue < c.eg_pvalue and abs(ct.trend - 0.02) < 0.002


def test_trend_spread_extrapolates_from_fit_window_only():
    p = _drifting_pair()
    fit_w, ev_w = (p.index[0], p.index[499]), (p.index[500], p.index[-1])
    s = StrategyConfig(lookback=20, use_trend=True)
    a = build_pair_signals(p, "Y", "X", s, fit_w, ev_w)
    alt = p.copy()
    alt.iloc[600:] += 50
    b = build_pair_signals(alt, "Y", "X", s, fit_w, ev_w)
    pd.testing.assert_series_equal(a.frame["intercept"], b.frame["intercept"])   # params fixed on fit window
    assert abs(a.frame["spread"].mean()) < 2      # detrended spread stays centred out of sample
