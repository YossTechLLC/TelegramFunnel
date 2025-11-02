# NowPayments Webhook Amount Validation Fix - Comprehensive Checklist

**Created:** 2025-11-02
**Status:** READY FOR IMPLEMENTATION
**Priority:** P0 - Critical Bug - Blocking Payment Validation
**Related:** `NP_WEBHOOK_FIX_CHECKLIST.md` (Channel ID fix)

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
GCWebhook2 payment validation is **failing** because it's comparing cryptocurrency amounts directly to USD amounts:
- **Stored in DB:** `nowpayments_outcome_amount = 0.000269590000000000` (ETH)
- **Validated as:** `$0.00` (treating ETH as USD)
- **Expected:** `$1.08` minimum (80% of $1.35)
- **Result:** ❌ Validation fails: "Insufficient payment amount: received $0.00, expected at least $1.08"

### The Problem Explained

#### Current Log Analysis
```
👤 [TOKEN] User: 6271402111, Channel: 280471680626277
💰 [TOKEN] Price: $1.35, Duration: 15 days
✅ [VALIDATION] Found NowPayments payment_id: 5657058125
📊 [VALIDATION] Payment status: finished
💰 [VALIDATION] Outcome amount: 0.000269590000000000
❌ [VALIDATION] Insufficient payment amount: received $0.00, expected at least $1.08
```

#### What's Happening

**Step 1: NowPayments Invoice Creation** (`TelePay10-26/start_np_gateway.py:73`)
```python
invoice_payload = {
    "price_amount": 1.35,        # USD
    "price_currency": "USD",
    "order_id": "PGP-6271402111|-1003296084379",
    "is_fixed_rate": False,
    "is_fee_paid_by_user": False
}
```

**Step 2: User Pays** (NowPayments processes)
- User pays in ETH (or any crypto)
- NowPayments receives: `0.0003453 ETH`
- NowPayments deducts fees
- Outcome amount (what merchant gets): `0.00026959 ETH`

**Step 3: IPN Callback** (`np-webhook-10-26/app.py`)
```json
{
  "payment_id": "5657058125",
  "payment_status": "finished",
  "pay_amount": "0.0003453",       // What user paid
  "pay_currency": "eth",
  "outcome_amount": "0.00026959",  // What merchant gets (in ETH!)
  "price_amount": "1.35",          // Original USD amount (NOT STORED!)
  "price_currency": "usd"          // Original currency (NOT STORED!)
}
```

**Step 4: Database Storage** (`np-webhook-10-26/app.py:407-416`)
```python
payment_data = {
    'payment_id': ipn_data.get('payment_id'),
    'pay_amount': ipn_data.get('pay_amount'),          # 0.0003453 ETH
    'pay_currency': ipn_data.get('pay_currency'),      # "eth"
    'outcome_amount': ipn_data.get('outcome_amount')   # 0.00026959 ETH
    # ❌ price_amount NOT captured!
    # ❌ price_currency NOT captured!
}
```

**Step 5: Payment Validation** (`GCWebhook2-10-26/database_manager.py:180-190`)
```python
actual_amount = float(outcome_amount)  # 0.00026959
# ❌ TREATING ETH AS USD!

minimum_amount = expected_amount * 0.80  # $1.35 * 0.80 = $1.08

if actual_amount < minimum_amount:  # $0.0002696 < $1.08 ❌ FAILS!
    error_msg = f"Insufficient payment: ${actual_amount:.2f}, expected ${minimum_amount:.2f}"
    return False, error_msg
```

### Root Cause Summary

**Three-Part Problem:**

1. **Missing Data Capture** - IPN handler doesn't store `price_amount` and `price_currency`
2. **Currency Confusion** - `outcome_amount` is in crypto (ETH), not USD
3. **Invalid Comparison** - Validation compares crypto amount directly to USD

**The Fix:** Store and use the correct USD amount from NowPayments IPN.

---

## Impact Assessment

### Current Impact
- ✅ **IPN Reception:** Working - payment_id stored correctly
- ✅ **Payment Status:** Correctly shows "finished"
- ❌ **Amount Validation:** Failing - compares crypto to USD
- ❌ **Invitation Sending:** Blocked - users can't join channels
- ❌ **User Experience:** Broken - users pay but don't get access

