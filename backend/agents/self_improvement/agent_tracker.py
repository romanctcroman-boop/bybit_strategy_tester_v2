"""
Agent Performance Tracker

Per-agent accuracy tracking for dynamic ConsensusEngine weight adjustment.

Tracks each agent's (DeepSeek, Qwen, Perplexity) strategy quality over time:
- Strategy pass/fail rate
- Average Sharpe ratio achieved
- Win rate consistency
- Drawdown tendency
- Consensus agreement rate

These metrics feed back into ConsensusEngine._calculate_agent_weight()
to give higher weight to consistently better-performing agents.

Example:
    tracker = AgentPerformanceTracker()

    # Record after each backtest
    tracker.record_result("deepseek", backtest_metrics, strategy_passed=True)
    tracker.record_result("qwen", backtest_metrics, strategy_passed=False)

    # Get dynamic weights for consensus
    weights = tracker.compute_dynamic_weights(["deepseek", "qwen", "perplexity"])
    # → {"deepseek": 0.45, "qwen": 0.25, "perplexity": 0.30}

    # Apply to ConsensusEngine
    consensus_engine.set_external_weights(weights)
"""

from __future__ import annotations

import json
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class AgentRecord:
    """Single backtest record for an agent."""

    agent_name: str
    timestamp: datetime
    strategy_type: str
    fitness_score: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown_pct: float
    profit_factor: float
    total_trades: int
    passed: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "agent_name": self.agent_name,
            "timestamp": self.timestamp.isoformat(),
            "strategy_type": self.strategy_type,
            "fitness_score": round(self.fitness_score, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "total_trades": self.total_trades,
            "passed": self.passed,
        }


@dataclass
class AgentProfile:
    """Aggregated performance profile for one agent."""

    agent_name: str
    total_strategies: int = 0
    passed_strategies: int = 0
    avg_sharpe: float = 0.0
    avg_win_rate: float = 0.0
    avg_drawdown: float = 0.0
    avg_profit_factor: float = 0.0
    avg_fitness: float = 0.0
    sharpe_trend: float = 0.0  # positive = improving
    consistency_score: float = 0.0  # low variance = high consistency
    specialization_scores: dict[str, float] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def pass_rate(self) -> float:
        """Strategy pass rate."""
        if self.total_strategies == 0:
            return 0.0
        return self.passed_strategies / self.total_strategies

    @property
    def composite_score(self) -> float:
        """
        Composite performance score (0-100).

        Weights:
        - 30% Sharpe ratio contribution
        - 25% pass rate
        - 20% consistency
        - 15% profit factor
        - 10% low drawdown
        """
        sharpe_norm = min(max(self.avg_sharpe, 0), 3) / 3.0  # 0-3 → 0-1
        dd_norm = max(0, 1.0 - self.avg_drawdown / 50.0)  # 0-50% → 1-0
        pf_norm = min(max(self.avg_profit_factor, 0), 3) / 3.0

        score = sharpe_norm * 30 + self.pass_rate * 25 + self.consistency_score * 20 + pf_norm * 15 + dd_norm * 10
        return round(max(0, min(100, score)), 2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "agent_name": self.agent_name,
            "total_strategies": self.total_strategies,
            "passed_strategies": self.passed_strategies,
            "pass_rate": round(self.pass_rate, 4),
            "avg_sharpe": round(self.avg_sharpe, 4),
            "avg_win_rate": round(self.avg_win_rate, 4),
            "avg_drawdown": round(self.avg_drawdown, 2),
            "avg_profit_factor": round(self.avg_profit_factor, 4),
            "avg_fitness": round(self.avg_fitness, 2),
            "sharpe_trend": round(self.sharpe_trend, 4),
            "consistency_score": round(self.consistency_score, 4),
            "composite_score": self.composite_score,
            "specialization_scores": {k: round(v, 2) for k, v in self.specialization_scores.items()},
            "last_updated": self.last_updated.isoformat(),
        }


