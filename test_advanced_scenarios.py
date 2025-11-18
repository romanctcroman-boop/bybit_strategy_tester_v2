"""
ADVANCED TEST SCENARIOS: Copilot ↔ Perplexity AI ↔ ML-Optimization
====================================================================

Расширенные варианты тестов для различных сценариев использования
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import json

from mcp_bridge import MCPPerplexityBridge
from test_copilot_perplexity_ml_comprehensive import (
    load_test_data, 
    simple_backtest
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


# ==================== SCENARIO 1: Strategy Discovery ====================

async def scenario_strategy_discovery():
    """
    Scenario: User wants to discover new trading strategies
    
    Flow:
    1. Ask Perplexity for trending strategies 2025
    2. Get code implementation
    3. Quick backtest
    4. Ask for improvement suggestions
    """
    print("\n" + "="*80)
    print("🔍 SCENARIO 1: Strategy Discovery")
    print("="*80 + "\n")
    
    bridge = MCPPerplexityBridge()
    
    # Step 1: Discovery
    print("Step 1: Discovering trending strategies...")
    response1 = await bridge.query("""
What are the most effective crypto trading strategies in 2025?
Focus on quantitative, algorithmic strategies that work well with BTC/USDT.
Include pros, cons, and typical performance metrics.
""")
    
    print(f"✅ Discovered {len(response1['content'])} chars of insights\n")
    
    # Step 2: Get implementation
    print("Step 2: Getting implementation for best strategy...")
    response2 = await bridge.query("""
Generate Python code for a VWAP (Volume Weighted Average Price) mean reversion strategy:
- Entry: Price deviates from VWAP by threshold
- Exit: Price returns to VWAP
- Include stop loss and take profit
- Provide parameter ranges for optimization
""")
    
    print(f"✅ Implementation received ({len(response2['content'])} chars)\n")
    
    # Step 3: Ask for optimization guidance
    print("Step 3: Getting optimization guidance...")
    response3 = await bridge.query("""
For VWAP mean reversion strategy on 15-minute BTC/USDT:
1. What parameters should I optimize?
2. What are safe ranges to avoid overfitting?
3. Which ML algorithm is best for this strategy type?
4. What metrics should I prioritize?
""")
    
    print(f"✅ Optimization guidance received\n")
    print("📊 Recommendations:")
    print(response3['content'][:500] + "...\n")
    
    return {
        'discovery': response1['content'][:200],
        'implementation': response2['content'][:200],
        'optimization': response3['content'][:200]
    }


# ==================== SCENARIO 2: Parameter Sensitivity Analysis ====================

async def scenario_parameter_sensitivity():
    """
    Scenario: Analyze parameter sensitivity with Perplexity guidance
    
    Flow:
    1. Run baseline optimization
    2. Ask Perplexity which parameters are most critical
    3. Test sensitivity of each parameter
    4. Get recommendations for robust ranges
    """
    print("\n" + "="*80)
    print("📊 SCENARIO 2: Parameter Sensitivity Analysis")
    print("="*80 + "\n")
    
    bridge = MCPPerplexityBridge()
    data = await load_test_data(1000)
    
    # Step 1: Baseline
    print("Step 1: Running baseline optimization...")
    
    from backend.ml.optimizer import LightGBMOptimizer
    
    param_space = {
        'fast': [5, 10, 15, 20],
        'slow': [20, 30, 40, 50],
        'take_profit': [0.015, 0.02, 0.03],
        'stop_loss': [0.008, 0.01, 0.015]
    }
    
    def objective(params):
        result = simple_backtest(data, params)
        return result['sharpe_ratio'] * (0.5 if result['total_trades'] < 10 else 1.0)
    
    optimizer = LightGBMOptimizer(objective, param_space, n_jobs=-1, verbose=0)
    result = await optimizer.optimize(n_trials=20)
    
    baseline_params = result.best_params
    baseline_sharpe = result.best_score
    
    print(f"✅ Baseline Sharpe: {baseline_sharpe:.2f}")
    print(f"   Baseline params: {baseline_params}\n")
    
    # Step 2: Ask Perplexity about sensitivity
    print("Step 2: Consulting Perplexity about parameter importance...")
    
    response = await bridge.query(f"""
