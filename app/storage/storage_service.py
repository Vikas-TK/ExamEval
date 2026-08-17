"""
Storage Service abstraction layer for AI AutoGrader system.
Primary Storage Provider: Supabase Storage.
Provides reusable functions: upload_file, download_file, delete_file, list_files.
Decouples application logic from storage infrastructure.
"""

from abc import ABC, abstractmethod
import urllib.request
import urllib.error
import urllib.parse
from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.config import get_settings
from app.core.supabase_client import SupabaseClientManager

settings = get_settings()


class BaseStorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    def upload_file(
        self,
        data: bytes,
        bucket_name: str,
        file_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        pass

    @abstractmethod
    def download_file(self, bucket_name: str, file_path: str) -> bytes:
        pass

    @abstractmethod
    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        pass

    @abstractmethod
    def list_files(self, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        pass


class SupabaseStorageProvider(BaseStorageProvider):
    """Storage provider implementation using Supabase Storage."""

    def __init__(self):
        self.settings = get_settings()

    def upload_file(
        self,
        data: bytes,
        bucket_name: str,
        file_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Uploads raw bytes to a Supabase Storage bucket and returns the access URL."""
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            logger.warning("Supabase storage credentials not set. Falling back to local reference.")
            return f"supabase://{bucket_name}/{file_path}"

        encoded_path = urllib.parse.quote(file_path, safe="/")
        target_url = f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}/{encoded_path}"
        token = self.settings.supabase_service_role_key
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": token,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        req = urllib.request.Request(target_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 201):
                    logger.info(f"Uploaded file to Supabase Storage: bucket={bucket_name}, path={file_path}")
                    return f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{encoded_path}"
        except Exception as exc:
            logger.error(f"Failed to upload to Supabase Storage: bucket={bucket_name}, path={file_path}, error={exc}")
            # Fallback to direct client API if available
            try:
                client = SupabaseClientManager.get_client()
                res = client.storage.from_(bucket_name).upload(
                    file_path,
                    data,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
                return f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{encoded_path}"
            except Exception as client_exc:
                logger.error(f"Supabase client upload fallback error: {client_exc}")

        return f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{encoded_path}"

    def download_file(self, bucket_name: str, file_path: str) -> bytes:
        """Downloads raw bytes of a file from Supabase Storage."""
        if self.settings.supabase_url and self.settings.supabase_service_role_key:
            encoded_path = urllib.parse.quote(file_path, safe="/")
            target_url = f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/authenticated/{bucket_name}/{encoded_path}"
            token = self.settings.supabase_service_role_key
            headers = {"Authorization": f"Bearer {token}", "apikey": token}
            req = urllib.request.Request(target_url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req) as resp:
                    return resp.read()
            except Exception as exc:
                logger.error(f"REST download error for bucket={bucket_name}, path={file_path}: {exc}")

        try:
            client = SupabaseClientManager.get_client()
            return client.storage.from_(bucket_name).download(file_path)
        except Exception as exc:
            logger.error(f"Supabase client download error: {exc}")
            return b""

    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """Deletes a file from Supabase Storage."""
        try:
            client = SupabaseClientManager.get_client()
            client.storage.from_(bucket_name).remove([file_path])
            logger.info(f"Deleted file from Supabase Storage: bucket={bucket_name}, path={file_path}")
            return True
        except Exception as exc:
            logger.error(f"Failed to delete file from Supabase Storage: {exc}")
            return False

    def list_files(self, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        """Lists files in a given bucket matching prefix."""
        try:
            client = SupabaseClientManager.get_client()
            options = {"prefix": prefix} if prefix else {}
            res = client.storage.from_(bucket_name).list(prefix, options)
            return res if isinstance(res, list) else []
        except Exception as exc:
            logger.error(f"Failed to list files in Supabase Storage bucket={bucket_name}: {exc}")
            return []


class StorageService:
    """
    Unified Storage Service delegating to the configured storage provider.
    Enables zero-code-change provider swapping.
    """

    def __init__(self, provider: Optional[BaseStorageProvider] = None):
        self.provider = provider or SupabaseStorageProvider()

    def upload_file(
        self,
        data: bytes,
        bucket_name: str,
        file_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        return self.provider.upload_file(data, bucket_name, file_path, content_type)

    def download_file(self, bucket_name: str, file_path: str) -> bytes:
        return self.provider.download_file(bucket_name, file_path)

    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        return self.provider.delete_file(bucket_name, file_path)

    def list_files(self, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        return self.provider.list_files(bucket_name, prefix)


# Global singleton instance for easy dependency injection across services
storage_service = StorageService()
