# PayGatePrime v1 Deployment Scripts

**⚠️ DO NOT EXECUTE THESE SCRIPTS AUTOMATICALLY**

These scripts are designed to help you deploy PayGatePrime v1 to the `pgp-live` GCP project. Review and customize each script before running.

---

## 📋 Deployment Sequence

Execute these scripts **in order**:

### 1️⃣ **01_enable_apis.sh**
**Purpose:** Enable all required GCP APIs

**APIs Enabled:**
- Cloud Run
- Cloud SQL
- Secret Manager
- Cloud Tasks
- Cloud Scheduler
- Cloud Build
- Artifact Registry
- And more...

**Run:**
```bash
chmod +x 01_enable_apis.sh
./01_enable_apis.sh
```

---

### 2️⃣ **02_create_cloudsql.sh**
**Purpose:** Create Cloud SQL PostgreSQL instance

**Creates:**
- Instance: `pgp-live-psql`
- Database: `pgpdb`
- Region: `us-central1`
- Tier: `db-custom-2-7680` (2 vCPUs, 7.5 GB RAM)

**Connection String:** `pgp-live:us-central1:pgp-live-psql`

**⚠️ IMPORTANT:** You must set the postgres password manually:
```bash
gcloud sql users set-password postgres \
  --instance=pgp-live-psql \
  --password=YOUR_SECURE_PASSWORD
```

**Run:**
```bash
chmod +x 02_create_cloudsql.sh
./02_create_cloudsql.sh
```

---

### 3️⃣ **03_create_secrets.sh**
**Purpose:** Create core secrets in Secret Manager

**⚠️ CRITICAL:** This script contains placeholders! You MUST:
1. Generate new JWT keys (DO NOT reuse from telepay-459221)
2. Replace all `<placeholder>` values with actual secrets
3. Manually create sensitive secrets (API keys, wallet addresses)

**Secrets Created Automatically:**
- ✅ CLOUD_SQL_CONNECTION_NAME
- ✅ DATABASE_NAME_SECRET
- ✅ DATABASE_USER_SECRET
- ✅ BASE_URL
- ✅ CORS_ORIGIN
- ✅ FROM_EMAIL
- ✅ FROM_NAME
- ✅ TP_PERCENTAGE
- ✅ TP_FLAT_FEE
- ✅ CLOUD_TASKS_PROJECT_ID
- ✅ CLOUD_TASKS_LOCATION

**Secrets You MUST Create Manually:**
- ⚠️ JWT_SECRET_KEY (new 256-bit key)
- ⚠️ SIGNUP_SECRET_KEY (new 256-bit key)
- ⚠️ DATABASE_PASSWORD_SECRET
- ⚠️ SENDGRID_API_KEY
- ⚠️ CHANGENOW_API_KEY
- ⚠️ CHANGENOW_USDT_WALLET
- ⚠️ NOWPAYMENTS_API_KEY
- ⚠️ NOWPAYMENTS_IPN_SECRET
- ⚠️ NOWPAYMENTS_USDT_WALLET
- ⚠️ PLATFORM_USDT_WALLET_ADDRESS
- ⚠️ ALCHEMY_API_KEY_POLYGON
- ⚠️ TELEGRAM_BOT_TOKEN

**Generate Keys:**
```bash
# Generate JWT_SECRET_KEY
openssl rand -base64 32

# Generate SIGNUP_SECRET_KEY
openssl rand -base64 32
```

**Create Manually:**
```bash
echo -n 'YOUR_JWT_KEY' | gcloud secrets create JWT_SECRET_KEY --data-file=-
echo -n 'YOUR_SIGNUP_KEY' | gcloud secrets create SIGNUP_SECRET_KEY --data-file=-
# ... etc
```

**Run:**
```bash
chmod +x 03_create_secrets.sh
# REVIEW AND EDIT FIRST!
./03_create_secrets.sh
```

---

### 4️⃣ **04_create_queue_secrets.sh**
**Purpose:** Create Cloud Tasks queue name secrets

**Creates:**
- GCWEBHOOK1_QUEUE
- GCWEBHOOK2_QUEUE
- GCSPLIT1_QUEUE, GCSPLIT2_QUEUE, GCSPLIT3_QUEUE
- GCACCUMULATOR_QUEUE, GCACCUMULATOR_RESPONSE_QUEUE
- GCBATCHPROCESSOR_QUEUE
- GCHOSTPAY1_QUEUE, GCHOSTPAY2_QUEUE, GCHOSTPAY3_QUEUE
- GCHOSTPAY1_RESPONSE_QUEUE, GCHOSTPAY1_THRESHOLD_QUEUE
- GCHOSTPAY3_RETRY_QUEUE
- GCSPLIT1_BATCH_QUEUE, GCSPLIT2_RESPONSE_QUEUE

**Run:**
```bash
chmod +x 04_create_queue_secrets.sh
./04_create_queue_secrets.sh
```

---

### 5️⃣ **Deploy Cloud Run Services**
**Purpose:** Deploy all 14 services to Cloud Run

**⚠️ Manual Deployment Required**

