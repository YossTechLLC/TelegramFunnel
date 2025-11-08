# Cloud Tasks Architecture Design for GCSplit Services
## Implementation Date: 2025-10-26

---

## 🎯 **OBJECTIVE**

Refactor the monolithic GCSplit10-26 service into three independent microservices communicating via Google Cloud Tasks to:
1. **Mitigate ChangeNow API rate limiting** through managed retry logic
2. **Handle ChangeNow API downtime** with infinite retry capability (24hr max duration)
3. **Prevent critical payout failures** by ensuring eventual consistency
4. **Improve system resilience** through asynchronous processing

---

## 📊 **CURRENT ARCHITECTURE (Before)**

```
GCWebhook10-26
    ↓ (HTTP POST with HMAC signature)
GCSplit10-26 (Monolithic)
    ├─ Verify signature
    ├─ Calculate adjusted amount (USD - TP fee)
    ├─ Get USDT→ETH estimate (ChangeNow API v2)
    ├─ Calculate pure market value
    ├─ Save to split_payout_request
    ├─ Create ETH→ClientCurrency swap (ChangeNow API v2)
    ├─ Save to split_payout_que
    └─ Trigger GCHostPay10-26
```

**Problem**: If ChangeNow API fails or rate limits, the entire flow fails and client doesn't get paid.

---

## 🏗️ **NEW ARCHITECTURE (After)**

```
GCWebhook10-26
    ↓ (HTTP POST with HMAC signature)
GCSplit1-10-26 (Orchestrator)
    ├─ Endpoint: POST /
    │   ├─ Verify signature
    │   ├─ Calculate adjusted amount
    │   ├─ Encrypt token
    │   └─ Enqueue → GCSplit2
    │
    ├─ Endpoint: POST /usdt-eth-estimate
    │   ├─ Decrypt token from GCSplit2
    │   ├─ Calculate pure market value
    │   ├─ Save to split_payout_request
    │   ├─ Encrypt token
    │   └─ Enqueue → GCSplit3
    │
    └─ Endpoint: POST /eth-client-swap
        ├─ Decrypt token from GCSplit3
        ├─ Save to split_payout_que
        ├─ Encrypt token
        └─ Enqueue → GCHostPay

GCSplit2-10-26 (USDT→ETH Estimator)
    └─ Endpoint: POST /
        ├─ Decrypt token from GCSplit1
        ├─ Call ChangeNow API (USDT→ETH estimate)
        │   └─ RETRY INFINITELY until success (60s backoff)
        ├─ Encrypt response token
        └─ Enqueue → GCSplit1 /usdt-eth-estimate

GCSplit3-10-26 (ETH→ClientCurrency Swapper)
    └─ Endpoint: POST /
        ├─ Decrypt token from GCSplit1
        ├─ Call ChangeNow API (ETH→Client swap)
        │   └─ RETRY INFINITELY until success (60s backoff)
        ├─ Encrypt response token
        └─ Enqueue → GCSplit1 /eth-client-swap
```

---

## 🔐 **TOKEN ENCRYPTION SCHEMA**

All inter-service communication uses **encrypted tokens** (similar to current GCHostPay token structure).

### **Encryption Key**
- Uses `SUCCESS_URL_SIGNING_KEY` from Secret Manager
- Same key used for GCWebhook → GCSplit1 signature verification

### **Token Structure (Binary Packed)**

#### **GCSplit1 → GCSplit2** (Initial USDT Estimate Request)
```
- 4 bytes: user_id (uint32)
- 16 bytes: closed_channel_id (UTF-8, fixed, padded)
- 1 byte: wallet_address length + variable bytes
- 1 byte: payout_currency length + variable bytes
- 1 byte: payout_network length + variable bytes
- 8 bytes: adjusted_amount_usdt (double)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC-SHA256 signature (truncated)
```

#### **GCSplit2 → GCSplit1** (USDT→ETH Estimate Response)
```
- 4 bytes: user_id (uint32)
- 16 bytes: closed_channel_id (UTF-8, fixed, padded)
- 1 byte: wallet_address length + variable bytes
- 1 byte: payout_currency length + variable bytes
- 1 byte: payout_network length + variable bytes
- 8 bytes: from_amount_usdt (double)
- 8 bytes: to_amount_eth_post_fee (double)
- 8 bytes: deposit_fee (double)
- 8 bytes: withdrawal_fee (double)
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC-SHA256 signature (truncated)
```

