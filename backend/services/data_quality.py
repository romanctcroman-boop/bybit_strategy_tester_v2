"""
Market Data Quality Layer.

AI Agent Recommendation Implementation:
- Dedicated data validation layer for market data feeds
- Quality metrics and scoring
- Anomaly detection in data
- Gap detection
- Staleness monitoring
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DataQualityLevel(str, Enum):
    """Quality levels for market data."""

    EXCELLENT = "excellent"  # Score >= 95
    GOOD = "good"  # Score >= 80
    ACCEPTABLE = "acceptable"  # Score >= 60
    POOR = "poor"  # Score >= 40
    CRITICAL = "critical"  # Score < 40


class DataIssueType(str, Enum):
    """Types of data quality issues."""

    MISSING_DATA = "missing_data"
    STALE_DATA = "stale_data"
    PRICE_SPIKE = "price_spike"
    PRICE_GAP = "price_gap"  # Gap between close and next open
    VOLUME_ANOMALY = "volume_anomaly"
    TIMESTAMP_GAP = "timestamp_gap"
    INVALID_OHLC = "invalid_ohlc"  # High < Low, etc.
    ZERO_VOLUME = "zero_volume"
    DUPLICATE_DATA = "duplicate_data"
    SEQUENCE_ERROR = "sequence_error"
    SPREAD_ANOMALY = "spread_anomaly"


@dataclass
class DataQualityIssue:
    """Represents a data quality issue."""

    issue_type: DataIssueType
    symbol: str
    interval: str
    timestamp: datetime
    severity: float  # 0-1, higher = more severe
    description: str
    raw_data: dict[str, Any] | None = None
    auto_corrected: bool = False


@dataclass
class CandleData:
    """Represents a single candle/OHLCV data point."""

    timestamp: int  # Unix timestamp in ms
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = ""
    interval: str = ""


@dataclass
class DataQualityMetrics:
    """Quality metrics for a data stream."""

    symbol: str
    interval: str
    total_candles: int = 0
    valid_candles: int = 0
    issues_detected: int = 0
    gaps_detected: int = 0
    spikes_detected: int = 0
    quality_score: float = 100.0
    last_update: datetime | None = None
    avg_latency_ms: float = 0.0
    staleness_seconds: float = 0.0


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    quality_score: float
    issues: list[DataQualityIssue]
    corrected_data: CandleData | None = None


class MarketDataValidator:
    """
    Validator for market data quality.

    Performs various checks on OHLCV data:
    - OHLC consistency (High >= Low, etc.)
    - Price spike detection
    - Price gap detection (close → next open)
    - Volume anomaly detection
    - Timestamp gap detection
    - Staleness monitoring
    """

    def __init__(
        self,
        max_price_change_pct: float = 20.0,  # Max allowed price change %
        max_price_gap_pct: float = 1.0,  # Max allowed gap between close→open %
        max_volume_multiplier: float = 10.0,  # Max volume vs average
        staleness_threshold_seconds: float = 60.0,  # Max staleness
        min_volume: float = 0.0,  # Minimum expected volume
    ):
        self.max_price_change_pct = max_price_change_pct
        self.max_price_gap_pct = max_price_gap_pct
        self.max_volume_multiplier = max_volume_multiplier
        self.staleness_threshold_seconds = staleness_threshold_seconds
        self.min_volume = min_volume

        # Historical data for comparison
        self._price_history: dict[str, deque[float]] = {}
        self._volume_history: dict[str, deque[float]] = {}
        self._timestamp_history: dict[str, int] = {}

        self._history_size = 100

    def _get_key(self, symbol: str, interval: str) -> str:
        """Generate key for symbol/interval pair."""
        return f"{symbol}:{interval}"

    def validate_candle(
        self,
        candle: CandleData,
        previous_candle: CandleData | None = None,
    ) -> ValidationResult:
        """Validate a single candle."""
        issues = []
        score = 100.0

        # 1. OHLC Consistency Check
        ohlc_issues = self._check_ohlc_consistency(candle)
        issues.extend(ohlc_issues)
        score -= len(ohlc_issues) * 10

        # 2. Price Spike Detection
        if previous_candle:
            spike_issue = self._check_price_spike(candle, previous_candle)
            if spike_issue:
                issues.append(spike_issue)
                score -= 15

        # 3. Price Gap Detection (close → open)
        if previous_candle:
            price_gap_issue = self._check_price_gap(candle, previous_candle)
            if price_gap_issue:
                issues.append(price_gap_issue)
                score -= 10

        # 4. Volume Check
        volume_issue = self._check_volume(candle)
        if volume_issue:
            issues.append(volume_issue)
            score -= 5

        # 5. Timestamp Check
        if previous_candle:
            gap_issue = self._check_timestamp_gap(candle, previous_candle)
            if gap_issue:
                issues.append(gap_issue)
                score -= 10

        # Update history
        self._update_history(candle)

        # Ensure score is within bounds
        score = max(0.0, min(100.0, score))

        return ValidationResult(
            is_valid=len(issues) == 0,
            quality_score=score,
            issues=issues,
            corrected_data=self._attempt_correction(candle, issues) if issues else None,
        )

    def _check_ohlc_consistency(self, candle: CandleData) -> list[DataQualityIssue]:
        """Check OHLC price consistency."""
        issues = []

        # High should be >= Open, Close, Low
        if (
            candle.high < candle.open
            or candle.high < candle.close
            or candle.high < candle.low
        ):
            issues.append(
                DataQualityIssue(
                    issue_type=DataIssueType.INVALID_OHLC,
                    symbol=candle.symbol,
                    interval=candle.interval,
                    timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                    severity=0.8,
                    description=f"High ({candle.high}) is not the highest price",
                    raw_data={
                        "ohlc": [candle.open, candle.high, candle.low, candle.close]
                    },
                )
            )

        # Low should be <= Open, Close, High
        if (
            candle.low > candle.open
            or candle.low > candle.close
            or candle.low > candle.high
        ):
            issues.append(
                DataQualityIssue(
                    issue_type=DataIssueType.INVALID_OHLC,
                    symbol=candle.symbol,
                    interval=candle.interval,
                    timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                    severity=0.8,
                    description=f"Low ({candle.low}) is not the lowest price",
                    raw_data={
                        "ohlc": [candle.open, candle.high, candle.low, candle.close]
                    },
                )
            )

        # Check for zero/negative prices
        if any(p <= 0 for p in [candle.open, candle.high, candle.low, candle.close]):
            issues.append(
                DataQualityIssue(
                    issue_type=DataIssueType.INVALID_OHLC,
                    symbol=candle.symbol,
                    interval=candle.interval,
                    timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                    severity=1.0,
                    description="Zero or negative price detected",
                    raw_data={
                        "ohlc": [candle.open, candle.high, candle.low, candle.close]
                    },
                )
            )

        return issues

    def _check_price_spike(
        self, candle: CandleData, previous: CandleData
    ) -> DataQualityIssue | None:
        """Check for abnormal price changes."""
        if previous.close == 0:
            return None

        price_change_pct = abs(candle.close - previous.close) / previous.close * 100

        if price_change_pct > self.max_price_change_pct:
            return DataQualityIssue(
                issue_type=DataIssueType.PRICE_SPIKE,
                symbol=candle.symbol,
                interval=candle.interval,
                timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                severity=min(1.0, price_change_pct / 100),
                description=f"Price changed {price_change_pct:.1f}% (threshold: {self.max_price_change_pct}%)",
                raw_data={
                    "previous_close": previous.close,
                    "current_close": candle.close,
                    "change_pct": price_change_pct,
                },
            )

        return None

    def _check_price_gap(
        self, candle: CandleData, previous: CandleData
    ) -> DataQualityIssue | None:
        """Check for gap between previous close and current open."""
        if previous.close == 0:
            return None

        # Calculate gap between previous close and current open
        gap_pct = abs(candle.open - previous.close) / previous.close * 100

        if gap_pct > self.max_price_gap_pct:
            return DataQualityIssue(
                issue_type=DataIssueType.PRICE_GAP,
                symbol=candle.symbol,
                interval=candle.interval,
                timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                severity=min(1.0, gap_pct / 5),
                description=f"Price gap {gap_pct:.2f}% between close→open (threshold: {self.max_price_gap_pct}%)",
                raw_data={
                    "previous_close": previous.close,
                    "current_open": candle.open,
                    "gap_pct": gap_pct,
                },
            )

        return None

    def _check_volume(self, candle: CandleData) -> DataQualityIssue | None:
        """Check volume for anomalies."""
        # Zero volume check
        if candle.volume == 0:
            return DataQualityIssue(
                issue_type=DataIssueType.ZERO_VOLUME,
                symbol=candle.symbol,
                interval=candle.interval,
                timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                severity=0.3,
                description="Zero volume detected",
            )

        # Volume spike check against history
        key = self._get_key(candle.symbol, candle.interval)
        if key in self._volume_history and len(self._volume_history[key]) >= 10:
            avg_volume = sum(self._volume_history[key]) / len(self._volume_history[key])
            if (
                avg_volume > 0
                and candle.volume > avg_volume * self.max_volume_multiplier
            ):
                return DataQualityIssue(
                    issue_type=DataIssueType.VOLUME_ANOMALY,
                    symbol=candle.symbol,
                    interval=candle.interval,
                    timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                    severity=0.5,
                    description=f"Volume {candle.volume:.0f} is {candle.volume / avg_volume:.1f}x average",
                    raw_data={"volume": candle.volume, "avg_volume": avg_volume},
                )

        return None

    def _check_timestamp_gap(
        self, candle: CandleData, previous: CandleData
    ) -> DataQualityIssue | None:
        """Check for timestamp gaps."""
        # Calculate expected interval in milliseconds
        interval_ms = self._interval_to_ms(candle.interval)
        if interval_ms == 0:
            return None

        actual_gap = candle.timestamp - previous.timestamp
        expected_gap = interval_ms

        # Allow some tolerance (1.5x expected gap)
        if actual_gap > expected_gap * 1.5:
            missed_candles = int(actual_gap / expected_gap) - 1
            return DataQualityIssue(
                issue_type=DataIssueType.TIMESTAMP_GAP,
                symbol=candle.symbol,
                interval=candle.interval,
                timestamp=datetime.fromtimestamp(candle.timestamp / 1000),
                severity=min(1.0, missed_candles / 10),
                description=f"Gap detected: ~{missed_candles} candles missing",
                raw_data={
                    "previous_ts": previous.timestamp,
                    "current_ts": candle.timestamp,
                    "gap_ms": actual_gap,
                    "expected_ms": expected_gap,
                },
            )

        return None

    def _interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds."""
        mapping = {
            "1": 60000,
            "3": 180000,
            "5": 300000,
            "15": 900000,
            "30": 1800000,
            "60": 3600000,
            "120": 7200000,
            "240": 14400000,
            "360": 21600000,
            "720": 43200000,
            "D": 86400000,
            "W": 604800000,
        }
        return mapping.get(interval, 0)

    def _update_history(self, candle: CandleData) -> None:
        """Update historical data for the symbol."""
        key = self._get_key(candle.symbol, candle.interval)

        if key not in self._price_history:
            self._price_history[key] = deque(maxlen=self._history_size)
            self._volume_history[key] = deque(maxlen=self._history_size)

        self._price_history[key].append(candle.close)
        self._volume_history[key].append(candle.volume)
        self._timestamp_history[key] = candle.timestamp

    def _attempt_correction(
        self, candle: CandleData, issues: list[DataQualityIssue]
    ) -> CandleData | None:
        """Attempt to correct data issues."""
        # Only attempt correction for OHLC issues
        ohlc_issues = [i for i in issues if i.issue_type == DataIssueType.INVALID_OHLC]

        if not ohlc_issues:
            return None

        # Create corrected candle
        corrected = CandleData(
            timestamp=candle.timestamp,
            open=candle.open,
            high=max(candle.open, candle.high, candle.low, candle.close),
            low=min(candle.open, candle.high, candle.low, candle.close),
            close=candle.close,
            volume=candle.volume,
            symbol=candle.symbol,
            interval=candle.interval,
        )

        logger.info(f"Auto-corrected OHLC for {candle.symbol}:{candle.interval}")
        return corrected

    def check_staleness(self, symbol: str, interval: str) -> DataQualityIssue | None:
        """Check if data for a symbol is stale."""
        key = self._get_key(symbol, interval)

        if key not in self._timestamp_history:
            return None

        last_ts = self._timestamp_history[key]
        current_ts = int(time.time() * 1000)
        staleness_seconds = (current_ts - last_ts) / 1000

        if staleness_seconds > self.staleness_threshold_seconds:
            return DataQualityIssue(
                issue_type=DataIssueType.STALE_DATA,
                symbol=symbol,
                interval=interval,
                timestamp=datetime.now(),
                severity=min(
                    1.0, staleness_seconds / (self.staleness_threshold_seconds * 5)
                ),
                description=f"Data is {staleness_seconds:.0f}s old (threshold: {self.staleness_threshold_seconds}s)",
                raw_data={"staleness_seconds": staleness_seconds},
            )

        return None


