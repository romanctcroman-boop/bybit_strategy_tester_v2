"""
Compare ENTRY/EXIT bar indices between TV and our backtest.
TV timestamps are UTC+3 → subtract 3h to get UTC bar time → find bar index.
Then check: do TV and our system actually use the SAME bar number for entry/exit?

If TV bar_index == our bar_index → same bar, just UTC+3 display difference
If TV bar_index != our bar_index → genuinely different bar (real bug)
"""

import csv
import sys
from datetime import UTC, datetime, timedelta

import requests

STRATEGY_ID = "3fc04505-a70d-4ede-98ee-275369d1008f"
TV_CSV = r"c:\Users\roman\Downloads\a4.csv"
BASE_URL = "http://localhost:8000"
OUT_FILE = r"d:\bybit_strategy_tester_v2\temp_analysis\bar_compare.txt"

out = open(OUT_FILE, "w", encoding="utf-8")  # noqa: SIM115


def p(line=""):
    print(line)
    out.write(line + "\n")
    out.flush()


# ── Load TV trades ────────────────────────────────────────────────────────────
by_num: dict[int, dict] = {}
with open(TV_CSV, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        keys = list(row.keys())
        num_str = row.get(keys[0], "").strip()
        if not num_str:
            continue
        try:
            num = int(num_str)
        except ValueError:
            continue
        trade_type = row.get("Тип", "")
        dt_str = row.get("Дата и время", "")
        price_str = (row.get("Цена USDT", "0") or "0").replace(",", ".").replace(" ", "").replace("\u202f", "")
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0
        try:
            dt: datetime | None = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        except Exception:
            dt = None
        if num not in by_num:
            by_num[num] = {}
        if "Вход" in trade_type:
            by_num[num]["direction"] = "long" if "длинн" in trade_type.lower() else "short"
            by_num[num]["entry_time_tv"] = dt  # this is UTC+3 labeled as UTC
            by_num[num]["entry_price"] = price
        elif "Выход" in trade_type:
            by_num[num]["exit_time_tv"] = dt  # same: UTC+3 labeled as UTC
            by_num[num]["exit_price"] = price
            pnl_str = (
                (row.get("Чистая прибыль / убыток USDT", "") or "")
                .replace(" ", "")
                .replace("\u202f", "")
                .replace(",", ".")
            )
            try:
                by_num[num]["pnl"] = float(pnl_str)
            except ValueError:
                by_num[num]["pnl"] = None

tv = [by_num[n] for n in sorted(by_num.keys()) if "entry_time_tv" in by_num.get(n, {})]
p(f"TV trades loaded: {len(tv)}")

# TV timestamps are UTC+3 → real UTC = TV time - 3h
for t in tv:
    if t.get("entry_time_tv"):
        t["entry_time_utc"] = t["entry_time_tv"] - timedelta(hours=3)
    if t.get("exit_time_tv"):
        t["exit_time_utc"] = t["exit_time_tv"] - timedelta(hours=3)

# ── Fetch raw OHLCV bars from DB via API ──────────────────────────────────────
p("Fetching kline data...")
resp = requests.get(
    f"{BASE_URL}/api/v1/klines",
    params={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00",
        "end_date": "2026-03-05T00:00:00",
        "limit": "20000",
    },
    timeout=60,
)
if resp.status_code != 200:
    p(f"ERROR fetching klines {resp.status_code}: {resp.text[:300]}")
    # Try alternative endpoint
    resp = requests.get(
        f"{BASE_URL}/api/v1/market/klines",
        params={"symbol": "ETHUSDT", "interval": "30", "limit": "20000"},
        timeout=60,
    )

if resp.status_code != 200:
    p(f"FATAL: Cannot fetch klines: {resp.status_code}")
    out.close()
    sys.exit(1)

kdata = resp.json()
# Find the list of bars
bars = None
if isinstance(kdata, list):
    bars = kdata
elif isinstance(kdata, dict):
    for key in ("data", "klines", "candles", "result"):
        if key in kdata and isinstance(kdata[key], list):
            bars = kdata[key]
            break

if bars is None:
    p(
        f"FATAL: Could not find bars list in response keys: {list(kdata.keys()) if isinstance(kdata, dict) else type(kdata)}"
    )
    out.close()
    sys.exit(1)

p(f"Bars loaded: {len(bars)}")

# Build timestamp → bar_index map
# Each bar is [timestamp_ms, open, high, low, close, volume] or dict
bar_time_to_idx = {}
ts_ms: int | None = None
for idx, bar in enumerate(bars):
    if isinstance(bar, (list, tuple)):
        ts_ms = int(bar[0])
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    elif isinstance(bar, dict):
        # Try common field names
        ts_ms = bar.get("timestamp") or bar.get("open_time") or bar.get("ts") or bar.get("time")
        if ts_ms is None:
            continue
        ts_ms = int(ts_ms)
        if ts_ms > 1e12:  # milliseconds
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        else:  # seconds
            dt = datetime.fromtimestamp(ts_ms, tz=UTC)
    else:
        continue
    # Round to minute to handle any second-level noise
    dt_rounded = dt.replace(second=0, microsecond=0)
    bar_time_to_idx[dt_rounded] = idx

p(f"Bar time map built: {len(bar_time_to_idx)} entries")
if bar_time_to_idx:
    times = sorted(bar_time_to_idx.keys())
    p(f"  First bar: {times[0]}")
    p(f"  Last bar:  {times[-1]}")

# ── Run our backtest ──────────────────────────────────────────────────────────
p("Running our backtest...")
resp = requests.post(
    f"{BASE_URL}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest",
    json={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00+00:00",
        "end_date": "2026-03-04T21:30:00+00:00",
        "initial_capital": 10000,
        "commission": 0.0007,
        "slippage": 0.0,
        "position_size": 0.1,
        "position_size_type": "percent",
        "leverage": 10,
        "pyramiding": 1,
        "direction": "both",
        "market_type": "linear",
        "take_profit": 0.066,
        "stop_loss": 0.132,
        "sl_type": "average_price",
    },
    timeout=120,
)
if resp.status_code != 200:
    p(f"ERROR {resp.status_code}: {resp.text[:300]}")
    out.close()
    sys.exit(1)

data = resp.json()
ours = data.get("trades", data.get("closed_trades", []))
p(f"Our trades: {len(ours)}")

# ── Compare bar indices ───────────────────────────────────────────────────────
p("")
p("=" * 120)
p(
    f"{'#':3} | {'Dir':5} | {'TV entry (UTC+3)':17} {'TV entry (UTC)':17} {'TV bar#':7} | "
    f"{'Our entry (UTC)':17} {'Our bar#':7} | {'Bar diff':8} | "
    f"{'TV exit (UTC+3)':17} {'TV exit (UTC)':17} {'TV xbar#':7} | "
    f"{'Our exit (UTC)':17} {'Our xbar#':7} | {'Xbar diff':9}"
)
p("=" * 120)


def find_bar(dt_utc):
    if dt_utc is None:
        return None
    dt_key = dt_utc.replace(second=0, microsecond=0)
    return bar_time_to_idx.get(dt_key)


bar_diffs_entry = []
bar_diffs_exit = []

for i in range(min(len(tv), len(ours))):
    t = tv[i]
    o = ours[i]

    tv_entry_tv = t.get("entry_time_tv")  # UTC+3 (as TV shows it)
    tv_entry_utc = t.get("entry_time_utc")  # UTC (after -3h)
    our_entry_str = str(o.get("entry_time", ""))[:16].replace("T", " ")
    try:
        our_entry_utc: datetime | None = datetime.strptime(our_entry_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    except Exception:
        our_entry_utc = None

    tv_exit_tv = t.get("exit_time_tv")
    tv_exit_utc = t.get("exit_time_utc")
    our_exit_str = str(o.get("exit_time", ""))[:16].replace("T", " ")
    try:
        our_exit_utc: datetime | None = datetime.strptime(our_exit_str, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    except Exception:
        our_exit_utc = None

    tv_entry_bar = find_bar(tv_entry_utc)
    our_entry_bar = find_bar(our_entry_utc)
    tv_exit_bar = find_bar(tv_exit_utc)
    our_exit_bar = find_bar(our_exit_utc)

    entry_bar_diff = (
        (our_entry_bar - tv_entry_bar) if (tv_entry_bar is not None and our_entry_bar is not None) else None
    )
    exit_bar_diff = (our_exit_bar - tv_exit_bar) if (tv_exit_bar is not None and our_exit_bar is not None) else None

    if entry_bar_diff is not None:
        bar_diffs_entry.append(entry_bar_diff)
    if exit_bar_diff is not None:
        bar_diffs_exit.append(exit_bar_diff)

    def fs(dt):
        return str(dt)[:16].replace("T", " ") if dt else "None            "

    entry_status = "SAME" if entry_bar_diff == 0 else f"DIFF={entry_bar_diff:+d}"
    exit_status = "SAME" if exit_bar_diff == 0 else f"DIFF={exit_bar_diff:+d}"

    p(
        f"{i + 1:3} | {t.get('direction', '?'):5} | "
        f"{fs(tv_entry_tv):17} {fs(tv_entry_utc):17} {(tv_entry_bar or 'N/A')!s:7} | "
        f"{fs(our_entry_utc):17} {(our_entry_bar or 'N/A')!s:7} | "
        f"{entry_status:8} | "
        f"{fs(tv_exit_tv):17} {fs(tv_exit_utc):17} {(tv_exit_bar or 'N/A')!s:7} | "
        f"{fs(our_exit_utc):17} {(our_exit_bar or 'N/A')!s:7} | "
        f"{exit_status:9}"
    )

p("")
p("=" * 120)
if bar_diffs_entry:
    unique_entry = set(bar_diffs_entry)
    unique_exit = set(bar_diffs_exit)
    p(
        f"Entry bar diffs: {sorted(unique_entry)}  (0=same bar, positive=ours is LATER bar, negative=ours is EARLIER bar)"
    )
    p(f"Exit  bar diffs: {sorted(unique_exit)}")
    p(f"All entry diffs zero (same bar)? {'YES ✓' if all(d == 0 for d in bar_diffs_entry) else 'NO ✗'}")
    p(f"All exit  diffs zero (same bar)? {'YES ✓' if all(d == 0 for d in bar_diffs_exit) else 'NO ✗'}")

out.close()
print(f"\nFull output written to {OUT_FILE}")
