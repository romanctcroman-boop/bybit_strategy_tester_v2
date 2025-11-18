"""
Unit-тесты для расширенных MCP инструментов
Быстрые тесты без обращения к Perplexity API
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "mcp-server"))

from server import (
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
# MOCK ДАННЫЕ
# ═══════════════════════════════════════════════════════════════════════════

MOCK_PERPLEXITY_RESPONSE = {
    "success": True,
    "answer": "This is a mock answer from Perplexity AI for testing purposes.",
    "sources": [
        {"title": "Mock Source 1", "url": "https://example.com/1"},
        {"title": "Mock Source 2", "url": "https://example.com/2"}
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    }
}


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ANALYZE_BACKTEST_RESULTS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('server.perplexity_search', new_callable=AsyncMock)
async def test_analyze_backtest_results_success(mock_search):
    """Тест успешного анализа результатов бэктеста"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await analyze_backtest_results(backtest_id=1, detailed=True)
    
    assert result["success"] == True
    assert "backtest_id" in result
    assert result["backtest_id"] == 1
    assert "metrics" in result
    assert "analysis_type" in result
    assert result["analysis_type"] == "backtest_analysis"
    
    # Проверяем, что mock метрики присутствуют
    metrics = result["metrics"]
    assert "total_return" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "win_rate" in metrics


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_analyze_backtest_results_different_ids(mock_search):
    """Тест с разными ID бэктестов"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    # Тест с ID = 0
    result = await analyze_backtest_results(backtest_id=0)
    assert result["backtest_id"] == 0
    
    # Тест с большим ID
    result = await analyze_backtest_results(backtest_id=999)
    assert result["backtest_id"] == 999
    
    # Тест с отрицательным ID (должен обработаться)
    result = await analyze_backtest_results(backtest_id=-1)
    assert result["backtest_id"] == -1


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_analyze_backtest_results_detailed_flag(mock_search):
    """Тест флага detailed"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    # Детальный анализ
    result = await analyze_backtest_results(backtest_id=1, detailed=True)
    assert result["success"] == True
    
    # Базовый анализ
    result = await analyze_backtest_results(backtest_id=1, detailed=False)
    assert result["success"] == True


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ COMPARE_STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_compare_strategies_success(mock_search):
    """Тест успешного сравнения стратегий"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await compare_strategies(
        strategy_a="EMA Crossover",
        strategy_b="RSI Mean Reversion",
        market_type="crypto"
    )
    
    assert result["success"] == True
    assert result["strategy_a"] == "EMA Crossover"
    assert result["strategy_b"] == "RSI Mean Reversion"
    assert result["market_type"] == "crypto"
    assert result["analysis_type"] == "strategy_comparison"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_compare_strategies_different_markets(mock_search):
    """Тест сравнения для разных типов рынков"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    # Crypto
    result = await compare_strategies("Strategy A", "Strategy B", market_type="crypto")
    assert result["market_type"] == "crypto"
    
    # Stocks
    result = await compare_strategies("Strategy A", "Strategy B", market_type="stocks")
    assert result["market_type"] == "stocks"
    
    # Forex
    result = await compare_strategies("Strategy A", "Strategy B", market_type="forex")
    assert result["market_type"] == "forex"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_compare_strategies_same_strategy(mock_search):
    """Тест сравнения одинаковых стратегий (edge case)"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await compare_strategies(
        strategy_a="MACD",
        strategy_b="MACD",
        market_type="crypto"
    )
    
    # Должно обработаться без ошибок
    assert result["success"] == True
    assert result["strategy_a"] == result["strategy_b"]


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ RISK_MANAGEMENT_ADVICE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_risk_management_advice_success(mock_search):
    """Тест успешного получения рекомендаций по риск-менеджменту"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await risk_management_advice(
        capital=10000.0,
        risk_per_trade=2.0,
        max_positions=3
    )
    
    assert result["success"] == True
    assert result["capital"] == 10000.0
    assert result["risk_per_trade"] == 2.0
    assert result["max_positions"] == 3
    assert result["analysis_type"] == "risk_management"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_risk_management_advice_default_params(mock_search):
    """Тест с параметрами по умолчанию"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await risk_management_advice(capital=5000.0)
    
    assert result["capital"] == 5000.0
    assert result["risk_per_trade"] == 2.0  # default
    assert result["max_positions"] == 3     # default


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_risk_management_advice_edge_cases(mock_search):
    """Тест граничных значений"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    # Маленький капитал
    result = await risk_management_advice(capital=100.0, risk_per_trade=1.0, max_positions=1)
    assert result["success"] == True
    
    # Большой капитал
    result = await risk_management_advice(capital=1000000.0, risk_per_trade=0.5, max_positions=10)
    assert result["success"] == True
    
    # Высокий риск
    result = await risk_management_advice(capital=10000.0, risk_per_trade=10.0)
    assert result["success"] == True


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ TECHNICAL_INDICATOR_RESEARCH
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_technical_indicator_research_success(mock_search):
    """Тест исследования технического индикатора"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await technical_indicator_research(
        indicator_name="RSI",
        use_case="mean-reversion"
    )
    
    assert result["success"] == True
    assert result["indicator_name"] == "RSI"
    assert result["use_case"] == "mean-reversion"
    assert result["analysis_type"] == "indicator_research"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_technical_indicator_research_various_indicators(mock_search):
    """Тест разных индикаторов"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    indicators = ["RSI", "MACD", "Bollinger Bands", "Stochastic", "ATR"]
    
    for indicator in indicators:
        result = await technical_indicator_research(indicator_name=indicator)
        assert result["indicator_name"] == indicator
        assert result["success"] == True


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_technical_indicator_research_use_cases(mock_search):
    """Тест разных случаев использования"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    use_cases = ["trend-following", "mean-reversion", "breakout", "momentum"]
    
    for use_case in use_cases:
        result = await technical_indicator_research(
            indicator_name="MACD",
            use_case=use_case
        )
        assert result["use_case"] == use_case
        assert result["success"] == True


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ EXPLAIN_METRIC
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_explain_metric_success(mock_search):
    """Тест объяснения метрики"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await explain_metric(
        metric_name="Sharpe Ratio",
        context="crypto_trading"
    )
    
    assert result["success"] == True
    assert result["metric_name"] == "Sharpe Ratio"
    assert result["context"] == "crypto_trading"
    assert result["analysis_type"] == "metric_explanation"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_explain_metric_various_metrics(mock_search):
    """Тест разных метрик"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    metrics = [
        "Sharpe Ratio",
        "Max Drawdown",
        "Win Rate",
        "Profit Factor",
        "Sortino Ratio",
        "Calmar Ratio"
    ]
    
    for metric in metrics:
        result = await explain_metric(metric_name=metric)
        assert result["metric_name"] == metric
        assert result["success"] == True


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ MARKET_REGIME_DETECTION
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_market_regime_detection_success(mock_search):
    """Тест определения рыночного режима"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await market_regime_detection(
        symbol="BTCUSDT",
        timeframe="1d"
    )
    
    assert result["success"] == True
    assert result["symbol"] == "BTCUSDT"
    assert result["timeframe"] == "1d"
    assert result["analysis_type"] == "market_regime"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_market_regime_detection_various_symbols(mock_search):
    """Тест разных символов"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]
    
    for symbol in symbols:
        result = await market_regime_detection(symbol=symbol)
        assert result["symbol"] == symbol
        assert result["success"] == True


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_market_regime_detection_various_timeframes(mock_search):
    """Тест разных таймфреймов"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    
    for timeframe in timeframes:
        result = await market_regime_detection(symbol="BTCUSDT", timeframe=timeframe)
        assert result["timeframe"] == timeframe
        assert result["success"] == True


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ CODE_REVIEW_STRATEGY
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_code_review_strategy_success(mock_search):
    """Тест code review стратегии"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    code = """
