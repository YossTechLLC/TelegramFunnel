# 🔒 PGP_v1 Network Security Implementation Checklist

**⚠️ CRITICAL SECURITY ISSUE IDENTIFIED:**
Current deployment uses `--allow-unauthenticated` flag which exposes all services publicly without authentication. Services handling sensitive financial data (payment webhooks) **MUST NOT** be deployed with this flag.

**Status:** 🔴 **HIGH PRIORITY - SECURITY VULNERABILITY**

---

## 📋 Executive Summary

### Current State (INSECURE)
```bash
# ❌ CURRENT: Insecure deployment
gcloud run deploy pgp-service \
  --allow-unauthenticated     # PUBLIC ACCESS - NO AUTHENTICATION
  --region us-central1
```

### Target State (SECURE)
```bash
# ✅ TARGET: Multi-layered security
Internet → Cloud Load Balancer → Cloud Armor → IAM Auth → Cloud Run Service
          (HTTPS/SSL)         (DDoS/WAF/IP)  (Identity)   (HMAC verification)
```

### Security Concerns Addressed
1. ✅ **No `--allow-unauthenticated`**: Remove public access flag
2. ✅ **VPC Service Controls**: Implement service perimeters to prevent data exfiltration
3. ✅ **Cloud Armor**: Add DDoS protection, WAF, and advanced rate limiting
4. ✅ **IAM Authentication**: Require authenticated service accounts for all calls
5. ✅ **Defense in Depth**: Layer multiple security mechanisms

---

## 🎯 Implementation Strategy

### Phase 1: Foundation (Week 1) - **PRIORITY**
- Remove `--allow-unauthenticated` flag
- Implement IAM authentication for service-to-service calls
- Verify HMAC authentication in application code
- Configure proper service accounts with least privilege

### Phase 2: Network Security (Week 2)
- Deploy Cloud Load Balancer for external-facing services
- Configure Cloud Armor with DDoS protection and WAF rules
- Implement IP whitelisting at Cloud Armor level
- Set up SSL/TLS certificates

### Phase 3: Advanced Security (Week 3-4)
- Implement VPC Service Controls (optional but recommended)
- Configure Cloud NAT for predictable egress IPs
- Set up comprehensive monitoring and alerting
- Implement rate limiting and circuit breakers

### Phase 4: Documentation & Compliance (Ongoing)
- Document security architecture
- Create runbooks for security incidents
- Review PCI DSS compliance requirements
- Conduct security audit

---

## 📝 Detailed Checklist

## PHASE 1: FOUNDATION - IAM AUTHENTICATION & SERVICE ACCOUNTS

### 1.1 Update Service Account Configuration

**Context:** Each Cloud Run service needs a dedicated service account with minimal permissions.

#### ✅ Task: Create Dedicated Service Accounts

```bash
# For each PGP service, create a dedicated service account
# Example for PGP_NP_IPN_v1 (NowPayments webhook receiver)

# 1. Create service account
gcloud iam service-accounts create pgp-np-ipn-v1-sa \
  --display-name="PGP NowPayments IPN Service Account" \
  --description="Service account for PGP_NP_IPN_v1 Cloud Run service" \
  --project=pgp-live

# 2. Grant minimal permissions
# - Cloud SQL Client (to connect to database)
# - Secret Manager Secret Accessor (to read secrets)
# - Cloud Tasks Enqueuer (to send tasks to orchestrator)

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-np-ipn-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-np-ipn-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-np-ipn-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"
```

**Service Accounts to Create:**
- [ ] `pgp-server-v1-sa` - Main Telegram bot server
- [ ] `pgp-web-v1-sa` - Frontend web application
- [ ] `pgp-webapi-v1-sa` - Web API backend
- [ ] `pgp-np-ipn-v1-sa` - NowPayments IPN webhook receiver
- [ ] `pgp-orchestrator-v1-sa` - Payment orchestrator
- [ ] `pgp-invite-v1-sa` - Invite handler
- [ ] `pgp-split1-v1-sa`, `pgp-split2-v1-sa`, `pgp-split3-v1-sa` - Split services
- [ ] `pgp-hostpay1-v1-sa`, `pgp-hostpay2-v1-sa`, `pgp-hostpay3-v1-sa` - HostPay services
- [ ] `pgp-accumulator-v1-sa` - Payout accumulator
- [ ] `pgp-batchprocessor-v1-sa` - Batch processor
- [ ] `pgp-microbatchprocessor-v1-sa` - Micro batch processor
- [ ] `pgp-notifications-v1-sa` - Notification service
- [ ] `pgp-broadcast-v1-sa` - Broadcast scheduler

**Checklist:**
- [ ] Create all 17 service accounts with descriptive names
- [ ] Document service account → service mapping in SECRET_SCHEME.md
- [ ] Grant minimal required IAM roles to each service account
- [ ] Test service account permissions in development environment

---

### 1.2 Configure IAM Invoker Permissions

**Context:** For Cloud Run → Cloud Run service-to-service calls, the calling service's service account needs `roles/run.invoker` permission on the target service.

#### ✅ Task: Grant Invoker Permissions

**Service Communication Flow:**
```
PGP_NP_IPN_v1 → PGP_ORCHESTRATOR_v1 → {PGP_INVITE_v1, PGP_SPLIT1_v1}
PGP_ORCHESTRATOR_v1 → PGP_NOTIFICATIONS_v1 → PGP_SERVER_v1
PGP_ACCUMULATOR_v1 → PGP_BATCHPROCESSOR_v1
```

