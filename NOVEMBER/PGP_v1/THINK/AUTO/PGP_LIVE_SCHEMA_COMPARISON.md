# PayGatePrime Schema Comparison: telepay-459221 vs pgp-live

**Generated:** 2025-11-18
**Purpose:** Document differences between original and new database schemas

---

## Executive Summary

The pgp-live database schema is a **streamlined version** of the original telepay-459221 schema, removing deprecated state management tables while maintaining all core operational functionality.

| Metric | Original (telepay-459221) | New (pgp-live) | Change |
|--------|---------------------------|----------------|---------|
| **Tables** | 15 | 13 | -2 (❌ Excluded deprecated) |
| **ENUM Types** | 4 | 4 | ✅ Same |
| **Sequences** | 5 | 5 | ✅ Same |
| **Foreign Keys** | 3 | 3 | ✅ Same |
| **Indexes** | 60+ | 60+ | ✅ Same |
| **Project ID** | telepay-459221 | pgp-live | 🔄 Changed |
| **Instance** | telepay-459221:us-central1:telepaypsql | pgp-live:us-central1:pgp-telepaypsql | 🔄 Changed |
| **Database Name** | telepaydb | telepaydb | ✅ Same |
| **Code Reference** | client_table | pgp_live_db | 🔄 Changed |

---

## Tables Excluded (2)

### 1. donation_keypad_state ❌

