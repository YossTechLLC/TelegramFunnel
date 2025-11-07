# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-04 Session 60

---

## Active Bugs

(No active critical bugs)

---

## Recently Resolved

### ✅ RESOLVED: GCHostPay3 ETH/USDT Token Type Confusion - Payment Execution Fixed

**Date Discovered:** 2025-11-04 Session 60
**Date Resolved:** 2025-11-04 Session 60
**Service:** GCHostPay3-10-26 (ETH Payment Executor)
**Severity:** CRITICAL - All USDT payments were failing with "insufficient funds"
**Status:** ✅ **RESOLVED** - ERC-20 support deployed to production (revision 00016-l6l)

**Root Cause:**
GCHostPay3 is attempting to send **native ETH** to ChangeNow payin addresses when it should be sending **USDT (ERC-20 tokens)**. The system treats all payment amounts as ETH regardless of the `from_currency` field.

**Evidence:**
```
Error Log:
💰 [ENDPOINT] PAYMENT AMOUNT: 3.11693635 ETH  ❌ Should be 3.11693635 USDT!
💰 [WALLET] Current balance: 0.001161551275950277 ETH
❌ [ENDPOINT] Insufficient funds: need 3.11693635 ETH, have 0.001161551275950277 ETH

ChangeNow API Says:
{
    "fromCurrency": "usdt",        ✅ Should send USDT
    "expectedAmountFrom": 3.116936 ✅ 3.116936 USDT (~$3.12)
}

What System Tries:
- Send 3.116936 ETH (~$7,800) ❌ WRONG CURRENCY!
- Uses native ETH transfer ❌ Should use ERC-20 transfer
```

**Impact:**
- 100% of USDT→TokenX payments failing (USDT→SHIB, USDT→DOGE, etc.)
- All instant payouts broken (NowPayments outputs USDT)
- All batch conversions broken (accumulate USDT, swap to client tokens)
- All threshold payouts broken (accumulated USDT to client wallets)
- Platform cannot fulfill ANY payment obligations

**The Three Problems:**
1. **Currency Confusion**: System ignores `from_currency` field, treats all amounts as ETH
2. **Missing Token Support**: WalletManager only has `send_eth_payment()`, no ERC-20 support
3. **No Contract Integration**: Missing USDT contract address, ERC-20 ABI, transfer logic

**Financial Risk (If Not Caught):**
- System would try to send 3.116936 ETH instead of 3.116936 USDT
- Overpayment: 2,500x intended amount (~$7,800 vs ~$3.12)
- Good news: Wallet has insufficient ETH, so fails safely

**Required Fix:**
1. Add ERC-20 token transfer support to WalletManager
   - Implement `send_erc20_token()` method
   - Add ERC-20 ABI (transfer, balanceOf, decimals)
   - Add token contract addresses (USDT, USDC, DAI)
2. Update GCHostPay3 payment routing
   - Detect currency type from `from_currency` field
   - Route to ETH method for native transfers
   - Route to ERC-20 method for token transfers
3. Fix all logging to show correct currency type
   - Replace hardcoded "ETH" with `{from_currency.upper()}`

**Comprehensive Analysis:**
📄 `/OCTOBER/10-26/GCHOSTPAY3_ETH_USDT_TOKEN_TYPE_CONFUSION_BUG.md`
- Complete root cause analysis
- Detailed implementation checklist (5 phases, 29 tasks)
- Code examples for all changes
- Testing strategy
- Rollback plan

**Affected Services:**
- ✅ GCHostPay1: No changes needed (passes currency correctly)
- ✅ GCHostPay2: No changes needed (status checker only)
- ❌ GCHostPay3: CRITICAL CHANGES REQUIRED
- ✅ GCSplit1: No changes needed (creates correct exchanges)

**Resolution Implemented:**
1. ✅ Added `send_erc20_token()` method to wallet_manager.py
   - Full ERC-20 contract interaction via web3.py
   - Token-specific decimal handling (USDT=6, DAI=18)
   - 100,000 gas limit for contract calls
2. ✅ Added ERC-20 ABI (transfer, balanceOf, decimals)
3. ✅ Added TOKEN_CONFIGS for USDT, USDC, DAI mainnet contracts
4. ✅ Implemented currency type detection in GCHostPay3
5. ✅ Added payment routing logic (ETH vs ERC-20)
6. ✅ Fixed all logging to show dynamic currency
7. ✅ Deployed to production: revision 00016-l6l
8. ✅ Health check confirmed: all components healthy

**Files Modified:**
- `GCHostPay3-10-26/wallet_manager.py` - Added ERC-20 support
- `GCHostPay3-10-26/tph3-10-26.py` - Added currency routing

**Verification:**
- Service URL: https://gchostpay3-10-26-291176869049.us-central1.run.app
- Next USDT payment will validate the fix
- Monitor logs for "Currency type: ERC-20 TOKEN (Tether USD)"

---

### ⚠️ Potential Future Issues - Low Priority

**Other Tables with NUMERIC < 20 (Not Currently Causing Errors):**
1. `payout_batches.payout_amount_crypto`: NUMERIC(18,8) ⚠️
   - May overflow with large SHIB/DOGE batch payouts
   - Monitor for errors in GCBatchProcessor logs

2. `failed_transactions.from_amount`: NUMERIC(18,8) ⚠️
   - May fail to record large failed transactions

3. USD Price Fields: NUMERIC(10,2)
   - `main_clients_database.sub_prices`, `payout_threshold_usd`
   - Unlikely to exceed $99,999,999.99
   - No action needed unless business model changes

**Recommendation:** Monitor logs for similar `numeric field overflow` errors, migrate additional tables if needed.

---

## Recently Fixed

### 2025-11-04 Session 58: GCSplit3 USDT Amount Multiplication - ChangeNOW Receiving Wrong Amounts ✅

