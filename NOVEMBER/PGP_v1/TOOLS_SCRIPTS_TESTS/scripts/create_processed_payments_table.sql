-- File: scripts/create_processed_payments_table.sql
-- Purpose: Create processed_payments table for idempotency tracking
-- Date: 2025-11-02

BEGIN;

-- Create table
CREATE TABLE IF NOT EXISTS processed_payments (
    -- Primary key: NowPayments payment_id (unique identifier)
    payment_id BIGINT PRIMARY KEY,

    -- Reference data for lookups and debugging
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,

    -- Processing state flags
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,

    -- Telegram invite state
    telegram_invite_sent BOOLEAN DEFAULT FALSE,
    telegram_invite_sent_at TIMESTAMP,
    telegram_invite_link TEXT,

    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT payment_id_positive CHECK (payment_id > 0),
    CONSTRAINT user_id_positive CHECK (user_id > 0)
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_processed_payments_user_channel
ON processed_payments(user_id, channel_id);

CREATE INDEX IF NOT EXISTS idx_processed_payments_invite_status
ON processed_payments(telegram_invite_sent);

CREATE INDEX IF NOT EXISTS idx_processed_payments_webhook1_status
ON processed_payments(gcwebhook1_processed);

CREATE INDEX IF NOT EXISTS idx_processed_payments_created_at
ON processed_payments(created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE processed_payments IS 'Tracks payment processing state for idempotency - prevents duplicate Telegram invites and payment accumulation';
COMMENT ON COLUMN processed_payments.payment_id IS 'NowPayments payment_id (unique identifier from IPN callback)';
COMMENT ON COLUMN processed_payments.gcwebhook1_processed IS 'Flag indicating if GCWebhook1 successfully processed this payment';
COMMENT ON COLUMN processed_payments.telegram_invite_sent IS 'Flag indicating if Telegram invite successfully sent to user';
COMMENT ON COLUMN processed_payments.telegram_invite_link IS 'The actual one-time invite link sent to user (for reference/debugging)';

COMMIT;

-- Verify table structure
\d processed_payments;

-- Verify indexes
\di processed_payments*;

-- Check initial count (should be 0)
SELECT COUNT(*) as initial_count FROM processed_payments;
