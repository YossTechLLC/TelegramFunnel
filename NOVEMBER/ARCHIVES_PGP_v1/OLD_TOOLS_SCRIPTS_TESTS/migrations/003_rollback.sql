-- ============================================================================
-- Rollback 003: Restore gcwebhook1_* column names
-- ============================================================================
-- Purpose: Revert migration 003 if needed
-- ============================================================================

BEGIN;

-- Step 1: Restore original column names
ALTER TABLE processed_payments
    RENAME COLUMN pgp_orchestrator_processed TO gcwebhook1_processed;

ALTER TABLE processed_payments
    RENAME COLUMN pgp_orchestrator_processed_at TO gcwebhook1_processed_at;

-- Step 2: Restore original index
DROP INDEX IF EXISTS idx_pgp_orchestrator_processed;
CREATE INDEX IF NOT EXISTS idx_gcwebhook1_processed
    ON processed_payments(gcwebhook1_processed);

-- Step 3: Restore original column comments
COMMENT ON COLUMN processed_payments.gcwebhook1_processed IS
    'Flag indicating if GCWebhook1 successfully processed this payment';

COMMENT ON COLUMN processed_payments.gcwebhook1_processed_at IS
    'Timestamp when GCWebhook1 processed this payment';

COMMIT;
