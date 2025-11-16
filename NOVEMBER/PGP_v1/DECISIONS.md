# DECISIONS

## 2025-11-16 - PayGatePrime v1 Migration Architecture

### Individual Service Deployment Scripts
- **Decision:** Create individual deployment scripts for each of 15 services
- **Location:** `deployment_scripts/individual_services/`
- **Rationale:**
  - Granular control for debugging specific services
  - Ability to deploy/redeploy single services without affecting others
  - Easier troubleshooting with service-specific configurations
  - Better documentation with per-service next steps
- **Scripts Created:** 16 total (15 individual + 1 master orchestration)
- **Master Script:** `deploy_all_services.sh` orchestrates deployment in correct order
- **Benefits:**
  - Deploy all at once OR one at a time
  - Each script self-contained with all required secrets
  - Service-specific resource allocation (memory, CPU, timeout)
  - Clear authentication settings (public vs internal)
  - Automatic URL secret updates after each phase

### Project Migration Strategy
- **Decision:** Migrate from `telepay-459221` to new `pgp-live` GCP project
- **Rationale:** Fresh start for PayGatePrime v1 with clean project structure
- **Impact:** All 14 services, 46 secrets, and database instance must be recreated

### Service Naming Convention
- **Decision:** Remove `-10-26` suffix from service names
- **New Pattern:** `GCRegisterAPI-PGP`, `GCWebhook1-PGP`, etc.
- **Rationale:** Date-based naming is confusing; use product-based naming

### Database Instance Naming
- **Decision:** Suggest new instance name `pgp-psql` (vs old `telepaypsql`)
- **Connection Format:** `pgp-live:us-central1:pgp-psql`
- **Database Name:** Consider `pgpdb` (vs old `telepaydb`)

### Secret Management Approach
- **Decision:** All secrets managed via GCP Secret Manager (no .env files)
- **Total Secrets:** 46 secrets documented
- **Priority Tiers:** Critical (🔴), High (🟡), Medium (🟢)

### Code Migration Methodology
- **Decision:** Systematic 8-phase approach via MIGRATION_CHECKLIST.md
- **Sequence:** Discovery → Copy → Update → Verify → Document
- **No Deployment:** Code preparation only; deployment handled separately

### Documentation Structure
- **Created:** MIGRATION_CHECKLIST.md (master plan)
- **Created:** SECRET_CONFIG_UPDATE.md (46 secrets catalog)
- **Created:** DISCOVERY_REPORT.md (analysis findings)
- **Approach:** Separate concerns for clarity and reference
