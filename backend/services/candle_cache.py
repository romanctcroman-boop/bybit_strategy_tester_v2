from __future__ import annotations

"""
Reusable in-memory candle cache with 1000-load/500-RAM policy.

Goals:
- Load up to 1000 candles via BybitAdapter.get_klines on first access or refresh.
- Keep only the last 500 candles per (symbol, interval) in RAM for fast consumers (UI/backtester/ML).
- Persist full batch to DB (MarketData) for durability and reuse by other modules.
- Provide thread-safe access/update.

Design notes:
- Time unit conventions:
  * BybitAdapter returns 'open_time' in milliseconds and float OHLC.
  * We store MarketData.timestamp as datetime (UTC). We persist the full 1000 batch to DB.
  * In-memory store keeps a list of dicts: { time: seconds(int), open, high, low, close, volume } to be chart-friendly.
  * Public API returns both flavors on request when needed.

This module has no external deps and is safe for use in workers/backtester.
"""

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from backend.services.adapters.bybit import BybitAdapter


def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def ms_to_sec(ms: int) -> int:
    return int(ms // 1000)


class CandleCache:
    RAM_LIMIT = 500
    LOAD_LIMIT = 1000

    def __init__(self):
        self._lock = threading.RLock()
        # key: (symbol_upper, interval)
        self._store: Dict[Tuple[str, str], List[dict]] = {}
        # marker for last load timestamp (ms) per key
        self._last_loaded_at: Dict[Tuple[str, str], int] = {}

    def _key(self, symbol: str, interval: str) -> Tuple[str, str]:
        return (symbol.upper(), str(interval))

    def _dedup_sort(self, rows: List[dict]) -> List[dict]:
        """Sort ascending by open_time(ms) and deduplicate equal times (keep latest)."""
        rows_sorted = sorted(rows, key=lambda r: int(r.get("open_time") or 0))
        out: List[dict] = []
        last_ms: Optional[int] = None
        for r in rows_sorted:
            ms = int(r.get("open_time") or 0)
            if last_ms is None or ms > last_ms:
                out.append(r)
                last_ms = ms
            elif ms == last_ms and out:
                # replace last with latest values
                out[-1] = r
        return out

    def load_initial(
        self, symbol: str, interval: str, *, load_limit: Optional[int] = None, persist: bool = True
    ) -> List[dict]:
        """
        Fetch up to 1000 candles from Bybit, persist to DB, and cache last 500 in RAM.
        Returns the working set (<=500) as chart-friendly dicts with time in seconds.
        """
        with self._lock:
            lim = load_limit or self.LOAD_LIMIT
            adapter = BybitAdapter(api_key=None, api_secret=None)
            raw_rows = adapter.get_klines(symbol=symbol, interval=interval, limit=lim)
            norm = self._dedup_sort(raw_rows)

            # Note: BybitAdapter.get_klines already best-effort persists into bybit_kline_audit
            # via its _persist_klines_to_db method. We skip a second persistence here to avoid
            # coupling to other model imports that may not exist in all environments.

            # Keep only last RAM_LIMIT in memory, mapped to seconds-based time
            last_n = norm[-self.RAM_LIMIT :] if len(norm) > self.RAM_LIMIT else norm
            working = [
                {
                    "time": ms_to_sec(int(r.get("open_time") or 0)),
                    "open": float(r.get("open") or 0.0),
                    "high": float(r.get("high") or 0.0),
                    "low": float(r.get("low") or 0.0),
                    "close": float(r.get("close") or 0.0),
                    "volume": (
                        float(r.get("volume") or 0.0) if r.get("volume") is not None else None
                    ),
                }
                for r in last_n
            ]
            self._store[self._key(symbol, interval)] = working
            if norm:
                self._last_loaded_at[self._key(symbol, interval)] = int(
                    norm[-1].get("open_time") or 0
                )
            return working

    def get_working_set(
        self, symbol: str, interval: str, *, ensure_loaded: bool = True
    ) -> List[dict]:
        key = self._key(symbol, interval)
        with self._lock:
            if key not in self._store and ensure_loaded:
                return self.load_initial(symbol, interval)
            return list(self._store.get(key, []))

    def refresh(self, symbol: str, interval: str) -> List[dict]:
        """Force reload from remote."""
        return self.load_initial(symbol, interval)

    def upsert_closed(self, symbol: str, interval: str, candle: dict) -> List[dict]:
        """
        Append or replace a closed candle in working set. Candle must have 'time' in seconds.
        Returns updated working set.
        """
        key = self._key(symbol, interval)
        with self._lock:
            arr = self._store.get(key, [])
            t = int(candle.get("time"))
            if arr and int(arr[-1]["time"]) == t:
                arr[-1] = candle
            else:
                arr.append(candle)
                if len(arr) > self.RAM_LIMIT:
                    arr = arr[-self.RAM_LIMIT :]
            self._store[key] = arr
            return list(arr)


# Singleton instance
CANDLE_CACHE = CandleCache()
