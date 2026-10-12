"""QuantPair design system: terminal-grade styling, layout primitives, chart theme.

Principles: information density, hairline rules instead of boxes, sharp
corners, uppercase micro-labels, monospaced numerics, one warm accent
(amber) for interaction and one cool accent (steel blue) for data.
"""
from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

C = {"bg": "#0a0c10", "panel": "#0e1117", "panel2": "#131821", "border": "#1d232d", "border2": "#2a313d",
     "text": "#d8dde4", "dim": "#9aa4b2", "muted": "#5f6b7a", "amber": "#e3a33b", "accent": "#5b9bd5",
     "pos": "#3fae7c", "neg": "#de5b52", "warn": "#e3a33b", "grid": "#161b23",
     "series": ["#5b9bd5", "#e3a33b", "#9b8ce0", "#3fae7c", "#de5b52", "#6fb6b0", "#c9cfd8"]}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root { --bg:%(bg)s; --panel:%(panel)s; --panel2:%(panel2)s; --bd:%(border)s; --bd2:%(border2)s; --tx:%(text)s;
        --dim:%(dim)s; --mu:%(muted)s; --amb:%(amber)s; --acc:%(accent)s; --pos:%(pos)s; --neg:%(neg)s; }
html, body, .stApp, button, input, textarea, select, p, li, label { font-family: 'IBM Plex Sans', sans-serif !important; }
.stApp { background: var(--bg); }
/* chrome */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], footer,
[data-testid="stSidebarCollapsedControl"], #MainMenu { display: none !important; }
header[data-testid="stHeader"] { background: var(--panel) !important; border-bottom: 1px solid var(--bd); }
header[data-testid="stHeader"] a, header[data-testid="stHeader"] a p, header[data-testid="stHeader"] a span {
  font-size: 12px !important; letter-spacing: .07em; text-transform: uppercase; color: var(--dim) !important; }
header[data-testid="stHeader"] a:hover p, header[data-testid="stHeader"] a:hover span { color: var(--tx) !important; }
header[data-testid="stHeader"] a[aria-current="page"] p, header[data-testid="stHeader"] a[aria-current="page"] span { color: var(--amb) !important; }
.block-container { padding: 4.2rem 2rem 4rem !important; max-width: 1560px; }
h1, h2, h3, h4 { font-weight: 500 !important; letter-spacing: -.005em; color: var(--tx); }
/* status strip */
.qp-strip { position: fixed; left: 0; right: 0; bottom: 0; z-index: 999; display: flex; align-items: stretch;
  height: 24px; background: var(--panel); border-top: 1px solid var(--bd); font: 11px 'IBM Plex Mono', monospace; color: var(--mu); }
.qp-strip span { padding: 0 12px; display: flex; align-items: center; border-right: 1px solid var(--bd); white-space: nowrap; }
.qp-strip b { color: var(--dim); font-weight: 500; margin-left: 6px; }
.qp-strip .live b { color: var(--pos); } .qp-strip .snap b { color: var(--amb); } .qp-strip .off b { color: var(--neg); }
.qp-strip .grow { flex: 1; border-right: none; justify-content: flex-end; overflow: hidden; }
/* page header */
.qp-page { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid var(--bd);
  padding-bottom: 12px; margin-bottom: 18px; gap: 24px; }
.qp-crumb { font: 11px 'IBM Plex Mono', monospace; color: var(--mu); letter-spacing: .08em; text-transform: uppercase; }
.qp-crumb i { color: var(--amb); font-style: normal; }
.qp-title { font-size: 22px; font-weight: 500; color: var(--tx); margin-top: 4px; letter-spacing: -.01em; }
.qp-sub { font-size: 13px; color: var(--mu); margin-top: 4px; max-width: 900px; line-height: 1.45; }
.qp-tags { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.qp-tag { font: 10.5px 'IBM Plex Mono', monospace; padding: 2px 7px; border: 1px solid var(--bd2); color: var(--dim);
  letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; display: inline-block; margin-right: 4px; }
.qp-tag.ok { color: var(--pos); border-color: #1f4a37; } .qp-tag.warn { color: var(--amb); border-color: #4d3b1c; }
.qp-tag.bad { color: var(--neg); border-color: #52241f; }
/* sections */
.qp-sec { display: flex; align-items: center; gap: 10px; margin: 26px 0 10px; }
.qp-sec .n { font: 11px 'IBM Plex Mono', monospace; color: var(--amb); }
.qp-sec .t { font-size: 11.5px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--tx); }
.qp-sec .r { flex: 1; height: 1px; background: var(--bd); }
.qp-sec .h { font: 11px 'IBM Plex Mono', monospace; color: var(--mu); }
/* KPI strip */
.qp-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); border: 1px solid var(--bd);
  background: var(--panel); margin: 4px 0 14px; }
