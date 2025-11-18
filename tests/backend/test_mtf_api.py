import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import importlib

from fastapi.testclient import TestClient


def _app():
    appmod = importlib.import_module("backend.api.app")
    return appmod.app


def test_mtf_endpoint_raw(monkeypatch):
    mtfmod = importlib.import_module("backend.services.mtf_manager")

    # Provide a dummy CandleCache inside mtf_manager to avoid network
    class DummyCache:
        def get_working_set(self, symbol, interval, ensure_loaded=True):
            base = [
                {"time": 1000, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
                {"time": 1060, "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0},
            ]
            return base

        def load_initial(self, *a, **k):
            return []

    monkeypatch.setattr(mtfmod, "CANDLE_CACHE", DummyCache())

    client = TestClient(_app())
    r = client.get(
        "/api/v1/marketdata/bybit/mtf",
        params={"symbol": "BTCUSDT", "intervals": "1,15", "aligned": 0},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["symbol"] == "BTCUSDT"
    assert "1" in payload["data"] and "15" in payload["data"]
    assert len(payload["data"]["1"]) == 2


def test_mtf_endpoint_aligned(monkeypatch):
    mtfmod = importlib.import_module("backend.services.mtf_manager")

    # base returns three 1m bars (180 seconds)
    class DummyCache:
        def get_working_set(self, symbol, interval, ensure_loaded=True):
            if interval == "1":
                return [
                    {"time": 1000, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
                    {"time": 1060, "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 1},
                    {"time": 1120, "open": 2.0, "high": 3.0, "low": 1.5, "close": 2.5, "volume": 1},
                ]
            return []

        def load_initial(self, *a, **k):
            return []

    monkeypatch.setattr(mtfmod, "CANDLE_CACHE", DummyCache())

    client = TestClient(_app())
    r = client.get(
        "/api/v1/marketdata/bybit/mtf",
        params={"symbol": "BTCUSDT", "intervals": "1,3", "aligned": 1, "base": "1"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert "3" in payload["data"]
    htf = payload["data"]["3"]
    assert len(htf) >= 1
    # time is window start (aligned to minute buckets); first should equal 1000 aligned to 3m
    assert htf[0]["time"] <= 1000
    # volume aggregated: first 3m bucket (start 900) includes two 1m bars => volume = 2
    assert htf[0]["volume"] == 2
