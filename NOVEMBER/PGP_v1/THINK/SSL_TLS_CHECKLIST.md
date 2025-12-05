# SSL/TLS & Database Security Comprehensive Checklist
## PGP_v1 Architecture Security Hardening

**Project**: `pgp-live`
**Database Instance**: `telepaypsql` (transitioning from `telepay-459221:us-central1:telepaypsql`)
**Created**: 2025-11-18
**Priority**: CRITICAL - Financial Data Protection
**Status**: IMPLEMENTATION REQUIRED

---

## Executive Summary

### Current Security Gaps Identified

This checklist addresses **CRITICAL** security concerns for a payment processing system handling sensitive financial data:

⚠️ **CRITICAL CONCERNS**:
1. ❌ **No SSL/TLS enforcement** - Database connections may be unencrypted
2. ❌ **No encryption at rest verification** - Cannot confirm data encryption status
3. ❌ **No documented backup strategy** - No disaster recovery plan
4. ❌ **No audit logging enabled** - Cannot track database access for compliance
5. ❌ **No secret rotation policy** - Database credentials never rotated
6. ❌ **Public IP exposure** - Database accessible via public IP (security risk)
7. ❌ **No connection monitoring** - Cannot verify SSL/TLS is actually being used

**IMPACT**: These gaps expose the system to:
- Data interception during transmission (MITM attacks)
- Regulatory compliance violations (PCI-DSS, GDPR, SOC 2)
- Permanent data loss without backups
- Inability to detect unauthorized database access
- Credential compromise without rotation

---

## Part 1: SSL/TLS Encryption for Database Connections

### 1.1 Cloud SQL Instance SSL/TLS Configuration

**OBJECTIVE**: Enforce encrypted connections to prevent network-level data interception.

#### ✅ Phase 1A: Verify Current SSL Configuration

**Location**: Google Cloud Console → SQL → telepaypsql instance

- [ ] **Check Current SSL Mode**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql instances describe telepaypsql \
    --project=pgp-live \
    --format="value(settings.ipConfiguration.requireSsl)"
  ```
  - Expected output: `true` (currently likely `false`)
  - Document current setting in implementation notes

- [ ] **Verify Server CA Certificate Status**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql ssl-certs list \
    --instance=telepaypsql \
    --project=pgp-live
  ```
  - Cloud SQL automatically creates server certificate (10-year expiration)
  - Document certificate details and expiration date

- [ ] **Review Current Connection String**
  - Current: `telepay-459221:us-central1:telepaypsql`
  - No explicit SSL parameters in Cloud SQL Python Connector
  - **STATUS**: Relying on connector defaults (NOT VERIFIED)

#### ✅ Phase 1B: Enable SSL/TLS Enforcement (IMPLEMENTATION)

⚠️ **WARNING**: This change requires service restarts. Coordinate deployment window.

**Step 1: Configure Cloud SQL Instance to Require SSL**

- [ ] **Enable `requireSsl` Flag**
  ```bash
  # DO NOT RUN - Document only (deployment phase)
  gcloud sql instances patch telepaypsql \
    --require-ssl \
    --project=pgp-live
  ```
  - **Effect**: Rejects all unencrypted connections
  - **Downtime**: Brief interruption (~30 seconds) during patch
  - **Rollback**: `--no-require-ssl` (not recommended)

**Step 2: Choose SSL Enforcement Level**

Select ONE of the following modes:

- [ ] **Option A: ENCRYPTED_ONLY (RECOMMENDED FOR CLOUD RUN)**
  - Enforces SSL/TLS encryption
  - Does NOT require client certificates
  - Best for Cloud SQL Python Connector + Cloud Run
  - **Implementation**: Already enabled by `--require-ssl`

- [ ] **Option B: TRUSTED_CLIENT_CERTIFICATE_REQUIRED (MAXIMUM SECURITY)**
  - Enforces SSL/TLS encryption
  - Requires valid client certificates (mutual TLS)
  - Best for highest security compliance (PCI-DSS Level 1)
  - **Implementation**:
    ```bash
    # DO NOT RUN - Document only
    # 1. Generate client certificates for each service
    gcloud sql ssl-certs create pgp-server-v1-cert \
      /tmp/pgp-server-v1-cert.pem \
      --instance=telepaypsql \
      --project=pgp-live

    # 2. Store certificates in Secret Manager
    gcloud secrets create PGP_DB_CLIENT_CERT \
      --data-file=/tmp/pgp-server-v1-cert.pem \
      --project=pgp-live

    # 3. Update database connection code (see Phase 1C)
    ```
  - ⚠️ **WARNING**: Requires code changes in ALL services
  - ⚠️ **WARNING**: More complex deployment and certificate management

**DECISION REQUIRED**: Choose Option A or Option B based on compliance requirements.

**Step 3: Verify SSL Enforcement**

- [ ] **Test Connection Without SSL**
  ```bash
  # Should FAIL after enabling requireSsl
  psql "host=<PUBLIC_IP> user=postgres dbname=telepaydb sslmode=disable"
  ```
  - Expected: Connection refused (SSL required)
  - If successful: SSL enforcement NOT working

- [ ] **Test Connection With SSL**
  ```bash
  # Should SUCCEED
  psql "host=<PUBLIC_IP> user=postgres dbname=telepaydb sslmode=require"
  ```
  - Expected: Connection successful
  - Verify SSL cipher: `SELECT ssl_cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();`

#### ✅ Phase 1C: Update Application Code for SSL Verification

**OBJECTIVE**: Ensure Cloud SQL Python Connector explicitly verifies SSL connections.

**Current Implementation** (`PGP_COMMON/database/db_manager.py:55`):

```python
# CURRENT - NO EXPLICIT SSL CONFIGURATION
connection = self.connector.connect(
    self.instance_connection_name,
    "pg8000",
    user=self.db_user,
    password=self.db_password,
    db=self.db_name
)
```

**ISSUE**: No explicit SSL configuration - relying on connector defaults.

**SOLUTION OPTIONS**:

- [ ] **Option 1: Cloud SQL Python Connector (Auto SSL) - RECOMMENDED**

  **Advantages**:
  - ✅ Automatic SSL/TLS encryption (Cloud SQL Connector handles it)
  - ✅ Automatic certificate verification
  - ✅ Automatic certificate rotation
  - ✅ No manual certificate management
  - ✅ Works seamlessly with Cloud Run

  **Implementation** (No code changes needed - verify only):
  ```python
  # Cloud SQL Python Connector automatically encrypts connections
  # Verify version is up to date:
  # cloud-sql-python-connector>=1.5.0

  # OPTIONAL: Add logging to verify SSL is used
  import logging
  logging.basicConfig(level=logging.DEBUG)
  # Will show SSL handshake in logs
  ```

  - [ ] Verify `cloud-sql-python-connector>=1.5.0` in requirements.txt
  - [ ] Add debug logging to confirm SSL handshake
  - [ ] Update documentation to confirm auto-SSL

