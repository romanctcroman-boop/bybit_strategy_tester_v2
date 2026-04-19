"""
Live Data Provider — данные из Bybit (REST/cache) для paper и live.

Использует SmartKlineService: кэш RAM → БД → API.
"""

from datetime import datetime

import pandas as pd

from backend.services.unified_trading.interfaces import DataProvider


class LiveDataProvider(DataProvider):
    """
    Провайдер live данных (Bybit REST + SmartKlineService).

    Для paper и live trading: актуальные свечи из кэша/API.
    """

    def __init__(self, force_fresh: bool = False):
        """
        Args:
            force_fresh: Всегда запрашивать свежие данные из API.
        """
        self.force_fresh = force_fresh

    def _get_service(self):
        """Ленивая инициализация SmartKlineService."""
        from backend.services.smart_kline_service import SMART_KLINE_SERVICE

        return SMART_KLINE_SERVICE

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """OHLCV из SmartKlineService (кэш/API)."""
        svc = self._get_service()
        candles = svc.get_candles(
            symbol=symbol,
            interval=interval,
            limit=limit,
            force_fresh=self.force_fresh,
        )

        if not candles:
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(
            [
                {
                    "open_time": c.get("open_time", 0),
                    "open": float(c.get("open", 0) or 0),
                    "high": float(c.get("high", 0) or 0),
                    "low": float(c.get("low", 0) or 0),
                    "close": float(c.get("close", 0) or 0),
                    "volume": float(c.get("volume", 0) or 0),
                }
                for c in candles
            ]
        )
        return df

    def get_current_price(self, symbol: str) -> float:
        """Последняя цена (close последней свечи)."""
        df = self.get_klines(symbol, "1", limit=1)
        if df.empty or "close" not in df.columns:
            return 0.0
        return float(df["close"].iloc[-1])
