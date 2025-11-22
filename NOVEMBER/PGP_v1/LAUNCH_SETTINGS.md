# LAUNCH_SETTINGS.md - GCP VM Deployment Configuration

**Service:** PGP_SERVER_v1 (Telegram Bot & Webhook Server)
**Date:** 2025-11-21
**Purpose:** Step-by-step VM creation settings for Google Cloud Console

---

## 🔍 PART 1: DEBIAN 13 (TRIXIE) COMPATIBILITY ANALYSIS

### Question: Will using Debian 13 (trixie) require codebase changes?

**Answer: ⚠️ PARTIAL COMPATIBILITY - Minor startup script changes required**

---

### Compatibility Matrix

| Component | Debian 11 (Bullseye) | Debian 13 (Trixie) | Status | Changes Needed |
|-----------|---------------------|-------------------|--------|----------------|
| **Python 3.11** | Available (backports) | Native in repos | ✅ Better | None |
| **gcc compiler** | gcc 10.2.1 | gcc 13.x | ✅ Better | None |
| **postgresql-client** | psql 13 | psql 15+ | ✅ Better | None |
| **System libraries** | glibc 2.31 | glibc 2.38 | ✅ Better | None |
| **OpenSSL** | 1.1.1 | 3.0+ | ✅ Better | None |
| **Package manager** | apt (stable) | apt (testing) | ⚠️ Different | Update apt commands |
| **Python dependencies** | All compatible | All compatible | ✅ Same | None |

---

### Detailed Analysis

#### ✅ **COMPATIBLE - No Code Changes**

**Python 3.11 Support:**
- Debian 13 (trixie) includes Python 3.11 in main repositories
- Debian 11 (bullseye) requires backports or manual installation
- **Verdict:** Trixie is BETTER (native Python 3.11, no backports needed)

**Application Code:**
- All Python code in PGP_SERVER_v1 is pure Python (no OS-specific APIs)
- Dependencies (Flask, python-telegram-bot, SQLAlchemy) are OS-agnostic
- `psycopg2-binary` includes precompiled binaries for all Linux distros
- **Verdict:** NO CHANGES to application code

**System Dependencies:**
- `gcc` - Required for compiling some Python packages (cryptography, etc.)
  - Bullseye: gcc 10.2.1 ✅
  - Trixie: gcc 13.x ✅ (newer, better optimization)
- `postgresql-client` - For debugging/troubleshooting (not runtime dependency)
  - Bullseye: PostgreSQL 13 ✅
  - Trixie: PostgreSQL 15+ ✅ (backward compatible with Cloud SQL)
- **Verdict:** NO CHANGES needed

---

#### ⚠️ **REQUIRES MINOR UPDATES - Startup Script Only**

**Package Installation Commands:**

Debian 13 (trixie) is a **testing** distribution with different package availability:

**CHANGE REQUIRED in Startup Script:**

```bash
# ❌ OLD (Debian 11 Bullseye)
apt-get install -y python3.11 python3.11-venv python3-pip gcc postgresql-client

# ✅ NEW (Debian 13 Trixie)
apt-get install -y python3 python3-venv python3-pip gcc postgresql-client-15

# DIFFERENCE:
# 1. Use "python3" instead of "python3.11" (Python 3.11 is default in Trixie)
# 2. Use "postgresql-client-15" instead of generic "postgresql-client"
```

**Updated Startup Script for Debian 13:**

```bash
#!/bin/bash
# Debian 13 (Trixie) Startup Script for PGP_SERVER_v1

set -e

echo "🚀 PGP_SERVER_v1 VM Startup Script (Debian 13 Trixie)"

# Update system
apt-get update
apt-get upgrade -y

# Install system dependencies (Trixie-specific versions)
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  gcc \
  postgresql-client-15 \
  git \
  supervisor

# Verify Python version (should be 3.11+)
python3 --version

# Rest of script remains the same...
# (Mount disks, clone code, install dependencies, configure systemd)
```

