-- Migration: Fix NUMERIC precision overflow for token amounts
-- Date: 2025-11-04
-- Issue: NUMERIC(12,8) cannot store large quantities of low-value tokens (e.g., SHIB)
-- Root Cause: split_payout_request.to_amount = 596,726 SHIB exceeds NUMERIC(12,8) max of 9999.99999999
-- Solution: Increase precision to NUMERIC(20,18) for all amount fields

-- Database: client_table
-- Affected Tables: split_payout_request, split_payout_que, split_payout_hostpay

BEGIN;

-- ============================================================================
-- Table: split_payout_request
-- ============================================================================

-- Fix to_amount: NUMERIC(12,8) → NUMERIC(20,18)
-- This field stores token quantities (e.g., SHIB, DOGE) which can be in millions
ALTER TABLE split_payout_request
ALTER COLUMN to_amount TYPE NUMERIC(20,18);

COMMENT ON COLUMN split_payout_request.to_amount IS 'Target token amount - NUMERIC(20,18) to support large quantities of low-value tokens';

-- Fix from_amount: NUMERIC(10,2) → NUMERIC(20,18)
-- This field stores USDT amounts which need higher precision for crypto conversions
ALTER TABLE split_payout_request
ALTER COLUMN from_amount TYPE NUMERIC(20,18);

COMMENT ON COLUMN split_payout_request.from_amount IS 'Source USDT amount - NUMERIC(20,18) for precision in crypto conversions';


-- ============================================================================
-- Table: split_payout_que (aka split_payout_hostpay)
-- ============================================================================

-- Fix from_amount: NUMERIC(12,8) → NUMERIC(20,18)
-- This field stores ETH amounts from ChangeNow
ALTER TABLE split_payout_que
ALTER COLUMN from_amount TYPE NUMERIC(20,18);

COMMENT ON COLUMN split_payout_que.from_amount IS 'ChangeNow from_amount (ETH) - NUMERIC(20,18) for precision';

-- Optionally increase to_amount: NUMERIC(24,12) → NUMERIC(30,18)
-- This field stores client token amounts which can be extremely large (SHIB, PEPE, etc.)
ALTER TABLE split_payout_que
ALTER COLUMN to_amount TYPE NUMERIC(30,18);

COMMENT ON COLUMN split_payout_que.to_amount IS 'Client token amount - NUMERIC(30,18) to support extreme quantities of micro-value tokens';


-- ============================================================================
-- Table: split_payout_hostpay
-- ============================================================================

-- Fix from_amount: NUMERIC(12,8) → NUMERIC(20,18)
-- This field stores ETH amounts
ALTER TABLE split_payout_hostpay
ALTER COLUMN from_amount TYPE NUMERIC(20,18);

COMMENT ON COLUMN split_payout_hostpay.from_amount IS 'ETH amount - NUMERIC(20,18) for precision';


COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Verify all changes
SELECT
    table_name,
    column_name,
    data_type,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name IN ('split_payout_request', 'split_payout_que', 'split_payout_hostpay')
AND column_name LIKE '%amount%'
ORDER BY table_name, column_name;

-- Expected Results:
-- split_payout_hostpay.actual_eth_amount     NUMERIC(20,18) ✅
-- split_payout_hostpay.from_amount            NUMERIC(20,18) ✅ FIXED
-- split_payout_que.actual_eth_amount          NUMERIC(20,18) ✅ (if exists)
-- split_payout_que.from_amount                NUMERIC(20,18) ✅ FIXED
-- split_payout_que.to_amount                  NUMERIC(30,18) ✅ FIXED
-- split_payout_request.actual_eth_amount      NUMERIC(20,18) ✅
-- split_payout_request.from_amount            NUMERIC(20,18) ✅ FIXED
-- split_payout_request.to_amount              NUMERIC(20,18) ✅ FIXED
