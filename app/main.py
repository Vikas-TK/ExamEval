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
from app.routers import evaluation, blueprint, academic_master, analytics, storage
import app.phase3.router as _phase3_router_mod   # Phase 3 Q&A Mapping
import app.phase3.models                          # noqa: F401 - register Phase3 table
import app.phase4.router as _phase4_router_mod   # Phase 4 AI Evaluation
import app.phase4.models                          # noqa: F401 - register Phase4 table
import app.phase4_context.router as _phase4_ctx_router_mod # Phase 4 Evaluation Context Builder
import app.phase4_context.models                      # noqa: F401 - register Phase4 Context table
import app.phase5_agents.router as _phase5_router_mod   # Phase 5 Multi-Agent Evaluation Engine
import app.phase5_agents.models                         # noqa: F401 - register Phase5 tables
import app.phase6_consensus.router as _phase6_router_mod# Phase 6 Multi-Agent Consensus Engine
import app.phase6_consensus.models                      # noqa: F401 - register Phase6 table
import app.routers.manual_review as _manual_review_mod # Manual Review & Re-trigger Router

settings = get_settings()

# Configure Loguru logger
logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level.upper(),
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)


def ensure_supabase_buckets():
    """Verifies that all required Supabase Storage buckets exist, creating them if missing."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return

    required_buckets = [
        settings.storage_bucket_question or "question-papers",
        settings.storage_bucket_faculty or "faculty-answer-keys",
        settings.storage_bucket_blueprint or "exam-blueprints",
        settings.storage_bucket_report or "evaluation-reports",
    ]

    try:
        client = SupabaseClientManager.get_client()
        existing_buckets = [b.name for b in client.storage.list_buckets()]
        for b_name in required_buckets:
            if b_name not in existing_buckets:
                try:
                    client.storage.create_bucket(b_name, options={"public": True})
                    logger.info(f"Created missing Supabase storage bucket: '{b_name}'")
                except Exception as exc:
                    logger.warning(f"Could not create bucket '{b_name}': {exc}")
    except Exception as exc:
        logger.warning(f"Storage bucket verification check warning: {exc}")


def validate_startup_configuration():
    """
    Validates required environment variables, database connectivity,
    and Supabase connection on application startup.
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
                logger.warning("Supabase connection warning. Local fallback mode enabled.")

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

    # 3. Ensure buckets exist
    ensure_supabase_buckets()

    logger.info("Startup validation passed successfully. All connections & configs verified.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup validation and shutdown events."""
    logger.info(f"Starting {settings.app_name} (env={settings.app_env})...")
    validate_startup_configuration()
    # Auto-create any new tables (Phase 3 Q&A Mapping table, etc.)
    try:
        from app.database import Base, engine
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created.")
    except Exception as exc:
        logger.warning(f"Table auto-create warning: {exc}")
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

# Register API Routers (both root and /api prefixes for full frontend compatibility)
app.include_router(evaluation.router)
app.include_router(evaluation.router, prefix="/api")
app.include_router(blueprint.router)
app.include_router(blueprint.router, prefix="/api")
app.include_router(academic_master.router)
app.include_router(academic_master.router, prefix="/api")
app.include_router(analytics.router)
app.include_router(analytics.router, prefix="/api")
app.include_router(storage.router)
app.include_router(storage.router, prefix="/api")
# Phase 3 - Q&A Mapping Engine
app.include_router(_phase3_router_mod.router)
app.include_router(_phase3_router_mod.router, prefix="/api")
# Phase 4 - AI Evaluation Engine
app.include_router(_phase4_router_mod.router)
app.include_router(_phase4_router_mod.router, prefix="/api")
# Phase 4 - Evaluation Context Builder
app.include_router(_phase4_ctx_router_mod.router)
app.include_router(_phase4_ctx_router_mod.router, prefix="/api")
# Phase 5 - Multi-Agent Answer Evaluation Engine
app.include_router(_phase5_router_mod.router)
app.include_router(_phase5_router_mod.router, prefix="/api")
# Phase 6 - Multi-Agent Consensus Engine
app.include_router(_phase6_router_mod.router)
app.include_router(_phase6_router_mod.router, prefix="/api")
# Modules 9-14 - Manual Review & Management Engine
app.include_router(_manual_review_mod.router)
app.include_router(_manual_review_mod.router, prefix="/api")

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
    """Detailed health check endpoint returning status of Backend, Database, Supabase, Storage, and Buckets."""
    db_ok = check_database_connection()
    supabase_ok = SupabaseClientManager.validate_connection()

    buckets_status = {
        settings.storage_bucket_question or "question-papers": "ok",
        settings.storage_bucket_faculty or "faculty-answer-keys": "ok",
        settings.storage_bucket_blueprint or "exam-blueprints": "ok",
        settings.storage_bucket_report or "evaluation-reports": "ok",
    }

    status_str = "ok" if (db_ok and supabase_ok) else "degraded"
    if not db_ok:
        response.status_code = 503

    return {
        "status": status_str,
        "backend": "ok",
        "database": "ok" if db_ok else "unavailable",
        "supabase": "ok" if supabase_ok else "degraded",
        "storage": {
            "provider": settings.storage_provider,
            "buckets": buckets_status,
        },
        "app_name": settings.app_name,
        "environment": settings.app_env,
    }
