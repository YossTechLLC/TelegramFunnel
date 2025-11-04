# Architectural Decisions - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-04 Session 61

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Table of Contents
1. [Service Architecture](#service-architecture)
2. [Cloud Infrastructure](#cloud-infrastructure)
3. [Data Flow & Orchestration](#data-flow--orchestration)
4. [Security & Authentication](#security--authentication)
5. [Database Design](#database-design)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [User Interface](#user-interface)

---

## Recent Decisions

### 2025-11-04 Session 61: Remove Channel Message Auto-Deletion - Prioritize Payment Transparency ✅

**Decision:** Remove 60-second auto-deletion of payment prompt messages from open channels to preserve payment transparency and user trust.

**Status:** ✅ **CODE COMPLETE** - Pending deployment

**Context:**
- Original design: Auto-delete channel messages after 60 seconds to keep channels "clean"
- Implementation: `asyncio.get_event_loop().call_later(60, delete_message)` in broadcast and message utilities
- User experience problem: Payment prompts disappear mid-transaction
- Impact: User panic, distrust, support burden, poor UX

**Problem:**
```
User Flow (WITH AUTO-DELETE):
T=0s   → User sees subscription tier buttons in channel
T=5s   → User clicks tier, receives payment prompt
T=15s  → User sends crypto payment
T=60s  → ⚠️ MESSAGE DISAPPEARS FROM CHANNEL
T=120s → User panics: "Was this a scam?"

Result: Lost trust, confused users, support burden
```

**Architecture Decision:**

**1. Remove Auto-Deletion Entirely**
- Delete `call_later(60, delete_message)` from `broadcast_manager.py`
- Delete `call_later(60, delete_message)` from `message_utils.py`
- Allow messages to persist permanently in channels
- Prioritize user trust over channel aesthetics

**2. Rationale: Trust > Cleanliness**
```
Professional Payment System Standards:
✅ Payment evidence must be preserved
✅ Users need reference to payment request
✅ Transparency builds trust
❌ Deleting payment records = red flag
```

**3. Trade-off Analysis**
```
Benefits:
✅ Payment transparency maintained
✅ User trust improved
✅ Reduced support burden
✅ Aligns with payment industry standards
✅ No breaking changes

Trade-offs:
⚠️ Channels may accumulate old prompts
⚠️ Less "clean" aesthetic

Mitigation (Future):
→ Edit-in-place status updates ("✅ Payment Received")
→ Periodic admin cleanup tools
→ Extended timers (24h instead of 60s)
```

**4. Files Modified**
```python
# TelePay10-26/broadcast_manager.py
# REMOVED lines 101-110:
# - msg_id extraction
# - del_url construction
# - asyncio.call_later(60, delete)

# TelePay10-26/message_utils.py
# REMOVED lines 23-32:
# - msg_id extraction
# - del_url construction
# - asyncio.call_later(60, delete)
# UPDATED docstring: removed "with auto-deletion after 60 seconds"
```

**5. User Experience Improvement**
```
User Flow (WITHOUT AUTO-DELETE):
T=0s   → User sees subscription tier buttons in channel
T=5s   → User clicks tier, receives payment prompt
T=15s  → User sends crypto payment
T=60s  → ✅ MESSAGE STILL VISIBLE (user confident)
T=120s → User receives invite, payment evidence intact

Result: Trust maintained, professional UX, reduced support burden
```

**Alternative Solutions Considered:**

1. **Edit-in-place updates (DEFERRED)**
   - Update message to show "✅ Payment Received" when complete
   - Requires message_id tracking in database
   - More complex implementation
   - Future enhancement candidate

2. **Extended timer (REJECTED)**
   - Increase from 60s to 10+ minutes
   - Band-aid solution, doesn't solve core problem
   - Messages still disappear eventually

3. **Remove deletion (IMPLEMENTED)**
   - Simplest solution
   - Highest trust impact
   - Easiest to deploy

**Impact:**
- ✅ Payment transparency restored
- ✅ User trust and confidence improved
- ✅ Support burden reduced
- ✅ Aligns with professional payment system standards
- ✅ Fully backward compatible
- ✅ No changes to private messages (already permanent)
- ✅ No changes to webhook contracts or database

**Documentation:**
- Created `CHANNEL_MESSAGE_AUTO_DELETE_UX_BUG_FIX.md`
- Comprehensive root cause analysis
- User experience comparison (before/after)
- Alternative solutions analysis
- Future enhancement roadmap

**Deployment:**
- Code changes: COMPLETE ✅
- Build TelePay10-26: PENDING ⏳
- Deploy to Cloud Run: PENDING ⏳
- Test verification: PENDING ⏳

**Future Enhancements:**
- Phase 2: Edit-in-place payment status updates
- Phase 3: Admin cleanup tools for old messages
- Phase 4: Conditional deletion (only after payment confirmed)

---

### 2025-11-04 Session 60: Multi-Currency Payment Support - ERC-20 Token Architecture ✅ DEPLOYED

**Decision:** Extend GCHostPay3 WalletManager to support ERC-20 token transfers (USDT, USDC, DAI) in addition to native ETH.

**Status:** ✅ **IMPLEMENTED AND DEPLOYED** - GCHostPay3 revision 00016-l6l now live with full ERC-20 support

**Context:**
- Platform receives payments in various cryptocurrencies via NowPayments
- NowPayments converts all incoming payments to **USDT** (ERC-20 token)
- ChangeNow requires **USDT** for secondary swaps (USDT→SHIB, USDT→DOGE, etc.)
- Current system only supports native ETH transfers
- **Critical bug discovered**: System attempts to send native ETH instead of USDT tokens
- All USDT payments fail with "insufficient funds" error

**Problem:**
```
Current Flow (BROKEN):
User Payment (BTC/ETH/LTC/etc) → NowPayments → USDT (ERC-20)
    ↓
Platform Wallet receives USDT ✅
    ↓
GCHostPay3 tries to send ETH ❌ WRONG!
    ↓
ChangeNow expects USDT ❌ Never received
```

**Architecture Decision:**

**1. Currency Type Detection**
- Parse `from_currency` field from payment token
- Route to appropriate transfer method based on currency type
- Support both native (ETH) and ERC-20 (USDT, USDC, DAI) transfers

**2. WalletManager Multi-Currency Support**
```python
# Native ETH transfers (existing)
def send_eth_payment(to_address, amount, unique_id) -> tx_result

# NEW: ERC-20 token transfers
def send_erc20_token(
    token_contract_address,  # e.g., USDT: 0xdac17f958d2ee523a2206206994597c13d831ec7
    to_address,
    amount,
    token_decimals,          # USDT=6, USDC=6, DAI=18
    unique_id
) -> tx_result

# NEW: ERC-20 balance checking
def get_erc20_balance(token_contract_address, token_decimals) -> balance
```

**3. Token Configuration**
```python
TOKEN_CONFIGS = {
    'usdt': {
        'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
        'decimals': 6,
        'name': 'Tether USD'
    },
    'usdc': {
        'address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
        'decimals': 6,
        'name': 'USD Coin'
    },
    'dai': {
        'address': '0x6b175474e89094c44da98b954eedeac495271d0f',
        'decimals': 18,
        'name': 'Dai Stablecoin'
    }
}
```

**4. Payment Routing Logic**
```python
# GCHostPay3 payment execution
if from_currency == 'eth':
    # Native ETH transfer (existing path)
    tx_result = wallet_manager.send_eth_payment(...)
elif from_currency in ['usdt', 'usdc', 'dai']:
    # ERC-20 token transfer (NEW path)
    token_config = TOKEN_CONFIGS[from_currency]
    tx_result = wallet_manager.send_erc20_token(
        token_contract_address=token_config['address'],
        token_decimals=token_config['decimals'],
        ...
    )
else:
    raise ValueError(f"Unsupported currency: {from_currency}")
```

**Key Technical Differences:**

| Aspect | Native ETH | ERC-20 Tokens |
|--------|-----------|---------------|
| Transfer Method | `eth.sendTransaction()` | Contract `.transfer()` call |
| Transaction Type | Value transfer | Contract function call |
| Gas Limit | 21,000 | 60,000-100,000 |
| Amount Field | `value` (Wei) | Function parameter (token units) |
| Decimals | 18 | Token-specific (USDT=6) |
| Contract Required | No | Yes (token contract address) |
| Balance Check | `eth.getBalance()` | Contract `.balanceOf()` |

**Implementation Phases:**
1. **Phase 1**: Add ERC-20 ABI and token configs to WalletManager
2. **Phase 2**: Implement `send_erc20_token()` and `get_erc20_balance()` methods
3. **Phase 3**: Update GCHostPay3 to route based on currency type
4. **Phase 4**: Fix logging to show correct currency labels
5. **Phase 5**: Test on testnet, deploy to production with gradual rollout

**Benefits:**
- ✅ **Multi-Currency Support**: Handle both ETH and ERC-20 tokens seamlessly
- ✅ **Correct Payment Routing**: Send USDT tokens instead of ETH when required
- ✅ **Financial Safety**: Prevent massive overpayments (3.11 USDT vs 3.11 ETH = $3 vs $7,800)
- ✅ **Extensible Architecture**: Easy to add more tokens (WBTC, LINK, etc.)
- ✅ **Production Ready**: Unblocks entire payment flow (instant, batch, threshold)

**Risks & Mitigations:**
- **Risk**: Higher gas costs for ERC-20 transfers (60k vs 21k gas)
  - *Mitigation*: Monitor gas prices, implement EIP-1559 optimization
- **Risk**: Token contract vulnerabilities
  - *Mitigation*: Use well-audited contracts (USDT, USDC, DAI are battle-tested)
- **Risk**: Decimal conversion errors (6 vs 18 decimals)
  - *Mitigation*: Extensive testing, validation checks, comprehensive logging

**Related Bug:**
- 🔴 CRITICAL: `/OCTOBER/10-26/BUGS.md` - GCHostPay3 ETH/USDT Token Type Confusion
- 📄 Analysis: `/OCTOBER/10-26/GCHOSTPAY3_ETH_USDT_TOKEN_TYPE_CONFUSION_BUG.md`

**Status:** ARCHITECTURE DEFINED - Implementation Pending 🚧

---

### 2025-11-04 Session 59: Configurable Validation Thresholds via Secret Manager ✅

**Decision:** Move hardcoded payment validation thresholds to Secret Manager for runtime configurability without code changes.

**Context:**
- Payment validation in GCWebhook2 had hardcoded thresholds:
  - Primary validation (outcome_amount): **0.75** (75% minimum)
  - Fallback validation (price_amount): **0.95** (95% minimum)
- Legitimate payment failed: **$0.95 received** vs **$1.01 required** (70.4% vs 75% threshold)
- No way to adjust thresholds without code changes and redeployment
- Different environments (dev/staging/prod) may need different tolerance levels

**Problem Pattern:**
- Business logic constants hardcoded in application code
- Unable to adjust thresholds quickly in response to production issues
- No flexibility for A/B testing different tolerance levels
- Code deployment required for simple configuration changes

**Solution:**
1. **Create Secret Manager Secrets**:
   - `PAYMENT_MIN_TOLERANCE` = primary validation threshold (default: 0.50 / 50%)
   - `PAYMENT_FALLBACK_TOLERANCE` = fallback validation threshold (default: 0.75 / 75%)

2. **Configuration Pattern**:
   - ConfigManager fetches thresholds from environment variables
   - Cloud Run injects secrets as env vars using `--set-secrets` flag
   - Defaults preserved in code (0.50, 0.75) for backwards compatibility
   - Comprehensive logging shows which thresholds are loaded

3. **Code Architecture**:
   - ConfigManager: `get_payment_tolerances()` method fetches values
   - DatabaseManager: Accepts tolerance parameters in `__init__()`
   - Main app: Passes config values to DatabaseManager
   - Validation logic: Uses `self.payment_*_tolerance` instead of hardcoded values

**Implementation:**
```python
# config_manager.py - Fetch from Secret Manager
def get_payment_tolerances(self) -> dict:
    min_tolerance = float(os.getenv('PAYMENT_MIN_TOLERANCE', '0.50'))
    fallback_tolerance = float(os.getenv('PAYMENT_FALLBACK_TOLERANCE', '0.75'))
    return {'min_tolerance': min_tolerance, 'fallback_tolerance': fallback_tolerance}

# database_manager.py - Use configurable values
minimum_amount = expected_amount * self.payment_min_tolerance  # Not hardcoded!

# Cloud Run deployment - Inject secrets
--set-secrets="PAYMENT_MIN_TOLERANCE=PAYMENT_MIN_TOLERANCE:latest,..."
```

**Values Chosen:**
- **Primary (50%)**: More lenient than original 75%
  - Accounts for NowPayments fees (~15%)
  - Accounts for price volatility (~10%)
  - Accounts for network fees (~5%)
  - Buffer: 20% cushion for unexpected variations
- **Fallback (75%)**: More lenient than original 95%
  - Used only when crypto-to-USD conversion fails
  - Validates invoice price instead of actual received amount
  - More tolerance needed since it's less accurate

**Benefits:**
- ✅ **Runtime Configuration**: Change thresholds via Secret Manager without code changes
- ✅ **Environment-Specific**: Different values for dev/staging/prod
- ✅ **Audit Trail**: Secret Manager tracks all value changes with versioning
- ✅ **Rollback Capability**: Revert to previous values instantly
- ✅ **Backwards Compatible**: Defaults match new behavior (0.50, 0.75)
- ✅ **Consistent Pattern**: Follows existing `MICRO_BATCH_THRESHOLD_USD` pattern
- ✅ **Reduced False Failures**: More lenient thresholds prevent legitimate payment rejections

**Impact:**
```
Example: $1.35 subscription payment

BEFORE (Hardcoded 75%):
- Minimum required: $1.01 (75% of $1.35)
- Received: $0.95
- Result: ❌ FAILED (70.4% < 75%)

AFTER (Configurable 50%):
- Minimum required: $0.68 (50% of $1.35)
- Received: $0.95
- Result: ✅ PASSES (70.4% > 50%)
```

**Related to:**
- Session 58: Data Flow Separation (both involve data type clarity)
- Session 57: NUMERIC Precision (both involve handling crypto amount variations)
- Pattern: Configuration flexibility reduces operational burden

**Future Enhancements:**
- Could add maximum threshold to detect overpayments
- Could add per-currency thresholds for different fee structures
- Could add monitoring alerts when payments are near threshold

---

### 2025-11-04 Session 58: Data Flow Separation - Calculate vs Pass Through Values ✅

**Decision:** Always pass **original input amounts** to downstream services, keep **calculated values** separate for database storage only.

**Context:**
- GCSplit1 was passing `pure_market_eth_value` (596,726 SHIB) to GCSplit3
- `pure_market_eth_value` is a **calculated token quantity** for database storage
- GCSplit3 needs the **original USDT amount** (5.48) for ChangeNOW API
- Bug resulted in 108,703x multiplier error in ChangeNOW requests

**Problem Pattern:**
- Reusing calculated values (token quantities) as input amounts (USDT)
- Confusion between semantic data types (USDT vs tokens)
- Generic variable names (`eth_amount`) hiding actual data type

**Solution:**
1. **Separation of Concerns**:
   - `pure_market_eth_value` = Database storage ONLY (token quantity for accounting)
   - `from_amount_usdt` = Pass to downstream services (original USDT for swaps)

2. **Variable Naming Convention**:
   - Use semantic names: `usdt_amount`, `token_quantity`, not generic `eth_amount`
   - Add type hints in comments when variable names are ambiguous
   - Log both values in same statement: `print(f"Creating swap: {usdt_in} USDT → {token_out} {currency}")`

3. **Architectural Pattern**:
   - Each service performs its own calculations
   - Don't reuse intermediate calculations across services
   - Always pass original amounts, not derived/calculated values

**Implementation:**
```python
# GCSplit1-10-26/tps1-10-26.py:507

# BEFORE (WRONG):
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    eth_amount=pure_market_eth_value,  # ❌ Calculated token quantity
)

# AFTER (CORRECT):
encrypted_token_for_split3 = token_manager.encrypt_gcsplit1_to_gcsplit3_token(
    eth_amount=from_amount_usdt,  # ✅ Original USDT amount
)
```

**Benefits:**
- Each service receives expected input types
- Clear separation between accounting data and transaction data
- Prevents confusion between different currency types
- Reduces risk of magnitude errors (100,000x multipliers)

**Related to:**
- Session 57: NUMERIC Precision Strategy (also caused by SHIB token quantities)
- Pattern: Both issues involved confusion between USDT amounts and token quantities

---

### 2025-11-04 Session 57: NUMERIC Precision Strategy for Cryptocurrency Amounts ✅

**Decision:** Use differentiated NUMERIC precision based on data type:
- **NUMERIC(20,8)** for USDT/ETH amounts (fiat-equivalent values)
- **NUMERIC(30,8)** for token quantities (low-value tokens like SHIB, DOGE)

**Context:**
- GCSplit1 failing to insert transactions with large SHIB quantities (596,726 tokens)
- Original schema: `NUMERIC(12,8)` max value = **9,999.99999999**
- Low-value tokens can have quantities in **millions or billions**
- Different crypto assets need different precision ranges

**Problem Analysis:**
```
Token Examples & Quantities:
- BTC:  0.00123456    ← small quantity, high value (NUMERIC(20,8) ✅)
- ETH:  1.23456789    ← medium quantity, high value (NUMERIC(20,8) ✅)
- DOGE: 10,000.123    ← large quantity, low value (NUMERIC(30,8) ✅)
- SHIB: 596,726.7004  ← HUGE quantity, micro value (NUMERIC(30,8) ✅)
- PEPE: 1,000,000+    ← extreme quantity (NUMERIC(30,8) ✅)
```

**Options Considered:**

**Option 1: Single Large Precision for All (e.g., NUMERIC(30,18))**
- ✅ One-size-fits-all solution
- ❌ Wastes storage space for USDT amounts (typically < $10,000)
- ❌ Excessive decimal precision (18 places) unnecessary for most tokens
- ❌ Potential performance impact on aggregations

**Option 2: Differentiated Precision by Data Type (CHOSEN)**
- ✅ Optimal storage efficiency
- ✅ Precision matched to data semantics
- ✅ `NUMERIC(20,8)` for USDT/ETH: max 999,999,999,999.99999999
- ✅ `NUMERIC(30,8)` for token quantities: max 9,999,999,999,999,999,999,999.99999999
- ✅ 8 decimal places sufficient for crypto (satoshi-level precision)
- ⚠️ Requires understanding column semantics

**Option 3: Dynamic Scaling Based on Token Type**
- ❌ Too complex - would require token registry
- ❌ Cannot be enforced at database level
- ❌ Prone to errors when new tokens added

**Implementation:**

**Column Categories:**
1. **USDT/Fiat Amounts** → `NUMERIC(20,8)`
   - `split_payout_request.from_amount` (USDT after fees)
   - `split_payout_que.from_amount` (ETH amounts)
   - `split_payout_hostpay.from_amount` (ETH amounts)

2. **Token Quantities** → `NUMERIC(30,8)`
   - `split_payout_request.to_amount` (target token quantity)
   - `split_payout_que.to_amount` (client token quantity)

3. **High-Precision Rates** → `NUMERIC(20,18)` (unchanged)
   - `actual_eth_amount` (NowPayments outcome)

**Migration Strategy:**
```sql
ALTER TABLE split_payout_request ALTER COLUMN from_amount TYPE NUMERIC(20,8);
ALTER TABLE split_payout_request ALTER COLUMN to_amount TYPE NUMERIC(30,8);
-- (repeated for all affected columns)
```

**Testing:**
- ✅ Test insert: 596,726 SHIB → Success
- ✅ Existing data migrated without loss
- ✅ All amount ranges supported

**Tradeoffs:**
- **Pro:** Optimal storage and performance
- **Pro:** Semantic clarity (column type indicates data semantics)
- **Pro:** Supports all known crypto asset types
- **Con:** Developers must understand precision requirements
- **Con:** Future tokens with extreme properties may need schema update

**Future Considerations:**
- Monitor for tokens with quantities > 10^22 (extremely unlikely)
- Consider adding database comments documenting precision rationale
- May need to increase precision for experimental tokens (e.g., fractionalized NFTs)

### 2025-11-03 Session 56: 30-Minute Token Expiration for Async Batch Callbacks ✅

**Decision:** Increase GCMicroBatchProcessor token expiration window from 5 minutes to 30 minutes (1800 seconds)

**Context:**
- GCMicroBatchProcessor rejecting valid callbacks from GCHostPay1 with "Token expired" error
- Batch conversion workflow is **asynchronous** with multiple retry delays:
  - ChangeNow swap can take 5-30 minutes to complete
  - GCHostPay1 retry mechanism: 3 retries × 5 minutes = up to 15 minutes
  - Cloud Tasks queue delays: 30s - 5 minutes
  - **Total workflow delay: 15-20 minutes in normal operation**
- Current 5-minute expiration rejects 70-90% of batch conversion callbacks
- Impact: USDT received but cannot distribute to individual payout records

**Options Considered:**

**Option 1: Increase Expiration Window to 30 Minutes (CHOSEN)**
- ✅ Simple one-line change (`300` → `1800`)
- ✅ Accommodates all known delays in workflow
- ✅ No breaking changes to token format
- ✅ Security maintained via HMAC signature validation
- ✅ Includes safety margin for unexpected delays
- ⚠️ Slightly longer window for theoretical replay attacks (mitigated by signature)

**Calculation:**
```
Max ChangeNow retry delay:  15 minutes (3 retries)
Max Cloud Tasks delay:       5 minutes
Safety margin:              10 minutes
Total:                      30 minutes
```

**Option 2: Refresh Token Timestamp on Each Retry**
- ⚠️ More complex - requires changes to GCHostPay1 retry logic
- ⚠️ Doesn't solve Cloud Tasks queue delay issue
- ⚠️ Hard to ensure token creation happens at right time
- ❌ Not chosen due to complexity vs. benefit

**Option 3: Remove Timestamp Validation Entirely**
- ❌ Less secure - no time-based replay protection
- ❌ Could allow old valid tokens to be replayed
- ❌ Not recommended for security reasons

**Rationale:**
1. **Workflow-Driven Design**: Expiration window must accommodate actual workflow delays
2. **Production Evidence**: Logs show tokens aged 10-20 minutes in normal operation
3. **Security Balance**: 30 minutes is reasonable for async workflows while maintaining security
4. **Simplicity**: One-line change vs. complex retry logic refactoring
5. **Safety Margin**: Accounts for unexpected Cloud Tasks delays during high load
6. **Industry Standard**: 30-minute token expiration common for async workflows

**Implementation:**
```python
# BEFORE
if not (current_time - 300 <= timestamp <= current_time + 5):
    raise ValueError("Token expired")

# AFTER
if not (current_time - 1800 <= timestamp <= current_time + 5):
    raise ValueError("Token expired")
```

**System-Wide Impact:**
- Performed audit of all token_manager.py files across services
- Identified potential similar issues in GCHostPay2, GCSplit3, GCAccumulator
- Recommended standardized expiration windows:
  - Synchronous calls: 5 minutes (300s)
  - Async with retries: 30 minutes (1800s)
  - Long-running workflows: 2 hours (7200s)
  - Internal retry mechanisms: 24 hours (86400s)

**Trade-offs:**
- ✅ **Pro**: Fixes critical production issue immediately
- ✅ **Pro**: Minimal code change, low risk
- ✅ **Pro**: Better logging for token age visibility
- ⚠️ **Con**: Longer window for replay attacks (mitigated by signature + idempotency)

**Future Considerations:**
- Add monitoring for token age distribution
- Add alerting for token expiration rate > 1%
- Consider Phase 2: Review other services with 5-minute windows
- Consider Phase 3: Standardize expiration windows across all services

---

### 2025-11-03 Session 55: Variable-Length String Encoding for Token Serialization ✅

**Decision:** Replace fixed 16-byte encoding with variable-length string encoding (`_pack_string`) for all string fields in inter-service tokens

**Context:**
- Fixed 16-byte encoding systematically truncated UUIDs and caused critical production failure
- GCMicroBatchProcessor received truncated batch_conversion_id: `"f577abaa-1"` instead of full UUID
- PostgreSQL rejected as invalid UUID format: `invalid input syntax for type uuid`
- Found 20+ instances of `.encode('utf-8')[:16]` pattern across 4 services
- Batch conversion flow completely broken

**Options Considered:**

**Option A: Variable-Length Encoding with _pack_string (CHOSEN)**
- Use existing `_pack_string()` method (1-byte length prefix + string bytes)
- Handles any string length up to 255 bytes
- ✅ Preserves full UUIDs (36 chars) and prefixed UUIDs (40+ chars)
- ✅ No silent data truncation
- ✅ Already implemented and proven in other token methods
- ✅ Efficient: only uses bytes needed for actual string
- ✅ Backward compatible with coordinated deployment (sender first, receiver second)
- ⚠️ Requires updating both encrypt and decrypt methods
- ⚠️ Changes token format (incompatible with old versions)

**Option B: Increase Fixed Length to 64 Bytes**
- Change fixed length from 16 → 64 bytes to accommodate longer UUIDs
- ❌ Wastes space for short strings (inefficient)
- ❌ Doesn't scale if we add longer prefixes later (e.g., "accumulation_uuid")
- ❌ Still has truncation risk if strings exceed 64 bytes
- ❌ Adds unnecessary padding bytes to every token

**Option C: Keep Fixed 16-Byte, Change UUID Format**
- Store UUIDs without hyphens (32 hex chars) to fit in 16 bytes
- ❌ Requires changing UUID generation across entire system
- ❌ Prefix strings like "batch_" still exceed 16 bytes
- ❌ Database expects standard UUID format with hyphens
- ❌ Massive refactoring effort across all services

**Rationale for Choice:**
1. **Safety First**: Variable-length prevents silent data corruption
2. **Proven Pattern**: `_pack_string` already used successfully in other tokens
3. **Efficiency**: Only uses bytes needed (1 + string length)
4. **Scalability**: Supports any future string length needs
5. **Minimal Impact**: Fix limited to 2 services for Phase 1 (GCHostPay3, GCHostPay1)
6. **Clear Migration Path**: Phase 2 can systematically fix remaining instances

**Implementation:**

**Encrypt (GCHostPay3):**
```python
# Before:
unique_id_bytes = unique_id.encode('utf-8')[:16].ljust(16, b'\x00')
packed_data.extend(unique_id_bytes)

# After:
packed_data.extend(self._pack_string(unique_id))
```

**Decrypt (GCHostPay1):**
```python
# Before:
unique_id = raw[offset:offset+16].rstrip(b'\x00').decode('utf-8')
offset += 16

# After:
unique_id, offset = self._unpack_string(raw, offset)
```

**Token Format Change:**
```
Old: [16 bytes fixed unique_id][variable cn_api_id]...
New: [1 byte len + N bytes unique_id][1 byte len + M bytes cn_api_id]...
```

**Deployment Strategy:**
1. Deploy sender (GCHostPay3) FIRST → sends new variable-length format
2. Deploy receiver (GCHostPay1) SECOND → reads new format
3. Order critical: receiver must understand new format before sender starts using it

**Trade-offs Accepted:**
- ✅ Accept token format change (requires coordinated deployment)
- ✅ Accept need to update all 20+ instances eventually (Phase 2)
- ✅ Prioritize correctness over minimal code changes

**Future Considerations:**
- Phase 2: Apply same fix to remaining 18 instances (GCHostPay1, GCHostPay2, GCHostPay3, GCSplit1)
- Investigate `closed_channel_id` truncation (may be safe if values always < 16 bytes)
- Add validation to prevent strings > 255 bytes (current `_pack_string` limit)
- Consider protocol versioning if future changes needed

**Monitoring Requirements:**
- Monitor GCHostPay3 logs: Verify full UUIDs in encrypted tokens
- Monitor GCHostPay1 logs: Verify full UUIDs in decrypted tokens
- Monitor GCMicroBatchProcessor logs: NO "invalid input syntax for type uuid" errors
- Alert on any token encryption/decryption errors

**Impact Assessment:**
- ✅ **Fixed:** Batch conversion flow now works with full UUIDs
- ✅ **Unblocked:** GCMicroBatchProcessor can query database successfully
- ⚠️ **Pending:** 18 remaining instances need fixing to prevent future issues
- ⚠️ **Risk:** Threshold payouts (acc_{uuid}) may have same issue if not fixed

**Documentation:**
- `UUID_TRUNCATION_BUG_ANALYSIS.md` - comprehensive root cause analysis
- `UUID_TRUNCATION_FIX_CHECKLIST.md` - 3-phase implementation plan

---

### 2025-11-03 Session 53: Maintain Two-Swap Architecture with Dynamic Currency Handling ✅

**Decision:** Fix existing two-swap batch payout architecture (ETH→USDT→ClientCurrency) by making currency parameters dynamic instead of switching to single-swap ETH→ClientCurrency

**Context:**
- Batch payout second swap was incorrectly using ETH→ClientCurrency instead of USDT→ClientCurrency
- Root cause: Hardcoded currency values in GCSplit2 (estimator) and GCSplit3 (swap creator)
- Two options: (1) Fix existing architecture with dynamic currencies, or (2) Redesign to single-swap ETH→ClientCurrency
- System already successfully accumulates to USDT via first swap (ETH→USDT)

**Options Considered:**

**Option A: Fix Two-Swap Architecture with Dynamic Currencies (CHOSEN)**
- Keep existing flow: ETH→USDT (accumulation) then USDT→ClientCurrency (payout)
- Make GCSplit2 and GCSplit3 use dynamic `payout_currency` and `payout_network` from tokens
- ✅ Minimal code changes (2 services, ~10 lines total)
- ✅ No database schema changes needed
- ✅ USDT provides stable intermediate currency during accumulation
- ✅ Reduces volatility risk for accumulated funds
- ✅ Simpler fee calculations (known USDT value)
- ✅ Easier to track accumulated value in stable currency
- ✅ First swap (ETH→USDT) already proven to work successfully
- ✅ Only second swap needs fixing
- ⚠️ Two API calls to ChangeNow instead of one

**Option B: Single-Swap ETH→ClientCurrency Direct**
- Redesign to swap ETH directly to client payout currency (e.g., ETH→SHIB)
- Eliminate intermediate USDT conversion
- ✅ One API call instead of two
- ✅ Potentially lower total fees (one swap instead of two)
- ❌ Higher volatility exposure during accumulation period
- ❌ More complex fee calculations (ETH price fluctuates)
- ❌ Harder to track accumulated value
- ❌ Requires major refactoring of GCSplit1 orchestration logic
- ❌ Database schema changes needed (amount tracking)
- ❌ More complex error handling (wider price swings)
- ❌ Risks breaking instant conversion flow (shares same services)

**Rationale:**
- **Stability First**: USDT intermediate provides price stability during accumulation period
  - Client funds accumulate in predictable USD value
  - Reduces risk of accumulated balance losing value before payout threshold
- **Proven Architecture**: First swap (ETH→USDT) already working correctly in production
  - Only second swap has bug (simple fix: use dynamic currency)
  - Lower risk to fix existing system than redesign
- **Minimal Impact**: Fix requires only 2 services with ~10 lines changed total
  - No database migrations
  - No Cloud Tasks queue changes
  - No token structure changes
  - Faster deployment (~1 hour vs multi-day refactor)
- **Fee Trade-off Acceptable**: Two swaps incur higher fees BUT provide stability benefit
  - Cost of stability is worth fee increase for accumulated payouts
  - Alternative (single swap) has hidden cost: volatility risk

**Implementation:**
```python
# GCSplit2-10-26/tps2-10-26.py (lines 131-132)
# BEFORE:
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency="eth",      # ❌ Hardcoded
    to_network="eth",       # ❌ Hardcoded
    ...
)

# AFTER:
estimate_response = changenow_client.get_estimated_amount_v2_with_retry(
    from_currency="usdt",
    to_currency=payout_currency,  # ✅ Dynamic from token
    to_network=payout_network,    # ✅ Dynamic from token
    ...
)

# GCSplit3-10-26/tps3-10-26.py (line 130)
# BEFORE:
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="eth",  # ❌ Hardcoded
    ...
)

# AFTER:
transaction = changenow_client.create_fixed_rate_transaction_with_retry(
    from_currency="usdt",  # ✅ Correct source currency
    ...
)
```

**Trade-offs Accepted:**
- ✅ Accept higher fees (two swaps) for stability benefit
- ✅ Accept two ChangeNow API calls for simpler architecture
- ✅ Prioritize minimal code changes over theoretical efficiency gains

**Future Considerations:**
- If ChangeNow fees become prohibitive, reconsider single-swap architecture
- Monitor actual fee percentages in production (log reconciliation data)
- Could optimize by batching multiple client payouts into single large swap
- Could add direct ETH→ClientCurrency path as alternative flow for large payouts

**Related Decisions:**
- Session 31: Two-swap threshold payout architecture design
- Session 28: USDT as intermediate accumulation currency
- Cloud Tasks orchestration: Split services for separation of concerns

**Impact:**
- ✅ Batch payouts now functional with correct currency flow
- ✅ USDT stability maintained during accumulation
- ✅ Client payouts complete successfully
- ✅ Instant conversion flow unchanged (uses different path)
- ✅ Simple fix deployed in ~60 minutes

**Monitoring:**
- Track fee reconciliation: first_swap_fee + second_swap_fee vs hypothetical single_swap_fee
- Monitor volatility impact: compare USDT accumulation stability vs direct ETH accumulation
- Alert if total fees exceed 5% of payout value

---

### 2025-11-03 Session 54: Use create_task() Directly for Batch Callbacks ✅

**Decision:** Call `create_task()` directly instead of creating specialized `enqueue_microbatch_callback()` method

**Context:**
- Batch callback logic (ENDPOINT_4) called non-existent method `cloudtasks_client.enqueue_task()`
- Need immediate fix to make batch conversion callbacks functional
- CloudTasksClient has specialized methods (e.g., `enqueue_gchostpay1_retry_callback()`) but no method for MicroBatch callbacks
- Must decide between using base `create_task()` vs creating new specialized method

**Options Considered:**

**Option A: Use create_task() Directly (CHOSEN)**
- Call the base `create_task(queue_name, target_url, payload)` method
- ✅ Simplest fix (just change method name and parameter)
- ✅ No new code needed in cloudtasks_client.py
- ✅ Fast deployment (~30 minutes)
- ✅ Consistent with CloudTasksClient architecture (specialized methods are just wrappers around create_task())
- ✅ Base method handles all necessary functionality
- ⚠️ Less consistent with existing specialized method pattern

**Option B: Create Specialized enqueue_microbatch_callback() Method**
- Add new method to CloudTasksClient following pattern of other specialized methods
- Follow precedent of `enqueue_gchostpay1_retry_callback()`, `enqueue_gchostpay3_payment_execution()`, etc.
- ✅ Consistent with existing specialized method pattern
- ✅ Better code organization and readability
- ✅ Easier to mock in unit tests
- ❌ More complex implementation (requires updating cloudtasks_client.py)
- ❌ Longer deployment time
- ❌ Not necessary for immediate fix

**Rationale:**
- **Critical production bug** requires fastest fix possible
- Base `create_task()` method is designed to handle all enqueue operations
- Specialized methods are convenience wrappers that just call `create_task()` internally
- Can create specialized method later as clean architecture improvement (Phase 2)
- Precedent: Other services already use `create_task()` directly in some places

**Implementation:**
- Changed line 160 in tphp1-10-26.py:
  ```python
  # FROM (BROKEN):
  task_success = cloudtasks_client.enqueue_task(
      queue_name=microbatch_response_queue,
      url=callback_url,
      payload=payload
  )

  # TO (FIXED):
  task_name = cloudtasks_client.create_task(
      queue_name=microbatch_response_queue,
      target_url=callback_url,
      payload=payload
  )
  ```
- Added task name logging for debugging
- Converted return value (task_name → boolean)

**Future Consideration:**
- May create `enqueue_microbatch_callback()` specialized method later for consistency
- Would follow pattern: wrapper around `create_task()` with MicroBatch-specific logging
- Not urgent - current fix is sufficient for production use

**Related Decisions:**
- Session 53: Config loading for retry logic
- Session 52: ChangeNow integration and retry logic
- Cloud Tasks architecture: Specialized methods vs base methods

**Impact:**
- ✅ Batch conversion callbacks now functional
- ✅ GCMicroBatchProcessor receives swap completion notifications
- ✅ End-to-end batch conversion flow operational
- ✅ Fix deployed in ~30 minutes (critical for production)

---

### 2025-11-03 Session 53: Reuse Response Queue for Retry Logic (Phase 1 Fix) ✅

**Decision:** Use existing `gchostpay1-response-queue` for retry callbacks instead of creating dedicated retry queue

**Context:**
- Session 52 Phase 2 retry logic failed due to missing config (GCHOSTPAY1_URL, GCHOSTPAY1_RESPONSE_QUEUE)
- Need immediate fix to make retry logic functional
- Must decide between reusing existing queue vs creating dedicated retry queue

**Options Considered:**

**Option A: Reuse Existing Response Queue (CHOSEN - Phase 1)**
- Use `gchostpay1-response-queue` for both:
  - External callbacks from GCHostPay3 (payment completion)
  - Internal retry callbacks from GCHostPay1 to itself
- ✅ No new infrastructure needed
- ✅ Minimal changes (just config loading)
- ✅ Fast deployment (~30 minutes)
- ✅ Consistent with current architecture
- ⚠️ Mixes external and internal callbacks in same queue
- ⚠️ Harder to monitor retry-specific metrics

**Option B: Create Dedicated Retry Queue (Recommended - Phase 2)**
- Create new `gchostpay1-retry-queue` for internal retry callbacks
- Follow GCHostPay3 precedent (has both payment queue and retry queue)
- ✅ Clean separation of concerns
- ✅ Easier to monitor retry-specific metrics
- ✅ Better for scaling and debugging
- ✅ Follows existing patterns in GCHostPay3
- ❌ More infrastructure to manage
- ❌ Slightly longer deployment time (~1 hour)

**Decision Rationale:**
1. **Immediate Need**: Retry logic completely broken, need quick fix
2. **Phase 1 (Now)**: Use Option A for immediate fix
3. **Phase 2 (Future)**: Migrate to Option B for clean architecture
4. **Precedent**: GCHostPay3 uses dedicated retry queue, should follow that pattern eventually

**Implementation:**
- ✅ Updated config_manager.py to load GCHOSTPAY1_URL and GCHOSTPAY1_RESPONSE_QUEUE
- ✅ Deployed revision gchostpay1-10-26-00017-rdp
- ⏳ Future: Create GCHOSTPAY1_RETRY_QUEUE and migrate retry logic to use it

**Impact:**
- ✅ Retry logic now functional
- ✅ Batch conversions can complete end-to-end
- ✅ No new infrastructure complexity
- 📝 Technical debt: Should migrate to dedicated retry queue for clean architecture

**Lessons Learned:**
1. **Config Loading Pattern**: When adding self-callback features:
   - Update config_manager.py to fetch service's own URL
   - Update config_manager.py to fetch service's own queue
   - Add secrets to Cloud Run deployment
   - Verify config loading in startup logs
2. **Two-Phase Approach**: Fix critical bugs immediately, refactor for clean architecture later
3. **Follow Existing Patterns**: GCHostPay3 already has retry queue pattern, follow it

**Documentation:**
- Created `CONFIG_LOADING_VERIFICATION_SUMMARY.md` with checklist pattern
- Updated `GCHOSTPAY1_RETRY_QUEUE_CONFIG_FIX_CHECKLIST.md` with both phases

---

### 2025-11-03 Session 52: Cloud Tasks Retry Logic for ChangeNow Swap Completion ✅

**Decision:** Implement automatic retry logic using Cloud Tasks with 5-minute delays to re-query ChangeNow

**Context:**
- Phase 1 fixed crashes with defensive Decimal conversion
- But callbacks still not sent when ChangeNow swap not finished
- Need automated solution to wait for swap completion and send callback

**Options Considered:**

**Option A: Polling from TelePay Bot (REJECTED)**
- Bot periodically checks database for pending conversions
- ❌ Adds complexity to bot service
- ❌ Tight coupling between bot and payment flow
- ❌ Inefficient polling approach
- ❌ Bot may be offline/restarting

**Option B: ChangeNow Webhook Integration (DEFERRED)**
- Subscribe to ChangeNow status update webhooks
- ✅ Event-driven, no polling needed
- ❌ Requires webhook endpoint setup and security
- ❌ Need to verify ChangeNow webhook reliability
- ❌ More complex initial implementation
- 📝 Consider for Phase 3

**Option C: Cloud Tasks Retry Logic (CHOSEN)**
- Enqueue delayed task (5 minutes) to re-query ChangeNow
- ✅ Simple, reliable, built-in scheduling
- ✅ Automatic retry with max limit (3 retries = 15 minutes)
- ✅ No external dependencies
- ✅ Serverless - no persistent polling service needed
- ✅ Recursive retry if swap still in progress
- ✅ Sends callback automatically once finished

**Implementation Details:**
- ENDPOINT_3 detects swap status = waiting/confirming/exchanging/sending
- Enqueues Cloud Task to `/retry-callback-check` with 5-minute delay
- New ENDPOINT_4 re-queries ChangeNow after delay
- If finished: Sends callback with actual_usdt_received
- If still in-progress: Schedules another retry (max 3 total)

**Rationale:**
- Cloud Tasks provides reliable delayed execution without complexity
- Max 3 retries (15 minutes total) covers typical ChangeNow swap time (5-10 min)
- Self-contained within GCHostPay1 service
- No additional infrastructure needed
- Graceful timeout if ChangeNow stuck

**Next Steps:**
- Monitor retry execution in production
- Consider ChangeNow webhook integration for Phase 3 optimization

---

### 2025-11-03 Session 52: Defensive Decimal Conversion Over Fail-Fast ✅

**Decision:** Implement defensive Decimal conversion to return `0` for invalid values instead of crashing

**Context:**
- ChangeNow API returns `null`/empty values when swap not finished
- Original code: `Decimal(str(None))` → ConversionSyntax error
- Need to handle this gracefully without breaking payment workflow

**Options Considered:**

**Option A: Fail-Fast (REJECTED)**
- Let exception crash and propagate up
- ❌ Breaks entire payment workflow
- ❌ No callback sent to MicroBatchProcessor
- ❌ Poor user experience

**Option B: Defensive Conversion (CHOSEN)**
- Return `Decimal('0')` for invalid values
- ✅ Prevents crashes
- ✅ Allows code to continue
- ✅ Clear warning logs when amounts missing
- ⚠️ Requires Phase 2 retry logic to get actual amounts

**Rationale:**
- Better to log a warning and continue than to crash the entire flow
- Phase 2 will add retry logic to query ChangeNow again after swap completes
- Defensive programming principle: handle external API variability gracefully

**Next Steps:**
- Phase 2: Add Cloud Tasks retry logic to check ChangeNow again after 5-10 minutes
- Phase 3: Consider ChangeNow webhook integration for event-driven approach

---

### 2025-11-03 Session 51: No TTL Window Change - Fix Root Cause Instead ✅

**Decision:** Do NOT expand TTL window from 24 hours to 10 minutes; fix the token unpacking order mismatch instead

**Context:**
- User observed "Token expired" errors every minute starting at 13:45:12 EST
- User suspected TTL window was only 1 minute and requested expansion to 10 minutes
- **ACTUAL TTL**: 24 hours backward, 5 minutes forward - already very generous
- **REAL PROBLEM**: GCSplit1 was reading wrong bytes as timestamp due to unpacking order mismatch

**Options Considered:**

**Option A: Expand TTL Window (REJECTED)**
- ❌ Would NOT fix the issue (timestamp being read was 0, not stale)
- ❌ Masks the real problem instead of solving it
- ❌ 24-hour window is already more than sufficient
- ❌ Expanding to 10 minutes would actually REDUCE the window (from 24 hours)

**Option B: Fix Token Unpacking Order (CHOSEN)**
- ✅ Addresses root cause: decryption order must match encryption order
- ✅ GCSplit1 now unpacks actual_eth_amount BEFORE timestamp (matches GCSplit3's packing)
- ✅ Prevents reading zeros (actual_eth_amount bytes) as timestamp
- ✅ Maintains appropriate TTL security window
- ✅ Fixes corrupted actual_eth_amount value (8.706401155e-315)

**Rationale:**
1. **Root Cause Analysis**: Timestamp validation was failing because GCSplit1 read `0x0000000000000000` (actual_eth_amount = 0.0) as the timestamp, not because tokens were old
2. **Binary Structure Alignment**: Encryption and decryption MUST pack/unpack fields in identical order
3. **Security Best Practice**: TTL windows should not be expanded to work around bugs - fix the bug
4. **Data Integrity**: Correcting the unpacking order also fixes the corrupted actual_eth_amount extraction

**Implementation:**
- Swapped unpacking order in `decrypt_gcsplit3_to_gcsplit1_token()` method
- Extract `actual_eth_amount` (8 bytes) FIRST, then `timestamp` (4 bytes)
- Added defensive validation: `if offset + 8 + 4 <= len(payload)`
- TTL window remains 24 hours (appropriate for payment processing)

**Key Lesson:**
When users report time-related errors, verify the actual timestamps being read - don't assume the time window is the problem. Binary structure mismatches can manifest as timestamp validation errors.

---

### 2025-11-03 Session 50: Token Mismatch Resolution - Forward Compatibility Over Rollback ✅

**Decision:** Update GCSplit1 to match GCSplit3's token format instead of rolling back GCSplit3

**Context:**
- GCSplit3 was encrypting tokens WITH `actual_eth_amount` field (8 bytes)
- GCSplit1 expected tokens WITHOUT `actual_eth_amount` field
- 100% token decryption failure - GCSplit1 read actual_eth bytes as timestamp, got 0, threw "Token expired"

**Options Considered:**

**Option A: Update GCSplit1 (CHOSEN)**
- ✅ Preserves `actual_eth_amount` data tracking capability
- ✅ GCSplit1 decryption already has backward compatibility code
- ✅ Forward-compatible with GCSplit3's enhanced format
- ✅ Only requires deploying 1 service (GCSplit1)
- ⚠️ Requires careful binary structure alignment

**Option B: Rollback GCSplit3**
- ❌ Loses `actual_eth_amount` data in GCSplit3→GCSplit1 flow
- ❌ Requires reverting previous deployment
- ❌ Inconsistent with other services that already use actual_eth_amount
- ✅ Simpler immediate fix (remove field)

**Rationale:**
1. **Data Integrity**: Preserving actual_eth_amount is critical for accurate payment tracking
2. **System Evolution**: GCSplit3's enhanced format is the future - align other services to it
3. **Minimal Impact**: GCSplit1's decryption already expects this field (backward compat code exists)
4. **One-Way Door**: Rollback loses functionality; update gains it

**Implementation:**
- Added `actual_eth_amount: float = 0.0` parameter to `encrypt_gcsplit3_to_gcsplit1_token()`
- Added 8-byte packing before timestamp: `packed_data.extend(struct.pack(">d", actual_eth_amount))`
- Updated token structure docstring to reflect new field
- Deployed as revision `gcsplit1-10-26-00015-jpz`

**Long-term Plan:**
- Add version byte to all inter-service tokens for explicit format detection
- Extract TokenManager to shared library to prevent version drift
- Implement integration tests for token compatibility across services

---

### 2025-11-02 Session 49: Deployment Order Strategy - Downstream-First for Backward Compatibility ✅

**Decision:** Deploy services in reverse order (downstream → upstream) to maintain backward compatibility during rolling deployment

**Rationale:**
- Token managers have backward compatibility (default values for missing actual_eth_amount)
- Deploying GCHostPay3 first ensures it can receive tokens with OR without actual_eth_amount
- Deploying GCWebhook1 last ensures it sends actual_eth_amount only when all downstream services are ready
- Prevents 500 errors during deployment window

**Deployment Order:**
1. GCHostPay3 (consumer of actual_eth_amount)
2. GCHostPay1 (pass-through)
3. GCSplit3 (pass-through)
4. GCSplit2 (pass-through)
5. GCSplit1 (pass-through)
6. GCWebhook1 (producer of actual_eth_amount)
7. GCBatchProcessor (batch threshold payouts)
8. GCMicroBatchProcessor (micro-batch conversions)

**Result:** Zero-downtime deployment with no errors during transition

---

### 2025-11-02: GCHostPay3 from_amount Fix - Use ACTUAL ETH from NowPayments, Not ChangeNow Estimates ✅ DEPLOYED

**Decision:** Pass `actual_eth_amount` (from NowPayments `outcome_amount`) through entire payment chain to GCHostPay3

**Status:** 🎉 **DEPLOYED TO PRODUCTION** (Sessions 47-49) - All 8 services live

**Context:**
- **Critical Bug:** GCHostPay3 trying to send 4.48 ETH when wallet only has 0.00115 ETH
- **Root Cause:** `nowpayments_outcome_amount` (ACTUAL ETH) is extracted in GCWebhook1 but NEVER passed downstream
- **Current Flow:** GCSplit2 estimates USDT→ETH, GCSplit3 creates swap, ChangeNow returns wrong amount
- **Result:** 3,886x discrepancy, transaction timeouts

**Problem Analysis:**
```
NowPayments: User pays $5 → Deposits 0.00115340416715763 ETH (ACTUAL)
GCWebhook1: Has ACTUAL ETH but doesn't pass it ❌
GCSplit2: Estimates $3.36 USDT → ~0.00112 ETH (ESTIMATE)
GCSplit3: Creates swap for 0.00115 ETH
ChangeNow: Returns "need 4.48 ETH" (WRONG!)
GCHostPay3: Tries to send 4.48 ETH ❌ TIMEOUT
```

**Options Considered:**

1. ❌ **Query database in GCHostPay3**
   - GCHostPay3 could query `private_channel_users_database` for `nowpayments_outcome_amount`
   - Simpler implementation (one file change)
   - But couples GCHostPay3 to upstream table schema
   - Harder to trace in logs
   - Doesn't work for threshold/batch payouts (multiple payments aggregated)

2. ✅ **Pass through entire payment chain (SELECTED)**
   - Add `actual_eth_amount` parameter to all tokens and database records
   - Preserves Single Responsibility Principle
   - Better traceability in logs
   - Works for all payout modes (instant, threshold, batch)
   - Backward compatible with default values

3. ❌ **Remove GCSplit2 estimate step**
   - Skip USDT→ETH estimation entirely
   - Simpler flow
   - But loses validation of NowPayments conversion rates
   - GCSplit2 still useful for alerting on discrepancies

**Implementation Strategy:**

**Phase 1: Database Schema** (✅ COMPLETE)
- Add `actual_eth_amount NUMERIC(20,18)` to `split_payout_request` and `split_payout_hostpay`
- DEFAULT 0 for backward compatibility
- Constraints and indexes for data integrity

**Phase 2: Token Managers** (🟡 IN PROGRESS)
- GCWebhook1 → GCSplit1: Add `actual_eth_amount` to CloudTasks payload
- GCSplit1 → GCSplit3: Add `actual_eth_amount` to encrypted token
- GCSplit3 → GCSplit1: Pass `actual_eth_amount` through response
- GCSplit1 → GCHostPay1: Add to binary packed token (with backward compat)
- GCHostPay1 → GCHostPay3: Pass through

**Phase 3: Service Code** (⏳ PENDING)
- GCSplit1: Store `actual_eth_amount` in database
- GCHostPay3: Use `actual_eth_amount` for payment (not estimate)
- Add validation: Compare actual vs estimate, alert if >5% difference
- Add balance check before payment

**Deployment Strategy:**
- Deploy in REVERSE order (downstream first) to maintain backward compatibility
- GCHostPay3 first (accepts both old and new token formats)
- GCWebhook1 last (starts sending new tokens)
- Rollback plan ready if needed

**Trade-offs:**
- ✅ **Pros:**
  - Fixes 3,886x discrepancy bug
  - Backward compatible
  - Works for all payout modes
  - Better observability (logs show actual vs estimate)
  - Single source of truth (NowPayments outcome)

- ⚠️ **Cons:**
  - More code changes (6 services)
  - More complex tokens
  - Higher implementation effort

**Alternative Considered:** "Hybrid Approach"
- Store in database AND pass through tokens
- Use token for primary flow
- Database as fallback/verification
- Rejected as over-engineered for current needs

**Validation:**
- Compare ChangeNow estimate vs NowPayments actual at each step
- Alert if discrepancy > 5%
- Log both amounts for forensic analysis
- Check wallet balance before payment

**Impact:**
- Fixes critical bug blocking all crypto payouts
- Enables successful ChangeNow conversions
- Users receive expected payouts
- Platform retains correct fees

**Status:** Phase 1 complete, Phase 2 in progress (2/8 tasks)

### 2025-11-02: Serve payment-processing.html from np-webhook (Same-Origin Architecture)

**Decision:** Serve payment-processing.html from np-webhook service itself instead of Cloud Storage

**Context:**
- Session 44 fixed payment confirmation bug by adding CORS to np-webhook
- But this created redundant URL storage:
  - `NOWPAYMENTS_IPN_CALLBACK_URL` secret = `https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app`
  - Hardcoded in HTML: `API_BASE_URL = 'https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app'`
- Violates DRY principle - URL changes require updates in two places

**Problem:**
```
Old Architecture:
User → storage.googleapis.com/payment-processing.html → np-webhook.run.app/api/payment-status
       (different origins - needed CORS)
```

**Options Considered:**

1. ❌ **Add `/api/config` endpoint to fetch URL dynamically**
   - HTML would call endpoint to get base URL
   - But creates bootstrap problem: where to call config endpoint from?
   - Still needs some hardcoded URL

2. ❌ **Use deployment script to inject URL into HTML**
   - Build-time injection from Secret Manager
   - Complex build pipeline
   - Still requires HTML in Cloud Storage

3. ✅ **Serve HTML from np-webhook itself (same-origin)**
   - HTML and API from same service
   - Uses `window.location.origin` - no hardcoding
   - Eliminates CORS need entirely
   - Single source of truth (NOWPAYMENTS_IPN_CALLBACK_URL)

**Implementation:**
```python
# np-webhook/app.py
@app.route('/payment-processing', methods=['GET'])
def payment_processing_page():
    with open('payment-processing.html', 'r') as f:
        html_content = f.read()
    return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}

# payment-processing.html
const API_BASE_URL = window.location.origin;  // Dynamic, no hardcoding!
```

**Benefits:**
1. ✅ **Single source of truth** - URL only in `NOWPAYMENTS_IPN_CALLBACK_URL` secret
2. ✅ **No hardcoded URLs** - HTML uses `window.location.origin`
3. ✅ **No CORS needed** - Same-origin requests (kept CORS for backward compatibility only)
4. ✅ **Simpler architecture** - HTML and API bundled together
5. ✅ **Better performance** - No preflight OPTIONS requests
6. ✅ **Easier maintenance** - URL change only requires updating one secret

**Trade-offs:**
- **Static hosting:** HTML no longer on CDN (Cloud Storage), served from Cloud Run
  - Impact: Minimal - HTML is small (17KB), Cloud Run is fast enough
  - Benefit: One less moving part to maintain
- **Coupling:** HTML now coupled with backend service
  - Impact: Minor - They're tightly related anyway (API contract)
  - Benefit: Simpler deployment, single service

**Migration Path:**
1. NowPayments success_url updated to: `https://np-webhook-10-26-pjxwjsdktq-uc.a.run.app/payment-processing?order_id={order_id}`
2. Old Cloud Storage URL still works (CORS configured for backward compatibility)
3. Can remove Cloud Storage file after cache expiry

**Status:** IMPLEMENTED & DEPLOYED (2025-11-02, Session 45)

---

### 2025-11-02: CORS Policy for np-webhook API - Allow Cross-Origin Requests from Static Site

**Decision:** Configure CORS to allow cross-origin requests from Cloud Storage and custom domain for `/api/*` endpoints only

**Context:**
- payment-processing.html served from `https://storage.googleapis.com/paygateprime-static/`
- Needs to poll np-webhook API at `https://np-webhook-10-26-*.run.app/api/payment-status`
- Browser blocks cross-origin requests without CORS headers
- Users stuck at "Processing Payment..." page indefinitely

**Problem:**
- Frontend (storage.googleapis.com) ≠ Backend (np-webhook.run.app) → Different origins
- Browser Same-Origin Policy blocks fetch requests without CORS headers
- 100% of users unable to see payment confirmation

**Options Considered:**

1. ❌ **Move payment-processing.html to Cloud Run (same-origin)**
   - Would eliminate CORS entirely
   - But requires entire HTML/JS/CSS stack on Cloud Run
   - Unnecessary infrastructure complexity
   - Static files better served from Cloud Storage

2. ❌ **Use Cloud Functions for separate API**
   - Creates unnecessary duplication
   - np-webhook already has the data
   - More services to maintain

3. ✅ **Add CORS to existing np-webhook API**
   - Simple, secure, efficient
   - Only exposes read-only API endpoints
   - IPN endpoint remains protected
   - No infrastructure changes needed

**Implementation:**
```python
from flask_cors import CORS

CORS(app, resources={
    r"/api/*": {                                    # Only /api/* routes (NOT IPN /)
        "origins": [
            "https://storage.googleapis.com",       # Cloud Storage static site
            "https://www.paygateprime.com",         # Custom domain
            "http://localhost:3000"                 # Local development
        ],
        "methods": ["GET", "OPTIONS"],              # Read-only
        "allow_headers": ["Content-Type", "Accept"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,              # No cookies/auth
        "max_age": 3600                             # 1-hour preflight cache
    }
})
```

**Security Considerations:**
- ✅ **Origin whitelist** (not wildcard `*`) - Only specific domains allowed
- ✅ **Method restriction** (GET/OPTIONS only) - No writes from browser
- ✅ **IPN endpoint (POST /) NOT exposed to CORS** - Remains protected
- ✅ **No sensitive data in API response** - Only payment status (confirmed/pending/failed)
- ✅ **No authentication cookies shared** (`supports_credentials=False`)
- ✅ **Read-only operations** - API only checks status, doesn't modify data

**Alternative for Future:**
Custom domain (api.paygateprime.com) with Cloud Load Balancer would eliminate CORS entirely (same-origin), but adds complexity:
- Would require: Custom domain → Load Balancer → Cloud Run
- Current solution is simpler and more cost-effective
- Can revisit if scaling requirements change

**Benefits:**
- ✅ Simple implementation (one dependency: flask-cors)
- ✅ Secure (whitelist, read-only, no credentials)
- ✅ Efficient (1-hour preflight cache reduces OPTIONS requests)
- ✅ Maintainable (clear separation: /api/* = CORS, / = IPN protected)

**Status:** IMPLEMENTED & DEPLOYED (2025-11-02)

---

### 2025-11-02: Database Access Pattern - Use get_connection() Not execute_query()

**Decision:** Always use DatabaseManager's `get_connection()` method + cursor operations for custom queries, NOT a generic `execute_query()` method

**Context:**
- Idempotency implementation assumed DatabaseManager had an `execute_query()` method
- DatabaseManager only provides specific methods (`record_private_channel_user()`, `get_payout_strategy()`, etc.)
- For custom queries, must use: `get_connection()` → `cursor()` → `execute()` → `commit()` → `close()`
- NP-Webhook correctly used this pattern; GCWebhook1/2 did not

**Rationale:**
- **Design Philosophy:** DatabaseManager uses specific, purpose-built methods for common operations
- **Flexibility:** `get_connection()` provides full control for complex queries
- **Consistency:** All custom queries should follow same pattern as NP-Webhook
- **pg8000 Behavior:** Returns tuples, not dicts - must use index access `result[0]` not `result['column']`

**Implementation Pattern:**
```python
# CORRECT PATTERN (for UPDATE/INSERT):
conn = db_manager.get_connection()
if conn:
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close()
    conn.close()

# CORRECT PATTERN (for SELECT):
conn = db_manager.get_connection()
if conn:
    cur = conn.cursor()
    cur.execute(query, params)
    result = cur.fetchone()  # Returns tuple: (val1, val2, val3)
    cur.close()
    conn.close()
# Access: result[0], result[1], result[2] (NOT result['column'])

# WRONG:
db_manager.execute_query(query, params)  # Method doesn't exist!
```

**Impact:** Fixed critical idempotency bugs in GCWebhook1 and GCWebhook2

---

### 2025-11-02: Environment Variable Naming Convention - Match Secret Manager Secret Names

**Decision:** Environment variable names should match Secret Manager secret names unless aliasing is intentional and documented

**Context:**
- NP-Webhook service failed to load `NOWPAYMENTS_IPN_SECRET` despite secret existing in Secret Manager
- Deployment configuration used `NOWPAYMENTS_IPN_SECRET_KEY` as env var name, mapping to `NOWPAYMENTS_IPN_SECRET` secret
- Code read `os.getenv('NOWPAYMENTS_IPN_SECRET')`, which didn't exist
- Previous session fixed secret reference but left env var name inconsistent

**Alternatives Considered:**

**Option 1: Fix deployment config (CHOSEN)**
- Change env var name from `NOWPAYMENTS_IPN_SECRET_KEY` → `NOWPAYMENTS_IPN_SECRET`
- Pros: Consistent naming, single deployment fix, no code changes
- Cons: None

**Option 2: Fix code to read different env var**
- Change code to `os.getenv('NOWPAYMENTS_IPN_SECRET_KEY')`
- Pros: Would work
- Cons: Inconsistent naming (env var differs from secret), requires code rebuild

**Rationale:**
- **Consistency:** Env var name matching secret name reduces cognitive load
- **Clarity:** Makes deployment configs self-documenting
- **Maintainability:** Future developers can easily map env vars to secrets
- **Error Prevention:** Reduces chance of similar mismatches

**Implementation Pattern:**
```yaml
# CORRECT:
- name: MY_SECRET              # ← Env var name
  valueFrom:
    secretKeyRef:
      name: MY_SECRET          # ← Same as env var name
      key: latest

# WRONG (what we had):
- name: MY_SECRET_KEY          # ← Different from secret name
  valueFrom:
    secretKeyRef:
      name: MY_SECRET          # ← Code can't find it!
      key: latest
```

**Enforcement:**
- Documented in NOWPAYMENTS_IPN_SECRET_ENV_VAR_MISMATCH_FIX_CHECKLIST.md
- Future deployments should verify env var names match secret names
- Exception: Intentional aliasing (e.g., mapping `DB_PASSWORD` → `DATABASE_PASSWORD_SECRET`) must be documented

**Related Files:**
- np-webhook-10-26 deployment configuration (fixed)
- NOWPAYMENTS_IPN_SECRET_ENV_VAR_MISMATCH_FIX_CHECKLIST.md (prevention guide)

---

### 2025-11-02: Multi-Layer Idempotency Architecture - Defense-in-Depth Against Duplicate Invites

**Decision:** Implement three-layer idempotency system using database-enforced uniqueness + application-level checks

**Context:**
- Users receiving 11+ duplicate Telegram invites for single payment
- Duplicate payment processing causing data integrity issues
- Cloud Tasks retry mechanism amplifying the problem
- Payment success page polling /api/payment-status repeatedly without idempotency

**Alternatives Considered:**

1. **Single-Layer at NP-Webhook Only**
   - ❌ Rejected: Doesn't prevent GCWebhook1/GCWebhook2 internal retries
   - ❌ Risk: If NP-Webhook check fails, entire flow unprotected

2. **Application-Level Only (No Database)**
   - ❌ Rejected: Race conditions between concurrent requests
   - ❌ Risk: Multiple NP-Webhook instances could process same payment

3. **Database-Level Only (No Application Checks)**
   - ❌ Rejected: Would require catching PRIMARY KEY violations
   - ❌ Risk: Error handling complexity, poor user feedback

4. **Three-Layer Defense-in-Depth** ✅ SELECTED
   - ✅ Database PRIMARY KEY enforces atomic uniqueness
   - ✅ NP-Webhook checks before GCWebhook1 enqueue (prevents duplicate processing)
   - ✅ GCWebhook1 marks processed after routing (audit trail)
   - ✅ GCWebhook2 checks before send + marks after (prevents duplicate invites)
   - ✅ Fail-open mode: System continues if DB unavailable (prefer duplicate over blocking)
   - ✅ Non-blocking DB updates: Payment processing continues on DB error

**Architecture:**

```
Payment Success Page Polling
         ↓ (repeated /api/payment-status calls)
    NP-Webhook IPN Handler
         ↓ (Layer 1: Check processed_payments)
         ├─ If gcwebhook1_processed = TRUE → Return 200 (no re-process)
         └─ If new → INSERT payment_id with ON CONFLICT DO NOTHING
         ↓
    Enqueue to GCWebhook1
         ↓
    GCWebhook1 Orchestrator
         ↓ (Routes to GCAccumulator/GCSplit1 + GCWebhook2)
         ↓ (Layer 2: Mark after routing)
         └─ UPDATE processed_payments SET gcwebhook1_processed = TRUE
         ↓
    Enqueue to GCWebhook2 (with payment_id)
         ↓
    GCWebhook2 Telegram Sender
         ↓ (Layer 3: Check before send)
         ├─ If telegram_invite_sent = TRUE → Return 200 (no re-send)
         ├─ If new → Send Telegram invite
         └─ UPDATE telegram_invite_sent = TRUE, store invite_link
```

**Implementation Details:**
- Database: `processed_payments` table (payment_id PRIMARY KEY, boolean flags, timestamps)
- NP-Webhook: 85-line idempotency check (lines 638-723)
- GCWebhook1: 20-line processing marker (lines 428-448), added payment_id to CloudTasks payload
- GCWebhook2: 47-line pre-check (lines 125-171) + 28-line post-marker (lines 273-300)
- All layers use fail-open mode (proceed if DB unavailable)
- All DB updates non-blocking (continue on error)

**Benefits:**
1. **Prevents duplicate invites:** Even with Cloud Tasks retries
2. **Prevents duplicate processing:** Multiple IPN callbacks handled correctly
3. **Audit trail:** Timestamps show when each layer processed payment
4. **Graceful degradation:** System continues if DB temporarily unavailable
5. **Performance:** Indexes on user_channel, invite_status, webhook1_status
6. **Debugging:** Can query incomplete processing (flags not all TRUE)

**Trade-offs:**
- Added database table (minimal storage cost)
- Additional DB queries per payment (3 SELECT, 2 UPDATE)
- Code complexity increased (154 lines across 3 services)
- BUT: Eliminates user-facing duplicate invite problem completely

**Deployment:**
- np-webhook-10-26-00006-9xs ✅
- gcwebhook1-10-26-00019-zbs ✅
- gcwebhook2-10-26-00016-p7q ✅

**Testing Plan:**
- Phase 8: User creates test payment, verify single invite
- Monitor processed_payments for records
- Check logs for 🔍 [IDEMPOTENCY] messages
- Simulate duplicate IPN to test Layer 1

---

### 2025-11-02: Cloud Tasks Queue Creation Strategy - Create Entry Point Queues First

**Decision:** Always create **entry point queues** (external → service) BEFORE internal service queues

**Context:**
- Cloud Tasks queues must exist before tasks can be enqueued to them
- Services can have multiple queue types:
  1. **Entry point queues** - External systems/services sending tasks TO this service
  2. **Exit point queues** - This service sending tasks TO other services
  3. **Internal queues** - Service-to-service communication within orchestration flow
- NP-Webhook → GCWebhook1 is the **critical entry point** for all payment processing
- Missing entry point queue causes 404 errors and completely blocks payment flow

**Problem:**
- Deployment scripts created internal queues (GCWebhook1 → GCWebhook2, GCWebhook1 → GCSplit1)
- **Forgot to create entry point queue** (NP-Webhook → GCWebhook1)
- Secret Manager had `GCWEBHOOK1_QUEUE=gcwebhook1-queue` but queue never created
- Result: 404 errors blocking ALL payment processing

**Queue Creation Priority (MUST FOLLOW):**

1. **Entry Point Queues (CRITICAL):**
   - `gcwebhook1-queue` - NP-Webhook → GCWebhook1 (payment entry)
   - `gcsplit-webhook-queue` - GCWebhook1 → GCSplit1 (payment processing)
   - `accumulator-payment-queue` - GCWebhook1 → GCAccumulator (threshold payments)

2. **Internal Processing Queues (HIGH PRIORITY):**
   - `gcwebhook-telegram-invite-queue` - GCWebhook1 → GCWebhook2 (invites)
   - `gcsplit-usdt-eth-estimate-queue` - GCSplit1 → GCSplit2 (conversions)
   - `gcsplit-eth-client-swap-queue` - GCSplit2 → GCSplit3 (swaps)

3. **HostPay Orchestration Queues (MEDIUM PRIORITY):**
   - `gchostpay1-batch-queue` - Batch payment initiation
   - `gchostpay2-status-check-queue` - ChangeNow status checks
   - `gchostpay3-payment-exec-queue` - ETH payment execution

4. **Response & Retry Queues (LOW PRIORITY):**
   - `gchostpay1-response-queue` - Payment completion responses
   - `gcaccumulator-response-queue` - Accumulator responses
   - `gchostpay3-retry-queue` - Failed payment retries

**Implementation Guidelines:**

1. **Before deploying a new service:**
   - Identify all queues the service will RECEIVE tasks from (entry points)
   - Create those queues FIRST
   - Then create queues the service will SEND tasks to (exit points)

2. **Queue verification checklist:**
   ```bash
   # For each service, verify:
   1. Entry point queues exist (critical path)
   2. Exit point queues exist (orchestration)
   3. Response queues exist (async patterns)
   4. Retry queues exist (error handling)
   ```

3. **Secret Manager verification:**
   ```bash
   # Verify secret value matches actual queue:
   QUEUE_NAME=$(gcloud secrets versions access latest --secret=QUEUE_SECRET)
   gcloud tasks queues describe "$QUEUE_NAME" --location=us-central1
   ```

**Why This Approach:**
- **Entry points are single points of failure** - Missing entry queue blocks entire flow
- **Internal queues can be created lazily** - Services can retry until queue exists
- **Priority ensures critical path works first** - Payments processed before optimizations
- **Systematic approach prevents gaps** - Checklist ensures no missing queues

**Example Application:**

When deploying NP-Webhook:
```bash
# CORRECT ORDER:
# 1. Create entry point queue (NP-Webhook receives from external)
#    (None - NP-Webhook receives HTTP callbacks, not Cloud Tasks)
#
# 2. Create exit point queue (NP-Webhook sends to GCWebhook1)
gcloud tasks queues create gcwebhook1-queue --location=us-central1 ...
#
# 3. Deploy service
gcloud run deploy np-webhook-10-26 ...
```

**Consequences:**
- ✅ Payment processing never blocked by missing entry queue
- ✅ Deployment failures caught early (missing critical queues)
- ✅ Clear priority for queue creation
- ✅ Systematic checklist prevents gaps
- ⚠️ Must maintain queue dependency map (documented in QUEUE_VERIFICATION_REPORT.md)

**Status:** ✅ Implemented (Session 40)

**Related:** Session 39 (newline fix), Session 40 (queue 404 fix)

---

### 2025-11-02: Defensive Environment Variable Handling - Always Strip Whitespace

**Decision:** ALL environment variable fetches MUST use defensive `.strip()` pattern to handle trailing/leading whitespace

**Context:**
- Google Cloud Secret Manager values can contain trailing newlines (especially when created via CLI with `echo`)
- Cloud Run injects secrets as environment variables via `--set-secrets`
- Services fetch these values using `os.getenv()`
- Cloud Tasks API strictly validates queue names: only `[A-Za-z0-9-]` allowed
- A single trailing newline in a queue name causes 400 errors: `Queue ID "gcwebhook1-queue\n" can contain only letters...`

**Problem:**
```python
# BROKEN: No whitespace handling
GCWEBHOOK1_QUEUE = os.getenv('GCWEBHOOK1_QUEUE')
# If secret value is "gcwebhook1-queue\n" (17 bytes with newline)
# Result: Cloud Tasks API returns 400 error
```

**Vulnerable Pattern Found:**
- **ALL 12 services** used unsafe `os.getenv()` without `.strip()`
- np-webhook-10-26, GCWebhook1-10-26, GCWebhook2-10-26
- GCSplit1-10-26, GCSplit2-10-26, GCSplit3-10-26
- GCAccumulator-10-26, GCBatchProcessor-10-26, GCMicroBatchProcessor-10-26
- GCHostPay1-10-26, GCHostPay2-10-26, GCHostPay3-10-26

**Options Considered:**

1. **Fix only the affected secrets** ❌ Rejected
   - Only addresses immediate issue
   - No protection against future whitespace in secrets
   - Other secrets could have same issue

2. **Add .strip() only in np-webhook** ❌ Rejected
   - Systemic vulnerability affects all services
   - Other services use queue names/URLs too
   - Half-measure solution

3. **Defensive .strip() in ALL services** ✅ **CHOSEN**
   - Handles None values gracefully
   - Strips leading/trailing whitespace
   - Returns None if empty after stripping
   - Protects against future secret creation errors
   - Industry best practice

**Solution Implemented:**
```python
# SAFE: Defensive pattern handles all edge cases
secret_value = (os.getenv(secret_name_env) or '').strip() or None
# - If env var doesn't exist: os.getenv() returns None
#   → (None or '') = '' → ''.strip() = '' → ('' or None) = None ✅
# - If env var is empty string: '' → ''.strip() = '' → None ✅
# - If env var has whitespace: '\n' → ''.strip() = '' → None ✅
# - If env var has value with whitespace: 'queue\n' → 'queue' ✅
# - If env var has clean value: 'queue' → 'queue' ✅
```

**Impact:**
- ✅ Protects against trailing newlines in Secret Manager values
- ✅ Protects against leading whitespace
- ✅ Protects against empty-string secrets
- ✅ No behavior change for clean values
- ✅ All 12 services now resilient

**Files Modified:**
1. `/np-webhook-10-26/app.py` - Lines 31, 39-42, 89-92
2. `/GC*/config_manager.py` - 11 files, all `fetch_secret()` methods updated

**Pattern to Use Going Forward:**
```python
# For environment variables
VALUE = (os.getenv('ENV_VAR_NAME') or '').strip() or None

# For config_manager.py fetch_secret() method
secret_value = (os.getenv(secret_name_env) or '').strip() or None
if not secret_value:
    print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set or empty")
    return None
```

**Why This Matters:**
- Cloud Tasks queue names are used in API path construction: `projects/{project}/locations/{location}/queues/{queue_name}`
- URLs are used in HTTP requests: any trailing whitespace breaks the request
- Database connection strings with whitespace cause connection failures
- This is a **systemic vulnerability** affecting production payment processing

**Lessons Learned:**
- Secret Manager CLI commands need `echo -n` (no newline) or heredoc
- Always use defensive coding for external inputs (env vars, secrets, API responses)
- Whitespace bugs are silent until they break critical paths
- One bad secret can cascade through multiple services

### 2025-11-02: URL Encoding for Query Parameters in success_url

**Decision:** Always URL-encode query parameter values when constructing URLs for external APIs

**Context:**
- NowPayments API requires `success_url` parameter in payment invoice creation
- Our order_id format uses pipe separator: `PGP-{user_id}|{open_channel_id}`
- Example: `PGP-6271402111|-1003268562225`
- Pipe character `|` is not a valid URI character per RFC 3986
- NowPayments API rejected URLs: `{"message":"success_url must be a valid uri"}`

**Problem:**
```python
# BROKEN: Unencoded special characters in URL
order_id = "PGP-6271402111|-1003268562225"
success_url = f"{base_url}?order_id={order_id}"
# Result: ?order_id=PGP-6271402111|-1003268562225
# Pipe | is invalid in URIs → NowPayments returns 400 error
```

**Options Considered:**

1. **Change order_id format to remove pipe** ❌ Rejected
   - Would break existing order_id parsing in np-webhook
   - Pipe separator chosen specifically to preserve negative channel IDs
   - Architectural regression

2. **URL-encode only pipe character** ⚠️ Fragile
   - `order_id.replace('|', '%7C')`
   - Doesn't handle other special characters
   - Manual encoding prone to errors

3. **Use urllib.parse.quote() for all query parameters** ✅ CHOSEN
   - Handles all special characters automatically
   - RFC 3986 compliant
   - Standard Python library (no dependencies)
   - One-line fix

**Decision Rationale:**
- **Option 3 selected**: Use `urllib.parse.quote(order_id, safe='')`
- Standard Python solution for URL encoding
- Handles all edge cases (pipe, space, ampersand, etc.)
- Future-proof: works regardless of order_id format changes
- No external dependencies

**Implementation:**
```python
from urllib.parse import quote

# Encode query parameter value
order_id = "PGP-6271402111|-1003268562225"
encoded_order_id = quote(order_id, safe='')
# Result: "PGP-6271402111%7C-1003268562225"

# Build URL with encoded parameter
success_url = f"{base_url}?order_id={encoded_order_id}"
# Result: https://...?order_id=PGP-6271402111%7C-1003268562225 ✅
```

**Parameter: `safe=''`**
- By default, `quote()` doesn't encode `/` (for path segments)
- `safe=''` means encode EVERYTHING (for query parameter values)
- Ensures maximum compatibility with strict API validators

**Character Encoding:**
```
| → %7C (pipe)
- → %2D (dash)
  → %20 (space)
& → %26 (ampersand)
= → %3D (equals)
# → %23 (hash)
```

**Trade-offs:**
- ✅ RFC 3986 compliant URLs
- ✅ Works with strict API validators (NowPayments, PayPal, Stripe, etc.)
- ✅ One-line fix with standard library
- ✅ Handles all special characters automatically
- ⚠️ URL slightly longer (encoded vs raw)
- ⚠️ Less human-readable in logs (acceptable trade-off)

**Alternative Rejected:**
- **Custom order_id format without special chars**: Rejected - would require rewriting order_id architecture
- **Base64 encoding**: Rejected - unnecessary complexity, still needs URL encoding for `=` and `/`

**Enforcement Pattern:**
```python
# ALWAYS use quote() when building URLs with dynamic values
from urllib.parse import quote

# ✅ CORRECT:
url = f"{base}?param={quote(value, safe='')}"

# ❌ WRONG:
url = f"{base}?param={value}"  # Special chars will break
url = f"{base}?param={value.replace('|', '%7C')}"  # Manual encoding fragile
```

**Impact:**
- ✅ NowPayments API accepts success_url
- ✅ Payment flow completes successfully
- ✅ Users redirected to landing page
- ✅ No more "invalid uri" errors

**Related Patterns:**
- Use `quote_plus()` for form data (spaces → `+` instead of `%20`)
- Use `urlencode()` for multiple query parameters
- Never manually replace special characters

**Files Modified:**
- `TelePay10-26/start_np_gateway.py` (added import, updated line 300)

**Status:** ADOPTED (2025-11-02) - Standard pattern for all URL construction

---

### 2025-11-02: Secret Manager Configuration Validation Strategy

**Decision:** Rely on deployment-time secret mounting rather than code-based validation for Cloud Run services

**Context:**
- GCSplit1 was missing HOSTPAY_WEBHOOK_URL and HOSTPAY_QUEUE environment variables
- Secrets existed in Secret Manager but were never mounted via `--set-secrets`
- Service started successfully but silently failed when trying to use missing configuration
- This created a "silent failure" scenario that's hard to debug

**Problem:**
```python
# In config_manager.py:
hostpay_webhook_url = self.fetch_secret("HOSTPAY_WEBHOOK_URL")
hostpay_queue = self.fetch_secret("HOSTPAY_QUEUE")

# Returns None if secret not mounted, but doesn't fail startup
# Later in code:
if not hostpay_queue or not hostpay_webhook_url:
    abort(500, "HostPay configuration error")  # Only fails when used
```

**Solution Chosen:** Deployment Configuration Fix
```bash
gcloud run services update gcsplit1-10-26 \
  --update-secrets=HOSTPAY_WEBHOOK_URL=HOSTPAY_WEBHOOK_URL:latest,HOSTPAY_QUEUE=HOSTPAY_QUEUE:latest
```

**Alternatives Considered:**

1. **Make secrets required in code** ❌ Rejected
   ```python
   if not hostpay_webhook_url:
       raise ValueError("HOSTPAY_WEBHOOK_URL is required")
   ```
   - Pros: Fail fast at startup if missing
   - Cons: Too strict - might prevent service from starting even if feature not needed yet

2. **Add pre-deployment validation script** ⚠️ Considered for future
   ```bash
   ./scripts/verify_service_config.sh gcsplit1-10-26
   ```
   - Pros: Catches issues before deployment
   - Cons: Requires maintaining separate validation logic

3. **Use deployment templates** ⚠️ Considered for future
   - Pros: Declarative configuration ensures consistency
   - Cons: More complex deployment process

**Decision Rationale:**
- Keep code flexible (don't require all secrets for all deployments)
- Fix at deployment layer where the issue actually occurred
- Use monitoring/logs to catch missing configuration warnings
- Consider stricter validation for production-critical services only

**Implementation:**
- Fixed GCSplit1 by adding missing secrets to deployment
- Created comprehensive checklist: `GCSPLIT1_MISSING_HOSTPAY_CONFIG_FIX.md`
- Verified no other services affected (only GCSplit1 needs these secrets)

**Monitoring Strategy:**
Always check startup logs for ❌ indicators:
```bash
gcloud logging read \
  "resource.labels.service_name=gcsplit1-10-26 AND textPayload:CONFIG" \
  --limit=20
```

**Future Improvements:**
- Consider adding deployment validation for production services
- Monitor for ❌ in configuration logs and alert if critical secrets missing
- Document required secrets per service in deployment README

**Status:** ADOPTED (2025-11-02) - Use deployment-time mounting with log monitoring

---

### 2025-11-02: Null-Safe String Handling Pattern for JSON Parsing

**Decision:** Use `(value or default)` pattern instead of `.get(key, default)` for string method chaining

**Context:**
- GCSplit1 crashed with `'NoneType' object has no attribute 'strip'` error
- Database NULL values sent as JSON `null` → Python `None`
- Python's `.get(key, default)` only uses default when key is MISSING, not when value is `None`

**Problem:**
```python
# Database returns NULL → JSON: {"wallet_address": null} → Python: None
data = {"wallet_address": None}

# BROKEN: .get(key, default) doesn't protect against None values
wallet_address = data.get('wallet_address', '').strip()
# Returns: None (key exists!)
# Then: None.strip() → AttributeError ❌
```

**Solution Chosen:** Or-coalescing pattern `(value or default)`
```python
# CORRECT: Use or-coalescing to handle None explicitly
wallet_address = (data.get('wallet_address') or '').strip()
# Returns: (None or '') → ''
# Then: ''.strip() → '' ✅
```

**Alternatives Considered:**
1. **Helper Function** (most verbose)
   ```python
   def safe_str(value, default=''):
       return str(value).strip() if value not in (None, '') else default
   ```
   - Rejected: Too verbose, adds function overhead

2. **Explicit None Check** (clearest but verbose)
   ```python
   value = data.get('wallet_address')
   wallet_address = value.strip() if value else ''
   ```
   - Rejected: Requires 2 lines per field (verbose)

3. **Or-Coalescing** (most Pythonic) ✅ CHOSEN
   ```python
   wallet_address = (data.get('wallet_address') or '').strip()
   ```
   - ✅ One-liner, readable, handles all cases
   - ✅ Works for None, empty string, missing key
   - ✅ Common Python idiom

**Rationale:**
- Most concise and Pythonic solution
- Single line of code per field
- Handles all edge cases: None, '', missing key
- Widely used pattern in Python community
- No performance overhead

**Impact:**
- Applied to GCSplit1-10-26 ENDPOINT_1 (wallet_address, payout_currency, payout_network, subscription_price)
- Pattern should be used in ALL services for JSON parsing
- Prevents future NoneType AttributeError crashes

**Implementation:**
```python
# Standard pattern for all JSON field extraction with string methods:
field = (json_data.get('field_name') or '').strip()
field_lower = (json_data.get('field_name') or '').strip().lower()
field_upper = (json_data.get('field_name') or '').strip().upper()

# For numeric fields:
amount = json_data.get('amount') or 0
price = json_data.get('price') or '0'

# For lists:
items = json_data.get('items') or []
```

**Related Documents:**
- Bug Report: `BUGS.md` (2025-11-02: GCSplit1 NoneType AttributeError)
- Fix Checklist: `GCSPLIT1_NONETYPE_STRIP_FIX_CHECKLIST.md`
- Code Change: `/GCSplit1-10-26/tps1-10-26.py` lines 296-304

**Status:** ADOPTED (2025-11-02) - Standard pattern for all future JSON parsing

---

### 2025-11-02: Static Landing Page Architecture for Payment Confirmation

**Decision:** Replace GCWebhook1 token-based redirect with static landing page + payment status polling API

**Context:**
- Previous architecture: NowPayments success_url → GCWebhook1 (token encryption) → GCWebhook2 (Telegram invite)
- Problems:
  - Token encryption/decryption overhead
  - Cloud Run cold starts delaying redirects (up to 10 seconds)
  - Complex token signing/verification logic
  - Poor user experience (blank page while waiting)
  - Difficult to debug token encryption failures

**Options Considered:**

1. **Keep existing token-based flow** - Status quo
   - Pros: Already implemented, working
   - Cons: Slow, complex, poor UX, hard to debug

2. **Direct Telegram redirect from NowPayments** - Skip intermediate pages
   - Pros: Fastest possible redirect
   - Cons: No payment confirmation, race condition with IPN, security risk

3. **Static landing page with client-side polling** - CHOSEN
   - Pros: Fast initial load, real-time status updates, good UX, simple architecture
   - Cons: Requires polling API, client-side JavaScript dependency

4. **Server-side redirect with database poll** - Dynamic page with server-side logic
   - Pros: No client JavaScript needed
   - Cons: Still has Cloud Run cold starts, more complex than static page

**Decision Rationale:**

Selected Option 3 (Static Landing Page) because:

1. **Performance:**
   - Static page loads instantly (Cloud Storage CDN)
   - No Cloud Run cold starts
   - Parallel processing: IPN updates database while user sees landing page

2. **User Experience:**
   - Visual feedback: "Processing payment..."
   - Real-time status updates every 5 seconds
   - Progress indication (time elapsed, status changes)
   - Clear error messages if payment fails

3. **Simplicity:**
   - No token encryption/decryption
   - No signed URLs
   - Simple URL: `?order_id={order_id}` instead of `?token={encrypted_blob}`
   - Easier debugging (just check payment_status in database)

4. **Cost:**
   - Cloud Storage cheaper than Cloud Run
   - Fewer Cloud Run invocations (no GCWebhook1 token endpoint hits)
   - Reduced compute costs

5. **Reliability:**
   - No dependency on GCWebhook1 service availability
   - Graceful degradation: polling continues even if API temporarily unavailable
   - Timeout handling: clear message after 10 minutes

**Implementation:**

**Components:**
1. **Cloud Storage Bucket:** `gs://paygateprime-static`
   - Public read access
   - CORS configured for GET requests

2. **Static Landing Page:** `payment-processing.html`
   - JavaScript polls `/api/payment-status` every 5 seconds
   - Displays payment status with visual indicators
   - Auto-redirects to Telegram on confirmation
   - Timeout after 10 minutes (120 polls)

3. **Payment Status API:** `GET /api/payment-status?order_id={order_id}`
   - Returns: {status: pending|confirmed|failed|error, message, data}
   - Queries `payment_status` column in database
   - Two-step lookup: order_id → closed_channel_id → payment_status

4. **Database Schema:**
   - Added `payment_status` column to `private_channel_users_database`
   - Values: 'pending' (default) | 'confirmed' (IPN validated) | 'failed'
   - Index: `idx_nowpayments_order_id_status` for fast lookups

5. **IPN Handler Update:**
   - np-webhook sets `payment_status='confirmed'` on successful IPN validation
   - Atomic update with nowpayments_payment_id

**Data Flow:**
```
1. User completes payment on NowPayments
2. NowPayments redirects to: static-landing-page?order_id=PGP-XXX
3. Landing page starts polling: GET /api/payment-status?order_id=PGP-XXX
   - Response: {status: "pending"} (IPN not yet received)
4. (In parallel) NowPayments sends IPN → np-webhook
5. np-webhook validates IPN → sets payment_status='confirmed'
6. Next poll: GET /api/payment-status?order_id=PGP-XXX
   - Response: {status: "confirmed"}
7. Landing page auto-redirects to Telegram after 3 seconds
```

**Trade-offs:**

**Advantages:**
- ✅ Faster initial page load (static vs Cloud Run)
- ✅ Better UX with real-time status updates
- ✅ Simpler architecture (no token encryption)
- ✅ Easier debugging (check payment_status column)
- ✅ Lower costs (Cloud Storage cheaper than Cloud Run)
- ✅ No cold starts delaying user experience

**Disadvantages:**
- ⚠️ Requires client-side JavaScript (not accessible if JS disabled)
- ⚠️ Polling overhead (API calls every 5 seconds)
- ⚠️ Additional database column (payment_status)
- ⚠️ Slight increase in API surface (new endpoint)

**Acceptance Criteria:**
- JavaScript widely supported in modern browsers (>99% coverage)
- Polling overhead acceptable (5-second intervals, max 10 minutes)
- Database storage cost negligible (VARCHAR(20) column)
- API security handled by existing authentication/validation

**Migration Strategy:**
- Phased rollout: Keep GCWebhook1 endpoint active during transition
- TelePay bot updated to use landing page URL
- Old token-based flow deprecated but not removed
- Can revert by changing success_url back to GCWebhook1

**Monitoring:**
- Track landing page load times (Cloud Storage metrics)
- Monitor API polling rate (np-webhook logs)
- Measure time-to-redirect (user-facing latency)
- Alert on high timeout rate (>5% of payments)

**Future Enhancements:**
- Server-Sent Events (SSE) instead of polling (push vs pull)
- WebSocket connection for real-time updates
- Progressive Web App (PWA) for offline support
- Branded landing page with channel preview

**Related Decisions:**
- Session 29: NowPayments order_id format change (pipe separator)
- Session 30: USD-to-USD payment validation strategy

---

### 2025-11-02: Database Query Pattern - JOIN for Multi-Table Data Retrieval

**Decision:** Use explicit JOINs when data spans multiple tables instead of assuming all data exists in a single table

**Context:**
- Token encryption was failing in GCWebhook1 with "required argument is not an integer"
- Root cause: np-webhook was querying wrong column names (`subscription_time` vs `sub_time`)
- Deeper issue: Wallet/payout data stored in different table than subscription data

**Problem:**
```python
# BROKEN (np-webhook original):
cur.execute("""
    SELECT wallet_address, payout_currency, payout_network,
           subscription_time, subscription_price
    FROM private_channel_users_database
    WHERE user_id = %s AND private_channel_id = %s
""")
# Returns None for all fields (columns don't exist in this table)
```

**Database Architecture Discovery:**
- **Table 1:** `private_channel_users_database`
  - Contains: `sub_time`, `sub_price` (subscription info)
  - Does NOT contain: wallet/payout data

- **Table 2:** `main_clients_database`
  - Contains: `client_wallet_address`, `client_payout_currency`, `client_payout_network`
  - Does NOT contain: subscription info

- **JOIN Key:** `private_channel_id = closed_channel_id`

**Solution Implemented:**
```python
# FIXED (np-webhook with JOIN):
cur.execute("""
    SELECT
        c.client_wallet_address,
        c.client_payout_currency::text,
        c.client_payout_network::text,
        u.sub_time,
        u.sub_price
    FROM private_channel_users_database u
    JOIN main_clients_database c ON u.private_channel_id = c.closed_channel_id
    WHERE u.user_id = %s AND u.private_channel_id = %s
    ORDER BY u.id DESC LIMIT 1
""")
```

**Type Safety Added:**
- Convert ENUM types to text: `::text` for currency and network
- Ensure string type: `str(sub_price)` before passing to encryption
- Validate types before encryption in token_manager.py

**Rationale:**
1. **Correctness:** Query actual column names from database schema
2. **Completeness:** JOIN tables to get all required data in one query
3. **Performance:** Single query better than multiple round-trips
4. **Type Safety:** Explicit type conversions prevent runtime errors

**Impact on Services:**
- ✅ np-webhook: Now fetches complete payment data correctly
- ✅ GCWebhook1: Receives valid data for token encryption
- ✅ Token encryption: No longer fails with type errors

**Enforcement:**
- Always verify database schema before writing queries
- Use JOINs when data spans multiple tables
- Add defensive type checking at service boundaries

---

### 2025-11-02: Defensive Type Validation in Token Encryption

**Decision:** Add explicit type validation before binary struct packing operations

**Context:**
- `struct.pack(">H", None)` produces cryptic error: "required argument is not an integer"
- Error occurs deep in token encryption, making debugging difficult
- No validation of input types before binary operations

**Problem:**
```python
# BROKEN (token_manager.py original):
def encrypt_token_for_gcwebhook2(self, user_id, closed_channel_id, subscription_time_days, subscription_price):
    packed_data.extend(struct.pack(">H", subscription_time_days))  # Fails if None!
    price_bytes = subscription_price.encode('utf-8')  # Fails if None!
```

**Solution Implemented:**
```python
# FIXED (token_manager.py with validation):
def encrypt_token_for_gcwebhook2(self, user_id, closed_channel_id, subscription_time_days, subscription_price):
    # Validate input types
    if not isinstance(user_id, int):
        raise ValueError(f"user_id must be integer, got {type(user_id).__name__}: {user_id}")
    if not isinstance(subscription_time_days, int):
        raise ValueError(f"subscription_time_days must be integer, got {type(subscription_time_days).__name__}: {subscription_time_days}")
    if not isinstance(subscription_price, str):
        raise ValueError(f"subscription_price must be string, got {type(subscription_price).__name__}: {subscription_price}")

    # Now safe to use struct.pack
    packed_data.extend(struct.pack(">H", subscription_time_days))
```

**Additional Safeguards in GCWebhook1:**
```python
# Validate before calling token encryption
if not subscription_time_days or not subscription_price:
    print(f"❌ Missing subscription data")
    abort(400, "Missing subscription data from payment")

# Ensure correct types
subscription_time_days = int(subscription_time_days)
subscription_price = str(subscription_price)
```

**Rationale:**
1. **Clear Errors:** "must be integer, got NoneType" vs "required argument is not an integer"
2. **Early Detection:** Fail at service boundary, not deep in encryption
3. **Type Safety:** Explicit isinstance() checks prevent silent coercion
4. **Debugging:** Include actual value and type in error message

**Pattern for Binary Operations:**
- Always validate types before `struct.pack()`, `struct.unpack()`
- Use isinstance() checks, not duck typing
- Raise ValueError with clear type information
- Validate at service boundaries AND in shared libraries

---

### 2025-11-02: Dockerfile Module Copy Pattern Standardization

**Decision:** Enforce explicit `COPY` commands for all local Python modules in Dockerfiles instead of relying on `COPY . .`

**Context:**
- np-webhook service failed to initialize CloudTasks client
- Error: `No module named 'cloudtasks_client'`
- Root cause: Dockerfile missing `COPY cloudtasks_client.py .` command
- File existed in source but wasn't copied into container

**Problem:**
```dockerfile
# BROKEN (np-webhook original):
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .  # Missing cloudtasks_client.py!

# WORKING (GCWebhook1 pattern):
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY cloudtasks_client.py .
COPY database_manager.py .
COPY app.py .
```

**Options Considered:**
1. **Explicit COPY for each file** (CHOSEN)
   - Pros: Clear dependencies, reproducible builds, smaller image size
   - Cons: More verbose, must remember to add new files
   - Pattern: `COPY module.py .` for each module

2. **COPY . . (copy everything)**
   - Pros: Simple, never misses files
   - Cons: Larger images, cache invalidation, unclear dependencies
   - Used by: GCMicroBatchProcessor (acceptable for simple services)

3. **.dockerignore with COPY . .**
   - Pros: Flexible, can exclude unnecessary files
   - Cons: Still unclear what's actually needed

**Decision Rationale:**
- **Explicit is better than implicit** (Python Zen)
- Clear dependency graph visible in Dockerfile
- Easier to audit what's being deployed
- Smaller Docker images (only copy what's needed)
- Better cache utilization (change app.py doesn't invalidate module layers)

**Implementation:**
```dockerfile
# Standard pattern for all services:
FROM python:3.11-slim
WORKDIR /app

# Step 1: Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 2: Copy modules in dependency order
COPY config_manager.py .      # Config (no dependencies)
COPY database_manager.py .    # DB (depends on config)
COPY token_manager.py .       # Token (depends on config)
COPY cloudtasks_client.py .   # CloudTasks (depends on config)
COPY app.py .                 # Main app (depends on all above)

# Step 3: Run
CMD ["python", "app.py"]
```

**Services Verified:**
- ✅ GCWebhook1: Explicit COPY pattern
- ✅ GCSplit1, GCSplit2, GCSplit3: Explicit COPY pattern
- ✅ GCAccumulator, GCBatchProcessor: Explicit COPY pattern
- ✅ GCHostPay1, GCHostPay2, GCHostPay3: Explicit COPY pattern
- ✅ np-webhook: FIXED to explicit COPY pattern
- ✅ GCMicroBatchProcessor: Uses `COPY . .` (acceptable, simple service)

**Enforcement:**
- All new services MUST use explicit COPY pattern
- Document required modules in Dockerfile comments
- Code review checklist: Verify all Python imports have corresponding COPY commands

---

### 2025-11-02: Outcome Amount USD Conversion for Payment Validation

**Decision:** Validate payment using `outcome_amount` converted to USD (actual received) instead of `price_amount` (invoice price)

**Context:**
- Previous fix (Session 30) added `price_amount` validation
- But `price_amount` is the subscription invoice amount, NOT what the host wallet receives
- NowPayments takes fees (~15-20%) before sending crypto to host wallet
- Host receives `outcome_amount` (e.g., 0.00026959 ETH) which is less than invoice
- Need to validate what was ACTUALLY received, not what was invoiced

**Problem Scenario:**
```
User pays: $1.35 subscription (price_amount)
NowPayments processes: Takes 20% fee ($0.27)
Host receives: 0.00026959 ETH (outcome_amount)
Current validation: $1.35 >= $1.28 ✅ PASS
Actual USD value received: 0.00026959 ETH × $4,000 = $1.08
Should validate: $1.08 >= minimum expected
```

**Options Considered:**
1. **Continue using price_amount** - Validate invoice price
   - Pros: Simple, no external dependencies
   - Cons: Doesn't validate actual received amount, can't detect excessive fees

2. **Use outcome_amount with real-time price feed** - Convert crypto to USD
   - Pros: Validates actual received value, fee transparency, accurate
   - Cons: External API dependency, price volatility

3. **Query NowPayments API for conversion** - Use NowPayments own conversion rates
   - Pros: Authoritative source, no third-party dependency
   - Cons: Requires API authentication, rate limits, extra latency

4. **Hybrid approach** - outcome_amount conversion with price_amount fallback
   - Pros: Best accuracy, graceful degradation if API fails
   - Cons: Most complex implementation

**Decision Rationale:**
- **Option 4 selected**: Hybrid with outcome_amount conversion primary, price_amount fallback

**Implementation:**

**Tier 1 (PRIMARY)**: Outcome Amount USD Conversion
```python
# Convert crypto to USD using CoinGecko
outcome_usd = convert_crypto_to_usd(outcome_amount, outcome_currency)
# Example: 0.00026959 ETH × $4,000/ETH = $1.08 USD

# Validate actual received amount
minimum_amount = expected_amount * 0.75  # 75% threshold
if outcome_usd >= minimum_amount:  # $1.08 >= $1.01 ✅
    return True

# Log fee reconciliation
fee_lost = price_amount - outcome_usd  # $1.35 - $1.08 = $0.27
fee_percentage = (fee_lost / price_amount) * 100  # 20%
```

**Tier 2 (FALLBACK)**: Invoice Price Validation
```python
# If price feed fails, fall back to price_amount
if price_amount:
    minimum = expected_amount * 0.95
    if price_amount >= minimum:
        # Log warning: validating invoice, not actual received
        return True
```

**Tier 3 (ERROR)**: No Validation Possible
```python
# Neither outcome conversion nor price_amount available
return False, "Cannot validate payment"
```

**Price Feed Choice:**
- **CoinGecko Free API** selected
  - No authentication required
  - 50 calls/minute (sufficient for our volume)
  - Supports all major cryptocurrencies
  - Reliable and well-maintained

**Validation Threshold:**
```
Subscription Price: $1.35 (100%)
Expected Fees: ~20% = $0.27 (NowPayments 15% + network 5%)
Expected Received: ~80% = $1.08
Tolerance: 5% = $0.07
Minimum: 75% = $1.01
```

**Trade-offs:**
- ✅ Validates actual USD value received (accurate)
- ✅ Fee transparency (logs actual fees)
- ✅ Prevents invitations for underpaid transactions
- ✅ Backward compatible (falls back to price_amount)
- ⚠️ External API dependency (CoinGecko)
- ⚠️ ~50-100ms additional latency per validation
- ⚠️ Price volatility during conversion time (acceptable)

**Alternative Rejected:**
- **NowPayments API**: Requires authentication, rate limits, extra complexity
- **price_amount only**: Doesn't validate actual received amount

**Impact:**
- Payment validation now checks actual wallet balance
- Host protected from excessive fee scenarios
- Fee reconciliation enabled for accounting
- Transparent logging of invoice vs received amounts

**Files Modified:**
- `GCWebhook2-10-26/database_manager.py` (crypto price feed methods, validation logic)
- `GCWebhook2-10-26/requirements.txt` (requests dependency)

**Related Decision:**
- Session 30: price_amount capture (prerequisite for fee reconciliation)

---

### 2025-11-02: NowPayments Payment Validation Strategy (USD-to-USD Comparison)

**Decision:** Use `price_amount` (original USD invoice amount) for payment validation instead of `outcome_amount` (crypto amount after fees)

**Context:**
- GCWebhook2 payment validation was failing for all crypto payments
- Root cause: Comparing crypto amounts directly to USD expectations
  - Example: outcome_amount = 0.00026959 ETH (what merchant receives)
  - Validation: $0.0002696 < $1.08 (80% of $1.35) ❌ FAILS
- NowPayments IPN provides both `price_amount` (USD) and `outcome_amount` (crypto)
- Previous implementation only captured `outcome_amount`, losing USD reference

**Options Considered:**
1. **Capture price_amount from IPN** - Store original USD invoice amount
   - Pros: Clean USD-to-USD comparison, no external dependencies
   - Cons: Requires database schema change, doesn't help old records

2. **Implement crypto-to-USD conversion** - Use real-time price feed
   - Pros: Can validate any crypto payment
   - Cons: Requires external API, price volatility, API failures affect validation

3. **Skip amount validation** - Only check payment_status = "finished"
   - Pros: Simple, no changes needed
   - Cons: Risk of fraud, can't detect underpayment

4. **Hybrid approach** - Use price_amount when available, fallback to stablecoin or price feed
   - Pros: Best of all worlds, backward compatible
   - Cons: More complex logic

**Decision Rationale:**
- **Option 4 selected**: Hybrid 3-tier validation strategy

**Implementation:**
1. **Tier 1 (PRIMARY)**: USD-to-USD validation using `price_amount`
   - Tolerance: 95% (allows 5% for rounding/fees)
   - When: price_amount available (all new payments)
   - Example: $1.35 >= $1.28 ✅

2. **Tier 2 (FALLBACK)**: Stablecoin validation for old records
   - Detects USDT/USDC/BUSD as USD-equivalent
   - Tolerance: 80% (accounts for NowPayments ~15% fee)
   - When: price_amount not available, outcome in stablecoin
   - Example: $1.15 USDT >= $1.08 ✅

3. **Tier 3 (FUTURE)**: Crypto price feed
   - For non-stablecoin cryptos without price_amount
   - Requires CoinGecko or similar API integration
   - Currently fails validation (manual approval needed)

**Schema Changes:**
- Added 3 columns to `private_channel_users_database`:
  - `nowpayments_price_amount` (DECIMAL) - Original USD amount
  - `nowpayments_price_currency` (VARCHAR) - Original currency
  - `nowpayments_outcome_currency` (VARCHAR) - Crypto currency

**Trade-offs:**
- ✅ Solves immediate problem (crypto payment validation)
- ✅ Backward compatible (doesn't break old records)
- ✅ Future-proof (can add price feed later)
- ⚠️ Old records without price_amount require manual verification for non-stablecoins

**Alternative Rejected:**
- **Real-time price feed only**: Too complex, external dependency, price volatility
- **Skip validation**: Security risk, can't detect underpayment

**Impact:**
- Payment validation success rate: 0% → ~95%+ expected
- User experience: Payment → instant validation → invitation sent
- Fee tracking: Can now reconcile fees using price_amount vs outcome_amount

**Files Modified:**
- `tools/execute_price_amount_migration.py` (NEW)
- `np-webhook-10-26/app.py` (IPN capture)
- `GCWebhook2-10-26/database_manager.py` (validation logic)

---

### 2025-11-02: NowPayments Order ID Format Change (Pipe Separator)

**Decision:** Changed NowPayments order_id format from `PGP-{user_id}{open_channel_id}` to `PGP-{user_id}|{open_channel_id}` using pipe separator

**Context:**
- NowPayments IPN webhooks receiving callbacks but failing to store payment_id in database
- Root cause: Order ID format `PGP-6271402111-1003268562225` loses negative sign
- Telegram channel IDs are ALWAYS negative (e.g., -1003268562225)
- When concatenating with `-`, negative sign becomes separator: `PGP-{user_id}-{abs(channel_id)}`
- Database lookup fails: searches for +1003268562225, finds nothing (actual ID is -1003268562225)

**Options Considered:**
1. **Modify database schema** - Add open_channel_id to private_channel_users_database
   - Pros: Direct lookup without intermediate query
   - Cons: Requires migration, affects all services, breaks existing functionality

2. **Use different separator (|)** - Change order_id format to preserve negative sign
   - Pros: Quick fix, no schema changes, backward compatible
   - Cons: Requires updating both TelePay bot and np-webhook

3. **Store absolute value and add negative** - Assume all channel IDs are negative
   - Pros: Works with existing format
   - Cons: Fragile assumption, doesn't solve root cause

**Decision Rationale:**
- **Option 2 selected**: Change separator to pipe (`|`)
- Safer than database migration (no risk to existing data)
- Faster implementation (2 files vs. full system migration)
- Backward compatible: old format supported during transition
- Pipe separator cannot appear in user IDs or channel IDs (unambiguous)

**Implementation:**
1. TelePay Bot (`start_np_gateway.py:168`):
   - OLD: `order_id = f"PGP-{user_id}{open_channel_id}"`
   - NEW: `order_id = f"PGP-{user_id}|{open_channel_id}"`
   - Added validation: ensure channel_id starts with `-`

2. np-webhook (`app.py`):
   - Created `parse_order_id()` function
   - Detects format: `|` present → new format, else old format
   - Old format fallback: adds negative sign back (`-abs(channel_id)`)
   - Two-step database lookup:
     - Parse order_id → extract user_id, open_channel_id
     - Query main_clients_database → get closed_channel_id
     - Update private_channel_users_database using closed_channel_id

**Impact:**
- ✅ Payment IDs captured correctly from NowPayments
- ✅ Fee reconciliation unblocked
- ✅ Customer support enabled for payment disputes
- ⚠️ Old format orders processed with fallback logic (7-day transition window)

**Trade-offs:**
- Pros: Zero database changes, minimal code changes, immediate fix
- Cons: Two parsing formats to maintain (temporary during transition)

**References:**
- Checklist: `NP_WEBHOOK_FIX_CHECKLIST.md`
- Root cause: `NP_WEBHOOK_403_ROOT_CAUSE_ANALYSIS.md`
- Progress: `NP_WEBHOOK_FIX_CHECKLIST_PROGRESS.md`

---

### 2025-11-02: np-webhook Two-Step Database Lookup

**Decision:** Implemented two-step database lookup in np-webhook to correctly map channel IDs

**Context:**
- Order ID contains `open_channel_id` (public channel)
- Database update targets `private_channel_users_database` using `private_channel_id` (private channel)
- These are DIFFERENT channel IDs for the same Telegram channel group
- Direct lookup impossible without intermediate mapping

**Implementation:**
```python
# Step 1: Parse order_id
user_id, open_channel_id = parse_order_id(order_id)

# Step 2: Look up closed_channel_id from main_clients_database
SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s

# Step 3: Update private_channel_users_database
UPDATE private_channel_users_database
SET nowpayments_payment_id = %s, ...
WHERE user_id = %s AND private_channel_id = %s
```

**Rationale:**
- Database schema correctly normalized: one channel relationship per subscription
- `main_clients_database` holds channel mapping (open → closed)
- `private_channel_users_database` tracks subscription access (user → private channel)
- Two-step lookup respects existing architecture without modifications

**Trade-offs:**
- Pros: Works with existing schema, no migrations, respects normalization
- Cons: Two database queries per IPN (acceptable for low-volume webhook)

---

### 2025-11-02: np-webhook Secret Configuration Fix

**Decision:** Configured np-webhook Cloud Run service with required secrets for IPN processing and database updates

**Context:**
- GCWebhook2 payment validation implementation revealed payment_id always NULL in database
- Investigation showed NowPayments sending IPN callbacks but np-webhook returning 403 Forbidden
- np-webhook service configuration inspection revealed ZERO secrets mounted
- Service couldn't verify IPN signatures or connect to database without secrets
- Critical blocker preventing payment_id capture throughout payment flow

**Problem:**
1. np-webhook deployed without any environment variables or secrets
2. Service receives IPN POST from NowPayments with payment metadata
3. Without NOWPAYMENTS_IPN_SECRET, can't verify callback signature → rejects with 403
4. Without database credentials, can't write payment_id even if signature verified
5. NowPayments retries IPN callbacks but eventually gives up
6. Database never populated with payment_id from successful payments
7. Downstream services (GCWebhook1, GCWebhook2, GCAccumulator) all working correctly but no data to process

**Implementation:**
1. **Mounted 5 Required Secrets:**
   ```bash
   gcloud run services update np-webhook --region=us-east1 \
     --update-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,\
   CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
   DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
   DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
   DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest
   ```

2. **Deployed New Revision:**
   - Created revision: `np-webhook-00004-kpk`
   - Routed 100% traffic to new revision
   - Old revision (00003-r27) with no secrets deprecated

3. **Secrets Mounted:**
   - **NOWPAYMENTS_IPN_SECRET**: IPN callback signature verification
   - **CLOUD_SQL_CONNECTION_NAME**: PostgreSQL connection string
   - **DATABASE_NAME_SECRET**: Database name (telepaydb)
   - **DATABASE_USER_SECRET**: Database user (postgres)
   - **DATABASE_PASSWORD_SECRET**: Database authentication

4. **Verification:**
   - Inspected service description → all 5 secrets present as environment variables
   - IAM permissions already correct (service account has secretAccessor role)
   - Service health check returns 405 for GET (expected - only accepts POST)

**Rationale:**
- **Critical Path**: np-webhook is the only service that receives payment_id from NowPayments
- **Single Point of Failure**: Without np-webhook processing IPNs, payment_id never enters system
- **Graceful Degradation**: System worked without payment_id but lacked fee reconciliation capability
- **Security First**: IPN signature verification prevents forged payment confirmations
- **Database Integration**: Must connect to database to update payment metadata

**Alternatives Considered:**
1. **Query NowPayments API directly in GCWebhook1:** Rejected - inefficient, rate limits, IPN already available
2. **Store payment_id in token payload:** Rejected - payment_id not available when token created (race condition)
3. **Use different service for IPN handling:** Rejected - np-webhook already exists and deployed
4. **Make payment_id optional permanently:** Rejected - defeats purpose of fee reconciliation implementation

**Trade-offs:**
- **Pro**: Enables complete payment_id flow from NowPayments through entire system
- **Pro**: Fixes 100% of payment validation failures in GCWebhook2
- **Pro**: Minimal code changes (configuration only, no code deployment)
- **Pro**: Immediate effect - next IPN callback will succeed
- **Con**: Requires retest of entire payment flow to verify
- **Con**: Historical payments missing payment_id (can backfill if needed)

**Impact:**
- ✅ np-webhook can now process IPN callbacks from NowPayments
- ✅ Database will be updated with payment_id for new payments
- ✅ GCWebhook2 payment validation will succeed instead of retry loop
- ✅ Telegram invitations will be sent immediately after payment
- ✅ Fee reconciliation data now captured for all future payments
- ⏳ Requires payment test to verify end-to-end flow working

**Files Modified:**
- np-webhook Cloud Run service configuration (5 secrets added)

**Files Created:**
- `/NP_WEBHOOK_403_ROOT_CAUSE_ANALYSIS.md` (investigation details)
- `/NP_WEBHOOK_FIX_SUMMARY.md` (fix summary and verification)

**Status:** ✅ Deployed - Awaiting payment test for verification

---

### 2025-11-02: GCWebhook2 Payment Validation Security Fix

**Decision:** Added payment validation to GCWebhook2 service to verify payment completion before sending Telegram invitations

**Context:**
- Security review revealed GCWebhook2 was sending Telegram invitations without payment verification
- Service blindly trusted encrypted tokens from GCWebhook1
- No check for NowPayments IPN callback or payment_id existence
- Race condition could allow unauthorized access if payment failed after token generation
- Critical security vulnerability in payment flow

**Problem:**
1. GCWebhook1 creates encrypted token and enqueues GCWebhook2 task immediately after creating subscription record
2. GCWebhook2 receives token and sends Telegram invitation without checking payment status
3. If NowPayments IPN callback is delayed or payment fails, user gets invitation without paying
4. No validation of payment_id, payment_status, or payment amount

**Implementation:**
1. **New Database Manager:**
   - Created `database_manager.py` with Cloud SQL Connector integration
   - `get_nowpayments_data()`: Queries payment_id, status, address, outcome_amount
   - `validate_payment_complete()`: Validates payment against business rules
   - Returns tuple of (is_valid: bool, error_message: str)

2. **Payment Validation Rules:**
   - Check payment_id exists (populated by np-webhook IPN callback)
   - Verify payment_status = 'finished'
   - Validate outcome_amount >= 80% of expected price (accounts for 15% NowPayments fee + 5% tolerance)

3. **Cloud Tasks Retry Logic:**
   - Return 503 if IPN callback not yet processed → Cloud Tasks retries after 60s
   - Return 400 if payment invalid (wrong amount, failed status) → Cloud Tasks stops retrying
   - Return 200 only after payment validation succeeds

4. **Configuration Updates:**
   - Added database credential fetching to `config_manager.py`
   - Fetches CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME_SECRET, DATABASE_USER_SECRET, DATABASE_PASSWORD_SECRET
   - Updated `requirements.txt` with cloud-sql-python-connector and pg8000
   - Fixed Dockerfile to include database_manager.py

**Rationale:**
- **Security:** Prevents unauthorized Telegram access without payment confirmation
- **Trust Model:** Zero-trust approach - validate payment even with signed tokens
- **Race Condition Fix:** Handles IPN delays gracefully with retry logic
- **Business Logic:** Validates payment amount to prevent underpayment fraud
- **Reliability:** Cloud Tasks retry ensures eventual consistency when IPN delayed

**Alternatives Considered:**
1. **Skip validation, trust GCWebhook1 token:** Rejected - security vulnerability
2. **Validate in GCWebhook1 before enqueueing:** Rejected - still has race condition
3. **Poll NowPayments API directly:** Rejected - inefficient, rate limits, already have IPN data
4. **Add payment_id to token payload:** Rejected - token created before payment_id available

**Trade-offs:**
- **Performance:** Additional database query per invitation (~50ms latency)
- **Complexity:** Requires database credentials in GCWebhook2 service
- **Dependencies:** Adds Cloud SQL Connector dependency to service
- **Benefit:** Eliminates critical security vulnerability, worth the cost

**Impact:**
- GCWebhook2 now validates payment before sending invitations
- Service health check includes database_manager status
- Payment validation logs provide audit trail
- Cloud Tasks retry logic handles IPN delays automatically

**Files Modified:**
- `/GCWebhook2-10-26/database_manager.py` (NEW)
- `/GCWebhook2-10-26/tph2-10-26.py` (payment validation added)
- `/GCWebhook2-10-26/config_manager.py` (database credentials)
- `/GCWebhook2-10-26/requirements.txt` (dependencies)
- `/GCWebhook2-10-26/Dockerfile` (copy database_manager.py)

**Status:** ✅ Implemented and deployed (gcwebhook2-10-26-00011-w2t)

---

### 2025-11-02: TelePay Bot - Secret Manager Integration for IPN Callback URL

**Decision:** Modified TelePay bot to fetch IPN callback URL from Google Cloud Secret Manager instead of directly from environment variables

**Context:**
- Phase 3 of payment_id implementation originally used direct environment variable lookup
- Inconsistent with existing secret management pattern for `PAYMENT_PROVIDER_TOKEN`
- Environment variables storing sensitive URLs less secure than Secret Manager
- Needed centralized secret management across all services

**Implementation:**
1. **New Method Added:**
   - `fetch_ipn_callback_url()` method follows same pattern as `fetch_payment_provider_token()`
   - Fetches from Secret Manager using path from `NOWPAYMENTS_IPN_CALLBACK_URL` env var
   - Returns IPN URL or None if not configured

2. **Initialization Pattern:**
   - `__init__()` now calls `fetch_ipn_callback_url()` on startup
   - Stores IPN URL in `self.ipn_callback_url` instance variable
   - Can be overridden via constructor parameter for testing

3. **Invoice Creation:**
   - `create_payment_invoice()` uses `self.ipn_callback_url` instead of `os.getenv()`
   - Single fetch on initialization, not on every invoice creation
   - Better performance and consistent behavior

**Rationale:**
- **Security:** Secrets stored in Secret Manager with IAM controls, audit logging, versioning
- **Consistency:** Matches existing pattern for all other secrets in codebase
- **Maintainability:** Single source of truth for IPN URL configuration
- **Flexibility:** Environment variable only needs secret path, not the actual URL
- **Observability:** Better logging at fetch time vs. usage time

**Trade-offs:**
- Environment variable now stores secret path instead of actual URL
- Secret Manager API call on bot startup (minimal latency ~50-100ms)
- Must restart bot to pick up secret changes (acceptable for infrequent changes)

**Impact:**
- ✅ More secure secret management
- ✅ Consistent with codebase patterns
- ✅ Better error handling and logging
- ✅ Zero impact on invoice creation performance

**Configuration Required:**
```bash
# Old way (Phase 3 - Direct URL):
export NOWPAYMENTS_IPN_CALLBACK_URL="https://np-webhook-291176869049.us-east1.run.app"

# New way (Session 26 - Secret Manager path):
export NOWPAYMENTS_IPN_CALLBACK_URL="projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest"
```

---

### 2025-11-02: NowPayments Payment ID Storage Architecture

**Decision:** Implemented payment_id storage and propagation through the payment flow to enable fee discrepancy resolution

**Context:**
- Fee discrepancies discovered between NowPayments charges and actual blockchain transactions
- Cannot reconcile fees without linking NowPayments payment_id to our database records
- Need to track actual fees paid vs. estimated fees for accurate accounting

**Implementation:**
1. **Database Layer:**
   - Added 10 NowPayments columns to `private_channel_users_database` (payment_id, invoice_id, order_id, pay_address, payment_status, pay_amount, pay_currency, outcome_amount, created_at, updated_at)
   - Added 5 NowPayments columns to `payout_accumulation` (payment_id, pay_address, outcome_amount, network_fee, payment_fee_usd)
   - Created indexes on payment_id and order_id for fast lookups

2. **Service Integration:**
   - Leveraged existing `np-webhook` service for IPN handling
   - Updated GCWebhook1 to query payment_id after database write and pass to GCAccumulator
   - Updated GCAccumulator to store payment_id in payout_accumulation records
   - Added NOWPAYMENTS_IPN_SECRET and NOWPAYMENTS_IPN_CALLBACK_URL to Secret Manager

3. **TelePay Bot Updates (Phase 3):**
   - Updated `start_np_gateway.py` to include `ipn_callback_url` in NowPayments invoice creation
   - Bot now passes IPN endpoint to NowPayments: `https://np-webhook-291176869049.us-east1.run.app`
   - Added logging to track invoice_id, order_id, and IPN callback URL for debugging
   - Environment variable `NOWPAYMENTS_IPN_CALLBACK_URL` must be set before bot starts

4. **Data Flow:**
   - TelePay bot creates invoice with `ipn_callback_url` specified
   - Customer pays → NowPayments sends IPN to np-webhook
   - NowPayments IPN → np-webhook → updates `private_channel_users_database` with payment_id
   - NowPayments success_url → GCWebhook1 → queries payment_id → passes to GCAccumulator
   - GCAccumulator → stores payment_id in `payout_accumulation`

**Rationale:**
- Minimal changes to existing architecture (reused np-webhook service)
- payment_id propagates through entire payment flow automatically
- Enables future fee reconciliation tools via NowPayments API queries
- Database indexes ensure fast lookups even with large datasets

**Trade-offs:**
- Relies on np-webhook IPN arriving before success_url (usually true, but not guaranteed)
- If IPN delayed, payment_id will be NULL initially but can be backfilled
- Additional database storage for NowPayments metadata (~300 bytes per payment)

**Impact:**
- Zero downtime migration (additive schema changes)
- Backward compatible (payment_id fields are optional)
- Foundation for accurate fee tracking and discrepancy resolution

---

### 2025-11-02: Micro-Batch Processor Schedule Optimization

**Decision:** Reduced micro-batch-conversion-job scheduler interval from 15 minutes to 5 minutes

**Rationale:**
- Faster threshold detection for accumulated payments
- Improved payout latency for users (3x faster threshold checks)
- Aligns with batch-processor-job interval (also 5 minutes)
- No functional changes to service logic - only scheduling frequency

**Impact:**
- Threshold checks now occur every 5 minutes instead of 15 minutes
- Maximum wait time for threshold detection reduced from 15 min to 5 min
- Expected payout completion time reduced by up to 10 minutes
- Minimal increase in Cloud Scheduler API calls (cost negligible)

**Configuration:**
```
Schedule: */5 * * * * (Etc/UTC)
Target: https://gcmicrobatchprocessor-10-26-291176869049.us-central1.run.app/check-threshold
State: ENABLED
```

---

## Notes
- All previous architectural decisions have been archived to DECISIONS_ARCH.md
- This file tracks only the most recent architectural decisions
- Add new decisions at the TOP of the document
