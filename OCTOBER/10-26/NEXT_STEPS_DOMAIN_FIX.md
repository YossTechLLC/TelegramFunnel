# Next Steps to Complete Domain Fix

**Status:** ⏳ Waiting for SSL certificate provisioning and DNS changes

---

## Current Status (2025-11-15)

### ✅ Completed Steps

1. **URL Map Updated**
   - Added redirect rule for `paygateprime.com` → `www.paygateprime.com`
   - Path matcher configured with 301 permanent redirect
   - HTTPS redirect enabled
   - Query strings preserved during redirect

2. **SSL Certificate Created**
   - New certificate: `paygateprime-ssl-combined`
   - Covers both: `www.paygateprime.com` AND `paygateprime.com`
   - Type: Google-managed (auto-renewal)
   - Status: **PROVISIONING** (started at 16:33 PST)

3. **HTTPS Proxy Updated**
   - Proxy: `www-paygateprime-https-proxy`
   - Now using new certificate: `paygateprime-ssl-combined`
   - Will automatically serve both domains once cert is active

4. **Documentation Created**
   - `CLOUDFLARE_DNS_CHANGES_REQUIRED.md` - Step-by-step DNS update guide
   - `PAYGATEPRIME_DOMAIN_INVESTIGATION_REPORT.md` - Full technical analysis

---

## ⏳ Waiting For

### 1. SSL Certificate Provisioning (15-60 minutes)

**Check status with:**
```bash
gcloud compute ssl-certificates describe paygateprime-ssl-combined --global --format="yaml(managed.status,managed.domainStatus)"
```

**Expected output when ready:**
```yaml
managed:
  domainStatus:
    paygateprime.com: ACTIVE
    www.paygateprime.com: ACTIVE
  status: ACTIVE
```

**Action:** Wait until status shows ACTIVE for both domains

---

### 2. DNS Changes in Cloudflare (MANUAL ACTION REQUIRED)

**You need to:**
1. Login to Cloudflare dashboard
2. Navigate to `paygateprime.com` DNS settings
3. Delete 4 A records pointing to Cloud Run IPs (216.239.x.x)
4. Add 1 A record pointing to Load Balancer IP: `35.244.222.18`
5. Ensure Cloudflare proxy is DISABLED (gray cloud icon)

**Detailed instructions:** See `CLOUDFLARE_DNS_CHANGES_REQUIRED.md`

---

## Next Steps (After SSL Cert is ACTIVE and DNS is Updated)

### Step 1: Verify SSL Certificate
```bash
gcloud compute ssl-certificates describe paygateprime-ssl-combined --global
```
- Confirm both domains show **ACTIVE** status

### Step 2: Verify DNS Propagation
```bash
# Should return 35.244.222.18 for BOTH
dig paygateprime.com +short
dig www.paygateprime.com +short
```

### Step 3: Test Redirect
```bash
# Test HTTP redirect
curl -I http://paygateprime.com

# Test HTTPS redirect
curl -I https://paygateprime.com

# Expected response:
# HTTP/1.1 301 Moved Permanently
# Location: https://www.paygateprime.com/
```

### Step 4: Test WWW Domain
```bash
curl -I https://www.paygateprime.com

# Expected response:
# HTTP/1.1 200 OK
```

### Step 5: Test in Browser
- Open https://paygateprime.com
- Verify automatic redirect to https://www.paygateprime.com
- Verify NEW website loads (not old registration page)
- Check URL bar shows `www.paygateprime.com`

---

## Step 6: Remove Cloud Run Domain Mapping (After Verification)

**Only proceed after confirming everything works!**

```bash
# Check current domain mapping
gcloud beta run domain-mappings list --region=us-central1

# Delete the mapping
gcloud beta run domain-mappings delete paygateprime.com --region=us-central1

# Confirm deletion
gcloud beta run domain-mappings list --region=us-central1
```

---

## Step 7: Cleanup Old SSL Certificate (Optional)

**After everything is working for 24 hours:**

