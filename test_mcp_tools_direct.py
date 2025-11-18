"""
Прямой вызов MCP tool функций с логированием
Тестирование real-time логирования в MCP Monitor
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавить MCP server в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

# Импорт необходимых компонентов
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Импортируем функции напрямую из server.py
# Эти функции уже содержат log_mcp_execution внутри себя
from server import (
    perplexity_search,
    chain_of_thought_analysis,
    quick_reasoning_analysis,
    perplexity_analyze_crypto,
    perplexity_strategy_research
)


# Тестовые запросы для сложного анализа (sonar-pro)
COMPLEX_QUERIES = [
    "Какую торговую стратегию лучше использовать для Bitcoin в текущих рыночных условиях?",
    "Как оптимизировать параметры RSI стратегии для повышения Sharpe Ratio?",
    "Какие риски несет DCA стратегия при высокой волатильности?",
    "Разработай план для бэктестинга momentum стратегии на криптовалютах",
    "Какие индикаторы лучше всего работают в боковом тренде?"
]

# Тестовые запросы для быстрых ответов (sonar)
QUICK_QUERIES = [
    "Какой сейчас тренд у Bitcoin?",
    "Какие ключевые уровни поддержки/сопротивления у Ethereum?",
    "Что такое Sharpe Ratio простыми словами?",
    "Какой оптимальный период для EMA в дневном трейдинге?",
    "В чем разница между Mean Reversion и Trend Following стратегиями?"
]


async def run_complex_analysis():
    """Запустить 5 сложных анализов через Perplexity Sonar Pro"""
    print("=" * 80)
    print("🧠 СЛОЖНЫЙ АНАЛИЗ (Perplexity Sonar Pro) - 5 запросов")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(COMPLEX_QUERIES, 1):
        print(f"📝 Запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Вызываем функцию напрямую
            # Она содержит log_mcp_execution внутри себя!
            result = await perplexity_search(
                query=query,
                model="sonar-pro"
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем краткий результат
            preview = result[:200] if isinstance(result, str) else str(result)[:200]
            print(f"   ✅ Ответ получен за {elapsed:.1f}s")
            print(f"   📄 Превью: {preview}...")
            print()
            
            results.append({
                "query": query,
                "success": True,
                "time": elapsed,
                "preview": preview
            })
            
            # Небольшая пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ❌ Ошибка за {elapsed:.1f}s: {e}")
            print()
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })
    
    return results


async def run_quick_analysis():
    """Запустить 5 быстрых анализов через Perplexity Sonar"""
    print("=" * 80)
    print("⚡ БЫСТРЫЙ АНАЛИЗ (Perplexity Sonar) - 5 запросов")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(QUICK_QUERIES, 1):
        print(f"📝 Запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Вызываем функцию напрямую
            result = await perplexity_search(
                query=query,
                model="sonar"
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем краткий результат
            preview = result[:200] if isinstance(result, str) else str(result)[:200]
            print(f"   ✅ Ответ получен за {elapsed:.1f}s")
            print(f"   📄 Превью: {preview}...")
            print()
            
            results.append({
                "query": query,
                "success": True,
                "time": elapsed,
                "preview": preview
            })
            
            # Небольшая пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ❌ Ошибка за {elapsed:.1f}s: {e}")
            print()
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })
    
    return results


async def check_monitor_logs():
    """Проверить логи MCP Monitor"""
    print("=" * 80)
    print("📊 ПРОВЕРКА MCP MONITOR LOGS")
    print("=" * 80)
    print()
    
    log_file = project_root / "logs" / "mcp_activity.jsonl"
    
    if not log_file.exists():
        print("⚠️  Файл логов не найден")
        return
    
    # Читаем все записи
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"📝 Всего событий в логе: {len(lines)}")
    print(f"📌 Последние 20 событий:\n")
    
    import json
    
    # Статистика
    perplexity_calls = 0
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    error_count = 0
    
    for line in lines[-20:]:
        try:
            event = json.loads(line)
            
            timestamp = event.get("timestamp", "")[:19]  # Только дата и время
            api = event.get("api", "")
            tool = event.get("tool", "")
            status = event.get("status", "")
            duration = event.get("duration_ms", 0)
            tokens = event.get("tokens", 0)
            cost = event.get("cost", 0.0)
            
            # Подсчет
            if "Perplexity" in api or "perplexity" in tool:
                perplexity_calls += 1
            
            if status == "SUCCESS":
                success_count += 1
            else:
                error_count += 1
            
            total_tokens += tokens
            total_cost += cost
            
            # Форматированный вывод
            status_icon = "✅" if status == "SUCCESS" else "❌"
            print(f"  {status_icon} {timestamp} | {api}/{tool}")
            print(f"     Duration: {duration}ms | Tokens: {tokens} | Cost: ${cost:.6f}")
            print()
            
        except json.JSONDecodeError:
            continue
    
    print("─" * 80)
    print("📊 СТАТИСТИКА (последние 20 событий):")
    print(f"  Perplexity вызовов: {perplexity_calls}")
    print(f"  ✅ Успешных: {success_count}")
    print(f"  ❌ Ошибок: {error_count}")
    print(f"  Всего токенов: {total_tokens}")
    print(f"  Общая стоимость: ${total_cost:.6f}")
    print()


async def main():
    """Основная функция"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║  🧪 DIRECT MCP TOOLS CALL + ACTIVITY LOGGING TEST                       ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Сначала сложный анализ
    complex_results = await run_complex_analysis()
    
    print("\n⏸️  Пауза 3 секунды...\n")
    await asyncio.sleep(3)
    
    # Затем быстрый анализ
    quick_results = await run_quick_analysis()
    
    print("\n⏸️  Пауза 2 секунды перед проверкой логов...\n")
    await asyncio.sleep(2)
    
    # Проверка логов
    await check_monitor_logs()
    
    # Итоговая сводка
    print("=" * 80)
    print("🎊 ИТОГОВАЯ СВОДКА")
    print("=" * 80)
    print()
    
    complex_success = sum(1 for r in complex_results if r.get("success"))
    quick_success = sum(1 for r in quick_results if r.get("success"))
    
    print(f"Сложный анализ (Sonar Pro):")
    print(f"  ✅ Успешно: {complex_success}/5")
    print(f"  ❌ Ошибок: {5 - complex_success}/5")
    if complex_success > 0:
        avg_time = sum(r.get("time", 0) for r in complex_results if r.get("success")) / complex_success
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
    print()
    
    print(f"Быстрый анализ (Sonar):")
    print(f"  ✅ Успешно: {quick_success}/5")
    print(f"  ❌ Ошибок: {5 - quick_success}/5")
    if quick_success > 0:
        avg_time = sum(r.get("time", 0) for r in quick_results if r.get("success")) / quick_success
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
    print()
    
    print("=" * 80)
    print("✅ Тестирование завершено!")
    print("💡 Теперь запустите MCP Monitor для просмотра real-time событий:")
    print("   powershell -ExecutionPolicy Bypass -File scripts/mcp_monitor_simple_v2.ps1")
    print("=" * 80)
    print()


if __name__ == "__main__":
    asyncio.run(main())
