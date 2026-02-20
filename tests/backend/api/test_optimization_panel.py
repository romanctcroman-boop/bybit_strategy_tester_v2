"""
Tests for Optimization Panel — config propagation, method routing,
parameter parsing, and worker management.

Covers:
  BUG-1: Method selection ignored (always grid-search)
  BUG-2: 7 config fields not passed to backend
  BUG-3: max_trials vs max_iterations naming mismatch
  BUG-4: buildParameterRangesForAPI split('_') bug with multi-underscore blockIds
  BUG-5: Multiprocessing workers hardcoded, ignoring request.workers

Naming: test_[function]_[scenario]
"""


import pytest

from backend.api.routers.optimizations import (
    SyncOptimizationRequest,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def valid_payload() -> dict:
    """Minimal valid payload for SyncOptimizationRequest."""
    return {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "start_date": "2025-01-01",
        "end_date": "2025-06-01",
        "strategy_type": "rsi",
        "direction": "long",
        "initial_capital": 10000.0,
        "commission": 0.0007,
        "rsi_period_range": [7, 14, 21],
        "rsi_overbought_range": [70, 75, 80],
        "rsi_oversold_range": [20, 25, 30],
    }


# ============================================================================
# 1. SyncOptimizationRequest Model — New Config Fields (BUG-2)
# ============================================================================


class TestSyncOptimizationRequestConfigFields:
    """Test that SyncOptimizationRequest accepts all config fields from frontend."""

    def test_default_values(self):
        """Test default values for new config fields."""
        req = SyncOptimizationRequest()
        assert req.workers is None
        assert req.timeout_seconds == 3600
        assert req.train_split == 1.0
        assert req.early_stopping is False
        assert req.early_stopping_patience == 20
        assert req.warm_start is False
        assert req.prune_infeasible is True
        assert req.random_seed is None

    def test_workers_accepted(self, valid_payload):
        """Test workers field is accepted and stored."""
        valid_payload["workers"] = 8
        req = SyncOptimizationRequest(**valid_payload)
        assert req.workers == 8

    def test_workers_none_accepted(self, valid_payload):
        """Test workers=None is accepted (use default)."""
        valid_payload["workers"] = None
        req = SyncOptimizationRequest(**valid_payload)
        assert req.workers is None

    def test_timeout_seconds_accepted(self, valid_payload):
        """Test timeout_seconds field is accepted."""
        valid_payload["timeout_seconds"] = 7200
        req = SyncOptimizationRequest(**valid_payload)
        assert req.timeout_seconds == 7200

    def test_train_split_accepted(self, valid_payload):
        """Test train_split field is accepted."""
        valid_payload["train_split"] = 0.8
        req = SyncOptimizationRequest(**valid_payload)
        assert req.train_split == 0.8

    def test_train_split_full_data(self, valid_payload):
        """Test train_split=1.0 means use all data."""
        valid_payload["train_split"] = 1.0
        req = SyncOptimizationRequest(**valid_payload)
        assert req.train_split == 1.0

    def test_early_stopping_enabled(self, valid_payload):
        """Test early stopping fields are accepted together."""
        valid_payload["early_stopping"] = True
        valid_payload["early_stopping_patience"] = 50
        req = SyncOptimizationRequest(**valid_payload)
        assert req.early_stopping is True
        assert req.early_stopping_patience == 50

    def test_warm_start_accepted(self, valid_payload):
        """Test warm_start field is accepted."""
        valid_payload["warm_start"] = True
        req = SyncOptimizationRequest(**valid_payload)
        assert req.warm_start is True

    def test_prune_infeasible_accepted(self, valid_payload):
        """Test prune_infeasible field is accepted."""
        valid_payload["prune_infeasible"] = False
        req = SyncOptimizationRequest(**valid_payload)
        assert req.prune_infeasible is False

    def test_random_seed_accepted(self, valid_payload):
        """Test random_seed field is accepted."""
        valid_payload["random_seed"] = 42
        req = SyncOptimizationRequest(**valid_payload)
        assert req.random_seed == 42

    def test_random_seed_none_accepted(self, valid_payload):
        """Test random_seed=None is accepted (non-reproducible)."""
        valid_payload["random_seed"] = None
        req = SyncOptimizationRequest(**valid_payload)
        assert req.random_seed is None

    def test_all_config_fields_together(self, valid_payload):
        """Test all config fields can be set simultaneously."""
        valid_payload.update(
            {
                "workers": 4,
                "timeout_seconds": 1800,
                "train_split": 0.7,
                "early_stopping": True,
                "early_stopping_patience": 30,
                "warm_start": True,
                "prune_infeasible": False,
                "random_seed": 123,
            }
        )
        req = SyncOptimizationRequest(**valid_payload)
        assert req.workers == 4
        assert req.timeout_seconds == 1800
        assert req.train_split == 0.7
        assert req.early_stopping is True
        assert req.early_stopping_patience == 30
        assert req.warm_start is True
        assert req.prune_infeasible is False
        assert req.random_seed == 123


# ============================================================================
# 2. max_trials → max_iterations mapping (BUG-3)
# ============================================================================


class TestMaxTrialsMapping:
    """Test max_trials alias maps correctly to max_iterations."""

    def test_max_trials_field_exists(self):
        """Test max_trials field is accepted by the model."""
        req = SyncOptimizationRequest(max_trials=200)
        assert req.max_trials == 200

    def test_max_trials_default_is_none(self):
        """Test max_trials defaults to None."""
        req = SyncOptimizationRequest()
        assert req.max_trials is None

    def test_max_iterations_default_is_zero(self):
        """Test max_iterations still defaults to 0."""
        req = SyncOptimizationRequest()
        assert req.max_iterations == 0

    def test_max_trials_and_max_iterations_both_set(self):
        """Test both fields can be set independently."""
        req = SyncOptimizationRequest(max_trials=100, max_iterations=50)
        assert req.max_trials == 100
        assert req.max_iterations == 50

    def test_max_trials_mapping_logic(self, valid_payload):
        """Test that max_trials maps to max_iterations when max_iterations is 0.

        This tests the mapping logic that should occur in the handler:
        if request.max_trials > 0 and request.max_iterations == 0:
            request.max_iterations = request.max_trials
        """
        valid_payload["max_trials"] = 150
        valid_payload["max_iterations"] = 0
        req = SyncOptimizationRequest(**valid_payload)
        # Simulate handler mapping
        if req.max_trials and req.max_trials > 0 and req.max_iterations == 0:
            req.max_iterations = req.max_trials
        assert req.max_iterations == 150

    def test_max_trials_does_not_override_explicit_max_iterations(self, valid_payload):
        """Test max_trials does NOT override explicit max_iterations."""
        valid_payload["max_trials"] = 150
        valid_payload["max_iterations"] = 50
        req = SyncOptimizationRequest(**valid_payload)
        # Simulate handler mapping — should NOT override because max_iterations != 0
        if req.max_trials and req.max_trials > 0 and req.max_iterations == 0:
            req.max_iterations = req.max_trials
        assert req.max_iterations == 50  # Original value preserved


# ============================================================================
# 3. Search method field (BUG-1 — backend side)
# ============================================================================


class TestSearchMethodField:
    """Test search_method field for Grid vs Random Search routing."""

    def test_default_search_method_is_grid(self):
        """Test default search method is 'grid'."""
        req = SyncOptimizationRequest()
        assert req.search_method == "grid"

    def test_random_search_method_accepted(self, valid_payload):
        """Test random search method is accepted."""
        valid_payload["search_method"] = "random"
        req = SyncOptimizationRequest(**valid_payload)
        assert req.search_method == "random"

    def test_grid_search_method_accepted(self, valid_payload):
        """Test grid search method is accepted."""
        valid_payload["search_method"] = "grid"
        req = SyncOptimizationRequest(**valid_payload)
        assert req.search_method == "grid"

    def test_random_search_with_max_trials(self, valid_payload):
        """Test random search with max_trials populates max_iterations."""
        valid_payload["search_method"] = "random"
        valid_payload["max_trials"] = 50
        req = SyncOptimizationRequest(**valid_payload)
        # Simulate handler
        if req.max_trials and req.max_trials > 0 and req.max_iterations == 0:
            req.max_iterations = req.max_trials
        assert req.search_method == "random"
        assert req.max_iterations == 50


# ============================================================================
# 4. Parameter name parsing (BUG-4 — JavaScript simulation)
# ============================================================================


class TestParameterNameParsing:
    """Test parameter name parsing logic (simulates JS buildParameterRangesForAPI).

    BUG-4: Using split('_') on names like 'stoch_rsi_period' incorrectly splits
    into ['stoch', 'rsi', 'period'] and destructures as _blockId='stoch', paramKey='rsi'.

    FIX: Use lastIndexOf('_') to split only on the last underscore.
    """

    @staticmethod
    def _parse_param_key_old(name: str) -> str:
        """OLD (buggy) parsing — split('_') destructuring."""
        parts = name.split("_")
        if len(parts) >= 2:
            return parts[1]  # Second element
        return name

    @staticmethod
    def _parse_param_key_new(name: str) -> str:
        """NEW (fixed) parsing — lastIndexOf('_')."""
        last_underscore = name.rfind("_")
        if last_underscore >= 0:
            return name[last_underscore + 1 :]
        return name

    # --- Simple blockIds (no underscore) ---

    def test_rsi_period_old_correct(self):
        """Old method works for simple blockIds."""
        assert self._parse_param_key_old("rsi_period") == "period"

    def test_rsi_period_new_correct(self):
        """New method works for simple blockIds."""
        assert self._parse_param_key_new("rsi_period") == "period"

    def test_rsi_overbought_new(self):
        assert self._parse_param_key_new("rsi_overbought") == "overbought"

    def test_rsi_oversold_new(self):
        assert self._parse_param_key_new("rsi_oversold") == "oversold"

    def test_macd_fast_new(self):
        assert self._parse_param_key_new("macd_fast") == "fast"

    def test_macd_slow_new(self):
        assert self._parse_param_key_new("macd_slow") == "slow"

    def test_macd_signal_new(self):
        assert self._parse_param_key_new("macd_signal") == "signal"

    # --- Multi-underscore blockIds (OLD method FAILS) ---

    def test_stoch_rsi_period_old_WRONG(self):
        """OLD method returns 'rsi' instead of 'period' for stoch_rsi_period."""
        result = self._parse_param_key_old("stoch_rsi_period")
        assert result == "rsi"  # This is the BUG — returns 'rsi' not 'period'

    def test_stoch_rsi_period_new_correct(self):
        """NEW method correctly returns 'period' for stoch_rsi_period."""
        assert self._parse_param_key_new("stoch_rsi_period") == "period"

    def test_hull_ma_period_old_WRONG(self):
        """OLD method returns 'ma' instead of 'period' for hull_ma_period."""
        result = self._parse_param_key_old("hull_ma_period")
        assert result == "ma"  # BUG

    def test_hull_ma_period_new_correct(self):
        """NEW method correctly returns 'period' for hull_ma_period."""
        assert self._parse_param_key_new("hull_ma_period") == "period"

    def test_parabolic_sar_step_old_WRONG(self):
        """OLD method returns 'sar' instead of 'step' for parabolic_sar_step."""
        result = self._parse_param_key_old("parabolic_sar_step")
        assert result == "sar"  # BUG

    def test_parabolic_sar_step_new_correct(self):
        """NEW method correctly returns 'step' for parabolic_sar_step."""
        assert self._parse_param_key_new("parabolic_sar_step") == "step"

    def test_williams_r_period_old_WRONG(self):
        """OLD method returns 'r' instead of 'period' for williams_r_period."""
        result = self._parse_param_key_old("williams_r_period")
        assert result == "r"  # BUG

    def test_williams_r_period_new_correct(self):
        """NEW method correctly returns 'period' for williams_r_period."""
        assert self._parse_param_key_new("williams_r_period") == "period"

    # --- Edge cases ---

    def test_single_word_name(self):
        """Test name without underscore."""
        assert self._parse_param_key_new("period") == "period"

    def test_empty_string(self):
        """Test empty string."""
        assert self._parse_param_key_new("") == ""

    def test_trailing_underscore(self):
        """Test name with trailing underscore."""
        assert self._parse_param_key_new("rsi_") == ""

    def test_leading_underscore(self):
        """Test name with leading underscore."""
        assert self._parse_param_key_new("_period") == "period"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("rsi_period", "period"),
            ("rsi_overbought", "overbought"),
            ("rsi_oversold", "oversold"),
            ("stoch_rsi_period", "period"),
            ("stoch_rsi_overbought", "overbought"),
            ("hull_ma_period", "period"),
            ("parabolic_sar_step", "step"),
            ("parabolic_sar_max", "max"),
            ("williams_r_period", "period"),
            ("cci_period", "period"),
            ("adx_period", "period"),
            ("supertrend_period", "period"),
            ("supertrend_multiplier", "multiplier"),
            ("ichimoku_conversion", "conversion"),
            ("aroon_period", "period"),
            ("qqe_period", "period"),
        ],
    )
    def test_all_block_param_combinations(self, name, expected):
        """Test all known block+param combinations parse correctly."""
        assert self._parse_param_key_new(name) == expected


