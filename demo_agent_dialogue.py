"""
🎭 LIVE DEMO: DeepSeek vs Qwen — Полный диалог между двумя AI провайдерами

Этот скрипт показывает ПОЛНЫЙ ТЕКСТ каждого сообщения между агентами:
  - Agent-Q (Quantitative Analyst) → DeepSeek API (deepseek-chat)
  - Agent-T (Technical Analyst)    → Qwen API (qwen-flash, Singapore)

Формат вывода — как чат: каждая реплика, каждая критика, итоговое решение.

Qwen models available (International / Singapore, Feb 2026):
  qwen-plus  — Best balance ($0.40/$1.20 per 1M tok)
  qwen-flash — Fastest & cheapest ($0.05/$0.40 per 1M tok) ★ used here
  qwen3-max  — Most powerful ($1.20/$6.00 per 1M tok)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ────────────────────────────────────────────────────────────
DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")
QW_KEY = os.getenv("QWEN_API_KEY", "")

DS_URL = "https://api.deepseek.com/v1/chat/completions"
QW_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

# ─── Personas ─────────────────────────────────────────────────────────────
QUANT_SYSTEM = (
    "You are Agent-Q, a quantitative trading analyst. "
    "Your expertise: statistical edge, Sharpe ratio, drawdown control, position sizing. "
    "You ALWAYS back claims with numbers. You prefer conservative approaches. "
    "Keep answers concise (max 200 words). Always state your CONFIDENCE (0-100%)."
)

TECH_SYSTEM = (
    "You are Agent-T, a technical analysis expert. "
    "Your expertise: RSI, MACD, Bollinger Bands, candlestick patterns, support/resistance. "
    "You focus on signal quality and are willing to accept more risk for higher returns. "
    "Keep answers concise (max 200 words). Always state your CONFIDENCE (0-100%)."
)


# ─── Styling ──────────────────────────────────────────────────────────────
def header(text: str):
    w = 78
    print(f"\n{'═' * w}")
    print(f"  {text}")
    print(f"{'═' * w}")


def agent_says(name: str, provider: str, text: str, tokens: int, ms: int):
    emoji = "🔵" if provider == "DeepSeek" else "🟢"
    print(f"\n{emoji} ── {name} ({provider}) ── [{tokens} tok, {ms}ms] ──")
    print(text.strip())
    print(f"{'─' * 78}")


def system_msg(text: str):
    print(f"\n⚙️  {text}")


# ─── Raw API call ─────────────────────────────────────────────────────────
async def call_llm(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    model: str,
    system: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> tuple[str, int, int]:
    """Call LLM API, return (content, total_tokens, latency_ms)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    async with session.post(url, json=body, headers=headers) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"{model} returned {resp.status}: {text[:200]}")
        data = await resp.json()
    ms = int((time.time() - t0) * 1000)
    content = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return content, tokens, ms


async def ask_deepseek(session, prompt, system=QUANT_SYSTEM, temp=0.5):
    return await call_llm(session, DS_URL, DS_KEY, "deepseek-chat", system, prompt, temp)


async def ask_qwen(session, prompt, system=TECH_SYSTEM, temp=0.8):
    return await call_llm(session, QW_URL, QW_KEY, "qwen-flash", system, prompt, temp)


