#!/usr/bin/env python3
"""
Database Migration Executor for Threshold Payout and User Account Management
Executes SQL migrations against Google Cloud SQL PostgreSQL instance
"""

import sys
import os
from google.cloud.sql.connector import Connector
import pg8000
from google.cloud import secretmanager

def get_secret(secret_name):
    """Fetch secret from Google Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/telepay-459221/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8').strip()

def get_db_connection():
    """Create database connection using Cloud SQL Connector"""
    connector = Connector()

    conn = connector.connect(
        "telepay-459221:us-central1:telepaypsql",
        "pg8000",
        user=get_secret("DATABASE_USER_SECRET"),
        password=get_secret("DATABASE_PASSWORD_SECRET"),
        db=get_secret("DATABASE_NAME_SECRET"),
    )

    return conn

def execute_sql(conn, sql, description):
    """Execute SQL statement and return results"""
    print(f"\n🔧 {description}")
    print(f"{'='*60}")

    cursor = conn.cursor()
    try:
        cursor.execute(sql)

        # Check if this is a SELECT query
        if sql.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            if results:
                print(f"✅ Results ({len(results)} rows):")
                if columns:
                    print(f"  Columns: {', '.join(columns)}")
                for row in results[:10]:  # Limit to first 10 rows
                    print(f"  {row}")
                if len(results) > 10:
                    print(f"  ... ({len(results) - 10} more rows)")
            else:
                print("✅ No results (table/columns may not exist yet)")
        else:
            conn.commit()
            print(f"✅ Executed successfully")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        cursor.close()

def main():
    print("🚀 Starting Database Migration Execution")
    print(f"📍 Project: telepay-459221")
    print(f"📍 Instance: telepaypsql")
    print(f"📍 Database: telepaydb")

    # Connect to database
    print("\n📡 Connecting to database...")
    conn = get_db_connection()
    print("✅ Connected successfully")

    # ============================================================================
    # STEP 1: Check current schema
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 1: Checking Current Schema")
    print("="*80)

    execute_sql(conn, """
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
          AND column_name IN ('payout_strategy', 'payout_threshold_usd', 'payout_threshold_updated_at')
    """, "Checking for threshold payout columns in main_clients_database")

    execute_sql(conn, """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name IN ('payout_accumulation', 'payout_batches', 'registered_users')
    """, "Checking for new tables")

    # ============================================================================
    # STEP 2: Execute Threshold Payout Migration
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 2: Threshold Payout Migration")
    print("="*80)

    # Check if already migrated
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
          AND column_name = 'payout_strategy'
    """)
    threshold_migrated = cursor.fetchone()[0] > 0
    cursor.close()

    if threshold_migrated:
        print("⏭️  Threshold payout migration already applied - skipping")
    else:
        print("📝 Applying threshold payout migration...")

        # Add columns to main_clients_database
        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ADD COLUMN payout_strategy VARCHAR(20) DEFAULT 'instant',
            ADD COLUMN payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
            ADD COLUMN payout_threshold_updated_at TIMESTAMP
        """, "Adding payout strategy columns to main_clients_database")

        # Add constraint
        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ADD CONSTRAINT check_threshold_positive
            CHECK (payout_threshold_usd >= 0)
        """, "Adding threshold validation constraint")

        # Add index
        execute_sql(conn, """
            CREATE INDEX idx_payout_strategy ON main_clients_database(payout_strategy)
        """, "Creating index on payout_strategy")

        # Create payout_accumulation table
        execute_sql(conn, """
            CREATE TABLE payout_accumulation (
                id SERIAL PRIMARY KEY,
                client_id VARCHAR(14) NOT NULL,
                user_id BIGINT NOT NULL,
                subscription_id INTEGER,
                payment_amount_usd NUMERIC(10, 2) NOT NULL,
                payment_currency VARCHAR(10) NOT NULL,
                payment_timestamp TIMESTAMP NOT NULL,
                accumulated_amount_usdt NUMERIC(18, 8) NOT NULL,
                eth_to_usdt_rate NUMERIC(18, 8) NOT NULL,
                conversion_timestamp TIMESTAMP NOT NULL,
                conversion_tx_hash VARCHAR(100),
                client_wallet_address VARCHAR(200) NOT NULL,
                client_payout_currency VARCHAR(10) NOT NULL,
                client_payout_network VARCHAR(50) NOT NULL,
                is_paid_out BOOLEAN DEFAULT FALSE,
                payout_batch_id VARCHAR(50),
                paid_out_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """, "Creating payout_accumulation table")

        # Create indexes for payout_accumulation
        execute_sql(conn, """
            CREATE INDEX idx_client_pending ON payout_accumulation(client_id, is_paid_out)
        """, "Creating index on client_id + is_paid_out")

        execute_sql(conn, """
            CREATE INDEX idx_payout_batch ON payout_accumulation(payout_batch_id)
        """, "Creating index on payout_batch_id")

        execute_sql(conn, """
            CREATE INDEX idx_user ON payout_accumulation(user_id)
        """, "Creating index on user_id")

        execute_sql(conn, """
            CREATE INDEX idx_payment_timestamp ON payout_accumulation(payment_timestamp)
        """, "Creating index on payment_timestamp")

        # Create payout_batches table
        execute_sql(conn, """
            CREATE TABLE payout_batches (
                batch_id VARCHAR(50) PRIMARY KEY,
                client_id VARCHAR(14) NOT NULL,
                client_wallet_address VARCHAR(200) NOT NULL,
                client_payout_currency VARCHAR(10) NOT NULL,
                client_payout_network VARCHAR(50) NOT NULL,
                total_amount_usdt NUMERIC(18, 8) NOT NULL,
                total_payments_count INTEGER NOT NULL,
                payout_amount_crypto NUMERIC(18, 8),
                usdt_to_crypto_rate NUMERIC(18, 8),
                conversion_fee NUMERIC(18, 8),
                cn_api_id VARCHAR(100),
                cn_payin_address VARCHAR(200),
                tx_hash VARCHAR(100),
                tx_status VARCHAR(20),
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processing_started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """, "Creating payout_batches table")

        # Create indexes for payout_batches
        execute_sql(conn, """
            CREATE INDEX idx_client_batch ON payout_batches(client_id)
        """, "Creating index on client_id")

        execute_sql(conn, """
            CREATE INDEX idx_status_batch ON payout_batches(status)
        """, "Creating index on status")

        execute_sql(conn, """
            CREATE INDEX idx_created_batch ON payout_batches(created_at)
        """, "Creating index on created_at")

        print("\n✅ Threshold payout migration completed!")

    # ============================================================================
    # STEP 3: Execute User Accounts Migration
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 3: User Accounts Migration")
    print("="*80)

    # Check if already migrated
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'registered_users'
    """)
    users_migrated = cursor.fetchone()[0] > 0
    cursor.close()

    if users_migrated:
        print("⏭️  User accounts migration already applied - skipping")
    else:
        print("📝 Applying user accounts migration...")

        # Create registered_users table
        execute_sql(conn, """
            CREATE TABLE registered_users (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                email_verified BOOLEAN DEFAULT FALSE,
                verification_token VARCHAR(255),
                verification_token_expires TIMESTAMP,
                reset_token VARCHAR(255),
                reset_token_expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """, "Creating registered_users table")

        # Create indexes for registered_users
        execute_sql(conn, """
            CREATE INDEX idx_registered_users_username ON registered_users(username)
        """, "Creating index on username")

        execute_sql(conn, """
            CREATE INDEX idx_registered_users_email ON registered_users(email)
        """, "Creating index on email")

        execute_sql(conn, """
            CREATE INDEX idx_registered_users_verification_token ON registered_users(verification_token)
        """, "Creating index on verification_token")

        execute_sql(conn, """
            CREATE INDEX idx_registered_users_reset_token ON registered_users(reset_token)
        """, "Creating index on reset_token")

        # Insert legacy user
        execute_sql(conn, """
            INSERT INTO registered_users (
                user_id,
                username,
                email,
                password_hash,
                is_active,
                email_verified
            ) VALUES (
                '00000000-0000-0000-0000-000000000000',
                'legacy_system',
                'legacy@paygateprime.com',
                '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5qlcHxqCJzqZ2',
                FALSE,
                FALSE
            )
        """, "Creating legacy_system user")

        # Add columns to main_clients_database
        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ADD COLUMN client_id UUID
        """, "Adding client_id column to main_clients_database")

        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ADD COLUMN created_by VARCHAR(50)
        """, "Adding created_by column")

        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """, "Adding updated_at column")

        # Assign legacy user to existing channels
        execute_sql(conn, """
            UPDATE main_clients_database
            SET
                client_id = '00000000-0000-0000-0000-000000000000',
                created_by = 'legacy_migration',
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id IS NULL
        """, "Assigning all existing channels to legacy user")

        # Make client_id NOT NULL
        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ALTER COLUMN client_id SET NOT NULL
        """, "Making client_id NOT NULL")

        # Add foreign key constraint
        execute_sql(conn, """
            ALTER TABLE main_clients_database
            ADD CONSTRAINT fk_client_id
                FOREIGN KEY (client_id)
                REFERENCES registered_users(user_id)
                ON DELETE CASCADE
        """, "Adding foreign key constraint")

        # Create index
        execute_sql(conn, """
            CREATE INDEX idx_main_clients_client_id ON main_clients_database(client_id)
        """, "Creating index on client_id")

        print("\n✅ User accounts migration completed!")

    # ============================================================================
    # STEP 4: Verify migrations
    # ============================================================================
    print("\n" + "="*80)
    print("STEP 4: Verification")
    print("="*80)

    execute_sql(conn, """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
          AND column_name IN (
              'payout_strategy', 'payout_threshold_usd', 'payout_threshold_updated_at',
              'client_id', 'created_by', 'updated_at'
          )
        ORDER BY column_name
    """, "Verifying main_clients_database schema")

    execute_sql(conn, """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name IN ('payout_accumulation', 'payout_batches', 'registered_users')
        ORDER BY table_name
    """, "Verifying new tables exist")

    execute_sql(conn, """
        SELECT COUNT(*) as channel_count
        FROM main_clients_database
    """, "Counting total channels")

    execute_sql(conn, """
        SELECT
            COUNT(*) as channels_with_legacy_user,
            payout_strategy
        FROM main_clients_database
        WHERE client_id = '00000000-0000-0000-0000-000000000000'
        GROUP BY payout_strategy
    """, "Verifying legacy user assignment and payout strategy")

    print("\n" + "="*80)
    print("🎉 All migrations completed successfully!")
    print("="*80)

    # Close connection
    conn.close()
    print("\n✅ Database connection closed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
