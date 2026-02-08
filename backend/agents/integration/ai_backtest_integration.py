"""
AI-Powered Backtest and Optimization Integration

Connects AI Agent System with Backtesting and Optimization engines:
1. AI analyzes backtest results and provides recommendations
2. AI helps interpret optimization outcomes
3. AI detects overfitting risks
4. AI suggests parameter adjustments based on market regime

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    AI-BACKTEST INTEGRATION                     │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   User Request                                                  │
    │        │                                                        │
    │        ▼                                                        │
    │   ┌──────────────────┐                                         │
    │   │  AIBacktester    │                                         │
    │   │                  │                                         │
    │   │  1. Run Backtest ├─────► IntrabarEngine                    │
    │   │  2. Get Results  │                                         │
    │   │  3. AI Analysis  ├─────► RealLLMDeliberation               │
    │   │  4. Combine      │                                         │
    │   └──────────────────┘                                         │
    │           │                                                     │
    │           ▼                                                     │
    │   Enhanced Results with AI Insights                             │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger


@dataclass
class AIBacktestResult:
    """Enhanced backtest result with AI analysis"""

    # Original backtest metrics
    net_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int

    # AI Analysis
    ai_summary: str
    ai_risk_assessment: str
    ai_recommendations: list[str]
    ai_confidence: float
    overfitting_risk: str  # "low", "medium", "high"
    market_regime_fit: str  # Which market conditions suit this strategy

    # Metadata
    strategy_name: str
    symbol: str
    timeframe: str
    backtest_period: str
    analysis_timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": {
                "net_pnl": self.net_pnl,
                "total_return_pct": self.total_return_pct,
                "sharpe_ratio": self.sharpe_ratio,
                "max_drawdown_pct": self.max_drawdown_pct,
                "win_rate": self.win_rate,
                "profit_factor": self.profit_factor,
                "total_trades": self.total_trades,
            },
            "ai_analysis": {
                "summary": self.ai_summary,
                "risk_assessment": self.ai_risk_assessment,
                "recommendations": self.ai_recommendations,
                "confidence": self.ai_confidence,
                "overfitting_risk": self.overfitting_risk,
                "market_regime_fit": self.market_regime_fit,
            },
            "metadata": {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "backtest_period": self.backtest_period,
                "analysis_timestamp": self.analysis_timestamp.isoformat(),
            },
        }


@dataclass
class AIOptimizationResult:
    """Optimization result with AI interpretation"""

    # Best parameters found
    best_params: dict[str, Any]
    best_sharpe: float
    best_return: float

    # All trials summary
    total_trials: int
    convergence_score: float

    # AI interpretation
    ai_parameter_analysis: str
    ai_robustness_assessment: str
    ai_confidence: float
    overfitting_warning: str | None
    suggested_adjustments: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimization": {
                "best_params": self.best_params,
                "best_sharpe": self.best_sharpe,
                "best_return": self.best_return,
                "total_trials": self.total_trials,
                "convergence_score": self.convergence_score,
            },
            "ai_analysis": {
                "parameter_analysis": self.ai_parameter_analysis,
                "robustness_assessment": self.ai_robustness_assessment,
                "confidence": self.ai_confidence,
                "overfitting_warning": self.overfitting_warning,
                "suggested_adjustments": self.suggested_adjustments,
            },
        }


class AIBacktestAnalyzer:
    """
    AI-powered backtest result analyzer.

    Uses RealLLMDeliberation to provide intelligent insights on backtest results.

    Example:
        analyzer = AIBacktestAnalyzer()

        result = await analyzer.analyze_backtest(
            metrics={
                "net_pnl": 15000,
                "sharpe_ratio": 1.8,
                "max_drawdown_pct": 12.5,
                "win_rate": 0.58,
                "total_trades": 145,
            },
            strategy_name="Momentum RSI",
            symbol="BTCUSDT",
            timeframe="1h",
        )

        print(result.ai_summary)
        print(result.ai_recommendations)
    """

    ANALYSIS_PROMPT = """
