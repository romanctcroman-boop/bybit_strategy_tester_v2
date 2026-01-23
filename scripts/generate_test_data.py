"""
🧪 Generate Test Data for Dashboard

Creates realistic test data for strategies, backtests, and optimizations
to demonstrate dashboard functionality.

Usage:
    python scripts/generate_test_data.py [--clean]

Options:
    --clean     Clear existing test data before generating new
"""

import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Set DATABASE_URL to the actual database file
os.environ.setdefault("DATABASE_URL", f"sqlite:///{project_root}/data.sqlite3")

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.database.models.backtest import Backtest, BacktestStatus
from backend.database.models.optimization import (
    Optimization,
    OptimizationStatus,
    OptimizationType,
)
from backend.database.models.strategy import Strategy, StrategyStatus, StrategyType


def utc_now() -> datetime:
    """Get current UTC time with timezone awareness."""
    return datetime.now(timezone.utc)


# Realistic crypto symbols
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
]
TIMEFRAMES = ["15m", "1h", "4h", "1d"]

# Strategy templates
STRATEGY_TEMPLATES = [
    {
        "name": "Golden Cross BTC",
        "type": StrategyType.SMA_CROSSOVER,
        "params": {"fast_period": 50, "slow_period": 200},
    },
    {
        "name": "RSI Oversold Hunter",
        "type": StrategyType.RSI,
        "params": {"period": 14, "oversold": 30, "overbought": 70},
    },
    {
        "name": "MACD Divergence",
        "type": StrategyType.MACD,
        "params": {"fast": 12, "slow": 26, "signal": 9},
    },
    {
        "name": "Bollinger Breakout",
        "type": StrategyType.BOLLINGER_BANDS,
        "params": {"period": 20, "std_dev": 2},
    },
    {
        "name": "Multi-TF Momentum",
        "type": StrategyType.CUSTOM,
        "params": {"momentum_period": 10},
    },
    {
        "name": "Mean Reversion ETH",
        "type": StrategyType.BOLLINGER_BANDS,
        "params": {"period": 14, "std_dev": 2.5},
    },
    {
        "name": "Trend Following SOL",
        "type": StrategyType.SMA_CROSSOVER,
        "params": {"fast_period": 20, "slow_period": 50},
    },
    {
        "name": "Scalper 15m",
        "type": StrategyType.RSI,
        "params": {"period": 7, "oversold": 25, "overbought": 75},
    },
    # Additional strategies for more variety
    {
        "name": "Double Bottom Finder",
        "type": StrategyType.CUSTOM,
        "params": {"lookback": 50, "threshold": 0.02},
    },
    {
        "name": "Volatility Breakout",
        "type": StrategyType.BOLLINGER_BANDS,
        "params": {"period": 10, "std_dev": 1.5},
    },
    {
        "name": "EMA Cross XRP",
        "type": StrategyType.SMA_CROSSOVER,
        "params": {"fast_period": 9, "slow_period": 21},
    },
    {
        "name": "RSI Divergence Pro",
        "type": StrategyType.RSI,
        "params": {"period": 21, "oversold": 35, "overbought": 65},
    },
    {
        "name": "MACD Histogram Strategy",
        "type": StrategyType.MACD,
        "params": {"fast": 8, "slow": 17, "signal": 9},
    },
    {
        "name": "Swing Trader DOGE",
        "type": StrategyType.CUSTOM,
        "params": {"swing_period": 14, "atr_mult": 2.0},
    },
    {
        "name": "Breakout Momentum ADA",
        "type": StrategyType.BOLLINGER_BANDS,
        "params": {"period": 20, "std_dev": 2.2},
    },
    {
        "name": "Trend Rider AVAX",
        "type": StrategyType.SMA_CROSSOVER,
        "params": {"fast_period": 10, "slow_period": 30},
    },
]


