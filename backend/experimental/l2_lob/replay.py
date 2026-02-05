"""
L2 Replay — использование сохранённых снимков в бэктесте.

Интеграция с OrderBookSimulator: инициализация и обновление из реальных L2 данных.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from backend.experimental.l2_lob.models import L2Level, L2Snapshot

logger = logging.getLogger(__name__)


def load_snapshots_ndjson(path: Path) -> Iterator[L2Snapshot]:
    """Load L2 snapshots from NDJSON file (one JSON object per line)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                bids = [L2Level(price=float(p), size=float(s)) for p, s in d.get("bids", [])]
                asks = [L2Level(price=float(p), size=float(s)) for p, s in d.get("asks", [])]
                yield L2Snapshot(
                    timestamp=d.get("ts", 0),
                    symbol=d.get("symbol", ""),
                    bids=bids,
                    asks=asks,
                    update_id=d.get("u"),
                    seq=d.get("seq"),
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skip invalid line: %s", e)


def snapshot_to_orderbook_simulator(
    snap: L2Snapshot,
    config: Any | None = None,
) -> Any:
    """
    Create OrderBookSimulator initialized from real L2 snapshot.

    Lazy import to avoid pulling numba/universal_engine when not needed.
    """
    from backend.backtesting.universal_engine.order_book import (
        OrderBookConfig,
        OrderBookLevel,
        OrderBookSimulator,
    )

    sim = OrderBookSimulator(config or OrderBookConfig())
    sim.bids = [OrderBookLevel(price=l.price, size=l.size) for l in snap.bids]
    sim.asks = [OrderBookLevel(price=l.price, size=l.size) for l in snap.asks]
    sim.last_mid_price = snap.mid_price or 0.0
    sim.timestamp = snap.timestamp
    return sim
