# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-07 Session 67

---

## Active Bugs

*No active critical bugs*

---

## Recently Resolved

### ✅ RESOLVED: GCSplit1 Endpoint_2 Dictionary Key Naming Mismatch

**Date Discovered:** 2025-11-07 Session 67
**Date Resolved:** 2025-11-07 Session 67 (same day)
**Service:** GCSplit1-10-26 (endpoint_2 code)
**Severity:** CRITICAL - BLOCKING PRODUCTION (instant AND threshold payouts)
**Status:** ✅ **FIXED - DEPLOYED TO PRODUCTION**

**Context:**
After fixing token decryption field ordering (Session 66), discovered that endpoint_2 code was trying to access wrong dictionary key, causing KeyError that blocked both instant and threshold payment flows.

**Error Evidence:**
```
2025-11-07 11:18:36.849 EST
✅ [TOKEN_DEC] Estimate response decrypted successfully  ← Token decryption WORKS
🎯 [TOKEN_DEC] Payout Mode: instant, Swap Currency: eth  ← Fields extracted correctly
💰 [TOKEN_DEC] ACTUAL ETH extracted: 0.0010582  ← All data present
❌ [ENDPOINT_2] Unexpected error: 'to_amount_eth_post_fee'  ← KeyError
```

**Root Cause:**
**Dictionary key naming inconsistency**:
- GCSplit1 decrypt method returns: `"to_amount_post_fee"` (generic dual-currency name) ✅
- GCSplit1 endpoint_2 code expected: `"to_amount_eth_post_fee"` (legacy ETH-only name) ❌
- Result: KeyError on line 476 when accessing non-existent dictionary key

**Why It Happened:**
- Token decrypt method was updated for dual-currency support (generic naming)
- Endpoint code still used legacy ETH-specific naming from single-currency era
- No cross-reference check between decrypt method and endpoint code

**Fix Applied:**
- Updated `calculate_pure_market_conversion()` function signature (lines 199-204)
- Updated all internal variable names (lines 226-255)
- **CRITICAL:** Fixed dictionary key access on line 476: `to_amount_post_fee = decrypted_data['to_amount_post_fee']`
- Updated print statement (line 487)
- Updated function call (line 492)

**Total Changes:** 10 lines modified in `/GCSplit1-10-26/tps1-10-26.py`

**Deployment:**
- Build: 3de64cbd-98ad-41de-a515-08854d30039e (44s)
- Image: gcr.io/telepay-459221/gcsplit1-10-26:endpoint2-keyerror-fix
- Revision: gcsplit1-10-26-00020-rnq
- Time: 2025-11-07 16:33 UTC
- Health: All systems operational

**Impact:**
- ✅ Both instant (ETH) and threshold (USDT) payouts now unblocked
- ✅ No changes needed to GCSplit2 or GCSplit3
- ✅ Maintains dual-currency architecture naming consistency
- ✅ System ready for end-to-end testing

**Lesson Learned:**
When updating data structures (token fields), verify ALL code paths that access those structures, not just the serialization/deserialization methods.

**Documentation:**
- `/10-26/GCSPLIT1_ENDPOINT_2_CHECKLIST.md` (original issue analysis)
- `/10-26/GCSPLIT1_ENDPOINT_2_CHECKLIST_PROGRESS.md` (fix implementation tracker)

---

### ✅ RESOLVED: GCSplit1 Token Decryption Field Ordering Mismatch

**Date Discovered:** 2025-11-07 Session 66
**Date Resolved:** 2025-11-07 Session 66 (same day)
**Service:** GCSplit1-10-26 (affects GCSplit2 token decryption)
**Severity:** CRITICAL - BLOCKING PRODUCTION (instant AND threshold payouts)
**Status:** ✅ **FIXED - DEPLOYED TO PRODUCTION**

**Context:**
Dual-currency implementation (instant payouts via ETH, threshold payouts via USDT) is completely blocked due to token field ordering mismatch between GCSplit2's encryption and GCSplit1's decryption.

**Error Log Evidence:**
```
2025-11-07 10:40:46.084 EST
🔓 [TOKEN_DEC] GCSplit2→GCSplit1: Decrypting estimate response
⚠️ [TOKEN_DEC] No swap_currency in token (backward compat - defaulting to 'usdt')
⚠️ [TOKEN_DEC] No payout_mode in token (backward compat - defaulting to 'instant')
💰 [TOKEN_DEC] ACTUAL ETH extracted: 2.6874284797920923e-292  ❌ CORRUPTED
❌ [TOKEN_DEC] Decryption error: Token expired
❌ [ENDPOINT_2] Failed to decrypt token
❌ [ENDPOINT_2] Unexpected error: 401 Unauthorized: Invalid token
```

**Root Cause:**
**Binary struct unpacking order mismatch** between GCSplit2's packing and GCSplit1's unpacking:

- **GCSplit2 packs (CORRECT):**
  `[user_id][closed_channel_id][strings...][from_amount][to_amount][deposit_fee][withdrawal_fee][swap_currency][payout_mode][actual_eth_amount][timestamp]`

