"""
Unified Trading Interfaces — абстракции для Backtest / Paper / Live.

См. docs/architecture/BACKTEST_PAPER_LIVE_API.md
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class OrderResult:
    """Результат размещения ордера."""

    order_id: str
    symbol: str
    side: str  # "buy" | "sell"
    status: str  # "filled" | "partial" | "rejected" | "pending"
    filled_qty: float = 0.0
    filled_price: float = 0.0
    error: str | None = None


class DataProvider(ABC):
    """
    Абстрактный провайдер рыночных данных.

    Backtest: HistoricalDataProvider (БД).
    Paper/Live: LiveDataProvider (Bybit REST/WebSocket).
    """

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """
        OHLCV данные.

        Returns:
            DataFrame с колонками: open_time, open, high, low, close, volume
        """
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Текущая цена (для paper/live)."""
        pass


class OrderExecutorInterface(ABC):
    """
    Абстрактный исполнитель ордеров.

    Backtest/Paper: SimulatedExecutor (симуляция fills).
    Live: BybitExecutor (реальные ордера).
    """

    @abstractmethod
    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> OrderResult:
        """Разместить рыночный ордер."""
        pass

    @abstractmethod
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        reduce_only: bool = False,
        **kwargs: Any,
    ) -> OrderResult:
        """Разместить лимитный ордер."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Отменить ордер."""
        pass
