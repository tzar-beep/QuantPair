"""Hedge-ratio-aware share sizing.

For direction d (+1 long spread, -1 short spread) and budget B of *gross*
notional:  n_y = d * B / (P_y + |beta| * P_x),  n_x = -beta * n_y.
So |n_y| P_y + |n_x| P_x = B. With beta > 0 the legs have opposite signs
(classic long/short pair); with beta < 0 both legs share the same sign, which
is still the correct hedge for the residual y - beta*x.
"""
from __future__ import annotations


def hedge_shares(direction: int, budget: float, price_y: float, price_x: float,
                 beta: float) -> tuple[float, float]:
    denom = price_y + abs(beta) * price_x
    if direction == 0 or denom <= 0 or budget <= 0:
        return 0.0, 0.0
    n_y = direction * budget / denom
    return n_y, -beta * n_y
