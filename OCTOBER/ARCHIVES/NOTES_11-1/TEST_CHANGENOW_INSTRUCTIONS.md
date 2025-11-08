# ChangeNow Precision Test - Instructions

## Purpose

This test determines if your system can safely handle high-value tokens like SHIBA INU (10M+ tokens per $100).

**Question:** Does ChangeNow return token amounts as strings or numbers in JSON?
- **Strings** (`"toAmount": "10000000"`) → ✅ Safe, exact precision
- **Numbers** (`"toAmount": 10000000`) → ⚠️ Risky, float precision limits

---

## Quick Start

### Step 1: Get ChangeNow API Key

1. Go to https://changenow.io/
2. Sign up or log in
3. Navigate to API settings
4. Copy your API key

### Step 2: Set API Key

**Option A - Environment Variable (Recommended):**
```bash
export CHANGENOW_API_KEY='your_api_key_here'
```

**Option B - Edit Script:**
```bash
# Edit line 24 of test_changenow_precision.py
CHANGENOW_API_KEY = 'your_api_key_here'
```

### Step 3: Install Dependencies

```bash
pip3 install requests
```

### Step 4: Run Test

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26
python3 test_changenow_precision.py
```

---

## What the Test Does

Tests 3 scenarios:

1. **SHIB (Shiba Inu)** - ~10,000,000 tokens for $100
   - High quantity, tests if system can handle millions

2. **PEPE** - ~Billions of tokens for $100
   - Extreme quantity, stress test

3. **XRP** - ~100 tokens for $100
   - Control test, normal quantity

---

## Understanding Results

### ✅ BEST CASE - All Tests Show Strings

```
🎯 Conclusion:
   ✅ ChangeNow returns amounts as STRINGS
   ✅ System CAN safely handle high-value tokens
```

**Action:** You're good to go! System will work as-is.

---

### 🟡 BORDERLINE - Numbers but No Precision Loss

```
🎯 Conclusion:
   🟡 ChangeNow returns amounts as NUMBERS
   🟡 System MAY work but precision is at risk
```

**Action:** Implement Fix #2 (see below) to be safe.

---

### ❌ WORST CASE - Precision Loss Detected

```
🎯 Conclusion:
   ❌ Precision loss detected in some test cases
   ❌ System NEEDS fixes before handling high-value tokens
```

**Action:** Implement both Fix #1 and Fix #2 immediately.

---

## Example Output

```
================================================================================
TEST: SHIB (Shiba Inu) - 100K per USD
================================================================================

📤 Request:
   URL: https://api.changenow.io/v2/exchange/estimated-amount
   From: 100 usdt
   To: shib
   Expected: ~10,000,000 SHIB

📥 Response:
   Status: 200

📄 Raw JSON Response:
   {"fromCurrency":"usdt","toCurrency":"shib","toAmount":"9876543.21",...

🔍 Analysis:
   toAmount value: 9876543.21
   toAmount type: str
   toAmount repr: '9876543.21'
   JSON format: STRING

🧪 Precision Test:
   Original: 9876543.21
   As float: 9876543.21
   Float→str: 9876543.21
   As Decimal: 9876543.21
   Status: ✅ NO PRECISION LOSS

💰 Exchange Details:
   From Amount: 100 USDT
   To Amount: 9876543.21 SHIB
   Deposit Fee: 0
   Withdrawal Fee: 50000

📊 Digit Analysis:
   Total digits: 9
   Float safety: ✅ SAFE (≤15 digits)
```

---

## If Fixes Are Needed

### Fix #1: GCBatchProcessor Float Conversion

**File:** `GCBatchProcessor-10-26/batch10-26.py`
**Line:** 149

**Change:**
```python
# OLD (risky):
total_amount_usdt=float(total_usdt)

# NEW (safe):
total_amount_usdt=str(total_usdt)
```

Then update `token_manager.py` to handle string amounts.

---

### Fix #2: ChangeNow Response Parsing

**File:** `GCSplit2-10-26/changenow_client.py`
**Line:** 115

**Change:**
```python
# OLD (risky):
result = response.json()
to_amount = result.get('toAmount', 0)

# NEW (safe):
from decimal import Decimal

result = response.json()
to_amount = Decimal(str(result.get('toAmount', 0)))
```

---

## Troubleshooting

### Error: "API key not configured"

**Solution:** Set your ChangeNow API key (see Step 2)

### Error: "ModuleNotFoundError: No module named 'requests'"

**Solution:** Install requests library
```bash
pip3 install requests
```

### Error: HTTP 401 Unauthorized

**Solution:** Check your API key is correct

### Error: HTTP 429 Rate Limited

**Solution:** Wait 60 seconds and try again

### Test hangs or times out

**Solution:** Check internet connection, ChangeNow API may be down

---

## What Happens Next?

### If Test Shows ✅ SAFE

1. No code changes needed
2. You can enable SHIB/PEPE payouts immediately
3. Monitor first payout to verify end-to-end

### If Test Shows 🟡 BORDERLINE

1. Implement Fix #2 (ChangeNow parsing)
2. Test again to verify
3. Enable SHIB/PEPE payouts

### If Test Shows ❌ UNSAFE

1. Implement both Fix #1 and Fix #2
2. Test again to verify
3. Consider refactoring token manager (long-term)
4. Enable SHIB/PEPE payouts only after fixes deployed

---

## Additional Resources

- **Full Analysis:** `LARGE_TOKEN_QUANTITY_ANALYSIS.md`
- **Database Review:** `DATABASE_MAPPING_REVIEW_REPORT.md`
- **ChangeNow API Docs:** https://changenow.io/api/docs

---

## Questions?

**Q: Do I need to run this test for every token?**
A: No, just once to determine ChangeNow's response format. All tokens use the same format.

**Q: What if I want to test a different token?**
A: Edit `TEST_CASES` array in the script, add your token.

**Q: Is this test safe to run in production?**
A: Yes, it only queries ChangeNow estimate API (no actual swaps).

**Q: What's the cost?**
A: Free, ChangeNow estimate API has no fees.

---

**Created:** 2025-10-31
**Purpose:** Verify system readiness for high-value tokens (SHIB/PEPE)
**Status:** Ready to run
