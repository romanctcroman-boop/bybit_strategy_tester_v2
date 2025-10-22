"""
Minimal example test for MTF alignment: aggregate 1-minute candles into 3-minute candles.

This serves as a readable template showing how MTF_MANAGER aligns windows and aggregates
OHLCV using UTC-aligned windows (minute-based buckets).
"""
import os
import sys
import importlib

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


def test_mtf_alignment_1m_to_3m(monkeypatch):
    mtfmod = importlib.import_module('backend.services.mtf_manager')

    # 3 one-minute candles at seconds: 1000, 1060, 1120
    base_1m = [
        {'time': 1000, 'open': 10, 'high': 11, 'low': 9, 'close': 10.5, 'volume': 1},
        {'time': 1060, 'open': 10.5, 'high': 12, 'low': 10, 'close': 11.0, 'volume': 1},
        {'time': 1120, 'open': 11.0, 'high': 13, 'low': 10.5, 'close': 12.0, 'volume': 1},
    ]

    class DummyCache:
        def get_working_set(self, symbol, interval, ensure_loaded=True):
            if interval == '1':
                return base_1m
            return []
        def load_initial(self, *a, **k):
            return []

    # Replace MTF manager's cache with deterministic dummy
    monkeypatch.setattr(mtfmod, 'CANDLE_CACHE', DummyCache())

    result = mtfmod.MTF_MANAGER.get_aligned('BTCUSDT', intervals=['1', '3'], base_interval='1')

    # Base returned as-is (sorted ascending by time)
    assert result.data['1'][0]['time'] == 1000
    assert result.data['1'][-1]['time'] == 1120

    # 3-minute aggregation buckets start at 900, 1080, ... for these times
    agg_3m = result.data['3']
    assert len(agg_3m) >= 2

    first = agg_3m[0]
    # first window start (aligned to 3-minute) <= first base time
    assert first['time'] == mtfmod.window_start_seconds(1000, '3')
    # two 1m candles fall into first 3m bucket (1000 and 1060)
    assert first['open'] == 10
    assert first['high'] == 12
    assert first['low'] == 9
    assert first['close'] == 11.0
    assert first['volume'] == 2

    second = agg_3m[1]
    # third 1m candle in the next 3m bucket
    assert second['open'] == 11.0
    assert second['high'] == 13
    assert second['low'] == 10.5
    assert second['close'] == 12.0
    assert second['volume'] == 1
