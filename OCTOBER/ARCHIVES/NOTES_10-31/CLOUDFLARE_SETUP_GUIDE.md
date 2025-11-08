# Cloudflare Configuration for www.paygateprime.com

## ✅ Current Status (2025-10-29)

**Frontend SPA Deployed:** https://storage.googleapis.com/www-paygateprime-com/index.html

**Backend API:** https://gcregisterapi-10-26-291176869049.us-central1.run.app

**Load Balancer:** ✅ DEPLOYED

**Static IP Address:** `35.244.222.18`

**SSL Certificate:** 🔄 Provisioning (10-15 minutes)

## Required Cloudflare Configuration

### ✅ RECOMMENDED: Google Cloud Load Balancer (DEPLOYED)

**Status:** Load Balancer fully configured with Cloud CDN enabled

**Components Deployed:**
- ✅ Backend Bucket: `www-paygateprime-backend` (linked to `www-paygateprime-com` bucket)
- ✅ URL Map: `www-paygateprime-urlmap`
- ✅ SSL Certificate: `www-paygateprime-ssl` (managed, auto-renewal)
- ✅ HTTPS Proxy: `www-paygateprime-https-proxy`
- ✅ HTTP Proxy: `www-paygateprime-http-proxy` (for redirect)
- ✅ Static IP: `35.244.222.18` (reserved)
- ✅ Forwarding Rules: HTTP (port 80) and HTTPS (port 443)
- ✅ Cloud CDN: Enabled on backend bucket

**Required Action: Update Cloudflare DNS**

1. **Log into Cloudflare Dashboard**
   - Go to https://dash.cloudflare.com
   - Select `paygateprime.com` domain
   - Navigate to **DNS** settings

2. **Update DNS Record**
   ```
   Type: A
   Name: www
   Target: 35.244.222.18
   TTL: Auto
   Proxy status: DNS Only (grey cloud) ⚠️ IMPORTANT
   ```

   **⚠️ CRITICAL:** Set Proxy status to **DNS Only** (grey cloud icon), NOT Proxied (orange cloud).

   Why? Google Cloud Load Balancer already provides:
   - SSL termination
   - Cloud CDN caching
   - DDoS protection

   Cloudflare proxying would create a "double proxy" which will break SSL certificate provisioning.

3. **Save DNS Record**
   - Click Save
   - Wait 2-5 minutes for DNS propagation

## SSL Certificate Provisioning (⏳ 10-15 minutes)

**Current Status:** PROVISIONING

After you update the Cloudflare DNS record to point to `35.244.222.18`, Google will automatically provision the SSL certificate for `www.paygateprime.com`. This process takes 10-15 minutes.

**Check SSL Status:**
```bash
gcloud compute ssl-certificates describe www-paygateprime-ssl --global --format="value(managed.status)"
```

- `PROVISIONING` → Wait 5 more minutes
- `ACTIVE` → SSL ready! Test the site

**Why does it take time?**
- Google needs to verify you control www.paygateprime.com
- DNS must point to 35.244.222.18 for verification
- Certificate is automatically renewed before expiration

## Verification Steps (After SSL = ACTIVE)

1. **Check SSL Certificate Status**
   ```bash
   gcloud compute ssl-certificates describe www-paygateprime-ssl --global
   ```

   Wait until `managed.status: ACTIVE` before testing.

2. **Test HTTPS URL**
   ```bash
   curl -I https://www.paygateprime.com
   # Should return: HTTP/2 200
   # Should show: content-type: text/html
   ```

3. **Test SPA Routing**
   - Visit: https://www.paygateprime.com/login
   - Should load React SPA login page (not 404)
   - Should see PayGate Prime logo and login form

4. **Test API Connectivity**
   - Open browser DevTools → Network tab
   - Visit https://www.paygateprime.com
   - Should see API calls to gcregisterapi-10-26-*.run.app
   - Check for CORS errors (should be none)

