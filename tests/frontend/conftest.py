"""
Playwright E2E — pytest configuration & fixtures
=================================================
Функции:
  - Запись Playwright trace при провале теста (для CI-дебаггинга)
  - Централизованный browser/context fixture
  - Автоматическое сохранение HTML-тела страницы при провале

Просмотр trace:
    playwright show-trace test-traces/<trace>.zip

Для CI (GitHub Actions) добавить в workflow:
    - uses: actions/upload-artifact@v4
      if: failure()
      with:
        name: playwright-traces
        path: test-traces/
        retention-days: 7
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
TRACE_DIR = Path("test-traces")
BASE_URL = "http://localhost:8000"

# Записывать traces только на CI (GITHUB_ACTIONS=true / CI=true) или всегда.
# Переменная PLAYWRIGHT_TRACES=always принудительно включает даже локально.
_trace_mode_env = os.environ.get("PLAYWRIGHT_TRACES", "")
TRACES_ENABLED: bool = (
    _trace_mode_env == "always" or os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
)


# ---------------------------------------------------------------------------
# Session-level: один браузер
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Создаём папку для traces заранее."""
    TRACE_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def playwright_instance():
    """Единственный экземпляр Playwright на всю сессию."""
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance):
    """Единственный браузер (Chromium headless) на всю сессию."""
    b = playwright_instance.chromium.launch(headless=True)
    yield b
    b.close()


# ---------------------------------------------------------------------------
# Test-level: новый контекст + страница, trace при провале
# ---------------------------------------------------------------------------


@pytest.fixture
def context(browser: Browser) -> BrowserContext:
    """
    Новый контекст для каждого теста.
    При включённых traces — запускает запись (snapshot + screenshots).
    """
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
    )
    if TRACES_ENABLED:
        ctx.tracing.start(
            screenshots=True,
            snapshots=True,
            sources=False,  # исходники JS не нужны — только DOM
        )
    return ctx


@pytest.fixture
def page(context: BrowserContext, request: pytest.FixtureRequest) -> Page:
    """
    Страница для теста.
    При провале: сохраняет trace + screenshot + HTML дамп.
    """
    p = context.new_page()
    yield p

    # ── POST-TEST ──────────────────────────────────────────────────────────
    failed = request.node.rep_call.failed if hasattr(request.node, "rep_call") else False

    if TRACES_ENABLED:
        # Безопасное имя файла из pytest node id
        safe_name = _safe_filename(request.node.nodeid)
        trace_path = TRACE_DIR / f"{safe_name}.zip"
        context.tracing.stop(path=str(trace_path))
        if not failed:
            # Тест прошёл — удаляем trace чтобы не занимал место
            trace_path.unlink(missing_ok=True)
        else:
            print(f"\n🎭 Playwright trace saved: {trace_path}")
            print(f"   View with: playwright show-trace {trace_path}")

    if failed:
        # Screenshot при провале (независимо от режима traces)
        try:
            screenshot_dir = TRACE_DIR / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            safe_name = _safe_filename(request.node.nodeid)
            screenshot_path = screenshot_dir / f"{safe_name}.png"
            p.screenshot(path=str(screenshot_path), full_page=True)
            print(f"\n📸 Screenshot saved: {screenshot_path}")
        except Exception:
            pass  # не блокируем основной провал теста

        # HTML дамп при провале
        try:
            html_dir = TRACE_DIR / "html"
            html_dir.mkdir(exist_ok=True)
            safe_name = _safe_filename(request.node.nodeid)
            html_path = html_dir / f"{safe_name}.html"
            html_content = p.content()
            html_path.write_text(html_content, encoding="utf-8")
            print(f"\n📄 HTML dump saved: {html_path}")
        except Exception:
            pass

    context.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """Записывает результат каждой фазы теста в item для доступа в fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_filename(nodeid: str) -> str:
    """
    Преобразует pytest node id в безопасное имя файла.
    Пример: "tests/frontend/test_pages_e2e.py::TestPageLoad::test_page_loads_in_browser[/frontend/trading.html]"
    → "TestPageLoad__test_page_loads_in_browser__frontend_trading.html"
    """
    # Берём только часть после последнего "::" (имя теста + параметр)
    parts = nodeid.split("::")
    short = "__".join(parts[1:]) if len(parts) > 1 else nodeid
    # Заменяем недопустимые символы
    for char in r'/\:*?"<>|[]{}(),;':
        short = short.replace(char, "_")
    return short[:120]  # ограничиваем длину


# ---------------------------------------------------------------------------
# Fixture: server_available (переехал из test_pages_e2e.py для reuse)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def server_available():
    """Проверяем доступность сервера один раз на сессию."""
    import requests as req

    try:
        r = req.get(f"{BASE_URL}/api/v1/health", timeout=5)
        assert r.status_code == 200, f"Server returned {r.status_code}"
    except Exception as e:
        pytest.skip(f"Server not available at {BASE_URL}: {e}")
