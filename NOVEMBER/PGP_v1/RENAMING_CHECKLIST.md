# PGP_v1 Service Renaming Checklist

**Purpose:** Systematic checklist to update all references after folder/file renaming
**Date:** 2025-11-15
**Status:** ⏳ Pre-Deployment Review

## ⚠️ CRITICAL: DO NOT DEPLOY UNTIL ALL ITEMS ARE CHECKED

---

## 📋 Naming Schema Changes Summary

| Old Name | New Name | Main File Old | Main File New |
|----------|----------|---------------|---------------|
| PGP_ACCUMULATOR_v1 | PGP_ACCUMULATOR_v1 | pgp_accumulator_v1.py | pgp_accumulator_v1.py |
| PGP_BATCHPROCESSOR_v1 | PGP_BATCHPROCESSOR_v1 | pgp_batchprocessor_v1.py | pgp_batchprocessor_v1.py |
| PGP_WEB_v1 | PGP_WEB_v1 | (static files) | (static files) |
| PGP_WEBAPI_v1 | PGP_WEBAPI_v1 | app.py | pgp_webapi_v1.py |
| PGP_NP_IPN_v1 | PGP_NP_IPN_v1 | app.py | pgp_np_ipn_v1.py |
| PGP_NOTIFICATIONS_v1 | PGP_NOTIFICATIONS_v1 | pgp_notifications_v1.py | pgp_notifications_v1.py |
| PGP_MICROBATCHPROCESSOR_v1 | PGP_MICROBATCHPROCESSOR_v1 | micropgp_batchprocessor_v1.py | pgp_microbatchprocessor_v1.py |
| PGP_INVITE_v1 | PGP_INVITE_v1 | pgp_invite_v1.py | pgp_invite_v1.py |
| PGP_ORCHESTRATOR_v1 | PGP_ORCHESTRATOR_v1 | pgp_orchestrator_v1.py | pgp_orchestrator_v1.py |
| PGP_BROADCAST_v1 | PGP_BROADCAST_v1 | pgp_broadcast_v1.py | pgp_broadcast_v1.py |
| PGP_SPLIT3_v1 | PGP_SPLIT3_v1 | pgp_split3_v1.py | pgp_split3_v1.py |
| PGP_SPLIT2_v1 | PGP_SPLIT2_v1 | pgp_split2_v1.py | pgp_split2_v1.py |
| PGP_SPLIT1_v1 | PGP_SPLIT1_v1 | pgp_split1_v1.py | pgp_split1_v1.py |
| PGP_HOSTPAY3_v1 | PGP_HOSTPAY3_v1 | pgp_hostpay3_v1.py | pgp_hostpay3_v1.py |
| PGP_HOSTPAY2_v1 | PGP_HOSTPAY2_v1 | pgp_hostpay2_v1.py | pgp_hostpay2_v1.py |
| PGP_HOSTPAY1_v1 | PGP_HOSTPAY1_v1 | pgp_hostpay1_v1.py | pgp_hostpay1_v1.py |
| PGP_SERVER_v1 | PGP_SERVER_v1 | pgp_server_v1.py | pgp_server_v1.py |

---

## 🔧 PHASE 1: Internal Service File Updates

### 1.1 Dockerfile Updates (17 services)

#### ☐ PGP_ACCUMULATOR_v1
- [ ] Update `COPY pgp_accumulator_v1.py .` → `COPY pgp_accumulator_v1.py .`
- [ ] Update `CMD ["python", "pgp_accumulator_v1.py"]` → `CMD ["python", "pgp_accumulator_v1.py"]`

#### ☐ PGP_BATCHPROCESSOR_v1
- [ ] Update `COPY pgp_batchprocessor_v1.py .` → `COPY pgp_batchprocessor_v1.py .`
- [ ] Update `CMD ["python", "pgp_batchprocessor_v1.py"]` → `CMD ["python", "pgp_batchprocessor_v1.py"]`

#### ☐ PGP_ORCHESTRATOR_v1
- [ ] Update `COPY pgp_orchestrator_v1.py .` → `COPY pgp_orchestrator_v1.py .`
- [ ] Update `CMD ["python", "pgp_orchestrator_v1.py"]` → `CMD ["python", "pgp_orchestrator_v1.py"]`

