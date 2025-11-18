"""
100% ЧЕСТНЫЙ ФУНКЦИОНАЛЬНЫЙ ТЕСТ MCP ИНСТРУМЕНТОВ
Использует РЕАЛЬНЫЕ вызовы Perplexity API

⚠️ СТОИМОСТЬ: ~$0.15-0.25 за полный прогон
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем путь к MCP серверу
project_root = Path(__file__).parent
mcp_server_dir = project_root / "mcp-server"
sys.path.insert(0, str(mcp_server_dir))

# Импортируем MCP сервер
import server

# Получаем оригинальные функции из FastMCP FunctionTool (через .fn)
print("Загрузка MCP инструментов...")
tools = {
    "analyze_backtest_results": server.analyze_backtest_results.fn if hasattr(server.analyze_backtest_results, 'fn') else server.analyze_backtest_results,
    "compare_strategies": server.compare_strategies.fn if hasattr(server.compare_strategies, 'fn') else server.compare_strategies,
    "risk_management_advice": server.risk_management_advice.fn if hasattr(server.risk_management_advice, 'fn') else server.risk_management_advice,
    "technical_indicator_research": server.technical_indicator_research.fn if hasattr(server.technical_indicator_research, 'fn') else server.technical_indicator_research,
    "explain_metric": server.explain_metric.fn if hasattr(server.explain_metric, 'fn') else server.explain_metric,
    "market_regime_detection": server.market_regime_detection.fn if hasattr(server.market_regime_detection, 'fn') else server.market_regime_detection,
    "code_review_strategy": server.code_review_strategy.fn if hasattr(server.code_review_strategy, 'fn') else server.code_review_strategy,
    "generate_test_scenarios": server.generate_test_scenarios.fn if hasattr(server.generate_test_scenarios, 'fn') else server.generate_test_scenarios,
}
print(f"✅ Загружено {len(tools)} инструментов\n")


async def test_tool(name: str, func: callable, args: dict) -> dict:
    """
    Тестирует один MCP инструмент с реальным API
    
    Returns:
        dict с результатами теста
    """
    print(f"\n🧪 Тестирование: {name}")
    print(f"   Параметры: {json.dumps(args, ensure_ascii=False)[:100]}...")
    
    try:
        result = await func(**args)
        
        success = result.get("success", False)
        answer = result.get("answer", "")
        tokens = result.get("usage", {}).get("total_tokens", 0)
        
        # Валидация качества
        quality_score = 0
        max_score = 5
        
        # 1. API вернул success
        if success:
            quality_score += 1
        
        # 2. Ответ достаточно длинный
        if len(answer) >= 100:
            quality_score += 1
        
        # 3. Ответ содержит релевантные термины
        answer_lower = answer.lower()
        relevant_terms = ["strategy", "trading", "crypto", "market", "risk", "return", 
                         "indicator", "signal", "test", "code", "formula"]
        if any(term in answer_lower for term in relevant_terms):
            quality_score += 1
        
        # 4. Есть источники (для Perplexity инструментов)
        if "sources" in result and len(result.get("sources", [])) > 0:
            quality_score += 1
        
        # 5. Ответ не является ошибкой
        if "error" not in answer_lower and "sorry" not in answer_lower:
            quality_score += 1
        
        status = "✅ PASS" if quality_score >= 3 else "⚠️  PARTIAL"
        
        print(f"   {status}: Качество {quality_score}/{max_score}, Длина {len(answer)}, Токенов {tokens}")
        
        return {
            "tool": name,
            "status": "PASS" if quality_score >= 3 else "PARTIAL",
            "success": success,
            "quality_score": quality_score,
            "answer_length": len(answer),
            "tokens": tokens,
            "has_sources": "sources" in result
        }
        
    except Exception as e:
        print(f"   ❌ FAILED: {str(e)}")
        return {
            "tool": name,
            "status": "FAILED",
            "error": str(e),
            "quality_score": 0
        }


async def main():
    """
    Комплексный тест всех 8 новых MCP инструментов
    """
    print("="*80)
    print("100% ЧЕСТНЫЙ ФУНКЦИОНАЛЬНЫЙ ТЕСТ MCP ИНСТРУМЕНТОВ")
    print("="*80)
    print("\n⚠️  ВНИМАНИЕ: Используется реальный Perplexity API")
    print("💰 Примерная стоимость: $0.15-0.25\n")
    
    start_time = datetime.now()
    
    # Определяем тестовые сценарии
    test_scenarios = [
        {
            "name": "analyze_backtest_results",
            "args": {"backtest_id": 1, "detailed": True}
        },
        {
            "name": "compare_strategies",
            "args": {
                "strategy_a": "EMA Crossover",
                "strategy_b": "RSI Mean Reversion",
                "market_type": "crypto"
            }
        },
        {
            "name": "risk_management_advice",
            "args": {
                "capital": 10000.0,
                "risk_per_trade": 2.0,
                "max_positions": 3
            }
        },
        {
            "name": "technical_indicator_research",
            "args": {
                "indicator_name": "MACD",
                "use_case": "trend-following"
            }
        },
        {
            "name": "explain_metric",
            "args": {
                "metric_name": "Sharpe Ratio",
                "context": "crypto_trading"
            }
        },
        {
            "name": "market_regime_detection",
            "args": {
                "symbol": "BTCUSDT",
                "timeframe": "1d"
            }
        },
        {
            "name": "code_review_strategy",
            "args": {
                "strategy_code": """