def clear_test_data(db: Session) -> None:
    """Remove all test data from database."""
    print("🗑️  Clearing existing data...")
    db.query(Backtest).delete()
    db.query(Optimization).delete()
    db.query(Strategy).delete()
    db.commit()
    print("✅ Data cleared")


def generate_strategies(db: Session, count: int = 8) -> list[Strategy]:
    """Generate test strategies."""
    print(f"📝 Generating {count} strategies...")
    strategies = []

    for i, template in enumerate(STRATEGY_TEMPLATES[:count]):
        symbol = random.choice(SYMBOLS)
        timeframe = random.choice(TIMEFRAMES)

        # Mix of active and other statuses
        if i < 5:
            status = StrategyStatus.ACTIVE
        elif i < 7:
            status = StrategyStatus.PAUSED
        else:
            status = StrategyStatus.DRAFT

        strategy = Strategy(
            id=str(uuid.uuid4()),
            name=template["name"],
            description=f"Test strategy: {template['name']} on {symbol}",
            strategy_type=template["type"],
            status=status,
            parameters=template["params"],
            symbol=symbol,
            timeframe=timeframe,
            initial_capital=10000.0,
            position_size=1.0,
            stop_loss_pct=random.uniform(1.0, 3.0),
            take_profit_pct=random.uniform(2.0, 6.0),
            max_drawdown_pct=random.uniform(10.0, 25.0),
            created_at=utc_now() - timedelta(days=random.randint(1, 30)),
            updated_at=utc_now(),
        )
        strategies.append(strategy)
        db.add(strategy)

    db.commit()
    print(f"✅ Created {len(strategies)} strategies")
    return strategies


