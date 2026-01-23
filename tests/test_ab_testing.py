"""
Tests for A/B Testing Framework

Covers:
- Experiment creation and lifecycle
- Variant allocation strategies
- Statistical analysis
- API endpoints
"""

import pytest

from backend.services.ab_testing import (
    ABExperiment,
    AllocationStrategy,
    ExperimentConfig,
    ExperimentManager,
    ExperimentStatus,
    StatisticalAnalyzer,
    Variant,
    create_strategy_ab_test,
    get_experiment_manager,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_variants():
    """Create sample variants for testing."""
    return [
        Variant(name="control", weight=0.5, config={"param": 1}, is_control=True),
        Variant(name="treatment", weight=0.5, config={"param": 2}, is_control=False),
    ]


@pytest.fixture
def sample_config(sample_variants):
    """Create sample experiment config."""
    return ExperimentConfig(
        name="Test Experiment",
        description="A test A/B experiment",
        variants=sample_variants,
        allocation_strategy=AllocationStrategy.DETERMINISTIC,
        min_samples_per_variant=10,
        confidence_level=0.95,
        primary_metric="pnl",
    )


@pytest.fixture
def experiment(sample_config):
    """Create a sample experiment."""
    return ABExperiment(sample_config)


@pytest.fixture
def experiment_manager():
    """Create a fresh experiment manager."""
    return ExperimentManager()


# ============================================================================
# Variant Tests
# ============================================================================


class TestVariant:
    """Tests for Variant class."""

    def test_variant_creation(self):
        """Test creating a variant."""
        variant = Variant(
            name="test", weight=0.5, config={"key": "value"}, is_control=True
        )

        assert variant.name == "test"
        assert variant.weight == 0.5
        assert variant.config == {"key": "value"}
        assert variant.is_control is True
        assert variant.samples == 0
        assert variant.metrics == {}

    def test_add_metric(self):
        """Test adding metrics to a variant."""
        variant = Variant(name="test", weight=0.5)

        variant.add_metric("pnl", 100.0)
        variant.add_metric("pnl", 150.0)
        variant.add_metric("win", 1.0)

        assert variant.samples == 3
        assert len(variant.metrics["pnl"]) == 2
        assert len(variant.metrics["win"]) == 1

    def test_get_metric_stats(self):
        """Test calculating metric statistics."""
        variant = Variant(name="test", weight=0.5)

        for value in [100, 150, 200, 250, 300]:
            variant.add_metric("pnl", value)

        stats = variant.get_metric_stats("pnl")

        assert stats["mean"] == 200.0
        assert stats["count"] == 5
        assert stats["min"] == 100.0
        assert stats["max"] == 300.0
        assert stats["sum"] == 1000.0

    def test_get_metric_stats_empty(self):
        """Test stats for non-existent metric."""
        variant = Variant(name="test", weight=0.5)

        stats = variant.get_metric_stats("nonexistent")

        assert stats["mean"] == 0
        assert stats["count"] == 0


# ============================================================================
# Experiment Tests
# ============================================================================


class TestABExperiment:
    """Tests for ABExperiment class."""

    def test_experiment_creation(self, experiment):
        """Test creating an experiment."""
        assert experiment.status == ExperimentStatus.DRAFT
        assert experiment.id is not None
        assert len(experiment.config.variants) == 2

    def test_experiment_validation_no_control(self, sample_variants):
        """Test that experiment requires exactly one control."""
        for v in sample_variants:
            v.is_control = False

        config = ExperimentConfig(
            name="Test",
            variants=sample_variants,
        )

        with pytest.raises(ValueError, match="exactly 1 control"):
            ABExperiment(config)

    def test_experiment_validation_insufficient_variants(self):
        """Test that experiment requires at least 2 variants."""
        config = ExperimentConfig(
            name="Test",
            variants=[Variant(name="single", is_control=True)],
        )

        with pytest.raises(ValueError, match="at least 2 variants"):
            ABExperiment(config)

    def test_experiment_start(self, experiment):
        """Test starting an experiment."""
        experiment.start()

        assert experiment.status == ExperimentStatus.RUNNING
        assert experiment.started_at is not None

    def test_experiment_pause_resume(self, experiment):
        """Test pausing and resuming an experiment."""
        experiment.start()
        experiment.pause()

        assert experiment.status == ExperimentStatus.PAUSED

        experiment.resume()

        assert experiment.status == ExperimentStatus.RUNNING

    def test_experiment_stop(self, experiment):
        """Test stopping an experiment."""
        experiment.start()
        experiment.stop()

        assert experiment.status == ExperimentStatus.COMPLETED
        assert experiment.ended_at is not None

    def test_experiment_cancel(self, experiment):
        """Test cancelling an experiment."""
        experiment.cancel()

        assert experiment.status == ExperimentStatus.CANCELLED

    def test_weight_normalization(self):
        """Test that variant weights are normalized."""
        variants = [
            Variant(name="control", weight=1, is_control=True),
            Variant(name="treatment", weight=3, is_control=False),
        ]

        config = ExperimentConfig(name="Test", variants=variants)
        experiment = ABExperiment(config)

        assert experiment.config.variants[0].weight == 0.25
        assert experiment.config.variants[1].weight == 0.75


# ============================================================================
# Allocation Tests
# ============================================================================


class TestAllocation:
    """Tests for variant allocation strategies."""

    def test_random_allocation(self, sample_config):
        """Test random allocation."""
        sample_config.allocation_strategy = AllocationStrategy.RANDOM
        experiment = ABExperiment(sample_config)
        experiment.start()

        allocations = {"control": 0, "treatment": 0}
        for _ in range(1000):
            variant = experiment.allocate()
            allocations[variant.name] += 1

        # Should be roughly 50/50 with some variance
        assert 400 < allocations["control"] < 600
        assert 400 < allocations["treatment"] < 600

    def test_deterministic_allocation(self, sample_config):
        """Test deterministic allocation is consistent."""
        sample_config.allocation_strategy = AllocationStrategy.DETERMINISTIC
        experiment = ABExperiment(sample_config)
        experiment.start()

        # Same user should always get same variant
        variant1 = experiment.allocate(user_id="user123")
        variant2 = experiment.allocate(user_id="user123")

        assert variant1.name == variant2.name

    def test_allocation_targeting_symbols(self, sample_config):
        """Test allocation respects symbol targeting."""
        sample_config.target_symbols = {"BTCUSDT", "ETHUSDT"}
        experiment = ABExperiment(sample_config)
        experiment.start()

        # Targeted symbol should get allocated
        variant = experiment.allocate(symbol="BTCUSDT")
        assert variant is not None

        # Non-targeted symbol should get control
        variant = experiment.allocate(symbol="XRPUSDT")
        assert variant.is_control is True

    def test_allocation_when_not_running(self, experiment):
        """Test allocation returns control when not running."""
        # Not started
        variant = experiment.allocate()
        assert variant.is_control is True


# ============================================================================
# Statistical Analyzer Tests
# ============================================================================


class TestStatisticalAnalyzer:
    """Tests for StatisticalAnalyzer."""

    def test_t_test(self):
        """Test t-test calculation."""
        control = [100, 110, 90, 105, 95, 100, 108, 92, 103, 97]
        treatment = [120, 130, 115, 125, 135, 128, 122, 138, 125, 130]

        t_stat, p_value = StatisticalAnalyzer.t_test(control, treatment)

        assert p_value < 0.05  # Should be significant
        assert t_stat < 0  # Treatment > Control

    def test_t_test_insufficient_samples(self):
        """Test t-test with insufficient samples."""
        t_stat, p_value = StatisticalAnalyzer.t_test([1], [2])

        assert t_stat == 0.0
        assert p_value == 1.0

    def test_effect_size(self):
        """Test Cohen's d effect size."""
        control = [100, 110, 90, 105, 95]
        treatment = [120, 130, 115, 125, 135]

        effect = StatisticalAnalyzer.calculate_effect_size(control, treatment)

        # Large effect size (> 0.8)
        assert effect > 0.8

    def test_relative_uplift(self):
        """Test relative uplift calculation."""
        uplift = StatisticalAnalyzer.calculate_relative_uplift(100, 120)

        assert uplift == 20.0  # 20% improvement

    def test_chi_squared_test(self):
        """Test chi-squared test for binary outcomes."""
        # Control: 30/100 success, Treatment: 45/100 success
        chi2, p_value = StatisticalAnalyzer.chi_squared_test(30, 100, 45, 100)

        # Should be significant
        assert p_value < 0.05


# ============================================================================
# Experiment Results Tests
# ============================================================================


class TestExperimentResults:
    """Tests for experiment results calculation."""

    def test_get_results_with_data(self, experiment):
        """Test getting results with recorded data."""
        experiment.start()

        # Record metrics for control
        for _ in range(50):
            experiment.record_metric(
                "control", "pnl", 100 + 10 * (0.5 - __import__("random").random())
            )

        # Record metrics for treatment (better)
        for _ in range(50):
            experiment.record_metric(
                "treatment", "pnl", 120 + 10 * (0.5 - __import__("random").random())
            )

        results = experiment.get_results()

        assert results.experiment_id == experiment.id
        assert results.total_samples == 100
        assert "control" in results.variant_stats
        assert "treatment" in results.variant_stats

    def test_get_results_insufficient_data(self, experiment):
        """Test results with insufficient data."""
        experiment.start()

        # Only a few samples
        experiment.record_metric("control", "pnl", 100)
        experiment.record_metric("treatment", "pnl", 120)

        results = experiment.get_results()

        assert "Insufficient samples" in results.warnings[0]


# ============================================================================
# Experiment Manager Tests
# ============================================================================


class TestExperimentManager:
    """Tests for ExperimentManager."""

    def test_create_experiment(self, experiment_manager, sample_config):
        """Test creating experiment through manager."""
        experiment = experiment_manager.create_experiment(sample_config)

        assert experiment.id in experiment_manager.experiments

    def test_start_experiment(self, experiment_manager, sample_config):
        """Test starting experiment through manager."""
        experiment = experiment_manager.create_experiment(sample_config)
        experiment_manager.start_experiment(experiment.id)

        assert experiment.status == ExperimentStatus.RUNNING

    def test_stop_experiment(self, experiment_manager, sample_config):
        """Test stopping experiment and getting results."""
        experiment = experiment_manager.create_experiment(sample_config)
        experiment_manager.start_experiment(experiment.id)

        # Record some data
        for _ in range(20):
            experiment.record_metric("control", "pnl", 100)
            experiment.record_metric("treatment", "pnl", 120)

        result = experiment_manager.stop_experiment(experiment.id)

        assert result.status == ExperimentStatus.COMPLETED

    def test_conflict_detection(self, experiment_manager):
        """Test that conflicting experiments are detected."""
        config1 = ExperimentConfig(
            name="Exp1",
            variants=[
                Variant(name="control", is_control=True),
                Variant(name="treatment", is_control=False),
            ],
            target_symbols={"BTCUSDT"},
        )

        config2 = ExperimentConfig(
            name="Exp2",
            variants=[
                Variant(name="control", is_control=True),
                Variant(name="treatment", is_control=False),
            ],
            target_symbols={"BTCUSDT"},  # Same symbol
        )

        exp1 = experiment_manager.create_experiment(config1)
        exp2 = experiment_manager.create_experiment(config2)

        experiment_manager.start_experiment(exp1.id)

        with pytest.raises(ValueError, match="already has active experiment"):
            experiment_manager.start_experiment(exp2.id)

    def test_get_variant_for_request(self, experiment_manager, sample_config):
        """Test getting variant for a trading request."""
        sample_config.target_symbols = {"BTCUSDT"}
        experiment = experiment_manager.create_experiment(sample_config)
        experiment_manager.start_experiment(experiment.id)

        exp_id, variant = experiment_manager.get_variant_for_request("BTCUSDT")

        assert exp_id == experiment.id
        assert variant is not None

    def test_record_trade_result(self, experiment_manager, sample_config):
        """Test recording trade results."""
        experiment = experiment_manager.create_experiment(sample_config)
        experiment_manager.start_experiment(experiment.id)

        experiment_manager.record_trade_result(
            experiment_id=experiment.id,
            variant_name="control",
            pnl=100.0,
            win=True,
            metrics={"sharpe": 1.5},
        )

        control = next(v for v in experiment.config.variants if v.name == "control")
        assert len(control.metrics["pnl"]) == 1
        assert len(control.metrics["win"]) == 1
        assert len(control.metrics["sharpe"]) == 1

    def test_list_experiments(self, experiment_manager, sample_config):
        """Test listing experiments."""
        experiment_manager.create_experiment(sample_config)

        config2 = ExperimentConfig(
            name="Exp2",
            variants=[
                Variant(name="control", is_control=True),
                Variant(name="treatment", is_control=False),
            ],
        )
        experiment_manager.create_experiment(config2)

        all_exps = experiment_manager.list_experiments()
        assert len(all_exps) == 2

        draft_exps = experiment_manager.list_experiments(status=ExperimentStatus.DRAFT)
        assert len(draft_exps) == 2

    def test_get_dashboard_data(self, experiment_manager, sample_config):
        """Test getting dashboard data."""
        experiment = experiment_manager.create_experiment(sample_config)
        experiment_manager.start_experiment(experiment.id)

        data = experiment_manager.get_dashboard_data(experiment.id)

        assert data["name"] == "Test Experiment"
        assert data["status"] == "running"
        assert len(data["variants"]) == 2


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestFactoryFunctions:
    """Tests for convenience factory functions."""

    def test_create_strategy_ab_test(self):
        """Test creating a strategy A/B test."""
        experiment = create_strategy_ab_test(
            name="Strategy Test",
            control_config={"sl": 0.02},
            treatment_config={"sl": 0.03},
            target_symbols=["BTCUSDT"],
            traffic_split=0.3,
        )

        assert experiment.config.name == "Strategy Test"
        assert len(experiment.config.variants) == 2

        control = next(v for v in experiment.config.variants if v.is_control)
        treatment = next(v for v in experiment.config.variants if not v.is_control)

        assert control.weight == 0.7
        assert treatment.weight == 0.3
        assert control.config == {"sl": 0.02}
        assert treatment.config == {"sl": 0.03}

    def test_get_experiment_manager_singleton(self):
        """Test that get_experiment_manager returns singleton."""
        manager1 = get_experiment_manager()
        manager2 = get_experiment_manager()

        assert manager1 is manager2


# ============================================================================
# API Tests
# ============================================================================


@pytest.mark.asyncio
class TestABTestingAPI:
    """Tests for A/B Testing API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.routers.ab_testing import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_create_experiment_endpoint(self, client):
        """Test creating experiment via API."""
        response = client.post(
            "/ab-testing/experiments",
            json={
                "name": "API Test",
                "variants": [
                    {"name": "control", "weight": 0.5, "is_control": True},
                    {"name": "treatment", "weight": 0.5, "is_control": False},
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Test"
        assert data["status"] == "draft"

    def test_quick_experiment_endpoint(self, client):
        """Test quick experiment creation."""
        response = client.post(
            "/ab-testing/experiments/quick",
            json={
                "name": "Quick Test",
                "control_config": {"param": 1},
                "treatment_config": {"param": 2},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Quick Test"

    def test_list_experiments_endpoint(self, client):
        """Test listing experiments."""
        # Create an experiment first
        client.post(
            "/ab-testing/experiments/quick",
            json={
                "name": "List Test",
                "control_config": {},
                "treatment_config": {},
            },
        )

        response = client.get("/ab-testing/experiments")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_start_experiment_endpoint(self, client):
        """Test starting an experiment."""
        # Create experiment
        create_resp = client.post(
            "/ab-testing/experiments/quick",
            json={
                "name": "Start Test",
                "control_config": {},
                "treatment_config": {},
            },
        )
        exp_id = create_resp.json()["id"]

        # Start it
        response = client.post(f"/ab-testing/experiments/{exp_id}/start")

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_record_metric_endpoint(self, client):
        """Test recording metrics."""
        # Create and start experiment
        create_resp = client.post(
            "/ab-testing/experiments/quick",
            json={
                "name": "Metric Test",
                "control_config": {},
                "treatment_config": {},
            },
        )
        exp_id = create_resp.json()["id"]
        client.post(f"/ab-testing/experiments/{exp_id}/start")

        # Record metric
        response = client.post(
            f"/ab-testing/experiments/{exp_id}/metrics",
            json={
                "variant_name": "control",
                "metric_name": "pnl",
                "value": 100.0,
            },
        )

        assert response.status_code == 200

    def test_allocate_variant_endpoint(self, client):
        """Test variant allocation endpoint."""
        # Create and start experiment with symbol targeting
        create_resp = client.post(
            "/ab-testing/experiments/quick",
            json={
                "name": "Allocate Test",
                "control_config": {},
                "treatment_config": {},
                "target_symbols": ["BTCUSDT"],
            },
        )
        exp_id = create_resp.json()["id"]
        client.post(f"/ab-testing/experiments/{exp_id}/start")

        # Get allocation
        response = client.get("/ab-testing/allocate?symbol=BTCUSDT")

        assert response.status_code == 200
        data = response.json()
        assert data["experiment_id"] == exp_id
        assert data["variant_name"] in ["control", "treatment"]
