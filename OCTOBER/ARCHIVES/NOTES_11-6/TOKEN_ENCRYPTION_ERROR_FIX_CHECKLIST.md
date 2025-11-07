# Token Encryption Error Fix Checklist

**Issue:** Token encryption failing in GCWebhook1 with "required argument is not an integer"
**Error:** `❌ [TOKEN] Error encrypting token for GCWebhook2: required argument is not an integer`
**Root Cause:** Database column name mismatch in np-webhook causing None values to be passed to token encryption
**Created:** 2025-11-02

---

## Problem Analysis

### Error Details
```
📱 [VALIDATED] Queuing Telegram invite to GCWebhook2
❌ [TOKEN] Error encrypting token for GCWebhook2: required argument is not an integer
❌ [VALIDATED] Failed to encrypt token for GCWebhook2
❌ [VALIDATED] Unexpected error: 500 Internal Server Error: Token encryption failed
```

### Root Cause Chain

**1. Database Column Name Mismatch (np-webhook)**
- **File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/app.py`
- **Line 619:** Querying for `subscription_time` and `subscription_price`
- **Actual columns:** `sub_time` and `sub_price`
- **Result:** Query returns `None` for both fields

**2. None Values Passed to GCWebhook1**
- np-webhook sends: `subscription_time_days=None`, `subscription_price=None`
- GCWebhook1 receives and passes these None values to token encryption

**3. Token Encryption Fails (GCWebhook1)**
- **File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py`
- **Line 228:** `struct.pack(">H", subscription_time_days)` expects integer, gets None
- **Error:** "required argument is not an integer"

### Database Schema (VERIFIED)
```sql
Table: private_channel_users_database

Correct column names:
- sub_time (smallint) ❌ NOT subscription_time
- sub_price (character varying) ❌ NOT subscription_price
```

---

## Fix Checklist

### ✅ Step 1: Fix np-webhook Database Query
**Action:** Update column names in database query
**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/app.py`
**Lines:** 618-619

**Change:**
```python
# BEFORE (line 618-619):
SELECT wallet_address, payout_currency, payout_network,
       subscription_time, subscription_price

# AFTER:
SELECT wallet_address, payout_currency, payout_network,
       sub_time, sub_price
```

**Status:** Pending

---

### ✅ Step 2: Add Missing Columns to Query
**Action:** Include wallet_address, payout_currency, payout_network from correct columns
**Analysis Required:** Check if these column names are also wrong

**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/app.py`
**Lines:** 618-623

**Database Schema Check:**
```sql
-- Need to verify these columns exist:
- wallet_address
- payout_currency
- payout_network
```

**Status:** Pending

---

### ✅ Step 3: Add Defensive Type Checking in GCWebhook1
**Action:** Add validation to handle None values gracefully
**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py`
**Lines:** 367-375

**Change:**
```python
# BEFORE (line 367-375):
encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_time_days=subscription_time_days,
    subscription_price=subscription_price
)

# AFTER:
# Validate subscription data before encryption
if not subscription_time_days or not subscription_price:
    print(f"❌ [VALIDATED] Missing subscription data:")
    print(f"   subscription_time_days: {subscription_time_days}")
    print(f"   subscription_price: {subscription_price}")
    abort(400, "Missing subscription data from payment")

encrypted_token = token_manager.encrypt_token_for_gcwebhook2(
    user_id=user_id,
    closed_channel_id=closed_channel_id,
    wallet_address=wallet_address,
    payout_currency=payout_currency,
    payout_network=payout_network,
    subscription_time_days=subscription_time_days,
    subscription_price=subscription_price
)
```

**Status:** Pending

---

### ✅ Step 4: Add Defensive Type Checking in token_manager.py
**Action:** Add type validation and default values
**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py`
**Lines:** 210-229

**Change:**
```python
# BEFORE (line 210-229):
try:
    # Convert IDs to 48-bit format (handle negative IDs)
    if user_id < 0:
        user_id += 2**48
    if closed_channel_id < 0:
        closed_channel_id += 2**48

    # Get current timestamp in minutes (for 16-bit wrap-around)
    current_time = int(time.time())
    timestamp_minutes = (current_time // 60) % 65536

    # Build token data
    packed_data = bytearray()

    # Add fixed fields
    packed_data.extend(user_id.to_bytes(6, 'big'))
    packed_data.extend(closed_channel_id.to_bytes(6, 'big'))
    packed_data.extend(struct.pack(">H", timestamp_minutes))
    packed_data.extend(struct.pack(">H", subscription_time_days))

# AFTER:
try:
    # Validate input types
    if not isinstance(user_id, int):
        raise ValueError(f"user_id must be integer, got {type(user_id)}")
    if not isinstance(closed_channel_id, int):
        raise ValueError(f"closed_channel_id must be integer, got {type(closed_channel_id)}")
    if not isinstance(subscription_time_days, int):
        raise ValueError(f"subscription_time_days must be integer, got {type(subscription_time_days)}: {subscription_time_days}")
    if not isinstance(subscription_price, str):
        raise ValueError(f"subscription_price must be string, got {type(subscription_price)}: {subscription_price}")

    # Convert IDs to 48-bit format (handle negative IDs)
    if user_id < 0:
        user_id += 2**48
    if closed_channel_id < 0:
        closed_channel_id += 2**48

    # Get current timestamp in minutes (for 16-bit wrap-around)
    current_time = int(time.time())
    timestamp_minutes = (current_time // 60) % 65536

    # Build token data
    packed_data = bytearray()

    # Add fixed fields
    packed_data.extend(user_id.to_bytes(6, 'big'))
    packed_data.extend(closed_channel_id.to_bytes(6, 'big'))
    packed_data.extend(struct.pack(">H", timestamp_minutes))
    packed_data.extend(struct.pack(">H", subscription_time_days))
```

