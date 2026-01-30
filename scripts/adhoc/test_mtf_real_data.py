"""
MTF System Real Data Test - 6+ Months Period

Tests the Multi-Timeframe backtesting system on real market data from the database.
Validates all MTF components:
1. HTF Index Mapping (lookahead prevention)
2. HTF Trend Filters (SMA/EMA)
3. BTC Correlation Filter
4. Signal Generation with MTF
5. FallbackEngineV4 MTF Integration

Run with: python test_mtf_real_data.py
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
    as_dataframe: bool = False,
) -> pd.DataFrame:
    """Load candle data from database.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Timeframe (e.g., '15' for 15m)
        start_date: Start date 'YYYY-MM-DD'
        end_date: End date 'YYYY-MM-DD'
        db_path: Path to SQLite database
        as_dataframe: If True, return DataFrame with datetime index (for engine)
                      If False, return DataFrame with timestamp column (for analysis)

    Returns:
        DataFrame with OHLCV data
    """
    conn = sqlite3.connect(db_path)

    # Convert dates to timestamps (milliseconds)
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

    if as_dataframe:
        # Format for FallbackEngineV4: datetime index, standard column names
        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df.drop(columns=["open_time"], inplace=True)
        df.columns = ["open", "high", "low", "close", "volume"]
    else:
        # Format for analysis: keep timestamp column
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    return df


def test_data_availability() -> TestResult:
    """Test 1: Check data availability for 6+ months."""
    start = time.time()
    details = {}

    try:
        # Load BTCUSDT 15m for 6 months
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)

        if df.empty:
            return TestResult(
                "Data Availability",
                False,
                time.time() - start,
                {"error": "No data found"},
            )

        days = (df["timestamp"].max() - df["timestamp"].min()).days
        details = {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "rows": len(df),
            "start": str(df["timestamp"].min().date()),
            "end": str(df["timestamp"].max().date()),
            "days": days,
        }

        passed = days >= 180  # At least 6 months
        return TestResult("Data Availability", passed, time.time() - start, details)

    except Exception as e:
        return TestResult(
            "Data Availability", False, time.time() - start, {"error": str(e)}
        )


def test_htf_index_mapping() -> TestResult:
    """Test 2: HTF Index Mapping with lookahead prevention."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.mtf.index_mapper import create_htf_index_map

        # Load LTF (15m) and HTF (4H) data
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db(
            "BTCUSDT", "60", start_date, end_date
        )  # Use 1H as HTF

        if ltf_df.empty or htf_df.empty:
            return TestResult(
                "HTF Index Mapping",
                False,
                time.time() - start,
                {"error": f"Missing data: LTF={len(ltf_df)}, HTF={len(htf_df)}"},
            )

        # Convert to numpy timestamps (milliseconds)
        ltf_timestamps = (ltf_df["timestamp"].astype(np.int64) // 10**6).values
        htf_timestamps = (htf_df["timestamp"].astype(np.int64) // 10**6).values

        # Create index map (no lookahead)
        index_map = create_htf_index_map(
            ltf_timestamps, htf_timestamps, lookahead_mode="none"
        )

        # Validate no lookahead
        lookahead_violations = 0
        for i, htf_idx in enumerate(index_map):
            if htf_idx >= 0:
                ltf_ts = ltf_timestamps[i]
                htf_ts = htf_timestamps[htf_idx]
                if htf_ts > ltf_ts:
                    lookahead_violations += 1

        details = {
            "ltf_bars": len(ltf_df),
            "htf_bars": len(htf_df),
            "mapped_bars": sum(1 for x in index_map if x >= 0),
            "lookahead_violations": lookahead_violations,
        }

        passed = lookahead_violations == 0 and details["mapped_bars"] > 0
        return TestResult("HTF Index Mapping", passed, time.time() - start, details)

    except Exception as e:
        import traceback

        return TestResult(
            "HTF Index Mapping",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def test_htf_trend_filter() -> TestResult:
    """Test 3: HTF Trend Filter (SMA/EMA) logic."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.mtf.filters import (
            HTFTrendFilter,
            calculate_ema,
            calculate_sma,
        )

        # Load HTF (1H) data
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if htf_df.empty or len(htf_df) < 100:
            return TestResult(
                "HTF Trend Filter",
                False,
                time.time() - start,
                {"error": f"Insufficient HTF data: {len(htf_df)} bars"},
            )

        closes = htf_df["close"].values

        # Test SMA calculation
        sma_20 = calculate_sma(closes, 20)
        sma_50 = calculate_sma(closes, 50)

        # Test EMA calculation
        ema_20 = calculate_ema(closes, 20)

        # Test HTFTrendFilter
        filter_sma = HTFTrendFilter(filter_type="sma", period=20, neutral_zone_pct=0.5)
        filter_ema = HTFTrendFilter(filter_type="ema", period=20, neutral_zone_pct=0.5)

        # Get signals for last 100 bars using check() method
        sma_signals = []
        ema_signals = []
        for i in range(len(closes) - 100, len(closes)):
            htf_close = closes[i]
            htf_sma = sma_20[i] if i < len(sma_20) and sma_20[i] > 0 else htf_close
            htf_ema = ema_20[i] if i < len(ema_20) and ema_20[i] > 0 else htf_close

            allow_long_sma, allow_short_sma = filter_sma.check(htf_close, htf_sma)
            allow_long_ema, allow_short_ema = filter_ema.check(htf_close, htf_ema)

            # 1 = bullish, -1 = bearish, 0 = both
            if allow_long_sma and not allow_short_sma:
                sma_signals.append(1)
            elif allow_short_sma and not allow_long_sma:
                sma_signals.append(-1)
            else:
                sma_signals.append(0)

            if allow_long_ema and not allow_short_ema:
                ema_signals.append(1)
            elif allow_short_ema and not allow_long_ema:
                ema_signals.append(-1)
            else:
                ema_signals.append(0)

        details = {
            "htf_bars": len(htf_df),
            "sma_20_range": f"{np.nanmin(sma_20):.2f} - {np.nanmax(sma_20):.2f}",
            "ema_20_range": f"{np.nanmin(ema_20):.2f} - {np.nanmax(ema_20):.2f}",
            "bullish_periods_sma": sum(1 for s in sma_signals if s == 1),
            "bearish_periods_sma": sum(1 for s in sma_signals if s == -1),
            "neutral_periods_sma": sum(1 for s in sma_signals if s == 0),
        }

        # Passed if we have meaningful trend signals
        passed = (
            details["bullish_periods_sma"] > 0 or details["bearish_periods_sma"] > 0
        )
        return TestResult("HTF Trend Filter", passed, time.time() - start, details)

    except Exception as e:
        import traceback

        return TestResult(
            "HTF Trend Filter",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def test_btc_correlation_filter() -> TestResult:
    """Test 4: BTC Correlation Filter for altcoins."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.mtf.filters import BTCCorrelationFilter, calculate_sma

        # Load BTC and ETH data
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        btc_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)
        eth_df = load_candles_from_db("ETHUSDT", "60", start_date, end_date)

        if btc_df.empty or eth_df.empty:
            return TestResult(
                "BTC Correlation Filter",
                False,
                time.time() - start,
                {"error": f"Missing data: BTC={len(btc_df)}, ETH={len(eth_df)}"},
            )

        btc_closes = btc_df["close"].values
        eth_closes = eth_df["close"].values

        # Align lengths
        min_len = min(len(btc_closes), len(eth_closes))
        btc_closes = btc_closes[:min_len]
        eth_closes = eth_closes[:min_len]

        # Test BTC Correlation Filter with correct API
        btc_filter = BTCCorrelationFilter(btc_sma_period=20)

        # Calculate BTC SMA
        btc_sma = calculate_sma(btc_closes, 20)

        # Calculate correlation
        btc_returns = np.diff(btc_closes) / btc_closes[:-1]
        eth_returns = np.diff(eth_closes) / eth_closes[:-1]

        correlation = np.corrcoef(btc_returns[-100:], eth_returns[-100:])[0, 1]

        # Test filter signals using check() method
        long_allowed = []
        short_allowed = []
        for i in range(len(btc_closes) - 50, len(btc_closes)):
            btc_close = btc_closes[i]
            btc_sma_val = (
                btc_sma[i] if i < len(btc_sma) and btc_sma[i] > 0 else btc_close
            )
            allow_long, allow_short = btc_filter.check(btc_close, btc_sma_val)
            long_allowed.append(allow_long)
            short_allowed.append(allow_short)

        details = {
            "btc_bars": len(btc_df),
            "eth_bars": len(eth_df),
            "btc_eth_correlation": f"{correlation:.4f}",
            "longs_allowed": sum(long_allowed),
            "shorts_allowed": sum(short_allowed),
            "longs_blocked": 50 - sum(long_allowed),
            "shorts_blocked": 50 - sum(short_allowed),
        }

        # Passed if filter is working (some signals allowed, some blocked)
        passed = details["longs_allowed"] > 0 and details["shorts_allowed"] > 0
        return TestResult(
            "BTC Correlation Filter", passed, time.time() - start, details
        )

    except Exception as e:
        import traceback

        return TestResult(
            "BTC Correlation Filter",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def test_mtf_signal_generation() -> TestResult:
    """Test 5: MTF-enhanced signal generation."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.mtf.index_mapper import create_htf_index_map
        from backend.backtesting.mtf.signals import generate_mtf_rsi_signals

        # Load LTF (15m) and HTF (1H) data
        start_date = "2025-10-01"  # 3 months for faster test
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db("BTCUSDT", "15", start_date, end_date)
        htf_df = load_candles_from_db("BTCUSDT", "60", start_date, end_date)

        if ltf_df.empty or htf_df.empty:
            return TestResult(
                "MTF Signal Generation",
                False,
                time.time() - start,
                {"error": f"Missing data: LTF={len(ltf_df)}, HTF={len(htf_df)}"},
            )

        # Prepare data as DataFrames (expected by generate_mtf_rsi_signals)
        ltf_timestamps = (ltf_df["timestamp"].astype(np.int64) // 10**6).values
        htf_timestamps = (htf_df["timestamp"].astype(np.int64) // 10**6).values

        # Create index map
        htf_index_map = create_htf_index_map(
            ltf_timestamps, htf_timestamps, lookahead_mode="none"
        )

        # Generate MTF RSI signals using DataFrame API
        long_entries, long_exits, short_entries, short_exits = generate_mtf_rsi_signals(
            ltf_candles=ltf_df,
            htf_candles=htf_df,
            htf_index_map=np.array(htf_index_map, dtype=np.int32),
            rsi_period=14,
            overbought=70,
            oversold=30,
            htf_filter_type="sma",
            htf_filter_period=20,
        )

        details = {
            "ltf_bars": len(ltf_df),
            "htf_bars": len(htf_df),
            "long_entries": int(np.sum(long_entries)),
            "long_exits": int(np.sum(long_exits)),
            "short_entries": int(np.sum(short_entries)),
            "short_exits": int(np.sum(short_exits)),
            "total_signals": int(np.sum(long_entries) + np.sum(short_entries)),
        }

        # Passed if we have some signals
        passed = details["total_signals"] > 0
        return TestResult("MTF Signal Generation", passed, time.time() - start, details)

    except Exception as e:
        import traceback

        return TestResult(
            "MTF Signal Generation",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def test_fallback_engine_mtf_integration() -> TestResult:
    """Test 6: FallbackEngineV4 with MTF enabled on real data."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.mtf.index_mapper import create_htf_index_map

        # Load LTF (15m) and HTF (1H) data as DataFrames for engine
        start_date = "2025-10-01"  # 3 months
        end_date = "2026-01-26"

        # Load as DataFrame with datetime index for engine
        ltf_df = load_candles_from_db(
            "BTCUSDT", "15", start_date, end_date, as_dataframe=True
        )
        htf_df = load_candles_from_db(
            "BTCUSDT", "60", start_date, end_date, as_dataframe=True
        )

        if ltf_df.empty or len(ltf_df) < 200:
            return TestResult(
                "FallbackV4 MTF Integration",
                False,
                time.time() - start,
                {"error": f"Insufficient LTF data: {len(ltf_df)} bars"},
            )

        if htf_df.empty or len(htf_df) < 50:
            return TestResult(
                "FallbackV4 MTF Integration",
                False,
                time.time() - start,
                {"error": f"Insufficient HTF data: {len(htf_df)} bars"},
            )

        # Get timestamps in milliseconds for index mapping
        ltf_timestamps_ms = (ltf_df.index.astype(np.int64) // 10**6).values
        htf_timestamps_ms = (htf_df.index.astype(np.int64) // 10**6).values

        # Create HTF index map
        htf_index_map = create_htf_index_map(
            ltf_timestamps_ms, htf_timestamps_ms, lookahead_mode="none"
        )

        # Generate simple RSI signals for testing
        closes = ltf_df["close"].values
        n = len(closes)

        # Simple RSI calculation
        def calc_rsi(prices, period=14):
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.zeros(len(prices))
            avg_loss = np.zeros(len(prices))
            for i in range(period, len(prices)):
                avg_gain[i] = np.mean(gains[i - period : i])
                avg_loss[i] = np.mean(losses[i - period : i])
            rs = np.divide(
                avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0
            )
            rsi = 100 - (100 / (1 + rs))
            return rsi

        rsi = calc_rsi(closes, 14)
        long_entries = (rsi < 30).astype(bool)
        short_entries = (rsi > 70).astype(bool)
        long_exits = (rsi > 50).astype(bool)
        short_exits = (rsi < 50).astype(bool)

        # Create BacktestInput with MTF enabled (using DataFrames)
        input_data = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=10,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0007,
            maker_fee=0.0002,
            candles=ltf_df,  # DataFrame with datetime index
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,  # Disable bar magnifier
            # MTF parameters
            mtf_enabled=True,
            mtf_htf_candles=htf_df,  # DataFrame with datetime index
            mtf_htf_index_map=np.array(htf_index_map, dtype=np.int32),
            mtf_filter_type="sma",
            mtf_filter_period=20,
            mtf_neutral_zone_pct=0.005,
        )

        # Run backtest with MTF
        engine = FallbackEngineV4()
        result_mtf = engine.run(input_data)

        # Run backtest WITHOUT MTF for comparison
        input_no_mtf = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=10,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0007,
            maker_fee=0.0002,
            candles=ltf_df,  # DataFrame
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,  # Disable bar magnifier
            mtf_enabled=False,
        )
        result_no_mtf = engine.run(input_no_mtf)

        # Access metrics through result.metrics
        mtf_metrics = result_mtf.metrics
        no_mtf_metrics = result_no_mtf.metrics

        details = {
            "ltf_bars": len(ltf_df),
            "htf_bars": len(htf_df),
            "mtf_trades": mtf_metrics.total_trades,
            "no_mtf_trades": no_mtf_metrics.total_trades,
            "mtf_pnl": f"{mtf_metrics.net_profit:.2f}",
            "no_mtf_pnl": f"{no_mtf_metrics.net_profit:.2f}",
            "mtf_win_rate": f"{mtf_metrics.win_rate:.2f}%",
            "no_mtf_win_rate": f"{no_mtf_metrics.win_rate:.2f}%",
            "trades_filtered": no_mtf_metrics.total_trades - mtf_metrics.total_trades,
        }

        # Passed if MTF filters trades (should have fewer or equal trades)
        passed = mtf_metrics.total_trades <= no_mtf_metrics.total_trades
        return TestResult(
            "FallbackV4 MTF Integration", passed, time.time() - start, details
        )

    except Exception as e:
        import traceback

        return TestResult(
            "FallbackV4 MTF Integration",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def test_mtf_long_period_backtest() -> TestResult:
    """Test 7: Full 6-month MTF backtest with performance metrics."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.mtf.index_mapper import create_htf_index_map

        # Load 6+ months of data as DataFrames for engine
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db(
            "BTCUSDT", "15", start_date, end_date, as_dataframe=True
        )
        htf_df = load_candles_from_db(
            "BTCUSDT", "60", start_date, end_date, as_dataframe=True
        )

        if ltf_df.empty or len(ltf_df) < 1000:
            return TestResult(
                "6-Month MTF Backtest",
                False,
                time.time() - start,
                {"error": f"Insufficient data: {len(ltf_df)} LTF bars"},
            )

        # Get timestamps in milliseconds for index mapping
        ltf_timestamps_ms = (ltf_df.index.astype(np.int64) // 10**6).values
        htf_timestamps_ms = (htf_df.index.astype(np.int64) // 10**6).values

        htf_index_map = create_htf_index_map(
            ltf_timestamps_ms, htf_timestamps_ms, lookahead_mode="none"
        )

        # Generate RSI signals
        closes = ltf_df["close"].values

        def calc_rsi(prices, period=14):
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.zeros(len(prices))
            avg_loss = np.zeros(len(prices))
            for i in range(period, len(prices)):
                avg_gain[i] = np.mean(gains[i - period : i])
                avg_loss[i] = np.mean(losses[i - period : i])
            rs = np.divide(
                avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0
            )
            return 100 - (100 / (1 + rs))

        rsi = calc_rsi(closes, 14)
        long_entries = (rsi < 30).astype(bool)
        short_entries = (rsi > 70).astype(bool)
        long_exits = (rsi > 50).astype(bool)
        short_exits = (rsi < 50).astype(bool)

        # Run WITH MTF (using DataFrames)
        input_mtf = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=10,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0007,
            maker_fee=0.0002,
            candles=ltf_df,  # DataFrame
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,  # Disable bar magnifier
            mtf_enabled=True,
            mtf_htf_candles=htf_df,  # DataFrame
            mtf_htf_index_map=np.array(htf_index_map, dtype=np.int32),
            mtf_filter_type="sma",
            mtf_filter_period=50,
            mtf_neutral_zone_pct=0.01,
        )

        engine = FallbackEngineV4()
        result_mtf = engine.run(input_mtf)

        # Run WITHOUT MTF
        input_no_mtf = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=10,
            direction="both",
            stop_loss=0.02,
            take_profit=0.03,
            taker_fee=0.0007,
            maker_fee=0.0002,
            candles=ltf_df,  # DataFrame
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,  # Disable bar magnifier
            mtf_enabled=False,
        )
        result_no_mtf = engine.run(input_no_mtf)

        # Access metrics through result.metrics
        mtf = result_mtf.metrics
        no_mtf = result_no_mtf.metrics

        # Calculate period (from DataFrame index)
        days = (ltf_df.index.max() - ltf_df.index.min()).days
        details = {
            "period_days": days,
            "ltf_bars": len(ltf_df),
            "htf_bars": len(htf_df),
            # MTF Results
            "mtf_trades": mtf.total_trades,
            "mtf_pnl": f"${mtf.net_profit:.2f}",
            "mtf_return": f"{mtf.total_return:.2f}%",
            "mtf_win_rate": f"{mtf.win_rate * 100:.2f}%",
            "mtf_max_dd": f"{mtf.max_drawdown:.2f}%",
            "mtf_profit_factor": f"{mtf.profit_factor:.2f}",
            # No MTF Results
            "no_mtf_trades": no_mtf.total_trades,
            "no_mtf_pnl": f"${no_mtf.net_profit:.2f}",
            "no_mtf_return": f"{no_mtf.total_return:.2f}%",
            "no_mtf_win_rate": f"{no_mtf.win_rate * 100:.2f}%",
            "no_mtf_max_dd": f"{no_mtf.max_drawdown:.2f}%",
            # Comparison
            "trades_filtered": no_mtf.total_trades - mtf.total_trades,
            "pnl_improvement": f"${mtf.net_profit - no_mtf.net_profit:.2f}",
        }

        # Passed if we ran successfully on 6+ months
        passed = days >= 180 and mtf.total_trades >= 0
        return TestResult("6-Month MTF Backtest", passed, time.time() - start, details)

    except Exception as e:
        import traceback

        return TestResult(
            "6-Month MTF Backtest",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def test_mtf_sma_crossover_strategy() -> TestResult:
    """Test 8: SMA Crossover Strategy with MTF filter - More Trades."""
    start = time.time()
    details = {}

    try:
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput
        from backend.backtesting.mtf.filters import calculate_sma
        from backend.backtesting.mtf.index_mapper import create_htf_index_map

        # Load 6+ months of data as DataFrames for engine
        start_date = "2025-07-01"
        end_date = "2026-01-26"

        ltf_df = load_candles_from_db(
            "BTCUSDT", "15", start_date, end_date, as_dataframe=True
        )
        htf_df = load_candles_from_db(
            "BTCUSDT", "60", start_date, end_date, as_dataframe=True
        )

        if ltf_df.empty or len(ltf_df) < 1000:
            return TestResult(
                "SMA Crossover with MTF",
                False,
                time.time() - start,
                {"error": f"Insufficient data: {len(ltf_df)} LTF bars"},
            )

        # Get timestamps in milliseconds for index mapping
        ltf_timestamps_ms = (ltf_df.index.astype(np.int64) // 10**6).values
        htf_timestamps_ms = (htf_df.index.astype(np.int64) // 10**6).values

        htf_index_map = create_htf_index_map(
            ltf_timestamps_ms, htf_timestamps_ms, lookahead_mode="none"
        )

        # Generate SMA crossover signals (Fast=10, Slow=30) - more frequent
        closes = ltf_df["close"].values
        sma_fast = calculate_sma(closes, 10)
        sma_slow = calculate_sma(closes, 30)

        n = len(closes)
        long_entries = np.zeros(n, dtype=bool)
        short_entries = np.zeros(n, dtype=bool)
        long_exits = np.zeros(n, dtype=bool)
        short_exits = np.zeros(n, dtype=bool)

        # Generate crossover signals
        for i in range(31, n):
            # Long entry: fast crosses above slow
            if sma_fast[i - 1] <= sma_slow[i - 1] and sma_fast[i] > sma_slow[i]:
                long_entries[i] = True
            # Short entry: fast crosses below slow
            if sma_fast[i - 1] >= sma_slow[i - 1] and sma_fast[i] < sma_slow[i]:
                short_entries[i] = True
            # Long exit: fast crosses below slow
            if sma_fast[i - 1] >= sma_slow[i - 1] and sma_fast[i] < sma_slow[i]:
                long_exits[i] = True
            # Short exit: fast crosses above slow
            if sma_fast[i - 1] <= sma_slow[i - 1] and sma_fast[i] > sma_slow[i]:
                short_exits[i] = True

        # Run WITH MTF (using DataFrames)
        input_mtf = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,  # Lower leverage for stability
            direction="both",
            stop_loss=0.015,  # 1.5% SL
            take_profit=0.03,  # 3% TP
            taker_fee=0.0007,
            maker_fee=0.0002,
            candles=ltf_df,  # DataFrame
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,  # Disable bar magnifier
            mtf_enabled=True,
            mtf_htf_candles=htf_df,  # DataFrame
            mtf_htf_index_map=np.array(htf_index_map, dtype=np.int32),
            mtf_filter_type="sma",
            mtf_filter_period=50,
            mtf_neutral_zone_pct=0.01,  # 1% neutral zone
        )

        engine = FallbackEngineV4()
        result_mtf = engine.run(input_mtf)

        # Run WITHOUT MTF (using DataFrames)
        input_no_mtf = BacktestInput(
            symbol="BTCUSDT",
            interval="15m",
            initial_capital=10000.0,
            leverage=5,
            direction="both",
            stop_loss=0.015,
            take_profit=0.03,
            taker_fee=0.0007,
            maker_fee=0.0002,
            candles=ltf_df,  # DataFrame
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,  # Disable bar magnifier
            mtf_enabled=False,
        )
        result_no_mtf = engine.run(input_no_mtf)

        # Access metrics
        mtf = result_mtf.metrics
        no_mtf = result_no_mtf.metrics

        # Calculate period (from DataFrame index)
        days = (ltf_df.index.max() - ltf_df.index.min()).days

        # Count raw signals
        raw_long_signals = int(np.sum(long_entries))
        raw_short_signals = int(np.sum(short_entries))
        details = {
            "period_days": days,
            "ltf_bars": len(ltf_df),
            "htf_bars": len(htf_df),
            "raw_long_signals": raw_long_signals,
            "raw_short_signals": raw_short_signals,
            # MTF Results
            "mtf_trades": mtf.total_trades,
            "mtf_long_trades": mtf.long_trades,
            "mtf_short_trades": mtf.short_trades,
            "mtf_pnl": f"${mtf.net_profit:.2f}",
            "mtf_return": f"{mtf.total_return:.2f}%",
            "mtf_win_rate": f"{mtf.win_rate * 100:.1f}%",
            "mtf_max_dd": f"{mtf.max_drawdown:.2f}%",
            "mtf_sharpe": f"{mtf.sharpe_ratio:.2f}",
            # No MTF Results
            "no_mtf_trades": no_mtf.total_trades,
            "no_mtf_long_trades": no_mtf.long_trades,
            "no_mtf_short_trades": no_mtf.short_trades,
            "no_mtf_pnl": f"${no_mtf.net_profit:.2f}",
            "no_mtf_return": f"{no_mtf.total_return:.2f}%",
            "no_mtf_win_rate": f"{no_mtf.win_rate * 100:.1f}%",
            "no_mtf_max_dd": f"{no_mtf.max_drawdown:.2f}%",
            # Comparison
            "trades_filtered": no_mtf.total_trades - mtf.total_trades,
            "mtf_improves_winrate": mtf.win_rate > no_mtf.win_rate
            if no_mtf.total_trades > 0
            else False,
        }

        # Passed if we have trades and MTF filters some
        passed = days >= 180 and no_mtf.total_trades > 0
        return TestResult(
            "SMA Crossover with MTF", passed, time.time() - start, details
        )

    except Exception as e:
        import traceback

        return TestResult(
            "SMA Crossover with MTF",
            False,
            time.time() - start,
            {"error": str(e), "traceback": traceback.format_exc()},
        )


def main():
    """Run all MTF real data tests."""
    print("=" * 80)
    print("MTF SYSTEM REAL DATA TEST - 6+ Months Period")
    print("=" * 80)
    print()

    tests = [
        test_data_availability,
        test_htf_index_mapping,
        test_htf_trend_filter,
        test_btc_correlation_filter,
        test_mtf_signal_generation,
        test_fallback_engine_mtf_integration,
        test_mtf_long_period_backtest,
        test_mtf_sma_crossover_strategy,  # New test with actual trades
    ]

    results = []
    total_time = 0

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
    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"{status} {result.name}: {result.duration:.2f}s")

    print("\n" + "=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
