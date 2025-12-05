# PGP_v1 Database Security Deployment Guide

**Project**: `pgp-live`
**Database Instance**: `telepaypsql`
**Created**: 2025-11-18
**Status**: READY FOR DEPLOYMENT

---

## Overview

This directory contains all deployment scripts and documentation for implementing comprehensive database security for the PGP_v1 payment processing system.

**Security Improvements Implemented**:
- ✅ Automated backups with 30-day retention
- ✅ Point-in-Time Recovery (PITR) with 7-day transaction logs
- ✅ SSL/TLS enforcement for all database connections
- ✅ pgAudit logging for compliance and security monitoring
- ✅ Automated password rotation every 90 days
- ✅ Storage auto-increase to prevent disk full

**CRITICAL CONSTRAINT**: VPC is NOT being used per architectural decision
- Reason: VPC-SC breaks Cloud Scheduler and external APIs (ChangeNow, NowPayments)
- Alternative: IAM + HMAC + Cloud Armor + SSL/TLS provide sufficient security

---

## Directory Structure

```
scripts/security/
├── phase1_backups/             # Backup & PITR configuration
│   ├── verify_backup_config.sh     # Check current backup settings (READ-ONLY)
│   ├── enable_automated_backups.sh # Enable daily backups
│   ├── enable_pitr.sh              # Enable Point-in-Time Recovery
│   └── validate_backup.sh          # Automated backup validation
│
├── phase2_ssl/                 # SSL/TLS enforcement
│   ├── verify_ssl_enforcement.sh   # Check SSL configuration (READ-ONLY)
│   ├── enable_ssl_enforcement.sh   # Enforce SSL/TLS for all connections
│   └── rollback_ssl_enforcement.sh # Emergency rollback (if needed)
│
├── phase3_audit/               # Audit logging
│   ├── enable_pgaudit_ddl.sh       # Enable DDL logging (low impact)
│   └── enable_pgaudit_full.sh      # Enable full logging (DDL + DML)
│
└── phase5_rotation/            # Secret rotation automation
    ├── rotate_db_password/
    │   ├── main.py                 # Cloud Function code
    │   └── requirements.txt        # Python dependencies
    └── deploy_rotation_function.sh # Deploy rotation automation
```

---

## Implementation Phases

### Phase 1: Backups & PITR (Week 1) - CRITICAL

**Priority**: CRITICAL
**Downtime**: Minimal (~30 seconds)
**Risk**: LOW

**Steps**:

1. **Verify Current Configuration**
   ```bash
   cd phase1_backups
   ./verify_backup_config.sh
   ```

2. **Enable Automated Backups**
   ```bash
   # Review script before running
   ./enable_automated_backups.sh
   ```

3. **Enable Point-in-Time Recovery**
   ```bash
   # Review script before running
   ./enable_pitr.sh
   ```

4. **Test Backup Validation**
   ```bash
   ./validate_backup.sh
   ```

**Success Criteria**:
- ✅ Automated backups running daily
- ✅ 30-day retention configured
- ✅ PITR enabled with 7-day transaction logs
- ✅ Backup validation script operational

---

### Phase 2: SSL/TLS Enforcement (Week 2-3) - CRITICAL

**Priority**: CRITICAL
**Downtime**: ~30 seconds (instance restart)
**Risk**: MEDIUM

**Steps**:

1. **Verify Current SSL Status**
   ```bash
   cd ../phase2_ssl
   ./verify_ssl_enforcement.sh
   ```

2. **Test in Staging First** (REQUIRED)
   ```bash
   # Create staging instance
   # Apply SSL enforcement to staging
   # Test all service connections
   # Monitor for 24 hours
   ```

3. **Enable SSL Enforcement (Production)**
   ```bash
   # Coordinate maintenance window
   # Review script before running
   ./enable_ssl_enforcement.sh
   ```

4. **Monitor for 24 Hours**
   ```bash
   # Check Cloud Run logs for connection errors
   gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=50
   ```

5. **Rollback If Needed**
   ```bash
   # Only if critical issues detected
   ./rollback_ssl_enforcement.sh
   ```

**Success Criteria**:
- ✅ SSL/TLS enforcement enabled
- ✅ All services connect successfully
- ✅ 100% of connections use SSL (verify in logs)
- ✅ No connection errors for 48 hours

---

### Phase 3: Audit Logging (Week 4-6) - HIGH PRIORITY

**Priority**: HIGH
**Downtime**: ~30 seconds (instance restart)
**Risk**: MEDIUM

**Steps**:

1. **Enable DDL Logging (Phase 3A)**
   ```bash
   cd ../phase3_audit
   # Review script before running
   ./enable_pgaudit_ddl.sh
   ```

2. **Monitor for 1 Week**
   - Check performance impact (<5% acceptable)
   - Monitor disk usage (should grow slowly)
   - Review audit logs in Cloud Logging

3. **Enable Full Logging (Phase 3B) - Optional**
   ```bash
   # Only if Phase 3A performance acceptable
   # Review script before running
   ./enable_pgaudit_full.sh
   ```

4. **Configure Log Export to BigQuery**
   ```bash
   # Follow guide in /docs/AUDIT_LOG_QUERIES.sql
   ```

