-- Add message ID tracking columns to broadcast_manager table
-- Purpose: Track last sent message IDs for deletion when resending
-- Date: 2025-01-14
-- Related: LIVETIME_BROADCAST_ONLY_CHECKLIST.md Phase 1

-- Add columns for tracking message IDs and timestamps
ALTER TABLE broadcast_manager
ADD COLUMN IF NOT EXISTS last_open_message_id BIGINT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS last_closed_message_id BIGINT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS last_open_message_sent_at TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS last_closed_message_sent_at TIMESTAMP DEFAULT NULL;

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_broadcast_manager_open_message
ON broadcast_manager(last_open_message_id)
WHERE last_open_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_broadcast_manager_closed_message
ON broadcast_manager(last_closed_message_id)
WHERE last_closed_message_id IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN broadcast_manager.last_open_message_id IS
'Telegram message ID of last subscription tier message sent to open channel';

COMMENT ON COLUMN broadcast_manager.last_closed_message_id IS
'Telegram message ID of last donation button message sent to closed channel';

COMMENT ON COLUMN broadcast_manager.last_open_message_sent_at IS
'Timestamp when last open channel message was sent';

COMMENT ON COLUMN broadcast_manager.last_closed_message_sent_at IS
'Timestamp when last closed channel message was sent';

-- Log completion
DO $$
BEGIN
  RAISE NOTICE '✅ Message tracking columns added successfully to broadcast_manager table';
END $$;
