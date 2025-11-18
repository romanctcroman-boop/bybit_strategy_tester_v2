"""
Test Watcher - Автоматическая верификация тестов через DeepSeek AI

Мониторит изменения Python файлов, автоматически запускает тесты с покрытием
и отправляет результаты в DeepSeek для анализа.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import httpx
import pytest
import coverage
from loguru import logger
from dotenv import load_dotenv

# Загрузка переменных окружения
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

# Интеграция с KeyManager
sys.path.insert(0, str(project_root / "automation" / "task2_key_manager"))
from key_manager import KeyManager


class TestWatcher:
    """Система автоматической верификации тестов с AI анализом"""
    
    def __init__(self, watch_path: str = ".", debounce_seconds: int = 20):
        self.watch_path = Path(watch_path).resolve()
        self.debounce_seconds = debounce_seconds
        self.observer = Observer()
        self.changed_files: Set[Path] = set()
        self.last_change_time = 0
        self.processing = False
        self.loop = None  # Event loop будет установлен в start()
        
        # Инициализация KeyManager для безопасного получения API ключей
        self.key_manager = KeyManager()
        self._init_api_keys()
        
        # DeepSeek API configuration
        self.deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
        
        # Results directory
        self.results_dir = project_root / "ai_audit_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Configure logging
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / "test_watcher.log"
        logger.add(str(log_file), rotation="10 MB", level="INFO")
        
    def _init_api_keys(self):
        """Инициализация API ключей через KeyManager"""
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if encryption_key and self.key_manager.initialize_encryption(encryption_key):
            secrets_file = project_root / "encrypted_secrets.json"
            if secrets_file.exists() and self.key_manager.load_keys(str(secrets_file)):
                self.deepseek_api_key = self.key_manager.get_key("DEEPSEEK_API_KEY")
                if self.deepseek_api_key:
                    logger.info("[OK] DEEPSEEK_API_KEY loaded from KeyManager")
                else:
                    logger.warning("[WARN] DEEPSEEK_API_KEY not found in KeyManager")
                    self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
            else:
                logger.warning("[WARN] Falling back to .env for API keys")
                self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        else:
            logger.warning("[WARN] KeyManager not available, using .env")
            self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        
        if not self.deepseek_api_key:
            logger.error("[ERROR] DEEPSEEK_API_KEY not configured!")
        
    class ChangeHandler(FileSystemEventHandler):
        """Обработчик событий изменения файлов"""
        
        def __init__(self, watcher):
            self.watcher = watcher
            
        def on_modified(self, event):
            if not event.is_directory:
                file_path = Path(event.src_path)
                if file_path.suffix in ['.py', '.pyx', '.pyi']:
                    self.watcher.handle_file_change(file_path)
                    
        def on_created(self, event):
            if not event.is_directory:
                file_path = Path(event.src_path)
                if file_path.suffix in ['.py', '.pyx', '.pyi']:
                    self.watcher.handle_file_change(file_path)
                    
        def on_deleted(self, event):
            if not event.is_directory:
                file_path = Path(event.src_path)
                if file_path.suffix in ['.py', '.pyx', '.pyi']:
                    self.watcher.handle_file_change(file_path)
    
    def handle_file_change(self, file_path: Path):
        """Обработка изменения файла с debouncing"""
        current_time = time.time()
        
        # Нормализация пути
        try:
            normalized_path = file_path.resolve().relative_to(self.watch_path)
        except ValueError:
            normalized_path = file_path.resolve()
            
        self.changed_files.add(normalized_path)
        self.last_change_time = current_time
        
        logger.info(f"File changed: {normalized_path}")
        
        # Запланировать обработку если еще не запланирована
        if not self.processing and self.loop:
            self.processing = True
            # Используем run_coroutine_threadsafe для вызова из другого потока
            asyncio.run_coroutine_threadsafe(self.debounced_processing(), self.loop)
    
    async def debounced_processing(self):
        """Ожидание debounce периода и обработка изменений"""
        await asyncio.sleep(self.debounce_seconds)
        
        # Проверка наличия более поздних изменений
        if time.time() - self.last_change_time >= self.debounce_seconds - 1:
            await self.process_changes()
        else:
            # Перепланирование если были недавние изменения
            self.processing = False
            await self.debounced_processing()
    
    async def process_changes(self):
        """Обработка накопленных изменений файлов"""
        if not self.changed_files:
            self.processing = False
            return
            
        changed_files_list = list(self.changed_files)
        self.changed_files.clear()
        
        logger.info(f"Processing {len(changed_files_list)} changed files")
        
        try:
            # Запуск тестов
            test_results = await self.run_tests()
            
            # Отправка в DeepSeek для анализа
            analysis_results = await self.send_to_deepseek(test_results, changed_files_list)
            
            # Сохранение результатов
            await self.save_results(test_results, analysis_results, changed_files_list)
            
            logger.success("Test verification completed successfully")
            
        except Exception as e:
            logger.error(f"Error during test verification: {e}")
        finally:
            self.processing = False
    
    async def run_tests(self) -> Dict:
        """Запуск pytest с coverage и возврат результатов"""
        logger.info("Running tests with coverage...")
        
        # Настройка coverage
        cov = coverage.Coverage()
        cov.start()
        
        # Запуск pytest
        pytest_args = [
            "-v",
            "--tb=short",
            "--disable-warnings",
            "--color=yes"
        ]
        
        try:
            pytest_result = pytest.main(pytest_args)
            
            # Остановка coverage и получение результатов
            cov.stop()
            cov.save()
            
            # Получение данных покрытия
            coverage_data = {}
            cov_data = cov.get_data()
            
            for filename in cov_data.measured_files():
                try:
                    relative_path = Path(filename).relative_to(self.watch_path)
                    line_coverage = cov_data.lines(filename)
                    covered_lines = cov_data.covered_lines(filename)
                    missing_lines = cov_data.missing_lines(filename)
                    
                    coverage_data[str(relative_path)] = {
                        "total_lines": len(line_coverage),
                        "covered_lines": len(covered_lines),
                        "missing_lines": len(missing_lines),
                        "coverage_percent": (len(covered_lines) / len(line_coverage)) * 100 if line_coverage else 0
                    }
                except (ValueError, KeyError):
                    continue
            
            # Расчет общего покрытия
            total_lines = sum(f["total_lines"] for f in coverage_data.values())
            total_covered = sum(f["covered_lines"] for f in coverage_data.values())
            total_coverage = (total_covered / total_lines * 100) if total_lines > 0 else 0
            
            results = {
                "pytest_exit_code": pytest_result,
                "coverage_total": total_coverage,
                "coverage_by_file": coverage_data,
                "timestamp": time.time(),
                "success": pytest_result == 0
            }
            
            logger.info(f"Tests completed with exit code: {pytest_result}")
            logger.info(f"Total coverage: {total_coverage:.2f}%")
            
            return results
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return {
                "pytest_exit_code": -1,
                "coverage_total": 0,
                "coverage_by_file": {},
                "timestamp": time.time(),
                "success": False,
                "error": str(e)
            }
    
    async def send_to_deepseek(self, test_results: Dict, changed_files: List[Path]) -> Dict:
        """Отправка результатов тестов в DeepSeek API для анализа"""
        if not self.deepseek_api_key:
            logger.warning("DeepSeek API key not configured, skipping analysis")
            return {"analysis_skipped": True}
        
        logger.info("Sending results to DeepSeek for analysis...")
        
        # Подготовка промпта для анализа
        prompt = self._build_analysis_prompt(test_results, changed_files)
        
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Python developer and QA engineer. Analyze test results and provide actionable insights."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.deepseek_api_url,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data["choices"][0]["message"]["content"]
                    
                    logger.info("DeepSeek analysis completed successfully")
                    
                    return {
                        "analysis": analysis,
                        "model": data.get("model", "unknown"),
                        "usage": data.get("usage", {}),
                        "success": True
                    }
                else:
                    error_text = response.text
                    logger.error(f"DeepSeek API error: {response.status_code} - {error_text}")
                    return {
                        "error": f"API error: {response.status_code}",
                        "response": error_text,
                        "success": False
                    }
                    
        except httpx.TimeoutException:
            logger.error("DeepSeek API request timed out")
            return {
                "error": "Request timeout",
                "success": False
            }
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    def _build_analysis_prompt(self, test_results: Dict, changed_files: List[Path]) -> str:
        """Построение промпта для анализа DeepSeek"""
        changed_files_str = "\n".join([f"- {str(f)}" for f in changed_files])
        
        prompt = f"""
