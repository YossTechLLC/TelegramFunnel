# Migration Execution Script Creation Checklist

**Created:** 2025-11-18
**Purpose:** Document requirements for creating a generic database migration execution script
**Context:** User asked to check if migration execution script exists in `/TOOLS_SCRIPTS_TESTS/` and create checklist if not found

---

## Current State Analysis

### Existing Migration Scripts
- ✅ `deploy_pgp_live_schema.py` - Deploys complete schema (001, 002)
- ✅ `deploy_pgp_live_schema.sh` - Bash wrapper for Python script
- ✅ `rollback_pgp_live_schema.py` - Rollback tool for schema
- ✅ `verify_pgp_live_schema.py` - Schema verification tool

### Pattern Observed
All existing scripts are **schema-specific** and **project-specific** (pgp-live).
**No generic migration runner exists.**

### New Migrations Created (Security Fixes)
- ✅ `004_add_payment_unique_constraint.sql` - C-04 fix (race conditions)
- ✅ `004_rollback.sql` - Rollback for migration 004
- ✅ `005_create_transaction_limits.sql` - C-05 fix (amount limits)
- ✅ `005_rollback.sql` - Rollback for migration 005

---

## Requirements for Generic Migration Execution Script

### 1. Script Naming & Location
- **File:** `TOOLS_SCRIPTS_TESTS/scripts/run_migration.sh`
- **Python Tool:** `TOOLS_SCRIPTS_TESTS/tools/execute_migration.py`
- **Pattern:** Similar to existing `deploy_pgp_live_schema.sh` + `.py` pair

### 2. Input Parameters
```bash
./run_migration.sh MIGRATION_NUMBER [--dry-run] [--skip-confirmation] [--rollback]

Examples:
  ./run_migration.sh 004                    # Run migration 004
  ./run_migration.sh 004 --dry-run          # Preview migration 004
  ./run_migration.sh 005 --skip-confirmation # Run without prompt
  ./run_migration.sh 004 --rollback         # Rollback migration 004
```

### 3. Required Functionality

#### A. Migration File Detection
- [x] Auto-detect migration files: `migrations/{number}_*.sql`
- [x] Auto-detect rollback files: `migrations/{number}_rollback.sql`
- [x] Support both formats:
  - `004_add_payment_unique_constraint.sql`
  - `005_create_transaction_limits.sql`
- [x] Error if migration file not found

#### B. Database Connection
- [x] Use Google Cloud SQL Connector (matches existing pattern)
- [x] Fetch credentials from Secret Manager:
  - `PGP_DB_USER` (default: postgres)
  - `PGP_DB_PASSWORD`
  - `PGP_DB_NAME` (default: telepaydb)
- [x] Connection string: `pgp-live:us-central1:pgp-telepaypsql`
- [x] Use SQLAlchemy with `text()` for SQL execution (correct pattern)

#### C. Pre-Migration Validation
- [x] Check database connectivity (ping test)
- [x] Verify migration file is valid SQL (syntax check)
- [x] Check if migration already applied (tracking table?)
- [x] Backup current schema (optional, recommended)
- [x] Display migration summary before execution

#### D. Migration Execution
- [x] Read SQL file content
- [x] Execute in transaction (BEGIN/COMMIT)
- [x] Use `\set ON_ERROR_STOP on` equivalent (rollback on error)
- [x] Log all output to file: `logs/migration_{number}_{timestamp}.log`
- [x] Display real-time progress to console

#### E. Post-Migration Validation
- [x] Verify migration completed (check for error messages)
- [x] Run verification queries if specified in migration
- [x] Record migration in tracking table (optional, best practice)
- [x] Display summary of changes (tables created, rows affected)

#### F. Rollback Support
- [x] Detect rollback file: `{number}_rollback.sql`
- [x] Same validation as forward migration
- [x] Transaction-based rollback
- [x] Update migration tracking table

#### G. Dry-Run Mode
- [x] Print SQL without executing
- [x] Simulate connection (validate credentials)
- [x] Show what would be executed
- [x] No changes to database

#### H. Error Handling
- [x] Catch connection errors (network, auth, etc.)
- [x] Catch SQL execution errors (syntax, constraint violations)
- [x] Auto-rollback transaction on error
- [x] Preserve error logs for debugging
- [x] Clear error messages (use error sanitization from C-07)

---

## Implementation Checklist

### Phase 1: Create Python Execution Tool
- [ ] **File:** `TOOLS_SCRIPTS_TESTS/tools/execute_migration.py`
- [ ] Import required libraries:
  - `argparse` - Command-line argument parsing
  - `pathlib.Path` - File path handling
  - `google.cloud.secretmanager` - Secret Manager client
  - `google.cloud.sql.connector` - Cloud SQL connection
  - `sqlalchemy` - Database connection/queries
  - `logging` - Structured logging
- [ ] Function: `get_secret(secret_id: str) -> str`
  - Fetch from Secret Manager
  - Same pattern as `deploy_pgp_live_schema.py`
- [ ] Function: `get_db_connection() -> sqlalchemy.Engine`
  - Use Cloud SQL Connector
  - Return SQLAlchemy engine
