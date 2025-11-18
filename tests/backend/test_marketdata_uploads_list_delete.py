import io
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import app


def test_list_and_delete_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    client = TestClient(app)

    # Initially empty
    r0 = client.get("/api/v1/marketdata/uploads")
    assert r0.status_code == 200
    body0 = r0.json()
    assert body0["items"] == []

    # Upload a file
    content = b"t\n"
    r1 = client.post(
        "/api/v1/marketdata/upload",
        data={"symbol": "BTCUSDT", "interval": "1"},
        files={"file": ("a.csv", io.BytesIO(content), "text/csv")},
    )
    assert r1.status_code == 200
    up = r1.json()

    # List should include it
    r2 = client.get("/api/v1/marketdata/uploads")
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) >= 1
    assert any(x["upload_id"] == up["upload_id"] for x in items)

    # Delete it
    r3 = client.delete(f"/api/v1/marketdata/uploads/{up['upload_id']}")
    assert r3.status_code == 200

    # List again: should be gone
    r4 = client.get("/api/v1/marketdata/uploads")
    assert r4.status_code == 200
    ids = [x["upload_id"] for x in r4.json()["items"]]
    assert up["upload_id"] not in ids
