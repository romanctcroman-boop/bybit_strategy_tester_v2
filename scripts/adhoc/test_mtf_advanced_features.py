"""
MTF + Advanced Features Test - 6+ Months Real Data

Tests the Multi-Timeframe system combined with all advanced FallbackEngineV4 features:
1. MTF + DCA (Dollar Cost Averaging)
2. MTF + Trailing Stop
3. MTF + Multi-Level TP
4. MTF + ATR-based TP/SL
5. MTF + Breakeven
6. MTF + Pyramiding
7. MTF + Time-Based Exits
8. MTF + Position Sizing Modes
9. Full Feature Combination Test

Run with: python test_mtf_advanced_features.py
"""

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from loguru import logger

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="{message}", level="INFO")


@dataclass
class TestResult:
    """Test result container."""

    name: str
    passed: bool
    duration: float
    details: dict


def load_candles_from_db(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    db_path: str = "data.sqlite3",
) -> pd.DataFrame:
    """Load candle data from database as DataFrame with datetime index."""
    conn = sqlite3.connect(db_path)

    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

    query = """
    SELECT open_time, open_price, high_price, low_price, close_price, volume
    FROM bybit_kline_audit
    WHERE symbol = ? AND interval = ? AND open_time >= ? AND open_time < ?
    ORDER BY open_time ASC
    """

    df = pd.read_sql_query(query, conn, params=[symbol, interval, start_ts, end_ts])
    conn.close()

    if df.empty:
        return df

    # Format for FallbackEngineV4: datetime index, standard column names
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.drop(columns=["open_time"], inplace=True)
    df.columns = ["open", "high", "low", "close", "volume"]

    return df


