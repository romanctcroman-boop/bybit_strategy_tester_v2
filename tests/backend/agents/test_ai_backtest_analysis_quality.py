"""
Real API Quality Test — AI Backtest Analysis (DeepSeek, Qwen, Perplexity).

PURPOSE:
  Sends realistic backtest metrics to each AI agent and validates that they
  produce structured, high-quality analysis with all required JSON fields.
  Tests both the ANALYSIS_PROMPT quality and the _parse_analysis() parser.

HOW IT WORKS:
  1. Prepare realistic backtest metric scenarios (good, bad, mediocre strategies)
  2. Build the ANALYSIS_PROMPT with real numbers
  3. Send via LLM clients (DeepSeek/Qwen/Perplexity)
  4. Parse JSON response and score completeness + correctness
  5. Verify grade/risk assessment match the metric profile

USAGE:
  pytest tests/backend/agents/test_ai_backtest_analysis_quality.py -v -m api_live
  pytest tests/backend/agents/test_ai_backtest_analysis_quality.py -v -m api_live -k deepseek
  pytest tests/backend/agents/test_ai_backtest_analysis_quality.py -v -m api_live -k "scenario"

COST ESTIMATE:
  3 scenarios x 3 agents = 9 API calls
  ~$0.02-0.05 total

REQUIRES:
  Environment variables: DEEPSEEK_API_KEY, QWEN_API_KEY, PERPLEXITY_API_KEY
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import aiohttp
import pytest
from dotenv import load_dotenv
from loguru import logger

# Load .env BEFORE importing backend modules
load_dotenv(override=True)

from backend.agents.integration.ai_backtest_integration import AIBacktestAnalyzer
from backend.agents.llm.base_client import LLMConfig, LLMMessage, LLMProvider, LLMResponse, OpenAICompatibleClient
from backend.agents.llm.clients.deepseek import DeepSeekClient
from backend.agents.llm.clients.perplexity import PerplexityClient
from backend.agents.llm.clients.qwen import QwenClient

# =============================================================================
# TEST SCENARIOS — realistic backtest metric profiles
# =============================================================================

SCENARIOS: dict[str, dict[str, Any]] = {
    "excellent_strategy": {
        "description": "High-performing momentum strategy — should get A/B grade, low overfit risk",
        "metrics": {
            "net_pnl": 25000.0,
            "total_return_pct": 125.0,
            "sharpe_ratio": 2.1,
            "sortino_ratio": 3.2,
            "max_drawdown_pct": 8.5,
            "win_rate": 0.62,
            "profit_factor": 2.3,
            "total_trades": 187,
            "calmar_ratio": 14.7,
            "avg_win": 450.0,
            "avg_loss": -195.0,
            "max_consecutive_wins": 8,
            "max_consecutive_losses": 3,
            "recovery_factor": 5.2,
            "payoff_ratio": 2.31,
            "avg_trade_duration": "4h 30m",
            "best_trade": 3200.0,
            "worst_trade": -820.0,
            "avg_trade_pnl": 133.69,
            "winning_trades": 116,
            "losing_trades": 71,
        },
        "strategy_name": "Momentum RSI + SuperTrend",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "period": "2025-01-01 to 2025-06-30",
        "expected_grade": ["A", "B"],
        "expected_overfit_risk": ["low", "medium"],
        "expected_regime": ["trending", "all_conditions"],
    },
    "poor_strategy": {
        "description": "Losing strategy with high drawdown — should get D/F grade, high overfit risk",
        "metrics": {
            "net_pnl": -8500.0,
            "total_return_pct": -42.5,
            "sharpe_ratio": -0.8,
            "sortino_ratio": -1.1,
            "max_drawdown_pct": 55.0,
            "win_rate": 0.35,
            "profit_factor": 0.6,
            "total_trades": 312,
            "calmar_ratio": -0.77,
            "avg_win": 120.0,
            "avg_loss": -180.0,
            "max_consecutive_wins": 3,
            "max_consecutive_losses": 11,
            "recovery_factor": -0.5,
            "payoff_ratio": 0.67,
            "avg_trade_duration": "45m",
            "best_trade": 950.0,
            "worst_trade": -1800.0,
            "avg_trade_pnl": -27.24,
            "winning_trades": 109,
            "losing_trades": 203,
        },
        "strategy_name": "Aggressive Scalper v3",
        "symbol": "ETHUSDT",
        "timeframe": "5m",
        "period": "2025-03-01 to 2025-06-30",
        "expected_grade": ["D", "F"],
        "expected_overfit_risk": ["medium", "high"],
        "expected_regime": ["ranging", "volatile", "all_conditions", "trending"],
    },
    "mediocre_strategy": {
        "description": "Average strategy, slight profit — should get B/C grade",
        "metrics": {
            "net_pnl": 3200.0,
            "total_return_pct": 16.0,
            "sharpe_ratio": 0.9,
            "sortino_ratio": 1.1,
            "max_drawdown_pct": 22.0,
            "win_rate": 0.48,
            "profit_factor": 1.15,
            "total_trades": 95,
            "calmar_ratio": 0.73,
            "avg_win": 280.0,
            "avg_loss": -240.0,
            "max_consecutive_wins": 5,
            "max_consecutive_losses": 6,
            "recovery_factor": 1.1,
            "payoff_ratio": 1.17,
            "avg_trade_duration": "8h 15m",
            "best_trade": 1500.0,
            "worst_trade": -1100.0,
            "avg_trade_pnl": 33.68,
            "winning_trades": 46,
            "losing_trades": 49,
        },
        "strategy_name": "MA Cross + Bollinger Filter",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "period": "2025-01-15 to 2025-06-15",
        "expected_grade": ["B", "C", "D"],
        "expected_overfit_risk": ["low", "medium"],
        "expected_regime": ["trending", "ranging", "all_conditions", "volatile"],
    },
}

# Required JSON fields in AI response
REQUIRED_FIELDS = [
    "summary",
    "risk_assessment",
    "strengths",
    "weaknesses",
    "recommendations",
    "overfitting_risk",
    "market_regime",
    "grade",
    "confidence",
]


# =============================================================================
# Helpers
# =============================================================================


def _parse_llm_json(response_text: str) -> dict[str, Any] | None:
    """Parse JSON from LLM response, handling markdown fences."""
    text = response_text.strip()

    # Remove markdown code fences
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
    if brace_start < 0:
        return None

    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                json_str = text[brace_start : i + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None
    return None


def _score_analysis(
    parsed: dict[str, Any],
    scenario: dict[str, Any],
    scenario_name: str,
) -> dict[str, Any]:
    """Score the quality of AI analysis response.

    Checks:
    - Field completeness (all required fields present)
    - Summary quality (non-empty, mentions key metrics)
    - Recommendations count (>= 2)
    - Grade correctness (matches expected)
    - Overfitting risk correctness
    - Confidence in valid range

    Returns:
        {
            "scenario": str,
            "fields_present": N/M,
            "summary_quality": 0-1,
            "recommendations_quality": 0-1,
            "grade_correct": bool,
            "overfit_correct": bool,
            "confidence_valid": bool,
            "total_score": 0.0-1.0,
            "details": {...}
        }
    """
    result: dict[str, Any] = {
        "scenario": scenario_name,
        "fields_present": 0,
        "fields_total": len(REQUIRED_FIELDS),
        "summary_quality": 0.0,
        "recommendations_quality": 0.0,
        "grade_correct": False,
        "overfit_correct": False,
        "confidence_valid": False,
        "details": {},
    }

    # 1. Field completeness
    for field in REQUIRED_FIELDS:
        if field in parsed and parsed[field] not in (None, "", []):
            result["fields_present"] += 1
        else:
            result["details"][f"missing_{field}"] = f"Field '{field}' is missing or empty"

    # 2. Summary quality — should be non-trivial
    summary = parsed.get("summary", "")
    if isinstance(summary, str) and len(summary) > 20:
        result["summary_quality"] = 1.0
    elif isinstance(summary, str) and len(summary) > 5:
        result["summary_quality"] = 0.5
    else:
        result["details"]["summary"] = f"Too short: '{summary[:50]}'"

    # 3. Recommendations quality
    recs = parsed.get("recommendations", [])
    if isinstance(recs, list) and len(recs) >= 3:
        result["recommendations_quality"] = 1.0
    elif isinstance(recs, list) and len(recs) >= 1:
        result["recommendations_quality"] = 0.5
    else:
        result["details"]["recommendations"] = f"Too few: {len(recs) if isinstance(recs, list) else 0}"

    # 4. Grade correctness
    grade = parsed.get("grade", "").upper().strip()
    expected_grades = [g.upper() for g in scenario.get("expected_grade", [])]
    if grade in expected_grades:
        result["grade_correct"] = True
    else:
        # Allow ±1 grade tolerance (A matches B, C matches B/D, etc.)
        grade_scale = ["F", "D", "C", "B", "A"]
        grade_idx = grade_scale.index(grade) if grade in grade_scale else -1
        for eg in expected_grades:
            eg_idx = grade_scale.index(eg) if eg in grade_scale else -1
            if grade_idx >= 0 and eg_idx >= 0 and abs(grade_idx - eg_idx) <= 1:
                result["grade_correct"] = True
                break
        if not result["grade_correct"]:
            result["details"]["grade"] = f"Got '{grade}', expected one of {expected_grades}"

    # 5. Overfitting risk correctness
    overfit = parsed.get("overfitting_risk", "").lower().strip()
    expected_overfit = [o.lower() for o in scenario.get("expected_overfit_risk", [])]
    if overfit in expected_overfit:
        result["overfit_correct"] = True
    else:
        result["details"]["overfit"] = f"Got '{overfit}', expected one of {expected_overfit}"

    # 6. Confidence in valid range [0, 1]
    confidence = parsed.get("confidence", -1)
    try:
        conf_val = float(confidence)
        if 0.0 <= conf_val <= 1.0:
            result["confidence_valid"] = True
        else:
            result["details"]["confidence"] = f"Out of range: {conf_val}"
    except (ValueError, TypeError):
        result["details"]["confidence"] = f"Invalid value: {confidence}"

    # Total score (weighted):
    # Field completeness 25%, summary 15%, recs 15%, grade 20%, overfit 15%, confidence 10%
    field_score = result["fields_present"] / result["fields_total"] if result["fields_total"] > 0 else 0
    grade_score = 1.0 if result["grade_correct"] else 0.0
    overfit_score = 1.0 if result["overfit_correct"] else 0.0
    conf_score = 1.0 if result["confidence_valid"] else 0.0

    result["total_score"] = round(
        0.25 * field_score
        + 0.15 * result["summary_quality"]
        + 0.15 * result["recommendations_quality"]
        + 0.20 * grade_score
        + 0.15 * overfit_score
        + 0.10 * conf_score,
        3,
    )

    return result


# =============================================================================
# Client factory (reuse from comprehension test)
# =============================================================================

_client_cache: dict[str, OpenAICompatibleClient | None] = {}


def _make_client(provider: str) -> OpenAICompatibleClient | None:
    """Create LLM client from env vars. Returns None if key missing."""
    key_map = {
        "deepseek": ("DEEPSEEK_API_KEY", LLMProvider.DEEPSEEK, "deepseek-chat"),
        "qwen": ("QWEN_API_KEY", LLMProvider.QWEN, "qwen-plus"),
        "perplexity": ("PERPLEXITY_API_KEY", LLMProvider.PERPLEXITY, "sonar-pro"),
    }
    env_key, llm_provider, model = key_map[provider]
    api_key = os.environ.get(env_key)
    if not api_key or "YOUR_" in api_key:
        return None

    timeout = 120 if provider == "perplexity" else 60

    config = LLMConfig(
        provider=llm_provider,
        api_key=api_key,
        model=model,
        temperature=0.1,
        max_tokens=2048,
        timeout_seconds=timeout,
        max_retries=3 if provider == "perplexity" else 2,
        retry_delay_seconds=2.0 if provider == "perplexity" else 1.0,
    )
    if provider == "deepseek":
        return DeepSeekClient(config)
    elif provider == "qwen":
        return QwenClient(config)
    elif provider == "perplexity":
        return PerplexityClient(config)
    return None


def _get_cached_client(provider: str):
    """Get or create cached client for provider."""
    if provider not in _client_cache:
        _client_cache[provider] = _make_client(provider)
    return _client_cache[provider]


async def _ask_agent_analysis(
    client: OpenAICompatibleClient,
    scenario_name: str,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Send backtest metrics to agent using ANALYSIS_PROMPT and parse response."""
    metrics = scenario["metrics"]

    # Build prompt using the AIBacktestAnalyzer.ANALYSIS_PROMPT
    prompt = AIBacktestAnalyzer.ANALYSIS_PROMPT.format(
        strategy_name=scenario["strategy_name"],
        symbol=scenario["symbol"],
        timeframe=scenario["timeframe"],
        period=scenario["period"],
        net_pnl=metrics["net_pnl"],
        total_return_pct=metrics["total_return_pct"],
        sharpe_ratio=metrics["sharpe_ratio"],
        sortino_ratio=metrics["sortino_ratio"],
        max_drawdown_pct=metrics["max_drawdown_pct"],
        win_rate=metrics["win_rate"],
        profit_factor=metrics["profit_factor"],
        total_trades=metrics["total_trades"],
        calmar_ratio=metrics["calmar_ratio"],
        avg_win=metrics["avg_win"],
        avg_loss=metrics["avg_loss"],
        max_consecutive_wins=metrics["max_consecutive_wins"],
        max_consecutive_losses=metrics["max_consecutive_losses"],
        recovery_factor=metrics["recovery_factor"],
        payoff_ratio=metrics["payoff_ratio"],
        avg_trade_duration=metrics["avg_trade_duration"],
        best_trade=metrics["best_trade"],
        worst_trade=metrics["worst_trade"],
        avg_trade_pnl=metrics["avg_trade_pnl"],
    )

    messages = [
        LLMMessage(
            role="system",
            content="You are an expert quantitative analyst. Return ONLY valid JSON, no markdown.",
        ),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        if client.session is not None and not client.session.closed:
            await client.session.close()
        client.session = None

        response: LLMResponse = await client.chat(messages)

        if client.session is not None and not client.session.closed:
            await client.session.close()
        client.session = None

        parsed = _parse_llm_json(response.content)
        return {
            "raw": response.content,
            "parsed": parsed,
            "tokens": response.total_tokens,
            "latency_ms": response.latency_ms,
            "cost": response.estimated_cost,
        }
    except Exception as e:
        logger.error(f"API call failed for {client.PROVIDER.value}/{scenario_name}: {type(e).__name__}: {e}")
        try:
            if client.session is not None and not client.session.closed:
                await client.session.close()
        except Exception:
            pass
        client.session = None

        is_network_error = isinstance(
            e, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError, aiohttp.ClientError)
        )
        return {
            "raw": str(e),
            "parsed": None,
            "tokens": 0,
            "latency_ms": 0,
            "cost": 0,
            "network_error": is_network_error,
            "error_type": type(e).__name__,
        }


