"""
RL Agent Integration with AI Guidance

Integrates reinforcement learning trading agents with AI advisor agents:
- AI-guided reward shaping
- Market regime detection
- Decision validation
- Training recommendations

Enables smarter RL training through AI-provided insights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from loguru import logger


class MarketRegime(Enum):
    """Market regime classifications"""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"


@dataclass
class AIGuidedTrainingConfig:
    """Configuration for AI-guided RL training"""

    regime_based_rewards: bool = True
    ai_validation_frequency: int = 100  # Validate every N steps
    min_confidence_for_action: float = 0.6
    reward_scale_factor: float = 1.0
    use_ai_for_exploration: bool = True
    max_ai_queries_per_episode: int = 10


@dataclass
class RewardShapingConfig:
    """Reward shaping configuration from AI"""

    base_reward_scale: float = 1.0
    profit_weight: float = 1.0
    drawdown_penalty: float = 1.5
    holding_penalty: float = 0.01
    overtrading_penalty: float = 0.5
    regime_bonuses: dict[str, float] = field(default_factory=dict)


@dataclass
class TrainingRecommendation:
    """Recommendation from AI for RL training"""

    parameter: str
    current_value: Any
    recommended_value: Any
    reasoning: str
    confidence: float
    priority: str  # low, medium, high


class RLAgentIntegration:
    """
    Integration between AI agents and RL trading system

    Uses AI agents to:
    1. Detect market regime
    2. Suggest reward shaping
    3. Validate RL decisions
    4. Recommend training parameters

    Example:
        integration = RLAgentIntegration(ai_interface, rl_agent)

        # AI-guided training episode
        await integration.ai_guided_episode(market_data)

        # Validate RL decision
        validation = await integration.validate_decision(state, action)
    """

    REGIME_DETECTION_PROMPT = """
Analyze the market data and classify the current regime.

Recent price data (last {window} candles):
High: {highs}
Low: {lows}
Close: {closes}
Volume: {volumes}

Calculate and report:
1. Trend direction and strength
2. Volatility level
3. Primary regime classification

Response format:
REGIME: [trending_up/trending_down/ranging/high_volatility/low_volatility/breakout]
TREND_STRENGTH: [0.0-1.0]
VOLATILITY: [low/medium/high]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief explanation]
"""

    REWARD_SHAPING_PROMPT = """
Based on the current market regime, suggest reward shaping for RL training.

Market Regime: {regime}
Volatility: {volatility}
Current RL Performance:
- Win Rate: {win_rate}%
- Max Drawdown: {max_drawdown}%
- Sharpe Ratio: {sharpe}

Suggest reward adjustments:
PROFIT_WEIGHT: [0.5-2.0]
DRAWDOWN_PENALTY: [0.5-3.0]
HOLDING_PENALTY: [0.001-0.1]
OVERTRADING_PENALTY: [0.1-1.0]
REGIME_BONUS: [0.0-0.5]
CONFIDENCE: [0.0-1.0]
REASONING: [Why these adjustments]
"""

    VALIDATION_PROMPT = """
Validate this RL trading decision.

Current Market State:
- Price: {price}
- RSI: {rsi}
- MACD: {macd}
- Position: {position}
- Unrealized PnL: {pnl}%

RL Agent Decision: {action}
Confidence Score: {confidence}

Evaluate:
1. Is this decision appropriate for current conditions?
2. What risks should be considered?
3. Would you recommend this action?

