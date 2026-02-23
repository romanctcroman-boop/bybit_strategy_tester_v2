"""
Rerun backtest for Strategy_RSI_L\\S_6 with TV-matching params (IC=1M, slippage=0)
and compare entry signals to TV CSV q4.csv (47 of 104 trades listed).

TV settings confirmed from q5.csv + DB (5c03fd86-a821-4a62-a783-4d617bf25bc7):
  Timeframe: 30 minutes
  IC=1,000,000  commission=0.07%  slippage=0 (TV)  leverage=10
  position_size=10%  BaseCash=100 USDT  direction=both
  SL=9.1%  TP=1.5%
  RSI period=14, source=close
  use_long_range=True,  long_rsi_more=10,  long_rsi_less=40
  use_short_range=True, short_rsi_more=50, short_rsi_less=65
  use_cross_level=True, cross_long_level=18, cross_short_level=63
  opposite_signal=False, use_cross_memory=False

NOTE: RSI_6 DB has _slippage=0.0005, but TV uses 0 ticks (Проскальзывание=0).
      We run with slippage=0 to match TV export exactly.

TV export results (from q1/q2/q3.csv):
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
STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"

# TV CSV — first 47 of 104 trades from q4.csv (UTC+3 timezone)
# Format: (num, side, entry_time_utc3, entry_price, exit_reason, exit_time_utc3, exit_price, pnl)
TV_TRADES_RAW = [
    (1, "short", "2025-01-01 19:30", 94126.2, "SL Hit", "2025-01-07 03:30", 102691.7, -92.46),
    (2, "short", "2025-01-07 04:00", 101996.9, "TP Hit", "2025-01-07 14:30", 100466.9, 13.61),
    (3, "long", "2025-01-08 00:00", 96494.5, "TP Hit", "2025-01-15 16:30", 97942.0, 13.59),
    (4, "short", "2025-01-15 20:00", 98970.0, "TP Hit", "2025-01-16 17:30", 97485.4, 13.61),
    (5, "short", "2025-01-17 06:00", 101068.3, "TP Hit", "2025-01-20 03:30", 99552.2, 13.61),
    (6, "short", "2025-01-20 15:30", 106664.3, "TP Hit", "2025-01-20 18:30", 105064.3, 13.61),
    (7, "short", "2025-01-21 17:00", 104455.7, "TP Hit", "2025-01-21 18:00", 102888.8, 13.61),
    (8, "short", "2025-01-22 00:00", 106100.0, "TP Hit", "2025-01-22 16:30", 104508.5, 13.61),
    (9, "short", "2025-01-23 18:30", 104189.8, "TP Hit", "2025-01-23 23:30", 102626.9, 13.61),
    (10, "short", "2025-01-24 22:00", 106304.3, "TP Hit", "2025-01-24 23:30", 104709.7, 13.61),
    (11, "short", "2025-01-26 08:00", 105142.8, "TP Hit", "2025-01-27 02:00", 103565.6, 13.61),
    (12, "long", "2025-01-27 03:30", 102800.0, "TP Hit", "2025-01-29 23:00", 104342.0, 13.59),
    (13, "short", "2025-01-30 01:00", 103679.0, "TP Hit", "2025-01-31 22:00", 102123.8, 13.61),
    (14, "short", "2025-02-04 05:30", 101020.9, "TP Hit", "2025-02-04 08:00", 99505.5, 13.61),
    (15, "short", "2025-02-06 10:30", 98144.7, "TP Hit", "2025-02-06 19:30", 96672.5, 13.61),
    (16, "short", "2025-02-07 18:30", 98466.4, "TP Hit", "2025-02-07 22:30", 96989.4, 13.61),
    (17, "short", "2025-02-09 05:30", 96680.0, "TP Hit", "2025-02-10 00:30", 95229.8, 13.61),
    (18, "short", "2025-02-10 15:00", 97629.9, "TP Hit", "2025-02-11 20:00", 96165.4, 13.61),
    (19, "long", "2025-02-11 23:30", 95233.2, "TP Hit", "2025-02-12 19:30", 96661.7, 13.59),
    (20, "short", "2025-02-12 21:00", 97321.3, "TP Hit", "2025-02-13 09:30", 95861.4, 13.61),
    (21, "short", "2025-02-14 04:00", 96723.2, "TP Hit", "2025-02-17 19:30", 95272.3, 13.61),
    (22, "short", "2025-02-19 16:00", 96157.2, "TP Hit", "2025-02-24 17:30", 94714.8, 13.61),
    (23, "long", "2025-02-25 14:00", 88176.2, "TP Hit", "2025-02-25 15:00", 89498.9, 13.59),
    (24, "short", "2025-02-27 14:30", 86599.6, "TP Hit", "2025-02-27 17:30", 85300.6, 13.61),
    (25, "short", "2025-02-28 21:00", 83566.2, "SL Hit", "2025-03-02 19:30", 91170.8, -92.46),
    (26, "short", "2025-03-03 04:30", 93061.1, "TP Hit", "2025-03-03 09:30", 91665.1, 13.61),
    (27, "short", "2025-03-03 17:30", 93163.9, "TP Hit", "2025-03-03 18:00", 89270.3, 40.42),
    (28, "short", "2025-03-05 00:00", 86841.8, "TP Hit", "2025-03-07 03:30", 85539.1, 13.61),
    (29, "short", "2025-03-07 18:30", 89183.3, "TP Hit", "2025-03-07 19:00", 87845.5, 13.61),
    (30, "long", "2025-03-09 18:00", 83558.3, "TP Hit", "2025-03-14 18:00", 84811.7, 13.59),
    (31, "short", "2025-03-14 21:00", 84332.4, "TP Hit", "2025-03-16 14:00", 83067.4, 13.61),
    (32, "long", "2025-03-16 15:30", 82818.4, "TP Hit", "2025-03-16 19:00", 84060.7, 13.59),
    (33, "short", "2025-03-17 23:30", 84083.2, "TP Hit", "2025-03-18 07:30", 82821.9, 13.61),
    (34, "short", "2025-03-19 04:30", 82812.5, "TP Hit", "2025-03-31 01:00", 81570.3, 13.61),
    (35, "short", "2025-03-31 20:00", 83246.7, "TP Hit", "2025-04-03 15:30", 81997.9, 13.61),
    (36, "short", "2025-04-06 05:00", 83390.0, "TP Hit", "2025-04-06 19:30", 82139.1, 13.61),
    (37, "long", "2025-04-06 22:30", 79474.0, "TP Hit", "2025-04-07 17:00", 80666.2, 13.59),
    (38, "short", "2025-04-08 02:30", 79821.1, "TP Hit", "2025-04-08 17:30", 78623.7, 13.61),
    (39, "short", "2025-04-10 05:00", 82220.2, "TP Hit", "2025-04-10 16:30", 80986.8, 13.61),
    (40, "short", "2025-04-11 16:00", 82093.8, "SL Hit", "2025-04-22 16:00", 89564.4, -92.46),
    (41, "short", "2025-04-23 05:00", 92612.0, "SL Hit", "2025-05-08 18:30", 101039.7, -92.46),
    (42, "short", "2025-05-09 05:30", 102685.6, "TP Hit", "2025-05-12 21:30", 101145.3, 13.61),
    (43, "short", "2025-05-13 15:30", 103496.3, "TP Hit", "2025-05-15 10:00", 101943.8, 13.61),
    (44, "short", "2025-05-15 21:30", 103450.6, "TP Hit", "2025-06-05 22:00", 101898.8, 13.61),
    (45, "long", "2025-06-06 00:30", 100946.9, "TP Hit", "2025-06-06 06:30", 102461.2, 13.59),
    (46, "short", "2025-06-06 16:00", 103704.8, "TP Hit", "2025-06-21 23:00", 102149.2, 13.61),
    (47, "short", "2025-06-23 12:00", 101826.8, "TP Hit", "2025-06-23 19:00", 100299.3, 13.61),
]


def load_ohlcv() -> pd.DataFrame:
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


def load_strategy_graph() -> dict:
    """Load Strategy_RSI_L\\S_6 from DB and build strategy_graph dict."""
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

    graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": builder_blocks,
        "connections": builder_connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if builder_graph_raw and isinstance(builder_graph_raw, dict) and builder_graph_raw.get("main_strategy"):
        graph["main_strategy"] = builder_graph_raw["main_strategy"]
    return graph


def generate_signals(ohlcv: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Generate signals using StrategyBuilderAdapter for Strategy_RSI_L\\S_6."""
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(load_strategy_graph())
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


