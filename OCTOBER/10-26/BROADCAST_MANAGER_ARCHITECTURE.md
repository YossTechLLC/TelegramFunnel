# Broadcast Manager Architecture
**Version:** 1.0
**Date:** 2025-11-11
**Status:** Architecture Design
**Author:** Claude Code

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Architecture Overview](#architecture-overview)
4. [Database Schema](#database-schema)
5. [Modular Component Design](#modular-component-design)
6. [Google Cloud Infrastructure](#google-cloud-infrastructure)
7. [Configuration Management](#configuration-management)
8. [API Endpoints](#api-endpoints)
9. [Scheduling Logic](#scheduling-logic)
10. [Security Considerations](#security-considerations)
11. [Error Handling & Monitoring](#error-handling--monitoring)
12. [Migration Strategy](#migration-strategy)
13. [Testing Strategy](#testing-strategy)
14. [Deployment Guide](#deployment-guide)

---

## Executive Summary

### Problem Statement
The current broadcast manager (`broadcast_manager.py`) runs synchronously whenever `telepay10-26.py` starts locally, sending subscription tier messages to `open_channel_id` and donation messages to `closed_channel_id` channels. This approach:
- ❌ Doesn't track when messages were last sent
- ❌ Lacks scheduling capabilities for automated resends
- ❌ Cannot be triggered on-demand from the website
- ❌ Will not scale when deployed as a webhook service

### Solution Overview
Implement a **scheduled broadcast management system** that:
- ✅ Tracks broadcast history per channel pair in a dedicated database table
- ✅ Uses Google Cloud Scheduler for automated periodic broadcasts (24-hour interval)
- ✅ Allows clients to manually trigger rebroadcasts via the website (rate-limited to 5 minutes)
- ✅ Configures intervals via Google Cloud Secret Manager (no redeployment needed)
- ✅ Follows modular architecture principles for maintainability

### Key Features
1. **Automated Scheduling**: Cron-based broadcasts every 24 hours
2. **Manual Triggers**: Website button to resend messages (rate-limited)
3. **Dynamic Configuration**: Intervals stored in Secret Manager
4. **Broadcast Tracking**: Database table tracks last/next send times
5. **Modular Design**: Separate components for scheduling, execution, tracking, and API

---

## Current State Analysis

### Existing Implementation

**File:** `TelePay10-26/broadcast_manager.py`

**Current Behavior:**
```python
# Called during app initialization (app_initializer.py:127-129)
self.broadcast_manager.fetch_open_channel_list()
self.broadcast_manager.broadcast_hash_links()
```

**What It Does:**
1. Fetches all `open_channel_id` from `main_clients_database`
2. Sends subscription tier buttons to each open channel
3. Runs **once** at application startup
4. No tracking of send times or scheduling

**Limitations:**
- ❌ No persistence of broadcast state
- ❌ No way to prevent duplicate broadcasts on restart
- ❌ No scheduling mechanism
- ❌ No manual trigger capability
- ❌ Tightly coupled to application startup

### Existing Database Schema

**Table:** `main_clients_database`

**Relevant Columns:**
```sql
- user_id (references registered website user)
- open_channel_id (TEXT)
- open_channel_title (TEXT)
- open_channel_description (TEXT)
- closed_channel_id (TEXT)
- closed_channel_title (TEXT)
- closed_channel_description (TEXT)
- closed_channel_donation_message (TEXT)
- sub_1_price, sub_1_time (subscription tiers)
- sub_2_price, sub_2_time
- sub_3_price, sub_3_time
- notification_status (BOOLEAN)
- notification_id (BIGINT)
```

**Missing:**
- ❌ No broadcast tracking columns
- ❌ No last_sent timestamp
- ❌ No next_send timestamp
- ❌ No broadcast status flags

---

## Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Google Cloud Scheduler                        │
│                  (Cron: "0 0 * * *" - Daily)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP POST
                             │ /api/broadcast/execute
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              GCBroadcastScheduler-10-26 (Cloud Run)             │
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │ BroadcastExecutor│────│ BroadcastTracker │                  │
│  │  (Send Messages) │    │  (Update DB)     │                  │
│  └──────────────────┘    └──────────────────┘                  │
│            │                       │                             │
│            │                       │                             │
│            ▼                       ▼                             │
│  ┌─────────────────────────────────────────────┐               │
│  │         DatabaseManager                      │               │
│  │  - broadcast_manager table                   │               │
│  │  - main_clients_database table               │               │
│  └─────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │ HTTP POST
                             │ /api/broadcast/trigger
                             │ (Manual trigger from website)
┌─────────────────────────────────────────────────────────────────┐
│                  GCRegisterWeb-10-26                             │
│                   (Client Dashboard)                             │
│                                                                  │
│  ┌──────────────────────────────────────────┐                  │
│  │  "Resend Messages" Button                │                  │
│  │  - Rate limited (5 min interval)         │                  │
│  │  - Per-channel pair selection            │                  │
│  └──────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Google Cloud Secret Manager                         │
│  - BROADCAST_AUTO_INTERVAL (24 hours)                           │
│  - BROADCAST_MANUAL_INTERVAL (5 minutes)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

**Automated Broadcast (Daily):**
```
1. Cloud Scheduler triggers → GCBroadcastScheduler webhook
2. BroadcastScheduler.check_due_broadcasts()
   └── Query broadcast_manager table WHERE next_send_time <= NOW()
3. BroadcastExecutor.send_broadcasts()
   ├── Send subscription messages to open_channel_id
   ├── Send donation messages to closed_channel_id
   └── Handle errors gracefully
4. BroadcastTracker.update_broadcast_status()
   ├── Update last_sent_time = NOW()
   ├── Update next_send_time = NOW() + BROADCAST_AUTO_INTERVAL
   └── Update broadcast_status = 'completed'
```

**Manual Broadcast (Website Trigger):**
```
1. Client clicks "Resend Messages" on dashboard
2. Frontend → POST /api/broadcast/trigger
   └── Headers: Authorization (JWT token)
   └── Body: { "channel_pair_id": "uuid" }
3. BroadcastWebAPI.validate_request()
   ├── Authenticate user
   ├── Verify channel ownership
   └── Check rate limit (last_manual_trigger + 5min < NOW())
4. BroadcastScheduler.queue_manual_broadcast()
   └── Update next_send_time = NOW() (mark for immediate send)
5. BroadcastExecutor.send_broadcasts()
   └── Execute immediately or queue for next cron run
6. BroadcastTracker.update_manual_trigger_time()
   └── Update last_manual_trigger_time = NOW()
```

---

## Database Schema

### New Table: `broadcast_manager`

**Purpose:** Track broadcast history and scheduling state for each channel pair

```sql
-- Create broadcast_manager table
-- Purpose: Track broadcast scheduling and history for open/closed channel pairs
-- Version: 1.0
-- Date: 2025-11-11

CREATE TABLE IF NOT EXISTS broadcast_manager (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Keys & Relationships
    user_id INTEGER NOT NULL,
    open_channel_id TEXT NOT NULL,
    closed_channel_id TEXT NOT NULL,

    -- Broadcast Scheduling
    last_sent_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    next_send_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    broadcast_status VARCHAR(20) DEFAULT 'pending' NOT NULL,
        -- Values: 'pending', 'in_progress', 'completed', 'failed', 'skipped'

    -- Manual Trigger Tracking
    last_manual_trigger_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    manual_trigger_count INTEGER DEFAULT 0,

    -- Broadcast Statistics
    total_broadcasts INTEGER DEFAULT 0,
    successful_broadcasts INTEGER DEFAULT 0,
    failed_broadcasts INTEGER DEFAULT 0,

    -- Error Tracking
    last_error_message TEXT DEFAULT NULL,
    last_error_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    consecutive_failures INTEGER DEFAULT 0,

    -- Metadata
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT fk_broadcast_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_broadcast_channels
        FOREIGN KEY (open_channel_id)
        REFERENCES main_clients_database(open_channel_id)
        ON DELETE CASCADE,

    CONSTRAINT unique_channel_pair
        UNIQUE (open_channel_id, closed_channel_id),

    CONSTRAINT valid_broadcast_status
        CHECK (broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped'))
);

-- Create indexes for performance
CREATE INDEX idx_broadcast_next_send ON broadcast_manager(next_send_time) WHERE is_active = true;
CREATE INDEX idx_broadcast_user ON broadcast_manager(user_id);
CREATE INDEX idx_broadcast_status ON broadcast_manager(broadcast_status) WHERE is_active = true;
CREATE INDEX idx_broadcast_open_channel ON broadcast_manager(open_channel_id);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_broadcast_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_broadcast_updated_at
    BEFORE UPDATE ON broadcast_manager
    FOR EACH ROW
    EXECUTE FUNCTION update_broadcast_updated_at();

-- Add comments for documentation
COMMENT ON TABLE broadcast_manager IS
'Tracks broadcast scheduling and history for Telegram channel message broadcasts';

COMMENT ON COLUMN broadcast_manager.id IS
'Unique identifier for the broadcast schedule entry';

COMMENT ON COLUMN broadcast_manager.user_id IS
'Foreign key to users table - identifies the channel owner';

COMMENT ON COLUMN broadcast_manager.open_channel_id IS
'Telegram channel ID for subscription tier messages';

COMMENT ON COLUMN broadcast_manager.closed_channel_id IS
'Telegram channel ID for donation messages';

COMMENT ON COLUMN broadcast_manager.last_sent_time IS
'Timestamp of the last successful broadcast to this channel pair';

COMMENT ON COLUMN broadcast_manager.next_send_time IS
'Timestamp when the next broadcast should be sent. Set to NOW() for immediate send.';

COMMENT ON COLUMN broadcast_manager.broadcast_status IS
'Current status: pending (waiting), in_progress (sending), completed (success), failed (error), skipped (disabled)';

COMMENT ON COLUMN broadcast_manager.last_manual_trigger_time IS
'Timestamp of the last manual trigger from website (for rate limiting)';

COMMENT ON COLUMN broadcast_manager.manual_trigger_count IS
'Total number of manual triggers by the user';

COMMENT ON COLUMN broadcast_manager.consecutive_failures IS
'Number of consecutive failed broadcasts (resets to 0 on success)';

COMMENT ON COLUMN broadcast_manager.is_active IS
'Enable/disable broadcasts for this channel pair. Default true.';
```

### Migration Script

**File:** `TOOLS_SCRIPTS_TESTS/scripts/create_broadcast_manager_table.sql`

The script above creates the table with all necessary constraints, indexes, and triggers.

### Rollback Script

**File:** `TOOLS_SCRIPTS_TESTS/scripts/rollback_broadcast_manager_table.sql`

```sql
-- Rollback broadcast_manager table creation
-- Purpose: Remove broadcast_manager table and dependencies
-- Version: 1.0
-- Date: 2025-11-11

BEGIN;

-- Drop trigger first
DROP TRIGGER IF EXISTS trigger_broadcast_updated_at ON broadcast_manager;
DROP FUNCTION IF EXISTS update_broadcast_updated_at();

-- Drop indexes
DROP INDEX IF EXISTS idx_broadcast_next_send;
DROP INDEX IF EXISTS idx_broadcast_user;
DROP INDEX IF EXISTS idx_broadcast_status;
DROP INDEX IF EXISTS idx_broadcast_open_channel;

-- Drop table
DROP TABLE IF EXISTS broadcast_manager CASCADE;

-- Verify table is dropped
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'broadcast_manager'
    ) THEN
        RAISE EXCEPTION 'Failed to drop broadcast_manager table';
    END IF;

    RAISE NOTICE '✅ Successfully rolled back broadcast_manager table';
END $$;

COMMIT;
```

### Initial Data Population

**File:** `TOOLS_SCRIPTS_TESTS/tools/populate_broadcast_manager.py`

```python
#!/usr/bin/env python
"""
Populate broadcast_manager table with existing channel pairs from main_clients_database.
This script should be run once after creating the broadcast_manager table.
"""

import sys
import os
from datetime import datetime, timedelta
from google.cloud import secretmanager
import psycopg2

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def fetch_database_credentials():
    """Fetch database credentials from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()

    credentials = {}
    secrets = {
        'host': os.getenv('DATABASE_HOST_SECRET'),
        'name': os.getenv('DATABASE_NAME_SECRET'),
        'user': os.getenv('DATABASE_USER_SECRET'),
        'password': os.getenv('DATABASE_PASSWORD_SECRET')
    }

    for key, secret_path in secrets.items():
        if not secret_path:
            raise ValueError(f"Environment variable for {key} is not set")
        response = client.access_secret_version(request={"name": secret_path})
        credentials[key] = response.payload.data.decode("UTF-8")

    return credentials

def populate_broadcast_manager():
    """Populate broadcast_manager table from main_clients_database."""

    print("🚀 Starting broadcast_manager population...")

    # Fetch credentials
    creds = fetch_database_credentials()

    # Connect to database
    conn = psycopg2.connect(
        host=creds['host'],
        dbname=creds['name'],
        user=creds['user'],
        password=creds['password'],
        port=5432
    )

    try:
        with conn.cursor() as cur:
            # Fetch all channel pairs from main_clients_database
            print("📋 Fetching channel pairs from main_clients_database...")
            cur.execute("""
                SELECT
                    user_id,
                    open_channel_id,
                    closed_channel_id
                FROM main_clients_database
                WHERE open_channel_id IS NOT NULL
                    AND closed_channel_id IS NOT NULL
                ORDER BY user_id
            """)

            channel_pairs = cur.fetchall()
            print(f"✅ Found {len(channel_pairs)} channel pairs")

            # Insert into broadcast_manager
            print("💾 Inserting into broadcast_manager...")
            inserted = 0
            skipped = 0

            for user_id, open_channel_id, closed_channel_id in channel_pairs:
                try:
                    # Set initial next_send_time to NOW (will send on first cron run)
                    cur.execute("""
                        INSERT INTO broadcast_manager (
                            user_id,
                            open_channel_id,
                            closed_channel_id,
                            next_send_time,
                            broadcast_status,
                            is_active
                        ) VALUES (%s, %s, %s, NOW(), 'pending', true)
                        ON CONFLICT (open_channel_id, closed_channel_id) DO NOTHING
                    """, (user_id, open_channel_id, closed_channel_id))

                    if cur.rowcount > 0:
                        inserted += 1
                        print(f"  ✅ Inserted: user={user_id}, open={open_channel_id}")
                    else:
                        skipped += 1
                        print(f"  ⏭️  Skipped (already exists): open={open_channel_id}")

                except Exception as e:
                    print(f"  ❌ Error inserting {open_channel_id}: {e}")
                    skipped += 1

            conn.commit()

            print("\n📊 Population Summary:")
            print(f"  Total channel pairs: {len(channel_pairs)}")
            print(f"  Successfully inserted: {inserted}")
            print(f"  Skipped (duplicates): {skipped}")
            print("✅ Population complete!")

    except Exception as e:
        print(f"❌ Error during population: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    populate_broadcast_manager()
```

---

## Modular Component Design

### Component Architecture

**Directory Structure:**
```
GCBroadcastScheduler-10-26/
├── main.py                      # Cloud Run entry point
├── config_manager.py            # Configuration & Secret Manager
├── database_manager.py          # Database operations
├── broadcast_scheduler.py       # Scheduling logic (NEW)
├── broadcast_executor.py        # Message sending logic (NEW)
├── broadcast_tracker.py         # State tracking (NEW)
├── broadcast_web_api.py         # Manual trigger API (NEW)
├── telegram_client.py           # Telegram API wrapper (NEW)
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

### 1. BroadcastScheduler (New Module)

**File:** `GCBroadcastScheduler-10-26/broadcast_scheduler.py`

**Responsibility:** Determine which broadcasts are due to be sent

```python
#!/usr/bin/env python
"""
BroadcastScheduler - Determines which broadcasts should be sent
Handles scheduling logic, rate limiting, and broadcast queuing
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from database_manager import DatabaseManager
from config_manager import ConfigManager

logger = logging.getLogger(__name__)


class BroadcastScheduler:
    """
    Handles broadcast scheduling logic and rate limiting.

    Responsibilities:
    - Identify broadcasts that are due to be sent
    - Enforce rate limiting for manual triggers
    - Calculate next send times based on intervals
    - Queue broadcasts for execution
    """

    def __init__(self, db_manager: DatabaseManager, config_manager: ConfigManager):
        """
        Initialize the BroadcastScheduler.

        Args:
            db_manager: DatabaseManager instance
            config_manager: ConfigManager instance (for fetching intervals)
        """
        self.db = db_manager
        self.config = config_manager
        self.logger = logging.getLogger(__name__)

    def get_due_broadcasts(self) -> List[Dict[str, Any]]:
        """
        Get all broadcast entries that are due to be sent.

        A broadcast is "due" if:
        - is_active = true
        - broadcast_status = 'pending'
        - next_send_time <= NOW()
        - consecutive_failures < 5 (auto-disable after 5 failures)

        Returns:
            List of broadcast entries with full channel details
        """
        try:
            with self.db.get_connection() as conn, conn.cursor() as cur:
                query = """
                    SELECT
                        bm.id,
                        bm.user_id,
                        bm.open_channel_id,
                        bm.closed_channel_id,
                        bm.last_sent_time,
                        bm.next_send_time,
                        bm.broadcast_status,
                        bm.consecutive_failures,
                        mc.open_channel_title,
                        mc.open_channel_description,
                        mc.closed_channel_title,
                        mc.closed_channel_description,
                        mc.closed_channel_donation_message,
                        mc.sub_1_price,
                        mc.sub_1_time,
                        mc.sub_2_price,
                        mc.sub_2_time,
                        mc.sub_3_price,
                        mc.sub_3_time
                    FROM broadcast_manager bm
                    INNER JOIN main_clients_database mc
                        ON bm.open_channel_id = mc.open_channel_id
                    WHERE bm.is_active = true
                        AND bm.broadcast_status = 'pending'
                        AND bm.next_send_time <= NOW()
                        AND bm.consecutive_failures < 5
                    ORDER BY bm.next_send_time ASC
                """

                cur.execute(query)
                rows = cur.fetchall()

                broadcasts = []
                for row in rows:
                    broadcasts.append({
                        'id': row[0],
                        'user_id': row[1],
                        'open_channel_id': row[2],
                        'closed_channel_id': row[3],
                        'last_sent_time': row[4],
                        'next_send_time': row[5],
                        'broadcast_status': row[6],
                        'consecutive_failures': row[7],
                        'open_channel_title': row[8],
                        'open_channel_description': row[9],
                        'closed_channel_title': row[10],
                        'closed_channel_description': row[11],
                        'closed_channel_donation_message': row[12],
                        'sub_1_price': row[13],
                        'sub_1_time': row[14],
                        'sub_2_price': row[15],
                        'sub_2_time': row[16],
                        'sub_3_price': row[17],
                        'sub_3_time': row[18],
                    })

                self.logger.info(f"📋 Found {len(broadcasts)} broadcasts due for sending")
                return broadcasts

        except Exception as e:
            self.logger.error(f"❌ Error fetching due broadcasts: {e}")
            return []

    def check_manual_trigger_rate_limit(
        self,
        broadcast_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Check if a manual trigger is allowed based on rate limiting.

        Rate limit enforced: BROADCAST_MANUAL_INTERVAL (default 5 minutes)

        Args:
            broadcast_id: UUID of the broadcast entry
            user_id: User ID requesting the trigger (for verification)

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'retry_after_seconds': int (if not allowed)
            }
        """
        try:
            # Fetch manual interval from Secret Manager
            manual_interval_hours = self.config.get_broadcast_manual_interval()
            manual_interval = timedelta(hours=manual_interval_hours)

            with self.db.get_connection() as conn, conn.cursor() as cur:
                # Get last manual trigger time
                cur.execute("""
                    SELECT
                        user_id,
                        last_manual_trigger_time
                    FROM broadcast_manager
                    WHERE id = %s
                """, (broadcast_id,))

                result = cur.fetchone()

                if not result:
                    return {
                        'allowed': False,
                        'reason': 'Broadcast entry not found',
                        'retry_after_seconds': 0
                    }

                db_user_id, last_trigger = result

                # Verify ownership
                if db_user_id != user_id:
                    return {
                        'allowed': False,
                        'reason': 'Unauthorized: User does not own this channel',
                        'retry_after_seconds': 0
                    }

                # Check rate limit
                if last_trigger:
                    time_since_last = datetime.now() - last_trigger

                    if time_since_last < manual_interval:
                        retry_after = manual_interval - time_since_last
                        return {
                            'allowed': False,
                            'reason': f'Rate limit: Must wait {manual_interval_hours} hours between manual triggers',
                            'retry_after_seconds': int(retry_after.total_seconds())
                        }

                # All checks passed
                return {
                    'allowed': True,
                    'reason': 'Manual trigger allowed',
                    'retry_after_seconds': 0
                }

        except Exception as e:
            self.logger.error(f"❌ Error checking rate limit: {e}")
            return {
                'allowed': False,
                'reason': f'Internal error: {str(e)}',
                'retry_after_seconds': 0
            }

    def queue_manual_broadcast(self, broadcast_id: str) -> bool:
        """
        Queue a broadcast for immediate execution (manual trigger).

        Sets next_send_time = NOW() to trigger on next cron run.

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successfully queued, False otherwise
        """
        try:
            with self.db.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    UPDATE broadcast_manager
                    SET
                        next_send_time = NOW(),
                        broadcast_status = 'pending',
                        last_manual_trigger_time = NOW(),
                        manual_trigger_count = manual_trigger_count + 1
                    WHERE id = %s
                    RETURNING id
                """, (broadcast_id,))

                result = cur.fetchone()

                if result:
                    self.logger.info(f"✅ Queued manual broadcast: {broadcast_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ Broadcast not found: {broadcast_id}")
                    return False

        except Exception as e:
            self.logger.error(f"❌ Error queuing manual broadcast: {e}")
            return False

    def calculate_next_send_time(self) -> datetime:
        """
        Calculate the next send time based on BROADCAST_AUTO_INTERVAL.

        Returns:
            Datetime for next scheduled send
        """
        auto_interval_hours = self.config.get_broadcast_auto_interval()
        return datetime.now() + timedelta(hours=auto_interval_hours)
```

### 2. BroadcastExecutor (New Module)

**File:** `GCBroadcastScheduler-10-26/broadcast_executor.py`

**Responsibility:** Execute broadcasts by sending messages to Telegram channels

```python
#!/usr/bin/env python
"""
BroadcastExecutor - Executes broadcast operations
Sends subscription and donation messages to Telegram channels
"""

import logging
from typing import Dict, Any, List
from telegram_client import TelegramClient
from broadcast_tracker import BroadcastTracker

logger = logging.getLogger(__name__)


class BroadcastExecutor:
    """
    Executes broadcast operations by sending messages to Telegram channels.

    Responsibilities:
    - Send subscription tier messages to open channels
    - Send donation messages to closed channels
    - Handle Telegram API errors gracefully
    - Update broadcast status via BroadcastTracker
    """

    def __init__(
        self,
        telegram_client: TelegramClient,
        broadcast_tracker: BroadcastTracker
    ):
        """
        Initialize the BroadcastExecutor.

        Args:
            telegram_client: TelegramClient instance for sending messages
            broadcast_tracker: BroadcastTracker instance for updating status
        """
        self.telegram = telegram_client
        self.tracker = broadcast_tracker
        self.logger = logging.getLogger(__name__)

    def execute_broadcast(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single broadcast operation.

        Sends both subscription and donation messages, then updates status.

        Args:
            broadcast_entry: Broadcast entry from get_due_broadcasts()

        Returns:
            {
                'success': bool,
                'open_channel_sent': bool,
                'closed_channel_sent': bool,
                'errors': List[str]
            }
        """
        broadcast_id = broadcast_entry['id']
        open_channel_id = broadcast_entry['open_channel_id']
        closed_channel_id = broadcast_entry['closed_channel_id']

        self.logger.info(f"🚀 Executing broadcast {broadcast_id}")

        # Mark as in-progress
        self.tracker.update_status(broadcast_id, 'in_progress')

        errors = []
        open_sent = False
        closed_sent = False

        try:
            # Send subscription message to open channel
            open_result = self._send_subscription_message(broadcast_entry)
            open_sent = open_result['success']

            if not open_sent:
                errors.append(f"Open channel: {open_result['error']}")

            # Send donation message to closed channel
            closed_result = self._send_donation_message(broadcast_entry)
            closed_sent = closed_result['success']

            if not closed_sent:
                errors.append(f"Closed channel: {closed_result['error']}")

            # Determine overall success
            success = open_sent and closed_sent

            # Update broadcast status
            if success:
                self.tracker.mark_success(broadcast_id)
                self.logger.info(f"✅ Broadcast {broadcast_id} completed successfully")
            else:
                error_msg = '; '.join(errors)
                self.tracker.mark_failure(broadcast_id, error_msg)
                self.logger.error(f"❌ Broadcast {broadcast_id} failed: {error_msg}")

            return {
                'success': success,
                'open_channel_sent': open_sent,
                'closed_channel_sent': closed_sent,
                'errors': errors
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            errors.append(error_msg)
            self.tracker.mark_failure(broadcast_id, error_msg)
            self.logger.error(f"❌ Broadcast {broadcast_id} exception: {e}", exc_info=True)

            return {
                'success': False,
                'open_channel_sent': open_sent,
                'closed_channel_sent': closed_sent,
                'errors': errors
            }

    def _send_subscription_message(
        self,
        broadcast_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send subscription tier message to open channel.

        Args:
            broadcast_entry: Broadcast entry with channel details

        Returns:
            {'success': bool, 'error': str}
        """
        try:
            open_channel_id = broadcast_entry['open_channel_id']
            open_title = broadcast_entry['open_channel_title']
            open_desc = broadcast_entry['open_channel_description']
            closed_title = broadcast_entry['closed_channel_title']
            closed_desc = broadcast_entry['closed_channel_description']

            # Build subscription tier buttons
            tier_buttons = []
            for tier_num in (1, 2, 3):
                price = broadcast_entry.get(f'sub_{tier_num}_price')
                time = broadcast_entry.get(f'sub_{tier_num}_time')

                if price is not None and time is not None:
                    tier_buttons.append({
                        'tier': tier_num,
                        'price': price,
                        'time': time
                    })

            # Send via TelegramClient
            result = self.telegram.send_subscription_message(
                chat_id=open_channel_id,
                open_title=open_title,
                open_desc=open_desc,
                closed_title=closed_title,
                closed_desc=closed_desc,
                tier_buttons=tier_buttons
            )

            if result['success']:
                self.logger.info(f"✅ Sent subscription message to {open_channel_id}")
            else:
                self.logger.error(f"❌ Failed to send to {open_channel_id}: {result['error']}")

            return result

        except Exception as e:
            self.logger.error(f"❌ Exception sending subscription message: {e}")
            return {'success': False, 'error': str(e)}

    def _send_donation_message(
        self,
        broadcast_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send donation message to closed channel.

        Args:
            broadcast_entry: Broadcast entry with channel details

        Returns:
            {'success': bool, 'error': str}
        """
        try:
            closed_channel_id = broadcast_entry['closed_channel_id']
            donation_message = broadcast_entry.get(
                'closed_channel_donation_message',
                'Consider supporting our channel!'
            )
            open_channel_id = broadcast_entry['open_channel_id']

            # Send via TelegramClient
            result = self.telegram.send_donation_message(
                chat_id=closed_channel_id,
                donation_message=donation_message,
                open_channel_id=open_channel_id
            )

            if result['success']:
                self.logger.info(f"✅ Sent donation message to {closed_channel_id}")
            else:
                self.logger.error(f"❌ Failed to send to {closed_channel_id}: {result['error']}")

            return result

        except Exception as e:
            self.logger.error(f"❌ Exception sending donation message: {e}")
            return {'success': False, 'error': str(e)}

    def execute_batch(self, broadcast_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple broadcasts in sequence.

        Args:
            broadcast_entries: List of broadcast entries

        Returns:
            {
                'total': int,
                'successful': int,
                'failed': int,
                'results': List[Dict]
            }
        """
        total = len(broadcast_entries)
        successful = 0
        failed = 0
        results = []

        self.logger.info(f"📊 Executing batch of {total} broadcasts")

        for entry in broadcast_entries:
            result = self.execute_broadcast(entry)

            if result['success']:
                successful += 1
            else:
                failed += 1

            results.append({
                'broadcast_id': entry['id'],
                'open_channel_id': entry['open_channel_id'],
                'result': result
            })

        self.logger.info(
            f"📊 Batch complete: {successful}/{total} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': results
        }
```

### 3. BroadcastTracker (New Module)

**File:** `GCBroadcastScheduler-10-26/broadcast_tracker.py`

**Responsibility:** Track broadcast state and update database

```python
#!/usr/bin/env python
"""
BroadcastTracker - Tracks broadcast state and updates database
Handles state transitions, statistics, and error tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from database_manager import DatabaseManager
from config_manager import ConfigManager

logger = logging.getLogger(__name__)


class BroadcastTracker:
    """
    Tracks broadcast state and updates the broadcast_manager table.

    Responsibilities:
    - Update broadcast status (pending → in_progress → completed/failed)
    - Track success/failure statistics
    - Calculate and set next send times
    - Handle error logging
    """

    def __init__(self, db_manager: DatabaseManager, config_manager: ConfigManager):
        """
        Initialize the BroadcastTracker.

        Args:
            db_manager: DatabaseManager instance
            config_manager: ConfigManager instance (for intervals)
        """
        self.db = db_manager
        self.config = config_manager
        self.logger = logging.getLogger(__name__)

    def update_status(self, broadcast_id: str, status: str) -> bool:
        """
        Update broadcast status.

        Args:
            broadcast_id: UUID of the broadcast entry
            status: New status ('pending', 'in_progress', 'completed', 'failed', 'skipped')

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    UPDATE broadcast_manager
                    SET broadcast_status = %s
                    WHERE id = %s
                """, (status, broadcast_id))

                self.logger.info(f"📝 Updated status: {broadcast_id} → {status}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error updating status: {e}")
            return False

    def mark_success(self, broadcast_id: str) -> bool:
        """
        Mark broadcast as successfully completed.

        Updates:
        - broadcast_status = 'completed'
        - last_sent_time = NOW()
        - next_send_time = NOW() + BROADCAST_AUTO_INTERVAL
        - total_broadcasts += 1
        - successful_broadcasts += 1
        - consecutive_failures = 0
        - last_error_message = NULL

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get auto interval from config
            auto_interval_hours = self.config.get_broadcast_auto_interval()
            next_send = datetime.now() + timedelta(hours=auto_interval_hours)

            with self.db.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    UPDATE broadcast_manager
                    SET
                        broadcast_status = 'completed',
                        last_sent_time = NOW(),
                        next_send_time = %s,
                        total_broadcasts = total_broadcasts + 1,
                        successful_broadcasts = successful_broadcasts + 1,
                        consecutive_failures = 0,
                        last_error_message = NULL,
                        last_error_time = NULL
                    WHERE id = %s
                """, (next_send, broadcast_id))

                self.logger.info(f"✅ Marked success: {broadcast_id}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error marking success: {e}")
            return False

    def mark_failure(self, broadcast_id: str, error_message: str) -> bool:
        """
        Mark broadcast as failed.

        Updates:
        - broadcast_status = 'failed'
        - failed_broadcasts += 1
        - consecutive_failures += 1
        - last_error_message = error_message
        - last_error_time = NOW()
        - is_active = false (if consecutive_failures >= 5)

        Args:
            broadcast_id: UUID of the broadcast entry
            error_message: Error description

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn, conn.cursor() as cur:
                # Increment consecutive failures and check if should deactivate
                cur.execute("""
                    UPDATE broadcast_manager
                    SET
                        broadcast_status = 'failed',
                        failed_broadcasts = failed_broadcasts + 1,
                        consecutive_failures = consecutive_failures + 1,
                        last_error_message = %s,
                        last_error_time = NOW(),
                        is_active = CASE
                            WHEN consecutive_failures + 1 >= 5 THEN false
                            ELSE is_active
                        END
                    WHERE id = %s
                    RETURNING consecutive_failures, is_active
                """, (error_message, broadcast_id))

                result = cur.fetchone()

                if result:
                    failures, is_active = result
                    if not is_active:
                        self.logger.warning(
                            f"⚠️ Broadcast {broadcast_id} deactivated after {failures} consecutive failures"
                        )
                    else:
                        self.logger.error(
                            f"❌ Marked failure: {broadcast_id} (consecutive: {failures})"
                        )

                return True

        except Exception as e:
            self.logger.error(f"❌ Error marking failure: {e}")
            return False

    def reset_consecutive_failures(self, broadcast_id: str) -> bool:
        """
        Reset consecutive failure count (useful for manual re-enable).

        Args:
            broadcast_id: UUID of the broadcast entry

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db.get_connection() as conn, conn.cursor() as cur:
                cur.execute("""
                    UPDATE broadcast_manager
                    SET consecutive_failures = 0
                    WHERE id = %s
                """, (broadcast_id,))

                self.logger.info(f"🔄 Reset consecutive failures: {broadcast_id}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error resetting failures: {e}")
            return False
```

### 4. TelegramClient (New Module)

**File:** `GCBroadcastScheduler-10-26/telegram_client.py`

**Responsibility:** Wrapper for Telegram Bot API operations

```python
#!/usr/bin/env python
"""
TelegramClient - Telegram Bot API wrapper for broadcast operations
Handles message sending with proper formatting and error handling
"""

import logging
import base64
from typing import Dict, Any, List
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, BadRequest

logger = logging.getLogger(__name__)


class TelegramClient:
    """
    Wrapper for Telegram Bot API operations specific to broadcast messages.

    Responsibilities:
    - Send subscription tier messages with inline buttons
    - Send donation messages with inline buttons
    - Format messages with proper HTML
    - Handle Telegram API errors gracefully
    """

    def __init__(self, bot_token: str, bot_username: str):
        """
        Initialize the TelegramClient.

        Args:
            bot_token: Telegram bot token
            bot_username: Bot username (for deep links)
        """
        self.bot = Bot(token=bot_token)
        self.bot_username = bot_username
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def encode_id(i):
        """Encode ID for deep link tokens."""
        return base64.urlsafe_b64encode(str(i).encode()).decode()

    def send_subscription_message(
        self,
        chat_id: str,
        open_title: str,
        open_desc: str,
        closed_title: str,
        closed_desc: str,
        tier_buttons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send subscription tier message to open channel.

        Args:
            chat_id: Open channel ID
            open_title: Open channel title
            open_desc: Open channel description
            closed_title: Closed channel title
            closed_desc: Closed channel description
            tier_buttons: List of tier info [{'tier': 1, 'price': 5.0, 'time': 30}, ...]

        Returns:
            {'success': bool, 'error': str (if failed)}
        """
        try:
            # Build message text
            message_text = (
                f"Hello, welcome to <b>{open_title}: {open_desc}</b>\n\n"
                f"Choose your Subscription Tier to gain access to <b>{closed_title}: {closed_desc}</b>."
            )

            # Build inline keyboard
            tier_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            buttons = []

            for tier_info in tier_buttons:
                tier_num = tier_info['tier']
                price = tier_info['price']
                days = tier_info['time']

                # Encode subscription token
                base_hash = self.encode_id(chat_id)
                safe_sub = str(price).replace(".", "d")
                token = f"{base_hash}_{safe_sub}_{days}"
                url = f"https://t.me/{self.bot_username}?start={token}"

                emoji = tier_emojis.get(tier_num, "💰")
                button_text = f"{emoji} ${price} for {days} days"

                buttons.append([InlineKeyboardButton(text=button_text, url=url)])

            reply_markup = InlineKeyboardMarkup(buttons)

            # Send message
            self.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

            return {'success': True, 'error': None}

        except Forbidden as e:
            error_msg = f"Bot not admin or kicked from channel"
            self.logger.warning(f"⚠️ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except BadRequest as e:
            error_msg = f"Invalid channel or API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except TelegramError as e:
            error_msg = f"Telegram API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

    def send_donation_message(
        self,
        chat_id: str,
        donation_message: str,
        open_channel_id: str
    ) -> Dict[str, Any]:
        """
        Send donation message to closed channel.

        Args:
            chat_id: Closed channel ID
            donation_message: Custom donation message
            open_channel_id: Associated open channel (for callback data)

        Returns:
            {'success': bool, 'error': str (if failed)}
        """
        try:
            # Build message text
            message_text = (
                f"Enjoying the content? Consider making a donation.\n<b>{donation_message}</b>"
            )

            # Build inline keyboard
            callback_data = f"donate_start_{open_channel_id}"

            # Validate callback_data length (Telegram limit: 64 bytes)
            if len(callback_data.encode('utf-8')) > 64:
                self.logger.warning(f"⚠️ Callback data too long, truncating")
                callback_data = callback_data[:64]

            button = InlineKeyboardButton(
                text="💝 Donate to Support This Channel",
                callback_data=callback_data
            )

            reply_markup = InlineKeyboardMarkup([[button]])

            # Send message
            self.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

            return {'success': True, 'error': None}

        except Forbidden as e:
            error_msg = f"Bot not admin or kicked from channel"
            self.logger.warning(f"⚠️ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except BadRequest as e:
            error_msg = f"Invalid channel or API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except TelegramError as e:
            error_msg = f"Telegram API error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"❌ {error_msg}: {chat_id}")
            return {'success': False, 'error': error_msg}
```

### 5. BroadcastWebAPI (New Module)

**File:** `GCBroadcastScheduler-10-26/broadcast_web_api.py`

**Responsibility:** Handle manual trigger requests from website

```python
#!/usr/bin/env python
"""
BroadcastWebAPI - API endpoints for manual broadcast triggers
Handles authentication, authorization, and rate limiting for website requests
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import os
from broadcast_scheduler import BroadcastScheduler

logger = logging.getLogger(__name__)

# Create Flask blueprint
broadcast_api = Blueprint('broadcast_api', __name__)


def authenticate_request(f):
    """
    Decorator to authenticate JWT tokens from requests.

    Expects Authorization header: "Bearer <token>"
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({'error': 'Missing Authorization header'}), 401

        try:
            # Extract token from "Bearer <token>"
            token = auth_header.split(' ')[1]

            # Decode JWT (secret key from environment)
            jwt_secret = os.getenv('JWT_SECRET_KEY')
            if not jwt_secret:
                logger.error("JWT_SECRET_KEY not configured")
                return jsonify({'error': 'Server configuration error'}), 500

            payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])

            # Attach user_id to request context
            request.user_id = payload.get('user_id')

            if not request.user_id:
                return jsonify({'error': 'Invalid token payload'}), 401

            return f(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401

        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({'error': 'Authentication failed'}), 401

    return decorated


class BroadcastWebAPI:
    """
    Handles API endpoints for broadcast manual triggers.

    Endpoints:
    - POST /api/broadcast/trigger - Trigger manual broadcast
    - GET /api/broadcast/status/:id - Get broadcast status
    """

    def __init__(self, broadcast_scheduler: BroadcastScheduler):
        """
        Initialize the BroadcastWebAPI.

        Args:
            broadcast_scheduler: BroadcastScheduler instance
        """
        self.scheduler = broadcast_scheduler
        self.logger = logging.getLogger(__name__)

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register Flask blueprint routes."""

        @broadcast_api.route('/api/broadcast/trigger', methods=['POST'])
        @authenticate_request
        def trigger_broadcast():
            """
            Manually trigger a broadcast for a specific channel pair.

            Request Body:
            {
                "broadcast_id": "uuid"
            }

            Response:
            {
                "success": true,
                "message": "Broadcast queued for sending",
                "broadcast_id": "uuid"
            }

            OR (rate limited):
            {
                "success": false,
                "error": "Rate limit exceeded",
                "retry_after_seconds": 180
            }
            """
            try:
                data = request.get_json()

                if not data or 'broadcast_id' not in data:
                    return jsonify({'error': 'Missing broadcast_id'}), 400

                broadcast_id = data['broadcast_id']
                user_id = request.user_id

                # Check rate limit
                rate_limit_check = self.scheduler.check_manual_trigger_rate_limit(
                    broadcast_id, user_id
                )

                if not rate_limit_check['allowed']:
                    return jsonify({
                        'success': False,
                        'error': rate_limit_check['reason'],
                        'retry_after_seconds': rate_limit_check['retry_after_seconds']
                    }), 429

                # Queue broadcast
                success = self.scheduler.queue_manual_broadcast(broadcast_id)

                if success:
                    return jsonify({
                        'success': True,
                        'message': 'Broadcast queued for sending',
                        'broadcast_id': broadcast_id
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to queue broadcast'
                    }), 500

            except Exception as e:
                self.logger.error(f"Error in trigger_broadcast: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @broadcast_api.route('/api/broadcast/status/<broadcast_id>', methods=['GET'])
        @authenticate_request
        def get_broadcast_status(broadcast_id):
            """
            Get status of a specific broadcast.

            Response:
            {
                "broadcast_id": "uuid",
                "status": "completed",
                "last_sent_time": "2025-11-11T12:00:00Z",
                "next_send_time": "2025-11-12T12:00:00Z",
                "total_broadcasts": 10,
                "successful_broadcasts": 9,
                "failed_broadcasts": 1
            }
            """
            # Implementation would query broadcast_manager table
            # and return status information
            pass

    def get_blueprint(self):
        """Get the Flask blueprint for registration."""
        return broadcast_api
```

---

## Google Cloud Infrastructure

### Cloud Scheduler Setup

**Scheduler Job Name:** `broadcast-scheduler-daily`

**Schedule:** `0 0 * * *` (Every day at midnight UTC)

**Target:** Cloud Run service `GCBroadcastScheduler-10-26`

**Endpoint:** `POST /api/broadcast/execute`

**Creation Command:**
```bash
gcloud scheduler jobs create http broadcast-scheduler-daily \
    --location=us-central1 \
    --schedule="0 0 * * *" \
    --uri="https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app/api/broadcast/execute" \
    --http-method=POST \
    --oidc-service-account-email="291176869049-compute@developer.gserviceaccount.com" \
    --oidc-token-audience="https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app" \
    --headers="Content-Type=application/json" \
    --message-body='{"source":"cloud_scheduler"}' \
    --time-zone="UTC"
```

### Cloud Run Service Deployment

**Service Name:** `GCBroadcastScheduler-10-26`

**Region:** `us-central1`

**Key Configuration:**
- **Min Instances:** 0 (cost optimization)
- **Max Instances:** 1 (no need for multiple instances)
- **Memory:** 512MB
- **CPU:** 1
- **Timeout:** 300s (5 minutes - enough for batch broadcasts)
- **Concurrency:** 1 (prevent overlapping executions)

**Environment Variables:**
```bash
BOT_TOKEN_SECRET=projects/telepay-459221/secrets/BOT_TOKEN/versions/latest
BOT_USERNAME_SECRET=projects/telepay-459221/secrets/BOT_USERNAME/versions/latest
DATABASE_HOST_SECRET=projects/telepay-459221/secrets/DATABASE_HOST_SECRET/versions/latest
DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest
BROADCAST_AUTO_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_AUTO_INTERVAL/versions/latest
BROADCAST_MANUAL_INTERVAL_SECRET=projects/telepay-459221/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest
JWT_SECRET_KEY_SECRET=projects/telepay-459221/secrets/JWT_SECRET_KEY/versions/latest
```

**Deployment Script:**
```bash
#!/bin/bash
# deploy_broadcast_scheduler.sh

set -e

PROJECT_ID="telepay-459221"
REGION="us-central1"
SERVICE_NAME="gcbroadcastscheduler-10-26"

echo "🚀 Deploying $SERVICE_NAME..."

# Build and deploy
gcloud run deploy $SERVICE_NAME \
    --source=./GCBroadcastScheduler-10-26 \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300s \
    --concurrency=1 \
    --set-env-vars="BOT_TOKEN_SECRET=projects/$PROJECT_ID/secrets/BOT_TOKEN/versions/latest" \
    --set-env-vars="BOT_USERNAME_SECRET=projects/$PROJECT_ID/secrets/BOT_USERNAME/versions/latest" \
    --set-env-vars="DATABASE_HOST_SECRET=projects/$PROJECT_ID/secrets/DATABASE_HOST_SECRET/versions/latest" \
    --set-env-vars="DATABASE_NAME_SECRET=projects/$PROJECT_ID/secrets/DATABASE_NAME_SECRET/versions/latest" \
    --set-env-vars="DATABASE_USER_SECRET=projects/$PROJECT_ID/secrets/DATABASE_USER_SECRET/versions/latest" \
    --set-env-vars="DATABASE_PASSWORD_SECRET=projects/$PROJECT_ID/secrets/DATABASE_PASSWORD_SECRET/versions/latest" \
    --set-env-vars="BROADCAST_AUTO_INTERVAL_SECRET=projects/$PROJECT_ID/secrets/BROADCAST_AUTO_INTERVAL/versions/latest" \
    --set-env-vars="BROADCAST_MANUAL_INTERVAL_SECRET=projects/$PROJECT_ID/secrets/BROADCAST_MANUAL_INTERVAL/versions/latest" \
    --set-env-vars="JWT_SECRET_KEY_SECRET=projects/$PROJECT_ID/secrets/JWT_SECRET_KEY/versions/latest"

echo "✅ Deployment complete!"
```

---

## Configuration Management

### Secret Manager Secrets

**1. BROADCAST_AUTO_INTERVAL**
- **Purpose:** Interval between automated broadcasts
- **Default Value:** `24` (hours)
- **Format:** Integer (hours)

**2. BROADCAST_MANUAL_INTERVAL**
- **Purpose:** Rate limit for manual triggers
- **Default Value:** `0.0833` (5 minutes = 1/12 hour)
- **Format:** Float (hours)

### Creating Secrets

```bash
#!/bin/bash
# create_broadcast_secrets.sh

PROJECT_ID="telepay-459221"

# Create BROADCAST_AUTO_INTERVAL secret (24 hours)
echo "24" | gcloud secrets create BROADCAST_AUTO_INTERVAL \
    --project=$PROJECT_ID \
    --replication-policy="automatic" \
    --data-file=-

# Create BROADCAST_MANUAL_INTERVAL secret (5 minutes = 0.0833 hours)
echo "0.0833" | gcloud secrets create BROADCAST_MANUAL_INTERVAL \
    --project=$PROJECT_ID \
    --replication-policy="automatic" \
    --data-file=-

# Grant access to compute service account
SERVICE_ACCOUNT="291176869049-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding BROADCAST_AUTO_INTERVAL \
    --project=$PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding BROADCAST_MANUAL_INTERVAL \
    --project=$PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"

echo "✅ Secrets created successfully!"
```

### ConfigManager Implementation

**File:** `GCBroadcastScheduler-10-26/config_manager.py`

```python
#!/usr/bin/env python
"""
ConfigManager - Manages configuration from Secret Manager
Fetches and caches broadcast intervals
"""

import os
import logging
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration from Google Cloud Secret Manager.

    Responsibilities:
    - Fetch configuration from Secret Manager
    - Cache values for performance
    - Provide type-safe access to config values
    """

    def __init__(self):
        """Initialize the ConfigManager."""
        self.client = secretmanager.SecretManagerServiceClient()
        self.logger = logging.getLogger(__name__)
        self._cache = {}

    def _fetch_secret(self, secret_env_var: str) -> str:
        """
        Fetch a secret from Secret Manager.

        Args:
            secret_env_var: Environment variable containing secret path

        Returns:
            Secret value as string
        """
        try:
            secret_path = os.getenv(secret_env_var)
            if not secret_path:
                raise ValueError(f"Environment variable {secret_env_var} not set")

            # Check cache
            if secret_path in self._cache:
                return self._cache[secret_path]

            # Fetch from Secret Manager
            response = self.client.access_secret_version(request={"name": secret_path})
            value = response.payload.data.decode("UTF-8")

            # Cache value
            self._cache[secret_path] = value

            return value

        except Exception as e:
            self.logger.error(f"Error fetching secret {secret_env_var}: {e}")
            raise

    def get_broadcast_auto_interval(self) -> float:
        """
        Get automated broadcast interval in hours.

        Returns:
            Interval in hours (default: 24.0)
        """
        try:
            value = self._fetch_secret('BROADCAST_AUTO_INTERVAL_SECRET')
            return float(value)
        except Exception as e:
            self.logger.warning(f"Using default auto interval (24h): {e}")
            return 24.0

    def get_broadcast_manual_interval(self) -> float:
        """
        Get manual trigger rate limit interval in hours.

        Returns:
            Interval in hours (default: 0.0833 = 5 minutes)
        """
        try:
            value = self._fetch_secret('BROADCAST_MANUAL_INTERVAL_SECRET')
            return float(value)
        except Exception as e:
            self.logger.warning(f"Using default manual interval (5min): {e}")
            return 0.0833  # 5 minutes

    def clear_cache(self):
        """Clear the configuration cache (useful for testing)."""
        self._cache.clear()
```

---

## API Endpoints

### 1. Execute Scheduled Broadcast

**Endpoint:** `POST /api/broadcast/execute`

**Caller:** Google Cloud Scheduler

**Authentication:** OIDC token (service account)

**Request:**
```json
{
    "source": "cloud_scheduler"
}
```

**Response (Success):**
```json
{
    "success": true,
    "total_broadcasts": 10,
    "successful": 9,
    "failed": 1,
    "execution_time_seconds": 45.2
}
```

**Response (Error):**
```json
{
    "success": false,
    "error": "Database connection failed"
}
```

### 2. Manual Trigger

**Endpoint:** `POST /api/broadcast/trigger`

**Caller:** GCRegisterWeb-10-26 (client dashboard)

**Authentication:** JWT Bearer token

**Request:**
```json
{
    "broadcast_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Success):**
```json
{
    "success": true,
    "message": "Broadcast queued for sending",
    "broadcast_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Rate Limited):**
```json
{
    "success": false,
    "error": "Rate limit: Must wait 0.0833 hours between manual triggers",
    "retry_after_seconds": 180
}
```

---

## Scheduling Logic

### Broadcast Lifecycle

```
┌─────────────┐
│   PENDING   │ ← Initial state
└──────┬──────┘
       │
       ├── next_send_time <= NOW()
       │
       ▼
┌─────────────┐
│ IN_PROGRESS │ ← Currently sending
└──────┬──────┘
       │
       ├── Success?
       │
       ├─YES──▶ ┌───────────┐
       │        │ COMPLETED │
       │        └─────┬─────┘
       │              │
       │              └──▶ next_send_time = NOW() + 24h
       │                   back to PENDING
       │
       └─NO───▶ ┌─────────┐
                │ FAILED  │
                └────┬────┘
                     │
                     ├── consecutive_failures < 5?
                     │
                     ├─YES──▶ back to PENDING
                     │        (will retry on next cron)
                     │
                     └─NO───▶ is_active = false
                              (requires manual re-enable)
```

### Rate Limiting Logic

**Automated Broadcasts:**
- Controlled by `next_send_time` field
- Interval: `BROADCAST_AUTO_INTERVAL` (default 24 hours)
- Calculation: `next_send_time = last_sent_time + interval`

**Manual Triggers:**
- Controlled by `last_manual_trigger_time` field
- Interval: `BROADCAST_MANUAL_INTERVAL` (default 5 minutes)
- Check: `NOW() - last_manual_trigger_time >= interval`
- Action: Set `next_send_time = NOW()` to trigger on next cron run

---

## Security Considerations

### Authentication & Authorization

**1. Cloud Scheduler → Cloud Run**
- **Method:** OIDC (OpenID Connect) tokens
- **Service Account:** `291176869049-compute@developer.gserviceaccount.com`
- **Validation:** Cloud Run automatically validates OIDC tokens
- **No additional auth** needed in application code

**2. Website → Cloud Run (Manual Triggers)**
- **Method:** JWT Bearer tokens
- **Token Generation:** GCRegisterAPI-10-26 (on user login)
- **Token Validation:** BroadcastWebAPI (jwt.decode with secret key)
- **Claims:** `user_id`, `exp` (expiration)
- **Rate Limiting:** Enforced per user via `last_manual_trigger_time`

### Database Security

**1. SQL Injection Prevention**
- ✅ **All queries use parameterized statements** (`%s` placeholders)
- ✅ **Never concatenate user input** into SQL strings
- ✅ **Validated UUIDs** for broadcast_id references

**2. Authorization Checks**
- ✅ **Verify channel ownership** before manual triggers
- ✅ **Check `user_id`** matches JWT token
- ✅ **Prevent unauthorized broadcasts** to other users' channels

### Secrets Management

**1. Never Hardcode Secrets**
- ❌ No tokens, passwords, or keys in code
- ✅ All sensitive data in Secret Manager
- ✅ Environment variables point to secret paths

**2. Least Privilege Access**
- ✅ Service account has **only** Secret Accessor role
- ✅ No broad permissions granted
- ✅ Secrets scoped to specific services

---

## Error Handling & Monitoring

### Error Categories

**1. Telegram API Errors**
- `Forbidden`: Bot not admin or kicked from channel
  - Action: Log warning, mark failure, notify user
- `BadRequest`: Invalid channel ID or message format
  - Action: Log error, mark failure, disable after 5 failures
- `TelegramError`: General API errors (rate limits, network)
  - Action: Log error, retry on next cron run

**2. Database Errors**
- Connection failures
  - Action: Log critical error, return 500, retry on next cron
- Query errors (constraint violations)
  - Action: Log error, skip entry, continue batch
- Transaction errors
  - Action: Rollback, log error, retry

**3. Configuration Errors**
- Missing secrets
  - Action: Use default values, log warning
- Invalid secret values
  - Action: Use default values, log error

### Logging Strategy

**Log Levels:**
- `INFO`: Normal operations (broadcasts sent, status updates)
- `WARNING`: Recoverable issues (rate limits, missing data)
- `ERROR`: Failures requiring attention (API errors, DB errors)
- `CRITICAL`: System failures (config missing, DB unavailable)

**Log Format:**
```python
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
```

**Key Log Messages:**
```python
# ✅ Success
logger.info(f"✅ Broadcast {broadcast_id} completed successfully")

# ⚠️ Warning
logger.warning(f"⚠️ Rate limit exceeded for user {user_id}")

# ❌ Error
logger.error(f"❌ Broadcast {broadcast_id} failed: {error_msg}")

# 🔥 Critical
logger.critical(f"🔥 Database connection failed: {error}")
```

### Monitoring with Cloud Logging

**Query Examples:**

**1. Failed Broadcasts**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastscheduler-10-26"
severity="ERROR"
textPayload=~"Broadcast.*failed"
```

**2. Rate Limit Violations**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastscheduler-10-26"
textPayload=~"Rate limit"
```

**3. Execution Statistics**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastscheduler-10-26"
textPayload=~"Batch complete"
```

### Alerting

**Cloud Monitoring Alerts:**

**1. High Failure Rate**
- **Condition:** Failed broadcasts > 10% in 1 hour
- **Action:** Email notification to admin
- **Query:** Count ERROR logs with "failed" in 1-hour window

**2. Consecutive Failures**
- **Condition:** broadcast_manager.consecutive_failures >= 5
- **Action:** Slack notification, email to client
- **Query:** Database query for high failure counts

**3. Scheduler Failures**
- **Condition:** Cloud Scheduler job fails 3 times in a row
- **Action:** Email notification, PagerDuty alert
- **Built-in:** Cloud Scheduler retry policy

---

## Migration Strategy

### Phase 1: Database Setup (Week 1)

**Tasks:**
1. ✅ Review and approve `broadcast_manager` table schema
2. ✅ Create migration script (`create_broadcast_manager_table.sql`)
3. ✅ Create rollback script (`rollback_broadcast_manager_table.sql`)
4. ✅ Execute migration on `telepaypsql` database
5. ✅ Verify table structure and indexes
6. ✅ Run population script (`populate_broadcast_manager.py`)
7. ✅ Verify initial data

### Phase 2: Service Development (Week 2)

**Tasks:**
1. ✅ Create `GCBroadcastScheduler-10-26` directory structure
2. ✅ Implement `ConfigManager` with Secret Manager integration
3. ✅ Implement `DatabaseManager` with broadcast_manager queries
4. ✅ Implement `TelegramClient` message sending
5. ✅ Implement `BroadcastScheduler` scheduling logic
6. ✅ Implement `BroadcastExecutor` broadcast execution
7. ✅ Implement `BroadcastTracker` state management
8. ✅ Implement `BroadcastWebAPI` manual trigger endpoints
9. ✅ Create `main.py` Flask application
10. ✅ Write `Dockerfile` and `requirements.txt`

### Phase 3: Secret Manager Setup (Week 2)

**Tasks:**
1. ✅ Create `BROADCAST_AUTO_INTERVAL` secret (24 hours)
2. ✅ Create `BROADCAST_MANUAL_INTERVAL` secret (5 minutes)
3. ✅ Grant service account access to secrets
4. ✅ Test secret fetching from ConfigManager

### Phase 4: Cloud Run Deployment (Week 3)

**Tasks:**
1. ✅ Deploy `GCBroadcastScheduler-10-26` to Cloud Run
2. ✅ Configure environment variables (secret paths)
3. ✅ Test `/health` endpoint
4. ✅ Test `/api/broadcast/execute` endpoint (manual POST)
5. ✅ Verify database connectivity
6. ✅ Verify Secret Manager access

### Phase 5: Cloud Scheduler Setup (Week 3)

**Tasks:**
1. ✅ Create Cloud Scheduler job `broadcast-scheduler-daily`
2. ✅ Configure cron schedule (`0 0 * * *`)
3. ✅ Configure OIDC authentication
4. ✅ Test manual trigger from Cloud Console
5. ✅ Verify execution logs in Cloud Logging

### Phase 6: Website Integration (Week 4)

**Tasks:**
1. ✅ Add "Resend Messages" button to dashboard
2. ✅ Implement frontend API call to `/api/broadcast/trigger`
3. ✅ Handle rate limit responses (show retry timer)
4. ✅ Display success/error messages
5. ✅ Test end-to-end workflow

### Phase 7: Monitoring & Testing (Week 4)

**Tasks:**
1. ✅ Set up Cloud Logging queries
2. ✅ Create Cloud Monitoring dashboards
3. ✅ Configure alerting policies
4. ✅ Test failure scenarios (invalid channels, API errors)
5. ✅ Test rate limiting
6. ✅ Load testing (multiple broadcasts)

### Phase 8: Decommission Old System (Week 5)

**Tasks:**
1. ✅ Disable broadcast calls in `app_initializer.py`
2. ✅ Archive old `broadcast_manager.py` code
3. ✅ Update documentation
4. ✅ Final verification

---

## Testing Strategy

### Unit Tests

**File:** `TOOLS_SCRIPTS_TESTS/tests/test_broadcast_scheduler.py`

```python
#!/usr/bin/env python
"""
Unit tests for BroadcastScheduler
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from broadcast_scheduler import BroadcastScheduler


class TestBroadcastScheduler(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.db_manager = Mock()
        self.config_manager = Mock()
        self.config_manager.get_broadcast_auto_interval.return_value = 24.0
        self.config_manager.get_broadcast_manual_interval.return_value = 0.0833

        self.scheduler = BroadcastScheduler(self.db_manager, self.config_manager)

    def test_get_due_broadcasts(self):
        """Test fetching due broadcasts."""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            # Sample broadcast entry
            ('uuid-123', 1, '-1001234', '-1005678', None, datetime.now(), 'pending', 0,
             'Open Title', 'Open Desc', 'Closed Title', 'Closed Desc', 'Donate!',
             5.0, 30, 10.0, 60, None, None)
        ]

        self.db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        broadcasts = self.scheduler.get_due_broadcasts()

        # Verify
        self.assertEqual(len(broadcasts), 1)
        self.assertEqual(broadcasts[0]['open_channel_id'], '-1001234')

    def test_manual_trigger_rate_limit_allowed(self):
        """Test rate limit allows trigger after interval."""
        # Mock database: last trigger was 10 minutes ago
        mock_cursor = MagicMock()
        last_trigger = datetime.now() - timedelta(minutes=10)
        mock_cursor.fetchone.return_value = (1, last_trigger)

        self.db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        result = self.scheduler.check_manual_trigger_rate_limit('uuid-123', 1)

        # Verify
        self.assertTrue(result['allowed'])

    def test_manual_trigger_rate_limit_blocked(self):
        """Test rate limit blocks trigger within interval."""
        # Mock database: last trigger was 2 minutes ago
        mock_cursor = MagicMock()
        last_trigger = datetime.now() - timedelta(minutes=2)
        mock_cursor.fetchone.return_value = (1, last_trigger)

        self.db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        # Execute
        result = self.scheduler.check_manual_trigger_rate_limit('uuid-123', 1)

        # Verify
        self.assertFalse(result['allowed'])
        self.assertGreater(result['retry_after_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
```

### Integration Tests

**File:** `TOOLS_SCRIPTS_TESTS/tests/test_broadcast_integration.py`

```python
#!/usr/bin/env python
"""
Integration tests for broadcast system
Tests full workflow from scheduling to execution
"""

import unittest
import os
from database_manager import DatabaseManager
from config_manager import ConfigManager
from broadcast_scheduler import BroadcastScheduler
from broadcast_executor import BroadcastExecutor
from broadcast_tracker import BroadcastTracker
from telegram_client import TelegramClient


class TestBroadcastIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Use test database credentials
        os.environ['DATABASE_HOST_SECRET'] = 'test-db-host'
        os.environ['DATABASE_NAME_SECRET'] = 'test-db-name'
        # ... other test env vars

    def setUp(self):
        """Set up test fixtures."""
        self.db = DatabaseManager()
        self.config = ConfigManager()
        self.telegram = TelegramClient(
            os.getenv('BOT_TOKEN'),
            os.getenv('BOT_USERNAME')
        )

        self.tracker = BroadcastTracker(self.db, self.config)
        self.scheduler = BroadcastScheduler(self.db, self.config)
        self.executor = BroadcastExecutor(self.telegram, self.tracker)

    def test_full_broadcast_workflow(self):
        """Test complete broadcast workflow."""
        # 1. Get due broadcasts
        broadcasts = self.scheduler.get_due_broadcasts()
        self.assertIsInstance(broadcasts, list)

        if len(broadcasts) == 0:
            self.skipTest("No broadcasts due")

        # 2. Execute first broadcast
        broadcast = broadcasts[0]
        result = self.executor.execute_broadcast(broadcast)

        # 3. Verify result
        self.assertIn('success', result)

        # 4. Verify database updated
        # ... query broadcast_manager table and verify status


if __name__ == '__main__':
    unittest.main()
```

---

## Deployment Guide

### Prerequisites

1. ✅ Google Cloud Project: `telepay-459221`
2. ✅ Cloud SQL database: `telepaypsql`
3. ✅ Service account: `291176869049-compute@developer.gserviceaccount.com`
4. ✅ Required APIs enabled:
   - Cloud Run API
   - Cloud Scheduler API
   - Secret Manager API
   - Cloud SQL Admin API

### Step-by-Step Deployment

**Step 1: Create Database Table**
```bash
cd TOOLS_SCRIPTS_TESTS/scripts
psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
     -U postgres \
     -d telepaydb \
     -f create_broadcast_manager_table.sql
```

**Step 2: Populate Initial Data**
```bash
cd TOOLS_SCRIPTS_TESTS/tools
python3 populate_broadcast_manager.py
```

**Step 3: Create Secrets**
```bash
./create_broadcast_secrets.sh
```

**Step 4: Deploy Cloud Run Service**
```bash
./deploy_broadcast_scheduler.sh
```

**Step 5: Create Cloud Scheduler Job**
```bash
gcloud scheduler jobs create http broadcast-scheduler-daily \
    --location=us-central1 \
    --schedule="0 0 * * *" \
    --uri="https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app/api/broadcast/execute" \
    --http-method=POST \
    --oidc-service-account-email="291176869049-compute@developer.gserviceaccount.com" \
    --oidc-token-audience="https://gcbroadcastscheduler-10-26-291176869049.us-central1.run.app" \
    --headers="Content-Type=application/json" \
    --message-body='{"source":"cloud_scheduler"}' \
    --time-zone="UTC"
```

**Step 6: Test Manual Execution**
```bash
gcloud scheduler jobs run broadcast-scheduler-daily --location=us-central1
```

**Step 7: Monitor Logs**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbroadcastscheduler-10-26" \
    --limit=50 \
    --format=json
```

---

## Summary

This architecture provides a **robust, scalable, and maintainable** solution for broadcast message management with the following key benefits:

✅ **Automated Scheduling**: Cron-based broadcasts run reliably without manual intervention
✅ **Manual Control**: Clients can trigger rebroadcasts via website with rate limiting
✅ **Dynamic Configuration**: Intervals adjustable via Secret Manager without redeployment
✅ **Modular Design**: Clear separation of concerns across 5 specialized components
✅ **Error Resilience**: Comprehensive error handling and automatic retry logic
✅ **Monitoring**: Full observability via Cloud Logging and custom metrics
✅ **Security**: OIDC authentication, JWT tokens, and SQL injection prevention
✅ **Cost Optimized**: Min instances = 0, only runs when needed

**Next Steps:**
1. Review and approve this architecture
2. Begin Phase 1 (Database Setup)
3. Proceed through migration phases systematically
4. Monitor and iterate based on production feedback

---

**End of Document**
