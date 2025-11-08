# Fee Discrepancy Architectural Solution
## Two-Phase Blockchain Confirmation System

**Created:** 2025-11-02
**Status:** CRITICAL - Requires Implementation
**Priority:** P0 - System Integrity Issue

---

## Executive Summary

### The Problem
The current system stores payment amounts based on **estimated calculations** (payment_amount - TP_fee) rather than **actual received amounts** from the blockchain. This creates a discrepancy that causes payout failures.

**Example:**
- Customer pays: **$1.35**
- TP fee (15%): **$0.2025**
- **Stored amount: $1.1475** ← Current behavior
- **Actual ETH received: $1.05** ← Reality (verified via Payment ID 4971340333)
- **Discrepancy: $0.0975** (8.5% loss)

The missing $0.0975 is due to:
1. **NowPayments processing fee** (~5-7%)
2. **Ethereum network gas fees** (~2-4%)

### The Impact
When GCHostPay attempts to execute payouts, it will:
- Try to pay out $1.1475 (stored amount)
- But only has $1.05 (actual received)
- **Result: Transaction FAILS due to insufficient funds**

### The Solution
Implement a **Two-Phase Blockchain Confirmation System** that uses the blockchain as the source of truth, not estimates.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TWO-PHASE CONFIRMATION FLOW                       │
└─────────────────────────────────────────────────────────────────────┘

PHASE 1: PENDING CONFIRMATION (EXISTING FLOW - ENHANCED)
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ NowPayments  │─────▶│  GCWebhook1  │─────▶│  GCSplit1    │
│   Webhook    │      │   (Payment   │      │  (TP Fee     │
│              │      │  Confirmed)  │      │  Deduction)  │
└──────────────┘      └──────────────┘      └──────────────┘
                                                     │
                                                     ▼
                                            ┌──────────────┐
                                            │GCAccumulator │
                                            │              │
                                            │ Stores:      │
                                            │ • estimated  │
                                            │   amount     │
                                            │ • status:    │
                                            │   'pending'  │
                                            └──────────────┘

PHASE 2: BLOCKCHAIN CONFIRMATION (NEW FLOW)
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Alchemy     │─────▶│  GCHostPay3  │─────▶│GCAccumulator │
│  Webhook     │      │  (Enhanced)  │      │  (Enhanced)  │
│              │      │              │      │              │
│ ETH lands in │      │ Receives:    │      │ Updates:     │
│ host wallet  │      │ • tx_hash    │      │ • actual_amt │
│              │      │ • value      │      │ • status:    │
│              │      │ • from_addr  │      │   'confirmed'│
└──────────────┘      └──────────────┘      └──────────────┘
                                                     │
                                                     ▼
                                            ┌──────────────┐
                                            │ GCMicroBatch │
                                            │  Processor   │
                                            │              │
                                            │ ONLY process │
                                            │ 'confirmed'  │
                                            │ payments     │
                                            └──────────────┘
