# Secret Manager Configuration - Quick Reference

**Project**: `telepay-459221`
**Total**: 75 secrets
**Last Updated**: 2025-11-14

---

## All Secrets - Alphabetical

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `1INCH_API_KEY` | `tXRQ...v7c5` (32 chars) | 1inch DEX API |
| `ALERTING_ENABLED` | `true` | System alerts flag |
| `BASE_URL` | `https://www.paygateprime.com` | Main app URL |
| `BROADCAST_AUTO_INTERVAL` | `24` | Auto broadcast hours |
| `BROADCAST_MANUAL_INTERVAL` | `0.0833` | Manual broadcast hours (5min) |
| `CHANGENOW_API_KEY` | `0e7a...5bde` (64 chars) | ChangeNOW exchange |
| `CLOUD_SQL_CONNECTION_NAME` | `telepay-459221:us-central1:telepaypsql` | Cloud SQL instance |
| `CLOUD_TASKS_LOCATION` | `us-central1` | Tasks region |
| `CLOUD_TASKS_PROJECT_ID` | `telepay-459221` | Tasks project |
| `COINGECKO_API_KEY` | `CG-A...Dzmo` (25 chars) | CoinGecko price API |
| `CORS_ORIGIN` | `https://www.paygateprime.com` | CORS origin |
| `CRYPTOCOMPARE_API_KEY` | `f76f...df48` (64 chars) | CryptoCompare API |
| `DATABASE_HOST_SECRET` | `34.58.246.248` | PostgreSQL host IP |
| `DATABASE_NAME_SECRET` | `client_table` | Database name |
| `DATABASE_PASSWORD_SECRET` | `Chig...st3$` (15 chars) | PostgreSQL password |
| `DATABASE_SECRET_KEY` | `y764...3LM` (43 chars) | DB encryption key |
| `DATABASE_USER_SECRET` | `postgres` | PostgreSQL user |
| `ETHEREUM_RPC_URL` | `https://eth-mainnet.g.alchemy.com/v2/AQB6...Nohb` | Alchemy RPC full URL |
| `ETHEREUM_RPC_URL_API` | `AQB6...Nohb` (32 chars) | Alchemy API key only |
| `ETHEREUM_RPC_WEBHOOK_SECRET` | `whse...1exs` (32 chars) | Alchemy webhook secret |
| `FROM_EMAIL` | `noreply@paygateprime.com` | Sender email |
| `FROM_NAME` | `PayGatePrime` | Sender name |
| `GCACCUMULATOR_QUEUE` | `accumulator-payment-queue` | Accumulator queue |
| `GCACCUMULATOR_RESPONSE_QUEUE` | `pgp_accumulator-swap-response-queue` | Accumulator response |
| `GCACCUMULATOR_URL` | `https://pgp_accumulator-10-26-291176869049.us-central1.run.app` | Accumulator service |
| `GCBATCHPROCESSOR_QUEUE` | `pgp_batchprocessor-10-26-queue` | Batch processor queue |
| `GCBATCHPROCESSOR_URL` | `https://pgp_batchprocessor-10-26-291176869049.us-central1.run.app` | Batch processor service |
| `GCHOSTPAY1_BATCH_QUEUE` | `gchostpay1-batch-queue` | HostPay1 batch queue |
| `GCHOSTPAY1_QUEUE` | `gcsplit-hostpay-trigger-queue` | HostPay1 trigger queue |
| `GCHOSTPAY1_RESPONSE_QUEUE` | `gchostpay1-response-queue` | HostPay1 response |
| `GCHOSTPAY1_URL` | `https://gchostpay1-10-26-291176869049.us-central1.run.app` | HostPay1 service |
| `GCHOSTPAY2_QUEUE` | `gchostpay2-status-check-queue` | HostPay2 status queue |
| `GCHOSTPAY2_URL` | `https://gchostpay2-10-26-291176869049.us-central1.run.app` | HostPay2 service |
| `GCHOSTPAY3_QUEUE` | `gchostpay3-payment-exec-queue` | HostPay3 exec queue |
| `GCHOSTPAY3_RETRY_QUEUE` | `gchostpay3-retry-queue` | HostPay3 retry |
| `GCHOSTPAY3_URL` | `https://gchostpay3-10-26-291176869049.us-central1.run.app` | HostPay3 service |
| `GCSPLIT1_BATCH_QUEUE` | `gcsplit1-batch-queue` | Split1 batch queue |
| `GCSPLIT1_ESTIMATE_RESPONSE_URL` | `https://gcsplit1-10-26-291176869049.us-central1.run.app/usdt-eth-estimate` | Split1 estimate callback |
| `GCSPLIT1_QUEUE` | `gcsplit-webhook-queue` | Split1 webhook queue |
| `GCSPLIT1_SWAP_RESPONSE_URL` | `https://gcsplit1-10-26-291176869049.us-central1.run.app/eth-client-swap` | Split1 swap callback |
| `GCSPLIT1_URL` | `https://gcsplit1-10-26-291176869049.us-central1.run.app` | Split1 service |
| `GCSPLIT2_QUEUE` | `gcsplit-usdt-eth-estimate-queue` | Split2 estimate queue |
| `GCSPLIT2_RESPONSE_QUEUE` | `gcsplit-usdt-eth-response-queue` | Split2 response |
| `GCSPLIT2_URL` | `https://gcsplit2-10-26-291176869049.us-central1.run.app` | Split2 service |
| `GCSPLIT3_QUEUE` | `gcsplit-eth-client-swap-queue` | Split3 swap queue |
| `GCSPLIT3_RESPONSE_QUEUE` | `gcsplit-eth-client-response-queue` | Split3 response |
| `GCSPLIT3_URL` | `https://gcsplit3-10-26-291176869049.us-central1.run.app` | Split3 service |
| `GCWEBHOOK1_QUEUE` | `gcwebhook1-queue` | Webhook1 queue |
| `GCWEBHOOK1_URL` | `https://gcwebhook1-10-26-pjxwjsdktq-uc.a.run.app` | Webhook1 service |
| `GCWEBHOOK2_QUEUE` | `gcwebhook-telegram-invite-queue` | Webhook2 invite queue |
| `GCWEBHOOK2_URL` | `https://gcwebhook2-10-26-291176869049.us-central1.run.app` | Webhook2 service |
| `HOSTPAY_QUEUE` | `gcsplit-hostpay-trigger-queue` | ⚠️ Duplicate of GCHOSTPAY1_QUEUE |
| `HOSTPAY_WEBHOOK_URL` | `https://gchostpay1-10-26-291176869049.us-central1.run.app` | ⚠️ Duplicate of GCHOSTPAY1_URL |
| `HOST_WALLET_ETH_ADDRESS` | `0x16...1bc4` | Host wallet ETH address |
| `HOST_WALLET_PRIVATE_KEY` | `7273...8f2e` (64 chars) | 🔴 CRITICAL: Wallet private key |
| `HOST_WALLET_USDT_ADDRESS` | `0x16...1bc4` | Host wallet USDT (same as ETH) |
| `JWT_SECRET_KEY` | `cc54...de71` (64 chars) | JWT signing key |
| `MICROBATCH_RESPONSE_QUEUE` | `microbatch-response-queue` | MicroBatch response |
| `MICROBATCH_URL` | `https://pgp_microbatchprocessor-10-26-pjxwjsdktq-uc.a.run.app` | MicroBatch service |
| `MICRO_BATCH_THRESHOLD_USD` | `5.00` | Micro batch threshold |
| `NOWPAYMENTS_API_KEY` | `WHY9...D9J` (27 chars) | NOWPayments API |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | `https://PGP_NP_IPN_v1-pjxwjsdktq-uc.a.run.app` | NOWPayments IPN callback |
| `NOWPAYMENTS_IPN_SECRET` | `1EQD...DQs` (28 chars) | NOWPayments IPN secret |
| `NOWPAYMENT_WEBHOOK_KEY` | `erwU...uqL` (28 chars) | NOWPayments webhook key |
| `PAYMENT_FALLBACK_TOLERANCE` | `0.75` | Fallback tolerance USD |
| `PAYMENT_MIN_TOLERANCE` | `0.50` | Min tolerance USD |
| `PAYMENT_PROVIDER_TOKEN` | `WHY9...D9J` (27 chars) | ⚠️ Duplicate of NOWPAYMENTS_API_KEY |
| `SENDGRID_API_KEY` | `SG.t...tVs` (69 chars) | SendGrid email API |
| `SIGNUP_SECRET_KEY` | `16a5...75d4` (64 chars) | User signup key |
| `SUCCESS_URL_SIGNING_KEY` | `sSll...q+sI=` (44 chars) | Payment success URL signing |
| `TELEGRAM_BOT_SECRET_NAME` | `8139...6Co` (46 chars) | Telegram bot token |
| `TELEGRAM_BOT_USERNAME` | `PayGatePrime_bot` | Telegram bot username |
| `TELEPAY_BOT_URL` | `http://34.58.80.152:8080` | TelePay bot VM (HTTP) |
| `TPS_HOSTPAY_SIGNING_KEY` | `6b5f...df5a` (64 chars) | TelePay→HostPay signing |
| `TPS_WEBHOOK_URL` | `https://gcsplit1-10-26-291176869049.us-central1.run.app` | TelePay webhook callback |
| `TP_FLAT_FEE` | `15` | TelePay flat fee % |
| `WEBHOOK_BASE_URL` | `https://gcwebhook1-10-26-291176869049.us-central1.run.app` | Webhook base URL |
| `WEBHOOK_SIGNING_KEY` | `f4e7...2345` (64 chars) | Webhook payload signing |

