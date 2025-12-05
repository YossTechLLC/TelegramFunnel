# Architectural Decisions - TelegramFunnel NOVEMBER/PGP_v1

**Last Updated:** 2025-11-19 - **🚀 Complete Deployment Automation Architecture** ✅

This document records all significant architectural decisions made during the development of the TelegramFunnel payment system.

---

## Recent Decisions

## 2025-11-19: Complete Deployment Automation - Master Orchestration Architecture ✅

### Decision 19.1: Master Orchestration Script with Checkpoint Resume
**Context:** Need single command to deploy entire PGP_v1 infrastructure (15 services + database + queues + scheduler + webhooks + monitoring)
**Decision:** Create `deploy_pgp_infrastructure.sh` orchestrating 12 deployment phases with checkpoint-based resume capability
**Rationale:**
- **Single Entry Point**: One script to deploy everything (reduces operator error)
- **Dependency Management**: Phases execute in correct order (e.g., Secrets before Cloud Run)
- **Checkpoint Resume**: Failed deployments can resume from last successful phase (no need to start over)
- **Phase Flexibility**: --start-phase, --end-phase, --skip-phase flags allow selective execution
- **Rollback Points**: Clear phases provide natural rollback boundaries
**Implementation:**
```bash
# 12 Deployment Phases:
Phase 1: GCP Project Setup (APIs, Service Accounts, IAM)
Phase 2: Secret Manager (6 sub-scripts, 75+ secrets)
Phase 3: Cloud SQL (PostgreSQL instance + schema)
Phase 4: Redis (Cloud Memorystore for nonce tracking)
Phase 5: Cloud Tasks (17 async queues)
Phase 6: Cloud Run (15 microservices + URL updates + verification)
Phase 7: Cloud Scheduler (3 CRON jobs)
Phase 8: Webhooks (NOWPayments, Telegram)
Phase 9: Load Balancer (Cloud Armor + SSL)
Phase 10: Monitoring (Cloud Logging + alerting - manual)
Phase 11: Integration Testing (end-to-end validation)
Phase 12: Production Hardening (security review - manual)
```
**Trade-offs:**
- ✅ **Single Command Deployment**: `./deploy_pgp_infrastructure.sh` deploys everything
- ✅ **Resume Capability**: Failed deployment at Phase 7? Resume with `--start-phase 7`
- ✅ **Selective Deployment**: Already have database? Skip with `--skip-phase 3`
- ✅ **Clear Dependencies**: Can't deploy Cloud Run before Secrets exist (enforced)
- ⚠️ **Complexity**: 700+ line script (necessary for comprehensive orchestration)
- ⚠️ **Long Execution Time**: Full deployment takes 30-45 minutes (acceptable for infrastructure)
**Alternative Rejected:** Multiple independent scripts with manual coordination (error-prone, no resume capability)

### Decision 19.2: Auto-Discovery Pattern for Service URLs and Queue Names
**Context:** After deploying Cloud Run services, need to update Secret Manager with actual service URLs
**Decision:** Create `update_service_urls_to_secrets.sh` that auto-discovers deployed services and updates secrets
**Rationale:**
- **Eliminates Manual Errors**: No copy-paste of URLs from console to Secret Manager
- **Idempotent**: Can be run multiple times (updates existing secrets)
- **Verification**: Compares secret values to actual deployed URLs (catch drift)
- **Automation**: Single command updates all 15 service URL secrets
**Pattern:**
```bash
# For each service:
1. Query: gcloud run services describe SERVICE --format="value(status.url)"
2. Update: echo -n "$URL" | gcloud secrets versions add SECRET_NAME --data-file=-
3. Verify: Compare secret value to actual service URL
```
**Trade-offs:**
- ✅ **Zero Manual Work**: URLs automatically fetched and stored
- ✅ **Always Accurate**: URLs match actual deployed services
- ✅ **Drift Detection**: Verification catches mismatches
- ⚠️ **Requires Deployment First**: Can't run before Cloud Run services exist (acceptable - enforced by orchestrator)
**Integration:** Called automatically by deploy_pgp_infrastructure.sh in Phase 6

