import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from quantpair.analytics.market import drawdown, rolling_volatility
from quantpair.config import BENCHMARK
from quantpair.risk.metrics import (
    exposure_concentration,
    historical_var_es,
    pair_attribution,
    rolling_sharpe,
    tail_summary,
)
from quantpair.risk.regimes import regime_performance, volatility_regime
from quantpair.risk.stress_testing import cost_stress, pair_scenarios, volatility_stress
from ui import state
from ui.components import C, area, empty, header, kpis, money, num, pct, plot, section

p = state.require_data()
c = state.cfg()
header("Risk Analytics", "Drawdowns, volatility, exposure, attribution, tail risk and hypothetical stress scenarios "
       "for the most recent backtest.", [state.data_badge()])
bt = state.get("backtest")
if bt is None:
    empty("No backtest to analyse", "Run a backtest first; this page analyses its daily returns and positions.")
    st.stop()
pipe = bt["pipe"]
r = pipe.backtest
st.caption(f"Analysing: {bt['segment']} · {str(pipe.eval_window[0])[:10]} → {str(pipe.eval_window[1])[:10]} · "
           f"pairs: {', '.join(r.pairs) or 'none'}")

a, b, cc = st.columns(3)
level = a.select_slider("VaR / ES confidence", [0.90, 0.95, 0.975, 0.99], 0.95)
vwin = b.number_input("VaR estimation window (sessions, 0 = all)", 0, 5000, 0, 21)
rwin = cc.number_input("Rolling window (sessions)", 20, 504, 63, 21)
active = r.returns
section("Tail risk", "historical simulation")
ve = historical_var_es(active, level, int(vwin) or None)
tail = tail_summary(active)
kpis([(f"1-day VaR {level:.1%}", pct(ve["var"]), "neg", f"n = {ve['n']}"),
      (f"1-day ES {level:.1%}", pct(ve["es"]), "neg"), ("Worst day", pct(tail.get("worst_day")), "neg"),
      ("Skew", num(tail.get("skew"))), ("Excess kurtosis", num(tail.get("excess_kurtosis"))),
      ("Days < −2σ", tail.get("days_below_2sd", "—"), "", f"normal ≈ {tail.get('expected_under_normal', 0):.0f}"),
      ("Max drawdown", pct(r.metrics["max_drawdown"]), "neg")])
st.caption("Historical simulation on daily portfolio returns (simple returns on equity). Losses shown as positive "
           "fractions. Flat days are included, which lowers VaR for a strategy that is often in cash.")

section("Drawdown, volatility & exposure")
a, b = st.columns(2)
with a:
    dd = drawdown(r.equity)
    plot(go.Figure(area(dd.index, dd * 100, "drawdown %", C["neg"], 0.0)),
         height=260, title="Drawdown timeline (%)", legend=False)
    rv = rolling_volatility(r.returns, int(rwin))
    rs = rolling_sharpe(r.returns, int(rwin), r.config.risk_free_rate)
    f = go.Figure([go.Scatter(x=rv.index, y=rv * 100, name="ann. vol %", line=dict(color=C["accent"], width=1.2)),
                   go.Scatter(x=rs.index, y=rs, name="rolling Sharpe", yaxis="y2", line=dict(color=C["series"][1], width=1))])
    f.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False))
    plot(f, height=260, title=f"Rolling volatility & Sharpe ({rwin}d)")
with b:
    e = r.exposure
    plot(go.Figure([go.Scatter(x=e.index, y=e["gross_pct"] * 100, name="gross % equity", line=dict(color=C["accent"], width=1.2)),
                    go.Scatter(x=e.index, y=e["net_pct"] * 100, name="net % equity", line=dict(color=C["series"][1], width=1))]),
         height=260, title="Exposure over time")
    conc = exposure_concentration(r.pair_gross_exposure)
    plot(go.Figure(go.Scatter(x=conc.index, y=conc["max_share"] * 100, line=dict(color=C["series"][2], width=1.1))),
         height=260, title="Largest pair share of gross exposure (%)", legend=False)

section("Attribution")
if r.pairs:
    att = pair_attribution(r.pair_pnl, r.pair_gross_pnl, r.pair_costs)
    a, b = st.columns([3, 2])
    with a:
        f = go.Figure([go.Bar(x=att.index, y=att["gross_pnl"], name="gross P&L", marker_color=C["series"][1]),
                       go.Bar(x=att.index, y=-att["costs"], name="costs", marker_color=C["neg"]),
                       go.Bar(x=att.index, y=att["net_pnl"], name="net P&L", marker_color=C["accent"])])
        plot(f.update_layout(barmode="group"), height=300, title="P&L contribution by pair")
    b.dataframe(att, width="stretch", column_config={k: st.column_config.NumberColumn(format="%.0f") for k in att}
                | {"share_of_losses": st.column_config.NumberColumn(format="%.2f")})
