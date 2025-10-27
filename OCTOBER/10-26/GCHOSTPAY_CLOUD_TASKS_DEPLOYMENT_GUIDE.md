# GCHostPay Cloud Tasks Deployment Guide

## Overview

This guide covers the deployment of the refactored GCHostPay architecture, which splits the monolithic GCHostPay10-26 service into three specialized microservices:

- **GCHostPay1-10-26**: Validator & Orchestrator
- **GCHostPay2-10-26**: ChangeNow Status Checker (infinite retry)
- **GCHostPay3-10-26**: ETH Payment Executor (infinite retry)

## Architecture

```
GCSplit1-10-26
    ↓ (Cloud Task)
GCHostPay1-10-26 (Validator & Orchestrator)
    ├─ POST / - Main webhook
    ├─ POST /status-verified - Status response from GCHostPay2
    └─ POST /payment-completed - Payment response from GCHostPay3
    │
    ├─→ GCHostPay2-10-26 (Status Checker)
    │   └─ Infinite retry: 60s backoff, 24h max
    │
    └─→ GCHostPay3-10-26 (Payment Executor)
        └─ Infinite retry: 60s backoff, 24h max
```

## Prerequisites

1. Google Cloud Project with billing enabled
2. Cloud Run API enabled
3. Cloud Tasks API enabled
4. Cloud SQL instance running PostgreSQL
5. Secret Manager secrets configured
6. Docker installed locally for building images

## Cloud Tasks Queue Configuration

### Queue Parameters

All queues use the following configuration:
- `--max-attempts=-1` (infinite retry)
- `--max-retry-duration=86400s` (24 hours)
- `--min-backoff=60s` (60 second backoff)
- `--max-backoff=60s` (fixed backoff)
- `--max-doublings=0` (no exponential backoff)
- `--max-dispatches-per-second=<TBD>` (based on vendor RPS limits)
- `--max-concurrent-dispatches=<TBD>` (based on target RPS × p95 latency × 1.5)

### Required Queues

Create the following Cloud Tasks queues:

```bash
# Queue for GCHostPay2 (Status Checker)
gcloud tasks queues create gchostpay2-status-checker \
  --location=us-central1 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0

# Queue for GCHostPay3 (Payment Executor)
gcloud tasks queues create gchostpay3-payment-executor \
  --location=us-central1 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0

# Queue for GCHostPay1 responses (from GCHostPay2 and GCHostPay3)
gcloud tasks queues create gchostpay1-response \
  --location=us-central1 \
  --max-attempts=-1 \
  --max-retry-duration=86400s \
  --min-backoff=60s \
  --max-backoff=60s \
  --max-doublings=0
```

## Secret Manager Configuration

### Required Secrets

All services require the following secrets:

#### GCHostPay1-10-26
- `TPS_HOSTPAY_SIGNING_KEY` - For GCSplit1 → GCHostPay1 communication
- `SUCCESS_URL_SIGNING_KEY` - For internal GCHostPay communication
- `CLOUD_TASKS_PROJECT_ID` - Project ID for Cloud Tasks
- `CLOUD_TASKS_LOCATION` - Region for Cloud Tasks (e.g., us-central1)
- `GCHOSTPAY2_QUEUE` - Name of GCHostPay2 queue
- `GCHOSTPAY2_URL` - URL of GCHostPay2 service
- `GCHOSTPAY3_QUEUE` - Name of GCHostPay3 queue
- `GCHOSTPAY3_URL` - URL of GCHostPay3 service
- `CLOUD_SQL_CONNECTION_NAME` - Cloud SQL connection string
- `DATABASE_NAME_SECRET` - Database name
- `DATABASE_USER_SECRET` - Database user
- `DATABASE_PASSWORD_SECRET` - Database password

#### GCHostPay2-10-26
- `SUCCESS_URL_SIGNING_KEY` - For internal GCHostPay communication
- `CHANGENOW_API_KEY` - ChangeNow API key
- `CLOUD_TASKS_PROJECT_ID` - Project ID for Cloud Tasks
- `CLOUD_TASKS_LOCATION` - Region for Cloud Tasks
- `GCHOSTPAY1_RESPONSE_QUEUE` - Name of GCHostPay1 response queue
- `GCHOSTPAY1_URL` - URL of GCHostPay1 service

