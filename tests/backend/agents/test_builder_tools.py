"""
Tests for Strategy Builder MCP Tools and Builder Workflow.

Tests cover:
- MCP tool registration (all 20 builder tools)
- Individual tool functions (with mocked HTTP calls)
- BuilderWorkflow orchestration
- API endpoint for builder task

All HTTP calls to the Strategy Builder API are mocked — no real server needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_strategy_response() -> dict[str, Any]:
    """Sample strategy response from the API."""
    return {
        "id": "test-strategy-001",
        "name": "Test RSI Strategy",
        "description": "",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "direction": "both",
        "market_type": "linear",
        "initial_capital": 10000.0,
        "leverage": 10.0,
        "blocks": [],
        "connections": [],
        "builder_graph": {},
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_strategy_with_blocks() -> dict[str, Any]:
    """Strategy response with blocks and connections."""
    return {
        "id": "test-strategy-002",
        "name": "RSI + EMA Strategy",
        "description": "",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "direction": "both",
        "market_type": "linear",
        "initial_capital": 10000.0,
        "leverage": 10.0,
        "blocks": [
            {
                "id": "rsi_abc123",
                "type": "rsi",
                "name": "RSI",
                "x": 100,
                "y": 100,
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "id": "ema_def456",
                "type": "ema",
                "name": "EMA",
                "x": 100,
                "y": 220,
                "params": {"period": 21},
            },
        ],
        "connections": [
            {
                "id": "conn_aaa111",
                "source": {"blockId": "rsi_abc123", "portId": "value"},
                "target": {"blockId": "ema_def456", "portId": "input"},
            }
        ],
        "builder_graph": {},
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_block_library() -> dict[str, Any]:
    """Sample block library response."""
    return {
        "indicators": [
            {"id": "rsi", "name": "RSI", "description": "Relative Strength Index"},
            {"id": "ema", "name": "EMA", "description": "Exponential Moving Average"},
            {"id": "macd", "name": "MACD", "description": "MACD"},
        ],
        "conditions": [
            {"id": "crossover", "name": "Crossover", "description": "Crossover condition"},
        ],
        "actions": [
            {"id": "buy", "name": "Buy", "description": "Buy action"},
            {"id": "sell", "name": "Sell", "description": "Sell action"},
        ],
    }


@pytest.fixture
def mock_backtest_results() -> dict[str, Any]:
    """Sample backtest results."""
    return {
        "metrics": {
            "sharpe_ratio": 1.25,
            "win_rate": 0.55,
            "total_trades": 42,
            "net_profit": 1500.0,
            "max_drawdown_pct": -8.5,
            "profit_factor": 1.8,
        },
        "trades": [
            {
                "id": 1,
                "type": "long",
                "entry_price": 50000,
                "exit_price": 51000,
                "pnl": 200.0,
            },
        ],
    }


# =============================================================================
# TOOL REGISTRATION TESTS
# =============================================================================


class TestToolRegistration:
    """Verify all 20 builder tools are registered."""

    def test_builder_tools_registered(self):
        """All builder tools should be in the global registry."""
        import backend.agents.mcp.tools.strategy_builder  # noqa: F401
        from backend.agents.mcp.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.list_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "builder_get_block_library",
            "builder_create_strategy",
            "builder_get_strategy",
            "builder_list_strategies",
            "builder_update_strategy",
            "builder_delete_strategy",
            "builder_add_block",
            "builder_update_block_params",
            "builder_remove_block",
            "builder_connect_blocks",
            "builder_disconnect_blocks",
            "builder_validate_strategy",
            "builder_generate_code",
            "builder_run_backtest",
            "builder_list_templates",
            "builder_instantiate_template",
            "builder_get_optimizable_params",
            "builder_analyze_strategy",
            "builder_get_versions",
            "builder_revert_version",
            "builder_export_strategy",
            "builder_import_strategy",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool '{tool_name}' not registered"

    def test_builder_tools_have_category(self):
        """All builder tools should have category 'strategy_builder'."""
        import backend.agents.mcp.tools.strategy_builder  # noqa: F401
        from backend.agents.mcp.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.list_tools()

        builder_tools = [t for t in tools if t.name.startswith("builder_")]
        assert len(builder_tools) >= 20, f"Expected 20+ builder tools, got {len(builder_tools)}"

        for tool in builder_tools:
            assert tool.category == "strategy_builder", (
                f"Tool '{tool.name}' has category '{tool.category}' instead of 'strategy_builder'"
            )

    def test_builder_tools_count_in_init(self):
        """All builder tools should be importable from __init__."""
        from backend.agents.mcp.tools import (
            builder_add_block,
            builder_analyze_strategy,
            builder_connect_blocks,
            builder_create_strategy,
            builder_delete_strategy,
            builder_disconnect_blocks,
            builder_export_strategy,
            builder_generate_code,
            builder_get_block_library,
            builder_get_optimizable_params,
            builder_get_strategy,
            builder_get_versions,
            builder_import_strategy,
            builder_instantiate_template,
            builder_list_strategies,
            builder_list_templates,
            builder_remove_block,
            builder_revert_version,
            builder_run_backtest,
            builder_update_block_params,
            builder_update_strategy,
            builder_validate_strategy,
        )

        # All should be callable
        assert callable(builder_add_block)
        assert callable(builder_analyze_strategy)
        assert callable(builder_connect_blocks)
        assert callable(builder_create_strategy)
        assert callable(builder_delete_strategy)
        assert callable(builder_disconnect_blocks)
        assert callable(builder_export_strategy)
        assert callable(builder_generate_code)
        assert callable(builder_get_block_library)
        assert callable(builder_get_optimizable_params)
        assert callable(builder_get_strategy)
        assert callable(builder_get_versions)
        assert callable(builder_import_strategy)
        assert callable(builder_instantiate_template)
        assert callable(builder_list_strategies)
        assert callable(builder_list_templates)
        assert callable(builder_remove_block)
        assert callable(builder_revert_version)
        assert callable(builder_run_backtest)
        assert callable(builder_update_block_params)
        assert callable(builder_update_strategy)
        assert callable(builder_validate_strategy)


# =============================================================================
# INDIVIDUAL TOOL TESTS (with mocked HTTP)
# =============================================================================


class TestBuilderGetBlockLibrary:
    """Tests for builder_get_block_library."""

    @pytest.mark.asyncio
    async def test_get_block_library_success(self, mock_block_library):
        """Should return block library from API."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_get",
            new_callable=AsyncMock,
            return_value=mock_block_library,
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_get_block_library

            result = await builder_get_block_library()

        assert "indicators" in result
        assert "conditions" in result
        assert "actions" in result
        assert len(result["indicators"]) == 3

    @pytest.mark.asyncio
    async def test_get_block_library_error_handling(self):
        """Should return error dict on failure."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_get",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_get_block_library

            result = await builder_get_block_library()

        assert "error" in result
        assert "Connection refused" in result["error"]


class TestBuilderCreateStrategy:
    """Tests for builder_create_strategy."""

    @pytest.mark.asyncio
    async def test_create_strategy_success(self, mock_strategy_response):
        """Should create strategy via API."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_post",
            new_callable=AsyncMock,
            return_value=mock_strategy_response,
        ) as mock_post:
            from backend.agents.mcp.tools.strategy_builder import builder_create_strategy

            result = await builder_create_strategy(
                name="Test RSI Strategy",
                symbol="BTCUSDT",
                timeframe="15",
            )

        assert result["id"] == "test-strategy-001"
        assert result["name"] == "Test RSI Strategy"
        mock_post.assert_called_once()
        call_payload = mock_post.call_args[1]["json_data"]
        assert call_payload["name"] == "Test RSI Strategy"
        assert call_payload["symbol"] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_create_strategy_with_all_params(self, mock_strategy_response):
        """Should pass all parameters to API."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_post",
            new_callable=AsyncMock,
            return_value=mock_strategy_response,
        ) as mock_post:
            from backend.agents.mcp.tools.strategy_builder import builder_create_strategy

            await builder_create_strategy(
                name="Full Strategy",
                symbol="ETHUSDT",
                timeframe="60",
                direction="long",
                market_type="linear",
                initial_capital=50000.0,
                leverage=20.0,
                description="My strategy description",
            )

        call_payload = mock_post.call_args[1]["json_data"]
        assert call_payload["symbol"] == "ETHUSDT"
        assert call_payload["timeframe"] == "60"
        assert call_payload["direction"] == "long"
        assert call_payload["initial_capital"] == 50000.0
        assert call_payload["leverage"] == 20.0
        assert call_payload["description"] == "My strategy description"


class TestBuilderAddBlock:
    """Tests for builder_add_block."""

    @pytest.mark.asyncio
    async def test_add_block_success(self, mock_strategy_response):
        """Should add block to strategy and save."""
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value=mock_strategy_response,
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
                return_value=mock_strategy_response,
            ) as mock_put,
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_add_block

            result = await builder_add_block(
                strategy_id="test-strategy-001",
                block_type="rsi",
                params={"period": 14, "overbought": 70, "oversold": 30},
            )

        assert result["status"] == "added"
        assert result["block"]["type"] == "rsi"
        assert result["total_blocks"] == 1
        # Verify the PUT was called with the new block
        put_payload = mock_put.call_args[1]["json_data"]
        assert len(put_payload["blocks"]) == 1
        assert put_payload["blocks"][0]["type"] == "rsi"

    @pytest.mark.asyncio
    async def test_add_block_with_custom_id(self, mock_strategy_response):
        """Should use custom block ID when provided."""
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value=mock_strategy_response,
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
                return_value=mock_strategy_response,
            ),
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_add_block

            result = await builder_add_block(
                strategy_id="test-strategy-001",
                block_type="ema",
                block_id="my_custom_ema",
                params={"period": 50},
            )

        assert result["block"]["id"] == "my_custom_ema"

    @pytest.mark.asyncio
    async def test_add_multiple_blocks(self, mock_strategy_with_blocks):
        """Should add block to existing blocks list."""
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ) as mock_put,
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_add_block

            result = await builder_add_block(
                strategy_id="test-strategy-002",
                block_type="crossover",
            )

        assert result["total_blocks"] == 3  # 2 existing + 1 new
        put_payload = mock_put.call_args[1]["json_data"]
        assert len(put_payload["blocks"]) == 3


class TestBuilderUpdateBlockParams:
    """Tests for builder_update_block_params."""

    @pytest.mark.asyncio
    async def test_update_params_success(self, mock_strategy_with_blocks):
        """Should merge new params into existing block."""
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ),
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_update_block_params

            result = await builder_update_block_params(
                strategy_id="test-strategy-002",
                block_id="rsi_abc123",
                params={"period": 21, "overbought": 80},
            )

        assert result["status"] == "updated"
        assert result["params"]["period"] == 21
        assert result["params"]["overbought"] == 80
        assert result["params"]["oversold"] == 30  # preserved

    @pytest.mark.asyncio
    async def test_update_params_block_not_found(self, mock_strategy_with_blocks):
        """Should return error for non-existent block."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_get",
            new_callable=AsyncMock,
            return_value=mock_strategy_with_blocks,
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_update_block_params

            result = await builder_update_block_params(
                strategy_id="test-strategy-002",
                block_id="nonexistent_block",
                params={"period": 21},
            )

        assert "error" in result
        assert "not found" in result["error"]


