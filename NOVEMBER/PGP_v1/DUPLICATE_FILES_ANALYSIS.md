# PGP_v1 Duplicate Files Analysis Report

**Date:** 2025-11-15
**Working Directory:** /home/user/TelegramFunnel/NOVEMBER/PGP_v1

---

## Executive Summary

This report analyzes duplicate and shared files across all PGP_v1 services, focusing on four core file types that are replicated across multiple services. The analysis reveals significant code duplication with opportunities for consolidation through shared libraries.

### Total File Instances Found:
- **config_manager.py**: 15 copies
- **cloudtasks_client.py**: 11 copies
- **database_manager.py**: 12 copies
- **token_manager.py**: 11 copies

**Total**: 49 duplicate files across services

---

## 1. config_manager.py Analysis

### Locations (15 instances):
1. PGP_NOTIFICATIONS_v1/config_manager.py
2. PGP_BROADCAST_v1/config_manager.py
3. PGP_WEBAPI_v1/config_manager.py
4. PGP_SERVER_v1/config_manager.py
5. PGP_ORCHESTRATOR_v1/config_manager.py
6. PGP_SPLIT1_v1/config_manager.py
7. PGP_SPLIT2_v1/config_manager.py
8. PGP_SPLIT3_v1/config_manager.py
9. PGP_HOSTPAY1_v1/config_manager.py
10. PGP_HOSTPAY2_v1/config_manager.py
11. PGP_HOSTPAY3_v1/config_manager.py
12. PGP_ACCUMULATOR_v1/config_manager.py
13. PGP_INVITE_v1/config_manager.py
14. PGP_BATCHPROCESSOR_v1/config_manager.py
15. PGP_MICROBATCHPROCESSOR_v1/config_manager.py

### Common Code (Estimated 60-70% identical):

**Identical Components:**
```python
# Class structure
class ConfigManager:
    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()
        print(f"⚙️ [CONFIG] ConfigManager initialized")

# fetch_secret method (identical across most services)
def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
    try:
        secret_value = (os.getenv(secret_name_env) or '').strip() or None
        if not secret_value:
            print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set or empty")
            return None
        print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
        return secret_value
    except Exception as e:
        print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
        return None
```

**Identical Imports:**
```python
import os
from google.cloud import secretmanager
from typing import Optional
```

**Identical Database Configuration Pattern:**
```python
# All services fetch these same database configs
cloud_sql_connection_name = self.fetch_secret("CLOUD_SQL_CONNECTION_NAME", "...")
database_name = self.fetch_secret("DATABASE_NAME_SECRET", "...")
database_user = self.fetch_secret("DATABASE_USER_SECRET", "...")
database_password = self.fetch_secret("DATABASE_PASSWORD_SECRET", "...")
```

**Identical Cloud Tasks Configuration Pattern:**
```python
# All services using Cloud Tasks fetch these
cloud_tasks_project_id = self.fetch_secret("CLOUD_TASKS_PROJECT_ID", "...")
cloud_tasks_location = self.fetch_secret("CLOUD_TASKS_LOCATION", "...")
```

### Service-Specific Code (Estimated 30-40% unique):

**Differences:**

1. **PGP_NOTIFICATIONS_v1 & PGP_WEBAPI_v1**: Use different implementation
   - Directly calls Secret Manager API instead of reading from environment variables
   - Has `access_secret()` method instead of `fetch_secret()`

2. **Queue and URL Configuration**: Each service fetches different queues/URLs
   - PGP_ORCHESTRATOR_v1: `pgp_invite_queue`, `pgp_split1_queue`, `pgp_accumulator_queue`
   - PGP_ACCUMULATOR_v1: `pgp_split2_queue`, `pgp_split3_queue`, `pgp_hostpay1_queue`
   - PGP_SPLIT1_v1: `pgp_split2_queue`, `pgp_split3_queue`, `pgp_hostpay_trigger_queue`

3. **Service-Specific Secrets**:
   - PGP_SPLIT1_v1: `tps_hostpay_signing_key`, `tp_flat_fee`
   - PGP_ACCUMULATOR_v1: `host_wallet_usdt_address`, `tp_flat_fee`
   - PGP_WEBAPI_v1: `jwt_secret_key`, `signup_secret_key`, `sendgrid_api_key`

4. **Configuration Dictionary Keys**: Each service returns different config dict

