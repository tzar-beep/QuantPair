import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from quantpair.config import DEFAULT_UNIVERSE, UNIVERSE_PRESETS, ExperimentConfig
from quantpair.data.market_data import save_snapshot, snapshot_info
from ui import state
from ui.components import empty, header, kpis, plot, section

c = state.cfg()
header("Settings & Data", "Data provider, universe, date range, cache and data-quality diagnostics.",
       [state.data_badge()])

section("Provider status")
try:
    import yfinance
    yf_ver = yfinance.__version__
except Exception as exc:  # pragma: no cover
    yf_ver = f"unavailable ({exc})"
snap = snapshot_info()
d = state.data()
kpis([("Provider", "Yahoo Finance"), ("yfinance", yf_ver), ("Network", "required for live data"),
      ("Last load", d["meta"].retrieved_at if d else "—", "", d["meta"].source if d else ""),
      ("Snapshot", snap["retrieved_at"][:16] if snap else "none")])
if err := state.get("data_error"):
    st.error(err)

section("Universe & dates")
pa, pb = st.columns([3, 1])
preset = pa.selectbox("Universe preset", ["(custom)"] + list(UNIVERSE_PRESETS),
                      help="Same-business peers are more plausible cointegration candidates. The positive-control "
                           "set holds near-identical assets that the tests should flag.")
if pb.button("Apply preset", disabled=preset == "(custom)"):
    c.universe = list(UNIVERSE_PRESETS[preset])
    st.rerun()
with st.form("data_form"):
    uni = st.text_area("Tickers (comma separated)", ", ".join(c.universe), height=80)
    a, b, cc = st.columns(3)
    start = a.date_input("Start", dt.date.fromisoformat(c.start), min_value=dt.date(1990, 1, 1))
    use_end = b.toggle("Fixed end date", c.end is not None)
    end = cc.date_input("End (exclusive)", dt.date.fromisoformat(c.end) if c.end else dt.date.today())
    x = st.columns(3)
    fetch = x[0].form_submit_button("Download / refresh data", type="primary")
    snap_btn = x[1].form_submit_button("Load saved snapshot", disabled=snap is None)
    reset = x[2].form_submit_button("Reset universe to default")
if fetch or snap_btn or reset:
    tickers = DEFAULT_UNIVERSE if reset else [t.strip().upper() for t in uni.split(",") if t.strip()]
    if len(tickers) < 2:
        st.error("Enter at least two tickers.")
        st.stop()
    c.universe, c.start, c.end = list(dict.fromkeys(tickers)), str(start), str(end) if use_end else None
    if not reset:
        with st.spinner("Loading prices…"):
            ok = state.load_data("snapshot" if snap_btn else "live")
        if ok:
            st.success("Data loaded and validated. Downstream results were cleared.")
            st.rerun()
        else:
            st.error(state.get("data_error"))

a, b, _ = st.columns([1, 1, 2])
if a.button("Save snapshot of loaded data", disabled=d is None or d["meta"].is_snapshot):
    path = save_snapshot(d["meta"])
    st.success(f"Saved real prices to {path.name} for offline reuse (gitignored).")
if b.button("Clear data cache"):
    st.cache_data.clear()
    st.success("Cached downloads and discovery results cleared; the next load re-downloads.")

section("Default research settings")
with st.form("defaults_form"):
    a, b, cc, dd = st.columns(4)
    tf = a.number_input("Train fraction", 0.3, 0.8, c.train_frac, 0.05)
    vf = b.number_input("Validation fraction", 0.05, 0.4, c.val_frac, 0.05)
    rf = cc.number_input("Risk-free rate", 0.0, 0.2, c.backtest.risk_free_rate, 0.005, format="%.3f")
    mo = dd.number_input("Min observations", 30, 5000, c.discovery.min_obs, 21)
    x = st.columns(2)
    save = x[0].form_submit_button("Save defaults")
    reset_all = x[1].form_submit_button("Reset all settings")
if save:
    if tf + vf >= 0.95:
        st.error("Train + validation must leave room for a test period.")
    else:
        c.train_frac, c.val_frac = tf, vf
        c.backtest.risk_free_rate, c.discovery.min_obs = rf, int(mo)
        st.success("Saved.")
if reset_all:
    state.put("cfg", ExperimentConfig())
    state.clear_results()
    st.rerun()

section("Data quality")
if d is None:
    empty("No data loaded", "Download data above.")
    st.stop()
p, rep = d["prices"], d["report"]
kpis([("Range", f"{rep.start} → {rep.end}"), ("Sessions", rep.n_dates), ("Tickers", p.shape[1]),
      ("All-present dates", rep.common_dates), ("Errors", rep.n_errors, "neg" if rep.n_errors else ""),
      ("Warnings", rep.n_warnings)])
if d["meta"].failed:
    st.error(f"No data returned for: {', '.join(d['meta'].failed)}")
st.dataframe(rep.summary, hide_index=True, width="stretch",
             column_config={"missing_frac": st.column_config.NumberColumn(format="%.4f")})
iss = rep.issues_frame()
if not iss.empty:
    st.dataframe(iss, hide_index=True, width="stretch")
sel = st.multiselect("Inspect prices", list(p.columns), list(p.columns)[:4])
if sel:
    plot(go.Figure([go.Scatter(x=p.index, y=p[t], name=t, line=dict(width=1.1)) for t in sel]),
         height=320, title="Adjusted close (gaps = missing sessions, not interpolated)")
