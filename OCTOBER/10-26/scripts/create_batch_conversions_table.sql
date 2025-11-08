-- Create batch_conversions table
CREATE TABLE IF NOT EXISTS batch_conversions (
    id SERIAL PRIMARY KEY,
    batch_conversion_id UUID NOT NULL UNIQUE,
    total_eth_usd NUMERIC(20, 8) NOT NULL,
    threshold_at_creation NUMERIC(20, 2) NOT NULL,
    cn_api_id VARCHAR(255),
    payin_address VARCHAR(255),
    conversion_status VARCHAR(20) DEFAULT 'pending',
    actual_usdt_received NUMERIC(20, 8),
    conversion_tx_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_batch_conversions_status ON batch_conversions(conversion_status);
CREATE INDEX IF NOT EXISTS idx_batch_conversions_cn_api_id ON batch_conversions(cn_api_id);
CREATE INDEX IF NOT EXISTS idx_batch_conversions_created ON batch_conversions(created_at);

-- Add batch_conversion_id column to payout_accumulation
ALTER TABLE payout_accumulation
ADD COLUMN IF NOT EXISTS batch_conversion_id UUID REFERENCES batch_conversions(batch_conversion_id);

CREATE INDEX IF NOT EXISTS idx_payout_accumulation_batch_conversion ON payout_accumulation(batch_conversion_id);

-- Verify table structure
\d batch_conversions
\d payout_accumulation