# ═════════════════════════════════════════════════════════════════════════
async def main():
    print("\n" * 2)
    header("🎭  LIVE DIALOGUE: DeepSeek (Agent-Q) vs Qwen (Agent-T)")
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  DeepSeek: deepseek-chat | Qwen: qwen-flash (Singapore)")
    print(f"  Тема: Стоп-лосс стратегия для BTCUSDT 15m RSI+MACD")
    total_start = time.time()

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # ── ПРОВЕРКА ПОДКЛЮЧЕНИЯ ──────────────────────────────────
        system_msg("Проверка подключений...")
        try:
            ds_test, _, ds_ms = await ask_deepseek(session, "Say 'ready' in one word.")
            print(f"  🔵 DeepSeek: OK ({ds_ms}ms) → '{ds_test.strip()}'")
        except Exception as e:
            print(f"  ❌ DeepSeek: {e}")
            return

        try:
            qw_test, _, qw_ms = await ask_qwen(session, "Say 'ready' in one word.")
            print(f"  🟢 Qwen:     OK ({qw_ms}ms) → '{qw_test.strip()}'")
        except Exception as e:
            print(f"  ❌ Qwen: {e}")
            return

        QUESTION = (
            "For a BTC/USDT 15-minute RSI(14)+MACD(12,26,9) strategy with:\n"
            "- Sharpe ratio: 1.62\n"
            "- Win rate: 58%\n"
            "- Max drawdown: 18%\n"
            "- Commission: 0.07% per trade\n"
            "- 142 trades in backtest\n\n"
            "Should we use a TRAILING stop-loss or a FIXED stop-loss?\n"
            "Give your recommendation with specific parameters."
        )

        # ═══════════════════════════════════════════════════════════
        # РАУНД 1: Начальные позиции
        # ═══════════════════════════════════════════════════════════
        header("📍 РАУНД 1: Начальные позиции")
        system_msg(f"Вопрос для обсуждения:\n  {QUESTION}")

        # Параллельные вызовы к DeepSeek и Qwen
        system_msg("Оба агента думают одновременно (DeepSeek + Qwen)...")
        (ds_r1, ds_tok1, ds_ms1), (qw_r1, qw_tok1, qw_ms1) = await asyncio.gather(
            ask_deepseek(session, QUESTION),
            ask_qwen(session, QUESTION),
        )

        agent_says("Agent-Q (Quant)", "DeepSeek", ds_r1, ds_tok1, ds_ms1)
        agent_says("Agent-T (Technical)", "Qwen", qw_r1, qw_tok1, qw_ms1)

        # ═══════════════════════════════════════════════════════════
        # РАУНД 2: Перекрёстная критика
        # ═══════════════════════════════════════════════════════════
        header("📍 РАУНД 2: Перекрёстная критика")

        critique_prompt_q = (
            f"Your colleague Agent-T (Technical Analyst, powered by Qwen) proposes:\n\n"
            f'"""\n{qw_r1.strip()}\n"""\n\n'
            f"Do you AGREE or DISAGREE? What are the strengths and weaknesses "
            f"of their approach? Suggest specific improvements with numbers."
        )

        critique_prompt_t = (
            f"Your colleague Agent-Q (Quantitative Analyst, powered by DeepSeek) proposes:\n\n"
            f'"""\n{ds_r1.strip()}\n"""\n\n'
            f"Do you AGREE or DISAGREE? What are the strengths and weaknesses "
            f"of their approach? Suggest specific improvements with numbers."
        )

        system_msg("Агенты читают позиции друг друга и готовят критику...")
        (ds_r2, ds_tok2, ds_ms2), (qw_r2, qw_tok2, qw_ms2) = await asyncio.gather(
            ask_deepseek(session, critique_prompt_q),
            ask_qwen(session, critique_prompt_t),
        )

        agent_says("Agent-Q критикует Agent-T", "DeepSeek", ds_r2, ds_tok2, ds_ms2)
        agent_says("Agent-T критикует Agent-Q", "Qwen", qw_r2, qw_tok2, qw_ms2)

        # ═══════════════════════════════════════════════════════════
        # РАУНД 3: Финальные позиции с учётом критики
        # ═══════════════════════════════════════════════════════════
        header("📍 РАУНД 3: Финальные позиции после дебатов")

        final_prompt_q = (
            f"After hearing Agent-T's critique of your position:\n\n"
            f'"""\n{qw_r2.strip()}\n"""\n\n'
            f"Revise your FINAL recommendation for the stop-loss strategy. "
            f"Have you changed your mind? What's your final answer with "
            f"specific parameters? State your CONFIDENCE (0-100%)."
        )

        final_prompt_t = (
            f"After hearing Agent-Q's critique of your position:\n\n"
            f'"""\n{ds_r2.strip()}\n"""\n\n'
            f"Revise your FINAL recommendation for the stop-loss strategy. "
            f"Have you changed your mind? What's your final answer with "
            f"specific parameters? State your CONFIDENCE (0-100%)."
        )

        system_msg("Агенты формулируют финальные позиции...")
        (ds_r3, ds_tok3, ds_ms3), (qw_r3, qw_tok3, qw_ms3) = await asyncio.gather(
            ask_deepseek(session, final_prompt_q),
            ask_qwen(session, final_prompt_t),
        )

        agent_says("Agent-Q — ФИНАЛЬНАЯ ПОЗИЦИЯ", "DeepSeek", ds_r3, ds_tok3, ds_ms3)
        agent_says("Agent-T — ФИНАЛЬНАЯ ПОЗИЦИЯ", "Qwen", qw_r3, qw_tok3, qw_ms3)

        # ═══════════════════════════════════════════════════════════
        # ИТОГО: Синтез решения
        # ═══════════════════════════════════════════════════════════
        header("🏆  СИНТЕЗ: Финальное объединённое решение")

        synthesis_prompt = (
            f"You are a neutral moderator. Two AI agents debated the best stop-loss "
            f"strategy for a BTCUSDT 15m RSI+MACD system.\n\n"
            f"Agent-Q (DeepSeek, Quantitative) final position:\n"
            f'"""\n{ds_r3.strip()}\n"""\n\n'
            f"Agent-T (Qwen, Technical) final position:\n"
            f'"""\n{qw_r3.strip()}\n"""\n\n'
            f"Synthesize BOTH positions into ONE actionable recommendation. "
            f"Note where they agree and disagree. Give specific parameters."
        )

        # Use DeepSeek as synthesizer (neutral)
        synth, synth_tok, synth_ms = await call_llm(
            session,
            DS_URL,
            DS_KEY,
            "deepseek-chat",
            "You are a neutral trading strategy moderator. Synthesize two expert opinions.",
            synthesis_prompt,
            temperature=0.3,
            max_tokens=800,
        )

        agent_says("Модератор — СИНТЕЗ", "DeepSeek", synth, synth_tok, synth_ms)

        # ── Статистика ────────────────────────────────────────────
        total_time = time.time() - total_start
        total_tokens = ds_tok1 + qw_tok1 + ds_tok2 + qw_tok2 + ds_tok3 + qw_tok3 + synth_tok
        ds_total = ds_tok1 + ds_tok2 + ds_tok3 + synth_tok
        qw_total = qw_tok1 + qw_tok2 + qw_tok3

        header("📊  СТАТИСТИКА ДИАЛОГА")
        print(f"  Время:         {total_time:.1f}s")
        print(f"  Раунды:        3 + синтез")
        print(f"  API вызовов:   7 (4× DeepSeek, 3× Qwen)")
        print(f"  Всего токенов: {total_tokens:,}")
        print(f"  🔵 DeepSeek:   {ds_total:,} токенов")
        print(f"  🟢 Qwen:       {qw_total:,} токенов")
        print(f"  Стоимость:     ~${total_tokens * 0.0000005:.4f}")
        print(f"{'═' * 78}\n")


if __name__ == "__main__":
    if not DS_KEY or "YOUR" in DS_KEY:
        print("❌ DEEPSEEK_API_KEY не настроен в .env")
        sys.exit(1)
    if not QW_KEY or "YOUR" in QW_KEY:
        print("❌ QWEN_API_KEY не настроен в .env")
        sys.exit(1)

    asyncio.run(main())