### Affected Services
1. **np-webhook-10-26** (PRIMARY) - Missing data capture
2. **GCWebhook2-10-26** (PRIMARY) - Invalid validation logic
3. **Database Schema** (SECONDARY) - Missing columns for price_amount/currency

### Not Affected
- ✅ TelePay bot - Invoice creation works correctly
- ✅ GCWebhook1 - Token flow unchanged
- ✅ Payment processing - NowPayments works fine
- ✅ Other downstream services

---

## Solution Architecture

### Design Principles
1. **Store Original USD Amount:** Capture `price_amount` from IPN
2. **Validate USD to USD:** Compare like currencies
3. **Preserve Crypto Data:** Keep outcome_amount for reconciliation
4. **Backward Compatible:** Handle existing records without price_amount
5. **Crypto Conversion Optional:** Can add crypto-to-USD conversion later

### Proposed Solution: Three-Step Fix

#### Step 1: Database Schema Enhancement
Add missing columns to `private_channel_users_database`:
- `nowpayments_price_amount` (DECIMAL) - Original USD amount
- `nowpayments_price_currency` (VARCHAR) - Original currency ("USD")
- `nowpayments_outcome_currency` (VARCHAR) - Outcome currency (e.g., "eth", "usdt")

#### Step 2: IPN Webhook Enhancement
Update `np-webhook-10-26/app.py` to:
- Capture `price_amount` and `price_currency` from IPN
- Capture `outcome_currency` if available (or infer from pay_currency)
- Store these fields in database

#### Step 3: Validation Logic Fix
Update `GCWebhook2-10-26/database_manager.py` to:
- Use `nowpayments_price_amount` (USD) for validation
- Fallback to crypto conversion if price_amount unavailable
- Add proper currency-aware validation

---

## Implementation Checklist

### Phase 1: Database Schema Migration

**File:** Create new migration script `tools/execute_price_amount_migration.py`

- [ ] **1.1** Create migration script
  ```python
  """
  Add price_amount and currency fields to private_channel_users_database.
  These fields store the original USD invoice amount for payment validation.
  """

  migration_sql = """
  -- Add price amount and currency fields
  ALTER TABLE private_channel_users_database
  ADD COLUMN IF NOT EXISTS nowpayments_price_amount DECIMAL(20, 8);

  ALTER TABLE private_channel_users_database
  ADD COLUMN IF NOT EXISTS nowpayments_price_currency VARCHAR(10);

  ALTER TABLE private_channel_users_database
  ADD COLUMN IF NOT EXISTS nowpayments_outcome_currency VARCHAR(10);

  -- Add comment for documentation
  COMMENT ON COLUMN private_channel_users_database.nowpayments_price_amount IS
    'Original invoice amount in USD from NowPayments (for validation)';

  COMMENT ON COLUMN private_channel_users_database.nowpayments_price_currency IS
    'Original invoice currency (typically USD)';

  COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_currency IS
    'Currency of outcome_amount (e.g., eth, usdt, btc)';
  """
  ```

- [ ] **1.2** Test migration locally
  ```bash
  python3 tools/execute_price_amount_migration.py
  ```

- [ ] **1.3** Verify columns created
  ```sql
  SELECT column_name, data_type, is_nullable
  FROM information_schema.columns
  WHERE table_name = 'private_channel_users_database'
  AND column_name LIKE '%price%' OR column_name LIKE '%outcome_currency%';
  ```

- [ ] **1.4** Run migration in production
  ```bash
  python3 /mnt/c/Users/YossTech/Desktop/2025/.venv/bin/python \
    tools/execute_price_amount_migration.py
  ```

### Phase 2: Update IPN Webhook Handler

**File:** `OCTOBER/10-26/np-webhook-10-26/app.py`

- [ ] **2.1** Update payment data capture (line 407-416)
  ```python
  # OLD:
  payment_data = {
      'payment_id': ipn_data.get('payment_id'),
      'invoice_id': ipn_data.get('invoice_id'),
      'order_id': ipn_data.get('order_id'),
      'pay_address': ipn_data.get('pay_address'),
      'payment_status': ipn_data.get('payment_status'),
      'pay_amount': ipn_data.get('pay_amount'),
      'pay_currency': ipn_data.get('pay_currency'),
      'outcome_amount': ipn_data.get('outcome_amount')
  }

  # NEW:
  payment_data = {
      'payment_id': ipn_data.get('payment_id'),
      'invoice_id': ipn_data.get('invoice_id'),
      'order_id': ipn_data.get('order_id'),
      'pay_address': ipn_data.get('pay_address'),
      'payment_status': ipn_data.get('payment_status'),
      'pay_amount': ipn_data.get('pay_amount'),
      'pay_currency': ipn_data.get('pay_currency'),
      'outcome_amount': ipn_data.get('outcome_amount'),
      'price_amount': ipn_data.get('price_amount'),           # NEW: Original USD amount
      'price_currency': ipn_data.get('price_currency'),       # NEW: Original currency
      'outcome_currency': ipn_data.get('outcome_currency')    # NEW: Outcome currency
  }
  ```

