"""
🧪 Проверка DeepSeek MCP Tools через list_all_tools
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Add mcp-server to path
sys.path.insert(0, str(project_root / "mcp-server"))

from server import list_all_tools


async def main():
    """Test DeepSeek tools via list_all_tools"""
    
    print("=" * 80)
    print("🧪 DEEPSEEK MCP TOOLS - List All Tools Test")
    print("=" * 80)
    
    # Call list_all_tools
    result = await list_all_tools()
    
    if result["success"]:
        tools = result["tools"]
        
        print(f"\n📊 Total tools: {result['total_count']}")
        
        # Find DeepSeek tools
        deepseek_tools = [
            tool for tool in tools 
            if 'deepseek' in tool['name'].lower()
        ]
        
        print(f"\n🤖 DeepSeek tools found: {len(deepseek_tools)}")
        
        if deepseek_tools:
            print("\n✅ DeepSeek MCP Tools:")
            for tool in deepseek_tools:
                print(f"\n   📦 {tool['name']}")
                print(f"      Category: {tool.get('category', 'N/A')}")
                if 'description' in tool:
                    desc = tool['description'].split('\n')[0][:80]
                    print(f"      Description: {desc}...")
        else:
            print("\n❌ No DeepSeek tools found!")
            
            # Show some other tools for comparison
            print("\n📋 Sample tools (first 5):")
            for tool in tools[:5]:
                print(f"   - {tool['name']}")
        
        # Check categories
        print(f"\n📂 Tool categories:")
        categories = {}
        for tool in tools:
            cat = tool.get('category', 'Uncategorized')
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in sorted(categories.items()):
            print(f"   - {cat}: {count} tools")
        
        print("\n" + "=" * 80)
        
        if deepseek_tools:
            print("🎉 SUCCESS! DeepSeek tools are registered in MCP Server!")
        else:
            print("❌ FAILED: DeepSeek tools not found in MCP Server")
        
        print("=" * 80)
        
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