### Decision 19.3: Comprehensive Service Verification with Health Checks
**Context:** After deployment, need to verify all 15 services are healthy and correctly configured
**Decision:** Create `verify_all_services.sh` with health endpoint testing and config validation
**Rationale:**
- **Automated Verification**: No manual checking of 15 services
- **Health Endpoint Testing**: Validates services respond to /health with authentication
- **Config Validation**: Verifies memory, min/max instances, timeout match expected values
- **Queue/Scheduler Validation**: Confirms all 17 queues and 3 CRON jobs exist
- **Early Detection**: Catches misconfigurations before they cause production issues
**Modes:**
- **Quick Mode**: Status checks only (fast, for monitoring)
- **Full Mode**: Health checks + config validation (comprehensive, for post-deployment)
**Trade-offs:**
- ✅ **Deployment Confidence**: Know immediately if something is wrong
- ✅ **Configuration Drift Detection**: Catches manual changes to services
- ✅ **Queue/Scheduler Validation**: Ensures async infrastructure exists
- ⚠️ **Execution Time**: Full mode takes 2-3 minutes (acceptable for comprehensive validation)
**Integration:** Called automatically by deploy_pgp_infrastructure.sh in Phase 6

### Decision 19.4: Integration Testing Architecture with 10 Test Suites
**Context:** Need automated testing to validate entire system works end-to-end
**Decision:** Create `test_end_to_end.sh` with 10 test suites covering all payment/payout flows
**Rationale:**
- **Complete Coverage**: Tests all critical paths (payment flow, payout pipeline, notifications, broadcasts)
- **Automated Validation**: No manual testing required
- **Regression Prevention**: Catch breaking changes before production
- **Documentation**: Test suites serve as executable documentation of system behavior
**Test Suites:**
```
1. Health Checks: All 15 services responding
2. Payment Flow: NP IPN → Orchestrator → Split1/2/3 → HostPay1/2/3
3. Payout Pipeline: HostPay 3-stage pipeline
4. Batch Processing: Batch and micro-batch processors
5. Notification System: Telegram notifications
6. Broadcast System: Scheduled broadcasts
7. Database Operations: Connection and schema validation
8. Secret Manager: Access and hot-reload testing
9. Cloud Tasks: Queue existence (17 queues)
10. Cloud Scheduler: CRON job existence (3 jobs)
```
**Trade-offs:**
- ✅ **High Confidence**: All flows validated before declaring success
- ✅ **Catch Integration Issues**: Service A works, Service B works, but A→B fails? Test catches it
- ✅ **Quick Mode Available**: Smoke tests only (fast) vs full integration (comprehensive)
- ⚠️ **Test Data Cleanup**: Requires cleanup after tests (automated with --skip-cleanup option)
**Integration:** Called by deploy_pgp_infrastructure.sh in Phase 11 (optional)

### Decision 19.5: Fix Critical Project ID Bug in Existing Script
**Context:** `deploy_all_pgp_services.sh` had wrong project ID (telepay-459221 instead of pgp-live)
**Decision:** Fix project ID immediately before creating new scripts (prevent deploying to wrong project)
**Rationale:**
- **Correctness**: Would have deployed to WRONG GCP project without fix
- **Cost**: Deploying 15 services to wrong project = wasted resources
- **Security**: Services in wrong project don't have correct IAM/secrets
- **Data Isolation**: telepay-459221 and pgp-live must remain completely separate
**Changes:**
```bash
# OLD (WRONG):
PROJECT_ID="${GCP_PROJECT_ID:-telepay-459221}"
CLOUD_SQL_INSTANCE="telepay-459221:us-central1:telepaypsql"

# NEW (CORRECT):
PROJECT_ID="${GCP_PROJECT_ID:-pgp-live}"
CLOUD_SQL_INSTANCE="pgp-live:us-central1:pgp-live-psql"
```
**Trade-offs:**
- ✅ **Correctness**: Services deploy to correct project
- ✅ **Data Isolation**: Legacy telepay-459221 untouched
- ✅ **Security**: Correct IAM/secrets per project
- ⚠️ **Breaking Change**: Script no longer deploys to telepay-459221 (intentional - deprecated project)
**Impact:** Would have been catastrophic if not caught (entire deployment to wrong project)

