-- Rollback notification columns from main_clients_database
-- Purpose: Remove notification feature columns if needed
-- Version: 1.0
-- Date: 2025-11-11
-- Author: Claude (Notification Management Architecture Implementation)

BEGIN;

-- Drop notification columns (if they exist)
ALTER TABLE main_clients_database
DROP COLUMN IF EXISTS notification_status,
DROP COLUMN IF EXISTS notification_id;

-- Verify columns removed
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
        AND column_name IN ('notification_status', 'notification_id')
    ) THEN
        RAISE EXCEPTION 'Failed to remove notification columns';
    END IF;

    RAISE NOTICE '✅ Successfully removed notification columns from main_clients_database';
END $$;

COMMIT;