cc_ = r.costs.cumsum()
plot(go.Figure([go.Scatter(x=cc_.index, y=cc_[k], name=k, stackgroup="c") for k in cc_]),
     height=260, title=f"Cumulative transaction & borrow costs · total {money(r.metrics['total_costs'])}")

section("Stress scenarios (hypothetical)")
st.caption("What-if calculations on current sizing — not forecasts or historical events.")
a, b, cc, d, e_ = st.columns(5)
shock = a.number_input("Spread shock (σ)", 0.5, 10.0, 3.0, 0.5)
stall = b.number_input("No-reversion days", 5, 500, 60, 5)
berr = cc.number_input("Hedge-ratio error", 0.0, 2.0, 0.2, 0.05)
xmove = d.number_input("Move in x leg", 0.0, 1.0, 0.10, 0.01)
cost_m = e_.text_input("Cost multipliers", "1, 2, 3")
budget = c.backtest.alloc_per_pair * c.backtest.initial_capital
if pipe.signals:
    rows = []
    for sig in pipe.signals:
        sc = pair_scenarios(sig, budget, shock, int(stall), berr, xmove, c.backtest.costs.borrow_bps_annual)
        rows.append(sc.assign(pair=sig.name))
    st.dataframe(pd.concat(rows)[["pair", "scenario", "assumption", "loss", "loss_pct_of_budget"]], hide_index=True,
                 width="stretch", column_config={"loss": st.column_config.NumberColumn(format="$%.0f"),
                                                 "loss_pct_of_budget": st.column_config.NumberColumn(format="%.3f")})
a, b = st.columns(2)
with a:
    st.markdown("**Higher volatility** — returns scaled around their mean")
    st.dataframe(volatility_stress(r.returns, (1.0, 1.5, 2.0, 3.0), level), hide_index=True, width="stretch")
with b:
    st.markdown("**Higher transaction costs** — full backtest re-run")
    if st.button("Run cost stress"):
        try:
            mults = tuple(float(x) for x in cost_m.split(","))
        except ValueError:
            st.error("Cost multipliers must be numbers separated by commas.")
            st.stop()
        state.put("cost_stress", cost_stress(p, pipe.signals, r.config, *pipe.eval_window, mults))
    if (cs := state.get("cost_stress")) is not None:
        st.dataframe(cs, hide_index=True, width="stretch")

section("Volatility regimes")
if BENCHMARK in p:
    a, b = st.columns([1, 3])
    rw = a.number_input("Regime vol window", 10, 252, 63, 21)
    reg = volatility_regime(p[BENCHMARK], int(rw))
    perf = regime_performance(r.returns, reg)
    b.caption(f"Regime = {BENCHMARK} {rw}-day realised vol above / below its expanding median (past data only); "
              f"each day's return is matched to the regime known at the previous close. "
              f"Unclassified days (insufficient history): {perf.attrs['unclassified_days']}.")
    st.dataframe(perf, hide_index=True, width="stretch",
                 column_config={k: st.column_config.NumberColumn(format="%.4f") for k in
                                ("ann_return", "ann_vol", "sharpe", "hit_rate", "total_contribution")})
    rr = reg.shift(1).reindex(r.returns.index)
    fr = go.Figure(go.Scatter(x=r.equity.index, y=r.equity, line=dict(color=C["accent"], width=1.3), name="equity"))
    for _, grp in rr[rr == "high-vol"].groupby((rr != "high-vol").cumsum()):
        fr.add_vrect(x0=grp.index[0], x1=grp.index[-1], fillcolor=C["neg"], opacity=0.08, line_width=0)
    plot(fr, height=260, title="Equity with high-volatility regimes shaded", legend=False)
else:
    st.caption(f"{BENCHMARK} not in loaded data; regime analysis unavailable.")

with st.expander("How a cointegrated pair still loses money"):
    st.markdown(
        "- **Breakdown:** cointegration is estimated on past data; mergers, regulation or business-model change can "
        "make the spread non-stationary, so the 'mean' it should revert to no longer exists.\n"
        "- **Divergence before convergence:** even a truly mean-reverting spread can widen far beyond entry; with "
        "finite capital and stops, losses are realised before reversion.\n"
        "- **Hedge-ratio drift:** a stale β leaves residual directional exposure to one leg.\n"
        "- **Slow reversion:** a long half-life ties up capital while borrow and opportunity costs accrue.\n"
        "- **Costs:** small per-trade edges vanish after fees, slippage and borrow — compare gross vs net P&L.\n"
        "- **Selection bias:** among many tested pairs some look cointegrated by chance (hence FDR control).")
