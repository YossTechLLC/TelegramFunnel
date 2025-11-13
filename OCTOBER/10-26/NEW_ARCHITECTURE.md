# TelePay New Centralized Architecture

**Date:** 2025-11-13
**Status:** PROPOSED - NOT YET IMPLEMENTED
**Purpose:** Architectural analysis after removing GCBotCommand, GCDonationHandler, and GCPaymentGateway

---

## Executive Summary

After removing the redundant microservices (GCBotCommand-10-26, GCDonationHandler-10-26, GCPaymentGateway-10-26), the architecture now centers around **TelePay10-26** running locally on a VM. This service owns all core business logic:

- ✅ Payment gateway generation (NowPayments integration)
- ✅ Donation handling (keypad input, payment flow)
- ✅ Bot command processing (Telegram Bot API)
- ✅ Webhook URL generation with HMAC signatures
- ✅ Notification orchestration
- ✅ Subscription management
- ✅ Broadcast coordination

The remaining **Cloud Run services** act as lightweight webhook receivers that forward requests to TelePay10-26's local endpoints.

---

## Architecture Overview

### 1. Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    TelePay10-26 (Local VM)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ telepay10-26.py (Main Orchestrator)                       │  │
│  │  • Bot Manager (Telegram Bot API)                         │  │
│  │  • Subscription Monitor (expiration checking)             │  │
│  │  • Flask Server (notification endpoint)                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Payment Gateway  │  │ Donation Handler │  │ Notification │  │
│  │                  │  │                  │  │   Service    │  │
│  │ • NowPayments    │  │ • Keypad UI      │  │ • Channel    │  │
│  │ • Invoice Gen    │  │ • Amount Valid   │  │   Notify     │  │
│  │ • Order Tracking │  │ • Payment Trigger│  │ • Payment    │  │
│  └──────────────────┘  └──────────────────┘  │   Alerts     │  │
│                                                └──────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Webhook Manager  │  │ Broadcast Mgr    │  │  Database    │  │
│  │                  │  │                  │  │   Manager    │  │
│  │ • HMAC Signing   │  │ • Message Queue  │  │ • Cloud SQL  │  │
│  │ • URL Generation │  │ • Scheduling     │  │ • Queries    │  │
│  │ • Token Verify   │  │ • Delivery Track │  │ • Connection │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                   │
│  Flask Server (Port 5000+):                                      │
│   • POST /send-notification - Receive notification requests     │
│   • GET  /health            - Health check                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Cloud Webhook Services (Lightweight Forwarders)

```
┌─────────────────────────────────────────────────────────────────┐
│                Cloud Run Services (us-central1)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ GCNotificationService-10-26                               │  │
│  │  Webhook: POST /send-notification                         │  │
│  │                                                            │  │
│  │  Receives: Payment notifications from external services   │  │
│  │  Sends to: TelePay10-26 Flask endpoint                    │  │
│  │  Database: Queries telepaypsql for channel owner info     │  │
│  │  Telegram: Sends notifications via Bot API                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ GCBroadcastService-10-26                                  │  │
│  │  Webhooks: POST /api/broadcasts/*                         │  │
│  │            GET  /api/broadcasts/status                    │  │
│  │                                                            │  │
│  │  Features: JWT authentication, CORS for web UI            │  │
│  │  Purpose: Manage scheduled/manual broadcasts              │  │
│  │  Database: Queries broadcast_manager table                │  │
│  │  Telegram: Sends broadcast messages via Bot API           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ GCSubscriptionMonitor-10-26                               │  │
│  │  Scheduled: Cloud Scheduler (cron job)                    │  │
│  │                                                            │  │
│  │  Features: Expiration checking, reminder notifications    │  │
│  │  Database: Queries subscription expiration records        │  │
│  │  Telegram: Sends expiration warnings via Bot API          │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3. External Integrations

```
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────┐ │
│  │ Telegram Bot API  │  │  NowPayments API  │  │  Cloud SQL  │ │
│  │                   │  │                   │  │             │ │
│  │ • Webhook Updates │  │ • Invoice Create  │  │ • telepay   │ │
│  │ • Send Messages   │  │ • Payment Track   │  │   psql      │ │
│  │ • Bot Commands    │  │ • IPN Callbacks   │  │ • Client    │ │
│  └───────────────────┘  └───────────────────┘  │   Data      │ │
│                                                  └─────────────┘ │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────┐ │
│  │ Google Secret Mgr │  │ Cloud Scheduler   │  │ Web UI      │ │
│  │                   │  │                   │  │             │ │
│  │ • Bot Token       │  │ • Subscription    │  │ • Dashboard │ │
│  │ • Database Creds  │  │   Monitor Cron    │  │ • Broadcast │ │
│  │ • API Keys        │  │ • Broadcast Cron  │  │   Controls  │ │
│  └───────────────────┘  └───────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### Flow 1: User Subscribes to Channel (Centralized)

