# GCWebhook Split Implementation Checklist

## 📋 Overview

**Objective**: Split monolithic GCWebhook into two independent services with Google Cloud Tasks queue management for resilience against rate limiting and burst traffic.

**Current Risk**: Single GCWebhook service can be overwhelmed by burst traffic from NOWPayments API or rate-limited by Telegram API.

**Solution**: Separate concerns into two services with independent Cloud Tasks queues for asynchronous processing and infinite retry.

---

## 🏗️ Architecture Design

### **Service Separation**

#### **GCWebhook1-10-26** (Payment Processor)
**Responsibilities:**
1. Accept success_url GET requests from NOWPayments API
2. Decrypt TOKEN from URL parameter
3. Calculate expire_time and expire_date
4. Populate `private_channel_users_database` table
5. Encrypt TOKEN and enqueue to GCWebhook2 via Cloud Tasks
6. Encrypt TOKEN and enqueue to GCSplit1 via Cloud Tasks

**Endpoints:**
- `GET /` - Main success_url endpoint (accepts token parameter)
- `GET /health` - Health check endpoint

**Key Features:**
- No direct external API calls (no rate limiting risk)
- Database writes only
- Asynchronous task dispatch only
- Fast response to NOWPayments

#### **GCWebhook2-10-26** (Telegram Invite Sender)
**Responsibilities:**
1. Accept encrypted TOKEN from GCWebhook1 via Cloud Tasks
2. Decrypt TOKEN
3. Send Telegram one-time invitation link with infinite retry
4. Return success/failure status

**Endpoints:**
- `POST /` - Main webhook endpoint (accepts encrypted token)
- `GET /health` - Health check endpoint

**Key Features:**
- Infinite retry for Telegram API calls (60s fixed backoff)
- Independent scaling from GCWebhook1
- Isolated from NOWPayments success_url processing

---

## 📊 Cloud Tasks Queues

### **New Queue: `gcwebhook-telegram-invite-queue`**
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
- `max-dispatches-per-second=8`: Conservative rate (~80% of Telegram bot API limit of ~10 rps)
- `max-concurrent-dispatches=24`: Assumes 3s p95 latency × 8 rps × 1.5 safety margin
- `max-attempts=-1`: Infinite retry for 24 hours
- `60s fixed backoff`: Allows Telegram API to recover from rate limits

### **Existing Queue: `gcsplit-webhook-queue`**
**Purpose**: GCWebhook1 → GCSplit1 (Payment split dispatch)

**Already configured with:**
- Infinite retry (24h max duration)
- 60s fixed backoff
- No rate limiting concerns (internal service)

---

## 🔐 Token Flow

### **Encryption Schema**

#### **Token Structure (same as current GCWebhook)**
```
Fields (in order):
1. user_id (8 bytes, unsigned long long, big-endian)
2. closed_channel_id (8 bytes, signed long long, big-endian)
3. wallet_address (1 byte length + UTF-8 bytes)
4. payout_currency (1 byte length + UTF-8 bytes)
5. payout_network (1 byte length + UTF-8 bytes)
6. subscription_time_days (4 bytes, unsigned int, big-endian)
7. subscription_price (1 byte length + UTF-8 bytes)
8. HMAC-SHA256 signature (16 bytes, truncated)
```

#### **Encryption Key**
- Seed: `SUCCESS_URL_SIGNING_KEY` (from Google Secret Manager)
- Algorithm: HMAC-SHA256
- Signature: 16-byte truncated
- Encoding: Base64 URL-safe (without padding)

### **Token Flow Diagram**
```
NOWPayments API → success_url with TOKEN (unencrypted query param)
  ↓
GCWebhook1 receives TOKEN
  ↓
  ├─→ Decrypt TOKEN locally
  │     ↓
  │   Calculate expire_time/expire_date
  │     ↓
  │   Write to private_channel_users_database
  │     ↓
  │   Encrypt TOKEN → Enqueue to GCWebhook2 (Cloud Tasks)
  │     ↓
  │   Encrypt TOKEN → Enqueue to GCSplit1 (Cloud Tasks)
  │     ↓
  │   Return HTTP 200 to NOWPayments
  │
  └─→ Cloud Tasks dispatches to GCWebhook2
        ↓
      GCWebhook2 receives encrypted TOKEN
        ↓
      Decrypt TOKEN
        ↓
      Call Telegram API (with infinite retry)
        ↓
      Send invitation link to user_id for closed_channel_id
        ↓
      Return success (Cloud Tasks marks complete)
```

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

