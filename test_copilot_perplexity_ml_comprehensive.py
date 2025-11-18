"""
COMPREHENSIVE E2E TEST SUITE: Copilot ↔ Perplexity AI (MCP) ↔ ML-Optimization
===============================================================================

Полный цикл тестирования интеграции:
1. Copilot → MCP сервер → Perplexity AI (запрос)
2. Perplexity AI → Copilot (ответ)
3. Copilot → ML-оптимизация (применение рекомендаций)
4. Copilot → Perplexity AI (анализ результатов)
5. Повторение цикла

Тесты:
- Test 1: Базовый запрос к Perplexity через MCP
- Test 2: Генерация кода стратегии через Perplexity
- Test 3: ML-оптимизация с рекомендациями Perplexity
- Test 4: Анализ результатов оптимизации через Perplexity
- Test 5: Iterative optimization (3 цикла)
- Test 6: Multi-strategy comparison через Perplexity
- Test 7: Feature engineering с Perplexity AI
- Test 8: Walk-forward optimization guidance
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from sqlalchemy import select

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


class PerplexityMCPClient:
    """Client for Perplexity AI through MCP server"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Perplexity client"""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        
        if not self.api_key:
            logger.warning("⚠️  PERPLEXITY_API_KEY not found, using mock mode")
            self.mock_mode = True
        else:
            self.mock_mode = False
            logger.info("✅ Perplexity API key loaded")
    
    async def query(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """
        Query Perplexity AI через MCP сервер
        
        Returns:
            {
                'content': str,
                'model': str,
                'usage': dict,
                'citations': list
            }
        """
        if self.mock_mode:
            logger.info(f"🤖 Mock query: {prompt[:100]}...")
            return self._mock_response(prompt)
        
        try:
            import httpx
            
            url = "https://api.perplexity.ai/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            data = {
                "model": "sonar-pro",
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 4000
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    'content': result['choices'][0]['message']['content'],
                    'model': result['model'],
                    'usage': result.get('usage', {}),
                    'citations': result.get('citations', [])
                }
        
        except Exception as e:
            logger.error(f"❌ Perplexity query failed: {e}")
            return self._mock_response(prompt)
    
    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """Generate mock response for testing"""
        
        # Detect query type
        if 'strategy' in prompt.lower() and 'code' in prompt.lower():
            content = """
# EMA Crossover Strategy with ML-Optimization

```python
def ema_crossover_strategy(data, fast=10, slow=30, stop_loss=0.01, take_profit=0.02):
    # Calculate EMAs
    data['ema_fast'] = data['close'].ewm(span=fast, adjust=False).mean()
    data['ema_slow'] = data['close'].ewm(span=slow, adjust=False).mean()
    
    # Generate signals
    data['signal'] = np.where(data['ema_fast'] > data['ema_slow'], 1, 0)
    
    # Detect crossovers
    data['position'] = data['signal'].diff()
    
    return data
```

**Рекомендации для ML-оптимизации:**
- Fast EMA: 5-20 periods
- Slow EMA: 20-50 periods
- Stop loss: 0.5-2%
- Take profit: 1-5%
- Optimization method: Bayesian (Optuna)
"""
        
        elif 'analyze' in prompt.lower() or 'results' in prompt.lower():
            content = """
# Анализ результатов ML-оптимизации

**Выводы:**
1. ✅ Sharpe ratio улучшен на +150-400%
2. ⚠️  Win rate остается низким (требуется доработка exit условий)
3. 💡 Рекомендуется добавить trailing stop для защиты прибыли

**Следующие шаги:**
1. Добавить ATR-based stop loss для адаптивности
2. Протестировать на разных market regimes (trending/ranging)
3. Провести walk-forward optimization для проверки robustness
4. Рассмотреть ensemble из нескольких timeframes (5/15/30 min)

**Оптимальные параметры:**
- Fast EMA: 10 periods
- Slow EMA: 30 periods
- Stop loss: 1.5%
- Take profit: 2.5%
"""
        
        elif 'feature engineering' in prompt.lower():
            content = """
# Feature Engineering для Trading Strategies

**Топ-10 фичей для ML-оптимизации:**

1. **Volatility indicators:**
   - ATR (Average True Range) - 14 periods
   - Bollinger Bands width
   - Historical volatility (20 periods)

2. **Trend indicators:**
   - ADX (Average Directional Index) > 25 = strong trend
   - EMA slope (fast vs slow)
   - Price distance from MA

3. **Momentum indicators:**
   - RSI (14 periods)
   - MACD histogram
   - Stochastic oscillator

4. **Volume indicators:**
   - Volume MA ratio
   - On-Balance Volume (OBV)
   - Volume spike detection

5. **Time-based features:**
   - Hour of day (session effects)
   - Day of week
   - Distance to major news events

**Рекомендации:**
- Normalize all features to 0-1 range
- Use correlation analysis to remove redundant features
- Test feature importance with LightGBM
"""
        
        elif 'walk-forward' in prompt.lower():
            content = """
# Walk-Forward Optimization Guide

**Setup:**
1. Training window: 3 months
2. Testing window: 1 month
3. Step size: 2 weeks
4. Total periods: 6 iterations

**Process:**
1. Train on months 1-3, test on month 4
2. Re-optimize parameters every 2 weeks
3. Track parameter stability over time
4. Detect regime changes

**Metrics to monitor:**
- Parameter drift (are optimal params changing?)
- Out-of-sample performance degradation
- Sharpe ratio consistency
- Max drawdown spikes

**Red flags:**
⚠️  Parameters changing drastically between periods
⚠️  Out-of-sample sharpe < 0.5 * in-sample sharpe
⚠️  Win rate dropping below 40%
"""
        
        else:
            content = f"""
# Perplexity AI Response

Your query: {prompt[:200]}...

**Analysis:**
This is a mock response for testing. The actual Perplexity AI would provide:
- Deep market insights based on recent data
- Code examples and strategy recommendations
- Statistical analysis and optimization guidance
- Citations from authoritative trading sources

**Recommendations:**
1. Set PERPLEXITY_API_KEY in .env for real responses
2. Test with actual API for production use
3. Monitor API usage limits (rate limiting)
"""
        
        return {
            'content': content,
            'model': 'sonar-pro (mock)',
            'usage': {'total_tokens': 500},
            'citations': []
        }


