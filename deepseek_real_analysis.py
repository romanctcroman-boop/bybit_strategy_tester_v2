"""
Реальный анализ проекта через DeepSeek API
Отправляет запросы к DeepSeek для анализа кода и архитектуры
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import aiohttp
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

PROJECT_ROOT = Path(__file__).parent

# Import secure key manager
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from security.key_manager import get_decrypted_key

# Get API key securely
DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Результаты
RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "deepseek_requests": [],
    "analysis": {}
}


async def call_deepseek_api(prompt: str, model: str = "deepseek-chat") -> Dict[str, Any]:
    """
    Реальный запрос к DeepSeek API
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Ты - экспертный код-аналитик. Анализируй код детально и предоставляй конкретные рекомендации."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    print(f"\n{'='*80}")
    print(f"🤖 DeepSeek API Request")
    print(f"{'='*80}")
    print(f"Model: {model}")
    print(f"Prompt length: {len(prompt)} chars")
    print(f"{'='*80}\n")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    result = {
                        "status": "success",
                        "model": model,
                        "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                        "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                        "total_tokens": data.get("usage", {}).get("total_tokens", 0),
                        "response": data["choices"][0]["message"]["content"]
                    }
                    
                    print(f"✅ SUCCESS")
                    print(f"   Tokens used: {result['total_tokens']} (prompt: {result['prompt_tokens']}, completion: {result['completion_tokens']})")
                    print(f"   Response length: {len(result['response'])} chars")
                    
                    return result
                else:
                    error_text = await response.text()
                    print(f"❌ ERROR: {response.status}")
                    print(f"   {error_text}")
                    
                    return {
                        "status": "error",
                        "code": response.status,
                        "error": error_text
                    }
        except asyncio.TimeoutError:
            print(f"❌ TIMEOUT after 120 seconds")
            return {
                "status": "error",
                "error": "Request timeout"
            }
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }


async def analyze_architecture_with_deepseek() -> Dict[str, Any]:
    """
    Анализ архитектуры через DeepSeek API
    """
    print("\n" + "="*80)
    print("📘 АНАЛИЗ 1: Архитектура проекта")
    print("="*80 + "\n")
    
    # Читаем ключевые файлы архитектуры
    backend_main = PROJECT_ROOT / "backend" / "main.py"
    mcp_server = PROJECT_ROOT / "mcp-server" / "server.py"
    docker_compose = PROJECT_ROOT / "docker-compose.yml"
    
    architecture_code = ""
    
    if backend_main.exists():
        architecture_code += f"\n# backend/main.py\n{backend_main.read_text(encoding='utf-8')[:2000]}\n"
    
    if mcp_server.exists():
        architecture_code += f"\n# mcp-server/server.py\n{mcp_server.read_text(encoding='utf-8')[:2000]}\n"
    
    if docker_compose.exists():
        architecture_code += f"\n# docker-compose.yml\n{docker_compose.read_text(encoding='utf-8')[:1000]}\n"
    
    prompt = f"""Проанализируй архитектуру этого проекта торгового бота для Bybit.

Код проекта:
```
{architecture_code}
```

Технические требования из ТЗ:
1. JSON-RPC 2.0 на FastAPI/asyncio
2. Redis Streams для очередей задач
3. Workers с автоматическим масштабированием
4. Saga pattern для оркестрации
5. Docker изоляция

Проанализируй:
1. Соответствует ли архитектура требованиям ТЗ?
2. Какие критичные компоненты отсутствуют?
3. Какие есть проблемы в текущей реализации?
4. Конкретные рекомендации по улучшению (с примерами кода)

Будь конкретным и критичным. Формат: JSON с секциями compliance, missing_components, issues, recommendations."""
    
    result = await call_deepseek_api(prompt)
    RESULTS["deepseek_requests"].append({
        "type": "architecture_analysis",
        "timestamp": datetime.now().isoformat(),
        "result": result
    })
    
    return result


async def analyze_mcp_integration_with_deepseek() -> Dict[str, Any]:
    """
    Анализ MCP интеграции через DeepSeek API
    """
    print("\n" + "="*80)
    print("🤖 АНАЛИЗ 2: MCP Multi-Agent Integration")
    print("="*80 + "\n")
    
    # Читаем MCP server код
    mcp_server = PROJECT_ROOT / "mcp-server" / "server.py"
    mcp_orchestrator = PROJECT_ROOT / "mcp-server" / "orchestrator"
    
    mcp_code = ""
    
    if mcp_server.exists():
        mcp_code += f"\n# mcp-server/server.py\n{mcp_server.read_text(encoding='utf-8')[:3000]}\n"
    
    # Ищем файлы оркестратора
    if mcp_orchestrator.exists() and mcp_orchestrator.is_dir():
        for file in mcp_orchestrator.glob("*.py"):
            try:
                mcp_code += f"\n# {file.name}\n{file.read_text(encoding='utf-8')[:1500]}\n"
            except:
                pass
    
    prompt = f"""Проанализируй MCP (Model Context Protocol) интеграцию в этом проекте.

Код MCP сервера:
```
{mcp_code}
```

Требования из ТЗ-3:
1. Perplexity AI для reasoning (41 инструмент)
2. DeepSeek для code generation
3. AutoML для оптимизации стратегий
4. Оркестрация между агентами
5. Pipeline: Query → Reasoning → CodeGen → ML → Deploy

Проанализируй:
1. Правильно ли реализована интеграция с Perplexity?
2. Как работает chain-of-thought reasoning?
3. Есть ли проблемы в оркестрации агентов?
4. Какие улучшения нужны для production?

Конкретные рекомендации с примерами кода. Формат: JSON."""
    
    result = await call_deepseek_api(prompt)
    RESULTS["deepseek_requests"].append({
        "type": "mcp_integration_analysis",
        "timestamp": datetime.now().isoformat(),
        "result": result
    })
    
    return result