---

## ✅ Implementation Checklist

### **Phase 1: Design & Documentation**
- [x] Create implementation checklist document
- [ ] Design GCWebhook1 token flow and endpoint logic
- [ ] Design GCWebhook2 token flow and endpoint logic
- [ ] Document database schema requirements (no changes expected)
- [ ] Document Secret Manager requirements

### **Phase 2: GCWebhook1 Service Implementation**
- [ ] Create GCWebhook1-10-26/ directory
- [ ] Implement `tph1-10-26.py` main Flask app
  - [ ] GET / endpoint (success_url handler)
  - [ ] Token decryption logic
  - [ ] expire_time/expire_date calculation
  - [ ] Database write to private_channel_users_database
  - [ ] Encrypt and enqueue to GCWebhook2
  - [ ] Encrypt and enqueue to GCSplit1
  - [ ] Health check endpoint
- [ ] Implement `config_manager.py` (Secret Manager integration)
- [ ] Implement `database_manager.py` (PostgreSQL operations)
- [ ] Implement `token_manager.py` (encrypt/decrypt functions)
- [ ] Implement `cloudtasks_client.py` (task dispatch)
- [ ] Create `Dockerfile` for GCWebhook1
- [ ] Create `requirements.txt` for GCWebhook1
- [ ] Create `.dockerignore` for GCWebhook1

### **Phase 3: GCWebhook2 Service Implementation**
- [ ] Create GCWebhook2-10-26/ directory
- [ ] Implement `tph2-10-26.py` main Flask app
  - [ ] POST / endpoint (Cloud Tasks webhook handler)
  - [ ] Token decryption logic
  - [ ] Telegram Bot API integration with infinite retry
  - [ ] Create one-time invitation link
  - [ ] Send invitation message to user
  - [ ] Health check endpoint
- [ ] Implement `config_manager.py` (Secret Manager integration)
- [ ] Implement `token_manager.py` (decrypt functions)
- [ ] Create `Dockerfile` for GCWebhook2
- [ ] Create `requirements.txt` for GCWebhook2
- [ ] Create `.dockerignore` for GCWebhook2

### **Phase 4: Cloud Tasks Queue Configuration**
- [ ] Create `deploy_gcwebhook_queues.sh` script
- [ ] Add `gcwebhook-telegram-invite-queue` configuration
- [ ] Verify `gcsplit-webhook-queue` still used by GCWebhook1
- [ ] Document queue parameters and rationale

### **Phase 5: Secret Manager Configuration**
- [ ] Add `GCWEBHOOK2_URL` secret (GCWebhook2 service URL)
- [ ] Verify existing secrets still work:
  - `SUCCESS_URL_SIGNING_KEY`
  - `GCSPLIT1_URL`
  - `TELEGRAM_BOT_TOKEN`
  - `DATABASE_PASSWORD`
  - Cloud Tasks project/location/queue names

### **Phase 6: Deployment Scripts**
- [ ] Update main deployment guide with GCWebhook1/2 instructions
- [ ] Create deployment script for GCWebhook1
- [ ] Create deployment script for GCWebhook2
- [ ] Update `update_service_urls.sh` to include GCWEBHOOK2_URL
- [ ] Test local builds with Docker

### **Phase 7: Testing & Validation**
- [ ] Test GCWebhook1 success_url endpoint locally
- [ ] Test token encryption/decryption flow
- [ ] Test database write operations
- [ ] Test Cloud Tasks enqueue operations (mocked)
- [ ] Test GCWebhook2 Telegram invite flow locally
- [ ] Test end-to-end flow with Cloud Tasks (staging)
- [ ] Verify infinite retry behavior
- [ ] Load test with burst traffic simulation

### **Phase 8: Documentation**
- [ ] Create `GCWEBHOOK_SPLIT_ARCHITECTURE.md`
- [ ] Document service responsibilities
- [ ] Document token flow between services
- [ ] Document failure scenarios and retry logic
- [ ] Document deployment procedures
- [ ] Document monitoring and alerting setup
- [ ] Update main `DEPLOYMENT_GUIDE.md`

### **Phase 9: Migration & Cleanup**
- [ ] Archive old GCWebhook10-26/ to ARCHIVES/
- [ ] Update TelePay registration to use new GCWebhook1 success_url
- [ ] Verify no references to old GCWebhook10-26 remain
- [ ] Update environment variable documentation

