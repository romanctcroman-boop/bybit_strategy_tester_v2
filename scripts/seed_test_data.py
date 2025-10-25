"""Create seed data for testing frontend.

Creates:
- 2 test strategies
- 1 backtest with results
- Sample trades
- Sample OHLCV data for charts
"""

import json
import os
import sys
from datetime import datetime, timedelta

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import engine
from backend.models import Backtest, Optimization, Strategy, Trade
from sqlalchemy import text
from sqlalchemy.orm import Session as SessionClass


def create_seed_data():
    """Create test data for frontend testing."""
    session = SessionClass(bind=engine)

    try:
        # Create test strategies
        strategy1 = Strategy(
            name="EMA Crossover",
            description="Simple EMA crossover strategy (Fast 50, Slow 200)",
            strategy_type="ema_crossover",
            config={"fast_ema": 50, "slow_ema": 200, "stop_loss": 2.0, "take_profit": 4.0},
            is_active=True,
        )
        strategy2 = Strategy(
            name="RSI Mean Reversion",
            description="Buy when RSI < 30, Sell when RSI > 70",
            strategy_type="rsi_reversion",
            config={"rsi_period": 14, "oversold": 30, "overbought": 70},
            is_active=True,
        )

        session.add(strategy1)
        session.add(strategy2)
        session.flush()  # Get IDs

        print(f"✅ Created strategies: ID {strategy1.id}, ID {strategy2.id}")

        # Create test backtest
        backtest = Backtest(
            strategy_id=strategy1.id,
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now() - timedelta(days=1),
            initial_capital=10000.0,
            leverage=1.0,
            commission=0.0006,
            config=json.dumps({"slippage": 0.0, "max_position_size": 1.0}),
            status="completed",
            started_at=datetime.now() - timedelta(hours=2),
            completed_at=datetime.now() - timedelta(hours=1),
            final_capital=12450.75,
            total_return=24.51,
            total_trades=15,
            winning_trades=9,
            losing_trades=6,
            win_rate=60.0,
            sharpe_ratio=1.85,
            max_drawdown=-8.5,
            results=json.dumps(
                {
                    "equity_curve": [
                        {"timestamp": "2025-09-25T00:00:00Z", "equity": 10000.0},
                        {"timestamp": "2025-09-26T00:00:00Z", "equity": 10150.0},
                        {"timestamp": "2025-09-27T00:00:00Z", "equity": 10050.0},
                        {"timestamp": "2025-09-28T00:00:00Z", "equity": 10300.0},
                        {"timestamp": "2025-09-29T00:00:00Z", "equity": 10450.0},
                        {"timestamp": "2025-09-30T00:00:00Z", "equity": 10350.0},
                        {"timestamp": "2025-10-01T00:00:00Z", "equity": 10600.0},
                        {"timestamp": "2025-10-02T00:00:00Z", "equity": 10750.0},
                        {"timestamp": "2025-10-03T00:00:00Z", "equity": 10650.0},
                        {"timestamp": "2025-10-04T00:00:00Z", "equity": 10900.0},
                        {"timestamp": "2025-10-05T00:00:00Z", "equity": 11050.0},
                        {"timestamp": "2025-10-06T00:00:00Z", "equity": 11200.0},
                        {"timestamp": "2025-10-07T00:00:00Z", "equity": 11350.0},
                        {"timestamp": "2025-10-08T00:00:00Z", "equity": 11500.0},
                        {"timestamp": "2025-10-09T00:00:00Z", "equity": 11650.0},
                        {"timestamp": "2025-10-10T00:00:00Z", "equity": 11550.0},
                        {"timestamp": "2025-10-11T00:00:00Z", "equity": 11700.0},
                        {"timestamp": "2025-10-12T00:00:00Z", "equity": 11850.0},
                        {"timestamp": "2025-10-13T00:00:00Z", "equity": 11950.0},
                        {"timestamp": "2025-10-14T00:00:00Z", "equity": 12100.0},
                        {"timestamp": "2025-10-15T00:00:00Z", "equity": 12250.0},
                        {"timestamp": "2025-10-16T00:00:00Z", "equity": 12150.0},
                        {"timestamp": "2025-10-17T00:00:00Z", "equity": 12300.0},
                        {"timestamp": "2025-10-18T00:00:00Z", "equity": 12450.75},
                    ],
                    "metrics": {
                        "total_return": 24.51,
                        "win_rate": 60.0,
                        "sharpe_ratio": 1.85,
                        "max_drawdown": -8.5,
                        "profit_factor": 2.15,
                        "avg_win": 245.5,
                        "avg_loss": -145.3,
                    },
                }
            ),
        )

        session.add(backtest)
        session.flush()

        print(f"✅ Created backtest: ID {backtest.id}")

        # Create sample trades
        trades = [
            Trade(
                backtest_id=backtest.id,
                entry_time=datetime.now() - timedelta(days=25),
                exit_time=datetime.now() - timedelta(days=24, hours=8),
                side="long",
                entry_price=28500.0,
                exit_price=29200.0,
                quantity=0.35,
                pnl=245.0,
                pnl_pct=2.46,
            ),
            Trade(
                backtest_id=backtest.id,
                entry_time=datetime.now() - timedelta(days=23),
                exit_time=datetime.now() - timedelta(days=22, hours=12),
                side="long",
                entry_price=29300.0,
                exit_price=28900.0,
                quantity=0.34,
                pnl=-136.0,
                pnl_pct=-1.37,
            ),
            Trade(
                backtest_id=backtest.id,
                entry_time=datetime.now() - timedelta(days=20),
                exit_time=datetime.now() - timedelta(days=19, hours=6),
                side="long",
                entry_price=29500.0,
                exit_price=30100.0,
                quantity=0.34,
                pnl=204.0,
                pnl_pct=2.03,
            ),
            Trade(
                backtest_id=backtest.id,
                entry_time=datetime.now() - timedelta(days=18),
                exit_time=datetime.now() - timedelta(days=17, hours=10),
                side="long",
                entry_price=30200.0,
                exit_price=30800.0,
                quantity=0.33,
                pnl=198.0,
                pnl_pct=1.99,
            ),
            Trade(
                backtest_id=backtest.id,
                entry_time=datetime.now() - timedelta(days=15),
                exit_time=datetime.now() - timedelta(days=14, hours=8),
                side="long",
                entry_price=30900.0,
                exit_price=30400.0,
                quantity=0.32,
                pnl=-160.0,
                pnl_pct=-1.62,
            ),
        ]

        for trade in trades:
            session.add(trade)

        print(f"✅ Created {len(trades)} trades")

        # Create test optimization
        optimization = Optimization(
            strategy_id=strategy1.id,
            optimization_type="grid",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now() - timedelta(days=1),
            param_ranges={"fast_ema": [20, 50, 100], "slow_ema": [100, 200, 300]},
            metric="sharpe",
            initial_capital=10000.0,
            total_combinations=9,
            status="completed",
            started_at=datetime.now() - timedelta(hours=5),
            completed_at=datetime.now() - timedelta(hours=3),
        )

        session.add(optimization)
        session.flush()

        print(f"✅ Created optimization: ID {optimization.id}")

        # Add sample OHLCV data to bybit_kline_audit for charts
        sample_klines = []
        base_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)

        for i in range(720):  # 30 days * 24 hours
            timestamp = base_time + (i * 3600 * 1000)  # 1 hour intervals
            base_price = 28000 + (i * 10) + (100 * (i % 24))  # Simulate price movement

            kline = {
                "symbol": "BTCUSDT",
                "open_time": timestamp,
                "open_time_dt": datetime.fromtimestamp(timestamp / 1000),
                "open_price": base_price,
                "high_price": base_price + 100,
                "low_price": base_price - 80,
                "close_price": base_price + 50,
                "volume": 1000 + (i * 10),
                "turnover": (base_price * 1000),
                "raw": json.dumps(
                    {
                        "start": timestamp,
                        "open": str(base_price),
                        "high": str(base_price + 100),
                        "low": str(base_price - 80),
                        "close": str(base_price + 50),
                        "volume": str(1000 + (i * 10)),
                        "turnover": str(base_price * 1000),
                    }
                ),
            }
            sample_klines.append(kline)

        # Insert klines using raw SQL (faster for bulk insert)
        insert_stmt = """
            INSERT INTO bybit_kline_audit 
            (symbol, open_time, open_time_dt, open_price, high_price, low_price, close_price, volume, turnover, raw)
            VALUES 
            (:symbol, :open_time, :open_time_dt, :open_price, :high_price, :low_price, :close_price, :volume, :turnover, :raw)
        """

        session.execute(text(insert_stmt), sample_klines)

        print(f"✅ Created {len(sample_klines)} OHLCV klines for BTCUSDT")

        session.commit()
        print("\n🎉 Seed data created successfully!")
        print("\nSummary:")
        print(f"  - Strategies: 2")
        print(f"  - Backtests: 1 (with {len(trades)} trades)")
        print(f"  - Optimizations: 1")
        print(f"  - OHLCV Data: {len(sample_klines)} candles (30 days)")
        print("\nYou can now test the frontend pages!")

    except Exception as e:
        session.rollback()
        print(f"❌ Error creating seed data: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("Creating seed data for testing...")
    create_seed_data()
