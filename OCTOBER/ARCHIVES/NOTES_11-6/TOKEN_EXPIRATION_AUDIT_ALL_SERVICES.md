# Token Expiration Audit - All Services
**Date**: 2025-11-03
**Purpose**: Comprehensive audit of all token_manager.py files to identify which services need token expiration window updates

---

## Executive Summary

This audit examines token expiration windows across all 11 services in the /10-26 architecture to identify which services require updates from **5-minute (300s) windows to 30-minute (1800s) windows** to accommodate asynchronous workflow delays.

### Key Findings:
- **1 service already fixed** ✅ (GCMicroBatchProcessor-10-26)
- **4 services require updates** ⚠️ (GCHostPay2, GCHostPay1 [partial], GCAccumulator, GCSplit3 [partial])
- **6 services already have adequate windows** ✓ (GCHostPay3, GCWebhook1, GCWebhook2, GCSplit1, GCSplit2, GCBatchProcessor)

---

## Detailed Service Breakdown

### 🔴 Services Requiring 30-Minute Window Update

#### 1. **GCHostPay2-10-26** ⚠️ CRITICAL
**Current Status**: 5-minute (300s) window
**Instances**: 5 token validation methods
**Recommendation**: Update ALL instances to 1800s (30 minutes)

**Token Validation Methods & Line Numbers:**
| Method | Line | Current Window | Required Window |
|--------|------|----------------|-----------------|
| `decrypt_gcsplit2_to_gchostpay2_single_token()` | 187 | 300s (5m) | 1800s (30m) |
| `decrypt_gchostpay2_to_gcsplit2_single_response_token()` | 340 | 300s (5m) | 1800s (30m) |
| `decrypt_gcsplit2_to_gchostpay2_batch_token()` | 498 | 300s (5m) | 1800s (30m) |
| `decrypt_gchostpay2_to_gcsplit2_batch_response_token()` | 639 | 300s (5m) | 1800s (30m) |
| `decrypt_threshold_check_token()` | 782 | 300s (5m) | 1800s (30m) |

**Rationale**: GCHostPay2 processes ChangeNow swaps with retry mechanisms similar to GCHostPay1. The 5-minute window is insufficient for:
- ChangeNow swap processing: 5-30 minutes
- Retry delays: Up to 15 minutes (3 retries × 5 minutes)
- Cloud Tasks queue delays: 30s-5 minutes
- **Total workflow delay: 15-20 minutes**

---

#### 2. **GCHostPay1-10-26** ⚠️ PARTIAL UPDATE NEEDED
**Current Status**: Mixed (mostly 7200s, one 300s)
**Instances**: 1 token validation method needs update
**Recommendation**: Update ONLY `decrypt_microbatch_response_token()` to 1800s (30 minutes)