For EMA crossover strategy, I found these optimal parameters:
{json.dumps(baseline_params, indent=2)}

Questions:
1. Which parameter is most sensitive to changes?
2. What are safe ranges for each parameter to avoid overfitting?
3. Should I fix any parameters or keep them flexible?
4. How to test parameter stability?
""")
    
    print(f"✅ Expert guidance received\n")
    print("📊 Key insights:")
    print(response['content'][:400] + "...\n")
    
    # Step 3: Sensitivity testing
    print("Step 3: Testing parameter sensitivity...")
    
    sensitivity_results = {}
    
    for param_name, baseline_value in baseline_params.items():
        print(f"   Testing {param_name}...")
        
        # Test ±20% variation
        test_values = [
            baseline_value * 0.8,
            baseline_value,
            baseline_value * 1.2
        ]
        
        scores = []
        for val in test_values:
            test_params = baseline_params.copy()
            test_params[param_name] = val
            
            result = simple_backtest(data, test_params)
            scores.append(result['sharpe_ratio'])
        
        # Calculate sensitivity (std of scores)
        sensitivity = np.std(scores)
        sensitivity_results[param_name] = {
            'sensitivity': sensitivity,
            'baseline_score': scores[1],
            'variation_range': (min(scores), max(scores))
        }
    
    print("\n📈 Sensitivity Results:")
    for param, stats in sorted(sensitivity_results.items(), key=lambda x: x[1]['sensitivity'], reverse=True):
        print(f"   {param}: Sensitivity={stats['sensitivity']:.4f}, Range={stats['variation_range']}")
    
    return {
        'baseline': baseline_params,
        'sensitivity': sensitivity_results,
        'guidance': response['content'][:200]
    }


# ==================== SCENARIO 3: Market Regime Detection ====================

async def scenario_market_regime():
    """
    Scenario: Optimize strategy for different market conditions
    
    Flow:
    1. Ask Perplexity about market regimes
    2. Detect regimes in historical data
    3. Optimize for each regime separately
    4. Compare performance across regimes
    """
    print("\n" + "="*80)
    print("🌐 SCENARIO 3: Market Regime Optimization")
    print("="*80 + "\n")
    
    bridge = MCPPerplexityBridge()
    data = await load_test_data(2000)
    
    # Step 1: Learn about regimes
    print("Step 1: Learning about market regimes...")
    
    response1 = await bridge.query("""
What are the main market regimes for crypto trading?
For each regime, suggest:
1. How to detect it
2. Which strategy works best
3. Parameter adjustments needed
""")
    
    print(f"✅ Market regime guide received\n")
    
    # Step 2: Simple regime detection (ADX-based)
    print("Step 2: Detecting market regimes in data...")
    
    # Calculate ADX (simplified)
    data['tr'] = data[['high', 'low', 'close']].apply(
        lambda x: max(x['high'] - x['low'], abs(x['high'] - x['close']), abs(x['low'] - x['close'])),
        axis=1
    )
    data['atr'] = data['tr'].rolling(14).mean()
    
    # Classify regimes
    # Trending: High volatility
    # Ranging: Low volatility
    volatility_threshold = data['atr'].quantile(0.5)
    
    trending_data = data[data['atr'] > volatility_threshold].copy()
    ranging_data = data[data['atr'] <= volatility_threshold].copy()
    
    print(f"   Trending periods: {len(trending_data)} bars")
    print(f"   Ranging periods: {len(ranging_data)} bars\n")
    
    # Step 3: Optimize for each regime
    print("Step 3: Optimizing for each regime...")
    
    from backend.ml.optimizer import LightGBMOptimizer
    
    param_space = {
        'fast': [5, 10, 15],
        'slow': [20, 30, 40],
        'take_profit': [0.02, 0.03],
        'stop_loss': [0.01, 0.015]
    }
    
    # Optimize for trending
    print("   Optimizing for TRENDING regime...")
    def objective_trending(params):
        result = simple_backtest(trending_data, params)
        return result['sharpe_ratio'] * (0.5 if result['total_trades'] < 5 else 1.0)
    
    opt_trending = LightGBMOptimizer(objective_trending, param_space, n_jobs=-1, verbose=0)
    result_trending = await opt_trending.optimize(n_trials=15)
    
    print(f"   ✅ Trending optimal Sharpe: {result_trending.best_score:.2f}")
    
    # Optimize for ranging
    print("   Optimizing for RANGING regime...")
    def objective_ranging(params):
        result = simple_backtest(ranging_data, params)
        return result['sharpe_ratio'] * (0.5 if result['total_trades'] < 5 else 1.0)
    
    opt_ranging = LightGBMOptimizer(objective_ranging, param_space, n_jobs=-1, verbose=0)
    result_ranging = await opt_ranging.optimize(n_trials=15)
    
    print(f"   ✅ Ranging optimal Sharpe: {result_ranging.best_score:.2f}\n")
    
    # Step 4: Ask Perplexity for interpretation
    print("Step 4: Consulting Perplexity for regime-based strategy...")
    
    response2 = await bridge.query(f"""
