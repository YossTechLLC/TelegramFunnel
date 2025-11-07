# NowPayments Webhook Channel ID Fix - Comprehensive Checklist

**Created:** 2025-11-02
**Status:** READY FOR IMPLEMENTATION
**Priority:** P0 - Critical Bug - Blocking Payment ID Storage

---

## Table of Contents
1. [Root Cause Analysis](#root-cause-analysis)
2. [Impact Assessment](#impact-assessment)
3. [Solution Architecture](#solution-architecture)
4. [Implementation Checklist](#implementation-checklist)
5. [Testing Strategy](#testing-strategy)
6. [Verification Steps](#verification-steps)

---

## Root Cause Analysis

### Issue Summary
NowPayments IPN callback is failing to update the database because of a **channel ID sign mismatch**:
- **Order ID contains:** `PGP-6271402111-1003268562225` (positive channel ID)
- **Database contains:** `-1003268562225` (negative channel ID)

### Three-Part Problem

#### 1. **Order ID Generation Bug** (`TelePay10-26/start_np_gateway.py:168`)

```python
# CURRENT (BUGGY):
order_id = f"PGP-{user_id}{open_channel_id}"
# Result: PGP-6271402111-1003268562225
# The negative sign in -1003268562225 becomes a separator!
```

**What Happens:**
- If `open_channel_id = "-1003268562225"` and `user_id = "6271402111"`
- Result: `"PGP-6271402111" + "-1003268562225"` = `"PGP-6271402111-1003268562225"`
- The negative sign is treated as a hyphen separator
- Telegram channel IDs are ALWAYS negative for supergroups/channels

**Actual Telegram Channel ID Format:**
- Public/Open Channel ID: `-1003268562225` (NEGATIVE)
- Private/Closed Channel ID: `-1001234567890` (ALSO NEGATIVE)

#### 2. **Order ID Parsing Bug** (`np-webhook-10-26/app.py:123-129`)

```python
# CURRENT (BUGGY):
parts = order_id.split('-')
# For "PGP-6271402111-1003268562225":
# parts = ['PGP', '6271402111', '1003268562225']

user_id = int(parts[1])      # 6271402111 ✅
channel_id = int(parts[2])   # 1003268562225 ❌ (should be -1003268562225)
```

**Problem:**
- Splits on `-` which treats the negative sign as a delimiter
- Loses the negative sign when parsing channel_id
- Results in positive channel ID that doesn't exist in database

#### 3. **Database Lookup Mismatch** (`np-webhook-10-26/app.py:153`)

```python
# CURRENT (BUGGY):
WHERE user_id = %s AND private_channel_id = %s
```

**Data Model Confusion:**

| Table | Contains | Example Value |
|-------|----------|---------------|
| `main_clients_database` | `open_channel_id` (public) | `-1003268562225` |
| `main_clients_database` | `closed_channel_id` (private) | `-1001234567890` |
| `private_channel_users_database` | `private_channel_id` (private) | `-1001234567890` |

**The Problem:**
1. Order ID is built using `open_channel_id` from `main_clients_database`
2. But webhook queries `private_channel_users_database` using `private_channel_id`
3. These are **DIFFERENT VALUES** - one is the public channel, one is the private channel
4. Even if we fix the sign, we're looking up the wrong ID!

**The Correct Flow Should Be:**
1. Order ID contains: `user_id` + `open_channel_id` (public channel)
2. Webhook receives order_id
3. Webhook must:
   - Parse `user_id` and `open_channel_id` correctly (with negative sign)
   - Look up `closed_channel_id` from `main_clients_database` using `open_channel_id`
   - Update `private_channel_users_database` using `user_id` + `private_channel_id` (which equals `closed_channel_id`)

---

## Impact Assessment

### Current Impact
- ✅ **Signature Verification:** Working correctly
- ✅ **IPN Reception:** Webhook receiving callbacks successfully
- ❌ **Database Updates:** Failing with "No records found to update"
- ❌ **Payment ID Storage:** Not being stored
- ❌ **Fee Reconciliation:** Blocked (depends on payment_id)

### Affected Services
1. `np-webhook-10-26` - IPN handler (PRIMARY)
2. `TelePay10-26/start_np_gateway.py` - Order ID generation (ROOT CAUSE)

### Not Affected
- ✅ GCWebhook1, GCWebhook2 - Use different flow (success_url tokens)
- ✅ GCSplit services - Downstream, not involved in order_id
- ✅ GCAccumulator, GCBatchProcessor - Downstream services

---

## Solution Architecture

### Design Principles
1. **Explicit Separator:** Use unique separator that cannot appear in channel IDs
2. **Preserve Negative Sign:** Ensure negative channel IDs are preserved
3. **Correct Database Mapping:** Look up the right table with the right ID
4. **Backward Compatible:** Handle both old and new format during transition
5. **Validation:** Add checks to ensure data integrity

### Proposed Changes

#### Change 1: Order ID Format
```python
# OLD: PGP-{user_id}{open_channel_id}
# Example: PGP-6271402111-1003268562225 (BROKEN - loses negative sign)

# NEW: PGP-{user_id}|{open_channel_id}
# Example: PGP-6271402111|-1003268562225 (FIXED - preserves negative sign)
```

**Rationale:**
- Use `|` as separator (cannot appear in user IDs or channel IDs)
- Negative sign explicitly preserved
- Easy to parse: `split('|')` instead of `split('-')`

#### Change 2: Database Lookup Strategy
```sql
-- Step 1: Lookup closed_channel_id from open_channel_id
SELECT closed_channel_id
FROM main_clients_database
WHERE open_channel_id = %s

-- Step 2: Update private_channel_users_database
UPDATE private_channel_users_database
SET nowpayments_payment_id = %s, ...
WHERE user_id = %s AND private_channel_id = %s
```

---

## Implementation Checklist

### Phase 1: Fix Order ID Generation (TelePay Bot)
**File:** `OCTOBER/10-26/TelePay10-26/start_np_gateway.py`

- [ ] **1.1** Update order_id generation (line 168)
  ```python
  # OLD:
  order_id = f"PGP-{user_id}{open_channel_id}"

  # NEW:
  order_id = f"PGP-{user_id}|{open_channel_id}"
  ```

- [ ] **1.2** Add validation before creating order_id
  ```python
  # Ensure open_channel_id is negative (Telegram requirement)
  if not str(open_channel_id).startswith('-'):
      print(f"⚠️ [VALIDATION] open_channel_id should be negative: {open_channel_id}")
      # Option A: Add negative sign
      open_channel_id = f"-{open_channel_id}"
      # Option B: Raise error to catch misconfiguration
      # raise ValueError(f"Invalid open_channel_id format: {open_channel_id}")
  ```

- [ ] **1.3** Add debug logging
  ```python
  print(f"📋 [ORDER] Created order_id: {order_id}")
  print(f"   User ID: {user_id}")
  print(f"   Open Channel ID: {open_channel_id}")
  ```

### Phase 2: Fix IPN Webhook Parsing
**File:** `OCTOBER/10-26/np-webhook-10-26/app.py`

- [ ] **2.1** Update order_id parsing logic (lines 121-130)
  ```python
  # NEW PARSING LOGIC:
  def parse_order_id(order_id: str) -> tuple:
      """
      Parse NowPayments order_id to extract user_id and open_channel_id.

      Format: PGP-{user_id}|{open_channel_id}
      Example: PGP-6271402111|-1003268562225

      Returns:
          Tuple of (user_id, open_channel_id) or (None, None) if invalid
      """
      try:
          # Check for new format first (with | separator)
          if '|' in order_id:
              # New format: PGP-{user_id}|{open_channel_id}
              prefix_and_user, channel_id_str = order_id.split('|')
              if not prefix_and_user.startswith('PGP-'):
                  return None, None
              user_id_str = prefix_and_user[4:]  # Remove 'PGP-' prefix
              user_id = int(user_id_str)
              open_channel_id = int(channel_id_str)  # Preserves negative sign
              return user_id, open_channel_id

          # Fallback to old format for backward compatibility (during transition)
          else:
              # Old format: PGP-{user_id}-{channel_id} (loses negative sign)
              parts = order_id.split('-')
              if len(parts) < 3 or parts[0] != 'PGP':
                  return None, None
              user_id = int(parts[1])
              channel_id = int(parts[2])
              # FIX: Add negative sign back (all Telegram channels are negative)
              open_channel_id = -abs(channel_id)
              print(f"⚠️ [PARSE] Old format detected - added negative sign: {open_channel_id}")
              return user_id, open_channel_id

      except (ValueError, IndexError) as e:
          print(f"❌ [PARSE] Failed to parse order_id '{order_id}': {e}")
          return None, None
  ```

- [ ] **2.2** Update `update_payment_data()` function signature
  ```python
  # OLD:
  def update_payment_data(order_id: str, payment_data: dict) -> bool:

  # NEW:
  def update_payment_data(order_id: str, payment_data: dict) -> bool:
  ```

- [ ] **2.3** Implement two-step database lookup
  ```python
  def update_payment_data(order_id: str, payment_data: dict) -> bool:
      """
      Update private_channel_users_database with NowPayments payment data.

      Two-step process:
      1. Parse order_id to get user_id and open_channel_id
      2. Look up closed_channel_id from main_clients_database
      3. Update private_channel_users_database using private_channel_id
      """
      conn = None
      cur = None

      try:
          # Step 1: Parse order_id
          user_id, open_channel_id = parse_order_id(order_id)
          if user_id is None or open_channel_id is None:
              print(f"❌ [DATABASE] Invalid order_id format: {order_id}")
              return False

          print(f"📝 [DATABASE] Parsed order_id:")
          print(f"   User ID: {user_id}")
          print(f"   Open Channel ID: {open_channel_id}")

          conn = get_db_connection()
          if not conn:
              return False

          cur = conn.cursor()

          # Step 2: Look up closed_channel_id (private_channel_id) from main_clients_database
          print(f"🔍 [DATABASE] Looking up closed_channel_id for open_channel_id: {open_channel_id}")
          cur.execute(
              "SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s",
              (str(open_channel_id),)
          )
          result = cur.fetchone()

          if not result or not result[0]:
              print(f"❌ [DATABASE] No closed_channel_id found for open_channel_id: {open_channel_id}")
              print(f"⚠️ [DATABASE] This channel may not be registered in main_clients_database")
              return False

          closed_channel_id = result[0]
          print(f"✅ [DATABASE] Found closed_channel_id: {closed_channel_id}")

          # Step 3: Update private_channel_users_database
          # Note: private_channel_id in this table = closed_channel_id from main_clients_database
          update_query = """
              UPDATE private_channel_users_database
              SET
                  nowpayments_payment_id = %s,
                  nowpayments_invoice_id = %s,
                  nowpayments_order_id = %s,
                  nowpayments_pay_address = %s,
                  nowpayments_payment_status = %s,
                  nowpayments_pay_amount = %s,
                  nowpayments_pay_currency = %s,
                  nowpayments_outcome_amount = %s,
                  nowpayments_created_at = CURRENT_TIMESTAMP,
                  nowpayments_updated_at = CURRENT_TIMESTAMP
              WHERE user_id = %s AND private_channel_id = %s
              AND id = (
                  SELECT id FROM private_channel_users_database
                  WHERE user_id = %s AND private_channel_id = %s
                  ORDER BY id DESC LIMIT 1
              )
          """

          cur.execute(update_query, (
              payment_data.get('payment_id'),
              payment_data.get('invoice_id'),
              payment_data.get('order_id'),
              payment_data.get('pay_address'),
              payment_data.get('payment_status'),
              payment_data.get('pay_amount'),
              payment_data.get('pay_currency'),
              payment_data.get('outcome_amount'),
              user_id,
              closed_channel_id,  # Use closed_channel_id (not open_channel_id!)
              user_id,
              closed_channel_id
          ))

          conn.commit()
          rows_updated = cur.rowcount

          if rows_updated > 0:
              print(f"✅ [DATABASE] Updated {rows_updated} record(s)")
              print(f"   User ID: {user_id}")
              print(f"   Private Channel ID: {closed_channel_id}")
              print(f"   Payment ID: {payment_data.get('payment_id')}")
              print(f"   Status: {payment_data.get('payment_status')}")
              return True
          else:
              print(f"⚠️ [DATABASE] No records found to update")
              print(f"   User ID: {user_id}")
              print(f"   Private Channel ID: {closed_channel_id}")
              print(f"💡 [DATABASE] User may not have an active subscription record")
              return False

      except Exception as e:
          print(f"❌ [DATABASE] Update failed: {e}")
          if conn:
              conn.rollback()
          return False
      finally:
          if cur:
              cur.close()
          if conn:
              conn.close()
              print(f"🔌 [DATABASE] Connection closed")
  ```

### Phase 3: Add Comprehensive Logging
**Files:** Both `start_np_gateway.py` and `app.py`

- [ ] **3.1** Add order_id validation logs
  ```python
  print(f"🔍 [VALIDATION] Order ID format check:")
  print(f"   Raw order_id: {order_id}")
  print(f"   Contains | separator: {('|' in order_id)}")
  print(f"   User ID: {user_id}")
  print(f"   Channel ID: {open_channel_id}")
  print(f"   Channel ID is negative: {str(open_channel_id).startswith('-')}")
  ```

- [ ] **3.2** Add database lookup logs
  ```python
  print(f"🗄️ [DATABASE] Channel ID Mapping:")
  print(f"   Open Channel ID (from order): {open_channel_id}")
  print(f"   Closed Channel ID (from DB): {closed_channel_id}")
  print(f"   Searching in private_channel_users_database...")
  ```

### Phase 4: Error Handling & Edge Cases

- [ ] **4.1** Handle missing channel mapping
  ```python
  if not closed_channel_id:
      print(f"❌ [ERROR] Channel mapping not found")
      print(f"💡 [HINT] Register this channel in main_clients_database:")
      print(f"   open_channel_id: {open_channel_id}")
      return False
  ```

- [ ] **4.2** Handle no subscription record
  ```python
  if rows_updated == 0:
      print(f"⚠️ [WARNING] No subscription record found")
      print(f"💡 [HINT] User may need to create subscription first")
      print(f"   Check: SELECT * FROM private_channel_users_database")
      print(f"   WHERE user_id = {user_id} AND private_channel_id = {closed_channel_id}")
      # Still return 500 so NowPayments retries
      return False
  ```

- [ ] **4.3** Add IPN retry awareness
  ```python
  # NowPayments will retry on 500 errors
  # Return 200 only when truly successful
  # Return 500 for retryable errors (DB connection, etc.)
  # Return 400 for non-retryable errors (invalid order_id format)
  ```

### Phase 5: Database Schema Validation

- [ ] **5.1** Verify `main_clients_database` schema
  ```sql
  SELECT column_name, data_type
  FROM information_schema.columns
  WHERE table_name = 'main_clients_database'
  AND column_name IN ('open_channel_id', 'closed_channel_id');
  ```

- [ ] **5.2** Verify `private_channel_users_database` has NowPayments columns
  ```sql
  SELECT column_name
  FROM information_schema.columns
  WHERE table_name = 'private_channel_users_database'
  AND column_name LIKE 'nowpayments%';
  ```

- [ ] **5.3** Check for existing test data
  ```sql
  SELECT user_id, private_channel_id, nowpayments_payment_id
  FROM private_channel_users_database
  WHERE user_id = 6271402111
  LIMIT 5;
  ```

---

## Testing Strategy

### Test Case 1: New Format Order ID
**Setup:**
- User ID: `6271402111`
- Open Channel ID: `-1003268562225`
- Closed Channel ID: `-1001234567890` (from DB lookup)

**Expected:**
```
Order ID: PGP-6271402111|-1003268562225
Parsing Result: user_id=6271402111, open_channel_id=-1003268562225
DB Lookup: closed_channel_id=-1001234567890
Update Query: WHERE user_id=6271402111 AND private_channel_id=-1001234567890
Result: ✅ Success
```

### Test Case 2: Old Format Order ID (Backward Compatibility)
**Setup:**
- Order ID: `PGP-6271402111-1003268562225` (old format)

**Expected:**
```
Parsing Result: user_id=6271402111, open_channel_id=-1003268562225 (sign added)
Warning: "Old format detected - added negative sign"
DB Lookup: closed_channel_id=-1001234567890
Result: ✅ Success (with warning)
```

### Test Case 3: Missing Channel Mapping
**Setup:**
- Open Channel ID not in `main_clients_database`

**Expected:**
```
Parsing: ✅ Success
DB Lookup: ❌ No closed_channel_id found
Result: ❌ Error (channel not registered)
HTTP: 500 (retry)
```

### Test Case 4: No Subscription Record
**Setup:**
- Channel mapping exists
- No record in `private_channel_users_database`

**Expected:**
```
Parsing: ✅ Success
DB Lookup: ✅ closed_channel_id found
Update: ⚠️ 0 rows updated
Result: ❌ Error (no subscription)
HTTP: 500 (retry)
```

---

## Verification Steps

### Pre-Deployment Verification

- [ ] **V1:** Code review of both files
  - [ ] Order ID format uses `|` separator
  - [ ] Parsing handles negative signs correctly
  - [ ] Two-step database lookup implemented
  - [ ] Error handling covers all edge cases

- [ ] **V2:** Local testing with mock data
  ```python
  # Test parse_order_id function
  assert parse_order_id("PGP-6271402111|-1003268562225") == (6271402111, -1003268562225)
  assert parse_order_id("PGP-6271402111-1003268562225") == (6271402111, -1003268562225)  # Old format
  ```

- [ ] **V3:** Database connectivity test
  ```python
  # Verify can connect and query both tables
  # Verify channel mapping exists for test channel
  ```

### Post-Deployment Verification

- [ ] **V4:** Monitor IPN webhook logs
  ```bash
  gcloud run services logs read np-webhook-10-26 \
    --region=us-east1 \
    --limit=50 \
    | grep "IPN"
  ```

- [ ] **V5:** Test payment flow end-to-end
  1. Create test payment in TelePay bot
  2. Check order_id format in logs
  3. Complete payment (or simulate IPN)
  4. Verify payment_id stored in database

- [ ] **V6:** Query database for successful update
  ```sql
  SELECT
      user_id,
      private_channel_id,
      nowpayments_payment_id,
      nowpayments_order_id,
      nowpayments_payment_status,
      nowpayments_updated_at
  FROM private_channel_users_database
  WHERE nowpayments_payment_id IS NOT NULL
  ORDER BY nowpayments_updated_at DESC
  LIMIT 5;
  ```

---

## Deployment Plan

### Step 1: Deploy TelePay Bot Update
```bash
cd OCTOBER/10-26/TelePay10-26
# Review changes
git diff start_np_gateway.py

# Deploy (if using Cloud Run/Functions)
# gcloud run deploy telepay-10-26 ...
```

### Step 2: Deploy NP Webhook Update
```bash
cd OCTOBER/10-26/np-webhook-10-26

# Build and deploy
gcloud builds submit --tag gcr.io/telepay-459221/np-webhook-10-26
gcloud run deploy np-webhook-10-26 \
  --image gcr.io/telepay-459221/np-webhook-10-26 \
  --region=us-east1 \
  --platform=managed
```

### Step 3: Trigger Test IPN
```bash
# Option A: Make real test payment
# Option B: Use NowPayments sandbox
# Option C: Manually trigger IPN with curl (if signature available)
```

### Step 4: Monitor and Verify
```bash
# Watch logs in real-time
gcloud run services logs tail np-webhook-10-26 --region=us-east1

# Check for successful updates
# Query database for newly stored payment_ids
```

---

## Rollback Plan

### If Deployment Fails

1. **Immediate:** Revert to previous version
   ```bash
   gcloud run services update-traffic np-webhook-10-26 \
     --to-revisions=PREVIOUS_REVISION=100 \
     --region=us-east1
   ```

2. **Investigation:** Check logs for specific error
   ```bash
   gcloud run services logs read np-webhook-10-26 \
     --region=us-east1 \
     --limit=100
   ```

3. **Fix and Redeploy:** Address issue and redeploy

---

## Additional Safeguards

### Monitoring Alerts
- [ ] Set up alert for IPN webhook 500 errors
- [ ] Set up alert for missing payment_id after X minutes
- [ ] Set up daily report of successful payment_id captures

### Documentation Updates
- [ ] Update `NOWPAYMENTS_IMPLEMENTATION_SUMMARY.md` with new order_id format
- [ ] Document channel ID mapping in `MAIN_ARCHITECTURE_WORKFLOW.md`
- [ ] Add troubleshooting guide for IPN failures

---

## Success Criteria

- ✅ Order IDs generated with `|` separator
- ✅ IPN webhook correctly parses negative channel IDs
- ✅ Database lookup finds correct closed_channel_id
- ✅ Payment IDs successfully stored in database
- ✅ No 500 errors from IPN webhook (except legitimate retries)
- ✅ 100% payment_id capture rate

---

## Notes

### Why Not Just Fix the Database?
**Question:** Why not store `open_channel_id` in `private_channel_users_database`?

**Answer:**
- Database schema is normalized: one channel relationship per subscription
- `private_channel_users_database` tracks private channel access (closed_channel_id)
- `main_clients_database` holds the channel mapping (open → closed)
- Changing schema would require:
  - Migration script
  - Update all services reading this table
  - Risk of breaking existing functionality
- **Fixing the webhook is safer and faster**

### Why Use `|` Separator?
- Cannot appear in Telegram user IDs (numbers only)
- Cannot appear in Telegram channel IDs (negative numbers only)
- Easy to parse: `split('|')` is unambiguous
- Visually distinct from `-` which has meaning in negative numbers

### Backward Compatibility Window
- Support old format for 7 days after deployment
- Monitor for any old-format order IDs in logs
- After 7 days, can remove fallback parsing if no old orders seen

---

## Related Issues

This fix enables:
- ✅ Payment ID storage (immediate benefit)
- ✅ Fee discrepancy resolution (depends on payment_id)
- ✅ NowPayments API reconciliation
- ✅ Customer support for payment disputes

---

**END OF CHECKLIST**