---

## Quick Access Patterns

### Database Connection
```python
DB_HOST = "34.58.246.248"
DB_NAME = "client_table"
DB_USER = "postgres"
DB_PASS = "Chig...st3$"  # Fetch from SECRET_CONFIG
CLOUD_SQL = "telepay-459221:us-central1:telepaypsql"
```

### Service URLs (Pattern: https://[SERVICE]-10-26-291176869049.us-central1.run.app)
- PGP_ACCUMULATOR, PGP_BATCHPROCESSOR, GCHostPay1/2/3, GCSplit1/2/3, GCWebhook2

### Service URLs (Pattern: https://[SERVICE]-10-26-pjxwjsdktq-uc.a.run.app)
- GCWebhook1, PGP_MICROBATCHPROCESSOR, np-webhook

### VM-based (HTTP)
- PGP_SERVER_v1: `http://34.58.80.152:8080`

### Critical Secrets (Fetch via gcloud)
- `HOST_WALLET_PRIVATE_KEY`: 7273...8f2e (64 chars) 🔴
- `DATABASE_PASSWORD_SECRET`: Chig...st3$ (15 chars)
- `TELEGRAM_BOT_SECRET_NAME`: 8139...6Co (46 chars)
- `NOWPAYMENTS_API_KEY`: WHY9...D9J (27 chars)

### Fetch Command
```bash
gcloud secrets versions access latest --secret="SECRET_NAME" --project=telepay-459221
```

### Full Path Format
```
projects/telepay-459221/secrets/[SECRET_NAME]/versions/latest
```

---

## Notes
- 3 duplicate secrets: PAYMENT_PROVIDER_TOKEN, HOSTPAY_QUEUE, HOSTPAY_WEBHOOK_URL
- HOST_WALLET_ETH_ADDRESS = HOST_WALLET_USDT_ADDRESS (correct for ERC-20)
- BROADCAST_MANUAL_INTERVAL = 0.0833 hours = 5 minutes