- [ ] **2.2** Update IPN logging (line 383-389)
  ```python
  print(f"📋 [IPN] Payment Data Received:")
  print(f"   Payment ID: {ipn_data.get('payment_id', 'N/A')}")
  print(f"   Order ID: {ipn_data.get('order_id', 'N/A')}")
  print(f"   Payment Status: {ipn_data.get('payment_status', 'N/A')}")
  print(f"   Pay Amount: {ipn_data.get('pay_amount', 'N/A')} {ipn_data.get('pay_currency', 'N/A')}")
  print(f"   Outcome Amount: {ipn_data.get('outcome_amount', 'N/A')} {ipn_data.get('outcome_currency', ipn_data.get('pay_currency', 'N/A'))}")
  print(f"   Price Amount: {ipn_data.get('price_amount', 'N/A')} {ipn_data.get('price_currency', 'N/A')}")  # NEW
  print(f"   Pay Address: {ipn_data.get('pay_address', 'N/A')}")
  ```

- [ ] **2.3** Update database UPDATE query (line 140-175)
  ```python
  # Update the most recent subscription record with NowPayments data
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
          nowpayments_price_amount = %s,          -- NEW
          nowpayments_price_currency = %s,        -- NEW
          nowpayments_outcome_currency = %s,      -- NEW
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
      payment_data.get('price_amount'),         # NEW
      payment_data.get('price_currency'),       # NEW
      payment_data.get('outcome_currency'),     # NEW
      user_id,
      closed_channel_id,
      user_id,
      closed_channel_id
  ))
  ```

- [ ] **2.4** Add fallback for outcome_currency
  ```python
  # If outcome_currency not provided, infer from pay_currency
  # (NowPayments might not always include outcome_currency)
  if not payment_data.get('outcome_currency'):
      # Assume outcome is in same currency as payment
      payment_data['outcome_currency'] = payment_data.get('pay_currency')
      print(f"💡 [IPN] outcome_currency not provided, inferring from pay_currency: {payment_data['outcome_currency']}")
  ```

### Phase 3: Update GCWebhook2 Database Manager

**File:** `OCTOBER/10-26/GCWebhook2-10-26/database_manager.py`

- [ ] **3.1** Update `get_nowpayments_data()` to fetch new fields (line 91-101)
  ```python
  # OLD QUERY:
  query = """
      SELECT
          nowpayments_payment_id,
          nowpayments_payment_status,
          nowpayments_pay_address,
          nowpayments_outcome_amount
      FROM private_channel_users_database
      WHERE user_id = %s AND private_channel_id = %s
      ORDER BY id DESC
      LIMIT 1
  """

  # NEW QUERY:
  query = """
      SELECT
          nowpayments_payment_id,
          nowpayments_payment_status,
          nowpayments_pay_address,
          nowpayments_outcome_amount,
          nowpayments_price_amount,
          nowpayments_price_currency,
          nowpayments_outcome_currency,
          nowpayments_pay_currency
      FROM private_channel_users_database
      WHERE user_id = %s AND private_channel_id = %s
      ORDER BY id DESC
      LIMIT 1
  """
  ```

