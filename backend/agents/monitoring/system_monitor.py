"""
System Monitor for LLM Trading Agents.

Per spec section 6.1: tracks agent-level metrics including
success_rate, strategy_generation_time, backtest_duration,
llm_token_usage, api_costs, strategy_performance, and system_errors.

Provides singleton access, thread-safe metric tracking, and alerting.
"""

from __future__ import annotations

import statistics
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

__all__ = [
    "SystemMonitor",
    "get_system_monitor",
]


class SystemMonitor:
    """
    Monitors the LLM trading system.

    Tracks:
    - agent_success_rate: fraction of successful agent calls
    - strategy_generation_time: seconds per generation
    - backtest_duration: seconds per backtest
    - llm_token_usage: total tokens consumed
    - api_costs: estimated USD cost
    - strategy_performance: latest strategy quality scores
    - system_errors: count of errors
    """

    METRICS_TO_TRACK: list[str] = [
        "agent_success_rate",
        "strategy_generation_time",
        "backtest_duration",
        "llm_token_usage",
        "api_costs",
        "strategy_performance",
        "system_errors",
    ]

    ALERT_RULES: dict[str, dict[str, Any]] = {
        "agent_success_rate": {
            "threshold": 0.3,
            "condition": "lt",
            "message": "Low agent success rate",
            "severity": "warning",
        },
        "strategy_generation_time": {
            "threshold": 30.0,
            "condition": "gt",
            "message": "Slow strategy generation",
            "severity": "info",
        },
        "api_costs": {
            "threshold": 100.0,
            "condition": "gt_daily",
            "message": "High daily API costs",
            "severity": "warning",
        },
        "system_errors": {
            "threshold": 10,
            "condition": "gt_hourly",
            "message": "High error rate",
            "severity": "error",
        },
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics_history: dict[str, list[dict[str, Any]]] = {m: [] for m in self.METRICS_TO_TRACK}
        self._alerts: list[dict[str, Any]] = []
        self._total_runs: int = 0
        self._successful_runs: int = 0

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def track_metric(
        self,
        metric_name: str,
        value: float | int,
        timestamp: datetime | None = None,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a single metric value."""
        if metric_name not in self.METRICS_TO_TRACK:
            logger.warning(f"Unknown metric: {metric_name}")
            return

        ts = timestamp or datetime.now(UTC)
        entry: dict[str, Any] = {
            "timestamp": ts.isoformat(),
            "value": value,
        }
        if labels:
            entry["labels"] = labels

        with self._lock:
            self._metrics_history[metric_name].append(entry)

        # Check alert rules
        self._check_alerts(metric_name, value, ts)

    def record_pipeline_run(
        self,
        success: bool,
        generation_time_s: float = 0.0,
        backtest_time_s: float = 0.0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        quality_score: float = 0.0,
    ) -> None:
        """Convenience method to record a full pipeline run."""
        now = datetime.now(UTC)
        with self._lock:
            self._total_runs += 1
            if success:
                self._successful_runs += 1

        self.track_metric("agent_success_rate", 1.0 if success else 0.0, now)
        if generation_time_s > 0:
            self.track_metric("strategy_generation_time", generation_time_s, now)
        if backtest_time_s > 0:
            self.track_metric("backtest_duration", backtest_time_s, now)
        if tokens_used > 0:
            self.track_metric("llm_token_usage", tokens_used, now)
        if cost_usd > 0:
            self.track_metric("api_costs", cost_usd, now)
        if quality_score > 0:
            self.track_metric("strategy_performance", quality_score, now)
        if not success:
            self.track_metric("system_errors", 1, now)

    def record_error(self, error_msg: str = "") -> None:
        """Record an error occurrence."""
        self.track_metric(
            "system_errors",
            1,
            labels={"error": error_msg[:200]} if error_msg else None,
        )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Return aggregated metrics for the monitoring API."""
        with self._lock:
            history = {k: list(v) for k, v in self._metrics_history.items()}
            total = self._total_runs
            successful = self._successful_runs

        result: dict[str, Any] = {
            "total_runs": total,
        }

        # Agent success rate (overall)
        if total > 0:
            result["agent_success_rate"] = successful / total
        else:
            result["agent_success_rate"] = 0.0

        # Average generation time
        gen_times = [e["value"] for e in history["strategy_generation_time"]]
        result["strategy_generation_time"] = statistics.mean(gen_times) if gen_times else 0.0

        # Average backtest duration
        bt_times = [e["value"] for e in history["backtest_duration"]]
        result["backtest_duration"] = statistics.mean(bt_times) if bt_times else 0.0

        # Total token usage
        tokens = [e["value"] for e in history["llm_token_usage"]]
        result["llm_token_usage"] = int(sum(tokens))

        # Total API costs
        costs = [e["value"] for e in history["api_costs"]]
        result["api_costs"] = sum(costs)

        # Average strategy performance
        perf = [e["value"] for e in history["strategy_performance"]]
        result["strategy_performance"] = statistics.mean(perf) if perf else 0.0

        # Error count
        errors = history["system_errors"]
        result["system_errors"] = len(errors)

        return result

    def get_alerts(self, max_count: int = 50) -> list[dict[str, Any]]:
        """Return recent alerts."""
        with self._lock:
            return list(reversed(self._alerts[-max_count:]))

    def get_full_report(self) -> dict[str, Any]:
        """Return full monitoring report (metrics + alerts)."""
        return {
            "metrics": self.get_metrics_summary(),
            "alerts": self.get_alerts(),
        }

    def get_metrics_history(
        self,
        metric_name: str,
        last_n: int = 100,
    ) -> list[dict[str, Any]]:
        """Return raw history for a specific metric."""
        with self._lock:
            history = self._metrics_history.get(metric_name, [])
            return list(history[-last_n:])

    def reset(self) -> None:
        """Reset all metrics and alerts (for testing)."""
        with self._lock:
            self._metrics_history = {m: [] for m in self.METRICS_TO_TRACK}
            self._alerts = []
            self._total_runs = 0
            self._successful_runs = 0

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    def _check_alerts(
        self,
        metric_name: str,
        value: float | int,
        timestamp: datetime,
    ) -> None:
        """Evaluate alert rules and trigger if conditions are met."""
        if metric_name not in self.ALERT_RULES:
            return

        rule = self.ALERT_RULES[metric_name]
        triggered = False

        if (rule["condition"] == "lt" and value < rule["threshold"]) or (
            rule["condition"] == "gt" and value > rule["threshold"]
        ):
            triggered = True
        elif rule["condition"] == "gt_daily":
            triggered = self._check_daily_threshold(metric_name, rule["threshold"])
        elif rule["condition"] == "gt_hourly":
            triggered = self._check_hourly_threshold(metric_name, rule["threshold"])

        if triggered:
            self._trigger_alert(metric_name, value, rule, timestamp)

    def _check_daily_threshold(self, metric_name: str, threshold: float) -> bool:
        """Check if daily sum exceeds threshold."""
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with self._lock:
            entries = self._metrics_history.get(metric_name, [])

        daily_sum = 0.0
        for entry in entries:
            ts_str = entry["timestamp"]
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts >= day_start:
                    daily_sum += entry["value"]
            except (ValueError, TypeError):
                continue

        return daily_sum > threshold

    def _check_hourly_threshold(self, metric_name: str, threshold: float) -> bool:
        """Check if hourly count exceeds threshold."""
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)

        with self._lock:
            entries = self._metrics_history.get(metric_name, [])

        hourly_count = 0
        for entry in entries:
            ts_str = entry["timestamp"]
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts >= hour_ago:
                    hourly_count += 1
            except (ValueError, TypeError):
                continue

        return hourly_count > threshold

    def _trigger_alert(
        self,
        metric_name: str,
        value: float | int,
        rule: dict[str, Any],
        timestamp: datetime,
    ) -> None:
        """Record an alert."""
        alert = {
            "metric": metric_name,
            "value": value,
            "message": rule["message"],
            "severity": rule["severity"],
            "threshold": rule["threshold"],
            "timestamp": timestamp.isoformat(),
        }

        with self._lock:
            # Deduplicate: don't repeat same alert within 5 minutes
            recent = [a for a in self._alerts[-10:] if a["metric"] == metric_name]
            if recent:
                last_ts_str = recent[-1]["timestamp"]
                try:
                    last_ts = datetime.fromisoformat(last_ts_str)
                    if (timestamp - last_ts) < timedelta(minutes=5):
                        return  # Skip duplicate
                except (ValueError, TypeError):
                    pass

            self._alerts.append(alert)
            # Cap alerts list
            if len(self._alerts) > 500:
                self._alerts = self._alerts[-250:]

        logger.warning(
            f"Alert [{rule['severity']}] {rule['message']}: {metric_name}={value} (threshold={rule['threshold']})"
        )


# ------------------------------------------------------------------
# SINGLETON
# ------------------------------------------------------------------

_system_monitor: SystemMonitor | None = None
_monitor_lock = threading.Lock()


def get_system_monitor() -> SystemMonitor:
    """Get or create the global SystemMonitor singleton."""
    global _system_monitor
    if _system_monitor is None:
        with _monitor_lock:
            if _system_monitor is None:
                _system_monitor = SystemMonitor()
    return _system_monitor
