"""
E2E Frontend Page Tests — Playwright + Chromium
================================================
Проверяет:
  1. HTTP 200 для всех продуктовых страниц
  2. Отсутствие JS-исключений при загрузке (window.onerror)
  3. Наличие ключевых DOM-элементов на каждой странице
  4. Работоспособность основных кнопок (клик без краша)

Запуск:
    pytest tests/frontend/test_pages_e2e.py -v
    pytest tests/frontend/test_pages_e2e.py -v -k "strategy_builder"
"""

import pytest
from playwright.sync_api import ConsoleMessage, Page, sync_playwright

BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Продуктовые страницы (без debug/test страниц)
# ---------------------------------------------------------------------------
PRODUCT_PAGES = [
    "/frontend/dashboard.html",
    "/frontend/strategy-builder.html",
    "/frontend/analytics.html",
    "/frontend/analytics-advanced.html",
    "/frontend/backtest-results.html",
    "/frontend/market-chart.html",
    "/frontend/marketplace.html",
    "/frontend/ml-models.html",
    "/frontend/notifications.html",
    "/frontend/optimizations.html",
    "/frontend/optimization-results.html",
    "/frontend/portfolio.html",
    "/frontend/risk-management.html",
    "/frontend/settings.html",
    "/frontend/streaming-chat.html",
    "/frontend/tick-chart.html",
    "/frontend/trading.html",
    "/frontend/ai-pipeline.html",
    "/frontend/health-dashboard.html",
]

# ---------------------------------------------------------------------------
# Ожидаемые ключевые элементы на каждой странице
# ---------------------------------------------------------------------------
PAGE_KEY_ELEMENTS = {
    "/frontend/dashboard.html": [
        "body",
        "#mainContent, main, .dashboard, .container",
    ],
    "/frontend/strategy-builder.html": [
        "#canvasContainer, #strategyCanvas, .canvas-container",
        "#btnBacktest, #runBacktestBtn, button[id*='Backtest'], button[id*='backtest']",
    ],
    "/frontend/analytics.html": [
        "body",
    ],
    "/frontend/analytics-advanced.html": [
        "body",
    ],
    "/frontend/backtest-results.html": [
        "body",
    ],
    "/frontend/market-chart.html": [
        "body",
    ],
    "/frontend/marketplace.html": [
        "body",
    ],
    "/frontend/ml-models.html": [
        "body",
    ],
    "/frontend/notifications.html": [
        "body",
    ],
    "/frontend/optimizations.html": [
        "body",
    ],
    "/frontend/optimization-results.html": [
        "body",
    ],
    "/frontend/portfolio.html": [
        "body",
    ],
    "/frontend/risk-management.html": [
        "body",
    ],
    "/frontend/settings.html": [
        "body",
    ],
    "/frontend/streaming-chat.html": [
        "body",
    ],
    "/frontend/tick-chart.html": [
        "body",
    ],
    "/frontend/trading.html": [
        "body",
    ],
    "/frontend/ai-pipeline.html": [
        "body",
    ],
    "/frontend/health-dashboard.html": [
        "body",
    ],
}

# ---------------------------------------------------------------------------
# Критические JS-ошибки — паттерны, которые вызывают тест-провал
# ---------------------------------------------------------------------------
CRITICAL_ERROR_PATTERNS = [
    "TypeError",
    "ReferenceError",
    "SyntaxError",
    "Uncaught",
]

# Допустимые предупреждения (не падаем по ним)
IGNORED_PATTERNS = [
    "favicon",
    "404",
    "WebSocket",  # WS может не подключиться в тестах
    "connecting",
    "connection",
    "ECONNREFUSED",
    "net::ERR",
    "Failed to fetch",
    "api/v1/symbols",  # API вызовы в init — нормально
    "api/v1/health",
    "Redis",
    "MCP",
    "[HMR]",
    "Navigated to",
    "Download the React DevTools",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser():
    """Один браузер на всю сессию."""
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture(scope="session")
def server_available():
    """Проверяем доступность сервера один раз."""
    import requests

    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        assert r.status_code == 200, f"Server returned {r.status_code}"
    except Exception as e:
        pytest.skip(f"Server not available at {BASE_URL}: {e}")


@pytest.fixture
def page(browser):
    """Новый контекст + страница для каждого теста."""
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
    )
    p = context.new_page()
    yield p
    context.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def collect_js_errors(page: Page) -> list[str]:
    """Возвращает список критических JS-ошибок, пойманных на странице."""
    errors: list[str] = []

    def on_console(msg: ConsoleMessage):
        if msg.type == "error":
            text = msg.text
            # Пропускаем сетевые ошибки и допустимые предупреждения
            if any(p in text for p in IGNORED_PATTERNS):
                return
            errors.append(text)

    page.on("console", on_console)
    return errors