- [ ] **3.2** Update result parsing (line 106-119)
  ```python
  if result:
      # OLD:
      # payment_id, payment_status, pay_address, outcome_amount = result

      # NEW:
      (payment_id, payment_status, pay_address, outcome_amount,
       price_amount, price_currency, outcome_currency, pay_currency) = result

      if payment_id:
          print(f"✅ [VALIDATION] Found NowPayments payment_id: {payment_id}")
          print(f"📊 [VALIDATION] Payment status: {payment_status}")
          print(f"💰 [VALIDATION] Price amount: {price_amount} {price_currency}")  # NEW
          print(f"💰 [VALIDATION] Outcome amount: {outcome_amount} {outcome_currency}")  # NEW
          print(f"📬 [VALIDATION] Pay address: {pay_address}")

          return {
              'nowpayments_payment_id': payment_id,
              'nowpayments_payment_status': payment_status,
              'nowpayments_pay_address': pay_address,
              'nowpayments_outcome_amount': str(outcome_amount) if outcome_amount else None,
              'nowpayments_price_amount': str(price_amount) if price_amount else None,  # NEW
              'nowpayments_price_currency': price_currency,  # NEW
              'nowpayments_outcome_currency': outcome_currency,  # NEW
              'nowpayments_pay_currency': pay_currency  # NEW
          }
  ```

- [ ] **3.3** Update `validate_payment_complete()` logic (line 178-197)
  ```python
  def validate_payment_complete(self, user_id: int, closed_channel_id: int, expected_price: str) -> tuple[bool, str]:
      """
      Validate that payment has been completed and confirmed via IPN callback.
      Uses price_amount (USD) for validation when available.
      Falls back to crypto conversion if needed.
      """
      print(f"🔐 [VALIDATION] Starting payment validation for user {user_id}, channel {closed_channel_id}")

      # Get payment data
      payment_data = self.get_nowpayments_data(user_id, closed_channel_id)

      if not payment_data:
          error_msg = "Payment not confirmed - IPN callback not yet processed. Please wait."
          print(f"❌ [VALIDATION] {error_msg}")
          return False, error_msg

      payment_id = payment_data.get('nowpayments_payment_id')
      payment_status = payment_data.get('nowpayments_payment_status')
      price_amount = payment_data.get('nowpayments_price_amount')
      price_currency = payment_data.get('nowpayments_price_currency')
      outcome_amount = payment_data.get('nowpayments_outcome_amount')
      outcome_currency = payment_data.get('nowpayments_outcome_currency')

      # Validate payment_id exists
      if not payment_id:
          error_msg = "Payment ID not available - IPN callback pending"
          print(f"❌ [VALIDATION] {error_msg}")
          return False, error_msg

      # Validate payment status is 'finished'
      if payment_status != 'finished':
          error_msg = f"Payment not completed - status: {payment_status}"
          print(f"❌ [VALIDATION] {error_msg}")
          return False, error_msg

      # Validate payment amount
      try:
          expected_amount = float(expected_price)

          # Strategy 1: Use price_amount if available (preferred - USD to USD comparison)
          if price_amount and price_currency:
              actual_usd = float(price_amount)
              print(f"💰 [VALIDATION] Using price_amount for validation: ${actual_usd:.2f} {price_currency}")

              # Allow 5% tolerance for rounding/fees
              minimum_amount = expected_amount * 0.95

              if actual_usd < minimum_amount:
                  error_msg = f"Insufficient payment: received ${actual_usd:.2f} {price_currency}, expected at least ${minimum_amount:.2f}"
                  print(f"❌ [VALIDATION] {error_msg}")
                  return False, error_msg

              print(f"✅ [VALIDATION] Payment amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
              return True, ""

          # Strategy 2: Fallback - Convert crypto to USD (for old records or missing price_amount)
          else:
              print(f"⚠️ [VALIDATION] price_amount not available, falling back to crypto conversion")

              # Check if outcome is already in USD-based stablecoin
              if outcome_currency and outcome_currency.lower() in ['usd', 'usdt', 'usdc', 'busd']:
                  actual_usd = float(outcome_amount) if outcome_amount else 0.0
                  print(f"💰 [VALIDATION] Outcome is in stablecoin: ${actual_usd:.2f} {outcome_currency}")

                  # NowPayments takes ~15% fee, so outcome should be ~85% of price
                  # Allow 20% tolerance (80% minimum)
                  minimum_amount = expected_amount * 0.80

                  if actual_usd < minimum_amount:
                      error_msg = f"Insufficient payment: received ${actual_usd:.2f} {outcome_currency}, expected at least ${minimum_amount:.2f}"
                      print(f"❌ [VALIDATION] {error_msg}")
                      return False, error_msg

                  print(f"✅ [VALIDATION] Payment amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
                  return True, ""

              # Strategy 3: Crypto amount - needs conversion (NOT RECOMMENDED - requires price feed)
              else:
                  error_msg = f"Cannot validate crypto payment: outcome_amount is in {outcome_currency}, price_amount not available"
                  print(f"❌ [VALIDATION] {error_msg}")
                  print(f"💡 [VALIDATION] This payment requires manual verification or NowPayments API call")
                  print(f"💡 [VALIDATION] Payment ID: {payment_id}")
                  print(f"💡 [VALIDATION] Outcome: {outcome_amount} {outcome_currency}")

                  # For now, fail validation and require manual intervention
                  # TODO: Implement crypto-to-USD conversion using price feed or NowPayments API
                  return False, error_msg

      except (ValueError, TypeError) as e:
          error_msg = f"Invalid payment amount data: {e}"
          print(f"❌ [VALIDATION] {error_msg}")
          return False, error_msg
  ```

