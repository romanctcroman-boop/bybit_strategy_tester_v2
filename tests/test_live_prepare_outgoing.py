import json
from backend.api.routers import live


def test_prepare_outgoing_valid_candle():
    stream = 'stream:candles:BTCUSDT:1'
    data = {
        "type": "update",
        "subscription": "candles",
        "symbol": "BTCUSDT",
        "timeframe": "1",
        "candle": {
            "timestamp": 1697520000000,
            "start": 1697520000000,
            "end": 1697520060000,
            "open": "28350.50",
            "high": "28365.00",
            "low": "28340.00",
            "close": "28355.25",
            "volume": "125.345",
            "confirm": False
        }
    }

    out = live._prepare_outgoing_payload(stream, data)
    assert out is not None
    assert out['type'] == 'update'
    assert out['subscription'] == 'candles'
    assert out['symbol'] == 'BTCUSDT'


def test_prepare_outgoing_invalid_candle_missing_field():
    stream = 'stream:candles:BTCUSDT:1'
    data = {
        "type": "update",
        "subscription": "candles",
        "symbol": "BTCUSDT",
        "timeframe": "1",
        "candle": {
            # missing timestamp
            "start": 1697520000000,
            "end": 1697520060000,
            "open": "28350.50",
            "high": "28365.00",
            "low": "28340.00",
            "close": "28355.25",
            "volume": "125.345",
            "confirm": False
        }
    }

    out = live._prepare_outgoing_payload(stream, data)
    assert out is None

    err = live._build_validation_error(stream, data, "missing timestamp")
    assert isinstance(err, dict)
    assert err.get('error_code') == 'INVALID_PAYLOAD'


def test_prepare_outgoing_valid_trade():
    stream = 'stream:trades:BTCUSDT'
    data = {
        "type": "update",
        "subscription": "trades",
        "symbol": "BTCUSDT",
        "trades": [
            {
                "timestamp": 1697520000000,
                "symbol": "BTCUSDT",
                "side": "Buy",
                "price": "28355.50",
                "size": "0.125",
                "trade_id": "abc123"
            }
        ]
    }

    out = live._prepare_outgoing_payload(stream, data)
    assert out is not None
    assert out['subscription'] == 'trades'


def test_prepare_outgoing_invalid_trade_bad_side():
    stream = 'stream:trades:BTCUSDT'
    data = {
        "type": "update",
        "subscription": "trades",
        "symbol": "BTCUSDT",
        "trades": [
            {
                "timestamp": 1697520000000,
                "symbol": "BTCUSDT",
                "side": "Hold",  # invalid side
                "price": "28355.50",
                "size": "0.125",
                "trade_id": "abc123"
            }
        ]
    }

    out = live._prepare_outgoing_payload(stream, data)
    assert out is None