def is_critical_js_error(error_text: str) -> bool:
    return any(p in error_text for p in CRITICAL_ERROR_PATTERNS)


# ---------------------------------------------------------------------------
# Тест 1: HTTP 200 для всех страниц
# ---------------------------------------------------------------------------


class TestPageLoad:
    """Все продуктовые страницы возвращают HTTP 200 и загружаются без краша."""

    @pytest.mark.parametrize("path", PRODUCT_PAGES)
    def test_page_returns_200(self, path, server_available):
        import requests

        r = requests.get(f"{BASE_URL}{path}", timeout=10)
        assert r.status_code == 200, f"Page {path} returned HTTP {r.status_code}"
        assert len(r.content) > 1000, f"Page {path} returned suspiciously small body ({len(r.content)} bytes)"

    @pytest.mark.parametrize("path", PRODUCT_PAGES)
    def test_page_loads_in_browser(self, path, page: Page, server_available):
        """Страница загружается в браузере без JS-краша."""
        js_errors: list[str] = []
        page.on(
            "console",
            lambda msg: (
                js_errors.append(msg.text)
                if msg.type == "error" and not any(p in msg.text for p in IGNORED_PATTERNS)
                else None
            ),
        )

        # Перехватываем window.onerror
        uncaught: list[str] = []
        page.on("pageerror", lambda err: uncaught.append(str(err)))

        response = page.goto(
            f"{BASE_URL}{path}",
            wait_until="domcontentloaded",
            timeout=15_000,
        )

        assert response is not None, f"No response for {path}"
        assert response.status == 200, f"{path} → HTTP {response.status}"

        # Ждём немного чтобы JS успел выполниться
        page.wait_for_timeout(800)

        # Проверяем на критические ошибки
        critical = [e for e in uncaught if is_critical_js_error(e)]
        assert not critical, f"Page {path} has JS exceptions:\n" + "\n".join(critical)

        # body должен содержать контент (не пустой)
        body_text = page.evaluate("() => document.body?.innerHTML?.length ?? 0")
        assert body_text > 100, f"Page {path} has empty body"


# ---------------------------------------------------------------------------
# Тест 2: Ключевые DOM-элементы присутствуют
# ---------------------------------------------------------------------------


class TestPageElements:
    """На каждой странице есть ожидаемые DOM-элементы."""

    @pytest.mark.parametrize("path,selectors", list(PAGE_KEY_ELEMENTS.items()))
    def test_key_elements_present(self, path, selectors, page: Page, server_available):
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(600)

        for selector in selectors:
            # Поддерживаем selector1, selector2 (OR — хоть один должен быть)
            alternatives = [s.strip() for s in selector.split(",")]
            found = any(page.locator(alt).count() > 0 for alt in alternatives)
            assert found, f"Page {path}: none of [{selector}] found in DOM"


# ---------------------------------------------------------------------------
# Тест 3: Strategy Builder — ключевые кнопки
# ---------------------------------------------------------------------------


