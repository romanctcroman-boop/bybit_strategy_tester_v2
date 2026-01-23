"""
🏗️ UNIFIED BACKTEST ENGINE INTERFACES
Общие интерфейсы для всех движков бэктестинга.
Обеспечивает независимость и сравнимость результатов.

Архитектура:
- BacktestInput: унифицированный вход для всех движков
- BacktestOutput: унифицированный выход для сравнения точности
- BaseBacktestEngine: абстрактный базовый класс
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import numpy as np
import pandas as pd
from datetime import datetime


class TradeDirection(Enum):
    """Направление торговли"""

    LONG = "long"
    SHORT = "short"
    BOTH = "both"


class ExitReason(Enum):
    """Причина закрытия позиции"""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    SIGNAL = "signal"
    END_OF_DATA = "end_of_data"
    MAX_DRAWDOWN = "max_drawdown"


@dataclass
class TradeRecord:
    """Унифицированная запись о сделке"""

    entry_time: datetime
    exit_time: datetime
    direction: str  # "long" или "short"
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fees: float
    exit_reason: ExitReason
    duration_bars: int

    # Bar Magnifier данные (опционально)
    intrabar_sl_hit: bool = False
    intrabar_tp_hit: bool = False
    intrabar_exit_price: Optional[float] = None

    # MFE/MAE (Maximum Favorable/Adverse Excursion)
    mfe: float = 0.0  # Максимальная прибыль во время сделки
    mae: float = 0.0  # Максимальный убыток во время сделки


@dataclass
class BacktestInput:
    """
    Унифицированный вход для всех движков.
    Все движки получают ОДИНАКОВЫЕ данные.
    """

    # === РЫНОЧНЫЕ ДАННЫЕ ===
    candles: pd.DataFrame  # Основной таймфрейм (OHLCV)
    candles_1m: Optional[pd.DataFrame] = None  # 1-минутные для Bar Magnifier

    # === СИГНАЛЫ ===
    long_entries: np.ndarray = None  # bool array
    long_exits: np.ndarray = None  # bool array
    short_entries: np.ndarray = None  # bool array
    short_exits: np.ndarray = None  # bool array

    # === КОНФИГУРАЦИЯ ===
    symbol: str = "BTCUSDT"
    interval: str = "60"
    initial_capital: float = 10000.0
    position_size: float = (
        0.10  # 10% от капитала (используется если use_fixed_amount=False)
    )
    use_fixed_amount: bool = (
        False  # True = использовать fixed_amount вместо position_size
    )
    fixed_amount: float = 0.0  # Фиксированная сумма в USDT (как в TradingView)
    leverage: int = 10

    # === РИСК-МЕНЕДЖМЕНТ ===
    stop_loss: float = 0.02  # 2%
    take_profit: float = 0.03  # 3%
    direction: TradeDirection = TradeDirection.BOTH

    # === ИЗДЕРЖКИ ===
    taker_fee: float = 0.001  # 0.1%
    maker_fee: float = 0.0006  # 0.06%
    slippage: float = 0.0005  # 0.05%

    # === ОПЦИИ ===
    use_bar_magnifier: bool = True  # Использовать 1m данные для SL/TP
    max_drawdown_limit: float = 0.0  # Лимит просадки (0 = без лимита)
    pyramiding: int = 1  # Макс. позиций одновременно (0 или 1 = отключено)
    close_entries_rule: str = "ALL"  # Правило закрытия: "ALL", "FIFO", "LIFO"

    def validate(self) -> Tuple[bool, List[str]]:
        """Валидация входных данных"""
        errors = []

        if self.candles is None or len(self.candles) == 0:
            errors.append("Candles DataFrame пуст или None")

        if self.use_bar_magnifier and self.candles_1m is None:
            errors.append("Bar Magnifier включен, но 1m данные не предоставлены")

        if self.stop_loss < 0 or self.stop_loss > 1:
            errors.append(f"stop_loss должен быть 0-1, получено: {self.stop_loss}")

        if self.take_profit < 0 or self.take_profit > 1:
            errors.append(f"take_profit должен быть 0-1, получено: {self.take_profit}")

        if self.position_size <= 0 or self.position_size > 1:
            errors.append(
                f"position_size должен быть 0-1, получено: {self.position_size}"
            )

        return len(errors) == 0, errors


@dataclass
class BacktestMetrics:
    """
    Унифицированные метрики для сравнения движков.
    Все движки возвращают ОДИНАКОВУЮ структуру.
    """

    # === ОСНОВНЫЕ МЕТРИКИ ===
    net_profit: float = 0.0
    total_return: float = 0.0  # в процентах
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # === ПРОСАДКА ===
    max_drawdown: float = 0.0  # в процентах
    max_drawdown_duration: int = 0  # в барах
    avg_drawdown: float = 0.0

    # === РИСК-МЕТРИКИ ===
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # === СТАТИСТИКА СДЕЛОК ===
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0  # 0-1
    profit_factor: float = 0.0

    # === СРЕДНИЕ ===
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    # === LONG/SHORT РАЗБИВКА ===
    long_trades: int = 0
    long_winning_trades: int = 0
    long_losing_trades: int = 0
    short_trades: int = 0
    short_winning_trades: int = 0
    short_losing_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_profit: float = 0.0
    short_profit: float = 0.0
    long_gross_profit: float = 0.0
    long_gross_loss: float = 0.0
    short_gross_profit: float = 0.0
    short_gross_loss: float = 0.0
    long_profit_factor: float = 0.0
    short_profit_factor: float = 0.0
    long_avg_win: float = 0.0
    long_avg_loss: float = 0.0
    short_avg_win: float = 0.0
    short_avg_loss: float = 0.0

    # === ВРЕМЯ ===
    avg_trade_duration: float = 0.0  # в барах
    avg_winning_duration: float = 0.0
    avg_losing_duration: float = 0.0

    # === ДОПОЛНИТЕЛЬНЫЕ ===
    expectancy: float = 0.0  # Математическое ожидание
    recovery_factor: float = 0.0
    payoff_ratio: float = 0.0  # avg_win / abs(avg_loss)

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сериализации"""
        return {
            "net_profit": round(self.net_profit, 2),
            "total_return": round(self.total_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "expectancy": round(self.expectancy, 2),
        }


@dataclass
class BacktestOutput:
    """
    Унифицированный выход для всех движков.
    Содержит метрики, сделки и equity curve.
    """

    # === МЕТРИКИ ===
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)

    # === СДЕЛКИ ===
    trades: List[TradeRecord] = field(default_factory=list)

    # === EQUITY CURVE ===
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    timestamps: np.ndarray = field(default_factory=lambda: np.array([]))

    # === МЕТА-ИНФОРМАЦИЯ ===
    engine_name: str = ""
    execution_time: float = 0.0  # секунды
    bars_processed: int = 0
    bar_magnifier_used: bool = False

    # === ВАЛИДАЦИЯ ===
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)


