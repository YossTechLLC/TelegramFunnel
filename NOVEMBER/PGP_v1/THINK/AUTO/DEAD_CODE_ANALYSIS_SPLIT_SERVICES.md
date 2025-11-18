# Dead Code & Redundancy Analysis: PGP_SPLIT Services
**Analysis Date:** 2025-11-18
**Services Reviewed:** PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_SPLIT3_v1
**Focus:** Dead code, redundant functions, inconsistencies, and optimization opportunities

---

## Executive Summary

### Critical Findings
1. **Token Manager Duplication:** All three services contain nearly identical token manager code with inconsistent implementations
2. **Unused Endpoint:** PGP_SPLIT3_v1 has `/eth-to-usdt` endpoint that appears incomplete/unused
3. **Hot-Reload Inconsistency:** PGP_SPLIT2_v1 has hot-reload but PGP_SPLIT3_v1 does not
4. **Token Format Mismatch:** PGP_SPLIT2_v1 and PGP_SPLIT3_v1 token managers are **out of sync** with PGP_SPLIT1_v1

---

## 1. PGP_SPLIT1_v1 Analysis

### ✅ Core Functionality (KEEP)
- **4 Endpoints:** All active and necessary
  - `POST /` - Initial webhook from PGP_ORCHESTRATOR_v1
  - `POST /usdt-eth-estimate` - Receives estimate from PGP_SPLIT2_v1
  - `POST /eth-client-swap` - Receives swap result from PGP_SPLIT3_v1
  - `POST /batch-payout` - Batch payout from PGP_BATCHPROCESSOR
  - `GET /health` - Health check

### ⚠️ Functions That May Be Redundant

#### **Function:** `verify_webhook_signature()` (Lines 66-92)
- **Location:** `pgp_split1_v1.py:66-92`
- **Issue:** Similar signature verification in `PGP_COMMON/auth/service_auth.py`
- **Recommendation:** Consider using shared implementation
- **Priority:** Low (working code, but duplication)

#### **Function:** `calculate_adjusted_amount()` (Lines 95-122)
- **Status:** ✅ **KEEP** - Used in line 360 for threshold payout mode
- **Note:** Only calculates fee for threshold (USDT), instant mode uses direct calculation

#### **Function:** `calculate_pure_market_conversion()` (Lines 199-255)
- **Status:** ✅ **KEEP** - Used in line 491 to calculate pure market value
- **Purpose:** Back-calculates market rate from ChangeNow fee-inclusive estimates
- **Critical:** Ensures accurate market value storage in `split_payout_request`

#### **Function:** `build_hostpay_token()` (Lines 125-196)
- **Status:** ✅ **KEEP** - Used in line 783 to build token for PGP_HOSTPAY1_v1
- **Note:** Uses **actual_eth_amount** for payment, **estimated_eth_amount** for comparison

### 🔴 Dead Code - Variables

#### **Variable:** `to_amount_post_fee` naming inconsistency
- **Location:** Lines 476, 492
- **Issue:** Variable extracted as `to_amount_post_fee` but docs say `toAmount`
- **Status:** ✅ **FIXED** in current code (correct key name)
- **Action:** None needed

### 🟡 Potential Issues

#### **Database Idempotency Check**
- **Location:** Lines 704-727
- **Status:** ✅ **KEEP** - Critical for Cloud Tasks retry protection
- **Purpose:** Prevents duplicate `split_payout_que` insertions during retries
- **Note:** Excellent defensive programming

---

## 2. PGP_SPLIT2_v1 Analysis

### ✅ Core Functionality (KEEP)
- **2 Endpoints:** Both active
  - `POST /` - Processes USDT→ETH estimate requests
  - `GET /health` - Health check

### 🔴 Dead Code - Token Manager

**CRITICAL ISSUE:** PGP_SPLIT2_v1's `token_manager.py` is **OUT OF SYNC** with PGP_SPLIT1_v1

#### **Missing Methods in PGP_SPLIT2_v1:**
1. ❌ No `encrypt_pgp_split1_to_pgp_split3_token()` - **NOT NEEDED** (correct)
2. ❌ No `decrypt_pgp_split1_to_pgp_split3_token()` - **NOT NEEDED** (correct)
3. ❌ No `encrypt_pgp_split3_to_pgp_split1_token()` - **NOT NEEDED** (correct)
4. ❌ No `decrypt_pgp_split3_to_pgp_split1_token()` - **NOT NEEDED** (correct)

