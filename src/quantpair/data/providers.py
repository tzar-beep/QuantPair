"""Keyed market-data providers: history (Alpaca) and live quotes (Alpaca, Finnhub).

Keys come from environment variables or are set at runtime by the API layer.
They are never logged or returned; ``key_status`` exposes only masked hints.

  ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY   history + live quotes (free tier)
  FINNHUB_API_KEY                             live quotes (free tier)

Price convention is unchanged: daily bars are split- and dividend-adjusted
(Alpaca ``adjustment=all``) so they are comparable with the Yahoo series.
Live quotes are last trades; on Alpaca's free plan they come from the IEX
exchange only, which can differ slightly from the consolidated tape.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

from quantpair.data.market_data import DataFetchError, PriceData, normalize_index

ALPACA_DATA = "https://data.alpaca.markets/v2"
FINNHUB = "https://finnhub.io/api/v1"
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
KEYS = ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "FINNHUB_API_KEY")
TIMEOUT = 20


def load_env_file(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines); existing environment wins."""
    path = path or ENV_FILE
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def set_keys(values: dict[str, str], persist: bool = False, path: Path | None = None) -> None:
    """Set keys for this process; optionally write them to the gitignored .env file."""
    path = path or ENV_FILE
    for k, v in values.items():
        if k not in KEYS:
            raise ValueError(f"Unknown key name: {k}")
        if v:
            os.environ[k] = v.strip()
        else:
            os.environ.pop(k, None)
    if persist:
        existing = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    a, b = line.split("=", 1)
                    existing[a.strip()] = b.strip()
        for k in KEYS:
            if os.environ.get(k):
                existing[k] = os.environ[k]
            else:
                existing.pop(k, None)
        path.write_text("".join(f"{k}={v}\n" for k, v in existing.items()), encoding="utf-8")


def _mask(v: str | None) -> str | None:
    return None if not v else f"••••{v[-4:]}" if len(v) > 4 else "••••"


def key_status() -> dict:
    a_id, a_sec, fh = (os.environ.get(k) for k in KEYS)
    return {"alpaca": {"configured": bool(a_id and a_sec), "key_id": _mask(a_id)},
            "finnhub": {"configured": bool(fh), "key": _mask(fh)},
            "persisted": ENV_FILE.exists()}


def _alpaca_headers() -> dict:
    a_id, a_sec = os.environ.get(KEYS[0]), os.environ.get(KEYS[1])
    if not (a_id and a_sec):
        raise DataFetchError("Alpaca keys are not configured. Add them in Data → Data provider.")
    return {"APCA-API-KEY-ID": a_id, "APCA-API-SECRET-KEY": a_sec, "Accept": "application/json"}


def _get(url: str, headers: dict | None = None, params: dict | None = None) -> dict:
    try:
        r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise DataFetchError(f"Network error contacting provider: {exc}") from exc
    if r.status_code in (401, 403):
        raise DataFetchError(f"Provider rejected the API key (HTTP {r.status_code}). Check the key and its plan.")
    if r.status_code == 429:
        raise DataFetchError("Provider rate limit reached (HTTP 429). Wait a minute and retry.")
    if not r.ok:
        raise DataFetchError(f"Provider error HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def fetch_prices_alpaca(tickers: list[str], start: str, end: str | None = None, feed: str = "sip") -> PriceData:
    """Adjusted daily closes from Alpaca, following pagination.

    The free plan serves SIP history except the most recent 15 minutes, which
    is irrelevant for daily bars; use feed="iex" if your plan rejects "sip".
    """
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    if not tickers:
        raise DataFetchError("No tickers requested.")
    headers = _alpaca_headers()
    params = {"symbols": ",".join(tickers), "timeframe": "1Day", "start": start, "adjustment": "all",
              "feed": feed, "limit": 10000}
    if end:
        params["end"] = end
    closes: dict[str, dict[str, float]] = {t: {} for t in tickers}
    while True:
        js = _get(f"{ALPACA_DATA}/stocks/bars", headers, params)
        for sym, bars in (js.get("bars") or {}).items():
            for b in bars:
                closes.setdefault(sym, {})[b["t"][:10]] = float(b["c"])
        token = js.get("next_page_token")
        if not token:
            break
        params["page_token"] = token
    frame = pd.DataFrame({t: pd.Series(v, dtype=float) for t, v in closes.items()})
    if frame.empty:
        raise DataFetchError("Alpaca returned no bars for these tickers and dates.")
    frame = normalize_index(frame).reindex(columns=tickers)
    failed = [t for t in tickers if frame[t].dropna().empty]
    frame = frame.drop(columns=failed)
    if frame.empty:
        raise DataFetchError(f"No usable bars for any requested ticker: {failed}")
    return PriceData(frame, "alpaca", dt.datetime.now().isoformat(timespec="seconds"), tickers, failed)


@dataclass
class Quote:
    symbol: str
    price: float
    time: str          # ISO timestamp of the trade/quote
    source: str


def latest_quotes(tickers: list[str], provider: str = "auto") -> dict[str, Quote]:
    """Latest trade price per ticker. provider: 'alpaca', 'finnhub' or 'auto' (first configured)."""
    st = key_status()
    if provider == "auto":
        provider = "alpaca" if st["alpaca"]["configured"] else "finnhub" if st["finnhub"]["configured"] else ""
    if not provider:
        raise DataFetchError("No live-data key configured. Add an Alpaca or Finnhub key in Data → Data provider.")
    syms = list(dict.fromkeys(t.upper() for t in tickers))
    out: dict[str, Quote] = {}
    if provider == "alpaca":
        js = _get(f"{ALPACA_DATA}/stocks/trades/latest", _alpaca_headers(), {"symbols": ",".join(syms), "feed": "iex"})
        for sym, tr in (js.get("trades") or {}).items():
            out[sym] = Quote(sym, float(tr["p"]), str(tr["t"]), "alpaca (IEX)")
    elif provider == "finnhub":
        key = os.environ.get("FINNHUB_API_KEY")
        if not key:
            raise DataFetchError("Finnhub key is not configured.")
        for sym in syms:
            js = _get(f"{FINNHUB}/quote", params={"symbol": sym, "token": key})
            if js.get("c"):
                ts = dt.datetime.fromtimestamp(int(js.get("t") or 0), dt.UTC).isoformat()
                out[sym] = Quote(sym, float(js["c"]), ts, "finnhub")
    else:
        raise DataFetchError(f"Unknown provider: {provider}")
    return out


def test_connection(provider: str) -> dict:
    """Cheap authenticated call to confirm a key works."""
    q = latest_quotes(["SPY"], provider)
    if "SPY" not in q:
        raise DataFetchError("Connected, but no quote returned for SPY.")
    return {"ok": True, "provider": provider, "spy": q["SPY"].price, "time": q["SPY"].time}
