# GCSplit7-14 Deployment Instructions

## 🚀 Overview
This Google Cloud Function integrates ChangeNow API for automated cryptocurrency payment splitting. After successful subscription payments, it converts ETH to client payout currencies.

## 📋 Prerequisites

### 1. Google Cloud Secret Manager Secrets
Create the following secrets in Google Cloud Secret Manager:

```bash
# ChangeNow API Key
gcloud secrets create CHANGENOW_API_KEY --data-file=<api_key_file>

# Webhook Signing Key (shared with tph10-13.py)
gcloud secrets create WEBHOOK_SIGNING_KEY --data-file=<signing_key_file>
```

### 2. Environment Variables
Set these environment variables for the Cloud Function:

```bash
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest
WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest
TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest
TPS_WEBHOOK_URL=https://[REGION]-291176869049.cloudfunctions.net/tps10-9
HPW_WEBHOOK_URL=https://[REGION]-291176869049.cloudfunctions.net/hpw10-9/gcsplit
```

### 3. Update tph10-13.py Environment
Add this environment variable to tph10-13.py:

```bash
TPS_WEBHOOK_URL=https://[REGION]-291176869049.cloudfunctions.net/tps10-9
```

## 🔧 Deployment Steps

### 1. Deploy to Cloud Run
```bash
# Navigate to GCSplit7-14 directory
cd GCSplit7-14

# Deploy using gcloud run deploy
gcloud run deploy tps10-9 \
    --source . \
    --region us-central1 \
    --port 8080 \
    --allow-unauthenticated \
    --service-account=291176869049-compute@developer.gserviceaccount.com \
    --set-env-vars CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    --set-env-vars WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest \
    --set-env-vars TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest \
    --set-env-vars TPS_WEBHOOK_URL=https://tps7-14-291176869049.us-central1.run.app \
    --set-env-vars HPW_WEBHOOK_URL=https://hpw10-9-291176869049.us-central1.run.app/gcsplit

# Note: Cloud Run will automatically detect the Flask app and set the PORT environment variable
# The service will be available at: https://tps10-9-291176869049.us-central1.run.app
```

### 2. Alternative: Docker Deployment
```bash
# Build the Docker image
docker build -t tps10-9 .

# Run locally for testing
docker run -p 8080:8080 \
    -e CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    -e WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest \
    tps10-9
```

## 🔗 Integration Flow

1. **Payment Success** → `tph10-13.py` processes payment and creates user subscription
2. **Invite Sent** → `tph10-13.py` sends Telegram invite to user
3. **Webhook Trigger** → `tph10-13.py` calls `tps10-9.py` webhook with payment data
4. **ChangeNow Integration** → `tps10-9.py` processes payment splitting:
   - Validates ETH → client_currency pair
   - Checks amount limits
   - Creates fixed-rate transaction
   - Returns deposit address for funding

## 📊 Expected Logs

### tph10-13.py Logs:
```
🚀 [PAYMENT_SPLITTING] Starting Client Payout
🔄 [PAYMENT_SPLITTING] Triggering TPS10-9 webhook
📦 [PAYMENT_SPLITTING] Payload: user_id=123, amount=0.05 ETH → USDT
✅ [PAYMENT_SPLITTING] Payment splitting webhook completed successfully
```

### tps10-9.py Logs:
```
🎯 [WEBHOOK] TPS10-9 Webhook Called
🔍 [CHANGENOW_PAIR_CHECK] Validating ETH → USDT
💰 [CHANGENOW_LIMITS] Checking limits for 0.05 ETH → USDT
🚀 [CHANGENOW_SWAP] Starting fixed-rate transaction
✅ [CHANGENOW_SWAP] Transaction created successfully
🏦 [CUSTOMER_FUNDING_INFO] Send exactly 0.05 ETH to: 0x1234...
```

## 🧪 Testing

### Health Check
```bash
curl https://tps10-9-291176869049.us-central1.run.app/health
```

### Manual Webhook Test
```bash
curl -X POST https://tps10-9-291176869049.us-central1.run.app \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature:  " \
  -d '{
    "user_id": 123456789,
    "wallet_address": "0x1234567890abcdef",
    "payout_currency": "usdt",
    "sub_price": "0.05"
  }'
```

## 🔐 Security Notes

- All secrets stored in Google Cloud Secret Manager
- Webhook signatures verified using HMAC-SHA256
- Input validation on all external data
- Error handling prevents sensitive data exposure
- Timeout protection on external API calls

## 📝 Monitoring

Monitor the following metrics:
- Webhook success/failure rates
- ChangeNow API response times
- Transaction creation success rates
- Error rates and types

## ⚠️ Important Notes

1. **ChangeNow API Key**: Obtain from ChangeNow partner portal
2. **Rate Limits**: ChangeNow API has rate limits - implement backoff if needed
3. **Currency Support**: Verify supported pairs before deployment
4. **Amount Limits**: Each pair has min/max limits that must be respected
5. **Error Handling**: Failed splits are logged but don't block main payment flow