#!/usr/bin/env python
"""
PostCompact hook — двойная задача:
1. ЗАПИСЫВАЕТ compact_summary в memory-bank/activeContext.md (авто-обновление Memory Bank)
2. ЧИТАЕТ и переинжектирует ключевой контекст в сессию

Срабатывает mid-session после авто- или ручной компакции.
compact_summary — это Claude-generated сводка всего что произошло в сессии.
Записывая её в activeContext.md мы получаем бесплатный авто-апдейт Memory Bank.
"""

import json
import os
import sys
from datetime import datetime

CRITICAL = """
## ⚡ КОНТЕКСТ ВОССТАНОВЛЕН ПОСЛЕ КОМПРЕССИИ

### Критические константы — НИКОГДА НЕ МЕНЯТЬ
| Константа | Значение |
|-----------|---------|
| commission_value | **0.0007** — TradingView parity |
| Engine | **FallbackEngineV4** — gold standard |
| DATA_START_DATE | **2025-01-01** — из database_policy.py |
| Max backtest | **730 дней** |

### Ловушки
- direction: API→"long" | Engine→"both" | Builder→"both"
- Port aliases: long↔bullish, short↔bearish, output↔value, result↔signal
- commission = trade_value × 0.0007 (на MARGIN, не на leveraged_value!)
- Bash нестабилен → Read/Glob/Grep/Edit/Write
"""


def read_file(path: str, max_lines: int = 40) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        content = "".join(lines[:max_lines]).strip()
        if len(lines) > max_lines:
            content += f"\n... (+{len(lines) - max_lines} строк)"
        return content or None
    except Exception:
        return None


def write_active_context(mb_dir: str, compact_summary: str, trigger: str) -> bool:
    """
    Записывает compact_summary в activeContext.md.
    Это ключевая функция — авто-обновление Memory Bank без ручного вмешательства.
    """
    if not compact_summary or not compact_summary.strip():
        return False

    path = os.path.join(mb_dir, "activeContext.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    content = f"""# Active Context — Текущая работа

> Авто-обновлено PostCompact хуком: {now} (trigger: {trigger})
> Следующие шаги и детали — обновляй вручную по мере работы.

## Сводка сессии (compact_summary)

{compact_summary.strip()}

## Следующие шаги
<!-- Обнови вручную после завершения задачи -->

## Открытые вопросы / Блокеры
<!-- Обнови вручную -->
"""
    try:
        os.makedirs(mb_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[hook] Не удалось записать activeContext.md: {e}", file=sys.stderr)
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    cwd = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", os.getcwd()))
    trigger = data.get("trigger", "auto")
    compact_summary = data.get("compact_summary", "")

    mb_dir = os.path.join(cwd, "memory-bank")

    # === ГЛАВНОЕ: записываем compact_summary в activeContext.md ===
    saved = write_active_context(mb_dir, compact_summary, trigger)
    if saved:
        print(f"[hook] ✅ Memory Bank обновлён — activeContext.md перезаписан (trigger: {trigger})")
    else:
        print("[hook] ⚠️  compact_summary пустой — activeContext.md не обновлён", file=sys.stderr)

    # === Переинжектируем контекст в сессию ===
    print(CRITICAL)

    # Показываем что только что записали
    if compact_summary:
        short = compact_summary[:500] + "..." if len(compact_summary) > 500 else compact_summary
        print(f"\n## Сохранённая сводка сессии\n{short}")

    # progress.md — статус проекта
    progress = read_file(os.path.join(mb_dir, "progress.md"), max_lines=25)
    if progress:
        print(f"\n## Статус проекта (progress.md)\n{progress}")

    print("\n[hook] Контекст восстановлен. Продолжай работу.")
    sys.exit(0)


if __name__ == "__main__":
    main()
