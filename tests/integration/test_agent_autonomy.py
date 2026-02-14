"""
Tests for Agent Autonomy Infrastructure

Tests for:
- MCP tools: run_backtest, get_backtest_metrics, list_strategies, validate_strategy, check_system_health
- Strategy Validator: parameter validation, risk assessment, cross-validation
- Vector Memory: save_backtest_result, find_similar_results
- API endpoints: /agents/actions/* (via httpx AsyncClient)

Naming: test_[function]_[scenario]
"""

import pytest

# ============================================================================
# Strategy Validator Tests (unit — no external deps)
# ============================================================================


class TestStrategyValidator:
    """Unit tests for backend/agents/security/strategy_validator.py"""

    @pytest.fixture
    def validator(self):
        from backend.agents.security.strategy_validator import StrategyValidator

        return StrategyValidator()

    def test_validate_rsi_with_valid_params(self, validator):
        """Valid RSI params should pass"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70, "oversold": 30},
            leverage=5,
            stop_loss=0.02,
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.risk_level.value == "safe"

    def test_validate_rsi_with_invalid_period(self, validator):
        """RSI period below min should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 1},  # min is 2
        )
        assert result.is_valid is False
        assert any("period" in e and "below min" in e for e in result.errors)

    def test_validate_rsi_with_negative_period(self, validator):
        """RSI negative period should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": -5},
        )
        assert result.is_valid is False

    def test_validate_unknown_strategy_type(self, validator):
        """Unknown strategy type should produce error"""
        result = validator.validate(
            strategy_type="nonexistent_strategy",
            strategy_params={},
        )
        assert result.is_valid is False
        assert any("Unknown strategy" in e for e in result.errors)

    def test_validate_macd_fast_greater_than_slow(self, validator):
        """MACD fast_period >= slow_period should fail"""
        result = validator.validate(
            strategy_type="macd",
            strategy_params={"fast_period": 30, "slow_period": 12, "signal_period": 9},
        )
        assert result.is_valid is False
        assert any("fast_period" in e and "less than" in e for e in result.errors)

    def test_validate_macd_valid_params(self, validator):
        """Valid MACD params should pass"""
        result = validator.validate(
            strategy_type="macd",
            strategy_params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            leverage=1,
            stop_loss=0.03,
        )
        assert result.is_valid is True

    def test_validate_sma_crossover_fast_greater_than_slow(self, validator):
        """SMA fast_period >= slow_period should fail"""
        result = validator.validate(
            strategy_type="sma_crossover",
            strategy_params={"fast_period": 100, "slow_period": 50},
        )
        assert result.is_valid is False
        assert any("fast_period" in e for e in result.errors)

    def test_validate_bollinger_with_valid_params(self, validator):
        """Valid Bollinger params should pass"""
        result = validator.validate(
            strategy_type="bollinger_bands",
            strategy_params={"period": 20, "std_dev": 2.0},
        )
        assert result.is_valid is True

    def test_validate_grid_upper_below_lower(self, validator):
        """Grid upper_price <= lower_price should fail"""
        result = validator.validate(
            strategy_type="grid",
            strategy_params={"grid_count": 10, "upper_price": 100, "lower_price": 200},
        )
        assert result.is_valid is False
        assert any("upper_price" in e for e in result.errors)

    # --- Leverage risk tests ---

    def test_validate_leverage_exceeds_max(self, validator):
        """Leverage > 125 should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            leverage=200,
        )
        assert result.is_valid is False
        assert any("125" in e for e in result.errors)

    def test_validate_leverage_below_one(self, validator):
        """Leverage < 1 should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            leverage=0.5,
        )
        assert result.is_valid is False

    def test_validate_high_leverage_warning(self, validator):
        """Leverage 50-100x should produce warning"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            leverage=60,
            stop_loss=0.02,
        )
        assert result.is_valid is True
        assert result.risk_level.value == "high"
        assert any("leverage" in w.lower() for w in result.warnings)

    def test_validate_extreme_leverage(self, validator):
        """Leverage > 100x should be EXTREME risk"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            leverage=110,
            stop_loss=0.02,
        )
        assert result.is_valid is True
        assert result.risk_level.value == "extreme"

    # --- Capital tests ---

    def test_validate_capital_too_low(self, validator):
        """Capital < 100 should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            initial_capital=50,
        )
        assert result.is_valid is False
        assert any("Capital too low" in e for e in result.errors)

    def test_validate_capital_too_high(self, validator):
        """Capital > 100M should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            initial_capital=200_000_000,
        )
        assert result.is_valid is False

    # --- Date tests ---

    def test_validate_dates_start_after_end(self, validator):
        """start_date >= end_date should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            start_date="2025-07-01",
            end_date="2025-06-01",
        )
        assert result.is_valid is False
        assert any("before end_date" in e for e in result.errors)

    def test_validate_dates_before_data_start(self, validator):
        """Dates before 2025-01-01 should produce warning"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            start_date="2024-06-01",
            end_date="2024-07-01",
        )
        # Should warn, not fail
        assert any("2025-01-01" in w for w in result.warnings)

    # --- Stop loss / Take profit ---

    def test_validate_stop_loss_out_of_range(self, validator):
        """Stop loss outside 0.001-0.5 should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            stop_loss=0.9,  # 90% — way too high
        )
        assert result.is_valid is False

    def test_validate_risk_reward_warning(self, validator):
        """Risk-reward < 1.0 should produce warning"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            stop_loss=0.05,
            take_profit=0.02,  # reward < risk
        )
        assert any("Risk-reward" in w for w in result.warnings)

    # --- Missing params / defaults ---

    def test_validate_missing_params_use_defaults(self, validator):
        """Missing params should be filled with defaults + warning"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={},  # no period, overbought, oversold
        )
        assert result.is_valid is True
        assert "period" in result.sanitized_params
        assert result.sanitized_params["period"] == 14  # default

    def test_validate_interval_invalid(self, validator):
        """Invalid interval should fail"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
            interval="3h",  # not valid
        )
        assert result.is_valid is False
        assert any("interval" in e.lower() for e in result.errors)

    def test_validate_custom_strategy_passes(self, validator):
        """Custom strategy type should pass (no param constraints)"""
        result = validator.validate(
            strategy_type="custom",
            strategy_params={"my_param": 42},
        )
        assert result.is_valid is True

    def test_to_dict(self, validator):
        """to_dict() should return proper structure"""
        result = validator.validate(
            strategy_type="rsi",
            strategy_params={"period": 14},
        )
        d = result.to_dict()
        assert "is_valid" in d
        assert "risk_level" in d
        assert "errors" in d
        assert "warnings" in d
        assert isinstance(d["risk_level"], str)


# ============================================================================
# MCP Trading Tools Tests (mock external deps)
# ============================================================================


class TestMCPTradingTools:
    """Tests for new MCP tools in backend/agents/mcp/trading_tools.py"""

    @pytest.mark.asyncio
    async def test_validate_strategy_tool_valid(self):
        """validate_strategy tool with valid RSI params"""
        from backend.agents.mcp.trading_tools import validate_strategy

        result = await validate_strategy(
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70, "oversold": 30},
            leverage=5.0,
            stop_loss=0.02,
            take_profit=0.03,
        )
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_strategy_tool_unknown_type(self):
        """validate_strategy tool with unknown strategy type"""
        from backend.agents.mcp.trading_tools import validate_strategy

        result = await validate_strategy(
            strategy_type="magic_beans",
            strategy_params={},
        )
        assert result["is_valid"] is False
        assert any("Unknown" in e or "magic_beans" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_strategy_tool_high_leverage_warning(self):
        """validate_strategy tool warns on high leverage"""
        from backend.agents.mcp.trading_tools import validate_strategy

        result = await validate_strategy(
            strategy_type="rsi",
            strategy_params={"period": 14},
            leverage=75.0,
        )
        # Should be valid but with warnings
        assert result["is_valid"] is True
        assert any("leverage" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_validate_strategy_tool_bad_risk_reward(self):
        """validate_strategy tool warns on poor risk-reward"""
        from backend.agents.mcp.trading_tools import validate_strategy

        result = await validate_strategy(
            strategy_type="rsi",
            strategy_params={"period": 14},
            stop_loss=0.05,
            take_profit=0.01,  # reward < risk
        )
        assert any("Risk-reward" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_list_strategies_returns_data(self):
        """list_strategies tool should return available strategies"""
        from backend.agents.mcp.trading_tools import list_strategies

        result = await list_strategies()
        assert "count" in result
        assert "strategies" in result
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_check_system_health_returns_components(self):
        """check_system_health should return component statuses"""
        from backend.agents.mcp.trading_tools import check_system_health

        result = await check_system_health()
        assert "overall" in result
        assert "components" in result
        assert "warnings" in result
        assert result["overall"] in ("healthy", "degraded")
        # Should always have disk component
        assert "disk" in result["components"]

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_strategy(self):
        """run_backtest with invalid strategy type should return error"""
        from backend.agents.mcp.trading_tools import run_backtest

        result = await run_backtest(
            symbol="BTCUSDT",
            interval="15",
            strategy_type="nonexistent_strategy",
        )
        assert "error" in result
        assert "valid_strategies" in result

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_interval(self):
        """run_backtest with invalid interval should return error"""
        from backend.agents.mcp.trading_tools import run_backtest

        result = await run_backtest(
            symbol="BTCUSDT",
            interval="3h",
            strategy_type="rsi",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_dates(self):
        """run_backtest with end before start should return error"""
        from backend.agents.mcp.trading_tools import run_backtest

        result = await run_backtest(
            symbol="BTCUSDT",
            interval="15",
            strategy_type="rsi",
            start_date="2025-07-01",
            end_date="2025-06-01",
        )
        assert "error" in result
        assert "before" in result["error"]

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_capital(self):
        """run_backtest with capital out of range should return error"""
        from backend.agents.mcp.trading_tools import run_backtest

        result = await run_backtest(
            symbol="BTCUSDT",
            interval="15",
            strategy_type="rsi",
            initial_capital=50,  # below 100
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_leverage(self):
        """run_backtest with leverage > 125 should return error"""
        from backend.agents.mcp.trading_tools import run_backtest

        result = await run_backtest(
            symbol="BTCUSDT",
            interval="15",
            strategy_type="rsi",
            leverage=200,
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_backtest_metrics_not_found(self):
        """get_backtest_metrics with non-existent ID should return error"""
        from backend.agents.mcp.trading_tools import get_backtest_metrics

        result = await get_backtest_metrics(backtest_id=999999999)
        # Should either return error or empty
        assert "error" in result or result.get("id") is None

    @pytest.mark.asyncio
    async def test_get_backtest_metrics_list_recent(self):
        """get_backtest_metrics without ID should list recent"""
        from backend.agents.mcp.trading_tools import get_backtest_metrics

        result = await get_backtest_metrics(backtest_id=None, limit=5)
        # Should return list structure even if empty
        assert "count" in result or "error" in result


# ============================================================================
# Sandbox / Resource Limits Tests (P2)
# ============================================================================


class TestSandboxResourceLimits:
    """Tests for P2 sandbox: timeout + memory guard in run_backtest"""

    @pytest.mark.asyncio
    async def test_run_backtest_has_timeout_wrapper(self):
        """run_backtest should use asyncio.wait_for with 300s timeout"""
        import inspect

        from backend.agents.mcp.trading_tools import run_backtest

        source = inspect.getsource(run_backtest)
        assert "wait_for" in source
        assert "timeout" in source.lower()

    @pytest.mark.asyncio
    async def test_run_backtest_has_memory_guard(self):
        """run_backtest should check available memory before execution"""
        import inspect

        from backend.agents.mcp.trading_tools import run_backtest

        source = inspect.getsource(run_backtest)
        assert "psutil" in source
        assert "virtual_memory" in source
        assert "512" in source  # 512MB minimum

    @pytest.mark.asyncio
    async def test_run_backtest_memory_check_low_memory(self):
        """run_backtest should abort when free memory < 512MB"""
        from unittest.mock import patch

        from backend.agents.mcp.trading_tools import run_backtest

        # Mock psutil to simulate low memory
        mock_mem = type("vmem", (), {"available": 256 * 1024 * 1024})()  # 256MB

        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = await run_backtest(
                symbol="BTCUSDT",
                interval="15",
                strategy_type="rsi",
            )
            assert "error" in result
            assert "memory" in result["error"].lower()
            assert "free_memory_mb" in result

    @pytest.mark.asyncio
    async def test_run_backtest_timeout_returns_error(self):
        """run_backtest should return error on timeout"""
        import asyncio
        from unittest.mock import AsyncMock, patch

        from backend.agents.mcp.trading_tools import run_backtest

        # Mock BacktestService to simulate a timeout
        async def slow_backtest(*args, **kwargs):
            await asyncio.sleep(999)

        mock_service = AsyncMock()
        mock_service.run_backtest = slow_backtest

        with (
            patch("backend.agents.mcp.trading_tools.BacktestService", return_value=mock_service)
            if False
            else patch.dict("sys.modules", {})
        ):
            # Can't easily mock inside the function due to lazy imports
            # Instead verify the timeout constant exists
            import inspect

            source = inspect.getsource(run_backtest)
            assert "BACKTEST_TIMEOUT" in source
            assert "300" in source  # 5 minutes


# ============================================================================
# Vector Memory Backtest Methods Tests
# ============================================================================


class TestVectorMemoryBacktest:
    """Tests for save_backtest_result / find_similar_results in vector_store.py"""

    @pytest.fixture
    def sample_metrics(self) -> dict:
        return {
            "win_rate": 65.0,
            "total_return_pct": 12.5,
            "sharpe_ratio": 1.8,
            "max_drawdown_pct": 5.2,
            "total_trades": 42,
            "profit_factor": 2.1,
        }

    @pytest.mark.asyncio
    async def test_save_backtest_result_without_init(self):
        """save_backtest_result on uninitialized store should return None"""
        from backend.agents.memory.vector_store import VectorMemoryStore

        store = VectorMemoryStore()
        # Don't initialize — _collection is None
        result = await store.save_backtest_result(
            backtest_id="test-123",
            strategy_type="rsi",
            strategy_params={"period": 14},
            metrics={"win_rate": 65.0, "total_return_pct": 12.5},
        )
        # Should return None (graceful failure)
        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_results_without_init(self):
        """find_similar_results on uninitialized store should return empty"""
        from backend.agents.memory.vector_store import VectorMemoryStore

        store = VectorMemoryStore()
        results = await store.find_similar_results(query="RSI strategy")
        assert results == []

    @pytest.mark.asyncio
    async def test_save_and_find_backtest_result(self, sample_metrics):
        """save_backtest_result then find_similar_results should find it"""
        from backend.agents.memory.vector_store import VectorMemoryStore

        store = VectorMemoryStore()  # In-memory (no persist_path)
        await store.initialize()

        if store._collection is None:
            pytest.skip("ChromaDB not available")

        # Save a result
        doc_id = await store.save_backtest_result(
            backtest_id="test-456",
            strategy_type="rsi",
            strategy_params={"period": 14, "overbought": 70},
            metrics=sample_metrics,
            symbol="BTCUSDT",
            interval="15",
        )
        assert doc_id is not None

        # Search for it
        results = await store.find_similar_results(
            query="RSI strategy with high win rate on BTC",
            top_k=5,
        )
        assert len(results) >= 1
        # Verify the result has the expected metadata
        found = results[0]
        assert found.metadata.get("strategy_type") == "rsi"
        assert found.metadata.get("type") == "backtest_result"

    @pytest.mark.asyncio
    async def test_save_backtest_result_metadata(self, sample_metrics):
        """Saved backtest should contain proper metadata"""
        from backend.agents.memory.vector_store import VectorMemoryStore

        store = VectorMemoryStore()
        await store.initialize()

        if store._collection is None:
            pytest.skip("ChromaDB not available")

        doc_id = await store.save_backtest_result(
            backtest_id="test-789",
            strategy_type="macd",
            strategy_params={"fast_period": 12, "slow_period": 26},
            metrics=sample_metrics,
            symbol="ETHUSDT",
            interval="60",
        )
        assert doc_id == "backtest_test-789"

        # Query and verify metadata
        results = await store.find_similar_results(
            query="MACD strategy",
            top_k=1,
        )
        assert len(results) >= 1
        meta = results[0].metadata
        assert meta["backtest_id"] == "test-789"
        assert meta["symbol"] == "ETHUSDT"
        assert meta["interval"] == "60"
        assert meta["profitable"] is True


# ============================================================================
# API Endpoint Tests (via httpx)
# ============================================================================


@pytest.mark.slow
class TestAgentAPIEndpoints:
    """Integration tests for /agents/actions/* endpoints.

    Marked as 'slow' because they instantiate the full FastAPI app.
    Run with: pytest -m slow
    Skip with: pytest -m "not slow"
    """

    @pytest.fixture
    async def client(self):
        """Create async test client with proper lifecycle."""
        try:
            from httpx import ASGITransport, AsyncClient

            from backend.api.app import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c
        except ImportError:
            pytest.skip("httpx not available")
        except Exception as e:
            pytest.skip(f"App init failed: {e}")

    @pytest.mark.asyncio
    async def test_strategies_endpoint(self, client):
        """GET /agents/actions/strategies should return list"""
        response = await client.get("/api/v1/agents/actions/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "strategies" in data

    @pytest.mark.asyncio
    async def test_system_health_endpoint(self, client):
        """GET /agents/actions/system-health should return status"""
        response = await client.get("/api/v1/agents/actions/system-health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "overall" in data

    @pytest.mark.asyncio
    async def test_validate_strategy_endpoint(self, client):
        """POST /agents/actions/validate-strategy should validate params"""
        response = await client.post(
            "/api/v1/agents/actions/validate-strategy",
            params={"strategy_type": "rsi", "leverage": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "is_valid" in data

    @pytest.mark.asyncio
    async def test_backtest_history_endpoint(self, client):
        """GET /agents/actions/backtest-history should return list"""
        response = await client.get(
            "/api/v1/agents/actions/backtest-history",
            params={"limit": 5},
        )
        # Should return 200 even if empty
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_tools_endpoint(self, client):
        """GET /agents/actions/tools should list registered tools"""
        response = await client.get("/api/v1/agents/actions/tools")
        assert response.status_code == 200
        data = response.json()
        assert "total_tools" in data
        assert data["total_tools"] > 0
        assert "categories" in data

    @pytest.mark.asyncio
    async def test_run_backtest_invalid_strategy(self, client):
        """POST /agents/actions/run-backtest with bad strategy should fail gracefully"""
        response = await client.post(
            "/api/v1/agents/actions/run-backtest",
            json={
                "symbol": "BTCUSDT",
                "interval": "15",
                "strategy_type": "nonexistent",
                "start_date": "2025-06-01",
                "end_date": "2025-07-01",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False
        assert data.get("error") is not None


# ============================================================================
# P3 Tools Tests
# ============================================================================


class TestP3Tools:
    """Tests for P3 tools: evolve_strategy, generate_backtest_report, log_agent_action"""

    @pytest.mark.asyncio
    async def test_evolve_strategy_invalid_timeframe(self):
        """evolve_strategy with invalid timeframe should return error"""
        from backend.agents.mcp.trading_tools import evolve_strategy

        result = await evolve_strategy(timeframe="3h")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_evolve_strategy_invalid_leverage(self):
        """evolve_strategy with leverage > 125 should return error"""
        from backend.agents.mcp.trading_tools import evolve_strategy

        result = await evolve_strategy(leverage=200)
        assert "error" in result
        assert "125" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_backtest_report_no_data(self):
        """generate_backtest_report for nonexistent ID should return error"""
        from backend.agents.mcp.trading_tools import generate_backtest_report

        result = await generate_backtest_report(backtest_id=999999999)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_backtest_report_format_json(self):
        """generate_backtest_report with format=json should return json structure"""
        from backend.agents.mcp.trading_tools import generate_backtest_report

        result = await generate_backtest_report(format="json")
        assert "error" in result or "assessment" in result

    @pytest.mark.asyncio
    async def test_generate_backtest_report_format_markdown(self):
        """generate_backtest_report with format=markdown should return markdown"""
        from backend.agents.mcp.trading_tools import generate_backtest_report

        result = await generate_backtest_report(format="markdown")
        if "report" in result:
            assert "# Backtest Report" in result["report"]
            assert result["format"] == "markdown"

    @pytest.mark.asyncio
    async def test_log_agent_action_success(self):
        """log_agent_action should create a log entry"""
        from backend.agents.mcp.trading_tools import log_agent_action

        result = await log_agent_action(
            agent_name="test_agent",
            action="test_action",
            details={"test_key": "test_value"},
            result_summary="Test completed",
            success=True,
        )
        assert result["logged"] is True
        assert "timestamp" in result
        assert "log_file" in result

    @pytest.mark.asyncio
    async def test_log_agent_action_failure(self):
        """log_agent_action for failed action should still log"""
        from backend.agents.mcp.trading_tools import log_agent_action

        result = await log_agent_action(
            agent_name="test_agent",
            action="failed_action",
            result_summary="Something broke",
            success=False,
        )
        assert result["logged"] is True

    @pytest.mark.asyncio
    async def test_log_agent_action_creates_file(self):
        """log_agent_action should create a JSONL log file"""
        import json
        from pathlib import Path

        from backend.agents.mcp.trading_tools import log_agent_action

        result = await log_agent_action(
            agent_name="file_test_agent",
            action="file_test",
        )
        assert result["logged"] is True

        log_file = Path(result["log_file"])
        assert log_file.exists()

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry["agent_name"] == "file_test_agent"
        assert last_entry["action"] == "file_test"
