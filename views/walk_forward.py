from dataclasses import replace

import plotly.graph_objects as go
import streamlit as st

from quantpair.config import BENCHMARK, WalkForwardConfig
from quantpair.validation.robustness import buy_and_hold, parameter_grid, run_grid
from quantpair.validation.walk_forward import chronological_split, split_evaluation, walk_forward
from ui import runs, state
from ui.components import C, area, empty, header, kpis, note, num, pct, plot, section, style, tone, warnings_box

p = state.require_data()
c = state.cfg()
header("Walk-Forward Validation", "Chronological splits, rolling re-discovery out of sample, parameter "
       "robustness and cost sensitivity.", [state.data_badge()])

section("Chronological split")
a, b, _ = st.columns([1, 1, 2])
tf = a.slider("Train fraction", 0.3, 0.8, c.train_frac, 0.05)
vf = b.slider("Validation fraction", 0.05, 0.4, c.val_frac, 0.05)
try:
    chronological_split(p.index, tf, vf)
    c.train_frac, c.val_frac = tf, vf
except ValueError as exc:
    st.error(str(exc))
sp = state.splits()
kpis([(k.title() + (" (final test)" if k == "test" else ""), f"{v[0].date()} → {v[1].date()}", "acc" if k == "test" else "",
       f"{len(p.loc[v[0]:v[1]])} sessions") for k, v in sp.items()])

tab1, tab2, tab3, tab4 = st.tabs(["In-sample vs validation vs test", "Walk-forward", "Robustness", "ML reversion filter"])
with tab1:
    note("Discovery on train → evaluate on train (in-sample) and validation. The final test refits on "
         "train+validation and should be viewed once, after parameters are frozen.")
    inc = st.checkbox("Include final test period (one-time evaluation)")
    sel = st.radio("Selection", ["fdr", "raw"], horizontal=True, key="split_sel",
                   format_func=lambda x: "FDR-significant" if x == "fdr" else "Raw p (exploratory)")
    if st.button("Run split evaluation", type="primary"):
        with st.spinner("Running segments…"):
            state.put("split_table", split_evaluation(p, state.universe_cols(), sp, c.discovery, c.strategy,
                                                      c.backtest, c.walkforward.top_k, sel, inc))
    if (t := state.get("split_table")) is not None:
        st.dataframe(t, hide_index=True, width="stretch",
                     column_config={k: st.column_config.NumberColumn(format="%.4f") for k in
                                    ("total_return", "cagr", "sharpe", "max_drawdown")})

