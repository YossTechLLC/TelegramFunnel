-- ============================================================================
-- Migration 005 Rollback: Drop Transaction Limits Table
-- ============================================================================
-- Reverses migration 005 by dropping the transaction_limits table.
--
-- ⚠️ WARNING: This will permanently delete all transaction limit configurations!
--
-- Usage:
--   psql -h $DB_HOST -U postgres -d pgp-live-db -f 005_rollback.sql
-- ============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- Drop transaction_limits table
DROP TABLE IF EXISTS transaction_limits CASCADE;

-- Verification
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'transaction_limits'
    ) THEN
        RAISE EXCEPTION 'Rollback failed: transaction_limits table still exists';
    END IF;

    RAISE NOTICE '✅ Rollback 005 verification passed';
END $$;

COMMIT;

\echo '============================================'
\echo '✅ Migration 005 Rollback Complete'
\echo '============================================'
\echo ''
\echo 'Dropped Tables:'
\echo '  - transaction_limits'
\echo ''
\echo '⚠️  Transaction limit enforcement is now disabled!'
\echo '============================================'