### Phase 4: Add Crypto-to-USD Conversion (Optional/Future)

**File:** Create `OCTOBER/10-26/GCWebhook2-10-26/crypto_price_feed.py`

- [ ] **4.1** Create price feed module (OPTIONAL - for future enhancement)
  ```python
  """
  Crypto Price Feed - Converts crypto amounts to USD for payment validation.
  Uses CoinGecko or similar API to get real-time prices.
  """
  import httpx
  from typing import Optional

  class CryptoPriceFeed:
      """Get cryptocurrency prices in USD."""

      def __init__(self):
          self.base_url = "https://api.coingecko.com/api/v3"

      async def get_usd_value(self, amount: float, currency: str) -> Optional[float]:
          """
          Convert crypto amount to USD.

          Args:
              amount: Amount in crypto
              currency: Crypto currency (e.g., "eth", "btc")

          Returns:
              USD value or None if conversion fails
          """
          try:
              # Map currency codes to CoinGecko IDs
              currency_map = {
                  'eth': 'ethereum',
                  'btc': 'bitcoin',
                  'usdt': 'tether',
                  'usdc': 'usd-coin',
                  # Add more as needed
              }

              coin_id = currency_map.get(currency.lower())
              if not coin_id:
                  print(f"❌ [PRICE] Unknown currency: {currency}")
                  return None

              # Stablecoins are always ~$1
              if currency.lower() in ['usdt', 'usdc', 'busd', 'dai']:
                  return amount * 1.0

              # Fetch price from CoinGecko
              url = f"{self.base_url}/simple/price?ids={coin_id}&vs_currencies=usd"

              async with httpx.AsyncClient(timeout=10) as client:
                  response = await client.get(url)
                  if response.status_code == 200:
                      data = response.json()
                      price_usd = data[coin_id]['usd']
                      usd_value = amount * price_usd

                      print(f"💹 [PRICE] {amount} {currency.upper()} = ${usd_value:.2f} (${price_usd:.2f}/unit)")
                      return usd_value
                  else:
                      print(f"❌ [PRICE] API error: {response.status_code}")
                      return None

          except Exception as e:
              print(f"❌ [PRICE] Conversion failed: {e}")
              return None
  ```

- [ ] **4.2** Update validation to use price feed (OPTIONAL)
  ```python
  # In validate_payment_complete, Strategy 3:
  from crypto_price_feed import CryptoPriceFeed

  # Convert crypto to USD
  price_feed = CryptoPriceFeed()
  actual_usd = await price_feed.get_usd_value(
      float(outcome_amount),
      outcome_currency
  )

  if actual_usd:
      minimum_amount = expected_amount * 0.80
      if actual_usd >= minimum_amount:
          print(f"✅ [VALIDATION] Crypto payment OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
          return True, ""
  ```

### Phase 5: Update Migration Tracker

**File:** `OCTOBER/10-26/tools/execute_price_amount_migration.py`

