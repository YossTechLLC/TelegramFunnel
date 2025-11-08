# NowPayments Payment ID Storage - Architectural Implementation Plan

**Created:** 2025-11-02
**Status:** ARCHITECTURAL DESIGN - Ready for Implementation
**Priority:** P0 - Critical for Fee Discrepancy Resolution
**Related Documents:**
- `NOWPAYMENTS_PAYMENT_ID_STORAGE_ANALYSIS.md` - Problem analysis and requirements
- `FEE_DISCREPANCY_ARCHITECTURAL_SOLUTION.md` - Fee discrepancy solution (depends on payment_id)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Architectural Principles](#architectural-principles)
4. [Proposed Architecture](#proposed-architecture)
5. [Database Schema Changes](#database-schema-changes)
6. [Token Format Extensions](#token-format-extensions)
7. [Service Modifications](#service-modifications)
8. [Cloud Tasks Queue Updates](#cloud-tasks-queue-updates)
9. [Implementation Phases](#implementation-phases)
10. [Testing Strategy](#testing-strategy)
11. [Deployment Plan](#deployment-plan)

---

## Executive Summary

### Problem Statement
NowPayments Payment ID (e.g., `'4971340333'`) is **NOT** being captured or stored anywhere in our system. This prevents:
- Querying NowPayments API for actual received amounts
- Reconciling payments with blockchain transactions
- Resolving fee discrepancies (critical issue)
- Customer support and dispute resolution

### Solution Overview
Implement **IPN (Instant Payment Notification) callback endpoint** in GCWebhook1 to capture payment_id and actual amounts from NowPayments in real-time, then propagate this data through the existing Cloud Tasks pipeline using enhanced encrypted tokens.

### Architectural Alignment
✅ **Maintains existing patterns:**
- **CRON JOBS**: No changes to Cloud Scheduler jobs
- **QUEUES & TASKS**: Uses existing Cloud Tasks infrastructure
- **ENCRYPT/DECRYPT TOKEN**: Extends existing token formats with payment_id fields
- **Config Management**: Uses Secret Manager for IPN verification key
- **Service Communication**: Follows existing async queue-based flow

### Impact
- ✅ **Backward Compatible**: Existing instant payout flow unchanged
- ✅ **Zero Downtime**: Can be deployed incrementally
- ✅ **Scalable**: IPN endpoint handles thousands of concurrent callbacks
- ✅ **Secure**: HMAC signature verification for IPN authenticity

---

## Current Architecture Analysis

### Existing Service Flow (Instant Payout)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CURRENT PAYMENT FLOW (Instant Payout - No Payment ID Captured)         │
└──────────────────────────────────────────────────────────────────────────┘

1. TelePay Bot (start_np_gateway.py)
   ↓ Creates NowPayments invoice
   ↓ Returns: invoice_url, invoice_id
   ↓ NO payment_id yet (customer hasn't paid)

2. Customer completes payment
   ↓ NowPayments creates payment_id: 4971340333
   ↓ ❌ WE DON'T RECEIVE THIS (no IPN configured)

3. NowPayments redirects to success_url
   ↓ GCWebhook1 receives encrypted token
   ↓ Token contains: user_id, channel_id, wallet, price
   ↓ ❌ Token does NOT contain payment_id (not available)

4. GCWebhook1 (tph1-10-26.py)
   ↓ Decodes token
   ↓ Writes to private_channel_users_database
   ↓ ❌ payment_id NOT stored
   ↓ Routes based on payout_strategy:

   IF instant:
      ↓ Enqueues to GCSplit1 (Cloud Tasks)
      ↓ Token: user_id, channel_id, wallet, price
      ↓ ❌ payment_id NOT in token

   IF threshold:
      ↓ Enqueues to GCAccumulator (Cloud Tasks)
      ↓ Token: user_id, client_id, wallet, price
      ↓ ❌ payment_id NOT in token

5. GCAccumulator (acc10-26.py)
   ↓ Stores in payout_accumulation
   ↓ ❌ payment_id NOT stored
   ↓ conversion_status = 'pending'

6. GCMicroBatchProcessor (microbatch10-26.py)
   ↓ Cloud Scheduler triggers every 5 minutes
   ↓ Checks if total_pending >= threshold
   ↓ Creates batch_conversion_id
   ↓ ❌ No payment_id reference for reconciliation
```

### Existing Token Architecture

**Current Token Format (GCWebhook1 → GCWebhook2/GCSplit1):**
```python
# Binary packed format (efficient, not JSON)
packed_data = bytearray()
packed_data.extend(user_id.to_bytes(6, 'big'))              # 6 bytes
packed_data.extend(closed_channel_id.to_bytes(6, 'big'))    # 6 bytes
packed_data.extend(struct.pack(">H", timestamp_minutes))    # 2 bytes
packed_data.extend(struct.pack(">H", subscription_time_days)) # 2 bytes

# Variable length fields (1 byte length prefix + data)
packed_data.append(len(price_bytes))
packed_data.extend(price_bytes)
packed_data.append(len(wallet_bytes))
packed_data.extend(wallet_bytes)
packed_data.append(len(currency_bytes))
packed_data.extend(currency_bytes)
packed_data.append(len(network_bytes))
packed_data.extend(network_bytes)

# HMAC signature (16 bytes truncated)
full_signature = hmac.new(signing_key.encode(), bytes(packed_data), hashlib.sha256).digest()
truncated_signature = full_signature[:16]
final_data = bytes(packed_data) + truncated_signature

# Base64 URL-safe encoding
token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')
```

**Key Characteristics:**
- ✅ Binary packed (not JSON) for efficiency
- ✅ HMAC-SHA256 signature verification
- ✅ Variable-length fields with length prefixes
- ✅ Base64 URL-safe encoding
- ✅ Signature prevents tampering

### Existing Cloud Tasks Pattern

**Example from GCWebhook1 → GCAccumulator:**
```python
# cloudtasks_client.py
def enqueue_gcaccumulator_payment(self, queue_name, target_url, user_id, ...):
    payload = {
        "user_id": user_id,
        "client_id": client_id,
        "payment_amount_usd": subscription_price,
        "wallet_address": wallet_address,
        "payout_currency": payout_currency,
        "payout_network": payout_network,
        "subscription_id": subscription_id,
        "payment_timestamp": datetime.datetime.now().isoformat()
    }

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": target_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode()
        }
    }

    response = self.client.create_task(request={"parent": parent, "task": task})
    return response.name
```

**Key Characteristics:**
- ✅ JSON payloads for Cloud Tasks (not encrypted tokens)
- ✅ Asynchronous, decoupled service communication
- ✅ Automatic retry on failure
- ✅ Rate limiting via queue configuration

---

## Architectural Principles

### 1. **Maintain Existing Patterns**
- ✅ Use Cloud Tasks for async service communication
- ✅ Use encrypted tokens for sensitive data transfer
- ✅ Use Secret Manager for all credentials
- ✅ Follow existing logging patterns (emoji prefixes)

### 2. **Backward Compatibility**
- ✅ Existing instant payout flow continues to work
- ✅ Services gracefully handle missing payment_id (optional field)
- ✅ Database schema changes are additive (no breaking changes)

### 3. **Security First**
- ✅ IPN endpoint verifies HMAC signature from NowPayments
- ✅ payment_id propagated via encrypted tokens
- ✅ Database stores payment_id with proper indexing

### 4. **Scalability**
- ✅ IPN endpoint handles concurrent callbacks
- ✅ Database updates are idempotent (duplicate IPN handling)
- ✅ Cloud Tasks provide retry logic

### 5. **Observability**
- ✅ Comprehensive logging at each step
- ✅ Emoji-prefixed debug statements match existing style
- ✅ Error tracking for failed IPN verifications

---

## Proposed Architecture

### New Payment Flow (With Payment ID Capture)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  NEW PAYMENT FLOW (With Payment ID Capture via IPN)                     │
└──────────────────────────────────────────────────────────────────────────┘

1. TelePay Bot (start_np_gateway.py) - MODIFIED
   ↓ Creates NowPayments invoice
   ↓ NEW: Adds ipn_callback_url to payload
   ↓ ipn_callback_url: "https://gcwebhook1.../ipn"
   ↓ Returns: invoice_url, invoice_id
   ↓ Stores invoice_id in context for later use

2. Customer completes payment
   ↓ NowPayments creates payment_id: 4971340333
   ↓ ✅ NowPayments sends IPN callback to our endpoint

   ┌────────────────────────────────────────────────────┐
   │ 2a. IPN Callback (ASYNC - Parallel to success_url)│
   └────────────────────────────────────────────────────┘
   ↓ POST /ipn (GCWebhook1)
   ↓ Payload: {payment_id, order_id, pay_address, outcome_amount, ...}
   ↓ Verify HMAC signature (x-nowpayments-sig header)
   ↓ ✅ Signature valid
   ↓ Extract: payment_id, order_id, pay_address, outcome_amount
   ↓ Update private_channel_users_database (by order_id):
   ↓    SET nowpayments_payment_id = '4971340333'
   ↓    SET nowpayments_pay_address = '0xABC...'
   ↓    SET nowpayments_outcome_amount = 0.0002712
   ↓    SET nowpayments_payment_status = 'finished'
   ↓ ✅ payment_id NOW STORED
   ↓ Return 200 OK to NowPayments

3. NowPayments redirects to success_url (MAIN FLOW)
   ↓ GCWebhook1 receives encrypted token
   ↓ Token contains: user_id, channel_id, wallet, price
   ↓ (payment_id not in success_url token - comes from IPN)

4. GCWebhook1 (tph1-10-26.py) - MODIFIED
   ↓ Decodes token
   ↓ Writes to private_channel_users_database
   ↓ ✅ payment_id already stored (from IPN step 2a)
   ↓ Lookup payment_id by user_id + channel_id
   ↓ Routes based on payout_strategy:

   IF instant:
      ↓ Enqueues to GCSplit1 (Cloud Tasks)
      ↓ NEW Token includes: payment_id, pay_address, outcome_amount

   IF threshold:
      ↓ Enqueues to GCAccumulator (Cloud Tasks)
      ↓ NEW Payload includes: payment_id, pay_address, outcome_amount

5. GCAccumulator (acc10-26.py) - MODIFIED
   ↓ Receives payload with payment_id
   ↓ Stores in payout_accumulation
   ↓ ✅ nowpayments_payment_id = '4971340333'
   ↓ ✅ nowpayments_pay_address = '0xABC...'
   ↓ ✅ nowpayments_outcome_amount = 0.0002712
   ↓ conversion_status = 'pending'

6. GCMicroBatchProcessor (microbatch10-26.py) - NO CHANGES
   ↓ Cloud Scheduler triggers every 5 minutes
   ↓ Checks if total_pending >= threshold
   ↓ ✅ Can now query NowPayments API with payment_id
   ↓ ✅ Can match blockchain tx with pay_address
```

### IPN Flow Diagram (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     NOWPAYMENTS IPN CALLBACK FLOW                       │
└─────────────────────────────────────────────────────────────────────────┘

NowPayments                         GCWebhook1 (/ipn endpoint)
     │                                      │
     │  POST /ipn                           │
     │  Headers:                            │
     │    x-nowpayments-sig: <HMAC>        │
     │  Body:                               │
     │  {                                   │
     │    "payment_id": 4971340333,        │
     │    "invoice_id": 9876543,           │
     │    "order_id": "PGP-123-456",       │
     │    "payment_status": "finished",    │
     │    "pay_address": "0xABC...",       │
     │    "pay_amount": 0.0002712,         │
     │    "outcome_amount": 0.0002712,     │
     │    "pay_currency": "eth",           │
     │    ...                               │
     │  }                                   │
     ├──────────────────────────────────────>
     │                                      │ 1. Verify HMAC signature
     │                                      │    (using IPN_SECRET_KEY)
     │                                      │
     │                                      │ 2. Parse IPN payload
     │                                      │
     │                                      │ 3. Extract key fields:
     │                                      │    - payment_id
     │                                      │    - order_id
     │                                      │    - pay_address
     │                                      │    - outcome_amount
     │                                      │    - payment_status
     │                                      │
     │                                      │ 4. Database Update:
     │                                      │    UPDATE private_channel_users_database
     │                                      │    SET nowpayments_payment_id = '4971340333',
     │                                      │        nowpayments_pay_address = '0xABC...',
     │                                      │        nowpayments_outcome_amount = 0.0002712,
     │                                      │        nowpayments_payment_status = 'finished'
     │                                      │    WHERE nowpayments_order_id = 'PGP-123-456'
     │                                      │
     │                                      │ 5. Idempotency Check:
     │                                      │    - Check if payment_id already stored
     │                                      │    - If yes, skip update, return 200
     │                                      │    - Handles duplicate IPN callbacks
     │                                      │
     │  200 OK {"status": "success"}        │ 6. Return success
     <──────────────────────────────────────┤
     │                                      │
     │                                      │ 7. If payment_status == 'finished':
     │                                      │    - Queue update to GCAccumulator
     │                                      │    - (if threshold payout active)
     │                                      │
```

### Race Condition Handling

**Scenario**: IPN callback arrives BEFORE success_url redirect

```
Timeline:
---------
T+0ms:  Customer completes payment
T+50ms: NowPayments sends IPN → GCWebhook1 /ipn
        ✅ Stores payment_id in database (by order_id)
T+100ms: NowPayments redirects customer → success_url
        ✅ GCWebhook1 main endpoint processes payment
        ✅ Finds payment_id already in database

Result: ✅ Works correctly (IPN already stored payment_id)
```

**Scenario**: success_url arrives BEFORE IPN callback

```
Timeline:
---------
T+0ms:  Customer completes payment
T+50ms: NowPayments redirects customer → success_url
        ⚠️ GCWebhook1 main endpoint processes payment
        ⚠️ payment_id NOT yet in database
        ✅ Continues with instant/threshold routing
T+100ms: NowPayments sends IPN → GCWebhook1 /ipn
        ✅ Stores payment_id in database (by order_id)
        ✅ Retroactively updates existing record

Result: ✅ Works correctly (eventual consistency)
```

**Solution**:
- Main flow doesn't block waiting for payment_id
- payment_id is **optional** in downstream services
- IPN updates are idempotent (can arrive before or after)

---

## Database Schema Changes

### 1. `private_channel_users_database` (Existing Table)

**Purpose**: Stores user subscription records
**Modified by**: GCWebhook1 (main endpoint + IPN endpoint)

```sql
-- Add NowPayments tracking columns
ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_payment_id VARCHAR(50);

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_invoice_id VARCHAR(50);

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_order_id VARCHAR(100);

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_pay_address VARCHAR(255);
-- Customer's payment address (where they sent crypto)

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_payment_status VARCHAR(50);
-- 'waiting', 'confirming', 'confirmed', 'sending', 'finished', etc.

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_pay_amount DECIMAL(30, 18);
-- Amount customer actually paid in crypto

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_pay_currency VARCHAR(20);
-- Currency customer paid with (e.g., 'eth', 'btc')

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_outcome_amount DECIMAL(30, 18);
-- Amount we actually received (after NowPayments fee)

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_created_at TIMESTAMP;
-- When payment was created in NowPayments

ALTER TABLE private_channel_users_database
ADD COLUMN nowpayments_updated_at TIMESTAMP;
-- Last update from NowPayments IPN

-- Create indexes for fast lookups
CREATE INDEX idx_nowpayments_payment_id
ON private_channel_users_database(nowpayments_payment_id);

CREATE INDEX idx_nowpayments_order_id
ON private_channel_users_database(nowpayments_order_id);

-- For IPN lookup: find record by order_id
CREATE INDEX idx_nowpayments_order_id_lookup
ON private_channel_users_database(nowpayments_order_id)
WHERE nowpayments_order_id IS NOT NULL;
```

### 2. `payout_accumulation` (Existing Table)

**Purpose**: Stores accumulated payments for threshold payout
**Modified by**: GCAccumulator

```sql
-- Add NowPayments tracking columns
ALTER TABLE payout_accumulation
ADD COLUMN nowpayments_payment_id VARCHAR(50);

ALTER TABLE payout_accumulation
ADD COLUMN nowpayments_pay_address VARCHAR(255);
-- For blockchain transaction matching

ALTER TABLE payout_accumulation
ADD COLUMN nowpayments_outcome_amount DECIMAL(30, 18);
-- Actual received amount (for fee discrepancy tracking)

ALTER TABLE payout_accumulation
ADD COLUMN nowpayments_network_fee DECIMAL(30, 18);
-- Network fee (extracted from NowPayments API)

ALTER TABLE payout_accumulation
ADD COLUMN payment_fee_usd DECIMAL(20, 8);
-- Total fees (NowPayments + network) for analytics

-- Create index for payment_id lookup
CREATE INDEX idx_payout_nowpayments_payment_id
ON payout_accumulation(nowpayments_payment_id);

-- For blockchain matching: find accumulation by pay_address
CREATE INDEX idx_payout_pay_address
ON payout_accumulation(nowpayments_pay_address)
WHERE nowpayments_pay_address IS NOT NULL;
```

### Migration Script

```python
#!/usr/bin/env python
"""
Database migration script for NowPayments payment_id storage.
Run this BEFORE deploying service updates.
"""
import os
import psycopg2
from google.cloud.sql.connector import Connector

def execute_migration():
    """Execute database schema migration."""

    # Initialize Cloud SQL Connector
    connector = Connector()

    def getconn():
        return connector.connect(
            "telepay-459221:us-central1:telepaypsql",
            "pg8000",
            user="postgres",
            password=os.environ.get("DB_PASSWORD"),
            db="telepaydb"
        )

    conn = getconn()
    cursor = conn.cursor()

    print("🚀 Starting NowPayments payment_id migration...")

    # Migration SQL
    migration_sql = """
    -- private_channel_users_database modifications
    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_payment_id VARCHAR(50);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_invoice_id VARCHAR(50);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_order_id VARCHAR(100);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_pay_address VARCHAR(255);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_payment_status VARCHAR(50);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_pay_amount DECIMAL(30, 18);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_pay_currency VARCHAR(20);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount DECIMAL(30, 18);

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_created_at TIMESTAMP;

    ALTER TABLE private_channel_users_database
    ADD COLUMN IF NOT EXISTS nowpayments_updated_at TIMESTAMP;

    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
    ON private_channel_users_database(nowpayments_payment_id);

    CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id
    ON private_channel_users_database(nowpayments_order_id);

    -- payout_accumulation modifications
    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_payment_id VARCHAR(50);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_pay_address VARCHAR(255);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_outcome_amount DECIMAL(30, 18);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS nowpayments_network_fee DECIMAL(30, 18);

    ALTER TABLE payout_accumulation
    ADD COLUMN IF NOT EXISTS payment_fee_usd DECIMAL(20, 8);

    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_payout_nowpayments_payment_id
    ON payout_accumulation(nowpayments_payment_id);

    CREATE INDEX IF NOT EXISTS idx_payout_pay_address
    ON payout_accumulation(nowpayments_pay_address);
    """

    try:
        cursor.execute(migration_sql)
        conn.commit()
        print("✅ Migration completed successfully")

        # Verify columns exist
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'private_channel_users_database'
            AND column_name LIKE 'nowpayments_%'
        """)

        columns = cursor.fetchall()
        print(f"✅ Verified {len(columns)} NowPayments columns in private_channel_users_database")

        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'payout_accumulation'
            AND column_name LIKE 'nowpayments_%'
        """)

        columns = cursor.fetchall()
        print(f"✅ Verified {len(columns)} NowPayments columns in payout_accumulation")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()
        connector.close()

if __name__ == "__main__":
    execute_migration()
```

---

## Token Format Extensions

### Option A: Add to Existing Token (RECOMMENDED)

**Extend existing token format to include payment_id fields as optional:**

```python
# token_manager.py (GCWebhook1)

def encrypt_token_for_gcwebhook2(
    self,
    user_id: int,
    closed_channel_id: int,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    subscription_time_days: int,
    subscription_price: str,
    nowpayments_payment_id: str = None,  # NEW (optional)
    nowpayments_pay_address: str = None,  # NEW (optional)
    nowpayments_outcome_amount: str = None  # NEW (optional)
) -> Optional[str]:
    """
    Encrypt token with optional NowPayments fields.

    Token format (EXTENDED):
    - 6 bytes user_id
    - 6 bytes closed_channel_id
    - 2 bytes timestamp_minutes
    - 2 bytes subscription_time_days
    - 1 byte price_length + subscription_price
    - 1 byte wallet_length + wallet_address
    - 1 byte currency_length + payout_currency
    - 1 byte network_length + payout_network
    - 1 byte payment_id_length + nowpayments_payment_id (NEW - optional)
    - 1 byte pay_address_length + nowpayments_pay_address (NEW - optional)
    - 1 byte outcome_amount_length + nowpayments_outcome_amount (NEW - optional)
    - 16 bytes HMAC signature
    """
    try:
        # ... existing packing code ...

        # Add existing fields
        packed_data = bytearray()
        packed_data.extend(user_id.to_bytes(6, 'big'))
        # ... all existing fields ...

        # NEW: Add optional NowPayments fields
        if nowpayments_payment_id:
            payment_id_bytes = nowpayments_payment_id.encode('utf-8')
            packed_data.append(len(payment_id_bytes))
            packed_data.extend(payment_id_bytes)
        else:
            packed_data.append(0)  # 0-length indicates absent

        if nowpayments_pay_address:
            pay_address_bytes = nowpayments_pay_address.encode('utf-8')
            packed_data.append(len(pay_address_bytes))
            packed_data.extend(pay_address_bytes)
        else:
            packed_data.append(0)

        if nowpayments_outcome_amount:
            outcome_amount_bytes = nowpayments_outcome_amount.encode('utf-8')
            packed_data.append(len(outcome_amount_bytes))
            packed_data.extend(outcome_amount_bytes)
        else:
            packed_data.append(0)

        # Calculate HMAC signature
        full_signature = hmac.new(
            self.signing_key.encode(),
            bytes(packed_data),
            hashlib.sha256
        ).digest()
        truncated_signature = full_signature[:16]

        # Combine data + signature
        final_data = bytes(packed_data) + truncated_signature
        token = base64.urlsafe_b64encode(final_data).rstrip(b'=').decode('utf-8')

        print(f"🔐 [TOKEN] Encrypted token for GCWebhook2 (with payment_id: {bool(nowpayments_payment_id)})")
        return token

    except Exception as e:
        print(f"❌ [TOKEN] Error encrypting token: {e}")
        return None
```

**Decoding (Backward Compatible):**

```python
def decode_and_verify_token(self, token: str) -> Tuple:
    """
    Decode token with optional NowPayments fields.

    Returns:
        Tuple of (user_id, closed_channel_id, wallet_address, payout_currency,
                 payout_network, subscription_time_days, subscription_price,
                 nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount)

    If NowPayments fields absent, returns None for those fields.
    """
    # ... existing decoding code ...

    # Parse existing fields
    user_id = ...
    # ... all existing fields ...

    # NEW: Parse optional NowPayments fields
    # Check if there's more data after existing fields
    if offset + 1 <= len(raw):
        # Read payment_id
        payment_id_len = struct.unpack(">B", raw[offset:offset+1])[0]
        offset += 1

        if payment_id_len > 0:
            nowpayments_payment_id = raw[offset:offset+payment_id_len].decode('utf-8')
            offset += payment_id_len
        else:
            nowpayments_payment_id = None
    else:
        # Token from old version (no NowPayments fields)
        nowpayments_payment_id = None
        nowpayments_pay_address = None
        nowpayments_outcome_amount = None

        # Return with None values (backward compatible)
        return (user_id, closed_channel_id, wallet_address, payout_currency,
                payout_network, subscription_time_days, subscription_price,
                None, None, None)

    # Continue parsing if present...
    # ... similar for pay_address and outcome_amount ...

    return (user_id, closed_channel_id, wallet_address, payout_currency,
            payout_network, subscription_time_days, subscription_price,
            nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount)
```

### Option B: Use JSON Payload (Alternative for Cloud Tasks)

**For GCWebhook1 → GCAccumulator (Cloud Tasks), use JSON payload:**

```python
# cloudtasks_client.py (GCWebhook1)

def enqueue_gcaccumulator_payment(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    client_id: int,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    subscription_price: str,
    subscription_id: int,
    nowpayments_payment_id: str = None,  # NEW (optional)
    nowpayments_pay_address: str = None,  # NEW (optional)
    nowpayments_outcome_amount: str = None  # NEW (optional)
) -> Optional[str]:
    """Enqueue payment accumulation with NowPayments data."""

    payload = {
        "user_id": user_id,
        "client_id": client_id,
        "wallet_address": wallet_address,
        "payout_currency": payout_currency,
        "payout_network": payout_network,
        "payment_amount_usd": subscription_price,
        "subscription_id": subscription_id,
        "payment_timestamp": datetime.datetime.now().isoformat(),

        # NEW: NowPayments fields (optional)
        "nowpayments_payment_id": nowpayments_payment_id,
        "nowpayments_pay_address": nowpayments_pay_address,
        "nowpayments_outcome_amount": nowpayments_outcome_amount
    }

    return self.create_task(
        queue_name=queue_name,
        target_url=target_url,
        payload=payload
    )
```

**Recommendation**: Use **Option B (JSON payload)** for Cloud Tasks enqueuing. It's simpler, more readable, and follows existing patterns. The encrypted token approach (Option A) is better for URL-based transmission (success_url).

---

## Service Modifications

### 1. TelePay Bot (`start_np_gateway.py`)

**Changes Required:**
- Add `ipn_callback_url` to invoice creation payload
- Store `invoice_id` and `order_id` in bot context

```python
# start_np_gateway.py

async def create_payment_invoice(self, user_id: int, amount: float, success_url: str, order_id: str):
    """
    Create a payment invoice with NowPayments.

    NEW: Adds ipn_callback_url for payment_id callback.
    """
    if not self.payment_token:
        return {"error": "Payment provider token not available"}

    # NEW: Get IPN callback URL from config
    ipn_callback_url = os.getenv('NOWPAYMENTS_IPN_CALLBACK_URL')
    if not ipn_callback_url:
        print(f"⚠️ [INVOICE] IPN callback URL not configured - payment_id won't be captured")

    invoice_payload = {
        "price_amount": amount,
        "price_currency": "USD",
        "order_id": order_id,
        "order_description": "Payment-Test-1",
        "success_url": success_url,
        "ipn_callback_url": ipn_callback_url,  # NEW
        "is_fixed_rate": False,
        "is_fee_paid_by_user": False
    }

    headers = {
        "x-api-key": self.payment_token,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.api_url,
                headers=headers,
                json=invoice_payload,
            )

            if resp.status_code == 200:
                response_data = resp.json()

                # NEW: Log invoice_id for debugging
                invoice_id = response_data.get('id')
                print(f"📋 [INVOICE] Created invoice_id: {invoice_id}")
                print(f"📋 [INVOICE] Order ID: {order_id}")
                print(f"📋 [INVOICE] IPN will be sent to: {ipn_callback_url}")

                return {
                    "success": True,
                    "status_code": resp.status_code,
                    "data": response_data
                }
            else:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": resp.text
                }
    except Exception as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}"
        }
```

**Environment Variable:**
```bash
# Add to Secret Manager
NOWPAYMENTS_IPN_CALLBACK_URL="https://gcwebhook1-10-26-291176869049.us-central1.run.app/ipn"
```

### 2. GCWebhook1 (`tph1-10-26.py`)

**Changes Required:**
- Add `/ipn` endpoint for IPN callbacks
- Add IPN signature verification
- Update database with payment_id from IPN
- Enhance main endpoint to lookup and propagate payment_id

#### 2a. Add IPN Endpoint

```python
# tph1-10-26.py (GCWebhook1)

import hmac
import hashlib

# NEW: IPN signature verification
def verify_ipn_signature(payload: bytes, signature: str, ipn_secret: str) -> bool:
    """
    Verify IPN signature from NowPayments.

    NowPayments signature format:
    - Header: x-nowpayments-sig
    - Algorithm: HMAC-SHA512
    - Comparison: hexdigest

    Args:
        payload: Raw request body (bytes)
        signature: Signature from x-nowpayments-sig header
        ipn_secret: IPN secret key from Secret Manager

    Returns:
        True if signature is valid, False otherwise
    """
    if not ipn_secret or not signature:
        return False

    try:
        # NowPayments uses HMAC-SHA512 (not SHA256)
        expected_signature = hmac.new(
            ipn_secret.encode(),
            payload,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        print(f"❌ [IPN_VERIFY] Signature verification error: {e}")
        return False


# NEW: IPN endpoint
@app.route("/ipn", methods=["POST"])
def nowpayments_ipn():
    """
    IPN (Instant Payment Notification) endpoint for NowPayments.

    Receives payment_id and actual amounts when payment status changes.

    Flow:
    1. Verify HMAC signature from x-nowpayments-sig header
    2. Parse IPN payload
    3. Extract payment_id, order_id, pay_address, outcome_amount
    4. Update private_channel_users_database (by order_id)
    5. Idempotency: skip if payment_id already stored
    6. Return 200 OK to NowPayments

    Returns:
        JSON response with status
    """
    try:
        print(f"📨 [IPN] Received IPN notification from NowPayments")
        print(f"⏰ [IPN] Timestamp: {int(time.time())}")

        # Get raw payload for signature verification
        payload = request.get_data()
        signature = request.headers.get('x-nowpayments-sig', '')

        print(f"📦 [IPN] Payload size: {len(payload)} bytes")
        print(f"🔐 [IPN] Signature: {signature[:20]}...")

        # Verify signature
        ipn_secret = config.get('nowpayments_ipn_secret')
        if not ipn_secret:
            print(f"❌ [IPN] IPN secret not configured")
            abort(500, "IPN secret not configured")

        if not verify_ipn_signature(payload, signature, ipn_secret):
            print(f"❌ [IPN] Invalid signature - rejecting IPN")
            abort(401, "Invalid IPN signature")

        print(f"✅ [IPN] Signature verified successfully")

        # Parse IPN payload
        try:
            ipn_data = request.get_json()
            if not ipn_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ [IPN] JSON parsing error: {e}")
            abort(400, "Malformed JSON payload")

        # Extract fields
        payment_id = ipn_data.get('payment_id')
        invoice_id = ipn_data.get('invoice_id')
        order_id = ipn_data.get('order_id')
        payment_status = ipn_data.get('payment_status')
        pay_address = ipn_data.get('pay_address')
        pay_amount = ipn_data.get('pay_amount')
        actually_paid = ipn_data.get('actually_paid')
        outcome_amount = ipn_data.get('outcome_amount')
        pay_currency = ipn_data.get('pay_currency')
        created_at = ipn_data.get('created_at')
        updated_at = ipn_data.get('updated_at')

        print(f"💳 [IPN] Payment ID: {payment_id}")
        print(f"📋 [IPN] Invoice ID: {invoice_id}")
        print(f"📋 [IPN] Order ID: {order_id}")
        print(f"📊 [IPN] Status: {payment_status}")
        print(f"💰 [IPN] Pay Amount: {pay_amount} {pay_currency}")
        print(f"💰 [IPN] Actually Paid: {actually_paid} {pay_currency}")
        print(f"💰 [IPN] Outcome Amount: {outcome_amount} {pay_currency}")
        print(f"📬 [IPN] Pay Address: {pay_address}")

        # Validate required fields
        if not all([payment_id, order_id, payment_status]):
            print(f"❌ [IPN] Missing required fields")
            abort(400, "Missing required IPN fields")

        # Update database
        if not db_manager:
            print(f"❌ [IPN] Database manager not available")
            abort(500, "Database unavailable")

        # Idempotency check: check if payment_id already stored
        existing_record = db_manager.get_record_by_order_id(order_id)

        if existing_record and existing_record.get('nowpayments_payment_id') == payment_id:
            print(f"✅ [IPN] Payment ID already stored (idempotency) - returning success")
            return jsonify({"status": "success", "message": "Already processed"}), 200

        # Update record with NowPayments data
        print(f"💾 [IPN] Updating private_channel_users_database with payment_id")

        success = db_manager.update_nowpayments_data_by_order_id(
            order_id=order_id,
            payment_id=payment_id,
            invoice_id=invoice_id,
            payment_status=payment_status,
            pay_address=pay_address,
            pay_amount=pay_amount,
            outcome_amount=outcome_amount,
            pay_currency=pay_currency,
            created_at=created_at,
            updated_at=updated_at
        )

        if not success:
            print(f"❌ [IPN] Failed to update database")
            abort(500, "Database update failed")

        print(f"✅ [IPN] Database updated successfully")
        print(f"🎉 [IPN] IPN processed successfully")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ [IPN] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"IPN processing error: {str(e)}"
        }), 500
```

#### 2b. Enhance Main Endpoint

```python
# tph1-10-26.py (GCWebhook1)

@app.route("/", methods=["GET"])
def process_payment():
    """
    Main endpoint for processing payment confirmations from NOWPayments success_url.

    MODIFIED: Now looks up payment_id from database and propagates to downstream services.
    """
    try:
        # ... existing code ...

        # Decode token
        user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price = token_manager.decode_and_verify_token(token)

        # ... existing database write ...

        # NEW: Lookup payment_id from database (may have been set by IPN)
        print(f"🔍 [ENDPOINT] Looking up payment_id from database")
        subscription_record = db_manager.get_subscription_record(user_id, closed_channel_id)

        nowpayments_payment_id = None
        nowpayments_pay_address = None
        nowpayments_outcome_amount = None

        if subscription_record:
            nowpayments_payment_id = subscription_record.get('nowpayments_payment_id')
            nowpayments_pay_address = subscription_record.get('nowpayments_pay_address')
            nowpayments_outcome_amount = subscription_record.get('nowpayments_outcome_amount')

            if nowpayments_payment_id:
                print(f"✅ [ENDPOINT] Found payment_id: {nowpayments_payment_id}")
            else:
                print(f"⚠️ [ENDPOINT] payment_id not yet available (IPN may arrive later)")

        # ... existing payout strategy routing ...

        if payout_strategy == 'threshold':
            # NEW: Include payment_id in accumulator enqueue
            task_name_accumulator = cloudtasks_client.enqueue_gcaccumulator_payment(
                queue_name=gcaccumulator_queue,
                target_url=gcaccumulator_url,
                user_id=user_id,
                client_id=closed_channel_id,
                wallet_address=wallet_address,
                payout_currency=payout_currency,
                payout_network=payout_network,
                subscription_price=subscription_price,
                subscription_id=subscription_id,
                nowpayments_payment_id=nowpayments_payment_id,  # NEW
                nowpayments_pay_address=nowpayments_pay_address,  # NEW
                nowpayments_outcome_amount=nowpayments_outcome_amount  # NEW
            )

        # ... rest of existing code ...
```

#### 2c. Database Manager Updates

```python
# database_manager.py (GCWebhook1)

def update_nowpayments_data_by_order_id(
    self,
    order_id: str,
    payment_id: str,
    invoice_id: str,
    payment_status: str,
    pay_address: str,
    pay_amount: float,
    outcome_amount: float,
    pay_currency: str,
    created_at: str,
    updated_at: str
) -> bool:
    """
    Update subscription record with NowPayments data from IPN.

    Args:
        order_id: NowPayments order_id (e.g., "PGP-123-456")
        payment_id: NowPayments payment_id (e.g., "4971340333")
        ... other IPN fields

    Returns:
        True if update successful, False otherwise
    """
    try:
        conn = self.get_connection()
        cur = conn.cursor()

        # Update by order_id
        cur.execute("""
            UPDATE private_channel_users_database
            SET
                nowpayments_payment_id = %s,
                nowpayments_invoice_id = %s,
                nowpayments_order_id = %s,
                nowpayments_payment_status = %s,
                nowpayments_pay_address = %s,
                nowpayments_pay_amount = %s,
                nowpayments_outcome_amount = %s,
                nowpayments_pay_currency = %s,
                nowpayments_created_at = %s,
                nowpayments_updated_at = %s
            WHERE nowpayments_order_id = %s
        """, (
            payment_id, invoice_id, order_id, payment_status,
            pay_address, pay_amount, outcome_amount, pay_currency,
            created_at, updated_at, order_id
        ))

        rows_updated = cur.rowcount
        conn.commit()

        if rows_updated > 0:
            print(f"✅ [DATABASE] Updated {rows_updated} record(s) with payment_id {payment_id}")
            return True
        else:
            print(f"⚠️ [DATABASE] No records found for order_id {order_id}")
            return False

    except Exception as e:
        print(f"❌ [DATABASE] Error updating NowPayments data: {e}")
        return False

def get_record_by_order_id(self, order_id: str) -> dict:
    """Get subscription record by order_id (for idempotency check)."""
    try:
        conn = self.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, user_id, private_channel_id, nowpayments_payment_id,
                   nowpayments_pay_address, nowpayments_outcome_amount
            FROM private_channel_users_database
            WHERE nowpayments_order_id = %s
        """, (order_id,))

        row = cur.fetchone()
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'private_channel_id': row[2],
                'nowpayments_payment_id': row[3],
                'nowpayments_pay_address': row[4],
                'nowpayments_outcome_amount': row[5]
            }
        return None

    except Exception as e:
        print(f"❌ [DATABASE] Error fetching record: {e}")
        return None

def get_subscription_record(self, user_id: int, channel_id: int) -> dict:
    """Get subscription record for payment_id lookup."""
    try:
        conn = self.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT nowpayments_payment_id, nowpayments_pay_address,
                   nowpayments_outcome_amount
            FROM private_channel_users_database
            WHERE user_id = %s AND private_channel_id = %s
            ORDER BY subscription_time DESC
            LIMIT 1
        """, (user_id, channel_id))

        row = cur.fetchone()
        if row:
            return {
                'nowpayments_payment_id': row[0],
                'nowpayments_pay_address': row[1],
                'nowpayments_outcome_amount': row[2]
            }
        return None

    except Exception as e:
        print(f"❌ [DATABASE] Error fetching subscription: {e}")
        return None
```

### 3. GCAccumulator (`acc10-26.py`)

**Changes Required:**
- Accept payment_id fields in Cloud Tasks payload
- Store payment_id in payout_accumulation table

```python
# acc10-26.py (GCAccumulator)

@app.route("/", methods=["POST"])
def accumulate_payment():
    """
    Main endpoint for accumulating payments.

    MODIFIED: Now accepts and stores nowpayments_payment_id from Cloud Tasks payload.
    """
    try:
        # ... existing code ...

        # Extract payment data
        user_id = request_data.get('user_id')
        client_id = request_data.get('client_id')
        # ... existing fields ...

        # NEW: Extract NowPayments fields (optional)
        nowpayments_payment_id = request_data.get('nowpayments_payment_id')
        nowpayments_pay_address = request_data.get('nowpayments_pay_address')
        nowpayments_outcome_amount = request_data.get('nowpayments_outcome_amount')

        if nowpayments_payment_id:
            print(f"💳 [ENDPOINT] NowPayments Payment ID: {nowpayments_payment_id}")
            print(f"📬 [ENDPOINT] Pay Address: {nowpayments_pay_address}")
            print(f"💰 [ENDPOINT] Outcome Amount: {nowpayments_outcome_amount}")
        else:
            print(f"⚠️ [ENDPOINT] payment_id not available (may arrive via IPN later)")

        # ... existing fee calculation ...

        # Write to payout_accumulation table
        accumulation_id = db_manager.insert_payout_accumulation_pending(
            client_id=client_id,
            user_id=user_id,
            subscription_id=subscription_id,
            payment_amount_usd=payment_amount_usd,
            payment_currency='usd',
            payment_timestamp=payment_timestamp,
            accumulated_eth=accumulated_eth,
            client_wallet_address=wallet_address,
            client_payout_currency=payout_currency,
            client_payout_network=payout_network,
            nowpayments_payment_id=nowpayments_payment_id,  # NEW
            nowpayments_pay_address=nowpayments_pay_address,  # NEW
            nowpayments_outcome_amount=nowpayments_outcome_amount  # NEW
        )

        # ... rest of existing code ...
```

**Database Manager Update:**

```python
# database_manager.py (GCAccumulator)

def insert_payout_accumulation_pending(
    self,
    client_id: str,
    user_id: int,
    subscription_id: int,
    payment_amount_usd: Decimal,
    payment_currency: str,
    payment_timestamp: str,
    accumulated_eth: Decimal,
    client_wallet_address: str,
    client_payout_currency: str,
    client_payout_network: str,
    nowpayments_payment_id: str = None,  # NEW
    nowpayments_pay_address: str = None,  # NEW
    nowpayments_outcome_amount: str = None  # NEW
) -> Optional[int]:
    """
    Insert payment into payout_accumulation with 'pending' status.

    MODIFIED: Now accepts and stores NowPayments fields.
    """
    try:
        conn = self.get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO payout_accumulation (
                client_id, user_id, subscription_id, payment_amount_usd,
                payment_currency, payment_timestamp, accumulated_eth,
                client_wallet_address, client_payout_currency, client_payout_network,
                conversion_status,
                nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s
            )
            RETURNING id
        """, (
            client_id, user_id, subscription_id, payment_amount_usd,
            payment_currency, payment_timestamp, accumulated_eth,
            client_wallet_address, client_payout_currency, client_payout_network,
            nowpayments_payment_id, nowpayments_pay_address, nowpayments_outcome_amount
        ))

        accumulation_id = cur.fetchone()[0]
        conn.commit()

        print(f"✅ [DATABASE] Inserted accumulation record ID: {accumulation_id}")
        if nowpayments_payment_id:
            print(f"💳 [DATABASE] Linked to payment_id: {nowpayments_payment_id}")

        return accumulation_id

    except Exception as e:
        print(f"❌ [DATABASE] Error inserting accumulation: {e}")
        return None
```

---

## Cloud Tasks Queue Updates

### No New Queues Required

The existing Cloud Tasks queues will be used:
- ✅ `GCWEBHOOK2_QUEUE` - Telegram invite (no changes)
- ✅ `GCSPLIT1_QUEUE` - Instant payout split (enhanced payload)
- ✅ `GCACCUMULATOR_QUEUE` - Threshold accumulation (enhanced payload)

### Enhanced Payloads

**GCWebhook1 → GCAccumulator:**
```json
{
  "user_id": 123456,
  "client_id": "-1001234567890",
  "wallet_address": "0xABC...",
  "payout_currency": "shib",
  "payout_network": "eth",
  "payment_amount_usd": "1.35",
  "subscription_id": 42,
  "payment_timestamp": "2025-11-02T00:05:12Z",

  "nowpayments_payment_id": "4971340333",
  "nowpayments_pay_address": "0x1234...",
  "nowpayments_outcome_amount": "0.0002712"
}
```

---

## Implementation Phases

### Phase 1: Database Migration (Week 1, Days 1-2)
**Goal**: Add database columns for payment_id storage

**Tasks:**
1. ✅ Create migration script (`execute_payment_id_migration.py`)
2. ✅ Test migration in staging environment
3. ✅ Execute migration in production
4. ✅ Verify columns exist and indexes created

**Deliverables:**
- Database schema updated with NowPayments columns
- Indexes created for fast lookups
- Migration verified in production

**Testing:**
```sql
-- Verify columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'private_channel_users_database'
AND column_name LIKE 'nowpayments_%';

-- Verify indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'private_channel_users_database'
AND indexname LIKE 'idx_nowpayments_%';
```

---

### Phase 2: IPN Endpoint Implementation (Week 1, Days 3-5)
**Goal**: Implement IPN endpoint to capture payment_id in real-time

**Tasks:**
1. ✅ Add IPN secret to Secret Manager
2. ✅ Implement `/ipn` endpoint in GCWebhook1
3. ✅ Implement signature verification
4. ✅ Update `database_manager.py` with IPN methods
5. ✅ Deploy GCWebhook1 with IPN endpoint
6. ✅ Configure NowPayments IPN callback URL in TelePay

**Deliverables:**
- IPN endpoint deployed and accessible
- Signature verification working
- Database updates working
- Idempotency handling implemented

**Testing:**
```bash
# Test IPN endpoint with mock payload
curl -X POST https://gcwebhook1.../ipn \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: <test_signature>" \
  -d '{
    "payment_id": "TEST123",
    "order_id": "PGP-TEST",
    "payment_status": "finished",
    "pay_address": "0xTEST",
    "outcome_amount": "0.001"
  }'

# Verify database updated
psql -c "SELECT nowpayments_payment_id FROM private_channel_users_database WHERE nowpayments_order_id = 'PGP-TEST';"
```

---

### Phase 3: Token Enhancement (Week 2, Days 1-3)
**Goal**: Extend tokens to include payment_id fields

**Tasks:**
1. ✅ Update `token_manager.py` in GCWebhook1 (encrypt methods)
2. ✅ Update `token_manager.py` in GCWebhook1 (decrypt methods)
3. ✅ Update `cloudtasks_client.py` in GCWebhook1 (enhanced payloads)
4. ✅ Test token encoding/decoding with payment_id
5. ✅ Deploy updated GCWebhook1

**Deliverables:**
- Tokens include payment_id (backward compatible)
- Cloud Tasks payloads include payment_id
- Existing flows continue to work

**Testing:**
```python
# Test token with payment_id
token = token_manager.encrypt_token_for_gcwebhook2(
    user_id=123,
    closed_channel_id=-1001234,
    wallet_address="0xABC",
    payout_currency="shib",
    payout_network="eth",
    subscription_time_days=30,
    subscription_price="1.35",
    nowpayments_payment_id="4971340333",
    nowpayments_pay_address="0x1234",
    nowpayments_outcome_amount="0.0002712"
)

# Verify decoding
decoded = token_manager.decode_and_verify_token(token)
assert decoded[7] == "4971340333"  # payment_id at index 7
```

---

### Phase 4: GCAccumulator Integration (Week 2, Days 4-5)
**Goal**: Update GCAccumulator to store payment_id

**Tasks:**
1. ✅ Update `acc10-26.py` to accept payment_id in payload
2. ✅ Update `database_manager.py` to store payment_id
3. ✅ Deploy updated GCAccumulator
4. ✅ Test end-to-end flow

**Deliverables:**
- GCAccumulator stores payment_id in payout_accumulation
- End-to-end test successful
- Logging shows payment_id propagation

**Testing:**
```bash
# Trigger test payment
# 1. Create NowPayments invoice
# 2. Complete payment
# 3. Verify IPN received and payment_id stored
# 4. Verify GCAccumulator stored payment_id

psql -c "SELECT nowpayments_payment_id FROM payout_accumulation ORDER BY id DESC LIMIT 1;"
```

---

### Phase 5: Production Validation (Week 3)
**Goal**: Validate entire flow in production

**Tasks:**
1. ✅ Monitor IPN callbacks in production
2. ✅ Verify payment_id capture for real payments
3. ✅ Test NowPayments API queries with payment_id
4. ✅ Document edge cases and fixes
5. ✅ Update PROGRESS.md and DECISIONS.md

**Deliverables:**
- Production validation complete
- 100% payment_id capture rate
- Documentation updated

**Testing:**
```bash
# Query recent payments
psql -c "
SELECT
    id,
    user_id,
    private_channel_id,
    sub_price,
    nowpayments_payment_id,
    nowpayments_payment_status,
    nowpayments_outcome_amount
FROM private_channel_users_database
WHERE subscription_time > NOW() - INTERVAL '24 hours'
ORDER BY subscription_time DESC
LIMIT 10;
"

# Query NowPayments API with payment_id
curl -X GET "https://api.nowpayments.io/v1/payment/4971340333" \
  -H "x-api-key: $NOWPAYMENTS_API_KEY"
```

---

## Testing Strategy

### Unit Tests

```python
# test_ipn_signature.py
def test_ipn_signature_verification():
    """Test IPN signature verification."""
    payload = b'{"payment_id": "123", "order_id": "TEST"}'
    secret = "test_secret_key"

    # Generate signature
    signature = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()

    # Verify
    assert verify_ipn_signature(payload, signature, secret) == True

    # Test invalid signature
    assert verify_ipn_signature(payload, "invalid", secret) == False

# test_token_with_payment_id.py
def test_token_encoding_with_payment_id():
    """Test token encoding/decoding with payment_id."""
    token_manager = TokenManager("test_key")

    # Encrypt with payment_id
    token = token_manager.encrypt_token_for_gcwebhook2(
        user_id=123,
        closed_channel_id=-1001234,
        wallet_address="0xABC",
        payout_currency="shib",
        payout_network="eth",
        subscription_time_days=30,
        subscription_price="1.35",
        nowpayments_payment_id="4971340333",
        nowpayments_pay_address="0x1234",
        nowpayments_outcome_amount="0.0002712"
    )

    # Decrypt and verify
    decoded = token_manager.decode_and_verify_token(token)
    assert decoded[7] == "4971340333"  # payment_id
    assert decoded[8] == "0x1234"  # pay_address
    assert decoded[9] == "0.0002712"  # outcome_amount

# test_backward_compatibility.py
def test_token_without_payment_id():
    """Test backward compatibility: old tokens without payment_id."""
    token_manager = TokenManager("test_key")

    # Encrypt WITHOUT payment_id (old format)
    token = token_manager.encrypt_token_for_gcwebhook2(
        user_id=123,
        closed_channel_id=-1001234,
        wallet_address="0xABC",
        payout_currency="shib",
        payout_network="eth",
        subscription_time_days=30,
        subscription_price="1.35"
        # NO payment_id fields
    )

    # Decrypt should return None for payment_id fields
    decoded = token_manager.decode_and_verify_token(token)
    assert decoded[7] is None  # payment_id
    assert decoded[8] is None  # pay_address
    assert decoded[9] is None  # outcome_amount
```

### Integration Tests

```python
# test_ipn_endpoint.py
def test_ipn_endpoint_integration():
    """Test IPN endpoint end-to-end."""

    # 1. Create test order in database
    db_manager.record_private_channel_user(
        user_id=123,
        private_channel_id=-1001234,
        sub_time=30,
        sub_price="1.35",
        expire_time="23:59:59",
        expire_date="2025-12-01"
    )

    # Set order_id
    db_manager.update_order_id(user_id=123, order_id="TEST-ORDER-123")

    # 2. Send IPN request
    ipn_payload = {
        "payment_id": "4971340333",
        "order_id": "TEST-ORDER-123",
        "payment_status": "finished",
        "pay_address": "0xTEST",
        "outcome_amount": "0.001",
        "pay_currency": "eth"
    }

    signature = generate_ipn_signature(ipn_payload, IPN_SECRET)

    response = client.post(
        "/ipn",
        json=ipn_payload,
        headers={"x-nowpayments-sig": signature}
    )

    # 3. Verify response
    assert response.status_code == 200

    # 4. Verify database updated
    record = db_manager.get_record_by_order_id("TEST-ORDER-123")
    assert record['nowpayments_payment_id'] == "4971340333"
    assert record['nowpayments_pay_address'] == "0xTEST"
```

### Production Validation

```bash
#!/bin/bash
# validate_payment_id_capture.sh

echo "🔍 Validating payment_id capture in production..."

# Check recent payments
echo "📊 Recent payments (last 24 hours):"
gcloud sql execute telepaypsql --query="
SELECT
    COUNT(*) as total_payments,
    COUNT(nowpayments_payment_id) as with_payment_id,
    ROUND(100.0 * COUNT(nowpayments_payment_id) / COUNT(*), 2) as capture_rate
FROM private_channel_users_database
WHERE subscription_time > NOW() - INTERVAL '24 hours';
"

# Check accumulation records
echo "📊 Accumulation records with payment_id:"
gcloud sql execute telepaypsql --query="
SELECT
    COUNT(*) as total_accumulations,
    COUNT(nowpayments_payment_id) as with_payment_id
FROM payout_accumulation
WHERE created_at > NOW() - INTERVAL '24 hours';
"

# Check IPN logs
echo "📨 IPN callback logs (last hour):"
gcloud logging read "resource.labels.service_name=gcwebhook1-10-26 AND textPayload=~\"IPN\"" \
  --limit 50 \
  --format json \
  --freshness 1h

# Test NowPayments API query
echo "🔗 Testing NowPayments API query with captured payment_id:"
PAYMENT_ID=$(gcloud sql execute telepaypsql --query="
SELECT nowpayments_payment_id
FROM private_channel_users_database
WHERE nowpayments_payment_id IS NOT NULL
ORDER BY subscription_time DESC
LIMIT 1;
" --format=value)

curl -X GET "https://api.nowpayments.io/v1/payment/$PAYMENT_ID" \
  -H "x-api-key: $NOWPAYMENTS_API_KEY" \
  | jq '.'
```

---

## Deployment Plan

### Pre-Deployment Checklist

- [ ] Database migration script tested in staging
- [ ] IPN secret added to Secret Manager
- [ ] IPN callback URL configured in environment
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Code review completed
- [ ] Documentation updated

### Deployment Steps

#### Step 1: Database Migration
```bash
# Run migration in production
python /tools/execute_payment_id_migration.py

# Verify migration
psql -c "\d private_channel_users_database"
psql -c "\d payout_accumulation"
```

#### Step 2: Deploy GCWebhook1 (IPN Endpoint)
```bash
# Build and deploy
cd OCTOBER/10-26/GCWebhook1-10-26
gcloud run deploy gcwebhook1-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated

# Verify deployment
curl https://gcwebhook1-10-26-..../health
```

#### Step 3: Update TelePay Bot
```bash
# Update start_np_gateway.py with ipn_callback_url
# Deploy to bot hosting environment
# Restart bot
```

#### Step 4: Deploy GCAccumulator
```bash
# Build and deploy
cd OCTOBER/10-26/GCAccumulator-10-26
gcloud run deploy gcaccumulator-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated

# Verify deployment
curl https://gcaccumulator-10-26-..../health
```

#### Step 5: Production Validation
```bash
# Monitor IPN callbacks
gcloud logging tail "resource.labels.service_name=gcwebhook1-10-26" \
  --format json | grep "IPN"

# Create test payment
# Verify payment_id captured
# Verify propagation through pipeline
```

### Rollback Plan

If issues arise:

1. **Rollback GCWebhook1**:
   ```bash
   gcloud run services update-traffic gcwebhook1-10-26 \
     --to-revisions PREVIOUS_REVISION=100
   ```

2. **Rollback GCAccumulator**:
   ```bash
   gcloud run services update-traffic gcaccumulator-10-26 \
     --to-revisions PREVIOUS_REVISION=100
   ```

3. **Database is backward compatible** (new columns are optional, existing code works)

---

## Monitoring and Observability

### Key Metrics to Track

```python
# Metrics to monitor
metrics = {
    "ipn_callbacks_received": "Count of IPN callbacks",
    "ipn_signature_failures": "Count of invalid signatures",
    "payment_id_capture_rate": "% of payments with payment_id",
    "ipn_processing_latency": "Time to process IPN",
    "database_update_failures": "Failed DB updates"
}
```

### Logging Patterns

```python
# IPN received
print(f"📨 [IPN] Received IPN notification from NowPayments")

# Signature verified
print(f"✅ [IPN] Signature verified successfully")

# Database updated
print(f"💾 [IPN] Updated private_channel_users_database with payment_id")

# payment_id propagated
print(f"💳 [ENDPOINT] NowPayments Payment ID: {payment_id}")
```

### Alerting

```yaml
# Alerting rules
alerts:
  - name: IPN Signature Failures
    condition: ipn_signature_failures > 10 in 5 minutes
    severity: critical

  - name: Low Payment ID Capture Rate
    condition: payment_id_capture_rate < 90% over 1 hour
    severity: warning

  - name: IPN Processing Latency
    condition: ipn_processing_latency > 5 seconds
    severity: warning
```

---

## Success Criteria

### Phase 1 (Database Migration)
- ✅ All database columns created
- ✅ All indexes created
- ✅ Migration verified in production
- ✅ Zero downtime during migration

### Phase 2 (IPN Endpoint)
- ✅ IPN endpoint deployed and accessible
- ✅ Signature verification working (100% success rate)
- ✅ Database updates working (no failures)
- ✅ Idempotency handling working

### Phase 3 (Token Enhancement)
- ✅ Tokens include payment_id (when available)
- ✅ Backward compatibility maintained (old tokens still work)
- ✅ Cloud Tasks payloads include payment_id

### Phase 4 (GCAccumulator Integration)
- ✅ payment_id stored in payout_accumulation
- ✅ End-to-end flow working
- ✅ Logging shows payment_id propagation

### Phase 5 (Production Validation)
- ✅ **>95% payment_id capture rate** (target: 100%)
- ✅ **Zero IPN signature failures**
- ✅ **<500ms IPN processing latency**
- ✅ NowPayments API queries working with payment_id
- ✅ Fee discrepancy resolution possible

---

## Next Steps

1. **Review this document** with team/stakeholder
2. **Execute Phase 1** (Database Migration)
3. **Execute Phase 2** (IPN Endpoint Implementation)
4. **Continue with remaining phases**
5. **Integrate with fee discrepancy solution** (see `FEE_DISCREPANCY_ARCHITECTURAL_SOLUTION.md`)

---

## Related Work

Once payment_id storage is complete, integrate with:

1. **Fee Discrepancy Solution** (`FEE_DISCREPANCY_ARCHITECTURAL_SOLUTION.md`)
   - Use payment_id to query NowPayments API for actual amounts
   - Use pay_address for blockchain transaction matching
   - Calculate fee discrepancies accurately

2. **Customer Support Tools**
   - Build admin dashboard to query by payment_id
   - Enable support to lookup payments quickly

3. **Financial Reporting**
   - Calculate actual fees paid to NowPayments
   - Generate revenue reports with accurate amounts

---

**Document Owner:** Claude
**Last Updated:** 2025-11-02
**Version:** 1.0
**Status:** Ready for Implementation
