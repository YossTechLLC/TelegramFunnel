# PayGatePrime PGP-LIVE Database Migration

**Project:** pgp-live
**Database:** telepaydb
**Instance:** pgp-live:us-central1:pgp-telepaypsql
**Created:** 2025-11-18

---

## Overview

This directory contains the complete database migration scripts for deploying the PayGatePrime schema to the **pgp-live** Google Cloud project. The migration creates a **13-table schema** optimized for cryptocurrency payment processing and Telegram private channel subscriptions.

### Key Changes from Original Schema

| Change | Old | New | Reason |
|--------|-----|-----|--------|
| **Tables** | 15 tables | 13 tables | Excluded deprecated state management tables |
| **Project** | telepay-459221 | pgp-live | New GCP project |
| **Instance** | telepay-459221:us-central1:telepaypsql | pgp-live:us-central1:pgp-telepaypsql | New Cloud SQL instance |
| **Code References** | client_table | pgp_live_db | Consistent naming convention |

### Tables Excluded

1. ❌ **donation_keypad_state** - Deprecated donation UI state management
2. ❌ **user_conversation_state** - Deprecated bot conversation state management

**Reason:** These tables were part of old bot architecture and are no longer needed in PGP_v1 services.

---

## Prerequisites

### 1. GCP Access

- [ ] Access to **pgp-live** project
- [ ] Cloud SQL Admin role (`roles/cloudsql.admin`)
- [ ] Secret Manager Secret Accessor role (`roles/secretmanager.secretAccessor`)

### 2. Cloud SQL Instance

- [ ] Instance **pgp-live:us-central1:pgp-telepaypsql** exists
- [ ] Database **telepaydb** exists on instance
- [ ] Instance is running (not stopped)

### 3. Secrets Configuration

Required secrets in **pgp-live** Secret Manager:

- `DATABASE_USER_SECRET` - PostgreSQL username (usually `postgres`)
- `DATABASE_PASSWORD_SECRET` - PostgreSQL password

### 4. Local Environment

- [ ] Python 3.9+ installed
- [ ] Virtual environment created at `PGP_v1/.venv`
- [ ] Required Python packages installed:
  ```bash
  pip install google-cloud-secret-manager cloud-sql-python-connector sqlalchemy pg8000
  ```
- [ ] `gcloud` CLI installed and authenticated

### 5. Permissions

- [ ] Service account has access to Secret Manager secrets
- [ ] Service account can connect to Cloud SQL instance
- [ ] User is authenticated: `gcloud auth application-default login`

---

## File Structure

```
TOOLS_SCRIPTS_TESTS/
├── migrations/
│   └── pgp-live/
│       ├── 001_pgp_live_complete_schema.sql      # Main schema (13 tables, 4 ENUMs)
│       ├── 001_pgp_live_rollback.sql              # Rollback script (drops everything)
│       ├── 002_pgp_live_populate_currency_to_network.sql  # Currency data (87 rows)
│       ├── 003_pgp_live_verify_schema.sql         # Verification queries
│       └── README_PGP_LIVE_MIGRATION.md           # This file
├── tools/
│   ├── deploy_pgp_live_schema.py                 # Python deployment tool
│   ├── verify_pgp_live_schema.py                 # Python verification tool
│   └── rollback_pgp_live_schema.py               # Python rollback tool
└── scripts/
    ├── deploy_pgp_live_schema.sh                 # Shell wrapper for deployment
    ├── verify_pgp_live_schema.sh                 # Shell wrapper for verification
    └── rollback_pgp_live_schema.sh               # Shell wrapper for rollback
```

---

## Deployment Steps

### Step 1: Verify Prerequisites

```bash
# Check GCP project
gcloud config get-value project
# Should output: pgp-live

# List Cloud SQL instances
gcloud sql instances list
# Should show: pgp-telepaypsql

# Verify virtual environment
ls -la .venv/
# Should exist with bin/, lib/, etc.
```

### Step 2: Dry Run (Recommended)

Test the deployment without making changes:

```bash
# Using shell script
cd TOOLS_SCRIPTS_TESTS/scripts
./deploy_pgp_live_schema.sh --dry-run

# Or using Python directly
cd TOOLS_SCRIPTS_TESTS/tools
python3 deploy_pgp_live_schema.py --dry-run
```

**Expected Output:**
- 🔍 Prints SQL statements without executing
- ✅ Validates migration files exist
- ✅ Tests database connection

### Step 3: Deploy Schema