**Token Validation Methods & Line Numbers:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decrypt_gcsplit2_to_gchostpay1_single_token()` | 226 | 7200s (2h) | ✓ OK |
| `decrypt_gchostpay1_to_gcsplit2_single_response_token()` | 332 | 7200s (2h) | ✓ OK |
| `decrypt_gcsplit2_to_gchostpay1_batch_token()` | 488 | 7200s (2h) | ✓ OK |
| `decrypt_gchostpay1_to_gcsplit2_batch_response_token()` | 646 | 7200s (2h) | ✓ OK |
| `decrypt_threshold_check_token()` | 794 | 7200s (2h) | ✓ OK |
| `decrypt_gcaccumulator_to_gchostpay1_token()` | 940 | 7200s (2h) | ✓ OK |
| **`decrypt_microbatch_response_token()`** | **1043** | **300s (5m)** | **⚠️ UPDATE NEEDED** |

**Rationale**: The `decrypt_microbatch_response_token()` method receives callbacks from GCMicroBatchProcessor after batch conversion completion. This is the reverse flow from the bug we just fixed. While GCMicroBatchProcessor now accepts 30-minute tokens, GCHostPay1 should also accept 30-minute tokens for consistency and to handle potential delays in the reverse callback flow.

**Comment at line 1041**: *"Validate timestamp (5-minute window: current_time - 300 to current_time + 5)"*

---

#### 3. **GCAccumulator-10-26** ⚠️ CRITICAL
**Current Status**: 5-minute (300s) window
**Instances**: 2 token validation methods
**Recommendation**: Update ALL instances to 1800s (30 minutes)

**Token Validation Methods & Line Numbers:**
| Method | Line | Current Window | Required Window |
|--------|------|----------------|-----------------|
| `decrypt_gcsplit3_to_accumulator_token()` | 269 | 300s (5m) | 1800s (30m) |
| `decrypt_gchostpay1_to_accumulator_token()` | 440 | 300s (5m) | 1800s (30m) |

**Rationale**: GCAccumulator receives tokens from:
1. **GCSplit3** - After individual payout completion (includes ChangeNow delays)
2. **GCHostPay1** - After batch conversion completion (includes ChangeNow retry delays)

Both flows can experience delays of 15-20 minutes due to:
- ChangeNow processing times
- Retry mechanisms (up to 15 minutes)
- Cloud Tasks queue delays

**Comments at lines 267, 438**: *"Validate timestamp (5 minutes = 300 seconds)"*

---

#### 4. **GCSplit3-10-26** ⚠️ PARTIAL UPDATE NEEDED
**Current Status**: Mixed (mostly 86400s, one 300s)
**Instances**: 1 token validation method needs update
**Recommendation**: Update ONLY `decrypt_gchostpay1_response_token()` to 1800s (30 minutes)

**Token Validation Methods & Line Numbers:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decrypt_gcsplit1_to_gcsplit3_single_token()` | 195 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit1_to_gcsplit3_batch_token()` | 325 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit3_to_accumulator_response_token()` | 466 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit3_to_gchostpay1_batch_token()` | 627 | 86400s (24h) | ✓ OK |
| **`decrypt_gchostpay1_response_token()`** | **716** | **300s (5m)** | **⚠️ UPDATE NEEDED** |

**Rationale**: The `decrypt_gchostpay1_response_token()` method receives callbacks from GCHostPay1 after ChangeNow swap completion with potential delays of 15-20 minutes.

**Comment at line 714**: *"Validate timestamp (5 minutes = 300 seconds)"*

---

### ✅ Services Already Fixed

#### **GCMicroBatchProcessor-10-26** ✅
**Current Status**: 30-minute (1800s) window
**Line**: 161
**Status**: ✅ **ALREADY UPDATED** (Session 56)

**Token Validation Method:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decrypt_gchostpay1_to_microbatch_token()` | 161 | 1800s (30m) | ✅ Fixed |

**Comment at lines 154-158**:
```python
# Validate timestamp (30 minutes = 1800 seconds)
# Extended window to accommodate:
# - ChangeNow retry delays (up to 15 minutes for 3 retries)
# - Cloud Tasks queue delays (2-5 minutes)
# - Safety margin (10 minutes)
```

---

### ✓ Services with Adequate Windows (No Update Needed)

#### 5. **GCHostPay3-10-26** ✓
**Current Status**: 2-hour (7200s) window
**Instances**: 5 token validation methods
**Assessment**: ✓ **ADEQUATE** - 2-hour window provides sufficient margin

**Token Validation Methods:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decrypt_gcsplit2_to_gchostpay3_token()` | 188 | 7200s (2h) | ✓ OK |
| `decrypt_gchostpay3_to_gcsplit3_response_token()` | 341 | 7200s (2h) | ✓ OK |
| `decrypt_gchostpay3_to_gcsplit3_single_response_token()` | 499 | 7200s (2h) | ✓ OK |
| `decrypt_gchostpay3_to_gcaccumulator_payout_response_token()` | 709 | 7200s (2h) | ✓ OK |
| `decrypt_threshold_check_token()` | 858 | 7200s (2h) | ✓ OK |

---

#### 6. **GCWebhook1-10-26** ✓
**Current Status**: 2-hour (7200s) window
**Instances**: 1 token validation method
**Assessment**: ✓ **ADEQUATE** - 2-hour window for NOWPayments token

**Token Validation Method:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decode_and_verify_token()` | 169 | 7200s (2h) | ✓ OK |

