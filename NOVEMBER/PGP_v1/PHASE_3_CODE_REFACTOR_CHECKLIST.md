# Phase 3: Code-Level Naming Refactor - Comprehensive Checklist

## Overview

**Objective:** Refactor function names, variable names, and database schema to align with PGP_v1 naming conventions.

**Scope:**
- Function/method names (API contracts between services)
- Internal variable names (implementation details)
- Database column names (schema changes requiring migration)

**Risk Level:** HIGH - Changes actual code logic, API contracts, and database schema

**Prerequisites:**
- ✅ Phase 2.6 Complete (all comments/docs updated)
- ✅ All services currently deployed and functional
- ✅ Full database backup created
- ✅ All tests passing

---

## Naming Transformation Map

### Variable Name Transformations

| Current Variable Name | New Variable Name | Services Affected |
|----------------------|-------------------|-------------------|
| `gcsplit1_queue` | `pgp_split1_queue` | ORCHESTRATOR, BATCHPROCESSOR |
| `gcsplit1_url` | `pgp_split1_url` | ORCHESTRATOR, BATCHPROCESSOR, SPLIT2, SPLIT3 |
| `gcsplit2_url` | `pgp_split2_url` | SPLIT1 |
| `gcsplit3_url` | `pgp_split3_url` | SPLIT1 |
| `gcsplit1_batch_queue` | `pgp_split1_batch_queue` | BATCHPROCESSOR |
| `gcwebhook1_url` | `pgp_orchestrator_url` | (if exists) |
| `gcwebhook2_url` | `pgp_invite_url` | ORCHESTRATOR |
| `gcwebhook2_queue` | `pgp_invite_queue` | ORCHESTRATOR |
| `gchostpay1_url` | `pgp_hostpay1_url` | HOSTPAY1, HOSTPAY2, HOSTPAY3, MICROBATCH, SPLIT1 |
| `gchostpay1_response_queue` | `pgp_hostpay1_response_queue` | HOSTPAY1, HOSTPAY2, HOSTPAY3 |
| `gchostpay1_batch_queue` | `pgp_hostpay1_batch_queue` | MICROBATCH |
| `gchostpay2_url` | `pgp_hostpay2_url` | HOSTPAY1, HOSTPAY2 |
| `gchostpay2_queue` | `pgp_hostpay2_queue` | HOSTPAY1 |
| `gchostpay2_response_queue` | `pgp_hostpay2_response_queue` | HOSTPAY2 |
| `gchostpay3_url` | `pgp_hostpay3_url` | HOSTPAY1, HOSTPAY3 |
| `gchostpay3_queue` | `pgp_hostpay3_queue` | HOSTPAY1 |
| `gchostpay3_retry_queue` | `pgp_hostpay3_retry_queue` | HOSTPAY3 |

### Function/Method Name Transformations

#### Token Manager Functions (Cross-Service API)

