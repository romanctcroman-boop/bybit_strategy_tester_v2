"""Dump all engine trades for RSI_6 and compare counts with TV (104 expected)."""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import warnings

warnings.filterwarnings("ignore")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"


def load_bt_params():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT parameters, builder_blocks, timeframe FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cur.fetchone()
    conn.close()
    params = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
    sltp = next((b for b in blocks if b.get("type") == "static_sltp"), {})
    sp = sltp.get("params", {})
    return {
        "slippage": float(params.get("_slippage", 0.0)),
        "taker_fee": float(params.get("_commission", 0.0007)),
        "leverage": int(params.get("_leverage", 10)),
        "pyramiding": int(params.get("_pyramiding", 1)),
        "take_profit": float(sp.get("take_profit_percent", 1.5)) / 100.0,
        "stop_loss": float(sp.get("stop_loss_percent", 9.1)) / 100.0,
        "interval": str(row[2] or "30"),
    }


def load_candles():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 25, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        """SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
           FROM bybit_kline_audit
           WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear'
           AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC""",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))
    bb = json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
    bc = (
        json.loads(strat["builder_connections"])
        if isinstance(strat["builder_connections"], str)
        else strat["builder_connections"]
    )
    bg = json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
    graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": bb,
        "connections": bc,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if bg and isinstance(bg, dict) and bg.get("main_strategy"):
        graph["main_strategy"] = bg["main_strategy"]
    return graph


def main():
    p = load_bt_params()
    print(
        f"Params: SL={p['stop_loss'] * 100:.1f}% TP={p['take_profit'] * 100:.1f}% "
        f"fee={p['taker_fee']} slippage={p['slippage']} lev={p['leverage']}x pyramid={p['pyramiding']}"
    )

    candles = load_candles()
    print(f"Candles: {len(candles)} bars  {candles.index[0]} -> {candles.index[-1]}")

    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    signals = StrategyBuilderAdapter(load_graph()).generate_signals(candles)
    long_e = np.asarray(signals.entries.values, dtype=bool)
    short_e = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_e), dtype=bool)
    )
    long_x = (
        np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(long_e), dtype=bool)
    )
    short_x = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(long_e), dtype=bool)
    )
    print(f"Signals: {long_e.sum()} long entries, {short_e.sum()} short entries")

    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection

    bt = BacktestInput(
        candles=candles,
        long_entries=long_e,
        long_exits=long_x,
        short_entries=short_e,
        short_exits=short_x,
        initial_capital=1_000_000.0,
        position_size=0.10,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=p["leverage"],
        stop_loss=p["stop_loss"],
        take_profit=p["take_profit"],
        taker_fee=p["taker_fee"],
        slippage=p["slippage"],
        direction=TradeDirection.BOTH,
        pyramiding=p["pyramiding"],
        interval=p["interval"],
    )
    result = FallbackEngineV4().run(bt)
    trades = result.trades
    m = result.metrics
    print(f"\nEngine trades: {len(trades)}  (TV=104, delta={len(trades) - 104:+d})")
    print(f"net_profit={m.net_profit:.2f}  TV=381.47  gap={m.net_profit - 381.47:+.2f}")
    print()

    # Print all trades: UTC time, side, entry/exit price, pnl, reason
    hdr = f"{'#':<4} {'side':<6} {'entry_UTC':<22} {'entry_p':>10} {'exit_UTC':<22} {'exit_p':>10} {'pnl':>8}  reason"
    print(hdr)
    print("-" * len(hdr))
    for i, t in enumerate(trades):
        print(
            f"{i + 1:<4} {t.direction:<6} {str(t.entry_time)[:19]:<22} {t.entry_price:>10.1f} "
            f"{str(t.exit_time)[:19]:<22} {t.exit_price:>10.1f} {t.pnl:>8.2f}  {t.exit_reason}"
        )

    # Stats
    wins = sum(1 for t in trades if t.pnl > 0)
    losses = sum(1 for t in trades if t.pnl < 0)
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]
    print()
    print(f"Total: {len(trades)}  wins={wins}  losses={losses}")
    print(f"Long: {len(longs)}  Short: {len(shorts)}")
    print(
        f"Gross profit: {sum(t.pnl for t in trades if t.pnl > 0):.2f}  Gross loss: {sum(t.pnl for t in trades if t.pnl < 0):.2f}"
    )

    # Show consecutive entries/exits to find blocked signals
    print()
    print("=== Checking for consecutive same-direction entries (pyramiding blocks) ===")
    for i in range(1, len(trades)):
        prev = trades[i - 1]
        curr = trades[i]
        gap_bars = None
        try:
            gap = (pd.Timestamp(curr.entry_time) - pd.Timestamp(prev.exit_time)).total_seconds() / 1800
            gap_bars = int(gap)
        except Exception:
            pass
        if gap_bars is not None and gap_bars <= 1:
            print(
                f"  Trade #{i}: prev exit {str(prev.exit_time)[:19]} -> curr entry {str(curr.entry_time)[:19]}  gap={gap_bars} bars"
            )


if __name__ == "__main__":
    main()