```
┌───────┐                  ┌────────────────┐                ┌──────────────┐
│ User  │                  │ TelePay10-26   │                │ NowPayments  │
│       │                  │   (Local VM)   │                │     API      │
└───┬───┘                  └───────┬────────┘                └──────┬───────┘
    │                              │                                │
    │  1. /start command           │                                │
    │─────────────────────────────>│                                │
    │                              │                                │
    │  2. Channel list (keyboard)  │                                │
    │<─────────────────────────────│                                │
    │                              │                                │
    │  3. Click channel button     │                                │
    │─────────────────────────────>│                                │
    │                              │                                │
    │  4. Tier selection keyboard  │                                │
    │<─────────────────────────────│                                │
    │                              │                                │
    │  5. Select tier (e.g., $9.99)│                                │
    │─────────────────────────────>│                                │
    │                              │                                │
    │                              │  6. Create invoice             │
    │                              │   (order_id: PGP-{user}|{ch})  │
    │                              │───────────────────────────────>│
    │                              │                                │
    │                              │  7. Invoice URL + invoice_id   │
    │                              │<───────────────────────────────│
    │                              │                                │
    │  8. WebApp payment button    │                                │
    │     (NowPayments gateway)    │                                │
    │<─────────────────────────────│                                │
    │                              │                                │
    │  9. Complete payment         │                                │
    │─────────────────────────────────────────────────────────────>│
    │                              │                                │
    │  10. Success redirect        │                                │
    │     (signed webhook URL)     │                                │
    │<─────────────────────────────────────────────────────────────│
```

### Flow 2: User Makes Donation (Centralized)

```
┌───────┐                  ┌────────────────┐                ┌──────────────┐
│ User  │                  │ TelePay10-26   │                │ NowPayments  │
│       │                  │   (Local VM)   │                │     API      │
└───┬───┘                  └───────┬────────┘                └──────┬───────┘
    │                              │                                │
    │  1. Click [💝 Donate] in     │                                │
    │     closed channel           │                                │
    │─────────────────────────────>│                                │
    │                              │                                │
    │  2. Numeric keypad appears   │                                │
    │     (donation_input_handler) │                                │
    │<─────────────────────────────│                                │
    │                              │                                │
    │  3. Enter amount via keypad  │                                │
    │     (e.g., 5, 0, ., 0, 0)    │                                │
    │─────────────────────────────>│                                │
    │                              │                                │
    │  4. Click [✅ Confirm & Pay] │                                │
    │─────────────────────────────>│                                │
    │                              │                                │
    │  5. Validation (min $4.99)   │                                │
    │     Delete keypad message    │                                │
    │     Send confirmation        │                                │
    │<─────────────────────────────│                                │
    │                              │                                │
    │                              │  6. Create invoice             │
    │                              │   (order_id: PGP-{user}|{ch})  │
    │                              │───────────────────────────────>│
    │                              │                                │
    │                              │  7. Invoice URL                │
    │                              │<───────────────────────────────│
    │                              │                                │
    │  8. WebApp payment button    │                                │
    │     sent to PRIVATE CHAT     │                                │
    │<─────────────────────────────│                                │
    │                              │                                │
    │  9. Complete payment         │                                │
    │─────────────────────────────────────────────────────────────>│
```

