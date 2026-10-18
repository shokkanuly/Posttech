import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
from app.errors import install_error_handlers
from app.middleware import RequestBodyLimitMiddleware
from app.migrate import SchemaNotCurrentError, require_current_schema
from app.routers.academy import router as academy_router
from app.routers.admin import router as admin_router
from app.routers.ai import router as ai_router
from app.routers.auth import demo_accounts
from app.routers.auth import router as auth_router
from app.routers.internal import router as internal_router
from app.routers.manager import router as manager_router
from app.routers.me import router as me_router
from app.routers.notifications import router as notifications_router
from app.routers.requests import router as requests_router
from app.schemas.common import ErrorResponse, HealthResponse, PublicConfig
from app.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables and seed data exist
    require_current_schema(engine)
    if settings.DEMO_MODE:
        seed_database()
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Unified Digital HR Self-Service Platform for Jana Post × Terricon Valley Hackathon 2026",
    version="1.0.0",
    lifespan=lifespan,
    responses={
        code: {"model": ErrorResponse}
        for code in (400, 401, 403, 404, 409, 413, 422, 429, 500, 503)
    },
)

app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)
install_error_handlers(app)

# Same-origin by default. Optional development/deployment origins are explicit.
if settings.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.get(settings.API_V1_STR + "/config", tags=["Configuration"], response_model=PublicConfig)
def public_config(db: Session = Depends(get_db)):
    return {
        "demo_mode": settings.DEMO_MODE,
        "demo_accounts": demo_accounts(db) if settings.DEMO_MODE else {},
    }


# Register API v1 Routers
api_v1_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(me_router, prefix=api_v1_prefix)
app.include_router(requests_router, prefix=api_v1_prefix)
app.include_router(academy_router, prefix=api_v1_prefix)
app.include_router(notifications_router, prefix=api_v1_prefix)
app.include_router(ai_router, prefix=api_v1_prefix)
app.include_router(manager_router, prefix=api_v1_prefix)
app.include_router(admin_router, prefix=api_v1_prefix)
app.include_router(internal_router, prefix=api_v1_prefix)

# Mount Static assets
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health", tags=["Health"], response_model=HealthResponse)
def health_check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    try:
        require_current_schema(engine)
    except SchemaNotCurrentError:
        from fastapi import HTTPException

        raise HTTPException(503, "Database schema is not ready; contact the operator") from None
    return {
        "status": "healthy",
        "platform": "JanaMen Digital HR",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    }


@app.get("/")
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to JanaMen Digital HR API. Visit /docs for the Swagger UI."}