I optimized EMA crossover for different market regimes:

TRENDING REGIME:
- Optimal params: {result_trending.best_params}
- Sharpe: {result_trending.best_score:.2f}

RANGING REGIME:
- Optimal params: {result_ranging.best_params}
- Sharpe: {result_ranging.best_score:.2f}

Questions:
1. Should I use different parameters for each regime?
2. How to implement regime-switching in live trading?
3. What are the risks of regime detection lag?
""")
    
    print("📊 Expert recommendations:")
    print(response2['content'][:400] + "...\n")
    
    return {
        'trending_params': result_trending.best_params,
        'ranging_params': result_ranging.best_params,
        'recommendations': response2['content'][:200]
    }


# ==================== SCENARIO 4: Feature Engineering Pipeline ====================

async def scenario_feature_engineering():
    """
    Scenario: Build advanced features with Perplexity guidance
    
    Flow:
    1. Ask for TOP-20 features
    2. Implement top features
    3. Test feature importance
    4. Get recommendations for feature combinations
    """
    print("\n" + "="*80)
    print("🔬 SCENARIO 4: Feature Engineering Pipeline")
    print("="*80 + "\n")
    
    bridge = MCPPerplexityBridge()
    data = await load_test_data(2000)
    
    # Step 1: Get feature recommendations
    print("Step 1: Getting feature engineering recommendations...")
    
    response1 = await bridge.query("""
What are the TOP-20 technical indicators and features for ML-based trading strategies?

For each feature, provide:
1. Calculation method
2. Typical parameters
3. Best use case (trending/ranging/both)
4. Expected importance score

Focus on features that work well with tree-based ML models (XGBoost, LightGBM).
""")
    
    print(f"✅ Feature recommendations received\n")
    print("📊 Top features:")
    print(response1['content'][:500] + "...\n")
    
    # Step 2: Implement key features
    print("Step 2: Implementing key technical features...")
    
    # EMA features
    for period in [9, 21, 50, 200]:
        data[f'ema_{period}'] = data['close'].ewm(span=period, adjust=False).mean()
    
    # RSI
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    data['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR
    data['tr'] = data[['high', 'low', 'close']].apply(
        lambda x: max(x['high'] - x['low'], abs(x['high'] - x['close']), abs(x['low'] - x['close'])),
        axis=1
    )
    data['atr'] = data['tr'].rolling(14).mean()
    
    # Volume features
    data['volume_ma'] = data['volume'].rolling(20).mean()
    data['volume_ratio'] = data['volume'] / data['volume_ma']
    
    # Price distance from EMAs
    data['dist_ema_21'] = (data['close'] - data['ema_21']) / data['ema_21']
    data['dist_ema_50'] = (data['close'] - data['ema_50']) / data['ema_50']
    
    print(f"✅ Implemented {len([c for c in data.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']])} features\n")
    
    # Step 3: Test with LightGBM feature importance
    print("Step 3: Testing feature importance with LightGBM...")
    
    # Prepare features
    feature_cols = ['ema_9', 'ema_21', 'ema_50', 'ema_200', 'rsi', 'atr', 
                    'volume_ratio', 'dist_ema_21', 'dist_ema_50']
    
    X = data[feature_cols].fillna(0).values
    
    # Create simple target (next period return > 0)
    y = (data['close'].shift(-1) > data['close']).astype(int).fillna(0).values
    
    # Train LightGBM
    import lightgbm as lgb
    
    train_data = lgb.Dataset(X[:1500], label=y[:1500])
    
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'num_leaves': 31,
        'verbose': -1
    }
    
    model = lgb.train(params, train_data, num_boost_round=100)
    
    # Feature importance
    importance = model.feature_importance()
    feature_importance = dict(zip(feature_cols, importance))
    
    print("📈 Feature Importance:")
    for feat, imp in sorted(feature_importance.items(), key=lambda x: x[1], reverse=True):
        print(f"   {feat}: {imp:.0f}")
    
    print()
    
    # Step 4: Get recommendations
    print("Step 4: Getting recommendations for feature combinations...")
    
    response2 = await bridge.query(f"""