- [ ] **Option 2: Explicit SSL Context (For Maximum Control)**

  **Use Case**: If you need to customize SSL verification or use client certificates.

  **Implementation**:
  ```python
  import ssl
  from google.cloud.sql.connector import Connector

  # Create custom SSL context
  ssl_context = ssl.create_default_context()
  ssl_context.check_hostname = True
  ssl_context.verify_mode = ssl.CERT_REQUIRED

  # Optional: Add custom CA bundle
  # ssl_context.load_verify_locations('/path/to/ca-bundle.pem')

  # Connect with custom SSL context
  connection = connector.connect(
      instance_connection_name,
      "pg8000",
      user=db_user,
      password=db_password,
      db=db_name,
      enable_iam_auth=False,
      # Custom SSL context (if needed)
      # ssl_context=ssl_context  # Not directly supported - use connector defaults
  )
  ```

  - [ ] **DECISION**: Only implement if you need custom SSL verification
  - [ ] Test with Cloud Run deployment
  - [ ] Document SSL context configuration

**RECOMMENDED APPROACH**: Option 1 (Cloud SQL Python Connector Auto SSL)

- No code changes required
- Leverages Google's managed SSL infrastructure
- Automatic certificate rotation
- Simpler deployment and maintenance

#### ✅ Phase 1D: Document and Monitor SSL Connections

- [ ] **Enable Query Insights (Cloud SQL)**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --enable-query-insights \
    --query-insights-query-string-length=1024 \
    --query-insights-record-application-tags \
    --project=pgp-live
  ```
  - Tracks SSL connection statistics
  - No performance impact

- [ ] **Create SSL Connection Monitoring Dashboard**
  - Cloud Console → Monitoring → Dashboards
  - Add metric: `cloudsql.googleapis.com/database/postgresql/num_backends`
  - Filter: SSL connections vs non-SSL
  - Alert if non-SSL connections detected (after enforcement)

- [ ] **Update Architecture Documentation**
  - Document SSL mode: ENCRYPTED_ONLY or TRUSTED_CLIENT_CERTIFICATE_REQUIRED
  - Document Cloud SQL Python Connector auto-SSL behavior
  - Add network diagram showing encrypted connections
  - Location: `/THINK/AUTO/DATABASE_SSL_DOCUMENTATION.md`

---

## Part 2: Database Encryption at Rest

### 2.1 Verify Current Encryption Configuration

**OBJECTIVE**: Confirm data is encrypted at rest and document encryption method.

#### ✅ Phase 2A: Verify Default Encryption

- [ ] **Check Encryption Status**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql instances describe telepaypsql \
    --project=pgp-live \
    --format="value(diskEncryptionConfiguration.kmsKeyName)"
  ```
  - **If empty**: Using Google-managed encryption (AES-256) ✅
  - **If populated**: Using Customer-Managed Encryption Key (CMEK) ✅

- [ ] **Document Current Encryption**
  - Default: Google-managed AES-256 encryption
  - Keys automatically rotated by Google
  - No additional cost
  - Compliant with most regulatory requirements
  - **STATUS**: ✅ Encryption at rest is ENABLED by default

- [ ] **Verify Backup Encryption**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql backups list \
    --instance=telepaypsql \
    --project=pgp-live \
    --limit=5
  ```
  - Backups inherit instance encryption
  - Encrypted with same key as primary data
  - **STATUS**: ✅ Backups are encrypted

#### ✅ Phase 2B: Consider Customer-Managed Encryption Keys (CMEK)

**WHEN TO USE CMEK**:
- ✅ Need explicit control over encryption keys
- ✅ Regulatory requirement for key management (HIPAA, FedRAMP)
- ✅ Need to revoke access by destroying keys
- ✅ Need custom key rotation schedule
- ✅ Multi-region key replication requirements

**WHEN NOT TO USE CMEK**:
- ❌ No specific compliance requirement
- ❌ Default Google-managed encryption is sufficient
- ❌ Additional complexity not justified
- ❌ Additional cost ($0.06/key/month + operations)

**DECISION POINT**:
- [ ] **Evaluate CMEK Requirement**
  - Review compliance requirements (PCI-DSS, GDPR, etc.)
  - Consult with legal/compliance team
  - Document decision in `/DECISIONS.md`

**If CMEK Required** (DO NOT IMPLEMENT WITHOUT APPROVAL):

- [ ] **Create Cloud KMS Key Ring**
  ```bash
  # DO NOT RUN - Document only
  gcloud kms keyrings create pgp-db-keyring \
    --location=us-central1 \
    --project=pgp-live
  ```

- [ ] **Create Encryption Key**
  ```bash
  # DO NOT RUN - Document only
  gcloud kms keys create pgp-db-key \
    --keyring=pgp-db-keyring \
    --location=us-central1 \
    --purpose=encryption \
    --rotation-period=90d \
    --next-rotation-time=$(date -d '+90 days' -u +%Y-%m-%dT%H:%M:%SZ) \
    --project=pgp-live
  ```

- [ ] **Grant Cloud SQL Service Account Access**
  ```bash
  # DO NOT RUN - Document only
  gcloud kms keys add-iam-policy-binding pgp-db-key \
    --keyring=pgp-db-keyring \
    --location=us-central1 \
    --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-cloud-sql.iam.gserviceaccount.com" \
    --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" \
    --project=pgp-live
  ```

- [ ] **Create New Instance with CMEK** (Migration Required)
  ```bash
  # DO NOT RUN - Document only
  # CMEK can only be set during instance creation
  # Requires database migration from existing instance
  gcloud sql instances create telepaypsql-cmek \
    --database-version=POSTGRES_14 \
    --tier=db-custom-2-7680 \
    --region=us-central1 \
    --disk-encryption-key=projects/pgp-live/locations/us-central1/keyRings/pgp-db-keyring/cryptoKeys/pgp-db-key \
    --project=pgp-live
  ```

⚠️ **CRITICAL CMEK WARNINGS**:
- **NEVER DESTROY KEY VERSION USED TO ENCRYPT INSTANCE**
  - Destroys instance data permanently
  - Destroys all backups encrypted with that key
  - IRREVERSIBLE data loss
- **CMEK CANNOT BE ADDED TO EXISTING INSTANCE**
  - Requires new instance creation
  - Requires full database migration
  - Significant downtime
- **KEY ROTATION MUST BE MANAGED CAREFULLY**
  - New data uses new key version
  - Old data remains encrypted with old key version
  - Old key versions must NEVER be destroyed

**RECOMMENDED DECISION**:
- ✅ **USE DEFAULT GOOGLE-MANAGED ENCRYPTION** (current setup)
  - Already AES-256 encrypted
  - Automatic key rotation
  - No additional management overhead
  - Sufficient for most compliance requirements
  - Document in architecture docs

---

## Part 3: Backup & Disaster Recovery Strategy

### 3.1 Automated Backup Configuration

**OBJECTIVE**: Implement automated backups with proper retention and recovery testing.

#### ✅ Phase 3A: Configure Automated Backups

**Current Status**: UNKNOWN - Must verify

- [ ] **Check Current Backup Configuration**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql instances describe telepaypsql \
    --project=pgp-live \
    --format="value(settings.backupConfiguration)"
  ```
  - Check: `enabled: true`
  - Check: `startTime` (backup window - typically 04:00 UTC)
  - Check: `transactionLogRetentionDays` (for PITR)
  - Check: `backupRetentionSettings.retainedBackups` (count)

