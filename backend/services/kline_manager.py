"""
KlineDataManager — единая точка управления свечными данными.

Все части системы (backtests, marketdata, live_chart) обращаются к данным
ТОЛЬКО через этот модуль. Никаких прямых вызовов BybitAdapter._persist_klines_to_db
или _get_kline_audit_state_sync за пределами этого файла.

Инварианты:
- Все timestamps — в миллисекундах.
- Уникальный ключ БД: (symbol, interval, market_type, open_time).
- Запись — через BybitAdapter._persist_klines_to_db (проверен UPSERT с market_type).
- Fetch — через BybitAdapter.get_historical_klines (без side-effects).
- Per-(symbol, interval, market_type) asyncio.Lock — предотвращает дублирование запросов.

Singleton: создаётся один раз в lifespan.py, затем импортируется как:
    from backend.services.kline_manager import kline_manager
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from backend.config.database_policy import DATA_START_DATE

if TYPE_CHECKING:
    from backend.services.adapters.bybit import BybitAdapter

logger = logging.getLogger(__name__)

# =============================================================================
# КОНСТАНТЫ — единственное место определения в проекте
# =============================================================================

#: Длительность интервала в миллисекундах (9 поддерживаемых TF)
INTERVAL_MS: dict[str, int] = {
    "1": 60_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "240": 14_400_000,
    "D": 86_400_000,
    "W": 604_800_000,
    "M": 2_592_000_000,
}

#: Кол-во свечей нахлёста при догрузке (перезаписывает последние N баров)
OVERLAP_CANDLES: dict[str, int] = {
    "1": 5,
    "5": 5,
    "15": 5,
    "30": 5,
    "60": 5,
    "240": 4,
    "D": 3,
    "W": 2,
    "M": 2,
}

#: Поддерживаемые интервалы — для валидации входных данных
VALID_INTERVALS: list[str] = list(INTERVAL_MS)

#: Максимальный разрыв (730 дней) — больше не имеет смысла патчить, нужен новый бэктест
MAX_GAP_MS: int = 730 * 86_400_000

#: Минимальный разрыв (2 бара) — меньше не стоит делать fetch
MIN_GAP_CANDLES: int = 2


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class CoverageInfo:
    """Состояние данных в БД для (symbol, interval, market_type)."""

    symbol: str
    interval: str
    market_type: str
    count: int
    earliest_ms: int | None  # earliest open_time в БД (ms)
    latest_ms: int | None  # latest open_time в БД (ms)
    completeness_pct: float = 0.0


@dataclass
class SyncResult:
    """Результат синхронизации одного TF."""

    status: str  # "loaded" | "updated" | "fresh" | "error" | "timeout"
    new_candles: int = 0
    latest_ts: int | None = None
    error: str | None = None


# =============================================================================
# KlineDataManager
# =============================================================================


class KlineDataManager:
    """
    Единая точка входа для всех операций со свечными данными.

    Использование:
        # В lifespan.py:
        kline_manager = KlineDataManager(adapter=bybit_adapter)
        app.state.kline_manager = kline_manager

        # В роутерах:
        from backend.services.kline_manager import kline_manager
        candles = await kline_manager.ensure_range(symbol, interval, start_ms, end_ms)

    Правила:
    - Services MUST NOT raise HTTPException — только ValueError / RuntimeError.
    - Все Bybit-ответы проверяются на retCode == 0.
    - asyncio.to_thread() для всех синхронных DB-операций.
    """

    def __init__(self, adapter: BybitAdapter) -> None:
        self._adapter = adapter
        # Per-(symbol, interval, market_type) locks — только один fetch за раз
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}
        self._locks_mutex = asyncio.Lock()

    # =========================================================================
    # ПУБЛИЧНЫЙ API
    # =========================================================================

    async def ensure_range(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        market_type: str = "linear",
        overlap: int | None = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        """
        Гарантирует наличие данных [start_ms, end_ms] в БД.
        После загрузки читает и возвращает полный диапазон из БД.

        Алгоритм:
        1. Валидация interval.
        2. Читаем coverage (latest_ms, earliest_ms) в потоке.
        3. Определяем gaps (левый/правый/полный).
        4. Для каждого gap — fetch с Bybit + persist в поток.
        5. Возвращаем get_candles(start_ms, end_ms).

        Использование: chart load, backtest extend, /klines/ensure endpoint.

        Args:
            symbol: Торговая пара (BTCUSDT).
            interval: Таймфрейм ("15", "60", "D").
            start_ms: Начало диапазона (ms).
            end_ms: Конец диапазона (ms).
            market_type: "linear" | "spot".
            overlap: Кол-во баров нахлёста (None = из OVERLAP_CANDLES).
            force_refresh: True = всегда обращаться к Bybit.

        Returns:
            Список свечей в формате LightweightCharts:
            [{"time": <sec>, "open": .., "high": .., "low": .., "close": .., "volume": ..}]

        Raises:
            ValueError: Неподдерживаемый interval.
            RuntimeError: Bybit API недоступен.
        """
        self._validate_interval(interval)

        eff_overlap = overlap if overlap is not None else OVERLAP_CANDLES.get(interval, 3)
        interval_ms = INTERVAL_MS[interval]

        lock = await self._get_lock(symbol, interval, market_type)
        async with lock:
            # 1. Coverage из БД
            cov = await asyncio.to_thread(self._get_coverage_sync, symbol, interval, market_type)

            # 2. Определить что нужно загрузить
            gaps: list[tuple[int, int]] = []

            if force_refresh or cov.count == 0:
                # Полная загрузка
                gaps.append((start_ms, end_ms))
            else:
                assert cov.earliest_ms is not None
                assert cov.latest_ms is not None

                # Левый gap: данные начинаются позже чем нужно
                if cov.earliest_ms > start_ms + interval_ms:
                    gaps.append((start_ms, cov.earliest_ms - interval_ms))

                # Правый gap: данные заканчиваются раньше нужного
                # + нахлёст на последние N баров (overlap)
                fetch_from = cov.latest_ms - (interval_ms * eff_overlap)
                if fetch_from < end_ms:
                    gaps.append((fetch_from, end_ms))

                # Внутренние gaps: дыры внутри диапазона (window function через SQL)
                internal = await asyncio.to_thread(
                    self._find_internal_gaps_sync,
                    symbol,
                    interval,
                    market_type,
                    start_ms,
                    end_ms,
                    interval_ms,
                )
                gaps.extend(internal)

            # 3. Загрузить каждый gap
            total_fetched = 0
            for gap_start, gap_end in gaps:
                rows = await self._fetch_from_bybit(symbol, interval, gap_start, gap_end, market_type)
                if rows:
                    n = await asyncio.to_thread(self._persist_sync, symbol, interval, market_type, rows)
                    total_fetched += n
                    logger.info(
                        "[KlineManager] %s/%s/%s: persisted %d candles (gap %d→%d)",
                        symbol,
                        interval,
                        market_type,
                        n,
                        gap_start,
                        gap_end,
                    )

        # 4. Читаем из БД и возвращаем
        return await self.get_candles(symbol, interval, start_ms, end_ms, market_type)

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        market_type: str = "linear",
        limit: int = 100_000,
    ) -> list[dict]:
        """
        Только читает свечи из БД. БЕЗ сетевых запросов.

        Returns:
            Список свечей, отсортированных по времени (oldest first):
            [{"time": <sec>, "open": .., "high": .., "low": .., "close": .., "volume": ..}]
        """
        self._validate_interval(interval)
        return await asyncio.to_thread(self._get_candles_sync, symbol, interval, start_ms, end_ms, market_type, limit)

    async def sync_all_timeframes(
        self,
        symbol: str,
        market_type: str = "linear",
        timeframes: list[str] | None = None,
        from_date: datetime | None = None,
        on_progress: Callable[[str, str, int], Any] | None = None,
        max_concurrent: int = 3,
    ) -> dict[str, SyncResult]:
        """
        Синхронизирует все (или указанные) TF для символа от from_date до now.

        Для каждого TF вызывает ensure_range(start=from_date_ms, end=now_ms).
        TF синхронизируются параллельно через asyncio.Semaphore(max_concurrent=3).

        Args:
            symbol: Торговая пара.
            market_type: "linear" | "spot".
            timeframes: Список TF; None = все VALID_INTERVALS.
            from_date: Начальная дата; None = DATA_START_DATE.
            on_progress: Callback(interval, status, new_candles) — вызывается после каждого TF.
            max_concurrent: Максимальное кол-во параллельных TF (default 3).

        Returns:
            {interval: SyncResult}

        Использование: /symbols/sync-all-tf, /symbols/sync-all-tf-stream.
        """
        tfs = timeframes or VALID_INTERVALS
        start_ms = int((from_date or DATA_START_DATE).timestamp() * 1000)
        now_ms = int(datetime.now(UTC).timestamp() * 1000)

        sem = asyncio.Semaphore(max_concurrent)

        async def _sync_one(interval: str) -> tuple[str, SyncResult]:
            async with sem:
                try:
                    cov_before = await asyncio.to_thread(self._get_coverage_sync, symbol, interval, market_type)

                    await self.ensure_range(
                        symbol=symbol,
                        interval=interval,
                        start_ms=start_ms,
                        end_ms=now_ms,
                        market_type=market_type,
                    )

                    cov_after = await asyncio.to_thread(self._get_coverage_sync, symbol, interval, market_type)
                    new_candles = max(0, cov_after.count - cov_before.count)

                    # Определяем статус
                    if cov_before.count == 0:
                        status = "loaded"
                    elif new_candles > 0:
                        status = "updated"
                    else:
                        status = "fresh"

                    result = SyncResult(
                        status=status,
                        new_candles=new_candles,
                        latest_ts=cov_after.latest_ms,
                    )
                except Exception as exc:
                    logger.error("[KlineManager] sync_all_timeframes %s/%s error: %s", symbol, interval, exc)
                    result = SyncResult(status="error", error=str(exc))

                if on_progress is not None:
                    try:
                        await on_progress(interval, result.status, result.new_candles)
                    except Exception as cb_exc:
                        logger.warning("[KlineManager] on_progress callback error: %s", cb_exc)

                return interval, result

        outcomes = await asyncio.gather(*(_sync_one(tf) for tf in tfs), return_exceptions=True)

        results: dict[str, SyncResult] = {}
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.error("[KlineManager] sync_all_timeframes gather error: %s", outcome)
                continue
            tf, result = outcome
            results[tf] = result

        return results

    async def patch_last_bar(
        self,
        symbol: str,
        interval: str,
        market_type: str = "linear",
    ) -> dict | None:
        """
        Перезаписывает последнюю свечу в БД актуальными данными с биржи.

        Нужно перед запуском бэктеста — последняя закрытая свеча в БД
        могла быть записана во время её формирования (OHLCV неполные).

        Returns:
            Обновлённая свеча в LightweightCharts формате или None.
        """
        self._validate_interval(interval)

        cov = await asyncio.to_thread(self._get_coverage_sync, symbol, interval, market_type)
        if cov.latest_ms is None:
            return None

        interval_ms = INTERVAL_MS[interval]
        # Fetch последние 2 бара чтобы финализировать last
        fetch_start = cov.latest_ms - interval_ms
        fetch_end = cov.latest_ms + interval_ms  # +1 бар с запасом

        rows = await self._fetch_from_bybit(symbol, interval, fetch_start, fetch_end, market_type)
        if not rows:
            return None

        await asyncio.to_thread(self._persist_sync, symbol, interval, market_type, rows)

        # Возвращаем последнюю
        return rows[-1] if rows else None

    async def persist_bar(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        candle: dict,
    ) -> None:
        """
        Сохраняет одну закрытую свечу от live WebSocket.

        UPSERT с MAX/MIN для H/L (свеча могла частично уже прийти).
        Вызывается через asyncio.create_task() из live_chart/stream.

        Args:
            candle: LightweightCharts формат: {time (sec), open, high, low, close, volume}
        """
        open_time_ms: int = candle["time"] * 1000
        await asyncio.to_thread(
            self._persist_live_bar_sync,
            symbol,
            interval,
            market_type,
            candle,
            open_time_ms,
        )

    async def get_coverage(
        self,
        symbol: str,
        interval: str,
        market_type: str = "linear",
    ) -> CoverageInfo:
        """
        Возвращает состояние БД для (symbol, interval, market_type).
        Использование: диагностические endpoints, ensure_range (внутри).
        """
        self._validate_interval(interval)
        return await asyncio.to_thread(self._get_coverage_sync, symbol, interval, market_type)

    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ (PRIVATE)
    # =========================================================================

    async def _get_lock(self, symbol: str, interval: str, market_type: str) -> asyncio.Lock:
        """Возвращает (создаёт при необходимости) asyncio.Lock для ключа."""
        key = (symbol, interval, market_type)
        # Проверяем без mutex — быстрый путь
        if key in self._locks:
            return self._locks[key]
        # Медленный путь — создаём с mutex чтобы не создать два Lock'а
        async with self._locks_mutex:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def _fetch_from_bybit(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        market_type: str,
    ) -> list[dict]:
        """
        Вызывает BybitAdapter.get_historical_klines и нормализует результат.
        Все возвращаемые свечи содержат open_time (ms) + interval.
        """
        try:
            rows = await self._adapter.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_time=start_ms,
                end_time=end_ms,
                limit=1000,
                market_type=market_type,
            )
            if not rows:
                return []
            # Обогащаем каждую строку interval для _persist_klines_to_db
            return [{**r, "interval": interval} for r in rows]
        except Exception as exc:
            logger.error(
                "[KlineManager] Bybit fetch failed %s/%s [%d-%d]: %s",
                symbol,
                interval,
                start_ms,
                end_ms,
                exc,
            )
            raise RuntimeError(f"Bybit API unavailable for {symbol}/{interval}: {exc}") from exc

    def _persist_sync(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        rows: list[dict],
    ) -> int:
        """
        СИНХРОННАЯ запись батча через BybitAdapter._persist_klines_to_db.
        Вызывается через asyncio.to_thread().

        Использует тот же путь записи, что и весь остальной код —
        raw SQL UPSERT с поддержкой market_type.
        """
        if not rows:
            return 0
        self._adapter._persist_klines_to_db(
            symbol=symbol,
            normalized_rows=rows,
            market_type=market_type,
            interval=interval,
        )
        return len(rows)

    def _get_coverage_sync(
        self,
        symbol: str,
        interval: str,
        market_type: str,
    ) -> CoverageInfo:
        """
        СИНХРОННАЯ читает (latest_ts, earliest_ts, count) из BybitKlineAudit.
        Вызывается через asyncio.to_thread().

        Заменяет _get_kline_audit_state_sync из marketdata.py.
        """
        from sqlalchemy import func

        from backend.database import SessionLocal
        from backend.models.bybit_kline_audit import BybitKlineAudit

        with SessionLocal() as session:
            row = (
                session.query(
                    func.min(BybitKlineAudit.open_time).label("earliest"),
                    func.max(BybitKlineAudit.open_time).label("latest"),
                    func.count(BybitKlineAudit.id).label("count"),
                )
                .filter(
                    BybitKlineAudit.symbol == symbol,
                    BybitKlineAudit.interval == interval,
                    BybitKlineAudit.market_type == market_type,
                )
                .first()
            )

        count = int(row.count) if row and row.count else 0
        earliest_ms = int(row.earliest) if row and row.earliest is not None else None
        latest_ms = int(row.latest) if row and row.latest is not None else None

        # Completeness (оценка — без учёта рыночных пауз)
        completeness = 0.0
        if count > 0 and earliest_ms is not None and latest_ms is not None:
            interval_ms = INTERVAL_MS.get(interval, 60_000)
            expected = max(1, int((latest_ms - earliest_ms) / interval_ms) + 1)
            completeness = round(count / expected * 100, 2)

        return CoverageInfo(
            symbol=symbol,
            interval=interval,
            market_type=market_type,
            count=count,
            earliest_ms=earliest_ms,
            latest_ms=latest_ms,
            completeness_pct=completeness,
        )

    def _get_candles_sync(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        market_type: str,
        limit: int,
    ) -> list[dict]:
        """
        СИНХРОННАЯ читает свечи из БД в формате LightweightCharts.
        Вызывается через asyncio.to_thread().
        """
        from backend.database import SessionLocal
        from backend.models.bybit_kline_audit import BybitKlineAudit

        with SessionLocal() as session:
            rows = (
                session.query(BybitKlineAudit)
                .filter(
                    BybitKlineAudit.symbol == symbol,
                    BybitKlineAudit.interval == interval,
                    BybitKlineAudit.market_type == market_type,
                    BybitKlineAudit.open_time >= start_ms,
                    BybitKlineAudit.open_time <= end_ms,
                )
                .order_by(BybitKlineAudit.open_time.asc())
                .limit(limit)
                .all()
            )

        return [
            {
                "time": r.open_time // 1000,  # LightweightCharts использует секунды
                "open": float(r.open_price),
                "high": float(r.high_price),
                "low": float(r.low_price),
                "close": float(r.close_price),
                "volume": float(r.volume) if r.volume else 0.0,
            }
            for r in rows
        ]

    def _persist_live_bar_sync(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        candle: dict,
        open_time_ms: int,
    ) -> None:
        """
        СИНХРОННАЯ UPSERT одной закрытой свечи от live WebSocket.
        MAX(high) / MIN(low) — свеча могла уже частично прийти.
        Вызывается через asyncio.to_thread().

        Это вынесено сюда из _persist_live_bar_sync в marketdata.py.
        """
        from sqlalchemy import text

        from backend.database import SessionLocal

        row = {
            "symbol": symbol,
            "interval": interval,
            "market_type": market_type,
            "open_time": open_time_ms,
            "open_price": candle["open"],
            "high_price": candle["high"],
            "low_price": candle["low"],
            "close_price": candle["close"],
            "volume": candle.get("volume", 0),
            "turnover": candle.get("volume", 0),
            "raw": "{}",
        }

        with SessionLocal() as session:
            dialect = session.bind.dialect.name  # type: ignore[union-attr]
            if dialect in ("postgres", "postgresql"):
                sql = text(
                    """
                    INSERT INTO bybit_kline_audit
                        (symbol, interval, market_type, open_time,
                         open_price, high_price, low_price, close_price,
                         volume, turnover, raw)
                    VALUES
                        (:symbol, :interval, :market_type, :open_time,
                         :open_price, :high_price, :low_price, :close_price,
                         :volume, :turnover, :raw)
                    ON CONFLICT (symbol, interval, market_type, open_time) DO UPDATE SET
                        high_price  = GREATEST(EXCLUDED.high_price,  bybit_kline_audit.high_price),
                        low_price   = LEAST(EXCLUDED.low_price,   bybit_kline_audit.low_price),
                        close_price = EXCLUDED.close_price,
                        volume      = EXCLUDED.volume
                    """
                )
            else:
                sql = text(
                    """
                    INSERT INTO bybit_kline_audit
                        (symbol, interval, market_type, open_time,
                         open_price, high_price, low_price, close_price,
                         volume, turnover, raw)
                    VALUES
                        (:symbol, :interval, :market_type, :open_time,
                         :open_price, :high_price, :low_price, :close_price,
                         :volume, :turnover, :raw)
                    ON CONFLICT(symbol, interval, market_type, open_time) DO UPDATE SET
                        high_price  = MAX(EXCLUDED.high_price,  bybit_kline_audit.high_price),
                        low_price   = MIN(EXCLUDED.low_price,   bybit_kline_audit.low_price),
                        close_price = EXCLUDED.close_price,
                        volume      = EXCLUDED.volume
                    """
                )
            session.execute(sql, row)
            session.commit()

    def _validate_interval(self, interval: str) -> None:
        """Raises ValueError если interval не в VALID_INTERVALS."""
        if interval not in VALID_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval!r}. Supported: {VALID_INTERVALS}")

    def _find_internal_gaps_sync(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_ms: int,
        end_ms: int,
        interval_ms: int,
    ) -> list[tuple[int, int]]:
        """
        СИНХРОННАЯ SQL window-function поиск внутренних дыр в [start_ms, end_ms].

        Использует LEAD() для нахождения пар (open_time, next_open_time) где
        разрыв превышает 1.5 * interval_ms. Фильтрует по market_type и диапазону.

        Returns:
            Список (gap_start_ms, gap_end_ms) — каждый требует отдельного fetch.
        """
        from sqlalchemy import text

        from backend.database import SessionLocal

        gap_threshold = int(interval_ms * 1.5)

        sql = text(
            """
            WITH ordered AS (
                SELECT
                    open_time,
                    LEAD(open_time) OVER (ORDER BY open_time) AS next_time
                FROM bybit_kline_audit
                WHERE symbol   = :symbol
                  AND interval = :interval
                  AND market_type = :market_type
                  AND open_time >= :start_ms
                  AND open_time <= :end_ms
            )
            SELECT open_time AS gap_start, next_time AS gap_end
            FROM ordered
            WHERE next_time IS NOT NULL
              AND (next_time - open_time) > :threshold
            ORDER BY open_time
            LIMIT 50
            """
        )

        with SessionLocal() as session:
            rows = session.execute(
                sql,
                {
                    "symbol": symbol,
                    "interval": interval,
                    "market_type": market_type,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "threshold": gap_threshold,
                },
            ).fetchall()

        result: list[tuple[int, int]] = []
        for row in rows:
            gs = int(row[0])
            ge = int(row[1])
            # Проверяем: gap должен быть минимум MIN_GAP_CANDLES баров
            if (ge - gs) >= interval_ms * MIN_GAP_CANDLES:
                result.append((gs + interval_ms, ge - interval_ms))

        if result:
            logger.info(
                "[KlineManager] %s/%s/%s: found %d internal gap(s)",
                symbol,
                interval,
                market_type,
                len(result),
            )
        return result


# =============================================================================
# MODULE-LEVEL SINGLETON
#
# Правильный паттерн — lazy accessor через init_kline_manager() / get_kline_manager().
# НЕ импортировать `kline_manager` напрямую из других модулей — при импорте
# во время старта сервера значение будет None (lifespan ещё не запущен).
#
# Использование в lifespan.py:
#     from backend.services.kline_manager import init_kline_manager
#     init_kline_manager(bybit_adapter)
#
# Использование в роутерах:
#     from backend.services.kline_manager import get_kline_manager
#     km = get_kline_manager()
# =============================================================================

#: Singleton — НЕ импортировать напрямую. Использовать get_kline_manager().
_instance: KlineDataManager | None = None

# Алиас для обратной совместимости (lifespan.py присваивает через него)
kline_manager: KlineDataManager | None = None


def init_kline_manager(adapter: BybitAdapter) -> KlineDataManager:
    """
    Создаёт и регистрирует singleton KlineDataManager.

    Должен вызываться ОДИН РАЗ из lifespan.py при старте сервера.
    Повторный вызов заменяет существующий инстанс (для тестов).

    Args:
        adapter: Инициализированный BybitAdapter с ключами API.

    Returns:
        Созданный KlineDataManager.
    """
    global _instance, kline_manager
    _instance = KlineDataManager(adapter=adapter)
    kline_manager = _instance  # обратная совместимость
    logger.info("[KlineManager] Singleton initialized with adapter %s", type(adapter).__name__)
    return _instance


def get_kline_manager() -> KlineDataManager:
    """
    Возвращает инициализированный singleton KlineDataManager.

    Raises:
        RuntimeError: Если init_kline_manager() ещё не был вызван
                      (lifespan.py не запустился или тест не инициализировал).
    """
    if _instance is None:
        raise RuntimeError(
            "KlineDataManager not initialized. "
            "Call init_kline_manager(adapter) in lifespan.py before handling requests."
        )
    return _instance
