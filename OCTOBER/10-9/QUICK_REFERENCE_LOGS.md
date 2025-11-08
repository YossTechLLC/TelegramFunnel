# Quick Reference: Log Patterns to Search

## Critical Success Markers (These MUST appear for ChangeNow API to work)

### In tph10-13 Logs:
```
✅ [PAYMENT_SPLITTING] Webhook triggered successfully
```
**Meaning:** tps10-9 received the webhook

---

### In tps10-9 Logs:
```
🎯 [WEBHOOK] TPS10-9 Webhook Called
```
**Meaning:** Webhook reached tps10-9

```
>>> ENTERING _make_request <<<
```
**Meaning:** HTTP request function called

```
POST https://api.changenow.io/v2/exchange
```
**Meaning:** Actual HTTP POST being sent

```
Response status: 200
```
**Meaning:** ChangeNow API responded successfully

```
✅ [CHANGENOW_TRANSACTION] Transaction ID:
```
**Meaning:** Transaction created! API is working!

---

## Critical Failure Markers (Root Causes)

### TPS_WEBHOOK_URL Not Configured:
```
⚠️ [PAYMENT_SPLITTING] TPS_WEBHOOK_URL not configured
```
**Fix:** Add environment variable to tph10-13

---

### tps10-9 Not Accessible:
```
❌ [PAYMENT_SPLITTING] Webhook connection error
```
**Fix:** Deploy tps10-9 service

---

### API Key Missing/Wrong:
```
Response status: 401
```
**Fix:** Update CHANGENOW_API_KEY secret

---

### Currency Not Supported:
```
❌ [PAYMENT_SPLITTING] VALIDATION FAILED! Currency pair not supported
```
**Fix:** Use different payout currency

---

### Amount Too Small/Large:
```
❌ [PAYMENT_SPLITTING] VALIDATION FAILED! Amount outside limits
```
**Fix:** Adjust subscription price

---

## Search Commands for Google Cloud Logs

### tph10-13:
```
Search: "PAYMENT_SPLITTING"
Then look for: "Webhook triggered successfully" or errors
```

### tps10-9:
```
Search: "CHANGENOW_API"
Then look for: "POST /exchange" and "Response status:"
```

---

## If ChangeNow API IS Working

You'll see this sequence in tps10-9 logs:
1. `>>> ENTERING _make_request <<<`
2. `POST https://api.changenow.io/v2/exchange`
3. `Sending HTTP request...`
4. `Response received!`
5. `Response status: 200`
6. `✅ [CHANGENOW_TRANSACTION] Transaction ID:`

---

## If ChangeNow API Is NOT Working

The sequence will stop before step 6 above. Check where it stops:

**Stops at step 1?** → Function never called (validation failed earlier)
**Stops at step 2?** → Exception in _make_request
**Stops at step 3?** → Payload construction failed
**Stops at step 4?** → HTTP request never sent (connection error)
**Stops at step 5?** → No response (timeout)
**Status ≠ 200?** → API rejected request (check error message)
