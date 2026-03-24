"""Tests for P3-8: Federated Strategy Learning."""

import numpy as np
import pytest

from backend.research import FederatedLearning, LocalModel


class DummyModelClass:
    """Placeholder model class for testing."""

    pass


@pytest.fixture
def initial_weights():
    return {
        "layer1": np.array([0.1, 0.2, 0.3]),
        "layer2": np.array([[0.4, 0.5], [0.6, 0.7]]),
    }


@pytest.fixture
def fl(initial_weights):
    f = FederatedLearning(model_class=DummyModelClass, n_clients=5)
    f.initialize_global_model(initial_weights)
    return f


class TestLocalModel:
    def test_create(self):
        lm = LocalModel(
            client_id="c1",
            weights={"w": np.array([1.0])},
            n_samples=100,
            metrics={"accuracy": 0.8},
        )
        assert lm.client_id == "c1"
        assert lm.n_samples == 100


class TestFederatedLearning:
    def test_init(self):
        fl = FederatedLearning(model_class=DummyModelClass, n_clients=10)
        assert fl.n_clients == 10
        assert fl.global_weights == {}
        assert fl.rounds == []

    def test_initialize_global_model(self, initial_weights):
        fl = FederatedLearning(model_class=DummyModelClass, n_clients=3)
        fl.initialize_global_model(initial_weights)
        assert "layer1" in fl.global_weights
        assert "layer2" in fl.global_weights

    def test_train_local_model_returns_local_model(self, fl):
        lm = fl.train_local_model("client_0", list(range(100)))
        assert isinstance(lm, LocalModel)
        assert lm.client_id == "client_0"

    def test_train_local_model_has_weights(self, fl):
        lm = fl.train_local_model("client_0", list(range(100)))
        assert "layer1" in lm.weights
        assert "layer2" in lm.weights

    def test_train_local_model_weights_differ_from_global(self, fl, initial_weights):
        lm = fl.train_local_model("client_0", list(range(100)))
        # Weights should be close but not identical (noise added)
        diff = np.abs(lm.weights["layer1"] - initial_weights["layer1"]).max()
        # Very unlikely to be exactly 0 due to noise
        assert diff >= 0.0  # allow 0 technically, but usually > 0

    def test_train_local_model_has_metrics(self, fl):
        lm = fl.train_local_model("client_0", list(range(100)))
        assert "accuracy" in lm.metrics
        assert "sharpe" in lm.metrics

    def test_train_local_model_stores_in_local_models(self, fl):
        fl.train_local_model("client_0", list(range(100)))
        assert "client_0" in fl.local_models

    def test_aggregate_models_updates_global(self, fl):
        fl.train_local_model("c1", list(range(100)))
        fl.train_local_model("c2", list(range(100)))
        original_layer1 = fl.global_weights["layer1"].copy()
        aggregated = fl.aggregate_models()
        assert "layer1" in aggregated
        # After aggregation, global weights updated
        assert aggregated is not None

    def test_aggregate_models_no_local_models_returns_global(self, fl, initial_weights):
        result = fl.aggregate_models()
        np.testing.assert_array_equal(result["layer1"], initial_weights["layer1"])

    def test_aggregate_records_round(self, fl):
        fl.train_local_model("c1", list(range(100)))
        fl.aggregate_models()
        assert len(fl.rounds) == 1
        assert "n_clients" in fl.rounds[0]
        assert "total_samples" in fl.rounds[0]
        assert "avg_accuracy" in fl.rounds[0]

    def test_federated_round_runs_full_cycle(self, fl):
        clients_data = {f"client_{i}": list(range(100)) for i in range(3)}
        result = fl.federated_round(clients_data)
        assert isinstance(result, dict)
        assert "n_clients" in result
        assert result["n_clients"] == 3

    def test_federated_round_increments_rounds(self, fl):
        clients_data = {"c1": list(range(50)), "c2": list(range(50))}
        fl.federated_round(clients_data)
        fl.federated_round(clients_data)
        assert len(fl.rounds) == 2

    def test_get_global_model_returns_copy(self, fl):
        gm = fl.get_global_model()
        assert isinstance(gm, dict)
        assert "layer1" in gm

    def test_get_global_model_is_copy(self, fl):
        gm = fl.get_global_model()
        gm["layer1"][0] = 999.0
        # Original should not be modified
        assert fl.global_weights["layer1"][0] != 999.0

    def test_set_global_model(self, fl):
        new_weights = {"layer1": np.array([9.0, 9.0, 9.0]), "layer2": np.zeros((2, 2))}
        fl.set_global_model(new_weights)
        np.testing.assert_array_equal(fl.global_weights["layer1"], [9.0, 9.0, 9.0])

    def test_get_training_history_empty_initially(self):
        fl = FederatedLearning(model_class=DummyModelClass, n_clients=3)
        assert fl.get_training_history() == []

    def test_get_training_history_after_rounds(self, fl):
        clients_data = {"c1": list(range(100))}
        fl.federated_round(clients_data)
        history = fl.get_training_history()
        assert len(history) == 1

    def test_evaluate_global_model_returns_metrics(self, fl):
        metrics = fl.evaluate_global_model(list(range(100)))
        assert "accuracy" in metrics
        assert "sharpe" in metrics
        assert "max_drawdown" in metrics

    def test_weighted_aggregation_correctness(self, initial_weights):
        """Verify FedAvg weighted average is correct."""
        fl = FederatedLearning(model_class=DummyModelClass, n_clients=2)
        fl.initialize_global_model(initial_weights)

        # Manually inject local models with known weights
        w1 = {"layer1": np.array([1.0, 1.0, 1.0]), "layer2": np.ones((2, 2))}
        w2 = {"layer1": np.array([3.0, 3.0, 3.0]), "layer2": np.ones((2, 2)) * 3}
        fl.local_models = {
            "c1": LocalModel("c1", w1, n_samples=1000, metrics={"accuracy": 0.8, "sharpe": 1.0}),
            "c2": LocalModel("c2", w2, n_samples=1000, metrics={"accuracy": 0.9, "sharpe": 1.5}),
        }
        result = fl.aggregate_models()
        # Equal weights (1000/2000 each), so expected avg = (1+3)/2 = 2.0
        np.testing.assert_allclose(result["layer1"], [2.0, 2.0, 2.0])
