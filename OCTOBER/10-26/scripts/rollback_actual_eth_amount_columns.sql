-- Rollback script for actual_eth_amount migration
-- Date: 2025-11-02
-- Use only if migration needs to be reverted

BEGIN;

-- Drop indexes
DROP INDEX IF EXISTS idx_split_payout_hostpay_actual_eth;
DROP INDEX IF EXISTS idx_split_payout_request_actual_eth;

-- Drop constraints
ALTER TABLE split_payout_hostpay
DROP CONSTRAINT IF EXISTS actual_eth_positive;

ALTER TABLE split_payout_request
DROP CONSTRAINT IF EXISTS actual_eth_positive;

-- Drop columns
ALTER TABLE split_payout_hostpay
DROP COLUMN IF EXISTS actual_eth_amount;

ALTER TABLE split_payout_request
DROP COLUMN IF EXISTS actual_eth_amount;

COMMIT;

-- Verification
SELECT column_name
FROM information_schema.columns
WHERE table_name IN ('split_payout_request', 'split_payout_hostpay')
  AND column_name = 'actual_eth_amount';
-- Should return no rows if rollback successful
