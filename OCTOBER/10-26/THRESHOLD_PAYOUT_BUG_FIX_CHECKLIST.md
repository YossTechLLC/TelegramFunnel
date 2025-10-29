# Threshold Payout Bug Fix Checklist
**Date Created:** 2025-10-29
**Issue:** Threshold payout strategy defaulting to instant payout instead of accumulation
**Channel ID:** -1003296084379
**Transaction:** 0x7603d7944c4ea164e7f134619deb2dbe594ac210d0f5f50351103e8bd360ae18

---

## Root Cause Analysis

### The Problem
Channel `-1003296084379` is configured with:
- **Payout Strategy:** `threshold`
- **Threshold Amount:** `$2.00 USD`
- **Payment Amount:** `$1.35 USD` (below threshold)

Expected behavior: Payment should accumulate in `payout_accumulation` table
Actual behavior: Payment processed as instant/direct payout via GCSplit1

### The Root Cause
GCWebhook1's `get_payout_strategy()` method queries the database to check payout strategy, but **FAILS TO FIND** the channel configuration and defaults to `instant`.

**Log Evidence:**
```
🔍 [DATABASE] Fetching payout strategy for channel -1003296084379
🔗 [DATABASE] Connection established successfully
⚠️ [DATABASE] No client found for channel -1003296084379, defaulting to instant
🔌 [DATABASE] Connection closed
💰 [ENDPOINT] Payout strategy: instant
⚡ [ENDPOINT] Instant payout mode - processing immediately
```

**Why the Query Fails:**
GCWebhook1's Cloud Run deployment has database credentials set as **SECRET PATHS** instead of **SECRET VALUES**:

```yaml
# WRONG (current deployment):
env:
  - name: DATABASE_NAME_SECRET
    value: projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
```

The `config_manager.py` uses `os.getenv()` to read these values, expecting actual credentials (like `client_table`), but instead gets the SECRET PATH.

This causes the database connection to use **INCORRECT** credentials, resulting in:
1. Either connecting to wrong database
2. Or query failing silently
3. Defaulting to `instant` payout strategy

**This is the SAME bug we just fixed in GCHostPay1 and GCHostPay3!**

---

## Affected Services

### Primary Service (Needs Fix)
1. **GCWebhook1-10-26** ❌
   - File: `GCWebhook1-10-26/Dockerfile` (if deployment script embedded)
   - Current deployment uses environment variables with secret PATHS
   - Needs to use `--set-secrets` flag instead

### Services to Verify (Might Have Same Issue)
2. **GCWebhook2-10-26** ⚠️ (check deployment)
3. **GCSplit1-10-26** ⚠️ (check deployment)
4. **GCSplit2-10-26** ⚠️ (check deployment)
5. **GCSplit3-10-26** ⚠️ (check deployment)
6. **GCAccumulator-10-26** ⚠️ (check deployment)
7. **GCBatchProcessor-10-26** ⚠️ (check deployment)

### Services Already Fixed ✅
- GCHostPay1-10-26 (fixed today)
- GCHostPay3-10-26 (fixed today)

---

## Fix Strategy

### Solution: Use --set-secrets Instead of Environment Variables

**Change from:**
```bash
gcloud run deploy gcwebhook1-10-26 \
  --image gcr.io/telepay-459221/gcwebhook1-10-26:latest \
  --set-env-vars="DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest"
```

**Change to:**
```bash
gcloud run deploy gcwebhook1-10-26 \
  --image gcr.io/telepay-459221/gcwebhook1-10-26:latest \
  --set-secrets="DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest"
```

This way, Cloud Run automatically injects the secret **VALUES** into the environment variables, which `config_manager.py` can read directly with `os.getenv()`.

---

## Implementation Checklist

### Phase 1: Fix GCWebhook1 Deployment
- [  ] 1. Find current deployment command/script for GCWebhook1
- [  ] 2. Update deployment to use `--set-secrets` flag for:
  - `DATABASE_NAME_SECRET`
  - `DATABASE_USER_SECRET`
  - `DATABASE_PASSWORD_SECRET`
  - `CLOUD_SQL_CONNECTION_NAME`
