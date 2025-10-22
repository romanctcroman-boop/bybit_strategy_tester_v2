import argparse
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `backend` package resolves when running this script directly
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.services.backfill_service import backfill_cli


def main():
    parser = argparse.ArgumentParser(description="Historical backfill (Bybit -> DB)")
    parser.add_argument("symbol", help="Symbol, e.g. BTCUSDT")
    parser.add_argument("--interval", default="1", help="Interval: 1,3,5,15,60,240,D,W")
    parser.add_argument("--days", type=int, default=7, help="Lookback days (default 7)")
    parser.add_argument("--page", type=int, default=1000, help="Page size (default 1000)")
    args = parser.parse_args()

    backfill_cli(args.symbol, args.interval, args.days, args.page)


if __name__ == "__main__":
    main()
