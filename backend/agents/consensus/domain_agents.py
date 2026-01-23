"""
Specialized Domain Agents

Expert agents for specific domains that provide specialized knowledge:
- TradingStrategyAgent: Strategy analysis and optimization
- RiskManagementAgent: Risk assessment and mitigation
- CodeAuditAgent: Code review and security analysis
- MarketResearchAgent: Market research with web search

Each agent has domain-specific prompts, validation, and scoring.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


class AgentExpertise(Enum):
    """Areas of expertise for domain agents"""

    TRADING_STRATEGY = "trading_strategy"
    RISK_MANAGEMENT = "risk_management"
    CODE_AUDIT = "code_audit"
    MARKET_RESEARCH = "market_research"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    DATA_ANALYSIS = "data_analysis"


@dataclass
class AnalysisResult:
    """Result from domain agent analysis"""

    agent_id: str
    agent_type: str
    expertise: AgentExpertise
    summary: str
    findings: List[Dict[str, Any]]
    recommendations: List[str]
    confidence: float
    risk_level: Optional[str] = None  # low, medium, high, critical
    score: Optional[float] = None  # Domain-specific score
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "expertise": self.expertise.value,
            "summary": self.summary,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "score": self.score,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result from domain agent validation"""

    is_valid: bool
    issues: List[Dict[str, Any]]
    warnings: List[str]
    suggestions: List[str]
    validation_score: float  # 0.0 to 1.0


class DomainAgent(ABC):
    """
    Base class for specialized domain agents

    Each domain agent:
    - Has specific expertise areas
    - Uses domain-specific prompts
    - Validates results against domain rules
    - Provides confidence-weighted outputs
    """

    def __init__(
        self,
        name: str,
        expertise: List[AgentExpertise],
        agent_interface: Optional[Any] = None,
        ask_fn: Optional[Callable[[str], str]] = None,
    ):
        """
        Initialize domain agent

        Args:
            name: Agent name
            expertise: List of expertise areas
            agent_interface: UnifiedAgentInterface instance
            ask_fn: Optional async function (prompt) -> response
        """
        self.name = name
        self.expertise = expertise
        self.agent_interface = agent_interface
        self.ask_fn = ask_fn
        self.agent_id = f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"

        self.analysis_history: List[AnalysisResult] = []

        logger.debug(f"🎯 Domain Agent initialized: {name}")

    @abstractmethod
    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze context with domain expertise

        Args:
            context: Domain-specific context data

        Returns:
            AnalysisResult with findings and recommendations
        """
        pass

    @abstractmethod
    async def validate(
        self, proposal: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate a proposal against domain rules

        Args:
            proposal: The proposal to validate
            context: Optional additional context

        Returns:
            ValidationResult with issues and suggestions
        """
        pass

    async def _ask(self, prompt: str, agent_type: str = "deepseek") -> str:
        """Internal method to ask for AI response"""
        if self.ask_fn:
            return await self.ask_fn(prompt)

        if self.agent_interface:
            try:
                from backend.agents.unified_agent_interface import AgentRequest
                from backend.agents.models import AgentType

                at = (
                    AgentType.DEEPSEEK
                    if "deepseek" in agent_type.lower()
                    else AgentType.PERPLEXITY
                )
                request = AgentRequest(
                    task_type="domain_analysis",
                    agent_type=at,
                    prompt=prompt,
                )
                response = await self.agent_interface.send_request(request)
                return (
                    response.content if response.success else f"Error: {response.error}"
                )
            except Exception as e:
                logger.warning(f"Agent request failed: {e}")
                return f"Error: {e}"

        return self._simulate_response(prompt)

    def _simulate_response(self, prompt: str) -> str:
        """Simulate response for testing"""
        return f"Simulated analysis for: {prompt[:50]}..."

    def _parse_findings(self, response: str) -> List[Dict[str, Any]]:
        """Parse findings from response"""
        findings = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                findings.append(
                    {
                        "description": line[1:].strip(),
                        "severity": "info",
                    }
                )
            elif "FINDING:" in line.upper():
                findings.append(
                    {
                        "description": line.split(":", 1)[-1].strip(),
                        "severity": "medium",
                    }
                )

        return findings

    def _parse_recommendations(self, response: str) -> List[str]:
        """Parse recommendations from response"""
        recommendations = []
        lines = response.split("\n")

        in_recommendations = False
        for line in lines:
            line = line.strip()
            if "recommendation" in line.lower():
                in_recommendations = True
                continue
            if in_recommendations and (
                line.startswith("-") or line.startswith("*") or line.startswith("1")
            ):
                recommendations.append(line.lstrip("-*0123456789. "))

        return recommendations or [
            "Review analysis results",
            "Consider implementing suggested changes",
        ]


