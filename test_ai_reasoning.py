"""
Тестовые запросы к DeepSeek и Perplexity AI
Проверка real-time логирования в MCP Monitor
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавить MCP server в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

# Импортируем внутренние функции напрямую
from server import perplexity_cache, _call_perplexity_api


# Тестовые запросы для DeepSeek (chain-of-thought)
DEEPSEEK_QUERIES = [
    "Какую торговую стратегию лучше использовать для Bitcoin в текущих рыночных условиях?",
    "Как оптимизировать параметры RSI стратегии для повышения Sharpe Ratio?",
    "Какие риски несет DCA стратегия при высокой волатильности?",
    "Разработай plan для бэктестинга momentum стратегии на криптовалютах",
    "Какие индикаторы лучше всего работают в боковом тренде?"
]

# Тестовые запросы для Perplexity (quick reasoning)
PERPLEXITY_QUERIES = [
    "Какой сейчас тренд у Bitcoin?",
    "Какие ключевые уровни поддержки/сопротивления у Ethereum?",
    "Что такое Sharpe Ratio простыми словами?",
    "Какой оптимальный период для EMA в дневном трейдинге?",
    "В чем разница между Mean Reversion и Trend Following стратегиями?"
]


async def run_deepseek_tests():
    """Выполнить 5 тестовых запросов к DeepSeek (используем Perplexity sonar-pro)"""
    print("=" * 80)
    print("🧠 CHAIN-OF-THOUGHT STYLE ANALYSIS via Perplexity Sonar Pro (5 запросов)")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(DEEPSEEK_QUERIES, 1):
        print(f"📝 Запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Используем Perplexity sonar-pro для глубокого анализа
            result = await _call_perplexity_api(query, model="sonar-pro")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем краткий результат
            if result.get("success"):
                answer = result.get("answer", "")
                preview = answer[:200]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                
                print(f"   ✅ Ответ получен за {elapsed:.1f}s")
                print(f"   📊 Tokens: {tokens}")
                print(f"   📄 Превью: {preview}...")
                print()
                
                results.append({
                    "query": query,
                    "success": True,
                    "time": elapsed,
                    "tokens": tokens,
                    "preview": preview
                })
            else:
                print(f"   ❌ Ошибка: {result.get('error')}")
                print()
                results.append({
                    "query": query,
                    "success": False,
                    "error": result.get('error')
                })
            
            # Небольшая пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
            print()
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })
    
    return results


async def run_perplexity_tests():
    """Выполнить 5 тестовых запросов к Perplexity AI Sonar (быстрая модель)"""
    print("=" * 80)
    print("⚡ PERPLEXITY AI SONAR (5 быстрых запросов)")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(PERPLEXITY_QUERIES, 1):
        print(f"📝 Запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Используем Perplexity sonar (быстрая модель)
            result = await _call_perplexity_api(query, model="sonar")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем краткий результат
            if result.get("success"):
                answer = result.get("answer", "")
                preview = answer[:200]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                
                print(f"   ✅ Ответ получен за {elapsed:.1f}s")
                print(f"   � Tokens: {tokens}")
                print(f"   �📄 Превью: {preview}...")
                print()
                
                results.append({
                    "query": query,
                    "success": True,
                    "time": elapsed,
                    "tokens": tokens,
                    "preview": preview
                })
            else:
                print(f"   ❌ Ошибка: {result.get('error')}")
                print()
                results.append({
                    "query": query,
                    "success": False,
                    "error": result.get('error')
                })
            
            # Небольшая пауза между запросами
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
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
    
    # Читаем последние 20 записей
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"📝 Всего событий в логе: {len(lines)}")
    print(f"📌 Последние 15 событий:\n")
    
    import json
    
    # Статистика
    deepseek_calls = 0
    perplexity_calls = 0
    total_tokens = 0
    total_cost = 0.0
    
    for line in lines[-15:]:
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
            if "chain_of_thought" in tool or "DeepSeek" in api:
                deepseek_calls += 1
            if "Perplexity" in api or "perplexity" in tool:
                perplexity_calls += 1
            
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
    print("📊 СТАТИСТИКА:")
    print(f"  DeepSeek вызовов: {deepseek_calls}")
    print(f"  Perplexity вызовов: {perplexity_calls}")
    print(f"  Всего токенов: {total_tokens}")
    print(f"  Общая стоимость: ${total_cost:.6f}")
    print()


async def main():
    """Основная функция"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║  🧪 ТЕСТИРОВАНИЕ DEEPSEEK И PERPLEXITY AI + MCP MONITOR                ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Сначала DeepSeek
    deepseek_results = await run_deepseek_tests()
    
    print("\n⏸️  Пауза 3 секунды...\n")
    await asyncio.sleep(3)
    
    # Затем Perplexity
    perplexity_results = await run_perplexity_tests()
    
    print("\n⏸️  Пауза 2 секунды перед проверкой логов...\n")
    await asyncio.sleep(2)
    
    # Проверка логов
    await check_monitor_logs()
    
    # Итоговая сводка
    print("=" * 80)
    print("🎊 ИТОГОВАЯ СВОДКА")
    print("=" * 80)
    print()
    
    deepseek_success = sum(1 for r in deepseek_results if r.get("success"))
    perplexity_success = sum(1 for r in perplexity_results if r.get("success"))
    
    print(f"DeepSeek Chain-of-Thought:")
    print(f"  ✅ Успешно: {deepseek_success}/5")
    print(f"  ❌ Ошибок: {5 - deepseek_success}/5")
    if deepseek_success > 0:
        avg_time = sum(r.get("time", 0) for r in deepseek_results if r.get("success")) / deepseek_success
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
    print()
    
    print(f"Perplexity AI Sonar Pro:")
    print(f"  ✅ Успешно: {perplexity_success}/5")
    print(f"  ❌ Ошибок: {5 - perplexity_success}/5")
    if perplexity_success > 0:
        avg_time = sum(r.get("time", 0) for r in perplexity_results if r.get("success")) / perplexity_success
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
