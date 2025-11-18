"""
Minimal test app to verify security integration works
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.middleware.rate_limiter import get_rate_limiter, RateLimitMiddleware
from backend.api.routers import security as security_router

app = FastAPI(
    title="Security Test App",
    version="2.0.0",
    description="Minimal app to test JWT Auth & Rate Limiting"
)

# Add rate limiting middleware
rate_limiter = get_rate_limiter()
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register security router
app.include_router(security_router.router, prefix="/api/v1", tags=["security"])

@app.get("/")
async def root():
    return {"message": "Security Test App - Phase 1 Integration"}

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy", "features": ["jwt_auth", "rate_limiting"]}
