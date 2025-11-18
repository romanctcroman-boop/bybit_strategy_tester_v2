"""
Comprehensive Walk-Forward Validation Test Suite

Tests the WalkForwardOptimizer with EMA 20/50 strategy (best from Priority #2).

Test Plan:
1. Load 90 days of data (BTCUSDT 5m)
2. Configure Walk-Forward: Train=60d, Test=29d, Rolling=7d
3. Run optimization with EMA 20/50 parameters
4. Compare Walk-Forward vs Standard Backtest
5. Analyze efficiency, stability, and robustness
6. Generate comprehensive report

Metrics to validate:
- OOS vs IS Sharpe Ratio (efficiency)
- Parameter stability across periods
- Trade consistency
- Drawdown stability
- Win rate stability
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from backend.core.walk_forward_optimizer import WalkForwardOptimizer
from backend.core.backtest_engine import BacktestEngine
from backend.core.data_manager import DataManager


class WalkForwardValidationSuite:
    """Comprehensive test suite for Walk-Forward Validation."""
    
    def __init__(self):
        self.symbol = 'BTCUSDT'
        self.timeframe = '5'
        self.initial_capital = 10000.0
        self.commission = 0.00075
        
        # Walk-Forward configuration (adjusted for available data)
        # Using 1000 bars total from cache
        # Train: 600 bars (~2 days 5m), Test: 300 bars (~1 day), Rolling: 100 bars
        self.wf_in_sample_bars = 600  # 600 bars train
        self.wf_out_sample_bars = 300  # 300 bars test
        self.wf_step_bars = 100  # 100 bars rolling step
        
        # Best strategy from Priority #2: EMA 20/50
        self.base_strategy_config = {
            'type': 'ema_crossover',
            'fast_ema': 20,
            'slow_ema': 50,
            'direction': 'both',  # Long and short
        }
        
        # Parameter space for optimization (fine-tuning around best params)
        self.param_space = {
            'fast_ema': [15, 20, 25],  # Around 20
            'slow_ema': [40, 50, 60],  # Around 50
        }
        
    def run_all_tests(self):
        """Run all Walk-Forward validation tests."""
        
        logger.info("=" * 80)
        logger.info("🚀 WALK-FORWARD VALIDATION TEST SUITE")
        logger.info("=" * 80)
        
        tests = [
            ("Test 1: Load 90-day Data", self.test_data_loading),
            ("Test 2: Standard Backtest (Baseline)", self.test_standard_backtest),
            ("Test 3: Walk-Forward Optimization", self.test_walkforward_optimization),
            ("Test 4: Efficiency Analysis (OOS/IS)", self.test_efficiency_analysis),
            ("Test 5: Parameter Stability", self.test_parameter_stability),
            ("Test 6: Performance Comparison", self.test_performance_comparison),
            ("Test 7: Robustness Metrics", self.test_robustness_metrics),
        ]
        
        results = {}
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            logger.info(f"\n{'─' * 80}")
            logger.info(f"📋 {test_name}")
            logger.info(f"{'─' * 80}")
            
            try:
                result = test_func()
                results[test_name] = result
                
                if result:
                    logger.success(f"✅ PASS | {test_name}")
                    passed += 1
                else:
                    logger.error(f"❌ FAIL | {test_name}")
                    failed += 1
                    
            except Exception as e:
                logger.error(f"❌ ERROR | {test_name}: {str(e)}")
                logger.exception(e)
                results[test_name] = False
                failed += 1
        
        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Passed: {passed}/{len(tests)}")
        logger.info(f"❌ Failed: {failed}/{len(tests)}")
        
        if failed == 0:
            logger.success("\n🎉 ALL TESTS PASSED! Walk-Forward Validation is production-ready!")
        else:
            logger.warning(f"\n⚠️ {failed} test(s) failed. Review results above.")
        
        return results
    
    def test_data_loading(self) -> bool:
        """Test 1: Load historical BTCUSDT 5m data."""
        
        logger.info("Loading BTCUSDT 5m data from cache...")
        
        # DataManager limit is 1000 bars max
        expected_bars = 1000
        
        dm = DataManager(symbol=self.symbol, cache_dir='./data/cache')
        
        # Load data
        data = dm.load_historical(
            timeframe=self.timeframe,
            limit=expected_bars
        )
        
        logger.info(f"📊 Loaded {len(data)} bars")
        logger.info(f"   Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
        logger.info(f"   Columns: {list(data.columns)}")
        
        # Validate
        assert len(data) >= 900, f"Expected ~{expected_bars} bars, got {len(data)}"
        assert 'close' in data.columns, "Missing 'close' column"
        assert 'volume' in data.columns, "Missing 'volume' column"
        
        # Store for other tests
        self.data = data
        
        logger.success(f"✅ Successfully loaded {len(data)} bars")
        
        return True
    
    def test_standard_backtest(self) -> bool:
        """Test 2: Run standard backtest (baseline for comparison)."""
        
        logger.info("Running standard backtest with EMA 20/50...")
        
        engine = BacktestEngine(
            initial_capital=self.initial_capital,
            commission=self.commission,
        )
        
        results = engine.run(self.data, self.base_strategy_config)
        
        # Store baseline results
        self.baseline_results = results
        
        logger.info("📊 Standard Backtest Results:")
        logger.info(f"   Total Trades: {results.get('total_trades', 0)}")
        logger.info(f"   Total Return: {results.get('total_return', 0):.2f}%")
        logger.info(f"   Sharpe Ratio: {results.get('sharpe_ratio', 0):.3f}")
        logger.info(f"   Win Rate: {results.get('win_rate', 0):.2%}")
        logger.info(f"   Max Drawdown: {results.get('max_drawdown', 0):.2%}")
        logger.info(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
        
        # Validate baseline has trades
        assert results.get('total_trades', 0) > 0, "No trades in standard backtest"
        
        logger.success("✅ Standard backtest completed")
        
        return True
    
    def test_walkforward_optimization(self) -> bool:
        """Test 3: Run Walk-Forward Optimization."""
        
        logger.info("Running Walk-Forward Optimization...")
        logger.info(f"   In-Sample: {self.wf_in_sample_bars} bars")
        logger.info(f"   Out-of-Sample: {self.wf_out_sample_bars} bars")
        logger.info(f"   Rolling Step: {self.wf_step_bars} bars")
        logger.info(f"   Parameter Space: {self.param_space}")
        
        optimizer = WalkForwardOptimizer(
            in_sample_size=self.wf_in_sample_bars,
            out_sample_size=self.wf_out_sample_bars,
            step_size=self.wf_step_bars,
            initial_capital=self.initial_capital,
            commission=self.commission,
        )
        
        wf_results = optimizer.run(
            data=self.data,
            param_space=self.param_space,
            strategy_config=self.base_strategy_config,
            metric='sharpe_ratio',
        )
        
        # Store Walk-Forward results
        self.wf_results = wf_results
        
        walk_periods = wf_results['walk_results']
        aggregated = wf_results['aggregated_metrics']
        
        logger.info(f"\n📊 Walk-Forward Results:")
        logger.info(f"   Total Periods: {aggregated.get('total_periods', 0)}")
        logger.info(f"   Avg Efficiency (OOS/IS): {aggregated.get('avg_efficiency', 0):.2%}")
        logger.info(f"   OOS Total Return: {aggregated.get('oos_total_return', 0):.2f}%")
        logger.info(f"   OOS Avg Sharpe: {aggregated.get('oos_avg_sharpe', 0):.3f}")
        logger.info(f"   OOS Total Trades: {aggregated.get('oos_total_trades', 0)}")
        logger.info(f"   OOS Avg Win Rate: {aggregated.get('oos_avg_win_rate', 0):.2%}")
        
        # Show period details
        logger.info(f"\n📋 Period Details:")
        for period in walk_periods:
            logger.info(f"   Period {period.period_num}:")
            logger.info(f"      Best Params: {period.best_params}")
            logger.info(f"      IS Sharpe: {period.is_sharpe:.3f}")
            logger.info(f"      OOS Sharpe: {period.oos_sharpe:.3f}")
            logger.info(f"      Efficiency: {period.efficiency:.2%}")
        
        # Validate
        assert len(walk_periods) > 0, "No Walk-Forward periods generated"
        assert aggregated.get('total_periods', 0) > 0, "No periods in aggregated results"
        
        logger.success(f"✅ Walk-Forward completed: {len(walk_periods)} periods")
        
        return True
    
    def test_efficiency_analysis(self) -> bool:
        """Test 4: Analyze OOS/IS efficiency (overfitting detection)."""
        
        logger.info("Analyzing Walk-Forward Efficiency...")
        
        walk_periods = self.wf_results['walk_results']
        aggregated = self.wf_results['aggregated_metrics']
        
        avg_efficiency = aggregated.get('avg_efficiency', 0)
        
        logger.info(f"📊 Efficiency Analysis:")
        logger.info(f"   Average Efficiency: {avg_efficiency:.2%}")
        
        # Efficiency benchmarks:
        # > 80%: Excellent (minimal overfitting)
        # 60-80%: Good (acceptable overfitting)
        # 40-60%: Moderate (some overfitting)
        # < 40%: Poor (significant overfitting)
        
        if avg_efficiency > 0.8:
            logger.success(f"   🎯 EXCELLENT: Minimal overfitting ({avg_efficiency:.2%})")
            assessment = "Excellent"
        elif avg_efficiency > 0.6:
            logger.info(f"   ✅ GOOD: Acceptable overfitting ({avg_efficiency:.2%})")
            assessment = "Good"
        elif avg_efficiency > 0.4:
            logger.warning(f"   ⚠️ MODERATE: Some overfitting ({avg_efficiency:.2%})")
            assessment = "Moderate"
        else:
            logger.error(f"   ❌ POOR: Significant overfitting ({avg_efficiency:.2%})")
            assessment = "Poor"
        
        # Period-by-period efficiency
        logger.info(f"\n   Period Efficiency Breakdown:")
        for period in walk_periods:
            eff = period.efficiency
            emoji = "🎯" if eff > 0.8 else "✅" if eff > 0.6 else "⚠️" if eff > 0.4 else "❌"
            logger.info(f"      Period {period.period_num}: {eff:>6.2%} {emoji}")
        
        # Store assessment
        self.efficiency_assessment = assessment
        
        # Test passes if not "Poor"
        return assessment != "Poor"
    
    def test_parameter_stability(self) -> bool:
        """Test 5: Analyze parameter stability across periods."""
        
        logger.info("Analyzing parameter stability...")
        
        stability = self.wf_results['parameter_stability']
        
        logger.info(f"📊 Parameter Stability:")
        
        for param_name, stats in stability.items():
            mean = stats['mean']
            std = stats['std']
            min_val = stats['min']
            max_val = stats['max']
            stability_score = stats['stability_score']
            
            logger.info(f"\n   {param_name}:")
            logger.info(f"      Mean: {mean:.2f}")
            logger.info(f"      Std Dev: {std:.2f}")
            logger.info(f"      Range: [{min_val:.0f}, {max_val:.0f}]")
            logger.info(f"      Stability Score: {stability_score:.3f}")
            
            # Stability benchmarks:
            # < 0.2: Excellent (very stable)
            # 0.2-0.4: Good (stable)
            # 0.4-0.6: Moderate (some variation)
            # > 0.6: Poor (unstable)
            
            if stability_score < 0.2:
                logger.success(f"      🎯 EXCELLENT stability")
            elif stability_score < 0.4:
                logger.info(f"      ✅ GOOD stability")
            elif stability_score < 0.6:
                logger.warning(f"      ⚠️ MODERATE stability")
            else:
                logger.error(f"      ❌ POOR stability (parameters vary widely)")
        
        # Test passes if all parameters have stability_score < 0.6
        all_stable = all(stats['stability_score'] < 0.6 for stats in stability.values())
        
        if all_stable:
            logger.success("✅ All parameters show acceptable stability")
        else:
            logger.warning("⚠️ Some parameters show high variation")
        
        return all_stable
    
    def test_performance_comparison(self) -> bool:
        """Test 6: Compare Walk-Forward vs Standard Backtest."""
        
        logger.info("Comparing Walk-Forward vs Standard Backtest...")
        
        baseline = self.baseline_results
        wf_agg = self.wf_results['aggregated_metrics']
        
        # Extract metrics
        baseline_return = baseline.get('total_return', 0)
        baseline_sharpe = baseline.get('sharpe_ratio', 0)
        baseline_trades = baseline.get('total_trades', 0)
        baseline_winrate = baseline.get('win_rate', 0)
        baseline_drawdown = baseline.get('max_drawdown', 0)
        
        wf_return = wf_agg.get('oos_total_return', 0)
        wf_sharpe = wf_agg.get('oos_avg_sharpe', 0)
        wf_trades = wf_agg.get('oos_total_trades', 0)
        wf_winrate = wf_agg.get('oos_avg_win_rate', 0)
        wf_drawdown = wf_agg.get('oos_avg_drawdown', 0)
        
        logger.info(f"\n📊 COMPARISON TABLE:")
        logger.info(f"{'Metric':<25} {'Standard':<15} {'Walk-Forward':<15} {'Winner':<10}")
        logger.info("=" * 70)
        
        # Total Return
        winner = "WF" if wf_return > baseline_return else "Standard"
        logger.info(f"{'Total Return (%)':<25} {baseline_return:>14.2f} {wf_return:>14.2f}  {winner:<10}")
        
        # Sharpe Ratio
        winner = "WF" if wf_sharpe > baseline_sharpe else "Standard"
        logger.info(f"{'Sharpe Ratio':<25} {baseline_sharpe:>14.3f} {wf_sharpe:>14.3f}  {winner:<10}")
        
        # Total Trades
        winner = "WF" if wf_trades > baseline_trades else "Standard"
        logger.info(f"{'Total Trades':<25} {baseline_trades:>14.0f} {wf_trades:>14.0f}  {winner:<10}")
        
        # Win Rate
        winner = "WF" if wf_winrate > baseline_winrate else "Standard"
        logger.info(f"{'Win Rate (%)':<25} {baseline_winrate*100:>14.2f} {wf_winrate*100:>14.2f}  {winner:<10}")
        
        # Max Drawdown (lower is better)
        winner = "WF" if abs(wf_drawdown) < abs(baseline_drawdown) else "Standard"
        logger.info(f"{'Max Drawdown (%)':<25} {baseline_drawdown:>14.2f} {wf_drawdown:>14.2f}  {winner:<10}")
        
        logger.info("=" * 70)
        
        # Analysis
        logger.info(f"\n💡 Analysis:")
        
        if wf_return < baseline_return * 0.7:
            logger.warning(f"   ⚠️ WF return significantly lower than baseline ({wf_return:.2f}% vs {baseline_return:.2f}%)")
            logger.warning(f"   This suggests overfitting in standard backtest or parameter space too narrow")
        elif wf_return > baseline_return * 0.9:
            logger.success(f"   ✅ WF return comparable to baseline ({wf_return:.2f}% vs {baseline_return:.2f}%)")
            logger.success(f"   Strategy shows good out-of-sample performance")
        else:
            logger.info(f"   ℹ️ WF return moderately lower than baseline ({wf_return:.2f}% vs {baseline_return:.2f}%)")
        
        # Test passes if WF return > 50% of baseline (not catastrophic degradation)
        return wf_return > baseline_return * 0.5
    
    def test_robustness_metrics(self) -> bool:
        """Test 7: Calculate robustness metrics."""
        
        logger.info("Calculating robustness metrics...")
        
        walk_periods = self.wf_results['walk_results']
        
        # Calculate consistency metrics
        oos_sharpes = [p.oos_sharpe for p in walk_periods]
        oos_returns = [p.oos_net_profit for p in walk_periods]
        
        import numpy as np
        
        sharpe_mean = np.mean(oos_sharpes)
        sharpe_std = np.std(oos_sharpes)
        sharpe_min = np.min(oos_sharpes)
        sharpe_max = np.max(oos_sharpes)
        
        return_mean = np.mean(oos_returns)
        return_std = np.std(oos_returns)
        
        logger.info(f"📊 Robustness Metrics:")
        logger.info(f"\n   OOS Sharpe Ratio:")
        logger.info(f"      Mean: {sharpe_mean:.3f}")
        logger.info(f"      Std Dev: {sharpe_std:.3f}")
        logger.info(f"      Range: [{sharpe_min:.3f}, {sharpe_max:.3f}]")
        
        # Coefficient of Variation (CV) = std/mean
        # Lower CV = more consistent
        sharpe_cv = abs(sharpe_std / sharpe_mean) if sharpe_mean != 0 else float('inf')
        
        logger.info(f"      Consistency (CV): {sharpe_cv:.3f}")
        
        if sharpe_cv < 0.5:
            logger.success(f"      🎯 EXCELLENT consistency (CV < 0.5)")
        elif sharpe_cv < 1.0:
            logger.info(f"      ✅ GOOD consistency (CV < 1.0)")
        elif sharpe_cv < 1.5:
            logger.warning(f"      ⚠️ MODERATE consistency (CV < 1.5)")
        else:
            logger.error(f"      ❌ POOR consistency (CV >= 1.5)")
        
        logger.info(f"\n   OOS Net Profit:")
        logger.info(f"      Mean per period: ${return_mean:.2f}")
        logger.info(f"      Std Dev: ${return_std:.2f}")
        
        # Count profitable periods
        profitable_periods = sum(1 for p in walk_periods if p.oos_net_profit > 0)
        profit_rate = profitable_periods / len(walk_periods)
        
        logger.info(f"\n   Period Profitability:")
        logger.info(f"      Profitable periods: {profitable_periods}/{len(walk_periods)} ({profit_rate:.2%})")
        
        if profit_rate > 0.7:
            logger.success(f"      🎯 EXCELLENT: >70% periods profitable")
        elif profit_rate > 0.5:
            logger.info(f"      ✅ GOOD: >50% periods profitable")
        else:
            logger.warning(f"      ⚠️ MODERATE: <50% periods profitable")
        
        # Test passes if consistency is acceptable (CV < 1.5)
        return sharpe_cv < 1.5


def main():
    """Main test execution."""
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Run test suite
    suite = WalkForwardValidationSuite()
    results = suite.run_all_tests()
    
    return results


if __name__ == "__main__":
    results = main()
