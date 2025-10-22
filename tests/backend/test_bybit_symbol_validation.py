import importlib


def test_validate_symbol_direct_match():
    m = importlib.import_module("backend.services.adapters.bybit")
    b = m.BybitAdapter()
    # inject fake cache
    b._instruments_cache = {
        "BTCUSDT": {"symbol": "BTCUSDT", "status": "Trading", "isPreListing": False},
        "ETHUSDT": {"symbol": "ETHUSDT", "status": "Trading", "isPreListing": False},
    }
    assert b.validate_symbol("BTCUSDT") == "BTCUSDT"
    assert b.validate_symbol("btcUsdt") == "BTCUSDT"


def test_validate_symbol_add_usdt():
    m = importlib.import_module("backend.services.adapters.bybit")
    b = m.BybitAdapter()
    b._instruments_cache = {
        "BTCUSDT": {"symbol": "BTCUSDT", "status": "Trading", "isPreListing": False}
    }
    assert b.validate_symbol("BTC") == "BTCUSDT"


def test_validate_symbol_not_found():
    m = importlib.import_module("backend.services.adapters.bybit")
    b = m.BybitAdapter()
    b._instruments_cache = {}
    try:
        b.validate_symbol("NOSYMBOL")
        assert False, "Expected ValueError"
    except ValueError:
        pass
