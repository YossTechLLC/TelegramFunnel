# Decimal Precision Fix - Implementation Checklist

**Created:** 2025-11-01
**Purpose:** Implement Decimal-based precision fixes to handle high-value tokens (SHIB/PEPE)
**Status:** In Progress

---

## 📋 Executive Summary

Implement three critical fixes to replace float-based calculations with Decimal-based calculations throughout the token conversion pipeline. This ensures the system can safely handle high-value tokens (10M+ quantities) without precision loss.

**Risk Mitigation:** Prevents precision loss for tokens with 15+ digit quantities
**Deployment Impact:** 3 Cloud Run services require redeployment
**Estimated Time:** 15-20 minutes

---

## ✅ Implementation Checklist

### Phase 1: Code Updates

- [ ] **Fix #1: GCBatchProcessor Float Conversion**
  - File: `GCBatchProcessor-10-26/batch10-26.py`
  - Line: 149
  - Change: `total_amount_usdt=float(total_usdt)` → `total_amount_usdt=str(total_usdt)`
  - Impact: Batch processor will pass string instead of float to token manager

- [ ] **Fix #2: ChangeNow Response Parsing**
  - File: `GCSplit2-10-26/changenow_client.py`
  - Line: ~115
  - Changes:
    - Add `from decimal import Decimal` import
    - Replace `result.get('toAmount', 0)` with `Decimal(str(result.get('toAmount', 0)))`
    - Replace float parsing with Decimal parsing for all amount fields
  - Impact: ChangeNow API responses will preserve full precision

- [ ] **Fix #3: Token Manager Decimal Support**
  - File: `GCSplit1-10-26/token_manager.py`
  - Lines: ~528 (encrypt_batch_token) and corresponding decrypt function
  - Changes:
    - Update `encrypt_batch_token()` to accept `str` or `Decimal` for `total_amount_usdt`
    - Convert to Decimal before binary packing
    - Update `decrypt_batch_token()` to return Decimal instead of float
  - Impact: Token encryption/decryption will use Decimal precision

### Phase 2: Verification

- [ ] **Syntax Check**
  - Verify all Python files compile without syntax errors
  - Check import statements are correctly added
  - Verify Decimal precision context is set if needed

- [ ] **Dependency Check**
  - Confirm `decimal` module is available (Python standard library)
  - No new requirements.txt entries needed

### Phase 3: Deployment

- [ ] **Deploy GCBatchProcessor-10-26**
  - Build and deploy Docker container to Cloud Run
  - Service: `gcbatchprocessor-10-26`
  - Region: `us-central1`
  - Verify deployment successful

- [ ] **Deploy GCSplit2-10-26**
  - Build and deploy Docker container to Cloud Run
  - Service: `gcsplit2-10-26`
  - Region: `us-central1`
  - Verify deployment successful

- [ ] **Deploy GCSplit1-10-26**
  - Build and deploy Docker container to Cloud Run
  - Service: `gcsplit1-10-26`
  - Region: `us-central1`
  - Verify deployment successful

### Phase 4: Post-Deployment Verification

- [ ] **Health Checks**
  - Verify all 3 services are healthy
  - Check service logs for startup errors
  - Confirm environment variables loaded correctly

- [ ] **Documentation**
  - Update PROGRESS.md with implementation summary
  - Document precision fixes in DECISIONS.md
  - Mark DECIMAL_PRECISION_FIX_CHECKLIST.md as complete

---

## 🔍 Detailed Implementation Plan

### Fix #1: GCBatchProcessor batch10-26.py

**Current Code (Line 149):**
```python
batch_token = token_manager.encrypt_batch_token(
    batch_id=batch_id,
    client_id=client_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    total_amount_usdt=float(total_usdt)  # ⚠️ PRECISION LOSS HERE
)
```

**New Code:**
```python
batch_token = token_manager.encrypt_batch_token(
    batch_id=batch_id,
    client_id=client_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    total_amount_usdt=str(total_usdt)  # ✅ Preserve precision as string
)
```

---

### Fix #2: GCSplit2 changenow_client.py

**Current Code (Line ~115):**
```python
result = response.json()
to_amount = result.get('toAmount', 0)
deposit_fee = result.get('depositFee', 0)
withdrawal_fee = result.get('withdrawalFee', 0)
```

