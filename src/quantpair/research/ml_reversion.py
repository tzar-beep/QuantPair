"""Extension C - machine-learning reversion filter (optional research module).

Question: given a spread that is currently stretched (|z| >= min_abs_z), will
it revert inside the exit band within the next H sessions?

Target (label at t): 1 if for some k in 1..H, z_{t+k} has crossed back inside
the exit band on the reverting side (z>0: z_{t+k} <= exit_z; z<0:
z_{t+k} >= -exit_z), else 0. Labels need H future sessions, so a row is only
used if t+H lies inside the same segment: training labels never peek into the
evaluation period (purging).

Features at t use only data up to t: z, |z|, 5-day z change, normalised spread
volatility, trailing AR(1) half-life, trailing return correlation, rolling
hedge-ratio instability and market volatility. Tree models need no feature
scaling, so no normalisation statistics can leak.

Model: scikit-learn HistGradientBoostingClassifier (gradient-boosted trees,
same family as XGBoost; avoids an extra dependency) with fixed, untuned
hyper-parameters - no tuning on the evaluation segment. Baseline: logistic
regression on |z| alone (the classical statistical rule).

Caveat: in the training segment the static hedge ratio is fitted on that same
segment, so training spreads are slightly in-sample; evaluation spreads are not.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from quantpair.backtesting.engine import run_backtest
from quantpair.config import BacktestConfig, StrategyConfig
from quantpair.strategy.pairs_strategy import PairSignals, build_pair_signals

FEATURES = ["z", "abs_z", "z_chg5", "spread_vol_ratio", "half_life60", "ret_corr60", "beta_instab", "mkt_vol21"]


@dataclass
class MLConfig:
    horizon: int = 10            # sessions ahead for the reversion label
    min_abs_z: float = 1.0       # only stretched spreads are modelled
    threshold: float = 0.5       # entry allowed if P(revert) >= threshold
    max_depth: int = 3
    learning_rate: float = 0.05
    max_iter: int = 200
    random_state: int = 0


def pair_features(sig: PairSignals, market: pd.Series | None) -> pd.DataFrame:
    f = sig.frame
    s, z = f["spread"], f["z"]
    ds = s.diff()
    lag = s.shift(1)
    b = ds.rolling(60).cov(lag) / lag.rolling(60).var()            # trailing AR slope
    hl = (-np.log(2) / np.log1p(b.where((b < 0) & (b > -1)))).clip(upper=500)
    ry, rx = np.log(f["price_y"]).diff(), np.log(f["price_x"]).diff()
    roll_beta = ry.rolling(60).cov(rx) / rx.rolling(60).var()
    out = pd.DataFrame({
        "z": z, "abs_z": z.abs(), "z_chg5": z - z.shift(5),
        "spread_vol_ratio": ds.rolling(20).std() / s.rolling(60).std(),
        "half_life60": hl, "ret_corr60": ry.rolling(60).corr(rx),
        "beta_instab": roll_beta.rolling(20).std() / roll_beta.rolling(20).mean().abs(),
    }, index=f.index)
    if market is not None:
        mr = np.log(market).diff()
        out["mkt_vol21"] = (mr.rolling(21).std() * np.sqrt(252)).reindex(f.index)
    else:
        out["mkt_vol21"] = np.nan
    return out.replace([np.inf, -np.inf], np.nan)


def reversion_label(z: pd.Series, horizon: int, exit_z: float) -> pd.Series:
    zz = z.to_numpy(float)
    n = len(zz)
    lab = np.full(n, np.nan)
    for t in range(n - horizon):
        if not np.isfinite(zz[t]) or zz[t] == 0:
            continue
        fut = zz[t + 1:t + 1 + horizon]
        hit = (fut <= exit_z) if zz[t] > 0 else (fut >= -exit_z)
        lab[t] = float(np.any(hit[np.isfinite(fut)]))
    return pd.Series(lab, index=z.index, name="label")


def build_dataset(signals: list[PairSignals], market, cfg: MLConfig, exit_z: float) -> pd.DataFrame:
    parts = []
    for sig in signals:
        X = pair_features(sig, market)
        X["label"] = reversion_label(sig.frame["z"], cfg.horizon, exit_z)
        X["pair"] = sig.name
        parts.append(X[X["abs_z"] >= cfg.min_abs_z])
    return pd.concat(parts) if parts else pd.DataFrame(columns=FEATURES + ["label", "pair"])


@dataclass
class MLResult:
    summary: dict
    importance: pd.DataFrame
    comparison: pd.DataFrame
    eval_predictions: pd.DataFrame


def run_ml_study(prices: pd.DataFrame, pairs: pd.DataFrame, strat: StrategyConfig, bt: BacktestConfig,
                 fit_window: tuple, eval_window: tuple, market: pd.Series | None,
                 cfg: MLConfig | None = None) -> MLResult:
    cfg = cfg or MLConfig()
    if pairs.empty:
        raise ValueError("No pairs supplied for the ML study.")
    tr_sig = [build_pair_signals(prices, r.y, r.x, strat, fit_window, fit_window) for r in pairs.itertuples()]
    ev_sig = [build_pair_signals(prices, r.y, r.x, strat, fit_window, eval_window) for r in pairs.itertuples()]
    tr = build_dataset(tr_sig, market, cfg, strat.exit_z).dropna(subset=["label"])
    ev = build_dataset(ev_sig, market, cfg, strat.exit_z).dropna(subset=["label"])
    if len(tr) < 50 or tr["label"].nunique() < 2:
        raise ValueError(f"Too few usable training rows ({len(tr)}) or a single class; widen the window or "
                         "lower min |z|.")
    model = HistGradientBoostingClassifier(max_depth=cfg.max_depth, learning_rate=cfg.learning_rate,
                                           max_iter=cfg.max_iter, random_state=cfg.random_state)
    model.fit(tr[FEATURES], tr["label"])
    base = LogisticRegression().fit(tr[["abs_z"]].fillna(0), tr["label"])
    summary = {"n_train": len(tr), "n_eval": len(ev), "train_base_rate": float(tr["label"].mean()),
               "horizon": cfg.horizon, "threshold": cfg.threshold, "min_abs_z": cfg.min_abs_z}
    imp = pd.DataFrame(columns=["feature", "importance_mean", "importance_std"])
    preds = pd.DataFrame()
    if len(ev) and ev["label"].nunique() == 2:
        p_m = model.predict_proba(ev[FEATURES])[:, 1]
        p_b = base.predict_proba(ev[["abs_z"]].fillna(0))[:, 1]
        summary.update(eval_base_rate=float(ev["label"].mean()),
                       auc_model=float(roc_auc_score(ev["label"], p_m)),
                       auc_baseline_absz=float(roc_auc_score(ev["label"], p_b)),
                       brier_model=float(brier_score_loss(ev["label"], p_m)),
                       brier_baseline=float(brier_score_loss(ev["label"], p_b)),
                       brier_base_rate=float(brier_score_loss(ev["label"], np.full(len(ev), tr["label"].mean()))))
        pi = permutation_importance(model, ev[FEATURES], ev["label"], scoring="roc_auc", n_repeats=5,
                                    random_state=cfg.random_state)
        imp = pd.DataFrame({"feature": FEATURES, "importance_mean": pi.importances_mean,
                            "importance_std": pi.importances_std}).sort_values("importance_mean", ascending=False)
        preds = ev.assign(p_model=p_m, p_baseline=p_b)
    else:
        summary["note"] = "Evaluation rows contain a single class; AUC undefined."

    # Strategy comparison: same signals, entries allowed only where P(revert) >= threshold.
    filt_sig = []
    for r, sig in zip(pairs.itertuples(), ev_sig):
        X = pair_features(sig, market)
        ok = X[FEATURES].notna().any(axis=1)
        prob = pd.Series(np.nan, index=X.index)
        if ok.any():
            prob[ok] = model.predict_proba(X.loc[ok, FEATURES])[:, 1]
        filt_sig.append(build_pair_signals(prices, r.y, r.x, strat, fit_window, eval_window,
                                           entry_filter=prob >= cfg.threshold))
    rows = []
    for name, sigs in (("Statistical rule (unfiltered)", ev_sig), ("ML-filtered entries", filt_sig)):
        m = run_backtest(prices, sigs, replace(bt), *eval_window).metrics
        rows.append({"strategy": name, **{k: m[k] for k in ("total_return", "sharpe", "max_drawdown", "n_trades",
                                                           "win_rate", "total_costs")}})
    return MLResult(summary, imp, pd.DataFrame(rows), preds)
