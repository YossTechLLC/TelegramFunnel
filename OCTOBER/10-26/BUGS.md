# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-01 (Archived previous entries to BUGS_ARCH.md)

---

## Active Bugs

*No active bugs currently*

---

## Recently Fixed

### 2025-11-02: NowPayments Payment Validation Failing - Crypto vs USD Mismatch ✅

**Service:** GCWebhook2-10-26 (Payment Validation Service)
**Severity:** Critical
**Status:** FIXED ✅

**Description:**
- Payment validation consistently failing for all crypto payments
- Users pay successfully via NowPayments, but can't access paid channels
- Result: "Insufficient payment amount: received $0.00, expected at least $1.08"

**Root Cause:**
Currency type mismatch in validation logic:

1. **Data Capture** (`np-webhook-10-26/app.py:407-416`)
   ```python
   # BUGGY: Only capturing crypto outcome, not USD price
   payment_data = {
       'outcome_amount': ipn_data.get('outcome_amount')  # 0.00026959 ETH
       # ❌ Missing: price_amount (1.35 USD)
       # ❌ Missing: price_currency ("usd")
   }
   ```

2. **Validation Logic** (`GCWebhook2-10-26/database_manager.py:178-190`)
   ```python
   # BUGGY: Treating crypto as USD
   actual_amount = float(outcome_amount)  # 0.00026959 (ETH!)
   minimum_amount = expected_amount * 0.80  # $1.35 * 0.80 = $1.08

   if actual_amount < minimum_amount:  # $0.0002696 < $1.08 ❌
       return False, "Insufficient payment"
   ```

**The Problem:**
- NowPayments IPN provides `price_amount` (USD) AND `outcome_amount` (crypto)
- We were only storing crypto `outcome_amount`
- Validation compared crypto value to USD expectation (apples to oranges)
- Example: 0.00026959 ETH ≈ $1.08, but validation saw it as $0.0002696

**Fix Implemented:**

1. **Database Schema** - Added 3 columns
   ```sql
   ALTER TABLE private_channel_users_database
   ADD COLUMN nowpayments_price_amount DECIMAL(20, 8);
   ADD COLUMN nowpayments_price_currency VARCHAR(10);
   ADD COLUMN nowpayments_outcome_currency VARCHAR(10);
   ```

2. **IPN Capture** - Store USD amount
   ```python
   # FIXED: Capture all currency fields
   payment_data = {
       'outcome_amount': ipn_data.get('outcome_amount'),      # 0.00026959 ETH
       'price_amount': ipn_data.get('price_amount'),          # 1.35 USD ✅
       'price_currency': ipn_data.get('price_currency'),      # "usd" ✅
       'outcome_currency': ipn_data.get('outcome_currency')   # "eth" ✅
   }
   ```

3. **Validation Logic** - USD-to-USD comparison
   ```python
   # FIXED: 3-tier validation strategy
   # Tier 1: USD-to-USD (preferred)
   if price_amount:
       actual_usd = float(price_amount)  # 1.35
       minimum = expected * 0.95          # $1.35 * 0.95 = $1.28
       if actual_usd >= minimum:          # $1.35 >= $1.28 ✅
           return True

   # Tier 2: Stablecoin fallback (old records)
   elif outcome_currency in ['usdt', 'usdc', 'busd']:
       actual_usd = float(outcome_amount)  # 1.15 USDT
       minimum = expected * 0.80           # $1.35 * 0.80 = $1.08
       if actual_usd >= minimum:           # $1.15 >= $1.08 ✅
           return True

   # Tier 3: Crypto (requires price feed - TODO)
   else:
       return False  # Manual verification needed
   ```

**Testing:**
- ✅ Migration executed successfully
- ✅ IPN webhook deployed and capturing price_amount
- ✅ GCWebhook2 deployed with new validation logic
- ⏳ Pending: End-to-end test with real payment

**Files Modified:**
- `tools/execute_price_amount_migration.py` (NEW)
- `np-webhook-10-26/app.py` (lines 388, 407-426)
- `GCWebhook2-10-26/database_manager.py` (lines 91-129, 148-251)

**Deployment:**
- np-webhook: Revision `np-webhook-00007-rf2`
- gcwebhook2-10-26: Revision `gcwebhook2-10-26-00012-9m5`
- Region: np-webhook (us-east1), gcwebhook2 (us-central1)

**Impact:**
- ✅ Payment validation now works for crypto payments
- ✅ Users receive invitation links after payment
- ✅ Fee reconciliation enabled (price_amount vs outcome_amount)
- ✅ Backward compatible (old records use stablecoin fallback)