#### GCHostPay3-10-26
- `SUCCESS_URL_SIGNING_KEY` - For internal GCHostPay communication
- `HOST_WALLET_ETH_ADDRESS` - Host wallet Ethereum address
- `HOST_WALLET_PRIVATE_KEY` - Host wallet private key
- `ETHEREUM_RPC_URL` - Ethereum RPC provider URL
- `ETHEREUM_RPC_URL_API` - Ethereum RPC API key (Alchemy)
- `CLOUD_TASKS_PROJECT_ID` - Project ID for Cloud Tasks
- `CLOUD_TASKS_LOCATION` - Region for Cloud Tasks
- `GCHOSTPAY1_RESPONSE_QUEUE` - Name of GCHostPay1 response queue
- `GCHOSTPAY1_URL` - URL of GCHostPay1 service
- `CLOUD_SQL_CONNECTION_NAME` - Cloud SQL connection string
- `DATABASE_NAME_SECRET` - Database name
- `DATABASE_USER_SECRET` - Database user
- `DATABASE_PASSWORD_SECRET` - Database password

### Creating Secrets

```bash
# Example: Create SUCCESS_URL_SIGNING_KEY
echo -n "your-signing-key-here" | gcloud secrets create SUCCESS_URL_SIGNING_KEY --data-file=-

# Example: Create queue names
echo -n "gchostpay2-status-checker" | gcloud secrets create GCHOSTPAY2_QUEUE --data-file=-
echo -n "gchostpay3-payment-executor" | gcloud secrets create GCHOSTPAY3_QUEUE --data-file=-
echo -n "gchostpay1-response" | gcloud secrets create GCHOSTPAY1_RESPONSE_QUEUE --data-file=-
```

## Deployment Steps

### Step 1: Build and Push Docker Images

```bash
# Set project ID
export PROJECT_ID=your-project-id

# Build GCHostPay1
cd /path/to/GCHostPay1-10-26
docker build -t gcr.io/${PROJECT_ID}/gchostpay1-10-26:latest .
docker push gcr.io/${PROJECT_ID}/gchostpay1-10-26:latest

# Build GCHostPay2
cd ../GCHostPay2-10-26
docker build -t gcr.io/${PROJECT_ID}/gchostpay2-10-26:latest .
docker push gcr.io/${PROJECT_ID}/gchostpay2-10-26:latest

# Build GCHostPay3
cd ../GCHostPay3-10-26
docker build -t gcr.io/${PROJECT_ID}/gchostpay3-10-26:latest .
docker push gcr.io/${PROJECT_ID}/gchostpay3-10-26:latest
```

### Step 2: Deploy to Cloud Run

