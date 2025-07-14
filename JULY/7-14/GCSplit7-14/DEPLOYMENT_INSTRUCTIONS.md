# GCSplit7-14 Deployment Instructions

## 🚀 Overview
This Google Cloud Function integrates ChangeNow API for automated cryptocurrency payment splitting. After successful subscription payments, it converts ETH to client payout currencies.

## 📋 Prerequisites

### 1. Google Cloud Secret Manager Secrets
Create the following secrets in Google Cloud Secret Manager:

```bash
# ChangeNow API Key
gcloud secrets create CHANGENOW_API_KEY --data-file=<api_key_file>

# Webhook Signing Key (shared with tph7-14.py)
gcloud secrets create WEBHOOK_SIGNING_KEY --data-file=<signing_key_file>
```

### 2. Environment Variables
Set these environment variables for the Cloud Function:

```bash
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest
WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest
TPS_WEBHOOK_URL=https://[REGION]-291176869049.cloudfunctions.net/tps7-14
```

### 3. Update tph7-14.py Environment
Add this environment variable to tph7-14.py:

```bash
TPS_WEBHOOK_URL=https://[REGION]-291176869049.cloudfunctions.net/tps7-14
```

## 🔧 Deployment Steps

### 1. Deploy the Cloud Function
```bash
# Navigate to GCSplit7-14 directory
cd GCSplit7-14

# Deploy using gcloud
gcloud functions deploy tps7-14 \
    --runtime python311 \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    --set-env-vars WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest \
    --set-env-vars TPS_WEBHOOK_URL=https://[REGION]-291176869049.cloudfunctions.net/tps7-14 \
    --source .
```

### 2. Alternative: Docker Deployment
```bash
# Build the Docker image
docker build -t tps7-14 .

# Run locally for testing
docker run -p 8080:8080 \
    -e CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    -e WEBHOOK_SIGNING_KEY=projects/291176869049/secrets/WEBHOOK_SIGNING_KEY/versions/latest \
    tps7-14
```

## 🔗 Integration Flow

1. **Payment Success** → `tph7-14.py` processes payment and creates user subscription
2. **Invite Sent** → `tph7-14.py` sends Telegram invite to user
3. **Webhook Trigger** → `tph7-14.py` calls `tps7-14.py` webhook with payment data
4. **ChangeNow Integration** → `tps7-14.py` processes payment splitting:
   - Validates ETH → client_currency pair
   - Checks amount limits
   - Creates fixed-rate transaction
   - Returns deposit address for funding

## 📊 Expected Logs

### tph7-14.py Logs:
```
🚀 [PAYMENT_SPLITTING] Starting Client Payout
🔄 [PAYMENT_SPLITTING] Triggering TPS7-14 webhook
📦 [PAYMENT_SPLITTING] Payload: user_id=123, amount=0.05 ETH → USDT
✅ [PAYMENT_SPLITTING] Payment splitting webhook completed successfully
```

### tps7-14.py Logs:
```
🎯 [WEBHOOK] TPS7-14 Webhook Called
🔍 [CHANGENOW_PAIR_CHECK] Validating ETH → USDT
💰 [CHANGENOW_LIMITS] Checking limits for 0.05 ETH → USDT
🚀 [CHANGENOW_SWAP] Starting fixed-rate transaction
✅ [CHANGENOW_SWAP] Transaction created successfully
🏦 [CUSTOMER_FUNDING_INFO] Send exactly 0.05 ETH to: 0x1234...
```

## 🧪 Testing

### Health Check
```bash
curl https://[REGION]-291176869049.cloudfunctions.net/tps7-14/health
```

### Manual Webhook Test
```bash
curl -X POST https://[REGION]-291176869049.cloudfunctions.net/tps7-14 \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: [SIGNATURE]" \
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