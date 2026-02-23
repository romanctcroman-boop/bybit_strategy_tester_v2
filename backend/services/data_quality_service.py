"""
Data Quality Service - Autonomous anomaly detection and repair.

This service continuously monitors data quality and automatically fixes issues:
1. Completeness - missing candles detection
2. Freshness - stale data detection
3. Continuity - price jump detection (Z-score)
4. Anomalies - ML-based outlier detection (Isolation Forest)

Runs as background task and auto-repairs detected issues.
"""

import asyncio
import contextlib
import logging
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data.sqlite3"

# Interval in milliseconds
INTERVAL_MS = {
    "1": 60_000,
    "3": 180_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "120": 7_200_000,
    "240": 14_400_000,
    "D": 86_400_000,
    "W": 604_800_000,
}


@dataclass
class AnomalyReport:
    """Report of detected anomaly."""

    anomaly_type: str  # 'missing_data', 'stale_data', 'price_jump', 'outlier'
    symbol: str
    interval: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    timestamp: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    auto_repaired: bool = False


@dataclass
class QualityCheckResult:
    """Result of quality check."""

    symbol: str
    interval: str
    check_time: datetime
    is_healthy: bool
    completeness_pct: float
    freshness_ok: bool
    continuity_issues: int
    ml_anomalies: int
    anomalies: list[AnomalyReport] = field(default_factory=list)


