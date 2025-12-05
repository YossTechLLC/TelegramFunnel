-- Migration: Create failed_transactions table for GCHostPay3 error handling
-- Date: 2025-11-01
-- Author: TelePay Architecture
-- Purpose: Store ETH payment transactions that failed after 3 retry attempts

BEGIN;

-- Create failed_transactions table
CREATE TABLE IF NOT EXISTS failed_transactions (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Original Transaction Data
    unique_id VARCHAR(16) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    from_network VARCHAR(10) NOT NULL,
    from_amount NUMERIC(18, 8) NOT NULL,
    payin_address VARCHAR(100) NOT NULL,

    -- Context
    context VARCHAR(20) NOT NULL DEFAULT 'instant',

    -- Failure Metadata
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    last_error_details JSONB,

    -- Retry Tracking
    attempt_count INTEGER NOT NULL DEFAULT 3,
    last_attempt_timestamp TIMESTAMP NOT NULL,

    -- Status Tracking
    status VARCHAR(30) NOT NULL DEFAULT 'failed_pending_review',

    -- Recovery Metadata
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_attempt TIMESTAMP,
    recovery_tx_hash VARCHAR(100),
    recovered_at TIMESTAMP,
    recovered_by VARCHAR(50),

    -- Notes
    admin_notes TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_failed_transactions_unique_id ON failed_transactions(unique_id);
CREATE INDEX idx_failed_transactions_cn_api_id ON failed_transactions(cn_api_id);
CREATE INDEX idx_failed_transactions_status ON failed_transactions(status);
CREATE INDEX idx_failed_transactions_error_code ON failed_transactions(error_code);
CREATE INDEX idx_failed_transactions_created_at ON failed_transactions(created_at DESC);

-- Composite index for retry queries
CREATE INDEX idx_failed_transactions_retry ON failed_transactions(status, error_code, created_at)
WHERE status IN ('failed_retryable', 'retry_scheduled');

-- Add comment
COMMENT ON TABLE failed_transactions IS 'Stores ETH payment transactions that failed after 3 retry attempts for recovery and analysis';

COMMIT;

-- Verification query
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_name = 'failed_transactions'
ORDER BY ordinal_position;

-- ROLLBACK SCRIPT (for emergency use):
-- BEGIN;
-- DROP TABLE IF EXISTS failed_transactions CASCADE;
-- COMMIT;