class TradingStrategyAgent(DomainAgent):
    """
    Specialized agent for trading strategy analysis

    Expertise:
    - Strategy backtesting interpretation
    - Parameter optimization
    - Risk/reward analysis
    - Market regime detection
    """

    ANALYSIS_PROMPT = """
You are an expert trading strategy analyst. Analyze the following strategy:

Strategy Configuration:
{strategy_config}

Backtest Results:
{backtest_results}

Provide your analysis in this format:
SUMMARY: [One paragraph summary]
STRENGTHS:
- [Strength 1]
- [Strength 2]
WEAKNESSES:
- [Weakness 1]
- [Weakness 2]
RISK_LEVEL: [low/medium/high/critical]
SHARPE_ASSESSMENT: [good/acceptable/poor]
RECOMMENDATIONS:
1. [Recommendation 1]
2. [Recommendation 2]
CONFIDENCE: [0.0-1.0]
"""

    VALIDATION_PROMPT = """
You are validating a trading strategy proposal. Check for:
1. Reasonable parameter ranges
2. Risk management presence
3. Market condition appropriateness
4. Realistic expectations

Proposal:
{proposal}

Context:
{context}

Provide validation in this format:
IS_VALID: [yes/no]
ISSUES:
- [Issue 1]
WARNINGS:
- [Warning 1]
SUGGESTIONS:
- [Suggestion 1]
VALIDATION_SCORE: [0.0-1.0]
"""

    def __init__(
        self, agent_interface: Optional[Any] = None, ask_fn: Optional[Callable] = None
    ):
        super().__init__(
            name="Trading Strategy Expert",
            expertise=[AgentExpertise.TRADING_STRATEGY, AgentExpertise.RISK_MANAGEMENT],
            agent_interface=agent_interface,
            ask_fn=ask_fn,
        )

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze trading strategy"""
        strategy_config = json.dumps(context.get("strategy", {}), indent=2)
        backtest_results = json.dumps(context.get("results", {}), indent=2)

        prompt = self.ANALYSIS_PROMPT.format(
            strategy_config=strategy_config,
            backtest_results=backtest_results,
        )

        response = await self._ask(prompt)

        # Parse response
        summary = self._extract_field(response, "SUMMARY")
        risk_level = self._extract_field(response, "RISK_LEVEL").lower()
        confidence = self._extract_float(response, "CONFIDENCE", 0.7)
        findings = self._parse_findings(response)
        recommendations = self._parse_recommendations(response)

        # Calculate strategy score
        score = self._calculate_strategy_score(context.get("results", {}))

        result = AnalysisResult(
            agent_id=self.agent_id,
            agent_type=self.name,
            expertise=AgentExpertise.TRADING_STRATEGY,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence,
            risk_level=risk_level
            if risk_level in ["low", "medium", "high", "critical"]
            else "medium",
            score=score,
            metadata={
                "strategy_type": context.get("strategy", {}).get("type", "unknown")
            },
        )

        self.analysis_history.append(result)
        return result

    async def validate(
        self, proposal: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate strategy proposal"""
        context_str = json.dumps(context or {}, indent=2)

        prompt = self.VALIDATION_PROMPT.format(
            proposal=proposal,
            context=context_str,
        )

        response = await self._ask(prompt)

        is_valid = "yes" in self._extract_field(response, "IS_VALID").lower()
        validation_score = self._extract_float(response, "VALIDATION_SCORE", 0.5)

        issues = []
        warnings = []
        suggestions = []

        # Parse sections
        lines = response.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if "ISSUES:" in line:
                current_section = "issues"
            elif "WARNINGS:" in line:
                current_section = "warnings"
            elif "SUGGESTIONS:" in line:
                current_section = "suggestions"
            elif line.startswith("-") and current_section:
                item = line[1:].strip()
                if current_section == "issues":
                    issues.append({"description": item, "severity": "high"})
                elif current_section == "warnings":
                    warnings.append(item)
                elif current_section == "suggestions":
                    suggestions.append(item)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            suggestions=suggestions,
            validation_score=validation_score,
        )

    def _calculate_strategy_score(self, results: Dict[str, Any]) -> float:
        """Calculate composite strategy score"""
        score = 50.0  # Base score

        # Sharpe ratio contribution
        sharpe = results.get("sharpe_ratio", 0)
        if sharpe > 2:
            score += 20
        elif sharpe > 1:
            score += 10
        elif sharpe < 0:
            score -= 20

        # Win rate contribution
        win_rate = results.get("win_rate", 0.5)
        score += (win_rate - 0.5) * 40  # -20 to +20

        # Max drawdown penalty
        max_dd = results.get("max_drawdown", 0.2)
        if max_dd > 0.3:
            score -= 20
        elif max_dd > 0.2:
            score -= 10

        # Profit factor
        pf = results.get("profit_factor", 1)
        if pf > 2:
            score += 15
        elif pf > 1.5:
            score += 10

        return max(0, min(100, score))

    def _extract_field(self, text: str, field: str) -> str:
        """Extract field value from text"""
        for line in text.split("\n"):
            if field.upper() + ":" in line.upper():
                return line.split(":", 1)[-1].strip()
        return ""

    def _extract_float(self, text: str, field: str, default: float) -> float:
        """Extract float value from text"""
        value = self._extract_field(text, field)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


