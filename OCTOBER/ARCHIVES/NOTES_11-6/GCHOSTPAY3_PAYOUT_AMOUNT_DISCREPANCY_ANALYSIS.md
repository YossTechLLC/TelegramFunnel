# GCHostPay3 Payout Amount Discrepancy Analysis

**Date:** 2025-11-02
**Service:** gchostpay3-10-26 (ETH Payment Executor)
**Issue:** Inconsistent payout amounts with 3900% variation
**Severity:** CRITICAL - Financial discrepancy

---

## Executive Summary

GCHostPay3 is attempting to send two wildly different ETH payment amounts for what appear to be similar transactions:

- **Large Amount:** 4.48332809 ETH (~$13,449 USD @ $3,000/ETH)
- **Small Amount:** 0.00115340416715763 ETH (~$3.46 USD @ $3,000/ETH)

**Discrepancy Ratio:** 3,886x (or 388,500% difference)

All payments are failing with "Transaction confirmation timeout after 300s", but this analysis focuses on **why such drastically different amounts are being sent** in the first place.

---

## Observed Behavior from Logs

### Log Evidence (2025-11-02 17:50 - 18:07 UTC)

#### Pattern 1: Large Payment (4.48 ETH)
```
17:50:24 - 💰 [ENDPOINT] Amount: 4.48332809 ETH
17:50:24 - 💸 [ETH_PAYMENT] Amount: 4.48332809 ETH
17:50:24 - 💸 [ETH_PAYMENT] Amount in Wei: 4483328090000000000
```

#### Pattern 2: Small Payment (0.00115 ETH)
```
17:50:24 - 💰 [ENDPOINT] Amount: 0.00115340416715763 ETH
17:50:24 - 💸 [ETH_PAYMENT] Amount: 0.00115340416715763 ETH
17:50:24 - 💸 [ETH_PAYMENT] Amount in Wei: 1153404167157630
```

### Observed Sequence

| Timestamp | Amount (ETH) | Wei | Status |
|-----------|--------------|-----|--------|
| 17:50:24 | 4.48332809 | 4483328090000000000 | Timeout → Failed after 3 attempts |
| 17:50:24 | 0.00115340416715763 | 1153404167157630 | Timeout → Failed after 3 attempts |
| 17:56:24 | 4.48332809 | 4483328090000000000 | Timeout → Failed after 3 attempts |
| 17:56:25 | 0.00115340416715763 | 1153404167157630 | Timeout → Failed after 3 attempts |
| 18:02:25 | 4.48332809 | 4483328090000000000 | Timeout → Failed after 3 attempts |
| 18:02:26 | 0.00115340416715763 | 1153404167157630 | Timeout → Failed after 3 attempts |

**Pattern:** Two distinct payment amounts alternating, both failing consistently.

---

## Root Cause Hypothesis

### Hypothesis 1: Confusing `outcome_amount` (crypto) with `outcome_amount_usd` (fiat)

**Likely:** HIGH

**Evidence:**
- Large amount: 4.48332809 ETH ≈ $13,449 USD
- Small amount: 0.00115340416715763 ETH ≈ $3.46 USD
- The ratio suggests one might be a USD value mistakenly used as ETH amount

**Flow Analysis:**

1. **NowPayments IPN** sends:
   ```json
   {
     "outcome_amount": "0.00448332809",  // Actual crypto received
     "outcome_currency": "ETH",
     "outcome_amount_usd": 13.45,        // USD equivalent
     "price_amount": 5.00,               // Original USD price
     "price_currency": "USD"
   }
   ```

2. **Question:** Is GCHostPay3 receiving:
   - `outcome_amount` (0.00448332809 ETH) ✅ CORRECT
   - `outcome_amount_usd` (13.45 USD) ❌ WRONG - mistaken as crypto amount?

3. **If USD value treated as crypto:**
   - 13.45 USD mistakenly sent as 13.45 ETH = ~$40,350 USD ❌ DISASTER
   - But our log shows 4.48 ETH, not 13.45 ETH

### Hypothesis 2: ChangeNow Quote vs Actual Send Amount Mismatch

**Likely:** VERY HIGH

**Evidence:**
Looking at the architecture flow:

```
GCSplit2 → ChangeNow API → Get quote for swap
         ← Response: {
              "fromAmount": "4.48332809",  // ETH needed to send
              "toAmount": "13.45",         // USDT you'll receive
              "estimatedAmount": "0.00115" // Estimated ETH (?)
           }
```

