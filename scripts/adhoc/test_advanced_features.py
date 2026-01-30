"""
Тест расширенных функций FallbackEngineV4:
- Position Sizing (risk-based, volatility-based, Kelly)
- Re-entry Rules
- Time-based Exits
- Dynamic Slippage
- Funding Rate
"""

from datetime import datetime

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection


def create_test_candles(n_bars: int = 100) -> pd.DataFrame:
    """Создать тестовые свечи с трендом и волатильностью."""
    np.random.seed(42)

    base_price = 50000
    trend = np.cumsum(np.random.randn(n_bars) * 50)
    prices = base_price + trend

    data = {
        "open": prices + np.random.randn(n_bars) * 10,
        "high": prices + np.abs(np.random.randn(n_bars)) * 50,
        "low": prices - np.abs(np.random.randn(n_bars)) * 50,
        "close": prices + np.random.randn(n_bars) * 20,
        "volume": np.random.randint(100, 1000, n_bars).astype(float),
    }

    start_time = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = pd.date_range(start=start_time, periods=n_bars, freq="15min")

    return pd.DataFrame(data, index=timestamps)


def test_basic_backtest():
    """Базовый тест с дефолтными параметрами."""
    print("\n=== Test 1: Basic Backtest ===")

    candles = create_test_candles(200)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[::20] = True

    long_exits = np.zeros(len(candles), dtype=bool)
    long_exits[10::20] = True

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=1,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    print(f"  Win Rate: {result.metrics.win_rate:.1%}")
    print(f"  Net Profit: ${result.metrics.net_profit:.2f}")
    print(f"  Max Drawdown: {result.metrics.max_drawdown:.2f}%")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    assert result.metrics.total_trades > 0, "Should have trades"
    print("  ✓ PASSED")


def test_position_sizing_risk():
    """Тест risk-based position sizing."""
    print("\n=== Test 2: Risk-Based Position Sizing ===")

    candles = create_test_candles(200)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[::30] = True

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.01,
        take_profit=0.02,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        position_sizing_mode="risk",
        risk_per_trade=0.02,
        max_position_size=0.5,
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    print(f"  Net Profit: ${result.metrics.net_profit:.2f}")
    print(f"  Max Drawdown: {result.metrics.max_drawdown:.2f}%")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    print("  ✓ PASSED")


def test_position_sizing_volatility():
    """Тест volatility-based position sizing."""
    print("\n=== Test 3: Volatility-Based Position Sizing ===")

    candles = create_test_candles(200)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[::30] = True

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=5,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        position_sizing_mode="volatility",
        volatility_target=0.02,
        max_position_size=0.8,
        min_position_size=0.1,
        atr_enabled=True,
        atr_period=14,
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    print(f"  Net Profit: ${result.metrics.net_profit:.2f}")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    print("  ✓ PASSED")


def test_reentry_rules():
    """Тест re-entry rules."""
    print("\n=== Test 4: Re-entry Rules ===")

    candles = create_test_candles(200)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[10:15] = True
    long_entries[50:55] = True

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=1,
        position_size=0.3,
        stop_loss=0.01,
        take_profit=0.02,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        allow_re_entry=True,
        re_entry_delay_bars=5,
        max_trades_per_day=3,
        max_consecutive_losses=2,
        cooldown_after_loss=10,
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    print("  (Limited by re-entry rules)")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    print("  ✓ PASSED")


def test_time_based_exits():
    """Тест time-based exits."""
    print("\n=== Test 5: Time-Based Exits ===")

    candles = create_test_candles(200)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[10] = True
    long_entries[100] = True

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=1,
        position_size=0.5,
        stop_loss=0.05,
        take_profit=0.10,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        max_bars_in_trade=50,
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    for trade in result.trades:
        print(f"    Duration: {trade.duration_bars} bars, Exit: {trade.exit_reason}")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    print("  ✓ PASSED")


def test_dynamic_slippage():
    """Тест dynamic slippage models."""
    print("\n=== Test 6: Dynamic Slippage Model ===")

    candles = create_test_candles(200)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[::20] = True

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=5,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        slippage_model="combined",
        slippage_volume_impact=0.2,
        slippage_volatility_mult=0.5,
        atr_enabled=True,
        atr_period=14,
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    print(f"  Net Profit: ${result.metrics.net_profit:.2f}")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    print("  ✓ PASSED")


def test_funding_rate():
    """Тест funding rate calculation."""
    print("\n=== Test 7: Funding Rate ===")

    candles = create_test_candles(500)
    long_entries = np.zeros(len(candles), dtype=bool)
    long_entries[10] = True

    input_no_funding = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.05,
        take_profit=0.10,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        include_funding=False,
    )

    input_with_funding = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.05,
        take_profit=0.10,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        include_funding=True,
        funding_rate=0.0001,
        funding_interval_hours=8,
    )

    engine = FallbackEngineV4()
    result_no_funding = engine.run(input_no_funding)
    result_with_funding = engine.run(input_with_funding)

    print(f"  Without Funding: ${result_no_funding.metrics.net_profit:.2f}")
    print(f"  With Funding:    ${result_with_funding.metrics.net_profit:.2f}")

    profit_diff = (
        result_no_funding.metrics.net_profit - result_with_funding.metrics.net_profit
    )
    print(f"  Funding Cost:    ${profit_diff:.2f}")

    assert result_no_funding.is_valid, f"Error: {result_no_funding.validation_errors}"
    assert result_with_funding.is_valid, (
        f"Error: {result_with_funding.validation_errors}"
    )
    print("  ✓ PASSED")


def test_no_trade_hours():
    """Тест запрета торговли в определённые часы."""
    print("\n=== Test 8: No Trade Hours ===")

    candles = create_test_candles(200)
    long_entries = np.ones(len(candles), dtype=bool)

    input_data = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=np.zeros(len(candles), dtype=bool),
        short_entries=np.zeros(len(candles), dtype=bool),
        short_exits=np.zeros(len(candles), dtype=bool),
        initial_capital=10000,
        leverage=1,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.001,
        slippage=0.0005,
        direction=TradeDirection.LONG,
        use_bar_magnifier=False,
        no_trade_hours=(0, 1, 2, 3, 4, 5, 6, 7),
    )

    engine = FallbackEngineV4()
    result = engine.run(input_data)

    print(f"  Trades: {result.metrics.total_trades}")
    print("  (Filtered by no_trade_hours)")

    assert result.is_valid, f"Backtest failed: {result.validation_errors}"
    print("  ✓ PASSED")


def main():
    print("=" * 60)
    print("  Testing FallbackEngineV4 Advanced Features")
    print("=" * 60)

    test_basic_backtest()
    test_position_sizing_risk()
    test_position_sizing_volatility()
    test_reentry_rules()
    test_time_based_exits()
    test_dynamic_slippage()
    test_funding_rate()
    test_no_trade_hours()

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
