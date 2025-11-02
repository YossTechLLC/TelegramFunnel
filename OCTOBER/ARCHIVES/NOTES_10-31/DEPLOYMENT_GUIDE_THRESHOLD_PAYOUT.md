# Deployment Guide - Threshold Payout System

**Created:** 2025-10-28
**Version:** 1.0
**Target Environment:** Google Cloud Run + Cloud SQL

---

## Overview

This guide provides step-by-step instructions for deploying the Threshold Payout System to Google Cloud Platform.

**Services to Deploy:**
1. GCAccumulator-10-26 - Payment accumulation service
2. GCBatchProcessor-10-26 - Batch processing service
3. GCWebhook1-10-26 - Modified payment processor (re-deploy)
4. GCRegister10-26 - Modified registration form (re-deploy)

**Infrastructure:**
- 2 Cloud Tasks queues
- 1 Cloud Scheduler job
- Multiple Secret Manager entries

---

## Prerequisites

- [ ] Database migration completed (`DB_MIGRATION_THRESHOLD_PAYOUT.md`)
- [ ] Google Cloud SDK installed and configured
- [ ] Project ID: `telepay-459221`
- [ ] Region: `us-central1`
- [ ] Permissions: Cloud Run Admin, Cloud Tasks Admin, Secret Manager Admin

---

## Step 1: Update Secret Manager

Add new secrets for threshold payout services:

```bash
# GCAccumulator configuration
gcloud secrets create GCACCUMULATOR_QUEUE --data-file=- <<EOF
accumulator-payment-queue
EOF

gcloud secrets create GCACCUMULATOR_URL --data-file=- <<EOF
https://gcaccumulator-10-26-YOUR_PROJECT_HASH-uc.a.run.app
EOF

# GCSplit1 batch queue
gcloud secrets create GCSPLIT1_BATCH_QUEUE --data-file=- <<EOF
gcsplit1-batch-queue
EOF

# Verify secrets created
gcloud secrets list | grep -E "(GCACCUMULATOR|GCSPLIT1_BATCH)"
```

**Note:** Replace `YOUR_PROJECT_HASH` with actual Cloud Run URL after deployment.

---

## Step 2: Create Cloud Tasks Queues

Run the deployment script:

```bash
cd OCTOBER/10-26
chmod +x deploy_accumulator_tasks_queues.sh
./deploy_accumulator_tasks_queues.sh
```

**Expected Output:**
```
🚀 [DEPLOY] Starting Cloud Tasks queue deployment (Threshold Payout)
📍 [DEPLOY] Project: telepay-459221
📍 [DEPLOY] Location: us-central1

📦 [DEPLOY] Creating queue: accumulator-payment-queue
✅ [DEPLOY] Queue accumulator-payment-queue created successfully

📦 [DEPLOY] Creating queue: gcsplit1-batch-queue
✅ [DEPLOY] Queue gcsplit1-batch-queue created successfully

🎉 [DEPLOY] All Cloud Tasks queues deployed successfully!
```

**Verify queues:**
```bash
gcloud tasks queues list --location=us-central1
```

---

## Step 3: Deploy GCAccumulator-10-26

### Build and deploy:

```bash
cd OCTOBER/10-26/GCAccumulator-10-26

# Build container
gcloud builds submit --tag gcr.io/telepay-459221/gcaccumulator-10-26

# Deploy to Cloud Run
gcloud run deploy gcaccumulator-10-26 \
  --image gcr.io/telepay-459221/gcaccumulator-10-26 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 540 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "SUCCESS_URL_SIGNING_KEY=projects/telepay-459221/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,\
CLOUD_TASKS_PROJECT_ID=projects/telepay-459221/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,\
CLOUD_TASKS_LOCATION=projects/telepay-459221/secrets/CLOUD_TASKS_LOCATION/versions/latest,\
GCSPLIT2_QUEUE=projects/telepay-459221/secrets/GCSPLIT2_QUEUE/versions/latest,\
GCSPLIT2_URL=projects/telepay-459221/secrets/GCSPLIT2_URL/versions/latest,\
CLOUD_SQL_CONNECTION_NAME=projects/telepay-459221/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,\
DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest,\
DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest,\
DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest,\
TP_FLAT_FEE=projects/telepay-459221/secrets/TP_FLAT_FEE/versions/latest"
```

### Verify deployment:

