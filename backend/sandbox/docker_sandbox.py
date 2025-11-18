"""
Docker Sandbox - Isolated execution environment for AI-generated code
Uses Docker-in-Docker with network isolation and resource limits
"""

import os
import uuid
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import docker
from docker.errors import DockerException
import logging

logger = logging.getLogger('sandbox.docker')


class DockerSandbox:
    """
    Docker-based sandbox for secure code execution.
    
    Features:
    - Network isolation (no internet access)
    - Read-only filesystem (except /tmp)
    - CPU/Memory/Time limits
    - Syscall auditing
    - Automatic cleanup
    """
    
    def __init__(
        self,
        image: str = "python:3.11-slim",
        cpu_limit: float = 1.0,  # CPU cores
        memory_limit: str = "512m",  # Memory limit
        timeout: int = 30,  # Execution timeout (seconds)
        network_disabled: bool = True
    ):
        """
        Initialize Docker sandbox.
        
        Args:
            image: Docker image to use
            cpu_limit: CPU cores limit
            memory_limit: Memory limit (e.g., "512m", "1g")
            timeout: Execution timeout in seconds
            network_disabled: Disable network access
        """
        self.image = image
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.timeout = timeout
        self.network_disabled = network_disabled
        
        try:
            self.client = docker.from_env()
            # Verify Docker is available
            self.client.ping()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise RuntimeError(f"Docker not available: {e}")
    
    async def execute_code(
        self,
        code: str,
        language: str = "python",
        working_dir: Optional[Path] = None
    ) -> Dict:
        """
        Execute code in isolated sandbox.
        
        Args:
            code: Code to execute
            language: Programming language (python, javascript, etc.)
            working_dir: Optional working directory with files
            
        Returns:
            Dict with execution results:
            {
                "success": bool,
                "output": str,
                "error": str,
                "exit_code": int,
                "duration": float,
                "container_id": str
            }
        """
        container_id = f"sandbox_{uuid.uuid4().hex[:8]}"
        start_time = datetime.utcnow()
        
        logger.info(f"Starting sandbox execution: {container_id}")
        
        try:
            # Create temporary directory for code
            with tempfile.TemporaryDirectory() as tmpdir:
                code_file = Path(tmpdir) / f"script.{self._get_extension(language)}"
                code_file.write_text(code, encoding='utf-8')
                
                # Prepare Docker volumes
                volumes = {
                    tmpdir: {'bind': '/workspace', 'mode': 'ro'}  # Read-only
                }
                
                # If working_dir provided, add it as read-only volume
                if working_dir and working_dir.exists():
                    volumes[str(working_dir)] = {'bind': '/data', 'mode': 'ro'}
                
                # Week 1, Day 2: Load seccomp profile for syscall filtering
                seccomp_profile = self._load_seccomp_profile()
                
                # Container configuration
                container_config = {
                    'image': self.image,
                    'command': self._get_command(language, '/workspace/script'),
                    'volumes': volumes,
                    'working_dir': '/workspace',
                    'detach': True,
                    'remove': True,  # Auto-remove after execution
                    'name': container_id,
                    
                    # Security settings
                    'network_disabled': self.network_disabled,
                    'read_only': True,  # Read-only root filesystem
                    'tmpfs': {'/tmp': 'size=100m,mode=1777'},  # Writable /tmp
                    'security_opt': [
                        'no-new-privileges:true',
                        f'seccomp={seccomp_profile}'  # Week 1, Day 2: Seccomp profile
                    ],
                    'cap_drop': ['ALL'],  # Drop all capabilities
                    'cap_add': [],  # No additional capabilities
                    
                    # Resource limits
                    'cpu_quota': int(self.cpu_limit * 100000),
                    'cpu_period': 100000,
                    'mem_limit': self.memory_limit,
                    'memswap_limit': self.memory_limit,  # No swap
                    'pids_limit': 100,  # Process limit
                    
                    # Environment
                    'environment': {
                        'PYTHONUNBUFFERED': '1',
                        'SANDBOX': 'true'
                    }
                }
                
                # Run container
                container = self.client.containers.run(**container_config)
                
                # Wait for completion with timeout
                try:
                    result = container.wait(timeout=self.timeout)
                    exit_code = result['StatusCode']
                    
                    # Get logs
                    output = container.logs(stdout=True, stderr=False).decode('utf-8')
                    error = container.logs(stdout=False, stderr=True).decode('utf-8')
                    
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    
                    logger.info(f"Sandbox {container_id} completed: exit_code={exit_code}, duration={duration:.2f}s")
                    
                    return {
                        "success": exit_code == 0,
                        "output": output,
                        "error": error,
                        "exit_code": exit_code,
                        "duration": duration,
                        "container_id": container_id,
                        "timeout_exceeded": False
                    }
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Sandbox {container_id} timeout exceeded ({self.timeout}s)")
                    container.stop(timeout=1)
                    
                    return {
                        "success": False,
                        "output": "",
                        "error": f"Execution timeout ({self.timeout}s) exceeded",
                        "exit_code": -1,
                        "duration": self.timeout,
                        "container_id": container_id,
                        "timeout_exceeded": True
                    }
                    
        except DockerException as e:
            logger.error(f"Docker error in sandbox {container_id}: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Docker error: {str(e)}",
                "exit_code": -1,
                "duration": 0,
                "container_id": container_id,
                "timeout_exceeded": False
            }
        
        except Exception as e:
            logger.error(f"Unexpected error in sandbox {container_id}: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Sandbox error: {str(e)}",
                "exit_code": -1,
                "duration": 0,
                "container_id": container_id,
                "timeout_exceeded": False
            }
    
    def _load_seccomp_profile(self) -> str:
        """
        Load seccomp profile for syscall filtering.
        Week 1, Day 2: Enhanced security via syscall whitelist/blacklist.
        
        Returns:
            Path to seccomp profile JSON file
        """
        # Determine which profile to use based on environment
        profile_name = os.getenv('SECCOMP_PROFILE', 'seccomp-profile-strict.json')
        
        # Profile paths
        sandbox_dir = Path(__file__).parent
        profile_path = sandbox_dir / profile_name
        
        # Fallback to default if strict not found
        if not profile_path.exists():
            logger.warning(f"Seccomp profile {profile_name} not found, using default")
            profile_path = sandbox_dir / 'seccomp-profile.json'
        
        if not profile_path.exists():
            logger.error("No seccomp profile found! Container will run without seccomp.")
            return 'unconfined'  # Fallback to no seccomp (not recommended)
        
        logger.info(f"Using seccomp profile: {profile_path}")
        return str(profile_path.absolute())
    
    def _get_extension(self, language: str) -> str:
        """Get file extension for language"""
        extensions = {
            'python': 'py',
            'javascript': 'js',
            'typescript': 'ts',
            'bash': 'sh',
        }
        return extensions.get(language.lower(), 'txt')
    
    def _get_command(self, language: str, script_path: str) -> List[str]:
        """Get execution command for language"""
        commands = {
            'python': ['python', f'{script_path}.py'],
            'javascript': ['node', f'{script_path}.js'],
            'bash': ['bash', f'{script_path}.sh'],
        }
        return commands.get(language.lower(), ['cat', script_path])
    
    async def test_sandbox(self) -> bool:
        """
        Test sandbox functionality.
        
        Returns:
            True if sandbox works correctly
        """
        test_code = """
import sys
print("Hello from sandbox!")
print(f"Python version: {sys.version}")
"""
        
        result = await self.execute_code(test_code, language='python')
        
        if result['success']:
            logger.info("Sandbox test passed")
            return True
        else:
            logger.error(f"Sandbox test failed: {result['error']}")
            return False
    
    def cleanup(self):
        """Cleanup sandbox resources"""
        try:
            # Remove dangling sandbox containers
            containers = self.client.containers.list(
                all=True,
                filters={'name': 'sandbox_*'}
            )
            
            for container in containers:
                logger.info(f"Cleaning up container: {container.name}")
                container.remove(force=True)
                
        except DockerException as e:
            logger.error(f"Cleanup error: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
