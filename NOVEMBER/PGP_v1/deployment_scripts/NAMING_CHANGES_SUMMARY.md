# PayGatePrime v1 - Naming Architecture Changes Summary

## ✅ Complete Migration to PGP v1 Naming Scheme

All queue names, service names, and secret names have been updated from the old GC scheme to the new PGP v1 naming architecture.

---

## 🎯 New Naming Convention

### Format Rules:
- **Cloud Run Services:** `pgp-{service}-v1` (lowercase, hyphens)
- **Cloud Tasks Queues:** `pgp-{service}-queue` or `pgp-{service}-{type}-queue`
- **Queue Secret Names:** `PGP_{SERVICE}_QUEUE` (uppercase, underscores)
- **Service URL Secret Names:** `PGP_{SERVICE}_URL` (uppercase, underscores)

---

## 📦 Service Name Changes (15 Services)

| Old Name (GC Scheme) | New Name (PGP v1) | Purpose |
|---------------------|-------------------|---------|
| `gcregisterapi-pgp` | `pgp-server-v1` | Main backend API server |
| `np-webhook-pgp` | `pgp-npwebhook-v1` | NowPayments IPN webhook |
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

---

## 📨 Queue Name Changes (16 Queues)

| Old Queue Name | New Queue Name | Old Secret Name | New Secret Name |
|---------------|----------------|----------------|----------------|
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

---

## 🌐 Service URL Secret Changes (9 Secrets)

| Old Secret Name | New Secret Name | Example New URL |
|----------------|-----------------|-----------------|
| `GCWEBHOOK1_URL` | `PGP_WEBHOOK1_URL` | `https://pgp-webhook1-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCWEBHOOK2_URL` | `PGP_WEBHOOK2_URL` | `https://pgp-webhook2-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCSPLIT1_URL` | `PGP_SPLIT1_URL` | `https://pgp-split1-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCSPLIT2_URL` | `PGP_SPLIT2_URL` | `https://pgp-split2-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCSPLIT3_URL` | `PGP_SPLIT3_URL` | `https://pgp-split3-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCACCUMULATOR_URL` | `PGP_ACCUMULATOR_URL` | `https://pgp-accumulator-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCHOSTPAY1_URL` | `PGP_HOSTPAY1_URL` | `https://pgp-hostpay1-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCHOSTPAY2_URL` | `PGP_HOSTPAY2_URL` | `https://pgp-hostpay2-v1-{PROJECT_NUMBER}.us-central1.run.app` |
| `GCHOSTPAY3_URL` | `PGP_HOSTPAY3_URL` | `https://pgp-hostpay3-v1-{PROJECT_NUMBER}.us-central1.run.app` |

---

## 📋 Files Updated

1. ✅ **NAMING_SCHEME.md** (NEW) - Complete naming architecture reference
2. ✅ **04_create_queue_secrets.sh** - Updated all queue secret names and values
3. ✅ **05_create_service_url_secrets.sh** - Updated all service URL secrets and names
4. ✅ **SECRETS_REFERENCE.md** - Updated all queue and service URL references
5. ✅ **SECRET_CONFIG_UPDATE.md** - Updated all secret name references

---

## 📊 Statistics

- **Total Services Renamed:** 15
- **Total Queues Renamed:** 16
- **Total Queue Secrets Renamed:** 16
- **Total Service URL Secrets Renamed:** 9
- **Total Secret Changes:** 25

---

## 🎯 Benefits of New Naming Scheme

### 1. Consistent Branding
- All resources use "PGP" (PayGatePrime) prefix
- Professional, cohesive naming across entire platform

### 2. Clear Versioning
- `-v1` suffix enables future version management
- Easy to deploy v2 alongside v1 if needed

### 3. Cloud Run Compliant
- Lowercase with hyphens (Cloud Run requirements)
- No underscores or special characters in service names

### 4. Better Readability
- `pgp-webhook1-v1` vs `gcwebhook1-pgp`
- Immediately identifies service purpose and version

### 5. Easier Management
- Consistent pattern makes automation easier
- Secret names clearly map to services (PGP_WEBHOOK1_URL)

---

## 🔄 Backward Compatibility Note

**IMPORTANT:** These naming changes affect deployment scripts ONLY. The actual Python source code in service directories (GCWebhook1-PGP, etc.) does NOT need to be renamed - only the Cloud Run service names when deploying.

**Service directory names remain unchanged:**
- Directory: `/NOVEMBER/PGP_v1/GCWebhook1-PGP/` ✅ (unchanged)
- Deployed as: `pgp-webhook1-v1` ✅ (new)

This separation allows for:
- Clean git history
- No code changes required
- Deployment scripts control naming

---

## ✅ Next Steps

1. **Review** NAMING_SCHEME.md for complete reference
2. **Use** updated deployment scripts (04, 05)
3. **Deploy** services with new names when ready
4. **Verify** all secret names match new convention

---

## 📚 Reference Documents

- **NAMING_SCHEME.md** - Complete naming architecture
- **SECRETS_REFERENCE.md** - All 46 secrets with new names
- **SECRET_CONFIG_UPDATE.md** - Configuration update guide
- **04_create_queue_secrets.sh** - Queue secrets creation
- **05_create_service_url_secrets.sh** - Service URL secrets creation

---

**Migration Date:** 2025-11-16
**Architecture:** PayGatePrime v1
**Status:** ✅ COMPLETE
