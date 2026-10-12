import pandas as pd
import streamlit as st

from quantpair.data.market_data import snapshot_info
from quantpair.reporting.exports import load_experiments
from ui import runs, state
from ui.components import empty, header, kpis, money, num, pct, section, tone

c = state.cfg()
header("Research Overview", "Cointegration pairs research: data → discovery → signals → backtest → validation",
       [state.data_badge()])

if state.data() is None:
    empty("No experiment has run yet",
          "Run the first analysis to download adjusted daily closes for the configured universe "
          f"({len(c.universe)} tickers from {c.start}), discover pairs on the training split and "
          "backtest the selected pairs on the validation split.")
    st.write("")
    a, b, _ = st.columns([1, 1, 3])
    ok = False
    if a.button("Run first analysis", type="primary"):
        with st.status("Running first analysis…", expanded=True) as s:
            s.write("Downloading prices from Yahoo Finance…")
            if state.load_data("live"):
                s.write("Testing all pairs on the training split…")
                runs.run_backtest_job("Validation", "fdr", c.walkforward.top_k)
                s.update(label="First analysis complete", state="complete")
                ok = True
            else:
                s.update(label="Data download failed", state="error")
    snap = snapshot_info()
    if snap and b.button(f"Load snapshot ({snap['retrieved_at'][:10]})"):
        ok = state.load_data("snapshot")
    if ok:
        st.rerun()
    if err := state.get("data_error"):
        st.error(f"{err}\n\nCheck your network connection and retry, or load a previously saved snapshot "
                 "of real prices from Settings & Data.")
    st.stop()

d = state.data()
p, rep, meta = d["prices"], d["report"], d["meta"]
disc = state.discovery()
section("Data & discovery")
kpis([("Universe", f"{len(state.universe_cols())} / {len(c.universe)}", "", "loaded / configured"),
      ("Data range", f"{rep.start} → {rep.end}", "", f"{rep.n_dates} sessions"),
      ("Eligible instruments", len(disc.tickers) if disc else "—", "", "in discovery window"),
      ("Pairs tested", disc.n_tested if disc else "—"),
      ("BH-significant", disc.n_significant if disc else "—", "acc", f"FDR q = {c.discovery.fdr_q}"),
      ("Eligible pairs", disc.n_eligible if disc else "—", "acc", "significant + half-life in range"),
      ("Data issues", f"{rep.n_errors} err · {rep.n_warnings} warn", "neg" if rep.n_errors else "")])
if meta.is_snapshot:
    st.warning(f"Using a saved snapshot of real prices retrieved {meta.retrieved_at}, not a fresh download.")
if meta.failed:
    st.error(f"Provider returned no data for: {', '.join(meta.failed)}")

section("Most recent backtest")
bt = state.get("backtest")
if bt is None:
    empty("No backtest yet", "Run one from the Backtesting page.")
else:
    m, pipe = bt["pipe"].backtest.metrics, bt["pipe"]
    st.caption(f"Segment: **{bt['segment']}** · fit {str(pipe.fit_window[0])[:10]} → {str(pipe.fit_window[1])[:10]}"
               f" · eval {str(pipe.eval_window[0])[:10]} → {str(pipe.eval_window[1])[:10]}"
               f" · pairs: {', '.join(pipe.selected['pair']) if len(pipe.selected) else 'none selected'}")
    kpis([("Total return", pct(m["total_return"]), tone(m["total_return"])),
          ("Sharpe", num(m["sharpe"]), tone(m["sharpe"])), ("Max drawdown", pct(m["max_drawdown"]), "neg"),
          ("Trades", m["n_trades"]), ("Net P&L", money(m["net_pnl"]), tone(m["net_pnl"])),
          ("Costs", money(m["total_costs"]))])

section("Validation status")
wf = state.get("wf")
if wf is None:
    empty("Walk-forward not run", "Out-of-sample robustness has not been assessed yet.")
else:
    w = wf["result"].windows
    tot = wf["result"].equity.iloc[-1] / wf["capital"] - 1
    kpis([("Windows", len(w)), ("Windows with trades", int((w["n_trades"] > 0).sum())),
          ("OOS cumulative return", pct(tot), tone(tot)), ("OOS trades", int(w["n_trades"].sum()))])
st.info(runs.conclusion_text())

col1, col2 = st.columns(2)
with col1:
    section("Experiment configuration")
    s, b = c.strategy, c.backtest
    st.dataframe(pd.DataFrame({"setting": ["Split train/val/test", "Coint α / FDR q", "Lookback", "Entry / exit / stop z",
                                           "Max hold", "Hedge", "Fees / slippage / borrow", "Alloc per pair / max gross"],
                               "value": [f"{c.train_frac:.0%} / {c.val_frac:.0%} / {1 - c.train_frac - c.val_frac:.0%}",
                                         f"{c.discovery.coint_alpha} / {c.discovery.fdr_q}", s.lookback,
                                         f"{s.entry_z} / {s.exit_z} / {s.stop_z}", s.max_hold, s.hedge_method,
                                         f"{b.costs.fee_bps} / {b.costs.slippage_bps} bps / {b.costs.borrow_bps_annual} bps/yr",
                                         f"{b.alloc_per_pair:.0%} / {b.max_gross_leverage:.1f}x"]}).astype(str),
                 hide_index=True, width="stretch")
with col2:
    section("Data-quality warnings")
    iss = rep.issues_frame()
    if iss.empty:
        st.success("No data-quality issues detected.")
    else:
        st.dataframe(iss, hide_index=True, width="stretch", height=280)

section("Recent experiments")
hist = load_experiments()[-5:][::-1]
if not hist:
    empty("No saved experiments", "Save one from Research Reports to build a reproducible history.")
else:
    st.dataframe(pd.DataFrame([{"id": h["id"], "timestamp": h["timestamp"], "segment": h["results"].get("segment"),
                                "sharpe": h["results"].get("metrics", {}).get("sharpe"),
                                "total_return": h["results"].get("metrics", {}).get("total_return")} for h in hist]),
                 hide_index=True, width="stretch")
