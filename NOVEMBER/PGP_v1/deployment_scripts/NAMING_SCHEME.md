# PayGatePrime v1 - Service and Queue Naming Scheme

## Complete Naming Architecture Update

### Service Names (Cloud Run Deployments)

| Old Name (GC Scheme) | New Name (PGP v1 Scheme) | Purpose |
|---------------------|-------------------------|---------|
| `gcregisterapi-pgp` | `pgp-server-v1` | Main backend API server |
| `np-webhook-pgp` | `pgp-npwebhook-v1` | NowPayments IPN webhook handler |
| `gcwebhook1-pgp` | `pgp-webhook1-v1` | Primary payment processor |
| `gcwebhook2-pgp` | `pgp-webhook2-v1` | Telegram invite handler |
| `gcsplit1-pgp` | `pgp-split1-v1` | Payment splitter |
| `gcsplit2-pgp` | `pgp-split2-v1` | Payment router |
| `gcsplit3-pgp` | `pgp-split3-v1` | Accumulator enqueuer |
| `gchostpay1-pgp` | `pgp-hostpay1-v1` | Crypto conversion executor |
| `gchostpay2-pgp` | `pgp-hostpay2-v1` | Conversion monitor |
| `gchostpay3-pgp` | `pgp-hostpay3-v1` | Blockchain validator |
| `gcaccumulator-pgp` | `pgp-accumulator-v1` | Payment accumulator |
| `gcbatchprocessor-pgp` | `pgp-batchprocessor-v1` | Batch processor |
| `gcmicrobatchprocessor-pgp` | `pgp-microbatchprocessor-v1` | Micro batch processor |
| `telepay-pgp` | `pgp-bot-v1` | Telegram bot |
| `gcregisterweb-pgp` | `pgp-frontend-v1` | React frontend |

### Queue Names (Cloud Tasks)

| Old Queue Name | New Queue Name | Secret Name (Old) | Secret Name (New) |
|---------------|----------------|-------------------|-------------------|
| `gcwebhook1-queue` | `pgp-webhook1-queue` | `GCWEBHOOK1_QUEUE` | `PGP_WEBHOOK1_QUEUE` |
| `gcwebhook2-queue` | `pgp-webhook2-queue` | `GCWEBHOOK2_QUEUE` | `PGP_WEBHOOK2_QUEUE` |
| `gcsplit1-queue` | `pgp-split1-queue` | `GCSPLIT1_QUEUE` | `PGP_SPLIT1_QUEUE` |
| `gcsplit2-queue` | `pgp-split2-queue` | `GCSPLIT2_QUEUE` | `PGP_SPLIT2_QUEUE` |
| `gcsplit3-queue` | `pgp-split3-queue` | `GCSPLIT3_QUEUE` | `PGP_SPLIT3_QUEUE` |
| `gcaccumulator-queue` | `pgp-accumulator-queue` | `GCACCUMULATOR_QUEUE` | `PGP_ACCUMULATOR_QUEUE` |
| `gcaccumulator-response-queue` | `pgp-accumulator-response-queue` | `GCACCUMULATOR_RESPONSE_QUEUE` | `PGP_ACCUMULATOR_RESPONSE_QUEUE` |
| `gcbatchprocessor-queue` | `pgp-batchprocessor-queue` | `GCBATCHPROCESSOR_QUEUE` | `PGP_BATCHPROCESSOR_QUEUE` |
| `gchostpay1-queue` | `pgp-hostpay1-queue` | `GCHOSTPAY1_QUEUE` | `PGP_HOSTPAY1_QUEUE` |
| `gchostpay2-queue` | `pgp-hostpay2-queue` | `GCHOSTPAY2_QUEUE` | `PGP_HOSTPAY2_QUEUE` |
| `gchostpay3-queue` | `pgp-hostpay3-queue` | `GCHOSTPAY3_QUEUE` | `PGP_HOSTPAY3_QUEUE` |
| `gchostpay1-response-queue` | `pgp-hostpay1-response-queue` | `GCHOSTPAY1_RESPONSE_QUEUE` | `PGP_HOSTPAY1_RESPONSE_QUEUE` |
| `gchostpay1-threshold-queue` | `pgp-hostpay1-threshold-queue` | `GCHOSTPAY1_THRESHOLD_QUEUE` | `PGP_HOSTPAY1_THRESHOLD_QUEUE` |
| `gchostpay3-retry-queue` | `pgp-hostpay3-retry-queue` | `GCHOSTPAY3_RETRY_QUEUE` | `PGP_HOSTPAY3_RETRY_QUEUE` |
| `gcsplit1-batch-queue` | `pgp-split1-batch-queue` | `GCSPLIT1_BATCH_QUEUE` | `PGP_SPLIT1_BATCH_QUEUE` |
| `gcsplit2-response-queue` | `pgp-split2-response-queue` | `GCSPLIT2_RESPONSE_QUEUE` | `PGP_SPLIT2_RESPONSE_QUEUE` |

