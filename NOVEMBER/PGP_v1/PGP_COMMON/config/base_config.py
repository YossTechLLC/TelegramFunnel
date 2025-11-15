#!/usr/bin/env python
"""
Base Configuration Manager for PGP_v1 Services.
Provides common configuration methods shared across all PGP_v1 microservices.
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict
from abc import ABC, abstractmethod


class BaseConfigManager(ABC):
    """
    Base class for configuration management across all PGP_v1 services.

    This class provides common methods for:
    - Fetching secrets from environment variables (Cloud Run secret injection)
    - Fetching environment variables
    - Fetching database configuration
    - Fetching Cloud Tasks configuration

    Each service must implement initialize_config() with service-specific secrets.
    """

    def __init__(self, service_name: str):
        """
        Initialize the BaseConfigManager.

        Args:
            service_name: Name of the service (e.g., 'PGP_ORCHESTRATOR_v1')
        """
        self.service_name = service_name
        self.client = secretmanager.SecretManagerServiceClient()
        print(f"⚙️ [CONFIG] ConfigManager initialized for {service_name}")

    def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret value from environment variable.
        Cloud Run automatically injects secret values when using --set-secrets.

        This method is 100% identical across all PGP_v1 services.

        Args:
            secret_name_env: Environment variable name containing the secret value
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            # Defensive pattern: handle None, strip whitespace, return None if empty
            secret_value = (os.getenv(secret_name_env) or '').strip() or None
            if not secret_value:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set or empty")
                return None

            print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
            return None

    def get_env_var(self, var_name: str, description: str = "", required: bool = True) -> Optional[str]:
        """
        Get environment variable value.

        This method is used by some services (e.g., PGP_SPLIT2_v1, PGP_SPLIT3_v1).

        Args:
            var_name: Environment variable name
            description: Description for logging
            required: Whether the variable is required

        Returns:
            Environment variable value or None if not found
        """
        value = os.getenv(var_name)
        if not value:
            if required:
                print(f"❌ [CONFIG] Required environment variable {var_name} is not set or empty")
            else:
                print(f"⚠️ [CONFIG] Optional environment variable {var_name} is not set or empty")
            return None

        print(f"✅ [CONFIG] {description or var_name}: {value[:50]}..." if len(value) > 50 else f"✅ [CONFIG] {description or var_name}: {value}")
        return value

    def fetch_database_config(self) -> Dict[str, Optional[str]]:
        """
        Fetch database configuration from Secret Manager.

        This method is 100% identical across all services that use the database.

        Returns:
            Dictionary with database configuration:
            - instance_connection_name: Cloud SQL connection name
            - db_name: Database name
            - db_user: Database user
            - db_password: Database password
        """
        cloud_sql_connection_name = self.fetch_secret(
            "CLOUD_SQL_CONNECTION_NAME",
            "Cloud SQL instance connection name"
        )

        database_name = self.fetch_secret(
            "DATABASE_NAME_SECRET",
            "Database name"
        )

        database_user = self.fetch_secret(
            "DATABASE_USER_SECRET",
            "Database user"
        )

        database_password = self.fetch_secret(
            "DATABASE_PASSWORD_SECRET",
            "Database password"
        )

        return {
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
        }

    def fetch_cloud_tasks_config(self) -> Dict[str, Optional[str]]:
        """
        Fetch Cloud Tasks configuration from Secret Manager.

        This method is 100% identical across all services.

        Returns:
            Dictionary with Cloud Tasks configuration:
            - cloud_tasks_project_id: GCP project ID
            - cloud_tasks_location: GCP region/location
        """
        cloud_tasks_project_id = self.fetch_secret(
            "CLOUD_TASKS_PROJECT_ID",
            "Cloud Tasks project ID"
        )

        cloud_tasks_location = self.fetch_secret(
            "CLOUD_TASKS_LOCATION",
            "Cloud Tasks location/region"
        )

        return {
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location
        }

    def validate_critical_config(self, config: dict, critical_keys: list) -> None:
        """
        Validate that critical configuration keys are present.

        Args:
            config: Configuration dictionary
            critical_keys: List of keys that must be present
        """
        for key in critical_keys:
            if not config.get(key):
                print(f"⚠️ [CONFIG] Warning: {key} not available")

    @abstractmethod
    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for the service.

        Each service must implement this method with service-specific secrets.

        Returns:
            Dictionary containing all configuration values
        """
        pass