class RiskManagementAgent(DomainAgent):
    """
    Specialized agent for risk assessment

    Expertise:
    - Position sizing recommendations
    - Stop loss optimization
    - Portfolio risk analysis
    - Maximum drawdown prevention
    """

    ANALYSIS_PROMPT = """
You are a risk management expert. Analyze risk factors for:

Portfolio Configuration:
{portfolio_config}

Current Positions:
{positions}

Market Conditions:
{market_conditions}

Provide risk analysis:
SUMMARY: [Risk overview]
RISK_LEVEL: [low/medium/high/critical]
EXPOSURE_ISSUES:
- [Issue 1]
CONCENTRATION_RISKS:
- [Risk 1]
RECOMMENDATIONS:
1. [Risk mitigation 1]
2. [Risk mitigation 2]
MAX_RECOMMENDED_POSITION_SIZE: [percentage]
SUGGESTED_STOP_LOSS: [percentage]
CONFIDENCE: [0.0-1.0]
"""

    def __init__(
        self, agent_interface: Optional[Any] = None, ask_fn: Optional[Callable] = None
    ):
        super().__init__(
            name="Risk Management Expert",
            expertise=[AgentExpertise.RISK_MANAGEMENT],
            agent_interface=agent_interface,
            ask_fn=ask_fn,
        )

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze risk factors"""
        prompt = self.ANALYSIS_PROMPT.format(
            portfolio_config=json.dumps(context.get("portfolio", {}), indent=2),
            positions=json.dumps(context.get("positions", []), indent=2),
            market_conditions=json.dumps(context.get("market", {}), indent=2),
        )

        response = await self._ask(prompt)

        summary = self._extract_value(response, "SUMMARY")
        risk_level = self._extract_value(response, "RISK_LEVEL").lower()
        confidence = float(self._extract_value(response, "CONFIDENCE") or "0.7")

        findings = []
        for line in response.split("\n"):
            if line.strip().startswith("-"):
                findings.append(
                    {"description": line.strip()[1:].strip(), "type": "risk"}
                )

        recommendations = self._parse_recommendations(response)

        return AnalysisResult(
            agent_id=self.agent_id,
            agent_type=self.name,
            expertise=AgentExpertise.RISK_MANAGEMENT,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            confidence=min(1.0, max(0.0, confidence)),
            risk_level=risk_level
            if risk_level in ["low", "medium", "high", "critical"]
            else "medium",
            metadata={
                "max_position_size": self._extract_value(
                    response, "MAX_RECOMMENDED_POSITION_SIZE"
                ),
                "suggested_stop_loss": self._extract_value(
                    response, "SUGGESTED_STOP_LOSS"
                ),
            },
        )

    async def validate(
        self, proposal: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate risk parameters"""
        # Check against risk rules
        issues = []
        warnings = []
        suggestions = []

        context = context or {}

        # Check position size
        position_size = context.get("position_size", 0)
        if position_size > 0.1:  # More than 10%
            issues.append(
                {
                    "description": f"Position size {position_size * 100}% exceeds recommended 10%",
                    "severity": "high",
                }
            )

        # Check stop loss
        stop_loss = context.get("stop_loss", 0)
        if stop_loss > 0.05:  # More than 5%
            warnings.append(f"Stop loss at {stop_loss * 100}% may be too wide")

        # Check leverage
        leverage = context.get("leverage", 1)
        if leverage > 5:
            issues.append(
                {
                    "description": f"Leverage {leverage}x is dangerous",
                    "severity": "critical",
                }
            )
        elif leverage > 2:
            warnings.append(f"Leverage {leverage}x adds significant risk")

        is_valid = len([i for i in issues if i.get("severity") == "critical"]) == 0
        validation_score = 1.0 - (len(issues) * 0.2 + len(warnings) * 0.05)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            suggestions=suggestions
            or ["Consider reducing position sizes", "Add stop losses"],
            validation_score=max(0.0, validation_score),
        )

    def _extract_value(self, text: str, field: str) -> str:
        for line in text.split("\n"):
            if field.upper() + ":" in line.upper():
                return line.split(":", 1)[-1].strip()
        return ""


