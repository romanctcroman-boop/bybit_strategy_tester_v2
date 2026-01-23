"""
AI-Driven Feature Engineering for Trading Strategies

This module uses AI agents (DeepSeek/Perplexity) to:
1. Generate technical indicator ideas
2. Validate feature usefulness
3. Create feature engineering code
4. Evaluate feature importance

Flow:
User: "I want to predict BTC price for next 4 hours"
→ AI: Suggests RSI, MACD, Volume, Bollinger Bands, etc.
→ AI: Generates Python code to calculate these features
→ System: Runs backtests to evaluate effectiveness
→ AI: Recommends best features based on results
"""

import json
from typing import Any, Dict, List

from backend.agents.unified_agent_interface import UnifiedAgentInterface
from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class AIFeatureEngineer:
    """
    AI-powered feature engineering for trading strategies

    Uses AI agents to suggest, generate, and validate trading features.
    """

    def __init__(self):
        self.agent = UnifiedAgentInterface()
        self.feature_history: List[Dict[str, Any]] = []

    async def suggest_features(
        self,
        objective: str,
        asset: str = "BTC/USDT",
        timeframe: str = "1h",
        max_features: int = 10,
    ) -> Dict[str, Any]:
        """
        Ask AI to suggest technical indicators for trading strategy

        Args:
            objective: What you want to predict (e.g., "price direction", "volatility")
            asset: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h", "15m")
            max_features: Maximum number of features to suggest

        Returns:
            Dict with suggested features, explanations, and code snippets
        """
        logger.info(
            f"🧠 Asking AI to suggest features for {objective} on {asset} ({timeframe})"
        )

        prompt = f"""You are a quantitative trading expert. I need technical indicators for a trading strategy.

**Objective**: {objective}
**Asset**: {asset}
**Timeframe**: {timeframe}
**Max Features**: {max_features}

Please suggest {max_features} most effective technical indicators for this task. For each indicator:
1. Name and brief description
2. Why it's relevant for this objective
3. Typical parameter values (e.g., RSI period=14)
4. Expected predictive power (high/medium/low)

Format your response as JSON:
{{
  "features": [
    {{
      "name": "RSI",
      "description": "Relative Strength Index - momentum oscillator",
      "parameters": {{"period": 14}},
      "relevance": "Detects overbought/oversold conditions",
      "predictive_power": "high",
      "category": "momentum"
    }}
  ],
  "rationale": "Overall explanation of why these features work together"
}}

Respond ONLY with valid JSON, no additional text."""

        try:
            # Query AI agent
            result = await self.agent.query_deepseek(
                prompt=prompt,
                temperature=0.3,  # Lower for more deterministic output
                max_tokens=2000,
            )

            response_text = result.get("response", "")

            # Try to parse JSON
            try:
                # Extract JSON from response (in case AI adds text around it)
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    suggestions = json.loads(json_str)
                else:
                    logger.warning("No JSON found in AI response, using fallback")
                    suggestions = self._fallback_suggestions(objective)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.debug(f"Response was: {response_text[:500]}")
                suggestions = self._fallback_suggestions(objective)

            # Add metadata
            suggestions["metadata"] = {
                "objective": objective,
                "asset": asset,
                "timeframe": timeframe,
                "ai_model": result.get("model", "deepseek-chat"),
                "from_cache": result.get("from_cache", False),
                "latency_ms": result.get("latency_ms", 0),
            }

            # Store in history
            self.feature_history.append(suggestions)

            logger.info(
                f"✅ AI suggested {len(suggestions.get('features', []))} features"
            )
            return suggestions

        except Exception as e:
            logger.error(f"❌ Error getting feature suggestions: {e}")
            return self._fallback_suggestions(objective)

    def _fallback_suggestions(self, objective: str) -> Dict[str, Any]:
        """Fallback suggestions if AI fails"""
        return {
            "features": [
                {
                    "name": "RSI",
                    "description": "Relative Strength Index",
                    "parameters": {"period": 14},
                    "relevance": "Momentum indicator",
                    "predictive_power": "high",
                    "category": "momentum",
                },
                {
                    "name": "MACD",
                    "description": "Moving Average Convergence Divergence",
                    "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    "relevance": "Trend following",
                    "predictive_power": "high",
                    "category": "trend",
                },
                {
                    "name": "BB",
                    "description": "Bollinger Bands",
                    "parameters": {"period": 20, "std": 2},
                    "relevance": "Volatility indicator",
                    "predictive_power": "medium",
                    "category": "volatility",
                },
            ],
            "rationale": "Common technical indicators for price prediction",
            "metadata": {
                "objective": objective,
                "source": "fallback",
            },
        }

    async def generate_feature_code(
        self,
        feature_name: str,
        parameters: Dict[str, Any],
        data_format: str = "pandas DataFrame with OHLCV columns",
    ) -> Dict[str, Any]:
        """
        Ask AI to generate Python code for calculating a feature

        Args:
            feature_name: Name of indicator (e.g., "RSI", "MACD")
            parameters: Indicator parameters (e.g., {"period": 14})
            data_format: Description of input data format

        Returns:
            Dict with code, imports, and usage instructions
        """
        logger.info(f"💻 Generating code for {feature_name} with params {parameters}")

        prompt = f"""Generate Python code to calculate the {feature_name} technical indicator.

**Input Data Format**: {data_format}
**Parameters**: {json.dumps(parameters, indent=2)}

Requirements:
1. Use pandas and numpy (standard libraries)
2. Input: df (pandas DataFrame with columns: open, high, low, close, volume)
3. Output: Add new column(s) to the DataFrame
4. Handle edge cases (NaN, insufficient data)
5. Optimize for performance
6. Include docstring

Return ONLY Python code, ready to execute. Start with imports."""

        try:
            result = await self.agent.query_deepseek(
                prompt=prompt,
                temperature=0.1,  # Very low for consistent code
                max_tokens=1500,
            )

            code = result.get("response", "")

            # Extract code block if wrapped in markdown
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

            return {
                "feature_name": feature_name,
                "parameters": parameters,
                "code": code,
                "language": "python",
                "ai_model": result.get("model"),
                "from_cache": result.get("from_cache", False),
            }

        except Exception as e:
            logger.error(f"❌ Error generating code: {e}")
            return {
                "feature_name": feature_name,
                "parameters": parameters,
                "code": "# Error generating code",
                "error": str(e),
            }

    async def validate_features(
        self,
        features: List[str],
        performance_metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Ask AI to analyze which features are most valuable

        Args:
            features: List of feature names tested
            performance_metrics: Dict of feature -> performance score

        Returns:
            AI's analysis and recommendations
        """
        logger.info(f"🔍 Asking AI to validate {len(features)} features")

        # Sort features by performance
        sorted_features = sorted(
            performance_metrics.items(), key=lambda x: x[1], reverse=True
        )

        prompt = f"""Analyze the performance of these technical indicators in a trading strategy:

**Performance Results**:
{json.dumps(dict(sorted_features[:10]), indent=2)}

**Questions**:
1. Which features are most valuable? Why?
2. Are there any redundant features (high correlation)?
3. What additional features should we try?
4. Any concerns about overfitting?

Provide analysis in JSON format:
{{
  "best_features": ["feature1", "feature2"],
  "redundant_features": ["feature3"],
  "suggested_additions": ["feature4", "feature5"],
  "overfitting_risk": "low/medium/high",
  "analysis": "Detailed explanation..."
}}"""

        try:
            result = await self.agent.query_deepseek(
                prompt=prompt,
                temperature=0.5,
                max_tokens=1500,
            )

            response_text = result.get("response", "")

            # Try to parse JSON
            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    analysis = {"analysis": response_text}
            except json.JSONDecodeError:
                analysis = {"analysis": response_text}

            return analysis

        except Exception as e:
            logger.error(f"❌ Error validating features: {e}")
            return {"error": str(e)}

    async def suggest_complete_strategy(
        self,
        objective: str,
        asset: str = "BTC/USDT",
        timeframe: str = "1h",
        risk_tolerance: str = "medium",
    ) -> Dict[str, Any]:
        """
        Ask AI to design a complete trading strategy

        Returns strategy with entry/exit rules, features, risk management
        """
        logger.info(f"🎯 Asking AI to design complete strategy for {asset}")

        prompt = f"""Design a complete algorithmic trading strategy:

**Objective**: {objective}
**Asset**: {asset}
**Timeframe**: {timeframe}
**Risk Tolerance**: {risk_tolerance}

Provide a comprehensive strategy including:
1. **Features**: Technical indicators to use
2. **Entry Rules**: When to enter position (buy/long)
3. **Exit Rules**: When to exit (take profit, stop loss)
4. **Position Sizing**: How much capital to risk per trade
5. **Risk Management**: Maximum drawdown, position limits

Return as JSON:
{{
  "strategy_name": "...",
  "features": ["RSI", "MACD", "Volume"],
  "entry_conditions": {{
    "long": ["RSI < 30", "MACD cross up"],
    "short": ["RSI > 70", "MACD cross down"]
  }},
  "exit_conditions": {{
    "take_profit": "2% profit",
    "stop_loss": "1% loss"
  }},
  "position_sizing": {{
    "method": "fixed_fraction",
    "risk_per_trade": 0.02
  }},
  "expected_metrics": {{
    "win_rate": "55-60%",
    "profit_factor": "1.5+",
    "max_drawdown": "< 15%"
  }}
}}"""

        try:
            result = await self.agent.query_deepseek(
                prompt=prompt,
                temperature=0.4,
                max_tokens=2500,
            )

            response_text = result.get("response", "")

            # Parse JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                strategy = json.loads(json_str)
            else:
                strategy = {"error": "No JSON in response"}

            strategy["metadata"] = {
                "ai_model": result.get("model"),
                "from_cache": result.get("from_cache"),
                "generated_at": result.get("latency_ms"),
            }

            logger.info(
                f"✅ Strategy '{strategy.get('strategy_name', 'Unknown')}' generated"
            )
            return strategy

        except Exception as e:
            logger.error(f"❌ Error generating strategy: {e}")
            return {"error": str(e)}


# Convenience function
async def ask_ai_for_features(
    objective: str,
    asset: str = "BTC/USDT",
    timeframe: str = "1h",
) -> Dict[str, Any]:
    """Quick helper to get AI feature suggestions"""
    engineer = AIFeatureEngineer()
    return await engineer.suggest_features(objective, asset, timeframe)