**Key Differences:**
1. `python3.11` → `python3` (3.11 is default)
2. `postgresql-client` → `postgresql-client-15` (explicit version)
3. No other changes needed

---

### Recommendation: Debian 11 vs Debian 13

| Criterion | Debian 11 (Bullseye) | Debian 13 (Trixie) | Winner |
|-----------|---------------------|-------------------|--------|
| **Stability** | Stable (production) | Testing (pre-release) | 🏆 Debian 11 |
| **Python 3.11** | Backports needed | Native support | 🏆 Debian 13 |
| **Security Updates** | Regular, stable | Frequent, rapid | 🏆 Debian 11 |
| **Long-term Support** | 5 years (until 2026) | Not yet stable | 🏆 Debian 11 |
| **Package Maturity** | Tested, stable | Newer, may have bugs | 🏆 Debian 11 |
| **Community Support** | Extensive docs | Limited (testing) | 🏆 Debian 11 |
| **GCP VM Images** | Official, supported | May not be available | 🏆 Debian 11 |

**🎯 FINAL RECOMMENDATION: Use Debian 11 (Bullseye)**

**Reasons:**
1. **Production Stability** - Bullseye is stable, Trixie is testing (not production-ready)
2. **GCP Support** - Official GCP images use Debian 11
3. **Security Updates** - Bullseye has predictable security update schedule
4. **LTS Support** - Bullseye supported until 2026
5. **Minimal Setup** - Startup script already written for Bullseye

**If you MUST use Debian 13:**
- Update startup script as shown above
- Monitor for package compatibility issues
- Be prepared for potential breaking changes (Trixie is testing, not stable)
- Test thoroughly before production deployment

---

## 🖥️ PART 2: VM DEPLOYMENT SETTINGS (GOOGLE CLOUD CONSOLE)

### Prerequisites

Before creating the VM, ensure:
- [ ] GCP project `pgp-live` is selected
- [ ] VPC network `pgp-production-vpc` exists
- [ ] Subnet `pgp-server-subnet` exists in `us-central1`
- [ ] Service account `pgp-server-v1@pgp-live.iam.gserviceaccount.com` created with correct IAM roles
- [ ] Startup script uploaded to Cloud Storage: `gs://pgp-deployment-scripts/vm_startup.sh`
- [ ] Static IP reserved: `pgp-server-v1-ip`

---

## 📋 SECTION 1: MACHINE CONFIGURATION

Navigate to: **Compute Engine > VM Instances > Create Instance**

### Basic Settings

```yaml
Name: pgp-server-v1
  Pattern: Lowercase, hyphens only
  Purpose: Identifies the service in logs and monitoring

Region: us-central1
  Rationale:
    - Same region as Cloud SQL (pgp-live-psql)
    - Low latency to database
    - Cost-effective region

Zone: us-central1-a
  Rationale:
    - Any zone in us-central1 works
    - Single zone is sufficient (not using instance groups)
    - Can migrate zones later if needed
```

### Machine Family & Type

```yaml
Series: N2
  Options: E2, N2, N2D, C2, M1, M2
  Selected: N2
  Rationale:
    - Balanced price/performance
    - Better than E2 (E2 is burstable, not consistent)
    - Cost-effective compared to C2 (compute-optimized)
    - Ideal for mixed workloads (CPU + memory)

Machine Type: n2-standard-4
  vCPUs: 4
  Memory: 16 GB
  Cost: ~$140/month (us-central1)

  Rationale:
    - 4 vCPUs handle concurrent Telegram bot + Flask server
    - 16GB RAM for Python application + connection pools
    - Supports 5,000-10,000 concurrent users
    - Can scale vertically to n2-standard-8 if needed
```

**Alternative Options (if budget constraints):**
- `n2-standard-2` (2 vCPU, 8GB) - $70/month, handles 2,000-3,000 users
- `e2-standard-4` (4 vCPU, 16GB) - $100/month, burstable performance