def main() -> None:
    print("=" * 72)
    print("RSI_L\\S_6 — Signal comparison vs TV (q4.csv, UTC+3 → signal bar = entry-30min)")
    print("Timeframe: 30m | SL=9.1% | TP=1.5% | slippage=0 (TV) | IC=1,000,000")
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
        f"{'our sig':<8} {'entry bar(UTC)':<22} {'our open':<11} {'TV price'}"
    )
    print(hdr)
    print("-" * len(hdr))

    missing = []
    matched = 0
    for tv in TV_TRADES_RAW:
        num, side, tv_entry_str, tv_price = tv[0], tv[1], tv[2], tv[3]
        entry_bar_utc = utc3_to_utc(tv_entry_str)
        signal_bar_utc = entry_bar_utc - pd.Timedelta(minutes=30)

        our_sig = False
        if signal_bar_utc in ohlcv.index:
            idx = ohlcv.index.get_loc(signal_bar_utc)
            our_sig = bool(long_arr[idx]) if side == "long" else bool(short_arr[idx])

        entry_open = "N/A"
        if entry_bar_utc in ohlcv.index:
            entry_open = f"{ohlcv.loc[entry_bar_utc, 'open']:.1f}"

        status = "✓" if our_sig else "MISS"
        if not our_sig:
            missing.append((num, side, tv_entry_str, tv_price))
        else:
            matched += 1

        print(
            f"{num:<4} {side:<6} {tv_entry_str:<21} {str(signal_bar_utc)[:19]:<21} "
            f"{status:<8} {str(entry_bar_utc)[:19]:<22} {entry_open:<11} {tv_price}"
        )

    print()
    print(f"Matched: {matched}/{len(TV_TRADES_RAW)}  Missing: {len(missing)}/{len(TV_TRADES_RAW)}")
    if missing:
        print("Missing signals:")
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
                cross_long_level = 18
                cross_short_level = 63
                if side == "long":
                    range_ok = 10 <= rsi_cur <= 40
                    cross_ok = rsi_prev <= cross_long_level < rsi_cur
                    print(f"    long_range [10,40]: {rsi_cur:.2f} → in_range={range_ok}")
                    print(
                        f"    cross_long ({cross_long_level}): prev={rsi_prev:.2f} cur={rsi_cur:.2f} → cross={cross_ok}"
                    )
                else:
                    range_ok = 50 <= rsi_cur <= 65
                    cross_ok = rsi_prev >= cross_short_level > rsi_cur
                    print(f"    short_range [50,65]: {rsi_cur:.2f} → in_range={range_ok}")
                    print(
                        f"    cross_short ({cross_short_level}): prev={rsi_prev:.2f} cur={rsi_cur:.2f} → cross={cross_ok}"
                    )
        except Exception as exc:
            print(f"RSI debug error: {exc}")
            import traceback

            traceback.print_exc()

    # 5. Run full backtest with IC=1M, slippage=0 (matching TV)
    print()
    print("=== Running backtest with IC=1,000,000  slippage=0  (30m, SL=9.1%, TP=1.5%) ===")
    try:
        import asyncio

        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.service import BacktestService

        async def _fetch_candles() -> pd.DataFrame:
            svc = BacktestService()
            return await svc._fetch_historical_data(
                symbol="BTCUSDT",
                interval="30",
                start_date=pd.Timestamp("2025-01-01", tz="UTC"),
                end_date=pd.Timestamp("2026-02-24", tz="UTC"),
            )

        candles = asyncio.run(_fetch_candles())
        if candles is None or len(candles) == 0:
            print("  BacktestService returned no candles, using direct DB data...")
            candles = ohlcv
        else:
            print(f"  Candles via service: {len(candles)} bars  ({candles.index[0]} → {candles.index[-1]})")

        # Generate signals on service candles
        from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

        adapter = StrategyBuilderAdapter(load_strategy_graph())
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
            fixed_amount=100.0,  # TV: BaseCash=100 USDT
            leverage=10,
            stop_loss=0.091,  # SL=9.1%
            take_profit=0.015,  # TP=1.5%
            taker_fee=0.0007,  # commission=0.07%
            slippage=0.0,  # TV: 0 ticks (DB has 0.0005 but TV uses 0)
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
        )

        engine = FallbackEngineV4()
        result = engine.run(bt_input)
        m = result.metrics
        our_trades = result.trades

        # ── TV target metrics from q1/q2/q3.csv ──────────────────────────────
        TV_METRICS = {
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
            "avg_loss": (-92.43, 1.0),
            "largest_win": (40.42, 1.0),  # TV#27 bar-close exit
            "largest_loss": (-92.46, 1.0),
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
        all_ok = True
        for k, (tv_v, scale) in TV_METRICS.items():
            our_raw = getattr(m, k, None)
            if our_raw is None:
                print(f"  {k:<25} {tv_v:>12.4g} {'N/A':>14}   MISSING")
                all_ok = False
                continue
            our_v = float(our_raw) * scale
            diff = our_v - tv_v
            pct = abs(diff / tv_v * 100) if tv_v != 0 else 0.0
            mark = "✓ OK" if pct < 0.5 else f"DIFF {pct:.1f}%"
            if pct >= 0.5:
                all_ok = False
            print(f"  {k:<25} {tv_v:>12.4g} {our_v:>14.4g}   {mark}")

        print(f"\n  Trades total: {len(our_trades)} (TV=104)")
        if all_ok and len(our_trades) == 104:
            print("\n  ✅ FULL PARITY ACHIEVED — all metrics match TV within 0.5%")
        else:
            print("\n  ⚠️  Parity not yet complete — see DIFFs above")

        # ── Detailed trade list ───────────────────────────────────────────────
        print()
        print("=== Engine trades (all) ===")
        print(
            f"{'#':<4} {'side':<7} {'entry_time':<22} {'entry_p':<12} "
            f"{'exit_time':<22} {'exit_p':<12} {'pnl':<10} {'exit_r':<14} {'TV match'}"
        )
        tv_by_entry = {(t[1], round(t[3], 1)): t[0] for t in TV_TRADES_RAW}
        for i, t in enumerate(our_trades):
            key = (t.direction, round(t.entry_price, 1))
            tv_num = tv_by_entry.get(key, "")
            tv_label = f"[TV#{tv_num}]" if tv_num else ""
            print(
                f"{i + 1:<4} {t.direction:<7} {str(t.entry_time)[:19]:<22} {t.entry_price:<12.1f} "
                f"{str(t.exit_time)[:19]:<22} {t.exit_price:<12.1f} {t.pnl:<10.2f} "
                f"{str(t.exit_reason)[:12]:<14} {tv_label}"
            )

        # ── TV trades not found in our engine ────────────────────────────────
        print()
        print("=== TV trades (first 47) NOT found in our engine ===")
        our_entry_set = {(t.direction, round(t.entry_price, 1)) for t in our_trades}
        unmatched = [tv for tv in TV_TRADES_RAW if (tv[1], round(tv[3], 1)) not in our_entry_set]
        if unmatched:
            for tv_t in unmatched:
                print(
                    f"  TV#{tv_t[0]} {tv_t[1]} entry={tv_t[3]} ({tv_t[2]} UTC+3)  "
                    f"exit={tv_t[6]}  reason={tv_t[4]}  pnl={tv_t[7]}"
                )
        else:
            print("  All 47 listed TV trades matched ✓")

        # ── TV#27 special analysis (pnl=40.42) ───────────────────────────────
        print()
        print("=== TV#27 analysis (pnl=40.42 — bar-close exit when TP hit on entry bar) ===")
        tv27_entry_utc = utc3_to_utc("2025-03-03 17:30")
        tv27_naive = tv27_entry_utc.replace(tzinfo=None)
        for t in our_trades:
            entry_naive = (
                t.entry_time.replace(tzinfo=None)
                if hasattr(t.entry_time, "tzinfo") and t.entry_time.tzinfo
                else t.entry_time
            )
            if abs((entry_naive - tv27_naive).total_seconds()) < 1800:
                print(
                    f"  Our trade: entry={t.entry_time}  price={t.entry_price:.1f}  "
                    f"exit={t.exit_time}  price={t.exit_price:.1f}  pnl={t.pnl:.2f}  reason={t.exit_reason}"
                )
                if candles is not None and t.exit_time in candles.index:
                    bar = candles.loc[t.exit_time]
                    print(
                        f"  Exit bar OHLCV: O={bar['open']:.1f} H={bar['high']:.1f} "
                        f"L={bar['low']:.1f} C={bar['close']:.1f}"
                    )
                    print(f"  TV exits at bar close ({bar['close']:.1f}) since TP triggered on entry bar.")
                    print(f"  Our engine exits at TP price ({t.exit_price:.1f}) → gap = {40.42 - t.pnl:.2f} USDT")
                break
        else:
            print("  TV#27 not found in our engine near entry time 2025-03-03 14:30 UTC")

    except Exception as exc:
        print(f"  Backtest error: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