class TestBuilderRemoveBlock:
    """Tests for builder_remove_block."""

    @pytest.mark.asyncio
    async def test_remove_block_and_connections(self, mock_strategy_with_blocks):
        """Should remove block and its connections."""
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ) as mock_put,
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_remove_block

            result = await builder_remove_block(
                strategy_id="test-strategy-002",
                block_id="rsi_abc123",
            )

        assert result["status"] == "removed"
        assert result["remaining_blocks"] == 1
        assert result["connections_removed"] == 1  # connection had rsi as source
        put_payload = mock_put.call_args[1]["json_data"]
        assert len(put_payload["blocks"]) == 1
        assert len(put_payload["connections"]) == 0


class TestBuilderConnectBlocks:
    """Tests for builder_connect_blocks."""

    @pytest.mark.asyncio
    async def test_connect_blocks_success(self, mock_strategy_with_blocks):
        """Should create connection between blocks."""
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
                return_value=mock_strategy_with_blocks,
            ) as mock_put,
        ):
            from backend.agents.mcp.tools.strategy_builder import builder_connect_blocks

            result = await builder_connect_blocks(
                strategy_id="test-strategy-002",
                source_block_id="rsi_abc123",
                source_port="value",
                target_block_id="ema_def456",
                target_port="condition",
            )

        assert result["status"] == "connected"
        assert result["total_connections"] == 2  # 1 existing + 1 new
        assert result["connection"]["source"]["blockId"] == "rsi_abc123"


