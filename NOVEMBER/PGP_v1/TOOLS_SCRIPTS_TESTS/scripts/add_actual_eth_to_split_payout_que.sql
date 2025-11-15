-- Migration: Add actual_eth_amount column to split_payout_que
-- Date: 2025-11-07
-- Purpose: Store ACTUAL ETH from NowPayments alongside ChangeNow estimates
-- Related: SPLIT_PAYOUT_TABLES_INC_ANALYSIS_REVIEW.md Issue 4

BEGIN;

-- Add column to split_payout_que
ALTER TABLE split_payout_que
ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Add validation constraint (non-negative values)
ALTER TABLE split_payout_que
ADD CONSTRAINT actual_eth_positive_que CHECK (actual_eth_amount >= 0);

-- Create index for performance (partial index on non-zero values)
CREATE INDEX IF NOT EXISTS idx_split_payout_que_actual_eth
ON split_payout_que(actual_eth_amount)
WHERE actual_eth_amount > 0;

-- Add comment for documentation
COMMENT ON COLUMN split_payout_que.actual_eth_amount IS
'ACTUAL ETH amount received from NowPayments outcome_amount (post network fees, pre TP fee)';

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Verification query 1: Check column exists
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'split_payout_que'
  AND column_name = 'actual_eth_amount';

-- Verification query 2: Check constraint exists
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name = 'actual_eth_positive_que';

-- Verification query 3: Check index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'split_payout_que'
  AND indexname = 'idx_split_payout_que_actual_eth';
