"""
Sandbox Manager - High-level orchestration for secure code execution
Combines Docker isolation, security validation, and resource monitoring
"""

import asyncio
from typing import Dict, Optional, List
from pathlib import Path
import logging

from .docker_sandbox import DockerSandbox
from .security_validator import SecurityValidator, SecurityLevel
from .resource_limiter import ResourceLimiter, ResourceLimits

logger = logging.getLogger('sandbox.manager')


class SandboxExecutionError(Exception):
    """Exception raised when sandbox execution fails"""
    pass


class SecurityViolationError(Exception):
    """Exception raised when security validation fails"""
    pass


class SandboxManager:
    """
    High-level manager for secure code execution.
    
    Workflow:
    1. Security validation (static analysis)
    2. Docker sandbox execution (isolation)
    3. Resource monitoring (runtime limits)
    4. Result collection and cleanup
    """
    
    def __init__(
        self,
        docker_image: str = "python:3.11-slim",
        strict_security: bool = True,
        resource_limits: Optional[ResourceLimits] = None
    ):
        """
        Initialize sandbox manager.
        
        Args:
            docker_image: Docker image for code execution
            strict_security: If True, reject code with any dangerous operations
            resource_limits: Resource limits configuration
        """
        self.docker_sandbox = DockerSandbox(image=docker_image)
        self.security_validator = SecurityValidator(strict_mode=strict_security)
        self.default_resource_limits = resource_limits or ResourceLimits()
        self.execution_history: List[Dict] = []
    
    async def execute_code(
        self,
        code: str,
        language: str = "python",
        working_dir: Optional[Path] = None,
        validate_security: bool = True,
        monitor_resources: bool = True,
        resource_limits: Optional[ResourceLimits] = None
    ) -> Dict:
        """
        Execute code in secure sandbox with validation and monitoring.
        
        Args:
            code: Code to execute
            language: Programming language (python, javascript, etc.)
            working_dir: Working directory for execution
            validate_security: If True, perform security validation
            monitor_resources: If True, monitor resource usage
            resource_limits: Custom resource limits (uses default if None)
            
        Returns:
            Dict with execution results:
            {
                "success": bool,
                "output": str,
                "error": str,
                "exit_code": int,
                "duration": float,
                "security_report": Dict,
                "resource_report": Dict,
                "container_id": str
            }
            
        Raises:
            SecurityViolationError: If code fails security validation
            SandboxExecutionError: If execution fails
        """
        execution_id = len(self.execution_history)
        logger.info(f"[Execution {execution_id}] Starting secure code execution")
        
        result = {
            "execution_id": execution_id,
            "success": False,
            "output": "",
            "error": "",
            "exit_code": -1,
            "duration": 0.0,
            "security_report": None,
            "resource_report": None,
            "container_id": None
        }
        
        try:
            # Step 1: Security validation
            if validate_security:
                logger.info(f"[Execution {execution_id}] Step 1: Security validation")
                security_report = self.security_validator.validate_code(code, language)
                result["security_report"] = security_report
                
                if not security_report["safe"]:
                    error_msg = f"Security validation failed: {len(security_report['issues'])} issues found"
                    logger.error(f"[Execution {execution_id}] {error_msg}")
                    result["error"] = error_msg
                    result["security_report"] = security_report
                    raise SecurityViolationError(error_msg)
                
                logger.info(f"[Execution {execution_id}] Security validation passed (score: {security_report['score']}/100)")
            
            # Step 2: Execute in Docker sandbox
            logger.info(f"[Execution {execution_id}] Step 2: Docker sandbox execution")
            
            # Prepare resource monitoring
            resource_limiter = None
            if monitor_resources:
                limits = resource_limits or self.default_resource_limits
                resource_limiter = ResourceLimiter(limits)
            
            # Execute code
            exec_result = await self.docker_sandbox.execute_code(
                code=code,
                language=language,
                working_dir=working_dir
            )
            
            # Update result
            result.update({
                "success": exec_result["success"],
                "output": exec_result["output"],
                "error": exec_result["error"],
                "exit_code": exec_result["exit_code"],
                "duration": exec_result["duration"],
                "container_id": exec_result["container_id"]
            })
            
            # Step 3: Resource monitoring (if enabled)
            if monitor_resources and resource_limiter and exec_result["container_id"]:
                logger.info(f"[Execution {execution_id}] Step 3: Resource monitoring")
                
                # Start monitoring in background
                await resource_limiter.start_monitoring(exec_result["container_id"])
                
                # Wait for execution to complete (already done)
                await resource_limiter.stop_monitoring()
                
                # Get resource report
                resource_report = resource_limiter.get_usage_report()
                result["resource_report"] = resource_report
                
                if resource_report["status"] == "violation":
                    logger.warning(f"[Execution {execution_id}] Resource violations detected")
            
            logger.info(f"[Execution {execution_id}] Execution completed: success={result['success']}, duration={result['duration']:.2f}s")
            
        except SecurityViolationError:
            # Security validation failed - already logged
            pass
        except Exception as e:
            error_msg = f"Sandbox execution error: {str(e)}"
            logger.error(f"[Execution {execution_id}] {error_msg}")
            result["error"] = error_msg
            result["success"] = False
        
        # Save to history
        self.execution_history.append(result)
        
        return result
    
    async def execute_batch(
        self,
        codes: List[Dict[str, str]],
        validate_security: bool = True,
        monitor_resources: bool = True
    ) -> List[Dict]:
        """
        Execute multiple code snippets in sequence.
        
        Args:
            codes: List of dicts with 'code' and optional 'language' keys
            validate_security: If True, validate each code snippet
            monitor_resources: If True, monitor resources for each execution
            
        Returns:
            List of execution results
        """
        results = []
        
        for i, code_info in enumerate(codes):
            logger.info(f"Executing batch item {i+1}/{len(codes)}")
            
            result = await self.execute_code(
                code=code_info["code"],
                language=code_info.get("language", "python"),
                validate_security=validate_security,
                monitor_resources=monitor_resources
            )
            
            results.append(result)
        
        return results
    
    def get_execution_stats(self) -> Dict:
        """
        Get statistics about all executions.
        
        Returns:
            Dict with execution statistics
        """
        if not self.execution_history:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "security_violations": 0,
                "resource_violations": 0,
                "average_duration": 0.0
            }
        
        total = len(self.execution_history)
        successful = sum(1 for e in self.execution_history if e["success"])
        failed = total - successful
        
        security_violations = sum(
            1 for e in self.execution_history 
            if e["security_report"] and not e["security_report"]["safe"]
        )
        
        resource_violations = sum(
            1 for e in self.execution_history 
            if e["resource_report"] and e["resource_report"]["status"] == "violation"
        )
        
        total_duration = sum(e["duration"] for e in self.execution_history)
        avg_duration = total_duration / total if total > 0 else 0.0
        
        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "security_violations": security_violations,
            "resource_violations": resource_violations,
            "average_duration": avg_duration,
            "total_duration": total_duration
        }
    
    async def test_sandbox(self) -> bool:
        """
        Test sandbox functionality with a simple execution.
        
        Returns:
            True if test passed
        """
        logger.info("Testing sandbox functionality...")
        
        test_code = "print('Hello from sandbox!')"
        
        try:
            result = await self.execute_code(
                code=test_code,
                validate_security=True,
                monitor_resources=True
            )
            
            if result["success"] and "Hello from sandbox!" in result["output"]:
                logger.info("✅ Sandbox test passed")
                return True
            else:
                logger.error(f"❌ Sandbox test failed: {result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Sandbox test failed with exception: {e}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup all sandbox resources"""
        logger.info("Cleaning up sandbox resources...")
        self.docker_sandbox.cleanup()
        logger.info("Sandbox cleanup complete")
    
    def format_execution_report(self, result: Dict) -> str:
        """
        Format execution result as human-readable report.
        
        Args:
            result: Execution result from execute_code()
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append(f"Sandbox Execution Report #{result['execution_id']}")
        lines.append("=" * 60)
        lines.append(f"Status: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
        lines.append(f"Duration: {result['duration']:.2f}s")
        lines.append(f"Exit Code: {result['exit_code']}")
        
        if result["container_id"]:
            lines.append(f"Container ID: {result['container_id'][:12]}")
        
        # Security report
        if result["security_report"]:
            sr = result["security_report"]
            lines.append(f"\n🔒 Security Analysis:")
            lines.append(f"  Safe: {'✅ YES' if sr['safe'] else '❌ NO'}")
            lines.append(f"  Score: {sr['score']}/100")
            lines.append(f"  Level: {sr['security_level'].name}")
            if sr["issues"]:
                lines.append(f"  Issues: {len(sr['issues'])}")
        
        # Resource report
        if result["resource_report"]:
            rr = result["resource_report"]
            if rr["status"] != "no_data":
                lines.append(f"\n📊 Resource Usage:")
                lines.append(f"  Status: {'❌ VIOLATION' if rr['status'] == 'violation' else '✅ OK'}")
                lines.append(f"  Peak CPU: {rr['peak_usage']['cpu_percent']:.1f}%")
                lines.append(f"  Peak Memory: {rr['peak_usage']['memory_mb']:.1f}MB")
                lines.append(f"  Average CPU: {rr['average_usage']['cpu_percent']:.1f}%")
                lines.append(f"  Average Memory: {rr['average_usage']['memory_mb']:.1f}MB")
        
        # Output
        if result["output"]:
            lines.append(f"\n📤 Output:")
            lines.append(result["output"][:500])  # Truncate long output
            if len(result["output"]) > 500:
                lines.append("... (truncated)")
        
        # Error
        if result["error"]:
            lines.append(f"\n❌ Error:")
            lines.append(result["error"][:500])  # Truncate long errors
        
        return '\n'.join(lines)
