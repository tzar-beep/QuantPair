"""QuantPair - Streamlit entry point.  Run:  streamlit run app.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st  # noqa: E402

from ui import state  # noqa: E402
from ui.components import inject_css, status_strip  # noqa: E402

st.set_page_config(page_title="QuantPair · Statistical Arbitrage Research", page_icon=str(ROOT / "ui" / "mark.svg"),
                   layout="wide", initial_sidebar_state="collapsed")
st.logo(str(ROOT / "ui" / "logo.svg"), size="large")
inject_css()

V = ROOT / "views"
pages = [
    st.Page(V / "overview.py", title="Overview", default=True),
    st.Page(V / "pair_discovery.py", title="Discovery"),
    st.Page(V / "strategy_lab.py", title="Strategy Lab"),
    st.Page(V / "backtesting.py", title="Backtest"),
    st.Page(V / "risk.py", title="Risk"),
    st.Page(V / "walk_forward.py", title="Validation"),
    st.Page(V / "reports.py", title="Reports"),
    st.Page(V / "settings_data.py", title="Data"),
]
nav = st.navigation(pages, position="top")

d = state.data()
kind, label = state.data_badge()
items = [("FEED", label, {"ok": "live", "warn": "snap", "bad": "off"}[kind])]
if d is not None:
    p = d["prices"]
    items += [("SYMBOLS", str(p.shape[1]), ""), ("RANGE", f"{p.index[0].date()} → {p.index[-1].date()}", ""),
              ("SESSIONS", f"{len(p):,}", "")]
    disc = state.discovery()
    if disc is not None:
        items += [("DISCOVERY", f"{disc.window[0]} → {disc.window[1]}", ""),
                  ("ELIGIBLE", f"{disc.n_eligible}/{disc.n_tested}", "")]
    bt = state.get("backtest")
    if bt is not None:
        items.append(("LAST RUN", bt["segment"].upper(), ""))
status_strip(items)

nav.run()
