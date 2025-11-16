# PGP_v1 Secret Name Mapping

This document maps old secret names to new PGP_v1 secret names.

## Service URL Secrets

| Old Secret Name | New Secret Name | New Value Example |
|-----------------|-----------------|-------------------|
| `GCWEBHOOK1_URL` | `PGP_ORCHESTRATOR_URL` | `https://pgp-orchestrator-v1-xxx.run.app` |
| `GCWEBHOOK2_URL` | `PGP_INVITE_URL` | `https://pgp-invite-v1-xxx.run.app` |
| `GCSPLIT1_URL` | `PGP_SPLIT1_URL` | `https://pgp-split1-v1-xxx.run.app` |
| `GCSPLIT2_URL` | `PGP_SPLIT2_URL` | `https://pgp-split2-v1-xxx.run.app` |
| `GCSPLIT3_URL` | `PGP_SPLIT3_URL` | `https://pgp-split3-v1-xxx.run.app` |
| `GCHOSTPAY1_URL` | `PGP_HOSTPAY1_URL` | `https://pgp-hostpay1-v1-xxx.run.app` |
| `GCHOSTPAY2_URL` | `PGP_HOSTPAY2_URL` | `https://pgp-hostpay2-v1-xxx.run.app` |
| `GCHOSTPAY3_URL` | `PGP_HOSTPAY3_URL` | `https://pgp-hostpay3-v1-xxx.run.app` |
| `GCACCUMULATOR_URL` | `PGP_ACCUMULATOR_URL` | `https://pgp-accumulator-v1-xxx.run.app` |
| `GCBATCHPROCESSOR_URL` | `PGP_BATCHPROCESSOR_URL` | `https://pgp-batchprocessor-v1-xxx.run.app` |
| `MICROBATCH_URL` | `PGP_MICROBATCH_URL` | `https://pgp-microbatch-v1-xxx.run.app` |
| `TELEPAY_BOT_URL` | `PGP_SERVER_URL` | `https://pgp-server-v1-xxx.run.app` |
| `HOSTPAY_WEBHOOK_URL` | `PGP_HOSTPAY1_URL` | (same as above) |

## Queue Name Secrets

| Old Secret Name | New Secret Name | New Value |
|-----------------|-----------------|-----------|
| `GCWEBHOOK2_QUEUE` | `PGP_INVITE_QUEUE` | `pgp-invite-queue-v1` |
| `GCSPLIT1_QUEUE` | `PGP_ORCHESTRATOR_QUEUE` | `pgp-orchestrator-queue-v1` |
| `GCSPLIT2_QUEUE` | `PGP_SPLIT2_ESTIMATE_QUEUE` | `pgp-split2-estimate-queue-v1` |
| `GCSPLIT3_QUEUE` | `PGP_SPLIT3_SWAP_QUEUE` | `pgp-split3-swap-queue-v1` |
| `HOSTPAY_QUEUE` | `PGP_HOSTPAY_TRIGGER_QUEUE` | `pgp-hostpay-trigger-queue-v1` |
| `GCHOSTPAY1_RESPONSE_QUEUE` | `PGP_HOSTPAY1_RESPONSE_QUEUE` | `pgp-hostpay1-response-queue-v1` |
| `GCHOSTPAY2_QUEUE` | `PGP_HOSTPAY2_STATUS_QUEUE` | `pgp-hostpay2-status-queue-v1` |
| `GCHOSTPAY3_QUEUE` | `PGP_HOSTPAY3_PAYMENT_QUEUE` | `pgp-hostpay3-payment-queue-v1` |
| `GCACCUMULATOR_QUEUE` | `PGP_ACCUMULATOR_QUEUE` | `pgp-accumulator-queue-v1` |
| `MICROBATCH_RESPONSE_QUEUE` | `PGP_MICROBATCH_RESPONSE_QUEUE` | `pgp-microbatch-response-queue-v1` |

## Static Secrets (No Changes)

These secrets keep their current names:
- `SUCCESS_URL_SIGNING_KEY`
- `TPS_HOSTPAY_SIGNING_KEY`
- `TP_FLAT_FEE`
- `CHANGENOW_API_KEY`
- `NOWPAYMENTS_API_KEY`
- `NOWPAYMENTS_IPN_SECRET`
- `CLOUD_TASKS_PROJECT_ID`
- `CLOUD_TASKS_LOCATION`
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`
- `TELEGRAM_BOT_SECRET_NAME`
- `TELEGRAM_BOT_USERNAME`
- `JWT_SECRET_KEY`
- `SENDGRID_API_KEY`
- `FROM_EMAIL`
- `FROM_NAME`
- `BASE_URL`
- `CORS_ORIGIN`
- `SIGNUP_SECRET_KEY`

## Implementation Notes

1. **Backwards Compatibility**: During transition, both old and new secrets can coexist
2. **Deployment Order**: Update secrets in Google Secret Manager BEFORE deploying services
3. **Validation**: Each service logs which secrets it successfully loaded
4. **Rollback**: If needed, revert to old secret names without code changes (just secret values)