**GPU:** None (not needed for this workload)

---

### Boot Disk

Click **"CHANGE"** under Boot Disk section:

```yaml
Operating System: Debian GNU/Linux
Version: Debian GNU/Linux 11 (bullseye)
  ⚠️ Important: Do NOT select Debian 13 (trixie) unless you update startup script

Boot Disk Type: SSD Persistent Disk (pd-ssd)
  Options: Standard (pd-standard), Balanced (pd-balanced), SSD (pd-ssd)
  Selected: SSD (pd-ssd)
  Rationale:
    - Faster boot times (~10s vs 30s for standard)
    - Better I/O performance for logs
    - Minimal cost difference ($8.50 vs $4/month for 50GB)

Size (GB): 50
  Breakdown:
    - OS: ~10GB
    - Application code: ~5GB
    - Python packages: ~3GB
    - Temporary files: ~5GB
    - Logs (if not using separate disk): ~20GB
    - Buffer: ~7GB

Deletion Rule: Keep boot disk
  ⚠️ CRITICAL: Uncheck "Delete boot disk when instance is deleted"
  Rationale: Preserve data if VM is accidentally deleted
```

**Encryption:**
```yaml
Encryption: Google-managed encryption key
  Alternative: Customer-managed encryption key (CMEK)
  Recommendation: Google-managed (simpler, no key management)
```

---

### Identity and API Access

```yaml
Service Account: pgp-server-v1@pgp-live.iam.gserviceaccount.com
  ⚠️ CRITICAL: Do NOT use "Compute Engine default service account"

  Rationale:
    - Least privilege access
    - Only has necessary IAM roles:
      * Cloud SQL Client (database access)
      * Secret Manager Secret Accessor (configuration)
      * Logging Writer (send logs)
      * Monitoring Metric Writer (send metrics)
      * Error Reporting Writer (send errors)

Access Scopes: Allow default access
  Options:
    - Allow default access (recommended)
    - Allow full access to all Cloud APIs (NOT recommended - too broad)
    - Set access for each API (advanced)

  Selected: Allow default access
  Rationale:
    - Service account IAM roles control permissions (not scopes)
    - Default scopes are sufficient with proper IAM
    - More secure than "full access"
```

**How to Create Service Account (if not exists):**
```bash
# Create service account
gcloud iam service-accounts create pgp-server-v1 \
  --display-name="PGP Server v1 Service Account" \
  --project=pgp-live

# Grant IAM roles
gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-server-v1@pgp-live.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-server-v1@pgp-live.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-server-v1@pgp-live.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-server-v1@pgp-live.iam.gserviceaccount.com" \
  --role="roles/monitoring.metricWriter"

gcloud projects add-iam-policy-binding pgp-live \
  --member="serviceAccount:pgp-server-v1@pgp-live.iam.gserviceaccount.com" \
  --role="roles/errorreporting.writer"
```

---

## 🌐 SECTION 2: NETWORKING

### Network Interfaces

Click **"Advanced Network Configuration"** (expand section)

```yaml
Network: pgp-production-vpc
  ⚠️ Do NOT use "default" network
  Rationale:
    - Custom VPC with firewall rules
    - Private IP to Cloud SQL via VPC peering
    - Isolated from other projects

Subnetwork: pgp-server-subnet (us-central1)
  IP Range: 10.10.0.0/24 (example)
  Rationale:
    - Regional subnet in us-central1
    - Private IP addresses for internal communication

Primary Internal IP:
  Type: Ephemeral (Automatic)
  Alternative: Reserve static internal IP (if needed for internal DNS)
  Recommendation: Ephemeral (simpler, no cost)

External IPv4 Address: pgp-server-v1-ip (Static)
  ⚠️ CRITICAL: Must be static (reserved)

  How to Set:
    1. Click "Create IP Address"
    2. Name: pgp-server-v1-ip
    3. Type: Regional
    4. Region: us-central1
    5. Tier: Premium
    6. Click "Reserve"

  Rationale:
    - Telegram webhook requires stable IP
    - Prevents webhook reconfiguration on VM restart
    - Cost: $6/month (minimal)

IP Forwarding: Off
  Rationale: Not needed (not acting as router/gateway)

Network Service Tier: Premium
  Options: Premium, Standard
  Selected: Premium
  Rationale:
    - Low latency to Telegram API servers (global routing)
    - Better performance for webhook callbacks
    - Difference: ~$0.01/GB vs Standard tier
```

