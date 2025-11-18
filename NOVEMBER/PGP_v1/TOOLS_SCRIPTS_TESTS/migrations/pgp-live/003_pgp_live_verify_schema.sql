-- ============================================================================
-- PayGatePrime Schema Verification - PGP-LIVE Project
-- ============================================================================
-- Project: pgp-live
-- Database: telepaydb
-- Instance: pgp-live:us-central1:pgp-telepaypsql
-- Migration: 003_pgp_live - Schema Verification Queries
-- Created: 2025-11-18
--
-- Purpose: Verify that the pgp-live database schema was created correctly
-- Expected: 13 tables, 4 ENUMs, 60+ indexes, 87 currency mappings
-- ============================================================================

-- ============================================================================
-- QUERY 1: Count Tables (Expected: 13)
-- ============================================================================
SELECT
    'Total Tables' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 13 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
  AND table_name NOT IN ('donation_keypad_state', 'user_conversation_state');

-- ============================================================================
-- QUERY 2: List All Tables
-- ============================================================================
SELECT
    table_name,
    CASE
        WHEN table_name IN (
            'registered_users',
            'main_clients_database',
            'private_channel_users_database',
            'processed_payments',
            'batch_conversions',
            'payout_accumulation',
            'payout_batches',
            'split_payout_request',
            'split_payout_que',
            'split_payout_hostpay',
            'broadcast_manager',
            'currency_to_network',
            'failed_transactions'
        ) THEN '✅ Expected'
        ELSE '⚠️  Unexpected'
    END AS table_status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- ============================================================================
-- QUERY 3: Verify Deprecated Tables NOT Present
-- ============================================================================
SELECT
    'Deprecated Tables Check' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 0 THEN '✅ PASS (None found)'
        ELSE '❌ FAIL (Found deprecated tables)'
    END AS status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
  AND table_name IN ('donation_keypad_state', 'user_conversation_state');

-- ============================================================================
-- QUERY 4: Count Indexes (Expected: 60+)
-- ============================================================================
SELECT
    'Total Indexes' AS metric,
    COUNT(DISTINCT indexname) AS count,
    CASE
        WHEN COUNT(DISTINCT indexname) >= 60 THEN '✅ PASS'
        ELSE '⚠️  WARNING (Less than expected)'
    END AS status
FROM pg_indexes
WHERE schemaname = 'public';

-- ============================================================================
-- QUERY 5: List All Indexes by Table
-- ============================================================================
SELECT
    tablename,
    COUNT(indexname) AS index_count
FROM pg_indexes
WHERE schemaname = 'public'
GROUP BY tablename
ORDER BY tablename;

-- ============================================================================
-- QUERY 6: Verify ENUM Types (Expected: 4)
-- ============================================================================
SELECT
    'Custom ENUM Types' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 4 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS status
FROM pg_type
WHERE typtype = 'e'
  AND typname IN ('currency_type', 'network_type', 'flow_type', 'type_type');

-- ============================================================================
-- QUERY 7: List All ENUM Types
-- ============================================================================
SELECT
    typname AS enum_name,
    CASE
        WHEN typname IN ('currency_type', 'network_type', 'flow_type', 'type_type')
        THEN '✅ Expected'
        ELSE '⚠️  Unexpected'
    END AS enum_status
FROM pg_type
WHERE typtype = 'e'
ORDER BY typname;

-- ============================================================================
-- QUERY 8: Verify Foreign Keys (Expected: 3)
-- ============================================================================
SELECT
    'Foreign Key Constraints' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 3 THEN '✅ PASS'
        ELSE '⚠️  WARNING (Different than expected)'
    END AS status
FROM information_schema.table_constraints
WHERE constraint_schema = 'public'
  AND constraint_type = 'FOREIGN KEY';

-- ============================================================================
-- QUERY 9: List All Foreign Keys
-- ============================================================================
SELECT
    tc.table_name,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name;

-- ============================================================================
-- QUERY 10: Verify Currency to Network Data (Expected: 87 rows)
-- ============================================================================
SELECT
    'Currency to Network Mappings' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 87 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS status
FROM currency_to_network;

-- ============================================================================
-- QUERY 11: Verify Sequences (Expected: 5)
-- ============================================================================
SELECT
    'Sequences' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 5 THEN '✅ PASS'
        ELSE '⚠️  WARNING'
    END AS status
FROM pg_sequences
WHERE schemaname = 'public';

-- ============================================================================
-- QUERY 12: List All Sequences
-- ============================================================================
SELECT
    sequencename,
    CASE
        WHEN sequencename IN (
            'batch_conversions_id_seq',
            'failed_transactions_id_seq',
            'main_clients_database_id_seq',
            'payout_accumulation_id_seq',
            'private_channel_users_database_id_seq'
        ) THEN '✅ Expected'
        ELSE '⚠️  Unexpected'
    END AS sequence_status
FROM pg_sequences
WHERE schemaname = 'public'
ORDER BY sequencename;

-- ============================================================================
-- QUERY 13: Verify Legacy User Exists
-- ============================================================================
SELECT
    'Legacy System User' AS metric,
    COUNT(*) AS count,
    CASE
        WHEN COUNT(*) = 1 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS status
FROM registered_users
WHERE user_id = '00000000-0000-0000-0000-000000000000'
  AND username = 'legacy_system';

-- ============================================================================
-- QUERY 14: Summary - Schema Verification Report
-- ============================================================================
SELECT
    '============================================' AS divider
UNION ALL
SELECT 'PGP-LIVE SCHEMA VERIFICATION COMPLETE'
UNION ALL
SELECT '============================================'
UNION ALL
SELECT '✅ Expected: 13 tables'
UNION ALL
SELECT '✅ Expected: 4 ENUM types'
UNION ALL
SELECT '✅ Expected: 60+ indexes'
UNION ALL
SELECT '✅ Expected: 3 foreign keys'
UNION ALL
SELECT '✅ Expected: 5 sequences'
UNION ALL
SELECT '✅ Expected: 87 currency mappings'
UNION ALL
SELECT '✅ Expected: legacy_system user'
UNION ALL
SELECT '============================================';
