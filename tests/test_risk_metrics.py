import numpy as np
import pandas as pd

from quantpair.backtesting.costs import trade_costs
from quantpair.config import CostConfig, ExperimentConfig
from quantpair.risk.metrics import historical_var_es, pair_attribution, rolling_sharpe


def test_var_es():
    r = pd.Series(np.linspace(-0.10, 0.09, 100))
    out = historical_var_es(r, 0.95)
    assert np.isclose(out["var"], -np.quantile(r, 0.05)) and out["es"] >= out["var"]
    assert historical_var_es(r.iloc[:5])["var"] is None


def test_rolling_sharpe_zero_vol_nan():
    assert rolling_sharpe(pd.Series([0.0] * 200), 50).isna().all()


def test_attribution_sums():
    net = pd.DataFrame({"a": [1.0, -2.0], "b": [-1.0, 3.0]})
    out = pair_attribution(net, net + 0.5, pd.DataFrame({"a": [0.5, 0.5], "b": [0.5, 0.5]}))
    assert np.isclose(out["share_of_losses"].sum(), 1.0) and np.isclose(out.loc["a", "net_pnl"], -1)


def test_trade_costs_and_config_roundtrip():
    assert trade_costs(10_000, CostConfig(1, 5, 0)) == (1.0, 5.0)
    cfg = ExperimentConfig()
    cfg.backtest.costs.fee_bps = 7
    assert ExperimentConfig.from_dict(cfg.to_dict()) == cfg
