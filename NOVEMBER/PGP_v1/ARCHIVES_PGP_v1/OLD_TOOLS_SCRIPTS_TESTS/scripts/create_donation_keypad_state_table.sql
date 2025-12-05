-- Create donation_keypad_state table
-- Purpose: Store donation keypad input state to enable stateless horizontal scaling
-- Version: 1.0
-- Date: 2025-11-13
-- Author: Claude Code
--
-- This table stores the current state of donation amount input for each user.
-- Replaces in-memory state dictionary to allow PGP_DONATIONS_v1 to scale horizontally.
-- Each row represents a user's current donation input session with:
-- - The amount they've entered so far (as string to preserve decimal precision)
-- - Which channel they're donating to
-- - Whether they've entered a decimal point yet
-- - Automatic cleanup of stale states (> 1 hour old)

BEGIN;

-- Create donation_keypad_state table
CREATE TABLE IF NOT EXISTS donation_keypad_state (
    -- Primary Key
    user_id BIGINT PRIMARY KEY,
        -- Telegram user_id is BIGINT (can be negative for channels)

    -- Donation Session Data
    channel_id TEXT NOT NULL,
        -- Telegram channel ID (e.g., "-1003268562225")
    current_amount TEXT NOT NULL DEFAULT '',
        -- Current amount entered as string (e.g., "25.00", "5.", "100")
        -- Stored as TEXT to preserve decimal precision during input
    decimal_entered BOOLEAN DEFAULT false NOT NULL,
        -- Whether user has entered a decimal point yet (prevents multiple decimals)

    -- State Tracking
    state_type VARCHAR(20) DEFAULT 'keypad_input' NOT NULL,
        -- Values: 'keypad_input', 'text_input', 'awaiting_confirmation'
        -- Future-proofing for different donation input methods

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT valid_state_type
        CHECK (state_type IN ('keypad_input', 'text_input', 'awaiting_confirmation')),

    CONSTRAINT valid_amount_format
        CHECK (
            current_amount ~ '^[0-9]*\.?[0-9]*$'  -- Regex: digits, optional decimal, digits
            AND length(current_amount) <= 10       -- Max 10 characters (e.g., "9999.99")
        )
);

-- Create indexes for performance

-- Index on updated_at for cleanup queries (find stale states)
CREATE INDEX idx_donation_state_updated_at
    ON donation_keypad_state(updated_at);

-- Index on channel_id for channel-specific queries (optional, for future features)
CREATE INDEX idx_donation_state_channel
    ON donation_keypad_state(channel_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_donation_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at on row updates
CREATE TRIGGER trigger_donation_state_updated_at
    BEFORE UPDATE ON donation_keypad_state
    FOR EACH ROW
    EXECUTE FUNCTION update_donation_state_updated_at();

-- Create cleanup function to remove stale states (older than 1 hour)
-- This prevents the table from growing indefinitely with abandoned sessions
CREATE OR REPLACE FUNCTION cleanup_stale_donation_states()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete states older than 1 hour
    DELETE FROM donation_keypad_state
    WHERE updated_at < NOW() - INTERVAL '1 hour';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Log cleanup results
    RAISE NOTICE '🧹 Cleaned up % stale donation keypad states', deleted_count;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON TABLE donation_keypad_state IS
'Stores donation keypad input state to enable stateless horizontal scaling of PGP_DONATIONS_v1. Replaces in-memory user_states dictionary. States older than 1 hour are automatically cleaned up.';

COMMENT ON COLUMN donation_keypad_state.user_id IS
'Telegram user ID (primary key). Each user can have only one active donation input session at a time.';

COMMENT ON COLUMN donation_keypad_state.channel_id IS
'Telegram channel ID the user is donating to (e.g., "-1003268562225")';

COMMENT ON COLUMN donation_keypad_state.current_amount IS
'Current amount entered as string (e.g., "25.00", "5.", "100"). Stored as TEXT to preserve decimal precision during keypad input.';

COMMENT ON COLUMN donation_keypad_state.decimal_entered IS
'Whether user has entered a decimal point yet. Used to prevent multiple decimal points in amount (e.g., "25..50" is invalid).';

COMMENT ON COLUMN donation_keypad_state.state_type IS
'Type of donation input state: keypad_input (numeric keypad), text_input (typed amount), awaiting_confirmation (waiting for user to confirm amount)';

COMMENT ON COLUMN donation_keypad_state.created_at IS
'Timestamp when this donation input session was started';

COMMENT ON COLUMN donation_keypad_state.updated_at IS
'Timestamp of last keypad input or state update (auto-updated via trigger). Used to identify stale sessions for cleanup.';

COMMENT ON FUNCTION cleanup_stale_donation_states() IS
'Deletes donation keypad states older than 1 hour. Should be called periodically (e.g., via cron) to prevent table bloat from abandoned donation sessions.';

-- Verification query to confirm table structure
DO $$
BEGIN
    -- Verify table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'donation_keypad_state'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create donation_keypad_state table';
    END IF;

    -- Verify all indexes exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'donation_keypad_state'
        AND indexname = 'idx_donation_state_updated_at'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create idx_donation_state_updated_at index';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'donation_keypad_state'
        AND indexname = 'idx_donation_state_channel'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create idx_donation_state_channel index';
    END IF;

    -- Verify trigger exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trigger_donation_state_updated_at'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create trigger_donation_state_updated_at';
    END IF;

    -- Verify cleanup function exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'cleanup_stale_donation_states'
    ) THEN
        RAISE EXCEPTION '❌ Failed to create cleanup_stale_donation_states function';
    END IF;

    RAISE NOTICE '✅ Successfully created donation_keypad_state table with all indexes, constraints, triggers, and cleanup function';
END $$;

COMMIT;