**Service:** GCSplit1-10-26 (affects GCSplit3-10-26)
**Severity:** CRITICAL - Payment workflow completely broken
**Status:** FIXED ✅ (Code deployed)

**Root Cause:**
1. **Variable Confusion**: GCSplit1 passes `pure_market_eth_value` to GCSplit3
2. **Semantic Mismatch**: `pure_market_eth_value` contains token quantity (596,726 SHIB), not USDT amount
3. **Wrong Usage**: GCSplit3 uses this as USDT input for ChangeNOW API
4. **Result**: ChangeNOW receives request to swap 596,726 USDT instead of 5.48 USDT
5. **Multiplier Error**: 108,703x amplification (596,726 / 5.48 ≈ 108,703)

**Impact:**
- 100% of USDT→ClientCurrency swaps failing
- All token payouts (SHIB, DOGE, PEPE, BTC, ETH) broken
- Clients never receive tokens
- Platform cannot fulfill payment obligations

**Error Details:**
```
ChangeNOW API Request (WRONG):
{
    "fromCurrency": "usdt",
    "fromAmount": "596726.70043",  // ❌ Should be "5.48949167"
    "toCurrency": "shib"
}

ChangeNOW API Response:
{
    "expectedAmountFrom": 596726.70043,  // ❌ Wrong input
    "expectedAmountTo": 61942343929.62906  // ❌ Wrong output calculation
}
```

**Fix Applied:**
- **File**: GCSplit1-10-26/tps1-10-26.py
- **Line**: 507
- **Change**: `eth_amount=pure_market_eth_value` → `eth_amount=from_amount_usdt`

**Code Fix:**
```python
# BEFORE (WRONG):
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    eth_amount=pure_market_eth_value,  # ❌ Token quantity (596,726)
)

# AFTER (CORRECT):
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    eth_amount=from_amount_usdt,  # ✅ USDT amount (5.48)
)
```

**Deployment:**
- ✅ Code fixed: GCSplit1-10-26/tps1-10-26.py:507
- ✅ Build: gcr.io/telepay-459221/gcsplit1-10-26:latest (Build ID: 6f1af128)
- ✅ Deployed: gcsplit1-10-26 (revision 00017-vcq)
- ✅ Health check: All components healthy
- ✅ Production ready: 2025-11-04

**Prevention Strategy:**
1. Variable naming convention: Use semantic names (usdt_amount vs token_quantity)
2. Architectural pattern: Pass original amounts, not calculated values
3. Code review checklist: Verify data types match parameter semantics
4. Monitoring alert: ChangeNOW `expectedAmountFrom` > $10,000

**Related Documentation:**
- `/GCSPLIT3_USDT_AMOUNT_MULTIPLICATION_BUG_ANALYSIS.md` (comprehensive analysis)
- Session 57: NUMERIC Precision (also involved SHIB token confusion)

**Lessons Learned:**
- Don't reuse calculated values (token quantities) as input amounts (USDT)
- Separate accounting data (pure_market_eth_value) from transaction data (from_amount_usdt)
- Generic variable names (`eth_amount`) can hide actual data types

---

### 2025-11-04 Session 57: Numeric Precision Overflow - GCSplit1 Cannot Store SHIB Transactions ✅

**Service:** GCSplit1-10-26
**Database:** client_table
**Severity:** CRITICAL - Payment workflow completely blocked
**Status:** FIXED ✅ (Database migration applied)

**Symptom:**
GCSplit1 failing to insert split_payout_request records for low-value tokens (SHIB):

```
🔑 [UNIQUE_ID] Generated: ZH4ITXGMFC8XV88Z
✅ [DATABASE] Connection established
❌ [DB_INSERT] Error: {'S': 'ERROR', 'V': 'ERROR', 'C': '22003',
    'M': 'numeric field overflow',
    'D': 'A field with precision 12, scale 8 must round to an absolute value less than 10^4.'}
❌ [ENDPOINT_2] Failed to insert into database
❌ [ENDPOINT_2] Unexpected error: 500 Internal Server Error: Database insertion failed
```

**Root Cause:**
Database schema insufficient precision for large token quantities:

1. **Column Type**: `split_payout_request.to_amount` = `NUMERIC(12,8)`
2. **Maximum Value**: 9,999.99999999 (4 digits before decimal, 8 after)
3. **Actual Value Attempted**: 596,726.7004304786 SHIB (6 digits before decimal)
4. **Result**: PostgreSQL `numeric field overflow` error
5. **Cause**: Low-value tokens (SHIB, DOGE, PEPE) have extremely large quantities

**Data Analysis:**
```
Current Max Values (BEFORE fix):
- split_payout_request.from_amount: 5,335 USDT
- split_payout_request.to_amount: 4.6 (artificially low due to constraint!)
- split_payout_que.to_amount: 1,352,956 SHIB (stored successfully in NUMERIC(24,12))

Token Quantity Examples:
- BTC:  0.001 BTC  → fits in NUMERIC(12,8) ✅
- ETH:  1.234 ETH  → fits in NUMERIC(12,8) ✅
- DOGE: 10,000 DOGE → fits in NUMERIC(12,8) ✅
- SHIB: 596,726 SHIB → OVERFLOW in NUMERIC(12,8) ❌
```

**Impact:**
- **Payment Flow Blocked**: Client deposits succeed but payout workflow stops at GCSplit1
- **Affected Tokens**: SHIB, PEPE, and other micro-value tokens with large quantities
- **User Experience**: Payment appears to succeed but never reaches client wallet
- **No Rollback**: Funds received by platform but cannot be processed

**Fix Applied:**
Database migration to increase NUMERIC precision for all amount columns:

```sql
-- BEFORE → AFTER
split_payout_request.to_amount:      NUMERIC(12,8) → NUMERIC(30,8) ✅
split_payout_request.from_amount:    NUMERIC(10,2) → NUMERIC(20,8) ✅
split_payout_que.from_amount:        NUMERIC(12,8) → NUMERIC(20,8) ✅
split_payout_que.to_amount:          NUMERIC(24,12) → NUMERIC(30,8) ✅
split_payout_hostpay.from_amount:    NUMERIC(12,8) → NUMERIC(20,8) ✅
```

**New Limits:**
- **USDT/ETH amounts** (NUMERIC(20,8)): max **999,999,999,999.99999999**
- **Token quantities** (NUMERIC(30,8)): max **9,999,999,999,999,999,999,999.99999999**

**Verification:**
```sql
-- Test insert that previously failed
INSERT INTO split_payout_request (to_amount) VALUES (596726.7004304786);
-- Result: ✅ SUCCESS
```

**Deployment:**
- ✅ Migration executed on production `client_table` database
- ✅ All existing data migrated without loss
- ✅ Schema verified with test inserts
- ✅ No service downtime required (database-only change)

**Prevention:**
- ✅ Migration script documented: `/scripts/fix_numeric_precision_overflow_v2.sql`
- ✅ Column precision now supports all known cryptocurrency token types
- ⚠️ Future monitoring: Additional tables may need similar fixes if errors occur

### 2025-11-03 Session 56: Token Expiration - GCMicroBatchProcessor Rejecting Valid Callbacks ✅

**Service:** GCMicroBatchProcessor-10-26
**Severity:** CRITICAL - Batch conversions stuck in processing state
**Status:** FIXED ✅ (Deployed revision 00013-5zw)

**Symptom:**
GCMicroBatchProcessor rejecting valid callback tokens from GCHostPay1:

```
🎯 [ENDPOINT] Swap execution callback received
⏰ [ENDPOINT] Timestamp: 1762206594
🔐 [ENDPOINT] Decrypting token from GCHostPay1
❌ [TOKEN_DEC] Decryption error: Token expired
❌ [ENDPOINT] Token decryption failed
❌ [ENDPOINT] Unexpected error: 401 Unauthorized: Invalid token
```

**Root Cause:**
5-minute token expiration window insufficient for asynchronous batch conversion workflow:

1. **ChangeNow Swap Processing**: 5-30 minutes to complete exchange
2. **GCHostPay1 Retry Mechanism**: Up to 3 retries × 5 minutes = 15 minutes
3. **Cloud Tasks Queue Delays**: 30 seconds - 5 minutes
4. **Total Workflow Delay**: 15-20 minutes in normal operation
5. **Current Expiration**: 5 minutes ❌
6. **Result**: Valid callbacks rejected as expired

**Workflow Timeline:**
```
T0: Alchemy webhook → GCHostPay1 receives ETH payment
T0+2s: Query ChangeNow → status='exchanging' (not finished)
T0+2s: Enqueue retry task (delay: 5 minutes)
---
T0+5m: Retry #1 → ChangeNow still 'exchanging'
T0+5m: Enqueue retry task (delay: 5 minutes)
---
T0+10m: Retry #2 → ChangeNow status='finished'!
T0+10m: Create callback token (timestamp = T1)
T0+10m: Enqueue callback to GCMicroBatchProcessor
---
T0+15m: Cloud Tasks delivers callback
T0+15m: Token validation: age = 5 minutes
        ❌ REJECTED: Exceeds 5-minute window
```

**Impact:**
- ✅ ChangeNow swap completes successfully
- ✅ Platform receives USDT in wallet
- ❌ GCMicroBatchProcessor cannot distribute USDT to individual payout_accumulation records
- ❌ Batch conversion stuck in "processing" state indefinitely
- ❌ Users do not receive their proportional USDT share

**Fix Applied:**
Increased token expiration window from 5 minutes to 30 minutes:

**File:** `GCMicroBatchProcessor-10-26/token_manager.py:154-165`

**BEFORE:**
```python
# Validate timestamp (5 minutes = 300 seconds)
current_time = int(time.time())
if not (current_time - 300 <= timestamp <= current_time + 5):
    raise ValueError("Token expired")
```

**AFTER:**
```python
# Validate timestamp (30 minutes = 1800 seconds)
# Extended window to accommodate:
# - ChangeNow retry delays (up to 15 minutes for 3 retries)
# - Cloud Tasks queue delays (2-5 minutes)
# - Safety margin (10 minutes)
current_time = int(time.time())
token_age_seconds = current_time - timestamp
if not (current_time - 1800 <= timestamp <= current_time + 5):
    print(f"❌ [TOKEN_DEC] Token expired: age={token_age_seconds}s ({token_age_seconds/60:.1f}m), max=1800s (30m)")
    raise ValueError("Token expired")

print(f"✅ [TOKEN_DEC] Token age: {token_age_seconds}s ({token_age_seconds/60:.1f}m) - within 30-minute window")
```

**Deployment:**
- ✅ Built: Build ID `a12e0cf9-8b8e-41a0-8014-d582862c6c59`
- ✅ Deployed: Revision `gcmicrobatchprocessor-10-26-00013-5zw` (100% traffic)

**Verification Checklist:**
- [ ] Monitor GCMicroBatchProcessor logs for successful token validation
- [ ] Verify zero "Token expired" errors in production
- [ ] Confirm batch conversions completing end-to-end
- [ ] Verify USDT distribution to payout_accumulation records
- [ ] Check token age logs for actual production delays
- [ ] Trigger test batch conversion

**Lessons Learned:**
1. **Workflow-Driven Validation**: Token expiration windows must account for actual async workflow delays
2. **Production Monitoring**: Token age logging provides visibility into real-world timing
3. **System-Wide Review**: Similar issues may exist in other services with 5-minute windows