def generate_backtests(
    db: Session, strategies: list[Strategy], count: int = 50
) -> list[Backtest]:
    """Generate test backtests with realistic metrics."""
    print(f"📊 Generating {count} backtests...")
    backtests = []

    now = utc_now()

    for i in range(count):
        strategy = random.choice(strategies)

        # Determine status with realistic distribution
        status_roll = random.random()
        if status_roll < 0.75:  # 75% completed
            status = BacktestStatus.COMPLETED
        elif status_roll < 0.85:  # 10% running
            status = BacktestStatus.RUNNING
        elif status_roll < 0.95:  # 10% failed
            status = BacktestStatus.FAILED
        else:  # 5% pending
            status = BacktestStatus.PENDING

        # Random date range for backtest - include recent (last 24h) backtests
        if i < count // 3:
            # 1/3 of backtests are from last 24 hours
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(hours=hours_ago, minutes=random.randint(0, 59))
        else:
            # Rest spread over 1-14 days
            days_ago = random.randint(1, 14)
            created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))
        start_date = created_at - timedelta(days=random.randint(30, 180))
        end_date = created_at - timedelta(days=1)

        # Realistic performance metrics (only for completed)
        if status == BacktestStatus.COMPLETED:
            # Simulate realistic returns (-30% to +80%)
            total_return = random.gauss(15, 25)  # Mean 15%, std 25%
            total_return = max(-50, min(100, total_return))  # Clamp

            # Calculate other metrics based on return
            is_profitable = total_return > 0

            win_rate = (
                random.uniform(0.45, 0.65)
                if is_profitable
                else random.uniform(0.30, 0.50)
            )
            total_trades = random.randint(20, 200)
            winning_trades = int(total_trades * win_rate)
            losing_trades = total_trades - winning_trades

            sharpe_ratio = total_return / 20 + random.uniform(-0.5, 0.5)
            sortino_ratio = sharpe_ratio * random.uniform(1.1, 1.4)
            max_drawdown = random.uniform(5, 30)
            profit_factor = (
                (1 + total_return / 100) / (1 + max_drawdown / 100)
                if max_drawdown > 0
                else 1.5
            )

            initial_capital = 10000.0
            final_capital = initial_capital * (1 + total_return / 100)
            peak_capital = final_capital * random.uniform(1.0, 1.15)

            execution_time_ms = random.randint(5000, 120000)
            started_at = created_at
            completed_at = created_at + timedelta(milliseconds=execution_time_ms)

            avg_trade_pnl = (
                (final_capital - initial_capital) / total_trades
                if total_trades > 0
                else 0
            )
            best_trade = abs(avg_trade_pnl) * random.uniform(2, 5)
            worst_trade = -abs(avg_trade_pnl) * random.uniform(1.5, 4)

            error_message = None
        elif status == BacktestStatus.FAILED:
            # Failed backtest
            total_return = None
            win_rate = None
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
            sharpe_ratio = None
            sortino_ratio = None
            max_drawdown = None
            profit_factor = None
            initial_capital = 10000.0
            final_capital = None
            peak_capital = None
            execution_time_ms = random.randint(1000, 10000)
            started_at = created_at
            completed_at = created_at + timedelta(milliseconds=execution_time_ms)
            avg_trade_pnl = None
            best_trade = None
            worst_trade = None
            error_message = random.choice(
                [
                    "Insufficient data for backtest period",
                    "API rate limit exceeded",
                    "Invalid strategy parameters",
                    "Memory limit exceeded",
                ]
            )
        else:
            # Running or Pending
            total_return = None
            win_rate = None
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
            sharpe_ratio = None
            sortino_ratio = None
            max_drawdown = None
            profit_factor = None
            initial_capital = 10000.0
            final_capital = None
            peak_capital = None
            execution_time_ms = None
            started_at = created_at if status == BacktestStatus.RUNNING else None
            completed_at = None
            avg_trade_pnl = None
            best_trade = None
            worst_trade = None
            error_message = None

        backtest = Backtest(
            id=str(uuid.uuid4()),
            strategy_id=strategy.id,
            strategy_type=strategy.strategy_type.value,
            status=status,
            error_message=error_message,
            symbol=strategy.symbol or random.choice(SYMBOLS),
            timeframe=strategy.timeframe or random.choice(TIMEFRAMES),
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            parameters=strategy.parameters,
            total_return=total_return,
            annual_return=total_return * 2
            if total_return
            else None,  # Rough annualized
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_trade_pnl=avg_trade_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade,
            final_capital=final_capital,
            peak_capital=peak_capital,
            execution_time_ms=execution_time_ms,
            started_at=started_at,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=completed_at or created_at,
        )
        backtests.append(backtest)
        db.add(backtest)

    db.commit()

    # Count stats
    completed = sum(1 for b in backtests if b.status == BacktestStatus.COMPLETED)
    running = sum(1 for b in backtests if b.status == BacktestStatus.RUNNING)
    failed = sum(1 for b in backtests if b.status == BacktestStatus.FAILED)

    print(
        f"✅ Created {len(backtests)} backtests (completed: {completed}, running: {running}, failed: {failed})"
    )
    return backtests