| Current Function Name | New Function Name | Defined In | Called From |
|----------------------|-------------------|------------|-------------|
| `encrypt_token_for_gcsplit2` | `encrypt_token_for_pgp_split2` | ACCUMULATOR | ACCUMULATOR |
| `encrypt_accumulator_to_gcsplit3_token` | `encrypt_accumulator_to_pgp_split3_token` | ACCUMULATOR | ACCUMULATOR |
| `encrypt_accumulator_to_gchostpay1_token` | `encrypt_accumulator_to_pgp_hostpay1_token` | ACCUMULATOR | ACCUMULATOR |
| `decrypt_accumulator_to_gchostpay1_token` | `decrypt_accumulator_to_pgp_hostpay1_token` | HOSTPAY1 | HOSTPAY1 |
| `encrypt_microbatch_to_gchostpay1_token` | `encrypt_microbatch_to_pgp_hostpay1_token` | MICROBATCH | MICROBATCH |
| `decrypt_microbatch_to_gchostpay1_token` | `decrypt_microbatch_to_pgp_hostpay1_token` | HOSTPAY1 | HOSTPAY1 |
| `encrypt_token_for_gcwebhook2` | `encrypt_token_for_pgp_invite` | ORCHESTRATOR | ORCHESTRATOR |
| `decrypt_gcsplit1_to_gchostpay1_token` | `decrypt_pgp_split1_to_pgp_hostpay1_token` | HOSTPAY1, HOSTPAY2, HOSTPAY3 | HOSTPAY1 |
| `encrypt_gchostpay1_to_gchostpay2_token` | `encrypt_pgp_hostpay1_to_pgp_hostpay2_token` | HOSTPAY1, HOSTPAY2, HOSTPAY3 | HOSTPAY1 |
| `decrypt_gchostpay1_to_gchostpay2_token` | `decrypt_pgp_hostpay1_to_pgp_hostpay2_token` | HOSTPAY2 | HOSTPAY2 |
| `encrypt_gchostpay2_to_gchostpay1_token` | `encrypt_pgp_hostpay2_to_pgp_hostpay1_token` | HOSTPAY2 | HOSTPAY2 |
| `decrypt_gchostpay2_to_gchostpay1_token` | `decrypt_pgp_hostpay2_to_pgp_hostpay1_token` | HOSTPAY1 | HOSTPAY1 |
| `encrypt_gchostpay1_to_gchostpay3_token` | `encrypt_pgp_hostpay1_to_pgp_hostpay3_token` | HOSTPAY1, HOSTPAY2, HOSTPAY3 | HOSTPAY1 |
| `decrypt_gchostpay1_to_gchostpay3_token` | `decrypt_pgp_hostpay1_to_pgp_hostpay3_token` | HOSTPAY3 | HOSTPAY3 |
| `encrypt_gchostpay3_to_gchostpay1_token` | `encrypt_pgp_hostpay3_to_pgp_hostpay1_token` | HOSTPAY3 | HOSTPAY3 |
| `decrypt_gchostpay3_to_gchostpay1_token` | `decrypt_pgp_hostpay3_to_pgp_hostpay1_token` | HOSTPAY1 | HOSTPAY1 |
| `encrypt_gchostpay3_retry_token` | `encrypt_pgp_hostpay3_retry_token` | HOSTPAY3 | HOSTPAY3 |

### Database Column Name Transformations

| Current Column Name | New Column Name | Table | Services Reading/Writing |
|--------------------|-----------------|-------|-------------------------|
| `gcwebhook1_processed` | `pgp_orchestrator_processed` | `processed_payments` | NP_IPN, ORCHESTRATOR |
| `gcwebhook1_processed_at` | `pgp_orchestrator_processed_at` | `processed_payments` | ORCHESTRATOR |

---

## Phase 3.1: Internal Variable Names (Low Risk)

**Risk:** LOW - Internal to each service, no cross-service dependencies
**Estimated Time:** 2-3 hours
**Files Affected:** ~15 Python files

### Implementation Steps

#### 3.1.1: Inventory Variable Occurrences

```bash
# Create inventory of all variable occurrences
grep -r "gcsplit1_queue\|gcsplit1_url\|gcsplit2_url\|gcsplit3_url" --include="*.py" PGP_*/
grep -r "gcwebhook1_url\|gcwebhook2_url\|gcwebhook2_queue" --include="*.py" PGP_*/
grep -r "gchostpay1_url\|gchostpay1_queue\|gchostpay1_response_queue\|gchostpay1_batch_queue" --include="*.py" PGP_*/
grep -r "gchostpay2_url\|gchostpay2_queue\|gchostpay2_response_queue" --include="*.py" PGP_*/
grep -r "gchostpay3_url\|gchostpay3_queue\|gchostpay3_retry_queue" --include="*.py" PGP_*/
```

**Expected Count:** ~100-150 occurrences

#### 3.1.2: Create Automated Replacement Script

Create `phase_3_1_variable_rename.py`:

```python
VARIABLE_REPLACEMENTS = [
    # Split variables
    ('gcsplit1_queue', 'pgp_split1_queue'),
    ('gcsplit1_url', 'pgp_split1_url'),
    ('gcsplit2_url', 'pgp_split2_url'),
    ('gcsplit3_url', 'pgp_split3_url'),
    ('gcsplit1_batch_queue', 'pgp_split1_batch_queue'),

    # Webhook/Orchestrator variables
    ('gcwebhook1_url', 'pgp_orchestrator_url'),
    ('gcwebhook2_url', 'pgp_invite_url'),
    ('gcwebhook2_queue', 'pgp_invite_queue'),

    # HostPay variables
    ('gchostpay1_url', 'pgp_hostpay1_url'),
    ('gchostpay1_queue', 'pgp_hostpay1_queue'),
    ('gchostpay1_response_queue', 'pgp_hostpay1_response_queue'),
    ('gchostpay1_batch_queue', 'pgp_hostpay1_batch_queue'),
    ('gchostpay2_url', 'pgp_hostpay2_url'),
    ('gchostpay2_queue', 'pgp_hostpay2_queue'),
    ('gchostpay2_response_queue', 'pgp_hostpay2_response_queue'),
    ('gchostpay3_url', 'pgp_hostpay3_url'),
    ('gchostpay3_queue', 'pgp_hostpay3_queue'),
    ('gchostpay3_retry_queue', 'pgp_hostpay3_retry_queue'),
]
```

#### 3.1.3: Verification Checklist

- [ ] Run script in dry-run mode
- [ ] Verify no false positives (e.g., in string literals that should remain unchanged)
- [ ] Check that environment variable names are NOT changed (only variable names in code)
- [ ] Verify Python syntax with `python -m py_compile` on all modified files

#### 3.1.4: Deployment Strategy

**Option A: All-at-once (Recommended for variables)**
- Variables are internal to each service
- No cross-service coordination needed
- Deploy all services simultaneously

**Option B: Service-by-service**
- Deploy one service at a time
- Test each deployment
- Slower but safer

---

## Phase 3.2: Function/Method Names (HIGH RISK)

**Risk:** HIGH - These are API contracts between services
**Estimated Time:** 6-8 hours
**Files Affected:** ~30 Python files across token_manager.py files

### Critical Dependencies Map

```
ACCUMULATOR.token_manager
├── encrypt_token_for_gcsplit2()
├── encrypt_accumulator_to_gcsplit3_token()
└── encrypt_accumulator_to_gchostpay1_token()
    └─> Called by: ACCUMULATOR.pgp_accumulator_v1.py

HOSTPAY1.token_manager
├── decrypt_accumulator_to_gchostpay1_token()  ← From ACCUMULATOR
├── decrypt_microbatch_to_gchostpay1_token()   ← From MICROBATCH
├── encrypt_gchostpay1_to_gchostpay2_token()
├── decrypt_gchostpay2_to_gchostpay1_token()   ← From HOSTPAY2
├── encrypt_gchostpay1_to_gchostpay3_token()
└── decrypt_gchostpay3_to_gchostpay1_token()   ← From HOSTPAY3

HOSTPAY2.token_manager
├── decrypt_gchostpay1_to_gchostpay2_token()   ← From HOSTPAY1
└── encrypt_gchostpay2_to_gchostpay1_token()

HOSTPAY3.token_manager
├── decrypt_gchostpay1_to_gchostpay3_token()   ← From HOSTPAY1
├── encrypt_gchostpay3_to_gchostpay1_token()
└── encrypt_gchostpay3_retry_token()

ORCHESTRATOR.token_manager
└── encrypt_token_for_gcwebhook2()
    └─> Called by: ORCHESTRATOR.pgp_orchestrator_v1.py
```

### Implementation Steps

#### 3.2.1: Map All Function Definitions and Call Sites

Create `function_call_map.py`:

```python
# For each function:
# - Where is it defined?
# - Where is it called?
# - What parameters does it take?
# - What does it return?
```

#### 3.2.2: Create Coordinated Replacement Script

**CRITICAL:** All renames must happen atomically within each service

```python
# phase_3_2_function_rename.py

FUNCTION_RENAMES = {
    'PGP_ACCUMULATOR_v1': [
        ('encrypt_token_for_gcsplit2', 'encrypt_token_for_pgp_split2'),
        ('encrypt_accumulator_to_gcsplit3_token', 'encrypt_accumulator_to_pgp_split3_token'),
        ('encrypt_accumulator_to_gchostpay1_token', 'encrypt_accumulator_to_pgp_hostpay1_token'),
    ],
    'PGP_HOSTPAY1_v1': [
        ('decrypt_accumulator_to_gchostpay1_token', 'decrypt_accumulator_to_pgp_hostpay1_token'),
        ('decrypt_microbatch_to_gchostpay1_token', 'decrypt_microbatch_to_pgp_hostpay1_token'),
        ('encrypt_gchostpay1_to_gchostpay2_token', 'encrypt_pgp_hostpay1_to_pgp_hostpay2_token'),
        ('decrypt_gchostpay2_to_gchostpay1_token', 'decrypt_pgp_hostpay2_to_pgp_hostpay1_token'),
        ('encrypt_gchostpay1_to_gchostpay3_token', 'encrypt_pgp_hostpay1_to_pgp_hostpay3_token'),
        ('decrypt_gchostpay3_to_gchostpay1_token', 'decrypt_pgp_hostpay3_to_pgp_hostpay1_token'),
    ],
    # ... etc for each service
}
```