**Prevention Measures:**
1. Standardize token expiration windows:
   - Synchronous calls: 5 minutes
   - Async with retries: 30 minutes
   - Long-running workflows: 2 hours
   - Internal retries: 24 hours
2. Add monitoring/alerting for token expiration rates
3. Document expected workflow delays in token manager comments

**Related Issues:**
- Similar 5-minute windows identified in GCHostPay2, GCSplit3, GCAccumulator
- Phase 2: Review these services for potential similar issues

---

### 2025-11-03 Session 55: UUID Truncation Bug - Batch Conversion IDs Truncated to 10 Characters ✅

**Services:** GCHostPay3-10-26, GCHostPay1-10-26
**Severity:** CRITICAL - Batch conversion flow completely broken
**Status:** FIXED ✅ (Phase 1 deployed: GCHostPay3 revision 00015-d79, GCHostPay1 revision 00019-9r5)

**Symptom:**
GCMicroBatchProcessor failing with PostgreSQL UUID validation error:

```
❌ [DATABASE] Query error: {'S': 'ERROR', 'V': 'ERROR', 'C': '22P02',
   'M': 'invalid input syntax for type uuid: "f577abaa-1"'}
❌ [ENDPOINT] No records found for batch f577abaa-1
🆔 [ENDPOINT] Batch Conversion ID: f577abaa-1  ← TRUNCATED (expected 36-char UUID)
🆔 [ENDPOINT] ChangeNow ID: 613c822e844358
💰 [ENDPOINT] Actual USDT received: $1.832669
```

**Root Cause:**
Fixed 16-byte encoding in GCHostPay3 token encryption **systematically truncates UUIDs**:

