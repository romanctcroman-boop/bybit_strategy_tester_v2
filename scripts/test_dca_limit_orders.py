"""
Test DCA with limit orders (Safety Orders) in FallbackEngineV3.

This test demonstrates:
1. Base Order - triggered by signal (RSI)
2. Safety Orders - triggered by price levels (limit orders)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.services.kline_db_service import KlineDBService


def main():
    print("=" * 70)
    print("🧪 DCA with Limit Orders (Safety Orders) Test")
    print("=" * 70)

    # Load data from SQLite
    print("\n📊 Loading market data...")
    db_service = KlineDBService()
    klines = db_service.get_klines("BTCUSDT", "15", limit=3000)
    if not klines:
        print("❌ Failed to load data from SQLite")
        return

    df = pd.DataFrame(klines)
    df = df.rename(
        columns={
            "open_time": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
    )
    print(f"   ✅ Loaded {len(df)} bars")

    # Create simple RSI-based entry signals
    # RSI < 30 = oversold = BUY signal
    print("\n📈 Generating RSI signals...")

    # Calculate RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    alpha = 1.0 / 14
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    rsi = 100 - (100 / (1 + rs))

    # Entry signal: RSI < 30
    long_entries = (rsi < 30).values
    # Exit signal: RSI > 70
    long_exits = (rsi > 70).values

    print(f"   Entry signals (RSI < 30): {long_entries.sum()}")
    print(f"   Exit signals (RSI > 70): {long_exits.sum()}")

    # DCA Parameters (3commas style)
    print("\n📊 DCA Parameters:")
    print("   Base Order: 10% of capital")
    print("   Safety Orders: 3")
    print("   Price Deviation (SO1): 2%")
    print("   Step Scale: 1.5 (SO2 at 3%, SO3 at 4.5%)")
    print("   Volume Scale: 1.5 (martingale)")
    print("   Pyramiding: 4 (1 base + 3 SOs)")

    # Calculate SO levels for display
    print("\n📊 Safety Order Levels:")
    deviation = 0.02
    step_scale = 1.5
    cumulative = 0.0
    for i in range(3):
        cumulative += deviation
        print(f"   SO{i + 1}: triggers at -{cumulative * 100:.1f}% from entry")
        deviation *= step_scale

    # Run with V3 engine (DCA mode)
    print("\n🚀 Running FallbackEngineV3 with DCA...")
    engine = FallbackEngineV3()

    input_data = BacktestInput(
        candles=df,
        candles_1m=None,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=None,
        short_exits=None,
        symbol="BTCUSDT",
        interval="15",
        initial_capital=10000,
        position_size=0.10,  # 10% base order
        use_fixed_amount=False,
        leverage=10,
        direction=TradeDirection.LONG,
        stop_loss=0,  # DCA handles risk
        take_profit=0.05,  # 5% TP
        taker_fee=0.0007,
        slippage=0.0001,
        use_bar_magnifier=False,
        # DCA Parameters
        dca_enabled=True,
        dca_safety_orders=3,  # 3 Safety Orders
        dca_price_deviation=0.02,  # First SO at -2%
        dca_step_scale=1.5,  # SO2 at -5%, SO3 at -9.5%
        dca_volume_scale=1.5,  # Martingale: each SO is 1.5x bigger
        dca_base_order_size=0.10,  # 10% for base
        dca_safety_order_size=0.10,  # 10% for first SO
        pyramiding=4,  # 1 base + 3 SOs
    )

    result = engine.run(input_data)

    print("\n" + "=" * 70)
    print("📊 DCA BACKTEST RESULTS")
    print("=" * 70)
    m = result.metrics
    print(f"   Total Trades: {m.total_trades}")
    print(f"   Net Profit: ${m.net_profit:.2f}")
    print(f"   Gross Profit: ${m.gross_profit:.2f}")
    print(f"   Gross Loss: ${m.gross_loss:.2f}")
    print(f"   Win Rate: {m.win_rate:.2%}")
    print(f"   Profit Factor: {m.profit_factor:.3f}")
    print(f"   Max Drawdown: {m.max_drawdown:.2%}")

    # Show trades with entry details
    if result.trades:
        print(f"\n📋 All {len(result.trades)} Trades:")
        for i, trade in enumerate(result.trades):
            print(
                f"   {i + 1}. {trade.direction.upper()} "
                f"entry={trade.entry_price:.2f} exit={trade.exit_price:.2f} "
                f"size={trade.size:.4f} pnl=${trade.pnl:.2f} ({trade.exit_reason.value})"
            )

    # Summary
    print("\n" + "=" * 70)
    print("✅ DCA TEST COMPLETE")
    print("=" * 70)
    print("""
    Expected behavior:
    1. Base Order opens when RSI < 30
    2. Safety Orders trigger automatically when price drops:
       - SO1 at -2% from entry
       - SO2 at -5% from entry (2% + 3%)
       - SO3 at -9.5% from entry (2% + 3% + 4.5%)
    3. Position closes at 5% Take Profit from average price
    """)


if __name__ == "__main__":
    main()
