"""Session state + cached engine calls shared by every page.

All pages read and write the same keys, so changing data or settings in one
section propagates to the others. Downstream results are cleared whenever the
underlying data change, so stale results are never shown against new data.
"""
from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from quantpair.config import BENCHMARK, DiscoveryConfig, ExperimentConfig
from quantpair.data.market_data import DataFetchError, PriceData, fetch_prices, load_snapshot
from quantpair.data.validation import clean_prices
from quantpair.research.pair_selection import DiscoveryResult, discover_pairs
from quantpair.validation.walk_forward import chronological_split

RESULT_KEYS = ("discovery", "backtest", "wf", "split_table", "grid", "cost_stress", "ml")


def cfg() -> ExperimentConfig:
    if "cfg" not in st.session_state:
        st.session_state["cfg"] = ExperimentConfig()
    return st.session_state["cfg"]


def get(key: str, default=None):
    return st.session_state.get(key, default)


def put(key: str, value) -> None:
    st.session_state[key] = value


def clear_results() -> None:
    for k in RESULT_KEYS:
        st.session_state.pop(k, None)


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def _fetch(tickers: tuple[str, ...], start: str, end: str | None) -> PriceData:
    return fetch_prices(list(tickers), start, end)


def load_data(source: str = "live") -> bool:
    """Fetch (or load snapshot), validate and store. Returns success."""
    c = cfg()
    tickers = list(dict.fromkeys(c.universe + [BENCHMARK]))
    try:
        data = _fetch(tuple(tickers), c.start, c.end) if source == "live" else load_snapshot()
    except DataFetchError as exc:
        put("data_error", str(exc))
        return False
    except Exception as exc:  # unexpected provider failure: surface verbatim
        put("data_error", f"{type(exc).__name__}: {exc}")
        return False
    prices, report = clean_prices(data.prices, min_obs=c.discovery.min_obs)
    if source == "snapshot":
        prices = prices.loc[c.start:c.end] if c.end else prices.loc[c.start:]
    put("data", {"prices": prices, "report": report, "meta": data})
    st.session_state.pop("data_error", None)
    clear_results()
    return True


def data() -> dict | None:
    return get("data")


def prices() -> pd.DataFrame | None:
    d = data()
    return None if d is None else d["prices"]


def universe_cols() -> list[str]:
    p = prices()
    return [] if p is None else [t for t in cfg().universe if t in p.columns]


def splits() -> dict:
    c = cfg()
    return chronological_split(prices().index, c.train_frac, c.val_frac)


@st.cache_data(show_spinner=False, max_entries=32)
def _discover(prices: pd.DataFrame, dcfg: dict, start, end, _progress=None) -> DiscoveryResult:
    return discover_pairs(prices, DiscoveryConfig(**dcfg), start, end, progress=_progress)


def run_discovery(tickers: list[str], dcfg: DiscoveryConfig, window: tuple, progress=None) -> DiscoveryResult:
    p = prices()[tickers]
    res = _discover(p, asdict(dcfg), pd.Timestamp(window[0]), pd.Timestamp(window[1]), _progress=progress)
    put("discovery", {"result": res, "tickers": tickers, "config": asdict(dcfg)})
    return res


def discovery() -> DiscoveryResult | None:
    d = get("discovery")
    return None if d is None else d["result"]


def require_data() -> pd.DataFrame:
    from ui.components import empty
    p = prices()
    if p is None:
        empty("No market data loaded",
              "Open Research Overview or Settings & Data to download prices (or load a saved snapshot).")
        if err := get("data_error"):
            st.error(err)
        st.stop()
    return p


def data_badge() -> tuple[str, str]:
    d = data()
    if d is None:
        return ("bad", "NO DATA")
    m: PriceData = d["meta"]
    return ("warn", f"SNAPSHOT {m.retrieved_at[:10]}") if m.is_snapshot else ("ok", f"LIVE {m.retrieved_at[:16]}")
