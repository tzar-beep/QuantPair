from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from quantpair.analytics.market import drawdown
from quantpair.config import HEDGE_METHODS, BacktestConfig, CostConfig, StrategyConfig
from quantpair.reporting.exports import csv_bytes
from quantpair.validation.robustness import relationship_stability_warning, research_warnings
from ui import runs, state
from ui.components import C, area, empty, header, kpis, money, num, pct, plot, section, tone, warnings_box

p = state.require_data()
c = state.cfg()
header("Backtesting", "Custom daily engine: lagged execution, both legs, fees, slippage, borrow, capital limits.",
       [state.data_badge()])
sp = state.splits()
s, b = c.strategy, c.backtest

with st.form("bt_form"):
    a, bb, cc = st.columns([2, 2, 1])
    seg = a.radio("Test period", runs.SEGMENTS, horizontal=True)
    sel_label = bb.radio("Pair selection", list(runs.SELECTIONS), horizontal=True)
    top_k = cc.number_input("Top-k pairs", 1, 50, c.walkforward.top_k)
    disc = state.discovery()
    manual = st.multiselect("Manual pairs (used when 'Manual pairs' is selected; from current discovery)",
                            disc.table["pair"].tolist() if disc is not None and "pair" in disc.table else [])
    d1, d2, d3, d4 = st.columns(4)
    cf0 = d1.date_input("Custom fit start", sp["train"][0].date())
    cf1 = d2.date_input("Custom fit end", sp["train"][1].date())
    ce0 = d3.date_input("Custom test start", sp["validation"][0].date())
    ce1 = d4.date_input("Custom test end", sp["validation"][1].date())
    st.markdown("**Strategy**")
    x = st.columns(6)
    lookback = x[0].number_input("Lookback", 5, 500, s.lookback, 5)
    entry = x[1].number_input("Entry z", 0.1, 10.0, s.entry_z, 0.1)
    exit_ = x[2].number_input("Exit z", 0.0, 10.0, s.exit_z, 0.1)
    stop = x[3].number_input("Stop z (0 = off)", 0.0, 20.0, s.stop_z or 0.0, 0.1)
    mh = x[4].number_input("Max hold (0 = off)", 0, 1000, s.max_hold or 0, 5)
    hedge = x[5].selectbox("Hedge", HEDGE_METHODS, HEDGE_METHODS.index(s.hedge_method))
    st.markdown("**Portfolio & costs**")
    x = st.columns(5)
    cap = x[0].number_input("Starting capital", 1_000.0, 1e10, b.initial_capital, 10_000.0)
    alloc = x[1].number_input("Gross alloc per pair", 0.01, 2.0, b.alloc_per_pair, 0.05)
    lev = x[2].number_input("Max gross / equity", 0.1, 10.0, b.max_gross_leverage, 0.1)
    lag = x[3].number_input("Execution lag (sessions)", 1, 10, b.execution_lag)
    rf = x[4].number_input("Risk-free rate (annual)", 0.0, 0.2, b.risk_free_rate, 0.005, format="%.3f")
    x = st.columns(4)
    fee = x[0].number_input("Fees (bps)", 0.0, 100.0, b.costs.fee_bps, 0.5)
    slip = x[1].number_input("Slippage (bps)", 0.0, 100.0, b.costs.slippage_bps, 0.5)
    borrow = x[2].number_input("Borrow (bps / yr)", 0.0, 2000.0, b.costs.borrow_bps_annual, 5.0)
    close_end = x[3].toggle("Liquidate at end", b.close_at_end)
    go_ = st.form_submit_button("Run backtest", type="primary")

if go_:
    try:
        c.strategy = replace(s, lookback=int(lookback), entry_z=float(entry), exit_z=float(exit_),
                             stop_z=float(stop) or None, max_hold=int(mh) or None, hedge_method=hedge)
        StrategyConfig(**{k: getattr(c.strategy, k) for k in c.strategy.__dataclass_fields__})
        c.backtest = BacktestConfig(float(cap), float(alloc), float(lev), int(lag), float(rf), close_end,
                                    CostConfig(float(fee), float(slip), float(borrow)))
    except ValueError as exc:
        st.error(f"Invalid settings: {exc}")
        st.stop()
    selection = runs.SELECTIONS[sel_label]
    if selection == "manual" and not manual:
        st.error("Pick at least one manual pair.")
        st.stop()
    custom = ((pd.Timestamp(cf0), pd.Timestamp(cf1)), (pd.Timestamp(ce0), pd.Timestamp(ce1)))
    with st.spinner("Discovering on fit window and simulating…"):
        runs.run_backtest_job(seg, selection, int(top_k), manual, custom if seg == "Custom" else None)

bt = state.get("backtest")
if bt is None:
    empty("No backtest yet", "Configure the run above. Pairs are selected on the fit window, then traded on the test period.")
    st.stop()
pipe = bt["pipe"]
r, m = pipe.backtest, pipe.backtest.metrics
tags = [("warn" if pipe.in_sample else "ok", "IN-SAMPLE" if pipe.in_sample else "OUT-OF-SAMPLE"),
        ("", bt["segment"]), ("", f"fit {str(pipe.fit_window[0])[:10]} → {str(pipe.fit_window[1])[:10]}"),
        ("", f"test {str(pipe.eval_window[0])[:10]} → {str(pipe.eval_window[1])[:10]}")]
