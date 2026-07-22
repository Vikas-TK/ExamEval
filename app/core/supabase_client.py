"""
Singleton Supabase Client for AI AutoGrader system.
Handles environment variable validation, client initialization, and error handling.
"""

from typing import Optional
from loguru import logger
from supabase import Client, create_client

from app.core.config import get_settings


class SupabaseClientManager:
    _instance: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._instance is None:
            settings = get_settings()
            url = settings.supabase_url.strip() if settings.supabase_url else ""
            key = settings.supabase_service_role_key.strip() if settings.supabase_service_role_key else ""

            if not url or not key:
                logger.error("Supabase URL or Service Role Key is missing from configuration.")
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be provided.")

            try:
                cls._instance = create_client(url, key)
                logger.info("Supabase client initialized successfully.")
            except Exception as exc:
                logger.error(f"Failed to initialize Supabase client: {exc}")
                raise RuntimeError(f"Could not connect to Supabase: {exc}") from exc

        return cls._instance

    @classmethod
    def validate_connection(cls) -> bool:
        """Validates that Supabase client can be instantiated and reached."""
        try:
            client = cls.get_client()
            return client is not None
        except Exception as exc:
            logger.warning(f"Supabase connection validation failed: {exc}")
            return False


def get_supabase() -> Client:
    """Convenience helper to fetch the singleton Supabase client instance."""
    return SupabaseClientManager.get_client()
