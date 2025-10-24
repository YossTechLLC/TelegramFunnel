#!/usr/bin/env python
"""
Configuration Manager for GCRegister10-5 Channel Registration Service.
Handles fetching configuration values from Google Cloud Secret Manager.
"""
import os
from google.cloud import secretmanager
from typing import Optional

# LIST OF ENVIRONMENT VARIABLES
# DATABASE_NAME_SECRET: Path to database name in Secret Manager
# DATABASE_USER_SECRET: Path to database user in Secret Manager
# DATABASE_PASSWORD_SECRET: Path to database password in Secret Manager
# DATABASE_SECRET_KEY: Path to Flask secret key in Secret Manager
# CLOUD_SQL_CONNECTION_NAME: Path to Cloud SQL instance connection name in Secret Manager

class ConfigManager:
    """
    Manages configuration and secrets for the GCRegister10-5 service.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.db_name = None
        self.db_user = None
        self.db_password = None
        self.secret_key = None
        self.cloud_sql_connection_name = None

    def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret from Google Cloud Secret Manager.

        Args:
            secret_name_env: Environment variable containing the secret path
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            secret_path = os.getenv(secret_name_env)
            if not secret_path:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set")
                return None

            print(f"🔐 [CONFIG] Fetching {description or secret_name_env}")
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")

            print(f"✅ [CONFIG] Successfully fetched {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error fetching {description or secret_name_env}: {e}")
            return None

    def fetch_database_name(self) -> Optional[str]:
        """
        Fetch the database name from Secret Manager.

        Returns:
            Database name or None if failed
        """
        return self.fetch_secret("DATABASE_NAME_SECRET", "database name")

    def fetch_database_user(self) -> Optional[str]:
        """
        Fetch the database user from Secret Manager.

        Returns:
            Database user or None if failed
        """
        return self.fetch_secret("DATABASE_USER_SECRET", "database user")

    def fetch_database_password(self) -> Optional[str]:
        """
        Fetch the database password from Secret Manager.

        Returns:
            Database password or None if failed
        """
        return self.fetch_secret("DATABASE_PASSWORD_SECRET", "database password")

    def get_secret_key(self) -> str:
        """
        Get the Flask secret key from Secret Manager.

        Returns:
            Flask secret key
        """
        return self.fetch_secret("DATABASE_SECRET_KEY", "Flask secret key")

    def get_cloud_sql_connection_name(self) -> Optional[str]:
        """
        Get the Cloud SQL instance connection name from Secret Manager.

        Returns:
            Instance connection name (e.g., project:region:instance)
        """
        return self.fetch_secret(
            "CLOUD_SQL_CONNECTION_NAME",
            "Cloud SQL connection name"
        )

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing GCRegister10-5 configuration")

        # Fetch all secrets and environment variables
        self.db_name = self.fetch_database_name()
        self.db_user = self.fetch_database_user()
        self.db_password = self.fetch_database_password()
        self.secret_key = self.get_secret_key()
        self.cloud_sql_connection_name = self.get_cloud_sql_connection_name()

        # Validate critical configurations
        missing_configs = []
        if not self.db_name:
            missing_configs.append("Database Name")
        if not self.db_user:
            missing_configs.append("Database User")
        if not self.db_password:
            missing_configs.append("Database Password")
        if not self.cloud_sql_connection_name:
            missing_configs.append("Cloud SQL Connection Name")

        if missing_configs:
            print(f"❌ [CONFIG] Missing critical configuration: {', '.join(missing_configs)}")

        config = {
            'db_name': self.db_name,
            'db_user': self.db_user,
            'db_password': self.db_password,
            'secret_key': self.secret_key,
            'instance_connection_name': self.cloud_sql_connection_name
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   Cloud SQL Instance: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   Database Name: {'✅' if config['db_name'] else '❌'}")
        print(f"   Database User: {'✅' if config['db_user'] else '❌'}")
        print(f"   Database Password: {'✅' if config['db_password'] else '❌'}")
        print(f"   Secret Key: {'✅' if config['secret_key'] else '❌'}")

        return config

    def get_config(self) -> dict:
        """
        Get current configuration values.

        Returns:
            Dictionary containing current configuration
        """
        return {
            'db_name': self.db_name,
            'db_user': self.db_user,
            'db_password': self.db_password,
            'secret_key': self.secret_key,
            'instance_connection_name': self.cloud_sql_connection_name
        }
