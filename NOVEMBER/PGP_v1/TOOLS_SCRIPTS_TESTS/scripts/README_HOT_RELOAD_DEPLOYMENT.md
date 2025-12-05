# Hot-Reload Deployment Guide

**Status**: Implementation in progress
**Last Updated**: 2025-11-18
**Implemented Services**: 1/17 (PGP_SPLIT2_v1)

---

## Overview

This directory contains deployment scripts for the hot-reload secret management feature across all PGP_v1 services.

**What is Hot-Reload?**
- Secrets can be updated in Google Cloud Secret Manager and take effect immediately
- No service restart required
- Enables zero-downtime API key rotation, service URL blue-green deployments, and queue migrations

**What Secrets are Hot-Reloadable?** (43 total)
- ✅ API Keys (5): CHANGENOW_API_KEY, NOWPAYMENTS_API_KEY, ETHEREUM_RPC_URL_API, TELEGRAM_BOT_API_TOKEN, TELEGRAM_BOT_USERNAME
- ✅ Service URLs (13): All PGP_*_URL secrets
- ✅ Queue Names (15): All queue secrets
- ✅ Webhook/IPN Secrets (4): NOWPAYMENTS_IPN_SECRET, etc.
- ✅ Application Config (6): TP_FLAT_FEE, success/failure URLs, feature flags

**What Secrets NEVER Hot-Reload?** (3 security-critical + 8 complex cases)
- ❌ HOST_WALLET_PRIVATE_KEY (ETH wallet private key in PGP_HOSTPAY3_v1)
- ❌ SUCCESS_URL_SIGNING_KEY (JWT signing key in PGP_ORCHESTRATOR_v1)
- ❌ TPS_HOSTPAY_SIGNING_KEY (HMAC signing key in PGP_SERVER_v1, PGP_HOSTPAY1_v1)
- ⚠️ Database credentials (require connection pool restart)
- ⚠️ Infrastructure config (CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION)

---

## Implementation Status

### Completed (1/17):
- ✅ **PGP_SPLIT2_v1** - Pilot service
  - Hot-reloadable: CHANGENOW_API_KEY, PGP_SPLIT1_RESPONSE_QUEUE, PGP_SPLIT1_URL, PGP_BATCHPROCESSOR_QUEUE, PGP_BATCHPROCESSOR_URL
  - Static: SUCCESS_URL_SIGNING_KEY, DATABASE_PASSWORD_SECRET

### Pending - Security-Critical Services (4/17):
- ⏸️ **PGP_ORCHESTRATOR_v1** - Must keep SUCCESS_URL_SIGNING_KEY static
- ⏸️ **PGP_HOSTPAY1_v1** - Must keep TPS_HOSTPAY_SIGNING_KEY static
- ⏸️ **PGP_HOSTPAY3_v1** - Must keep HOST_WALLET_PRIVATE_KEY static
- ⏸️ **PGP_SERVER_v1** - Must keep TPS_HOSTPAY_SIGNING_KEY static

### Pending - Core Services (12/17):
- ⏸️ PGP_SPLIT1_v1
- ⏸️ PGP_HOSTPAY2_v1
- ⏸️ PGP_NOTIFICATIONS_v1
- ⏸️ PGP_INVITE_v1
- ⏸️ PGP_ACCUMULATOR_v1
- ⏸️ PGP_BATCHPROCESSOR_v1
- ⏸️ PGP_BROADCAST_v1
- ⏸️ PGP_NP_IPN_v1 (formerly PGP_NPWEBHOOK_v1)
- ⏸️ PGP_MICROBATCHPROCESSOR_v1
- ⏸️ PGP_WEBAPI_v1
- ⏸️ PGP_WEB_v1
- ⏸️ PGP_BOTCOMMAND_v1 (if exists)

---

## Deployment Scripts

### Infrastructure Scripts:
1. **`deploy_hot_reload_base_config.sh`** (NOT YET CREATED)
   - Deploys updated PGP_COMMON with hot-reload infrastructure
   - Must be run FIRST before any service deployments

2. **`test_hot_reload_pilot.sh`** (NOT YET CREATED)
   - Tests hot-reload functionality on PGP_SPLIT2_v1
   - Verifies API key rotation, queue name update, service URL update
   - Validates request-level caching

### Service Deployment Scripts:
3. **`deploy_hot_reload_pilot.sh`** (NOT YET CREATED)
   - Deploys PGP_SPLIT2_v1 with hot-reload enabled
   - For testing in staging before full rollout

4. **`deploy_hot_reload_security_critical.sh`** (NOT YET CREATED)
   - Deploys 4 security-critical services (orchestrator, hostpay1, hostpay3, server)
   - Extra validation to ensure private keys remain static

5. **`deploy_hot_reload_all_services.sh`** (NOT YET CREATED)
   - Staged deployment of all 17 services
   - Week-by-week rollout plan

### Verification Scripts:
6. **`verify_hot_reload_secrets.sh`** (NOT YET CREATED)
   - Verifies all 43 hot-reloadable secrets can be fetched dynamically
   - Verifies 3 static secrets NEVER fetched via Secret Manager API during requests
   - Uses Cloud Audit Logs

7. **`audit_static_secrets.sh`** (NOT YET CREATED)
   - Searches codebase for direct `os.getenv()` calls to hot-reloadable secrets
   - Searches for hardcoded secret values
   - Verifies request-level caching implemented

---

## Deployment Phases

### Phase 1: Infrastructure Foundation (COMPLETED)
- ✅ Update PGP_COMMON/config/base_config.py
- ✅ Add `fetch_secret_dynamic()` method
- ✅ Add `build_secret_path()` helper
- ✅ Add Flask `g` context caching

