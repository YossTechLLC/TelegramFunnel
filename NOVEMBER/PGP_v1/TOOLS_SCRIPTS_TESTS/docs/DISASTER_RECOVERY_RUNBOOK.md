# Disaster Recovery Runbook - PGP_v1 Database

**Project**: `pgp-live`
**Database Instance**: `telepaypsql`
**Version**: 1.0
**Last Updated**: 2025-11-18

---

## Table of Contents

1. [Emergency Contacts](#emergency-contacts)
2. [Failure Scenarios](#failure-scenarios)
3. [Recovery Procedures](#recovery-procedures)
4. [Rollback Procedures](#rollback-procedures)
5. [Post-Recovery Steps](#post-recovery-steps)

---

## Emergency Contacts

**Database Administrator**: [TO BE FILLED]
**DevOps Lead**: [TO BE FILLED]
**Security Team**: [TO BE FILLED]
**On-Call**: [TO BE FILLED]

**Escalation Path**:
1. Database Administrator (Response time: 15 minutes)
2. DevOps Lead (Response time: 30 minutes)
3. CTO (Response time: 1 hour)

---

## Failure Scenarios

### Scenario 1: Database Corruption

**Symptoms**:
- Query errors
- Data inconsistency
- Index corruption

**Recovery Method**: Point-in-Time Recovery (PITR)
**RTO**: 1 hour
**RPO**: 5 minutes

### Scenario 2: Accidental Data Deletion

**Symptoms**:
- Missing tables
- Deleted records
- DROP operations

**Recovery Method**: Point-in-Time Recovery (PITR)
**RTO**: 1 hour
**RPO**: 5 minutes

### Scenario 3: Complete Instance Failure

**Symptoms**:
- Instance unreachable
- Cloud SQL instance deleted
- Regional outage

**Recovery Method**: Restore from automated backup
**RTO**: 2 hours
**RPO**: 24 hours (last backup)

---

## Recovery Procedures

### Procedure 1: Point-in-Time Recovery (PITR)

**Use Case**: Recover to specific timestamp (last 7 days)

**Steps**:

1. **Identify Recovery Timestamp**
   ```bash
   # Determine when corruption/deletion occurred
   # Use Cloud Logging to find exact timestamp
   ```

2. **Clone Instance to Recovery Point**
   ```bash
   RECOVERY_TIMESTAMP="2025-11-18T12:30:00.000Z"

   gcloud sql instances clone telepaypsql telepaypsql-recovery \
     --point-in-time="${RECOVERY_TIMESTAMP}" \
     --project=pgp-live
   ```

3. **Verify Recovered Data**
   ```bash
   # Connect to recovery instance
   # Verify data integrity
   # Check that corruption/deletion is not present
   ```

4. **Promote Recovery Instance**
   ```bash
   # Option A: Failover to recovery instance
   # Update Cloud Run services to use new connection name

   # Option B: Export/import specific data
   # If only specific tables/data affected
   ```

5. **Update Application Configuration**
   ```bash
   # Update Secret Manager with new connection name
   # OR import recovered data to original instance
   ```

**Estimated Time**: 1 hour

---

### Procedure 2: Restore from Automated Backup

**Use Case**: Recover from backup (last 30 days)

**Steps**:

1. **List Available Backups**
   ```bash
   gcloud sql backups list \
     --instance=telepaypsql \
     --project=pgp-live \
     --limit=30
   ```

2. **Identify Backup to Restore**
   ```bash
   # Choose backup closest to desired recovery point
   BACKUP_ID="[BACKUP_ID_FROM_LIST]"
   ```

3. **Create New Instance from Backup**
   ```bash
   gcloud sql instances create telepaypsql-restored \
     --source-instance=telepaypsql \
     --source-backup=${BACKUP_ID} \
     --project=pgp-live
   ```

4. **Verify Restored Instance**
   ```bash
   # Connect and verify data
   # Run data integrity checks
   ```

5. **Failover to Restored Instance**
   ```bash
   # Update Cloud Run services
   # Update Secret Manager connection name
   ```

**Estimated Time**: 2 hours

---

### Procedure 3: Emergency Rollback (SSL/TLS)

**Use Case**: Rollback SSL enforcement if breaking connectivity

**Steps**:

1. **Run Rollback Script**
   ```bash
   cd /TOOLS_SCRIPTS_TESTS/scripts/security/phase2_ssl
   ./rollback_ssl_enforcement.sh
   ```

2. **Verify Services Connect**
   ```bash
   # Check Cloud Run health endpoints
   # Monitor application logs
   ```

3. **Fix SSL Issues**
   ```bash
   # Update Cloud SQL Connector version
   # Fix service configuration
   # Test in staging
   ```

4. **Re-enable SSL**
   ```bash
   ./enable_ssl_enforcement.sh
   ```

**Estimated Time**: 30 minutes

---

## Rollback Procedures

### Rollback 1: Failed Database Migration

**Steps**:

1. **Stop Migration**
2. **Restore Pre-Migration Backup**
3. **Verify Data Integrity**
4. **Investigate Failure**

### Rollback 2: Configuration Change

**Steps**:

1. **Revert Database Flags**
   ```bash
   gcloud sql instances patch telepaypsql \
     --clear-database-flags \
     --project=pgp-live
   ```

2. **Verify Instance Health**

---

## Post-Recovery Steps

### Step 1: Verify Data Integrity

- [ ] Run data consistency checks
- [ ] Verify all services connecting
- [ ] Check application functionality
- [ ] Review recent transactions

### Step 2: Root Cause Analysis

- [ ] Identify failure cause
- [ ] Document incident timeline
- [ ] Create incident report
- [ ] Identify prevention measures

### Step 3: Update Documentation

- [ ] Document recovery procedure used
- [ ] Update runbook with lessons learned
- [ ] Share post-mortem with team

### Step 4: Prevent Recurrence

- [ ] Implement fixes
- [ ] Add monitoring/alerts
- [ ] Test recovery procedures
- [ ] Schedule disaster recovery drill

---

## Testing Schedule

**Monthly**: Test backup restoration
**Quarterly**: Test PITR recovery
**Annually**: Full disaster recovery drill

**Last DR Test**: [TO BE FILLED]
**Next DR Test**: [TO BE FILLED]