Response:
APPROVED: [yes/no]
RISK_LEVEL: [low/medium/high]
CONCERNS: [List any concerns]
ALTERNATIVE: [If not approved, suggest alternative]
CONFIDENCE: [0.0-1.0]
"""

    def __init__(
        self,
        ai_interface: Any | None = None,
        rl_agent: Any | None = None,
        config: AIGuidedTrainingConfig | None = None,
    ):
        """
        Initialize RL-AI integration

        Args:
            ai_interface: UnifiedAgentInterface instance
            rl_agent: RLTradingAgent instance
            config: Training configuration
        """
        self.ai_interface = ai_interface
        self.rl_agent = rl_agent
        self.config = config or AIGuidedTrainingConfig()

        self.current_regime: MarketRegime | None = None
        self.reward_config: RewardShapingConfig = RewardShapingConfig()

        # Statistics
        self.stats = {
            "ai_queries": 0,
            "decisions_validated": 0,
            "decisions_approved": 0,
            "regime_changes": 0,
        }

        self.training_history: list[dict[str, Any]] = []

        logger.info("🤝 RL-AI Integration initialized")

    async def detect_market_regime(
        self,
        market_data: np.ndarray,
        window: int = 20,
    ) -> tuple[MarketRegime, float]:
        """
        Use AI to detect current market regime

        Args:
            market_data: OHLCV data array
            window: Lookback window

        Returns:
            Tuple of (regime, confidence)
        """
        # Extract recent data
        recent = market_data[-window:] if len(market_data) > window else market_data

        # Prepare data for prompt
        highs = [f"{x:.2f}" for x in recent[:, 1][-5:]]  # Last 5 highs
        lows = [f"{x:.2f}" for x in recent[:, 2][-5:]]
        closes = [f"{x:.2f}" for x in recent[:, 3][-5:]]
        volumes = [f"{x:.0f}" for x in recent[:, 4][-5:]]

        prompt = self.REGIME_DETECTION_PROMPT.format(
            window=window,
            highs=", ".join(highs),
            lows=", ".join(lows),
            closes=", ".join(closes),
            volumes=", ".join(volumes),
        )

        response = await self._ask_ai(prompt)
        self.stats["ai_queries"] += 1

        # Parse response
        regime_str = self._extract_value(response, "REGIME").lower()
        confidence = float(self._extract_value(response, "CONFIDENCE") or "0.6")

        regime_map = {
            "trending_up": MarketRegime.TRENDING_UP,
            "trending_down": MarketRegime.TRENDING_DOWN,
            "ranging": MarketRegime.RANGING,
            "high_volatility": MarketRegime.HIGH_VOLATILITY,
            "low_volatility": MarketRegime.LOW_VOLATILITY,
            "breakout": MarketRegime.BREAKOUT,
        }

        regime = regime_map.get(regime_str, MarketRegime.RANGING)

        # Track regime changes
        if self.current_regime != regime:
            self.stats["regime_changes"] += 1
            logger.info(f"📊 Market regime changed: {self.current_regime} → {regime}")

        self.current_regime = regime

        return regime, confidence

    async def suggest_reward_shaping(
        self,
        regime: MarketRegime,
        rl_performance: dict[str, float],
    ) -> RewardShapingConfig:
        """
        Get AI recommendations for reward shaping

        Args:
            regime: Current market regime
            rl_performance: Current RL agent performance metrics

        Returns:
            RewardShapingConfig with recommended values
        """
        prompt = self.REWARD_SHAPING_PROMPT.format(
            regime=regime.value,
            volatility=self._estimate_volatility_level(regime),
            win_rate=rl_performance.get("win_rate", 50),
            max_drawdown=rl_performance.get("max_drawdown", 10),
            sharpe=rl_performance.get("sharpe", 0.5),
        )

        response = await self._ask_ai(prompt)
        self.stats["ai_queries"] += 1

        # Parse response
        config = RewardShapingConfig(
            profit_weight=float(
                self._extract_value(response, "PROFIT_WEIGHT") or "1.0"
            ),
            drawdown_penalty=float(
                self._extract_value(response, "DRAWDOWN_PENALTY") or "1.5"
            ),
            holding_penalty=float(
                self._extract_value(response, "HOLDING_PENALTY") or "0.01"
            ),
            overtrading_penalty=float(
                self._extract_value(response, "OVERTRADING_PENALTY") or "0.5"
            ),
        )

        # Add regime-specific bonus
        regime_bonus = float(self._extract_value(response, "REGIME_BONUS") or "0.0")
        config.regime_bonuses[regime.value] = regime_bonus

        self.reward_config = config

        logger.debug(f"🎯 Reward shaping updated for {regime.value}")
        return config

    async def validate_decision(
        self,
        state: dict[str, Any],
        action: int,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """
        Use AI to validate RL agent's decision

        Args:
            state: Current market state
            action: RL agent's chosen action (0=hold, 1=buy, 2=sell, 3=close)
            confidence: RL agent's confidence in the decision

        Returns:
            Validation result dict
        """
        action_names = {0: "HOLD", 1: "BUY", 2: "SELL", 3: "CLOSE"}

        prompt = self.VALIDATION_PROMPT.format(
            price=state.get("price", 0),
            rsi=state.get("rsi", 50),
            macd=state.get("macd", 0),
            position=state.get("position_size", 0),
            pnl=state.get("unrealized_pnl", 0),
            action=action_names.get(action, "UNKNOWN"),
            confidence=confidence,
        )

        response = await self._ask_ai(prompt)
        self.stats["ai_queries"] += 1
        self.stats["decisions_validated"] += 1

        # Parse response
        approved = "yes" in self._extract_value(response, "APPROVED").lower()
        risk_level = self._extract_value(response, "RISK_LEVEL").lower()
        ai_confidence = float(self._extract_value(response, "CONFIDENCE") or "0.5")

        if approved:
            self.stats["decisions_approved"] += 1

        result = {
            "approved": approved,
            "risk_level": risk_level,
            "concerns": self._extract_list(response, "CONCERNS"),
            "alternative": self._extract_value(response, "ALTERNATIVE"),
            "ai_confidence": ai_confidence,
            "original_action": action,
        }

        return result

    async def ai_guided_episode(
        self,
        market_data: np.ndarray,
        episode_length: int = 1000,
    ) -> dict[str, Any]:
        """
        Run RL training episode with AI guidance

        Args:
            market_data: Historical market data
            episode_length: Maximum episode length

        Returns:
            Episode results with AI interventions
        """
        if self.rl_agent is None:
            logger.warning("No RL agent configured")
            return {"error": "No RL agent"}

        # Detect initial regime
        regime, regime_confidence = await self.detect_market_regime(market_data[:100])

        # Get reward shaping recommendations
        rl_perf = {"win_rate": 50, "max_drawdown": 15, "sharpe": 0.3}  # Default/initial
        reward_config = await self.suggest_reward_shaping(regime, rl_perf)

        episode_log = {
            "regime": regime.value,
            "regime_confidence": regime_confidence,
            "reward_config": {
                "profit_weight": reward_config.profit_weight,
                "drawdown_penalty": reward_config.drawdown_penalty,
            },
            "ai_interventions": 0,
            "steps": 0,
            "total_reward": 0.0,
        }

        ai_queries_this_episode = 0

        # Training loop (simplified - actual implementation would call rl_agent methods)
        for step in range(min(episode_length, len(market_data) - 1)):
            # Periodic AI validation
            if (
                self.config.ai_validation_frequency > 0
                and step % self.config.ai_validation_frequency == 0
                and ai_queries_this_episode < self.config.max_ai_queries_per_episode
            ):
                # Get current state and action from RL agent
                current_state = self._extract_state(market_data, step)

                # Simulate RL decision (in real implementation, get from agent)
                action = np.random.choice([0, 1, 2, 3])
                confidence = np.random.uniform(0.4, 0.9)

                # Validate with AI
                validation = await self.validate_decision(
                    current_state, action, confidence
                )

                ai_queries_this_episode += 1

                if not validation["approved"]:
                    episode_log["ai_interventions"] += 1

            episode_log["steps"] += 1
            # In real implementation: execute step, get reward, update agent

        self.training_history.append(episode_log)

        logger.info(
            f"📈 AI-guided episode complete: {episode_log['steps']} steps, "
            f"{episode_log['ai_interventions']} interventions"
        )

        return episode_log

    async def get_training_recommendations(
        self,
        recent_performance: dict[str, float],
    ) -> list[TrainingRecommendation]:
        """
        Get AI recommendations for RL training parameters

        Args:
            recent_performance: Recent RL agent performance metrics

        Returns:
            List of parameter recommendations
        """
        recommendations = []

        # Analysis based on performance
        win_rate = recent_performance.get("win_rate", 50)
        sharpe = recent_performance.get("sharpe", 0)
        max_dd = recent_performance.get("max_drawdown", 20)

        # Win rate recommendations
        if win_rate < 40:
            recommendations.append(
                TrainingRecommendation(
                    parameter="exploration_rate",
                    current_value="unknown",
                    recommended_value=0.3,
                    reasoning="Low win rate suggests more exploration needed",
                    confidence=0.7,
                    priority="high",
                )
            )

        # Drawdown recommendations
        if max_dd > 30:
            recommendations.append(
                TrainingRecommendation(
                    parameter="drawdown_penalty",
                    current_value=self.reward_config.drawdown_penalty,
                    recommended_value=self.reward_config.drawdown_penalty * 1.5,
                    reasoning="High drawdown requires stronger penalty in reward function",
                    confidence=0.8,
                    priority="high",
                )
            )

        # Sharpe recommendations
        if sharpe < 0.5:
            recommendations.append(
                TrainingRecommendation(
                    parameter="reward_scaling",
                    current_value=1.0,
                    recommended_value=1.5,
                    reasoning="Low Sharpe ratio suggests reward signal is too weak",
                    confidence=0.6,
                    priority="medium",
                )
            )

        return recommendations

    def calculate_shaped_reward(
        self,
        base_reward: float,
        state: dict[str, Any],
    ) -> float:
        """
        Calculate shaped reward using AI recommendations

        Args:
            base_reward: Original reward from environment
            state: Current state

        Returns:
            Shaped reward value
        """
        shaped = base_reward * self.reward_config.profit_weight

        # Apply drawdown penalty
        if state.get("current_drawdown", 0) > 0.1:
            shaped -= self.reward_config.drawdown_penalty * state["current_drawdown"]

        # Apply holding penalty (encourages action)
        if state.get("position_held_steps", 0) > 50:
            shaped -= self.reward_config.holding_penalty

        # Apply regime bonus
        if self.current_regime:
            bonus = self.reward_config.regime_bonuses.get(self.current_regime.value, 0)
            if bonus > 0 and base_reward > 0:
                shaped += bonus

        return shaped * self.reward_config.base_reward_scale

    def _extract_state(self, market_data: np.ndarray, step: int) -> dict[str, Any]:
        """Extract state dict from market data"""
        if step >= len(market_data):
            step = len(market_data) - 1

        return {
            "price": float(market_data[step, 3]),  # Close
            "rsi": 50.0,  # Would calculate actual RSI
            "macd": 0.0,  # Would calculate actual MACD
            "position_size": 0.0,
            "unrealized_pnl": 0.0,
        }

    def _estimate_volatility_level(self, regime: MarketRegime) -> str:
        """Estimate volatility from regime"""
        if regime == MarketRegime.HIGH_VOLATILITY:
            return "high"
        elif regime == MarketRegime.LOW_VOLATILITY:
            return "low"
        elif regime in [
            MarketRegime.BREAKOUT,
            MarketRegime.TRENDING_UP,
            MarketRegime.TRENDING_DOWN,
        ]:
            return "medium"
        else:
            return "medium"

    def _extract_value(self, text: str, field: str) -> str:
        """Extract field value from text"""
        for line in text.split("\n"):
            if field.upper() + ":" in line.upper():
                return line.split(":", 1)[-1].strip()
        return ""

    def _extract_list(self, text: str, field: str) -> list[str]:
        """Extract list items after field"""
        items = []
        in_section = False

        for line in text.split("\n"):
            if field.upper() + ":" in line.upper():
                in_section = True
                # Check if items on same line
                after_colon = line.split(":", 1)[-1].strip()
                if after_colon and after_colon != "":
                    items.append(after_colon)
                continue
            if in_section:
                if line.strip().startswith("-"):
                    items.append(line.strip()[1:].strip())
                elif line.strip() and ":" in line:
                    break  # New section

        return items

    async def _ask_ai(self, prompt: str) -> str:
        """Ask AI for response"""
        if self.ai_interface:
            try:
                from backend.agents.models import AgentType
                from backend.agents.unified_agent_interface import AgentRequest

                request = AgentRequest(
                    task_type="rl_guidance",
                    agent_type=AgentType.DEEPSEEK,
                    prompt=prompt,
                )
                response = await self.ai_interface.send_request(request)
                return response.content if response.success else ""
            except Exception as e:
                logger.warning(f"AI request failed: {e}")
                return ""

        # Simulate response for testing
        return self._simulate_response(prompt)

    def _simulate_response(self, prompt: str) -> str:
        """Simulate AI response for testing"""
        if "REGIME" in prompt:
            return """