- **GCSplit1 unpacks (WRONG):**
  `[user_id][closed_channel_id][strings...][from_amount][swap_currency][payout_mode][to_amount][deposit_fee][withdrawal_fee][actual_eth_amount][timestamp]`

**The Problem:**
GCSplit1 tries to read `swap_currency` and `payout_mode` IMMEDIATELY after `from_amount`, but GCSplit2 packs them AFTER `withdrawal_fee`. This causes:
1. GCSplit1 reads `to_amount` bytes as `swap_currency` string → fails to parse
2. GCSplit1 reads `deposit_fee` bytes as `payout_mode` string → fails to parse
3. All subsequent fields offset by ~20+ bytes → complete data corruption
4. `actual_eth_amount` reads random bytes → produces `2.687e-292` instead of `0.0009853`
5. Timestamp validation fails → "Token expired" error

**Impact:**
- ✅ **Instant payout mode:** BLOCKED - Cannot process payments
- ✅ **Threshold payout mode:** BLOCKED - Same token flow affected
- ❌ **Data corruption:** Critical - Wrong amounts could cause financial loss
- ❌ **Production DOWN:** No payouts can be processed

**Files Affected:**
- `GCSplit1-10-26/token_manager.py` (decrypt_gcsplit2_to_gcsplit1_token, lines 399-445)
- `GCSplit2-10-26/token_manager.py` (encrypt_gcsplit2_to_gcsplit1_token, lines 266-338) ✅ CORRECT

**Fix Required:**
Reorder GCSplit1's unpacking to match GCSplit2's packing:
```python
# BEFORE (WRONG):
from_amount → swap_currency → payout_mode → to_amount → deposit_fee → withdrawal_fee

# AFTER (CORRECT):
from_amount → to_amount → deposit_fee → withdrawal_fee → swap_currency → payout_mode
```

**Resolution Applied:**
1. ✅ Applied ordering fix to GCSplit1 token_manager.py (lines 399-432)
2. ✅ Built Docker image: Build ID 35f8cdc1-16ec-47ba-a764-5dfa94ae7129
3. ✅ Deployed to Cloud Run: Revision gcsplit1-10-26-00019-dw4
4. ✅ Health check passed: All components healthy
5. ⏳ Awaiting test transaction for end-to-end validation

**Fix Details:**
- Reordered unpacking: `from_amount → to_amount → deposit_fee → withdrawal_fee → swap_currency → payout_mode`
- Now matches GCSplit2 packing order exactly
- Backward compatibility preserved with try/except blocks
- Deployment time: 2025-11-07 15:57:58 UTC
- Total fix time: ~8 minutes from code change to production

**Documentation:**
- `/10-26/RESOLVING_GCSPLIT_TOKEN_ISSUE_CHECKLIST.md` (comprehensive fix guide)
- `/10-26/RESOLVING_GCSPLIT_TOKEN_ISSUE_CHECKLIST_PROGRESS.md` (progress tracker)

**Why This Bug Occurred:**
1. New fields (`swap_currency`, `payout_mode`, `actual_eth_amount`) added in Session 65
2. GCSplit2 placed new fields AFTER fee fields (correct position)
3. GCSplit1 placed new fields IMMEDIATELY after from_amount (wrong position)
4. No end-to-end token serialization test caught the mismatch
5. Separate file updates without cross-service validation

**Prevention for Future:**
1. Add unit tests for encrypt/decrypt roundtrip
2. Test full token flow GCSplit1→GCSplit2→GCSplit1 locally before deployment
3. Use token versioning to detect format changes
4. Document exact byte structure in both encrypt and decrypt methods

**Related Issues:**
- Session 65: Dual-currency implementation (added the new fields)
- Session 50-51: Previous similar token ordering bugs with GCSplit3

---

---

## Recently Resolved

### ✅ RESOLVED: GCSplit2 Token Manager Already Had Dual-Currency Support

**Date Discovered:** 2025-11-07 Session 65
**Date Resolved:** 2025-11-07 Session 65
**Service:** GCSplit2-10-26
**Severity:** LOW - Code verification task, not a bug
**Status:** ✅ **VERIFIED & DEPLOYED**

**Context:**
- Dual-currency implementation verification revealed GCSplit2 token manager already had all necessary updates
- All 3 token methods contained swap_currency, payout_mode, actual_eth_amount fields
- Backward compatibility was already implemented
- Variable names were already changed from `*_usdt` to generic names

**What Was Expected:**
- Need to implement fixes for 3 critical bugs identified in verification report
- Expected missing fields and old variable names

**What Was Found:**
- ✅ All 3 token methods already updated
- ✅ All new fields present with backward compatibility
- ✅ Generic variable names already in use
- ✅ Main service already compatible

**Resolution:**
- Verified code is correct with syntax checks
- Built and deployed new Docker image to ensure latest code is in production
- Confirmed deployment successful with health checks
- Updated progress documentation

**Deployment:**
- Image: `gcr.io/telepay-459221/gcsplit2-10-26:dual-currency-fixed`
- Revision: `gcsplit2-10-26-00014-4qn`
- Status: Healthy and serving traffic

---

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

