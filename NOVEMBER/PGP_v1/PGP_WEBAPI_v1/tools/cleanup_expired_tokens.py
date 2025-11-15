#!/usr/bin/env python3
"""
🧹 Token Cleanup Script for PGP_WEBAPI_v1
Removes expired verification and password reset tokens from the database

This script should be run daily via Cloud Scheduler to clean up
expired tokens and maintain database hygiene.

Usage:
    python3 tools/cleanup_expired_tokens.py

Scheduling:
    Cloud Scheduler: 0 2 * * * (2 AM daily UTC)
"""
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config_manager import ConfigManager
from google.cloud.sql.connector import Connector
import sqlalchemy


class TokenCleanup:
    """Handles cleanup of expired tokens"""

    def __init__(self):
        """Initialize cleanup service"""
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.connector = Connector()

    def get_connection(self):
        """Get database connection"""
        conn = self.connector.connect(
            self.config['cloud_sql_connection_name'],
            'pg8000',
            user=self.config['database_user'],
            password=self.config['database_password'],
            db=self.config['database_name']
        )
        return conn

    def cleanup_expired_verification_tokens(self) -> int:
        """
        Clean up expired email verification tokens

        Returns:
            Number of tokens cleaned up
        """
        pool = sqlalchemy.create_engine(
            'postgresql+pg8000://',
            creator=self.get_connection,
        )

        cleanup_sql = """
            UPDATE registered_users
            SET verification_token = NULL,
                verification_token_expires = NULL
            WHERE verification_token IS NOT NULL
              AND verification_token_expires < NOW()
        """

        with pool.connect() as conn:
            result = conn.execute(sqlalchemy.text(cleanup_sql))
            conn.commit()
            count = result.rowcount

        return count

    def cleanup_expired_reset_tokens(self) -> int:
        """
        Clean up expired password reset tokens

        Returns:
            Number of tokens cleaned up
        """
        pool = sqlalchemy.create_engine(
            'postgresql+pg8000://',
            creator=self.get_connection,
        )

        cleanup_sql = """
            UPDATE registered_users
            SET reset_token = NULL,
                reset_token_expires = NULL
            WHERE reset_token IS NOT NULL
              AND reset_token_expires < NOW()
        """

        with pool.connect() as conn:
            result = conn.execute(sqlalchemy.text(cleanup_sql))
            conn.commit()
            count = result.rowcount

        return count

    def get_token_statistics(self) -> dict:
        """
        Get statistics about token usage

        Returns:
            Dictionary with token statistics
        """
        pool = sqlalchemy.create_engine(
            'postgresql+pg8000://',
            creator=self.get_connection,
        )

        stats_sql = """
            SELECT
                COUNT(*) FILTER (WHERE verification_token IS NOT NULL) as active_verification_tokens,
                COUNT(*) FILTER (WHERE reset_token IS NOT NULL) as active_reset_tokens,
                COUNT(*) FILTER (WHERE email_verified = FALSE) as unverified_users,
                COUNT(*) FILTER (WHERE email_verified = TRUE) as verified_users
            FROM registered_users
        """

        with pool.connect() as conn:
            result = conn.execute(sqlalchemy.text(stats_sql))
            row = result.fetchone()

        return {
            'active_verification_tokens': row[0],
            'active_reset_tokens': row[1],
            'unverified_users': row[2],
            'verified_users': row[3]
        }

    def run_cleanup(self):
        """
        Run complete cleanup process

        Returns:
            Dictionary with cleanup results
        """
        print("🧹 Starting token cleanup process...")
        print(f"⏰ Timestamp: {datetime.utcnow().isoformat()}Z")
        print("")

        # Get statistics before cleanup
        print("📊 Token statistics before cleanup:")
        stats_before = self.get_token_statistics()
        print(f"  • Active verification tokens: {stats_before['active_verification_tokens']}")
        print(f"  • Active reset tokens: {stats_before['active_reset_tokens']}")
        print(f"  • Unverified users: {stats_before['unverified_users']}")
        print(f"  • Verified users: {stats_before['verified_users']}")
        print("")

        # Cleanup expired verification tokens
        print("🔍 Cleaning up expired verification tokens...")
        verification_count = self.cleanup_expired_verification_tokens()
        print(f"  ✅ Cleaned up {verification_count} expired verification token(s)")

        # Cleanup expired reset tokens
        print("🔍 Cleaning up expired password reset tokens...")
        reset_count = self.cleanup_expired_reset_tokens()
        print(f"  ✅ Cleaned up {reset_count} expired reset token(s)")

        # Get statistics after cleanup
        print("")
        print("📊 Token statistics after cleanup:")
        stats_after = self.get_token_statistics()
        print(f"  • Active verification tokens: {stats_after['active_verification_tokens']}")
        print(f"  • Active reset tokens: {stats_after['active_reset_tokens']}")
        print(f"  • Unverified users: {stats_after['unverified_users']}")
        print(f"  • Verified users: {stats_after['verified_users']}")
        print("")

        # Summary
        total_cleaned = verification_count + reset_count
        print(f"✅ Cleanup complete! Total tokens cleaned: {total_cleaned}")

        # Close connector
        self.connector.close()

        return {
            'verification_tokens_cleaned': verification_count,
            'reset_tokens_cleaned': reset_count,
            'total_cleaned': total_cleaned,
            'stats_before': stats_before,
            'stats_after': stats_after,
            'timestamp': datetime.utcnow().isoformat()
        }


def main():
    """Main entry point"""
    try:
        cleanup = TokenCleanup()
        results = cleanup.run_cleanup()

        # Exit with success
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
