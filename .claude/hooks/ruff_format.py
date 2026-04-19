#!/usr/bin/env python
"""
PostToolUse hook — запускает ruff check --fix и ruff format на отредактированном файле.
Быстрый quality gate: форматирование + lint прямо после каждого Edit/Write.

Запускается ПАРАЛЛЕЛЬНО с post_edit_tests.py (оба зарегистрированы в PostToolUse).
Ruff намного быстрее pytest, поэтому feedback приходит сразу.
"""

import json
import os
import subprocess
import sys


def find_python() -> str:
    for candidate in ("python", "python3", "py"):
        try:
            r = subprocess.run([candidate, "--version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return "python"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Только Python-файлы, исключая хуки и тесты (тесты форматирует тот же ruff)
    norm = file_path.replace("\\", "/")
    if not norm.endswith(".py"):
        sys.exit(0)

    # Исключаем временные и сгенерированные файлы
    skip_patterns = ["__pycache__", ".pyc", "migrations/versions/", "temp_analysis/"]
    if any(p in norm for p in skip_patterns):
        sys.exit(0)

    cwd = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", os.getcwd()))
    python = find_python()
    abs_path = file_path  # уже абсолютный путь из tool_input

    # ruff check --fix (исправляет автоматически исправимые lint-ошибки)
    fix_result = subprocess.run(
        [python, "-m", "ruff", "check", "--fix", "--quiet", abs_path],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    # ruff format (форматирование)
    fmt_result = subprocess.run(
        [python, "-m", "ruff", "format", "--quiet", abs_path],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    # Выводим только если есть что-то существенное
    filename = os.path.basename(norm)
    issues = []

    if fix_result.returncode != 0:
        out = (fix_result.stdout + fix_result.stderr).strip()
        if out:
            issues.append(f"ruff check:\n{out}")

    if fmt_result.returncode != 0:
        out = (fmt_result.stdout + fmt_result.stderr).strip()
        if out:
            issues.append(f"ruff format:\n{out}")

    if issues:
        print(f"\n[ruff] ⚠️  {filename}:\n" + "\n".join(issues))
    # Если всё чисто — молчим (не засоряем контекст)

    sys.exit(0)


if __name__ == "__main__":
    main()
