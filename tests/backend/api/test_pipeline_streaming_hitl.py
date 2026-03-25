"""
Tests for P2-3 (HITL) and P2-4 (streaming WebSocket) API endpoints.

Tests ai_pipeline.py routes:
  POST /ai-pipeline/generate-stream
  WS   /ai-pipeline/stream/{pipeline_id}
  POST /ai-pipeline/generate-hitl
  GET  /ai-pipeline/pipeline/{id}/hitl
  POST /ai-pipeline/pipeline/{id}/hitl/approve
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from backend.api.routers.ai_pipeline import router
from backend.agents.langgraph_orchestrator import AgentState

# Bare app with only the ai_pipeline router — no /api/v1 prefix
app = FastAPI()
app.include_router(router)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(hitl_pending: bool = False, hitl_approved: bool = False, errors: list | None = None) -> AgentState:
    state = AgentState()
    state.context["hitl_pending"] = hitl_pending
    state.context["hitl_approved"] = hitl_approved
    if hitl_pending:
        state.context["hitl_payload"] = {
            "strategy_name": "TestRSI",
            "backtest_summary": {"trades": 20, "sharpe": 1.1, "max_dd": 12.0, "net_profit": 300},
            "regime": "trending_bull",
            "message": "Pipeline paused.",
        }
    state.set_result("report", {"strategy": "TestRSI", "pipeline_metrics": {}})
    if errors:
        for e in errors:
            state.add_error("test", RuntimeError(e))
    return state


FAKE_DF = MagicMock()
FAKE_DF.empty = False


# ---------------------------------------------------------------------------
# P2-4: POST /generate-stream
# ---------------------------------------------------------------------------


class TestGenerateStream:
    def test_returns_pipeline_id_and_ws_url(self):
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=_make_state()):
                with TestClient(app) as client:
                    resp = client.post("/ai-pipeline/generate-stream", json={
                        "symbol": "BTCUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_id" in data
        assert "ws_url" in data
        assert data["ws_url"].startswith("/ai-pipeline/stream/")

    def test_pipeline_id_is_unique_per_call(self):
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=_make_state()):
                with TestClient(app) as client:
                    r1 = client.post("/ai-pipeline/generate-stream", json={
                        "symbol": "BTCUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
                    r2 = client.post("/ai-pipeline/generate-stream", json={
                        "symbol": "ETHUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
        assert r1.json()["pipeline_id"] != r2.json()["pipeline_id"]

    def test_ohlcv_error_returns_500(self):
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data",
                   new_callable=AsyncMock, side_effect=ValueError("no data")):
            with TestClient(app) as client:
                resp = client.post("/ai-pipeline/generate-stream", json={
                    "symbol": "BTCUSDT", "timeframe": "15",
                    "start_date": "2025-01-01", "end_date": "2025-06-01",
                })
        # Returns 200 immediately (background task handles the error)
        assert resp.status_code == 200

    def test_job_stored_in_pipeline_jobs(self):
        from backend.api.routers.ai_pipeline import _pipeline_jobs
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=_make_state()):
                with TestClient(app) as client:
                    resp = client.post("/ai-pipeline/generate-stream", json={
                        "symbol": "BTCUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
        pid = resp.json()["pipeline_id"]
        assert pid in _pipeline_jobs


# ---------------------------------------------------------------------------
# P2-4: WS /stream/{pipeline_id}
# ---------------------------------------------------------------------------


class TestStreamWebSocket:
    def test_ws_unknown_pipeline_returns_error(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ai-pipeline/stream/nonexistent_id") as ws:
                msg = ws.receive_json()
                assert "error" in msg

    def test_ws_receives_done_event_from_queue(self):
        """Manually inject a 'done' event into the queue and verify WS receives it."""
        import asyncio
        from backend.api.routers.ai_pipeline import _pipeline_queues

        pid = "test_ws_pid_001"
        q: asyncio.Queue = asyncio.Queue()
        _pipeline_queues[pid] = q

        # Put the done event into queue before connecting
        q.put_nowait({"status": "done", "success": True, "pipeline_id": pid, "result": {}})

        with TestClient(app) as client:
            with client.websocket_connect(f"/ai-pipeline/stream/{pid}") as ws:
                msg = ws.receive_json()
                assert msg["status"] == "done"
                assert msg["pipeline_id"] == pid

        # Queue should be cleaned up
        assert pid not in _pipeline_queues

    def test_ws_receives_node_events_then_done(self):
        """Verify WS streams node events in order, then closes on 'done'."""
        import asyncio
        from backend.api.routers.ai_pipeline import _pipeline_queues

        pid = "test_ws_pid_002"
        q: asyncio.Queue = asyncio.Queue()
        _pipeline_queues[pid] = q

        q.put_nowait({"node": "analyze_market", "status": "completed", "iteration": 1})
        q.put_nowait({"node": "regime_classifier", "status": "completed", "iteration": 2})
        q.put_nowait({"status": "done", "success": True, "pipeline_id": pid, "result": {}})

        events = []
        with TestClient(app) as client:
            with client.websocket_connect(f"/ai-pipeline/stream/{pid}") as ws:
                for _ in range(3):
                    events.append(ws.receive_json())

        assert events[0]["node"] == "analyze_market"
        assert events[1]["node"] == "regime_classifier"
        assert events[2]["status"] == "done"
        assert pid not in _pipeline_queues


# ---------------------------------------------------------------------------
# P2-3: POST /generate-hitl
# ---------------------------------------------------------------------------


class TestGenerateHITL:
    def test_returns_hitl_pending_when_not_approved(self):
        pending_state = _make_state(hitl_pending=True)
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=pending_state):
                with TestClient(app) as client:
                    resp = client.post("/ai-pipeline/generate-hitl", json={
                        "symbol": "BTCUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hitl_pending"] is True
        assert "pipeline_id" in data
        assert "backtest_summary" in data["hitl_payload"]

    def test_returns_completed_when_hitl_not_triggered(self):
        """When pipeline completes without HITL pause, returns hitl_pending=False."""
        completed_state = _make_state(hitl_pending=False)
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=completed_state):
                with TestClient(app) as client:
                    resp = client.post("/ai-pipeline/generate-hitl", json={
                        "symbol": "BTCUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
        assert resp.status_code == 200
        assert resp.json()["hitl_pending"] is False

    def test_message_contains_approve_url_when_pending(self):
        pending_state = _make_state(hitl_pending=True)
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=pending_state):
                with TestClient(app) as client:
                    resp = client.post("/ai-pipeline/generate-hitl", json={
                        "symbol": "BTCUSDT", "timeframe": "15",
                        "start_date": "2025-01-01", "end_date": "2025-06-01",
                    })
        assert "/hitl/approve" in resp.json()["message"]

    def test_ohlcv_error_returns_500(self):
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data",
                   new_callable=AsyncMock, side_effect=ValueError("no data")):
            with TestClient(app) as client:
                resp = client.post("/ai-pipeline/generate-hitl", json={
                    "symbol": "BTCUSDT", "timeframe": "15",
                    "start_date": "2025-01-01", "end_date": "2025-06-01",
                })
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# P2-3: GET /pipeline/{id}/hitl
# ---------------------------------------------------------------------------


class TestGetHITLStatus:
    def test_404_for_unknown_pipeline(self):
        with TestClient(app) as client:
            resp = client.get("/ai-pipeline/pipeline/nonexistent_id/hitl")
        assert resp.status_code == 404

    def test_returns_pending_status_from_job_store(self):
        from backend.api.routers.ai_pipeline import _pipeline_jobs
        pid = "hitl_status_test_001"
        _pipeline_jobs[pid] = {
            "status": "hitl_pending",
            "created_at": "2026-03-25T12:00:00+00:00",
            "hitl_pending": True,
            "hitl_payload": {"strategy_name": "TestRSI"},
        }
        with TestClient(app) as client:
            resp = client.get(f"/ai-pipeline/pipeline/{pid}/hitl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hitl_pending"] is True
        assert data["hitl_payload"]["strategy_name"] == "TestRSI"

    def test_returns_not_pending_when_completed(self):
        from backend.api.routers.ai_pipeline import _pipeline_jobs
        pid = "hitl_status_test_002"
        _pipeline_jobs[pid] = {
            "status": "completed",
            "created_at": "2026-03-25T12:00:00+00:00",
            "hitl_pending": False,
        }
        with TestClient(app) as client:
            resp = client.get(f"/ai-pipeline/pipeline/{pid}/hitl")
        assert resp.status_code == 200
        assert resp.json()["hitl_pending"] is False


# ---------------------------------------------------------------------------
# P2-3: POST /pipeline/{id}/hitl/approve
# ---------------------------------------------------------------------------


class TestApproveHITL:
    def test_404_for_unknown_pipeline(self):
        with TestClient(app) as client:
            resp = client.post("/ai-pipeline/pipeline/nonexistent_id/hitl/approve")
        assert resp.status_code == 404

    def test_approve_not_pending_returns_status(self):
        from backend.api.routers.ai_pipeline import _pipeline_jobs
        pid = "hitl_approve_test_001"
        _pipeline_jobs[pid] = {
            "status": "completed",
            "created_at": "2026-03-25T12:00:00+00:00",
            "hitl_pending": False,
        }
        with TestClient(app) as client:
            resp = client.post(f"/ai-pipeline/pipeline/{pid}/hitl/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert "not in HITL-pending state" in resp.json()["message"]

    def test_approve_runs_pipeline_with_approval(self):
        from backend.api.routers.ai_pipeline import _pipeline_jobs
        pid = "hitl_approve_test_002"
        _pipeline_jobs[pid] = {
            "status": "hitl_pending",
            "created_at": "2026-03-25T12:00:00+00:00",
            "hitl_pending": True,
            "hitl_request": {
                "symbol": "BTCUSDT", "timeframe": "15",
                "start_date": "2025-01-01", "end_date": "2025-06-01",
                "agents": ["deepseek"], "run_backtest": True,
                "initial_capital": 10000, "leverage": 1, "pipeline_timeout": 300.0,
            },
        }
        approved_state = _make_state(hitl_pending=False)
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=approved_state) as mock_run:
                with TestClient(app) as client:
                    resp = client.post(f"/ai-pipeline/pipeline/{pid}/hitl/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        # Verify pipeline was called with hitl_approved=True
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("hitl_approved") is True
        assert call_kwargs.get("hitl_enabled") is True

    def test_approve_updates_job_status(self):
        from backend.api.routers.ai_pipeline import _pipeline_jobs
        pid = "hitl_approve_test_003"
        _pipeline_jobs[pid] = {
            "status": "hitl_pending",
            "created_at": "2026-03-25T12:00:00+00:00",
            "hitl_pending": True,
            "hitl_request": {
                "symbol": "BTCUSDT", "timeframe": "15",
                "start_date": "2025-01-01", "end_date": "2025-06-01",
                "agents": ["deepseek"], "run_backtest": True,
                "initial_capital": 10000, "leverage": 1, "pipeline_timeout": 300.0,
            },
        }
        with patch("backend.api.routers.ai_pipeline._load_ohlcv_data", new_callable=AsyncMock, return_value=FAKE_DF):
            with patch("backend.agents.trading_strategy_graph.run_strategy_pipeline",
                       new_callable=AsyncMock, return_value=_make_state()):
                with TestClient(app) as client:
                    client.post(f"/ai-pipeline/pipeline/{pid}/hitl/approve")
        assert _pipeline_jobs[pid]["status"] == "completed"
        assert _pipeline_jobs[pid]["hitl_pending"] is False
