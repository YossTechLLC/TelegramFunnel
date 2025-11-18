# PGP_v1 New Naming Architecture

**Date:** 2025-11-15
**Purpose:** Complete fresh deployment with new naming scheme
**Status:** 🚀 Ready for Implementation

---

## 🏗️ **New Service Names (Cloud Run)**

| Component | Old Service Name | New Service Name | Purpose |
|-----------|------------------|------------------|---------|
| Server | `pgp_server-10-26` | `pgp-server-v1` | Main Telegram bot server |
| Orchestrator | `pgp-orchestrator-v1` | `pgp-orchestrator-v1` | Payment orchestration webhook |
| Invite | `pgp-invite-v1` | `pgp-invite-v1` | Invitation handling webhook |
| HostPay1 | `pgp-hostpay1-v1` | `pgp-hostpay1-v1` | Host payment processor 1 |
| HostPay2 | `pgp-hostpay2-v1` | `pgp-hostpay2-v1` | Host payment processor 2 |
| HostPay3 | `pgp-hostpay3-v1` | `pgp-hostpay3-v1` | Host payment processor 3 |
| Split1 | `pgp-split1-v1` | `pgp-split1-v1` | Payment splitter 1 |
| Split2 | `pgp-split2-v1` | `pgp-split2-v1` | Payment splitter 2 |
| Split3 | `pgp-split3-v1` | `pgp-split3-v1` | Payment splitter 3 |
| Accumulator | `pgp_accumulator-10-26` | `pgp-accumulator-v1` | Payment accumulator |
| BatchProcessor | `pgp_batchprocessor-10-26` | `pgp-batchprocessor-v1` | Batch payment processor |
| MicroBatch | `pgp_microbatchprocessor-10-26` | `pgp-microbatch-v1` | Micro batch processor |
| Broadcast | `pgp_broadcastscheduler-10-26` | `pgp-broadcast-v1` | Broadcast scheduler |
| Notifications | `pgp_notificationservice-10-26` | `pgp-notifications-v1` | Notification service |
| NP IPN | `PGP_NP_IPN_v1` | `pgp-np-ipn-v1` | NowPayments IPN webhook |
| Web API | `gcregisterapi-10-26` | `pgp-webapi-v1` | Backend REST API |
| Web Frontend | `gcregisterweb-10-26` | `pgp-web-v1` | Frontend static site |

---

## 📮 **New Cloud Tasks Queue Names**

| Purpose | Old Queue Name | New Queue Name |
|---------|----------------|----------------|
| Orchestrator Queue | `webhook1-queue` | `pgp-orchestrator-queue-v1` |
| Invite Queue | `webhook2-queue` | `pgp-invite-queue-v1` |
| HostPay1 Queue | `hostpay1-queue` | `pgp-hostpay1-queue-v1` |
| HostPay2 Queue | `hostpay2-queue` | `pgp-hostpay2-queue-v1` |
| HostPay3 Queue | `hostpay3-queue` | `pgp-hostpay3-queue-v1` |
| Split1 Queue | `split1-queue` | `pgp-split1-queue-v1` |
| Split2 Queue | `split2-queue` | `pgp-split2-queue-v1` |
| Split3 Queue | `split3-queue` | `pgp-split3-queue-v1` |
| Accumulator Queue | `accumulator-queue` | `pgp-accumulator-queue-v1` |
| Batch Queue | `batch-queue` | `pgp-batchprocessor-queue-v1` |
| MicroBatch Queue | `microbatch-queue` | `pgp-microbatch-queue-v1` |

---

## 🌐 **Website URLs (STATIC - DO NOT CHANGE)**

✅ **Keep these exactly as-is:**
- `http://paygateprime.com/`
- `https://www.paygateprime.com/`

These will point to `pgp-web-v1` service via Cloud Load Balancer.

---

## 📁 **File Structure (Already Renamed)**

All folders and main files already renamed per your schema:
```
PGP_v1/
├── PGP_SERVER_v1/pgp_server_v1.py
├── PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py
├── PGP_INVITE_v1/pgp_invite_v1.py
├── PGP_HOSTPAY1_v1/pgp_hostpay1_v1.py
├── PGP_HOSTPAY2_v1/pgp_hostpay2_v1.py
├── PGP_HOSTPAY3_v1/pgp_hostpay3_v1.py
├── PGP_SPLIT1_v1/pgp_split1_v1.py
├── PGP_SPLIT2_v1/pgp_split2_v1.py
├── PGP_SPLIT3_v1/pgp_split3_v1.py
├── PGP_ACCUMULATOR_v1/pgp_accumulator_v1.py
├── PGP_BATCHPROCESSOR_v1/pgp_batchprocessor_v1.py
├── PGP_MICROBATCHPROCESSOR_v1/pgp_microbatchprocessor_v1.py
├── PGP_BROADCAST_v1/pgp_broadcast_v1.py
├── PGP_NOTIFICATIONS_v1/pgp_notifications_v1.py
├── PGP_NP_IPN_v1/pgp_np_ipn_v1.py
├── PGP_WEBAPI_v1/pgp_webapi_v1.py
└── PGP_WEB_v1/index.html
```