```bash
# Get service URL
gcloud run services describe gcaccumulator-10-26 \
  --region us-central1 \
  --format='value(status.url)'

# Test health endpoint
curl https://gcaccumulator-10-26-YOUR_URL/health
```

**Expected health response:**
```json
{
  "status": "healthy",
  "service": "GCAccumulator-10-26 Payment Accumulation",
  "components": {
    "database": "healthy",
    "token_manager": "healthy",
    "cloudtasks": "healthy"
  }
}
```

### Update Secret Manager with service URL:

```bash
# Get the actual URL from previous command
SERVICE_URL=$(gcloud run services describe gcaccumulator-10-26 \
  --region us-central1 \
  --format='value(status.url)')

# Update secret
echo "$SERVICE_URL" | gcloud secrets versions add GCACCUMULATOR_URL --data-file=-
```

---

## Step 4: Deploy GCBatchProcessor-10-26

### Build and deploy:

```bash
cd OCTOBER/10-26/GCBatchProcessor-10-26

# Build container
gcloud builds submit --tag gcr.io/telepay-459221/gcbatchprocessor-10-26

# Deploy to Cloud Run
gcloud run deploy gcbatchprocessor-10-26 \
  --image gcr.io/telepay-459221/gcbatchprocessor-10-26 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 540 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 5 \
  --set-env-vars "TPS_HOSTPAY_SIGNING_KEY=projects/telepay-459221/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest,\
CLOUD_TASKS_PROJECT_ID=projects/telepay-459221/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,\
CLOUD_TASKS_LOCATION=projects/telepay-459221/secrets/CLOUD_TASKS_LOCATION/versions/latest,\
GCSPLIT1_BATCH_QUEUE=projects/telepay-459221/secrets/GCSPLIT1_BATCH_QUEUE/versions/latest,\
GCSPLIT1_URL=projects/telepay-459221/secrets/GCSPLIT1_URL/versions/latest,\
CLOUD_SQL_CONNECTION_NAME=projects/telepay-459221/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,\
DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest,\
DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest,\
DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest"
```

### Verify deployment:

```bash
# Get service URL
gcloud run services describe gcbatchprocessor-10-26 \
  --region us-central1 \
  --format='value(status.url)'

# Test health endpoint
curl https://gcbatchprocessor-10-26-YOUR_URL/health
```

---

## Step 5: Create Cloud Scheduler Job

Create scheduler to trigger batch processor every 5 minutes:

```bash
# Get GCBatchProcessor URL
BATCH_PROCESSOR_URL=$(gcloud run services describe gcbatchprocessor-10-26 \
  --region us-central1 \
  --format='value(status.url)')

# Create scheduler job
gcloud scheduler jobs create http batch-processor-job \
  --schedule="*/5 * * * *" \
  --uri="$BATCH_PROCESSOR_URL/process" \
  --http-method=POST \
  --location=us-central1 \
  --time-zone="America/Los_Angeles" \
  --description="Triggers batch payout processing for threshold clients"
```

### Verify scheduler:

```bash
# List jobs
gcloud scheduler jobs list --location=us-central1

# Test job manually
gcloud scheduler jobs run batch-processor-job --location=us-central1
```

---

## Step 6: Re-deploy GCWebhook1-10-26 (Modified)

Re-deploy with threshold payout routing logic:

```bash
cd OCTOBER/10-26/GCWebhook1-10-26

# Build container
gcloud builds submit --tag gcr.io/telepay-459221/gcwebhook1-10-26

# Deploy (same env vars as before + new ones)
gcloud run deploy gcwebhook1-10-26 \
  --image gcr.io/telepay-459221/gcwebhook1-10-26 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --concurrency 80 \
  --min-instances 1 \
  --max-instances 20 \
  --set-env-vars "SUCCESS_URL_SIGNING_KEY=projects/telepay-459221/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,\
CLOUD_TASKS_PROJECT_ID=projects/telepay-459221/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,\
CLOUD_TASKS_LOCATION=projects/telepay-459221/secrets/CLOUD_TASKS_LOCATION/versions/latest,\
GCWEBHOOK2_QUEUE=projects/telepay-459221/secrets/GCWEBHOOK2_QUEUE/versions/latest,\
GCWEBHOOK2_URL=projects/telepay-459221/secrets/GCWEBHOOK2_URL/versions/latest,\
GCSPLIT1_QUEUE=projects/telepay-459221/secrets/GCSPLIT1_QUEUE/versions/latest,\
GCSPLIT1_URL=projects/telepay-459221/secrets/GCSPLIT1_URL/versions/latest,\
GCACCUMULATOR_QUEUE=projects/telepay-459221/secrets/GCACCUMULATOR_QUEUE/versions/latest,\
GCACCUMULATOR_URL=projects/telepay-459221/secrets/GCACCUMULATOR_URL/versions/latest,\
CLOUD_SQL_CONNECTION_NAME=projects/telepay-459221/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,\
DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest,\
DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest,\
DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest"
```

