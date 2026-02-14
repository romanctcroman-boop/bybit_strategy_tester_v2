"""Test sync timing and results."""

import json
import time

import requests

t0 = time.time()
r = requests.get(
    "http://localhost:8000/api/v1/marketdata/symbols/sync-all-tf-stream?symbol=BTCUSDT&market_type=linear",
    stream=True,
    timeout=300,
)

for line in r.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data:"):
        continue
    data = json.loads(line[5:].strip())
    elapsed = time.time() - t0
    if data.get("event") == "progress":
        print(
            f"[{elapsed:6.1f}s] TF={data.get('tf'):>3} step={data.get('step')}/{data.get('totalSteps')} {data.get('message', '')}"
        )
    elif data.get("event") == "complete":
        print(f"\n[{elapsed:6.1f}s] === COMPLETE ===")
        print(f"  Total new candles: {data.get('totalNew')}")
        results = data.get("results", {})
        for tf, info in results.items():
            print(f"  TF={tf:>3}: status={info.get('status'):>12}, new={info.get('new_candles', 0)}")
    elif data.get("event") == "error":
        print(f"[{elapsed:6.1f}s] ERROR: {data.get('message')}")

print(f"\nTotal time: {time.time() - t0:.1f}s")
