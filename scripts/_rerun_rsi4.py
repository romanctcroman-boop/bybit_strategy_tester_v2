"""
Rerun backtest for Strategy_RSI_L\\S_4 with TV-matching params (IC=1M, slippage=0)
and compare entry signals to TV CSV to find missing 3 trades.

TV settings confirmed:
  IC=1,000,000  commission=0.07%  slippage=0  leverage=10
  position_size=10%  direction=both  SL=3%  TP=1.5%
  cross_short_level=53 (strategy param, NOT 55 default)
  use_long_range=false, use_short_range=true, use_cross_level=true
"""

import json
import sqlite3
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "8597c9e0-c147-4d9a-8025-92994b4cdf1b"

# TV CSV - first 40 trades from a4.csv (entry side + time in UTC+3 + price)
TV_TRADES_RAW = [
    (1, "short", "2025-11-01 14:30", 110003.6, "TP Hit", "2025-11-03 06:00", 108353.5, 13.61),
    (2, "long", "2025-11-03 08:15", 107903.8, "SL Hit", "2025-11-04 08:45", 104666.6, -31.38),
    (3, "long", "2025-11-04 09:15", 104835.7, "SL Hit", "2025-11-04 20:00", 101690.6, -31.38),
    (4, "long", "2025-11-04 21:45", 101212.5, "TP Hit", "2025-11-05 15:15", 102730.7, 13.59),
    (5, "short", "2025-11-06 00:00", 103789.8, "TP Hit", "2025-11-06 17:30", 102232.9, 13.61),
    (6, "long", "2025-11-06 20:00", 100806.7, "TP Hit", "2025-11-07 05:15", 102260.8, 13.59),
    (7, "short", "2025-11-07 07:45", 101766.1, "TP Hit", "2025-11-07 13:15", 100232.2, 13.61),
    (8, "long", "2025-11-07 14:45", 100110.0, "TP Hit", "2025-11-08 03:45", 101576.4, 13.59),
    (9, "short", "2025-11-08 05:45", 103087.8, "TP Hit", "2025-11-08 16:15", 101533.5, 13.61),
    (10, "short", "2025-11-09 00:15", 101983.3, "SL Hit", "2025-11-09 23:00", 105142.8, -31.42),
    (11, "short", "2025-11-10 13:30", 106119.0, "TP Hit", "2025-11-11 14:45", 104553.0, 13.61),
    (12, "long", "2025-11-11 19:15", 103486.0, "TP Hit", "2025-11-12 11:30", 104974.8, 13.59),
    (13, "short", "2025-11-12 17:45", 104667.2, "TP Hit", "2025-11-12 18:45", 103052.7, 13.61),
    (14, "long", "2025-11-12 22:45", 101351.2, "TP Hit", "2025-11-13 09:00", 102821.5, 13.59),
    (15, "long", "2025-11-14 00:15", 98578.3, "TP Hit", "2025-11-14 02:30", 100013.4, 13.59),
    (16, "short", "2025-11-14 06:00", 99573.6, "TP Hit", "2025-11-14 07:30", 98091.2, 13.61),
    (17, "long", "2025-11-14 08:00", 97769.2, "SL Hit", "2025-11-14 15:15", 94736.3, -31.38),
    (18, "long", "2025-11-14 16:00", 95326.8, "TP Hit", "2025-11-14 18:15", 96760.7, 13.59),
    (19, "short", "2025-11-14 19:15", 96466.9, "TP Hit", "2025-11-14 22:00", 95020.7, 13.61),
    (20, "short", "2025-11-15 09:45", 96063.2, "TP Hit", "2025-11-16 18:45", 94619.3, 13.61),
    (21, "long", "2025-11-16 21:00", 94317.8, "TP Hit", "2025-11-17 10:45", 95731.9, 13.59),
    (22, "short", "2025-11-17 15:00", 95530.9, "TP Hit", "2025-11-17 16:30", 94102.6, 13.61),
    (23, "long", "2025-11-17 17:15", 94028.8, "TP Hit", "2025-11-17 17:45", 95418.0, 13.59),
    (24, "long", "2025-11-17 23:30", 91735.2, "TP Hit", "2025-11-18 19:15", 93111.2, 13.59),
    (25, "long", "2025-11-19 09:30", 90767.0, "TP Hit", "2025-11-19 18:15", 92128.5, 13.59),
    (26, "long", "2025-11-20 21:15", 87656.8, "SL Hit", "2025-11-21 10:30", 84988.1, -31.38),
    (27, "long", "2025-11-21 11:15", 84450.6, "SL Hit", "2025-11-21 13:15", 81876.1, -31.38),
    (28, "long", "2025-11-21 14:00", 82671.2, "TP Hit", "2025-11-21 16:15", 83897.0, 13.59),
    (29, "short", "2025-11-21 17:15", 83778.9, "TP Hit", "2025-11-21 19:15", 82421.4, 13.61),
    (30, "short", "2025-11-21 22:45", 84409.8, "SL Hit", "2025-11-23 17:15", 87142.9, -31.42),
    (31, "short", "2025-11-23 20:00", 86642.9, "TP Hit", "2025-11-24 17:00", 85368.7, 13.61),
    (32, "short", "2025-11-25 02:45", 88369.8, "TP Hit", "2025-11-25 11:45", 86966.3, 13.61),
    (33, "long", "2025-11-25 12:45", 87032.4, "TP Hit", "2025-11-26 20:30", 88336.8, 13.59),
    (34, "short", "2025-11-27 08:45", 90919.8, "TP Hit", "2025-12-01 03:15", 89556.0, 13.61),
    (35, "long", "2025-12-01 09:00", 85964.2, "TP Hit", "2025-12-02 04:15", 87243.8, 13.59),
    (36, "short", "2025-12-02 06:30", 86306.8, "SL Hit", "2025-12-02 17:45", 88940.5, -31.42),
    (37, "short", "2025-12-03 03:00", 91241.7, "SL Hit", "2025-12-04 01:45", 94025.9, -31.42),
    (38, "short", "2025-12-04 04:30", 93336.1, "TP Hit", "2025-12-04 17:45", 91824.5, 13.61),
    (39, "long", "2025-12-04 18:15", 92602.0, "SL Hit", "2025-12-05 20:30", 89779.0, -31.38),
    (40, "long", "2025-12-05 20:00", 88760.0, "TP Hit", "2025-12-06 17:15", 90091.4, 13.59),
]


