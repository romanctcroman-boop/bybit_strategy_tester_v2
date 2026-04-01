#!/usr/bin/env python
"""
PreToolUse hook — защищает commission_value = 0.0007 от случайных изменений.

Срабатывает при Edit/Write Python-файлов.
Если в new_string/content обнаруживается 0.001 в контексте commission —
выводит предупреждение (exit 1) и блокирует.

Exit code 2 + stderr → Claude Code блокирует действие.
Exit code 0 → всё ок.
"""

import json
import re
import sys


# Паттерны: "commission" рядом с "0.001" (но НЕ 0.0007, 0.001_tolerance, 0.001_qty)
# Захватываем строки где есть commission AND значение 0.001 (не 0.0007)
COMMISSION_BAD_PATTERNS = [
    # commission_value = 0.001  или commission_rate = 0.001
    r"commission[_\s\w]*=\s*0\.001(?!7)",
    # "commission": 0.001
    r'"commission[^"]*"\s*:\s*0\.001(?!7)',
    # commission_value: 0.001  (YAML style)
    r"commission[_\w]*:\s*0\.001(?!7)",
]

# Исключения — эти паттерны в строке означают что это НЕ баг (legacy/tolerance/qty)
ALLOWLIST_PATTERNS = [
    r"optimize_tasks",
    r"ai_backtest_executor",
    r"tolerance",
    r"qty",
    r"#.*0\.001",           # комментарий
    r"legacy",
    r"fallback.*missing",
    r"_commission.*0\.001", # legacy DB param name
]


def check_content(content: str, file_path: str) -> list[str]:
    """Проверяет содержимое на плохие commission значения. Возвращает список нарушений."""
    violations = []
    lines = content.split("\n")

    for lineno, line in enumerate(lines, 1):
        # Проверяем allowlist — если совпадает, пропускаем строку
        skip = False
        for allow in ALLOWLIST_PATTERNS:
            if re.search(allow, line, re.IGNORECASE):
                skip = True
                break
        if skip:
            continue

        # Проверяем bad patterns
        for pattern in COMMISSION_BAD_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append(f"  Строка {lineno}: {line.strip()}")
                break

    return violations


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Только Python-файлы
    file_path = tool_input.get("file_path", "")
    if not file_path.endswith(".py"):
        sys.exit(0)

    # Получаем изменяемый контент
    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        sys.exit(0)

    if not content:
        sys.exit(0)

    violations = check_content(content, file_path)

    if violations:
        print(
            f"🔴 COMMISSION GUARD: обнаружено значение commission=0.001 вместо 0.0007!\n"
            f"Файл: {file_path}\n"
            f"Нарушения:\n" + "\n".join(violations) + "\n\n"
            f"Правило: commission_value ВСЕГДА = 0.0007 (TradingView parity).\n"
            f"Исключения (legacy/experimental): optimize_tasks.py, ai_backtest_executor.py\n"
            f"Если ты уверен что это исключение — добавь комментарий # legacy или явно попроси пользователя подтвердить.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