class DataQualityService:
    """
    Autonomous data quality monitoring and repair service.

    Features:
    - 4-layer detection (completeness, freshness, continuity, ML)
    - Auto-repair of detected issues
    - Background monitoring
    - Detailed logging
    """

    # Singleton instance
    _instance = None
    _lock = threading.Lock()

    # Configuration
    FRESHNESS_THRESHOLD_MULTIPLIER = 2.0  # Data is stale if older than 2x interval
    PRICE_JUMP_ZSCORE_THRESHOLD = 3.0  # Z-score threshold for price jumps
    COMPLETENESS_THRESHOLD = 95.0  # Minimum completeness percentage
    MONITORING_INTERVAL_SECONDS = 60  # Background check interval

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(DB_PATH)
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="DataQuality"
        )
        self._monitoring_task: asyncio.Task | None = None
        self._monitored_symbols: dict[str, set] = {}  # symbol -> set of intervals
        self._repair_service = None
        self._adapter = None

    @classmethod
    def get_instance(cls) -> "DataQualityService":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_repair_service(self):
        """Get DataGapRepairService for auto-repair."""
        if self._repair_service is None:
            try:
                from backend.services.data_gap_repair import DataGapRepairService

                self._repair_service = DataGapRepairService(self.db_path)
            except ImportError:
                logger.warning("DataGapRepairService not available")
        return self._repair_service

    # =========================================================================
    # LAYER 1: COMPLETENESS CHECK
    # =========================================================================

    def check_completeness(
        self, symbol: str, interval: str
    ) -> tuple[float, list[AnomalyReport]]:
        """
        Check data completeness - are all expected candles present?

        Returns:
            Tuple of (completeness_percentage, list of anomalies)
        """
        conn = self._get_connection()
        anomalies = []

        try:
            # Get data range and count
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count, MIN(open_time) as min_time, MAX(open_time) as max_time
                FROM bybit_kline_audit
                WHERE symbol = ? AND interval = ?
                """,
                (symbol, interval),
            )
            row = cursor.fetchone()

            if not row or row["count"] == 0:
                return 0.0, [
                    AnomalyReport(
                        anomaly_type="missing_data",
                        symbol=symbol,
                        interval=interval,
                        severity="critical",
                        description=f"No data found for {symbol}:{interval}",
                    )
                ]

            actual_count = row["count"]
            min_time = row["min_time"]
            max_time = row["max_time"]

            # Calculate expected count
            interval_ms = INTERVAL_MS.get(interval, 60_000)
            expected_count = int((max_time - min_time) / interval_ms) + 1

            if expected_count <= 0:
                return 100.0, []

            completeness = (actual_count / expected_count) * 100

            # Find specific gaps
            if completeness < self.COMPLETENESS_THRESHOLD:
                # Find gaps using window function
                gap_query = """
                WITH ordered AS (
                    SELECT open_time,
                           LEAD(open_time) OVER (ORDER BY open_time) as next_time
                    FROM bybit_kline_audit
                    WHERE symbol = ? AND interval = ?
                )
                SELECT open_time, next_time, (next_time - open_time) as gap_ms
                FROM ordered
                WHERE next_time IS NOT NULL AND (next_time - open_time) > ? * 1.5
                ORDER BY gap_ms DESC
                LIMIT 10
                """
                cursor = conn.execute(gap_query, (symbol, interval, interval_ms))
                gaps = cursor.fetchall()

                for gap in gaps:
                    missing_candles = int(gap["gap_ms"] / interval_ms) - 1
                    severity = "high" if missing_candles > 10 else "medium"

                    anomalies.append(
                        AnomalyReport(
                            anomaly_type="missing_data",
                            symbol=symbol,
                            interval=interval,
                            severity=severity,
                            description=f"Gap of {missing_candles} missing candles",
                            timestamp=gap["open_time"],
                            details={
                                "gap_start": gap["open_time"],
                                "gap_end": gap["next_time"],
                                "missing_candles": missing_candles,
                            },
                        )
                    )

            return completeness, anomalies

        finally:
            conn.close()

    # =========================================================================
    # LAYER 2: FRESHNESS CHECK
    # =========================================================================

    def check_freshness(
        self, symbol: str, interval: str
    ) -> tuple[bool, list[AnomalyReport]]:
        """
        Check if data is up-to-date.

        Returns:
            Tuple of (is_fresh, list of anomalies)
        """
        conn = self._get_connection()
        anomalies = []

        try:
            cursor = conn.execute(
                """
                SELECT MAX(open_time) as last_time
                FROM bybit_kline_audit
                WHERE symbol = ? AND interval = ?
                """,
                (symbol, interval),
            )
            row = cursor.fetchone()

            if not row or row["last_time"] is None:
                return False, [
                    AnomalyReport(
                        anomaly_type="stale_data",
                        symbol=symbol,
                        interval=interval,
                        severity="critical",
                        description="No data available",
                    )
                ]

            last_time_ms = row["last_time"]
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            interval_ms = INTERVAL_MS.get(interval, 60_000)

            # Data is stale if last candle is older than threshold
            max_age_ms = interval_ms * self.FRESHNESS_THRESHOLD_MULTIPLIER
            age_ms = now_ms - last_time_ms

            is_fresh = age_ms <= max_age_ms

            if not is_fresh:
                age_minutes = age_ms / 60_000
                expected_minutes = max_age_ms / 60_000

                severity = "high" if age_ms > interval_ms * 5 else "medium"

                anomalies.append(
                    AnomalyReport(
                        anomaly_type="stale_data",
                        symbol=symbol,
                        interval=interval,
                        severity=severity,
                        description=f"Data is {age_minutes:.0f} min old (max allowed: {expected_minutes:.0f} min)",
                        timestamp=last_time_ms,
                        details={
                            "last_candle_time": last_time_ms,
                            "age_ms": age_ms,
                            "threshold_ms": max_age_ms,
                        },
                    )
                )

            return is_fresh, anomalies

        finally:
            conn.close()

    # =========================================================================
    # LAYER 3: CONTINUITY CHECK (Z-SCORE)
    # =========================================================================

    def check_continuity(
        self, symbol: str, interval: str, limit: int = 500
    ) -> tuple[int, list[AnomalyReport]]:
        """
        Check price continuity using Z-score to detect unusual jumps.

        Returns:
            Tuple of (number of issues, list of anomalies)
        """
        conn = self._get_connection()
        anomalies = []

        try:
            # Get recent candles with previous close
            query = """
            WITH candles AS (
                SELECT
                    open_time,
                    open_price as open,
                    close_price as close,
                    LAG(close_price) OVER (ORDER BY open_time) as prev_close
                FROM bybit_kline_audit
                WHERE symbol = ? AND interval = ?
                ORDER BY open_time DESC
                LIMIT ?
            )
            SELECT open_time, open, close, prev_close,
                   ABS(open - prev_close) as gap,
                   ABS(open - prev_close) / prev_close * 100 as gap_pct
            FROM candles
            WHERE prev_close IS NOT NULL
            ORDER BY open_time
            """

            cursor = conn.execute(query, (symbol, interval, limit))
            rows = cursor.fetchall()

            if len(rows) < 10:
                return 0, []  # Not enough data for statistical analysis

            # Calculate gaps
            gaps = [row["gap_pct"] for row in rows if row["gap_pct"] is not None]

            if not gaps:
                return 0, []

            # Calculate Z-scores
            gaps_array = np.array(gaps)
            mean_gap = np.mean(gaps_array)
            std_gap = np.std(gaps_array)

            if std_gap == 0:
                return 0, []

            z_scores = (gaps_array - mean_gap) / std_gap

            # Absolute thresholds for critical gaps (market volatility detection)
            CRITICAL_GAP_PCT = 1.5  # >1.5% gap is always critical
            HIGH_GAP_PCT = 0.8  # >0.8% gap is high severity

            # Find anomalies: Z-score threshold OR absolute gap threshold
            issue_count = 0
            for _i, (z, row) in enumerate(zip(z_scores, rows, strict=False)):
                gap_pct = abs(row["gap_pct"])

                # Detect by Z-score OR absolute gap percentage
                is_zscore_anomaly = abs(z) > self.PRICE_JUMP_ZSCORE_THRESHOLD
                is_critical_gap = gap_pct >= CRITICAL_GAP_PCT
                is_high_gap = gap_pct >= HIGH_GAP_PCT

                if is_zscore_anomaly or is_critical_gap:
                    issue_count += 1

                    # Determine severity by multiple criteria
                    if is_critical_gap or abs(z) > 5:
                        severity = "critical"
                    elif is_high_gap or abs(z) > 4:
                        severity = "high"
                    else:
                        severity = "medium"

                    # Calculate dollar amount for context
                    gap_dollars = abs(row["open"] - row["prev_close"])
                    direction = "UP" if row["gap_pct"] > 0 else "DOWN"

                    anomalies.append(
                        AnomalyReport(
                            anomaly_type="price_gap",  # renamed for clarity
                            symbol=symbol,
                            interval=interval,
                            severity=severity,
                            description=f"Price gap {direction}: ${gap_dollars:,.2f} ({row['gap_pct']:+.2f}%) - Z-score: {z:.2f}",
                            timestamp=row["open_time"],
                            details={
                                "open": row["open"],
                                "prev_close": row["prev_close"],
                                "gap_pct": row["gap_pct"],
                                "gap_dollars": gap_dollars,
                                "direction": direction,
                                "z_score": float(z),
                                "is_critical": is_critical_gap,
                            },
                        )
                    )

            return issue_count, anomalies

        finally:
            conn.close()

    # =========================================================================
    # LAYER 4: ML ANOMALY DETECTION (ISOLATION FOREST)
    # =========================================================================

    def check_ml_anomalies(
        self, symbol: str, interval: str, limit: int = 500
    ) -> tuple[int, list[AnomalyReport]]:
        """
        Use Isolation Forest to detect complex anomalies.

        Returns:
            Tuple of (number of anomalies, list of anomalies)
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.debug("sklearn not available, skipping ML anomaly detection")
            return 0, []

        conn = self._get_connection()
        anomalies = []

        try:
            # Get features for ML
            query = """
            SELECT
                open_time,
                open_price as open,
                high_price as high,
                low_price as low,
                close_price as close,
                volume,
                (high_price - low_price) as range,
                (close_price - open_price) as body,
                ABS(close_price - open_price) / NULLIF(high_price - low_price, 0) as body_ratio
            FROM bybit_kline_audit
            WHERE symbol = ? AND interval = ?
            ORDER BY open_time DESC
            LIMIT ?
            """

            cursor = conn.execute(query, (symbol, interval, limit))
            rows = cursor.fetchall()

            if len(rows) < 50:
                return 0, []  # Need minimum data for ML

            # Prepare features
            features = []
            timestamps = []

            for row in rows:
                range_val = row["range"] or 0
                body_val = row["body"] or 0
                body_ratio = row["body_ratio"] or 0
                volume = row["volume"] or 0

                # Normalize by price
                price = row["close"] or 1

                features.append(
                    [
                        range_val / price * 100,  # Range as % of price
                        abs(body_val) / price * 100,  # Body as % of price
                        body_ratio,
                        np.log1p(volume),  # Log volume
                    ]
                )
                timestamps.append(row["open_time"])

            features_array = np.array(features)

            # Replace NaN/Inf with 0
            features_array = np.nan_to_num(
                features_array, nan=0.0, posinf=0.0, neginf=0.0
            )

            # Fit Isolation Forest
            clf = IsolationForest(
                contamination=0.02,  # Expect ~2% anomalies
                random_state=42,
                n_estimators=100,
            )
            predictions = clf.fit_predict(features_array)

            # Find anomalies (prediction == -1)
            anomaly_count = 0
            for i, pred in enumerate(predictions):
                if pred == -1:
                    anomaly_count += 1
                    row = rows[i]

                    anomalies.append(
                        AnomalyReport(
                            anomaly_type="outlier",
                            symbol=symbol,
                            interval=interval,
                            severity="medium",
                            description="ML detected outlier candle",
                            timestamp=timestamps[i],
                            details={
                                "open": row["open"],
                                "high": row["high"],
                                "low": row["low"],
                                "close": row["close"],
                                "volume": row["volume"],
                            },
                        )
                    )

            return anomaly_count, anomalies

        except Exception as e:
            logger.error(f"ML anomaly detection failed: {e}")
            return 0, []
        finally:
            conn.close()

    # =========================================================================
    # RUN ALL CHECKS
    # =========================================================================

    def run_all_checks(self, symbol: str, interval: str) -> QualityCheckResult:
        """
        Run all quality checks and return comprehensive report.
        """
        check_time = datetime.now(UTC)
        all_anomalies = []

        # Layer 1: Completeness
        completeness_pct, completeness_anomalies = self.check_completeness(
            symbol, interval
        )
        all_anomalies.extend(completeness_anomalies)

        # Layer 2: Freshness
        freshness_ok, freshness_anomalies = self.check_freshness(symbol, interval)
        all_anomalies.extend(freshness_anomalies)

        # Layer 3: Continuity
        continuity_issues, continuity_anomalies = self.check_continuity(
            symbol, interval
        )
        all_anomalies.extend(continuity_anomalies)

        # Layer 4: ML Anomalies
        ml_anomalies, ml_anomaly_list = self.check_ml_anomalies(symbol, interval)
        all_anomalies.extend(ml_anomaly_list)

        # Determine overall health
        is_healthy = (
            completeness_pct >= self.COMPLETENESS_THRESHOLD
            and freshness_ok
            and continuity_issues == 0
            and ml_anomalies < 5  # Allow some ML anomalies
        )

        return QualityCheckResult(
            symbol=symbol,
            interval=interval,
            check_time=check_time,
            is_healthy=is_healthy,
            completeness_pct=completeness_pct,
            freshness_ok=freshness_ok,
            continuity_issues=continuity_issues,
            ml_anomalies=ml_anomalies,
            anomalies=all_anomalies,
        )

    # =========================================================================
    # AUTO-REPAIR
    # =========================================================================

    async def auto_repair(
        self, symbol: str, interval: str, result: QualityCheckResult
    ) -> int:
        """
        Automatically repair detected issues.

        Returns:
            Number of issues repaired
        """
        repaired = 0
        repair_service = self._get_repair_service()

        if repair_service is None:
            logger.warning("Repair service not available")
            return 0

        for anomaly in result.anomalies:
            try:
                if anomaly.anomaly_type == "missing_data" and anomaly.details.get(
                    "gap_start"
                ):
                    # Repair timestamp gap
                    from backend.services.data_gap_repair import GapInfo

                    gap = GapInfo(
                        symbol=symbol,
                        interval=interval,
                        gap_start=anomaly.details["gap_start"],
                        gap_end=anomaly.details["gap_end"],
                        gap_start_dt=datetime.fromtimestamp(
                            anomaly.details["gap_start"] / 1000, tz=UTC
                        ),
                        gap_end_dt=datetime.fromtimestamp(
                            anomaly.details["gap_end"] / 1000, tz=UTC
                        ),
                        missing_candles=anomaly.details["missing_candles"],
                    )

                    loop = asyncio.get_event_loop()
                    repair_result = await loop.run_in_executor(
                        self._executor, lambda: repair_service.repair_gap(gap)
                    )

                    if repair_result.get("status") == "success":
                        anomaly.auto_repaired = True
                        repaired += 1
                        logger.info(
                            f"[DataQuality] Auto-repaired gap: {anomaly.description}"
                        )

                elif anomaly.anomaly_type == "stale_data":
                    # Trigger fresh data fetch via SmartKlineService
                    try:
                        from backend.services.smart_kline_service import (
                            SMART_KLINE_SERVICE,
                        )

                        loop = asyncio.get_event_loop()
                        candles = await loop.run_in_executor(
                            self._executor,
                            lambda: SMART_KLINE_SERVICE.get_candles(
                                symbol, interval, 500, force_fresh=True
                            ),
                        )

                        if candles and len(candles) > 0:
                            anomaly.auto_repaired = True
                            repaired += 1
                            logger.info(
                                f"[DataQuality] Refreshed stale data for {symbol}:{interval}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[DataQuality] Could not refresh stale data: {e}"
                        )

                elif anomaly.anomaly_type == "price_gap":
                    # Repair price gap by re-fetching candles around the gap
                    try:
                        repair_count = await self.repair_bad_candles(
                            symbol=symbol,
                            interval=interval,
                            timestamps=[int(anomaly.timestamp)],
                        )
                        if repair_count > 0:
                            anomaly.auto_repaired = True
                            repaired += 1
                            logger.info(
                                f"[DataQuality] Repaired price gap at {anomaly.timestamp}"
                            )
                    except Exception as e:
                        logger.warning(f"[DataQuality] Could not repair price gap: {e}")

                elif anomaly.anomaly_type == "outlier":
                    # Repair ML-detected outlier by re-fetching
                    try:
                        repair_count = await self.repair_bad_candles(
                            symbol=symbol,
                            interval=interval,
                            timestamps=[int(anomaly.timestamp)],
                        )
                        if repair_count > 0:
                            anomaly.auto_repaired = True
                            repaired += 1
                            logger.info(
                                f"[DataQuality] Repaired outlier at {anomaly.timestamp}"
                            )
                    except Exception as e:
                        logger.warning(f"[DataQuality] Could not repair outlier: {e}")

            except Exception as e:
                logger.error(f"[DataQuality] Auto-repair failed for {anomaly}: {e}")

        return repaired

    async def repair_bad_candles(
        self,
        symbol: str,
        interval: str,
        timestamps: list[int],
        context_candles: int = 3,
    ) -> int:
        """
        Repair bad/corrupted candles by re-fetching from Bybit API.

        Args:
            symbol: Trading symbol
            interval: Timeframe
            timestamps: List of timestamps (ms) of bad candles
            context_candles: Number of candles before/after to also refresh

        Returns:
            Number of candles repaired
        """
        if not timestamps:
            return 0

        logger.info(
            f"[DataQuality] Repairing {len(timestamps)} bad candles for {symbol}:{interval}"
        )

        # Get interval in ms
        interval_ms = {
            "1": 60_000,
            "3": 180_000,
            "5": 300_000,
            "15": 900_000,
            "30": 1_800_000,
            "60": 3_600_000,
            "120": 7_200_000,
            "240": 14_400_000,
            "D": 86_400_000,
            "W": 604_800_000,
        }.get(interval, 60_000)

        # Calculate range to fetch (include context)
        min_ts = min(timestamps) - (context_candles * interval_ms)
        max_ts = max(timestamps) + (context_candles * interval_ms)

        # Fetch fresh candles from Bybit API
        try:
            from backend.services.adapters.bybit import BybitAdapter

            adapter = BybitAdapter()

            loop = asyncio.get_event_loop()
            candles = await loop.run_in_executor(
                self._executor,
                lambda: adapter.get_klines_before(
                    symbol=symbol,
                    interval=interval,
                    end_time=max_ts + interval_ms,
                    limit=min(1000, (context_candles * 2 + len(timestamps)) * 2),
                ),
            )

            if not candles:
                logger.warning("[DataQuality] No candles returned from API")
                return 0

            # Filter to our range
            candles = [c for c in candles if min_ts <= c["open_time"] <= max_ts]

            if not candles:
                logger.warning("[DataQuality] No candles in target range")
                return 0

            # Update database with fresh data
            repaired = await self._update_candles_in_db(symbol, interval, candles)

            logger.info(f"[DataQuality] Repaired {repaired} candles")
            return repaired

        except Exception as e:
            logger.error(f"[DataQuality] Repair failed: {e}")
            return 0

    async def _update_candles_in_db(
        self, symbol: str, interval: str, candles: list[dict]
    ) -> int:
        """Update candles in database (INSERT OR REPLACE)."""
        conn = sqlite3.connect(self.db_path)
        updated = 0

        try:
            for candle in candles:
                open_time_dt = datetime.fromtimestamp(
                    candle["open_time"] / 1000, tz=UTC
                ).isoformat()

                conn.execute(
                    """
                    INSERT OR REPLACE INTO bybit_kline_audit
                    (symbol, interval, open_time, open_time_dt,
                     open_price, high_price, low_price, close_price,
                     volume, turnover, raw)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        interval,
                        candle["open_time"],
                        open_time_dt,
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                        candle.get("volume", 0),
                        candle.get("turnover", 0),
                        str(candle),
                    ),
                )
                updated += 1

            conn.commit()
            logger.info(f"[DataQuality] Updated {updated} candles in DB")

        except Exception as e:
            logger.error(f"[DataQuality] DB update failed: {e}")
            conn.rollback()
        finally:
            conn.close()

        return updated

    # =========================================================================
    # BACKGROUND MONITORING
    # =========================================================================

    def start_monitoring(self, symbol: str, interval: str):
        """Add symbol/interval to monitoring list."""
        if symbol not in self._monitored_symbols:
            self._monitored_symbols[symbol] = set()
        self._monitored_symbols[symbol].add(interval)
        logger.info(f"[DataQuality] Started monitoring {symbol}:{interval}")

    def stop_monitoring(self, symbol: str, interval: str):
        """Remove symbol/interval from monitoring list."""
        if symbol in self._monitored_symbols:
            self._monitored_symbols[symbol].discard(interval)
            if not self._monitored_symbols[symbol]:
                del self._monitored_symbols[symbol]
        logger.info(f"[DataQuality] Stopped monitoring {symbol}:{interval}")

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        logger.info("[DataQuality] Background monitoring started")

        while True:
            try:
                await asyncio.sleep(self.MONITORING_INTERVAL_SECONDS)

                for symbol, intervals in list(self._monitored_symbols.items()):
                    for interval in list(intervals):
                        try:
                            result = await asyncio.get_event_loop().run_in_executor(
                                self._executor,
                                lambda s=symbol, i=interval: self.run_all_checks(s, i),
                            )

                            if not result.is_healthy:
                                logger.warning(
                                    f"[DataQuality] Issues detected for {symbol}:{interval}: "
                                    f"completeness={result.completeness_pct:.1f}%, "
                                    f"fresh={result.freshness_ok}, "
                                    f"continuity_issues={result.continuity_issues}, "
                                    f"ml_anomalies={result.ml_anomalies}"
                                )

                                # Auto-repair
                                repaired = await self.auto_repair(
                                    symbol, interval, result
                                )
                                if repaired > 0:
                                    logger.info(
                                        f"[DataQuality] Auto-repaired {repaired} issues for {symbol}:{interval}"
                                    )
                            else:
                                logger.debug(
                                    f"[DataQuality] {symbol}:{interval} is healthy"
                                )

                        except Exception as e:
                            logger.error(
                                f"[DataQuality] Check failed for {symbol}:{interval}: {e}"
                            )

            except asyncio.CancelledError:
                logger.info("[DataQuality] Background monitoring stopped")
                break
            except Exception as e:
                logger.error(f"[DataQuality] Monitoring loop error: {e}")

    async def start_background_monitoring(self):
        """Start the background monitoring task."""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_background_monitoring(self):
        """Stop the background monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task


# Singleton instance
DATA_QUALITY_SERVICE = DataQualityService.get_instance()
