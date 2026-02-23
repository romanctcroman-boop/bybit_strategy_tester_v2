"""
WebSocket L2 Order Book collector — real-time streaming from Bybit.

Topic: orderbook.{depth}.{symbol}
- Snapshot: initial full book, then delta updates
- Delta: size=0 → delete, new price → insert, existing → update
"""

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path

from backend.experimental.l2_lob.models import L2Level, L2Snapshot

logger = logging.getLogger(__name__)

BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"
BYBIT_WS_TESTNET = "wss://stream-testnet.bybit.com/v5/public/linear"


def _apply_delta(
    book: dict[float, float],
    updates: list[list[str]],
    side: str,
) -> None:
    """Apply delta updates to price->size dict. side: 'b' or 'a'."""
    for row in updates or []:
        if len(row) < 2:
            continue
        try:
            price = float(row[0])
            size = float(row[1])
            if size == 0:
                book.pop(price, None)
            else:
                book[price] = size
        except (ValueError, TypeError):
            continue


def _book_to_levels(book: dict[float, float], descending: bool) -> list[L2Level]:
    """Convert price->size dict to sorted L2Level list."""
    prices = sorted(book.keys(), reverse=descending)
    return [L2Level(price=p, size=book[p]) for p in prices]


async def run_websocket_collector(
    symbol: str = "BTCUSDT",
    depth: int = 50,
    output_path: Path | None = None,
    on_snapshot: Callable[[L2Snapshot], None] | None = None,
    testnet: bool = False,
) -> None:
    """
    Connect to Bybit WebSocket, maintain orderbook, emit snapshots.

    Args:
        symbol: Trading pair
        depth: 1, 50, 200, or 1000
        output_path: NDJSON file to append each snapshot
        on_snapshot: Callback for each snapshot (e.g. for custom processing)
        testnet: Use testnet WebSocket
    """
    try:
        import websockets
    except ImportError:
        raise ImportError("websockets package required: pip install websockets") from None

    url = BYBIT_WS_TESTNET if testnet else BYBIT_WS_URL
    topic = f"orderbook.{depth}.{symbol}"
    subscribe_msg = json.dumps({"op": "subscribe", "args": [topic]})

    bids: dict[float, float] = {}
    asks: dict[float, float] = {}
    fp = open(output_path, "a", encoding="utf-8") if output_path else None

    def _emit(ts: int, u: int | None, seq: int | None) -> None:
        nonlocal bids, asks
        if not bids or not asks:
            return
        snap = L2Snapshot(
            timestamp=ts,
            symbol=symbol,
            bids=_book_to_levels(bids, descending=True),
            asks=_book_to_levels(asks, descending=False),
            update_id=u,
            seq=seq,
        )
        if on_snapshot:
            on_snapshot(snap)
        if fp:
            d = {
                "ts": ts,
                "symbol": symbol,
                "bids": [[l.price, l.size] for l in snap.bids],
                "asks": [[l.price, l.size] for l in snap.asks],
                "u": u,
                "seq": seq,
            }
            fp.write(json.dumps(d, ensure_ascii=False) + "\n")
            fp.flush()

    async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
        await ws.send(subscribe_msg)
        logger.info("Subscribed to %s", topic)

        async for message in ws:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            if "topic" in data and data.get("topic") == topic:
                msg_type = data.get("type", "")
                ts = data.get("ts", 0)
                payload = data.get("data", {})
                u = payload.get("u")
                seq = payload.get("seq")
                raw_b = payload.get("b", [])
                raw_a = payload.get("a", [])

                if msg_type == "snapshot":
                    bids.clear()
                    asks.clear()
                    for row in raw_b:
                        if len(row) >= 2:
                            bids[float(row[0])] = float(row[1])
                    for row in raw_a:
                        if len(row) >= 2:
                            asks[float(row[0])] = float(row[1])
                    _emit(ts, u, seq)
                elif msg_type == "delta":
                    if u == 1:
                        # Reset: new snapshot coming
                        bids.clear()
                        asks.clear()
                    _apply_delta(bids, raw_b, "b")
                    _apply_delta(asks, raw_a, "a")
                    _emit(ts, u, seq)
            elif "success" in data and not data.get("success"):
                logger.error("Subscribe failed: %s", data)

    if fp:
        fp.close()


def run_collector_sync(
    symbol: str = "BTCUSDT",
    depth: int = 50,
    output_path: Path | None = None,
    max_duration_sec: float | None = None,
) -> None:
    """
    Run WebSocket collector (blocking). Ctrl+C to stop.

    Args:
        max_duration_sec: Stop after N seconds (None = run until interrupt)
    """
    collected = [0]

    def on_snap(snap: "L2Snapshot") -> None:
        collected[0] += 1
        if collected[0] % 100 == 0:
            logger.info("Collected %d snapshots", collected[0])

    async def _run() -> None:
        try:
            if max_duration_sec:
                await asyncio.wait_for(
                    run_websocket_collector(
                        symbol=symbol,
                        depth=depth,
                        output_path=output_path,
                        on_snapshot=on_snap,
                    ),
                    timeout=max_duration_sec,
                )
            else:
                await run_websocket_collector(
                    symbol=symbol,
                    depth=depth,
                    output_path=output_path,
                    on_snapshot=on_snap,
                )
        except TimeoutError:
            logger.info("Stopped after %.0f seconds", max_duration_sec)
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Stopped by user. Collected %d snapshots.", collected[0])
