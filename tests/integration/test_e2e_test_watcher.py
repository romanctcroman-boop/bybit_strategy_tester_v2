"""
E2E тесты для Test Watcher - полный цикл работы

Проверяет:
1. Обнаружение изменений файлов
2. Запуск тестов с coverage
3. Отправка в DeepSeek API
4. Сохранение результатов
"""
import asyncio
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.task1_test_watcher.test_watcher import TestWatcher


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_e2e_file_change_detection():
    """
    E2E: Обнаружение изменения файла
    
    Workflow:
    1. Создаём temp директорию
    2. Создаём Python файл
    3. TestWatcher должен обнаружить изменение
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Создаём watcher
        watcher = TestWatcher(
            watch_path=str(temp_dir),
            debounce_seconds=1  # Короткий debounce для теста
        )
        
        # Создаём тестовый Python файл
        test_file = temp_dir / "test_module.py"
        test_file.write_text("""
def test_example():
    assert 1 + 1 == 2
""")
        
        # Симулируем обнаружение изменения
        watcher.handle_file_change(test_file)
        
        # Проверяем что файл добавлен (проверяем имя файла)
        assert any(str(f).endswith("test_module.py") for f in watcher.changed_files)
        
        # Проверяем timestamp обновлён
        assert watcher.last_change_time > 0
        
        print("✓ File change detection works")
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_e2e_debounce_mechanism():
    """
    E2E: Механизм debounce
    
    Workflow:
    1. Несколько быстрых изменений файлов
    2. Debounce должен сгруппировать их
    3. Обработка происходит только раз
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(
            watch_path=str(temp_dir),
            debounce_seconds=2
        )
        
        # Создаём несколько файлов быстро
        files = []
        for i in range(3):
            file_path = temp_dir / f"test_{i}.py"
            file_path.write_text(f"def test_{i}(): pass")
            watcher.handle_file_change(file_path)
            files.append(file_path)
            await asyncio.sleep(0.1)  # Быстрые изменения
        
        # Все файлы должны быть зарегистрированы (проверяем по именам)
        assert len(watcher.changed_files) >= 3
        
        # Запускаем debounced processing
        await watcher.debounced_processing()
        
        # После обработки - очищено
        assert len(watcher.changed_files) == 0
        
        print("✓ Debounce mechanism works")
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_e2e_run_tests_with_coverage():
    """
    E2E: Запуск тестов с coverage
    
    Workflow:
    1. Создаём простой тест
    2. Запускаем через watcher
    3. Проверяем результаты и coverage
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Создаём простой модуль
        module_file = temp_dir / "calculator.py"
        module_file.write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")
        
        # Создаём тест для модуля
        test_file = temp_dir / "test_calculator.py"
        test_file.write_text("""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from calculator import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
""")
        
        watcher = TestWatcher(watch_path=str(temp_dir))
        
        # Запускаем тесты
        results = await watcher.run_tests()
        
        # Проверяем результаты
        assert results["pytest_exit_code"] == 0, "Tests should pass"
        assert results["success"] == True
        assert "coverage_total" in results
        assert "coverage_by_file" in results
        
        print(f"✓ Tests ran successfully")
        print(f"  Coverage: {results['coverage_total']:.1f}%")
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_e2e_deepseek_api_mock():
    """
    E2E: Отправка в DeepSeek API (с моком)
    
    Workflow:
    1. Создаём результаты тестов
    2. Отправляем в DeepSeek (мок)
    3. Проверяем формат запроса и ответа
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir))
        
        # Тестовые результаты
        test_results = {
            "pytest_exit_code": 0,
            "coverage_total": 85.5,
            "coverage_by_file": {
                "test_module.py": {
                    "total_lines": 100,
                    "covered_lines": 85,
                    "coverage_percent": 85.0
                }
            },
            "timestamp": 1234567890,
            "success": True
        }
        
        changed_files = [Path("test_module.py")]
        
        # Мокаем DeepSeek API
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "Test analysis: All tests passing with good coverage."
                    }
                }],
                "model": "deepseek-chat",
                "usage": {"total_tokens": 100}
            }
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            # Отправляем в DeepSeek
            analysis = await watcher.send_to_deepseek(test_results, changed_files)
            
            # Проверяем результат
            assert analysis["success"] == True
            assert "analysis" in analysis
            assert "All tests passing" in analysis["analysis"]
            
            print("✓ DeepSeek API integration works")
    
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_e2e_save_results():
    """
    E2E: Сохранение результатов
    
    Workflow:
    1. Создаём результаты тестов и анализа
    2. Сохраняем через watcher
    3. Проверяем что файл создан и валиден
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        watcher = TestWatcher(watch_path=str(temp_dir))
        
        # Временная директория для результатов
        results_dir = temp_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)  # ✅ Создаём директорию
        watcher.results_dir = results_dir
        
        test_results = {
            "pytest_exit_code": 0,
            "coverage_total": 90.0,
            "success": True
        }
        
        analysis_results = {
            "analysis": "Good test coverage!",
            "success": True
        }
        
        changed_files = [Path("test_file.py")]
        
        # Сохраняем результаты
        await watcher.save_results(test_results, analysis_results, changed_files)
        
        # Проверяем что файл создан
        result_files = list(results_dir.glob("test_results_*.json"))
        assert len(result_files) > 0, "Result file should be created"
        
        # Проверяем содержимое
        with open(result_files[0], 'r') as f:
            saved_data = json.load(f)
        
        assert "test_results" in saved_data
        assert "analysis_results" in saved_data
        assert "changed_files" in saved_data
        assert saved_data["test_results"]["success"] == True
        
        print("✓ Results saved successfully")
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_e2e_full_cycle_mock():
    """
    E2E: Полный цикл работы (с моками)
    
    Full workflow:
    1. Изменение файла
    2. Debounce
    3. Запуск тестов
    4. DeepSeek анализ (мок)
    5. Сохранение результатов
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Создаём простой тест
        test_file = temp_dir / "test_simple.py"
        test_file.write_text("""
def test_simple():
    assert True
""")
        
        watcher = TestWatcher(
            watch_path=str(temp_dir),
            debounce_seconds=1
        )
        
        # Временная директория для результатов
        results_dir = temp_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)  # ✅ Создаём директорию
        watcher.results_dir = results_dir
        
        # 1. Обнаружение изменения
        watcher.handle_file_change(test_file)
        assert any(str(f).endswith("test_simple.py") for f in watcher.changed_files)  # ✅ Проверяем по имени
        print("✓ Step 1: File change detected")
        
        # 2. Debounce wait
        await asyncio.sleep(1.5)
        
        # 3. Запуск тестов (реальный)
        test_results = await watcher.run_tests()
        assert test_results["success"] == True
        print("✓ Step 2: Tests ran successfully")
        
        # 4. DeepSeek анализ (мок)
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "Analysis complete."
                    }
                }],
                "model": "deepseek-chat",
                "usage": {}
            }
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            analysis = await watcher.send_to_deepseek(
                test_results,
                [test_file]
            )
            
            assert analysis["success"] == True
            print("✓ Step 3: DeepSeek analysis completed")
        
        # 5. Сохранение результатов
        await watcher.save_results(test_results, analysis, [test_file])
        
        result_files = list(results_dir.glob("test_results_*.json"))
        assert len(result_files) > 0
        print("✓ Step 4: Results saved")
        
        print("\n✅ Full E2E cycle completed successfully!")
        
    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
