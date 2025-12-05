# 📬 Notification Message Refactor - Architecture & Verification Checklist

## 📋 Overview

**Goal:** Refactor payment notification messages sent to channel owners to:
1. ✅ Remove NowPayments branding → Replace with PayGatePrime branding
2. ✅ Remove Payment Amount section (crypto amount & USD value)
3. ✅ Add Payout Method section showing client's payout configuration
4. ✅ For THRESHOLD mode: Show live progress tracking (`current_paid_amount / payout_threshold_usd`)

---

## 🎯 Current vs Desired Notification Format

### ❌ Current Format (Example from test)
```
🎉 New Subscription Payment!

Channel: 11-11 SHIBA CLOSED INSTANT
Channel ID: -1003202734748

Customer: User ID: 6271402111
User ID: 6271402111

Subscription Details:
├ Tier: 1
├ Price: $2.55 USD
└ Duration: 30 days

Payment Amount:               ← REMOVE THIS SECTION
├ Crypto: 0.00034 ETH
└ USD Value: $1.0856438000000002

Timestamp: N/A

✅ Payment confirmed via NowPayments IPN   ← CHANGE BRANDING
```

### ✅ Desired Format - INSTANT Mode
```
🎉 New Subscription Payment!

Channel: 11-11 SHIBA CLOSED INSTANT
Channel ID: -1003202734748

Customer: User ID: 6271402111

Subscription Details:
├ Tier: 1
├ Price: $2.55 USD
└ Duration: 30 days

Payout Method: INSTANT                    ← NEW SECTION
├ Currency: SHIB
├ Network: ETH
└ Wallet: 0x249A83b498acE1177920566CE83CADA0A56F69D8

Timestamp: 2025-11-14 12:34:56 UTC

✅ Payment confirmed via PayGatePrime      ← NEW BRANDING
```

### ✅ Desired Format - THRESHOLD Mode
```
🎉 New Subscription Payment!

Channel: Premium Content Channel
Channel ID: -1001234567890

Customer: User ID: 6271402111

Subscription Details:
├ Tier: 2
├ Price: $10.00 USD
└ Duration: 30 days

Payout Method: THRESHOLD                   ← NEW SECTION
├ Currency: USDT
├ Network: TRX
├ Wallet: TXyz123...abc
├ Threshold: $100.00 USD
└ Progress: $47.50 / $100.00 (47.5%)      ← LIVE TRACKING

Timestamp: 2025-11-14 12:34:56 UTC

✅ Payment confirmed via PayGatePrime      ← NEW BRANDING
```

---

## 🗄️ Database Schema Analysis

### ✅ main_clients_database Table
**Payout-related columns available:**
```sql
- client_wallet_address           VARCHAR      -- e.g., "0x249A83b498acE1177920566CE83CADA0A56F69D8"
- client_payout_currency          ENUM         -- e.g., "SHIB", "USDT", "ETH"
- client_payout_network           ENUM         -- e.g., "ETH", "TRX", "BSC"
- payout_strategy                 VARCHAR      -- "instant" or "threshold"
- payout_threshold_usd            NUMERIC      -- e.g., 100.00 (NULL for instant mode)
- payout_threshold_updated_at     TIMESTAMP
```

### ✅ payout_accumulation Table
**Columns for tracking threshold progress:**
```sql
- client_id                       VARCHAR      -- FK to main_clients_database
- user_id                         BIGINT       -- Subscriber's Telegram ID
- subscription_id                 INTEGER
- payment_amount_usd              NUMERIC      -- This payment's USD value
- accumulated_amount_usdt         NUMERIC      -- Total accumulated (post-conversion)
- client_wallet_address           VARCHAR
- client_payout_currency          VARCHAR
- client_payout_network           VARCHAR
- is_paid_out                     BOOLEAN      -- FALSE until payout threshold reached
- created_at                      TIMESTAMP
```

**Key Query for Threshold Progress:**
```sql
-- Get current accumulated amount for a client
SELECT
    COALESCE(SUM(payment_amount_usd), 0) as current_accumulated
FROM payout_accumulation
WHERE client_id = :open_channel_id
  AND is_paid_out = FALSE;
```

---

## 🏗️ Architecture Changes Required

### 1️⃣ **GCNotificationService - database_manager.py**

#### ✅ Add New Method: `get_payout_configuration()`
```python
def get_payout_configuration(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
    """
    Get payout configuration for notification message (NEW_ARCHITECTURE pattern)

    Returns:
        {
            "payout_strategy": str,        # "instant" or "threshold"
            "wallet_address": str,
            "payout_currency": str,        # "SHIB", "USDT", etc.
            "payout_network": str,         # "ETH", "TRX", "BSC", etc.
            "threshold_usd": Decimal       # NULL for instant mode
        }
    """
```