---

## 🔐 **Secrets Strategy**

**Existing Secrets (Keep):**
- `TELEGRAM_BOT_SECRET_NAME`
- `DATABASE_*_SECRET` (all database secrets)
- `NOWPAYMENTS_API_KEY`
- `JWT_SECRET_KEY`
- `SENDGRID_API_KEY`
- etc.

**New Secrets (Will Create):**
- Service URLs will be fetched dynamically via Cloud Run metadata
- Queue URLs constructed programmatically
- No hardcoded service URLs in secrets

---

## 🔄 **Service Communication Pattern**

**Old Pattern:**
```
hardcoded URL: https://pgp-orchestrator-v1-xyz.run.app
```

**New Pattern:**
```python
# Services discover each other via:
1. Environment variables (set during deployment)
2. Cloud Run metadata API
3. Programmatic queue name construction
```

**Example:**
```python
# Old
WEBHOOK_URL = "https://pgp-orchestrator-v1-xyz.run.app"

# New
ORCHESTRATOR_URL = os.getenv("PGP_ORCHESTRATOR_URL")  # Set during deployment
# OR construct queue name:
QUEUE_NAME = f"pgp-orchestrator-queue-v1"
```

---

## 📦 **Deployment Strategy**

### Phase 1: Infrastructure Setup
1. ✅ Update all Dockerfiles
2. ✅ Update deployment scripts
3. ✅ Create master deployment script

### Phase 2: Service Deployment (Specific Order)
1. Deploy `pgp-server-v1` (Telegram bot - independent)
2. Deploy `pgp-webapi-v1` (API - independent)
3. Deploy `pgp-web-v1` (Frontend - points to API)
4. Deploy `pgp-notifications-v1` (Notifications)
5. Deploy `pgp-np-ipn-v1` (NowPayments webhook)
6. Deploy webhooks: `pgp-orchestrator-v1`, `pgp-invite-v1`
7. Deploy processors: `pgp-hostpay1/2/3-v1`, `pgp-split1/2/3-v1`
8. Deploy batch: `pgp-accumulator-v1`, `pgp-batchprocessor-v1`, `pgp-microbatch-v1`
9. Deploy `pgp-broadcast-v1` (Scheduler)

### Phase 3: Configuration
1. Update NowPayments IPN URL to point to `pgp-np-ipn-v1`
2. Update Telegram webhook to point to `pgp-server-v1`
3. Configure Cloud Load Balancer for `paygateprime.com` → `pgp-web-v1`
4. Test all service-to-service communication

---

## 🧪 **Testing Checklist**

### Pre-Deployment Testing
- [ ] All Dockerfiles build successfully
- [ ] All services pass local container tests
- [ ] Configuration files validated

### Post-Deployment Testing
- [ ] Health endpoints respond (200 OK)
- [ ] Telegram bot receives webhook
- [ ] NowPayments IPN receives test webhook
- [ ] Payment flow: NP → Orchestrator → HostPay → Split
- [ ] Batch processing works
- [ ] Broadcast scheduler triggers
- [ ] Notifications deliver
- [ ] Website loads at paygateprime.com

---

## 🔙 **Rollback Plan**

If issues occur:
1. Old services (`pgp_server-10-26`, etc.) remain untouched
2. Can switch back by updating:
   - NowPayments IPN URL
   - Telegram webhook URL
   - DNS/Load Balancer (if changed)
3. New services can be deleted without affecting old deployment

---

## 📊 **Migration vs Clean Deployment**

**Approach: Clean Deployment**
- Old services stay running
- New services deployed in parallel
- Cutover when ready (update webhooks)
- Zero downtime
- Easy rollback

---

## 🎯 **Success Criteria**

✅ All 17 services deployed with new names
✅ All webhooks pointing to new services
✅ All service-to-service communication working
✅ Website accessible at paygateprime.com
✅ End-to-end payment flow tested successfully
✅ Old services can be safely decommissioned

---

**Next Step:** Begin systematic implementation starting with Dockerfile updates.