### Flow 3: Payment Notification (Webhook Chain)

```
┌──────────────┐    ┌───────────────────┐    ┌────────────────┐
│ NowPayments  │    │ GCNotification    │    │ TelePay10-26   │
│     IPN      │    │  Service-10-26    │    │   (Local VM)   │
│  (Webhook)   │    │   (Cloud Run)     │    │  Flask Server  │
└──────┬───────┘    └─────────┬─────────┘    └───────┬────────┘
       │                      │                       │
       │  1. POST /ipn        │                       │
       │  {payment_id, ...}   │                       │
       │─────────────────────>│                       │
       │                      │                       │
       │                      │  2. Query DB for      │
       │                      │     channel owner     │
       │                      │     (open_channel_id) │
       │                      │                       │
       │                      │  3. POST /send-notif  │
       │                      │  {open_channel_id,    │
       │                      │   payment_type,       │
       │                      │   payment_data}       │
       │                      │──────────────────────>│
       │                      │                       │
       │                      │  4. Send Telegram     │
       │                      │     notification      │
       │                      │     to channel owner  │
       │                      │                       │
       │                      │  5. 200 OK            │
       │                      │<──────────────────────│
       │                      │                       │
       │  6. 200 OK           │                       │
       │<─────────────────────│                       │
```

### Flow 4: Broadcast Message Distribution

```
┌─────────────┐    ┌──────────────────┐    ┌────────────────┐
│  Web UI     │    │ GCBroadcast      │    │ TelePay10-26   │
│ Dashboard   │    │  Service-10-26   │    │   (Local VM)   │
└──────┬──────┘    └────────┬─────────┘    └───────┬────────┘
       │                    │                       │
       │  1. POST /api/     │                       │
       │     broadcasts     │                       │
       │  {message, tier,   │                       │
       │   schedule}        │                       │
       │  [JWT token]       │                       │
       │───────────────────>│                       │
       │                    │                       │
       │                    │  2. Validate JWT      │
       │                    │     Query DB for      │
       │                    │     eligible users    │
       │                    │     (tier filter)     │
       │                    │                       │
       │                    │  3. Store in          │
       │                    │     broadcast_manager │
       │                    │     table             │
       │                    │                       │
       │                    │  [Cloud Scheduler     │
       │                    │   triggers at time]   │
       │                    │                       │
       │                    │  4. Fetch due         │
       │                    │     broadcasts        │
       │                    │                       │
       │                    │  5. Send messages     │
       │                    │     via Telegram API  │
       │                    │     (batch)           │
       │                    │                       │
       │                    │  6. Update status     │
       │                    │     in DB             │
       │                    │                       │
       │  7. 200 OK         │                       │
       │<───────────────────│                       │
```

---

## Security Analysis

### 1. Webhook Security (Current Implementation)

**TelePay10-26 Webhook URL Generation:**
```python
# secure_webhook.py - HMAC-signed URLs with timestamped tokens

def build_signed_success_url(...) -> str:
    """
    Creates cryptographically signed success URL for post-payment redirect

    Security Features:
    1. HMAC-SHA256 signature (16-byte truncated)
    2. Base64 URL-safe encoding
    3. Packed binary format (6+6+2+2+variable bytes)
    4. Timestamp-based expiration (minutes since epoch)
    5. Signed with SECRET_KEY from Secret Manager

    Token Structure:
    - User ID (6 bytes, 48-bit)
    - Channel ID (6 bytes, 48-bit)
    - Timestamp (2 bytes, modulo 65536 minutes)
    - Subscription time (2 bytes, 1-999 days)
    - Variable length strings (wallet, currency, network, price)
    - HMAC signature (16 bytes)
    """

    # Example: PGP-6271402111|-1003268562225
    order_id = f"PGP-{user_id}|{open_channel_id}"

    # Create signed token
    packed = user_id_bytes + channel_id_bytes + timestamp + ...
    signature = hmac.new(signing_key, packed, hashlib.sha256).digest()[:16]
    token = base64.urlsafe_b64encode(packed + signature)

    return f"{webhook_base_url}?token={token}"
```

