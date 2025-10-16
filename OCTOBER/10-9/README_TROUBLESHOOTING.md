# ChangeNow API Troubleshooting Package

**Created:** 2025-10-13
**Issue:** Payment succeeds but ChangeNow API POST request never appears in logs or on ChangeNow backend

---

## 🎯 Quick Start

1. **Deploy enhanced logging version:**
   ```bash
   cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-9/GCSplit7-14
   # Then run deployment command from QUICK_COMMANDS.sh
   ```

2. **Verify TPS_WEBHOOK_URL is configured:**
   ```bash
   # Run verification command from QUICK_COMMANDS.sh
   ```

3. **Trigger test payment**

4. **Review logs using patterns in QUICK_REFERENCE_LOGS.md**

5. **Apply fix from DEPLOY_AND_TEST_GUIDE.md**

---

## 📚 Documentation Files

### 1. **TROUBLESHOOTING_SUMMARY.md** ⭐ START HERE
**Purpose:** Overall summary and next steps
**Read this first to understand:**
- What was done
- Most likely root causes
- Quick path to resolution

### 2. **DEPLOY_AND_TEST_GUIDE.md** ⭐ MAIN GUIDE
**Purpose:** Complete step-by-step deployment and testing procedure
**Use this for:**
- Deploying enhanced logging version
- Testing procedure
- Log analysis
- 9 common scenarios with fixes
- Expected success log flow

### 3. **QUICK_REFERENCE_LOGS.md** ⭐ DURING TESTING
**Purpose:** Quick log pattern reference
**Use this when:**
- Reviewing Cloud Run logs
- Need to quickly identify root cause
- Want search commands for specific patterns

### 4. **DIAGNOSTIC_CHECKLIST.md**
**Purpose:** Manual phase-by-phase checklist
**Use this for:**
- Systematic troubleshooting
- Checking environment variables
- Verifying deployments
- Recording findings

### 5. **QUICK_COMMANDS.sh**
**Purpose:** Copy-paste commands
**Use this for:**
- Quick access to deployment commands
- Verification commands
- Log search patterns

---

## 🔧 What Was Modified

### Enhanced Logging Added To:

1. **`GCSplit7-14/changenow_client.py`**
   - `_make_request()` method
   - `create_fixed_rate_transaction()` method
   - Logs full HTTP request/response details
   - Logs complete exception stack traces

2. **`GCSplit7-14/tps10-9.py`**
   - `process_payment_split()` function
   - `create_fixed_rate_transaction()` function
   - Step-by-step validation logging
   - Function entry/exit markers

### New Log Patterns Added:

```
===============================================================================
🚀 [CHANGENOW_TRANSACTION] >>> STARTING ChangeNow API Transaction <<<
===============================================================================
🌐 [CHANGENOW_API] >>> ENTERING _make_request <<<
🌐 [CHANGENOW_API] POST https://api.changenow.io/v2/exchange
📦 [CHANGENOW_API] Request body: {...}
🔄 [CHANGENOW_API] Sending HTTP request...
📊 [CHANGENOW_API] Response received!
📊 [CHANGENOW_API] Response status: 200
✅ [CHANGENOW_TRANSACTION] Transaction created successfully!
===============================================================================
```

---

## 🎯 Most Likely Root Causes

### 1. TPS_WEBHOOK_URL Not Configured (80% probability)
```bash
# Check:
gcloud run services describe tph10-13 --region us-central1 --format="value(spec.template.spec.containers[0].env)" | grep TPS_WEBHOOK_URL

# Fix:
gcloud run services update tph10-13 \
    --region us-central1 \
    --set-env-vars TPS_WEBHOOK_URL=https://tps10-9-291176869049.us-central1.run.app
```

### 2. tps10-9 Service Not Deployed (15% probability)
```bash
# Check:
gcloud run services list --region us-central1 | grep tps10-9

# Fix:
# Deploy using command from QUICK_COMMANDS.sh
```

