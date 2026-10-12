"""Module C - hedge ratios, spreads, z-scores, half-life and OU estimates.

Spread convention (used everywhere):

    spread_t = P^y_t - (alpha + beta * P^x_t)

i.e. the OLS residual of y on x in *price levels*. Long the spread = long 1
share of y, short beta shares of x. This is a residual (level) relationship,
not a return relationship: a return regression tells you how daily moves
co-vary, but only a stationary *level* residual implies the prices are tied
together and drift back toward each other (cointegration).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm


@dataclass
class HedgeFit:
    beta: float
    intercept: float
    r2: float
    n: int
    start: str
    end: str
    trend: float = 0.0     # per session, measured from the first fit observation (t = 0)


def _align(y: pd.Series, x: pd.Series) -> pd.DataFrame:
    return pd.concat({"y": y, "x": x}, axis=1).dropna()


def fit_hedge_ratio(y: pd.Series, x: pd.Series, use_intercept: bool = True,
                    use_trend: bool = False) -> HedgeFit:
    """OLS of y on x over the given (training) observations only.

    With use_trend: y_t = a + g*t + b*x_t + e_t, t = 0, 1, ... sessions since the
    first fit observation. The trend captures deterministic drift between
    near-identical assets (e.g. different expense ratios). Out of sample the
    fitted trend is *extrapolated*, which assumes the drift rate persists.
    """
    if use_trend and not use_intercept:
        raise ValueError("A trend term requires the intercept.")
    df = _align(y, x)
    if len(df) < 3:
        raise ValueError("Need at least 3 aligned observations to fit a hedge ratio.")
    t = np.arange(len(df), dtype=float)
    cols = ([np.ones(len(df))] if use_intercept else []) + ([t] if use_trend else []) + [df["x"].to_numpy()]
    coef, *_ = np.linalg.lstsq(np.column_stack(cols), df["y"].to_numpy(), rcond=None)
    intercept = float(coef[0]) if use_intercept else 0.0
    trend = float(coef[1]) if use_trend else 0.0
    beta = float(coef[-1])
    resid = df["y"] - intercept - trend * t - beta * df["x"]
    tss = ((df["y"] - df["y"].mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / tss if tss > 0 else float("nan")
    return HedgeFit(beta, intercept, float(r2), len(df), str(df.index[0])[:10], str(df.index[-1])[:10], trend)


def compute_spread(y: pd.Series, x: pd.Series, beta: float | pd.Series,
                   intercept: float | pd.Series = 0.0, trend: float = 0.0) -> pd.Series:
    """Residual spread; `trend` is per session with t = 0 at the first aligned date."""
    df = _align(y, x)
    t = np.arange(len(df), dtype=float)
    return (df["y"] - intercept - trend * t - beta * df["x"]).rename("spread")


def rolling_hedge_ratio(y: pd.Series, x: pd.Series, window: int,
                        use_intercept: bool = True) -> pd.DataFrame:
    """Trailing-window OLS; the estimate at t uses observations (t-window, t] only."""
    df = _align(y, x)
    r = lambda s: s.rolling(window, min_periods=window)  # noqa: E731
    if use_intercept:
        var = r(df["x"]).var()
        beta = r(df["y"]).cov(df["x"]) / var.where(var > 1e-12)
        intercept = r(df["y"]).mean() - beta * r(df["x"]).mean()
    else:
        sxx = r(df["x"] * df["x"]).sum()
        beta = r(df["y"] * df["x"]).sum() / sxx.where(sxx > 1e-12)
        intercept = beta * 0.0
    return pd.DataFrame({"beta": beta, "intercept": intercept})


def kalman_hedge_ratio(y: pd.Series, x: pd.Series, delta: float = 1e-4, warmup: int = 30,
                       use_intercept: bool = True) -> pd.DataFrame:
    """Time-varying hedge ratio via a Kalman filter (random-walk coefficients).

    State theta_t = [beta_t, alpha_t] evolves as theta_t = theta_{t-1} + w_t;
    observation y_t = beta_t x_t + alpha_t + v_t. The row for date t holds the
    *prior* estimate theta_{t|t-1}, built from observations before t only, so
    spread_t = y_t - alpha - beta x_t is a genuine one-step-ahead residual.
    Initial state and noise scales come from OLS on the first `warmup`
    observations (those rows are NaN). State noise = delta/(1-delta) times the
    coefficient variance scale, so delta is dimensionless (typ. 1e-5..1e-3).
    Assumes Gaussian noise and random-walk coefficients.
    """
    df = _align(y, x)
    n = len(df)
    out = np.full((n, 2), np.nan)
    if n <= warmup + 1:
        return pd.DataFrame(out, index=df.index, columns=["beta", "intercept"])
    yw, xw = df["y"].iloc[:warmup], df["x"].iloc[:warmup]
    fit = fit_hedge_ratio(yw, xw, use_intercept)
    R = max(float(np.var(yw - fit.intercept - fit.beta * xw, ddof=2)), 1e-12)
    xv = max(float(np.var(xw)), 1e-12)
    k = 2 if use_intercept else 1
    theta = np.array([fit.beta, fit.intercept][:k])
    scale = np.array([R / xv, R][:k])
    Q = np.diag(delta / (1 - delta) * scale)
    P = np.diag(scale)
    yy, xx = df["y"].to_numpy(), df["x"].to_numpy()
    for t in range(warmup, n):
        P = P + Q                                    # predict
        out[t, :k] = theta                           # prior: data before t only
        F = np.array([xx[t], 1.0][:k])
        K = P @ F / (F @ P @ F + R)
        theta = theta + K * (yy[t] - F @ theta)      # update with y_t
        P = P - np.outer(K, F) @ P
    if not use_intercept:
        out[warmup:, 1] = 0.0
    return pd.DataFrame(out, index=df.index, columns=["beta", "intercept"])


def rolling_zscore(spread: pd.Series, window: int) -> pd.Series:
    """z_t = (s_t - mean(s_{t-w+1..t})) / std(s_{t-w+1..t}).

    Uses only data up to and including t (known at the close of t). Returns
    NaN until a full window exists or when the window has ~zero variance.
    """
    roll = spread.rolling(window, min_periods=window)
    mean, std = roll.mean(), roll.std(ddof=1)
    tol = 1e-10 * np.maximum(1.0, mean.abs())
    return ((spread - mean) / std.where(std > tol)).rename("z")


@dataclass
class HalfLife:
    value: float | None        # sessions; None when not meaningful
    b: float                   # AR slope in  ds_t = a + b*s_{t-1} + e
    pvalue: float
    valid: bool
    reason: str


def estimate_half_life(spread: pd.Series, min_obs: int = 30) -> HalfLife:
    """Mean-reversion half-life from  ds_t = a + b*s_{t-1} + e_t.

    s reverts geometrically at rate (1+b) per session, so the gap halves after
    h = -ln 2 / ln(1+b). Only valid for -1 < b < 0; b >= 0 means no mean
    reversion. Under the null b = 0 the t-statistic of b follows the
    Dickey-Fuller (not Student-t) distribution, so significance uses the
    MacKinnon p-value of the same regression (ADF with zero lags).
    """
    from statsmodels.tsa.stattools import adfuller

    s = spread.dropna()
    if len(s) < min_obs:
        return HalfLife(None, float("nan"), float("nan"), False, "insufficient data")
    ds, lag = s.diff().iloc[1:], s.shift(1).iloc[1:]
    res = sm.OLS(ds.to_numpy(), sm.add_constant(lag.to_numpy())).fit()
    b = float(res.params[1])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = float(adfuller(s.to_numpy(), maxlag=0, regression="c", autolag=None)[1])
    if not np.isfinite(b) or b >= 0:
        return HalfLife(None, b, p, False, "no mean reversion (b >= 0)")
    if b <= -1:
        return HalfLife(None, b, p, False, "overshooting dynamics (b <= -1)")
    hl = -np.log(2) / np.log1p(b)
    reason = "ok" if p < 0.05 else "slope not significant at 5%"
    return HalfLife(float(hl), b, p, p < 0.05, reason)


@dataclass
class OUParams:
    theta: float      # mean-reversion speed per session
    mu: float         # long-run mean
    sigma: float      # diffusion volatility per sqrt(session)
    sigma_eq: float   # stationary std of the spread = sigma / sqrt(2 theta)
    half_life: float
    valid: bool


def fit_ou(spread: pd.Series) -> OUParams:
    """Ornstein-Uhlenbeck  ds = theta (mu - s) dt + sigma dW  via exact AR(1) mapping.

    s_t = c + phi s_{t-1} + e,  phi = exp(-theta),  mu = c/(1-phi),
    sigma_eq = std(e)/sqrt(1-phi^2). Assumes constant parameters and Gaussian
    shocks - real spreads have regime shifts and fat tails.
    """
    s = spread.dropna()
    nan = float("nan")
    if len(s) < 30:
        return OUParams(nan, nan, nan, nan, nan, False)
    res = sm.OLS(s.iloc[1:].to_numpy(), sm.add_constant(s.iloc[:-1].to_numpy())).fit()
    c, phi = float(res.params[0]), float(res.params[1])
    if not 0 < phi < 1:
        return OUParams(nan, nan, nan, nan, nan, False)
    theta = -np.log(phi)
    eps_sd = float(np.std(res.resid, ddof=2))
    sigma_eq = eps_sd / np.sqrt(1 - phi ** 2)
    return OUParams(theta, c / (1 - phi), sigma_eq * np.sqrt(2 * theta), sigma_eq,
                    float(np.log(2) / theta), True)
