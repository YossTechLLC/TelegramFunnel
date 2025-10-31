-- Database Migration: Add conversion status tracking fields to payout_accumulation
-- Date: October 31, 2025
-- Purpose: Support asynchronous ETH→USDT conversion with status tracking

-- Add new fields for conversion status tracking
ALTER TABLE payout_accumulation
ADD COLUMN IF NOT EXISTS conversion_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS conversion_attempts INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_conversion_attempt TIMESTAMP;

-- Update existing records to mark them as completed (they have conversion data)
UPDATE payout_accumulation
SET conversion_status = 'completed'
WHERE accumulated_amount_usdt IS NOT NULL
  AND eth_to_usdt_rate IS NOT NULL
  AND conversion_status = 'pending';

-- Create index on conversion_status for faster queries
CREATE INDEX IF NOT EXISTS idx_payout_accumulation_conversion_status
ON payout_accumulation(conversion_status);

-- Add comments for documentation
COMMENT ON COLUMN payout_accumulation.conversion_status IS 'Status of ETH→USDT conversion: pending, completed, failed';
COMMENT ON COLUMN payout_accumulation.conversion_attempts IS 'Number of conversion attempts (for monitoring retry behavior)';
COMMENT ON COLUMN payout_accumulation.last_conversion_attempt IS 'Timestamp of last conversion attempt';

-- Verify migration
SELECT
    COUNT(*) FILTER (WHERE conversion_status = 'pending') AS pending_conversions,
    COUNT(*) FILTER (WHERE conversion_status = 'completed') AS completed_conversions,
    COUNT(*) FILTER (WHERE conversion_status = 'failed') AS failed_conversions,
    COUNT(*) AS total_records
FROM payout_accumulation;