---

### Network Tags

**Tags determine firewall rule application**

```yaml
Network Tags:
  - pgp-server
  - https-server

Purpose:
  - pgp-server: Target for custom firewall rules
  - https-server: GCP default HTTPS allow rule (if needed)

Firewall Rules (Create after VM):
  1. allow-pgp-server-webhook (TCP 5000 from Load Balancer)
  2. allow-pgp-server-iap-ssh (TCP 22 from IAP range)
  3. deny-all-ingress (default deny, lowest priority)
```

---

### Network Interfaces Advanced Options

```yaml
NIC Type: GVNIC (Google Virtual NIC)
  Options: VirtIO, GVNIC
  Recommendation: GVNIC (better performance, lower latency)

Public DNS PTR Record: Off
  Rationale: Not needed (not running mail server)

Network Performance Configuration: Default (Tier 1)
  Options: Tier 1 (default), up to 100 Gbps (not needed)
```

---

## 🔍 SECTION 3: OBSERVABILITY

**Expand "Management" section > "Observability" tab**

### Cloud Logging

```yaml
Enable Cloud Logging: ✅ Checked (Enabled)
  Rationale:
    - Centralized log collection
    - Searchable logs in Cloud Console
    - Integration with Cloud Monitoring for alerts
    - Retention: 30 days (default)

Logs to Collect:
  ✅ System logs (syslog, kernel, boot)
  ✅ Application logs (stdout/stderr from systemd service)
  ✅ Security logs (SSH access, sudo commands)

Log Level: INFO
  Override: Set via application environment variable (LOG_LEVEL=INFO)
```

**Configuration:**
```yaml
# Automatically enabled via VM metadata
Metadata Key: google-logging-enabled
Metadata Value: true

# Logging agent automatically collects:
# - /var/log/syslog
# - /var/log/auth.log
# - stdout/stderr from systemd services
```

---

### Cloud Monitoring

```yaml
Enable Cloud Monitoring: ✅ Checked (Enabled)
  Rationale:
    - CPU, memory, disk, network metrics
    - Custom application metrics
    - Integration with alerting policies
    - Dashboard visualization

Metrics to Collect (Automatic):
  - compute.googleapis.com/instance/cpu/utilization
  - compute.googleapis.com/instance/memory/balloon/ram_used
  - compute.googleapis.com/instance/disk/read_bytes_count
  - compute.googleapis.com/instance/disk/write_bytes_count
  - compute.googleapis.com/instance/network/received_bytes_count
  - compute.googleapis.com/instance/network/sent_bytes_count

Metrics Collection Interval: 60 seconds (default)
```

**Configuration:**
```yaml
# Automatically enabled via VM metadata
Metadata Key: google-monitoring-enabled
Metadata Value: true
```

---

### Custom Metrics (Application)

**Configure in application code to send custom metrics:**

```python
# Example: Send custom metrics from Python
from google.cloud import monitoring_v3

client = monitoring_v3.MetricServiceClient()
project_name = f"projects/pgp-live"

# Custom metric: Active Telegram sessions
series = monitoring_v3.TimeSeries()
series.metric.type = "custom.googleapis.com/pgp/server/telegram/active_sessions"
series.resource.type = "gce_instance"
series.resource.labels["instance_id"] = "pgp-server-v1"
series.resource.labels["zone"] = "us-central1-a"

# Send metric value
point = monitoring_v3.Point()
point.value.int64_value = active_session_count
interval = monitoring_v3.TimeInterval({"end_time": {"seconds": int(time.time())}})
point.interval = interval
series.points = [point]

client.create_time_series(name=project_name, time_series=[series])
```