#### ☐ PGP_INVITE_v1
- [ ] Update `COPY pgp_invite_v1.py .` → `COPY pgp_invite_v1.py .`
- [ ] Update `CMD ["python", "pgp_invite_v1.py"]` → `CMD ["python", "pgp_invite_v1.py"]`

#### ☐ PGP_HOSTPAY1_v1
- [ ] Update `COPY pgp_hostpay1_v1.py .` → `COPY pgp_hostpay1_v1.py .`
- [ ] Update `CMD ["python", "pgp_hostpay1_v1.py"]` → `CMD ["python", "pgp_hostpay1_v1.py"]`

#### ☐ PGP_HOSTPAY2_v1
- [ ] Update `COPY pgp_hostpay2_v1.py .` → `COPY pgp_hostpay2_v1.py .`
- [ ] Update `CMD ["python", "pgp_hostpay2_v1.py"]` → `CMD ["python", "pgp_hostpay2_v1.py"]`

#### ☐ PGP_HOSTPAY3_v1
- [ ] Update `COPY pgp_hostpay3_v1.py .` → `COPY pgp_hostpay3_v1.py .`
- [ ] Update `CMD ["python", "pgp_hostpay3_v1.py"]` → `CMD ["python", "pgp_hostpay3_v1.py"]`

#### ☐ PGP_SPLIT1_v1
- [ ] Update `COPY pgp_split1_v1.py .` → `COPY pgp_split1_v1.py .`
- [ ] Update `CMD ["python", "pgp_split1_v1.py"]` → `CMD ["python", "pgp_split1_v1.py"]`

#### ☐ PGP_SPLIT2_v1
- [ ] Update `COPY pgp_split2_v1.py .` → `COPY pgp_split2_v1.py .`
- [ ] Update `CMD ["python", "pgp_split2_v1.py"]` → `CMD ["python", "pgp_split2_v1.py"]`

#### ☐ PGP_SPLIT3_v1
- [ ] Update `COPY pgp_split3_v1.py .` → `COPY pgp_split3_v1.py .`
- [ ] Update `CMD ["python", "pgp_split3_v1.py"]` → `CMD ["python", "pgp_split3_v1.py"]`

#### ☐ PGP_MICROBATCHPROCESSOR_v1
- [ ] Update `COPY micropgp_batchprocessor_v1.py .` → `COPY pgp_microbatchprocessor_v1.py .`
- [ ] Update `CMD ["python", "micropgp_batchprocessor_v1.py"]` → `CMD ["python", "pgp_microbatchprocessor_v1.py"]`

#### ☐ PGP_SERVER_v1
- [ ] Update `COPY pgp_server_v1.py .` → `COPY pgp_server_v1.py .`
- [ ] Update `CMD ["python", "pgp_server_v1.py"]` → `CMD ["python", "pgp_server_v1.py"]`

#### ☐ PGP_BROADCAST_v1
- [ ] Update `COPY pgp_broadcast_v1.py .` → `COPY pgp_broadcast_v1.py .`
- [ ] Update `CMD ["python", "pgp_broadcast_v1.py"]` → `CMD ["python", "pgp_broadcast_v1.py"]`

#### ☐ PGP_NOTIFICATIONS_v1
- [ ] Update `COPY pgp_notifications_v1.py .` → `COPY pgp_notifications_v1.py .`
- [ ] Update `CMD ["python", "pgp_notifications_v1.py"]` → `CMD ["python", "pgp_notifications_v1.py"]`

#### ☐ PGP_NP_IPN_v1
- [ ] Update `COPY app.py .` → `COPY pgp_np_ipn_v1.py .`
- [ ] Update `CMD ["python", "app.py"]` → `CMD ["python", "pgp_np_ipn_v1.py"]`

#### ☐ PGP_WEBAPI_v1
- [ ] Update `COPY app.py .` → `COPY pgp_webapi_v1.py .`
- [ ] Update `CMD ["python", "app.py"]` → `CMD ["python", "pgp_webapi_v1.py"]`