def generate_optimizations(
    db: Session, strategies: list[Strategy], count: int = 10
) -> list[Optimization]:
    """Generate test optimization runs."""
    print(f"⚙️  Generating {count} optimizations...")
    optimizations = []

    now = utc_now()

    for i in range(count):
        strategy = random.choice(strategies)

        # Status distribution
        status_roll = random.random()
        if status_roll < 0.6:
            status = OptimizationStatus.COMPLETED
        elif status_roll < 0.8:
            status = OptimizationStatus.RUNNING
        else:
            status = OptimizationStatus.QUEUED

        created_at = now - timedelta(
            days=random.randint(0, 7), hours=random.randint(0, 23)
        )

        total_combinations = random.randint(50, 200)
        evaluated = (
            total_combinations
            if status == OptimizationStatus.COMPLETED
            else random.randint(0, total_combinations)
        )

        optimization = Optimization(
            strategy_id=strategy.id,
            optimization_type=OptimizationType.GRID_SEARCH,
            symbol=strategy.symbol or random.choice(SYMBOLS),
            timeframe=strategy.timeframe or random.choice(TIMEFRAMES),
            start_date=created_at - timedelta(days=90),
            end_date=created_at - timedelta(days=1),
            param_ranges={
                "fast_period": {"min": 10, "max": 50, "step": 5},
                "slow_period": {"min": 50, "max": 200, "step": 10},
            },
            metric="sharpe_ratio",
            initial_capital=10000.0,
            total_combinations=total_combinations,
            evaluated_combinations=evaluated
            if status != OptimizationStatus.QUEUED
            else 0,
            status=status,
            progress=evaluated / total_combinations if total_combinations > 0 else 0.0,
            best_params=strategy.parameters
            if status == OptimizationStatus.COMPLETED
            else None,
            best_score=random.uniform(1.0, 3.0)
            if status == OptimizationStatus.COMPLETED
            else None,
            created_at=created_at,
            updated_at=now,
        )
        optimizations.append(optimization)
        db.add(optimization)

    db.commit()

    completed = sum(
        1 for o in optimizations if o.status == OptimizationStatus.COMPLETED
    )
    running = sum(1 for o in optimizations if o.status == OptimizationStatus.RUNNING)

    print(
        f"✅ Created {len(optimizations)} optimizations (completed: {completed}, running: {running})"
    )
    return optimizations


def update_strategy_stats(
    db: Session, strategies: list[Strategy], backtests: list[Backtest]
) -> None:
    """Update strategy statistics based on backtests."""
    print("📈 Updating strategy statistics...")

    for strategy in strategies:
        # Get completed backtests for this strategy
        strategy_backtests = [
            b
            for b in backtests
            if b.strategy_id == strategy.id and b.status == BacktestStatus.COMPLETED
        ]

        if strategy_backtests:
            strategy.backtest_count = len(strategy_backtests)
            strategy.total_trades = sum(b.total_trades or 0 for b in strategy_backtests)

            # Average metrics
            returns = [
                b.total_return for b in strategy_backtests if b.total_return is not None
            ]
            if returns:
                strategy.total_return = sum(returns) / len(returns)

            sharpes = [
                b.sharpe_ratio for b in strategy_backtests if b.sharpe_ratio is not None
            ]
            if sharpes:
                strategy.sharpe_ratio = sum(sharpes) / len(sharpes)

            win_rates = [
                b.win_rate for b in strategy_backtests if b.win_rate is not None
            ]
            if win_rates:
                strategy.win_rate = sum(win_rates) / len(win_rates)

            # Last backtest date
            dates = [b.completed_at for b in strategy_backtests if b.completed_at]
            if dates:
                strategy.last_backtest_at = max(dates)

    db.commit()
    print("✅ Strategy statistics updated")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate test data for dashboard")
    parser.add_argument(
        "--clean", action="store_true", help="Clear existing data first"
    )
    parser.add_argument(
        "--strategies", type=int, default=8, help="Number of strategies"
    )
    parser.add_argument("--backtests", type=int, default=50, help="Number of backtests")
    parser.add_argument(
        "--optimizations", type=int, default=10, help="Number of optimizations"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🧪 TEST DATA GENERATOR")
    print("=" * 60)

    db = SessionLocal()

    try:
        if args.clean:
            clear_test_data(db)

        strategies = generate_strategies(db, args.strategies)
        backtests = generate_backtests(db, strategies, args.backtests)
        optimizations = generate_optimizations(db, strategies, args.optimizations)
        update_strategy_stats(db, strategies, backtests)

        print("=" * 60)
        print("✅ TEST DATA GENERATION COMPLETE!")
        print("=" * 60)
        print(f"   Strategies:    {len(strategies)}")
        print(f"   Backtests:     {len(backtests)}")
        print(f"   Optimizations: {len(optimizations)}")
        print("=" * 60)
        print("🔄 Refresh the dashboard to see the new data!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
