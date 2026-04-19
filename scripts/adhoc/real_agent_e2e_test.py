"""
🧪 РЕАЛЬНЫЙ E2E ТЕСТ ВСЕХ АГЕНТОВ
===================================
Тестирует ВСЕ системы агентов на реальных API:

1. Индивидуальный тест каждого агента (DeepSeek, Qwen, Perplexity)
2. Совместная задача — анализ уязвимостей стратегии
3. Deliberation — голосование агентов по вопросу модернизации
4. Agent-to-Agent коммуникация
5. Проверка cost tracking и rate limiting

Использует ДЕШЁВЫЕ модели и КОРОТКИЕ промпты для экономии.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
QWEN_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# Короткие промпты для экономии токенов (~200 input + ~200 output = $0.0001 per call)
MAX_TOKENS = 300  # Минимум для осмысленного ответа

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def banner(text: str) -> None:
    """Print a banner."""
    print(f"\n{'=' * 70}")
    print(f"  {BOLD}{CYAN}{text}{RESET}")
    print(f"{'=' * 70}")


def ok(text: str) -> None:
    print(f"  {GREEN}✅ {text}{RESET}")


def fail(text: str) -> None:
    print(f"  {RED}❌ {text}{RESET}")


def warn(text: str) -> None:
    print(f"  {YELLOW}⚠️  {text}{RESET}")


def info(text: str) -> None:
    print(f"  {CYAN}ℹ️  {text}{RESET}")


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 1: ИНДИВИДУАЛЬНЫЕ ВЫЗОВЫ КАЖДОГО АГЕНТА
# ═══════════════════════════════════════════════════════════════


async def test_individual_agents() -> dict:
    """Тест каждого агента отдельно на реальном API."""
    import httpx

    banner("ТЕСТ 1: Индивидуальные вызовы агентов")

    results = {}

    agents = {
        "deepseek": {
            "url": DEEPSEEK_URL,
            "key_env": "DEEPSEEK_API_KEY",
            "model": "deepseek-chat",
            "prompt": (
                "Кратко (3-5 предложений): какие основные уязвимости "
                "у RSI-стратегии для торговли криптовалютами? Ответ на русском."
            ),
        },
        "qwen": {
            "url": QWEN_URL,
            "key_env": "QWEN_API_KEY",
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
            "prompt": (
                "Кратко (3-5 предложений): какие технические индикаторы "
                "лучше комбинировать с RSI для подтверждения сигналов? Ответ на русском."
            ),
        },
        "perplexity": {
            "url": PERPLEXITY_URL,
            "key_env": "PERPLEXITY_API_KEY",
            "model": "sonar",  # Самая дешёвая модель
            "prompt": (
                "Briefly (3-5 sentences): what are current BTC market conditions "
                "and dominant trend as of February 2026?"
            ),
        },
    }

    for agent_name, cfg in agents.items():
        api_key = os.getenv(cfg["key_env"], "")
        if not api_key:
            warn(f"{agent_name}: API ключ не найден ({cfg['key_env']})")
            results[agent_name] = {"status": "skipped", "error": "no API key"}
            continue

        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": "You are a trading strategy expert. Be concise."},
                {"role": "user", "content": cfg["prompt"]},
            ],
            "temperature": 0.3,
            "max_tokens": MAX_TOKENS,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                resp = await client.post(cfg["url"], json=payload, headers=headers)

            latency = (time.time() - start) * 1000
            data = resp.json()

            if resp.status_code == 200:
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)

                ok(
                    f"{agent_name} ({cfg['model']}): {latency:.0f}ms, "
                    f"{total_tokens} tokens ({prompt_tokens}+{completion_tokens})"
                )
                # Первые 120 символов ответа
                preview = content[:120].replace("\n", " ")
                info(f"Ответ: {preview}...")

                results[agent_name] = {
                    "status": "success",
                    "model": cfg["model"],
                    "latency_ms": round(latency),
                    "tokens": {"prompt": prompt_tokens, "completion": completion_tokens, "total": total_tokens},
                    "response_length": len(content),
                    "response_preview": content[:200],
                }
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                fail(f"{agent_name}: HTTP {resp.status_code} — {error_msg[:100]}")
                results[agent_name] = {"status": "error", "http_code": resp.status_code, "error": error_msg[:200]}

        except httpx.ConnectError:
            fail(f"{agent_name}: Не удалось подключиться (DNS/VPN/Firewall)")
            results[agent_name] = {"status": "connection_error", "error": "ConnectError — DNS/VPN/Firewall"}
        except Exception as e:
            fail(f"{agent_name}: {type(e).__name__}: {e}")
            results[agent_name] = {"status": "error", "error": str(e)[:200]}

    return results


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 2: СОВМЕСТНАЯ ЗАДАЧА — АНАЛИЗ УЯЗВИМОСТЕЙ
# ═══════════════════════════════════════════════════════════════


async def test_collaborative_task() -> dict:
    """
    DeepSeek и Qwen анализируют одну задачу с разных сторон,
    потом результаты объединяются.
    """
    import httpx

    banner("ТЕСТ 2: Совместная задача — анализ уязвимостей стратегии")

    task_prompt = (
        "Проанализируй RSI+MACD стратегию для BTCUSDT (15m, commission 0.07%). "
        "Назови ровно 3 уязвимости. Формат ответа:\n"
        "1. [название]: описание (1 предложение)\n"
        "2. [название]: описание\n"
        "3. [название]: описание\n"
        "Ответ на русском, ТОЛЬКО 3 пункта."
    )

    agents_config = {
        "deepseek": {
            "url": DEEPSEEK_URL,
            "key": os.getenv("DEEPSEEK_API_KEY", ""),
            "model": "deepseek-chat",
            "system": "Ты — количественный аналитик. Фокус: риск-метрики, drawdown, Sharpe ratio.",
        },
        "qwen": {
            "url": QWEN_URL,
            "key": os.getenv("QWEN_API_KEY", ""),
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
            "system": "Ты — технический аналитик. Фокус: индикаторы, паттерны, оптимизация параметров.",
        },
    }

    responses = {}

    for agent_name, cfg in agents_config.items():
        if not cfg["key"]:
            warn(f"{agent_name}: нет ключа")
            continue

        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": cfg["system"]},
                {"role": "user", "content": task_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": MAX_TOKENS,
        }

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    cfg["url"],
                    json=payload,
                    headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
                )

            latency = (time.time() - start) * 1000
            data = resp.json()

            if resp.status_code == 200:
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                ok(f"{agent_name}: {latency:.0f}ms, {tokens} tokens")
                print(f"    --- {agent_name} ответ ---")
                for line in content.strip().split("\n")[:5]:
                    print(f"    {line}")
                responses[agent_name] = content
            else:
                fail(f"{agent_name}: HTTP {resp.status_code}")

        except httpx.ConnectError:
            fail(f"{agent_name}: Connection error")
        except Exception as e:
            fail(f"{agent_name}: {e}")

    # Анализ пересечений
    if len(responses) >= 2:
        print(f"\n  📊 {BOLD}Сравнение результатов:{RESET}")
        all_responses = " ".join(responses.values()).lower()
        common_themes = []
        for keyword in [
            "drawdown",
            "боковой",
            "флэт",
            "шум",
            "ложн",
            "комисси",
            "slippage",
            "перекуп",
            "перепрод",
            "дивергенц",
            "оптимизац",
            "overfit",
            "переобуч",
        ]:
            if keyword in all_responses:
                common_themes.append(keyword)
        if common_themes:
            ok(f"Общие темы: {', '.join(common_themes)}")
        else:
            warn("Агенты нашли разные уязвимости (низкое пересечение)")

    return {
        "agents_responded": list(responses.keys()),
        "response_count": len(responses),
        "collaborative": len(responses) >= 2,
    }


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 3: DELIBERATION — ГОЛОСОВАНИЕ АГЕНТОВ
# ═══════════════════════════════════════════════════════════════


async def test_deliberation() -> dict:
    """
    Тест системы deliberation: агенты голосуют по вопросу.
    Используем RealLLMDeliberation если Perplexity недоступна — только DeepSeek+Qwen.
    """
    banner("ТЕСТ 3: Deliberation — голосование агентов")

    try:
        from backend.agents.consensus.real_llm_deliberation import RealLLMDeliberation

        delib = RealLLMDeliberation(enable_perplexity_enrichment=False)

        # Какие клиенты инициализированы?
        available = list(delib._clients.keys())
        info(f"Доступные агенты для deliberation: {available}")

        if len(available) < 2:
            warn("Нужно минимум 2 агента для deliberation")
            return {"status": "insufficient_agents", "available": available}

        question = (
            "Для стратегии RSI на BTCUSDT 15min: стоит ли добавить MACD "
            "как фильтр подтверждения сигналов? "
            "Ответь: ДА или НЕТ и кратко почему (2-3 предложения)."
        )

        info(f"Вопрос: {question[:80]}...")
        start = time.time()

        result = await delib.deliberate(
            question=question,
            agents=available[:3],  # Максимум 3 агента
            max_rounds=1,  # 1 раунд для экономии
        )

        latency = (time.time() - start) * 1000

        rounds_count = len(result.rounds) if result.rounds else 0
        ok(f"Deliberation завершена: {latency:.0f}ms")
        print(f"    📋 Решение: {result.decision[:150]}")
        print(f"    📊 Уверенность: {result.confidence:.1%}")
        print(f"    🔄 Раундов: {rounds_count}")

        # Показать финальные голоса агентов
        if result.final_votes:
            print("    👥 Финальные голоса:")
            for vote in result.final_votes:
                agent_name = getattr(vote, "agent", "unknown")
                position = getattr(vote, "position", "")[:80]
                conf = getattr(vote, "confidence", 0)
                print(f"       - {agent_name}: {position} (уверенность: {conf:.0%})")

        return {
            "status": "success",
            "agents": available,
            "latency_ms": round(latency),
            "decision_preview": result.decision[:200],
            "confidence": result.confidence,
            "rounds": rounds_count,
        }

    except ImportError as e:
        fail(f"Не удалось импортировать RealLLMDeliberation: {e}")
        return {"status": "import_error", "error": str(e)}
    except Exception as e:
        fail(f"Deliberation ошибка: {type(e).__name__}: {e}")
        return {"status": "error", "error": str(e)[:300]}


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 4: UNIFIED AGENT INTERFACE (send_request)
# ═══════════════════════════════════════════════════════════════


async def test_unified_interface() -> dict:
    """Тест через UnifiedAgentInterface.send_request() — основной API."""
    banner("ТЕСТ 4: UnifiedAgentInterface — основной API проекта")

    try:
        from backend.agents.models import AgentType
        from backend.agents.request_models import AgentRequest
        from backend.agents.unified_agent_interface import UnifiedAgentInterface

        agent = UnifiedAgentInterface()
        results = {}

        test_cases = [
            {
                "name": "deepseek_analyze",
                "agent_type": AgentType.DEEPSEEK,
                "task_type": "analyze",
                "prompt": "Кратко: главный недостаток RSI-стратегии? 1-2 предложения.",
            },
            {
                "name": "qwen_analyze",
                "agent_type": AgentType.QWEN,
                "task_type": "analyze",
                "prompt": "Кратко: оптимальный период RSI для BTCUSDT 15m? 1-2 предложения.",
            },
        ]

        for tc in test_cases:
            request = AgentRequest(
                agent_type=tc["agent_type"],
                task_type=tc["task_type"],
                prompt=tc["prompt"],
                thinking_mode=False,
            )

            try:
                start = time.time()
                response = await agent.send_request(request)
                latency = (time.time() - start) * 1000

                if response.success:
                    tokens_info = ""
                    if response.tokens_used:
                        tokens_info = f", {response.tokens_used.total_tokens} tok"
                    ok(f"{tc['name']}: {latency:.0f}ms{tokens_info}, channel={response.channel.value}")
                    preview = (response.content or "")[:100].replace("\n", " ")
                    info(f"Ответ: {preview}...")
                    results[tc["name"]] = {
                        "status": "success",
                        "latency_ms": round(latency),
                        "channel": response.channel.value,
                        "tokens": response.tokens_used.total_tokens if response.tokens_used else 0,
                    }
                else:
                    fail(f"{tc['name']}: {response.error}")
                    results[tc["name"]] = {"status": "error", "error": response.error}

            except Exception as e:
                fail(f"{tc['name']}: {type(e).__name__}: {e}")
                results[tc["name"]] = {"status": "exception", "error": str(e)[:200]}

        return results

    except ImportError as e:
        fail(f"Import error: {e}")
        return {"status": "import_error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 5: COST TRACKING
# ═══════════════════════════════════════════════════════════════


async def test_cost_tracking() -> dict:
    """Проверка системы отслеживания расходов."""
    banner("ТЕСТ 5: Cost Tracking — контроль расходов")

    try:
        from backend.agents.cost_tracker import COST_TABLE, CostTracker

        tracker = CostTracker()

        # Проверяем таблицу стоимостей
        info(f"Провайдеров в таблице: {len(COST_TABLE)}")
        for provider, models in COST_TABLE.items():
            info(f"  {provider}: {list(models.keys())}")

        # Симулируем запись расходов
        tracker.record(
            agent="deepseek",
            model="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        tracker.record(
            agent="qwen",
            model="qwen-plus",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        )

        summary = tracker.get_summary()
        ok(f"Cost tracker работает: {json.dumps(summary, indent=2, default=str)[:300]}")

        # Проверяем guards
        info("Проверка cost guards:")
        guards = {
            "DEEPSEEK_ALLOW_REASONER": os.getenv("DEEPSEEK_ALLOW_REASONER", "not set"),
            "QWEN_ENABLE_THINKING": os.getenv("QWEN_ENABLE_THINKING", "not set"),
            "PERPLEXITY_ALLOW_EXPENSIVE": os.getenv("PERPLEXITY_ALLOW_EXPENSIVE", "not set"),
        }
        all_safe = True
        for guard, value in guards.items():
            if value.lower() == "true":
                warn(f"  {guard} = {value} (ДОРОГИЕ модели ВКЛЮЧЕНЫ!)")
                all_safe = False
            else:
                ok(f"  {guard} = {value}")

        return {
            "status": "success",
            "cost_table_providers": list(COST_TABLE.keys()),
            "guards": guards,
            "all_guards_safe": all_safe,
        }

    except Exception as e:
        fail(f"Cost tracking error: {e}")
        return {"status": "error", "error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 6: MODERNIZATION PATH — агент предлагает улучшения
# ═══════════════════════════════════════════════════════════════


async def test_modernization_path() -> dict:
    """DeepSeek и Qwen предлагают пути модернизации агентной системы."""
    import httpx

    banner("ТЕСТ 6: Путь модернизации — агенты предлагают улучшения")

    modernization_prompt = (
        "Ты анализируешь агентную систему для бэктестинга крипто-стратегий. "
        "Система: 3 агента (DeepSeek, Qwen, Perplexity), deliberation с голосованием, "
        "cost tracking, rate limiting, key rotation. "
        "Назови ТОП-3 приоритетных улучшения. Формат:\n"
        "1. [Название]: что и зачем (1 предложение)\n"
        "2. [Название]: что и зачем\n"
        "3. [Название]: что и зачем\n"
        "Ответ на русском, ТОЛЬКО 3 пункта."
    )

    agents_config = {
        "deepseek": {
            "url": DEEPSEEK_URL,
            "key": os.getenv("DEEPSEEK_API_KEY", ""),
            "model": "deepseek-chat",
        },
        "qwen": {
            "url": QWEN_URL,
            "key": os.getenv("QWEN_API_KEY", ""),
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
        },
    }

    responses = {}
    for agent_name, cfg in agents_config.items():
        if not cfg["key"]:
            continue

        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": "Ты — эксперт по AI/ML архитектуре. Будь конкретен."},
                {"role": "user", "content": modernization_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": MAX_TOKENS,
        }

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    cfg["url"],
                    json=payload,
                    headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
                )

            latency = (time.time() - start) * 1000
            data = resp.json()

            if resp.status_code == 200:
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                ok(f"{agent_name}: {latency:.0f}ms, {tokens} tokens")
                print(f"    --- {agent_name}: Путь модернизации ---")
                for line in content.strip().split("\n")[:5]:
                    if line.strip():
                        print(f"    {line}")
                responses[agent_name] = content
            else:
                fail(f"{agent_name}: HTTP {resp.status_code}")
        except httpx.ConnectError:
            fail(f"{agent_name}: Connection error")
        except Exception as e:
            fail(f"{agent_name}: {e}")

    return {"agents_responded": list(responses.keys()), "modernization_plans": len(responses)}


# ═══════════════════════════════════════════════════════════════
# MAIN — ЗАПУСК ВСЕХ ТЕСТОВ
# ═══════════════════════════════════════════════════════════════


async def main():
    print(f"\n{'#' * 70}")
    print(f"  {BOLD}🧪 РЕАЛЬНЫЙ E2E ТЕСТ АГЕНТОВ — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"  Модели: deepseek-chat, {os.getenv('QWEN_MODEL', 'qwen-plus')}, sonar")
    print(f"  max_tokens: {MAX_TOKENS} (экономный режим)")
    print(f"{'#' * 70}")

    all_results = {}
    total_start = time.time()

    # Тест 1: Индивидуальные агенты
    all_results["1_individual"] = await test_individual_agents()

    # Тест 2: Совместная задача
    all_results["2_collaborative"] = await test_collaborative_task()

    # Тест 3: Deliberation
    all_results["3_deliberation"] = await test_deliberation()

    # Тест 4: Unified Interface
    all_results["4_unified_interface"] = await test_unified_interface()

    # Тест 5: Cost Tracking
    all_results["5_cost_tracking"] = await test_cost_tracking()

    # Тест 6: Modernization Path
    all_results["6_modernization"] = await test_modernization_path()

    total_time = time.time() - total_start

    # ═══════════════════════════════════════════════════════════
    # ИТОГИ
    # ═══════════════════════════════════════════════════════════

    banner("ИТОГИ E2E ТЕСТИРОВАНИЯ")

    passed = 0
    failed = 0
    skipped = 0

    test_names = {
        "1_individual": "Индивидуальные агенты",
        "2_collaborative": "Совместная задача",
        "3_deliberation": "Deliberation",
        "4_unified_interface": "Unified Interface",
        "5_cost_tracking": "Cost Tracking",
        "6_modernization": "Путь модернизации",
    }

    for test_id, name in test_names.items():
        result = all_results.get(test_id, {})

        if isinstance(result, dict):
            # Для теста 1 (словарь агентов)
            if test_id == "1_individual":
                agent_ok = sum(1 for v in result.values() if isinstance(v, dict) and v.get("status") == "success")
                agent_total = len(result)
                if agent_ok >= 2:
                    ok(f"{name}: {agent_ok}/{agent_total} агентов")
                    passed += 1
                elif agent_ok >= 1:
                    warn(f"{name}: {agent_ok}/{agent_total} агентов (частично)")
                    passed += 1
                else:
                    fail(f"{name}: 0/{agent_total}")
                    failed += 1
            elif test_id == "4_unified_interface":
                tc_ok = sum(1 for v in result.values() if isinstance(v, dict) and v.get("status") == "success")
                tc_total = len(result)
                if tc_ok >= 1:
                    ok(f"{name}: {tc_ok}/{tc_total}")
                    passed += 1
                else:
                    fail(f"{name}: 0/{tc_total}")
                    failed += 1
            else:
                status = result.get("status", "")
                if status == "success" or result.get("collaborative") or result.get("agents_responded"):
                    ok(f"{name}")
                    passed += 1
                elif status in ("skipped", "insufficient_agents"):
                    warn(f"{name}: {status}")
                    skipped += 1
                else:
                    fail(f"{name}: {result.get('error', 'unknown')[:60]}")
                    failed += 1

    print(f"\n  {'=' * 50}")
    print(f"  {BOLD}Всего: {passed} ✅ passed, {failed} ❌ failed, {skipped} ⚠️ skipped{RESET}")
    print(f"  Время: {total_time:.1f}s")
    print(f"  {'=' * 50}")

    # Сохраняем результаты
    output_dir = Path("docs/agent_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total_time_s": round(total_time, 1),
                "summary": {"passed": passed, "failed": failed, "skipped": skipped},
                "results": all_results,
            },
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    ok(f"Результаты сохранены: {output_file}")

    return passed, failed, skipped


if __name__ == "__main__":
    p, f, s = asyncio.run(main())
    sys.exit(1 if f > 0 else 0)
