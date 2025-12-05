-- ============================================================================
-- 📢 Broadcast Manager Integrity Verification Queries
-- ============================================================================
-- Purpose: Verify data integrity between main_clients_database and broadcast_manager
-- Usage: Run these queries periodically to detect orphaned entries or missing broadcasts
-- Expected Result: All queries should return 0 rows after backfill is complete
-- ============================================================================

-- Query 1: Find channels WITHOUT broadcast_manager entries (orphaned channels)
-- ============================================================================
-- Expected: 0 rows (all channels should have broadcast entries)
-- If rows found: Run backfill script (backfill_missing_broadcast_entries.py)

SELECT
    m.client_id,
    m.open_channel_id,
    m.closed_channel_id,
    m.open_channel_title,
    m.closed_channel_title,
    m.created_at AS channel_created_at
FROM main_clients_database m
LEFT JOIN broadcast_manager b
    ON m.open_channel_id = b.open_channel_id
    AND m.closed_channel_id = b.closed_channel_id
WHERE b.id IS NULL
    AND m.client_id IS NOT NULL
    AND m.open_channel_id IS NOT NULL
    AND m.closed_channel_id IS NOT NULL
ORDER BY m.created_at DESC;

-- Expected Result: 0 rows
-- If rows returned: These channels are missing broadcast_manager entries


-- Query 2: Find broadcast_manager entries WITHOUT matching channels (orphaned broadcasts)
-- ============================================================================
-- Expected: 0 rows (all broadcasts should have matching channels)
-- If rows found: These may be deleted channels (CASCADE should have removed them)

SELECT
    b.id AS broadcast_id,
    b.client_id,
    b.open_channel_id,
    b.closed_channel_id,
    b.created_at AS broadcast_created_at,
    b.broadcast_status,
    b.is_active
FROM broadcast_manager b
LEFT JOIN main_clients_database m
    ON b.open_channel_id = m.open_channel_id
    AND b.closed_channel_id = m.closed_channel_id
WHERE m.open_channel_id IS NULL;

-- Expected Result: 0 rows
-- If rows returned: These broadcasts have no matching channel (CASCADE delete failed)


-- Query 3: Verify target user 7e1018e4-5644-4031-a05c-4166cc877264 has broadcast entry
-- ============================================================================
-- Expected: 1+ rows (user should have broadcast_manager entry)

SELECT
    m.client_id,
    m.open_channel_id,
    m.closed_channel_id,
    b.id AS broadcast_id,
    b.broadcast_status,
    b.is_active,
    b.total_broadcasts,
    b.successful_broadcasts,
    b.last_sent_time,
    b.next_send_time
FROM main_clients_database m
INNER JOIN broadcast_manager b
    ON m.open_channel_id = b.open_channel_id
    AND m.closed_channel_id = b.closed_channel_id
WHERE m.client_id = '7e1018e4-5644-4031-a05c-4166cc877264';

-- Expected Result: 1+ rows with broadcast_id populated
-- If 0 rows: User does not have broadcast_manager entry (run backfill)


-- Query 4: Count channels vs broadcasts (should be equal)
-- ============================================================================
-- Expected: Counts should match

SELECT
    'Channels' AS entity,
    COUNT(*) AS total_count
FROM main_clients_database
WHERE client_id IS NOT NULL
    AND open_channel_id IS NOT NULL
    AND closed_channel_id IS NOT NULL

UNION ALL

SELECT
    'Broadcasts' AS entity,
    COUNT(*) AS total_count
FROM broadcast_manager;

-- Expected Result: Both counts should be equal
-- If different: Run Query 1 and Query 2 to identify discrepancies


-- Query 5: Find users with multiple channels but inconsistent broadcast entries
-- ============================================================================
-- Expected: 0 rows (all users should have broadcasts for all their channels)

SELECT
    m.client_id,
    COUNT(m.open_channel_id) AS channel_count,
    COUNT(b.id) AS broadcast_count
FROM main_clients_database m
LEFT JOIN broadcast_manager b
    ON m.open_channel_id = b.open_channel_id
    AND m.closed_channel_id = b.closed_channel_id
WHERE m.client_id IS NOT NULL
GROUP BY m.client_id
HAVING COUNT(m.open_channel_id) != COUNT(b.id);