- [ ] **Enable Automated Backups (If Not Enabled)**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --backup-start-time=04:00 \
    --backup-location=us \
    --retained-backups-count=30 \
    --retained-transaction-log-days=7 \
    --enable-bin-log \
    --project=pgp-live
  ```
  - **Backup Window**: 04:00 UTC (low traffic period)
  - **Retention**: 30 daily backups (meets compliance requirements)
  - **Transaction Logs**: 7 days (for Point-in-Time Recovery)
  - **Location**: `us` (multi-region for disaster recovery)

- [ ] **Verify Backup Schedule**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql backups list \
    --instance=telepaypsql \
    --project=pgp-live \
    --limit=10
  ```
  - Verify daily backups are being created
  - Check backup status: `SUCCESSFUL`
  - Document backup size and growth trend

#### ✅ Phase 3B: Enable Point-in-Time Recovery (PITR)

**OBJECTIVE**: Recover database to any point within the last 7 days.

- [ ] **Enable Transaction Log Retention**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --enable-point-in-time-recovery \
    --retained-transaction-log-days=7 \
    --project=pgp-live
  ```
  - **Effect**: Enables recovery to any second within 7 days
  - **Cost**: ~10% storage overhead for transaction logs
  - **Use Case**: Recover from data corruption, accidental deletion

- [ ] **Test PITR Recovery (Dry Run)**
  ```bash
  # DO NOT RUN - Document only (test in staging first)
  # Create clone at specific point in time
  gcloud sql instances clone telepaypsql telepaypsql-pitr-test \
    --point-in-time='2025-11-18T12:00:00.000Z' \
    --project=pgp-live

  # Verify data integrity
  # Delete test instance
  gcloud sql instances delete telepaypsql-pitr-test --project=pgp-live
  ```
  - **TEST QUARTERLY**: Every 90 days
  - Document test results in `/TOOLS_SCRIPTS_TESTS/docs/BACKUP_TEST_LOG.md`

#### ✅ Phase 3C: Implement Cross-Region Disaster Recovery

**OBJECTIVE**: Maintain active copy in different region for disaster recovery.

**Current Status**: NO CROSS-REGION REPLICA

- [ ] **Evaluate Cross-Region Replica Requirement**

  **WHEN TO USE**:
  - ✅ Business requirement for <1 hour RTO (Recovery Time Objective)
  - ✅ Need active-active or active-standby setup
  - ✅ Geographic redundancy for disaster recovery
  - ✅ Read scalability across regions

  **COST CONSIDERATIONS**:
  - 💰 Additional instance cost (~$200-500/month)
  - 💰 Cross-region data transfer costs
  - 💰 Ongoing replication overhead

  **DECISION REQUIRED**: Evaluate based on RTO/RPO requirements

- [ ] **Create Cross-Region Read Replica (If Required)**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances create telepaypsql-replica-us-east1 \
    --master-instance-name=telepaypsql \
    --tier=db-custom-2-7680 \
    --region=us-east1 \
    --replica-type=READ \
    --availability-type=REGIONAL \
    --project=pgp-live
  ```
  - **Region**: us-east1 (different from primary us-central1)
  - **Failover Time**: 5-15 minutes (automatic backup after promotion)
  - **Replication Lag**: Typically <1 second

- [ ] **Document Failover Procedure**
  - Create runbook: `/TOOLS_SCRIPTS_TESTS/docs/DISASTER_RECOVERY_RUNBOOK.md`
  - Include:
    - Failover decision criteria
    - Step-by-step failover commands
    - DNS/service reconfiguration steps
    - Rollback procedure
    - Contact escalation path

- [ ] **Test Failover (Annually)**
  ```bash
  # DO NOT RUN - Document only (scheduled maintenance window)
  # Promote replica to standalone
  gcloud sql instances promote-replica telepaypsql-replica-us-east1 \
    --project=pgp-live

  # Update application connection strings
  # Verify application functionality
  # Document results
  ```

#### ✅ Phase 3D: Backup Testing & Validation

**OBJECTIVE**: Ensure backups are valid and restorable.

- [ ] **Create Backup Test Schedule**
  - **Monthly**: Restore latest backup to test instance
  - **Quarterly**: Point-in-Time Recovery test
  - **Annually**: Full disaster recovery drill (if cross-region replica exists)

- [ ] **Automated Backup Validation Script**

  Create: `/TOOLS_SCRIPTS_TESTS/scripts/validate_backup.sh`

  ```bash
  #!/bin/bash
  # DO NOT RUN - Create script only

  # 1. List recent backups
  echo "📋 Listing recent backups..."
  gcloud sql backups list --instance=telepaypsql --project=pgp-live --limit=5

  # 2. Check backup completion
  LATEST_BACKUP=$(gcloud sql backups list \
    --instance=telepaypsql \
    --project=pgp-live \
    --limit=1 \
    --format="value(id)")

  BACKUP_STATUS=$(gcloud sql backups describe $LATEST_BACKUP \
    --instance=telepaypsql \
    --project=pgp-live \
    --format="value(status)")

  if [ "$BACKUP_STATUS" == "SUCCESSFUL" ]; then
    echo "✅ Latest backup successful"
  else
    echo "❌ Latest backup FAILED - Alert required"
    # Send alert (integrate with monitoring)
  fi

  # 3. Check backup age
  BACKUP_TIME=$(gcloud sql backups describe $LATEST_BACKUP \
    --instance=telepaypsql \
    --project=pgp-live \
    --format="value(windowStartTime)")

  # Calculate age and alert if > 25 hours (should be daily)
  ```

  - [ ] Schedule via Cloud Scheduler (daily run)
  - [ ] Integrate with alerting system
  - [ ] Log results to Cloud Logging

- [ ] **Document Backup Inventory**

  Create: `/TOOLS_SCRIPTS_TESTS/docs/BACKUP_INVENTORY.md`

  ```markdown
  # Backup Inventory

  ## Automated Backups
  - **Frequency**: Daily at 04:00 UTC
  - **Retention**: 30 days
  - **Location**: us (multi-region)
  - **Encryption**: AES-256 (Google-managed)

  ## Transaction Logs (PITR)
  - **Retention**: 7 days
  - **Recovery Granularity**: 1 second
  - **Last Tested**: [DATE]

  ## Cross-Region Replica
  - **Status**: [ENABLED/DISABLED]
  - **Region**: us-east1
  - **Replication Lag**: <1 second
  - **Last Failover Test**: [DATE]

  ## Recovery Metrics
  - **RTO (Recovery Time Objective)**: [DEFINE - e.g., 1 hour]
  - **RPO (Recovery Point Objective)**: [DEFINE - e.g., 5 minutes]
  ```

