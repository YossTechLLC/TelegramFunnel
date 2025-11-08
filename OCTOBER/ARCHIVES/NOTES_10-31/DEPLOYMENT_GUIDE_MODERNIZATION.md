# Deployment Guide - GCRegister Modernization (Phase 3)

**Created:** 2025-10-29
**Version:** 1.0
**Services:** GCRegisterAPI-10-26 (Backend) + GCRegisterWeb-10-26 (Frontend)
**Architecture:** TypeScript + React SPA → Flask REST API

---

## Overview

This guide provides step-by-step instructions for deploying the modernized GCRegister architecture, which splits the monolithic Flask app into:

1. **GCRegisterAPI-10-26** - Flask REST API (Cloud Run)
2. **GCRegisterWeb-10-26** - TypeScript + React SPA (Cloud Storage + CDN)

**Key Benefits:**
- ⚡ Zero cold starts (static SPA served from CDN)
- 🎯 Real-time validation and instant feedback
- 🔐 JWT-based stateless authentication
- 📱 Mobile-first responsive design

---

## Prerequisites

Before starting deployment, ensure:

- [ ] Database migrations completed:
  - [ ] `DB_MIGRATION_THRESHOLD_PAYOUT.md` executed
  - [ ] `DB_MIGRATION_USER_ACCOUNTS.md` executed
- [ ] Google Cloud SDK installed and configured
- [ ] Project ID: `telepay-459221`
- [ ] Region: `us-central1`
- [ ] Permissions: Cloud Run Admin, Secret Manager Admin, Cloud Storage Admin

---

## Part 1: Backend API Deployment (GCRegisterAPI-10-26)

### Step 1: Verify Secrets

The following secrets must exist in Secret Manager:

```bash
# Check existing secrets
gcloud secrets list --project=telepay-459221 | grep -E "JWT_SECRET_KEY|CORS_ORIGIN|DATABASE"

# Required secrets:
# - JWT_SECRET_KEY (created automatically during setup)
# - CORS_ORIGIN (created automatically, value: https://www.paygateprime.com)
# - CLOUD_SQL_CONNECTION_NAME (existing)
# - DATABASE_NAME_SECRET (existing)
# - DATABASE_USER_SECRET (existing)
# - DATABASE_PASSWORD_SECRET (existing)
```

**If JWT_SECRET_KEY doesn't exist:**
```bash
# Generate random secret
python3 -c "import secrets; print(secrets.token_hex(32))" > /tmp/jwt_secret.txt

# Create secret
gcloud secrets create JWT_SECRET_KEY \
  --project=telepay-459221 \
  --replication-policy="automatic" \
  --data-file=/tmp/jwt_secret.txt

rm /tmp/jwt_secret.txt
```

**If CORS_ORIGIN doesn't exist:**
```bash
echo "https://www.paygateprime.com" > /tmp/cors_origin.txt

gcloud secrets create CORS_ORIGIN \
  --project=telepay-459221 \
  --replication-policy="automatic" \
  --data-file=/tmp/cors_origin.txt

rm /tmp/cors_origin.txt
```

---

### Step 2: Build Backend Docker Image

```bash
cd OCTOBER/10-26/GCRegisterAPI-10-26

# Build and push to Container Registry
gcloud builds submit \
  --tag gcr.io/telepay-459221/gcregisterapi-10-26 \
  --project=telepay-459221 \
  --timeout=10m

# Verify image exists
gcloud container images list --project=telepay-459221 | grep gcregisterapi-10-26
```

---

### Step 3: Deploy Backend to Cloud Run

```bash
gcloud run deploy gcregisterapi-10-26 \
  --image gcr.io/telepay-459221/gcregisterapi-10-26 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60s \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 10 \
  --project=telepay-459221 \
  --set-secrets="JWT_SECRET_KEY=JWT_SECRET_KEY:latest,\
CORS_ORIGIN=CORS_ORIGIN:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest"

# Get service URL
export API_URL=$(gcloud run services describe gcregisterapi-10-26 \
  --region us-central1 \
  --project=telepay-459221 \
  --format='value(status.url)')

echo "✅ Backend API deployed at: $API_URL"
```

---

### Step 4: Test Backend API

```bash
# Test health endpoint
curl $API_URL/api/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "GCRegisterAPI-10-26 REST API",
#   "version": "1.0",
#   ...
# }

# Test root endpoint (API documentation)
curl $API_URL/

# Test signup (should fail without request body, but endpoint should exist)
curl -X POST $API_URL/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{}'

# Expected: 400 Bad Request with validation errors
```

