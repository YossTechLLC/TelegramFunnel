-- ============================================================================
-- Audit Log Analysis Queries for BigQuery
-- Project: pgp-live
-- Purpose: Compliance reporting and security monitoring
-- Last Updated: 2025-11-18
-- ============================================================================

-- ============================================================================
-- 1. Failed Authentication Attempts
-- ============================================================================
-- Purpose: Detect potential brute force attacks or unauthorized access attempts
-- Alert Threshold: >5 failed attempts in 5 minutes from same IP

SELECT
  timestamp,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  protoPayload.request.user AS db_user,
  protoPayload.resourceName AS resource,
  protoPayload.status.message AS error_message,
  COUNT(*) AS failed_attempts
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Filter for authentication failures
  protoPayload.status.code != 0
  AND protoPayload.methodName LIKE '%connect%'
  -- Last 24 hours
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY 1, 2, 3, 4, 5
HAVING failed_attempts > 5
ORDER BY failed_attempts DESC, timestamp DESC
LIMIT 100;


-- ============================================================================
-- 2. Schema Changes (DDL Operations)
-- ============================================================================
-- Purpose: Track all database schema modifications for compliance and auditing
-- Review: Weekly

SELECT
  timestamp,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  protoPayload.request.statement AS sql_statement,
  REGEXP_EXTRACT(protoPayload.request.statement, r'^(CREATE|ALTER|DROP)') AS operation_type,
  protoPayload.request.database AS database_name
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Filter for DDL operations
  (protoPayload.request.statement LIKE 'CREATE%'
   OR protoPayload.request.statement LIKE 'ALTER%'
   OR protoPayload.request.statement LIKE 'DROP%')
  -- Last 7 days
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY timestamp DESC
LIMIT 1000;


-- ============================================================================
-- 3. Large Data Exports (Potential Data Exfiltration)
-- ============================================================================
-- Purpose: Detect suspicious large SELECT queries that may indicate data theft
-- Alert Threshold: >10,000 rows exported in single query

SELECT
  timestamp,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  protoPayload.request.statement AS sql_statement,
  protoPayload.response.rowsAffected AS rows_exported,
  protoPayload.request.database AS database_name
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Filter for large SELECT queries
  protoPayload.request.statement LIKE 'SELECT%'
  AND protoPayload.response.rowsAffected > 10000
  -- Last 24 hours
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY protoPayload.response.rowsAffected DESC
LIMIT 100;


-- ============================================================================
-- 4. Data Modifications (DML Operations)
-- ============================================================================
-- Purpose: Track all INSERT, UPDATE, DELETE operations for compliance
-- Review: Daily for sensitive tables

SELECT
  timestamp,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  REGEXP_EXTRACT(protoPayload.request.statement, r'^(INSERT|UPDATE|DELETE)') AS operation_type,
  protoPayload.request.statement AS sql_statement,
  protoPayload.response.rowsAffected AS rows_affected,
  protoPayload.request.database AS database_name
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Filter for DML operations
  (protoPayload.request.statement LIKE 'INSERT%'
   OR protoPayload.request.statement LIKE 'UPDATE%'
   OR protoPayload.request.statement LIKE 'DELETE%')
  -- Exclude automated operations if needed
  -- AND protoPayload.authenticationInfo.principalEmail NOT LIKE '%@gserviceaccount.com'
  -- Last 24 hours
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY timestamp DESC
LIMIT 1000;


-- ============================================================================
-- 5. Off-Hours Database Access
-- ============================================================================
-- Purpose: Detect database access outside normal business hours
-- Alert: Access between 22:00 - 06:00 UTC

SELECT
  timestamp,
  EXTRACT(HOUR FROM timestamp) AS access_hour,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  protoPayload.request.statement AS sql_statement,
  protoPayload.request.database AS database_name
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Off-hours: 22:00 - 06:00 UTC
  (EXTRACT(HOUR FROM timestamp) >= 22 OR EXTRACT(HOUR FROM timestamp) <= 6)
  -- Exclude automated services if needed
  AND protoPayload.authenticationInfo.principalEmail NOT LIKE '%@gserviceaccount.com'
  -- Last 7 days
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY timestamp DESC
LIMIT 100;