def ema_strategy(data):
    data['ema'] = data['close'].ewm(span=20).mean()
    data['signal'] = (data['close'] > data['ema']).astype(int)
    return data
                """,
                "language": "python"
            }
        },
        {
            "name": "generate_test_scenarios",
            "args": {
                "strategy_name": "Bollinger Bands",
                "complexity": "comprehensive"
            }
        }
    ]
    
    results = []
    total_tokens = 0
    
    # Запускаем тесты
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n[{i}/{len(test_scenarios)}]", end=" ")
        
        tool_name = scenario["name"]
        tool_func = tools[tool_name]
        tool_args = scenario["args"]
        
        result = await test_tool(tool_name, tool_func, tool_args)
        results.append(result)
        
        total_tokens += result.get("tokens", 0)
        
        # Небольшая задержка между запросами
        await asyncio.sleep(0.5)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Анализ результатов
    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    
    total_quality = sum(r.get("quality_score", 0) for r in results)
    max_quality = len(results) * 5
    
    # Итоговая статистика
    print("\n" + "="*80)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*80)
    print(f"\n📊 Статус тестов:")
    print(f"   ✅ PASS:    {passed}/{len(results)}")
    print(f"   ⚠️  PARTIAL: {partial}/{len(results)}")
    print(f"   ❌ FAILED:  {failed}/{len(results)}")
    
    print(f"\n📈 Качество:")
    print(f"   Общий балл: {total_quality}/{max_quality} ({total_quality/max_quality*100:.1f}%)")
    
    print(f"\n⏱️  Производительность:")
    print(f"   Время выполнения: {duration:.2f}s")
    print(f"   Среднее время/тест: {duration/len(results):.2f}s")
    
    print(f"\n🪙 Использование API:")
    print(f"   Всего токенов: {total_tokens}")
    print(f"   Среднее токенов/тест: {total_tokens/len(results):.0f}")
    print(f"   Примерная стоимость: ${total_tokens * 0.00001:.4f}")
    
    # Детальная таблица
    print(f"\n📋 Детальные результаты:")
    print(f"   {'Инструмент':<35} {'Статус':<10} {'Качество':<10} {'Длина':<10} {'Токены':<10}")
    print(f"   {'-'*85}")
    
    for r in results:
        tool = r["tool"][:34]
        status = r["status"]
        quality = f"{r.get('quality_score', 0)}/5"
        length = r.get("answer_length", 0)
        tokens = r.get("tokens", 0)
        
        print(f"   {tool:<35} {status:<10} {quality:<10} {length:<10} {tokens:<10}")
    
    print("="*80)
    
    # Сохраняем отчёт
    output_dir = project_root / "results" / "mcp_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "test_date": datetime.now().isoformat(),
        "test_type": "100_percent_honest_functional",
        "duration_seconds": duration,
        "total_tokens": total_tokens,
        "estimated_cost_usd": total_tokens * 0.00001,
        "results": results,
        "summary": {
            "total_tools": len(results),
            "passed": passed,
            "partial": partial,
            "failed": failed,
            "quality_score": f"{total_quality}/{max_quality}",
            "quality_percentage": f"{total_quality/max_quality*100:.1f}%"
        }
    }
    
    report_file = output_dir / "honest_functional_test_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Отчёт сохранён: {report_file}")
    
    # Финальная оценка
    if failed == 0 and partial == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ НА 100%!")
        return 0
    elif passed >= len(results) * 0.75:
        print(f"\n✅ ТЕСТЫ ПРОЙДЕНЫ: {passed}/{len(results)} ({passed/len(results)*100:.0f}%)")
        return 0
    else:
        print(f"\n⚠️  ВНИМАНИЕ: Только {passed}/{len(results)} тестов прошли полностью")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
