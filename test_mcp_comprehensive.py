"""
MCP Server Comprehensive Test Suite
Полная самодиагностика DeepSeek и Perplexity AI Sonar Pro
"""

import asyncio
import sys
from pathlib import Path

# Добавить путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Импорт MCP tools (будут доступны через VS Code Copilot)
print("=" * 80)
print("🧪 MCP SERVER COMPREHENSIVE TEST SUITE")
print("=" * 80)


async def test_health_check():
    """Тест 1: Проверка здоровья MCP сервера"""
    print("\n[1/6] Health Check...")
    # Tool: mcp_bybit-strateg_health_check
    print("✅ Используйте: mcp_bybit-strateg_health_check")
    

async def test_deepseek_quick():
    """Тест 2: DeepSeek Quick Reasoning"""
    print("\n[2/6] DeepSeek Quick Reasoning...")
    # Tool: mcp_bybit-strateg_quick_reasoning_analysis
    print("✅ Используйте: mcp_bybit-strateg_quick_reasoning_analysis")
    print("   Query: 'Самодиагностика: оптимальный период RSI для скальпинга?'")


async def test_deepseek_chain():
    """Тест 3: DeepSeek Chain-of-Thought"""
    print("\n[3/6] DeepSeek Chain-of-Thought Analysis...")
    # Tool: mcp_bybit-strateg_chain_of_thought_analysis
    print("✅ Используйте: mcp_bybit-strateg_chain_of_thought_analysis")
    print("   Query: 'Проанализируй стратегию DCA для BTC в 5 шагов reasoning'")


async def test_perplexity_search():
    """Тест 4: Perplexity Search"""
    print("\n[4/6] Perplexity Sonar Pro Search...")
    # Tool: mcp_bybit-strateg_perplexity_search
    print("✅ Используйте: mcp_bybit-strateg_perplexity_search")
    print("   Model: sonar-pro")
    print("   Query: 'Текущая ситуация на крипторынке BTC ноябрь 2025'")


async def test_perplexity_crypto():
    """Тест 5: Perplexity Crypto Analysis"""
    print("\n[5/6] Perplexity Crypto Analysis...")
    # Tool: mcp_bybit-strateg_perplexity_analyze_crypto
    print("✅ Используйте: mcp_bybit-strateg_perplexity_analyze_crypto")
    print("   Symbol: BTCUSDT")
    print("   Timeframe: 1d")


async def test_cache_stats():
    """Тест 6: Cache Statistics"""
    print("\n[6/6] Cache Stats...")
    # Tool: mcp_bybit-strateg_cache_stats
    print("✅ Используйте: mcp_bybit-strateg_cache_stats")


async def main():
    """Запуск всех тестов"""
    print("\n📋 ИНСТРУКЦИИ ДЛЯ ЗАПУСКА ТЕСТОВ:")
    print("-" * 80)
    print("1. Откройте VS Code Copilot Chat")
    print("2. Скопируйте и выполните каждую команду из списка ниже:")
    print("-" * 80)
    
    await test_health_check()
    await test_deepseek_quick()
    await test_deepseek_chain()
    await test_perplexity_search()
    await test_perplexity_crypto()
    await test_cache_stats()
    
    print("\n" + "=" * 80)
    print("✅ ВСЕ ТЕСТЫ ГОТОВЫ К ЗАПУСКУ")
    print("=" * 80)
    print("\n💡 РЕКОМЕНДАЦИЯ:")
    print("   Запустите MCP Monitor для отслеживания всех вызовов:")
    print("   Start-Process powershell -ArgumentList \"-NoExit\", \"-ExecutionPolicy\", \"Bypass\", \"-File\", \"D:\\bybit_strategy_tester_v2\\scripts\\mcp_monitor_simple.ps1\"")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
