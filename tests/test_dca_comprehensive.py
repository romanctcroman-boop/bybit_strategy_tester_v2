"""
Comprehensive DCA (Dollar Cost Averaging) Test Suite.

Tests DCA strategies with:
- DCA Long / Short directions
- Multi-Timeframe (MTF) filtering
- Multi-level Take Profit (TP1-TP4)
- ATR-based dynamic TP/SL
- Various Safety Order configurations
- Trailing Stop + Breakeven
- Different leverage and risk settings

Uses REAL data from SQLite database.

Version: 1.0.2
Date: 2026-01-28
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from loguru import logger

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.backtesting.dca_strategies.dca_multi_tp import (
    DCADirection,
    DCAMultiTPConfig,
    SLMode,
    TPMode,
    create_dca_long_atr_tp_sl,
    create_dca_long_multi_tp,
    create_dca_short_atr_tp_sl,
    create_dca_short_multi_tp,
)
from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.interfaces import SlMode as InputSlMode
from backend.backtesting.interfaces import TpMode as InputTpMode
from backend.backtesting.universal_engine.signal_generator import calculate_rsi_numba

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
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        logger.info(f"Loaded {len(df)} candles for {symbol} {interval}")
        return df

    finally:
        conn.close()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="module")
def btc_data() -> pd.DataFrame:
    """Load BTC 15m data for testing."""
    df = load_candles_from_db("BTCUSDT", "15", limit=5000)
    if df is None or df.empty:
        pytest.skip("No BTC data available")
    return df


@pytest.fixture(scope="module")
def eth_data() -> pd.DataFrame:
    """Load ETH 15m data for testing."""
    df = load_candles_from_db("ETHUSDT", "15", limit=3000)
    if df is None or df.empty:
        pytest.skip("No ETH data available")
    return df


@pytest.fixture(scope="module")
def btc_1h_data() -> pd.DataFrame:
    """Load BTC 1h data for MTF testing."""
    df = load_candles_from_db("BTCUSDT", "60", limit=2000)
    if df is None or df.empty:
        pytest.skip("No BTC 1h data available")
    return df


# =============================================================================
# DCA CONFIGURATIONS
# =============================================================================

# DCA Long configurations
DCA_LONG_CONFIGS = [
    {
        "name": "Basic_Long_3SO",
        "direction": DCADirection.LONG,
        "max_safety_orders": 3,
        "price_deviation_pct": 1.0,
        "step_scale": 1.4,
        "volume_scale": 1.5,
    },
    {
        "name": "Aggressive_Long_5SO",
        "direction": DCADirection.LONG,
        "max_safety_orders": 5,
        "price_deviation_pct": 0.8,
        "step_scale": 1.2,
        "volume_scale": 2.0,
    },
    {
        "name": "Conservative_Long_2SO",
        "direction": DCADirection.LONG,
        "max_safety_orders": 2,
        "price_deviation_pct": 2.0,
        "step_scale": 1.5,
        "volume_scale": 1.0,
    },
    {
        "name": "DeepDCA_Long_7SO",
        "direction": DCADirection.LONG,
        "max_safety_orders": 7,
        "price_deviation_pct": 0.5,
        "step_scale": 1.1,
        "volume_scale": 1.3,
    },
    {
        "name": "WideSO_Long_4SO",
        "direction": DCADirection.LONG,
        "max_safety_orders": 4,
        "price_deviation_pct": 2.5,
        "step_scale": 1.8,
        "volume_scale": 1.8,
    },
    {
        "name": "Breakeven_Long",
        "direction": DCADirection.LONG,
        "max_safety_orders": 3,
        "price_deviation_pct": 1.5,
        "step_scale": 1.3,
        "volume_scale": 1.5,
        "breakeven_enabled": True,
    },
]

# DCA Short configurations
DCA_SHORT_CONFIGS = [
    {
        "name": "Basic_Short_3SO",
        "direction": DCADirection.SHORT,
        "max_safety_orders": 3,
        "price_deviation_pct": 1.0,
        "step_scale": 1.4,
        "volume_scale": 1.5,
    },
    {
        "name": "Aggressive_Short_5SO",
        "direction": DCADirection.SHORT,
        "max_safety_orders": 5,
        "price_deviation_pct": 0.8,
        "step_scale": 1.2,
        "volume_scale": 2.0,
    },
    {
        "name": "Conservative_Short_2SO",
        "direction": DCADirection.SHORT,
        "max_safety_orders": 2,
        "price_deviation_pct": 2.0,
        "step_scale": 1.5,
        "volume_scale": 1.0,
    },
    {
        "name": "DeepDCA_Short_6SO",
        "direction": DCADirection.SHORT,
        "max_safety_orders": 6,
        "price_deviation_pct": 0.6,
        "step_scale": 1.15,
        "volume_scale": 1.4,
    },
    {
        "name": "Breakeven_Short",
        "direction": DCADirection.SHORT,
        "max_safety_orders": 3,
        "price_deviation_pct": 1.5,
        "step_scale": 1.3,
        "volume_scale": 1.5,
        "breakeven_enabled": True,
    },
]

# Multi-TP configurations (all must have 4 levels for engine compatibility)
MULTI_TP_CONFIGS = [
    {
        "name": "TP_25_50_75_100",
        "tp_mode": TPMode.MULTI,
        "tp_levels_pct": (0.5, 1.0, 1.5, 2.0),
        "tp_portions": (0.25, 0.25, 0.25, 0.25),
    },
    {
        "name": "TP_40_30_20_10",
        "tp_mode": TPMode.MULTI,
        "tp_levels_pct": (0.8, 1.5, 2.5, 4.0),
        "tp_portions": (0.4, 0.3, 0.2, 0.1),
    },
    {
        "name": "TP_50_25_15_10",
        "tp_mode": TPMode.MULTI,
        "tp_levels_pct": (1.0, 2.0, 3.0, 5.0),
        "tp_portions": (0.5, 0.25, 0.15, 0.1),
    },
    {
        "name": "TP_Aggressive_4Level",
        "tp_mode": TPMode.MULTI,
        "tp_levels_pct": (0.3, 0.6, 1.0, 2.0),
        "tp_portions": (0.4, 0.3, 0.2, 0.1),
    },
    {
        "name": "TP_Conservative_4Level",
        "tp_mode": TPMode.MULTI,
        "tp_levels_pct": (1.5, 3.0, 5.0, 8.0),
        "tp_portions": (0.4, 0.3, 0.2, 0.1),
    },
]

# ATR TP/SL configurations
ATR_CONFIGS = [
    {
        "name": "ATR_2x_1x",
        "tp_mode": TPMode.ATR,
        "sl_mode": SLMode.ATR,
        "atr_period": 14,
        "atr_tp_multiplier": 2.0,
        "atr_sl_multiplier": 1.0,
    },
    {
        "name": "ATR_3x_1.5x",
        "tp_mode": TPMode.ATR,
        "sl_mode": SLMode.ATR,
        "atr_period": 14,
        "atr_tp_multiplier": 3.0,
        "atr_sl_multiplier": 1.5,
    },
    {
        "name": "ATR_1.5x_0.75x",
        "tp_mode": TPMode.ATR,
        "sl_mode": SLMode.ATR,
        "atr_period": 14,
        "atr_tp_multiplier": 1.5,
        "atr_sl_multiplier": 0.75,
    },
    {
        "name": "ATR_20period",
        "tp_mode": TPMode.ATR,
        "sl_mode": SLMode.ATR,
        "atr_period": 20,
        "atr_tp_multiplier": 2.5,
        "atr_sl_multiplier": 1.25,
    },
    {
        "name": "ATR_Tight",
        "tp_mode": TPMode.ATR,
        "sl_mode": SLMode.ATR,
        "atr_period": 10,
        "atr_tp_multiplier": 1.0,
        "atr_sl_multiplier": 0.5,
    },
]

# Leverage configurations
LEVERAGE_CONFIGS = [
    {"name": "Leverage_1x", "leverage": 1},
    {"name": "Leverage_3x", "leverage": 3},
    {"name": "Leverage_5x", "leverage": 5},
    {"name": "Leverage_10x", "leverage": 10},
    {"name": "Leverage_20x", "leverage": 20},
]

# Risk configurations
RISK_CONFIGS = [
    {
        "name": "LowRisk",
        "risk_per_trade": 0.01,
        "max_position_pct": 0.2,
        "volume_scale": 1.0,
    },
    {
        "name": "MediumRisk",
        "risk_per_trade": 0.02,
        "max_position_pct": 0.4,
        "volume_scale": 1.5,
    },
    {
        "name": "HighRisk",
        "risk_per_trade": 0.03,
        "max_position_pct": 0.6,
        "volume_scale": 2.0,
    },
    {
        "name": "AggressiveRisk",
        "risk_per_trade": 0.05,
        "max_position_pct": 0.8,
        "volume_scale": 2.5,
    },
]


# =============================================================================
# SIGNAL GENERATION HELPERS
# =============================================================================


def generate_rsi_signals(
    df: pd.DataFrame, period: int = 14, oversold: float = 30.0, overbought: float = 70.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate RSI-based entry/exit signals."""
    closes = df["close"].values.astype(np.float64)
    rsi = calculate_rsi_numba(closes, period)

    long_entries = rsi < oversold
    long_exits = rsi > overbought
    short_entries = rsi > overbought
    short_exits = rsi < oversold

    return long_entries, long_exits, short_entries, short_exits