**Security Strengths:**
- ✅ HMAC prevents tampering (attacker can't forge valid tokens)
- ✅ Timestamp limits replay attacks (tokens expire after ~45 days)
- ✅ Compact binary format reduces URL length (avoids NowPayments URL limits)
- ✅ Secret key stored in Google Secret Manager (not hardcoded)

**Security Weaknesses:**
- ⚠️ No explicit expiration validation on webhook receiver side
- ⚠️ Truncated HMAC (16 bytes instead of 32) reduces brute-force resistance
- ⚠️ Timestamp uses modulo arithmetic (wraps after 45 days)

### 2. Flask Webhook Endpoints (TelePay10-26)

**Current Implementation:**
```python
# server_manager.py

@flask_app.route('/send-notification', methods=['POST'])
def handle_notification_request():
    """
    Security Issues:
    ❌ No authentication (anyone can POST if they know the URL)
    ❌ No rate limiting (vulnerable to DoS)
    ❌ No request signing verification
    ❌ No IP whitelist (should only accept from Cloud Run services)
    """
    data = request.get_json()
    # ... process notification
```

**Recommended Improvements (from Flask best practices):**

```python
import hmac
import hashlib
from flask import Flask, request, jsonify, abort
from functools import wraps

# 1. Add HMAC request signing
def verify_signature(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get('X-Signature')
        if not signature:
            abort(401, "Missing signature")

        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            request.get_data(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            abort(403, "Invalid signature")

        return f(*args, **kwargs)
    return decorated_function

# 2. Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

# 3. Add IP whitelist
ALLOWED_IPS = [
    '10.0.0.0/8',  # Cloud Run internal IPs
    # Add specific Cloud Run egress IPs
]

def check_ip_whitelist():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip not in ALLOWED_IPS:
        abort(403, "Unauthorized IP")

# 4. Apply to endpoint
@app.route('/send-notification', methods=['POST'])
@verify_signature
def handle_notification_request():
    check_ip_whitelist()
    # ... process notification
```

### 3. Cloud Run Service Security

**GCNotificationService-10-26:**
```python
# Current Implementation - Good practices already in place:
✅ Request validation (required fields)
✅ JSON-only content type enforcement
✅ Error handling with appropriate HTTP status codes
✅ Logging of all operations

# Improvements from best practices:
❌ Missing CSRF protection (if exposed to web)
❌ No rate limiting per client
❌ No request size limits
```

**GCBroadcastService-10-26:**
```python
# Current Implementation:
✅ JWT authentication (flask-jwt-extended)
✅ CORS configured for specific origin (www.paygateprime.com)
✅ Error handlers for expired/invalid tokens

# Already follows best practices:
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
```

---

## Integration Patterns

### Pattern 1: Cloud-to-Local Webhook Forwarding

**Use Case:** Cloud Run service receives webhook, forwards to local TelePay10-26

**Implementation:**
```python
# GCNotificationService-10-26 (Cloud Run)
@app.route('/send-notification', methods=['POST'])
def send_notification():
    # 1. Validate incoming webhook from NowPayments/external service
    data = request.get_json()
    validate_required_fields(data)

    # 2. Query database for enrichment
    channel_owner = db.get_channel_owner(data['open_channel_id'])

    # 3. Forward to TelePay10-26 local endpoint
    response = requests.post(
        f"{TELEPAY_LOCAL_URL}/send-notification",
        json={
            'open_channel_id': data['open_channel_id'],
            'payment_type': data['payment_type'],
            'payment_data': data['payment_data']
        },
        headers={'X-Signature': sign_request(data)},
        timeout=10
    )

    return jsonify({'status': 'success'}), 200
```

**Considerations:**
- ⚠️ Local VM must have public IP or Cloud VPN
- ⚠️ Network latency (Cloud Run → Local VM)
- ⚠️ Firewall rules (allow Cloud Run egress IPs)

**Alternative: Use Google Pub/Sub for async communication:**
```python
# Cloud Run publishes to Pub/Sub topic
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, 'telepay-notifications')
publisher.publish(topic_path, json.dumps(data).encode())

# TelePay10-26 subscribes to Pub/Sub
subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT_ID, 'telepay-sub')
subscriber.subscribe(subscription_path, callback=handle_notification)
```

### Pattern 2: Telegram Bot Webhook Setup

**From python-telegram-bot best practices:**

```python
# TelePay10-26 - Recommended webhook setup

from telegram.ext import Application

# Option A: Polling (Simple, good for development)
app = Application.builder().token(BOT_TOKEN).build()
app.run_polling()

# Option B: Webhook (Production, more efficient)
app = Application.builder().token(BOT_TOKEN).build()
app.run_webhook(
    listen='0.0.0.0',
    port=8443,
    secret_token='RANDOM_SECRET_TOKEN',  # Validates requests from Telegram
    webhook_url='https://your-vm-domain.com:8443',
    cert='cert.pem',  # Self-signed cert (or use reverse proxy with Let's Encrypt)
    key='private.key'
)
```

**Current Implementation Analysis:**
```python
# telepay10-26.py uses POLLING (not webhooks)
async def run_application(app):
    bot_task = asyncio.create_task(app.run_bot())
    subscription_task = asyncio.create_task(app.subscription_manager.start_monitoring())
    await asyncio.gather(bot_task, subscription_task)
```

**Recommendation:**
- ✅ Keep polling for local development (simpler, no SSL setup)
- ✅ Add webhook option for production (faster, more scalable)
- ⚠️ If using webhook, use reverse proxy (Nginx/Caddy) for SSL termination

### Pattern 3: Database Connection Pooling

**Current Implementation:**
```python
# database.py - Likely creates new connection per query
class DatabaseManager:
    def __init__(self, host, dbname, user, password):
        self.host = host
        # ... connection setup
```

**Best Practice (from Flask + Cloud SQL):**
```python
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine, pool

# Initialize Cloud SQL connector with connection pooling
connector = Connector()

def getconn():
    conn = connector.connect(
        "telepay-459221:us-central1:telepaypsql",
        "pg8000",
        user="postgres",
        db="telepaydb",
        enable_iam_auth=False  # Use Secret Manager password
    )
    return conn

# Create engine with connection pool
engine = create_engine(
    "postgresql+pg8000://",
    creator=getconn,
    poolclass=pool.QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections after 30 minutes
)
```

---

## Deployment Architecture

### 1. Current State (After Removal)

```
┌──────────────────────────────────────────────────────────────┐
│                     Google Cloud (telepay-459221)            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Cloud Run Services:                                         │
│   • gcbroadcastservice-10-26    (Port 8080, JWT auth)       │
│   • gcnotificationservice-10-26 (Port 8080, webhook)        │
│   • gcsubscriptionmonitor-10-26 (Cron-triggered)            │
│                                                               │
│  Cloud SQL:                                                  │
│   • telepaypsql (PostgreSQL 14)                             │
│     - Connection name: telepay-459221:us-central1:telepaypsql│
│     - Private IP: 10.x.x.x                                   │
│                                                               │
│  Secret Manager:                                             │
│   • TELEGRAM_BOT_SECRET_NAME                                 │
│   • DATABASE_HOST_SECRET                                     │
│   • DATABASE_NAME_SECRET                                     │
│   • DATABASE_USER_SECRET                                     │
│   • DATABASE_PASSWORD_SECRET                                 │
│   • NOWPAYMENTS_API_KEY                                      │
│   • NOWPAYMENTS_IPN_CALLBACK_URL                             │
│   • SUCCESS_URL_SIGNING_KEY                                  │
│   • WEBHOOK_BASE_URL                                         │
│                                                               │
│  Cloud Scheduler:                                            │
│   • subscription-monitor-cron (daily)                        │
│   • broadcast-scheduler-cron (as needed)                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    Local VM / On-Premises                     │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  TelePay10-26:                                               │
│   • telepay10-26.py         (Main orchestrator)             │
│   • Flask server            (Port 5000+)                     │
│   • Telegram bot polling    (python-telegram-bot)           │
│                                                               │
│  Network Requirements:                                       │
│   • Public IP or Cloud VPN                                  │
│   • Firewall: Allow inbound on Flask port (5000)            │
│   • Firewall: Allow outbound to Cloud SQL (3306)            │
│   • Firewall: Allow outbound to Telegram API (443)          │
└──────────────────────────────────────────────────────────────┘
```

### 2. Network Configuration

**Cloud SQL Connection:**
```bash
# TelePay10-26 connects to Cloud SQL via public IP
# Uses Secret Manager for credentials

# Option A: Public IP with SSL (current)
HOST=34.x.x.x
PORT=5432
SSL_MODE=require

# Option B: Cloud SQL Proxy (recommended)
./cloud-sql-proxy telepay-459221:us-central1:telepaypsql \
    --port 5432 \
    --credentials-file=/path/to/service-account-key.json
```

**Cloud Run → Local VM Communication:**
```bash
# Option A: Public IP with firewall rules
TELEPAY_LOCAL_URL=http://<VM_PUBLIC_IP>:5000

# Firewall rule:
gcloud compute firewall-rules create allow-cloud-run-to-vm \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:5000 \
    --source-ranges=<CLOUD_RUN_EGRESS_IP_RANGE>

# Option B: Cloud VPN (more secure)
# Set up Cloud VPN tunnel between Cloud Run VPC and on-prem network
```

### 3. Recommended Deployment Flow

```bash
# 1. Deploy Cloud Run Services
cd GCBroadcastService-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcbroadcastservice-10-26
gcloud run deploy gcbroadcastservice-10-26 \
    --image gcr.io/telepay-459221/gcbroadcastservice-10-26 \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql

cd ../GCNotificationService-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcnotificationservice-10-26
gcloud run deploy gcnotificationservice-10-26 \
    --image gcr.io/telepay-459221/gcnotificationservice-10-26 \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql

cd ../GCSubscriptionMonitor-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcsubscriptionmonitor-10-26
gcloud run deploy gcsubscriptionmonitor-10-26 \
    --image gcr.io/telepay-459221/gcsubscriptionmonitor-10-26 \
    --region us-central1 \
    --platform managed \
    --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql

# 2. Configure Cloud Scheduler
gcloud scheduler jobs create http subscription-monitor-daily \
    --schedule="0 0 * * *" \
    --uri="https://gcsubscriptionmonitor-10-26-291176869049.us-central1.run.app/monitor" \
    --http-method=POST \
    --location=us-central1

# 3. Start TelePay10-26 on local VM
cd TelePay10-26
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python telepay10-26.py

# 4. Configure systemd service for auto-start
sudo tee /etc/systemd/system/telepay.service > /dev/null <<EOF
[Unit]
Description=TelePay10-26 Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/TelePay10-26
Environment="PATH=/path/to/TelePay10-26/venv/bin"
ExecStart=/path/to/TelePay10-26/venv/bin/python telepay10-26.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable telepay
sudo systemctl start telepay
```

---

## Benefits of Centralized Architecture

### Advantages ✅

1. **Single Source of Truth**
   - All core logic (payment, donations, commands) in one place
   - Easier to reason about data flow
   - No cross-service synchronization issues

2. **Simplified Payment Flow**
   - Payment gateway generation happens in TelePay10-26
   - No need to coordinate between GCDonationHandler and GCPaymentGateway
   - Direct NowPayments integration

3. **Reduced Deployment Complexity**
   - Fewer Cloud Run services to manage (3 instead of 6)
   - Less infrastructure cost (fewer container instances)
   - Faster iteration (no Docker rebuilds for core logic changes)

4. **Improved Debugging**
   - All bot interactions logged in one place
   - No distributed tracing needed for bot commands
   - Easier to reproduce issues locally

5. **Direct Database Access**
   - TelePay10-26 has full database access
   - No need for REST API calls between services
   - Faster query performance (local queries)

### Challenges ⚠️

1. **Single Point of Failure**
   - If VM goes down, entire bot is offline
   - Mitigation: Use systemd auto-restart, VM health monitoring

2. **Scalability Limits**
   - Single VM has finite resources
   - High traffic may overwhelm local bot
   - Mitigation: Cloud Run services can scale independently

3. **Network Dependency**
   - Cloud Run services must reach local VM
   - Requires public IP or VPN setup
   - Latency between Cloud Run → VM

4. **Deployment Friction**
   - Local VM updates require manual deployment
   - No Docker-based rollback
   - Mitigation: Use git branches, automated deployment scripts

5. **State Management**
   - Flask server must handle concurrent requests safely
   - Need proper connection pooling for database
   - Asyncio + Flask integration requires care

---

## Security Recommendations

### Critical (Implement Immediately)

1. **Add HMAC request signing to TelePay10-26 Flask endpoints**
   - Verify requests from Cloud Run services are legitimate
   - Use shared secret stored in Secret Manager

2. **Implement IP whitelist on Flask server**
   - Only accept requests from Cloud Run egress IPs
   - Reject all other traffic

3. **Add rate limiting to `/send-notification` endpoint**
   - Prevent DoS attacks
   - Use Flask-Limiter library

4. **Use HTTPS for Flask server**
   - Set up reverse proxy (Nginx/Caddy) with Let's Encrypt
   - Terminate SSL at proxy, forward to Flask

### High Priority

5. **Add JWT authentication between services**
   - Cloud Run services send JWT token
   - TelePay10-26 validates token

6. **Implement request logging with correlation IDs**
   - Trace requests across service boundaries
   - Use Google Cloud Logging

7. **Add health check endpoint to TelePay10-26**
   - Cloud Scheduler can monitor VM availability
   - Alert on failures

8. **Set up Cloud Armor for Cloud Run services**
   - DDoS protection
   - WAF rules for common attacks

### Medium Priority

9. **Use Cloud SQL IAM authentication**
   - Eliminate password-based auth
   - Rotate credentials automatically

10. **Implement secret rotation for bot token**
    - Use Secret Manager versioning
    - Graceful restart on rotation

11. **Add audit logging for all payment operations**
    - Log to Cloud Logging
    - Set up alerts for anomalies

---

## Alternative Architectures Considered

### Option A: Keep All Microservices (Rejected)

**Why Rejected:**
- ❌ Overcomplicated for bot use case
- ❌ High maintenance overhead (6+ services)
- ❌ Network overhead between services
- ❌ Difficult to debug distributed issues

### Option B: Move Everything to Cloud Run (Future)

**Pros:**
- ✅ Fully managed (no VM maintenance)
- ✅ Auto-scaling
- ✅ Built-in logging and monitoring

**Cons:**
- ⚠️ Telegram bot webhook setup more complex
- ⚠️ Cold start latency for bot responses
- ⚠️ Higher cost for always-on bot

**Recommendation:** Consider if bot traffic grows significantly

### Option C: Hybrid with Cloud Functions (Future)

**Use Case:** Replace Cloud Run services with Cloud Functions

**Pros:**
- ✅ Lower cost (pay per invocation)
- ✅ Simpler deployment

**Cons:**
- ⚠️ Cold start latency
- ⚠️ Max execution time (9 minutes)

---

## Migration Checklist

### Phase 1: Validate Current State ✅

- [x] Confirm GCBotCommand-10-26 removed
- [x] Confirm GCDonationHandler-10-26 removed
- [x] Confirm GCPaymentGateway-10-26 removed
- [x] Verify TelePay10-26 has all required modules
- [ ] Test payment flow end-to-end
- [ ] Test donation flow end-to-end
- [ ] Test notification delivery
- [ ] Test broadcast delivery

### Phase 2: Security Hardening 🔒

- [ ] Add HMAC signing to Flask endpoints
- [ ] Implement IP whitelist
- [ ] Add rate limiting
- [ ] Set up HTTPS with reverse proxy
- [ ] Implement JWT authentication
- [ ] Add request logging with correlation IDs

### Phase 3: Infrastructure Updates 🏗️

- [ ] Set up systemd service for auto-restart
- [ ] Configure Cloud VPN (or finalize public IP setup)
- [ ] Set up firewall rules
- [ ] Configure Cloud SQL connection pooling
- [ ] Set up health monitoring and alerting

### Phase 4: Documentation & Monitoring 📊

- [ ] Update deployment documentation
- [ ] Create runbook for common issues
- [ ] Set up Cloud Monitoring dashboards
- [ ] Configure alerting policies
- [ ] Document API contracts between services

---

## Next Steps

1. **Review and approve this architecture** with stakeholders
2. **Test current implementation** end-to-end
3. **Implement security hardening** (Phase 2)
4. **Deploy infrastructure updates** (Phase 3)
5. **Monitor and iterate** based on production metrics

---

## Appendix: API Contracts

### TelePay10-26 Flask Server

**Endpoint:** `POST /send-notification`

**Request:**
```json
{
  "open_channel_id": "-1003268562225",
  "payment_type": "subscription",
  "payment_data": {
    "user_id": 6271402111,
    "username": "john_doe",
    "amount_crypto": "0.00034",
    "amount_usd": "9.99",
    "crypto_currency": "ETH",
    "timestamp": "2025-11-13 14:32:15 UTC",
    "tier": 1,
    "tier_price": "9.99",
    "duration_days": 30
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Notification sent"
}
```

**Errors:**
- `400 Bad Request` - Missing required fields
- `503 Service Unavailable` - Notification service not initialized
- `500 Internal Server Error` - Unexpected error

---

### GCNotificationService-10-26

**Endpoint:** `POST /send-notification`

**Request:** Same as TelePay10-26

**Response:** Same as TelePay10-26

**Additional Endpoints:**
- `GET /health` - Health check
- `POST /test-notification` - Send test notification

---

### GCBroadcastService-10-26

**Endpoint:** `POST /api/broadcasts`

**Request:**
```json
{
  "message": "Hello subscribers!",
  "tier": 1,
  "schedule_time": "2025-11-13T15:00:00Z"
}
```

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Response:**
```json
{
  "status": "success",
  "broadcast_id": "abc123",
  "message": "Broadcast scheduled"
}
```

---

## References

- [Python Telegram Bot Documentation](https://docs.python-telegram-bot.org/)
- [Flask Web Security](https://flask.palletsprojects.com/en/latest/security/)
- [Google Cloud Run Best Practices](https://cloud.google.com/run/docs/best-practices)
- [NowPayments API Documentation](https://documenter.getpostman.com/view/7907941/S1a32n38)
- [Google Cloud SQL Connection Pooling](https://cloud.google.com/sql/docs/postgres/manage-connections)

---

**END OF ARCHITECTURE DOCUMENT**