async def analyze_redis_streams_with_deepseek() -> Dict[str, Any]:
    """
    Анализ Redis Streams реализации через DeepSeek API
    """
    print("\n" + "="*80)
    print("🔴 АНАЛИЗ 3: Redis Streams Implementation")
    print("="*80 + "\n")
    
    # Ищем файлы с Redis
    redis_files = []
    for pattern in ["*redis*.py", "*queue*.py", "*task*.py"]:
        redis_files.extend(list((PROJECT_ROOT / "backend").rglob(pattern)))
    
    redis_code = ""
    for file in redis_files[:5]:  # Первые 5 файлов
        try:
            redis_code += f"\n# {file.name}\n{file.read_text(encoding='utf-8')[:1500]}\n"
        except:
            pass
    
    prompt = f"""Проанализируй реализацию Redis Streams для очереди задач.

Код Redis интеграции:
```
{redis_code}
```

Требования из ТЗ-1:
1. Stream: mcp_tasks с полями (priority, type, payload, time, agent)
2. Consumer Groups для распределённой обработки
3. XPENDING для recovery после сбоев
4. Checkpointing для длительных задач
5. Priority routing

Проанализируй:
1. Правильно ли используются Redis Streams команды?
2. Реализованы ли Consumer Groups?
3. Есть ли recovery механизм (XPENDING)?
4. Как обрабатывается приоритизация?
5. Критичные проблемы и их решения

Конкретные примеры кода для исправлений. Формат: JSON."""
    
    result = await call_deepseek_api(prompt)
    RESULTS["deepseek_requests"].append({
        "type": "redis_streams_analysis",
        "timestamp": datetime.now().isoformat(),
        "result": result
    })
    
    return result


async def analyze_autoscaling_with_deepseek() -> Dict[str, Any]:
    """
    Анализ autoscaling логики через DeepSeek API
    """
    print("\n" + "="*80)
    print("⚡ АНАЛИЗ 4: Autoscaling & Worker Management")
    print("="*80 + "\n")
    
    # Ищем файлы с workers
    worker_files = []
    for pattern in ["*worker*.py", "*scale*.py", "*celery*.py"]:
        worker_files.extend(list((PROJECT_ROOT / "backend").rglob(pattern)))
    
    worker_code = ""
    for file in worker_files[:3]:
        try:
            worker_code += f"\n# {file.name}\n{file.read_text(encoding='utf-8')[:2000]}\n"
        except:
            pass
    
    # Добавляем monitoring
    monitoring = PROJECT_ROOT / "monitoring_prometheus.py"
    if monitoring.exists():
        worker_code += f"\n# monitoring_prometheus.py\n{monitoring.read_text(encoding='utf-8')[:1500]}\n"
    
    prompt = f"""Проанализируй систему автоматического масштабирования workers.

Код worker management:
```
{worker_code}
```

Требования из ТЗ-1:
1. MinWorkers=2, MaxWorkers=10
2. SLA-driven scaling (queue depth, latency)
3. Автоматический spawn/kill workers
4. Graceful shutdown
5. Health checks

Проанализируй:
1. Реализовано ли автоматическое масштабирование?
2. Как SLA metrics влияют на scaling решения?
3. Есть ли graceful shutdown?
4. Критичные проблемы в текущей реализации
5. Конкретный код для автомасштабирования

Детальные примеры кода. Формат: JSON."""
    
    result = await call_deepseek_api(prompt)
    RESULTS["deepseek_requests"].append({
        "type": "autoscaling_analysis",
        "timestamp": datetime.now().isoformat(),
        "result": result
    })
    
    return result


