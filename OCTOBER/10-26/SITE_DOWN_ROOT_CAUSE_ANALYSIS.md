# Site Down - Root Cause Analysis

**Date:** 2025-11-15
**Issue:** Both `paygateprime.com` and `www.paygateprime.com` are returning `ERR_CONNECTION_CLOSED`
**Status:** 🔴 **CRITICAL - SITE DOWN**

---

## Executive Summary

**ROOT CAUSE:** Deleting the `gcregister10-26` Cloud Run service broke the SSL certificate provisioning for `paygateprime.com` (apex domain), which in turn prevents HTTPS connections from working for both domains.

**IMPACT:**
- ❌ `paygateprime.com` - Connection refused (no service behind old Cloud Run IPs)
- ❌ `www.paygateprime.com` - SSL handshake fails (certificate still provisioning)
- 🔴 **100% downtime for website**

---

## Timeline of Events

### 2025-11-14 16:33 PST
- Created `paygateprime-ssl-combined` certificate for both domains
- Certificate started provisioning

### 2025-11-15 (Today)
- **Deleted `gcregister10-26` Cloud Run service**
- This removed the backend service that was handling requests to old Cloud Run IPs
- DNS still points apex domain to Cloud Run IPs that no longer have a service

### Current State (2025-11-15 01:41 PST)
- SSL certificate status:
  - `www.paygateprime.com`: **ACTIVE** ✅
  - `paygateprime.com`: **FAILED_NOT_VISIBLE** ❌
- Certificate overall status: **PROVISIONING** (cannot activate until apex domain is visible)

---

## Technical Analysis

### 1. DNS Configuration (Current - INCORRECT)

#### Apex Domain (`paygateprime.com`)
```
Type: A
Current DNS (in Cloudflare):
  - 216.239.32.21  ← OLD Cloud Run IP (service deleted)
  - 216.239.34.21  ← OLD Cloud Run IP (service deleted)
  - 216.239.36.21  ← OLD Cloud Run IP (service deleted)
  - 216.239.38.21  ← OLD Cloud Run IP (service deleted)

Actual DNS resolution (via dig):
  - 35.244.222.18   ← Load Balancer IP (correct)
```

**Status:** DNS has been updated but may be cached OR Cloudflare still has old records

#### WWW Subdomain (`www.paygateprime.com`)
```
Type: A
DNS: 35.244.222.18  ✅ CORRECT (Load Balancer IP)
```

### 2. SSL Certificate Status

```yaml
Name: paygateprime-ssl-combined
Created: 2025-11-14 16:33:27 PST
Status: PROVISIONING

Domain Status:
  www.paygateprime.com: ACTIVE ✅
  paygateprime.com: FAILED_NOT_VISIBLE ❌
```

**Why `FAILED_NOT_VISIBLE`?**
- Google's SSL provisioning service cannot verify ownership of `paygateprime.com`
- It expects to reach a Google-controlled service at the domain
- The old Cloud Run IPs (216.239.x.x) no longer have `gcregister10-26` service
- Without a Cloud Run domain mapping, Google can't verify the domain

### 3. Infrastructure Configuration

#### Load Balancer Setup ✅
```yaml
URL Map: www-paygateprime-urlmap
- Host: www.paygateprime.com → Backend bucket
- Host: paygateprime.com → 301 redirect to www

Backend Bucket: www-paygateprime-backend
- Bucket: gs://www-paygateprime-com/
- CDN: Enabled
- Files: Present ✅

HTTPS Proxy: www-paygateprime-https-proxy
- SSL Certificate: paygateprime-ssl-combined
- URL Map: www-paygateprime-urlmap

Forwarding Rules:
- HTTP: 35.244.222.18 → HTTP proxy (redirects to HTTPS)
- HTTPS: 35.244.222.18 → HTTPS proxy
```

**Status:** Infrastructure is correctly configured, waiting for SSL certificate

### 4. Connection Test Results

#### HTTP Test (Port 80)
```bash
$ curl -I http://paygateprime.com
HTTP/1.1 301 Moved Permanently
Location: https://www.paygateprime.com:443/
```
✅ **HTTP works** - Redirects to HTTPS as expected

