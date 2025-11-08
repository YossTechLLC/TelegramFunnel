# Database Migration Guide - User Account Management

**Created:** 2025-10-28
**Purpose:** Add user account management and multi-channel dashboard support
**Related:** USER_ACCOUNT_MANAGEMENT_ARCHITECTURE.md

---

## Overview

This migration adds user account functionality to enable:
- User registration with email/username/password
- Multi-channel management (up to 10 channels per user)
- Dashboard for viewing and editing channels
- Secure user-to-channel mapping via UUID

**Tables Modified:**
1. `main_clients_database` - Add `client_id` foreign key
2. `registered_users` - NEW table for user accounts

**Execution Order:**
1. Create `registered_users` table first
2. Create default "legacy" user for existing channels
3. Modify `main_clients_database` to add `client_id`
4. Update existing channels to use legacy `client_id`
5. Add foreign key constraint

---

## Step 1: Create `registered_users` Table

**Purpose:** Store user account information for authentication

```sql
-- ==============================================================================
-- Step 1: Create registered_users Table
-- ==============================================================================

CREATE TABLE registered_users (
    -- Primary Key (UUID generated automatically)
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Authentication Fields
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash with salt

    -- Account Status
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,

    -- Password Reset Tokens
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Create indexes for efficient lookups
CREATE INDEX idx_registered_users_username ON registered_users(username);
CREATE INDEX idx_registered_users_email ON registered_users(email);
CREATE INDEX idx_registered_users_verification_token ON registered_users(verification_token);
CREATE INDEX idx_registered_users_reset_token ON registered_users(reset_token);

-- Verification query
SELECT
    'registered_users table created' as status,
    COUNT(*) as record_count
FROM registered_users;
```

**Expected Result:**
```
status                        | record_count
------------------------------|-------------
registered_users table created|           0
```

---

## Step 2: Create Default "Legacy" User

**Purpose:** Assign existing channels to a default user for backward compatibility

```sql
-- ==============================================================================
-- Step 2: Create Legacy User for Existing Channels
-- ==============================================================================

INSERT INTO registered_users (
    user_id,
    username,
    email,
    password_hash,
    is_active,
    email_verified
) VALUES (
    '00000000-0000-0000-0000-000000000000',  -- Reserved UUID for legacy channels
    'legacy_system',
    'legacy@paygateprime.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5qlcHxqCJzqZ2',  -- Random hash (login disabled)
    FALSE,  -- Account inactive (cannot login)
    FALSE
);

-- Verification query
SELECT
    user_id,
    username,
    email,
    is_active,
    'Legacy user created for existing channels' as note
FROM registered_users
WHERE user_id = '00000000-0000-0000-0000-000000000000';
```

**Expected Result:**
```
user_id                              | username      | email                     | is_active | note
-------------------------------------|---------------|---------------------------|-----------|------
00000000-0000-0000-0000-000000000000 | legacy_system | legacy@paygateprime.com   | false     | Legacy user created for existing channels
```

**Note:** The `legacy_system` user cannot login (is_active = FALSE). This is purely for data migration. Existing channel owners can later claim their channels through an admin interface.

---

## Step 3: Add `client_id` to `main_clients_database`

**Purpose:** Link channels to user accounts

```sql
-- ==============================================================================
-- Step 3: Modify main_clients_database Table
-- ==============================================================================

-- Add client_id column (nullable initially for migration)
ALTER TABLE main_clients_database
ADD COLUMN client_id UUID;

-- Add created_by column for audit trail (username at creation time)
ALTER TABLE main_clients_database
ADD COLUMN created_by VARCHAR(50);

-- Add updated_at column for tracking edits
ALTER TABLE main_clients_database
ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Verification query (columns added but still NULL)
SELECT
    'Columns added to main_clients_database' as status,
    COUNT(*) as total_channels,
    COUNT(client_id) as channels_with_client_id
FROM main_clients_database;
```

**Expected Result:**
```
status                                  | total_channels | channels_with_client_id
----------------------------------------|----------------|------------------------
Columns added to main_clients_database  |            N   |                      0
```

---

## Step 4: Assign Legacy User to Existing Channels

**Purpose:** Update all existing channels to use the legacy `client_id`

```sql
-- ==============================================================================
-- Step 4: Assign Legacy User ID to Existing Channels
-- ==============================================================================

-- Update all existing channels to use legacy client_id
UPDATE main_clients_database
SET
    client_id = '00000000-0000-0000-0000-000000000000',
    created_by = 'legacy_migration',
    updated_at = CURRENT_TIMESTAMP
WHERE client_id IS NULL;

-- Verification query
SELECT
    'Existing channels assigned to legacy user' as status,
    COUNT(*) as total_channels,
    COUNT(client_id) as channels_with_client_id
FROM main_clients_database;
```

