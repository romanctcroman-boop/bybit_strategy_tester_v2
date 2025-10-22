from fastapi import FastAPI
from fastapi.testclient import TestClient

# Build a minimal app to avoid importing heavy admin/backfill modules
from backend.api.routers.backtests import router as backtests_router


_app = FastAPI()
_app.include_router(backtests_router, prefix="/api/v1/backtests")
client = TestClient(_app)


def test_create_backtest_missing_required_fields_returns_422():
    # Missing all required fields
    resp = client.post("/api/v1/backtests/", json={})
    assert resp.status_code == 422


def test_create_backtest_invalid_types_returns_422():
    payload = {
        "strategy_id": "not-an-int",
        "symbol": 123,  # should be str
        "timeframe": 1,  # should be str
        "start_date": "invalid-date",
        "end_date": "invalid-date",
        "initial_capital": "abc",
    }
    resp = client.post("/api/v1/backtests/", json=payload)
    assert resp.status_code == 422