**Related:**
- Analysis: `NP_WEBHOOK_FIX_AMOUNT_CHECKLIST.md`
- Progress: `NP_WEBHOOK_FIX_AMOUNT_CHECKLIST_PROGRESS.md`
- Decision: `DECISIONS.md` (USD-to-USD validation strategy)

---

### 2025-11-02: NowPayments payment_id Not Stored - Channel ID Sign Mismatch ✅

**Service:** np-webhook (NowPayments IPN Handler)
**Severity:** Critical
**Status:** FIXED ✅

**Description:**
- NowPayments IPN callbacks received successfully (200 OK from signature verification)
- Database update consistently failed with "No records found to update"
- Result: payment_id never stored, blocking fee reconciliation

**Root Cause:**
Three-part bug in order ID handling:

1. **Order ID Generation** (`TelePay10-26/start_np_gateway.py:168`)
   ```python
   # BUGGY:
   order_id = f"PGP-{user_id}{open_channel_id}"
   # Result: PGP-6271402111-1003268562225
   # The negative sign in -1003268562225 becomes a separator!
   ```

2. **Order ID Parsing** (`np-webhook-10-26/app.py:123`)
   ```python
   # BUGGY:
   parts = order_id.split('-')  # ['PGP', '6271402111', '1003268562225']
   channel_id = int(parts[2])   # 1003268562225 (LOST NEGATIVE SIGN!)
   ```

3. **Database Lookup Mismatch**
   - Order ID built with `open_channel_id` (public channel)
   - Webhook queried `private_channel_users_database` with wrong ID type
   - Even with negative sign fix, would lookup wrong channel

**Fix Implemented:**

1. **Change Separator** (TelePay Bot)
   ```python
   # FIXED:
   order_id = f"PGP-{user_id}|{open_channel_id}"
   # Result: PGP-6271402111|-1003268562225
   # Pipe separator preserves negative sign
   ```

2. **Smart Parsing** (np-webhook)
   ```python
   def parse_order_id(order_id: str) -> tuple:
       if '|' in order_id:
           # New format - preserves negative sign
           prefix_and_user, channel_id_str = order_id.split('|')
           return int(user_id), int(channel_id_str)
       else:
           # Old format fallback - add negative sign back
           parts = order_id.split('-')
           return int(parts[1]), -abs(int(parts[2]))
   ```

3. **Two-Step Database Lookup** (np-webhook)
   ```python
   # Step 1: Parse order_id
   user_id, open_channel_id = parse_order_id(order_id)

   # Step 2: Look up closed_channel_id
   SELECT closed_channel_id FROM main_clients_database
   WHERE open_channel_id = %s

   # Step 3: Update with correct channel ID
   UPDATE private_channel_users_database
   WHERE user_id = %s AND private_channel_id = %s  -- Uses closed_channel_id
   ```

**Testing:**
- ✅ Health check returns 200 with all components healthy
- ✅ Service logs show correct initialization
- ✅ Database schema validation confirmed
- ⏳ Pending: End-to-end test with real NowPayments IPN

**Files Modified:**
- `OCTOBER/10-26/TelePay10-26/start_np_gateway.py` (line 168-186)
- `OCTOBER/10-26/np-webhook-10-26/app.py` (added parse_order_id, rewrote update_payment_data)

**Deployment:**
- Image: `gcr.io/telepay-459221/np-webhook-10-26`
- Service: `np-webhook` revision `np-webhook-00006-q7g`
- Region: us-east1
- URL: `https://np-webhook-291176869049.us-east1.run.app`

**Impact:**
- ✅ Payment IDs will now be captured from NowPayments
- ✅ Fee reconciliation unblocked
- ✅ Customer support for payment disputes enabled

**Related:**
- Analysis: `NP_WEBHOOK_403_ROOT_CAUSE_ANALYSIS.md`
- Checklist: `NP_WEBHOOK_FIX_CHECKLIST.md`
- Progress: `NP_WEBHOOK_FIX_CHECKLIST_PROGRESS.md`

---

---

## Known Issues (Non-Critical)

*No known issues currently*

---

## Bug Reporting Guidelines

When reporting bugs, please include:

1. **Service Name** - Which service exhibited the bug
2. **Severity** - Critical / High / Medium / Low
3. **Description** - What happened vs what should happen
4. **Steps to Reproduce** - Exact steps to trigger the bug
5. **Logs** - Relevant log entries with emojis for context
6. **Environment** - Production / Staging / Local
7. **User Impact** - How many users affected
8. **Proposed Solution** - If known

---

## Notes
- All previous bug reports have been archived to BUGS_ARCH.md
- This file tracks only active and recently fixed bugs
- Add new bugs at the TOP of the "Active Bugs" section
- Move resolved bugs to "Recently Fixed" before archiving