Deploy the complete schema to pgp-live:

```bash
# Using shell script (recommended)
cd TOOLS_SCRIPTS_TESTS/scripts
./deploy_pgp_live_schema.sh

# Or using Python directly
cd TOOLS_SCRIPTS_TESTS/tools
python3 deploy_pgp_live_schema.py
```

**What Happens:**
1. Prompts for user confirmation
2. Connects to pgp-live database
3. Executes `001_pgp_live_complete_schema.sql`
   - Creates 4 ENUM types
   - Creates 13 tables in dependency order
   - Creates 60+ indexes
   - Creates 3 foreign key constraints
   - Inserts legacy system user
4. Executes `002_pgp_live_populate_currency_to_network.sql`
   - Inserts 87 currency/network mappings
5. Prints deployment summary

**Duration:** ~10-30 seconds

### Step 4: Verify Deployment

Verify the schema was deployed correctly:

```bash
# Using shell script (recommended)
cd TOOLS_SCRIPTS_TESTS/scripts
./verify_pgp_live_schema.sh

# Or using Python directly
cd TOOLS_SCRIPTS_TESTS/tools
python3 verify_pgp_live_schema.py
```

**Verification Checks:**
- ✅ 13 tables exist (no deprecated tables)
- ✅ 4 ENUM types exist
- ✅ 60+ indexes created
- ✅ 3 foreign keys established
- ✅ 5 sequences created
- ✅ 87 currency mappings inserted
- ✅ Legacy system user exists

**Exit Codes:**
- `0` - All checks passed
- `1` - One or more checks failed

---

## Schema Details

### Tables Created (13)

| # | Table Name | Purpose | Service |
|---|------------|---------|---------|
| 1 | `registered_users` | User accounts | PGP_SERVER_v1 |
| 2 | `main_clients_database` | Channel configs | PGP_SERVER_v1, PGP_ORCHESTRATOR_v1 |
| 3 | `private_channel_users_database` | Subscriptions | PGP_ORCHESTRATOR_v1, PGP_MONITOR_v1 |
| 4 | `processed_payments` | Payment tracking | PGP_ORCHESTRATOR_v1, PGP_INVITE_v1 |
| 5 | `batch_conversions` | ETH→USDT conversions | PGP_MICROBATCHPROCESSOR_v1 |
| 6 | `payout_accumulation` | Payment accumulation | PGP_ACCUMULATOR_v1 |
| 7 | `payout_batches` | Batch payouts | PGP_MICROBATCHPROCESSOR_v1 |
| 8 | `split_payout_request` | Split requests | PGP_SPLIT1_v1 |
| 9 | `split_payout_que` | Split queue | PGP_SPLIT1_v1, PGP_SPLIT2_v1 |
| 10 | `split_payout_hostpay` | Host payments | PGP_HOSTPAY_v1 |
| 11 | `broadcast_manager` | Broadcast scheduling | PGP_BROADCAST_v1 |
| 12 | `currency_to_network` | Currency mapping | All services |
| 13 | `failed_transactions` | Error tracking | PGP_ORCHESTRATOR_v1 |

### ENUM Types (4)

- `currency_type` - 16 cryptocurrencies (BTC, ETH, USDT, etc.)
- `network_type` - 10 blockchain networks (BTC, ETH, TRX, etc.)
- `flow_type` - ChangeNOW flow types (standard, fixed-rate)
- `type_type` - Exchange directions (direct, reverse)

### Foreign Keys (3)

1. `main_clients_database.client_id` → `registered_users.user_id`
2. `broadcast_manager.client_id` → `registered_users.user_id`
3. `payout_accumulation.batch_conversion_id` → `batch_conversions.batch_conversion_id`

---

## Rollback

### ⚠️ WARNING: Rollback will DELETE ALL DATA

Rollback should only be used in **development/testing** environments or if deployment failed.

### Safety Features

- Triple confirmation required
- Must type exact phrase: `DELETE ALL DATA`
- No dry-run mode (too dangerous)
- Prints table counts before/after

### Rollback Steps

```bash
# Using shell script (recommended)
cd TOOLS_SCRIPTS_TESTS/scripts
./rollback_pgp_live_schema.sh

# Or using Python directly
cd TOOLS_SCRIPTS_TESTS/tools
python3 rollback_pgp_live_schema.py
```

**What Happens:**
1. Prompts for first confirmation (yes/no)
2. Prompts for second confirmation (yes/no)
3. Requires typing exact phrase: `DELETE ALL DATA`
4. Drops all 13 tables
5. Drops 4 ENUM types
6. Drops 5 sequences
7. Prints summary