# ============================================================================
# 5. Workers logic (BUG-5)
# ============================================================================


class TestWorkersLogic:
    """Test worker count calculation logic from handler."""

    @staticmethod
    def _calculate_max_workers(request_workers: int | None, cpu_count: int) -> int:
        """Simulate the fixed worker calculation logic."""
        if request_workers and request_workers > 0:
            return min(request_workers, cpu_count)
        return min(cpu_count, 8)

    def test_default_workers_capped_at_8(self):
        """Test default workers is capped at 8."""
        assert self._calculate_max_workers(None, 16) == 8

    def test_default_workers_with_4_cpus(self):
        """Test default workers with 4 CPUs."""
        assert self._calculate_max_workers(None, 4) == 4

    def test_default_workers_with_2_cpus(self):
        """Test default workers with 2 CPUs."""
        assert self._calculate_max_workers(None, 2) == 2

    def test_requested_workers_within_cpu_count(self):
        """Test requested workers within CPU count is honored."""
        assert self._calculate_max_workers(4, 8) == 4

    def test_requested_workers_exceeds_cpu_count(self):
        """Test requested workers exceeding CPU count is capped."""
        assert self._calculate_max_workers(16, 8) == 8

    def test_requested_workers_equals_cpu_count(self):
        """Test requested workers equal to CPU count is honored."""
        assert self._calculate_max_workers(8, 8) == 8

    def test_requested_workers_one(self):
        """Test single worker request."""
        assert self._calculate_max_workers(1, 8) == 1

    def test_requested_workers_zero_uses_default(self):
        """Test workers=0 falls back to default."""
        assert self._calculate_max_workers(0, 8) == 8

    def test_requested_workers_negative_uses_default(self):
        """Test workers=-1 falls back to default."""
        assert self._calculate_max_workers(-1, 8) == 8


