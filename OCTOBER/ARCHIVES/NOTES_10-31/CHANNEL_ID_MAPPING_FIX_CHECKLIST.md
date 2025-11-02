# Channel ID Mapping Fix Checklist

## Issue Summary
GCWebhook1-10-26 is receiving `closed_channel_id` (private channel) in payment tokens, but attempting to query `main_clients_database` using `WHERE open_channel_id = <closed_channel_id>`. This causes "No client found" errors because the database schema uses:
- `open_channel_id` (PRIMARY KEY) - Public channel ID
- `closed_channel_id` - Private channel ID

## Root Cause
Line 206 in `GCWebhook1-10-26/database_manager.py`:
```python
WHERE open_channel_id = %s
```
Should query by `closed_channel_id` instead.

## Services Affected
1. ✅ **GCWebhook1-10-26** - `database_manager.py::get_payout_strategy()` - PRIMARY FIX
2. ⚠️  **GCAccumulator-10-26** - Uses `client_id` parameter (needs review)
3. ⚠️  **GCBatchProcessor-10-26** - Queries by `client_id` (needs review)
4. ⚠️  **GCSplit1-10-26** - Receives `closed_channel_id` (needs review)
5. ⚠️  **GCHostPay1-10-26** - May need similar fix (needs review)

## Fix Implementation Steps

### Step 1: Fix GCWebhook1 database_manager.py ✓
- [ ] Change query from `WHERE open_channel_id = %s` to `WHERE closed_channel_id = %s`
- [ ] Update logging to reflect correct channel type
- [ ] Test query locally if possible

### Step 2: Review GCAccumulator database_manager.py
- [ ] Check `get_client_accumulation_total()` - uses client_id
- [ ] Check `get_client_threshold()` - uses client_id
- [ ] Verify if client_id == open_channel_id or closed_channel_id
- [ ] Fix if needed

### Step 3: Review GCBatchProcessor database_manager.py
- [ ] Check `find_clients_over_threshold()` - joins with main_clients_database
- [ ] Verify join condition uses correct channel ID mapping
- [ ] Fix if needed

### Step 4: Review Token Flows
- [ ] GCWebhook1 receives closed_channel_id from NOWPayments token ✓
- [ ] GCWebhook1 passes closed_channel_id to GCAccumulator as client_id ✓
- [ ] GCAccumulator stores client_id (verify this is closed_channel_id) ✓
- [ ] GCBatchProcessor reads client_id from payout_accumulation table ✓
- [ ] Ensure consistency across all services

### Step 5: Rebuild and Deploy
- [ ] Rebuild GCWebhook1-10-26 Docker image
- [ ] Deploy GCWebhook1-10-26 to Cloud Run
- [ ] (If needed) Rebuild and deploy GCAccumulator-10-26
- [ ] (If needed) Rebuild and deploy GCBatchProcessor-10-26
- [ ] (If needed) Rebuild and deploy other affected services

### Step 6: Test and Verify
- [ ] Monitor GCWebhook1 logs for next payment
- [ ] Verify "Found strategy" message instead of "No client found"
- [ ] Verify threshold vs instant routing works correctly
- [ ] Check GCAccumulator receives tasks if threshold mode
- [ ] Check GCSplit1 receives tasks if instant mode

## Database Schema Reference
```sql
CREATE TABLE main_clients_database (
    open_channel_id VARCHAR(14) PRIMARY KEY,      -- Public channel
    closed_channel_id VARCHAR(14) NOT NULL,       -- Private channel
    payout_strategy VARCHAR(20),                  -- 'instant' or 'threshold'
    payout_threshold_usd NUMERIC(10, 2),
    ...
);

CREATE TABLE payout_accumulation (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(14) NOT NULL,               -- References ??? (needs verification)
    ...
);
```

## Key Question to Answer
**What does `client_id` in `payout_accumulation` table refer to?**
- If `client_id` == `open_channel_id`: Need to create mapping logic
- If `client_id` == `closed_channel_id`: Current approach is correct

## Expected Behavior After Fix
1. User pays for subscription to private channel `-1003272448971`
2. GCWebhook1 receives token with `closed_channel_id = -1003272448971`
3. GCWebhook1 queries `main_clients_database WHERE closed_channel_id = '-1003272448971'`
4. Query finds client record with matching closed_channel_id
5. Returns correct `payout_strategy` and `payout_threshold_usd`
6. Routes payment to either GCAccumulator (threshold) or GCSplit1 (instant)

## Rollback Plan
If fix causes issues:
1. Revert to previous gcwebhook1-10-26 revision
2. Check logs for specific error
3. Re-analyze token flow and database schema
4. Apply corrected fix
