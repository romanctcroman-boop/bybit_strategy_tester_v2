#!/usr/bin/env python
"""
Stop hook — срабатывает когда Claude завершает ответ.

Цели:
1. Если в этом ответе были отредактированы Python-файлы бэкенда → напоминает
   обновить memory-bank/activeContext.md
2. Защита от бесконечного цикла через stop_hook_active

НЕ блокирует Claude (exit 0 всегда) — только советует.
Если нужно заблокировать остановку — вернуть {"decision": "block", "reason": "..."}.
"""

import json
import os
import sys

# Файлы которые сигнализируют о значимой работе
SIGNIFICANT_DIRS = [
    "backend/backtesting/engines/",
    "backend/backtesting/strategy_builder_adapter",
    "backend/backtesting/indicator_handlers",
    "backend/core/metrics_calculator",
    "backend/api/routers/",
    "backend/optimization/",
]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Защита от бесконечного цикла — критически важно!
    if data.get("stop_hook_active"):
        sys.exit(0)

    # Читаем список отредактированных файлов из transcript (если доступен)
    # Простой подход: просто всегда выводим напоминание — Claude решит сам нужно ли
    # (дешевле чем парсить весь JSONL transcript)

    cwd = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", os.getcwd()))
    mb_active = os.path.join(cwd, "memory-bank", "activeContext.md")

    # Проверяем возраст activeContext.md
    needs_reminder = True
    if os.path.exists(mb_active):
        import time

        age_minutes = (time.time() - os.path.getmtime(mb_active)) / 60
        # Не напоминаем если файл обновлялся менее 10 минут назад
        # (значит PostCompact уже обновил или мы сами обновляли)
        if age_minutes < 10:
            needs_reminder = False

    if needs_reminder:
        # Выводим в stdout → попадает в контекст Claude как подсказка
        print(
            "\n💡 **Напоминание:** Если в этой сессии была сделана значимая работа "
            "(исправлен баг, добавлена фича, изменена архитектура) — "
            "обнови `memory-bank/activeContext.md` прежде чем завершать. "
            "Это займёт 30 секунд и сэкономит время в следующей сессии."
        )

    sys.exit(0)  # Всегда exit 0 — не блокируем завершение


if __name__ == "__main__":
    main()