class DataQualityMonitor:
    """
    Monitor for tracking data quality across multiple symbols.

    Aggregates quality metrics and provides reporting.
    """

    def __init__(self, validator: MarketDataValidator | None = None):
        self.validator = validator or MarketDataValidator()

        # Metrics per symbol/interval
        self._metrics: dict[str, DataQualityMetrics] = {}

        # Issue history
        self._issues: deque[DataQualityIssue] = deque(maxlen=1000)

        # Last candle per symbol/interval for comparison
        self._last_candle: dict[str, CandleData] = {}

        self._start_time = time.time()

    def _get_key(self, symbol: str, interval: str) -> str:
        """Generate key for symbol/interval pair."""
        return f"{symbol}:{interval}"

    def process_candle(self, candle: CandleData) -> ValidationResult:
        """Process and validate a candle."""
        key = self._get_key(candle.symbol, candle.interval)

        # Get previous candle for comparison
        previous = self._last_candle.get(key)

        # Validate
        result = self.validator.validate_candle(candle, previous)

        # Update metrics
        self._update_metrics(candle, result)

        # Store issues
        for issue in result.issues:
            self._issues.append(issue)

        # Update last candle
        self._last_candle[key] = candle

        return result

    def process_batch(
        self, candles: list[CandleData]
    ) -> tuple[list[ValidationResult], DataQualityMetrics]:
        """Process a batch of candles."""
        results = []

        # Sort by timestamp
        sorted_candles = sorted(candles, key=lambda c: c.timestamp)

        for candle in sorted_candles:
            result = self.process_candle(candle)
            results.append(result)

        # Get aggregated metrics
        if sorted_candles:
            key = self._get_key(sorted_candles[0].symbol, sorted_candles[0].interval)
            metrics = self._metrics.get(
                key,
                DataQualityMetrics(
                    symbol=sorted_candles[0].symbol,
                    interval=sorted_candles[0].interval,
                ),
            )
        else:
            metrics = DataQualityMetrics(symbol="", interval="")

        return results, metrics

    def _update_metrics(self, candle: CandleData, result: ValidationResult) -> None:
        """Update quality metrics."""
        key = self._get_key(candle.symbol, candle.interval)

        if key not in self._metrics:
            self._metrics[key] = DataQualityMetrics(
                symbol=candle.symbol,
                interval=candle.interval,
            )

        metrics = self._metrics[key]
        metrics.total_candles += 1

        if result.is_valid:
            metrics.valid_candles += 1
        else:
            metrics.issues_detected += len(result.issues)

            # Count specific issue types
            for issue in result.issues:
                if issue.issue_type == DataIssueType.TIMESTAMP_GAP:
                    metrics.gaps_detected += 1
                elif issue.issue_type == DataIssueType.PRICE_SPIKE:
                    metrics.spikes_detected += 1

        # Update quality score (exponential moving average)
        alpha = 0.1
        metrics.quality_score = (
            alpha * result.quality_score + (1 - alpha) * metrics.quality_score
        )

        metrics.last_update = datetime.now()

    def get_metrics(self, symbol: str, interval: str) -> DataQualityMetrics | None:
        """Get quality metrics for a symbol/interval."""
        key = self._get_key(symbol, interval)
        return self._metrics.get(key)

    def get_all_metrics(self) -> dict[str, DataQualityMetrics]:
        """Get all quality metrics."""
        return self._metrics.copy()

    def get_recent_issues(
        self,
        limit: int = 100,
        symbol: str | None = None,
        issue_type: DataIssueType | None = None,
    ) -> list[DataQualityIssue]:
        """Get recent quality issues."""
        issues = list(self._issues)

        if symbol:
            issues = [i for i in issues if i.symbol == symbol]

        if issue_type:
            issues = [i for i in issues if i.issue_type == issue_type]

        return issues[-limit:]

    def get_quality_level(self, score: float) -> DataQualityLevel:
        """Convert quality score to level."""
        if score >= 95:
            return DataQualityLevel.EXCELLENT
        elif score >= 80:
            return DataQualityLevel.GOOD
        elif score >= 60:
            return DataQualityLevel.ACCEPTABLE
        elif score >= 40:
            return DataQualityLevel.POOR
        else:
            return DataQualityLevel.CRITICAL

    def get_summary(self) -> dict[str, Any]:
        """Get data quality summary."""
        all_metrics = list(self._metrics.values())

        if not all_metrics:
            return {
                "symbols_monitored": 0,
                "overall_quality": 100.0,
                "quality_level": DataQualityLevel.EXCELLENT.value,
                "total_candles": 0,
                "total_issues": 0,
            }

        avg_quality = sum(m.quality_score for m in all_metrics) / len(all_metrics)
        total_candles = sum(m.total_candles for m in all_metrics)
        total_issues = sum(m.issues_detected for m in all_metrics)

        # Group by quality level
        by_level = {}
        for m in all_metrics:
            level = self.get_quality_level(m.quality_score).value
            by_level[level] = by_level.get(level, 0) + 1

        return {
            "symbols_monitored": len(all_metrics),
            "overall_quality": avg_quality,
            "quality_level": self.get_quality_level(avg_quality).value,
            "total_candles": total_candles,
            "total_issues": total_issues,
            "by_quality_level": by_level,
            "uptime_hours": (time.time() - self._start_time) / 3600,
        }

    def check_all_staleness(self) -> list[DataQualityIssue]:
        """Check staleness for all monitored symbols."""
        stale_issues = []

        for key in self._metrics:
            symbol, interval = key.split(":")
            issue = self.validator.check_staleness(symbol, interval)
            if issue:
                stale_issues.append(issue)
                self._issues.append(issue)

        return stale_issues


# Global monitor instance
_monitor: DataQualityMonitor | None = None


def get_data_quality_monitor() -> DataQualityMonitor:
    """Get or create global data quality monitor."""
    global _monitor
    if _monitor is None:
        _monitor = DataQualityMonitor()
    return _monitor
