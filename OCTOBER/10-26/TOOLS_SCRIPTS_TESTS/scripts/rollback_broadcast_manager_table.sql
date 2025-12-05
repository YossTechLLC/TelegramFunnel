-- Rollback broadcast_manager table creation
-- Purpose: Remove broadcast_manager table and all dependencies
-- Version: 1.0
-- Date: 2025-11-11
-- Author: Claude Code
--
-- This script safely removes the broadcast_manager table, its triggers, functions, and indexes.
-- Use this script if you need to revert the migration or start fresh.
-- WARNING: This will delete all broadcast history and scheduling data!

BEGIN;

-- Drop trigger first (must be dropped before function)
DROP TRIGGER IF EXISTS trigger_broadcast_updated_at ON broadcast_manager;

-- Drop trigger function
DROP FUNCTION IF EXISTS update_broadcast_updated_at();

-- Drop indexes (CASCADE not needed for indexes, but doesn't hurt)
DROP INDEX IF EXISTS idx_broadcast_next_send;
DROP INDEX IF EXISTS idx_broadcast_user;
DROP INDEX IF EXISTS idx_broadcast_status;
DROP INDEX IF EXISTS idx_broadcast_open_channel;

-- Drop table with CASCADE to remove foreign key references
DROP TABLE IF EXISTS broadcast_manager CASCADE;

-- Verify table is dropped
DO $$
BEGIN
    -- Check if table still exists
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'broadcast_manager'
    ) THEN
        RAISE EXCEPTION '❌ Failed to drop broadcast_manager table';
    END IF;

    -- Check if trigger function still exists
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'update_broadcast_updated_at'
    ) THEN
        RAISE EXCEPTION '❌ Failed to drop update_broadcast_updated_at function';
    END IF;

    -- Check if any indexes still exist
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'broadcast_manager'
    ) THEN
        RAISE EXCEPTION '❌ Failed to drop all broadcast_manager indexes';
    END IF;

    RAISE NOTICE '✅ Successfully rolled back broadcast_manager table and all dependencies';
    RAISE NOTICE '📋 All broadcast history and scheduling data has been removed';
END $$;

COMMIT;
