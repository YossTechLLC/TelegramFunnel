-- ============================================================================
-- Add nowpayments_outcome_amount_usd column to private_channel_users_database
-- Part of: NowPayments Outcome Amount - PGP_ORCHESTRATOR_v1 Architecture Implementation
-- Date: 2025-11-02
-- ============================================================================

-- Step 1.1: Add new column for outcome USD amount
-- This column stores the ACTUAL USD value of the crypto payment received
-- Calculated by NP-Webhook using CoinGecko API at time of IPN callback

ALTER TABLE private_channel_users_database
ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount_usd DECIMAL(20, 8);

-- Verify column was added
\echo '✅ Column nowpayments_outcome_amount_usd added'

-- Step 1.2: Add index for faster payment_id lookups
-- This improves performance when NP-Webhook queries by payment_id

CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
ON private_channel_users_database(nowpayments_payment_id);

-- Verify index was created
\echo '✅ Index idx_nowpayments_payment_id created'

-- Step 1.3: Add documentation comment
-- Explains the purpose and source of this column

COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_amount_usd IS
'Actual USD value of outcome_amount calculated via CoinGecko API at time of IPN callback. This is the REAL amount received, not the declared subscription price.';

\echo '✅ Column comment added'

-- Verification Query: Show column details
\echo ''
\echo '📊 Verification: Column Details'
SELECT
    column_name,
    data_type,
    numeric_precision,
    numeric_scale,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'private_channel_users_database'
AND column_name = 'nowpayments_outcome_amount_usd';

-- Verification Query: Show index details
\echo ''
\echo '📊 Verification: Index Details'
\di idx_nowpayments_payment_id

-- Verification Query: Show column comment
\echo ''
\echo '📊 Verification: Column Comment'
SELECT
    column_name,
    col_description('private_channel_users_database'::regclass, ordinal_position) as column_comment
FROM information_schema.columns
WHERE table_name = 'private_channel_users_database'
AND column_name = 'nowpayments_outcome_amount_usd';

\echo ''
\echo '🎉 Database schema changes completed successfully!'
