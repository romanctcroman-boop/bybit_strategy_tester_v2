r"""90s backend probe for the market chart endpoints.

Purpose:
- Detect periodic slowdowns (e.g. every ~60s) on the backend side.
- Provide a clear log of latency + status codes.

This script is intentionally dependency-free (stdlib only).

Usage (PowerShell):
    .\.venv\Scripts\python.exe .\scripts\probe_market_chart_api.py

Notes:
- Assumes the server is reachable on http://127.0.0.1:8000
- Targets the same endpoint the frontend uses for candles.
"""

from __future__ import annotations

import contextlib
import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def fetch_json(url: str, timeout_s: float = 10.0):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body


def main() -> int:
    symbol = "BTCUSDT"
    interval = "60"  # normalized
    limit = 500

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": str(limit),
        "source": "db",
    }
    url = (
        f"{BASE}/api/v1/marketdata/bybit/klines/smart?{urllib.parse.urlencode(params)}"
    )

    duration_s = 90
    every_s = 3
    deadline = time.time() + duration_s

    print(f"Probing for {duration_s}s, every {every_s}s")
    print("URL:", url)

    i = 0
    worst_ms = 0.0
    while time.time() < deadline:
        i += 1
        t0 = time.perf_counter()
        status = None
        size = 0
        err = None
        try:
            status, body = fetch_json(url, timeout_s=15.0)
            size = len(body)
            # basic sanity parse (don’t print huge body)
            with contextlib.suppress(Exception):
                json.loads(body)
        except Exception as e:
            err = repr(e)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        worst_ms = max(worst_ms, dt_ms)

        ts = time.strftime("%H:%M:%S")
        if err:
            print(f"[{ts}] #{i:02d} ERROR {dt_ms:7.1f}ms {err}")
        else:
            print(f"[{ts}] #{i:02d} {status} {dt_ms:7.1f}ms bytes={size}")

        time.sleep(every_s)

    print(f"Done. Worst latency: {worst_ms:.1f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
