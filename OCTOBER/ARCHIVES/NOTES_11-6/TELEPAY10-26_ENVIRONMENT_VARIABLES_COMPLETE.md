# TelePay10-26 Architecture - Complete Environment Variables Reference

This document outlines **ALL** environment variables required to successfully run the updated TelePay10-26 architecture.

---

## 📋 Table of Contents

1. [Core Database Configuration](#1-core-database-configuration)
2. [Token Signing Keys](#2-token-signing-keys)
3. [External API Keys](#3-external-api-keys)
4. [Cloud Tasks Configuration](#4-cloud-tasks-configuration)
5. [Service URLs (Cloud Run Endpoints)](#5-service-urls-cloud-run-endpoints)
6. [Queue Names (Cloud Tasks Queues)](#6-queue-names-cloud-tasks-queues)
7. [Wallet Addresses](#7-wallet-addresses)
8. [Ethereum Blockchain Configuration](#8-ethereum-blockchain-configuration)
9. [NowPayments IPN Configuration](#9-nowpayments-ipn-configuration)
10. [Telegram Bot Configuration](#10-telegram-bot-configuration)
11. [Fee & Threshold Configuration](#11-fee--threshold-configuration)
12. [Optional: Alerting Configuration](#12-optional-alerting-configuration)
13. [Optional: CORS Configuration](#13-optional-cors-configuration)
14. [Service-Specific Requirements Matrix](#14-service-specific-requirements-matrix)

---

## 1. Core Database Configuration

**Required by:** ALL services (except GCHostPay2, GCRegisterWeb)

All services connect to the same Cloud SQL PostgreSQL database.

| Variable | Secret Name | Description | Example Value |
|----------|-------------|-------------|---------------|
| `CLOUD_SQL_CONNECTION_NAME` | `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL instance connection string | `telepay-459221:us-central1:telepaypsql` |
| `DATABASE_NAME_SECRET` | `DATABASE_NAME_SECRET` | PostgreSQL database name | `telepaydb` |
| `DATABASE_USER_SECRET` | `DATABASE_USER_SECRET` | PostgreSQL username | `postgres` |
| `DATABASE_PASSWORD_SECRET` | `DATABASE_PASSWORD_SECRET` | PostgreSQL password | `YourSecurePassword123$` |

---

## 2. Token Signing Keys

**Required by:** ALL microservices (except GCRegisterWeb, GCHostPay2)

Used for HMAC-based token encryption between services.

| Variable | Secret Name | Description | Used By |
|----------|-------------|-------------|---------|
| `SUCCESS_URL_SIGNING_KEY` | `SUCCESS_URL_SIGNING_KEY` | Primary signing key for all inter-service tokens | GCWebhook1, GCWebhook2, GCSplit1-3, GCAccumulator, GCHostPay1-3, GCBatchProcessor, GCMicroBatchProcessor |
| `TPS_HOSTPAY_SIGNING_KEY` | `TPS_HOSTPAY_SIGNING_KEY` | Secondary signing key for TPS→HostPay communication | GCSplit1, GCBatchProcessor |

---

## 3. External API Keys

**Required by:** Services interacting with external providers

| Variable | Secret Name | Description | Used By |
|----------|-------------|-------------|---------|
| `CHANGENOW_API_KEY` | `CHANGENOW_API_KEY` | ChangeNow API key for cryptocurrency swaps | GCSplit2, GCSplit3, GCHostPay2, GCMicroBatchProcessor |
| `NOWPAYMENTS_IPN_SECRET` | `NOWPAYMENTS_IPN_SECRET` | NowPayments IPN signature verification secret | np-webhook-10-26 |
| `PAYMENT_PROVIDER_SECRET_NAME` | Path to NowPayments API key in Secret Manager | NowPayments API token for invoice creation | TelePay10-26 bot |
| `TELEGRAM_BOT_SECRET_NAME` | Path to Telegram bot token in Secret Manager | Telegram Bot API token | TelePay10-26 bot, GCWebhook2-10-26 |
| `TELEGRAM_BOT_USERNAME` | Path to bot username in Secret Manager | Telegram bot username (for mentions) | TelePay10-26 bot |

---

## 4. Cloud Tasks Configuration

**Required by:** ALL microservices that enqueue tasks

| Variable | Secret Name | Description | Example Value |
|----------|-------------|-------------|---------------|
| `CLOUD_TASKS_PROJECT_ID` | `CLOUD_TASKS_PROJECT_ID` | Google Cloud project ID | `telepay-459221` |
| `CLOUD_TASKS_LOCATION` | `CLOUD_TASKS_LOCATION` | Cloud Tasks region | `us-central1` |

---

## 5. Service URLs (Cloud Run Endpoints)

**Required by:** Services that enqueue tasks to other services

All URLs should be in format: `https://SERVICE_NAME-HASH.REGION.run.app`

| Variable | Secret Name | Description | Example Value | Used By |
|----------|-------------|-------------|---------------|---------|
| `GCWEBHOOK1_URL` | `GCWEBHOOK1_URL` | GCWebhook1 service endpoint | `https://gcwebhook1-10-26-xxx.us-central1.run.app` | np-webhook-10-26 |
| `GCWEBHOOK2_URL` | `GCWEBHOOK2_URL` | GCWebhook2 (Telegram invite) endpoint | `https://gcwebhook2-10-26-xxx.us-central1.run.app` | GCWebhook1 |
| `GCSPLIT1_URL` | `GCSPLIT1_URL` | GCSplit1 orchestrator endpoint | `https://gcsplit1-10-26-xxx.us-central1.run.app` | GCWebhook1, GCBatchProcessor |
| `GCSPLIT2_URL` | `GCSPLIT2_URL` | GCSplit2 estimator endpoint | `https://gcsplit2-10-26-xxx.us-central1.run.app` | GCSplit1, GCAccumulator |
| `GCSPLIT3_URL` | `GCSPLIT3_URL` | GCSplit3 swap creator endpoint | `https://gcsplit3-10-26-xxx.us-central1.run.app` | GCSplit1, GCAccumulator |
| `GCACCUMULATOR_URL` | `GCACCUMULATOR_URL` | GCAccumulator endpoint | `https://gcaccumulator-10-26-xxx.us-central1.run.app` | GCWebhook1, GCHostPay3 |
| `GCHOSTPAY1_URL` | `GCHOSTPAY1_URL` | GCHostPay1 validator endpoint | `https://gchostpay1-10-26-xxx.us-central1.run.app` | GCSplit1, GCAccumulator, GCHostPay2, GCHostPay3, GCMicroBatchProcessor |
| `GCHOSTPAY2_URL` | `GCHOSTPAY2_URL` | GCHostPay2 status checker endpoint | `https://gchostpay2-10-26-xxx.us-central1.run.app` | GCHostPay1 |
| `GCHOSTPAY3_URL` | `GCHOSTPAY3_URL` | GCHostPay3 executor endpoint | `https://gchostpay3-10-26-xxx.us-central1.run.app` | GCHostPay1, GCHostPay3 (self-retry) |
| `HOSTPAY_WEBHOOK_URL` | `HOSTPAY_WEBHOOK_URL` | Legacy HostPay webhook URL | (May be deprecated) | GCSplit1 |

---

## 6. Queue Names (Cloud Tasks Queues)

**Required by:** Services that enqueue tasks

All queue names should be unique identifiers (e.g., `gcwebhook1-queue-10-26`)

| Variable | Secret Name | Description | Used By |
|----------|-------------|-------------|---------|
| `GCWEBHOOK1_QUEUE` | `GCWEBHOOK1_QUEUE` | Queue for GCWebhook1 payment processing | np-webhook-10-26 |
| `GCWEBHOOK2_QUEUE` | `GCWEBHOOK2_QUEUE` | Queue for Telegram invite delivery | GCWebhook1 |
| `GCSPLIT1_QUEUE` | `GCSPLIT1_QUEUE` | Queue for GCSplit1 instant payouts | GCWebhook1 |
| `GCSPLIT1_BATCH_QUEUE` | `GCSPLIT1_BATCH_QUEUE` | Queue for GCSplit1 batch payouts | GCBatchProcessor |
| `GCSPLIT2_QUEUE` | `GCSPLIT2_QUEUE` | Queue for GCSplit2 estimates | GCSplit1, GCAccumulator |
| `GCSPLIT3_QUEUE` | `GCSPLIT3_QUEUE` | Queue for GCSplit3 swaps | GCSplit1, GCAccumulator |
| `GCACCUMULATOR_QUEUE` | `GCACCUMULATOR_QUEUE` | Queue for payment accumulation | GCWebhook1 |
| `GCACCUMULATOR_RESPONSE_QUEUE` | `GCACCUMULATOR_RESPONSE_QUEUE` | Queue for accumulator responses | GCHostPay3 |
| `GCHOSTPAY1_QUEUE` | `GCHOSTPAY1_QUEUE` | Queue for GCHostPay1 validation | GCSplit1, GCAccumulator |
| `GCHOSTPAY1_BATCH_QUEUE` | `GCHOSTPAY1_BATCH_QUEUE` | Queue for batch conversions | GCMicroBatchProcessor |
| `GCHOSTPAY1_RESPONSE_QUEUE` | `GCHOSTPAY1_RESPONSE_QUEUE` | Queue for instant payout responses | GCHostPay2, GCHostPay3 |
| `GCHOSTPAY2_QUEUE` | `GCHOSTPAY2_QUEUE` | Queue for ChangeNow status checks | GCHostPay1 |
| `GCHOSTPAY3_QUEUE` | `GCHOSTPAY3_QUEUE` | Queue for ETH payment execution | GCHostPay1 |
| `GCHOSTPAY3_RETRY_QUEUE` | `GCHOSTPAY3_RETRY_QUEUE` | Queue for GCHostPay3 self-retry | GCHostPay3 |
| `HOSTPAY_QUEUE` | `HOSTPAY_QUEUE` | Legacy HostPay trigger queue | GCSplit1 |

---

## 7. Wallet Addresses

**Required by:** Services handling cryptocurrency

| Variable | Secret Name | Description | Used By |
|----------|-------------|-------------|---------|
| `HOST_WALLET_ETH_ADDRESS` | `HOST_WALLET_ETH_ADDRESS` | Platform's Ethereum wallet address | GCHostPay3 |
| `HOST_WALLET_PRIVATE_KEY` | `HOST_WALLET_PRIVATE_KEY` | Platform's Ethereum private key (CRITICAL) | GCHostPay3 |
| `HOST_WALLET_USDT_ADDRESS` | `HOST_WALLET_USDT_ADDRESS` | Platform's USDT wallet address (ERC-20) | GCAccumulator, GCMicroBatchProcessor |

---

## 8. Ethereum Blockchain Configuration

**Required by:** GCHostPay3-10-26

| Variable | Secret Name | Description | Example Value |
|----------|-------------|-------------|---------------|
| `ETHEREUM_RPC_URL` | `ETHEREUM_RPC_URL` | Ethereum RPC endpoint (Alchemy/Infura) | `https://eth-mainnet.g.alchemy.com/v2/` |
| `ETHEREUM_RPC_URL_API` | `ETHEREUM_RPC_URL_API` | Alchemy/Infura API key | `YOUR_ALCHEMY_API_KEY` |

**Full RPC URL:** Concatenate `ETHEREUM_RPC_URL` + `ETHEREUM_RPC_URL_API`

---

## 9. NowPayments IPN Configuration

**Required by:** TelePay10-26 bot, np-webhook-10-26

| Variable | Secret Name | Description | Example Value |
|----------|-------------|-------------|---------------|
| `NOWPAYMENTS_IPN_CALLBACK_URL` | Path to IPN callback URL in Secret Manager | URL for NowPayments IPN callbacks | `https://np-webhook-10-26-xxx.us-central1.run.app/` |
| `NOWPAYMENT_WEBHOOK_KEY` | Path to webhook key in Secret Manager | NowPayments IPN webhook key (legacy, TelePay bot) | (Legacy - may be deprecated) |

---

## 10. Telegram Bot Configuration

**Required by:** TelePay10-26 bot, GCWebhook2-10-26

| Variable | Secret Name | Description | Used By |
|----------|-------------|-------------|---------|
| `TELEGRAM_BOT_SECRET_NAME` | Path to bot token in Secret Manager | Full Telegram Bot API token | TelePay10-26, GCWebhook2 |
| `TELEGRAM_BOT_USERNAME` | Path to bot username in Secret Manager | Bot username (e.g., `@YourBot`) | TelePay10-26 |
| `TELEGRAM_BOT_WEBHOOK_URL` | (Direct env variable) | Webhook URL for Telegram bot | TelePay10-26 |

---

## 11. Fee & Threshold Configuration

**Required by:** Payment processing services

| Variable | Secret Name | Description | Default | Used By |
|----------|-------------|-------------|---------|---------|
| `TP_FLAT_FEE` | `TP_FLAT_FEE` | TelePay platform fee percentage | `3` (3%) | GCSplit1, GCAccumulator |
| `MICRO_BATCH_THRESHOLD_USD` | `MICRO_BATCH_THRESHOLD_USD` | Minimum USD for micro-batch conversion | `20.00` | GCMicroBatchProcessor |

**Note:** GCBatchProcessor fetches client-specific thresholds from database (`payout_threshold` column in `main_clients_database`)

---

## 12. Optional: Alerting Configuration

**Required by:** GCHostPay3-10-26 (for error alerts)

| Variable | Secret Name | Description | Default |
|----------|-------------|-------------|---------|
| `ALERTING_ENABLED` | `ALERTING_ENABLED` | Enable/disable alerting | `false` |
| `SLACK_ALERT_WEBHOOK` | `SLACK_ALERT_WEBHOOK` | Slack webhook URL for error alerts | None |

---

## 13. Optional: CORS Configuration

**Required by:** GCRegisterAPI-10-26

| Variable | Secret Name | Description | Default |
|----------|-------------|-------------|---------|
| `CORS_ORIGIN` | `CORS_ORIGIN` | Allowed CORS origin for API | `https://www.paygateprime.com` |

---

## 14. Service-Specific Requirements Matrix

### NP-Webhook-10-26 (IPN Handler)

**Required Environment Variables:**
- ✅ `NOWPAYMENTS_IPN_SECRET` - IPN signature verification
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCWEBHOOK1_QUEUE` - GCWebhook1 queue name
- ✅ `GCWEBHOOK1_URL` - GCWebhook1 service URL

**Total:** 9 required variables

---

### GCWebhook1-10-26 (Payment Orchestrator)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCWEBHOOK2_QUEUE` - Telegram invite queue
- ✅ `GCWEBHOOK2_URL` - Telegram invite URL
- ✅ `GCSPLIT1_QUEUE` - Instant payout queue
- ✅ `GCSPLIT1_URL` - Instant payout URL
- ✅ `GCACCUMULATOR_QUEUE` - Threshold payout queue
- ✅ `GCACCUMULATOR_URL` - Threshold payout URL

**Total:** 13 required variables

---

### GCWebhook2-10-26 (Telegram Invite Sender)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token decryption
- ✅ `TELEGRAM_BOT_SECRET_NAME` - Telegram bot token
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password

**Total:** 6 required variables

---

### GCSplit1-10-26 (Orchestrator)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `TPS_HOSTPAY_SIGNING_KEY` - HostPay token encryption
- ✅ `TP_FLAT_FEE` - Fee calculation
- ✅ `HOSTPAY_WEBHOOK_URL` - HostPay webhook
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCSPLIT2_QUEUE` - Estimator queue
- ✅ `GCSPLIT2_URL` - Estimator URL
- ✅ `GCSPLIT3_QUEUE` - Swap creator queue
- ✅ `GCSPLIT3_URL` - Swap creator URL
- ✅ `HOSTPAY_QUEUE` - HostPay queue

**Total:** 15 required variables

---

### GCSplit2-10-26 (Estimator)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `CHANGENOW_API_KEY` - ChangeNow API access
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCSPLIT1_QUEUE` - Response queue
- ✅ `GCSPLIT1_URL` - Response URL

**Total:** 6 required variables

---

### GCSplit3-10-26 (Swap Creator)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `CHANGENOW_API_KEY` - ChangeNow API access
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCSPLIT1_QUEUE` - Response queue (instant)
- ✅ `GCSPLIT1_URL` - Response URL (instant)
- ✅ `GCACCUMULATOR_QUEUE` - Response queue (threshold)
- ✅ `GCACCUMULATOR_URL` - Response URL (threshold)

**Total:** 8 required variables

---

### GCAccumulator-10-26 (Payment Accumulator)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `TP_FLAT_FEE` - Fee calculation
- ✅ `HOST_WALLET_USDT_ADDRESS` - Platform USDT wallet
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCSPLIT2_QUEUE` - Estimator queue
- ✅ `GCSPLIT2_URL` - Estimator URL
- ✅ `GCSPLIT3_QUEUE` - Swap creator queue
- ✅ `GCSPLIT3_URL` - Swap creator URL
- ✅ `GCHOSTPAY1_QUEUE` - Validator queue
- ✅ `GCHOSTPAY1_URL` - Validator URL

**Total:** 15 required variables

---

### GCHostPay1-10-26 (Validator & Orchestrator)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token decryption
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCHOSTPAY2_QUEUE` - Status checker queue
- ✅ `GCHOSTPAY2_URL` - Status checker URL
- ✅ `GCHOSTPAY3_QUEUE` - Executor queue
- ✅ `GCHOSTPAY3_URL` - Executor URL

**Total:** 11 required variables

---

### GCHostPay2-10-26 (Status Checker)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `CHANGENOW_API_KEY` - ChangeNow API access
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCHOSTPAY1_RESPONSE_QUEUE` - Response queue
- ✅ `GCHOSTPAY1_URL` - Response URL

**Total:** 6 required variables

---

### GCHostPay3-10-26 (ETH Executor)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `HOST_WALLET_ETH_ADDRESS` - Platform ETH wallet
- ✅ `HOST_WALLET_PRIVATE_KEY` - Platform private key
- ✅ `ETHEREUM_RPC_URL` - Ethereum RPC endpoint
- ✅ `ETHEREUM_RPC_URL_API` - Alchemy API key
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCHOSTPAY1_RESPONSE_QUEUE` - Instant response queue
- ✅ `GCHOSTPAY1_URL` - Instant response URL
- ✅ `GCACCUMULATOR_RESPONSE_QUEUE` - Threshold response queue
- ✅ `GCACCUMULATOR_URL` - Threshold response URL
- ✅ `GCHOSTPAY3_RETRY_QUEUE` - Self-retry queue
- ✅ `GCHOSTPAY3_URL` - Self-retry URL
- ⚠️ `ALERTING_ENABLED` - (Optional) Enable alerts
- ⚠️ `SLACK_ALERT_WEBHOOK` - (Optional) Slack webhook

**Total:** 17 required + 2 optional variables

---

### GCBatchProcessor-10-26 (Threshold Payout Processor)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `TPS_HOSTPAY_SIGNING_KEY` - Batch token encryption
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCSPLIT1_BATCH_QUEUE` - Batch payout queue
- ✅ `GCSPLIT1_URL` - Batch payout URL

**Total:** 10 required variables

---

### GCMicroBatchProcessor-10-26 (Micro-Batch Converter)

**Required Environment Variables:**
- ✅ `SUCCESS_URL_SIGNING_KEY` - Token encryption
- ✅ `CHANGENOW_API_KEY` - ChangeNow API access
- ✅ `HOST_WALLET_USDT_ADDRESS` - Platform USDT wallet
- ✅ `MICRO_BATCH_THRESHOLD_USD` - Batch threshold
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ✅ `CLOUD_TASKS_PROJECT_ID` - Cloud Tasks config
- ✅ `CLOUD_TASKS_LOCATION` - Cloud Tasks region
- ✅ `GCHOSTPAY1_BATCH_QUEUE` - Batch execution queue
- ✅ `GCHOSTPAY1_URL` - Batch execution URL

**Total:** 12 required variables

---

### TelePay10-26 (Telegram Bot)

**Required Environment Variables:**
- ✅ `TELEGRAM_BOT_SECRET_NAME` - Bot token (Secret Manager path)
- ✅ `TELEGRAM_BOT_USERNAME` - Bot username (Secret Manager path)
- ✅ `TELEGRAM_BOT_WEBHOOK_URL` - Bot webhook URL
- ✅ `PAYMENT_PROVIDER_SECRET_NAME` - NowPayments API token (Secret Manager path)
- ✅ `NOWPAYMENTS_IPN_CALLBACK_URL` - IPN callback URL (Secret Manager path)
- ⚠️ `NOWPAYMENT_WEBHOOK_KEY` - (Legacy) Webhook key

**Total:** 5 required + 1 legacy variable

---

### GCRegister10-26 (Legacy Web Form)

**Required Environment Variables:**
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password

**Total:** 4 required variables

---

### GCRegisterAPI-10-26 (REST API)

**Required Environment Variables:**
- ✅ `JWT_SECRET_KEY` - JWT token signing
- ✅ `CLOUD_SQL_CONNECTION_NAME` - Database connection
- ✅ `DATABASE_NAME_SECRET` - Database name
- ✅ `DATABASE_USER_SECRET` - Database user
- ✅ `DATABASE_PASSWORD_SECRET` - Database password
- ⚠️ `CORS_ORIGIN` - (Optional) CORS origin

**Total:** 5 required + 1 optional variable

---

### GCRegisterWeb-10-26 (React Frontend)

**Required Environment Variables:**
- ✅ `VITE_API_URL` - GCRegisterAPI endpoint

**Total:** 1 required variable (build-time)

---

## 📊 Summary Statistics

- **Total Unique Secrets in Secret Manager:** ~45-50
- **Services Requiring Database Access:** 10 services
- **Services Requiring Cloud Tasks:** 11 services
- **Services Requiring ChangeNow API:** 4 services
- **Most Complex Service (env vars):** GCHostPay3-10-26 (19 total)
- **Simplest Service (env vars):** GCRegisterWeb-10-26 (1 variable)

---

## 🚀 Deployment Checklist

Before deploying any service, ensure:

1. ✅ All required secrets exist in Google Cloud Secret Manager
2. ✅ Cloud Run service has `--set-secrets` flag mapping env vars to secrets
3. ✅ Service account has `secretmanager.secretAccessor` role
4. ✅ Cloud SQL connection name matches actual instance
5. ✅ All service URLs point to deployed Cloud Run services
6. ✅ All queue names match created Cloud Tasks queues
7. ✅ Wallet addresses are correct and secure
8. ✅ API keys are valid and not rate-limited
9. ✅ Database user has correct permissions
10. ✅ Ethereum RPC endpoint is active and funded (for GCHostPay3)

---

## 🔐 Security Best Practices

1. **Never commit secrets to Git** - All sensitive values in Secret Manager
2. **Rotate secrets regularly** - Especially API keys and wallet private keys
3. **Use service accounts** - Each Cloud Run service should have minimal IAM permissions
4. **Enable Secret Manager versioning** - Keep history of secret changes
5. **Monitor failed authentications** - Alert on repeated signature verification failures
6. **Separate staging & production** - Use different secrets for each environment
7. **Encrypt database credentials** - Already using Secret Manager ✅
8. **Audit secret access** - Enable Cloud Audit Logs for Secret Manager

---

## 📞 Support & Troubleshooting

**Common Issues:**

1. **"Environment variable X is not set"**
   - Check `--set-secrets` flag in Cloud Run deployment
   - Verify secret exists in Secret Manager
   - Ensure service account has access

2. **"Failed to connect to Cloud SQL"**
   - Verify `CLOUD_SQL_CONNECTION_NAME` format
   - Check database credentials are correct
   - Ensure Cloud SQL Admin API is enabled

3. **"ChangeNow API authentication failed"**
   - Verify `CHANGENOW_API_KEY` is valid
   - Check API key hasn't been revoked
   - Ensure no rate limiting

4. **"Token signature mismatch"**
   - Ensure same `SUCCESS_URL_SIGNING_KEY` across all services
   - Check for trailing whitespace in secret value
   - Verify token hasn't expired (2-hour window)

---

**Generated:** 2025-11-02
**Architecture Version:** TelePay10-26
**Document Version:** 1.0
