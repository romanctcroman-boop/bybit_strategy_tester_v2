"""Tests for L2 Order Book experimental module."""

import json
import tempfile
from pathlib import Path

import pytest

from backend.experimental.l2_lob.bybit_client import _parse_levels
from backend.experimental.l2_lob.collector import snapshot_to_dict
from backend.experimental.l2_lob.models import L2Level, L2Snapshot
from backend.experimental.l2_lob.replay import load_snapshots_ndjson, snapshot_to_orderbook_simulator


def test_parse_levels():
    """Parse Bybit orderbook format."""
    raw = [["100.5", "10.2"], ["100.4", "5.0"]]
    levels = _parse_levels(raw)
    assert len(levels) == 2
    assert levels[0].price == 100.5
    assert levels[0].size == 10.2
    assert levels[1].price == 100.4


def test_l2_snapshot_properties():
    """L2Snapshot mid, spread, spread_bps."""
    snap = L2Snapshot(
        timestamp=1000,
        symbol="X",
        bids=[L2Level(100.0, 5.0), L2Level(99.0, 10.0)],
        asks=[L2Level(101.0, 3.0), L2Level(102.0, 7.0)],
    )
    assert snap.best_bid == 100.0
    assert snap.best_ask == 101.0
    assert snap.mid_price == 100.5
    assert snap.spread == 1.0
    assert snap.spread_bps is not None
    assert snap.spread_bps > 0


def test_snapshot_to_dict():
    """Serialize L2Snapshot to dict."""
    snap = L2Snapshot(
        timestamp=1000,
        symbol="X",
        bids=[L2Level(100.0, 5.0)],
        asks=[L2Level(101.0, 3.0)],
    )
    d = snapshot_to_dict(snap)
    assert d["ts"] == 1000
    assert d["symbol"] == "X"
    assert d["bids"] == [[100.0, 5.0]]
    assert d["asks"] == [[101.0, 3.0]]


def test_load_snapshots_ndjson():
    """Load NDJSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        f.write('{"ts":1,"symbol":"X","bids":[[100,5]],"asks":[[101,3]]}\n')
        path = Path(f.name)
    try:
        snaps = list(load_snapshots_ndjson(path))
        assert len(snaps) == 1
        assert snaps[0].timestamp == 1
        assert snaps[0].best_bid == 100.0
        assert snaps[0].best_ask == 101.0
    finally:
        path.unlink(missing_ok=True)


def test_snapshot_to_orderbook_simulator():
    """Create OrderBookSimulator from L2Snapshot (requires numba/universal_engine)."""
    pytest.importorskip("numba")
    snap = L2Snapshot(
        timestamp=1000,
        symbol="X",
        bids=[L2Level(100.0, 5.0), L2Level(99.0, 10.0)],
        asks=[L2Level(101.0, 3.0), L2Level(102.0, 7.0)],
    )
    sim = snapshot_to_orderbook_simulator(snap)
    assert len(sim.bids) == 2
    assert len(sim.asks) == 2
    assert sim.bids[0].price == 100.0
    assert sim.bids[0].size == 5.0
    assert sim.last_mid_price == 100.5


def test_cgan_fit_and_generate():
    """Train CGAN for 2 epochs on synthetic data, then generate."""
    pytest.importorskip("torch")
    import numpy as np

    from backend.experimental.l2_lob.generative_cgan import _HAS_TORCH, LOB_CGAN

    if not _HAS_TORCH:
        pytest.skip("PyTorch not installed")

    np.random.seed(42)
    base = 100000.0
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        for _ in range(200):
            mid = base * (1 + np.random.uniform(-0.01, 0.01))
            spread = mid * 0.0001
            bids = [[mid - spread * (i + 1), 10 + np.random.exponential(5)] for i in range(25)]
            asks = [[mid + spread * (i + 1), 10 + np.random.exponential(5)] for i in range(25)]
            d = {"ts": 0, "symbol": "X", "bids": bids, "asks": asks}
            f.write(json.dumps(d) + "\n")
        path = Path(f.name)
    try:
        model = LOB_CGAN(num_levels=20)
        model.fit(path, epochs=2, batch_size=32)
        out = model.generate(mid_price=100500.0, spread_bps=10.0, n_samples=2)
        assert len(out) == 2
        bids, asks = out[0]
        assert len(bids) == 20
        assert len(asks) == 20
        assert bids[0][0] < asks[0][0]
    finally:
        path.unlink(missing_ok=True)


def test_websocket_apply_delta():
    """WebSocket delta application logic."""
    from backend.experimental.l2_lob.websocket_collector import _apply_delta

    book = {100.0: 5.0, 99.0: 10.0}
    _apply_delta(book, [["100", "0"], ["98", "3"]], "b")
    assert 100.0 not in book
    assert book.get(98.0) == 3.0
    assert book.get(99.0) == 10.0


def test_fetch_orderbook_live():
    """Fetch orderbook from Bybit (requires network)."""
    from backend.experimental.l2_lob import fetch_orderbook

    snap = fetch_orderbook("BTCUSDT", limit=5)
    if snap:
        assert snap.mid_price is not None
        assert snap.mid_price > 0
        assert len(snap.bids) >= 1
        assert len(snap.asks) >= 1
