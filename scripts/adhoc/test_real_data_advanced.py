"""
Тест всех расширенных функций FallbackEngineV4 на реальных данных.
Период: 6 месяцев BTCUSDT 15m (июль-декабрь 2025)
"""

import sqlite3
import time

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection


def load_real_data(
    symbol: str = "BTCUSDT",
    interval: str = "15",
    start_date: str = "2025-07-01",
    end_date: str = "2025-12-31",
) -> pd.DataFrame:
    """Загрузить реальные данные из БД."""
    conn = sqlite3.connect("data.sqlite3")

    query = """
        SELECT
            open_time,
            open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit
        WHERE symbol = ? AND interval = ?
          AND datetime(open_time/1000, 'unixepoch') >= ?
          AND datetime(open_time/1000, 'unixepoch') <= ?
        ORDER BY open_time
    """

    df = pd.read_sql_query(query, conn, params=[symbol, interval, start_date, end_date])
    conn.close()

    if len(df) == 0:
        raise ValueError(
            f"No data found for {symbol} {interval} from {start_date} to {end_date}"
        )

    # Convert timestamp to datetime index
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.drop(columns=["open_time"], inplace=True)

    # Rename columns
    df.columns = ["open", "high", "low", "close", "volume"]

    print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    return df


def generate_signals(
    candles: pd.DataFrame, fast_period: int = 10, slow_period: int = 30
) -> tuple:
    """Генерировать сигналы с помощью SMA кроссовер стратегии."""
    close = candles["close"].values
    n = len(close)

    # Calculate SMAs
    fast_sma = np.full(n, np.nan)
    slow_sma = np.full(n, np.nan)

    for i in range(fast_period - 1, n):
        fast_sma[i] = np.mean(close[i - fast_period + 1 : i + 1])
    for i in range(slow_period - 1, n):
        slow_sma[i] = np.mean(close[i - slow_period + 1 : i + 1])

    # Generate signals
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    for i in range(slow_period, n):
        # Golden cross - long entry / short exit
        if fast_sma[i] > slow_sma[i] and fast_sma[i - 1] <= slow_sma[i - 1]:
            long_entries[i] = True
            short_exits[i] = True
        # Death cross - short entry / long exit
        elif fast_sma[i] < slow_sma[i] and fast_sma[i - 1] >= slow_sma[i - 1]:
            short_entries[i] = True
            long_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def run_test(name: str, input_data: BacktestInput) -> dict:
    """Запустить один тест и вернуть результаты."""
    engine = FallbackEngineV4()

    start_time = time.time()
    result = engine.run(input_data)
    elapsed = time.time() - start_time

    if not result.is_valid:
        print(f"  ❌ {name}: INVALID - {result.validation_errors}")
        return None

    m = result.metrics
    print(f"  ✅ {name}:")
    print(f"     Trades: {m.total_trades}, Win Rate: {m.win_rate:.1%}")
    print(f"     Net Profit: ${m.net_profit:,.2f} ({m.total_return:.2f}%)")
    print(f"     Max DD: {m.max_drawdown:.2f}%, Sharpe: {m.sharpe_ratio:.2f}")
    print(f"     Time: {elapsed:.2f}s")

    return {
        "name": name,
        "trades": m.total_trades,
        "win_rate": m.win_rate,
        "net_profit": m.net_profit,
        "max_drawdown": m.max_drawdown,
        "sharpe": m.sharpe_ratio,
        "elapsed": elapsed,
    }