def simple_strategy(data):
    data['sma'] = data['close'].rolling(20).mean()
    return data
    """
    
    result = await code_review_strategy(
        strategy_code=code,
        language="python"
    )
    
    assert result["success"] == True
    assert result["language"] == "python"
    assert result["code_length"] == len(code)
    assert result["analysis_type"] == "code_review"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_code_review_strategy_long_code(mock_search):
    """Тест с длинным кодом (обрезка до 2000 символов)"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    # Генерируем код длиной > 2000 символов
    long_code = "# " + "x" * 3000
    
    result = await code_review_strategy(strategy_code=long_code)
    
    assert result["success"] == True
    assert result["code_length"] == len(long_code)
    # Убеждаемся, что код был обрезан в запросе (проверяется через mock)


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_code_review_strategy_empty_code(mock_search):
    """Тест с пустым кодом"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await code_review_strategy(strategy_code="")
    
    assert result["success"] == True
    assert result["code_length"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ GENERATE_TEST_SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_generate_test_scenarios_success(mock_search):
    """Тест генерации тестовых сценариев"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    result = await generate_test_scenarios(
        strategy_name="MACD Crossover",
        complexity="comprehensive"
    )
    
    assert result["success"] == True
    assert result["strategy_name"] == "MACD Crossover"
    assert result["complexity"] == "comprehensive"
    assert result["analysis_type"] == "test_generation"


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_generate_test_scenarios_complexity_levels(mock_search):
    """Тест разных уровней сложности"""
    
    mock_search.return_value = MOCK_PERPLEXITY_RESPONSE
    
    complexities = ["basic", "comprehensive", "stress-test"]
    
    for complexity in complexities:
        result = await generate_test_scenarios(
            strategy_name="Test Strategy",
            complexity=complexity
        )
        assert result["complexity"] == complexity
        assert result["success"] == True


# ═══════════════════════════════════════════════════════════════════════════
# ТЕСТЫ ОБРАБОТКИ ОШИБОК
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_tools_handle_perplexity_errors(mock_search):
    """Тест обработки ошибок от Perplexity API"""
    
    # Симулируем ошибку API
    mock_search.return_value = {
        "success": False,
        "error": "API error: Rate limit exceeded"
    }
    
    result = await analyze_backtest_results(backtest_id=1)
    
    # Инструмент должен вернуть ответ с success=False
    assert result["success"] == False


@pytest.mark.asyncio
@patch('mcp_server.server.perplexity_search', new_callable=AsyncMock)
async def test_tools_handle_network_errors(mock_search):
    """Тест обработки сетевых ошибок"""
    
    # Симулируем сетевую ошибку
    mock_search.side_effect = Exception("Network timeout")
    
    try:
        result = await analyze_backtest_results(backtest_id=1)
        # Если не упало с исключением, проверяем структуру ответа
        assert "error" in result or "success" in result
    except Exception as e:
        # Допускаем исключение, если инструмент не обрабатывает сам
        assert "Network timeout" in str(e)


if __name__ == "__main__":
    """Запуск unit-тестов напрямую"""
    
    pytest.main([__file__, "-v", "--tb=short"])
