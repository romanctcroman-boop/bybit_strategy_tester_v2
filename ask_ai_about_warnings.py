"""
Консультация с AI по поводу диагностических предупреждений VS Code
"""
import asyncio
import sys
from pathlib import Path

# Добавить MCP server в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

# Импортируем через прямой путь
from server import perplexity_search


async def ask_ai_about_warnings():
    """Спросить AI о том, как решить предупреждения"""
    
    print("=" * 80)
    print("🤖 КОНСУЛЬТАЦИЯ С PERPLEXITY AI")
    print("=" * 80)
    print()
    
    query = """
    I'm getting these diagnostic warnings in VS Code for my project:
    
    1. **Frontend package.json warning:**
       - Error code: 768
       - Message: "Problems loading reference 'https://json.schemastore.org/eslintrc': 
         Service Unavailable. The server is currently unavailable (overloaded or down)."
       - File: frontend/package.json
    
    2. **PowerShell script warnings:**
       - PSUseApprovedVerbs: "The cmdlet 'Parse-LogEntry' uses an unapproved verb"
       - PSAvoidAssignmentToAutomaticVariable: "The Variable 'event' is an automatic 
         variable that is built into PowerShell, assigning to it might have undesired 
         side effects"
       - File: mcp_monitor_simple_v2.ps1
    
    Questions:
    1. Are these warnings critical or can they be safely ignored?
    2. What's the best way to fix them if needed?
    3. Should I suppress these warnings or address them?
    
    Please provide practical, actionable advice for each warning.
    """
    
    print("📝 Отправляю запрос Perplexity AI...")
    print()
    
    try:
        # Вызываем через внутренний API напрямую
        from server import _call_perplexity_api
        
        result = await _call_perplexity_api(query, model="sonar-pro")
        
        if result.get("success"):
            print("✅ Ответ получен!")
            print()
            print("─" * 80)
            print(result.get("answer", "No answer"))
            print("─" * 80)
            print()
            
            # Источники
            sources = result.get("sources", [])
            if sources:
                print("📚 Источники:")
                for i, source in enumerate(sources[:5], 1):
                    print(f"  {i}. {source.get('title', 'N/A')}")
                    if source.get('url'):
                        print(f"     {source['url']}")
            
            # Метрики
            usage = result.get("usage", {})
            print()
            print(f"📊 Метрики:")
            print(f"  Tokens: {usage.get('total_tokens', 'N/A')}")
            print(f"  Model: {result.get('model', 'N/A')}")
        else:
            print(f"❌ Ошибка: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        print(f"❌ Исключение: {e}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(ask_ai_about_warnings())