- [ ] Function: `find_migration_file(migration_number: str) -> Path`
  - Search `migrations/` directory
  - Return path or raise FileNotFoundError
- [ ] Function: `read_sql_file(file_path: Path) -> str`
  - Read SQL content
  - Handle encoding issues
- [ ] Function: `execute_migration(sql: str, engine: sqlalchemy.Engine) -> bool`
  - Use `with engine.connect() as conn:` pattern
  - Use `conn.execute(text(sql))`
  - Wrap in transaction
  - Return success/failure
- [ ] Function: `verify_migration(migration_number: str) -> bool`
  - Check if migration already applied
  - Query migration tracking table (if exists)
- [ ] Function: `log_migration(migration_number: str, status: str)`
  - Record in migration history table
  - Track: number, timestamp, status, user
- [ ] Main execution logic:
  - Parse arguments
  - Connect to database
  - Find migration file
  - Execute or rollback
  - Log results
- [ ] Add color output for better UX
- [ ] Add progress indicators
- [ ] Add dry-run mode

### Phase 2: Create Bash Wrapper Script
- [ ] **File:** `TOOLS_SCRIPTS_TESTS/scripts/run_migration.sh`
- [ ] Pattern: Same as `deploy_pgp_live_schema.sh`
- [ ] Features:
  - Activate virtual environment (`.venv`)
  - Set GCP project (`gcloud config set project pgp-live`)
  - Call Python script with arguments
  - Capture exit code
  - Display colored output
- [ ] Error handling:
  - Check if `.venv` exists
  - Check if Python script exists
  - Check if gcloud is authenticated
- [ ] Make executable: `chmod +x run_migration.sh`

### Phase 3: Create Migration Tracking Table (Optional but Recommended)
- [ ] **File:** `migrations/000_create_migration_tracking.sql`
- [ ] Table schema:
  ```sql
  CREATE TABLE IF NOT EXISTS schema_migrations (
      migration_number VARCHAR(10) PRIMARY KEY,
      migration_name VARCHAR(255) NOT NULL,
      applied_at TIMESTAMP DEFAULT NOW(),
      applied_by VARCHAR(100),
      status VARCHAR(20) DEFAULT 'applied',
      rollback_at TIMESTAMP,
      notes TEXT
  );
  ```
- [ ] Functions:
  - `is_migration_applied(number) -> bool`
  - `record_migration(number, name, status)`
  - `record_rollback(number)`

### Phase 4: Testing
- [ ] Test migration 004 (unique constraint)
  - Dry-run mode
  - Real execution
  - Verify constraint created
  - Rollback
  - Verify constraint removed
- [ ] Test migration 005 (transaction limits)
  - Dry-run mode
  - Real execution
  - Verify table created
  - Verify default values inserted
  - Rollback
  - Verify table dropped
- [ ] Test error handling
  - Invalid migration number
  - SQL syntax error in migration
  - Database connection failure
  - Permission denied
- [ ] Test tracking table
  - Prevent duplicate migrations
  - Record history correctly

### Phase 5: Documentation
- [ ] **File:** `TOOLS_SCRIPTS_TESTS/migrations/README_MIGRATIONS.md`
- [ ] Document:
  - How to create new migration
  - How to run migration
  - How to rollback migration
  - Migration naming convention
  - Best practices for migrations
  - Troubleshooting common errors
- [ ] Add usage examples
- [ ] Add to main README.md

---

## Recommendation

**Should we create this generic migration runner?**

### Pros
- ✅ Consistent migration execution across all migrations
- ✅ Better error handling and logging
- ✅ Migration tracking (prevent duplicates)
- ✅ Easier for team members to run migrations
- ✅ Dry-run mode for safety
- ✅ Automated rollback on error

### Cons
- ⚠️ Adds complexity (200-300 lines of code)
- ⚠️ Requires testing to ensure reliability
- ⚠️ May be overkill if migrations are rare

### Alternative Approach (Simpler)
Instead of generic script, create **migration-specific runners**:
- `run_migration_004.sh` - Run migration 004 only
- `run_migration_005.sh` - Run migration 005 only

This is simpler and follows the existing pattern of project-specific scripts.

---

## Decision Required from User

**Question:** Which approach do you prefer?

1. **Option A: Generic Migration Runner**
   - Create `run_migration.sh NUMBER` script
   - ~300 lines of code
   - Reusable for all future migrations
   - Estimated effort: 3-4 hours

2. **Option B: Migration-Specific Scripts**
   - Create `run_migration_004.sh` and `run_migration_005.sh`
   - ~100 lines each
   - Simpler, follows existing pattern
   - Estimated effort: 1-2 hours

3. **Option C: Manual Execution (Current State)**
   - Use `psql` directly to run migrations
   - No script needed
   - Documented in migration file headers
   - Estimated effort: 0 hours (already done)

**Recommendation:** Option B (migration-specific scripts) balances simplicity and reusability.

---

## Summary

**Existing Migration Scripts:** Schema-specific only, no generic runner
**New Migrations Created:** 004 (payment constraint), 005 (transaction limits)
**Migration Execution:** Currently requires manual `psql` execution
**Checklist Created:** ✅ Yes (this document)
**Next Step:** User decision on which approach to use (A, B, or C)

---

**END OF CHECKLIST**