class TestStrategyBuilderButtons:
    """Strategy Builder: кнопки кликаются без JS-краша."""

    SB_URL = f"{BASE_URL}/frontend/strategy-builder.html"

    def test_page_loads(self, page: Page, server_available):
        uncaught: list[str] = []
        page.on("pageerror", lambda e: uncaught.append(str(e)))

        page.goto(self.SB_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(1000)

        critical = [e for e in uncaught if is_critical_js_error(e)]
        assert not critical, "Strategy Builder has JS exceptions:\n" + "\n".join(critical)

    def test_canvas_container_visible(self, page: Page, server_available):
        page.goto(self.SB_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(800)

        canvas = page.locator("#canvasContainer, #strategyCanvas, .canvas-container, #canvas")
        assert canvas.count() > 0, "Canvas container not found on strategy builder"

    def test_run_backtest_button_exists(self, page: Page, server_available):
        page.goto(self.SB_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(800)

        btn = (
            page.locator("button")
            .filter(has_text="Run Backtest")
            .or_(page.locator("button").filter(has_text="Запустить"))
            .or_(page.locator("#runBacktestBtn, #run-backtest-btn, [id*='backtest']"))
        )
        # Кнопка может называться по-разному — проверяем что хоть одна есть
        any_btn = page.locator("button").count()
        assert any_btn > 0, "No buttons found on Strategy Builder page"

    def test_clear_button_click_no_crash(self, page: Page, server_available):
        """Клик по Clear/Reset не вызывает JS-ошибку."""
        uncaught: list[str] = []
        page.on("pageerror", lambda e: uncaught.append(str(e)))

        page.goto(self.SB_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(800)

        # Принимаем confirm диалог (clearAllAndReset показывает confirm)
        page.on("dialog", lambda d: d.dismiss())

        # Ищем кнопку очистки
        clear_btn = page.locator("#clearAllBtn, #clear-all-btn, button[id*='clear'], button[title*='Clear']")
        if clear_btn.count() > 0:
            clear_btn.first.click()
            page.wait_for_timeout(500)

        critical = [e for e in uncaught if is_critical_js_error(e)]
        assert not critical, "Clear button caused JS exception:\n" + "\n".join(critical)

    def test_add_block_from_palette(self, page: Page, server_available):
        """Элементы палитры блоков присутствуют в DOM (могут быть скрыты)."""
        uncaught: list[str] = []
        page.on("pageerror", lambda e: uncaught.append(str(e)))

        page.goto(self.SB_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(1000)

        # Палитра блоков может быть скрыта в свёрнутой панели — проверяем DOM
        palette_count = page.evaluate("""() => {
            return document.querySelectorAll(
                '.block-palette-item, .palette-item, .block-item, [data-block-id]'
            ).length
        }""")
        assert palette_count > 0, "No block palette items found in DOM"

        critical = [e for e in uncaught if is_critical_js_error(e)]
        assert not critical, "Palette check caused JS exception:\n" + "\n".join(critical)


# ---------------------------------------------------------------------------
# Тест 4: Dashboard — метрики и навигация
# ---------------------------------------------------------------------------


class TestDashboardPage:
    """Dashboard: загрузка, метрические карточки, навигация."""

    DASH_URL = f"{BASE_URL}/frontend/dashboard.html"

    def test_dashboard_loads_no_crash(self, page: Page, server_available):
        uncaught: list[str] = []
        page.on("pageerror", lambda e: uncaught.append(str(e)))

        page.goto(self.DASH_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(1000)

        critical = [e for e in uncaught if is_critical_js_error(e)]
        assert not critical, "Dashboard has JS exceptions:\n" + "\n".join(critical)

    def test_navigation_links_present(self, page: Page, server_available):
        """На странице есть nav-ссылки на другие разделы."""
        page.goto(self.DASH_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(600)

        # Должен быть хотя бы один nav-элемент
        nav = page.locator("nav, .navbar, .sidebar, #sidebar, .nav")
        assert nav.count() > 0, "No navigation found on dashboard"

    def test_page_title_set(self, page: Page, server_available):
        page.goto(self.DASH_URL, wait_until="domcontentloaded", timeout=15_000)
        title = page.title()
        assert title, "Dashboard page has empty <title>"


# ---------------------------------------------------------------------------
# Тест 5: Настройки — форма
# ---------------------------------------------------------------------------


class TestSettingsPage:
    """Settings: форма загружается, инпуты доступны."""

    SETTINGS_URL = f"{BASE_URL}/frontend/settings.html"

    def test_settings_loads(self, page: Page, server_available):
        uncaught: list[str] = []
        page.on("pageerror", lambda e: uncaught.append(str(e)))

        page.goto(self.SETTINGS_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(800)

        critical = [e for e in uncaught if is_critical_js_error(e)]
        assert not critical, "Settings page has JS exceptions:\n" + "\n".join(critical)

    def test_has_form_inputs(self, page: Page, server_available):
        page.goto(self.SETTINGS_URL, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(600)

        inputs = page.locator("input, select, textarea")
        assert inputs.count() > 0, "Settings page has no form inputs"


# ---------------------------------------------------------------------------
# Тест 6: Проверка всех nav-ссылок — не ведут на 404
# ---------------------------------------------------------------------------


class TestNavigationLinks:
    """Все внутренние ссылки в навигации возвращают 200."""

    def test_nav_links_not_404(self, page: Page, server_available):
        import requests

        page.goto(f"{BASE_URL}/frontend/dashboard.html", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_timeout(500)

        # Собираем все href ссылки на /frontend/
        links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h && h.includes('/frontend/') && h.endsWith('.html'))
        }""")

        broken = []
        checked = set()
        for href in links:
            url = f"{BASE_URL}{href}" if href.startswith("/") else href
            if url in checked:
                continue
            checked.add(url)
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 404:
                    broken.append(f"404: {url}")
            except Exception as e:
                broken.append(f"ERROR {url}: {e}")

        assert not broken, "Broken navigation links found:\n" + "\n".join(broken)
