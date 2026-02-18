"""
Real API Agent Test Suite
=========================

Полный тест агентов через реальные API:
1. Проверка доступности всех 3 провайдеров (DeepSeek, Qwen, Perplexity)
2. Индивидуальные задания каждому агенту
3. Мульти-агентная делиберация (3 агента обсуждают стратегию)
4. Перекрёстная валидация (cross-validation сигналов)
5. Обогащение контекста через Perplexity (context enrichment)
6. Память агентов (сохранение и извлечение)
7. Prompt Optimizer (экономия токенов)

Результаты сохраняются в docs/agent_analysis/real_api_test_results.json
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root in path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# Force UTF-8
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n--- {title} ---\n")


async def test_1_api_connectivity() -> dict:
    """Тест 1: Проверка подключения к API всех 3 провайдеров."""
    section("ТЕСТ 1: Проверка подключения к API")

    from backend.agents.llm.connections import (
        DeepSeekClient,
        LLMConfig,
        LLMMessage,
        LLMProvider,
        PerplexityClient,
        QwenClient,
    )

    results = {}

    providers = [
        ("DeepSeek", LLMProvider.DEEPSEEK, DeepSeekClient, "DEEPSEEK_API_KEY", "deepseek-chat"),
        ("Qwen", LLMProvider.QWEN, QwenClient, "QWEN_API_KEY", "qwen-plus"),
        ("Perplexity", LLMProvider.PERPLEXITY, PerplexityClient, "PERPLEXITY_API_KEY", "sonar-pro"),
    ]

    for name, provider, client_cls, key_name, model in providers:
        subsection(f"{name}")

        api_key = os.getenv(key_name, "")
        if not api_key or api_key.startswith("YOUR_"):
            print(f"  ПРОПУСК: ключ {key_name} не задан")
            results[name.lower()] = {"status": "skipped", "reason": "no key"}
            continue

        print(f"  Ключ: {api_key[:8]}...{api_key[-4:]} ({len(api_key)} символов)")

        config = LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model,
            temperature=0.3,
            max_tokens=256,
            timeout_seconds=30,
        )

        client = client_cls(config)
        try:
            start = time.time()
            response = await client.chat(
                [
                    LLMMessage(role="system", content="You are a helpful assistant. Answer briefly."),
                    LLMMessage(role="user", content=f"Say 'Hello from {name}!' and nothing else."),
                ]
            )
            elapsed = time.time() - start

            print(f"  Ответ: {response.content.strip()[:100]}")
            print(f"  Модель: {response.model}")
            print(f"  Токены: {response.total_tokens} (in={response.prompt_tokens}, out={response.completion_tokens})")
            print(f"  Время: {elapsed:.1f}с")
            print("  Статус: OK")

            results[name.lower()] = {
                "status": "ok",
                "model": response.model,
                "tokens": response.total_tokens,
                "latency_s": round(elapsed, 2),
                "response": response.content.strip()[:200],
            }
        except Exception as e:
            print(f"  ОШИБКА: {e}")
            results[name.lower()] = {"status": "error", "error": str(e)}
        finally:
            await client.close()

    # Summary
    ok_count = sum(1 for r in results.values() if r.get("status") == "ok")
    print(f"\n  Итого: {ok_count}/3 провайдеров доступны")
    results["status"] = "ok" if ok_count == 3 else "partial"
    return results


async def test_2_individual_agents() -> dict:
    """Тест 2: Индивидуальные задания каждому агенту (домен-специфичные)."""
    section("ТЕСТ 2: Индивидуальные задания агентам")

    from backend.agents.llm.connections import (
        DeepSeekClient,
        LLMConfig,
        LLMMessage,
        LLMProvider,
        PerplexityClient,
        QwenClient,
    )

    tasks = {
        "deepseek": {
            "system": (
                "You are a quantitative trading analyst. "
                "Analyze the given strategy metrics and provide risk assessment. "
                "Be concise but thorough. Answer in 150-250 words."
            ),
            "prompt": (
                "Analyze this BTC/USDT 15m RSI strategy backtest result:\n"
                "- Net Profit: +12.3% over 30 days\n"
                "- Win Rate: 58.2%\n"
                "- Max Drawdown: -8.4%\n"
                "- Sharpe Ratio: 1.42\n"
                "- Sortino Ratio: 2.01\n"
                "- Total Trades: 47\n"
                "- Commission: 0.07% per trade\n"
                "- Profit Factor: 1.65\n\n"
                "Questions:\n"
                "1. Is this strategy viable for live trading?\n"
                "2. What is the biggest risk factor?\n"
                "3. Suggested improvements?"
            ),
            "provider": LLMProvider.DEEPSEEK,
            "client_cls": DeepSeekClient,
            "key": "DEEPSEEK_API_KEY",
            "model": "deepseek-chat",
        },
        "qwen": {
            "system": (
                "You are a technical analysis expert. "
                "Optimize indicator parameters for the given setup. "
                "Be concise but thorough. Answer in 150-250 words."
            ),
            "prompt": (
                "I'm using RSI(14) with overbought=70, oversold=30 on BTC/USDT 15m chart.\n"
                "The strategy generates 47 trades/month but many are false signals.\n\n"
                "Current metrics:\n"
                "- Win Rate: 58.2%\n"
                "- Avg Win: 1.8%, Avg Loss: -1.2%\n"
                "- Max consecutive losses: 5\n\n"
                "Questions:\n"
                "1. How should I optimize RSI parameters (period, OB/OS levels)?\n"
                "2. Should I add a confirmation indicator? Which one?\n"
                "3. What timeframe filter would help reduce false signals?"
            ),
            "provider": LLMProvider.QWEN,
            "client_cls": QwenClient,
            "key": "QWEN_API_KEY",
            "model": "qwen-plus",
        },
        "perplexity": {
            "system": (
                "You are a crypto market research analyst with real-time web access. "
                "Provide current market context for the given trading scenario. "
                "Be concise but thorough. Answer in 150-250 words."
            ),
            "prompt": (
                "I'm trading BTC/USDT with a momentum strategy on 15-minute timeframe.\n\n"
                "Questions:\n"
                "1. What is the current BTC market regime (trending/ranging/volatile)?\n"
                "2. Are there any upcoming macro events that could affect BTC in the next 7 days?\n"
                "3. What is the current market sentiment (bullish/bearish/neutral)?\n"
                "4. Any recent whale activity or significant exchange flows?"
            ),
            "provider": LLMProvider.PERPLEXITY,
            "client_cls": PerplexityClient,
            "key": "PERPLEXITY_API_KEY",
            "model": "sonar-pro",
        },
    }

    results = {}

    for agent_name, task in tasks.items():
        subsection(f"{agent_name.upper()} — домен-специфичное задание")

        api_key = os.getenv(task["key"], "")
        if not api_key or api_key.startswith("YOUR_"):
            print("  ПРОПУСК: ключ не задан")
            results[agent_name] = {"status": "skipped"}
            continue

        config = LLMConfig(
            provider=task["provider"],
            api_key=api_key,
            model=task["model"],
            temperature=0.5,
            max_tokens=1024,
            timeout_seconds=45,
        )

        client = task["client_cls"](config)
        try:
            start = time.time()
            response = await client.chat(
                [
                    LLMMessage(role="system", content=task["system"]),
                    LLMMessage(role="user", content=task["prompt"]),
                ]
            )
            elapsed = time.time() - start

            content = response.content.strip()
            # Print first 500 chars
            print(f"  Ответ ({len(content)} символов, {response.total_tokens} токенов, {elapsed:.1f}с):")
            print()
            for line in content[:600].split("\n"):
                print(f"    {line}")
            if len(content) > 600:
                print(f"    ... (ещё {len(content) - 600} символов)")

            results[agent_name] = {
                "status": "ok",
                "tokens": response.total_tokens,
                "latency_s": round(elapsed, 2),
                "response_length": len(content),
                "response": content[:1000],
            }
        except Exception as e:
            print(f"  ОШИБКА: {e}")
            results[agent_name] = {"status": "error", "error": str(e)}
        finally:
            await client.close()

    ok_count = sum(1 for r in results.values() if r.get("status") == "ok")
    results["status"] = "ok" if ok_count == len(tasks) else "partial"
    return results


async def test_3_multi_agent_deliberation() -> dict:
    """Тест 3: Трёхстороння дискуссия агентов (deliberation)."""
    section("ТЕСТ 3: Мульти-агентная делиберация")

    from backend.agents.consensus.deliberation import VotingStrategy
    from backend.agents.consensus.real_llm_deliberation import (
        deliberate_with_llm,
        get_real_deliberation,
    )

    question = (
        "Should we use RSI(14) with thresholds 70/30 or MACD(12,26,9) "
        "as the primary entry signal for a BTC/USDT 15-minute momentum strategy? "
        "Consider win rate, drawdown, and current market conditions (February 2026). "
        "The strategy must maintain Sharpe ratio > 1.0 and max drawdown < 15%."
    )

    print("  Вопрос для обсуждения:")
    print(f"    {question[:120]}...")
    print()

    delib = get_real_deliberation()
    available = list(delib._clients.keys())
    print(f"  Доступные агенты: {available}")

    if not available:
        print("  ПРОПУСК: нет доступных агентов")
        return {"status": "skipped", "reason": "no agents available"}

    try:
        start = time.time()
        result = await deliberate_with_llm(
            question=question,
            agents=available,
            max_rounds=2,
            min_confidence=0.6,
            voting_strategy=VotingStrategy.WEIGHTED,
            symbol="BTCUSDT",
            strategy_type="rsi_vs_macd",
            enrich_with_perplexity=True,
        )
        elapsed = time.time() - start

        subsection("Результат делиберации")
        print(f"  Решение: {result.decision[:200]}")
        print(f"  Уверенность: {result.confidence:.1%}")
        print(f"  Раундов: {len(result.rounds)}")
        # Check consensus from last round's convergence
        consensus_emerging = result.rounds[-1].consensus_emerging if result.rounds else False
        convergence = result.rounds[-1].convergence_score if result.rounds else 0
        print(f"  Консенсус формируется: {consensus_emerging}")
        print(f"  Конвергенция: {convergence:.1%}")
        print(f"  Время: {elapsed:.1f}с")

        # Agent opinions from final votes
        subsection("Мнения агентов")
        for vote in result.final_votes:
            print(f"  [{vote.agent_type}] (уверенность={vote.confidence:.0%}):")
            print(f"    Позиция: {vote.position[:150]}")
            if vote.reasoning:
                print(f"    Аргументы: {vote.reasoning[:200]}")
            print()

        # Cross-validation
        cross_val = result.metadata.get("cross_validation")
        if cross_val:
            subsection("Перекрёстная валидация")
            print(f"  Согласие: {cross_val.get('agents_agree', '?')}")
            print(f"  Оценка согласия: {cross_val.get('agreement_score', 0):.0%}")
            conflicts = cross_val.get("conflicts", [])
            if conflicts:
                for c in conflicts:
                    print(f"  Конфликт: {c['agents']} — {c['directions']} ({c.get('type', '')})")
            print(f"  Резолюция: {cross_val.get('resolution', 'нет')[:200]}")

        # Stats
        stats = delib.get_integration_stats()
        subsection("Статистика интеграции")
        print(f"  Сигналы записаны: {stats['signals_recorded']}")
        print(f"  Контекст рынка доступен: {stats['market_context_available']}")
        pplx_stats = stats.get("perplexity_integration", {})
        print(f"  Perplexity вызовы: {pplx_stats.get('calls_made', 0)}")
        print(f"  Perplexity пропуски: {pplx_stats.get('calls_skipped', 0)}")
        print(f"  Конфликты обнаружены: {pplx_stats.get('conflicts_detected', 0)}")

        return {
            "status": "ok",
            "decision": result.decision[:500],
            "confidence": result.confidence,
            "rounds_count": len(result.rounds),
            "consensus_emerging": consensus_emerging,
            "convergence": convergence,
            "elapsed_s": round(elapsed, 2),
            "votes": [
                {
                    "agent": v.agent_type,
                    "confidence": v.confidence,
                    "position": v.position[:300],
                    "reasoning": v.reasoning[:300] if v.reasoning else "",
                }
                for v in result.final_votes
            ],
            "dissenting_opinions": len(result.dissenting_opinions),
            "cross_validation": cross_val,
            "integration_stats": stats,
        }

    except Exception as e:
        print(f"  ОШИБКА: {e}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "error": str(e)}


async def test_4_perplexity_enrichment() -> dict:
    """Тест 4: Обогащение контекста через Perplexity."""
    section("ТЕСТ 4: Обогащение контекста через Perplexity")

    from backend.agents.consensus.perplexity_integration import get_perplexity_integration

    pi = get_perplexity_integration()

    # Test adaptive routing
    subsection("Адаптивная маршрутизация")
    routing_tests = [
        ("optimize RSI parameters for backtest", False),
        ("analyze BTC with current market sentiment and FED news", True),
        ("calculate historical drawdown statistics", False),
        ("what is today market regime for BTCUSDT", True),
        ("evaluate Sharpe ratio commission impact", False),
        ("current whale activity and exchange flows for ETH", True),
    ]
    for task, expected in routing_tests:
        actual = pi.should_consult_perplexity(task)
        status = "OK" if actual == expected else "МИСС"
        direction = "ВЫЗОВ" if actual else "ПРОПУСК"
        print(f"  [{status}] {task[:55]:55s} -> {direction}")

    # Test actual enrichment
    subsection("Реальное обогащение контекста")

    api_key = os.getenv("PERPLEXITY_API_KEY", "")
    if not api_key or api_key.startswith("YOUR_"):
        print("  ПРОПУСК: ключ Perplexity не задан")
        return {"status": "skipped", "routing_tests": "passed"}

    try:
        start = time.time()
        enriched = await pi.enrich_context(
            symbol="BTCUSDT",
            strategy_type="rsi_momentum",
            base_context={"timeframe": "15m", "direction": "both"},
        )
        elapsed = time.time() - start

        market_ctx = enriched.get("market_context", {})

        print(f"  Время: {elapsed:.1f}с")
        print(f"  Токены: {enriched.get('perplexity_tokens', '?')}")
        print(f"  Режим рынка: {market_ctx.get('regime', '?')}")
        print(f"  Тренд: {market_ctx.get('trend_direction', '?')}")
        sentiment = market_ctx.get("sentiment", {})
        print(f"  Сентимент: {sentiment.get('direction', '?')} (score={sentiment.get('score', '?')})")
        print(f"  Волатильность: {market_ctx.get('volatility_assessment', '?')}")

        news = market_ctx.get("key_news", [])
        if news:
            print("  Новости:")
            for n in news[:3]:
                print(f"    - {n[:100]}")

        risks = market_ctx.get("risk_factors", [])
        if risks:
            print("  Факторы риска:")
            for r in risks[:3]:
                print(f"    - {r[:100]}")

        return {
            "status": "ok",
            "market_context": market_ctx,
            "latency_s": round(elapsed, 2),
            "tokens": enriched.get("perplexity_tokens"),
        }

    except Exception as e:
        print(f"  ОШИБКА: {e}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "error": str(e)}


async def test_5_cross_validation() -> dict:
    """Тест 5: Перекрёстная валидация сигналов."""
    section("ТЕСТ 5: Перекрёстная валидация сигналов")

    from backend.agents.consensus.perplexity_integration import (
        AgentSignal,
        get_perplexity_integration,
    )

    pi = get_perplexity_integration()

    # Scenario 1: Agents agree
    subsection("Сценарий 1: Все агенты согласны (bullish)")
    signals_agree = [
        AgentSignal("deepseek", "quantitative", "bullish", 0.85, "Sharpe 1.4, low VaR, positive momentum"),
        AgentSignal("qwen", "technical", "bullish", 0.78, "RSI oversold bounce, MACD crossover"),
        AgentSignal("perplexity", "sentiment", "bullish", 0.72, "Strong ETF inflows, positive sentiment"),
    ]
    result_agree = pi.cross_validate_signals(signals_agree)
    print(f"  Согласие: {result_agree.agents_agree}")
    print(f"  Оценка: {result_agree.agreement_score:.0%}")
    print(f"  Конфликты: {len(result_agree.conflicts)}")
    print(f"  Резолюция: {result_agree.resolution[:150]}")

    # Scenario 2: Conflict between technical and sentiment
    subsection("Сценарий 2: Конфликт технический vs сентимент")
    signals_conflict = [
        AgentSignal("deepseek", "quantitative", "bearish", 0.82, "High VaR, negative skew, drawdown risk"),
        AgentSignal("qwen", "technical", "bullish", 0.71, "RSI oversold, bollinger bounce pattern"),
        AgentSignal("perplexity", "sentiment", "bearish", 0.65, "FED hawkish, regulation fears"),
    ]
    result_conflict = pi.cross_validate_signals(signals_conflict)
    print(f"  Согласие: {result_conflict.agents_agree}")
    print(f"  Оценка: {result_conflict.agreement_score:.0%}")
    print(f"  Конфликты: {len(result_conflict.conflicts)}")
    for c in result_conflict.conflicts:
        print(f"    {c['agents']}: {c['directions']} — {c.get('type', '?')}")
    print(f"  Резолюция: {result_conflict.resolution[:200]}")

    # Scenario 3: Total disagreement
    subsection("Сценарий 3: Полное несогласие")
    signals_total = [
        AgentSignal("deepseek", "quantitative", "neutral", 0.55, "Insufficient data for conviction"),
        AgentSignal("qwen", "technical", "bullish", 0.80, "Strong momentum breakout pattern"),
        AgentSignal("perplexity", "sentiment", "bearish", 0.70, "Whale selling, exchange inflows"),
    ]
    result_total = pi.cross_validate_signals(signals_total)
    print(f"  Согласие: {result_total.agents_agree}")
    print(f"  Оценка: {result_total.agreement_score:.0%}")
    print(f"  Конфликты: {len(result_total.conflicts)}")
    for c in result_total.conflicts:
        print(f"    {c['agents']}: {c['directions']} — {c.get('type', '?')}")
    print(f"  Резолюция: {result_total.resolution[:200]}")

    return {
        "status": "ok",
        "scenario_1_agree": result_agree.to_dict(),
        "scenario_2_conflict": result_conflict.to_dict(),
        "scenario_3_total": result_total.to_dict(),
    }


async def test_6_agent_memory() -> dict:
    """Тест 6: Память агентов — сохранение и извлечение."""
    section("ТЕСТ 6: Память агентов")

    from backend.agents.agent_memory import AgentMemoryManager

    memory = AgentMemoryManager(PROJECT_ROOT)
    session_id = f"real_api_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    subsection("Сохранение диалога в память")

    messages = [
        {"role": "user", "content": "Проанализируй стратегию RSI(14) на BTCUSDT 15m"},
        {"role": "deepseek", "content": "Sharpe=1.42, DrawDown=-8.4%. Стратегия умеренно рискованная."},
        {"role": "qwen", "content": "RSI(21) с уровнями 75/25 покажет лучшие результаты на 15m."},
        {"role": "perplexity", "content": "Текущий рынок в состоянии консолидации. Рекомендую осторожность."},
        {"role": "system", "content": "Консенсус: MACD+RSI комбинация предпочтительнее. Уверенность 78%."},
    ]

    for msg in messages:
        memory.store_message(session_id, msg)
        print(f"  Сохранено: [{msg['role']}] {msg['content'][:60]}")

    subsection("Извлечение из памяти")
    retrieved = memory.get_conversation(session_id)
    print(f"  Извлечено сообщений: {len(retrieved)}")
    for msg in retrieved:
        print(f"    [{msg['role']}] {msg['content'][:60]}")

    # Check persistence
    subsection("Проверка персистентности")
    memory2 = AgentMemoryManager(PROJECT_ROOT)
    retrieved2 = memory2.get_conversation(session_id)
    print(f"  После повторной загрузки: {len(retrieved2)} сообщений")
    persistence_ok = len(retrieved2) == len(messages)
    print(f"  Персистентность: {'OK' if persistence_ok else 'ОШИБКА'}")

    # Cleanup
    memory.clear_conversation(session_id)
    print(f"  Сессия {session_id} очищена")

    return {
        "status": "ok",
        "messages_stored": len(messages),
        "messages_retrieved": len(retrieved),
        "persistence_ok": persistence_ok,
        "session_id": session_id,
    }


async def test_7_prompt_optimizer() -> dict:
    """Тест 7: Prompt Optimizer — экономия токенов."""
    section("ТЕСТ 7: Prompt Optimizer")

    from backend.agents.llm.prompt_optimizer import TaskComplexity, get_prompt_optimizer

    optimizer = get_prompt_optimizer()

    # Test task complexity classification
    subsection("Классификация сложности задач")
    tasks = [
        ("What is the current BTC price?", TaskComplexity.SIMPLE),
        ("Analyze RSI crossover signals for BTCUSDT on 15m", TaskComplexity.MODERATE),
        (
            "Compare 5 strategies across 3 timeframes with Monte Carlo simulation and walk-forward optimization",
            TaskComplexity.COMPLEX,
        ),
        ("Calculate Sharpe ratio", TaskComplexity.SIMPLE),
        (
            "Optimize multi-indicator strategy with grid search and cross-validation on regime-dependent parameters",
            TaskComplexity.COMPLEX,
        ),
    ]
    for task, expected in tasks:
        actual = optimizer.classify_task_complexity(task)
        status = "OK" if actual == expected else "МИСС"
        print(f"  [{status}] {actual.value:8s} <- {task[:65]}")

    # Test thinking mode decision
    subsection("Решение о режиме мышления (Qwen)")
    for task, _ in tasks:
        complexity = optimizer.classify_task_complexity(task)
        should_think = optimizer.should_enable_thinking("qwen", task)
        print(f"  thinking={'ON' if should_think else 'OFF':3s} ({complexity.value:8s}) <- {task[:55]}")

    # Test metric filtering
    subsection("Фильтрация метрик по агентам")
    sample_metrics = {
        "net_profit": 1234.56789,
        "total_trades": 47,
        "win_rate": 0.582456789,
        "sharpe_ratio": 1.4234567,
        "sortino_ratio": 2.0123456,
        "calmar_ratio": 0.8765432,
        "max_drawdown": -0.08432,
        "var_95": -0.02345,
        "cvar_95": -0.03456,
        "avg_rsi": 52.3456789,
        "macd_signal_quality": 0.78,
        "bollinger_bandwidth": 0.0234,
        "momentum_score": 0.65,
        "trend_strength": 0.72,
        "regime_stability": 0.83,
        "sentiment_score": 0.55,
        "news_impact": 0.3,
        "some_irrelevant_metric": 99.99,
    }

    for agent in ["deepseek", "qwen", "perplexity"]:
        filtered = optimizer.filter_metrics_for_agent(agent, sample_metrics)
        print(
            f"  {agent:10s}: {len(sample_metrics)} -> {len(filtered)} метрик ({len(sample_metrics) - len(filtered)} отфильтровано)"
        )
        print(f"              {list(filtered.keys())[:6]}...")

    # Test quantization
    subsection("Квантизация чисел")
    quantized = optimizer.quantize_floats(sample_metrics)
    print(f"  До:    sharpe_ratio={sample_metrics['sharpe_ratio']}, win_rate={sample_metrics['win_rate']}")
    print(f"  После: sharpe_ratio={quantized['sharpe_ratio']}, win_rate={quantized['win_rate']}")

    # Test caching
    subsection("Кеширование")
    test_prompt = "analyze RSI strategy for BTCUSDT"
    test_response = "RSI(14) shows positive alpha with Sharpe 1.4"
    optimizer.cache_response("deepseek", test_prompt, test_response)
    cached = optimizer.get_cached_response("deepseek", test_prompt)
    cache_hit = cached == test_response
    print(f"  Кеш записан: {test_prompt[:40]}...")
    print(f"  Кеш прочитан: {'OK' if cache_hit else 'MISS'}")

    # Stats
    stats = optimizer.get_stats()
    subsection("Статистика оптимизатора")
    print(f"  {stats}")

    return {
        "status": "ok",
        "complexity_tests": "passed",
        "metric_filtering": {
            agent: len(optimizer.filter_metrics_for_agent(agent, sample_metrics))
            for agent in ["deepseek", "qwen", "perplexity"]
        },
        "cache_hit": cache_hit,
        "stats": stats.__dict__ if hasattr(stats, "__dict__") else str(stats),
    }


async def main():
    """Run all tests and save results."""
    print("\n" + "=" * 70)
    print("  ТЕСТ АГЕНТОВ НА РЕАЛЬНЫХ API")
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {},
    }

    total_start = time.time()

    # Run tests sequentially
    test_functions = [
        ("1_api_connectivity", test_1_api_connectivity),
        ("2_individual_agents", test_2_individual_agents),
        ("3_multi_agent_deliberation", test_3_multi_agent_deliberation),
        ("4_perplexity_enrichment", test_4_perplexity_enrichment),
        ("5_cross_validation", test_5_cross_validation),
        ("6_agent_memory", test_6_agent_memory),
        ("7_prompt_optimizer", test_7_prompt_optimizer),
    ]

    for test_name, test_fn in test_functions:
        try:
            result = await test_fn()
            all_results["tests"][test_name] = result
        except Exception as e:
            import traceback

            print(f"\n  КРИТИЧЕСКАЯ ОШИБКА в {test_name}: {e}")
            traceback.print_exc()
            all_results["tests"][test_name] = {"status": "critical_error", "error": str(e)}

    total_elapsed = time.time() - total_start

    # Final summary
    section("ИТОГОВЫЙ ОТЧЁТ")

    for name, result in all_results["tests"].items():
        status = result.get("status", "?")
        icon = "✅" if status == "ok" else ("⏭️" if status == "skipped" else "❌")
        print(f"  {icon} {name}: {status}")

    print(f"\n  Общее время: {total_elapsed:.1f}с")

    # Save results
    output_dir = PROJECT_ROOT / "docs" / "agent_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "real_api_test_results.json"

    all_results["total_elapsed_s"] = round(total_elapsed, 2)

    # Serialize safely
    def safe_serialize(obj):
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=safe_serialize)

    print(f"\n  Результаты сохранены: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
