"""
Tests for AI Strategy Pipeline components.

Tests cover:
- ResponseParser (JSON extraction, parsing, validation)
- PromptEngineer (prompt creation)
- MarketContextBuilder (market regime detection)
- StrategyController (pipeline orchestration)
- BacktestBridge (strategy → engine mapping)
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from backend.agents.prompts.context_builder import MarketContextBuilder
from backend.agents.prompts.prompt_engineer import PromptEngineer
from backend.agents.prompts.response_parser import (
    ResponseParser,
    StrategyDefinition,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate sample OHLCV data for testing (200 candles)."""
    np.random.seed(42)
    n = 200
    base = 50000.0
    dates = pd.date_range("2025-01-01", periods=n, freq="15min")

    close = base + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    op = close + np.random.randn(n) * 20
    volume = np.abs(np.random.randn(n) * 1000) + 100

    return pd.DataFrame(
        {
            "open": op,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


@pytest.fixture
def valid_llm_response() -> str:
    """Simulated valid LLM response with JSON strategy."""
    strategy = {
        "strategy_name": "RSI Mean Reversion",
        "description": "Buy oversold, sell overbought",
        "signals": [
            {
                "id": "signal_1",
                "type": "RSI",
                "params": {"period": 14, "overbought": 70, "oversold": 30},
                "weight": 1.0,
                "condition": "RSI crosses below 30 for long, above 70 for short",
            }
        ],
        "filters": [
            {
                "id": "filter_1",
                "type": "Volume",
                "params": {"min_volume_ratio": 1.5},
                "condition": "Volume > 1.5x average",
            }
        ],
        "entry_conditions": {
            "long": "RSI < 30 AND Volume > average",
            "short": "RSI > 70 AND Volume > average",
            "logic": "AND",
        },
        "exit_conditions": {
            "take_profit": {"type": "fixed_pct", "value": 3.0, "description": "3% TP"},
            "stop_loss": {"type": "fixed_pct", "value": 2.0, "description": "2% SL"},
        },
    }
    return f"Here is the strategy:\n\n```json\n{json.dumps(strategy, indent=2)}\n```"


@pytest.fixture
def parser() -> ResponseParser:
    return ResponseParser()


@pytest.fixture
def prompt_engineer() -> PromptEngineer:
    return PromptEngineer()


@pytest.fixture
def context_builder() -> MarketContextBuilder:
    return MarketContextBuilder()


# =============================================================================
# RESPONSE PARSER TESTS
# =============================================================================


class TestResponseParser:
    """Tests for ResponseParser."""

    def test_parse_strategy_valid_json(self, parser, valid_llm_response):
        """Test parsing a valid LLM response."""
        result = parser.parse_strategy(valid_llm_response, agent_name="deepseek")

        assert result is not None
        assert result.strategy_name == "RSI Mean Reversion"
        assert len(result.signals) == 1
        assert result.signals[0].type == "RSI"
        assert result.signals[0].params["period"] == 14
        assert result.agent_metadata is not None
        assert result.agent_metadata.agent_name == "deepseek"

    def test_parse_strategy_empty_input(self, parser):
        """Test parsing empty string returns None."""
        assert parser.parse_strategy("") is None
        assert parser.parse_strategy("   ") is None

    def test_parse_strategy_no_json(self, parser):
        """Test parsing text without JSON returns None."""
        assert parser.parse_strategy("This has no JSON at all.") is None

    def test_parse_strategy_raw_json(self, parser):
        """Test parsing raw JSON without markdown."""
        raw = json.dumps(
            {
                "strategy_name": "Simple MACD",
                "signals": [{"id": "s1", "type": "MACD", "params": {"fast_period": 12}}],
            }
        )
        result = parser.parse_strategy(raw, agent_name="qwen")

        assert result is not None
        assert result.strategy_name == "Simple MACD"
        assert result.signals[0].type == "MACD"

    def test_parse_strategy_with_trailing_commas(self, parser):
        """Test JSON with trailing commas gets auto-fixed."""
        broken_json = '{"strategy_name": "Test", "signals": [{"id": "s1", "type": "RSI", "params": {},},],}'
        response = f"```json\n{broken_json}\n```"
        result = parser.parse_strategy(response)
        # Should either parse successfully or return None (not crash)
        if result:
            assert result.strategy_name == "Test"

    def test_validate_strategy_valid(self, parser, valid_llm_response):
        """Test validation of a valid strategy."""
        strategy = parser.parse_strategy(valid_llm_response)
        assert strategy is not None

        validation = parser.validate_strategy(strategy)
        assert validation.is_valid
        assert validation.quality_score > 0.5

    def test_validate_strategy_out_of_range_params(self, parser):
        """Test validation catches out-of-range parameters."""
        strategy = StrategyDefinition(
            strategy_name="Bad Params",
            signals=[
                {
                    "id": "s1",
                    "type": "RSI",
                    "params": {"period": 500, "overbought": 110, "oversold": -5},
                    "weight": 1.0,
                }
            ],
        )
        validation = parser.validate_strategy(strategy)
        # Should have warnings about out-of-range params
        assert len(validation.issues) > 0

    def test_extract_json_from_markdown(self, parser):
        """Test JSON extraction from markdown code blocks."""
        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = parser._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_from_raw_braces(self, parser):
        """Test JSON extraction from raw { ... }."""
        text = 'Before text {"strategy_name": "test"} after text'
        result = parser._extract_json(text)
        assert result is not None
        assert "strategy_name" in result

    def test_get_strategy_type_for_engine(self):
        """Test engine type mapping."""
        strategy = StrategyDefinition(
            strategy_name="RSI Test",
            signals=[{"id": "s1", "type": "RSI", "params": {"period": 14}}],
        )
        assert strategy.get_strategy_type_for_engine() == "rsi"

    def test_get_engine_params_rsi(self):
        """Test engine params extraction for RSI."""
        strategy = StrategyDefinition(
            strategy_name="RSI Test",
            signals=[
                {
                    "id": "s1",
                    "type": "RSI",
                    "params": {"period": 21, "overbought": 75, "oversold": 25},
                }
            ],
        )
        params = strategy.get_engine_params()
        assert params["period"] == 21
        assert params["overbought"] == 75
        assert params["oversold"] == 25

    def test_get_engine_params_macd(self):
        """Test engine params extraction for MACD."""
        strategy = StrategyDefinition(
            strategy_name="MACD Test",
            signals=[
                {
                    "id": "s1",
                    "type": "MACD",
                    "params": {"fast_period": 8, "slow_period": 21, "signal_period": 5},
                }
            ],
        )
        params = strategy.get_engine_params()
        assert params["fast_period"] == 8
        assert params["slow_period"] == 21
        assert params["signal_period"] == 5

    def test_signal_type_normalization(self):
        """Test signal type validation normalizes variants."""
        strategy = StrategyDefinition(
            strategy_name="Test",
            signals=[
                {
                    "id": "s1",
                    "type": "ema_crossover",
                    "params": {"fast_period": 9},
                }
            ],
        )
        assert strategy.signals[0].type == "EMA_Crossover"


# =============================================================================
# MARKET CONTEXT BUILDER TESTS
# =============================================================================


class TestMarketContextBuilder:
    """Tests for MarketContextBuilder."""

    def test_build_context_basic(self, context_builder, sample_ohlcv):
        """Test building market context from OHLCV data."""
        ctx = context_builder.build_context("BTCUSDT", "15", sample_ohlcv)

        assert ctx.symbol == "BTCUSDT"
        assert ctx.timeframe == "15"
        assert ctx.current_price > 0
        assert ctx.market_regime in (
            "trending_up",
            "trending_down",
            "ranging",
            "volatile",
        )
        assert ctx.trend_direction in ("up", "down", "sideways", "neutral")

    def test_build_context_has_support_resistance(self, context_builder, sample_ohlcv):
        """Test context has support/resistance levels."""
        ctx = context_builder.build_context("ETHUSDT", "60", sample_ohlcv)

        assert isinstance(ctx.support_levels, list)
        assert isinstance(ctx.resistance_levels, list)

    def test_to_prompt_vars(self, context_builder, sample_ohlcv):
        """Test conversion to prompt template variables."""
        ctx = context_builder.build_context("BTCUSDT", "15", sample_ohlcv)
        prompt_vars = ctx.to_prompt_vars()

        assert "symbol" in prompt_vars
        assert "current_price" in prompt_vars
        assert "market_regime" in prompt_vars
        assert prompt_vars["symbol"] == "BTCUSDT"

    def test_small_dataframe(self, context_builder):
        """Test with very small DataFrame (edge case)."""
        small = pd.DataFrame(
            {
                "open": [100, 101],
                "high": [102, 103],
                "low": [98, 99],
                "close": [101, 102],
                "volume": [1000, 1100],
            }
        )
        ctx = context_builder.build_context("TEST", "15", small)
        # With very small data, context builder returns defaults gracefully
        assert ctx.symbol == "TEST"
        assert ctx.indicators_summary == "Insufficient data"


# =============================================================================
# PROMPT ENGINEER TESTS
# =============================================================================


class TestPromptEngineer:
    """Tests for PromptEngineer."""

    def test_create_strategy_prompt(self, prompt_engineer, context_builder, sample_ohlcv):
        """Test strategy prompt generation."""
        ctx = context_builder.build_context("BTCUSDT", "15", sample_ohlcv)
        platform_config = {"exchange": "Bybit", "commission": 0.0007}

        prompt = prompt_engineer.create_strategy_prompt(
            context=ctx,
            platform_config=platform_config,
            agent_name="deepseek",
        )

        assert "BTCUSDT" in prompt
        assert len(prompt) > 100
        # Prompt should contain strategy-related terms
        assert any(term in prompt.lower() for term in ("strategy", "signal", "trade"))

    def test_get_system_message(self, prompt_engineer):
        """Test system message generation."""
        msg_ds = prompt_engineer.get_system_message("deepseek")
        msg_qw = prompt_engineer.get_system_message("qwen")
        msg_unknown = prompt_engineer.get_system_message("unknown_agent")

        assert len(msg_ds) > 0
        assert len(msg_qw) > 0
        assert len(msg_unknown) > 0

    def test_create_optimization_prompt(self, prompt_engineer):
        """Test optimization prompt generation."""
        prompt = prompt_engineer.create_optimization_prompt(
            strategy_name="RSI Strategy",
            strategy_type="rsi",
            strategy_params={"period": 14},
            backtest_results={
                "sharpe_ratio": 0.5,
                "max_drawdown_pct": 20,
                "win_rate": 0.35,
                "profit_factor": 0.8,
                "total_trades": 50,
            },
        )
        assert "RSI Strategy" in prompt
        assert len(prompt) > 100


# =============================================================================
# BACKTEST BRIDGE TESTS
# =============================================================================


class TestBacktestBridge:
    """Tests for BacktestBridge."""

    def test_strategy_to_config(self):
        """Test converting StrategyDefinition to API config dict."""
        from backend.agents.integration.backtest_bridge import BacktestBridge

        bridge = BacktestBridge()
        strategy = StrategyDefinition(
            strategy_name="Test RSI",
            signals=[
                {
                    "id": "s1",
                    "type": "RSI",
                    "params": {"period": 14, "overbought": 70, "oversold": 30},
                }
            ],
            exit_conditions={
                "take_profit": {"type": "fixed_pct", "value": 3.0},
                "stop_loss": {"type": "fixed_pct", "value": 2.0},
            },
        )

        config = bridge.strategy_to_config(strategy)

        assert config["strategy_type"] == "rsi"
        assert config["strategy_params"]["period"] == 14
        assert config["stop_loss"] == 0.02
        assert config["take_profit"] == 0.03

    def test_extract_stop_loss_default(self):
        """Test default SL when not specified."""
        from backend.agents.integration.backtest_bridge import BacktestBridge

        bridge = BacktestBridge()
        strategy = StrategyDefinition(
            strategy_name="No SL",
            signals=[{"id": "s1", "type": "RSI", "params": {"period": 14}}],
        )
        sl = bridge._extract_stop_loss(strategy)
        assert sl == 0.02  # Default 2%

    def test_extract_take_profit_percentage(self):
        """Test TP extraction with percentage value."""
        from backend.agents.integration.backtest_bridge import BacktestBridge

        bridge = BacktestBridge()
        strategy = StrategyDefinition(
            strategy_name="With TP",
            signals=[{"id": "s1", "type": "RSI", "params": {"period": 14}}],
            exit_conditions={
                "take_profit": {"type": "fixed_pct", "value": 5.0},
            },
        )
        tp = bridge._extract_take_profit(strategy)
        assert tp == 0.05  # 5% converted to fraction

    def test_commission_rate_constant(self):
        """Test commission rate is 0.0007 (TradingView parity)."""
        from backend.agents.integration.backtest_bridge import BacktestBridge

        bridge = BacktestBridge()
        assert bridge.COMMISSION_RATE == 0.0007


# =============================================================================
# STRATEGY CONTROLLER TESTS
# =============================================================================


class TestStrategyController:
    """Tests for StrategyController (no LLM calls)."""

    def test_score_proposal_basic(self):
        """Test proposal scoring heuristic."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        strategy = StrategyDefinition(
            strategy_name="Good Strategy",
            signals=[
                {"id": "s1", "type": "RSI", "params": {"period": 14}},
                {"id": "s2", "type": "EMA_Crossover", "params": {"fast_period": 9}},
            ],
            exit_conditions={
                "take_profit": {"type": "fixed_pct", "value": 3.0},
                "stop_loss": {"type": "fixed_pct", "value": 2.0},
            },
            filters=[{"id": "f1", "type": "Volume", "params": {}}],
        )

        score = controller._score_proposal(strategy)
        assert score > 5.0  # Should be above baseline
        assert score <= 10.0

    def test_score_proposal_minimal(self):
        """Test scoring a minimal strategy."""
        from backend.agents.strategy_controller import StrategyController

        controller = StrategyController()

        strategy = StrategyDefinition(
            strategy_name="Minimal",
            signals=[{"id": "s1", "type": "RSI", "params": {"period": 14}}],
        )

        score = controller._score_proposal(strategy)
        assert score >= 4.0  # Base + 1 signal bonus
        assert score <= 10.0
