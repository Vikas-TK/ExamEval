"""
Backwards-compatibility layer for configuration.
Re-exports Settings and get_settings from app.core.config.
"""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
