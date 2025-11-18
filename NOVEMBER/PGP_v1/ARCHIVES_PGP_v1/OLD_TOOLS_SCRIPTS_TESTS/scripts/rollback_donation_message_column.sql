-- Rollback: Remove closed_channel_donation_message column
-- Created: 2025-11-11
-- Use only if migration needs to be reverted
-- ⚠️ WARNING: This will permanently delete all custom donation messages

BEGIN;

-- Drop check constraint
ALTER TABLE main_clients_database
DROP CONSTRAINT IF EXISTS check_donation_message_not_empty;

-- Drop column
ALTER TABLE main_clients_database
DROP COLUMN IF EXISTS closed_channel_donation_message;

COMMIT;

-- Verification
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'main_clients_database'
  AND column_name = 'closed_channel_donation_message';
-- Should return 0 rows after rollback
