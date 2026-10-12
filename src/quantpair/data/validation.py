"""Data-quality checks. Problems are reported, never silently patched.

Missing sessions are left as NaN: interpolating prices would invent trades
that could not have happened. Pair-level analysis later aligns two series by
dropping dates where either leg is missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class QualityIssue:
    ticker: str
    severity: str      # "error" | "warning" | "info"
    check: str
    detail: str


@dataclass
class DataQualityReport:
    issues: list[QualityIssue] = field(default_factory=list)
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    start: str | None = None
    end: str | None = None
    n_dates: int = 0
    common_dates: int = 0

    def issues_frame(self) -> pd.DataFrame:
        return pd.DataFrame([i.__dict__ for i in self.issues],
                            columns=["ticker", "severity", "check", "detail"])

    @property
    def n_errors(self) -> int:
        return sum(i.severity == "error" for i in self.issues)

    @property
    def n_warnings(self) -> int:
        return sum(i.severity == "warning" for i in self.issues)


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def clean_prices(raw: pd.DataFrame, min_obs: int = 252, stale_run: int = 5,
                 stale_lag_days: int = 7) -> tuple[pd.DataFrame, DataQualityReport]:
    """Validate a wide price frame (dates x tickers) and return a safe copy.

    * duplicate timestamps -> last observation kept (reported)
    * non-positive / infinite prices -> NaN (error)
    * all-empty tickers -> dropped (error)
    * internal gaps, short history, stale endings, repeated prints -> reported
    """
    issues: list[QualityIssue] = []
    df = raw.copy()
    try:
        idx = pd.DatetimeIndex(pd.to_datetime(df.index))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Price index is not parseable as dates: {exc}") from exc
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df.sort_index()

    dup = df.index.duplicated(keep="last")
    if dup.any():
        issues.append(QualityIssue("ALL", "warning", "duplicate_timestamps",
                                   f"{int(dup.sum())} duplicate dates; kept the last observation."))
        df = df[~dup]

    df = df.apply(pd.to_numeric, errors="coerce").astype(float)
    bad = df.notna() & ((df <= 0) | np.isinf(df))
    for t in df.columns[bad.any()]:
        issues.append(QualityIssue(t, "error", "invalid_price",
                                   f"{int(bad[t].sum())} non-positive/infinite prices set to missing."))
    df = df.mask(bad)

    empty = [t for t in df.columns if df[t].dropna().empty]
    for t in empty:
        issues.append(QualityIssue(t, "error", "no_data", "No valid prices; ticker dropped."))
    df = df.drop(columns=empty)

    rows = []
    last_global = df.index.max() if len(df) else None
    for t in df.columns:
        s = df[t]
        first, last = s.first_valid_index(), s.last_valid_index()
        span = s.loc[first:last]
        n_obs = int(span.notna().sum())
        internal_missing = int(span.isna().sum())
        max_gap = _longest_run(span.isna().to_numpy())
        unchanged = _longest_run((span.dropna().diff() == 0).to_numpy()) + 1
        status = "ok"
        if n_obs < min_obs:
            status = "insufficient"
            issues.append(QualityIssue(t, "warning", "insufficient_history",
                                       f"{n_obs} observations < required {min_obs}."))
        if internal_missing:
            issues.append(QualityIssue(t, "warning" if max_gap > 3 else "info", "missing_sessions",
                                       f"{internal_missing} missing sessions inside history "
                                       f"(longest gap {max_gap}); not interpolated."))
        if last_global is not None and (last_global - last).days > stale_lag_days:
            status = "stale"
            issues.append(QualityIssue(t, "warning", "stale_end",
                                       f"Data ends {last.date()} vs dataset end {last_global.date()}."))
        if unchanged >= stale_run:
            issues.append(QualityIssue(t, "warning", "repeated_prints",
                                       f"{unchanged} consecutive identical prices (possible stale feed)."))
        rows.append({"ticker": t, "first": first.date(), "last": last.date(), "n_obs": n_obs,
                     "missing_inside": internal_missing,
                     "missing_frac": internal_missing / max(len(span), 1),
                     "max_gap": max_gap, "max_unchanged_run": unchanged, "status": status})

    common = int(df.dropna().shape[0]) if len(df.columns) else 0
    report = DataQualityReport(
        issues=issues, summary=pd.DataFrame(rows),
        start=str(df.index.min().date()) if len(df) else None,
        end=str(df.index.max().date()) if len(df) else None,
        n_dates=len(df), common_dates=common)
    return df, report
