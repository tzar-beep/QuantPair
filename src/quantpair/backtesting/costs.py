"""Transaction-cost model: linear in traded notional, applied per leg."""
from __future__ import annotations

from quantpair.config import TRADING_DAYS, CostConfig


def trade_costs(traded_notional: float, cfg: CostConfig) -> tuple[float, float]:
    """(fees, slippage) for a trade of the given absolute notional."""
    return traded_notional * cfg.fee_bps / 1e4, traded_notional * cfg.slippage_bps / 1e4


def daily_borrow_rate(cfg: CostConfig) -> float:
    """Annual stock-loan fee spread evenly over trading sessions."""
    return cfg.borrow_bps_annual / 1e4 / TRADING_DAYS
