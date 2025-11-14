#!/usr/bin/env python3
"""
Execute message tracking migration for broadcast_manager table
Date: 2025-01-14
Related: LIVETIME_BROADCAST_ONLY_CHECKLIST.md Phase 1
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "TelePay10-26"))

from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def get_connection():
    """Get database connection using Cloud SQL Connector."""
    connector = Connector()

    def getconn():
        conn = connector.connect(
            instance_connection_string="telepay-459221:us-central1:telepaypsql",
            driver="pg8000",
            user="postgres",
            password=os.environ.get("DB_PASSWORD", "Chigdabeast123$"),
            db="client_table"
        )
        return conn

    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return engine, connector


def execute_migration():
    """Execute the message tracking migration."""
    logger.info("🚀 Starting message tracking migration...")

    engine, connector = None, None

    try:
        engine, connector = get_connection()

        with engine.connect() as conn:
            # Check if columns already exist
            check_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='broadcast_manager'
                AND column_name IN ('last_open_message_id', 'last_closed_message_id',
                                   'last_open_message_sent_at', 'last_closed_message_sent_at')
            """)

            existing = conn.execute(check_query).fetchall()
            existing_cols = [row[0] for row in existing]

            if len(existing_cols) == 4:
                logger.info("⚠️ All columns already exist - migration already applied")
                return True

            if len(existing_cols) > 0:
                logger.warning(f"⚠️ Some columns already exist: {existing_cols}")
                logger.info("🔧 Attempting to add missing columns...")

            # Add columns
            logger.info("📝 Adding message tracking columns...")

            migration_sql = """
                ALTER TABLE broadcast_manager
                ADD COLUMN IF NOT EXISTS last_open_message_id BIGINT DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS last_closed_message_id BIGINT DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS last_open_message_sent_at TIMESTAMP DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS last_closed_message_sent_at TIMESTAMP DEFAULT NULL;
            """

            conn.execute(text(migration_sql))
            conn.commit()
            logger.info("✅ Columns added successfully")

            # Add indexes
            logger.info("📝 Creating indexes...")

            index_sql_1 = """
                CREATE INDEX IF NOT EXISTS idx_broadcast_manager_open_message
                ON broadcast_manager(last_open_message_id)
                WHERE last_open_message_id IS NOT NULL;
            """

            index_sql_2 = """
                CREATE INDEX IF NOT EXISTS idx_broadcast_manager_closed_message
                ON broadcast_manager(last_closed_message_id)
                WHERE last_closed_message_id IS NOT NULL;
            """

            conn.execute(text(index_sql_1))
            conn.execute(text(index_sql_2))
            conn.commit()
            logger.info("✅ Indexes created successfully")

            # Add comments
            logger.info("📝 Adding column comments...")

            comment_sql = """
                COMMENT ON COLUMN broadcast_manager.last_open_message_id IS
                'Telegram message ID of last subscription tier message sent to open channel';

                COMMENT ON COLUMN broadcast_manager.last_closed_message_id IS
                'Telegram message ID of last donation button message sent to closed channel';

                COMMENT ON COLUMN broadcast_manager.last_open_message_sent_at IS
                'Timestamp when last open channel message was sent';

                COMMENT ON COLUMN broadcast_manager.last_closed_message_sent_at IS
                'Timestamp when last closed channel message was sent';
            """

            conn.execute(text(comment_sql))
            conn.commit()
            logger.info("✅ Comments added successfully")

            # Verify migration
            logger.info("🔍 Verifying migration...")

            verify_query = text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name='broadcast_manager'
                AND column_name LIKE 'last_%_message_%'
                ORDER BY column_name
            """)

            results = conn.execute(verify_query).fetchall()

            logger.info("\n📊 Column details:")
            logger.info("-" * 60)
            logger.info(f"{'Column Name':<35} {'Type':<15} {'Nullable'}")
            logger.info("-" * 60)

            for row in results:
                logger.info(f"{row[0]:<35} {row[1]:<15} {row[2]}")

            logger.info("-" * 60)
            logger.info(f"\n✅ Migration complete! {len(results)} columns verified")

            if len(results) != 4:
                logger.error(f"❌ Expected 4 columns but found {len(results)}")
                return False

            return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return False

    finally:
        if connector:
            connector.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("MESSAGE TRACKING MIGRATION TOOL")
    logger.info("=" * 60)
    logger.info("")

    success = execute_migration()

    logger.info("")
    if success:
        logger.info("✅ Migration executed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed!")
        sys.exit(1)