---

## Step 7: Update GCRegister10-26 (Modified)

Apply modifications from `GCREGISTER_MODIFICATIONS_GUIDE.md`, then deploy:

```bash
cd OCTOBER/10-26/GCRegister10-26

# Build container
gcloud builds submit --tag gcr.io/telepay-459221/gcregister10-26

# Deploy
gcloud run deploy gcregister10-26 \
  --image gcr.io/telepay-459221/gcregister10-26 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --concurrency 80 \
  --min-instances 1 \
  --max-instances 10 \
  --set-env-vars [... existing env vars ...]
```

---

## Step 8: End-to-End Testing

### Test 1: Instant Payout (Existing Flow)

1. Register channel with `payout_strategy='instant'`
2. Make test payment
3. Verify logs show routing to GCSplit1
4. Confirm payment split executed

### Test 2: Threshold Payout (New Flow)

1. Register channel with `payout_strategy='threshold'`, `threshold=$500`
2. Make test payment for $50
3. Check GCWebhook1 logs:
   ```
   🔍 [ENDPOINT] Checking payout strategy for channel...
   💰 [ENDPOINT] Payout strategy: threshold
   🎯 [ENDPOINT] Threshold payout mode - $500 threshold
   ✅ [ENDPOINT] Enqueued to GCAccumulator
   ```

4. Check GCAccumulator logs:
   ```
   🎯 [ENDPOINT] Payment accumulation request received
   💰 [ENDPOINT] Payment Amount: $50
   ✅ [ENDPOINT] Database insertion successful
   📊 [ENDPOINT] Client total accumulated: $50
   🎯 [ENDPOINT] Client threshold: $500
   ⏳ [ENDPOINT] $450 remaining to reach threshold
   ```

5. Verify database:
   ```sql
   SELECT * FROM payout_accumulation
   WHERE client_id = 'YOUR_CHANNEL_ID'
   ORDER BY id DESC LIMIT 1;
   ```

6. Make 10 more payments to reach $500+
7. Wait for GCBatchProcessor run (every 5 min)
8. Check GCBatchProcessor logs:
   ```
   🔍 [ENDPOINT] Searching for clients over threshold
   📊 [ENDPOINT] Found 1 client(s) ready for payout
   💰 [ENDPOINT] Processing client: YOUR_CHANNEL_ID
   📊 [ENDPOINT] Total USDT: $520.50 (threshold: $500)
   🚀 [ENDPOINT] Enqueueing to GCSplit1
   ✅ [ENDPOINT] Task enqueued successfully
   ```

9. Verify batch created:
   ```sql
   SELECT * FROM payout_batches
   WHERE client_id = 'YOUR_CHANNEL_ID'
   ORDER BY created_at DESC LIMIT 1;
   ```

10. Verify accumulations marked paid:
    ```sql
    SELECT COUNT(*), is_paid_out
    FROM payout_accumulation
    WHERE client_id = 'YOUR_CHANNEL_ID'
    GROUP BY is_paid_out;
    ```

---

## Monitoring & Observability

### Cloud Run Logs

```bash
# GCAccumulator logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcaccumulator-10-26" \
  --limit 50 \
  --format json

# GCBatchProcessor logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbatchprocessor-10-26" \
  --limit 50 \
  --format json

# GCWebhook1 logs (threshold routing)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcwebhook1-10-26 AND textPayload=~'threshold'" \
  --limit 50 \
  --format json
```

### Cloud Tasks Monitoring

```bash
# Check queue status
gcloud tasks queues describe accumulator-payment-queue --location=us-central1
gcloud tasks queues describe gcsplit1-batch-queue --location=us-central1

# List pending tasks
gcloud tasks list --queue=accumulator-payment-queue --location=us-central1
gcloud tasks list --queue=gcsplit1-batch-queue --location=us-central1
```