---

## Part 4: Additional Security Hardening

### 4.1 Database Audit Logging (pgAudit)

**OBJECTIVE**: Track all database access for compliance and security monitoring.

#### ✅ Phase 4A: Enable pgAudit Extension

**Current Status**: NOT ENABLED

- [ ] **Enable pgAudit Database Flag**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --database-flags=cloudsql.enable_pgaudit=on,pgaudit.log=all \
    --project=pgp-live
  ```
  - **Effect**: Logs all DDL, DML, and connection events
  - **Performance Impact**: 5-10% overhead (acceptable for compliance)
  - **Requires**: Instance restart (~30 seconds downtime)

- [ ] **Configure Audit Log Settings**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --database-flags=cloudsql.enable_pgaudit=on,pgaudit.log=ddl,pgaudit.log_catalog=off,pgaudit.log_parameter=on \
    --project=pgp-live
  ```
  - **pgaudit.log=ddl**: Log schema changes (CREATE, ALTER, DROP)
  - **pgaudit.log=write**: Log INSERT, UPDATE, DELETE
  - **pgaudit.log=all**: Log all operations (most comprehensive)
  - **RECOMMENDED**: Start with `ddl,write` to reduce log volume

- [ ] **Enable Data Access Logging**
  - Cloud Console → IAM & Admin → Audit Logs
  - Enable "Data Access" logs for Cloud SQL
  - **Warning**: Generates high log volume
  - Set log retention to 30 days minimum

#### ✅ Phase 4B: Configure Audit Log Analysis

- [ ] **Export Logs to BigQuery**
  ```bash
  # DO NOT RUN - Document only
  gcloud logging sinks create pgp-audit-logs-sink \
    bigquery.googleapis.com/projects/pgp-live/datasets/audit_logs \
    --log-filter='resource.type="cloudsql_database" AND protoPayload.serviceName="cloudsql.googleapis.com"' \
    --project=pgp-live
  ```
  - Enable long-term storage and analysis
  - Create compliance reports
  - Investigate security incidents

- [ ] **Create Audit Log Alerts**
  - Alert on: Failed authentication attempts (>5 in 5 minutes)
  - Alert on: Schema changes (DDL operations)
  - Alert on: Large data exports (SELECT * queries)
  - Alert on: Off-hours database access

- [ ] **Monitor Disk Usage for Logs**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --enable-storage-auto-increase \
    --storage-auto-increase-limit=500 \
    --project=pgp-live
  ```
  - Audit logs written to disk before Cloud Logging
  - Log ingestion rate: 4 MB/second
  - Enable auto-increase to prevent disk full

### 4.2 Secret Rotation for Database Credentials

**OBJECTIVE**: Implement automated password rotation to limit credential exposure.

**Current Status**: NO ROTATION POLICY

- [ ] **Design Rotation Architecture**

  **Components**:
  - Cloud Scheduler → Pub/Sub → Cloud Function
  - Cloud Function generates new password
  - Updates database user password
  - Creates new Secret Manager version
  - Cloud Run services fetch new version (hot-reload)

  **Rotation Schedule**: Every 90 days (quarterly)

- [ ] **Create Rotation Cloud Function**

  Create: `/TOOLS_SCRIPTS_TESTS/scripts/rotate_db_password.py`

  ```python
  # DO NOT IMPLEMENT YET - Design only
  import os
  import secrets
  from google.cloud import secretmanager
  from google.cloud.sql.connector import Connector

  def rotate_database_password(event, context):
      """
      Rotate Cloud SQL database password.
      Triggered by Cloud Scheduler via Pub/Sub.
      """
      project_id = 'pgp-live'
      instance_name = 'telepaypsql'
      db_user = 'postgres'

      # Generate strong password
      new_password = secrets.token_urlsafe(32)

      # Update database password
      connector = Connector()
      conn = connector.connect(
          f"{project_id}:us-central1:{instance_name}",
          "pg8000",
          user=db_user,
          password=os.getenv('CURRENT_DB_PASSWORD'),
          db='postgres'
      )
      cursor = conn.cursor()
      cursor.execute(f"ALTER USER {db_user} WITH PASSWORD %s", (new_password,))
      conn.commit()

      # Create new secret version
      client = secretmanager.SecretManagerServiceClient()
      parent = client.secret_path(project_id, 'DATABASE_PASSWORD_SECRET')
      response = client.add_secret_version(
          request={"parent": parent, "payload": {"data": new_password.encode()}}
      )

      # Verify new version accessible
      version = client.access_secret_version(request={"name": response.name})

      print(f"✅ Password rotated successfully: {response.name}")

      # Services will fetch new version on next request (hot-reload)
  ```

  - [ ] Test in staging environment
  - [ ] Implement rollback mechanism
  - [ ] Add error handling and alerting

- [ ] **Configure Rotation Schedule**
  ```bash
  # DO NOT RUN - Document only
  # Create Pub/Sub topic
  gcloud pubsub topics create db-password-rotation --project=pgp-live

  # Create Cloud Scheduler job (every 90 days)
  gcloud scheduler jobs create pubsub rotate-db-password \
    --schedule="0 0 1 */3 *" \
    --topic=db-password-rotation \
    --message-body='{"instance":"telepaypsql","user":"postgres"}' \
    --time-zone="UTC" \
    --project=pgp-live
  ```

- [ ] **Document Rotation Procedure**
  - Create manual rotation runbook (emergency use)
  - Document service restart requirements (none with hot-reload)
  - Define rollback procedure

### 4.3 Network Security: Private IP Configuration

**OBJECTIVE**: Remove public IP exposure and use private VPC connectivity.

**Current Status**: PUBLIC IP ENABLED (security risk)

#### ✅ Phase 4C-1: Assess Public IP Usage

- [ ] **Identify Current Public IP Connections**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql instances describe telepaypsql \
    --project=pgp-live \
    --format="value(ipAddresses)"
  ```
  - Document public IP address
  - Identify which services connect via public IP
  - **Cloud Run services**: Should use Cloud SQL Connector (auto-routes via private IP if available)

