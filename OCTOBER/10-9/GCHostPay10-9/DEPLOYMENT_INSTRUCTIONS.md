# GCHostPay10-9 Deployment Instructions

## 🚀 Overview
This Google Cloud Function automates ETH payment dispatching from the custodial HOST wallet to ChangeNow deposit addresses. It monitors incoming payments via NowPayments webhooks and automatically sends ETH to complete the payment split flow.

## 📋 Prerequisites

### 1. Google Cloud Secret Manager Secrets

#### Existing Secrets:
```bash
# Host Wallet (Custodial Wallet)
HOST_WALLET_ETH_ADDRESS: projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest
HOST_WALLET_PRIVATE_KEY: projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest
```

#### New Secrets to Create:
```bash
# NowPayments Webhook Key (from NowPayments dashboard)
# Note: This secret already exists as NOWPAYMENT_WEBHOOK_KEY
# If not created yet, use:
gcloud secrets create NOWPAYMENT_WEBHOOK_KEY --data-file=<webhook_key_file>

# Ethereum Node RPC URL (Alchemy/Infura)
# Note: This secret already exists as ETHEREUM_RPC_URL
# If not created yet, use:
gcloud secrets create ETHEREUM_RPC_URL --data-file=<ethereum_rpc_url_file>

# Alchemy API Key (for future use)
# Note: This secret already exists as ETHEREUM_RPC_URL_API
# If not created yet, use:
gcloud secrets create ETHEREUM_RPC_URL_API --data-file=<alchemy_api_key_file>
```

**Example ETHEREUM_RPC_URL values:**
```
Alchemy: https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
Infura: https://mainnet.infura.io/v3/YOUR_PROJECT_ID
```

### 2. Database Setup

The `host_payment_queue` table must be created manually in pgAdmin before deploying. Run this SQL script:

```sql
CREATE TABLE host_payment_queue (
    id SERIAL PRIMARY KEY,
    payment_id VARCHAR(255) UNIQUE NOT NULL,
    order_id VARCHAR(255) NOT NULL,
    changenow_tx_id VARCHAR(255),
    payin_address VARCHAR(255) NOT NULL,
    expected_amount_eth NUMERIC(18, 8) NOT NULL,
    actual_amount_received NUMERIC(18, 8),
    status VARCHAR(50) DEFAULT 'pending',
    tx_hash VARCHAR(255),
    gas_price_gwei NUMERIC(18, 8),
    gas_used INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    user_id BIGINT
);
```

Ensure your database credentials are configured:

```bash
DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest
```

### 3. Environment Variables

Set these environment variables for the Cloud Function:

```bash
# Secret Manager Paths
HOST_WALLET_ETH_ADDRESS=projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest
HOST_WALLET_PRIVATE_KEY=projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest
NOWPAYMENT_WEBHOOK_KEY=projects/291176869049/secrets/NOWPAYMENT_WEBHOOK_KEY/versions/latest
ETHEREUM_RPC_URL=projects/291176869049/secrets/ETHEREUM_RPC_URL/versions/latest
ETHEREUM_RPC_URL_API=projects/291176869049/secrets/ETHEREUM_RPC_URL_API/versions/latest

# Database Credentials
DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest

# Configuration
ETH_NETWORK=mainnet                    # or 'goerli' for testnet
PAYMENT_TIMEOUT_MINUTES=120            # Payment expiration timeout
MAX_RETRY_ATTEMPTS=5                   # Maximum retry attempts
POLLING_INTERVAL_SECONDS=30            # Wallet balance polling interval
```

## 🔧 Deployment Steps

### 1. Deploy to Cloud Run

```bash
# Navigate to GCHostPay10-9 directory
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-9/GCHostPay10-9

# Deploy using gcloud run deploy
gcloud run deploy hpw10-9 \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --service-account=291176869049-compute@developer.gserviceaccount.com \
    --set-env-vars HOST_WALLET_ETH_ADDRESS=projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest \
    --set-env-vars HOST_WALLET_PRIVATE_KEY=projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest \
    --set-env-vars NOWPAYMENT_WEBHOOK_KEY=projects/291176869049/secrets/NOWPAYMENT_WEBHOOK_KEY/versions/latest \
    --set-env-vars ETHEREUM_RPC_URL=projects/291176869049/secrets/ETHEREUM_RPC_URL/versions/latest \
    --set-env-vars ETHEREUM_RPC_URL_API=projects/291176869049/secrets/ETHEREUM_RPC_URL_API/versions/latest \
    --set-env-vars DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest \
    --set-env-vars DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest \
    --set-env-vars DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest \
    --set-env-vars DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest \
    --set-env-vars ETH_NETWORK=mainnet \
    --set-env-vars PAYMENT_TIMEOUT_MINUTES=120 \
    --set-env-vars MAX_RETRY_ATTEMPTS=5 \
    --set-env-vars POLLING_INTERVAL_SECONDS=30

# Note: Cloud Run will automatically detect the Flask app and set the PORT environment variable
# The service will be available at: https://hpw10-9-291176869049.us-central1.run.app
```

