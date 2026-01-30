"""
Tests for Strategy Builder WebSocket Validation Endpoint.

Tests real-time validation functionality via WebSocket.
"""

import pytest

from backend.api.routers.strategy_validation_ws import (
    BLOCK_VALIDATION_RULES,
    ValidationResult,
    ValidationSeverity,
    router,
    validate_block,
    validate_connection,
    validate_param_value,
    validate_strategy,
)


class TestValidationRules:
    """Test validation rule coverage."""

    def test_rules_exist_for_common_blocks(self):
        """Test that common blocks have validation rules."""
        common_blocks = [
            "rsi",
            "macd_cross",
            "ma_cross",
            "bb_breakout",
            "engulfing",
            "stop_loss",
            "take_profit",
        ]

        for block_type in common_blocks:
            assert block_type in BLOCK_VALIDATION_RULES, f"Missing rules for {block_type}"

    def test_exotic_patterns_have_rules(self):
        """Test that exotic candlestick patterns have rules."""
        exotic_patterns = [
            "three_line_strike",
            "kicker",
            "abandoned_baby",
            "belt_hold",
            "counterattack",
            "gap_pattern",
            "ladder_pattern",
            "stick_sandwich",
            "homing_pigeon",
            "matching_low_high",
        ]

        for pattern in exotic_patterns:
            assert pattern in BLOCK_VALIDATION_RULES, f"Missing rules for {pattern}"


class TestParamValidation:
    """Test individual parameter validation."""

    def test_valid_integer(self):
        """Test valid integer parameter."""
        rules = {"period": {"type": "integer", "min": 1, "max": 500}}
        messages = validate_param_value("period", 14, rules)
        assert len(messages) == 0

    def test_invalid_integer_too_low(self):
        """Test integer below minimum."""
        rules = {"period": {"type": "integer", "min": 1, "max": 500}}
        messages = validate_param_value("period", 0, rules)
        assert len(messages) == 1
        assert messages[0].severity == ValidationSeverity.ERROR
        assert "MIN_VALUE" in messages[0].code

    def test_invalid_integer_too_high(self):
        """Test integer above maximum."""
        rules = {"period": {"type": "integer", "min": 1, "max": 500}}
        messages = validate_param_value("period", 1000, rules)
        assert len(messages) == 1
        assert messages[0].severity == ValidationSeverity.ERROR

    def test_valid_number(self):
        """Test valid number parameter."""
        rules = {"threshold": {"type": "number", "min": 0, "max": 100}}
        messages = validate_param_value("threshold", 70.5, rules)
        assert len(messages) == 0

    def test_valid_select(self):
        """Test valid select parameter."""
        rules = {"direction": {"type": "select", "options": ["bullish", "bearish", "both"]}}
        messages = validate_param_value("direction", "bullish", rules)
        assert len(messages) == 0

    def test_invalid_select(self):
        """Test invalid select option."""
        rules = {"direction": {"type": "select", "options": ["bullish", "bearish", "both"]}}
        messages = validate_param_value("direction", "invalid", rules)
        assert len(messages) == 1
        assert messages[0].code == "INVALID_OPTION"

    def test_required_param_missing(self):
        """Test required parameter missing."""
        rules = {"period": {"type": "integer", "min": 1, "max": 500, "required": True}}
        messages = validate_param_value("period", None, rules)
        assert len(messages) == 1
        assert messages[0].code == "REQUIRED"


class TestBlockValidation:
    """Test block-level validation."""

    def test_valid_rsi_block(self):
        """Test valid RSI block."""
        result = validate_block("rsi", {"period": 14, "overbought": 70, "oversold": 30})
        assert result.valid is True
        assert len([m for m in result.messages if m.severity == ValidationSeverity.ERROR]) == 0

    def test_invalid_rsi_oversold_greater_than_overbought(self):
        """Test RSI with oversold > overbought."""
        result = validate_block("rsi", {"period": 14, "overbought": 30, "oversold": 70})
        assert result.valid is False
        assert any(m.code == "CROSS_VALIDATION" for m in result.messages)

    def test_valid_macd_block(self):
        """Test valid MACD block."""
        result = validate_block("macd_cross", {"fast_period": 12, "slow_period": 26, "signal_period": 9})
        assert result.valid is True

    def test_invalid_macd_fast_greater_than_slow(self):
        """Test MACD with fast >= slow."""
        result = validate_block("macd_cross", {"fast_period": 26, "slow_period": 12, "signal_period": 9})
        assert result.valid is False
        assert any(m.code == "CROSS_VALIDATION" for m in result.messages)

    def test_unknown_block_type_warning(self):
        """Test that unknown block type produces warning."""
        result = validate_block("nonexistent_block", {"param": 123})
        assert result.valid is True  # Still valid but with warning
        assert any(m.code == "UNKNOWN_BLOCK" for m in result.messages)


class TestConnectionValidation:
    """Test connection validation."""

    def test_valid_connection_to_entry(self):
        """Test valid connection to entry_long."""
        result = validate_connection(
            source_type="rsi",
            source_output="signal",
            target_type="entry_long",
            target_input="condition",
        )
        assert result.valid is True

    def test_valid_logic_gate_connection(self):
        """Test that logic gates accept any source."""
        result = validate_connection(
            source_type="rsi",
            source_output="signal",
            target_type="and",
            target_input="input",
        )
        assert result.valid is True

    def test_invalid_connection_type_mismatch(self):
        """Test connection with signal to value type mismatch."""
        result = validate_connection(
            source_type="rsi",
            source_output="signal",
            target_type="entry_long",
            target_input="value",
        )
        # Should produce warning about type mismatch
        assert any(m.code == "TYPE_MISMATCH" for m in result.messages)