async def generate_implementation_plan_with_deepseek() -> Dict[str, Any]:
    """
    Генерация плана реализации через DeepSeek API
    """
    print("\n" + "="*80)
    print("📋 АНАЛИЗ 5: Implementation Plan Generation")
    print("="*80 + "\n")
    
    # Собираем summary предыдущих анализов
    architecture_issues = ""
    if RESULTS["deepseek_requests"]:
        for req in RESULTS["deepseek_requests"]:
            if req["result"].get("status") == "success":
                architecture_issues += f"\n{req['type']}: Проблемы найдены\n"
    
    prompt = f"""На основе проведённого анализа проекта, создай детальный план реализации недостающих компонентов.

Найденные проблемы:
{architecture_issues}

Критичные требования из ТЗ:
1. JSON-RPC 2.0 endpoints: /run_task, /status, /analytics, /inject, /control
2. Автоматическое масштабирование workers (SLA-driven)
3. Tenant isolation для multi-tenancy
4. Улучшение MCP оркестрации

Создай:
1. Приоритизированный список задач (критично/важно/желательно)
2. Оценки времени для каждой задачи
3. Конкретные файлы для создания/изменения
4. Примеры кода для ключевых компонентов
5. План тестирования

Формат: Подробный JSON с секциями tasks, timeline, code_examples, testing_plan."""
    
    result = await call_deepseek_api(prompt, model="deepseek-chat")
    RESULTS["deepseek_requests"].append({
        "type": "implementation_plan",
        "timestamp": datetime.now().isoformat(),
        "result": result
    })
    
    return result


async def main():
    """
    Главная функция - запускает все анализы через DeepSeek API
    """
    print("\n" + "="*80)
    print("🚀 DEEPSEEK REAL API ANALYSIS")
    print("="*80)
    print(f"API Key: {DEEPSEEK_API_KEY[:20]}...")
    print(f"Project: {PROJECT_ROOT}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    if not DEEPSEEK_API_KEY:
        print("❌ ERROR: DEEPSEEK_API_KEY not found in .env")
        return
    
    try:
        # Запускаем анализы последовательно
        print("📊 Запуск 5 DeepSeek API анализов...\n")
        
        # 1. Архитектура
        arch_result = await analyze_architecture_with_deepseek()
        RESULTS["analysis"]["architecture"] = arch_result
        await asyncio.sleep(2)  # Rate limiting
        
        # 2. MCP Integration
        mcp_result = await analyze_mcp_integration_with_deepseek()
        RESULTS["analysis"]["mcp_integration"] = mcp_result
        await asyncio.sleep(2)
        
        # 3. Redis Streams
        redis_result = await analyze_redis_streams_with_deepseek()
        RESULTS["analysis"]["redis_streams"] = redis_result
        await asyncio.sleep(2)
        
        # 4. Autoscaling
        autoscale_result = await analyze_autoscaling_with_deepseek()
        RESULTS["analysis"]["autoscaling"] = autoscale_result
        await asyncio.sleep(2)
        
        # 5. Implementation Plan
        plan_result = await generate_implementation_plan_with_deepseek()
        RESULTS["analysis"]["implementation_plan"] = plan_result
        
        # Сохраняем полные результаты
        output_file = PROJECT_ROOT / "DEEPSEEK_REAL_API_RESULTS.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(RESULTS, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*80)
        print("✅ ВСЕ АНАЛИЗЫ ЗАВЕРШЕНЫ")
        print("="*80)
        print(f"\nОтправлено запросов к DeepSeek API: {len(RESULTS['deepseek_requests'])}")
        
        # Считаем токены
        total_tokens = 0
        for req in RESULTS["deepseek_requests"]:
            if req["result"].get("status") == "success":
                total_tokens += req["result"].get("total_tokens", 0)
        
        print(f"Использовано токенов: {total_tokens}")
        print(f"Результаты сохранены: {output_file}")
        
        # Создаём markdown отчёт
        await create_markdown_report()
        
        print("\n🎉 ГОТОВО!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


async def create_markdown_report():
    """
    Создаёт markdown отчёт из результатов DeepSeek
    """
    print("\n📝 Создание markdown отчёта...")
    
    report = f"""# 🤖 DeepSeek Real API Analysis Report

**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**API:** DeepSeek Chat API  
**Запросов:** {len(RESULTS['deepseek_requests'])}

---

## 📊 Отправленные Запросы

"""
    
    for i, req in enumerate(RESULTS["deepseek_requests"], 1):
        report += f"\n### {i}. {req['type'].replace('_', ' ').title()}\n\n"
        
        if req["result"].get("status") == "success":
            report += f"**Статус:** ✅ SUCCESS  \n"
            report += f"**Токены:** {req['result'].get('total_tokens', 0)}  \n"
            report += f"**Время:** {req['timestamp']}  \n\n"
            report += f"**Ответ DeepSeek:**\n\n"
            report += f"```\n{req['result']['response'][:1000]}...\n```\n\n"
        else:
            report += f"**Статус:** ❌ ERROR  \n"
            report += f"**Ошибка:** {req['result'].get('error', 'Unknown')}  \n\n"
    
    report += f"""
---

## 🎯 Итоговая Статистика

- **Успешных запросов:** {sum(1 for r in RESULTS['deepseek_requests'] if r['result'].get('status') == 'success')}
- **Ошибок:** {sum(1 for r in RESULTS['deepseek_requests'] if r['result'].get('status') == 'error')}
- **Всего токенов:** {sum(r['result'].get('total_tokens', 0) for r in RESULTS['deepseek_requests'] if r['result'].get('status') == 'success')}

---

*Сгенерировано автоматически через DeepSeek API*
"""
    
    report_file = PROJECT_ROOT / "DEEPSEEK_REAL_API_REPORT.md"
    report_file.write_text(report, encoding='utf-8')
    print(f"✅ Отчёт сохранён: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
