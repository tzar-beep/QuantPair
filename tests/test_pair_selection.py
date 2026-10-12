import numpy as np
from statsmodels.stats.multitest import multipletests

from quantpair.config import DiscoveryConfig
from quantpair.research.pair_selection import benjamini_hochberg, candidate_pairs, discover_pairs, select_pairs


def test_bh_matches_statsmodels():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    adj, rej = benjamini_hochberg(p, 0.05)
    rej_sm, adj_sm, *_ = multipletests(p, 0.05, method="fdr_bh")
    assert np.allclose(adj, adj_sm) and (rej == rej_sm).all()
    adj2, rej2 = benjamini_hochberg([0.01, np.nan], 0.05)
    assert np.isnan(adj2[1]) and not rej2[1] and np.isclose(adj2[0], 0.01)


def test_candidate_pairs_unique():
    pairs = candidate_pairs(["A", "B", "C", "D", "A"])
    assert len(pairs) == 6 and len({frozenset(p) for p in pairs}) == 6


def test_discovery_detects_cointegrated_pair(prices):
    res = discover_pairs(prices, DiscoveryConfig(min_obs=200))
    t = res.table.set_index("pair")
    assert res.n_tested == 3
    assert t.loc["Y/X", "eg_pvalue"] < 0.01 and t.loc["Y/X", "eligible"]
    assert abs(t.loc["Y/X", "beta"] - 1.5) < 0.1
    assert select_pairs(res.table, 5)["pair"].tolist()[0] == "Y/X"


def test_discovery_uses_window_only(prices):
    cfg = DiscoveryConfig(min_obs=200)
    end = prices.index[399]
    a = discover_pairs(prices, cfg, end=end)
    altered = prices.copy()
    altered.iloc[400:] *= 3
    b = discover_pairs(altered, cfg, end=end)
    assert a.table.equals(b.table)
    assert a.window[1] == str(end.date()) and (a.table["discovery_end"] == str(end.date())).all()
    assert (a.table["n_obs"] == 400).all()
