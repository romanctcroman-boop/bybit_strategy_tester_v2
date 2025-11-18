"""
🔍 Simple Diagnostic with Agent Analysis
Упрощённая диагностика с критичным анализом от агентов
"""

import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os

# Загрузка .env
load_dotenv()


async def load_api_keys():
    """Загрузка всех API ключей"""
    keys = {
        "deepseek": [],
        "perplexity": []
    }
    
    # DeepSeek keys (8 шт)
    for i in range(1, 9):
        key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
        if key:
            keys["deepseek"].append(key)
    
    # Perplexity keys (4 шт)
    for i in range(1, 5):
        key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
        if key:
            keys["perplexity"].append(key)
    
    return keys


async def test_api_key(url: str, api_key: str, model: str) -> bool:
    """Тест одного API ключа"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Test: 2+2=?"}],
                    "max_tokens": 50
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            return response.status_code == 200
    except:
        return False


async def request_agent_analysis(keys: dict, diagnostic_results: dict):
    """🔥 КРИТИЧНО: Запрос аналитики от обоих агентов"""
    
    print("\n" + "=" * 80)
    print("🧠 КРИТИЧНЫЙ ЗАПРОС АНАЛИТИКИ ОТ AI АГЕНТОВ")
    print("=" * 80)
    
    analysis_prompt = f"""
# КРИТИЧЕСКАЯ ЗАДАЧА: Полная диагностика MCP Reliability System

## Текущее состояние

**DeepSeek Keys Working:** {diagnostic_results['deepseek_working']}/{diagnostic_results['deepseek_total']}
**Perplexity Keys Working:** {diagnostic_results['perplexity_working']}/{diagnostic_results['perplexity_total']}
**MCP Server:** {diagnostic_results['mcp_status']}

## Детали проблем

{json.dumps(diagnostic_results, indent=2)}

## Твоя задача (КРИТИЧНО ВАЖНО!)

Проанализируй систему и дай КОНКРЕТНЫЕ рекомендации:

1. **Оценка надёжности:** Готова ли система к production?
2. **Критические проблемы:** Что НЕ работает и ПОЧЕМУ?
3. **План действий:** Что исправить СРОЧНО (шаг за шагом)?
4. **Мониторинг:** Какие метрики отслеживать 24/7?
5. **Автоматизация:** Как улучшить автодиагностику?

Будь максимально конкретным. Это блокирует весь проект!
"""
    
    # DeepSeek Agent
    deepseek_analysis = None
    if keys["deepseek"]:
        print(f"\n🤖 Запрос к DeepSeek Agent...")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": analysis_prompt}],
                        "max_tokens": 3000,
                        "temperature": 0.7
                    },
                    headers={
                        "Authorization": f"Bearer {keys['deepseek'][0]}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deepseek_analysis = data["choices"][0]["message"]["content"]
                    print(f"✅ DeepSeek Agent ответил ({len(deepseek_analysis)} символов)")
        except Exception as e:
            print(f"❌ DeepSeek Agent error: {e}")
    
    # Perplexity Agent
    perplexity_analysis = None
    if keys["perplexity"]:
        print(f"\n🤖 Запрос к Perplexity Agent...")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": analysis_prompt}],
                        "max_tokens": 2000
                    },
                    headers={
                        "Authorization": f"Bearer {keys['perplexity'][0]}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    perplexity_analysis = data["choices"][0]["message"]["content"]
                    print(f"✅ Perplexity Agent ответил ({len(perplexity_analysis)} символов)")
        except Exception as e:
            print(f"❌ Perplexity Agent error: {e}")
    
    return {
        "deepseek": deepseek_analysis,
        "perplexity": perplexity_analysis
    }


async def main():
    print("=" * 80)
    print("🔍 SIMPLE DIAGNOSTIC WITH AGENT ANALYSIS")
    print("=" * 80)
    
    # 1. Загрузка ключей
    print("\n📦 Step 1/4: Загрузка API ключей...")
    keys = await load_api_keys()
    
    print(f"   DeepSeek: {len(keys['deepseek'])} ключей")
    print(f"   Perplexity: {len(keys['perplexity'])} ключей")
    
    if not keys["deepseek"] and not keys["perplexity"]:
        print("\n❌ ОШИБКА: API ключи не найдены в .env!")
        print("   Проверьте файл .env")
        return
    
    # 2. Проверка MCP Server
    print("\n📦 Step 2/4: Проверка MCP Server...")
    mcp_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:3000/health")
            mcp_ok = response.status_code == 200
    except:
        pass
    
    print(f"   MCP Server: {'✅ Работает' if mcp_ok else '⚠️ Недоступен'}")
    
    # 3. Проверка всех API ключей
    print(f"\n📦 Step 3/4: Проверка всех API ключей...")
    
    print(f"\n   Проверка DeepSeek ключей...")
    deepseek_tasks = [
        test_api_key(
            "https://api.deepseek.com/v1/chat/completions",
            key,
            "deepseek-chat"
        )
        for key in keys["deepseek"]
    ]
    deepseek_results = await asyncio.gather(*deepseek_tasks)
    
    for idx, result in enumerate(deepseek_results):
        status = "✅ OK" if result else "❌ FAIL"
        print(f"      Key #{idx + 1}: {status}")
    
    print(f"\n   Проверка Perplexity ключей...")
    perplexity_tasks = [
        test_api_key(
            "https://api.perplexity.ai/chat/completions",
            key,
            "sonar"
        )
        for key in keys["perplexity"]
    ]
    perplexity_results = await asyncio.gather(*perplexity_tasks)
    
    for idx, result in enumerate(perplexity_results):
        status = "✅ OK" if result else "❌ FAIL"
        print(f"      Key #{idx + 1}: {status}")
    
    # Результаты диагностики
    diagnostic_results = {
        "mcp_status": "available" if mcp_ok else "unavailable",
        "deepseek_working": sum(deepseek_results),
        "deepseek_total": len(deepseek_results),
        "perplexity_working": sum(perplexity_results),
        "perplexity_total": len(perplexity_results),
        "timestamp": datetime.now().isoformat()
    }
    
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ")
    print("=" * 80)
    print(f"   MCP Server: {'✅' if mcp_ok else '⚠️'}")
    print(f"   DeepSeek: {sum(deepseek_results)}/{len(deepseek_results)} работают")
    print(f"   Perplexity: {sum(perplexity_results)}/{len(perplexity_results)} работают")
    
    # 4. 🔥 КРИТИЧНО: Запрос аналитики от агентов
    if sum(deepseek_results) > 0 or sum(perplexity_results) > 0:
        print("\n📦 Step 4/4: Запрос аналитики от AI агентов...")
        
        agent_analysis = await request_agent_analysis(keys, diagnostic_results)
        
        # Сохранение результатов
        output_file = f"ai_audit_results/simple_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path("ai_audit_results").mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "diagnostic_results": diagnostic_results,
                "agent_analysis": agent_analysis
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены: {output_file}")
        
        # Вывод аналитики
        if agent_analysis["deepseek"]:
            print("\n" + "=" * 80)
            print("🤖 DEEPSEEK AGENT ANALYSIS")
            print("=" * 80)
            print(agent_analysis["deepseek"])
        
        if agent_analysis["perplexity"]:
            print("\n" + "=" * 80)
            print("🤖 PERPLEXITY AGENT ANALYSIS")
            print("=" * 80)
            print(agent_analysis["perplexity"])
    
    else:
        print("\n❌ Нет рабочих API ключей для запроса аналитики!")
    
    print("\n" + "=" * 80)
    print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
