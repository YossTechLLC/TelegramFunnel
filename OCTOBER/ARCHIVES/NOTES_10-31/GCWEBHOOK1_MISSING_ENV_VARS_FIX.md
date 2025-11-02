# GCWebhook1 Missing Environment Variables Fix

## Issue Summary
GCWebhook1-10-26 logs show missing environment variables:
```
❌ [CONFIG] Environment variable GCACCUMULATOR_QUEUE is not set
❌ [CONFIG] Environment variable GCACCUMULATOR_URL is not set
```

These variables are needed for threshold payout mode to route payments to GCAccumulator.

## Root Cause
GCWebhook1 deployment is missing the `--set-secrets` flags for:
- `GCACCUMULATOR_QUEUE`
- `GCACCUMULATOR_URL`

## Checklist

### Step 1: Verify Secrets Exist in Secret Manager ✓
- [ ] Check if `GCACCUMULATOR_QUEUE` secret exists
- [ ] Check if `GCACCUMULATOR_URL` secret exists
- [ ] If missing, create them

### Step 2: Review GCWebhook1 config_manager.py ✓
- [ ] Verify config_manager loads these variables
- [ ] Check variable names are correct

### Step 3: Update GCWebhook1 Deployment ✓
- [ ] Add `GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest`
- [ ] Add `GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest`
- [ ] Redeploy service

### Step 4: Verify Fix ✓
- [ ] Check GCWebhook1 startup logs
- [ ] Verify both variables show ✅ instead of ❌
- [ ] Test threshold payout routing

## Expected Secrets in Secret Manager
Based on system architecture, these should exist:
- `GCACCUMULATOR_QUEUE` → Queue name (e.g., "gcaccumulator-payment-queue")
- `GCACCUMULATOR_URL` → Service URL (e.g., "https://gcaccumulator-10-26-291176869049.us-central1.run.app")

## Deployment Command Template
```bash
gcloud run deploy gcwebhook1-10-26 \
  --image gcr.io/telepay-459221/gcwebhook1-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --max-instances 10 \
  --add-cloudsql-instances telepay-459221:us-central1:telepaypsql \
  --set-secrets \
SUCCESS_URL_SIGNING_KEY=SUCCESS_URL_SIGNING_KEY:latest,\
CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,\
CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,\
GCWEBHOOK2_QUEUE=GCWEBHOOK2_QUEUE:latest,\
GCWEBHOOK2_URL=GCWEBHOOK2_URL:latest,\
GCSPLIT1_QUEUE=GCSPLIT1_QUEUE:latest,\
GCSPLIT1_URL=GCSPLIT1_URL:latest,\
GCACCUMULATOR_QUEUE=GCACCUMULATOR_QUEUE:latest,\
GCACCUMULATOR_URL=GCACCUMULATOR_URL:latest,\
CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,\
DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,\
DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,\
DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest
```