#### **GCSplit1 → GCSplit3** (ETH→Client Swap Request)
```
- 16 bytes: unique_id (UTF-8, fixed, padded)
- 4 bytes: user_id (uint32)
- 16 bytes: closed_channel_id (UTF-8, fixed, padded)
- 1 byte: wallet_address length + variable bytes
- 1 byte: payout_currency length + variable bytes
- 1 byte: payout_network length + variable bytes
- 8 bytes: eth_amount (double) - pure market value
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC-SHA256 signature (truncated)
```

#### **GCSplit3 → GCSplit1** (ETH→Client Swap Response)
```
- 16 bytes: unique_id (UTF-8, fixed, padded)
- 4 bytes: user_id (uint32)
- 16 bytes: closed_channel_id (UTF-8, fixed, padded)
- 1 byte: cn_api_id length + variable bytes (ChangeNow transaction ID)
- 1 byte: from_currency length + variable bytes
- 1 byte: to_currency length + variable bytes
- 1 byte: from_network length + variable bytes
- 1 byte: to_network length + variable bytes
- 8 bytes: from_amount (double)
- 8 bytes: to_amount (double)
- 1 byte: payin_address length + variable bytes
- 1 byte: payout_address length + variable bytes
- 1 byte: refund_address length + variable bytes
- 1 byte: flow length + variable bytes
- 1 byte: type length + variable bytes
- 4 bytes: timestamp (uint32)
- 16 bytes: HMAC-SHA256 signature (truncated)
```

---

## ☁️ **CLOUD TASKS CONFIGURATION**

### **Queue Names**
- `gcsplit-usdt-eth-estimate-queue` (GCSplit1 → GCSplit2)
- `gcsplit-usdt-eth-response-queue` (GCSplit2 → GCSplit1)
- `gcsplit-eth-client-swap-queue` (GCSplit1 → GCSplit3)
- `gcsplit-eth-client-response-queue` (GCSplit3 → GCSplit1)
- `gcsplit-hostpay-trigger-queue` (GCSplit1 → GCHostPay)

### **Queue Configuration**
All queues use the following settings:
```bash
--max-dispatches-per-second=<~80% of vendor RPS>
--max-concurrent-dispatches=<ceil(target_rps * p95_latency_sec * 1.5)>
--max-attempts=-1  # Infinite retries
--max-retry-duration=86400s  # 24 hours
--min-backoff=60s  # 60 second minimum backoff
--max-backoff=60s  # 60 second maximum backoff (no exponential backoff)
--max-doublings=0  # Disable exponential backoff
```

**Note**: Exact RPS values will be determined based on ChangeNow API limits (typically ~10-20 RPS for standard plans).

---

## 📁 **FILE STRUCTURE**

```
/10-26/
├── GCSplit1-10-26/
│   ├── tps1-10-26.py          # Main Flask app (3 endpoints)
│   ├── config_manager.py       # Fetches secrets
│   ├── database_manager.py     # Database operations
│   ├── token_manager.py        # Token encryption/decryption
│   ├── cloudtasks_client.py    # Cloud Tasks operations
│   ├── requirements.txt
│   └── Dockerfile
│
├── GCSplit2-10-26/
│   ├── tps2-10-26.py          # Main Flask app (1 endpoint)
│   ├── config_manager.py       # Fetches secrets
│   ├── changenow_client.py     # ChangeNow API wrapper (RETRY LOGIC)
│   ├── token_manager.py        # Token encryption/decryption
│   ├── cloudtasks_client.py    # Cloud Tasks operations
│   ├── requirements.txt
│   └── Dockerfile
│
└── GCSplit3-10-26/
    ├── tps3-10-26.py          # Main Flask app (1 endpoint)
    ├── config_manager.py       # Fetches secrets
    ├── changenow_client.py     # ChangeNow API wrapper (RETRY LOGIC)
    ├── token_manager.py        # Token encryption/decryption
    ├── cloudtasks_client.py    # Cloud Tasks operations
    ├── requirements.txt
    └── Dockerfile
```

