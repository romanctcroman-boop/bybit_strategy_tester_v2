"""
Historical Data Provider — данные из БД для backtest.

Использует DataService для чтения bybit_kline_audit.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd

from backend.services.unified_trading.interfaces import DataProvider

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Интервал (строка) -> длительность одного бара в миллисекундах
INTERVAL_MS = {
    "1": 60_000,
    "3": 180_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "120": 7_200_000,
    "240": 14_400_000,
    "360": 21_600_000,
    "720": 43_200_000,
    "D": 86_400_000,
    "W": 604_800_000,
    "M": 2_592_000_000,
}


class HistoricalDataProvider(DataProvider):
    """
    Провайдер исторических данных из БД.

    Для backtest: стратегия получает OHLCV через единый интерфейс DataProvider.
    """

    def __init__(
        self,
        db: "Session",
        market_type: str = "linear",
    ):
        self.db = db
        self.market_type = market_type

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """OHLCV из БД."""
        from backend.services.data_service import DataService

        data_service = DataService(self.db)

        end_time = end_time or datetime.now(UTC)
        interval_ms = INTERVAL_MS.get(str(interval), 60_000)
        start_time = end_time - timedelta(milliseconds=limit * interval_ms)

        records = data_service.get_market_data(
            symbol=symbol,
            timeframe=str(interval),
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            market_type=self.market_type,
        )

        if not records:
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(
            [
                {
                    "open_time": r.open_time,
                    "open": float(r.open_price or 0),
                    "high": float(r.high_price or 0),
                    "low": float(r.low_price or 0),
                    "close": float(r.close_price or 0),
                    "volume": float(r.volume or 0),
                }
                for r in records
            ]
        )
        return df

    def get_current_price(self, symbol: str) -> float:
        """Для backtest — последняя известная цена (из последней свечи)."""
        from backend.services.data_service import DataService

        data_service = DataService(self.db)
        candle = data_service.get_latest_candle(symbol, "1")
        if candle and candle.close_price:
            return float(candle.close_price)
        return 0.0