### Decision 19.6: Deployment Script Organization Strategy
**Context:** 21 scripts across multiple directories with unclear organization
**Decision:** Consolidate all deployment automation in `/TOOLS_SCRIPTS_TESTS/DEPLOYMENT/` directory
**Rationale:**
- **Organization**: Separates deployment (automation) from migrations (SQL) from scripts (utilities)
- **Discovery**: All deployment scripts in one place
- **Purpose Clarity**: DEPLOYMENT/ = production deployment automation only
- **Consistency**: Aligns with existing /scripts/, /tools/, /migrations/ structure
**Directory Structure:**
```
/TOOLS_SCRIPTS_TESTS/
  /DEPLOYMENT/              # NEW - Production deployment automation
    deploy_pgp_infrastructure.sh    # Master orchestrator
    deploy_cloud_scheduler_jobs.sh  # CRON jobs
    deploy_cloud_tasks_queues.sh    # Async queues
    deploy_webhook_configuration.sh # External webhooks
    pgp-live-psql-deployment.sh     # Database deployment
    update_service_urls_to_secrets.sh # Auto-discovery
    verify_all_services.sh          # Verification
    test_end_to_end.sh              # Integration testing
  /scripts/                 # Utility scripts (secret creation, etc.)
  /migrations/              # SQL schema migrations
  /tools/                   # One-off tools/utilities
```
**Trade-offs:**
- ✅ **Clear Separation**: Deployment vs migration vs utility scripts
- ✅ **Easy Discovery**: All automation in one directory
- ✅ **Scalable**: Room for future deployment scripts
- ⚠️ **Migration Required**: Moved pgp-live-psql-deployment.sh to DEPLOYMENT/ (acceptable)
**Alternative Rejected:** Keep scripts scattered across multiple directories (confusing, hard to find)

### Decision 19.7: Dry-Run Mode as Standard Feature
**Context:** All deployment scripts have potential for destructive operations
**Decision:** Implement --dry-run mode in all 4 new scripts (mandatory feature)
**Rationale:**
- **Safety**: Preview all actions before execution (prevent mistakes)
- **Validation**: Test script logic without making changes
- **Documentation**: Dry-run output serves as executable documentation
- **Confidence**: Operators can verify actions before committing
**Implementation:**
```bash
# All scripts support:
./script.sh --dry-run  # Preview only
./script.sh            # Execute

# Example output:
[DRY-RUN] Would create Cloud Run service: pgp-server-v1
[DRY-RUN] Would update secret: PGP_SERVER_URL
[DRY-RUN] Would verify health endpoint: https://pgp-server-v1-....run.app/health
```
**Trade-offs:**
- ✅ **Safety**: No surprises (see exactly what will happen)
- ✅ **Testing**: Validate logic before execution
- ✅ **Training**: New operators can learn by dry-running
- ⚠️ **Implementation Overhead**: Every command needs dry-run check (acceptable - safety critical)
**Standard Pattern:** All future deployment scripts must implement --dry-run mode

### Decision 19.8: Color-Coded Output for Operational Clarity
**Context:** Long-running deployment scripts need clear visual feedback
**Decision:** Standardize on color-coded output across all deployment scripts
**Rationale:**
- **Visual Clarity**: Quickly identify success (green) vs errors (red) vs warnings (yellow)
- **Operational Efficiency**: Operators can scan output quickly
- **Consistency**: Same colors mean same things across all scripts
- **Accessibility**: Colors improve but don't replace text (e.g., "✅ Success" not just green)
**Color Standard:**
```bash
GREEN   - Success, completion (✅)
RED     - Error, failure (❌)
YELLOW  - Warning, attention needed (⚠️)
BLUE    - Info, section headers (📍)
CYAN    - Steps, progress (⏳)
MAGENTA - Critical, important (🔥)
```
**Trade-offs:**
- ✅ **Better UX**: Easier to read long outputs
- ✅ **Faster Troubleshooting**: Errors stand out visually
- ✅ **Consistent Experience**: All scripts look/feel similar
- ⚠️ **Terminal Compatibility**: Some terminals don't support colors (degrades gracefully to text)
**Alternative Rejected:** Plain text only (harder to scan, no visual hierarchy)