class TestBuilderRunBacktest:
    """Tests for builder_run_backtest."""

    @pytest.mark.asyncio
    async def test_run_backtest_success(self, mock_backtest_results):
        """Should run backtest and return metrics."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_post",
            new_callable=AsyncMock,
            return_value=mock_backtest_results,
        ) as mock_post:
            from backend.agents.mcp.tools.strategy_builder import builder_run_backtest

            result = await builder_run_backtest(
                strategy_id="test-strategy-001",
                symbol="BTCUSDT",
                interval="15",
                start_date="2025-01-01",
                end_date="2025-06-01",
            )

        assert result["metrics"]["sharpe_ratio"] == 1.25
        assert result["metrics"]["win_rate"] == 0.55
        call_payload = mock_post.call_args[1]["json_data"]
        assert call_payload["commission"] == 0.0007  # TradingView parity

    @pytest.mark.asyncio
    async def test_run_backtest_with_sl_tp(self, mock_backtest_results):
        """Should pass stop_loss and take_profit."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_post",
            new_callable=AsyncMock,
            return_value=mock_backtest_results,
        ) as mock_post:
            from backend.agents.mcp.tools.strategy_builder import builder_run_backtest

            await builder_run_backtest(
                strategy_id="test-strategy-001",
                stop_loss=0.02,
                take_profit=0.03,
            )

        call_payload = mock_post.call_args[1]["json_data"]
        assert call_payload["stop_loss"] == 0.02
        assert call_payload["take_profit"] == 0.03

    @pytest.mark.asyncio
    async def test_run_backtest_commission_never_changed(self, mock_backtest_results):
        """Commission must always be 0.0007 — TradingView parity."""
        with patch(
            "backend.agents.mcp.tools.strategy_builder._api_post",
            new_callable=AsyncMock,
            return_value=mock_backtest_results,
        ) as mock_post:
            from backend.agents.mcp.tools.strategy_builder import builder_run_backtest

            # Even with different commission arg, should use 0.0007
            await builder_run_backtest(
                strategy_id="test-strategy-001",
                commission=0.0007,
            )

        call_payload = mock_post.call_args[1]["json_data"]
        assert call_payload["commission"] == 0.0007


