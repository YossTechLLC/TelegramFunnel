-- Rollback message tracking columns from broadcast_manager table
-- Purpose: Remove message tracking functionality if rollback needed
-- Date: 2025-01-14
-- Related: LIVETIME_BROADCAST_ONLY_CHECKLIST.md Phase 1

-- Drop indexes first
DROP INDEX IF EXISTS idx_broadcast_manager_open_message;
DROP INDEX IF EXISTS idx_broadcast_manager_closed_message;

-- Drop columns
ALTER TABLE broadcast_manager
DROP COLUMN IF EXISTS last_open_message_id,
DROP COLUMN IF EXISTS last_closed_message_id,
DROP COLUMN IF EXISTS last_open_message_sent_at,
DROP COLUMN IF EXISTS last_closed_message_sent_at;

-- Log completion
DO $$
BEGIN
  RAISE NOTICE '🔄 Message tracking columns rolled back from broadcast_manager table';
END $$;
