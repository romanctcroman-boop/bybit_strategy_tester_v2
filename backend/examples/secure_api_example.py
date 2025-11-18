"""
Пример интеграции всех security компонентов в FastAPI
Демонстрирует использование Sandbox, JWT Auth и Rate Limiting
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging

# Security components
from backend.security.sandbox_executor import get_sandbox_executor, SandboxExecutor
from backend.auth.jwt_bearer import (
    jwt_bearer, token_manager, Scopes, require_permissions
)
from backend.middleware.rate_limiter import (
    get_rate_limiter, RateLimitMiddleware, rate_limit_dependency
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Bybit Strategy Tester API",
    version="2.0.0",
    description="Secure API with Sandbox, JWT Auth and Rate Limiting"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting middleware
rate_limiter = get_rate_limiter()
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)


# =============================================================================
# Request/Response Models
# =============================================================================

class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CodeExecutionRequest(BaseModel):
    """Code execution request"""
    code: str
    input_data: Optional[str] = None
    allowed_modules: Optional[list[str]] = None


class CodeExecutionResponse(BaseModel):
    """Code execution response"""
    execution_id: str
    status: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time: Optional[float] = None
    timestamp: str


# =============================================================================
# Authentication Endpoints
# =============================================================================

@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login endpoint - возвращает JWT токены
    
    В production здесь должна быть проверка username/password
    против базы данных
    """
    # TODO: Реальная валидация credentials
    # Сейчас просто демо - любой username/password принимается
    
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
    
    # Определяем scopes на основе роли
    # В production это должно браться из базы данных
    scopes = Scopes.ALL if request.username == "admin" else [
        Scopes.READ, Scopes.RUN_TASK, Scopes.VIEW_LOGS
    ]
    
    # Создаём токены
    access_token = token_manager.create_access_token(
        user_id=request.username,
        scopes=scopes
    )
    
    refresh_token = token_manager.create_refresh_token(
        user_id=request.username
    )
    
    logger.info(f"User {request.username} logged in successfully")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token
    """
    user_id = token_manager.verify_refresh_token(refresh_token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Создаём новые токены
    # TODO: Получить scopes из базы данных
    scopes = Scopes.ALL
    
    new_access_token = token_manager.create_access_token(
        user_id=user_id,
        scopes=scopes
    )
    
    new_refresh_token = token_manager.create_refresh_token(
        user_id=user_id
    )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


# =============================================================================
# Protected Endpoints (with JWT Auth)
# =============================================================================

@app.get("/status")
async def get_status(token_data: dict = Depends(jwt_bearer)):
    """
    Get API status - требует аутентификации
    """
    return {
        "status": "healthy",
        "user": token_data.get("sub"),
        "scopes": token_data.get("scopes", []),
        "authenticated": True
    }


@app.post("/sandbox/execute", response_model=CodeExecutionResponse)
async def execute_code(
    request: CodeExecutionRequest,
    token_data: dict = Depends(jwt_bearer),
    sandbox: SandboxExecutor = Depends(get_sandbox_executor)
):
    """
    Execute AI-generated code in secure sandbox
    
    Требует аутентификации и разрешение SANDBOX_EXEC
    """
    # Проверяем разрешения
    user_scopes = token_data.get("scopes", [])
    if Scopes.SANDBOX_EXEC not in user_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to execute code"
        )
    
    logger.info(f"User {token_data['sub']} executing code in sandbox")
    
    try:
        # Выполняем код в sandbox
        result = await sandbox.execute_python_code(
            code=request.code,
            input_data=request.input_data,
            allowed_modules=request.allowed_modules
        )
        
        return CodeExecutionResponse(**result)
        
    except Exception as e:
        logger.error(f"Sandbox execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sandbox execution failed: {str(e)}"
        )


@app.get("/sandbox/health")
async def sandbox_health(
    token_data: dict = Depends(jwt_bearer),
    sandbox: SandboxExecutor = Depends(get_sandbox_executor)
):
    """
    Check sandbox health - требует аутентификации
    """
    health = await sandbox.health_check()
    return health


# =============================================================================
# Admin Endpoints (требуют ADMIN scope)
# =============================================================================

@app.post("/admin/whitelist/add")
async def add_to_whitelist(
    ip_address: str,
    token_data: dict = Depends(jwt_bearer)
):
    """
    Add IP to rate limit whitelist - только для админов
    """
    # Проверяем admin права
    if Scopes.ADMIN not in token_data.get("scopes", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    rate_limiter.add_to_whitelist(ip_address)
    
    return {
        "status": "success",
        "message": f"IP {ip_address} added to whitelist",
        "admin": token_data["sub"]
    }


@app.post("/admin/blacklist/add")
async def add_to_blacklist(
    ip_address: str,
    token_data: dict = Depends(jwt_bearer)
):
    """
    Add IP to rate limit blacklist - только для админов
    """
    if Scopes.ADMIN not in token_data.get("scopes", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    rate_limiter.add_to_blacklist(ip_address)
    
    return {
        "status": "success",
        "message": f"IP {ip_address} added to blacklist",
        "admin": token_data["sub"]
    }


# =============================================================================
# Public Endpoints (no auth required)
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint - public"""
    return {
        "message": "Bybit Strategy Tester API v2.0",
        "documentation": "/docs",
        "security": {
            "jwt_auth": "enabled",
            "rate_limiting": "enabled",
            "sandbox": "enabled"
        }
    }


@app.get("/health")
async def health_check():
    """Health check - public"""
    return {
        "status": "healthy",
        "timestamp": "2025-11-04"
    }


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Startup initialization"""
    logger.info("="*80)
    logger.info("Starting Bybit Strategy Tester API v2.0")
    logger.info("="*80)
    logger.info("Security features:")
    logger.info("  ✓ JWT Authentication (Bearer)")
    logger.info("  ✓ Rate Limiting (Token Bucket)")
    logger.info("  ✓ Sandbox Execution (Docker)")
    logger.info("="*80)
    
    # Health check sandbox
    sandbox = get_sandbox_executor()
    health = await sandbox.health_check()
    logger.info(f"Sandbox status: {health['status']}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down API...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "secure_api_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
