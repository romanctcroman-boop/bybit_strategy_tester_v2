#!/usr/bin/env python3
"""
Проверка списка тикеров напрямую от Bybit (без нашего API).

Если этот скрипт возвращает список — сеть и Bybit API в порядке, проблема в нашем бэкенде/фронте.
Если падает с DNS/таймаутом — проблема сеть/фаервол/прокси.

  py -3.14 scripts/test_bybit_symbols_direct.py
  py -3.14 scripts/test_bybit_symbols_direct.py --category spot
"""
from __future__ import annotations

import argparse
import sys

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch ticker list directly from Bybit")
    parser.add_argument("--category", default="linear", choices=("linear", "spot"), help="Market category")
    parser.add_argument("--limit", type=int, default=500, help="Limit per page (max 1000)")
    args = parser.parse_args()

    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {"category": args.category, "limit": args.limit}

    print(f"GET {url}?category={args.category}&limit={args.limit}")
    print("...")
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети: {e}", file=sys.stderr)
        sys.exit(1)

    ret_code = data.get("retCode", -1)
    ret_msg = data.get("retMsg", "")
    if ret_code != 0:
        print(f"Bybit retCode={ret_code} retMsg={ret_msg}", file=sys.stderr)
        sys.exit(1)

    result = data.get("result") or {}
    items = result.get("list") or []
    symbols = [it.get("symbol") for it in items if isinstance(it, dict) and it.get("symbol")]

    print(f"OK: получено {len(symbols)} тикеров (category={args.category})")
    if symbols:
        print("Примеры:", ", ".join(symbols[:15]))
    sys.exit(0)


if __name__ == "__main__":
    main()