# =============================================================================
# BUILDER WORKFLOW TESTS
# =============================================================================


class TestBuilderWorkflow:
    """Tests for BuilderWorkflow orchestration."""

    @pytest.mark.asyncio
    async def test_workflow_full_pipeline(
        self,
        mock_strategy_response,
        mock_block_library,
        mock_backtest_results,
    ):
        """Should execute full pipeline: create → add → connect → validate → backtest."""
        from backend.agents.workflows.builder_workflow import (
            BuilderStage,
            BuilderWorkflow,
            BuilderWorkflowConfig,
        )

        config = BuilderWorkflowConfig(
            name="Test Workflow Strategy",
            symbol="BTCUSDT",
            timeframe="15",
            blocks=[
                {"type": "rsi", "id": "rsi_1", "params": {"period": 14}},
                {"type": "buy", "id": "buy_1"},
            ],
            connections=[
                {
                    "source": "rsi_1",
                    "source_port": "value",
                    "target": "buy_1",
                    "target_port": "condition",
                },
            ],
        )

        # Workflow now auto-adds price_input + main_strategy blocks
        # So strategy evolves through multiple GET calls
        strategy_empty = {**mock_strategy_response, "blocks": [], "connections": []}
        strategy_with_price = {
            **mock_strategy_response,
            "blocks": [
                {
                    "id": "price_input",
                    "type": "price",
                    "category": "input",
                    "name": "PRICE",
                    "x": 50,
                    "y": 200,
                    "params": {"source": "close"},
                },
            ],
            "connections": [],
        }
        strategy_with_rsi = {
            **strategy_with_price,
            "blocks": strategy_with_price["blocks"]
            + [
                {
                    "id": "rsi_1",
                    "type": "rsi",
                    "category": "indicator",
                    "name": "RSI",
                    "x": 200,
                    "y": 100,
                    "params": {"period": 14},
                },
            ],
        }
        strategy_with_buy = {
            **strategy_with_rsi,
            "blocks": strategy_with_rsi["blocks"]
            + [
                {"id": "buy_1", "type": "buy", "category": "action", "name": "BUY", "x": 700, "y": 220, "params": {}},
            ],
        }
        strategy_with_main = {
            **strategy_with_buy,
            "blocks": strategy_with_buy["blocks"]
            + [
                {
                    "id": "main_strategy",
                    "type": "strategy",
                    "category": "output",
                    "name": "STRATEGY",
                    "isMain": True,
                    "x": 950,
                    "y": 300,
                    "params": {"isMain": True},
                },
            ],
        }
        strategy_with_conn = {
            **strategy_with_main,
            "connections": [
                {
                    "id": "conn_1",
                    "source": {"blockId": "rsi_1", "portId": "value"},
                    "target": {"blockId": "buy_1", "portId": "condition"},
                }
            ],
        }
        # After auto-adding static_sltp block (no exit blocks in config)
        strategy_with_sltp = {
            **strategy_with_main,
            "blocks": strategy_with_main["blocks"]
            + [
                {
                    "id": "auto_sltp",
                    "type": "static_sltp",
                    "category": "action",
                    "name": "SL/TP",
                    "x": 950,
                    "y": 500,
                    "params": {"stop_loss_percent": 2.0, "take_profit_percent": 4.0},
                },
            ],
        }

        # Mock all API calls
        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_post",
                new_callable=AsyncMock,
            ) as mock_post,
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_put",
                new_callable=AsyncMock,
            ) as mock_put,
        ):
            # Configure return values
            # GETs: block_library, add_block(price), add_block(rsi), add_block(buy),
            #        add_block(main_strategy), add_block(static_sltp),
            #        connect(user), connect(auto-wire buy→main)
            mock_get.side_effect = [
                mock_block_library,  # get block library
                strategy_empty,  # get strategy for add_block (price_input)
                strategy_with_price,  # get strategy for add_block (rsi)
                strategy_with_rsi,  # get strategy for add_block (buy)
                strategy_with_buy,  # get strategy for add_block (main_strategy)
                strategy_with_main,  # get strategy for add_block (static_sltp)
                strategy_with_sltp,  # get strategy for connect_blocks (user)
                strategy_with_conn,  # get strategy for connect_blocks (auto-wire)
            ]
            mock_post.side_effect = [
                mock_strategy_response,  # create strategy
                {"is_valid": True, "errors": [], "warnings": []},  # validate
                {"code": "# generated code"},  # generate code
                mock_backtest_results,  # backtest
            ]
            mock_put.return_value = strategy_with_main  # update (add block, connect)

            workflow = BuilderWorkflow()
            result = await workflow.run(config)

        assert result.status == BuilderStage.COMPLETED
        assert result.strategy_id == "test-strategy-001"
        # 5 blocks: price_input + rsi + buy + main_strategy + auto_sltp
        assert len(result.blocks_added) == 5
        assert result.backtest_results["metrics"]["sharpe_ratio"] == 1.25
        assert result.duration_seconds > 0
        assert len(result.iterations) == 1

    @pytest.mark.asyncio
    async def test_workflow_handles_create_failure(self):
        """Should fail gracefully when strategy creation fails."""
        from backend.agents.workflows.builder_workflow import (
            BuilderStage,
            BuilderWorkflow,
            BuilderWorkflowConfig,
        )

        config = BuilderWorkflowConfig(name="Failing Strategy")

        with (
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_get",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder._api_post",
                new_callable=AsyncMock,
                return_value={"error": "Database error"},
            ),
        ):
            workflow = BuilderWorkflow()
            result = await workflow.run(config)

        assert result.status == BuilderStage.FAILED
        assert len(result.errors) > 0

    def test_workflow_config_serialization(self):
        """WorkflowConfig should serialize to dict."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflowConfig

        config = BuilderWorkflowConfig(
            name="Test",
            symbol="ETHUSDT",
            blocks=[{"type": "rsi"}],
        )
        d = config.to_dict()

        assert d["name"] == "Test"
        assert d["symbol"] == "ETHUSDT"
        assert d["commission"] == 0.0007
        assert len(d["blocks"]) == 1

    def test_workflow_result_serialization(self):
        """WorkflowResult should serialize to dict."""
        from backend.agents.workflows.builder_workflow import (
            BuilderStage,
            BuilderWorkflowResult,
        )

        result = BuilderWorkflowResult(
            workflow_id="bw_test123",
            strategy_id="strat_abc",
            status=BuilderStage.COMPLETED,
            generated_code="x" * 1000,
        )
        d = result.to_dict()

        assert d["workflow_id"] == "bw_test123"
        assert d["status"] == "completed"
        assert len(d["generated_code"]) == 500  # truncated

    @pytest.mark.asyncio
    async def test_workflow_optimize_existing_strategy(self):
        """Optimize mode: skip Stages 2-4 when existing_strategy_id is set."""
        from backend.agents.workflows.builder_workflow import (
            BuilderWorkflow,
            BuilderWorkflowConfig,
        )

        config = BuilderWorkflowConfig(
            name="Optimize RSI",
            symbol="BTCUSDT",
            existing_strategy_id="existing-strat-999",
            blocks=[],
            connections=[],
            max_iterations=1,
        )

        existing_strategy_response = {
            "id": "existing-strat-999",
            "name": "Optimize RSI",
            "blocks": [
                {"id": "rsi_1", "type": "rsi", "params": {"period": 14}},
                {"id": "buy_1", "type": "buy", "params": {}},
            ],
            "connections": [{"source": "rsi_1", "source_port": "value", "target": "buy_1", "target_port": "signal"}],
        }

        mock_validate = {"is_valid": True, "errors": []}
        mock_code = {"code": "def generate_signals(df): return df"}
        mock_backtest = {
            "results": {
                "sharpe_ratio": 1.5,
                "win_rate": 0.55,
                "total_trades": 20,
                "net_profit": 500.0,
                "max_drawdown_pct": 5.0,
            }
        }

        with (
            patch(
                "backend.agents.workflows.builder_workflow.builder_get_block_library",
                new_callable=AsyncMock,
                return_value={"blocks": {}},
            ),
            patch(
                "backend.agents.mcp.tools.strategy_builder.builder_get_strategy",
                new_callable=AsyncMock,
                return_value=existing_strategy_response,
            ) as mock_get_strat,
            patch(
                "backend.agents.workflows.builder_workflow.builder_validate_strategy",
                new_callable=AsyncMock,
                return_value=mock_validate,
            ),
            patch(
                "backend.agents.workflows.builder_workflow.builder_generate_code",
                new_callable=AsyncMock,
                return_value=mock_code,
            ),
            patch(
                "backend.agents.workflows.builder_workflow.builder_run_backtest",
                new_callable=AsyncMock,
                return_value=mock_backtest,
            ),
        ):
            workflow = BuilderWorkflow()
            result = await workflow.run(config)

        # Verify strategy_id is set to existing one (not created)
        assert result.strategy_id == "existing-strat-999"
        assert result.status.value == "completed"
        # Verify no create/add_block/connect calls were made
        # (builder_create_strategy, builder_add_block, builder_connect_blocks NOT called)
        assert result.blocks_added == existing_strategy_response["blocks"]
        assert result.connections_made == existing_strategy_response["connections"]
        # Verify backtest was run
        assert result.backtest_results == mock_backtest
        assert len(result.iterations) >= 1
        assert result.iterations[0]["sharpe_ratio"] == 1.5

    def test_workflow_config_existing_strategy_serialization(self):
        """Config with existing_strategy_id should serialize correctly."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflowConfig

        config = BuilderWorkflowConfig(
            name="Optimize Test",
            existing_strategy_id="strat-abc-123",
        )
        d = config.to_dict()
        assert d["existing_strategy_id"] == "strat-abc-123"

        # Without existing_strategy_id
        config2 = BuilderWorkflowConfig(name="Build Test")
        d2 = config2.to_dict()
        assert d2["existing_strategy_id"] is None