- [ ] **Review Authorized Networks**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql instances describe telepaypsql \
    --project=pgp-live \
    --format="value(settings.ipConfiguration.authorizedNetworks)"
  ```
  - List all whitelisted IP ranges
  - Identify if `0.0.0.0/0` is present (MAJOR SECURITY RISK)

#### ✅ Phase 4C-2: Configure Private IP

⚠️ **WARNING**: This is a MAJOR architecture change requiring careful planning.

**Prerequisites**:
- VPC network configured
- Private Service Access configured
- Serverless VPC Access Connector created (for Cloud Run)

- [ ] **Create VPC Network (If Not Exists)**
  ```bash
  # DO NOT RUN - Document only
  gcloud compute networks create pgp-vpc \
    --subnet-mode=custom \
    --project=pgp-live

  # Create subnet
  gcloud compute networks subnets create pgp-subnet-us-central1 \
    --network=pgp-vpc \
    --region=us-central1 \
    --range=10.0.0.0/24 \
    --project=pgp-live
  ```

- [ ] **Configure Private Service Access**
  ```bash
  # DO NOT RUN - Document only
  # Allocate IP range for Google services
  gcloud compute addresses create pgp-private-ip-range \
    --global \
    --purpose=VPC_PEERING \
    --prefix-length=16 \
    --network=pgp-vpc \
    --project=pgp-live

  # Create VPC peering
  gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges=pgp-private-ip-range \
    --network=pgp-vpc \
    --project=pgp-live
  ```

- [ ] **Create Serverless VPC Access Connector**
  ```bash
  # DO NOT RUN - Document only
  gcloud compute networks vpc-access connectors create pgp-vpc-connector \
    --region=us-central1 \
    --network=pgp-vpc \
    --range=10.8.0.0/28 \
    --min-instances=2 \
    --max-instances=10 \
    --project=pgp-live
  ```
  - **Cost**: ~$50/month (always-on)
  - **Latency**: <1ms overhead
  - **Required**: For Cloud Run to access private IP

- [ ] **Add Private IP to Cloud SQL Instance**
  ```bash
  # DO NOT RUN - Document only
  gcloud sql instances patch telepaypsql \
    --network=projects/pgp-live/global/networks/pgp-vpc \
    --project=pgp-live
  ```
  - **Effect**: Adds private IP (does NOT remove public IP yet)
  - **Downtime**: Brief interruption (~30 seconds)

- [ ] **Update Cloud Run Services to Use VPC Connector**
  ```bash
  # DO NOT RUN - Document only
  # Update each Cloud Run service
  gcloud run services update pgp-server-v1 \
    --vpc-connector=pgp-vpc-connector \
    --vpc-egress=private-ranges-only \
    --region=us-central1 \
    --project=pgp-live
  ```
  - Repeat for ALL 17 PGP_v1 services
  - **Effect**: Routes database connections through VPC

- [ ] **Test Private IP Connectivity**
  - Deploy updated services
  - Verify database connections work
  - Check logs for connection errors
  - Monitor latency (should be same or better)

- [ ] **Remove Public IP (Final Step)**
  ```bash
  # DO NOT RUN - Document only (ONLY after confirming private IP works)
  gcloud sql instances patch telepaypsql \
    --no-assign-ip \
    --project=pgp-live
  ```
  - **Effect**: Removes public IP permanently
  - **IRREVERSIBLE**: Requires new instance to add public IP back
  - **Do this LAST**: Only after confirming private IP works for ALL services

**RECOMMENDED TIMELINE**:
- Week 1: Configure VPC and Private Service Access
- Week 2: Create VPC Connector and add private IP to Cloud SQL
- Week 3: Update Cloud Run services to use VPC Connector
- Week 4: Test all services, then remove public IP

### 4.4 Connection Pooling & Performance

**OBJECTIVE**: Optimize database connections and prevent exhaustion.

- [ ] **Review Current Connection Pool Settings**
  - `PGP_SERVER_v1/models/connection_pool.py` (SQLAlchemy pool)
  - `PGP_COMMON/database/db_manager.py` (Cloud SQL Connector)

- [ ] **Configure Cloud SQL Connection Limits**
  ```bash
  # Via gcloud CLI (read-only - safe to run)
  gcloud sql instances describe telepaypsql \
    --project=pgp-live \
    --format="value(settings.databaseFlags)"
  ```
  - Check `max_connections` (default: 100 for db-custom-2-7680)
  - Check `shared_preload_libraries`
  - Consider increasing if services hit connection limit

- [ ] **Optimize SQLAlchemy Pool Settings**

  Current: `PGP_SERVER_v1/models/connection_pool.py`
  - `pool_size=5`: Connections per service instance
  - `max_overflow=10`: Additional connections under load
  - `pool_timeout=30`: Wait time for available connection
  - `pool_recycle=1800`: Recycle connections after 30 minutes

  **RECOMMENDED**: Keep current settings (well-optimized)

- [ ] **Monitor Connection Usage**
  - Cloud Console → SQL → telepaypsql → Monitoring
  - Metric: `cloudsql.googleapis.com/database/postgresql/num_backends`
  - Alert if connections > 80% of max (80 connections)

---

## Part 5: Compliance & Documentation

### 5.1 Regulatory Compliance Checklist

**OBJECTIVE**: Ensure database security meets regulatory requirements.

#### ✅ PCI-DSS (Payment Card Industry Data Security Standard)

- [ ] **Requirement 3: Protect Stored Cardholder Data**
  - ✅ Encryption at rest (AES-256)
  - ✅ Encryption in transit (SSL/TLS)
  - ⚠️ NOT STORING CARD DATA (using NowPayments - PCI-compliant)

- [ ] **Requirement 4: Encrypt Transmission of Cardholder Data**
  - ⚠️ IMPLEMENT: Enforce SSL/TLS (Part 1)
  - ⚠️ IMPLEMENT: Verify strong ciphers (TLS 1.2+)

- [ ] **Requirement 8: Identify and Authenticate Access**
  - ✅ Unique database user credentials
  - ⚠️ IMPLEMENT: Password rotation (Part 4.2)
  - ⚠️ IMPLEMENT: Audit logging (Part 4.1)

- [ ] **Requirement 10: Track and Monitor All Access**
  - ⚠️ IMPLEMENT: Enable pgAudit (Part 4.1)
  - ⚠️ IMPLEMENT: Log retention 90 days minimum
  - ⚠️ IMPLEMENT: Regular log review process

#### ✅ GDPR (General Data Protection Regulation)

- [ ] **Article 32: Security of Processing**
  - ✅ Encryption at rest and in transit
  - ⚠️ IMPLEMENT: Regular security testing (backup restoration)
  - ⚠️ IMPLEMENT: Incident response plan

- [ ] **Article 33: Breach Notification**
  - ⚠️ IMPLEMENT: Monitoring and alerting
  - ⚠️ IMPLEMENT: Breach detection procedures
  - ⚠️ IMPLEMENT: 72-hour notification process

#### ✅ SOC 2 (Service Organization Control 2)

- [ ] **CC6.1: Logical and Physical Access Controls**
  - ⚠️ IMPLEMENT: Private IP only (Part 4.3)
  - ⚠️ IMPLEMENT: IP whitelisting (if public IP required)
  - ✅ IAM-based access control

- [ ] **CC6.6: Encryption**
  - ✅ Encryption at rest
  - ⚠️ IMPLEMENT: Encryption in transit enforcement

- [ ] **CC7.2: System Monitoring**
  - ⚠️ IMPLEMENT: Audit logging
  - ⚠️ IMPLEMENT: Anomaly detection
  - ⚠️ IMPLEMENT: Regular review and response

### 5.2 Architecture Documentation Updates

**OBJECTIVE**: Document all security implementations for audit and handoff.

- [ ] **Create Security Architecture Document**

  Create: `/THINK/AUTO/DATABASE_SECURITY_ARCHITECTURE.md`

  **Contents**:
  - SSL/TLS configuration and enforcement
  - Encryption at rest implementation
  - Backup and disaster recovery strategy
  - Audit logging configuration
  - Secret rotation process
  - Network security architecture
  - Compliance mapping (PCI-DSS, GDPR, SOC 2)

- [ ] **Update PGP Architecture Documentation**

  Update: `/ARCHIVES_PGP_v1/11-18_PGP_v1/PGP_ARCHITECTURE_COMPLETE.md`

  Add sections:
  - Database security controls
  - Encryption implementation
  - Disaster recovery procedures
  - Network diagrams (VPC, private IP)

- [ ] **Create Runbooks**

  Create: `/TOOLS_SCRIPTS_TESTS/docs/`

  Files to create:
  - `DISASTER_RECOVERY_RUNBOOK.md` - Step-by-step failover procedure
  - `BACKUP_RESTORATION_RUNBOOK.md` - How to restore from backup
  - `SECRET_ROTATION_RUNBOOK.md` - Manual rotation procedure
  - `SECURITY_INCIDENT_RESPONSE.md` - Breach response procedure

- [ ] **Update DECISIONS.md**

  Add entries:
  - SSL enforcement mode chosen (ENCRYPTED_ONLY vs TRUSTED_CLIENT_CERTIFICATE_REQUIRED)
  - CMEK decision (yes/no and justification)
  - Cross-region replica decision (yes/no and justification)
  - Private IP migration timeline
  - Backup retention policy (30 days, 7 days PITR)

---

## Part 6: Implementation Roadmap

### 6.1 Phased Implementation Plan

**OBJECTIVE**: Roll out security improvements with minimal disruption.

#### 🟢 **Phase 1: Immediate (Week 1) - No Code Changes**

**PRIORITY**: CRITICAL
**DOWNTIME**: Minimal (30 seconds per change)
**RISK**: LOW

- [x] ✅ Verify current encryption at rest (already enabled)
- [ ] ⚠️ Enable automated backups (if not enabled)
- [ ] ⚠️ Enable Point-in-Time Recovery (PITR)
- [ ] ⚠️ Configure backup retention (30 days)
- [ ] ⚠️ Document current security posture
- [ ] ⚠️ Create monitoring dashboard for backups

**Commands to Execute** (after review):
```bash
# 1. Enable automated backups
gcloud sql instances patch telepaypsql \
  --backup-start-time=04:00 \
  --backup-location=us \
  --retained-backups-count=30 \
  --retained-transaction-log-days=7 \
  --enable-bin-log \
  --project=pgp-live