### 2. Alternative: Docker Deployment

```bash
# Build the Docker image
docker build -t hpw10-9 .

# Run locally for testing
docker run -p 8080:8080 \
    -e HOST_WALLET_ETH_ADDRESS=projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest \
    -e HOST_WALLET_PRIVATE_KEY=projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest \
    -e NOWPAYMENT_WEBHOOK_KEY=projects/291176869049/secrets/NOWPAYMENT_WEBHOOK_KEY/versions/latest \
    -e ETHEREUM_RPC_URL=projects/291176869049/secrets/ETHEREUM_RPC_URL/versions/latest \
    -e ETHEREUM_RPC_URL_API=projects/291176869049/secrets/ETHEREUM_RPC_URL_API/versions/latest \
    -e DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest \
    -e DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest \
    -e DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest \
    -e DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest \
    -e ETH_NETWORK=mainnet \
    hpw10-9
```

## 🔗 Integration Flow

### Complete Payment Pipeline:

1. **User Payment** → NowPayments invoice created via GCWebhook10-13
2. **Payment Confirmation** → NowPayments converts payment to ETH in HOST wallet
3. **IPN Webhook** → NowPayments sends IPN to HPW10-9 `/nowpayments` endpoint
4. **ChangeNow Setup** → GCSplit7-14 creates ChangeNow transaction and notifies HPW10-9
5. **Payment Queue** → HPW10-9 queues payment for processing
6. **Balance Monitoring** → Payment dispatcher polls HOST wallet balance
7. **ETH Transfer** → Once funds available, HPW10-9 sends ETH to ChangeNow `payinAddress`
8. **Conversion** → ChangeNow converts ETH → client's payout currency
9. **Final Delivery** → Client receives funds in their wallet

### Webhook Endpoints:

#### 1. NowPayments IPN Webhook:
```
POST https://hpw10-9-291176869049.us-central1.run.app/nowpayments
```

#### 2. GCSplit7-14 Notification Webhook:
```
POST https://hpw10-9-291176869049.us-central1.run.app/gcsplit
```

#### 3. Health Check:
```
GET https://hpw10-9-291176869049.us-central1.run.app/health
```

#### 4. Payment Status:
```
GET https://hpw10-9-291176869049.us-central1.run.app/status/<payment_id>
```

## 📊 Expected Logs

### Initialization:
```
⚙️ [CONFIG] Initializing HPW10-9 configuration
✅ [CONFIG] Successfully fetched host custodial wallet address
🔒 [CONFIG] Private key loaded (length: 66 chars)
✅ [ETH_WALLET] Connected to Ethereum node
🏦 [ETH_WALLET] Wallet address: 0x1234...
🔐 [ETH_WALLET] Private key validated successfully
🌐 [HPW10-9] Running on Mainnet
✅ [HPW10-9] Background dispatcher thread started
```

### GCSplit Webhook:
```
🎯 [WEBHOOK] GCSplit7-14 Notification Webhook Called
📊 [CHANGENOW_TRACKER] Parsed ChangeNow transaction data:
   TX ID: abc123...
   Payin address: 0x5678...
   Amount: 0.05 ETH
📥 [PAYMENT_DISPATCHER] Queueing payment for processing
✅ [PAYMENT_DISPATCHER] Payment queued successfully
```

### Payment Processing:
```
💳 [PAYMENT_DISPATCHER] Processing payment: CHANGENOW_abc123
💰 [PAYMENT_DISPATCHER] Current wallet balance: 0.15 ETH
⛽ [ETH_WALLET] Gas estimate:
   Base fee: 25.5 Gwei
   Priority fee: 2.0 Gwei
   Max fee: 32.6 Gwei
✅ [PAYMENT_DISPATCHER] Sufficient balance available
🚀 [PAYMENT_DISPATCHER] Initiating ETH transfer
🔐 [ETH_WALLET] Transaction signed successfully
🚀 [ETH_WALLET] Transaction broadcasted!
📋 [ETH_WALLET] TX Hash: 0x9abc...
✅ [PAYMENT_DISPATCHER] Transaction sent successfully!
```

### Transaction Confirmation:
```
🔍 [PAYMENT_DISPATCHER] Checking confirmation for TX: 0x9abc...
✅ [PAYMENT_DISPATCHER] Transaction confirmed: 0x9abc...
   Gas used: 21000
   Gas price: 28.3 Gwei
🎉 [PAYMENT_DISPATCHER] Payment CHANGENOW_abc123 completed successfully!
```

