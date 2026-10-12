"""Module B - candidate generation, cointegration testing, FDR control, ranking.

Statistical notes
* Engle-Granger (``statsmodels.tsa.stattools.coint``): regress y on x, then
  test the residual for a unit root using MacKinnon critical values that
  account for the estimated hedge ratio. This is the cointegration test.
* A plain ADF test on that same residual uses the wrong (too lenient)
  critical values because the residual was fitted to look stationary; it is
  reported only as a descriptive diagnostic.
* Orientation is fixed (y = first ticker in universe order) so each pair is
  tested once; testing both directions and keeping the better p-value would
  be an extra hidden test.
* Benjamini-Hochberg controls the expected share of false discoveries among
  pairs declared significant. It assumes independent or positively dependent
  p-values; pairs sharing a leg are dependent, so q-values are approximate.
* Everything is estimated on the discovery (training) window only.
"""
from __future__ import annotations

import itertools
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

from quantpair.config import DiscoveryConfig
from quantpair.research.spread_model import compute_spread, estimate_half_life, fit_hedge_ratio, rolling_hedge_ratio


def benjamini_hochberg(pvalues: np.ndarray | list[float], q: float = 0.10
                       ) -> tuple[np.ndarray, np.ndarray]:
    """BH step-up procedure. Returns (adjusted p-values, reject mask). NaNs stay NaN/False."""
    p = np.asarray(pvalues, dtype=float)
    adj = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    m = int(ok.sum())
    if m:
        pv = p[ok]
        order = np.argsort(pv)
        ranked = pv[order] * m / np.arange(1, m + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1]
        out = np.empty(m)
        out[order] = np.clip(ranked, 0, 1)
        adj[ok] = out
    return adj, np.where(ok, adj <= q, False)


def candidate_pairs(tickers: list[str]) -> list[tuple[str, str]]:
    """Unordered pairs (each combination once), oriented by universe order."""
    return list(itertools.combinations(list(dict.fromkeys(tickers)), 2))


def eligible_tickers(prices: pd.DataFrame, cfg: DiscoveryConfig) -> tuple[list[str], dict[str, str]]:
    ok, excluded = [], {}
    for t in prices.columns:
        s = prices[t]
        first = s.first_valid_index()
        if first is None:
            excluded[t] = "no data in window"
            continue
        span = s.loc[first:]
        n, miss = int(span.notna().sum()), float(span.isna().mean())
        if n < cfg.min_obs:
            excluded[t] = f"{n} obs < {cfg.min_obs}"
        elif miss > cfg.max_missing_frac:
            excluded[t] = f"missing {miss:.1%} > {cfg.max_missing_frac:.0%}"
        else:
            ok.append(t)
    return ok, excluded


def analyze_pair(y: pd.Series, x: pd.Series, cfg: DiscoveryConfig) -> dict:
    df = pd.concat({"y": y, "x": x}, axis=1).dropna()
    row: dict = {"pair": f"{y.name}/{x.name}", "y": y.name, "x": x.name, "n_obs": len(df)}
    if len(df) < cfg.min_obs:
        row["status"] = "insufficient aligned history"
        return row
    row.update(start=str(df.index[0].date()), end=str(df.index[-1].date()))
    rets = np.log(df).diff().dropna()
    ct = cfg.coint_trend == "ct"
    fit = fit_hedge_ratio(df["y"], df["x"], cfg.use_intercept, use_trend=ct)
    spread = compute_spread(df["y"], df["x"], fit.beta, fit.intercept, fit.trend)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eg_stat, eg_p, _ = coint(df["y"], df["x"], trend=cfg.coint_trend if cfg.use_intercept else "n",
                                 autolag="aic")
        adf_stat, adf_p = adfuller(spread, autolag="AIC")[:2]
    hl = estimate_half_life(spread)
    rb = rolling_hedge_ratio(df["y"], df["x"], cfg.stability_window, cfg.use_intercept)["beta"].dropna()
    mean_rb = rb.mean() if len(rb) else np.nan
    beta_cv = float(rb.std() / abs(mean_rb)) if len(rb) > 1 and abs(mean_rb) > 1e-12 else np.nan
    sign_flip = float((np.sign(rb) != np.sign(fit.beta)).mean()) if len(rb) else np.nan
    row.update(
        status="tested", return_corr=float(rets["y"].corr(rets["x"])),
        price_corr=float(df["y"].corr(df["x"])), beta=fit.beta, intercept=fit.intercept, trend=fit.trend,
        r2=fit.r2, eg_stat=float(eg_stat), eg_pvalue=float(eg_p),
        adf_stat=float(adf_stat), adf_pvalue_naive=float(adf_p),
        half_life=hl.value, half_life_valid=hl.valid, half_life_note=hl.reason,
        spread_std=float(spread.std()), beta_cv=beta_cv, beta_sign_flip=sign_flip)
    return row


