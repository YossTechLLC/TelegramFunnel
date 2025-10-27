# GCWebhook Split Architecture Documentation

## 📋 Overview

This document describes the split architecture of the GCWebhook service into two independent microservices (GCWebhook1 and GCWebhook2) with Google Cloud Tasks queue management for resilience against rate limiting and burst traffic.

**Date**: 2025-10-26
**Status**: Implementation Complete

---

## 🎯 Objectives

### **Problems Solved**
1. **Rate Limiting Protection**: Telegram Bot API can rate-limit services sending too many invites simultaneously
2. **Burst Traffic Resilience**: NOWPayments success_url callbacks can arrive in bursts, overwhelming a single service
3. **API Downtime Resilience**: Telegram API downtime no longer blocks payment processing
4. **Separation of Concerns**: Payment processing and Telegram invite sending are now independent

### **Key Benefits**
- ✅ Payment confirmations are processed immediately (fast response to NOWPayments)
- ✅ Database writes happen before any external API calls
- ✅ Telegram invites retry infinitely for 24 hours if API is down
- ✅ Payment splits to GCSplit1 retry infinitely for 24 hours
- ✅ Independent scaling for payment processing vs Telegram invite sending
- ✅ No data loss during burst traffic or API failures

---

## 🏗️ Architecture Design

### **Service Overview**

```
NOWPayments API → success_url with TOKEN
        ↓
    GCWebhook1 (Payment Processor)
        ↓
        ├─→ Database Write (private_channel_users_database)
        ├─→ Enqueue to GCWebhook2 (Cloud Tasks) → Telegram Invite
        └─→ Enqueue to GCSplit1 (Cloud Tasks) → Payment Split
```

### **GCWebhook1-10-26** (Payment Processor)

**Responsibilities:**
- Accept GET requests from NOWPayments success_url
- Decrypt and verify TOKEN from URL parameter
- Calculate subscription expiration time/date
- Write to `private_channel_users_database` table
- Encrypt TOKEN and enqueue to GCWebhook2 via Cloud Tasks
- Enqueue payment split to GCSplit1 via Cloud Tasks (with HMAC signature)
- Return HTTP 200 immediately to NOWPayments

**Endpoints:**
- `GET /` - Main success_url endpoint
- `GET /health` - Health check endpoint

**Dependencies:**
- Google Cloud Secret Manager (for configuration)
- Google Cloud SQL (PostgreSQL database)
- Google Cloud Tasks (for async task dispatch)

**No External API Calls** - Fast, reliable processing

### **GCWebhook2-10-26** (Telegram Invite Sender)

**Responsibilities:**
- Accept POST requests from GCWebhook1 via Cloud Tasks
- Decrypt and verify encrypted TOKEN
- Create Telegram one-time invitation link
- Send invitation message to user
- Return HTTP 200 (success) or HTTP 500 (retry)

**Endpoints:**
- `POST /` - Main webhook endpoint (from Cloud Tasks)
- `GET /health` - Health check endpoint

**Dependencies:**
- Google Cloud Secret Manager (for configuration)
- Telegram Bot API (for sending invites)

**Infinite Retry** - Cloud Tasks retries every 60s for 24h on failure

---

## 📊 Cloud Tasks Queues

### **Queue 1: `gcwebhook-telegram-invite-queue`**

**Purpose**: GCWebhook1 → GCWebhook2 (Telegram invite dispatch)

**Configuration:**
```bash
gcloud tasks queues create gcwebhook-telegram-invite-queue \
  --location=us-central1 \
  --max-dispatches-per-second=8 \
  --max-concurrent-dispatches=24 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0
```

**Rationale:**
- `max-dispatches-per-second=8`: Conservative rate (~80% of Telegram bot API limit of ~10 rps for invite links)
- `max-concurrent-dispatches=24`: Assumes 3s p95 latency × 8 rps × 1.5 safety margin = 36 (conservatively set to 24)
- `max-attempts=-1`: Infinite retry for 24 hours (critical that invites always send)
- `60s fixed backoff`: Allows Telegram API to recover from rate limits

### **Queue 2: `gcsplit-webhook-queue`**

**Purpose**: GCWebhook1 → GCSplit1 (Payment split dispatch)

**Configuration:**
```bash
gcloud tasks queues create gcsplit-webhook-queue \
  --location=us-central1 \
  --max-dispatches-per-second=100 \
  --max-concurrent-dispatches=150 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0
```