# =============================================================================
# Pytest fixtures
# =============================================================================

pytestmark = [
    pytest.mark.api_live,
    pytest.mark.timeout(300),
]


@pytest.fixture
def deepseek_client():
    client = _get_cached_client("deepseek")
    if client is None:
        pytest.skip("DEEPSEEK_API_KEY not set")
    return client


@pytest.fixture
def qwen_client():
    client = _get_cached_client("qwen")
    if client is None:
        pytest.skip("QWEN_API_KEY not set")
    return client


@pytest.fixture
def perplexity_client():
    client = _get_cached_client("perplexity")
    if client is None:
        pytest.skip("PERPLEXITY_API_KEY not set")
    return client


# =============================================================================
# Results collector
# =============================================================================

_all_results: dict[str, dict[str, dict[str, Any]]] = {}


def _record_result(agent: str, scenario: str, score: dict[str, Any]) -> None:
    if agent not in _all_results:
        _all_results[agent] = {}
    _all_results[agent][scenario] = score


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestDeepSeekBacktestAnalysis:
    """Test DeepSeek's backtest analysis quality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
    async def test_analysis_quality(self, deepseek_client, scenario_name: str):
        """DeepSeek should produce complete, accurate backtest analysis."""
        scenario = SCENARIOS[scenario_name]
        result = await _ask_agent_analysis(deepseek_client, scenario_name, scenario)

        assert result["parsed"] is not None, (
            f"DeepSeek returned invalid JSON for {scenario_name}. Raw: {result['raw'][:500]}"
        )

        score = _score_analysis(result["parsed"], scenario, scenario_name)
        score["tokens"] = result["tokens"]
        score["latency_ms"] = result["latency_ms"]
        score["cost"] = result["cost"]
        _record_result("deepseek", scenario_name, score)

        logger.info(
            f"🔵 DeepSeek/{scenario_name}: score={score['total_score']:.0%} "
            f"fields={score['fields_present']}/{score['fields_total']} "
            f"grade={'✅' if score['grade_correct'] else '❌'} "
            f"overfit={'✅' if score['overfit_correct'] else '❌'} "
            f"tokens={score['tokens']} latency={score['latency_ms']:.0f}ms"
        )

        assert score["total_score"] >= 0.6, (
            f"DeepSeek analysis quality too low for {scenario_name}: "
            f"{score['total_score']:.0%}\n"
            f"Details: {json.dumps(score['details'], indent=2)}"
        )


class TestQwenBacktestAnalysis:
    """Test Qwen's backtest analysis quality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
    async def test_analysis_quality(self, qwen_client, scenario_name: str):
        """Qwen should produce complete, accurate backtest analysis."""
        scenario = SCENARIOS[scenario_name]
        result = await _ask_agent_analysis(qwen_client, scenario_name, scenario)

        assert result["parsed"] is not None, (
            f"Qwen returned invalid JSON for {scenario_name}. Raw: {result['raw'][:500]}"
        )

        score = _score_analysis(result["parsed"], scenario, scenario_name)
        score["tokens"] = result["tokens"]
        score["latency_ms"] = result["latency_ms"]
        score["cost"] = result["cost"]
        _record_result("qwen", scenario_name, score)

        logger.info(
            f"🟢 Qwen/{scenario_name}: score={score['total_score']:.0%} "
            f"fields={score['fields_present']}/{score['fields_total']} "
            f"grade={'✅' if score['grade_correct'] else '❌'} "
            f"overfit={'✅' if score['overfit_correct'] else '❌'} "
            f"tokens={score['tokens']} latency={score['latency_ms']:.0f}ms"
        )

        assert score["total_score"] >= 0.6, (
            f"Qwen analysis quality too low for {scenario_name}: "
            f"{score['total_score']:.0%}\n"
            f"Details: {json.dumps(score['details'], indent=2)}"
        )


