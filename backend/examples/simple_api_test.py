"""
Упрощённый тест API для проверки security компонентов
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Security components
from backend.security.sandbox_executor import get_sandbox_executor, SandboxExecutor
from backend.auth.jwt_bearer import jwt_bearer, token_manager, Scopes
from backend.middleware.rate_limiter import get_rate_limiter, RateLimitMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Security Test API",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting middleware
rate_limiter = get_rate_limiter()
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)


# Models
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CodeExecutionRequest(BaseModel):
    code: str


# Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Security Test API",
        "version": "2.0.0",
        "security": {
            "jwt_auth": "enabled",
            "rate_limiting": "enabled",
            "sandbox": "enabled"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy"}


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login endpoint"""
    if not request.username or not request.password:
        raise HTTPException(400, "Username and password required")
    
    # Demo mode - accept any credentials
    scopes = Scopes.ALL if request.username == "admin" else [
        Scopes.READ, Scopes.RUN_TASK
    ]
    
    access_token = token_manager.create_access_token(
        user_id=request.username,
        scopes=scopes
    )
    
    refresh_token = token_manager.create_refresh_token(
        user_id=request.username
    )
    
    logger.info(f"User {request.username} logged in")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@app.get("/status")
async def get_status(token_data: dict = Depends(jwt_bearer)):
    """Protected endpoint"""
    return {
        "status": "authenticated",
        "user": token_data.get("sub"),
        "scopes": token_data.get("scopes", [])
    }


@app.post("/sandbox/execute")
async def execute_code(
    request: CodeExecutionRequest,
    token_data: dict = Depends(jwt_bearer),
    sandbox: SandboxExecutor = Depends(get_sandbox_executor)
):
    """Execute code in sandbox"""
    # Check permissions
    if Scopes.SANDBOX_EXEC not in token_data.get("scopes", []):
        raise HTTPException(403, "SANDBOX_EXEC scope required")
    
    try:
        result = await sandbox.execute_python_code(code=request.code)
        return result
    except Exception as e:
        logger.error(f"Sandbox error: {e}")
        raise HTTPException(500, str(e))


@app.get("/sandbox/health")
async def sandbox_health(
    token_data: dict = Depends(jwt_bearer),
    sandbox: SandboxExecutor = Depends(get_sandbox_executor)
):
    """Sandbox health check"""
    return await sandbox.health_check()


@app.on_event("startup")
async def startup():
    """Startup"""
    logger.info("="*80)
    logger.info("Security Test API v2.0 Starting")
    logger.info("="*80)
    logger.info("✓ JWT Authentication")
    logger.info("✓ Rate Limiting")
    logger.info("✓ Sandbox Execution")
    logger.info("="*80)
    
    # Test sandbox
    sandbox = get_sandbox_executor()
    health = await sandbox.health_check()
    logger.info(f"Sandbox: {health['status']}")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown"""
    logger.info("Shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
