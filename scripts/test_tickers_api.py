#!/usr/bin/env python3
"""
Проверка запросов/ответов API тикеров (symbols-list, refresh-tickers).

Запуск (сервер должен быть поднят):
  py -3.14 scripts/test_tickers_api.py
  py -3.14 scripts/test_tickers_api.py --base http://127.0.0.1:8000
При 404: обязательно перезапустите API-сервер (остановить и снова запустить),
чтобы подхватить маршруты symbols-list и refresh-tickers из app.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Test tickers API (symbols-list, refresh-tickers)")
    parser.add_argument(
        "--base",
        default="http://127.0.0.1:8000",
        help="Base URL of the API (default: http://127.0.0.1:8000)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print full response body")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    def get(path: str) -> tuple[int, dict | list, str]:
        url = f"{base}{path}"
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    data = body
                return r.status, data, body
        except HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = body
            return e.code, data, body
        except URLError as e:
            print(f"URLError: {e}", file=sys.stderr)
            return -1, {}, str(e)

    def post(path: str) -> tuple[int, dict | list, str]:
        url = f"{base}{path}"
        req = Request(url, method="POST", data=b"", headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    data = body
                return r.status, data, body
        except HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = body
            return e.code, data, body
        except URLError as e:
            print(f"URLError: {e}", file=sys.stderr)
            return -1, {}, str(e)

    def show(name: str, status: int, data: dict | list, raw: str) -> None:
        ok = "OK" if 200 <= status < 300 else "FAIL"
        print(f"\n--- {name} ---")
        print(f"Status: {status} {ok}")
        if args.verbose:
            print("Body (raw):", raw[:2000] + ("..." if len(raw) > 2000 else ""))
        else:
            if isinstance(data, dict):
                if "symbols" in data:
                    n = len(data.get("symbols", []))
                    print(f"symbols: {n} items")
                    if n and n <= 5:
                        print("  sample:", data["symbols"][:5])
                    elif n:
                        print("  sample:", data["symbols"][:3], "...")
                else:
                    print("Response:", json.dumps(data, ensure_ascii=False)[:500])
            else:
                print("Response:", str(data)[:500])

    print(f"Base URL: {base}")

    # 0) Sanity: endpoints that should work
    status0, _, _ = get("/healthz")
    print(f"\n--- Sanity ---\n/healthz: {status0} {'OK' if status0 == 200 else 'FAIL'}")
    status0b, _, _ = get("/api/v1/marketdata/symbols/BTCUSDT/instrument-info")
    print(f"GET /api/v1/marketdata/symbols/BTCUSDT/instrument-info: {status0b} {'OK' if status0b == 200 else 'FAIL'}")

    # 1) GET symbols-list (linear)
    status1, data1, raw1 = get("/api/v1/marketdata/symbols-list?category=linear")
    show("GET /api/v1/marketdata/symbols-list?category=linear", status1, data1, raw1)

    # 2) POST refresh-tickers
    status2, data2, raw2 = post("/api/v1/refresh-tickers")
    show("POST /api/v1/refresh-tickers", status2, data2, raw2)

    # 3) GET symbols-list again (after refresh)
    status3, data3, raw3 = get("/api/v1/marketdata/symbols-list?category=linear")
    show("GET /api/v1/marketdata/symbols-list?category=linear (after refresh)", status3, data3, raw3)

    # Summary
    ok = status1 == 200 and status2 == 200 and status3 == 200
    print("\n--- Summary ---")
    print("symbols-list (1st):", "OK" if status1 == 200 else f"FAIL {status1}")
    print("refresh-tickers:   ", "OK" if status2 == 200 else f"FAIL {status2}")
    print("symbols-list (2nd):", "OK" if status3 == 200 else f"FAIL {status3}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
