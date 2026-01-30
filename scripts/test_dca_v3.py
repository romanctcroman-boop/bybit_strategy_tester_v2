"""
Test DCA strategy with FallbackEngineV3 pyramiding.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
from backend.backtesting.interfaces import BacktestInput
from backend.backtesting.strategies import DCAStrategy
from backend.services.kline_db_service import KlineDBService


def main():
    print("=" * 60)
    print("🧪 DCA Strategy Test with FallbackEngineV3")
    print("=" * 60)

    # Load data from SQLite
    print("\n📊 Loading market data...")
    db_service = KlineDBService()
    klines = db_service.get_klines("BTCUSDT", "15", limit=2000)
    if not klines:
        print("❌ Failed to load data from SQLite")
        return

    df = pd.DataFrame(klines)
    # Rename columns to match expected format
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
    print(f"   Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    # DCA strategy params
    params = {
        "_direction": "long",
        "rsi_period": 14,
        "rsi_trigger": 35,  # RSI < 35 triggers base order
        "base_order_size": 10.0,  # 10% of capital
        "max_safety_orders": 3,  # 3 safety orders
        "safety_order_size": 15.0,  # 15% of capital
        "safety_order_volume_scale": 1.5,  # Each SO is 1.5x bigger
        "price_deviation": 1.0,  # First SO triggers at -1%
        "step_scale": 1.4,  # SO2 at -2.4%, SO3 at -4.76%
        "target_profit": 2.0,  # 2% take profit from average
        "trailing_deviation": 0.3,  # 0.3% trailing
        "stop_loss": 0.0,  # No stop loss
    }

    print("\n📈 DCA Parameters:")
    print(f"   Direction: {params['_direction']}")
    print(f"   RSI Trigger: < {params['rsi_trigger']}")
    print(f"   Base Order: {params['base_order_size']}%")
    print(f"   Max Safety Orders: {params['max_safety_orders']}")
    print(f"   Safety Order Size: {params['safety_order_size']}%")
    print(f"   Price Deviation (SO1): {params['price_deviation']}%")
    print(f"   Take Profit: {params['target_profit']}%")

    # Generate signals
    print("\n🔍 Generating DCA signals...")
    strategy = DCAStrategy(params)
    signals = strategy.generate_signals(df)

    print(f"   Long entries: {signals.entries.sum()}")
    print(f"   Long exits: {signals.exits.sum()}")

    # Check SO levels
    print("\n📊 Safety Order Levels:")
    for i, level in enumerate(strategy.so_levels):
        print(f"   SO{i + 1}: triggers at -{level * 100:.2f}% from entry")

    # Run with V3 engine (pyramiding)
    print("\n🚀 Running FallbackEngineV3 with pyramiding...")
    engine = FallbackEngineV3()

    input_data = BacktestInput(
        candles=df,
        candles_1m=None,  # No bar magnifier
        long_entries=signals.entries.values,
        long_exits=signals.exits.values,
        short_entries=None,
        short_exits=None,
        symbol="BTCUSDT",
        interval="15",
        initial_capital=10000,
        position_size=0.10,  # 10%
        use_fixed_amount=False,
        leverage=10,
        stop_loss=0,
        take_profit=0,  # DCA uses internal TP
        taker_fee=0.0007,
        slippage=0.0001,
        pyramiding=4,  # 1 base + 3 SOs = 4 max entries
        use_bar_magnifier=False,
    )

    result = engine.run(input_data)

    print("\n" + "=" * 60)
    print("📊 V3 BACKTEST RESULTS (with Pyramiding)")
    print("=" * 60)
    m = result.metrics
    print(f"   Total Trades: {m.total_trades}")
    print(f"   Net Profit: ${m.net_profit:.2f}")
    print(f"   Gross Profit: ${m.gross_profit:.2f}")
    print(f"   Gross Loss: ${m.gross_loss:.2f}")
    print(f"   Win Rate: {m.win_rate:.2%}")
    print(f"   Profit Factor: {m.profit_factor:.3f}")
    print(f"   Max Drawdown: {m.max_drawdown:.2%}")

    # Show sample trades
    if result.trades:
        print("\n📋 Sample Trades (first 10):")
        for i, trade in enumerate(result.trades[:10]):
            print(
                f"   {i + 1}. {trade.direction.upper()} "
                f"entry={trade.entry_price:.2f} exit={trade.exit_price:.2f} "
                f"pnl=${trade.pnl:.2f} ({trade.exit_reason.value})"
            )


if __name__ == "__main__":
    main()
