#!/usr/bin/env python3
"""
Фоновый аудит-агент для автоматического мониторинга проекта
Автоматически запускает аудит при достижении milestone
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Добавляем путь к config
sys.path.insert(0, str(Path(__file__).parent))
from config import AuditConfig

# Добавляем SafeAsyncBridge для thread-safe async операций
sys.path.insert(0, str(Path(__file__).parent.parent))
from safe_async_bridge import SafeAsyncBridge


class AuditHistory:
    """Управление историей запусков аудита"""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load_history(self) -> List[Dict[str, Any]]:
        """Загрузка истории запусков"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logging.warning(f"Не удалось загрузить историю: {e}")
        return []
    
    def save_history(self, history: List[Dict[str, Any]]):
        """Сохранение истории запусков"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Не удалось сохранить историю: {e}")
    
    def add_audit_record(self, trigger_reason: str, status: str, details: str = ""):
        """Добавление записи об аудите"""
        history = self.load_history()
        record = {
            "timestamp": datetime.now().isoformat(),
            "trigger_reason": trigger_reason,
            "status": status,
            "details": details
        }
        history.append(record)
        
        # Сохраняем только последние 100 записей
        if len(history) > 100:
            history = history[-100:]
        
        self.save_history(history)
        logging.info(f"Добавлена запись в историю: {trigger_reason} - {status}")


class MarkerFileHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы для маркеров"""
    
    def __init__(self, agent):
        self.agent = agent
        self.processed_files = set()
    
    def on_created(self, event):
        """Обработка создания файлов"""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if self._is_marker_file(file_path) and str(file_path) not in self.processed_files:
                self.processed_files.add(str(file_path))
                if self.agent.loop:
                    # Week 2 upgrade: SafeAsyncBridge вместо run_coroutine_threadsafe
                    # Используем future для безопасного вызова из sync контекста
                    future = asyncio.run_coroutine_threadsafe(
                        self.agent.async_bridge.call_async(
                            self.agent.handle_marker_creation(file_path)
                        ),
                        self.agent.loop
                    )
    
    def on_modified(self, event):
        """Обработка изменения файлов"""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if self._is_marker_file(file_path) and str(file_path) not in self.processed_files:
                self.processed_files.add(str(file_path))
                if self.agent.loop:
                    # Week 2 upgrade: SafeAsyncBridge вместо run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(
                        self.agent.async_bridge.call_async(
                            self.agent.handle_marker_creation(file_path)
                        ),
                        self.agent.loop
                    )
    
    def _is_marker_file(self, file_path: Path) -> bool:
        """Проверка, является ли файл маркером"""
        patterns = [
            r'.*_COMPLETE\.md$',
            r'.*_COMPLETION_REPORT\.md$',
            r'PHASE_.*\.md$',
            r'MILESTONE_.*\.md$',
            r'TASK.*_COMPLETION_REPORT\.md$'
        ]
        filename = file_path.name
        return any(re.match(pattern, filename) for pattern in patterns)


