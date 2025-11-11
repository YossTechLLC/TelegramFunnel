-- Migration: Fix split_payout_hostpay unique_id column length
-- Date: 2025-11-04
-- Issue: UUID truncation causing batch conversion failures
-- Root Cause: VARCHAR(16) too short for "batch_{uuid}" format (needs 42 chars)
-- Fix: Extend to VARCHAR(64)

-- ============================================================================
-- CRITICAL BUG FIX
-- ============================================================================
-- Error: invalid input syntax for type uuid: "e0514205-7"
-- Cause: split_payout_hostpay.unique_id VARCHAR(16) truncates "batch_{uuid}"
-- Impact: 100% batch conversion failure rate
-- ============================================================================

BEGIN;

-- Display current schema before change
SELECT
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'split_payout_hostpay'
  AND column_name = 'unique_id';

-- Show existing truncated records
SELECT
    unique_id,
    LENGTH(unique_id) as id_length,
    cn_api_id,
    from_currency,
    created_at
FROM split_payout_hostpay
WHERE unique_id LIKE 'batch_%'
ORDER BY created_at DESC
LIMIT 10;

-- Extend unique_id column to support batch identifiers
-- varchar(16) → varchar(64)
-- This allows:
--   - Instant payments: 16 chars (backward compatible)
--   - Batch conversions: 42 chars ("batch_" + 36-char UUID)
--   - Future use cases: Up to 64 chars
ALTER TABLE split_payout_hostpay
ALTER COLUMN unique_id TYPE VARCHAR(64);

-- Verify change was applied
SELECT
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'split_payout_hostpay'
  AND column_name = 'unique_id';

-- Expected output after fix:
-- table_name            | column_name | data_type         | character_maximum_length | is_nullable
-- ----------------------+-------------+-------------------+--------------------------+-------------
-- split_payout_hostpay | unique_id   | character varying | 64                       | NO

COMMIT;

-- Post-migration verification
-- This query should now show full 42-character batch IDs (after new records are inserted)
SELECT
    unique_id,
    LENGTH(unique_id) as id_length,
    CASE
        WHEN LENGTH(unique_id) = 16 AND unique_id LIKE 'batch_%' THEN 'TRUNCATED (OLD)'
        WHEN LENGTH(unique_id) = 42 AND unique_id LIKE 'batch_%' THEN 'FULL BATCH ID (FIXED)'
        WHEN LENGTH(unique_id) = 16 AND unique_id NOT LIKE 'batch_%' THEN 'INSTANT PAYMENT'
        ELSE 'UNKNOWN FORMAT'
    END as id_type,
    created_at
FROM split_payout_hostpay
ORDER BY created_at DESC
LIMIT 20;

-- Success message
SELECT '✅ Migration completed successfully!' as status;
SELECT 'unique_id column extended from VARCHAR(16) to VARCHAR(64)' as change;
SELECT 'Batch conversions will now work correctly' as impact;
