-- =============================================================================
-- Database Migration: Add Indexes for Token Lookups
-- =============================================================================
-- Date: 2025-11-09
-- Purpose: Add partial indexes on verification_token and reset_token columns
--          for improved query performance during email verification and
--          password reset flows.
--
-- Performance Impact:
--   - Speeds up token lookups from O(n) to O(log n)
--   - Minimal storage overhead due to partial index (only non-NULL values)
--   - No impact on writes (tokens are rarely updated)
--
-- Indexes:
--   1. idx_registered_users_verification_token - For email verification lookups
--   2. idx_registered_users_reset_token        - For password reset lookups
--
-- Note: Using partial indexes (WHERE ... IS NOT NULL) because:
--   - Most users will have NULL tokens (already verified or no reset pending)
--   - Reduces index size by ~90%
--   - Only indexes rows that actually need fast lookup
-- =============================================================================

-- Index for email verification token lookups
-- This speeds up queries like: SELECT * FROM registered_users WHERE verification_token = ?
CREATE INDEX IF NOT EXISTS idx_registered_users_verification_token
ON registered_users(verification_token)
WHERE verification_token IS NOT NULL;

-- Index for password reset token lookups
-- This speeds up queries like: SELECT * FROM registered_users WHERE reset_token = ?
CREATE INDEX IF NOT EXISTS idx_registered_users_reset_token
ON registered_users(reset_token)
WHERE reset_token IS NOT NULL;

-- =============================================================================
-- Verification Queries
-- =============================================================================
-- Run these queries after migration to verify indexes were created:
--
-- 1. List all indexes on registered_users table:
--    \d registered_users
--
-- 2. Verify index usage with EXPLAIN:
--    EXPLAIN SELECT * FROM registered_users WHERE verification_token = 'test';
--    (Should show "Index Scan using idx_registered_users_verification_token")
--
-- 3. Check index size:
--    SELECT pg_size_pretty(pg_relation_size('idx_registered_users_verification_token'));
--
-- =============================================================================
-- Rollback (if needed):
-- =============================================================================
-- DROP INDEX IF EXISTS idx_registered_users_verification_token;
-- DROP INDEX IF EXISTS idx_registered_users_reset_token;
-- =============================================================================