class BaseBacktestEngine(ABC):
    """
    Абстрактный базовый класс для всех движков.
    Определяет общий интерфейс.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Имя движка"""
        pass

    @property
    @abstractmethod
    def supports_bar_magnifier(self) -> bool:
        """Поддерживает ли Bar Magnifier"""
        pass

    @property
    @abstractmethod
    def supports_parallel(self) -> bool:
        """Поддерживает ли параллельную оптимизацию"""
        pass

    @abstractmethod
    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """
        Запуск бэктеста.

        Args:
            input_data: Унифицированные входные данные

        Returns:
            BacktestOutput: Унифицированный результат
        """
        pass

    @abstractmethod
    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: Dict[str, List[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> List[Tuple[Dict[str, Any], BacktestOutput]]:
        """
        Оптимизация параметров.

        Args:
            input_data: Базовые входные данные
            param_ranges: Диапазоны параметров для оптимизации
            metric: Метрика для оптимизации
            top_n: Количество лучших результатов

        Returns:
            List of (params, result) tuples
        """
        pass

    def validate_input(self, input_data: BacktestInput) -> Tuple[bool, List[str]]:
        """Валидация входных данных"""
        return input_data.validate()


class EngineComparator:
    """
    Сравнение результатов разных движков.
    Использует Fallback как эталон.
    """

    def __init__(self, reference_engine: BaseBacktestEngine):
        self.reference = reference_engine
        self.engines: List[BaseBacktestEngine] = []

    def add_engine(self, engine: BaseBacktestEngine):
        """Добавить движок для сравнения"""
        self.engines.append(engine)

    def compare(self, input_data: BacktestInput) -> Dict[str, Any]:
        """
        Сравнить результаты всех движков.

        Returns:
            Словарь с результатами сравнения
        """
        # Запуск эталона
        reference_result = self.reference.run(input_data)

        comparison = {
            "reference": {
                "engine": self.reference.name,
                "metrics": reference_result.metrics.to_dict(),
                "execution_time": reference_result.execution_time,
            },
            "comparisons": [],
        }

        # Сравнение с другими движками
        for engine in self.engines:
            result = engine.run(input_data)

            drift = self._calculate_drift(reference_result.metrics, result.metrics)

            comparison["comparisons"].append(
                {
                    "engine": engine.name,
                    "metrics": result.metrics.to_dict(),
                    "execution_time": result.execution_time,
                    "speedup": reference_result.execution_time / result.execution_time
                    if result.execution_time > 0
                    else 0,
                    "drift": drift,
                    "is_accurate": drift["max_drift"] < 0.01,  # < 1% drift
                }
            )

        return comparison

    def _calculate_drift(
        self, ref: BacktestMetrics, test: BacktestMetrics
    ) -> Dict[str, float]:
        """Расчёт отклонения от эталона"""

        def safe_pct_diff(a, b):
            if a == 0:
                return 0 if b == 0 else 1.0
            return abs(a - b) / abs(a)

        drifts = {
            "net_profit_drift": safe_pct_diff(ref.net_profit, test.net_profit),
            "sharpe_drift": safe_pct_diff(ref.sharpe_ratio, test.sharpe_ratio),
            "return_drift": safe_pct_diff(ref.total_return, test.total_return),
            "drawdown_drift": safe_pct_diff(ref.max_drawdown, test.max_drawdown),
            "trades_drift": safe_pct_diff(ref.total_trades, test.total_trades),
            "win_rate_drift": safe_pct_diff(ref.win_rate, test.win_rate),
        }

        drifts["max_drift"] = max(drifts.values())
        drifts["avg_drift"] = sum(drifts.values()) / len(drifts)

        return drifts


# ============================================================================
# FACTORY для создания движков
# ============================================================================


def get_engine(
    engine_type: str = "fallback", pyramiding: int = 1
) -> BaseBacktestEngine:
    """
    Фабрика для создания движков.

    Args:
        engine_type: "fallback", "fallback_v3", "numba", "gpu"
        pyramiding: Если > 1, автоматически использует FallbackEngineV3

    Returns:
        Инстанс движка
    """
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
    from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
    from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
    from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2

    # Если включён пирамидинг (> 1), используем FallbackEngineV3
    # который поддерживает множественные позиции
    if pyramiding > 1:
        return FallbackEngineV3()

    engines = {
        "fallback": FallbackEngineV2,
        "fallback_v3": FallbackEngineV3,
        "numba": NumbaEngineV2,
        "gpu": GPUEngineV2,
    }

    if engine_type not in engines:
        raise ValueError(
            f"Unknown engine type: {engine_type}. Available: {list(engines.keys())}"
        )

    return engines[engine_type]()


def get_engine_for_config(config: BacktestInput) -> BaseBacktestEngine:
    """
    Выбор оптимального движка на основе конфигурации бэктеста.

    Автоматически выбирает FallbackEngineV3 если нужен пирамидинг.

    Args:
        config: Конфигурация бэктеста

    Returns:
        Оптимальный движок для данной конфигурации
    """
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
    from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
    from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

    pyramiding = getattr(config, "pyramiding", 1)

    # Пирамидинг > 1 требует FallbackEngineV3
    if pyramiding > 1:
        return FallbackEngineV3()

    # Для обычных случаев - пробуем Numba, потом Fallback
    try:
        engine = NumbaEngineV2()
        return engine
    except Exception:
        return FallbackEngineV2()
