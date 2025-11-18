"""
Test DeepSeek Agent with RSI strategy generation
"""
import sys
import asyncio
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')
sys.path.insert(0, 'd:/bybit_strategy_tester_v2/mcp-server')

print('='*80)
print('TESTING DEEPSEEK AGENT - RSI STRATEGY GENERATION')
print('='*80)

# Import and initialize
from server import initialize_providers, get_deepseek_agent

print('\n🔧 Initializing MCP providers...')
asyncio.run(initialize_providers())

agent = get_deepseek_agent()

if agent is None:
    print('❌ DeepSeek Agent not initialized!')
    sys.exit(1)

print(f'\n✅ DeepSeek Agent loaded: {type(agent).__name__}')

# Test generate_code with RSI strategy prompt
print('\n📝 Generating RSI strategy...')

result = agent.generate_code(
    prompt='''Create a simple RSI trading strategy in Python.

Requirements:
1. Use pandas and talib for RSI calculation
2. RSI period: 14
3. Buy signal: RSI < 30 (oversold)
4. Sell signal: RSI > 70 (overbought)
5. Include signal generation function
6. Add docstrings

Return clean, production-ready code.''',
    context='Trading strategy for Bybit',
    max_tokens=1500
)

print(f'\n✅ Generation complete!')
print(f'   Status: {result.get("status")}')
print(f'   Iterations: {result.get("iterations")}')
print(f'   Tokens: {result.get("tokens", 0)}')
print(f'   Processing time: {result.get("processing_time", 0):.2f}s')

if result.get('status') == 'success':
    code = result.get('code', '')
    print(f'   Code length: {len(code)} chars')
    print(f'\n📄 Generated RSI Strategy:')
    print('='*80)
    print(code)
    print('='*80)
else:
    error = result.get('error', 'Unknown error')
    print(f'\n❌ Generation failed: {error}')