def generate_sma_crossover_signals(candles: pd.DataFrame, fast: int = 10, slow: int = 30):
    """Generate SMA crossover signals - more frequent than RSI."""
    close = candles["close"].values
    n = len(close)

    # Calculate SMAs
    fast_sma = np.full(n, np.nan)
    slow_sma = np.full(n, np.nan)

    for i in range(fast - 1, n):
        fast_sma[i] = np.mean(close[i - fast + 1 : i + 1])
    for i in range(slow - 1, n):
        slow_sma[i] = np.mean(close[i - slow + 1 : i + 1])

    # Generate signals
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    for i in range(slow, n):
        # Golden cross
        if fast_sma[i] > slow_sma[i] and fast_sma[i - 1] <= slow_sma[i - 1]:
            long_entries[i] = True
            short_exits[i] = True
        # Death cross
        elif fast_sma[i] < slow_sma[i] and fast_sma[i - 1] >= slow_sma[i - 1]:
            short_entries[i] = True
            long_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def create_htf_data_and_map(ltf_df: pd.DataFrame, htf_df: pd.DataFrame):
    """Create HTF index map for MTF."""
    from backend.backtesting.mtf.index_mapper import create_htf_index_map

    ltf_timestamps_ms = (ltf_df.index.astype(np.int64) // 10**6).values
    htf_timestamps_ms = (htf_df.index.astype(np.int64) // 10**6).values

    htf_index_map = create_htf_index_map(
        ltf_timestamps_ms, htf_timestamps_ms, lookahead_mode="none"
    )

    return np.array(htf_index_map, dtype=np.int32)


# ============================================================================
# TEST 1: MTF + DCA
# ============================================================================
def test_mtf_with_dca() -> TestResult:
    """Test MTF filter combined with DCA (Dollar Cost Averaging)."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput

        # Load 6 months data
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty or len(ltf_df) < 1000:
            return TestResult("MTF + DCA", False, time.time() - start, {"error": "Insufficient data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + DCA
        input_mtf_dca = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.03,  # 3% SL
            take_profit=0.05,  # 5% TP
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            # MTF parameters
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            mtf_neutral_zone_pct=0.01,
            # DCA parameters
            dca_enabled=True,
            dca_safety_orders=3,  # 3 safety orders
            dca_price_deviation=0.01,  # 1% deviation for each
            dca_step_scale=1.5,  # Step multiplier
            dca_volume_scale=1.5,  # Volume multiplier
            dca_base_order_size=0.1,  # 10% base order
            dca_safety_order_size=0.1,  # 10% safety order
        )

        engine = FallbackEngineV4()
        result_mtf_dca = engine.run(input_mtf_dca)

        # Run without DCA for comparison
        input_mtf_only = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.03,
            take_profit=0.05,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            mtf_neutral_zone_pct=0.01,
            dca_enabled=False,
        )
        result_mtf_only = engine.run(input_mtf_only)

        mtf_dca = result_mtf_dca.metrics
        mtf_only = result_mtf_only.metrics

        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "bars": len(ltf_df),
            # MTF + DCA
            "mtf_dca_trades": mtf_dca.total_trades,
            "mtf_dca_pnl": f"${mtf_dca.net_profit:.2f}",
            "mtf_dca_return": f"{mtf_dca.total_return:.2f}%",
            "mtf_dca_win_rate": f"{mtf_dca.win_rate * 100:.1f}%",
            "mtf_dca_max_dd": f"{mtf_dca.max_drawdown:.2f}%",
            # MTF Only
            "mtf_only_trades": mtf_only.total_trades,
            "mtf_only_pnl": f"${mtf_only.net_profit:.2f}",
            "mtf_only_return": f"{mtf_only.total_return:.2f}%",
            "mtf_only_win_rate": f"{mtf_only.win_rate * 100:.1f}%",
            "mtf_only_max_dd": f"{mtf_only.max_drawdown:.2f}%",
            # Comparison
            "dca_improves_pnl": mtf_dca.net_profit > mtf_only.net_profit,
        }

        passed = days >= 180 and result_mtf_dca.is_valid and result_mtf_only.is_valid
        return TestResult("MTF + DCA", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + DCA", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 2: MTF + Trailing Stop
# ============================================================================
def test_mtf_with_trailing_stop() -> TestResult:
    """Test MTF filter combined with Trailing Stop."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty or len(ltf_df) < 1000:
            return TestResult("MTF + Trailing", False, time.time() - start, {"error": "Insufficient data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + Trailing Stop
        input_trailing = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.05,  # Higher TP to let trailing work
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # Trailing Stop
            trailing_stop_enabled=True,
            trailing_stop_activation=0.015,  # Activate at 1.5% profit
            trailing_stop_distance=0.01,  # Trail at 1% distance
        )

        engine = FallbackEngineV4()
        result_trailing = engine.run(input_trailing)

        # Run without trailing
        input_no_trailing = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.05,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            trailing_stop_enabled=False,
        )
        result_no_trailing = engine.run(input_no_trailing)

        trailing = result_trailing.metrics
        no_trailing = result_no_trailing.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "trailing_trades": trailing.total_trades,
            "trailing_pnl": f"${trailing.net_profit:.2f}",
            "trailing_win_rate": f"{trailing.win_rate * 100:.1f}%",
            "trailing_max_dd": f"{trailing.max_drawdown:.2f}%",
            "no_trailing_trades": no_trailing.total_trades,
            "no_trailing_pnl": f"${no_trailing.net_profit:.2f}",
            "no_trailing_win_rate": f"{no_trailing.win_rate * 100:.1f}%",
            "trailing_improves": trailing.net_profit > no_trailing.net_profit,
        }

        passed = days >= 180 and result_trailing.is_valid
        return TestResult("MTF + Trailing", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + Trailing", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 3: MTF + Multi-Level TP
# ============================================================================
def test_mtf_with_multi_tp() -> TestResult:
    """Test MTF filter combined with Multi-Level Take Profit."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput, TpMode

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("MTF + Multi-TP", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + Multi-TP (4 levels)
        input_multi_tp = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # Multi-TP
            tp_mode=TpMode.MULTI,
            tp_levels=(0.01, 0.02, 0.03, 0.05),  # 1%, 2%, 3%, 5%
            tp_portions=(0.25, 0.25, 0.25, 0.25),  # Close 25% at each level
        )

        engine = FallbackEngineV4()
        result_multi = engine.run(input_multi_tp)

        # Run with single TP
        input_single_tp = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,  # Single 3% TP
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
        )
        result_single = engine.run(input_single_tp)

        multi = result_multi.metrics
        single = result_single.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "multi_tp_trades": multi.total_trades,
            "multi_tp_pnl": f"${multi.net_profit:.2f}",
            "multi_tp_win_rate": f"{multi.win_rate * 100:.1f}%",
            "multi_tp_max_dd": f"{multi.max_drawdown:.2f}%",
            "single_tp_trades": single.total_trades,
            "single_tp_pnl": f"${single.net_profit:.2f}",
            "single_tp_win_rate": f"{single.win_rate * 100:.1f}%",
            "multi_tp_improves": multi.net_profit > single.net_profit,
        }

        passed = days >= 180 and result_multi.is_valid
        return TestResult("MTF + Multi-TP", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + Multi-TP", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 4: MTF + ATR-Based TP/SL
# ============================================================================
def test_mtf_with_atr() -> TestResult:
    """Test MTF filter combined with ATR-based TP/SL."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput, SlMode, TpMode

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("MTF + ATR", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + ATR-based exits
        input_atr = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.05,  # Max limit for ATR SL
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # ATR-based TP/SL
            tp_mode=TpMode.ATR,
            sl_mode=SlMode.ATR,
            atr_period=14,
            atr_tp_multiplier=2.5,  # TP at 2.5 ATR
            atr_sl_multiplier=1.5,  # SL at 1.5 ATR
            sl_max_limit_enabled=True,  # Limit SL to stop_loss value
        )

        engine = FallbackEngineV4()
        result_atr = engine.run(input_atr)

        # Run with fixed TP/SL
        input_fixed = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
        )
        result_fixed = engine.run(input_fixed)

        atr = result_atr.metrics
        fixed = result_fixed.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "atr_trades": atr.total_trades,
            "atr_pnl": f"${atr.net_profit:.2f}",
            "atr_win_rate": f"{atr.win_rate * 100:.1f}%",
            "atr_max_dd": f"{atr.max_drawdown:.2f}%",
            "fixed_trades": fixed.total_trades,
            "fixed_pnl": f"${fixed.net_profit:.2f}",
            "fixed_win_rate": f"{fixed.win_rate * 100:.1f}%",
            "atr_improves": atr.net_profit > fixed.net_profit,
        }

        passed = days >= 180 and result_atr.is_valid
        return TestResult("MTF + ATR", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + ATR", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 5: MTF + Breakeven
# ============================================================================
def test_mtf_with_breakeven() -> TestResult:
    """Test MTF filter combined with Breakeven Stop."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput, TpMode

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("MTF + Breakeven", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + Multi-TP + Breakeven (breakeven requires Multi-TP)
        input_be = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # Multi-TP (required for breakeven)
            tp_mode=TpMode.MULTI,
            tp_levels=(0.01, 0.02, 0.03, 0.05),
            tp_portions=(0.25, 0.25, 0.25, 0.25),
            # Breakeven - activates after first TP
            breakeven_enabled=True,
            breakeven_mode="average",  # Move SL to average entry
            breakeven_offset=0.001,  # Small offset above breakeven
        )

        engine = FallbackEngineV4()
        result_be = engine.run(input_be)

        # Run without breakeven (same Multi-TP but no breakeven)
        input_no_be = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # Multi-TP (same as with breakeven for fair comparison)
            tp_mode=TpMode.MULTI,
            tp_levels=(0.01, 0.02, 0.03, 0.05),
            tp_portions=(0.25, 0.25, 0.25, 0.25),
            breakeven_enabled=False,  # Only difference - no breakeven
        )
        result_no_be = engine.run(input_no_be)

        be = result_be.metrics
        no_be = result_no_be.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "be_trades": be.total_trades,
            "be_pnl": f"${be.net_profit:.2f}",
            "be_win_rate": f"{be.win_rate * 100:.1f}%",
            "be_max_dd": f"{be.max_drawdown:.2f}%",
            "no_be_trades": no_be.total_trades,
            "no_be_pnl": f"${no_be.net_profit:.2f}",
            "be_improves": be.net_profit > no_be.net_profit,
        }

        passed = days >= 180 and result_be.is_valid
        return TestResult("MTF + Breakeven", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + Breakeven", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 6: MTF + Pyramiding
# ============================================================================
def test_mtf_with_pyramiding() -> TestResult:
    """Test MTF filter combined with Pyramiding (multiple entries)."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("MTF + Pyramiding", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + Pyramiding (allow 3 entries)
        input_pyramid = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.04,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # Pyramiding
            pyramiding=3,  # Allow up to 3 entries per direction
            close_entries_rule="ALL",  # Close all on exit signal
        )

        engine = FallbackEngineV4()
        result_pyramid = engine.run(input_pyramid)

        # Run without pyramiding
        input_no_pyramid = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.04,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            pyramiding=1,  # Only 1 entry (default)
        )
        result_no_pyramid = engine.run(input_no_pyramid)

        pyramid = result_pyramid.metrics
        no_pyramid = result_no_pyramid.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "pyramid_trades": pyramid.total_trades,
            "pyramid_pnl": f"${pyramid.net_profit:.2f}",
            "pyramid_win_rate": f"{pyramid.win_rate * 100:.1f}%",
            "pyramid_max_dd": f"{pyramid.max_drawdown:.2f}%",
            "no_pyramid_trades": no_pyramid.total_trades,
            "no_pyramid_pnl": f"${no_pyramid.net_profit:.2f}",
            "pyramid_improves": pyramid.net_profit > no_pyramid.net_profit,
        }

        passed = days >= 180 and result_pyramid.is_valid
        return TestResult("MTF + Pyramiding", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + Pyramiding", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 7: MTF + Time-Based Exits
# ============================================================================
def test_mtf_with_time_exits() -> TestResult:
    """Test MTF filter combined with Time-Based Exits."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("MTF + Time Exit", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Run with MTF + Time-based exit (max 48 bars = 12 hours on 15m)
        input_time = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.05,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            # Time-based exits
            max_bars_in_trade=48,  # Exit after 48 bars (12 hours)
            exit_end_of_week=True,  # Exit on Friday close
            exit_before_weekend=2,  # 2 hours before weekend
        )

        engine = FallbackEngineV4()
        result_time = engine.run(input_time)

        # Run without time exits
        input_no_time = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.05,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            max_bars_in_trade=0,  # No time limit
            exit_end_of_week=False,
        )
        result_no_time = engine.run(input_no_time)

        time_exit = result_time.metrics
        no_time = result_no_time.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "time_exit_trades": time_exit.total_trades,
            "time_exit_pnl": f"${time_exit.net_profit:.2f}",
            "time_exit_win_rate": f"{time_exit.win_rate * 100:.1f}%",
            "no_time_trades": no_time.total_trades,
            "no_time_pnl": f"${no_time.net_profit:.2f}",
            "time_exit_improves": time_exit.net_profit > no_time.net_profit,
        }

        passed = days >= 180 and result_time.is_valid
        return TestResult("MTF + Time Exit", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + Time Exit", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 8: MTF + Position Sizing Modes
# ============================================================================
def test_mtf_with_position_sizing() -> TestResult:
    """Test MTF filter combined with different Position Sizing modes."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("MTF + Sizing", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        engine = FallbackEngineV4()
        results = {}

        # Test each position sizing mode
        for mode in ["fixed", "risk", "volatility"]:
            input_data = BacktestInput(
                symbol="BTCUSDT",
                interval="15m",
                initial_capital=10000.0,
                leverage=5,
                direction="both",
                stop_loss=0.02,
                take_profit=0.03,
                taker_fee=0.0007,
                candles=ltf_df,
                long_entries=long_entries,
                long_exits=long_exits,
                short_entries=short_entries,
                short_exits=short_exits,
                use_bar_magnifier=False,
                mtf_enabled=True,
                mtf_htf_candles=htf_df,
                mtf_htf_index_map=htf_index_map,
                mtf_filter_type="sma",
                mtf_filter_period=50,
                # Position sizing
                position_sizing_mode=mode,
                risk_per_trade=0.02,  # 2% risk per trade
                volatility_target=0.02,  # 2% volatility target
            )

            result = engine.run(input_data)
            results[mode] = result.metrics

        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "fixed_trades": results["fixed"].total_trades,
            "fixed_pnl": f"${results['fixed'].net_profit:.2f}",
            "risk_trades": results["risk"].total_trades,
            "risk_pnl": f"${results['risk'].net_profit:.2f}",
            "volatility_trades": results["volatility"].total_trades,
            "volatility_pnl": f"${results['volatility'].net_profit:.2f}",
            "best_mode": max(results.keys(), key=lambda k: results[k].net_profit),
        }

        passed = days >= 180
        return TestResult("MTF + Sizing", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("MTF + Sizing", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


# ============================================================================
# TEST 9: Full Feature Combination
# ============================================================================
def test_full_feature_combination() -> TestResult:
    """Test MTF with ALL advanced features combined."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.interfaces import TpMode as TpModeEnum

        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty:
            return TestResult("Full Features", False, time.time() - start, {"error": "No data"})

        htf_index_map = create_htf_data_and_map(ltf_df, htf_df)
        long_entries, long_exits, short_entries, short_exits = generate_sma_crossover_signals(ltf_df)

        # Full feature combination (use Multi-TP for breakeven compatibility)

        input_full = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.05,  # Max limit
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            # MTF
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
            mtf_neutral_zone_pct=0.01,
            # Multi-level TP (required for breakeven to work)
            tp_mode=TpModeEnum.MULTI,
            tp_levels=(0.01, 0.02, 0.03, 0.05),
            tp_portions=(0.25, 0.25, 0.25, 0.25),
            # Trailing Stop
            trailing_stop_enabled=True,
            trailing_stop_activation=0.02,
            trailing_stop_distance=0.01,
            # Breakeven (works with Multi-TP)
            breakeven_enabled=True,
            breakeven_mode="average",
            breakeven_offset=0.001,
            # DCA
            dca_enabled=True,
            dca_safety_orders=2,
            dca_price_deviation=0.015,
            dca_step_scale=1.5,
            dca_volume_scale=1.3,
            # Time exits
            max_bars_in_trade=96,  # 24 hours
            # Position sizing
            position_sizing_mode="risk",
            risk_per_trade=0.02,
        )

        engine = FallbackEngineV4()
        result_full = engine.run(input_full)

        # Baseline - only MTF
        input_baseline = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0007,
            candles=ltf_df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
            mtf_enabled=True,
            mtf_htf_candles=htf_df,
            mtf_htf_index_map=htf_index_map,
            mtf_filter_type="sma",
            mtf_filter_period=50,
        )
        result_baseline = engine.run(input_baseline)

        full = result_full.metrics
        baseline = result_baseline.metrics
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        details = {
            "period_days": days,
            "bars": len(ltf_df),
            # Full features
            "full_trades": full.total_trades,
            "full_pnl": f"${full.net_profit:.2f}",
            "full_return": f"{full.total_return:.2f}%",
            "full_win_rate": f"{full.win_rate * 100:.1f}%",
            "full_max_dd": f"{full.max_drawdown:.2f}%",
            "full_sharpe": f"{full.sharpe_ratio:.2f}",
            "full_profit_factor": f"{full.profit_factor:.2f}",
            # Baseline
            "baseline_trades": baseline.total_trades,
            "baseline_pnl": f"${baseline.net_profit:.2f}",
            "baseline_return": f"{baseline.total_return:.2f}%",
            "baseline_win_rate": f"{baseline.win_rate * 100:.1f}%",
            # Comparison
            "features_improve_pnl": full.net_profit > baseline.net_profit,
            "features_improve_dd": full.max_drawdown < baseline.max_drawdown,
        }

        passed = days >= 180 and result_full.is_valid
        return TestResult("Full Features", passed, time.time() - start, details)

    except Exception as e:
        import traceback
        return TestResult("Full Features", False, time.time() - start, {"error": str(e), "traceback": traceback.format_exc()})


def main():
    """Run all MTF + Advanced Features tests."""
    print("=" * 80)
    print("MTF + ADVANCED FEATURES TEST - 6+ Months Real Data")
    print("=" * 80)
    print()

    tests = [
        test_mtf_with_dca,
        test_mtf_with_trailing_stop,
        test_mtf_with_multi_tp,
        test_mtf_with_atr,
        test_mtf_with_breakeven,
        test_mtf_with_pyramiding,
        test_mtf_with_time_exits,
        test_mtf_with_position_sizing,
        test_full_feature_combination,
    ]

    results = []
    total_time = 0.0

    for test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Running: {test_func.__name__}")
        print("=" * 60)

        result = test_func()
        results.append(result)
        total_time += result.duration

        status = "✅ PASSED" if result.passed else "❌ FAILED"
        print(f"\n{status} - {result.name} ({result.duration:.2f}s)")
        print("Details:")
        for key, value in result.details.items():
            print(f"  {key}: {value}")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Total time: {total_time:.2f}s")

    print("\n" + "-" * 80)
    for r in results:
        status = "✅" if r.passed else "❌"
        print(f"{status} {r.name}: {r.duration:.2f}s")

    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
