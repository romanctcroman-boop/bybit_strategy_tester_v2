#!/usr/bin/env python3
"""
Печатает маршруты приложения, связанные с тикерами (symbols-list, refresh-tickers).

Запуск из корня проекта (чтобы подхватить backend):
  py -3.14 scripts/list_tickers_routes.py

Если в выводе есть /api/v1/marketdata/symbols-list и /api/v1/refresh-tickers —
они зарегистрированы в загруженном app.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Добавить корень проекта в path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def main() -> None:
    from backend.api.app import app

    targets = ("symbols-list", "refresh-tickers", "symbols_list", "refresh_tickers")
    print("Registered routes containing 'symbols-list', 'refresh-tickers', etc.:\n")
    found = []
    for r in app.routes:
        path = getattr(r, "path", None) or getattr(r, "path_regex", "")
        name = getattr(r, "name", "")
        methods = getattr(r, "methods", set()) or getattr(r, "methods", set())
        path_str = str(path)
        if any(t in path_str or t in name for t in targets):
            found.append((path_str, methods, name))
    for path, methods, name in sorted(found, key=lambda x: x[0]):
        print(f"  {list(methods)!r:30} {path}  ({name})")
    if not found:
        print("  (none found — tickers routes may not be in loaded app)")
    print("\nAll /api/v1 routes (first 40):")
    api_routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api/v1")]
    for r in api_routes[:40]:
        path = getattr(r, "path", "")
        methods = getattr(r, "methods", set()) or set()
        print(f"  {list(methods)!r:30} {path}")


if __name__ == "__main__":
    main()
