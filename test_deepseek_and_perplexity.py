"""
ПРАВИЛЬНЫЙ ТЕСТ: DeepSeek + Perplexity AI с раздельным логированием
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавить MCP server в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

# Импорты
from activity_logger import log_mcp_execution
from server import _call_deepseek_api, _call_perplexity_api


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТОВЫЕ ЗАПРОСЫ
# ═══════════════════════════════════════════════════════════════════════════

DEEPSEEK_QUERIES = [
    "Какую торговую стратегию лучше использовать для Bitcoin в текущих рыночных условиях?",
    "Как оптимизировать параметры RSI стратегии для повышения Sharpe Ratio?",
    "Какие риски несет DCA стратегия при высокой волатильности?",
    "Разработай план для бэктестинга momentum стратегии на криптовалютах",
    "Какие индикаторы лучше всего работают в боковом тренде?"
]

PERPLEXITY_QUERIES = [
    "Какой сейчас тренд у Bitcoin?",
    "Какие ключевые уровни поддержки/сопротивления у Ethereum?",
    "Что такое Sharpe Ratio простыми словами?",
    "Какой оптимальный период для EMA в дневном трейдинге?",
    "В чем разница между Mean Reversion и Trend Following стратегиями?"
]


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ DEEPSEEK
# ═══════════════════════════════════════════════════════════════════════════

async def test_deepseek_reasoning():
    """Тест DeepSeek с глубоким reasoning анализом"""
    print("=" * 80)
    print("🧠 DEEPSEEK REASONING ANALYSIS - 5 запросов")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(DEEPSEEK_QUERIES, 1):
        print(f"📝 DeepSeek запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Вручную логируем через log_mcp_execution
            async with log_mcp_execution("DeepSeek", "deepseek_reasoning_analysis") as logger:
                result = await _call_deepseek_api(query, model="deepseek-chat")
                
                # Извлекаем метрики для логирования
                if result.get("success"):
                    usage = result.get("usage", {})
                    logger.tokens = usage.get("total_tokens", 0)
                    # DeepSeek стоимость: ~$0.14 за 1M prompt tokens, ~$0.28 за 1M completion tokens
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    logger.cost = (prompt_tokens * 0.14 / 1_000_000) + (completion_tokens * 0.28 / 1_000_000)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем результат
            if result.get("success"):
                answer = result.get("answer", "")
                reasoning = result.get("reasoning", "")
                preview = answer[:200]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                
                print(f"   ✅ DeepSeek ответ получен за {elapsed:.1f}s")
                print(f"   📊 Tokens: {tokens}")
                if reasoning:
                    print(f"   🧠 Reasoning: {len(reasoning)} символов")
                print(f"   📄 Превью: {preview}...")
                print()
                
                results.append({
                    "query": query,
                    "success": True,
                    "time": elapsed,
                    "tokens": tokens
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


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ PERPLEXITY
# ═══════════════════════════════════════════════════════════════════════════

async def test_perplexity_sonar_pro():
    """Тест Perplexity AI Sonar Pro"""
    print("=" * 80)
    print("⚡ PERPLEXITY AI SONAR PRO - 5 запросов")
    print("=" * 80)
    print()
    
    results = []
    
    for i, query in enumerate(PERPLEXITY_QUERIES, 1):
        print(f"📝 Perplexity запрос {i}/5:")
        print(f"   {query}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Вручную логируем через log_mcp_execution
            async with log_mcp_execution("Perplexity", "perplexity_sonar_pro_analysis") as logger:
                result = await _call_perplexity_api(query, model="sonar-pro", use_cache=False)
                
                # Извлекаем метрики
                if result.get("success"):
                    usage = result.get("usage", {})
                    logger.tokens = usage.get("total_tokens", 0)
                    cost_data = usage.get("cost", {})
                    if isinstance(cost_data, dict):
                        logger.cost = cost_data.get("total_cost", 0.0)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Показываем результат
            if result.get("success"):
                answer = result.get("answer", "")
                preview = answer[:200]
                tokens = result.get("usage", {}).get("total_tokens", 0)
                
                print(f"   ✅ Perplexity ответ получен за {elapsed:.1f}s")
                print(f"   📊 Tokens: {tokens}")
                print(f"   📄 Превью: {preview}...")
                print()
                
                results.append({
                    "query": query,
                    "success": True,
                    "time": elapsed,
                    "tokens": tokens
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


# ═══════════════════════════════════════════════════════════════════════════
# ПРОВЕРКА ЛОГОВ
# ═══════════════════════════════════════════════════════════════════════════

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
    print(f"📌 Последние 25 событий:\n")
    
    import json
    
    # Статистика
    perplexity_calls = 0
    deepseek_calls = 0
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    error_count = 0
    
    for line in lines[-25:]:
        try:
            event = json.loads(line)
            
            timestamp = event.get("timestamp", "")[:19]
            api = event.get("api", "")
            tool = event.get("tool", "")
            status = event.get("status", "")
            duration = event.get("duration_ms", 0)
            tokens = event.get("tokens", 0)
            cost = event.get("cost", 0.0)
            
            # Подсчет
            if "Perplexity" in api:
                perplexity_calls += 1
            if "DeepSeek" in api:
                deepseek_calls += 1
            
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
    print("📊 СТАТИСТИКА (последние 25 событий):")
    print(f"  🟣 DeepSeek вызовов: {deepseek_calls}")
    print(f"  🔵 Perplexity вызовов: {perplexity_calls}")
    print(f"  ✅ Успешных: {success_count}")
    print(f"  ❌ Ошибок: {error_count}")
    print(f"  Всего токенов: {total_tokens}")
    print(f"  Общая стоимость: ${total_cost:.6f}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Основная функция"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║  🧪 DEEPSEEK vs PERPLEXITY AI - ПРАВИЛЬНЫЙ ТЕСТ                         ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Сначала DeepSeek
    print("🟣 ТЕСТИРУЕМ DEEPSEEK API\n")
    deepseek_results = await test_deepseek_reasoning()
    
    print("\n⏸️  Пауза 3 секунды...\n")
    await asyncio.sleep(3)
    
    # Затем Perplexity
    print("🔵 ТЕСТИРУЕМ PERPLEXITY API\n")
    perplexity_results = await test_perplexity_sonar_pro()
    
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
    
    print(f"🟣 DeepSeek Reasoning:")
    print(f"  ✅ Успешно: {deepseek_success}/5")
    print(f"  ❌ Ошибок: {5 - deepseek_success}/5")
    if deepseek_success > 0:
        avg_time = sum(r.get("time", 0) for r in deepseek_results if r.get("success")) / deepseek_success
        avg_tokens = sum(r.get("tokens", 0) for r in deepseek_results if r.get("success")) / deepseek_success
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
        print(f"  📊 Средние токены: {avg_tokens:.0f}")
    print()
    
    print(f"🔵 Perplexity AI Sonar Pro:")
    print(f"  ✅ Успешно: {perplexity_success}/5")
    print(f"  ❌ Ошибок: {5 - perplexity_success}/5")
    if perplexity_success > 0:
        avg_time = sum(r.get("time", 0) for r in perplexity_results if r.get("success")) / perplexity_success
        avg_tokens = sum(r.get("tokens", 0) for r in perplexity_results if r.get("success")) / perplexity_success
        print(f"  ⏱️  Среднее время: {avg_time:.1f}s")
        print(f"  📊 Средние токены: {avg_tokens:.0f}")
    print()
    
    print("=" * 80)
    print("✅ Тестирование завершено!")
    print()
    print("💡 Проверьте MCP Monitor:")
    print("   DeepSeek calls должно быть > 0")
    print("   Perplexity calls должно быть > 0")
    print()
    print("📝 Файл логов:")
    print("   logs/mcp_activity.jsonl")
    print("=" * 80)
    print()


if __name__ == "__main__":
    asyncio.run(main())
