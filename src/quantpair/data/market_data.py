"""Market-data adapters.

Price convention: QuantPair uses split- and dividend-adjusted daily closes
(yfinance ``auto_adjust=True``) for every calculation. Adjusted and unadjusted
series are never mixed. Adjusted closes handle corporate actions consistently
for return and spread research, but providers restate history when new
dividends occur, so a saved snapshot may differ slightly from a fresh download.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
SNAPSHOT_FILE = DATA_DIR / "snapshot_prices.csv"


class DataFetchError(RuntimeError):
    """Raised when the provider cannot return usable prices."""


@dataclass
class PriceData:
    prices: pd.DataFrame               # index: tz-naive session dates; columns: tickers
    source: str                        # "yfinance" | "snapshot"
    retrieved_at: str
    requested: list[str]
    failed: list[str] = field(default_factory=list)
    is_snapshot: bool = False

    @property
    def date_range(self) -> tuple[str, str] | None:
        if self.prices.empty:
            return None
        return str(self.prices.index[0].date()), str(self.prices.index[-1].date())


def normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    """Tz-naive, midnight-normalised, sorted DatetimeIndex named 'date'."""
    out = df.copy()
    idx = pd.DatetimeIndex(pd.to_datetime(out.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "date"
    return out.sort_index()


def _clean_tickers(tickers: list[str]) -> list[str]:
    return list(dict.fromkeys(t.strip().upper() for t in tickers if t and t.strip()))


def fetch_prices(tickers: list[str], start: str, end: str | None = None,
                 retries: int = 2) -> PriceData:
    """Download adjusted daily closes from Yahoo Finance via yfinance.

    Requires network access. Failed tickers are reported, never filled with
    synthetic prices. ``end`` is exclusive (yfinance convention).
    """
    import yfinance as yf

    tickers = _clean_tickers(tickers)
    if not tickers:
        raise DataFetchError("No tickers requested.")
    last_err: Exception | None = None
    raw = None
    for attempt in range(retries + 1):
        try:
            raw = yf.download(tickers, start=start, end=end, auto_adjust=True,
                              progress=False, group_by="column", threads=True)
            if raw is not None and not raw.empty:
                break
        except Exception as exc:  # network failures, rate limits, provider changes
            last_err = exc
        time.sleep(1.5 * (attempt + 1))
    if raw is None or raw.empty:
        detail = f": {last_err}" if last_err else ""
        raise DataFetchError(
            "Yahoo Finance returned no data (network blocked, rate-limited, or invalid "
            f"tickers/dates){detail}. Retry later, reduce the universe, or load a saved snapshot.")
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].rename(columns={"Close": tickers[0]})
    close = normalize_index(close.reindex(columns=tickers)).astype(float)
    failed = [t for t in tickers if close[t].dropna().empty]
    close = close.drop(columns=failed)
    if close.empty:
        raise DataFetchError(f"No usable prices for any requested ticker: {failed}")
    return PriceData(close, "yfinance", dt.datetime.now().isoformat(timespec="seconds"),
                     tickers, failed)


def save_snapshot(data: PriceData, path: Path = SNAPSHOT_FILE) -> Path:
    """Persist real downloaded prices so research can be repeated offline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data.prices.to_csv(path)
    meta = {"source": data.source, "retrieved_at": data.retrieved_at,
            "requested": data.requested, "failed": data.failed}
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return path


def load_snapshot(path: Path = SNAPSHOT_FILE) -> PriceData:
    if not path.exists():
        raise DataFetchError(f"No snapshot found at {path}. Download data first and save a snapshot.")
    prices = normalize_index(pd.read_csv(path, index_col=0, parse_dates=True)).astype(float)
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return PriceData(prices, "snapshot", meta.get("retrieved_at", "unknown"),
                     meta.get("requested", list(prices.columns)), meta.get("failed", []),
                     is_snapshot=True)


def snapshot_info(path: Path = SNAPSHOT_FILE) -> dict | None:
    if not path.exists():
        return None
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return {"path": str(path), "retrieved_at": meta.get("retrieved_at", "unknown"),
            "tickers": meta.get("requested", [])}