def load_ohlcv():
    """Load BTCUSDT 15m klines from DB."""
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 23, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def generate_signals(ohlcv: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Generate signals using StrategyBuilderAdapter for Strategy_RSI_L\\S_4."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))

    builder_blocks = (
        json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
    )
    builder_connections = (
        json.loads(strat["builder_connections"])
        if isinstance(strat["builder_connections"], str)
        else strat["builder_connections"]
    )
    builder_graph_raw = (
        json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
    )

    strategy_graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": builder_blocks,
        "connections": builder_connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "15",
    }
    if builder_graph_raw and isinstance(builder_graph_raw, dict) and builder_graph_raw.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(strategy_graph)
    signals = adapter.generate_signals(ohlcv)

    long_arr = np.asarray(signals.entries.values, dtype=bool)
    short_arr = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(long_arr), dtype=bool)
    )
    return long_arr, short_arr


def utc3_to_utc(s: str) -> pd.Timestamp:
    """Convert 'YYYY-MM-DD HH:MM' UTC+3 string to UTC timestamp."""
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    return pd.Timestamp(dt) - pd.Timedelta(hours=3)


def main():
    print("=" * 72)
    print("RSI_L\\S_4 — Signal comparison vs TV (UTC+3 → signal bar = entry-15min)")
    print("=" * 72)

    # 1. Load OHLCV
    ohlcv = load_ohlcv()
    print(f"OHLCV: {len(ohlcv)} bars  ({ohlcv.index[0]}  →  {ohlcv.index[-1]})")

    # 2. Generate signals
    long_arr, short_arr = generate_signals(ohlcv)
    print(f"Signals: {long_arr.sum()} long, {short_arr.sum()} short")

    # 3. Map TV trade entry-time → signal-bar (= entry_bar - 15min)
    print()
    print("=== TV trades vs our signals ===")
    hdr = f"{'#':<4} {'side':<6} {'TV entry(UTC+3)':<21} {'signal bar(UTC)':<21} {'our sig':<8} {'entry bar':<21} {'entry_O':<11} {'TV_price'}"
    print(hdr)
    print("-" * len(hdr))

    missing = []
    for tv in TV_TRADES_RAW:
        num, side, tv_entry_str, tv_price = tv[0], tv[1], tv[2], tv[3]
        entry_bar_utc = utc3_to_utc(tv_entry_str)  # = bar on which TV executes (bar+1 after signal)
        signal_bar_utc = entry_bar_utc - pd.Timedelta(minutes=15)  # = bar where RSI crosses

        # Does our signal array have a signal at signal_bar?
        our_sig = False
        if signal_bar_utc in ohlcv.index:
            idx = ohlcv.index.get_loc(signal_bar_utc)
            our_sig = bool(long_arr[idx]) if side == "long" else bool(short_arr[idx])
        else:
            pass  # bar not found

        # Find entry bar open price in our data
        entry_open = "N/A"
        if entry_bar_utc in ohlcv.index:
            entry_open = f"{ohlcv.loc[entry_bar_utc, 'open']:.1f}"

        status = "✓" if our_sig else "MISS"
        if not our_sig:
            missing.append((num, side, tv_entry_str, tv_price))

        print(
            f"{num:<4} {side:<6} {tv_entry_str:<21} {str(signal_bar_utc)[:19]:<21} "
            f"{status:<8} {str(entry_bar_utc)[:19]:<21} {entry_open:<11} {tv_price}"
        )

    print()
    print(f"Missing signals: {len(missing)}/{len(TV_TRADES_RAW)}")
    if missing:
        for m in missing:
            print(f"  #{m[0]} {m[1]} entry@{m[2]} price={m[3]}")

    # 4. Print RSI values at signal bars for missing trades
    if missing:
        print()
        print("=== RSI debug for missing signals ===")
        # compute RSI using same function as indicator_handlers
        try:
            from backend.backtesting.indicator_handlers import calculate_rsi

            rsi_arr = calculate_rsi(ohlcv["close"].values, period=14)
            rsi = pd.Series(rsi_arr, index=ohlcv.index)

            for m in missing:
                num, side, tv_entry_str, tv_price = m
                entry_bar_utc = utc3_to_utc(tv_entry_str)
                signal_bar_utc = entry_bar_utc - pd.Timedelta(minutes=15)
                prev_bar_utc = signal_bar_utc - pd.Timedelta(minutes=15)

                rsi_cur = rsi.get(signal_bar_utc, float("nan"))
                rsi_prev = rsi.get(prev_bar_utc, float("nan"))
                close_cur = ohlcv["close"].get(signal_bar_utc, float("nan"))

                print(
                    f"  #{num} {side} signal_bar={str(signal_bar_utc)[:19]}  "
                    f"RSI_prev={rsi_prev:.2f}  RSI_cur={rsi_cur:.2f}  close={close_cur:.1f}"
                )
                # For cross_level: need RSI_prev >= cross_short_level AND RSI_cur < cross_short_level
                # or RSI_prev <= cross_long_level AND RSI_cur > cross_long_level
                cross_long = 29
                cross_short = 53  # strategy param
                if side == "long":
                    expected = rsi_prev <= cross_long and rsi_cur > cross_long
                    print(
                        f"    cross_long({cross_long}): prev={rsi_prev:.2f}<={cross_long}? {rsi_prev <= cross_long}  cur={rsi_cur:.2f}>{cross_long}? {rsi_cur > cross_long}  → {expected}"
                    )
                else:
                    expected = rsi_prev >= cross_short and rsi_cur < cross_short
                    print(
                        f"    cross_short({cross_short}): prev={rsi_prev:.2f}>={cross_short}? {rsi_prev >= cross_short}  cur={rsi_cur:.2f}<{cross_short}? {rsi_cur < cross_short}  → {expected}"
                    )
        except Exception as e:
            print(f"RSI debug error: {e}")

    # 5. Run full backtest with IC=1M, slippage=0
    print()
    print("=== Running backtest with IC=1,000,000 slippage=0 ===")
    try:
        import asyncio

        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.service import BacktestService

        async def run_bt():
            svc = BacktestService()
            candles = await svc._fetch_historical_data(
                symbol="BTCUSDT",
                interval="15",
                start_date=pd.Timestamp("2025-11-01", tz="UTC"),
                end_date=pd.Timestamp("2026-02-22", tz="UTC"),
            )
            return candles

        candles = asyncio.run(run_bt())
        if candles is None:
            print("  Could not fetch candles for rerun")
            return

        # Generate signals
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
        row = cursor.fetchone()
        col_names = [d[0] for d in cursor.description]
        conn.close()
        strat = dict(zip(col_names, row, strict=True))
        builder_blocks = (
            json.loads(strat["builder_blocks"]) if isinstance(strat["builder_blocks"], str) else strat["builder_blocks"]
        )
        builder_connections = (
            json.loads(strat["builder_connections"])
            if isinstance(strat["builder_connections"], str)
            else strat["builder_connections"]
        )
        builder_graph_raw = (
            json.loads(strat["builder_graph"]) if isinstance(strat["builder_graph"], str) else strat["builder_graph"]
        )

        strategy_graph = {
            "name": strat["name"],
            "blocks": builder_blocks,
            "connections": builder_connections,
            "market_type": "linear",
            "direction": "both",
            "interval": "15",
        }
        if builder_graph_raw and isinstance(builder_graph_raw, dict) and builder_graph_raw.get("main_strategy"):
            strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

        adapter = StrategyBuilderAdapter(strategy_graph)
        signals = adapter.generate_signals(candles)
        long_entries = np.asarray(signals.entries.values, dtype=bool)
        short_entries = (
            np.asarray(signals.short_entries.values, dtype=bool)
            if signals.short_entries is not None
            else np.zeros(len(long_entries), dtype=bool)
        )
        long_exits = (
            np.asarray(signals.exits.values, dtype=bool)
            if signals.exits is not None
            else np.zeros(len(long_entries), dtype=bool)
        )
        short_exits = (
            np.asarray(signals.short_exits.values, dtype=bool)
            if signals.short_exits is not None
            else np.zeros(len(long_entries), dtype=bool)
        )

        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import TradeDirection

        bt_input = BacktestInput(
            candles=candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            initial_capital=1_000_000.0,
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=100.0,  # TV: BaseCash=100 per trade
            leverage=10,
            stop_loss=0.03,
            take_profit=0.015,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
        )

        engine = FallbackEngineV4()
        result = engine.run(bt_input)
        m = result.metrics

        # Print all available attributes
        print("\n  All metrics attrs:")
        for attr in sorted(dir(m)):
            if not attr.startswith("_"):
                val = getattr(m, attr, None)
                if not callable(val) and val is not None:
                    print(f"    {attr} = {val}")

        # TV metrics — from TradingView CSV export (a1-a4.csv, 121 trades)
        # NOTE: win_rate stored as fraction in engine (0.0-1.0), TV shows percentage
        # NOTE: avg_loss stored as negative in engine, TV shows positive magnitude
        TV = {
            "net_profit": (440.91, 1.0),  # (value, scale_our_by)
            "gross_profit": (1289.36, 1.0),
            "gross_loss": (848.46, 1.0),  # engine gross_loss is positive
            "commission_paid": (170.04, 1.0),
            "total_trades": (121, 1.0),
            "winning_trades": (94, 1.0),
            "losing_trades": (27, 1.0),
            "win_rate": (77.69, 100.0),  # engine=fraction → multiply by 100
            "profit_factor": (1.52, 1.0),
            "avg_win": (13.72, 1.0),
            "avg_loss": (-31.42, 1.0),  # engine stores as negative
            "largest_win": (13.72, 1.0),  # approx from TV
            "largest_loss": (-31.42, 1.0),  # approx from TV
            "avg_trade": (3.64, 1.0),  # TV: net_profit/total_trades
            "long_trades": (59, 1.0),
            "short_trades": (62, 1.0),
            "long_win_rate": (78.0, 100.0),  # approx from TV
            "short_win_rate": (77.42, 100.0),  # approx from TV
            "long_profit": (173.49, 1.0),  # TV long net profit
            "short_profit": (267.42, 1.0),  # TV short net profit
        }

        print(f"  {'Metric':<25} {'TV':>12} {'OUR':>14} {'DIFF':>10}")
        print(f"  {'-' * 65}")
        for k, (tv_v, scale) in TV.items():
            our_raw = getattr(m, k, None)
            if our_raw is None:
                print(f"  {k:<25} {tv_v:>12.2f} {'N/A':>14}")
                continue
            our_v = float(our_raw) * scale  # scale fraction→percent for win_rate etc
            diff = our_v - tv_v
            pct = abs(diff / tv_v * 100) if tv_v != 0 else 0
            mark = "✓ OK" if pct < 1.0 else f"DIFF {pct:.1f}%"
            print(f"  {k:<25} {tv_v:>12.2f} {our_v:>14.2f}   {mark}")

        print(f"\n  Trades total: {len(result.trades)} (TV=121)")

        # Print all engine trades for comparison with TV's 121
        print()
        print("=== Engine trades (all 118) vs TV trades ===")
        our_trades = result.trades

        print(
            f"{'#':<4} {'side':<7} {'entry_time':<22} {'entry_p':<12} {'exit_time':<22} {'exit_p':<12} {'pnl':<10} {'exit_r'}"
        )
        for i, t in enumerate(our_trades):
            # Find matching TV trade by entry_price (close match within 0.5)
            tv_match = None
            for tv_t in TV_TRADES_RAW:
                if tv_t[1] == t.direction and abs(tv_t[3] - t.entry_price) < 0.5:
                    tv_match = tv_t[0]
                    break
            marker = f"[TV#{tv_match}]" if tv_match else ""
            print(
                f"{i + 1:<4} {t.direction:<7} {str(t.entry_time)[:19]:<22} {t.entry_price:<12.1f} "
                f"{str(t.exit_time)[:19]:<22} {t.exit_price:<12.1f} {t.pnl:<10.2f} "
                f"{str(t.exit_reason)[:12]:<14} {marker}"
            )

        # Find TV trades NOT in our results
        print()
        print("=== TV trades NOT matched in our engine ===")
        our_entries = {(t.direction, round(t.entry_price, 1)) for t in our_trades}
        for tv_t in TV_TRADES_RAW:
            key = (tv_t[1], round(tv_t[3], 1))
            if key not in our_entries:
                print(f"  TV#{tv_t[0]} {tv_t[1]} entry={tv_t[3]} ({tv_t[2]} UTC+3)  exit={tv_t[6]} pnl={tv_t[7]}")

    except Exception as e:
        print(f"  Backtest error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
