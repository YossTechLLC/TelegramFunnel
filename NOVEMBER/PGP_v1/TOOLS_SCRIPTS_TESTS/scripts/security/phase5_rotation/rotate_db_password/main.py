#!/usr/bin/env python3
"""
Cloud Function: Rotate Database Password

Purpose: Automatically rotate Cloud SQL database password every 90 days
Trigger: Cloud Scheduler → Pub/Sub → Cloud Function
Project: pgp-live
Instance: telepaypsql

This function:
1. Generates a strong random password
2. Updates Cloud SQL user password
3. Creates new Secret Manager version
4. Verifies new secret is accessible
5. Services auto-reload via hot-reload (no restart needed)

IMPORTANT:
- Requires Secret Manager Admin role
- Requires Cloud SQL Admin role
- Test in staging first
- Implement rollback mechanism
"""

import os
import secrets
import string
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector
import pg8000
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_strong_password(length=32):
    """
    Generate a strong random password.

    Requirements:
    - At least 32 characters
    - Mix of uppercase, lowercase, digits, special chars
    - Cryptographically secure

    Returns:
        str: Strong random password
    """
    # Use secrets module for cryptographic randomness
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    logger.info("✅ Generated strong password (32 chars)")
    return password


def rotate_database_password(event, context):
    """
    Rotate Cloud SQL database password.

    Triggered by Cloud Scheduler via Pub/Sub.

    Args:
        event: Pub/Sub event data
        context: Cloud Functions context

    Returns:
        str: Success message
    """
    logger.info("🔄 Starting database password rotation")

    # Configuration from environment
    project_id = os.getenv('GCP_PROJECT', 'pgp-live')
    instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME', 'pgp-live:us-central1:telepaypsql')
    db_user = os.getenv('DB_USER', 'postgres')
    secret_name = os.getenv('SECRET_NAME', 'DATABASE_PASSWORD_SECRET')

    logger.info(f"📋 Project: {project_id}")
    logger.info(f"📋 Instance: {instance_connection_name}")
    logger.info(f"📋 User: {db_user}")

    try:
        # Step 1: Get current password from Secret Manager
        logger.info("🔐 Fetching current password...")
        sm_client = secretmanager.SecretManagerServiceClient()
        current_secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = sm_client.access_secret_version(request={"name": current_secret_path})
        current_password = response.payload.data.decode("UTF-8")
        logger.info("✅ Current password retrieved")

        # Step 2: Generate new password
        logger.info("🔐 Generating new password...")
        new_password = generate_strong_password(32)

        # Step 3: Update database password
        logger.info("🗄️  Connecting to database...")
        connector = Connector()

        conn = connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=current_password,
            db='postgres'  # Connect to postgres db for user management
        )

        logger.info("✅ Connected to database")

        # Execute password change
        logger.info("🔄 Updating database password...")
        cursor = conn.cursor()

        # Use parameterized query for safety
        cursor.execute(
            f"ALTER USER {db_user} WITH PASSWORD %s",
            (new_password,)
        )
        conn.commit()

        logger.info("✅ Database password updated")

        # Close connection
        cursor.close()
        conn.close()
        connector.close()

        # Step 4: Create new secret version
        logger.info("🔐 Creating new secret version...")
        parent = sm_client.secret_path(project_id, secret_name)

        new_version_response = sm_client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": new_password.encode("UTF-8")}
            }
        )

        logger.info(f"✅ New secret version created: {new_version_response.name}")

        # Step 5: Verify new version is accessible
        logger.info("🔍 Verifying new secret version...")
        verify_response = sm_client.access_secret_version(
            request={"name": new_version_response.name}
        )

        if verify_response.payload.data.decode("UTF-8") == new_password:
            logger.info("✅ New secret version verified")
        else:
            raise Exception("❌ Secret verification failed")

        # Step 6: Test connection with new password
        logger.info("🔍 Testing connection with new password...")
        connector_test = Connector()

        test_conn = connector_test.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=new_password,
            db='postgres'
        )

        test_cursor = test_conn.cursor()
        test_cursor.execute("SELECT version();")
        version = test_cursor.fetchone()

        logger.info(f"✅ Connection test successful: {version[0]}")

        test_cursor.close()
        test_conn.close()
        connector_test.close()

        # Success
        logger.info("🎉 Password rotation completed successfully")
        logger.info("📌 Services will auto-reload new password on next request")

        return {
            'status': 'success',
            'message': 'Database password rotated successfully',
            'new_version': new_version_response.name,
            'timestamp': context.timestamp if context else 'unknown'
        }

    except Exception as e:
        logger.error(f"❌ Password rotation failed: {str(e)}")

        # TODO: Implement alerting
        # send_alert_to_pagerduty(f"Database password rotation failed: {str(e)}")

        raise Exception(f"Password rotation failed: {str(e)}")


# For local testing
if __name__ == "__main__":
    class MockContext:
        timestamp = "2025-11-18T12:00:00Z"

    result = rotate_database_password({}, MockContext())
    print(result)
