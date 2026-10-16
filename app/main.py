import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.seed import seed_database
from app.routers.auth import router as auth_router
from app.routers.me import router as me_router
from app.routers.requests import router as requests_router
from app.routers.academy import router as academy_router
from app.routers.notifications import router as notifications_router
from app.routers.ai import router as ai_router
from app.routers.manager import router as manager_router
from app.routers.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables and seed data exist
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Unified Digital HR Self-Service Platform for Jana Post × Terricon Valley Hackathon 2026",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Mount Static assets
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health", tags=["Health"])
def health_check():
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
