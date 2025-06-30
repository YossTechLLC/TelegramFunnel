# 🔧 Webhook URL Update Required - Payment Flow Fix

## 🎯 **Problem Identified**

**Issue**: Client wallets are not receiving payouts because the success webhook URL points to the wrong service.

**Root Cause**: 
- Success URL points to: `https://tph5-291176869049.us-central1.run.app`
- Payment splitting logic is in: `https://tph30-291176869049.us-central1.run.app`

## ✅ **Solution: Update Environment Variable**

You need to update your `~/.profile` file to point the webhook URL to the correct service.

### **Required Change**:

```bash
# Change this line in your ~/.profile:
export WEBHOOK_BASE_URL="https://tph5-291176869049.us-central1.run.app"

# To this:
export WEBHOOK_BASE_URL="https://tph30-291176869049.us-central1.run.app"
```

## 📋 **Step-by-Step Instructions**

### **1. Edit your .profile file**:
```bash
nano ~/.profile
```

### **2. Find and update the WEBHOOK_BASE_URL line**:
```bash
# OLD (causing the issue):
export WEBHOOK_BASE_URL="https://tph5-291176869049.us-central1.run.app"

# NEW (will fix the payment flow):
export WEBHOOK_BASE_URL="https://tph30-291176869049.us-central1.run.app"
```

### **3. Save and reload your environment**:
```bash
# Save the file (Ctrl+X, then Y, then Enter in nano)
source ~/.profile
```

### **4. Restart TelePay30**:
```bash
# Stop the current telepay30.py process (Ctrl+C)
# Then restart it:
python telepay30.py
```

## 🔍 **How to Verify the Fix**

### **Before the fix** (current behavior):
```
✅ Payment gateway created successfully for $3.32
🔗 Invoice URL: https://nowpayments.io/payment/?iid=5223603441
✅ Complete success URL generated: https://tph5-291176869049.us-central1.run.app?token=...
```
→ Success URL calls tph5 (wrong service) → No client payout

### **After the fix** (expected behavior):
```
✅ Payment gateway created successfully for $3.32  
🔗 Invoice URL: https://nowpayments.io/payment/?iid=XXXXXXX
✅ Complete success URL generated: https://tph30-291176869049.us-central1.run.app?token=...
```
→ Success URL calls tph30 (correct service) → Client receives TRX/crypto

## 🎯 **Expected Results**

After making this change:

1. **Payment Flow**: User pays → Money goes to host wallet → Success URL calls tph30 service
2. **Payment Splitting**: tph30 webhook automatically triggers ChangeNOW swap process  
3. **Client Payout**: Client wallet receives TRX (or requested cryptocurrency)
4. **Visibility**: You'll see payment splitting logs in tph30 service logs

## 🚨 **Important Notes**

- **Make sure tph30 service is deployed**: The URL `https://tph30-291176869049.us-central1.run.app` must be accessible
- **Monitor tph30 logs**: After the change, check tph30 service logs to see payment splitting execution
- **Test with small payment**: Test the flow with a small payment amount first

## 📊 **What Should Happen Next**

After updating and restarting, when a payment is made:

1. ✅ TelePay30 generates correct success URL (pointing to tph30)
2. ✅ User completes payment via NowPayments  
3. ✅ NowPayments calls success webhook → tph30 service
4. ✅ tph30 executes payment splitting logic
5. ✅ ChangeNOW swap processes: ETH → TRX (or other currency)
6. ✅ Client wallet receives the cryptocurrency payout

**This should resolve the missing client wallet payouts!** 🎉