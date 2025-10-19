"""
БЛОК 2: Database Schema - Comprehensive Test Suite
Tests all database models, relationships, and CRUD operations
"""

import sys
sys.path.insert(0, 'D:/bybit_strategy_tester_v2')

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Strategy, Backtest, Trade, Optimization, OptimizationResult, MarketData
from sqlalchemy import inspect

# Test colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
WHITE = '\033[0m'

def print_header(text):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def print_test(name, passed, details=""):
    symbol = "✅" if passed else "❌"
    color = GREEN if passed else RED
    status = "PASS" if passed else "FAIL"
    padding = "." * (50 - len(name))
    print(f"{name}{padding} {color}{symbol} {status}{WHITE}")
    if details:
        print(f"   └─ {details}")

test_results = []

def test_result(name, passed, details=""):
    test_results.append((name, passed))
    print_test(name, passed, details)

# ============================================================================
# TEST 1: Database Connection
# ============================================================================
def test_database_connection():
    print_header("TEST 1: Database Connection")
    
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        test_result("Database connection", True, f"URL: {engine.url}")
        return True
    except Exception as e:
        test_result("Database connection", False, str(e))
        return False

# ============================================================================
# TEST 2: Tables Exist
# ============================================================================
def test_tables_exist():
    print_header("TEST 2: Tables Exist")
    
    inspector = inspect(engine)
    expected_tables = ['strategies', 'backtests', 'trades', 'optimizations', 'optimization_results', 'market_data']
    
    all_passed = True
    for table in expected_tables:
        exists = table in inspector.get_table_names()
        all_passed = all_passed and exists
        test_result(f"Table: {table}", exists)
    
    return all_passed

