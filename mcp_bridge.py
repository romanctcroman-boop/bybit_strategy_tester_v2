"""
MCP Server Integration для Copilot ↔ Perplexity AI
===================================================

Unified interface для взаимодействия Copilot с Perplexity AI через MCP
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class MCPPerplexityBridge:
    """
    Мост между Copilot и Perplexity AI через MCP сервер
    
    Обеспечивает:
    - Унифицированный API для запросов
    - Кэширование ответов
    - Rate limiting
    - Error handling
    - Logging всех взаимодействий
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: str = "logs/mcp_cache",
        enable_cache: bool = True
    ):
        """
        Args:
            api_key: Perplexity API key (или из .env)
            cache_dir: Директория для кэша
            enable_cache: Включить кэширование
        """
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = api_key or os.getenv('PERPLEXITY_API_KEY')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.enable_cache = enable_cache
        
        self.request_history: List[Dict] = []
        
        if not self.api_key:
            logger.warning("⚠️  PERPLEXITY_API_KEY not set, using MOCK mode")
            self.mock_mode = True
        else:
            self.mock_mode = False
            logger.info("✅ MCP-Perplexity Bridge initialized")
    
    def _get_cache_key(self, prompt: str, system_prompt: str = None) -> str:
        """Generate cache key from prompt"""
        import hashlib
        content = f"{system_prompt or ''}\n{prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load response from cache"""
        if not self.enable_cache:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📦 Cache hit: {cache_key[:8]}")
                    return data
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, response: Dict):
        """Save response to cache"""
        if not self.enable_cache:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(response, f, indent=2, ensure_ascii=False)
                logger.info(f"💾 Cached: {cache_key[:8]}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "sonar-pro",
        temperature: float = 0.2,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Отправить запрос к Perplexity AI через MCP
        
        Args:
            prompt: Пользовательский запрос
            system_prompt: Системный промпт (опционально)
            model: Модель Perplexity (sonar-pro, sonar)
            temperature: Температура генерации (0-1)
            max_tokens: Макс токенов в ответе
        
        Returns:
            {
                'content': str,              # Ответ от Perplexity
                'model': str,                # Использованная модель
                'usage': dict,               # Токены
                'citations': list,           # Источники
                'cached': bool,              # Из кэша?
                'timestamp': str             # Время запроса
            }
        """
        
        # Check cache
        cache_key = self._get_cache_key(prompt, system_prompt)
        cached_response = self._load_from_cache(cache_key)
        
        if cached_response:
            cached_response['cached'] = True
            return cached_response
        
        # Make request
        if self.mock_mode:
            response = self._mock_response(prompt)
        else:
            response = await self._real_request(
                prompt, system_prompt, model, temperature, max_tokens
            )
        
        response['cached'] = False
        response['timestamp'] = datetime.now().isoformat()
        
        # Save to cache
        self._save_to_cache(cache_key, response)
        
        # Log request
        self.request_history.append({
            'prompt': prompt[:100] + '...' if len(prompt) > 100 else prompt,
            'response_length': len(response['content']),
            'timestamp': response['timestamp'],
            'cached': False
        })
        
        return response
    
    async def _real_request(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Make real API request to Perplexity"""
        
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
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            logger.info(f"🌐 Sending request to Perplexity API...")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(f"✅ Response received ({result.get('usage', {}).get('total_tokens', 0)} tokens)")
                
                return {
                    'content': result['choices'][0]['message']['content'],
                    'model': result['model'],
                    'usage': result.get('usage', {}),
                    'citations': result.get('citations', [])
                }
        
        except Exception as e:
            logger.error(f"❌ Perplexity API error: {e}")
            logger.warning("Falling back to mock response")
            return self._mock_response(prompt)
    
    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """Generate mock response (for testing without API key)"""
        
        logger.info(f"🤖 Generating mock response...")
        
        # Detect intent
        prompt_lower = prompt.lower()
        
        if 'optimize' in prompt_lower or 'parameters' in prompt_lower:
            content = """
# ML-Optimization Recommendations

**Best practices for strategy parameter optimization:**

1. **Optimization method:** Use Bayesian Optimization (Optuna/scikit-optimize)
   - More efficient than Grid Search
   - Finds optimal parameters faster
   - Handles non-linear parameter interactions

2. **Parameter ranges:**
   - Fast EMA: 5-20 periods
   - Slow EMA: 20-50 periods
   - Stop Loss: 0.5-2%
   - Take Profit: 1-5%

3. **Optimization metrics:**
   - Primary: Sharpe Ratio (risk-adjusted returns)
   - Secondary: Max Drawdown, Win Rate
   - Constraint: Minimum 30 trades for statistical significance

4. **Validation:**
   - Use walk-forward optimization
   - Test on out-of-sample data
   - Monitor parameter stability
"""
        
        elif 'strategy' in prompt_lower and 'code' in prompt_lower:
            content = """
# Trading Strategy Code Template

```python
import pandas as pd
import numpy as np

def ema_crossover_strategy(data, fast=10, slow=30, stop_loss=0.01, take_profit=0.02):
    '''
    EMA Crossover Strategy
    
    Entry: Fast EMA crosses above Slow EMA
    Exit: Stop loss, take profit, or opposite signal
    '''
    
    # Calculate indicators
    data['ema_fast'] = data['close'].ewm(span=fast, adjust=False).mean()
    data['ema_slow'] = data['close'].ewm(span=slow, adjust=False).mean()
    
    # Generate signals
    data['signal'] = np.where(data['ema_fast'] > data['ema_slow'], 1, 0)
    data['position'] = data['signal'].diff()
    
    return data

# Parameter space for ML-optimization
PARAM_SPACE = {
    'fast': [5, 10, 15, 20],
    'slow': [20, 30, 40, 50],
    'stop_loss': [0.005, 0.01, 0.015, 0.02],
    'take_profit': [0.015, 0.02, 0.03, 0.04]
}
```
"""
        
        elif 'analyze' in prompt_lower or 'results' in prompt_lower:
            content = """
# Strategy Performance Analysis

**Key metrics evaluation:**

1. **Sharpe Ratio:** 
   - Good: > 1.0
   - Excellent: > 2.0
   - Current: Needs improvement if < 0.5

2. **Win Rate:**
   - Typical for trend-following: 40-50%
   - Mean reversion: 50-60%
   - High win rate (>70%) may indicate overfitting

3. **Max Drawdown:**
   - Acceptable: < 20%
   - Concerning: > 30%
   - Critical: > 50%

4. **Trade Count:**
   - Minimum for significance: 30 trades
   - Ideal: 100+ trades
   - Too few: Risk of overfitting

**Recommendations:**
- Add trailing stop for profit protection
- Test on different market conditions
- Implement position sizing based on volatility
"""
        
        elif 'features' in prompt_lower or 'indicators' in prompt_lower:
            content = """
# Technical Indicators for ML-Optimization

**TOP-10 Features:**

1. **Trend Indicators:**
   - EMA (9, 21, 50, 200)
   - ADX (Average Directional Index)
   - Supertrend

2. **Momentum:**
   - RSI (14 periods)
   - MACD
   - Stochastic Oscillator

3. **Volatility:**
   - ATR (Average True Range)
   - Bollinger Bands width
   - Historical volatility (20 periods)

4. **Volume:**
   - Volume MA ratio
   - OBV (On-Balance Volume)
   - Volume spike detection

5. **Price Action:**
   - Support/Resistance levels
   - Pivot points
   - Price distance from key levels

**Feature engineering tips:**
- Normalize all features to 0-1 range
- Use correlation matrix to remove redundant features
- Test feature importance with LightGBM/XGBoost
"""
        
        elif 'compare' in prompt_lower or 'strategies' in prompt_lower:
            content = """
# Strategy Comparison Guide

**EMA Crossover vs RSI Mean Reversion vs Bollinger Bands:**

**EMA Crossover:**
- ✅ Best for: Trending markets
- ✅ Pros: Simple, clear signals
- ⚠️  Cons: Lags in choppy markets
- Win Rate: 40-45%
- Sharpe: 0.8-1.5

**RSI Mean Reversion:**
- ✅ Best for: Range-bound markets
- ✅ Pros: Catches reversals
- ⚠️  Cons: Struggles in strong trends
- Win Rate: 55-60%
- Sharpe: 1.0-2.0

**Bollinger Bands:**
- ✅ Best for: High volatility
- ✅ Pros: Adapts to volatility
- ⚠️  Cons: Many false signals
- Win Rate: 48-52%
- Sharpe: 0.9-1.8

**Recommendation:** Combine multiple strategies in ensemble
"""
        
        else:
            content = f"""
# Perplexity AI Response (Mock)

Query: {prompt[:200]}...

This is a **MOCK response** for testing without API key.

To get real Perplexity AI insights:
1. Set PERPLEXITY_API_KEY in .env file
2. Get API key from https://www.perplexity.ai/
3. Re-run the test

**Mock response provides:**
- Strategy recommendations
- Parameter optimization guidance
- Code examples
- Performance analysis tips

For production use, enable real Perplexity API!
"""
        
        return {
            'content': content,
            'model': 'sonar-pro (MOCK)',
            'usage': {'total_tokens': len(content.split())},
            'citations': []
        }
    
    def get_request_history(self) -> List[Dict]:
        """Get history of all requests"""
        return self.request_history
    
    def clear_cache(self):
        """Clear all cached responses"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("🗑️  Cache cleared")
    
    def save_session_log(self, filepath: str = "logs/mcp_session.json"):
        """Save session log to file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_requests': len(self.request_history),
                'requests': self.request_history,
                'mock_mode': self.mock_mode
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Session log saved to {filepath}")


# ==================== CONVENIENCE FUNCTIONS ====================

async def ask_perplexity(prompt: str, system_prompt: str = None) -> str:
    """
    Convenience function: быстрый запрос к Perplexity
    
    Usage:
        response = await ask_perplexity("How to optimize EMA crossover?")
        print(response)
    """
    bridge = MCPPerplexityBridge()
    result = await bridge.query(prompt, system_prompt)
    return result['content']


async def get_strategy_code(strategy_name: str) -> str:
    """
    Get strategy code from Perplexity
    
    Usage:
        code = await get_strategy_code("EMA Crossover")
    """
    prompt = f"Generate Python code for {strategy_name} trading strategy"
    return await ask_perplexity(prompt)


async def analyze_backtest_results(metrics: Dict) -> str:
    """
    Analyze backtest results with Perplexity
    
    Usage:
        analysis = await analyze_backtest_results({
            'sharpe': 1.5,
            'return': 0.25,
            'win_rate': 0.55
        })
    """
    prompt = f"""
Analyze these backtest results:
{json.dumps(metrics, indent=2)}

Provide:
1. Performance evaluation
2. Risk assessment
3. Improvement suggestions
"""
    return await ask_perplexity(prompt)


# ==================== EXAMPLE USAGE ====================

async def example_usage():
    """Example: How to use MCP-Perplexity Bridge"""
    
    print("\n" + "="*80)
    print("📖 MCP-PERPLEXITY BRIDGE - EXAMPLE USAGE")
    print("="*80 + "\n")
    
    # Initialize bridge
    bridge = MCPPerplexityBridge(enable_cache=True)
    
    # Example 1: Basic query
    print("1️⃣  Basic query:")
    response = await bridge.query("What is the best ML algorithm for trading?")
    print(f"   Response: {response['content'][:100]}...")
    print(f"   Cached: {response['cached']}\n")
    
    # Example 2: Get strategy code
    print("2️⃣  Get strategy code:")
    code = await get_strategy_code("RSI Mean Reversion")
    print(f"   Code length: {len(code)} chars\n")
    
    # Example 3: Analyze results
    print("3️⃣  Analyze results:")
    analysis = await analyze_backtest_results({
        'sharpe_ratio': 1.5,
        'total_return': 0.25,
        'win_rate': 0.55,
        'max_drawdown': 0.15
    })
    print(f"   Analysis: {analysis[:100]}...\n")
    
    # Example 4: Request history
    print("4️⃣  Request history:")
    history = bridge.get_request_history()
    print(f"   Total requests: {len(history)}")
    
    # Save session log
    bridge.save_session_log()
    
    print("\n✅ Example complete!\n")


if __name__ == '__main__':
    asyncio.run(example_usage())