For each service directory:
```bash
# Example: Deploy GCRegisterAPI
cd GCRegisterAPI-PGP
gcloud run deploy pgp-server-v1 \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-secrets=JWT_SECRET_KEY=JWT_SECRET_KEY:latest,... \
  --add-cloudsql-instances=pgp-live:us-central1:pgp-live-psql \
  --memory=512Mi \
  --cpu=1
```

**Services to Deploy:**
1. pgp-server-v1
2. gcregisterweb-pgp (static site or Cloud Storage + CDN)
3. pgp-webhook1-v1
4. pgp-webhook2-v1
5. pgp-split1-v1
6. pgp-split2-v1
7. pgp-split3-v1
8. pgp-hostpay1-v1
9. pgp-hostpay2-v1
10. pgp-hostpay3-v1
11. pgp-accumulator-v1
12. pgp-batchprocessor-v1
13. pgp-microbatchprocessor-v1
14. pgp-bot-v1

---

### 6️⃣ **05_create_service_url_secrets.sh**
**Purpose:** Fetch deployed service URLs and create URL secrets

**⚠️ Run AFTER deploying all Cloud Run services**

This script automatically:
1. Fetches service URLs from Cloud Run
2. Creates/updates URL secrets in Secret Manager

**Creates:**
- GCWEBHOOK1_URL
- GCWEBHOOK2_URL
- GCSPLIT1_URL, GCSPLIT2_URL, GCSPLIT3_URL
- GCACCUMULATOR_URL
- GCHOSTPAY1_URL, GCHOSTPAY2_URL, GCHOSTPAY3_URL

**Run:**
```bash
chmod +x 05_create_service_url_secrets.sh
./05_create_service_url_secrets.sh
```

---

### 7️⃣ **Create Cloud Tasks Queues**
**Purpose:** Create task queues for service-to-service communication

**Use existing deployment scripts:**
```bash
cd TOOLS_SCRIPTS_TESTS/scripts/

# Deploy webhook queues
./deploy_gcwebhook_tasks_queues.sh

# Deploy split queues
./deploy_gcsplit_tasks_queues.sh

# Deploy hostpay queues
./deploy_hostpay_tasks_queues.sh

# Deploy accumulator queues
./deploy_accumulator_tasks_queues.sh
```

---

### 8️⃣ **Run Database Migrations**
**Purpose:** Set up database schema

**Run migration scripts:**
```bash
cd TOOLS_SCRIPTS_TESTS/tools/

# Run main migrations
python3 execute_migrations.py

# Run specific migrations as needed
python3 execute_failed_transactions_migration.py
python3 execute_processed_payments_migration.py
# ... etc
```

---

### 9️⃣ **Configure External Webhooks**
**Purpose:** Update third-party webhook URLs

**NowPayments:**
1. Log into NowPayments dashboard
2. Update IPN callback URL to: `https://pgp-webhook1-v1-XXXXX.us-central1.run.app/webhook`

**ChangeNOW:**
1. Log into ChangeNOW account
2. Update webhook URL if applicable

---

### 🔟 **Testing & Verification**
**Purpose:** Verify deployment

**Test Checklist:**
- [ ] Cloud SQL instance accessible
- [ ] All secrets accessible by services
- [ ] Cloud Run services responding
- [ ] Database schema created
- [ ] Cloud Tasks queues created
- [ ] API endpoints working
- [ ] Payment flow working
- [ ] Webhooks receiving callbacks
- [ ] Email service working
- [ ] Logs showing no errors

---

## 🔐 Security Reminders

1. **Rotate Keys:** Generate NEW JWT_SECRET_KEY and SIGNUP_SECRET_KEY
2. **Never Commit Secrets:** Do not commit actual secret values to git
3. **Use Strong Passwords:** Database password should be complex
4. **Review IAM:** Ensure proper service account permissions
5. **Enable Audit Logs:** Monitor all Secret Manager access

---

## 📚 Additional Resources

- **MIGRATION_SUMMARY.md** - Complete migration overview
- **SECRET_CONFIG_UPDATE.md** - All 46 secrets detailed
- **MIGRATION_CHECKLIST.md** - Detailed checklist
- **DISCOVERY_REPORT.md** - Analysis findings

---

## ⚠️ Important Notes

### Cloud SQL Connection Name
**Updated:** `pgp-live:us-central1:pgp-live-psql`
- Old: `telepay-459221:us-central1:telepaypsql`
- Database: `pgpdb` (vs `telepaydb`)

### Service Naming
- Removed `-10-26` suffix
- Added `-pgp` suffix
- Example: `pgp-server-v1`

### Domain
- Current: `www.paygateprime.com`
- Verify if this stays or changes for PGP v1

---

## 🆘 Troubleshooting

**Cloud SQL Connection Fails:**
- Verify service account has Cloud SQL Client role
- Check connection name is correct
- Ensure Cloud SQL API is enabled

**Secrets Not Accessible:**
- Grant Secret Manager Secret Accessor role to service accounts
- Verify secrets exist in Secret Manager
- Check secret names match exactly

**Cloud Run Deploy Fails:**
- Check Dockerfile builds locally
- Verify all required secrets exist
- Check Cloud Build logs for errors

---

**Status:** Scripts ready for deployment
**Project:** pgp-live
**Instance:** pgp-live-psql
**Database:** pgpdb