**Rationale:**
- `max-dispatches-per-second=100`: Internal service, no external rate limits
- `max-concurrent-dispatches=150`: High throughput for burst traffic
- `max-attempts=-1`: Infinite retry for 24 hours
- `60s fixed backoff`: Consistent with other queues

---

## 🔐 Token Flow

### **Token Format (Same for Both Services)**

```
Token Structure (binary packed):
1. user_id (6 bytes, 48-bit, big-endian)
2. closed_channel_id (6 bytes, 48-bit, big-endian)
3. timestamp_minutes (2 bytes, unsigned short, big-endian)
4. subscription_time_days (2 bytes, unsigned short, big-endian)
5. subscription_price (1 byte length + UTF-8 bytes)
6. wallet_address (1 byte length + UTF-8 bytes)
7. payout_currency (1 byte length + UTF-8 bytes)
8. payout_network (1 byte length + UTF-8 bytes)
9. HMAC-SHA256 signature (16 bytes, truncated)

Total minimum size: 38 bytes
Encoding: Base64 URL-safe (without padding)
```

### **Token Encryption Key**
- Seed: `SUCCESS_URL_SIGNING_KEY` (from Google Secret Manager)
- Algorithm: HMAC-SHA256
- Signature: 16-byte truncated
- Validity: 24-hour window (to accommodate retry delays)

### **Token Flow Diagram**

```
NOWPayments API
    ↓ [token via success_url query parameter]
GCWebhook1
    ↓ [decrypt token]
    ├─→ Write to Database
    ├─→ [encrypt fresh token] → Cloud Tasks → GCWebhook2 → [decrypt] → Telegram API
    └─→ [create signed payload] → Cloud Tasks → GCSplit1
```

**Key Points:**
1. **Fresh Token**: GCWebhook1 creates a fresh encrypted token for GCWebhook2 (with new timestamp)
2. **Signature Verification**: Both services verify HMAC signature independently
3. **24-Hour Validity**: Tokens valid for 24 hours to accommodate Cloud Tasks retry duration

---

## 🗄️ Database Schema

### **Table: `private_channel_users_database`**

**Purpose**: Track user subscriptions to private channels

**Schema:**
```sql
CREATE TABLE private_channel_users_database (
    private_channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    sub_time INT NOT NULL,
    sub_price VARCHAR(50) NOT NULL,
    timestamp TIME NOT NULL,
    datestamp DATE NOT NULL,
    expire_time TIME NOT NULL,
    expire_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (user_id, private_channel_id)
);
```

**Written By**: GCWebhook1 (before enqueuing any tasks)

**Read By**: TelePay10-26 (for subscription validation)

---

## 📂 File Structure

### **GCWebhook1-10-26/**
```
GCWebhook1-10-26/
├── tph1-10-26.py              # Main Flask app (payment processor)
├── config_manager.py          # Secret Manager + env config
├── database_manager.py        # PostgreSQL operations
├── token_manager.py           # Token encrypt/decrypt
├── cloudtasks_client.py       # Cloud Tasks dispatcher
├── Dockerfile                 # Container definition
├── requirements.txt           # Python dependencies
└── .dockerignore             # Docker build exclusions
```

**Dependencies (requirements.txt):**
```
Flask==3.0.3
google-cloud-secret-manager==2.16.3
google-cloud-tasks==2.16.1
cloud-sql-python-connector==1.4.3
pg8000==1.30.3
```

### **GCWebhook2-10-26/**
```
GCWebhook2-10-26/
├── tph2-10-26.py              # Main Flask app (Telegram invite sender)
├── config_manager.py          # Secret Manager + env config
├── token_manager.py           # Token decrypt
├── Dockerfile                 # Container definition
├── requirements.txt           # Python dependencies
└── .dockerignore             # Docker build exclusions
```

**Dependencies (requirements.txt):**
```
Flask==3.0.3
python-telegram-bot==20.7
google-cloud-secret-manager==2.16.3
```

---

## 🔧 Configuration

### **GCWebhook1 Environment Variables**

```bash
# Secret Manager Paths
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
GCWEBHOOK2_QUEUE=projects/291176869049/secrets/GCWEBHOOK2_QUEUE/versions/latest
GCWEBHOOK2_URL=projects/291176869049/secrets/GCWEBHOOK2_URL/versions/latest
GCSPLIT1_QUEUE=projects/291176869049/secrets/GCSPLIT1_QUEUE/versions/latest
GCSPLIT1_URL=projects/291176869049/secrets/GCSPLIT1_URL/versions/latest
CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest
```

