-- Migration: Add actual_eth_amount columns to tracking tables
-- Date: 2025-11-02
-- Purpose: Store ACTUAL ETH from NowPayments alongside estimates
-- Issue: GCHostPay3 receiving wrong from_amount (ChangeNow estimates vs actual NowPayments outcome)

BEGIN;

-- Add column to split_payout_request
ALTER TABLE split_payout_request
ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Add column to split_payout_hostpay
ALTER TABLE split_payout_hostpay
ADD COLUMN IF NOT EXISTS actual_eth_amount NUMERIC(20,18) DEFAULT 0;

-- Add validation constraints
ALTER TABLE split_payout_request
ADD CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0);

ALTER TABLE split_payout_hostpay
ADD CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_split_payout_request_actual_eth
ON split_payout_request(actual_eth_amount)
WHERE actual_eth_amount > 0;

CREATE INDEX IF NOT EXISTS idx_split_payout_hostpay_actual_eth
ON split_payout_hostpay(actual_eth_amount)
WHERE actual_eth_amount > 0;

COMMIT;

-- Verification queries
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'split_payout_request'
  AND column_name = 'actual_eth_amount';

SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'split_payout_hostpay'
  AND column_name = 'actual_eth_amount';