#### HTTPS Test (Port 443)
```bash
$ curl -Ik https://www.paygateprime.com
curl: (35) error:0A000126:SSL routines::unexpected eof while reading
```
❌ **HTTPS fails** - SSL handshake incomplete because certificate is still provisioning

---

## Root Cause Chain

```
1. Deleted gcregister10-26 Cloud Run service
   ↓
2. Old Cloud Run IPs (216.239.x.x) no longer have backend service
   ↓
3. Google SSL verification cannot reach apex domain
   ↓
4. paygateprime.com domain status: FAILED_NOT_VISIBLE
   ↓
5. SSL certificate stuck in PROVISIONING
   ↓
6. HTTPS proxy cannot complete SSL handshake
   ↓
7. Both domains return ERR_CONNECTION_CLOSED
```

---

## Why Did This Happen?

### The Chicken-and-Egg Problem

**Original Plan (Nov 14):**
1. Create SSL certificate for both domains ✅
2. Wait for DNS change to point apex to Load Balancer ⏳
3. Certificate provisions for both domains ❌

**What Actually Happened:**
- Created SSL certificate before DNS was updated
- `www.paygateprime.com` was already pointing to Load Balancer → Verified ✅
- `paygateprime.com` was still pointing to Cloud Run → Needed Cloud Run service to verify ❌
- Deleted Cloud Run service → Broke verification ❌
- Certificate now stuck waiting for apex domain to be visible

---

## Solution Paths

### Option 1: Delete and Recreate SSL Certificate (RECOMMENDED) ⚡

**Steps:**
1. Delete the current SSL certificate:
   ```bash
   gcloud compute ssl-certificates delete paygateprime-ssl-combined --global
   ```

2. Verify DNS is pointing to Load Balancer:
   ```bash
   dig paygateprime.com A +short
   # Should return: 35.244.222.18
   ```

3. Create new SSL certificate (will provision quickly since DNS is correct):
   ```bash
   gcloud compute ssl-certificates create paygateprime-ssl-final \
       --domains=www.paygateprime.com,paygateprime.com \
       --global
   ```

4. Update HTTPS proxy to use new certificate:
   ```bash
   gcloud compute target-https-proxies update www-paygateprime-https-proxy \
       --ssl-certificates=paygateprime-ssl-final \
       --global
   ```

5. Wait 5-15 minutes for provisioning

**Pros:**
- ✅ Fast (5-15 minutes total)
- ✅ Clean solution
- ✅ Will work immediately since DNS is already correct

**Cons:**
- ⚠️ Brief period where cert might be invalid (but site is already down)

---

### Option 2: Wait for DNS Propagation (SLOWER)

**If DNS hasn't fully propagated yet:**
1. Verify current DNS in Cloudflare
2. Ensure Cloudflare proxy is DISABLED (gray cloud)
3. Wait 15-30 minutes for full DNS propagation
4. SSL certificate should auto-resolve

**Pros:**
- ✅ No manual intervention needed

**Cons:**
- ❌ Slow (15-60 minutes)
- ❌ May not work if DNS was already propagated

---

### Option 3: Temporarily Serve WWW Only

**Quick fix while waiting:**
1. Create temporary SSL certificate for WWW only:
   ```bash
   gcloud compute ssl-certificates create www-paygateprime-temp \
       --domains=www.paygateprime.com \
       --global
   ```

2. Update HTTPS proxy:
   ```bash
   gcloud compute target-https-proxies update www-paygateprime-https-proxy \
       --ssl-certificates=www-paygateprime-temp \
       --global
   ```

3. Wait 2-5 minutes (www domain already verified)

4. Site will work at `www.paygateprime.com`
   - Apex domain will redirect to www via HTTP (works)
   - WWW will work via HTTPS

**Pros:**
- ✅ Very fast (2-5 minutes)
- ✅ Gets site back online quickly

**Cons:**
- ⚠️ Apex domain users will see HTTP→HTTPS redirect warning
- ⚠️ Need to fix apex domain SSL later

---

## Recommended Action Plan

### Immediate (Next 5 Minutes)

