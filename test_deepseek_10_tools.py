#!/usr/bin/env python3
"""
Test DeepSeek 10 MCP Tools Integration (100% Complete)

Проверка всех 10 DeepSeek tools в MCP Server:
- 3 базовых (generate_strategy, fix_strategy, test_strategy)
- 7 специализированных (analyze, optimize, backtest_analysis, risk, compare, generate_tests, refactor)
"""

import sys
from pathlib import Path

# Добавляем путь к MCP серверу
mcp_path = Path(__file__).parent / "mcp-server"
sys.path.insert(0, str(mcp_path))

async def test_deepseek_tools():
    """Проверка всех 10 DeepSeek MCP tools"""
    
    try:
        from server import mcp
        
        # Получаем все зарегистрированные tools (список имён)
        all_tools = await mcp.get_tools()
        
        # Фильтруем DeepSeek tools
        deepseek_tools = [tool for tool in all_tools if tool.startswith('deepseek_')]
        
        print("=" * 80)
        print("🚀 DEEPSEEK MCP TOOLS INTEGRATION TEST")
        print("=" * 80)
        print(f"✅ Total MCP Tools: {len(all_tools)}")
        print(f"🤖 DeepSeek Tools: {len(deepseek_tools)}")
        print()
        
        # Базовые tools (Phase 4)
        basic_tools = [
            'deepseek_generate_strategy',
            'deepseek_fix_strategy',
            'deepseek_test_strategy'
        ]
        
        # Специализированные tools (Phase 5)
        specialized_tools = [
            'deepseek_analyze_strategy',
            'deepseek_optimize_parameters',
            'deepseek_backtest_analysis',
            'deepseek_risk_analysis',
            'deepseek_compare_strategies',
            'deepseek_generate_tests',
            'deepseek_refactor_code'
        ]
        
        print("📋 BASIC TOOLS (Phase 4):")
        for tool_name in basic_tools:
            found = tool_name in deepseek_tools
            status = "✅" if found else "❌"
            print(f"  {status} {tool_name}")
        print()
        
        print("🎯 SPECIALIZED TOOLS (Phase 5):")
        for tool_name in specialized_tools:
            found = tool_name in deepseek_tools
            status = "✅" if found else "❌"
            print(f"  {status} {tool_name}")
        print()
        
        # Статистика
        total_expected = len(basic_tools) + len(specialized_tools)
        integration_level = (len(deepseek_tools) / total_expected) * 100
        
        print("=" * 80)
        print("📊 INTEGRATION STATISTICS")
        print("=" * 80)
        print(f"Expected Tools: {total_expected}")
        print(f"Registered Tools: {len(deepseek_tools)}")
        print(f"Integration Level: {integration_level:.1f}%")
        print()
        
        if integration_level == 100:
            print("🎉 100% INTEGRATION COMPLETE! DeepSeek Agent fully integrated with MCP!")
        elif integration_level >= 80:
            print(f"⚠️  {integration_level:.1f}% integration - Missing {total_expected - len(deepseek_tools)} tools")
        else:
            print(f"❌ Low integration level: {integration_level:.1f}%")
        
        print("=" * 80)
        
        # Детали всех DeepSeek tools
        print("\n🔍 DEEPSEEK TOOLS DETAILS:")
        print("-" * 80)
        for tool_name in deepseek_tools:
            print(f"  • {tool_name}")
        print("-" * 80)
        
        return integration_level == 100
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_deepseek_tools())
    sys.exit(0 if success else 1)
