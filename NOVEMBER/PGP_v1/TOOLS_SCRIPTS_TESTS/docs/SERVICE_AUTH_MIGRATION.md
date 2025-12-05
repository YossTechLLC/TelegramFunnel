# 🔒 Service-to-Service Authentication Migration Guide

**Purpose:** Update PGP_v1 services to use IAM authentication for service-to-service calls
**Version:** 1.0.0
**Date:** 2025-01-18

---

## 📋 Overview

With the removal of `--allow-unauthenticated`, all Cloud Run services now require authentication. This guide shows how to update your code to use the new `PGP_COMMON.auth` module for making authenticated service-to-service calls.

### Before (INSECURE):
```python
# ❌ Old code - no authentication
response = requests.post(
    orchestrator_url,
    json=payload,
    timeout=30
)
```

### After (SECURE):
```python
# ✅ New code - with IAM authentication
from PGP_COMMON.auth import call_authenticated_service

response = call_authenticated_service(
    url=orchestrator_url,
    method="POST",
    json_data=payload,
    timeout=30
)
```

---

## 🎯 Quick Start

### Step 1: Add Dependency

Update `requirements.txt`:
```txt
google-auth>=2.30.0
requests>=2.31.0
```

### Step 2: Import Authentication Helper

```python
from PGP_COMMON.auth import call_authenticated_service
```

### Step 3: Replace All Service Calls

Replace all `requests.post()`, `requests.get()` calls to other Cloud Run services with `call_authenticated_service()`.

---

## 📝 Migration Examples by Service

### Example 1: PGP_NP_IPN_v1 → PGP_ORCHESTRATOR_v1

**File:** `/PGP_NP_IPN_v1/ipn_handler.py`

**Before:**
```python
import requests
import os

def forward_to_orchestrator(payment_data):
    """Forward payment to orchestrator service."""
    orchestrator_url = os.getenv('PGP_ORCHESTRATOR_URL')

    # ❌ INSECURE: No authentication
    response = requests.post(
        f"{orchestrator_url}/webhook/payment",
        json={
            "payment_id": payment_data['payment_id'],
            "status": payment_data['payment_status'],
            "order_id": payment_data['order_id'],
            "amount": payment_data['price_amount']
        },
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Orchestrator call failed: {response.status_code}")
```

**After:**
```python
import os
from PGP_COMMON.auth import call_authenticated_service

def forward_to_orchestrator(payment_data):
    """Forward payment to orchestrator service."""
    orchestrator_url = os.getenv('PGP_ORCHESTRATOR_URL')

    # ✅ SECURE: IAM authentication
    response = call_authenticated_service(
        url=f"{orchestrator_url}/webhook/payment",
        method="POST",
        json_data={
            "payment_id": payment_data['payment_id'],
            "status": payment_data['payment_status'],
            "order_id": payment_data['order_id'],
            "amount": payment_data['price_amount']
        },
        timeout=30
    )

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Orchestrator call failed: {response.status_code}")
```

---

### Example 2: PGP_ORCHESTRATOR_v1 → PGP_NOTIFICATIONS_v1

**File:** `/PGP_ORCHESTRATOR_v1/orchestrator.py`

**Before:**
```python
import requests

def send_payment_notification(user_id, channel_id, payment_type, payment_data):
    """Send payment notification via notification service."""
    notification_url = os.getenv('PGP_NOTIFICATIONS_URL')

    # ❌ INSECURE: No authentication
    response = requests.post(
        f"{notification_url}/notify/payment",
        json={
            "user_id": user_id,
            "channel_id": channel_id,
            "payment_type": payment_type,
            "payment_data": payment_data
        },
        timeout=15
    )

    return response.status_code == 200
```

**After:**
```python
from PGP_COMMON.auth import call_authenticated_service

def send_payment_notification(user_id, channel_id, payment_type, payment_data):
    """Send payment notification via notification service."""
    notification_url = os.getenv('PGP_NOTIFICATIONS_URL')

    # ✅ SECURE: IAM authentication
    response = call_authenticated_service(
        url=f"{notification_url}/notify/payment",
        method="POST",
        json_data={
            "user_id": user_id,
            "channel_id": channel_id,
            "payment_type": payment_type,
            "payment_data": payment_data
        },
        timeout=15
    )

    return response.status_code == 200
```

---

### Example 3: PGP_SPLIT1_v1 → PGP_SPLIT2_v1 (Pipeline)

**File:** `/PGP_SPLIT1_v1/split_handler.py`

