# Backup Inventory - PGP_v1 Database

**Project**: `pgp-live`
**Database Instance**: `telepaypsql`
**Last Updated**: 2025-11-18

---

## Automated Backups

### Configuration

**Frequency**: Daily at 04:00 UTC
**Retention**: 30 backups (~30 days)
**Location**: `us` (multi-region for disaster recovery)
**Encryption**: AES-256 (Google-managed keys)
**Type**: Automated on-demand backups

### Backup Window

**Scheduled Time**: 04:00 UTC (low traffic period)
**Duration**: ~15-30 minutes (depends on database size)
**Impact**: No downtime (online backup)

### Verification

**Last Backup**: [TO BE FILLED - Run verify_backup_config.sh]
**Status**: [TO BE FILLED]
**Size**: [TO BE FILLED]

---

## Point-in-Time Recovery (PITR)

### Configuration

**Status**: [ENABLED/DISABLED]
**Retention**: 7 days
**Recovery Granularity**: 1 second
**Last Tested**: [TO BE FILLED]

### Recovery Window

**Earliest Recovery Point**: 7 days ago from last backup
**Latest Recovery Point**: Current timestamp

### Usage Example

```bash
# Clone instance to specific timestamp
gcloud sql instances clone telepaypsql telepaypsql-pitr-recovery \
  --point-in-time='2025-11-18T12:30:00.000Z' \
  --project=pgp-live
```

---

## Recovery Metrics

### Targets

**RTO (Recovery Time Objective)**: 1 hour
**RPO (Recovery Point Objective)**: 5 minutes

### Actual Performance

**Last Restoration Test**: [TO BE FILLED]
**Restoration Time**: [TO BE FILLED]
**Data Loss**: [TO BE FILLED]

---

## Backup Testing Schedule

**Monthly**: Restore latest backup to test instance
**Quarterly**: Point-in-Time Recovery test
**Annually**: Full disaster recovery drill

---

## Monitoring

### Alerts Configured

- [ ] Backup failure
- [ ] Backup age > 25 hours
- [ ] Storage usage > 80%
- [ ] PITR transaction log gap > 1 hour

### Verification Script

```bash
/TOOLS_SCRIPTS_TESTS/scripts/security/phase1_backups/validate_backup.sh
```

Run daily at 10:00 UTC via Cloud Scheduler

---

## Storage Usage

**Current Disk Size**: [TO BE FILLED] GB
**Storage Auto-Increase**: [ENABLED/DISABLED]
**Storage Limit**: [TO BE FILLED] GB

---

## Notes

- Backups are incremental (only changes since last backup)
- First backup is full, subsequent are incremental
- Storage usage will grow over time
- Enable storage auto-increase to prevent disk full
