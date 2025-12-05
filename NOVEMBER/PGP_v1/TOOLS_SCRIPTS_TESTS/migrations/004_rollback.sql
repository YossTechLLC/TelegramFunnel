-- ============================================================================
-- Rollback: 004 - Remove Unique Constraint on Payment ID
-- ============================================================================
-- Purpose: Rollback migration 004 if needed
-- Created: 2025-11-18
--
-- WARNING: This will allow duplicate payment processing again!
-- Only use for rollback in case of issues.
-- ============================================================================

\echo '🔄 [ROLLBACK 004] Removing unique constraint on payment_id...'

-- Remove unique constraint
ALTER TABLE processed_payments
DROP CONSTRAINT IF EXISTS unique_payment_id;

\echo '⚠️ [ROLLBACK 004] Unique constraint removed'
\echo '⚠️ WARNING: Race condition protection disabled!'
\echo '⚠️ Duplicate payment processing is now possible again'

-- Verify constraint was removed
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

    IF NOT constraint_exists THEN
        RAISE NOTICE '✅ Constraint unique_payment_id successfully removed';
    ELSE
        RAISE EXCEPTION '❌ Constraint unique_payment_id still exists after removal';
    END IF;
END $$;

\echo '🔄 [ROLLBACK 004] Complete'

-- ============================================================================
-- Rollback Complete
-- ============================================================================
