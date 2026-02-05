#!/usr/bin/env python3
"""
Collect L2 order book via Bybit WebSocket in real-time.

Usage:
    python scripts/l2_lob_collect_ws.py                    # until Ctrl+C
    python scripts/l2_lob_collect_ws.py --duration 300     # 5 minutes
    python scripts/l2_lob_collect_ws.py --symbol ETHUSDT --output eth.ndjson
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket L2 order book collector")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--depth", type=int, default=50, choices=[1, 50, 200, 1000])
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument("--duration", type=float, default=None, help="Stop after N seconds")
    parser.add_argument("--testnet", action="store_true")
    args = parser.parse_args()

    output = args.output or Path(f"l2_{args.symbol.lower()}_ws.ndjson")

    from backend.experimental.l2_lob.websocket_collector import run_collector_sync

    run_collector_sync(
        symbol=args.symbol,
        depth=args.depth,
        output_path=output,
        max_duration_sec=args.duration,
    )


if __name__ == "__main__":
    main()
