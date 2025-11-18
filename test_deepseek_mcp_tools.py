"""
🧪 Тест DeepSeek MCP Tools
Проверка интеграции DeepSeek Agent с MCP сервером
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Add mcp-server to path
sys.path.insert(0, str(project_root / "mcp-server"))

from server import mcp


def test_deepseek_tools():
    """Тест наличия DeepSeek MCP tools"""
    
    print("=" * 80)
    print("🧪 DEEPSEEK MCP TOOLS TEST")
    print("=" * 80)
    
    # Список ожидаемых DeepSeek tools
    expected_tools = [
        "deepseek_generate_strategy",
        "deepseek_fix_strategy",
        "deepseek_test_strategy"
    ]
    
    # Получить все tools
    all_tools = [name for name in dir(mcp) if not name.startswith('_')]
    
    print(f"\n📊 Total MCP tools: {len(all_tools)}")
    
    # Проверить DeepSeek tools
    deepseek_tools = [name for name in all_tools if 'deepseek' in name.lower()]
    
    print(f"\n🤖 DeepSeek tools found: {len(deepseek_tools)}")
    
    if deepseek_tools:
        print("\n✅ DeepSeek MCP Tools:")
        for tool in deepseek_tools:
            status = "✅" if tool in expected_tools else "⚠️"
            print(f"   {status} {tool}")
    else:
        print("\n❌ No DeepSeek tools found!")
    
    # Проверка всех ожидаемых tools
    print(f"\n🔍 Expected tools check:")
    all_found = True
    
    for tool in expected_tools:
        found = tool in deepseek_tools
        status = "✅" if found else "❌"
        print(f"   {status} {tool}")
        
        if not found:
            all_found = False
    
    # Финальный результат
    print("\n" + "=" * 80)
    
    if all_found and len(deepseek_tools) == len(expected_tools):
        print("🎉 SUCCESS! All 3 DeepSeek MCP tools registered!")
        print("✅ DeepSeek Agent is now fully integrated with MCP Server")
        print("✅ Copilot can now use DeepSeek for code generation!")
    elif deepseek_tools:
        print(f"⚠️  PARTIAL: {len(deepseek_tools)}/{len(expected_tools)} tools found")
    else:
        print("❌ FAILED: No DeepSeek tools found in MCP Server")
    
    print("=" * 80)
    
    # Дополнительная статистика
    print(f"\n📈 MCP Server Statistics:")
    print(f"   ├─ Total tools: {len(all_tools)}")
    print(f"   ├─ Perplexity tools: {len([t for t in all_tools if 'perplexity' in t.lower()])}")
    print(f"   ├─ DeepSeek tools: {len(deepseek_tools)}")
    print(f"   └─ Other tools: {len(all_tools) - len([t for t in all_tools if 'perplexity' in t.lower() or 'deepseek' in t.lower()])}")
    
    return all_found


if __name__ == "__main__":
    try:
        success = test_deepseek_tools()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