#### **OLD Token Format in PGP_SPLIT2_v1:**
The token manager in PGP_SPLIT2_v1 does **NOT** include these fields that PGP_SPLIT1_v1 expects:
- ❌ `swap_currency` (line 112 in SPLIT1 token manager)
- ❌ `payout_mode` (line 113 in SPLIT1 token manager)
- ❌ `actual_eth_amount` (line 111 in SPLIT1 token manager)

**Impact:**
- Token decryption in PGP_SPLIT2_v1 will fail when receiving tokens from PGP_SPLIT1_v1
- Backward compatibility exists but **new fields are not being transmitted**

**Recommendation:**
```diff
🔧 UPDATE PGP_SPLIT2_v1/token_manager.py to match PGP_SPLIT1_v1/token_manager.py
```

### 🟢 Hot-Reload Implementation
- **Status:** ✅ **EXCELLENT** - PGP_SPLIT2_v1 has hot-reload for `CHANGENOW_API_KEY`
- **Location:** `changenow_client.py:20-35, 94-102`
- **Note:** Uses `config_manager.get_changenow_api_key()` dynamically

---

## 3. PGP_SPLIT3_v1 Analysis

### ✅ Core Functionality (KEEP)
- **3 Endpoints:**
  - `POST /` - Processes ETH→ClientCurrency swap requests ✅ ACTIVE
  - `POST /eth-to-usdt` - Creates ETH→USDT swaps ⚠️ **QUESTIONABLE**
  - `GET /health` - Health check ✅ ACTIVE

### 🔴 Dead Code - Unused Endpoint

#### **Endpoint:** `POST /eth-to-usdt` (Lines 238-382)
- **Purpose:** Create ETH→USDT swaps for threshold payout accumulation
- **Issue:** **NO CALLER IDENTIFIED**
  - Claims to be called by "PGP_ACCUMULATOR"
  - No `PGP_ACCUMULATOR` service exists in codebase
  - Token methods reference accumulator but service is missing

**Evidence of Dead Code:**
```python
# Lines 276-279 - References non-existent service
decrypted_data = token_manager.decrypt_accumulator_to_pgp_split3_token(encrypted_token)

# Lines 354-357 - Sends to non-existent queue
task_name = cloudtasks_client.enqueue_accumulator_swap_response(
    queue_name=pgp_accumulator_response_queue,
    target_url=f"{pgp_accumulator_url}/swap-created",
```

**Recommendation:**
```diff
❓ INVESTIGATE: Is PGP_ACCUMULATOR planned or abandoned?
   - If planned → Document as TODO
   - If abandoned → DELETE lines 238-382 and accumulator token methods
```

### 🔴 Dead Code - Token Manager

**CRITICAL ISSUE:** PGP_SPLIT3_v1's `token_manager.py` is **SEVERELY OUT OF SYNC**

#### **Missing/Outdated in PGP_SPLIT3_v1:**

**1. OLD encrypt_pgp_split1_to_pgp_split2_token() (Lines 56-125)**
- ❌ Still has `adjusted_amount_usdt` parameter (should be `adjusted_amount`)
- ❌ Missing `swap_currency` parameter
- ❌ Missing `payout_mode` parameter
- ❌ Missing `actual_eth_amount` parameter
- **Status:** 🚨 **WRONG SERVICE** - This method should NOT exist in SPLIT3

**2. OLD decrypt_pgp_split1_to_pgp_split2_token() (Lines 127-203)**
- **Status:** 🚨 **WRONG SERVICE** - This method should NOT exist in SPLIT3

**3. OLD encrypt_pgp_split2_to_pgp_split1_token() (Lines 205-265)**
- **Status:** 🚨 **WRONG SERVICE** - This method should NOT exist in SPLIT3

**4. OLD decrypt_pgp_split2_to_pgp_split1_token() (Lines 267-336)**
- **Status:** 🚨 **WRONG SERVICE** - This method should NOT exist in SPLIT3

**5. `decrypt_pgp_split1_to_pgp_split3_token()` (Lines 398-507)**
- ✅ Has backward compatibility for `swap_currency`, `payout_mode`, `actual_eth_amount`
- ⚠️ But checks are defensive - PGP_SPLIT1_v1 SHOULD be sending these fields
- **Status:** GOOD but relies on sender having correct token format

**6. `encrypt_pgp_split3_to_pgp_split1_token()` (Lines 509-587)**
- ✅ Correctly includes `actual_eth_amount` (line 567)
- ✅ Logs it properly (line 546)
- **Status:** GOOD