### **GCWebhook2 Environment Variables**

```bash
# Secret Manager Paths
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_TOKEN/versions/latest
```

---

## 🚀 Deployment Guide

### **Step 1: Deploy Cloud Tasks Queues**

```bash
cd /path/to/OCTOBER/10-26/
chmod +x deploy_gcwebhook_queues.sh
./deploy_gcwebhook_queues.sh
```

### **Step 2: Build and Deploy GCWebhook1**

```bash
cd GCWebhook1-10-26/

# Build container image
gcloud builds submit --tag gcr.io/telepay-f7f59/gcwebhook1-10-26:latest

# Deploy to Cloud Run
gcloud run deploy gcwebhook1-10-26 \
  --image gcr.io/telepay-f7f59/gcwebhook1-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,GCWEBHOOK2_QUEUE=projects/291176869049/secrets/GCWEBHOOK2_QUEUE/versions/latest,GCWEBHOOK2_URL=projects/291176869049/secrets/GCWEBHOOK2_URL/versions/latest,GCSPLIT1_QUEUE=projects/291176869049/secrets/GCSPLIT1_QUEUE/versions/latest,GCSPLIT1_URL=projects/291176869049/secrets/GCSPLIT1_URL/versions/latest,CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest,DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest,DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest
```

### **Step 3: Build and Deploy GCWebhook2**

```bash
cd ../GCWebhook2-10-26/

# Build container image
gcloud builds submit --tag gcr.io/telepay-f7f59/gcwebhook2-10-26:latest

# Deploy to Cloud Run
gcloud run deploy gcwebhook2-10-26 \
  --image gcr.io/telepay-f7f59/gcwebhook2-10-26:latest \
  --region us-central1 \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_TOKEN/versions/latest
```

**Note**: GCWebhook2 uses `--no-allow-unauthenticated` because it only receives requests from Cloud Tasks (which authenticates automatically).

### **Step 4: Update Secret Manager with Service URLs**

```bash
cd /path/to/OCTOBER/10-26/
chmod +x setup_gcwebhook_secrets.sh
./setup_gcwebhook_secrets.sh
```

Follow the prompts to set GCWEBHOOK2_URL after deployment.

### **Step 5: Update TelePay Success URL**

Update the success_url in TelePay10-26 bot to point to GCWebhook1:

```python
# In TelePay10-26/bot_manager.py or wherever success_url is generated
success_url = "https://gcwebhook1-10-26-xxx.run.app/?token={token}"
```

---

## 🚨 Failure Scenarios & Recovery

### **Scenario 1: Telegram API Down**

**Impact**: GCWebhook2 tasks accumulate in `gcwebhook-telegram-invite-queue`

**Behavior**:
1. Cloud Tasks retries every 60s for 24h
2. GCWebhook1 continues processing payments normally
3. Database writes complete successfully
4. Payment splits to GCSplit1 continue normally

**Recovery**: When Telegram API recovers, all pending invites send in order

**User Experience**: Delay in receiving invite (but payment already processed)

### **Scenario 2: GCSplit1 Down**

**Impact**: GCWebhook1 tasks accumulate in `gcsplit-webhook-queue`

**Behavior**:
1. Cloud Tasks retries every 60s for 24h
2. GCWebhook1 continues processing payments normally
3. Database writes complete successfully
4. Telegram invites continue sending normally

**Recovery**: When GCSplit1 recovers, all payment splits process in order

**User Experience**: No impact (payment split is async, user already has invite)

### **Scenario 3: Database Down**

**Impact**: GCWebhook1 cannot write to `private_channel_users_database`

**Behavior**:
1. GCWebhook1 returns HTTP 500 to NOWPayments
2. NOWPayments retries success_url (their retry logic)
3. No tasks enqueued until database write succeeds

**Recovery**: When database recovers, NOWPayments re-sends success_url

**User Experience**: Delay in payment confirmation (acceptable)

### **Scenario 4: NOWPayments Burst Traffic**

**Impact**: Many success_url requests hit GCWebhook1 simultaneously

**Behavior**:
1. GCWebhook1 processes all quickly (no external API calls except database)
2. Database writes complete at normal speed
3. Cloud Tasks queues throttle downstream processing:
   - Telegram invites: 8 per second (rate-limited)
   - GCSplit1: 100 per second (high throughput)

**Recovery**: All tasks eventually process (queue depth increases temporarily)

