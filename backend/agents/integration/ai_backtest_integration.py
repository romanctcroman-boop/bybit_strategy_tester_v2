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

    # Original backtest metrics — core
    net_pnl: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int

    # Extended metrics
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    recovery_factor: float = 0.0
    payoff_ratio: float = 0.0
    avg_trade_duration: str = "N/A"
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade_pnl: float = 0.0

    # AI Analysis
    ai_summary: str = ""
    ai_risk_assessment: str = ""
    ai_strengths: list[str] = field(default_factory=list)
    ai_weaknesses: list[str] = field(default_factory=list)
    ai_recommendations: list[str] = field(default_factory=list)
    ai_confidence: float = 0.0
    ai_grade: str = "C"  # A/B/C/D/F
    overfitting_risk: str = "unknown"  # "low", "medium", "high"
    overfitting_reason: str = ""
    market_regime_fit: str = "unknown"  # trending/ranging/volatile/all_conditions
    market_regime_detail: str = ""

    # Multi-agent info
    agents_used: list[str] = field(default_factory=list)

    # Metadata
    strategy_name: str = ""
    symbol: str = ""
    timeframe: str = ""
    backtest_period: str = ""
    analysis_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": {
                "net_pnl": self.net_pnl,
                "total_return_pct": self.total_return_pct,
                "sharpe_ratio": self.sharpe_ratio,
                "sortino_ratio": self.sortino_ratio,
                "max_drawdown_pct": self.max_drawdown_pct,
                "win_rate": self.win_rate,
                "profit_factor": self.profit_factor,
                "total_trades": self.total_trades,
                "calmar_ratio": self.calmar_ratio,
                "avg_win": self.avg_win,
                "avg_loss": self.avg_loss,
                "max_consecutive_wins": self.max_consecutive_wins,
                "max_consecutive_losses": self.max_consecutive_losses,
                "recovery_factor": self.recovery_factor,
                "payoff_ratio": self.payoff_ratio,
                "avg_trade_duration": self.avg_trade_duration,
                "best_trade": self.best_trade,
                "worst_trade": self.worst_trade,
                "avg_trade_pnl": self.avg_trade_pnl,
            },
            "ai_analysis": {
                "summary": self.ai_summary,
                "risk_assessment": self.ai_risk_assessment,
                "strengths": self.ai_strengths,
                "weaknesses": self.ai_weaknesses,
                "recommendations": self.ai_recommendations,
                "confidence": self.ai_confidence,
                "grade": self.ai_grade,
                "overfitting_risk": self.overfitting_risk,
                "overfitting_reason": self.overfitting_reason,
                "market_regime_fit": self.market_regime_fit,
                "market_regime_detail": self.market_regime_detail,
                "agents_used": self.agents_used,
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

    ANALYSIS_PROMPT = """You are an expert quantitative analyst reviewing trading strategy backtest results.
Return your analysis as a JSON object — NO markdown, NO explanation outside JSON.

BACKTEST CONTEXT:
- Strategy: {strategy_name}
- Symbol: {symbol}
- Timeframe: {timeframe}
- Period: {period}

CORE METRICS:
- Net PnL: ${net_pnl:,.2f}
- Total Return: {total_return_pct:.2f}%
- Sharpe Ratio: {sharpe_ratio:.2f}
- Sortino Ratio: {sortino_ratio:.2f}
- Max Drawdown: {max_drawdown_pct:.2f}%
- Win Rate: {win_rate:.1%}
- Profit Factor: {profit_factor:.2f}
- Total Trades: {total_trades}

RISK METRICS:
- Calmar Ratio: {calmar_ratio:.2f}
- Avg Win: ${avg_win:,.2f}
- Avg Loss: ${avg_loss:,.2f}
- Max Consecutive Wins: {max_consecutive_wins}
- Max Consecutive Losses: {max_consecutive_losses}
- Recovery Factor: {recovery_factor:.2f}
- Payoff Ratio: {payoff_ratio:.2f}

TRADE STATISTICS:
- Avg Trade Duration: {avg_trade_duration}
- Best Trade: ${best_trade:,.2f}
- Worst Trade: ${worst_trade:,.2f}
- Avg Trade PnL: ${avg_trade_pnl:,.2f}

GRADING CRITERIA (use these EXACTLY):
- A: Sharpe >= 1.5 AND Profit Factor >= 1.8 AND Max Drawdown <= 15% AND net PnL > 0
- B: Sharpe >= 0.8 AND Profit Factor >= 1.3 AND Max Drawdown <= 25% AND net PnL > 0
- C: Sharpe >= 0.3 AND Profit Factor >= 1.0 AND net PnL >= 0
- D: Sharpe < 0.3 OR Profit Factor < 1.0 OR net PnL < 0 (but not severely negative)
- F: Sharpe < -0.5 OR Profit Factor < 0.7 OR Total Return < -30%

OVERFITTING RISK CRITERIA:
- low: Total Trades >= 100 AND Max Drawdown <= 20% AND no extreme metrics
- medium: Total Trades 50-100 OR Max Drawdown 20-35% OR payoff ratio > 3
- high: Total Trades < 50 OR Max Drawdown > 35% OR Sharpe > 3.5 (suspiciously high)

Return ONLY this JSON:
{{
  "summary": "2-3 sentence overall assessment of strategy quality",
  "risk_assessment": "Detailed evaluation of risk metrics — drawdown, Sharpe, Sortino, recovery",
  "strengths": ["strength1", "strength2", "strength3"],
  "weaknesses": ["weakness1", "weakness2"],
  "recommendations": ["specific actionable improvement 1", "improvement 2", "improvement 3"],
  "overfitting_risk": "low|medium|high",
  "overfitting_reason": "Specific reason for the overfitting assessment",
  "market_regime": "trending|ranging|volatile|all_conditions",
  "market_regime_detail": "Why this strategy fits that regime",
  "grade": "A|B|C|D|F",
  "confidence": 0.85
}}"""

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
        agents: list[str] | None = None,
    ) -> AIBacktestResult:
        """
        Analyze backtest results with AI (supports DeepSeek, Qwen, Perplexity).

        Args:
            metrics: Backtest metrics dict (all available metrics)
            strategy_name: Name of the strategy
            symbol: Trading symbol
            timeframe: Chart timeframe
            period: Backtest period description
            agents: Which AI agents to use (default: all 3)

        Returns:
            AIBacktestResult with AI insights
        """
        agents = agents or ["deepseek", "qwen", "perplexity"]

        # Build prompt with extended metrics
        prompt = self.ANALYSIS_PROMPT.format(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            period=period,
            net_pnl=metrics.get("net_pnl", 0),
            total_return_pct=metrics.get("total_return_pct", metrics.get("total_return", 0)),
            sharpe_ratio=metrics.get("sharpe_ratio", 0),
            sortino_ratio=metrics.get("sortino_ratio", 0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0)),
            win_rate=metrics.get("win_rate", 0),
            profit_factor=metrics.get("profit_factor", 1),
            total_trades=metrics.get("total_trades", 0),
            calmar_ratio=metrics.get("calmar_ratio", 0),
            avg_win=metrics.get("avg_win", 0),
            avg_loss=metrics.get("avg_loss", 0),
            max_consecutive_wins=metrics.get("max_consecutive_wins", 0),
            max_consecutive_losses=metrics.get("max_consecutive_losses", 0),
            recovery_factor=metrics.get("recovery_factor", 0),
            payoff_ratio=metrics.get("payoff_ratio", 0),
            avg_trade_duration=metrics.get("avg_trade_duration", "N/A"),
            best_trade=metrics.get("best_trade", 0),
            worst_trade=metrics.get("worst_trade", 0),
            avg_trade_pnl=metrics.get("avg_trade_pnl", 0),
        )

        # Call ALL agents and merge results (consensus)
        all_analyses = []
        for agent_name in agents:
            try:
                raw_response = await self._call_llm(agent_name, prompt)
                if raw_response:
                    analysis = self._parse_analysis(raw_response)
                    analysis["_agent"] = agent_name
                    all_analyses.append(analysis)
                    logger.info(f"✅ {agent_name} analysis complete")
            except Exception as e:
                logger.warning(f"⚠️ {agent_name} analysis failed: {e}")

        # Merge analyses from all agents
        merged = self._merge_analyses(all_analyses)

        return AIBacktestResult(
            # Core metrics
            net_pnl=metrics.get("net_pnl", 0),
            total_return_pct=metrics.get("total_return_pct", metrics.get("total_return", 0)),
            sharpe_ratio=metrics.get("sharpe_ratio", 0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0)),
            win_rate=metrics.get("win_rate", 0),
            profit_factor=metrics.get("profit_factor", 1),
            total_trades=metrics.get("total_trades", 0),
            # Extended metrics
            sortino_ratio=metrics.get("sortino_ratio", 0),
            calmar_ratio=metrics.get("calmar_ratio", 0),
            avg_win=metrics.get("avg_win", 0),
            avg_loss=metrics.get("avg_loss", 0),
            max_consecutive_wins=metrics.get("max_consecutive_wins", 0),
            max_consecutive_losses=metrics.get("max_consecutive_losses", 0),
            recovery_factor=metrics.get("recovery_factor", 0),
            payoff_ratio=metrics.get("payoff_ratio", 0),
            avg_trade_duration=str(metrics.get("avg_trade_duration", "N/A")),
            best_trade=metrics.get("best_trade", 0),
            worst_trade=metrics.get("worst_trade", 0),
            avg_trade_pnl=metrics.get("avg_trade_pnl", 0),
            # AI analysis
            ai_summary=merged.get("summary", "Analysis not available"),
            ai_risk_assessment=merged.get("risk_assessment", ""),
            ai_strengths=merged.get("strengths", []),
            ai_weaknesses=merged.get("weaknesses", []),
            ai_recommendations=merged.get("recommendations", []),
            ai_confidence=merged.get("confidence", 0.0),
            ai_grade=merged.get("grade", "C"),
            overfitting_risk=merged.get("overfitting_risk", "unknown"),
            overfitting_reason=merged.get("overfitting_reason", ""),
            market_regime_fit=merged.get("market_regime", "unknown"),
            market_regime_detail=merged.get("market_regime_detail", ""),
            agents_used=merged.get("agents_used", []),
            # Metadata
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
        """Parse AI response — supports JSON (primary) and text (fallback)."""
        analysis = {
            "summary": "",
            "risk_assessment": "",
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "overfitting_risk": "unknown",
            "overfitting_reason": "",
            "market_regime": "unknown",
            "market_regime_detail": "",
            "grade": "C",
            "confidence": 0.0,
        }

        if not response:
            return analysis

        # Try JSON parsing first (new format)
        try:
            text = response.strip()
            # Remove markdown code fences if present
            if "```json" in text:
                text = text.split("```json", 1)[1]
                if "```" in text:
                    text = text.split("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1]
                if "```" in text:
                    text = text.split("```", 1)[0]
            text = text.strip()

            # Find JSON object
            brace_start = text.find("{")
            if brace_start >= 0:
                depth = 0
                for i in range(brace_start, len(text)):
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                        if depth == 0:
                            json_str = text[brace_start : i + 1]
                            parsed = json.loads(json_str)
                            # Merge parsed fields into analysis
                            for key in analysis:
                                if key in parsed:
                                    analysis[key] = parsed[key]
                            if parsed.get("summary"):
                                analysis["confidence"] = parsed.get("confidence", 0.85)
                            logger.debug("Parsed AI analysis as JSON successfully")
                            return analysis
        except (json.JSONDecodeError, IndexError, ValueError):
            logger.debug("JSON parsing failed, falling back to text parsing")

        # Fallback: text-based parsing (legacy format)
        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("SUMMARY:"):
                analysis["summary"] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("RISK_ASSESSMENT:"):
                analysis["risk_assessment"] = line.replace("RISK_ASSESSMENT:", "").strip()
            elif line.startswith("RECOMMENDATIONS:"):
                recs = line.replace("RECOMMENDATIONS:", "").strip()
                analysis["recommendations"] = [r.strip() for r in recs.split(",") if r.strip()]
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

        if analysis["summary"]:
            analysis["confidence"] = 0.7  # Lower confidence for text-parsed responses

        return analysis

    def _merge_analyses(self, analyses: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge analyses from multiple agents into a consensus result.

        Strategy:
        - summary: combine unique summaries
        - recommendations: deduplicate, take top 5
        - overfitting_risk: most common vote
        - confidence: average
        - strengths/weaknesses: merge and deduplicate
        """
        if not analyses:
            return {
                "summary": "Analysis not available — no agents responded",
                "risk_assessment": "",
                "recommendations": [],
                "overfitting_risk": "unknown",
                "market_regime": "unknown",
                "confidence": 0.0,
            }

        if len(analyses) == 1:
            return analyses[0]

        # Multi-agent consensus
        agent_names = [a.get("_agent", "unknown") for a in analyses]
        logger.info(f"🤝 Merging analyses from {len(analyses)} agents: {agent_names}")

        # Summary: combine with agent attribution
        summaries = []
        for a in analyses:
            if a.get("summary"):
                agent = a.get("_agent", "AI")
                summaries.append(f"[{agent.upper()}] {a['summary']}")
        merged_summary = " | ".join(summaries) if summaries else "No summary available"

        # Risk assessment: combine
        risk_parts = [a.get("risk_assessment", "") for a in analyses if a.get("risk_assessment")]
        merged_risk = " ".join(risk_parts) if risk_parts else ""

        # Recommendations: deduplicate, limit to 5
        all_recs = []
        seen_recs: set[str] = set()
        for a in analyses:
            for rec in a.get("recommendations", []):
                rec_lower = rec.lower().strip()
                if rec_lower and rec_lower not in seen_recs:
                    seen_recs.add(rec_lower)
                    all_recs.append(rec)

        # Strengths & weaknesses: merge
        all_strengths = list({s for a in analyses for s in a.get("strengths", [])})
        all_weaknesses = list({w for a in analyses for w in a.get("weaknesses", [])})

        # Overfitting risk: majority vote
        risk_votes = [a.get("overfitting_risk", "unknown") for a in analyses]
        risk_counter: dict[str, int] = {}
        for v in risk_votes:
            risk_counter[v] = risk_counter.get(v, 0) + 1
        merged_risk_level = (
            sorted(risk_counter.items(), key=lambda x: x[1], reverse=True)[0][0] if risk_counter else "unknown"
        )

        # Market regime: majority vote
        regime_votes = [a.get("market_regime", "unknown") for a in analyses]
        regime_counter: dict[str, int] = {}
        for v in regime_votes:
            regime_counter[v] = regime_counter.get(v, 0) + 1
        merged_regime = (
            sorted(regime_counter.items(), key=lambda x: x[1], reverse=True)[0][0] if regime_counter else "unknown"
        )

        # Confidence: average
        confidences = [a.get("confidence", 0) for a in analyses if a.get("confidence")]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        # Grade: majority vote
        grade_votes = [a.get("grade", "C").upper().strip() for a in analyses]
        grade_counter: dict[str, int] = {}
        for v in grade_votes:
            grade_counter[v] = grade_counter.get(v, 0) + 1
        merged_grade = sorted(grade_counter.items(), key=lambda x: x[1], reverse=True)[0][0] if grade_counter else "C"

        # Overfitting reason: take longest (most detailed)
        overfit_reasons = [a.get("overfitting_reason", "") for a in analyses if a.get("overfitting_reason")]
        merged_overfit_reason = max(overfit_reasons, key=len) if overfit_reasons else ""

        # Market regime detail: take longest (most detailed)
        regime_details = [a.get("market_regime_detail", "") for a in analyses if a.get("market_regime_detail")]
        merged_regime_detail = max(regime_details, key=len) if regime_details else ""

        return {
            "summary": merged_summary,
            "risk_assessment": merged_risk,
            "strengths": all_strengths[:5],
            "weaknesses": all_weaknesses[:5],
            "recommendations": all_recs[:5],
            "overfitting_risk": merged_risk_level,
            "overfitting_reason": merged_overfit_reason,
            "market_regime": merged_regime,
            "market_regime_detail": merged_regime_detail,
            "grade": merged_grade,
            "confidence": round(avg_confidence, 2),
            "agents_used": agent_names,
        }


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
        analysis: dict[str, Any] = {
            "parameter_analysis": "",
            "robustness": "",
            "overfitting_warning": None,
            "adjustments": [],
        }

        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("PARAMETER_ANALYSIS:"):
                analysis["parameter_analysis"] = line.replace("PARAMETER_ANALYSIS:", "").strip()
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
