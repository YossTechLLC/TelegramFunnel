# PGP_COMMON Migration Tracker

## Overview
Tracking the migration of all 17 PGP_v1 services to use the PGP_COMMON shared library.

## Migration Checklist

### Core Services (12 services)
- [x] **PGP_ORCHESTRATOR_v1** (Pilot Service) ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (169 → 115 lines, saved 54)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (299 → 208 lines, saved 91)
  - [x] database_manager.py → BaseDatabaseManager (358 → 315 lines, saved 43)
  - [x] token_manager.py → BaseTokenManager (272 → 189 lines, saved 83)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~271 lines**

- [x] **PGP_INVITE_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (159 → 113 lines, saved 46)
  - [x] database_manager.py → BaseDatabaseManager (511 → 490 lines, saved 21)
  - [x] token_manager.py → BaseTokenManager (166 → 167 lines, +1 line)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~67 lines**

- [ ] **PGP_SPLIT1_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] token_manager.py → BaseTokenManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_SPLIT2_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_SPLIT3_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_HOSTPAY1_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] token_manager.py → BaseTokenManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_HOSTPAY2_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] token_manager.py → BaseTokenManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_HOSTPAY3_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_ACCUMULATOR_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_BATCHPROCESSOR_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] token_manager.py → BaseTokenManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_MICROBATCHPROCESSOR_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] database_manager.py → BaseDatabaseManager
  - [ ] Dockerfile → Add PGP_COMMON installation

- [ ] **PGP_NP_IPN_v1**
  - [ ] config_manager.py → BaseConfigManager
  - [ ] cloudtasks_client.py → BaseCloudTasksClient
  - [ ] Dockerfile → Add PGP_COMMON installation

### Supporting Services (5 services)
- [ ] **PGP_NP_WEBHOOK_v1**
- [ ] **PGP_SUBSCRIPTION_MONITOR_v1**
- [ ] **PGP_NOTIFICATION_SERVICE_v1**
- [ ] **PGP_MESSAGE_TRACKING_v1**
- [ ] **PGP_TG_BOT_v1**

## Migration Pattern

### 1. config_manager.py
```python
from PGP_COMMON.config import BaseConfigManager

class ConfigManager(BaseConfigManager):
    def __init__(self):
        super().__init__(service_name="PGP_SERVICE_NAME_v1")

    def initialize_config(self) -> dict:
        # Use base methods
        db_config = self.fetch_database_config()
        ct_config = self.fetch_cloud_tasks_config()

        # Service-specific secrets
        my_secret = self.fetch_secret("MY_SECRET", "Description")

        return {**db_config, **ct_config, 'my_secret': my_secret}
```

### 2. cloudtasks_client.py
```python
from PGP_COMMON.cloudtasks import BaseCloudTasksClient

class CloudTasksClient(BaseCloudTasksClient):
    def __init__(self, project_id: str, location: str, signing_key: str):
        super().__init__(
            project_id=project_id,
            location=location,
            signing_key=signing_key,
            service_name="PGP_SERVICE_NAME_v1"
        )

    # Service-specific enqueue methods
```

### 3. database_manager.py
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
            service_name="PGP_SERVICE_NAME_v1"
        )

    # Service-specific query methods
```

### 4. token_manager.py
```python
from PGP_COMMON.tokens import BaseTokenManager

class TokenManager(BaseTokenManager):
    def __init__(self, signing_key: str):
        super().__init__(
            signing_key=signing_key,
            service_name="PGP_SERVICE_NAME_v1"
        )

    # Service-specific token methods
```

### 5. Dockerfile
```dockerfile
# Install PGP_COMMON shared library
COPY PGP_COMMON/ /app/PGP_COMMON/
RUN pip install -e /app/PGP_COMMON
```

## Progress Summary

- **Completed**: 2/17 services (PGP_ORCHESTRATOR_v1, PGP_INVITE_v1)
- **In Progress**: 0/17 services
- **Pending**: 15/17 services
- **Total Code Reduction So Far**: ~338 lines

## Notes

- ✅ Pilot service (PGP_ORCHESTRATOR_v1) validated the architecture
- ✅ PGP_INVITE_v1 completed successfully
- Each migration reduces duplicate code by ~67-271 lines depending on service complexity
- Total expected code reduction: ~7,250 lines
