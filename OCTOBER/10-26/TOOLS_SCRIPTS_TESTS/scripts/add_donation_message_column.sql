-- Migration: Add closed_channel_donation_message column
-- Created: 2025-11-11
-- Purpose: Allow clients to customize donation messages in closed channels
-- Reference: DONATION_MESSAGE_ARCHITECTURE.md

BEGIN;

-- Step 1: Add column with temporary NULL constraint
ALTER TABLE main_clients_database
ADD COLUMN closed_channel_donation_message VARCHAR(256);

-- Step 2: Set default message for all existing channels
UPDATE main_clients_database
SET closed_channel_donation_message = 'Enjoying the content? Consider making a donation to help us continue providing quality content. Click the button below to donate any amount you choose.'
WHERE closed_channel_donation_message IS NULL;

-- Step 3: Add NOT NULL constraint
ALTER TABLE main_clients_database
ALTER COLUMN closed_channel_donation_message SET NOT NULL;

-- Step 4: Add check constraint for minimum length (at least 1 character)
ALTER TABLE main_clients_database
ADD CONSTRAINT check_donation_message_not_empty
CHECK (LENGTH(TRIM(closed_channel_donation_message)) > 0);

-- Step 5: Add check constraint for maximum length (enforced by VARCHAR(256))
-- (This is already enforced by VARCHAR(256), but documenting for clarity)

COMMIT;

-- Verification queries
SELECT
    COUNT(*) as total_channels,
    COUNT(closed_channel_donation_message) as channels_with_message,
    AVG(LENGTH(closed_channel_donation_message)) as avg_message_length
FROM main_clients_database;

-- Sample data check
SELECT
    open_channel_id,
    closed_channel_id,
    closed_channel_title,
    LEFT(closed_channel_donation_message, 50) || '...' as message_preview
FROM main_clients_database
LIMIT 5;
