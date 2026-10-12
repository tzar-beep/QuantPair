import pandas as pd
import streamlit as st

from quantpair.config import ExperimentConfig
from quantpair.reporting.exports import csv_bytes, json_bytes, load_experiments, make_experiment, save_experiment
from quantpair.reporting.research_report import build_report
from quantpair.risk.metrics import historical_var_es
from quantpair.validation.robustness import relationship_stability_warning, research_warnings
from ui import runs, state
from ui.components import empty, header, section

p = state.require_data()
c = state.cfg()
header("Research Reports", "Export reproducible results: configuration, data, methodology, metrics, validation, "
       "limitations.", [state.data_badge()])

d = state.data()
meta, rep = d["meta"], d["report"]
data_info = {"source": "snapshot of Yahoo Finance prices" if meta.is_snapshot else "Yahoo Finance (yfinance)",
             "retrieved_at": meta.retrieved_at, "price_field": "adjusted close (auto_adjust=True)",
             "range": f"{rep.start} → {rep.end}", "sessions": rep.n_dates, "tickers": ", ".join(p.columns),
             "failed_tickers": ", ".join(meta.failed) or "none",
             "quality": f"{rep.n_errors} errors, {rep.n_warnings} warnings"}
disc, bt, wf = state.discovery(), state.get("backtest"), state.get("wf")
split_t, grid = state.get("split_table"), state.get("grid")
metrics = risk = selected = None
warns: list[str] = []
if bt is not None:
    r = bt["pipe"].backtest
    metrics = {"segment": bt["segment"], **r.metrics}
    risk = historical_var_es(r.returns, 0.95)
    selected = bt["pipe"].selected
    warns = research_warnings(r, grid["table"] if grid else None) + relationship_stability_warning(selected)
conclusion = runs.conclusion_text()

section("Contents")
st.dataframe(pd.DataFrame({"section": ["Discovery", "Backtest", "Split evaluation", "Walk-forward", "Robustness grid"],
                           "status": ["✓" if x is not None else "not run" for x in (disc, bt, split_t, wf, grid)]}),
             hide_index=True)
st.info(conclusion)

report = build_report(c.to_dict(), data_info, disc.table if disc else None, selected, metrics, risk, split_t,
                      wf["result"].windows if wf else None, warns, conclusion)
summary = {"config": c.to_dict(), "data": data_info, "metrics": metrics, "risk": risk,
           "selected_pairs": list(selected["pair"]) if selected is not None else [],
           "discovery_window": disc.window if disc else None,
           "walk_forward": wf["result"].windows.to_dict("records") if wf else None, "conclusion": conclusion}

section("Downloads")
a, b, cc = st.columns(3)
a.download_button("Research report (Markdown)", report.encode(), "quantpair_report.md", "text/markdown", type="primary")
b.download_button("Configuration + summary (JSON)", json_bytes(summary), "quantpair_summary.json", "application/json")
cc.download_button("Configuration only (JSON)", json_bytes(c.to_dict()), "quantpair_config.json", "application/json")
x = st.columns(5)
if disc:
    x[0].download_button("Discovery table CSV", csv_bytes(disc.table), "discovery.csv", "text/csv")
if bt:
    x[1].download_button("Trades CSV", csv_bytes(bt["pipe"].backtest.trades), "trades.csv", "text/csv")
    eq = pd.DataFrame({"equity": r.equity, "gross_equity": r.gross_equity, "returns": r.returns}).join(r.exposure)
    x[2].download_button("Equity & exposure CSV", csv_bytes(eq), "equity.csv", "text/csv")
if wf:
    x[3].download_button("Walk-forward windows CSV", csv_bytes(wf["result"].windows), "walk_forward.csv", "text/csv")
if grid:
    x[4].download_button("Robustness grid CSV", csv_bytes(grid["table"]), "robustness.csv", "text/csv")

with st.expander("Preview report"):
    st.markdown(report)

section("Experiment tracking")
if st.button("Save experiment to log"):
    rec = make_experiment(c.to_dict(), data_info, {"segment": bt["segment"] if bt else None, "metrics": metrics,
                                                    "selected_pairs": summary["selected_pairs"],
                                                    "walk_forward_windows": len(wf["result"].windows) if wf else 0})
    save_experiment(rec)
    st.success(f"Saved experiment {rec['id']} to reports/experiments.jsonl")
hist = load_experiments()
if not hist:
    empty("No saved experiments", "Saved experiments store configuration, data range, metrics and package versions.")
else:
    st.dataframe(pd.DataFrame([{"id": h["id"], "timestamp": h["timestamp"], "range": h["data"].get("range"),
                                "segment": h["results"].get("segment"),
                                "sharpe": (h["results"].get("metrics") or {}).get("sharpe"),
                                "total_return": (h["results"].get("metrics") or {}).get("total_return"),
                                "pairs": ", ".join(h["results"].get("selected_pairs") or [])} for h in hist[::-1]]),
                 hide_index=True, width="stretch")
    pick = st.selectbox("Reproduce experiment", [h["id"] for h in hist[::-1]])
    if st.button("Load its configuration"):
        rec = next(h for h in hist if h["id"] == pick)
        state.put("cfg", ExperimentConfig.from_dict(rec["config"]))
        state.clear_results()
        st.success("Configuration loaded. Reload data in Settings & Data if the universe or dates changed, then "
                   "re-run discovery and backtests.")
