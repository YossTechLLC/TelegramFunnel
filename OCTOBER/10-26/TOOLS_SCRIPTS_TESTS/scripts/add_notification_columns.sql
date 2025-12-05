-- Add notification columns to main_clients_database
-- Purpose: Enable channel owners to receive payment notifications
-- Version: 1.0
-- Date: 2025-11-11
-- Author: Claude (Notification Management Architecture Implementation)

BEGIN;

-- Add notification_status column (enables/disables notifications)
ALTER TABLE main_clients_database
ADD COLUMN IF NOT EXISTS notification_status BOOLEAN DEFAULT false NOT NULL;

-- Add notification_id column (Telegram user ID for notification recipient)
ALTER TABLE main_clients_database
ADD COLUMN IF NOT EXISTS notification_id BIGINT DEFAULT NULL;

-- Add column comments for documentation
COMMENT ON COLUMN main_clients_database.notification_status IS
'Enable/disable payment notifications for channel owner. Default false (disabled).';

COMMENT ON COLUMN main_clients_database.notification_id IS
'Telegram user ID to receive payment notifications. NULL if notifications disabled.';

-- Verify columns exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
        AND column_name = 'notification_status'
    ) THEN
        RAISE EXCEPTION 'Failed to create notification_status column';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
        AND column_name = 'notification_id'
    ) THEN
        RAISE EXCEPTION 'Failed to create notification_id column';
    END IF;

    RAISE NOTICE '✅ Successfully added notification columns to main_clients_database';
END $$;

COMMIT;
