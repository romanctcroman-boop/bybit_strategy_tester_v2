from io import BytesIO

from fastapi.testclient import TestClient

from backend.api.app import app


def test_marketdata_ingest_csv(tmp_path, monkeypatch):
    # Route under test: /api/v1/marketdata/uploads/{upload_id}/ingest
    client = TestClient(app)

    # Point uploads dir to temp
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    # Prepare a small CSV file
    csv_data = (
        "open_time,open,high,low,close,volume\n"
        "1730000000000,100,110,90,105,1.2\n"
        "1730000060000,105,115,100,112,0.8\n"
        "1730000120000,112,120,110,118,1.1\n"
    ).encode("utf-8")

    # Upload
    files = {"file": ("sample.csv", BytesIO(csv_data), "text/csv")}
    data = {"symbol": "BTCUSDT", "interval": "1"}
    r = client.post("/api/v1/marketdata/upload", data=data, files=files)
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["upload_id"]

    # Ingest
    r2 = client.post(
        f"/api/v1/marketdata/uploads/{up['upload_id']}/ingest",
        data={"symbol": "BTCUSDT", "interval": "1", "fmt": "csv"},
    )
    assert r2.status_code == 200, r2.text
    ing = r2.json()
    assert ing["ingested"] >= 3
    assert ing["symbol"] == "BTCUSDT"
    assert ing["interval"] == "1"

    # Working set should be updated and contain at least 3 candles
    r3 = client.get(
        "/api/v1/marketdata/bybit/klines/working",
        params={"symbol": "BTCUSDT", "interval": "1", "load_limit": 100},
    )
    assert r3.status_code == 200, r3.text
    data = r3.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_klines_working_validation():
    """Test that load_limit parameter validates correctly (min 100, max 1000)."""
    client = TestClient(app)

    # Test: load_limit too small (< 100) - should fail
    r1 = client.get(
        "/api/v1/marketdata/bybit/klines/working",
        params={"symbol": "BTCUSDT", "interval": "15", "load_limit": 10},
    )
    assert r1.status_code == 422, "Should reject load_limit < 100"

    # Test: load_limit at minimum (100) - should succeed
    r2 = client.get(
        "/api/v1/marketdata/bybit/klines/working",
        params={"symbol": "BTCUSDT", "interval": "15", "load_limit": 100},
    )
    assert r2.status_code in [200, 404], "Should accept load_limit = 100"

    # Test: load_limit at maximum (1000) - should succeed
    r3 = client.get(
        "/api/v1/marketdata/bybit/klines/working",
        params={"symbol": "BTCUSDT", "interval": "15", "load_limit": 1000},
    )
    assert r3.status_code in [200, 404], "Should accept load_limit = 1000"

    # Test: load_limit too large (> 1000) - should fail
    r4 = client.get(
        "/api/v1/marketdata/bybit/klines/working",
        params={"symbol": "BTCUSDT", "interval": "15", "load_limit": 2000},
    )
    assert r4.status_code == 422, "Should reject load_limit > 1000"