Based on feature importance analysis:
{json.dumps(feature_importance, indent=2)}

Questions:
1. Which features should I combine?
2. Are there any redundant features to remove?
3. What additional features would complement these?
4. How to handle feature correlation?
""")
    
    print("✅ Feature engineering recommendations:")
    print(response2['content'][:400] + "...\n")
    
    return {
        'features_implemented': feature_cols,
        'feature_importance': feature_importance,
        'recommendations': response2['content'][:200]
    }


# ==================== SCENARIO 5: Walk-Forward Optimization ====================

async def scenario_walkforward():
    """
    Scenario: Implement walk-forward optimization with Perplexity guidance
    
    Flow:
    1. Ask about walk-forward best practices
    2. Implement walk-forward windows
    3. Track parameter stability
    4. Get recommendations for deployment
    """
    print("\n" + "="*80)
    print("📅 SCENARIO 5: Walk-Forward Optimization")
    print("="*80 + "\n")
    
    bridge = MCPPerplexityBridge()
    data = await load_test_data(2000)
    
    # Step 1: Learn best practices
    print("Step 1: Learning walk-forward best practices...")
    
    response1 = await bridge.query("""
Explain walk-forward optimization for crypto trading strategies:
1. Optimal training/testing window sizes
2. How to detect parameter drift
3. When to re-optimize
4. Red flags for overfitting
5. Metrics to track over time
""")
    
    print(f"✅ Walk-forward guide received\n")
    print("📊 Key points:")
    print(response1['content'][:400] + "...\n")
    
    # Step 2: Implement walk-forward
    print("Step 2: Running walk-forward optimization...")
    
    from backend.ml.optimizer import LightGBMOptimizer
    
    window_size = 500  # Training window
    test_size = 200    # Testing window
    step_size = 100    # Step forward
    
    param_space = {
        'fast': [5, 10, 15],
        'slow': [20, 30, 40],
        'take_profit': [0.02, 0.03],
        'stop_loss': [0.01, 0.015]
    }
    
    walkforward_results = []
    
    for i in range(0, len(data) - window_size - test_size, step_size):
        window_num = i // step_size + 1
        
        # Training data
        train_data = data.iloc[i:i+window_size]
        
        # Test data
        test_data = data.iloc[i+window_size:i+window_size+test_size]
        
        print(f"   Window {window_num}: Training on {len(train_data)} bars, testing on {len(test_data)} bars")
        
        # Optimize on training
        def objective(params):
            result = simple_backtest(train_data, params)
            return result['sharpe_ratio'] * (0.5 if result['total_trades'] < 5 else 1.0)
        
        optimizer = LightGBMOptimizer(objective, param_space, n_jobs=-1, verbose=0)
        result = await optimizer.optimize(n_trials=10)
        
        # Test on out-of-sample
        test_result = simple_backtest(test_data, result.best_params)
        
        walkforward_results.append({
            'window': window_num,
            'train_sharpe': result.best_score,
            'test_sharpe': test_result['sharpe_ratio'],
            'params': result.best_params,
            'test_return': test_result['total_return'],
            'test_trades': test_result['total_trades']
        })
        
        if len(walkforward_results) >= 3:  # Limit to 3 windows for demo
            break
    
    print()
    
    # Step 3: Analyze results
    print("Step 3: Analyzing walk-forward results...")
    
    print("\n📊 Walk-Forward Results:")
    for r in walkforward_results:
        print(f"\n   Window {r['window']}:")
        print(f"      Training Sharpe: {r['train_sharpe']:.2f}")
        print(f"      Testing Sharpe:  {r['test_sharpe']:.2f}")
        print(f"      Test Return:     {r['test_return']*100:.2f}%")
        print(f"      Trades:          {r['test_trades']}")
        print(f"      Params:          {r['params']}")
    
    # Calculate parameter stability
    param_names = walkforward_results[0]['params'].keys()
    param_stability = {}
    
    for param in param_names:
        values = [r['params'][param] for r in walkforward_results]
        param_stability[param] = {
            'mean': np.mean(values),
            'std': np.std(values),
            'range': (min(values), max(values))
        }
    
    print("\n📈 Parameter Stability:")
    for param, stats in param_stability.items():
        print(f"   {param}: μ={stats['mean']:.2f}, σ={stats['std']:.2f}, range={stats['range']}")
    
    # Step 4: Get deployment recommendations
    print("\nStep 4: Getting deployment recommendations...")
    
    response2 = await bridge.query(f"""
