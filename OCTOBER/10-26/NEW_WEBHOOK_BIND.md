# NEW_WEBHOOK_BIND - Webhook Communication Architecture

## Overview
This document details the webhook communication patterns between all services in the TelePay ecosystem, showing how each service communicates through HTTP endpoints and Cloud Tasks to facilitate the complete payment and notification workflow.

## Services Architecture

### Core Services
1. **TelePay10-26** - Main bot service
2. **np-webhook-10-26** - NowPayments IPN handler
3. **GCWebhook1-10-26** - Payment processor
4. **GCWebhook2-10-26** - Telegram invite service
5. **GCNotificationService-10-26** - Payment notification service
6. **GCBroadcastService-10-26** - Broadcast management (manual triggers)
7. **GCBroadcastScheduler-10-26** - Broadcast execution (automated)

---

## Webhook Communication Flows

### 1. Payment Processing Flow

#### 1.1 Invoice Creation (TelePay → NowPayments API)
**Trigger:** User initiates subscription/donation
**Service:** TelePay10-26 → NowPayments API

**Endpoint Flow:**
```
TelePay10-26 (services/payment_service.py)
  ↓ POST https://api.nowpayments.io/v1/invoice
  → NowPayments API
```

**Request Body:**
```json
{
  "price_amount": 29.99,
  "price_currency": "USD",
  "order_id": "PGP-{user_id}|{channel_id}",
  "order_description": "Premium Subscription - Tier 1",
  "success_url": "https://{gcwebhook1-url}?token={signed_token}",
  "ipn_callback_url": "https://{np-webhook-url}/",
  "is_fixed_rate": false,
  "is_fee_paid_by_user": false
}
```

**Success URL Token Structure:**
- User ID (6 bytes)
- Channel ID (6 bytes)
- Timestamp (2 bytes)
- Subscription time (2 bytes)
- Price (variable)
- Wallet address (variable, max 110 bytes)
- Currency (variable, max 4 bytes)
- Network (variable, max 10 bytes)
- HMAC signature (16 bytes)

---

#### 1.2 IPN Callback (NowPayments → np-webhook)
**Trigger:** Payment confirmed by NowPayments
**Service:** NowPayments API → np-webhook-10-26

**Endpoint:**
```
POST https://{np-webhook-url}/
```

**Headers:**
```
x-nowpayments-sig: {HMAC-SHA512 signature}
```

**Request Body:**
```json
{
  "payment_id": 4479119533,
  "payment_status": "finished",
  "pay_address": "0x123...",
  "price_amount": 29.99,
  "price_currency": "USD",
  "pay_amount": 0.00785,
  "actually_paid": 0.00785,
  "pay_currency": "ETH",
  "order_id": "PGP-123456789|-1001234567890",
  "order_description": "Premium Subscription - Tier 1",
  "purchase_id": "5678901234",
  "outcome_amount": 29.45,
  "outcome_currency": "USD"
}
```

**Processing Steps:**
1. Verify HMAC-SHA512 signature using `NOWPAYMENTS_IPN_SECRET`
2. Extract `payment_id` and payment metadata
3. Update database (`client_table.payment_id`, `nowpayments_outcome_usd`)
4. Trigger GCWebhook1 via Cloud Tasks
5. Trigger GCNotificationService via HTTP POST

---

#### 1.3 Payment Notification (np-webhook → GCNotificationService)
**Trigger:** After successful IPN validation
**Service:** np-webhook-10-26 → GCNotificationService-10-26

**Endpoint:**
```
POST https://{gcnotificationservice-url}/send-notification
```

**Request Body:**
```json
{
  "open_channel_id": "-1003268562225",
  "payment_type": "subscription",
  "payment_data": {
    "user_id": 123456789,
    "username": "john_doe",
    "amount_crypto": "0.00785",
    "amount_usd": "29.99",
    "crypto_currency": "ETH",
    "tier": 1,
    "tier_price": "29.99",
    "duration_days": 30,
    "timestamp": "2025-11-14 14:32:15 UTC"
  }
}
```

**Processing (GCNotificationService):**
1. Fetch notification settings from database (`notification_status`, `notification_id`)
2. Check if notifications are enabled for the channel
3. Format message based on payment type (subscription/donation)
4. Send notification via Telegram Bot API to channel owner

**Response:**
```json
{
  "status": "success",
  "message": "Notification sent successfully"
}
```

---