**After Rollback:**
- Database is empty (ready for re-deployment)
- Can run `deploy_pgp_live_schema.sh` again

---

## Troubleshooting

### Issue: "Database connection failed"

**Possible Causes:**
- Cloud SQL instance is stopped
- Wrong project selected
- Secrets not accessible
- Network connectivity issues

**Solutions:**
```bash
# Verify instance is running
gcloud sql instances describe pgp-telepaypsql --project=pgp-live

# Start instance if stopped
gcloud sql instances patch pgp-telepaypsql --project=pgp-live --activation-policy=ALWAYS

# Verify secrets exist
gcloud secrets list --project=pgp-live | grep DATABASE
```

### Issue: "Table already exists"

**Cause:** Schema was partially deployed or already exists

**Solutions:**
1. Run rollback script to clean up
2. Or continue deployment (script uses `CREATE TABLE IF NOT EXISTS`)

### Issue: "Permission denied"

**Cause:** Missing IAM roles

**Solutions:**
```bash
# Grant Cloud SQL Admin role
gcloud projects add-iam-policy-binding pgp-live \
  --member="user:your-email@example.com" \
  --role="roles/cloudsql.admin"

# Grant Secret Manager Secret Accessor role
gcloud projects add-iam-policy-binding pgp-live \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Issue: "Currency data not populated"

**Cause:** Step 2 of deployment failed

**Solution:**
```bash
# Manually run population script
psql -h /cloudsql/pgp-live:us-central1:pgp-telepaypsql -U postgres -d telepaydb \
  -f TOOLS_SCRIPTS_TESTS/migrations/pgp-live/002_pgp_live_populate_currency_to_network.sql
```

### Issue: "Virtual environment not found"

**Cause:** `.venv` directory doesn't exist

**Solution:**
```bash
# Create virtual environment
cd PGP_v1
python3 -m venv .venv

# Activate and install dependencies
source .venv/bin/activate
pip install google-cloud-secret-manager cloud-sql-python-connector sqlalchemy pg8000
```

---

## Service Migration Steps

After deploying the schema, update service code:

### 1. Update Database References

Search and replace in all service code:

**Old:** `client_table`
**New:** `pgp_live_db`

**Files to Update:**
- All `PGP_*_v1` service directories
- Database connection configuration
- Environment variable references

### 2. Update Connection Strings

**Old:**
```python
INSTANCE_CONNECTION_NAME = "telepay-459221:us-central1:telepaypsql"
```

**New:**
```python
INSTANCE_CONNECTION_NAME = "pgp-live:us-central1:pgp-telepaypsql"
```

### 3. Update Secret References

Ensure services pull secrets from **pgp-live** project:

```python
PROJECT_ID = "pgp-live"
```

### 4. Test Service Connections

Before deploying services:

```bash
# Test connection from each service
python3 -c "
from google.cloud.sql.connector import Connector
connector = Connector()
conn = connector.connect(
    'pgp-live:us-central1:pgp-telepaypsql',
    'pg8000',
    user='postgres',
    password='***',
    db='telepaydb'
)
print('✅ Connection successful')
conn.close()
connector.close()
"
```

---

## Maintenance

### Backup Recommendations

Before major changes:

```bash
# Export schema only
gcloud sql export sql pgp-telepaypsql \
  gs://pgp-live-backups/schema-$(date +%Y%m%d).sql \
  --database=telepaydb \
  --project=pgp-live

# Export schema + data
gcloud sql export sql pgp-telepaypsql \
  gs://pgp-live-backups/full-backup-$(date +%Y%m%d).sql \
  --database=telepaydb \
  --project=pgp-live
```

### Schema Updates

For future schema changes:

1. Create new migration file: `00X_pgp_live_<description>.sql`
2. Create corresponding rollback: `00X_pgp_live_<description>_rollback.sql`
3. Update `deploy_pgp_live_schema.py` to include new migration
4. Test in development environment first
5. Run `verify_pgp_live_schema.py` after deployment

---

## Support

For issues or questions:

1. Check `PROGRESS.md` for known issues
2. Check `DECISIONS.md` for architectural decisions
3. Check `BUGS.md` for reported bugs
4. Review logs in `/THINK/AUTO/` directory

---

**End of Migration Guide**
**Status:** Production-ready (awaiting user approval for deployment)
**Last Updated:** 2025-11-18