.qp-kpi { padding: 10px 14px 11px; border-right: 1px solid var(--bd); min-width: 0; }
.qp-kpi:last-child { border-right: none; }
.qp-kpi .l { font-size: 10px; color: var(--mu); letter-spacing: .1em; text-transform: uppercase; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.qp-kpi .v { font: 500 17px 'IBM Plex Mono', monospace; color: var(--tx); margin-top: 5px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; letter-spacing: -.01em; }
.qp-kpi .v.pos { color: var(--pos); } .qp-kpi .v.neg { color: var(--neg); } .qp-kpi .v.acc { color: var(--acc); }
.qp-kpi .n { font: 10.5px 'IBM Plex Mono', monospace; color: var(--mu); margin-top: 3px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
/* empty / note */
.qp-empty { border: 1px dashed var(--bd2); padding: 22px 24px; background: var(--panel); }
.qp-empty .t { font-size: 13px; color: var(--tx); font-weight: 500; }
.qp-empty .b { font-size: 12.5px; color: var(--mu); margin-top: 6px; line-height: 1.5; max-width: 820px; }
.qp-note { font-size: 12px; color: var(--mu); line-height: 1.5; border-left: 2px solid var(--bd2); padding: 2px 0 2px 10px; margin: 6px 0 10px; }
/* widgets */
[data-testid="stWidgetLabel"] p { font-size: 10.5px !important; letter-spacing: .08em; text-transform: uppercase; color: var(--mu) !important; }
input, textarea { font-family: 'IBM Plex Mono', monospace !important; font-size: 13px !important; }
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] {
  background: var(--panel) !important; border-radius: 0 !important; }
[data-baseweb="tag"] { border-radius: 0 !important; font-family: 'IBM Plex Mono', monospace; }
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {
  border-radius: 0 !important; letter-spacing: .07em; text-transform: uppercase; font-weight: 500;
  border: 1px solid var(--bd2) !important; background: var(--panel) !important; color: var(--tx) !important; min-height: 34px; }
.stButton button p, .stDownloadButton button p, [data-testid="stFormSubmitButton"] button p { font-size: 11.5px !important; }
.stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { border-color: var(--amb) !important; color: var(--amb) !important; }
button[kind="primary"], button[kind="primaryFormSubmit"] { background: var(--amb) !important; color: #0a0c10 !important; border-color: var(--amb) !important; }
button[kind="primary"] p, button[kind="primaryFormSubmit"] p { color: #0a0c10 !important; font-weight: 600; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { background: #f0b450 !important; }
[data-testid="stForm"] { border: 1px solid var(--bd) !important; border-radius: 0 !important; background: var(--panel); padding: 16px 18px 6px; }
[data-testid="stExpander"] details { border: 1px solid var(--bd) !important; border-radius: 0 !important; background: var(--panel); }
[data-testid="stExpander"] summary p { font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--dim); }
[data-baseweb="tab-list"] { gap: 0 !important; border-bottom: 1px solid var(--bd); }
[data-baseweb="tab"] { padding: 8px 16px !important; }
[data-baseweb="tab"] p { font-size: 11.5px !important; letter-spacing: .08em; text-transform: uppercase; }
[data-baseweb="tab-highlight"] { background: var(--amb) !important; height: 2px !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--bd); }
[data-testid="stPlotlyChart"] { border: 1px solid var(--bd); background: var(--panel); }
[data-testid="stAlert"] > div { border-radius: 0 !important; background: var(--panel) !important;
  border: 1px solid var(--bd) !important; border-left: 2px solid var(--acc) !important; }
[data-testid="stAlert"] p, [data-testid="stAlert"] li, [data-testid="stAlert"] div { font-family: 'IBM Plex Sans', sans-serif !important; color: var(--dim) !important; font-size: 12.5px !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) > div { border-left-color: var(--amb) !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) > div { border-left-color: var(--neg) !important; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) > div { border-left-color: var(--pos) !important; }
[data-testid="stAlert"] [data-testid="stAlertDynamicIcon"], [data-testid="stAlert"] svg { display: none !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--mu) !important; font-size: 12px !important; }
hr { border-color: var(--bd) !important; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS % C, unsafe_allow_html=True)


def status_strip(items: list[tuple[str, str, str]]) -> None:
    """Fixed bottom bar of (label, value, css class) cells."""
    cells = "".join(f'<span class="{k}">{html.escape(lbl)}<b>{html.escape(v)}</b></span>' for lbl, v, k in items)
    st.markdown(f'<div class="qp-strip">{cells}<span class="grow">QUANTPAIR v0.1 · RESEARCH USE ONLY · '
                f'NOT INVESTMENT ADVICE</span></div>', unsafe_allow_html=True)


_SEC = {"n": 0}