**Example: Allow PGP_NP_IPN_v1 to call PGP_ORCHESTRATOR_v1**
```bash
gcloud run services add-iam-policy-binding pgp-orchestrator-v1 \
  --region=us-central1 \
  --member="serviceAccount:pgp-np-ipn-v1-sa@pgp-live.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**Checklist - Grant Invoker Permissions:**

**Payment Processing Pipeline:**
- [ ] `pgp-np-ipn-v1-sa` → `pgp-orchestrator-v1` (invoker)
- [ ] `pgp-orchestrator-v1-sa` → `pgp-invite-v1` (invoker)
- [ ] `pgp-orchestrator-v1-sa` → `pgp-split1-v1` (invoker)
- [ ] `pgp-split1-v1-sa` → `pgp-split2-v1` (invoker)
- [ ] `pgp-split2-v1-sa` → `pgp-split3-v1` (invoker)

**Payout Pipeline:**
- [ ] `pgp-accumulator-v1-sa` → `pgp-hostpay1-v1` (invoker)
- [ ] `pgp-hostpay1-v1-sa` → `pgp-hostpay2-v1` (invoker)
- [ ] `pgp-hostpay2-v1-sa` → `pgp-hostpay3-v1` (invoker)
- [ ] `pgp-accumulator-v1-sa` → `pgp-batchprocessor-v1` (invoker)
- [ ] `pgp-batchprocessor-v1-sa` → `pgp-microbatchprocessor-v1` (invoker)

**Notification Pipeline:**
- [ ] `pgp-orchestrator-v1-sa` → `pgp-notifications-v1` (invoker)
- [ ] `pgp-notifications-v1-sa` → `pgp-server-v1` (invoker)

**Broadcast System:**
- [ ] `pgp-broadcast-v1-sa` → `pgp-server-v1` (invoker)

**Web API:**
- [ ] `pgp-web-v1-sa` → `pgp-webapi-v1` (invoker)

---

### 1.3 Update Deployment Script to Remove `--allow-unauthenticated`

**Context:** Current `deploy_all_pgp_services.sh` uses `--allow-unauthenticated` (line 101). This must be changed based on service type.

#### ✅ Task: Update deploy_service() Function

**File:** `/TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh`

**Current (INSECURE):**
```bash
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --platform managed \
  --region "$REGION" \
  --memory "$MEMORY" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --timeout "$TIMEOUT" \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION" \
  --add-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
  --allow-unauthenticated \    # ❌ REMOVE THIS
  --quiet
```

**Updated (SECURE):**
```bash
# Add authentication parameter to deploy_service function
deploy_service() {
    local SERVICE_NAME=$1
    local SERVICE_DIR=$2
    local MEMORY=${3:-512Mi}
    local MIN_INSTANCES=${4:-0}
    local MAX_INSTANCES=${5:-10}
    local TIMEOUT=${6:-300}
    local AUTHENTICATION=${7:-"require"}  # NEW: "require" or "allow-unauthenticated"
    local SERVICE_ACCOUNT=${8:-""}        # NEW: Service account email

    # Determine authentication flag
    local AUTH_FLAG=""
    if [ "$AUTHENTICATION" = "allow-unauthenticated" ]; then
        AUTH_FLAG="--allow-unauthenticated"
        echo "⚠️  WARNING: Deploying with public access (--allow-unauthenticated)"
    else
        AUTH_FLAG="--no-allow-unauthenticated"
        echo "🔒 Deploying with authentication required"
    fi

    # Build service account flag
    local SA_FLAG=""
    if [ -n "$SERVICE_ACCOUNT" ]; then
        SA_FLAG="--service-account=${SERVICE_ACCOUNT}"
    fi

    # Deploy with authentication settings
    gcloud run deploy "$SERVICE_NAME" \
      --source . \
      --platform managed \
      --region "$REGION" \
      --memory "$MEMORY" \
      --min-instances "$MIN_INSTANCES" \
      --max-instances "$MAX_INSTANCES" \
      --timeout "$TIMEOUT" \
      --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION" \
      --add-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
      $AUTH_FLAG \
      $SA_FLAG \
      --quiet
}
```

**Service Authentication Configuration:**

**🌐 Public-Facing Services (Allow Unauthenticated + Cloud Armor):**
```bash
# Frontend web application - accessed by users
deploy_service "pgp-web-v1" "$BASE_DIR/PGP_WEB_v1" "128Mi" "0" "5" "60" \
  "allow-unauthenticated" "pgp-web-v1-sa@pgp-live.iam.gserviceaccount.com"
```

**🔒 Webhook Endpoints (Require Auth via Load Balancer + Cloud Armor):**
```bash
# NowPayments IPN - external webhook with HMAC + Cloud Armor protection
# NOTE: Will require Load Balancer for Cloud Armor integration
deploy_service "pgp-np-ipn-v1" "$BASE_DIR/PGP_NP_IPN_v1" "512Mi" "0" "20" "300" \
  "require" "pgp-np-ipn-v1-sa@pgp-live.iam.gserviceaccount.com"
```

**🔐 Internal Services (Require Auth - Service-to-Service Only):**
```bash
# All internal services require IAM authentication
deploy_service "pgp-orchestrator-v1" "$BASE_DIR/PGP_ORCHESTRATOR_v1" "512Mi" "0" "20" "300" \
  "require" "pgp-orchestrator-v1-sa@pgp-live.iam.gserviceaccount.com"