You are an expert quantitative analyst reviewing trading strategy backtest results.

BACKTEST RESULTS:
- Strategy: {strategy_name}
- Symbol: {symbol}
- Timeframe: {timeframe}
- Period: {period}

METRICS:
- Net PnL: ${net_pnl:,.2f}
- Total Return: {total_return_pct:.2f}%
- Sharpe Ratio: {sharpe_ratio:.2f}
- Max Drawdown: {max_drawdown_pct:.2f}%
- Win Rate: {win_rate:.1%}
- Profit Factor: {profit_factor:.2f}
- Total Trades: {total_trades}

Analyze these results and provide:
1. SUMMARY: Brief overall assessment (2-3 sentences)
2. RISK_ASSESSMENT: Evaluation of risk metrics (focus on drawdown, Sharpe)
3. RECOMMENDATIONS: 3 specific actionable improvements
4. OVERFITTING_RISK: low/medium/high with reason
5. MARKET_REGIME: What market conditions suit this strategy best

Format your response as:
SUMMARY: [your summary]
RISK_ASSESSMENT: [your risk analysis]
RECOMMENDATIONS: [rec1], [rec2], [rec3]
OVERFITTING_RISK: [low/medium/high] - [reason]
MARKET_REGIME: [trending/ranging/volatile/all conditions]
"""

    def __init__(self):
        self._deliberation = None
        logger.info("📊 AIBacktestAnalyzer initialized")

    def _get_deliberation(self):
        """Lazy load deliberation"""
        if self._deliberation is None:
            try:
                from backend.agents.consensus.real_llm_deliberation import (
                    get_real_deliberation,
                )

                self._deliberation = get_real_deliberation()
            except Exception as e:
                logger.warning(f"Could not load RealLLMDeliberation: {e}")
                from backend.agents.consensus.deliberation import MultiAgentDeliberation

                self._deliberation = MultiAgentDeliberation()
        return self._deliberation

    async def analyze_backtest(
        self,
        metrics: dict[str, Any],
        strategy_name: str,
        symbol: str,
        timeframe: str,
        period: str = "Unknown",
        agents: list[str] = None,
    ) -> AIBacktestResult:
        """
        Analyze backtest results with AI.

        Args:
            metrics: Backtest metrics dict
            strategy_name: Name of the strategy
            symbol: Trading symbol
            timeframe: Chart timeframe
            period: Backtest period description
            agents: Which AI agents to use

        Returns:
            AIBacktestResult with AI insights
        """
        agents = agents or ["deepseek"]

        # Build prompt
        prompt = self.ANALYSIS_PROMPT.format(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            period=period,
            net_pnl=metrics.get("net_pnl", 0),
            total_return_pct=metrics.get("total_return_pct", 0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", 0),
            win_rate=metrics.get("win_rate", 0),
            profit_factor=metrics.get("profit_factor", 1),
            total_trades=metrics.get("total_trades", 0),
        )

        # Call LLM directly for raw response
        raw_response = await self._call_llm(agents[0], prompt)

        # Parse response
        analysis = self._parse_analysis(raw_response)

        return AIBacktestResult(
            net_pnl=metrics.get("net_pnl", 0),
            total_return_pct=metrics.get("total_return_pct", 0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", 0),
            win_rate=metrics.get("win_rate", 0),
            profit_factor=metrics.get("profit_factor", 1),
            total_trades=metrics.get("total_trades", 0),
            ai_summary=analysis.get("summary", "Analysis not available"),
            ai_risk_assessment=analysis.get("risk_assessment", ""),
            ai_recommendations=analysis.get("recommendations", []),
            ai_confidence=0.8 if analysis.get("summary") else 0.0,
            overfitting_risk=analysis.get("overfitting_risk", "unknown"),
            market_regime_fit=analysis.get("market_regime", "unknown"),
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            backtest_period=period,
        )

    async def _call_llm(self, agent_type: str, prompt: str) -> str:
        """Call LLM directly for raw response"""
        try:
            from backend.agents.consensus.real_llm_deliberation import (
                get_real_deliberation,
            )

            delib = get_real_deliberation()

            # Use the real_ask function to call LLM directly
            return await delib._real_ask(agent_type, prompt)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_analysis(self, response: str) -> dict[str, Any]:
        """Parse AI response into structured data"""
        analysis = {
            "summary": "",
            "risk_assessment": "",
            "recommendations": [],
            "overfitting_risk": "unknown",
            "market_regime": "unknown",
        }

        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("SUMMARY:"):
                analysis["summary"] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("RISK_ASSESSMENT:"):
                analysis["risk_assessment"] = line.replace(
                    "RISK_ASSESSMENT:", ""
                ).strip()
            elif line.startswith("RECOMMENDATIONS:"):
                recs = line.replace("RECOMMENDATIONS:", "").strip()
                analysis["recommendations"] = [r.strip() for r in recs.split(",")]
            elif line.startswith("OVERFITTING_RISK:"):
                risk = line.replace("OVERFITTING_RISK:", "").strip().lower()
                if "low" in risk:
                    analysis["overfitting_risk"] = "low"
                elif "high" in risk:
                    analysis["overfitting_risk"] = "high"
                else:
                    analysis["overfitting_risk"] = "medium"
            elif line.startswith("MARKET_REGIME:"):
                analysis["market_regime"] = line.replace("MARKET_REGIME:", "").strip()

        return analysis


class AIOptimizationAnalyzer:
    """
    AI-powered optimization result analyzer.

    Interprets optimization results and provides insights on:
    - Parameter selection rationale
    - Overfitting detection
    - Robustness assessment
    """

    OPTIMIZATION_PROMPT = """
