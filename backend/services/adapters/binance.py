"""Thin Binance adapter (spot & futures as needed).

Behavior:
 - If `python-binance` is installed, it will be used for API calls.
 - Otherwise, the adapter uses public REST endpoints via `requests` for klines and ping.
"""

import logging

import requests

logger = logging.getLogger(__name__)

try:
    from binance.client import Client as BinanceClient  # type: ignore

    _HAS_BINANCE = True
except Exception:
    BinanceClient = None
    _HAS_BINANCE = False


class BinanceAdapter:
    BASE = "https://api.binance.com"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: int = 10,
    ):
        self.timeout = timeout
        if _HAS_BINANCE and api_key and api_secret:
            try:
                self._client = BinanceClient(api_key, api_secret)
            except Exception:
                self._client = None
        else:
            self._client = None

    def ping(self) -> bool:
        if self._client:
            try:
                self._client.ping()
                return True
            except Exception:
                return False
        try:
            r = requests.get(self.BASE + "/api/v3/ping", timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def get_klines(
        self, symbol: str, interval: str = "1m", limit: int = 500
    ) -> list[dict]:
        # Using /api/v3/klines for spot
        if self._client:
            data = self._client.get_klines(
                symbol=symbol, interval=interval, limit=limit
            )
            return [self._normalize_kline_row(d) for d in data]

        url = self.BASE + "/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return [self._normalize_kline_row(d) for d in data]

    def _normalize_kline_row(self, row: list) -> dict:
        # Binance returns list-based rows: [Open time, Open, High, Low, Close, Volume, ...]
        return {
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