**The Issue:**
- ChangeNow returns `fromAmount` = amount of ETH to SEND
- ChangeNow returns `toAmount` = amount of USDT to RECEIVE
- If these get swapped, we'd send the wrong amount

**Possible Bug:**
```python
# WRONG (sending outcome amount instead of input amount)
from_amount = changenow_response['toAmount']  # ❌ This is the OUTPUT

# CORRECT (sending input amount to get desired output)
from_amount = changenow_response['fromAmount']  # ✅ This is the INPUT
```

### Hypothesis 3: Fee Calculation Error

**Likely:** MEDIUM

**Evidence:**
- User pays $5 USD
- After NowPayments fees (3-5%), outcome = ~$4.75 USD
- After our platform fee (10%), payout = ~$4.28 USD
- ChangeNow needs ETH to convert to USDT

**Potential Issue:**
Are we calculating:
- Fee-inclusive amount (total ETH including ChangeNow fees) ✅ CORRECT
- Fee-exclusive amount (just the output USDT value) ❌ WRONG

If we're not accounting for ChangeNow's fees properly:
- Need to send: 4.48 ETH to get 13.45 USDT ✅
- Actually sending: 0.00115 ETH to get 3.46 USDT ❌

### Hypothesis 4: Precision Loss in Amount Conversion

**Likely:** LOW (but possible)

**Evidence:**
```python
# wallet_manager.py line 171
amount_wei = self.w3.to_wei(amount, 'ether')
```

**Potential Issue:**
- Input: `amount` as float (e.g., 4.48332809)
- Conversion: Float → Wei → Integer
- Precision: Python floats are 64-bit (15-17 significant digits)
- ETH precision: 18 decimal places

**Test:**
```python
>>> from web3 import Web3
>>> amount = 4.48332809
>>> Web3.to_wei(amount, 'ether')
4483328090000000000  # ✅ Correct (matches log)
```

**Conclusion:** Precision loss is NOT the issue here.

---

## Upstream Data Flow Analysis

### Step-by-Step Payment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User Payment via NowPayments                                 │
│    - User pays $5 USD                                           │
│    - NowPayments converts to ETH                                │
│    - NowPayments sends IPN with outcome_amount = 0.00448 ETH    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. np-webhook-10-26 (IPN Handler)                               │
│    - Receives IPN callback                                      │
│    - Extracts outcome_amount_usd (e.g., $13.45)                 │
│    - Stores in database                                         │
│    - Triggers GCWebhook1                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. GCSplit1-10-26 (Fee Splitter)                                │
│    - Receives outcome_amount_usd = $13.45                       │
│    - Calculates platform fee (10%)                              │
│    - Client payout = $13.45 × 0.90 = $12.11                     │
│    - Platform fee = $13.45 × 0.10 = $1.34                       │
│    - Sends to GCSplit2                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. GCSplit2-10-26 (ChangeNow Quote Fetcher)                     │
│    - Receives payout_amount_usd = $12.11                        │
│    - Calls ChangeNow API:                                       │
│      GET /v2/exchange/estimated-amount                          │
│      ?from=eth&to=usdt&amount=12.11&flow=standard               │
│    - ChangeNow responds:                                        │
│      {                                                           │
│        "fromAmount": "4.48332809",  ← ETH to send                │
│        "toAmount": "12.11",         ← USDT to receive            │
│        "estimatedAmount": "0.00115" ← ??? (unclear)              │
│      }                                                           │
│    - Sends to GCHostPay1                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. GCHostPay1-10-26 (Payment Orchestrator)                      │
│    - Receives from_amount from GCSplit2                         │
│    - Question: What value is this?                              │
│      Option A: fromAmount (4.48 ETH) ✅ CORRECT                 │
│      Option B: toAmount (12.11 USDT) ❌ WRONG                   │
│      Option C: estimatedAmount (0.00115 ETH) ❌ WRONG           │
│    - Encrypts token for GCHostPay3                              │
│    - Enqueues to GCHostPay3                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. GCHostPay3-10-26 (ETH Payment Executor)                      │
│    - Receives encrypted token                                   │
│    - Decrypts: from_amount = ???                                │
│    - Calls wallet_manager.send_eth_payment(                     │
│        to_address=changenow_payin_address,                      │
│        amount=from_amount  ← CRITICAL: What is this value?      │
│      )                                                           │
│    - Observed: Sending both 4.48 ETH AND 0.00115 ETH            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Critical Questions