#### 1.4 Payment Processing (np-webhook → GCWebhook1)
**Trigger:** After successful IPN validation
**Service:** np-webhook-10-26 → GCWebhook1-10-26 (via Cloud Tasks)

**Cloud Tasks Queue:** `gcwebhook1-queue`

**Endpoint:**
```
POST https://{gcwebhook1-url}/process-validated-payment
```

**Request Body:**
```json
{
  "payment_id": 4479119533,
  "user_id": 123456789,
  "closed_channel_id": -1001234567890,
  "open_channel_id": -1003268562225,
  "client_id": "uuid-client-id",
  "wallet_address": "0x123...",
  "payout_currency": "ETH",
  "payout_network": "ETH",
  "subscription_time_days": 30,
  "subscription_price": "29.99",
  "amount_crypto": "0.00785",
  "crypto_currency": "ETH",
  "outcome_usd": "29.45"
}
```

**Processing (GCWebhook1):**
1. Calculate expiration time/date
2. Record subscription in database (`private_channel_users_database`)
3. Trigger GCWebhook2 (Telegram invite) via Cloud Tasks
4. Trigger GCSplit1 (payment split) via Cloud Tasks

---

#### 1.5 Telegram Invite (GCWebhook1 → GCWebhook2)
**Trigger:** After payment processing
**Service:** GCWebhook1-10-26 → GCWebhook2-10-26 (via Cloud Tasks)

**Cloud Tasks Queue:** `gcwebhook2-queue`

**Endpoint:**
```
POST https://{gcwebhook2-url}/
```

**Request Body (Encrypted):**
```json
{
  "encrypted_data": "{base64_encrypted_payload}"
}
```

**Decrypted Payload:**
```json
{
  "user_id": 123456789,
  "closed_channel_id": -1001234567890
}
```

**Processing (GCWebhook2):**
1. Decrypt payload using AES-256
2. Generate invite link for closed channel
3. Send invite link to user via Telegram Bot API

---

### 2. Broadcast Communication Flow

#### 2.1 Manual Broadcast Trigger (Website → GCBroadcastService)
**Trigger:** User clicks "Send Now" button on dashboard
**Service:** www.paygateprime.com → GCBroadcastService-10-26

**Endpoint:**
```
POST https://{gcbroadcastservice-url}/api/broadcast/trigger
```

**Headers:**
```
Authorization: Bearer {JWT_TOKEN}
Content-Type: application/json
```

**Request Body:**
```json
{
  "broadcast_id": "uuid-broadcast-id"
}
```

**Processing (GCBroadcastService):**
1. Verify JWT token (extract `client_id` from `sub` claim)
2. Check manual trigger rate limit (default: 5 minutes)
3. Verify user owns the broadcast
4. Queue broadcast for immediate execution
5. Update `last_manual_trigger_time` in database

**Response (Success):**
```json
{
  "success": true,
  "message": "Broadcast queued for sending",
  "broadcast_id": "uuid-broadcast-id"
}
```

**Response (Rate Limited):**
```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "retry_after_seconds": 180
}
```

---

#### 2.2 Broadcast Status Query (Website → GCBroadcastService)
**Trigger:** Dashboard loads broadcast statistics
**Service:** www.paygateprime.com → GCBroadcastService-10-26

**Endpoint:**
```
GET https://{gcbroadcastservice-url}/api/broadcast/status/{broadcast_id}
```

**Headers:**
```
Authorization: Bearer {JWT_TOKEN}
```

**Processing:**
1. Verify JWT token
2. Fetch broadcast statistics from database
3. Verify user owns the broadcast (authorization check)
4. Return statistics

**Response:**
```json
{
  "broadcast_id": "uuid-broadcast-id",
  "broadcast_status": "completed",
  "last_sent_time": "2025-11-14T12:00:00Z",
  "next_send_time": "2025-11-15T12:00:00Z",
  "total_broadcasts": 10,
  "successful_broadcasts": 9,
  "failed_broadcasts": 1,
  "consecutive_failures": 0,
  "is_active": true,
  "manual_trigger_count": 2
}
```

---

#### 2.3 Automated Broadcast Execution (Cloud Scheduler → GCBroadcastScheduler)
**Trigger:** Cloud Scheduler cron job (daily)
**Service:** Cloud Scheduler → GCBroadcastScheduler-10-26

**Endpoint:**
```
POST https://{gcbroadcastscheduler-url}/api/broadcast/execute
```

**Request Body (Optional):**
```json
{
  "source": "cloud_scheduler"
}
```

