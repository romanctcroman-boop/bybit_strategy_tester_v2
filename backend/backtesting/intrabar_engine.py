"""
Intrabar Engine: Universal Bar Magnifier

Генерирует псевдотики из 1m баров для любого старшего таймфрейма.
Это позволяет точно определять порядок срабатывания SL/TP/Entry.

Архитектура:
    BarRunner(T) ──► IntrabarEngine(1m) ──► BrokerEmulator

Режимы генерации тиков внутри 1m бара:
    - O-H-L-C: Open → High → Low → Close (консервативный для short)
    - O-L-H-C: Open → Low → High → Close (консервативный для long)
    - O-HL-C:  Open → (H,L по близости к O) → Close (эвристика TradingView)
    - subticks: O-H-L-C с N промежуточных интерполированных точек
"""

import logging
from collections.abc import Generator
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OHLCPath(str, Enum):
    """Порядок обхода OHLC внутри 1m бара."""

    O_H_L_C = "O-H-L-C"  # Open → High → Low → Close (консервативный для short)
    O_L_H_C = "O-L-H-C"  # Open → Low → High → Close (консервативный для long)
    O_HL_HEURISTIC = "O-HL-heuristic"  # TradingView-style: по близости O к H/L
    CONSERVATIVE_LONG = "conservative_long"  # Сначала Low (worst), потом High
    CONSERVATIVE_SHORT = "conservative_short"  # Сначала High (worst), потом Low


@dataclass
class IntrabarConfig:
    """Конфигурация генерации внутрибарных тиков."""

    # Режим пути внутри 1m бара
    ohlc_path: OHLCPath = OHLCPath.O_HL_HEURISTIC

    # Количество промежуточных тиков между O-H-L-C (0 = только 4 точки)
    subticks_per_segment: int = 0

    # Как распределять объём по тикам
    volume_distribution: str = "proportional"  # "equal", "proportional", "none"

    # Пустые минуты (нет 1m данных)
    empty_minute_behavior: str = "last_close"  # "last_close", "skip", "interpolate"


@dataclass
class PseudoTick:
    """Псевдотик, сгенерированный из 1m бара."""

    timestamp_ms: int  # Время тика (миллисекунды)
    price: float  # Цена
    volume: float = 0.0  # Объём (опционально)
    tick_type: str = "price"  # "open", "high", "low", "close", "interpolated"
    bar_index: int = 0  # Индекс 1m бара в текущем баре T
    source_bar_time: int = 0  # Время исходного 1m бара


@dataclass
class IntrabarData:
    """Данные для одного бара старшего ТФ."""

    bar_start_ms: int  # Начало бара T
    bar_end_ms: int  # Конец бара T
    m1_bars: pd.DataFrame  # 1m бары внутри этого бара T
    ticks: list[PseudoTick] = field(default_factory=list)


