#!/usr/bin/env python
"""
PostToolUseFailure hook — срабатывает когда инструмент завершается ошибкой.

Цель: предоставить контекстно-зависимые подсказки что делать когда инструмент упал.
Не блокирует Claude (exit 0 всегда) — только информирует.

Событие: PostToolUseFailure
Получает: tool_name, tool_input, tool_response (ошибка), exit_code
"""

import json
import sys

# Платформо-специфичные советы
BASH_HINTS = [
    "⚠️  Bash нестабилен (Cygwin fork errors на Windows).",
    "   Используй вместо него:",
    "   • Read — читать файлы",
    "   • Grep — искать в коде",
    "   • Glob — искать файлы по паттерну",
    "   • Edit/Write — редактировать файлы",
]

# Советы по конкретным командам
COMMAND_HINTS = {
    "pytest": [
        "💡 Если pytest упал:",
        "   • Проверь traceback — обычно проблема в первых строках ошибки",
        "   • conftest.py в корне добавляет backend/ в sys.path",
        "   • Запускай конкретный тест: pytest tests/path/test_file.py::test_name -v",
    ],
    "python": [
        "💡 Python упал. Частые причины:",
        "   • Import error → проверь что venv активирован и зависимости установлены",
        "   • Encoding error → PYTHONIOENCODING=utf-8 уже должен быть в env",
    ],
    "ruff": [
        "💡 Ruff упал. Проверь:",
        "   • Синтаксическую ошибку в файле — ruff не может форматировать невалидный Python",
        "   • Или запусти вручную: ruff check --fix <file> && ruff format <file>",
    ],
    "alembic": [
        "💡 Alembic упал. Частые причины:",
        "   • DATABASE_URL не задан в .env",
        "   • Конфликт версий миграций — проверь alembic/versions/",
    ],
    "git": [
        "💡 Git упал. Проверь:",
        "   • Нет незакоммиченных конфликтов (git status)",
        "   • Не пытаешься push --force или reset --hard (заблокировано политикой)",
    ],
}

# Советы по Edit/Write ошибкам
EDIT_HINTS = [
    "💡 Edit/Write упал. Возможные причины:",
    "   • Файл защищён protect_files.py: .env, alembic/versions/, .git/, *.lock",
    "   • old_string не найден в файле — проверь точное совпадение (включая пробелы)",
    "   • Файл был изменён после последнего чтения — перечитай его сначала (Read)",
]


def get_command_hint(command: str) -> list[str]:
    """Возвращает подсказки для конкретной команды."""
    cmd_lower = command.lower().strip()
    for key, hints in COMMAND_HINTS.items():
        if key in cmd_lower:
            return hints
    return []


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    error_msg = data.get("tool_response", "")

    lines = []

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        lines.extend(BASH_HINTS)
        cmd_hints = get_command_hint(command)
        if cmd_hints:
            lines.append("")
            lines.extend(cmd_hints)
        if command:
            lines.append(f"\n   Упавшая команда: {command[:120]}")

    elif tool_name in ("Edit", "Write"):
        file_path = tool_input.get("file_path", "")
        lines.extend(EDIT_HINTS)
        if file_path:
            lines.append(f"\n   Файл: {file_path}")

    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        lines.append(f"💡 Read упал для: {file_path}")
        lines.append("   Проверь что файл существует. Используй Glob для поиска файлов.")

    if lines:
        print("\n".join(lines), file=sys.stderr)

    sys.exit(0)  # Всегда exit 0 — не блокируем Claude


if __name__ == "__main__":
    main()
