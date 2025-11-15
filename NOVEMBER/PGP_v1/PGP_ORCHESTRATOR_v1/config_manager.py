#!/usr/bin/env python
"""
Configuration Manager for PGP_ORCHESTRATOR_v1 (Payment Processor Service).
Handles fetching configuration values from Google Cloud Secret Manager and environment variables.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_ORCHESTRATOR_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_ORCHESTRATOR_v1")

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_ORCHESTRATOR_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_ORCHESTRATOR_v1 configuration")

        # Fetch secrets from Secret Manager (using inherited fetch_secret method)
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token verification and encryption)"
        )

        # Use base method to fetch Cloud Tasks configuration
        ct_config = self.fetch_cloud_tasks_config()

        # Service-specific queue and URL configurations
        pgp_invite_queue = self.fetch_secret(
            "PGP_INVITE_QUEUE",
            "PGP Invite queue name"
        )

        pgp_invite_url = self.fetch_secret(
            "PGP_INVITE_URL",
            "PGP Invite service URL"
        )

        pgp_split1_queue = self.fetch_secret(
            "PGP_SPLIT1_QUEUE",
            "PGP Split1 queue name"
        )

        pgp_split1_url = self.fetch_secret(
            "PGP_SPLIT1_URL",
            "PGP Split1 service URL"
        )

        # PGP Accumulator configuration (for threshold payout)
        pgp_accumulator_queue = self.fetch_secret(
            "PGP_ACCUMULATOR_QUEUE",
            "PGP Accumulator queue name"
        )

        pgp_accumulator_url = self.fetch_secret(
            "PGP_ACCUMULATOR_URL",
            "PGP Accumulator service URL"
        )

        # Use base method to fetch database configuration
        db_config = self.fetch_database_config()

        # Validate critical configurations
        if not success_url_signing_key:
            print(f"⚠️ [CONFIG] Warning: SUCCESS_URL_SIGNING_KEY not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        config = {
            # Secrets
            'success_url_signing_key': success_url_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Service-specific configurations
            'pgp_invite_queue': pgp_invite_queue,
            'pgp_invite_url': pgp_invite_url,
            'pgp_split1_queue': pgp_split1_queue,
            'pgp_split1_url': pgp_split1_url,
            'pgp_accumulator_queue': pgp_accumulator_queue,
            'pgp_accumulator_url': pgp_accumulator_url,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP Invite Queue: {'✅' if config['pgp_invite_queue'] else '❌'}")
        print(f"   PGP Invite URL: {'✅' if config['pgp_invite_url'] else '❌'}")
        print(f"   PGP Split1 Queue: {'✅' if config['pgp_split1_queue'] else '❌'}")
        print(f"   PGP Split1 URL: {'✅' if config['pgp_split1_url'] else '❌'}")
        print(f"   PGP Accumulator Queue: {'✅' if config['pgp_accumulator_queue'] else '❌'}")
        print(f"   PGP Accumulator URL: {'✅' if config['pgp_accumulator_url'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