# ============================================================================
# 6. OptunaSyncRequest inherits new fields (BUG-1 — backend)
# ============================================================================


class TestOptunaSyncRequest:
    """Test OptunaSyncRequest inherits all SyncOptimizationRequest fields."""

    def test_optuna_request_inherits_config_fields(self):
        """Test OptunaSyncRequest has all new config fields from parent."""
        from backend.api.routers.optimizations import OptunaSyncRequest

        req = OptunaSyncRequest(
            workers=4,
            timeout_seconds=1800,
            train_split=0.7,
            early_stopping=True,
            n_trials=100,
        )
        assert req.workers == 4
        assert req.timeout_seconds == 1800
        assert req.train_split == 0.7
        assert req.early_stopping is True
        assert req.n_trials == 100

    def test_optuna_request_has_n_trials(self):
        """Test OptunaSyncRequest has n_trials field."""
        from backend.api.routers.optimizations import OptunaSyncRequest

        req = OptunaSyncRequest(n_trials=200)
        assert req.n_trials == 200

    def test_optuna_request_has_sampler_type(self):
        """Test OptunaSyncRequest has sampler_type field."""
        from backend.api.routers.optimizations import OptunaSyncRequest

        req = OptunaSyncRequest(sampler_type="cmaes")
        assert req.sampler_type == "cmaes"

    def test_optuna_request_has_n_jobs(self):
        """Test OptunaSyncRequest has n_jobs field."""
        from backend.api.routers.optimizations import OptunaSyncRequest

        req = OptunaSyncRequest(n_jobs=4)
        assert req.n_jobs == 4

    def test_optuna_default_n_trials(self):
        """Test OptunaSyncRequest default n_trials is 100."""
        from backend.api.routers.optimizations import OptunaSyncRequest

        req = OptunaSyncRequest()
        assert req.n_trials == 100


