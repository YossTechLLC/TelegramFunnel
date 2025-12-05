-- Migration: Fix NUMERIC precision overflow for token amounts (CORRECTED)
-- Date: 2025-11-04
-- Issue: NUMERIC(12,8) cannot store large quantities of low-value tokens (e.g., SHIB)
-- Root Cause: split_payout_request.to_amount = 596,726 SHIB exceeds NUMERIC(12,8) max of 9999.99999999
-- Solution: Use appropriate precision based on data type

-- Database: client_table
-- Affected Tables: split_payout_request, split_payout_que, split_payout_hostpay

-- Data Analysis Results:
-- split_payout_request.from_amount: MAX=5335 (USDT values) → NUMERIC(20,8)
-- split_payout_request.to_amount: MAX=4.6 (blocked by constraint!) → NUMERIC(30,8)
-- split_payout_que.from_amount: MAX=0.024 (ETH values) → NUMERIC(20,8)
-- split_payout_que.to_amount: MAX=1,352,956 (SHIB quantities) → NUMERIC(30,8)

BEGIN;

-- ============================================================================
-- Table: split_payout_request
-- ============================================================================

-- Fix to_amount: NUMERIC(12,8) → NUMERIC(30,8)
-- This field stores token quantities (e.g., SHIB, DOGE) which can be in millions
-- NUMERIC(30,8) = 22 digits before decimal + 8 after = up to 9,999,999,999,999,999,999,999.99999999
ALTER TABLE split_payout_request
ALTER COLUMN to_amount TYPE NUMERIC(30,8);

COMMENT ON COLUMN split_payout_request.to_amount IS 'Target token amount - NUMERIC(30,8) to support large quantities of low-value tokens (SHIB, DOGE, PEPE)';

-- Fix from_amount: NUMERIC(10,2) → NUMERIC(20,8)
-- This field stores USDT amounts
-- NUMERIC(20,8) = 12 digits before decimal + 8 after = up to 999,999,999,999.99999999
ALTER TABLE split_payout_request
ALTER COLUMN from_amount TYPE NUMERIC(20,8);

COMMENT ON COLUMN split_payout_request.from_amount IS 'Source USDT amount - NUMERIC(20,8) for precision in crypto conversions';


-- ============================================================================
-- Table: split_payout_que (aka split_payout_hostpay alias)
-- ============================================================================

-- Fix from_amount: NUMERIC(12,8) → NUMERIC(20,8)
-- This field stores ETH amounts from ChangeNow (currently max 0.024)
-- NUMERIC(20,8) = 12 digits before decimal + 8 after = up to 999,999,999,999.99999999
ALTER TABLE split_payout_que
ALTER COLUMN from_amount TYPE NUMERIC(20,8);

COMMENT ON COLUMN split_payout_que.from_amount IS 'ChangeNow from_amount (ETH) - NUMERIC(20,8) for precision';

-- Fix to_amount: NUMERIC(24,12) → NUMERIC(30,8)
-- This field stores client token amounts (currently max 1,352,956 SHIB)
-- NUMERIC(30,8) = 22 digits before decimal + 8 after = supports billions of tokens
ALTER TABLE split_payout_que
ALTER COLUMN to_amount TYPE NUMERIC(30,8);

COMMENT ON COLUMN split_payout_que.to_amount IS 'Client token amount - NUMERIC(30,8) to support extreme quantities of micro-value tokens';


-- ============================================================================
-- Table: split_payout_hostpay
-- ============================================================================

-- Fix from_amount: NUMERIC(12,8) → NUMERIC(20,8)
-- This field stores ETH amounts
ALTER TABLE split_payout_hostpay
ALTER COLUMN from_amount TYPE NUMERIC(20,8);

COMMENT ON COLUMN split_payout_hostpay.from_amount IS 'ETH amount - NUMERIC(20,8) for precision';


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
    numeric_scale,
    CASE
        WHEN numeric_precision >= 30 THEN '✅ LARGE'
        WHEN numeric_precision >= 20 THEN '✅ GOOD'
        WHEN numeric_precision >= 12 THEN '⚠️ SMALL'
        ELSE '❌ TOO SMALL'
    END as status
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name IN ('split_payout_request', 'split_payout_que', 'split_payout_hostpay')
AND column_name LIKE '%amount%'
ORDER BY table_name, column_name;

-- Expected Results:
-- split_payout_hostpay.actual_eth_amount     NUMERIC(20,18) ✅
-- split_payout_hostpay.from_amount            NUMERIC(20,8)  ✅ FIXED
-- split_payout_que.from_amount                NUMERIC(20,8)  ✅ FIXED
-- split_payout_que.to_amount                  NUMERIC(30,8)  ✅ FIXED
-- split_payout_request.actual_eth_amount      NUMERIC(20,18) ✅
-- split_payout_request.from_amount            NUMERIC(20,8)  ✅ FIXED
-- split_payout_request.to_amount              NUMERIC(30,8)  ✅ FIXED