#### ☐ PGP_WEB_v1
- [ ] Verify no CMD changes needed (static files only)

---

### 1.2 Python Import Statements

#### ☐ Check all Python files for relative imports
- [ ] Search for `from acc10-26 import`
- [ ] Search for `from batch10-26 import`
- [ ] Search for `from tph1-10-26 import`
- [ ] Search for `from tph2-10-26 import`
- [ ] Search for `from tphp1-10-26 import`
- [ ] Search for `from tphp2-10-26 import`
- [ ] Search for `from tphp3-10-26 import`
- [ ] Search for `from tps1-10-26 import`
- [ ] Search for `from tps2-10-26 import`
- [ ] Search for `from tps3-10-26 import`
- [ ] Search for `from microbatch10-26 import`
- [ ] Search for `from pgp_server10-26 import`
- [ ] Search for `from service import` (in notifications context)
- [ ] Search for `from main import` (in broadcast context)
- [ ] Search for `from app import` (in webapi/np_ipn context)

---

## 🌐 PHASE 2: Cross-Service References

### 2.1 Service URL References

#### ☐ Update Google Cloud Run Service Names
**Old naming pattern:** `pgp_server-10-26`, `gcwebhook1-10-26`, etc.
**New naming pattern:** TBD - Need to define

Potential new service names:
- [ ] `pgp_server-10-26` → `pgp-server-v1` or `pgp_server-server-v1`?
- [ ] `gcwebhook1-10-26` → `pgp-orchestrator-v1`?
- [ ] `gcwebhook2-10-26` → `pgp-invite-v1`?
- [ ] `gchostpay1-10-26` → `pgp-hostpay1-v1`?
- [ ] `gchostpay2-10-26` → `pgp-hostpay2-v1`?
- [ ] `gchostpay3-10-26` → `pgp-hostpay3-v1`?
- [ ] `gcsplit1-10-26` → `pgp-split1-v1`?
- [ ] `gcsplit2-10-26` → `pgp-split2-v1`?
- [ ] `gcsplit3-10-26` → `pgp-split3-v1`?
- [ ] `pgp_batchprocessor-10-26` → `pgp-batchprocessor-v1`?
- [ ] `pgp_accumulator-10-26` → `pgp-accumulator-v1`?
- [ ] `pgp_microbatchprocessor-10-26` → `pgp-microbatchprocessor-v1`?
- [ ] `pgp_broadcastscheduler-10-26` → `pgp-broadcast-v1`?
- [ ] `pgp_notificationservice-10-26` → `pgp-notifications-v1`?
- [ ] `PGP_NP_IPN_v1` → `pgp-np-ipn-v1`?
- [ ] `gcregisterapi-10-26` → `pgp-webapi-v1`?
- [ ] `gcregisterweb-10-26` → `pgp-web-v1`?

**⚠️ DECISION NEEDED:** Confirm new Cloud Run service names before proceeding!

### 2.2 HTTP Endpoint References

#### ☐ Search for hardcoded service URLs in all Python files
- [ ] PGP_ORCHESTRATOR_v1: Check for webhook calls to other services
- [ ] PGP_INVITE_v1: Check for webhook calls to other services
- [ ] PGP_HOSTPAY1_v1: Check for calls to split services
- [ ] PGP_HOSTPAY2_v1: Check for calls to split services
- [ ] PGP_HOSTPAY3_v1: Check for calls to split services
- [ ] PGP_SPLIT1_v1: Check for calls to hostpay services
- [ ] PGP_SPLIT2_v1: Check for calls to hostpay services
- [ ] PGP_SPLIT3_v1: Check for calls to hostpay services
- [ ] PGP_BATCHPROCESSOR_v1: Check for accumulator calls
- [ ] PGP_ACCUMULATOR_v1: Check for webhook callbacks
- [ ] PGP_SERVER_v1: Check for notification service calls
- [ ] PGP_NOTIFICATIONS_v1: Check for server callbacks
- [ ] PGP_NP_IPN_v1: Check for calls to orchestrator/invite

### 2.3 Cloud Tasks Queue Names

