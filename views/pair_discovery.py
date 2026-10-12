import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from quantpair.analytics.market import log_returns
from quantpair.config import DiscoveryConfig
from quantpair.research.spread_model import compute_spread, rolling_hedge_ratio, rolling_zscore
from ui import state
from ui.components import C, empty, header, kpis, note, num, plot, section, style

p = state.require_data()
c = state.cfg()
header("Pair Discovery", "Engle–Granger cointegration on every unordered pair, Benjamini–Hochberg FDR control, "
       "transparent ranking. Uses the discovery window only.", [state.data_badge()])
sp = state.splits()
dc = c.discovery

with st.form("disc_form"):
    uni = st.multiselect("Universe", list(p.columns), default=state.universe_cols())
    a, b, cc, d = st.columns(4)
    mode = a.radio("Discovery window", ["Training split", "Custom"], horizontal=True)
    start = b.date_input("Custom start", sp["train"][0].date(), min_value=p.index[0].date(), max_value=p.index[-1].date())
    end = cc.date_input("Custom end", sp["train"][1].date(), min_value=p.index[0].date(), max_value=p.index[-1].date())
    min_obs = d.number_input("Min aligned observations", 30, 5000, dc.min_obs, 21)
    a, b, cc, d = st.columns(4)
    alpha = a.number_input("Raw significance α", 0.001, 0.5, dc.coint_alpha, 0.005, format="%.3f")
    q = b.number_input("FDR level q", 0.001, 0.5, dc.fdr_q, 0.01, format="%.3f")
    max_miss = cc.number_input("Max missing fraction", 0.0, 0.5, dc.max_missing_frac, 0.01)
    stab = d.number_input("Stability window (sessions)", 20, 1000, dc.stability_window, 21)
    a, b, cc, d = st.columns(4)
    hl_min = a.number_input("Min half-life (days)", 0.0, 100.0, dc.min_half_life, 0.5)
    hl_max = b.number_input("Max half-life (days)", 1.0, 500.0, dc.max_half_life, 5.0)
    intercept = cc.toggle("Include intercept (y = α + βx)", dc.use_intercept)
    w = d.text_input("Rank weights evidence/stability/history", ", ".join(str(x) for x in dc.rank_weights))
    trend = st.radio("Deterministic terms in the cointegrating regression", ["c", "ct"],
                     index=["c", "ct"].index(dc.coint_trend), horizontal=True,
                     format_func=lambda v: "constant (y = α + βx)" if v == "c"
                     else "constant + linear trend (y = α + γt + βx)",
                     help="Use the trend for near-identical assets whose prices drift apart deterministically "
                          "(e.g. different expense ratios). The fitted trend is extrapolated when trading.")
    go_ = st.form_submit_button("Run pair discovery", type="primary")

if go_:
    try:
        weights = tuple(float(x) for x in w.split(","))
        assert len(weights) == 3
        new = DiscoveryConfig(int(min_obs), float(max_miss), float(alpha), float(q), intercept, trend,
                              int(stab), float(hl_min), float(hl_max), weights)
    except (ValueError, AssertionError) as exc:
        st.error(f"Invalid settings: {exc or 'rank weights need three numbers'}")
        st.stop()
    if len(uni) < 2:
        st.error("Select at least two instruments.")
        st.stop()
    c.discovery, c.universe = new, list(uni) + [t for t in c.universe if t not in p.columns]
    c.strategy.use_trend = trend == "ct"
    win = sp["train"] if mode == "Training split" else (pd.Timestamp(start), pd.Timestamp(end))
    if pd.Timestamp(win[1]) > sp["train"][1]:
        st.warning("This window extends past the training split: validation/test backtests would then be "
                   "contaminated by in-sample selection.")
    bar = st.progress(0.0, "Testing pairs…")
    state.run_discovery(state.universe_cols(), new, win, progress=lambda f, m: bar.progress(f, f"Testing {m}"))
    bar.empty()

res = state.discovery()
if res is None:
    empty("Discovery has not been run", "Choose a universe and window above, then run pair discovery.")
    st.stop()

section("Discovery results")
t = res.table
tested = t[t.get("status", pd.Series(dtype=str)) == "tested"] if "status" in t else t.iloc[0:0]
kpis([("Window", f"{res.window[0]} → {res.window[1]}"), ("Eligible tickers", len(res.tickers)),
      ("Candidate pairs", res.n_candidates), ("Tested", res.n_tested),
      ("Raw p < α", int(t["raw_pass"].sum()) if "raw_pass" in t else 0, "", "not a discovery"),
      ("BH-significant", res.n_significant, "acc"), ("Eligible", res.n_eligible, "acc", "BH + half-life band")])
if res.excluded:
    st.caption("Excluded tickers: " + "; ".join(f"{k} ({v})" for k, v in res.excluded.items()))
note(f"With {res.n_tested} tests at α = {c.discovery.coint_alpha}, roughly "
     f"{res.n_tested * c.discovery.coint_alpha:.1f} pairs would pass by chance alone — which is why the "
     "BH-adjusted q-value, not the raw p-value, decides significance.")

section("Candidate pairs", "sortable · filterable")
a, b, cc = st.columns([2, 2, 1])
search = a.text_input("Search pairs", placeholder="e.g. XLF or KO")
show = b.radio("Show", ["All tested", "BH-significant", "Eligible"], horizontal=True)
view = tested
if search:
    view = view[view["pair"].str.contains(search.upper(), regex=False)]
