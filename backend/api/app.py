from fastapi import FastAPI

from backend.api.routers import strategies, backtests, marketdata

app = FastAPI(title="bybit_strategy_tester_v2 API", version="0.1")

app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(marketdata.router, prefix="/api/v1/marketdata", tags=["marketdata"])

@app.get("/health")
def health():
    return {"status": "ok"}
