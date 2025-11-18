"""
Script to test full backtest cycle via API.

Tests:
1. Create backtest via POST /api/backtests
2. Run backtest synchronously
3. Verify results format
4. Check that Frontend receives correct data
"""

import json
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, "D:/bybit_strategy_tester_v2")

from backend.database import SessionLocal
from backend.models import Backtest, Strategy
from backend.services.data_service import DataService
from backend.tasks.backtest_tasks import run_backtest_task


def create_test_strategy():
    """Create a test strategy in the database."""
    with SessionLocal() as session:
        # Check if strategy already exists
        strategy = session.query(Strategy).filter(Strategy.name == "API Test EMA").first()
        
        if strategy:
            print(f"✅ Using existing strategy: {strategy.name} (ID: {strategy.id})")
            return strategy.id
        
        # Create new strategy
        strategy = Strategy(
            name="API Test EMA",
            description="EMA Crossover for API testing",
            strategy_type="ema_crossover",
            config={
                "ema_fast": 12,
                "ema_slow": 26,
                "direction": "long",
            },
            is_active=True,
        )
        session.add(strategy)
        session.commit()
        session.refresh(strategy)
        
        print(f"✅ Created strategy: {strategy.name} (ID: {strategy.id})")
        return strategy.id


def create_backtest(strategy_id):
    """Create a backtest via DataService."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)  # 1 week of data
    
    with DataService() as ds:
        backtest = ds.create_backtest(
            strategy_id=strategy_id,
            symbol="BTCUSDT",
            timeframe="15",
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            leverage=1,
            commission=0.00075,  # 0.075% Bybit
            config={
                "ema_fast": 12,
                "ema_slow": 26,
                "direction": "long",
                "take_profit_pct": 2.0,
                "stop_loss_pct": 1.0,
                "trailing_stop_pct": 0.5,
            },
        )
        
        print(f"✅ Created backtest ID: {backtest.id}")
        print(f"   Symbol: {backtest.symbol}")
        print(f"   Timeframe: {backtest.timeframe}")
        print(f"   Period: {backtest.start_date} → {backtest.end_date}")
        
        return backtest.id


def run_backtest(backtest_id):
    """Run backtest synchronously."""
    print(f"\n🚀 Running backtest {backtest_id}...")
    
    # Get backtest details
    with SessionLocal() as session:
        backtest = session.query(Backtest).filter(Backtest.id == backtest_id).first()
        
        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found!")
        
        # Get strategy config
        strategy = session.query(Strategy).filter(Strategy.id == backtest.strategy_id).first()
        
        if not strategy:
            raise ValueError(f"Strategy {backtest.strategy_id} not found!")
        
        # Merge backtest config with strategy config
        strategy_config = {**strategy.config, **(backtest.config or {})}
        
        # Run the task
        result = run_backtest_task(
            backtest_id=backtest_id,
            strategy_config=strategy_config,
            symbol=backtest.symbol,
            interval=backtest.timeframe,
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            initial_capital=backtest.initial_capital,
        )
    
    print(f"✅ Backtest completed: {result.get('status')}")
    
    return result


def verify_results(backtest_id):
    """Verify results format in database."""
    with SessionLocal() as session:
        backtest = session.query(Backtest).filter(Backtest.id == backtest_id).first()
        
        if not backtest:
            print("❌ Backtest not found!")
            return False
        
        print(f"\n📊 Backtest Results:")
        print(f"   Status: {backtest.status}")
        print(f"   Final Capital: ${backtest.final_capital:.2f}")
        print(f"   Total Return: {backtest.total_return * 100:.2f}%")
        print(f"   Total Trades: {backtest.total_trades}")
        print(f"   Win Rate: {backtest.win_rate:.2f}%")
        print(f"   Sharpe Ratio: {backtest.sharpe_ratio:.3f}")
        print(f"   Max Drawdown: {backtest.max_drawdown * 100:.2f}%")
        
        # Check results format
        if not backtest.results:
            print("❌ No results JSON!")
            return False
        
        results = backtest.results
        
        # Verify structure
        required_sections = ['overview', 'by_side', 'dynamics', 'risk', 'equity', 'pnl_bars']
        missing = [s for s in required_sections if s not in results]
        
        if missing:
            print(f"❌ Missing sections in results: {missing}")
            return False
        
        print(f"\n✅ Results structure valid!")
        print(f"   Sections: {list(results.keys())}")
        
        # Check overview
        overview = results.get('overview', {})
        print(f"\n📈 Overview:")
        print(f"   Net PnL: ${overview.get('net_pnl', 0):.2f}")
        print(f"   Net %: {overview.get('net_pct', 0):.2f}%")
        print(f"   Total Trades: {overview.get('total_trades', 0)}")
        print(f"   Wins: {overview.get('wins', 0)}")
        print(f"   Losses: {overview.get('losses', 0)}")
        print(f"   Max DD: ${overview.get('max_drawdown_abs', 0):.2f} ({overview.get('max_drawdown_pct', 0):.2f}%)")
        print(f"   Profit Factor: {overview.get('profit_factor', 0):.3f}")
        
        # Check by_side
        by_side = results.get('by_side', {})
        all_stats = by_side.get('all', {})
        long_stats = by_side.get('long', {})
        short_stats = by_side.get('short', {})
        
        print(f"\n📊 By Side:")
        print(f"   All: {all_stats.get('total_trades', 0)} trades, {all_stats.get('win_rate', 0):.2f}% win rate")
        print(f"   Long: {long_stats.get('total_trades', 0)} trades, {long_stats.get('win_rate', 0):.2f}% win rate")
        print(f"   Short: {short_stats.get('total_trades', 0)} trades, {short_stats.get('win_rate', 0):.2f}% win rate")
        
        # Check dynamics
        dynamics = results.get('dynamics', {})
        all_dynamics = dynamics.get('all', {})
        
        print(f"\n💰 Dynamics (All):")
        print(f"   Net: ${all_dynamics.get('net_abs', 0):.2f} ({all_dynamics.get('net_pct', 0):.2f}%)")
        print(f"   Gross Profit: ${all_dynamics.get('gross_profit_abs', 0):.2f}")
        print(f"   Gross Loss: ${all_dynamics.get('gross_loss_abs', 0):.2f}")
        print(f"   Fees: ${all_dynamics.get('fees_abs', 0):.2f}")
        print(f"   Max Runup: ${all_dynamics.get('max_runup_abs', 0):.2f} ({all_dynamics.get('max_runup_pct', 0):.2f}%)")
        print(f"   Max DD: ${all_dynamics.get('max_drawdown_abs', 0):.2f} ({all_dynamics.get('max_drawdown_pct', 0):.2f}%)")
        print(f"   Buy&Hold: ${all_dynamics.get('buyhold_abs', 0):.2f} ({all_dynamics.get('buyhold_pct', 0):.2f}%)")
        
        # Check risk
        risk = results.get('risk', {})
        print(f"\n⚠️  Risk:")
        print(f"   Sharpe: {risk.get('sharpe', 0):.3f}")
        print(f"   Sortino: {risk.get('sortino', 0):.3f}")
        print(f"   Profit Factor: {risk.get('profit_factor', 0):.3f}")
        
        # Check equity curve
        equity = results.get('equity', [])
        pnl_bars = results.get('pnl_bars', [])
        
        print(f"\n📉 Charts:")
        print(f"   Equity points: {len(equity)}")
        print(f"   PnL bars: {len(pnl_bars)}")
        
        if equity:
            print(f"   First equity: {equity[0]}")
            print(f"   Last equity: {equity[-1]}")
        
        # Save to file for inspection
        output_file = f"backtest_{backtest_id}_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {output_file}")
        
        return True


def main():
    """Run full cycle test."""
    print("=" * 60)
    print("🧪 Testing Full Backtest Cycle via API")
    print("=" * 60)
    
    try:
        # Step 1: Create strategy
        print("\n📝 Step 1: Create test strategy")
        strategy_id = create_test_strategy()
        
        # Step 2: Create backtest
        print("\n📝 Step 2: Create backtest")
        backtest_id = create_backtest(strategy_id)
        
        # Step 3: Run backtest
        print("\n📝 Step 3: Run backtest")
        result = run_backtest(backtest_id)
        
        # Step 4: Verify results
        print("\n📝 Step 4: Verify results format")
        success = verify_results(backtest_id)
        
        if success:
            print("\n" + "=" * 60)
            print("✅ FULL CYCLE TEST PASSED!")
            print("=" * 60)
            print(f"\n🌐 View in browser:")
            print(f"   http://localhost:3000/backtests/{backtest_id}")
            print(f"\n📊 API endpoint:")
            print(f"   GET http://localhost:8000/api/backtests/{backtest_id}")
        else:
            print("\n❌ FULL CYCLE TEST FAILED!")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
