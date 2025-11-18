"""
Sandbox Executor Service для безопасного выполнения сгенерированного кода
Docker-based isolation с resource limits и monitoring
"""

import os
import tempfile
import logging
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import docker
from docker.models.containers import Container
from docker.errors import DockerException, ContainerError, ImageNotFound

from backend.core.code_validator import CodeValidator, ValidationResult, RiskLevel

logger = logging.getLogger(__name__)


class SandboxExecutionResult:
    """Результат выполнения кода в sandbox"""
    
    def __init__(
        self,
        success: bool,
        exit_code: int,
        stdout: str,
        stderr: str,
        execution_time: float,
        resource_usage: Dict[str, Any],
        validation_result: Optional[ValidationResult] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time = execution_time
        self.resource_usage = resource_usage
        self.validation_result = validation_result
        self.error = error
    
    def to_dict(self) -> Dict:
        """Сериализация в dict"""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time,
            "resource_usage": self.resource_usage,
            "validation": self.validation_result.to_dict() if self.validation_result else None,
            "error": self.error
        }


class SandboxExecutor:
    """
    Executor для безопасного запуска кода в Docker sandbox
    
    Features:
        - Pre-execution code validation (AST analysis)
        - Docker container isolation
        - Network isolation (--network=none)
        - Resource limits (CPU, RAM, time)
        - Read-only filesystem
        - Non-root user execution
        - Automatic cleanup
    
    Usage:
        executor = SandboxExecutor()
        result = await executor.execute(
            code="print('Hello from sandbox!')",
            timeout=30
        )
        print(result.stdout)  # "Hello from sandbox!"
    """
    
    # Default configuration
    DEFAULT_IMAGE = "bybit-sandbox:latest"
    DEFAULT_TIMEOUT = 300  # 5 minutes
    DEFAULT_CPU_LIMIT = 2.0  # 2 cores
    DEFAULT_MEM_LIMIT = "4g"  # 4GB
    DEFAULT_MEM_SWAP_LIMIT = "4g"  # No swap
    
    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        timeout: int = DEFAULT_TIMEOUT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        mem_limit: str = DEFAULT_MEM_LIMIT,
        validate_code: bool = True,
        max_risk_score: int = 30
    ):
        """
        Args:
            image: Docker image name
            timeout: Execution timeout (seconds)
            cpu_limit: CPU cores limit
            mem_limit: Memory limit (e.g., "4g", "512m")
            validate_code: Pre-validate code before execution
            max_risk_score: Maximum allowed risk score (default: 30 = LOW risk)
        """
        self.image = image
        self.timeout = timeout
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
        self.mem_swap_limit = mem_limit  # Disable swap
        self.validate_code = validate_code
        self.max_risk_score = max_risk_score
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise RuntimeError(f"Docker not available: {e}")
        
        # Check if image exists
        self._check_image()
    
    def _check_image(self):
        """Check if sandbox image exists"""
        try:
            self.docker_client.images.get(self.image)
            logger.info(f"Sandbox image found: {self.image}")
        except ImageNotFound:
            logger.warning(f"Sandbox image not found: {self.image}")
            logger.info("Building sandbox image...")
            self._build_image()
    
    def _build_image(self):
        """Build sandbox image from Dockerfile"""
        project_root = Path(__file__).parent.parent.parent
        dockerfile_path = project_root / "docker" / "Dockerfile.sandbox"
        
        if not dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")
        
        try:
            logger.info(f"Building image from {dockerfile_path}...")
            image, build_logs = self.docker_client.images.build(
                path=str(project_root),
                dockerfile=str(dockerfile_path),
                tag=self.image,
                rm=True,
                pull=True
            )
            
            for log in build_logs:
                if 'stream' in log:
                    logger.debug(log['stream'].strip())
            
            logger.info(f"Image built successfully: {self.image}")
        except DockerException as e:
            logger.error(f"Failed to build image: {e}")
            raise
    
    async def execute(
        self,
        code: str,
        timeout: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
        working_dir: str = "/workspace"
    ) -> SandboxExecutionResult:
        """
        Execute Python code in isolated sandbox
        
        Args:
            code: Python code to execute
            timeout: Execution timeout (seconds), overrides default
            env_vars: Environment variables to pass to container
            working_dir: Working directory inside container
        
        Returns:
            SandboxExecutionResult with output and metrics
        """
        start_time = time.time()
        validation_result = None
        
        # Step 1: Validate code
        if self.validate_code:
            validator = CodeValidator()
            validation_result = validator.validate(code)
            
            if not validation_result.is_valid:
                logger.warning(f"Code validation failed: {validation_result.violations}")
                return SandboxExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Code validation failed",
                    execution_time=time.time() - start_time,
                    resource_usage={},
                    validation_result=validation_result,
                    error=f"Security validation failed: {validation_result.violations[0]['message']}"
                )
            
            if validation_result.risk_score > self.max_risk_score:
                logger.warning(f"Code risk score too high: {validation_result.risk_score} > {self.max_risk_score}")
                return SandboxExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Risk score too high",
                    execution_time=time.time() - start_time,
                    resource_usage={},
                    validation_result=validation_result,
                    error=f"Risk score {validation_result.risk_score} exceeds maximum {self.max_risk_score}"
                )
            
            logger.info(f"Code validation passed: risk_score={validation_result.risk_score}, level={validation_result.risk_level}")
        
        # Step 2: Create temporary file for code
        with tempfile.TemporaryDirectory() as temp_dir:
            code_file = Path(temp_dir) / "strategy.py"
            code_file.write_text(code, encoding='utf-8')
            
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir(exist_ok=True)
            
            # Step 3: Run container
            try:
                result = await self._run_container(
                    code_path=code_file,
                    output_dir=output_dir,
                    timeout=timeout or self.timeout,
                    env_vars=env_vars
                )
                
                result.validation_result = validation_result
                return result
                
            except Exception as e:
                logger.error(f"Sandbox execution error: {e}")
                return SandboxExecutionResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=str(e),
                    execution_time=time.time() - start_time,
                    resource_usage={},
                    validation_result=validation_result,
                    error=f"Execution error: {str(e)}"
                )
    
    async def _run_container(
        self,
        code_path: Path,
        output_dir: Path,
        timeout: int,
        env_vars: Optional[Dict[str, str]]
    ) -> SandboxExecutionResult:
        """Run Docker container with code"""
        start_time = time.time()
        container = None
        
        try:
            # Prepare volumes
            volumes = {
                str(code_path.parent): {
                    'bind': '/workspace',
                    'mode': 'ro'  # Read-only
                },
                str(output_dir): {
                    'bind': '/output',
                    'mode': 'rw'  # Read-write for output
                }
            }
            
            # Prepare environment
            environment = env_vars or {}
            
            # Create container
            logger.info(f"Creating container from {self.image}...")
            container = self.docker_client.containers.create(
                image=self.image,
                command=f"python /workspace/{code_path.name}",
                volumes=volumes,
                environment=environment,
                network_mode='none',  # No network access
                read_only=True,  # Read-only filesystem
                mem_limit=self.mem_limit,
                memswap_limit=self.mem_swap_limit,
                cpu_period=100000,  # 100ms
                cpu_quota=int(self.cpu_limit * 100000),  # CPU limit
                cap_drop=['ALL'],  # Drop all capabilities
                security_opt=['no-new-privileges'],  # Prevent privilege escalation
                user='sandboxuser',  # Non-root user
                working_dir='/workspace',
                detach=True,
                # remove parameter not supported in create(), we remove manually
            )
            
            logger.info(f"Starting container {container.id[:12]}...")
            container.start()
            
            # Wait for completion with timeout
            try:
                exit_code = container.wait(timeout=timeout)
                
                # Handle different return types (dict or int)
                if isinstance(exit_code, dict):
                    exit_code = exit_code.get('StatusCode', -1)
                
            except Exception as e:
                logger.warning(f"Container timeout or error: {e}")
                container.kill()
                exit_code = -1
            
            execution_time = time.time() - start_time
            
            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
            
            # Get resource usage stats
            stats = container.stats(stream=False)
            resource_usage = self._parse_stats(stats)
            
            # Cleanup container
            container.remove(force=True)
            
            success = exit_code == 0
            
            logger.info(f"Container execution finished: exit_code={exit_code}, time={execution_time:.2f}s")
            
            return SandboxExecutionResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                resource_usage=resource_usage,
                error=None if success else f"Non-zero exit code: {exit_code}"
            )
            
        except ContainerError as e:
            logger.error(f"Container error: {e}")
            return SandboxExecutionResult(
                success=False,
                exit_code=e.exit_status,
                stdout="",
                stderr=str(e),
                execution_time=time.time() - start_time,
                resource_usage={},
                error=f"Container error: {str(e)}"
            )
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
            
            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=time.time() - start_time,
                resource_usage={},
                error=f"Execution failed: {str(e)}"
            )
    
    def _parse_stats(self, stats: Dict) -> Dict[str, Any]:
        """Parse Docker container stats"""
        try:
            # Memory usage
            mem_usage = stats.get('memory_stats', {}).get('usage', 0)
            mem_limit = stats.get('memory_stats', {}).get('limit', 0)
            mem_percent = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0
            
            # CPU usage (more complex calculation)
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            
            cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - \
                        precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - \
                           precpu_stats.get('system_cpu_usage', 0)
            
            num_cpus = cpu_stats.get('online_cpus', 1)
            cpu_percent = (cpu_delta / system_delta * num_cpus * 100.0) if system_delta > 0 else 0
            
            return {
                "memory_usage_bytes": mem_usage,
                "memory_limit_bytes": mem_limit,
                "memory_usage_mb": mem_usage / (1024 * 1024),
                "memory_percent": round(mem_percent, 2),
                "cpu_percent": round(cpu_percent, 2),
                "num_cpus": num_cpus
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse stats: {e}")
            return {}
    
    def cleanup(self):
        """Cleanup Docker client"""
        try:
            self.docker_client.close()
            logger.info("Docker client closed")
        except Exception as e:
            logger.error(f"Error closing Docker client: {e}")


# =============================================================================
# Convenience Functions
# =============================================================================

async def execute_code_in_sandbox(
    code: str,
    timeout: int = 300,
    validate: bool = True
) -> SandboxExecutionResult:
    """
    Quick function to execute code in sandbox
    
    Args:
        code: Python code to execute
        timeout: Execution timeout (seconds)
        validate: Pre-validate code
    
    Returns:
        SandboxExecutionResult
    """
    executor = SandboxExecutor(validate_code=validate)
    try:
        result = await executor.execute(code, timeout=timeout)
        return result
    finally:
        executor.cleanup()