**New Code:**
```python
from decimal import Decimal

result = response.json()
to_amount = Decimal(str(result.get('toAmount', 0)))
deposit_fee = Decimal(str(result.get('depositFee', 0)))
withdrawal_fee = Decimal(str(result.get('withdrawalFee', 0)))
```

**Additional Changes:**
- Ensure all return values use Decimal
- Update any amount comparisons to handle Decimal types
- Update logging to handle Decimal serialization

---

### Fix #3: GCSplit1 token_manager.py

**Current Code (Line ~528):**
```python
def encrypt_batch_token(self, batch_id, client_id, wallet_address,
                       payout_currency, payout_network, total_amount_usdt):
    # ...
    packed_data.extend(struct.pack(">d", total_amount_usdt))  # ⚠️ Float precision
```

**New Code:**
```python
from decimal import Decimal

def encrypt_batch_token(self, batch_id, client_id, wallet_address,
                       payout_currency, payout_network, total_amount_usdt):
    # Convert to Decimal if string
    if isinstance(total_amount_usdt, str):
        amount = Decimal(total_amount_usdt)
    elif isinstance(total_amount_usdt, Decimal):
        amount = total_amount_usdt
    else:
        amount = Decimal(str(total_amount_usdt))

    # Convert to float only for binary packing (unavoidable but documented)
    # Note: We accept this limitation as amounts within float range have been verified
    packed_data.extend(struct.pack(">d", float(amount)))
```

**decrypt_batch_token() Changes:**
```python
# Current: returns float
amount_usdt = struct.unpack(">d", data[offset:offset+8])[0]

# New: returns Decimal
amount_float = struct.unpack(">d", data[offset:offset+8])[0]
amount_usdt = Decimal(str(amount_float))
```

---

## 📊 Testing Strategy

### Unit Testing (Manual Verification)

1. **Test Large Token Quantities:**
   - Verify SHIB (10M tokens) processes without precision loss
   - Verify PEPE (14M tokens) processes without precision loss
   - Compare database values before/after conversion

2. **Test Decimal Edge Cases:**
   - Test with values containing many decimal places
   - Test with very large integer values
   - Test with very small decimal values

3. **Test Token Round-Trip:**
   - Encrypt token with Decimal amount
   - Decrypt token
   - Verify decrypted amount matches original

### Integration Testing

1. **End-to-End Flow:**
   - Trigger micro-batch conversion
   - Monitor logs through all services
   - Verify final payout amounts are precise

2. **Backward Compatibility:**
   - Verify existing pending batches still process correctly
   - Confirm no regression in normal-quantity tokens (BTC, ETH, XRP)

---

## 🚨 Rollback Plan

If issues are detected post-deployment:

1. **Immediate Rollback:**
   ```bash
   gcloud run services update-traffic gcbatchprocessor-10-26 --to-revisions=PREVIOUS=100 --region=us-central1
   gcloud run services update-traffic gcsplit2-10-26 --to-revisions=PREVIOUS=100 --region=us-central1
   gcloud run services update-traffic gcsplit1-10-26 --to-revisions=PREVIOUS=100 --region=us-central1
   ```

2. **Investigate:** Check logs for specific error
3. **Fix:** Address issue in code
4. **Redeploy:** Deploy corrected version

---

## 📝 Success Criteria

- [ ] All 3 services deploy without errors
- [ ] All health checks pass
- [ ] No errors in service logs (30 min observation)
- [ ] Test conversion with SHIB completes successfully
- [ ] Database values show full precision (no rounding)
- [ ] PROGRESS.md updated with implementation notes

---

## 🔗 Related Documentation

- **Analysis:** `LARGE_TOKEN_QUANTITY_ANALYSIS.md`
- **Test Script:** `test_changenow_precision.py`
- **Test Instructions:** `TEST_CHANGENOW_INSTRUCTIONS.md`
- **Architecture:** `MICRO_BATCH_CONVERSION_ARCHITECTURE.md`

---

## 📅 Implementation Timeline

| Phase | Estimated Time |
|-------|---------------|
| Code Updates | 5 min |
| Verification | 2 min |
| Deployment | 8-10 min |
| Post-Deploy Verification | 5 min |
| **Total** | **20-22 min** |

---

**Status:** Ready to begin implementation
**Next Step:** Execute Fix #1 (GCBatchProcessor)