**Expected Result:**
```
status                                      | total_channels | channels_with_client_id
--------------------------------------------|----------------|------------------------
Existing channels assigned to legacy user   |            N   |                      N
```

**Note:** All existing channels now have `client_id` set to the legacy user UUID.

---

## Step 5: Add Constraints and Foreign Key

**Purpose:** Enforce data integrity and relationships

```sql
-- ==============================================================================
-- Step 5: Add Constraints to main_clients_database
-- ==============================================================================

-- Make client_id NOT NULL (now that all rows have values)
ALTER TABLE main_clients_database
ALTER COLUMN client_id SET NOT NULL;

-- Add foreign key constraint (cascade delete - remove channels when user deleted)
ALTER TABLE main_clients_database
ADD CONSTRAINT fk_client_id
    FOREIGN KEY (client_id)
    REFERENCES registered_users(user_id)
    ON DELETE CASCADE;

-- Add index for efficient queries by client_id
CREATE INDEX idx_main_clients_client_id ON main_clients_database(client_id);

-- Verification query
SELECT
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'main_clients_database'
    AND tc.constraint_type = 'FOREIGN KEY';
```

**Expected Result:**
```
constraint_name | constraint_type | column_name | foreign_table_name | foreign_column_name
----------------|-----------------|-------------|--------------------|--------------------
fk_client_id    | FOREIGN KEY     | client_id   | registered_users   | user_id
```

---

## Step 6: Verification Queries

**Run these queries to verify the migration:**

### 6.1 Check `registered_users` Table Structure

```sql
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'registered_users'
ORDER BY ordinal_position;
```

**Expected Columns:**
- user_id (UUID, NOT NULL, PK)
- username (VARCHAR(50), NOT NULL, UNIQUE)
- email (VARCHAR(255), NOT NULL, UNIQUE)
- password_hash (VARCHAR(255), NOT NULL)
- is_active (BOOLEAN, DEFAULT TRUE)
- email_verified (BOOLEAN, DEFAULT FALSE)
- verification_token (VARCHAR(255), NULL)
- verification_token_expires (TIMESTAMP, NULL)
- reset_token (VARCHAR(255), NULL)
- reset_token_expires (TIMESTAMP, NULL)
- created_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
- updated_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)
- last_login (TIMESTAMP, NULL)

### 6.2 Check `main_clients_database` Modifications

```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'main_clients_database'
    AND column_name IN ('client_id', 'created_by', 'updated_at')
ORDER BY column_name;
```

**Expected Result:**
```
column_name | data_type | is_nullable | column_default
------------|-----------|-------------|---------------
client_id   | uuid      | NO          |
created_by  | varchar   | YES         |
updated_at  | timestamp | YES         | CURRENT_TIMESTAMP
```

### 6.3 Verify Foreign Key Relationship

```sql
-- Test query: Get channels for legacy user
SELECT
    m.open_channel_id,
    m.open_channel_title,
    m.client_id,
    r.username
FROM main_clients_database m
JOIN registered_users r ON m.client_id = r.user_id
WHERE r.username = 'legacy_system';
```

**Expected Result:** All existing channels should appear with `username = 'legacy_system'`

### 6.4 Test Channel Count Limit Query

```sql
-- Test query: Count channels per user (for 10-limit enforcement)
SELECT
    r.user_id,
    r.username,
    COUNT(m.open_channel_id) as channel_count
FROM registered_users r
LEFT JOIN main_clients_database m ON r.user_id = m.client_id
GROUP BY r.user_id, r.username
ORDER BY channel_count DESC;
```

**Expected Result:**
```
user_id                              | username      | channel_count
-------------------------------------|---------------|---------------
00000000-0000-0000-0000-000000000000 | legacy_system |             N
```

---

## Integration with Threshold Payout Migration

**If you have already run `DB_MIGRATION_THRESHOLD_PAYOUT.md`:**

The `main_clients_database` table should now have these columns from BOTH migrations:

```sql
-- Verify combined schema (Threshold Payout + User Accounts)
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'main_clients_database'
    AND column_name IN (
        'payout_strategy',           -- From Threshold Payout
        'payout_threshold_usd',      -- From Threshold Payout
        'payout_threshold_updated_at', -- From Threshold Payout
        'client_id',                 -- From User Accounts
        'created_by',                -- From User Accounts
        'updated_at'                 -- From User Accounts
    )
ORDER BY column_name;
```