### Decision 19.9: Checkpoint File Format and Location
**Context:** deploy_pgp_infrastructure.sh needs to track completed phases for resume capability
**Decision:** Use simple text file in /tmp with last completed phase number
**Rationale:**
- **Simplicity**: Single number in text file (easy to read/write)
- **Portability**: Works on all Unix systems
- **Debugging**: Human-readable (can inspect/modify manually)
- **Cleanup**: /tmp automatically cleaned on reboot
**Format:**
```bash
# File: /tmp/pgp_deployment_checkpoint_TIMESTAMP.txt
# Contents: "6" (last completed phase)
# Resume: --start-phase 7 (next phase)
```
**Trade-offs:**
- ✅ **Simple Implementation**: Read/write with echo/cat
- ✅ **Human-Readable**: Operators can inspect
- ✅ **Manual Override**: Can edit checkpoint to force resume from specific phase
- ⚠️ **Not Persistent**: /tmp cleared on reboot (acceptable - redeploy if system reboots)
- ⚠️ **No Concurrency Protection**: Two simultaneous runs = conflict (acceptable - operator error)
**Alternative Rejected:** JSON state file with detailed phase tracking (over-engineered for this use case)

---

## 2025-11-18: Secret Manager Phased Deployment Architecture ✅

### Decision 18.4: Phased Secret Deployment with Hot-Reload Classification
**Context:** 69 secrets required for PGP_v1 deployment to pgp-live project with complex dependencies
**Decision:** Create 6-phase deployment scripts with auto-discovery for dynamic secrets (URLs, queues)
**Rationale:**
- **Dependency Management:** Some secrets depend on infrastructure being deployed first
  - Service URLs require Cloud Run services deployed
  - Queue names require Cloud Tasks queues created
- **Hot-Reload Strategy:** 51 secrets can be rotated without service restart (74%)
  - BaseConfigManager implements fetch_secret_dynamic() with 60-second TTL cache
  - Static secrets (18) require service restart due to connection pools or token invalidation
- **Security Tiers:** Different secrets have different criticality levels
  - Ultra-Critical: HOST_WALLET_PRIVATE_KEY (controls all funds)
  - Critical: Database, signing keys, IPN secrets (12)
  - High/Medium/Low: Service URLs, config values (56)
- **Auto-Discovery:** Phase 5-6 scripts query GCP to get actual deployed values
  - Eliminates manual URL/queue name entry errors
  - Ensures exact match between deployed infrastructure and secrets

**Implementation:**

**Phase 1: Infrastructure (9 secrets)**
- Database: CLOUD_SQL_CONNECTION_NAME, DATABASE_NAME_SECRET, DATABASE_USER_SECRET, DATABASE_PASSWORD_SECRET
- Cloud Tasks: CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION
- Redis: PGP_REDIS_HOST, PGP_REDIS_PORT
- Auto-generates 64-char hex password

**Phase 2: Security (10 secrets)**
- Generates 5 signing keys (SUCCESS_URL, TPS_HOSTPAY, JWT, SIGNUP, PGP_INTERNAL)
- Wallet: HOST_WALLET_PRIVATE_KEY (hidden input), ETH/USDT addresses
- Webhooks: NOWPAYMENTS_IPN_SECRET, TELEGRAM_BOT_API_TOKEN
- Format validation: hex64, eth_address

**Phase 3: External APIs (5 secrets)**
- NOWPAYMENTS_API_KEY, CHANGENOW_API_KEY, SENDGRID_API_KEY
- ETHEREUM_RPC_URL, ETHEREUM_RPC_URL_API
- All hot-reloadable

