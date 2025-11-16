# Individual Service Deployment Scripts

This directory contains individual deployment scripts for each of the 15 PayGatePrime v1 services. These scripts provide granular control over service deployment, allowing you to deploy services one at a time or in specific groups.

---

## 📋 Overview

**Total Services:** 15
**Project:** pgp-live
**Region:** us-central1
**Deployment Mode:** Cloud Run (serverless containers)

---

## 🎯 Quick Start

### Deploy All Services (Recommended Order)

```bash
# Make all scripts executable
chmod +x *.sh

# Deploy all services in correct order
./deploy_all_services.sh
```

### Deploy Individual Services

```bash
# Example: Deploy only the main API
./deploy_gcregisterapi.sh

# Example: Deploy payment processing chain
./deploy_gcwebhook1.sh
./deploy_gcwebhook2.sh
```

---

## 📦 Service List

### 1. Public Services (External Access)

| Script | Service | Purpose | Authentication |
|--------|---------|---------|----------------|
| `deploy_gcregisterapi.sh` | pgp-server-v1 | Main backend API | Public |
| `deploy_np_webhook.sh` | pgp-npwebhook-v1 | NowPayments IPN handler | Public |
| `deploy_telepay.sh` | pgp-bot-v1 | Telegram bot | Public |

### 2. Payment Processing Services (Internal Only)

| Script | Service | Purpose |
|--------|---------|---------|
| `deploy_gcwebhook1.sh` | pgp-webhook1-v1 | Primary payment processor |
| `deploy_gcwebhook2.sh` | pgp-webhook2-v1 | Telegram invite handler |

### 3. Split Payment Services (Internal Only)

| Script | Service | Purpose |
|--------|---------|---------|
| `deploy_gcsplit1.sh` | pgp-split1-v1 | Payment splitter |
| `deploy_gcsplit2.sh` | pgp-split2-v1 | Payment router |
| `deploy_gcsplit3.sh` | pgp-split3-v1 | Accumulator enqueuer |

### 4. Host Payment Services (Internal Only)

| Script | Service | Purpose |
|--------|---------|---------|
| `deploy_gchostpay1.sh` | pgp-hostpay1-v1 | Crypto conversion executor |
| `deploy_gchostpay2.sh` | pgp-hostpay2-v1 | Conversion monitor |
| `deploy_gchostpay3.sh` | pgp-hostpay3-v1 | Blockchain validator |

### 5. Batch Processing Services (Internal Only)

| Script | Service | Purpose |
|--------|---------|---------|
| `deploy_gcaccumulator.sh` | pgp-accumulator-v1 | Payment accumulator |
| `deploy_gcbatchprocessor.sh` | pgp-batchprocessor-v1 | Batch processor |
| `deploy_gcmicrobatchprocessor.sh` | pgp-microbatchprocessor-v1 | Micro batch processor |

---

## 🔄 Deployment Order

For optimal deployment, follow this order:

### Phase 1: Critical Public Services (Deploy First)
1. `deploy_gcregisterapi.sh` - Main API
2. `deploy_np_webhook.sh` - Payment webhook handler

**After Phase 1:** Run `05_create_service_url_secrets.sh` to update URL secrets

### Phase 2: Payment Processing
3. `deploy_gcwebhook1.sh` - Payment processor
4. `deploy_gcwebhook2.sh` - Telegram invites

**After Phase 2:** Update URL secrets again

### Phase 3: Split Payment Services
5. `deploy_gcsplit1.sh` - Splitter
6. `deploy_gcsplit2.sh` - Router
7. `deploy_gcsplit3.sh` - Accumulator enqueuer

**After Phase 3:** Update URL secrets again

### Phase 4: Host Payment Services
8. `deploy_gchostpay1.sh` - Crypto executor
9. `deploy_gchostpay2.sh` - Conversion monitor
10. `deploy_gchostpay3.sh` - Blockchain validator

**After Phase 4:** Update URL secrets again

### Phase 5: Batch Processors
11. `deploy_gcaccumulator.sh` - Accumulator
12. `deploy_gcbatchprocessor.sh` - Batch processor
13. `deploy_gcmicrobatchprocessor.sh` - Micro batch processor

**After Phase 5:** Update URL secrets again

### Phase 6: Telegram Bot
14. `deploy_telepay.sh` - Telegram bot

