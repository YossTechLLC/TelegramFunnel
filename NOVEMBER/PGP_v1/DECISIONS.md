# DECISIONS

## 2025-11-16 - PayGatePrime v1 Migration Architecture

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
