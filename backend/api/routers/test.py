"""
Test endpoints for E2E testing
Provides database reset and cleanup functionality
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any
import os
import logging

from backend.database import get_db
from backend.models import User, Strategy, Backtest, Optimization
from backend.utils.password import hash_password

router = APIRouter(prefix="/test", tags=["testing"])
logger = logging.getLogger(__name__)

# Only allow in testing mode
def require_testing_mode():
    """Ensure endpoint is only accessible in testing mode"""
    if os.getenv("TESTING") != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are only available in TESTING mode"
        )


@router.post("/reset")
async def reset_test_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Reset database to clean state with test fixtures
    
    This endpoint:
    1. Truncates all test-related tables
    2. Reloads baseline test data (admin + user accounts)
    3. Returns confirmation
    
    ⚠️ Only works when TESTING=true environment variable is set
    """
    require_testing_mode()
    
    try:
        logger.info("🔄 Starting database reset...")
        
        # Step 1: Delete all test data (in correct order to respect foreign keys)
        db.query(Optimization).delete()
        db.query(Backtest).delete()
        db.query(Strategy).delete()
        # Don't delete users - we'll update them instead
        
        # Step 2: Ensure test users exist with known credentials
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                role="admin",
                scopes=["read", "write", "admin", "run_task", "view_logs", "manage_workers", "sandbox_exec"]
            )
            db.add(admin_user)
            logger.info("✅ Created admin user")
        else:
            # Update password to ensure it's correct
            admin_user.hashed_password = hash_password("admin123")
            logger.info("✅ Updated admin user password")
        
        regular_user = db.query(User).filter(User.username == "user").first()
        if not regular_user:
            regular_user = User(
                username="user",
                email="user@example.com",
                hashed_password=hash_password("user123"),
                role="user",
                scopes=["read", "write"]
            )
            db.add(regular_user)
            logger.info("✅ Created regular user")
        else:
            # Update password to ensure it's correct
            regular_user.hashed_password = hash_password("user123")
            logger.info("✅ Updated regular user password")
        
        # Step 3: Commit changes
        db.commit()
        
        logger.info("✅ Database reset complete!")
        
        return {
            "status": "reset_complete",
            "message": "Database reset to clean state with test fixtures",
            "users": {
                "admin": {"username": "admin", "password": "admin123"},
                "user": {"username": "user", "password": "user123"}
            },
            "tables_cleared": ["strategies", "backtests", "optimizations"]
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Database reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database reset failed: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_test_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Clean up test artifacts after test run
    
    This endpoint:
    1. Removes temporary test data
    2. Clears rate limiter state (if applicable)
    3. Resets any test flags
    
    ⚠️ Only works when TESTING=true environment variable is set
    """
    require_testing_mode()
    
    try:
        logger.info("🧹 Starting test cleanup...")
        
        # Step 1: Remove test artifacts (strategies/backtests created during tests)
        test_strategies = db.query(Strategy).filter(
            Strategy.name.like("test_%")
        ).delete(synchronize_session=False)
        
        test_backtests = db.query(Backtest).filter(
            Backtest.strategy_id.in_(
                db.query(Strategy.id).filter(Strategy.name.like("test_%"))
            )
        ).delete(synchronize_session=False)
        
        # Step 2: Commit cleanup
        db.commit()
        
        logger.info(f"✅ Cleanup complete! Removed {test_strategies} test strategies, {test_backtests} test backtests")
        
        return {
            "status": "cleanup_complete",
            "message": "Test artifacts cleaned up successfully",
            "removed": {
                "strategies": test_strategies,
                "backtests": test_backtests
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Test cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test cleanup failed: {str(e)}"
        )


@router.get("/health/db")
async def health_check_db(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Check database connectivity and health
    
    Returns:
    - status: "healthy" or "unhealthy"
    - database: "connected" or error message
    - users_count: Number of users in database
    """
    try:
        # Test database query (SQLAlchemy 2.0 compatible)
        result = db.execute(text("SELECT 1")).scalar()
        users_count = db.query(User).count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "users_count": users_count,
            "test_mode": os.getenv("TESTING") == "true"
        }
        
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": str(e),
            "users_count": 0,
            "test_mode": os.getenv("TESTING") == "true"
        }
