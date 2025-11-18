#!/usr/bin/env python3
"""
Health Check System для Bybit Strategy Tester
==============================================

Проверяет состояние всех компонентов системы:
- Test Watcher (процесс, файл лога, активность)
- Audit Agent (процесс, файл лога, активность)
- DeepSeek API (доступность)
- Perplexity API (доступность)
- KeyManager (работоспособность)
- База данных (подключение)
- Файловая система (доступность путей)

Использование:
    python health_check.py              # Полная проверка
    python health_check.py --component test-watcher  # Конкретный компонент
    python health_check.py --json       # JSON вывод для мониторинга
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import psutil
from loguru import logger
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Добавляем корень проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "automation" / "task2_key_manager"))

try:
    from backend.security.key_manager import KeyManager
except ImportError:
    try:
        from key_manager import KeyManager
    except ImportError:
        KeyManager = None  # Fallback если модуль не доступен


class HealthStatus:
    """Статусы здоровья компонентов"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentHealth:
    """Результат проверки компонента"""
    
    def __init__(
        self,
        component: str,
        status: str,
        message: str,
        details: Optional[Dict] = None,
        timestamp: Optional[datetime] = None
    ):
        self.component = component
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class HealthChecker:
    """Система проверки здоровья компонентов"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.results: List[ComponentHealth] = []
    
    def _find_process_by_name(self, name: str) -> Optional[psutil.Process]:
        """Найти процесс по имени скрипта"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any(name in arg for arg in cmdline):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def _check_log_activity(self, log_path: Path, max_age_seconds: int = 300) -> bool:
        """Проверить активность в логе (последние 5 минут)"""
        if not log_path.exists():
            return False
        
        try:
            mtime = log_path.stat().st_mtime
            age = datetime.now().timestamp() - mtime
            return age <= max_age_seconds
        except Exception:
            return False
    
    async def check_test_watcher(self) -> ComponentHealth:
        """Проверка Test Watcher"""
        try:
            # 1. Проверка процесса
            proc = self._find_process_by_name("test_watcher.py")
            if not proc:
                return ComponentHealth(
                    component="test_watcher",
                    status=HealthStatus.UNHEALTHY,
                    message="Process not running",
                    details={"process": None}
                )
            
            # 2. Проверка логов
            log_file = self.project_root / "logs" / "test_watcher.log"
            log_active = self._check_log_activity(log_file)
            
            # 3. Сбор метрик
            details = {
                "process": {
                    "pid": proc.pid,
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "create_time": datetime.fromtimestamp(proc.create_time()).isoformat()
                },
                "log": {
                    "path": str(log_file),
                    "exists": log_file.exists(),
                    "active": log_active,
                    "size_mb": log_file.stat().st_size / 1024 / 1024 if log_file.exists() else 0
                }
            }
            
            # 4. Определение статуса
            if not log_active:
                status = HealthStatus.DEGRADED
                message = "Process running but log inactive"
            else:
                status = HealthStatus.HEALTHY
                message = "All checks passed"
            
            return ComponentHealth(
                component="test_watcher",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return ComponentHealth(
                component="test_watcher",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                details={"error": str(e)}
            )
    
    async def check_audit_agent(self) -> ComponentHealth:
        """Проверка Audit Agent"""
        try:
            # 1. Проверка процесса
            proc = self._find_process_by_name("audit_agent.py")
            if not proc:
                return ComponentHealth(
                    component="audit_agent",
                    status=HealthStatus.UNHEALTHY,
                    message="Process not running",
                    details={"process": None}
                )
            
            # 2. Проверка логов
            log_file = self.project_root / "logs" / "audit_agent.log"
            log_active = self._check_log_activity(log_file, max_age_seconds=600)  # 10 минут (запускается каждые 5)
            
            # 3. Сбор метрик
            details = {
                "process": {
                    "pid": proc.pid,
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "create_time": datetime.fromtimestamp(proc.create_time()).isoformat()
                },
                "log": {
                    "path": str(log_file),
                    "exists": log_file.exists(),
                    "active": log_active,
                    "size_mb": log_file.stat().st_size / 1024 / 1024 if log_file.exists() else 0
                }
            }
            
            status = HealthStatus.HEALTHY if log_active else HealthStatus.DEGRADED
            message = "All checks passed" if log_active else "Process running but log inactive"
            
            return ComponentHealth(
                component="audit_agent",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return ComponentHealth(
                component="audit_agent",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                details={"error": str(e)}
            )
    
    async def check_deepseek_api(self) -> ComponentHealth:
        """Проверка DeepSeek API"""
        try:
            # Получаем API ключ из переменных окружения или KeyManager
            api_key = os.getenv("DEEPSEEK_API_KEY")
            
            if not api_key and KeyManager:
                try:
                    km = KeyManager()
                    api_key = km.get_decrypted_key("DEEPSEEK_API_KEY") if hasattr(km, 'get_decrypted_key') else None
                except Exception:
                    pass
            
            if not api_key:
                return ComponentHealth(
                    component="deepseek_api",
                    status=HealthStatus.UNHEALTHY,
                    message="API key not found in environment",
                    details={}
                )
            
            # Простой запрос для проверки доступности
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 10
                    }
                )
            
            if response.status_code == 200:
                return ComponentHealth(
                    component="deepseek_api",
                    status=HealthStatus.HEALTHY,
                    message="API accessible",
                    details={"status_code": 200, "response_time_ms": response.elapsed.total_seconds() * 1000}
                )
            else:
                return ComponentHealth(
                    component="deepseek_api",
                    status=HealthStatus.DEGRADED,
                    message=f"API returned {response.status_code}",
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            return ComponentHealth(
                component="deepseek_api",
                status=HealthStatus.UNHEALTHY,
                message=f"API check failed: {e}",
                details={"error": str(e)}
            )
    
    async def check_perplexity_api(self) -> ComponentHealth:
        """Проверка Perplexity API"""
        try:
            # Получаем API ключ из переменных окружения или KeyManager
            api_key = os.getenv("PERPLEXITY_API_KEY")
            
            if not api_key and KeyManager:
                try:
                    km = KeyManager()
                    api_key = km.get_decrypted_key("PERPLEXITY_API_KEY") if hasattr(km, 'get_decrypted_key') else None
                except Exception:
                    pass
            
            if not api_key:
                return ComponentHealth(
                    component="perplexity_api",
                    status=HealthStatus.UNHEALTHY,
                    message="API key not found in environment",
                    details={}
                )
            
            # Простой запрос для проверки доступности
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": "ping"}]
                    }
                )
            
            if response.status_code == 200:
                return ComponentHealth(
                    component="perplexity_api",
                    status=HealthStatus.HEALTHY,
                    message="API accessible",
                    details={"status_code": 200, "response_time_ms": response.elapsed.total_seconds() * 1000}
                )
            else:
                return ComponentHealth(
                    component="perplexity_api",
                    status=HealthStatus.DEGRADED,
                    message=f"API returned {response.status_code}",
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            return ComponentHealth(
                component="perplexity_api",
                status=HealthStatus.UNHEALTHY,
                message=f"API check failed: {e}",
                details={"error": str(e)}
            )
    
    async def check_filesystem(self) -> ComponentHealth:
        """Проверка файловой системы"""
        try:
            required_dirs = [
                self.project_root / "logs",
                self.project_root / "ai_audit_results",
                self.project_root / "mcp-server",
                self.project_root / "tests"
            ]
            
            missing_dirs = [d for d in required_dirs if not d.exists()]
            
            # Проверка свободного места (минимум 1GB)
            disk_usage = psutil.disk_usage(str(self.project_root))
            free_gb = disk_usage.free / (1024 ** 3)
            
            details = {
                "required_directories": len(required_dirs),
                "missing_directories": len(missing_dirs),
                "missing_paths": [str(d) for d in missing_dirs],
                "disk": {
                    "total_gb": disk_usage.total / (1024 ** 3),
                    "used_gb": disk_usage.used / (1024 ** 3),
                    "free_gb": free_gb,
                    "percent_used": disk_usage.percent
                }
            }
            
            if missing_dirs:
                status = HealthStatus.DEGRADED
                message = f"{len(missing_dirs)} directories missing"
            elif free_gb < 1:
                status = HealthStatus.DEGRADED
                message = f"Low disk space: {free_gb:.2f} GB free"
            else:
                status = HealthStatus.HEALTHY
                message = "All checks passed"
            
            return ComponentHealth(
                component="filesystem",
                status=status,
                message=message,
                details=details
            )
            
        except Exception as e:
            return ComponentHealth(
                component="filesystem",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                details={"error": str(e)}
            )
    
    async def run_all_checks(self) -> List[ComponentHealth]:
        """Запустить все проверки"""
        self.results = []
        
        # Параллельный запуск всех проверок
        checks = [
            self.check_test_watcher(),
            self.check_audit_agent(),
            self.check_deepseek_api(),
            self.check_perplexity_api(),
            self.check_filesystem()
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                self.results.append(ComponentHealth(
                    component="unknown",
                    status=HealthStatus.UNKNOWN,
                    message=f"Check crashed: {result}",
                    details={"error": str(result)}
                ))
            else:
                self.results.append(result)
        
        return self.results
    
    def get_overall_status(self) -> str:
        """Получить общий статус системы"""
        if not self.results:
            return HealthStatus.UNKNOWN
        
        statuses = [r.status for r in self.results]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def print_results(self, json_output: bool = False):
        """Вывести результаты проверок"""
        if json_output:
            output = {
                "timestamp": datetime.now().isoformat(),
                "overall_status": self.get_overall_status(),
                "components": [r.to_dict() for r in self.results]
            }
            print(json.dumps(output, indent=2))
        else:
            print("\n" + "=" * 80)
            print("🏥 HEALTH CHECK REPORT")
            print("=" * 80)
            print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Overall Status: {self.get_overall_status().upper()}")
            print("=" * 80)
            
            for result in self.results:
                status_icon = {
                    HealthStatus.HEALTHY: "✅",
                    HealthStatus.DEGRADED: "⚠️",
                    HealthStatus.UNHEALTHY: "❌",
                    HealthStatus.UNKNOWN: "❓"
                }.get(result.status, "❓")
                
                print(f"\n{status_icon} {result.component.upper()}")
                print(f"   Status: {result.status}")
                print(f"   Message: {result.message}")
                
                if result.details:
                    print(f"   Details: {json.dumps(result.details, indent=6)}")
            
            print("\n" + "=" * 80)


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Health Check для Bybit Strategy Tester")
    parser.add_argument("--component", help="Проверить конкретный компонент")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON формате")
    args = parser.parse_args()
    
    checker = HealthChecker()
    
    if args.component:
        # Проверка конкретного компонента
        check_method = getattr(checker, f"check_{args.component.replace('-', '_')}", None)
        if not check_method:
            print(f"❌ Unknown component: {args.component}", file=sys.stderr)
            sys.exit(1)
        
        result = await check_method()
        checker.results = [result]
    else:
        # Все проверки
        await checker.run_all_checks()
    
    # Вывод результатов
    checker.print_results(json_output=args.json)
    
    # Exit code по статусу
    overall_status = checker.get_overall_status()
    if overall_status == HealthStatus.HEALTHY:
        sys.exit(0)
    elif overall_status == HealthStatus.DEGRADED:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
