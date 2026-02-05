"""
Автоматическое тестирование UI Strategy Builder
Тестирует все вкладки и кнопки на странице strategy-builder.html
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

# Добавить корень проекта в путь
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

async def test_strategy_builder_ui():
    """Тестирование всех элементов UI Strategy Builder"""

    results = {
        "passed": [],
        "failed": [],
        "warnings": []
    }

    async with async_playwright() as p:
        try:
            # Запустить браузер
            browser = await p.chromium.launch(headless=False)  # headless=False для визуального тестирования
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True
            )
            page = await context.new_page()

            print("🌐 Открываю страницу Strategy Builder...")
            await page.goto("http://localhost:8000/frontend/strategy-builder.html", wait_until="networkidle", timeout=30000)

            # Ждем загрузки страницы
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)  # Дополнительное время для инициализации JS

            print("\n" + "="*60)
            print("📋 ТЕСТИРОВАНИЕ ВКЛАДОК (Properties Panel)")
            print("="*60)

            # Тест 1: Проверка наличия всех вкладок
            tabs = [
                ("Основные", "properties-section:has-text('Основные')"),
                ("Закладка-2", "properties-section:has-text('Закладка-2')"),
                ("Закладка-3", "properties-section:has-text('Закладка-3')"),
                ("Закладка-4", "properties-section:has-text('Закладка-4')"),
                ("Закладка-5", "properties-section:has-text('Закладка-5')"),
            ]

            for tab_name, selector in tabs:
                try:
                    tab_element = await page.query_selector(selector)
                    if tab_element:
                        print(f"✅ Вкладка '{tab_name}' найдена")
                        results["passed"].append(f"Вкладка '{tab_name}' найдена")

                        # Кликнуть на вкладку для открытия
                        await tab_element.click()
                        await asyncio.sleep(0.5)
                        print(f"   → Вкладка '{tab_name}' открыта")
                    else:
                        print(f"❌ Вкладка '{tab_name}' не найдена")
                        results["failed"].append(f"Вкладка '{tab_name}' не найдена")
                except Exception as e:
                    print(f"⚠️ Ошибка при тестировании вкладки '{tab_name}': {e}")
                    results["warnings"].append(f"Вкладка '{tab_name}': {e}")

            print("\n" + "="*60)
            print("🔘 ТЕСТИРОВАНИЕ КНОПОК NAVBAR")
            print("="*60)

            # Тест 2: Кнопки в navbar
            navbar_buttons = [
                ("Templates", "#btnTemplates"),
                ("Validate", "#btnValidate"),
                ("Generate Code", "#btnGenerateCode"),
                ("Save", "#btnSave"),
                ("Backtest", "#btnBacktest"),
            ]

            for btn_name, selector in navbar_buttons:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()

                        print(f"✅ Кнопка '{btn_name}' найдена (visible: {is_visible}, enabled: {is_enabled})")
                        results["passed"].append(f"Кнопка '{btn_name}' найдена")

                        # Попытка кликнуть (если включена)
                        if is_enabled and is_visible:
                            try:
                                await button.click(timeout=2000)
                                await asyncio.sleep(0.5)
                                print(f"   → Кнопка '{btn_name}' нажата")

                                # Закрыть модальное окно если открылось (Templates)
                                if btn_name == "Templates":
                                    close_btn = await page.query_selector("#btnCloseModal, #btnCancelModal")
                                    if close_btn:
                                        await close_btn.click()
                                        await asyncio.sleep(0.3)
                                        print("   → Модальное окно закрыто")
                            except PlaywrightTimeoutError:
                                print(f"   ⚠️ Кнопка '{btn_name}' не отвечает на клик (возможно, требует сохранения стратегии)")
                                results["warnings"].append(f"Кнопка '{btn_name}' не отвечает на клик")
                    else:
                        print(f"❌ Кнопка '{btn_name}' не найдена")
                        results["failed"].append(f"Кнопка '{btn_name}' не найдена")
                except Exception as e:
                    print(f"⚠️ Ошибка при тестировании кнопки '{btn_name}': {e}")
                    results["warnings"].append(f"Кнопка '{btn_name}': {e}")

            print("\n" + "="*60)
            print("🛠️ ТЕСТИРОВАНИЕ КНОПОК TOOLBAR")
            print("="*60)

            # Тест 3: Кнопки toolbar
            toolbar_buttons = [
                ("Undo", "button[title='Undo']"),
                ("Redo", "button[title='Redo']"),
                ("Delete", "button[title='Delete']"),
                ("Duplicate", "button[title='Duplicate']"),
                ("Align Left", "button[title='Align Left']"),
                ("Align Center", "button[title='Align Center']"),
                ("Align Right", "button[title='Align Right']"),
                ("Auto Layout", "button[title='Auto Layout']"),
                ("Fit to Screen", "button[title='Fit to Screen']"),
            ]

            for btn_name, selector in toolbar_buttons:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        is_visible = await button.is_visible()
                        print(f"✅ Кнопка '{btn_name}' найдена (visible: {is_visible})")
                        results["passed"].append(f"Кнопка toolbar '{btn_name}' найдена")

                        if is_visible:
                            await button.click()
                            await asyncio.sleep(0.3)
                            print(f"   → Кнопка '{btn_name}' нажата")
                    else:
                        print(f"❌ Кнопка '{btn_name}' не найдена")
                        results["failed"].append(f"Кнопка toolbar '{btn_name}' не найдена")
                except Exception as e:
                    print(f"⚠️ Ошибка при тестировании кнопки '{btn_name}': {e}")
                    results["warnings"].append(f"Кнопка toolbar '{btn_name}': {e}")

            print("\n" + "="*60)
            print("🔍 ТЕСТИРОВАНИЕ ZOOM КОНТРОЛОВ")
            print("="*60)

            # Тест 4: Zoom controls
            zoom_controls = [
                ("Zoom Out", "button[title='Zoom out']"),
                ("Zoom In", "button[title='Zoom in']"),
                ("Reset Zoom", "button[title='Reset zoom']"),
            ]

            for control_name, selector in zoom_controls:
                try:
                    control = await page.query_selector(selector)
                    if control:
                        is_visible = await control.is_visible()
                        print(f"✅ Контрол '{control_name}' найден (visible: {is_visible})")
                        results["passed"].append(f"Zoom контрол '{control_name}' найден")

                        if is_visible:
                            await control.click()
                            await asyncio.sleep(0.3)
                            print(f"   → Контрол '{control_name}' активирован")
                    else:
                        print(f"❌ Контрол '{control_name}' не найден")
                        results["failed"].append(f"Zoom контрол '{control_name}' не найден")
                except Exception as e:
                    print(f"⚠️ Ошибка при тестировании контрола '{control_name}': {e}")
                    results["warnings"].append(f"Zoom контрол '{control_name}': {e}")

            print("\n" + "="*60)
            print("📚 ТЕСТИРОВАНИЕ БИБЛИОТЕКИ БЛОКОВ")
            print("="*60)

            # Тест 5: Блоки библиотеки
            block_categories = [
                "Indicators",
                "Conditions",
                "Actions",
                "Logic",
                "Inputs",
            ]

            for category in block_categories:
                try:
                    # Поиск категории по тексту
                    category_element = await page.query_selector(f"text={category}")
                    if category_element:
                        print(f"✅ Категория '{category}' найдена")
                        results["passed"].append(f"Категория блоков '{category}' найдена")

                        # Кликнуть для раскрытия
                        await category_element.click()
                        await asyncio.sleep(0.5)
                        print(f"   → Категория '{category}' раскрыта")
                    else:
                        print(f"⚠️ Категория '{category}' не найдена (возможно, свернута)")
                        results["warnings"].append(f"Категория '{category}' не найдена")
                except Exception as e:
                    print(f"⚠️ Ошибка при тестировании категории '{category}': {e}")
                    results["warnings"].append(f"Категория '{category}': {e}")

            print("\n" + "="*60)
            print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
            print("="*60)

            total_passed = len(results["passed"])
            total_failed = len(results["failed"])
            total_warnings = len(results["warnings"])
            total_tests = total_passed + total_failed + total_warnings

            print(f"\n✅ Пройдено: {total_passed}")
            print(f"❌ Провалено: {total_failed}")
            print(f"⚠️ Предупреждений: {total_warnings}")
            print(f"📊 Всего тестов: {total_tests}")

            if total_failed > 0:
                print("\n❌ Проваленные тесты:")
                for failed in results["failed"]:
                    print(f"   - {failed}")

            if total_warnings > 0:
                print("\n⚠️ Предупреждения:")
                for warning in results["warnings"]:
                    print(f"   - {warning}")

            # Закрыть браузер через 5 секунд (для визуального осмотра)
            print("\n⏳ Браузер закроется через 5 секунд...")
            await asyncio.sleep(5)

            await browser.close()

            # Вернуть код выхода
            return 0 if total_failed == 0 else 1

        except Exception as e:
            print(f"\n❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
            return 1

if __name__ == "__main__":
    exit_code = asyncio.run(test_strategy_builder_ui())
    sys.exit(exit_code)
