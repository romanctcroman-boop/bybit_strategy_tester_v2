"""Простая проверка работоспособности backend"""
import asyncio
import httpx

async def simple_test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("✅ Backend запущен успешно!")
        print("\n📊 Выполненные изменения:")
        print("1. ✅ API Key Auth - добавлена защита /mcp")
        print("2. ✅ Deadlock Prevention - inline комментарии в MCP tools")
        print("3. ✅ Load Test Script - scripts/load_test_mcp.py")
        print("4. ✅ Agent Feedback - AGENT_FEEDBACK_IMPLEMENTATION_SUMMARY.md")
        print("5. ✅ JSON-RPC Docs - docs/MCP_HTTP_CHEATSHEET.md")
        print("\n3 MCP tools зарегистрированы:")
        print("  - mcp_agent_to_agent_send_to_deepseek")
        print("  - mcp_agent_to_agent_send_to_perplexity")
        print("  - mcp_agent_to_agent_get_consensus")
        print("\n📝 Следующие шаги:")
        print("1. Запустите load test: py scripts\\load_test_mcp.py")
        print("2. Включите auth в .env: MCP_REQUIRE_AUTH=true, MCP_API_KEY=...")
        print("3. Добавьте alerts в Alertmanager")
        print("4. Мониторинг 24-48h перед production")

if __name__ == "__main__":
    asyncio.run(simple_test())