#### ☐ Update queue names if they reference old service names
- [ ] Check PGP_ORCHESTRATOR_v1 for queue creation/references
- [ ] Check PGP_INVITE_v1 for queue creation/references
- [ ] Check PGP_HOSTPAY* services for queue references
- [ ] Check PGP_SPLIT* services for queue references
- [ ] Check PGP_ACCUMULATOR_v1 for queue references
- [ ] Check PGP_BATCHPROCESSOR_v1 for queue references

---

## 📜 PHASE 3: Deployment Scripts

### 3.1 Shell Script Updates

#### ☐ deploy_pgp_server_bot.sh
- [ ] Update `SERVICE_NAME="pgp_server-10-26"` → `SERVICE_NAME="pgp-server-v1"`
- [ ] Update `SOURCE_DIR` path to `NOVEMBER/PGP_v1/PGP_SERVER_v1`
- [ ] Update file existence checks (notification_pgp_notifications_v1.py, server_manager.py)

#### ☐ deploy_np_webhook.sh
- [ ] Update service name references
- [ ] Update SOURCE_DIR path to `NOVEMBER/PGP_v1/PGP_NP_IPN_v1`

#### ☐ deploy_gcwebhook_tasks_queues.sh
- [ ] Update service names for orchestrator and invite
- [ ] Update SOURCE_DIR paths

#### ☐ deploy_hostpay_tasks_queues.sh
- [ ] Update all 3 hostpay service names
- [ ] Update SOURCE_DIR paths

#### ☐ deploy_gcsplit_tasks_queues.sh
- [ ] Update all 3 split service names
- [ ] Update SOURCE_DIR paths

#### ☐ deploy_accumulator_tasks_queues.sh
- [ ] Update accumulator service name
- [ ] Update SOURCE_DIR path

#### ☐ deploy_backend_api.sh
- [ ] Update WEBAPI service name
- [ ] Update SOURCE_DIR path to `NOVEMBER/PGP_v1/PGP_WEBAPI_v1`

#### ☐ deploy_frontend.sh
- [ ] Update WEB service name
- [ ] Update SOURCE_DIR path to `NOVEMBER/PGP_v1/PGP_WEB_v1`

#### ☐ deploy_broadcast_scheduler.sh
- [ ] Update broadcast service name
- [ ] Update SOURCE_DIR path to `NOVEMBER/PGP_v1/PGP_BROADCAST_v1`

#### ☐ deploy_gcsubscriptionmonitor.sh
- [ ] Update notifications service name
- [ ] Update SOURCE_DIR path to `NOVEMBER/PGP_v1/PGP_NOTIFICATIONS_v1`

#### ☐ deploy_pgp_broadcastservice_message_tracking.sh
- [ ] Update broadcast service name
- [ ] Update SOURCE_DIR path

#### ☐ Other deployment scripts
- [ ] deploy_config_fixes.sh
- [ ] deploy_notification_feature.sh
- [ ] deploy_message_tracking_migration.sh
- [ ] deploy_actual_eth_fix.sh
- [ ] pause_broadcast_scheduler.sh
- [ ] resume_broadcast_scheduler.sh

---

## 🗄️ PHASE 4: Configuration & Secrets

### 4.1 Environment Variables

#### ☐ Check for service name references in env vars
- [ ] Review all `.env.example` files
- [ ] Check for hardcoded service URLs in config_manager.py files
- [ ] Verify no old service names in environment variable values

### 4.2 Google Cloud Secrets

#### ☐ SECRET_CONFIG.md
- [ ] Review for any secret values that contain old service names
- [ ] Update documentation if new service URLs are stored as secrets

### 4.3 Service Account Permissions

#### ☐ Verify service accounts have access to new service names
- [ ] Cloud Run Invoker roles
- [ ] Cloud Tasks Enqueuer roles
- [ ] Secret Manager accessor roles

---

## 📊 PHASE 5: Database References

### 5.1 Database Tables

#### ☐ Check if any DB tables reference service names
- [ ] Review database_manager.py in all services
- [ ] Check for table names that might include old service names
- [ ] Verify no stored procedures reference old names

### 5.2 Stored Data