### Q1: What is GCHostPay3 receiving in the `from_amount` field?

**Expected:** The amount of ETH to send to ChangeNow (e.g., 4.48332809 ETH)

**Actual:** Two different values alternating:
- 4.48332809 ETH (large)
- 0.00115340416715763 ETH (small)

### Q2: Where does the small amount (0.00115 ETH) come from?

**Hypothesis A:** ChangeNow `estimatedAmount` field
- Some ChangeNow API responses include `estimatedAmount`
- This might be a fee estimate or minimum amount
- **Should NOT be used as the send amount**

**Hypothesis B:** Incorrect fee calculation
- If we're dividing instead of multiplying
- Or using wrong fee percentage

**Hypothesis C:** Testing/debug value
- Hardcoded test amount that shouldn't be in production

### Q3: Where does the large amount (4.48 ETH) come from?

**Hypothesis A:** ChangeNow `fromAmount` (CORRECT)
- This is the actual amount to send
- $13,449 USD worth of ETH
- **This seems HIGH for a $5 payment**

**Hypothesis B:** Accumulated batch amount
- If this is a threshold payout
- Multiple payments accumulated
- Total ETH needed for batch conversion

**Hypothesis C:** Bug multiplying instead of dividing
- Wrong direction of calculation
- Using inverse of correct amount

---

## The $13,449 Problem

### Why is 4.48 ETH being sent for a $5 payment?

**Math Check:**
- 4.48332809 ETH × $3,000/ETH = $13,449 USD
- User paid: $5 USD
- **Ratio:** 2,690x more than user paid! ❌

**This is FINANCIALLY IMPOSSIBLE unless:**

1. **Accumulated Batch Payment (Threshold Context)**
   - Multiple users' payouts accumulated
   - Total payout = $12,000+ USD
   - Context = "threshold"
   - **Check logs for context field**

2. **ChangeNow API Response Misinterpretation**
   - We're reading wrong field
   - Or ChangeNow quote is for wrong direction (USDT→ETH instead of ETH→USDT)

3. **Currency Confusion**
   - Treating USDT amount as ETH amount
   - 12.11 USDT mistaken as 12.11 ETH (but log shows 4.48, not 12.11)

---

## Code Investigation Required

### Files to Check

#### 1. GCSplit2-10-26/tps2-10-26.py
**Critical Section:** ChangeNow API call and response parsing

```python
# NEED TO VERIFY:
changenow_response = changenow_client.get_estimated_amount(
    from_currency='eth',
    to_currency='usdt',
    amount=payout_amount_usd  # ← Is this correct direction?
)

# What fields are extracted?
from_amount = changenow_response.get('fromAmount')  # ✅ or
from_amount = changenow_response.get('estimatedAmount')  # ❌
```

#### 2. GCSplit2-10-26/changenow_client.py
**Critical Section:** API request parameters

```python
# NEED TO VERIFY:
# Are we requesting:
params = {
    'from': 'eth',
    'to': 'usdt',
    'amount': payout_usd,  # ← Fixed flow: Request ETH needed for X USDT
    'flow': 'fixed'  # or 'standard'?
}

# OR reverse direction:
params = {
    'from': 'usdt',  # ❌ WRONG
    'to': 'eth',     # ❌ WRONG
    'amount': payout_usd
}
```

#### 3. GCHostPay1-10-26/token_manager.py
**Critical Section:** Token encryption for GCHostPay3

```python
# NEED TO VERIFY:
# What value goes into from_amount field?
token_data = {
    'unique_id': unique_id,
    'cn_api_id': cn_api_id,
    'from_currency': 'eth',
    'from_network': 'eth',
    'from_amount': ???,  # ← What is this value?
    'payin_address': changenow_payin_address
}
```

---

## Verification Steps

### Step 1: Check ChangeNow API Direction

**Action:** Review GCSplit2 ChangeNow client implementation

**Expected:**
```
Request: "I want to receive 12.11 USDT. How much ETH do I need to send?"
Response: "You need to send 0.00448332809 ETH to receive 12.11 USDT"
```

**Not:**
```
Request: "I have 12.11 ETH. How much USDT will I receive?"
Response: "You'll receive ~$36,330 USDT"  ← WRONG DIRECTION
```

### Step 2: Trace a Single Transaction End-to-End

**Action:** Follow one payment from IPN → GCHostPay3