- [  ] 3. Redeploy GCWebhook1-10-26
- [  ] 4. Verify logs show successful database connection
- [  ] 5. Verify `get_payout_strategy()` can now find channels

### Phase 2: Verify Other Services
- [  ] 6. Check deployment config for GCWebhook2-10-26
- [  ] 7. Check deployment config for GCSplit1-10-26
- [  ] 8. Check deployment config for GCSplit2-10-26
- [  ] 9. Check deployment config for GCSplit3-10-26
- [  ] 10. Check deployment config for GCAccumulator-10-26
- [  ] 11. Check deployment config for GCBatchProcessor-10-26
- [  ] 12. Fix any services with same issue

### Phase 3: Test Threshold Payout Flow
- [  ] 13. Make a test payment to channel `-1003296084379` ($1.35)
- [  ] 14. Verify GCWebhook1 logs show:
  - `✅ [DATABASE] Found client by closed_channel_id: strategy=threshold, threshold=$2.00`
  - `🎯 [ENDPOINT] Threshold payout mode - $2.00 threshold`
  - `✅ [ENDPOINT] Enqueued to GCAccumulator for threshold payout`
- [  ] 15. Verify GCAccumulator receives the task
- [  ] 16. Verify `payout_accumulation` table has the entry
- [  ] 17. Verify `split_payout_request` has `type=accumulation` (NOT `type=direct`)
- [  ] 18. Verify NO task sent to GCSplit1 (instant payout should be skipped)

### Phase 4: Documentation
- [  ] 19. Update BUGS.md with bug report
- [  ] 20. Update DECISIONS.md with architectural decision
- [  ] 21. Update PROGRESS.md with session summary
- [  ] 22. Document the pattern for all future deployments

---

## Verification Commands

### Check Current Deployment Config
```bash
gcloud run services describe gcwebhook1-10-26 --region=us-central1 --format="yaml(spec.template.spec.containers[0].env)"
```

### Check Logs After Fix
```bash
gcloud logging read "resource.labels.service_name=gcwebhook1-10-26 AND textPayload:payout_strategy" --limit=20 --format=json
```

### Query Database Directly
```sql
SELECT closed_channel_id, payout_strategy, payout_threshold_usd
FROM main_clients_database
WHERE closed_channel_id = '-1003296084379';
```

### Check Recent Payout Requests
```sql
SELECT unique_id, closed_channel_id, type, flow, from_amount, created_at
FROM split_payout_request
WHERE closed_channel_id = '-1003296084379'
ORDER BY created_at DESC
LIMIT 5;
```

---

## Expected Outcomes

### Before Fix
- ❌ `get_payout_strategy()` returns `('instant', 0)`
- ❌ Payment routed to GCSplit1
- ❌ `split_payout_request.type` = `direct`
- ❌ No entry in `payout_accumulation`

### After Fix
- ✅ `get_payout_strategy()` returns `('threshold', 2.00)`
- ✅ Payment routed to GCAccumulator
- ✅ `split_payout_request.type` = `accumulation`
- ✅ Entry created in `payout_accumulation`
- ✅ Accumulation continues until threshold reached
- ✅ GCBatchProcessor triggered when threshold met

---

## Risk Assessment

### Low Risk
- This is the same fix we successfully applied to GCHostPay1 and GCHostPay3
- Only changes deployment configuration (not code)
- `--set-secrets` is the recommended Cloud Run pattern
- Falls back to instant payout if anything fails (safe default)

### Rollback Plan
If fix causes issues:
1. Revert to previous Cloud Run revision
2. `gcloud run services update-traffic gcwebhook1-10-26 --to-revisions=PREVIOUS_REVISION=100 --region=us-central1`

---

## Related Files

- `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py:176-213` (payout routing logic)
- `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/database_manager.py:180-229` (get_payout_strategy method)
- `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/config_manager.py:103-120` (database config loading)
- `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/DATABASE_CREDENTIALS_FIX_CHECKLIST.md` (previous fix for same issue)

---

## Notes

- This bug affects ALL threshold-based payouts, not just this one channel
- Every payment to a threshold channel is being processed instantly instead of accumulating
- The fix is critical for the threshold payout architecture to work
- After fix, existing accumulation logic should work correctly
