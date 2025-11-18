"""
Security Router: Authentication & Authorization
Endpoints для login, logout, refresh tokens
"""

from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from pydantic import BaseModel
from typing import Optional
import logging
from sqlalchemy.orm import Session

from backend.auth.jwt_bearer import (
    jwt_bearer,
    token_manager,
    Scopes
)
from backend.security.jwt_manager import JWTManager, TokenType
from backend.database import get_db

# Week 1, Day 1 Enhancement: HTTP-only Cookie Support
_jwt_cookie_manager: Optional[JWTManager] = None

def get_jwt_cookie_manager() -> JWTManager:
    """Get JWT manager for cookie operations"""
    global _jwt_cookie_manager
    if _jwt_cookie_manager is None:
        _jwt_cookie_manager = JWTManager()
    return _jwt_cookie_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class UserInfoResponse(BaseModel):
    """User info response"""
    user_id: str
    scopes: list[str]
    authenticated: bool = True


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/auth/login", response_model=TokenResponse, tags=["security"])
async def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Login endpoint - validates credentials and returns JWT tokens
    
    Week 1, Day 1 Enhancement: Now sets HTTP-only cookies for enhanced security
    - Tokens sent both in response body (backward compatibility) and cookies (secure)
    - HTTP-only cookies prevent XSS attacks
    - SameSite=strict prevents CSRF attacks
    
    - **admin users**: Full access (all scopes)
    - **regular users**: Limited access (read, run_task, view_logs)
    
    Authentication is done via database with bcrypt password hashing.
    """
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
    
    # Authenticate user against database
    from backend.services.user_service import UserService
    user_service = UserService(db)
    
    user = user_service.authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Assign scopes based on user role
    if user.is_admin:
        scopes = Scopes.ALL
    else:
        scopes = [Scopes.READ, Scopes.RUN_TASK, Scopes.VIEW_LOGS]
    
    # Create tokens
    access_token = token_manager.create_access_token(
        user_id=request.username,
        scopes=scopes
    )
    
    refresh_token = token_manager.create_refresh_token(
        user_id=request.username
    )
    
    # Week 1, Day 1: Set secure HTTP-only cookies
    jwt_manager = get_jwt_cookie_manager()
    jwt_manager.set_token_cookie(
        response,
        access_token,
        TokenType.ACCESS,
        secure=True  # HTTPS only in production
    )
    jwt_manager.set_token_cookie(
        response,
        refresh_token,
        TokenType.REFRESH,
        secure=True
    )
    
    logger.info(f"User {request.username} logged in successfully (with secure cookies)")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


class RegisterRequest(BaseModel):
    """User registration request"""
    username: str
    password: str
    email: Optional[str] = None


@router.post("/auth/register", response_model=TokenResponse, tags=["security"])
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account
    
    Creates a new user with hashed password.
    New users are created as regular users (not admins).
    """
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
    
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters"
        )
    
    from backend.services.user_service import UserService
    user_service = UserService(db)
    
    try:
        user = user_service.create_user(
            username=request.username,
            password=request.password,
            email=request.email,
            is_admin=False
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Create tokens for newly registered user
    scopes = [Scopes.READ, Scopes.RUN_TASK, Scopes.VIEW_LOGS]
    
    access_token = token_manager.create_access_token(
        user_id=user.username,
        scopes=scopes
    )
    
    refresh_token = token_manager.create_refresh_token(
        user_id=user.username
    )
    
    logger.info(f"New user {user.username} registered successfully")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["security"])
async def refresh_token(request: RefreshTokenRequest, response: Response, req: Request):
    """
    Refresh access token using refresh token
    
    Week 1, Day 1 Enhancement: Supports both cookie and body-based refresh tokens
    - Tries to extract refresh token from HTTP-only cookie first (secure)
    - Falls back to request body (backward compatibility)
    - Returns new tokens in both response body and cookies
    """
    # Week 1, Day 1: Try to get refresh token from cookie first
    jwt_manager = get_jwt_cookie_manager()
    refresh_token_value = jwt_manager.get_token_from_cookie(req, TokenType.REFRESH)
    
    # Fallback to request body
    if not refresh_token_value:
        refresh_token_value = request.refresh_token
    
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )
    
    user_id = token_manager.verify_refresh_token(refresh_token_value)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # TODO: Get user scopes from database
    # For now: assign admin scopes
    scopes = Scopes.ALL
    
    # Create new tokens
    new_access_token = token_manager.create_access_token(
        user_id=user_id,
        scopes=scopes
    )
    
    new_refresh_token = token_manager.create_refresh_token(
        user_id=user_id
    )
    
    # Week 1, Day 1: Set new secure HTTP-only cookies
    jwt_manager.set_token_cookie(
        response,
        new_access_token,
        TokenType.ACCESS,
        secure=True
    )
    jwt_manager.set_token_cookie(
        response,
        new_refresh_token,
        TokenType.REFRESH,
        secure=True
    )
    
    logger.info(f"Tokens refreshed for user {user_id} (with secure cookies)")
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


@router.get("/auth/me", response_model=UserInfoResponse, tags=["security"])
async def get_current_user(token_data: dict = Depends(jwt_bearer)):
    """
    Get current authenticated user info
    
    Requires: Valid JWT token
    """
    return UserInfoResponse(
        user_id=token_data.get("sub"),
        scopes=token_data.get("scopes", [])
    )


@router.post("/auth/logout", tags=["security"])
async def logout(response: Response, token_data: dict = Depends(jwt_bearer)):
    """
    Logout endpoint
    
    Week 1, Day 1 Enhancement: Now deletes HTTP-only cookies
    - Removes both access and refresh tokens from cookies
    - Prevents cookie reuse after logout
    
    In production: Add token to blacklist/revocation list
    For now: Client-side token deletion + cookie deletion
    """
    user_id = token_data.get("sub")
    
    # Week 1, Day 1: Delete secure HTTP-only cookies
    jwt_manager = get_jwt_cookie_manager()
    jwt_manager.delete_token_cookie(response, TokenType.ACCESS)
    jwt_manager.delete_token_cookie(response, TokenType.REFRESH)
    
    logger.info(f"User {user_id} logged out (cookies deleted)")
    
    return {
        "message": "Logged out successfully",
        "user_id": user_id
    }
