"""
Tests for AI Backtest Integration module.

Covers:
- AIBacktestResult dataclass and serialization
- AIOptimizationResult dataclass and serialization
- AIBacktestAnalyzer: analyze_backtest, LLM fallback, response parsing
- AIOptimizationAnalyzer: analyze_optimization, response parsing
- Global singleton accessors
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.integration.ai_backtest_integration import (
    AIBacktestAnalyzer,
    AIBacktestResult,
    AIOptimizationAnalyzer,
    AIOptimizationResult,
    get_backtest_analyzer,
    get_optimization_analyzer,
)

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_metrics():
    """Standard backtest metrics"""
    return {
        "net_pnl": 15000.0,
        "total_return_pct": 150.0,
        "sharpe_ratio": 1.8,
        "max_drawdown_pct": 12.5,
        "win_rate": 0.58,
        "profit_factor": 1.9,
        "total_trades": 145,
    }


@pytest.fixture
def sample_backtest_result():
    """Pre-built AIBacktestResult"""
    return AIBacktestResult(
        net_pnl=15000.0,
        total_return_pct=150.0,
        sharpe_ratio=1.8,
        max_drawdown_pct=12.5,
        win_rate=0.58,
        profit_factor=1.9,
        total_trades=145,
        ai_summary="Strategy performs well with consistent returns.",
        ai_risk_assessment="Moderate risk with acceptable drawdown.",
        ai_recommendations=["Add trailing stop", "Reduce position size"],
        ai_confidence=0.85,
        overfitting_risk="low",
        market_regime_fit="trending",
        strategy_name="Momentum RSI",
        symbol="BTCUSDT",
        timeframe="1h",
        backtest_period="2025-01-01 to 2025-06-01",
    )


@pytest.fixture
def sample_optimization_result():
    """Pre-built AIOptimizationResult"""
    return AIOptimizationResult(
        best_params={"rsi_period": 14, "ma_fast": 9, "ma_slow": 21},
        best_sharpe=2.1,
        best_return=180.0,
        total_trials=100,
        convergence_score=0.92,
        ai_parameter_analysis="Parameters are reasonable for trending markets.",
        ai_robustness_assessment="Results appear robust with good convergence.",
        ai_confidence=0.8,
        overfitting_warning=None,
        suggested_adjustments=["Widen RSI period range", "Test higher timeframes"],
    )


@pytest.fixture
def analyzer():
    """AIBacktestAnalyzer instance"""
    return AIBacktestAnalyzer()


@pytest.fixture
def opt_analyzer():
    """AIOptimizationAnalyzer instance"""
    return AIOptimizationAnalyzer()


@pytest.fixture
def mock_llm_response():
    """Mock successful LLM analysis response"""
    return (
        "SUMMARY: Strategy shows strong momentum characteristics with good risk-adjusted returns.\n"
        "RISK_ASSESSMENT: Max drawdown of 12.5% is within acceptable limits. Sharpe of 1.8 is good.\n"
        "RECOMMENDATIONS: Add trailing stop, Reduce position size in volatile periods, Increase holding time\n"
        "OVERFITTING_RISK: low - sufficient number of trades and reasonable parameters\n"
        "MARKET_REGIME: trending markets with moderate volatility"
    )


@pytest.fixture
def mock_optimization_llm_response():
    """Mock successful optimization LLM response"""
    return (
        "PARAMETER_ANALYSIS: RSI period of 14 is a standard choice. MA crossover parameters look reasonable.\n"
        "ROBUSTNESS: With 100 trials, convergence at 0.92 suggests stable parameter region.\n"
        "OVERFITTING_WARNING: None detected\n"
        "ADJUSTMENTS: Consider widening RSI range, Test on different symbols, Add volatility filter"
    )


# ═══════════════════════════════════════════════════════════════════
# AIBacktestResult
# ═══════════════════════════════════════════════════════════════════


class TestAIBacktestResult:
    """Tests for AIBacktestResult dataclass"""

    def test_creation(self, sample_backtest_result):
        """Test creating AIBacktestResult with all fields"""
        r = sample_backtest_result
        assert r.net_pnl == 15000.0
        assert r.sharpe_ratio == 1.8
        assert r.ai_summary == "Strategy performs well with consistent returns."
        assert r.overfitting_risk == "low"
        assert r.strategy_name == "Momentum RSI"

    def test_to_dict_structure(self, sample_backtest_result):
        """Test to_dict produces correct structure"""
        d = sample_backtest_result.to_dict()

        assert "metrics" in d
        assert "ai_analysis" in d
        assert "metadata" in d

        assert d["metrics"]["net_pnl"] == 15000.0
        assert d["metrics"]["sharpe_ratio"] == 1.8
        assert d["metrics"]["win_rate"] == 0.58

        assert d["ai_analysis"]["summary"] == "Strategy performs well with consistent returns."
        assert len(d["ai_analysis"]["recommendations"]) == 2

        assert d["metadata"]["strategy_name"] == "Momentum RSI"
        assert d["metadata"]["symbol"] == "BTCUSDT"

    def test_default_timestamp(self):
        """Test that analysis_timestamp defaults to now"""
        r = AIBacktestResult(
            net_pnl=0,
            total_return_pct=0,
            sharpe_ratio=0,
            max_drawdown_pct=0,
            win_rate=0,
            profit_factor=0,
            total_trades=0,
            ai_summary="",
            ai_risk_assessment="",
            ai_recommendations=[],
            ai_confidence=0,
            overfitting_risk="unknown",
            market_regime_fit="unknown",
            strategy_name="test",
            symbol="TEST",
            timeframe="1h",
            backtest_period="",
        )
        assert r.analysis_timestamp is not None
        assert r.analysis_timestamp.tzinfo is not None


# ═══════════════════════════════════════════════════════════════════
# AIOptimizationResult
# ═══════════════════════════════════════════════════════════════════


class TestAIOptimizationResult:
    """Tests for AIOptimizationResult dataclass"""

    def test_creation(self, sample_optimization_result):
        """Test creating AIOptimizationResult"""
        r = sample_optimization_result
        assert r.best_sharpe == 2.1
        assert r.total_trials == 100
        assert r.overfitting_warning is None
        assert len(r.suggested_adjustments) == 2

    def test_to_dict_structure(self, sample_optimization_result):
        """Test to_dict structure"""
        d = sample_optimization_result.to_dict()

        assert "optimization" in d
        assert "ai_analysis" in d

        assert d["optimization"]["best_params"]["rsi_period"] == 14
        assert d["optimization"]["best_sharpe"] == 2.1
        assert d["optimization"]["total_trials"] == 100

        assert d["ai_analysis"]["confidence"] == 0.8
        assert d["ai_analysis"]["overfitting_warning"] is None


# ═══════════════════════════════════════════════════════════════════
# AIBacktestAnalyzer — Response Parsing
# ═══════════════════════════════════════════════════════════════════


class TestAIBacktestAnalyzerParsing:
    """Tests for AIBacktestAnalyzer response parsing"""

    def test_parse_complete_response(self, analyzer, mock_llm_response):
        """Test parsing a complete well-formed LLM response"""
        result = analyzer._parse_analysis(mock_llm_response)

        assert "momentum" in result["summary"].lower() or "strong" in result["summary"].lower()
        assert len(result["risk_assessment"]) > 0
        assert len(result["recommendations"]) >= 2
        assert result["overfitting_risk"] == "low"
        assert len(result["market_regime"]) > 0

    def test_parse_empty_response(self, analyzer):
        """Test parsing empty response"""
        result = analyzer._parse_analysis("")

        assert result["summary"] == ""
        assert result["risk_assessment"] == ""
        assert result["recommendations"] == []
        assert result["overfitting_risk"] == "unknown"
        assert result["market_regime"] == "unknown"

    def test_parse_high_overfitting_risk(self, analyzer):
        """Test parsing response with high overfitting risk"""
        response = "OVERFITTING_RISK: high - too many parameters for small dataset"
        result = analyzer._parse_analysis(response)
        assert result["overfitting_risk"] == "high"

    def test_parse_medium_overfitting_risk(self, analyzer):
        """Test parsing response with medium overfitting risk"""
        response = "OVERFITTING_RISK: medium - some parameters may be overfit"
        result = analyzer._parse_analysis(response)
        assert result["overfitting_risk"] == "medium"

    def test_parse_partial_response(self, analyzer):
        """Test parsing response with only some fields"""
        response = "SUMMARY: Good strategy overall.\nOVERFITTING_RISK: low"
        result = analyzer._parse_analysis(response)

        assert result["summary"] == "Good strategy overall."
        assert result["overfitting_risk"] == "low"
        assert result["recommendations"] == []


# ═══════════════════════════════════════════════════════════════════
# AIBacktestAnalyzer — analyze_backtest
# ═══════════════════════════════════════════════════════════════════


class TestAIBacktestAnalyzerAnalyze:
    """Tests for AIBacktestAnalyzer.analyze_backtest"""

    @pytest.mark.asyncio
    async def test_analyze_backtest_with_mock_llm(self, analyzer, sample_metrics, mock_llm_response):
        """Test full analyze_backtest flow with mocked LLM (3 agents)"""
        with patch.object(analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_llm_response

            result = await analyzer.analyze_backtest(
                metrics=sample_metrics,
                strategy_name="Momentum RSI",
                symbol="BTCUSDT",
                timeframe="1h",
                period="2025-01-01 to 2025-06-01",
            )

        assert isinstance(result, AIBacktestResult)
        assert result.net_pnl == 15000.0
        assert result.sharpe_ratio == 1.8
        assert result.strategy_name == "Momentum RSI"
        assert len(result.ai_summary) > 0
        assert result.overfitting_risk == "low"
        # Default agents: deepseek, qwen, perplexity → 3 calls
        assert mock_call.call_count == 3

    @pytest.mark.asyncio
    async def test_analyze_backtest_llm_failure(self, analyzer, sample_metrics):
        """Test analyze_backtest when LLM call fails for all agents"""
        with patch.object(analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ""  # Empty response simulates failure

            result = await analyzer.analyze_backtest(
                metrics=sample_metrics,
                strategy_name="Failed Strategy",
                symbol="BTCUSDT",
                timeframe="15m",
            )

        assert isinstance(result, AIBacktestResult)
        assert result.ai_confidence == 0.0  # No summary → 0 confidence
        # _merge_analyses([]) returns default summary
        assert isinstance(result.ai_summary, str)
        # All 3 agents called, all returned ""
        assert mock_call.call_count == 3

    @pytest.mark.asyncio
    async def test_analyze_backtest_default_agents(self, analyzer, sample_metrics):
        """Test that default agents are ['deepseek', 'qwen', 'perplexity']"""
        with patch.object(analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "SUMMARY: Test"

            await analyzer.analyze_backtest(
                metrics=sample_metrics,
                strategy_name="Test",
                symbol="BTCUSDT",
                timeframe="1h",
            )

            # Should call all 3 default agents
            assert mock_call.call_count == 3
            called_agents = [call.args[0] for call in mock_call.call_args_list]
            assert "deepseek" in called_agents
            assert "qwen" in called_agents
            assert "perplexity" in called_agents

    @pytest.mark.asyncio
    async def test_analyze_backtest_custom_agents(self, analyzer, sample_metrics):
        """Test analyze with custom agent list"""
        with patch.object(analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "SUMMARY: Qwen analysis"

            await analyzer.analyze_backtest(
                metrics=sample_metrics,
                strategy_name="Test",
                symbol="BTCUSDT",
                timeframe="1h",
                agents=["qwen"],
            )

            call_args = mock_call.call_args
            assert call_args[0][0] == "qwen"

    @pytest.mark.asyncio
    async def test_analyze_backtest_missing_metrics(self, analyzer):
        """Test analyze with partial/missing metrics"""
        with patch.object(analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "SUMMARY: Sparse data"

            result = await analyzer.analyze_backtest(
                metrics={},  # Empty metrics
                strategy_name="Sparse",
                symbol="ETHUSDT",
                timeframe="4h",
            )

        assert result.net_pnl == 0
        assert result.sharpe_ratio == 0
        assert result.total_trades == 0


# ═══════════════════════════════════════════════════════════════════
# AIOptimizationAnalyzer — Response Parsing
# ═══════════════════════════════════════════════════════════════════


class TestAIOptimizationAnalyzerParsing:
    """Tests for AIOptimizationAnalyzer response parsing"""

    def test_parse_complete_response(self, opt_analyzer, mock_optimization_llm_response):
        """Test parsing complete optimization response"""
        result = opt_analyzer._parse_optimization_analysis(mock_optimization_llm_response)

        assert len(result["parameter_analysis"]) > 0
        assert len(result["robustness"]) > 0
        assert result["overfitting_warning"] is None  # "None detected"
        assert len(result["adjustments"]) >= 2

    def test_parse_with_overfitting_warning(self, opt_analyzer):
        """Test parsing with actual overfitting warning"""
        response = "OVERFITTING_WARNING: High sensitivity to parameter changes suggests overfitting"
        result = opt_analyzer._parse_optimization_analysis(response)
        assert result["overfitting_warning"] is not None
        assert "overfitting" in result["overfitting_warning"].lower()

    def test_parse_empty_response(self, opt_analyzer):
        """Test parsing empty response"""
        result = opt_analyzer._parse_optimization_analysis("")

        assert result["parameter_analysis"] == ""
        assert result["robustness"] == ""
        assert result["overfitting_warning"] is None
        assert result["adjustments"] == []


# ═══════════════════════════════════════════════════════════════════
# AIOptimizationAnalyzer — analyze_optimization
# ═══════════════════════════════════════════════════════════════════


class TestAIOptimizationAnalyzerAnalyze:
    """Tests for AIOptimizationAnalyzer.analyze_optimization"""

    @pytest.mark.asyncio
    async def test_analyze_optimization_success(self, opt_analyzer, mock_optimization_llm_response):
        """Test full optimization analysis flow"""
        with patch.object(opt_analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_optimization_llm_response

            result = await opt_analyzer.analyze_optimization(
                best_params={"rsi_period": 14, "ma_fast": 9},
                best_sharpe=2.1,
                best_return=180.0,
                total_trials=100,
                convergence_score=0.92,
                param_ranges={"rsi_period": [5, 30], "ma_fast": [5, 20]},
                strategy_name="Momentum RSI",
                symbol="BTCUSDT",
            )

        assert isinstance(result, AIOptimizationResult)
        assert result.best_sharpe == 2.1
        assert result.total_trials == 100
        assert result.ai_confidence == 0.8
        assert len(result.ai_parameter_analysis) > 0

    @pytest.mark.asyncio
    async def test_analyze_optimization_llm_failure(self, opt_analyzer):
        """Test optimization analysis when LLM fails"""
        with patch.object(opt_analyzer, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ""

            result = await opt_analyzer.analyze_optimization(
                best_params={"p": 1},
                best_sharpe=1.0,
                best_return=50.0,
                total_trials=10,
                convergence_score=0.5,
                param_ranges={},
                strategy_name="Test",
                symbol="TEST",
            )

        assert result.ai_confidence == 0.0
        assert result.ai_parameter_analysis == ""


# ═══════════════════════════════════════════════════════════════════
# Global Singletons
# ═══════════════════════════════════════════════════════════════════


class TestGlobalSingletons:
    """Tests for singleton accessors"""

    def test_get_backtest_analyzer_returns_instance(self):
        """Test get_backtest_analyzer returns AIBacktestAnalyzer"""
        analyzer = get_backtest_analyzer()
        assert isinstance(analyzer, AIBacktestAnalyzer)

    def test_get_backtest_analyzer_is_singleton(self):
        """Test that subsequent calls return same instance"""
        a1 = get_backtest_analyzer()
        a2 = get_backtest_analyzer()
        assert a1 is a2

    def test_get_optimization_analyzer_returns_instance(self):
        """Test get_optimization_analyzer returns AIOptimizationAnalyzer"""
        analyzer = get_optimization_analyzer()
        assert isinstance(analyzer, AIOptimizationAnalyzer)

    def test_get_optimization_analyzer_is_singleton(self):
        """Test that subsequent calls return same instance"""
        a1 = get_optimization_analyzer()
        a2 = get_optimization_analyzer()
        assert a1 is a2


# ═══════════════════════════════════════════════════════════════════
# AIBacktestAnalyzer — _call_llm fallback
# ═══════════════════════════════════════════════════════════════════


class TestAIBacktestAnalyzerLLMCall:
    """Tests for _call_llm method fallback"""

    @pytest.mark.asyncio
    async def test_call_llm_returns_empty_on_import_error(self, analyzer):
        """Test that _call_llm returns empty string when imports fail"""
        with patch(
            "backend.agents.consensus.real_llm_deliberation.get_real_deliberation",
            side_effect=ImportError("No module"),
        ):
            # Reset deliberation to force re-import
            result = await analyzer._call_llm("deepseek", "test prompt")
            # Should gracefully return empty string
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_call_llm_handles_runtime_error(self, analyzer):
        """Test _call_llm handles runtime errors gracefully"""
        mock_delib = MagicMock()
        mock_delib._real_ask = AsyncMock(side_effect=RuntimeError("API down"))

        with patch(
            "backend.agents.consensus.real_llm_deliberation.get_real_deliberation",
            return_value=mock_delib,
        ):
            result = await analyzer._call_llm("deepseek", "test")
            assert result == ""


# ═══════════════════════════════════════════════════════════════════
# AIBacktestAnalyzer — Lazy Deliberation Init
# ═══════════════════════════════════════════════════════════════════


class TestAIBacktestAnalyzerDeliberation:
    """Tests for lazy deliberation initialization"""

    def test_deliberation_initially_none(self):
        """Test that _deliberation starts as None"""
        analyzer = AIBacktestAnalyzer()
        assert analyzer._deliberation is None

    def test_get_deliberation_fallback(self):
        """Test that _get_deliberation falls back to MultiAgentDeliberation"""
        analyzer = AIBacktestAnalyzer()

        with patch(
            "backend.agents.consensus.real_llm_deliberation.get_real_deliberation",
            side_effect=ImportError("not available"),
        ):
            delib = analyzer._get_deliberation()
            assert delib is not None
            # Should be the fallback MultiAgentDeliberation
            assert analyzer._deliberation is not None
