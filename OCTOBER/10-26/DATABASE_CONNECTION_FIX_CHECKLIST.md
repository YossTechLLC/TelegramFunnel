# Database Connection Timeout Fix Checklist
## GCBroadcastScheduler-10-26

**Date:** 2025-11-12
**Issue:** Manual broadcast trigger failing with database connection timeout (127 seconds)
**Status:** ⏸️ AWAITING APPROVAL

---

## 🔍 Root Cause Analysis

### Current Situation
- ❌ JWT authentication is **WORKING CORRECTLY** (fixed in Session 121)
- ❌ Database connection **TIMING OUT** after 127 seconds
- ❌ Users see error after long wait when clicking "Resend Messages"
- ❌ Service returns HTTP 429 (rate limit error) as fallback when DB query fails

### Error Details
```
2025-11-12 02:33:19,876 - database_manager - ERROR - ❌ Error fetching manual trigger info:
connection to server at "34.58.246.248", port 5432 failed: Connection timed out
```

### Technical Root Cause
**GCBroadcastScheduler uses WRONG database connection method:**

```python
# ❌ CURRENT (database_manager.py lines 48-54):
conn = psycopg2.connect(
    host='34.58.246.248',      # Public IP - doesn't work in Cloud Run!
    port=5432,
    dbname='telepaydb',
    user='postgres',
    password='...'
)
```

**Other services use CORRECT method (e.g., GCWebHook1):**

```python
# ✅ CORRECT:
from google.cloud.sql.connector import Connector

connector = Connector()
conn = connector.connect(
    'telepay-459221:us-central1:telepaypsql',  # Instance connection name
    'pg8000',                                   # Driver
    user='postgres',
    password='...',
    db='telepaydb'
)
```

### Why This Matters
1. **Cloud Run → Cloud SQL connectivity** requires Cloud SQL Connector or Unix socket
2. **Direct IP connection** (`34.58.246.248:5432`) is blocked/times out in Cloud Run
3. **Cloud SQL Connector** automatically handles secure connection, IP allowlisting, and authentication
4. **All other working services** in the project use Cloud SQL Connector

---

## 📋 Fix Strategy

### Option 1: Cloud SQL Connector with pg8000 (RECOMMENDED) ✅
**Advantages:**
- ✅ Matches existing service pattern (GCWebHook1, GCSplit1, etc.)
- ✅ No network configuration changes needed
- ✅ Automatic connection management and retry logic
- ✅ More secure (no public IP exposure)
- ✅ Better performance (optimized connection pooling)

**Disadvantages:**
- ⚠️ Requires code changes in database_manager.py
- ⚠️ Changes driver from psycopg2 to pg8000 (minimal syntax differences)

### Option 2: Keep psycopg2 + Configure VPC/IP Allowlist ❌
**Advantages:**
- ✅ No code changes to database_manager.py

**Disadvantages:**
- ❌ Requires VPC Connector setup (infrastructure complexity)
- ❌ Requires adding Cloud Run service IP to SQL allowlist
- ❌ Less secure (exposes public IP)
- ❌ More configuration to maintain
- ❌ Doesn't match existing service pattern

### ✅ Selected Approach: Option 1 (Cloud SQL Connector with pg8000)

---

## 🛠️ Implementation Plan

### Phase 1: Add Cloud SQL Connector Dependency
**File:** `requirements.txt`

**Change:**
```diff
  # Database
  psycopg2-binary>=2.9.0,<3.0.0
+ cloud-sql-python-connector[pg8000]>=1.4.0,<2.0.0
```

**Why:** Install Cloud SQL Connector library with pg8000 driver support

---

### Phase 2: Update ConfigManager to Fetch Connection Name
**File:** `config_manager.py`

**Add new method after `get_database_password()` (around line 169):**

