"""
AI Agent: Build & Backtest a Real Strategy via Strategy Builder API

Strategy: "AI EMA Crossover + RSI Filter"
- Long entry: EMA(9) crosses above EMA(21) — momentum shift up
- Short entry: EMA(9) crosses below EMA(21) — momentum shift down
- RSI(14) calculated as auxiliary (for display / future filter)
- Risk: SL=2%, TP=4%, Leverage=10x, Commission=0.07%
- Data: BTCUSDT 15m, January 2025

Architecture Note:
  - Blocks use CLEAN types matching adapter internals: "price", "rsi", "ema", "crossover", "crossunder"
  - Connection ports use adapter's expected keys: "a"/"b" for conditions, "value" for indicators
  - A main_strategy node (type="strategy") aggregates entry/exit signals
  - Blocks + connections are passed directly in POST /strategies body (saved to DB)
  - Backtest endpoint reads from DB and creates StrategyBuilderAdapter
"""

import sys
import time
import uuid

import requests

BASE = "http://localhost:8000/api/v1/strategy-builder"
TIMEOUT = 60

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})


def log(icon, msg):
    print(f"  {icon} {msg}")


def fail(step, r):
    print(f"\n  FAIL [{step}] HTTP {r.status_code}")
    print(f"  Body: {r.text[:500]}")
    sys.exit(1)


def bid():
    """Generate short unique ID."""
    return str(uuid.uuid4())[:8]


# =========================================================================
print("=" * 70)
print("  AI AGENT: Strategy Builder — Real API Flow")
print("=" * 70)

# =========================================================================
# PHASE 1: Health Check
# =========================================================================
print("\n PHASE 1: Health Check")
r = session.get("http://localhost:8000/api/v1/health", timeout=TIMEOUT)
if r.status_code != 200:
    fail("health", r)
health = r.json()
log("OK", f"Server: {health['status']}")

# =========================================================================
# PHASE 2: Define Block Graph
# =========================================================================
print("\n PHASE 2: Define Strategy Graph")

# Block IDs
price_id = bid()
rsi_id = bid()
ema9_id = bid()
ema21_id = bid()
cross_up_id = bid()
cross_dn_id = bid()
main_id = bid()

blocks = [
    # === INPUT: Price data ===
    {
        "id": price_id,
        "type": "price",
        "category": "input",
        "name": "Price Data",
        "params": {},
    },
    # === INDICATORS ===
    {
        "id": rsi_id,
        "type": "rsi",
        "category": "indicator",
        "name": "RSI(14)",
        "params": {"period": 14, "overbought": 70, "oversold": 30},
    },
    {
        "id": ema9_id,
        "type": "ema",
        "category": "indicator",
        "name": "EMA(9)",
        "params": {"period": 9},
    },
    {
        "id": ema21_id,
        "type": "ema",
        "category": "indicator",
        "name": "EMA(21)",
        "params": {"period": 21},
    },
    # === CONDITIONS ===
    {
        "id": cross_up_id,
        "type": "crossover",
        "category": "condition",
        "name": "EMA9 > EMA21",
        "params": {},
    },
    {
        "id": cross_dn_id,
        "type": "crossunder",
        "category": "condition",
        "name": "EMA9 < EMA21",
        "params": {},
    },
    # === MAIN STRATEGY (signal aggregator) ===
    {
        "id": main_id,
        "type": "strategy",
        "category": "strategy",
        "isMain": True,
        "name": "Main Strategy",
        "params": {},
    },
]

connections = [
    # Price → indicators (input ports: "source" for RSI/EMA, but adapter uses close from ohlcv directly)
    # Actually, RSI and EMA indicators read ohlcv["close"] directly, so no data connection needed for them.
    # But they DO need to be in execution order after price block — topological sort handles this.
    # EMA9 value → crossover input "a"
    {"id": bid(), "source_block": ema9_id, "source_output": "value", "target_block": cross_up_id, "target_input": "a"},
    # EMA21 value → crossover input "b"
    {"id": bid(), "source_block": ema21_id, "source_output": "value", "target_block": cross_up_id, "target_input": "b"},
    # EMA9 value → crossunder input "a"
    {"id": bid(), "source_block": ema9_id, "source_output": "value", "target_block": cross_dn_id, "target_input": "a"},
    # EMA21 value → crossunder input "b"
    {"id": bid(), "source_block": ema21_id, "source_output": "value", "target_block": cross_dn_id, "target_input": "b"},
    # Crossover result → main_strategy.entry_long
    {
        "id": bid(),
        "source_block": cross_up_id,
        "source_output": "result",
        "target_block": main_id,
        "target_input": "entry_long",
    },
    # Crossunder result → main_strategy.entry_short
    {
        "id": bid(),
        "source_block": cross_dn_id,
        "source_output": "result",
        "target_block": main_id,
        "target_input": "entry_short",
    },
]

for b in blocks:
    log("BLOCK", f"{b['name']:20s} type={b['type']:12s} cat={b['category']}")
log("LINK", f"{len(connections)} connections")

# =========================================================================
# PHASE 3: Create Strategy via API
# =========================================================================
print("\n PHASE 3: Create Strategy")

strategy_payload = {
    "name": "AI EMA Crossover + RSI",
    "description": (
        "AI-built strategy: EMA(9)/EMA(21) crossover signals, RSI(14) momentum indicator. "
        "BTCUSDT 15m. SL=2%, TP=4%, Leverage=10x."
    ),
    "timeframe": "15",
    "symbol": "BTCUSDT",
    "market_type": "linear",
    "direction": "both",
    "initial_capital": 10000.0,
    "leverage": 10,
    "blocks": blocks,
    "connections": connections,
    "main_strategy": {
        "id": main_id,
        "type": "strategy",
        "isMain": True,
        "name": "Main Strategy",
        "params": {},
    },
}

