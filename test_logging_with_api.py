"""
Тестирование логирования с реальными Perplexity API вызовами
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавить пути
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

# Импорты
from activity_logger import log_mcp_execution
from server import _call_perplexity_api, extract_metrics


# Тестовые запросы
COMPLEX_QUERIES = [
    "Какую торговую стратегию лучше использовать для Bitcoin в текущих рыночных условиях?",
    "Как оптимизировать параметры RSI стратегии для повышения Sharpe Ratio?",
    "Какие риски несет DCA стратегия при высокой волатильности?",
    "Разработай план для бэктестинга momentum стратегии на криптовалютах",
    "Какие индикаторы лучше всего работают в боковом тренде?"
]

QUICK_QUERIES = [
    "Какой сейчас тренд у Bitcoin?",
    "Какие ключевые уровни поддержки/сопротивления у Ethereum?",
    "Что такое Sharpe Ratio простыми словами?",
    "Какой оптимальный период для EMA в дневном трейдинге?",
    "В чем разница между Mean Reversion и Trend Following стратегиями?"
]


async def test_complex_analysis():
    """Тест сложных запросов с логированием"""
    print("=" * 80)
    print("🧠 СЛОЖНЫЙ АНАЛИЗ (Perplexity Sonar Pro) + Логирование - 5 запросов")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(COMPLEX_QUERIES, 1):
        print(f"📝 Запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Вручную используем log_mcp_execution
            async with log_mcp_execution("Perplexity", "test_complex_analysis") as logger:
                result = await _call_perplexity_api(query, model="sonar-pro")
                extract_metrics(result, logger)  # Извлекаем токены/стоимость
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем результат
            if result.get("success"):
                answer = result.get("answer", "")
                preview = answer[:200]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                cost = result.get("usage", {}).get("cost", {}).get("total_cost", 0.0)
                
                print(f"   ✅ Ответ получен за {elapsed:.1f}s")
                print(f"   📊 Tokens: {tokens} | Cost: ${cost:.6f}")
                print(f"   📄 Превью: {preview}...")
                print()
                
                results.append({
                    "query": query,
                    "success": True,
                    "time": elapsed,
                    "tokens": tokens,
                    "cost": cost
                })
            else:
                print(f"   ❌ Ошибка: {result.get('error')}")
                print()
                results.append({
                    "query": query,
                    "success": False,
                    "error": result.get('error')
                })
            
            # Пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ❌ Исключение за {elapsed:.1f}s: {e}")
            print()
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })
    
    return results


async def test_quick_analysis():
    """Тест быстрых запросов с логированием"""
    print("=" * 80)
    print("⚡ БЫСТРЫЙ АНАЛИЗ (Perplexity Sonar) + Логирование - 5 запросов")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(QUICK_QUERIES, 1):
        print(f"📝 Запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Вручную используем log_mcp_execution
            async with log_mcp_execution("Perplexity", "test_quick_analysis") as logger:
                result = await _call_perplexity_api(query, model="sonar")
                extract_metrics(result, logger)  # Извлекаем токены/стоимость
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем результат
            if result.get("success"):
                answer = result.get("answer", "")
                preview = answer[:200]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                cost = result.get("usage", {}).get("cost", {}).get("total_cost", 0.0)
                
                print(f"   ✅ Ответ получен за {elapsed:.1f}s")
                print(f"   📊 Tokens: {tokens} | Cost: ${cost:.6f}")
                print(f"   📄 Превью: {preview}...")
                print()
                
                results.append({
                    "query": query,
                    "success": True,
                    "time": elapsed,
                    "tokens": tokens,
                    "cost": cost
                })
            else:
                print(f"   ❌ Ошибка: {result.get('error')}")
                print()
                results.append({
                    "query": query,
                    "success": False,
                    "error": result.get('error')
                })
            
            # Пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ❌ Исключение за {elapsed:.1f}s: {e}")
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
    test_calls = 0
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
            if "Perplexity" in api:
                perplexity_calls += 1
            if "test_" in tool:
                test_calls += 1
            
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
    print(f"  Perplexity API вызовов: {perplexity_calls}")
    print(f"  Test вызовов: {test_calls}")
    print(f"  ✅ Успешных: {success_count}")
    print(f"  ❌ Ошибок: {error_count}")
    print(f"  Всего токенов: {total_tokens}")
    print(f"  Общая стоимость: ${total_cost:.6f}")
    print()


async def main():
    """Основная функция"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║  🧪 PERPLEXITY API + MANUAL ACTIVITY LOGGING TEST                       ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Сложный анализ
    complex_results = await test_complex_analysis()
    
    print("\n⏸️  Пауза 3 секунды...\n")
    await asyncio.sleep(3)
    
    # Быстрый анализ
    quick_results = await test_quick_analysis()
    
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
        avg_tokens = sum(r.get("tokens", 0) for r in complex_results if r.get("success")) / complex_success
        total_cost = sum(r.get("cost", 0) for r in complex_results if r.get("success"))
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
        print(f"  📊 Средние токены: {avg_tokens:.0f}")
        print(f"  💰 Общая стоимость: ${total_cost:.6f}")
    print()
    
    print(f"Быстрый анализ (Sonar):")
    print(f"  ✅ Успешно: {quick_success}/5")
    print(f"  ❌ Ошибок: {5 - quick_success}/5")
    if quick_success > 0:
        avg_time = sum(r.get("time", 0) for r in quick_results if r.get("success")) / quick_success
        avg_tokens = sum(r.get("tokens", 0) for r in quick_results if r.get("success")) / quick_success
        total_cost = sum(r.get("cost", 0) for r in quick_results if r.get("success"))
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
        print(f"  📊 Средние токены: {avg_tokens:.0f}")
        print(f"  💰 Общая стоимость: ${total_cost:.6f}")
    print()
    
    print("=" * 80)
    print("✅ Тестирование завершено!")
    print()
    print("💡 Запустите MCP Monitor для real-time просмотра:")
    print("   powershell -ExecutionPolicy Bypass -File scripts/mcp_monitor_simple_v2.ps1")
    print()
    print("📝 Файл логов:")
    print("   logs/mcp_activity.jsonl")
    print("=" * 80)
    print()


if __name__ == "__main__":
    asyncio.run(main())