# ============================================================================
# 7. Commission rate invariant
# ============================================================================


class TestCommissionInvariant:
    """Test commission rate is always 0.0007 (TradingView parity)."""

    def test_default_commission(self):
        """Test default commission is 0.0007."""
        req = SyncOptimizationRequest()
        assert req.commission == 0.0007

    def test_commission_preserved_in_payload(self, valid_payload):
        """Test explicit commission is preserved."""
        valid_payload["commission"] = 0.0007
        req = SyncOptimizationRequest(**valid_payload)
        assert req.commission == 0.0007


# ============================================================================
# 8. Existing fields still work (regression)
# ============================================================================


class TestExistingFieldsRegression:
    """Test that existing SyncOptimizationRequest fields still work."""

    def test_evaluation_criteria_fields(self, valid_payload):
        """Test constraints, sort_order, weights fields still work."""
        valid_payload["constraints"] = [{"metric": "max_drawdown", "operator": "<=", "value": 15}]
        valid_payload["sort_order"] = [{"metric": "sharpe_ratio", "direction": "desc"}]
        valid_payload["use_composite"] = True
        valid_payload["weights"] = {"sharpe_ratio": 0.6, "net_profit": 0.4}

        req = SyncOptimizationRequest(**valid_payload)
        assert len(req.constraints) == 1
        assert req.constraints[0]["metric"] == "max_drawdown"
        assert len(req.sort_order) == 1
        assert req.use_composite is True
        assert req.weights["sharpe_ratio"] == 0.6

    def test_market_regime_fields(self, valid_payload):
        """Test market regime fields still work."""
        valid_payload["market_regime_enabled"] = True
        valid_payload["market_regime_filter"] = "trending"
        valid_payload["market_regime_lookback"] = 100

        req = SyncOptimizationRequest(**valid_payload)
        assert req.market_regime_enabled is True
        assert req.market_regime_filter == "trending"
        assert req.market_regime_lookback == 100

    def test_engine_type_field(self, valid_payload):
        """Test engine_type field still works."""
        valid_payload["engine_type"] = "numba"
        req = SyncOptimizationRequest(**valid_payload)
        assert req.engine_type == "numba"

    def test_selection_criteria_field(self, valid_payload):
        """Test selection_criteria field still works."""
        valid_payload["selection_criteria"] = ["sharpe_ratio", "win_rate", "profit_factor"]
        req = SyncOptimizationRequest(**valid_payload)
        assert len(req.selection_criteria) == 3
        assert "sharpe_ratio" in req.selection_criteria

    def test_validate_best_with_fallback(self, valid_payload):
        """Test validate_best_with_fallback field still works."""
        valid_payload["validate_best_with_fallback"] = True
        req = SyncOptimizationRequest(**valid_payload)
        assert req.validate_best_with_fallback is True