#### ☐ Check if any stored data contains service URLs
- [ ] Review any callback URL storage
- [ ] Check webhook URL configurations
- [ ] Verify notification endpoints

---

## 📝 PHASE 6: Documentation Updates

### 6.1 Project Documentation

#### ☐ Update all markdown files
- [ ] PROGRESS.md - Update service name references
- [ ] DECISIONS.md - Document naming change decision
- [ ] BUGS.md - Update any bug reports with old names
- [ ] SECRET_CONFIG.md - Update service URL references
- [ ] CLAUDE.md - Update any service name references

### 6.2 Architecture Documentation

#### ☐ Create/Update architecture docs
- [ ] Document new naming convention
- [ ] Update service diagram (if exists)
- [ ] Create service mapping reference table

---

## 🧪 PHASE 7: Testing Plan

### 7.1 Pre-Deployment Verification

#### ☐ Static Analysis
- [ ] Grep for all old file names across entire PGP_v1 directory
- [ ] Verify no `import` statements reference old files
- [ ] Confirm all Dockerfiles updated
- [ ] Verify all deployment scripts updated

### 7.2 Build Testing

#### ☐ Docker Build Tests (DO NOT DEPLOY YET)
- [ ] Test build PGP_ACCUMULATOR_v1
- [ ] Test build PGP_BATCHPROCESSOR_v1
- [ ] Test build PGP_BROADCAST_v1
- [ ] Test build PGP_HOSTPAY1_v1
- [ ] Test build PGP_HOSTPAY2_v1
- [ ] Test build PGP_HOSTPAY3_v1
- [ ] Test build PGP_INVITE_v1
- [ ] Test build PGP_MICROBATCHPROCESSOR_v1
- [ ] Test build PGP_NOTIFICATIONS_v1
- [ ] Test build PGP_NP_IPN_v1
- [ ] Test build PGP_ORCHESTRATOR_v1
- [ ] Test build PGP_SERVER_v1
- [ ] Test build PGP_SPLIT1_v1
- [ ] Test build PGP_SPLIT2_v1
- [ ] Test build PGP_SPLIT3_v1
- [ ] Test build PGP_WEBAPI_v1
- [ ] Test build PGP_WEB_v1

### 7.3 Integration Testing Plan

#### ☐ Service Communication Paths
- [ ] Map out all service-to-service communication
- [ ] Document webhook endpoints
- [ ] Document Cloud Tasks queue flows
- [ ] Create integration test plan

---

## 🚨 CRITICAL DECISIONS NEEDED

### Decision 1: Cloud Run Service Names
**Question:** What should the new Google Cloud Run service names be?

**Options:**
- A) `pgp-server-v1`, `pgp-orchestrator-v1`, etc. (matches folder names)
- B) `pgp_server-server-v1`, `pgp_server-orchestrator-v1`, etc. (keeps pgp_server prefix)
- C) Something else?

**Current Status:** ⏳ AWAITING DECISION

### Decision 2: Cloud Tasks Queue Names
**Question:** Should queue names also be updated to match new naming scheme?

**Current Status:** ⏳ AWAITING DECISION

### Decision 3: Service URL Secret Names
**Question:** Should we create new secrets for new service URLs or update existing ones?

**Current Status:** ⏳ AWAITING DECISION

---

## ✅ FINAL CHECKLIST BEFORE DEPLOYMENT

- [ ] All Dockerfiles updated and tested
- [ ] All deployment scripts updated
- [ ] All cross-service references updated
- [ ] All Cloud Run service names decided and documented
- [ ] All secrets updated/created
- [ ] Documentation updated
- [ ] Integration test plan created
- [ ] Rollback plan documented
- [ ] Team notified of changes
- [ ] User approval obtained for service name changes

---

## 📅 Timeline

**Phase 1-6:** Pre-deployment updates and testing
**Phase 7:** Deployment execution (REQUIRES USER APPROVAL)

---

## 🔄 Rollback Plan

In case of issues:
1. Git revert to previous commit
2. Redeploy old service names
3. Restore old configurations
4. Update documentation

---

**Last Updated:** 2025-11-15
**Status:** ⏳ Awaiting critical decisions before proceeding