#### 3.2.3: Verification Checklist

- [ ] Map all function definitions
- [ ] Map all function calls
- [ ] Verify no function is missed
- [ ] Check docstrings reference correct function names
- [ ] Run `python -m py_compile` on all modified files
- [ ] Run unit tests if available

#### 3.2.4: Deployment Strategy

**CRITICAL: Must use atomic deployment**

**Option A: Blue-Green Deployment (RECOMMENDED)**
1. Keep old services running
2. Deploy new services with updated function names to new endpoints
3. Update environment variables to point to new endpoints
4. Test thoroughly
5. Cutover traffic
6. Decommission old services

**Option B: Backward-Compatible Wrapper (SAFEST)**
1. Add new function names as aliases to old functions
2. Deploy services with both old and new function names
3. Update callers to use new names
4. Remove old function names after verification

Example:
```python
# Step 1: Add aliases
def encrypt_pgp_hostpay1_to_pgp_hostpay3_token(self, ...):
    """New function name."""
    # implementation

def encrypt_gchostpay1_to_gchostpay3_token(self, ...):
    """DEPRECATED: Use encrypt_pgp_hostpay1_to_pgp_hostpay3_token instead."""
    return self.encrypt_pgp_hostpay1_to_pgp_hostpay3_token(...)

# Step 2: Deploy and test
# Step 3: Remove old function after all callers updated
```

---

## Phase 3.3: Database Schema Changes (CRITICAL RISK)

**Risk:** CRITICAL - Requires database migration with potential downtime
**Estimated Time:** 4-6 hours (including testing and rollback prep)
**Affected Tables:** `processed_payments`

### Database Column Transformations

```sql
-- Current schema
processed_payments (
    unique_id VARCHAR(255) PRIMARY KEY,
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,
    ...
)

-- New schema
processed_payments (
    unique_id VARCHAR(255) PRIMARY KEY,
    pgp_orchestrator_processed BOOLEAN DEFAULT FALSE,
    pgp_orchestrator_processed_at TIMESTAMP,
    ...
)
```

### Implementation Steps

#### 3.3.1: Create Migration Script

Create `migrations/003_rename_gcwebhook1_columns.sql`:

```sql
-- Migration: Rename gcwebhook1_* columns to pgp_orchestrator_*
-- Date: 2025-01-15
-- Risk: LOW (column rename only, no data loss)

BEGIN;

-- Step 1: Rename columns (PostgreSQL syntax)
ALTER TABLE processed_payments
    RENAME COLUMN gcwebhook1_processed TO pgp_orchestrator_processed;

ALTER TABLE processed_payments
    RENAME COLUMN gcwebhook1_processed_at TO pgp_orchestrator_processed_at;

-- Step 2: Rename index if it exists
DROP INDEX IF EXISTS idx_gcwebhook1_processed;
CREATE INDEX idx_pgp_orchestrator_processed
    ON processed_payments(pgp_orchestrator_processed);

-- Step 3: Update column comments
COMMENT ON COLUMN processed_payments.pgp_orchestrator_processed IS
    'Flag indicating if PGP_ORCHESTRATOR_v1 successfully processed this payment';

COMMENT ON COLUMN processed_payments.pgp_orchestrator_processed_at IS
    'Timestamp when PGP_ORCHESTRATOR_v1 processed this payment';

COMMIT;
```

#### 3.3.2: Create Rollback Script

Create `migrations/003_rollback.sql`:

```sql
-- Rollback: Restore gcwebhook1_* column names
BEGIN;

ALTER TABLE processed_payments
    RENAME COLUMN pgp_orchestrator_processed TO gcwebhook1_processed;

ALTER TABLE processed_payments
    RENAME COLUMN pgp_orchestrator_processed_at TO gcwebhook1_processed_at;

DROP INDEX IF EXISTS idx_pgp_orchestrator_processed;
CREATE INDEX idx_gcwebhook1_processed
    ON processed_payments(gcwebhook1_processed);

COMMIT;
```

#### 3.3.3: Code Changes Required

Update all services that reference these columns:

**PGP_NP_IPN_v1:**
```python
# Before
SELECT gcwebhook1_processed FROM processed_payments WHERE unique_id = %s

# After
SELECT pgp_orchestrator_processed FROM processed_payments WHERE unique_id = %s
```

**PGP_ORCHESTRATOR_v1:**
```python
# Before
UPDATE processed_payments
SET gcwebhook1_processed = TRUE, gcwebhook1_processed_at = NOW()
WHERE unique_id = %s

# After
UPDATE processed_payments
SET pgp_orchestrator_processed = TRUE, pgp_orchestrator_processed_at = NOW()
WHERE unique_id = %s
```

#### 3.3.4: Deployment Strategy

**CRITICAL: Zero-downtime migration required**

**Recommended Approach: Multi-Phase Migration**

**Phase 1: Add New Columns (Backward Compatible)**
```sql
-- Add new columns alongside old ones
ALTER TABLE processed_payments
    ADD COLUMN pgp_orchestrator_processed BOOLEAN DEFAULT FALSE;

ALTER TABLE processed_payments
    ADD COLUMN pgp_orchestrator_processed_at TIMESTAMP;

-- Copy existing data
UPDATE processed_payments
SET pgp_orchestrator_processed = gcwebhook1_processed,
    pgp_orchestrator_processed_at = gcwebhook1_processed_at;
```

**Phase 2: Deploy Code That Writes to Both Columns**
```python
# Write to both old and new columns
UPDATE processed_payments
SET gcwebhook1_processed = TRUE,
    gcwebhook1_processed_at = NOW(),
    pgp_orchestrator_processed = TRUE,
    pgp_orchestrator_processed_at = NOW()
WHERE unique_id = %s
```

**Phase 3: Deploy Code That Reads From New Columns**
```python
# Read from new columns only
SELECT pgp_orchestrator_processed FROM processed_payments WHERE unique_id = %s
```

**Phase 4: Drop Old Columns (After Verification)**
```sql
ALTER TABLE processed_payments
    DROP COLUMN gcwebhook1_processed,
    DROP COLUMN gcwebhook1_processed_at;
```

#### 3.3.5: Verification Checklist

- [ ] Create full database backup
- [ ] Test migration on dev/staging database
- [ ] Verify data integrity after migration
- [ ] Test rollback script
- [ ] Document expected downtime (if any)
- [ ] Create monitoring alerts for migration
- [ ] Plan rollback procedure

---

## Phase 3.4: Environment Variable Names (Optional)

**Risk:** MEDIUM - Requires updating Secret Manager and deployment configs
**Estimated Time:** 2-3 hours

### Transformations

Current secret names in Secret Manager:
```
GCSPLIT1_URL → PGP_SPLIT1_URL
GCSPLIT2_URL → PGP_SPLIT2_URL
GCSPLIT3_URL → PGP_SPLIT3_URL
GCWEBHOOK1_URL → PGP_ORCHESTRATOR_URL
GCWEBHOOK2_URL → PGP_INVITE_URL
GCHOSTPAY1_URL → PGP_HOSTPAY1_URL
GCHOSTPAY2_URL → PGP_HOSTPAY2_URL
GCHOSTPAY3_URL → PGP_HOSTPAY3_URL
```

**Note:** This can be deferred as it's purely cosmetic and doesn't affect functionality.

---

## Overall Implementation Strategy

### Recommended Order

1. **Phase 3.1 First** (Internal Variables) - Low risk, good warm-up
2. **Phase 3.3 Second** (Database Schema) - Do while services still use old names
3. **Phase 3.2 Last** (Function Names) - Highest risk, requires coordination

### Alternative Order (Lower Risk)

1. **Phase 3.1** (Variables) - Low risk
2. **Phase 3.2 with Aliases** (Functions) - Add new names, keep old names
3. **Phase 3.3 with Dual Columns** (Database) - Run both schemas in parallel
4. **Cleanup Phase** - Remove old function names and database columns after verification

