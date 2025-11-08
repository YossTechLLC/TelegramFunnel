# NowPayments Payment Validation Fix - Outcome Amount USD Conversion

**Date:** 2025-11-02
**Service:** GCWebhook2-10-26 (Payment Validation)
**Priority:** CRITICAL
**Status:** In Progress

---

## Executive Summary

### The Problem

GCWebhook2 currently validates payments using `price_amount` (subscription price: $1.35 USD) instead of the actual amount received in the host wallet (`outcome_amount`: 0.00026959 ETH).

**Current Behavior (INCORRECT):**
```
User pays $1.35 → NowPayments takes fees → Host receives 0.00026959 ETH
Validation: price_amount ($1.35) >= $1.28 ✅ PASSES
Invitation: SENT ✅
```

**The Issue:**
- `price_amount` = Original subscription price ($1.35 USD)
- `outcome_amount` = Actual crypto received (0.00026959 ETH)
- **We're validating the invoice, not what was actually received**
- Host wallet could receive significantly less value than expected
- NowPayments fees could be higher than anticipated

**What Should Happen (CORRECT):**
```
User pays $1.35 → NowPayments takes fees → Host receives 0.00026959 ETH
Convert: 0.00026959 ETH → $1.08 USD (at current market rate)
Validation: $1.08 >= minimum expected
If valid: SEND invitation
If invalid: DO NOT send invitation
```

---

## Root Cause Analysis

### Current Validation Logic

File: `GCWebhook2-10-26/database_manager.py:196-212`

```python
# Strategy 1 (PRIMARY): USD-to-USD validation using price_amount
if price_amount and price_currency:
    actual_usd = float(price_amount)  # 1.35 USD ❌ INVOICE PRICE
    print(f"💰 [VALIDATION] Using price_amount for validation: ${actual_usd:.2f} {price_currency}")

    # Allow 5% tolerance for rounding/fees
    minimum_amount = expected_amount * 0.95  # $1.35 * 0.95 = $1.28

    if actual_usd < minimum_amount:
        error_msg = f"Insufficient payment: received ${actual_usd:.2f} {price_currency}, expected at least ${minimum_amount:.2f}"
        print(f"❌ [VALIDATION] {error_msg}")
        return False, error_msg

    print(f"✅ [VALIDATION] Payment amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
    print(f"✅ [VALIDATION] Payment validation successful - payment_id: {payment_id}")
    return True, ""
```

### The Issue

1. **Validation Target Mismatch:**
   - Validating `price_amount` (what user was invoiced)
   - Should validate `outcome_amount` (what merchant received)
   - These can differ significantly due to:
     - NowPayments fees (~15%)
     - Network fees (gas fees for ETH)
     - Exchange rate fluctuations

2. **Missing USD Conversion:**
   - `outcome_amount` is in crypto (ETH, BTC, etc.)
   - Need to convert to USD for meaningful validation
   - Current code doesn't perform this conversion

3. **Example Scenario:**
   ```
   Subscription Price: $1.35 USD (price_amount)
   Customer Pays: 0.000412 ETH (pay_amount at time of invoice)
   NowPayments Fees: ~15%
   Host Receives: 0.00026959 ETH (outcome_amount)
   ETH Market Price: $4,000/ETH
   USD Value Received: 0.00026959 × $4,000 = $1.08 USD

   Current Validation: $1.35 >= $1.28 ✅ PASS (WRONG!)
   Correct Validation: $1.08 >= minimum ??? (SHOULD CHECK THIS)
   ```

---

## Solution Architecture

### Overview

Implement **3-tier validation strategy** with outcome_amount conversion:

1. **Tier 1 (PRIMARY)**: Convert `outcome_amount` to USD and validate
   - Use real-time crypto price feed (CoinGecko API)
   - Convert crypto to USD at current market rate
   - Validate USD value against expected amount

2. **Tier 2 (FALLBACK)**: Stablecoin direct validation
   - For USDT, USDC, BUSD: treat as 1:1 with USD
   - No conversion needed (already USD-equivalent)

3. **Tier 3 (LEGACY)**: `price_amount` validation (current behavior)
   - Only used if outcome_amount conversion fails
   - Logs warning about using invoice price instead of actual received

