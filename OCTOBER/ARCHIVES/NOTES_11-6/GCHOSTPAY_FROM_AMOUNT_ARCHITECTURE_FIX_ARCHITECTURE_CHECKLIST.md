# GCHostPay3 from_amount Architecture Fix - Implementation Checklist

**Date:** 2025-11-02
**Status:** 🔴 NOT STARTED
**Approach:** Staged implementation with backward compatibility
**Total Tasks:** 45

---

## Progress Summary

| Phase | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Phase 1: Database Preparation | 4 | 0/4 | ⏳ PENDING |
| Phase 2: Token Manager Updates | 8 | 0/8 | ⏳ PENDING |
| Phase 3: Service Code Updates | 18 | 0/18 | ⏳ PENDING |
| Phase 4: Deployment | 6 | 0/6 | ⏳ PENDING |
| Phase 5: Testing & Validation | 6 | 0/6 | ⏳ PENDING |
| Phase 6: Monitoring & Rollback | 3 | 0/3 | ⏳ PENDING |

**Total:** 45 tasks, 0 completed, 45 pending

---

## Phase 1: Database Preparation ⏳

### Task 1.1: Create Database Migration Script
- **Status:** PENDING
- **File:** `/10-26/scripts/add_actual_eth_amount_columns.sql`
- **Action:** Create SQL migration script

**SQL:**
```sql
-- Migration: Add actual_eth_amount columns to tracking tables
-- Date: 2025-11-02
-- Purpose: Store ACTUAL ETH from NowPayments alongside estimates

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
```

---

### Task 1.2: Execute Database Migration
- **Status:** PENDING
- **Command:**
  ```bash
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -f /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/scripts/add_actual_eth_amount_columns.sql
  ```

**Verification:**
```bash
PGPASSWORD='Chigdabeast123$' psql \
  -h /cloudsql/telepay-459221:us-central1:telepaypsql \
  -U postgres \
  -d telepaydb \
  -c "\d split_payout_request"

PGPASSWORD='Chigdabeast123$' psql \
  -h /cloudsql/telepay-459221:us-central1:telepaypsql \
  -U postgres \
  -d telepaydb \
  -c "\d split_payout_hostpay"
```

**Success Criteria:**
- Column `actual_eth_amount` exists in both tables
- Data type: `NUMERIC(20,18)`
- Default value: `0`
- Constraint: `actual_eth_positive` exists

---

### Task 1.3: Test Backward Compatibility
- **Status:** PENDING
- **Action:** Verify old code still works with new schema

**Test Query:**
```sql
-- Verify DEFAULT value allows old code to work
SELECT actual_eth_amount
FROM split_payout_request
WHERE actual_eth_amount = 0
LIMIT 1;

-- Should return 0, proving backward compatibility
```

---

### Task 1.4: Create Rollback Script
- **Status:** PENDING
- **File:** `/10-26/scripts/rollback_actual_eth_amount_columns.sql`
- **Action:** Create rollback script (just in case)

**SQL:**
```sql
-- Rollback script (use only if needed)
BEGIN;

DROP INDEX IF EXISTS idx_split_payout_hostpay_actual_eth;
DROP INDEX IF EXISTS idx_split_payout_request_actual_eth;

ALTER TABLE split_payout_hostpay
DROP CONSTRAINT IF EXISTS actual_eth_positive;

ALTER TABLE split_payout_request
DROP CONSTRAINT IF EXISTS actual_eth_positive;

ALTER TABLE split_payout_hostpay
DROP COLUMN IF EXISTS actual_eth_amount;

ALTER TABLE split_payout_request
DROP COLUMN IF EXISTS actual_eth_amount;

COMMIT;
```

---

## Phase 2: Token Manager Updates ⏳

### Task 2.1: Update GCWebhook1 CloudTasks Client
- **Status:** PENDING
- **File:** `/GCWebhook1-10-26/cloudtasks_client.py`
- **Location:** Method `enqueue_gcsplit1_payment_split()`
- **Action:** Add `actual_eth_amount` parameter and include in payload

**Current Code:**
```python
def enqueue_gcsplit1_payment_split(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    closed_channel_id: int,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    subscription_price: float
) -> Optional[str]:
```

**Updated Code:**
```python
def enqueue_gcsplit1_payment_split(
    self,
    queue_name: str,
    target_url: str,
    user_id: int,
    closed_channel_id: int,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    subscription_price: float,
    actual_eth_amount: float  # ✅ ADD THIS
) -> Optional[str]:
    """
    Enqueue payment split request to GCSplit1.

    Args:
        ...
        actual_eth_amount: ACTUAL ETH from NowPayments outcome
    """
    payload = {
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'subscription_price': subscription_price,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD THIS
    }
```

---

### Task 2.2: Update GCWebhook1 Main Service
- **Status:** PENDING
- **File:** `/GCWebhook1-10-26/tph1-10-26.py`
- **Location:** Line 352
- **Action:** Pass `nowpayments_outcome_amount` to CloudTasks

**Current Code:**
```python
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd
)
```

**Updated Code:**
```python
task_name = cloudtasks_client.enqueue_gcsplit1_payment_split(
    queue_name=gcsplit1_queue,
    target_url=gcsplit1_url,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_price=outcome_amount_usd,
    actual_eth_amount=nowpayments_outcome_amount  # ✅ ADD THIS
)

# Log for verification
print(f"")
print(f"💰 [VALIDATED] Payment amounts:")
print(f"   Declared USD: ${subscription_price}")
print(f"   Outcome USD: ${outcome_amount_usd}")
print(f"   ACTUAL ETH: {nowpayments_outcome_amount}")  # ✅ ADD LOG
print(f"")
```