### Consolidation Opportunities:

**High Priority (Can be shared 100%):**
- Base `ConfigManager` class with `__init__` and `fetch_secret`
- Database configuration fetching logic
- Cloud Tasks base configuration fetching
- Logging patterns

**Medium Priority (Requires abstraction):**
- `initialize_config` can be abstracted with service-specific config definitions
- Validation patterns for critical configurations

---

## 2. cloudtasks_client.py Analysis

### Locations (11 instances):
1. PGP_ORCHESTRATOR_v1/cloudtasks_client.py
2. PGP_SPLIT1_v1/cloudtasks_client.py
3. PGP_SPLIT2_v1/cloudtasks_client.py
4. PGP_SPLIT3_v1/cloudtasks_client.py
5. PGP_ACCUMULATOR_v1/cloudtasks_client.py
6. PGP_HOSTPAY1_v1/cloudtasks_client.py
7. PGP_HOSTPAY2_v1/cloudtasks_client.py
8. PGP_HOSTPAY3_v1/cloudtasks_client.py
9. PGP_BATCHPROCESSOR_v1/cloudtasks_client.py
10. PGP_MICROBATCHPROCESSOR_v1/cloudtasks_client.py
11. PGP_NP_IPN_v1/cloudtasks_client.py

### Common Code (Estimated 70-80% identical):

**Identical Components:**
```python
# Class structure and initialization
class CloudTasksClient:
    def __init__(self, project_id: str, location: str, signing_key: str = None):
        if not project_id or not location:
            raise ValueError("Project ID and location are required")
        self.project_id = project_id
        self.location = location
        self.signing_key = signing_key
        self.client = tasks_v2.CloudTasksClient()
        print(f"☁️ [CLOUD_TASKS] Initialized client")
        print(f"📍 [CLOUD_TASKS] Project: {project_id}, Location: {location}")

# create_task method (95% identical across all services)
def create_task(self, queue_name: str, target_url: str, payload: dict,
                schedule_delay_seconds: int = 0) -> Optional[str]:
    try:
        parent = self.client.queue_path(self.project_id, self.location, queue_name)
        print(f"🚀 [CLOUD_TASKS] Creating task for queue: {queue_name}")
        print(f"🎯 [CLOUD_TASKS] Target URL: {target_url}")
        print(f"📦 [CLOUD_TASKS] Payload size: {len(json.dumps(payload))} bytes")

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": target_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode()
            }
        }

        # Schedule delay handling (identical)
        if schedule_delay_seconds > 0:
            d = datetime.datetime.utcnow() + datetime.timedelta(seconds=schedule_delay_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(d)
            task["schedule_time"] = timestamp
            print(f"⏰ [CLOUD_TASKS] Scheduled delay: {schedule_delay_seconds}s")

        response = self.client.create_task(request={"parent": parent, "task": task})
        task_name = response.name
        print(f"✅ [CLOUD_TASKS] Task created successfully")
        print(f"🆔 [CLOUD_TASKS] Task name: {task_name}")
        return task_name
    except Exception as e:
        print(f"❌ [CLOUD_TASKS] Error creating task: {e}")
        return None
```

**Identical Imports:**
```python
import json
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import datetime
```

### Service-Specific Code (Estimated 20-30% unique):

**Differences:**

1. **Enqueue Methods**: Each service has different helper methods
   - PGP_ORCHESTRATOR_v1: `enqueue_gcwebhook2_telegram_invite()`, `enqueue_gcsplit1_payment_split()`, `enqueue_gcaccumulator_payment()`
   - PGP_ACCUMULATOR_v1: `enqueue_gcsplit2_conversion()`, `enqueue_gcsplit3_eth_to_usdt_swap()`, `enqueue_gchostpay1_execution()`
   - PGP_SPLIT1_v1: `enqueue_gcsplit2_estimate_request()`, `enqueue_gcsplit3_swap_request()`, `enqueue_hostpay_trigger()`

2. **Payload Structures**: Different services create different payloads
   - Some include encrypted tokens
   - Some include webhook signatures
   - Different field names and data structures

3. **Signature Handling**:
   - PGP_ORCHESTRATOR_v1 adds HMAC signatures to some tasks
   - Most others don't add signatures (rely on token encryption)

### Consolidation Opportunities:

**High Priority (Can be shared 100%):**
- Base `CloudTasksClient` class with `__init__` and `create_task`
- All import statements
- Error handling patterns
- Schedule delay logic

**Medium Priority (Requires abstraction):**
- Enqueue methods can be consolidated into generic `enqueue()` method
- Signature generation can be optional parameter

---

## 3. database_manager.py Analysis

### Locations (12 instances):
1. PGP_ORCHESTRATOR_v1/database_manager.py
2. PGP_SPLIT1_v1/database_manager.py
3. PGP_SPLIT2_v1/database_manager.py
4. PGP_ACCUMULATOR_v1/database_manager.py
5. PGP_HOSTPAY1_v1/database_manager.py
6. PGP_HOSTPAY3_v1/database_manager.py
7. PGP_INVITE_v1/database_manager.py
8. PGP_BATCHPROCESSOR_v1/database_manager.py
9. PGP_MICROBATCHPROCESSOR_v1/database_manager.py
10. PGP_NOTIFICATIONS_v1/database_manager.py
11. PGP_BROADCAST_v1/database_manager.py
12. PGP_NP_IPN_v1/database_manager.py

### Common Code (Estimated 50-60% identical):

**Identical Components:**
```python
# Class structure and initialization
class DatabaseManager:
    def __init__(self, instance_connection_name: str, db_name: str,
                 db_user: str, db_password: str):
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.connector = Connector()
        print(f"🗄️ [DATABASE] DatabaseManager initialized")
        print(f"📊 [DATABASE] Instance: {instance_connection_name}")
        print(f"📊 [DATABASE] Database: {db_name}")

# get_connection method (100% identical)
def get_connection(self):
    try:
        connection = self.connector.connect(
            self.instance_connection_name,
            "pg8000",
            user=self.db_user,
            password=self.db_password,
            db=self.db_name
        )
        print(f"🔗 [DATABASE] Connection established successfully")
        return connection
    except Exception as e:
        print(f"❌ [DATABASE] Connection failed: {e}")
        return None

# Helper methods (identical across many services)
def get_current_timestamp(self) -> str:
    now = datetime.now()
    return now.strftime('%H:%M:%S')

def get_current_datestamp(self) -> str:
    now = datetime.now()
    return now.strftime('%Y-%m-%d')
```

**Identical Imports:**
```python
from datetime import datetime
from typing import Optional
from google.cloud.sql.connector import Connector
```

### Service-Specific Code (Estimated 40-50% unique):

**Differences:**

1. **Database Operations**: Completely different per service
   - PGP_ORCHESTRATOR_v1: `record_private_channel_user()`, `get_payout_strategy()`, `get_subscription_id()`, `get_nowpayments_data()`
   - PGP_ACCUMULATOR_v1: `insert_payout_accumulation_pending()`, `get_client_accumulation_total()`, `get_client_threshold()`, `update_accumulation_conversion_status()`
   - Each service accesses different tables

2. **Table Access Patterns**:
   - PGP_ORCHESTRATOR_v1: `private_channel_users_database`, `main_clients_database`
   - PGP_ACCUMULATOR_v1: `payout_accumulation`, `main_clients_database`
   - Different queries, different data models

3. **Return Types**: Different methods return different data structures

### Consolidation Opportunities:

**High Priority (Can be shared 100%):**
- Base `DatabaseManager` class with `__init__` and `get_connection`
- Timestamp/datestamp helper methods
- Error handling patterns
- Connection management (try/finally patterns)

**Low Priority (Service-specific by nature):**
- Database operations are inherently service-specific
- Query methods should remain in individual services
- Could benefit from shared query builder utilities

---

## 4. token_manager.py Analysis

### Locations (11 instances):
1. PGP_ORCHESTRATOR_v1/token_manager.py
2. PGP_SPLIT1_v1/token_manager.py
3. PGP_SPLIT2_v1/token_manager.py
4. PGP_SPLIT3_v1/token_manager.py
5. PGP_ACCUMULATOR_v1/token_manager.py
6. PGP_HOSTPAY1_v1/token_manager.py
7. PGP_HOSTPAY2_v1/token_manager.py
8. PGP_HOSTPAY3_v1/token_manager.py
9. PGP_INVITE_v1/token_manager.py
10. PGP_BATCHPROCESSOR_v1/token_manager.py
11. PGP_MICROBATCHPROCESSOR_v1/token_manager.py

