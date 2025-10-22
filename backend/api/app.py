from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.api.routers import strategies, backtests, marketdata, admin
from backend.api.routers import optimizations
from backend.api.routers import bots as bots_router
from backend.api.routers import active_deals as active_deals_router
from backend.api.routers import live as live_router
from backend.api.routers import wizard as wizard_router
from backend.config import CONFIG

# Optional: start BybitWsManager on app startup when feature flag is enabled
try:
    from redis.asyncio import Redis
    from backend.services.bybit_ws_manager import BybitWsManager
except Exception:
    Redis = None  # type: ignore
    BybitWsManager = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if CONFIG.ws_enabled and Redis is not None and BybitWsManager is not None:
        try:
            r = Redis.from_url(CONFIG.redis.url, encoding="utf-8", decode_responses=True)
            mgr = BybitWsManager(r, CONFIG.redis.channel_ticks, CONFIG.redis.channel_klines)
            await mgr.start(symbols=CONFIG.ws_symbols, intervals=CONFIG.ws_intervals)
            app.state.ws_resources = (mgr, r)
        except Exception:
            app.state.ws_resources = None
    else:
        app.state.ws_resources = None

    yield

    # Shutdown
    ws = getattr(app.state, "ws_resources", None)
    if ws:
        mgr, r = ws
        try:
            await mgr.stop()
        finally:
            try:
                await r.close()
            except Exception:
                pass


app = FastAPI(title="bybit_strategy_tester_v2 API", version="0.1", lifespan=lifespan)

app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(marketdata.router, prefix="/api/v1/marketdata", tags=["marketdata"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(optimizations.router, prefix="/api/v1/optimizations", tags=["optimizations"])
app.include_router(live_router.router, prefix="/api/v1", tags=["live"])
# Also expose WebSocket endpoints under /ws for frontend clients (ws://host/ws and ws://host/ws/live)
app.include_router(live_router.router, prefix="/ws", tags=["live-ws"])
app.include_router(wizard_router.router, prefix="/api/v1/wizard", tags=["wizard"])
app.include_router(bots_router.router, prefix="/api/v1/bots", tags=["bots"])
app.include_router(active_deals_router.router, prefix="/api/v1/active-deals", tags=["active-deals"])

# Optional Prometheus metrics (/metrics), minimal text format
from fastapi import Response
from prometheus_client import Counter, Histogram, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest

# Prometheus metrics registry and metrics
REGISTRY = CollectorRegistry()
BACKFILL_UPSERTS = Counter(
    "backfill_upserts_total",
    "Total number of upserts performed by backfill",
    labelnames=("symbol", "interval"),
    registry=REGISTRY,
)
BACKFILL_PAGES = Counter(
    "backfill_pages_total",
    "Total number of pages processed by backfill",
    labelnames=("symbol", "interval"),
    registry=REGISTRY,
)
BACKFILL_DURATION = Histogram(
    "backfill_duration_seconds",
    "Backfill duration in seconds",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, float("inf")),
    registry=REGISTRY,
)
RUNS_BY_STATUS = Counter(
    "backfill_runs_total",
    "Backfill runs by terminal status",
    labelnames=("status",),
    registry=REGISTRY,
)


def metrics_inc_upserts(symbol: str, interval: str, n: int = 1):
    try:
        BACKFILL_UPSERTS.labels(symbol=symbol, interval=interval).inc(n)
    except Exception:
        pass


def metrics_inc_pages(symbol: str, interval: str, n: int = 1):
    try:
        BACKFILL_PAGES.labels(symbol=symbol, interval=interval).inc(n)
    except Exception:
        pass


def metrics_observe_duration(seconds: float):
    try:
        BACKFILL_DURATION.observe(seconds)
    except Exception:
        pass


def metrics_inc_run_status(status: str):
    try:
        RUNS_BY_STATUS.labels(status=status).inc(1)
    except Exception:
        pass


@app.get("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    # In a real deployment, check DB connectivity, broker reachability, etc.
    return {"status": "ready"}


@app.get("/livez")
def livez():
    return {"status": "alive"}


# Background Bybit WS manager is handled via the app lifespan above.