if bt["selection"] == "raw":
    tags.append(("warn", "RAW p SELECTION · exploratory"))
st.markdown("".join(f'<span class="qp-tag {k}">{v}</span>' for k, v in tags), unsafe_allow_html=True)
if bt["segment"] == "Final test":
    st.warning("Final-test results: re-tuning after looking at these numbers turns the test set into a validation set.")
st.caption("Pairs traded: " + (", ".join(pipe.selected["pair"]) if len(pipe.selected) else "none"))
if pipe.selected.empty:
    st.info("No pairs passed the selection rule on the fit window, so the strategy stayed in cash. "
            "That is a legitimate research outcome, not an error.")

section("Performance", "after fees, slippage and borrow")
kpis([("Total return", pct(m["total_return"]), tone(m["total_return"])), ("CAGR", pct(m["cagr"]), tone(m["cagr"])),
      ("Ann. vol", pct(m["ann_vol"])), ("Sharpe", num(m["sharpe"]), tone(m["sharpe"])),
      ("Sortino", num(m["sortino"]), tone(m["sortino"])), ("Max drawdown", pct(m["max_drawdown"]), "neg"),
      ("Calmar", num(m["calmar"]))])
kpis([("Trades", m["n_trades"]), ("Win rate", pct(m["win_rate"], 1)), ("Profit factor", num(m["profit_factor"])),
      ("Avg trade", pct(m["avg_trade_return"]), tone(m["avg_trade_return"])),
      ("Avg hold", num(m["avg_holding_days"], 1) + " d" if m["avg_holding_days"] else "—"),
      ("Turnover", num(m["turnover"], 1) + "x/yr" if m["turnover"] is not None else "—"),
      ("Avg gross exp.", pct(m["avg_gross_exposure"], 1))])
kpis([("Gross P&L", money(m["gross_pnl"]), tone(m["gross_pnl"])), ("Total costs", money(m["total_costs"]), "neg"),
      ("Net P&L", money(m["net_pnl"]), tone(m["net_pnl"])), ("Skipped entries", m["skipped_entries"]),
      ("Time in market", pct(m["time_in_market"], 1))])
warnings_box(research_warnings(r) + relationship_stability_warning(pipe.selected))

section("Equity, drawdown & return distribution")
k0 = r.config.initial_capital
pc = lambda s: (s / k0 - 1) * 100  # noqa: E731
lo = min(pc(r.equity).min(), pc(r.gross_equity).min(), 0)
fig = go.Figure(area(r.equity.index, pc(r.equity), "Net", C["accent"], lo))
fig.add_trace(go.Scatter(x=r.gross_equity.index, y=pc(r.gross_equity), name="Gross (before costs)",
                         line=dict(color=C["series"][1], width=1.1, dash="dot")))
if bt["bench"] is not None:
    fig.add_trace(go.Scatter(x=bt["bench"].index, y=pc(bt["bench"]), name=bt["bench"].name, yaxis="y2",
                             line=dict(color=C["muted"], width=1)))
fig.add_hline(y=0, line=dict(color=C["border"], width=1))
fig.update_layout(yaxis=dict(title="strategy %"), yaxis2=dict(title="benchmark % (right)", overlaying="y", side="right", showgrid=False, zeroline=False))
plot(fig, height=360, title="Cumulative return (%)")
st.caption("SPY is a market benchmark, not a risk-matched comparison for a market-neutral strategy. Cash baseline = flat line.")

a, b_ = st.columns(2)
with a:
    dd = drawdown(pd.concat([pd.Series([r.config.initial_capital], index=[r.equity.index[0] - pd.Timedelta(days=1)]),
                             r.equity])).iloc[1:]
    plot(go.Figure(area(dd.index, dd * 100, "drawdown %", C["neg"], 0.0)), height=280, title="Drawdown (%)", legend=False)
with b_:
    rr = r.returns[r.returns != 0] * 100
    plot(go.Figure(go.Histogram(x=rr, nbinsx=60, marker_color=C["accent"], name="daily return %")),
         height=280, title=f"Daily returns, active days (%) · n={len(rr)}", legend=False)
section("Attribution")
if len(r.pairs):
    cum = r.pair_pnl.cumsum()
    plot(go.Figure([go.Scatter(x=cum.index, y=cum[k], name=k, line=dict(width=1.2)) for k in cum]),
         height=300, title="Cumulative net P&L by pair")

section("Trade ledger")
tr = r.trades
if tr.empty:
    st.caption("No trades.")
else:
    st.dataframe(tr, hide_index=True, width="stretch", height=320,
                 column_config={k: st.column_config.NumberColumn(format="%.2f") for k in
                                ("entry_z", "exit_z", "beta", "shares_y", "shares_x", "entry_notional", "gross_pnl",
                                 "costs", "borrow", "net_pnl")}
                 | {"return_on_notional": st.column_config.NumberColumn(format="%.4f")})
    st.download_button("Download trades CSV", csv_bytes(tr), "trades.csv", "text/csv")
with st.expander("All metrics"):
    st.dataframe(pd.DataFrame({"metric": list(m), "value": [None if v is None else float(v) if
                                                            isinstance(v, (int, float, np.number)) else v
                                                            for v in m.values()]}), hide_index=True)