### Detailed Implementation Plan

#### Phase 1: Add Crypto Price Feed Integration

**Files to Modify:**
- `GCWebhook2-10-26/database_manager.py`
- `GCWebhook2-10-26/requirements.txt`

**New Dependencies:**
```txt
requests==2.31.0  # For API calls to CoinGecko
```

**New Method:**
```python
def get_crypto_usd_price(self, crypto_symbol: str) -> Optional[float]:
    """
    Get current USD price for a cryptocurrency using CoinGecko API.

    Args:
        crypto_symbol: Crypto currency symbol (eth, btc, ltc, etc.)

    Returns:
        Current USD price or None if API fails
    """
    try:
        # CoinGecko Free API (no auth required)
        # Map common symbols to CoinGecko IDs
        symbol_map = {
            'eth': 'ethereum',
            'btc': 'bitcoin',
            'ltc': 'litecoin',
            'bch': 'bitcoin-cash',
            'xrp': 'ripple',
            'bnb': 'binancecoin',
            'ada': 'cardano',
            'doge': 'dogecoin',
            'trx': 'tron',
            'usdt': 'tether',
            'usdc': 'usd-coin',
            'busd': 'binance-usd'
        }

        crypto_id = symbol_map.get(crypto_symbol.lower())
        if not crypto_id:
            print(f"❌ [PRICE] Unknown crypto symbol: {crypto_symbol}")
            return None

        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=usd"

        print(f"🔍 [PRICE] Fetching {crypto_symbol.upper()} price from CoinGecko...")

        import requests
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            usd_price = data.get(crypto_id, {}).get('usd')

            if usd_price:
                print(f"💰 [PRICE] {crypto_symbol.upper()}/USD = ${usd_price:,.2f}")
                return float(usd_price)
            else:
                print(f"❌ [PRICE] USD price not found in response")
                return None
        else:
            print(f"❌ [PRICE] CoinGecko API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ [PRICE] Error fetching crypto price: {e}")
        return None


def convert_crypto_to_usd(self, amount: float, crypto_symbol: str) -> Optional[float]:
    """
    Convert cryptocurrency amount to USD using current market rate.

    Args:
        amount: Amount of cryptocurrency
        crypto_symbol: Crypto currency symbol (eth, btc, etc.)

    Returns:
        USD equivalent or None if conversion fails
    """
    try:
        # Check if stablecoin (1:1 with USD)
        if crypto_symbol.lower() in ['usd', 'usdt', 'usdc', 'busd']:
            print(f"💰 [CONVERT] {crypto_symbol.upper()} is stablecoin, treating as 1:1 USD")
            return float(amount)

        # Get current market price
        usd_price = self.get_crypto_usd_price(crypto_symbol)
        if not usd_price:
            print(f"❌ [CONVERT] Could not fetch price for {crypto_symbol}")
            return None

        # Convert to USD
        usd_value = float(amount) * usd_price
        print(f"💰 [CONVERT] {amount} {crypto_symbol.upper()} = ${usd_value:.2f} USD")

        return usd_value

    except Exception as e:
        print(f"❌ [CONVERT] Conversion error: {e}")
        return None
```

#### Phase 2: Update Validation Logic

**File:** `GCWebhook2-10-26/database_manager.py`

**Current Code (Lines 193-246):**
```python
# Validate payment amount
try:
    expected_amount = float(expected_price)

    # Strategy 1: Use price_amount if available (preferred - USD to USD comparison)
    if price_amount and price_currency:
        actual_usd = float(price_amount)
        # ... validation ...
        return True, ""

    # Strategy 2: Fallback - Convert crypto to USD (for old records or missing price_amount)
    else:
        # ... crypto conversion (incomplete) ...
```