```

**Checklist:**
- [ ] Update `deploy_service()` function to support authentication parameter
- [ ] Update `deploy_service()` function to support service account parameter
- [ ] Configure authentication for each service based on its purpose:
  - [ ] **Public:** `pgp-web-v1` (frontend - allow-unauthenticated)
  - [ ] **Webhook:** `pgp-np-ipn-v1` (require auth via LB)
  - [ ] **Webhook:** `pgp-server-v1` (Telegram webhook - require auth via LB)
  - [ ] **Internal:** All other services (require auth)
- [ ] Test deployment script with new parameters
- [ ] Document authentication decisions in DECISIONS.md

---

### 1.4 Update Application Code for Service-to-Service Authentication

**Context:** When Cloud Run services call each other with `--no-allow-unauthenticated`, they must include an identity token in the `Authorization` header.

#### ✅ Task: Implement Identity Token Fetching

**Create:** `/PGP_COMMON/auth/service_auth.py`

```python
#!/usr/bin/env python
"""
Service-to-service authentication for Cloud Run.
Generates identity tokens for calling authenticated Cloud Run services.
"""
import logging
import requests
from google.auth import compute_engine
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


class ServiceAuthenticator:
    """
    Generates identity tokens for authenticating to Cloud Run services.

    Usage:
        auth = ServiceAuthenticator()
        token = auth.get_identity_token("https://pgp-orchestrator-v1-xxx.run.app")

        response = requests.post(
            "https://pgp-orchestrator-v1-xxx.run.app/webhook",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
    """

    def __init__(self):
        """Initialize service authenticator using compute engine credentials."""
        self._credentials_cache = {}
        logger.info("🔒 [AUTH] Service authenticator initialized")

    def get_identity_token(self, target_audience: str) -> str:
        """
        Get identity token for calling target Cloud Run service.

        Args:
            target_audience: URL of target Cloud Run service
                           (e.g., "https://pgp-orchestrator-v1-xxx.run.app")

        Returns:
            Identity token (JWT) for Authorization header

        Raises:
            Exception: If token generation fails
        """
        try:
            # Check cache
            if target_audience in self._credentials_cache:
                credentials = self._credentials_cache[target_audience]
            else:
                # Create credentials with target audience
                credentials = compute_engine.IDTokenCredentials(
                    Request(),
                    target_audience=target_audience
                )
                self._credentials_cache[target_audience] = credentials

            # Refresh token if expired
            if not credentials.valid:
                credentials.refresh(Request())

            token = credentials.token
            logger.debug(f"✅ [AUTH] Identity token generated for {target_audience}")
            return token

        except Exception as e:
            logger.error(f"❌ [AUTH] Failed to generate identity token: {e}")
            raise

    def get_authenticated_session(self, target_audience: str) -> requests.Session:
        """
        Get requests.Session with automatic identity token injection.

        Args:
            target_audience: URL of target Cloud Run service

        Returns:
            Configured requests.Session with auth header
        """
        session = requests.Session()
        token = self.get_identity_token(target_audience)
        session.headers.update({
            "Authorization": f"Bearer {token}"
        })
        return session


# Global authenticator instance
_authenticator = None


def get_authenticator() -> ServiceAuthenticator:
    """Get or create global ServiceAuthenticator instance."""
    global _authenticator
    if _authenticator is None:
        _authenticator = ServiceAuthenticator()
    return _authenticator


def call_authenticated_service(
    url: str,
    method: str = "POST",
    json_data: dict = None,
    timeout: int = 30
) -> requests.Response:
    """
    Call authenticated Cloud Run service with automatic token injection.

    Args:
        url: Full URL of target endpoint
        method: HTTP method (GET, POST, etc.)
        json_data: JSON payload
        timeout: Request timeout in seconds

    Returns:
        requests.Response object

    Example:
        response = call_authenticated_service(
            url="https://pgp-orchestrator-v1-xxx.run.app/webhook",
            method="POST",
            json_data={"order_id": "PGP-123"}
        )
    """
    try:
        # Extract base URL for token audience
        from urllib.parse import urlparse
        parsed = urlparse(url)
        target_audience = f"{parsed.scheme}://{parsed.netloc}"

        # Get authenticator and token
        auth = get_authenticator()
        token = auth.get_identity_token(target_audience)

        # Make authenticated request
        response = requests.request(
            method=method,
            url=url,
            json=json_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=timeout
        )

        logger.info(f"✅ [AUTH] Authenticated request to {url}: {response.status_code}")
        return response

    except Exception as e:
        logger.error(f"❌ [AUTH] Authenticated request failed: {e}")
        raise
```

**Update Service Code to Use Authentication:**

**Example: PGP_NP_IPN_v1 calling PGP_ORCHESTRATOR_v1**

**Before (INSECURE):**
```python
# Old code - no authentication
response = requests.post(
    orchestrator_url,
    json=payload,
    timeout=30
)
```

**After (SECURE):**
```python
from PGP_COMMON.auth.service_auth import call_authenticated_service