**Phase 4: Application Config (12 secrets)**
- Web/Email: BASE_URL, CORS_ORIGIN, FROM_EMAIL, FROM_NAME
- Payment: TP_FLAT_FEE, PAYMENT_MIN_TOLERANCE, PAYMENT_FALLBACK_TOLERANCE
- Thresholds: MICRO_BATCH_THRESHOLD_USD
- Broadcast: BROADCAST_AUTO_INTERVAL, BROADCAST_MANUAL_INTERVAL
- All hot-reloadable

**Phase 5: Service URLs (14 secrets - AUTO-DISCOVERED)**
- gcloud run services list → PGP_*_URL secrets
- Prerequisite: Cloud Run services deployed
- Pattern: https://pgp-{service}-v1-{PROJECT_NUM}.us-central1.run.app

**Phase 6: Queue Names (16 secrets - AUTO-DISCOVERED)**
- gcloud tasks queues list → PGP_*_QUEUE secrets
- Prerequisite: Cloud Tasks queues created
- Pattern: pgp-{component}-{purpose}-queue-v1

**Trade-offs:**
- ✅ **Phased Deployment** - Clear dependencies, can't create Phase 5 before services exist
- ✅ **Auto-Discovery** - Eliminates manual errors in URLs/queue names
- ✅ **Hot-Reload Classification** - Explicit documentation of which secrets can rotate without restart
- ✅ **Security Validation** - Format checks (hex64, URLs, addresses) prevent invalid secrets
- ✅ **Skip Existing** - Idempotent scripts detect existing secrets
- ⚠️ **6-Step Process** - More complex than single script, but safer and more maintainable
- ⚠️ **Phase Dependencies** - Must follow order: 1-4, deploy services, 5, deploy queues, 6

**Alignment with BaseConfigManager:**
- Hot-reloadable secrets use fetch_secret_dynamic() (60s TTL cache)
- Static secrets use one-time fetch at service startup
- Pattern: build_secret_path(secret_name) + fetch_secret_dynamic()
- Matches implementation in PGP_COMMON/config/base_config.py:184-222

**Utility Scripts:**
- **grant_pgp_live_secret_access.sh:** Auto-discovers all secrets, grants IAM to service account
- **verify_pgp_live_secrets.sh:** Comprehensive validation of existence and format
- **README_SECRET_DEPLOYMENT.md:** Complete deployment guide with troubleshooting

**Alternatives Considered:**
1. **Single Monolithic Script:** Rejected - can't handle phase dependencies, error-prone
2. **Manual Secret Creation:** Rejected - 69 secrets too many, high error rate
3. **Terraform/IaC:** Considered but rejected for now - scripts provide more control and validation

**Next Steps:**
- Run Phase 1-4 scripts (infrastructure, security, APIs, config)
- Deploy Cloud Run services
- Run Phase 5 (auto-discover service URLs)
- Deploy Cloud Tasks queues
- Run Phase 6 (auto-discover queue names)
- Grant IAM permissions
- Verify all 69 secrets

---

## 2025-11-18: Production Deployment Scripts (Cloud Scheduler, Tasks, Webhooks) ✅

### Decision 18.3: Cloud Scheduler Job Configuration
**Context:** Automated batch processing requires scheduled CRON jobs for 3 services
**Decision:** Create deploy_cloud_scheduler_jobs.sh with OIDC authentication and timezone support
**Rationale:**
- **Batch Processing:** pgp-batchprocessor-v1 needs frequent execution (every 5 min)
- **Micro-Batch:** pgp-microbatchprocessor-v1 processes smaller amounts (every 15 min)
- **Broadcasts:** pgp-broadcast-v1 sends daily scheduled messages (9 AM UTC)
- **OIDC Auth:** Service accounts authenticate scheduler → Cloud Run (no API keys)
**Implementation:**
- Schedule: CRON syntax (*/5 * * * *, */15 * * * *, 0 9 * * *)
- Timezone: America/New_York (EST/EDT - user preference)
- Method: HTTP POST to /process endpoints
- Auth: --oidc-service-account-email for each service
**Trade-offs:**
- ✅ OIDC authentication (no exposed API keys)
- ✅ Dry-run mode (safe testing)
- ✅ Update existing jobs (idempotent)
- ⚠️ Requires service deployment first (dependency)
**Alternative Rejected:** Cloud Pub/Sub triggers (more complex, no scheduling)