### Service URL Secrets

| Old Secret Name | New Secret Name | Example Value Pattern |
|----------------|-----------------|----------------------|
| `GCWEBHOOK1_URL` | `PGP_WEBHOOK1_URL` | `https://pgp-webhook1-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCWEBHOOK2_URL` | `PGP_WEBHOOK2_URL` | `https://pgp-webhook2-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCSPLIT1_URL` | `PGP_SPLIT1_URL` | `https://pgp-split1-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCSPLIT2_URL` | `PGP_SPLIT2_URL` | `https://pgp-split2-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCSPLIT3_URL` | `PGP_SPLIT3_URL` | `https://pgp-split3-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCACCUMULATOR_URL` | `PGP_ACCUMULATOR_URL` | `https://pgp-accumulator-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCHOSTPAY1_URL` | `PGP_HOSTPAY1_URL` | `https://pgp-hostpay1-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCHOSTPAY2_URL` | `PGP_HOSTPAY2_URL` | `https://pgp-hostpay2-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCHOSTPAY3_URL` | `PGP_HOSTPAY3_URL` | `https://pgp-hostpay3-v1-{PROJECT_NUMBER}.us-central1.run.app` |

### Naming Convention Rules

**Format:** `pgp-{service}-v1`

**Components:**
- **Prefix:** `pgp` (PayGatePrime)
- **Service:** Descriptive service name (lowercase, no special chars)
- **Version:** `v1` (version 1)
- **Separator:** Hyphen `-` (Cloud Run compatible)

**Examples:**
- Server: `pgp-server-v1`
- Webhook: `pgp-webhook1-v1`, `pgp-webhook2-v1`
- Split services: `pgp-split1-v1`, `pgp-split2-v1`, `pgp-split3-v1`
- Host pay: `pgp-hostpay1-v1`, `pgp-hostpay2-v1`, `pgp-hostpay3-v1`
- Batch: `pgp-batchprocessor-v1`, `pgp-microbatchprocessor-v1`
- Special: `pgp-npwebhook-v1` (NowPayments), `pgp-bot-v1` (Telegram)

### Queue Naming Convention

**Format:** `pgp-{service}-queue` or `pgp-{service}-{type}-queue`

**Examples:**
- Simple: `pgp-webhook1-queue`
- With type: `pgp-accumulator-response-queue`, `pgp-hostpay1-threshold-queue`

### Secret Naming Convention

**Format:** `PGP_{SERVICE}_{TYPE}` (uppercase with underscores)

**Examples:**
- Queue secrets: `PGP_WEBHOOK1_QUEUE`, `PGP_SPLIT1_QUEUE`
- URL secrets: `PGP_WEBHOOK1_URL`, `PGP_HOSTPAY1_URL`
- Response queues: `PGP_ACCUMULATOR_RESPONSE_QUEUE`

---

**Last Updated:** 2025-11-16
**Architecture:** PayGatePrime v1
**Total Services:** 15
**Total Queues:** 16
