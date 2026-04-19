"""
Rerun backtest for Strategy_RSI_L\\S_5 with TV-matching params (IC=1M, slippage=0)
and compare entry signals to TV CSV s4.csv.

TV settings confirmed from s5.csv + DB (684869b5-70f5-4464-9825-97a8c4e52f96):
  Timeframe: 30 minutes  (KEY DIFF from RSI_4's 15m)
  IC=1,000,000  commission=0.07%  slippage=0  leverage=10
  position_size=10%  BaseCash=100 USDT  direction=both
  SL=9.1%  TP=1.5%
  RSI period=14, source=close
  use_long_range=True,  long_rsi_more=10,  long_rsi_less=40
  use_short_range=True, short_rsi_more=50, short_rsi_less=65
  use_cross_level=True, cross_long_level=18, cross_short_level=63
  opposite_signal=False, use_cross_memory=False

TV export results (from s1/s2/s3.csv):
  net_profit=381.47  gross_profit=1305.81  gross_loss=924.34
  total_trades=104  winning=94  losing=10  win_rate=90.38%
  avg_win=13.89  avg_loss=-92.43  commission_paid=145.35
  long_trades=20 (18W/2L)  short_trades=84 (76W/8L)
  profit_factor=1.413  Sharpe=-17.511  Sortino=-0.998
  Date range: 2025-01-01 19:30 → 2026-02-24 00:30 UTC+3
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
KLINES_DB_PATH = r"d:\bybit_strategy_tester_v2\bybit_klines_15m.db"
STRATEGY_ID = "684869b5-70f5-4464-9825-97a8c4e52f96"

# TV CSV — all 47 available trades from s4.csv (UTC+3 timezone)
# Format: (num, side, entry_time_utc3, entry_price, exit_reason, exit_time_utc3, exit_price, pnl)
TV_TRADES_RAW = [
    (1, "short", "2025-01-01 19:30", 94126.2, "SL Hit", "2025-01-07 03:30", 102691.7, -92.46),
    (2, "short", "2025-01-07 04:00", 101996.9, "TP Hit", "2025-01-07 14:30", 100466.9, 13.61),
    (3, "long", "2025-01-08 00:00", 96494.5, "TP Hit", "2025-01-15 16:30", 97942.0, 13.59),
    (4, "short", "2025-01-15 20:00", 98970.0, "TP Hit", "2025-01-16 17:30", 97485.4, 13.61),
    (5, "short", "2025-01-17 06:00", 101068.3, "TP Hit", "2025-01-20 03:30", 99552.2, 13.61),
    (6, "short", "2025-01-20 05:30", 103736.4, "TP Hit", "2025-01-21 16:00", 102233.5, 13.61),
    (7, "long", "2025-01-21 21:30", 101155.5, "TP Hit", "2025-01-22 17:30", 102671.7, 13.59),
    (8, "short", "2025-01-22 19:30", 102400.9, "TP Hit", "2025-01-23 08:00", 100901.6, 13.61),
    (9, "short", "2025-01-23 17:30", 105086.5, "TP Hit", "2025-01-27 03:30", 103460.1, 13.61),
    (10, "short", "2025-01-27 22:00", 104520.5, "TP Hit", "2025-01-28 14:30", 103028.3, 13.61),
    (11, "short", "2025-01-28 21:30", 102781.7, "TP Hit", "2025-01-29 09:00", 101251.9, 13.61),
    (12, "short", "2025-01-30 01:30", 103500.4, "TP Hit", "2025-01-30 07:30", 101979.4, 13.61),
    (13, "short", "2025-01-30 20:30", 103297.0, "TP Hit", "2025-01-31 03:30", 101778.3, 13.61),
    (14, "short", "2025-01-31 12:30", 103867.4, "TP Hit", "2025-01-31 21:30", 102339.8, 13.61),
    (15, "long", "2025-02-03 05:30", 97094.8, "TP Hit", "2025-02-06 07:00", 98541.5, 13.59),
    (16, "short", "2025-02-06 23:00", 97540.4, "TP Hit", "2025-02-07 16:30", 96032.4, 13.61),
    (17, "short", "2025-02-10 20:30", 96994.2, "TP Hit", "2025-02-11 08:30", 95514.3, 13.61),
    (18, "long", "2025-02-11 13:30", 95313.0, "TP Hit", "2025-02-14 11:00", 96742.7, 13.59),
    (19, "short", "2025-02-14 17:30", 97972.8, "TP Hit", "2025-02-14 23:30", 96458.6, 13.61),
    (20, "short", "2025-02-17 18:30", 97218.4, "TP Hit", "2025-02-18 06:30", 95730.3, 13.61),
    (21, "short", "2025-02-19 21:00", 96057.3, "TP Hit", "2025-02-20 09:30", 94616.4, 13.61),
    (22, "long", "2025-02-21 00:30", 97611.8, "TP Hit", "2025-02-28 19:00", 99074.2, 13.59),
    (23, "short", "2025-03-01 00:00", 84342.6, "TP Hit", "2025-03-01 07:00", 83077.4, 13.61),
    (24, "short", "2025-03-01 19:30", 84945.3, "TP Hit", "2025-03-02 07:00", 83580.4, 13.61),
    (25, "short", "2025-03-02 12:30", 86932.8, "TP Hit", "2025-03-02 18:30", 85611.1, 13.61),
    (26, "short", "2025-03-03 12:30", 91157.7, "TP Hit", "2025-03-03 17:30", 89740.6, 13.61),
    (27, "short", "2025-03-03 17:30", 93163.9, "exit", "2025-03-03 18:00", None, 40.42),  # unusual pnl
    (28, "short", "2025-03-04 02:30", 91185.6, "TP Hit", "2025-03-04 12:30", 89748.2, 13.61),
    (29, "short", "2025-03-04 19:00", 89979.1, "TP Hit", "2025-03-05 13:00", 88579.7, 13.61),
    (30, "long", "2025-03-06 08:30", 86866.4, "TP Hit", "2025-03-10 11:00", 88169.2, 13.59),
    (31, "short", "2025-03-10 15:30", 79898.9, "TP Hit", "2025-03-11 08:30", 78698.9, 13.61),
    (32, "short", "2025-03-11 14:30", 82395.2, "TP Hit", "2025-03-12 02:30", 81158.4, 13.61),
    (33, "short", "2025-03-13 07:00", 83497.7, "TP Hit", "2025-03-13 09:30", 82195.3, 13.61),
    (34, "short", "2025-03-13 12:30", 84157.7, "TP Hit", "2025-03-13 16:00", 82875.3, 13.61),
    (35, "short", "2025-03-14 00:00", 82000.0, "TP Hit", "2025-03-14 12:00", 80770.0, 13.61),
    (36, "long", "2025-03-14 18:30", 84117.0, "SL Hit", "2025-03-18 22:30", 76570.8, -92.33),
    (37, "long", "2025-03-18 23:30", 83879.5, "SL Hit", "2025-03-19 19:00", 76330.0, -92.33),
    (38, "short", "2025-03-19 21:30", 85124.2, "TP Hit", "2025-03-20 10:30", 83797.5, 13.61),
    (39, "long", "2025-03-21 00:30", 87098.7, "TP Hit", "2025-03-21 22:30", 88408.8, 13.59),
    (40, "short", "2025-03-23 22:00", 88003.7, "TP Hit", "2025-03-24 18:00", 86683.6, 13.61),
    (41, "long", "2025-03-28 12:00", 86682.5, "TP Hit", "2025-03-31 14:30", 87985.6, 13.59),
    (42, "short", "2025-04-02 08:00", 83177.9, "TP Hit", "2025-04-02 21:30", 81920.1, 13.61),
    (43, "short", "2025-04-03 11:00", 84000.0, "TP Hit", "2025-04-03 16:30", 82730.0, 13.61),
    (44, "short", "2025-04-04 02:00", 83200.0, "TP Hit", "2025-04-04 14:00", 81967.0, 13.61),
    (45, "short", "2025-04-07 08:30", 77200.0, "TP Hit", "2025-04-07 17:00", 76043.0, 13.61),
    (46, "long", "2025-04-09 21:00", 79000.0, "SL Hit", "2025-04-14 23:00", 71920.0, -92.33),
    (47, "short", "2025-04-14 23:30", 85174.3, "SL Hit", "2025-04-25 07:00", 92633.5, -92.46),
]


def load_ohlcv():
    """Load BTCUSDT 30m klines from DB (data.sqlite3, bybit_kline_audit table)."""
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 25, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def generate_signals(ohlcv: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Generate signals using StrategyBuilderAdapter for Strategy_RSI_L\\S_5."""
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
        "interval": "30",  # 30-minute timeframe
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
    print("RSI_L\\S_5 — Signal comparison vs TV (UTC+3 → signal bar = entry-30min)")
    print("Timeframe: 30m | SL=9.1% | TP=1.5% | use_long_range + use_short_range + use_cross")
    print("=" * 72)

    # 1. Load OHLCV (30m bars)
    ohlcv = load_ohlcv()
    print(f"OHLCV: {len(ohlcv)} bars  ({ohlcv.index[0]}  →  {ohlcv.index[-1]})")

    # 2. Generate signals
    long_arr, short_arr = generate_signals(ohlcv)
    print(f"Signals: {long_arr.sum()} long, {short_arr.sum()} short  (total raw = {long_arr.sum() + short_arr.sum()})")

    # 3. Map TV trade entry-time → signal-bar (= entry_bar - 30min for 30m TF)
    print()
    print("=== TV trades vs our signals ===")
    hdr = (
        f"{'#':<4} {'side':<6} {'TV entry(UTC+3)':<21} {'signal bar(UTC)':<21} "
        f"{'our sig':<8} {'entry bar':<21} {'entry_O':<11} {'TV_price'}"
    )
    print(hdr)
    print("-" * len(hdr))

    missing = []
    for tv in TV_TRADES_RAW:
        num, side, tv_entry_str, tv_price = tv[0], tv[1], tv[2], tv[3]
        entry_bar_utc = utc3_to_utc(tv_entry_str)  # bar on which TV executes (bar+1 after signal)
        signal_bar_utc = entry_bar_utc - pd.Timedelta(minutes=30)  # bar where RSI signal fires

        # Check if our signal array has a signal at signal_bar
        our_sig = False
        if signal_bar_utc in ohlcv.index:
            idx = ohlcv.index.get_loc(signal_bar_utc)
            our_sig = bool(long_arr[idx]) if side == "long" else bool(short_arr[idx])

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

    # 4. RSI debug for missing signals
    if missing:
        print()
        print("=== RSI debug for missing signals ===")
        try:
            from backend.backtesting.indicator_handlers import calculate_rsi

            rsi_arr = calculate_rsi(ohlcv["close"].values, period=14)
            rsi = pd.Series(rsi_arr, index=ohlcv.index)

            for m in missing:
                num, side, tv_entry_str, tv_price = m
                entry_bar_utc = utc3_to_utc(tv_entry_str)
                signal_bar_utc = entry_bar_utc - pd.Timedelta(minutes=30)
                prev_bar_utc = signal_bar_utc - pd.Timedelta(minutes=30)

                rsi_cur = rsi.get(signal_bar_utc, float("nan"))
                rsi_prev = rsi.get(prev_bar_utc, float("nan"))
                close_cur = ohlcv["close"].get(signal_bar_utc, float("nan"))

                print(
                    f"  #{num} {side} signal_bar={str(signal_bar_utc)[:19]}  "
                    f"RSI_prev={rsi_prev:.2f}  RSI_cur={rsi_cur:.2f}  close={close_cur:.1f}"
                )
                # cross_long_level=18, cross_short_level=63
                cross_long = 18
                cross_short = 63
                # long_range: [10, 40], short_range: [50, 65]
                if side == "long":
                    range_ok = 10 <= rsi_cur <= 40
                    cross_ok = rsi_prev <= cross_long and rsi_cur > cross_long
                    print(f"    long_range [10,40]: RSI={rsi_cur:.2f} in range? {range_ok}")
                    print(
                        f"    cross_long ({cross_long}): prev={rsi_prev:.2f}<={cross_long}? {rsi_prev <= cross_long}"
                        f"  cur={rsi_cur:.2f}>{cross_long}? {rsi_cur > cross_long}  → cross={cross_ok}"
                    )
                else:
                    range_ok = 50 <= rsi_cur <= 65
                    cross_ok = rsi_prev >= cross_short and rsi_cur < cross_short
                    print(f"    short_range [50,65]: RSI={rsi_cur:.2f} in range? {range_ok}")
                    print(
                        f"    cross_short ({cross_short}): prev={rsi_prev:.2f}>={cross_short}? {rsi_prev >= cross_short}"
                        f"  cur={rsi_cur:.2f}<{cross_short}? {rsi_cur < cross_short}  → cross={cross_ok}"
                    )
        except Exception as e:
            print(f"RSI debug error: {e}")
            import traceback

            traceback.print_exc()

    # 5. Run full backtest with IC=1M, slippage=0
    print()
    print("=== Running backtest with IC=1,000,000 slippage=0 (30m, SL=9.1%, TP=1.5%) ===")
    try:
        import asyncio

        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.service import BacktestService

        async def run_bt():
            svc = BacktestService()
            candles = await svc._fetch_historical_data(
                symbol="BTCUSDT",
                interval="30",
                start_date=pd.Timestamp("2025-01-01", tz="UTC"),
                end_date=pd.Timestamp("2026-02-24", tz="UTC"),
            )
            return candles

        candles = asyncio.run(run_bt())
        if candles is None:
            print("  Could not fetch candles via BacktestService, using direct DB load instead...")
            candles = ohlcv  # fallback to already-loaded data
        else:
            print(f"  Candles via service: {len(candles)} bars  ({candles.index[0]} → {candles.index[-1]})")

        # Generate signals on candles from service
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
            "interval": "30",
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
            fixed_amount=100.0,  # TV: BaseCash=100 USDT per trade
            leverage=10,
            stop_loss=0.091,  # SL=9.1% (RSI_5 uses much wider SL than RSI_4's 3%)
            take_profit=0.015,  # TP=1.5%
            taker_fee=0.0007,  # commission=0.07%
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
        )

        engine = FallbackEngineV4()
        result = engine.run(bt_input)
        m = result.metrics

        # TV target metrics (from s1/s2/s3.csv)
        TV = {
            "net_profit": (381.47, 1.0),
            "gross_profit": (1305.81, 1.0),
            "gross_loss": (924.34, 1.0),  # magnitude (positive)
            "commission_paid": (145.35, 1.0),
            "total_trades": (104, 1.0),
            "winning_trades": (94, 1.0),
            "losing_trades": (10, 1.0),
            "win_rate": (90.38, 100.0),  # engine stores fraction → ×100
            "profit_factor": (1.413, 1.0),
            "avg_win": (13.89, 1.0),
            "avg_loss": (-92.43, 1.0),  # negative
            "largest_win": (40.42, 1.0),  # trade #27 unusual exit
            "largest_loss": (-92.46, 1.0),  # negative
            "avg_trade": (3.67, 1.0),
            "long_trades": (20, 1.0),
            "short_trades": (84, 1.0),
            "long_profit": (59.95, 1.0),
            "short_profit": (321.52, 1.0),
            "long_win_rate": (90.0, 100.0),
            "short_win_rate": (90.48, 100.0),
        }

        print(f"\n  {'Metric':<25} {'TV':>12} {'OUR':>14} {'DIFF':>10}")
        print(f"  {'-' * 65}")
        for k, (tv_v, scale) in TV.items():
            our_raw = getattr(m, k, None)
            if our_raw is None:
                print(f"  {k:<25} {tv_v:>12.2f} {'N/A':>14}")
                continue
            our_v = float(our_raw) * scale
            diff = our_v - tv_v
            pct = abs(diff / tv_v * 100) if tv_v != 0 else 0
            mark = "✓ OK" if pct < 1.0 else f"DIFF {pct:.1f}%"
            print(f"  {k:<25} {tv_v:>12.4g} {our_v:>14.4g}   {mark}")

        print(f"\n  Trades total: {len(result.trades)} (TV=104)")

        # Print all engine trades
        print()
        print("=== Engine trades vs TV trades ===")
        print(
            f"{'#':<4} {'side':<7} {'entry_time':<22} {'entry_p':<12} "
            f"{'exit_time':<22} {'exit_p':<12} {'pnl':<10} {'exit_r':<14} {'TV match'}"
        )
        our_trades = result.trades
        tv_by_entry = {(t[1], round(t[3], 1)): t[0] for t in TV_TRADES_RAW}

        for i, t in enumerate(our_trades):
            key = (t.direction, round(t.entry_price, 1))
            tv_match = tv_by_entry.get(key, "")
            marker = f"[TV#{tv_match}]" if tv_match else ""
            print(
                f"{i + 1:<4} {t.direction:<7} {str(t.entry_time)[:19]:<22} {t.entry_price:<12.1f} "
                f"{str(t.exit_time)[:19]:<22} {t.exit_price:<12.1f} {t.pnl:<10.2f} "
                f"{str(t.exit_reason)[:12]:<14} {marker}"
            )

        # TV trades not matched in our engine
        print()
        print("=== TV trades NOT matched in our engine ===")
        our_entries = {(t.direction, round(t.entry_price, 1)) for t in our_trades}
        unmatched = [tv for tv in TV_TRADES_RAW if (tv[1], round(tv[3], 1)) not in our_entries]
        if unmatched:
            for tv_t in unmatched:
                print(
                    f"  TV#{tv_t[0]} {tv_t[1]} entry={tv_t[3]} ({tv_t[2]} UTC+3)  "
                    f"exit={tv_t[6]}  reason={tv_t[4]}  pnl={tv_t[7]}"
                )
        else:
            print("  All TV trades (from s4.csv partial 47) are matched ✓")

        # Check trade #27 special exit (pnl=40.42 instead of standard 13.61)
        print()
        print("=== Trade #27 analysis (unusual pnl=40.42, TV entry=2025-03-03 17:30 UTC+3) ===")
        tv27_entry_utc3 = "2025-03-03 17:30"
        tv27_entry_utc = utc3_to_utc(tv27_entry_utc3)
        # Find in our engine trades
        tv27_naive = tv27_entry_utc.replace(tzinfo=None)
        for t in our_trades:
            entry_naive = (
                t.entry_time.replace(tzinfo=None)
                if hasattr(t.entry_time, "tzinfo") and t.entry_time.tzinfo
                else t.entry_time
            )
            if abs((entry_naive - tv27_naive).total_seconds()) < 1800:  # within 30min
                print(
                    f"  Our trade: entry={t.entry_time} price={t.entry_price:.1f} "
                    f"exit={t.exit_time} price={t.exit_price:.1f} pnl={t.pnl:.2f} reason={t.exit_reason}"
                )
                if candles is not None and t.exit_time in candles.index:
                    bar = candles.loc[t.exit_time]
                    print(
                        f"  Exit bar OHLCV: O={bar['open']:.1f} H={bar['high']:.1f} "
                        f"L={bar['low']:.1f} C={bar['close']:.1f}"
                    )
                break
        else:
            print("  Trade #27 not found in our engine near that time")

    except Exception as e:
        print(f"  Backtest error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
