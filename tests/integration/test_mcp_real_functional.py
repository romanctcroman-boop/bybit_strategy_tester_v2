"""
РЕАЛЬНЫЕ ФУНКЦИОНАЛЬНЫЕ ТЕСТЫ MCP ИНСТРУМЕНТОВ
Используют настоящие вызовы Perplexity API для 100% честного тестирования

⚠️ ВНИМАНИЕ: Эти тесты стоят денег (~$0.20-0.30 за полный прогон)
"""

import pytest
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем путь к MCP серверу
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "mcp-server"))

from server import (
    # Новые расширенные инструменты
    analyze_backtest_results,
    compare_strategies,
    risk_management_advice,
    technical_indicator_research,
    explain_metric,
    market_regime_detection,
    code_review_strategy,
    generate_test_scenarios,
    # Базовые для проверки
    perplexity_search
)


# ═══════════════════════════════════════════════════════════════════════════
# РЕАЛЬНЫЕ ФУНКЦИОНАЛЬНЫЕ ТЕСТЫ С PERPLEXITY API
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.slow
async def test_analyze_backtest_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Анализ бэктеста с настоящим Perplexity API
    Проверяем, что AI даёт осмысленные рекомендации
    """
    print("\n🔍 Тест 1/8: analyze_backtest_results (REAL API)")
    
    result = await analyze_backtest_results.fn(backtest_id=1, detailed=True)
    
    # Проверяем структуру
    assert result is not None
    assert isinstance(result, dict)
    assert "success" in result
    
    # Если API успешен, проверяем качество ответа
    if result.get("success"):
        assert "answer" in result
        assert len(result["answer"]) > 50, "Ответ слишком короткий"
        
        # Проверяем наличие ключевых терминов в анализе
        answer_lower = result["answer"].lower()
        key_terms = ["sharpe", "return", "drawdown", "strategy", "risk"]
        found_terms = [term for term in key_terms if term in answer_lower]
        
        assert len(found_terms) >= 2, f"Недостаточно аналитики. Найдено терминов: {found_terms}"
        
        print(f"  ✅ SUCCESS: Анализ содержит {len(found_terms)} ключевых терминов")
        print(f"  📊 Метрики бэктеста: {result.get('metrics', {})}")
        print(f"  📝 Длина ответа: {len(result['answer'])} символов")
    else:
        pytest.fail(f"API вернул ошибку: {result.get('error', 'Unknown')}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_compare_strategies_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Сравнение стратегий
    Проверяем качество сравнительного анализа
    """
    print("\n⚖️  Тест 2/8: compare_strategies (REAL API)")
    
    result = await compare_strategies(
        strategy_a="EMA Crossover",
        strategy_b="RSI Mean Reversion",
        market_type="crypto"
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    assert len(result["answer"]) > 100
    
    # Проверяем, что обе стратегии упомянуты
    answer = result["answer"].lower()
    assert "ema" in answer or "crossover" in answer
    assert "rsi" in answer or "mean" in answer or "reversion" in answer
    
    # Проверяем наличие сравнительного анализа
    comparison_words = ["better", "worse", "advantage", "disadvantage", "pros", "cons", "compare"]
    has_comparison = any(word in answer for word in comparison_words)
    assert has_comparison, "Нет сравнительного анализа"
    
    print(f"  ✅ SUCCESS: Качественное сравнение двух стратегий")
    print(f"  📝 Длина анализа: {len(result['answer'])} символов")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_risk_management_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Рекомендации по риск-менеджменту
    Проверяем конкретность рекомендаций
    """
    print("\n💰 Тест 3/8: risk_management_advice (REAL API)")
    
    result = await risk_management_advice(
        capital=10000.0,
        risk_per_trade=2.0,
        max_positions=3
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    
    # Проверяем наличие конкретных рекомендаций
    answer = result["answer"].lower()
    risk_terms = ["position size", "stop loss", "risk", "capital", "leverage"]
    found_terms = [term for term in risk_terms if term in answer]
    
    assert len(found_terms) >= 2, f"Недостаточно риск-терминов: {found_terms}"
    
    print(f"  ✅ SUCCESS: Рекомендации содержат {len(found_terms)} риск-терминов")
    print(f"  💵 Капитал: ${result['capital']:,.2f}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_technical_indicator_research_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Исследование технического индикатора
    Проверяем наличие формул и практических советов
    """
    print("\n📚 Тест 4/8: technical_indicator_research (REAL API)")
    
    result = await technical_indicator_research(
        indicator_name="MACD",
        use_case="trend-following"
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    
    # Проверяем наличие технической информации
    answer = result["answer"].lower()
    tech_terms = ["formula", "period", "parameter", "signal", "calculate"]
    found_terms = [term for term in tech_terms if term in answer]
    
    assert len(found_terms) >= 2, f"Недостаточно технической информации: {found_terms}"
    
    print(f"  ✅ SUCCESS: Исследование содержит {len(found_terms)} технических терминов")
    print(f"  📖 Индикатор: {result['indicator_name']}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_explain_metric_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Объяснение метрики
    Проверяем наличие формулы и интерпретации
    """
    print("\n📊 Тест 5/8: explain_metric (REAL API)")
    
    result = await explain_metric(
        metric_name="Sharpe Ratio",
        context="crypto_trading"
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    
    # Проверяем качество объяснения
    answer = result["answer"].lower()
    explanation_terms = ["formula", "calculate", "measure", "risk", "return"]
    found_terms = [term for term in explanation_terms if term in answer]
    
    assert len(found_terms) >= 2, f"Недостаточно объяснений: {found_terms}"
    
    print(f"  ✅ SUCCESS: Объяснение содержит {len(found_terms)} ключевых терминов")
    print(f"  📈 Метрика: {result['metric_name']}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_market_regime_detection_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Определение рыночного режима
    Проверяем актуальность анализа
    """
    print("\n📈 Тест 6/8: market_regime_detection (REAL API)")
    
    result = await market_regime_detection(
        symbol="BTCUSDT",
        timeframe="1d"
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    
    # Проверяем наличие анализа рынка
    answer = result["answer"].lower()
    market_terms = ["trend", "volatility", "volume", "support", "resistance", "regime"]
    found_terms = [term for term in market_terms if term in answer]
    
    assert len(found_terms) >= 2, f"Недостаточно рыночного анализа: {found_terms}"
    
    print(f"  ✅ SUCCESS: Анализ содержит {len(found_terms)} рыночных терминов")
    print(f"  💹 Символ: {result['symbol']} ({result['timeframe']})")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_code_review_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Code review стратегии
    Проверяем качество code review
    """
    print("\n💻 Тест 7/8: code_review_strategy (REAL API)")
    
    code = """
def ema_crossover_strategy(data):
    data['ema_fast'] = data['close'].ewm(span=12).mean()
    data['ema_slow'] = data['close'].ewm(span=26).mean()
    data['signal'] = 0
    data.loc[data['ema_fast'] > data['ema_slow'], 'signal'] = 1
    data.loc[data['ema_fast'] < data['ema_slow'], 'signal'] = -1
    return data
    """
    
    result = await code_review_strategy(
        strategy_code=code,
        language="python"
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    
    # Проверяем качество code review
    answer = result["answer"].lower()
    review_terms = ["code", "function", "logic", "improve", "error", "bug", "optimize"]
    found_terms = [term for term in review_terms if term in answer]
    
    assert len(found_terms) >= 2, f"Недостаточно code review: {found_terms}"
    
    print(f"  ✅ SUCCESS: Code review содержит {len(found_terms)} критериев")
    print(f"  📝 Код: {result['code_length']} символов")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_generate_test_scenarios_real_api():
    """
    РЕАЛЬНЫЙ ТЕСТ: Генерация тестовых сценариев
    Проверяем полноту и практичность сценариев
    """
    print("\n🧪 Тест 8/8: generate_test_scenarios (REAL API)")
    
    result = await generate_test_scenarios(
        strategy_name="Bollinger Bands Breakout",
        complexity="comprehensive"
    )
    
    assert result.get("success"), f"API error: {result.get('error')}"
    assert "answer" in result
    
    # Проверяем наличие тестовых сценариев
    answer = result["answer"].lower()
    test_terms = ["test", "scenario", "case", "unit", "integration", "edge"]
    found_terms = [term for term in test_terms if term in answer]
    
    assert len(found_terms) >= 3, f"Недостаточно тестовых сценариев: {found_terms}"
    
    print(f"  ✅ SUCCESS: Сгенерировано {len(found_terms)} типов тестов")
    print(f"  🎯 Стратегия: {result['strategy_name']}")


# ═══════════════════════════════════════════════════════════════════════════
# КОМПЛЕКСНЫЙ ТЕСТ ВСЕХ 8 ИНСТРУМЕНТОВ
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.slow
async def test_all_advanced_tools_functional():
    """
    КОМПЛЕКСНЫЙ ФУНКЦИОНАЛЬНЫЙ ТЕСТ
    Запускает все 8 инструментов последовательно и собирает статистику
    """
    print("\n" + "="*80)
    print("КОМПЛЕКСНЫЙ ФУНКЦИОНАЛЬНЫЙ ТЕСТ ВСЕХ 8 MCP ИНСТРУМЕНТОВ")
    print("="*80)
    
    tools = [
        ("analyze_backtest_results", analyze_backtest_results.fn, {"backtest_id": 1}),
        ("compare_strategies", compare_strategies.fn, {
            "strategy_a": "Grid Trading",
            "strategy_b": "DCA Bot",
            "market_type": "crypto"
        }),
        ("risk_management_advice", risk_management_advice.fn, {
            "capital": 50000.0,
            "risk_per_trade": 1.5
        }),
        ("technical_indicator_research", technical_indicator_research.fn, {
            "indicator_name": "RSI",
            "use_case": "mean-reversion"
        }),
        ("explain_metric", explain_metric.fn, {
            "metric_name": "Maximum Drawdown",
            "context": "risk_assessment"
        }),
        ("market_regime_detection", market_regime_detection.fn, {
            "symbol": "ETHUSDT",
            "timeframe": "4h"
        }),
        ("code_review_strategy", code_review_strategy.fn, {
            "strategy_code": "# Simple momentum\nif momentum > 0: buy()",
            "language": "python"
        }),
        ("generate_test_scenarios", generate_test_scenarios.fn, {
            "strategy_name": "VWAP Reversion",
            "complexity": "basic"
        })
    ]
    
    results = []
    total_tokens = 0
    start_time = datetime.now()
    
    for i, (name, func, args) in enumerate(tools, 1):
        print(f"\n[{i}/8] Тестирование: {name}")
        
        try:
            result = await func(**args)
            
            success = result.get("success", False)
            answer_len = len(result.get("answer", "")) if "answer" in result else 0
            tokens = result.get("usage", {}).get("total_tokens", 0)
            total_tokens += tokens
            
            results.append({
                "tool": name,
                "success": success,
                "answer_length": answer_len,
                "tokens": tokens
            })
            
            if success:
                print(f"  ✅ SUCCESS: {answer_len} символов, {tokens} токенов")
            else:
                print(f"  ❌ FAILED: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ EXCEPTION: {str(e)}")
            results.append({
                "tool": name,
                "success": False,
                "error": str(e)
            })
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Сохраняем результаты
    output_dir = project_root / "results" / "mcp_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "test_date": datetime.now().isoformat(),
        "test_type": "real_functional_api",
        "duration_seconds": duration,
        "total_tokens": total_tokens,
        "results": results,
        "summary": {
            "total_tools": len(tools),
            "successful": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "success_rate": f"{sum(1 for r in results if r.get('success')) / len(tools) * 100:.1f}%"
        }
    }
    
    with open(output_dir / "functional_test_report.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Печатаем итоговую статистику
    print("\n" + "="*80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("="*80)
    print(f"Всего инструментов: {len(tools)}")
    print(f"✅ Успешно: {report['summary']['successful']}")
    print(f"❌ Ошибок: {report['summary']['failed']}")
    print(f"📊 Success Rate: {report['summary']['success_rate']}")
    print(f"⏱️  Время выполнения: {duration:.2f}s")
    print(f"🪙 Всего токенов: {total_tokens}")
    print(f"💰 Примерная стоимость: ${total_tokens * 0.00001:.4f}")
    print("="*80)
    
    # Проверяем, что минимум 75% инструментов работают
    success_rate = sum(1 for r in results if r.get("success")) / len(tools)
    assert success_rate >= 0.75, f"Слишком низкий success rate: {success_rate*100:.1f}%"
    
    print("\n✅ КОМПЛЕКСНЫЙ ТЕСТ ПРОЙДЕН!")


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТ КАЧЕСТВА ОТВЕТОВ
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.slow
async def test_answer_quality_metrics():
    """
    Тест качества ответов от Perplexity AI
    Проверяем, что ответы содержательные и полезные
    """
    print("\n📊 Тест качества ответов Perplexity AI")
    
    # Тестируем на простом запросе
    result = await perplexity_search(
        "What is the optimal RSI period for crypto day trading?",
        model="sonar"
    )
    
    assert result.get("success"), "Базовый поиск не работает"
    
    answer = result.get("answer", "")
    
    # Проверки качества
    quality_checks = {
        "min_length": len(answer) >= 100,
        "has_numbers": any(char.isdigit() for char in answer),
        "has_technical_term": any(term in answer.lower() for term in ["rsi", "period", "day", "trading"]),
        "not_error": "error" not in answer.lower() or "sorry" not in answer.lower(),
        "has_sources": "sources" in result and len(result.get("sources", [])) > 0
    }
    
    passed_checks = sum(quality_checks.values())
    total_checks = len(quality_checks)
    
    print(f"  Проверок пройдено: {passed_checks}/{total_checks}")
    for check, status in quality_checks.items():
        print(f"    {'✅' if status else '❌'} {check}")
    
    assert passed_checks >= total_checks * 0.8, f"Качество ответа недостаточное: {passed_checks}/{total_checks}"


if __name__ == "__main__":
    """Запуск функциональных тестов напрямую"""
    
    print("⚠️  ВНИМАНИЕ: Эти тесты используют реальный Perplexity API")
    print("💰 Стоимость: ~$0.20-0.30 за полный прогон")
    print("\nЗапуск через 3 секунды...\n")
    
    import time
    time.sleep(3)
    
    # Запускаем комплексный тест
    asyncio.run(test_all_advanced_tools_functional())
    
    print("\n✅ Все функциональные тесты завершены!")