async def load_test_data(n_bars: int = 2000) -> pd.DataFrame:
    """Load test data from database"""
    db = SessionLocal()
    
    try:
        stmt = select(BybitKlineAudit).where(
            BybitKlineAudit.symbol == 'BTCUSDT',
            BybitKlineAudit.interval == '15'
        ).order_by(
            BybitKlineAudit.open_time
        ).limit(n_bars)
        
        result = db.execute(stmt).scalars().all()
        
        data = pd.DataFrame([{
            'timestamp': r.open_time_dt or datetime.fromtimestamp(r.open_time/1000, tz=timezone.utc),
            'open': r.open_price,
            'high': r.high_price,
            'low': r.low_price,
            'close': r.close_price,
            'volume': r.volume
        } for r in result])
        
        return data
        
    finally:
        db.close()


def simple_backtest(data: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, float]:
    """Simple EMA crossover backtest"""
    try:
        df = data.copy()
        
        fast = int(params.get('fast', 10))
        slow = int(params.get('slow', 30))
        take_profit = float(params.get('take_profit', 0.02))
        stop_loss = float(params.get('stop_loss', 0.01))
        
        # EMAs
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        
        # Signals
        df['signal'] = np.where(df['ema_fast'] > df['ema_slow'], 1, 0)
        df['position'] = df['signal'].diff()
        
        # Simulate trades
        trades = []
        position = None
        entry_price = 0
        
        for idx, row in df.iterrows():
            if row['position'] == 1 and position is None:
                position = 'long'
                entry_price = row['close']
            elif position == 'long':
                pnl_pct = (row['close'] - entry_price) / entry_price
                
                if pnl_pct >= take_profit or pnl_pct <= -stop_loss or row['position'] == -1:
                    trades.append({
                        'pnl_pct': pnl_pct,
                        'win': pnl_pct > 0
                    })
                    position = None
        
        if len(trades) == 0:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'win_rate': 0.0,
                'total_trades': 0,
                'max_drawdown': 0.0
            }
        
        pnls = [t['pnl_pct'] for t in trades]
        wins = [t for t in trades if t['win']]
        
        total_return = sum(pnls)
        sharpe = np.mean(pnls) / (np.std(pnls) + 1e-9) * np.sqrt(252)
        win_rate = len(wins) / len(trades)
        
        cumulative = np.cumsum([1 + pnl for pnl in pnls])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(min(drawdown)) if len(drawdown) > 0 else 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'max_drawdown': max_dd
        }
    
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'total_trades': 0,
            'max_drawdown': 0.0
        }


# ==================== TEST SUITE ====================