**New Code (Replacement):**
```python
# Validate payment amount
try:
    expected_amount = float(expected_price)

    # ============================================================================
    # STRATEGY 1 (PRIMARY): Validate outcome_amount converted to USD
    # ============================================================================
    if outcome_amount and outcome_currency:
        print(f"💰 [VALIDATION] Outcome: {outcome_amount} {outcome_currency}")

        # Convert outcome_amount to USD
        outcome_usd = self.convert_crypto_to_usd(
            amount=float(outcome_amount),
            crypto_symbol=outcome_currency
        )

        if outcome_usd is not None:
            print(f"💰 [VALIDATION] Outcome in USD: ${outcome_usd:.2f}")

            # Calculate minimum acceptable amount
            # Account for NowPayments fees (~15%) + tolerance (5%)
            # Merchant should receive at least 75% of subscription price
            minimum_amount = expected_amount * 0.75

            if outcome_usd < minimum_amount:
                error_msg = (
                    f"Insufficient payment received: ${outcome_usd:.2f} USD "
                    f"(from {outcome_amount} {outcome_currency}), "
                    f"expected at least ${minimum_amount:.2f} USD"
                )
                print(f"❌ [VALIDATION] {error_msg}")
                return False, error_msg

            print(f"✅ [VALIDATION] Outcome amount OK: ${outcome_usd:.2f} >= ${minimum_amount:.2f}")

            # Log fee information for reconciliation
            if price_amount:
                fee_lost = float(price_amount) - outcome_usd
                fee_percentage = (fee_lost / float(price_amount)) * 100
                print(f"📊 [VALIDATION] Invoice: ${price_amount}, Received: ${outcome_usd:.2f}, Fee: ${fee_lost:.2f} ({fee_percentage:.1f}%)")

            print(f"✅ [VALIDATION] Payment validation successful - payment_id: {payment_id}")
            return True, ""
        else:
            print(f"⚠️ [VALIDATION] Could not convert outcome_amount to USD")
            print(f"⚠️ [VALIDATION] Falling back to price_amount validation...")

    # ============================================================================
    # STRATEGY 2 (FALLBACK): Use price_amount if outcome conversion failed
    # ============================================================================
    if price_amount and price_currency:
        print(f"💰 [VALIDATION] Using price_amount fallback: ${float(price_amount):.2f} {price_currency}")
        print(f"⚠️ [VALIDATION] WARNING: Validating invoice price, not actual received amount")

        actual_usd = float(price_amount)
        minimum_amount = expected_amount * 0.95  # 5% tolerance

        if actual_usd < minimum_amount:
            error_msg = f"Insufficient invoice amount: ${actual_usd:.2f}, expected at least ${minimum_amount:.2f}"
            print(f"❌ [VALIDATION] {error_msg}")
            return False, error_msg

        print(f"✅ [VALIDATION] Invoice amount OK: ${actual_usd:.2f} >= ${minimum_amount:.2f}")
        print(f"⚠️ [VALIDATION] NOTE: Actual received amount not validated (outcome conversion unavailable)")
        return True, ""

    # ============================================================================
    # STRATEGY 3 (ERROR): No validation possible
    # ============================================================================
    error_msg = "Cannot validate payment: both outcome_amount and price_amount unavailable"
    print(f"❌ [VALIDATION] {error_msg}")
    return False, error_msg

except (ValueError, TypeError) as e:
    error_msg = f"Invalid payment amount data: {e}"
    print(f"❌ [VALIDATION] {error_msg}")
    return False, error_msg
```

#### Phase 3: Testing Strategy

**Test Cases:**

1. **Test Case 1: ETH Payment (Normal Scenario)**
   ```
   Subscription: $1.35 USD
   Outcome: 0.00026959 ETH
   ETH Price: ~$4,000/ETH
   Expected USD: $1.08
   Minimum: $1.01 (75% of $1.35)
   Expected Result: PASS ✅
   ```

2. **Test Case 2: Stablecoin Payment (USDT)**
   ```
   Subscription: $1.35 USD
   Outcome: 1.15 USDT
   Expected USD: $1.15
   Minimum: $1.01 (75% of $1.35)
   Expected Result: PASS ✅
   ```

3. **Test Case 3: Insufficient Outcome Amount**
   ```
   Subscription: $1.35 USD
   Outcome: 0.00015 ETH
   ETH Price: ~$4,000/ETH
   Expected USD: $0.60
   Minimum: $1.01 (75% of $1.35)
   Expected Result: FAIL ❌
   ```

