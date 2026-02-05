"""
L2 Order Book collector — периодический сбор снимков.

Сохранение в JSON/NDJSON для последующего replay и обучения Generative LOB.
"""

import json
import logging
import time
from pathlib import Path

from backend.experimental.l2_lob.bybit_client import fetch_orderbook
from backend.experimental.l2_lob.models import L2Snapshot

logger = logging.getLogger(__name__)


def snapshot_to_dict(snap: L2Snapshot) -> dict:
    """Serialize L2Snapshot to JSON-serializable dict."""
    return {
        "ts": snap.timestamp,
        "symbol": snap.symbol,
        "bids": [[l.price, l.size] for l in snap.bids],
        "asks": [[l.price, l.size] for l in snap.asks],
        "u": snap.update_id,
        "seq": snap.seq,
    }


def collect_snapshots(
    symbol: str = "BTCUSDT",
    category: str = "linear",
    limit: int = 50,
    interval_sec: float = 1.0,
    output_path: Path | None = None,
    max_snapshots: int | None = None,
) -> list[L2Snapshot]:
    """
    Collect L2 snapshots periodically and optionally save to file.

    Args:
        symbol: Trading pair
        category: Bybit category
        limit: Order book depth
        interval_sec: Seconds between snapshots
        output_path: NDJSON file to append snapshots (one JSON per line)
        max_snapshots: Stop after N snapshots (None = infinite until interrupt)

    Returns:
        List of collected L2Snapshot
    """
    snapshots: list[L2Snapshot] = []
    fp = open(output_path, "a", encoding="utf-8") if output_path else None

    try:
        count = 0
        while max_snapshots is None or count < max_snapshots:
            snap = fetch_orderbook(symbol=symbol, category=category, limit=limit)
            if snap:
                snapshots.append(snap)
                count += 1
                if fp:
                    fp.write(json.dumps(snapshot_to_dict(snap), ensure_ascii=False) + "\n")
                    fp.flush()
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        logger.info("Collector stopped by user")
    finally:
        if fp:
            fp.close()

    return snapshots