---

## Part 2: Frontend SPA Deployment (GCRegisterWeb-10-26)

### Step 5: Create Frontend Project

**Note:** Due to the large size of the React SPA (multiple TypeScript files, components, routing, etc.), the frontend implementation has been designed but needs to be created.

**Frontend Structure (Summary):**
```
GCRegisterWeb-10-26/
├── src/
│   ├── main.tsx (entry point)
│   ├── App.tsx (root component)
│   ├── pages/ (LoginPage, SignupPage, DashboardPage, etc.)
│   ├── components/ (forms, dashboard, UI components)
│   ├── services/ (API client, auth, channels)
│   ├── hooks/ (useAuth, useChannels, useForm)
│   └── types/ (TypeScript definitions)
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

**Technology Stack:**
- React 18 + TypeScript
- Vite (build tool)
- React Router (client-side routing)
- React Hook Form (form management)
- React Query (API data caching)
- Tailwind CSS (styling)
- Axios (HTTP client)

**Implementation Options:**

**Option A: Manual Creation (Recommended for Full Control)**
1. Follow `GCREGISTER_MODERNIZATION_ARCHITECTURE.md` Section 6-7
2. Use provided component examples as templates
3. Customize UI/UX as needed

**Option B: Use Existing Template (Faster)**
1. Use create-vite or similar boilerplate
2. Add authentication and channel management
3. Integrate with backend API

---

### Step 6: Build Frontend (When Ready)

```bash
cd OCTOBER/10-26/GCRegisterWeb-10-26

# Install dependencies
npm install

# Build for production
npm run build

# Output will be in dist/ folder
# - dist/index.html
# - dist/assets/*.js (bundled JS)
# - dist/assets/*.css (styles)
```

---

### Step 7: Deploy Frontend to Cloud Storage

```bash
# Create bucket (one-time)
gsutil mb -p telepay-459221 gs://www-paygateprime-com

# Set bucket to public-read
gsutil iam ch allUsers:objectViewer gs://www-paygateprime-com

# Configure as website
gsutil web set -m index.html -e index.html gs://www-paygateprime-com

# Upload files
gsutil -m rsync -r -d dist/ gs://www-paygateprime-com

# Set cache headers for assets
gsutil -m setmeta -h "Cache-Control:public, max-age=31536000" \
  'gs://www-paygateprime-com/assets/*.js'

gsutil -m setmeta -h "Cache-Control:public, max-age=31536000" \
  'gs://www-paygateprime-com/assets/*.css'

# Set short cache for index.html (always fresh)
gsutil setmeta -h "Cache-Control:public, max-age=300" \
  gs://www-paygateprime-com/index.html
```

---

### Step 8: Configure Cloud CDN (Optional but Recommended)

```bash
# Create backend bucket
gcloud compute backend-buckets create www-paygateprime-backend \
  --gcs-bucket-name=www-paygateprime-com \
  --enable-cdn \
  --project=telepay-459221

# Create URL map
gcloud compute url-maps create www-paygateprime-urlmap \
  --default-backend-bucket=www-paygateprime-backend \
  --project=telepay-459221

# Create HTTP proxy
gcloud compute target-http-proxies create www-paygateprime-http-proxy \
  --url-map=www-paygateprime-urlmap \
  --project=telepay-459221

# Reserve global IP
gcloud compute addresses create www-paygateprime-ip \
  --global \
  --ip-version=IPV4 \
  --project=telepay-459221

# Get IP address
export FRONTEND_IP=$(gcloud compute addresses describe www-paygateprime-ip \
  --global \
  --project=telepay-459221 \
  --format='value(address)')

echo "Frontend IP: $FRONTEND_IP"

# Create forwarding rule
gcloud compute forwarding-rules create www-paygateprime-http-rule \
  --global \
  --address=www-paygateprime-ip \
  --target-http-proxy=www-paygateprime-http-proxy \
  --ports=80 \
  --project=telepay-459221
```

---

### Step 9: Configure HTTPS (SSL)

```bash
# Create SSL certificate
gcloud compute ssl-certificates create www-paygateprime-ssl \
  --domains=www.paygateprime.com \
  --project=telepay-459221