4. **Test Case 4: Price Feed Failure (Fallback to price_amount)**
   ```
   Subscription: $1.35 USD
   Outcome: 0.00026959 ETH (but price feed fails)
   Price Amount: $1.35 USD (available)
   Expected Result: PASS (with warning) ⚠️
   ```

---

## Implementation Checklist

### Phase 1: Add Crypto Price Feed

- [ ] Add `requests==2.31.0` to `GCWebhook2-10-26/requirements.txt`
- [ ] Add `get_crypto_usd_price()` method to `database_manager.py`
- [ ] Add `convert_crypto_to_usd()` method to `database_manager.py`
- [ ] Test price feed with manual API call (verify CoinGecko working)

### Phase 2: Update Validation Logic

- [ ] Backup current `database_manager.py`
- [ ] Replace validation logic in `validate_payment_complete()` method
- [ ] Add outcome_amount USD conversion as Strategy 1
- [ ] Move price_amount validation to Strategy 2 (fallback)
- [ ] Add comprehensive logging for debugging
- [ ] Add fee reconciliation logging

### Phase 3: Build and Deploy

- [ ] Build Docker image for GCWebhook2-10-26
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook2-10-26
  docker build -t gcr.io/telepay-459221/gcwebhook2-10-26 .
  docker push gcr.io/telepay-459221/gcwebhook2-10-26
  ```

- [ ] Deploy to Cloud Run
  ```bash
  gcloud run deploy gcwebhook2-10-26 \
    --image gcr.io/telepay-459221/gcwebhook2-10-26 \
    --region us-central1 \
    --platform managed
  ```

- [ ] Verify deployment
  ```bash
  gcloud run services describe gcwebhook2-10-26 --region us-central1
  curl https://gcwebhook2-10-26-291176869049.us-central1.run.app/health
  ```

### Phase 4: Testing & Validation

- [ ] Create test payment ($1.35 subscription)
- [ ] Monitor GCWebhook2 logs for outcome_amount conversion
- [ ] Verify invitation sent successfully
- [ ] Check logs show correct USD conversion
- [ ] Verify fee reconciliation data logged correctly

### Phase 5: Monitoring & Rollback Plan

- [ ] Monitor validation success rate for 24 hours
- [ ] Check for any price feed API failures
- [ ] Verify CoinGecko rate limits not exceeded
- [ ] Document rollback procedure if issues arise

---

## Configuration Changes

### Environment Variables

**No new environment variables required** - CoinGecko Free API doesn't need authentication.

### Dependencies

**Add to `GCWebhook2-10-26/requirements.txt`:**
```
requests==2.31.0
```

---

## Deployment Steps

### Step 1: Update Code

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCWebhook2-10-26
```

1. Edit `requirements.txt` - add `requests==2.31.0`
2. Edit `database_manager.py` - add price feed methods
3. Edit `database_manager.py` - update validation logic

### Step 2: Build Docker Image

```bash
docker build -t gcr.io/telepay-459221/gcwebhook2-10-26 .
```

### Step 3: Push to Container Registry

```bash
docker push gcr.io/telepay-459221/gcwebhook2-10-26
```

### Step 4: Deploy to Cloud Run

```bash
gcloud run deploy gcwebhook2-10-26 \
  --image gcr.io/telepay-459221/gcwebhook2-10-26 \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated
```

### Step 5: Verify Deployment

```bash
# Check service status
gcloud run services describe gcwebhook2-10-26 --region us-central1

# Test health endpoint
curl https://gcwebhook2-10-26-291176869049.us-central1.run.app/health
```

---

## Expected Behavior After Fix

### Before Fix

```
[LOG] 💰 [VALIDATION] Using price_amount for validation: $1.35 usd
[LOG] ✅ [VALIDATION] Payment amount OK: $1.35 >= $1.28
[LOG] ✅ [VALIDATION] Payment validation successful
```

**Problem:** Validating invoice price, not actual received amount

### After Fix

