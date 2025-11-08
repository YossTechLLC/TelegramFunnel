# GCSplit10-21 Deployment Instructions

## 🚀 Overview
This Google Cloud Run service integrates ChangeNow API for automated cryptocurrency payment splitting. After successful subscription payments, it converts USDT to client payout currencies and saves conversion estimates to the database.

## 📋 Prerequisites

### 1. Google Cloud Secret Manager Secrets
Create the following secrets in Google Cloud Secret Manager:

```bash
# ChangeNow API Key
gcloud secrets create CHANGENOW_API_KEY --data-file=<api_key_file>

# Success URL Signing Key (shared with tph10-16.py)
gcloud secrets create SUCCESS_URL_SIGNING_KEY --data-file=<signing_key_file>

# Telegram Bot Token (shared with TelePay10-16)
gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=<telegram_bot_token_file>

# TelePay Flat Fee Percentage
gcloud secrets create TP_FLAT_FEE --data-file=<tp_flat_fee_file>

# TPS Webhook URL
gcloud secrets create TPS_WEBHOOK_URL --data-file=<tps_webhook_url_file>

# Database Credentials (shared with TelePay10-16)
gcloud secrets create DATABASE_HOST --data-file=<database_host_file>
gcloud secrets create DATABASE_NAME --data-file=<database_name_file>
gcloud secrets create DATABASE_USER --data-file=<database_user_file>
gcloud secrets create DATABASE_PASSWORD --data-file=<database_password_file>
```

### 2. Environment Variables
Set these environment variables for the Cloud Run service:

```bash
# ChangeNow API Configuration
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest

# Webhook Security (shared with tph10-16)
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest

# TPS Webhook URL
TPS_WEBHOOK_URL=projects/291176869049/secrets/TPS_WEBHOOK_URL/versions/latest

# Telegram Bot Configuration (shared with TelePay10-16)
TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_TOKEN/versions/latest

# Payment Fee Configuration
TP_FLAT_FEE=projects/291176869049/secrets/TP_FLAT_FEE/versions/latest

# Database Configuration (shared with TelePay10-16)
DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD/versions/latest

# Cloud SQL Connection (required for Cloud SQL Connector)
CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest
```

**Note**: The service uses Google Cloud SQL Connector (`cloud-sql-python-connector`) which is the same method used by tph10-16.py. This connector:
- Creates connections on-demand (no connection pooling)
- Automatically manages SSL/TLS encryption
- Works with Cloud Run's `--add-cloudsql-instances` flag
- Uses `pg8000` driver instead of `psycopg2`

### 3. Update tph10-16.py Environment
Add the TPS webhook URL environment variable to tph10-16.py after deployment.

## 🔧 Deployment Steps

### Deploy to Google Cloud Run

```bash
# Navigate to GCSplit10-21 directory
cd GCSplit10-21

# Deploy using gcloud with Cloud SQL connection
gcloud run deploy tps10-21 \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --port 8080 \
    --service-account=291176869049-compute@developer.gserviceaccount.com \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql \
    --set-env-vars CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    --set-env-vars SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest \
    --set-env-vars TPS_WEBHOOK_URL=projects/291176869049/secrets/TPS_WEBHOOK_URL/versions/latest \
    --set-env-vars TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_TOKEN/versions/latest \
    --set-env-vars TP_FLAT_FEE=projects/291176869049/secrets/TP_FLAT_FEE/versions/latest \
    --set-env-vars DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME/versions/latest \
    --set-env-vars DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER/versions/latest \
    --set-env-vars DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD/versions/latest \
    --set-env-vars CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest
```

### Important Deployment Notes

1. **Service Account**: The service account must have these IAM roles:
   - `roles/cloudsql.client` - To connect to Cloud SQL
   - `roles/secretmanager.secretAccessor` - To access Secret Manager secrets

2. **Cloud SQL Instance**: Must be running before deployment:
   ```bash
   # Verify Cloud SQL instance is running
   gcloud sql instances describe telepaypsql --project=telepay-459221
   ```

3. **Secret Manager Permissions**: Grant the service account access to secrets:
   ```bash
   # Grant Secret Manager access to the service account
   gcloud projects add-iam-policy-binding telepay-459221 \
       --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor"
   ```

### Local Development with Docker

```bash
# Build the Docker image
docker build -t tps10-21 .

# Run locally for testing (uses Cloud SQL Connector)
docker run -p 8080:8080 \
    -e CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest \
    -e SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest \
    -e DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME/versions/latest \
    -e DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER/versions/latest \
    -e DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD/versions/latest \
    -e CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest \
    tps10-21
```

