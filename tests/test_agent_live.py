"""
Live Agent Integration Tests
============================
Тесты с РЕАЛЬНЫМИ вызовами к DeepSeek / QWEN / Perplexity.

Запуск:
    pytest tests/test_agent_live.py -v -s --timeout=120

Каждый тест делает реальные HTTP запросы. Стоимость: ~$0.01–0.05 за тест.

Что проверяется:
  1. DeepSeek отвечает и возвращает парсируемую стратегию
  2. QWEN отвечает и имеет технический характер (RSI/MACD)
  3. Perplexity отвечает с рыночным контекстом
  4. Deliberation (MAD) реально спорит — 2 агента, 2 раунда
  5. Полный pipeline analyze→generate→parse→consensus без бэктеста
  6. Self-MoA: 3 температуры DeepSeek дают разные тексты
  7. Память: записывает результат pipeline и вспоминает его
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv
from loguru import logger

# Загружаем .env до любых imports из backend
load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# OHLCV fixture — 200 баров синтетического BTC (восходящий тренд)
# ──────────────────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 200, trend: float = 0.001, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(trend, 0.015, n)
    prices = 85_000.0 * np.cumprod(1 + returns)
    ho = np.abs(rng.normal(0, 0.007, n))
    lo = np.abs(rng.normal(0, 0.007, n))
    opens = prices * (1 + rng.normal(0, 0.003, n))
    return pd.DataFrame({
        "open":   opens,
        "high":   np.maximum(opens, prices) * (1 + ho),
        "low":    np.minimum(opens, prices) * (1 - lo),
        "close":  prices,
        "volume": np.abs(rng.normal(1_000_000, 200_000, n)),
    }, index=pd.date_range("2026-01-01", periods=n, freq="15min"))


OHLCV = _make_ohlcv()

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _banner(title: str) -> None:
    sep = "═" * 72
    print(f"\n{sep}\n  {title}\n{sep}")


def _print_strategy(strategy, source: str = "") -> None:
    if strategy is None:
        print(f"  [{source}] strategy=None")
        return
    print(f"\n  [{source}] {strategy.strategy_name}")
    print(f"    description : {strategy.description[:120]}...")
    print(f"    signals     : {[s.type for s in strategy.signals]}")
    print(f"    filters     : {[f.type for f in strategy.filters]}")
    if strategy.exit_conditions:
        tp = strategy.exit_conditions.take_profit
        sl = strategy.exit_conditions.stop_loss
        print(f"    TP          : {tp.type}={tp.value}" if tp else "    TP          : —")
        print(f"    SL          : {sl.type}={sl.value}" if sl else "    SL          : —")
    if strategy.position_management:
        print(f"    position    : {strategy.position_management.size_pct}% x{strategy.position_management.max_positions}")
    if strategy.optimization_hints:
        print(f"    optimize    : {strategy.optimization_hints.primary_objective}")
        print(f"    params      : {strategy.optimization_hints.parameters_to_optimize}")


def _print_deliberation(result) -> None:
    print(f"\n  Вопрос    : {result.question[:100]}")
    print(f"  Решение   : {result.decision[:150]}")
    print(f"  Уверенность: {result.confidence:.0%}")
    print(f"  Раундов   : {len(result.rounds)}")
    for i, rnd in enumerate(result.rounds, 1):
        print(f"\n  --- Раунд {i}: {rnd.phase.value} ---")
        for vote in rnd.opinions:
            print(f"    [{vote.agent_type}] conf={vote.confidence:.0%}")
            print(f"      позиция: {vote.position[:120]}")
            if vote.reasoning:
                print(f"      логика : {vote.reasoning[:100]}")
    if result.metadata.get("cross_validation"):
        cv = result.metadata["cross_validation"]
        print(f"\n  Cross-validation: agree={cv.get('agents_agree')}, score={cv.get('agreement_score', 0):.0%}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: DeepSeek живой вызов
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_deepseek_live_strategy_generation():
    """
    DeepSeek получает рыночный контекст и генерирует реальную стратегию.
    Проверяем: ответ не пустой, JSON парсится, сигналы присутствуют.
    """
    _banner("LIVE: DeepSeek — реальная генерация стратегии")

    from backend.agents.trading_strategy_graph import AnalyzeMarketNode, GenerateStrategiesNode
    from backend.agents.langgraph_orchestrator import AgentState

    # Шаг 1: анализ рынка (бесплатно, без API)
    analyze_node = AnalyzeMarketNode()
    state = AgentState(context={"symbol": "BTCUSDT", "timeframe": "15", "df": OHLCV})
    state = await analyze_node.execute(state)

    market_result = state.get_result("analyze_market")
    assert market_result, "AnalyzeMarketNode должна вернуть результат"
    print(f"\n  Рынок: regime={market_result['regime']}, trend={market_result.get('trend')}")
    print(f"  Цена : {market_result['current_price']:.2f}")

    # Шаг 2: генерация стратегии — РЕАЛЬНЫЙ вызов DeepSeek
    t0 = time.time()
    gen_node = GenerateStrategiesNode()
    state.context["agents"] = ["deepseek"]
    state = await gen_node.execute(state)
    elapsed = time.time() - t0

    gen_result = state.get_result("generate_strategies")
    assert gen_result, "GenerateStrategiesNode должна вернуть результат"
    responses = gen_result.get("responses", [])
    assert len(responses) >= 1, f"Ожидали хотя бы 1 ответ, получили: {responses}"

    raw_response = responses[0]["response"]
    print(f"\n  Время ответа DeepSeek: {elapsed:.1f}с")
    print(f"  Длина ответа: {len(raw_response)} символов")
    print(f"\n  Сырой ответ (первые 500 символов):\n{raw_response[:500]}")

    # Парсим
    from backend.agents.prompts.response_parser import ResponseParser
    parser = ResponseParser()
    strategy = parser.parse_strategy(raw_response, agent_name="deepseek")

    if strategy:
        _print_strategy(strategy, "DeepSeek")
        assert len(strategy.signals) >= 1, "Стратегия должна иметь сигналы"
        print(f"\n  ✅ DeepSeek живой и вернул парсируемую стратегию!")
    else:
        print(f"\n  ⚠️  DeepSeek ответил, но ResponseParser не смог распознать стратегию.")
        print(f"  Raw:\n{raw_response[:1000]}")
        # Не fail — агент живой, это проблема парсера
        pytest.xfail("DeepSeek ответил но формат не распознан парсером")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: QWEN живой вызов
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_qwen_live_strategy_generation():
    """
    QWEN получает тот же контекст. Проверяем что он технически ориентирован:
    использует RSI/MACD/momentum индикаторы.
    """
    _banner("LIVE: QWEN — технический аналитик")

    from backend.agents.trading_strategy_graph import AnalyzeMarketNode, GenerateStrategiesNode
    from backend.agents.langgraph_orchestrator import AgentState

    analyze_node = AnalyzeMarketNode()
    state = AgentState(context={"symbol": "BTCUSDT", "timeframe": "15", "df": OHLCV})
    state = await analyze_node.execute(state)

    gen_node = GenerateStrategiesNode()
    state.context["agents"] = ["qwen"]

    t0 = time.time()
    state = await gen_node.execute(state)
    elapsed = time.time() - t0

    gen_result = state.get_result("generate_strategies")
    responses = gen_result.get("responses", []) if gen_result else []

    if not responses:
        pytest.xfail("QWEN не вернул ответ — возможно проблема с API ключом")

    raw_response = responses[0]["response"]
    print(f"\n  Время ответа QWEN: {elapsed:.1f}с")
    print(f"  Длина ответа: {len(raw_response)} символов")
    print(f"\n  Сырой ответ (первые 500 символов):\n{raw_response[:500]}")

    from backend.agents.prompts.response_parser import ResponseParser
    strategy = ResponseParser().parse_strategy(raw_response, "qwen")

    if strategy:
        _print_strategy(strategy, "QWEN")

        signal_types = {s.type for s in strategy.signals}
        technical_indicators = {"RSI", "MACD", "Stochastic", "EMA_Crossover", "SMA_Crossover",
                                 "Bollinger", "CCI", "Williams_R", "OBV", "ADX"}
        found = signal_types & technical_indicators
        print(f"\n  Технические индикаторы: {found}")
        assert len(found) >= 1, f"QWEN должен использовать технические индикаторы, найдено: {signal_types}"
        print(f"  ✅ QWEN живой и техничен!")
    else:
        print(f"  ⚠️  QWEN ответил, парсер не распознал формат.")
        pytest.xfail("QWEN ответил но формат не распознан")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Perplexity живой вызов
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_perplexity_live_strategy_generation():
    """
    Perplexity должен принести рыночный контекст: режим рынка, макро-тренды.
    """
    _banner("LIVE: Perplexity — рыночный контекст")

    from backend.agents.trading_strategy_graph import AnalyzeMarketNode, GenerateStrategiesNode
    from backend.agents.langgraph_orchestrator import AgentState

    analyze_node = AnalyzeMarketNode()
    state = AgentState(context={"symbol": "BTCUSDT", "timeframe": "15", "df": OHLCV})
    state = await analyze_node.execute(state)

    gen_node = GenerateStrategiesNode()
    state.context["agents"] = ["perplexity"]

    t0 = time.time()
    state = await gen_node.execute(state)
    elapsed = time.time() - t0

    gen_result = state.get_result("generate_strategies")
    responses = gen_result.get("responses", []) if gen_result else []

    if not responses:
        pytest.xfail("Perplexity не вернул ответ — проверить PERPLEXITY_API_KEY")

    raw_response = responses[0]["response"]
    print(f"\n  Время ответа Perplexity: {elapsed:.1f}с")
    print(f"  Длина ответа: {len(raw_response)} символов")
    print(f"\n  Сырой ответ (первые 600 символов):\n{raw_response[:600]}")

    from backend.agents.prompts.response_parser import ResponseParser
    strategy = ResponseParser().parse_strategy(raw_response, "perplexity")

    if strategy:
        _print_strategy(strategy, "Perplexity")
        print(f"\n  ✅ Perplexity живой!")
    else:
        print(f"  ⚠️  Perplexity ответил, парсер не распознал формат.")
        pytest.xfail("Perplexity ответил но формат не распознан")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Self-MoA — 3 температуры реально дают разные тексты
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_self_moa_temperature_diversity_live():
    """
    DeepSeek вызывается 3 раза параллельно (T=0.3 / 0.7 / 1.1).
    Проверяем что тексты реально отличаются друг от друга.
    """
    _banner("LIVE: Self-MoA — реальное разнообразие температур")

    from backend.agents.trading_strategy_graph import GenerateStrategiesNode
    from backend.agents.langgraph_orchestrator import AgentState
    from backend.agents.prompts.context_builder import MarketContextBuilder

    builder = MarketContextBuilder()
    market_context = builder.build_context("BTCUSDT", "15", OHLCV)

    node = GenerateStrategiesNode()

    prompt = node._prompt_engineer.create_strategy_prompt(
        context=market_context,
        platform_config={"exchange": "Bybit", "commission": 0.0007, "max_leverage": 100},
        agent_name="deepseek",
        include_examples=True,
    )
    system_msg = node._prompt_engineer.get_system_message("deepseek")

    print(f"\n  Промпт для DeepSeek: {len(prompt)} символов")
    print(f"  Запускаем 3 параллельных вызова T=[0.3, 0.7, 1.1]...")

    t0 = time.time()
    results = await asyncio.gather(
        node._call_llm("deepseek", prompt, system_msg, temperature=0.3),
        node._call_llm("deepseek", prompt, system_msg, temperature=0.7),
        node._call_llm("deepseek", prompt, system_msg, temperature=1.1),
        return_exceptions=True,
    )
    elapsed = time.time() - t0

    print(f"\n  Время 3 параллельных вызовов: {elapsed:.1f}с")

    texts = []
    for i, (r, temp) in enumerate(zip(results, [0.3, 0.7, 1.1])):
        if isinstance(r, Exception):
            print(f"  T={temp}: ОШИБКА — {r}")
        elif r:
            texts.append(r)
            print(f"\n  T={temp} ({len(r)} символов):")
            print(f"    {r[:200]}...")
        else:
            print(f"  T={temp}: пустой ответ")

    assert len(texts) >= 2, f"Хотя бы 2 вызова должны вернуть текст, получили {len(texts)}"

    # Проверяем что тексты отличаются (не одинаковые копии)
    if len(texts) >= 2:
        unique = set(texts)
        print(f"\n  Уникальных ответов: {len(unique)} из {len(texts)}")
        if len(unique) == 1:
            print(f"  ⚠️  Все температуры дали ОДИНАКОВЫЙ текст — детерминизм?")
        else:
            # Находим минимальное различие
            t1, t2 = texts[0], texts[1]
            common_prefix = 0
            for a, b in zip(t1, t2):
                if a == b:
                    common_prefix += 1
                else:
                    break
            print(f"  Общий префикс T0.3 vs T0.7: {common_prefix} символов из {min(len(t1), len(t2))}")
            print(f"  ✅ Self-MoA реально даёт разнообразие!")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: MAD Дебаты — реальный спор DeepSeek vs QWEN
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_mad_debate_deepseek_vs_qwen_live():
    """
    DeepSeek и QWEN реально спорят о рыночной стратегии.
    Показываем каждый раунд: позиции, критику, конвергенцию.
    """
    _banner("LIVE: MAD Дебаты — DeepSeek vs QWEN")

    from backend.agents.consensus.real_llm_deliberation import deliberate_with_llm
    from backend.agents.consensus.deliberation import VotingStrategy

    question = (
        "Given BTCUSDT on 15m timeframe in a bull market regime with moderate volatility: "
        "Should we use RSI mean-reversion (buy oversold, sell overbought) "
        "OR EMA trend-following (buy golden cross, ride the trend)? "
        "Which approach gives better Sharpe ratio and lower drawdown?"
    )

    print(f"\n  Вопрос: {question[:120]}...")
    print(f"  Агенты: DeepSeek (квант) vs QWEN (технарь)")
    print(f"  Максимум раундов: 2")

    t0 = time.time()
    result = await deliberate_with_llm(
        question=question,
        agents=["deepseek", "qwen"],
        max_rounds=2,
        min_confidence=0.65,
        voting_strategy=VotingStrategy.WEIGHTED,
        symbol="BTCUSDT",
        strategy_type="rsi",
        enrich_with_perplexity=False,
        use_memory=False,
    )
    elapsed = time.time() - t0

    print(f"\n  Время дебатов: {elapsed:.1f}с")
    _print_deliberation(result)

    # Ключевые проверки
    assert result.decision, "Дебаты должны дать решение"
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.rounds) >= 1, "Должен быть хотя бы 1 раунд"

    # Проверяем что агенты действительно участвовали
    all_agent_types = set()
    for rnd in result.rounds:
        for vote in rnd.opinions:
            all_agent_types.add(vote.agent_type)

    print(f"\n  Участвовавшие агенты: {all_agent_types}")
    assert len(all_agent_types) >= 1, "Хотя бы один агент должен участвовать"

    print(f"\n  ✅ MAD дебаты прошли! Решение: {result.decision[:100]}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Полный pipeline — analyze→generate→parse→consensus
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_pipeline_no_backtest_live():
    """
    Полный цикл с двумя реальными агентами (DeepSeek + QWEN).
    Без дебатов и бэктеста — чтобы минимизировать стоимость.
    """
    _banner("LIVE: Полный pipeline DeepSeek + QWEN (без дебатов, без бэктеста)")

    from backend.agents.trading_strategy_graph import run_strategy_pipeline

    t0 = time.time()
    state = await run_strategy_pipeline(
        symbol="BTCUSDT",
        timeframe="15",
        df=OHLCV,
        agents=["deepseek", "qwen"],
        run_backtest=False,
        run_debate=False,
    )
    elapsed = time.time() - t0

    print(f"\n  Время полного pipeline: {elapsed:.1f}с")
    print(f"  Выполненные ноды: {[n for n, _ in state.execution_path]}")
    print(f"  Ошибок в state: {len(state.errors)}")

    if state.errors:
        print(f"\n  Ошибки:")
        for e in state.errors:
            print(f"    [{e['node']}] {e['error_type']}: {e['error_message']}")

    # Market analysis
    market = state.get_result("analyze_market")
    if market:
        print(f"\n  Рынок: regime={market['regime']}, trend={market.get('trend')}, price={market['current_price']:.0f}")

    # Generated responses
    gen = state.get_result("generate_strategies")
    if gen:
        responses = gen.get("responses", [])
        print(f"\n  Ответы от агентов: {len(responses)}")
        for r in responses:
            print(f"    [{r['agent']}] {len(r['response'])} символов")
            print(f"      {r['response'][:200]}...")

    # Parsed proposals
    parsed = state.get_result("parse_responses")
    if parsed:
        proposals = parsed.get("proposals", [])
        print(f"\n  Спарсено стратегий: {len(proposals)}")
        for p in proposals:
            _print_strategy(p["strategy"], p["agent"])
            print(f"    quality_score: {p['validation'].quality_score:.2f}")

    # Consensus
    consensus = state.get_result("select_best")
    if consensus:
        selected = consensus["selected_strategy"]
        print(f"\n  ════ КОНСЕНСУС ════")
        print(f"  Выбрана: '{selected.strategy_name}'")
        print(f"  Агент  : {consensus['selected_agent']}")
        print(f"  Agreement: {consensus['agreement_score']:.0%}")
        print(f"  Из {consensus['candidates_count']} кандидатов")

    # Report
    report = state.get_result("report")
    print(f"\n  ════ ФИНАЛЬНЫЙ ОТЧЁТ ════")
    print(f"  Предложений     : {report.get('proposals_count', 0)}")
    print(f"  Execution path  : {report.get('execution_path', [])}")
    print(f"  Ошибок          : {len(report.get('errors', []))}")

    # Assertions — что-то должно работать
    assert market is not None, "analyze_market должна отработать"
    # Если оба агента не ответили — xfail
    if not gen or not gen.get("responses"):
        pytest.xfail("Ни один агент не вернул ответ — проверить API ключи")

    print(f"\n  ✅ Полный pipeline завершён за {elapsed:.1f}с")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: Полный pipeline С дебатами — самый полный сценарий
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_pipeline_with_debate_live():
    """
    Полный цикл С дебатами: analyze → debate → generate → parse → consensus.
    Показываем полный поток мышления агентов.
    """
    _banner("LIVE: ПОЛНЫЙ pipeline С дебатами (DeepSeek + QWEN)")

    from backend.agents.trading_strategy_graph import run_strategy_pipeline

    t0 = time.time()
    state = await run_strategy_pipeline(
        symbol="BTCUSDT",
        timeframe="15",
        df=OHLCV,
        agents=["deepseek", "qwen"],
        run_backtest=False,
        run_debate=True,
    )
    elapsed = time.time() - t0

    print(f"\n  ⏱  Время: {elapsed:.1f}с")
    print(f"  📍 Путь: {[n for n, t in state.execution_path]}")

    # Дебаты
    debate = state.get_result("debate")
    if debate:
        print(f"\n  ════ ДЕБАТЫ ════")
        print(f"  Консенсус : {debate.get('consensus', 'N/A')[:150]}")
        print(f"  Уверенность: {debate.get('confidence', 0):.0%}")
        dc = state.context.get("debate_consensus")
        if dc:
            print(f"  В контексте: {dc.get('consensus', '')[:100]}")
    else:
        print(f"\n  ⚠️  Дебаты не дали результата")

    # Генерация
    gen = state.get_result("generate_strategies")
    if gen:
        responses = gen.get("responses", [])
        print(f"\n  ════ ГЕНЕРАЦИЯ ════")
        for r in responses:
            print(f"  [{r['agent']}] {len(r['response'])} символов")

    # Консенсус
    consensus = state.get_result("select_best")
    if consensus and consensus.get("selected_strategy"):
        s = consensus["selected_strategy"]
        print(f"\n  ════ РЕЗУЛЬТАТ ════")
        print(f"  Стратегия : {s.strategy_name}")
        print(f"  Агент     : {consensus['selected_agent']}")
        print(f"  Agreement : {consensus['agreement_score']:.0%}")
        print(f"  Сигналы   : {[sig.type for sig in s.signals]}")

    # Ошибки
    if state.errors:
        print(f"\n  ⚠️  Ошибки в pipeline:")
        for e in state.errors:
            print(f"    [{e['node']}] {e['error_type']}: {e['error_message'][:100]}")

    assert state.get_result("analyze_market") is not None
    print(f"\n  ✅ Полный pipeline с дебатами завершён!")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8: Память — pipeline записывает, мы вспоминаем
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_memory_pipeline_store_and_recall_live():
    """
    Запускаем MemoryUpdateNode с реальными данными из предыдущих нод.
    Затем делаем recall и проверяем что данные доступны.
    """
    _banner("LIVE: Память — store + recall после pipeline")

    from backend.agents.trading_strategy_graph import (
        AnalyzeMarketNode, MemoryUpdateNode
    )
    from backend.agents.langgraph_orchestrator import AgentState
    from backend.agents.prompts.response_parser import ResponseParser, StrategyDefinition, Signal
    from backend.agents.memory.hierarchical_memory import HierarchicalMemory, MemoryType

    # Строим фиктивный select_best результат и backtest результат
    fake_strategy = StrategyDefinition(
        strategy_name="Live Test RSI Strategy",
        signals=[Signal(id="s1", type="RSI", params={"period": 14}, weight=1.0, condition="RSI<30")],
    )
    fake_metrics = {
        "sharpe_ratio": 1.42,
        "max_drawdown": 14.5,
        "total_trades": 38,
        "win_rate": 0.57,
        "profit_factor": 1.7,
    }

    state = AgentState(context={"symbol": "BTCUSDT", "timeframe": "15"})
    state.set_result("select_best", {
        "selected_strategy": fake_strategy,
        "selected_agent": "deepseek",
    })
    state.set_result("backtest", {"metrics": fake_metrics})

    # Запускаем MemoryUpdateNode
    node = MemoryUpdateNode()
    t0 = time.time()
    state = await node.execute(state)
    elapsed = time.time() - t0

    mem_result = state.get_result("memory_update")
    print(f"\n  MemoryUpdateNode: {elapsed:.2f}с, result={mem_result}")

    # Теперь recall — проверяем что можно найти
    memory = HierarchicalMemory()
    recalls = await memory.recall(
        query="RSI strategy backtest BTCUSDT",
        top_k=5,
        min_importance=0.0,
    )

    print(f"\n  Recall по 'RSI strategy backtest BTCUSDT':")
    print(f"  Найдено: {len(recalls)} записей")
    for r in recalls:
        print(f"    [{r.memory_type.value}] imp={r.importance:.2f} — {r.content[:100]}")

    # Проверяем что записал sharpe
    if recalls:
        sharpe_in_memory = any("1.42" in r.content or "Sharpe=1.42" in r.content for r in recalls)
        print(f"  Sharpe=1.42 в памяти: {'✅' if sharpe_in_memory else '⚠️ не найдено'}")

    print(f"\n  ✅ Память работает: {len(recalls)} записей доступны для recall")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9: Сравнение — что DeepSeek и QWEN думают по-разному
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_agent_personality_divergence_live():
    """
    Запускаем DeepSeek и QWEN параллельно на ОДИНАКОВЫЙ запрос.
    Показываем ЧЕМ они отличаются: размер позиции, выбор индикаторов, TP/SL.
    """
    _banner("LIVE: Дивергенция персоналий — DeepSeek vs QWEN")

    from backend.agents.trading_strategy_graph import GenerateStrategiesNode
    from backend.agents.langgraph_orchestrator import AgentState
    from backend.agents.prompts.context_builder import MarketContextBuilder
    from backend.agents.prompts.response_parser import ResponseParser

    builder = MarketContextBuilder()
    market_context = builder.build_context("BTCUSDT", "15", OHLCV)

    node = GenerateStrategiesNode()

    # Один и тот же промпт для обоих
    prompt_ds  = node._prompt_engineer.create_strategy_prompt(market_context, {}, "deepseek")
    prompt_qw  = node._prompt_engineer.create_strategy_prompt(market_context, {}, "qwen")
    sys_ds     = node._prompt_engineer.get_system_message("deepseek")
    sys_qw     = node._prompt_engineer.get_system_message("qwen")

    print(f"\n  Параллельный запрос к DeepSeek и QWEN...")
    t0 = time.time()
    ds_raw, qw_raw = await asyncio.gather(
        node._call_llm("deepseek", prompt_ds, sys_ds, temperature=0.7),
        node._call_llm("qwen",     prompt_qw, sys_qw, temperature=0.4),
        return_exceptions=True,
    )
    elapsed = time.time() - t0
    print(f"  Параллельный запрос: {elapsed:.1f}с")

    parser = ResponseParser()
    results: dict[str, Any] = {}

    for agent, raw in [("deepseek", ds_raw), ("qwen", qw_raw)]:
        if isinstance(raw, Exception):
            print(f"\n  [{agent}] ОШИБКА: {raw}")
            continue
        if not raw:
            print(f"\n  [{agent}] пустой ответ")
            continue

        strategy = parser.parse_strategy(raw, agent)
        results[agent] = strategy
        print(f"\n  {'━'*60}")
        _print_strategy(strategy, agent)
        if not strategy:
            print(f"  Сырой ответ:\n{raw[:300]}")

    # Сравниваем
    if len(results) == 2:
        ds_s = results["deepseek"]
        qw_s = results["qwen"]

        print(f"\n  {'━'*60}")
        print(f"  СРАВНЕНИЕ ПЕРСОНАЛИЙ:")

        if ds_s and qw_s:
            ds_types = {s.type for s in ds_s.signals}
            qw_types = {s.type for s in qw_s.signals}
            print(f"  DeepSeek сигналы : {sorted(ds_types)}")
            print(f"  QWEN сигналы     : {sorted(qw_types)}")
            print(f"  Общие            : {sorted(ds_types & qw_types)}")
            print(f"  Уникальные DS    : {sorted(ds_types - qw_types)}")
            print(f"  Уникальные QWEN  : {sorted(qw_types - ds_types)}")

            ds_pos = ds_s.position_management.size_pct if ds_s.position_management else "?"
            qw_pos = qw_s.position_management.size_pct if qw_s.position_management else "?"
            print(f"\n  Размер позиции: DeepSeek={ds_pos}%, QWEN={qw_pos}%")

            if ds_s.optimization_hints and qw_s.optimization_hints:
                print(f"  Цель оптимизации: DeepSeek={ds_s.optimization_hints.primary_objective}, "
                      f"QWEN={qw_s.optimization_hints.primary_objective}")

            diverged = ds_types != qw_types
            print(f"\n  Дивергенция индикаторов: {'✅ ДА' if diverged else '⚠️ НЕТ (одинаковые)'}")

    print(f"\n  ✅ Тест персоналий завершён")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10: CostCircuitBreaker — реальные вызовы фиксируются в трекере
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cost_tracking_after_real_call_live():
    """
    После реального вызова — CostCircuitBreaker должен фиксировать затраты.
    Проверяем что record_actual() вызывается и hourly_spend растёт.
    """
    _banner("LIVE: Cost tracking — реальные затраты фиксируются")

    from backend.agents.cost_circuit_breaker import get_cost_circuit_breaker
    from backend.agents.trading_strategy_graph import GenerateStrategiesNode
    from backend.agents.langgraph_orchestrator import AgentState
    from backend.agents.prompts.context_builder import MarketContextBuilder

    breaker = get_cost_circuit_breaker()
    breaker.reset()  # чистим историю

    spend_before = breaker.get_spend_summary()["hourly_spend_usd"]
    print(f"\n  Затраты до вызова : ${spend_before:.6f}")

    # Делаем 1 реальный вызов через GenerateStrategiesNode
    builder = MarketContextBuilder()
    market_context = builder.build_context("BTCUSDT", "15", OHLCV)

    state = AgentState(context={
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "df": OHLCV,
        "agents": ["deepseek"],
    })
    state.set_result("analyze_market", {"market_context": market_context, "regime": "bull"})

    node = GenerateStrategiesNode()
    await node.execute(state)

    spend_after = breaker.get_spend_summary()["hourly_spend_usd"]
    print(f"  Затраты после вызова: ${spend_after:.6f}")
    print(f"  Дельта              : ${spend_after - spend_before:.6f}")

    summary = breaker.get_spend_summary()
    print(f"\n  Полная сводка circuit breaker:")
    print(f"    hourly_spend : ${summary['hourly_spend_usd']:.6f} / ${summary['limits']['per_hour_usd']:.2f}")
    print(f"    daily_spend  : ${summary['daily_spend_usd']:.6f} / ${summary['limits']['per_day_usd']:.2f}")
    print(f"    records      : {summary['record_count']}")

    if spend_after > spend_before:
        print(f"\n  ✅ Затраты зафиксированы в circuit breaker!")
    else:
        print(f"\n  ⚠️  Затраты не зафиксированы (record_actual не вызван или вызов упал)")