---

## Testing Requirements

### Pre-Deployment Testing

- [ ] Unit tests pass for all modified services
- [ ] Integration tests pass for cross-service communication
- [ ] Database migration tested on staging
- [ ] Rollback procedure tested
- [ ] Performance benchmarks unchanged

### Post-Deployment Verification

- [ ] All services healthy after deployment
- [ ] No errors in Cloud Logging
- [ ] Database queries using new column names succeed
- [ ] Token encryption/decryption working across services
- [ ] End-to-end payment flow working

---

## Rollback Plan

### Phase 3.1 Rollback (Variables)
- Git revert commit
- Redeploy previous version
- Low risk, can be done quickly

### Phase 3.2 Rollback (Functions)
- If using aliases: No rollback needed, old names still work
- If atomic rename: Git revert, redeploy all affected services simultaneously
- High risk if not using aliases

### Phase 3.3 Rollback (Database)
- If using dual columns: Switch code back to reading old columns
- If renamed columns: Run rollback SQL script
- CRITICAL: Must have verified rollback script before migration

---

## Success Criteria

### Phase 3.1 Complete
- [ ] All internal variable names updated
- [ ] No references to `gcsplit`, `gcwebhook`, `gchostpay` in variable names
- [ ] All services deployed successfully
- [ ] All services passing health checks

### Phase 3.2 Complete
- [ ] All function names updated
- [ ] No references to old function names in code
- [ ] All docstrings updated
- [ ] All services communicating successfully
- [ ] Token encryption/decryption working

### Phase 3.3 Complete
- [ ] Database schema updated
- [ ] All queries using new column names
- [ ] No errors in database operations
- [ ] Data integrity verified
- [ ] Old columns removed (if not using dual-column approach)

### Overall Phase 3 Complete
- [ ] Zero occurrences of `gc*` naming in code (except comments documenting old schema)
- [ ] All services using PGP_* naming consistently
- [ ] All tests passing
- [ ] No production errors
- [ ] Performance unchanged

---

## Risk Mitigation

1. **Create Full Backups**
   - Database backup before schema changes
   - Git branch for all code changes
   - Cloud Run revision history available for quick rollback

2. **Use Feature Flags**
   - Consider adding feature flags to toggle between old/new function names
   - Allows gradual rollout and easy rollback

3. **Monitor Closely**
   - Set up alerts for increased error rates
   - Monitor Cloud Logging during and after deployment
   - Have team on standby during deployment window

4. **Test Thoroughly**
   - Run all changes in dev environment first
   - Perform load testing after changes
   - Verify end-to-end payment flows

---

## Timeline Estimate

**Minimum Time (Aggressive):** 2-3 days
- Day 1: Phase 3.1 (Variables)
- Day 2: Phase 3.2 (Functions) + Phase 3.3 (Database)
- Day 3: Testing and verification

**Recommended Time (Conservative):** 5-7 days
- Day 1: Phase 3.1 (Variables) + Testing
- Day 2: Phase 3.3 Database migration prep + Dual-column deployment
- Day 3: Phase 3.2 Function aliases added
- Day 4: Testing and monitoring
- Day 5: Update callers to new function names
- Day 6: Cleanup old function names and database columns
- Day 7: Final verification

---

## Status

**NOT STARTED** - Awaiting user approval and decision on:
1. Which phases to execute (3.1, 3.2, 3.3, or all)
2. Deployment strategy (atomic vs. dual-schema vs. blue-green)
3. Timeline constraints
4. Testing requirements

---

## Next Steps

Before proceeding:

1. **User Decision Required:**
   - Do you want to proceed with all phases (3.1, 3.2, 3.3)?
   - Or start with Phase 3.1 only (variables)?
   - What is your preferred deployment strategy?

2. **Create Detailed Scripts:**
   - `phase_3_1_variable_rename.py`
   - `phase_3_2_function_rename.py`
   - `migrations/003_rename_columns.sql`

3. **Set Up Testing Environment:**
   - Verify dev/staging database available
   - Ensure ability to test migration
   - Set up monitoring and alerts

4. **Schedule Deployment Window:**
   - Determine low-traffic period
   - Allocate team resources
   - Plan rollback procedure