class TestPerplexityBacktestAnalysis:
    """Test Perplexity's backtest analysis quality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
    async def test_analysis_quality(self, perplexity_client, scenario_name: str):
        """Perplexity should produce complete, accurate backtest analysis."""
        scenario = SCENARIOS[scenario_name]
        result = await _ask_agent_analysis(perplexity_client, scenario_name, scenario)

        if result.get("network_error"):
            pytest.skip(f"Perplexity API unreachable for {scenario_name}: {result.get('error_type', 'unknown')}")

        assert result["parsed"] is not None, (
            f"Perplexity returned invalid JSON for {scenario_name}. Raw: {result['raw'][:500]}"
        )

        score = _score_analysis(result["parsed"], scenario, scenario_name)
        score["tokens"] = result["tokens"]
        score["latency_ms"] = result["latency_ms"]
        score["cost"] = result["cost"]
        _record_result("perplexity", scenario_name, score)

        logger.info(
            f"🟣 Perplexity/{scenario_name}: score={score['total_score']:.0%} "
            f"fields={score['fields_present']}/{score['fields_total']} "
            f"grade={'✅' if score['grade_correct'] else '❌'} "
            f"overfit={'✅' if score['overfit_correct'] else '❌'} "
            f"tokens={score['tokens']} latency={score['latency_ms']:.0f}ms"
        )

        assert score["total_score"] >= 0.6, (
            f"Perplexity analysis quality too low for {scenario_name}: "
            f"{score['total_score']:.0%}\n"
            f"Details: {json.dumps(score['details'], indent=2)}"
        )


# =============================================================================
# PARSER UNIT TEST — verify _parse_analysis() works correctly
# =============================================================================


class TestParseAnalysis:
    """Unit tests for AIBacktestAnalyzer._parse_analysis() method."""

    def setup_method(self):
        self.analyzer = AIBacktestAnalyzer()

    def test_parse_valid_json(self):
        """Parse a valid JSON response."""
        response = json.dumps(
            {
                "summary": "Strategy shows strong performance",
                "risk_assessment": "Moderate risk with controlled drawdown",
                "strengths": ["High Sharpe ratio", "Good win rate"],
                "weaknesses": ["Limited trades"],
                "recommendations": ["Increase sample size", "Test on other pairs"],
                "overfitting_risk": "low",
                "overfitting_reason": "Sufficient trade count",
                "market_regime": "trending",
                "market_regime_detail": "Works best in trending markets",
                "grade": "B",
                "confidence": 0.85,
            }
        )
        result = self.analyzer._parse_analysis(response)
        assert result["summary"] == "Strategy shows strong performance"
        assert result["grade"] == "B"
        assert result["confidence"] == 0.85
        assert len(result["strengths"]) == 2
        assert result["overfitting_risk"] == "low"

    def test_parse_json_with_markdown_fences(self):
        """Parse JSON wrapped in markdown code fences."""
        response = '```json\n{"summary": "Good strategy", "grade": "A", "confidence": 0.9}\n```'
        result = self.analyzer._parse_analysis(response)
        assert result["summary"] == "Good strategy"
        assert result["grade"] == "A"

    def test_parse_json_with_extra_text(self):
        """Parse JSON preceded by explanation text."""
        response = (
            "Here is my analysis:\n\n"
            '{"summary": "Average results", "grade": "C", "confidence": 0.7, '
            '"recommendations": ["Improve entries"]}'
        )
        result = self.analyzer._parse_analysis(response)
        assert result["summary"] == "Average results"
        assert result["grade"] == "C"

    def test_parse_empty_response(self):
        """Empty response should return defaults."""
        result = self.analyzer._parse_analysis("")
        assert result["summary"] == ""
        assert result["grade"] == "C"
        assert result["confidence"] == 0.0

    def test_parse_legacy_text_format(self):
        """Parse legacy text-based format (fallback)."""
        response = (
            "SUMMARY: Strategy performs adequately\n"
            "RISK_ASSESSMENT: Medium risk level\n"
            "RECOMMENDATIONS: Increase period, Reduce leverage, Test more\n"
            "OVERFITTING_RISK: medium\n"
            "MARKET_REGIME: trending\n"
        )
        result = self.analyzer._parse_analysis(response)
        assert result["summary"] == "Strategy performs adequately"
        assert result["risk_assessment"] == "Medium risk level"
        assert result["overfitting_risk"] == "medium"
        assert len(result["recommendations"]) == 3
        assert result["confidence"] == 0.7  # Lower confidence for text parsing


# =============================================================================
# MERGE UNIT TEST — verify _merge_analyses() works correctly
# =============================================================================


class TestMergeAnalyses:
    """Unit tests for AIBacktestAnalyzer._merge_analyses() method."""

    def setup_method(self):
        self.analyzer = AIBacktestAnalyzer()

    def test_merge_empty_list(self):
        """Empty list should return default."""
        result = self.analyzer._merge_analyses([])
        assert "not available" in result["summary"].lower() or "no agents" in result["summary"].lower()
        assert result["confidence"] == 0.0

    def test_merge_single_analysis(self):
        """Single analysis should be returned as-is."""
        analysis = {
            "summary": "Good",
            "grade": "B",
            "confidence": 0.8,
            "_agent": "deepseek",
        }
        result = self.analyzer._merge_analyses([analysis])
        assert result["summary"] == "Good"

    def test_merge_multiple_analyses(self):
        """Multiple analyses should be merged with consensus."""
        analyses = [
            {
                "summary": "Excellent performance",
                "risk_assessment": "Low risk",
                "strengths": ["High Sharpe"],
                "weaknesses": ["Few trades"],
                "recommendations": ["Add more data"],
                "overfitting_risk": "low",
                "overfitting_reason": "Sufficient trades",
                "market_regime": "trending",
                "market_regime_detail": "Best in uptrend",
                "grade": "A",
                "confidence": 0.9,
                "_agent": "deepseek",
            },
            {
                "summary": "Strong strategy",
                "risk_assessment": "Controlled risk",
                "strengths": ["Good win rate"],
                "weaknesses": ["High drawdown"],
                "recommendations": ["Reduce position size", "Add more data"],
                "overfitting_risk": "low",
                "overfitting_reason": "Good sample size",
                "market_regime": "trending",
                "market_regime_detail": "Works well in trending markets with moderate volatility",
                "grade": "A",
                "confidence": 0.85,
                "_agent": "qwen",
            },
            {
                "summary": "Solid results",
                "risk_assessment": "Moderate",
                "strengths": ["High Sharpe", "Consistent"],
                "weaknesses": [],
                "recommendations": ["Test on other symbols"],
                "overfitting_risk": "medium",
                "overfitting_reason": "",
                "market_regime": "trending",
                "market_regime_detail": "",
                "grade": "B",
                "confidence": 0.8,
                "_agent": "perplexity",
            },
        ]
        result = self.analyzer._merge_analyses(analyses)

        # Check all agents mentioned in summary
        assert "DEEPSEEK" in result["summary"]
        assert "QWEN" in result["summary"]
        assert "PERPLEXITY" in result["summary"]

        # Check recommendations deduplicated
        assert len(result["recommendations"]) <= 5
        rec_lower = [r.lower() for r in result["recommendations"]]
        # "Add more data" should appear only once
        assert rec_lower.count("add more data") <= 1

        # Majority vote: 2 out of 3 say "low" overfitting
        assert result["overfitting_risk"] == "low"

        # Majority vote: all say "trending"
        assert result["market_regime"] == "trending"

        # Grade: majority vote (2 x A, 1 x B → A)
        assert result["grade"] == "A"

        # Overfitting reason: longest non-empty
        assert len(result["overfitting_reason"]) > 0

        # Market regime detail: longest non-empty
        assert "trending" in result["market_regime_detail"].lower()

        # Average confidence
        assert 0.8 <= result["confidence"] <= 0.9

        # Agents list
        assert "agents_used" in result
        assert len(result["agents_used"]) == 3


# =============================================================================
# SUMMARY REPORT
# =============================================================================


class TestBacktestAnalysisSummary:
    """Print summary comparison after all agent tests complete."""

    def test_print_summary(self):
        """Print comparative summary of backtest analysis quality."""
        if not _all_results:
            pytest.skip("No API results collected")

        print("\n")
        print("=" * 90)
        print("  SUMMARY: AI BACKTEST ANALYSIS QUALITY (Real API)")
        print("=" * 90)

        agents = sorted(_all_results.keys())
        scenarios = sorted({s for agent_results in _all_results.values() for s in agent_results})

        # Header
        header = f"{'Scenario':<25}"
        for agent in agents:
            header += f" | {agent:>12}"
        print(header)
        print("-" * len(header))

        # Per-scenario scores
        agent_totals: dict[str, list[float]] = {a: [] for a in agents}
        for scenario in scenarios:
            row = f"{scenario:<25}"
            for agent in agents:
                if agent in _all_results and scenario in _all_results[agent]:
                    s = _all_results[agent][scenario]["total_score"]
                    agent_totals[agent].append(s)
                    mark = "[OK]" if s >= 0.8 else ("[~~]" if s >= 0.6 else "[XX]")
                    row += f" | {s:>6.0%} {mark}"
                else:
                    row += f" | {'---':>10}"
            print(row)

        # Average
        print("-" * len(header))
        avg_row = f"{'AVERAGE SCORE':<25}"
        for agent in agents:
            scores = agent_totals[agent]
            if scores:
                avg = sum(scores) / len(scores)
                avg_row += f" | {avg:>6.0%}     "
            else:
                avg_row += f" | {'---':>10}"
        print(avg_row)

        # Cost summary
        print()
        print("  COST:")
        for agent in agents:
            if agent in _all_results:
                total_tokens = sum(r.get("tokens", 0) for r in _all_results[agent].values())
                total_cost = sum(r.get("cost", 0) for r in _all_results[agent].values())
                avg_latency = sum(r.get("latency_ms", 0) for r in _all_results[agent].values()) / max(
                    len(_all_results[agent]), 1
                )
                print(f"  {agent:<12}: {total_tokens:>6} tokens, ${total_cost:.4f}, avg latency {avg_latency:.0f}ms")

        print("=" * 90)

    def test_all_agents_above_threshold(self):
        """All agents must achieve >= 70% average quality score."""
        if not _all_results:
            pytest.skip("No API results collected")

        for agent, scenarios in _all_results.items():
            scores = [s["total_score"] for s in scenarios.values()]
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            assert avg >= 0.7, (
                f"Агент {agent}: средний балл {avg:.0%} ниже порога 70%. Качество AI-анализа бэктестов недостаточное!"
            )