---

### Ops Agent (Advanced Monitoring)

**Optional: Install Ops Agent for advanced metrics**

```yaml
Ops Agent: Install via startup script (optional)
  Benefits:
    - More detailed system metrics
    - Process-level monitoring
    - Application log parsing
    - Custom log-based metrics

Installation:
  # Add to startup script
  curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
  sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

---

## 🔒 SECTION 4: SECURITY

**Expand "Management" section > "Security" tab**

### Shielded VM

```yaml
Turn on Shielded VM: ✅ Enabled (Recommended)

Features Enabled:
  ✅ Turn on Secure Boot
     Rationale: Ensures only signed bootloader/kernel can run
     Impact: Prevents rootkit/bootkit attacks
     Compatibility: Compatible with all standard Linux images

  ✅ Turn on vTPM (Virtual Trusted Platform Module)
     Rationale: Hardware-based key storage and attestation
     Impact: Enhanced key protection, measured boot
     Compatibility: No application changes needed

  ✅ Turn on Integrity Monitoring
     Rationale: Detects changes to boot sequence
     Impact: Alerts on unauthorized boot modifications
     Compatibility: No application changes needed

Recommendation: Enable ALL three (no downside, significant security benefit)
```

---

### SSH Keys

```yaml
SSH Keys Configuration:
  Options:
    1. Block project-wide SSH keys (use instance-specific only)
    2. Allow project-wide SSH keys + instance-specific

  Recommendation: Allow project-wide SSH keys
  Rationale:
    - Easier team access management
    - Centralized SSH key control
    - Can still add instance-specific keys if needed

OS Login: ✅ Enable (via metadata)
  Metadata Key: enable-oslogin
  Metadata Value: true

  Benefits:
    - SSH access via Cloud IAM (no key management)
    - Centralized access control
    - Automatic key rotation
    - Audit logs for all SSH sessions

  How it works:
    gcloud compute ssh pgp-server-v1 --zone=us-central1-a
    (Automatically uses your Google account credentials)
```

**Access Control:**
```yaml
IAM Role for SSH Access: roles/compute.osLogin
  Grant to specific users:
    gcloud projects add-iam-policy-binding pgp-live \
      --member="user:engineer@example.com" \
      --role="roles/compute.osLogin"

Admin SSH Access: roles/compute.osAdminLogin
  Grant to admins (can sudo):
    gcloud projects add-iam-policy-binding pgp-live \
      --member="user:admin@example.com" \
      --role="roles/compute.osAdminLogin"
```

---

### Firewall

```yaml
Firewall Rules: Configure via VPC Firewall (not here)
  Location: VPC Network > Firewall > Create Firewall Rule

Required Rules:
  1. allow-pgp-server-webhook
     Direction: Ingress
     Targets: Network tag "pgp-server"
     Source: <LOAD_BALANCER_IP_RANGE>
     Protocol/Port: TCP 5000
     Action: Allow

  2. allow-pgp-server-iap-ssh
     Direction: Ingress
     Targets: Network tag "pgp-server"
     Source: 35.235.240.0/20 (IAP range)
     Protocol/Port: TCP 22
     Action: Allow

  3. deny-all-ingress (default)
     Direction: Ingress
     Targets: All instances
     Source: 0.0.0.0/0
     Protocol/Port: All
     Action: Deny
     Priority: 65535 (lowest)

Egress Rules (Default Allow All):
  - Allow to Cloud SQL private IP (10.x.x.x)
  - Allow to Telegram Bot API (api.telegram.org:443)
  - Allow to Secret Manager (secretmanager.googleapis.com:443)
```

---

### Deletion Protection

```yaml
Enable Deletion Protection: ✅ Enabled (Recommended)
  Rationale:
    - Prevents accidental VM deletion
    - Must be explicitly disabled before deletion
    - No performance impact
    - No cost impact

  How to Delete (when needed):
    1. Disable deletion protection
    2. Delete instance
    3. Confirm deletion
