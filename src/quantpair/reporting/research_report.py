"""Markdown research report assembled from actual computed results."""
from __future__ import annotations

import pandas as pd

METHODOLOGY = """\
* Prices: split/dividend-adjusted daily closes (Yahoo Finance via yfinance). Missing sessions are not interpolated.
* Discovery: all unordered pairs of eligible tickers; OLS hedge ratio y = a + b·x on the discovery window;
  Engle–Granger cointegration test (MacKinnon p-values); Benjamini–Hochberg FDR across all tested pairs;
  AR(1) half-life of the residual spread. Pairs are ranked by percentile ranks of FDR evidence, hedge-ratio
  stability and history length — never by backtest profit.
* Signals: rolling z-score of the spread using data up to t; enter at |z| ≥ entry, exit inside the exit band,
  optional stop and max-holding rules.
* Execution: signals at the close of t trade at the close of t+lag (lag ≥ 1). Fees and slippage are charged on
  traded notional of both legs; short borrow fees accrue daily on short notional.
* Validation: chronological train/validation/test split and rolling walk-forward re-discovery.
"""

LIMITATIONS = """\
* Close-to-close execution with linear costs; no market impact model, partial fills or intraday prices.
* No interest on cash/margin; borrow availability and recalls are not modelled; borrow fee is a flat rate.
* Survivorship bias: the universe is chosen today; delisted names are absent.
* Adjusted prices are restated by the provider over time.
* BH correction assumes independent/positively dependent tests; pairs sharing a leg are dependent.
* Cointegration estimated in-sample may break out of sample; past mean reversion does not guarantee future reversion.
"""


def _fmt(v, pct=False) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/a"
    if pct:
        return f"{v:.2%}"
    return f"{v:,.3f}" if isinstance(v, float) else str(v)


def _table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_none_\n"
    d = df.head(max_rows).copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "n/a" if pd.isna(v) else f"{v:.4g}")
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join(lines) + "\n"


PCT_KEYS = {"total_return", "cagr", "ann_vol", "max_drawdown", "win_rate", "avg_trade_return",
            "avg_gross_exposure", "avg_net_exposure", "time_in_market", "var", "es"}


def build_report(config: dict, data_info: dict, discovery: pd.DataFrame | None,
                 selected: pd.DataFrame | None, metrics: dict | None, risk: dict | None,
                 split_table: pd.DataFrame | None, wf_windows: pd.DataFrame | None,
                 warnings: list[str], conclusion: str) -> str:
    s = config.get("strategy", {})
    c = config.get("backtest", {}).get("costs", {})
    out = ["# QuantPair Research Report\n",
           "## Experiment configuration\n", f"```json\n{_json(config)}\n```\n",
           "## Dataset\n", "\n".join(f"* **{k}**: {v}" for k, v in data_info.items()) + "\n",
           "## Methodology\n", METHODOLOGY,
           "## Strategy parameters\n",
           f"lookback={s.get('lookback')}, entry_z={s.get('entry_z')}, exit_z={s.get('exit_z')}, "
           f"stop_z={s.get('stop_z')}, max_hold={s.get('max_hold')}, hedge={s.get('hedge_method')}\n",
           "## Transaction-cost assumptions\n",
           f"fees {c.get('fee_bps')} bps, slippage {c.get('slippage_bps')} bps per leg traded; "
           f"borrow {c.get('borrow_bps_annual')} bps/yr on short notional.\n"]
    if discovery is not None:
        cols = [k for k in ("pair", "n_obs", "beta", "eg_pvalue", "q_value", "half_life", "beta_cv",
                            "score", "eligible") if k in discovery]
        out += ["## Pair-selection results\n", _table(discovery[cols], 25)]
    if selected is not None:
        out += ["### Selected pairs\n", _table(selected[[k for k in ("pair", "beta", "q_value", "half_life")
                                                        if k in selected]])]
    if metrics:
        out += ["## Performance metrics\n",
                "\n".join(f"* {k}: {_fmt(v, k in PCT_KEYS)}" for k, v in metrics.items()) + "\n"]
    if risk:
        out += ["## Risk metrics\n", "\n".join(f"* {k}: {_fmt(v, k in PCT_KEYS)}" for k, v in risk.items()) + "\n"]
    if split_table is not None:
        out += ["## In-sample / validation / test\n", _table(split_table)]
    if wf_windows is not None:
        out += ["## Walk-forward windows\n", _table(wf_windows)]
    out += ["## Warnings\n", "\n".join(f"* {w}" for w in warnings) + "\n" if warnings else "_none_\n",
            "## Limitations\n", LIMITATIONS, "## Conclusion\n", conclusion + "\n"]
    return "\n".join(out)


def _json(obj) -> str:
    import json

    from quantpair.reporting.exports import to_jsonable
    return json.dumps(to_jsonable(obj), indent=2)
