"""Central, serialisable configuration for every QuantPair experiment.

All research settings live in plain dataclasses so an experiment can be saved
to JSON and reproduced exactly (see ``ExperimentConfig.to_dict/from_dict``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

# Daily US equities: ~252 trading sessions per year. Used for every
# annualisation (vol * sqrt(252), mean * 252, CAGR over n/252 years).
TRADING_DAYS = 252

DEFAULT_UNIVERSE = [
    "SPY", "QQQ", "IWM", "XLF", "XLK", "XLE", "XLV",
    "AAPL", "MSFT", "JPM", "BAC", "KO", "PEP", "WMT", "COST",
]
BENCHMARK = "SPY"

# Starter universes. Same-business peers are more plausible cointegration
# candidates than broad ETFs. The last set is a positive control: near-identical
# assets (same index / same asset / share classes) should be detected.
UNIVERSE_PRESETS: dict[str, list[str]] = {
    "Default (ETFs + large caps)": DEFAULT_UNIVERSE,
    "Consumer staples": ["KO", "PEP", "PG", "CL", "KMB", "GIS", "MDLZ", "HSY", "KHC", "CPB"],
    "US banks": ["JPM", "BAC", "C", "WFC", "USB", "PNC", "TFC", "MS", "GS"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "OXY", "SLB", "PSX", "MPC", "VLO"],
    "Utilities": ["DUK", "SO", "D", "AEP", "XEL", "ED", "PEG", "WEC", "EIX"],
    "Positive control (same index / same asset)": ["SPY", "IVV", "VOO", "GLD", "IAU", "GOOGL", "GOOG"],
}
HEDGE_METHODS = ("static_ols", "rolling_ols", "kalman")


@dataclass
class DiscoveryConfig:
    min_obs: int = 252                 # minimum aligned observations per pair
    max_missing_frac: float = 0.05     # max share of missing sessions per ticker
    coint_alpha: float = 0.05          # raw per-test significance level
    fdr_q: float = 0.10                # Benjamini-Hochberg false-discovery rate
    use_intercept: bool = True         # y = a + b*x + e  (False: y = b*x + e)
    coint_trend: str = "c"             # "c": constant | "ct": constant + linear time trend
    stability_window: int = 126        # rolling window for hedge-ratio stability
    min_half_life: float = 1.0         # days; faster than this is likely noise
    max_half_life: float = 60.0        # days; slower is impractical to trade
    rank_weights: tuple[float, float, float] = (0.5, 0.3, 0.2)  # evidence, stability, history

    def __post_init__(self) -> None:
        self.rank_weights = tuple(float(w) for w in self.rank_weights)  # type: ignore[assignment]
        if not 0 < self.coint_alpha < 1 or not 0 < self.fdr_q < 1:
            raise ValueError("Significance levels must lie in (0, 1).")
        if self.min_obs < 30:
            raise ValueError("min_obs must be at least 30.")
        if self.coint_trend not in ("c", "ct"):
            raise ValueError("coint_trend must be 'c' or 'ct'.")
        if self.coint_trend == "ct" and not self.use_intercept:
            raise ValueError("A trend term requires the intercept.")


@dataclass
class StrategyConfig:
    lookback: int = 60                 # rolling z-score window (sessions)
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float | None = 4.0         # None disables the stop
    max_hold: int | None = 60          # sessions; None disables
    hedge_method: str = "static_ols"   # "static_ols" (fit on training) | "rolling_ols" | "kalman"
    hedge_window: int = 126            # used by rolling_ols
    use_intercept: bool = True
    kalman_delta: float = 1e-4         # Kalman state-noise ratio (higher = faster-adapting beta)
    use_trend: bool = False            # static_ols only: y = a + g*t + b*x (t = sessions since fit start)

    def __post_init__(self) -> None:
        if self.lookback < 5:
            raise ValueError("lookback must be >= 5.")
        if not 0 <= self.exit_z < self.entry_z:
            raise ValueError("Require 0 <= exit_z < entry_z.")
        if self.stop_z is not None and self.stop_z <= self.entry_z:
            raise ValueError("stop_z must exceed entry_z.")
        if self.hedge_method not in HEDGE_METHODS:
            raise ValueError(f"hedge_method must be one of {HEDGE_METHODS}.")
        if not 0 < self.kalman_delta < 1:
            raise ValueError("kalman_delta must lie in (0, 1).")
        if self.max_hold is not None and self.max_hold < 1:
            raise ValueError("max_hold must be >= 1.")


@dataclass
class CostConfig:
    fee_bps: float = 1.0               # commission/fees per unit traded notional
    slippage_bps: float = 5.0          # half-spread + impact per unit traded notional
    borrow_bps_annual: float = 25.0    # stock-loan fee on short notional, charged daily


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    alloc_per_pair: float = 0.20       # gross notional per new pair position, as share of equity
    max_gross_leverage: float = 1.0    # cap on total gross exposure / equity
    execution_lag: int = 1             # signal at close t -> trade at close t+lag
    risk_free_rate: float = 0.0        # annual, for Sharpe/Sortino excess returns
    close_at_end: bool = True          # liquidate open positions on the last test day
    costs: CostConfig = field(default_factory=CostConfig)

    def __post_init__(self) -> None:
        if self.execution_lag < 1:
            raise ValueError("execution_lag must be >= 1 to avoid look-ahead.")
        if self.initial_capital <= 0 or self.alloc_per_pair <= 0:
            raise ValueError("Capital and allocation must be positive.")


@dataclass
class WalkForwardConfig:
    train_days: int = 504              # ~2 years of sessions for discovery/fitting
    test_days: int = 126               # ~6 months out-of-sample per window
    expanding: bool = False            # True: train window grows from the first date
    top_k: int = 5                     # max pairs traded per window
    selection: str = "fdr"             # "fdr" (BH-adjusted) | "raw" (exploratory)


@dataclass
class ExperimentConfig:
    universe: list[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))
    start: str = "2015-01-01"
    end: str | None = None
    train_frac: float = 0.6            # chronological split: train / validation / final test
    val_frac: float = 0.2
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    walkforward: WalkForwardConfig = field(default_factory=WalkForwardConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        return _from_dict(cls, data)


_NESTED = {"discovery": DiscoveryConfig, "strategy": StrategyConfig, "backtest": BacktestConfig,
           "walkforward": WalkForwardConfig, "costs": CostConfig}


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    kwargs = {}
    for f in fields(cls):
        if f.name in data:
            value = data[f.name]
            if f.name in _NESTED and isinstance(value, dict):
                value = _from_dict(_NESTED[f.name], value)
            kwargs[f.name] = value
    return cls(**kwargs)