**Original Structure:**
```sql
CREATE TABLE donation_keypad_state (
    user_id BIGINT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    current_amount TEXT NOT NULL DEFAULT '',
    decimal_entered BOOLEAN NOT NULL DEFAULT FALSE,
    state_type VARCHAR(20) NOT NULL DEFAULT 'keypad_input',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Reason for Exclusion:**
- Deprecated donation UI state management
- Part of old bot architecture (pre-PGP_v1)
- No longer needed with current donation flow
- Only 1 row in production database

**Impact:**
- ✅ No impact on core payment processing
- ✅ No impact on subscription management
- ✅ Donation functionality handled differently in PGP_v1

### 2. user_conversation_state ❌

**Original Structure:**
```sql
CREATE TABLE user_conversation_state (
    user_id BIGINT NOT NULL,
    conversation_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, conversation_type)
);
```

**Reason for Exclusion:**
- Generic bot conversation state manager
- Part of old stateful bot architecture
- Only 1 row in production database
- PGP_v1 services are stateless by design

**Impact:**
- ✅ No impact on payment processing
- ✅ No impact on subscription management
- ✅ State management handled in-memory or via other mechanisms

---

## Tables Retained (13)

All 13 core operational tables are **identical** between old and new schemas:

| # | Table Name | Status | Changes |
|---|------------|--------|---------|
| 1 | registered_users | ✅ Retained | None - Identical |
| 2 | main_clients_database | ✅ Retained | None - Identical |
| 3 | private_channel_users_database | ✅ Retained | None - Identical |
| 4 | processed_payments | ✅ Retained | None - Identical |
| 5 | batch_conversions | ✅ Retained | None - Identical |
| 6 | payout_accumulation | ✅ Retained | None - Identical |
| 7 | payout_batches | ✅ Retained | None - Identical |
| 8 | split_payout_request | ✅ Retained | None - Identical |
| 9 | split_payout_que | ✅ Retained | None - Identical |
| 10 | split_payout_hostpay | ✅ Retained | None - Identical |
| 11 | broadcast_manager | ✅ Retained | None - Identical |
| 12 | currency_to_network | ✅ Retained | None - Identical |
| 13 | failed_transactions | ✅ Retained | None - Identical |

**Key Point:** All table structures, constraints, indexes, and data types are **100% identical** between schemas. Only the deprecated tables were removed.

---

## Infrastructure Changes

### GCP Project Changes

| Component | Old Value | New Value |
|-----------|-----------|-----------|
| **Project ID** | telepay-459221 | pgp-live |
| **Cloud SQL Instance** | telepay-459221:us-central1:telepaypsql | pgp-live:us-central1:pgp-telepaypsql |
| **Region** | us-central1 | us-central1 (unchanged) |
| **Database Engine** | PostgreSQL | PostgreSQL (unchanged) |
| **Database Name** | telepaydb | telepaydb (unchanged) |

### Code Reference Changes

**Old Code:**
```python
# Service code referenced database as "client_table"
DATABASE_NAME = "client_table"
```

**New Code:**
```python
# Service code now references database as "pgp_live_db"
DATABASE_NAME = "pgp_live_db"
```

**Reason:** Improve naming consistency and clarity across codebase.

**Impact:** All PGP_*_v1 services need code updates to reference `pgp_live_db` instead of `client_table`.

---

## Service Name Mapping

Services using the database have been renamed for clarity:

| Old Name (GC) | New Name (PGP_v1) | Tables Used |
|---------------|-------------------|-------------|
| GCRegisterAPI-10-26 | PGP_SERVER_v1 | registered_users, main_clients_database |
| GCWebhook1-10-26 | PGP_ORCHESTRATOR_v1 | processed_payments, split_payout_request |
| GCWebhook2-10-26 | PGP_INVITE_v1 | processed_payments |
| GCBroadcastScheduler-10-26 | PGP_BROADCAST_v1 | broadcast_manager |
| GCAccumulator-10-26 | PGP_ACCUMULATOR_v1 | payout_accumulation |
| GCMicroBatchProcessor-10-26 | PGP_MICROBATCHPROCESSOR_v1 | batch_conversions, payout_batches |
| GCSplit1-10-26 | PGP_SPLIT1_v1 | split_payout_request, split_payout_que |
| GCSplit2-10-26 | PGP_SPLIT2_v1 | split_payout_que |
| GCHostPay1/2/3-10-26 | PGP_HOSTPAY1/2/3_v1 | split_payout_hostpay |
| GCSubscriptionMonitor-10-26 | PGP_MONITOR_v1 | private_channel_users_database |
| GCNotificationService-10-26 | PGP_NOTIFICATIONS_v1 | main_clients_database |

---

## Data Migration Implications

### No Data Loss

All operational data tables are retained:
- ✅ User accounts (registered_users)
- ✅ Channel configurations (main_clients_database)
- ✅ Subscriptions (private_channel_users_database)
- ✅ Payment history (processed_payments, payout_accumulation)
- ✅ Transaction records (split_payout_*, payout_batches)
- ✅ Error tracking (failed_transactions)

### Minimal Data Loss

Only deprecated state data is excluded:
- ❌ 1 row from donation_keypad_state
- ❌ 1 row from user_conversation_state

**Impact:** Negligible - these tables had minimal production usage.

### Migration Strategy

**Option 1: Fresh Start (Recommended for pgp-live)**
- Deploy clean schema to pgp-live
- No data migration from telepay-459221
- Services populate tables organically

**Option 2: Data Migration**
- Export data from telepay-459221
- Transform to pgp-live format (minimal changes needed)
- Import into pgp-live
- Skip deprecated tables

**Recommendation:** Option 1 (Fresh Start) for pgp-live, as this is a new production environment.

---

## Compatibility Matrix

### Backward Compatibility

| Component | Compatible? | Notes |
|-----------|-------------|-------|
| **SQL Queries** | ✅ Yes | All table structures identical |
| **Service Code** | ⚠️ Partial | Requires `client_table` → `pgp_live_db` rename |
| **Foreign Keys** | ✅ Yes | All relationships maintained |
| **Indexes** | ✅ Yes | All performance optimizations preserved |
| **Constraints** | ✅ Yes | All data validation rules maintained |

### Forward Compatibility

- ✅ Schema supports all current PGP_*_v1 services
- ✅ No breaking changes to service interfaces
- ✅ Future migrations can add tables without breaking existing services

---

## Verification Checklist

Use this checklist to verify schema equivalence:

### Structure Verification

- [ ] 13 tables exist in pgp-live (not 15)
- [ ] `donation_keypad_state` does NOT exist
- [ ] `user_conversation_state` does NOT exist
- [ ] All 13 retained tables have identical column definitions
- [ ] All 13 retained tables have identical constraints
- [ ] All 13 retained tables have identical indexes

### Data Type Verification

- [ ] 4 ENUM types exist: currency_type, network_type, flow_type, type_type
- [ ] 5 sequences exist for auto-increment columns
- [ ] UUID types used correctly (registered_users, broadcast_manager)
- [ ] TIMESTAMP vs TIMESTAMPTZ usage matches original

### Constraint Verification

- [ ] 3 foreign keys established correctly
- [ ] All CHECK constraints match original
- [ ] All UNIQUE constraints match original
- [ ] All NOT NULL constraints match original

### Index Verification

- [ ] 60+ indexes created
- [ ] Partial indexes created correctly (WHERE clauses)
- [ ] Composite indexes match original (multi-column)
- [ ] UNIQUE indexes enforce uniqueness

---

## Risk Assessment

### Low Risk ✅

- Table structure changes (None - all identical)
- Data loss (Minimal - only 2 deprecated tables)
- Service disruption (None - fresh deployment)
- Performance degradation (None - identical indexes)

### Medium Risk ⚠️

- Code reference updates (`client_table` → `pgp_live_db`)
  - **Mitigation:** Search and replace across all services before deployment
  - **Verification:** Unit tests confirm database connections work

### No Risk ❌

- Schema incompatibility (No risk - structures identical)
- Foreign key violations (No risk - relationships preserved)
- Index performance (No risk - identical optimization)

---

## Migration Timeline

### Pre-Deployment (Completed ✅)

- [x] Create migration SQL scripts
- [x] Create Python deployment tools
- [x] Create shell script wrappers
- [x] Create documentation
- [x] Review schema comparison

### Deployment (Awaiting User Approval 🛑)

- [ ] User reviews migration checklist
- [ ] User approves pgp-live deployment
- [ ] Run `deploy_pgp_live_schema.sh`
- [ ] Run `verify_pgp_live_schema.sh`
- [ ] Confirm all checks pass

### Post-Deployment

- [ ] Update service code references
- [ ] Deploy PGP_*_v1 services to pgp-live
- [ ] Test service-to-database connectivity
- [ ] Monitor for errors in first 24 hours

---

## Conclusion

The pgp-live database schema is a **production-ready, streamlined version** of the original schema with:

✅ **Identical operational tables** (13/13)
✅ **Identical constraints and indexes**
✅ **Identical data types and relationships**
❌ **Excluded deprecated state tables** (2/15)
🔄 **Updated naming conventions** (client_table → pgp_live_db)

The schema is ready for deployment once user approval is granted.

---

**End of Comparison Report**
**Status:** Complete
**Next Steps:** Await user approval for Phase 7 (deployment)