class CodeAuditAgent(DomainAgent):
    """
    Specialized agent for code review and security

    Expertise:
    - Security vulnerability detection
    - Performance analysis
    - Best practices compliance
    - Bug detection
    """

    ANALYSIS_PROMPT = """
You are a senior code auditor. Review this code:

```{language}
{code}
```

Purpose: {purpose}

Analyze for:
1. Security vulnerabilities
2. Performance issues
3. Code quality
4. Best practices

Provide analysis:
SUMMARY: [Overview]
SECURITY_ISSUES:
- [Issue with severity]
PERFORMANCE_ISSUES:
- [Issue]
QUALITY_ISSUES:
- [Issue]
RECOMMENDATIONS:
1. [Fix 1]
2. [Fix 2]
RISK_LEVEL: [low/medium/high/critical]
CODE_QUALITY_SCORE: [0-100]
CONFIDENCE: [0.0-1.0]
"""

    def __init__(
        self, agent_interface: Optional[Any] = None, ask_fn: Optional[Callable] = None
    ):
        super().__init__(
            name="Code Audit Expert",
            expertise=[
                AgentExpertise.CODE_AUDIT,
                AgentExpertise.PERFORMANCE_OPTIMIZATION,
            ],
            agent_interface=agent_interface,
            ask_fn=ask_fn,
        )

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Analyze code for issues"""
        prompt = self.ANALYSIS_PROMPT.format(
            language=context.get("language", "python"),
            code=context.get("code", ""),
            purpose=context.get("purpose", "Unknown"),
        )

        response = await self._ask(prompt)

        summary = self._extract_value(response, "SUMMARY")
        risk_level = self._extract_value(response, "RISK_LEVEL").lower()
        score = float(self._extract_value(response, "CODE_QUALITY_SCORE") or "70")
        confidence = float(self._extract_value(response, "CONFIDENCE") or "0.8")

        findings = self._parse_findings(response)
        recommendations = self._parse_recommendations(response)

        return AnalysisResult(
            agent_id=self.agent_id,
            agent_type=self.name,
            expertise=AgentExpertise.CODE_AUDIT,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence,
            risk_level=risk_level
            if risk_level in ["low", "medium", "high", "critical"]
            else "low",
            score=score,
            metadata={"language": context.get("language", "python")},
        )

    async def validate(
        self, proposal: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate code changes"""
        issues = []
        warnings = []
        suggestions = []

        # Check for dangerous patterns
        dangerous_patterns = [
            ("eval(", "CRITICAL: eval() is dangerous"),
            ("exec(", "CRITICAL: exec() is dangerous"),
            ("__import__", "WARNING: Dynamic imports risky"),
            ("rm -rf", "CRITICAL: Destructive file operation"),
            ("os.remove", "WARNING: File deletion"),
            ("DROP TABLE", "CRITICAL: Database destruction"),
        ]

        for pattern, message in dangerous_patterns:
            if pattern in proposal:
                if "CRITICAL" in message:
                    issues.append({"description": message, "severity": "critical"})
                else:
                    warnings.append(message)

        is_valid = len([i for i in issues if i.get("severity") == "critical"]) == 0

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            suggestions=suggestions or ["Review security implications"],
            validation_score=1.0 - (len(issues) * 0.3 + len(warnings) * 0.1),
        )

    def _extract_value(self, text: str, field: str) -> str:
        for line in text.split("\n"):
            if field.upper() + ":" in line.upper():
                return line.split(":", 1)[-1].strip()
        return ""