**Status:** Pending

---

### ✅ Step 5: Verify All Database Column Names in np-webhook
**Action:** Check what columns actually exist for wallet/payout data
**Command:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/tools
/mnt/c/Users/YossTech/Desktop/2025/.venv/bin/python3 -c "
from google.cloud.sql.connector import Connector
import pg8000

conn = Connector().connect(
    'telepay-459221:us-central1:telepaypsql',
    'pg8000',
    user='postgres',
    password='Chigdabeast123\$',
    db='client_table'
)
cur = conn.cursor()
cur.execute('''
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = '\''private_channel_users_database'\''
    AND column_name LIKE '\''%wallet%'\''
       OR column_name LIKE '\''%payout%'\''
       OR column_name LIKE '\''%currency%'\''
       OR column_name LIKE '\''%network%'\''
    ORDER BY column_name
''')
for row in cur.fetchall():
    print(row[0])
"
```

**Status:** Pending

---

### ✅ Step 6: Update np-webhook Column Names for All Fields
**Action:** Fix ALL column name mismatches based on Step 5 findings
**File:** `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/app.py`
**Lines:** 616-638

**Expected columns to check:**
- `wallet_address` → might be `payout_wallet` or similar
- `payout_currency` → verify exact name
- `payout_network` → verify exact name
- `subscription_time` → should be `sub_time` ✅
- `subscription_price` → should be `sub_price` ✅

**Status:** Pending

---

### ✅ Step 7: Check for Similar Issues in Other Services
**Action:** Audit all services that query private_channel_users_database
**Services to check:**
- [x] GCWebhook1-10-26 (doesn't query this table directly)
- [ ] GCWebhook2-10-26 (check if it queries this table)
- [ ] GCSplit1-10-26 (check if it queries this table)
- [ ] GCAccumulator-10-26 (check if it queries this table)
- [ ] GCBatchProcessor-10-26 (check if it queries this table)
- [ ] TelePay10-26 bot (might have correct column names)

**Command:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26
grep -r "subscription_time\|subscription_price" --include="*.py" | grep -v ".md"
```

**Status:** Pending

---

### ✅ Step 8: Rebuild and Redeploy np-webhook
**Action:** Deploy fixed np-webhook service
**Command:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26

gcloud run deploy np-webhook-10-26 \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-secrets=NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest \
  --memory=512Mi \
  --timeout=300
```

**Status:** Pending

---

### ✅ Step 9: Rebuild and Redeploy GCWebhook1
**Action:** Deploy GCWebhook1 with defensive type checking
**Command:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26

gcloud run deploy gcwebhook1-10-26 \
  --source . \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-secrets=SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCSPLIT1_QUEUE=GCSPLIT1_QUEUE:latest,GCSPLIT1_URL=GCSPLIT1_URL:latest,GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest,GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest,GCWEBHOOK2_QUEUE=GCWEBHOOK2_QUEUE:latest,GCWEBHOOK2_URL=GCWEBHOOK2_URL:latest \
  --memory=512Mi \
  --timeout=300
```

**Status:** Pending

---

### ✅ Step 10: Verify Fix in Production Logs
**Action:** Monitor logs for successful token encryption
**Expected Logs:**
```
✅ [ORCHESTRATION] Successfully enqueued to GCWebhook1 (np-webhook)
🔐 [TOKEN] Encrypted token for GCWebhook2 (length: XXX) (gcwebhook1)
✅ [VALIDATED] Enqueued Telegram invite to GCWebhook2 (gcwebhook1)
```

**Commands:**
```bash
# Check np-webhook logs
gcloud run services logs tail np-webhook-10-26 --region=us-central1 | grep -E "ORCHESTRATION|ERROR"

# Check GCWebhook1 logs
gcloud run services logs tail gcwebhook1-10-26 --region=us-central1 | grep -E "TOKEN|VALIDATED|ERROR"
```

**Status:** Pending

---

## Verification Plan

### Test 1: Database Query Returns Correct Data
**Check:** np-webhook fetches actual values (not None)
**Expected:**
```
Subscription Days: 30 (not None)
Declared Price: $5.00 (not None)
```

### Test 2: Token Encryption Succeeds
**Check:** GCWebhook1 encrypts token successfully
**Expected:**
```
🔐 [TOKEN] Encrypted token for GCWebhook2 (length: 100+)
```

### Test 3: End-to-End Flow
**Check:** Payment flows from np-webhook → GCWebhook1 → GCWebhook2
**Expected:**
- np-webhook validates payment ✅
- np-webhook triggers GCWebhook1 ✅
- GCWebhook1 encrypts token ✅
- GCWebhook1 queues to GCWebhook2 ✅

---

## Related Files

### Files to Modify:
1. `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26/app.py` (lines 618-619)
2. `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/tph1-10-26.py` (lines 367-375)
3. `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook1-10-26/token_manager.py` (lines 210-229)

### Database:
- Instance: `telepay-459221:us-central1:telepaypsql`
- Database: `client_table`
- Table: `private_channel_users_database`
- Columns: `sub_time`, `sub_price` (NOT subscription_time, subscription_price)

---

## Expected Outcome
✅ np-webhook queries correct database columns
✅ np-webhook sends valid subscription data to GCWebhook1
✅ GCWebhook1 validates data before token encryption
✅ Token encryption succeeds with proper integer/string types
✅ Telegram invite successfully queued to GCWebhook2
✅ No token encryption errors in any service