```bash
# Verify old cert is no longer in use
gcloud compute target-https-proxies describe www-paygateprime-https-proxy --global

# If not in use, delete it
gcloud compute ssl-certificates delete www-paygateprime-ssl --global
```

---

## Monitoring Commands

### Check SSL Certificate Status
```bash
watch -n 30 'gcloud compute ssl-certificates describe paygateprime-ssl-combined --global --format="value(managed.status)"'
```

### Check DNS Resolution
```bash
watch -n 10 'echo "Apex:"; dig paygateprime.com +short; echo "WWW:"; dig www.paygateprime.com +short'
```

### Check Load Balancer Status
```bash
gcloud compute url-maps describe www-paygateprime-urlmap --global --format="yaml(hostRules)"
```

---

## Troubleshooting

### If SSL Certificate Fails to Provision

**Symptoms:**
- Status stays "PROVISIONING" for >2 hours
- Status shows "FAILED_NOT_VISIBLE" or similar

**Causes:**
- DNS not pointing to Load Balancer yet
- Cloudflare proxy is enabled (orange cloud)
- Domain ownership verification failed

**Solution:**
1. Ensure DNS A record points to 35.244.222.18
2. Ensure Cloudflare proxy is DISABLED (gray cloud)
3. Wait 15 minutes and check again
4. If still failing, delete and recreate certificate

---

### If Redirect Not Working

**Symptoms:**
- Visiting paygateprime.com doesn't redirect
- Shows old registration page

**Possible causes:**
1. DNS hasn't propagated yet → Wait 15 minutes
2. Browser cache → Try incognito mode or different browser
3. SSL cert not active yet → Check cert status
4. Cloudflare proxy interfering → Disable CF proxy

**Solution:**
```bash
# Check actual DNS resolution
dig paygateprime.com +short

# Check if Load Balancer is receiving traffic
gcloud logging read 'resource.type="http_load_balancer"' --limit 10

# Test with curl (bypasses browser cache)
curl -I -L https://paygateprime.com
```

---

### If www.paygateprime.com Stops Working

**This should NOT happen, but if it does:**

**Rollback steps:**
1. Update HTTPS proxy back to old certificate:
   ```bash
   gcloud compute target-https-proxies update www-paygateprime-https-proxy \
     --ssl-certificates=www-paygateprime-ssl \
     --global
   ```

2. Revert URL Map if needed:
   ```bash
   gcloud compute url-maps import www-paygateprime-urlmap \
     --source=/tmp/urlmap-config.yaml \
     --global
   ```

---

## Timeline Estimate

| Step | Duration | Notes |
|------|----------|-------|
| SSL Cert Provisioning | 15-60 min | Automatic, just wait |
| DNS Changes in Cloudflare | 5 min | Manual action required |
| DNS Propagation | 5-15 min | Automatic |
| Testing & Verification | 10 min | Manual testing |
| Remove Cloud Run Mapping | 2 min | After confirming everything works |
| **Total** | **~1-2 hours** | Mostly waiting time |

---

## Success Criteria

✅ SSL certificate shows ACTIVE for both domains
✅ DNS resolves paygateprime.com to 35.244.222.18
✅ HTTP redirect works (paygateprime.com → www.paygateprime.com)
✅ HTTPS redirect works (paygateprime.com → www.paygateprime.com)
✅ www.paygateprime.com serves NEW website
✅ Browser shows correct URL after redirect
✅ Cloud Run domain mapping removed
✅ No SSL certificate warnings in browser

---

## Current Action Required

**YOU NEED TO:**
1. ⏳ Wait ~30 minutes for SSL certificate to finish provisioning
2. 📝 Update DNS in Cloudflare (see CLOUDFLARE_DNS_CHANGES_REQUIRED.md)
3. ⏳ Wait 15 minutes for DNS propagation
4. ✅ Test everything works
5. 🗑️ Remove Cloud Run domain mapping

**Check SSL cert status in ~30 minutes:**
```bash
gcloud compute ssl-certificates describe paygateprime-ssl-combined --global
```

When it shows ACTIVE, proceed with Cloudflare DNS changes!
