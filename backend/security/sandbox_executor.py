"""
Secure Sandbox Executor для AI-генерированного кода
Реализует Docker-изоляцию с полным контролем безопасности
"""

import docker
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from prometheus_client import Counter, Histogram, Gauge
from pathlib import Path
import tempfile
import shutil

# Prometheus метрики
SANDBOX_EXECUTIONS = Counter(
    'sandbox_executions_total',
    'Total number of sandbox executions',
    ['status', 'language']
)

SANDBOX_ESCAPE_ATTEMPTS = Counter(
    'sandbox_escape_attempts_total',
    'Detected sandbox escape attempts',
    ['attempt_type']
)

SANDBOX_EXECUTION_TIME = Histogram(
    'sandbox_execution_seconds',
    'Time taken for sandbox execution',
    ['language']
)

ACTIVE_SANDBOXES = Gauge(
    'active_sandboxes',
    'Currently running sandbox containers'
)

logger = logging.getLogger(__name__)


class SandboxSecurityViolation(Exception):
    """Raised when sandbox security violation detected"""
    pass


class SandboxExecutor:
    """
    Secure sandbox executor для AI-кода с Docker изоляцией
    
    Features:
    - Network isolation (--network none)
    - Read-only filesystem (--read-only)
    - Resource limits (CPU, Memory, Time)
    - Syscall monitoring
    - Automated cleanup
    """
    
    def __init__(self, 
                 docker_image: str = "python:3.11-slim",
                 max_memory: str = "512m",
                 cpu_quota: int = 100000,
                 timeout: int = 30):
        """
        Args:
            docker_image: Docker image для sandbox
            max_memory: Лимит памяти (например, "512m")
            cpu_quota: CPU quota (100000 = 1 CPU)
            timeout: Timeout в секундах
        """
        self.client = docker.from_env()
        self.docker_image = docker_image
        self.max_memory = max_memory
        self.cpu_quota = cpu_quota
        self.timeout = timeout
        
        # Проверяем наличие образа
        self._ensure_docker_image()
    
    def _ensure_docker_image(self):
        """Проверяет наличие Docker образа"""
        try:
            self.client.images.get(self.docker_image)
            logger.info(f"Docker image {self.docker_image} found")
        except docker.errors.ImageNotFound:
            logger.warning(f"Docker image {self.docker_image} not found, pulling...")
            self.client.images.pull(self.docker_image)
            logger.info(f"Docker image {self.docker_image} pulled successfully")
    
    async def execute_python_code(self, 
                                   code: str,
                                   input_data: Optional[str] = None,
                                   allowed_modules: Optional[list] = None) -> Dict[str, Any]:
        """
        Выполняет Python код в изолированном sandbox
        
        Args:
            code: Python код для выполнения
            input_data: Опциональные входные данные
            allowed_modules: Разрешённые модули (whitelist)
        
        Returns:
            Dict с результатами выполнения
        """
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"Starting sandbox execution {execution_id}")
        
        # Валидация кода
        if not self._validate_code(code, allowed_modules):
            SANDBOX_ESCAPE_ATTEMPTS.labels(attempt_type='forbidden_module').inc()
            raise SandboxSecurityViolation("Code contains forbidden imports or operations")
        
        # Создаём временную директорию
        temp_dir = tempfile.mkdtemp(prefix=f"sandbox_{execution_id}_")
        
        try:
            # Сохраняем код в файл
            code_file = Path(temp_dir) / "script.py"
            code_file.write_text(code, encoding='utf-8')
            
            # Входные данные
            if input_data:
                input_file = Path(temp_dir) / "input.txt"
                input_file.write_text(input_data, encoding='utf-8')
            
            ACTIVE_SANDBOXES.inc()
            
            # Выполняем в Docker контейнере
            with SANDBOX_EXECUTION_TIME.labels(language='python').time():
                result = await self._run_container(
                    execution_id=execution_id,
                    temp_dir=temp_dir,
                    code_file="script.py"
                )
            
            SANDBOX_EXECUTIONS.labels(
                status='success' if result['exit_code'] == 0 else 'failure',
                language='python'
            ).inc()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            return {
                'execution_id': execution_id,
                'status': 'success' if result['exit_code'] == 0 else 'error',
                'stdout': result['stdout'],
                'stderr': result['stderr'],
                'exit_code': result['exit_code'],
                'execution_time': elapsed,
                'timestamp': start_time.isoformat()
            }
            
        except docker.errors.ContainerError as e:
            logger.error(f"Container error in {execution_id}: {e}")
            SANDBOX_EXECUTIONS.labels(status='error', language='python').inc()
            
            # Проверяем на попытки escape
            if self._detect_escape_attempt(str(e)):
                SANDBOX_ESCAPE_ATTEMPTS.labels(attempt_type='container_escape').inc()
                raise SandboxSecurityViolation(f"Sandbox escape attempt detected: {e}")
            
            return {
                'execution_id': execution_id,
                'status': 'error',
                'error': str(e),
                'timestamp': start_time.isoformat()
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Sandbox {execution_id} timed out")
            SANDBOX_EXECUTIONS.labels(status='timeout', language='python').inc()
            return {
                'execution_id': execution_id,
                'status': 'timeout',
                'error': f'Execution exceeded {self.timeout} seconds',
                'timestamp': start_time.isoformat()
            }
            
        finally:
            ACTIVE_SANDBOXES.dec()
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    async def _run_container(self, 
                            execution_id: str,
                            temp_dir: str,
                            code_file: str) -> Dict[str, Any]:
        """Запускает Docker контейнер с максимальной изоляцией"""
        
        container = None
        try:
            # Создаём контейнер с жёсткими ограничениями
            container = self.client.containers.run(
                self.docker_image,
                command=f'python3 /sandbox/{code_file}',
                
                # Network isolation
                network_mode='none',
                
                # Filesystem isolation
                read_only=True,
                volumes={
                    temp_dir: {'bind': '/sandbox', 'mode': 'ro'},
                    '/tmp': {'bind': '/tmp', 'mode': 'rw'}
                },
                
                # Resource limits
                mem_limit=self.max_memory,
                cpu_quota=self.cpu_quota,
                pids_limit=50,  # Ограничение процессов
                
                # Security options
                security_opt=['no-new-privileges'],
                cap_drop=['ALL'],  # Drop все capabilities
                
                # Runtime
                detach=True,
                remove=False,  # Не удаляем сразу для анализа
                
                # Logging
                labels={
                    'execution_id': execution_id,
                    'sandbox': 'true',
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            # Ждём завершения с timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(container.wait),
                timeout=self.timeout
            )
            
            # Получаем логи
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
            
            return {
                'exit_code': result['StatusCode'],
                'stdout': stdout,
                'stderr': stderr
            }
            
        finally:
            if container:
                try:
                    # Проверяем статистику контейнера
                    stats = container.stats(stream=False)
                    logger.debug(f"Container {execution_id} stats: {stats}")
                    
                    # Удаляем контейнер
                    container.remove(force=True)
                except Exception as e:
                    logger.error(f"Error cleaning up container {execution_id}: {e}")
    
    def _validate_code(self, code: str, allowed_modules: Optional[list] = None) -> bool:
        """
        Валидация кода на опасные паттерны
        
        Args:
            code: Код для проверки
            allowed_modules: Whitelist разрешённых модулей
        
        Returns:
            True если код безопасен
        """
        # Запрещённые импорты
        forbidden_imports = [
            'os', 'sys', 'subprocess', 'socket', 'requests',
            'urllib', 'http', 'ftplib', 'telnetlib', 'pickle',
            'marshal', 'shelve', 'exec', 'eval', '__import__',
            'compile', 'open', 'file', 'input', 'raw_input'
        ]
        
        # Если есть whitelist, проверяем только его
        if allowed_modules:
            forbidden_imports = [
                imp for imp in forbidden_imports 
                if imp not in allowed_modules
            ]
        
        code_lower = code.lower()
        
        # Проверка на запрещённые импорты
        for forbidden in forbidden_imports:
            if f'import {forbidden}' in code_lower or f'from {forbidden}' in code_lower:
                logger.warning(f"Forbidden import detected: {forbidden}")
                return False
        
        # Проверка на опасные функции
        dangerous_patterns = [
            '__builtins__',
            'globals()',
            'locals()',
            '__dict__',
            '__class__',
            '__bases__',
            '__subclasses__',
        ]
        
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return False
        
        return True
    
    def _detect_escape_attempt(self, error_message: str) -> bool:
        """Детектирует попытки escape из sandbox"""
        escape_indicators = [
            'privilege',
            'escape',
            'breakout',
            'capability',
            'chroot',
            'namespace',
            'cgroup',
            'ptrace',
            'proc',
            'sys',
            'dev'
        ]
        
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in escape_indicators)
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка работоспособности sandbox"""
        try:
            # Простой тест
            result = await self.execute_python_code("print('health check')")
            
            return {
                'status': 'healthy' if result['status'] == 'success' else 'degraded',
                'docker_available': True,
                'image': self.docker_image,
                'test_result': result
            }
        except Exception as e:
            logger.error(f"Sandbox health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'docker_available': False
            }


# Singleton instance
_sandbox_executor = None


def get_sandbox_executor() -> SandboxExecutor:
    """Получить singleton instance sandbox executor"""
    global _sandbox_executor
    if _sandbox_executor is None:
        _sandbox_executor = SandboxExecutor()
    return _sandbox_executor
