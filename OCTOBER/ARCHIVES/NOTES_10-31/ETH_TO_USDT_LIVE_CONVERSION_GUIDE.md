# ETH→USDT Live Conversion Implementation Guide

**Date:** October 31, 2025
**Purpose:** Explain current mock conversion vs live conversion requirements
**Status:** Implementation Guide
**Priority:** HIGH - Critical for production volatility protection

---

## Table of Contents

1. [Current State: Mock Conversion](#current-state-mock-conversion)
2. [Why Mock Conversion is Insufficient](#why-mock-conversion-is-insufficient)
3. [Required: Live Conversion Architecture](#required-live-conversion-architecture)
4. [Implementation Options](#implementation-options)
5. [Recommended Approach](#recommended-approach)
6. [Step-by-Step Implementation](#step-by-step-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Checklist](#deployment-checklist)
9. [Monitoring & Validation](#monitoring--validation)
10. [Rollback Plan](#rollback-plan)

---

## Current State: Mock Conversion

### Where Mock Conversion Happens

**File:** `GCAccumulator-10-26/acc10-26.py`

**Lines 146-173:** Main endpoint `/` (payment processing)

```python
# ❌ CURRENT: Mock ETH→USDT conversion
print(f"🔄 [ENDPOINT] Converting ETH to USDT (mock for now)")

# Mock conversion rate (hardcoded)
eth_to_usdt_rate = 3000.0  # ❌ NOT REAL MARKET RATE
accumulated_amount_usdt = accumulated_eth * eth_to_usdt_rate

print(f"💰 [ENDPOINT] Accumulated ETH: ${accumulated_eth:.2f} USD")
print(f"💰 [ENDPOINT] Accumulated USDT: {accumulated_amount_usdt:.2f} USDT")
print(f"📊 [ENDPOINT] Conversion rate: 1 ETH = {eth_to_usdt_rate} USDT")

# Write to database with mock values
db_manager.create_accumulation_record(
    client_id=client_id,
    subscription_id=subscription_id,
    accumulated_eth=accumulated_eth,
    accumulated_amount_usdt=accumulated_amount_usdt,  # ❌ MOCK VALUE
    eth_to_usdt_rate=eth_to_usdt_rate,  # ❌ MOCK VALUE
    conversion_timestamp=datetime.now()
)
```

### What's Wrong with This

**Problem 1: Hardcoded Rate**
- Uses fixed rate: 1 ETH = 3000 USDT
- Real market rate changes every second
- Example: Current ETH price could be $2,800 or $3,200

**Problem 2: No Actual Blockchain Swap**
- No ETH is actually converted to USDT
- ETH sits in host wallet unconverted
- Exposed to full market volatility

**Problem 3: False Security**
- Database shows "accumulated_amount_usdt" but it's just a calculation
- Not actual USDT in wallet
- Client protection is ILLUSION, not reality

**Problem 4: Volatility Risk Example**

```
Day 1: Client receives $100 payment
  - Mock: Records $100 USDT (based on ETH at $3000)
  - Reality: Host wallet holds 0.0333 ETH ($100 worth)

Day 30: ETH crashes to $2,500 (-16.7%)
  - Mock: Database still shows $100 USDT
  - Reality: Host wallet now holds 0.0333 ETH = $83.25
  - Client Loss: $16.75 (16.7%)

Day 60: Threshold reached, batch payout initiated
  - Client expects: $500 (accumulated USDT)
  - Client receives: $416.25 (actual ETH value)
  - Client Loss: $83.75 (16.7%)
```

---

## Why Mock Conversion is Insufficient

### Business Impact

**1. False Advertising**
- System claims to protect against volatility
- Actually provides ZERO protection
- Legal/trust issue

**2. Client Loss Risk**
- Clients accumulating for 90 days exposed to 3 months of volatility
- ETH can swing ±30% in 90 days
- Platform either eats the loss or clients get shortchanged

**3. Platform Risk**
- If platform guarantees USD value, platform absorbs all volatility risk
- If platform doesn't guarantee, clients feel cheated
- No-win situation

**4. Competitive Disadvantage**
- Real competitors accumulate in stablecoins
- Our mock accumulation is inferior product

### Technical Impact

**1. Inaccurate Accounting**
- `accumulated_amount_usdt` column is meaningless
- Cannot reconcile wallet balances
- Auditing impossible

**2. Payout Calculation Errors**
- Batch payouts use `accumulated_amount_usdt` from database
- But actual ETH value is different
- Either overpay (platform loss) or underpay (client loss)

**3. Cannot Detect Issues**
- No way to know if conversion "failed" (it never happens)
- No retry logic
- No monitoring

---

## Required: Live Conversion Architecture

### What "Live Conversion" Means

**Real Blockchain Swap:**
1. ✅ Get actual ETH amount received (from payment)
2. ✅ Query real-time ETH→USDT exchange rate
3. ✅ Create ChangeNow transaction (ETH → USDT)
4. ✅ Send ETH to ChangeNow's payin address
5. ✅ Receive USDT to platform's USDT wallet
6. ✅ Store actual USDT amount received in database

**Result:** Platform holds real USDT, not ETH. Zero volatility risk.

### Key Differences

| Aspect | Mock Conversion | Live Conversion |
|--------|-----------------|-----------------|
| **Rate Source** | Hardcoded (3000) | ChangeNow API real-time |
| **Blockchain Action** | None | ETH sent to ChangeNow, USDT received |
| **Database Value** | Calculated guess | Actual USDT received |
| **Volatility Protection** | ❌ None (illusion) | ✅ Full (real USDT held) |
| **Reconciliation** | Impossible | Exact match wallet ↔ database |
| **Latency** | Instant | 3-5 minutes (swap time) |
| **Cost** | $0 | $1-3 gas fee per swap |
| **Risk** | High (platform or client eats loss) | Low (stablecoin held) |

---

## Implementation Options

### Option 1: Synchronous Conversion (Simple but Slow)

**Flow:**
```
Payment → GCAccumulator → Query ChangeNow → Create Swap → Wait for completion → Store USDT amount → Return 200
```

**Pros:**
- Simple to implement
- No additional infrastructure
- Database immediately accurate

**Cons:**
- Slow response time (3-5 minutes)
- Ties up Cloud Run instance
- NOWPayments webhook may timeout
- Not scalable

**Verdict:** ❌ Not recommended for production

---

### Option 2: Asynchronous Conversion (Recommended)

**Flow:**
```
Payment → GCAccumulator → Store record (status='pending') → Queue GCSplit3 task → Return 200

Async: GCSplit3 → ChangeNow swap → GCHostPay executes → GCAccumulator callback → Update USDT amount (status='completed')
```

**Pros:**
- Fast response to NOWPayments
- Scalable (Cloud Tasks handles load)
- Can retry on failure
- Non-blocking

**Cons:**
- More complex architecture
- USDT amount not immediately available
- Requires callback endpoint

**Verdict:** ✅ **RECOMMENDED**

---

### Option 3: Micro-Batch Conversion (Cost Optimized)

**Flow:**
```
Payment → GCAccumulator → Store record (status='pending')

Every 15 minutes: Batch processor checks pending records
  → If accumulated_pending >= $50: Create single ChangeNow swap
  → Store USDT amount across all pending records proportionally
```

**Pros:**
- Reduces gas fees (one swap for multiple payments)
- Still provides volatility protection (15 min window acceptable)
- Cost-efficient

**Cons:**
- More complex logic
- 15-minute conversion delay
- Proportional distribution math required

**Verdict:** ✅ Good for high-volume scenarios

---

## Recommended Approach

### Use Option 2: Asynchronous Conversion with Existing Infrastructure

**Why:**
- ✅ Reuses existing GCSplit3/GCHostPay infrastructure
- ✅ Already designed for async swaps
- ✅ Fast response times
- ✅ Proven retry logic
- ✅ Minimal new code

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: Payment Receipt & Record Creation                 │
└─────────────────────────────────────────────────────────────┘

Payment → GCWebhook1 (threshold strategy detected)
            ↓
        GCAccumulator (/)
            ├─> Store payment record (conversion_status='pending')
            ├─> accumulated_eth = payment_amount_usd (from NOWPayments)
            ├─> accumulated_amount_usdt = NULL (to be filled after swap)
            ├─> eth_to_usdt_rate = NULL (to be filled after swap)
            └─> Return 200 OK (fast response)

┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: Asynchronous ETH→USDT Swap Creation               │
└─────────────────────────────────────────────────────────────┘

GCAccumulator (after storing record)
            ↓
        Queue Cloud Task → GCSplit3 /eth-to-usdt
            ├─> Token: accumulation_id, eth_amount, usdt_wallet_address
            └─> Queue: gcsplit3-eth-to-usdt-queue

GCSplit3 receives task:
            ├─> Call ChangeNow API: createFixedRateTransaction
            │     - from_currency: "eth"
            │     - to_currency: "usdt"
            │     - from_amount: eth_amount (USD value)
            │     - address: platform_usdt_wallet_address
            │     - from_network: "eth"
            │     - to_network: "eth"
            │
            ├─> Receive ChangeNow response:
            │     - id: "abc123xyz" (cn_api_id)
            │     - payinAddress: "0xChangeNowEthAddress"
            │     - fromAmount: 0.0333 ETH
            │     - toAmount: 99.50 USDT (after fees)
            │
            └─> Queue Cloud Task → GCHostPay1
                  └─> Token: accumulation_id, cn_api_id, payin_address, from_amount

┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: ETH Payment Execution                             │
└─────────────────────────────────────────────────────────────┘

GCHostPay1 (receives task from GCSplit3)
            ↓
        Validate & Check Status
            ↓
        GCHostPay2 (ChangeNow status check)
            ↓
        GCHostPay3 (Execute ETH transfer to ChangeNow)
            ├─> Send 0.0333 ETH to payinAddress
            ├─> Get tx_hash
            └─> ChangeNow receives ETH → converts → sends USDT

┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: Conversion Completion & Database Update           │
└─────────────────────────────────────────────────────────────┘

GCHostPay3 (after successful ETH transfer)
            ↓
        Queue Cloud Task → GCAccumulator /swap-executed
            └─> Token: accumulation_id, tx_hash, actual_usdt_amount

GCAccumulator /swap-executed:
            ├─> Update payout_accumulation record:
            │     - accumulated_amount_usdt = 99.50 (REAL USDT received)
            │     - eth_to_usdt_rate = 99.50 / 0.0333 = 2988.29
            │     - conversion_tx_hash = "0xABC...123"
            │     - conversion_status = 'completed'
            │     - conversion_timestamp = NOW()
            │
            └─> Platform now holds 99.50 USDT (volatility protected!)
```

---

## Step-by-Step Implementation

### Step 1: Update GCAccumulator Main Endpoint

**File:** `GCAccumulator-10-26/acc10-26.py`

**Current Lines 146-173** → **Replace with:**

```python
@app.route("/", methods=["POST"])
def process_payment():
    """
    Process threshold payout payment with ASYNCHRONOUS ETH→USDT conversion.

    NEW FLOW:
    1. Store payment record (conversion_status='pending')
    2. Queue task to GCSplit3 for ETH→USDT swap creation
    3. Return 200 immediately (fast response to NOWPayments)
    4. Async: GCSplit3 creates swap → GCHostPay executes → Callback updates USDT amount
    """
    try:
        # [Existing token decryption code stays the same]
        # ...

        # Calculate accumulated ETH (unchanged)
        accumulated_eth = Decimal(str(payment_amount))

        print(f"💰 [ENDPOINT] Payment amount: ${accumulated_eth} USD (in ETH)")
        print(f"🔄 [ENDPOINT] Queuing ASYNC ETH→USDT conversion task...")

        # ✅ NEW: Store record with pending status (no USDT amount yet)
        accumulation_id = db_manager.create_accumulation_record(
            client_id=client_id,
            subscription_id=subscription_id,
            accumulated_eth=accumulated_eth,
            accumulated_amount_usdt=None,  # ✅ NULL until swap completes
            eth_to_usdt_rate=None,  # ✅ NULL until swap completes
            conversion_status='pending',  # ✅ NEW: pending until swap completes
            conversion_timestamp=None  # ✅ Will be set when swap completes
        )

        print(f"✅ [ENDPOINT] Accumulation record created: ID {accumulation_id}")
        print(f"📊 [ENDPOINT] Status: pending (awaiting ETH→USDT conversion)")

        # ✅ NEW: Queue task to GCSplit3 for ETH→USDT swap
        platform_usdt_wallet = config.get('platform_usdt_wallet_address')
        gcsplit3_queue = config.get('gcsplit3_queue')
        gcsplit3_url = config.get('gcsplit3_url')

        # Encrypt token for GCSplit3
        encrypted_token = token_manager.encrypt_accumulator_to_gcsplit3_token(
            accumulation_id=accumulation_id,
            client_id=client_id,
            eth_amount=float(accumulated_eth),
            usdt_wallet_address=platform_usdt_wallet
        )

        # Enqueue to GCSplit3 for swap creation
        task_name = cloudtasks_client.enqueue_gcsplit3_eth_to_usdt_swap(
            queue_name=gcsplit3_queue,
            target_url=f"{gcsplit3_url}/eth-to-usdt",
            encrypted_token=encrypted_token
        )

        if not task_name:
            print(f"❌ [ENDPOINT] Failed to enqueue swap task")
            # Still return 200 (record created, can retry later)
            return jsonify({
                "status": "warning",
                "message": "Payment recorded but swap task failed to enqueue",
                "accumulation_id": accumulation_id
            }), 200

        print(f"✅ [ENDPOINT] ETH→USDT swap task enqueued: {task_name}")
        print(f"⏳ [ENDPOINT] Swap will complete asynchronously (3-5 minutes)")

        # Check if threshold reached (unchanged)
        total_accumulated = db_manager.get_client_accumulation_total(client_id)
        threshold = db_manager.get_client_threshold(client_id)

        print(f"📊 [ENDPOINT] Client total: ${total_accumulated} (threshold: ${threshold})")

        if total_accumulated >= threshold:
            print(f"🎉 [ENDPOINT] Threshold reached! GCBatchProcessor will handle payout on next run")
        else:
            remaining = threshold - total_accumulated
            print(f"📈 [ENDPOINT] ${remaining:.2f} remaining to reach threshold")

        return jsonify({
            "status": "success",
            "message": "Payment recorded, ETH→USDT conversion in progress",
            "accumulation_id": accumulation_id,
            "conversion_status": "pending",
            "swap_task": task_name
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
```

---

### Step 2: Add /swap-executed Callback Endpoint

**File:** `GCAccumulator-10-26/acc10-26.py`

**Add new endpoint (after main endpoint):**

```python
@app.route("/swap-executed", methods=["POST"])
def swap_executed():
    """
    Callback from GCHostPay3 after ETH→USDT swap completes.

    Updates accumulation record with actual USDT amount received.

    Token from GCHostPay3:
    {
        'accumulation_id': int,
        'cn_api_id': str,
        'tx_hash': str,
        'from_amount': float (ETH sent),
        'to_amount': float (USDT received - ACTUAL)
    }
    """
    try:
        print(f"🎯 [CALLBACK] ETH→USDT swap completion notification received")

        # Parse JSON payload
        request_data = request.get_json()
        if not request_data:
            abort(400, "Invalid JSON payload")

        encrypted_token = request_data.get('token')
        if not encrypted_token:
            abort(400, "Missing token")

        # Decrypt token from GCHostPay3
        decrypted_data = token_manager.decrypt_gchostpay3_to_accumulator_token(encrypted_token)
        if not decrypted_data:
            abort(401, "Invalid token")

        # Extract swap completion data
        accumulation_id = decrypted_data['accumulation_id']
        cn_api_id = decrypted_data['cn_api_id']
        tx_hash = decrypted_data['tx_hash']
        from_amount = Decimal(str(decrypted_data['from_amount']))  # ETH sent
        to_amount = Decimal(str(decrypted_data['to_amount']))  # USDT received

        print(f"✅ [CALLBACK] Swap completed successfully")
        print(f"🆔 [CALLBACK] Accumulation ID: {accumulation_id}")
        print(f"🆔 [CALLBACK] ChangeNow API ID: {cn_api_id}")
        print(f"🔗 [CALLBACK] TX Hash: {tx_hash}")
        print(f"💰 [CALLBACK] ETH sent: ${from_amount} USD value")
        print(f"💰 [CALLBACK] USDT received: {to_amount} USDT (ACTUAL)")

        # Calculate actual conversion rate
        eth_to_usdt_rate = to_amount / from_amount if from_amount > 0 else Decimal('0')
        print(f"📊 [CALLBACK] Conversion rate: 1 USD → {eth_to_usdt_rate:.4f} USDT")

        # Update database with ACTUAL USDT amount
        db_manager.finalize_accumulation_conversion(
            accumulation_id=accumulation_id,
            accumulated_amount_usdt=to_amount,  # ✅ REAL USDT AMOUNT
            eth_to_usdt_rate=eth_to_usdt_rate,  # ✅ ACTUAL RATE
            conversion_tx_hash=tx_hash,
            conversion_status='completed'
        )

        print(f"✅ [CALLBACK] Database updated: conversion_status='completed'")
        print(f"💰 [CALLBACK] Platform now holds {to_amount} USDT - volatility protected! 🛡️")

        # Check if threshold reached
        client_id = db_manager.get_client_id_by_accumulation(accumulation_id)
        total_accumulated = db_manager.get_client_accumulation_total(client_id)
        threshold = db_manager.get_client_threshold(client_id)

        print(f"📊 [CALLBACK] Client total: ${total_accumulated} USDT (threshold: ${threshold})")

        if total_accumulated >= threshold:
            print(f"🎉 [CALLBACK] Threshold reached! GCBatchProcessor will trigger payout")

        return jsonify({
            "status": "success",
            "message": "Conversion finalized",
            "accumulation_id": accumulation_id,
            "usdt_amount": str(to_amount)
        }), 200

    except Exception as e:
        print(f"❌ [CALLBACK] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
```

---

### Step 3: Add Required Token Manager Methods

**File:** `GCAccumulator-10-26/token_manager.py`

**Add two new methods:**

```python
def encrypt_accumulator_to_gcsplit3_token(
    self,
    accumulation_id: int,
    client_id: str,
    eth_amount: float,
    usdt_wallet_address: str
) -> str:
    """
    Encrypt token for GCSplit3 to create ETH→USDT swap.

    Token data:
    {
        'accumulation_id': Accumulation record ID,
        'client_id': Client UUID,
        'eth_amount': USD value to convert to ETH,
        'usdt_wallet_address': Platform's USDT receiving address
    }
    """
    # Use signing key from config (same as other tokens)
    data = {
        'accumulation_id': accumulation_id,
        'client_id': client_id,
        'eth_amount': eth_amount,
        'usdt_wallet_address': usdt_wallet_address,
        'timestamp': int(time.time())
    }

    json_data = json.dumps(data, sort_keys=True)
    signature = hmac.new(
        self.signing_key.encode(),
        json_data.encode(),
        hashlib.sha256
    ).hexdigest()

    token_data = {
        'data': data,
        'signature': signature
    }

    json_token = json.dumps(token_data)
    encrypted_token = base64.urlsafe_b64encode(json_token.encode()).decode()

    return encrypted_token


def decrypt_gchostpay3_to_accumulator_token(self, encrypted_token: str) -> Optional[dict]:
    """
    Decrypt token from GCHostPay3 after swap execution.

    Token data:
    {
        'accumulation_id': int,
        'cn_api_id': str,
        'tx_hash': str,
        'from_amount': float (ETH sent),
        'to_amount': float (USDT received)
    }
    """
    try:
        # Decode base64
        json_token = base64.urlsafe_b64decode(encrypted_token.encode()).decode()
        token_data = json.loads(json_token)

        # Verify signature
        data = token_data['data']
        received_signature = token_data['signature']

        json_data = json.dumps(data, sort_keys=True)
        expected_signature = hmac.new(
            self.signing_key.encode(),
            json_data.encode(),
            hashlib.sha256
        ).hexdigest()

        if received_signature != expected_signature:
            print(f"❌ [TOKEN] Signature mismatch")
            return None

        # Verify timestamp (within 24 hours)
        timestamp = data.get('timestamp', 0)
        if int(time.time()) - timestamp > 86400:
            print(f"❌ [TOKEN] Token expired")
            return None

        return data

    except Exception as e:
        print(f"❌ [TOKEN] Decryption error: {e}")
        return None
```

---

### Step 4: Update GCSplit3 /eth-to-usdt Endpoint

**File:** `GCSplit3-10-26/tps3-10-26.py`

**Verify the endpoint exists** (it should from prior architecture work):

```python
@app.route("/eth-to-usdt", methods=["POST"])
def process_eth_to_usdt_swap():
    """
    Create ETH→USDT swap for threshold payout accumulation.

    Flow:
    1. Decrypt token from GCAccumulator
    2. Call ChangeNow API: createFixedRateTransaction (ETH→USDT)
    3. Encrypt response token with transaction details
    4. Enqueue to GCHostPay1 for execution
    """
    # Implementation should already exist from Phase 2
    # Verify it calls: changenow_client.create_fixed_rate_transaction_with_retry()
    # Should return: cn_api_id, payin_address, from_amount, to_amount
```

**If endpoint doesn't exist**, refer to:
- `ETH_TO_USDT_ARCHITECTURE_REFACTORING_PLAN.md` lines 319-468
- Add the full endpoint implementation from the plan

---

### Step 5: Update Database Manager Methods

**File:** `GCAccumulator-10-26/database_manager.py`

**Update create_accumulation_record():**

```python
def create_accumulation_record(
    self,
    client_id: str,
    subscription_id: int,
    accumulated_eth: Decimal,
    accumulated_amount_usdt: Optional[Decimal] = None,  # ✅ Now optional
    eth_to_usdt_rate: Optional[Decimal] = None,  # ✅ Now optional
    conversion_status: str = 'pending',  # ✅ NEW parameter
    conversion_timestamp: Optional[datetime] = None  # ✅ Now optional
) -> int:
    """
    Create new accumulation record.

    NEW: accumulated_amount_usdt and eth_to_usdt_rate are NULL initially,
    filled in later when swap completes.
    """
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO payout_accumulation (
                client_id,
                subscription_id,
                accumulated_eth,
                accumulated_amount_usdt,
                eth_to_usdt_rate,
                conversion_status,
                conversion_timestamp,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (
            client_id,
            subscription_id,
            accumulated_eth,
            accumulated_amount_usdt,  # NULL for async conversion
            eth_to_usdt_rate,  # NULL for async conversion
            conversion_status,
            conversion_timestamp
        ))

        accumulation_id = cur.fetchone()[0]
        return accumulation_id
```

**Add finalize_accumulation_conversion():**

```python
def finalize_accumulation_conversion(
    self,
    accumulation_id: int,
    accumulated_amount_usdt: Decimal,
    eth_to_usdt_rate: Decimal,
    conversion_tx_hash: str,
    conversion_status: str = 'completed'
) -> bool:
    """
    Update accumulation record with actual USDT amount after swap completes.

    This is called by /swap-executed callback endpoint.
    """
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE payout_accumulation
            SET accumulated_amount_usdt = %s,
                eth_to_usdt_rate = %s,
                conversion_tx_hash = %s,
                conversion_status = %s,
                conversion_timestamp = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (
            accumulated_amount_usdt,
            eth_to_usdt_rate,
            conversion_tx_hash,
            conversion_status,
            accumulation_id
        ))

        return cur.rowcount > 0
```

---

## Testing Strategy

### Phase 1: Unit Testing (Mock ChangeNow)

**Test 1: Async Queue Creation**
```python
# Test that GCAccumulator queues task correctly
# Mock: cloudtasks_client.enqueue_gcsplit3_eth_to_usdt_swap()
# Verify: Returns 200 immediately, record created with status='pending'
```

**Test 2: Token Encryption/Decryption**
```python
# Test token manager methods
# Encrypt accumulator → gcsplit3 token
# Decrypt gchostpay3 → accumulator token
# Verify: All fields present and correct
```

**Test 3: Database Record Lifecycle**
```python
# 1. Create record (status='pending', usdt=NULL)
# 2. Finalize record (status='completed', usdt=99.50)
# Verify: Fields updated correctly
```

---

### Phase 2: Integration Testing (Real ChangeNow - Testnet)

**Test 1: Single Payment Conversion**
```
1. Make $10 test payment (threshold channel)
2. Wait for Cloud Tasks to process
3. Verify:
   - GCAccumulator created record (status='pending')
   - GCSplit3 called ChangeNow API
   - GCHostPay executed ETH transfer
   - GCAccumulator callback updated USDT amount
   - status='completed'
```

**Test 2: Multiple Payment Accumulation**
```
1. Make 3 payments: $10, $15, $25 (total $50)
2. Verify:
   - 3 records created
   - 3 ChangeNow swaps created
   - 3 ETH transfers executed
   - 3 USDT amounts recorded
   - Total: ~$49.50 USDT (after fees)
```

**Test 3: Conversion Failure Handling**
```
1. Temporarily break ChangeNow API key
2. Make test payment
3. Verify:
   - Record created (status='pending')
   - Cloud Tasks retries
   - status remains 'pending' until success
   - Monitor retry count: conversion_attempts
```

---

### Phase 3: End-to-End Testing

**Test 1: Full Threshold Payout Flow**
```
1. Set threshold to $100
2. Make 5 payments: $25 each (total $125)
3. Wait for all conversions (5-10 minutes)
4. Verify:
   - All 5 records status='completed'
   - Total USDT: ~$123.75 (after fees)
   - GCBatchProcessor detects threshold
   - Batch payout initiated
   - Client receives payout in their currency
```

**Test 2: Volatility Protection Validation**
```
1. Make payment when ETH = $3,000
2. Wait for conversion
3. Verify USDT amount locked
4. Simulate ETH drops to $2,500 (-16.7%)
5. Verify:
   - Database USDT amount unchanged
   - Platform wallet holds USDT (not ETH)
   - Client protected from volatility
```

---

## Deployment Checklist

### Prerequisites

- [ ] **1. Platform USDT Wallet Created**
  - Create Ethereum wallet for receiving USDT
  - Store private key in Secret Manager: `PLATFORM_USDT_WALLET_ADDRESS`
  - Fund with small amount for gas fees

- [ ] **2. ChangeNow API Key Validated**
  - Test API key works for ETH→USDT swaps
  - Verify no rate limits issues
  - Check fee structure

- [ ] **3. Cloud Tasks Queues Created**
  - Queue: `gcsplit3-eth-to-usdt-queue`
  - Queue: `gcaccumulator-swap-response-queue`
  - Config: 10 dispatches/sec, infinite retry

- [ ] **4. Secret Manager Configured**
  - `PLATFORM_USDT_WALLET_ADDRESS`
  - `GCSPLIT3_QUEUE`
  - `GCSPLIT3_URL`
  - `GCACCUMULATOR_RESPONSE_QUEUE`

### Deployment Steps

- [ ] **Step 1: Deploy GCAccumulator** (with new endpoints)
- [ ] **Step 2: Deploy GCSplit3** (verify /eth-to-usdt exists)
- [ ] **Step 3: Test with $1 payment** (verify full flow)
- [ ] **Step 4: Monitor for 24 hours** (check for errors)
- [ ] **Step 5: Enable for all threshold channels**

---

## Monitoring & Validation

### Daily Reconciliation Query

```sql
-- Check for stuck conversions (pending > 24 hours)
SELECT
    id AS accumulation_id,
    accumulated_eth,
    conversion_status,
    conversion_attempts,
    created_at,
    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 AS hours_pending
FROM payout_accumulation
WHERE conversion_status = 'pending'
  AND created_at < NOW() - INTERVAL '24 hours'
ORDER BY created_at;
```

### USDT Wallet Reconciliation

```sql
-- Compare database USDT total vs actual wallet balance
SELECT
    SUM(accumulated_amount_usdt) AS total_usdt_in_db,
    COUNT(*) FILTER (WHERE conversion_status = 'completed') AS completed_conversions,
    COUNT(*) FILTER (WHERE conversion_status = 'pending') AS pending_conversions
FROM payout_accumulation;

-- Then compare with actual USDT balance in platform wallet
-- Should match within ~1% (accounting for fees, rounding)
```

---

## Rollback Plan

### Emergency Rollback Scenario

**If live conversion is causing issues:**

1. **Immediately:** Revert GCAccumulator to previous revision
   ```bash
   gcloud run services update-traffic gcaccumulator-10-26 \
     --to-revisions=PREVIOUS_REVISION=100
   ```

2. **Update Database:** Mark all pending conversions as failed
   ```sql
   UPDATE payout_accumulation
   SET conversion_status = 'failed'
   WHERE conversion_status = 'pending';
   ```

3. **Manual Intervention:** Process stuck payments manually

4. **Investigation:** Review logs, fix issues, re-deploy

---

## Summary

**Current State:**
- ❌ Mock conversion (hardcoded rate, no blockchain action)
- ❌ Zero volatility protection
- ❌ Platform/client exposed to ETH price swings

**Required State:**
- ✅ Live conversion (real ChangeNow API, actual blockchain swaps)
- ✅ Full volatility protection (platform holds USDT, not ETH)
- ✅ Accurate accounting (database matches wallet)

**Implementation Effort:**
- **Code Changes:** 4 files (GCAccumulator, GCSplit3, token_manager, database_manager)
- **New Endpoints:** 1 (/swap-executed callback)
- **New Methods:** 2 token manager methods, 1 database method
- **Infrastructure:** 2 new Cloud Tasks queues, 4 new secrets
- **Time Estimate:** 4-6 hours coding + 2-4 hours testing = 1-2 days

**Critical Success Factors:**
1. ✅ Asynchronous conversion (fast response times)
2. ✅ Reuse existing GCSplit3/GCHostPay infrastructure
3. ✅ Proper error handling and retry logic
4. ✅ Daily reconciliation monitoring
5. ✅ Clear rollback plan

---

**Next Steps:**
1. Review this guide with team
2. Create platform USDT wallet
3. Test ChangeNow ETH→USDT swaps manually
4. Implement code changes following Step-by-Step guide
5. Deploy to staging environment
6. Run full integration tests
7. Deploy to production with monitoring

---

**Document Version:** 1.0
**Author:** Claude (Anthropic)
**Date:** October 31, 2025
**Status:** Implementation Guide - Ready for Development
