-- Create broadcast_manager table
-- Purpose: Track broadcast scheduling and history for open/closed channel pairs
-- Version: 1.0
-- Date: 2025-11-11
-- Author: Claude Code
--
-- This table manages automated and manual broadcast scheduling for Telegram channel messages.
-- Each row represents a channel pair (open_channel_id, closed_channel_id) with tracking for:
-- - Last broadcast time and next scheduled broadcast time
-- - Broadcast statistics (total, successful, failed)
-- - Manual trigger tracking and rate limiting
-- - Error tracking and auto-disable after consecutive failures

BEGIN;

-- Create broadcast_manager table
CREATE TABLE IF NOT EXISTS broadcast_manager (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Keys & Relationships
    client_id UUID NOT NULL,
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
    CONSTRAINT fk_broadcast_client
        FOREIGN KEY (client_id)
        REFERENCES registered_users(user_id)
        ON DELETE CASCADE,

    -- Note: No FK on open_channel_id because main_clients_database doesn't have unique constraint
    -- Orphaned broadcasts will be handled by application logic

    CONSTRAINT unique_channel_pair
        UNIQUE (open_channel_id, closed_channel_id),

    CONSTRAINT valid_broadcast_status
        CHECK (broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped'))
);

-- Create indexes for performance
-- Index on next_send_time for scheduled broadcast queries (only active broadcasts)
CREATE INDEX idx_broadcast_next_send
    ON broadcast_manager(next_send_time)
    WHERE is_active = true;

-- Index on client_id for user-specific queries
CREATE INDEX idx_broadcast_client
    ON broadcast_manager(client_id);

-- Index on broadcast_status for status-based queries (only active broadcasts)
CREATE INDEX idx_broadcast_status
    ON broadcast_manager(broadcast_status)
    WHERE is_active = true;

-- Index on open_channel_id for channel-specific lookups
CREATE INDEX idx_broadcast_open_channel
    ON broadcast_manager(open_channel_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_broadcast_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at on row updates
CREATE TRIGGER trigger_broadcast_updated_at
    BEFORE UPDATE ON broadcast_manager
    FOR EACH ROW
    EXECUTE FUNCTION update_broadcast_updated_at();

-- Add comments for documentation
COMMENT ON TABLE broadcast_manager IS
'Tracks broadcast scheduling and history for Telegram channel message broadcasts. Manages both automated (daily) and manual (on-demand) broadcasts with rate limiting and error tracking.';

COMMENT ON COLUMN broadcast_manager.id IS
'Unique identifier for the broadcast schedule entry (UUID v4)';

COMMENT ON COLUMN broadcast_manager.client_id IS
'Foreign key to registered_users table - identifies the channel owner (for authorization)';

COMMENT ON COLUMN broadcast_manager.open_channel_id IS
'Telegram channel ID for subscription tier messages (open channel)';

COMMENT ON COLUMN broadcast_manager.closed_channel_id IS
'Telegram channel ID for donation messages (closed/premium channel)';

COMMENT ON COLUMN broadcast_manager.last_sent_time IS
'Timestamp of the last successful broadcast to this channel pair';

COMMENT ON COLUMN broadcast_manager.next_send_time IS
'Timestamp when the next broadcast should be sent. Set to NOW() for immediate send on next cron run.';

COMMENT ON COLUMN broadcast_manager.broadcast_status IS
'Current status: pending (waiting for next_send_time), in_progress (currently sending), completed (success), failed (error occurred), skipped (manually disabled)';

COMMENT ON COLUMN broadcast_manager.last_manual_trigger_time IS
'Timestamp of the last manual trigger from website (used for 5-minute rate limiting)';

COMMENT ON COLUMN broadcast_manager.manual_trigger_count IS
'Total number of times user has manually triggered this broadcast from website';

COMMENT ON COLUMN broadcast_manager.total_broadcasts IS
'Total number of broadcast attempts (successful + failed)';

COMMENT ON COLUMN broadcast_manager.successful_broadcasts IS
'Number of successful broadcasts (both channels sent successfully)';

COMMENT ON COLUMN broadcast_manager.failed_broadcasts IS
'Number of failed broadcasts (one or both channels failed)';

COMMENT ON COLUMN broadcast_manager.last_error_message IS
'Most recent error message from failed broadcast';

COMMENT ON COLUMN broadcast_manager.last_error_time IS
'Timestamp of most recent broadcast failure';

COMMENT ON COLUMN broadcast_manager.consecutive_failures IS
'Number of consecutive failed broadcasts (resets to 0 on success). Auto-disables at 5 failures.';

COMMENT ON COLUMN broadcast_manager.is_active IS
'Enable/disable broadcasts for this channel pair. Automatically set to false after 5 consecutive failures.';

COMMENT ON COLUMN broadcast_manager.created_at IS
'Timestamp when this broadcast schedule entry was created';

COMMENT ON COLUMN broadcast_manager.updated_at IS
'Timestamp of last update to this entry (auto-updated via trigger)';

-- Verification query to confirm table structure
DO $$
BEGIN
    -- Verify table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'broadcast_manager'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create broadcast_manager table';
    END IF;

    -- Verify all indexes exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'broadcast_manager'
        AND indexname = 'idx_broadcast_next_send'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create idx_broadcast_next_send index';
    END IF;

    -- Verify trigger exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trigger_broadcast_updated_at'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create trigger_broadcast_updated_at';
    END IF;

    RAISE NOTICE '✅ Successfully created broadcast_manager table with all indexes, constraints, and triggers';
END $$;

COMMIT;