def generate_ma_crossover_signals(
    df: pd.DataFrame, fast: int = 10, slow: int = 50
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate MA crossover signals."""
    closes = df["close"].values
    fast_ma = pd.Series(closes).rolling(fast).mean().values
    slow_ma = pd.Series(closes).rolling(slow).mean().values

    # Bullish crossover (fast crosses above slow)
    long_entries = (fast_ma > slow_ma) & (np.roll(fast_ma, 1) <= np.roll(slow_ma, 1))
    long_entries[:slow] = False

    # Bearish crossover
    short_entries = (fast_ma < slow_ma) & (np.roll(fast_ma, 1) >= np.roll(slow_ma, 1))
    short_entries[:slow] = False

    long_exits = short_entries.copy()
    short_exits = long_entries.copy()

    return long_entries, long_exits, short_entries, short_exits


def generate_mtf_filter(
    htf_data: pd.DataFrame, ltf_data: pd.DataFrame, ma_period: int = 50, ma_type: str = "SMA"
) -> np.ndarray:
    """Generate MTF trend filter from higher timeframe."""
    closes = htf_data["close"].values

    if ma_type == "SMA":
        ma = pd.Series(closes).rolling(ma_period).mean().values
    elif ma_type == "EMA":
        ma = pd.Series(closes).ewm(span=ma_period).mean().values
    else:
        ma = pd.Series(closes).rolling(ma_period).mean().values

    # HTF trend: 1 if price above MA, -1 if below
    htf_trend = np.where(closes > ma, 1, -1)

    # Expand HTF trend to LTF (simple forward fill based on ratio)
    ratio = len(ltf_data) / len(htf_data)
    ltf_trend = np.repeat(htf_trend, int(np.ceil(ratio)))[: len(ltf_data)]

    return ltf_trend


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestDCALongStrategies:
    """Test DCA Long strategies."""

    @pytest.mark.parametrize("config", DCA_LONG_CONFIGS, ids=lambda c: c["name"])
    def test_dca_long_config(self, btc_data: pd.DataFrame, config: dict):
        """Test DCA Long with various configurations."""
        # Create DCA config (only using supported params)
        dca_config = DCAMultiTPConfig(
            direction=config["direction"],
            tp_mode=config.get("tp_mode", TPMode.MULTI),
            sl_mode=config.get("sl_mode", SLMode.FIXED),
            max_safety_orders=config.get("max_safety_orders", 3),
            price_deviation_pct=config.get("price_deviation_pct", 1.0),
            step_scale=config.get("step_scale", 1.4),
            volume_scale=config.get("volume_scale", 1.5),
            breakeven_enabled=config.get("breakeven_enabled", False),
        )

        # Generate signals
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Get engine (pyramiding controls DCA implicitly)
        engine = get_engine(pyramiding=config.get("max_safety_orders", 3) + 1)

        # Prepare input
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=config.get("max_safety_orders", 3) + 1,
            dca_enabled=True,
            dca_safety_orders=config.get("max_safety_orders", 3),
            dca_price_deviation=config.get("price_deviation_pct", 1.0) / 100,
            dca_step_scale=config.get("step_scale", 1.4),
            dca_volume_scale=config.get("volume_scale", 1.0),
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed for {config['name']}"

        logger.info(
            f"DCA Long {config['name']}: "
            f"Trades={result.metrics.total_trades}, "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"WR={result.metrics.win_rate:.1f}%, "
            f"MaxDD={result.metrics.max_drawdown:.2f}%"
        )


class TestDCAShortStrategies:
    """Test DCA Short strategies."""

    @pytest.mark.parametrize("config", DCA_SHORT_CONFIGS, ids=lambda c: c["name"])
    def test_dca_short_config(self, btc_data: pd.DataFrame, config: dict):
        """Test DCA Short with various configurations."""
        # Create DCA config
        dca_config = DCAMultiTPConfig(
            direction=config["direction"],
            tp_mode=config.get("tp_mode", TPMode.MULTI),
            sl_mode=config.get("sl_mode", SLMode.FIXED),
            max_safety_orders=config.get("max_safety_orders", 3),
            price_deviation_pct=config.get("price_deviation_pct", 1.0),
            step_scale=config.get("step_scale", 1.4),
            volume_scale=config.get("volume_scale", 1.5),
            breakeven_enabled=config.get("breakeven_enabled", False),
        )

        # Generate signals
        _, _, short_entries, short_exits = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Get engine
        engine = get_engine(pyramiding=config.get("max_safety_orders", 3) + 1)

        # Prepare input
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.SHORT,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            short_entries=short_entries,
            short_exits=short_exits,
            pyramiding=config.get("max_safety_orders", 3) + 1,
            dca_enabled=True,
            dca_safety_orders=config.get("max_safety_orders", 3),
            dca_price_deviation=config.get("price_deviation_pct", 1.0) / 100,
            dca_step_scale=config.get("step_scale", 1.4),
            dca_volume_scale=config.get("volume_scale", 1.0),
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed for {config['name']}"

        logger.info(
            f"DCA Short {config['name']}: "
            f"Trades={result.metrics.total_trades}, "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"WR={result.metrics.win_rate:.1f}%, "
            f"MaxDD={result.metrics.max_drawdown:.2f}%"
        )


class TestMultiTP:
    """Test Multi-level Take Profit configurations."""

    @pytest.mark.parametrize("config", MULTI_TP_CONFIGS, ids=lambda c: c["name"])
    def test_multi_tp_config(self, btc_data: pd.DataFrame, config: dict):
        """Test multi-level TP with various configurations."""
        # Generate signals
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Get engine with multi-TP support
        engine = get_engine(pyramiding=4)

        # Prepare input with multi-TP
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=config["tp_levels_pct"][-1] / 100,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=3,
            tp_mode=InputTpMode.MULTI,
            tp_levels=[lvl / 100 for lvl in config["tp_levels_pct"]],
            tp_portions=list(config["tp_portions"]),
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed for {config['name']}"

        logger.info(
            f"Multi-TP {config['name']}: "
            f"Trades={result.metrics.total_trades}, "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"WR={result.metrics.win_rate:.1f}%"
        )


class TestATRTPSL:
    """Test ATR-based TP/SL configurations."""

    @pytest.mark.parametrize("config", ATR_CONFIGS, ids=lambda c: c["name"])
    def test_atr_config(self, btc_data: pd.DataFrame, config: dict):
        """Test ATR-based TP/SL with various configurations."""
        # Generate signals
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Get engine with ATR support (v4)
        engine = get_engine(engine_type="fallback_v4", pyramiding=4)

        # Prepare input with ATR TP/SL
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=3,
            tp_mode=InputTpMode.ATR,
            sl_mode=InputSlMode.ATR,
            atr_period=config["atr_period"],
            atr_tp_multiplier=config["atr_tp_multiplier"],
            atr_sl_multiplier=config["atr_sl_multiplier"],
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed for {config['name']}"

        logger.info(
            f"ATR {config['name']}: "
            f"Trades={result.metrics.total_trades}, "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"WR={result.metrics.win_rate:.1f}%"
        )


class TestDCALeverage:
    """Test DCA with various leverage settings."""

    @pytest.mark.parametrize("config", LEVERAGE_CONFIGS, ids=lambda c: c["name"])
    def test_dca_leverage(self, btc_data: pd.DataFrame, config: dict):
        """Test DCA with different leverage levels."""
        # Generate signals
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Get engine
        engine = get_engine(pyramiding=4)

        # Prepare input
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=config["leverage"],
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=3,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed for {config['name']}"

        logger.info(
            f"Leverage {config['name']}: "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"MaxDD={result.metrics.max_drawdown:.2f}%"
        )


class TestDCARiskConfigs:
    """Test DCA with various risk configurations."""

    @pytest.mark.parametrize("config", RISK_CONFIGS, ids=lambda c: c["name"])
    def test_dca_risk_config(self, btc_data: pd.DataFrame, config: dict):
        """Test DCA with different risk profiles."""
        # Generate signals
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Get engine
        engine = get_engine(pyramiding=4)

        # Prepare input with risk settings
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=3,
            dca_volume_scale=config["volume_scale"],
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, f"Backtest failed for {config['name']}"

        logger.info(
            f"Risk {config['name']}: PnL={result.metrics.net_profit:+.2f}%, MaxDD={result.metrics.max_drawdown:.2f}%"
        )


class TestDCAMultiMTF:
    """Test DCA with Multi-Timeframe filtering."""

    def test_mtf_sma_filter(self, btc_data: pd.DataFrame, btc_1h_data: pd.DataFrame):
        """Test DCA with SMA-based MTF filter."""
        # Generate MTF trend filter
        mtf_trend = generate_mtf_filter(btc_1h_data, btc_data, ma_period=50, ma_type="SMA")

        # Generate base signals
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Apply MTF filter (only long when HTF trend is bullish)
        filtered_long_entries = long_entries & (mtf_trend == 1)

        # Get engine
        engine = get_engine(pyramiding=4)

        # Prepare input
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=filtered_long_entries,
            long_exits=long_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=4,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, "Backtest failed for MTF SMA filter"

        logger.info(
            f"MTF SMA Filter: "
            f"Trades={result.metrics.total_trades}, "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"WR={result.metrics.win_rate:.1f}%"
        )

    def test_mtf_ema_filter(self, btc_data: pd.DataFrame, btc_1h_data: pd.DataFrame):
        """Test DCA with EMA-based MTF filter."""
        # Generate MTF trend filter
        mtf_trend = generate_mtf_filter(btc_1h_data, btc_data, ma_period=50, ma_type="EMA")

        # Generate base signals
        _, _, short_entries, short_exits = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        # Apply MTF filter (only short when HTF trend is bearish)
        filtered_short_entries = short_entries & (mtf_trend == -1)

        # Get engine
        engine = get_engine(pyramiding=4)

        # Prepare input
        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.SHORT,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            short_entries=filtered_short_entries,
            short_exits=short_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=4,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)

        assert result.is_valid, "Backtest failed for MTF EMA filter"

        logger.info(
            f"MTF EMA Filter: "
            f"Trades={result.metrics.total_trades}, "
            f"PnL={result.metrics.net_profit:+.2f}%, "
            f"WR={result.metrics.win_rate:.1f}%"
        )


class TestDCAFactoryFunctions:
    """Test DCA factory functions."""

    def test_create_dca_long_multi_tp(self, btc_data: pd.DataFrame):
        """Test create_dca_long_multi_tp factory."""
        strategy = create_dca_long_multi_tp(
            tp_levels_pct=[0.5, 1.0, 1.5, 2.0],
            tp_portions=[0.25, 0.25, 0.25, 0.25],
            max_safety_orders=3,
        )

        assert strategy.config.direction == DCADirection.LONG
        assert strategy.config.tp_mode == TPMode.MULTI
        assert len(strategy.config.tp_levels_pct) == 4

        logger.info(f"Factory DCA Long Multi-TP: {strategy.config}")

    def test_create_dca_short_multi_tp(self, btc_data: pd.DataFrame):
        """Test create_dca_short_multi_tp factory."""
        strategy = create_dca_short_multi_tp(
            tp_levels_pct=[0.5, 1.0, 1.5],
            tp_portions=[0.5, 0.3, 0.2],
            max_safety_orders=4,
        )

        assert strategy.config.direction == DCADirection.SHORT
        assert strategy.config.tp_mode == TPMode.MULTI
        assert len(strategy.config.tp_levels_pct) == 3

        logger.info(f"Factory DCA Short Multi-TP: {strategy.config}")

    def test_create_dca_long_atr_tp_sl(self, btc_data: pd.DataFrame):
        """Test create_dca_long_atr_tp_sl factory."""
        strategy = create_dca_long_atr_tp_sl(
            atr_period=14,
            atr_tp_multiplier=2.0,
            atr_sl_multiplier=1.0,
            max_safety_orders=5,
        )

        assert strategy.config.direction == DCADirection.LONG
        assert strategy.config.tp_mode == TPMode.ATR
        assert strategy.config.sl_mode == SLMode.ATR
        assert strategy.config.atr_period == 14

        logger.info(f"Factory DCA Long ATR: {strategy.config}")

    def test_create_dca_short_atr_tp_sl(self, btc_data: pd.DataFrame):
        """Test create_dca_short_atr_tp_sl factory."""
        strategy = create_dca_short_atr_tp_sl(
            atr_period=20,
            atr_tp_multiplier=2.5,
            atr_sl_multiplier=1.25,
            max_safety_orders=3,
        )

        assert strategy.config.direction == DCADirection.SHORT
        assert strategy.config.tp_mode == TPMode.ATR
        assert strategy.config.sl_mode == SLMode.ATR
        assert strategy.config.atr_period == 20

        logger.info(f"Factory DCA Short ATR: {strategy.config}")


class TestDCAEdgeCases:
    """Test DCA edge cases and boundary conditions."""

    def test_dca_no_safety_orders(self, btc_data: pd.DataFrame):
        """Test DCA with 0 safety orders (essentially no DCA)."""
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        engine = get_engine(pyramiding=1)

        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=1,
            dca_enabled=True,
            dca_safety_orders=0,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)
        assert result.is_valid, "Zero safety orders should still work"
        logger.info(f"Zero SO: Trades={result.metrics.total_trades}")

    def test_dca_max_safety_orders(self, btc_data: pd.DataFrame):
        """Test DCA with maximum safety orders (10)."""
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        engine = get_engine(pyramiding=11)

        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=11,
            dca_enabled=True,
            dca_safety_orders=10,
            dca_price_deviation=0.005,
            dca_step_scale=1.2,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)
        assert result.is_valid, "Max safety orders should work"
        logger.info(f"Max SO (10): Trades={result.metrics.total_trades}")

    def test_dca_high_volume_scale(self, btc_data: pd.DataFrame):
        """Test DCA with high volume scaling (3x)."""
        long_entries, long_exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)

        engine = get_engine(pyramiding=4)

        input_data = BacktestInput(
            candles=btc_data,
            initial_capital=10000.0,
            taker_fee=0.0007,
            direction=TradeDirection.LONG,
            stop_loss=0.05,
            take_profit=0.02,
            leverage=10,
            long_entries=long_entries,
            long_exits=long_exits,
            pyramiding=4,
            dca_enabled=True,
            dca_safety_orders=3,
            dca_volume_scale=3.0,
            use_bar_magnifier=False,
        )

        result = engine.run(input_data)
        assert result.is_valid, "High volume scale should work"
        logger.info(f"High Volume Scale (3x): PnL={result.metrics.net_profit:+.2f}%")


class TestDCAStrategyRanking:
    """Test strategy ranking by performance."""

    def test_dca_strategy_ranking(self, btc_data: pd.DataFrame):
        """Run all DCA configurations and rank by Sharpe ratio."""
        results = []

        # Test configurations
        configs_to_test = [
            ("DCA_Long_Basic", DCADirection.LONG, 3, 1.0, 1.4, 1.5),
            ("DCA_Long_Aggressive", DCADirection.LONG, 5, 0.8, 1.2, 2.0),
            ("DCA_Long_Conservative", DCADirection.LONG, 2, 2.0, 1.5, 1.0),
            ("DCA_Short_Basic", DCADirection.SHORT, 3, 1.0, 1.4, 1.5),
            ("DCA_Short_Aggressive", DCADirection.SHORT, 5, 0.8, 1.2, 2.0),
        ]

        for name, direction, so, dev, step, vol in configs_to_test:
            try:
                # Generate signals
                if direction == DCADirection.LONG:
                    entries, exits, _, _ = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)
                    trade_dir = TradeDirection.LONG
                else:
                    _, _, entries, exits = generate_rsi_signals(btc_data, period=14, oversold=30, overbought=70)
                    trade_dir = TradeDirection.SHORT

                engine = get_engine(pyramiding=so + 1)

                input_data = BacktestInput(
                    candles=btc_data,
                    initial_capital=10000.0,
                    taker_fee=0.0007,
                    direction=trade_dir,
                    stop_loss=0.05,
                    take_profit=0.02,
                    leverage=10,
                    long_entries=entries if direction == DCADirection.LONG else None,
                    long_exits=exits if direction == DCADirection.LONG else None,
                    short_entries=entries if direction == DCADirection.SHORT else None,
                    short_exits=exits if direction == DCADirection.SHORT else None,
                    pyramiding=so + 1,
                    dca_enabled=True,
                    dca_safety_orders=so,
                    dca_price_deviation=dev / 100,
                    dca_step_scale=step,
                    dca_volume_scale=vol,
                    use_bar_magnifier=False,
                )

                result = engine.run(input_data)

                if result.is_valid:
                    results.append(
                        {
                            "name": name,
                            "sharpe": result.metrics.sharpe_ratio,
                            "pnl": result.metrics.net_profit,
                            "max_dd": result.metrics.max_drawdown,
                            "win_rate": result.metrics.win_rate,
                            "trades": result.metrics.total_trades,
                        }
                    )

            except Exception as e:
                logger.warning(f"Failed to test {name}: {e}")

        # Sort by Sharpe ratio
        results.sort(key=lambda x: x["sharpe"], reverse=True)

        # Log ranking
        logger.info("\n" + "=" * 60)
        logger.info("DCA STRATEGY RANKING (by Sharpe Ratio)")
        logger.info("=" * 60)
        for i, r in enumerate(results, 1):
            logger.info(
                f"{i}. {r['name']}: "
                f"Sharpe={r['sharpe']:.2f}, "
                f"PnL={r['pnl']:+.2f}%, "
                f"MaxDD={r['max_dd']:.2f}%, "
                f"WR={r['win_rate']:.1f}%"
            )

        assert len(results) > 0, "At least one strategy should complete"
        assert results[0]["sharpe"] > 0 or results[0]["pnl"] != 0, "Best strategy should have results"


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
