# Database Schema Documentation - PGP_v1 → pgp-live Project

**Project:** PayGatePrime (PGP_v1)
**Source Environment:** telepay-459221 / telepaypsql / telepaydb
**Target Environment:** pgp-live / pgp-live-psql / **pgp-live-db**
**Migration Type:** Greenfield deployment with schema preservation
**Last Updated:** 2025-11-18
**Status:** 📋 DOCUMENTATION COMPLETE - Ready for Deployment

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Migration Overview](#migration-overview)
3. [Database Schema Architecture](#database-schema-architecture)
4. [Deployment Phases](#deployment-phases)
5. [Table Definitions (15 Tables)](#table-definitions-15-tables)
6. [Service-to-Table Mapping](#service-to-table-mapping)
7. [Migration Scripts & Verification](#migration-scripts--verification)
8. [Rollback Strategy](#rollback-strategy)
9. [Post-Deployment Validation](#post-deployment-validation)

---

## Executive Summary

### Overview

This document provides the complete database schema and deployment plan for the **pgp-live** project. The schema is based on the proven production database from **telepay-459221** but adapted for the new PGP_v1 microservices architecture.

### Key Changes

| Aspect | Old (telepay-459221) | New (pgp-live) | Status |
|--------|---------------------|----------------|--------|
| **Project ID** | telepay-459221 | pgp-live | ✅ New project |
| **PSQL Instance** | telepaypsql | pgp-live-psql | ✅ To be created |
| **Database Name** | telepaydb | **pgp-live-db** | ⚠️ **CHANGED** |
| **Table Names** | 15 tables | 15 tables (same names) | ✅ **PRESERVED** |
| **Column Names** | ~200 columns | ~200 columns (same names) | ✅ **PRESERVED** |
| **ENUM Types** | 4 custom types | 4 custom types (same) | ✅ **PRESERVED** |
| **Indexes** | 50+ indexes | 50+ indexes (same) | ✅ **PRESERVED** |
| **Constraints** | 30+ constraints | 30+ constraints (same) | ✅ **PRESERVED** |

### Database Name Change: telepaydb → pgp-live-db

**Why Change the Database Name?**

1. **Project Clarity**: "pgp-live-db" clearly indicates the database belongs to the pgp-live project
2. **Service Naming Consistency**: Aligns with PGP_v1 naming scheme (PGP_SERVER_v1, PGP_ORCHESTRATOR_v1, etc.)
3. **Environment Separation**: Clear distinction between legacy (telepaydb) and new (pgp-live-db) environments
4. **Code Readability**: Future developers immediately understand which project the database serves

**What Stays the Same?**

- ✅ All 15 table names (main_clients_database, private_channel_users_database, etc.)
- ✅ All column names across all tables
- ✅ All data types, constraints, indexes, and foreign keys
- ✅ All ENUM type definitions (currency_type, network_type, flow_type, type_type)
- ✅ Complete schema compatibility with existing PGP_v1 code

### Schema Metrics

- **Total Tables:** 15 operational tables
- **Total Columns:** ~200 columns across all tables
- **Custom ENUM Types:** 4 (currency_type, network_type, flow_type, type_type)
- **Indexes:** 50+ indexes (unique, composite, partial)
- **Foreign Keys:** 3 FK relationships
- **Constraints:** 30+ CHECK constraints for data integrity
- **Sequences:** 5 auto-increment sequences

### Services Using This Database

All 15 PGP_v1 microservices connect to pgp-live-db:

- **PGP_SERVER_v1** - Telegram bot server (main_clients_database, registered_users, private_channel_users_database)
- **PGP_WEBAPI_v1** - REST API (registered_users, main_clients_database)
- **PGP_NP_IPN_v1** - NOWPayments webhook (private_channel_users_database, processed_payments)
- **PGP_ORCHESTRATOR_v1** - Payment orchestration (processed_payments, payout_accumulation, split_payout_request, failed_transactions)
- **PGP_INVITE_v1** - Telegram invites (processed_payments, private_channel_users_database)
- **PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_SPLIT3_v1** - Split payout pipeline (split_payout_request, split_payout_que, split_payout_hostpay)
- **PGP_HOSTPAY1_v1, PGP_HOSTPAY2_v1, PGP_HOSTPAY3_v1** - Host payment pipeline (split_payout_hostpay)
- **PGP_BATCHPROCESSOR_v1** - Batch payouts (payout_batches, payout_accumulation)
- **PGP_MICROBATCHPROCESSOR_v1** - Micro-batch processing (batch_conversions, payout_accumulation)
- **PGP_NOTIFICATIONS_v1** - Payment notifications (processed_payments)
- **PGP_BROADCAST_v1** - Broadcast scheduler (broadcast_manager, main_clients_database)

---

## Migration Overview

### Source Environment (telepay-459221)

```
┌─────────────────────────────────────────────────┐
│         LEGACY PRODUCTION ENVIRONMENT           │
├─────────────────────────────────────────────────┤
│ Project ID:       telepay-459221                │
│ PSQL Instance:    telepaypsql                   │
│ Database Name:    telepaydb                     │
│ Region:           us-central1                   │
│ Status:           ✅ ACTIVE (production)        │
│                                                 │
│ Tables:           15 operational tables         │
│ Records:          ~600 rows (active data)       │
│ Services:         17 GC*-10-26 microservices    │
└─────────────────────────────────────────────────┘
```

### Target Environment (pgp-live)

```
┌─────────────────────────────────────────────────┐
│         NEW PGP_v1 PRODUCTION ENVIRONMENT       │
├─────────────────────────────────────────────────┤
│ Project ID:       pgp-live                      │
│ PSQL Instance:    pgp-live-psql                 │
│ Database Name:    pgp-live-db    ⚠️ NEW NAME   │
│ Region:           us-central1                   │
│ Status:           ❌ NOT DEPLOYED               │
│                                                 │
│ Tables:           15 operational tables (same)  │
│ Records:          0 rows (greenfield)           │
│ Services:         15 PGP_*_v1 microservices     │
└─────────────────────────────────────────────────┘
```

### Migration Strategy

**Type:** Greenfield deployment (fresh database, no data migration)

**Approach:**

1. Create new Cloud SQL instance (pgp-live-psql) in pgp-live project
2. Create new database (**pgp-live-db**) within instance
3. Deploy complete schema (15 tables, 4 ENUMs, 50+ indexes)
4. Populate currency_to_network reference table (87 entries)
5. Insert legacy_system user for backward compatibility
6. Deploy PGP_v1 services configured for pgp-live-db
7. Validate schema with verification scripts
8. Begin production operations on new infrastructure

**No Data Migration:** This is a greenfield deployment. The old telepaydb remains untouched and continues serving legacy services.

---

## Database Schema Architecture

### ENUM Types (4 Custom Types)

These custom PostgreSQL ENUM types ensure data consistency across all tables.

#### 1. currency_type

**Purpose:** Supported cryptocurrency types across the platform
**Used By:** split_payout_request, split_payout_que, split_payout_hostpay, main_clients_database

```sql
CREATE TYPE currency_type AS ENUM (
    'BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'XMR', 'BCH', 'BNB',
    'TRX', 'DOGE', 'XRP', 'ADA', 'DOT', 'SOL', 'MATIC', 'AVAX'
);
```

**Values:** 16 supported cryptocurrencies

#### 2. network_type

**Purpose:** Blockchain networks for cryptocurrency transactions
**Used By:** split_payout_request, split_payout_que, split_payout_hostpay, main_clients_database

```sql
CREATE TYPE network_type AS ENUM (
    'BTC', 'ETH', 'TRX', 'BSC', 'MATIC', 'AVAX', 'SOL', 'LTC', 'BCH', 'XMR'
);
```

**Values:** 10 supported blockchain networks

#### 3. flow_type

**Purpose:** ChangeNOW exchange flow types (standard or fixed-rate)
**Used By:** split_payout_request, split_payout_que

```sql
CREATE TYPE flow_type AS ENUM ('standard', 'fixed-rate');
```

**Values:** 2 flow types

#### 4. type_type

**Purpose:** ChangeNOW exchange direction (direct or reverse)
**Used By:** split_payout_request, split_payout_que

```sql
CREATE TYPE type_type AS ENUM ('direct', 'reverse');
```

**Values:** 2 direction types

---

### Table Categories

The 15 tables are organized into 5 functional categories:

```
📊 PGP-LIVE-DB SCHEMA (15 Tables)
════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────┐
│  CATEGORY 1: USER & CLIENT MANAGEMENT (3 tables)        │
├─────────────────────────────────────────────────────────┤
│  1. registered_users              - User accounts       │
│  2. main_clients_database         - Channel configs     │
│  3. private_channel_users_database - User subscriptions │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CATEGORY 2: PAYMENT PROCESSING (3 tables)              │
├─────────────────────────────────────────────────────────┤
│  4. processed_payments            - Payment tracking    │
│  5. payout_accumulation           - Payment accumulation│
│  6. payout_batches                - Batch payouts       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CATEGORY 3: CONVERSION PIPELINE (4 tables)             │
├─────────────────────────────────────────────────────────┤
│  7. batch_conversions             - ETH→USDT batches    │
│  8. split_payout_request          - Client payout req   │
│  9. split_payout_que              - Payout queue        │
│  10. split_payout_hostpay         - Host payment track  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CATEGORY 4: FEATURE TABLES (3 tables)                  │
├─────────────────────────────────────────────────────────┤
│  11. broadcast_manager            - Broadcast scheduler │
│  12. donation_keypad_state        - Donation UI state   │
│  13. user_conversation_state      - Bot conv state      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CATEGORY 5: UTILITY TABLES (2 tables)                  │
├─────────────────────────────────────────────────────────┤
│  14. currency_to_network          - Currency mappings   │
│  15. failed_transactions          - Error tracking      │
└─────────────────────────────────────────────────────────┘
```

---

## Deployment Phases

### Phase 1: Cloud SQL Instance Creation

**Objective:** Create pgp-live-psql Cloud SQL instance in pgp-live project

**Prerequisites:**
- [ ] GCP Project `pgp-live` created
- [ ] Billing enabled on pgp-live project
- [ ] Cloud SQL Admin API enabled
- [ ] gcloud CLI authenticated to pgp-live project

**Commands:**

```bash
# Set project
gcloud config set project pgp-live

# Enable Cloud SQL Admin API
gcloud services enable sqladmin.googleapis.com

# Create Cloud SQL instance
gcloud sql instances create pgp-live-psql \
    --database-version=POSTGRES_15 \
    --tier=db-custom-2-7680 \
    --region=us-central1 \
    --network=default \
    --enable-bin-log \
    --backup-start-time=03:00 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=04 \
    --database-flags=max_connections=500
```

**Instance Specifications:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Instance Name** | pgp-live-psql | Matches target naming scheme |
| **PostgreSQL Version** | 15 | Latest stable version |
| **Machine Type** | db-custom-2-7680 | 2 vCPU, 7.5GB RAM |
| **Region** | us-central1 | Same as Cloud Run services |
| **Max Connections** | 500 | Supports 15 microservices |
| **Backup Time** | 03:00 UTC | Off-peak hours |
| **Maintenance Window** | Sunday 04:00 | Weekend maintenance |

**Expected Cost:** $70-80/month

**Verification:**

```bash
# Verify instance created
gcloud sql instances describe pgp-live-psql --format="table(name,state,region,databaseVersion,settings.tier)"

# Expected output:
# NAME            STATE     REGION        DATABASE_VERSION  TIER
# pgp-live-psql   RUNNABLE  us-central1   POSTGRES_15       db-custom-2-7680
```

---

### Phase 2: Database Creation (pgp-live-db)

**Objective:** Create pgp-live-db database within pgp-live-psql instance

**Commands:**

```bash
# Create database
gcloud sql databases create pgp-live-db \
    --instance=pgp-live-psql \
    --charset=UTF8

# Verify database created
gcloud sql databases list --instance=pgp-live-psql
```

**Expected Output:**

```
NAME          CHARSET  COLLATION
postgres      UTF8     en_US.UTF8
pgp-live-db   UTF8     en_US.UTF8
```

**Verification:**

```bash
# Connect via Cloud SQL Proxy
cloud_sql_proxy -instances=pgp-live:us-central1:pgp-live-psql=tcp:5432 &

# Verify database exists
psql "host=127.0.0.1 port=5432 dbname=postgres user=postgres" \
    -c "\l pgp-live-db"
```

**Expected Result:** Database `pgp-live-db` listed with UTF8 encoding

---

### Phase 3: Schema Deployment (ENUM Types)

**Objective:** Create 4 custom ENUM types required by tables

**Migration Script:** `/TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql` (lines 19-46)

**SQL Commands:**

```sql
-- Connect to pgp-live-db
\c pgp-live-db

-- Create ENUM types
DO $$ BEGIN
    CREATE TYPE currency_type AS ENUM (
        'BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'XMR', 'BCH', 'BNB',
        'TRX', 'DOGE', 'XRP', 'ADA', 'DOT', 'SOL', 'MATIC', 'AVAX'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE network_type AS ENUM (
        'BTC', 'ETH', 'TRX', 'BSC', 'MATIC', 'AVAX', 'SOL', 'LTC', 'BCH', 'XMR'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE flow_type AS ENUM ('standard', 'fixed-rate');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE type_type AS ENUM ('direct', 'reverse');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
```

**Deployment via Cloud SQL Proxy:**

```bash
# Start Cloud SQL Proxy
cloud_sql_proxy -instances=pgp-live:us-central1:pgp-live-psql=tcp:5432 &

# Deploy ENUM types
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql
```

**Verification:**

```bash
# List custom types
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -c "\dT"
```

**Expected Output:**

```
                   List of data types
 Schema |      Name      | Internal name | Size |  Description
--------+----------------+---------------+------+---------------
 public | currency_type  | currency_type | 4    |
 public | flow_type      | flow_type     | 4    |
 public | network_type   | network_type  | 4    |
 public | type_type      | type_type     | 4    |
```

---

### Phase 4: Schema Deployment (Tables)

**Objective:** Create all 15 operational tables with indexes and constraints

**Migration Script:** `/TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql` (lines 48-663)

**Deployment Order:**

Tables must be created in this specific order due to foreign key dependencies:

1. ✅ **registered_users** (no dependencies)
2. ✅ **main_clients_database** (depends on registered_users)
3. ✅ **private_channel_users_database** (no FK dependencies)
4. ✅ **processed_payments** (no FK dependencies)
5. ✅ **batch_conversions** (no FK dependencies)
6. ✅ **payout_accumulation** (depends on batch_conversions)
7. ✅ **payout_batches** (no FK dependencies)
8. ✅ **split_payout_request** (no FK dependencies)
9. ✅ **split_payout_que** (no FK dependencies)
10. ✅ **split_payout_hostpay** (no FK dependencies)
11. ✅ **broadcast_manager** (depends on registered_users)
12. ✅ **donation_keypad_state** (no FK dependencies)
13. ✅ **user_conversation_state** (no FK dependencies)
14. ✅ **currency_to_network** (no FK dependencies)
15. ✅ **failed_transactions** (no FK dependencies)

**Deployment Command:**

```bash
# Deploy complete schema (ENUM types + tables + indexes + constraints)
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql
```

**Verification:**

```bash
# List all tables
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -c "\dt"
```

**Expected Output:**

```
                          List of relations
 Schema |              Name               | Type  |  Owner
--------+---------------------------------+-------+----------
 public | batch_conversions               | table | postgres
 public | broadcast_manager               | table | postgres
 public | currency_to_network             | table | postgres
 public | donation_keypad_state           | table | postgres
 public | failed_transactions             | table | postgres
 public | main_clients_database           | table | postgres
 public | payout_accumulation             | table | postgres
 public | payout_batches                  | table | postgres
 public | private_channel_users_database  | table | postgres
 public | processed_payments              | table | postgres
 public | registered_users                | table | postgres
 public | split_payout_hostpay            | table | postgres
 public | split_payout_que                | table | postgres
 public | split_payout_request            | table | postgres
 public | user_conversation_state         | table | postgres
(15 rows)
```

---

### Phase 5: Reference Data Population

**Objective:** Populate currency_to_network table with 87 currency/network mappings

**Migration Script:** `/TOOLS_SCRIPTS_TESTS/migrations/002_populate_currency_to_network.sql`

**Sample Data:**

```sql
INSERT INTO currency_to_network (currency, network, currency_name, network_name) VALUES
('BTC', 'BTC', 'Bitcoin', 'Bitcoin'),
('ETH', 'ETH', 'Ethereum', 'Ethereum'),
('USDT', 'ETH', 'Tether', 'Ethereum'),
('USDT', 'TRX', 'Tether', 'Tron'),
('USDT', 'BSC', 'Tether', 'BSC'),
-- ... 82 more rows
```

**Deployment Command:**

```bash
# Populate currency_to_network table
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/002_populate_currency_to_network.sql
```

**Verification:**

```bash
# Count entries in currency_to_network
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -c "SELECT COUNT(*) FROM currency_to_network;"
```

**Expected Output:**

```
 count
-------
    87
(1 row)
```

---

### Phase 6: Legacy User Creation

**Objective:** Insert legacy_system user for backward compatibility

**Purpose:** Channels registered before the web portal was deployed need a default user_id reference.

**SQL Command:**

```sql
INSERT INTO registered_users (
    user_id,
    username,
    email,
    password_hash,
    is_active,
    email_verified
) VALUES (
    '00000000-0000-0000-0000-000000000000',
    'legacy_system',
    'legacy@paygateprime.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5qlcHxqCJzqZ2',
    FALSE,
    FALSE
) ON CONFLICT (user_id) DO NOTHING;
```

**Deployment:**

```bash
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -c "INSERT INTO registered_users (user_id, username, email, password_hash, is_active, email_verified) VALUES ('00000000-0000-0000-0000-000000000000', 'legacy_system', 'legacy@paygateprime.com', '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5qlcHxqCJzqZ2', FALSE, FALSE) ON CONFLICT (user_id) DO NOTHING;"
```

**Verification:**

```bash
# Verify legacy user created
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -c "SELECT user_id, username, email FROM registered_users WHERE username = 'legacy_system';"
```

**Expected Output:**

```
               user_id                | username      | email
--------------------------------------+---------------+---------------------------
 00000000-0000-0000-0000-000000000000 | legacy_system | legacy@paygateprime.com
```

---

## Table Definitions (15 Tables)

### CATEGORY 1: USER & CLIENT MANAGEMENT

---

#### Table 1: registered_users

**Purpose:** User account management for PayGatePrime web portal (PGP_WEBAPI_v1)
**Service:** PGP_SERVER_v1, PGP_WEBAPI_v1
**Primary Key:** user_id (UUID)
**Expected Row Count:** 21+ (grows with user registrations)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS registered_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    pending_email VARCHAR(255),
    pending_email_token VARCHAR(500),
    pending_email_token_expires TIMESTAMP,
    pending_email_old_notification_sent BOOLEAN DEFAULT FALSE,
    last_verification_resent_at TIMESTAMP,
    verification_resend_count INTEGER DEFAULT 0,
    last_email_change_requested_at TIMESTAMP,

    CONSTRAINT check_pending_email_different
        CHECK (pending_email IS NULL OR pending_email <> email)
);
```

**Indexes:**

```sql
-- Unique constraints for username and email
CREATE UNIQUE INDEX IF NOT EXISTS unique_username ON registered_users(username);
CREATE UNIQUE INDEX IF NOT EXISTS unique_email ON registered_users(email);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_registered_users_username ON registered_users(username);
CREATE INDEX IF NOT EXISTS idx_registered_users_email ON registered_users(email);
CREATE INDEX IF NOT EXISTS idx_registered_users_verification_token ON registered_users(verification_token);
CREATE INDEX IF NOT EXISTS idx_registered_users_reset_token ON registered_users(reset_token);

-- Email change workflow indexes
CREATE INDEX IF NOT EXISTS idx_pending_email ON registered_users(pending_email) WHERE pending_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_verification_token_expires ON registered_users(verification_token_expires) WHERE verification_token_expires IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pending_email_token_expires ON registered_users(pending_email_token_expires) WHERE pending_email_token_expires IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pending_email ON registered_users(pending_email) WHERE pending_email IS NOT NULL;
```

**Constraints:**

- ✅ **PK:** user_id (UUID)
- ✅ **UNIQUE:** username, email, pending_email (if not null)
- ✅ **CHECK:** pending_email must differ from email

**Column Descriptions:**

| Column | Type | Purpose | Managed By |
|--------|------|---------|------------|
| user_id | UUID | Primary key | Auto-generated |
| username | VARCHAR(50) | User login name | PGP_WEBAPI_v1 |
| email | VARCHAR(255) | Current email | PGP_WEBAPI_v1 |
| password_hash | VARCHAR(255) | bcrypt hash | PGP_WEBAPI_v1 |
| is_active | BOOLEAN | Account active status | PGP_WEBAPI_v1 |
| email_verified | BOOLEAN | Email verified status | PGP_WEBAPI_v1 |
| verification_token | VARCHAR(255) | Email verification token | PGP_WEBAPI_v1 |
| reset_token | VARCHAR(255) | Password reset token | PGP_WEBAPI_v1 |
| pending_email | VARCHAR(255) | New email awaiting verification | PGP_WEBAPI_v1 |
| pending_email_token | VARCHAR(500) | Email change token | PGP_WEBAPI_v1 |

**Service Usage:**

- **PGP_WEBAPI_v1**: User registration, login, password reset, email verification, email change
- **PGP_SERVER_v1**: User lookup for channel ownership verification

**Special Notes:**

- ✅ Legacy user (00000000-0000-0000-0000-000000000000) created for pre-existing channels
- ✅ Email change workflow: user requests change → pending_email + pending_email_token → verification → email updated

---

#### Table 2: main_clients_database

**Purpose:** Channel configurations and client settings for Telegram channels
**Service:** PGP_SERVER_v1, PGP_ORCHESTRATOR_v1, PGP_BROADCAST_v1
**Primary Key:** id (SERIAL)
**Expected Row Count:** 20+ (grows with channel registrations)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS main_clients_database (
    id SERIAL PRIMARY KEY,
    open_channel_id VARCHAR(14) NOT NULL UNIQUE,
    open_channel_title VARCHAR(30),
    open_channel_description VARCHAR(140),
    closed_channel_id VARCHAR(14) NOT NULL UNIQUE,
    closed_channel_title VARCHAR(30),
    closed_channel_description VARCHAR(140),
    sub_1_price NUMERIC(10, 2) NOT NULL,
    sub_1_time SMALLINT NOT NULL,
    sub_2_price NUMERIC(10, 2),
    sub_2_time SMALLINT,
    sub_3_price NUMERIC(10, 2),
    sub_3_time SMALLINT,
    client_wallet_address VARCHAR(95) NOT NULL,
    client_payout_currency currency_type NOT NULL,
    client_payout_network network_type,
    payout_strategy VARCHAR(20) DEFAULT 'instant',
    payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
    payout_threshold_updated_at TIMESTAMP,
    client_id UUID NOT NULL,
    created_by VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_channel_donation_message VARCHAR(256) NOT NULL,
    notification_status BOOLEAN NOT NULL DEFAULT FALSE,
    notification_id BIGINT,

    CONSTRAINT fk_client_id FOREIGN KEY (client_id)
        REFERENCES registered_users(user_id) ON DELETE CASCADE,
    CONSTRAINT main_clients_database_sub_1_price_check
        CHECK (sub_1_price > 0 AND (sub_1_price * 100) % 1 = 0),
    CONSTRAINT main_clients_database_sub_1_time_check
        CHECK (sub_1_time > 0),
    CONSTRAINT main_clients_database_sub_2_price_check
        CHECK (sub_2_price IS NULL OR (sub_2_price > 0 AND (sub_2_price * 100) % 1 = 0)),
    CONSTRAINT main_clients_database_sub_2_time_check
        CHECK (sub_2_time IS NULL OR sub_2_time > 0),
    CONSTRAINT main_clients_database_sub_3_price_check
        CHECK (sub_3_price IS NULL OR (sub_3_price > 0 AND (sub_3_price * 100) % 1 = 0)),
    CONSTRAINT main_clients_database_sub_3_time_check
        CHECK (sub_3_time IS NULL OR sub_3_time > 0),
    CONSTRAINT main_clients_database_client_wallet_address_check
        CHECK (octet_length(client_wallet_address) >= 1 AND octet_length(client_wallet_address) <= 95),
    CONSTRAINT main_clients_database_open_channel_id_check
        CHECK (open_channel_id ~ '^-?[0-9]{5,14}$'),
    CONSTRAINT main_clients_database_closed_channel_id_check
        CHECK (closed_channel_id ~ '^-?[0-9]{5,14}$'),
    CONSTRAINT check_donation_message_not_empty
        CHECK (length(TRIM(BOTH FROM closed_channel_donation_message)) > 0),
    CONSTRAINT check_threshold_positive
        CHECK (payout_threshold_usd >= 0),
    CONSTRAINT unique_channel_pair
        UNIQUE (open_channel_id, closed_channel_id)
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_payout_strategy ON main_clients_database(payout_strategy);
CREATE INDEX IF NOT EXISTS idx_main_clients_client_id ON main_clients_database(client_id);
```

**Constraints:**

- ✅ **PK:** id (SERIAL)
- ✅ **FK:** client_id → registered_users.user_id (CASCADE DELETE)
- ✅ **UNIQUE:** open_channel_id, closed_channel_id, (open_channel_id, closed_channel_id)
- ✅ **CHECK:** Subscription prices > 0 and divisible by 0.01
- ✅ **CHECK:** Subscription times > 0
- ✅ **CHECK:** Wallet address length 1-95 bytes
- ✅ **CHECK:** Channel IDs match regex `^-?[0-9]{5,14}$`
- ✅ **CHECK:** Donation message not empty
- ✅ **CHECK:** Threshold >= 0

**Column Descriptions:**

| Column | Type | Purpose | Example |
|--------|------|---------|---------|
| open_channel_id | VARCHAR(14) | Public Telegram channel ID | -1001234567890 |
| closed_channel_id | VARCHAR(14) | Private Telegram channel ID | -1009876543210 |
| sub_1_price | NUMERIC(10, 2) | Tier 1 price (USD) | 10.00 |
| sub_1_time | SMALLINT | Tier 1 duration (days) | 30 |
| client_wallet_address | VARCHAR(95) | Payout wallet address | 0x742d35Cc6634C0... |
| client_payout_currency | currency_type | Payout currency (ENUM) | ETH, USDT, BTC |
| payout_strategy | VARCHAR(20) | instant or threshold | instant |
| payout_threshold_usd | NUMERIC(10, 2) | Threshold amount (USD) | 50.00 |
| notification_status | BOOLEAN | Notification enabled | TRUE |

**Service Usage:**

- **PGP_SERVER_v1**: Channel CRUD operations, subscription tier lookup
- **PGP_WEBAPI_v1**: Channel registration, configuration updates
- **PGP_ORCHESTRATOR_v1**: Payout configuration lookup (wallet, currency, strategy)
- **PGP_BROADCAST_v1**: Channel lookup for broadcast scheduling

**Payout Strategies:**

1. **instant**: Immediate payout after each payment (no accumulation)
2. **threshold**: Accumulate payments until `payout_threshold_usd` reached, then batch payout

---

#### Table 3: private_channel_users_database

**Purpose:** User subscriptions to private Telegram channels
**Service:** PGP_SERVER_v1, PGP_MONITOR_v1 (subscription expiration), PGP_ORCHESTRATOR_v1
**Primary Key:** id (SERIAL)
**Expected Row Count:** 18+ (grows with subscriptions)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS private_channel_users_database (
    id SERIAL PRIMARY KEY,
    private_channel_id VARCHAR(14) NOT NULL,
    user_id BIGINT NOT NULL,
    sub_time SMALLINT NOT NULL,
    sub_price VARCHAR(6) NOT NULL,
    timestamp TIME NOT NULL,
    datestamp DATE NOT NULL,
    expire_time TIME NOT NULL,
    expire_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL,
    nowpayments_payment_id VARCHAR(50),
    nowpayments_invoice_id VARCHAR(50),
    nowpayments_order_id VARCHAR(100),
    nowpayments_pay_address VARCHAR(255),
    nowpayments_payment_status VARCHAR(50),
    nowpayments_pay_amount NUMERIC(30, 18),
    nowpayments_pay_currency VARCHAR(20),
    nowpayments_outcome_amount NUMERIC(30, 18),
    nowpayments_created_at TIMESTAMP,
    nowpayments_updated_at TIMESTAMP,
    nowpayments_price_amount NUMERIC(20, 8),
    nowpayments_price_currency VARCHAR(10),
    nowpayments_outcome_currency VARCHAR(10),
    nowpayments_outcome_amount_usd NUMERIC(20, 8),
    payment_status VARCHAR(20) DEFAULT 'pending'
);
```

**Indexes:**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS unique_user_channel_pair
    ON private_channel_users_database(user_id, private_channel_id);
CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
    ON private_channel_users_database(nowpayments_payment_id);
CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id
    ON private_channel_users_database(nowpayments_order_id);
CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id_status
    ON private_channel_users_database(nowpayments_order_id, payment_status);
```

**Constraints:**

- ✅ **PK:** id (SERIAL)
- ✅ **UNIQUE:** (user_id, private_channel_id) - One active subscription per user per channel

**Column Descriptions:**

| Column | Type | Purpose | Managed By |
|--------|------|---------|------------|
| user_id | BIGINT | Telegram user ID | PGP_ORCHESTRATOR_v1 |
| private_channel_id | VARCHAR(14) | Private channel ID | PGP_ORCHESTRATOR_v1 |
| expire_date | DATE | Subscription expiration date | PGP_ORCHESTRATOR_v1 |
| is_active | BOOLEAN | Subscription active status | PGP_MONITOR_v1 |
| nowpayments_payment_id | VARCHAR(50) | NOWPayments payment ID | PGP_NP_IPN_v1 |
| nowpayments_order_id | VARCHAR(100) | NOWPayments order ID | PGP_ORCHESTRATOR_v1 |
| payment_status | VARCHAR(20) | Payment status | PGP_NP_IPN_v1 |

**Service Usage:**

- **PGP_SERVER_v1**: Subscription queries, expiration monitoring (every 5 minutes)
- **PGP_ORCHESTRATOR_v1**: Create subscription entries after payment confirmation
- **PGP_NP_IPN_v1**: Update payment status from NOWPayments IPN webhooks
- **PGP_INVITE_v1**: Verify subscription before sending Telegram invite

**Expiration Logic:**

- **PGP_SERVER_v1** runs background task every 5 minutes
- Checks for `is_active = TRUE AND expire_date < CURRENT_DATE`
- Sets `is_active = FALSE` and removes user from Telegram channel

---

### CATEGORY 2: PAYMENT PROCESSING

---

#### Table 4: processed_payments

**Purpose:** Tracks payment processing status and Telegram invite delivery (idempotency)
**Service:** PGP_ORCHESTRATOR_v1, PGP_INVITE_v1
**Primary Key:** payment_id (BIGINT)
**Expected Row Count:** 42+ (grows with payments)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS processed_payments (
    payment_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,
    telegram_invite_sent BOOLEAN DEFAULT FALSE,
    telegram_invite_sent_at TIMESTAMP,
    telegram_invite_link TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT payment_id_positive CHECK (payment_id > 0),
    CONSTRAINT user_id_positive CHECK (user_id > 0)
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_processed_payments_user_channel
    ON processed_payments(user_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_processed_payments_invite_status
    ON processed_payments(telegram_invite_sent);
CREATE INDEX IF NOT EXISTS idx_processed_payments_webhook1_status
    ON processed_payments(gcwebhook1_processed);
CREATE INDEX IF NOT EXISTS idx_processed_payments_created_at
    ON processed_payments(created_at DESC);
```

**Constraints:**

- ✅ **PK:** payment_id (NOWPayments payment_id)
- ✅ **CHECK:** payment_id > 0, user_id > 0

**Column Descriptions:**

| Column | Type | Purpose | Managed By |
|--------|------|---------|------------|
| payment_id | BIGINT | NOWPayments payment ID (PK) | PGP_ORCHESTRATOR_v1 |
| gcwebhook1_processed | BOOLEAN | Payment processed flag | PGP_ORCHESTRATOR_v1 |
| telegram_invite_sent | BOOLEAN | Invite sent flag | PGP_INVITE_v1 |
| telegram_invite_link | TEXT | One-time Telegram invite link | PGP_INVITE_v1 |

**Service Usage:**

- **PGP_ORCHESTRATOR_v1**: Insert entry when processing payment (idempotency check)
- **PGP_INVITE_v1**: Check if invite already sent, then send and update

**Legacy Naming:**

- ⚠️ `gcwebhook1_processed` - Legacy column name from old GCWebhook1 service
- ✅ Naming preserved for backward compatibility

**Idempotency Pattern:**

```python
# PGP_ORCHESTRATOR_v1 checks before processing
if payment_id already in processed_payments:
    logger.info("Payment already processed (idempotent)")
    return

# Process payment
insert into processed_payments (payment_id, user_id, channel_id, gcwebhook1_processed=TRUE)
```

---

#### Table 5: payout_accumulation

**Purpose:** Accumulates payments for threshold-based payouts
**Service:** PGP_ORCHESTRATOR_v1 (inline accumulation), PGP_MICROBATCHPROCESSOR_v1
**Primary Key:** id (SERIAL)
**Expected Row Count:** 101+ (grows with threshold-strategy payments)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS payout_accumulation (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(14) NOT NULL,
    user_id BIGINT NOT NULL,
    subscription_id INTEGER,
    payment_amount_usd NUMERIC(10, 2) NOT NULL,
    payment_currency VARCHAR(10) NOT NULL,
    payment_timestamp TIMESTAMP NOT NULL,
    accumulated_amount_usdt NUMERIC(18, 8) NOT NULL,
    eth_to_usdt_rate NUMERIC(18, 8),
    conversion_timestamp TIMESTAMP,
    conversion_tx_hash VARCHAR(100),
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,
    is_paid_out BOOLEAN DEFAULT FALSE,
    payout_batch_id VARCHAR(50),
    paid_out_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversion_status VARCHAR(50) DEFAULT 'pending',
    conversion_attempts INTEGER DEFAULT 0,
    last_conversion_attempt TIMESTAMP,
    batch_conversion_id UUID,
    nowpayments_payment_id VARCHAR(50),
    nowpayments_pay_address VARCHAR(255),
    nowpayments_outcome_amount NUMERIC(30, 18),
    nowpayments_network_fee NUMERIC(30, 18),
    payment_fee_usd NUMERIC(20, 8),

    CONSTRAINT fk_batch_conversion
        FOREIGN KEY (batch_conversion_id)
        REFERENCES batch_conversions(batch_conversion_id)
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_client_pending ON payout_accumulation(client_id, is_paid_out);
CREATE INDEX IF NOT EXISTS idx_payout_batch ON payout_accumulation(payout_batch_id);
CREATE INDEX IF NOT EXISTS idx_user ON payout_accumulation(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_timestamp ON payout_accumulation(payment_timestamp);
CREATE INDEX IF NOT EXISTS idx_payout_accumulation_conversion_status ON payout_accumulation(conversion_status);
CREATE INDEX IF NOT EXISTS idx_payout_accumulation_batch_conversion ON payout_accumulation(batch_conversion_id);
CREATE INDEX IF NOT EXISTS idx_payout_nowpayments_payment_id ON payout_accumulation(nowpayments_payment_id);
CREATE INDEX IF NOT EXISTS idx_payout_pay_address ON payout_accumulation(nowpayments_pay_address);
```

**Constraints:**

- ✅ **PK:** id (SERIAL)
- ✅ **FK:** batch_conversion_id → batch_conversions.batch_conversion_id

**Column Descriptions:**

| Column | Type | Purpose | Managed By |
|--------|------|---------|------------|
| client_id | VARCHAR(14) | Channel ID accumulating payments | PGP_ORCHESTRATOR_v1 |
| payment_amount_usd | NUMERIC(10, 2) | Payment amount (USD) | PGP_ORCHESTRATOR_v1 |
| accumulated_amount_usdt | NUMERIC(18, 8) | USDT equivalent amount | PGP_MICROBATCHPROCESSOR_v1 |
| eth_to_usdt_rate | NUMERIC(18, 8) | ETH→USDT conversion rate | PGP_MICROBATCHPROCESSOR_v1 |
| is_paid_out | BOOLEAN | Payout completed flag | PGP_BATCHPROCESSOR_v1 |
| conversion_status | VARCHAR(50) | pending, completed, failed | PGP_MICROBATCHPROCESSOR_v1 |
| batch_conversion_id | UUID | FK to batch_conversions | PGP_MICROBATCHPROCESSOR_v1 |

**Service Usage:**

- **PGP_ORCHESTRATOR_v1**: Insert entry for threshold-strategy payments (inline accumulation)
- **PGP_MICROBATCHPROCESSOR_v1**: Convert accumulated ETH → USDT (every 15 minutes)
- **PGP_BATCHPROCESSOR_v1**: Detect threshold reached, create payouts (every 5 minutes)

**Accumulation Flow:**

```
Payment Received (threshold strategy)
    ↓
PGP_ORCHESTRATOR_v1: Insert into payout_accumulation (conversion_status='pending')
    ↓
PGP_MICROBATCHPROCESSOR_v1 (every 15min): Convert ETH → USDT, update conversion_status='completed'
    ↓
PGP_BATCHPROCESSOR_v1 (every 5min): Check SUM(accumulated_amount_usdt) >= payout_threshold_usd
    ↓
Threshold Reached: Trigger payout pipeline (SPLIT → HOSTPAY)
```

---

#### Table 6: payout_batches

**Purpose:** Tracks batch payout transactions to clients
**Service:** PGP_MICROBATCHPROCESSOR_v1, PGP_BATCHPROCESSOR_v1, PGP_HOSTPAY_v1
**Primary Key:** batch_id (VARCHAR)
**Expected Row Count:** 33+ (grows with batch payouts)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS payout_batches (
    batch_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(14) NOT NULL,
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,
    total_amount_usdt NUMERIC(18, 8) NOT NULL,
    total_payments_count INTEGER NOT NULL,
    payout_amount_crypto NUMERIC(18, 8),
    usdt_to_crypto_rate NUMERIC(18, 8),
    conversion_fee NUMERIC(18, 8),
    cn_api_id VARCHAR(100),
    cn_payin_address VARCHAR(200),
    tx_hash VARCHAR(100),
    tx_status VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_client_batch ON payout_batches(client_id);
CREATE INDEX IF NOT EXISTS idx_status_batch ON payout_batches(status);
CREATE INDEX IF NOT EXISTS idx_created_batch ON payout_batches(created_at);
```

**Constraints:**

- ✅ **PK:** batch_id (VARCHAR)

**Column Descriptions:**

| Column | Type | Purpose | Managed By |
|--------|------|---------|------------|
| batch_id | VARCHAR(50) | Unique batch ID | PGP_BATCHPROCESSOR_v1 |
| client_id | VARCHAR(14) | Channel ID receiving payout | PGP_BATCHPROCESSOR_v1 |
| total_amount_usdt | NUMERIC(18, 8) | Total USDT to payout | PGP_BATCHPROCESSOR_v1 |
| total_payments_count | INTEGER | Number of payments batched | PGP_BATCHPROCESSOR_v1 |
| cn_api_id | VARCHAR(100) | ChangeNOW transaction ID | PGP_HOSTPAY_v1 |
| tx_hash | VARCHAR(100) | Blockchain transaction hash | PGP_HOSTPAY3_v1 |
| status | VARCHAR(20) | pending, completed, failed | PGP_HOSTPAY_v1 |

**Service Usage:**

- **PGP_BATCHPROCESSOR_v1**: Create batch entry when threshold reached
- **PGP_HOSTPAY_v1**: Update batch status during payout pipeline

**Batch Payout Statuses:**

1. **pending**: Batch created, awaiting processing
2. **processing**: Payout pipeline in progress
3. **completed**: Payout successfully sent to client wallet
4. **failed**: Payout failed (manual intervention required)

---

### CATEGORY 3: CONVERSION PIPELINE

---

#### Table 7: batch_conversions

**Purpose:** Tracks ETH→USDT batch conversions via ChangeNOW
**Service:** PGP_MICROBATCHPROCESSOR_v1
**Primary Key:** id (SERIAL)
**Expected Row Count:** 29+ (grows with batch conversions)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS batch_conversions (
    id SERIAL PRIMARY KEY,
    batch_conversion_id UUID NOT NULL UNIQUE,
    total_eth_usd NUMERIC(20, 8) NOT NULL,
    threshold_at_creation NUMERIC(20, 2) NOT NULL,
    cn_api_id VARCHAR(255),
    payin_address VARCHAR(255),
    conversion_status VARCHAR(20) DEFAULT 'pending',
    actual_usdt_received NUMERIC(20, 8),
    conversion_tx_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_batch_conversions_status ON batch_conversions(conversion_status);
CREATE INDEX IF NOT EXISTS idx_batch_conversions_cn_api_id ON batch_conversions(cn_api_id);
CREATE INDEX IF NOT EXISTS idx_batch_conversions_created ON batch_conversions(created_at);
```

**Constraints:**

- ✅ **PK:** id (SERIAL)
- ✅ **UNIQUE:** batch_conversion_id (UUID)

**Column Descriptions:**

| Column | Type | Purpose | Managed By |
|--------|------|---------|------------|
| batch_conversion_id | UUID | Unique batch ID | PGP_MICROBATCHPROCESSOR_v1 |
| total_eth_usd | NUMERIC(20, 8) | Total ETH to convert (USD value) | PGP_MICROBATCHPROCESSOR_v1 |
| threshold_at_creation | NUMERIC(20, 2) | Minimum threshold for conversion | PGP_MICROBATCHPROCESSOR_v1 |
| cn_api_id | VARCHAR(255) | ChangeNOW transaction ID | PGP_MICROBATCHPROCESSOR_v1 |
| conversion_status | VARCHAR(20) | pending, completed, failed | PGP_MICROBATCHPROCESSOR_v1 |
| actual_usdt_received | NUMERIC(20, 8) | USDT received after conversion | PGP_MICROBATCHPROCESSOR_v1 |

**Service Usage:**

- **PGP_MICROBATCHPROCESSOR_v1**: Create batch conversion when accumulated ETH ≥ $5 USD

**Conversion Threshold:** Minimum $5 USD in accumulated ETH before triggering conversion

---

#### Tables 8-10: Split Payout Pipeline

These three tables work together to handle the **client portion** of split payouts (60% to client, 40% to host).

---

**Table 8: split_payout_request**

**Purpose:** Stores split payout requests (client portion)
**Service:** PGP_ORCHESTRATOR_v1 (create), PGP_SPLIT1_v1 (read)
**Primary Key:** unique_id (CHAR(16))
**Expected Row Count:** 95+ (grows with instant-strategy payments)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS split_payout_request (
    unique_id CHAR(16) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    closed_channel_id VARCHAR(14),
    from_currency currency_type NOT NULL,
    to_currency currency_type NOT NULL,
    from_network network_type NOT NULL,
    to_network network_type NOT NULL,
    from_amount NUMERIC(20, 8),
    to_amount NUMERIC(30, 8),
    client_wallet_address VARCHAR(95) NOT NULL,
    refund_address VARCHAR(95),
    flow flow_type NOT NULL DEFAULT 'standard',
    type type_type NOT NULL DEFAULT 'direct',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actual_eth_amount NUMERIC(20, 18) DEFAULT 0,

    CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0),
    CONSTRAINT split_payout_request_from_amount_check CHECK (from_amount IS NULL OR from_amount >= 0),
    CONSTRAINT split_payout_request_to_amount_check CHECK (to_amount IS NULL OR to_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_split_payout_request_actual_eth
    ON split_payout_request(actual_eth_amount) WHERE actual_eth_amount > 0;
```

---

**Table 9: split_payout_que**

**Purpose:** Queue for split payout processing (with ChangeNOW exchange details)
**Service:** PGP_SPLIT1_v1 (insert), PGP_SPLIT2_v1 (process), PGP_SPLIT3_v1 (execute)
**Primary Key:** unique_id (CHAR(16))
**Expected Row Count:** 71+ (grows with split payouts)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS split_payout_que (
    unique_id CHAR(16) PRIMARY KEY,
    cn_api_id VARCHAR(14) NOT NULL,
    user_id BIGINT NOT NULL,
    closed_channel_id VARCHAR(14) NOT NULL,
    from_currency currency_type NOT NULL,
    to_currency currency_type NOT NULL,
    from_network network_type NOT NULL,
    to_network network_type NOT NULL,
    from_amount NUMERIC(20, 8),
    to_amount NUMERIC(30, 8),
    payin_address VARCHAR(95) NOT NULL,
    payout_address VARCHAR(95) NOT NULL,
    refund_address VARCHAR(95),
    flow flow_type NOT NULL DEFAULT 'standard',
    type type_type NOT NULL DEFAULT 'direct',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actual_eth_amount NUMERIC(20, 18) DEFAULT 0,

    CONSTRAINT actual_eth_positive_que CHECK (actual_eth_amount >= 0),
    CONSTRAINT split_payout_que_from_amount_check CHECK (from_amount IS NULL OR from_amount >= 0),
    CONSTRAINT split_payout_que_to_amount_check CHECK (to_amount IS NULL OR to_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_split_payout_que_actual_eth
    ON split_payout_que(actual_eth_amount) WHERE actual_eth_amount > 0;
```

---

**Table 10: split_payout_hostpay**

**Purpose:** Tracks host payment portion (40%) of split payouts
**Service:** PGP_SPLIT1_v1 (create), PGP_HOSTPAY1_v1 (process), PGP_HOSTPAY2_v1 (monitor), PGP_HOSTPAY3_v1 (execute)
**Primary Key:** None (uses unique_id + cn_api_id composite)
**Expected Row Count:** 51+ (grows with split payouts)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS split_payout_hostpay (
    unique_id VARCHAR(64) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency currency_type NOT NULL,
    from_network network_type NOT NULL,
    from_amount NUMERIC(20, 8) NOT NULL,
    payin_address VARCHAR(95) NOT NULL,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tx_hash VARCHAR(66),
    tx_status VARCHAR(20) DEFAULT 'pending',
    gas_used INTEGER,
    block_number INTEGER,
    actual_eth_amount NUMERIC(20, 18) DEFAULT 0,

    CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_split_payout_hostpay_actual_eth
    ON split_payout_hostpay(actual_eth_amount) WHERE actual_eth_amount > 0;
```

---

**Split Payout Pipeline Flow:**

```
Payment Received (instant strategy) - $100 USD payment
    ↓
PGP_ORCHESTRATOR_v1: Create split_payout_request
    - Client portion: $60 USD (60%)
    - Host portion: $40 USD (40%)
    ↓
PGP_SPLIT1_v1: Estimate exchange (USDT → client_payout_currency)
    - Create split_payout_que entry (client payout)
    - Create split_payout_hostpay entry (host payout)
    - Submit ChangeNOW exchange requests
    ↓
PGP_SPLIT2_v1: Monitor exchange completion (client portion)
    - Update split_payout_que with payin_address
    ↓
PGP_SPLIT3_v1: Execute ETH payment to ChangeNOW (client portion)
    - Send ETH to payin_address
    - ChangeNOW completes USDT → client_payout_currency swap
    - Client receives payout in their wallet
    ↓
PGP_HOSTPAY1_v1: Validate and orchestrate (host portion)
    ↓
PGP_HOSTPAY2_v1: Monitor ChangeNOW status (host portion)
    ↓
PGP_HOSTPAY3_v1: Execute ETH payment to ChangeNOW (host portion)
    - Send ETH to payin_address
    - ChangeNOW completes swap to USDT
    - Host receives USDT in company wallet
```

---

### CATEGORY 4: FEATURE TABLES

---

#### Table 11: broadcast_manager

**Purpose:** Manages scheduled broadcast messages to channels
**Service:** PGP_BROADCAST_v1
**Primary Key:** id (UUID)
**Expected Row Count:** 20+ (one per registered channel)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS broadcast_manager (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    open_channel_id TEXT NOT NULL UNIQUE,
    closed_channel_id TEXT NOT NULL UNIQUE,
    last_sent_time TIMESTAMPTZ,
    next_send_time TIMESTAMPTZ DEFAULT NOW(),
    broadcast_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    last_manual_trigger_time TIMESTAMPTZ,
    manual_trigger_count INTEGER DEFAULT 0,
    total_broadcasts INTEGER DEFAULT 0,
    successful_broadcasts INTEGER DEFAULT 0,
    failed_broadcasts INTEGER DEFAULT 0,
    last_error_message TEXT,
    last_error_time TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_open_message_id BIGINT,
    last_closed_message_id BIGINT,
    last_open_message_sent_at TIMESTAMP,
    last_closed_message_sent_at TIMESTAMP,

    CONSTRAINT fk_broadcast_client_id
        FOREIGN KEY (client_id)
        REFERENCES registered_users(user_id) ON DELETE CASCADE,
    CONSTRAINT valid_broadcast_status
        CHECK (broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    CONSTRAINT unique_channel_pair_broadcast
        UNIQUE (open_channel_id, closed_channel_id)
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_broadcast_next_send
    ON broadcast_manager(next_send_time) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_broadcast_client ON broadcast_manager(client_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_status
    ON broadcast_manager(broadcast_status) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_broadcast_open_channel ON broadcast_manager(open_channel_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_manager_open_message
    ON broadcast_manager(last_open_message_id) WHERE last_open_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broadcast_manager_closed_message
    ON broadcast_manager(last_closed_message_id) WHERE last_closed_message_id IS NOT NULL;
```

**Constraints:**

- ✅ **PK:** id (UUID)
- ✅ **FK:** client_id → registered_users.user_id (CASCADE DELETE)
- ✅ **UNIQUE:** open_channel_id, closed_channel_id, (open_channel_id, closed_channel_id)
- ✅ **CHECK:** broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')

**Service Usage:**

- **PGP_BROADCAST_v1**: Schedule and execute broadcasts (every 24 hours default)

**Broadcast Types:**

1. **Scheduled broadcasts**: Automated daily broadcasts (next_send_time updated after each send)
2. **Manual broadcasts**: Triggered by channel owner via API

---

#### Table 12: donation_keypad_state

**Purpose:** Stores donation keypad input state for users
**Service:** PGP_DONATIONS_v1 (deprecated in PGP_v1, kept for schema compatibility)
**Primary Key:** user_id (BIGINT)
**Expected Row Count:** 1+ (grows with active donation users)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS donation_keypad_state (
    user_id BIGINT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    current_amount TEXT NOT NULL DEFAULT '',
    decimal_entered BOOLEAN NOT NULL DEFAULT FALSE,
    state_type VARCHAR(20) NOT NULL DEFAULT 'keypad_input',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_state_type
        CHECK (state_type IN ('keypad_input', 'text_input', 'awaiting_confirmation')),
    CONSTRAINT valid_amount_format
        CHECK (current_amount ~ '^[0-9]*\.?[0-9]*$' AND length(current_amount) <= 10)
);

CREATE INDEX IF NOT EXISTS idx_donation_state_updated_at ON donation_keypad_state(updated_at);
CREATE INDEX IF NOT EXISTS idx_donation_state_channel ON donation_keypad_state(channel_id);
```

**Note:** Donation keypad UI was deprecated in PGP_v1 architecture (donation flow simplified). Table kept for schema preservation.

---

#### Table 13: user_conversation_state

**Purpose:** Stores bot conversation state (generic state management)
**Service:** PGP_BOT_v1 (deprecated in PGP_v1, kept for schema compatibility)
**Primary Key:** (user_id, conversation_type) composite
**Expected Row Count:** 1+ (grows with active bot users)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS user_conversation_state (
    user_id BIGINT NOT NULL,
    conversation_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (user_id, conversation_type)
);

CREATE INDEX IF NOT EXISTS idx_conversation_state_updated ON user_conversation_state(updated_at);
```

**Note:** Generic conversation state management deprecated in PGP_v1 (conversation flows refactored to stateless design). Table kept for schema preservation.

---

### CATEGORY 5: UTILITY TABLES

---

#### Table 14: currency_to_network

**Purpose:** Maps supported currencies to their networks (reference table)
**Service:** Referenced by all payment services
**Primary Key:** None (reference lookup table)
**Expected Row Count:** 87 (static reference data)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS currency_to_network (
    currency VARCHAR(6) NOT NULL,
    network VARCHAR(8) NOT NULL,
    currency_name VARCHAR(17),
    network_name VARCHAR(17)
);
```

**Sample Data:**

| currency | network | currency_name | network_name |
|----------|---------|---------------|--------------|
| BTC | BTC | Bitcoin | Bitcoin |
| ETH | ETH | Ethereum | Ethereum |
| USDT | ETH | Tether | Ethereum |
| USDT | TRX | Tether | Tron |
| USDT | BSC | Tether | BSC |

**Service Usage:**

- **PGP_ORCHESTRATOR_v1**: Validate currency/network pairs
- **PGP_SPLIT1_v1**: Lookup network for currency swaps
- **PGP_WEBAPI_v1**: Provide currency/network options to frontend

**Deployment:** Populated via migration script `/TOOLS_SCRIPTS_TESTS/migrations/002_populate_currency_to_network.sql`

---

#### Table 15: failed_transactions

**Purpose:** Tracks failed ChangeNOW transactions for manual recovery
**Service:** PGP_ORCHESTRATOR_v1, PGP_SPLIT_v1, PGP_HOSTPAY_v1
**Primary Key:** id (SERIAL)
**Expected Row Count:** 21+ (low volume, errors only)

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS failed_transactions (
    id SERIAL PRIMARY KEY,
    unique_id VARCHAR(16) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    from_network VARCHAR(10) NOT NULL,
    from_amount NUMERIC(18, 8) NOT NULL,
    payin_address VARCHAR(100) NOT NULL,
    context VARCHAR(20) NOT NULL DEFAULT 'instant',
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    last_error_details JSONB,
    attempt_count INTEGER NOT NULL DEFAULT 3,
    last_attempt_timestamp TIMESTAMP NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'failed_pending_review',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_attempt TIMESTAMP,
    recovery_tx_hash VARCHAR(100),
    recovered_at TIMESTAMP,
    recovered_by VARCHAR(50),
    admin_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Indexes:**

```sql
CREATE INDEX IF NOT EXISTS idx_failed_transactions_unique_id ON failed_transactions(unique_id);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_cn_api_id ON failed_transactions(cn_api_id);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_status ON failed_transactions(status);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_error_code ON failed_transactions(error_code);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_created_at ON failed_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_retry
    ON failed_transactions(status, error_code, created_at)
    WHERE status IN ('failed_retryable', 'retry_scheduled');
```

**Constraints:**

- ✅ **PK:** id (SERIAL)

**Service Usage:**

- **PGP_ORCHESTRATOR_v1**: Insert failed transactions from payment processing
- **PGP_SPLIT_v1**: Insert failed ChangeNOW exchanges
- **PGP_HOSTPAY_v1**: Insert failed ETH payment executions

**Failure Contexts:**

1. **instant**: Failed instant payment (split payout)
2. **threshold**: Failed threshold payment (batch payout)
3. **micro_batch**: Failed micro-batch conversion
4. **batch**: Failed batch payout

**Recovery Statuses:**

- **failed_pending_review**: Requires manual review by admin
- **failed_retryable**: Automatic retry scheduled
- **retry_scheduled**: Retry in progress
- **recovered**: Manually recovered by admin

---

## Service-to-Table Mapping

### PGP_v1 Services (15 Services)

| Service | Tables Accessed | Access Type | Purpose |
|---------|-----------------|-------------|---------|
| **PGP_SERVER_v1** | registered_users | READ/WRITE | User lookup, auth |
| | main_clients_database | READ | Channel configs |
| | private_channel_users_database | READ/WRITE | Subscription monitoring |
| **PGP_WEBAPI_v1** | registered_users | READ/WRITE | User registration, login |
| | main_clients_database | READ/WRITE | Channel registration |
| **PGP_NP_IPN_v1** | private_channel_users_database | WRITE | Payment status updates |
| | processed_payments | READ | Idempotency check |
| **PGP_ORCHESTRATOR_v1** | private_channel_users_database | WRITE | Create subscriptions |
| | main_clients_database | READ | Channel configs |
| | processed_payments | WRITE | Payment tracking |
| | failed_transactions | WRITE | Error handling |
| | split_payout_request | WRITE | Create split requests |
| | payout_accumulation | WRITE | Threshold accumulation |
| **PGP_INVITE_v1** | processed_payments | READ/WRITE | Invite delivery |
| | private_channel_users_database | READ | Subscription verification |
| **PGP_SPLIT1_v1** | split_payout_request | READ | Read split requests |
| | split_payout_que | WRITE | Create queue entries |
| | split_payout_hostpay | WRITE | Create host payments |
| **PGP_SPLIT2_v1** | split_payout_que | READ/WRITE | Monitor exchanges |
| **PGP_SPLIT3_v1** | split_payout_que | READ/WRITE | Execute ETH payments |
| **PGP_HOSTPAY1_v1** | split_payout_hostpay | READ/WRITE | Validate host payments |
| **PGP_HOSTPAY2_v1** | split_payout_hostpay | READ/WRITE | Monitor exchanges |
| **PGP_HOSTPAY3_v1** | split_payout_hostpay | READ/WRITE | Execute ETH payments |
| **PGP_BATCHPROCESSOR_v1** | payout_accumulation | READ | Detect thresholds |
| | payout_batches | WRITE | Create batches |
| **PGP_MICROBATCHPROCESSOR_v1** | payout_accumulation | READ/WRITE | Convert ETH → USDT |
| | batch_conversions | WRITE | Track conversions |
| **PGP_NOTIFICATIONS_v1** | processed_payments | READ | Payment confirmation |
| **PGP_BROADCAST_v1** | broadcast_manager | READ/WRITE | Schedule broadcasts |
| | main_clients_database | READ | Channel lookup |

---

## Migration Scripts & Verification

### Available Migration Scripts

Located in `/TOOLS_SCRIPTS_TESTS/migrations/`

#### 1. Complete Schema Creation

**File:** `001_create_complete_schema.sql`
**Purpose:** Deploy complete database schema (ENUMs + tables + indexes + constraints)
**Target Database:** pgp-live-db
**Deployment:**

```bash
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/001_create_complete_schema.sql
```

**Contents:**

- 4 ENUM types (currency_type, network_type, flow_type, type_type)
- 15 operational tables
- 50+ indexes
- 30+ constraints
- 1 legacy user insert

**Expected Output:**

```
CREATE TYPE
CREATE TYPE
CREATE TYPE
CREATE TYPE
CREATE TABLE
CREATE INDEX
...
COMMIT
✅ PayGatePrime Schema Creation Complete
📊 Created 15 tables with indexes and constraints
🔐 Created 4 custom ENUM types
👤 Created legacy_system user for existing data
```

---

#### 2. Currency/Network Mapping Population

**File:** `002_populate_currency_to_network.sql`
**Purpose:** Populate currency_to_network reference table with 87 entries
**Target Database:** pgp-live-db
**Deployment:**

```bash
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/002_populate_currency_to_network.sql
```

**Expected Output:**

```
INSERT 0 87
✅ Currency/network mappings populated successfully
```

---

#### 3. PGP-Live Specific Schema

**File:** `pgp-live/001_pgp_live_complete_schema.sql`
**Purpose:** PGP-live project specific schema (excludes deprecated tables)
**Target Database:** pgp-live-db
**Deployment:**

```bash
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/pgp-live/001_pgp_live_complete_schema.sql
```

**Differences from 001_create_complete_schema.sql:**

- ❌ Excludes: donation_keypad_state (deprecated)
- ❌ Excludes: user_conversation_state (deprecated)
- ✅ Includes: 13 core operational tables only

---

### Verification Scripts

Located in `/TOOLS_SCRIPTS_TESTS/tools/`

#### 1. Schema Verification

**File:** `verify_pgp_live_schema.py`
**Purpose:** Verify pgp-live-db schema matches expected structure
**Usage:**

```bash
python3 /path/to/TOOLS_SCRIPTS_TESTS/tools/verify_pgp_live_schema.py
```

**Checks:**

- ✅ Database pgp-live-db exists
- ✅ 15 tables exist
- ✅ 4 ENUM types exist
- ✅ 87 currency_to_network entries
- ✅ Legacy user exists
- ✅ All indexes created
- ✅ All constraints active

**Expected Output:**

```
🔍 Verifying pgp-live-db schema...
✅ Database: pgp-live-db exists
✅ Tables: 15/15 found
✅ ENUMs: 4/4 found
✅ currency_to_network: 87 entries
✅ Legacy user: exists
✅ Indexes: 50/50 created
✅ Constraints: 30/30 active

🎉 Schema verification complete - all checks passed!
```

---

#### 2. Schema Comparison

**File:** `verify_schema_match.py`
**Purpose:** Compare pgp-live-db schema with telepaydb schema
**Usage:**

```bash
python3 /path/to/TOOLS_SCRIPTS_TESTS/tools/verify_schema_match.py
```

**Checks:**

- ✅ Table names match
- ✅ Column names match
- ✅ Column types match
- ✅ Indexes match
- ✅ Constraints match

**Expected Output:**

```
🔍 Comparing schemas: telepaydb vs pgp-live-db...
✅ Table count: 15 = 15
✅ Column count: 200 = 200
✅ Index count: 50 = 50
✅ Constraint count: 30 = 30

🎉 Schemas match perfectly!
```

---

## Rollback Strategy

### Rollback Scripts

Located in `/TOOLS_SCRIPTS_TESTS/migrations/`

#### 1. Complete Schema Rollback

**File:** `001_rollback.sql`
**Purpose:** Drop all tables, indexes, constraints, and ENUM types
**Target Database:** pgp-live-db
**Deployment:**

```bash
psql "host=127.0.0.1 port=5432 dbname=pgp-live-db user=postgres" \
    -f /path/to/TOOLS_SCRIPTS_TESTS/migrations/001_rollback.sql
```

**Actions:**

- ❌ DROP TABLE (15 tables) CASCADE
- ❌ DROP TYPE (4 ENUM types) CASCADE
- ❌ All indexes and constraints dropped automatically (CASCADE)

**Expected Output:**

```
DROP TABLE
DROP TABLE
...
DROP TYPE
DROP TYPE
DROP TYPE
DROP TYPE
✅ Complete schema rollback successful
⚠️  All data in pgp-live-db has been deleted
```

**⚠️ WARNING:** This is a **destructive operation**. All data will be lost. Use only for greenfield redeployment.

---

## Post-Deployment Validation

### Validation Checklist

After deploying the pgp-live-db schema, complete the following validation steps:

#### Phase 1: Schema Validation

- [ ] Connect to pgp-live-db via Cloud SQL Proxy
- [ ] Run verification script: `verify_pgp_live_schema.py`
- [ ] Verify all 15 tables created: `\dt`
- [ ] Verify all 4 ENUM types created: `\dT`
- [ ] Verify currency_to_network has 87 entries: `SELECT COUNT(*) FROM currency_to_network;`
- [ ] Verify legacy user exists: `SELECT * FROM registered_users WHERE username = 'legacy_system';`

#### Phase 2: Index Validation

- [ ] Verify all indexes created: `\di`
- [ ] Check partial indexes: `SELECT * FROM pg_indexes WHERE schemaname = 'public';`
- [ ] Verify unique constraints: `SELECT * FROM pg_constraint WHERE contype = 'u';`

#### Phase 3: Foreign Key Validation

- [ ] Verify FK: main_clients_database.client_id → registered_users.user_id
- [ ] Verify FK: broadcast_manager.client_id → registered_users.user_id
- [ ] Verify FK: payout_accumulation.batch_conversion_id → batch_conversions.batch_conversion_id

#### Phase 4: Service Connection Validation

- [ ] Deploy PGP_SERVER_v1 to Cloud Run
- [ ] Verify PGP_SERVER_v1 can connect to pgp-live-db
- [ ] Deploy PGP_WEBAPI_v1 to Cloud Run
- [ ] Verify PGP_WEBAPI_v1 can connect to pgp-live-db
- [ ] Deploy remaining 13 PGP_v1 services
- [ ] Verify all services can connect to pgp-live-db

#### Phase 5: Data Integrity Validation

- [ ] Create test user via PGP_WEBAPI_v1: `POST /api/auth/signup`
- [ ] Register test channel via PGP_WEBAPI_v1: `POST /api/channels/register`
- [ ] Verify test data in registered_users and main_clients_database
- [ ] Delete test data: `DELETE FROM registered_users WHERE email = 'test@example.com';`

---

## Summary

### What Changed: Database Name Only

| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Database Name** | telepaydb | **pgp-live-db** | ✅ **CHANGED** |
| **Project ID** | telepay-459221 | pgp-live | ✅ New project |
| **PSQL Instance** | telepaypsql | pgp-live-psql | ✅ New instance |

### What Stayed the Same: Everything Else

| Aspect | Status | Details |
|--------|--------|---------|
| **Table Names** | ✅ **PRESERVED** | All 15 tables (same names) |
| **Column Names** | ✅ **PRESERVED** | All ~200 columns (same names) |
| **Data Types** | ✅ **PRESERVED** | All column types (same) |
| **ENUM Types** | ✅ **PRESERVED** | 4 ENUM types (same values) |
| **Indexes** | ✅ **PRESERVED** | 50+ indexes (same definitions) |
| **Constraints** | ✅ **PRESERVED** | 30+ constraints (same logic) |
| **Foreign Keys** | ✅ **PRESERVED** | 3 FK relationships (same) |

### Deployment Summary

**Total Deployment Steps:** 6 phases

1. ✅ Create Cloud SQL instance (pgp-live-psql)
2. ✅ Create database (pgp-live-db)
3. ✅ Deploy ENUM types (4 types)
4. ✅ Deploy tables (15 tables + 50+ indexes)
5. ✅ Populate currency_to_network (87 entries)
6. ✅ Insert legacy user (UUID 00000000-0000-0000-0000-000000000000)

**Verification:** Run `verify_pgp_live_schema.py` to validate complete deployment

**Rollback:** Run `001_rollback.sql` to drop all schema (destructive, use with caution)

---

**End of Documentation**

**Document Version:** 1.0
**Created:** 2025-11-18
**Author:** PGP_v1 Architecture Team
**Status:** ✅ Ready for Deployment