def main():
    print("=" * 70)
    print("  FallbackEngineV4 Advanced Features Test on Real Data")
    print("  BTCUSDT 15m | Jul-Dec 2025 (~6 months)")
    print("=" * 70)

    # Load data
    candles = load_real_data(
        symbol="BTCUSDT",
        interval="15",
        start_date="2025-07-01",
        end_date="2025-12-31",
    )

    # Generate signals with SMA crossover (fast=10, slow=30)
    long_entries, long_exits, short_entries, short_exits = generate_signals(
        candles, fast_period=10, slow_period=30
    )

    signal_count = np.sum(long_entries) + np.sum(short_entries)
    print(
        f"Generated {signal_count} entry signals ({np.sum(long_entries)} long, {np.sum(short_entries)} short)"
    )
    print()

    results = []

    # === TEST 1: Baseline (Market Orders) ===
    print("\n--- Test 1: Baseline (Market Orders) ---")
    baseline_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,  # Bybit taker fee
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        entry_order_type="market",
    )
    results.append(run_test("Baseline (Market)", baseline_input))

    # === TEST 2: Limit Orders ===
    print("\n--- Test 2: Limit Orders ---")
    limit_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0002,  # Maker fee for limit orders
        slippage=0.0,  # No slippage for limit
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        entry_order_type="limit",
        limit_entry_offset=0.002,  # 0.2% ниже текущей цены
        limit_entry_timeout_bars=10,  # 10 баров таймаут
    )
    results.append(run_test("Limit Orders", limit_input))

    # === TEST 3: Stop Orders (Breakout) ===
    print("\n--- Test 3: Stop Orders (Breakout) ---")
    stop_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.001,  # Higher slippage on breakout
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        entry_order_type="stop",
        stop_entry_offset=0.001,  # 0.1% выше текущей цены
        limit_entry_timeout_bars=5,
    )
    results.append(run_test("Stop Orders (Breakout)", stop_input))

    # === TEST 4: Risk-Based Position Sizing ===
    print("\n--- Test 4: Risk-Based Position Sizing ---")
    risk_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        position_sizing_mode="risk",
        risk_per_trade=0.02,  # 2% риска на сделку
        max_position_size=0.5,
        min_position_size=0.1,
    )
    results.append(run_test("Risk-Based Sizing", risk_input))

    # === TEST 5: Volatility-Based Position Sizing ===
    print("\n--- Test 5: Volatility-Based Position Sizing ---")
    vol_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        position_sizing_mode="volatility",
        volatility_target=0.02,
        max_position_size=0.8,
        min_position_size=0.1,
        atr_enabled=True,
        atr_period=14,
    )
    results.append(run_test("Volatility Sizing", vol_input))

    # === TEST 6: Re-entry Rules ===
    print("\n--- Test 6: Re-entry Rules ---")
    reentry_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        re_entry_delay_bars=4,  # 1 час между сделками (4 × 15m)
        max_trades_per_day=5,
        max_consecutive_losses=3,
        cooldown_after_loss=8,  # 2 часа кулдаун после убытка
    )
    results.append(run_test("Re-entry Rules", reentry_input))

    # === TEST 7: Time-Based Exits ===
    print("\n--- Test 7: Time-Based Exits (max 96 bars = 24h) ---")
    time_exit_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.05,  # Wider SL
        take_profit=0.10,  # Wider TP
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        max_bars_in_trade=96,  # 24 часа максимум
    )
    results.append(run_test("Max 24h in Trade", time_exit_input))

    # === TEST 8: No Trade Hours (Asia session only) ===
    print("\n--- Test 8: Trade Only Asia Session (0-8 UTC) ---")
    asia_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        no_trade_hours=tuple(range(8, 24)),  # Только 0-8 UTC
    )
    results.append(run_test("Asia Session Only", asia_input))

    # === TEST 9: Dynamic Slippage ===
    print("\n--- Test 9: Dynamic Slippage (Combined Model) ---")
    dyn_slip_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0003,  # Lower base
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        slippage_model="combined",
        slippage_volume_impact=0.2,
        slippage_volatility_mult=0.5,
        atr_enabled=True,
        atr_period=14,
    )
    results.append(run_test("Dynamic Slippage", dyn_slip_input))

    # === TEST 10: Funding Rate ===
    print("\n--- Test 10: With Funding Rate (0.01% / 8h) ---")
    funding_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        include_funding=True,
        funding_rate=0.0001,  # 0.01%
        funding_interval_hours=8,
    )
    results.append(run_test("With Funding", funding_input))

    # === TEST 11: Scale-In (Grid Entry) ===
    print("\n--- Test 11: Scale-In (50% сразу, 30% на -1%, 20% на -2%) ---")
    scale_in_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.03,  # Шире SL чтобы вместить сетку
        take_profit=0.04,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        scale_in_enabled=True,
        scale_in_levels=(0.0, -0.01, -0.02),  # 0%, -1%, -2%
        scale_in_portions=(0.5, 0.3, 0.2),  # 50%, 30%, 20%
    )
    results.append(run_test("Scale-In Grid", scale_in_input))

    # === TEST 12: Trend Filter (торговать по тренду) ===
    print("\n--- Test 12: Trend Filter (SMA 200, только по тренду) ---")
    trend_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        trend_filter_enabled=True,
        trend_filter_period=200,
        trend_filter_mode="with",  # Long только выше SMA, Short только ниже
    )
    results.append(run_test("Trend Filter", trend_input))

    # === TEST 13: Volatility Filter (не торговать при экстремах) ===
    print("\n--- Test 13: Volatility Filter (10-90 percentile) ---")
    vol_filter_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        volatility_filter_enabled=True,
        min_volatility_percentile=10.0,
        max_volatility_percentile=90.0,
        volatility_lookback=100,
        atr_enabled=True,
        atr_period=14,
    )
    results.append(run_test("Volatility Filter", vol_filter_input))

    # === TEST 14: Volume Filter (не торговать при низком объёме) ===
    print("\n--- Test 14: Volume Filter (>20 percentile) ---")
    vol_filter_input2 = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        volume_filter_enabled=True,
        min_volume_percentile=20.0,
        volume_lookback=50,
    )
    results.append(run_test("Volume Filter", vol_filter_input2))

    # === TEST 15: Momentum Filter (RSI oversold/overbought) ===
    print("\n--- Test 15: Momentum Filter (RSI <30 for Long, >70 for Short) ---")
    momentum_input = BacktestInput(
        candles=candles,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        initial_capital=10000,
        leverage=10,
        position_size=0.5,
        stop_loss=0.02,
        take_profit=0.03,
        taker_fee=0.0007,
        slippage=0.0005,
        direction=TradeDirection.BOTH,
        use_bar_magnifier=False,
        momentum_filter_enabled=True,
        momentum_oversold=30.0,
        momentum_overbought=70.0,
        momentum_period=14,
    )
    results.append(run_test("Momentum Filter", momentum_input))

    # === SUMMARY ===
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    valid_results = [r for r in results if r is not None]

    print(
        f"\n{'Test':<25} {'Trades':>8} {'Win%':>8} {'Net Profit':>12} {'MaxDD':>8} {'Sharpe':>8}"
    )
    print("-" * 70)

    for r in valid_results:
        print(
            f"{r['name']:<25} {r['trades']:>8} {r['win_rate'] * 100:>7.1f}% ${r['net_profit']:>10,.0f} {r['max_drawdown']:>7.1f}% {r['sharpe']:>8.2f}"
        )

    # Best by Sharpe
    if valid_results:
        best = max(valid_results, key=lambda x: x["sharpe"])
        print(f"\nBest by Sharpe: {best['name']} (Sharpe={best['sharpe']:.2f})")

    print("\n✅ All tests completed!")


if __name__ == "__main__":
    main()
