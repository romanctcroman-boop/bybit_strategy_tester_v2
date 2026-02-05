#!/usr/bin/env python3
"""
Train CGAN for LOB generation from NDJSON data.

Usage:
    python scripts/l2_lob_train_cgan.py --data l2_btcusdt.ndjson --epochs 50 --output model.pt
    python scripts/l2_lob_train_cgan.py --data l2_btcusdt.ndjson --collect 60  # collect 60s first
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train CGAN for LOB generation")
    parser.add_argument("--data", type=Path, help="NDJSON file with L2 snapshots")
    parser.add_argument("--output", "-o", type=Path, default=Path("lob_cgan.pt"))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--collect",
        type=int,
        metavar="SEC",
        help="Collect L2 via WebSocket for SEC seconds before training",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()

    data_path = args.data
    if args.collect:
        from backend.experimental.l2_lob.websocket_collector import run_collector_sync

        data_path = Path(f"l2_{args.symbol.lower()}_ws.ndjson")
        logger.info("Collecting %d seconds of L2 via WebSocket -> %s", args.collect, data_path)
        run_collector_sync(
            symbol=args.symbol,
            depth=50,
            output_path=data_path,
            max_duration_sec=float(args.collect),
        )
        if not data_path.exists() or data_path.stat().st_size < 100:
            logger.error("Collection produced no/few data")
            sys.exit(1)

    if not data_path or not data_path.exists():
        parser.error("--data required (or use --collect to gather first)")

    try:
        from backend.experimental.l2_lob.generative_cgan import _HAS_TORCH, LOB_CGAN
    except ImportError:
        logger.error("generative_cgan import failed")
        sys.exit(1)

    if not _HAS_TORCH:
        logger.error("PyTorch required: pip install torch")
        sys.exit(1)

    model = LOB_CGAN()
    losses = model.fit(data_path, epochs=args.epochs, batch_size=args.batch_size)
    model.save(args.output)
    logger.info("Saved to %s. Final G_loss=%.4f", args.output, losses[-1] if losses else 0)


if __name__ == "__main__":
    main()
