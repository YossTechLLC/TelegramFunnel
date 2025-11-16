# IP Whitelist Security Documentation

**Version:** 1.0
**Last Updated:** 2025-11-16
**Status:** ✅ IMPLEMENTED

---

## Executive Summary

This document describes the IP whitelist implementation for PGP_SERVER_v1, providing network-level access control for webhook endpoints. The implementation follows defense-in-depth principles, combining IP filtering with HMAC authentication for multi-layered security.

**Security Benefit:**
- **Before:** All IP addresses could reach webhook endpoints (relying solely on HMAC)
- **After:** Only whitelisted IPs can reach endpoints + HMAC validation

**Critical Architectural Decision:**
- IP whitelisting is **ONLY** for external webhooks (NowPayments, Telegram)
- Cloud Run → Cloud Run communication uses **HMAC-ONLY** authentication (NO IP whitelist)
- Reason: Cloud Run services have dynamic egress IPs

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Cloud Run Egress IP Research](#cloud-run-egress-ip-research)
3. [IP Whitelist Strategy](#ip-whitelist-strategy)
4. [Configuration Guide](#configuration-guide)
5. [External Webhook IP Sources](#external-webhook-ip-sources)
6. [Deployment Considerations](#deployment-considerations)
7. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
8. [FAQ](#faq)

---

## Architecture Overview

### Defense in Depth

PGP_SERVER_v1 implements **multiple layers of security**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Incoming Request                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ IP Whitelist  │ ◄─── Layer 1: Network-level filtering
              └───────┬───────┘
                      │ ✅ Allowed
                      ▼
              ┌───────────────┐
              │ Rate Limiting │ ◄─── Layer 2: DoS protection
              └───────┬───────┘
                      │ ✅ Within limits
                      ▼
              ┌───────────────┐
              │ HMAC Auth     │ ◄─── Layer 3: Request authentication
              └───────┬───────┘
                      │ ✅ Valid signature
                      ▼
              ┌───────────────┐
              │ Business      │
              │ Logic         │
              └───────────────┘
```

### When to Use IP Whitelist vs HMAC-Only

| Communication Type | Strategy | Reason |
|-------------------|----------|---------|
| **External Webhooks**<br>(NowPayments, Telegram) | ✅ IP Whitelist + HMAC | Known source IPs, defense in depth |
| **Cloud Run → Cloud Run**<br>(PGP_ORCHESTRATOR_v1) | ❌ HMAC-only | Dynamic egress IPs, no static ranges |
| **Cloud Scheduler → Cloud Run** | ❌ HMAC-only | Dynamic scheduler IPs |
| **GCP Health Checks** | ✅ IP Whitelist | Required for Cloud Run health checks |

---

## Cloud Run Egress IP Research

### Critical Finding: Cloud Run Has No Predefined Egress IPs

**Research Date**: 2025-01-16
**Region**: us-central1
**Finding**: Google Cloud Run does NOT have predefined egress IP ranges.

#### Key Facts

1. **Dynamic IPs by Default**
   - Cloud Run uses Google's global network infrastructure
   - Egress IPs are **dynamically assigned** and can change
   - No fixed IP ranges for outbound connections

2. **Static IPs Require Configuration**
   - Requires **VPC Connector** setup
   - Requires **Cloud NAT** with static IP reservations
   - Adds cost and complexity
   - Not recommended for inter-service communication

3. **Why This Matters**
   - IP whitelisting is **NOT suitable** for Cloud Run → Cloud Run communication
   - Must rely on **HMAC authentication** for service-to-service requests
   - IP whitelist is ONLY appropriate for external webhooks with known source IPs

#### Documentation References

- [Cloud Run Networking](https://cloud.google.com/run/docs/configuring/vpc-direct-vpc)
- [Google Cloud IP Ranges](https://www.gstatic.com/ipranges/cloud.json)
- [Cloud NAT for Static IPs](https://cloud.google.com/nat/docs/overview)

---

## IP Whitelist Strategy

### Per-Endpoint Strategy

PGP_SERVER_v1 has **4 main webhook endpoints** with different IP whitelist strategies:

#### 1. `/webhooks/notification` (PGP_ORCHESTRATOR_v1 → PGP_SERVER_v1)

```yaml
Type: Cloud Run → Cloud Run (internal)
IP Whitelist: DISABLED
Authentication: HMAC-only
Reason: Cloud Run has dynamic egress IPs
```

**Configuration**:
```bash
# app.yaml or .env
ENVIRONMENT=disabled  # Empty IP whitelist
```

#### 2. `/webhooks/broadcast_trigger` (Cloud Scheduler → PGP_SERVER_v1)

```yaml
Type: Cloud Scheduler → Cloud Run
IP Whitelist: DISABLED
Authentication: HMAC-only
Reason: Scheduler IPs are dynamic
```

**Configuration**:
```bash
# app.yaml or .env
ENVIRONMENT=disabled  # Empty IP whitelist
```

#### 3. `/webhooks/nowpayments` (NowPayments → PGP_SERVER_v1)

```yaml
Type: External webhook
IP Whitelist: ENABLED
Authentication: IP Whitelist + HMAC
Reason: Known source IPs, defense in depth
```

**Configuration**:
```bash
# app.yaml or .env
ENVIRONMENT=production
# Includes NowPayments IPN IPs: 52.29.216.31, 18.157.160.115, 3.126.138.126
```

#### 4. `/webhooks/telegram` (Telegram → PGP_SERVER_v1)

```yaml
Type: External webhook
IP Whitelist: ENABLED
Authentication: IP Whitelist + Secret Token
Reason: Known source IPs, Telegram best practice
```

**Configuration**:
```bash
# app.yaml or .env
ENVIRONMENT=production
# Includes Telegram ranges: 149.154.160.0/20, 91.108.4.0/22
```

---

## Configuration Guide

### Environment-Based Configuration

The IP whitelist uses **preset configurations** based on the `ENVIRONMENT` variable:

#### Development

```bash
ENVIRONMENT=development
```

**Allowed IPs**:
- `127.0.0.1/32` (IPv4 localhost)
- `::1/128` (IPv6 localhost)

**Use Case**: Local testing with test API keys

#### Staging

```bash
ENVIRONMENT=staging
```

**Allowed IPs**:
- Localhost
- GCP Internal VPC (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- GCP Health Checks (`35.191.0.0/16`, `130.211.0.0/22`)
- Cloud Shell (`35.235.240.0/20`)
- NowPayments IPN IPs
- Telegram Webhook IPs

**Use Case**: Staging environment with external webhooks enabled

#### Production (Recommended)

```bash
ENVIRONMENT=production
```

**Allowed IPs**:
- NowPayments IPN IPs (`52.29.216.31`, `18.157.160.115`, `3.126.138.126`)
- Telegram Webhook IPs (`149.154.160.0/20`, `91.108.4.0/22`)
- GCP Health Checks (`35.191.0.0/16`, `130.211.0.0/22`)

**Use Case**: Production with external webhooks only, minimal attack surface

#### Cloud Run Internal

```bash
ENVIRONMENT=cloud_run_internal
```

**Allowed IPs**:
- GCP Internal VPC
- GCP Health Checks
- GCP us-central1 ranges (if using VPC connector)

**Use Case**: Services receiving ONLY internal Cloud Run traffic (no external webhooks)

#### Disabled (HMAC-Only)

```bash
ENVIRONMENT=disabled
```

**Allowed IPs**: Empty list (`[]`)

**Use Case**: Cloud Run → Cloud Run communication, HMAC authentication only

### Custom IP Configuration

Override preset configurations with explicit IP list:

```bash
# Custom IP whitelist (comma-separated)
ALLOWED_IPS=192.168.1.1,10.0.0.0/24,52.29.216.31

# ALLOWED_IPS takes precedence over ENVIRONMENT
```

**Validation**: All IPs are validated at startup. Invalid IPs will cause startup failure.

### Code Integration

```python
from security.allowed_ips import get_allowed_ips_from_env, validate_ip_list

# Get IPs based on ENVIRONMENT or ALLOWED_IPS
allowed_ips = get_allowed_ips_from_env()

# Validate before use
validate_ip_list(allowed_ips)

# Initialize IP whitelist
from security.ip_whitelist import init_ip_whitelist
ip_whitelist = init_ip_whitelist(allowed_ips)
```

---

## External Webhook IP Sources

### NowPayments IPN

**Documentation**: [NowPayments IPN](https://documenter.getpostman.com/view/7907941/S1a32n38#ipn)
**Last Updated**: 2025-01-16

**IPN Server IPs** (eu-central-1):
```python
NOWPAYMENTS_IPN_IPS = [
    "52.29.216.31",     # Primary IPN server
    "18.157.160.115",   # Secondary IPN server
    "3.126.138.126",    # Tertiary IPN server
]
```

**Verification Process**:
1. Check official NowPayments documentation
2. Monitor webhook logs for actual source IPs
3. Update `allowed_ips.py` if IPs change
4. Run unit tests to validate changes

**Monitoring**:
```bash
# Check for IPN requests from unexpected IPs
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.endpoint=~/webhooks/nowpayments/ \
  AND jsonPayload.status=403" \
  --limit 50 --format json
```

### Telegram Bot API

**Documentation**: [Telegram Webhooks](https://core.telegram.org/bots/webhooks#the-short-version)
**Last Updated**: 2025-01-16

**Webhook IP Ranges**:
```python
TELEGRAM_WEBHOOK_IPS = [
    "149.154.160.0/20",  # Telegram datacenter range 1
    "91.108.4.0/22",     # Telegram datacenter range 2
]
```

**Verification Process**:
1. Check `https://core.telegram.org/bots/webhooks`
2. Use Telegram's `getWebhookInfo` API method
3. Monitor webhook logs for actual source IPs
4. Update `allowed_ips.py` if ranges change

**Monitoring**:
```bash
# Check Telegram webhook traffic
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.endpoint=~/webhooks/telegram/ \
  AND jsonPayload.client_ip=~149.154." \
  --limit 50 --format json
```

### GCP Health Checks

**Documentation**: [GCP Health Check Ranges](https://cloud.google.com/load-balancing/docs/health-checks)

**Health Check IP Ranges**:
```python
GCP_HEALTH_CHECK_RANGES = [
    "35.191.0.0/16",    # Legacy health checks
    "130.211.0.0/22",   # Legacy health checks
]
```

**Note**: These ranges are **required** for Cloud Run services. Do NOT remove from production configuration.

---

## Deployment Considerations

### Production Deployment Checklist

- [ ] **Set `ENVIRONMENT=production`** in Cloud Run service configuration
- [ ] **Verify external webhook IPs** are current (NowPayments, Telegram)
- [ ] **Test webhook delivery** from external services
- [ ] **Monitor 403 errors** for unexpected IP blocks
- [ ] **Enable Cloud Logging** for IP whitelist events
- [ ] **Set up alerts** for IP whitelist failures
- [ ] **Document IP sources** in runbook
- [ ] **Schedule quarterly review** of external webhook IPs

### Cloud Run Configuration

```bash
# Deploy with production IP whitelist
gcloud run deploy pgp-server-v1 \
  --set-env-vars ENVIRONMENT=production \
  --region us-central1 \
  --project pgp-live
```

### Environment Variable Priority

Configuration is loaded in this order (highest priority first):

1. **`ALLOWED_IPS`** environment variable (explicit override)
2. **`ENVIRONMENT`** environment variable (preset configuration)
3. **Default**: `production` preset

### Startup Validation

On startup, PGP_SERVER_v1 validates the IP whitelist configuration:

```
🔒 [IP_WHITELIST] Loaded configuration for environment: production
🔒 [SECURITY] Configured:
   Allowed IPs: 7 ranges
   IP ranges: 52.29.216.31, 18.157.160.115, 3.126.138.126 ...
   Rate limit: 10 req/min, burst 20
```

**Error Handling**:
- Invalid IPs → Startup failure
- Missing environment → Falls back to `production`
- Configuration error → Falls back to `127.0.0.1` (localhost only) with warning

---

## Monitoring and Troubleshooting

### Log Monitoring

#### IP Whitelist Blocks (403 Forbidden)

```bash
# Find requests blocked by IP whitelist
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.message=~'IP_WHITELIST.*blocked' \
  AND severity>=WARNING" \
  --limit 50 --format json
```

**Log Format**:
```json
{
  "severity": "WARNING",
  "jsonPayload": {
    "message": "❌ [IP_WHITELIST] Blocked request from IP: 8.8.8.8",
    "client_ip": "8.8.8.8",
    "endpoint": "/webhooks/nowpayments",
    "x_forwarded_for": "8.8.8.8"
  }
}
```

#### IP Whitelist Allows

```bash
# Find requests allowed by IP whitelist
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.message=~'IP_WHITELIST.*allowed' \
  AND severity=INFO" \
  --limit 50 --format json
```

**Log Format**:
```json
{
  "severity": "INFO",
  "jsonPayload": {
    "message": "✅ [IP_WHITELIST] Allowed request from IP: 52.29.216.31",
    "client_ip": "52.29.216.31",
    "endpoint": "/webhooks/nowpayments",
    "matched_network": "52.29.216.31/32"
  }
}
```

### Common Issues

#### Issue 1: External Webhook Blocked

**Symptoms**: NowPayments or Telegram webhooks return 403 Forbidden

**Diagnosis**:
```bash
# Check IP whitelist configuration
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.message=~'IP_WHITELIST.*Loaded configuration'" \
  --limit 5 --format json
```

**Possible Causes**:
1. External service changed IPs (check official documentation)
2. `ENVIRONMENT=disabled` incorrectly set
3. X-Forwarded-For header parsing issue

**Fix**:
```bash
# Update allowed_ips.py with new IPs
# Redeploy service
gcloud run deploy pgp-server-v1 \
  --set-env-vars ENVIRONMENT=production
```

#### Issue 2: Cloud Run Health Checks Failing

**Symptoms**: Service shows unhealthy in Cloud Run console

**Diagnosis**:
```bash
# Check health check requests
gcloud logging read "resource.type=cloud_run_revision \
  AND httpRequest.requestUrl=~'/_ah/health'" \
  --limit 10 --format json
```

**Possible Cause**: GCP health check ranges removed from IP whitelist

**Fix**: Ensure `GCP_HEALTH_CHECK_RANGES` are included in production configuration

#### Issue 3: Cloud Run → Cloud Run Communication Blocked

**Symptoms**: PGP_ORCHESTRATOR_v1 → PGP_SERVER_v1 requests fail with 403

**Diagnosis**:
```bash
# Check ORCHESTRATOR requests
gcloud logging read "resource.type=cloud_run_revision \
  AND jsonPayload.endpoint=~/webhooks/notification/ \
  AND jsonPayload.status=403" \
  --limit 10 --format json
```

**Root Cause**: Cloud Run has dynamic egress IPs - IP whitelist not appropriate

**Fix**:
```bash
# Disable IP whitelist for internal communication
gcloud run deploy pgp-server-v1 \
  --set-env-vars ENVIRONMENT=disabled

# Ensure HMAC authentication is enabled
```

### Alerting

Create Cloud Monitoring alerts for IP whitelist issues:

```yaml
# Alert: High rate of IP whitelist blocks
displayName: "IP Whitelist - High Block Rate"
conditions:
  - displayName: "403 rate > 10/min"
    conditionThreshold:
      filter: |
        resource.type="cloud_run_revision"
        AND jsonPayload.status="403"
        AND jsonPayload.message=~"IP_WHITELIST"
      aggregations:
        - alignmentPeriod: 60s
          perSeriesAligner: ALIGN_RATE
      comparison: COMPARISON_GT
      thresholdValue: 10
```

---

## FAQ

### Q1: Why doesn't Cloud Run have static egress IPs?

**A**: Cloud Run is a fully managed, serverless platform that uses Google's global network infrastructure. Instances are ephemeral and can be created/destroyed dynamically across multiple zones for auto-scaling. Assigning static IPs would require:
- VPC Connector setup (connects Cloud Run to VPC)
- Cloud NAT with static IP reservation (provides static egress IPs)
- Additional cost and operational complexity

For most use cases, **HMAC authentication** is a better solution than IP whitelisting for Cloud Run → Cloud Run communication.

### Q2: Should I use IP whitelist for Cloud Run → Cloud Run communication?

**A**: **NO**. Use **HMAC authentication only** (`ENVIRONMENT=disabled`).

**Reason**: Cloud Run services have dynamic egress IPs that cannot be reliably whitelisted without complex VPC/NAT setup.

**Exception**: If you've explicitly configured VPC Connector + Cloud NAT with static IP reservations.

### Q3: How do I update external webhook IPs (NowPayments, Telegram)?

**Process**:
1. Check official documentation for updated IPs
2. Update `PGP_SERVER_v1/security/allowed_ips.py`
3. Run unit tests: `pytest tests/test_ip_whitelist.py`
4. Update this documentation with new IPs and date
5. Redeploy PGP_SERVER_v1
6. Verify webhook delivery

**Example**:
```python
# allowed_ips.py
NOWPAYMENTS_IPN_IPS = [
    "52.29.216.31",     # Primary (updated 2025-01-16)
    "18.157.160.115",   # Secondary
    "3.126.138.126",    # Tertiary
    "1.2.3.4",          # NEW IP (added 2025-02-01)
]
```

### Q4: What happens if I set `ENVIRONMENT=disabled`?

**A**: IP whitelist is **completely disabled**. All requests are allowed through the IP whitelist layer and must pass **HMAC authentication** instead.

**Use Cases**:
- Cloud Run → Cloud Run communication
- Cloud Scheduler → Cloud Run communication
- Testing HMAC authentication without IP restrictions

**Security**: This is **secure** as long as HMAC authentication is properly implemented (Issue 1 completed).

### Q5: Can I use both IP whitelist AND HMAC authentication?

**A**: **YES** - this is **recommended** for external webhooks (defense in depth).

**Example**: `/webhooks/nowpayments` endpoint:
1. **Layer 1**: IP whitelist checks source IP against NowPayments IPN ranges
2. **Layer 2**: Rate limiting prevents DoS attacks
3. **Layer 3**: HMAC authentication validates request signature

Both layers must pass for request to succeed.

### Q6: How do I test IP whitelist locally?

**Development Setup**:
```bash
# .env file
ENVIRONMENT=development  # Allows localhost only

# Or allow custom IPs for testing
ALLOWED_IPS=127.0.0.1,192.168.1.100
```

**Unit Tests**:
```bash
# Run comprehensive test suite
cd PGP_SERVER_v1
pytest tests/test_ip_whitelist.py -v

# Test specific scenarios
pytest tests/test_ip_whitelist.py::TestIPWhitelistValidation -v
pytest tests/test_ip_whitelist.py::TestAllowedIPsConfiguration -v
```

**Manual Testing with curl**:
```bash
# Test with X-Forwarded-For header
curl -H "X-Forwarded-For: 52.29.216.31" http://localhost:8080/webhooks/nowpayments

# Test with blocked IP
curl -H "X-Forwarded-For: 8.8.8.8" http://localhost:8080/webhooks/nowpayments
# Expected: 403 Forbidden
```

### Q7: What's the difference between CIDR notation and single IPs?

**Single IP**: `52.29.216.31` (exact match only)
**CIDR Range**: `149.154.160.0/20` (matches 4,096 IPs: `149.154.160.0` - `149.154.175.255`)

**When to Use**:
- Single IPs: External services with fixed IPs (NowPayments)
- CIDR Ranges: External services with IP ranges (Telegram, GCP health checks)

**Validation**: Both formats are validated using Python's `ipaddress` module.

### Q8: How do I know if an IP is in a CIDR range?

**Python**:
```python
from ipaddress import ip_address, ip_network

ip = ip_address('149.154.165.100')
network = ip_network('149.154.160.0/20')

if ip in network:
    print("IP is in range")  # TRUE
```

**Online Tools**:
- https://www.ipaddressguide.com/cidr
- https://www.subnet-calculator.com/cidr.php

**Unit Tests**: See `tests/test_ip_whitelist.py` for comprehensive examples

### Q9: Should I include localhost in production IP whitelist?

**A**: **NO** - Production configuration should include ONLY:
- External webhook IPs (NowPayments, Telegram)
- GCP health check ranges (required for Cloud Run)

**Reason**: Localhost (`127.0.0.1`) is never a source IP in production Cloud Run. Including it provides no security benefit and violates the principle of least privilege.

**Development**: Use `ENVIRONMENT=development` which includes localhost.

### Q10: How often should I review IP whitelist configuration?

**Recommended Schedule**:
- **Quarterly**: Review external webhook IP sources (NowPayments, Telegram)
- **On Alert**: Review immediately if monitoring shows unexpected 403 errors
- **On Change**: Review when external services announce IP changes

**Review Checklist**:
- [ ] Check NowPayments documentation for IP updates
- [ ] Check Telegram documentation for IP range updates
- [ ] Verify GCP health check ranges (rarely change)
- [ ] Review Cloud Logging for blocked IPs
- [ ] Update `allowed_ips.py` if needed
- [ ] Run unit tests
- [ ] Update documentation

---

## Implementation Details

### Files Modified/Created

1. **`PGP_SERVER_v1/security/allowed_ips.py`** (NEW)
   - Centralized IP configuration module
   - Environment-based presets
   - Validation utilities

2. **`PGP_SERVER_v1/app_initializer.py`** (MODIFIED)
   - Integrated `get_allowed_ips_from_env()`
   - Added validation and error handling
   - Enhanced logging

3. **`PGP_SERVER_v1/tests/test_ip_whitelist.py`** (NEW)
   - 60+ unit tests
   - Comprehensive coverage
   - Environment configuration tests

4. **`PGP_SERVER_v1/security/IP_WHITELIST_SECURITY.md`** (THIS FILE)
   - Security documentation
   - Configuration guide
   - Troubleshooting

### Testing

```bash
# Run all IP whitelist tests
pytest tests/test_ip_whitelist.py -v

# Test coverage report
pytest tests/test_ip_whitelist.py --cov=security.ip_whitelist --cov=security.allowed_ips

# Test specific environment configuration
pytest tests/test_ip_whitelist.py::TestAllowedIPsConfiguration::test_production_environment -v
```

**Expected Test Output**:
```
tests/test_ip_whitelist.py::TestIPWhitelistValidation::test_single_ip_allowed PASSED
tests/test_ip_whitelist.py::TestIPWhitelistValidation::test_cidr_range_allowed PASSED
tests/test_ip_whitelist.py::TestAllowedIPsConfiguration::test_production_environment PASSED
...
============================== 60 passed in 2.31s ==============================
```

---

## Security Considerations

### Threat Model

**Threats Mitigated**:
1. ✅ **IP Spoofing** (limited) - Attackers from unauthorized IPs blocked
2. ✅ **DoS Attacks** - Combined with rate limiting
3. ✅ **Unauthorized Webhooks** - Only known IPs can trigger webhooks

**Threats NOT Mitigated**:
1. ❌ **Compromised External Service** - If NowPayments/Telegram IPs are compromised, IP whitelist won't help (HMAC authentication required)
2. ❌ **X-Forwarded-For Spoofing** - If proxy doesn't sanitize header (Cloud Run handles this correctly)

### Defense in Depth Strategy

IP whitelist is **one layer** of a multi-layer security approach:

```
External Request
    ↓
┌───────────────────┐
│ IP Whitelist      │ ← Blocks unauthorized IPs
└───────┬───────────┘
        ↓
┌───────────────────┐
│ Rate Limiting     │ ← Prevents DoS attacks
└───────┬───────────┘
        ↓
┌───────────────────┐
│ HMAC Auth         │ ← Validates request authenticity
└───────┬───────────┘
        ↓
┌───────────────────┐
│ Business Logic    │ ← Processes valid requests
└───────────────────┘
```

**All layers must pass** for request to succeed.

### Best Practices

1. ✅ **Use environment-based configuration** (avoid hardcoded IPs)
2. ✅ **Validate IPs at startup** (fail fast)
3. ✅ **Monitor 403 errors** (detect configuration issues)
4. ✅ **Document IP sources** (enable future updates)
5. ✅ **Test thoroughly** (unit tests + integration tests)
6. ✅ **Review quarterly** (external IPs can change)
7. ✅ **Use HMAC for Cloud Run → Cloud Run** (not IP whitelist)
8. ✅ **Combine with rate limiting** (defense in depth)

---

## Related Documentation

- [HMAC Timestamp Security](./HMAC_TIMESTAMP_SECURITY.md) - Issue 1 (CRITICAL)
- [IP Whitelist Implementation](./ip_whitelist.py) - Core implementation
- [IP Configuration Module](./allowed_ips.py) - Centralized configuration
- [Unit Tests](../tests/test_ip_whitelist.py) - Test coverage

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-16 | 1.0.0 | Initial implementation (Issue 2) |

---

**Security Issue**: Issue 2 - IP Whitelist Configuration
**Status**: ✅ IMPLEMENTED
**Next**: Issue 3 - Debug Logging Removal (MEDIUM Priority)