### Common Code (Estimated 40-50% identical):

**Identical Components:**
```python
# Class structure
class TokenManager:
    def __init__(self, signing_key: str):
        self.signing_key = signing_key
        print(f"🔐 [TOKEN] TokenManager initialized")

# Helper methods (100% identical across services that have them)
def _pack_string(self, s: str) -> bytes:
    s_bytes = s.encode('utf-8')
    if len(s_bytes) > 255:
        raise ValueError(f"String too long (max 255 bytes): {s}")
    return bytes([len(s_bytes)]) + s_bytes

def _unpack_string(self, data: bytes, offset: int) -> Tuple[str, int]:
    length = data[offset]
    offset += 1
    s_bytes = data[offset:offset + length]
    offset += length
    return s_bytes.decode('utf-8'), offset
```

**Identical Imports:**
```python
import base64
import hmac
import hashlib
import struct
import time
from typing import Optional, Dict, Any, Tuple
```

**Common Patterns:**
- Base64 encoding/decoding
- HMAC-SHA256 signature generation/verification
- Timestamp validation (with varying windows)
- Truncated signatures (16 bytes)

### Service-Specific Code (Estimated 50-60% unique):

**Differences:**

1. **Token Formats**: Each service pair has different token structures
   - PGP_ORCHESTRATOR_v1: Decodes NOWPayments tokens, encrypts for GCWebhook2
   - PGP_SPLIT1_v1: Complex multi-directional encryption (to/from Split2, Split3)
   - PGP_ACCUMULATOR_v1: Accumulator-specific tokens (to/from Split3, HostPay1)

2. **Encryption/Decryption Methods**: Service-specific method names
   - `encrypt_token_for_gcwebhook2()`
   - `encrypt_gcsplit1_to_gcsplit2_token()`
   - `encrypt_accumulator_to_gcsplit3_token()`
   - Each with different parameters and binary packing structures

3. **Field Structures**: Different data packed into tokens
   - User IDs, channel IDs, amounts, addresses, currency info
   - Different field orderings
   - Different validation rules

### Consolidation Opportunities:

**High Priority (Can be shared 100%):**
- Base `TokenManager` class with `__init__`
- `_pack_string()` and `_unpack_string()` helper methods
- Common signature generation/verification logic
- Base64 encoding/decoding utilities
- Timestamp validation utilities

**Medium Priority (Requires abstraction):**
- Generic `encrypt_token()` and `decrypt_token()` with configurable schemas
- Token format definitions could be externalized
- Signature handling could be standardized

---

## Summary Statistics

### Code Duplication by File Type:

| File Type | Instances | Common Code % | Unique Code % | Consolidation Priority |
|-----------|-----------|---------------|---------------|------------------------|
| config_manager.py | 15 | 60-70% | 30-40% | **HIGH** |
| cloudtasks_client.py | 11 | 70-80% | 20-30% | **VERY HIGH** |
| database_manager.py | 12 | 50-60% | 40-50% | **MEDIUM** |
| token_manager.py | 11 | 40-50% | 50-60% | **MEDIUM** |

### Estimated Lines of Code:

| File Type | Avg Lines/File | Total Lines | Duplicate Lines | Unique Lines |
|-----------|----------------|-------------|-----------------|--------------|
| config_manager.py | ~170 | ~2,550 | ~1,700 | ~850 |
| cloudtasks_client.py | ~200 | ~2,200 | ~1,650 | ~550 |
| database_manager.py | ~300 | ~3,600 | ~1,950 | ~1,650 |
| token_manager.py | ~400 | ~4,400 | ~1,950 | ~2,450 |
| **TOTAL** | - | **~12,750** | **~7,250** | **~5,500** |

**Duplication Rate: ~57%** of code is duplicated across services

---

## Consolidation Recommendations

### Phase 1: Immediate Wins (High Priority)

**1. Create Shared Base Classes**
```
PGP_v1/
├── shared/
│   ├── __init__.py
│   ├── base_config_manager.py    # Base ConfigManager class
│   ├── base_cloudtasks_client.py # Base CloudTasksClient class
│   ├── base_database_manager.py  # Base DatabaseManager class
│   └── base_token_manager.py     # Base TokenManager class
```