### Decision 18.4: Cloud Tasks Queue Configuration
**Context:** 15 async queues needed for payment processing pipeline
**Decision:** Infinite retry (max-attempts=0) with exponential backoff
**Rationale:**
- **Resilience:** Payment processing must never drop tasks
- **Money Movement:** Split/HostPay pipelines handle real money (zero tolerance for loss)
- **ChangeNOW API:** External API may be temporarily unavailable (retry needed)
- **Backoff:** 1s → 60s exponential prevents API rate limit violations
**Implementation:**
- max-attempts: 0 (infinite retry)
- max-retry-duration: 0 (never give up)
- min-backoff: 1s (fast initial retry)
- max-backoff: 60s (reasonable ceiling)
- max-doublings: 16 (exponential growth)
- max-concurrent-dispatches: 100 (high throughput)
**Trade-offs:**
- ✅ Zero task loss (guaranteed delivery)
- ✅ Handles transient failures (API timeouts, network issues)
- ✅ Prevents rate limit violations (backoff)
- ⚠️ Poison pill tasks may retry forever (requires dead-letter queue monitoring)
**Alternative Rejected:** max-attempts=10 (finite retry - risks losing payment tasks)

### Decision 18.5: Webhook Configuration Approach
**Context:** External webhooks require manual configuration (NOWPayments, Telegram, Cloudflare)
**Decision:** Semi-automated script with manual steps + verification
**Rationale:**
- **NOWPayments:** IPN dashboard requires manual URL update (no API)
- **Telegram:** Supports both polling (default) and webhook (optional)
- **Cloudflare:** DNS records require manual setup (per CLAUDE.md restrictions)
- **Verification:** Script tests endpoint accessibility and secret validation
**Implementation:**
- NOWPayments: Provide instructions + verify secret in Secret Manager
- Telegram: Optional --telegram-webhook flag (default: polling)
- Cloudflare: Documentation only (not deployed)
- Verification: curl health checks + connectivity tests
**Trade-offs:**
- ✅ Safe hybrid approach (automation + human verification)
- ✅ Telegram flexibility (polling for dev, webhook for prod)
- ✅ Cloudflare compliance (no automated DNS changes)
- ⚠️ Manual steps required (NOWPayments dashboard)
**Alternative Rejected:** Fully automated (violates CLAUDE.md restrictions, lacks human verification)

### Decision 18.6: Deployment Script Patterns
**Context:** Need consistent patterns across all 3 deployment scripts
**Decision:** Standardize on dry-run, validation, color-coded output, error handling
**Rationale:**
- **Dry-Run:** User can preview all actions before execution (safety)
- **Validation:** Check prerequisites (gcloud, APIs, IAM) before deployment
- **Colors:** Green (success), Red (error), Yellow (warning) improve UX
- **Error Handling:** set -e (exit on error) prevents partial deployments
**Implementation:**
- Bash: set -e, set -u (strict mode)
- Functions: print_header, print_success, print_error, execute_cmd
- Flags: --dry-run, --project, --location
- Logs: Save deployment metadata to /tmp for audit trail
**Trade-offs:**
- ✅ Consistent UX across all scripts
- ✅ Safe testing with dry-run
- ✅ Clear error messages (troubleshooting)
- ⚠️ Verbose scripts (585-644 lines each)
**Alternative Rejected:** Minimal scripts (less safe, harder to debug)

## 2025-11-18: PGP-LIVE Complete Deployment Script ✅

