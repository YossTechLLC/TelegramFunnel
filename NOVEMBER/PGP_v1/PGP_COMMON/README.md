# PGP_COMMON - Shared Library for PGP_v1 Microservices

This package provides common base classes and utilities shared across all PGP_v1 microservices.

## Overview

PGP_COMMON eliminates code duplication by providing base classes for:
- **Configuration Management** (`BaseConfigManager`)
- **Cloud Tasks Operations** (`BaseCloudTasksClient`)
- **Database Operations** (`BaseDatabaseManager`)
- **Token Management** (`BaseTokenManager`)

## Installation

From within a PGP_v1 service directory:

```bash
# Install in development/editable mode
pip install -e ../PGP_COMMON
```

## Package Structure

```
PGP_COMMON/
├── __init__.py               # Package initialization
├── setup.py                  # Package configuration
├── README.md                 # This file
├── config/
│   ├── __init__.py
│   └── base_config.py        # BaseConfigManager
├── cloudtasks/
│   ├── __init__.py
│   └── base_client.py        # BaseCloudTasksClient
├── database/
│   ├── __init__.py
│   └── db_manager.py         # BaseDatabaseManager
├── tokens/
│   ├── __init__.py
│   └── base_token.py         # BaseTokenManager
└── utils/
    └── __init__.py           # Future utilities
```

## Usage

### BaseConfigManager

```python
from PGP_COMMON.config import BaseConfigManager

class ConfigManager(BaseConfigManager):
    def __init__(self):
        super().__init__(service_name="PGP_ORCHESTRATOR_v1")

    def initialize_config(self) -> dict:
        # Fetch common database config
        db_config = self.fetch_database_config()

        # Fetch common Cloud Tasks config
        ct_config = self.fetch_cloud_tasks_config()

        # Fetch service-specific secrets
        my_secret = self.fetch_secret("MY_SECRET_KEY", "My custom secret")

        return {**db_config, **ct_config, 'my_secret': my_secret}
```

### BaseCloudTasksClient

```python
from PGP_COMMON.cloudtasks import BaseCloudTasksClient

class CloudTasksClient(BaseCloudTasksClient):
    def __init__(self, project_id: str, location: str, signing_key: str):
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key=signing_key,
            service_name="PGP_ORCHESTRATOR_v1"
        )

    def enqueue_my_task(self, queue_name: str, target_url: str, data: dict):
        payload = {"data": data}
        return self.create_task(queue_name, target_url, payload)
```

### BaseDatabaseManager

```python
from PGP_COMMON.database import BaseDatabaseManager

class DatabaseManager(BaseDatabaseManager):
    def __init__(self, instance_connection_name: str, db_name: str,
                 db_user: str, db_password: str):
        super().__init__(
            instance_connection_name=instance_connection_name,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            service_name="PGP_ORCHESTRATOR_v1"
        )

    def my_custom_query(self, user_id: int):
        query = "SELECT * FROM users WHERE id = %s"
        return self.execute_query(query, (user_id,), fetch_one=True)
```

### BaseTokenManager

```python
from PGP_COMMON.tokens import BaseTokenManager

class TokenManager(BaseTokenManager):
    def __init__(self, signing_key: str):
        super().__init__(
            signing_key=signing_key,
            service_name="PGP_ORCHESTRATOR_v1"
        )

    def create_my_token(self, user_id: int, data: str) -> str:
        # Use common utilities
        packed_data = bytearray()
        packed_data.extend(self.pack_48bit_id(user_id))
        packed_data.extend(self.pack_string(data))

        # Add signature
        signature = self.generate_hmac_signature(bytes(packed_data))
        final_data = bytes(packed_data) + signature

        # Encode
        return self.encode_base64_urlsafe(final_data)
```

## Benefits

- **60% Code Reduction**: Eliminates ~7,250 lines of duplicate code
- **Single Source of Truth**: Update common methods in one place
- **Consistent Behavior**: All services use the same patterns
- **Easier Maintenance**: Bug fixes and improvements propagate to all services
- **Better Testing**: Test base classes once instead of 17 times

## Dependencies

- `google-cloud-secret-manager >= 2.16.0`
- `google-cloud-tasks >= 2.13.0`
- `cloud-sql-python-connector[pg8000] >= 1.4.0`
- `pg8000 >= 1.29.0`

## Version History

- **1.0.0** (2025-01-15): Initial release
  - BaseConfigManager with common fetch methods
  - BaseCloudTasksClient with create_task()
  - BaseDatabaseManager with connection management
  - BaseTokenManager with token utilities
