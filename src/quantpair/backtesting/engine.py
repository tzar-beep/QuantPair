"""Module E - transparent daily backtesting engine for pairs portfolios.

Timeline for each session t (adjusted closes):
1. Mark holdings to market: pnl = shares * (P_t - P_{t-1}).
2. Charge short-borrow fees on short notional carried overnight.
3. Read the target spread position decided at the close of t - lag (lag >= 1)
   and trade at the close of t. A signal therefore never earns the move that
   produced it. (Daily closes only; no intraday or open prices are used.)
4. Record equity = cash + sum(shares * price).

Accounting conventions
* Short sale proceeds are credited to cash; equity = cash + market value.
* No interest is earned on cash or paid on margin.
* Shares are fixed while a position is open (no re-hedging), so dollar
  neutrality drifts with prices.
* Costs = traded notional * (fee_bps + slippage_bps) / 1e4 on each leg.
  Slippage is a cost, not a change of fill price. A flip's traded notional
  equals close + open notional, so nothing is double-counted.
* Capital policy: a new position gets alloc_per_pair * current equity of gross
  notional, and is rejected if total gross exposure would exceed
  max_gross_leverage * equity. A rejected signal is skipped (not entered late).
* Gross exposure is summed per pair (no netting across pairs) - conservative.
* A leg with no price today cannot trade; the order is retried next session.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quantpair.backtesting.costs import daily_borrow_rate
from quantpair.backtesting.metrics import performance_metrics
from quantpair.config import BacktestConfig
from quantpair.strategy.pairs_strategy import PairSignals
from quantpair.strategy.position_sizing import hedge_shares


@dataclass
class BacktestResult:
    equity: pd.Series
    gross_equity: pd.Series
    returns: pd.Series
    exposure: pd.DataFrame
    costs: pd.DataFrame
    pair_pnl: pd.DataFrame          # daily net P&L per pair (after all costs)
    pair_gross_pnl: pd.DataFrame
    pair_costs: pd.DataFrame        # daily transaction + borrow cost per pair
    pair_gross_exposure: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict
    skipped_entries: int
    config: BacktestConfig
    pairs: list[str] = field(default_factory=list)


TRADE_COLS = ["pair", "direction", "signal_date", "entry_date", "exit_date", "exit_reason",
              "entry_z", "exit_z", "beta", "shares_y", "shares_x", "entry_notional",
              "holding_days", "gross_pnl", "costs", "borrow", "net_pnl", "return_on_notional", "open"]


def run_backtest(prices: pd.DataFrame, signals: list[PairSignals], cfg: BacktestConfig,
                 start=None, end=None) -> BacktestResult:
    if cfg.execution_lag < 1:
        raise ValueError("execution_lag must be >= 1.")
    dates = prices.loc[start:end].index
    if len(dates) < 2:
        raise ValueError("Backtest window needs at least two sessions.")
    tickers = sorted({s.y for s in signals} | {s.x for s in signals})
    full = prices.reindex(columns=tickers)
    raw = full.loc[dates].to_numpy(float)
    val = full.ffill().loc[dates].to_numpy(float)     # last known price, for valuation only
    col = {t: i for i, t in enumerate(tickers)}
    n, P, lag = len(dates), len(signals), cfg.execution_lag

    tgt = np.zeros((n, P), dtype=int)
    beta = np.full((n, P), np.nan)
    zsig = np.full((n, P), np.nan)
    evt = np.full((n, P), "", dtype=object)
    for j, s in enumerate(signals):
        f = s.frame.reindex(prices.index)               # market calendar -> lag in sessions
        tgt[:, j] = f["position"].ffill().fillna(0).shift(lag).fillna(0).loc[dates].astype(int)
        beta[:, j] = f["beta"].ffill().shift(lag).loc[dates]
        zsig[:, j] = f["z"].shift(lag).loc[dates]
        evt[:, j] = f["event"].fillna("").shift(lag).fillna("").loc[dates]
    iy = np.array([col[s.y] for s in signals], dtype=int)
    ix = np.array([col[s.x] for s in signals], dtype=int)

    c = cfg.costs
    fee_r, slip_r, borrow_r = c.fee_bps / 1e4, c.slippage_bps / 1e4, daily_borrow_rate(c)
    cash = float(cfg.initial_capital)
    nY, nX = np.zeros(P), np.zeros(P)
    pos = np.zeros(P, dtype=int)
    blocked = np.zeros(P, dtype=int)
    equity = np.zeros(n)
    g_pnl, net_pnl, p_cost, p_gross = (np.zeros((n, P)) for _ in range(4))
    fees, slips, borrows, traded, gross_exp, net_exp, n_open = (np.zeros(n) for _ in range(7))
    open_tr: list[dict | None] = [None] * P
    trades: list[dict] = []
    skipped = 0

    for i in range(n):
        py, px = val[i, iy], val[i, ix]
        g = np.nan_to_num(nY * (py - val[i - 1, iy]) + nX * (px - val[i - 1, ix])) if i else np.zeros(P)
        bc = np.nan_to_num(np.maximum(-nY, 0) * py + np.maximum(-nX, 0) * px) * borrow_r
        cash -= bc.sum()
        borrows[i] = bc.sum()
        g_pnl[i], net_pnl[i], p_cost[i] = g, g - bc, bc
        for j in range(P):
            if open_tr[j] is not None:
                open_tr[j]["gross_pnl"] += g[j]
                open_tr[j]["borrow"] += bc[j]
        equity_pre = cash + np.nan_to_num(nY * py + nX * px).sum()
        last = i == n - 1

        for j in range(P):
            want, reason = int(tgt[i, j]), evt[i, j] or "signal"
            if last and cfg.close_at_end:
                want, reason = 0, "end_of_test"
            if equity_pre <= 0:
                want, reason = 0, "equity_depleted"
            if blocked[j]:
                if want == blocked[j]:
                    want = 0
                else:
                    blocked[j] = 0
            if want == pos[j]:
                continue
            ry, rx = raw[i, iy[j]], raw[i, ix[j]]
            if not (np.isfinite(ry) and np.isfinite(rx)):
                continue
            newY = newX = 0.0
            if want != 0:
                b = beta[i, j]
                budget = cfg.alloc_per_pair * equity_pre
                others = sum(abs(nY[k]) * py[k] + abs(nX[k]) * px[k] for k in range(P) if k != j)
                if not np.isfinite(b) or others + budget > cfg.max_gross_leverage * equity_pre * (1 + 1e-9):
                    skipped += 1
                    blocked[j], want, reason = want, 0, "capital_limit"
                    if pos[j] == 0:
                        continue
                else:
                    newY, newX = hedge_shares(want, budget, ry, rx, b)
            dY, dX = newY - nY[j], newX - nX[j]
            notional = abs(dY) * ry + abs(dX) * rx
            fee_c, slip_c = notional * fee_r, notional * slip_r
            cash -= dY * ry + dX * rx + fee_c + slip_c
            fees[i] += fee_c
            slips[i] += slip_c
            traded[i] += notional
            net_pnl[i, j] -= fee_c + slip_c
            p_cost[i, j] += fee_c + slip_c
            rate = fee_r + slip_r
            if pos[j] != 0 and open_tr[j] is not None:
                tr = open_tr[j]
                tr["costs"] += (abs(nY[j]) * ry + abs(nX[j]) * rx) * rate
                tr.update(exit_date=dates[i], exit_reason=reason, exit_z=zsig[i, j],
                          holding_days=i - tr.pop("_i"), open=False)
                trades.append(tr)
                open_tr[j] = None
            if want != 0:
                open_tr[j] = {
                    "pair": signals[j].name, "direction": "long_spread" if want > 0 else "short_spread",
                    "signal_date": dates[i - lag] if i >= lag else pd.NaT, "entry_date": dates[i],
                    "exit_date": pd.NaT, "exit_reason": "", "entry_z": zsig[i, j], "exit_z": np.nan,
                    "beta": beta[i, j], "shares_y": newY, "shares_x": newX,
                    "entry_notional": abs(newY) * ry + abs(newX) * rx, "holding_days": 0,
                    "gross_pnl": 0.0, "costs": (abs(newY) * ry + abs(newX) * rx) * rate,
                    "borrow": 0.0, "open": True, "_i": i}
            nY[j], nX[j], pos[j] = newY, newX, want

        p_gross[i] = np.nan_to_num(np.abs(nY) * py + np.abs(nX) * px)
        mv = np.nan_to_num(nY * py + nX * px)
        equity[i] = cash + mv.sum()
        gross_exp[i], net_exp[i], n_open[i] = p_gross[i].sum(), mv.sum(), (pos != 0).sum()

    for tr in open_tr:
        if tr is not None:
            tr["holding_days"] = n - 1 - tr.pop("_i")
            trades.append(tr)
    tdf = pd.DataFrame(trades, columns=TRADE_COLS)
    if len(tdf):
        tdf["net_pnl"] = tdf["gross_pnl"] - tdf["costs"] - tdf["borrow"]
        tdf["return_on_notional"] = tdf["net_pnl"] / tdf["entry_notional"]
        tdf["open"] = tdf["open"].astype(bool)

    names = [s.name for s in signals]
    eq = pd.Series(equity, index=dates, name="equity")
    rets = eq.pct_change()
    rets.iloc[0] = eq.iloc[0] / cfg.initial_capital - 1
    gross_eq = pd.Series(cfg.initial_capital + g_pnl.sum(axis=1).cumsum(), index=dates, name="gross_equity")
    costs = pd.DataFrame({"fees": fees, "slippage": slips, "borrow": borrows}, index=dates)
    exposure = pd.DataFrame({"gross": gross_exp, "net": net_exp, "n_open": n_open,
                             "gross_pct": gross_exp / equity, "net_pct": net_exp / equity}, index=dates)
    metrics = performance_metrics(eq, rets.rename("returns"), cfg.initial_capital, tdf,
                                  g_pnl.sum(), costs.to_numpy().sum(), traded.sum(),
                                  exposure["gross"], exposure["net"], cfg.risk_free_rate)
    metrics["skipped_entries"] = skipped
    mk = lambda a: pd.DataFrame(a, index=dates, columns=names)  # noqa: E731
    return BacktestResult(eq, gross_eq, rets.rename("returns"), exposure, costs, mk(net_pnl),
                          mk(g_pnl), mk(p_cost), mk(p_gross), tdf, metrics, skipped, cfg, names)
