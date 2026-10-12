from dataclasses import replace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from quantpair.backtesting.engine import run_backtest
from quantpair.config import HEDGE_METHODS, StrategyConfig
from quantpair.research.spread_model import fit_hedge_ratio, kalman_hedge_ratio, rolling_hedge_ratio
from quantpair.strategy.pairs_strategy import build_pair_signals
from ui import state
from ui.components import C, empty, header, kpis, money, num, pct, plot, section, tone

p = state.require_data()
c = state.cfg()
res = state.discovery()
header("Strategy Lab", "Explore spread signals for one pair. Exploratory analysis — final evaluation belongs in "
       "Backtesting / Walk-Forward on unseen data.", [state.data_badge()])
if res is None or "status" not in res.table:
    empty("No discovery results", "Run Pair Discovery first; the hedge ratio is fitted on its window.")
    st.stop()
tested = res.table[res.table["status"] == "tested"]
labels = {f"{r.pair}{'  ✓ eligible' if r.eligible else ''}": r.pair for r in tested.itertuples()}
pair = labels[st.selectbox("Pair", list(labels))]
row = tested.set_index("pair").loc[pair]
s = c.strategy

a, b, cc, d = st.columns(4)
lookback = a.number_input("Z-score lookback", 5, 500, s.lookback, 5)
entry = b.number_input("Entry |z|", 0.1, 10.0, s.entry_z, 0.1)
exit_ = cc.number_input("Exit |z|", 0.0, 10.0, s.exit_z, 0.1)
hedge = d.selectbox("Hedge ratio", HEDGE_METHODS, HEDGE_METHODS.index(s.hedge_method))
a, b, cc, d = st.columns(4)
use_stop = a.toggle("Stop-loss", s.stop_z is not None)
stop = b.number_input("Stop |z|", 0.2, 20.0, s.stop_z or 4.0, 0.1, disabled=not use_stop)
use_mh = cc.toggle("Max holding period", s.max_hold is not None)
mh = d.number_input("Max hold (sessions)", 1, 1000, s.max_hold or 60, 5, disabled=not use_mh)
a, a2, b = st.columns([1, 1, 3])
hwin = a.number_input("Rolling hedge window", 20, 1000, s.hedge_window, 21, disabled=hedge != "rolling_ols")
kdelta = a2.number_input("Kalman δ", 1e-7, 0.1, s.kalman_delta, format="%.1e", disabled=hedge != "kalman")
sp = state.splits()
seg = b.radio("Evaluation period", ["Validation", "Discovery window (in-sample)", "Custom"], horizontal=True)
fit = (pd.Timestamp(res.window[0]), pd.Timestamp(res.window[1]))
if seg == "Validation":
    ev = sp["validation"]
elif seg.startswith("Discovery"):
    ev = fit
else:
    d1, d2 = st.columns(2)
    ev = (pd.Timestamp(d1.date_input("From", sp["validation"][0].date())),
          pd.Timestamp(d2.date_input("To", sp["validation"][1].date())))
try:
    strat = StrategyConfig(int(lookback), float(entry), float(exit_), float(stop) if use_stop else None,
                           int(mh) if use_mh else None, hedge, int(hwin), c.discovery.use_intercept,
                           float(kdelta), c.discovery.coint_trend == "ct" and hedge == "static_ols")
except ValueError as exc:
    st.error(f"Invalid parameters: {exc}")
    st.stop()

in_sample = ev[0] <= fit[1]
st.markdown(f'<span class="qp-tag {"warn" if in_sample else "ok"}">'
            f'{"IN-SAMPLE · exploratory" if in_sample else "OUT-OF-SAMPLE"}</span>'
            f'<span class="qp-tag">fit {res.window[0]} → {res.window[1]}</span>'
            f'<span class="qp-tag">eval {ev[0].date()} → {ev[1].date()}</span>', unsafe_allow_html=True)
sig = build_pair_signals(p, row.y, row.x, strat, fit, ev)
f = sig.frame
if f.empty:
    st.error("No overlapping prices in the evaluation period.")
    st.stop()
section("Signal summary")
ev_counts = f["event"].value_counts()
kpis([("Long entries", int(ev_counts.get("enter_long", 0))), ("Short entries", int(ev_counts.get("enter_short", 0))),
      ("Reversion exits", int(ev_counts.get("exit", 0))), ("Stops", int(ev_counts.get("stop", 0)), "neg"),
      ("Max-hold exits", int(ev_counts.get("max_hold", 0))), ("Time in position", pct((f["position"] != 0).mean(), 1)),
      ("β (latest)", num(f["beta"].iloc[-1], 3))])

