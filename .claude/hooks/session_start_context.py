#!/usr/bin/env python
"""
SessionStart hook — инжектирует Memory Bank контекст при старте/compact сессии.
Matcher: compact|startup

Печатает в stdout → добавляется в контекст Claude Code.
Вызывается при:
  - startup: новая сессия
  - compact: сессия восстанавливается после компакции
"""

import json
import os
import sys


def read_file(path: str, max_lines: int | None = None) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if max_lines and len(lines) > max_lines:
            content = "".join(lines[:max_lines]).strip()
            content += f"\n... (ещё {len(lines) - max_lines} строк)"
        else:
            content = "".join(lines).strip()
        return content or None
    except Exception:
        return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    source = data.get("source", "startup")
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", os.getcwd()))

    mb = os.path.join(cwd, "memory-bank")

    # Загружаем Memory Bank
    active = read_file(os.path.join(mb, "activeContext.md"))
    progress = read_file(os.path.join(mb, "progress.md"), max_lines=30)
    patterns = read_file(os.path.join(mb, "systemPatterns.md"), max_lines=20)

    # Если Memory Bank пуст — только минимальный контекст
    if not active and not progress:
        print(
            "**[SessionStart]** Memory Bank не найден. Критические константы: commission=0.0007 | engine=FallbackEngineV4"
        )
        sys.exit(0)

    header = "## [SessionStart] Memory Bank загружен"
    if source == "compact":
        header = "## [SessionStart после compact] Memory Bank загружен"

    print(header)
    print()

    if active:
        print("### 📍 Текущая работа (activeContext.md)")
        print(active)
        print()

    if progress:
        print("### 📊 Статус проекта (progress.md — кратко)")
        print(progress)
        print()

    if patterns:
        print("### 🏗️ Ключевые паттерны (systemPatterns.md — кратко)")
        print(patterns)
        print()

    print("---")
    print("⚠️  **Критически:** commission=0.0007 | engine=FallbackEngineV4 | Bash нестабилен → Read/Grep/Edit")
    print(f"📁 Проект: {cwd}")
    print(f"🔄 Источник сессии: {source}")

    sys.exit(0)


if __name__ == "__main__":
    main()
