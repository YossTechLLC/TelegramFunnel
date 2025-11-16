# Shared Library Architecture - PGP_v1 Services

## Problem Statement

**Current State:**
- 49 duplicate files across 17 services
- 57% code duplication (~7,250 lines)
- Maintenance nightmare: Function renaming requires updating 11+ files
- High risk of inconsistencies and bugs
- Violates DRY (Don't Repeat Yourself) principle

**Impact:**
- Phase 2.5 (function renaming) requires ~30 function updates across 11 files
- Future bug fixes require updates in multiple locations
- Testing complexity increases exponentially

## Proposed Solution: Shared Library Pattern

Create a **pgp_common** Python package that all services import as a dependency.

### Architecture Overview

```
PGP_v1/
├── pgp_common/                          # NEW: Shared library package
│   ├── __init__.py
│   ├── setup.py                         # Package installation config
│   ├── README.md                        # Library documentation
│   ├── requirements.txt                 # Shared dependencies
│   │
│   ├── config/                          # Configuration management
│   │   ├── __init__.py
│   │   └── base_config.py              # BaseConfigManager class
│   │
│   ├── database/                        # Database operations
│   │   ├── __init__.py
│   │   └── db_manager.py               # BaseDatabaseManager class
│   │
│   ├── cloudtasks/                      # Cloud Tasks operations
│   │   ├── __init__.py
│   │   ├── base_client.py              # BaseCloudTasksClient class
│   │   └── enqueue_helpers.py          # Shared enqueue logic
│   │
│   ├── tokens/                          # Token management
│   │   ├── __init__.py
│   │   ├── base_token.py               # BaseTokenManager class
│   │   └── crypto_helpers.py           # Shared crypto functions
│   │
│   └── utils/                           # Common utilities
│       ├── __init__.py
│       └── logging.py                  # Standardized logging
│
├── PGP_ORCHESTRATOR_v1/
│   ├── pgp_orchestrator_v1.py          # Main service (UNCHANGED)
│   ├── config_manager.py               # Service-specific config (inherits from pgp_common)
│   ├── cloudtasks_client.py            # Service-specific tasks (inherits from pgp_common)
│   ├── database_manager.py             # Service-specific queries (inherits from pgp_common)
│   ├── token_manager.py                # Service-specific tokens (inherits from pgp_common)
│   ├── Dockerfile                      # UPDATED: Install pgp_common
│   └── requirements.txt                # UPDATED: Add -e ../pgp_common
│
├── PGP_SPLIT1_v1/
│   ├── ...                             # Same pattern
│
└── ... (all other services follow same pattern)
```

## Implementation Design

### 1. pgp_common/config/base_config.py

**Base class for configuration management:**

```python
#!/usr/bin/env python
"""
Base Configuration Manager for PGP_v1 Services
Provides common configuration loading patterns.
"""
import os
from google.cloud import secretmanager
from typing import Optional, Dict


class BaseConfigManager:
    """
    Base class for configuration management across PGP_v1 services.
    Service-specific config managers should inherit from this class.
    """

    def __init__(self, service_name: str):
        """
        Initialize the BaseConfigManager.

        Args:
            service_name: Name of the service (e.g., "PGP_ORCHESTRATOR_v1")
        """
        self.service_name = service_name
        self.client = secretmanager.SecretManagerServiceClient()
        print(f"⚙️ [CONFIG] ConfigManager initialized for {service_name}")

    def fetch_secret(self, secret_name_env: str, description: str = "") -> Optional[str]:
        """
        Fetch a secret value from environment variable.
        Cloud Run automatically injects secret values when using --set-secrets.

        Args:
            secret_name_env: Environment variable name containing the secret value
            description: Description for logging purposes

        Returns:
            Secret value or None if failed
        """
        try:
            # Defensive pattern: handle None, strip whitespace, return None if empty
            secret_value = (os.getenv(secret_name_env) or '').strip() or None
            if not secret_value:
                print(f"❌ [CONFIG] Environment variable {secret_name_env} is not set or empty")
                return None

            print(f"✅ [CONFIG] Successfully loaded {description or secret_name_env}")
            return secret_value

        except Exception as e:
            print(f"❌ [CONFIG] Error loading {description or secret_name_env}: {e}")
            return None

    def fetch_cloud_tasks_config(self) -> Dict[str, Optional[str]]:
        """
        Fetch Cloud Tasks configuration (common across all services).

        Returns:
            Dictionary with cloud_tasks_project_id and cloud_tasks_location
        """
        cloud_tasks_project_id = self.fetch_secret(
            "CLOUD_TASKS_PROJECT_ID",
            "Cloud Tasks project ID"
        )

        cloud_tasks_location = self.fetch_secret(
            "CLOUD_TASKS_LOCATION",
            "Cloud Tasks location/region"
        )

        return {
            'cloud_tasks_project_id': cloud_tasks_project_id,
            'cloud_tasks_location': cloud_tasks_location
        }

    def fetch_database_config(self) -> Dict[str, Optional[str]]:
        """
        Fetch database configuration (common across all services).

        Returns:
            Dictionary with database connection parameters
        """
        cloud_sql_connection_name = self.fetch_secret(
            "CLOUD_SQL_CONNECTION_NAME",
            "Cloud SQL instance connection name"
        )

        database_name = self.fetch_secret(
            "DATABASE_NAME_SECRET",
            "Database name"
        )

        database_user = self.fetch_secret(
            "DATABASE_USER_SECRET",
            "Database user"
        )

        database_password = self.fetch_secret(
            "DATABASE_PASSWORD_SECRET",
            "Database password"
        )

        return {
            'instance_connection_name': cloud_sql_connection_name,
            'db_name': database_name,
            'db_user': database_user,
            'db_password': database_password
        }

    def initialize_config(self) -> dict:
        """
        Initialize configuration. Must be implemented by subclasses.

        Returns:
            Dictionary containing all configuration values
        """
        raise NotImplementedError("Subclasses must implement initialize_config()")
```

**Service-specific usage (e.g., PGP_ORCHESTRATOR_v1/config_manager.py):**

```python
#!/usr/bin/env python
"""
Configuration Manager for PGP_ORCHESTRATOR_v1.
"""
from pgp_common.config.base_config import BaseConfigManager


class ConfigManager(BaseConfigManager):
    """
    Service-specific configuration for PGP_ORCHESTRATOR_v1.
    """

    def __init__(self):
        super().__init__(service_name="PGP_ORCHESTRATOR_v1")

    def initialize_config(self) -> dict:
        """Initialize PGP Orchestrator configuration."""
        print(f"⚙️ [CONFIG] Initializing {self.service_name} configuration")

        # Use base class methods for common config
        cloud_tasks = self.fetch_cloud_tasks_config()
        database = self.fetch_database_config()

        # Fetch service-specific secrets
        success_url_signing_key = self.fetch_secret(
            "SUCCESS_URL_SIGNING_KEY",
            "Success URL signing key"
        )

        pgp_invite_queue = self.fetch_secret(
            "PGP_INVITE_QUEUE",
            "PGP Invite queue name"
        )

        pgp_invite_url = self.fetch_secret(
            "PGP_INVITE_URL",
            "PGP Invite service URL"
        )

        # ... other service-specific secrets

        config = {
            # Common config (from base class)
            **cloud_tasks,
            **database,

            # Service-specific config
            'success_url_signing_key': success_url_signing_key,
            'pgp_invite_queue': pgp_invite_queue,
            'pgp_invite_url': pgp_invite_url,
            # ...
        }

        return config
```

### 2. pgp_common/cloudtasks/base_client.py

**Base class for Cloud Tasks operations:**

```python
#!/usr/bin/env python
"""
Base Cloud Tasks Client for PGP_v1 Services
Provides common Cloud Tasks patterns and enqueue logic.
"""
from google.cloud import tasks_v2
import json
from typing import Optional


class BaseCloudTasksClient:
    """
    Base class for Cloud Tasks operations across PGP_v1 services.
    Handles task creation, queue management, and error handling.
    """

    def __init__(self, project_id: str, location: str, service_name: str):
        """
        Initialize the Cloud Tasks client.

        Args:
            project_id: GCP project ID
            location: Cloud Tasks location (e.g., 'us-central1')
            service_name: Name of the calling service for logging
        """
        self.project_id = project_id
        self.location = location
        self.service_name = service_name
        self.client = tasks_v2.CloudTasksClient()

        print(f"✅ [CLOUD-TASKS] Initialized for {service_name}")
        print(f"   Project: {project_id}")
        print(f"   Location: {location}")

    def create_task(
        self,
        queue_name: str,
        target_url: str,
        payload: dict,
        task_name: Optional[str] = None,
        delay_seconds: int = 0
    ) -> Optional[str]:
        """
        Create a Cloud Task (COMMON ACROSS ALL SERVICES).

        Args:
            queue_name: Name of the queue (without project/location prefix)
            target_url: Full URL of the target endpoint
            payload: Dictionary payload to send
            task_name: Optional task name (auto-generated if None)
            delay_seconds: Delay before task execution

        Returns:
            Task name if successful, None otherwise
        """
        try:
            # Construct queue path
            parent = self.client.queue_path(
                self.project_id,
                self.location,
                queue_name
            )

            # Create task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode()
                }
            }

            if delay_seconds > 0:
                import datetime
                import google.protobuf.timestamp_pb2 as timestamp_pb2

                d = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(d)
                task["schedule_time"] = timestamp

            if task_name:
                task["name"] = self.client.task_path(
                    self.project_id,
                    self.location,
                    queue_name,
                    task_name
                )

            # Enqueue task
            response = self.client.create_task(
                request={"parent": parent, "task": task}
            )

            print(f"✅ [CLOUD-TASKS] Task created: {response.name}")
            return response.name

        except Exception as e:
            print(f"❌ [CLOUD-TASKS] Failed to create task: {e}")
            return None

    # Service-specific enqueue methods will be defined in subclasses
```

**Service-specific usage (e.g., PGP_ORCHESTRATOR_v1/cloudtasks_client.py):**

```python
#!/usr/bin/env python
"""
Cloud Tasks Client for PGP_ORCHESTRATOR_v1.
"""
from pgp_common.cloudtasks.base_client import BaseCloudTasksClient


class CloudTasksClient(BaseCloudTasksClient):
    """
    Service-specific Cloud Tasks client for PGP_ORCHESTRATOR_v1.
    """

    def __init__(self, project_id: str, location: str):
        super().__init__(
            project_id=project_id,
            location=location,
            service_name="PGP_ORCHESTRATOR_v1"
        )

    def enqueue_pgp_invite_telegram_invite(
        self,
        queue_name: str,
        target_url: str,
        user_id: int,
        # ... other params
    ) -> Optional[str]:
        """Enqueue PGP Invite telegram invitation task."""
        payload = {
            'user_id': user_id,
            # ... build payload
        }

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )

    def enqueue_pgp_split1_payment_split(
        self,
        queue_name: str,
        target_url: str,
        # ... other params
    ) -> Optional[str]:
        """Enqueue PGP Split1 payment split task."""
        payload = {
            # ... build payload
        }

        return self.create_task(
            queue_name=queue_name,
            target_url=target_url,
            payload=payload
        )
```

### 3. pgp_common/database/db_manager.py

**Base class for database operations:**

```python
#!/usr/bin/env python
"""
Base Database Manager for PGP_v1 Services
Provides common database connection and query patterns.
"""
from google.cloud.sql.connector import Connector
import sqlalchemy
from typing import Optional


class BaseDatabaseManager:
    """
    Base class for database management across PGP_v1 services.
    Handles connection pooling and common query patterns.
    """

    def __init__(
        self,
        instance_connection_name: str,
        db_name: str,
        db_user: str,
        db_password: str,
        service_name: str
    ):
        """Initialize database manager."""
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.service_name = service_name

        self.connector = Connector()
        self.pool = None

        print(f"🗄️ [DATABASE] Initialized for {service_name}")

    def get_connection(self):
        """Get database connection (COMMON PATTERN)."""
        return self.connector.connect(
            self.instance_connection_name,
            "pymysql",
            user=self.db_user,
            password=self.db_password,
            db=self.db_name
        )

    def get_pool(self) -> sqlalchemy.engine.Engine:
        """Get or create connection pool (COMMON PATTERN)."""
        if self.pool is None:
            self.pool = sqlalchemy.create_engine(
                "mysql+pymysql://",
                creator=self.get_connection,
                pool_size=5,
                max_overflow=2,
                pool_timeout=30,
                pool_recycle=1800,
            )
            print(f"✅ [DATABASE] Connection pool created")
        return self.pool

    # Service-specific query methods will be defined in subclasses
```

### 4. pgp_common/tokens/base_token.py

**Base class for token management:**

```python
#!/usr/bin/env python
"""
Base Token Manager for PGP_v1 Services
Provides common token encryption/decryption patterns.
"""
import hmac
import hashlib
import struct
from typing import Optional


class BaseTokenManager:
    """
    Base class for token management across PGP_v1 services.
    Handles HMAC signatures and token packing/unpacking.
    """

    def __init__(self, signing_key: str, service_name: str):
        """Initialize token manager."""
        self.signing_key = signing_key.encode('utf-8')
        self.service_name = service_name
        print(f"🔐 [TOKEN] Initialized for {service_name}")

    def _pack_string(self, s: str) -> bytes:
        """Pack string with length prefix (COMMON HELPER)."""
        encoded = s.encode('utf-8')
        return struct.pack('I', len(encoded)) + encoded

    def _unpack_string(self, data: bytes, offset: int) -> tuple:
        """Unpack string with length prefix (COMMON HELPER)."""
        length = struct.unpack_from('I', data, offset)[0]
        offset += 4
        string = data[offset:offset + length].decode('utf-8')
        offset += length
        return string, offset

    def create_hmac_signature(self, data: bytes) -> bytes:
        """Create HMAC-SHA256 signature (COMMON PATTERN)."""
        return hmac.new(self.signing_key, data, hashlib.sha256).digest()

    def verify_hmac_signature(self, data: bytes, signature: bytes) -> bool:
        """Verify HMAC-SHA256 signature (COMMON PATTERN)."""
        expected = self.create_hmac_signature(data)
        return hmac.compare_digest(expected, signature)

    # Service-specific token methods will be defined in subclasses
```

### 5. pgp_common/setup.py

**Package installation configuration:**

```python
#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='pgp-common',
    version='1.0.0',
    description='Shared library for PGP_v1 microservices',
    author='PayGatePrime',
    packages=find_packages(),
    install_requires=[
        'google-cloud-secret-manager>=2.16.0',
        'google-cloud-tasks>=2.13.0',
        'cloud-sql-python-connector>=1.4.0',
        'sqlalchemy>=2.0.0',
        'pymysql>=1.1.0',
    ],
    python_requires='>=3.10',
)
```

## Dockerfile Updates

Each service's Dockerfile needs to install the shared library:

```dockerfile
# Multi-stage build
FROM python:3.10-slim AS builder

WORKDIR /app

# Copy shared library FIRST
COPY pgp_common/ /app/pgp_common/

# Install shared library
RUN pip install -e /app/pgp_common/

# Copy service-specific code
COPY PGP_ORCHESTRATOR_v1/ /app/

# Install service-specific requirements
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages and code from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app /app

CMD ["python", "pgp_orchestrator_v1.py"]
```

## requirements.txt Updates

Each service's requirements.txt:

```txt
# Existing dependencies
flask>=3.0.0
flask-cors>=4.0.0
# ... other deps

# Shared library (installed from local path during Docker build)
# -e ../pgp_common  # This line is for local development only
```

## Benefits

### 1. Code Reduction
- **Before**: 49 files, ~12,750 lines
- **After**: 1 shared library + 17 thin wrappers = ~5,000 lines
- **Reduction**: 60% less code to maintain

### 2. Maintainability
- **Function renaming**: Update 1 file instead of 11
- **Bug fixes**: Fix once, applies to all services
- **Feature additions**: Add to base class, available everywhere

### 3. Consistency
- All services use identical patterns
- Standardized error handling
- Standardized logging
- Reduced risk of inconsistencies

### 4. Testing
- Test base classes once
- Service-specific tests only for unique logic
- Much smaller test surface area

### 5. Versioning
- Version the shared library
- Pin to specific versions for stability
- Easy rollback if issues arise

## Implementation Checklist

### Phase 1: Create Shared Library (Week 1)
- [ ] Create `pgp_common/` directory structure
- [ ] Implement `config/base_config.py`
- [ ] Implement `cloudtasks/base_client.py`
- [ ] Implement `database/db_manager.py`
- [ ] Implement `tokens/base_token.py`
- [ ] Create `setup.py` and `requirements.txt`
- [ ] Add unit tests for base classes
- [ ] Document API with examples

### Phase 2: Migrate One Service (Week 1-2)
- [ ] Choose pilot service (recommend PGP_ORCHESTRATOR_v1)
- [ ] Update `config_manager.py` to inherit from base
- [ ] Update `cloudtasks_client.py` to inherit from base
- [ ] Update `database_manager.py` to inherit from base
- [ ] Update `token_manager.py` to inherit from base
- [ ] Update Dockerfile to install pgp_common
- [ ] Test locally
- [ ] Deploy and validate
- [ ] Document migration process

### Phase 3: Migrate Remaining Services (Week 2-3)
- [ ] Migrate PGP_INVITE_v1
- [ ] Migrate PGP_SPLIT1_v1
- [ ] Migrate PGP_SPLIT2_v1
- [ ] Migrate PGP_SPLIT3_v1
- [ ] Migrate PGP_HOSTPAY1_v1
- [ ] Migrate PGP_HOSTPAY2_v1
- [ ] Migrate PGP_HOSTPAY3_v1
- [ ] Migrate PGP_ACCUMULATOR_v1
- [ ] Migrate PGP_BATCHPROCESSOR_v1
- [ ] Migrate PGP_MICROBATCHPROCESSOR_v1
- [ ] Migrate PGP_NP_IPN_v1
- [ ] Migrate remaining services

### Phase 4: Function Renaming (Week 3)
- [ ] Update function names in `pgp_common/cloudtasks/base_client.py`
- [ ] Update service-specific enqueue methods
- [ ] Test all services
- [ ] Deploy all services
- [ ] Validate end-to-end

### Phase 5: Cleanup (Week 4)
- [ ] Remove old duplicate files
- [ ] Update documentation
- [ ] Create library version 1.0.0
- [ ] Tag and release

## Best Practices (Context7 + Google MCP)

### 1. Dependency Injection
✅ Services receive config objects, not hardcoded values
✅ Easy to mock for testing

### 2. Interface Segregation
✅ Base classes provide core functionality
✅ Services only implement what they need

### 3. Single Responsibility
✅ Each base class has one clear purpose
✅ No "god objects"

### 4. Cloud-Native Patterns
✅ Stateless services
✅ Configuration via environment variables
✅ Secrets via Secret Manager
✅ Connection pooling for efficiency

### 5. Error Handling
✅ Consistent error patterns
✅ Proper logging
✅ Graceful degradation

### 6. Testing
✅ Unit tests for base classes
✅ Integration tests for services
✅ Mock external dependencies

## Risk Assessment

### Low Risk
- **Backward compatibility**: Services still use same interfaces
- **Gradual migration**: Migrate one service at a time
- **Easy rollback**: Keep old code until migration complete

### Medium Risk
- **Docker build complexity**: Multi-stage builds required
- **Local development**: Need to install pgp_common locally

### Mitigation
- **Documentation**: Clear migration guide
- **Testing**: Thorough testing at each phase
- **Monitoring**: Watch for errors after each deployment

## Success Criteria

- [ ] All 17 services migrated to use pgp_common
- [ ] No duplicate code in base functionality
- [ ] All tests passing
- [ ] No regressions in production
- [ ] Phase 2.5 (function renaming) completed in 1 file instead of 11
- [ ] Documentation updated
- [ ] Team trained on new architecture

## Timeline

- **Week 1**: Create pgp_common, migrate pilot service
- **Week 2-3**: Migrate remaining services
- **Week 3**: Function renaming (Phase 2.5)
- **Week 4**: Cleanup and documentation

**Total**: ~4 weeks for complete migration

## Next Steps

1. **Review this plan** with team
2. **Get approval** for architecture
3. **Start Phase 1**: Create pgp_common library
4. **Pilot migration**: PGP_ORCHESTRATOR_v1
5. **Iterate** based on lessons learned