```

---

## Database Schema Changes

### Current Schema (payout_accumulation)
```sql
CREATE TABLE payout_accumulation (
    id SERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    subscription_id VARCHAR(255),
    payment_amount_usd DECIMAL(20, 8) NOT NULL,
    payment_currency VARCHAR(20) NOT NULL,
    payment_timestamp TIMESTAMP NOT NULL,
    accumulated_eth DECIMAL(30, 18) NOT NULL,      -- ❌ PROBLEM: Estimated value
    client_wallet_address VARCHAR(255) NOT NULL,
    client_payout_currency VARCHAR(20) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,
    conversion_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### New Schema (payout_accumulation) - PHASE 1
```sql
ALTER TABLE payout_accumulation
ADD COLUMN confirmation_status VARCHAR(50) DEFAULT 'pending_blockchain';
-- Values: 'pending_blockchain', 'confirmed', 'discrepancy_alert', 'confirmation_failed'

ALTER TABLE payout_accumulation
ADD COLUMN estimated_amount_usd DECIMAL(20, 8);
-- What we EXPECT after TP fee deduction

ALTER TABLE payout_accumulation
ADD COLUMN actual_amount_usd DECIMAL(20, 8);
-- What ACTUALLY landed (from blockchain)

ALTER TABLE payout_accumulation
ADD COLUMN fee_discrepancy_usd DECIMAL(20, 8);
-- Difference between estimated and actual (for monitoring)

ALTER TABLE payout_accumulation
ADD COLUMN nowpayments_payment_id VARCHAR(255);
-- For matching blockchain tx to NowPayments payment

ALTER TABLE payout_accumulation
ADD COLUMN blockchain_tx_hash VARCHAR(255);
-- ETH transaction hash when payment landed

ALTER TABLE payout_accumulation
ADD COLUMN blockchain_confirmation_timestamp TIMESTAMP;
-- When we confirmed the actual amount from blockchain

ALTER TABLE payout_accumulation
ADD COLUMN confirmation_attempts INTEGER DEFAULT 0;
-- How many times we attempted to match/confirm

ALTER TABLE payout_accumulation
ADD COLUMN last_confirmation_attempt TIMESTAMP;
-- Last time we tried to confirm this payment
```

### New Table: blockchain_payment_matching (PHASE 1)
```sql
CREATE TABLE blockchain_payment_matching (
    id SERIAL PRIMARY KEY,
    tx_hash VARCHAR(255) NOT NULL UNIQUE,
    from_address VARCHAR(255) NOT NULL,
    to_address VARCHAR(255) NOT NULL,            -- Our host wallet
    value_eth DECIMAL(30, 18) NOT NULL,           -- Actual ETH received
    value_usd DECIMAL(20, 8),                     -- USD equivalent at time
    block_number BIGINT NOT NULL,
    block_timestamp TIMESTAMP NOT NULL,
    matched_accumulation_id INTEGER,              -- FK to payout_accumulation
    match_confidence VARCHAR(50),                 -- 'high', 'medium', 'low', 'manual'
    match_criteria JSONB,                         -- How we matched it
    matched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (matched_accumulation_id) REFERENCES payout_accumulation(id)
);

CREATE INDEX idx_blockchain_tx_hash ON blockchain_payment_matching(tx_hash);
CREATE INDEX idx_blockchain_to_address ON blockchain_payment_matching(to_address);
CREATE INDEX idx_blockchain_unmatched ON blockchain_payment_matching(matched_accumulation_id)
    WHERE matched_accumulation_id IS NULL;
```

---

## Component Changes

### 1. GCAccumulator Enhancement (PHASE 1)

**Current Behavior:**
```python
# Stores estimated amount as final
accumulated_eth = adjusted_amount_usd  # After TP fee
accumulation_id = db_manager.insert_payout_accumulation_pending(
    accumulated_eth=accumulated_eth,
    # ...
)
```

**New Behavior:**
```python
# Store as PENDING CONFIRMATION with estimated amount
accumulation_id = db_manager.insert_payout_accumulation_pending_confirmation(
    estimated_amount_usd=adjusted_amount_usd,     # What we expect
    actual_amount_usd=None,                       # Not known yet
    confirmation_status='pending_blockchain',     # Waiting for blockchain
    nowpayments_payment_id=payment_id,           # For matching
    # ...
)
```

**New Endpoint: `/blockchain-confirmed` (PHASE 2)**
```python
@app.route("/blockchain-confirmed", methods=["POST"])
def blockchain_confirmed():
    """
    Receives blockchain confirmation from GCHostPay3 Alchemy handler.
    Updates payout_accumulation with ACTUAL received amount.

    Request payload (encrypted token):
    {
        "token": "<encrypted_token>",
        "tx_hash": "0x...",
        "value_eth": "0.0002712",
        "value_usd": "1.05",
        "from_address": "0x...",
        "block_number": 12345678,
        "block_timestamp": "2025-11-02T00:06:28Z"
    }
    """
    # 1. Decrypt and validate token
    # 2. Find matching pending accumulation record
    # 3. Update with actual_amount_usd from blockchain
    # 4. Calculate fee_discrepancy
    # 5. Update confirmation_status to 'confirmed'
    # 6. Alert if discrepancy > threshold
```

### 2. GCHostPay3 Enhancement (PHASE 2)

**Current Alchemy Webhook Handler:**
Currently, GCHostPay3 has Alchemy webhook infrastructure but doesn't process incoming customer payments - it only monitors outgoing payments.

**New Behavior - INCOMING PAYMENT DETECTION:**
```python
@app.route("/alchemy-webhook", methods=["POST"])
def alchemy_webhook():
    """
    Enhanced to detect INCOMING payments to host wallet.

    Flow:
    1. Receive Alchemy webhook for transaction
    2. Check if TO address = our host wallet (INCOMING)
    3. If INCOMING:
       a. Extract tx_hash, value_eth, from_address, block_number
       b. Convert value_eth to USD using live price
       c. Store in blockchain_payment_matching table
       d. Attempt to match to pending payout_accumulation record
       e. If matched: Update accumulation with actual_amount_usd
       f. If no match: Log for manual reconciliation
    """
    # Extract transaction details
    tx_hash = webhook_data['transaction']['hash']
    from_address = webhook_data['transaction']['from']
    to_address = webhook_data['transaction']['to']
    value_wei = int(webhook_data['transaction']['value'], 16)
    value_eth = value_wei / 1e18

    # Check if this is INCOMING to our host wallet
    if to_address.lower() != config['host_wallet_address'].lower():
        return jsonify({"status": "ignored", "reason": "not_our_wallet"})

    # This is an incoming payment!
    print(f"💰 [ALCHEMY] INCOMING payment detected")
    print(f"📊 [ALCHEMY] Amount: {value_eth} ETH")
    print(f"🔗 [ALCHEMY] TX Hash: {tx_hash}")

    # Convert ETH to USD
    value_usd = get_eth_to_usd_price() * value_eth

    # Store in matching table
    db_manager.insert_blockchain_payment_matching(
        tx_hash=tx_hash,
        from_address=from_address,
        to_address=to_address,
        value_eth=value_eth,
        value_usd=value_usd,
        block_number=block_number,
        block_timestamp=block_timestamp
    )

    # Attempt to match to pending accumulation
    matched_id = attempt_payment_matching(
        value_usd=value_usd,
        tx_hash=tx_hash,
        timestamp=block_timestamp
    )

    if matched_id:
        # Found match - notify GCAccumulator
        encrypt_and_send_to_accumulator(
            accumulation_id=matched_id,
            actual_amount_usd=value_usd,
            tx_hash=tx_hash,
            block_data={...}
        )
    else:
        # No match - log for manual review
        print(f"⚠️ [ALCHEMY] Unmatched incoming payment: {tx_hash}")
        alert_unmatched_payment(tx_hash, value_usd)
```

### 3. Payment Matching Logic (PHASE 2)

**Matching Algorithm:**
```python
def attempt_payment_matching(value_usd, tx_hash, timestamp):
    """
    Attempts to match a blockchain transaction to a pending accumulation record.

    Matching criteria (in order of priority):
    1. PRIMARY: NowPayments payment_id in transaction metadata (ideal, rare)
    2. SECONDARY: Amount + Time window + User context
    3. TERTIARY: Manual reconciliation queue

    Returns:
        accumulation_id if matched, None otherwise
    """

    # Query pending records from last 24 hours
    pending_records = db_manager.get_pending_blockchain_confirmations(
        time_window_hours=24
    )

    # Match criteria
    for record in pending_records:
        estimated_usd = record['estimated_amount_usd']
        payment_timestamp = record['payment_timestamp']

        # Calculate tolerance (±10% for amount, ±30 min for time)
        amount_lower = estimated_usd * 0.90
        amount_upper = estimated_usd * 1.10
        time_window_seconds = 1800  # 30 minutes

        amount_match = amount_lower <= value_usd <= amount_upper
        time_diff = abs((timestamp - payment_timestamp).total_seconds())
        time_match = time_diff <= time_window_seconds

        if amount_match and time_match:
            # HIGH CONFIDENCE MATCH
            confidence = 'high'
            match_criteria = {
                'amount_match': True,
                'time_match': True,
                'amount_diff_pct': abs(value_usd - estimated_usd) / estimated_usd * 100,
                'time_diff_seconds': time_diff
            }

            # Update accumulation record
            db_manager.confirm_payout_accumulation(
                accumulation_id=record['id'],
                actual_amount_usd=value_usd,
                tx_hash=tx_hash,
                match_confidence=confidence,
                match_criteria=match_criteria
            )

            return record['id']

    # No match found
    return None
```

### 4. GCMicroBatchProcessor Changes (PHASE 2)

**Current Behavior:**
```python
# Queries ALL pending records
total_pending = db_manager.get_total_pending_usd()
pending_records = db_manager.get_all_pending_records()
```

**New Behavior:**
```python
# ONLY queries CONFIRMED records
total_confirmed = db_manager.get_total_confirmed_usd()
confirmed_records = db_manager.get_all_confirmed_records()

# Use ACTUAL amounts, not estimated
for record in confirmed_records:
    actual_amount = record['actual_amount_usd']  # ✅ Real blockchain value
    # NOT: estimated_amount = record['estimated_amount_usd']  # ❌ Incorrect
```

---

## Implementation Phases

### Phase 1: Database & Schema (Week 1)
**Priority: P0 - CRITICAL**

1. **Database Migration Script**
   - Add new columns to `payout_accumulation`
   - Create `blockchain_payment_matching` table
   - Create necessary indexes
   - Backfill existing records with estimated → actual for historical data

2. **Testing**
   - Run migration on telepaypsql database
   - Verify schema changes
   - Test rollback procedure

**Deliverables:**
- ✅ Migration SQL script
- ✅ Rollback SQL script
- ✅ Schema validation tests

---

### Phase 2: GCAccumulator Enhancement (Week 1-2)
**Priority: P0 - CRITICAL**

1. **Update Insert Logic**
   - Store `estimated_amount_usd` instead of direct `accumulated_eth`
   - Set `confirmation_status = 'pending_blockchain'`
   - Store `nowpayments_payment_id` for matching

2. **New Endpoint: `/blockchain-confirmed`**
   - Receive confirmation from GCHostPay3
   - Update `actual_amount_usd`
   - Calculate `fee_discrepancy_usd`
   - Update `confirmation_status = 'confirmed'`
   - Alert if discrepancy > 10%

3. **Database Manager Updates**
   - `insert_payout_accumulation_pending_confirmation()`
   - `confirm_payout_accumulation()`
   - `get_pending_blockchain_confirmations()`
   - `get_total_confirmed_usd()`

**Deliverables:**
- ✅ Updated `acc10-26.py`
- ✅ Updated `database_manager.py`
- ✅ Unit tests for new logic
- ✅ Integration tests

---

### Phase 3: GCHostPay3 Alchemy Enhancement (Week 2)
**Priority: P0 - CRITICAL**

1. **Alchemy Webhook Enhancement**
   - Detect INCOMING transactions to host wallet
   - Extract tx_hash, value_eth, from_address, block_number
   - Convert ETH → USD using live price feed
   - Store in `blockchain_payment_matching` table

2. **Matching Logic Implementation**
   - Implement `attempt_payment_matching()` algorithm
   - Match by: amount tolerance (±10%) + time window (±30 min)
   - Handle multiple match candidates
   - Store match confidence level

3. **Notification to GCAccumulator**
   - Encrypt matched payment data
   - Send to GCAccumulator `/blockchain-confirmed` endpoint
   - Handle failures with retry logic

**Deliverables:**
- ✅ Updated `tphp3-10-26.py` with Alchemy incoming detection
- ✅ Updated `wallet_manager.py` with matching logic
- ✅ Updated `database_manager.py` with matching methods
- ✅ ETH → USD price feed integration
- ✅ Integration tests

---

### Phase 4: GCMicroBatchProcessor Updates (Week 2-3)
**Priority: P1 - HIGH**

1. **Query Logic Changes**
   - Change from `get_total_pending_usd()` → `get_total_confirmed_usd()`
   - Change from `get_all_pending_records()` → `get_all_confirmed_records()`
   - Use `actual_amount_usd` instead of `estimated_amount_usd`

2. **Threshold Calculation**
   - Base threshold on CONFIRMED amounts only
   - Alert if large number of unconfirmed pending payments

**Deliverables:**
- ✅ Updated `microbatch10-26.py`
- ✅ Updated database queries
- ✅ Integration tests

---

### Phase 5: Monitoring & Alerting (Week 3)
**Priority: P1 - HIGH**

1. **Discrepancy Monitoring**
   - Alert if `fee_discrepancy_usd > $0.15` (>10% of avg payment)
   - Alert if confirmation takes > 2 hours
   - Dashboard showing pending vs confirmed ratio

2. **Unmatched Payment Alerts**
   - Alert on incoming payments with no match
   - Manual reconciliation queue UI
   - Daily reconciliation report

3. **Health Checks**
   - Endpoint showing confirmation statistics
   - Pending confirmation age distribution
   - Average discrepancy percentage

**Deliverables:**
- ✅ Alerting service integration
- ✅ Monitoring dashboard
- ✅ Daily reconciliation reports

---

## Edge Cases & Handling

### Edge Case 1: Payment Never Confirmed
**Scenario:** Customer payment stuck, ETH never lands in wallet

**Handling:**
- After 24 hours, mark as `confirmation_failed`
- Alert operations team
- Refund customer via NowPayments
- Remove from accumulation queue

---

### Edge Case 2: Multiple Payments Same Amount/Time
**Scenario:** Two customers pay $1.35 within same minute

**Handling:**
- Matching returns multiple candidates
- Use additional criteria: user_id, client_id from context
- If still ambiguous, mark both as `manual_reconciliation`
- Operations team manually matches via admin panel

---

### Edge Case 3: Huge Discrepancy (>20%)
**Scenario:** Expected $1.15, received $0.80

**Handling:**
- Automatic alert to operations
- Mark as `discrepancy_alert` status
- Do not include in batch processing
- Investigate: NowPayments issue? Network congestion?
- Manual resolution required

---

### Edge Case 4: Blockchain Confirmation Delays
**Scenario:** Alchemy webhook delayed by 30+ minutes

**Handling:**
- Implement polling fallback: query blockchain every 15 min for pending records
- Check for missing confirmations
- Alert if confirmation > 2 hours old

---

## Testing Strategy

### Unit Tests
- ✅ Amount matching algorithm (various tolerances)
- ✅ Time window matching
- ✅ Discrepancy calculation
- ✅ Confidence scoring

### Integration Tests
- ✅ Full flow: NowPayments → GCAccumulator → Alchemy → Confirmation
- ✅ Matching with exact amounts
- ✅ Matching with ±10% variance
- ✅ No match scenario
- ✅ Multiple match scenario

### Load Tests
- ✅ 1000 concurrent payments
- ✅ Confirmation latency under load
- ✅ Database query performance

### Edge Case Tests
- ✅ All edge cases documented above
- ✅ Manual reconciliation workflow

---

## Monitoring Metrics

### Key Performance Indicators (KPIs)

1. **Confirmation Rate**
   - Target: >95% of payments confirmed within 30 minutes
   - Alert if: <90% confirmation rate

2. **Average Discrepancy**
   - Target: <8% average fee discrepancy
   - Alert if: >12% average discrepancy

3. **Match Confidence**
   - Target: >90% high-confidence matches
   - Alert if: >20% low-confidence or manual matches

4. **Unmatched Payments**
   - Target: <2% unmatched payments
   - Alert if: >5% unmatched

### Dashboard Metrics

```
┌─────────────────────────────────────────────────────────────┐
│  BLOCKCHAIN CONFIRMATION DASHBOARD                          │
├─────────────────────────────────────────────────────────────┤
│  Pending Confirmations:        12 payments ($14.25 USD)    │
│  Confirmed Today:              157 payments ($189.42 USD)  │
│  Average Confirmation Time:    12.4 minutes                 │
│  Average Fee Discrepancy:      7.8% ($0.09 per payment)    │
│                                                             │
│  High Confidence Matches:      94.2%                        │
│  Low Confidence Matches:       4.5%                         │
│  Manual Reconciliation:        1.3%                         │
│  Unmatched Payments:           0.0%                         │
│                                                             │
│  Oldest Pending:               43 minutes                   │
│  Alerts (24h):                 0 critical, 2 warnings       │
└─────────────────────────────────────────────────────────────┘
```

---

## Rollout Plan

### Week 1: Preparation & Testing
- Deploy database schema changes
- Deploy GCAccumulator with new logic (FEATURE FLAG OFF)
- Integration testing in staging environment

### Week 2: Phased Rollout
- Enable FEATURE FLAG for 10% of traffic
- Monitor confirmation rates, discrepancies
- Adjust matching tolerances if needed
- Scale to 50% traffic

### Week 3: Full Production
- Enable for 100% of traffic
- Monitor for 7 days
- Fix any edge cases discovered
- Document lessons learned

---

## Success Criteria

✅ **Critical Success Factors:**
1. Zero payout failures due to insufficient funds
2. >95% automatic matching rate
3. <30 minute average confirmation time
4. <8% average fee discrepancy
5. Complete audit trail for all payments

✅ **Nice to Have:**
1. <15 minute average confirmation time
2. >98% automatic matching rate
3. <5% average fee discrepancy

---

## Cost Analysis

### Additional Infrastructure Costs

1. **Database Storage**
   - New columns: ~50 bytes per record
   - New table: ~200 bytes per transaction
   - At 1000 tx/day: ~250KB/day = ~7.5MB/month
   - **Cost: Negligible (<$0.01/month)**

2. **Alchemy API Calls**
   - Current: Only outgoing tx monitoring
   - New: Incoming tx monitoring
   - Increase: ~2x webhook calls
   - **Cost: Still within free tier (100k/month)**

3. **Cloud Tasks**
   - New: GCHostPay3 → GCAccumulator confirmation tasks
   - At 1000 tx/day: ~30k tasks/month
   - **Cost: ~$0.12/month**

4. **Compute Time**
   - Matching algorithm: ~50ms per payment
   - At 1000 tx/day: ~50 seconds/day
   - **Cost: Negligible (included in existing service)**

**Total Additional Cost: <$0.20/month**

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Matching fails | Medium | High | Manual reconciliation queue |
| Alchemy downtime | Low | Medium | Polling fallback |
| Large fee variance | Medium | Medium | Dynamic tolerance adjustment |
| DB migration issues | Low | Critical | Extensive testing, rollback plan |
| Performance degradation | Low | Medium | Indexing, query optimization |

---

## Conclusion

This two-phase blockchain confirmation system solves the critical fee discrepancy issue by using the blockchain as the source of truth. Instead of storing estimated amounts and hoping they match reality, we now:

1. **Store estimated amounts initially** (for tracking)
2. **Wait for blockchain confirmation** (actual amounts)
3. **Update with real values** (from Alchemy webhooks)
4. **Only process confirmed payments** (in batch processor)

This ensures that we **never attempt to pay out more than we actually received**, which is the current critical bug.

### Next Steps
1. Review and approve this architectural plan
2. Begin Phase 1: Database migration
3. Proceed through phases 2-5 sequentially
4. Monitor and iterate based on production metrics

---

**Document Owner:** Claude
**Last Updated:** 2025-11-02
**Version:** 1.0
