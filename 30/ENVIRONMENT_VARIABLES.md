# TelegramFunnel/30 Environment Variables Guide

## 🔧 **Required Environment Variables**

Based on your current setup and the application requirements, here are the **corrected** environment variables for your `~/.profile` file:

### **Critical Fix Needed**

**❌ PROBLEM IDENTIFIED**: Your current `.profile` has this line:
```bash
export HOST_WALLET_PRIVATE_KEY="projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY_SECRET/versions/latest"
```

**✅ SOLUTION**: The secret name should be `HOST_WALLET_PRIVATE_KEY` (without `_SECRET` suffix):
```bash
export HOST_WALLET_PRIVATE_KEY="projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest"
```

## 📝 **Corrected ~/.profile File**

```bash
# Database Configuration
export DATABASE_HOST_SECRET="projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest"
export DATABASE_NAME_SECRET="projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest"
export DATABASE_USER_SECRET="projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest"
export DATABASE_PASSWORD_SECRET="projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest"
export CLOUD_SQL_CONNECTION_NAME="telepay-459221:us-central1:telepaypsql"

# Telegram Bot Configuration
export TELEGRAM_BOT_SECRET_NAME="projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest"
export TELEGRAM_BOT_USERNAME="projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest"

# Security & Signing
export SUCCESS_URL_SIGNING_KEY="projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest"

# Payment Provider Configuration
export PAYMENT_PROVIDER_SECRET_NAME="projects/291176869049/secrets/NOWPAYMENTS_API_KEY/versions/latest"
export NOWPAYMENT_WEBHOOK_KEY="projects/291176869049/secrets/NOWPAYMENT_WEBHOOK_KEY/versions/latest"

# ChangeNOW Integration (NEW)
export CHANGENOW_API_KEY="projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest"
export HOST_WALLET_ETH_ADDRESS="projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest"
export HOST_WALLET_PRIVATE_KEY="projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest"

# Webhook URLs
export TPS30_WEBHOOK_URL="https://tph30-291176869049.us-central1.run.app"
export TPBTCS1_WEBHOOK_URL="https://tpbtcs1-291176869049.us-central1.run.app"

# Legacy Webhook URLs (if still needed)
export TPS1_WEBHOOK_URL="https://tps1-291176869049.us-central1.run.app"
export TPS2_WEBHOOK_URL="https://tps2-291176869049.us-central1.run.app"
export TPS3_WEBHOOK_URL="https://tps3-291176869049.us-central1.run.app"

# Optional/Legacy Configuration
export WEBHOOK_BASE_URL="https://tph5-291176869049.us-central1.run.app"
export ONEINCH_API_KEY_SECRET="projects/291176869049/secrets/YOUR_1INCH_API_KEY/versions/latest"
export ETHEREUM_RPC_URL_SECRET="projects/291176869049/secrets/ETHEREUM_RPC_URL_SECRET/versions/latest"
export HOST_WALLET_ADDRESS="0xcf1D64999FBf19CAde605d219B219F63a7E74E89"
```

## 🔍 **Validation Steps**

1. **Update your .profile**:
   ```bash
   nano ~/.profile
   ```

2. **Apply changes**:
   ```bash
   source ~/.profile
   ```

3. **Run validation script**:
   ```bash
   cd ~/TelegramFunnel/30/TelePay30
   python env_validator.py
   ```

## 🚨 **Key Changes from Your Current Setup**

1. **Fixed HOST_WALLET_PRIVATE_KEY secret name**:
   - ❌ `HOST_WALLET_PRIVATE_KEY_SECRET` 
   - ✅ `HOST_WALLET_PRIVATE_KEY`

2. **Removed duplicate entries**:
   - You had two `HOST_WALLET_PRIVATE_KEY` entries
   - Removed `HOST_WALLET_PRIVATE_KEY_SECRET` variable

3. **Ensured consistent naming**:
   - All variables now match what the code expects

## 📋 **Required Secrets in Google Secret Manager**

Make sure these secrets exist in your Google Cloud project:

### **Core Secrets**
- `TELEGRAM_BOT_SECRET_NAME`
- `TELEGRAM_BOT_USERNAME`
- `DATABASE_HOST_SECRET`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`
- `SUCCESS_URL_SIGNING_KEY`
- `NOWPAYMENT_WEBHOOK_KEY`
- `NOWPAYMENTS_API_KEY`

### **ChangeNOW Integration Secrets**
- `CHANGENOW_API_KEY`
- `HOST_WALLET_ETH_ADDRESS`
- `HOST_WALLET_PRIVATE_KEY` ⚠️ **This is the one that was failing**

## 🔧 **Create Missing Secrets**

If the `HOST_WALLET_PRIVATE_KEY` secret doesn't exist, create it:

```bash
# Create the secret
gcloud secrets create HOST_WALLET_PRIVATE_KEY

# Add the private key value
echo "YOUR_ACTUAL_PRIVATE_KEY" | gcloud secrets versions add HOST_WALLET_PRIVATE_KEY --data-file=-
```

## ✅ **Expected Results After Fix**

After updating your `.profile` and ensuring all secrets exist:

1. ✅ **No more "Secret not found" errors**
2. ✅ **Token Registry warning will persist** (this is normal - token_registry.py doesn't exist in GCSplit30)
3. ✅ **Application should start successfully**
4. ✅ **All features should work properly**

## 🎯 **Testing Commands**

```bash
# Test environment setup
cd ~/TelegramFunnel/30/TelePay30
python env_validator.py

# Test application startup
python telepay30.py
```

The validation script will tell you exactly which secrets are accessible and which ones need attention.