---

## 🔄 **COMPLETE DATA FLOW**

### **Step 1: GCWebhook → GCSplit1**
```
POST / (GCSplit1)
├─ Verify HMAC signature (SUCCESS_URL_SIGNING_KEY)
├─ Extract: user_id, closed_channel_id, wallet_address,
│           payout_currency, payout_network, subscription_price
├─ Calculate adjusted_amount = subscription_price - (TP_FLAT_FEE%)
├─ Build encrypted token with above data
└─ Create Cloud Task → GCSplit2
    └─ Queue: gcsplit-usdt-eth-estimate-queue
    └─ Payload: {"token": "<encrypted>"}
```

### **Step 2: GCSplit1 → GCSplit2**
```
POST / (GCSplit2)
├─ Decrypt token
├─ Extract: user_id, closed_channel_id, wallet_address,
│           payout_currency, payout_network, adjusted_amount_usdt
│
├─ Call ChangeNow API v2: GET /v2/exchange/estimated-amount
│   └─ from_currency=usdt, to_currency=eth
│   └─ from_network=eth, to_network=eth
│   └─ from_amount=adjusted_amount_usdt
│   └─ RETRY LOGIC:
│       ├─ If 429 (rate limit): Sleep 60s, retry
│       ├─ If 5xx (server error): Sleep 60s, retry
│       ├─ If timeout: Sleep 60s, retry
│       └─ Continue until 200 OK
│
├─ Extract: toAmount, depositFee, withdrawalFee
├─ Build encrypted token with estimate data
└─ Create Cloud Task → GCSplit1 /usdt-eth-estimate
    └─ Queue: gcsplit-usdt-eth-response-queue
    └─ Payload: {"token": "<encrypted>"}
```

### **Step 3: GCSplit2 → GCSplit1**
```
POST /usdt-eth-estimate (GCSplit1)
├─ Decrypt token
├─ Extract: from_amount, to_amount_post_fee, deposit_fee, withdrawal_fee
│
├─ Calculate pure_market_eth_value:
│   └─ usdt_swapped = from_amount - deposit_fee
│   └─ eth_before_withdrawal = to_amount_post_fee + withdrawal_fee
│   └─ market_rate = eth_before_withdrawal / usdt_swapped
│   └─ pure_market_value = from_amount * market_rate
│
├─ Insert into split_payout_request:
│   └─ from_currency=usdt, to_currency=<payout_currency>
│   └─ from_amount=<from_amount>, to_amount=<pure_market_eth_value>
│   └─ Returns unique_id (primary key)
│
├─ Build encrypted token with (unique_id, pure_market_eth_value, ...)
└─ Create Cloud Task → GCSplit3
    └─ Queue: gcsplit-eth-client-swap-queue
    └─ Payload: {"token": "<encrypted>"}
```

### **Step 4: GCSplit1 → GCSplit3**
```
POST / (GCSplit3)
├─ Decrypt token
├─ Extract: unique_id, user_id, closed_channel_id, wallet_address,
│           payout_currency, payout_network, eth_amount
│
├─ Call ChangeNow API v2: POST /v2/exchange
│   └─ from_currency=eth, to_currency=<payout_currency>
│   └─ from_network=eth, to_network=<payout_network>
│   └─ from_amount=eth_amount
│   └─ address=wallet_address
│   └─ RETRY LOGIC:
│       ├─ If 429 (rate limit): Sleep 60s, retry
│       ├─ If 5xx (server error): Sleep 60s, retry
│       ├─ If timeout: Sleep 60s, retry
│       └─ Continue until 200 OK
│
├─ Extract: id (cn_api_id), payinAddress, fromAmount, toAmount, etc.
├─ Build encrypted token with full transaction data
└─ Create Cloud Task → GCSplit1 /eth-client-swap
    └─ Queue: gcsplit-eth-client-response-queue
    └─ Payload: {"token": "<encrypted>"}
```

