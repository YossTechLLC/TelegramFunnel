-- ============================================================================
-- Migration 003: Rename gcwebhook1_* columns to pgp_orchestrator_*
-- ============================================================================
-- Date: 2025-01-15
-- Risk: MEDIUM - Column rename only, no data loss
-- Affected Tables: processed_payments
-- Affected Services: PGP_NP_IPN_v1, PGP_ORCHESTRATOR_v1
-- ============================================================================

BEGIN;

-- Step 1: Rename columns (PostgreSQL syntax)
ALTER TABLE processed_payments
    RENAME COLUMN gcwebhook1_processed TO pgp_orchestrator_processed;

ALTER TABLE processed_payments
    RENAME COLUMN gcwebhook1_processed_at TO pgp_orchestrator_processed_at;

-- Step 2: Rename index if it exists
DROP INDEX IF EXISTS idx_gcwebhook1_processed;
CREATE INDEX IF NOT EXISTS idx_pgp_orchestrator_processed
    ON processed_payments(pgp_orchestrator_processed);

-- Step 3: Update column comments
COMMENT ON COLUMN processed_payments.pgp_orchestrator_processed IS
    'Flag indicating if PGP_ORCHESTRATOR_v1 successfully processed this payment';

COMMENT ON COLUMN processed_payments.pgp_orchestrator_processed_at IS
    'Timestamp when PGP_ORCHESTRATOR_v1 processed this payment';

COMMIT;

-- Verification queries
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'processed_payments'
-- AND column_name LIKE '%orchestrator%';
