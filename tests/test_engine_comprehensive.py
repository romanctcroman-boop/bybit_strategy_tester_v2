"""
🔬 Comprehensive Engine Test Suite

Tests FallbackEngineV2 with:
- Multiple strategies (RSI, MACD, Bollinger, Stochastic, MA Crossover, SuperTrend)
- Multiple symbols from real DB (BTCUSDT, ETHUSDT if available)
- Multiple timeframes (15m, 1H, 4H)
- Different directions (long, short, both)
- Various SL/TP configurations
- Leverage variations
- Bar Magnifier on/off

Uses REAL data from SQLite database.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from loguru import logger

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.universal_engine.signal_generator import (
    calculate_bollinger_numba,
    calculate_macd_numba,
    calculate_rsi_numba,
    calculate_stochastic_numba,
    calculate_supertrend_numba,
    generate_bb_signals_numba,
    generate_macd_signals_numba,
    generate_rsi_signals_numba,
)

# Database path
DB_PATH = PROJECT_ROOT / "data.sqlite3"

# =============================================================================
# DATA LOADING
# =============================================================================


def load_candles_from_db(
    symbol: str = "BTCUSDT",
    interval: str = "15",
    limit: int = 5000,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame | None:
    """Load candles from database."""
    if not DB_PATH.exists():
        logger.warning(f"Database not found: {DB_PATH}")
        return None

    conn = sqlite3.connect(str(DB_PATH))
    try:
        date_filter = ""
        if start_date:
            ts_start = int(start_date.timestamp() * 1000)
            date_filter += f" AND open_time >= {ts_start}"
        if end_date:
            ts_end = int(end_date.timestamp() * 1000)
            date_filter += f" AND open_time <= {ts_end}"

        query = f"""
            SELECT 
                open_time as timestamp,
                open_price as open,
                high_price as high,
                low_price as low,
                close_price as close,
                volume
            FROM bybit_kline_audit
            WHERE symbol = ? AND interval = ? {date_filter}
            ORDER BY open_time ASC
            LIMIT ?
        """
        df = pd.read_sql(query, conn, params=[symbol, interval, limit])

        if df.empty:
            logger.warning(f"No data for {symbol} {interval}")
            return None

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        logger.info(f"Loaded {len(df)} candles for {symbol} {interval}m")
        return df

    except Exception as e:
        logger.error(f"Failed to load candles: {e}")
        return None
    finally:
        conn.close()


def get_available_symbols() -> list[str]:
    """Get list of symbols with data."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql(
            "SELECT DISTINCT symbol FROM bybit_kline_audit WHERE interval='15' LIMIT 10",
            conn,
        )
        return df["symbol"].tolist()
    except Exception:
        return []
    finally:
        conn.close()


def get_available_intervals(symbol: str = "BTCUSDT") -> list[str]:
    """Get available intervals for symbol."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql(
            f"SELECT DISTINCT interval FROM bybit_kline_audit WHERE symbol='{symbol}'",
            conn,
        )
        return df["interval"].tolist()
    except Exception:
        return []
    finally:
        conn.close()


# =============================================================================
# SIGNAL GENERATORS
# =============================================================================


def generate_rsi_signals(
    df: pd.DataFrame,
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
    direction: TradeDirection = TradeDirection.BOTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate RSI signals."""
    close = df["close"].values.astype(np.float64)
    rsi = calculate_rsi_numba(close, period)

    dir_code = {"long": 0, "short": 1, "both": 2}.get(direction.value, 2)
    return generate_rsi_signals_numba(rsi, oversold, overbought, dir_code)