### **Step 5: GCSplit3 → GCSplit1**
```
POST /eth-client-swap (GCSplit1)
├─ Decrypt token
├─ Extract: unique_id, cn_api_id, from_currency, to_currency,
│           from_network, to_network, from_amount, to_amount,
│           payin_address, payout_address, refund_address, flow, type
│
├─ Insert into split_payout_que:
│   └─ All extracted fields
│   └─ Links to split_payout_request via unique_id
│
├─ Build GCHostPay token (existing format):
│   └─ unique_id, cn_api_id, from_currency=eth, from_network=eth,
│       from_amount, payin_address
│
└─ Create Cloud Task → GCHostPay10-26
    └─ Queue: gcsplit-hostpay-trigger-queue
    └─ Payload: {"token": "<encrypted_hostpay_token>"}
```

---

## 🔁 **RETRY LOGIC DETAILS**

### **GCSplit2 & GCSplit3 ChangeNow API Retry**

Both services implement the same retry pattern:

```python
def call_changenow_with_retry(api_function, *args, **kwargs):
    """
    Call ChangeNow API with infinite retry logic.

    Retry Conditions:
    - HTTP 429 (Rate Limit)
    - HTTP 5xx (Server Error)
    - Timeout Exception
    - Connection Error

    Backoff: Fixed 60 seconds between retries
    Max Duration: Controlled by Cloud Tasks (24 hours)
    """
    attempt = 0
    while True:
        attempt += 1
        print(f"🔄 [RETRY] Attempt #{attempt}")

        try:
            result = api_function(*args, **kwargs)

            if result:
                print(f"✅ [RETRY] Success after {attempt} attempt(s)")
                return result
            else:
                print(f"⚠️ [RETRY] No result, retrying in 60s...")
                time.sleep(60)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"⏰ [RETRY] Rate limited, waiting 60s...")
            elif 500 <= e.response.status_code < 600:
                print(f"❌ [RETRY] Server error {e.response.status_code}, waiting 60s...")
            else:
                print(f"❌ [RETRY] HTTP error {e.response.status_code}, waiting 60s...")
            time.sleep(60)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"❌ [RETRY] Network error: {e}, waiting 60s...")
            time.sleep(60)

        except Exception as e:
            print(f"❌ [RETRY] Unexpected error: {e}, waiting 60s...")
            time.sleep(60)
```

**Note**: Cloud Tasks will terminate the task after 24 hours (max-retry-duration), preventing infinite loops.

---

## 🗄️ **DATABASE SCHEMA (No Changes Required)**

Existing tables remain unchanged:

### **split_payout_request**
- Stores **MARKET VALUE** of USDT→ETH conversion
- `to_amount` = pure market value (no fees deducted)
- Linked via `unique_id`

### **split_payout_que**
- Stores **ACTUAL TRANSACTION** details
- `to_amount` = actual client payout amount
- Linked via `unique_id`

---

## 🔧 **ENVIRONMENT VARIABLES**

### **GCSplit1-10-26**
```bash
SUCCESS_URL_SIGNING_KEY=projects/.../secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
CLOUD_TASKS_PROJECT_ID=<gcp-project-id>
CLOUD_TASKS_LOCATION=<region>  # e.g., us-central1
GCSPLIT2_QUEUE=gcsplit-usdt-eth-estimate-queue
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app
GCSPLIT3_QUEUE=gcsplit-eth-client-swap-queue
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app
HOSTPAY_QUEUE=gcsplit-hostpay-trigger-queue
HOSTPAY_WEBHOOK_URL=projects/.../secrets/HOSTPAY_WEBHOOK_URL/versions/latest
TPS_HOSTPAY_SIGNING_KEY=projects/.../secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest
TP_FLAT_FEE=projects/.../secrets/TP_FLAT_FEE/versions/latest
# Database credentials (Cloud SQL)
INSTANCE_CONNECTION_NAME=<project>:<region>:<instance>
DB_NAME=<database>
DB_USER=<user>
DB_PASSWORD=projects/.../secrets/DB_PASSWORD/versions/latest
```

