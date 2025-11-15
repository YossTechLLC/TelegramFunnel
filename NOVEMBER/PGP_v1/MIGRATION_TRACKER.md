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

- [x] **PGP_SPLIT1_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (207 → 126 lines, saved 81)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (265 → 200 lines, saved 65)
  - [x] database_manager.py → BaseDatabaseManager (403 → 393 lines, saved 10)
  - [x] token_manager.py → BaseTokenManager (889 → 854 lines, saved 35)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~191 lines**

- [x] **PGP_SPLIT2_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (183 → 101 lines, saved 82)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (265 → 200 lines, saved 65)
  - [x] database_manager.py → BaseDatabaseManager (220 → 184 lines, saved 36)
  - [x] token_manager.py → BaseTokenManager (740 → 705 lines, saved 35)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~218 lines**

- [x] **PGP_SPLIT3_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (141 → 83 lines, saved 58)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (299 → 234 lines, saved 65)
  - [x] token_manager.py → BaseTokenManager (842 → 833 lines, saved 9)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~132 lines**

- [x] **PGP_HOSTPAY1_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (203 → 145 lines, saved 58)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (255 → 198 lines, saved 57)
  - [x] database_manager.py → BaseDatabaseManager (393 → 344 lines, saved 49)
  - [x] token_manager.py → BaseTokenManager (1263 → 1226 lines, saved 37)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~201 lines**

- [x] **PGP_HOSTPAY2_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (122 → 87 lines, saved 35)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (215 → 160 lines, saved 55)
  - [x] token_manager.py → BaseTokenManager (783 → 743 lines, saved 40)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~130 lines**

- [x] **PGP_HOSTPAY3_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (228 → 168 lines, saved 60)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (261 → 199 lines, saved 62)
  - [x] database_manager.py → BaseDatabaseManager (792 → 744 lines, saved 48)
  - [x] token_manager.py → BaseTokenManager (938 → 898 lines, saved 40)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~210 lines**

- [x] **PGP_ACCUMULATOR_v1** ✅ COMPLETE
  - [x] config_manager.py → BaseConfigManager (191 → 134 lines, saved 57)
  - [x] cloudtasks_client.py → BaseCloudTasksClient (166 → 134 lines, saved 32)
  - [x] database_manager.py → BaseDatabaseManager (389 → 370 lines, saved 19)
  - [x] token_manager.py → BaseTokenManager (458 → 460 lines, +2 lines)
  - [x] Dockerfile → Add PGP_COMMON installation
  - **Total: Saved ~106 lines**

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

- **Completed**: 9/17 services (PGP_ORCHESTRATOR_v1, PGP_INVITE_v1, PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_SPLIT3_v1, PGP_HOSTPAY1_v1, PGP_HOSTPAY2_v1, PGP_HOSTPAY3_v1, PGP_ACCUMULATOR_v1)
- **In Progress**: 0/17 services
- **Pending**: 8/17 services
- **Total Code Reduction So Far**: ~1,526 lines

## Notes

- ✅ Pilot service (PGP_ORCHESTRATOR_v1) validated the architecture
- ✅ PGP_INVITE_v1 completed successfully
- ✅ PGP_SPLIT1_v1 completed successfully (largest token manager migration)
- ✅ PGP_SPLIT2_v1 completed successfully (USDT→ETH estimator service)
- ✅ PGP_SPLIT3_v1 completed successfully (ETH→ClientCurrency swapper service)
- ✅ PGP_HOSTPAY1_v1 completed successfully (Validator & Orchestrator service)
- ✅ PGP_HOSTPAY2_v1 completed successfully (ChangeNow Status Checker service)
- ✅ PGP_HOSTPAY3_v1 completed successfully (ETH Payment Executor service)
- ✅ PGP_ACCUMULATOR_v1 completed successfully (Payment Accumulation service)
- Each migration reduces duplicate code by ~67-271 lines depending on service complexity
- Total expected code reduction: ~7,250 lines
