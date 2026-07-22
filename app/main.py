from contextlib import asynccontextmanager
import os
import sys

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.supabase_client import SupabaseClientManager
from app.db.database import check_database_connection, engine
from app.routers import evaluation, blueprint, academic_master

settings = get_settings()

# Configure Loguru logger
logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level.upper(),
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)


def validate_startup_configuration():
    """
    Validates required environment variables, database connectivity,
    and Supabase connection on application startup.
    Fails startup if any required item is missing or unreachable.
    """
    logger.info("Performing startup configuration validation...")
    errors = []

    # 1. Environment Variable Validation
    if settings.storage_provider.lower() == "supabase":
        if not settings.supabase_url or "supabase.co" not in settings.supabase_url:
            if settings.app_env.lower() == "production":
                errors.append("SUPABASE_URL is missing or invalid.")
            else:
                logger.warning("SUPABASE_URL is not configured. Supabase storage will be disabled in development.")
        if not settings.supabase_service_role_key or settings.supabase_service_role_key == "<YOUR_SUPABASE_SERVICE_ROLE_KEY>":
            if settings.app_env.lower() == "production":
                errors.append("SUPABASE_SERVICE_ROLE_KEY is missing or unconfigured.")
            else:
                logger.warning("SUPABASE_SERVICE_ROLE_KEY is not configured. Supabase storage will be disabled in development.")
        if settings.supabase_url and settings.supabase_service_role_key:
            if not SupabaseClientManager.validate_connection():
                errors.append("Failed to initialize or validate Supabase client.")

    required_buckets = [
        ("STORAGE_BUCKET_QUESTION", settings.storage_bucket_question),
        ("STORAGE_BUCKET_FACULTY", settings.storage_bucket_faculty),
        ("STORAGE_BUCKET_BLUEPRINT", settings.storage_bucket_blueprint),
        ("STORAGE_BUCKET_REPORT", settings.storage_bucket_report),
    ]
    for bucket_env, bucket_val in required_buckets:
        if not bucket_val:
            errors.append(f"Storage bucket variable '{bucket_env}' is missing.")

    # 2. Database Connectivity Check
    if not check_database_connection():
        errors.append("Failed to establish connection to the configured database.")

    if errors:
        for err in errors:
            logger.critical(f"STARTUP VALIDATION ERROR: {err}")
        raise RuntimeError(f"Application startup failed due to configuration errors: {'; '.join(errors)}")

    logger.info("Startup validation passed successfully. All connections & configs verified.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup validation and shutdown events."""
    logger.info(f"Starting {settings.app_name} (env={settings.app_env})...")
    validate_startup_configuration()
    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    description="AI-Based Automated Answer Script Evaluation System Backend Infrastructure",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Configure Trusted Hosts
trusted_hosts = [host.strip() for host in settings.trusted_hosts.split(",") if host.strip()]
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

# Register API Routers
app.include_router(evaluation.router)
app.include_router(blueprint.router)
app.include_router(academic_master.router)

# Mount Static Files & Frontend SPA Integration
if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
    if os.path.exists("app/static"):
        app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/")
    def read_root():
        return FileResponse("frontend/dist/index.html")
else:
    if os.path.exists("app/static"):
        app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/")
    def read_root():
        return RedirectResponse(url="/static/index.html")


@app.get("/health", tags=["system"])
def health(response: Response):
    """Health check endpoint validating database connectivity and system status."""
    db_ok = check_database_connection()
    if not db_ok:
        response.status_code = 503
        return {"status": "degraded", "database": "unavailable", "app_name": settings.app_name}
    return {
        "status": "ok",
        "database": "ok",
        "supabase": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
    }