if show == "BH-significant":
    view = view[view["fdr_pass"]]
elif show == "Eligible":
    view = view[view["eligible"]]
cols = ["pair", "n_obs", "return_corr", "price_corr", "beta", "intercept", "eg_stat", "eg_pvalue", "q_value",
        "adf_pvalue_naive", "half_life", "beta_cv", "evidence", "stability", "history", "score", "fdr_pass",
        "hl_ok", "eligible"]
st.dataframe(view[[k for k in cols if k in view]], hide_index=True, width="stretch", height=360,
             column_config={k: st.column_config.NumberColumn(format="%.4f") for k in
                            ("eg_pvalue", "q_value", "adf_pvalue_naive")}
             | {k: st.column_config.NumberColumn(format="%.3f") for k in
                ("return_corr", "price_corr", "beta", "beta_cv", "evidence", "stability", "history", "score")}
             | {"half_life": st.column_config.NumberColumn("half_life (d)", format="%.1f")})
note("score = w₁·rank(−log₁₀ q) + w₂·rank(1/(1+CV of rolling β)) + w₃·rank(history). ADF p is the naive "
     "residual test (too lenient); the Engle–Granger p-value is the cointegration test.")

if tested.empty:
    st.stop()
section("Pair diagnostics")
pair = st.selectbox("Pair", tested["pair"].tolist())
r = tested.set_index("pair").loc[pair]
win = p.loc[res.window[0]:res.window[1], [r.y, r.x]].dropna()
spread = compute_spread(win[r.y], win[r.x], r.beta, r.intercept, r.get("trend", 0.0))
z = rolling_zscore(spread, c.strategy.lookback)
rb = rolling_hedge_ratio(win[r.y], win[r.x], c.discovery.stability_window, c.discovery.use_intercept)["beta"]
kpis([("Hedge ratio β", num(r.beta, 3)), ("Intercept α", num(r.intercept, 2)),
      ("EG p-value", num(r.eg_pvalue, 4), ""), ("BH q-value", num(r.q_value, 4), "acc" if r.fdr_pass else "neg"),
      ("Half-life", "invalid" if pd.isna(r.half_life) else f"{r.half_life:.1f} d", "", r.half_life_note),
      ("Rolling-β CV", num(r.beta_cv, 3)), ("Samples", int(r.n_obs), "", f"{r.start} → {r.end}")])
warn = []
if not r.fdr_pass:
    warn.append("Not significant after FDR correction — treat any pattern as likely noise.")
if not r.hl_ok:
    warn.append(f"Half-life outside [{c.discovery.min_half_life}, {c.discovery.max_half_life}] days or unreliable "
                f"({r.half_life_note}).")
if r.beta_cv > 0.25:
    warn.append(f"Hedge ratio unstable over rolling {c.discovery.stability_window}-day windows (CV {r.beta_cv:.2f}).")
if r.beta_sign_flip > 0:
    warn.append(f"Rolling β changes sign in {r.beta_sign_flip:.0%} of windows.")
if r.price_corr > 0.9 and not r.fdr_pass:
    warn.append("High price correlation without cointegration: trending series correlate spuriously.")
for x in warn:
    st.warning(x)

fig = make_subplots(rows=2, cols=2, shared_xaxes=True, vertical_spacing=0.12, horizontal_spacing=0.07,
                    subplot_titles=("Normalised prices (start = 100)", "Spread  y − α − γt − βx" if c.discovery.coint_trend == "ct" else "Spread  y − α − βx", "Rolling z-score "
                                    f"({c.strategy.lookback}d)", f"Rolling β ({c.discovery.stability_window}d) vs full-window β"))
for k, s in enumerate([r.y, r.x]):
    fig.add_trace(go.Scatter(x=win.index, y=100 * win[s] / win[s].iloc[0], name=s,
                             line=dict(width=1.4, color=C["series"][k])), 1, 1)
fig.add_trace(go.Scatter(x=spread.index, y=spread, name="spread", line=dict(width=1.1, color=C["accent"]),
                         showlegend=False), 1, 2)
for k in (-2, 0, 2):
    fig.add_hline(y=spread.mean() + k * spread.std(), line=dict(color=C["muted"], dash="dot" if k else "solid", width=1),
                  row=1, col=2)
fig.add_trace(go.Scatter(x=z.index, y=z, name="z", line=dict(width=1.1, color=C["series"][2]), showlegend=False), 2, 1)
for k in (-c.strategy.entry_z, c.strategy.entry_z):
    fig.add_hline(y=k, line=dict(color=C["neg"], dash="dot", width=1), row=2, col=1)
fig.add_trace(go.Scatter(x=rb.index, y=rb, name="rolling β", line=dict(width=1.2, color=C["series"][1]),
                         showlegend=False), 2, 2)
fig.add_hline(y=r.beta, line=dict(color=C["muted"], dash="dash", width=1), row=2, col=2)
fig.update_annotations(font=dict(size=12, color=C["text"]))
plot(fig, height=560)

with st.expander("Return correlation matrix (discovery window)"):
    corr = log_returns(p.loc[res.window[0]:res.window[1], res.tickers]).corr()
    hm = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1,
                              colorscale=[[0, C["neg"]], [0.5, C["panel2"]], [1, C["accent"]]],
                              text=np.round(corr.values, 2), texttemplate="%{text}", textfont=dict(size=9)))
    st.plotly_chart(style(hm, height=520, legend=False), width="stretch")
    note("Correlation measures co-movement of returns; it does not establish cointegration.")