# New code - with IAM authentication
response = call_authenticated_service(
    url=orchestrator_url,
    method="POST",
    json_data=payload,
    timeout=30
)
```

**Checklist:**
- [ ] Create `/PGP_COMMON/auth/` directory
- [ ] Create `service_auth.py` with ServiceAuthenticator class
- [ ] Add `google-auth` to requirements.txt for all services
- [ ] Update all inter-service calls to use `call_authenticated_service()`
  - [ ] PGP_NP_IPN_v1 → PGP_ORCHESTRATOR_v1
  - [ ] PGP_ORCHESTRATOR_v1 → PGP_INVITE_v1
  - [ ] PGP_ORCHESTRATOR_v1 → PGP_SPLIT1_v1
  - [ ] PGP_ORCHESTRATOR_v1 → PGP_NOTIFICATIONS_v1
  - [ ] PGP_NOTIFICATIONS_v1 → PGP_SERVER_v1
  - [ ] All other service-to-service calls
- [ ] Test service-to-service authentication in development
- [ ] Document authentication flow in architecture docs

---

### 1.5 Verify HMAC Authentication Implementation

**Context:** HMAC authentication is already implemented in `PGP_SERVER_v1/security/hmac_auth.py`. Need to ensure it's properly applied and documented.

#### ✅ Task: Audit HMAC Implementation

**Current Implementation Review:**
- [x] HMAC-SHA256 signature generation ✅ (line 41-61 in hmac_auth.py)
- [x] Timestamp validation (±5 minutes) ✅ (line 63-98 in hmac_auth.py)
- [x] Timing-safe comparison ✅ (line 127 in hmac_auth.py)
- [x] Flask decorator for easy application ✅ (line 134-186 in hmac_auth.py)

**Checklist:**
- [ ] Verify HMAC is applied to all webhook endpoints:
  - [ ] `/webhooks/notification` (PGP_ORCHESTRATOR_v1 → PGP_SERVER_v1)
  - [ ] `/webhooks/nowpayments-ipn` (NowPayments → PGP_NP_IPN_v1)
  - [ ] `/webhooks/telegram` (Telegram → PGP_SERVER_v1)
- [ ] Verify HMAC secrets are stored in Secret Manager (not env vars)
- [ ] Test HMAC signature generation in calling services
- [ ] Test HMAC signature validation in receiving services
- [ ] Document HMAC usage in `/PGP_SERVER_v1/security/HMAC_TIMESTAMP_SECURITY.md`
- [ ] Add HMAC signature generation to `PGP_COMMON` for reuse across services

---

## PHASE 2: NETWORK SECURITY - LOAD BALANCER & CLOUD ARMOR

**⚠️ IMPORTANT:** Cloud Armor can **ONLY** be used with Cloud Load Balancer. It **CANNOT** be directly attached to Cloud Run services.

### 2.1 Deploy Cloud Load Balancer for External-Facing Services

**Context:** External webhook endpoints need Load Balancer to enable Cloud Armor protection.

#### Services Requiring Load Balancer:
1. **PGP_NP_IPN_v1** - NowPayments IPN webhook (external)
2. **PGP_SERVER_v1** - Telegram bot webhook (external)
3. **PGP_WEB_v1** - Frontend web app (public)

#### ✅ Task: Create Load Balancer Configuration

**Architecture:**
```
Internet → Cloud Load Balancer → Cloud Armor → Serverless NEG → Cloud Run
          (HTTPS/SSL cert)       (DDoS/WAF)    (Backend)       (Service)
```

**Step 1: Create Serverless NEG (Network Endpoint Group)**

```bash
# For PGP_NP_IPN_v1
gcloud compute network-endpoint-groups create pgp-np-ipn-v1-neg \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=pgp-np-ipn-v1

# For PGP_SERVER_v1 (Telegram webhook)
gcloud compute network-endpoint-groups create pgp-server-v1-neg \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=pgp-server-v1

# For PGP_WEB_v1 (Frontend)
gcloud compute network-endpoint-groups create pgp-web-v1-neg \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=pgp-web-v1
```

**Step 2: Create Backend Services**

```bash
# For PGP_NP_IPN_v1
gcloud compute backend-services create pgp-np-ipn-v1-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --enable-cdn=false

gcloud compute backend-services add-backend pgp-np-ipn-v1-backend \
  --global \
  --network-endpoint-group=pgp-np-ipn-v1-neg \
  --network-endpoint-group-region=us-central1

# For PGP_SERVER_v1
gcloud compute backend-services create pgp-server-v1-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --enable-cdn=false

gcloud compute backend-services add-backend pgp-server-v1-backend \
  --global \
  --network-endpoint-group=pgp-server-v1-neg \
  --network-endpoint-group-region=us-central1

# For PGP_WEB_v1
gcloud compute backend-services create pgp-web-v1-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --enable-cdn=true  # Enable CDN for frontend

gcloud compute backend-services add-backend pgp-web-v1-backend \
  --global \
  --network-endpoint-group=pgp-web-v1-neg \
  --network-endpoint-group-region=us-central1
```

**Step 3: Create URL Maps**

```bash
# Create URL map with path-based routing
gcloud compute url-maps create pgp-lb-url-map \
  --default-service=pgp-web-v1-backend

# Add path rules for webhooks
gcloud compute url-maps add-path-matcher pgp-lb-url-map \
  --default-service=pgp-web-v1-backend \
  --path-matcher-name=pgp-webhooks \
  --path-rules="/webhook/nowpayments/*=pgp-np-ipn-v1-backend,/webhook/telegram/*=pgp-server-v1-backend"
```

**Step 4: Create SSL Certificate**

```bash
# Option A: Google-managed SSL certificate (recommended)
gcloud compute ssl-certificates create pgp-ssl-cert \
  --domains=paygateprime.com,www.paygateprime.com,webhooks.paygateprime.com \
  --global

# Option B: Self-managed certificate (if you have existing cert)
# gcloud compute ssl-certificates create pgp-ssl-cert \
#   --certificate=/path/to/cert.pem \
#   --private-key=/path/to/key.pem \
#   --global
```

**Step 5: Create HTTPS Proxy**

```bash
gcloud compute target-https-proxies create pgp-https-proxy \
  --url-map=pgp-lb-url-map \
  --ssl-certificates=pgp-ssl-cert
```

**Step 6: Create Forwarding Rule (Load Balancer Frontend)**

```bash
# Reserve static IP
gcloud compute addresses create pgp-lb-ip \
  --ip-version=IPV4 \
  --global

# Get IP address
gcloud compute addresses describe pgp-lb-ip --global --format="get(address)"