# 2. Enable PITR
gcloud sql instances patch telepaypsql \
  --enable-point-in-time-recovery \
  --project=pgp-live

# 3. Enable storage auto-increase (prevent disk full from logs)
gcloud sql instances patch telepaypsql \
  --enable-storage-auto-increase \
  --storage-auto-increase-limit=500 \
  --project=pgp-live
```

#### 🟡 **Phase 2: Short-Term (Week 2-3) - SSL/TLS Enforcement**

**PRIORITY**: CRITICAL
**DOWNTIME**: 30 seconds (instance restart)
**RISK**: MEDIUM (requires testing)

- [ ] ⚠️ Test SSL enforcement in staging
- [ ] ⚠️ Coordinate maintenance window with team
- [ ] ⚠️ Enable SSL enforcement on Cloud SQL
- [ ] ⚠️ Verify all services connect successfully
- [ ] ⚠️ Monitor for connection errors (24 hours)
- [ ] ⚠️ Update documentation

**Commands to Execute** (after review):
```bash
# Enable SSL enforcement
gcloud sql instances patch telepaypsql \
  --require-ssl \
  --project=pgp-live

# Verify SSL enforcement
gcloud sql instances describe telepaypsql \
  --project=pgp-live \
  --format="value(settings.ipConfiguration.requireSsl)"
```

**Rollback Plan**:
```bash
# If issues detected (within 24 hours)
gcloud sql instances patch telepaypsql \
  --no-require-ssl \
  --project=pgp-live
```

#### 🟡 **Phase 3: Medium-Term (Week 4-6) - Audit Logging**

**PRIORITY**: HIGH
**DOWNTIME**: 30 seconds (instance restart)
**RISK**: MEDIUM (performance impact, disk usage)

- [ ] ⚠️ Enable pgAudit extension
- [ ] ⚠️ Configure audit log settings (start with DDL only)
- [ ] ⚠️ Monitor disk usage (enable auto-increase)
- [ ] ⚠️ Export logs to BigQuery
- [ ] ⚠️ Create audit log dashboards
- [ ] ⚠️ Configure audit log alerts
- [ ] ⚠️ Expand to DML logging (after performance validation)

**Commands to Execute** (after review):
```bash
# Phase 3A: Enable pgAudit (DDL only - low volume)
gcloud sql instances patch telepaypsql \
  --database-flags=cloudsql.enable_pgaudit=on,pgaudit.log=ddl \
  --project=pgp-live

# Phase 3B: Monitor performance for 1 week

# Phase 3C: Expand to DML (if performance acceptable)
gcloud sql instances patch telepaypsql \
  --database-flags=cloudsql.enable_pgaudit=on,pgaudit.log=ddl,pgaudit.log=write \
  --project=pgp-live