section("Spread & z-score", "markers = executed signal events")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.45, 0.55],
                    subplot_titles=("Spread", "Rolling z-score with signals"))
fig.add_trace(go.Scatter(x=f.index, y=f["spread"], name="spread", line=dict(color=C["accent"], width=1.2)), 1, 1)
fig.add_trace(go.Scatter(x=f.index, y=f["z"], name="z", line=dict(color=C["series"][2], width=1.2)), 2, 1)
for lvl, col, dash in [(entry, C["neg"], "dot"), (-entry, C["neg"], "dot"), (exit_, C["muted"], "dash"),
                       (-exit_, C["muted"], "dash")] + ([(stop, C["warn"], "dashdot"), (-stop, C["warn"], "dashdot")]
                                                        if use_stop else []):
    fig.add_hline(y=lvl, line=dict(color=col, dash=dash, width=1), row=2, col=1)
marks = {"enter_long": ("triangle-up", C["pos"], "long entry"), "enter_short": ("triangle-down", C["neg"], "short entry"),
         "exit": ("circle", C["text"], "exit"), "stop": ("x", C["warn"], "stop"), "max_hold": ("square", C["muted"], "max hold")}
for evn, (sym, col, name) in marks.items():
    m = f[f["event"] == evn]
    if len(m):
        for r_ in (1, 2):
            fig.add_trace(go.Scatter(x=m.index, y=m["spread" if r_ == 1 else "z"], mode="markers", name=name,
                                     marker=dict(symbol=sym, size=8, color=col), showlegend=r_ == 2), r_, 1)
fig.update_annotations(font=dict(size=12, color=C["text"]))
plot(fig, height=560)

section("Hedge-ratio methods")
with st.expander("Compare hedge-ratio methods (static OLS vs rolling OLS vs Kalman)"):
    yy, xx = p[row.y].loc[:ev[1]], p[row.x].loc[:ev[1]]
    stat = fit_hedge_ratio(yy.loc[fit[0]:fit[1]], xx.loc[fit[0]:fit[1]], c.discovery.use_intercept).beta
    rol = rolling_hedge_ratio(yy, xx, int(hwin), c.discovery.use_intercept)["beta"]
    kal = kalman_hedge_ratio(yy, xx, float(kdelta), use_intercept=c.discovery.use_intercept)["beta"]
    hf = go.Figure([go.Scatter(x=rol.index, y=rol, name=f"rolling OLS ({int(hwin)}d)", line=dict(width=1.1)),
                    go.Scatter(x=kal.index, y=kal, name=f"Kalman (δ={kdelta:.0e})", line=dict(width=1.1))])
    hf.add_hline(y=stat, line=dict(color=C["muted"], dash="dash"), annotation_text="static OLS (fit window)")
    hf.add_vrect(x0=ev[0], x1=ev[1], fillcolor=C["accent"], opacity=0.06, line_width=0)
    plot(hf, height=300, title="Hedge ratio β over time (all estimates use past data only, except static = fit window)")
    rows = []
    for m in HEDGE_METHODS:
        sg = build_pair_signals(p, row.y, row.x, replace(strat, hedge_method=m), fit, ev)
        bm = run_backtest(p, [sg], c.backtest, *ev).metrics
        rows.append({"method": m, "spread_std": sg.frame["spread"].std(), "total_return": bm["total_return"],
                     "sharpe": bm["sharpe"], "n_trades": bm["n_trades"], "total_costs": bm["total_costs"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Adaptive hedges reduce stale-beta risk but can absorb genuine spread moves (the filter "
               "'explains away' divergence), weakening the mean-reversion signal.")

a, b = st.columns(2)
if a.button("Use these parameters in the experiment", type="primary"):
    c.strategy = strat
    st.success("Strategy parameters saved to the experiment configuration (used by Backtesting and Walk-Forward).")
if b.button("Quick backtest this pair on the evaluation period"):
    bt = run_backtest(p, [sig], c.backtest, *ev).metrics
    kpis([("Total return", pct(bt["total_return"]), tone(bt["total_return"])), ("Sharpe", num(bt["sharpe"])),
          ("Max DD", pct(bt["max_drawdown"]), "neg"), ("Trades", bt["n_trades"]),
          ("Gross P&L", money(bt["gross_pnl"])), ("Costs", money(bt["total_costs"])),
          ("Net P&L", money(bt["net_pnl"]), tone(bt["net_pnl"]))])
    if in_sample:
        st.warning("In-sample result: pair and hedge ratio were chosen on these same dates.")