---

## 🎯 Success Criteria

1. **Resilience**: GCWebhook1 can handle burst traffic from NOWPayments without dropping requests
2. **Isolation**: Telegram API rate limiting in GCWebhook2 does not affect payment processing in GCWebhook1
3. **Retry**: Both Telegram invites and GCSplit1 triggers retry infinitely (up to 24h) on failure
4. **Performance**: GCWebhook1 responds to success_url within 500ms
5. **Reliability**: Zero data loss during payment processing → Telegram invite flow

---

## 📊 Queue Parameters Rationale

### **gcwebhook-telegram-invite-queue**
```bash
--max-dispatches-per-second=8
```
- **Vendor**: Telegram Bot API
- **Rate Limit**: ~30 messages/second per bot (official limit)
- **Conservative RPS**: 10 (for invitation links)
- **80% Target**: 8 rps (safety margin for burst)

```bash
--max-concurrent-dispatches=24
```
- **Formula**: `ceil(target_rps * p95_latency_sec * 1.5)`
- **Calculation**: `ceil(8 * 3 * 1.5) = ceil(36) = 36`
- **Conservative**: 24 (lower bound estimate, can increase if needed)

```bash
--max-attempts=-1 --max-retry-duration=86400s
```
- **Infinite retry for 24 hours**: Critical that invites always send
- **Fixed 60s backoff**: Allows Telegram API to recover from rate limits

### **gcsplit-webhook-queue** (existing)
```bash
--max-dispatches-per-second=100
```
- **Internal service**: No external rate limits
- **High throughput**: Can handle burst traffic efficiently

---

## 🚨 Failure Scenarios

### **Scenario 1: Telegram API Down**
- **Impact**: GCWebhook2 tasks accumulate in `gcwebhook-telegram-invite-queue`
- **Behavior**: Cloud Tasks retries every 60s for 24h
- **Outcome**: When Telegram API recovers, all invites send in order
- **User Experience**: Delay in receiving invite (but payment already processed)

### **Scenario 2: GCSplit1 Down**
- **Impact**: GCWebhook1 tasks accumulate in `gcsplit-webhook-queue`
- **Behavior**: Cloud Tasks retries every 60s for 24h
- **Outcome**: When GCSplit1 recovers, all payment splits process in order
- **User Experience**: No impact (payment split is async and user already has invite)

### **Scenario 3: Database Down**
- **Impact**: GCWebhook1 cannot write to `private_channel_users_database`
- **Behavior**: GCWebhook1 returns 500 error to NOWPayments
- **Outcome**: NOWPayments retries success_url (their retry logic)
- **User Experience**: Delay in payment confirmation (acceptable)

### **Scenario 4: NOWPayments Burst Traffic**
- **Impact**: Many success_url requests hit GCWebhook1 simultaneously
- **Behavior**: GCWebhook1 processes all quickly (no external API calls), enqueues to Cloud Tasks
- **Outcome**: Cloud Tasks throttles Telegram invites at 8 rps, but all process eventually
- **User Experience**: Some users receive invites faster than others (acceptable)

---

## 📈 Monitoring Recommendations

### **Key Metrics**
1. **GCWebhook1**:
   - Success_url request rate
   - Database write latency
   - Cloud Tasks enqueue success rate
   - Response time to NOWPayments

2. **GCWebhook2**:
   - Telegram API success rate
   - Telegram API latency
   - Retry count per task
   - Queue depth (`gcwebhook-telegram-invite-queue`)

3. **Cloud Tasks Queues**:
   - `gcwebhook-telegram-invite-queue` depth
   - `gcsplit-webhook-queue` depth
   - Task age (time in queue)
   - Retry rate

### **Alerts**
1. GCWebhook1 error rate > 1%
2. GCWebhook2 retry count > 10 per task
3. Queue depth > 1000 tasks
4. Task age > 5 minutes (indicates backlog)
5. Telegram API error rate > 5%

---

## 🔧 Next Steps

1. Review and approve this architecture design
2. Proceed with Phase 2: GCWebhook1 implementation
3. Proceed with Phase 3: GCWebhook2 implementation
4. Deploy and test in staging environment
5. Monitor metrics and tune queue parameters
6. Deploy to production

---

**Created**: 2025-10-26
**Status**: Ready for implementation