```

#### 🔵 **Phase 4: Long-Term (Week 8-12) - Network Security**

**PRIORITY**: HIGH
**DOWNTIME**: Coordinated deployment (2-hour window)
**RISK**: HIGH (major architecture change)

- [ ] ⚠️ Create VPC network and subnets
- [ ] ⚠️ Configure Private Service Access
- [ ] ⚠️ Create Serverless VPC Access Connector
- [ ] ⚠️ Add private IP to Cloud SQL
- [ ] ⚠️ Update ALL Cloud Run services (17 services)
- [ ] ⚠️ Test private IP connectivity (2 weeks)
- [ ] ⚠️ Remove public IP (FINAL STEP)

**Timeline**: 4 weeks (1 week per step + 2 weeks testing)

#### 🟣 **Phase 5: Ongoing - Secret Rotation & DR Testing**

**PRIORITY**: MEDIUM
**DOWNTIME**: None (automated)
**RISK**: LOW

- [ ] ⚠️ Design and implement password rotation Cloud Function
- [ ] ⚠️ Test rotation in staging
- [ ] ⚠️ Configure Cloud Scheduler (every 90 days)
- [ ] ⚠️ Document manual rotation procedure
- [ ] ⚠️ Schedule quarterly backup restoration tests
- [ ] ⚠️ Schedule annual disaster recovery drill

**Timeline**: Ongoing after initial implementation (Week 12+)

### 6.2 Success Criteria

**Deployment is successful when**:

- [x] ✅ All database connections encrypted with SSL/TLS (verified in logs)
- [ ] ⚠️ Automated backups running daily with 30-day retention
- [ ] ⚠️ Point-in-Time Recovery enabled and tested
- [ ] ⚠️ Audit logging capturing all DDL and DML operations
- [ ] ⚠️ Logs exported to BigQuery for compliance reporting
- [ ] ⚠️ Private IP configured and public IP removed
- [ ] ⚠️ Secret rotation automated (every 90 days)
- [ ] ⚠️ Disaster recovery runbook created and tested
- [ ] ⚠️ All compliance requirements documented
- [ ] ⚠️ Monitoring and alerting operational

### 6.3 Risk Mitigation

**For Each Phase**:

1. **Test in Staging First**
   - Create staging Cloud SQL instance
   - Apply changes to staging
   - Run integration tests
   - Document any issues

2. **Coordinate Maintenance Windows**
   - Notify team 48 hours in advance
   - Choose low-traffic periods (04:00 UTC)
   - Have rollback plan ready
   - Monitor closely during and after deployment

3. **Have Rollback Commands Ready**
   - Document rollback procedure
   - Test rollback in staging
   - Keep previous configuration documented
   - Monitor for 24 hours after change

4. **Monitor Closely**
   - Watch error logs (Cloud Logging)
   - Monitor connection metrics (Cloud Monitoring)
   - Check application health endpoints
   - Review database performance metrics

---

## Part 7: Monitoring & Alerting

### 7.1 Cloud Monitoring Dashboards

**OBJECTIVE**: Create visibility into database security and performance.

- [ ] **Create "Database Security" Dashboard**

  **Metrics to Include**:
  - SSL connection count vs non-SSL (should be 100% SSL)
  - Failed authentication attempts (security)
  - Connection pool utilization (performance)
  - Backup success rate (disaster recovery)
  - Storage usage (audit logs can fill disk)
  - Replication lag (if cross-region replica exists)

  **Location**: Cloud Console → Monitoring → Dashboards → Create

- [ ] **Create "Database Operations" Dashboard**

  **Metrics to Include**:
  - Query latency (p50, p95, p99)
  - Transactions per second
  - Disk IOPS
  - CPU utilization
  - Memory usage
  - Deadlock count

### 7.2 Alerting Policies

**OBJECTIVE**: Get notified of security incidents and operational issues.

- [ ] **Security Alerts (CRITICAL)**

  Create alerts for:
  - Failed authentication attempts (>5 in 5 minutes)
  - Non-SSL connection attempts (after SSL enforcement)
  - DDL operations (schema changes - audit trail)
  - Off-hours database access (outside 06:00-22:00 UTC)
  - IP whitelist violations

  **Notification**: PagerDuty, email, Slack

- [ ] **Backup Alerts (CRITICAL)**

  Create alerts for:
  - Backup failure
  - Backup not completed in 24 hours
  - Storage usage >80% (audit logs can fill disk)
  - PITR transaction log gap >1 hour

  **Notification**: Email, Slack

- [ ] **Performance Alerts (HIGH)**

  Create alerts for:
  - Connection pool exhaustion (>80% utilization)
  - Query latency >1 second (p95)
  - Disk IOPS throttling
  - CPU >80% for 5 minutes

  **Notification**: Email

### 7.3 Log Analysis Queries

**OBJECTIVE**: Proactive security monitoring via log analysis.

- [ ] **Create Saved BigQuery Queries**

  Create: `/TOOLS_SCRIPTS_TESTS/docs/AUDIT_LOG_QUERIES.sql`

  ```sql
  -- Failed Authentication Attempts
  SELECT
    timestamp,
    protoPayload.authenticationInfo.principalEmail,
    protoPayload.request.user,
    COUNT(*) as failed_attempts
  FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
  WHERE
    protoPayload.status.code != 0
    AND protoPayload.methodName LIKE '%connect%'
    AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  GROUP BY 1, 2, 3
  HAVING failed_attempts > 5
  ORDER BY failed_attempts DESC;

  -- Schema Changes (DDL Operations)
  SELECT
    timestamp,
    protoPayload.authenticationInfo.principalEmail,
    protoPayload.request.statement
  FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
  WHERE
    protoPayload.request.statement LIKE 'CREATE%'
    OR protoPayload.request.statement LIKE 'ALTER%'
    OR protoPayload.request.statement LIKE 'DROP%'
    AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  ORDER BY timestamp DESC;

  -- Large Data Exports
  SELECT
    timestamp,
    protoPayload.authenticationInfo.principalEmail,
    protoPayload.request.statement,
    protoPayload.response.rowsAffected
  FROM `pgp-live.audit_logs.cloudaudit_googleapis_com_data_access`
  WHERE
    protoPayload.request.statement LIKE 'SELECT%'
    AND protoPayload.response.rowsAffected > 10000
    AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  ORDER BY protoPayload.response.rowsAffected DESC;
  ```

  - [ ] Schedule weekly automated execution
  - [ ] Send results to compliance team
  - [ ] Review monthly for anomalies

---

## Part 8: Testing & Validation

### 8.1 Pre-Deployment Testing

**OBJECTIVE**: Validate all changes before production deployment.

- [ ] **Create Staging Environment**
  ```bash
  # DO NOT RUN - Document only
  # Clone production instance to staging
  gcloud sql instances clone telepaypsql telepaypsql-staging \
    --project=pgp-live
  ```

- [ ] **Test SSL Enforcement**
  - Deploy services to staging Cloud Run
  - Enable SSL enforcement on staging database
  - Run integration tests
  - Verify all connections succeed
  - Check logs for SSL verification

- [ ] **Test Backup Restoration**
  - Create on-demand backup of staging
  - Restore to new instance
  - Verify data integrity
  - Test application against restored instance
  - Document restoration time

- [ ] **Test PITR Recovery**
  - Create test data with timestamps
  - Perform PITR to specific timestamp
  - Verify recovered data matches expected state
  - Document recovery time

- [ ] **Load Testing with Audit Logging**
  - Enable pgAudit on staging
  - Run load tests (1000 requests/second)
  - Measure performance impact
  - Monitor disk usage growth
  - Verify logs captured correctly

### 8.2 Post-Deployment Validation

**OBJECTIVE**: Confirm security improvements are working as expected.

- [ ] **SSL Enforcement Validation**
  ```bash
  # Connect to database and verify SSL
  psql "host=<DB_IP> user=postgres dbname=telepaydb sslmode=require" \
    -c "SELECT ssl_cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
  ```
  - Expected: SSL cipher name (e.g., "ECDHE-RSA-AES256-GCM-SHA384")
  - If NULL: SSL not enforced (CRITICAL ISSUE)

- [ ] **Backup Validation**
  - Check last backup timestamp (should be <24 hours)
  - Verify backup status: SUCCESSFUL
  - Check backup size (should grow incrementally)

- [ ] **Audit Log Validation**
  - Perform test DDL operation (CREATE TABLE)
  - Query audit logs in Cloud Logging
  - Verify operation captured
  - Verify log exported to BigQuery

- [ ] **Private IP Validation** (if implemented)
  - Verify Cloud Run services connect via private IP
  - Check no traffic on public IP
  - Verify latency is acceptable (<10ms)

### 8.3 Compliance Audit Preparation

**OBJECTIVE**: Prepare evidence for compliance audits.

- [ ] **Collect Evidence Documents**
  - SSL/TLS configuration screenshot
  - Encryption at rest verification
  - Backup schedule and retention configuration
  - Audit log samples (anonymized)
  - Secret rotation schedule
  - Disaster recovery test results

- [ ] **Create Compliance Report**

  Create: `/TOOLS_SCRIPTS_TESTS/docs/COMPLIANCE_EVIDENCE_REPORT.md`

  **Contents**:
  - Security controls implemented
  - Mapping to compliance requirements (PCI-DSS, GDPR, SOC 2)
  - Test results and validation
  - Screenshots and configuration exports
  - Quarterly review dates
  - Sign-off from security team

---

## Summary & Next Steps

### Implemented Security Controls

After completing this checklist, the following controls will be in place:

✅ **Encryption**:
- SSL/TLS encryption enforced for all database connections
- AES-256 encryption at rest (Google-managed or CMEK)
- Encrypted backups

✅ **Backup & Disaster Recovery**:
- Automated daily backups (30-day retention)
- Point-in-Time Recovery (7 days)
- Cross-region replica (optional)
- Tested disaster recovery procedures

✅ **Audit & Monitoring**:
- pgAudit logging all DDL and DML operations
- Logs exported to BigQuery for analysis
- Cloud Monitoring dashboards
- Alerting on security events

✅ **Access Control**:
- Private IP only (public IP removed)
- VPC peering and Serverless VPC Connector
- Automated secret rotation (90 days)
- IAM-based access control

✅ **Compliance**:
- PCI-DSS requirements met
- GDPR requirements met
- SOC 2 requirements met
- Documentation and evidence prepared

### Immediate Action Items (Next 48 Hours)

**PRIORITY 1 - CRITICAL (Do First)**:

1. [ ] Review this checklist with team lead
2. [ ] Verify current encryption at rest (should already be enabled)
3. [ ] Check if automated backups are configured
4. [ ] Enable PITR if not already enabled
5. [ ] Document current security posture

**PRIORITY 2 - HIGH (Week 1)**:

6. [ ] Create monitoring dashboard for database security
7. [ ] Enable SSL enforcement (after testing in staging)
8. [ ] Configure backup retention (30 days)
9. [ ] Update architecture documentation

**PRIORITY 3 - MEDIUM (Week 2-4)**:

10. [ ] Enable pgAudit logging
11. [ ] Export audit logs to BigQuery
12. [ ] Create security alerts
13. [ ] Design secret rotation architecture

**PRIORITY 4 - LONG-TERM (Week 4-12)**:

14. [ ] Implement private IP migration
15. [ ] Deploy cross-region replica (if required)
16. [ ] Automate secret rotation
17. [ ] Conduct disaster recovery drill

### Dependencies & Blockers

**Must Have Before Starting**:
- [ ] Approval from team lead / architect
- [ ] Maintenance window scheduled
- [ ] Staging environment created
- [ ] Rollback plan documented
- [ ] Team members notified

**External Dependencies**:
- [ ] VPC network configuration (for private IP)
- [ ] Compliance team sign-off (for audit logging)
- [ ] Budget approval (for cross-region replica, VPC connector)

### Estimated Costs

**One-Time Costs**:
- VPC Connector creation: $0
- Cross-region replica (if used): $200-500/month

**Ongoing Costs**:
- VPC Connector: ~$50/month (always-on)
- Additional storage for audit logs: ~$10-20/month
- BigQuery for log analysis: ~$5-10/month
- Cross-region data transfer: ~$20-50/month (if replica used)
- CMEK (if used): $0.06/key/month + operations

**Total Estimated Monthly Cost**: $85-630/month (depending on options chosen)

---

## Appendix A: Reference Links

### Google Cloud Documentation

- [Cloud SQL SSL/TLS](https://cloud.google.com/sql/docs/postgres/configure-ssl-instance)
- [Cloud SQL Encryption](https://cloud.google.com/sql/docs/postgres/cmek)
- [Cloud SQL Backups](https://cloud.google.com/sql/docs/postgres/backup-recovery/backing-up)
- [Cloud SQL PITR](https://cloud.google.com/sql/docs/postgres/backup-recovery/pitr)
- [pgAudit Extension](https://cloud.google.com/sql/docs/postgres/pg-audit)
- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
- [Serverless VPC Access](https://cloud.google.com/vpc/docs/configure-serverless-vpc-access)

### Compliance Standards

- [PCI-DSS Requirements](https://www.pcisecuritystandards.org/document_library)
- [GDPR Security Requirements](https://gdpr-info.eu/)
- [SOC 2 Trust Principles](https://www.aicpa.org/interestareas/frc/assuranceadvisoryservices/aicpasoc2report)

### Best Practices Guides

- [Database Security Best Practices (Google Cloud Blog)](https://cloud.google.com/blog/products/gcp/best-practices-for-securing-your-google-cloud-databases)
- [Cloud SQL Security Checklist](https://cloud.google.com/sql/docs/postgres/security-checklist)

---

## Appendix B: Glossary

**AES-256**: Advanced Encryption Standard with 256-bit key (industry-standard encryption)

**CMEK**: Customer-Managed Encryption Key (customer controls key lifecycle)

**PITR**: Point-In-Time Recovery (restore database to specific timestamp)

**pgAudit**: PostgreSQL Audit Extension (logs database operations)

**RTO**: Recovery Time Objective (maximum acceptable downtime)

**RPO**: Recovery Point Objective (maximum acceptable data loss)

**SSL/TLS**: Secure Sockets Layer / Transport Layer Security (encryption protocols)

**VPC**: Virtual Private Cloud (isolated network environment)

---

**END OF CHECKLIST**

**Document Version**: 1.0
**Last Updated**: 2025-11-18
**Next Review**: After Phase 1 completion (Week 1)
**Owner**: PGP_v1 Development Team
**Approver**: [To be assigned]