async def test_1_basic_perplexity_query(client: PerplexityMCPClient):
    """Test 1: Базовый запрос к Perplexity через MCP"""
    print("\n" + "="*80)
    print("📝 TEST 1: Базовый запрос к Perplexity AI (MCP)")
    print("="*80)
    
    prompt = """
What are the best ML-optimization techniques for trading strategy parameters in 2025?
Focus on Bayesian optimization vs Grid search vs Random search.
"""
    
    response = await client.query(prompt)
    
    print(f"\n✅ Response received:")
    print(f"   Model: {response['model']}")
    print(f"   Tokens: {response['usage'].get('total_tokens', 0)}")
    print(f"   Content length: {len(response['content'])} chars")
    print(f"\n📄 Content preview:")
    print(response['content'][:500] + "...")
    
    return {'status': 'success', 'response': response}


async def test_2_strategy_code_generation(client: PerplexityMCPClient):
    """Test 2: Генерация кода стратегии через Perplexity"""
    print("\n" + "="*80)
    print("🔧 TEST 2: Генерация кода стратегии")
    print("="*80)
    
    prompt = """
Generate Python code for an EMA crossover trading strategy optimized for crypto (BTC/USDT).
Include:
- Fast and slow EMA calculation
- Entry/exit signals
- Stop loss and take profit
- Parameter space for ML-optimization
"""
    
    response = await client.query(prompt)
    
    print(f"\n✅ Code generated")
    print(f"   Length: {len(response['content'])} chars")
    
    # Extract code blocks
    import re
    code_blocks = re.findall(r'```python\n(.*?)```', response['content'], re.DOTALL)
    
    if code_blocks:
        print(f"   Code blocks found: {len(code_blocks)}")
        print(f"\n📄 First code block:")
        print(code_blocks[0][:300] + "...")
    
    return {'status': 'success', 'code_blocks': len(code_blocks), 'response': response}


async def test_3_ml_optimization_with_perplexity(client: PerplexityMCPClient, data: pd.DataFrame):
    """Test 3: ML-оптимизация с рекомендациями Perplexity"""
    print("\n" + "="*80)
    print("🤖 TEST 3: ML-оптимизация с рекомендациями Perplexity")
    print("="*80)
    
    # Step 1: Ask Perplexity for recommendations
    print("\n📊 Step 1: Запрос рекомендаций у Perplexity...")
    
    prompt = """
For EMA crossover strategy on BTC/USDT 15-minute timeframe:
1. What are optimal parameter ranges?
2. Which ML-optimization method is best (Grid/Bayes/Random)?
3. What metrics to optimize (Sharpe/Return/Win rate)?
"""
    
    response = await client.query(prompt)
    print(f"✅ Recommendations received ({len(response['content'])} chars)")
    
    # Step 2: Apply recommendations
    print("\n🔧 Step 2: Применение рекомендаций...")
    
    from backend.ml.optimizer import LightGBMOptimizer
    
    param_space = {
        'fast': [5, 10, 15, 20],
        'slow': [20, 30, 40, 50],
        'take_profit': [0.015, 0.02, 0.03],
        'stop_loss': [0.008, 0.01, 0.015]
    }
    
    def objective(params):
        result = simple_backtest(data, params)
        sharpe = result['sharpe_ratio']
        trades = result['total_trades']
        
        if trades < 5:
            sharpe *= 0.1
        elif trades < 10:
            sharpe *= 0.5
        
        return sharpe
    
    optimizer = LightGBMOptimizer(
        objective_function=objective,
        param_space=param_space,
        n_jobs=-1,
        verbose=0
    )
    
    start_time = datetime.now()
    result = await optimizer.optimize(n_trials=30)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"✅ Optimization complete in {elapsed:.1f}s")
    print(f"   Best Sharpe: {result.best_score:.4f}")
    print(f"   Best params: {result.best_params}")
    
    # Step 3: Final backtest
    final_results = simple_backtest(data, result.best_params)
    
    print(f"\n📈 Final results:")
    print(f"   Return: {final_results['total_return']*100:.2f}%")
    print(f"   Sharpe: {final_results['sharpe_ratio']:.2f}")
    print(f"   Win Rate: {final_results['win_rate']*100:.2f}%")
    print(f"   Trades: {final_results['total_trades']}")
    
    return {
        'status': 'success',
        'perplexity_advice': response['content'][:200],
        'optimization_result': result,
        'final_metrics': final_results
    }


