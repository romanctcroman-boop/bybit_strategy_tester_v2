import importlib
import os
import sys
from datetime import datetime, timezone


def setup_module():
    # ensure project root on path for test discovery
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def test_normalize_list_row():
    m = importlib.import_module('backend.services.adapters.bybit')
    b = m.BybitAdapter()
    sample = ['1670608800000', '17071', '17073', '17027', '17055.5', '268611', '15.74462667']
    parsed = b._normalize_kline_row(sample)
    assert parsed['raw'] == sample
    assert parsed['open_time'] == 1670608800000
    assert parsed['open_time_dt'] == datetime.fromtimestamp(1670608800000 / 1000.0, tz=timezone.utc)
    assert parsed['open'] == 17071.0
    assert parsed['high'] == 17073.0
    assert parsed['low'] == 17027.0
    assert parsed['close'] == 17055.5
    assert parsed['volume'] == 268611.0
    assert parsed['turnover'] == 15.74462667


def test_normalize_dict_row():
    m = importlib.import_module('backend.services.adapters.bybit')
    b = m.BybitAdapter()
    sample = {
        'startTime': '1670608800000',
        'openPrice': '17071',
        'highPrice': '17073',
        'lowPrice': '17027',
        'closePrice': '17055.5',
        'volume': '268611',
        'turnover': '15.74462667'
    }
    parsed = b._normalize_kline_row(sample)
    assert parsed['raw'] == sample
    assert parsed['open_time'] == 1670608800000
    assert parsed['open_time_dt'] == datetime.fromtimestamp(1670608800000 / 1000.0, tz=timezone.utc)
    assert parsed['open'] == 17071.0
    assert parsed['high'] == 17073.0
    assert parsed['low'] == 17027.0
    assert parsed['close'] == 17055.5
    assert parsed['volume'] == 268611.0
    assert parsed['turnover'] == 15.74462667