You are an expert in algorithmic trading and hyperparameter optimization.

OPTIMIZATION RESULTS:
- Strategy: {strategy_name}
- Symbol: {symbol}
- Optimization Method: {method}

BEST PARAMETERS FOUND:
{params_json}

PERFORMANCE:
- Best Sharpe Ratio: {best_sharpe:.3f}
- Best Return: {best_return:.2f}%
- Total Trials: {total_trials}
- Convergence Score: {convergence:.2f}

PARAMETER RANGES TESTED:
{param_ranges}

Analyze these optimization results:

1. PARAMETER_ANALYSIS: Are these parameters reasonable? Any concerning values?
2. ROBUSTNESS: How robust are these results likely to be out-of-sample?
3. OVERFITTING_WARNING: Any signs of overfitting? (specific concerns)
4. ADJUSTMENTS: What parameter adjustments would you suggest for live trading?

Format your response as:
PARAMETER_ANALYSIS: [your analysis]
ROBUSTNESS: [your robustness assessment]
OVERFITTING_WARNING: [warning or "None detected"]
ADJUSTMENTS: [adj1], [adj2], [adj3]
"""

    def __init__(self):
        self._deliberation = None
        logger.info("🔧 AIOptimizationAnalyzer initialized")

    def _get_deliberation(self):
        """Lazy load deliberation"""
        if self._deliberation is None:
            try:
                from backend.agents.consensus.real_llm_deliberation import (
                    get_real_deliberation,
                )

                self._deliberation = get_real_deliberation()
            except Exception:
                from backend.agents.consensus.deliberation import MultiAgentDeliberation

                self._deliberation = MultiAgentDeliberation()
        return self._deliberation

    async def analyze_optimization(
        self,
        best_params: dict[str, Any],
        best_sharpe: float,
        best_return: float,
        total_trials: int,
        convergence_score: float,
        param_ranges: dict[str, Any],
        strategy_name: str,
        symbol: str,
        method: str = "Bayesian",
    ) -> AIOptimizationResult:
        """
        Analyze optimization results with AI.

        Args:
            best_params: Best parameters found
            best_sharpe: Best Sharpe ratio achieved
            best_return: Best return percentage
            total_trials: Number of optimization trials
            convergence_score: Optimization convergence (0-1)
            param_ranges: Parameter search ranges
            strategy_name: Strategy name
            symbol: Trading symbol
            method: Optimization method used

        Returns:
            AIOptimizationResult with AI insights
        """
        prompt = self.OPTIMIZATION_PROMPT.format(
            strategy_name=strategy_name,
            symbol=symbol,
            method=method,
            params_json=json.dumps(best_params, indent=2),
            best_sharpe=best_sharpe,
            best_return=best_return,
            total_trials=total_trials,
            convergence=convergence_score,
            param_ranges=json.dumps(param_ranges, indent=2),
        )

        # Call LLM directly for raw response
        raw_response = await self._call_llm("deepseek", prompt)

        analysis = self._parse_optimization_analysis(raw_response)

        return AIOptimizationResult(
            best_params=best_params,
            best_sharpe=best_sharpe,
            best_return=best_return,
            total_trials=total_trials,
            convergence_score=convergence_score,
            ai_parameter_analysis=analysis.get("parameter_analysis", ""),
            ai_robustness_assessment=analysis.get("robustness", ""),
            ai_confidence=0.8 if analysis.get("parameter_analysis") else 0.0,
            overfitting_warning=analysis.get("overfitting_warning"),
            suggested_adjustments=analysis.get("adjustments", []),
        )

    async def _call_llm(self, agent_type: str, prompt: str) -> str:
        """Call LLM directly for raw response"""
        try:
            from backend.agents.consensus.real_llm_deliberation import (
                get_real_deliberation,
            )

            delib = get_real_deliberation()
            return await delib._real_ask(agent_type, prompt)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_optimization_analysis(self, response: str) -> dict[str, Any]:
        """Parse optimization analysis response"""
        analysis = {
            "parameter_analysis": "",
            "robustness": "",
            "overfitting_warning": None,
            "adjustments": [],
        }

        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("PARAMETER_ANALYSIS:"):
                analysis["parameter_analysis"] = line.replace(
                    "PARAMETER_ANALYSIS:", ""
                ).strip()
            elif line.startswith("ROBUSTNESS:"):
                analysis["robustness"] = line.replace("ROBUSTNESS:", "").strip()
            elif line.startswith("OVERFITTING_WARNING:"):
                warning = line.replace("OVERFITTING_WARNING:", "").strip()
                if warning.lower() != "none detected":
                    analysis["overfitting_warning"] = warning
            elif line.startswith("ADJUSTMENTS:"):
                adjs = line.replace("ADJUSTMENTS:", "").strip()
                analysis["adjustments"] = [a.strip() for a in adjs.split(",")]

        return analysis


# Global instances
_backtest_analyzer: AIBacktestAnalyzer | None = None
_optimization_analyzer: AIOptimizationAnalyzer | None = None


def get_backtest_analyzer() -> AIBacktestAnalyzer:
    """Get AIBacktestAnalyzer singleton"""
    global _backtest_analyzer
    if _backtest_analyzer is None:
        _backtest_analyzer = AIBacktestAnalyzer()
    return _backtest_analyzer


def get_optimization_analyzer() -> AIOptimizationAnalyzer:
    """Get AIOptimizationAnalyzer singleton"""
    global _optimization_analyzer
    if _optimization_analyzer is None:
        _optimization_analyzer = AIOptimizationAnalyzer()
    return _optimization_analyzer


__all__ = [
    "AIBacktestAnalyzer",
    "AIBacktestResult",
    "AIOptimizationAnalyzer",
    "AIOptimizationResult",
    "get_backtest_analyzer",
    "get_optimization_analyzer",
]