**Benefits:**
- Eliminate ~7,250 lines of duplicate code
- Single source of truth for common patterns
- Easier bug fixes (fix once, apply everywhere)
- Consistent error handling and logging

**Estimated Effort:** 2-3 days
**Risk:** Low (can be done incrementally)

### Phase 2: Service-Specific Extensions (Medium Priority)

**2. Service Classes Extend Base Classes**
```python
# Example: PGP_ORCHESTRATOR_v1/config_manager.py
from shared.base_config_manager import BaseConfigManager

class ConfigManager(BaseConfigManager):
    def initialize_config(self) -> dict:
        # Service-specific configuration
        base_config = super().get_base_config()  # Database, Cloud Tasks

        # Add service-specific secrets
        base_config.update({
            'pgp_invite_queue': self.fetch_secret("PGP_INVITE_QUEUE", "..."),
            'pgp_invite_url': self.fetch_secret("PGP_INVITE_URL", "..."),
            # ... other service-specific configs
        })

        return base_config
```

**Benefits:**
- Maintain service-specific logic
- Reduce code by 50-70% per file
- Easier to add new services

**Estimated Effort:** 3-4 days
**Risk:** Medium (requires testing each service)

### Phase 3: Utilities and Helpers (Low Priority)

**3. Shared Utility Modules**
```
PGP_v1/
├── shared/
│   ├── utils/
│   │   ├── token_utils.py    # Common token packing/unpacking
│   │   ├── db_utils.py       # Common query patterns
│   │   └── validation.py     # Common validation logic
```

**Benefits:**
- DRY principle enforcement
- Reusable components
- Easier testing

**Estimated Effort:** 2-3 days
**Risk:** Low

---

## Implementation Strategy

### Recommended Approach:

1. **Start with cloudtasks_client.py** (70-80% common code)
   - Create `shared/base_cloudtasks_client.py`
   - Migrate `__init__` and `create_task` to base class
   - Update one service as proof of concept
   - Gradually migrate other services

2. **Move to config_manager.py** (60-70% common code)
   - Create `shared/base_config_manager.py`
   - Migrate common secret fetching logic
   - Update services incrementally

3. **Then database_manager.py** (50-60% common code)
   - Create `shared/base_database_manager.py`
   - Migrate connection management
   - Keep service-specific queries in service classes

4. **Finally token_manager.py** (40-50% common code)
   - Create `shared/base_token_manager.py`
   - Migrate helper methods and common patterns
   - Consider token schema abstraction

### Testing Strategy:

1. **Unit Tests**: Create tests for base classes
2. **Integration Tests**: Test service-specific extensions
3. **Regression Tests**: Ensure no behavioral changes
4. **Gradual Rollout**: One service at a time

---

## Risk Assessment

### Low Risk:
- Creating base classes without modifying existing services
- Migrating utility functions
- Adding tests

### Medium Risk:
- Updating service classes to extend base classes
- Changing import paths
- Testing all services

### High Risk:
- None identified (incremental approach mitigates risk)

---

## Expected Benefits

### Code Quality:
- **Reduced LOC**: ~7,250 lines eliminated
- **Maintainability**: Single source of truth for common patterns
- **Consistency**: Same error handling, logging across all services
- **Bug Fixes**: Fix once, apply everywhere

### Developer Productivity:
- **Faster Development**: New services easier to create
- **Easier Debugging**: Common patterns easier to trace
- **Better Onboarding**: Less code to understand

### Testing:
- **Easier Testing**: Test base classes once
- **Better Coverage**: Common code tested thoroughly
- **Regression Prevention**: Changes to base affect all services

---

## Conclusion

The PGP_v1 architecture contains significant code duplication across 49 files, with approximately **57% of code duplicated**. By implementing a shared base class architecture, we can:

1. Eliminate ~7,250 lines of duplicate code
2. Improve maintainability and consistency
3. Reduce bugs through single source of truth
4. Speed up development of new services

The recommended approach is to start with **cloudtasks_client.py** (highest duplication rate) and gradually migrate other file types, using an incremental strategy to minimize risk.

---

**Next Steps:**
1. Review and approve this analysis
2. Create proof of concept with cloudtasks_client base class
3. Test POC with one service (e.g., PGP_ORCHESTRATOR_v1)
4. Roll out to remaining services
5. Repeat for other file types

---

*End of Analysis*