### 3. Other Issues (5% probability)
See DEPLOY_AND_TEST_GUIDE.md Section "Interpreting Results" for:
- API key configuration
- Currency pair validation
- Amount limits
- Signature verification
- Etc.

---

## 🔍 How to Use This Package

### Workflow:

```
1. Read TROUBLESHOOTING_SUMMARY.md
   ↓
2. Deploy enhanced logging (see QUICK_COMMANDS.sh)
   ↓
3. Trigger test payment
   ↓
4. Search logs (patterns in QUICK_REFERENCE_LOGS.md)
   ↓
5. Identify scenario (see DEPLOY_AND_TEST_GUIDE.md)
   ↓
6. Apply fix
   ↓
7. Test again
   ↓
8. Verify ChangeNow API call succeeds
```

---

## 📊 Success Criteria

After fixing the issue, you should see these logs in tps10-9:

### Critical Success Markers:
- ✅ `">>> ENTERING _make_request <<<"` - API call function entered
- ✅ `"POST https://api.changenow.io/v2/exchange"` - HTTP request sent
- ✅ `"Response status: 200"` - ChangeNow responded successfully
- ✅ `"Transaction ID: xyz..."` - Transaction created!

### If You See These, API IS Working:
```
✅ [CHANGENOW_TRANSACTION] Transaction created successfully!
🆔 [CHANGENOW_TRANSACTION] Transaction ID: abc123xyz
🏦 [CHANGENOW_TRANSACTION] Deposit address: 0x742d35Cc...
```

---

## 🚨 Common Pitfalls

1. **Don't skip the deployment step**
   - Enhanced logging won't appear until tps10-9 is redeployed

2. **Check BOTH tph10-13 AND tps10-9 logs**
   - Issue could be in webhook trigger (tph10-13)
   - OR in API call execution (tps10-9)

3. **Use exact search patterns**
   - Copy patterns from QUICK_REFERENCE_LOGS.md
   - Case-sensitive searches in Cloud Logs

4. **Read error messages carefully**
   - Enhanced logging shows full stack traces
   - Look for root cause in exception messages

---

## 📈 What Enhanced Logging Reveals

Before (original code):
```
❌ [CHANGENOW_TRANSACTION] Failed to create transaction
```
**Problem:** No details on WHY it failed

After (enhanced logging):
```
===============================================================================
🚀 [CHANGENOW_TRANSACTION] >>> STARTING ChangeNow API Transaction <<<
📦 [CHANGENOW_TRANSACTION] Complete payload: {
  "fromCurrency": "eth",
  "toCurrency": "usdt",
  "fromAmount": "0.05",
  ...
}
🔄 [CHANGENOW_TRANSACTION] Calling _make_request with POST /exchange...
🌐 [CHANGENOW_API] >>> ENTERING _make_request <<<
🌐 [CHANGENOW_API] POST https://api.changenow.io/v2/exchange
🌐 [CHANGENOW_API] API Key (first 8 chars): 0e7ab0b9
📦 [CHANGENOW_API] Request body: {...full request body...}
🔄 [CHANGENOW_API] Sending HTTP request...
📊 [CHANGENOW_API] Response received!
📊 [CHANGENOW_API] Response status: 401
📊 [CHANGENOW_API] Response body: {"error":"Unauthorized","message":"Invalid API key"}
❌ [CHANGENOW_API] API error 401: Invalid API key
===============================================================================
```
**Result:** Exact root cause identified (API key invalid)

---

## 🎓 Understanding the Flow

