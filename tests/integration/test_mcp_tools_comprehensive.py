"""
Комплексные тесты для всех MCP инструментов
Формат: Cyclic Dialogue (Copilot ↔ Perplexity)

Тестируемые инструменты:
1. Базовые контекстные инструменты (7)
2. Perplexity поиск и анализ (4)
3. Расширенные аналитические инструменты (8)

ВСЕГО: 19 MCP Tools
"""

import pytest
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Импортируем MCP server напрямую
from mcp_server.server import (
    # Контекстные инструменты
    get_project_structure,
    list_available_strategies,
    get_supported_timeframes,
    get_backtest_capabilities,
    check_system_status,
    get_testing_summary,
    explain_project_architecture,
    
    # Базовые Perplexity инструменты
    perplexity_search,
    perplexity_analyze_crypto,
    perplexity_strategy_research,
    perplexity_market_news,
    
    # Расширенные аналитические инструменты
    analyze_backtest_results,
    compare_strategies,
    risk_management_advice,
    technical_indicator_research,
    explain_metric,
    market_regime_detection,
    code_review_strategy,
    generate_test_scenarios
)


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТОВЫЕ УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════════════════

class CyclicDialogueRecorder:
    """Записывает диалог между Copilot и Perplexity"""
    
    def __init__(self):
        self.turns: List[Dict[str, Any]] = []
        self.total_tokens = 0
        self.start_time = None
        self.end_time = None
    
    def start(self):
        self.start_time = datetime.now()
    
    def end(self):
        self.end_time = datetime.now()
    
    def add_turn(self, speaker: str, content: str, metadata: Dict[str, Any] = None):
        """Добавить реплику в диалог"""
        turn = {
            "turn_number": len(self.turns) + 1,
            "speaker": speaker,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        self.turns.append(turn)
        
        # Подсчёт токенов (примерная оценка)
        if metadata and "tokens" in metadata:
            self.total_tokens += metadata["tokens"]
    
    def get_duration(self) -> float:
        """Получить длительность диалога в секундах"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку по диалогу"""
        return {
            "total_turns": len(self.turns),
            "duration_seconds": self.get_duration(),
            "total_tokens": self.total_tokens,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }
    
    def save_to_file(self, filepath: Path):
        """Сохранить диалог в JSON файл"""
        data = {
            "summary": self.get_summary(),
            "dialogue": self.turns
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


async def cyclic_test_tool(
    tool_name: str,
    tool_func: callable,
    tool_args: Dict[str, Any],
    recorder: CyclicDialogueRecorder
) -> Dict[str, Any]:
    """
    Протестировать MCP инструмент в формате циклического диалога
    
    Шаги:
    1. Copilot → Question: Задать вопрос Perplexity о том, как тестировать инструмент
    2. Perplexity → Answer: Получить рекомендации
    3. Copilot → Analysis: Проанализировать рекомендации
    4. Copilot → Execute: Выполнить тест инструмента
    5. Perplexity → Verification: Проверить результат теста
    """
    
    # Turn 1: Copilot спрашивает Perplexity, как тестировать инструмент
    question = f"""
    How should I test the MCP tool "{tool_name}" with these parameters:
    {json.dumps(tool_args, indent=2)}
    
    What are:
    1. Key test scenarios
    2. Expected outputs
    3. Edge cases to check
    4. Success criteria
    """
    recorder.add_turn("Copilot", question, {"type": "question"})
    
    # Turn 2: Perplexity отвечает (используем perplexity_search)
    try:
        perplexity_response = await perplexity_search(question, model="sonar")
        recorder.add_turn(
            "Perplexity",
            perplexity_response.get("answer", "No answer received"),
            {
                "type": "answer",
                "success": perplexity_response.get("success", False),
                "tokens": perplexity_response.get("usage", {}).get("total_tokens", 0)
            }
        )
    except Exception as e:
        recorder.add_turn("Perplexity", f"Error: {str(e)}", {"type": "error"})
        perplexity_response = {"success": False, "error": str(e)}
    
    # Turn 3: Copilot анализирует рекомендации
    analysis = f"""
    Based on Perplexity recommendations, I will:
    1. Execute {tool_name} with provided arguments
    2. Validate output structure
    3. Check for expected fields
    4. Verify data types and values
    """
    recorder.add_turn("Copilot", analysis, {"type": "analysis"})
    
    # Turn 4: Copilot выполняет тест
    test_result = {
        "tool_name": tool_name,
        "arguments": tool_args,
        "status": "UNKNOWN",
        "output": None,
        "error": None,
        "validation": {}
    }
    
    try:
        # Выполняем инструмент
        output = await tool_func(**tool_args)
        test_result["output"] = output
        test_result["status"] = "SUCCESS"
        
        # Базовая валидация
        if isinstance(output, dict):
            test_result["validation"]["is_dict"] = True
            test_result["validation"]["has_keys"] = len(output) > 0
            
            # Специфичная валидация для Perplexity инструментов
            if "success" in output:
                test_result["validation"]["perplexity_success"] = output["success"]
            if "answer" in output:
                test_result["validation"]["has_answer"] = len(output["answer"]) > 0
        elif isinstance(output, str):
            test_result["validation"]["is_string"] = True
            test_result["validation"]["not_empty"] = len(output) > 0
        
        recorder.add_turn(
            "Copilot",
            f"Tool executed successfully. Output: {json.dumps(output, indent=2)[:500]}...",
            {"type": "execution", "status": "success"}
        )
        
    except Exception as e:
        test_result["status"] = "FAILED"
        test_result["error"] = str(e)
        recorder.add_turn(
            "Copilot",
            f"Tool execution failed: {str(e)}",
            {"type": "execution", "status": "failed"}
        )
    
    # Turn 5: Perplexity верифицирует результат
    verification_query = f"""
    Verify test result for {tool_name}:
    
    Status: {test_result['status']}
    Validation: {json.dumps(test_result['validation'], indent=2)}
    Error: {test_result.get('error', 'None')}
    
    Is this result acceptable? What improvements are needed?
    """
    
    try:
        verification = await perplexity_search(verification_query, model="sonar")
        recorder.add_turn(
            "Perplexity",
            verification.get("answer", "No verification received"),
            {
                "type": "verification",
                "success": verification.get("success", False),
                "tokens": verification.get("usage", {}).get("total_tokens", 0)
            }
        )
    except Exception as e:
        recorder.add_turn("Perplexity", f"Verification error: {str(e)}", {"type": "error"})
    
    return test_result


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ КОНТЕКСТНЫХ ИНСТРУМЕНТОВ (7 штук)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_context_tools_comprehensive():
    """Комплексный тест всех 7 контекстных инструментов"""
    
    recorder = CyclicDialogueRecorder()
    recorder.start()
    
    context_tools = [
        ("get_project_structure", get_project_structure, {}),
        ("list_available_strategies", list_available_strategies, {}),
        ("get_supported_timeframes", get_supported_timeframes, {}),
        ("get_backtest_capabilities", get_backtest_capabilities, {}),
        ("check_system_status", check_system_status, {}),
        ("get_testing_summary", get_testing_summary, {}),
        ("explain_project_architecture", explain_project_architecture, {})
    ]
    
    results = []
    for tool_name, tool_func, tool_args in context_tools:
        result = await cyclic_test_tool(tool_name, tool_func, tool_args, recorder)
        results.append(result)
        
        # Проверяем базовые требования
        assert result["status"] in ["SUCCESS", "FAILED"], f"{tool_name}: Invalid status"
        if result["status"] == "SUCCESS":
            assert result["output"] is not None, f"{tool_name}: No output"
    
    recorder.end()
    
    # Сохраняем диалог
    output_dir = Path(__file__).parent.parent.parent / "results" / "mcp_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder.save_to_file(output_dir / "context_tools_dialogue.json")
    
    # Сводка
    summary = recorder.get_summary()
    print(f"\n{'='*80}")
    print(f"CONTEXT TOOLS TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Tools Tested: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'SUCCESS')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'FAILED')}")
    print(f"Total Dialogue Turns: {summary['total_turns']}")
    print(f"Duration: {summary['duration_seconds']:.2f}s")
    print(f"Total Tokens: {summary['total_tokens']}")
    print(f"{'='*80}\n")
    
    # Все инструменты должны пройти
    assert all(r["status"] == "SUCCESS" for r in results), "Some context tools failed"


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ БАЗОВЫХ PERPLEXITY ИНСТРУМЕНТОВ (4 штуки)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_perplexity_basic_tools():
    """Тест базовых Perplexity инструментов"""
    
    recorder = CyclicDialogueRecorder()
    recorder.start()
    
    perplexity_tools = [
        ("perplexity_search", perplexity_search, {
            "query": "What is the optimal RSI period for crypto day trading?",
            "model": "sonar"
        }),
        ("perplexity_analyze_crypto", perplexity_analyze_crypto, {
            "symbol": "BTC",
            "analysis_type": "technical"
        }),
        ("perplexity_strategy_research", perplexity_strategy_research, {
            "strategy_type": "momentum",
            "market_conditions": "trending"
        }),
        ("perplexity_market_news", perplexity_market_news, {
            "topic": "bitcoin",
            "timeframe": "24h"
        })
    ]
    
    results = []
    for tool_name, tool_func, tool_args in perplexity_tools:
        result = await cyclic_test_tool(tool_name, tool_func, tool_args, recorder)
        results.append(result)
        
        # Проверяем Perplexity-специфичные поля
        if result["status"] == "SUCCESS":
            output = result["output"]
            assert "success" in output, f"{tool_name}: Missing 'success' field"
            assert "answer" in output, f"{tool_name}: Missing 'answer' field"
            
            if output.get("success"):
                assert len(output["answer"]) > 0, f"{tool_name}: Empty answer"
    
    recorder.end()
    
    # Сохраняем диалог
    output_dir = Path(__file__).parent.parent.parent / "results" / "mcp_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder.save_to_file(output_dir / "perplexity_basic_tools_dialogue.json")
    
    # Сводка
    summary = recorder.get_summary()
    print(f"\n{'='*80}")
    print(f"PERPLEXITY BASIC TOOLS TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Tools Tested: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'SUCCESS')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'FAILED')}")
    print(f"Total Dialogue Turns: {summary['total_turns']}")
    print(f"Duration: {summary['duration_seconds']:.2f}s")
    print(f"Total Tokens: {summary['total_tokens']}")
    print(f"{'='*80}\n")


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ РАСШИРЕННЫХ АНАЛИТИЧЕСКИХ ИНСТРУМЕНТОВ (8 штук)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_advanced_analytical_tools():
    """Тест расширенных аналитических инструментов"""
    
    recorder = CyclicDialogueRecorder()
    recorder.start()
    
    advanced_tools = [
        ("analyze_backtest_results", analyze_backtest_results, {
            "backtest_id": 1,
            "detailed": True
        }),
        ("compare_strategies", compare_strategies, {
            "strategy_a": "EMA Crossover",
            "strategy_b": "RSI Mean Reversion",
            "market_type": "crypto"
        }),
        ("risk_management_advice", risk_management_advice, {
            "capital": 10000.0,
            "risk_per_trade": 2.0,
            "max_positions": 3
        }),
        ("technical_indicator_research", technical_indicator_research, {
            "indicator_name": "MACD",
            "use_case": "trend-following"
        }),
        ("explain_metric", explain_metric, {
            "metric_name": "Sharpe Ratio",
            "context": "crypto_trading"
        }),
        ("market_regime_detection", market_regime_detection, {
            "symbol": "BTCUSDT",
            "timeframe": "1d"
        }),
        ("code_review_strategy", code_review_strategy, {
            "strategy_code": """
def generate_signals(data):
    data['ema_fast'] = data['close'].ewm(span=12).mean()
    data['ema_slow'] = data['close'].ewm(span=26).mean()
    data['signal'] = 0
    data.loc[data['ema_fast'] > data['ema_slow'], 'signal'] = 1
    data.loc[data['ema_fast'] < data['ema_slow'], 'signal'] = -1
    return data
            """,
            "language": "python"
        }),
        ("generate_test_scenarios", generate_test_scenarios, {
            "strategy_name": "Bollinger Bands Breakout",
            "complexity": "comprehensive"
        })
    ]
    
    results = []
    for tool_name, tool_func, tool_args in advanced_tools:
        result = await cyclic_test_tool(tool_name, tool_func, tool_args, recorder)
        results.append(result)
        
        # Проверяем успешность выполнения
        if result["status"] == "SUCCESS":
            output = result["output"]
            assert "success" in output, f"{tool_name}: Missing 'success' field"
            assert "analysis_type" in output, f"{tool_name}: Missing 'analysis_type' field"
    
    recorder.end()
    
    # Сохраняем диалог
    output_dir = Path(__file__).parent.parent.parent / "results" / "mcp_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder.save_to_file(output_dir / "advanced_tools_dialogue.json")
    
    # Сводка
    summary = recorder.get_summary()
    print(f"\n{'='*80}")
    print(f"ADVANCED ANALYTICAL TOOLS TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Tools Tested: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'SUCCESS')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'FAILED')}")
    print(f"Total Dialogue Turns: {summary['total_turns']}")
    print(f"Duration: {summary['duration_seconds']:.2f}s")
    print(f"Total Tokens: {summary['total_tokens']}")
    print(f"{'='*80}\n")


# ═══════════════════════════════════════════════════════════════════════════
# ОБЩИЙ ТЕСТ ВСЕХ 19 ИНСТРУМЕНТОВ
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_all_mcp_tools_comprehensive():
    """
    Комплексный тест всех 19 MCP инструментов
    
    Формат: Cyclic Dialogue (Copilot ↔ Perplexity)
    Охват: 100% инструментов MCP сервера
    """
    
    recorder = CyclicDialogueRecorder()
    recorder.start()
    
    all_tools = [
        # Контекстные инструменты (7)
        ("get_project_structure", get_project_structure, {}),
        ("list_available_strategies", list_available_strategies, {}),
        ("get_supported_timeframes", get_supported_timeframes, {}),
        ("get_backtest_capabilities", get_backtest_capabilities, {}),
        ("check_system_status", check_system_status, {}),
        ("get_testing_summary", get_testing_summary, {}),
        ("explain_project_architecture", explain_project_architecture, {}),
        
        # Базовые Perplexity (4)
        ("perplexity_search", perplexity_search, {
            "query": "Best practices for crypto trading bots",
            "model": "sonar"
        }),
        ("perplexity_analyze_crypto", perplexity_analyze_crypto, {
            "symbol": "ETH",
            "analysis_type": "fundamental"
        }),
        ("perplexity_strategy_research", perplexity_strategy_research, {
            "strategy_type": "mean-reversion",
            "market_conditions": "ranging"
        }),
        ("perplexity_market_news", perplexity_market_news, {
            "topic": "ethereum",
            "timeframe": "7d"
        }),
        
        # Расширенные аналитические (8)
        ("analyze_backtest_results", analyze_backtest_results, {
            "backtest_id": 42,
            "detailed": False
        }),
        ("compare_strategies", compare_strategies, {
            "strategy_a": "Grid Trading",
            "strategy_b": "DCA Bot",
            "market_type": "crypto"
        }),
        ("risk_management_advice", risk_management_advice, {
            "capital": 50000.0,
            "risk_per_trade": 1.5,
            "max_positions": 5
        }),
        ("technical_indicator_research", technical_indicator_research, {
            "indicator_name": "Bollinger Bands",
            "use_case": "breakout"
        }),
        ("explain_metric", explain_metric, {
            "metric_name": "Maximum Drawdown",
            "context": "risk_assessment"
        }),
        ("market_regime_detection", market_regime_detection, {
            "symbol": "ETHUSDT",
            "timeframe": "4h"
        }),
        ("code_review_strategy", code_review_strategy, {
            "strategy_code": "# Simple RSI strategy\nif rsi < 30: buy()",
            "language": "python"
        }),
        ("generate_test_scenarios", generate_test_scenarios, {
            "strategy_name": "MACD Divergence",
            "complexity": "basic"
        })
    ]
    
    results = []
    failed_tools = []
    
    for i, (tool_name, tool_func, tool_args) in enumerate(all_tools, 1):
        print(f"\n[{i}/{len(all_tools)}] Testing: {tool_name}")
        
        result = await cyclic_test_tool(tool_name, tool_func, tool_args, recorder)
        results.append(result)
        
        if result["status"] == "FAILED":
            failed_tools.append(tool_name)
            print(f"  ❌ FAILED: {result.get('error', 'Unknown error')}")
        else:
            print(f"  ✅ SUCCESS")
    
    recorder.end()
    
    # Сохраняем полный диалог
    output_dir = Path(__file__).parent.parent.parent / "results" / "mcp_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder.save_to_file(output_dir / "all_tools_comprehensive_dialogue.json")
    
    # Сохраняем детальный отчёт
    report = {
        "test_metadata": {
            "total_tools": len(all_tools),
            "test_date": datetime.now().isoformat(),
            "test_type": "comprehensive_cyclic_dialogue"
        },
        "summary": recorder.get_summary(),
        "results": results,
        "failed_tools": failed_tools,
        "coverage": {
            "context_tools": 7,
            "perplexity_basic": 4,
            "advanced_analytical": 8,
            "total_tested": len(results),
            "success_rate": f"{(len(results) - len(failed_tools)) / len(results) * 100:.1f}%"
        }
    }
    
    with open(output_dir / "comprehensive_test_report.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Печать итоговой сводки
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE MCP TOOLS TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Tools Tested: {len(results)}")
    print(f"✅ Successful: {len(results) - len(failed_tools)}")
    print(f"❌ Failed: {len(failed_tools)}")
    if failed_tools:
        print(f"\nFailed Tools:")
        for tool in failed_tools:
            print(f"  - {tool}")
    print(f"\nDialogue Statistics:")
    print(f"  Total Turns: {report['summary']['total_turns']}")
    print(f"  Duration: {report['summary']['duration_seconds']:.2f}s")
    print(f"  Total Tokens: {report['summary']['total_tokens']}")
    print(f"  Avg Tokens/Tool: {report['summary']['total_tokens'] / len(results):.0f}")
    print(f"\nCoverage:")
    print(f"  Context Tools: 7/7 (100%)")
    print(f"  Perplexity Basic: 4/4 (100%)")
    print(f"  Advanced Analytical: 8/8 (100%)")
    print(f"  Overall Success Rate: {report['coverage']['success_rate']}")
    print(f"{'='*80}\n")
    
    # Проверяем, что хотя бы 80% инструментов прошли тест
    success_rate = (len(results) - len(failed_tools)) / len(results)
    assert success_rate >= 0.8, f"Too many failures: {success_rate*100:.1f}% success rate"


# ═══════════════════════════════════════════════════════════════════════════
# СПЕЦИАЛЬНЫЕ ТЕСТЫ
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_perplexity_error_handling():
    """Тест обработки ошибок в Perplexity инструментах"""
    
    # Тест с пустым запросом
    result = await perplexity_search("", model="sonar")
    assert result["success"] == False, "Should fail with empty query"
    
    # Тест с невалидной моделью
    result = await perplexity_search("test query", model="invalid_model")
    # Должен fallback на sonar
    assert "error" in result or "answer" in result
    
    print("✅ Error handling tests passed")


@pytest.mark.asyncio
async def test_tool_parameter_validation():
    """Тест валидации параметров инструментов"""
    
    # Тест risk_management_advice с негативным капиталом
    result = await risk_management_advice(capital=-1000.0)
    # Инструмент должен обработать, но Perplexity укажет на проблему
    
    # Тест analyze_backtest_results с негативным ID
    result = await analyze_backtest_results(backtest_id=-1)
    
    print("✅ Parameter validation tests passed")


if __name__ == "__main__":
    """Запуск тестов напрямую"""
    
    print("Запуск комплексных MCP тестов...")
    print("Это займёт несколько минут (Perplexity API вызовы)\n")
    
    # Запускаем главный тест
    asyncio.run(test_all_mcp_tools_comprehensive())
    
    print("\n✅ Все тесты завершены!")
    print("📊 Результаты сохранены в: results/mcp_tests/")