with tab2:
    w = c.walkforward
    a, b, cc, d, e = st.columns(5)
    trd = a.number_input("Train window (sessions)", 60, 3000, w.train_days, 21)
    ted = b.number_input("Test window (sessions)", 21, 1000, w.test_days, 21)
    exp_ = cc.toggle("Expanding train window", w.expanding)
    k = d.number_input("Max pairs per window", 1, 50, w.top_k)
    sel = e.radio("Selection", ["fdr", "raw"], horizontal=True, index=["fdr", "raw"].index(w.selection),
                  format_func=lambda x: "FDR" if x == "fdr" else "Raw p")
    note(f"Each window: discover pairs on the previous {trd} sessions, trade the next {ted}, liquidate, roll forward. "
         f"Uses the experiment's strategy and cost settings (entry {c.strategy.entry_z}, exit {c.strategy.exit_z}, "
         f"fees+slippage {c.backtest.costs.fee_bps + c.backtest.costs.slippage_bps} bps).")
    if st.button("Run walk-forward", type="primary"):
        c.walkforward = WalkForwardConfig(int(trd), int(ted), exp_, int(k), sel)
        bar = st.progress(0.0, "Starting…")
        try:
            res = walk_forward(p, state.universe_cols(), c.discovery, c.strategy, c.backtest, c.walkforward,
                               final_test_start=sp["test"][0], progress=lambda f, m: bar.progress(f, m))
            state.put("wf", {"result": res, "capital": c.backtest.initial_capital, "config": c.walkforward})
        except ValueError as exc:
            st.error(str(exc))
        bar.empty()
    wf = state.get("wf")
    if wf is None:
        empty("Walk-forward not run", "Configure windows above and run.")
    else:
        res = wf["result"]
        wd = res.windows
        traded = wd[wd["n_trades"] > 0]
        tot = res.equity.iloc[-1] / wf["capital"] - 1
        from quantpair.backtesting.metrics import sharpe_ratio
        sh = sharpe_ratio(res.returns, c.backtest.risk_free_rate)
        kpis([("Windows", len(wd)), ("Windows with pairs", int((wd["pairs"] != "—").sum())),
              ("OOS return", pct(tot), tone(tot)), ("OOS Sharpe", num(sh), tone(sh)),
              ("OOS trades", int(wd["n_trades"].sum())),
              ("Profitable windows", f"{(traded['return'] > 0).sum()}/{len(traded)}" if len(traded) else "—"),
              ("Window return σ", pct(traded["return"].std()) if len(traded) > 1 else "—")])
        k0 = wf["capital"]
        fig = go.Figure(area(res.equity.index, (res.equity / k0 - 1) * 100, "Walk-forward OOS", C["accent"],
                             min(0, (res.equity / k0 - 1).min() * 100)))
        bh = buy_and_hold(p, BENCHMARK, res.equity.index[0], res.equity.index[-1], wf["capital"])
        if bh is not None:
            fig.update_layout(yaxis=dict(title="strategy %"), yaxis2=dict(title="benchmark % (right)", overlaying="y", side="right", showgrid=False, zeroline=False))
            fig.add_trace(go.Scatter(x=bh.index, y=(bh / k0 - 1) * 100, name=bh.name, yaxis="y2", line=dict(color=C["muted"], width=1)))
        fig.add_vrect(x0=sp["test"][0], x1=sp["test"][1], fillcolor=C["accent"], opacity=0.06, line_width=0,
                      annotation_text="final test period", annotation_position="top left")
        plot(fig, height=360, title="Stitched out-of-sample cumulative return (%)")
        bars = go.Figure(go.Bar(x=wd["window"], y=wd["return"] * 100,
                                marker_color=[C["pos"] if v > 0 else C["neg"] if v < 0 else C["muted"] for v in wd["return"]]))
        plot(bars, height=240, title="Return by window (%)", legend=False)
        st.dataframe(wd, hide_index=True, width="stretch",
                     column_config={"return": st.column_config.NumberColumn(format="%.4f"),
                                    "sharpe": st.column_config.NumberColumn(format="%.2f"),
                                    "max_drawdown": st.column_config.NumberColumn(format="%.4f"),
                                    "start_equity": st.column_config.NumberColumn(format="%.0f"),
                                    "costs": st.column_config.NumberColumn(format="%.0f")})
        warn = []
        if len(traded) < 3:
            warn.append(f"Only {len(traded)} windows traded at all - out-of-sample evidence is thin.")
        if int(wd["n_trades"].sum()) < 20:
            warn.append("Fewer than 20 out-of-sample trades in total.")
        if len(traded) and (traded["return"] > 0).mean() < 0.5:
            warn.append("Most traded windows lost money.")
        ps = [set(x.split(", ")) for x in wd["pairs"] if x != "—"]
        if len(ps) > 1:
            turnover = sum(len(a ^ b) / max(len(a | b), 1) for a, b in zip(ps, ps[1:])) / (len(ps) - 1)
            if turnover > 0.5:
                warn.append(f"Selected pairs change a lot between windows (avg Jaccard distance {turnover:.2f}): "
                            "relationships are unstable.")
        warnings_box(warn or ["No automatic red flags — still not proof of robustness."],
                     "warning" if warn else "info")

with tab3:
    note("Variants are evaluated on the validation segment with pairs selected on train. The final test is never "
         "used here. Every variant counts toward selection bias — the best of many is optimistic.")
    a, b, cc, d = st.columns(4)
    ent = a.multiselect("Entry z", [1.0, 1.5, 2.0, 2.5, 3.0], [1.5, 2.0, 2.5])
    ex = b.multiselect("Exit z", [0.0, 0.25, 0.5, 1.0], [0.0, 0.5])
    lb = cc.multiselect("Lookback", [20, 40, 60, 90, 120], [40, 60])
    cm = d.multiselect("Cost multiplier", [0.5, 1.0, 2.0, 3.0], [1.0, 2.0])
    sel = st.radio("Pair selection", ["fdr", "raw"], horizontal=True, key="rob_sel",
                   format_func=lambda x: "FDR-significant" if x == "fdr" else "Raw p (exploratory)")
    if st.button("Run robustness grid", type="primary"):
        grid = parameter_grid(c.strategy, ent, ex, lb)
        if not grid or not cm:
            st.error("No valid combinations (exit must be below entry, entry below stop).")
        else:
            disc = runs.ensure_discovery(sp["train"])
            from quantpair.research.pair_selection import select_pairs
            pairs = select_pairs(disc.table, c.walkforward.top_k, sel)
            if pairs.empty:
                st.warning("No pairs pass the selection rule on the training split; nothing to vary.")
            else:
                bar = st.progress(0.0)
                out = run_grid(p, pairs, sp["train"], sp["validation"], grid, replace(c.backtest),
                               tuple(cm), progress=lambda f, m: bar.progress(f, m))
                bar.empty()
                state.put("grid", {"table": out, "pairs": list(pairs["pair"])})
    g = state.get("grid")
    if g is not None:
        out = g["table"]
        st.caption(f"{len(out)} variants tested on pairs: {', '.join(g['pairs'])}")
        sh = out["sharpe"].dropna()
        kpis([("Variants", len(out)), ("Positive Sharpe", f"{(sh > 0).sum()}/{len(sh)}"),
              ("Median Sharpe", num(sh.median() if len(sh) else None)), ("Best Sharpe", num(sh.max() if len(sh) else None),
                                                                           "", "optimistic: best of many"),
              ("Worst Sharpe", num(sh.min() if len(sh) else None))])
        base = out[out["cost_mult"] == out["cost_mult"].min()]
        piv = base.pivot_table(index="entry_z", columns="exit_z", values="sharpe", aggfunc="mean")
        if piv.size:
            hm = go.Figure(go.Heatmap(z=piv.values, x=[str(x) for x in piv.columns], y=[str(y) for y in piv.index],
                                      colorscale=[[0, C["neg"]], [0.5, C["panel2"]], [1, C["pos"]]], zmid=0,
                                      text=piv.round(2).values, texttemplate="%{text}"))
            hm.update_xaxes(title="exit z")
            hm.update_yaxes(title="entry z")
            st.plotly_chart(style(hm, height=300, title="Validation Sharpe (mean over lookbacks, lowest cost)",
                                  legend=False), width="stretch")
        cs = out.groupby("cost_mult")[["total_return", "sharpe"]].median().reset_index()
        st.markdown("**Cost sensitivity (median across variants)**")
        st.dataframe(cs, hide_index=True, width="stretch")
        st.dataframe(out, hide_index=True, width="stretch", height=300)
        if len(sh) > 1 and sh.max() > 0 > sh.min():
            st.warning("Sharpe changes sign across variants - results are parameter-sensitive.")