# =============================================================================
# DATA MODEL TESTS
# =============================================================================


class TestBuilderStage:
    """Tests for BuilderStage enum."""

    def test_all_stages_exist(self):
        """Should have all expected pipeline stages."""
        from backend.agents.workflows.builder_workflow import BuilderStage

        expected = [
            "idle",
            "planning",
            "creating",
            "adding_blocks",
            "connecting",
            "validating",
            "generating_code",
            "backtesting",
            "evaluating",
            "iterating",
            "completed",
            "failed",
        ]
        actual = [s.value for s in BuilderStage]
        for stage in expected:
            assert stage in actual, f"Missing stage: {stage}"


class TestBuilderWorkflowConfig:
    """Tests for BuilderWorkflowConfig defaults."""

    def test_default_commission(self):
        """Default commission must be 0.0007."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflowConfig

        config = BuilderWorkflowConfig()
        assert config.commission == 0.0007

    def test_default_values(self):
        """Should have sensible defaults."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflowConfig

        config = BuilderWorkflowConfig()
        assert config.symbol == "BTCUSDT"
        assert config.timeframe == "15"
        assert config.direction == "both"
        assert config.initial_capital == 10000.0
        assert config.leverage == 10.0
        assert config.max_iterations == 3


# =============================================================================
# API ENDPOINT TESTS
# =============================================================================


