import importlib
import os
import sys


def setup_module():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def test_missing_fields_list():
    m = importlib.import_module("backend.services.adapters.bybit")
    b = m.BybitAdapter()
    # list missing turnover
    sample = ["1670608800000", "17071", "17073", "17027", "17055.5", "268611"]
    parsed = b._normalize_kline_row(sample)
    assert parsed["open_time"] == 1670608800000
    assert parsed["turnover"] is None


def test_empty_strings_dict():
    m = importlib.import_module("backend.services.adapters.bybit")
    b = m.BybitAdapter()
    sample = {
        "startTime": "1670608800000",
        "openPrice": "",
        "highPrice": "17073",
        "lowPrice": "",
        "closePrice": "17055.5",
        "volume": "",
    }
    parsed = b._normalize_kline_row(sample)
    assert parsed["open"] is None
    assert parsed["low"] is None
    assert parsed["volume"] is None


def test_malformed_row():
    m = importlib.import_module("backend.services.adapters.bybit")
    b = m.BybitAdapter()
    sample = object()  # completely invalid
    parsed = b._normalize_kline_row(sample)
    assert "raw" in parsed