- [ ] **5.1** Create complete migration script
  ```python
  #!/usr/bin/env python
  """
  Add price_amount and currency tracking to private_channel_users_database.

  This migration adds:
  - nowpayments_price_amount: Original USD invoice amount
  - nowpayments_price_currency: Original currency (typically USD)
  - nowpayments_outcome_currency: Currency of outcome_amount

  These fields enable proper USD-to-USD validation instead of comparing
  crypto amounts to USD.
  """
  import subprocess
  from google.cloud.sql.connector import Connector

  def get_secret(secret_name):
      """Fetch secret from Google Cloud Secret Manager."""
      result = subprocess.run(
          ['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret', secret_name],
          capture_output=True, text=True
      )
      return result.stdout.strip()

  def main():
      print("=" * 80)
      print("PRICE AMOUNT MIGRATION - Add USD tracking fields")
      print("=" * 80)
      print()

      # Get database credentials
      print("📋 [SETUP] Fetching database credentials...")
      instance_connection_name = get_secret('CLOUD_SQL_CONNECTION_NAME')
      db_name = get_secret('DATABASE_NAME_SECRET')
      db_user = get_secret('DATABASE_USER_SECRET')
      db_password = get_secret('DATABASE_PASSWORD_SECRET')
      print(f"✅ [SETUP] Connected to: {instance_connection_name}")
      print()

      # Connect to database
      connector = Connector()
      conn = connector.connect(
          instance_connection_name,
          "pg8000",
          user=db_user,
          password=db_password,
          db=db_name
      )
      cursor = conn.cursor()

      # Migration SQL
      migration_sql = """
      -- Add price amount and currency fields to private_channel_users_database
      ALTER TABLE private_channel_users_database
      ADD COLUMN IF NOT EXISTS nowpayments_price_amount DECIMAL(20, 8);

      ALTER TABLE private_channel_users_database
      ADD COLUMN IF NOT EXISTS nowpayments_price_currency VARCHAR(10);

      ALTER TABLE private_channel_users_database
      ADD COLUMN IF NOT EXISTS nowpayments_outcome_currency VARCHAR(10);

      -- Add helpful comments
      COMMENT ON COLUMN private_channel_users_database.nowpayments_price_amount IS
        'Original invoice amount from NowPayments (typically in USD) - used for payment validation';

      COMMENT ON COLUMN private_channel_users_database.nowpayments_price_currency IS
        'Original invoice currency (typically USD)';

      COMMENT ON COLUMN private_channel_users_database.nowpayments_outcome_currency IS
        'Currency of outcome_amount field (e.g., eth, usdt, btc)';
      """

      try:
          print("🔄 [MIGRATION] Executing schema changes...")
          cursor.execute(migration_sql)
          conn.commit()
          print("✅ [MIGRATION] Schema updated successfully")
          print()
      except Exception as e:
          print(f"❌ [MIGRATION] Failed: {e}")
          conn.rollback()
          return

      # Verify columns
      print("🔍 [VERIFY] Checking new columns...")
      cursor.execute("""
          SELECT column_name, data_type, is_nullable
          FROM information_schema.columns
          WHERE table_name = 'private_channel_users_database'
          AND (column_name = 'nowpayments_price_amount'
               OR column_name = 'nowpayments_price_currency'
               OR column_name = 'nowpayments_outcome_currency')
          ORDER BY column_name;
      """)

      columns = cursor.fetchall()
      if columns:
          print("✅ [VERIFY] Found new columns:")
          for col in columns:
              print(f"   - {col[0]}: {col[1]} (nullable: {col[2]})")
      else:
          print("❌ [VERIFY] Columns not found!")

      print()
      print("=" * 80)
      print("✅ MIGRATION COMPLETE")
      print("=" * 80)
      print()
      print("Next steps:")
      print("1. Deploy updated np-webhook-10-26 service")
      print("2. Deploy updated GCWebhook2-10-26 service")
      print("3. Test with new payment")
      print("4. Verify price_amount is captured and validated correctly")

      cursor.close()
      conn.close()

  if __name__ == "__main__":
      main()
  ```

### Phase 6: Error Handling & Edge Cases

- [ ] **6.1** Handle missing price_amount gracefully
  ```python
  # In validation logic
  if not price_amount:
      print(f"⚠️ [VALIDATION] price_amount not available (old IPN format or missing)")
      print(f"💡 [VALIDATION] Attempting alternative validation methods...")
  ```

- [ ] **6.2** Handle currency mismatches
  ```python
  # Check if price_currency matches expected
  if price_currency and price_currency.upper() != 'USD':
      print(f"⚠️ [VALIDATION] Unexpected price currency: {price_currency} (expected USD)")
      # Decide whether to fail or convert
  ```

- [ ] **6.3** Add manual verification override (future)
  ```python
  # For edge cases where automatic validation fails
  # Add admin endpoint to manually approve payments
  # Store manual_approval flag in database
  ```

---

## Testing Strategy