def header(title: str, subtitle: str = "", tags: list[tuple[str, str]] | None = None, crumb: str = "Research") -> None:
    _SEC["n"] = 0
    t = "".join(f'<span class="qp-tag {k}">{html.escape(v)}</span>' for k, v in (tags or []))
    st.markdown(f'<div class="qp-page"><div><div class="qp-crumb">QuantPair <i>/</i> {html.escape(crumb)}</div>'
                f'<div class="qp-title">{html.escape(title)}</div><div class="qp-sub">{html.escape(subtitle)}</div></div>'
                f'<div class="qp-tags">{t}</div></div>', unsafe_allow_html=True)


def section(title: str, hint: str = "") -> None:
    _SEC["n"] += 1
    st.markdown(f'<div class="qp-sec"><span class="n">{_SEC["n"]:02d}</span><span class="t">{html.escape(title)}</span>'
                f'<span class="r"></span><span class="h">{html.escape(hint)}</span></div>', unsafe_allow_html=True)


def kpis(items: list[tuple]) -> None:
    """items: (label, value_str, tone in {'', 'pos', 'neg', 'acc'}, note?)"""
    cells = []
    for it in items:
        label, value, tn = it[0], it[1], it[2] if len(it) > 2 else ""
        nt = f'<div class="n">{html.escape(str(it[3]))}</div>' if len(it) > 3 and it[3] else ""
        cells.append(f'<div class="qp-kpi"><div class="l">{html.escape(label)}</div>'
                     f'<div class="v {tn}">{html.escape(str(value))}</div>{nt}</div>')
    st.markdown(f'<div class="qp-kpis">{"".join(cells)}</div>', unsafe_allow_html=True)


def empty(title: str, body: str) -> None:
    st.markdown(f'<div class="qp-empty"><div class="t">{html.escape(title)}</div>'
                f'<div class="b">{html.escape(body)}</div></div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="qp-note">{html.escape(text)}</div>', unsafe_allow_html=True)


def tone(v, invert: bool = False) -> str:
    if v is None:
        return ""
    return ("neg" if v > 0 else "pos" if v < 0 else "") if invert else ("pos" if v > 0 else "neg" if v < 0 else "")


def pct(v, d: int = 2) -> str:
    return "—" if v is None or v != v else f"{v * 100:.{d}f}%"


def num(v, d: int = 2) -> str:
    return "—" if v is None or v != v else f"{v:,.{d}f}"


def money(v) -> str:
    return "—" if v is None or v != v else f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def style(fig: go.Figure, height: int = 320, title: str | None = None, legend: bool = True) -> go.Figure:
    mono = "IBM Plex Mono, Consolas, monospace"
    fig.update_layout(
        height=height,
        title=dict(text=title.upper(), font=dict(size=10.5, color=C["dim"], family="IBM Plex Sans, Helvetica, Arial, sans-serif"),
                   x=0.012, y=0.975, xanchor="left") if title else None,
        paper_bgcolor=C["panel"], plot_bgcolor=C["panel"], font=dict(color=C["muted"], size=10.5, family=mono),
        margin=dict(l=56, r=20, t=38 if title else 12, b=30), colorway=C["series"], hovermode="x unified",
        dragmode="zoom", showlegend=legend,
        hoverlabel=dict(bgcolor=C["panel2"], bordercolor=C["border2"], font=dict(color=C["text"], size=11, family=mono)),
        legend=dict(orientation="h", y=1.0, x=1, xanchor="right", yanchor="bottom", bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10.5, color=C["dim"]), itemsizing="constant"))
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True, linecolor=C["border"], ticks="outside",
                     ticklen=3, tickcolor=C["border"], tickfont=dict(size=10),
                     showspikes=True, spikemode="across", spikethickness=1, spikedash="solid", spikecolor=C["border2"])
    fig.update_yaxes(gridcolor=C["grid"], zeroline=False, showline=False, ticks="", tickfont=dict(size=10))
    fig.update_annotations(font=dict(size=10.5, color=C["dim"], family="IBM Plex Sans, Helvetica, Arial, sans-serif"))
    return fig


def plot(fig: go.Figure, **kw) -> None:
    st.plotly_chart(style(fig, **kw), width="stretch", config={"displaylogo": False, "displayModeBar": False})


def _rgba(hex_: str, a: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def area(x, y, name: str, color: str | None = None, baseline: float | None = None) -> list[go.Scatter]:
    """Line with a faint vertical gradient fill down to `baseline` (default: series minimum)."""
    color = color or C["accent"]
    yv = list(y)
    base = baseline if baseline is not None else (min(v for v in yv if v == v) if yv else 0)
    floor = go.Scatter(x=x, y=[base] * len(yv), mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False)
    top = go.Scatter(x=x, y=yv, name=name, mode="lines", fill="tonexty", line=dict(color=color, width=1.5),
                     fillgradient=dict(type="vertical", colorscale=[[0, _rgba(color, 0.0)], [1, _rgba(color, 0.18)]]))
    return [floor, top]


def warnings_box(items: list[str], kind: str = "warning") -> None:
    if items:
        getattr(st, kind)("\n".join(f"- {w}" for w in items))