---

## ⚙️ Configuration

### Service Resources

Most services use:
- **Memory:** 512Mi
- **CPU:** 1 vCPU
- **Timeout:** 300s (5 minutes)
- **Concurrency:** 80 requests

**Exceptions:**
- **Batch Processors:** 1Gi memory, 2 vCPUs, 900s timeout
- **Reason:** Handle larger batch operations

### Authentication

- **Public Services:** `--allow-unauthenticated`
  - pgp-server-v1
  - pgp-npwebhook-v1
  - pgp-bot-v1

- **Internal Services:** `--no-allow-unauthenticated`
  - All webhook, split, hostpay, and batch services
  - Only accessible via Cloud Tasks with proper service account

---

## 🔐 Prerequisites

Before deploying services, ensure:

1. ✅ All required APIs are enabled (`01_enable_apis.sh`)
2. ✅ Cloud SQL instance created (`02_create_cloudsql.sh`)
3. ✅ All secrets created (`03_create_secrets.sh`, `04_create_queue_secrets.sh`)
4. ✅ Service account created with proper IAM roles (`06_setup_iam_permissions.sh`)
5. ✅ Cloud Tasks queues created (see `TOOLS_SCRIPTS_TESTS/scripts/`)

---

## 🧪 Testing Individual Services

After deploying a service, test it:

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe SERVICE_NAME --region=us-central1 --format="value(status.url)")

# Test public services
curl $SERVICE_URL/

# Check service health
curl $SERVICE_URL/health

# View logs
gcloud run services logs read SERVICE_NAME --region=us-central1 --limit=50
```

---

## 🔧 Troubleshooting

### Deployment Fails

1. **Check Cloud Build logs:**
   ```bash
   gcloud builds list --limit=5
   gcloud builds log BUILD_ID
   ```

2. **Verify secrets exist:**
   ```bash
   gcloud secrets list
   ```

3. **Check service account permissions:**
   ```bash
   gcloud projects get-iam-policy pgp-live \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:pgp-services@pgp-live.iam.gserviceaccount.com"
   ```

### Service Fails to Start

1. **Check service logs:**
   ```bash
   gcloud run services logs read SERVICE_NAME --region=us-central1
   ```

2. **Verify environment variables:**
   ```bash
   gcloud run services describe SERVICE_NAME --region=us-central1 \
     --format="yaml(spec.template.spec.containers[0].env)"
   ```

3. **Check Cloud SQL connection:**
   ```bash
   gcloud run services describe SERVICE_NAME --region=us-central1 \
     --format="value(spec.template.metadata.annotations.'run.googleapis.com/cloudsql-instances')"
   ```

### Secrets Not Accessible

1. **Grant access to service account:**
   ```bash
   gcloud secrets add-iam-policy-binding SECRET_NAME \
     --member="serviceAccount:pgp-services@pgp-live.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

---

## 📊 Monitoring

After deployment, monitor services:

### Cloud Logging
```bash
# View all service logs
gcloud logging read "resource.type=cloud_run_revision" --limit=100

# Filter by service
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pgp-server-v1" --limit=50

# Filter by severity
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=50
```

### Cloud Monitoring
- Create dashboards for each service
- Set up alert policies for errors
- Monitor request latency and error rates

---

## 📝 Next Steps After Deployment

1. **Run Verification Script:**
   ```bash
   cd ../
   ./10_verify_deployment.sh
   ```

2. **Configure NowPayments IPN:**
   - See `09_EXTERNAL_WEBHOOKS_CONFIG.md`
   - Update IPN URL in NowPayments dashboard

3. **Deploy Frontend:**
   ```bash
   cd ../
   ./08_deploy_frontend.sh
   ```

4. **Test End-to-End Flow:**
   - Create test user account
   - Initiate test payment
   - Monitor logs across all services

---

## 🆘 Support

For issues or questions:
1. Check logs for specific error messages
2. Verify all prerequisites are met
3. Review service-specific troubleshooting in each deployment script
4. See main deployment guide: `../README.md`

---

## 📄 License

Internal deployment scripts for PayGatePrime v1
Project: pgp-live
Region: us-central1

---

**Last Updated:** 2025-11-16
**Total Scripts:** 16 (15 individual + 1 master)
**Status:** Ready for deployment
