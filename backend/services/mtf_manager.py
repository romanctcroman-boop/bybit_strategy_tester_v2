from __future__ import annotations

"""
MTF (Multi-Timeframe) Manager

Unified utilities to fetch working sets for multiple timeframes per symbol and
optionally align higher timeframes from a base timeframe using OHLCV aggregation.

This service relies on CandleCache for data access and provides a simple API for
backtester/ML modules to consume MTF inputs consistently across any trading pair.
"""

from typing import Dict, List, Optional, Iterable
from dataclasses import dataclass
from math import floor
from datetime import datetime, timezone

from backend.services.candle_cache import CANDLE_CACHE


def interval_to_minutes(interval: str) -> int:
    s = str(interval).upper()
    if s == 'D':
        return 24 * 60
    if s == 'W':
        return 7 * 24 * 60
    try:
        return int(s)  # minutes
    except Exception:
        # fallback: treat unknown as 1m
        return 1


def window_start_seconds(ts_sec: int, interval: str) -> int:
    """Return the UTC-aligned window start for a timestamp in seconds for the given interval.

    - For minute-based intervals, align to modulo minutes.
    - For D: align to 00:00:00 UTC.
    - For W: align to the start of ISO week (Monday 00:00:00 UTC).
    """
    iv = str(interval).upper()
    if iv == 'D':
        dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        aligned = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        return int(aligned.timestamp())
    if iv == 'W':
        dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
        # ISO weekday: Monday=1 ... Sunday=7
        delta_days = dt.isoweekday() - 1
        start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        aligned = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return int((aligned.timestamp()) - delta_days * 86400)
    # minute-based
    mins = interval_to_minutes(iv)
    bucket = (ts_sec // 60) // mins
    return int(bucket * mins * 60)


def aggregate_from_base(base: List[dict], target_interval: str) -> List[dict]:
    """Aggregate a list of base candles (time=seconds) to the target interval.

    Expects base to be sorted ascending by time without duplicate timestamps.
    Returns aggregated candles with time=windowStartSec.
    """
    if not base:
        return []
    out: List[dict] = []
    cur_start: Optional[int] = None
    cur: Optional[dict] = None
    for c in base:
        t = int(c['time'])
        ws = window_start_seconds(t, target_interval)
        if cur_start is None or ws != cur_start:
            # push previous
            if cur is not None:
                out.append(cur)
            # start new window
            cur_start = ws
            cur = {
                'time': ws,
                'open': float(c['open']),
                'high': float(c['high']),
                'low': float(c['low']),
                'close': float(c['close']),
                'volume': float(c.get('volume') or 0.0),
            }
        else:
            # extend window
            cur['high'] = max(cur['high'], float(c['high']))
            cur['low'] = min(cur['low'], float(c['low']))
            cur['close'] = float(c['close'])
            cur['volume'] = float(cur.get('volume') or 0.0) + float(c.get('volume') or 0.0)
    if cur is not None:
        out.append(cur)
    return out


@dataclass
class MTFResult:
    symbol: str
    intervals: List[str]
    data: Dict[str, List[dict]]  # interval -> candles (seconds, ohlc[v])


class MTFManager:
    """Fetch and align MTF working sets for any symbol.

    - get_working_sets: retrieve working sets per interval from CandleCache
    - get_aligned: resample higher frames from a base interval
    """

    def get_working_sets(self, symbol: str, intervals: Iterable[str], load_limit: int = 1000) -> MTFResult:
        ivs = [str(x) for x in intervals]
        out: Dict[str, List[dict]] = {}
        for itv in ivs:
            # use cache; load if absent
            data = CANDLE_CACHE.get_working_set(symbol, itv, ensure_loaded=False)
            if not data:
                data = CANDLE_CACHE.load_initial(symbol, itv, load_limit=load_limit, persist=True)
            # ensure ascending order and dedup (safety)
            data_sorted = sorted(data, key=lambda x: int(x['time']))
            dedup: List[dict] = []
            last_t: Optional[int] = None
            for d in data_sorted:
                t = int(d['time'])
                if last_t is None or t > last_t:
                    dedup.append(d)
                    last_t = t
                elif t == last_t:
                    dedup[-1] = d
            out[itv] = dedup
        return MTFResult(symbol=symbol.upper(), intervals=ivs, data=out)

    def get_aligned(self, symbol: str, intervals: Iterable[str], base_interval: Optional[str] = None, load_limit: int = 1000) -> MTFResult:
        ivs = sorted([str(x) for x in intervals], key=lambda v: interval_to_minutes(v))
        base = base_interval or ivs[0]
        raw = self.get_working_sets(symbol, ivs, load_limit=load_limit)
        base_set = raw.data.get(base, [])
        # ensure base sorted
        base_sorted = sorted(base_set, key=lambda x: int(x['time']))
        out: Dict[str, List[dict]] = {base: base_sorted}
        for itv in ivs:
            if itv == base:
                continue
            out[itv] = aggregate_from_base(base_sorted, itv)
        return MTFResult(symbol=raw.symbol, intervals=ivs, data=out)


# Singleton for convenience
MTF_MANAGER = MTFManager()