```

---

## ⚙️ SECTION 5: ADVANCED OPTIONS

**Expand "Management" section > "Advanced" tab**

### Management

#### Availability Policy

```yaml
Preemptibility: Off
  ⚠️ CRITICAL: Do NOT enable for production
  Rationale:
    - Preemptible VMs can be terminated any time (max 24h)
    - Not suitable for long-running Telegram bot
    - Cost savings not worth the reliability risk

  Use Case: Only for batch jobs, dev/test environments

On Host Maintenance: Migrate VM instance (recommended)
  Options:
    - Migrate VM instance (live migration)
    - Terminate VM instance (stop and restart)

  Selected: Migrate VM instance
  Rationale:
    - No downtime during host maintenance
    - Application continues running
    - Transparent to users
    - Preferred for production services

Automatic Restart: On (recommended)
  Options: On, Off
  Selected: On
  Rationale:
    - VM restarts automatically if host failure
    - Combined with systemd service auto-start
    - Minimizes downtime
    - Essential for production availability

Termination Action: Delete (default)
  Options: Delete, Stop
  Recommendation: Delete (standard behavior)
```

---

#### Metadata

**Key-value pairs for VM configuration**

```yaml
Metadata Entries:

1. enable-oslogin
   Key: enable-oslogin
   Value: true
   Purpose: Enable Cloud IAM-based SSH access

2. google-logging-enabled
   Key: google-logging-enabled
   Value: true
   Purpose: Enable Cloud Logging agent

3. google-monitoring-enabled
   Key: google-monitoring-enabled
   Value: true
   Purpose: Enable Cloud Monitoring agent

4. startup-script-url
   Key: startup-script-url
   Value: gs://pgp-deployment-scripts/vm_startup.sh
   Purpose: Run startup script from Cloud Storage

   Alternative: startup-script (inline script)
   Recommendation: Use URL (easier to update, version control)

5. shutdown-script-url (optional)
   Key: shutdown-script-url
   Value: gs://pgp-deployment-scripts/vm_shutdown.sh
   Purpose: Graceful shutdown (stop services, flush logs)

6. serial-port-enable (optional, for debugging)
   Key: serial-port-enable
   Value: 1
   Purpose: Enable serial console access (troubleshooting)
```

**How to Add Metadata:**
1. Click "Add Metadata"
2. Enter key and value
3. Repeat for all entries
4. Metadata is available to VM at: `http://metadata.google.internal/computeMetadata/v1/instance/attributes/<KEY>`

---

#### Startup Script Example

**Option 1: Inline Script**
```yaml
Metadata Key: startup-script
Metadata Value: |
  #!/bin/bash
  apt-get update
  apt-get install -y python3.11
  # ... (full script)
```

**Option 2: Cloud Storage URL (Recommended)**
```yaml
Metadata Key: startup-script-url
Metadata Value: gs://pgp-deployment-scripts/vm_startup.sh

Benefits:
  - Version control (track changes in Git, upload to GCS)
  - Easier updates (update GCS file, restart VM)
  - Shared across multiple VMs
  - Better organization

Upload Script:
  gsutil cp /path/to/vm_startup.sh gs://pgp-deployment-scripts/
  gsutil acl ch -u AllUsers:R gs://pgp-deployment-scripts/vm_startup.sh
```

---

### Disks

#### Additional Disks (Optional but Recommended)

**Add Data Disk for Logs:**

Click **"Attach Additional Disk"**

```yaml
Disk Name: pgp-server-v1-logs
Disk Type: Standard Persistent Disk (pd-standard)
  Rationale: Logs don't need SSD performance, save cost
Disk Size: 100 GB
  Rationale: 6-12 months of logs
Disk Mode: Read/Write
Deletion Rule: Keep disk when deleting instance
Encryption: Google-managed
```