1. User pays $5 USD
2. NowPayments outcome = $4.75 USD (after 5% fee)
3. Platform keeps 10% = $0.48
4. Client payout = $4.27 USD
5. ChangeNow quote: Need 0.00158 ETH to get 4.27 USDT (example)
6. GCHostPay3 should send: 0.00158 ETH

**Compare:** Does GCHostPay3 log match step 6?

### Step 3: Check Context Field

**Action:** Review logs for `context` field value

```python
# tphp3-10-26.py line 164
context = decrypted_data.get('context', 'instant')
```

**If context = 'threshold':**
- This is a batch payout
- Amount represents accumulated payouts
- 4.48 ETH might be legitimate for multiple users

**If context = 'instant':**
- This is a single payout
- 4.48 ETH is absolutely wrong
- Should be ~0.00158 ETH for $5 payment

### Step 4: Check Database Records

**Action:** Query `split_payout_hostpay` table

```sql
SELECT
    unique_id,
    cn_api_id,
    from_amount,
    from_currency,
    payin_address,
    created_at
FROM split_payout_hostpay
WHERE created_at >= '2025-11-02 17:00:00'
ORDER BY created_at DESC
LIMIT 20;
```

**Analysis:**
- Are there two different `cn_api_id` values (indicating two separate transactions)?
- Do the amounts match the logs (4.48 and 0.00115)?
- What are the actual ChangeNow API IDs?

---

## Impact Assessment

### Financial Risk

**IF the bug allows payments to execute:**

| Scenario | User Payment | Actual Payout | Loss per Transaction |
|----------|--------------|---------------|----------------------|
| Scenario A: 4.48 ETH sent | $5 USD | $13,449 USD | -$13,444 USD ❌ |
| Scenario B: 0.00115 ETH sent | $5 USD | $3.46 USD | +$1.54 USD ✅ (underpay) |

**Current State:**
- All payments timing out ✅ GOOD (preventing financial loss)
- But payments are stuck ❌ BAD (users not receiving payouts)

### User Impact

**Instant Payouts (context='instant'):**
- Expected payout time: 5-10 minutes
- Actual: Failing after 3 attempts (15+ minutes)
- Users not receiving channel access
- Manual intervention required

**Threshold Payouts (context='threshold'):**
- Expected payout: When accumulated amount hits threshold
- Actual: Failing completely
- Accumulated funds stuck
- Batch conversion not working

---

## Timeout Root Cause (Separate Issue)

**Why are transactions timing out?**

```
Transaction confirmation timeout after 300s: 0x4056d8e3...
```

**Possible Causes:**

1. **Insufficient Gas Price**
   - Transactions stuck in mempool
   - Need higher gas fees
   - Network congestion

2. **Insufficient Wallet Balance**
   - Trying to send 4.48 ETH
   - Wallet doesn't have enough funds
   - Transaction never confirms

3. **Nonce Issues**
   - Multiple transactions using same nonce
   - Replacement transaction needed
   - Or nonce gap

4. **RPC Provider Issues**
   - Alchemy/Infura connectivity
   - Transaction broadcast failing
   - Receipt retrieval timing out

**Check Wallet Balance:**
```bash
# Get wallet balance
WALLET_ADDRESS="<from logs>"
curl https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"eth_getBalance",
    "params":["'$WALLET_ADDRESS'", "latest"],
    "id":1
  }'
```