1. **Full batch_conversion_id**: `"batch_f577abaa-1234-5678-9012-abcdef123456"` (43 characters)
2. **After `.encode('utf-8')[:16]` truncation**: `"batch_f577abaa-1"` (16 bytes)
3. **After padding with nulls**: `"batch_f577abaa-1\x00\x00\x00\x00\x00"` (16 bytes)
4. **After GCHostPay1 decrypt** (rstrip nulls): `"batch_f577abaa-1"` (16 chars)
5. **After `.replace('batch_', '')`**: `"f577abaa-1"` (10 chars)
6. **PostgreSQL UUID validation**: ❌ REJECTS (expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

**Data Flow:**
```
GCMicroBatchProcessor
  └─> Creates batch UUID: "f577abaa-1234-5678-9012-abcdef123456"
  └─> Sends to GCHostPay1 with unique_id: "batch_f577abaa-1234-5678-9012..."
      └─> GCHostPay1 → GCHostPay2 → GCHostPay3 (payout execution)
          └─> GCHostPay3 encrypts response token
              ❌ Line 764: unique_id.encode('utf-8')[:16] TRUNCATES to "batch_f577abaa-1"
          └─> GCHostPay1 receives truncated token
              └─> Extracts: "f577abaa-1" (after removing "batch_" prefix)
          └─> Sends callback to GCMicroBatchProcessor
      └─> GCMicroBatchProcessor tries database query
          ❌ PostgreSQL rejects "f577abaa-1" as invalid UUID
```

**Fix Implementation:**

**GCHostPay3-10-26 Token Manager** (encrypt method):
- ❌ **Before (Line 764):**
  ```python
  unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
  packed_data.extend(unique_id_bytes)
  ```
- ✅ **After:**
  ```python
  packed_data.extend(self._pack_string(unique_id))  # Variable-length encoding
  ```
- ✅ Updated token structure comment (Line 749): "16 bytes: unique_id (fixed)" → "1 byte: unique_id length + variable bytes"

**GCHostPay1-10-26 Token Manager** (decrypt method):
- ❌ **Before (Lines 891-893):**
  ```python
  unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
  offset += 16
  ```
- ✅ **After:**
  ```python
  unique_id, offset = self._unpack_string(raw, offset)  # Variable-length decoding
  ```
- ✅ Updated minimum token size check (Line 886): 52 → 43 bytes (accommodates variable-length unique_id)

**Deployment Details:**
- ✅ GCHostPay3 Build ID: **115e4976-bf8c-402b-b7fc-977086d0e01b**
- ✅ GCHostPay3 Revision: **gchostpay3-10-26-00015-d79** (serving 100% traffic)
- ✅ GCHostPay1 Build ID: **914fd171-5ff0-4e1f-bea0-bcb10e57b796**
- ✅ GCHostPay1 Revision: **gchostpay1-10-26-00019-9r5** (serving 100% traffic)

**Verification Checklist:**
- ⏳ Monitor GCHostPay3 logs: Verify token encryption includes full UUID
- ⏳ Monitor GCHostPay1 logs: Verify decryption shows full UUID (not truncated)
- ⏳ Monitor GCMicroBatchProcessor logs: Verify NO "invalid input syntax for type uuid" errors
- ⏳ Trigger test batch conversion to validate end-to-end flow

**Lessons Learned:**
1. **Fixed-length encoding is dangerous for variable-length data**
   - UUIDs are 36 characters, prefixed UUIDs can be 40+ characters
   - Fixed 16-byte truncation **silently corrupts data**
   - Always use length-prefixed encoding for strings

2. **Systematic code patterns require systematic fixes**
   - Found 20+ instances of same truncation pattern across services
   - One fix reveals broader architectural issue
   - Phase 2 planned to address remaining instances

3. **Token format changes require coordinated deployment**
   - Deploy sender (GCHostPay3) first with new format
   - Deploy receiver (GCHostPay1) second to handle new format
   - Order matters for backward compatibility

**Prevention Measures:**
- Add code review rule: Flag any `.encode('utf-8')[:N]` patterns for review
- Add integration tests with realistic UUID formats (with prefixes)
- Document token encoding standards in architecture docs
- Add UUID format validation at token creation time

**Related Issues:**
- ⚠️ **Phase 2 Pending**: 18 remaining truncation instances across GCHostPay1, GCHostPay2, GCHostPay3, GCSplit1
- ⚠️ **Investigation Needed**: `closed_channel_id` truncation safety assessment

**Documentation:**
- `UUID_TRUNCATION_BUG_ANALYSIS.md` (root cause, scope, fix strategy)
- `UUID_TRUNCATION_FIX_CHECKLIST.md` (3-phase implementation plan)

---

### 2025-11-03 Session 53: GCSplit Hardcoded Currency Bug - USDT→Client Swap Using Wrong Source Currency ✅

**Services:** GCSplit2-10-26, GCSplit3-10-26
**Severity:** CRITICAL - Batch payouts completely broken
**Status:** FIXED ✅ (Deployed GCSplit2 revision 00012-575, GCSplit3 revision 00009-2jt)

**Symptom:**
Second ChangeNow swap in batch payouts using **ETH→ClientCurrency** instead of **USDT→ClientCurrency**:

```json
// Expected flow:
// 1. ETH → USDT (accumulation) ✅ Working
// 2. USDT → ClientCurrency (payout) ❌ Broken

// Actual ChangeNow transaction (WRONG):
{
    "id": "0bd9c09b68484c",
    "status": "waiting",
    "fromCurrency": "eth",        // ❌ Should be "usdt"
    "toCurrency": "shib",         // ✅ Correct
    "expectedAmountFrom": 0.00063941,  // ❌ ETH amount (no ETH available!)
    "payinAddress": "0x349254B0043502EA03cFAD88f708166ea42d3BBD"
}

// Expected ChangeNow transaction (CORRECT):
{
    "fromCurrency": "usdt",  // ✅ USDT from first swap
    "toCurrency": "shib",    // ✅ Client payout currency
    "expectedAmountFrom": 1.832669  // ✅ USDT amount available
}
```

**Root Cause:**
Two hardcoded currency bugs in batch payout flow:

1. **GCSplit2-10-26** (USDT Estimator Service) - Line 131
   ```python
   # BUGGY CODE:
   estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
       from_currency="usdt",
       to_currency="eth",      # ❌ BUG: Hardcoded to "eth"
       from_network="eth",
       to_network="eth",       # ❌ BUG: Hardcoded to "eth"
       from_amount=str(adjusted_amount_usdt),
       flow="standard",
       type_="direct"
   )
   ```
   - Service receives `payout_currency` and `payout_network` from GCSplit1 token
   - But IGNORES these values and uses hardcoded "eth"
   - Result: Estimate calculated for USDT→ETH instead of USDT→ClientCurrency

2. **GCSplit3-10-26** (Swap Creator Service) - Line 130
   ```python
   # BUGGY CODE:
   transaction = changenow_client.create_fixed_rate_transaction_with_retry(
       from_currency="eth",    # ❌ BUG: Hardcoded to "eth"
       to_currency=payout_currency,
       from_amount=eth_amount,  # ❌ Misleading variable name (actually USDT)
       address=wallet_address,
       from_network="eth",
       to_network=payout_network,
       user_id=str(user_id)
   )
   ```
   - Service should create USDT→ClientCurrency swap
   - But hardcoded `from_currency="eth"` creates ETH→ClientCurrency swap
   - Variable `eth_amount` misleading - actually contains USDT amount from first swap

**Impact:**
- ❌ All batch payouts stuck at second swap stage
- ❌ First swap (ETH→USDT) completes successfully, USDT in host wallet
- ❌ Second swap fails: Expects ETH input but only USDT available
- ❌ Clients never receive payouts in their desired currencies (SHIB, XMR, etc.)
- ✅ Instant conversion flow UNAFFECTED (uses different code path with NowPayments ETH)

**Timeline:**
- Unknown origin: Hardcoded values existed since GCSplit2/3 creation
- 2025-11-03 ~18:00 UTC: User reported batch payout failure
- 2025-11-03 18:30 UTC: Root cause analysis completed (Session 53)
- 2025-11-03 19:15 UTC: Fixes deployed to production

**Fix Implemented:**

**GCSplit2-10-26 (tps2-10-26.py):**
```python
# Line 127: Updated log message
print(f"🌐 [ENDPOINT] Calling ChangeNow API for USDT→{payout_currency.upper()} estimate (with retry)")

# Lines 131-132: Use dynamic currency from token
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency=payout_currency,  # ✅ FIXED: Dynamic from token
    from_network="eth",
    to_network=payout_network,    # ✅ FIXED: Dynamic from token
    from_amount=str(adjusted_amount_usdt),
    flow="standard",
    type_="direct"
)

# Line 154: Updated log message
print(f"💰 [ENDPOINT] To: {to_amount} {payout_currency.upper()} (post-fee)")
```

**GCSplit3-10-26 (tps3-10-26.py):**
```python
# Line 112: Renamed variable for clarity
usdt_amount = decrypted_data['eth_amount']  # ✅ RENAMED (field name unchanged for compatibility)

# Line 118: Updated log message
print(f"💰 [ENDPOINT] USDT Amount: {usdt_amount}")

# Line 127: Updated log message
print(f"🌐 [ENDPOINT] Creating ChangeNow transaction USDT→{payout_currency.upper()} (with retry)")

# Line 130: Fixed source currency
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="usdt",     # ✅ FIXED: Correct source currency
    to_currency=payout_currency,
    from_amount=usdt_amount,  # ✅ FIXED: Renamed variable
    address=wallet_address,
    from_network="eth",
    to_network=payout_network,
    user_id=str(user_id)
)

# Line 162: Updated log message
print(f"💰 [ENDPOINT] From: {api_from_amount} USDT")
```

**Code Changes Summary:**
- **GCSplit2**: 3 edits (lines 127, 131-132, 154)
- **GCSplit3**: 4 edits (lines 112, 118, 127, 130, 132, 162)
- **Total**: 2 services, 7 line changes

**Deployment:**
- ✅ GCSplit2 Build ID: a23bc7d5-b8c5-4aaf-b83a-641ee7d74daf
- ✅ GCSplit2 Deployed: Revision **gcsplit2-10-26-00012-575** (100% traffic)
- ✅ GCSplit3 Build ID: a23bc7d5-b8c5-4aaf-b83a-641ee7d74daf
- ✅ GCSplit3 Deployed: Revision **gcsplit3-10-26-00009-2jt** (100% traffic)
- ✅ Health checks: All components healthy
- ⏳ End-to-end validation: Pending test batch payout

**Verification Required:**
- [ ] Monitor GCSplit2 logs: Should show `To: X.XX SHIB (post-fee)` not ETH
- [ ] Monitor GCSplit3 logs: Should show `From: X.XX USDT` not ETH
- [ ] Check ChangeNow transaction: Should have `fromCurrency: "usdt"`
- [ ] Verify client receives payout in correct currency and amount

**Cross-Service Verification:**
- ✅ GCSplit1: No changes needed (already passes correct parameters)
- ✅ Instant conversion flow: Unaffected (different code path)
- ✅ Threshold accumulation: Uses separate `/eth-to-usdt` endpoint (correct)

**Lessons Learned:**
1. **Never hardcode dynamic parameters** - Always use values from tokens/config
2. **Variable naming matters** - `eth_amount` containing USDT caused confusion
3. **Test all flows end-to-end** - Batch payout flow wasn't fully tested before production
4. **Service naming can mislead** - "USDT→ETH Estimator" should be "USDT→Currency Estimator"
5. **Verify API calls match intent** - Currency parameters must align with system architecture

**Prevention:**
- Add integration tests for complete batch payout flow (ETH→USDT→ClientCurrency)
- Code review checklist: Flag all hardcoded currency/network values
- Add logging to show actual API parameters before calling ChangeNow
- Rename misleading variables (`eth_amount` → `usdt_amount`)
- Consider renaming GCSplit2 service description for accuracy

**Related Documentation:**
- Analysis: `/10-26/GCSPLIT_USDT_TO_CLIENT_CURRENCY_BUG_ANALYSIS.md`
- Checklist: `/10-26/GCSPLIT_USDT_CLIENT_CURRENCY_FIX_CHECKLIST.md`
- Decision: DECISIONS.md Session 53 (Maintain two-swap architecture)

---

### 2025-11-03 Session 54: GCHostPay1 enqueue_task() Method Not Found ✅

**Services:** GCHostPay1-10-26
**Severity:** CRITICAL - Batch conversion callbacks completely broken
**Status:** FIXED ✅ (Deployed revision 00018-8s7 at 21:22 UTC)

**Symptom:**
```python
✅ [BATCH_CALLBACK] Response token encrypted
📡 [BATCH_CALLBACK] Enqueueing callback to: https://gcmicrobatchprocessor-10-26-pjxwjsdktq-uc.a.run.app/swap-executed
❌ [BATCH_CALLBACK] Unexpected error: 'CloudTasksClient' object has no attribute 'enqueue_task'
❌ [ENDPOINT_4] Failed to send batch callback
```

**Root Cause:**
1. Batch callback code (tphp1-10-26.py line 160) called non-existent method `cloudtasks_client.enqueue_task()`
2. CloudTasksClient class only has `create_task()` method (base method)
3. Also had wrong parameter name: `url=` instead of `target_url=`
4. Old documentation from pre-Session 52 referenced `enqueue_task()` which was never implemented
5. CloudTasksClient was refactored to use specialized methods, but batch callback code wasn't updated

**Impact:**
- ❌ All batch conversion callbacks blocked
- ❌ GCMicroBatchProcessor never receives swap completion notifications
- ❌ Batch conversions cannot complete end-to-end
- ❌ ETH paid but USDT not distributed

**Timeline:**
- Session 52 (19:00-19:55 UTC): Implemented batch callback logic using old `enqueue_task()` reference
- Session 54 (21:15 UTC): Discovered error in production logs (ENDPOINT_4 execution)
- Session 54 (21:22 UTC): Fixed and deployed

**Fix:**
- ✅ Replaced `enqueue_task()` → `create_task()` (tphp1-10-26.py line 160)
- ✅ Replaced `url=` → `target_url=` parameter
- ✅ Updated return value handling (task_name → boolean conversion)
- ✅ Added task name logging for debugging (line 168)
- ✅ Rebuilt Docker image: 5f962fce-deed-4df9-b63a-f7e85968682e
- ✅ Deployed revision: gchostpay1-10-26-00018-8s7

**Verification:**
- ✅ Build successful
- ✅ Deployment successful
- ✅ Health check passing
- ✅ Config loading verified (MicroBatch URL and Queue)
- ✅ No more `enqueue_task` calls in codebase
- ⏳ End-to-end batch conversion test pending

**Lessons Learned:**
1. **Test all code paths** - ENDPOINT_4 retry callback path wasn't tested in Session 52
2. **Verify method names** - Python's dynamic typing doesn't catch method name errors until runtime
3. **Update all references** - When refactoring CloudTasksClient, all calling code should be updated
4. **Document cleanup** - Old checklists referenced non-existent methods

**Prevention:**
- Add integration tests for all Cloud Tasks enqueue paths
- Use type hints and mypy for static type checking
- Document all CloudTasksClient methods clearly
- Remove outdated documentation references

---

### 2025-11-03 Session 53: GCHostPay1 Retry Queue Config Missing ✅

**Services:** GCHostPay1-10-26
**Severity:** CRITICAL - Phase 2 retry logic completely broken
**Status:** FIXED ✅ (Deployed revision 00017-rdp at 20:44:26 UTC)

**Symptom:**
```python
🔄 [RETRY_ENQUEUE] Scheduling retry #1 in 300s
🆔 [RETRY_ENQUEUE] Unique ID: batch_bfd941e7-b
🆔 [RETRY_ENQUEUE] CN API ID: 90f68b408285a6
❌ [RETRY_ENQUEUE] GCHostPay1 response queue config missing
⚠️ [ENDPOINT_3] No callback sent (context=batch, actual_usdt_received=None)
```

**Root Cause:**
1. Session 52 Phase 2 implemented retry logic with `_enqueue_delayed_callback_check()` helper (tphp1-10-26.py lines 220-225)
2. Helper function requires `config.get('gchostpay1_response_queue')` and `config.get('gchostpay1_url')`
3. **config_manager.py did NOT load these secrets** (oversight in Phase 2 implementation)
4. Secrets exist in Secret Manager and queue exists, but weren't being loaded
5. Retry task enqueue fails immediately with "config missing" error

**Impact:**
- ❌ Phase 2 retry logic non-functional
- ❌ All batch conversions stuck when ChangeNow swap not finished
- ❌ No delayed callback scheduled
- ❌ GCMicroBatchProcessor never receives actual_usdt_received

**Timeline:**
- Session 52 (19:00-19:55 UTC): Implemented Phase 2 retry logic, forgot to update config_manager.py
- Session 53 (20:21 EST): Discovered error in production logs
- Session 53 (20:44 UTC): Fixed and deployed

**Fix:**
- ✅ Updated config_manager.py to fetch GCHOSTPAY1_URL (lines 101-104)
- ✅ Updated config_manager.py to fetch GCHOSTPAY1_RESPONSE_QUEUE (lines 106-109)
- ✅ Added both to config dictionary (lines 166-167)
- ✅ Added both to config status logging (lines 189-190)
- ✅ Rebuilt Docker image and deployed revision gchostpay1-10-26-00017-rdp

**Verification:**
```
✅ [CONFIG] Successfully loaded GCHostPay1 response queue name (for retry callbacks)
   GCHostPay1 URL: ✅
   GCHostPay1 Response Queue: ✅
```

**Files Fixed:**
- `/10-26/GCHostPay1-10-26/config_manager.py` (added missing config loading)

**Cross-Service Check:**
- ✅ GCHostPay3 already loads its own URL/retry queue correctly
- ✅ GCHostPay2 doesn't need self-callback config (no retry logic)

**Lessons Learned:**
1. When adding self-callback/retry logic, update config_manager.py immediately
2. Verify config loading in deployment logs before marking feature complete
3. Add integration test to verify config completeness

**Prevention:**
- Created checklist pattern for future self-callback features
- Documented in CONFIG_LOADING_VERIFICATION_SUMMARY.md

---

### 2025-11-03 Session 52: GCHostPay1 decimal.ConversionSyntax on Null ChangeNow Amounts ✅

**Services:** GCHostPay1-10-26
**Severity:** HIGH - Breaks micro-batch conversion feedback loop
**Status:** FIXED ✅ (Phase 1 - Deployed revision 00015-kgl at 19:12:12 UTC)

**Symptom:**
```python
❌ [CHANGENOW_STATUS] Unexpected error: [<class 'decimal.ConversionSyntax'>]
❌ [ENDPOINT_3] ChangeNow query error: [<class 'decimal.ConversionSyntax'>]
⚠️ [ENDPOINT_3] No callback sent (context=batch, actual_usdt_received=None)
```

**Root Cause:**
1. GCHostPay3 completes ETH payment and sends callback to GCHostPay1
2. GCHostPay1 queries ChangeNow API immediately (TOO EARLY)
3. ChangeNow swap still in progress (takes 5-10 minutes)
4. ChangeNow returns `amountTo=null` (not available yet)
5. Code attempts: `Decimal(str(None))` → `Decimal("None")` → ❌ ConversionSyntax

**Impact:**
- ❌ Batch conversion callbacks fail
- ❌ GCMicroBatchProcessor never notified
- ❌ Users don't receive payouts
- ⚠️ ETH payments succeed but feedback loop breaks

**Fix (Phase 1 - Defensive):**
- ✅ Added `_safe_decimal()` helper to handle None/null/empty values
- ✅ Returns `Decimal('0')` for invalid values instead of crashing
- ✅ Added warning logs when amounts are zero/unavailable
- ✅ Updated ENDPOINT_3 to detect in-progress swaps

**Files Fixed:**
- `/10-26/GCHostPay1-10-26/changenow_client.py` (added safe_decimal)
- `/10-26/GCHostPay1-10-26/tphp1-10-26.py` (enhanced query logic)

**Deployed:** Revision gchostpay1-10-26-00015-kgl

**Status:** ✅ Phase 1 complete (crash prevention)
**Next:** ⏳ Phase 2 needed (retry logic to query when swap finishes)

**Lessons Learned:**
1. Never trust external API fields to exist
2. Always validate before type conversion
3. Handle asynchronous processes with appropriate timing
4. Defensive programming > fail-fast for critical workflows
5. Add clear warning logs when data is incomplete

---

### 2025-11-03 Session 51: GCSplit1 Token Decryption Order Mismatch (Follow-up Fix) ✅

**Services:** GCSplit1-10-26
**Severity:** CRITICAL - Session 50 fix incomplete, token decryption still failing
**Status:** FIXED ✅ (Deployed GCSplit1 revision 00016-dnm at 18:57:36 UTC)

**Description:**
```python
❌ [TOKEN_DEC] Decryption error: Token expired
💰 [TOKEN_DEC] ACTUAL ETH extracted: 8.706401155e-315  # Corrupted value
ValueError: Token expired (timestamp=0)
```

**Root Cause:**
- **Session 50 Fixed**: GCSplit1 ENCRYPTION method to include `actual_eth_amount` field
- **Session 51 Found**: GCSplit1 DECRYPTION method still unpacking in WRONG order
- **Binary Unpacking Order Mismatch**:
  - GCSplit3 packs: `[...fields][actual_eth:8][timestamp:4][signature:16]`
  - GCSplit1 decryption was reading: `[...fields][timestamp:4][actual_eth:8][signature:16]`
  - GCSplit1 read 8 bytes of `actual_eth_amount` (0.0 = `0x0000000000000000`) but interpreted first 4 bytes as timestamp
- **Result**: Timestamp = 0 (Unix epoch 1970-01-01) → validation failed
- **Corrupted actual_eth_amount**: Reading timestamp bytes + signature bytes as double → `8.706401155e-315`

**User Report:**
User saw errors at 13:45:12 EST (18:45:12 UTC) and suspected TTL window was only 1 minute. Investigation revealed:
- **User's assumption**: TTL window too tight (1 minute)
- **Actual TTL**: 24 hours backward, 5 minutes forward (already generous)
- **Real problem**: Binary structure unpacking order mismatch

**Impact:**
- Continued 100% token decryption failure even after Session 50 fix
- Cloud Tasks retrying same token every ~60 seconds from 18:40:12 to 18:49:13 UTC
- Old failing tasks eventually exhausted retry limit and were dropped from queue
- No new payments could complete GCSplit3→GCSplit1 handoff

**Fix Implemented:**
```python
# GCSplit1-10-26/token_manager.py - decrypt_gcsplit3_to_gcsplit1_token()

# OLD ORDER (WRONG):
timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]  # ❌ Line 649
offset += 4
actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]  # ❌ Line 656
offset += 8

# NEW ORDER (CORRECT):
actual_eth_amount = 0.0
if offset + 8 + 4 <= len(payload):  # ✅ Line 651: Defensive check
    try:
        actual_eth_amount = struct.unpack(">d", payload[offset:offset + 8])[0]  # ✅ Line 653: Read FIRST
        offset += 8
    except Exception as e:
        print(f"⚠️ [TOKEN_DEC] Error extracting actual_eth_amount: {e}")

timestamp = struct.unpack(">I", payload[offset:offset + 4])[0]  # ✅ Line 661: Read SECOND
offset += 4
```

**Code Changes:**
- File: `/10-26/GCSplit1-10-26/token_manager.py`
- Lines modified: 649-662
- Swapped unpacking order to match GCSplit3's packing order
- Added defensive validation for buffer size
- Enhanced error handling for extraction failures

**Deployment:**
- Built: `gcr.io/telepay-459221/gcsplit1-10-26:latest` (SHA256: 318b0ca50c9899a4...)
- Deployed: Cloud Run revision `gcsplit1-10-26-00016-dnm`
- Time: 2025-11-03 18:57:36 UTC (13:57:36 EST)
- Status: Healthy, serving 100% traffic

**Validation:**
- ✅ New revision deployed successfully
- ✅ No errors in new revision logs
- ✅ Old failing tasks cleared from queue
- ⏳ Awaiting new payment transaction to validate end-to-end flow

**Lessons Learned:**
1. **Complete the picture**: Fixing encryption without fixing decryption leaves the bug half-resolved
2. **Binary structure discipline**: Pack and unpack order MUST match exactly
3. **Don't trust user assumptions**: User thought TTL was 1 minute; actual TTL was 24 hours
4. **Investigate corrupted values**: The `8.706401155e-315` value was a key clue pointing to wrong-offset reads
5. **Both sides matter**: Token encryption AND decryption must be validated together

**Prevention:**
- Add integration tests that encrypt with one service and decrypt with another
- Document binary structure format in both encryption and decryption docstrings
- Add assertions to verify unpacking order matches packing order
- Log extracted values at debug level to catch corruption early

---

### 2025-11-03 Session 50: GCSplit3→GCSplit1 Token Version Mismatch Causing "Token Expired" Error ✅

**Services:** GCSplit3-10-26, GCSplit1-10-26
**Severity:** CRITICAL - 100% token decryption failure, payment flow completely blocked
**Status:** FIXED ✅ (Deployed GCSplit1 revision 00015-jpz)

**Description:**
```python
❌ [TOKEN_DEC] Decryption error: Token expired
ValueError: Token expired (timestamp=0)
File "/app/token_manager.py", line 658
```

**Root Cause:**
- **Version Mismatch**: GCSplit3 TokenManager included `actual_eth_amount` field (8 bytes), GCSplit1 didn't
- **Binary Structure Misalignment**:
  - GCSplit3 packed: `[...fields][actual_eth:8][timestamp:4][signature:16]`
  - GCSplit1 expected: `[...fields][timestamp:4][signature:16]`
  - GCSplit1 read the first 4 bytes of `actual_eth_amount` (0.0 = `0x00000000`) as the timestamp
- **Validation Failure**: Timestamp of 0 (Unix epoch 1970-01-01) failed validation check `now - 86400 <= timestamp <= now + 300`
- **Corrupted Reading**: When GCSplit1 tried to extract actual_eth_amount for backward compat, it read from wrong position (timestamp + signature bytes) as float, producing corrupted value `8.70638631e-315`

**Impact:**
- GCSplit3→GCSplit1 handoff: 100% failure rate
- Payment confirmations never reached GCHostPay1
- All payments stuck at ETH→Client swap response stage
- Cloud Tasks retrying failed tasks every ~60 seconds for 24 hours

**Fix Implemented:**
```python
# GCSplit1-10-26/token_manager.py
def encrypt_gcsplit3_to_gcsplit1_token(
    self,
    # ... existing params ...
    type_: str,
    actual_eth_amount: float = 0.0  # ✅ ADDED
) -> Optional[str]:
