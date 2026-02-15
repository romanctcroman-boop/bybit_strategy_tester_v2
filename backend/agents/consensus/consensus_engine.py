"""
Consensus Engine — aggregation of strategies from multiple LLM agents.

Implements strategy-level consensus mechanisms from the spec (Section 3.4):
- Weighted Voting: signal-level aggregation by agent weight
- Bayesian Aggregation: posterior-based combination with historical accuracy
- Agreement scoring (Jaccard similarity between signal sets)
- Dynamic agent weights based on historical performance
- Consensus parameter calculation (median/weighted mean)

This is distinct from deliberation.py which handles text-level debate.
ConsensusEngine operates on StrategyDefinition objects (structured data).

Usage:
    engine = ConsensusEngine()
    consensus = engine.aggregate(
        strategies={"deepseek": strategy1, "qwen": strategy2},
        method="weighted_voting",
    )
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from loguru import logger

from backend.agents.prompts.response_parser import (
    AgentMetadata,
    ExitCondition,
    ExitConditions,
    Filter,
    OptimizationHints,
    Signal,
    StrategyDefinition,
)

# =============================================================================
# ENUMS & MODELS
# =============================================================================


class ConsensusMethod(str, Enum):
    """Available consensus methods."""

    WEIGHTED_VOTING = "weighted_voting"
    BAYESIAN = "bayesian_aggregation"
    BEST_OF = "best_of"


@dataclass
class AgentPerformance:
    """Historical performance record for a single agent."""

    agent_name: str
    total_strategies: int = 0
    successful_backtests: int = 0
    avg_sharpe: float = 0.0
    avg_profit_factor: float = 0.0
    avg_win_rate: float = 0.0
    cumulative_score: float = 0.0

    @property
    def success_rate(self) -> float:
        """Fraction of strategies that passed backtest."""
        if self.total_strategies == 0:
            return 0.5  # prior
        return self.successful_backtests / self.total_strategies


@dataclass
class ConsensusResult:
    """Result of strategy consensus aggregation."""

    strategy: StrategyDefinition
    method: str
    agreement_score: float
    agent_weights: dict[str, float]
    input_agents: list[str]
    signal_votes: dict[str, int]  # signal_type → vote count
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/logging."""
        return {
            "strategy_name": self.strategy.strategy_name,
            "method": self.method,
            "agreement_score": round(self.agreement_score, 4),
            "agent_weights": {k: round(v, 4) for k, v in self.agent_weights.items()},
            "input_agents": self.input_agents,
            "signal_votes": self.signal_votes,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# CONSENSUS ENGINE
# =============================================================================

# Minimum normalized weight for a signal to be included in consensus
_SIGNAL_INCLUSION_THRESHOLD = 0.25

# Maximum number of signals in the final strategy
_MAX_CONSENSUS_SIGNALS = 4

# Maximum number of filters
_MAX_CONSENSUS_FILTERS = 3


class ConsensusEngine:
    """
    Aggregates StrategyDefinition objects from multiple LLM agents
    into a single consensus strategy.

    Supports three methods:
    - weighted_voting: signal-level aggregation by agent weight
    - bayesian_aggregation: prior x likelihood update
    - best_of: pick the single best strategy by heuristic score

    Agent weights are calculated from historical performance if available,
    and adjusted by each strategy's own confidence/quality signals.

    Example:
        engine = ConsensusEngine()

        # Register historical performance (optional)
        engine.update_performance("deepseek", sharpe=1.8, win_rate=0.55)

        result = engine.aggregate(
            strategies={"deepseek": s1, "qwen": s2},
            method="weighted_voting",
        )
        print(result.strategy.strategy_name)
        print(result.agreement_score)
    """

    def __init__(self) -> None:
        self._performance: dict[str, AgentPerformance] = {}
        self._history: list[ConsensusResult] = []

    # ─────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────

    def aggregate(
        self,
        strategies: dict[str, StrategyDefinition],
        method: str = "weighted_voting",
        market_context: dict[str, Any] | None = None,
    ) -> ConsensusResult:
        """
        Aggregate strategies from multiple agents into one consensus strategy.

        Args:
            strategies: Agent name → StrategyDefinition mapping
            method: Consensus method (weighted_voting, bayesian_aggregation, best_of)
            market_context: Optional market context for naming

        Returns:
            ConsensusResult with the consensus strategy and metadata
        """
        if not strategies:
            raise ValueError("Cannot aggregate empty strategies dict")

        # Single strategy → return as-is
        if len(strategies) == 1:
            agent_name, strategy = next(iter(strategies.items()))
            result = ConsensusResult(
                strategy=strategy,
                method="single_agent",
                agreement_score=1.0,
                agent_weights={agent_name: 1.0},
                input_agents=[agent_name],
                signal_votes={s.type: 1 for s in strategy.signals},
            )
            self._history.append(result)
            return result

        # Calculate agent weights
        agent_weights = self._calculate_all_weights(strategies)

        # Dispatch to method
        if method == ConsensusMethod.BAYESIAN:
            consensus_strategy = self._bayesian_aggregation(strategies, agent_weights)
        elif method == ConsensusMethod.BEST_OF:
            consensus_strategy = self._best_of(strategies, agent_weights)
        else:
            consensus_strategy = self._weighted_voting(strategies, agent_weights)

        # Agreement score
        agreement = self._calculate_agreement_score(strategies)

        # Signal vote counts
        signal_votes = self._count_signal_votes(strategies)

        # Name the strategy
        symbol = (market_context or {}).get("symbol", "")
        date_str = datetime.now(UTC).strftime("%Y%m%d")
        consensus_strategy.strategy_name = f"Consensus_{symbol}_{date_str}" if symbol else f"Consensus_{date_str}"
        consensus_strategy.description = (
            f"Consensus strategy from {len(strategies)} agents "
            f"({', '.join(strategies.keys())}), "
            f"method={method}, agreement={agreement:.2f}"
        )

        result = ConsensusResult(
            strategy=consensus_strategy,
            method=method,
            agreement_score=agreement,
            agent_weights=agent_weights,
            input_agents=list(strategies.keys()),
            signal_votes=signal_votes,
        )
        self._history.append(result)

        logger.info(
            f"🤝 Consensus: {len(strategies)} agents → "
            f"{len(consensus_strategy.signals)} signals, "
            f"agreement={agreement:.2%}, method={method}"
        )
        return result

    def update_performance(
        self,
        agent_name: str,
        sharpe: float = 0.0,
        profit_factor: float = 0.0,
        win_rate: float = 0.0,
        backtest_passed: bool = True,
    ) -> None:
        """
        Update an agent's historical performance record.

        Called after a backtest run to track agent accuracy over time.
        Agent weights in future consensus rounds will reflect this history.

        Args:
            agent_name: Agent identifier (e.g. "deepseek")
            sharpe: Sharpe ratio from backtest
            profit_factor: Profit factor
            win_rate: Win rate (0-1)
            backtest_passed: Whether the strategy met quality threshold
        """
        if agent_name not in self._performance:
            self._performance[agent_name] = AgentPerformance(agent_name=agent_name)

        perf = self._performance[agent_name]
        perf.total_strategies += 1
        if backtest_passed:
            perf.successful_backtests += 1

        # Running average update
        n = perf.total_strategies
        perf.avg_sharpe = perf.avg_sharpe + (sharpe - perf.avg_sharpe) / n
        perf.avg_profit_factor = perf.avg_profit_factor + (profit_factor - perf.avg_profit_factor) / n
        perf.avg_win_rate = perf.avg_win_rate + (win_rate - perf.avg_win_rate) / n

        # Composite score
        perf.cumulative_score = (
            0.4 * perf.avg_sharpe
            + 0.3 * perf.avg_profit_factor
            + 0.2 * perf.avg_win_rate * 10  # scale 0-1 → 0-10
            + 0.1 * perf.success_rate * 10
        )

        logger.debug(
            f"📊 Updated {agent_name} performance: "
            f"success_rate={perf.success_rate:.2%}, "
            f"avg_sharpe={perf.avg_sharpe:.2f}, "
            f"score={perf.cumulative_score:.2f}"
        )

    def get_performance(self, agent_name: str) -> AgentPerformance | None:
        """Get an agent's performance record."""
        return self._performance.get(agent_name)

    @property
    def history(self) -> list[ConsensusResult]:
        """Get consensus history."""
        return list(self._history)

    async def build_memory_context(
        self,
        topic: str,
        max_items: int = 3,
    ) -> str | None:
        """P5.3: Build prior consensus context from memory.

        Queries hierarchical memory for previous deliberation results
        tagged with "deliberation" and formats them for prompt injection.
        Deduplicates: excludes results from the current session (last 5 min).

        Args:
            topic: The current deliberation topic for relevance matching.
            max_items: Maximum number of prior results to include.

        Returns:
            Formatted context string, or None if no prior results found.
        """
        try:
            from backend.agents.mcp.tools.memory import get_global_memory

            memory = get_global_memory()

            results = await memory.recall(
                query=topic,
                memory_type=None,
                top_k=max_items,
                min_importance=0.3,
                tags=["deliberation"],
                agent_namespace=None,
            )

            if not results:
                return None

            # Deduplicate: skip items created in the last 5 minutes
            from datetime import UTC, datetime, timedelta

            cutoff = datetime.now(UTC) - timedelta(minutes=5)
            prior = [r for r in results if r.created_at < cutoff]
            if not prior:
                return None

            lines = ["## Prior Consensus Results"]
            for i, item in enumerate(prior, 1):
                tier = item.memory_type.value.upper()
                lines.append(f"{i}. [{tier}, importance={item.importance:.2f}] {item.content[:300]}")

            context = "\n".join(lines)

            logger.info(f"🧠 P5.3: Built memory context with {len(prior)} prior consensus results")
            return context

        except Exception as e:
            logger.warning(f"P5.3: Failed to build memory context: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # WEIGHT CALCULATION
    # ─────────────────────────────────────────────────────────────────

    def _calculate_all_weights(
        self,
        strategies: dict[str, StrategyDefinition],
    ) -> dict[str, float]:
        """
        Calculate normalized weights for each agent.

        Weight formula:
            raw = base_weight x historical_factor x strategy_quality_factor
            normalized = raw / sum(all_raw)
        """
        raw_weights: dict[str, float] = {}

        for agent_name, strategy in strategies.items():
            raw_weights[agent_name] = self._calculate_agent_weight(agent_name, strategy)

        # Normalize to sum=1
        total = sum(raw_weights.values())
        if total <= 0:
            # Uniform fallback
            uniform = 1.0 / len(strategies)
            return dict.fromkeys(strategies, uniform)

        return {k: v / total for k, v in raw_weights.items()}

    def _calculate_agent_weight(
        self,
        agent_name: str,
        strategy: StrategyDefinition,
    ) -> float:
        """
        Calculate raw weight for a single agent.

        Factors:
        - Base weight: 1.0
        - Historical accuracy: success_rate x (sharpe + 1) / 2
        - Strategy quality: signal count, exit conditions, etc.
        - Agent specialization bonus
        """
        base_weight = 1.0

        # Historical performance factor
        perf = self._performance.get(agent_name)
        if perf and perf.total_strategies > 0:
            historical_factor = perf.success_rate * max(0, perf.avg_sharpe + 1) / 2
            base_weight *= max(0.1, historical_factor)  # floor at 0.1

        # Strategy quality factor
        quality = self._assess_strategy_quality(strategy)
        base_weight *= quality

        # Agent specialization bonus
        specialization = ""
        if strategy.agent_metadata:
            specialization = strategy.agent_metadata.specialization

        if specialization == "quantitative_analyst":
            base_weight *= 1.2  # quants get a slight bonus
        elif specialization == "technical_analyst":
            base_weight *= 1.1

        return max(0.01, base_weight)

    @staticmethod
    def _assess_strategy_quality(strategy: StrategyDefinition) -> float:
        """
        Heuristic quality score for a strategy (0.5-1.5).

        Good strategies have:
        - 2-3 signals (not too few, not too many)
        - Both TP and SL
        - At least one filter
        - Entry conditions specified
        """
        score = 1.0

        # Signal count
        n_signals = len(strategy.signals)
        if 2 <= n_signals <= 3:
            score += 0.15
        elif n_signals == 1:
            score -= 0.1
        elif n_signals > 4:
            score -= 0.15

        # Exit conditions
        if strategy.exit_conditions:
            if strategy.exit_conditions.take_profit:
                score += 0.1
            if strategy.exit_conditions.stop_loss:
                score += 0.1

        # Filters
        if strategy.filters:
            score += 0.05 * min(len(strategy.filters), 3)

        # Entry conditions
        if strategy.entry_conditions and (strategy.entry_conditions.long or strategy.entry_conditions.short):
            score += 0.05

        return max(0.5, min(1.5, score))

    # ─────────────────────────────────────────────────────────────────
    # CONSENSUS METHODS
    # ─────────────────────────────────────────────────────────────────

    def _weighted_voting(
        self,
        strategies: dict[str, StrategyDefinition],
        agent_weights: dict[str, float],
    ) -> StrategyDefinition:
        """
        Weighted voting: aggregate signals across agents by weight.

        1. Collect all signals across agents, keyed by type+timeframe
        2. Accumulate weights for each signal key
        3. Select top signals above threshold
        4. Merge parameters via weighted median
        5. Build exit conditions, filters, position mgmt from best agent
        """
        # ── Collect signal votes ──
        signal_pool: dict[str, dict] = {}  # key → aggregation info

        for agent_name, strategy in strategies.items():
            weight = agent_weights.get(agent_name, 0.0)
            for signal in strategy.signals:
                key = signal.type  # group by indicator type
                if key not in signal_pool:
                    signal_pool[key] = {
                        "type": signal.type,
                        "total_weight": 0.0,
                        "votes": [],
                        "params_list": [],
                        "conditions": [],
                    }
                signal_pool[key]["total_weight"] += weight
                signal_pool[key]["votes"].append(agent_name)
                signal_pool[key]["params_list"].append(signal.params)
                if signal.condition:
                    signal_pool[key]["conditions"].append(signal.condition)

        # ── Select top signals by weight ──
        sorted_signals = sorted(
            signal_pool.items(),
            key=lambda x: x[1]["total_weight"],
            reverse=True,
        )

        consensus_signals: list[Signal] = []
        for signal_key, info in sorted_signals[:_MAX_CONSENSUS_SIGNALS]:
            normalized_weight = info["total_weight"] / max(sum(agent_weights.values()), 1e-9)
            if normalized_weight < _SIGNAL_INCLUSION_THRESHOLD:
                continue

            # Merge parameters via median
            merged_params = self._merge_params(info["params_list"])

            consensus_signals.append(
                Signal(
                    id=f"consensus_{signal_key.lower()}",
                    type=info["type"],
                    params=merged_params,
                    weight=round(normalized_weight, 3),
                    condition=info["conditions"][0] if info["conditions"] else "",
                )
            )

        # If no signals survived threshold, take the top 1
        if not consensus_signals and sorted_signals:
            top_key, top_info = sorted_signals[0]
            merged_params = self._merge_params(top_info["params_list"])
            consensus_signals.append(
                Signal(
                    id=f"consensus_{top_key.lower()}",
                    type=top_info["type"],
                    params=merged_params,
                    weight=1.0,
                    condition=top_info["conditions"][0] if top_info["conditions"] else "",
                )
            )

        # ── Build remaining fields from best-weighted agent ──
        best_agent = max(agent_weights, key=lambda k: agent_weights[k])
        best_strategy = strategies[best_agent]

        # Merge filters (union, deduplicated by type)
        merged_filters = self._merge_filters(strategies, agent_weights)

        # If multiple agents define exits, average the values
        exit_conditions = self._merge_exit_conditions(strategies, agent_weights)

        # Entry conditions from best agent
        entry_conditions = best_strategy.entry_conditions

        # Position management from best agent
        position_management = best_strategy.position_management

        # Optimization hints — union of all suggested params
        optimization_hints = self._merge_optimization_hints(strategies)

        return StrategyDefinition(
            strategy_name="",  # will be set by aggregate()
            description="",
            signals=consensus_signals,
            filters=merged_filters,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            position_management=position_management,
            optimization_hints=optimization_hints,
            agent_metadata=AgentMetadata(
                agent_name="consensus",
                model="multi_agent",
                specialization="consensus",
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )

    def _bayesian_aggregation(
        self,
        strategies: dict[str, StrategyDefinition],
        agent_weights: dict[str, float],
    ) -> StrategyDefinition:
        """
        Bayesian aggregation: treat agent weights as prior,
        signal overlap as likelihood, compute posterior weights.

        Posterior ~ Prior x Likelihood
        where Likelihood for each signal ∝ number of agents supporting it.
        """
        n_agents = len(strategies)

        # Collect signal support counts
        signal_support: dict[str, int] = defaultdict(int)
        for strategy in strategies.values():
            for signal in strategy.signals:
                signal_support[signal.type] += 1

        # Prior from agent weights (already normalized)
        # Likelihood: fraction of agents that include this signal
        signal_pool: dict[str, dict] = {}

        for agent_name, strategy in strategies.items():
            prior = agent_weights.get(agent_name, 1.0 / n_agents)
            for signal in strategy.signals:
                key = signal.type
                likelihood = signal_support[key] / n_agents  # support fraction

                if key not in signal_pool:
                    signal_pool[key] = {
                        "type": signal.type,
                        "posterior_sum": 0.0,
                        "params_list": [],
                        "conditions": [],
                        "support_count": signal_support[key],
                    }
                # Posterior ~ prior x likelihood
                posterior = prior * likelihood
                signal_pool[key]["posterior_sum"] += posterior
                signal_pool[key]["params_list"].append(signal.params)
                if signal.condition:
                    signal_pool[key]["conditions"].append(signal.condition)

        # Normalize posteriors
        total_posterior = sum(info["posterior_sum"] for info in signal_pool.values())
        if total_posterior <= 0:
            total_posterior = 1.0

        # Select signals by posterior
        sorted_signals = sorted(
            signal_pool.items(),
            key=lambda x: x[1]["posterior_sum"],
            reverse=True,
        )

        consensus_signals: list[Signal] = []
        for signal_key, info in sorted_signals[:_MAX_CONSENSUS_SIGNALS]:
            normalized = info["posterior_sum"] / total_posterior
            if normalized < _SIGNAL_INCLUSION_THRESHOLD / 2:  # lower threshold for Bayesian
                continue

            merged_params = self._merge_params(info["params_list"])
            consensus_signals.append(
                Signal(
                    id=f"bayesian_{signal_key.lower()}",
                    type=info["type"],
                    params=merged_params,
                    weight=round(normalized, 3),
                    condition=info["conditions"][0] if info["conditions"] else "",
                )
            )

        if not consensus_signals and sorted_signals:
            top_key, top_info = sorted_signals[0]
            consensus_signals.append(
                Signal(
                    id=f"bayesian_{top_key.lower()}",
                    type=top_info["type"],
                    params=self._merge_params(top_info["params_list"]),
                    weight=1.0,
                    condition=top_info["conditions"][0] if top_info["conditions"] else "",
                )
            )

        # Build remaining fields from best agent
        best_agent = max(agent_weights, key=lambda k: agent_weights[k])
        best_strategy = strategies[best_agent]

        return StrategyDefinition(
            strategy_name="",
            description="",
            signals=consensus_signals,
            filters=self._merge_filters(strategies, agent_weights),
            entry_conditions=best_strategy.entry_conditions,
            exit_conditions=self._merge_exit_conditions(strategies, agent_weights),
            position_management=best_strategy.position_management,
            optimization_hints=self._merge_optimization_hints(strategies),
            agent_metadata=AgentMetadata(
                agent_name="consensus_bayesian",
                model="multi_agent",
                specialization="bayesian",
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )

    def _best_of(
        self,
        strategies: dict[str, StrategyDefinition],
        agent_weights: dict[str, float],
    ) -> StrategyDefinition:
        """
        Best-of: pick the single best strategy based on
        agent weight x strategy quality.
        """
        scored: list[tuple[float, str, StrategyDefinition]] = []
        for agent_name, strategy in strategies.items():
            weight = agent_weights.get(agent_name, 0.0)
            quality = self._assess_strategy_quality(strategy)
            score = weight * quality
            scored.append((score, agent_name, strategy))

        scored.sort(key=lambda x: x[0], reverse=True)
        _, best_agent, best_strategy = scored[0]

        logger.info(f"🏆 Best-of consensus selected '{best_agent}' (score={scored[0][0]:.3f})")
        return best_strategy

    # ─────────────────────────────────────────────────────────────────
    # MERGING HELPERS
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_params(params_list: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Merge signal parameters from multiple agents via median.

        For numeric values: take median.
        For non-numeric: take most common.
        """
        if not params_list:
            return {}
        if len(params_list) == 1:
            return dict(params_list[0])

        # Collect values per key
        all_keys: set[str] = set()
        for p in params_list:
            all_keys.update(p.keys())

        merged: dict[str, Any] = {}
        for key in all_keys:
            values = [p[key] for p in params_list if key in p]
            if not values:
                continue

            # Numeric → median
            if all(isinstance(v, int | float) for v in values):
                median_val = statistics.median(values)
                # If all inputs were ints, keep as int
                if all(isinstance(v, int) for v in values):
                    merged[key] = round(median_val)
                else:
                    merged[key] = round(median_val, 4)
            else:
                # Non-numeric → most common
                from collections import Counter

                counter = Counter(str(v) for v in values)
                merged[key] = counter.most_common(1)[0][0]

        return merged

    @staticmethod
    def _merge_filters(
        strategies: dict[str, StrategyDefinition],
        agent_weights: dict[str, float],
    ) -> list[Filter]:
        """Merge filters: deduplicate by type, keep highest-weight version."""
        seen_types: dict[str, tuple[float, Filter]] = {}

        for agent_name, strategy in strategies.items():
            weight = agent_weights.get(agent_name, 0.0)
            for f in strategy.filters:
                existing = seen_types.get(f.type)
                if existing is None or weight > existing[0]:
                    seen_types[f.type] = (weight, f)

        filters = [f for _, f in sorted(seen_types.values(), key=lambda x: x[0], reverse=True)]
        return filters[:_MAX_CONSENSUS_FILTERS]

    @staticmethod
    def _merge_exit_conditions(
        strategies: dict[str, StrategyDefinition],
        agent_weights: dict[str, float],
    ) -> ExitConditions:
        """
        Merge exit conditions: weighted average of TP/SL values.
        """
        tp_values: list[tuple[float, float, str]] = []  # (weight, value, type)
        sl_values: list[tuple[float, float, str]] = []

        for agent_name, strategy in strategies.items():
            weight = agent_weights.get(agent_name, 0.0)
            if strategy.exit_conditions:
                if strategy.exit_conditions.take_profit:
                    tp_values.append(
                        (
                            weight,
                            strategy.exit_conditions.take_profit.value,
                            strategy.exit_conditions.take_profit.type,
                        )
                    )
                if strategy.exit_conditions.stop_loss:
                    sl_values.append(
                        (
                            weight,
                            strategy.exit_conditions.stop_loss.value,
                            strategy.exit_conditions.stop_loss.type,
                        )
                    )

        tp = None
        if tp_values:
            total_w = sum(w for w, _, _ in tp_values)
            if total_w > 0:
                avg_val = sum(w * v for w, v, _ in tp_values) / total_w
                # Use the type from the highest-weight agent
                best_type = max(tp_values, key=lambda x: x[0])[2]
                tp = ExitCondition(
                    type=best_type,
                    value=round(avg_val, 4),
                    description="Consensus take profit (weighted average)",
                )

        sl = None
        if sl_values:
            total_w = sum(w for w, _, _ in sl_values)
            if total_w > 0:
                avg_val = sum(w * v for w, v, _ in sl_values) / total_w
                best_type = max(sl_values, key=lambda x: x[0])[2]
                sl = ExitCondition(
                    type=best_type,
                    value=round(avg_val, 4),
                    description="Consensus stop loss (weighted average)",
                )

        return ExitConditions(take_profit=tp, stop_loss=sl)

    @staticmethod
    def _merge_optimization_hints(
        strategies: dict[str, StrategyDefinition],
    ) -> OptimizationHints:
        """Merge optimization hints: union of all suggested parameters."""
        all_params: set[str] = set()
        all_ranges: dict[str, list[float]] = {}
        objectives: set[str] = set()

        for strategy in strategies.values():
            if strategy.optimization_hints:
                all_params.update(strategy.optimization_hints.parameters_to_optimize)
                for k, v in strategy.optimization_hints.ranges.items():
                    if k not in all_ranges:
                        all_ranges[k] = v
                    else:
                        # Widen range to include both
                        existing = all_ranges[k]
                        if len(existing) >= 2 and len(v) >= 2:
                            all_ranges[k] = [
                                min(existing[0], v[0]),
                                max(existing[1], v[1]),
                            ]
                if strategy.optimization_hints.primary_objective:
                    objectives.add(strategy.optimization_hints.primary_objective)

        return OptimizationHints(
            parameters_to_optimize=sorted(all_params),
            ranges=all_ranges,
            primary_objective=next(iter(objectives), "sharpe_ratio"),
        )

    # ─────────────────────────────────────────────────────────────────
    # AGREEMENT SCORING
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _calculate_agreement_score(
        strategies: dict[str, StrategyDefinition],
    ) -> float:
        """
        Calculate Jaccard similarity between agents' signal sets.

        agreement = avg(|intersection| / |union|) across all pairs.

        Returns:
            Float 0.0 (no overlap) to 1.0 (identical signals)
        """
        if len(strategies) < 2:
            return 1.0

        # Build signal type sets per agent
        signal_sets: list[set[str]] = []
        for strategy in strategies.values():
            types = {s.type for s in strategy.signals}
            signal_sets.append(types)

        # Pairwise Jaccard
        jaccard_scores: list[float] = []
        for i in range(len(signal_sets)):
            for j in range(i + 1, len(signal_sets)):
                intersection = len(signal_sets[i] & signal_sets[j])
                union = len(signal_sets[i] | signal_sets[j])
                if union > 0:
                    jaccard_scores.append(intersection / union)
                else:
                    jaccard_scores.append(0.0)

        return statistics.mean(jaccard_scores) if jaccard_scores else 0.0

    @staticmethod
    def _count_signal_votes(
        strategies: dict[str, StrategyDefinition],
    ) -> dict[str, int]:
        """Count how many agents voted for each signal type."""
        votes: dict[str, int] = defaultdict(int)
        for strategy in strategies.values():
            for signal in strategy.signals:
                votes[signal.type] += 1
        return dict(votes)