# Create HTTPS proxy
gcloud compute target-https-proxies create www-paygateprime-https-proxy \
  --url-map=www-paygateprime-urlmap \
  --ssl-certificates=www-paygateprime-ssl \
  --project=telepay-459221

# Create HTTPS forwarding rule
gcloud compute forwarding-rules create www-paygateprime-https-rule \
  --global \
  --address=www-paygateprime-ip \
  --target-https-proxy=www-paygateprime-https-proxy \
  --ports=443 \
  --project=telepay-459221
```

---

### Step 10: Update DNS

Update your domain's DNS records to point to the load balancer:

```
Type: A
Name: www
Value: [FRONTEND_IP from Step 8]
TTL: 300
```

**Wait 5-10 minutes for DNS propagation**

---

## Part 3: Testing

### Test Backend API

```bash
# Test health endpoint
curl https://gcregisterapi-10-26-291176869049.us-central1.run.app/api/health

# Test signup
curl -X POST https://gcregisterapi-10-26-291176869049.us-central1.run.app/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser123",
    "email": "test@example.com",
    "password": "TestPass123!"
  }'

# Test login
curl -X POST https://gcregisterapi-10-26-291176869049.us-central1.run.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser123",
    "password": "TestPass123!"
  }'

# Save access token from response

# Test get channels (requires token)
curl https://gcregisterapi-10-26-291176869049.us-central1.run.app/api/channels \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Test Frontend (When Deployed)

1. Navigate to https://www.paygateprime.com
2. Should load instantly (no cold start)
3. Test signup flow
4. Test login flow
5. Test dashboard
6. Test channel registration
7. Test channel editing

---

## Monitoring

### Backend Logs

```bash
# Stream logs
gcloud run services logs tail gcregisterapi-10-26 \
  --region us-central1 \
  --project=telepay-459221

# View in console
# https://console.cloud.google.com/run/detail/us-central1/gcregisterapi-10-26/logs
```

### Frontend CDN Logs

```bash
# Enable Cloud CDN logging
gcloud compute backend-buckets update www-paygateprime-backend \
  --enable-logging \
  --project=telepay-459221

# View logs in Cloud Logging
# https://console.cloud.google.com/logs
```

---

## Rollback Procedure

### Rollback Backend

```bash
# List revisions
gcloud run revisions list \
  --service gcregisterapi-10-26 \
  --region us-central1 \
  --project=telepay-459221

# Revert to previous revision
gcloud run services update-traffic gcregisterapi-10-26 \
  --region us-central1 \
  --project=telepay-459221 \
  --to-revisions PREVIOUS_REVISION=100
```

### Rollback Frontend

```bash
# Restore previous version from local backup
gsutil -m rsync -r -d dist_backup/ gs://www-paygateprime-com
```

---

## Success Criteria

Deployment is successful when:

- [ ] Backend API health endpoint returns 200 OK
- [ ] Backend API signup/login works
- [ ] Frontend loads in <1 second (no cold start)
- [ ] User can signup and login via frontend
- [ ] Dashboard displays channels
- [ ] Channel registration works end-to-end
- [ ] Channel editing enforces authorization
- [ ] 10-channel limit is enforced
- [ ] No errors in Cloud Run logs
- [ ] No errors in browser console

---

## Next Steps After Deployment

1. **Monitor Performance**
   - Track API latency
   - Monitor error rates
   - Check CDN hit rates

2. **Gather Feedback**
   - Test with real users
   - Collect UX feedback
   - Identify pain points

3. **Optimize**
   - Reduce bundle size (code splitting)
   - Add service worker (PWA)
   - Implement caching strategies

4. **Security Audit**
   - Penetration testing
   - CORS verification
   - Rate limiting tuning

---

## Related Documentation

- `GCREGISTER_MODERNIZATION_ARCHITECTURE.md` - Full architecture design
- `DB_MIGRATION_USER_ACCOUNTS.md` - User account database migration
- `DB_MIGRATION_THRESHOLD_PAYOUT.md` - Threshold payout database migration
- `MAIN_ARCHITECTURE_WORKFLOW.md` - Implementation tracker

---

**Document Status:** ✅ Ready for Execution
**Backend Status:** ✅ DEPLOYED (gcregisterapi-10-26)
**Frontend Status:** ⏳ Awaiting Implementation
**Risk Level:** Medium (new architecture)
**Reversible:** Yes (rollback procedures provided)

---

**Document Version:** 1.0
**Author:** Claude (Anthropic)
**Last Updated:** 2025-10-29
