"""
Full System Diagnostic - Sprint 1 Kickoff
Runs comprehensive checks on all critical components
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit
from sqlalchemy import select, func
import pandas as pd
import numpy as np


async def diagnostic_1_database():
    """Check database status"""
    print("\n" + "="*80)
    print("🔍 DIAGNOSTIC 1: DATABASE STATUS")
    print("="*80)
    
    try:
        db = SessionLocal()
        
        # Count bars
        count = db.query(func.count(BybitKlineAudit.id)).scalar()
        print(f"✅ Database connection: OK")
        print(f"   Total bars: {count:,}")
        
        # Get date range
        min_date = db.query(func.min(BybitKlineAudit.open_time_dt)).scalar()
        max_date = db.query(func.max(BybitKlineAudit.open_time_dt)).scalar()
        duration = (max_date - min_date).days
        
        print(f"   Date range: {min_date} to {max_date}")
        print(f"   Duration: {duration} days ({duration/30:.1f} months)")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


async def diagnostic_2_monte_carlo_bug():
    """Diagnose Monte Carlo Std Dev = 0 bug"""
    print("\n" + "="*80)
    print("🐛 DIAGNOSTIC 2: MONTE CARLO STD DEV BUG")
    print("="*80)
    
    try:
        from tests.integration.test_extended_backtest_suite import ExtendedBacktestSuite
        
        suite = ExtendedBacktestSuite()
        
        # Load data
        print("Loading 6-month data...")
        suite.test_load_6month_data()
        
        # Run standard backtest
        print("Running standard backtest...")
        suite.test_standard_6month_backtest()
        
        # Analyze trade PnLs
        trades = suite.standard_results.get('trades', [])
        pnls = [t.get('pnl', 0) for t in trades]
        
        pnl_series = pd.Series(pnls)
        
        print(f"\n📊 Trade PnL Analysis:")
        print(f"   Total trades: {len(trades)}")
        print(f"   Min PnL: ${pnl_series.min():.4f}")
        print(f"   Max PnL: ${pnl_series.max():.4f}")
        print(f"   Mean PnL: ${pnl_series.mean():.4f}")
        print(f"   Std Dev: ${pnl_series.std():.4f}")
        print(f"   Variance: ${pnl_series.var():.4f}")
        
        # Check if all PnLs are identical
        unique_pnls = len(set(pnls))
        print(f"   Unique PnL values: {unique_pnls}")
        
        if pnl_series.std() < 0.01:
            print("\n🚨 PROBLEM DETECTED:")
            print("   Trade PnLs have near-zero variance!")
            print("   This causes Monte Carlo Std Dev = 0.00%")
            print("\n   Possible causes:")
            print("   1. All trades hitting same TP/SL")
            print("   2. Fixed position size + fixed TP/SL = identical PnLs")
            print("   3. Bug in backtest engine")
            return False
        else:
            print("\n✅ Trade PnLs have healthy variance")
            print("   Monte Carlo should work correctly")
            return True
            
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def diagnostic_3_walk_forward_config():
    """Check Walk-Forward configuration"""
    print("\n" + "="*80)
    print("📊 DIAGNOSTIC 3: WALK-FORWARD CONFIGURATION")
    print("="*80)
    
    try:
        # Calculate optimal WFO parameters for 52K bars
        total_bars = 52001
        target_cycles = 12
        
        # Calculate
        in_sample = 8000   # ~27 days
        out_sample = 2000  # ~7 days
        step = 2000
        
        total_used = in_sample + (target_cycles - 1) * step
        
        print(f"Current data: {total_bars:,} bars")
        print(f"\nProposed WFO Configuration:")
        print(f"   In-sample: {in_sample:,} bars (~{in_sample*5/60/24:.1f} days)")
        print(f"   Out-of-sample: {out_sample:,} bars (~{out_sample*5/60/24:.1f} days)")
        print(f"   Step size: {step:,} bars (~{step*5/60/24:.1f} days)")
        print(f"   Target cycles: {target_cycles}")
        print(f"   Total bars used: {total_used:,} / {total_bars:,}")
        print(f"   Unused bars: {total_bars - total_used:,}")
        
        if total_used <= total_bars:
            print(f"\n✅ Configuration VALID")
            print(f"   Will produce {target_cycles} reoptimization cycles")
            return True
        else:
            print(f"\n⚠️ Configuration INVALID (not enough data)")
            return False
            
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")
        return False


async def diagnostic_4_strategy_metrics():
    """Analyze current strategy performance"""
    print("\n" + "="*80)
    print("📈 DIAGNOSTIC 4: STRATEGY PERFORMANCE ANALYSIS")
    print("="*80)
    
    try:
        from tests.integration.test_extended_backtest_suite import ExtendedBacktestSuite
        
        suite = ExtendedBacktestSuite()
        
        # Load and backtest
        suite.test_load_6month_data()
        suite.test_standard_6month_backtest()
        
        results = suite.standard_results
        
        print(f"Strategy: EMA 15/40 (Walk-Forward optimal)")
        print(f"\nPerformance Metrics:")
        print(f"   Total Trades: {results.get('total_trades', 0)}")
        print(f"   Win Rate: {results.get('win_rate', 0):.2f}%")
        print(f"   Total Return: {results.get('total_return', 0):.2f}%")
        print(f"   Sharpe Ratio: {results.get('sharpe_ratio', 0):.3f}")
        print(f"   Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
        print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
        
        # Perplexity benchmarks
        print(f"\n📊 Perplexity AI Benchmarks:")
        print(f"   Win Rate: Target >55%, Current {results.get('win_rate', 0):.1f}%")
        print(f"   Profit Factor: Target >1.5, Current {results.get('profit_factor', 0):.2f}")
        
        # Market regime
        suite.test_market_regime_detection()
        regime = suite.regime_distribution
        
        print(f"\n🌐 Market Regime (6 months):")
        print(f"   Sideways: {regime.get('sideways', 0):.1f}%")
        print(f"   Trending: {regime.get('neutral', 0) + regime.get('bull', 0) + regime.get('bear', 0):.1f}%")
        
        if regime.get('sideways', 0) > 90:
            print(f"\n⚠️ WARNING: Trend-following strategy in 90%+ sideways market")
            print(f"   Recommendation: Implement mean-reversion strategies")
            print(f"   - Support/Resistance")
            print(f"   - Bollinger Bands")
            print(f"   - RSI confirmation")
        
        return True
        
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def diagnostic_5_frontend_readiness():
    """Check frontend readiness"""
    print("\n" + "="*80)
    print("🎨 DIAGNOSTIC 5: FRONTEND READINESS")
    print("="*80)
    
    # Check if frontend directory exists
    frontend_dir = Path(__file__).parent / 'frontend'
    
    if frontend_dir.exists():
        print(f"✅ Frontend directory exists: {frontend_dir}")
        
        # Check package.json
        package_json = frontend_dir / 'package.json'
        if package_json.exists():
            print(f"✅ package.json found")
            import json
            with open(package_json) as f:
                pkg = json.load(f)
                print(f"   Name: {pkg.get('name', 'N/A')}")
                print(f"   Version: {pkg.get('version', 'N/A')}")
        else:
            print(f"⚠️ package.json not found")
            
        # Check node_modules
        node_modules = frontend_dir / 'node_modules'
        if node_modules.exists():
            print(f"✅ node_modules installed")
        else:
            print(f"⚠️ node_modules not found (run npm install)")
            
    else:
        print(f"❌ Frontend directory not found")
        print(f"   Recommendation: Clone electron-react-boilerplate")
        print(f"   Command: git clone https://github.com/electron-react-boilerplate/electron-react-boilerplate.git frontend")
        return False
    
    return True


async def run_full_diagnostic():
    """Run all diagnostics"""
    print("\n" + "="*80)
    print("🔬 FULL SYSTEM DIAGNOSTIC - SPRINT 1 KICKOFF")
    print("="*80)
    print(f"Date: 2025-10-29")
    print(f"Sprint: Week 1 (Oct 30 - Nov 5)")
    
    results = {
        'database': await diagnostic_1_database(),
        'monte_carlo': await diagnostic_2_monte_carlo_bug(),
        'walk_forward': await diagnostic_3_walk_forward_config(),
        'strategy': await diagnostic_4_strategy_metrics(),
        'frontend': await diagnostic_5_frontend_readiness(),
    }
    
    # Summary
    print("\n" + "="*80)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*80)
    
    for name, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {name.replace('_', ' ').title()}: {'PASS' if status else 'FAIL'}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} diagnostics passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL DIAGNOSTICS PASSED")
        print("   System ready for Sprint 1 development!")
    else:
        print(f"\n⚠️ {total - passed} diagnostic(s) failed")
        print("   Review issues above before starting development")
    
    # Recommendations
    print("\n" + "="*80)
    print("💡 IMMEDIATE RECOMMENDATIONS")
    print("="*80)
    
    if not results['monte_carlo']:
        print("\n🔴 CRITICAL: Fix Monte Carlo bug")
        print("   Issue: Trade PnLs have near-zero variance")
        print("   Action: Investigate backtest engine position sizing")
        print("   File: backend/core/backtest_engine.py")
        print("   Estimate: 2-3 hours")
    
    if not results['frontend']:
        print("\n🟡 HIGH: Setup frontend")
        print("   Action: Clone electron-react-boilerplate")
        print("   Command: git clone https://github.com/electron-react-boilerplate/electron-react-boilerplate.git frontend")
        print("   Estimate: 1 day")
    
    print("\n🟢 RECOMMENDED: Start parallel development")
    print("   Backend team: Fix Monte Carlo + expand Walk-Forward")
    print("   Frontend team: Setup Electron app + basic UI")
    print("   Duration: Week 1 (5 days)")


if __name__ == "__main__":
    asyncio.run(run_full_diagnostic())
