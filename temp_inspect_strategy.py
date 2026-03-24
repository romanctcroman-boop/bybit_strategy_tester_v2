"""Inspect strategy-builder strategy structure."""

import json
import urllib.request

STRATEGY_ID = "824561e0-5e27-4be4-a33a-b064a726d14c"
BASE = "http://localhost:8000"

url = f"{BASE}/api/v1/strategy-builder/strategies/{STRATEGY_ID}"
with urllib.request.urlopen(url, timeout=10) as resp:
    strategy = json.loads(resp.read())

print("Keys:", list(strategy.keys()))
for k, v in strategy.items():
    if k in ("blocks", "connections", "builder_graph", "parameters"):
        if isinstance(v, str) and len(v) > 50:
            try:
                parsed = json.loads(v)
                print(f"  {k}: JSON {type(parsed).__name__}")
                if isinstance(parsed, dict):
                    print(f"    keys: {list(parsed.keys())}")
                    if "blocks" in parsed:
                        print(f"    blocks count: {len(parsed['blocks'])}")
            except:
                print(f"  {k}: str[{len(v)}]")
        elif isinstance(v, (dict, list)):
            print(f"  {k}: {type(v).__name__} len={len(v)}")
            if k == "builder_graph" and isinstance(v, dict):
                print(f"    keys: {list(v.keys())}")
                if "blocks" in v:
                    print(f"    blocks: {[(b.get('id'), b.get('type')) for b in v['blocks'][:5]]}")
        else:
            print(f"  {k}: {v!r}")
