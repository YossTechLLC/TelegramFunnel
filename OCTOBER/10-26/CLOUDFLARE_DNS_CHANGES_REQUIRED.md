# Cloudflare DNS Changes Required for PayGatePrime Domain Fix

**Date:** 2025-11-15
**Purpose:** Fix `paygateprime.com` routing to show new website (currently shows old registration page)

---

## Current DNS Configuration

### paygateprime.com (Apex Domain) - NEEDS TO BE CHANGED
```
Type: A
Name: @ (or paygateprime.com)
Current Values: (4 records)
  - 216.239.32.21  (Cloud Run IP)
  - 216.239.34.21  (Cloud Run IP)
  - 216.239.36.21  (Cloud Run IP)
  - 216.239.38.21  (Cloud Run IP)
Proxy Status: Unknown (need to check in Cloudflare)
```

### www.paygateprime.com (WWW Subdomain) - KEEP AS-IS
```
Type: A
Name: www
Current Value: 35.244.222.18  (Load Balancer IP)
Proxy Status: Should be DNS only (not proxied through Cloudflare)
```

---

## Required DNS Changes

### Action: Update Apex Domain A Records

**REMOVE the 4 Cloud Run IP addresses:**
- ❌ 216.239.32.21
- ❌ 216.239.34.21
- ❌ 216.239.36.21
- ❌ 216.239.38.21

**REPLACE with single Load Balancer IP:**
- ✅ 35.244.222.18

---

## Step-by-Step Instructions for Cloudflare

### 1. Login to Cloudflare
- Go to https://dash.cloudflare.com/
- Select the `paygateprime.com` domain

### 2. Navigate to DNS Records
- Click on "DNS" in the left sidebar
- Find the DNS records section

### 3. Identify Apex Domain Records
- Look for records with:
  - Type: A
  - Name: @ (or paygateprime.com or just the domain)

### 4. Delete Old Cloud Run Records
- You should see 4 A records with Cloud Run IPs
- Click the "Edit" or "Delete" button for each
- Delete all 4 records pointing to 216.239.x.x

### 5. Add New Load Balancer Record
- Click "Add record"
- Configure as follows:
  ```
  Type: A
  Name: @ (or leave blank for apex domain)
  IPv4 address: 35.244.222.18
  Proxy status: DNS only (disable Cloudflare proxy - click the cloud icon to turn it gray)
  TTL: Auto
  ```
- Click "Save"

### 6. Verify WWW Record (Should Already Exist)
- Confirm there's an A record for `www` pointing to `35.244.222.18`
- Ensure it's set to "DNS only" (not proxied)

---

## Expected Result After DNS Changes

### Before Changes
- `paygateprime.com` → Cloud Run (OLD registration page)
- `www.paygateprime.com` → Load Balancer (NEW website)

### After Changes
- `paygateprime.com` → Load Balancer → 301 Redirect → `www.paygateprime.com` (NEW website)
- `www.paygateprime.com` → Load Balancer (NEW website)

---

## Important Notes

### 1. DNS Propagation Time
- Changes typically propagate within **5-15 minutes**
- Full global propagation may take up to **24-48 hours**
- Use https://dnschecker.org to verify propagation

### 2. Cloudflare Proxy Settings
- **MUST be set to "DNS only" (gray cloud icon)**
- If using Cloudflare proxy (orange cloud), it may interfere with Google Cloud Load Balancer
- For SSL to work properly with Google-managed certificates, DNS only mode is required

### 3. SSL Certificate Status
- Google is currently provisioning a new SSL certificate that covers BOTH domains
- Certificate Status: **PROVISIONING** (15-60 minutes to complete)
- Check status: `gcloud compute ssl-certificates describe paygateprime-ssl-combined --global`
- Once status shows **ACTIVE**, the redirect will work over HTTPS

### 4. Cloud Run Domain Mapping
- Currently there's a Cloud Run domain mapping for `paygateprime.com`
- This will be removed AFTER DNS changes propagate
- Keeping it temporarily ensures no downtime during transition

---

## Verification Steps (After DNS Changes)

### 1. Check DNS Resolution
```bash
# Should return 35.244.222.18 (Load Balancer IP)
dig paygateprime.com +short
dig www.paygateprime.com +short
```

### 2. Test HTTP Redirect
```bash
# Should return 301 redirect to www.paygateprime.com
curl -I http://paygateprime.com
```

### 3. Test HTTPS Redirect (Once SSL cert is ACTIVE)
```bash
# Should return 301 redirect to www.paygateprime.com
curl -I https://paygateprime.com
```

### 4. Test WWW Domain
```bash
# Should return 200 OK with website content
curl -I https://www.paygateprime.com
```

### 5. Test in Browser
- Visit https://paygateprime.com
- Should automatically redirect to https://www.paygateprime.com
- Should show the NEW website (not old registration page)

---

## Rollback Plan (If Needed)

If something goes wrong, you can revert the DNS changes:

1. Delete the new A record (35.244.222.18)
2. Add back the 4 Cloud Run IP addresses:
   - 216.239.32.21
   - 216.239.34.21
   - 216.239.36.21
   - 216.239.38.21
3. Wait for DNS to propagate back (5-15 minutes)

The Cloud Run domain mapping will still be active, so the old site will continue working.

---

## Timeline

1. ✅ **Completed:** URL Map updated with redirect rule
2. ✅ **Completed:** New SSL certificate created and attached to HTTPS proxy
3. ⏳ **In Progress:** SSL certificate provisioning (15-60 minutes)
4. ⏳ **Waiting:** DNS changes in Cloudflare (requires manual action)
5. ⏳ **Pending:** DNS propagation (5-15 minutes after changes)
6. ⏳ **Pending:** Remove Cloud Run domain mapping (after verification)
7. ⏳ **Pending:** Delete old SSL certificate (cleanup)

---

## Contact Information

If you need help with Cloudflare access or have questions:
- Check Cloudflare account: [Your Cloudflare email]
- Domain registrar: [Check where paygateprime.com is registered]

---

## Summary

**What to do in Cloudflare:**
1. Delete 4 A records for apex domain (216.239.x.x)
2. Add 1 new A record for apex domain (35.244.222.18)
3. Ensure Cloudflare proxy is DISABLED (DNS only - gray cloud)
4. Wait 15 minutes for DNS propagation
5. Test that https://paygateprime.com redirects to https://www.paygateprime.com

**Current Status:**
- Google Cloud infrastructure: ✅ Ready
- SSL Certificate: ⏳ Provisioning (check in ~30 minutes)
- DNS Changes: ⏳ Waiting for you to update Cloudflare
