-- ============================================================================
-- Migration 005: Create Transaction Limits Table
-- ============================================================================
-- Security Fix: C-05 - Missing Transaction Amount Limits
-- OWASP: A04:2021 - Insecure Design
-- CWE: CWE-770 (Allocation of Resources Without Limits)
--
-- Purpose:
--   Create transaction_limits table to enforce per-transaction, daily,
--   and monthly transaction limits to prevent fraud and money laundering.
--
-- Regulatory Compliance:
--   - PCI DSS: Transaction monitoring requirements
--   - SOC 2: Financial transaction controls
--   - FINRA: Anti-money laundering (AML) requirements
--
-- Tables Created:
--   - transaction_limits: Configurable limit thresholds
--
-- Usage:
--   psql -h $DB_HOST -U postgres -d pgp-live-db -f 005_create_transaction_limits.sql
--
-- Rollback:
--   See 005_rollback.sql
-- ============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ============================================================================
-- Create transaction_limits table
-- ============================================================================

CREATE TABLE IF NOT EXISTS transaction_limits (
    -- Primary key
    limit_type VARCHAR(50) PRIMARY KEY,

    -- Limit amount in USD
    limit_amount_usd DECIMAL(10, 2) NOT NULL,

    -- Validation constraints
    CHECK (limit_amount_usd >= 0.00),
    CHECK (limit_amount_usd <= 999999.99),

    -- Metadata
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_transaction_limits_type
ON transaction_limits (limit_type);

-- Add comment
COMMENT ON TABLE transaction_limits IS
'Configurable transaction amount limits for fraud prevention and AML compliance';

COMMENT ON COLUMN transaction_limits.limit_type IS
'Type of limit: per_transaction_max, daily_per_user_max, monthly_per_user_max';

COMMENT ON COLUMN transaction_limits.limit_amount_usd IS
'Maximum amount allowed in USD';

COMMENT ON COLUMN transaction_limits.description IS
'Human-readable description of this limit';

-- ============================================================================
-- Insert default limits
-- ============================================================================

-- Delete existing rows (idempotent migration)
DELETE FROM transaction_limits WHERE limit_type IN (
    'per_transaction_max',
    'daily_per_user_max',
    'monthly_per_user_max',
    'large_transaction_threshold'
);

-- Insert default limits
INSERT INTO transaction_limits (limit_type, limit_amount_usd, description)
VALUES
    (
        'per_transaction_max',
        1000.00,
        'Maximum amount allowed for a single transaction (prevents large fraud)'
    ),
    (
        'daily_per_user_max',
        5000.00,
        'Maximum total amount a user can transact in 24 hours (rolling window)'
    ),
    (
        'monthly_per_user_max',
        25000.00,
        'Maximum total amount a user can transact in 30 days (rolling window)'
    ),
    (
        'large_transaction_threshold',
        500.00,
        'Transactions above this amount trigger additional monitoring alerts'
    );

-- ============================================================================
-- Verification
-- ============================================================================

-- Verify table was created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'transaction_limits'
    ) THEN
        RAISE EXCEPTION 'Migration failed: transaction_limits table not created';
    END IF;

    -- Verify default limits were inserted
    IF (SELECT COUNT(*) FROM transaction_limits) < 4 THEN
        RAISE EXCEPTION 'Migration failed: Default limits not inserted';
    END IF;

    RAISE NOTICE '✅ Migration 005 verification passed';
END $$;

COMMIT;

-- ============================================================================
-- Migration Complete
-- ============================================================================

\echo '============================================'
\echo '✅ Migration 005: Transaction Limits Created'
\echo '============================================'
\echo ''
\echo 'Tables Created:'
\echo '  - transaction_limits (4 default limits)'
\echo ''
\echo 'Default Limits:'
\echo '  - Per Transaction Max:     $1,000.00'
\echo '  - Daily Per User Max:      $5,000.00'
\echo '  - Monthly Per User Max:    $25,000.00'
\echo '  - Large Transaction Alert: $500.00'
\echo ''
\echo 'Next Steps:'
\echo '  1. Update BaseDatabaseManager with amount validation methods'
\echo '  2. Update PGP_ORCHESTRATOR_v1 to enforce limits'
\echo '  3. Create monitoring alerts for limit violations'
\echo '  4. Test with various transaction amounts'
\echo ''
\echo '============================================'