class MarketResearchAgent(DomainAgent):
    """
    Specialized agent for market research with web search

    Uses Perplexity for real-time market data and research.

    Expertise:
    - Market condition analysis
    - News impact assessment
    - Competitor analysis
    - Trend identification
    """

    ANALYSIS_PROMPT = """
You are a market research analyst. Research the following:

Query: {query}
Asset: {asset}
Timeframe: {timeframe}

Provide research findings:
SUMMARY: [Market overview]
CURRENT_TREND: [bullish/bearish/neutral]
KEY_FACTORS:
- [Factor 1]
- [Factor 2]
NEWS_IMPACT:
- [News item with impact]
RISK_FACTORS:
- [Risk 1]
RECOMMENDATIONS:
1. [Action 1]
2. [Action 2]
CONFIDENCE: [0.0-1.0]
"""

    def __init__(
        self, agent_interface: Optional[Any] = None, ask_fn: Optional[Callable] = None
    ):
        super().__init__(
            name="Market Research Expert",
            expertise=[AgentExpertise.MARKET_RESEARCH, AgentExpertise.DATA_ANALYSIS],
            agent_interface=agent_interface,
            ask_fn=ask_fn,
        )

    async def analyze(self, context: Dict[str, Any]) -> AnalysisResult:
        """Research market conditions"""
        prompt = self.ANALYSIS_PROMPT.format(
            query=context.get("query", ""),
            asset=context.get("asset", "BTC"),
            timeframe=context.get("timeframe", "1D"),
        )

        # Use Perplexity for web search capability
        response = await self._ask(prompt, agent_type="perplexity")

        summary = self._extract_value(response, "SUMMARY")
        trend = self._extract_value(response, "CURRENT_TREND").lower()
        confidence = float(self._extract_value(response, "CONFIDENCE") or "0.6")

        findings = self._parse_findings(response)
        recommendations = self._parse_recommendations(response)

        return AnalysisResult(
            agent_id=self.agent_id,
            agent_type=self.name,
            expertise=AgentExpertise.MARKET_RESEARCH,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence,
            metadata={
                "trend": trend,
                "asset": context.get("asset", "BTC"),
            },
        )

    async def validate(
        self, proposal: str, context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate market-based decision"""
        return ValidationResult(
            is_valid=True,
            issues=[],
            warnings=["Market conditions can change rapidly"],
            suggestions=["Monitor news for changes", "Set alerts for key levels"],
            validation_score=0.7,
        )

    def _extract_value(self, text: str, field: str) -> str:
        for line in text.split("\n"):
            if field.upper() + ":" in line.upper():
                return line.split(":", 1)[-1].strip()
        return ""


class DomainAgentRegistry:
    """
    Registry for domain agents

    Provides centralized access to specialized agents.
    """

    def __init__(self, agent_interface: Optional[Any] = None):
        self.agent_interface = agent_interface
        self._agents: Dict[str, DomainAgent] = {}

        # Register default agents
        self.register("trading", TradingStrategyAgent(agent_interface))
        self.register("risk", RiskManagementAgent(agent_interface))
        self.register("code", CodeAuditAgent(agent_interface))
        self.register("market", MarketResearchAgent(agent_interface))

        logger.info(
            f"🎯 Domain Agent Registry initialized with {len(self._agents)} agents"
        )

    def register(self, name: str, agent: DomainAgent) -> None:
        """Register a domain agent"""
        self._agents[name] = agent

    def get(self, name: str) -> Optional[DomainAgent]:
        """Get agent by name"""
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """List registered agent names"""
        return list(self._agents.keys())

    def get_by_expertise(self, expertise: AgentExpertise) -> List[DomainAgent]:
        """Get agents with specific expertise"""
        return [
            agent for agent in self._agents.values() if expertise in agent.expertise
        ]

    async def analyze_with_all(
        self, context: Dict[str, Any]
    ) -> Dict[str, AnalysisResult]:
        """Run analysis with all relevant agents"""
        results = {}

        for name, agent in self._agents.items():
            try:
                result = await agent.analyze(context)
                results[name] = result
            except Exception as e:
                logger.warning(f"Agent {name} analysis failed: {e}")

        return results


__all__ = [
    "DomainAgent",
    "TradingStrategyAgent",
    "RiskManagementAgent",
    "CodeAuditAgent",
    "MarketResearchAgent",
    "DomainAgentRegistry",
    "AgentExpertise",
    "AnalysisResult",
    "ValidationResult",
]
