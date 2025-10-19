"""
Bybit Strategy Tester - FastAPI Main Application

This is the main entry point for the backend API.
Includes CORS, error handling, and API routes.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import time

from backend.middleware.logging import setup_structured_logging

# Configure logger with flexible format (handles missing request_id)
def format_record(record):
    """Custom formatter that handles optional request_id"""
    request_id = record["extra"].get("request_id", "--------")
    return (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        f"{request_id: <8} | "
        "{message}\n"
    )

logger.add(
    "logs/api_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    format=format_record,
    serialize=False
)

# Create FastAPI app
app = FastAPI(
    title="Bybit Strategy Tester API",
    description="Professional cryptocurrency trading strategy backtesting platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (file://, http://localhost, etc)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup structured logging middleware
setup_structured_logging(app)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint
    
    Returns API status and basic information
    """
    return {
        "status": "healthy",
        "service": "Bybit Strategy Tester API",
        "version": "1.0.0",
    }


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint
    
    Returns welcome message and links to documentation
    """
    return {
        "message": "Welcome to Bybit Strategy Tester API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
        },
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Execute on application startup"""
    logger.info("🚀 Starting Bybit Strategy Tester API")
    logger.info("📚 API Documentation: http://localhost:8000/docs")
    logger.info("📖 ReDoc: http://localhost:8000/redoc")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Execute on application shutdown"""
    logger.info("🛑 Shutting down Bybit Strategy Tester API")


# Import and include routers
from backend.api.routers import data, backtest, optimize, live

app.include_router(data.router, prefix="/api/v1")
app.include_router(backtest.router, prefix="/api/v1")
app.include_router(optimize.router, prefix="/api/v1")
app.include_router(live.router, prefix="/api/v1")

# PostgreSQL database routers
try:
    from backend.api.routers import strategies, results
    app.include_router(strategies.router)  # Has /api/strategies prefix
    app.include_router(results.router)      # Has /api/results prefix
    logger.info("✅ PostgreSQL database routers registered")
except ImportError as e:
    logger.warning(f"⚠️  PostgreSQL routers not available: {e}")

logger.info("✅ Optimization API router registered")
logger.info("✅ Live Data WebSocket router registered")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
