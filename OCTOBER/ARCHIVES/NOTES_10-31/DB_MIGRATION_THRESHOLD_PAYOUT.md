# Database Migration Guide - Threshold Payout System

**Version:** 1.0
**Date:** 2025-10-28
**Target Database:** PostgreSQL (Cloud SQL)

---

## Overview

This migration adds support for threshold-based payout accumulation to eliminate market volatility risk for high-fee cryptocurrencies like Monero (XMR).

**Key Innovation:** USDT accumulation locks in USD value immediately, preventing volatility losses.

---

## Migration Steps

### Step 1: Modify `main_clients_database` Table

Add columns for payout strategy configuration:

```sql
-- Add payout strategy columns
ALTER TABLE main_clients_database
ADD COLUMN payout_strategy VARCHAR(20) DEFAULT 'instant',
ADD COLUMN payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN payout_threshold_updated_at TIMESTAMP;

-- Add constraint: threshold must be non-negative
ALTER TABLE main_clients_database
ADD CONSTRAINT check_threshold_positive
CHECK (payout_threshold_usd >= 0);

-- Add index for strategy queries
CREATE INDEX idx_payout_strategy ON main_clients_database(payout_strategy);
```

**Field Descriptions:**
- `payout_strategy` - Either 'instant' or 'threshold'
- `payout_threshold_usd` - Minimum USD amount to accumulate before payout
- `payout_threshold_updated_at` - When threshold was last modified

---

### Step 2: Create `payout_accumulation` Table

Tracks individual payments accumulating toward threshold:

```sql
CREATE TABLE payout_accumulation (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Client & User Identification
    client_id VARCHAR(14) NOT NULL,  -- open_channel_id from main_clients_database
    user_id BIGINT NOT NULL,         -- Telegram user who made payment
    subscription_id INTEGER,          -- FK to private_channel_users_database

    -- Original Payment Information
    payment_amount_usd NUMERIC(10, 2) NOT NULL,  -- What user originally paid
    payment_currency VARCHAR(10) NOT NULL,        -- Original payment currency
    payment_timestamp TIMESTAMP NOT NULL,         -- When user paid

    -- Converted Stable Amount (CRITICAL - eliminates volatility)
    accumulated_amount_usdt NUMERIC(18, 8) NOT NULL,  -- Locked USDT value

    -- Conversion Tracking
    eth_to_usdt_rate NUMERIC(18, 8) NOT NULL,     -- Rate at conversion time
    conversion_timestamp TIMESTAMP NOT NULL,       -- When ETH→USDT executed
    conversion_tx_hash VARCHAR(100),               -- ChangeNow tx ID

    -- Client Payout Configuration
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,   -- Target currency (e.g., XMR)
    client_payout_network VARCHAR(50) NOT NULL,

    -- Payout Status
    is_paid_out BOOLEAN DEFAULT FALSE,
    payout_batch_id VARCHAR(50),      -- Links to payout_batches table
    paid_out_at TIMESTAMP,

    -- Audit Trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Performance
CREATE INDEX idx_client_pending ON payout_accumulation(client_id, is_paid_out);
CREATE INDEX idx_payout_batch ON payout_accumulation(payout_batch_id);
CREATE INDEX idx_user ON payout_accumulation(user_id);
CREATE INDEX idx_payment_timestamp ON payout_accumulation(payment_timestamp);
```

**Critical Field: `accumulated_amount_usdt`**
- This is the USD value locked in USDT stablecoins
- Example: User pays $50 → We immediately convert to 50 USDT
- Value NEVER changes regardless of market volatility
- This solves the volatility problem completely

---

### Step 3: Create `payout_batches` Table

Tracks batch payouts to clients:

```sql
CREATE TABLE payout_batches (
    -- Primary Key
    batch_id VARCHAR(50) PRIMARY KEY,  -- UUID for batch

    -- Client Identification
    client_id VARCHAR(14) NOT NULL,
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,

    -- Batch Totals
    total_amount_usdt NUMERIC(18, 8) NOT NULL,     -- Total USDT accumulated
    total_payments_count INTEGER NOT NULL,          -- Number of payments batched

    -- Conversion Details
    payout_amount_crypto NUMERIC(18, 8),           -- Amount in target currency (XMR)
    usdt_to_crypto_rate NUMERIC(18, 8),            -- Conversion rate USDT→XMR
    conversion_fee NUMERIC(18, 8),                 -- ChangeNow fee

    -- ChangeNow Transaction
    cn_api_id VARCHAR(100),                        -- ChangeNow swap ID
    cn_payin_address VARCHAR(200),                 -- Where we send USDT

    -- Blockchain Transaction
    tx_hash VARCHAR(100),                          -- XMR transaction hash
    tx_status VARCHAR(20),                         -- success/pending/failed

    -- Status Tracking
    status VARCHAR(20) DEFAULT 'pending',          -- pending, processing, completed, failed

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_client_batch ON payout_batches(client_id);
CREATE INDEX idx_status_batch ON payout_batches(status);
CREATE INDEX idx_created_batch ON payout_batches(created_at);
```

**Status Flow:**
1. `pending` - Batch created, awaiting processing
2. `processing` - GCSplit/GCHostPay calls in progress
3. `completed` - Funds delivered to client
4. `failed` - Error occurred, requires manual intervention

---

## Verification Queries

After migration, run these queries to verify:

```sql
-- 1. Check main_clients_database columns added
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'main_clients_database'
  AND column_name IN ('payout_strategy', 'payout_threshold_usd', 'payout_threshold_updated_at');

-- 2. Verify payout_accumulation table created
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'payout_accumulation';

-- 3. Verify payout_batches table created
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'payout_batches';

-- 4. Check indexes created
SELECT indexname
FROM pg_indexes
WHERE tablename IN ('main_clients_database', 'payout_accumulation', 'payout_batches');

-- 5. Verify all existing channels default to 'instant'
SELECT COUNT(*), payout_strategy
FROM main_clients_database
GROUP BY payout_strategy;
-- Expected: All channels have strategy='instant'
```

---

## Rollback Plan

If migration needs to be rolled back:

```sql
-- ROLLBACK: Remove new tables
DROP TABLE IF EXISTS payout_batches CASCADE;
DROP TABLE IF EXISTS payout_accumulation CASCADE;

-- ROLLBACK: Remove columns from main_clients_database
ALTER TABLE main_clients_database
DROP COLUMN IF EXISTS payout_strategy,
DROP COLUMN IF EXISTS payout_threshold_usd,
DROP COLUMN IF EXISTS payout_threshold_updated_at;

-- ROLLBACK: Remove indexes
DROP INDEX IF EXISTS idx_payout_strategy;
DROP INDEX IF EXISTS idx_client_pending;
DROP INDEX IF EXISTS idx_payout_batch;
DROP INDEX IF EXISTS idx_user;
DROP INDEX IF EXISTS idx_payment_timestamp;
DROP INDEX IF EXISTS idx_client_batch;
DROP INDEX IF EXISTS idx_status_batch;
DROP INDEX IF EXISTS idx_created_batch;
```

---

## Data Integrity Notes

1. **Existing Channels:** All existing channels will default to `payout_strategy='instant'`
2. **Backward Compatibility:** Instant payout flow unchanged
3. **No Data Loss:** Migration is purely additive
4. **NUMERIC Precision:** All financial fields use NUMERIC to avoid floating-point errors

---

## Execution Instructions

1. **Backup Database First:**
   ```bash
   gcloud sql backups create --instance=YOUR_INSTANCE_NAME
   ```

2. **Run Migration in Transaction:**
   ```sql
   BEGIN;
   -- [Run all migration SQL above]
   COMMIT;
   -- If any errors: ROLLBACK;
   ```

3. **Verify with Queries Above**

4. **Update Application Code** (see service modification guides)

---

## Related Documentation

- `THRESHOLD_PAYOUT_ARCHITECTURE.md` - Full architecture design
- `DEPLOYMENT_GUIDE_THRESHOLD_PAYOUT.md` - Service deployment guide
- `MAIN_ARCHITECTURE_WORKFLOW.md` - Implementation tracking

---

**Migration Author:** Claude (Anthropic)
**Review Status:** Pending User Review
**Execution Status:** Not Started