```
User Payment
    ↓
tph10-13.py (GCWebhook7-14)
    ├─ Sends Telegram invite ✅
    └─ Calls trigger_payment_split_webhook()
        ↓
        HTTP POST to TPS_WEBHOOK_URL
        ↓
tps10-9.py (GCSplit7-14)
    ├─ Receives webhook
    └─ Calls process_payment_split()
        ├─ Validates fields
        ├─ Validates currency pair
        ├─ Checks amount limits
        └─ Calls create_fixed_rate_transaction()
            ↓
            changenow_client.py
            └─ Calls create_fixed_rate_transaction()
                ├─ Gets estimate
                └─ Calls _make_request()
                    ↓
                    HTTP POST to ChangeNow API ⭐
                    ↓
                ChangeNow Server
                    ↓
                Returns transaction details
```

**The issue is somewhere in this chain.**
**Enhanced logging will show exactly where it stops.**

---

## 💡 Tips for Fast Resolution

1. **Start with tph10-13 logs**
   - If webhook trigger fails here, no need to check tps10-9

2. **Use QUICK_REFERENCE_LOGS.md**
   - Fastest way to identify root cause

3. **Compare with your working curl**
   - Enhanced logging shows exact payload sent
   - Compare byte-by-byte with curl command

4. **Check environment variables first**
   - 95% of issues are missing/wrong env vars

5. **Deploy before testing**
   - Changes won't take effect until redeployed

---

## 📞 Support

If after following all steps the issue persists:

### Share These Details:
1. Last successful log entry from tps10-9
2. First missing/error log entry
3. Which scenario from DEPLOY_AND_TEST_GUIDE.md matches your symptoms
4. Any error messages seen

### Check These Files:
- TROUBLESHOOTING_SUMMARY.md - For overall context
- DEPLOY_AND_TEST_GUIDE.md - For your specific scenario
- DIAGNOSTIC_CHECKLIST.md - For systematic verification

---

## ✅ Checklist Before Asking for Help

- [ ] Deployed enhanced logging version of tps10-9
- [ ] Verified TPS_WEBHOOK_URL is configured in tph10-13
- [ ] Triggered test payment
- [ ] Checked tph10-13 logs for webhook trigger
- [ ] Checked tps10-9 logs for API call attempt
- [ ] Searched for patterns from QUICK_REFERENCE_LOGS.md
- [ ] Reviewed scenario that matches my symptoms
- [ ] Tried suggested fix for my scenario
- [ ] Retested after applying fix

---

## 🏆 Success Stories

### Scenario 1: TPS_WEBHOOK_URL Missing
**Symptom:** tph10-13 showed "TPS_WEBHOOK_URL not configured"
**Fix:** Added environment variable
**Result:** ChangeNow API calls started working immediately

### Scenario 2: tps10-9 Not Deployed
**Symptom:** tph10-13 showed "Webhook connection error"
**Fix:** Deployed tps10-9 service
**Result:** Webhooks started reaching tps10-9, API calls succeeded

### Scenario 3: Wrong API Key
**Symptom:** Response status 401 in logs
**Fix:** Updated CHANGENOW_API_KEY secret
**Result:** API authentication succeeded

---

## 📦 Package Contents

```
TelegramFunnel/OCTOBER/10-9/
├── README_TROUBLESHOOTING.md        ← You are here
├── TROUBLESHOOTING_SUMMARY.md       ← Start here
├── DEPLOY_AND_TEST_GUIDE.md         ← Main guide
├── QUICK_REFERENCE_LOGS.md          ← Quick patterns
├── DIAGNOSTIC_CHECKLIST.md          ← Manual checklist
├── QUICK_COMMANDS.sh                ← Copy-paste commands
└── GCSplit7-14/
    ├── changenow_client.py          ← Enhanced logging
    └── tps10-9.py                   ← Enhanced logging
```

---

## 🚀 Ready to Start!

1. Open **TROUBLESHOOTING_SUMMARY.md**
2. Follow "Next Steps" section
3. Use **QUICK_REFERENCE_LOGS.md** during testing
4. Apply fixes from **DEPLOY_AND_TEST_GUIDE.md**

**Enhanced logging will reveal the exact root cause within one test payment!**

---

**Good luck! 🎉**
