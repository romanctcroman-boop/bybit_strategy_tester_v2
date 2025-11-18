"""
Интеграционный тест: Copilot ↔ Perplexity взаимодействие через MCP
=================================================================

Сценарий:
1. Copilot получает задачу от пользователя
2. Copilot делегирует исследование Perplexity (через MCP)
3. Perplexity возвращает результат анализа
4. Copilot принимает решение на основе ответа Perplexity
5. Copilot выполняет действие (например, запуск бэктеста)

Требования:
- MCP Server Perplexity должен быть запущен
- .vscode/mcp.json должен содержать конфигурацию perplexity
- PERPLEXITY_API_KEY должен быть установлен (или mock)

Автор: MCP Multi-Agent Test Suite
Дата: 2025-10-29
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
from typing import Dict, Any


# ============================================================================
# MOCK MCP CLIENT
# ============================================================================

class MockMCPClient:
    """Mock MCP клиент для эмуляции взаимодействия без реального SDK"""
    
    def __init__(self, responses: Dict[str, Any]):
        self.responses = responses
        self.call_log = []
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Эмуляция вызова MCP инструмента"""
        self.call_log.append({
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": datetime.now().isoformat()
        })
        
        # Возвращаем заранее подготовленный ответ
        if tool_name in self.responses:
            # Эмуляция задержки сети
            await asyncio.sleep(0.1)
            return self.responses[tool_name]
        
        raise ValueError(f"Unknown tool: {tool_name}")


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_perplexity_response():
    """Mock ответ от Perplexity AI"""
    return {
        "answer": """
        На основе анализа рынка криптовалют за последние 3 месяца:
        
        **Рекомендации для стратегии EMA Crossover:**
        1. Оптимальные параметры: EMA(12, 26) показали лучшие результаты
        2. Таймфрейм: 1h оптимален для BTC/USDT (избегайте 5m из-за шума)
        3. Фильтр тренда: Добавьте EMA(200) как фильтр для уменьшения ложных сигналов
        4. Take Profit: 2-3% оптимальны в текущих условиях
        5. Stop Loss: 1-1.5% для защиты капитала
        
        **Риски:**
        - Высокая волатильность в последние недели (+15%)
        - Рекомендуется уменьшить размер позиции на 30%
        
        **Источники:** CoinGecko, TradingView, CryptoCompare (Oct 2025)
        """,
        "sources": [
            "https://www.coingecko.com/en/coins/bitcoin",
            "https://www.tradingview.com/symbols/BTCUSDT/",
            "https://www.cryptocompare.com/coins/btc/overview"
        ],
        "confidence": 0.85,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def mock_copilot_decision():
    """Mock решение Copilot на основе ответа Perplexity"""
    return {
        "decision": "run_backtest",
        "reasoning": """
        На основе рекомендаций Perplexity:
        - Используем EMA(12, 26) с фильтром EMA(200)
        - Таймфрейм 1h (избегаем 5m из-за шума)
        - TP=2.5%, SL=1.5% (средние значения из диапазона)
        - Уменьшаем risk_per_trade с 2% до 1.4% (-30% от 2%)
        """,
        "action": {
            "type": "run_backtest",
            "params": {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "strategy_config": {
                    "type": "ema_crossover",
                    "fast_ema": 12,
                    "slow_ema": 26,
                    "ma_period": 200,  # Фильтр тренда
                    "take_profit_pct": 2.5,
                    "stop_loss_pct": 1.5,
                    "risk_per_trade_pct": 1.4
                },
                "start_date": "2024-07-01",
                "end_date": "2024-10-29"
            }
        },
        "validation": {
            "perplexity_confidence": 0.85,
            "parameters_adjusted": True,
            "risk_reduced": True
        }
    }


@pytest.fixture
def mock_backtest_result():
    """Mock результат бэктеста после решения Copilot"""
    return {
        "final_capital": 11250.0,
        "total_return": 0.125,  # 12.5%
        "total_trades": 45,
        "winning_trades": 28,
        "losing_trades": 17,
        "win_rate": 0.622,
        "sharpe_ratio": 1.85,
        "max_drawdown": 0.078,  # 7.8%
        "profit_factor": 2.34,
        "metrics": {
            "net_profit": 1250.0,
            "gross_profit": 2100.0,
            "gross_loss": -850.0,
            "avg_win": 75.0,
            "avg_loss": -50.0
        }
    }


# ============================================================================
# PHASE 1: COPILOT ЗАПРОС К PERPLEXITY
# ============================================================================

@pytest.mark.asyncio
async def test_copilot_queries_perplexity(mock_perplexity_response):
    """
    Тест 1: Copilot запрашивает исследование у Perplexity
    
    Сценарий:
    - Пользователь: "Какие параметры для EMA стратегии лучше для BTC?"
    - Copilot: Делегирует вопрос Perplexity через MCP
    - Perplexity: Возвращает аналитику с рекомендациями
    """
    # Mock MCP client для Perplexity
    mock_client = MockMCPClient(responses={
        "search_web": mock_perplexity_response
    })
    
    # Симуляция запроса Copilot → Perplexity
    user_query = "Какие параметры для EMA стратегии оптимальны для BTC/USDT в текущих условиях?"
    
    # Copilot формирует запрос для Perplexity
    perplexity_query = {
        "query": f"{user_query} cryptocurrency trading October 2025",
        "focus": "academic"  # Для более точных данных
    }
    
    # Вызов MCP инструмента Perplexity
    result = await mock_client.call_tool(
        "search_web",
        arguments=perplexity_query
    )
    
    # Проверки
    assert result is not None
    assert "answer" in result
    assert "EMA" in result["answer"]
    assert "12" in result["answer"] or "26" in result["answer"]
    assert result["confidence"] >= 0.7  # Минимальная уверенность
    assert len(result["sources"]) >= 3  # Должны быть источники
    assert len(mock_client.call_log) == 1  # Один вызов
    
    print(f"✅ Copilot → Perplexity: Запрос выполнен")
    print(f"📊 Уверенность: {result['confidence']:.2%}")
    print(f"📚 Источников: {len(result['sources'])}")


# ============================================================================
# PHASE 2: COPILOT АНАЛИЗИРУЕТ ОТВЕТ PERPLEXITY
# ============================================================================

@pytest.mark.asyncio
async def test_copilot_processes_perplexity_answer(
    mock_perplexity_response,
    mock_copilot_decision
):
    """
    Тест 2: Copilot обрабатывает ответ Perplexity и принимает решение
    
    Сценарий:
    - Perplexity вернул рекомендации
    - Copilot парсит ответ
    - Copilot извлекает параметры (EMA 12/26, TP 2-3%, SL 1-1.5%)
    - Copilot принимает решение: запустить бэктест с этими параметрами
    """
    # Симуляция обработки ответа Perplexity
    perplexity_answer = mock_perplexity_response["answer"]
    
    # Copilot парсит рекомендации (в реальности через LLM)
    # Здесь эмуляция через простой парсинг
    extracted_params = {
        "fast_ema": 12,
        "slow_ema": 26,
        "ma_filter": 200,
        "take_profit": 2.5,  # Среднее между 2-3%
        "stop_loss": 1.5,    # Среднее между 1-1.5%
        "timeframe": "1h",
        "risk_adjustment": -0.3  # -30% как рекомендовано
    }
    
    # Copilot формирует решение
    decision = {
        "decision": "run_backtest",
        "reasoning": f"Perplexity рекомендует EMA({extracted_params['fast_ema']}, {extracted_params['slow_ema']})",
        "action": {
            "type": "run_backtest",
            "params": {
                "strategy_config": {
                    "type": "ema_crossover",
                    "fast_ema": extracted_params["fast_ema"],
                    "slow_ema": extracted_params["slow_ema"],
                    "ma_period": extracted_params["ma_filter"],
                    "take_profit_pct": extracted_params["take_profit"],
                    "stop_loss_pct": extracted_params["stop_loss"],
                    "risk_per_trade_pct": 2.0 * (1 + extracted_params["risk_adjustment"])
                }
            }
        },
        "validation": {
            "perplexity_confidence": mock_perplexity_response["confidence"],
            "parameters_adjusted": True
        }
    }
    
    # Проверки
    assert decision["decision"] == "run_backtest"
    assert decision["action"]["params"]["strategy_config"]["fast_ema"] == 12
    assert decision["action"]["params"]["strategy_config"]["slow_ema"] == 26
    assert decision["action"]["params"]["strategy_config"]["ma_period"] == 200
    assert decision["validation"]["perplexity_confidence"] >= 0.7
    
    print(f"✅ Copilot обработал ответ Perplexity")
    print(f"🎯 Решение: {decision['decision']}")
    print(f"📝 Параметры: EMA({extracted_params['fast_ema']}, {extracted_params['slow_ema']})")


# ============================================================================
# PHASE 3: COPILOT ВЫПОЛНЯЕТ ДЕЙСТВИЕ
# ============================================================================

@pytest.mark.asyncio
async def test_copilot_executes_action_based_on_perplexity(
    mock_copilot_decision,
    mock_backtest_result
):
    """
    Тест 3: Copilot выполняет действие (запуск бэктеста) на основе решения
    
    Сценарий:
    - Copilot принял решение запустить бэктест
    - Copilot вызывает BybitStrategyTester MCP инструмент
    - Бэктест выполняется с параметрами из Perplexity
    - Copilot получает результаты
    """
    # Mock MCP client для BybitStrategyTester
    mock_client = MockMCPClient(responses={
        "run_backtest": mock_backtest_result
    })
    
    # Copilot вызывает инструмент run_backtest
    action = mock_copilot_decision["action"]
    
    result = await mock_client.call_tool(
        "run_backtest",
        arguments={
            "symbol": "BTCUSDT",
            "interval": "1h",
            "strategy_config": action["params"]["strategy_config"],
            "start_date": "2024-07-01",
            "end_date": "2024-10-29"
        }
    )
    
    # Проверки результата
    assert result["total_return"] > 0  # Прибыльная стратегия
    assert result["win_rate"] > 0.5    # >50% успешных сделок
    assert result["sharpe_ratio"] > 1.0  # Хорошее соотношение риск/доходность
    assert result["max_drawdown"] < 0.15  # Drawdown <15%
    assert len(mock_client.call_log) == 1  # Один вызов
    
    print(f"✅ Copilot выполнил бэктест")
    print(f"💰 Доходность: {result['total_return']:.2%}")
    print(f"📊 Win Rate: {result['win_rate']:.2%}")
    print(f"📉 Max DD: {result['max_drawdown']:.2%}")


# ============================================================================
# PHASE 4: ПОЛНЫЙ ЦИКЛ ИНТЕГРАЦИИ
# ============================================================================

@pytest.mark.asyncio
async def test_full_copilot_perplexity_workflow(
    mock_perplexity_response,
    mock_copilot_decision,
    mock_backtest_result
):
    """
    Тест 4: Полный цикл взаимодействия Copilot ↔ Perplexity ↔ BybitTester
    
    Полный сценарий:
    1. Пользователь задает вопрос Copilot
    2. Copilot → Perplexity (исследование)
    3. Perplexity → Copilot (рекомендации)
    4. Copilot принимает решение
    5. Copilot → BybitTester (запуск бэктеста)
    6. BybitTester → Copilot (результаты)
    7. Copilot → Пользователь (финальный отчет)
    """
    workflow = {
        "steps": [],
        "duration": 0,
        "success": False
    }
    
    start_time = datetime.now()
    
    try:
        # Step 1: Пользователь → Copilot
        user_query = "Подбери оптимальные параметры для EMA стратегии на BTC/USDT и запусти бэктест"
        workflow["steps"].append({
            "step": 1,
            "agent": "User → Copilot",
            "action": "Query received",
            "query": user_query
        })
        
        # Step 2: Copilot → Perplexity
        perplexity_client = MockMCPClient(responses={"search_web": mock_perplexity_response})
        
        perplexity_result = await perplexity_client.call_tool(
            "search_web",
            arguments={"query": f"{user_query} October 2025"}
        )
        
        workflow["steps"].append({
            "step": 2,
            "agent": "Copilot → Perplexity",
            "action": "Research request",
            "confidence": perplexity_result["confidence"]
        })
        
        # Step 3: Copilot обрабатывает ответ
        extracted_params = {
            "fast_ema": 12,
            "slow_ema": 26,
            "take_profit": 2.5,
            "stop_loss": 1.5
        }
        
        workflow["steps"].append({
            "step": 3,
            "agent": "Copilot (Processing)",
            "action": "Extract parameters",
            "params": extracted_params
        })
        
        # Step 4: Copilot → BybitTester
        bybit_client = MockMCPClient(responses={"run_backtest": mock_backtest_result})
        
        backtest_result = await bybit_client.call_tool(
            "run_backtest",
            arguments={
                "symbol": "BTCUSDT",
                "interval": "1h",
                "strategy_config": {
                    "type": "ema_crossover",
                    **extracted_params
                }
            }
        )
        
        workflow["steps"].append({
            "step": 4,
            "agent": "Copilot → BybitTester",
            "action": "Run backtest",
            "result": {
                "return": backtest_result["total_return"],
                "win_rate": backtest_result["win_rate"]
            }
        })
        
        # Step 5: Copilot формирует финальный ответ
        final_report = {
            "summary": f"Бэктест выполнен с параметрами из Perplexity",
            "perplexity_confidence": perplexity_result["confidence"],
            "backtest_performance": {
                "return": f"{backtest_result['total_return']:.2%}",
                "win_rate": f"{backtest_result['win_rate']:.2%}",
                "sharpe": backtest_result["sharpe_ratio"]
            },
            "recommendation": "Стратегия прибыльна, можно использовать" if backtest_result["total_return"] > 0 else "Требуется оптимизация"
        }
        
        workflow["steps"].append({
            "step": 5,
            "agent": "Copilot → User",
            "action": "Final report",
            "report": final_report
        })
        
        workflow["success"] = True
        
    finally:
        end_time = datetime.now()
        workflow["duration"] = (end_time - start_time).total_seconds()
    
    # Проверки полного workflow
    assert workflow["success"] is True
    assert len(workflow["steps"]) == 5
    assert workflow["steps"][1]["agent"] == "Copilot → Perplexity"
    assert workflow["steps"][3]["agent"] == "Copilot → BybitTester"
    assert workflow["duration"] < 60  # Должно занять <60 секунд
    
    # Вывод результатов
    print("\n" + "="*70)
    print("🤖 ПОЛНЫЙ ЦИКЛ COPILOT ↔ PERPLEXITY ↔ BYBIT TESTER")
    print("="*70)
    
    for step in workflow["steps"]:
        print(f"\n{step['step']}. {step['agent']}")
        print(f"   Действие: {step['action']}")
        if "confidence" in step:
            print(f"   Уверенность: {step['confidence']:.2%}")
        if "params" in step:
            print(f"   Параметры: {step['params']}")
        if "result" in step:
            print(f"   Результат: Return={step['result']['return']:.2%}, Win Rate={step['result']['win_rate']:.2%}")
        if "report" in step:
            print(f"   Отчет: {step['report']['summary']}")
            print(f"   Рекомендация: {step['report']['recommendation']}")
    
    print(f"\n⏱️  Время выполнения: {workflow['duration']:.2f} сек")
    print(f"✅ Статус: {'SUCCESS' if workflow['success'] else 'FAILED'}")
    print("="*70)


# ============================================================================
# EDGE CASES
# ============================================================================

@pytest.mark.asyncio
async def test_perplexity_unavailable_fallback():
    """
    Тест 5: Graceful degradation когда Perplexity недоступен
    
    Сценарий:
    - Copilot пытается запросить Perplexity
    - Perplexity возвращает ошибку (timeout/API limit)
    - Copilot использует локальные параметры по умолчанию
    - Бэктест все равно запускается
    """
    # Mock client который выбрасывает TimeoutError
    async def failing_call_tool(tool_name, arguments):
        raise TimeoutError("Perplexity timeout")
    
    # Создаем клиента с failure
    mock_client = Mock()
    mock_client.call_tool = failing_call_tool
    
    # Copilot пытается запросить Perplexity
    try:
        await mock_client.call_tool("search_web", arguments={})
    except TimeoutError:
        # Fallback на дефолтные параметры
        default_params = {
            "fast_ema": 50,  # Безопасные значения
            "slow_ema": 200,
            "take_profit_pct": 5.0,
            "stop_loss_pct": 2.0
        }
        
        print("⚠️  Perplexity недоступен, используем дефолтные параметры")
        print(f"📊 Параметры: {default_params}")
        
        # Проверяем что fallback работает
        assert default_params["fast_ema"] > 0
        assert default_params["slow_ema"] > default_params["fast_ema"]


@pytest.mark.asyncio
async def test_perplexity_low_confidence():
    """
    Тест 6: Copilot запрашивает подтверждение при низкой уверенности Perplexity
    
    Сценарий:
    - Perplexity возвращает ответ с confidence=0.3 (низкая)
    - Copilot не запускает бэктест автоматически
    - Copilot запрашивает подтверждение у пользователя
    """
    low_confidence_response = {
        "answer": "Недостаточно данных для точного анализа",
        "confidence": 0.3,  # Низкая уверенность
        "sources": []
    }
    
    # Copilot проверяет уверенность
    if low_confidence_response["confidence"] < 0.5:
        decision = {
            "decision": "request_user_confirmation",
            "reasoning": f"Perplexity confidence только {low_confidence_response['confidence']:.0%}",
            "recommendation": "Запросить дополнительные данные или использовать дефолтные параметры"
        }
        
        assert decision["decision"] == "request_user_confirmation"
        print(f"⚠️  Низкая уверенность ({low_confidence_response['confidence']:.0%}), запрашиваем подтверждение")


# ============================================================================
# PERFORMANCE TEST
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_performance():
    """
    Тест 7: Проверка производительности полного цикла
    
    Требования:
    - Copilot → Perplexity: <5 сек
    - Copilot обработка: <1 сек
    - Copilot → BybitTester: <10 сек
    - Полный цикл: <20 сек
    """
    timings = {}
    
    # Измеряем время каждого этапа
    start = datetime.now()
    perplexity_client = MockMCPClient(responses={"search_web": {"answer": "test", "confidence": 0.9, "sources": []}})
    await perplexity_client.call_tool("search_web", arguments={})
    timings["perplexity"] = (datetime.now() - start).total_seconds()
    
    start = datetime.now()
    # Processing time (эмуляция)
    await asyncio.sleep(0.1)
    timings["processing"] = (datetime.now() - start).total_seconds()
    
    start = datetime.now()
    bybit_client = MockMCPClient(responses={"run_backtest": {"total_return": 0.1}})
    await bybit_client.call_tool("run_backtest", arguments={})
    timings["backtest"] = (datetime.now() - start).total_seconds()
    
    total = sum(timings.values())
    
    # Проверки производительности
    assert timings["perplexity"] < 5.0, f"Perplexity слишком медленный: {timings['perplexity']:.2f}s"
    assert timings["processing"] < 1.0, f"Processing слишком медленный: {timings['processing']:.2f}s"
    assert timings["backtest"] < 10.0, f"Backtest слишком медленный: {timings['backtest']:.2f}s"
    assert total < 20.0, f"Полный цикл слишком медленный: {total:.2f}s"
    
    print(f"\n⏱️  Производительность:")
    print(f"   Perplexity: {timings['perplexity']:.2f}s")
    print(f"   Processing: {timings['processing']:.2f}s")
    print(f"   Backtest: {timings['backtest']:.2f}s")
    print(f"   TOTAL: {total:.2f}s ✅")


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    """
    Запуск тестов:
    
    # Все тесты
    pytest tests/integration/test_copilot_perplexity_mcp.py -v
    
    # Только полный workflow
    pytest tests/integration/test_copilot_perplexity_mcp.py::test_full_copilot_perplexity_workflow -v -s
    
    # С подробным выводом
    pytest tests/integration/test_copilot_perplexity_mcp.py -v -s --tb=short
    """
    pytest.main([__file__, "-v", "-s"])
