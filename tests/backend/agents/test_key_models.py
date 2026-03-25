"""
Tests for key_models.py — Canonical APIKey + APIKeyHealth.

Tests cover:
- APIKeyHealth enum states
- APIKey initialization (both calling conventions)
- Cooldown management (begin_cooldown, clear_cooldown, maybe_exit_cooldown)
- Usage tracking (mark_used, mark_error, mark_success)
- Value resolution (direct, value_override, env var)
- Health state machine (HEALTHY -> DEGRADED -> DISABLED)
- Serialization (to_dict)
- Backward compatibility (is_active, is_available, remaining_cooldown)
"""

import os
import time
from unittest.mock import patch

from backend.agents.key_models import APIKey, APIKeyHealth
from backend.agents.models import AgentType


class TestAPIKeyHealth:
    """Test APIKeyHealth enum."""

    def test_health_states_exist(self):
        """All required health states are defined."""
        assert APIKeyHealth.HEALTHY == "healthy"
        assert APIKeyHealth.DEGRADED == "degraded"
        assert APIKeyHealth.DISABLED == "disabled"

    def test_all_states_count(self):
        """Exactly 3 health states exist."""
        assert len(APIKeyHealth) == 3

    def test_is_str_enum(self):
        """APIKeyHealth values are strings."""
        for h in APIKeyHealth:
            assert isinstance(h, str)
            assert isinstance(h.value, str)