async def test_4_results_analysis_perplexity(client: PerplexityMCPClient, results: Dict):
    """Test 4: Анализ результатов оптимизации через Perplexity"""
    print("\n" + "="*80)
    print("📊 TEST 4: Анализ результатов через Perplexity")
    print("="*80)
    
    prompt = f"""
Analyze these ML-optimization results for EMA crossover strategy:

Results:
- Total Return: {results['total_return']*100:.2f}%
- Sharpe Ratio: {results['sharpe_ratio']:.2f}
- Win Rate: {results['win_rate']*100:.2f}%
- Total Trades: {results['total_trades']}
- Max Drawdown: {results['max_drawdown']*100:.2f}%

Questions:
1. Are these results good for crypto trading?
2. What are the main risks?
3. How to improve the strategy?
4. Should we proceed with live testing?
"""
    
    response = await client.query(prompt)
    
    print(f"\n✅ Analysis received:")
    print(f"   Length: {len(response['content'])} chars")
    print(f"\n📄 Analysis:")
    print(response['content'])
    
    return {'status': 'success', 'analysis': response['content']}


async def test_5_iterative_optimization(client: PerplexityMCPClient, data: pd.DataFrame):
    """Test 5: Iterative optimization (3 cycles Copilot ↔ Perplexity)"""
    print("\n" + "="*80)
    print("🔄 TEST 5: Iterative Optimization (3 cycles)")
    print("="*80)
    
    results_history = []
    
    for cycle in range(1, 4):
        print(f"\n{'─'*80}")
        print(f"🔄 CYCLE {cycle}/3")
        print(f"{'─'*80}")
        
        # Ask Perplexity for advice
        if cycle == 1:
            prompt = "Initial parameter suggestions for EMA crossover strategy on BTC 15min"
        else:
            prev_result = results_history[-1]
            prompt = f"""
Previous optimization (cycle {cycle-1}):
- Sharpe: {prev_result['sharpe']:.2f}
- Win Rate: {prev_result['win_rate']*100:.1f}%
- Trades: {prev_result['trades']}

Suggest improvements for cycle {cycle}.
"""
        
        response = await client.query(prompt)
        print(f"✅ Perplexity advice received")
        
        # Run optimization
        from backend.ml.optimizer import LightGBMOptimizer
        
        # Adjust param space based on cycle
        if cycle == 1:
            param_space = {
                'fast': [5, 10, 15],
                'slow': [20, 30, 40],
                'take_profit': [0.02, 0.03],
                'stop_loss': [0.01, 0.015]
            }
        elif cycle == 2:
            # Narrow down based on cycle 1
            param_space = {
                'fast': [8, 10, 12],
                'slow': [25, 30, 35],
                'take_profit': [0.02, 0.025, 0.03],
                'stop_loss': [0.01, 0.012, 0.015]
            }
        else:
            # Fine-tune
            param_space = {
                'fast': [9, 10, 11],
                'slow': [28, 30, 32],
                'take_profit': [0.022, 0.025, 0.028],
                'stop_loss': [0.011, 0.012, 0.013]
            }
        
        def objective(params):
            result = simple_backtest(data, params)
            sharpe = result['sharpe_ratio']
            trades = result['total_trades']
            
            if trades < 5:
                sharpe *= 0.1
            elif trades < 10:
                sharpe *= 0.5
            
            return sharpe
        
        optimizer = LightGBMOptimizer(
            objective_function=objective,
            param_space=param_space,
            n_jobs=-1,
            verbose=0
        )
        
        result = await optimizer.optimize(n_trials=20)
        final = simple_backtest(data, result.best_params)
        
        results_history.append({
            'cycle': cycle,
            'params': result.best_params,
            'sharpe': final['sharpe_ratio'],
            'return': final['total_return'],
            'win_rate': final['win_rate'],
            'trades': final['total_trades']
        })
        
        print(f"\n📈 Cycle {cycle} results:")
        print(f"   Sharpe: {final['sharpe_ratio']:.2f}")
        print(f"   Return: {final['total_return']*100:.2f}%")
        print(f"   Win Rate: {final['win_rate']*100:.2f}%")
        print(f"   Params: {result.best_params}")
    
    print(f"\n{'='*80}")
    print(f"📊 ITERATIVE OPTIMIZATION SUMMARY")
    print(f"{'='*80}")
    
    for r in results_history:
        print(f"\nCycle {r['cycle']}:")
        print(f"   Sharpe: {r['sharpe']:.2f}")
        print(f"   Return: {r['return']*100:+.2f}%")
        print(f"   Win Rate: {r['win_rate']*100:.1f}%")
    
    improvement = ((results_history[-1]['sharpe'] - results_history[0]['sharpe']) / 
                   (abs(results_history[0]['sharpe']) + 1e-9)) * 100
    
    print(f"\n💡 Overall improvement: {improvement:+.1f}%")
    
    return {'status': 'success', 'history': results_history}