REGIME: trending_up
TREND_STRENGTH: 0.7
VOLATILITY: medium
CONFIDENCE: 0.75
REASONING: Recent closes show upward movement with moderate volume
"""
        elif "PROFIT_WEIGHT" in prompt:
            return """
PROFIT_WEIGHT: 1.2
DRAWDOWN_PENALTY: 1.8
HOLDING_PENALTY: 0.02
OVERTRADING_PENALTY: 0.4
REGIME_BONUS: 0.15
CONFIDENCE: 0.7
REASONING: Trending market favors momentum, increase profit focus
"""
        elif "APPROVED" in prompt:
            return """
APPROVED: yes
RISK_LEVEL: medium
CONCERNS: Watch for reversal signals
ALTERNATIVE: N/A
CONFIDENCE: 0.75
"""
        return "CONFIDENCE: 0.5"

    def get_stats(self) -> dict[str, Any]:
        """Get integration statistics"""
        return {
            **self.stats,
            "current_regime": self.current_regime.value
            if self.current_regime
            else None,
            "approval_rate": (
                self.stats["decisions_approved"]
                / max(self.stats["decisions_validated"], 1)
            ),
            "training_episodes": len(self.training_history),
        }


__all__ = [
    "AIGuidedTrainingConfig",
    "MarketRegime",
    "RLAgentIntegration",
    "RewardShapingConfig",
    "TrainingRecommendation",
]