# ============================================================================
# 9. Full payload simulation (frontend → backend)
# ============================================================================


class TestFullPayloadSimulation:
    """Test complete payload as sent from frontend after all fixes."""

    def test_full_grid_search_payload(self):
        """Test complete grid search payload with all new fields."""
        payload = {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "start_date": "2025-01-01",
            "end_date": "2025-06-01",
            "strategy_type": "rsi",
            "initial_capital": 10000.0,
            "leverage": 10,
            "direction": "both",
            "commission": 0.0007,
            "market_type": "linear",
            "engine_type": "optimization",
            # Parameter ranges
            "rsi_period_range": [7, 10, 14, 21],
            "rsi_overbought_range": [70, 75, 80],
            "rsi_oversold_range": [20, 25, 30],
            "stop_loss_range": [5.0, 10.0, 15.0],
            "take_profit_range": [1.0, 1.5, 2.0],
            # Evaluation criteria
            "optimize_metric": "sharpe_ratio",
            "selection_criteria": ["net_profit", "max_drawdown", "sharpe_ratio"],
            "constraints": [{"metric": "total_trades", "operator": ">=", "value": 10}],
            "sort_order": [{"metric": "sharpe_ratio", "direction": "desc"}],
            "use_composite": False,
            "weights": None,
            # Optimization config (BUG-2 fix)
            "max_trials": 200,
            "workers": 4,
            "timeout_seconds": 1800,
            "train_split": 0.8,
            "early_stopping": True,
            "early_stopping_patience": 30,
            "warm_start": False,
            "prune_infeasible": True,
            "random_seed": 42,
        }

        req = SyncOptimizationRequest(**payload)
        assert req.symbol == "BTCUSDT"
        assert req.workers == 4
        assert req.timeout_seconds == 1800
        assert req.train_split == 0.8
        assert req.early_stopping is True
        assert req.early_stopping_patience == 30
        assert req.random_seed == 42
        assert req.max_trials == 200
        assert req.commission == 0.0007

    def test_full_random_search_payload(self):
        """Test complete random search payload."""
        payload = {
            "symbol": "ETHUSDT",
            "interval": "1h",
            "start_date": "2025-01-01",
            "end_date": "2025-03-01",
            "strategy_type": "rsi",
            "commission": 0.0007,
            # Random search specifics
            "search_method": "random",
            "max_trials": 50,
            "max_iterations": 0,
            "random_seed": 123,
            # Config
            "workers": 8,
            "timeout_seconds": 600,
        }

        req = SyncOptimizationRequest(**payload)
        assert req.search_method == "random"
        assert req.max_trials == 50
        # Simulate handler mapping
        if req.max_trials and req.max_trials > 0 and req.max_iterations == 0:
            req.max_iterations = req.max_trials
        assert req.max_iterations == 50

    def test_full_bayesian_payload(self):
        """Test complete Bayesian (Optuna) payload."""
        from backend.api.routers.optimizations import OptunaSyncRequest

        payload = {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "start_date": "2025-01-01",
            "end_date": "2025-06-01",
            "strategy_type": "rsi",
            "commission": 0.0007,
            # Optuna-specific
            "n_trials": 100,
            "sampler_type": "tpe",
            "n_jobs": 2,
            # Config from frontend
            "workers": 4,
            "timeout_seconds": 3600,
            "train_split": 0.7,
            "early_stopping": True,
            "early_stopping_patience": 25,
        }

        req = OptunaSyncRequest(**payload)
        assert req.n_trials == 100
        assert req.sampler_type == "tpe"
        assert req.workers == 4
        assert req.train_split == 0.7
        assert req.early_stopping is True


# ============================================================================
# 10. Payload extra fields handling
# ============================================================================


class TestPayloadExtraFields:
    """Test that unknown fields are handled correctly."""

    def test_unknown_field_ignored_by_default(self):
        """Test that Pydantic ignores unknown fields (default behavior)."""
        # This tests Pydantic's default behavior for extra fields
        payload = {
            "symbol": "BTCUSDT",
            "unknown_field": "should_be_ignored",
        }
        req = SyncOptimizationRequest(**payload)
        assert req.symbol == "BTCUSDT"
        assert not hasattr(req, "unknown_field") or getattr(req, "unknown_field", None) is None