@dataclass
class DiscoveryResult:
    table: pd.DataFrame
    window: tuple[str, str]
    tickers: list[str]
    excluded: dict[str, str] = field(default_factory=dict)
    n_candidates: int = 0
    n_tested: int = 0

    @property
    def n_significant(self) -> int:
        return int(self.table["fdr_pass"].sum()) if "fdr_pass" in self.table else 0

    @property
    def n_eligible(self) -> int:
        return int(self.table["eligible"].sum()) if "eligible" in self.table else 0


def _pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True).fillna(0.0)


def discover_pairs(prices: pd.DataFrame, cfg: DiscoveryConfig, start=None, end=None,
                   progress: Callable[[float, str], None] | None = None) -> DiscoveryResult:
    """Run the full discovery pipeline on prices.loc[start:end] only."""
    window = prices.loc[start:end]
    if window.empty:
        raise ValueError("Discovery window contains no data.")
    win = (str(window.index[0].date()), str(window.index[-1].date()))
    tickers, excluded = eligible_tickers(window, cfg)
    pairs = candidate_pairs(tickers)
    rows = []
    for k, (a, b) in enumerate(pairs):
        if progress:
            progress((k + 1) / max(len(pairs), 1), f"{a}/{b}")
        rows.append(analyze_pair(window[a], window[b], cfg))
    table = pd.DataFrame(rows)
    if table.empty:
        return DiscoveryResult(table, win, tickers, excluded, 0, 0)
    tested = table["status"].eq("tested") if "status" in table else pd.Series(False, index=table.index)
    if "eg_pvalue" not in table:
        table["eg_pvalue"] = np.nan
    table["q_value"], table["fdr_pass"] = benjamini_hochberg(
        table["eg_pvalue"].where(tested).to_numpy(), cfg.fdr_q)
    table["raw_pass"] = tested & (table["eg_pvalue"] < cfg.coint_alpha)
    hl = pd.to_numeric(table.get("half_life"), errors="coerce")
    table["hl_ok"] = (tested & table.get("half_life_valid", False).fillna(False).astype(bool)
                      & hl.between(cfg.min_half_life, cfg.max_half_life))
    # Transparent composite: percentile ranks of three interpretable components.
    table["evidence"] = -np.log10(table["q_value"].clip(lower=1e-12))
    table["stability"] = 1 / (1 + table.get("beta_cv", np.nan))
    table["history"] = table["n_obs"] / table["n_obs"].max()
    w = cfg.rank_weights
    table["score"] = np.where(tested, w[0] * _pct_rank(table["evidence"].where(tested))
                              + w[1] * _pct_rank(table["stability"].where(tested))
                              + w[2] * _pct_rank(table["history"].where(tested)), np.nan)
    table["eligible"] = table["fdr_pass"] & table["hl_ok"]
    table["discovery_start"], table["discovery_end"] = win
    table = table.sort_values(["eligible", "fdr_pass", "score"], ascending=False).reset_index(drop=True)
    return DiscoveryResult(table, win, tickers, excluded, len(pairs), int(tested.sum()))


def select_pairs(table: pd.DataFrame, top_k: int = 5, selection: str = "fdr") -> pd.DataFrame:
    """Pick tradeable pairs from a discovery table (never by backtest P&L).

    'fdr': BH-significant and half-life in range. 'raw': raw p < alpha and
    half-life in range - exploratory only, inflates false discoveries.
    """
    if table.empty or "score" not in table:
        return table.iloc[0:0]
    mask = table["eligible"] if selection == "fdr" else (table["raw_pass"] & table["hl_ok"])
    return table[mask].sort_values("score", ascending=False).head(top_k).reset_index(drop=True)
