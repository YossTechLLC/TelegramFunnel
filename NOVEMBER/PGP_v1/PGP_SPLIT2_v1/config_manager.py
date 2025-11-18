#!/usr/bin/env python
"""
Configuration Manager for PGP_SPLIT2_v1 (USDT→ETH Estimator Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_SPLIT2_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_SPLIT2_v1")

    def get_changenow_api_key(self) -> str:
        """
        Get ChangeNow API key (HOT-RELOADABLE).

        Returns:
            ChangeNow API key or None if not available
        """
        secret_path = self.build_secret_path("CHANGENOW_API_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "ChangeNow API key",
            cache_key="changenow_api_key"
        )

    def get_split1_response_queue(self) -> str:
        """
        Get PGP Split1 response queue name (HOT-RELOADABLE).

        Returns:
            PGP Split1 response queue name or None if not available
        """
        secret_path = self.build_secret_path("PGP_SPLIT1_RESPONSE_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP Split1 response queue",
            cache_key="split1_response_queue"
        )

    def get_split1_url(self) -> str:
        """
        Get PGP Split1 service URL (HOT-RELOADABLE).

        Returns:
            PGP Split1 service URL or None if not available
        """
        secret_path = self.build_secret_path("PGP_SPLIT1_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP Split1 service URL",
            cache_key="split1_url"
        )

    def get_batchprocessor_queue(self) -> str:
        """
        Get PGP BatchProcessor queue name (HOT-RELOADABLE).

        Returns:
            PGP BatchProcessor queue name or None if not available
        """
        secret_path = self.build_secret_path("PGP_BATCHPROCESSOR_QUEUE")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP BatchProcessor queue",
            cache_key="batchprocessor_queue"
        )

    def get_batchprocessor_url(self) -> str:
        """
        Get PGP BatchProcessor service URL (HOT-RELOADABLE).

        Returns:
            PGP BatchProcessor service URL or None if not available
        """
        secret_path = self.build_secret_path("PGP_BATCHPROCESSOR_URL")
        return self.fetch_secret_dynamic(
            secret_path,
            "PGP BatchProcessor service URL",
            cache_key="batchprocessor_url"
        )

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_SPLIT2_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_SPLIT2_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()
        db_config = self.fetch_database_config()

        # Fetch STATIC secrets (NEVER hot-reload)
        # SUCCESS_URL_SIGNING_KEY is used for token decryption - must remain static
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token encryption/decryption) - STATIC"
        )

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        # Note: Hot-reloadable secrets are NOT fetched here - they are fetched on-demand via getter methods
        config = {
            # STATIC Secrets (loaded once at startup)
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY (static): {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   Database configuration: {'✅' if all(db_config.values()) else '❌'}")
        print(f"   Hot-reloadable secrets: CHANGENOW_API_KEY, PGP_SPLIT1_*, PGP_BATCHPROCESSOR_*")

        return config