# Create forwarding rule
gcloud compute forwarding-rules create pgp-https-forwarding-rule \
  --address=pgp-lb-ip \
  --target-https-proxy=pgp-https-proxy \
  --global \
  --ports=443
```

**Step 7: Update Cloud Run Ingress Settings**

```bash
# Restrict Cloud Run to only accept traffic from Load Balancer
gcloud run services update pgp-np-ipn-v1 \
  --ingress=internal-and-cloud-load-balancing \
  --region=us-central1

gcloud run services update pgp-server-v1 \
  --ingress=internal-and-cloud-load-balancing \
  --region=us-central1

gcloud run services update pgp-web-v1 \
  --ingress=internal-and-cloud-load-balancing \
  --region=us-central1
```

**Checklist:**
- [ ] Create Serverless NEGs for all external-facing services
- [ ] Create Backend Services with appropriate settings (CDN for frontend)
- [ ] Create URL map with path-based routing for webhooks
- [ ] Provision SSL certificate for custom domains
- [ ] Create HTTPS proxy
- [ ] Create forwarding rule with static IP
- [ ] Update Cloud Run ingress settings to `internal-and-cloud-load-balancing`
- [ ] **Update DNS records** to point to Load Balancer IP (⚠️ requires Cloudflare changes)
- [ ] Test Load Balancer routing to each service
- [ ] Verify SSL certificate provisioning (can take 10-60 minutes)

---

### 2.2 Configure Cloud Armor Security Policy

**Context:** Cloud Armor provides DDoS protection, WAF (Web Application Firewall), IP whitelisting, and rate limiting.

#### ✅ Task: Create Cloud Armor Security Policy

**Step 1: Create Base Security Policy**

```bash
gcloud compute security-policies create pgp-security-policy \
  --description="Security policy for PayGatePrime webhook and web services" \
  --type=CLOUD_ARMOR
```

**Step 2: Configure Default Rule (Deny by Default)**

```bash
# Default rule: Deny all traffic (will add explicit allow rules next)
gcloud compute security-policies rules update 2147483647 \
  --security-policy=pgp-security-policy \
  --action=deny-403
```

**Step 3: Add IP Whitelist Rules**

**Allow NowPayments IPN IPs:**
```bash
gcloud compute security-policies rules create 1000 \
  --security-policy=pgp-security-policy \
  --description="Allow NowPayments IPN servers" \
  --src-ip-ranges="52.29.216.31/32,18.157.160.115/32,3.126.138.126/32" \
  --action=allow
```

**Allow Telegram Bot API IPs:**
```bash
gcloud compute security-policies rules create 1100 \
  --security-policy=pgp-security-policy \
  --description="Allow Telegram Bot API servers" \
  --src-ip-ranges="149.154.160.0/20,91.108.4.0/22" \
  --action=allow
```

**Allow All IPs for Frontend (Public Access):**
```bash
gcloud compute security-policies rules create 1200 \
  --security-policy=pgp-security-policy \
  --description="Allow all users to access frontend" \
  --expression="request.path.matches('/') || request.path.matches('/static/.*')" \
  --action=allow
```

**Step 4: Add Rate Limiting Rules**

**Rate limit NowPayments webhook (prevent abuse):**
```bash
gcloud compute security-policies rules create 2000 \
  --security-policy=pgp-security-policy \
  --description="Rate limit NowPayments IPN to 100 req/min" \
  --expression="request.path.matches('/webhook/nowpayments/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP
```

**Rate limit Telegram webhook:**
```bash
gcloud compute security-policies rules create 2100 \
  --security-policy=pgp-security-policy \
  --description="Rate limit Telegram webhook to 30 req/sec" \
  --expression="request.path.matches('/webhook/telegram/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=30 \
  --rate-limit-threshold-interval-sec=1 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP
```

**Rate limit frontend (prevent DDoS):**
```bash
gcloud compute security-policies rules create 2200 \
  --security-policy=pgp-security-policy \
  --description="Rate limit frontend to 1000 req/min per IP" \
  --expression="request.path.matches('/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=1000 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP
```

**Step 5: Enable Adaptive Protection (ML-based DDoS Detection)**

```bash
gcloud compute security-policies update pgp-security-policy \
  --enable-layer7-ddos-defense \
  --layer7-ddos-defense-rule-visibility=STANDARD
```

**Step 6: Add Pre-configured WAF Rules (OWASP Top 10)**

```bash
# SQL Injection protection
gcloud compute security-policies rules create 3000 \
  --security-policy=pgp-security-policy \
  --description="Block SQL injection attempts" \
  --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
  --action=deny-403

# Cross-Site Scripting (XSS) protection
gcloud compute security-policies rules create 3100 \
  --security-policy=pgp-security-policy \
  --description="Block XSS attempts" \
  --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
  --action=deny-403

# Local File Inclusion (LFI) protection
gcloud compute security-policies rules create 3200 \
  --security-policy=pgp-security-policy \
  --description="Block LFI attempts" \
  --expression="evaluatePreconfiguredExpr('lfi-v33-stable')" \
  --action=deny-403

# Remote Code Execution (RCE) protection
gcloud compute security-policies rules create 3300 \
  --security-policy=pgp-security-policy \
  --description="Block RCE attempts" \
  --expression="evaluatePreconfiguredExpr('rce-v33-stable')" \
  --action=deny-403

# Protocol attack protection
gcloud compute security-policies rules create 3400 \
  --security-policy=pgp-security-policy \
  --description="Block protocol attacks" \
  --expression="evaluatePreconfiguredExpr('protocolattack-v33-stable')" \
  --action=deny-403
