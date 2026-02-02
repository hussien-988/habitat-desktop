# -*- coding: utf-8 -*-
"""
API Configuration - Smart Configuration with Fallback Support
==============================================================

Provides configurable settings for API backend and tile server with:
- Environment variable support
- Health check capabilities
- Automatic fallback strategies
- SOLID principles implementation

Best Practices Applied:
- Single Responsibility: Each class handles one concern
- Open/Closed: Extensible without modification
- Dependency Inversion: Depends on abstractions
- DRY: No code duplication
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # dotenv not installed, will use system environment variables

# Set up module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Base Classes (SOLID: Liskov Substitution & Interface Segregation)
# ============================================================================

class HealthCheckable(ABC):
    """
    Abstract base for services that support health checks.

    SOLID: Interface Segregation - separate health check concern
    """

    @abstractmethod
    def check_health(self) -> bool:
        """Check if the service is healthy and available."""
        pass


class ConfigurationProvider(ABC):
    """
    Abstract base for configuration providers.

    SOLID: Dependency Inversion - depend on abstractions
    """

    @abstractmethod
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        pass


# ============================================================================
# Configuration Provider Implementation
# ============================================================================

class EnvironmentConfigProvider(ConfigurationProvider):
    """
    Provides configuration from environment variables.

    SOLID: Single Responsibility - only handles env var reading
    DRY: Centralizes env var access
    """

    def __init__(self, prefix: str = ""):
        """
        Initialize provider with optional prefix.

        Args:
            prefix: Prefix for environment variables (e.g., "TRRCMS_")
        """
        self.prefix = prefix

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get value from environment variables."""
        env_key = f"{self.prefix}{key}" if self.prefix else key
        value = os.getenv(env_key, default)
        return value

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer value from environment."""
        value = self.get_value(key, str(default))
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean value from environment."""
        value = self.get_value(key, str(default))
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('true', '1', 'yes', 'on')


# ============================================================================
# Settings Classes (SOLID: Single Responsibility)
# ============================================================================

@dataclass
class ApiSettings:
    """
    API Backend connection settings.

    SOLID: Single Responsibility - only API configuration
    """

    # Connection
    base_url: str = "http://localhost:8081"
    timeout: int = 30

    # Authentication
    username: str = "admin"
    password: str = "Admin@123"

    # Data source mode
    data_source: str = "api"  # "api", "local", or "mock"

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0

    # Token management
    auto_refresh_token: bool = True

    def is_api_mode(self) -> bool:
        """Check if using API backend."""
        return self.data_source == "api"

    def is_local_mode(self) -> bool:
        """Check if using local database."""
        return self.data_source == "local"

    def is_mock_mode(self) -> bool:
        """Check if using mock data."""
        return self.data_source == "mock"

    @classmethod
    def from_env(cls, config_provider: Optional[ConfigurationProvider] = None) -> "ApiSettings":
        """
        Create settings from environment variables.

        SOLID: Dependency Inversion - depends on abstract ConfigurationProvider
        """
        if config_provider is None:
            config_provider = EnvironmentConfigProvider()

        return cls(
            base_url=config_provider.get_value("API_BASE_URL", "http://localhost:8081"),
            timeout=config_provider.get_int("API_TIMEOUT", 30),
            username=config_provider.get_value("API_USERNAME", "admin"),
            password=config_provider.get_value("API_PASSWORD", "Admin@123"),
            data_source=config_provider.get_value("DATA_SOURCE", "api"),
            max_retries=config_provider.get_int("API_MAX_RETRIES", 3),
            auto_refresh_token=config_provider.get_bool("API_AUTO_REFRESH", True),
        )


@dataclass
class TileServerSettings:
    """
    Tile server configuration settings.

    SOLID: Single Responsibility - only tile server configuration
    """

    # Server URL
    url: str = ""
    port: int = 5000

    # Docker settings
    use_docker_tiles: bool = False

    # Fallback settings
    use_embedded_fallback: bool = True
    embedded_tiles_path: str = ""

    # Health check
    health_check_timeout: int = 2

    def has_url(self) -> bool:
        """Check if tile server URL is configured."""
        return bool(self.url and self.url.strip())

    def get_health_url(self) -> str:
        """Get health check endpoint URL."""
        if not self.has_url():
            return ""
        base = self.url.rstrip('/')
        return f"{base}/health"

    @classmethod
    def from_env(cls, config_provider: Optional[ConfigurationProvider] = None) -> "TileServerSettings":
        """Create settings from environment variables."""
        if config_provider is None:
            config_provider = EnvironmentConfigProvider()

        return cls(
            url=config_provider.get_value("TILE_SERVER_URL", ""),
            port=config_provider.get_int("TILE_SERVER_PORT", 5000),
            use_docker_tiles=config_provider.get_bool("USE_DOCKER_TILES", False),
            use_embedded_fallback=config_provider.get_bool("USE_EMBEDDED_TILES_FALLBACK", True),
            health_check_timeout=config_provider.get_int("TILE_SERVER_HEALTH_TIMEOUT", 2),
        )


