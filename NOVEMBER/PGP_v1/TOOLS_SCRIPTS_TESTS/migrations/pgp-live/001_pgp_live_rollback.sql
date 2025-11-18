-- ============================================================================
-- PayGatePrime Schema Rollback - PGP-LIVE Project
-- ============================================================================
-- Project: pgp-live
-- Database: telepaydb
-- Instance: pgp-live:us-central1:pgp-telepaypsql
-- Migration: 001_pgp_live_rollback - Complete Schema Removal (13 Tables)
-- Created: 2025-11-18
--
-- ⚠️⚠️⚠️ WARNING: THIS WILL DELETE ALL DATA IN THE DATABASE! ⚠️⚠️⚠️
--
-- This rollback script removes ONLY the 13 core tables from pgp-live schema.
-- Does NOT attempt to drop deprecated tables (donation_keypad_state, user_conversation_state)
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Drop Tables (in reverse dependency order)
-- ============================================================================

-- Drop tables with no dependencies first
DROP TABLE IF EXISTS failed_transactions CASCADE;
DROP TABLE IF EXISTS currency_to_network CASCADE;

-- Drop broadcast manager (depends on registered_users)
DROP TABLE IF EXISTS broadcast_manager CASCADE;

-- Drop split payout tables (no dependencies)
DROP TABLE IF EXISTS split_payout_hostpay CASCADE;
DROP TABLE IF EXISTS split_payout_que CASCADE;
DROP TABLE IF EXISTS split_payout_request CASCADE;

-- Drop payout tables (payout_accumulation depends on batch_conversions)
DROP TABLE IF EXISTS payout_batches CASCADE;
DROP TABLE IF EXISTS payout_accumulation CASCADE;
DROP TABLE IF EXISTS batch_conversions CASCADE;

-- Drop payment tracking
DROP TABLE IF EXISTS processed_payments CASCADE;

-- Drop subscription table
DROP TABLE IF EXISTS private_channel_users_database CASCADE;

-- Drop main_clients_database (depends on registered_users)
DROP TABLE IF EXISTS main_clients_database CASCADE;

-- Drop registered_users last (parent table)
DROP TABLE IF EXISTS registered_users CASCADE;

-- ============================================================================
-- STEP 2: Drop Custom ENUM Types
-- ============================================================================

DROP TYPE IF EXISTS type_type CASCADE;
DROP TYPE IF EXISTS flow_type CASCADE;
DROP TYPE IF EXISTS network_type CASCADE;
DROP TYPE IF EXISTS currency_type CASCADE;

-- ============================================================================
-- STEP 3: Drop Sequences (if any remain)
-- ============================================================================

DROP SEQUENCE IF EXISTS batch_conversions_id_seq CASCADE;
DROP SEQUENCE IF EXISTS failed_transactions_id_seq CASCADE;
DROP SEQUENCE IF EXISTS main_clients_database_id_seq CASCADE;
DROP SEQUENCE IF EXISTS payout_accumulation_id_seq CASCADE;
DROP SEQUENCE IF EXISTS private_channel_users_database_id_seq CASCADE;

-- ============================================================================
-- COMPLETION
-- ============================================================================

COMMIT;

-- Print rollback confirmation
DO $$
BEGIN
    RAISE NOTICE '✅ PayGatePrime PGP-LIVE Schema Rollback Complete';
    RAISE NOTICE '🗑️  Dropped 13 tables (13 core operational tables)';
    RAISE NOTICE '🗑️  Dropped 4 custom ENUM types';
    RAISE NOTICE '🗑️  Dropped 5 sequences';
    RAISE NOTICE ' ';
    RAISE NOTICE '⚠️  ALL DATA HAS BEEN DELETED';
    RAISE NOTICE '📝 Note: Deprecated tables NOT dropped (if they exist):';
    RAISE NOTICE '   - donation_keypad_state';
    RAISE NOTICE '   - user_conversation_state';
END $$;