-- ============================================================================
-- 6. Failed Queries (Potential SQL Injection Attempts)
-- ============================================================================
-- Purpose: Detect malformed queries that may indicate SQL injection attempts
-- Alert Threshold: >10 failed queries in 5 minutes

SELECT
  timestamp,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  protoPayload.request.statement AS sql_statement,
  protoPayload.status.message AS error_message,
  COUNT(*) AS failed_query_count
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Filter for query failures
  protoPayload.status.code != 0
  AND protoPayload.request.statement IS NOT NULL
  -- Last 1 hour
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
GROUP BY 1, 2, 3, 4
HAVING failed_query_count > 10
ORDER BY failed_query_count DESC, timestamp DESC
LIMIT 100;


-- ============================================================================
-- 7. User Privilege Changes
-- ============================================================================
-- Purpose: Track GRANT/REVOKE operations for compliance
-- Review: Immediate alert on execution

SELECT
  timestamp,
  protoPayload.authenticationInfo.principalEmail AS user_email,
  protoPayload.request.statement AS sql_statement,
  CASE
    WHEN protoPayload.request.statement LIKE 'GRANT%' THEN 'GRANT'
    WHEN protoPayload.request.statement LIKE 'REVOKE%' THEN 'REVOKE'
  END AS privilege_operation
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Filter for privilege operations
  (protoPayload.request.statement LIKE 'GRANT%'
   OR protoPayload.request.statement LIKE 'REVOKE%')
  -- Last 30 days
  AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
ORDER BY timestamp DESC
LIMIT 100;


-- ============================================================================
-- 8. Audit Log Volume by Hour (Performance Monitoring)
-- ============================================================================
-- Purpose: Monitor audit log volume to detect anomalies
-- Alert: Sudden spike (>200% of average)

SELECT
  TIMESTAMP_TRUNC(timestamp, HOUR) AS hour,
  COUNT(*) AS log_entry_count,
  COUNT(DISTINCT protoPayload.authenticationInfo.principalEmail) AS unique_users
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Last 24 hours
  timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY 1
ORDER BY 1 DESC;


-- ============================================================================
-- 9. Compliance Report: Monthly Activity Summary
-- ============================================================================
-- Purpose: Generate monthly compliance report for auditors
-- Schedule: First day of each month

SELECT
  EXTRACT(MONTH FROM timestamp) AS month,
  EXTRACT(YEAR FROM timestamp) AS year,
  COUNT(*) AS total_operations,
  COUNTIF(protoPayload.status.code = 0) AS successful_operations,
  COUNTIF(protoPayload.status.code != 0) AS failed_operations,
  COUNT(DISTINCT protoPayload.authenticationInfo.principalEmail) AS unique_users,
  COUNTIF(protoPayload.request.statement LIKE 'CREATE%') AS create_operations,
  COUNTIF(protoPayload.request.statement LIKE 'ALTER%') AS alter_operations,
  COUNTIF(protoPayload.request.statement LIKE 'DROP%') AS drop_operations,
  COUNTIF(protoPayload.request.statement LIKE 'INSERT%') AS insert_operations,
  COUNTIF(protoPayload.request.statement LIKE 'UPDATE%') AS update_operations,
  COUNTIF(protoPayload.request.statement LIKE 'DELETE%') AS delete_operations
FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
WHERE
  -- Last month
  timestamp >= TIMESTAMP_TRUNC(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 MONTH), MONTH)
  AND timestamp < TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH)
GROUP BY 1, 2
ORDER BY 2 DESC, 1 DESC;


-- ============================================================================
-- 10. SSL/TLS Connection Audit
-- ============================================================================
-- Purpose: Verify all connections use SSL/TLS encryption
-- Alert: Any non-SSL connection detected

-- Note: This query requires direct database access, not BigQuery
-- Run this query directly on the PostgreSQL database:

/*
SELECT
  datname AS database_name,
  usename AS user_name,
  ssl,
  ssl_version,
  ssl_cipher,
  client_addr,
  backend_start,
  state
FROM pg_stat_ssl
JOIN pg_stat_activity USING (pid)
WHERE ssl = false
  AND datname != 'postgres';  -- Exclude system connections
*/

-- If any rows returned: CRITICAL ALERT - Unencrypted connections detected