**SQL Query:**
```sql
SELECT
    payout_strategy,
    client_wallet_address,
    client_payout_currency::text,
    client_payout_network::text,
    payout_threshold_usd
FROM main_clients_database
WHERE open_channel_id = :open_channel_id
```

#### ✅ Add New Method: `get_threshold_progress()`
```python
def get_threshold_progress(self, open_channel_id: str) -> Optional[Decimal]:
    """
    Get current accumulated amount for threshold payout mode

    Returns:
        Decimal: Total accumulated USD not yet paid out
    """
```

**SQL Query:**
```sql
SELECT COALESCE(SUM(payment_amount_usd), 0) as current_accumulated
FROM payout_accumulation
WHERE client_id = :open_channel_id
  AND is_paid_out = FALSE
```

---

### 2️⃣ **GCNotificationService - notification_handler.py**

#### ✅ Update Method: `_format_notification_message()`

**Current Implementation (Lines 106-199):**
- Builds message with `amount_crypto`, `amount_usd`, `crypto_currency`
- Shows "Payment confirmed via NowPayments IPN"

**New Implementation:**

1. **Remove these fields from message:**
   ```python
   # DELETE:
   amount_crypto = payment_data.get('amount_crypto', '0')
   amount_usd = payment_data.get('amount_usd', '0')
   crypto_currency = payment_data.get('crypto_currency', 'CRYPTO')
   ```

2. **Add payout configuration fetching:**
   ```python
   # NEW: Fetch payout configuration
   payout_config = self.db_manager.get_payout_configuration(open_channel_id)
   ```

3. **Build payout section based on strategy:**
   ```python
   if payout_config:
       payout_strategy = payout_config['payout_strategy']

       if payout_strategy == 'instant':
           payout_section = f"""<b>Payout Method:</b> INSTANT
   ├ Currency: {payout_config['payout_currency']}
   ├ Network: {payout_config['payout_network']}
   └ Wallet: <code>{payout_config['wallet_address']}</code>"""

       elif payout_strategy == 'threshold':
           # Get current accumulated amount
           current_accumulated = self.db_manager.get_threshold_progress(open_channel_id)
           threshold_usd = payout_config['threshold_usd']

           # Calculate percentage
           if threshold_usd and threshold_usd > 0:
               progress_percent = (current_accumulated / threshold_usd) * 100
           else:
               progress_percent = 0

           payout_section = f"""<b>Payout Method:</b> THRESHOLD
   ├ Currency: {payout_config['payout_currency']}
   ├ Network: {payout_config['payout_network']}
   ├ Wallet: <code>{payout_config['wallet_address']}</code>
   ├ Threshold: ${threshold_usd} USD
   └ Progress: ${current_accumulated} / ${threshold_usd} ({progress_percent:.1f}%)"""

       else:
           payout_section = "<b>Payout Method:</b> Not configured"
   else:
       payout_section = "<b>Payout Method:</b> Not available"
   ```

4. **Update branding:**
   ```python
   # OLD:
   ✅ Payment confirmed via NowPayments IPN

   # NEW:
   ✅ Payment confirmed via PayGatePrime
   ```

5. **Remove duplicate User ID line:**
   ```python
   # OLD:
   <b>Customer:</b> {user_display}
   <b>User ID:</b> <code>{user_id}</code>

   # NEW:
   <b>Customer:</b> User ID: <code>{user_id}</code>
   ```

---

### 3️⃣ **np-webhook-10-26 - app.py**

#### ✅ Update Notification Payload (Lines 947-1000)

**No changes needed** - np-webhook doesn't need to know about payout configuration.
The notification handler in GCNotificationService will fetch payout details independently.

**Current payload will remain:**
```python
notification_payload = {
    'open_channel_id': str(open_channel_id),
    'payment_type': payment_type,
    'payment_data': {
        'user_id': user_id,
        'username': None,
        'amount_crypto': str(outcome_amount),      # Still sent but not displayed
        'amount_usd': str(outcome_amount_usd),    # Still sent but not displayed
        'crypto_currency': str(outcome_currency),  # Still sent but not displayed
        'timestamp': payment_data.get('created_at', 'N/A'),
        'tier': tier,                              # For subscription only
        'tier_price': str(subscription_price),     # For subscription only
        'duration_days': subscription_time_days    # For subscription only
    }
}
```

**Rationale:** Keep payment amounts in payload for potential audit/logging, but notification handler won't display them.

---

## 🧪 Testing Strategy