## Current Architecture (Updated 2025-10-29)

```
User (Browser)
 ↓
DNS: www.paygateprime.com → 35.244.222.18
 ↓
Google Cloud Load Balancer (Global, with Cloud CDN)
 ├─ HTTP (port 80) → www-paygateprime-http-proxy
 ├─ HTTPS (port 443) → www-paygateprime-https-proxy
 │   └─ SSL Certificate: www-paygateprime-ssl (auto-renewed)
 ↓
Backend Bucket: www-paygateprime-backend
 ↓
Google Cloud Storage: gs://www-paygateprime-com/
 ├─ /index.html (React SPA entry point, 674 bytes)
 ├─ /assets/index-*.js (main app bundle, 85KB)
 ├─ /assets/react-vendor-*.js (React vendor bundle, 162KB)
 ├─ /assets/form-vendor-*.js (form libraries, 0.04KB)
 └─ /assets/index-*.css (global styles, 3.4KB)
  Total: 245KB raw, ~82KB gzipped

React SPA makes API calls to:
 ↓
Google Cloud Run API: gcregisterapi-10-26-*.us-central1.run.app
 ├─ POST /api/auth/signup (create account)
 ├─ POST /api/auth/login (JWT tokens)
 ├─ POST /api/auth/refresh (refresh access token)
 ├─ GET /api/auth/me (current user)
 ├─ POST /api/channels/register (new channel)
 ├─ GET /api/channels (user's channels)
 ├─ GET /api/channels/<id> (channel details)
 ├─ PUT /api/channels/<id> (update channel)
 ├─ DELETE /api/channels/<id> (delete channel)
 └─ GET /api/mappings/currency-network (supported currencies)
```

## Troubleshooting

### Issue: 404 Not Found

**Cause:** DNS not pointing to Load Balancer or SSL not provisioned yet

**Fix:**
1. Verify A record in Cloudflare: `35.244.222.18`
2. Verify Proxy status is **DNS Only** (grey cloud), NOT Proxied
3. Check SSL status: `gcloud compute ssl-certificates describe www-paygateprime-ssl --global`
4. Wait for SSL status = ACTIVE (10-15 minutes after DNS update)
5. Clear browser cache and retry

### Issue: CORS Error in Browser Console

**Cause:** API CORS not configured for www.paygateprime.com

**Fix:**
1. Verify CORS_ORIGIN secret in Secret Manager
2. Redeploy GCRegisterAPI-10-26 if needed

### Issue: White Screen / JavaScript Errors

**Cause:** API URL not configured correctly

**Fix:**
1. Check browser console for errors
2. Verify .env file has correct VITE_API_URL
3. Rebuild frontend: `npm run build && gsutil rsync -r dist/ gs://www-paygateprime-com`

## Performance Optimization

Once deployed, verify these metrics:

- **Time to First Byte (TTFB):** <200ms (Cloudflare CDN)
- **Largest Contentful Paint (LCP):** <1s (React hydration)
- **First Input Delay (FID):** <100ms (React responsiveness)
- **Cumulative Layout Shift (CLS):** <0.1 (stable layout)

Use Lighthouse or PageSpeed Insights to measure.

## Rollback Procedure

If issues occur, revert to old Flask app:

1. **Update Cloudflare DNS**
   ```
   Type: A
   Name: www
   Target: [OLD_GCRegister10-26_CLOUD_RUN_IP]
   ```

2. **Clear Cloudflare cache**

3. **Wait 5 minutes** for DNS propagation

Old Flask app remains deployed at:
https://gcregister10-26-291176869049.us-central1.run.app

## Success Criteria

✅ www.paygateprime.com loads React SPA instantly
✅ User can signup → login → view dashboard
✅ API calls work (check Network tab)
✅ No CORS errors
✅ Page load time <1 second
✅ All routes work (/, /login, /signup, /dashboard)