r = session.post(f"{BASE}/strategies", json=strategy_payload, timeout=TIMEOUT)
if r.status_code not in (200, 201):
    fail("create", r)

strategy = r.json()
strategy_id = strategy["id"]
log("OK", f"Strategy ID: {strategy_id}")
log("OK", f"Blocks: {len(strategy.get('blocks', []))}")
log("OK", f"Connections: {len(strategy.get('connections', []))}")

# =========================================================================
# PHASE 4: Verify Strategy in DB
# =========================================================================
print("\n PHASE 4: Verify Persistence")

r = session.get(f"{BASE}/strategies/{strategy_id}", timeout=TIMEOUT)
if r.status_code == 200:
    s = r.json()
    log("OK", f"Name: '{s['name']}'")
    log("OK", f"Blocks: {len(s.get('blocks', []))}, Connections: {len(s.get('connections', []))}")
else:
    log("WARN", f"GET returned {r.status_code}")

# =========================================================================
# PHASE 5: Run Backtest
# =========================================================================
print("\n PHASE 5: Run Backtest (BTCUSDT 15m, Jan 2025)")

backtest_payload = {
    "symbol": "BTCUSDT",
    "interval": "15",
    "initial_capital": 10000.0,
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-02-01T00:00:00Z",
    "market_type": "linear",
    "direction": "both",
    "commission": 0.0007,
    "slippage": 0.0005,
    "leverage": 10,
    "pyramiding": 1,
    "stop_loss": 0.02,
    "take_profit": 0.04,
}

log("INFO", "Running backtest...")
t0 = time.time()
r = session.post(
    f"{BASE}/strategies/{strategy_id}/backtest",
    json=backtest_payload,
    timeout=180,
)
elapsed = time.time() - t0

if r.status_code != 200:
    fail("backtest", r)

result = r.json()
log("OK", f"Completed in {elapsed:.1f}s")

# =========================================================================
# PHASE 6: Display Results
# =========================================================================
print("\n PHASE 6: Results")

bt_id = result.get("backtest_id", "N/A")
log("OK", f"Backtest ID: {bt_id}")
log("OK", f"Status: {result.get('status')}")

# Summary metrics from builder response
summary = result.get("results", {})
if summary:
    print("\n  Quick Summary:")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"    {k:<20} {v:>10.2f}")
        else:
            print(f"    {k:<20} {v}")

# Load full backtest details from standard API
print("\n  Loading full backtest details...")
r2 = session.get(f"http://localhost:8000/api/v1/backtests/{bt_id}", timeout=TIMEOUT)
if r2.status_code == 200:
    full = r2.json()

    # Full metrics
    metrics = full.get("metrics", full.get("performance_metrics", {}))
    if isinstance(metrics, dict):
        print(f"\n  {'Metric':<25} {'Value':>12}")
        print(f"  {'─' * 40}")

        fields = [
            ("net_profit", "Net P&L ($)"),
            ("net_profit_pct", "Return (%)"),
            ("total_trades", "Total Trades"),
            ("winning_trades", "  Winners"),
            ("losing_trades", "  Losers"),
            ("win_rate", "Win Rate (%)"),
            ("profit_factor", "Profit Factor"),
            ("sharpe_ratio", "Sharpe Ratio"),
            ("sortino_ratio", "Sortino Ratio"),
            ("max_drawdown", "Max Drawdown (%)"),
            ("max_drawdown_value", "Max DD ($)"),
            ("avg_trade", "Avg Trade (%)"),
            ("expectancy", "Expectancy ($)"),
            ("largest_win", "Best Trade ($)"),
            ("largest_loss", "Worst Trade ($)"),
            ("total_commission", "Commission ($)"),
            ("buy_hold_return_pct", "Buy&Hold (%)"),
            ("recovery_factor", "Recovery Factor"),
        ]

        for key, label in fields:
            val = metrics.get(key)
            if val is not None:
                if isinstance(val, float):
                    print(f"  {label:<25} {val:>12.2f}")
                else:
                    print(f"  {label:<25} {val:>12}")

    # Trades
    trades = full.get("trades", [])
    if trades:
        print(f"\n  Trade samples (first 5 of {len(trades)}):")
        for t in trades[:5]:
            side = t.get("side", t.get("direction", "?"))
            pnl = t.get("pnl_pct", t.get("profit_pct", 0))
            entry = t.get("entry_price", 0)
            exit_p = t.get("exit_price", 0)
            print(f"    {str(side).upper():>5} | Entry: {entry:>10.2f} | Exit: {exit_p:>10.2f} | PnL: {pnl:>+7.2f}%")
    else:
        log("WARN", "No trades in GET response")

    # Equity curve
    equity = full.get("equity_curve", [])
    if equity:
        log("INFO", f"Equity curve: {len(equity)} points")
else:
    log("WARN", f"GET /backtests/{bt_id} returned {r2.status_code}")

# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 70)
print("  AI AGENT COMPLETED")
print("=" * 70)
print("  Strategy:     AI EMA Crossover + RSI")
print(f"  Strategy ID:  {strategy_id}")
print(f"  Backtest ID:  {bt_id}")
print(f"  Trades:       {len(trades)}")
print()
print(f"  Builder UI:   http://localhost:8000/frontend/strategy-builder.html?id={strategy_id}")
if bt_id and bt_id != "N/A":
    print(f"  Results:      http://localhost:8000/frontend/backtest-results.html?id={bt_id}")
print()