with tab4:
    from quantpair.research.ml_reversion import MLConfig, run_ml_study
    note("Optional research extension. A gradient-boosted tree classifier predicts whether a stretched spread "
         "(|z| ≥ min) reverts inside the exit band within H sessions. Trained on the training split with purged "
         "labels, evaluated on validation, compared with a logistic baseline on |z| alone and with the unfiltered "
         "statistical strategy. Hyper-parameters are fixed (no tuning on validation).")
    a, b, cc, d = st.columns(4)
    H = a.number_input("Label horizon H (sessions)", 2, 60, 10)
    mz = b.number_input("Min |z| for a sample", 0.0, 4.0, 1.0, 0.25)
    th = cc.number_input("Entry probability threshold", 0.05, 0.95, 0.5, 0.05)
    npairs = d.number_input("Pairs (top by score)", 1, 20, 5)
    src = st.radio("Pair source", ["eligible", "top score"], horizontal=True,
                   format_func=lambda x: "FDR-eligible only" if x == "eligible" else "Top discovery score (exploratory)")
    if st.button("Train & evaluate", type="primary"):
        disc = runs.ensure_discovery(sp["train"])
        tbl = disc.table[disc.table.get("status", "") == "tested"] if "status" in disc.table else disc.table.iloc[0:0]
        pairs = (tbl[tbl["eligible"]] if src == "eligible" else tbl).sort_values("score", ascending=False).head(int(npairs))
        if pairs.empty:
            st.warning("No pairs available under this source; try 'Top discovery score' or another universe.")
        else:
            with st.spinner("Building features, training, evaluating…"):
                try:
                    mres = run_ml_study(p, pairs, c.strategy, c.backtest, sp["train"], sp["validation"],
                                        p[BENCHMARK] if BENCHMARK in p else None,
                                        MLConfig(int(H), float(mz), float(th)))
                    state.put("ml", {"result": mres, "pairs": list(pairs["pair"]), "source": src})
                except ValueError as exc:
                    st.error(str(exc))
    ml = state.get("ml")
    if ml is not None:
        mr = ml["result"]
        sm = mr.summary
        st.caption(f"Pairs: {', '.join(ml['pairs'])}" + (" · exploratory selection" if ml["source"] != "eligible" else ""))
        kpis([("Train rows", sm["n_train"]), ("Eval rows", sm["n_eval"]),
              ("Eval base rate", pct(sm.get("eval_base_rate"), 1)),
              ("AUC model", num(sm.get("auc_model"), 3), "acc"), ("AUC |z| baseline", num(sm.get("auc_baseline_absz"), 3)),
              ("Brier model", num(sm.get("brier_model"), 4)), ("Brier base rate", num(sm.get("brier_base_rate"), 4))])
        if sm.get("note"):
            st.warning(sm["note"])
        verdict = ("The model does not beat the |z| baseline out of sample."
                   if (sm.get("auc_model") or 0) <= (sm.get("auc_baseline_absz") or 0)
                   else "The model ranks reversions better than the |z| baseline on validation (AUC); check whether "
                        "that survives costs in the strategy comparison below.")
        st.info(verdict + " An ML model that fails out of sample is not an improvement.")
        a, b = st.columns([2, 3])
        a.markdown("**Permutation importance (validation AUC drop)**")
        a.dataframe(mr.importance, hide_index=True, width="stretch")
        b.markdown("**Strategy comparison on validation**")
        b.dataframe(mr.comparison, hide_index=True, width="stretch",
                    column_config={k: st.column_config.NumberColumn(format="%.4f") for k in
                                   ("total_return", "sharpe", "max_drawdown", "win_rate")})