### Test Case 1: Instant Payout Mode
**Channel:** `-1003202734748` (11-11 SHIBA CLOSED INSTANT)
**Configuration:**
- payout_strategy: `instant`
- client_wallet_address: `0x249A83b498acE1177920566CE83CADA0A56F69D8`
- client_payout_currency: `SHIB`
- client_payout_network: `ETH`
- payout_threshold_usd: `NULL`

**Expected Notification:**
```
🎉 New Subscription Payment!

Channel: 11-11 SHIBA CLOSED INSTANT
Channel ID: -1003202734748

Customer: User ID: 6271402111

Subscription Details:
├ Tier: 1
├ Price: $2.55 USD
└ Duration: 30 days

Payout Method: INSTANT
├ Currency: SHIB
├ Network: ETH
└ Wallet: 0x249A83b498acE1177920566CE83CADA0A56F69D8

Timestamp: 2025-11-14 12:34:56 UTC

✅ Payment confirmed via PayGatePrime
```

**Verification Steps:**
```bash
# 1. Run test notification flow
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tools
DB_PASSWORD=$(gcloud secrets versions access latest --secret="DATABASE_PASSWORD_SECRET") \
NOWPAYMENTS_IPN_SECRET=$(gcloud secrets versions access latest --secret="NOWPAYMENTS_IPN_SECRET") \
python3 test_notification_flow.py

# 2. Check GCNotificationService logs
gcloud logging read 'resource.labels.service_name="gcnotificationservice-10-26"' \
  --limit 30 \
  --project=telepay-459221 \
  --format=json

# 3. Verify Telegram message received by user 6271402111
```

---

### Test Case 2: Threshold Payout Mode

**Setup Required:**
1. Create or identify a channel with threshold payout configuration
2. Manually insert test records into `payout_accumulation` to simulate accumulated payments

**SQL Setup:**
```sql
-- Find a threshold-configured channel
SELECT
    open_channel_id,
    closed_channel_title,
    payout_strategy,
    payout_threshold_usd,
    client_payout_currency::text,
    client_payout_network::text,
    client_wallet_address
FROM main_clients_database
WHERE payout_strategy = 'threshold'
LIMIT 1;

-- If none exist, update test channel temporarily:
UPDATE main_clients_database
SET
    payout_strategy = 'threshold',
    payout_threshold_usd = 100.00,
    client_payout_currency = 'USDT',
    client_payout_network = 'TRX'
WHERE open_channel_id = '-1003202734748';

-- Insert mock accumulated payments (total $47.50)
INSERT INTO payout_accumulation (
    client_id,
    user_id,
    payment_amount_usd,
    is_paid_out,
    created_at
) VALUES
    ('-1003202734748', 6271402111, 25.00, FALSE, NOW() - INTERVAL '2 days'),
    ('-1003202734748', 6271402111, 15.50, FALSE, NOW() - INTERVAL '1 day'),
    ('-1003202734748', 6271402111, 7.00, FALSE, NOW());
```

**Expected Notification:**
```
🎉 New Subscription Payment!

Channel: 11-11 SHIBA CLOSED INSTANT
Channel ID: -1003202734748

Customer: User ID: 6271402111

Subscription Details:
├ Tier: 1
├ Price: $2.55 USD
└ Duration: 30 days

Payout Method: THRESHOLD
├ Currency: USDT
├ Network: TRX
├ Wallet: 0x249A83b498acE1177920566CE83CADA0A56F69D8
├ Threshold: $100.00 USD
└ Progress: $47.50 / $100.00 (47.5%)

Timestamp: 2025-11-14 12:34:56 UTC

✅ Payment confirmed via PayGatePrime
```

**Verification Steps:**
```bash
# 1. Send test IPN
python3 test_notification_flow.py

# 2. Verify accumulated amount calculation
python3 << 'EOF'
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text, pool
import os

db_password = os.popen('gcloud secrets versions access latest --secret="DATABASE_PASSWORD_SECRET"').read().strip()
connector = Connector()

def getconn():
    return connector.connect(
        "telepay-459221:us-central1:telepaypsql",
        "pg8000",
        user="postgres",
        password=db_password,
        db="client_table"
    )

engine = create_engine("postgresql+pg8000://", creator=getconn, poolclass=pool.NullPool)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT
            COALESCE(SUM(payment_amount_usd), 0) as current_accumulated,
            COUNT(*) as payment_count
        FROM payout_accumulation
        WHERE client_id = '-1003202734748'
          AND is_paid_out = FALSE
    """))
    row = result.fetchone()
    print(f"Current Accumulated: ${row[0]}")
    print(f"Payment Count: {row[1]}")

connector.close()
EOF
```