**7. `decrypt_pgp_split3_to_pgp_split1_token()` (Lines 589-687)**
- ✅ Has backward compatibility for `actual_eth_amount`
- **Status:** GOOD

**Recommendation:**
```diff
🔧 DELETE methods 1-4 from PGP_SPLIT3_v1/token_manager.py (Lines 56-336)
   These belong to SPLIT2, not SPLIT3 - likely copy-paste error
```

### 🟡 Missing Hot-Reload

#### **Issue:** PGP_SPLIT3_v1 does NOT have hot-reload for `CHANGENOW_API_KEY`
- **Location:** `changenow_client.py:17-34`
- **Current:** API key stored in `__init__()` and never refreshed
- **Compare:** PGP_SPLIT2_v1 has `config_manager.get_changenow_api_key()` on each request

**Recommendation:**
```diff
🔧 ADD hot-reload to PGP_SPLIT3_v1/changenow_client.py
   - Pass config_manager instead of api_key
   - Fetch API key dynamically before each ChangeNow request
   - Mirror PGP_SPLIT2_v1 implementation
```

---

## 4. Cross-Service Token Manager Redundancy

### 🔴 Massive Code Duplication

**All three services have nearly identical token manager implementations**

#### **Duplicated Code:**
- `pack_string()` / `unpack_string()` - **Identical across all 3**
- Signature verification logic - **Identical across all 3**
- Base64 encoding/decoding - **Identical across all 3**
- Timestamp validation - **Identical across all 3**

#### **Current State:**
```
PGP_SPLIT1_v1/token_manager.py: 855 lines
PGP_SPLIT2_v1/token_manager.py: 706 lines
PGP_SPLIT3_v1/token_manager.py: 834 lines
```

**~2400 lines of mostly duplicated code**

### ✅ Solution: PGP_COMMON/tokens.py

**Good news:** `BaseTokenManager` already exists!
- **Location:** `PGP_COMMON/tokens/base_token_manager.py`
- **Provides:** Common encryption/decryption methods

**Current Implementation Status:**
- ✅ PGP_SPLIT1_v1 inherits from `BaseTokenManager`
- ✅ PGP_SPLIT2_v1 inherits from `BaseTokenManager`
- ✅ PGP_SPLIT3_v1 inherits from `BaseTokenManager`

**BUT:** Each service still duplicates specific token methods

**Recommendation:**
```diff
🔧 REFACTOR token managers to use composition over duplication
   Option 1: Move specific token methods to PGP_COMMON
   Option 2: Use mixin classes for shared token patterns
   Option 3: Document that duplication is intentional for service isolation
```

---

## 5. ChangeNow Client Duplication

### 🔴 Nearly Identical Implementations

**PGP_SPLIT2_v1/changenow_client.py:**
- 179 lines
- Method: `get_estimated_amount_v2_with_retry()`
- Has hot-reload via `config_manager`

**PGP_SPLIT3_v1/changenow_client.py:**
- 180 lines
- Method: `create_fixed_rate_transaction_with_retry()`
- NO hot-reload (stores `api_key` in `__init__`)

### ⚠️ Retry Logic Duplication

**Both files have IDENTICAL infinite retry logic:**
- 60-second backoff
- Same error handling (429, 5xx, timeout, connection)
- Same logging patterns

**Recommendation:**
```diff
🔧 CONSOLIDATE ChangeNow clients
   Option 1: Move to PGP_COMMON/changenow_client.py with both methods
   Option 2: Accept that each service owns its client (current architecture)

   IF consolidating → Add hot-reload to SPLIT3's client
```

---

## 6. Summary of Actions

### 🔴 CRITICAL - Fix Immediately

| Issue | Service | Action | Priority |
|-------|---------|--------|----------|
| Token format mismatch | PGP_SPLIT2_v1 | Update token_manager.py to match SPLIT1 | **HIGH** |
| Wrong token methods | PGP_SPLIT3_v1 | Delete SPLIT2 methods (lines 56-336) | **HIGH** |
| Dead endpoint | PGP_SPLIT3_v1 | Investigate PGP_ACCUMULATOR or delete `/eth-to-usdt` | **MEDIUM** |

### 🟡 MEDIUM - Improve Quality

| Issue | Service | Action | Priority |
|-------|---------|--------|----------|
| Missing hot-reload | PGP_SPLIT3_v1 | Add hot-reload for CHANGENOW_API_KEY | **MEDIUM** |
| Code duplication | All 3 | Consider consolidating token managers | **LOW** |
| Code duplication | SPLIT2/SPLIT3 | Consider consolidating ChangeNow clients | **LOW** |