```bash
# Deploy GCHostPay1
gcloud run deploy gchostpay1-10-26 \
  --image gcr.io/${PROJECT_ID}/gchostpay1-10-26:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 900s \
  --set-env-vars="TPS_HOSTPAY_SIGNING_KEY=projects/${PROJECT_ID}/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest,SUCCESS_URL_SIGNING_KEY=projects/${PROJECT_ID}/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,CLOUD_TASKS_PROJECT_ID=projects/${PROJECT_ID}/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,CLOUD_TASKS_LOCATION=projects/${PROJECT_ID}/secrets/CLOUD_TASKS_LOCATION/versions/latest,GCHOSTPAY2_QUEUE=projects/${PROJECT_ID}/secrets/GCHOSTPAY2_QUEUE/versions/latest,GCHOSTPAY2_URL=projects/${PROJECT_ID}/secrets/GCHOSTPAY2_URL/versions/latest,GCHOSTPAY3_QUEUE=projects/${PROJECT_ID}/secrets/GCHOSTPAY3_QUEUE/versions/latest,GCHOSTPAY3_URL=projects/${PROJECT_ID}/secrets/GCHOSTPAY3_URL/versions/latest,CLOUD_SQL_CONNECTION_NAME=projects/${PROJECT_ID}/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,DATABASE_NAME_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_NAME_SECRET/versions/latest,DATABASE_USER_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_USER_SECRET/versions/latest,DATABASE_PASSWORD_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_PASSWORD_SECRET/versions/latest"

# Deploy GCHostPay2
gcloud run deploy gchostpay2-10-26 \
  --image gcr.io/${PROJECT_ID}/gchostpay2-10-26:latest \
  --region us-central1 \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --timeout 900s \
  --set-env-vars="SUCCESS_URL_SIGNING_KEY=projects/${PROJECT_ID}/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,CHANGENOW_API_KEY=projects/${PROJECT_ID}/secrets/CHANGENOW_API_KEY/versions/latest,CLOUD_TASKS_PROJECT_ID=projects/${PROJECT_ID}/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,CLOUD_TASKS_LOCATION=projects/${PROJECT_ID}/secrets/CLOUD_TASKS_LOCATION/versions/latest,GCHOSTPAY1_RESPONSE_QUEUE=projects/${PROJECT_ID}/secrets/GCHOSTPAY1_RESPONSE_QUEUE/versions/latest,GCHOSTPAY1_URL=projects/${PROJECT_ID}/secrets/GCHOSTPAY1_URL/versions/latest"

# Deploy GCHostPay3
gcloud run deploy gchostpay3-10-26 \
  --image gcr.io/${PROJECT_ID}/gchostpay3-10-26:latest \
  --region us-central1 \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 900s \
  --set-env-vars="SUCCESS_URL_SIGNING_KEY=projects/${PROJECT_ID}/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,HOST_WALLET_ETH_ADDRESS=projects/${PROJECT_ID}/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest,HOST_WALLET_PRIVATE_KEY=projects/${PROJECT_ID}/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest,ETHEREUM_RPC_URL=projects/${PROJECT_ID}/secrets/ETHEREUM_RPC_URL/versions/latest,ETHEREUM_RPC_URL_API=projects/${PROJECT_ID}/secrets/ETHEREUM_RPC_URL_API/versions/latest,CLOUD_TASKS_PROJECT_ID=projects/${PROJECT_ID}/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,CLOUD_TASKS_LOCATION=projects/${PROJECT_ID}/secrets/CLOUD_TASKS_LOCATION/versions/latest,GCHOSTPAY1_RESPONSE_QUEUE=projects/${PROJECT_ID}/secrets/GCHOSTPAY1_RESPONSE_QUEUE/versions/latest,GCHOSTPAY1_URL=projects/${PROJECT_ID}/secrets/GCHOSTPAY1_URL/versions/latest,CLOUD_SQL_CONNECTION_NAME=projects/${PROJECT_ID}/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,DATABASE_NAME_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_NAME_SECRET/versions/latest,DATABASE_USER_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_USER_SECRET/versions/latest,DATABASE_PASSWORD_SECRET=projects/${PROJECT_ID}/secrets/DATABASE_PASSWORD_SECRET/versions/latest"
```

### Step 3: Update Service URLs in Secret Manager

After deployment, update the service URL secrets:

```bash
# Get the deployed URLs
gcloud run services describe gchostpay1-10-26 --region us-central1 --format='value(status.url)'
gcloud run services describe gchostpay2-10-26 --region us-central1 --format='value(status.url)'
gcloud run services describe gchostpay3-10-26 --region us-central1 --format='value(status.url)'

# Update secrets
gcloud secrets versions add GCHOSTPAY1_URL --data-file=- <<< "https://gchostpay1-10-26-xxx.run.app"
gcloud secrets versions add GCHOSTPAY2_URL --data-file=- <<< "https://gchostpay2-10-26-xxx.run.app"
gcloud secrets versions add GCHOSTPAY3_URL --data-file=- <<< "https://gchostpay3-10-26-xxx.run.app"
```

### Step 4: Configure IAM Permissions

```bash
# Allow Cloud Tasks to invoke GCHostPay services
gcloud run services add-iam-policy-binding gchostpay1-10-26 \
  --region us-central1 \
  --member=serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-cloudtasks.iam.gserviceaccount.com \
  --role=roles/run.invoker

gcloud run services add-iam-policy-binding gchostpay2-10-26 \
  --region us-central1 \
  --member=serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-cloudtasks.iam.gserviceaccount.com \
  --role=roles/run.invoker

gcloud run services add-iam-policy-binding gchostpay3-10-26 \
  --region us-central1 \
  --member=serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-cloudtasks.iam.gserviceaccount.com \
  --role=roles/run.invoker
```