**Processing (GCBroadcastScheduler):**
1. Fetch all broadcasts due for sending (`broadcast_scheduler.get_due_broadcasts()`)
2. Execute each broadcast via `broadcast_executor.execute_batch()`
3. Send messages via Telegram Bot API
4. Update broadcast statistics in database
5. Calculate next send time

**Response:**
```json
{
  "success": true,
  "total_broadcasts": 10,
  "successful": 9,
  "failed": 1,
  "execution_time_seconds": 45.2,
  "results": [
    {
      "broadcast_id": "uuid-1",
      "status": "success",
      "message_id": 12345
    },
    {
      "broadcast_id": "uuid-2",
      "status": "failed",
      "error": "Chat not found"
    }
  ]
}
```

---

### 3. Notification Flow (Alternative - Embedded)

#### 3.1 TelePay Internal Notification (DEPRECATED)
**Note:** This flow shows the legacy embedded notification pattern, now replaced by GCNotificationService.

**Endpoint:**
```
POST https://{telepay-url}/webhooks/notification
```

**Security:**
- HMAC signature verification
- IP whitelist
- Rate limiting

**Request Body:**
```json
{
  "open_channel_id": "-1003268562225",
  "payment_type": "subscription",
  "payment_data": {...}
}
```

**Processing (TelePay):**
1. Verify security (HMAC + IP whitelist + rate limit)
2. Get `notification_service` from Flask app context
3. Call `notification_service.send_payment_notification()` (async)
4. Send via Telegram Bot API

---

## Service Endpoints Summary

### TelePay10-26
- **GET /health** - Health check
- **POST /webhooks/notification** - Internal notification endpoint (deprecated)