### Decision 18.1: End-to-End Deployment Automation
**Context:** Need automated deployment for pgp-live-psql Cloud SQL instance and pgp-live-db database
**Decision:** Create comprehensive bash script (pgp-live-psql-deployment.sh) with 5-phase deployment
**Rationale:**
- **Automation:** Manual deployment error-prone (50+ steps)
- **Reproducibility:** Consistent deployment across environments
- **Documentation:** Script serves as executable documentation
- **Safety:** Dry-run mode allows preview before execution
**Implementation:**
- Phase 1: Cloud SQL instance creation (pgp-live-psql)
- Phase 2: Database creation (pgp-live-db)
- Phase 3: Schema deployment (13 tables, 4 ENUMs, 50+ indexes)
- Phase 4: Currency data population (87 entries)
- Phase 5: Deployment verification (automated checks)
**Trade-offs:**
- ✅ Automated deployment (reduces human error)
- ✅ Dry-run mode (safe preview)
- ✅ Embedded Python scripts (no external dependencies)
- ✅ Verification phase (ensures successful deployment)
- ⚠️ Complex script (850+ lines, requires review)
- ⚠️ Bash + Python mix (necessary for Cloud SQL Connector)
**Alternative Rejected:** Manual deployment via gcloud commands (error-prone, not reproducible, no verification)

### Decision 18.2: Greenfield Deployment (No Data Migration)
**Context:** Script must deploy empty database for pgp-live project
**Decision:** Greenfield deployment with zero data migration from telepay-459221
**Rationale:**
- **New Project:** pgp-live is separate production environment
- **Dual Operation:** Legacy telepay-459221 continues independently
- **Safety:** Eliminates data migration risks
- **Clean Start:** Fresh database for new production deployment
**Implementation:**
- Empty database creation (pgp-live-db)
- Schema-only deployment (tables, indexes, constraints)
- Reference data only (87 currency_to_network entries)
- Legacy user placeholder (UUID 00000000-0000-0000-0000-000000000000)
**Trade-offs:**
- ✅ Zero migration risk (no data transfer)
- ✅ Clean production start (no legacy data issues)
- ✅ Dual system operation (telepaydb unaffected)
- ⚠️ No historical data (acceptable - new project)
**Alternative Rejected:** Data migration from telepaydb (complex, risky, unnecessary for new project)

### Decision 18.3: Excluded Deprecated Tables
**Context:** Original schema has 15 tables, but 2 are deprecated
**Decision:** Exclude user_conversation_state and donation_keypad_state from deployment
**Rationale:**
- **Deprecated:** Tables used by old bot architecture (no longer needed)
- **Code Cleanup:** PGP_v1 services don't reference these tables
- **Schema Clarity:** Deploy only operational tables
- **Maintenance:** Reduces schema complexity
**Implementation:**
- Deploy 13 operational tables only
- Exclude user_conversation_state (deprecated bot conversation state)
- Exclude donation_keypad_state (deprecated donation UI state)
- Use 001_pgp_live_complete_schema.sql (already excludes deprecated tables)
**Trade-offs:**
- ✅ Cleaner schema (only operational tables)
- ✅ Reduced complexity (13 tables instead of 15)
- ✅ Code alignment (matches PGP_v1 service usage)
- ⚠️ Irreversible (deprecated tables not deployed, can't recover data)
**Alternative Rejected:** Deploy all 15 tables (includes unused deprecated tables, adds unnecessary complexity)

### Decision 18.4: Secret Manager Integration
**Context:** Database credentials must be stored securely
**Decision:** Store all credentials in Secret Manager (PGP_LIVE_DATABASE_USER/PASSWORD/NAME_SECRET)
**Rationale:**
- **Security:** No hardcoded credentials in script or config
- **Rotation:** Easy credential rotation without code changes
- **Audit:** Secret Manager provides access audit logs
- **Integration:** All PGP_v1 services use Secret Manager
**Implementation:**
- PGP_LIVE_DATABASE_USER_SECRET: postgres
- PGP_LIVE_DATABASE_PASSWORD_SECRET: 32-byte random password
- PGP_LIVE_DATABASE_NAME_SECRET: pgp-live-db
- Auto-creation if secrets don't exist
- Auto-update if secrets already exist