class TestAPIKeyInit:
    """Test APIKey initialization patterns."""

    def test_init_with_value_kwarg(self):
        """Initialize with explicit value=."""
        key = APIKey(value="sk-test-123", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.value == "sk-test-123"
        assert key.agent_type == AgentType.DEEPSEEK
        assert key.index == 0

    def test_init_with_value_override(self):
        """Initialize with value_override= (backward compat)."""
        key = APIKey(agent_type=AgentType.QWEN, index=1, value_override="sk-qwen-456")
        assert key.value == "sk-qwen-456"

    def test_init_env_var_fallback(self):
        """Resolve value from environment variable when not provided."""
        env_key = "DEEPSEEK_API_KEY"
        with patch.dict(os.environ, {env_key: "sk-env-789"}):
            key = APIKey(agent_type=AgentType.DEEPSEEK, index=0)
            assert key.value == "sk-env-789"

    def test_init_env_var_indexed(self):
        """Indexed key resolves from env var with index suffix."""
        env_key = "DEEPSEEK_API_KEY_3"
        with patch.dict(os.environ, {env_key: "sk-env-idx3"}):
            key = APIKey(agent_type=AgentType.DEEPSEEK, index=2)
            assert key.value == "sk-env-idx3"

    def test_init_defaults(self):
        """Default state is clean."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.health == APIKeyHealth.HEALTHY
        assert key.error_count == 0
        assert key.requests_count == 0
        assert key.cooldown_until is None
        assert key.cooldown_level == 0
        assert key.cooling_events == 0

    def test_init_auto_generates_key_name(self):
        """key_name is auto-generated when value not provided."""
        key = APIKey(agent_type=AgentType.DEEPSEEK, index=0)
        assert key.key_name == "DS-1"

        key2 = APIKey(agent_type=AgentType.QWEN, index=2)
        assert key2.key_name == "QW-3"

        key3 = APIKey(agent_type=AgentType.PERPLEXITY, index=4)
        assert key3.key_name == "PP-5"

    def test_init_with_explicit_key_name(self):
        """Explicit key_name is respected."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0, key_name="MY-KEY")
        assert key.key_name == "MY-KEY"

    def test_value_override_precedence(self):
        """value= takes precedence over value_override=."""
        key = APIKey(
            value="sk-primary",
            value_override="sk-fallback",
            agent_type=AgentType.DEEPSEEK,
            index=0,
        )
        assert key.value == "sk-primary"


class TestAPIKeyCooldown:
    """Test cooldown management."""

    def test_begin_cooldown(self):
        """begin_cooldown() sets future timestamp."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        duration = key.begin_cooldown(60, reason="rate_limit")
        assert duration == 60
        assert key.cooldown_until is not None
        assert key.cooldown_until > time.time()
        assert key.cooling_events == 1
        assert key.cooldown_level == 1

    def test_is_cooling_true(self):
        """is_cooling returns True during cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(60)
        assert key.is_cooling is True

    def test_is_cooling_false_after_expiry(self):
        """is_cooling returns False after cooldown expires."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(0.01)
        time.sleep(0.02)
        assert key.is_cooling is False

    def test_clear_cooldown(self):
        """clear_cooldown() removes cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(60)
        key.clear_cooldown()
        assert key.cooldown_until is None
        assert key.is_cooling is False

    def test_cooldown_remaining_seconds(self):
        """cooldown_remaining returns positive value during cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(60)
        assert 0 < key.cooldown_remaining <= 60

    def test_cooldown_remaining_zero_when_no_cooldown(self):
        """cooldown_remaining returns 0 when not cooling."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.cooldown_remaining == 0

    def test_remaining_cooldown_alias(self):
        """remaining_cooldown is alias for cooldown_remaining."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(30)
        # Both call time.time() independently, so allow tiny difference
        assert abs(key.remaining_cooldown - key.cooldown_remaining) < 0.01

    def test_begin_cooldown_negative_clamps_to_zero(self):
        """Negative duration clamped to 0."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        duration = key.begin_cooldown(-10)
        assert duration == 0

    def test_cooldown_level_increments(self):
        """Multiple cooldowns increment level."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(10)
        key.begin_cooldown(10)
        key.begin_cooldown(10)
        assert key.cooldown_level == 3
        assert key.cooling_events == 3

    def test_cooldown_level_capped_at_10(self):
        """Cooldown level is capped at 10."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        for _ in range(15):
            key.begin_cooldown(1)
        assert key.cooldown_level == 10


class TestAPIKeyUsability:
    """Test is_usable, is_available, status properties."""

    def test_is_usable_healthy_key(self):
        """Healthy key is usable."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.is_usable is True

    def test_is_usable_during_cooldown(self):
        """Cooling key is not usable."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(60)
        assert key.is_usable is False

    def test_is_usable_disabled_key(self):
        """Disabled key is not usable."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.health = APIKeyHealth.DISABLED
        assert key.is_usable is False

    def test_is_usable_degraded_key_no_cooldown(self):
        """Degraded key without cooldown IS usable."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.health = APIKeyHealth.DEGRADED
        assert key.is_usable is True

    def test_is_available_alias(self):
        """is_available matches is_usable."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.is_available == key.is_usable

    def test_is_active_backward_compat(self):
        """is_active is backward compatible alias."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.is_active is True

    def test_is_active_setter_disable(self):
        """Setting is_active=False disables the key."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.is_active = False
        assert key.health == APIKeyHealth.DISABLED
        assert key.is_usable is False

    def test_is_active_setter_enable(self):
        """Setting is_active=True re-enables the key."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.health = APIKeyHealth.DISABLED
        key.is_active = True
        assert key.health == APIKeyHealth.HEALTHY
        assert key.is_usable is True

    def test_status_property(self):
        """Status returns human-readable string."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        assert key.status == "healthy"

        key.begin_cooldown(60)
        assert key.status == "cooling"

        key.clear_cooldown()
        key.health = APIKeyHealth.DISABLED
        assert key.status == "disabled"


class TestAPIKeyUsageTracking:
    """Test mark_used, mark_error, mark_success."""

    def test_mark_used(self):
        """mark_used() updates usage stats."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.mark_used()
        assert key.requests_count == 1
        assert key.last_used is not None
        assert key.last_used <= time.time()

    def test_mark_used_increments(self):
        """Multiple mark_used() calls increment count."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.mark_used()
        key.mark_used()
        key.mark_used()
        assert key.requests_count == 3

    def test_mark_error_increments(self):
        """mark_error() increments error count."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.mark_error("test error")
        assert key.error_count == 1
        assert key.last_cooldown_reason == "test error"
        assert key.last_error_time is not None

    def test_mark_error_degrades_health(self):
        """5+ errors -> DEGRADED, 10+ errors -> DISABLED."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        for i in range(5):
            key.mark_error(f"err{i}")
        assert key.health == APIKeyHealth.DEGRADED

        for i in range(5, 10):
            key.mark_error(f"err{i}")
        assert key.health == APIKeyHealth.DISABLED

    def test_mark_error_triggers_cooldown(self):
        """mark_error() triggers automatic cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.mark_error("err")
        assert key.is_cooling is True
        assert key.cooling_events == 1

    def test_mark_error_exponential_backoff(self):
        """Cooldown times increase: 30, 60, 120, 300, 600."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        expected_cooldowns = [30, 60, 120, 300, 600]
        for i in range(5):
            before = time.time()
            key.mark_error(f"err{i}")
            expected_until = before + expected_cooldowns[i]
            # Allow 1s tolerance
            assert abs(key.cooldown_until - expected_until) < 1.0

    def test_mark_success_reduces_errors(self):
        """mark_success() decrements error count."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.error_count = 3
        key.mark_success()
        assert key.error_count == 2

    def test_mark_success_heals_degraded(self):
        """mark_success() restores DEGRADED to HEALTHY when errors < 3."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.health = APIKeyHealth.DEGRADED
        key.error_count = 2
        key.mark_success()
        assert key.error_count == 1
        assert key.health == APIKeyHealth.HEALTHY

    def test_mark_success_reduces_cooldown_level(self):
        """mark_success() decrements cooldown_level."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.cooldown_level = 3
        key.mark_success()
        assert key.cooldown_level == 2


class TestAPIKeyReset:
    """Test reset functionality."""

    def test_reset_clears_all_state(self):
        """reset() restores key to initial state."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.mark_used()
        key.mark_error("oops")
        key.begin_cooldown(60)

        key.reset()

        assert key.health == APIKeyHealth.HEALTHY
        assert key.error_count == 0
        assert key.cooldown_until is None
        assert key.cooldown_level == 0
        assert key.last_cooldown_reason is None


class TestAPIKeySerialization:
    """Test to_dict()."""

    def test_to_dict_contains_required_fields(self):
        """to_dict() includes all required fields."""
        key = APIKey(value="sk-test-123", agent_type=AgentType.DEEPSEEK, index=0)
        d = key.to_dict()

        assert d["agent_type"] == "deepseek"
        assert d["index"] == 0
        assert d["health"] == "healthy"
        assert d["error_count"] == 0
        assert d["requests_count"] == 0
        assert d["is_available"] is True
        assert d["remaining_cooldown"] == 0
        assert d["status"] == "healthy"
        assert "key_name" in d

    def test_to_dict_reflects_state_changes(self):
        """to_dict() reflects current state after modifications."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.mark_used()
        key.mark_error("err")

        d = key.to_dict()
        assert d["error_count"] == 1
        assert d["requests_count"] == 1
        assert d["last_error"] == "err"


class TestAPIKeyMaybeExitCooldown:
    """Test maybe_exit_cooldown()."""

    def test_exits_cooldown_when_expired(self):
        """maybe_exit_cooldown() clears expired cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(0.01)
        time.sleep(0.02)
        result = key.maybe_exit_cooldown()
        assert result is True
        assert key.cooldown_until is None

    def test_stays_in_cooldown_when_active(self):
        """maybe_exit_cooldown() keeps active cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        key.begin_cooldown(60)
        result = key.maybe_exit_cooldown()
        assert result is False
        assert key.cooldown_until is not None
        assert key.is_cooling is True

    def test_returns_false_when_no_cooldown(self):
        """maybe_exit_cooldown() returns False when not in cooldown."""
        key = APIKey(value="sk-test", agent_type=AgentType.DEEPSEEK, index=0)
        result = key.maybe_exit_cooldown()
        assert result is False
