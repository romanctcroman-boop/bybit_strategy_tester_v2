#!/usr/bin/env python
"""
PostToolUse hook — запускает целевые тесты после каждого Edit/Write Python-файла.

Получает JSON из stdin, определяет какие тесты гонять, запускает их.
Вывод идёт в stdout/stderr и виден в контексте Claude Code.
"""

import json
import os
import subprocess
import sys

# Маппинг: prefix пути файла → тест-путь (только startswith, без "in")
TEST_MAP = [
    ("backend/backtesting/engines/", "tests/backend/backtesting/test_engine.py"),
    ("backend/backtesting/strategy_builder_adapter", "tests/backend/backtesting/"),
    ("backend/backtesting/indicator_handlers", "tests/backend/backtesting/"),
    ("backend/backtesting/numba_engine", "tests/backend/backtesting/test_engine.py"),
    ("backend/backtesting/validation_suite", "tests/backend/backtesting/"),
    ("backend/backtesting/models", "tests/backend/backtesting/"),
    ("backend/backtesting/", "tests/backend/backtesting/"),
    ("backend/core/metrics_calculator", "tests/backend/core/"),
    ("backend/core/", "tests/backend/core/"),
    ("backend/api/routers/backtests", "tests/backend/api/test_backtests.py"),
    ("backend/api/routers/strategy_builder", "tests/backend/api/"),
    ("backend/api/", "tests/backend/api/"),
    ("backend/optimization/builder_optimizer", "tests/test_builder_optimizer.py"),
    ("backend/optimization/", "tests/backend/"),
    ("backend/agents/", "tests/backend/agents/"),
    ("backend/", "tests/backend/"),
]


def find_python():
    """Находит рабочий Python-исполняемый файл."""
    for candidate in ("python", "python3", "py"):
        try:
            result = subprocess.run([candidate, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def normalize_path(file_path: str) -> str:
    """Нормализует абсолютный путь → относительный от корня проекта."""
    norm = file_path.replace("\\", "/")
    # Ищем маркер проекта
    markers = ["bybit_strategy_tester_v2/"]
    for marker in markers:
        idx = norm.find(marker)
        if idx != -1:
            return norm[idx + len(marker) :]
    # Fallback: убираем CLAUDE_PROJECT_DIR если он совпадает
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "").replace("\\", "/").rstrip("/")
    if project_dir and norm.startswith(project_dir):
        return norm[len(project_dir) :].lstrip("/")
    return norm


def find_test_target(norm_path: str) -> str | None:
    """Возвращает тест-путь для данного файла, или None."""
    for prefix, target in TEST_MAP:
        if norm_path.startswith(prefix):
            return target
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    norm = normalize_path(file_path)

    # Только Python-файлы бэкенда
    if not norm.endswith(".py"):
        sys.exit(0)
    if not norm.startswith("backend/"):
        sys.exit(0)

    test_target = find_test_target(norm)
    if not test_target:
        sys.exit(0)

    # Используем CLAUDE_PROJECT_DIR для надёжного cwd
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", data.get("cwd", os.getcwd()))

    # Проверяем что тест-путь существует
    test_abs = os.path.join(cwd, test_target)
    if not os.path.exists(test_abs):
        print(f"[hook] Тест-путь не найден: {test_target}", file=sys.stderr)
        sys.exit(0)

    python = find_python()
    if not python:
        print("[hook] Python не найден в PATH — пропускаю тесты", file=sys.stderr)
        sys.exit(0)

    filename = os.path.basename(norm)
    print(f"\n[hook] Изменён: {filename} → запускаю: {test_target}", flush=True)

    result = subprocess.run(
        [python, "-m", "pytest", test_target, "-x", "-q", "--tb=short", "--no-header"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=115,  # чуть меньше hook timeout (120s)
    )

    # Показываем последние 35 строк (не спамим контекст)
    output = (result.stdout + result.stderr).strip()
    lines = output.splitlines()
    if len(lines) > 35:
        print(f"[hook] ... ({len(lines) - 35} строк скрыто, показываю последние 35)")
        lines = lines[-35:]
    print("\n".join(lines))

    if result.returncode != 0:
        print(f"\n[hook] ❌ ТЕСТЫ УПАЛИ (код {result.returncode}) — проверь {norm}")
    else:
        print("\n[hook] ✅ OK")

    sys.exit(0)  # всегда exit 0 — не блокируем Claude


if __name__ == "__main__":
    main()