### 🟢 LOW - Nice to Have

| Issue | Service | Action | Priority |
|-------|---------|--------|----------|
| Signature verification | PGP_SPLIT1_v1 | Use shared PGP_COMMON implementation | **LOW** |

---

## 7. Detailed Breakdown by File

### PGP_SPLIT1_v1

| File | Lines | Dead Code? | Redundant? | Notes |
|------|-------|------------|------------|-------|
| pgp_split1_v1.py | 1029 | ❌ No | ⚠️ Minor | verify_webhook_signature could use shared impl |
| database_manager.py | 394 | ❌ No | ❌ No | Clean, well-implemented |
| token_manager.py | 855 | ❌ No | ⚠️ Yes | Duplicates base methods |
| cloudtasks_client.py | - | - | - | Not analyzed yet |
| config_manager.py | - | - | - | Not analyzed yet |

### PGP_SPLIT2_v1

| File | Lines | Dead Code? | Redundant? | Notes |
|------|-------|------------|------------|-------|
| pgp_split2_v1.py | 254 | ❌ No | ❌ No | Clean implementation |
| changenow_client.py | 179 | ❌ No | ⚠️ Yes | Retry logic duplicated in SPLIT3 |
| token_manager.py | 706 | ❌ No | 🔴 **OUT OF SYNC** | Missing swap_currency, payout_mode, actual_eth_amount |
| cloudtasks_client.py | - | - | - | Not analyzed yet |
| config_manager.py | - | - | - | Not analyzed yet |

### PGP_SPLIT3_v1

| File | Lines | Dead Code? | Redundant? | Notes |
|------|-------|------------|------------|-------|
| pgp_split3_v1.py | 420 | 🔴 **YES** | ❌ No | `/eth-to-usdt` endpoint (lines 238-382) unused |
| changenow_client.py | 180 | ❌ No | ⚠️ Yes | Retry logic duplicated from SPLIT2 |
| token_manager.py | 834 | 🔴 **YES** | 🔴 **YES** | Has SPLIT2 methods (lines 56-336) - WRONG SERVICE |
| cloudtasks_client.py | - | - | - | Not analyzed yet |
| config_manager.py | - | - | - | Not analyzed yet |

---

## 8. Architectural Questions

### Q1: Is PGP_ACCUMULATOR planned or abandoned?
- **Evidence:** PGP_SPLIT3_v1 has endpoint + token methods for it
- **Issue:** Service doesn't exist in codebase
- **Action:** Clarify with stakeholders

### Q2: Should services share token managers via PGP_COMMON?
- **Pro:** Eliminates duplication, ensures consistency
- **Con:** Couples services, reduces autonomy
- **Current:** Inheritance from `BaseTokenManager` but duplicates specific methods

### Q3: Why does SPLIT2 have hot-reload but SPLIT3 doesn't?
- **Impact:** SPLIT3 requires redeploy to update API key
- **Fix:** Add hot-reload to SPLIT3 (simple change)

---

## 9. Testing Recommendations

### Before Fixing Token Managers
1. **Integration Test:** PGP_SPLIT1_v1 → PGP_SPLIT2_v1 token flow
2. **Integration Test:** PGP_SPLIT1_v1 → PGP_SPLIT3_v1 token flow
3. **Unit Test:** Token encryption/decryption with new fields

### After Fixes
1. **Regression Test:** Ensure backward compatibility works
2. **End-to-End Test:** Full payment split workflow (instant mode)
3. **End-to-End Test:** Full payment split workflow (threshold mode)

---

## 10. Conclusion

### Immediate Priorities

1. **Fix PGP_SPLIT2_v1 token manager** (token format mismatch with SPLIT1)
2. **Delete dead code in PGP_SPLIT3_v1** (SPLIT2 methods + possibly `/eth-to-usdt`)
3. **Add hot-reload to PGP_SPLIT3_v1** (consistency with SPLIT2)

### Long-term Considerations

1. **Decide on PGP_ACCUMULATOR** (build it or remove references)
2. **Consider consolidating** ChangeNow clients to PGP_COMMON
3. **Document** whether token manager duplication is intentional design

### Metrics

- **Dead Code Found:** ~650 lines (SPLIT3 token manager + endpoint)
- **Redundant Code:** ~2400 lines (token managers across 3 services)
- **Critical Issues:** 2 (token format mismatch, wrong methods in SPLIT3)
- **Code Quality:** Generally high, but synchronization issues present

---

**Next Steps:** Review this analysis and decide on remediation strategy before making changes.