## 🧪 Testing

### 1. Health Check
```bash
curl https://hpw10-9-291176869049.us-central1.run.app/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "HPW10-9 Host Payment Wallet",
  "database": "✅",
  "ethereum_node": "✅",
  "network": "Mainnet",
  "wallet_balance": "0.15 ETH",
  "queue_stats": {
    "pending": 2,
    "sent": 1
  }
}
```

### 2. Test GCSplit Webhook
```bash
curl -X POST https://hpw10-9-291176869049.us-central1.run.app/gcsplit \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "test_tx_123",
    "payin_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
    "expected_amount": "0.05",
    "order_id": "PGP-123456789-100",
    "user_id": 123456789,
    "payout_address": "0x1234567890abcdef",
    "payout_currency": "usdt"
  }'
```

### 3. Check Payment Status
```bash
curl https://hpw10-9-291176869049.us-central1.run.app/status/CHANGENOW_test_tx_123
```

## 🔐 Security Notes

### Critical Security Measures:

1. **Private Key Protection:**
   - NEVER log or expose the private key
   - Store only in Secret Manager
   - Access only in-memory during transaction signing
   - Implement key rotation procedures

2. **Webhook Validation:**
   - Always verify IPN signatures (HMAC-SHA512 for NowPayments)
   - Always verify webhook signatures (HMAC-SHA256 for GCSplit)
   - Reject invalid signatures immediately

3. **Transaction Safety:**
   - Validate all Ethereum addresses (checksum validation)
   - Estimate gas before sending transactions
   - Implement maximum transaction limits if needed
   - Monitor for nonce conflicts

4. **Database Security:**
   - All credentials in Secret Manager
   - Parameterized queries to prevent SQL injection
   - Regular backups of `host_payment_queue` table

5. **Error Handling:**
   - Never expose sensitive data in error messages
   - Log errors securely (no private keys/secrets)
   - Alert admin on critical failures

## 📈 Monitoring & Alerts

### Key Metrics to Monitor:

1. **Wallet Balance:** Ensure sufficient ETH for payments + gas
2. **Queue Length:** Monitor `pending` and `waiting_funds` payments
3. **Transaction Success Rate:** Should be >95%
4. **Gas Costs:** Track gas spending vs transaction value
5. **Error Rates:** Alert on repeated failures

### Database Queries for Monitoring:

```sql
-- Check pending payments
SELECT * FROM host_payment_queue WHERE status IN ('pending', 'waiting_funds') ORDER BY created_at;

-- Check failed payments
SELECT * FROM host_payment_queue WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 10;

-- Calculate success rate
SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM host_payment_queue
GROUP BY status;

-- Check average gas costs
SELECT
    AVG(gas_price_gwei * gas_used / 1000000000) as avg_gas_cost_eth,
    MAX(gas_price_gwei * gas_used / 1000000000) as max_gas_cost_eth
FROM host_payment_queue
WHERE status = 'completed';
```

## ⚠️ Important Notes

### 1. Ethereum Network:
- **Mainnet:** Use for production with real ETH
- **Goerli/Sepolia:** Use for testing with test ETH
- Set `ETH_NETWORK` environment variable accordingly

### 2. Gas Management:
- Always maintain buffer in wallet for gas fees
- Monitor gas prices during high network congestion
- EIP-1559 is used for dynamic gas pricing

### 3. Nonce Management:
- System tracks nonce automatically
- Handles concurrent transactions properly
- Recovery mechanisms for stuck transactions

### 4. Payment Timeouts:
- Default: 120 minutes (configurable)
- Payments expire if funds don't arrive in time
- Expired payments marked for manual review

### 5. Retry Logic:
- Maximum 5 retries (configurable)
- Exponential backoff between retries
- Failed payments logged for manual intervention

## 🆘 Troubleshooting

### Issue: Insufficient Gas
**Solution:** Fund HOST wallet with more ETH

### Issue: Transaction Stuck
**Solution:** Check Etherscan, may need to speed up with higher gas

### Issue: Payment Not Processing
**Solution:** Check logs, verify webhook signatures, check database connection

### Issue: Database Connection Failed
**Solution:** Verify database credentials in Secret Manager

### Issue: Ethereum Node Connection Failed
**Solution:** Verify ETHEREUM_RPC_URL is correct and node is accessible

## 📞 Support

For issues or questions:
1. Check Cloud Function logs in Google Cloud Console
2. Query `host_payment_queue` table for payment status
3. Monitor Ethereum transactions on Etherscan
4. Review error messages in database `error_message` column