---

### Test Case 3: Missing Payout Configuration

**Test Scenario:** Channel exists but has NULL payout configuration

**Expected Notification:**
```
🎉 New Subscription Payment!

Channel: Test Channel
Channel ID: -1001234567890

Customer: User ID: 6271402111

Subscription Details:
├ Tier: 1
├ Price: $5.00 USD
└ Duration: 30 days

Payout Method: Not configured

Timestamp: 2025-11-14 12:34:56 UTC

✅ Payment confirmed via PayGatePrime
```

---

## 📝 Implementation Checklist

### Phase 1: Database Layer (database_manager.py)
- [ ] Add `get_payout_configuration()` method with SQLAlchemy text() pattern
- [ ] Add `get_threshold_progress()` method with SQLAlchemy text() pattern
- [ ] Test both methods independently with known channel IDs
- [ ] Verify NULL handling for instant mode (threshold_usd = NULL)
- [ ] Verify 0.00 accumulated amount for new channels

### Phase 2: Notification Handler (notification_handler.py)
- [ ] Update `_format_notification_message()` signature (no changes needed)
- [ ] Remove `amount_crypto`, `amount_usd`, `crypto_currency` from message formatting
- [ ] Add `payout_config = self.db_manager.get_payout_configuration(open_channel_id)` call
- [ ] Implement instant mode payout section
- [ ] Implement threshold mode payout section with progress calculation
- [ ] Handle NULL/missing payout configuration gracefully
- [ ] Update branding: "NowPayments IPN" → "PayGatePrime"
- [ ] Remove duplicate "User ID" line from customer section
- [ ] Test with mock payout configurations

### Phase 3: Testing & Verification
- [ ] Test Case 1: Instant mode with real channel `-1003202734748`
- [ ] Test Case 2: Threshold mode (setup test data in payout_accumulation)
- [ ] Test Case 3: Missing payout configuration
- [ ] Test Case 4: Donation payment (verify it also uses new format)
- [ ] Verify no changes needed in np-webhook (payload remains the same)
- [ ] Check all emoji formatting renders correctly in Telegram
- [ ] Verify HTML parsing works (especially `<code>` tags for wallet addresses)

### Phase 4: Deployment
- [ ] Update `requirements.txt` if any new dependencies added (none expected)
- [ ] Deploy GCNotificationService with updated code
- [ ] Monitor logs for any errors during first real notifications
- [ ] Verify with channel owner that new format is displayed correctly

### Phase 5: Documentation
- [ ] Update PROGRESS.md with Session 157 entry
- [ ] Update DECISIONS.md with architectural decision
- [ ] Update NOTIFICATION_WORKFLOW_REPORT.md if needed
- [ ] Document new database methods in code comments

---

## 🔍 Edge Cases to Handle

### 1. Wallet Address Truncation (Long addresses)
```python
# For display, truncate long addresses:
wallet_display = wallet_address
if len(wallet_address) > 48:
    wallet_display = f"{wallet_address[:20]}...{wallet_address[-20:]}"
```

### 2. Decimal Precision for Progress
```python
# Use 2 decimal places for USD amounts
progress_percent = round((current_accumulated / threshold_usd) * 100, 1)
current_accumulated_str = f"{current_accumulated:.2f}"
threshold_usd_str = f"{threshold_usd:.2f}"
```

### 3. NULL Threshold (Instant Mode)
```python
if payout_strategy == 'threshold' and not threshold_usd:
    # Misconfigured - threshold mode but no threshold set
    payout_section = "<b>Payout Method:</b> THRESHOLD (misconfigured - no threshold set)"
```

### 4. Accumulation Query Returns None
```python
current_accumulated = self.db_manager.get_threshold_progress(open_channel_id)
if current_accumulated is None:
    current_accumulated = Decimal('0.00')
```

### 5. Division by Zero
```python
if threshold_usd and threshold_usd > 0:
    progress_percent = (current_accumulated / threshold_usd) * 100
else:
    progress_percent = 0
```

---

## 🎨 Branding Changes Summary

| Old Text | New Text |
|----------|----------|
| `✅ Payment confirmed via NowPayments IPN` | `✅ Payment confirmed via PayGatePrime` |
| Shows crypto amount & USD value | Hidden from notification |
| Generic payment confirmation | Shows payout method configuration |

---

## 📊 Database Queries Required

### Query 1: Get Payout Configuration
```sql
SELECT
    payout_strategy,
    client_wallet_address,
    client_payout_currency::text,
    client_payout_network::text,
    payout_threshold_usd
FROM main_clients_database
WHERE open_channel_id = :open_channel_id
```