class TestStrategyValidation:
    """Test full strategy validation."""

    def test_valid_strategy(self):
        """Test valid strategy with entry and exit."""
        blocks = [
            {"id": "1", "type": "rsi", "params": {"period": 14}},
            {"id": "2", "type": "entry_long", "params": {}},
            {"id": "3", "type": "stop_loss", "params": {"percent": 2}},
        ]
        connections = [{"source_block_id": "1", "target_block_id": "2"}]

        result = validate_strategy(blocks, connections)
        # Should be valid - has entry and exit
        assert result.valid is True or any(m.severity == ValidationSeverity.WARNING for m in result.messages)

    def test_strategy_without_entry(self):
        """Test strategy without any entry block."""
        blocks = [
            {"id": "1", "type": "rsi", "params": {"period": 14}},
            {"id": "2", "type": "stop_loss", "params": {"percent": 2}},
        ]
        connections = []

        result = validate_strategy(blocks, connections)
        assert result.valid is False
        assert any(m.code == "NO_ENTRY" for m in result.messages)

    def test_strategy_without_exit_warning(self):
        """Test strategy without exit gives warning."""
        blocks = [
            {"id": "1", "type": "rsi", "params": {"period": 14}},
            {"id": "2", "type": "entry_long", "params": {}},
        ]
        connections = []

        result = validate_strategy(blocks, connections)
        # May still be valid but should have warning about no exit
        assert any(m.code == "NO_EXIT" for m in result.messages)

    def test_strategy_with_block_validation_errors(self):
        """Test strategy where blocks have validation errors."""
        blocks = [
            {"id": "1", "type": "macd_cross", "params": {"fast_period": 30, "slow_period": 12}},  # fast > slow
            {"id": "2", "type": "entry_long", "params": {}},
            {"id": "3", "type": "stop_loss", "params": {"percent": 2}},
        ]
        connections = [{"source_block_id": "1", "target_block_id": "2"}]

        result = validate_strategy(blocks, connections)
        # Should be invalid due to MACD cross-validation error
        assert result.valid is False
        assert any(m.code == "BLOCK_ERRORS" for m in result.messages)


class TestValidationResultSerialization:
    """Test ValidationResult serialization."""

    def test_to_dict(self):
        """Test ValidationResult to_dict method."""
        from backend.api.routers.strategy_validation_ws import ValidationMessage

        result = ValidationResult(
            valid=True,
            messages=[
                ValidationMessage(severity=ValidationSeverity.INFO, message="Test message", field="test", code="TEST")
            ],
            block_id="block_1",
            param_name="period",
        )

        d = result.to_dict()

        assert d["valid"] is True
        assert len(d["messages"]) == 1
        assert d["messages"][0]["severity"] == "info"
        assert d["block_id"] == "block_1"
        assert d["param_name"] == "period"


# =============================================================================
# WebSocket Integration Tests
# =============================================================================


@pytest.fixture
def app():
    """Create test FastAPI app."""
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


class TestWebSocketEndpoint:
    """Test WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_connect(self, app):
        """Test WebSocket connection."""
        from starlette.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/strategy-builder/ws/validate") as ws:
            # Should receive welcome message
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "client_id" in data

    @pytest.mark.asyncio
    async def test_websocket_validate_param(self, app):
        """Test WebSocket param validation."""
        from starlette.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/strategy-builder/ws/validate") as ws:
            # Skip welcome message
            ws.receive_json()

            # Send validation request
            ws.send_json(
                {
                    "type": "validate_param",
                    "block_id": "test_block",
                    "block_type": "rsi",
                    "param_name": "period",
                    "param_value": 14,
                }
            )

            # Receive result
            result = ws.receive_json()
            assert result["type"] == "validation_result"
            assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_websocket_validate_block(self, app):
        """Test WebSocket block validation."""
        from starlette.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/strategy-builder/ws/validate") as ws:
            # Skip welcome message
            ws.receive_json()

            # Send validation request
            ws.send_json(
                {
                    "type": "validate_block",
                    "block_id": "test_block",
                    "block_type": "macd_cross",
                    "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
                }
            )

            # Receive result
            result = ws.receive_json()
            assert result["type"] == "validation_result"
            assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_websocket_heartbeat(self, app):
        """Test WebSocket heartbeat."""
        from starlette.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/strategy-builder/ws/validate") as ws:
            # Skip welcome message
            ws.receive_json()

            # Send heartbeat
            ws.send_json({"type": "heartbeat"})

            # Should receive heartbeat response
            result = ws.receive_json()
            assert result["type"] == "heartbeat"
            assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_websocket_invalid_json(self, app):
        """Test WebSocket handles invalid JSON."""
        from starlette.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/strategy-builder/ws/validate") as ws:
            # Skip welcome message
            ws.receive_json()

            # Send invalid JSON (raw string)
            ws.send_text("not valid json")

            # Should receive error
            result = ws.receive_json()
            assert result["type"] == "error"
            assert "Invalid JSON" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