```python
def get_cloud_sql_connection_name(self) -> str:
    """Get Cloud SQL instance connection name from Secret Manager."""
    return self._fetch_secret('CLOUD_SQL_CONNECTION_NAME_SECRET')
```

**Why:** Provides access to the instance connection name (`telepay-459221:us-central1:telepaypsql`)

---

### Phase 3: Replace Database Connection Logic
**File:** `database_manager.py`

**A. Update imports (lines 1-13):**
```diff
  import logging
  from typing import List, Dict, Any, Optional, Tuple
  from datetime import datetime
  from contextlib import contextmanager
- import psycopg2
- from psycopg2.extras import RealDictCursor
+ from google.cloud.sql.connector import Connector
+ import sqlalchemy
+ from sqlalchemy import create_engine, text
+ from sqlalchemy.pool import NullPool
  from config_manager import ConfigManager
```

**B. Update `__init__` method (lines 29-38):**
```diff
  def __init__(self, config_manager: ConfigManager):
      self.config = config_manager
      self.logger = logging.getLogger(__name__)
-     self._connection_params = None
+     self.connector = Connector()
+     self._engine = None
```

**C. Replace `_get_connection_params` and `get_connection` methods:**
```python
def _get_engine(self):
    """
    Get or create SQLAlchemy engine with Cloud SQL Connector.

    Returns:
        SQLAlchemy Engine instance
    """
    if self._engine is None:
        connection_name = self.config.get_cloud_sql_connection_name()
        db_name = self.config.get_database_name()
        db_user = self.config.get_database_user()
        db_password = self.config.get_database_password()

        def getconn():
            conn = self.connector.connect(
                connection_name,
                "pg8000",
                user=db_user,
                password=db_password,
                db=db_name
            )
            return conn

        self._engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            poolclass=NullPool,
        )

        self.logger.info(f"🔌 Database engine configured: {connection_name}/{db_name}")

    return self._engine

@contextmanager
def get_connection(self):
    """
    Context manager for database connections.

    Yields:
        Database connection object
    """
    engine = self._get_engine()
    conn = engine.raw_connection()
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        self.logger.error(f"❌ Database error: {e}")
        raise
    finally:
        conn.close()
```

**D. Update all SQL queries to use pg8000 syntax:**
- Replace `%s` placeholders with `?` (pg8000 uses positional parameters differently)
- Actually, keep `%s` - both psycopg2 and pg8000 support `%s` placeholders
- Update `cursor_factory=RealDictCursor` usage:

```python
# OLD (psycopg2):
with conn.cursor(cursor_factory=RealDictCursor) as cur:

# NEW (pg8000 via SQLAlchemy):
cur = conn.cursor()
# Then manually convert to dict when needed
```

**E. Add cleanup method:**
```python
def close(self):
    """Close the connector (for cleanup)."""
    if self.connector:
        self.connector.close()
        self.logger.info("🔌 Database connector closed")
```

**Why:** Replaces direct IP connection with Cloud SQL Connector pattern used by all other services

---

### Phase 4: Update Cloud Run Environment Variables
**Action:** Add `CLOUD_SQL_CONNECTION_NAME_SECRET` to environment variables

**Command:**
```bash
gcloud run services update gcbroadcastscheduler-10-26 \
  --region=us-central1 \
  --update-env-vars=CLOUD_SQL_CONNECTION_NAME_SECRET="projects/telepay-459221/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest"
```

**Why:** Allows ConfigManager to fetch the instance connection name

---

### Phase 5: Build and Deploy
**Commands:**
```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCBroadcastScheduler-10-26

# Build Docker image
gcloud builds submit --tag gcr.io/telepay-459221/gcbroadcastscheduler-10-26:latest --timeout=600s

# Deploy to Cloud Run (this will use the env var from Phase 4)
gcloud run deploy gcbroadcastscheduler-10-26 \
  --image gcr.io/telepay-459221/gcbroadcastscheduler-10-26:latest \
  --region us-central1 \
  --platform managed
```

