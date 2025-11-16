-- =============================================================================
-- Database Migration: Fix Duplicate Users and Add UNIQUE Constraints
-- =============================================================================
-- Date: 2025-11-09
-- Purpose: Fix duplicate username/email issue and prevent future duplicates
--          by adding UNIQUE constraints on username and email columns.
--
-- Issue:
--   Multiple users with same username were created due to missing UNIQUE
--   constraints, causing login failures when password hash doesn't match.
--
-- Solution:
--   1. Identify and clean up duplicate records (keep most recent)
--   2. Add UNIQUE constraints to prevent future duplicates
--
-- Impact:
--   - Fixes login issues for users with duplicate accounts
--   - Prevents future duplicate username/email registrations at DB level
--   - Application-level checks will be backed by DB constraints
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: Identify and Report Duplicates
-- =============================================================================
-- This section identifies duplicates for review (not executed, just for logging)
-- Uncomment the following queries to see duplicates before cleanup:

-- SELECT username, COUNT(*) as count, array_agg(user_id ORDER BY created_at) as user_ids
-- FROM registered_users
-- GROUP BY username
-- HAVING COUNT(*) > 1;

-- SELECT email, COUNT(*) as count, array_agg(user_id ORDER BY created_at) as user_ids
-- FROM registered_users
-- GROUP BY email
-- HAVING COUNT(*) > 1;

-- =============================================================================
-- STEP 2: Clean Up Duplicate Usernames
-- =============================================================================
-- Strategy: Keep the MOST RECENT user_id for each duplicate username
--           (most recent = highest created_at timestamp)
--
-- This deletes all but the most recent user for each duplicate username

DELETE FROM registered_users
WHERE user_id IN (
    SELECT user_id
    FROM (
        SELECT user_id,
               ROW_NUMBER() OVER (
                   PARTITION BY username
                   ORDER BY created_at DESC, user_id DESC
               ) as rn
        FROM registered_users
    ) duplicates
    WHERE rn > 1
);

-- =============================================================================
-- STEP 3: Clean Up Duplicate Emails
-- =============================================================================
-- Strategy: Keep the MOST RECENT user_id for each duplicate email
--
-- This deletes all but the most recent user for each duplicate email

DELETE FROM registered_users
WHERE user_id IN (
    SELECT user_id
    FROM (
        SELECT user_id,
               ROW_NUMBER() OVER (
                   PARTITION BY email
                   ORDER BY created_at DESC, user_id DESC
               ) as rn
        FROM registered_users
    ) duplicates
    WHERE rn > 1
);

-- =============================================================================
-- STEP 4: Add UNIQUE Constraints
-- =============================================================================
-- Add UNIQUE constraint on username column
-- This prevents duplicate usernames at the database level

ALTER TABLE registered_users
ADD CONSTRAINT unique_username UNIQUE (username);

-- Add UNIQUE constraint on email column
-- This prevents duplicate emails at the database level

ALTER TABLE registered_users
ADD CONSTRAINT unique_email UNIQUE (email);

-- =============================================================================
-- STEP 5: Verify Constraints
-- =============================================================================
-- After migration, verify constraints were added:
--
-- Run: \d registered_users
--
-- Expected output should include:
--   Indexes:
--     "unique_username" UNIQUE CONSTRAINT, btree (username)
--     "unique_email" UNIQUE CONSTRAINT, btree (email)
--
-- Test constraint enforcement:
--   Try to insert duplicate username: should FAIL with:
--   ERROR: duplicate key value violates unique constraint "unique_username"
--
-- =============================================================================

COMMIT;

-- =============================================================================
-- Rollback (if needed):
-- =============================================================================
-- To remove constraints if migration needs to be rolled back:
--
-- ALTER TABLE registered_users DROP CONSTRAINT IF EXISTS unique_username;
-- ALTER TABLE registered_users DROP CONSTRAINT IF EXISTS unique_email;
-- =============================================================================

-- =============================================================================
-- Post-Migration Actions Required:
-- =============================================================================
-- 1. Notify affected users (those whose duplicate accounts were deleted)
--    that they may need to re-register or reset their password
--
-- 2. Monitor application logs for any "duplicate key" errors during signup
--    (these are EXPECTED and handled by application code)
--
-- 3. Verify that signup flow correctly handles constraint violations
-- =============================================================================