```

**Step 7: Attach Security Policy to Backend Services**

```bash
# Attach to NowPayments IPN backend
gcloud compute backend-services update pgp-np-ipn-v1-backend \
  --security-policy=pgp-security-policy \
  --global

# Attach to Telegram webhook backend
gcloud compute backend-services update pgp-server-v1-backend \
  --security-policy=pgp-security-policy \
  --global

# Attach to frontend backend
gcloud compute backend-services update pgp-web-v1-backend \
  --security-policy=pgp-security-policy \
  --global
```

**Checklist:**
- [ ] Create base Cloud Armor security policy
- [ ] Configure default deny rule
- [ ] Add IP whitelist rules for NowPayments
- [ ] Add IP whitelist rules for Telegram
- [ ] Add allow rule for frontend public access
- [ ] Configure rate limiting for each service type
- [ ] Enable Adaptive Protection (ML-based DDoS detection)
- [ ] Add OWASP Top 10 WAF rules (SQLi, XSS, LFI, RCE, Protocol)
- [ ] Attach security policy to all backend services
- [ ] Test Cloud Armor rules (verify allowed IPs work, blocked IPs fail)
- [ ] Monitor Cloud Armor logs for blocked requests

---

### 2.3 Configure Monitoring for Cloud Armor

**Context:** Cloud Armor generates security telemetry that should be monitored for threats.

#### ✅ Task: Set Up Cloud Armor Monitoring

**Step 1: Create Log-Based Metrics**

```bash
# Metric for blocked requests
gcloud logging metrics create cloud_armor_blocked_requests \
  --description="Count of requests blocked by Cloud Armor" \
  --log-filter='resource.type="http_load_balancer"
jsonPayload.enforcedSecurityPolicy.name="pgp-security-policy"
jsonPayload.enforcedSecurityPolicy.outcome="DENY"'

# Metric for rate limited requests
gcloud logging metrics create cloud_armor_rate_limited \
  --description="Count of requests rate limited by Cloud Armor" \
  --log-filter='resource.type="http_load_balancer"
jsonPayload.enforcedSecurityPolicy.name="pgp-security-policy"
jsonPayload.enforcedSecurityPolicy.outcome="RATE_LIMIT"'
```

**Step 2: Create Alerting Policies**

```bash
# Alert on high number of blocked requests (potential attack)
gcloud alpha monitoring policies create \
  --notification-channels=NOTIFICATION_CHANNEL_ID \
  --display-name="Cloud Armor - High Blocked Request Rate" \
  --condition-display-name="Blocked requests > 100/min" \
  --condition-threshold-value=100 \
  --condition-threshold-duration=60s \
  --condition-filter='metric.type="logging.googleapis.com/user/cloud_armor_blocked_requests"
resource.type="http_load_balancer"'
```

**Checklist:**
- [ ] Create log-based metrics for blocked requests
- [ ] Create log-based metrics for rate-limited requests
- [ ] Set up alerting policy for high blocked request rate (> 100/min)
- [ ] Set up alerting policy for rate limit triggers
- [ ] Configure notification channels (email, Slack, PagerDuty)
- [ ] Create Cloud Armor dashboard in Cloud Monitoring
- [ ] Document monitoring and alerting in runbook

---

## PHASE 3: ADVANCED SECURITY - VPC SERVICE CONTROLS

**⚠️ NOTE:** VPC Service Controls (VPC-SC) is an **advanced security feature** that prevents data exfiltration. It's recommended for high-compliance environments (PCI DSS Level 1, HIPAA, etc.) but adds operational complexity.

**Recommendation:** Implement VPC-SC **only if** required by compliance or security policy. For most use cases, IAM + Cloud Armor + HMAC is sufficient.

### 3.1 Understand VPC Service Controls (VPC-SC)

**What is VPC-SC?**
- Creates a security perimeter around GCP services
- Prevents data exfiltration to unauthorized projects
- Requires services to be within the same perimeter
- Blocks unauthorized API calls from outside the perimeter

**Trade-offs:**
- ✅ **Pros:** Maximum security, prevents insider threats, compliance requirement
- ❌ **Cons:** Complex setup, breaks Cloud Scheduler, requires all dependencies in perimeter

**Architectural Impact:**
```
┌─────────────────────────────────────────────────────────┐
│  VPC Service Controls Perimeter                        │
│                                                          │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐ │
│  │Cloud Run│  │Cloud SQL│  │Secret Mgr│  │Container │ │
│  │Services │  │Database │  │         │  │Registry  │ │
│  └─────────┘  └─────────┘  └──────────┘  └──────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
        ↑ Allowed                  ↑ Blocked
    Inside perimeter          Outside perimeter
```

#### ✅ Task: Evaluate VPC-SC Requirement

**Decision Matrix:**

| Requirement | VPC-SC Needed? |
|-------------|----------------|
| PCI DSS Level 1 compliance | ✅ Yes (recommended) |
| PCI DSS Level 2-4 compliance | ⚠️ Optional (IAM + Cloud Armor sufficient) |
| Processing > $6M annually | ✅ Yes (PCI Level 1 threshold) |
| Regulatory audit required | ✅ Yes |
| Standard e-commerce | ❌ No (IAM + Cloud Armor sufficient) |

**Checklist:**
- [ ] Determine if VPC-SC is required for compliance
- [ ] Understand VPC-SC limitations (Cloud Scheduler, external APIs)
- [ ] If VPC-SC is **NOT required**, skip to Phase 4
- [ ] If VPC-SC **IS required**, continue with Section 3.2

---

### 3.2 Implement VPC Service Controls (Optional)

**⚠️ SKIP THIS SECTION IF VPC-SC IS NOT REQUIRED**

#### ✅ Task: Create VPC Service Controls Perimeter

**Step 1: Create Access Policy**

```bash
# Create organization-level access policy (one-time setup)
gcloud access-context-manager policies create \
  --organization=YOUR_ORG_ID \
  --title="PayGatePrime Security Policy"