# =============================================================================
# AGENT PERFORMANCE TRACKER
# =============================================================================


class AgentPerformanceTracker:
    """
    Per-agent performance tracking for dynamic consensus weights.

    Maintains a rolling window of performance records for each agent
    and computes dynamic weights based on historical accuracy.

    Example:
        tracker = AgentPerformanceTracker(window_size=50)

        # Record results
        tracker.record_result(
            agent_name="deepseek",
            metrics={"sharpe_ratio": 1.5, "win_rate": 0.55, ...},
            strategy_type="rsi",
            passed=True,
            fitness_score=72.5,
        )

        # Get dynamic weights
        weights = tracker.compute_dynamic_weights(
            agents=["deepseek", "qwen", "perplexity"]
        )

        # Get agent profile
        profile = tracker.get_profile("deepseek")
        print(f"DeepSeek composite: {profile.composite_score}")
    """

    # Weight computation parameters
    DEFAULT_WEIGHT = 1.0  # Weight for agents with no history
    MIN_WEIGHT = 0.1  # Minimum weight floor
    RECENCY_FACTOR = 0.8  # How much recent performance matters (0-1)
    MIN_RECORDS_FOR_WEIGHT = 3  # Minimum records before custom weight

    def __init__(
        self,
        *,
        window_size: int = 100,
        persist_path: str | None = None,
    ):
        """
        Initialize tracker.

        Args:
            window_size: Rolling window size for performance history
            persist_path: Optional path to persist tracking data
        """
        self.window_size = window_size
        self.persist_path = Path(persist_path) if persist_path else None

        # Per-agent record deques
        self._records: dict[str, deque[AgentRecord]] = {}

        # Cached profiles
        self._profiles: dict[str, AgentProfile] = {}

        # Load persisted data
        if self.persist_path:
            self._load_data()

        logger.info(f"📊 AgentPerformanceTracker initialized: window={window_size}")

    def record_result(
        self,
        agent_name: str,
        metrics: dict[str, Any],
        *,
        strategy_type: str = "unknown",
        passed: bool = True,
        fitness_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRecord:
        """
        Record a backtest result for an agent.

        Args:
            agent_name: Agent identifier (e.g., "deepseek", "qwen")
            metrics: Backtest metrics dict
            strategy_type: Type of strategy tested
            passed: Whether strategy met quality threshold
            fitness_score: Computed fitness score
            metadata: Additional metadata

        Returns:
            Created AgentRecord
        """
        record = AgentRecord(
            agent_name=agent_name,
            timestamp=datetime.now(UTC),
            strategy_type=strategy_type,
            fitness_score=fitness_score,
            sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
            win_rate=float(metrics.get("win_rate", 0)),
            max_drawdown_pct=float(metrics.get("max_drawdown_pct", 0)),
            profit_factor=float(metrics.get("profit_factor", 0)),
            total_trades=int(metrics.get("total_trades", 0)),
            passed=passed,
            metadata=metadata or {},
        )

        # Add to rolling window
        if agent_name not in self._records:
            self._records[agent_name] = deque(maxlen=self.window_size)
        self._records[agent_name].append(record)

        # Update profile
        self._update_profile(agent_name)

        # Persist
        if self.persist_path:
            self._persist_record(record)

        logger.debug(
            f"📊 Recorded {agent_name}: fitness={fitness_score:.1f}, sharpe={record.sharpe_ratio:.2f}, passed={passed}"
        )

        return record

    def get_profile(self, agent_name: str) -> AgentProfile:
        """
        Get aggregated performance profile for an agent.

        Args:
            agent_name: Agent identifier

        Returns:
            AgentProfile with aggregated stats
        """
        if agent_name in self._profiles:
            return self._profiles[agent_name]

        # Return empty profile for unknown agents
        return AgentProfile(agent_name=agent_name)

    def compute_dynamic_weights(
        self,
        agents: list[str],
        *,
        method: str = "composite",
    ) -> dict[str, float]:
        """
        Compute dynamic weights for consensus engine.

        Args:
            agents: List of agent names to compute weights for
            method: Weight method ("composite", "sharpe", "pass_rate")

        Returns:
            Normalized weights dict summing to 1.0
        """
        raw_weights: dict[str, float] = {}

        for agent in agents:
            profile = self.get_profile(agent)

            if profile.total_strategies < self.MIN_RECORDS_FOR_WEIGHT:
                # Not enough data — use default weight
                raw_weights[agent] = self.DEFAULT_WEIGHT
                continue

            if method == "composite":
                # Use composite score (0-100 → weight)
                raw_weights[agent] = max(
                    self.MIN_WEIGHT,
                    profile.composite_score / 50.0,  # 50 → 1.0, 100 → 2.0
                )
            elif method == "sharpe":
                # Weight by average Sharpe ratio
                raw_weights[agent] = max(
                    self.MIN_WEIGHT,
                    (profile.avg_sharpe + 1) / 2.0,
                )
            elif method == "pass_rate":
                # Weight by pass rate
                raw_weights[agent] = max(
                    self.MIN_WEIGHT,
                    profile.pass_rate + 0.1,
                )
            else:
                raw_weights[agent] = self.DEFAULT_WEIGHT

            # Apply recency bonus
            if profile.sharpe_trend > 0:
                raw_weights[agent] *= 1.0 + self.RECENCY_FACTOR * min(profile.sharpe_trend, 0.5)

        # Normalize to sum=1
        total = sum(raw_weights.values())
        if total <= 0:
            uniform = 1.0 / len(agents) if agents else 1.0
            return dict.fromkeys(agents, uniform)

        return {k: round(v / total, 4) for k, v in raw_weights.items()}

    def get_leaderboard(self) -> list[dict[str, Any]]:
        """
        Get sorted leaderboard of agent performance.

        Returns:
            List of agent profiles sorted by composite score
        """
        profiles = [self.get_profile(agent) for agent in self._records]
        profiles.sort(key=lambda p: p.composite_score, reverse=True)
        return [p.to_dict() for p in profiles]

    def get_comparison(
        self,
        agents: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Get side-by-side comparison of agents.

        Args:
            agents: Optional list of agents to compare (all if None)

        Returns:
            Dict of agent_name → profile dict
        """
        if agents is None:
            agents = list(self._records.keys())

        return {agent: self.get_profile(agent).to_dict() for agent in agents}

    def get_specialization_analysis(
        self,
        agent_name: str,
    ) -> dict[str, float]:
        """
        Analyze which strategy types an agent excels at.

        Args:
            agent_name: Agent identifier

        Returns:
            Dict of strategy_type → average fitness
        """
        records = self._records.get(agent_name, deque())
        type_scores: dict[str, list[float]] = {}

        for record in records:
            if record.strategy_type not in type_scores:
                type_scores[record.strategy_type] = []
            type_scores[record.strategy_type].append(record.fitness_score)

        return {st: round(statistics.mean(scores), 2) for st, scores in type_scores.items() if scores}

    def sync_to_consensus_engine(self, consensus_engine) -> None:
        """
        Sync performance data to ConsensusEngine.update_performance().

        Args:
            consensus_engine: ConsensusEngine instance to update
        """
        for agent_name, profile in self._profiles.items():
            if profile.total_strategies > 0:
                consensus_engine.update_performance(
                    agent_name=agent_name,
                    sharpe=profile.avg_sharpe,
                    profit_factor=profile.avg_profit_factor,
                    win_rate=profile.avg_win_rate,
                    backtest_passed=profile.pass_rate > 0.5,
                )

        logger.info(f"📊 Synced {len(self._profiles)} agent profiles to ConsensusEngine")

    def get_stats(self) -> dict[str, Any]:
        """Get tracker statistics."""
        return {
            "tracked_agents": len(self._records),
            "total_records": sum(len(r) for r in self._records.values()),
            "window_size": self.window_size,
            "agents": {
                name: {
                    "records": len(records),
                    "composite_score": self.get_profile(name).composite_score,
                }
                for name, records in self._records.items()
            },
        }

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _update_profile(self, agent_name: str) -> None:
        """Recalculate aggregated profile from records."""
        records = list(self._records.get(agent_name, []))
        if not records:
            return

        profile = AgentProfile(agent_name=agent_name)
        profile.total_strategies = len(records)
        profile.passed_strategies = sum(1 for r in records if r.passed)

        # Averages
        sharpes = [r.sharpe_ratio for r in records]
        profile.avg_sharpe = statistics.mean(sharpes)
        profile.avg_win_rate = statistics.mean(r.win_rate for r in records)
        profile.avg_drawdown = statistics.mean(r.max_drawdown_pct for r in records)
        profile.avg_profit_factor = statistics.mean(r.profit_factor for r in records)
        profile.avg_fitness = statistics.mean(r.fitness_score for r in records)

        # Sharpe trend (linear regression slope approximation)
        if len(sharpes) >= 3:
            n = len(sharpes)
            mid = n // 2
            first_half = statistics.mean(sharpes[:mid]) if sharpes[:mid] else 0
            second_half = statistics.mean(sharpes[mid:]) if sharpes[mid:] else 0
            profile.sharpe_trend = second_half - first_half
        else:
            profile.sharpe_trend = 0.0

        # Consistency (inverse of coefficient of variation)
        if len(sharpes) >= 2:
            std = statistics.stdev(sharpes)
            mean = abs(statistics.mean(sharpes)) or 1.0
            cv = std / mean  # Coefficient of variation
            profile.consistency_score = max(0, 1.0 - cv)  # Lower CV = higher consistency
        else:
            profile.consistency_score = 0.5  # Default for single record

        # Specialization scores
        profile.specialization_scores = self.get_specialization_analysis(agent_name)

        profile.last_updated = datetime.now(UTC)
        self._profiles[agent_name] = profile

    def _persist_record(self, record: AgentRecord) -> None:
        """Persist record to disk."""
        if not self.persist_path:
            return

        agent_dir = self.persist_path / record.agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)

        file_path = agent_dir / f"{record.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist record: {e}")

    def _load_data(self) -> None:
        """Load persisted data from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return

        count = 0
        for agent_dir in self.persist_path.iterdir():
            if agent_dir.is_dir():
                for json_file in sorted(agent_dir.glob("*.json")):
                    try:
                        with open(json_file, encoding="utf-8") as f:
                            data = json.load(f)
                        record = AgentRecord(
                            agent_name=data["agent_name"],
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            strategy_type=data.get("strategy_type", "unknown"),
                            fitness_score=data.get("fitness_score", 0),
                            sharpe_ratio=data.get("sharpe_ratio", 0),
                            win_rate=data.get("win_rate", 0),
                            max_drawdown_pct=data.get("max_drawdown_pct", 0),
                            profit_factor=data.get("profit_factor", 0),
                            total_trades=data.get("total_trades", 0),
                            passed=data.get("passed", False),
                        )
                        if record.agent_name not in self._records:
                            self._records[record.agent_name] = deque(maxlen=self.window_size)
                        self._records[record.agent_name].append(record)
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to load {json_file}: {e}")

        # Rebuild profiles
        for agent_name in self._records:
            self._update_profile(agent_name)

        logger.info(f"📂 Loaded {count} performance records")

    def reset(self, agent_name: str | None = None) -> None:
        """
        Reset tracking data.

        Args:
            agent_name: Optional specific agent to reset (all if None)
        """
        if agent_name:
            self._records.pop(agent_name, None)
            self._profiles.pop(agent_name, None)
        else:
            self._records.clear()
            self._profiles.clear()

        logger.info(f"📊 Reset tracker: {agent_name or 'all'}")


__all__ = [
    "AgentPerformanceTracker",
    "AgentProfile",
    "AgentRecord",
]