**Use Option 3 - Get WWW working ASAP:**

```bash
# 1. Create WWW-only certificate
gcloud compute ssl-certificates create www-paygateprime-temp \
    --domains=www.paygateprime.com \
    --global

# 2. Update HTTPS proxy
gcloud compute target-https-proxies update www-paygateprime-https-proxy \
    --ssl-certificates=www-paygateprime-temp \
    --global

# 3. Check status (wait 2-5 minutes)
gcloud compute ssl-certificates describe www-paygateprime-temp --global
```

**Result:** `www.paygateprime.com` will work in 2-5 minutes

---

### Follow-up (After 15 Minutes)

**Verify DNS propagation and recreate combined certificate:**

```bash
# 1. Verify DNS is correct
dig paygateprime.com A +short
# Must return: 35.244.222.18

# 2. Delete temporary certificate
gcloud compute ssl-certificates delete www-paygateprime-temp --global

# 3. Create final combined certificate
gcloud compute ssl-certificates create paygateprime-ssl-final \
    --domains=www.paygateprime.com,paygateprime.com \
    --global

# 4. Update HTTPS proxy
gcloud compute target-https-proxies update www-paygateprime-https-proxy \
    --ssl-certificates=paygateprime-ssl-final \
    --global

# 5. Monitor provisioning
watch -n 10 "gcloud compute ssl-certificates describe paygateprime-ssl-final --global --format='yaml(managed.status,managed.domainStatus)'"
```

**Result:** Both domains will work within 10-15 minutes

---

## Prevention for Future

### Checklist for Service Deletion

Before deleting any Cloud Run service with domain mapping:

- [ ] Check if service has domain mapping: `gcloud beta run domain-mappings list`
- [ ] Verify what DNS points to service: `dig <domain> A`
- [ ] Ensure alternative infrastructure is ready and SSL is ACTIVE
- [ ] Update DNS BEFORE deleting service
- [ ] Wait for DNS propagation (15 minutes)
- [ ] Then delete service

### Best Practice

**When migrating infrastructure:**
1. ✅ Build new infrastructure
2. ✅ Create SSL certificates for new infrastructure
3. ✅ Wait for SSL to be ACTIVE on all domains
4. ✅ Update DNS
5. ✅ Wait for DNS propagation
6. ✅ Verify new infrastructure works
7. ✅ Delete old infrastructure

**We did it in this order (caused issue):**
1. ✅ Build new infrastructure
2. ✅ Create SSL certificates
3. ❌ Delete old infrastructure (BEFORE DNS update)
4. ❌ SSL got stuck
5. ❌ Site went down

---

## Current DNS Status Check

```bash
# Check what Cloudflare is actually serving
dig @1.1.1.1 paygateprime.com A +short
# Returns: 35.244.222.18 ✅

# Check what our local DNS sees
dig paygateprime.com A +short
# Returns: 35.244.222.18 ✅
```

**DNS is correct!** The issue is purely SSL certificate provisioning.

---

## Monitoring Commands

```bash
# Check SSL certificate status
gcloud compute ssl-certificates describe paygateprime-ssl-combined --global --format='yaml(managed.status,managed.domainStatus)'

# Check HTTPS proxy configuration
gcloud compute target-https-proxies describe www-paygateprime-https-proxy --global --format='yaml(sslCertificates)'

# Test HTTP connection
curl -I http://paygateprime.com

# Test HTTPS connection
curl -Ik https://www.paygateprime.com

# Check DNS
dig paygateprime.com A +short
dig www.paygateprime.com A +short
```

---

## Summary

**Problem:** Deleted Cloud Run service before SSL certificate finished provisioning, breaking apex domain verification.

**Impact:** Complete site outage (both HTTP and HTTPS).

**Quick Fix:** Create WWW-only certificate → Site back in 2-5 minutes.

**Proper Fix:** Delete failed certificate, create new one → Site fully functional in 15 minutes.

**Root Lesson:** Never delete infrastructure that SSL verification depends on until new SSL is ACTIVE.

---

**NEXT ACTION:** Execute Option 3 (WWW-only temp certificate) to restore service immediately.