**If balance < 4.48 ETH:**
- Explains timeout (transaction can't execute)
- Need to fund wallet
- BUT: Doesn't explain the amount discrepancy

---

## Recommended Investigation Priority

### Priority 1: CRITICAL - Identify Amount Source

**Goal:** Determine where 4.48 ETH and 0.00115 ETH values originate

**Actions:**
1. Read GCSplit2-10-26/changenow_client.py - Check API call direction
2. Read GCSplit2-10-26/tps2-10-26.py - Check response parsing
3. Check ChangeNow API documentation - Verify field meanings
4. Add detailed logging to GCHostPay1 - Log from_amount at token creation

**Expected Outcome:**
- Identify which ChangeNow field is being used
- Confirm if API direction is correct
- Determine if amount calculation is right

### Priority 2: HIGH - Check Transaction Context

**Goal:** Determine if these are instant or threshold payouts

**Actions:**
1. Review GCHostPay3 logs for `context` field
2. Query database for associated batch_conversion_id
3. Check if amounts represent single or accumulated payouts

**Expected Outcome:**
- Confirm if 4.48 ETH is legitimate (batch) or wrong (instant)
- Understand why two amounts are alternating

### Priority 3: MEDIUM - Investigate Timeout Issue

**Goal:** Resolve transaction confirmation failures

**Actions:**
1. Check host wallet balance
2. Review gas price strategy
3. Check Ethereum RPC connectivity
4. Verify ChangeNow payin addresses are valid

**Expected Outcome:**
- Fix timeout issues
- Enable payments to complete

---

## Proposed Solution (Pending Investigation)

### Fix Option A: Correct ChangeNow API Usage

**IF Issue:** Using wrong ChangeNow field or direction

**Fix:**
```python
# GCSplit2-10-26/changenow_client.py

# BEFORE (if wrong):
quote = self.get_estimate(from='usdt', to='eth', amount=payout_usd)
from_amount = quote['toAmount']  # ❌ Wrong field

# AFTER (correct):
quote = self.get_estimate(from='eth', to='usdt', amount=payout_usd, flow='fixed')
from_amount = quote['fromAmount']  # ✅ Correct field
```

### Fix Option B: Add Amount Validation

**IF Issue:** Amount calculation logic error

**Fix:**
```python
# GCHostPay3-10-26/tphp3-10-26.py

# Add validation before payment
if context == 'instant':
    # Single payment should be small amount
    if from_amount > 0.1:  # More than 0.1 ETH suspicious
        print(f"⚠️ [VALIDATION] Suspiciously large instant payout: {from_amount} ETH")
        # Log to database, send alert, don't execute

elif context == 'threshold':
    # Batch payment can be larger
    if from_amount > 100:  # More than 100 ETH extremely suspicious
        print(f"⚠️ [VALIDATION] Suspiciously large batch payout: {from_amount} ETH")
```

### Fix Option C: Two-Phase Verification

**IF Issue:** Uncertainty about correct amount

**Fix:**
```python
# Add verification step before payment

# Step 1: Get ChangeNow quote again
verification_quote = changenow_client.get_estimate(
    from_currency='eth',
    to_currency='usdt',
    amount=expected_usdt_output
)

# Step 2: Compare with received amount
if abs(verification_quote['fromAmount'] - from_amount) > 0.01:
    # Amounts don't match - something wrong
    raise ValueError(f"Amount mismatch: expected {verification_quote['fromAmount']}, got {from_amount}")

# Step 3: Proceed with payment only if verified
```

---

## Next Steps

1. **Read GCSplit2 ChangeNow integration** - Understand exact API usage
2. **Add comprehensive logging** - Track amount at each step
3. **Query database** - Check actual values being stored
4. **Review ChangeNow API docs** - Confirm field meanings
5. **Test with small amount first** - Before enabling production
6. **Create validation checklist** - Prevent future amount errors

---

## Open Questions

1. **What is the `estimatedAmount` field from ChangeNow?**
   - Is this being used anywhere?
   - Should it be ignored?

2. **Are there two separate transactions or one transaction retrying?**
   - Same cn_api_id or different?
   - Same unique_id or different?

3. **What is the host wallet balance?**
   - Enough to cover 4.48 ETH?
   - Enough to cover 0.00115 ETH?

4. **Has any payment ever succeeded?**
   - Check database for completed transactions
   - Review ChangeNow dashboard for received funds

5. **What is the ChangeNow minimum send amount for ETH→USDT?**
   - Could 0.00115 ETH be below minimum?
   - Would that cause timeout?

---

## Conclusion

**Critical Finding:** GCHostPay3 is attempting to send two drastically different ETH amounts (4.48 ETH vs 0.00115 ETH) with a 3,886x discrepancy ratio.

**Primary Hypothesis:** The amount calculation in GCSplit2 or GCHostPay1 is using the wrong ChangeNow API field, wrong direction, or wrong currency.

**Immediate Action Required:**
1. **STOP all production payments** until investigation complete
2. **Review GCSplit2 ChangeNow integration** code
3. **Verify amount flow** end-to-end
4. **Check wallet balance** to prevent accidental large sends
5. **Add amount validation** guards before payment execution

**Financial Risk:** If the 4.48 ETH payments were to succeed, each would result in a ~$13,444 USD loss on a $5 user payment - a catastrophic financial bug.

**Good News:** All payments are currently timing out, preventing the bug from causing actual financial loss. But this also means users aren't receiving legitimate payouts.

**Priority:** CRITICAL - This must be investigated and resolved before any payments can process.
