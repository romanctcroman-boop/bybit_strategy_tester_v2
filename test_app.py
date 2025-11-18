"""
Minimal test app - just queue router
"""
from fastapi import FastAPI
from backend.api.routers import queue as queue_router

app = FastAPI()

# Register ONLY queue router
app.include_router(queue_router.router, prefix="/api/v1", tags=["queue"])

@app.get("/")
def root():
    return {"message": "Test app with queue router"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting test app with queue router only...")
    print(f"📝 Routes: {[r.path for r in app.routes if hasattr(r, 'path')]}")
    uvicorn.run(app, host="127.0.0.1", port=9000)