### Phase 2: Pilot Deployment (IN PROGRESS)
- ✅ Implement PGP_SPLIT2_v1 hot-reload
- ⏸️ Create deployment script
- ⏸️ Test in staging environment
- ⏸️ Validate hot-reload functionality
- ⏸️ Monitor for 48 hours

### Phase 3: Security-Critical Services (PENDING)
- ⏸️ Implement PGP_ORCHESTRATOR_v1
- ⏸️ Implement PGP_HOSTPAY1_v1
- ⏸️ Implement PGP_HOSTPAY3_v1
- ⏸️ Implement PGP_SERVER_v1
- ⏸️ Security audit (verify static secrets remain static)
- ⏸️ Deploy to staging
- ⏸️ Monitor for 48 hours

### Phase 4: Remaining Services (PENDING)
- ⏸️ Implement remaining 12 services
- ⏸️ Deploy in batches (5 services per week)
- ⏸️ Monitor each batch for 48 hours

### Phase 5: Production Validation (PENDING)
- ⏸️ Perform live API key rotation test
- ⏸️ Perform live service URL update test
- ⏸️ Perform live queue name migration test
- ⏸️ Validate audit logs (static secrets never accessed during requests)

---

## Testing Procedures

### 1. Hot-Reload API Key Test
```bash
# 1. Deploy service with hot-reload
./deploy_hot_reload_pilot.sh

# 2. Make test request (should succeed with current key)
curl -X POST https://pgp-split2-v1-.../test \
  -H "Content-Type: application/json" \
  -d '{"test": "api_key_rotation"}'

# 3. Rotate API key in Secret Manager
gcloud secrets versions add CHANGENOW_API_KEY \
  --data-file=new_api_key.txt \
  --project=pgp-live

# 4. Make test request immediately (should succeed with NEW key - no restart)
curl -X POST https://pgp-split2-v1-.../test \
  -H "Content-Type: application/json" \
  -d '{"test": "api_key_rotation"}'

# 5. Check logs for "Hot-reloaded" message
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"Hot-reloaded CHANGENOW_API_KEY"' \
  --limit=10 \
  --project=pgp-live
```

### 2. Static Secret Verification Test
```bash
# Verify private keys NEVER accessed during requests (should return 0 results)
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"Hot-reloaded.*HOST_WALLET_PRIVATE_KEY|SUCCESS_URL_SIGNING_KEY|TPS_HOSTPAY_SIGNING_KEY"' \
  --limit=100 \
  --project=pgp-live

# Should only see static load at container startup
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"Successfully loaded.*HOST_WALLET_PRIVATE_KEY.*static"' \
  --limit=10 \
  --project=pgp-live
```

### 3. Request-Level Caching Test
```bash
# Monitor Secret Manager API usage - should NOT spike after deployment
gcloud monitoring metrics list \
  --filter='metric.type="secretmanager.googleapis.com/secret/access_count"' \
  --project=pgp-live

# Verify <5ms latency increase
gcloud monitoring metrics list \
  --filter='metric.type="run.googleapis.com/request/latency"' \
  --project=pgp-live
```

---

## Rollback Procedures

### If Hot-Reload Causes Issues:

**Immediate Rollback (Revert to Previous Container)**:
```bash
# 1. Identify previous revision
gcloud run revisions list --service=pgp-split2-v1 --region=us-central1 --project=pgp-live

# 2. Revert traffic to previous revision (no hot-reload)
gcloud run services update-traffic pgp-split2-v1 \
  --to-revisions=PREVIOUS_REVISION_NAME=100 \
  --region=us-central1 \
  --project=pgp-live

# 3. Verify service using static secrets again
curl https://pgp-split2-v1-.../health
```

**Rollback Triggers**:
- Service crashes after hot-reload deployment
- >5% increase in error rate
- Secret Manager API call rate >10x expected
- Static secrets (private keys) fetched dynamically (CRITICAL - security incident)
- Payment failures increase >10%

---

## Security Incident Response

**If Static Secret Made Hot-Reloadable (CRITICAL)**:

1. **IMMEDIATE ROLLBACK**: Revert to previous container image
2. **SECURITY INCIDENT**: Notify security team
3. **INVESTIGATION**: Check Cloud Audit Logs for private key access during requests
   ```bash
   gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"HOST_WALLET_PRIVATE_KEY|SUCCESS_URL_SIGNING_KEY|TPS_HOSTPAY_SIGNING_KEY"' \
     --limit=1000 \
     --project=pgp-live
   ```
4. **REMEDIATION**: If private key leaked in logs, rotate immediately
5. **ROOT CAUSE**: Review code changes that caused violation

---

## Monitoring & Alerting

### Cloud Monitoring Dashboard (TO BE CREATED):
- Secret Manager API calls per service (time series)
- Secret Manager API errors per service
- Secret Manager API latency (p50, p95, p99)
- Hot-reload events count by secret name

### Alerting Policies (TO BE CREATED):
- Alert: Secret Manager API calls >1000/min for single service
- Alert: Secret Manager API errors >10/min
- Alert: Secret Manager API latency p95 >200ms
- Alert: Static secret accessed during request (CRITICAL)

---

## Cost Estimates

**Before Hot-Reload**:
- Secret Manager: ~$0 (only accessed at container startup)

**After Hot-Reload**:
- Secret Manager API calls: ~500k/month (est. 100 requests/min across 17 services)
- Secret Manager cost: ~$7.50/month ($0.03 per 10k accesses)
- **Total increase: <$10/month**

**Cost Optimization**:
- Request-level caching reduces API calls by ~90%
- Without caching: ~$75/month (10x higher)

---

**End of README**