### Test Case 1: New Payment with price_amount
**Setup:**
- Create new payment through TelePay bot
- Pay via NowPayments (any crypto)
- Wait for IPN callback

**Expected:**
```
IPN Webhook:
✅ Received price_amount: 1.35
✅ Received price_currency: usd
✅ Stored in database

GCWebhook2 Validation:
✅ Retrieved price_amount: 1.35 USD
✅ Compared $1.35 >= $1.28 (95% of $1.35)
✅ Validation passed
✅ Invitation sent
```

### Test Case 2: Old Payment without price_amount
**Setup:**
- Query existing payment record (before migration)
- Trigger validation

**Expected:**
```
GCWebhook2 Validation:
⚠️ price_amount not available
⚠️ outcome_currency: eth
❌ Cannot validate crypto payment
❌ Requires manual verification
```

### Test Case 3: Stablecoin Payment
**Setup:**
- User pays in USDT
- outcome_amount = 1.15 USDT (after fees)
- outcome_currency = "usdt"

**Expected:**
```
GCWebhook2 Validation:
✅ Outcome is stablecoin: 1.15 USDT
✅ Compared $1.15 >= $1.08 (80% of $1.35)
✅ Validation passed
```

### Test Case 4: Insufficient Payment
**Setup:**
- User pays but amount too low
- price_amount = 0.50 USD (should be 1.35)

**Expected:**
```
GCWebhook2 Validation:
❌ Insufficient payment: $0.50, expected at least $1.28
❌ Validation failed
❌ Invitation NOT sent
```

---

## Verification Steps

### Pre-Deployment

- [ ] **V1:** Test migration script locally
  ```bash
  python3 tools/execute_price_amount_migration.py
  ```

- [ ] **V2:** Verify database schema
  ```sql
  \d private_channel_users_database
  -- Check for price_amount, price_currency, outcome_currency columns
  ```

- [ ] **V3:** Code review all three services
  - np-webhook-10-26: IPN capture
  - GCWebhook2-10-26: Validation logic
  - Migration script: Schema changes

### Post-Deployment

- [ ] **V4:** Monitor IPN webhook logs
  ```bash
  gcloud run services logs read np-webhook-10-26 \
    --region=us-east1 \
    --limit=50 \
    | grep "price_amount"
  ```

- [ ] **V5:** Test complete payment flow
  1. Create payment in bot
  2. Complete payment
  3. Check IPN logs for price_amount
  4. Verify database updated
  5. Check GCWebhook2 validation
  6. Confirm invitation sent

- [ ] **V6:** Query database for verification
  ```sql
  SELECT
      user_id,
      private_channel_id,
      nowpayments_payment_id,
      nowpayments_payment_status,
      nowpayments_price_amount,
      nowpayments_price_currency,
      nowpayments_outcome_amount,
      nowpayments_outcome_currency,
      sub_price
  FROM private_channel_users_database
  WHERE nowpayments_payment_id IS NOT NULL
  ORDER BY id DESC
  LIMIT 5;
  ```

- [ ] **V7:** Verify validation logic
  ```bash
  # Check GCWebhook2 logs for successful validation
  gcloud run services logs read gcwebhook2-10-26 \
    --region=us-central1 \
    --limit=50 \
    | grep "VALIDATION"
  ```

---

## Deployment Plan

### Step 1: Run Database Migration
```bash
cd OCTOBER/10-26/tools
python3 execute_price_amount_migration.py
# Verify columns created
```

### Step 2: Deploy np-webhook Update
```bash
cd OCTOBER/10-26/np-webhook-10-26

# Build and deploy
gcloud builds submit --tag gcr.io/telepay-459221/np-webhook-10-26
gcloud run deploy np-webhook-10-26 \
  --image gcr.io/telepay-459221/np-webhook-10-26 \
  --region=us-east1 \
  --platform=managed
```

### Step 3: Deploy GCWebhook2 Update
```bash
cd OCTOBER/10-26/GCWebhook2-10-26

# Build and deploy
gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook2-10-26
gcloud run deploy gcwebhook2-10-26 \
  --image gcr.io/telepay-459221/gcwebhook2-10-26 \
  --region=us-central1 \
  --platform=managed
```

### Step 4: Test End-to-End
```bash
# Create test payment
# Monitor logs in real-time
gcloud run services logs tail np-webhook-10-26 --region=us-east1 &
gcloud run services logs tail gcwebhook2-10-26 --region=us-central1 &
```

