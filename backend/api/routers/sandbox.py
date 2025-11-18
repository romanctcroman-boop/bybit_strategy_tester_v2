"""
Bybit Strategy Tester V2 - Sandbox API Router
==============================================
Purpose: REST API endpoints for secure code execution in sandbox
Endpoints:
    POST /sandbox/execute - Execute code in sandbox
    POST /sandbox/validate - Validate code without execution
    GET /sandbox/status - Get sandbox system status
Author: Multi-Agent System (DeepSeek + Perplexity AI)
Created: 2025-11-01
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field, validator

from backend.services.sandbox_executor import (
    SandboxExecutor,
    ExecutionResult,
    ExecutionStatus,
    execute_strategy,
)
from backend.core.code_validator import (
    validate_strategy_code,
    ValidationResult,
    SecurityLevel,
)


logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/sandbox",
    tags=["sandbox"],
    responses={
        500: {"description": "Internal server error"},
        503: {"description": "Docker service unavailable"},
    },
)

# Global sandbox executor instance (reuse Docker client)
_executor: Optional[SandboxExecutor] = None


def get_executor() -> SandboxExecutor:
    """Get or create global sandbox executor instance"""
    global _executor
    if _executor is None:
        _executor = SandboxExecutor(
            image="bybit-sandbox:latest",
            timeout=300,  # 5 minutes default
            memory_limit="512m",
            cpu_limit=1.0,
        )
    return _executor


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class CodeExecutionRequest(BaseModel):
    """Request model for code execution"""
    code: str = Field(..., description="Python strategy code to execute", min_length=1)
    input_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional input data (passed as JSON file)"
    )
    timeout: int = Field(
        300,
        description="Execution timeout in seconds",
        ge=10,
        le=600
    )
    memory_limit: str = Field(
        "512m",
        description="Memory limit (e.g., '512m', '1g')"
    )
    cpu_limit: float = Field(
        1.0,
        description="CPU cores limit",
        ge=0.5,
        le=4.0
    )
    
    @validator('code')
    def validate_code_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Code cannot be empty")
        return v


class CodeValidationRequest(BaseModel):
    """Request model for code validation"""
    code: str = Field(..., description="Python code to validate", min_length=1)
    max_complexity: int = Field(
        100,
        description="Maximum allowed cyclomatic complexity",
        ge=10,
        le=1000
    )


class ValidationResponse(BaseModel):
    """Response model for code validation"""
    is_safe: bool
    security_score: int
    security_level: str
    violations: list
    warnings: list
    stats: Dict[str, int]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExecutionResponse(BaseModel):
    """Response model for code execution"""
    status: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    validation_result: Optional[ValidationResponse] = None
    resource_usage: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SandboxStatusResponse(BaseModel):
    """Response model for sandbox status"""
    docker_available: bool
    sandbox_image_available: bool
    sandbox_image_name: str
    active_executions: int
    system_info: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.post(
    "/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute code in sandbox",
    description="Execute Python strategy code in isolated Docker sandbox",
)
async def execute_code(request: CodeExecutionRequest) -> ExecutionResponse:
    """
    Execute code in secure sandbox environment.
    
    Security features:
    - AST validation before execution
    - Docker container isolation
    - Resource limits (CPU, RAM, timeout)
    - Network isolation
    - Read-only filesystem
    
    Example:
        POST /sandbox/execute
        {
            "code": "import pandas as pd\\nprint('Hello!')",
            "timeout": 60
        }
    """
    try:
        # Create executor with custom settings
        executor = SandboxExecutor(
            timeout=request.timeout,
            memory_limit=request.memory_limit,
            cpu_limit=request.cpu_limit,
        )
        
        # Execute code
        result = await executor.execute(
            code=request.code,
            input_data=request.input_data,
        )
        
        # Convert to response model
        return ExecutionResponse(
            status=result.status.value,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            validation_result=_convert_validation_result(result.validation_result) if result.validation_result else None,
            resource_usage=result.resource_usage,
            error_message=result.error_message,
        )
    
    except Exception as e:
        logger.exception(f"Failed to execute code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )
    
    finally:
        if 'executor' in locals():
            executor.close()


@router.post(
    "/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate code without execution",
    description="Perform AST-based security validation on code",
)
async def validate_code(request: CodeValidationRequest) -> ValidationResponse:
    """
    Validate code security without execution.
    
    Checks:
    - Dangerous imports (os, sys, subprocess, etc.)
    - Dangerous functions (eval, exec, compile, etc.)
    - Dangerous attribute access (__code__, __globals__, etc.)
    - Code complexity
    
    Example:
        POST /sandbox/validate
        {
            "code": "import pandas as pd\\ndf = pd.DataFrame()",
            "max_complexity": 100
        }
    """
    try:
        result = validate_strategy_code(
            code=request.code,
            max_complexity=request.max_complexity,
        )
        
        return _convert_validation_result(result)
    
    except Exception as e:
        logger.exception(f"Failed to validate code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


@router.get(
    "/status",
    response_model=SandboxStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get sandbox system status",
    description="Check Docker availability and sandbox image status",
)
async def get_sandbox_status() -> SandboxStatusResponse:
    """
    Get sandbox system status.
    
    Returns:
    - Docker availability
    - Sandbox image availability
    - System information
    
    Example:
        GET /sandbox/status
    """
    import docker
    from docker.errors import DockerException
    
    try:
        # Check Docker availability
        client = docker.from_env()
        docker_version = client.version()
        docker_available = True
        
        # Check sandbox image
        image_name = "bybit-sandbox:latest"
        try:
            client.images.get(image_name)
            sandbox_image_available = True
        except docker.errors.ImageNotFound:
            sandbox_image_available = False
        
        # System info
        system_info = {
            "docker_version": docker_version.get("Version", "unknown"),
            "api_version": docker_version.get("ApiVersion", "unknown"),
            "os": docker_version.get("Os", "unknown"),
            "arch": docker_version.get("Arch", "unknown"),
        }
        
        client.close()
        
        return SandboxStatusResponse(
            docker_available=docker_available,
            sandbox_image_available=sandbox_image_available,
            sandbox_image_name=image_name,
            active_executions=0,  # TODO: Track active executions
            system_info=system_info,
        )
    
    except DockerException as e:
        logger.warning(f"Docker not available: {e}")
        return SandboxStatusResponse(
            docker_available=False,
            sandbox_image_available=False,
            sandbox_image_name="bybit-sandbox:latest",
            active_executions=0,
            system_info={"error": str(e)},
        )
    
    except Exception as e:
        logger.exception(f"Failed to get sandbox status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _convert_validation_result(result: ValidationResult) -> ValidationResponse:
    """Convert ValidationResult to ValidationResponse"""
    return ValidationResponse(
        is_safe=result.is_safe,
        security_score=result.security_score,
        security_level=result.security_level.value,
        violations=result.violations,
        warnings=result.warnings,
        stats=result.stats,
    )


# ==============================================================================
# LIFECYCLE HOOKS
# ==============================================================================

@router.on_event("startup")
async def startup_event():
    """Initialize sandbox executor on startup"""
    logger.info("Initializing sandbox executor...")
    try:
        executor = get_executor()
        logger.info(f"Sandbox executor initialized: image={executor.image}")
    except Exception as e:
        logger.error(f"Failed to initialize sandbox executor: {e}")
        logger.warning("Sandbox endpoints will be unavailable!")


@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup sandbox executor on shutdown"""
    global _executor
    if _executor:
        logger.info("Closing sandbox executor...")
        _executor.close()
        _executor = None
        logger.info("Sandbox executor closed")