**Note**: This token is received from NOWPayments success_url callback, which can experience payment confirmation delays.

---

#### 7. **GCWebhook2-10-26** ✓
**Current Status**: 24-hour (86400s) window
**Instances**: 1 token validation method
**Assessment**: ✓ **ADEQUATE** - 24-hour window is very generous

**Token Validation Method:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decode_and_verify_token()` | 163 | 86400s (24h) | ✓ OK |

---

#### 8. **GCSplit1-10-26** ✓
**Current Status**: 24-hour (86400s) window
**Instances**: 5 token validation methods
**Assessment**: ✓ **ADEQUATE** - 24-hour window is very generous

**Token Validation Methods:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decrypt_gcsplit1_to_gcsplit2_token()` | ~200 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit2_to_gcsplit1_token()` | ~350 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit1_to_gcsplit3_token()` | ~500 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit3_to_gcsplit1_token()` | ~650 | 86400s (24h) | ✓ OK |
| `decrypt_batch_token()` | ~750 | 86400s (24h) | ✓ OK |

---

#### 9. **GCSplit2-10-26** ✓
**Current Status**: 24-hour (86400s) window
**Instances**: 4 token validation methods
**Assessment**: ✓ **ADEQUATE** - 24-hour window is very generous

**Token Validation Methods:**
| Method | Line | Current Window | Status |
|--------|------|----------------|--------|
| `decrypt_gcwebhook1_to_gcsplit2_token()` | 208 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit2_to_gchostpay1_single_token()` | ~350 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit2_to_gchostpay2_single_token()` | ~480 | 86400s (24h) | ✓ OK |
| `decrypt_gcsplit2_to_gchostpay3_token()` | ~630 | 86400s (24h) | ✓ OK |

---

#### 10. **GCBatchProcessor-10-26** ✓
**Current Status**: No token decryption (only encryption)
**Assessment**: ✓ **N/A** - This service only encrypts tokens for GCSplit1, no validation needed

**Functions**:
- `encrypt_batch_token()` - Creates tokens for GCSplit1 batch payout requests
- No decryption methods exist in this file

---

## Summary Table: Update Requirements

| Service | Total Methods | 5-min (300s) | 30-min (1800s) | 2-hr (7200s) | 24-hr (86400s) | Update Needed? |
|---------|---------------|--------------|----------------|--------------|----------------|----------------|
| **GCMicroBatchProcessor** | 1 | 0 | **1** ✅ | 0 | 0 | ✅ Already Fixed |
| **GCHostPay1** | 7 | **1** ⚠️ | 0 | 6 | 0 | ⚠️ 1 method |
| **GCHostPay2** | 5 | **5** ⚠️ | 0 | 0 | 0 | ⚠️ All methods |
| **GCHostPay3** | 5 | 0 | 0 | 5 ✓ | 0 | ✓ OK |
| **GCAccumulator** | 2 | **2** ⚠️ | 0 | 0 | 0 | ⚠️ All methods |
| **GCSplit1** | 5 | 0 | 0 | 0 | 5 ✓ | ✓ OK |
| **GCSplit2** | 4 | 0 | 0 | 0 | 4 ✓ | ✓ OK |
| **GCSplit3** | 5 | **1** ⚠️ | 0 | 0 | 4 ✓ | ⚠️ 1 method |
| **GCWebhook1** | 1 | 0 | 0 | 1 ✓ | 0 | ✓ OK |
| **GCWebhook2** | 1 | 0 | 0 | 0 | 1 ✓ | ✓ OK |
| **GCBatchProcessor** | 0 | 0 | 0 | 0 | 0 | ✓ N/A |
| **TOTAL** | **36** | **9** | **1** | **12** | **14** | **4 services** |

---

## Implementation Checklist

### Phase 1: Critical Updates (Services with ChangeNow Dependencies)

- [ ] **GCHostPay2-10-26** - Update 5 methods from 300s → 1800s
  - [ ] Line 187: `decrypt_gcsplit2_to_gchostpay2_single_token()`
  - [ ] Line 340: `decrypt_gchostpay2_to_gcsplit2_single_response_token()`
  - [ ] Line 498: `decrypt_gcsplit2_to_gchostpay2_batch_token()`
  - [ ] Line 639: `decrypt_gchostpay2_to_gcsplit2_batch_response_token()`
  - [ ] Line 782: `decrypt_threshold_check_token()`

- [ ] **GCAccumulator-10-26** - Update 2 methods from 300s → 1800s
  - [ ] Line 269: `decrypt_gcsplit3_to_accumulator_token()`
  - [ ] Line 440: `decrypt_gchostpay1_to_accumulator_token()`

- [ ] **GCSplit3-10-26** - Update 1 method from 300s → 1800s
  - [ ] Line 716: `decrypt_gchostpay1_response_token()`

- [ ] **GCHostPay1-10-26** - Update 1 method from 300s → 1800s
  - [ ] Line 1043: `decrypt_microbatch_response_token()`

### Phase 2: Code Updates

For each method requiring update, apply the following changes:

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

### Phase 3: Deployment

- [ ] Build and deploy **GCHostPay2-10-26**
- [ ] Build and deploy **GCAccumulator-10-26**
- [ ] Build and deploy **GCSplit3-10-26**
- [ ] Build and deploy **GCHostPay1-10-26**

### Phase 4: Validation

- [ ] Monitor logs for token age logging (should show actual delays)
- [ ] Verify no "Token expired" errors in production
- [ ] Confirm all async workflows complete end-to-end
- [ ] Trigger test payouts to validate fixes

---

## Rationale for 30-Minute Window

### ChangeNow Workflow Timeline:
1. **Initial API Call**: GCHostPay sends create-exchange request
2. **ChangeNow Processing**: 5-30 minutes (swap execution)
3. **Status Check Retry 1**: +5 minutes (if not finished)
4. **Status Check Retry 2**: +5 minutes (if not finished)
5. **Status Check Retry 3**: +5 minutes (if not finished)
6. **Cloud Tasks Queue**: 30s-5 minutes (task delivery delay)
7. **Safety Margin**: +10 minutes (unexpected delays during high load)

**Total Maximum Delay**: 15m (retries) + 5m (queue) + 10m (safety) = **30 minutes**

### Security Considerations:
- HMAC-SHA256 signature validation still enforced (prevents tampering)
- Timestamp validation prevents token replay after 30 minutes
- 30-minute window is reasonable for legitimate async workflows
- Trade-off: Security vs. reliability (30m is acceptable given the async nature)

---

## Production Evidence (GCMicroBatchProcessor Bug)

**Log Timestamp**: 2025-11-03 17:05:01.153 EST
**Service**: GCMicroBatchProcessor-10-26
**Error**: `❌ [TOKEN_DEC] Decryption error: Token expired`
**Root Cause**: 5-minute window insufficient for 15-20 minute ChangeNow workflow
**Resolution**: Updated to 30-minute window (Session 56)

This same pattern will occur in GCHostPay2, GCAccumulator, GCSplit3, and GCHostPay1 reverse callback if not addressed.

---

## Related Documents

- `TOKEN_EXPIRATION_BATCH_CALLBACK_ANALYSIS.md` - Original bug analysis and solution design
- `PROGRESS.md` - Session 56 implementation details
- `DECISIONS.md` - Session 56 architectural decision rationale
- `BUGS.md` - Session 56 bug report

---

## Questions?

If you need clarification on any service's token flow or expiration requirements, review the workflow diagrams in:
- `PAYMENT_ARCHITECTURE_BREAKDOWN.md`
- `MAIN_ARCHITECTURE_WORKFLOW.md`
