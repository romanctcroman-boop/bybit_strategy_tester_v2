"""
Live Signal Service.

Хранит скользящее окно OHLCV последних N баров (warmup) и пересчитывает
сигналы стратегии на каждом закрытом баре.

Критические требования (по ТЗ + экспертной оценке):
- push_closed_bar() никогда не возвращает None — при ошибке возвращает
  {long: False, short: False, error: str, bars_used: int}
- Пустые бары (volume=0) пропускаются — возвращается {empty_bar: True}
- Медленные вызовы generate_signals() (>2 сек) логируются WARNING
- Кэширование: если данные не изменились с прошлого бара — сигнал не пересчитывается
- deque с maxlen — не требует ручного урезания
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import deque

import pandas as pd

logger = logging.getLogger(__name__)

# Минимальный размер warmup окна — 500 баров покрывает 99% стратегий
MIN_WARMUP_BARS = 500

# Порог медленного вызова (сек): логировать WARNING если превышен
SLOW_SIGNAL_THRESHOLD_SEC = 2.0


def _hash_window(window: deque) -> str:
    """Лёгкий хэш последних баров окна для кэширования сигнала."""
    if not window:
        return ""
    # Хэшируем только последние 10 баров (достаточно для обнаружения изменений)
    tail = list(window)[-10:]
    raw = json.dumps(tail, sort_keys=True, default=str)
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()


class LiveSignalService:
    """
    Хранит скользящее окно OHLCV + пересчитывает сигналы адаптером.

    Создаётся один раз для каждой сессии (symbol × interval × strategy).
    При инициализации заполняется историческими данными из БД (warmup).

    Thread-safety: НЕ потокобезопасен. Предназначен для использования
    в одном asyncio-корутин-потоке (FastAPI SSE endpoint).
    """

    def __init__(
        self,
        strategy_graph: dict,
        warmup_bars: list[dict],  # [{"time", "open", "high", "low", "close", "volume"}]
        warmup_size: int = MIN_WARMUP_BARS,
    ) -> None:
        """
        Args:
            strategy_graph: Граф стратегии из builder_graph (dict с blocks/connections).
            warmup_bars:     Исторические бары для прогрева индикаторов.
            warmup_size:     Максимальный размер скользящего окна.
        """
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        self._adapter = StrategyBuilderAdapter(strategy_graph)
        self._warmup_size = max(warmup_size, MIN_WARMUP_BARS)
        self._window: deque[dict] = deque(maxlen=self._warmup_size)

        # Заполнить окно историческими данными (обрезать до warmup_size)
        for bar in warmup_bars[-self._warmup_size :]:
            self._window.append(bar)

        # Кэш последнего сигнала для пропуска пересчёта при неизменных данных
        self._last_window_hash: str = ""
        self._last_signal: dict = {"long": False, "short": False}

        logger.info(
            "[LiveSignalService] Initialized with %d warmup bars (maxlen=%d)",
            len(self._window),
            self._warmup_size,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push_closed_bar(self, candle: dict) -> dict:
        """
        Принять закрытый бар, пересчитать сигналы стратегии.

        НИКОГДА не возвращает None. При ошибке — возвращает словарь
        с ключом «error» и отладочной информацией.

        Args:
            candle: {"time", "open", "high", "low", "close", "volume"}

        Returns:
            Словарь с ключами:
              long      (bool)   — сигнал на лонг
              short     (bool)   — сигнал на шорт
              bars_used (int)    — количество баров в окне
              error     (str)    — только при ошибке
              empty_bar (bool)   — только для пустых баров (volume=0)
              cached    (bool)   — только если использован кэш
        """
        bars_used = len(self._window) + 1  # +1 т.к. candle ещё не добавлен

        # 1. Пропустить бары без объёма (volume=0 → нет сделок на Bybit)
        volume = candle.get("volume", 0)
        try:
            volume = float(volume)
        except (TypeError, ValueError):
            volume = 0.0

        if volume == 0.0:
            logger.debug(
                "[LiveSignalService] Skipping empty bar at time=%s (volume=0)",
                candle.get("time"),
            )
            return {"long": False, "short": False, "empty_bar": True, "bars_used": bars_used}

        # 2. Добавить бар в окно
        self._window.append(candle)
        bars_used = len(self._window)

        # 3. Проверить кэш — если данные не изменились, вернуть прошлый сигнал
        current_hash = _hash_window(self._window)
        if current_hash == self._last_window_hash and self._last_window_hash:
            return {**self._last_signal, "bars_used": bars_used, "cached": True}

        # 4. Построить DataFrame и вычислить сигналы
        df = self._build_df()
        t_start = time.perf_counter()

        try:
            result = self._adapter.generate_signals(df)
            elapsed = time.perf_counter() - t_start

            # Логировать медленные вызовы
            if elapsed > SLOW_SIGNAL_THRESHOLD_SEC:
                logger.warning(
                    "[LiveSignalService] Slow signal computation: %.2fs (bars=%d, threshold=%.1fs)",
                    elapsed,
                    bars_used,
                    SLOW_SIGNAL_THRESHOLD_SEC,
                )

            last_idx = len(df) - 1
            long_signal = bool(result.entries.iloc[last_idx]) if result.entries is not None else False
            short_signal = bool(result.short_entries.iloc[last_idx]) if result.short_entries is not None else False

            signal = {"long": long_signal, "short": short_signal, "bars_used": bars_used}

            # Обновить кэш
            self._last_window_hash = current_hash
            self._last_signal = {"long": long_signal, "short": short_signal}

            return signal

        except Exception as e:
            elapsed = time.perf_counter() - t_start
            logger.error(
                "[LiveSignalService] Signal computation failed after %.2fs: %s",
                elapsed,
                e,
                exc_info=True,
            )
            # Явно сообщаем об ошибке клиенту — не возвращаем None
            return {
                "long": False,
                "short": False,
                "error": str(e),
                "bars_used": bars_used,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_df(self) -> pd.DataFrame:
        """Построить DataFrame из текущего скользящего окна."""
        bars = list(self._window)
        df = pd.DataFrame(bars)
        df.index = pd.to_datetime(df["time"], unit="s", utc=True)
        # Колонки остаются lowercase (open/high/low/close/volume) —
        # StrategyBuilderAdapter.generate_signals() ожидает именно lowercase.
        return df

    # ------------------------------------------------------------------
    # Properties (used in tests)
    # ------------------------------------------------------------------

    @property
    def window_size(self) -> int:
        """Текущий размер окна."""
        return len(self._window)
