-- ============================================================================
-- Migration: 004 - Add Unique Constraint on Payment ID (Race Condition Fix)
-- ============================================================================
-- Purpose: Prevent duplicate payment processing via atomic UPSERT operations
-- Vulnerability: C-04 (Race Condition in Payment Processing)
-- Created: 2025-11-18
-- Author: PGP Security Audit Implementation
--
-- This migration adds a unique constraint on the payment_id column in the
-- processed_payments table to ensure that each payment can only be marked
-- as processed once, even under high concurrency.
--
-- Security Impact:
-- - Prevents duplicate subscriptions from race conditions
-- - Enables atomic mark_payment_processed_atomic() method
-- - No performance impact (constraint uses existing index)
--
-- Dependencies:
-- - Requires processed_payments table to exist
-- - Assumes no duplicate payment_ids currently exist (check before running)
-- ============================================================================

\echo '🔒 [MIGRATION 004] Adding unique constraint on payment_id...'

-- Step 1: Check for existing duplicates (should be 0)
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT payment_id, COUNT(*) as cnt
        FROM processed_payments
        GROUP BY payment_id
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_count > 0 THEN
        RAISE EXCEPTION '❌ Found % duplicate payment_ids. Clean up duplicates before running this migration.', duplicate_count;
    END IF;

    RAISE NOTICE '✅ No duplicate payment_ids found. Safe to proceed.';
END $$;

-- Step 2: Add unique constraint on payment_id
-- This allows INSERT...ON CONFLICT (payment_id) DO NOTHING
ALTER TABLE processed_payments
ADD CONSTRAINT unique_payment_id UNIQUE (payment_id);

\echo '✅ [MIGRATION 004] Unique constraint added successfully'

-- Step 3: Verify constraint was created
DO $$
DECLARE
    constraint_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'unique_payment_id'
        AND conrelid = 'processed_payments'::regclass
    ) INTO constraint_exists;

    IF constraint_exists THEN
        RAISE NOTICE '✅ Constraint unique_payment_id verified';
    ELSE
        RAISE EXCEPTION '❌ Constraint unique_payment_id not found after creation';
    END IF;
END $$;

-- Step 4: Display constraint info
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conname = 'unique_payment_id';

\echo '🎉 [MIGRATION 004] Complete! Race condition protection enabled.'
\echo '📝 Note: Use mark_payment_processed_atomic() method for idempotent payment processing'

-- ============================================================================
-- Migration Complete
-- ============================================================================