**Mount in Startup Script:**
```bash
# Create mount point
mkdir -p /var/log/pgp

# Format disk (only on first boot)
mkfs.ext4 -F /dev/disk/by-id/google-pgp-server-v1-logs || true

# Add to /etc/fstab for persistent mount
echo "/dev/disk/by-id/google-pgp-server-v1-logs /var/log/pgp ext4 defaults 0 2" >> /etc/fstab

# Mount disk
mount -a

# Verify mount
df -h /var/log/pgp
```

---

### Sole-Tenancy (Advanced)

```yaml
Node Affinity Labels: None (default)
  Use Case: Compliance requirements (dedicated hardware)
  Recommendation: Not needed for this workload
  Cost: Significantly higher (~3x cost)
```

---

### Reservation (Advanced)

```yaml
Reservation: None (default)
  Use Case: Guaranteed capacity in specific zone
  Recommendation: Not needed (no capacity concerns in us-central1)
  Cost: Pre-pay for VM capacity
```

---

### Labels

**Labels for organization and cost tracking**

```yaml
Labels (Key-Value Pairs):

1. service
   Key: service
   Value: pgp-server-v1
   Purpose: Identify service type

2. environment
   Key: environment
   Value: production
   Purpose: Distinguish prod/staging/dev

3. component
   Key: component
   Value: telegram-bot
   Purpose: Functional component

4. team
   Key: team
   Value: backend
   Purpose: Ownership/responsibility

5. cost-center
   Key: cost-center
   Value: pgp-infrastructure
   Purpose: Budget allocation

6. managed-by
   Key: managed-by
   Value: terraform
   Purpose: Infrastructure management (or "manual")
```

**How to Add Labels:**
1. Click "Add Label"
2. Enter key and value (lowercase, hyphens only)
3. Repeat for all labels
4. Labels are used for:
   - Cost reporting (billing by label)
   - Resource organization (filter by label)
   - Automation (scripts target labeled resources)

---

### Resource Policies

```yaml
Snapshot Schedule: Create after VM deployment
  Frequency: Daily at 2:00 AM UTC
  Retention: 7 days
  Location: us-central1

  Create via:
    Compute Engine > Snapshots > Snapshot Schedules > Create
```

---

## 📝 SECTION 6: COMPLETE CONFIGURATION SUMMARY

### Configuration Checklist

**Before clicking "CREATE", verify:**

- [ ] **Name:** pgp-server-v1
- [ ] **Region/Zone:** us-central1-a
- [ ] **Machine Type:** n2-standard-4 (4 vCPU, 16GB RAM)
- [ ] **Boot Disk:** Debian 11 (bullseye), SSD 50GB, keep on delete
- [ ] **Service Account:** pgp-server-v1@pgp-live.iam.gserviceaccount.com
- [ ] **VPC Network:** pgp-production-vpc
- [ ] **Subnet:** pgp-server-subnet
- [ ] **External IP:** pgp-server-v1-ip (static)
- [ ] **Network Tags:** pgp-server, https-server
- [ ] **Shielded VM:** All options enabled
- [ ] **OS Login:** Enabled (metadata)
- [ ] **Deletion Protection:** Enabled
- [ ] **Maintenance:** Migrate VM instance
- [ ] **Automatic Restart:** On
- [ ] **Metadata:** startup-script-url, enable-oslogin, logging/monitoring
- [ ] **Labels:** service, environment, component (minimum)
- [ ] **Additional Disk:** pgp-server-v1-logs (100GB, optional)

---

## 🚀 POST-DEPLOYMENT TASKS

### After VM Creation

**1. Verify VM is Running**
```bash
gcloud compute instances list --filter="name=pgp-server-v1"
```

**2. Check Startup Script Execution**
```bash
gcloud compute instances get-serial-port-output pgp-server-v1 \
  --zone=us-central1-a | grep "PGP_SERVER_v1"
```