### Query 2: Get Threshold Progress
```sql
SELECT COALESCE(SUM(payment_amount_usd), 0) as current_accumulated
FROM payout_accumulation
WHERE client_id = :open_channel_id
  AND is_paid_out = FALSE
```

### Query 3: Test Data Verification
```sql
-- Verify test channel configuration
SELECT
    open_channel_id,
    closed_channel_title,
    payout_strategy,
    client_wallet_address,
    client_payout_currency::text,
    client_payout_network::text,
    payout_threshold_usd
FROM main_clients_database
WHERE open_channel_id = '-1003202734748';

-- Verify accumulated amounts
SELECT
    client_id,
    COUNT(*) as payment_count,
    SUM(payment_amount_usd) as total_accumulated,
    SUM(CASE WHEN is_paid_out = FALSE THEN payment_amount_usd ELSE 0 END) as unpaid_accumulated
FROM payout_accumulation
WHERE client_id = '-1003202734748'
GROUP BY client_id;
```

---

## ⚠️ Important Considerations

### 1. **Performance Impact**
- Each notification now requires **2 additional database queries**:
  1. `get_payout_configuration()` - Always executed
  2. `get_threshold_progress()` - Only for threshold mode
- **Impact:** Minimal - notification service is already async and fail-open
- **Mitigation:** Use SQLAlchemy connection pool (already implemented)

### 2. **Consistency with Payment Processing**
- Payout configuration must be set **before** users can subscribe
- Already enforced by GCRegisterWeb registration flow
- No changes needed to existing validation

### 3. **Backward Compatibility**
- Old payments in database still work - we're only changing notification format
- No schema migrations required
- Existing payout_accumulation records unaffected

### 4. **Security Considerations**
- Wallet addresses shown in plaintext in Telegram messages
- **Safe:** These are receive-only addresses, not private keys
- **Safe:** Notification sent only to channel owner (verified by notification_id)

### 5. **Future Enhancements** (Not in this checklist)
- Add currency formatting (e.g., SHIB with 18 decimals → human-readable)
- Add estimated payout date based on average payment velocity
- Add link to PayGatePrime dashboard for detailed view

---

## 🚀 Deployment Commands

```bash
# Navigate to service directory
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26

# Build and deploy
gcloud run deploy gcnotificationservice-10-26 \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars CLOUD_SQL_CONNECTION_NAME="telepay-459221:us-central1:telepaypsql" \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql \
  --project=telepay-459221

# Monitor deployment
gcloud run services describe gcnotificationservice-10-26 \
  --region us-central1 \
  --project=telepay-459221

# Check logs after first notification
gcloud logging read 'resource.labels.service_name="gcnotificationservice-10-26"' \
  --limit 50 \
  --project=telepay-459221
```

---

## ✅ Verification Criteria

Before marking this task as complete, verify:

1. ✅ **Instant Mode Notification:**
   - Shows "Payout Method: INSTANT"
   - Displays currency, network, wallet address
   - No payment amounts visible
   - Branding shows "PayGatePrime"

2. ✅ **Threshold Mode Notification:**
   - Shows "Payout Method: THRESHOLD"
   - Displays currency, network, wallet address
   - Shows threshold amount
   - Shows live progress ($ amount and percentage)
   - Progress calculation is accurate

3. ✅ **Code Quality:**
   - NEW_ARCHITECTURE pattern (SQLAlchemy text())
   - Proper error handling for NULL values
   - Edge cases handled (division by zero, long addresses)
   - Emoji formatting renders correctly

4. ✅ **Testing:**
   - Test script executes successfully
   - Real Telegram message received
   - Logs show no errors
   - Database queries perform efficiently

5. ✅ **Documentation:**
   - PROGRESS.md updated
   - DECISIONS.md updated
   - Code comments explain new methods

---

## 📌 Notes

- **No changes to np-webhook** - it continues sending the same payload
- **No database migrations** - we're only reading existing columns
- **No changes to payout processing logic** - this is display-only
- **Fail-open pattern maintained** - notification failures don't block payments

---

## 🎯 Success Metrics

After deployment, verify:
- [ ] All notifications show PayGatePrime branding
- [ ] No payment amounts displayed to users
- [ ] Instant mode shows wallet configuration
- [ ] Threshold mode shows live progress
- [ ] No errors in GCNotificationService logs
- [ ] Channel owners confirm new format is clear and useful

---

**Ready for Implementation?** ✅
- Architecture is clear
- Database queries are defined
- Edge cases are documented
- Testing strategy is comprehensive
- Deployment steps are outlined

**Proceed with implementation?** (Awaiting user approval)