Please analyze these Python test results and provide actionable insights:

TEST EXECUTION:
- Exit Code: {test_results.get('pytest_exit_code')}
- Success: {test_results.get('success')}
- Total Coverage: {test_results.get('coverage_total', 0):.2f}%

CHANGED FILES:
{changed_files_str}

COVERAGE BY FILE:
{json.dumps(test_results.get('coverage_by_file', {}), indent=2)}

Please provide:
1. Test quality assessment
2. Coverage analysis and gaps
3. Potential issues with recent changes
4. Recommendations for improvement
5. Risk assessment

Be concise and focus on actionable insights.
"""
        
        return prompt
    
    async def save_results(self, test_results: Dict, analysis_results: Dict, changed_files: List[Path]):
        """Сохранение результатов в JSON файл"""
        timestamp = int(time.time())
        filename = self.results_dir / f"test_watcher_audit_{timestamp}.json"
        
        results_data = {
            "timestamp": timestamp,
            "changed_files": [str(f) for f in changed_files],
            "test_results": test_results,
            "analysis_results": analysis_results,
            "metadata": {
                "watch_path": str(self.watch_path),
                "debounce_seconds": self.debounce_seconds
            }
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Results saved to: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    async def start(self):
        """Запуск file watcher"""
        # Сохраняем ссылку на текущий event loop
        self.loop = asyncio.get_running_loop()
        
        logger.info(f"Starting TestWatcher on path: {self.watch_path}")
        logger.info(f"Debounce period: {self.debounce_seconds} seconds")
        
        event_handler = self.ChangeHandler(self)
        self.observer.schedule(event_handler, str(self.watch_path), recursive=True)
        self.observer.start()
        
        logger.info("TestWatcher started successfully")
        
        try:
            # Поддержание работы watcher
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down TestWatcher...")
        finally:
            self.observer.stop()
            self.observer.join()
    
    def stop(self):
        """Остановка file watcher"""
        self.observer.stop()
        self.observer.join()
        logger.info("TestWatcher stopped")


async def main():
    """Точка входа"""
    watcher = TestWatcher(
        watch_path=str(project_root),
        debounce_seconds=20
    )
    
    try:
        await watcher.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