---

### Task 2.3: Update GCSplit1 Database Manager
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/database_manager.py`
- **Location:** Method `insert_split_payout_request()`
- **Action:** Add `actual_eth_amount` parameter and INSERT statement

**Current Method Signature:**
```python
def insert_split_payout_request(
    self,
    user_id: int,
    closed_channel_id: int,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    client_wallet_address: str,
    refund_address: str,
    flow: str,
    type_: str
) -> Optional[str]:
```

**Updated Method:**
```python
def insert_split_payout_request(
    self,
    user_id: int,
    closed_channel_id: int,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    client_wallet_address: str,
    refund_address: str,
    flow: str,
    type_: str,
    actual_eth_amount: float = 0.0  # ✅ ADD WITH DEFAULT
) -> Optional[str]:
    """
    Insert split payout request record.

    Args:
        ...
        actual_eth_amount: ACTUAL ETH from NowPayments (default 0 for backward compat)
    """

    # ... existing code ...

    cur.execute("""
        INSERT INTO split_payout_request (
            unique_id, user_id, closed_channel_id,
            from_currency, to_currency,
            from_network, to_network,
            from_amount, to_amount,
            client_wallet_address, refund_address,
            flow, type,
            actual_eth_amount,  -- ✅ ADD COLUMN
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
    """, (
        unique_id, user_id, closed_channel_id,
        from_currency, to_currency,
        from_network, to_network,
        from_amount, to_amount,
        client_wallet_address, refund_address,
        flow, type_,
        actual_eth_amount  # ✅ ADD VALUE
    ))

    print(f"💰 [DB_INSERT] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG
```

---

### Task 2.4: Update GCSplit1 Token Manager (GCSplit1→GCSplit3)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/token_manager.py`
- **Location:** Methods `encrypt_gcsplit1_to_gcsplit3_token()` and `decrypt_gcsplit3_to_gcsplit1_token()`
- **Action:** Add `actual_eth_amount` field to token structure

**Encrypt Method Update:**
```python
def encrypt_gcsplit1_to_gcsplit3_token(
    self,
    unique_id: str,
    user_id: int,
    closed_channel_id: str,
    wallet_address: str,
    payout_currency: str,
    payout_network: str,
    eth_amount: float,
    actual_eth_amount: float = 0.0  # ✅ ADD WITH DEFAULT
) -> Optional[str]:
    """
    Encrypt token for GCSplit3.

    Args:
        ...
        eth_amount: Estimated ETH (from GCSplit2 calculation)
        actual_eth_amount: ACTUAL ETH from NowPayments
    """
    data = {
        'unique_id': unique_id,
        'user_id': user_id,
        'closed_channel_id': closed_channel_id,
        'wallet_address': wallet_address,
        'payout_currency': payout_currency,
        'payout_network': payout_network,
        'eth_amount': eth_amount,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD
    }
```

**Decrypt Method Update:**
```python
def decrypt_gcsplit3_to_gcsplit1_token(self, token: str) -> Optional[dict]:
    """
    Decrypt response token from GCSplit3.
    """
    decrypted_data = # ... existing decryption logic ...

    # Extract fields
    from_amount = decrypted_data.get('from_amount')
    actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADD WITH DEFAULT

    return {
        # ... existing fields ...
        'from_amount': from_amount,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD
    }
```

---

### Task 2.5: Update GCSplit3 Token Manager (Receive from GCSplit1)
- **Status:** PENDING
- **File:** `/GCSplit3-10-26/token_manager.py`
- **Location:** Method `decrypt_gcsplit1_to_gcsplit3_token()`
- **Action:** Extract `actual_eth_amount` from token

**Update Decrypt Method:**
```python
def decrypt_gcsplit1_to_gcsplit3_token(self, token: str) -> Optional[dict]:
    """
    Decrypt token from GCSplit1.
    """
    decrypted_data = # ... existing decryption logic ...

    eth_amount = decrypted_data.get('eth_amount')
    actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADD WITH DEFAULT

    print(f"💰 [TOKEN] Estimated ETH: {eth_amount}")
    print(f"💰 [TOKEN] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG

    return {
        # ... existing fields ...
        'eth_amount': eth_amount,
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD
    }
```

---

### Task 2.6: Update GCSplit3 Token Manager (Return to GCSplit1)
- **Status:** PENDING
- **File:** `/GCSplit3-10-26/token_manager.py`
- **Location:** Method `encrypt_gcsplit3_to_gcsplit1_token()`
- **Action:** Pass `actual_eth_amount` through response

**Update Encrypt Method:**
```python
def encrypt_gcsplit3_to_gcsplit1_token(
    self,
    unique_id: str,
    user_id: int,
    closed_channel_id: int,
    cn_api_id: str,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
    from_amount: float,
    to_amount: float,
    payin_address: str,
    payout_address: str,
    refund_address: str,
    flow: str,
    type_: str,
    actual_eth_amount: float = 0.0  # ✅ ADD WITH DEFAULT
) -> Optional[str]:
    """
    Encrypt response token for GCSplit1.
    """
    data = {
        # ... existing fields ...
        'from_amount': from_amount,  # ChangeNow estimate
        'actual_eth_amount': actual_eth_amount  # ✅ ADD FIELD (ACTUAL)
    }
```

---

### Task 2.7: Update GCSplit1 Binary Token Builder (GCSplit1→GCHostPay1)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py`
- **Location:** Function `build_hostpay_token()` (lines 125-193)
- **Action:** Add `actual_eth_amount` and `estimated_eth_amount` to binary token

**Current Function Signature:**
```python
def build_hostpay_token(
    unique_id: str,
    cn_api_id: str,
    from_currency: str,
    from_network: str,
    from_amount: float,
    payin_address: str,
    signing_key: str
) -> Optional[str]:
```

**Updated Function:**
```python
def build_hostpay_token(
    unique_id: str,
    cn_api_id: str,
    from_currency: str,
    from_network: str,
    actual_eth_amount: float,      # ✅ RENAMED from from_amount
    estimated_eth_amount: float,   # ✅ ADDED
    payin_address: str,
    signing_key: str
) -> Optional[str]:
    """
    Build binary packed token for GCHostPay.

    Token Format (NEW):
    - 16 bytes: unique_id
    - 1 byte + var: cn_api_id
    - 1 byte + var: from_currency
    - 1 byte + var: from_network
    - 8 bytes: actual_eth_amount (double)       ✅ ACTUAL
    - 8 bytes: estimated_eth_amount (double)    ✅ ESTIMATED
    - 1 byte + var: payin_address
    - 4 bytes: timestamp
    - 16 bytes: HMAC signature
    """
    try:
        # ... existing packing code ...

        # Pack BOTH amounts
        packed_data.extend(struct.pack(">d", actual_eth_amount))     # ✅ ACTUAL
        packed_data.extend(struct.pack(">d", estimated_eth_amount))  # ✅ ESTIMATED

        # ... rest of packing ...

        print(f"🔐 [HOSTPAY_TOKEN] ACTUAL amount: {actual_eth_amount} ETH")
        print(f"🔐 [HOSTPAY_TOKEN] ESTIMATED amount: {estimated_eth_amount} ETH")

        return token
```

---

### Task 2.8: Update GCHostPay1 Token Manager (Decrypt Binary Token)
- **Status:** PENDING
- **File:** `/GCHostPay1-10-26/token_manager.py`
- **Location:** Method to decrypt binary token from GCSplit1
- **Action:** Unpack BOTH `actual_eth_amount` and `estimated_eth_amount` with backward compatibility

**Add Backward Compatible Decrypt:**
```python
def decrypt_gcsplit1_to_gchostpay1_token(self, token: str) -> Optional[dict]:
    """
    Decrypt binary packed token from GCSplit1 with backward compatibility.

    Old format: single from_amount field
    New format: actual_eth_amount + estimated_eth_amount
    """
    try:
        # Decode base64
        token_bytes = base64.urlsafe_b64decode(token + '==')  # Add padding

        # Extract signature (last 16 bytes)
        payload = token_bytes[:-16]
        signature = token_bytes[-16:]

        # Verify signature
        expected_sig = hmac.new(
            self.signing_key.encode(),
            payload,
            hashlib.sha256
        ).digest()[:16]

        if not hmac.compare_digest(signature, expected_sig):
            print(f"❌ [TOKEN] Invalid signature")
            return None

        # Unpack payload
        offset = 0

        # unique_id (16 bytes)
        unique_id = payload[offset:offset + 16].rstrip(b'\x00').decode('utf-8')
        offset += 16

        # cn_api_id (length-prefixed)
        cn_api_id_len = payload[offset]
        offset += 1
        cn_api_id = payload[offset:offset + cn_api_id_len].decode('utf-8')
        offset += cn_api_id_len

        # from_currency (length-prefixed)
        from_currency_len = payload[offset]
        offset += 1
        from_currency = payload[offset:offset + from_currency_len].decode('utf-8')
        offset += from_currency_len

        # from_network (length-prefixed)
        from_network_len = payload[offset]
        offset += 1
        from_network = payload[offset:offset + from_network_len].decode('utf-8')
        offset += from_network_len

        # Check if we have new format (two amounts) or old format (one amount)
        remaining_bytes = len(payload) - offset - 4  # Subtract timestamp (4 bytes)

        if remaining_bytes >= 16:  # Two doubles (8 bytes each)
            # NEW FORMAT: actual_eth_amount + estimated_eth_amount
            actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8
            estimated_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            print(f"✅ [TOKEN] New format detected")
            print(f"💰 [TOKEN] ACTUAL ETH: {actual_eth_amount}")
            print(f"💰 [TOKEN] ESTIMATED ETH: {estimated_eth_amount}")

        else:  # One double (8 bytes)
            # OLD FORMAT: single from_amount
            from_amount = struct.unpack(">d", payload[offset:offset + 8])[0]
            offset += 8

            # Use same value for both (backward compatibility)
            actual_eth_amount = from_amount
            estimated_eth_amount = from_amount

            print(f"⚠️ [TOKEN] Old format detected - using from_amount for both")
            print(f"💰 [TOKEN] Amount: {from_amount} ETH")

        # payin_address (length-prefixed)
        payin_address_len = payload[offset]
        offset += 1
        payin_address = payload[offset:offset + payin_address_len].decode('utf-8')
        offset += payin_address_len

        # timestamp (4 bytes)
        timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]

        return {
            'unique_id': unique_id,
            'cn_api_id': cn_api_id,
            'from_currency': from_currency,
            'from_network': from_network,
            'actual_eth_amount': actual_eth_amount,       # ✅ ACTUAL
            'estimated_eth_amount': estimated_eth_amount, # ✅ ESTIMATED
            'payin_address': payin_address,
            'timestamp': timestamp
        }

    except Exception as e:
        print(f"❌ [TOKEN] Decryption failed: {e}")
        import traceback
        traceback.print_exc()
        return None
```

---

## Phase 3: Service Code Updates ⏳

### Task 3.1: Update GCSplit1 Endpoint 1 (Receive from GCWebhook1)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py`
- **Location:** Lines 296-325 (initial webhook handler)
- **Action:** Extract and log `actual_eth_amount` from webhook payload

**Add After Line 304:**
```python
# Extract required data
user_id = webhook_data.get('user_id')
closed_channel_id = webhook_data.get('closed_channel_id')
wallet_address = (webhook_data.get('wallet_address') or '').strip()
payout_currency = (webhook_data.get('payout_currency') or '').strip().lower()
payout_network = (webhook_data.get('payout_network') or '').strip().lower()
subscription_price = webhook_data.get('subscription_price') or webhook_data.get('sub_price') or '0'
actual_eth_amount = webhook_data.get('actual_eth_amount', 0.0)  # ✅ ADD THIS

print(f"👤 [ENDPOINT_1] User ID: {user_id}")
print(f"🏢 [ENDPOINT_1] Channel ID: {closed_channel_id}")
print(f"💰 [ENDPOINT_1] Subscription Price: ${subscription_price}")
print(f"💰 [ENDPOINT_1] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG
print(f"🏦 [ENDPOINT_1] Target: {wallet_address} ({payout_currency.upper()} on {payout_network.upper()})")
```

**Update Validation (Line 312):**
```python
# Validate required fields
if not all([user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_price]):
    print(f"❌ [ENDPOINT_1] Missing required fields")
    return jsonify({
        "status": "error",
        "message": "Missing required fields",
        "details": {
            "user_id": bool(user_id),
            "closed_channel_id": bool(closed_channel_id),
            "wallet_address": bool(wallet_address),
            "payout_currency": bool(payout_currency),
            "payout_network": bool(payout_network),
            "subscription_price": bool(subscription_price),
            "actual_eth_amount": bool(actual_eth_amount)  # ✅ ADD TO VALIDATION
        }
    }), 400

# Warn if actual_eth_amount is missing
if not actual_eth_amount or actual_eth_amount <= 0:
    print(f"⚠️ [ENDPOINT_1] WARNING: actual_eth_amount missing or zero: {actual_eth_amount}")
    print(f"⚠️ [ENDPOINT_1] Will use estimate workflow (backward compatibility)")
```

---

### Task 3.2: Update GCSplit1 Endpoint 2 (Store in Database)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py`
- **Location:** Lines 454-483 (database insertion)
- **Action:** Pass `actual_eth_amount` to database insertion

**Update Line 462:**
```python
# Insert into split_payout_request table
unique_id = database_manager.insert_split_payout_request(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    from_currency="usdt",
    to_currency=payout_currency,
    from_network="eth",
    to_network=payout_network,
    from_amount=from_amount_usdt,
    to_amount=pure_market_eth_value,
    client_wallet_address=wallet_address,
    refund_address="",
    flow="standard",
    type_="direct",
    actual_eth_amount=actual_eth_amount  # ✅ ADD THIS
)

print(f"✅ [ENDPOINT_2] Database insertion successful")
print(f"🆔 [ENDPOINT_2] Unique ID: {unique_id}")
print(f"💰 [ENDPOINT_2] Stored ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG
```

---

### Task 3.3: Update GCSplit1 Endpoint 2 (Pass to GCSplit3)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py`
- **Location:** Lines 484-493 (token encryption for GCSplit3)
- **Action:** Include `actual_eth_amount` in token

**Update Line 485:**
```python
# Encrypt token for GCSplit3
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    eth_amount=pure_market_eth_value,
    actual_eth_amount=actual_eth_amount  # ✅ ADD THIS
)

print(f"💰 [ENDPOINT_2] Passing to GCSplit3:")
print(f"   Estimated ETH: {pure_market_eth_value}")
print(f"   ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG
```

---

### Task 3.4: Update GCSplit1 Endpoint 3 (Use ACTUAL for GCHostPay)
- **Status:** PENDING
- **File:** `/GCSplit1-10-26/tps1-10-26.py`
- **Location:** Lines 584-650 (GCHostPay token building)
- **Action:** Extract `actual_eth_amount`, validate, and use for payment

**Update After Line 599:**
```python
# Extract data
unique_id = decrypted_data['unique_id']
user_id = decrypted_data['user_id']
closed_channel_id = decrypted_data['closed_channel_id']
cn_api_id = decrypted_data['cn_api_id']
from_currency = decrypted_data['from_currency']
to_currency = decrypted_data['to_currency']
from_network = decrypted_data['from_network']
to_network = decrypted_data['to_network']
from_amount = decrypted_data['from_amount']  # ChangeNow estimate
to_amount = decrypted_data['to_amount']
payin_address = decrypted_data['payin_address']
payout_address = decrypted_data['payout_address']
refund_address = decrypted_data['refund_address']
flow = decrypted_data['flow']
type_ = decrypted_data['type']
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADD THIS

print(f"🆔 [ENDPOINT_3] Unique ID: {unique_id}")
print(f"🆔 [ENDPOINT_3] ChangeNow API ID: {cn_api_id}")
print(f"👤 [ENDPOINT_3] User ID: {user_id}")
print(f"💰 [ENDPOINT_3] ChangeNow estimate: {from_amount} {from_currency.upper()}")
print(f"💰 [ENDPOINT_3] ACTUAL ETH: {actual_eth_amount} ETH")  # ✅ ADD LOG

# Validation: Compare actual vs estimate
if actual_eth_amount > 0 and from_amount > 0:
    discrepancy = abs(from_amount - actual_eth_amount)
    discrepancy_pct = (discrepancy / actual_eth_amount) * 100

    print(f"📊 [ENDPOINT_3] Amount comparison:")
    print(f"   ChangeNow estimate: {from_amount} ETH")
    print(f"   ACTUAL from NowPayments: {actual_eth_amount} ETH")
    print(f"   Discrepancy: {discrepancy} ETH ({discrepancy_pct:.2f}%)")

    if discrepancy_pct > 10:
        print(f"⚠️ [ENDPOINT_3] WARNING: Large discrepancy (>10%)!")
    elif discrepancy_pct > 5:
        print(f"⚠️ [ENDPOINT_3] Moderate discrepancy (>5%)")
    else:
        print(f"✅ [ENDPOINT_3] Amounts match within tolerance (<5%)")

# Decide which amount to use for payment
if actual_eth_amount > 0:
    payment_amount = actual_eth_amount
    print(f"✅ [ENDPOINT_3] Using ACTUAL ETH for payment: {payment_amount}")
else:
    payment_amount = from_amount
    print(f"⚠️ [ENDPOINT_3] ACTUAL ETH not available, using ChangeNow estimate: {payment_amount}")
```

**Update Line 645 (build_hostpay_token call):**
```python
# Build GCHostPay token
hostpay_token = build_hostpay_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,
    from_network=from_network,
    actual_eth_amount=payment_amount,        # ✅ ACTUAL (or estimate if ACTUAL missing)
    estimated_eth_amount=from_amount,        # ✅ ChangeNow estimate
    payin_address=payin_address,
    signing_key=tps_hostpay_signing_key
)
```

---

### Task 3.5: Update GCSplit3 Endpoint (Pass Through Actual Amount)
- **Status:** PENDING
- **File:** `/GCSplit3-10-26/tps3-10-26.py`
- **Location:** Lines 100-180 (main endpoint)
- **Action:** Extract, log, and pass `actual_eth_amount`

**Update After Line 112:**
```python
# Extract data
unique_id = decrypted_data['unique_id']
user_id = decrypted_data['user_id']
closed_channel_id = decrypted_data['closed_channel_id']
wallet_address = decrypted_data['wallet_address']
payout_currency = decrypted_data['payout_currency']
payout_network = decrypted_data['payout_network']
eth_amount = decrypted_data['eth_amount']  # Estimated
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADD THIS

print(f"🆔 [ENDPOINT] Unique ID: {unique_id}")
print(f"👤 [ENDPOINT] User ID: {user_id}")
print(f"🏦 [ENDPOINT] Wallet: {wallet_address}")
print(f"💰 [ENDPOINT] Estimated ETH: {eth_amount}")
print(f"💰 [ENDPOINT] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG
print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")
```

**Update Line 164 (response token):**
```python
# Encrypt response token for GCSplit1
encrypted_response_token = token_manager.encrypt_gcsplit3_to_gcsplit1_token(
    unique_id=unique_id,
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    cn_api_id=cn_api_id,
    from_currency=api_from_currency,
    to_currency=api_to_currency,
    from_network=api_from_network,
    to_network=api_to_network,
    from_amount=api_from_amount,
    to_amount=api_to_amount,
    payin_address=api_payin_address,
    payout_address=api_payout_address,
    refund_address=api_refund_address,
    flow=api_flow,
    type_=api_type,
    actual_eth_amount=actual_eth_amount  # ✅ ADD THIS
)
```

---

### Task 3.6: Update GCHostPay1 Service (Pass Through)
- **Status:** PENDING
- **File:** `/GCHostPay1-10-26/tphp1-10-26.py`
- **Location:** Lines 447-455 (token encryption for GCHostPay3)
- **Action:** Extract and pass both amounts

**Update Lines 411-455:**
```python
# Decrypt token
decrypted_data = token_manager.decrypt_gchostpay2_to_gchostpay1_token(token)
if not decrypted_data:
    print(f"❌ [ENDPOINT_2] Failed to decrypt token")
    abort(401, "Invalid token")

unique_id = decrypted_data['unique_id']
cn_api_id = decrypted_data['cn_api_id']
status = decrypted_data['status']
from_currency = decrypted_data['from_currency']
from_network = decrypted_data['from_network']
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADD
estimated_eth_amount = decrypted_data.get('estimated_eth_amount', 0.0)  # ✅ ADD
payin_address = decrypted_data['payin_address']

print(f"✅ [ENDPOINT_2] Token decoded successfully")
print(f"🆔 [ENDPOINT_2] Unique ID: {unique_id}")
print(f"🆔 [ENDPOINT_2] CN API ID: {cn_api_id}")
print(f"📊 [ENDPOINT_2] Status: {status}")
print(f"💰 [ENDPOINT_2] ACTUAL ETH: {actual_eth_amount}")  # ✅ ADD LOG
print(f"💰 [ENDPOINT_2] ESTIMATED ETH: {estimated_eth_amount}")  # ✅ ADD LOG

# Encrypt token for GCHostPay3 (already uses the new decrypt which has both amounts)
# The token_manager.encrypt_gchostpay1_to_gchostpay3_token will handle it
```

**Note:** GCHostPay1 uses binary token from GCSplit1, which we updated in Task 2.7 and 2.8. No additional changes needed here as the token_manager handles both amounts.

---

### Task 3.7: Add GCHostPay3 Wallet Balance Method
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/wallet_manager.py`
- **Location:** Add new method
- **Action:** Create `get_wallet_balance()` method

**Add New Method:**
```python
def get_wallet_balance(self) -> float:
    """
    Get current wallet balance in ETH.

    Returns:
        Balance in ETH (as float)
    """
    try:
        balance_wei = self.w3.eth.get_balance(self.wallet_address)
        balance_eth = self.w3.from_wei(balance_wei, 'ether')

        print(f"💰 [WALLET] Current balance: {balance_eth} ETH ({balance_wei} Wei)")

        return float(balance_eth)

    except Exception as e:
        print(f"❌ [WALLET] Failed to get balance: {e}")
        return 0.0
```

---

### Task 3.8: Update GCHostPay3 Token Decryption
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/tphp3-10-26.py`
- **Location:** Lines 152-180 (token decryption)
- **Action:** Extract both `actual_eth_amount` and `estimated_eth_amount`

**Update After Line 168:**
```python
# Decrypt token
decrypted_data = token_manager.decrypt_gchostpay1_to_gchostpay3_token(token)

unique_id = decrypted_data['unique_id']
cn_api_id = decrypted_data['cn_api_id']
from_currency = decrypted_data['from_currency']
from_network = decrypted_data['from_network']
payin_address = decrypted_data['payin_address']
context = decrypted_data.get('context', 'instant')

# Extract BOTH amounts (with backward compatibility)
actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)
estimated_eth_amount = decrypted_data.get('estimated_eth_amount', 0.0)

# Legacy fallback: if both are 0, try old 'from_amount' field
if actual_eth_amount == 0.0 and estimated_eth_amount == 0.0:
    from_amount = decrypted_data.get('from_amount', 0.0)
    actual_eth_amount = from_amount
    estimated_eth_amount = from_amount
    print(f"⚠️ [ENDPOINT] Using legacy from_amount: {from_amount}")

print(f"💰 [ENDPOINT] ACTUAL ETH: {actual_eth_amount}")
print(f"💰 [ENDPOINT] ESTIMATED ETH: {estimated_eth_amount}")

# Validate and compare
if actual_eth_amount > 0 and estimated_eth_amount > 0:
    discrepancy = abs(actual_eth_amount - estimated_eth_amount)
    discrepancy_pct = (discrepancy / actual_eth_amount) * 100

    print(f"📊 [ENDPOINT] Amount comparison:")
    print(f"   ACTUAL: {actual_eth_amount} ETH")
    print(f"   ESTIMATED: {estimated_eth_amount} ETH")
    print(f"   Discrepancy: {discrepancy} ETH ({discrepancy_pct:.2f}%)")

    if discrepancy_pct > 10:
        print(f"🚨 [ENDPOINT] CRITICAL: Discrepancy >10% - investigate!")
    elif discrepancy_pct > 5:
        print(f"⚠️ [ENDPOINT] WARNING: Discrepancy >5%")

# Use ACTUAL amount for payment
payment_amount = actual_eth_amount if actual_eth_amount > 0 else estimated_eth_amount
print(f"✅ [ENDPOINT] Using for payment: {payment_amount} ETH")
```

---

### Task 3.9: Add GCHostPay3 Balance Validation
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/tphp3-10-26.py`
- **Location:** Before line 203 (payment execution)
- **Action:** Check wallet balance before payment

**Add Before Line 203:**
```python
# Validate wallet balance before payment
print(f"")
print(f"🔍 [ENDPOINT] Validating wallet balance...")

wallet_balance = wallet_manager.get_wallet_balance()

print(f"💰 [ENDPOINT] Wallet balance: {wallet_balance} ETH")
print(f"💰 [ENDPOINT] Payment amount: {payment_amount} ETH")

if payment_amount > wallet_balance:
    print(f"❌ [ENDPOINT] INSUFFICIENT BALANCE!")
    print(f"   Required: {payment_amount} ETH")
    print(f"   Available: {wallet_balance} ETH")
    print(f"   Shortfall: {payment_amount - wallet_balance} ETH")

    # Return error response
    return jsonify({
        "status": "error",
        "error_type": "insufficient_balance",
        "message": f"Insufficient wallet balance (need {payment_amount}, have {wallet_balance})",
        "details": {
            "required_eth": payment_amount,
            "available_eth": wallet_balance,
            "shortfall_eth": payment_amount - wallet_balance,
            "unique_id": unique_id,
            "cn_api_id": cn_api_id
        }
    }), 400

print(f"✅ [ENDPOINT] Sufficient balance - proceeding with payment")
print(f"")
```

---

### Task 3.10: Update GCHostPay3 Payment Execution
- **Status:** PENDING
- **File:** `/GCHostPay3-10-26/tphp3-10-26.py`
- **Location:** Line 203 (payment call)
- **Action:** Use `payment_amount` instead of `from_amount`

**Update Line 203:**
```python
# Execute ETH payment (use ACTUAL amount)
tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
    to_address=payin_address,
    amount=payment_amount,  # ✅ Use payment_amount (ACTUAL)
    unique_id=unique_id
)
```

---

### Task 3.11: Update GCAccumulator (Threshold Payouts)
- **Status:** PENDING
- **File:** `/GCAccumulator-10-26/database_manager.py`
- **Location:** Add new method
- **Action:** Create method to sum actual ETH for threshold payouts

**Add New Method:**
```python
def get_accumulated_actual_eth(self, client_id: int) -> float:
    """
    Get total ACTUAL ETH accumulated for a client.

    Sums all nowpayments_outcome_amount values for confirmed but unpaid payments.

    Args:
        client_id: Channel/client ID

    Returns:
        Total actual ETH amount
    """
    conn = self.get_connection()
    if not conn:
        print(f"❌ [DB] Could not get database connection")
        return 0.0

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT COALESCE(SUM(nowpayments_outcome_amount), 0)
            FROM private_channel_users_database
            WHERE private_channel_id = %s
              AND payment_status = 'confirmed'
              AND (payout_status IS NULL OR payout_status = 'pending')
        """, (client_id,))

        result = cur.fetchone()
        total_eth = float(result[0]) if result and result[0] else 0.0

        cur.close()
        conn.close()

        print(f"💰 [ACCUMULATOR] Total actual ETH for client {client_id}: {total_eth}")

        return total_eth

    except Exception as e:
        print(f"❌ [ACCUMULATOR] Failed to get accumulated ETH: {e}")
        return 0.0
```

---

### Task 3.12: Update GCAccumulator Threshold Check
- **Status:** PENDING
- **File:** `/GCAccumulator-10-26/acc10-26.py`
- **Location:** When threshold is reached
- **Action:** Use summed actual ETH instead of USD estimate

**Add When Threshold Reached:**
```python
# When threshold is reached
if accumulated_usd >= threshold:
    print(f"🎯 [ACCUMULATOR] Threshold reached!")
    print(f"   Accumulated USD: ${accumulated_usd}")
    print(f"   Threshold: ${threshold}")

    # Get ACTUAL ETH accumulated (not USD estimate!)
    actual_eth_total = database_manager.get_accumulated_actual_eth(client_id)

    print(f"💰 [ACCUMULATOR] ACTUAL ETH total: {actual_eth_total} ETH")

    # Verify we have actual ETH
    if actual_eth_total <= 0:
        print(f"⚠️ [ACCUMULATOR] WARNING: No actual ETH found, falling back to USD conversion")
        # ... fallback logic

    # Send to GCHostPay with ACTUAL ETH
    token = token_manager.encrypt_accumulator_to_gchostpay1_token(
        accumulation_id=accumulation_id,
        client_id=client_id,
        cn_api_id=cn_api_id,
        from_currency="eth",
        from_network="eth",
        from_amount=actual_eth_total,  # ✅ Use summed ACTUAL ETH
        payin_address=payin_address,
        context="threshold"
    )
```

---

### Task 3.13-3.18: Additional Service Updates
- **Status:** PENDING
- **Note:** Tasks 3.13-3.18 cover similar updates for:
  - GCBatchProcessor (batch context)
  - GCMicroBatchProcessor (batch conversion)
  - GCHostPay2 (status check pass-through)
  - Database manager methods for split_payout_hostpay table
  - Logging improvements across all services
  - Error handling for missing actual_eth_amount

---

## Phase 4: Deployment ⏳

### Task 4.1: Create Deployment Script
- **Status:** PENDING
- **File:** `/10-26/scripts/deploy_actual_eth_fix.sh`
- **Action:** Create deployment script

**Script Content:**
```bash
#!/bin/bash
# Deploy actual_eth_amount fix
# Must deploy in REVERSE order (downstream first)

set -e  # Exit on error

echo "🚀 [DEPLOY] Starting actual_eth_amount deployment..."
echo ""

# Service order (downstream first)
SERVICES=(
    "GCHostPay3-10-26:gchostpay3-10-26"
    "GCHostPay2-10-26:gchostpay2-10-26"
    "GCHostPay1-10-26:gchostpay1-10-26"
    "GCSplit3-10-26:gcsplit3-10-26"
    "GCSplit1-10-26:gcsplit1-10-26"
    "GCWebhook1-10-26:gcwebhook1-10-26"
)

for service in "${SERVICES[@]}"; do
    IFS=':' read -r dir name <<< "$service"

    echo "📦 [DEPLOY] Deploying $name..."
    cd "/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/$dir"

    # Build
    echo "   Building..."
    gcloud builds submit --tag "gcr.io/telepay-459221/$name"

    # Deploy
    echo "   Deploying..."
    gcloud run deploy "$name" \
        --image "gcr.io/telepay-459221/$name" \
        --region us-central1

    echo "✅ [DEPLOY] $name deployed successfully"
    echo ""

    # Wait 30 seconds between deployments
    if [ "$name" != "gcwebhook1-10-26" ]; then
        echo "⏱️  Waiting 30 seconds before next deployment..."
        sleep 30
    fi
done

echo "🎉 [DEPLOY] All services deployed successfully!"
```

---

### Task 4.2: Deploy GCHostPay3 (First - Downstream)
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay3-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gchostpay3-10-26
  gcloud run deploy gchostpay3-10-26 --image gcr.io/telepay-459221/gchostpay3-10-26 --region us-central1
  ```

---

### Task 4.3: Deploy GCHostPay1
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCHostPay1-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gchostpay1-10-26
  gcloud run deploy gchostpay1-10-26 --image gcr.io/telepay-459221/gchostpay1-10-26 --region us-central1
  ```

---

### Task 4.4: Deploy GCSplit3
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit3-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcsplit3-10-26
  gcloud run deploy gcsplit3-10-26 --image gcr.io/telepay-459221/gcsplit3-10-26 --region us-central1
  ```

---

### Task 4.5: Deploy GCSplit1
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCSplit1-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcsplit1-10-26
  gcloud run deploy gcsplit1-10-26 --image gcr.io/telepay-459221/gcsplit1-10-26 --region us-central1
  ```

---

### Task 4.6: Deploy GCWebhook1 (Last - Upstream)
- **Status:** PENDING
- **Command:**
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26
  gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook1-10-26
  gcloud run deploy gcwebhook1-10-26 --image gcr.io/telepay-459221/gcwebhook1-10-26 --region us-central1
  ```

---

## Phase 5: Testing & Validation ⏳

### Task 5.1: Verify Database Schema
- **Status:** PENDING
- **Command:**
  ```bash
  PGPASSWORD='Chigdabeast123$' psql \
    -h /cloudsql/telepay-459221:us-central1:telepaypsql \
    -U postgres \
    -d telepaydb \
    -c "SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name IN ('split_payout_request', 'split_payout_hostpay') AND column_name = 'actual_eth_amount';"
  ```

**Success Criteria:**
- Both tables have `actual_eth_amount` column
- Type: `NUMERIC(20,18)`
- Default: `0`

---

### Task 5.2: Test with Small Payment ($5)
- **Status:** PENDING
- **Action:** Create test payment through TelePay bot

**Steps:**
1. Start TelePay bot
2. Create $5 subscription payment
3. Complete NowPayments payment
4. Monitor all services for logs

**Expected Logs:**
```
np-webhook: nowpayments_outcome_amount = 0.00115340416715763
GCWebhook1: actual_eth_amount = 0.00115340416715763
GCSplit1: actual_eth_amount = 0.00115340416715763 (stored in DB)
GCSplit3: actual_eth_amount = 0.00115340416715763
GCHostPay3: Using for payment: 0.00115340416715763 ETH
```

---

### Task 5.3: Verify Database Records
- **Status:** PENDING
- **Query:**
  ```sql
  SELECT
      spr.unique_id,
      spr.actual_eth_amount AS request_actual_eth,
      sph.actual_eth_amount AS hostpay_actual_eth,
      spr.from_amount AS estimated_usdt,
      spr.to_amount AS estimated_eth,
      pcu.nowpayments_outcome_amount AS nowpayments_eth
  FROM split_payout_request spr
  LEFT JOIN split_payout_hostpay sph ON spr.unique_id = sph.unique_id
  LEFT JOIN private_channel_users_database pcu
      ON spr.user_id = pcu.user_id
      AND spr.closed_channel_id = pcu.private_channel_id
  ORDER BY spr.created_at DESC
  LIMIT 5;
  ```

**Success Criteria:**
- `request_actual_eth` = `nowpayments_eth`
- No 3,886x discrepancies
- All actual amounts > 0

---

### Task 5.4: Monitor Service Logs
- **Status:** PENDING
- **Commands:**
  ```bash
  # GCWebhook1
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload=~'ACTUAL ETH'" --limit 20

  # GCSplit1
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsplit1-10-26 AND textPayload=~'ACTUAL ETH'" --limit 20

  # GCHostPay3
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gchostpay3-10-26 AND textPayload=~'ACTUAL ETH'" --limit 20
  ```

**Success Criteria:**
- All services log `ACTUAL ETH` amount
- Amounts consistent across services
- No errors related to missing fields

---

### Task 5.5: Verify ChangeNow Completion
- **Status:** PENDING
- **Action:** Check ChangeNow transaction status

**Expected:**
- Transaction status: `finished`
- No timeout errors
- Client receives expected amount

---

### Task 5.6: Test Backward Compatibility
- **Status:** PENDING
- **Action:** Send old format token to new service

**Method:**
- Keep np-webhook and GCWebhook1 on old revision
- Deploy only downstream services
- Send payment
- Verify graceful degradation

**Expected:**
- Services detect old format
- Fall back to using estimate
- No crashes or errors

---

## Phase 6: Monitoring & Rollback ⏳

### Task 6.1: Create Monitoring Alerts
- **Status:** PENDING
- **Action:** Set up alerts for discrepancies

**Alert Conditions:**
1. `actual_eth_amount` = 0 or NULL (missing data)
2. Discrepancy > 5% between actual and estimate
3. Insufficient wallet balance errors
4. Payment execution failures

---

### Task 6.2: Create Rollback Script
- **Status:** PENDING
- **File:** `/10-26/scripts/rollback_actual_eth_fix.sh`

**Script:**
```bash
#!/bin/bash
# Rollback actual_eth_amount deployment

set -e

echo "⏮️ [ROLLBACK] Starting rollback..."

SERVICES=(
    "gcwebhook1-10-26"
    "gcsplit1-10-26"
    "gcsplit3-10-26"
    "gchostpay1-10-26"
    "gchostpay3-10-26"
)

for service in "${SERVICES[@]}"; do
    echo "⏮️ [ROLLBACK] Rolling back $service..."

    gcloud run services update-traffic "$service" \
        --to-revisions PREVIOUS=100 \
        --region us-central1

    echo "✅ [ROLLBACK] $service rolled back"
done

echo "🎉 [ROLLBACK] Rollback complete"
```

---

### Task 6.3: Monitor for 24 Hours
- **Status:** PENDING
- **Action:** Monitor production for issues

**Checks:**
1. No increase in payment failures
2. Amounts flowing correctly
3. No discrepancy alerts
4. ChangeNow swaps completing
5. Clients receiving payouts

---

## Summary

**Total Tasks:** 45
- **Database:** 4 tasks
- **Token Managers:** 8 tasks
- **Service Code:** 18 tasks
- **Deployment:** 6 tasks
- **Testing:** 6 tasks
- **Monitoring:** 3 tasks

**Critical Path:**
1. Database migration (1-2 hours)
2. Token manager updates (4-6 hours)
3. Service code updates (6-8 hours)
4. Deployment (2-3 hours)
5. Testing (2-4 hours)

**Total Estimated Time:** 2-3 days for full implementation and testing

**Risk Level:** MEDIUM
- Backward compatibility built in
- Staged deployment reduces risk
- Rollback plan ready
- Database changes non-destructive

**Next Step:** Start with Phase 1 (Database Preparation)