class IntrabarEngine:
    """
    Движок генерации псевдотиков из 1m баров.

    Использование:
        engine = IntrabarEngine(config)
        engine.load_m1_data(m1_dataframe)

        for bar_T in bars_T:
            for tick in engine.generate_ticks(bar_T):
                broker.process_tick(tick)
    """

    def __init__(self, config: IntrabarConfig = None):
        self.config = config or IntrabarConfig()
        self.m1_data: pd.DataFrame | None = None
        self.m1_timestamps: np.ndarray | None = None

        # Кэш для быстрого поиска 1m баров
        self._m1_index: dict[int, int] = {}  # timestamp_ms -> index

        logger.info(
            f"[INTRABAR_ENGINE] Initialized with path={self.config.ohlc_path.value}, "
            f"subticks={self.config.subticks_per_segment}"
        )

    def load_m1_data(self, m1_data: pd.DataFrame) -> None:
        """
        Загрузить 1m данные.

        Args:
            m1_data: DataFrame с колонками: open_time, open, high, low, close, volume
        """
        self.m1_data = m1_data.copy()

        # Нормализация имён колонок
        col_map = {
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
        self.m1_data.rename(columns=col_map, inplace=True)

        # Индекс для быстрого поиска
        self.m1_timestamps = self.m1_data["open_time"].values
        self._m1_index = {ts: i for i, ts in enumerate(self.m1_timestamps)}

        logger.info(f"[INTRABAR_ENGINE] Loaded {len(m1_data)} 1m bars")

    def get_m1_bars_for_bar_T(self, bar_start_ms: int, bar_end_ms: int) -> pd.DataFrame:
        """
        Получить 1m бары, входящие в бар старшего ТФ.

        Args:
            bar_start_ms: Начало бара T (миллисекунды)
            bar_end_ms: Конец бара T (миллисекунды)

        Returns:
            DataFrame с 1m барами
        """
        if self.m1_data is None or len(self.m1_data) == 0:
            return pd.DataFrame()

        mask = (self.m1_timestamps >= bar_start_ms) & (self.m1_timestamps < bar_end_ms)
        return self.m1_data.iloc[mask]

    def generate_ticks_for_m1_bar(
        self, m1_bar: pd.Series, bar_index: int
    ) -> Generator[PseudoTick]:
        """
        Сгенерировать последовательность псевдотиков из одного 1m бара.

        Args:
            m1_bar: Series с O, H, L, C, volume
            bar_index: Индекс 1m бара внутри бара T

        Yields:
            PseudoTick для каждой точки пути
        """
        o = float(m1_bar["open"])
        h = float(m1_bar["high"])
        low_val = float(m1_bar["low"])
        c = float(m1_bar["close"])
        v = float(m1_bar.get("volume", 0))
        ts = int(m1_bar["open_time"])

        # Определяем порядок обхода
        path = self._get_ohlc_path(o, h, low_val, c)

        # Распределение объёма
        volumes = self._distribute_volume(v, len(path))

        # Генерируем тики
        for i, (price, tick_type) in enumerate(path):
            # Время тика (распределяем по минуте)
            tick_offset = (i / len(path)) * 60000  # мс внутри минуты
            tick_time = ts + int(tick_offset)

            yield PseudoTick(
                timestamp_ms=tick_time,
                price=price,
                volume=volumes[i],
                tick_type=tick_type,
                bar_index=bar_index,
                source_bar_time=ts,
            )

            # Если нужны промежуточные тики (subticks)
            if self.config.subticks_per_segment > 0 and i < len(path) - 1:
                next_price = path[i + 1][0]
                yield from self._generate_subticks(
                    price, next_price, tick_time, ts, bar_index
                )

    def _get_ohlc_path(
        self, o: float, h: float, low_val: float, c: float
    ) -> list[tuple[float, str]]:
        """
        Определить порядок обхода OHLC.

        Returns:
            List of (price, type) tuples
        """
        if self.config.ohlc_path == OHLCPath.O_H_L_C:
            return [(o, "open"), (h, "high"), (low_val, "low"), (c, "close")]

        elif self.config.ohlc_path == OHLCPath.O_L_H_C:
            return [(o, "open"), (low_val, "low"), (h, "high"), (c, "close")]

        elif self.config.ohlc_path == OHLCPath.CONSERVATIVE_LONG:
            # Для лонга: сначала worst (low), потом best (high)
            return [(o, "open"), (low_val, "low"), (h, "high"), (c, "close")]

        elif self.config.ohlc_path == OHLCPath.CONSERVATIVE_SHORT:
            # Для шорта: сначала worst (high), потом best (low)
            return [(o, "open"), (h, "high"), (low_val, "low"), (c, "close")]

        else:  # O_HL_HEURISTIC - TradingView style
            # Если Open ближе к High → сначала High, потом Low
            if abs(o - h) < abs(o - low_val):
                return [(o, "open"), (h, "high"), (low_val, "low"), (c, "close")]
            else:
                return [(o, "open"), (low_val, "low"), (h, "high"), (c, "close")]

    def _generate_subticks(
        self,
        price_from: float,
        price_to: float,
        time_from: int,
        source_bar_time: int,
        bar_index: int,
    ) -> Generator[PseudoTick]:
        """Генерировать промежуточные тики между двумя точками."""
        n = self.config.subticks_per_segment
        for i in range(1, n + 1):
            ratio = i / (n + 1)
            price = price_from + (price_to - price_from) * ratio
            tick_time = time_from + int(ratio * 15000)  # ~15 сек между OHLC точками

            yield PseudoTick(
                timestamp_ms=tick_time,
                price=price,
                volume=0.0,
                tick_type="interpolated",
                bar_index=bar_index,
                source_bar_time=source_bar_time,
            )

    def _distribute_volume(self, total_volume: float, n_ticks: int) -> list[float]:
        """Распределить объём по тикам."""
        if self.config.volume_distribution == "equal":
            return [total_volume / n_ticks] * n_ticks
        elif self.config.volume_distribution == "proportional":
            # O: 10%, H: 30%, L: 30%, C: 30%
            weights = [0.1, 0.3, 0.3, 0.3]
            if n_ticks != 4:
                weights = [1.0 / n_ticks] * n_ticks
            return [total_volume * w for w in weights[:n_ticks]]
        else:
            return [0.0] * n_ticks

    def generate_ticks(
        self, bar_start_ms: int, bar_end_ms: int
    ) -> Generator[PseudoTick]:
        """
        Генерировать все псевдотики для бара старшего ТФ.

        Args:
            bar_start_ms: Начало бара T
            bar_end_ms: Конец бара T

        Yields:
            PseudoTick в хронологическом порядке
        """
        m1_bars = self.get_m1_bars_for_bar_T(bar_start_ms, bar_end_ms)

        if len(m1_bars) == 0:
            # Нет 1m данных - возвращаем пустой генератор
            logger.debug(
                f"[INTRABAR_ENGINE] No 1m bars for {bar_start_ms}-{bar_end_ms}"
            )
            return

        for idx, (_, m1_bar) in enumerate(m1_bars.iterrows()):
            yield from self.generate_ticks_for_m1_bar(m1_bar, idx)

    def get_tick_count_for_bar(self, bar_start_ms: int, bar_end_ms: int) -> int:
        """Подсчитать количество тиков для бара T."""
        m1_bars = self.get_m1_bars_for_bar_T(bar_start_ms, bar_end_ms)
        ticks_per_bar = 4 + (self.config.subticks_per_segment * 3)
        return len(m1_bars) * ticks_per_bar


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_interval_ms(interval: str) -> int:
    """Получить длительность интервала в миллисекундах."""
    interval_map = {
        "1": 60000,
        "1m": 60000,
        "3": 180000,
        "3m": 180000,
        "5": 300000,
        "5m": 300000,
        "15": 900000,
        "15m": 900000,
        "30": 1800000,
        "30m": 1800000,
        "60": 3600000,
        "1h": 3600000,
        "120": 7200000,
        "2h": 7200000,
        "240": 14400000,
        "4h": 14400000,
        "360": 21600000,
        "6h": 21600000,
        "720": 43200000,
        "12h": 43200000,
        "D": 86400000,
        "1d": 86400000,
        "W": 604800000,
        "1w": 604800000,
    }
    return interval_map.get(interval, 3600000)


def get_m1_count_per_bar(interval: str) -> int:
    """Получить количество 1m баров в одном баре старшего ТФ."""
    interval_ms = get_interval_ms(interval)
    return interval_ms // 60000


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Пример использования
    config = IntrabarConfig(
        ohlc_path=OHLCPath.O_HL_HEURISTIC,
        subticks_per_segment=2,
    )

    engine = IntrabarEngine(config)

    # Создаём тестовые 1m данные
    test_m1 = pd.DataFrame(
        {
            "open_time": [1000000, 1060000, 1120000],  # 3 минуты
            "open": [100.0, 101.0, 100.5],
            "high": [102.0, 103.0, 101.5],
            "low": [99.0, 100.0, 99.5],
            "close": [101.0, 100.5, 101.0],
            "volume": [1000, 1500, 1200],
        }
    )

    engine.load_m1_data(test_m1)

    # Генерируем тики для 3-минутного бара
    print("Generated ticks:")
    for tick in engine.generate_ticks(1000000, 1180000):
        print(f"  {tick.timestamp_ms}: {tick.price:.2f} ({tick.tick_type})")