Walk-forward optimization results:

{json.dumps([{
    'window': r['window'],
    'train_sharpe': f"{r['train_sharpe']:.2f}",
    'test_sharpe': f"{r['test_sharpe']:.2f}",
    'params': r['params']
} for r in walkforward_results], indent=2)}

Parameter stability:
{json.dumps({k: f"σ={v['std']:.2f}" for k, v in param_stability.items()}, indent=2)}

Questions:
1. Is this strategy robust enough for live trading?
2. Are parameters stable or drifting?
3. What's the expected degradation in live performance?
4. How often should I re-optimize?
""")
    
    print("\n✅ Deployment recommendations:")
    print(response2['content'][:500] + "...\n")
    
    return {
        'walkforward_results': walkforward_results,
        'param_stability': param_stability,
        'recommendations': response2['content'][:200]
    }


# ==================== MAIN RUNNER ====================

async def run_advanced_scenarios():
    """Run all advanced test scenarios"""
    
    print("\n" + "="*80)
    print("🚀 ADVANCED TEST SCENARIOS")
    print("   Copilot ↔ Perplexity AI ↔ ML-Optimization")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    scenarios = [
        ("Strategy Discovery", scenario_strategy_discovery),
        ("Parameter Sensitivity", scenario_parameter_sensitivity),
        ("Market Regime Detection", scenario_market_regime),
        ("Feature Engineering", scenario_feature_engineering),
        ("Walk-Forward Optimization", scenario_walkforward)
    ]
    
    results = {}
    
    for name, scenario_func in scenarios:
        try:
            print(f"\n{'='*80}")
            print(f"▶️  Running: {name}")
            print(f"{'='*80}")
            
            result = await scenario_func()
            results[name] = {'status': 'success', 'data': result}
            
            print(f"\n✅ {name} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ {name} failed: {e}")
            results[name] = {'status': 'failed', 'error': str(e)}
    
    # Summary
    print("\n" + "="*80)
    print("📊 ADVANCED SCENARIOS SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results.values() if r['status'] == 'success')
    total = len(results)
    
    print(f"\n✅ Scenarios passed: {passed}/{total}")
    print(f"   Success rate: {passed/total*100:.1f}%")
    
    # Save results
    results_file = Path('logs/advanced_scenarios_results.json')
    results_file.parent.mkdir(exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'scenarios': {k: {'status': v['status']} for k, v in results.items()},
            'summary': {
                'passed': passed,
                'total': total,
                'success_rate': passed/total
            }
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {results_file}")
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == '__main__':
    asyncio.run(run_advanced_scenarios())
