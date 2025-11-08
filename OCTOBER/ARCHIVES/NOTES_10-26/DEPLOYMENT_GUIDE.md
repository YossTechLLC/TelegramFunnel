# GCSplit Cloud Tasks Architecture - Deployment Guide
## Implementation Date: 2025-10-26

---

## 📋 **TABLE OF CONTENTS**

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Service URLs Configuration](#service-urls-configuration)
4. [Environment Variables](#environment-variables)
5. [Deployment Steps](#deployment-steps)
6. [Verification & Testing](#verification--testing)
7. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
8. [Rollback Procedure](#rollback-procedure)

---

## 🎯 **OVERVIEW**

This deployment guide covers the three-service GCSplit architecture with Cloud Tasks:

- **GCSplit1-10-26**: Orchestrator service (3 endpoints)
- **GCSplit2-10-26**: USDT→ETH estimator service (infinite retry)
- **GCSplit3-10-26**: ETH→ClientCurrency swapper service (infinite retry)

**Key Features**:
- ✅ Infinite retry logic (up to 24 hours)
- ✅ Protection against ChangeNow API rate limiting
- ✅ Resilience to API downtime
- ✅ Asynchronous processing via Cloud Tasks
- ✅ Token-based secure communication

---

## 🔧 **PREREQUISITES**

Before deployment, ensure you have:

1. **Google Cloud Project** with billing enabled
2. **APIs Enabled**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable cloudtasks.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   gcloud services enable sqladmin.googleapis.com
   ```

3. **IAM Permissions**:
   - Cloud Run Admin
   - Cloud Tasks Admin
   - Secret Manager Admin
   - Cloud SQL Client

4. **Secrets in Secret Manager**:
   - `SUCCESS_URL_SIGNING_KEY`
   - `CHANGENOW_API_KEY`
   - `TPS_HOSTPAY_SIGNING_KEY`
   - `HOSTPAY_WEBHOOK_URL`
   - `TP_FLAT_FEE`
   - `DB_PASSWORD`

5. **Cloud SQL PostgreSQL instance** with database and tables created

---

## 🌐 **SERVICE URLS CONFIGURATION**

After deploying each service, you'll receive Cloud Run URLs. These URLs must be configured as environment variables for inter-service communication:

### **Deployment Order** (to get URLs):
1. Deploy **GCSplit1** first → Get URL1
2. Deploy **GCSplit2** → Get URL2
3. Deploy **GCSplit3** → Get URL3
4. **Re-deploy GCSplit1** with all URLs configured
5. **Re-deploy GCSplit2** with GCSplit1 URL
6. **Re-deploy GCSplit3** with GCSplit1 URL

### **Example URLs**:
```
GCSplit1: https://gcsplit1-10-26-abc123.run.app
GCSplit2: https://gcsplit2-10-26-def456.run.app
GCSplit3: https://gcsplit3-10-26-ghi789.run.app
```

### **GCSplit1 Endpoint URLs**:
```
Initial webhook: https://gcsplit1-10-26-abc123.run.app/
Estimate response: https://gcsplit1-10-26-abc123.run.app/usdt-eth-estimate
Swap response: https://gcsplit1-10-26-abc123.run.app/eth-client-swap
```

---

## 🔐 **ENVIRONMENT VARIABLES**

### **GCSplit1-10-26** (Orchestrator)
```bash
# Secrets from Secret Manager
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
TPS_HOSTPAY_SIGNING_KEY=projects/291176869049/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest
HOSTPAY_WEBHOOK_URL=projects/291176869049/secrets/HOSTPAY_WEBHOOK_URL/versions/latest
TP_FLAT_FEE=projects/291176869049/secrets/TP_FLAT_FEE/versions/latest

# Database credentials (all from Secret Manager)
CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest

# Cloud Tasks configuration (all from Secret Manager)
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
GCSPLIT2_QUEUE=projects/291176869049/secrets/GCSPLIT2_QUEUE/versions/latest
GCSPLIT2_URL=projects/291176869049/secrets/GCSPLIT2_URL/versions/latest
GCSPLIT3_QUEUE=projects/291176869049/secrets/GCSPLIT3_QUEUE/versions/latest
GCSPLIT3_URL=projects/291176869049/secrets/GCSPLIT3_URL/versions/latest
HOSTPAY_QUEUE=projects/291176869049/secrets/HOSTPAY_QUEUE/versions/latest
```

### **GCSplit2-10-26** (USDT→ETH Estimator)
```bash
# Secrets from Secret Manager
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest

# Cloud Tasks configuration (all from Secret Manager)
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
GCSPLIT2_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT2_RESPONSE_QUEUE/versions/latest
GCSPLIT1_ESTIMATE_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_ESTIMATE_RESPONSE_URL/versions/latest
```

### **GCSplit3-10-26** (ETH→Client Swapper)
```bash
# Secrets from Secret Manager
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest

# Cloud Tasks configuration (all from Secret Manager)
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest
GCSPLIT3_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT3_RESPONSE_QUEUE/versions/latest
GCSPLIT1_SWAP_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_SWAP_RESPONSE_URL/versions/latest
```

---

## 🚀 **DEPLOYMENT STEPS**

### **Step 1: Deploy Cloud Tasks Queues**

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26

# Make script executable
chmod +x deploy_cloud_tasks_queues.sh

# Set environment variables
export CLOUD_TASKS_PROJECT_ID=your-project-id
export CLOUD_TASKS_LOCATION=us-central1

# Deploy queues
./deploy_cloud_tasks_queues.sh
```

**Verify queues created**:
```bash
gcloud tasks queues list --location=us-central1
```

---

### **Step 2: Initial Deployment (Get URLs)**

#### **Deploy GCSplit1** (without dependencies)
```bash
cd GCSplit1-10-26

gcloud run deploy gcsplit1-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --timeout=3600s \
  --cpu=2 \
  --memory=1Gi \
  --set-env-vars="
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,
TPS_HOSTPAY_SIGNING_KEY=projects/291176869049/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest,
HOSTPAY_WEBHOOK_URL=projects/291176869049/secrets/HOSTPAY_WEBHOOK_URL/versions/latest,
TP_FLAT_FEE=projects/291176869049/secrets/TP_FLAT_FEE/versions/latest,
CLOUD_SQL_CONNECTION_NAME=projects/291176869049/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest,
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest,
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest,
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,
GCSPLIT2_QUEUE=projects/291176869049/secrets/GCSPLIT2_QUEUE/versions/latest,
GCSPLIT2_URL=projects/291176869049/secrets/GCSPLIT2_URL/versions/latest,
GCSPLIT3_QUEUE=projects/291176869049/secrets/GCSPLIT3_QUEUE/versions/latest,
GCSPLIT3_URL=projects/291176869049/secrets/GCSPLIT3_URL/versions/latest,
HOSTPAY_QUEUE=projects/291176869049/secrets/HOSTPAY_QUEUE/versions/latest"
```

**Save the URL**: `https://gcsplit1-10-26-xxx.run.app`

#### **Deploy GCSplit2**
```bash
cd ../GCSplit2-10-26

gcloud run deploy gcsplit2-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --timeout=3600s \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars="
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest,
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,
GCSPLIT2_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT2_RESPONSE_QUEUE/versions/latest,
GCSPLIT1_ESTIMATE_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_ESTIMATE_RESPONSE_URL/versions/latest"
```

**Save the URL**: `https://gcsplit2-10-26-xxx.run.app`

#### **Deploy GCSplit3**
```bash
cd ../GCSplit3-10-26

gcloud run deploy gcsplit3-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --timeout=3600s \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars="
SUCCESS_URL_SIGNING_KEY=projects/291176869049/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest,
CHANGENOW_API_KEY=projects/291176869049/secrets/CHANGENOW_API_KEY/versions/latest,
CLOUD_TASKS_PROJECT_ID=projects/291176869049/secrets/CLOUD_TASKS_PROJECT_ID/versions/latest,
CLOUD_TASKS_LOCATION=projects/291176869049/secrets/CLOUD_TASKS_LOCATION/versions/latest,
GCSPLIT3_RESPONSE_QUEUE=projects/291176869049/secrets/GCSPLIT3_RESPONSE_QUEUE/versions/latest,
GCSPLIT1_SWAP_RESPONSE_URL=projects/291176869049/secrets/GCSPLIT1_SWAP_RESPONSE_URL/versions/latest"
```

**Save the URL**: `https://gcsplit3-10-26-xxx.run.app`

---

### **Step 3: Re-deploy GCSplit1 with Correct URLs**

```bash
cd ../GCSplit1-10-26

# Update environment variables with actual GCSplit2 and GCSplit3 URLs
gcloud run services update gcsplit1-10-26 \
  --region us-central1 \
  --update-env-vars="
GCSPLIT2_URL=https://gcsplit2-10-26-xxx.run.app,
GCSPLIT3_URL=https://gcsplit3-10-26-xxx.run.app"
```

---

### **Step 4: Update GCWebhook to Call GCSplit1**

Update your GCWebhook service to call GCSplit1 instead of the old GCSplit:

```python
# In GCWebhook10-26/tph10-26.py
# Update the TPS webhook URL

TPS_WEBHOOK_URL = "https://gcsplit1-10-26-xxx.run.app"
```

Re-deploy GCWebhook:
```bash
cd ../GCWebhook10-26
gcloud run deploy gcwebhook10-26 --source . --region us-central1
```

---

## ✅ **VERIFICATION & TESTING**

### **1. Health Checks**
```bash
# GCSplit1
curl https://gcsplit1-10-26-xxx.run.app/health

# GCSplit2
curl https://gcsplit2-10-26-xxx.run.app/health

# GCSplit3
curl https://gcsplit3-10-26-xxx.run.app/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "service": "GCSplit1-10-26 Orchestrator",
  "timestamp": 1698765432,
  "components": {
    "database": "healthy",
    "token_manager": "healthy",
    "cloudtasks": "healthy"
  }
}
```

### **2. Check Cloud Tasks Queues**
```bash
gcloud tasks queues describe gcsplit-usdt-eth-estimate-queue --location=us-central1
```

### **3. Monitor Logs**
```bash
# Real-time logs for GCSplit1
gcloud run services logs tail gcsplit1-10-26 --region=us-central1

# Real-time logs for GCSplit2
gcloud run services logs tail gcsplit2-10-26 --region=us-central1

# Real-time logs for GCSplit3
gcloud run services logs tail gcsplit3-10-26 --region=us-central1
```

### **4. End-to-End Test**

Trigger a test payment through your system and verify:
1. ✅ GCWebhook calls GCSplit1
2. ✅ GCSplit1 enqueues task to GCSplit2
3. ✅ GCSplit2 gets USDT→ETH estimate
4. ✅ GCSplit2 enqueues response to GCSplit1
5. ✅ GCSplit1 saves to split_payout_request
6. ✅ GCSplit1 enqueues task to GCSplit3
7. ✅ GCSplit3 creates ChangeNow transaction
8. ✅ GCSplit3 enqueues response to GCSplit1
9. ✅ GCSplit1 saves to split_payout_que
10. ✅ GCSplit1 triggers GCHostPay

---

## 📊 **MONITORING & TROUBLESHOOTING**

### **Cloud Tasks Metrics**
View queue depth and task execution:
```bash
gcloud tasks queues describe gcsplit-usdt-eth-estimate-queue \
  --location=us-central1 \
  --format="table(state, rateLimits)"
```

### **Common Issues**

#### **Issue 1: Tasks Not Being Enqueued**
- **Check**: Cloud Tasks client initialization in logs
- **Fix**: Verify CLOUD_TASKS_PROJECT_ID and CLOUD_TASKS_LOCATION env vars

#### **Issue 2: Token Decryption Failures**
- **Check**: SUCCESS_URL_SIGNING_KEY matches across all services
- **Fix**: Ensure same secret path in all services

#### **Issue 3: ChangeNow API Failures**
- **Expected**: Service will retry every 60 seconds for 24 hours
- **Monitor**: Check retry attempt count in logs

#### **Issue 4: Database Connection Errors**
- **Check**: Cloud SQL instance is running
- **Fix**: Verify INSTANCE_CONNECTION_NAME format and IAM permissions

---

## 🔄 **ROLLBACK PROCEDURE**

If issues occur, rollback to previous GCSplit:

### **1. Update GCWebhook**
```python
# Point back to old GCSplit
TPS_WEBHOOK_URL = "https://gcsplit10-26-xxx.run.app"
```

### **2. Re-deploy GCWebhook**
```bash
cd GCWebhook10-26
gcloud run deploy gcwebhook10-26 --source . --region=us-central1
```

### **3. Delete New Services** (Optional)
```bash
gcloud run services delete gcsplit1-10-26 --region=us-central1
gcloud run services delete gcsplit2-10-26 --region=us-central1
gcloud run services delete gcsplit3-10-26 --region=us-central1
```

### **4. Delete Cloud Tasks Queues** (Optional)
```bash
for queue in gcsplit-usdt-eth-estimate-queue gcsplit-usdt-eth-response-queue \
             gcsplit-eth-client-swap-queue gcsplit-eth-client-response-queue \
             gcsplit-hostpay-trigger-queue; do
  gcloud tasks queues delete $queue --location=us-central1 --quiet
done
```

---

## 🎉 **POST-DEPLOYMENT CHECKLIST**

- [ ] All three services deployed successfully
- [ ] All five Cloud Tasks queues created
- [ ] Health checks passing for all services
- [ ] Environment variables correctly configured
- [ ] GCWebhook updated to call GCSplit1
- [ ] End-to-end test payment completed successfully
- [ ] Monitoring dashboards configured
- [ ] Alert policies set up
- [ ] Team notified of new architecture

---

**Deployment Date**: 2025-10-26
**Architecture Version**: Cloud Tasks v1.0
**Contact**: [Your Contact Info]