### Database Queries

```sql
-- Total accumulated per client (not paid out)
SELECT
    client_id,
    COUNT(*) as payment_count,
    SUM(accumulated_amount_usdt) as total_usdt,
    MAX(payment_timestamp) as latest_payment
FROM payout_accumulation
WHERE is_paid_out = FALSE
GROUP BY client_id
ORDER BY total_usdt DESC;

-- Batch payout history
SELECT
    batch_id,
    client_id,
    total_amount_usdt,
    total_payments_count,
    status,
    created_at,
    completed_at
FROM payout_batches
ORDER BY created_at DESC
LIMIT 20;

-- Clients approaching threshold
SELECT
    pa.client_id,
    SUM(pa.accumulated_amount_usdt) as current_total,
    mc.payout_threshold_usd as threshold,
    mc.payout_threshold_usd - SUM(pa.accumulated_amount_usdt) as remaining
FROM payout_accumulation pa
JOIN main_clients_database mc ON pa.client_id = mc.open_channel_id
WHERE pa.is_paid_out = FALSE
  AND mc.payout_strategy = 'threshold'
GROUP BY pa.client_id, mc.payout_threshold_usd
ORDER BY remaining ASC;
```

---

## Troubleshooting

### Issue: GCAccumulator not receiving tasks

**Check:**
1. GCWebhook1 logs for "Enqueued to GCAccumulator" message
2. Secret Manager: `GCACCUMULATOR_QUEUE` and `GCACCUMULATOR_URL`
3. Queue exists: `gcloud tasks queues describe accumulator-payment-queue --location=us-central1`

**Fix:**
```bash
# Verify queue
gcloud tasks queues list --location=us-central1 | grep accumulator

# Check GCWebhook1 env vars
gcloud run services describe gcwebhook1-10-26 --region=us-central1 --format=yaml | grep -A 20 env
```

### Issue: Batch processor not triggering

**Check:**
1. Cloud Scheduler job status
2. GCBatchProcessor service running
3. Database has clients over threshold

**Fix:**
```bash
# Check scheduler
gcloud scheduler jobs describe batch-processor-job --location=us-central1

# Manually trigger
gcloud scheduler jobs run batch-processor-job --location=us-central1

# Check logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcbatchprocessor-10-26" \
  --limit 10
```

### Issue: Accumulations not marked as paid

**Check:**
1. GCBatchProcessor logs for "Marked X accumulation(s) as paid"
2. Database constraints on `payout_accumulation` table

**Fix:**
```sql
-- Check for stuck accumulations
SELECT
    client_id,
    COUNT(*) as count,
    payout_batch_id,
    is_paid_out
FROM payout_accumulation
WHERE payout_batch_id IS NOT NULL
  AND is_paid_out = FALSE
GROUP BY client_id, payout_batch_id, is_paid_out;

-- Manually mark if needed (use with caution)
-- UPDATE payout_accumulation
-- SET is_paid_out = TRUE, paid_out_at = NOW()
-- WHERE payout_batch_id = 'YOUR_BATCH_ID';
```

---

## Rollback Plan

If deployment fails or issues arise:

1. **Rollback GCWebhook1:**
   ```bash
   gcloud run services update-traffic gcwebhook1-10-26 \
     --to-revisions=PREVIOUS_REVISION=100 \
     --region=us-central1
   ```

2. **Delete Cloud Scheduler job:**
   ```bash
   gcloud scheduler jobs delete batch-processor-job --location=us-central1
   ```

3. **Delete queues (optional):**
   ```bash
   gcloud tasks queues delete accumulator-payment-queue --location=us-central1
   gcloud tasks queues delete gcsplit1-batch-queue --location=us-central1
   ```

4. **Existing channels unaffected:** All existing channels default to `payout_strategy='instant'`

---

## Success Criteria

- [ ] All 4 services deployed and healthy
- [ ] 2 Cloud Tasks queues created
- [ ] Cloud Scheduler job running every 5 minutes
- [ ] Instant payout flow unchanged and working
- [ ] Threshold payout accumulation working
- [ ] Batch processing executing correctly
- [ ] Database tables populated correctly
- [ ] Monitoring and logs accessible

---

**Deployment Status:** Ready for Execution
**Estimated Time:** 45-60 minutes
**Risk Level:** Low (backward compatible)
