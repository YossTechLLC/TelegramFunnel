#!/usr/bin/env python
"""
Configuration Manager for PGP_BATCHPROCESSOR_v1 (Batch Payout Processor Service).
Handles fetching configuration values from Google Cloud Secret Manager.
"""
from PGP_COMMON.config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Manages configuration and secrets for the PGP_BATCHPROCESSOR_v1 service.
    Inherits common methods from BaseConfigManager.
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        super().__init__(service_name="PGP_BATCHPROCESSOR_v1")

    def initialize_config(self) -> dict:
        """
        Initialize and return all configuration values for PGP_BATCHPROCESSOR_v1.

        Returns:
            Dictionary containing all configuration values
        """
        print(f"⚙️ [CONFIG] Initializing PGP_BATCHPROCESSOR_v1 configuration")

        # Use base methods to fetch common configurations
        ct_config = self.fetch_cloud_tasks_config()
        db_config = self.fetch_database_config()

        # Fetch signing keys
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key (for token encryption)"
        )

        tps_hostpay_signing_key = self.fetch_secret(
            "TPS_HOSTPAY_SIGNING_KEY",
            "TPS-HostPay signing key (for batch payout tokens)"
        )

        # PGP Split1 configuration (for batch payout execution)
        pgp_split1_batch_queue = self.fetch_secret(
            "PGP_SPLIT1_BATCH_QUEUE",
            "PGP Split1 batch queue name"
        )

        pgp_split1_url = self.fetch_secret(
            "PGP_SPLIT1_URL",
            "PGP Split1 service URL"
        )

        # Validate critical configurations
        if not success_url_signing_key or not tps_hostpay_signing_key:
            print(f"⚠️ [CONFIG] Warning: Signing keys not available")
        if not ct_config['cloud_tasks_project_id'] or not ct_config['cloud_tasks_location']:
            print(f"⚠️ [CONFIG] Warning: Cloud Tasks configuration incomplete")

        # Combine all configurations
        config = {
            # Signing keys
            'success_url_signing_key': success_url_signing_key,
            'tps_hostpay_signing_key': tps_hostpay_signing_key,

            # Cloud Tasks configuration (from base method)
            **ct_config,

            # Service-specific queues and URLs
            'pgp_split1_batch_queue': pgp_split1_batch_queue,
            'pgp_split1_url': pgp_split1_url,

            # Database configuration (from base method)
            **db_config
        }

        # Log configuration status
        print(f"📊 [CONFIG] Configuration status:")
        print(f"   SUCCESS_URL_SIGNING_KEY: {'✅' if config['success_url_signing_key'] else '❌'}")
        print(f"   TPS_HOSTPAY_SIGNING_KEY: {'✅' if config['tps_hostpay_signing_key'] else '❌'}")
        print(f"   Cloud Tasks Project: {'✅' if config['cloud_tasks_project_id'] else '❌'}")
        print(f"   Cloud Tasks Location: {'✅' if config['cloud_tasks_location'] else '❌'}")
        print(f"   PGP Split1 Batch Queue: {'✅' if config['pgp_split1_batch_queue'] else '❌'}")
        print(f"   PGP Split1 URL: {'✅' if config['pgp_split1_url'] else '❌'}")
        print(f"   CLOUD_SQL_CONNECTION_NAME: {'✅' if config['instance_connection_name'] else '❌'}")
        print(f"   DATABASE_NAME_SECRET: {'✅' if config['db_name'] else '❌'}")
        print(f"   DATABASE_USER_SECRET: {'✅' if config['db_user'] else '❌'}")
        print(f"   DATABASE_PASSWORD_SECRET: {'✅' if config['db_password'] else '❌'}")

        return config