### np-webhook-10-26
- **POST /** - NowPayments IPN callback
- **GET /payment-processing** - Payment processing page
- **GET /api/payment-status/{order_id}** - Payment status query

### GCWebhook1-10-26
- **GET /** - Success URL redirect (legacy)
- **POST /process-validated-payment** - Process validated payment
- **GET /health** - Health check

### GCWebhook2-10-26
- **POST /** - Telegram invite generation
- **GET /health** - Health check

### GCNotificationService-10-26
- **POST /send-notification** - Send payment notification
- **POST /test-notification** - Send test notification
- **GET /health** - Health check

### GCBroadcastService-10-26
- **POST /api/broadcast/trigger** - Manual broadcast trigger (JWT required)
- **GET /api/broadcast/status/{broadcast_id}** - Get broadcast status (JWT required)
- **POST /api/broadcast/execute** - Execute broadcasts (Cloud Scheduler)
- **GET /health** - Health check

### GCBroadcastScheduler-10-26
- **POST /api/broadcast/trigger** - Manual broadcast trigger (JWT required)
- **GET /api/broadcast/status/{broadcast_id}** - Get broadcast status (JWT required)
- **POST /api/broadcast/execute** - Execute broadcasts (Cloud Scheduler)
- **GET /health** - Health check

---

## Security Patterns

### JWT Authentication (Broadcast Services)
- **Used by:** GCBroadcastService, GCBroadcastScheduler
- **Algorithm:** HS256
- **Claims:** `sub` (client_id), `exp` (expiration)
- **Leeway:** 10 seconds for clock skew
- **Endpoints:** `/api/broadcast/trigger`, `/api/broadcast/status/*`

### HMAC Signature Verification
- **Used by:** np-webhook (NowPayments IPN)
- **Algorithm:** HMAC-SHA512
- **Header:** `x-nowpayments-sig`
- **Secret:** `NOWPAYMENTS_IPN_SECRET`

### Token-Based URL Signing
- **Used by:** Success URL generation, GCWebhook1/GCWebhook2 communication
- **Algorithm:** HMAC-SHA256
- **Encoding:** Base64 URL-safe
- **Components:** Packed binary data + truncated signature (16 bytes)

### AES-256 Encryption
- **Used by:** GCWebhook1 → GCWebhook2 payload encryption
- **Mode:** CBC
- **Key:** Derived from `SUCCESS_URL_SIGNING_KEY`
- **IV:** Random 16 bytes prepended to ciphertext

---

## Database Operations

### Payment Flow Database Updates

#### np-webhook
- **Table:** `client_table`
- **Operation:** UPDATE
- **Fields:** `payment_id`, `nowpayments_outcome_usd`
- **Condition:** `WHERE order_id = ?`

#### GCWebhook1
- **Table:** `private_channel_users_database`
- **Operation:** INSERT or UPDATE
- **Fields:** `user_id`, `private_channel_id`, `sub_time`, `sub_price`, `expire_time`, `expire_date`, `is_active`

#### GCNotificationService
- **Table:** `client_table`
- **Operation:** SELECT
- **Query:** Get `notification_status`, `notification_id` by `open_channel_id`

### Broadcast Flow Database Updates

#### GCBroadcastService/Scheduler
- **Table:** `broadcast_manager`
- **Operations:**
  - SELECT: Fetch due broadcasts
  - UPDATE: Update `last_sent_time`, `next_send_time`, `broadcast_status`
  - UPDATE: Increment `total_broadcasts`, `successful_broadcasts`, `failed_broadcasts`
  - UPDATE: Update `consecutive_failures`, `last_error_time`, `last_error_message`

---

## Error Handling

### HTTP Status Codes
- **200** - Success
- **400** - Bad request (missing fields, invalid data)
- **401** - Unauthorized (invalid/missing JWT)
- **403** - Forbidden (user doesn't own resource)
- **404** - Not found (broadcast/payment not found)
- **429** - Too many requests (rate limited)
- **500** - Internal server error
- **503** - Service unavailable

### Retry Patterns
- **Cloud Tasks:** Automatic retry with exponential backoff
- **Telegram API:** Manual retry with exponential backoff (broadcast executor)
- **HTTP Requests:** Timeout 10-30 seconds, no automatic retry

---

## CORS Configuration

### GCBroadcastService/Scheduler
```python
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://www.paygateprime.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "max_age": 3600
    }
})
```

### np-webhook
```python
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://storage.googleapis.com",  # Backward compatibility
            "https://www.paygateprime.com",
            "http://localhost:3000"
        ],
        "methods": ["GET", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})
```

---

## Cloud Tasks Queues

### gcwebhook1-queue
- **Target:** GCWebhook1-10-26
- **Triggered by:** np-webhook-10-26
- **Payload:** Validated payment data

### gcwebhook2-queue
- **Target:** GCWebhook2-10-26
- **Triggered by:** GCWebhook1-10-26
- **Payload:** Encrypted user and channel data

### gcsplit1-queue
- **Target:** GCSplit1-10-26 (payment split service)
- **Triggered by:** GCWebhook1-10-26
- **Payload:** Payment split data

---

## Environment Variables / Secrets

### Common Secrets
- `TELEGRAM_BOT_SECRET_NAME` - Bot token
- `DATABASE_HOST_SECRET` - Database instance connection name
- `DATABASE_NAME_SECRET` - Database name
- `DATABASE_USER_SECRET` - Database user
- `DATABASE_PASSWORD_SECRET` - Database password

### Payment Secrets
- `PAYMENT_PROVIDER_SECRET_NAME` - NowPayments API key
- `NOWPAYMENTS_IPN_SECRET` - IPN signature verification secret
- `NOWPAYMENTS_IPN_CALLBACK_URL` - IPN callback URL
- `SUCCESS_URL_SIGNING_KEY` - Success URL signing key

### Broadcast Secrets
- `JWT_SECRET_KEY` - JWT signing secret
- `BROADCAST_AUTO_INTERVAL` - Auto broadcast interval (seconds)
- `BROADCAST_MANUAL_INTERVAL` - Manual broadcast rate limit (seconds)

### Service URLs
- `GCWEBHOOK1_URL` - GCWebhook1 service URL
- `GCWEBHOOK2_URL` - GCWebhook2 service URL
- `GCNOTIFICATIONSERVICE_URL` - GCNotificationService URL
- `WEBHOOK_BASE_URL` - Base URL for webhooks

---

## Architecture Patterns

### Microservices Communication
- **Synchronous:** HTTP POST/GET for immediate operations
- **Asynchronous:** Cloud Tasks for durable, retryable operations
- **Event-Driven:** IPN callbacks trigger payment processing chain

### Security Layers
1. **Network:** Cloud Run ingress controls
2. **Authentication:** JWT tokens, HMAC signatures
3. **Authorization:** Client ID verification, resource ownership checks
4. **Rate Limiting:** Per-endpoint request throttling

### Database Access
- **Connection:** Cloud SQL Connector (automatic IAM auth)
- **Pooling:** SQLAlchemy connection pooling
- **Pattern:** Single source of truth (DatabaseManager)
- **Transactions:** Implicit via SQLAlchemy engine execution

### Deployment Pattern
- **Platform:** Google Cloud Run (serverless containers)
- **Scaling:** Automatic based on request load
- **Health Checks:** `/health` endpoint for liveness probes
- **Secrets:** Google Secret Manager with environment variable mounting

---

## Complete Payment + Notification Flow

```
1. User initiates subscription
   ↓
2. TelePay creates NowPayments invoice
   ↓
3. User pays with crypto
   ↓
4. NowPayments sends IPN to np-webhook
   ↓
5. np-webhook verifies signature
   ↓
6. np-webhook updates database (payment_id)
   ↓
7. np-webhook triggers GCNotificationService (HTTP POST)
   ↓
8. GCNotificationService sends notification to channel owner
   ↓
9. np-webhook enqueues to GCWebhook1 (Cloud Tasks)
   ↓
10. GCWebhook1 records subscription in database
   ↓
11. GCWebhook1 enqueues to GCWebhook2 (Cloud Tasks)
   ↓
12. GCWebhook2 generates invite link
   ↓
13. GCWebhook2 sends invite to user
   ↓
14. User joins closed channel
```

---

## Complete Broadcast Flow

### Automated (Daily)
```
1. Cloud Scheduler triggers GCBroadcastScheduler
   ↓
2. GCBroadcastScheduler fetches due broadcasts
   ↓
3. BroadcastExecutor sends messages via Telegram API
   ↓
4. BroadcastTracker updates statistics in database
   ↓
5. BroadcastScheduler calculates next send time
```

### Manual (User-Triggered)
```
1. User clicks "Send Now" on dashboard
   ↓
2. Website sends JWT-authenticated request to GCBroadcastService
   ↓
3. GCBroadcastService verifies JWT and ownership
   ↓
4. GCBroadcastService checks rate limit
   ↓
5. BroadcastScheduler queues broadcast for immediate execution
   ↓
6. BroadcastExecutor sends message via Telegram API
   ↓
7. BroadcastTracker updates statistics
   ↓
8. Response returned to website with status
```

---

## Key Architectural Decisions

### Why GCNotificationService is Separate
- **Scalability:** Decouples notification logic from payment processing
- **Reliability:** Independent retry and failure handling
- **Maintainability:** Single responsibility principle
- **Reusability:** Can be called from multiple services

### Why Use Cloud Tasks
- **Durability:** Guaranteed delivery with automatic retries
- **Decoupling:** Services don't need to know about each other directly
- **Reliability:** Survives service restarts and failures
- **Observability:** Built-in logging and monitoring

### Why JWT for Broadcast API
- **Stateless:** No session storage required
- **Secure:** Cryptographically signed tokens
- **Standard:** Industry-standard authentication
- **Cross-Origin:** Works seamlessly with CORS

### Why HMAC for IPN
- **Security:** Verifies request authenticity from NowPayments
- **Integrity:** Prevents tampering with payment data
- **Standard:** Industry-standard webhook verification

---

## Monitoring & Observability

### Health Checks
All services expose `/health` endpoint for:
- Cloud Run liveness probes
- Uptime monitoring
- Service discovery

### Logging Standards
- **Format:** Structured logging with emojis for visual parsing
- **Levels:** INFO (normal), WARNING (recoverable), ERROR (critical)
- **Context:** Request ID, user ID, channel ID, payment ID

### Metrics to Monitor
- IPN callback success rate
- Payment processing latency
- Notification delivery rate
- Broadcast send success rate
- API request rate and errors
- Database query performance

---

## Future Enhancements

### Planned Improvements
1. **Webhook Retry Logic:** Implement exponential backoff for failed HTTP calls
2. **Dead Letter Queue:** Handle permanently failed tasks
3. **Circuit Breaker:** Protect against cascading failures
4. **Metrics Dashboard:** Real-time monitoring and alerting
5. **API Versioning:** Support multiple API versions
6. **Idempotency Keys:** Prevent duplicate processing
7. **Event Sourcing:** Audit trail of all state changes

---

## Conclusion

The webhook architecture implements a robust, scalable, and secure communication pattern between microservices. Each service has a clear responsibility and communicates through well-defined HTTP endpoints, with Cloud Tasks providing asynchronous, durable messaging for critical operations.

The separation of concerns allows for independent scaling, deployment, and maintenance of each service while maintaining a cohesive user experience across the entire payment and notification workflow.
