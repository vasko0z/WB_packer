# app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_schema
from .routers import (
    shipments, boxes, items, sku, users, settings as settings_router,
    sessions, google_sheets, moysklad, stock, admin
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WB Packer API...")
    init_schema()
    logger.info("Database schema initialized")
    yield
    logger.info("Shutting down WB Packer API")


app = FastAPI(
    title="WB Packer API",
    description="API server for WB Packer desktop client",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/api/health":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if api_key not in settings.API_KEYS:
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    return await call_next(request)


@app.get("/api/health")
async def health():
    from .database import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "healthy"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "detail": str(e)})


# Mount routers
app.include_router(shipments.router, prefix="/api/shipments", tags=["shipments"])
app.include_router(items.router, prefix="/api/shipments", tags=["items"])
app.include_router(boxes.router, prefix="/api", tags=["boxes"])
app.include_router(sku.router, prefix="/api/sku", tags=["sku"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(google_sheets.router, prefix="/api/google-sheets", tags=["google-sheets"])
app.include_router(moysklad.router, prefix="/api/moysklad", tags=["moysklad"])
app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