**Why:** Deploy the updated code with Cloud SQL Connector

---

### Phase 6: Test Manual Broadcast Trigger
**Actions:**
1. Navigate to `https://www.paygateprime.com/dashboard`
2. Log in with `user1user1 : user1TEST$`
3. Find '11-11 SHIBA OPEN INSTANT' channel
4. Click "Resend Messages" button
5. Verify:
   - ✅ No timeout error
   - ✅ Fast response (< 5 seconds, not 127 seconds!)
   - ✅ Proper rate limit check
   - ✅ Success message or legitimate rate limit message

**Expected Logs:**
```
📨 Manual trigger request: broadcast=b9e74024..., client=4a690051...
⏰ Manual trigger interval: 0.0833 hours (5.0 minutes)
✅ Manual broadcast queued: b9e74024...
```

**No More:**
```
❌ Error fetching manual trigger info: connection to server at "34.58.246.248", port 5432 failed: Connection timed out
```

---

## 🔒 Security Considerations

### Current (Insecure)
- ❌ Attempts to connect to public IP `34.58.246.248`
- ❌ Exposes database to public internet (if allowlisted)
- ❌ Connection times out (currently failing)

### After Fix (Secure)
- ✅ Uses Cloud SQL Connector with automatic IAM authentication
- ✅ No public IP exposure
- ✅ Encrypted connection via Cloud SQL Proxy
- ✅ Follows Google Cloud best practices
- ✅ Matches security model of all other services

---

## 📊 Expected Outcomes

### Before Fix
- ❌ HTTP 429 after 127-second timeout
- ❌ Users frustrated by long wait + error
- ❌ Manual broadcast trigger non-functional
- ❌ Error: "Connection timed out"

### After Fix
- ✅ HTTP 200 with fast response (< 2 seconds)
- ✅ Proper rate limiting validation
- ✅ Manual broadcast trigger fully functional
- ✅ Database queries work reliably
- ✅ Matches performance of other services

---

## 🚨 Risks and Rollback Plan

### Risks
- ⚠️ **Code Changes:** Switching from psycopg2 to pg8000 might have subtle differences
- ⚠️ **Testing:** Need to verify all database operations work correctly
- ⚠️ **Query Syntax:** Some psycopg2-specific features might need adjustment

### Mitigation
- ✅ Both drivers support DB-API 2.0 standard (high compatibility)
- ✅ Using SQLAlchemy as abstraction layer reduces driver-specific code
- ✅ Will test thoroughly before marking as complete

### Rollback Plan
If issues occur after deployment:
```bash
# Revert to previous revision
gcloud run services update-traffic gcbroadcastscheduler-10-26 \
  --region=us-central1 \
  --to-revisions=gcbroadcastscheduler-10-26-00005-t9j=100
```

Previous working revision (with JWT fix): `gcbroadcastscheduler-10-26-00005-t9j`

---

## ✅ Success Criteria

- [ ] Cloud SQL Connector library installed
- [ ] ConfigManager fetches `CLOUD_SQL_CONNECTION_NAME`
- [ ] DatabaseManager uses Cloud SQL Connector
- [ ] All database queries work correctly
- [ ] Manual broadcast trigger responds in < 5 seconds
- [ ] No connection timeout errors in logs
- [ ] Rate limiting works correctly
- [ ] Service matches connection pattern of other services

---

## 📝 Notes

1. **This fix is separate from JWT authentication issue** (already fixed in Session 121)
2. **Pattern matches existing services:** GCWebHook1, GCSplit1, GCAccumulator all use Cloud SQL Connector
3. **No infrastructure changes needed:** Just code changes to use existing Cloud SQL Connector pattern
4. **Connection name secret already exists:** `CLOUD_SQL_CONNECTION_NAME = telepay-459221:us-central1:telepaypsql`

---

**Ready to proceed?** Please review this checklist and approve before I make changes.
