# Bug Tracker - TelegramFunnel OCTOBER/10-26

**Last Updated:** 2025-11-01 (Archived previous entries to BUGS_ARCH.md)

---

## Active Bugs

*No active bugs currently*

---

## Recently Fixed

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