class TestBuilderEndpoints:
    """Tests for the agents_advanced builder endpoints."""

    @pytest.mark.asyncio
    async def test_builder_task_endpoint_exists(self):
        """The /builder/task endpoint should be registered."""
        from backend.api.routers.agents_advanced import router

        routes = [r.path for r in router.routes]
        assert "/builder/task" in routes

    @pytest.mark.asyncio
    async def test_builder_block_library_endpoint_exists(self):
        """The /builder/block-library endpoint should be registered."""
        from backend.api.routers.agents_advanced import router

        routes = [r.path for r in router.routes]
        assert "/builder/block-library" in routes

    @pytest.mark.asyncio
    async def test_builder_strategies_endpoint_exists(self):
        """The /builder/strategies endpoint should be registered."""
        from backend.api.routers.agents_advanced import router

        routes = [r.path for r in router.routes]
        assert "/builder/strategies" in routes

    def test_builder_task_request_model(self):
        """BuilderTaskRequest should validate correctly."""
        from backend.api.routers.agents_advanced import BuilderTaskRequest

        # Default values
        req = BuilderTaskRequest()
        assert req.name == "Agent Strategy"
        assert req.symbol == "BTCUSDT"
        assert req.blocks == []

        # Custom values
        req = BuilderTaskRequest(
            name="RSI Strategy",
            blocks=[{"type": "rsi", "params": {"period": 14}}],
            connections=[{"source": "rsi", "target": "buy"}],
        )
        assert req.name == "RSI Strategy"
        assert len(req.blocks) == 1
        assert len(req.connections) == 1

    def test_builder_task_request_deliberation_field(self):
        """BuilderTaskRequest should have enable_deliberation field."""
        from backend.api.routers.agents_advanced import BuilderTaskRequest

        req = BuilderTaskRequest()
        assert req.enable_deliberation is False

        req = BuilderTaskRequest(enable_deliberation=True)
        assert req.enable_deliberation is True