**Success Criteria**:
- ✅ pgAudit extension enabled
- ✅ DDL operations logged
- ✅ Performance impact <10%
- ✅ Logs exported to BigQuery

---

### Phase 4: VPC/Private IP - SKIPPED

**Status**: ❌ **NOT APPLICABLE**
**Reason**: VPC-SC breaks Cloud Scheduler and external APIs

**Alternative Security**:
- SSL/TLS encryption enforced (Phase 2)
- Audit logging (Phase 3)
- Cloud Armor for DDoS protection
- IAM-based access control

---

### Phase 5: Secret Rotation (Week 8+) - MEDIUM PRIORITY

**Priority**: MEDIUM
**Downtime**: None (automated)
**Risk**: LOW

**Steps**:

1. **Deploy Cloud Function**
   ```bash
   cd ../phase5_rotation
   # Review script before running
   ./deploy_rotation_function.sh
   ```

2. **Test in Staging**
   ```bash
   # Trigger function manually
   # Verify password rotates successfully
   # Verify services auto-reload new credentials
   ```

3. **Schedule Automation (90-day cycle)**
   - Cloud Scheduler configured by deploy script
   - First rotation in 90 days

**Success Criteria**:
- ✅ Cloud Function deployed
- ✅ Cloud Scheduler configured
- ✅ Test rotation successful
- ✅ Services auto-reload credentials

---

## Documentation Files

### `/TOOLS_SCRIPTS_TESTS/docs/`

- **BACKUP_INVENTORY.md** - Backup configuration and metrics
- **DISASTER_RECOVERY_RUNBOOK.md** - Step-by-step recovery procedures
- **AUDIT_LOG_QUERIES.sql** - BigQuery queries for compliance reporting

---

## Pre-Deployment Checklist

**Before ANY deployment**:

- [ ] Review this guide completely
- [ ] Read and approve SSL/TLS checklist: `/THINK/SSL_TLS_CHECKLIST.md`
- [ ] Review progress tracker: `/THINK/SSL_TLS_CHECKLIST_PROGRESS.md`
- [ ] Verify team lead approval
- [ ] Schedule maintenance window (low traffic period)
- [ ] Create staging instance for testing
- [ ] Notify team 48 hours in advance
- [ ] Have rollback scripts ready
- [ ] Document current configuration

---

## Deployment Order (STRICT)

**MUST follow this order**:

1. **Phase 1**: Backups & PITR (safe, no breaking changes)
2. **Phase 2**: SSL/TLS enforcement (test thoroughly)
3. **Phase 3**: Audit logging (monitor performance)
4. **Phase 5**: Secret rotation (after all others stable)

**Do NOT skip Phase 1** - backups are critical before any other changes

---

## Monitoring & Validation

### Daily Monitoring (First Week)

```bash
# Run backup validation
/scripts/security/phase1_backups/validate_backup.sh

# Check SSL enforcement
/scripts/security/phase2_ssl/verify_ssl_enforcement.sh

# Monitor Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=50
```

### Weekly Review

- Review audit logs in BigQuery
- Check storage usage trends
- Verify backup success rate
- Review compliance checklist

---

## Rollback Procedures

### If SSL Enforcement Breaks Connectivity

```bash
cd /scripts/security/phase2_ssl
./rollback_ssl_enforcement.sh
```

### If Backup Issues

```bash
# Disable PITR (if causing issues)
gcloud sql instances patch telepaypsql \
  --no-enable-point-in-time-recovery \
  --project=pgp-live
```

### If Audit Logging Impacts Performance

```bash
# Disable pgAudit
gcloud sql instances patch telepaypsql \
  --clear-database-flags \
  --project=pgp-live
```

---

## Emergency Contacts

**Database Administrator**: [TO BE FILLED]
**DevOps Lead**: [TO BE FILLED]
**Security Team**: [TO BE FILLED]
**On-Call**: [TO BE FILLED]

---

## Success Criteria (Overall)

**Deployment is successful when**:

- ✅ Automated backups running daily with 30-day retention
- ✅ Point-in-Time Recovery enabled and tested
- ✅ All database connections encrypted with SSL/TLS
- ✅ Audit logging capturing required operations
- ✅ Logs exported to BigQuery for compliance
- ✅ Secret rotation automated (90-day cycle)
- ✅ All compliance requirements documented
- ✅ Monitoring and alerting operational
- ✅ No service disruptions or errors

---

## Important Notes

- **NO DEPLOYMENT TO GOOGLE CLOUD** - Scripts document only
- All scripts require manual review before execution
- Test ALL changes in staging first
- Monitor closely during and after deployment
- Keep rollback scripts ready at all times
- Document all changes in DECISIONS.md

---

## Questions or Issues?

1. Review the checklist: `/THINK/SSL_TLS_CHECKLIST.md`
2. Check progress tracker: `/THINK/SSL_TLS_CHECKLIST_PROGRESS.md`
3. Review disaster recovery runbook: `/docs/DISASTER_RECOVERY_RUNBOOK.md`
4. Contact database administrator

---

**Last Updated**: 2025-11-18
**Next Review**: After Phase 1 deployment
**Owner**: PGP_v1 Development Team