## Testing

### Health Checks

```bash
# Test GCHostPay1 health
curl https://gchostpay1-10-26-xxx.run.app/health

# Test GCHostPay2 health
curl https://gchostpay2-10-26-xxx.run.app/health

# Test GCHostPay3 health
curl https://gchostpay3-10-26-xxx.run.app/health
```

### End-to-End Test

Trigger a test payment from GCSplit1 and monitor logs:

```bash
# Monitor GCHostPay1 logs
gcloud run services logs read gchostpay1-10-26 --region us-central1 --limit 50

# Monitor GCHostPay2 logs
gcloud run services logs read gchostpay2-10-26 --region us-central1 --limit 50

# Monitor GCHostPay3 logs
gcloud run services logs read gchostpay3-10-26 --region us-central1 --limit 50

# Monitor Cloud Tasks queues
gcloud tasks queues describe gchostpay2-status-checker --location us-central1
gcloud tasks queues describe gchostpay3-payment-executor --location us-central1
gcloud tasks queues describe gchostpay1-response --location us-central1
```

## Monitoring and Observability

### Key Metrics to Monitor

1. **Cloud Tasks Metrics**
   - Queue depth
   - Task execution time
   - Retry counts
   - Success/failure rates

2. **Cloud Run Metrics**
   - Request latency (p50, p95, p99)
   - Error rates
   - Instance count
   - CPU/memory utilization

3. **Custom Application Metrics**
   - Token encryption/decryption success rates
   - ChangeNow API response times
   - ETH payment success rates
   - Database operation latencies

### Logging

All services use structured logging with emoji prefixes:
- 🚀 - Service initialization
- 🎯 - Endpoint invocation
- ✅ - Success
- ❌ - Error
- ⚠️ - Warning
- 🔐 - Encryption/decryption
- 🔄 - Retry attempts
- 💰 - Payment operations
- 🔗 - Transaction hashes

## Troubleshooting

### Common Issues

1. **Token validation failures**
   - Check that signing keys match across services
   - Verify token is not expired (60-second window)

2. **Cloud Tasks not executing**
   - Verify IAM permissions
   - Check queue configuration
   - Ensure service URLs are correct in secrets

3. **ChangeNow API failures**
   - Monitor rate limiting (HTTP 429)
   - Check API key validity
   - Verify infinite retry is working

4. **ETH payment failures**
   - Check wallet balance
   - Verify RPC endpoint connectivity
   - Monitor gas prices
   - Check nonce issues

## Rollback Procedure

If issues arise, rollback to GCHostPay10-26:

```bash
# Update GCSplit1 to point back to GCHostPay10-26
gcloud secrets versions add HOSTPAY_WEBHOOK_URL --data-file=- <<< "https://gchostpay10-26-xxx.run.app"

# Disable new services (optional)
gcloud run services update gchostpay1-10-26 --region us-central1 --no-traffic
gcloud run services update gchostpay2-10-26 --region us-central1 --no-traffic
gcloud run services update gchostpay3-10-26 --region us-central1 --no-traffic
```

## Benefits of New Architecture

1. **Infinite Retry Resilience**: Protects against transient API/RPC failures
2. **Independent Scaling**: Each service scales based on its specific load
3. **Separation of Concerns**: Easier debugging and maintenance
4. **Rate Limit Protection**: 60-second backoff prevents API bans
5. **Fault Isolation**: Failures in one component don't affect others

## IMPORTANT NOTE: Token Format Issue

⚠️ **CRITICAL**: There is a design issue in GCHostPay1's `/status-verified` endpoint.

**Problem**: When GCHostPay2 returns the status, GCHostPay1 needs to create a payment execution request to GCHostPay3. However, the current token from GCHostPay2 only contains `unique_id`, `cn_api_id`, and `status`. It's missing the payment details (`from_currency`, `from_network`, `from_amount`, `payin_address`).

**Solution**: Update `encrypt_gchostpay1_to_gchostpay2_token` and `encrypt_gchostpay2_to_gchostpay1_token` to include ALL payment details, not just unique_id and cn_api_id. This ensures GCHostPay1 has all necessary information to create the GCHostPay3 payment request.

**Status**: This fix must be applied before production deployment.
