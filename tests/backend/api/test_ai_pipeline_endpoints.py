"""
Tests for AI Pipeline API endpoints.

Tests cover all 6 endpoints in /ai-pipeline/:
- POST /generate — strategy generation
- GET /agents — list agents
- POST /analyze-market — market context analysis
- POST /improve-strategy — walk-forward optimization
- GET /pipeline/{id}/status — pipeline job status
- GET /pipeline/{id}/result — pipeline job result
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.ai_pipeline import (
    AnalyzeMarketRequest,
    GenerateRequest,
    ImproveStrategyRequest,
    PipelineResponse,
    _pipeline_jobs,
    router,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with the AI pipeline router."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """HTTP test client for the AI pipeline router."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_jobs():
    """Clear in-memory pipeline jobs before each test."""
    _pipeline_jobs.clear()
    yield
    _pipeline_jobs.clear()


def _recent_ts(minutes_ago: int = 0) -> str:
    """Generate a recent ISO timestamp that survives TTL eviction (1h max)."""
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Minimal OHLCV DataFrame for mocks."""
    import numpy as np

    np.random.seed(42)
    n = 100
    base = 50000.0
    returns = np.random.randn(n) * 0.002
    prices = base * np.cumprod(1 + returns)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
            "open": prices * (1 + np.random.randn(n) * 0.001),
            "high": prices * (1 + abs(np.random.randn(n)) * 0.002),
            "low": prices * (1 - abs(np.random.randn(n)) * 0.002),
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        }
    )


@pytest.fixture
def mock_pipeline_result() -> dict[str, Any]:
    """Mock PipelineResult from StrategyController."""
    mock = MagicMock()
    mock.success = True
    mock.strategy = MagicMock()
    mock.strategy.strategy_name = "RSI Trend"
    mock.strategy.get_strategy_type_for_engine.return_value = "rsi"
    mock.strategy.get_engine_params.return_value = {"period": 14, "overbought": 70, "oversold": 30}
    mock.strategy.description = "RSI-based strategy"
    mock.strategy.signals = [MagicMock()]
    mock.strategy.agent_metadata = MagicMock()
    mock.strategy.agent_metadata.agent_name = "deepseek"
    mock.validation = MagicMock()
    mock.validation.quality_score = 0.85
    mock.backtest_metrics = {"total_return_pct": 5.0, "sharpe_ratio": 1.2}
    mock.walk_forward = {}
    mock.proposals = [MagicMock()]
    mock.consensus_summary = "Selected RSI strategy"
    mock.stages = [
        MagicMock(stage=MagicMock(value="context_analysis"), success=True, duration_ms=120.5, error=None),
        MagicMock(stage=MagicMock(value="strategy_generation"), success=True, duration_ms=3500.0, error=None),
    ]
    mock.total_duration_ms = 3620.5
    mock.timestamp = datetime(2025, 6, 1, 12, 0, 0)
    mock.final_stage = MagicMock(value="evaluation")
    return mock


# =============================================================================
# POST /generate TESTS
# =============================================================================


class TestGenerateEndpoint:
    """Tests for POST /ai-pipeline/generate."""

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.strategy_controller.StrategyController.generate_strategy")
    def test_generate_success(self, mock_gen, mock_load, client, sample_ohlcv, mock_pipeline_result):
        """Successful strategy generation returns PipelineResponse."""
        mock_load.return_value = sample_ohlcv
        mock_gen.return_value = mock_pipeline_result

        response = client.post(
            "/ai-pipeline/generate",
            json={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "agents": ["deepseek"],
                "run_backtest": False,
                "enable_walk_forward": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["pipeline_id"] != ""
        assert data["strategy"]["strategy_name"] == "RSI Trend"
        assert data["strategy"]["strategy_type"] == "rsi"
        assert data["proposals_count"] == 1

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.strategy_controller.StrategyController.generate_strategy")
    def test_generate_stores_job(self, mock_gen, mock_load, client, sample_ohlcv, mock_pipeline_result):
        """Pipeline job is stored for later retrieval."""
        mock_load.return_value = sample_ohlcv
        mock_gen.return_value = mock_pipeline_result

        response = client.post(
            "/ai-pipeline/generate",
            json={"symbol": "BTCUSDT", "timeframe": "15"},
        )

        data = response.json()
        pipeline_id = data["pipeline_id"]
        assert pipeline_id in _pipeline_jobs
        assert _pipeline_jobs[pipeline_id]["status"] == "completed"

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    def test_generate_no_data_returns_400(self, mock_load, client):
        """Missing OHLCV data returns 400."""
        mock_load.side_effect = ValueError("No OHLCV data for XYZUSDT")

        response = client.post(
            "/ai-pipeline/generate",
            json={"symbol": "XYZUSDT", "timeframe": "15"},
        )

        assert response.status_code == 400
        assert "No OHLCV data" in response.json()["detail"]

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.strategy_controller.StrategyController.generate_strategy")
    def test_generate_internal_error_returns_500(self, mock_gen, mock_load, client, sample_ohlcv):
        """Internal pipeline failure returns 500."""
        mock_load.return_value = sample_ohlcv
        mock_gen.side_effect = RuntimeError("LLM timeout")

        response = client.post(
            "/ai-pipeline/generate",
            json={"symbol": "BTCUSDT", "timeframe": "15"},
        )

        assert response.status_code == 500
        assert "Pipeline failed" in response.json()["detail"]

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.strategy_controller.StrategyController.generate_strategy")
    def test_generate_with_walk_forward(self, mock_gen, mock_load, client, sample_ohlcv, mock_pipeline_result):
        """Enable walk-forward flag is passed to controller."""
        mock_load.return_value = sample_ohlcv
        mock_pipeline_result.walk_forward = {"overfit_score": 0.2, "confidence_level": "high"}
        mock_gen.return_value = mock_pipeline_result

        response = client.post(
            "/ai-pipeline/generate",
            json={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "enable_walk_forward": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "walk_forward" in data
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs.get("enable_walk_forward") is True

    def test_generate_request_model_defaults(self):
        """GenerateRequest has correct defaults."""
        req = GenerateRequest()
        assert req.symbol == "BTCUSDT"
        assert req.timeframe == "15"
        assert req.agents == ["deepseek"]
        assert req.run_backtest is False
        assert req.enable_walk_forward is False
        assert req.initial_capital == 10000
        assert req.leverage == 1


# =============================================================================
# GET /agents TESTS
# =============================================================================


class TestAgentsEndpoint:
    """Tests for GET /ai-pipeline/agents."""

    @patch("backend.api.routers.ai_pipeline._check_agent_available")
    def test_list_agents_returns_three(self, mock_check, client):
        """Returns exactly 3 agents."""
        mock_check.return_value = True

        response = client.get("/ai-pipeline/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3
        names = [a["name"] for a in agents]
        assert "deepseek" in names
        assert "qwen" in names
        assert "perplexity" in names

    @patch("backend.api.routers.ai_pipeline._check_agent_available")
    def test_agents_availability_check(self, mock_check, client):
        """Agent availability reflects key check."""
        mock_check.side_effect = lambda name: name == "deepseek"

        response = client.get("/ai-pipeline/agents")

        agents = {a["name"]: a["available"] for a in response.json()}
        assert agents["deepseek"] is True
        assert agents["qwen"] is False
        assert agents["perplexity"] is False

    @patch("backend.api.routers.ai_pipeline._check_agent_available")
    def test_agents_have_specialization(self, mock_check, client):
        """Each agent has a specialization field."""
        mock_check.return_value = False

        response = client.get("/ai-pipeline/agents")

        for agent in response.json():
            assert "specialization" in agent
            assert len(agent["specialization"]) > 0


# =============================================================================
# POST /analyze-market TESTS
# =============================================================================


class TestAnalyzeMarketEndpoint:
    """Tests for POST /ai-pipeline/analyze-market."""

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.prompts.context_builder.MarketContextBuilder.build_context")
    def test_analyze_market_success(self, mock_ctx, mock_load, client, sample_ohlcv):
        """Successful market analysis returns structured response."""
        mock_load.return_value = sample_ohlcv

        # Mock context object with real MarketContext fields
        mock_context = MagicMock()
        mock_context.market_regime = "trending_up"
        mock_context.trend_direction = "bullish"
        mock_context.atr_pct = 1.5  # medium volatility (1-3%)
        mock_context.support_levels = [48000.0, 47000.0]
        mock_context.resistance_levels = [52000.0, 53000.0]
        mock_context.indicators_summary = "Bullish trend with medium volatility"
        mock_ctx.return_value = mock_context

        response = client.post(
            "/ai-pipeline/analyze-market",
            json={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "start_date": "2025-01-01",
                "end_date": "2025-03-01",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["market_regime"] == "trending_up"
        assert data["trend_direction"] == "bullish"
        assert data["volatility_level"] == "medium"
        assert data["context_summary"] == "Bullish trend with medium volatility"
        assert data["candles_analyzed"] == len(sample_ohlcv)

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    def test_analyze_market_no_data(self, mock_load, client):
        """No data returns 400."""
        mock_load.side_effect = ValueError("No OHLCV data")

        response = client.post(
            "/ai-pipeline/analyze-market",
            json={"symbol": "NONEUSDT", "timeframe": "15"},
        )

        assert response.status_code == 400

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.prompts.context_builder.MarketContextBuilder.build_context")
    def test_analyze_market_context_error(self, mock_ctx, mock_load, client, sample_ohlcv):
        """Context builder error returns 500."""
        mock_load.return_value = sample_ohlcv
        mock_ctx.side_effect = RuntimeError("Context build failed")

        response = client.post(
            "/ai-pipeline/analyze-market",
            json={"symbol": "BTCUSDT", "timeframe": "15"},
        )

        assert response.status_code == 500

    def test_analyze_market_request_model(self):
        """AnalyzeMarketRequest has correct defaults."""
        req = AnalyzeMarketRequest()
        assert req.symbol == "BTCUSDT"
        assert req.timeframe == "15"


# =============================================================================
# POST /improve-strategy TESTS
# =============================================================================


class TestImproveStrategyEndpoint:
    """Tests for POST /ai-pipeline/improve-strategy."""

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.integration.walk_forward_bridge.WalkForwardBridge.run_walk_forward_async")
    def test_improve_strategy_success(self, mock_wf, mock_load, client, sample_ohlcv):
        """Successful walk-forward optimization."""
        mock_load.return_value = sample_ohlcv

        # Mock WalkForwardResult
        mock_result = MagicMock()
        mock_result.recommended_params = {"period": 21, "overbought": 75, "oversold": 25}
        mock_result.confidence_level = "high"
        mock_result.overfit_score = 0.15
        mock_result.consistency_ratio = 0.85
        mock_result.parameter_stability = 0.9
        mock_result.to_dict.return_value = {"config": {}, "windows": [], "robustness": {}}
        mock_wf.return_value = mock_result

        response = client.post(
            "/ai-pipeline/improve-strategy",
            json={
                "symbol": "BTCUSDT",
                "timeframe": "15",
                "strategy_type": "rsi",
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
                "wf_splits": 5,
                "optimization_metric": "sharpe",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["recommended_params"]["period"] == 21
        assert data["confidence_level"] == "high"
        assert data["overfit_score"] == pytest.approx(0.15)
        assert data["original_params"]["period"] == 14

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    def test_improve_strategy_no_data(self, mock_load, client):
        """Missing data returns 400."""
        mock_load.side_effect = ValueError("No OHLCV data")

        response = client.post(
            "/ai-pipeline/improve-strategy",
            json={
                "strategy_type": "rsi",
                "strategy_params": {"period": 14},
            },
        )

        assert response.status_code == 400

    @patch("backend.api.routers.ai_pipeline._load_ohlcv_data")
    @patch("backend.agents.integration.walk_forward_bridge.WalkForwardBridge.run_walk_forward_async")
    def test_improve_strategy_wf_error(self, mock_wf, mock_load, client, sample_ohlcv):
        """Walk-forward failure returns 500."""
        mock_load.return_value = sample_ohlcv
        mock_wf.side_effect = RuntimeError("WF optimization failed")

        response = client.post(
            "/ai-pipeline/improve-strategy",
            json={
                "strategy_type": "macd",
                "strategy_params": {"fast": 12, "slow": 26},
            },
        )

        assert response.status_code == 500

    def test_improve_strategy_request_model(self):
        """ImproveStrategyRequest has correct defaults."""
        req = ImproveStrategyRequest(strategy_type="rsi")
        assert req.symbol == "BTCUSDT"
        assert req.timeframe == "15"
        assert req.wf_splits == 5
        assert req.wf_train_ratio == 0.7
        assert req.optimization_metric == "sharpe"
        assert req.initial_capital == 10000
        assert req.direction == "both"


# =============================================================================
# GET /pipeline/{id}/status TESTS
# =============================================================================


class TestPipelineStatusEndpoint:
    """Tests for GET /ai-pipeline/pipeline/{id}/status."""

    def test_status_not_found(self, client):
        """Unknown pipeline ID returns 404."""
        response = client.get("/ai-pipeline/pipeline/nonexistent/status")
        assert response.status_code == 404

    def test_status_running(self, client):
        """Running job returns status with progress."""
        _pipeline_jobs["job-123"] = {
            "status": "running",
            "created_at": _recent_ts(),
            "current_stage": "strategy_generation",
        }

        response = client.get("/ai-pipeline/pipeline/job-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "job-123"
        assert data["status"] == "running"
        assert data["progress_pct"] == 40  # strategy_generation = 40%
        assert data["current_stage"] == "strategy_generation"

    def test_status_completed(self, client):
        """Completed job shows 100% progress."""
        created = _recent_ts(5)
        completed = _recent_ts(0)
        _pipeline_jobs["job-456"] = {
            "status": "completed",
            "created_at": created,
            "completed_at": completed,
            "current_stage": "complete",
        }

        response = client.get("/ai-pipeline/pipeline/job-456/status")

        data = response.json()
        assert data["status"] == "completed"
        assert data["progress_pct"] == 100
        assert data["completed_at"] == completed

    def test_status_walk_forward_stage(self, client):
        """Walk-forward stage shows 95% progress."""
        _pipeline_jobs["job-wf"] = {
            "status": "running",
            "created_at": _recent_ts(),
            "current_stage": "walk_forward",
        }

        response = client.get("/ai-pipeline/pipeline/job-wf/status")

        data = response.json()
        assert data["progress_pct"] == 95


# =============================================================================
# GET /pipeline/{id}/result TESTS
# =============================================================================


class TestPipelineResultEndpoint:
    """Tests for GET /ai-pipeline/pipeline/{id}/result."""

    def test_result_not_found(self, client):
        """Unknown pipeline ID returns 404."""
        response = client.get("/ai-pipeline/pipeline/nonexistent/result")
        assert response.status_code == 404

    def test_result_still_running(self, client):
        """Running job returns 400."""
        _pipeline_jobs["job-run"] = {
            "status": "running",
            "created_at": _recent_ts(),
            "current_stage": "strategy_generation",
        }

        response = client.get("/ai-pipeline/pipeline/job-run/result")

        assert response.status_code == 400
        assert "still running" in response.json()["detail"]

    def test_result_completed(self, client):
        """Completed job returns full result."""
        created = _recent_ts(5)
        completed = _recent_ts(0)
        _pipeline_jobs["job-done"] = {
            "status": "completed",
            "created_at": created,
            "completed_at": completed,
            "current_stage": "evaluation",
            "result": {
                "success": True,
                "pipeline_id": "job-done",
                "strategy": {
                    "strategy_name": "RSI Basic",
                    "strategy_type": "rsi",
                    "strategy_params": {"period": 14},
                    "description": "Simple RSI strategy",
                },
                "backtest_metrics": {"total_return_pct": 3.5},
                "walk_forward": {},
                "proposals_count": 1,
                "consensus_summary": "Selected RSI",
                "stages": [],
                "total_duration_ms": 5000.0,
                "timestamp": completed,
            },
        }

        response = client.get("/ai-pipeline/pipeline/job-done/result")

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "job-done"
        assert data["status"] == "completed"
        assert data["result"]["success"] is True
        assert data["result"]["strategy"]["strategy_name"] == "RSI Basic"

    def test_result_failed_job(self, client):
        """Failed job returns result with error."""
        _pipeline_jobs["job-fail"] = {
            "status": "failed",
            "created_at": _recent_ts(),
            "error": "LLM API timeout",
        }

        response = client.get("/ai-pipeline/pipeline/job-fail/result")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "LLM API timeout"


# =============================================================================
# RESPONSE MODEL TESTS
# =============================================================================


class TestResponseModels:
    """Test Pydantic response models."""

    def test_pipeline_response_model(self):
        """PipelineResponse creates with defaults."""
        resp = PipelineResponse(success=True, pipeline_id="test-123")
        assert resp.success is True
        assert resp.strategy is None
        assert resp.backtest_metrics == {}
        assert resp.walk_forward == {}
        assert resp.stages == []

    def test_pipeline_response_with_walk_forward(self):
        """PipelineResponse includes walk_forward data."""
        resp = PipelineResponse(
            success=True,
            pipeline_id="wf-test",
            walk_forward={"overfit_score": 0.2, "confidence_level": "high"},
        )
        assert resp.walk_forward["overfit_score"] == 0.2

    def test_improve_strategy_request_validation(self):
        """ImproveStrategyRequest validates bounds."""
        from pydantic import ValidationError

        # wf_splits must be >= 2
        with pytest.raises(ValidationError):
            ImproveStrategyRequest(strategy_type="rsi", wf_splits=1)

        # wf_train_ratio must be >= 0.5
        with pytest.raises(ValidationError):
            ImproveStrategyRequest(strategy_type="rsi", wf_train_ratio=0.3)
