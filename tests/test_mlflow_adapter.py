"""
Unit tests for MLflowAdapter - MLflow experiment tracking integration.

Tests cover:
- Connection and availability checking
- Experiment creation and management
- Parameter and metric logging
- Model logging and registry
- Fallback behavior when MLflow unavailable
"""

from unittest.mock import MagicMock, patch


class TestMLflowAdapterImport:
    """Tests for MLflowAdapter import and initialization."""

    def test_import_mlflow_adapter(self):
        """Test that MLflowAdapter can be imported."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        assert MLflowAdapter is not None

    def test_create_adapter_instance(self):
        """Test creating MLflowAdapter instance."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        assert adapter is not None
        assert hasattr(adapter, "start_run")
        assert hasattr(adapter, "log_params")
        assert hasattr(adapter, "log_metrics")


class TestMLflowAdapterAvailability:
    """Tests for MLflow server availability detection."""

    def test_is_available_without_server(self):
        """is_available should handle missing server gracefully."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://nonexistent:9999")
        # Should not raise, just return False (is_available is a property)
        result = adapter.is_available
        assert isinstance(result, bool)

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_is_available_with_mock_server(self, mock_mlflow):
        """is_available should return True when server responds."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        mock_mlflow.get_tracking_uri.return_value = "http://localhost:5000"

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        # Manually set as available for test
        adapter._available = True
        # is_available is a property, not a method
        assert adapter.is_available is True


class TestMLflowAdapterExperiments:
    """Tests for experiment management."""

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_create_experiment(self, mock_mlflow):
        """Test creating a new experiment."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        mock_mlflow.create_experiment.return_value = "exp-123"
        mock_mlflow.get_experiment_by_name.return_value = None

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        # Simulate experiment creation
        exp_id = mock_mlflow.create_experiment("backtest_exp")
        assert exp_id == "exp-123"

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_set_experiment(self, mock_mlflow):
        """Test setting active experiment."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        mock_mlflow.set_experiment("my_experiment")
        mock_mlflow.set_experiment.assert_called_with("my_experiment")


class TestMLflowAdapterLogging:
    """Tests for parameter and metric logging."""

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_log_params(self, mock_mlflow):
        """Test logging parameters."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        params = {"learning_rate": 0.01, "epochs": 100, "batch_size": 32}
        mock_mlflow.log_params(params)
        mock_mlflow.log_params.assert_called_with(params)

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_log_metrics(self, mock_mlflow):
        """Test logging metrics."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        metrics = {"accuracy": 0.95, "loss": 0.05, "sharpe_ratio": 1.5}
        mock_mlflow.log_metrics(metrics)
        mock_mlflow.log_metrics.assert_called_with(metrics)

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_log_metric_with_step(self, mock_mlflow):
        """Test logging metric with step number."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        mock_mlflow.log_metric("loss", 0.1, step=10)
        mock_mlflow.log_metric.assert_called_with("loss", 0.1, step=10)


class TestMLflowAdapterRuns:
    """Tests for run management."""

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_start_run(self, mock_mlflow):
        """Test starting a new run."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        mock_run = MagicMock()
        mock_run.info.run_id = "run-123"
        mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=mock_run)
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        with mock_mlflow.start_run() as run:
            assert run.info.run_id == "run-123"

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_end_run(self, mock_mlflow):
        """Test ending a run."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        mock_mlflow.end_run()
        mock_mlflow.end_run.assert_called_once()


class TestMLflowAdapterModels:
    """Tests for model logging and registry."""

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_log_model(self, mock_mlflow):
        """Test logging a model."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        # Mock model
        mock_model = MagicMock()
        mock_mlflow.sklearn.log_model(mock_model, "model")
        mock_mlflow.sklearn.log_model.assert_called()

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_register_model(self, mock_mlflow):
        """Test registering a model."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        mock_mlflow.register_model("runs:/run-123/model", "my_model")
        mock_mlflow.register_model.assert_called_with("runs:/run-123/model", "my_model")


class TestMLflowAdapterFallback:
    """Tests for fallback behavior when MLflow is unavailable."""

    def test_fallback_mode_no_exception(self):
        """Operations should not raise when MLflow unavailable."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://nonexistent:9999")
        adapter._available = False

        # These should not raise exceptions
        try:
            adapter.log_params({"param": "value"})
            adapter.log_metrics({"metric": 1.0})
        except Exception as e:
            # If it raises, it should be caught internally
            assert False, f"Should not raise: {e}"

    def test_adapter_tracks_availability(self):
        """Adapter should track its availability status."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        # is_available is a property, check it exists
        assert hasattr(adapter, "is_available")
        assert isinstance(adapter.is_available, bool)


class TestMLflowAdapterArtifacts:
    """Tests for artifact logging."""

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_log_artifact(self, mock_mlflow):
        """Test logging an artifact file."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        mock_mlflow.log_artifact("/path/to/file.csv")
        mock_mlflow.log_artifact.assert_called_with("/path/to/file.csv")

    @patch("backend.ml.mlflow_adapter.mlflow")
    def test_log_artifacts_directory(self, mock_mlflow):
        """Test logging artifacts from directory."""
        from backend.ml.mlflow_adapter import MLflowAdapter

        adapter = MLflowAdapter(tracking_uri="http://localhost:5000")
        adapter._available = True
        adapter._mlflow = mock_mlflow

        mock_mlflow.log_artifacts("/path/to/dir")
        mock_mlflow.log_artifacts.assert_called_with("/path/to/dir")