**Before:**
```python
import requests

def forward_to_split2(split_data):
    """Forward to next split stage."""
    split2_url = os.getenv('PGP_SPLIT2_URL')

    # ❌ INSECURE: No authentication
    try:
        response = requests.post(
            f"{split2_url}/process/split",
            json=split_data,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call split2: {e}")
        raise
```

**After:**
```python
from PGP_COMMON.auth import call_authenticated_service
import requests

def forward_to_split2(split_data):
    """Forward to next split stage."""
    split2_url = os.getenv('PGP_SPLIT2_URL')

    # ✅ SECURE: IAM authentication
    try:
        response = call_authenticated_service(
            url=f"{split2_url}/process/split",
            method="POST",
            json_data=split_data,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call split2: {e}")
        raise
```

---

### Example 4: PGP_WEB_v1 → PGP_WEBAPI_v1 (Frontend to Backend)

**File:** `/PGP_WEB_v1/src/services/apiClient.ts` (TypeScript/React)

**Note:** For browser-based frontend calling backend API, we **CANNOT** use service account authentication. Instead, use **user authentication** (Firebase Auth, OAuth, etc.) or keep the WebAPI public with proper security (rate limiting, CORS, API keys).

**Recommendation for PGP_WEB_v1 → PGP_WEBAPI_v1:**
1. Keep PGP_WEBAPI_v1 as `allow-unauthenticated` (it's called from browser)
2. Implement user authentication (Firebase Auth tokens)
3. Use Cloud Armor for rate limiting and DDoS protection

**Alternative (if WebAPI needs to be authenticated):**
Deploy a **server-side BFF** (Backend-for-Frontend) that:
- Runs on Cloud Run with service account
- Calls PGP_WEBAPI_v1 with IAM authentication
- Exposed as public endpoint for browser

---

### Example 5: Cloud Tasks Usage (Async Task Queueing)

**File:** `/PGP_ORCHESTRATOR_v1/task_sender.py`

**Before:**
```python
from google.cloud import tasks_v2

def send_split_task(order_id, amount):
    """Send task to Split1 service via Cloud Tasks."""
    client = tasks_v2.CloudTasksClient()

    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f"{split1_url}/process/split",
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'order_id': order_id,
                'amount': amount
            }).encode()
        }
    }

    # ❌ MISSING: No authentication headers
    response = client.create_task(parent=queue_path, task=task)
    return response
```

**After:**
```python
from google.cloud import tasks_v2

def send_split_task(order_id, amount):
    """Send task to Split1 service via Cloud Tasks."""
    client = tasks_v2.CloudTasksClient()

    # ✅ SECURE: Add OIDC token for authentication
    task = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f"{split1_url}/process/split",
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'order_id': order_id,
                'amount': amount
            }).encode(),
            'oidc_token': {
                'service_account_email': 'pgp-orchestrator-v1-sa@pgp-live.iam.gserviceaccount.com',
                'audience': split1_url  # Target service URL
            }
        }
    }

    response = client.create_task(parent=queue_path, task=task)
    return response
```

---

## 🔍 Advanced Usage

### Using ServiceAuthenticator Directly

For advanced use cases where you need more control:

```python
from PGP_COMMON.auth import ServiceAuthenticator

class PaymentOrchestrator:
    def __init__(self):
        self.auth = ServiceAuthenticator()
        self.split1_url = os.getenv('PGP_SPLIT1_URL')

    def process_payment(self, payment_data):
        # Generate token for target service
        token = self.auth.get_identity_token(self.split1_url)

        # Make authenticated request with custom headers
        response = requests.post(
            f"{self.split1_url}/process/split",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Request-ID": self.generate_request_id(),
                "X-Correlation-ID": payment_data.get('correlation_id')
            },
            json=payment_data,
            timeout=60
        )

        return response
```

### Using Authenticated Session (Multiple Calls)

For services that make multiple calls to the same target:

```python
from PGP_COMMON.auth import get_authenticator

class BatchProcessor:
    def __init__(self):
        auth = get_authenticator()
        self.microbatch_url = os.getenv('PGP_MICROBATCHPROCESSOR_URL')
        self.session = auth.get_authenticated_session(self.microbatch_url)

    def process_batch(self, batch_items):
        results = []

        # Multiple calls reuse the same token (more efficient)
        for item in batch_items:
            response = self.session.post(
                f"/process/item",
                json=item
            )
            results.append(response.json())

        return results
```

---

## ✅ Migration Checklist

### For Each Service:

- [ ] Add `google-auth>=2.30.0` to `requirements.txt`
- [ ] Import `from PGP_COMMON.auth import call_authenticated_service`
- [ ] Find all `requests.post()` / `requests.get()` calls to other Cloud Run services
- [ ] Replace with `call_authenticated_service()`
- [ ] Update Cloud Tasks to use `oidc_token` for authentication
- [ ] Test service-to-service calls in development
- [ ] Verify IAM invoker permissions are configured
- [ ] Monitor logs for authentication errors after deployment

### Services Requiring Updates:

**Payment Processing Pipeline:**
- [ ] PGP_NP_IPN_v1 (calls → PGP_ORCHESTRATOR_v1)
- [ ] PGP_ORCHESTRATOR_v1 (calls → PGP_INVITE_v1, PGP_SPLIT1_v1, PGP_NOTIFICATIONS_v1)
- [ ] PGP_SPLIT1_v1 (calls → PGP_SPLIT2_v1)
- [ ] PGP_SPLIT2_v1 (calls → PGP_SPLIT3_v1)
- [ ] PGP_SPLIT3_v1 (calls → downstream services)

**Payout Pipeline:**
- [ ] PGP_ACCUMULATOR_v1 (calls → PGP_HOSTPAY1_v1, PGP_BATCHPROCESSOR_v1)
- [ ] PGP_HOSTPAY1_v1 (calls → PGP_HOSTPAY2_v1)
- [ ] PGP_HOSTPAY2_v1 (calls → PGP_HOSTPAY3_v1)
- [ ] PGP_BATCHPROCESSOR_v1 (calls → PGP_MICROBATCHPROCESSOR_v1)

**Notification Pipeline:**
- [ ] PGP_NOTIFICATIONS_v1 (calls → PGP_SERVER_v1)

**Broadcast System:**
- [ ] PGP_BROADCAST_v1 (calls → PGP_SERVER_v1)

---

## 🧪 Testing

### Local Testing (Development)

```python
# Test script: test_service_auth.py
import os
from PGP_COMMON.auth import call_authenticated_service

# Set target service URL
ORCHESTRATOR_URL = "https://pgp-orchestrator-v1-xxx.run.app"

# Test authenticated call
try:
    response = call_authenticated_service(
        url=f"{ORCHESTRATOR_URL}/health",
        method="GET",
        timeout=10
    )

    print(f"✅ Authentication successful: {response.status_code}")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Authentication failed: {e}")
```

### Monitoring Logs

After deployment, monitor Cloud Logging for authentication errors:

```bash
# Check for authentication errors
gcloud logging read \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="pgp-orchestrator-v1"
   severity>=ERROR
   jsonPayload.message=~"AUTH"' \
  --limit 50 \
  --format json
```

Common authentication errors:
- `403 Forbidden` - Caller service account missing `roles/run.invoker` permission
- `401 Unauthorized` - Invalid or expired token
- `Failed to generate identity token` - Not running on GCP, or service account misconfigured

---

## 🚨 Troubleshooting

### Error: "Failed to generate identity token"

**Cause:** Service not running on Google Cloud, or service account not configured

**Solution:**
1. Verify service is running on Cloud Run (not locally)
2. Check service account is assigned to Cloud Run service:
   ```bash
   gcloud run services describe pgp-orchestrator-v1 \
     --region=us-central1 \
     --format="value(spec.template.spec.serviceAccountName)"
   ```

### Error: "403 Permission denied"

**Cause:** Calling service account doesn't have `roles/run.invoker` on target service

**Solution:**
1. Grant invoker permission:
   ```bash
   gcloud run services add-iam-policy-binding pgp-orchestrator-v1 \
     --region=us-central1 \
     --member="serviceAccount:pgp-np-ipn-v1-sa@pgp-live.iam.gserviceaccount.com" \
     --role="roles/run.invoker"
   ```

### Error: "Invalid audience in token"

**Cause:** Token audience doesn't match target service URL

**Solution:**
- Ensure `target_audience` matches the exact base URL of the target service
- Example: Use `https://pgp-orchestrator-v1-xxx.run.app` (no trailing path)

---

## 📚 Additional Resources

- [Cloud Run Service-to-Service Authentication](https://cloud.google.com/run/docs/authenticating/service-to-service)
- [Google Auth Python Library](https://cloud.google.com/python/docs/reference/google-auth/latest)
- [Cloud Tasks with OIDC Tokens](https://cloud.google.com/tasks/docs/creating-http-target-tasks#token)
- [IAM Roles for Cloud Run](https://cloud.google.com/run/docs/reference/iam/roles)

---

**Last Updated:** 2025-01-18
**Status:** ✅ Ready for implementation