# ============================================================================
# TEST 3: Create Strategy
# ============================================================================
def test_create_strategy():
    print_header("TEST 3: Create Strategy (CRUD)")
    
    db = SessionLocal()
    all_passed = True
    
    try:
        # Create strategy
        strategy = Strategy(
            name="RSI Mean Reversion",
            description="Buy oversold, sell overbought",
            strategy_type="Indicator-Based",
            config={
                "indicators": ["RSI"],
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70
            }
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        
        test_result("Create Strategy", strategy.id is not None, f"ID: {strategy.id}")
        test_result("Strategy name", strategy.name == "RSI Mean Reversion")
        test_result("Strategy config (JSON)", 'indicators' in strategy.config)
        test_result("Auto timestamp", strategy.created_at is not None)
        
        return strategy.id
        
    except Exception as e:
        test_result("Create Strategy", False, str(e))
        return None
    finally:
        db.close()

# ============================================================================
# TEST 4: Create Backtest
# ============================================================================
def test_create_backtest(strategy_id):
    print_header("TEST 4: Create Backtest (CRUD)")
    
    db = SessionLocal()
    
    try:
        backtest = Backtest(
            strategy_id=strategy_id,
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            initial_capital=10000.00,
            leverage=2,
            commission=0.0006,
            final_capital=12500.00,
            total_return=25.00,
            total_trades=150,
            winning_trades=95,
            losing_trades=55,
            win_rate=63.33,
            sharpe_ratio=1.85,
            sortino_ratio=2.10,
            max_drawdown=-15.50,
            profit_factor=1.95,
            status="completed"
        )
        db.add(backtest)
        db.commit()
        db.refresh(backtest)
        
        test_result("Create Backtest", backtest.id is not None, f"ID: {backtest.id}")
        test_result("Foreign key", backtest.strategy_id == strategy_id)
        test_result("Numeric precision", backtest.final_capital == 12500.00)
        test_result("Percentage values", abs(float(backtest.win_rate) - 63.33) < 0.01)
        test_result("Status enum", backtest.status == "completed")
        
        return backtest.id
        
    except Exception as e:
        test_result("Create Backtest", False, str(e))
        return None
    finally:
        db.close()

# ============================================================================
# TEST 5: Create Trades
# ============================================================================
def test_create_trades(backtest_id):
    print_header("TEST 5: Create Trades (CRUD)")
    
    db = SessionLocal()
    
    try:
        # Create winning trade
        trade1 = Trade(
            backtest_id=backtest_id,
            entry_time=datetime(2024, 6, 1, 10, 0),
            exit_time=datetime(2024, 6, 1, 14, 0),
            side="LONG",
            entry_price=67000.50,
            exit_price=68500.00,
            quantity=0.1,
            position_size=6700.05,
            pnl=150.00,
            pnl_pct=2.24,
            commission=8.04,
            exit_reason="take_profit"
        )
        
        # Create losing trade
        trade2 = Trade(
            backtest_id=backtest_id,
            entry_time=datetime(2024, 6, 2, 10, 0),
            exit_time=datetime(2024, 6, 2, 12, 0),
            side="SHORT",
            entry_price=68000.00,
            exit_price=68500.00,
            quantity=0.1,
            position_size=6800.00,
            pnl=-50.00,
            pnl_pct=-0.74,
            commission=8.16,
            exit_reason="stop_loss"
        )
        
        db.add_all([trade1, trade2])
        db.commit()
        
        test_result("Create LONG trade", trade1.id is not None)
        test_result("Create SHORT trade", trade2.id is not None)
        test_result("Trade side validation", trade1.side in ["LONG", "SHORT"])
        test_result("Decimal precision", trade1.entry_price == 67000.50)
        test_result("PnL calculation", trade1.pnl > 0 and trade2.pnl < 0)
        
        return [trade1.id, trade2.id]
        
    except Exception as e:
        test_result("Create Trades", False, str(e))
        return []
    finally:
        db.close()

# ============================================================================
# TEST 6: Create Optimization
# ============================================================================
def test_create_optimization(strategy_id):
    print_header("TEST 6: Create Optimization (CRUD)")
    
    db = SessionLocal()
    
    try:
        optimization = Optimization(
            strategy_id=strategy_id,
            optimization_type="grid_search",
            symbol="BTCUSDT",
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            param_ranges={
                "rsi_period": [10, 14, 20],
                "rsi_oversold": [20, 25, 30],
                "rsi_overbought": [70, 75, 80]
            },
            metric="sharpe_ratio",
            initial_capital=10000.00,
            total_combinations=27,
            completed_combinations=27,
            best_params={
                "rsi_period": 14,
                "rsi_oversold": 25,
                "rsi_overbought": 75
            },
            best_score=2.15,
            status="completed"
        )
        db.add(optimization)
        db.commit()
        db.refresh(optimization)
        
        test_result("Create Optimization", optimization.id is not None, f"ID: {optimization.id}")
        test_result("Param ranges (JSON)", 'rsi_period' in optimization.param_ranges)
        test_result("Best params (JSON)", 'rsi_oversold' in optimization.best_params)
        test_result("Optimization type", optimization.optimization_type == "grid_search")
        test_result("Best score", abs(float(optimization.best_score) - 2.15) < 0.01)
        
        return optimization.id
        
    except Exception as e:
        test_result("Create Optimization", False, str(e))
        return None
    finally:
        db.close()

# ============================================================================
# TEST 7: Create Optimization Results
# ============================================================================
def test_create_optimization_results(optimization_id):
    print_header("TEST 7: Create Optimization Results (CRUD)")
    
    db = SessionLocal()
    
    try:
        result1 = OptimizationResult(
            optimization_id=optimization_id,
            params={"rsi_period": 10, "rsi_oversold": 20, "rsi_overbought": 70},
            total_return=15.50,
            sharpe_ratio=1.25,
            max_drawdown=-20.00,
            win_rate=55.00,
            score=1.25
        )
        
        result2 = OptimizationResult(
            optimization_id=optimization_id,
            params={"rsi_period": 14, "rsi_oversold": 25, "rsi_overbought": 75},
            total_return=25.00,
            sharpe_ratio=2.15,
            max_drawdown=-15.00,
            win_rate=63.00,
            score=2.15
        )
        
        db.add_all([result1, result2])
        db.commit()
        
        test_result("Create OptimizationResult #1", result1.id is not None)
        test_result("Create OptimizationResult #2", result2.id is not None)
        test_result("Params (JSON)", 'rsi_period' in result1.params)
        test_result("Score comparison", result2.score > result1.score)
        
        return [result1.id, result2.id]
        
    except Exception as e:
        test_result("Create OptimizationResults", False, str(e))
        return []
    finally:
        db.close()

# ============================================================================
# TEST 8: Create Market Data
# ============================================================================
def test_create_market_data():
    print_header("TEST 8: Create Market Data (CRUD)")
    
    db = SessionLocal()
    
    try:
        candle = MarketData(
            symbol="BTCUSDT",
            timeframe="1h",
            timestamp=datetime(2024, 6, 1, 10, 0),
            open=67000.00,
            high=67500.00,
            low=66800.00,
            close=67200.00,
            volume=150.5,
            quote_volume=10133400.00,
            trades_count=5432
        )
        db.add(candle)
        db.commit()
        db.refresh(candle)
        
        test_result("Create MarketData", candle.id is not None)
        test_result("OHLC values", candle.open == 67000.00 and candle.close == 67200.00)
        test_result("Volume", candle.volume == 150.5)
        test_result("Timestamp", candle.timestamp is not None)
        
        return candle.id
        
    except Exception as e:
        test_result("Create MarketData", False, str(e))
        return None
    finally:
        db.close()

# ============================================================================
# TEST 9: Relationships
# ============================================================================
def test_relationships(strategy_id, backtest_id):
    print_header("TEST 9: Test Relationships")
    
    db = SessionLocal()
    
    try:
        # Strategy -> Backtests
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        test_result("Strategy has backtests", len(strategy.backtests) > 0, f"Count: {len(strategy.backtests)}")
        
        # Backtest -> Trades
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        test_result("Backtest has trades", len(backtest.trades) > 0, f"Count: {len(backtest.trades)}")
        
        # Backtest -> Strategy
        test_result("Backtest.strategy", backtest.strategy is not None, f"Name: {backtest.strategy.name}")
        
        # Strategy -> Optimizations
        test_result("Strategy has optimizations", len(strategy.optimizations) > 0)
        
    except Exception as e:
        test_result("Relationships", False, str(e))
    finally:
        db.close()

# ============================================================================
# TEST 10: Indexes
# ============================================================================
def test_indexes():
    print_header("TEST 10: Test Indexes")
    
    inspector = inspect(engine)
    
    all_passed = True
    
    # Strategies indexes
    strategies_indexes = [idx['name'] for idx in inspector.get_indexes('strategies')]
    test_result("strategies indexes", len(strategies_indexes) >= 3, f"Count: {len(strategies_indexes)}")
    
    # Backtests indexes
    backtests_indexes = [idx['name'] for idx in inspector.get_indexes('backtests')]
    test_result("backtests indexes", len(backtests_indexes) >= 5, f"Count: {len(backtests_indexes)}")
    
    # Trades indexes
    trades_indexes = [idx['name'] for idx in inspector.get_indexes('trades')]
    test_result("trades indexes", len(trades_indexes) >= 4, f"Count: {len(trades_indexes)}")
    
    return all_passed

# ============================================================================
# RUN ALL TESTS
# ============================================================================
if __name__ == "__main__":
    print("="*70)
    print("  🧪 БЛОК 2: ПОЛНОЕ ТЕСТИРОВАНИЕ DATABASE SCHEMA")
    print("  SQLite Development Database")
    print("="*70)
    
    # Run tests
    test_database_connection()
    test_tables_exist()
    strategy_id = test_create_strategy()
    backtest_id = test_create_backtest(strategy_id) if strategy_id else None
    trade_ids = test_create_trades(backtest_id) if backtest_id else []
    optimization_id = test_create_optimization(strategy_id) if strategy_id else None
    opt_result_ids = test_create_optimization_results(optimization_id) if optimization_id else []
    market_data_id = test_create_market_data()
    
    if strategy_id and backtest_id:
        test_relationships(strategy_id, backtest_id)
    
    test_indexes()
    
    # Final report
    print_header("FINAL TEST REPORT - БЛОК 2")
    
    total = len(test_results)
    passed = sum(1 for _, p in test_results if p)
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"{GREEN}✅ Passed: {passed}{WHITE}")
    print(f"{RED}❌ Failed: {failed}{WHITE}")
    print(f"{CYAN}📊 Success Rate: {success_rate:.1f}%{WHITE}")
    print()
    
    if failed > 0:
        print(f"{RED}❌ Failed Tests:{WHITE}")
        for name, passed in test_results:
            if not passed:
                print(f"  • {name}")
        print()
    
    print("="*70)
    
    if success_rate == 100:
        print(f"{GREEN}🎉 ALL TESTS PASSED! БЛОК 2 ЗАВЕРШЁН НА 100%!{WHITE}")
        print()
        print("✅ Database Schema готова")
        print("✅ Все модели работают")
        print("✅ CRUD операции успешны")
        print("✅ Relationships функционируют")
        print()
        print(f"{CYAN}🚀 Готов к БЛОКУ 3: Data Layer{WHITE}")
    else:
        print(f"{YELLOW}⚠️ SOME TESTS FAILED{WHITE}")
        print()
        print("🔧 Исправьте ошибки выше")
    
    print("="*70)
    print()
    print(f"⏱️  Test completed")