### Step 5: Verify Success
```bash
# Check database for new fields populated
# Verify invitation sent successfully
```

---

## Rollback Plan

### If Validation Fails

**Option 1: Temporary fix - Disable validation**
```python
# In GCWebhook2-10-26/database_manager.py
def validate_payment_complete(...):
    # TEMPORARY: Skip validation, always return True
    print("⚠️ [VALIDATION] TEMPORARY: Validation disabled for debugging")
    return True, ""
```

**Option 2: Revert to previous version**
```bash
# List recent revisions
gcloud run revisions list --service=gcwebhook2-10-26 --region=us-central1

# Route traffic back to previous revision
gcloud run services update-traffic gcwebhook2-10-26 \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1
```

**Option 3: Use old validation logic**
```python
# Fallback to outcome_amount validation with higher tolerance
if not price_amount:
    # Use old logic but with 50% tolerance instead of 80%
    minimum_amount = expected_amount * 0.50
```

---

## Additional Safeguards

### Monitoring & Alerts

- [ ] **Alert 1:** IPN webhook not capturing price_amount
  ```
  Trigger: price_amount is NULL after IPN callback
  Action: Send alert to admin
  ```

- [ ] **Alert 2:** Validation failure rate > 10%
  ```
  Trigger: More than 10% of validations fail
  Action: Investigate logs, check for API changes
  ```

- [ ] **Alert 3:** Payment without invitation
  ```
  Trigger: Payment marked "finished" but no invitation sent
  Action: Manual verification needed
  ```

### Documentation Updates

- [ ] Update `NOWPAYMENTS_IMPLEMENTATION_SUMMARY.md`
- [ ] Document new database fields
- [ ] Add troubleshooting guide for validation failures
- [ ] Create manual approval procedure

---

## Success Criteria

- ✅ Database migration successful (3 new columns added)
- ✅ IPN webhook captures price_amount, price_currency, outcome_currency
- ✅ GCWebhook2 validates using USD amounts (not crypto)
- ✅ Payment validation success rate > 95%
- ✅ Users receive invitations after payment
- ✅ Zero false negatives (valid payments not rejected)

---

## Alternative Solutions Considered

### Alternative 1: Query NowPayments API
**Pros:**
- Get real-time, accurate data
- Can get additional fields not in IPN

**Cons:**
- Requires additional API call (latency)
- API rate limits
- Extra complexity
- IPN already has the data we need

**Decision:** ❌ Not chosen - IPN has all required data

### Alternative 2: Use Real-time Crypto Price Feed
**Pros:**
- Can validate crypto amounts directly
- Flexible for any cryptocurrency

**Cons:**
- Requires external API (CoinGecko, etc.)
- Price volatility issues
- API failures affect validation
- More complex than USD comparison

**Decision:** ❌ Not chosen as primary, but added as fallback option

### Alternative 3: Store Everything, Validate Later
**Pros:**
- Never block users
- Can fix validation logic later

**Cons:**
- Risk of fraud/abuse
- Harder to reconcile payments
- Users get access before validation

**Decision:** ❌ Not chosen - validation must happen before invitation

---

## Related Issues

This fix enables:
- ✅ Proper payment validation (immediate benefit)
- ✅ User access to paid channels (immediate benefit)
- ✅ Fee reconciliation using price_amount (future)
- ✅ Crypto-to-USD tracking (future)

---

## Notes

### Why price_amount vs outcome_amount?

**price_amount:**
- Original invoice amount in USD
- What the user was supposed to pay
- Always in USD (our invoice currency)
- ✅ Perfect for validation

**outcome_amount:**
- What merchant receives after fees
- Can be in any currency (crypto or fiat)
- Requires conversion to compare to USD
- ❌ Not ideal for validation

### NowPayments Fee Structure

- User pays: 100% (e.g., $1.35)
- NowPayments fee: ~15%
- Merchant receives: ~85% (e.g., $1.15)

For validation:
- Use `price_amount` (100%) with 5% tolerance = 95% minimum
- Using `outcome_amount` would need 80% tolerance (to account for fees)

### Backward Compatibility

Old records (before this fix):
- `price_amount` = NULL
- Validation falls back to stablecoin check or manual approval
- No disruption to existing data

---

**END OF CHECKLIST**
