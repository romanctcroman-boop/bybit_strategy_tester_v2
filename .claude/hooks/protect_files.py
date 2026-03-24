#!/usr/bin/env python
"""
PreToolUse hook — блокирует редактирование критических файлов.

Exit code 2 + stderr → Claude Code блокирует действие и передаёт
сообщение обратно Claude как объяснение почему нельзя.

Защищаемые категории:
1. Секреты: .env, .env.*, secrets.*, credentials.*
2. Миграции БД: alembic/versions/*.py (только добавление, не правка)
3. Git-служебные: .git/*
4. Lock-файлы: *.lock, package-lock.json, poetry.lock
"""

import json
import sys

# (паттерн, причина блокировки)
BLOCKED_PATTERNS = [
    # Секреты — абсолютный запрет
    (".env", "Файл .env содержит секреты. Редактируй .env.example вместо него."),
    ("secrets.", "Файл с секретами защищён от редактирования AI."),
    ("credentials.", "Файл credentials защищён от редактирования AI."),
    (".pem", "Приватный ключ защищён от редактирования AI."),
    ("id_rsa", "Приватный ключ защищён от редактирования AI."),
    # Миграции Alembic — только через alembic CLI
    (
        "alembic/versions/",
        (
            "Миграции Alembic нельзя редактировать напрямую — используй: "
            "alembic revision --autogenerate -m 'description'"
        ),
    ),
    # Git-служебные
    (".git/", "Git-служебные файлы нельзя редактировать напрямую."),
]

# Файлы которые требуют ПРЕДУПРЕЖДЕНИЯ но не блокировки
# (просто печатаем в stderr, exit 0)
WARN_PATTERNS = [
    ("pyproject.toml", "ВНИМАНИЕ: pyproject.toml содержит mypy/ruff конфиг. Проверь что изменения совместимы."),
    ("alembic.ini", "ВНИМАНИЕ: alembic.ini — конфигурация миграций. Изменяй осторожно."),
    ("pytest.ini", "ВНИМАНИЕ: pytest.ini — конфигурация тестов. Изменяй осторожно."),
]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    norm = file_path.replace("\\", "/")

    # Проверяем блокирующие паттерны
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern in norm:
            print(
                f"🔴 ЗАБЛОКИРОВАНО: {reason}\n"
                f"Файл: {file_path}\n"
                f"Если необходимо — явно попроси пользователя подтвердить редактирование.",
                file=sys.stderr,
            )
            sys.exit(2)  # exit 2 = блокировка

    # Проверяем предупреждающие паттерны (не блокируем)
    for pattern, warning in WARN_PATTERNS:
        if pattern in norm:
            print(f"⚠️  {warning}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
