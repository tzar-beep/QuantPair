"""Provider adapters and live monitor, tested against mocked HTTP (no network, no real keys)."""
import numpy as np
import pandas as pd
import pytest

from quantpair.config import StrategyConfig
from quantpair.data import providers as pv
from quantpair.data.market_data import DataFetchError
from quantpair.research.live import live_reading


class Resp:
    def __init__(self, js, status=200):
        self._js, self.status_code, self.ok, self.text = js, status, status < 400, str(js)

    def json(self):
        return self._js


@pytest.fixture
def keys(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "AKTESTKEY1234")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret5678")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(pv, "ENV_FILE", tmp_path / ".env")


def test_alpaca_bars_follow_pagination(keys, monkeypatch):
    pages = [
        {"bars": {"AAA": [{"t": "2024-01-02T05:00:00Z", "c": 10.0}], "BBB": [{"t": "2024-01-02T05:00:00Z", "c": 20.0}]},
         "next_page_token": "p2"},
        {"bars": {"AAA": [{"t": "2024-01-03T05:00:00Z", "c": 11.0}]}, "next_page_token": None},
    ]
    seen = []

    def fake_get(url, headers=None, params=None, timeout=None):
        seen.append(dict(params))
        assert headers["APCA-API-KEY-ID"] == "AKTESTKEY1234" and params["adjustment"] == "all"
        return Resp(pages[len(seen) - 1])

    monkeypatch.setattr(pv.requests, "get", fake_get)
    d = pv.fetch_prices_alpaca(["aaa", "BBB"], "2024-01-01")
    assert d.source == "alpaca" and list(d.prices.columns) == ["AAA", "BBB"]
    assert d.prices.loc["2024-01-03", "AAA"] == 11.0 and np.isnan(d.prices.loc["2024-01-03", "BBB"])
    assert seen[1]["page_token"] == "p2"


def test_auth_error_is_reported_not_swallowed(keys, monkeypatch):
    monkeypatch.setattr(pv.requests, "get", lambda *a, **k: Resp({"message": "forbidden"}, 403))
    with pytest.raises(DataFetchError, match="rejected the API key"):
        pv.fetch_prices_alpaca(["AAA"], "2024-01-01")


def test_latest_quotes_and_masking(keys, monkeypatch):
    trade = {"trades": {"SPY": {"p": 500.5, "t": "2026-10-12T14:30:00Z"}}}
    monkeypatch.setattr(pv.requests, "get", lambda *a, **k: Resp(trade))
    q = pv.latest_quotes(["spy"])
    assert q["SPY"].price == 500.5 and "alpaca" in q["SPY"].source
    st = pv.key_status()
    assert st["alpaca"]["configured"] and st["alpaca"]["key_id"] == "••••1234"
    assert "AKTESTKEY1234" not in str(st) and "secret5678" not in str(st)


def test_set_keys_persists_to_env_file(keys, tmp_path):
    pv.set_keys({"FINNHUB_API_KEY": "fh_abc"}, persist=True)
    text = (tmp_path / ".env").read_text()
    assert "FINNHUB_API_KEY=fh_abc" in text and "ALPACA_API_KEY_ID=AKTESTKEY1234" in text
    with pytest.raises(ValueError):
        pv.set_keys({"NOT_A_KEY": "x"})


def test_no_keys_gives_clear_error(monkeypatch):
    for k in pv.KEYS:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(DataFetchError, match="No live-data key"):
        pv.latest_quotes(["SPY"])


def test_live_reading_uses_history_only(prices):
    cfg = StrategyConfig(lookback=20)
    fit = (prices.index[0], prices.index[399])
    r = live_reading(prices, "Y", "X", float(prices["Y"].iloc[-1]), float(prices["X"].iloc[-1]), cfg, fit)
    spreads = prices["Y"] - r.intercept - r.beta * prices["X"]
    hist = spreads.iloc[-20:]
    assert np.isclose(r.mean, hist.mean()) and np.isclose(r.std, hist.std())
    py, px = float(prices["Y"].iloc[-1]), float(prices["X"].iloc[-1])
    shocked = live_reading(prices, "Y", "X", py + 10 * r.std, px, cfg, fit)
    assert shocked.z > cfg.entry_z and shocked.signal in ("short spread", "beyond stop")
    assert isinstance(pd.Timestamp(r.history_end), pd.Timestamp)
