# Google Cloud Run Security Best Practices for Payment Services
## Comprehensive Guide for PGP_v1 Financial Webhooks

**Last Updated:** 2025-11-18
**Project:** PGP_v1
**Scope:** Securing Cloud Run services handling sensitive financial data (NowPayments IPN, Telegram Bot webhooks)

---

## Table of Contents

1. [Authentication & Authorization](#1-authentication--authorization)
2. [Network Security](#2-network-security)
3. [Defense in Depth Strategy](#3-defense-in-depth-strategy)
4. [Payment Service Specific Security](#4-payment-service-specific-security)
5. [Implementation Checklist](#5-implementation-checklist)
6. [Architecture Recommendations](#6-architecture-recommendations)

---

## 1. Authentication & Authorization

### 1.1 The `--allow-unauthenticated` Flag

#### Security Implications

**CRITICAL RISKS:**
- ⚠️ **Public Exposure**: Anyone on the internet can invoke the service if they know the URL
- ⚠️ **Cost Abuse**: Unauthorized invocations can lead to unexpected cloud costs
- ⚠️ **Attack Surface**: Exposes the service to automated scanning and attacks
- ⚠️ **Compliance Issues**: Violates PCI DSS and financial data protection requirements

**When It's Appropriate:**
- Public-facing web frontends (NOT payment processing)
- Public API endpoints with their own authentication layer (API keys, JWT)
- Static content serving

**When It's NOT Appropriate:**
- ❌ Payment webhook endpoints (NowPayments IPN)
- ❌ Internal service-to-service communication
- ❌ Any service handling financial or sensitive data
- ❌ Administrative or management endpoints

#### Official Documentation
- **Source:** https://cloud.google.com/run/docs/authenticating/public
- **Key Quote:** "For an internal Cloud Run service, an important action to align with the least privilege principle is to disallow unauthenticated access"

---

### 1.2 IAM Authentication for Cloud Run

#### Best Practice: Use `--no-allow-unauthenticated`

**Deployment Command:**
```bash
gcloud run deploy SERVICE_NAME \
  --image=IMAGE_URL \
  --region=REGION \
  --no-allow-unauthenticated \
  --service-account=SERVICE_ACCOUNT_EMAIL
```

#### How IAM Authentication Works

1. **Default Behavior**: Cloud Run performs an IAM check on every request when authentication is enabled
2. **Required Permission**: Callers must have `roles/run.invoker` role
3. **Authentication Token**: Requests must include an OAuth 2.0 bearer token in the `Authorization` header

**Example Request:**
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://SERVICE_URL
```

---

### 1.3 Service-to-Service Authentication

#### Configuration Steps

**1. Grant Invoker Role to Calling Service:**

```bash
# Via gcloud CLI
gcloud run services add-iam-policy-binding RECEIVING_SERVICE \
  --member='serviceAccount:CALLING_SERVICE_IDENTITY@PROJECT.iam.gserviceaccount.com' \
  --role='roles/run.invoker' \
  --region=REGION
```

**2. Obtain Identity Token in Calling Service:**

```python
import google.auth.transport.requests
import google.oauth2.id_token

def get_id_token(target_audience):
    """
    Obtain an ID token for authenticating to a Cloud Run service.

    Args:
        target_audience: The URL of the receiving Cloud Run service
    """
    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, target_audience)
    return token

# Usage in your service
target_service_url = "https://receiving-service-url.run.app"
token = get_id_token(target_service_url)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.post(target_service_url, headers=headers, json=payload)
```

**3. Alternative: Using Metadata Server (within Cloud Run):**

```python
import requests

def get_id_token_from_metadata(audience):
    """
    Fetch identity token from Compute Metadata Server.
    This works within Cloud Run containers.
    """
    metadata_server_url = (
        "http://metadata.google.internal/computeMetadata/v1/"
        "instance/service-accounts/default/identity"
    )
    params = {"audience": audience}
    headers = {"Metadata-Flavor": "Google"}

    response = requests.get(
        metadata_server_url,
        params=params,
        headers=headers
    )
    return response.text
```

#### Official Documentation
- **Source:** https://cloud.google.com/run/docs/authenticating/service-to-service
- **Updated:** October 30, 2025

---

### 1.4 Service Account Best Practices

#### Principle of Least Privilege

**DO:**
- ✅ Create dedicated service accounts for each service
- ✅ Grant only the minimum required permissions
- ✅ Use workload identity for GKE workloads
- ✅ Rotate service account keys regularly (if keys must be used)
- ✅ Use IAM Conditions to further restrict access

**DON'T:**
- ❌ Use default Compute Engine service account (has Editor role)
- ❌ Grant overly broad permissions
- ❌ Share service accounts across multiple services
- ❌ Export service account keys unless absolutely necessary
- ❌ Commit service account keys to version control

#### Example Service Account Setup

```bash
# Create dedicated service account
gcloud iam service-accounts create pgp-webhook-receiver \
  --display-name="PGP Webhook Receiver Service" \
  --project=pgp-live

# Grant minimal permissions
gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-webhook-receiver@pgp-live.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Deploy Cloud Run service with this account
gcloud run deploy pgp-webhook-service \
  --service-account=pgp-webhook-receiver@pgp-live.iam.gserviceaccount.com \
  --no-allow-unauthenticated
```

#### Official Documentation
- **Source:** https://cloud.google.com/iam/docs/best-practices-service-accounts
- **Key Management:** https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys

---

## 2. Network Security

### 2.1 VPC Service Controls

#### What Are VPC Service Controls?

VPC Service Controls create a security perimeter around Google Cloud resources to:
- 🛡️ Prevent data exfiltration
- 🛡️ Restrict API access to authorized networks
- 🛡️ Add an additional layer beyond IAM
- 🛡️ Protect against insider threats and compromised accounts

#### How They Work with Cloud Run

**Key Concepts:**
1. **Service Perimeter**: A virtual boundary around GCP resources
2. **Access Levels**: Define who can access resources (based on IP, device, identity)
3. **VPC Accessible Services**: Control which GCP APIs can be called from within the perimeter

#### Implementation Steps

**1. Create VPC Service Controls Perimeter:**

```bash
# Create access level (IP-based example)
gcloud access-context-manager levels create pgp_production_access \
  --title="PGP Production Access" \
  --basic-level-spec=access_level.yaml \
  --policy=POLICY_ID

# access_level.yaml example:
# conditions:
#   - ipSubnetworks:
#     - "YOUR_OFFICE_IP/32"
#     - "149.154.160.0/20"  # Telegram IPs
#     - "91.108.4.0/22"      # Telegram IPs
```

**2. Create Service Perimeter:**

```bash
gcloud access-context-manager perimeters create pgp_production_perimeter \
  --title="PGP Production Perimeter" \
  --resources=projects/PROJECT_NUMBER \
  --restricted-services=run.googleapis.com,sqladmin.googleapis.com \
  --access-levels=pgp_production_access \
  --policy=POLICY_ID
```

**3. Configure Cloud Run for VPC SC:**

```bash
# Ensure container registry is in the same perimeter
# Deploy with VPC SC enabled
gcloud run deploy SERVICE_NAME \
  --image=IMAGE_URL \
  --vpc-connector=VPC_CONNECTOR_NAME \
  --region=REGION
```

#### Important Limitations

⚠️ **Cloud Run Specific Constraints:**
- Container registry must be in the same VPC SC perimeter
- Continuous deployment features are NOT available within VPC SC
- Cloud Scheduler cannot trigger jobs inside VPC SC perimeter directly (requires proxy)
- Ingress policy rules using IAM principals are NOT supported

#### VPC SC + Cloud Scheduler Workaround

```
┌──────────────────┐         ┌─────────────────┐         ┌──────────────┐
│ Cloud Scheduler  │────────>│ Proxy Cloud Run │────────>│ Target Job   │
│ (Outside VPC SC) │         │ (In VPC SC)     │         │ (In VPC SC)  │
└──────────────────┘         └─────────────────┘         └──────────────┘
```

#### Official Documentation
- **Source:** https://cloud.google.com/run/docs/securing/using-vpc-service-controls
- **Overview:** https://cloud.google.com/vpc-service-controls/docs/overview
- **Updated:** October 24, 2025

---

### 2.2 Cloud Armor

#### What Is Cloud Armor?

Google Cloud Armor provides:
- 🛡️ **DDoS Protection**: Advanced network and application-layer DDoS defense
- 🛡️ **WAF (Web Application Firewall)**: Protection against OWASP Top 10 attacks
- 🛡️ **Bot Management**: Detect and mitigate bot traffic
- 🛡️ **Rate Limiting**: Control request rates per IP or user
- 🛡️ **Geo-Blocking**: Restrict traffic by geographic location

#### Architecture with Cloud Run

**IMPORTANT**: Cloud Armor cannot be directly attached to Cloud Run. You MUST use a Load Balancer.

```
                                 ┌─────────────────┐
Internet ────────────────────────>│   Cloud Armor   │
                                 │  Security Policy│
                                 └────────┬────────┘
                                          │
                                 ┌────────▼────────┐
                                 │  Load Balancer  │
                                 │  (HTTPS/L7)     │
                                 └────────┬────────┘
                                          │
                                 ┌────────▼────────┐
                                 │ Serverless NEG  │
                                 └────────┬────────┘
                                          │
                                 ┌────────▼────────┐
                                 │   Cloud Run     │
                                 │    Service      │
                                 └─────────────────┘
```

#### Implementation Steps

**Step 1: Configure Cloud Run Ingress**

```bash
# Set ingress to accept traffic from load balancers only
gcloud run services update SERVICE_NAME \
  --ingress=internal-and-cloud-load-balancing \
  --region=REGION
```

**Step 2: Create Serverless Network Endpoint Group (NEG)**

```bash
gcloud compute network-endpoint-groups create pgp-webhook-neg \
  --region=REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=SERVICE_NAME
```

**Step 3: Create Backend Service**

```bash
gcloud compute backend-services create pgp-webhook-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED

# Add the NEG as a backend
gcloud compute backend-services add-backend pgp-webhook-backend \
  --global \
  --network-endpoint-group=pgp-webhook-neg \
  --network-endpoint-group-region=REGION
```

**Step 4: Create Cloud Armor Security Policy**

```bash
# Create security policy
gcloud compute security-policies create pgp-payment-security \
  --description="Security policy for payment webhooks"

# Add rate limiting rule (example: max 100 requests per minute per IP)
gcloud compute security-policies rules create 1000 \
  --security-policy=pgp-payment-security \
  --expression="true" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP

# Add geo-blocking (example: allow only specific countries)
gcloud compute security-policies rules create 2000 \
  --security-policy=pgp-payment-security \
  --expression="origin.region_code in ['US', 'CA', 'GB', 'EU']" \
  --action=allow

# Add OWASP protection (SQLi, XSS, etc.)
gcloud compute security-policies rules create 3000 \
  --security-policy=pgp-payment-security \
  --expression="evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})" \
  --action=deny-403

# Default rule (deny all other traffic)
gcloud compute security-policies rules create 2147483647 \
  --security-policy=pgp-payment-security \
  --action=deny-403
```

**Step 5: Attach Security Policy to Backend Service**

```bash
gcloud compute backend-services update pgp-webhook-backend \
  --security-policy=pgp-payment-security \
  --global
```

**Step 6: Create URL Map and HTTPS Load Balancer**

```bash
# Create URL map
gcloud compute url-maps create pgp-webhook-lb \
  --default-service=pgp-webhook-backend

# Create SSL certificate (managed)
gcloud compute ssl-certificates create pgp-webhook-cert \
  --domains=webhook.yourdomain.com \
  --global

# Create target HTTPS proxy
gcloud compute target-https-proxies create pgp-webhook-https-proxy \
  --url-map=pgp-webhook-lb \
  --ssl-certificates=pgp-webhook-cert

# Create forwarding rule
gcloud compute forwarding-rules create pgp-webhook-https-rule \
  --address=RESERVED_IP_ADDRESS \
  --global \
  --target-https-proxy=pgp-webhook-https-proxy \
  --ports=443
```

#### Cloud Armor Features

**1. Adaptive Protection (ML-based DDoS Defense):**
```bash
# Enable adaptive protection
gcloud compute security-policies update pgp-payment-security \
  --enable-layer7-ddos-defense \
  --layer7-ddos-defense-rule-visibility=STANDARD
```

**2. Bot Management:**
```bash
# Add bot management rule
gcloud compute security-policies rules create 4000 \
  --security-policy=pgp-payment-security \
  --expression="token.recaptcha_session.score < 0.4" \
  --action=deny-403
```

**3. Custom Rules (IP Whitelisting Example):**
```bash
# Allow specific IPs (e.g., NowPayments IPs)
gcloud compute security-policies rules create 100 \
  --security-policy=pgp-payment-security \
  --expression="inIpRange(origin.ip, 'NOWPAYMENTS_IP_RANGE')" \
  --action=allow \
  --description="Allow NowPayments IPN"
```

#### Official Documentation
- **Source:** https://cloud.google.com/run/docs/securing/cloud-armor
- **Full Docs:** https://cloud.google.com/armor/docs
- **DDoS Protection:** https://cloud.google.com/armor/docs/advanced-network-ddos

---

### 2.3 Cloud Load Balancer with Cloud Run

#### Benefits of Load Balancer

1. ✅ **Cloud Armor Integration**: Only way to use Cloud Armor with Cloud Run
2. ✅ **Custom Domains**: Easy SSL/TLS certificate management
3. ✅ **Global Load Balancing**: Serve traffic from nearest region
4. ✅ **Traffic Splitting**: A/B testing and canary deployments
5. ✅ **CDN Integration**: Cache static content
6. ✅ **Identity-Aware Proxy (IAP)**: Additional authentication layer

#### Architecture Options

**Option 1: External Application Load Balancer (for external webhooks)**
- Best for: NowPayments IPN, Telegram Bot webhooks
- Supports: Cloud Armor, SSL certificates, custom domains
- Endpoint: Public IP

**Option 2: Internal Application Load Balancer (for internal services)**
- Best for: Service-to-service communication within VPC
- Supports: Private IPs only, VPC-internal traffic
- Endpoint: Internal IP

**Option 3: Regional vs Global**
- **Regional**: Lower latency for region-specific traffic
- **Global**: Best for worldwide users, multi-region failover

#### Configuration for External Webhooks

```bash
# 1. Set Cloud Run ingress
gcloud run services update SERVICE_NAME \
  --ingress=internal-and-cloud-load-balancing \
  --region=REGION

# 2. Create serverless NEG
gcloud compute network-endpoint-groups create SERVICE_NEG \
  --region=REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=SERVICE_NAME

# 3. Create backend service
gcloud compute backend-services create SERVICE_BACKEND \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED

# 4. Add NEG to backend
gcloud compute backend-services add-backend SERVICE_BACKEND \
  --global \
  --network-endpoint-group=SERVICE_NEG \
  --network-endpoint-group-region=REGION

# 5. Configure health checks (if needed)
gcloud compute health-checks create https SERVICE_HEALTH_CHECK \
  --request-path=/health \
  --port=443

gcloud compute backend-services update SERVICE_BACKEND \
  --global \
  --health-checks=SERVICE_HEALTH_CHECK
```

#### Official Documentation
- **Classic ALB:** https://cloud.google.com/load-balancing/docs/https/setting-up-https-serverless
- **Regional External:** https://cloud.google.com/load-balancing/docs/https/setting-up-reg-ext-https-serverless
- **Regional Internal:** https://cloud.google.com/load-balancing/docs/l7-internal/setting-up-l7-internal-serverless
- **Serverless NEG:** https://cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts

---

### 2.4 Ingress Settings

#### Cloud Run Ingress Options

| Setting | Description | Use Case |
|---------|-------------|----------|
| **All** | Accept traffic from any source (default) | Public APIs with own auth |
| **Internal** | Block all external traffic | VPC-internal services only |
| **Internal and Cloud Load Balancing** | Accept traffic from LB or internal sources | **Recommended for webhooks** |

#### Recommended Configuration by Service Type

**External Payment Webhooks (NowPayments IPN):**
```bash
gcloud run services update nowpayments-webhook \
  --ingress=internal-and-cloud-load-balancing \
  --region=us-central1
```
- Use Load Balancer with Cloud Armor
- HMAC validation in application code
- IP whitelisting via Cloud Armor rules

**Telegram Bot Webhook:**
```bash
gcloud run services update telegram-webhook \
  --ingress=internal-and-cloud-load-balancing \
  --region=us-central1
```
- Use Load Balancer with Cloud Armor
- IP whitelisting for Telegram IPs: `149.154.160.0/20`, `91.108.4.0/22`
- Secret token validation (X-Telegram-Bot-Api-Secret-Token header)

**Internal Notification Service:**
```bash
gcloud run services update notification-service \
  --ingress=internal \
  --no-allow-unauthenticated \
  --region=us-central1
```
- IAM authentication required
- Only callable from other Cloud Run services in same project/VPC

#### Official Documentation
- **Source:** https://cloud.google.com/run/docs/securing/ingress

---

## 3. Defense in Depth Strategy

### 3.1 Layered Security Model

Defense in depth means using multiple independent security layers so that if one layer fails, others still provide protection.

#### Security Layers for Payment Webhooks

```
┌─────────────────────────────────────────────────────────┐
│ Layer 7: Application Logic                              │
│ - Business rule validation                              │
│ - Idempotency checks                                    │
│ - Database constraints                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ Layer 6: Application Security                           │
│ - HMAC signature validation                             │
│ - Timestamp verification (prevent replay)               │
│ - Payload validation (schema, types)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ Layer 5: Authentication & Authorization                 │
│ - IAM authentication (service-to-service)               │
│ - Service account permissions (least privilege)         │
│ - Secret token validation (Telegram)                    │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ Layer 4: Web Application Firewall (WAF)                 │
│ - Cloud Armor security policies                         │
│ - OWASP Top 10 protection                               │
│ - Bot detection and mitigation                          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ Layer 3: Network Security                               │
│ - IP whitelisting (Cloud Armor rules)                   │
│ - Rate limiting (per IP)                                │
│ - Geo-blocking (if applicable)                          │
│ - DDoS protection (Cloud Armor Adaptive Protection)     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ Layer 2: Perimeter Security                             │
│ - VPC Service Controls                                  │
│ - Load Balancer ingress control                         │
│ - Cloud Run ingress settings                            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│ Layer 1: Transport Security                             │
│ - HTTPS/TLS 1.2+ only                                   │
│ - Managed SSL certificates                              │
│ - Certificate pinning (client-side)                     │
└─────────────────────────────────────────────────────────┘
```

---

### 3.2 Implementation by Endpoint Type

#### 3.2.1 External Payment Webhook (NowPayments IPN)

**Threat Model:**
- 🎯 Replay attacks
- 🎯 Man-in-the-middle
- 🎯 Fraudulent payment notifications
- 🎯 DDoS attacks
- 🎯 Data exfiltration

**Security Stack:**

```python
# Layer 1: HTTPS (handled by Cloud Run/Load Balancer)

# Layer 2: Ingress Control
# gcloud run deploy --ingress=internal-and-cloud-load-balancing

# Layer 3: Cloud Armor Rules
# - IP whitelisting for NowPayments IPs
# - Rate limiting: 100 req/min per IP
# - DDoS protection enabled

# Layer 4: Cloud Armor WAF
# - SQL injection protection
# - XSS protection
# - CSRF protection

# Layer 5: Application-level HMAC validation
import hmac
import hashlib
import time

def validate_nowpayments_ipn(request):
    """
    Validate NowPayments IPN webhook signature.

    Layers:
    1. Check timestamp (prevent replay attacks)
    2. Verify HMAC signature
    3. Validate payload schema
    """
    # Get signature from header
    received_signature = request.headers.get('x-nowpayments-sig')
    if not received_signature:
        raise ValueError("Missing signature header")

    # Get IPN secret from Secret Manager
    ipn_secret = get_secret("PGP_NOWPAYMENTS_IPN_SECRET_v1")

    # Get request body
    payload = request.get_data(as_text=True)
    payload_dict = request.get_json()

    # Layer: Timestamp validation (5-minute window)
    if 'created_at' in payload_dict:
        created_at = payload_dict['created_at']
        current_time = int(time.time())
        if abs(current_time - created_at) > 300:  # 5 minutes
            raise ValueError("Timestamp too old - potential replay attack")

    # Layer: HMAC signature validation
    # Sort payload keys and create canonical string
    sorted_payload = sorted(payload_dict.items())
    canonical_string = ''.join([f"{k}{v}" for k, v in sorted_payload])

    # Compute HMAC-SHA512
    expected_signature = hmac.new(
        ipn_secret.encode(),
        canonical_string.encode(),
        hashlib.sha512
    ).hexdigest()

    # Constant-time comparison (prevent timing attacks)
    if not hmac.compare_digest(received_signature, expected_signature):
        raise ValueError("Invalid signature")

    # Layer: Schema validation
    required_fields = ['payment_id', 'payment_status', 'price_amount', 'pay_currency']
    for field in required_fields:
        if field not in payload_dict:
            raise ValueError(f"Missing required field: {field}")

    # Layer: Business logic validation
    # - Check if payment_id already processed (idempotency)
    # - Validate payment amounts
    # - Check payment status transitions

    return payload_dict

# Layer 6: IAM Authentication (for service-to-service calls)
# - Notification service calls are authenticated with service account
# - Cloud Tasks signed with service account credentials

# Layer 7: Audit Logging
def log_webhook_receipt(payload, validation_result):
    """Log all webhook receipts for audit trail."""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(
        "Webhook received",
        extra={
            "payment_id": payload.get("payment_id"),
            "status": payload.get("payment_status"),
            "validation": validation_result,
            "timestamp": time.time()
        }
    )
```

**Configuration:**
```bash
# Deploy with full security stack
gcloud run deploy nowpayments-webhook \
  --image=gcr.io/pgp-live/nowpayments-webhook:latest \
  --region=us-central1 \
  --no-allow-unauthenticated \
  --ingress=internal-and-cloud-load-balancing \
  --service-account=pgp-webhook-receiver@pgp-live.iam.gserviceaccount.com \
  --set-env-vars="ENVIRONMENT=production" \
  --set-secrets="NOWPAYMENTS_IPN_SECRET=PGP_NOWPAYMENTS_IPN_SECRET_v1:latest"
```

---

#### 3.2.2 Telegram Bot Webhook

**Threat Model:**
- 🎯 Impersonation attacks
- 🎯 Unauthorized bot commands
- 🎯 DDoS via bot flooding
- 🎯 Data leakage through bot interactions

**Security Stack:**

```python
# Layer 1: HTTPS/TLS 1.2+ (Telegram requirement)

# Layer 2: Ingress Control
# gcloud run deploy --ingress=internal-and-cloud-load-balancing

# Layer 3: Cloud Armor IP Whitelisting
# Telegram IP ranges:
# - 149.154.160.0/20
# - 91.108.4.0/22

# Layer 4: Cloud Armor Rate Limiting
# - Max 1000 requests/min per IP (generous for Telegram)

# Layer 5: Secret Token Validation
def validate_telegram_webhook(request):
    """
    Validate Telegram webhook request.

    Telegram provides X-Telegram-Bot-Api-Secret-Token header
    for webhook authentication (1-256 characters).
    """
    # Get secret token from header
    received_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')

    if not received_token:
        raise ValueError("Missing Telegram secret token")

    # Get expected token from Secret Manager
    expected_token = get_secret("PGP_TELEGRAM_WEBHOOK_SECRET_TOKEN_v1")

    # Constant-time comparison
    if not hmac.compare_digest(received_token, expected_token):
        raise ValueError("Invalid Telegram secret token")

    # Validate payload structure
    payload = request.get_json()
    if 'update_id' not in payload:
        raise ValueError("Invalid Telegram update structure")

    return payload

# Layer 6: Additional IP Verification (optional)
def verify_telegram_ip(request):
    """
    Verify request originates from Telegram IP ranges.
    This is redundant with Cloud Armor but adds defense in depth.
    """
    import ipaddress

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    telegram_ranges = [
        ipaddress.ip_network('149.154.160.0/20'),
        ipaddress.ip_network('91.108.4.0/22')
    ]

    client_ip_obj = ipaddress.ip_address(client_ip)

    for network in telegram_ranges:
        if client_ip_obj in network:
            return True

    raise ValueError(f"IP {client_ip} not in Telegram ranges")

# Layer 7: Bot Command Authorization
def check_user_authorization(user_id, command):
    """
    Check if user is authorized to execute command.
    Implements role-based access control for bot commands.
    """
    # Query database for user permissions
    # Implement rate limiting per user
    # Log all commands for audit
    pass
```

**Webhook Setup:**
```python
import requests

def set_telegram_webhook():
    """
    Set Telegram webhook with secret token.
    Only needs to be done once.
    """
    bot_token = get_secret("PGP_TELEGRAM_BOT_TOKEN_v1")
    webhook_url = "https://telegram-webhook.yourdomain.com/webhook"
    secret_token = get_secret("PGP_TELEGRAM_WEBHOOK_SECRET_TOKEN_v1")

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/setWebhook",
        json={
            "url": webhook_url,
            "secret_token": secret_token,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True
        }
    )

    return response.json()
```

---

#### 3.2.3 Internal Service-to-Service Communication

**Threat Model:**
- 🎯 Lateral movement after compromise
- 🎯 Privilege escalation
- 🎯 Data exfiltration

**Security Stack:**

```python
# Layer 1: VPC-Internal Communication
# gcloud run deploy --ingress=internal

# Layer 2: IAM Authentication (REQUIRED)
# - No allow-unauthenticated
# - Service accounts with minimal permissions
# - Invoker role granted explicitly

# Layer 3: Service-to-Service Auth Token
async def call_internal_service(target_service_url, payload):
    """
    Make authenticated call to another Cloud Run service.
    """
    import google.auth.transport.requests
    import google.oauth2.id_token
    import aiohttp

    # Get ID token for target service
    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, target_service_url)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            target_service_url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            response.raise_for_status()
            return await response.json()

# Layer 4: Request Signing (additional verification)
def sign_internal_request(payload, service_secret):
    """
    Sign internal service requests with HMAC.
    Adds an extra layer beyond IAM.
    """
    import hmac
    import hashlib
    import time
    import json

    timestamp = int(time.time())
    payload_with_timestamp = {
        **payload,
        "_timestamp": timestamp,
        "_service": "pgp-server"
    }

    canonical_payload = json.dumps(payload_with_timestamp, sort_keys=True)
    signature = hmac.new(
        service_secret.encode(),
        canonical_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "payload": payload,
        "timestamp": timestamp,
        "signature": signature
    }

def verify_internal_request(request_data, service_secret):
    """Verify signed internal request."""
    import hmac
    import hashlib
    import time
    import json

    timestamp = request_data.get("timestamp")
    signature = request_data.get("signature")
    payload = request_data.get("payload")

    # Check timestamp (5-minute window)
    if abs(int(time.time()) - timestamp) > 300:
        raise ValueError("Request timestamp expired")

    # Recreate signature
    payload_with_timestamp = {
        **payload,
        "_timestamp": timestamp,
        "_service": "pgp-server"
    }
    canonical_payload = json.dumps(payload_with_timestamp, sort_keys=True)
    expected_signature = hmac.new(
        service_secret.encode(),
        canonical_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid request signature")

    return payload

# Layer 5: Audit Logging
# - Log all inter-service calls
# - Monitor for unusual patterns
# - Alert on authorization failures
```

---

### 3.3 Trade-offs and Considerations

#### Performance vs Security

| Security Layer | Latency Impact | Cost Impact | Complexity |
|----------------|----------------|-------------|------------|
| HTTPS/TLS | Minimal (~1-2ms) | Included | Low |
| Cloud Armor | Low (~5-10ms) | $$ | Medium |
| Load Balancer | Low (~5-10ms) | $$ | Medium |
| IAM Auth | Minimal (~1-2ms) | Included | Low |
| HMAC Validation | Minimal (<1ms) | Included | Low |
| VPC SC | None | Included | High |
| Rate Limiting | None | Included | Low |

**Recommendations:**
- ✅ Always use: HTTPS, IAM Auth (internal), HMAC Validation
- ✅ Use for production: Cloud Armor, Load Balancer, Rate Limiting
- ⚠️ Use when needed: VPC SC (high compliance requirements)

#### Cost Considerations

**Cloud Armor:**
- Policy: $0.75/policy/month
- Rule: $0.10/rule/month
- Requests: $0.75/million requests

**Load Balancer:**
- Forwarding rule: $0.025/hour ($18/month)
- Data processing: $0.008-$0.016/GB

**VPC Service Controls:**
- Included in Google Cloud (no additional charge)

**Recommendation:**
- Start with: HMAC + IP whitelisting (Cloud Armor) + Load Balancer
- Add later: VPC SC if compliance requires it

---

## 4. Payment Service Specific Security

### 4.1 PCI DSS Compliance

#### Google Cloud PCI DSS Status

- ✅ Google Cloud is a **Level 1 PCI DSS 4.0.1 compliant service provider**
- ✅ Cloud Run is included in PCI DSS certification
- ✅ Cloud SQL, Secret Manager, Cloud Storage are also certified

#### Shared Responsibility Model

**Google's Responsibilities:**
- Physical security of data centers
- Network infrastructure security
- Encryption at rest (automatic)
- Platform-level security controls

**Your Responsibilities:**
- Application-level security
- Access controls (IAM)
- Encryption in transit (HTTPS)
- Data handling and processing
- Logging and monitoring
- Tokenization/hashing of card data (if applicable)

#### PCI DSS Requirements for Cloud Run

**Requirement 1 & 2: Network Security**
- ✅ Use Cloud Armor for firewall rules
- ✅ Use VPC Service Controls for network segmentation
- ✅ Configure ingress controls on Cloud Run

**Requirement 3: Protect Stored Data**
- ✅ Use Secret Manager for sensitive credentials
- ✅ Enable Cloud SQL encryption (automatic)
- ✅ Implement field-level encryption for card data (if stored)

**Requirement 4: Encrypt Transmission**
- ✅ HTTPS/TLS 1.2+ only
- ✅ Use managed SSL certificates
- ✅ Disable insecure protocols

**Requirement 5 & 6: Security Systems**
- ✅ Cloud Armor WAF for OWASP protection
- ✅ Container vulnerability scanning
- ✅ Regular dependency updates

**Requirement 7 & 8: Access Control**
- ✅ IAM with least privilege
- ✅ Service accounts for each service
- ✅ MFA for human access
- ✅ Audit logs for all access

**Requirement 9: Physical Access**
- ✅ Handled by Google Cloud

**Requirement 10: Logging and Monitoring**
- ✅ Cloud Logging for all requests
- ✅ Cloud Monitoring for alerting
- ✅ Audit logs for admin actions
- ✅ Retain logs for 1+ year

**Requirement 11: Security Testing**
- ✅ Regular penetration testing
- ✅ Vulnerability scanning
- ✅ Web application scanning

**Requirement 12: Security Policy**
- ✅ Document security architecture
- ✅ Incident response plan
- ✅ Regular security training

#### Important Notes

⚠️ **Cardholder Data Scope:**
- If using NowPayments (payment processor), you typically do NOT handle raw card data
- NowPayments handles PCI compliance for card processing
- You only receive payment status notifications (not card numbers)
- This significantly reduces your PCI DSS scope

✅ **SAQ (Self-Assessment Questionnaire) Type:**
- Most likely SAQ A (if using hosted payment page)
- Minimal compliance requirements
- No card data touches your servers

#### Official Documentation
- **Google PCI DSS:** https://cloud.google.com/security/compliance/pci-dss
- **Architecture Guide:** https://cloud.google.com/architecture/pci-dss-compliance-in-gcp

---

### 4.2 NowPayments IPN Security

#### NowPayments Security Mechanism

**HMAC-SHA512 Signature:**
1. NowPayments sends POST request with `x-nowpayments-sig` header
2. Signature computed from sorted payload + IPN secret key
3. Uses HMAC-SHA512 algorithm

#### Implementation

```python
import hmac
import hashlib
import time
from typing import Dict, Any
from flask import Request

class NowPaymentsIPNValidator:
    """
    Secure validator for NowPayments IPN webhooks.
    Implements multiple security layers.
    """

    def __init__(self, ipn_secret: str):
        self.ipn_secret = ipn_secret
        self.replay_window_seconds = 300  # 5 minutes
        self.processed_ipns = set()  # In production, use Redis/database

    def validate(self, request: Request) -> Dict[str, Any]:
        """
        Validate NowPayments IPN webhook.

        Security checks:
        1. HMAC signature verification
        2. Timestamp validation (anti-replay)
        3. Idempotency check
        4. Schema validation

        Raises:
            ValueError: If validation fails

        Returns:
            Validated payload dictionary
        """
        # Layer 1: Get signature from header
        received_signature = request.headers.get('x-nowpayments-sig')
        if not received_signature:
            raise ValueError("🚨 Missing x-nowpayments-sig header")

        # Layer 2: Parse payload
        try:
            payload = request.get_json()
        except Exception as e:
            raise ValueError(f"🚨 Invalid JSON payload: {e}")

        # Layer 3: Timestamp validation (prevent replay attacks)
        self._validate_timestamp(payload)

        # Layer 4: Idempotency check (prevent duplicate processing)
        self._check_idempotency(payload)

        # Layer 5: HMAC signature verification
        self._verify_signature(payload, received_signature)

        # Layer 6: Schema validation
        self._validate_schema(payload)

        # Layer 7: Business logic validation
        self._validate_business_rules(payload)

        # Mark as processed
        payment_id = payload['payment_id']
        self.processed_ipns.add(payment_id)

        return payload

    def _validate_timestamp(self, payload: Dict[str, Any]):
        """Validate timestamp to prevent replay attacks."""
        if 'created_at' not in payload:
            # If no timestamp, rely on other checks
            return

        created_at = payload['created_at']
        current_time = int(time.time())

        if abs(current_time - created_at) > self.replay_window_seconds:
            raise ValueError(
                f"🚨 Timestamp too old: {created_at} vs {current_time}. "
                f"Potential replay attack detected."
            )

    def _check_idempotency(self, payload: Dict[str, Any]):
        """Check if this IPN was already processed."""
        payment_id = payload.get('payment_id')
        if not payment_id:
            raise ValueError("🚨 Missing payment_id in payload")

        # In production, check database
        if payment_id in self.processed_ipns:
            raise ValueError(
                f"🚨 Duplicate IPN detected: {payment_id} already processed"
            )

    def _verify_signature(self, payload: Dict[str, Any], received_signature: str):
        """Verify HMAC-SHA512 signature."""
        # Sort payload by keys
        sorted_items = sorted(payload.items())

        # Create canonical string
        canonical_string = ''.join([f"{k}{v}" for k, v in sorted_items])

        # Compute HMAC-SHA512
        expected_signature = hmac.new(
            self.ipn_secret.encode(),
            canonical_string.encode(),
            hashlib.sha512
        ).hexdigest()

        # Constant-time comparison (prevent timing attacks)
        if not hmac.compare_digest(received_signature, expected_signature):
            raise ValueError("🚨 Invalid HMAC signature - authentication failed")

    def _validate_schema(self, payload: Dict[str, Any]):
        """Validate required fields are present."""
        required_fields = [
            'payment_id',
            'payment_status',
            'pay_currency',
            'price_amount',
            'price_currency',
            'order_id'  # Your internal order ID
        ]

        missing_fields = [f for f in required_fields if f not in payload]
        if missing_fields:
            raise ValueError(
                f"🚨 Missing required fields: {', '.join(missing_fields)}"
            )

    def _validate_business_rules(self, payload: Dict[str, Any]):
        """Validate business logic constraints."""
        # Validate payment status
        valid_statuses = [
            'waiting', 'confirming', 'confirmed', 'sending',
            'partially_paid', 'finished', 'failed', 'refunded', 'expired'
        ]
        if payload['payment_status'] not in valid_statuses:
            raise ValueError(
                f"🚨 Invalid payment status: {payload['payment_status']}"
            )

        # Validate amounts are positive
        if float(payload['price_amount']) <= 0:
            raise ValueError("🚨 Invalid price_amount: must be positive")

        # Add more business rules as needed
```

#### Firewall Configuration

**Important:** NowPayments warns about Cloudflare potentially blocking their requests.

**Recommended Approach:**
1. Use Cloud Armor (not Cloudflare) for DDoS protection
2. Whitelist NowPayments IP addresses in Cloud Armor
3. Configure Cloud Run behind Load Balancer
4. Do NOT use shared hosting

**Cloud Armor Rule:**
```bash
# Whitelist NowPayments IPs (get from their support)
gcloud compute security-policies rules create 100 \
  --security-policy=pgp-payment-security \
  --expression="inIpRange(origin.ip, 'NOWPAYMENTS_IP_1/32') || inIpRange(origin.ip, 'NOWPAYMENTS_IP_2/32')" \
  --action=allow \
  --description="Allow NowPayments IPN webhooks"
```

#### Official Documentation
- **NowPayments IPN:** https://nowpayments.zendesk.com/hc/en-us/articles/21395546303389-IPN-and-how-to-setup
- **API Docs:** https://documenter.getpostman.com/view/7907941/S1a32n38

---

### 4.3 Telegram Bot Webhook Security

#### Telegram Security Features

**1. Secret Token (Recommended Method):**
```python
# Set webhook with secret token
webhook_url = "https://telegram.yourdomain.com/webhook"
secret_token = secrets.token_urlsafe(32)  # Generate random token

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={
        "url": webhook_url,
        "secret_token": secret_token,  # 1-256 characters
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True
    }
)

# Validate in webhook handler
def validate_telegram_webhook(request):
    received_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    expected_token = get_secret("PGP_TELEGRAM_WEBHOOK_SECRET_TOKEN_v1")

    if not hmac.compare_digest(received_token or "", expected_token):
        raise ValueError("Invalid Telegram secret token")
```

**2. IP Whitelisting:**
```bash
# Telegram IP ranges (as of 2025)
# - 149.154.160.0/20
# - 91.108.4.0/22

# Cloud Armor rule
gcloud compute security-policies rules create 200 \
  --security-policy=pgp-payment-security \
  --expression="inIpRange(origin.ip, '149.154.160.0/20') || inIpRange(origin.ip, '91.108.4.0/22')" \
  --action=allow \
  --description="Allow Telegram webhooks"
```

**3. HTTPS Requirements:**
- Telegram requires HTTPS (not HTTP)
- Supports TLS 1.2 and higher
- Does NOT support SSLv2/3/TLS1.0/TLS1.1
- Ports: 443, 80, 88, or 8443 only

#### Full Implementation

```python
import hmac
import secrets
from typing import Dict, Any
from flask import Request

class TelegramWebhookValidator:
    """
    Secure validator for Telegram Bot webhooks.
    """

    def __init__(self, secret_token: str):
        self.secret_token = secret_token
        self.telegram_ip_ranges = [
            '149.154.160.0/20',
            '91.108.4.0/22'
        ]

    def validate(self, request: Request) -> Dict[str, Any]:
        """
        Validate Telegram webhook request.

        Security checks:
        1. Secret token verification
        2. IP range verification (defense in depth)
        3. Payload structure validation

        Raises:
            ValueError: If validation fails

        Returns:
            Validated update dictionary
        """
        # Layer 1: Secret token verification
        received_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        if not received_token:
            raise ValueError("🚨 Missing X-Telegram-Bot-Api-Secret-Token header")

        if not hmac.compare_digest(received_token, self.secret_token):
            raise ValueError("🚨 Invalid Telegram secret token")

        # Layer 2: IP verification (redundant with Cloud Armor, but adds defense)
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        self._verify_telegram_ip(client_ip)

        # Layer 3: Parse and validate payload
        try:
            update = request.get_json()
        except Exception as e:
            raise ValueError(f"🚨 Invalid JSON payload: {e}")

        # Layer 4: Structure validation
        if 'update_id' not in update:
            raise ValueError("🚨 Missing update_id in Telegram update")

        return update

    def _verify_telegram_ip(self, client_ip: str):
        """Verify IP is from Telegram (defense in depth)."""
        import ipaddress

        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            raise ValueError(f"🚨 Invalid client IP: {client_ip}")

        for ip_range in self.telegram_ip_ranges:
            network = ipaddress.ip_network(ip_range)
            if client_ip_obj in network:
                return True

        raise ValueError(
            f"🚨 IP {client_ip} not in Telegram IP ranges - potential spoofing"
        )

# Setup webhook (run once)
def setup_telegram_webhook(bot_token: str, webhook_url: str) -> str:
    """
    Set up Telegram webhook with secret token.

    Returns:
        The secret token (store in Secret Manager)
    """
    import requests

    # Generate cryptographically secure random token
    secret_token = secrets.token_urlsafe(32)

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/setWebhook",
        json={
            "url": webhook_url,
            "secret_token": secret_token,
            "max_connections": 40,
            "allowed_updates": ["message", "callback_query", "chat_member"],
            "drop_pending_updates": True
        }
    )

    if not response.ok:
        raise Exception(f"Failed to set webhook: {response.text}")

    print(f"✅ Webhook set successfully")
    print(f"🔒 Secret token (store in Secret Manager): {secret_token}")

    return secret_token
```

#### Rate Limiting for Bot Protection

```python
import time
from collections import defaultdict

class TelegramRateLimiter:
    """
    Rate limiter to prevent bot abuse.
    Implements per-user and per-chat rate limits.
    """

    def __init__(self):
        self.user_requests = defaultdict(list)
        self.chat_requests = defaultdict(list)

        # Limits
        self.user_limit_per_minute = 20
        self.chat_limit_per_minute = 100
        self.window_seconds = 60

    def check_rate_limit(self, user_id: int, chat_id: int) -> bool:
        """
        Check if request should be allowed.

        Returns:
            True if allowed, False if rate limited
        """
        current_time = time.time()

        # Clean old requests
        self._clean_old_requests(current_time)

        # Check user limit
        user_key = f"user:{user_id}"
        if len(self.user_requests[user_key]) >= self.user_limit_per_minute:
            return False

        # Check chat limit
        chat_key = f"chat:{chat_id}"
        if len(self.chat_requests[chat_key]) >= self.chat_limit_per_minute:
            return False

        # Record request
        self.user_requests[user_key].append(current_time)
        self.chat_requests[chat_key].append(current_time)

        return True

    def _clean_old_requests(self, current_time: float):
        """Remove requests older than window."""
        cutoff_time = current_time - self.window_seconds

        for key in list(self.user_requests.keys()):
            self.user_requests[key] = [
                t for t in self.user_requests[key] if t > cutoff_time
            ]
            if not self.user_requests[key]:
                del self.user_requests[key]

        for key in list(self.chat_requests.keys()):
            self.chat_requests[key] = [
                t for t in self.chat_requests[key] if t > cutoff_time
            ]
            if not self.chat_requests[key]:
                del self.chat_requests[key]
```

#### Official Documentation
- **Telegram Webhooks:** https://core.telegram.org/bots/webhooks
- **Bot API:** https://core.telegram.org/bots/api

---

## 5. Implementation Checklist

### Phase 1: Foundation (Week 1)

#### 5.1 Service Accounts & IAM

- [ ] Create dedicated service account for each Cloud Run service
  ```bash
  # Webhook receiver
  gcloud iam service-accounts create pgp-webhook-receiver \
    --display-name="PGP Webhook Receiver" \
    --project=pgp-live

  # Notification service
  gcloud iam service-accounts create pgp-notification-service \
    --display-name="PGP Notification Service" \
    --project=pgp-live

  # Server service
  gcloud iam service-accounts create pgp-server \
    --display-name="PGP Server" \
    --project=pgp-live
  ```

- [ ] Grant minimal IAM permissions
  ```bash
  # Cloud SQL access
  gcloud projects add-iam-policy-binding pgp-live \
    --member="serviceAccount:pgp-webhook-receiver@pgp-live.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

  # Secret Manager access
  gcloud secrets add-iam-policy-binding PGP_NOWPAYMENTS_IPN_SECRET_v1 \
    --member="serviceAccount:pgp-webhook-receiver@pgp-live.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
  ```

- [ ] Configure service-to-service authentication
  ```bash
  # Allow notification service to invoke server
  gcloud run services add-iam-policy-binding pgp-server \
    --member="serviceAccount:pgp-notification-service@pgp-live.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=us-central1
  ```

- [ ] Deploy services with `--no-allow-unauthenticated`
  ```bash
  gcloud run deploy pgp-server \
    --image=gcr.io/pgp-live/pgp-server:latest \
    --region=us-central1 \
    --no-allow-unauthenticated \
    --service-account=pgp-server@pgp-live.iam.gserviceaccount.com
  ```

#### 5.2 HMAC Validation

- [ ] Implement NowPayments IPN validator (see section 4.2)
- [ ] Implement Telegram webhook validator (see section 4.3)
- [ ] Add timestamp validation (5-minute window)
- [ ] Implement idempotency checks
- [ ] Add comprehensive logging for all validations
- [ ] Test with sample payloads

#### 5.3 Secrets Management

- [ ] Store all secrets in Secret Manager (not environment variables)
  ```bash
  # NowPayments IPN secret
  echo -n "YOUR_IPN_SECRET" | gcloud secrets create PGP_NOWPAYMENTS_IPN_SECRET_v1 \
    --data-file=- \
    --replication-policy=automatic

  # Telegram webhook secret
  echo -n "YOUR_WEBHOOK_TOKEN" | gcloud secrets create PGP_TELEGRAM_WEBHOOK_SECRET_TOKEN_v1 \
    --data-file=- \
    --replication-policy=automatic
  ```

- [ ] Grant secret access to service accounts
- [ ] Rotate secrets and update references
- [ ] Document all secrets in SECRET_SCHEME.md

---

### Phase 2: Network Security (Week 2)

#### 5.4 Load Balancer Setup

- [ ] Reserve static IP address
  ```bash
  gcloud compute addresses create pgp-webhook-ip \
    --global \
    --ip-version=IPV4
  ```

- [ ] Create serverless NEGs for webhook services
  ```bash
  # NowPayments webhook NEG
  gcloud compute network-endpoint-groups create pgp-nowpayments-neg \
    --region=us-central1 \
    --network-endpoint-type=serverless \
    --cloud-run-service=nowpayments-webhook

  # Telegram webhook NEG
  gcloud compute network-endpoint-groups create pgp-telegram-neg \
    --region=us-central1 \
    --network-endpoint-type=serverless \
    --cloud-run-service=telegram-webhook
  ```

- [ ] Create backend services
  ```bash
  # NowPayments backend
  gcloud compute backend-services create pgp-nowpayments-backend \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED

  gcloud compute backend-services add-backend pgp-nowpayments-backend \
    --global \
    --network-endpoint-group=pgp-nowpayments-neg \
    --network-endpoint-group-region=us-central1
  ```

- [ ] Create URL map with path-based routing
  ```bash
  # Create URL map
  gcloud compute url-maps create pgp-webhooks-lb \
    --default-service=pgp-nowpayments-backend

  # Add path matcher for Telegram
  gcloud compute url-maps add-path-matcher pgp-webhooks-lb \
    --path-matcher-name=telegram-matcher \
    --default-service=pgp-telegram-backend \
    --new-hosts=webhook.yourdomain.com
  ```

- [ ] Obtain SSL certificate
  ```bash
  # Managed certificate (recommended)
  gcloud compute ssl-certificates create pgp-webhook-cert \
    --domains=webhook.yourdomain.com \
    --global
  ```

- [ ] Create HTTPS load balancer
  ```bash
  # Target proxy
  gcloud compute target-https-proxies create pgp-webhooks-https-proxy \
    --url-map=pgp-webhooks-lb \
    --ssl-certificates=pgp-webhook-cert

  # Forwarding rule
  gcloud compute forwarding-rules create pgp-webhooks-https-rule \
    --address=pgp-webhook-ip \
    --global \
    --target-https-proxy=pgp-webhooks-https-proxy \
    --ports=443
  ```

- [ ] Update Cloud Run ingress settings
  ```bash
  gcloud run services update nowpayments-webhook \
    --ingress=internal-and-cloud-load-balancing \
    --region=us-central1

  gcloud run services update telegram-webhook \
    --ingress=internal-and-cloud-load-balancing \
    --region=us-central1
  ```

- [ ] Update DNS records to point to load balancer IP

#### 5.5 Cloud Armor Configuration

- [ ] Create security policy
  ```bash
  gcloud compute security-policies create pgp-payment-security \
    --description="Security policy for PGP payment webhooks"
  ```

- [ ] Add IP whitelisting rules
  ```bash
  # NowPayments IPs (get from support)
  gcloud compute security-policies rules create 100 \
    --security-policy=pgp-payment-security \
    --expression="inIpRange(origin.ip, 'NOWPAYMENTS_IP/32')" \
    --action=allow \
    --description="Allow NowPayments IPN"

  # Telegram IPs
  gcloud compute security-policies rules create 200 \
    --security-policy=pgp-payment-security \
    --expression="inIpRange(origin.ip, '149.154.160.0/20') || inIpRange(origin.ip, '91.108.4.0/22')" \
    --action=allow \
    --description="Allow Telegram webhooks"
  ```

- [ ] Add rate limiting
  ```bash
  # 100 requests per minute per IP
  gcloud compute security-policies rules create 1000 \
    --security-policy=pgp-payment-security \
    --expression="true" \
    --action=rate-based-ban \
    --rate-limit-threshold-count=100 \
    --rate-limit-threshold-interval-sec=60 \
    --ban-duration-sec=600 \
    --conform-action=allow \
    --exceed-action=deny-429 \
    --enforce-on-key=IP
  ```

- [ ] Add WAF rules (OWASP protection)
  ```bash
  # SQL injection protection
  gcloud compute security-policies rules create 3000 \
    --security-policy=pgp-payment-security \
    --expression="evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})" \
    --action=deny-403

  # XSS protection
  gcloud compute security-policies rules create 3001 \
    --security-policy=pgp-payment-security \
    --expression="evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})" \
    --action=deny-403
  ```

- [ ] Enable Adaptive Protection (ML-based DDoS)
  ```bash
  gcloud compute security-policies update pgp-payment-security \
    --enable-layer7-ddos-defense \
    --layer7-ddos-defense-rule-visibility=STANDARD
  ```

- [ ] Attach policy to backend services
  ```bash
  gcloud compute backend-services update pgp-nowpayments-backend \
    --security-policy=pgp-payment-security \
    --global

  gcloud compute backend-services update pgp-telegram-backend \
    --security-policy=pgp-payment-security \
    --global
  ```

- [ ] Test security policy rules
- [ ] Monitor Cloud Armor logs in Cloud Logging

---

### Phase 3: Advanced Security (Week 3-4)

#### 5.6 VPC Service Controls (Optional - High Compliance)

- [ ] Create access policy
  ```bash
  gcloud access-context-manager policies create \
    --organization=ORG_ID \
    --title="PGP Production Policy"
  ```

- [ ] Define access levels
  ```bash
  # Create access_level.yaml
  # conditions:
  #   - ipSubnetworks:
  #     - "YOUR_OFFICE_IP/32"
  #     - "149.154.160.0/20"
  #     - "91.108.4.0/22"

  gcloud access-context-manager levels create pgp_production_access \
    --title="PGP Production Access" \
    --basic-level-spec=access_level.yaml \
    --policy=POLICY_ID
  ```

- [ ] Create service perimeter
  ```bash
  gcloud access-context-manager perimeters create pgp_production_perimeter \
    --title="PGP Production Perimeter" \
    --resources=projects/PROJECT_NUMBER \
    --restricted-services=run.googleapis.com,sqladmin.googleapis.com,secretmanager.googleapis.com \
    --access-levels=pgp_production_access \
    --policy=POLICY_ID
  ```

- [ ] Test access from within and outside perimeter
- [ ] Document VPC SC configuration

#### 5.7 Logging & Monitoring

- [ ] Configure Cloud Logging sinks
  ```bash
  # Create log sink for security events
  gcloud logging sinks create pgp-security-logs \
    --log-filter='resource.type="cloud_run_revision" AND severity>=WARNING' \
    --destination=bigquery.googleapis.com/projects/pgp-live/datasets/security_logs
  ```

- [ ] Set up Cloud Monitoring alerts
  ```bash
  # Alert on high error rate
  # Alert on authentication failures
  # Alert on Cloud Armor blocks
  # Alert on unusual traffic patterns
  ```

- [ ] Create dashboard for security metrics
- [ ] Configure log retention (1+ year for PCI DSS)
- [ ] Set up log exports to BigQuery for analysis

#### 5.8 Testing & Validation

- [ ] Test NowPayments IPN with valid signature
- [ ] Test NowPayments IPN with invalid signature (should reject)
- [ ] Test Telegram webhook with valid token
- [ ] Test Telegram webhook with invalid token (should reject)
- [ ] Test service-to-service authentication
- [ ] Test rate limiting (exceed limits and verify blocking)
- [ ] Test Cloud Armor IP whitelisting
- [ ] Test WAF rules (send SQLi/XSS payloads)
- [ ] Verify all logs are captured
- [ ] Verify monitoring alerts trigger correctly
- [ ] Load test to verify performance under security layers

---

### Phase 4: Documentation & Compliance (Ongoing)

#### 5.9 Documentation

- [ ] Document security architecture (this document)
- [ ] Create incident response runbook
- [ ] Document secret rotation procedures
- [ ] Create security testing checklist
- [ ] Document compliance mappings (PCI DSS)
- [ ] Update DECISIONS.md with security decisions

#### 5.10 Ongoing Security

- [ ] Schedule quarterly security reviews
- [ ] Set up vulnerability scanning
- [ ] Plan penetration testing
- [ ] Implement security training for team
- [ ] Create security changelog
- [ ] Monitor Google Cloud security bulletins
- [ ] Update dependencies regularly
- [ ] Rotate secrets quarterly

---

## 6. Architecture Recommendations

### 6.1 Recommended Architecture: PGP_v1

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INTERNET                                    │
└────────────────┬───────────────────────────┬─────────────────────────┘
                 │                           │
                 │ NowPayments IPN           │ Telegram Bot
                 │                           │
                 ▼                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                    HTTPS Load Balancer                             │
│                  (Global, SSL Certificate)                         │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Cloud Armor Security Policy                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ • IP Whitelisting (NowPayments, Telegram)                    │  │
│  │ • Rate Limiting (100 req/min per IP)                         │  │
│  │ • WAF Rules (SQLi, XSS, CSRF protection)                     │  │
│  │ • Adaptive DDoS Protection (ML-based)                        │  │
│  │ • Geo-blocking (optional)                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
┌───────────────────────┐  ┌───────────────────────┐
│ Serverless NEG        │  │ Serverless NEG        │
│ (NowPayments)         │  │ (Telegram)            │
└───────────┬───────────┘  └───────────┬───────────┘
            │                          │
            ▼                          ▼
┌───────────────────────┐  ┌───────────────────────┐
│ Cloud Run:            │  │ Cloud Run:            │
│ NowPayments Webhook   │  │ Telegram Webhook      │
│                       │  │                       │
│ Ingress: LB Only      │  │ Ingress: LB Only      │
│ Auth: IAM Required    │  │ Auth: IAM Required    │
│                       │  │                       │
│ Security Layers:      │  │ Security Layers:      │
│ • HMAC-SHA512        │  │ • Secret Token       │
│ • Timestamp Check     │  │ • IP Verification    │
│ • Idempotency        │  │ • Rate Limiting      │
│ • Schema Validation   │  │ • Command Auth       │
└───────────┬───────────┘  └───────────┬───────────┘
            │                          │
            │ IAM Auth                 │ IAM Auth
            │ (ID Token)               │ (ID Token)
            │                          │
            └──────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │ Cloud Run:               │
        │ PGP Notification Service │
        │                          │
        │ Ingress: Internal Only   │
        │ Auth: IAM Required       │
        │                          │
        │ Security Layers:         │
        │ • Request Signing        │
        │ • Service Account Auth   │
        │ • Audit Logging          │
        └──────────┬───────────────┘
                   │
                   │ Cloud SQL Connector
                   │ (Private IP)
                   │
                   ▼
        ┌──────────────────────────┐
        │ Cloud SQL                │
        │ (PostgreSQL)             │
        │                          │
        │ • Private IP             │
        │ • Encryption at Rest     │
        │ • Automated Backups      │
        │ • IAM Auth               │
        └──────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                VPC Service Controls (Optional)                       │
│  Perimeter around: Cloud Run, Cloud SQL, Secret Manager             │
│  Access Level: Office IP + Telegram IPs                             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     Monitoring & Logging                             │
│  • Cloud Logging (all requests, security events)                    │
│  • Cloud Monitoring (alerts, dashboards)                            │
│  • Audit Logs (IAM, admin actions)                                  │
│  • BigQuery (long-term log storage, analysis)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 6.2 Security Layers Summary

| Layer | Technology | Purpose | External Webhooks | Internal Services |
|-------|-----------|---------|-------------------|-------------------|
| **L1: Transport** | HTTPS/TLS 1.2+ | Encryption in transit | ✅ Required | ✅ Required |
| **L2: Perimeter** | Load Balancer + Ingress | Traffic routing | ✅ LB Only | ✅ Internal Only |
| **L3: Network** | Cloud Armor | DDoS, IP whitelist, rate limit | ✅ Yes | ❌ N/A |
| **L4: WAF** | Cloud Armor Rules | OWASP Top 10 protection | ✅ Yes | ❌ N/A |
| **L5: Auth** | IAM / Secret Token | Identity verification | ✅ Token/HMAC | ✅ IAM Required |
| **L6: App Security** | HMAC/Signature | Request authenticity | ✅ HMAC-SHA512 | ✅ Request Signing |
| **L7: Business Logic** | Code Validation | Schema, rules, idempotency | ✅ Yes | ✅ Yes |
| **L8: Data Protection** | Secret Manager | Secrets management | ✅ Yes | ✅ Yes |
| **L9: Audit** | Cloud Logging | Visibility & compliance | ✅ Yes | ✅ Yes |
| **L10: Isolation** | VPC SC (optional) | Data exfiltration prevention | ⚠️ If needed | ⚠️ If needed |

---

### 6.3 Configuration Matrix

| Service | Ingress | Allow Unauth? | IAM Roles | Additional Auth | IP Whitelist | Rate Limit |
|---------|---------|---------------|-----------|-----------------|--------------|------------|
| **NowPayments Webhook** | LB Only | ❌ No | Minimal | HMAC-SHA512 | NowPayments IPs | 100/min |
| **Telegram Webhook** | LB Only | ❌ No | Minimal | Secret Token | Telegram IPs | 1000/min |
| **Notification Service** | Internal | ❌ No | run.invoker | Request Signing | N/A | N/A |
| **PGP Server** | Internal | ❌ No | run.invoker | Request Signing | N/A | N/A |
| **Admin API** | LB Only | ❌ No | admin.* | JWT Token | Office IPs | 60/min |

---

### 6.4 Cost Estimate

**Monthly Costs (Production):**

| Component | Cost | Notes |
|-----------|------|-------|
| Cloud Run (3 services) | ~$50-100 | Based on traffic |
| Cloud SQL (db-f1-micro) | ~$7-15 | PostgreSQL |
| Load Balancer | ~$18 | Forwarding rule |
| Cloud Armor | ~$10-20 | Policy + rules + requests |
| Secret Manager | ~$1 | Per secret |
| Cloud Logging | ~$0-50 | Based on volume |
| Cloud Monitoring | Free | Under free tier |
| SSL Certificates | Free | Google-managed |
| **Total** | **~$86-204/month** | Scales with traffic |

**Cost Optimization:**
- Start with Cloud Armor (essential for payment security)
- Add VPC SC only if compliance requires it
- Use Cloud Run min instances = 0 (pay per request)
- Set up budget alerts

---

## 7. References & Official Documentation

### Google Cloud Documentation

**Cloud Run Security:**
- Security Overview: https://cloud.google.com/run/docs/securing/security
- Managing Access (IAM): https://cloud.google.com/run/docs/securing/managing-access
- Service-to-Service Auth: https://cloud.google.com/run/docs/authenticating/service-to-service
- Ingress Controls: https://cloud.google.com/run/docs/securing/ingress
- VPC Service Controls: https://cloud.google.com/run/docs/securing/using-vpc-service-controls
- Cloud Armor Integration: https://cloud.google.com/run/docs/securing/cloud-armor

**Cloud Armor:**
- Overview: https://cloud.google.com/armor/docs
- Security Policies: https://cloud.google.com/armor/docs/security-policy-overview
- DDoS Protection: https://cloud.google.com/armor/docs/advanced-network-ddos
- WAF Rules: https://cloud.google.com/armor/docs/waf-rules

**Load Balancing:**
- Serverless NEG: https://cloud.google.com/load-balancing/docs/negs/serverless-neg-concepts
- HTTPS Load Balancer: https://cloud.google.com/load-balancing/docs/https/setting-up-https-serverless

**IAM & Service Accounts:**
- Service Account Best Practices: https://cloud.google.com/iam/docs/best-practices-service-accounts
- Key Management: https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys

**Compliance:**
- PCI DSS on GCP: https://cloud.google.com/security/compliance/pci-dss
- Architecture Guide: https://cloud.google.com/architecture/pci-dss-compliance-in-gcp

### Payment Provider Documentation

**NowPayments:**
- IPN Setup: https://nowpayments.zendesk.com/hc/en-us/articles/21395546303389-IPN-and-how-to-setup
- API Documentation: https://documenter.getpostman.com/view/7907941/S1a32n38

**Telegram:**
- Webhook Guide: https://core.telegram.org/bots/webhooks
- Bot API: https://core.telegram.org/bots/api

### Security Resources

**OWASP:**
- Top 10: https://owasp.org/www-project-top-ten/
- API Security: https://owasp.org/www-project-api-security/

**General Webhook Security:**
- HMAC Guide: https://www.bindbee.dev/blog/how-hmac-secures-your-webhooks-a-comprehensive-guide
- Security Checklist: https://hookdeck.com/webhooks/guides/webhooks-security-checklist

---

## 8. Quick Reference Commands

### Deploy Secure Cloud Run Service

```bash
gcloud run deploy SERVICE_NAME \
  --image=gcr.io/pgp-live/SERVICE_NAME:latest \
  --region=us-central1 \
  --no-allow-unauthenticated \
  --ingress=internal-and-cloud-load-balancing \
  --service-account=SERVICE_ACCOUNT@pgp-live.iam.gserviceaccount.com \
  --set-secrets="SECRET_NAME=PGP_SECRET_NAME_v1:latest" \
  --set-env-vars="ENVIRONMENT=production" \
  --max-instances=10 \
  --min-instances=0 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60s \
  --concurrency=80
```

### Grant Service-to-Service Access

```bash
gcloud run services add-iam-policy-binding RECEIVING_SERVICE \
  --member="serviceAccount:CALLING_SERVICE@pgp-live.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=us-central1
```

### Create Cloud Armor Security Policy

```bash
# Create policy
gcloud compute security-policies create POLICY_NAME \
  --description="Security policy description"

# IP whitelist
gcloud compute security-policies rules create 100 \
  --security-policy=POLICY_NAME \
  --expression="inIpRange(origin.ip, 'IP_ADDRESS/32')" \
  --action=allow

# Rate limiting
gcloud compute security-policies rules create 1000 \
  --security-policy=POLICY_NAME \
  --expression="true" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP

# WAF rules
gcloud compute security-policies rules create 3000 \
  --security-policy=POLICY_NAME \
  --expression="evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})" \
  --action=deny-403
```

### Check Service Configuration

```bash
# View service details
gcloud run services describe SERVICE_NAME --region=us-central1

# Check IAM policy
gcloud run services get-iam-policy SERVICE_NAME --region=us-central1

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=SERVICE_NAME" --limit=50 --format=json
```

---

## Summary

This comprehensive guide provides:

1. ✅ **Authentication & Authorization**: IAM best practices, service accounts, `--no-allow-unauthenticated`
2. ✅ **Network Security**: VPC SC, Cloud Armor, Load Balancer configuration
3. ✅ **Defense in Depth**: Multiple security layers (HMAC + IAM + IP + WAF + DDoS)
4. ✅ **Payment-Specific Security**: NowPayments IPN, Telegram Bot, PCI DSS compliance
5. ✅ **Implementation Checklist**: Step-by-step deployment guide
6. ✅ **Architecture Recommendations**: Complete security architecture for PGP_v1

**Next Steps:**
1. Review this document with your team
2. Follow Phase 1 checklist to implement foundation
3. Gradually add layers (Phase 2-3) based on risk assessment
4. Test thoroughly before production deployment
5. Monitor and iterate based on real-world traffic

**Key Takeaway:**
Security is not a one-time setup but an ongoing process. Start with essential layers (HMAC, IAM, HTTPS) and progressively add more as your system matures and requirements evolve.