-- Expected Result: 0 rows
-- If rows returned: These users have some channels without broadcasts


-- Query 6: Check CASCADE delete constraint exists
-- ============================================================================
-- Expected: 1 row showing ON DELETE CASCADE

SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON rc.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'broadcast_manager'
    AND kcu.column_name = 'client_id';

-- Expected Result: 1 row with delete_rule = 'CASCADE'
-- If delete_rule != 'CASCADE': Foreign key constraint is misconfigured


-- Query 7: Verify UNIQUE constraint on (open_channel_id, closed_channel_id)
-- ============================================================================
-- Expected: 1 row showing UNIQUE constraint

SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    conrelid::regclass AS table_name,
    a.attname AS column_name
FROM pg_constraint c
JOIN pg_attribute a
    ON a.attnum = ANY(c.conkey)
    AND a.attrelid = c.conrelid
WHERE c.conrelid = 'broadcast_manager'::regclass
    AND c.contype = 'u'  -- UNIQUE constraint
    AND a.attname IN ('open_channel_id', 'closed_channel_id');

-- Expected Result: 2 rows (one for each column in UNIQUE constraint)
-- If 0 rows: UNIQUE constraint is missing (duplicate broadcasts possible)


-- Query 8: Summary statistics
-- ============================================================================
-- Summary of current state

SELECT
    'Total Channels' AS metric,
    COUNT(*) AS value
FROM main_clients_database
WHERE client_id IS NOT NULL

UNION ALL

SELECT
    'Total Broadcasts' AS metric,
    COUNT(*) AS value
FROM broadcast_manager

UNION ALL

SELECT
    'Active Broadcasts' AS metric,
    COUNT(*) AS value
FROM broadcast_manager
WHERE is_active = true

UNION ALL

SELECT
    'Pending Broadcasts' AS metric,
    COUNT(*) AS value
FROM broadcast_manager
WHERE broadcast_status = 'pending'

UNION ALL

SELECT
    'Orphaned Channels (no broadcast)' AS metric,
    COUNT(*) AS value
FROM main_clients_database m
LEFT JOIN broadcast_manager b
    ON m.open_channel_id = b.open_channel_id
    AND m.closed_channel_id = b.closed_channel_id
WHERE b.id IS NULL
    AND m.client_id IS NOT NULL

UNION ALL

SELECT
    'Orphaned Broadcasts (no channel)' AS metric,
    COUNT(*) AS value
FROM broadcast_manager b
LEFT JOIN main_clients_database m
    ON b.open_channel_id = m.open_channel_id
    AND b.closed_channel_id = m.closed_channel_id
WHERE m.open_channel_id IS NULL;

-- Expected Result:
-- - Total Channels = Total Broadcasts
-- - Active Broadcasts = Total Broadcasts (assuming all are active)
-- - Orphaned Channels = 0
-- - Orphaned Broadcasts = 0


-- ============================================================================
-- REMEDIATION ACTIONS
-- ============================================================================

-- If Query 1 finds orphaned channels (no broadcast entries):
--   Run: python3 backfill_missing_broadcast_entries.py

-- If Query 2 finds orphaned broadcasts (no matching channels):
--   Manually delete: DELETE FROM broadcast_manager WHERE id IN (...);

-- If CASCADE delete is not working:
--   Check FK constraint: ALTER TABLE broadcast_manager DROP CONSTRAINT fk_broadcast_client;
--   Recreate with CASCADE: ALTER TABLE broadcast_manager ADD CONSTRAINT fk_broadcast_client
--                          FOREIGN KEY (client_id) REFERENCES registered_users(user_id) ON DELETE CASCADE;

-- If UNIQUE constraint is missing:
--   Add constraint: ALTER TABLE broadcast_manager ADD CONSTRAINT unique_channel_pair
--                   UNIQUE (open_channel_id, closed_channel_id);

-- ============================================================================
-- MONITORING SCHEDULE
-- ============================================================================

-- Run these queries:
--   - After backfill script execution (verify 0 orphaned channels)
--   - After channel registration (verify new broadcasts created)
--   - After channel deletion (verify CASCADE delete worked)
--   - Weekly (detect data drift over time)
--   - Before any database migrations

-- ============================================================================