# =============================================================================
# ITERATIVE OPTIMIZATION TESTS
# =============================================================================


class TestIterativeOptimization:
    """Tests for the iterative parameter adjustment loop."""

    def test_suggest_adjustments_rsi_low_win_rate(self):
        """When win rate is low, RSI thresholds should widen."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflow

        wf = BuilderWorkflow()

        blocks_added = [
            {
                "id": "rsi_001",
                "type": "rsi",
                "params": {"period": 14, "overbought": 70, "oversold": 30},
            },
        ]
        metrics = {"win_rate": 0.2, "sharpe_ratio": 0.1, "max_drawdown_pct": -10}

        adjustments = wf._heuristic_adjustments(blocks_added, 1, metrics)
        assert len(adjustments) == 1
        adj = adjustments[0]
        assert adj["block_id"] == "rsi_001"
        # Overbought should increase, oversold should decrease
        assert adj["params"]["overbought"] > 70
        assert adj["params"]["oversold"] < 30

    def test_suggest_adjustments_ema_high_drawdown(self):
        """When drawdown is high, EMA period should increase."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflow

        wf = BuilderWorkflow()

        blocks_added = [
            {"id": "ema_001", "type": "ema", "params": {"period": 21}},
        ]
        metrics = {"win_rate": 0.5, "sharpe_ratio": 0.5, "max_drawdown_pct": -25}

        adjustments = wf._heuristic_adjustments(blocks_added, 1, metrics)
        assert len(adjustments) == 1
        assert adjustments[0]["params"]["period"] > 21

    def test_suggest_adjustments_no_params(self):
        """Blocks without params should not generate adjustments."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflow

        wf = BuilderWorkflow()

        blocks_added = [
            {"id": "buy_001", "type": "buy", "params": {}},
            {"id": "sell_001", "type": "sell", "params": {}},
        ]
        metrics = {"win_rate": 0.2, "sharpe_ratio": 0.1, "max_drawdown_pct": -10}

        adjustments = wf._heuristic_adjustments(blocks_added, 1, metrics)
        assert len(adjustments) == 0

    def test_suggest_adjustments_progressive_step(self):
        """Each iteration should apply larger adjustments."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflow

        wf = BuilderWorkflow()

        blocks = [
            {"id": "rsi_001", "type": "rsi", "params": {"period": 14, "overbought": 70, "oversold": 30}},
        ]
        metrics = {"win_rate": 0.2, "sharpe_ratio": 0.1, "max_drawdown_pct": -10}

        adj1 = wf._heuristic_adjustments(blocks, 1, metrics)
        adj2 = wf._heuristic_adjustments(blocks, 2, metrics)

        # Iteration 2 should have bigger adjustments
        ob1 = adj1[0]["params"]["overbought"]
        ob2 = adj2[0]["params"]["overbought"]
        assert ob2 > ob1

    @pytest.mark.asyncio
    async def test_workflow_with_iterations(self):
        """Workflow should iterate when criteria not met."""
        from backend.agents.workflows.builder_workflow import (
            BuilderWorkflow,
            BuilderWorkflowConfig,
        )

        config = BuilderWorkflowConfig(
            name="Iteration Test",
            blocks=[{"type": "rsi", "params": {"period": 14, "overbought": 70, "oversold": 30}}],
            max_iterations=2,
            min_acceptable_sharpe=100.0,  # Impossibly high — forces iteration
        )

        # Mock all API calls
        with (
            patch("backend.agents.mcp.tools.strategy_builder._api_get") as mock_get,
            patch("backend.agents.mcp.tools.strategy_builder._api_post") as mock_post,
            patch("backend.agents.mcp.tools.strategy_builder._api_put") as mock_put,
        ):
            mock_get.return_value = {
                "id": "iter-strat-001",
                "name": "Test",
                "blocks": [
                    {"id": "rsi_x", "type": "rsi", "params": {"period": 14, "overbought": 70, "oversold": 30}},
                ],
                "connections": [],
                "description": "",
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "direction": "both",
                "market_type": "linear",
                "initial_capital": 10000.0,
                "leverage": 10.0,
            }
            mock_post.return_value = {
                "id": "iter-strat-001",
                "block": {"id": "rsi_x", "type": "rsi", "params": {"period": 14, "overbought": 70, "oversold": 30}},
                "code": "# test",
                "metrics": {
                    "sharpe_ratio": 0.3,
                    "win_rate": 0.3,  # Low win_rate triggers RSI threshold adjustments
                    "total_trades": 10,
                    "net_profit": 100,
                    "max_drawdown_pct": -5,
                },
            }
            mock_put.return_value = {"status": "ok"}

            wf = BuilderWorkflow()
            result = await wf.run(config)

            # Should have 2 iterations since Sharpe never reaches 100
            assert len(result.iterations) == 2
            assert result.status.value in ("completed", "failed")

    def test_config_enable_deliberation_default(self):
        """BuilderWorkflowConfig should default enable_deliberation=False."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflowConfig

        config = BuilderWorkflowConfig()
        assert config.enable_deliberation is False

        config = BuilderWorkflowConfig(enable_deliberation=True)
        assert config.enable_deliberation is True
        assert config.to_dict()["enable_deliberation"] is True

    def test_result_has_deliberation_field(self):
        """BuilderWorkflowResult should have deliberation field."""
        from backend.agents.workflows.builder_workflow import BuilderWorkflowResult

        result = BuilderWorkflowResult()
        assert result.deliberation == {}
        d = result.to_dict()
        assert "deliberation" in d