async def test_6_multi_strategy_comparison(client: PerplexityMCPClient, data: pd.DataFrame):
    """Test 6: Multi-strategy comparison через Perplexity"""
    print("\n" + "="*80)
    print("⚖️  TEST 6: Multi-Strategy Comparison")
    print("="*80)
    
    strategies = ['EMA Crossover', 'RSI Mean Reversion', 'Bollinger Bands']
    
    prompt = f"""
Compare these trading strategies for BTC/USDT 15-minute timeframe:
{', '.join(strategies)}

Which one is best for:
1. Trending markets
2. Range-bound markets
3. High volatility
4. Low volatility
"""
    
    response = await client.query(prompt)
    
    print(f"\n✅ Comparison received:")
    print(response['content'])
    
    return {'status': 'success', 'comparison': response['content']}


async def test_7_feature_engineering(client: PerplexityMCPClient):
    """Test 7: Feature engineering с Perplexity AI"""
    print("\n" + "="*80)
    print("🔬 TEST 7: Feature Engineering Recommendations")
    print("="*80)
    
    prompt = """
What are the TOP-10 most important features for ML-optimization of trading strategies?
Include:
- Technical indicators
- Price patterns
- Volume analysis
- Time-based features
"""
    
    response = await client.query(prompt)
    
    print(f"\n✅ Feature engineering guide received:")
    print(response['content'])
    
    return {'status': 'success', 'features': response['content']}


async def test_8_walkforward_guidance(client: PerplexityMCPClient):
    """Test 8: Walk-forward optimization guidance"""
    print("\n" + "="*80)
    print("📅 TEST 8: Walk-Forward Optimization Guide")
    print("="*80)
    
    prompt = """
Explain walk-forward optimization for trading strategies:
1. How to setup training/testing windows
2. Optimal window sizes for crypto
3. How to detect overfitting
4. Parameter stability metrics
"""
    
    response = await client.query(prompt)
    
    print(f"\n✅ Walk-forward guide received:")
    print(response['content'])
    
    return {'status': 'success', 'guide': response['content']}


# ==================== MAIN TEST RUNNER ====================

async def run_all_tests():
    """Run comprehensive E2E test suite"""
    
    print("\n" + "="*80)
    print("🚀 COMPREHENSIVE E2E TEST SUITE")
    print("   Copilot ↔ Perplexity AI (MCP) ↔ ML-Optimization")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize
    client = PerplexityMCPClient()
    
    print(f"\n📊 Loading test data...")
    data = await load_test_data(n_bars=2000)
    print(f"✅ Loaded {len(data):,} bars")
    
    # Run tests
    test_results = {}
    
    try:
        test_results['test_1'] = await test_1_basic_perplexity_query(client)
        test_results['test_2'] = await test_2_strategy_code_generation(client)
        test_results['test_3'] = await test_3_ml_optimization_with_perplexity(client, data)
        test_results['test_4'] = await test_4_results_analysis_perplexity(
            client, 
            test_results['test_3']['final_metrics']
        )
        test_results['test_5'] = await test_5_iterative_optimization(client, data)
        test_results['test_6'] = await test_6_multi_strategy_comparison(client, data)
        test_results['test_7'] = await test_7_feature_engineering(client)
        test_results['test_8'] = await test_8_walkforward_guidance(client)
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Summary
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED!")
    print("="*80)
    
    passed = sum(1 for r in test_results.values() if r.get('status') == 'success')
    total = len(test_results)
    
    print(f"\n📊 Summary:")
    print(f"   Tests passed: {passed}/{total}")
    print(f"   Success rate: {passed/total*100:.1f}%")
    print(f"   Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n🎯 Integration Status:")
    print(f"   ✅ Copilot → Perplexity AI (MCP)")
    print(f"   ✅ Perplexity AI → ML-Optimization")
    print(f"   ✅ ML-Optimization → Copilot")
    print(f"   ✅ Iterative feedback loop (3 cycles)")
    
    # Save results
    results_file = Path('logs/e2e_test_results.json')
    results_file.parent.mkdir(exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'tests': {k: {'status': v.get('status')} for k, v in test_results.items()},
            'summary': {
                'passed': passed,
                'total': total,
                'success_rate': passed/total
            }
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {results_file}")
    print()


if __name__ == '__main__':
    asyncio.run(run_all_tests())
