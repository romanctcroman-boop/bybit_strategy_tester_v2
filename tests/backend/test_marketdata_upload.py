import io
import os
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import app


def test_marketdata_upload_tmp(tmp_path, monkeypatch):
    # Redirect uploads dir to tmp
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    client = TestClient(app)

    content = b"open_time,open,high,low,close,volume\n0,1,2,0.5,1.5,10\n"
    files = {
        "file": ("data.csv", io.BytesIO(content), "text/csv"),
    }
    data = {"symbol": "BTCUSDT", "interval": "1"}

    r = client.post("/api/v1/marketdata/upload", data=data, files=files)
    assert r.status_code == 200, r.text
    body = r.json()

    assert set(body.keys()) == {
        "upload_id",
        "filename",
        "size",
        "symbol",
        "interval",
        "stored_path",
    }
    assert body["filename"] == "data.csv"
    assert body["symbol"] == "BTCUSDT"
    assert body["interval"] == "1"
    assert body["size"] == len(content)

    # File should exist under tmp_path/upload_id/
    p = Path(body["stored_path"]).resolve()
    assert p.exists()
    assert p.read_bytes() == content
