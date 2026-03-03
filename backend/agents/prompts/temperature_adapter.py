"""
Adaptive Temperature for AI Agent Requests

Dynamically adjusts temperature based on:
- Task confidence level
- Market regime
- Task type complexity
- Historical success rate

Usage:
    adapter = TemperatureAdapter()
    temp = adapter.get_temperature(confidence=0.8, task_type="strategy", market_regime="trending")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class TemperatureConfig:
    """Configuration for temperature adaptation."""
    base_temperature: float = 0.3
    min_temperature: float = 0.1
    max_temperature: float = 1.0
    
    # Confidence thresholds
    high_confidence_threshold: float = 0.8
    low_confidence_threshold: float = 0.4
    
    # Confidence multipliers
    high_confidence_multiplier: float = 0.7  # Reduce temp for high confidence
    low_confidence_multiplier: float = 1.5   # Increase temp for low confidence
    
    # Market regime adjustments
    regime_adjustments: dict[str, float] = None
    
    # Task type adjustments
    task_adjustments: dict[str, float] = None
    
    def __post_init__(self):
        if self.regime_adjustments is None:
            self.regime_adjustments = {
                "trending_up": -0.05,      # More deterministic in trends
                "trending_down": -0.05,
                "ranging": 0.1,            # More exploration in ranges
                "consolidating": 0.1,
                "volatile": 0.15,          # More creativity in volatility
            }
        
        if self.task_adjustments is None:
            self.task_adjustments = {
                "strategy_generation": 0.0,    # Base
                "optimization": -0.1,          # More focused
                "analysis": 0.05,              # Slightly more creative
                "validation": -0.15,           # Very deterministic
                "research": 0.1,               # More exploratory
                "code_generation": -0.1,       # More precise
            }


class TemperatureAdapter:
    """
    Adapts temperature dynamically for LLM requests.
    
    Factors:
    - Confidence level (0.0-1.0)
    - Market regime (trending/ranging/volatile)
    - Task type (strategy/optimization/analysis)
    - Historical success rate
    
    Example:
        adapter = TemperatureAdapter()
        temp = adapter.get_temperature(
            confidence=0.8,
            task_type="strategy_generation",
            market_regime="trending_up"
        )
        # Returns: ~0.21 (lower for high confidence + trend)
    """
    
    def __init__(self, config: TemperatureConfig | None = None):
        """
        Initialize temperature adapter.
        
        Args:
            config: Temperature configuration (default: TemperatureConfig())
        """
        self.config = config or TemperatureConfig()
        
        # Historical success rates by task type
        self._success_rates: dict[str, list[float]] = {}
        
        logger.info(
            f"🌡️ TemperatureAdapter initialized "
            f"(base={self.config.base_temperature}, "
            f"range=[{self.config.min_temperature}, {self.config.max_temperature}])"
        )
    
    def get_temperature(
        self,
        confidence: float,
        task_type: str = "strategy_generation",
        market_regime: str = "ranging",
        use_history: bool = True,
    ) -> float:
        """
        Calculate adaptive temperature.
        
        Args:
            confidence: Confidence level (0.0-1.0)
            task_type: Task type (strategy_generation, optimization, etc.)
            market_regime: Market regime (trending_up, ranging, volatile, etc.)
            use_history: Use historical success rate (default: True)
        
        Returns:
            Temperature value (clamped to [min, max])
        """
        # Start with base temperature
        temperature = self.config.base_temperature
        
        # Factor 1: Confidence adjustment
        confidence_adj = self._adjust_for_confidence(confidence)
        temperature *= confidence_adj
        logger.debug(f"Confidence {confidence:.2f} → multiplier {confidence_adj:.2f}")
        
        # Factor 2: Market regime adjustment
        regime_adj = self.config.regime_adjustments.get(market_regime, 0.0)
        temperature += regime_adj
        logger.debug(f"Regime '{market_regime}' → adjustment {regime_adj:+.2f}")
        
        # Factor 3: Task type adjustment
        task_adj = self.config.task_adjustments.get(task_type, 0.0)
        temperature += task_adj
        logger.debug(f"Task '{task_type}' → adjustment {task_adj:+.2f}")
        
        # Factor 4: Historical success rate
        if use_history:
            history_adj = self._adjust_for_history(task_type)
            temperature *= history_adj
            logger.debug(f"History → multiplier {history_adj:.2f}")
        
        # Clamp to valid range
        temperature = max(
            self.config.min_temperature,
            min(temperature, self.config.max_temperature)
        )
        
        logger.debug(f"Final temperature: {temperature:.3f}")
        
        return temperature
    
    def _adjust_for_confidence(self, confidence: float) -> float:
        """Adjust temperature based on confidence."""
        if confidence >= self.config.high_confidence_threshold:
            # High confidence → lower temperature (more deterministic)
            return self.config.high_confidence_multiplier
        elif confidence <= self.config.low_confidence_threshold:
            # Low confidence → higher temperature (more exploration)
            return self.config.low_confidence_multiplier
        else:
            # Medium confidence → linear interpolation
            range_size = (
                self.config.high_confidence_threshold -
                self.config.low_confidence_threshold
            )
            position = (confidence - self.config.low_confidence_threshold) / range_size
            
            # Interpolate between multipliers
            multiplier_range = (
                self.config.low_confidence_multiplier -
                self.config.high_confidence_multiplier
            )
            return self.config.high_confidence_multiplier + (position * multiplier_range)
    
    def _adjust_for_history(self, task_type: str) -> float:
        """Adjust temperature based on historical success rate."""
        if task_type not in self._success_rates:
            return 1.0  # No history, no adjustment
        
        rates = self._success_rates[task_type]
        if not rates:
            return 1.0
        
        avg_success = sum(rates) / len(rates)
        
        # High success rate → lower temperature (keep doing what works)
        # Low success rate → higher temperature (try different approaches)
        if avg_success > 0.8:
            return 0.9  # Slightly more deterministic
        elif avg_success < 0.4:
            return 1.2  # Slightly more exploratory
        else:
            return 1.0  # No adjustment
    
    def record_success(
        self,
        task_type: str,
        success: bool,
        weight: float = 1.0,
    ) -> None:
        """
        Record success/failure for a task type.
        
        Args:
            task_type: Task type
            success: Whether task succeeded
            weight: Weight for this result (default: 1.0)
        """
        if task_type not in self._success_rates:
            self._success_rates[task_type] = []
        
        # Add weighted result
        for _ in range(int(weight * 10)):
            self._success_rates[task_type].append(1.0 if success else 0.0)
        
        # Keep only last 100 results
        self._success_rates[task_type] = self._success_rates[task_type][-100:]
    
    def get_temperature_for_agent(
        self,
        agent_type: str,
        confidence: float,
        market_regime: str,
    ) -> float:
        """
        Get temperature optimized for specific agent type.
        
        Args:
            agent_type: Agent type (qwen, deepseek, perplexity)
            confidence: Confidence level
            market_regime: Market regime
        
        Returns:
            Temperature value
        """
        # Agent-specific base temperatures
        agent_bases = {
            "qwen": 0.3,        # Balanced
            "deepseek": 0.25,   # More deterministic (quantitative)
            "perplexity": 0.35, # More exploratory (research)
        }
        
        base = agent_bases.get(agent_type, self.config.base_temperature)
        
        # Calculate with custom base
        temp = base
        temp *= self._adjust_for_confidence(confidence)
        temp += self.config.regime_adjustments.get(market_regime, 0.0)
        
        # Clamp
        return max(
            self.config.min_temperature,
            min(temp, self.config.max_temperature)
        )
    
    def get_stats(self) -> dict[str, Any]:
        """Get adapter statistics."""
        stats = {
            "base_temperature": self.config.base_temperature,
            "min_temperature": self.config.min_temperature,
            "max_temperature": self.config.max_temperature,
            "success_rates": {},
        }
        
        for task_type, rates in self._success_rates.items():
            if rates:
                stats["success_rates"][task_type] = sum(rates) / len(rates)
        
        return stats
    
    def reset_history(self) -> None:
        """Reset historical success rates."""
        self._success_rates.clear()
        logger.info("🌡️ TemperatureAdapter history reset")