```
[LOG] 💰 [VALIDATION] Outcome: 0.000269520000000000 eth
[LOG] 🔍 [PRICE] Fetching ETH price from CoinGecko...
[LOG] 💰 [PRICE] ETH/USD = $4,000.00
[LOG] 💰 [CONVERT] 0.00026952 ETH = $1.08 USD
[LOG] 💰 [VALIDATION] Outcome in USD: $1.08
[LOG] ✅ [VALIDATION] Outcome amount OK: $1.08 >= $1.01
[LOG] 📊 [VALIDATION] Invoice: $1.35, Received: $1.08, Fee: $0.27 (20.0%)
[LOG] ✅ [VALIDATION] Payment validation successful - payment_id: 5181195855
```

**Result:** Validating actual USD value received in wallet ✅

---

## Rollback Plan

If issues arise after deployment:

### Option 1: Redeploy Previous Revision

```bash
# List revisions
gcloud run revisions list --service gcwebhook2-10-26 --region us-central1

# Route traffic back to previous revision
gcloud run services update-traffic gcwebhook2-10-26 \
  --region us-central1 \
  --to-revisions gcwebhook2-10-26-00012-9m5=100
```

### Option 2: Disable Price Feed (Fallback to price_amount)

Add conditional flag to skip outcome conversion:
```python
if os.getenv('USE_OUTCOME_VALIDATION', 'true').lower() == 'false':
    # Skip outcome conversion, use price_amount only
    pass
```

---

## Success Metrics

- [ ] **Validation Accuracy:** 100% of payments validate actual received amount
- [ ] **Price Feed Uptime:** >99% success rate for CoinGecko API calls
- [ ] **Fee Visibility:** All transactions log fee reconciliation data
- [ ] **User Experience:** No change (invitations still sent immediately after valid payment)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CoinGecko API failure | Medium | High | Fallback to price_amount validation |
| Rate limit exceeded | Low | Medium | Free tier allows 50 calls/min (sufficient) |
| Price volatility | Low | Low | Use current market rate at validation time |
| Stablecoin depeg | Very Low | Medium | Monitor stablecoin prices separately |

---

## Additional Notes

### Why 75% Minimum?

```
Subscription Price: $1.35 (100%)
NowPayments Fee: ~15% = $0.20
Network Fee (ETH): ~5% = $0.07
Expected Received: ~80% = $1.08
Tolerance: 5% = $0.07
Minimum: 75% = $1.01
```

### Price Feed Provider Choice

**CoinGecko Free API:**
- ✅ No authentication required
- ✅ 50 calls/minute (sufficient for our volume)
- ✅ Reliable and well-maintained
- ✅ Supports all major cryptocurrencies
- ❌ Rate limits (but acceptable for our use case)

**Alternatives Considered:**
- CryptoCompare: Requires API key
- Binance API: Requires account setup
- Chainlink: Requires blockchain integration (overkill)

---

## Timeline

- **Phase 1-2 (Code Changes):** 30 minutes
- **Phase 3 (Build & Deploy):** 15 minutes
- **Phase 4 (Testing):** 30 minutes
- **Phase 5 (Monitoring):** Ongoing (24 hours)

**Total Estimated Time:** 1.5 hours + 24h monitoring

---

## Files to Modify

1. `/OCTOBER/10-26/GCWebhook2-10-26/requirements.txt`
   - Add: `requests==2.31.0`

2. `/OCTOBER/10-26/GCWebhook2-10-26/database_manager.py`
   - Add: `get_crypto_usd_price()` method
   - Add: `convert_crypto_to_usd()` method
   - Modify: `validate_payment_complete()` method (lines 193-246)

3. `/OCTOBER/10-26/PROGRESS.md`
   - Add: Session 31 entry

4. `/OCTOBER/10-26/DECISIONS.md`
   - Add: Outcome amount validation decision

5. `/OCTOBER/10-26/BUGS.md`
   - Update: Move current bug to "Recently Fixed"

---

## Conclusion

This fix ensures that payment validation checks the **actual USD value received in the host wallet** rather than the invoice price. This provides:

1. **Accurate Validation:** Prevents invitations being sent for underpaid transactions
2. **Fee Transparency:** Logs actual fees taken by NowPayments
3. **Security:** Prevents exploitation of fee discrepancies
4. **Reliability:** Fallback to invoice validation if price feed fails

**Status:** Ready for implementation ✅
