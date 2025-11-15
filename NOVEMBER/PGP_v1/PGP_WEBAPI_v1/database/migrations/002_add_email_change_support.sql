-- =============================================================================
-- Database Migration: Add Email Change Support and Verification Rate Limiting
-- =============================================================================
-- Migration Number: 002
-- Date: 2025-11-09
-- Purpose: Add support for email changes and verification email rate limiting
--          to support the new verification architecture
--
-- Changes:
--   1. Add pending email change columns (pending_email, pending_email_token, etc.)
--   2. Add verification rate limiting columns (last_verification_resent_at, etc.)
--   3. Add email change tracking column (last_email_change_requested_at)
--   4. Create indexes for performance
--   5. Add constraints to enforce business rules
--
-- Impact:
--   - Enables verified users to change their email address with dual verification
--   - Prevents email bombing via rate-limited verification resends
--   - Prevents duplicate pending email addresses
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: Add Columns for Pending Email Changes
-- =============================================================================
-- These columns store pending email change requests until confirmed

-- New email address pending verification
ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS pending_email VARCHAR(255);

-- Token sent to new email for confirmation (1 hour expiration)
ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS pending_email_token VARCHAR(500);

-- Token expiration timestamp
ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS pending_email_token_expires TIMESTAMP;

-- Track if notification was sent to old email
ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS pending_email_old_notification_sent BOOLEAN DEFAULT FALSE;

-- =============================================================================
-- STEP 2: Add Columns for Verification Rate Limiting
-- =============================================================================
-- These columns prevent email bombing by rate-limiting verification resends

-- Timestamp of last verification email resend (5 minute rate limit)
ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS last_verification_resent_at TIMESTAMP;

-- Count of verification emails sent (for monitoring/analytics)
ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS verification_resend_count INTEGER DEFAULT 0;

-- =============================================================================
-- STEP 3: Add Column for Email Change Tracking
-- =============================================================================
-- Track when users last requested an email change (for rate limiting - 3 per hour)

ALTER TABLE registered_users
ADD COLUMN IF NOT EXISTS last_email_change_requested_at TIMESTAMP;

-- =============================================================================
-- STEP 4: Create Indexes for Performance
-- =============================================================================

-- Index on pending_email for fast lookups and duplicate prevention
-- Partial index (only non-NULL values) for efficiency
CREATE INDEX IF NOT EXISTS idx_pending_email
ON registered_users(pending_email)
WHERE pending_email IS NOT NULL;

-- Index on verification_token_expires for cleanup queries
-- Partial index for efficiency
CREATE INDEX IF NOT EXISTS idx_verification_token_expires
ON registered_users(verification_token_expires)
WHERE verification_token_expires IS NOT NULL;

-- Index on pending_email_token_expires for cleanup queries
-- Partial index for efficiency
CREATE INDEX IF NOT EXISTS idx_pending_email_token_expires
ON registered_users(pending_email_token_expires)
WHERE pending_email_token_expires IS NOT NULL;

-- =============================================================================
-- STEP 5: Add Constraints
-- =============================================================================

-- Ensure pending_email is different from current email
-- This prevents users from "changing" to their current email
-- Note: constraint will fail silently if it already exists
DO $$
BEGIN
    ALTER TABLE registered_users
    ADD CONSTRAINT check_pending_email_different
    CHECK (pending_email IS NULL OR pending_email != email);
EXCEPTION
    WHEN duplicate_object THEN
        NULL; -- Constraint already exists, ignore
END $$;

-- Unique constraint on pending_email to prevent race conditions
-- Two users cannot have the same pending email at the same time
-- This prevents user A from "stealing" user B's email during a change
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pending_email
ON registered_users(pending_email)
WHERE pending_email IS NOT NULL;

-- =============================================================================
-- STEP 6: Add Comments for Documentation
-- =============================================================================

COMMENT ON COLUMN registered_users.pending_email IS
'Email address pending confirmation via email change process';

COMMENT ON COLUMN registered_users.pending_email_token IS
'Token sent to new email for confirmation (1 hour expiration)';

COMMENT ON COLUMN registered_users.pending_email_token_expires IS
'Expiration timestamp for pending_email_token';

COMMENT ON COLUMN registered_users.pending_email_old_notification_sent IS
'TRUE if notification was sent to old email about pending change';

COMMENT ON COLUMN registered_users.last_verification_resent_at IS
'Timestamp of last verification email resend (rate limiting: 1 per 5 min)';

COMMENT ON COLUMN registered_users.verification_resend_count IS
'Count of verification emails sent (for monitoring)';

COMMENT ON COLUMN registered_users.last_email_change_requested_at IS
'Timestamp of last email change request (rate limiting: 3 per hour)';

-- =============================================================================
-- STEP 7: Verify Migration
-- =============================================================================
-- After migration, verify changes:
--
-- Run: \d registered_users
--
-- Expected NEW columns:
--   pending_email                      | varchar(255)
--   pending_email_token                | varchar(500)
--   pending_email_token_expires        | timestamp
--   pending_email_old_notification_sent| boolean (default FALSE)
--   last_verification_resent_at        | timestamp
--   verification_resend_count          | integer (default 0)
--   last_email_change_requested_at     | timestamp
--
-- Expected NEW indexes:
--   idx_pending_email                  | (pending_email) WHERE pending_email IS NOT NULL
--   idx_verification_token_expires     | (verification_token_expires) WHERE ... IS NOT NULL
--   idx_pending_email_token_expires    | (pending_email_token_expires) WHERE ... IS NOT NULL
--   idx_unique_pending_email           | UNIQUE (pending_email) WHERE pending_email IS NOT NULL
--
-- Expected NEW constraints:
--   check_pending_email_different      | CHECK (pending_email IS NULL OR pending_email != email)
--
-- Test constraint enforcement:
--   1. Try to set pending_email = current email → should FAIL
--   2. Try to set same pending_email on two users → should FAIL
-- =============================================================================

COMMIT;

-- =============================================================================
-- Rollback Script (if needed)
-- =============================================================================
-- To rollback this migration, run the following:
--
-- BEGIN;
--
-- -- Drop constraints first
-- ALTER TABLE registered_users DROP CONSTRAINT IF EXISTS check_pending_email_different;
-- DROP INDEX IF EXISTS idx_unique_pending_email;
--
-- -- Drop indexes
-- DROP INDEX IF EXISTS idx_pending_email;
-- DROP INDEX IF EXISTS idx_verification_token_expires;
-- DROP INDEX IF EXISTS idx_pending_email_token_expires;
--
-- -- Drop columns
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS pending_email;
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS pending_email_token;
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS pending_email_token_expires;
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS pending_email_old_notification_sent;
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS last_verification_resent_at;
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS verification_resend_count;
-- ALTER TABLE registered_users DROP COLUMN IF EXISTS last_email_change_requested_at;
--
-- COMMIT;
-- =============================================================================

-- =============================================================================
-- Post-Migration Actions
-- =============================================================================
-- 1. Deploy updated application code that uses these new columns
-- 2. Test email change flow end-to-end in staging
-- 3. Test verification resend rate limiting
-- 4. Monitor logs for any constraint violations
-- 5. Set up alerts for excessive resend attempts (possible abuse)
-- =============================================================================