@dataclass
class ApplicationSettings:
    """
    Combined application settings.

    SOLID: Composition over inheritance
    DRY: Single source of truth for all settings
    """

    api: ApiSettings = field(default_factory=ApiSettings)
    tile_server: TileServerSettings = field(default_factory=TileServerSettings)

    # Metadata
    config_source: str = "environment"

    @classmethod
    def from_env(cls) -> "ApplicationSettings":
        """Create all settings from environment."""
        config_provider = EnvironmentConfigProvider()

        return cls(
            api=ApiSettings.from_env(config_provider),
            tile_server=TileServerSettings.from_env(config_provider),
            config_source="environment"
        )

    @classmethod
    def with_defaults(cls) -> "ApplicationSettings":
        """Create settings with all defaults."""
        return cls(
            api=ApiSettings(),
            tile_server=TileServerSettings(),
            config_source="defaults"
        )


# ============================================================================
# Health Check Service (SOLID: Single Responsibility)
# ============================================================================

class ServiceHealthChecker:
    """
    Performs health checks on services.

    SOLID: Single Responsibility - only health checking
    DRY: Reusable health check logic
    """

    @staticmethod
    def check_url(url: str, timeout: int = 2) -> bool:
        """
        Check if a URL is reachable and healthy.

        Args:
            url: URL to check
            timeout: Request timeout in seconds

        Returns:
            True if healthy, False otherwise
        """
        try:
            import requests
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed for {url}: {e}")
            return False

    @staticmethod
    def check_tile_server(settings: TileServerSettings) -> bool:
        """
        Check if tile server is healthy.

        Args:
            settings: Tile server settings

        Returns:
            True if healthy, False otherwise
        """
        if not settings.has_url():
            return False

        health_url = settings.get_health_url()
        return ServiceHealthChecker.check_url(health_url, settings.health_check_timeout)


# ============================================================================
# Global Settings Manager (Singleton Pattern)
# ============================================================================

class SettingsManager:
    """
    Manages global application settings (Singleton).

    SOLID: Single Responsibility - only settings management
    DRY: Single instance, accessed globally
    """

    _instance: Optional["SettingsManager"] = None
    _settings: Optional[ApplicationSettings] = None

    def __new__(cls):
        """Implement Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_settings(cls) -> ApplicationSettings:
        """
        Get application settings (creates if needed).

        Returns:
            ApplicationSettings instance
        """
        instance = cls()
        if instance._settings is None:
            instance._settings = ApplicationSettings.from_env()
            logger.info(f"Settings loaded from {instance._settings.config_source}")
        return instance._settings

    @classmethod
    def set_settings(cls, settings: ApplicationSettings):
        """Set custom settings (for testing)."""
        instance = cls()
        instance._settings = settings

    @classmethod
    def reset(cls):
        """Reset settings (for testing)."""
        instance = cls()
        instance._settings = None


# ============================================================================
# Public API (DRY: Simple access functions)
# ============================================================================

def get_api_settings() -> ApiSettings:
    """
    Get API settings.

    Returns:
        ApiSettings instance

    Example:
        >>> settings = get_api_settings()
        >>> print(settings.base_url)
        http://localhost:8081
    """
    return SettingsManager.get_settings().api


def get_tile_server_settings() -> TileServerSettings:
    """
    Get tile server settings.

    Returns:
        TileServerSettings instance

    Example:
        >>> settings = get_tile_server_settings()
        >>> if settings.use_docker_tiles:
        >>>     print(f"Using Docker tiles: {settings.url}")
    """
    return SettingsManager.get_settings().tile_server


def get_app_settings() -> ApplicationSettings:
    """
    Get all application settings.

    Returns:
        ApplicationSettings instance
    """
    return SettingsManager.get_settings()


def check_tile_server_health() -> bool:
    """
    Check if configured tile server is healthy.

    Returns:
        True if healthy, False otherwise

    Example:
        >>> if check_tile_server_health():
        >>>     print("Tile server is ready!")
    """
    settings = get_tile_server_settings()
    return ServiceHealthChecker.check_tile_server(settings)


def reset_settings():
    """Reset all settings (for testing)."""
    SettingsManager.reset()


# ============================================================================
# Convenience Functions (DRY: Common operations)
# ============================================================================

def get_active_tile_server_url() -> Optional[str]:
    """
    Get active tile server URL with automatic fallback.

    Strategy:
        1. Check Docker tile server (if enabled)
        2. Fallback to embedded tiles (if enabled)
        3. Return None (use default)

    Returns:
        Tile server URL or None for embedded tiles

    Example:
        >>> url = get_active_tile_server_url()
        >>> if url:
        >>>     print(f"Using tile server: {url}")
        >>> else:
        >>>     print("Using embedded tiles")
    """
    settings = get_tile_server_settings()

    # Try Docker tile server first
    if settings.use_docker_tiles and settings.has_url():
        if ServiceHealthChecker.check_tile_server(settings):
            logger.info(f"✅ Using Docker tile server: {settings.url}")
            return settings.url
        else:
            logger.warning(f"⚠️ Docker tile server not available: {settings.url}")

    # Fallback to embedded
    if settings.use_embedded_fallback:
        logger.info("📦 Using embedded tiles (fallback)")
        return None  # None means use embedded

    # No fallback, return configured URL anyway
    return settings.url if settings.has_url() else None


def is_api_mode() -> bool:
    """Check if application is in API mode."""
    return get_api_settings().is_api_mode()


def is_local_mode() -> bool:
    """Check if application is in local database mode."""
    return get_api_settings().is_local_mode()