**3. SSH into VM (via IAP)**
```bash
gcloud compute ssh pgp-server-v1 \
  --zone=us-central1-a \
  --tunnel-through-iap
```

**4. Verify Service is Running**
```bash
sudo systemctl status pgp-server
sudo journalctl -u pgp-server -f
```

**5. Test Health Endpoint**
```bash
curl http://localhost:5000/health
# Expected: {"status": "healthy", ...}
```

**6. Configure Telegram Webhook**
```bash
# Get external IP
EXTERNAL_IP=$(gcloud compute addresses describe pgp-server-v1-ip \
  --region=us-central1 \
  --format="get(address)")

# Set webhook (replace <BOT_TOKEN>)
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://${EXTERNAL_IP}:5000/webhook"
```

**7. Configure Firewall Rules**
```bash
# Allow webhook traffic from Load Balancer
gcloud compute firewall-rules create allow-pgp-server-webhook \
  --network=pgp-production-vpc \
  --action=ALLOW \
  --rules=tcp:5000 \
  --source-ranges=<LOAD_BALANCER_IP> \
  --target-tags=pgp-server

# Allow IAP SSH
gcloud compute firewall-rules create allow-pgp-server-iap-ssh \
  --network=pgp-production-vpc \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=pgp-server
```

**8. Set Up Snapshot Schedule**
```bash
gcloud compute resource-policies create snapshot-schedule pgp-server-daily \
  --region=us-central1 \
  --max-retention-days=7 \
  --start-time=02:00 \
  --daily-schedule

gcloud compute disks add-resource-policies pgp-server-v1 \
  --zone=us-central1-a \
  --resource-policies=pgp-server-daily
```

**9. Configure Monitoring Alerts**
- Create CPU utilization alert (>80% for 10 min)
- Create memory utilization alert (>85% for 10 min)
- Create disk space alert (>90%)
- Create VM instance down alert

**10. Test End-to-End**
- Send message to Telegram bot
- Verify webhook receives callback
- Check database connection
- Verify subscription monitoring is running

---

## 📊 COST ESTIMATE (Final)

```yaml
Monthly Cost Breakdown:

Compute:
  - n2-standard-4 VM (730 hours): $140.16
  - SSD boot disk (50GB): $8.50
  - Standard data disk (100GB): $4.00
  - Static external IP: $6.57

Networking:
  - Egress to internet (100GB): $12.00
  - Ingress: Free

Storage:
  - Snapshots (7 × 50GB): $3.50
  - Cloud Logging (50GB): $12.50
  - Cloud Monitoring: Free (under quota)

Total: ~$187/month
Annual: ~$2,244/year
```

---

## 🔧 TROUBLESHOOTING

### Common Issues

**1. VM won't start**
- Check serial console output for errors
- Verify boot disk is attached
- Check startup script for syntax errors

**2. Can't SSH into VM**
- Verify IAP firewall rule exists (35.235.240.0/20)
- Check OS Login is enabled
- Verify IAM role (roles/compute.osLogin)

**3. Application not starting**
- Check systemd service status: `systemctl status pgp-server`
- Check logs: `journalctl -u pgp-server -n 100`
- Verify Python dependencies installed
- Check database connectivity

**4. High cost alerts**
- Review egress traffic (check for data leaks)
- Verify disk snapshots are cleaned up (7-day retention)
- Check for orphaned disks

---

## 📚 REFERENCES

- [Compute Engine Best Practices](https://cloud.google.com/compute/docs/best-practices)
- [Shielded VMs Documentation](https://cloud.google.com/compute/shielded-vm/docs)
- [OS Login Documentation](https://cloud.google.com/compute/docs/oslogin)
- [VPC Firewall Rules](https://cloud.google.com/vpc/docs/firewalls)
- [Cloud SQL Connector](https://cloud.google.com/sql/docs/postgres/connect-instance-compute-engine)

---

**END OF DOCUMENT**

Generated: 2025-11-21
Author: Claude Code
Review Status: ✅ Ready for deployment