**User Experience**: Some users receive invites faster than others (acceptable)

---

## 📈 Monitoring & Alerting

### **Key Metrics to Monitor**

#### **GCWebhook1**
1. **Request Rate**: Success_url requests per second
2. **Response Time**: P50, P95, P99 latency
3. **Error Rate**: % of 5xx responses
4. **Database Write Latency**: Time to write to database
5. **Task Enqueue Success Rate**: % of successful Cloud Tasks enqueues

#### **GCWebhook2**
1. **Request Rate**: Tasks received from Cloud Tasks
2. **Telegram API Success Rate**: % of successful invite sends
3. **Telegram API Latency**: Time to create invite link + send message
4. **Error Rate**: % of 5xx responses (triggers retry)
5. **Retry Count**: Average retries per task

#### **Cloud Tasks Queues**
1. **Queue Depth**: Number of pending tasks in each queue
2. **Task Age**: Time tasks have been waiting in queue
3. **Dispatch Rate**: Tasks dispatched per second
4. **Retry Rate**: % of tasks requiring retry

### **Recommended Alerts**

```yaml
alerts:
  - name: GCWebhook1 High Error Rate
    condition: error_rate > 1%
    severity: critical

  - name: GCWebhook2 High Retry Count
    condition: avg_retry_count_per_task > 10
    severity: warning

  - name: Queue Depth Too High
    condition: queue_depth > 1000
    severity: warning

  - name: Task Age Too High
    condition: max_task_age > 300s
    severity: warning

  - name: Telegram API Error Rate
    condition: telegram_error_rate > 5%
    severity: critical
```

---

## 🧪 Testing Checklist

### **Unit Testing**
- [ ] GCWebhook1 token decryption
- [ ] GCWebhook1 database write
- [ ] GCWebhook1 token encryption for GCWebhook2
- [ ] GCWebhook1 Cloud Tasks enqueue
- [ ] GCWebhook2 token decryption
- [ ] GCWebhook2 Telegram invite creation
- [ ] GCWebhook2 message sending

### **Integration Testing**
- [ ] End-to-end flow: NOWPayments → GCWebhook1 → Database
- [ ] End-to-end flow: GCWebhook1 → Cloud Tasks → GCWebhook2 → Telegram
- [ ] End-to-end flow: GCWebhook1 → Cloud Tasks → GCSplit1
- [ ] Retry behavior: Telegram API failure triggers retry
- [ ] Retry behavior: GCSplit1 failure triggers retry
- [ ] Token expiration validation
- [ ] Signature verification

### **Load Testing**
- [ ] Burst traffic: 100 simultaneous success_url requests
- [ ] Sustained traffic: 50 rps for 5 minutes
- [ ] Queue depth monitoring during load
- [ ] Response time under load (should stay < 500ms)

### **Failure Testing**
- [ ] Telegram API down: Verify infinite retry
- [ ] Database down: Verify NOWPayments retry
- [ ] GCSplit1 down: Verify infinite retry
- [ ] Invalid token: Verify rejection
- [ ] Expired token: Verify rejection

---

## 📋 Migration Checklist

### **Pre-Migration**
- [ ] Deploy GCWebhook1 and GCWebhook2 services
- [ ] Create Cloud Tasks queues
- [ ] Update Secret Manager with new URLs
- [ ] Test health check endpoints
- [ ] Run integration tests

### **Migration**
- [ ] Update TelePay success_url to point to GCWebhook1
- [ ] Monitor logs for first few transactions
- [ ] Verify database writes
- [ ] Verify Telegram invites send
- [ ] Verify payment splits process

### **Post-Migration**
- [ ] Archive old GCWebhook10-26 to ARCHIVES/
- [ ] Update documentation
- [ ] Remove old service URLs from Secret Manager
- [ ] Delete old Cloud Run service (after 7-day grace period)

---

## 🎉 Success Criteria

1. **Resilience**: GCWebhook1 handles burst traffic without dropping requests
2. **Isolation**: Telegram API failures don't affect payment processing
3. **Retry**: Both Telegram invites and GCSplit1 triggers retry infinitely (up to 24h)
4. **Performance**: GCWebhook1 responds to success_url within 500ms
5. **Reliability**: Zero data loss during payment processing → Telegram invite flow
6. **Monitoring**: All key metrics visible in Cloud Monitoring dashboard

---

**Document Version**: 1.0
**Last Updated**: 2025-10-26
**Author**: Claude Code
