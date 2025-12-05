# PayGatePrime Domain Investigation Report
**Date:** 2025-11-14  
**Status:** ✅ INVESTIGATION COMPLETE

---

## Executive Summary

The investigation revealed that `paygateprime.com` and `www.paygateprime.com` are serving different content due to **TWO COMPLETELY SEPARATE INFRASTRUCTURE CONFIGURATIONS**:

1. **paygateprime.com (without www)** → Serves OLD registration page via Cloud Run domain mapping
2. **www.paygateprime.com** → Serves NEW website via Cloud Load Balancer + Cloud Storage bucket

---

## Detailed Findings

### 1. DNS Configuration Analysis

#### `paygateprime.com` (without www)
- **DNS Records:** 4 A records pointing to Google Cloud Run IPs
  ```
  216.239.32.21
  216.239.34.21
  216.239.36.21
  216.239.38.21
  ```
- **Nameservers:** Cloudflare
  ```
  kip.ns.cloudflare.com
  roxy.ns.cloudflare.com
  ```
- **Infrastructure:** Cloud Run Domain Mapping
- **Target Service:** `gcregister10-26` (Cloud Run service)

#### `www.paygateprime.com`
- **DNS Record:** Single A record pointing to Cloud Load Balancer
  ```
  35.244.222.18
  ```
- **Infrastructure:** Cloud Load Balancer (www-paygateprime-ip)
- **Target Backend:** Cloud Storage bucket `www-paygateprime-com`

---

### 2. Cloud Run Configuration (Serving paygateprime.com)

**Domain Mapping:**
```json
{
  "name": "paygateprime.com",
  "spec": {
    "routeName": "gcregister10-26"
  },
  "status": {
    "conditions": [
      {
        "type": "Ready",
        "status": "True"
      },
      {
        "type": "CertificateProvisioned",
        "status": "True"
      }
    ],
    "mappedRouteName": "gcregister10-26"
  }
}
```

**Cloud Run Service:** `gcregister10-26`
- **Region:** us-central1
- **Image:** `us-central1-docker.pkg.dev/telepay-459221/cloud-run-source-deploy/gcregister10-26`
- **Service URL:** `https://gcregister10-26-pjxwjsdktq-uc.a.run.app`
- **Created:** 2025-11-15T00:20:02
- **Purpose:** OLD channel registration form (GCRegister10-26)
- **Content Served:** HTML registration form with Bootstrap styling

**Sample Content from paygateprime.com:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Register Channel - GCRegister</title>
    ...
</head>
<body>
    <header class="bg-primary text-white py-3 mb-4">
        <div class="container">
            <h1 class="h3 mb-0">🚀 Telegram Channel Registration</h1>
            <p class="mb-0 small">Register your channels for the payment subscription system</p>
        </div>
    </header>
    ...
```

---

### 3. Cloud Load Balancer Configuration (Serving www.paygateprime.com)

**Load Balancer Components:**

1. **Global IP Address:**
   - Name: `www-paygateprime-ip`
   - Address: `35.244.222.18`
   - Type: EXTERNAL, PREMIUM tier
   - Status: IN_USE

2. **Forwarding Rules:**
   - **HTTP Rule:** `www-paygateprime-http-rule`
     - Port: 80
     - Target: `www-paygateprime-http-proxy`
   
   - **HTTPS Rule:** `www-paygateprime-https-rule`
     - Port: 443
     - Target: `www-paygateprime-https-proxy`

3. **SSL Certificate:**
   - Name: `www-paygateprime-ssl`
   - Type: MANAGED (Google-managed)
   - Domain: `www.paygateprime.com` ONLY
   - Status: ACTIVE
   - Expiration: 2026-01-26

4. **URL Map:**
   - Name: `www-paygateprime-urlmap`
   - **Host Rules:** Configured for `www.paygateprime.com` ONLY
   - Default Service: `www-paygateprime-backend` (backend bucket)

5. **Backend Bucket:**
   - Name: `www-paygateprime-backend`
   - Storage Bucket: `www-paygateprime-com`
   - CDN Enabled: YES
   - Cache Mode: CACHE_ALL_STATIC
   - TTL: 3600s (1 hour)

6. **Storage Bucket:**
   - Name: `www-paygateprime-com`
   - Location: US-CENTRAL1
   - Created: 2025-10-29T06:41:28
   - Website Config:
     - Main Page: `index.html`
     - Not Found Page: `index.html`
   - Contents:
     ```
     gs://www-paygateprime-com/index.html
     gs://www-paygateprime-com/assets/
     ```

---

### 4. Additional Storage Bucket Found

**Bucket:** `paygateprime-static`
- **Location:** US-CENTRAL1
- **Created:** 2025-11-02T12:22:36
- **Contents:** `payment-processing.html`
- **Status:** NOT currently in use by any load balancer
- **Purpose:** Appears to be an older/alternate bucket

---

## Root Cause Analysis

The domain split is caused by **TWO INDEPENDENT INFRASTRUCTURE SETUPS**:

### Configuration 1: Cloud Run Domain Mapping (paygateprime.com)
- **Created:** 2025-10-28
- **Purpose:** Direct Cloud Run service mapping
- **DNS Setup:** Cloudflare A records → Google Cloud Run IPs
- **Content:** OLD GCRegister10-26 registration form
- **SSL:** Managed by Cloud Run (auto-provisioned)

### Configuration 2: Cloud Load Balancer (www.paygateprime.com)
- **Created:** 2025-10-28/29
- **Purpose:** Static website hosting via Cloud Storage
- **DNS Setup:** Cloudflare A record → Load Balancer IP (35.244.222.18)
- **Content:** NEW website with modern assets
- **SSL:** Managed Google SSL certificate

---

## Why This Happened

1. **Cloud Run Domain Mapping** was created FIRST for `paygateprime.com` on 2025-10-28
2. **Load Balancer setup** was created LATER for `www.paygateprime.com` on 2025-10-28/29
3. The URL Map in the Load Balancer has a **host rule that ONLY matches `www.paygateprime.com`**
4. There is NO redirect from the apex domain to www subdomain
5. DNS records point to different infrastructure:
   - Apex domain → Cloud Run IPs
   - WWW subdomain → Load Balancer IP

---

## Recommended Solutions

### Option 1: Redirect Apex to WWW (RECOMMENDED)
**Best Practice:** Use www as the canonical domain

**Steps:**
1. Update the Load Balancer URL Map to handle BOTH domains
2. Add host rule for `paygateprime.com` with redirect to `www.paygateprime.com`
3. Update SSL certificate to include both domains
4. Update DNS A records for `paygateprime.com` to point to Load Balancer IP (35.244.222.18)
5. Remove Cloud Run domain mapping for `paygateprime.com`

**Pros:**
- Industry standard (www is canonical)
- Maintains current SSL cert setup
- Clean redirect preserves SEO

**Cons:**
- Users must access via www (minor UX consideration)

---

### Option 2: Serve Both from Load Balancer (ALTERNATIVE)
**Approach:** Make both domains serve the same content

**Steps:**
1. Add `paygateprime.com` to URL Map host rules
2. Update SSL certificate to include both domains (managed cert supports multiple)
3. Update DNS A records for `paygateprime.com` to point to Load Balancer IP (35.244.222.18)
4. Configure both to use same backend bucket
5. Remove Cloud Run domain mapping for `paygateprime.com`

**Pros:**
- Both domains work identically
- No redirect needed
- Better UX (works with or without www)

**Cons:**
- Duplicate content (mild SEO concern)
- Slightly more complex certificate management

---

### Option 3: Redirect WWW to Apex (NOT RECOMMENDED)
**Approach:** Use apex domain as canonical

**Steps:**
1. Move all content to serve from apex domain
2. Reconfigure infrastructure

**Pros:**
- Shorter URL

**Cons:**
- Against industry best practices
- More complex DNS setup
- Some DNS providers don't support ALIAS/ANAME records well
- Current infrastructure already optimized for www

---

## Implementation Plan (Option 1 - Recommended)

### Phase 1: Update Load Balancer Configuration
```bash
# 1. Update URL Map to add redirect from apex to www
gcloud compute url-maps export www-paygateprime-urlmap --destination=urlmap-config.yaml

