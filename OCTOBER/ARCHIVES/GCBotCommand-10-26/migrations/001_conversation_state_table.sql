-- Migration 001: Create user_conversation_state table
-- Purpose: Store conversation state for stateless webhook operation
-- Date: 2025-11-12

-- Create table for storing conversation state
CREATE TABLE IF NOT EXISTS user_conversation_state (
    user_id BIGINT NOT NULL,
    conversation_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, conversation_type)
);

-- Create index on updated_at for cleanup queries
CREATE INDEX IF NOT EXISTS idx_conversation_state_updated ON user_conversation_state(updated_at);

-- Add comment on table
COMMENT ON TABLE user_conversation_state IS 'Stores conversation state for GCBotCommand webhook service';
COMMENT ON COLUMN user_conversation_state.user_id IS 'Telegram user ID';
COMMENT ON COLUMN user_conversation_state.conversation_type IS 'Type of conversation: database, donation, payment';
COMMENT ON COLUMN user_conversation_state.state_data IS 'JSON data storing current conversation state';
COMMENT ON COLUMN user_conversation_state.updated_at IS 'Last update timestamp';
