"""
Tests for Backend Validation Rules (Session 5.5).

Tests new validation rules for:
- Close Conditions blocks (time_bars_close kept; rsi/stoch/channel/ma/psar removed)
- New Filters (RVI, extended indicators)
- Indent Order
- ATR Stop extended
"""

from backend.api.routers.strategy_validation_ws import (
    BLOCK_VALIDATION_RULES,
    ValidationSeverity,
    validate_block,
    validate_param_value,
)


class TestCloseConditionValidationRules:
    """Tests for Close Condition validation rules."""

    def test_close_channel_rules_exist(self):
        """Test Channel Close validation rules exist."""
        assert "close_channel" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_channel"]

        assert "keltner_length" in rules
        assert rules["keltner_length"]["type"] == "integer"
        assert rules["keltner_length"]["min"] == 1
        assert rules["keltner_length"]["max"] == 100

        assert "keltner_mult" in rules
        assert "bb_length" in rules
        assert "bb_deviation" in rules

    def test_close_ma_cross_rules_exist(self):
        """Test MA Cross Close validation rules exist."""
        assert "close_ma_cross" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_ma_cross"]

        assert "min_profit_percent" in rules
        assert "ma1_length" in rules
        assert rules["ma1_length"]["min"] == 1
        assert rules["ma1_length"]["max"] == 500
        assert "ma2_length" in rules

    def test_close_rsi_rules_exist(self):
        """Test RSI Close validation rules exist."""
        assert "close_rsi" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_rsi"]

        assert "rsi_close_length" in rules
        assert rules["rsi_close_length"]["min"] == 1
        assert rules["rsi_close_length"]["max"] == 200
        assert "rsi_close_min_profit" in rules
        assert "rsi_long_more" in rules
        assert "rsi_cross_long_level" in rules

    def test_close_stochastic_rules_exist(self):
        """Test Stochastic Close validation rules exist."""
        assert "close_stochastic" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_stochastic"]

        assert "stoch_close_k_length" in rules
        assert rules["stoch_close_k_length"]["min"] == 1
        assert "stoch_close_k_smoothing" in rules
        assert "stoch_close_min_profit" in rules
        assert "stoch_long_more" in rules
        assert "stoch_cross_long_level" in rules

    def test_close_psar_rules_exist(self):
        """Test PSAR Close validation rules exist."""
        assert "close_psar" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["close_psar"]

        assert "psar_start" in rules
        assert rules["psar_start"]["min"] == 0.001
        assert "psar_increment" in rules
        assert "psar_maximum" in rules
        assert "psar_close_nth_bar" in rules
        assert rules["psar_close_nth_bar"]["max"] == 100

    def test_time_bars_close_rules_exist(self):
        """Test Time/Bars close validation rules exist."""
        assert "time_bars_close" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["time_bars_close"]

        assert "close_after_bars" in rules
        assert "close_min_profit" in rules
        assert "close_max_bars" in rules


class TestNewFilterValidationRules:
    """Tests for new filter validation rules."""

    def test_rvi_filter_rules_exist(self):
        """Test RVI filter validation rules exist."""
        assert "rvi_filter" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["rvi_filter"]

        assert "rvi_length" in rules
        assert "rvi_ma_length" in rules
        assert "rvi_long_more" in rules
        assert "rvi_short_less" in rules


class TestIndentOrderValidationRules:
    """Tests for Indent Order validation rules."""

    def test_indent_order_rules_exist(self):
        """Test Indent Order validation rules exist."""
        assert "indent_order" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["indent_order"]

        assert "indent_percent" in rules
        assert rules["indent_percent"]["type"] == "number"
        assert rules["indent_percent"]["min"] == 0.01
        assert rules["indent_percent"]["max"] == 10

        assert "indent_cancel_bars" in rules


class TestATRStopExtendedRules:
    """Tests for extended ATR Stop validation rules."""

    def test_atr_stop_rules_exist(self):
        """Test ATR Stop validation rules exist."""
        assert "atr_stop" in BLOCK_VALIDATION_RULES
        rules = BLOCK_VALIDATION_RULES["atr_stop"]

        assert "atr_sl_period" in rules
        assert "atr_sl_multiplier" in rules
        assert "atr_tp_period" in rules
        assert "atr_tp_multiplier" in rules


class TestValidateBlockWithNewRules:
    """Tests for validate_block function with new rules."""

    def test_validate_indent_order_valid(self):
        """Test validating valid indent order block."""
        result = validate_block(
            "indent_order",
            {
                "indent_percent": 0.5,
                "indent_cancel_bars": 10,
            },
        )

        assert result.valid is True

    def test_validate_indent_order_invalid_percent(self):
        """Test validating indent order with invalid percent."""
        result = validate_block(
            "indent_order",
            {
                "indent_percent": 15,  # Above max of 10
            },
        )

        assert result.valid is False


class TestValidateParamValue:
    """Tests for validate_param_value function."""

    def test_integer_validation(self):
        """Test integer parameter validation."""
        rules = {"test_int": {"type": "integer", "min": 1, "max": 100}}

        # Valid value
        messages = validate_param_value("test_int", 50, rules)
        assert len([m for m in messages if m.severity == ValidationSeverity.ERROR]) == 0

        # Below min
        messages = validate_param_value("test_int", 0, rules)
        assert any(m.code == "MIN_VALUE" for m in messages)

        # Above max
        messages = validate_param_value("test_int", 150, rules)
        assert any(m.code == "MAX_VALUE" for m in messages)

    def test_number_validation(self):
        """Test number parameter validation."""
        rules = {"test_num": {"type": "number", "min": 0.1, "max": 10.0}}

        # Valid value
        messages = validate_param_value("test_num", 5.5, rules)
        assert len([m for m in messages if m.severity == ValidationSeverity.ERROR]) == 0

        # Below min
        messages = validate_param_value("test_num", 0.05, rules)
        assert any(m.code == "MIN_VALUE" for m in messages)

    def test_required_validation(self):
        """Test required parameter validation."""
        rules = {"required_param": {"type": "integer", "required": True}}

        messages = validate_param_value("required_param", None, rules)
        assert any(m.code == "REQUIRED" for m in messages)