# Edit urlmap-config.yaml to add:
# hostRules:
# - hosts:
#   - paygateprime.com
#   pathMatcher: redirect-to-www
# pathMatchers:
# - name: redirect-to-www
#   defaultUrlRedirect:
#     hostRedirect: www.paygateprime.com
#     redirectResponseCode: MOVED_PERMANENTLY_DEFAULT

gcloud compute url-maps import www-paygateprime-urlmap --source=urlmap-config.yaml --global
```

### Phase 2: Update SSL Certificate
```bash
# Update managed SSL cert to include both domains
gcloud compute ssl-certificates update www-paygateprime-ssl \
    --domains=www.paygateprime.com,paygateprime.com \
    --global
```

### Phase 3: Update DNS (in Cloudflare)
```
# Update A records for paygateprime.com to point to Load Balancer
Type: A
Name: @
Value: 35.244.222.18
Proxy: DNS only (or disable CF proxy)
```

### Phase 4: Remove Cloud Run Domain Mapping
```bash
gcloud beta run domain-mappings delete paygateprime.com --region=us-central1
```

### Phase 5: Test and Verify
```bash
# Test apex domain redirect
curl -I https://paygateprime.com
# Should see: Location: https://www.paygateprime.com

# Test www domain
curl -I https://www.paygateprime.com
# Should see: 200 OK with content from bucket
```

---

## Migration Risk Assessment

### Low Risk Items
- ✅ DNS change is reversible
- ✅ Load Balancer changes are non-destructive
- ✅ SSL certificate update is managed by Google
- ✅ Old Cloud Run service can remain active during transition

### Medium Risk Items
- ⚠️ SSL certificate provisioning takes 15-60 minutes
- ⚠️ DNS propagation takes time (TTL dependent)
- ⚠️ CDN cache may need invalidation

### Mitigation Strategy
1. Perform changes during low-traffic period
2. Keep Cloud Run mapping active until DNS fully propagates
3. Test thoroughly before removing Cloud Run mapping
4. Have rollback plan ready

---

## Additional Notes

### Current Service Inventory
- **gcregister10-26** (Cloud Run) - Currently serving paygateprime.com
- **gcregisterapi-10-26** (Cloud Run) - Backend API service
- **www-paygateprime-com** (Storage bucket) - Contains new website
- **paygateprime-static** (Storage bucket) - Unused, contains payment-processing.html

### Deprecated/Unused Resources
Consider cleaning up:
- `paygateprime-static` bucket (if truly not needed)
- Old Cloud Run domain mapping after migration

---

## Questions for Decision

1. **Which option do you prefer?** (Option 1 recommended)
2. **When should migration occur?** (suggested: low-traffic period)
3. **Should we keep gcregister10-26 Cloud Run service?** (may still be needed for other purposes)
4. **What is the purpose of paygateprime-static bucket?** (can it be deleted?)

---

## Summary

| Domain | Current Infrastructure | Current Content | Desired State |
|--------|------------------------|-----------------|---------------|
| paygateprime.com | Cloud Run (gcregister10-26) | OLD registration form | Redirect to www |
| www.paygateprime.com | Load Balancer + Storage | NEW website | Keep as-is |

**Next Steps:** Await your decision on which option to implement, then proceed with detailed implementation.