### **GCSplit2-10-26**
```bash
SUCCESS_URL_SIGNING_KEY=projects/.../secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
CHANGENOW_API_KEY=projects/.../secrets/CHANGENOW_API_KEY/versions/latest
CLOUD_TASKS_PROJECT_ID=<gcp-project-id>
CLOUD_TASKS_LOCATION=<region>
GCSPLIT1_RESPONSE_QUEUE=gcsplit-usdt-eth-response-queue
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app
```

### **GCSplit3-10-26**
```bash
SUCCESS_URL_SIGNING_KEY=projects/.../secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
CHANGENOW_API_KEY=projects/.../secrets/CHANGENOW_API_KEY/versions/latest
CLOUD_TASKS_PROJECT_ID=<gcp-project-id>
CLOUD_TASKS_LOCATION=<region>
GCSPLIT1_RESPONSE_QUEUE=gcsplit-eth-client-response-queue
GCSPLIT1_URL=https://gcsplit1-10-26-xxx.run.app
```

---

## 📦 **DEPLOYMENT STEPS**

### **1. Create Cloud Tasks Queues**
```bash
# Create all queues with retry configuration
for queue in \
  gcsplit-usdt-eth-estimate-queue \
  gcsplit-usdt-eth-response-queue \
  gcsplit-eth-client-swap-queue \
  gcsplit-eth-client-response-queue \
  gcsplit-hostpay-trigger-queue
do
  gcloud tasks queues create $queue \
    --location=us-central1 \
    --max-dispatches-per-second=10 \
    --max-concurrent-dispatches=50 \
    --max-attempts=-1 \
    --max-retry-duration=86400s \
    --min-backoff=60s \
    --max-backoff=60s \
    --max-doublings=0
done
```

### **2. Deploy Services**
```bash
# Deploy GCSplit1
cd /10-26/GCSplit1-10-26
gcloud run deploy gcsplit1-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars=... \
  --timeout=3600s \
  --cpu=2 \
  --memory=1Gi

# Deploy GCSplit2
cd /10-26/GCSplit2-10-26
gcloud run deploy gcsplit2-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars=... \
  --timeout=3600s \
  --cpu=1 \
  --memory=512Mi

# Deploy GCSplit3
cd /10-26/GCSplit3-10-26
gcloud run deploy gcsplit3-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars=... \
  --timeout=3600s \
  --cpu=1 \
  --memory=512Mi
```

### **3. Update GCWebhook10-26**
Update webhook URL to point to GCSplit1 instead of old GCSplit.

---

## 📊 **MONITORING & LOGGING**

All services use existing emoji logging conventions:
- 🚀 Starting/launching
- ✅ Success
- ❌ Errors
- ⚠️ Warnings
- 🔐 Encryption/decryption
- 🔄 Retry attempts
- 💰 Money/amounts
- 🌐 API calls
- 📦 Payloads
- 🆔 IDs
- ⏰ Timestamps

### **Key Metrics to Monitor**
- Cloud Tasks queue depth
- Task retry counts
- ChangeNow API response times
- Token encryption/decryption failures
- Database insert success rates

---

## ✅ **SUCCESS CRITERIA**

1. **All three services deploy successfully** to Cloud Run
2. **Cloud Tasks queues created** with correct retry configuration
3. **GCWebhook calls GCSplit1** successfully
4. **End-to-end flow completes** from webhook to GCHostPay trigger
5. **ChangeNow API failures handled gracefully** with automatic retries
6. **All database tables updated correctly** (split_payout_request, split_payout_que)
7. **Token encryption/decryption works** across all services
8. **Infinite retry logic prevents failures** during API downtime

---

## 🚨 **CRITICAL IMPLEMENTATION NOTES**

1. **Token Expiry**: Tokens should have long expiry (e.g., 24 hours) to accommodate retry delays
2. **Idempotency**: GCSplit1 endpoints must handle duplicate deliveries gracefully
3. **Database Transactions**: Use transactions when inserting into split_payout_* tables
4. **ChangeNow API Keys**: Ensure API keys have sufficient rate limits
5. **Cloud Run Timeouts**: Set to 1 hour (3600s) to allow for retry loops
6. **Service Authentication**: Consider using Cloud Run service-to-service authentication for production

---

**Implementation Status**: Ready to Begin
**Last Updated**: 2025-10-26