def generate_macd_signals(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    direction: TradeDirection = TradeDirection.BOTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate MACD signals."""
    close = df["close"].values.astype(np.float64)
    macd_line, signal_line, histogram = calculate_macd_numba(close, fast, slow, signal)

    dir_code = {"long": 0, "short": 1, "both": 2}.get(direction.value, 2)
    return generate_macd_signals_numba(macd_line, signal_line, histogram, dir_code)


def generate_bollinger_signals(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    direction: TradeDirection = TradeDirection.BOTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate Bollinger Bands signals."""
    close = df["close"].values.astype(np.float64)
    upper, middle, lower = calculate_bollinger_numba(close, period, std_dev)

    dir_code = {"long": 0, "short": 1, "both": 2}.get(direction.value, 2)
    return generate_bb_signals_numba(close, upper, lower, dir_code)


def generate_stochastic_signals(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
    smooth: int = 3,
    oversold: float = 20.0,
    overbought: float = 80.0,
    direction: TradeDirection = TradeDirection.BOTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate Stochastic signals."""
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)

    k, d = calculate_stochastic_numba(high, low, close, k_period, d_period, smooth)

    n = len(close)
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    dir_code = {"long": 0, "short": 1, "both": 2}.get(direction.value, 2)

    for i in range(1, n):
        # Long signals
        if dir_code in (0, 2):
            if k[i - 1] <= oversold < k[i]:
                long_entries[i] = True
            if k[i - 1] <= overbought < k[i]:
                long_exits[i] = True

        # Short signals
        if dir_code in (1, 2):
            if k[i - 1] >= overbought > k[i]:
                short_entries[i] = True
            if k[i - 1] >= oversold > k[i]:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def generate_supertrend_signals(
    df: pd.DataFrame,
    atr_period: int = 10,
    multiplier: float = 3.0,
    direction: TradeDirection = TradeDirection.BOTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate SuperTrend signals."""
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)

    _, trend_dir = calculate_supertrend_numba(high, low, close, atr_period, multiplier)

    n = len(close)
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    dir_code = {"long": 0, "short": 1, "both": 2}.get(direction.value, 2)

    for i in range(1, n):
        # Trend change from down to up
        if trend_dir[i - 1] == -1 and trend_dir[i] == 1:
            if dir_code in (0, 2):
                long_entries[i] = True
            if dir_code in (1, 2):
                short_exits[i] = True

        # Trend change from up to down
        if trend_dir[i - 1] == 1 and trend_dir[i] == -1:
            if dir_code in (0, 2):
                long_exits[i] = True
            if dir_code in (1, 2):
                short_entries[i] = True

    return long_entries, long_exits, short_entries, short_exits


def generate_ma_crossover_signals(
    df: pd.DataFrame,
    fast_period: int = 10,
    slow_period: int = 20,
    direction: TradeDirection = TradeDirection.BOTH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate MA Crossover signals."""
    close = df["close"].values.astype(np.float64)

    # Simple EMA crossover
    fast_ma = pd.Series(close).ewm(span=fast_period, adjust=False).mean().values
    slow_ma = pd.Series(close).ewm(span=slow_period, adjust=False).mean().values

    n = len(close)
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    dir_code = {"long": 0, "short": 1, "both": 2}.get(direction.value, 2)

    for i in range(1, n):
        # Golden cross (fast crosses above slow)
        if fast_ma[i - 1] <= slow_ma[i - 1] and fast_ma[i] > slow_ma[i]:
            if dir_code in (0, 2):
                long_entries[i] = True
            if dir_code in (1, 2):
                short_exits[i] = True

        # Death cross (fast crosses below slow)
        if fast_ma[i - 1] >= slow_ma[i - 1] and fast_ma[i] < slow_ma[i]:
            if dir_code in (0, 2):
                long_exits[i] = True
            if dir_code in (1, 2):
                short_entries[i] = True

    return long_entries, long_exits, short_entries, short_exits


# =============================================================================
# TEST CONFIGURATIONS
# =============================================================================

STRATEGY_CONFIGS: list[dict[str, Any]] = [
    # RSI variations
    {
        "name": "RSI_default",
        "generator": generate_rsi_signals,
        "params": {"period": 14, "oversold": 30.0, "overbought": 70.0},
    },
    {
        "name": "RSI_aggressive",
        "generator": generate_rsi_signals,
        "params": {"period": 7, "oversold": 25.0, "overbought": 75.0},
    },
    {
        "name": "RSI_conservative",
        "generator": generate_rsi_signals,
        "params": {"period": 21, "oversold": 20.0, "overbought": 80.0},
    },
    # MACD variations
    {
        "name": "MACD_default",
        "generator": generate_macd_signals,
        "params": {"fast": 12, "slow": 26, "signal": 9},
    },
    {
        "name": "MACD_fast",
        "generator": generate_macd_signals,
        "params": {"fast": 8, "slow": 17, "signal": 9},
    },
    # Bollinger variations
    {
        "name": "BB_default",
        "generator": generate_bollinger_signals,
        "params": {"period": 20, "std_dev": 2.0},
    },
    {
        "name": "BB_tight",
        "generator": generate_bollinger_signals,
        "params": {"period": 20, "std_dev": 1.5},
    },
    # Stochastic
    {
        "name": "Stochastic_default",
        "generator": generate_stochastic_signals,
        "params": {"k_period": 14, "d_period": 3, "smooth": 3},
    },
    # SuperTrend
    {
        "name": "SuperTrend_default",
        "generator": generate_supertrend_signals,
        "params": {"atr_period": 10, "multiplier": 3.0},
    },
    {
        "name": "SuperTrend_sensitive",
        "generator": generate_supertrend_signals,
        "params": {"atr_period": 7, "multiplier": 2.0},
    },
    # MA Crossover
    {
        "name": "MA_Cross_fast",
        "generator": generate_ma_crossover_signals,
        "params": {"fast_period": 5, "slow_period": 10},
    },
    {
        "name": "MA_Cross_slow",
        "generator": generate_ma_crossover_signals,
        "params": {"fast_period": 20, "slow_period": 50},
    },
]

RISK_CONFIGS = [
    {"sl": 0.02, "tp": 0.04, "name": "2:1 RR"},
    {"sl": 0.01, "tp": 0.015, "name": "Scalping"},
    {"sl": 0.05, "tp": 0.10, "name": "Swing"},
    {"sl": 0.03, "tp": None, "name": "No TP"},
]

LEVERAGE_CONFIGS = [1.0, 3.0, 5.0, 10.0]


# =============================================================================
# TEST CLASS
# =============================================================================


@pytest.fixture(scope="module")
def real_data() -> dict[str, pd.DataFrame]:
    """Load real data for all tests."""
    data = {}

    # Try to load BTC 15m
    df_15m = load_candles_from_db("BTCUSDT", "15", limit=3000)
    if df_15m is not None and len(df_15m) >= 500:
        data["BTCUSDT_15m"] = df_15m

    # Try to load BTC 1H
    df_1h = load_candles_from_db("BTCUSDT", "60", limit=1000)
    if df_1h is not None and len(df_1h) >= 200:
        data["BTCUSDT_1H"] = df_1h

    # Try to load ETH 15m
    df_eth = load_candles_from_db("ETHUSDT", "15", limit=2000)
    if df_eth is not None and len(df_eth) >= 500:
        data["ETHUSDT_15m"] = df_eth

    return data


class TestEngineComprehensive:
    """Comprehensive tests for FallbackEngineV2."""

    def test_data_availability(self, real_data: dict[str, pd.DataFrame]):
        """Test that we have data to work with."""
        logger.info(f"Available datasets: {list(real_data.keys())}")
        if len(real_data) == 0:
            pytest.skip("No real data available for testing")

        for key, df in real_data.items():
            logger.info(f"  {key}: {len(df)} candles")
            assert len(df) >= 200, f"Insufficient data for {key}"

    @pytest.mark.parametrize("strategy_config", STRATEGY_CONFIGS)
    def test_all_strategies_long(self, real_data: dict[str, pd.DataFrame], strategy_config: dict):
        """Test all strategies in long-only mode."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]
        strategy_name = strategy_config["name"]
        generator = strategy_config["generator"]
        params = strategy_config["params"]

        logger.info(f"Testing {strategy_name} (long only)")

        # Generate signals
        long_entries, long_exits, _, _ = generator(df, direction=TradeDirection.LONG, **params)

        entry_count = np.sum(long_entries)
        if entry_count == 0:
            logger.warning(f"{strategy_name}: No entry signals generated")
            pytest.skip(f"No signals for {strategy_name}")

        logger.info(f"  Entries: {entry_count}, Exits: {np.sum(long_exits)}")

        # Run backtest
        engine = FallbackEngineV2()
        input_data = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,  # 0.07%
            direction=TradeDirection.LONG,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            long_entries=long_entries,
            long_exits=long_exits,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed: {result.validation_errors}"
        assert result.metrics is not None

        logger.info(
            f"  Result: {result.metrics.total_trades} trades, "
            f"PnL: {result.metrics.net_profit:.2f}%, "
            f"WinRate: {result.metrics.win_rate:.1f}%"
        )

    @pytest.mark.parametrize("strategy_config", STRATEGY_CONFIGS[:4])  # Test subset
    def test_all_strategies_short(self, real_data: dict[str, pd.DataFrame], strategy_config: dict):
        """Test strategies in short-only mode."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]
        strategy_name = strategy_config["name"]
        generator = strategy_config["generator"]
        params = strategy_config["params"]

        logger.info(f"Testing {strategy_name} (short only)")

        # Generate signals
        _, _, short_entries, short_exits = generator(df, direction=TradeDirection.SHORT, **params)

        entry_count = np.sum(short_entries)
        if entry_count == 0:
            pytest.skip(f"No short signals for {strategy_name}")

        # Run backtest
        engine = FallbackEngineV2()
        input_data = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.SHORT,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed: {result.validation_errors}"
        logger.info(f"  Result: {result.metrics.total_trades} trades, PnL: {result.metrics.net_profit:.2f}%")

    @pytest.mark.parametrize("strategy_config", STRATEGY_CONFIGS[:3])
    def test_all_strategies_both(self, real_data: dict[str, pd.DataFrame], strategy_config: dict):
        """Test strategies in both directions mode."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]
        strategy_name = strategy_config["name"]
        generator = strategy_config["generator"]
        params = strategy_config["params"]

        logger.info(f"Testing {strategy_name} (both directions)")

        # Generate signals
        long_entries, long_exits, short_entries, short_exits = generator(df, direction=TradeDirection.BOTH, **params)

        total_entries = np.sum(long_entries) + np.sum(short_entries)
        if total_entries == 0:
            pytest.skip(f"No signals for {strategy_name}")

        # Run backtest
        engine = FallbackEngineV2()
        input_data = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.BOTH,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid
        logger.info(
            f"  Result: {result.metrics.total_trades} trades, "
            f"Long: {result.metrics.winning_trades}, Short: {result.metrics.losing_trades}"
        )

    @pytest.mark.parametrize("risk_config", RISK_CONFIGS)
    def test_risk_configurations(self, real_data: dict[str, pd.DataFrame], risk_config: dict):
        """Test different SL/TP configurations."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]
        sl = risk_config["sl"]
        tp = risk_config["tp"]
        name = risk_config["name"]

        logger.info(f"Testing risk config: {name} (SL={sl}, TP={tp})")

        # Use RSI signals
        long_entries, long_exits, _, _ = generate_rsi_signals(df, direction=TradeDirection.LONG)

        if np.sum(long_entries) == 0:
            pytest.skip("No signals")

        engine = FallbackEngineV2()

        # Handle None TP (no take profit)
        tp_value = tp if tp is not None else 0.0

        input_data = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=sl,
            take_profit=tp_value,
            leverage=1,
            long_entries=long_entries,
            long_exits=long_exits,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid
        logger.info(f"  Result: {result.metrics.total_trades} trades, Max DD: {result.metrics.max_drawdown:.2f}%")

    @pytest.mark.parametrize("leverage", LEVERAGE_CONFIGS)
    def test_leverage_variations(self, real_data: dict[str, pd.DataFrame], leverage: float):
        """Test different leverage levels."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]

        logger.info(f"Testing leverage: {leverage}x")

        # Use RSI signals
        long_entries, long_exits, _, _ = generate_rsi_signals(df, direction=TradeDirection.LONG)

        if np.sum(long_entries) == 0:
            pytest.skip("No signals")

        engine = FallbackEngineV2()
        input_data = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=leverage,
            long_entries=long_entries,
            long_exits=long_exits,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid
        logger.info(f"  Result: PnL={result.metrics.net_profit:.2f}%, Max DD={result.metrics.max_drawdown:.2f}%")

        # Higher leverage should have higher volatility
        if leverage > 1.0:
            assert abs(result.metrics.net_profit) > 0 or result.metrics.total_trades == 0

    def test_multiple_symbols(self, real_data: dict[str, pd.DataFrame]):
        """Test same strategy on different symbols."""
        if len(real_data) < 2:
            pytest.skip("Need at least 2 symbols")

        results = {}
        engine = FallbackEngineV2()

        for key, df in real_data.items():
            logger.info(f"Testing on {key}")

            long_entries, long_exits, _, _ = generate_rsi_signals(df, direction=TradeDirection.LONG)

            if np.sum(long_entries) == 0:
                continue

            input_data = BacktestInput(
                candles=df,
                initial_capital=10000.0,
                taker_fee=0.0007,
                direction=TradeDirection.LONG,
                stop_loss=0.02,
                take_profit=0.04,
                leverage=1,
                long_entries=long_entries,
                long_exits=long_exits,
                use_bar_magnifier=False,
            )

            result = engine.run(input_data)
            if result.is_valid:
                results[key] = {
                    "trades": result.metrics.total_trades,
                    "pnl": result.metrics.net_profit,
                    "win_rate": result.metrics.win_rate,
                }

        logger.info(f"Multi-symbol results: {results}")
        assert len(results) > 0

    def test_bar_magnifier_comparison(self, real_data: dict[str, pd.DataFrame]):
        """Compare results with/without Bar Magnifier (if 1m data available)."""
        if "BTCUSDT_15m" not in real_data:
            pytest.skip("No 15m data")

        df_15m = real_data["BTCUSDT_15m"]

        # Try to load 1m data for bar magnifier
        df_1m = load_candles_from_db("BTCUSDT", "1", limit=len(df_15m) * 15)

        long_entries, long_exits, _, _ = generate_rsi_signals(df_15m, direction=TradeDirection.LONG)

        if np.sum(long_entries) == 0:
            pytest.skip("No signals")

        engine = FallbackEngineV2()

        # Without bar magnifier
        input_no_bm = BacktestInput(
            candles=df_15m,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            long_entries=long_entries,
            long_exits=long_exits,
            use_bar_magnifier=False,
        )
        result_no_bm = engine.run(input_no_bm)

        logger.info(f"Without Bar Magnifier: {result_no_bm.metrics.total_trades} trades")

        # With bar magnifier (if 1m data available)
        if df_1m is not None and len(df_1m) > 100:
            input_with_bm = BacktestInput(
                candles=df_15m,
                candles_1m=df_1m,
                initial_capital=10000.0,
                taker_fee=0.0007,
                direction=TradeDirection.LONG,
                stop_loss=0.02,
                take_profit=0.04,
                leverage=1,
                long_entries=long_entries,
                long_exits=long_exits,
                use_bar_magnifier=True,
            )
            result_with_bm = engine.run(input_with_bm)

            logger.info(f"With Bar Magnifier: {result_with_bm.metrics.total_trades} trades")

            # Results should be different (more accurate SL/TP detection)
            assert result_no_bm.is_valid and result_with_bm.is_valid

    def test_edge_cases(self, real_data: dict[str, pd.DataFrame]):
        """Test edge cases."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]
        engine = FallbackEngineV2()

        # Test 1: No signals at all
        input_no_signals = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            long_entries=np.zeros(len(df), dtype=bool),
            long_exits=np.zeros(len(df), dtype=bool),
            use_bar_magnifier=False,
        )
        result_no_signals = engine.run(input_no_signals)
        assert result_no_signals.is_valid
        assert result_no_signals.metrics.total_trades == 0
        logger.info("Edge case 1 (no signals): PASS")

        # Test 2: Entry on every bar (stress test)
        stress_entries = np.ones(len(df), dtype=bool)
        input_stress = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            long_entries=stress_entries,
            long_exits=np.zeros(len(df), dtype=bool),
            use_bar_magnifier=False,
        )
        result_stress = engine.run(input_stress)
        assert result_stress.is_valid
        logger.info(f"Edge case 2 (stress test): {result_stress.metrics.total_trades} trades")

        # Test 3: Very tight SL/TP
        long_entries, long_exits, _, _ = generate_rsi_signals(df, direction=TradeDirection.LONG)
        input_tight = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.001,  # 0.1%
            take_profit=0.002,  # 0.2%
            leverage=1,
            long_entries=long_entries,
            long_exits=long_exits,
            use_bar_magnifier=False,
        )
        result_tight = engine.run(input_tight)
        assert result_tight.is_valid
        logger.info(f"Edge case 3 (tight SL/TP): {result_tight.metrics.total_trades} trades")

    def test_metrics_sanity(self, real_data: dict[str, pd.DataFrame]):
        """Verify metrics are calculated correctly."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]

        long_entries, long_exits, _, _ = generate_rsi_signals(df, direction=TradeDirection.LONG)

        if np.sum(long_entries) == 0:
            pytest.skip("No signals")

        engine = FallbackEngineV2()
        input_data = BacktestInput(
            candles=df,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.02,
            take_profit=0.04,
            leverage=1,
            long_entries=long_entries,
            long_exits=long_exits,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)
        assert result.is_valid

        m = result.metrics

        # Sanity checks
        if m.total_trades > 0:
            assert 0 <= m.win_rate <= 100, f"Invalid win rate: {m.win_rate}"
            assert m.winning_trades + m.losing_trades == m.total_trades
            assert m.max_drawdown >= 0, "Drawdown should be positive"

            # Profit factor sanity
            if m.profit_factor is not None:
                assert m.profit_factor >= 0

            logger.info(
                f"Metrics sanity: trades={m.total_trades}, "
                f"win_rate={m.win_rate:.1f}%, "
                f"profit_factor={m.profit_factor:.2f}, "
                f"sharpe={m.sharpe_ratio:.2f}"
            )


class TestStrategyComparison:
    """Compare different strategies on same data."""

    def test_strategy_ranking(self, real_data: dict[str, pd.DataFrame]):
        """Rank strategies by performance."""
        if not real_data:
            pytest.skip("No real data available")

        df = list(real_data.values())[0]
        engine = FallbackEngineV2()

        results = []

        for config in STRATEGY_CONFIGS:
            strategy_name = config["name"]
            generator = config["generator"]
            params = config["params"]

            try:
                long_entries, long_exits, _, _ = generator(df, direction=TradeDirection.LONG, **params)

                if np.sum(long_entries) == 0:
                    continue

                input_data = BacktestInput(
                    candles=df,
                    initial_capital=10000.0,
                    taker_fee=0.0007,
                    direction=TradeDirection.LONG,
                    stop_loss=0.02,
                    take_profit=0.04,
                    leverage=1,
                    long_entries=long_entries,
                    long_exits=long_exits,
                    use_bar_magnifier=False,
                )

                result = engine.run(input_data)

                if result.is_valid and result.metrics.total_trades > 0:
                    results.append(
                        {
                            "strategy": strategy_name,
                            "trades": result.metrics.total_trades,
                            "pnl_pct": result.metrics.net_profit,
                            "win_rate": result.metrics.win_rate,
                            "sharpe": result.metrics.sharpe_ratio or 0,
                            "max_dd": result.metrics.max_drawdown,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to test {strategy_name}: {e}")

        if not results:
            pytest.skip("No valid results")

        # Sort by Sharpe ratio
        results.sort(key=lambda x: x["sharpe"], reverse=True)

        logger.info("\n" + "=" * 70)
        logger.info("STRATEGY RANKING (by Sharpe Ratio)")
        logger.info("=" * 70)
        for i, r in enumerate(results, 1):
            logger.info(
                f"{i}. {r['strategy']:25} | "
                f"Trades: {r['trades']:4} | "
                f"PnL: {r['pnl_pct']:+7.2f}% | "
                f"WR: {r['win_rate']:5.1f}% | "
                f"Sharpe: {r['sharpe']:6.2f} | "
                f"MaxDD: {r['max_dd']:6.2f}%"
            )

        assert len(results) > 0


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Run with verbose output
    pytest.main(
        [
            __file__,
            "-v",
            "-s",
            "--tb=short",
            "-x",  # Stop on first failure
        ]
    )
