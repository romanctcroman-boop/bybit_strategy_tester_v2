import json

import pytest

from backend.services.bybit_ws_manager import BybitWsManager


class FakeRedis:
    def __init__(self):
        self.published = []

    async def publish(self, channel, data):
        self.published.append((channel, data))


@pytest.mark.asyncio
async def test_handle_trade_and_kline_normalization():
    r = FakeRedis()
    m = BybitWsManager(redis=r, channel_ticks="bybit:ticks", channel_klines="bybit:klines")

    trade_msg = json.dumps(
        {
            "topic": "publicTrade.BTCUSDT",
            "data": [
                {
                    "T": 1700000000000,
                    "p": "100.0",
                    "v": "0.5",
                    "S": "Buy",
                }
            ],
        }
    )
    await m._handle_message(trade_msg)

    kline_msg = json.dumps(
        {
            "topic": "kline.1.BTCUSDT",
            "data": [
                {
                    "start": 1700000000000,
                    "open": "100",
                    "high": "110",
                    "low": "90",
                    "close": "105",
                    "volume": "123",
                    "turnover": "456",
                }
            ],
        }
    )
    await m._handle_message(kline_msg)

    # Two publishes: one trade, one kline
    assert len(r.published) == 2

    chan1, data1 = r.published[0]
    assert chan1 == "bybit:ticks"
    d1 = json.loads(data1)
    assert d1["v"] == 1
    assert d1["type"] == "trade"
    assert d1["symbol"] == "BTCUSDT"
    assert d1["price"] == 100.0
    assert d1["qty"] == 0.5
    assert d1["side"] == "buy"

    chan2, data2 = r.published[1]
    assert chan2 == "bybit:klines"
    d2 = json.loads(data2)
    assert d2["v"] == 1
    assert d2["type"] == "kline"
    assert d2["symbol"] == "BTCUSDT"
    assert d2["interval"] == "1"
    assert d2["open_time"] == 1700000000000
    assert d2["high"] == 110.0
    assert d2["turnover"] == 456.0