class GitMonitor:
    """Мониторинг Git коммитов"""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.last_checked_commit = self._get_latest_commit_hash()
    
    def _run_git_command(self, command: List[str]) -> Optional[str]:
        """Выполнение Git команды"""
        try:
            result = subprocess.run(
                ['git'] + command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def _get_latest_commit_hash(self) -> Optional[str]:
        """Получение хеша последнего коммита"""
        return self._run_git_command(['log', '-1', '--format=%H'])
    
    def _get_commit_message(self, commit_hash: str) -> Optional[str]:
        """Получение сообщения коммита"""
        return self._run_git_command(['log', '-1', '--format=%B', commit_hash])
    
    def check_milestone_commits(self) -> List[str]:
        """Проверка коммитов с milestone тегами"""
        new_commits = []
        
        current_commit = self._get_latest_commit_hash()
        if not current_commit or current_commit == self.last_checked_commit:
            return new_commits
        
        # Получаем историю коммитов с момента последней проверки
        try:
            if self.last_checked_commit:
                log_range = f"{self.last_checked_commit}..HEAD"
            else:
                log_range = "HEAD"
            
            result = subprocess.run(
                ['git', 'log', '--oneline', log_range],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    commit_hash = line.split()[0]
                    commit_message = self._get_commit_message(commit_hash)
                    if commit_message and self._is_milestone_commit(commit_message):
                        new_commits.append(f"Git commit: {commit_message}")
            
            self.last_checked_commit = current_commit
            
        except (subprocess.CalledProcessError, Exception) as e:
            logging.error(f"Ошибка при проверке Git коммитов: {e}")
        
        return new_commits
    
    def _is_milestone_commit(self, message: str) -> bool:
        """Проверка, является ли коммит milestone"""
        milestone_patterns = [
            r'\[MILESTONE\]',
            r'\[CHECKPOINT\]',
            r'milestone',
            r'checkpoint',
            r'release',
            r'version'
        ]
        message_lower = message.lower()
        return any(pattern.lower() in message_lower for pattern in milestone_patterns)


class CoverageChecker:
    """Проверка coverage тестов"""
    
    def __init__(self, coverage_threshold: float = 80.0):
        self.coverage_threshold = coverage_threshold
    
    async def check_test_coverage(self) -> Optional[float]:
        """Проверка coverage тестов"""
        try:
            # Попытка получить coverage из coverage.py
            coverage_result = await self._get_coverage_from_tool()
            if coverage_result is not None:
                return coverage_result
            
            # Альтернативный метод: поиск файлов coverage
            coverage_result = await self._find_coverage_files()
            if coverage_result is not None:
                return coverage_result
            
        except Exception as e:
            logging.error(f"Ошибка при проверке coverage: {e}")
        
        return None
    
    async def _get_coverage_from_tool(self) -> Optional[float]:
        """Получение coverage из инструмента coverage.py"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'coverage', 'report', '--format=total'],
                capture_output=True,
                text=True,
                check=True
            )
            coverage_percent = float(result.stdout.strip())
            return coverage_percent
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            return None
    
    async def _find_coverage_files(self) -> Optional[float]:
        """Поиск файлов coverage в проекте"""
        coverage_files = list(Path('.').glob('**/coverage.xml'))
        coverage_files.extend(list(Path('.').glob('**/.coverage')))
        coverage_files.extend(list(Path('.').glob('**/coverage.json')))
        
        for coverage_file in coverage_files:
            if coverage_file.suffix == '.xml':
                coverage = await self._parse_coverage_xml(coverage_file)
            elif coverage_file.name == '.coverage':
                coverage = await self._parse_coverage_data(coverage_file)
            elif coverage_file.suffix == '.json':
                coverage = await self._parse_coverage_json(coverage_file)
            else:
                continue
            
            if coverage is not None:
                return coverage
        
        return None
    
    async def _parse_coverage_xml(self, file_path: Path) -> Optional[float]:
        """Парсинг XML файла coverage"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Попытка найти coverage в разных форматах
            for elem in root.iter():
                if 'line-rate' in elem.attrib:
                    return float(elem.attrib['line-rate']) * 100
                elif 'coverage' in elem.attrib:
                    return float(elem.attrib['coverage'])
            
        except Exception:
            pass
        
        return None
    
    async def _parse_coverage_data(self, file_path: Path) -> Optional[float]:
        """Парсинг бинарного файла coverage"""
        return None  # Сложно парсить без coverage.py
    
    async def _parse_coverage_json(self, file_path: Path) -> Optional[float]:
        """Парсинг JSON файла coverage"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Поиск coverage в различных структурах JSON
            if 'totals' in data and 'percent_covered' in data['totals']:
                return data['totals']['percent_covered']
            elif 'coverage' in data and isinstance(data['coverage'], (int, float)):
                return float(data['coverage'])
            
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        
        return None


class AuditAgent:
    """Основной класс аудит-агента"""
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.history = AuditHistory(config.history_file)
        self.git_monitor = GitMonitor(config.project_root)
        self.coverage_checker = CoverageChecker(config.coverage_threshold)
        self.scheduler = AsyncIOScheduler()
        self.observer = Observer()
        self.is_running = False
        self.loop = None  # Event loop будет установлен в start()
        
        # SafeAsyncBridge для thread-safe async операций (Week 2 upgrade)
        self.async_bridge = SafeAsyncBridge()
        
        # Настройка логирования
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('AuditAgent')
    
    async def check_completion_markers(self) -> List[str]:
        """Проверка файлов маркеров завершения"""
        markers_found = []
        
        try:
            for pattern in self.config.marker_patterns:
                for file_path in self.config.project_root.glob(f"**/{pattern}"):
                    if file_path.is_file():
                        markers_found.append(f"Marker file: {file_path.name}")
                        self.logger.info(f"Найден маркер: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при поиске маркеров: {e}")
        
        return markers_found
    
    async def handle_marker_creation(self, file_path: Path):
        """Обработка создания маркера"""
        self.logger.info(f"Обнаружен новый маркер: {file_path}")
        await self.run_full_audit(f"Marker created: {file_path.name}")
    
    async def check_test_coverage_trigger(self) -> bool:
        """Проверка триггера coverage тестов"""
        coverage = await self.coverage_checker.check_test_coverage()
        if coverage is not None and coverage >= self.config.coverage_threshold:
            self.logger.info(f"Coverage достиг порога: {coverage}%")
            return True
        return False
    
    async def check_git_triggers(self) -> List[str]:
        """Проверка Git триггеров"""
        return self.git_monitor.check_milestone_commits()
    
    async def run_full_audit(self, trigger_reason: str):
        """Запуск полного аудита"""
        self.logger.info(f"Запуск аудита по причине: {trigger_reason}")
        
        try:
            # Проверяем существование скрипта аудита
            if not self.config.audit_script.exists():
                self.logger.error(f"Скрипт аудита не найден: {self.config.audit_script}")
                self.history.add_audit_record(
                    trigger_reason, 
                    "FAILED", 
                    f"Audit script not found: {self.config.audit_script}"
                )
                return
            
            # Запускаем скрипт аудита
            start_time = time.time()
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(self.config.audit_script),
                cwd=self.config.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            execution_time = time.time() - start_time
            
            if process.returncode == 0:
                status = "SUCCESS"
                details = f"Audit completed in {execution_time:.2f}s"
                self.logger.info(f"Аудит успешно завершен за {execution_time:.2f}с")
            else:
                status = "FAILED"
                details = f"Error: {stderr.decode() if stderr else 'Unknown error'}"
                self.logger.error(f"Аудит завершился с ошибкой: {details}")
            
            self.history.add_audit_record(trigger_reason, status, details)
            
        except Exception as e:
            error_msg = f"Ошибка при запуске аудита: {e}"
            self.logger.error(error_msg)
            self.history.add_audit_record(trigger_reason, "FAILED", error_msg)
    
    async def periodic_check(self):
        """Периодическая проверка всех триггеров"""
        self.logger.debug("Выполнение периодической проверки")
        
        try:
            # Проверка маркеров завершения
            markers = await self.check_completion_markers()
            for marker in markers:
                await self.run_full_audit(marker)
            
            # Проверка coverage
            if await self.check_test_coverage_trigger():
                await self.run_full_audit("Test coverage threshold reached")
            
            # Проверка Git коммитов
            git_triggers = await self.check_git_triggers()
            for trigger in git_triggers:
                await self.run_full_audit(trigger)
                
        except Exception as e:
            self.logger.error(f"Ошибка при периодической проверке: {e}")
    
    def start_file_monitoring(self):
        """Запуск мониторинга файловой системы"""
        event_handler = MarkerFileHandler(self)
        self.observer.schedule(
            event_handler, 
            str(self.config.project_root), 
            recursive=True
        )
        self.observer.start()
        self.logger.info("Мониторинг файловой системы запущен")
    
    def stop_file_monitoring(self):
        """Остановка мониторинга файловой системы"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.logger.info("Мониторинг файловой системы остановлен")
    
    async def start(self):
        """Запуск агента"""
        if self.is_running:
            self.logger.warning("Агент уже запущен")
            return
        
        # Сохраняем ссылку на текущий event loop
        self.loop = asyncio.get_running_loop()
        
        # Week 2 upgrade: Инициализируем SafeAsyncBridge с текущим loop
        self.async_bridge.set_loop(self.loop)
        self.logger.info("SafeAsyncBridge инициализирован")
        
        self.is_running = True
        self.logger.info("Запуск аудит-агента")
        
        try:
            # Запуск мониторинга файлов
            self.start_file_monitoring()
            
            # Настройка периодической проверки
            self.scheduler.add_job(
                self.periodic_check,
                IntervalTrigger(minutes=self.config.check_interval),
                id='periodic_check'
            )
            
            # Запуск планировщика
            self.scheduler.start()
            self.logger.info(f"Планировщик запущен с интервалом {self.config.check_interval} минут")
            
            # Бесконечный цикл
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Критическая ошибка в агенте: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка агента"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info("Остановка аудит-агента")
        
        # Остановка планировщика
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        # Остановка мониторинга файлов
        self.stop_file_monitoring()
        
        # Week 2 upgrade: Graceful cleanup SafeAsyncBridge
        try:
            await self.async_bridge.cleanup(force=False)
            self.logger.info("SafeAsyncBridge cleanup completed")
        except Exception as e:
            self.logger.error(f"Ошибка при cleanup SafeAsyncBridge: {e}")
        
        self.logger.info("Агент остановлен")


async def main():
    """Основная функция"""
    config = AuditConfig()
    agent = AuditAgent(config)
    
    # Обработка graceful shutdown
    def signal_handler():
        print("\nПолучен сигнал остановки...")
        asyncio.create_task(agent.stop())
    
    try:
        # Регистрация обработчиков сигналов
        if sys.platform != 'win32':
            import signal
            signal.signal(signal.SIGINT, lambda s, f: signal_handler())
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
        else:
            # Для Windows используем альтернативный подход
            pass
        
        await agent.start()
    except KeyboardInterrupt:
        await agent.stop()
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}")
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