```

**Step 2: Create Service Perimeter**

```bash
# Get policy name
POLICY_NAME=$(gcloud access-context-manager policies list --format="value(name)")

# Create service perimeter
gcloud access-context-manager perimeters create pgp_perimeter \
  --title="PayGatePrime Service Perimeter" \
  --policy=$POLICY_NAME \
  --resources=projects/PROJECT_NUMBER \
  --restricted-services=run.googleapis.com,sqladmin.googleapis.com,secretmanager.googleapis.com,storage.googleapis.com,artifactregistry.googleapis.com \
  --enable-vpc-accessible-services \
  --vpc-allowed-services=run.googleapis.com,sqladmin.googleapis.com,secretmanager.googleapis.com
```

**Step 3: Add Ingress/Egress Rules**

```bash
# Allow ingress from NowPayments IPs
gcloud access-context-manager perimeters update pgp_perimeter \
  --add-ingress-policies=ingress_policy.yaml

# ingress_policy.yaml content:
# - ingressFrom:
#     sources:
#       - resource: "*"
#     identityType: ANY_IDENTITY
#   ingressTo:
#     resources:
#       - "*"
#     operations:
#       - serviceName: "run.googleapis.com"
#         methodSelectors:
#           - method: "*"
```

**Checklist (VPC-SC):**
- [ ] Create organization-level access policy
- [ ] Create service perimeter for PGP_v1 project
- [ ] Add all required GCP services to perimeter
- [ ] Configure ingress rules for external webhooks
- [ ] Configure egress rules for internal services
- [ ] Test Cloud Run service communication within perimeter
- [ ] Document VPC-SC configuration and limitations
- [ ] Create workaround for Cloud Scheduler (if used)

---

## PHASE 4: DOCUMENTATION & COMPLIANCE

### 4.1 Update Architecture Documentation

#### ✅ Task: Document Security Architecture

**Create:** `/THINK/SECURITY_ARCHITECTURE.md`

**Contents:**
- Network security diagram
- Authentication flow diagrams
- Service-to-service authentication
- Cloud Armor rules and rationale
- VPC-SC configuration (if implemented)
- Threat model and mitigations
- Compliance mapping (PCI DSS, GDPR, etc.)

**Checklist:**
- [ ] Create security architecture diagram (Mermaid or Draw.io)
- [ ] Document all security layers and their purpose
- [ ] Map security controls to threat scenarios
- [ ] Document emergency response procedures
- [ ] Create runbook for security incidents

---

### 4.2 Update Deployment Scripts

#### ✅ Task: Create Secure Deployment Templates

**Update:** `/TOOLS_SCRIPTS_TESTS/scripts/deploy_all_pgp_services.sh`

**Add:**
- Service account creation commands
- IAM policy binding commands
- Load Balancer setup commands (if not already scripted)
- Cloud Armor policy creation
- Verification steps

**Checklist:**
- [ ] Update deployment script with authentication flags
- [ ] Add service account creation to deployment script
- [ ] Add IAM policy binding to deployment script
- [ ] Add Load Balancer and Cloud Armor setup script
- [ ] Add post-deployment verification script
- [ ] Test full deployment from scratch in staging environment

---

### 4.3 Compliance Review

#### ✅ Task: Verify Security Controls

**PCI DSS Requirements (if applicable):**
- [ ] ✅ Requirement 1: Firewall configuration (Cloud Armor)
- [ ] ✅ Requirement 2: Strong authentication (IAM + HMAC)
- [ ] ✅ Requirement 3: Protect cardholder data (encryption at rest/transit)
- [ ] ✅ Requirement 4: Encrypt transmission of data (HTTPS/TLS)
- [ ] ✅ Requirement 6: Secure development (code review, vulnerability scanning)
- [ ] ✅ Requirement 7: Restrict access (IAM, least privilege)
- [ ] ✅ Requirement 8: Unique IDs (service accounts per service)
- [ ] ✅ Requirement 9: Physical access (N/A - Cloud Run managed)
- [ ] ✅ Requirement 10: Logging and monitoring (Cloud Logging, Cloud Armor logs)
- [ ] ✅ Requirement 11: Security testing (penetration testing, vulnerability scans)
- [ ] ✅ Requirement 12: Information security policy (this document)

**GDPR Requirements:**
- [ ] ✅ Data encryption (at rest and in transit)
- [ ] ✅ Access controls (IAM policies)
- [ ] ✅ Audit logging (Cloud Logging)
- [ ] ✅ Data breach notification procedures
- [ ] ✅ Right to be forgotten (implement data deletion)

---

## 📊 Verification & Testing

### Post-Implementation Testing Checklist

#### Authentication Testing
- [ ] Test IAM authentication between Cloud Run services
- [ ] Verify unauthenticated requests are rejected (401/403)
- [ ] Test service account permissions (ensure least privilege)
- [ ] Test identity token generation and expiration

#### Network Security Testing
- [ ] Test Load Balancer routing to each service
- [ ] Verify SSL/TLS certificate is valid and auto-renewing
- [ ] Test Cloud Armor IP whitelist (allowed IPs work, blocked IPs fail)
- [ ] Test Cloud Armor rate limiting (trigger rate limit, verify 429 response)
- [ ] Test Cloud Armor WAF rules (SQL injection, XSS attempts blocked)
- [ ] Verify DDoS Adaptive Protection is active

#### HMAC Testing
- [ ] Test HMAC signature validation on all webhook endpoints
- [ ] Test timestamp validation (reject old timestamps)
- [ ] Test signature tampering detection (modified payload rejected)
- [ ] Test missing signature/timestamp rejection

#### End-to-End Testing
- [ ] Test complete payment flow (NowPayments IPN → Orchestrator → Split → HostPay)
- [ ] Test notification flow (Orchestrator → Notifications → Server → Telegram)
- [ ] Test broadcast flow (Scheduler → Server → Telegram)
- [ ] Monitor Cloud Logging for errors and security events

#### Performance Testing
- [ ] Load test external webhook endpoints (NowPayments, Telegram)
- [ ] Verify rate limits trigger at expected thresholds
- [ ] Measure latency impact of Cloud Armor (should be < 10ms)
- [ ] Verify auto-scaling works under load

#### Security Audit
- [ ] Run vulnerability scan (GCP Security Command Center)
- [ ] Review IAM policies for over-permissive roles
- [ ] Review secret access logs (who accessed which secrets)
- [ ] Review Cloud Armor logs for blocked requests (potential attacks)
- [ ] Conduct penetration test (if budget allows)

---

## 🚨 Rollback Plan

**If issues occur during implementation:**

### Rollback Steps

1. **Quick Rollback (Emergency):**
   ```bash
   # Revert to allow-unauthenticated temporarily
   gcloud run services update SERVICE_NAME \
     --allow-unauthenticated \
     --region=us-central1
   ```

2. **Remove Load Balancer (if causing issues):**
   ```bash
   # Delete forwarding rule
   gcloud compute forwarding-rules delete pgp-https-forwarding-rule --global

   # Delete target proxy
   gcloud compute target-https-proxies delete pgp-https-proxy

   # Restore Cloud Run ingress
   gcloud run services update SERVICE_NAME \
     --ingress=all \
     --region=us-central1
   ```

3. **Remove Cloud Armor (if causing issues):**
   ```bash
   # Detach from backend service
   gcloud compute backend-services update BACKEND_NAME \
     --security-policy="" \
     --global
   ```

4. **Restore Previous Authentication:**
   - Revert code changes to remove identity token generation
   - Remove service account assignments
   - Restore `--allow-unauthenticated` flag

---

## 💰 Cost Estimate

### Monthly Cost Breakdown

**Load Balancer:**
- Forwarding rules: ~$18/month (per rule)
- Data processing: ~$0.008-$0.016/GB
- **Estimated:** $20-30/month per service

**Cloud Armor:**
- Policy rules: $5/month (first 5 rules free)
- Requests: $0.75 per million requests (first 1M free)
- Advanced DDoS protection: $50/month (optional)
- **Estimated:** $10-50/month

**Service Accounts:**
- Free (no cost)

**Cloud Logging:**
- First 50GB/month free
- $0.50/GB after 50GB
- **Estimated:** $0-20/month (depends on log volume)

**Total Estimated Cost:** ~$86-204/month for full security implementation

---

## 📚 Additional Resources

### Official Documentation
- [Cloud Run Authentication](https://cloud.google.com/run/docs/authenticating/service-to-service)
- [Cloud Armor Overview](https://cloud.google.com/armor/docs/cloud-armor-overview)
- [VPC Service Controls](https://cloud.google.com/vpc-service-controls/docs/overview)
- [PCI DSS on Google Cloud](https://cloud.google.com/security/compliance/pci-dss)
- [Cloud Run Security Best Practices](https://cloud.google.com/run/docs/securing/overview)

### Internal Documentation
- `/PGP_v1/SECRET_SCHEME.md` - Secret naming and configuration
- `/PGP_v1/NAMING_SCHEME.md` - Service naming conventions
- `/PGP_v1/PGP_SERVER_v1/security/HMAC_TIMESTAMP_SECURITY.md` - HMAC implementation
- `/PGP_v1/PGP_SERVER_v1/security/IP_WHITELIST_SECURITY.md` - IP whitelist configuration

---

## 🏁 Success Criteria

**Security implementation is complete when:**

✅ **Phase 1 Complete:**
- [ ] All 17 services have dedicated service accounts
- [ ] All inter-service calls use IAM authentication
- [ ] Zero services deployed with `--allow-unauthenticated` (except frontend)
- [ ] HMAC authentication verified on all webhook endpoints

✅ **Phase 2 Complete:**
- [ ] Load Balancer deployed and routing correctly
- [ ] SSL/TLS certificates provisioned and valid
- [ ] Cloud Armor policies active on all backend services
- [ ] IP whitelisting enforced for external webhooks
- [ ] Rate limiting tested and verified

✅ **Phase 3 Complete (Optional):**
- [ ] VPC Service Controls perimeter created (if required)
- [ ] All services communicating within perimeter
- [ ] Ingress/egress rules configured

✅ **Phase 4 Complete:**
- [ ] Security architecture documented
- [ ] Deployment scripts updated with security flags
- [ ] Compliance requirements mapped and verified
- [ ] Security testing completed successfully
- [ ] Monitoring and alerting configured

---

## ⚠️ REMAINING CONTEXT WARNING

**Current Token Usage:** ~43,000 / 200,000 tokens
**Remaining Context:** ~157,000 tokens

**Recommendation:** This checklist should be completed in stages. After completing each phase, consider compacting the conversation to free up context for implementation details.

---

**Document Version:** 1.0.0
**Last Updated:** 2025-01-18
**Owner:** PayGatePrime Security Team
**Status:** 🔴 Implementation Pending
