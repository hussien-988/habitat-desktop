# -*- coding: utf-8 -*-
"""
Data Provider Factory.

Centralizes creation and management of data providers.
Supports switching between Mock, HTTP, and Local DB providers.
"""

import os
from pathlib import Path
from typing import Optional

from .data_provider import DataProvider, DataProviderType
from .mock_data_provider import MockDataProvider
from .http_data_provider import HttpDataProvider
from utils.logger import get_logger

logger = get_logger(__name__)


class DataProviderConfig:
    """Configuration for data provider."""

    def __init__(
        self,
        provider_type: DataProviderType = DataProviderType.MOCK,
        # Mock provider settings
        mock_simulate_delay: bool = True,
        mock_delay_ms: int = 200,
        mock_persist_to_file: bool = False,
        mock_data_file: Optional[Path] = None,
        # HTTP provider settings
        http_base_url: str = "http://localhost:8080",
        http_api_version: str = "v1",
        http_timeout: int = 30,
        http_max_retries: int = 3,
    ):
        self.provider_type = provider_type
        # Mock settings
        self.mock_simulate_delay = mock_simulate_delay
        self.mock_delay_ms = mock_delay_ms
        self.mock_persist_to_file = mock_persist_to_file
        self.mock_data_file = mock_data_file
        # HTTP settings
        self.http_base_url = http_base_url
        self.http_api_version = http_api_version
        self.http_timeout = http_timeout
        self.http_max_retries = http_max_retries

    @classmethod
    def from_env(cls) -> 'DataProviderConfig':
        """
        Load configuration from environment variables.

        Environment variables:
        - TRRCMS_DATA_PROVIDER: "mock", "http", or "local_db"
        - TRRCMS_MOCK_DELAY: Delay in ms for mock provider
        - TRRCMS_MOCK_PERSIST: "true" to persist mock data
        - TRRCMS_MOCK_DATA_FILE: Path to mock data file
        - TRRCMS_API_URL: Base URL for HTTP provider
        - TRRCMS_API_VERSION: API version for HTTP provider
        - TRRCMS_API_TIMEOUT: Request timeout in seconds
        """
        provider_str = os.getenv("TRRCMS_DATA_PROVIDER", "mock").lower()

        if provider_str == "http" or provider_str == "http_api":
            provider_type = DataProviderType.HTTP_API
        elif provider_str == "local_db" or provider_str == "database":
            provider_type = DataProviderType.LOCAL_DB
        else:
            provider_type = DataProviderType.MOCK

        mock_data_file = os.getenv("TRRCMS_MOCK_DATA_FILE")

        return cls(
            provider_type=provider_type,
            mock_simulate_delay=os.getenv("TRRCMS_MOCK_DELAY", "true").lower() == "true",
            mock_delay_ms=int(os.getenv("TRRCMS_MOCK_DELAY_MS", "200")),
            mock_persist_to_file=os.getenv("TRRCMS_MOCK_PERSIST", "false").lower() == "true",
            mock_data_file=Path(mock_data_file) if mock_data_file else None,
            http_base_url=os.getenv("TRRCMS_API_URL", "http://localhost:8080"),
            http_api_version=os.getenv("TRRCMS_API_VERSION", "v1"),
            http_timeout=int(os.getenv("TRRCMS_API_TIMEOUT", "30")),
            http_max_retries=int(os.getenv("TRRCMS_API_MAX_RETRIES", "3")),
        )


class DataProviderFactory:
    """
    Factory for creating and managing data providers.

    Singleton pattern - ensures only one provider instance exists.
    """

    _instance: Optional[DataProvider] = None
    _config: Optional[DataProviderConfig] = None

    @classmethod
    def create(cls, config: Optional[DataProviderConfig] = None) -> DataProvider:
        """
        Create or return existing data provider.

        Args:
            config: Provider configuration. If None, loads from environment.

        Returns:
            DataProvider instance
        """
        if config is None:
            config = DataProviderConfig.from_env()

        # Return existing if same config type
        if cls._instance is not None and cls._config is not None:
            if cls._config.provider_type == config.provider_type:
                return cls._instance
            else:
                # Different type requested - disconnect old provider
                cls.reset()

        cls._config = config

        logger.info(f"Creating data provider: {config.provider_type.value}")

        if config.provider_type == DataProviderType.MOCK:
            provider = MockDataProvider(
                simulate_delay=config.mock_simulate_delay,
                delay_ms=config.mock_delay_ms,
                persist_to_file=config.mock_persist_to_file,
                data_file=config.mock_data_file
            )

        elif config.provider_type == DataProviderType.HTTP_API:
            provider = HttpDataProvider(
                base_url=config.http_base_url,
                api_version=config.http_api_version,
                timeout=config.http_timeout,
                max_retries=config.http_max_retries
            )

        elif config.provider_type == DataProviderType.LOCAL_DB:
            # For local DB, we create a wrapper around existing database
            # This maintains backward compatibility
            from .local_db_data_provider import LocalDbDataProvider
            provider = LocalDbDataProvider()

        else:
            raise ValueError(f"Unknown provider type: {config.provider_type}")

        # Connect the provider
        if provider.connect():
            logger.info(f"Data provider {config.provider_type.value} connected successfully")
        else:
            logger.warning(f"Data provider {config.provider_type.value} failed to connect")

        cls._instance = provider
        return provider

    @classmethod
    def get_instance(cls) -> Optional[DataProvider]:
        """Get current data provider instance."""
        if cls._instance is None:
            return cls.create()
        return cls._instance

    @classmethod
    def get_type(cls) -> Optional[DataProviderType]:
        """Get current provider type."""
        if cls._instance:
            return cls._instance.provider_type
        return None

    @classmethod
    def is_mock(cls) -> bool:
        """Check if using mock provider."""
        return cls._instance and cls._instance.provider_type == DataProviderType.MOCK

    @classmethod
    def is_http(cls) -> bool:
        """Check if using HTTP provider."""
        return cls._instance and cls._instance.provider_type == DataProviderType.HTTP_API

    @classmethod
    def is_local_db(cls) -> bool:
        """Check if using local database provider."""
        return cls._instance and cls._instance.provider_type == DataProviderType.LOCAL_DB

    @classmethod
    def reset(cls) -> None:
        """Reset factory and disconnect current provider."""
        if cls._instance:
            try:
                cls._instance.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting provider: {e}")
        cls._instance = None
        cls._config = None

    @classmethod
    def switch_to_mock(cls) -> DataProvider:
        """Switch to mock data provider."""
        cls.reset()
        config = DataProviderConfig(provider_type=DataProviderType.MOCK)
        return cls.create(config)

    @classmethod
    def switch_to_http(cls, base_url: str = None) -> DataProvider:
        """Switch to HTTP data provider."""
        cls.reset()
        config = DataProviderConfig(
            provider_type=DataProviderType.HTTP_API,
            http_base_url=base_url or os.getenv("TRRCMS_API_URL", "http://localhost:8080")
        )
        return cls.create(config)

    @classmethod
    def switch_to_local_db(cls) -> DataProvider:
        """Switch to local database provider."""
        cls.reset()
        config = DataProviderConfig(provider_type=DataProviderType.LOCAL_DB)
        return cls.create(config)


# Convenience function
def get_data_provider() -> DataProvider:
    """Get the configured data provider."""
    return DataProviderFactory.get_instance()
