#!/usr/bin/env python3
"""
Диагностический скрипт для сравнения FallbackEngineV2 и FallbackEngineV3
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
from backend.backtesting.interfaces import BacktestInput, TradeDirection


def load_ohlc_data(filepath: Path) -> pd.DataFrame:
    """Загрузка OHLC данных из CSV."""
    df = pd.read_csv(filepath)

    column_map = {
        "time": "timestamp",
        "Time": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df.rename(columns=column_map, inplace=True)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_tv_signals():
    """Load pre-extracted TradingView signals from .npy files."""
    tv_data_dir = Path("d:/TV")

    long_signals = np.load(tv_data_dir / "long_signals.npy")
    short_signals = np.load(tv_data_dir / "short_signals.npy")

    print(
        f"📥 Loaded TV signals: {long_signals.sum()} long, {short_signals.sum()} short"
    )

    return long_signals, short_signals


def main():
    # Load data
    data_file = Path("d:/TV/BYBIT_BTCUSDT.P_15m_full.csv")
    print(f"✅ Загрузка данных: {data_file.name}")
    candles = load_ohlc_data(data_file)
    print(f"   {len(candles)} баров")

    # Load TV signals
    print("\n📈 Загрузка TradingView сигналов...")
    long_entries, short_entries = load_tv_signals()

    # Config matching verify_engine_parity.py
    config = {
        "initial_capital": 1_000_000.0,
        "fixed_amount": 100.0,
        "leverage": 10,
        "take_profit": 0.015,
        "stop_loss": 0.03,
        "commission": 0.0007,
    }

    print("\n📋 Параметры стратегии:")
    print(f"   TP: {config['take_profit'] * 100}%, SL: {config['stop_loss'] * 100}%")
    print(
        f"   Leverage: {config['leverage']}x, Commission: {config['commission'] * 100}%"
    )

    # Run V2
    print("\n" + "=" * 80)
    print("Running FallbackEngineV2...")
    v2 = FallbackEngineV2()
    input_v2 = BacktestInput(
        candles=candles,
        candles_1m=None,
        initial_capital=config["initial_capital"],
        use_fixed_amount=True,
        fixed_amount=config["fixed_amount"],
        leverage=config["leverage"],
        take_profit=config["take_profit"],
        stop_loss=config["stop_loss"],
        taker_fee=config["commission"],
        direction=TradeDirection.BOTH,
        long_entries=long_entries,
        short_entries=short_entries,
        use_bar_magnifier=False,
    )
    result_v2 = v2.run(input_v2)

    # Run V3
    print("Running FallbackEngineV3...")
    v3 = FallbackEngineV3()
    input_v3 = BacktestInput(
        candles=candles,
        candles_1m=None,
        initial_capital=config["initial_capital"],
        use_fixed_amount=True,
        fixed_amount=config["fixed_amount"],
        leverage=config["leverage"],
        take_profit=config["take_profit"],
        stop_loss=config["stop_loss"],
        taker_fee=config["commission"],
        direction=TradeDirection.BOTH,
        long_entries=long_entries,
        short_entries=short_entries,
        use_bar_magnifier=False,
        pyramiding=1,
    )
    result_v3 = v3.run(input_v3)

    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)

    print(f"\nV2 trades: {len(result_v2.trades)}")
    print(f"V3 trades: {len(result_v3.trades)}")

    print(f"\nV2 Net Profit: {result_v2.metrics.net_profit:.4f}")
    print(f"V3 Net Profit: {result_v3.metrics.net_profit:.4f}")

    print(f"\nV2 Max Drawdown: {result_v2.metrics.max_drawdown:.4f}")
    print(f"V3 Max Drawdown: {result_v3.metrics.max_drawdown:.4f}")

    print(f"\nEquity curve lengths:")
    print(f"  V2: {len(result_v2.equity_curve)}")
    print(f"  V3: {len(result_v3.equity_curve)}")

    print(f"\nEquity curve first 5 values:")
    print(f"  V2: {result_v2.equity_curve[:5]}")
    print(f"  V3: {result_v3.equity_curve[:5]}")

    print(f"\nEquity curve last 5 values:")
    print(f"  V2: {result_v2.equity_curve[-5:]}")
    print(f"  V3: {result_v3.equity_curve[-5:]}")

    # Compare first 10 trades
    print("\n" + "-" * 80)
    print("FIRST 10 TRADES COMPARISON")
    print("-" * 80)

    for idx in range(min(10, max(len(result_v2.trades), len(result_v3.trades)))):
        t2 = result_v2.trades[idx] if idx < len(result_v2.trades) else None
        t3 = result_v3.trades[idx] if idx < len(result_v3.trades) else None

        print(f"\n--- Trade {idx + 1} ---")
        if t2:
            print(
                f"V2: {t2.direction:5s} entry={t2.entry_price:.2f} exit={t2.exit_price:.2f} pnl={t2.pnl:.4f} fees={t2.fees:.4f} reason={t2.exit_reason}"
            )
        else:
            print("V2: (no trade)")

        if t3:
            print(
                f"V3: {t3.direction:5s} entry={t3.entry_price:.2f} exit={t3.exit_price:.2f} pnl={t3.pnl:.4f} fees={t3.fees:.4f} reason={t3.exit_reason}"
            )
        else:
            print("V3: (no trade)")

        if t2 and t3:
            if abs(t2.pnl - t3.pnl) > 0.01:
                print(f"  ⚠️ PnL DIFF: {t2.pnl - t3.pnl:.4f}")
            if abs(t2.fees - t3.fees) > 0.01:
                print(f"  ⚠️ Fees DIFF: {t2.fees - t3.fees:.4f}")
            if t2.entry_price != t3.entry_price:
                print(f"  ⚠️ Entry price DIFF: {t2.entry_price} vs {t3.entry_price}")
            if t2.exit_price != t3.exit_price:
                print(f"  ⚠️ Exit price DIFF: {t2.exit_price} vs {t3.exit_price}")

    # Find first mismatching trade
    print("\n" + "-" * 80)
    print("FINDING FIRST MISMATCH...")
    print("-" * 80)

    for idx in range(max(len(result_v2.trades), len(result_v3.trades))):
        t2 = result_v2.trades[idx] if idx < len(result_v2.trades) else None
        t3 = result_v3.trades[idx] if idx < len(result_v3.trades) else None

        if t2 is None or t3 is None:
            print(f"\nTrade {idx + 1}: Missing trade!")
            if t2:
                print(
                    f"  V2: {t2.direction} entry={t2.entry_price:.2f} exit={t2.exit_price:.2f}"
                )
            if t3:
                print(
                    f"  V3: {t3.direction} entry={t3.entry_price:.2f} exit={t3.exit_price:.2f}"
                )
            # Show surrounding trades
            print("\n  Context (V2 trades around this):")
            for j in range(max(0, idx - 2), min(len(result_v2.trades), idx + 3)):
                t = result_v2.trades[j]
                marker = " <-- MISSING IN V3" if j == idx else ""
                print(
                    f"    Trade {j + 1}: {t.direction} entry={t.entry_price:.2f} exit={t.exit_price:.2f} {t.exit_reason}{marker}"
                )
            break

        diff = abs(t2.pnl - t3.pnl)
        if (
            diff > 0.01
            or t2.entry_price != t3.entry_price
            or t2.exit_price != t3.exit_price
        ):
            print(f"\nFirst mismatch at Trade {idx + 1}:")
            print(
                f"  V2: dir={t2.direction} entry={t2.entry_price:.2f} exit={t2.exit_price:.2f} pnl={t2.pnl:.4f} fees={t2.fees:.4f}"
            )
            print(
                f"  V3: dir={t3.direction} entry={t3.entry_price:.2f} exit={t3.exit_price:.2f} pnl={t3.pnl:.4f} fees={t3.fees:.4f}"
            )
            # Context around this
            print("\n  V2 trades around mismatch:")
            for j in range(max(0, idx - 3), min(len(result_v2.trades), idx + 5)):
                t = result_v2.trades[j]
                marker = " <-- MISMATCH" if j == idx else ""
                print(
                    f"    Trade {j + 1}: {t.direction} entry={t.entry_price:.2f} exit={t.exit_price:.2f} {t.exit_reason}{marker}"
                )

            print("\n  V3 trades around mismatch:")
            for j in range(max(0, idx - 3), min(len(result_v3.trades), idx + 5)):
                t = result_v3.trades[j]
                marker = " <-- MISMATCH" if j == idx else ""
                print(
                    f"    Trade {j + 1}: {t.direction} entry={t.entry_price:.2f} exit={t.exit_price:.2f} {t.exit_reason}{marker}"
                )
            break
    else:
        print("\nAll trades match!")


if __name__ == "__main__":
    main()