**Expected Result:**
```
column_name                 | data_type | is_nullable
----------------------------|-----------|------------
client_id                   | uuid      | NO
created_by                  | varchar   | YES
payout_strategy             | varchar   | YES
payout_threshold_usd        | numeric   | YES
payout_threshold_updated_at | timestamp | YES
updated_at                  | timestamp | YES
```

**If you have NOT run threshold payout migration yet:**
- Run `DB_MIGRATION_THRESHOLD_PAYOUT.md` first
- Then run this migration
- Order doesn't matter as long as both complete before deploying services

---

## Rollback Procedure

**If you need to undo this migration:**

```sql
-- ==============================================================================
-- ROLLBACK: User Account Management Migration
-- ==============================================================================

-- WARNING: This will delete all user accounts and remove client_id relationship
-- Only run this if you need to completely undo the user account feature

-- Step 1: Drop foreign key constraint
ALTER TABLE main_clients_database
DROP CONSTRAINT IF EXISTS fk_client_id;

-- Step 2: Drop index
DROP INDEX IF EXISTS idx_main_clients_client_id;

-- Step 3: Remove columns from main_clients_database
ALTER TABLE main_clients_database
DROP COLUMN IF EXISTS client_id,
DROP COLUMN IF EXISTS created_by,
DROP COLUMN IF EXISTS updated_at;

-- Step 4: Drop registered_users table (and all user accounts)
DROP TABLE IF EXISTS registered_users CASCADE;

-- Verification: Check that tables are back to original state
SELECT 'Rollback complete' as status;
```

**⚠️ WARNING:** This rollback will:
- Delete ALL user accounts (including legacy_system)
- Remove all client_id relationships
- Channels will still exist but won't be linked to any user
- Cannot be undone without backup

**Recommended:** Take a database backup before running rollback.

---

## Post-Migration Tasks

**After running this migration, you must:**

1. **Update GCRegister10-26 Service**
   - Add Flask-Login integration
   - Implement `/signup`, `/login`, `/logout` routes
   - Implement `/channels` dashboard
   - Implement `/channels/add` and `/channels/<id>/edit` routes
   - Deploy updated service

2. **Update Secret Manager (if needed)**
   - Add `SECRET_KEY` for Flask session management (likely already exists)
   - No new secrets required for basic user management

3. **Test User Flow**
   - Create test user account
   - Login with test user
   - Add channel via dashboard (verify `client_id` populated)
   - Edit channel (verify authorization)
   - Test 10-channel limit

4. **Monitor for Issues**
   - Check logs for authentication errors
   - Verify session persistence
   - Test foreign key constraint (try deleting user with channels)

5. **Optional: Email Verification**
   - If implementing email verification, add email service configuration
   - Update signup flow to send verification emails

---

## Common Issues and Solutions

### Issue 1: Foreign Key Constraint Fails

**Error:**
```
ERROR: insert or update on table "main_clients_database" violates foreign key constraint "fk_client_id"
```

**Cause:** Trying to insert channel with non-existent `client_id`

**Solution:**
- Ensure user account exists before creating channel
- In application code, always use `current_user.id` from authenticated session

### Issue 2: Duplicate Username or Email

**Error:**
```
ERROR: duplicate key value violates unique constraint "registered_users_username_key"
```

**Cause:** Trying to create user with existing username/email

**Solution:**
- Add validation in signup form to check username/email availability
- Provide clear error message to user

### Issue 3: Legacy Channels Not Showing

**Error:** Dashboard shows 0 channels for legacy_system user

**Cause:** Migration Step 4 didn't update existing channels

**Solution:**
```sql
-- Check if channels have NULL client_id
SELECT COUNT(*) FROM main_clients_database WHERE client_id IS NULL;

-- If any exist, update them
UPDATE main_clients_database
SET client_id = '00000000-0000-0000-0000-000000000000'
WHERE client_id IS NULL;
```

---

## Summary

**Tables Created:** 1
- `registered_users` (13 columns, 4 indexes)

**Tables Modified:** 1
- `main_clients_database` (added 3 columns, 1 foreign key, 1 index)

**Data Migration:** All existing channels assigned to `legacy_system` user

**Next Step:** Modify GCRegister10-26 to add user authentication and dashboard

---

**Document Status:** ✅ Ready for Execution
**Execution Time:** ~5 minutes
**Risk Level:** Low (backward compatible via legacy user)
**Reversible:** Yes (rollback procedure provided)

---

**Related Documentation:**
- `USER_ACCOUNT_MANAGEMENT_ARCHITECTURE.md` - Full architecture design
- `MAIN_ARCHITECTURE_WORKFLOW.md` - Implementation tracker
- `DB_MIGRATION_THRESHOLD_PAYOUT.md` - Threshold payout database changes