**Note**: Local testing requires proper GCP credentials and service account permissions to access Secret Manager and Cloud SQL.

## 🔗 Integration Flow

1. **Payment Success** → `tph10-16.py` processes payment and creates user subscription
2. **Invite Sent** → `tph10-16.py` sends Telegram invite to user
3. **Webhook Trigger** → `tph10-16.py` calls `tps10-21.py` webhook with payment data
4. **ChangeNow Integration** → `tps10-21.py` processes payment splitting:
   - **Looks up network from database** → Queries `to_currency_to_network` table
   - Validates ETH → client_currency pair
   - Checks amount limits
   - Creates fixed-rate transaction
   - Returns deposit address for funding

## 📊 Database Requirements

### **Required Tables**

#### **1. split_payout_request** (Created automatically by service)
Stores conversion estimates and payout requests.

#### **2. to_currency_to_network** (Must be created manually)
Maps currencies to their blockchain networks.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS to_currency_to_network (
    to_currency VARCHAR(10) PRIMARY KEY,
    to_network VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Example Data:**
```sql
INSERT INTO to_currency_to_network (to_currency, to_network) VALUES
    ('LINK', 'eth'),
    ('ETH', 'eth'),
    ('USDT', 'eth'),
    ('USDC', 'eth'),
    ('BTC', 'btc'),
    ('BNB', 'bsc'),
    ('MATIC', 'polygon');
```

**Important Notes:**
- `to_currency` must be **UPPERCASE** (e.g., 'LINK', not 'link')
- `to_network` should be **lowercase** (e.g., 'eth', not 'ETH')
- Add entries for ALL currencies you plan to support
- If a currency is not in this table, payment splitting will fail

## 📊 Expected Logs

### Startup Logs (Database Connection):
```
⚙️ [CONFIG] Initializing TPS10-21 configuration
🔐 [CONFIG] Fetching ChangeNow API key
✅ [CONFIG] Successfully fetched ChangeNow API key
🔐 [CONFIG] Fetching success URL signing key
✅ [CONFIG] Successfully fetched success URL signing key
🔐 [CONFIG] Fetching Telegram bot token
✅ [CONFIG] Successfully fetched Telegram bot token
🔐 [CONFIG] Fetching TelePay flat fee percentage
✅ [CONFIG] Successfully fetched TelePay flat fee percentage
📊 [CONFIG] Configuration status:
   ChangeNow API Key: ✅
   Success URL Signing Key: ✅
   TPS Webhook URL: ✅
   Telegram Bot Token: ✅
   TP Flat Fee: ✅
🔄 [DATABASE] Initializing database connection
🔐 [DB_CONFIG] Fetching database host
✅ [DB_CONFIG] Successfully fetched database host
🔐 [DB_CONFIG] Fetching database name
✅ [DB_CONFIG] Successfully fetched database name
🔐 [DB_CONFIG] Fetching database user
✅ [DB_CONFIG] Successfully fetched database user
🔐 [DB_CONFIG] Fetching database password
✅ [DB_CONFIG] Successfully fetched database password
🔐 [DB_CONFIG] Fetching Cloud SQL connection name
✅ [DB_CONFIG] Successfully fetched Cloud SQL connection name
✅ [DATABASE] Database credentials initialized
📊 [DATABASE] Database: [your-database-name]
📊 [DATABASE] User: [your-database-user]
☁️ [DATABASE] Connection: telepay-459221:us-central1:telepaypsql
```

**Database Connection Pattern:**
The service now uses **Google Cloud SQL Connector** (same as tph10-16.py):
- Creates fresh connections for each database operation
- No connection pooling (connections are created and closed per request)
- Uses `pg8000` driver with Cloud SQL Connector
- Automatically handles SSL/TLS encryption

### tph10-16.py Logs:
```
🚀 [PAYMENT_SPLITTING] Starting Client Payout
🔄 [PAYMENT_SPLITTING] Triggering TPS10-21 webhook
📦 [PAYMENT_SPLITTING] Payload: user_id=123, amount=$3.30 → LINK
✅ [PAYMENT_SPLITTING] Payment splitting webhook completed successfully
```

### tps10-21.py Logs (Webhook Processing):
```
🎯 [WEBHOOK] TPS10-21 Webhook Called
📦 [WEBHOOK] Payload size: 196 bytes
📝 [WEBHOOK] Processing payment split request
🔄 [PAYMENT_SPLITTING] Starting Client Payout
👤 [PAYMENT_SPLITTING] User ID: 6271402111
🏢 [PAYMENT_SPLITTING] Channel ID: -1002409379260
💰 [PAYMENT_SPLITTING] Subscription Price: $3.3
🏦 [PAYMENT_SPLITTING] Target: 0xBc29Be20D4F90cF94f994cfADCf24742118C0Fe5 (LINK)
📊 [PAYMENT_SPLITTING] Step 1: Getting estimate and saving to database
🔄 [ESTIMATE_AND_SAVE] Starting conversion estimate workflow
💰 [FEE_CALCULATION] Original amount: $3.3
📊 [FEE_CALCULATION] TP flat fee: 3%
💸 [FEE_CALCULATION] Fee amount: $0.099
✅ [FEE_CALCULATION] Adjusted amount: $3.201
🔍 [NETWORK_LOOKUP] Looking up network for currency: LINK
🔗 [DATABASE] ✅ Cloud SQL Connector connection successful!
✅ [NETWORK_LOOKUP] Found network 'eth' for currency 'LINK'
🌐 [ESTIMATE_AND_SAVE] Using network 'eth' for currency 'LINK'
🌐 [ESTIMATE_AND_SAVE] Calling ChangeNow API for estimate
📈 [CHANGENOW_ESTIMATE_V2] Getting estimate for 3.201 USDT → LINK
✅ [CHANGENOW_ESTIMATE_V2] Estimate successful
💾 [ESTIMATE_AND_SAVE] Inserting into database
📝 [DB_INSERT] Preparing split payout request insertion
🔑 [UNIQUE_ID] Generated: 2WUA2ZPBXOIUO1T4
✅ [DB_INSERT] Successfully inserted split payout request
🆔 [DB_INSERT] Unique ID: 2WUA2ZPBXOIUO1T4
✅ [ESTIMATE_AND_SAVE] Successfully completed workflow
✅ [PAYMENT_SPLITTING] Estimate saved with unique_id: 2WUA2ZPBXOIUO1T4
```

## 🧪 Testing

### 1. Health Check
```bash
# Test the health endpoint
curl https://tps10-21-[YOUR-HASH]-uc.a.run.app/health

# Expected response:
# {"status":"healthy","service":"TPS10-21 Payment Splitting","timestamp":1234567890}
```

### 2. View Logs
```bash
# View real-time logs to verify database connection
gcloud run services logs read tps10-21 \
    --region us-central1 \
    --limit 50 \
    --project telepay-459221

# Look for these success indicators:
# ✅ [DATABASE] Database connection pool initialized
# ☁️ [DATABASE] Using Cloud SQL Unix socket connection
```

### 3. Manual Webhook Test
```bash
# Test the webhook endpoint (requires valid signature)
curl -X POST https://tps10-21-[YOUR-HASH]-uc.a.run.app \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: [VALID_HMAC_SIGNATURE]" \
  -d '{
    "user_id": 123456789,
    "closed_channel_id": "-1002409379260",
    "wallet_address": "0x1234567890abcdef",
    "payout_currency": "link",
    "subscription_price": "3.30"
  }'
```

### 4. Database Connection Verification
```bash
# Connect to Cloud SQL to verify the split_payout_request table
gcloud sql connect telepaypsql --user=postgres --project=telepay-459221

# Run this query to check recent entries:
# SELECT * FROM split_payout_request ORDER BY created_at DESC LIMIT 5;
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

## ⚠️ Troubleshooting

### Database Connection Issues

**Error**: `Cloud SQL Connector not available` or `Failed to create database connection`

**Solutions**:
1. Verify all database environment variables are set:
   ```bash
   gcloud run services describe tps10-21 --region us-central1 --format="value(spec.template.spec.containers[0].env)"
   ```

2. Check Secret Manager permissions:
   ```bash
   gcloud secrets get-iam-policy DATABASE_HOST --project=telepay-459221
   gcloud secrets get-iam-policy DATABASE_NAME --project=telepay-459221
   gcloud secrets get-iam-policy DATABASE_USER --project=telepay-459221
   gcloud secrets get-iam-policy DATABASE_PASSWORD --project=telepay-459221
   ```

3. Verify Cloud SQL Connector dependencies are installed:
   ```bash
   # Check if cloud-sql-python-connector and pg8000 are in requirements.txt
   cat requirements.txt | grep -E "cloud-sql-python-connector|pg8000"

   # Should show:
   # cloud-sql-python-connector==1.4.3
   # pg8000==1.30.3
   ```

4. Verify Cloud SQL connection is attached:
   ```bash
   gcloud run services describe tps10-21 \
       --region us-central1 \
       --format="value(spec.template.metadata.annotations['run.googleapis.com/cloudsql-instances'])"

   # Should return: telepay-459221:us-central1:telepaypsql
   ```

5. Check Cloud SQL instance is running:
   ```bash
   gcloud sql instances describe telepaypsql --project=telepay-459221
   # Status should be: RUNNABLE
   ```

6. Grant Cloud SQL Client role to service account:
   ```bash
   gcloud projects add-iam-policy-binding telepay-459221 \
       --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
       --role="roles/cloudsql.client"
   ```

### Secret Manager Access Issues

**Error**: `Error fetching [secret_name]: Permission denied`

**Solution**:
```bash
# Grant Secret Manager access to service account
gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Verify the role was granted
gcloud projects get-iam-policy telepay-459221 \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:291176869049-compute@developer.gserviceaccount.com"
```

### Network Lookup Issues

**Error**: `Failed to lookup network for currency [CURRENCY]`

**Cause**: The `to_currency_to_network` table doesn't have an entry for the requested currency.

**Solutions**:
1. Connect to the database and check if the currency exists:
   ```sql
   SELECT * FROM to_currency_to_network WHERE to_currency = 'LINK';
   ```

2. Add the missing currency to the table:
   ```sql
   INSERT INTO to_currency_to_network (to_currency, to_network)
   VALUES ('LINK', 'eth');
   ```

3. Verify the currency is in UPPERCASE:
   ```sql
   -- Wrong (will not be found):
   INSERT INTO to_currency_to_network (to_currency, to_network)
   VALUES ('link', 'eth');  -- ❌ lowercase

   -- Correct:
   INSERT INTO to_currency_to_network (to_currency, to_network)
   VALUES ('LINK', 'eth');  -- ✅ UPPERCASE
   ```

4. View all supported currencies:
   ```sql
   SELECT * FROM to_currency_to_network ORDER BY to_currency;
   ```

### ChangeNow API Issues

**Error**: `Failed to get estimate from ChangeNow API`

**Solutions**:
1. Verify ChangeNow API key is valid
2. Check supported currency pairs: https://changenow.io/currencies
3. Verify amount is within min/max limits for the pair
4. Check ChangeNow API status: https://status.changenow.io
5. Ensure the network from database matches ChangeNow's expected network

## 📝 Important Notes

1. **Cloud SQL Connector**: The service uses **Google Cloud SQL Connector** (`cloud-sql-python-connector`) which:
   - Mirrors the exact pattern used in tph10-16.py
   - Creates fresh connections for each database operation (no connection pooling)
   - Uses `pg8000` driver instead of `psycopg2`
   - Automatically handles SSL/TLS encryption
   - Requires `CLOUD_SQL_CONNECTION_NAME` from Secret Manager

2. **No Connection Pooling**: Unlike the previous version, this refactored version does NOT use `psycopg2.pool.SimpleConnectionPool`. Connections are created and closed for each database operation, matching tph10-16.py's pattern.

3. **Database Credentials**: All database environment variables must be set and point to valid Secret Manager secrets:
   - `DATABASE_NAME_SECRET` - Database name
   - `DATABASE_USER_SECRET` - Database user
   - `DATABASE_PASSWORD_SECRET` - Database password
   - `CLOUD_SQL_CONNECTION_NAME` - Connection string (e.g., `telepay-459221:us-central1:telepaypsql`)

4. **Service Account Permissions**: The deployment service account needs:
   - `roles/cloudsql.client` - To connect to Cloud SQL
   - `roles/secretmanager.secretAccessor` - To read secrets
   - `roles/run.invoker` - To allow invocations (if authenticated)

5. **ChangeNow API Key**: Obtain from ChangeNow partner portal

6. **Rate Limits**: ChangeNow API has rate limits - implement backoff if needed

7. **Currency Support**: Verify supported pairs before deployment at https://changenow.io/currencies

8. **Amount Limits**: Each pair has min/max limits that must be respected

9. **Error Handling**: Failed database operations are logged with detailed troubleshooting information

10. **Dynamic Network Lookup**: The service dynamically looks up the blockchain network for each currency from the `to_currency_to_network` database table. This allows supporting multiple networks (eth, bsc, polygon, etc.) without code changes.

11. **Removed Dependencies**: The following have been REMOVED from this service:
    - `psycopg2-binary` - Replaced with `pg8000`
    - `psycopg2.pool.SimpleConnectionPool` - No connection pooling
    - Unix socket path logic - Handled by Cloud SQL Connector
    - `DATABASE_HOST_SECRET` - No longer needed (Cloud SQL Connector manages connection)
    - Hardcoded `to_network="eth"` - Now dynamic from database