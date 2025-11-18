# Hot-Reload Implementation Checklist

**Objective**: Implement hot-reloadable secrets for 43 approved secrets across all 17 PGP_v1 services while ensuring 3 security-critical secrets remain static.

**Status**: 🔴 NOT STARTED
**Estimated Effort**: 2-4 hours
**Created**: 2025-11-18

---

## 📋 Secret Classification Reference

### ✅ Hot-Reloadable Secrets (43 total)

**API Keys (5)**:
- `CHANGENOW_API_KEY` - ChangeNow cryptocurrency exchange API
- `NOWPAYMENTS_API_KEY` - NowPayments payment processor API
- `ETHEREUM_RPC_URL_API` - Ethereum blockchain RPC endpoint
- `TELEGRAM_BOT_API_TOKEN` - Telegram bot authentication token
- `TELEGRAM_BOT_USERNAME` - Telegram bot username

**Service URLs (13)** - Critical for blue-green deployments:
- `PGP_ORCHESTRATOR_URL` - Payment orchestration service
- `PGP_SPLIT1_URL` - Split service 1 (estimate requests)
- `PGP_SPLIT2_URL` - Split service 2 (swap execution)
- `PGP_HOSTPAY1_URL` - HostPay orchestrator
- `PGP_HOSTPAY2_URL` - ChangeNow status checker
- `PGP_HOSTPAY3_URL` - ETH payment executor
- `PGP_INVITE_URL` - Invite link service
- `PGP_SERVER_URL` - Main API server
- `PGP_NOTIFICATION_URL` - Notification service
- `PGP_ACCUMULATOR_URL` - Payout accumulator
- `PGP_SCHEDULER_URL` - Broadcast scheduler
- `PGP_BROADCAST_URL` - Broadcast executor
- `PGP_BOTCOMMAND_URL` - Bot command handler

**Queue Names (15)** - Critical for infrastructure migration:
- `PGP_ORCHESTRATOR_QUEUE` - Orchestrator task queue
- `PGP_SPLIT1_ESTIMATE_QUEUE` - Split1 estimate queue
- `PGP_SPLIT1_RESPONSE_QUEUE` - Split1 response queue
- `PGP_SPLIT2_SWAP_QUEUE` - Split2 swap queue
- `PGP_SPLIT2_RESPONSE_QUEUE` - Split2 response queue
- `PGP_HOSTPAY_TRIGGER_QUEUE` - HostPay trigger queue
- `PGP_HOSTPAY2_QUEUE` - HostPay2 status queue
- `PGP_HOSTPAY3_QUEUE` - HostPay3 payment queue
- `PGP_HOSTPAY1_RESPONSE_QUEUE` - HostPay1 response queue
- `PGP_INVITE_QUEUE` - Invite task queue
- `PGP_NOTIFICATION_QUEUE` - Notification task queue
- `PGP_ACCUMULATOR_QUEUE` - Accumulator task queue
- `PGP_BATCHPROCESSOR_QUEUE` - Batch processor queue
- `PGP_SCHEDULER_QUEUE` - Scheduler task queue
- `PGP_BROADCAST_QUEUE` - Broadcast task queue

**Webhook/IPN Secrets (4)**:
- `NOWPAYMENTS_IPN_SECRET` - NowPayments webhook validation
- `SUCCESS_URL_SIGNING_KEY_SECONDARY` - Backup signing key
- `TPS_HOSTPAY_SIGNING_KEY_SECONDARY` - Backup HostPay signing key
- `CLOUDFLARE_WEBHOOK_SECRET` - Cloudflare webhook validation

**Application Config (6)**:
- `TP_FLAT_FEE` - Transaction flat fee amount
- `PGP_SUCCESS_URL` - Payment success redirect URL
- `PGP_FAILURE_URL` - Payment failure redirect URL
- `SERVICE_ENVIRONMENT` - Environment flag (prod/staging)
- `ALERTING_ENABLED` - Feature flag for alerting
- `LOG_LEVEL` - Logging verbosity level

### ❌ NEVER Hot-Reload (3 total) - Security Critical

**Private Keys**:
- `HOST_WALLET_PRIVATE_KEY` - Ethereum wallet private key (used by PGP_HOSTPAY3_v1)
- `SUCCESS_URL_SIGNING_KEY` - JWT signing key (used by PGP_ORCHESTRATOR_v1)
- `TPS_HOSTPAY_SIGNING_KEY` - HostPay HMAC signing key (used by PGP_SERVER_v1, PGP_HOSTPAY1_v1)

### ⚠️ Complex Case (8 total) - Keep Static for Now

**Database Credentials** (require connection pool restart):
- `DATABASE_PASSWORD_SECRET`
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`

**Infrastructure Config**:
- `CLOUD_TASKS_PROJECT_ID`
- `CLOUD_TASKS_LOCATION`
- `PGP_HOSTPAY_SIGNING_KEY_API` (used for request validation)
- `PAYMENT_PROCESSING_PAGE_URL`

---

## Phase 1: Infrastructure Foundation

### 1.1 Update BaseConfigManager (PGP_COMMON/config/base_config.py)

- [ ] **Add Secret Manager client initialization**
  - Add `from google.cloud import secretmanager` import
  - Add `self.secret_client = secretmanager.SecretManagerServiceClient()` in `__init__`
  - Verify project ID is available from environment

- [ ] **Add `fetch_secret_dynamic()` method**
  ```python
  def fetch_secret_dynamic(
      self,
      secret_path: str,
      description: str = "",
      cache_key: Optional[str] = None
  ) -> Optional[str]:
      """
      Fetch secret dynamically from Secret Manager (hot-reloadable).

      Args:
          secret_path: Full secret path (e.g., "projects/pgp-live/secrets/CHANGENOW_API_KEY/versions/latest")
          description: Human-readable description for logging
          cache_key: Optional request-level cache key

      Returns:
          Secret value or None if error
      """
  ```
  - Implement Secret Manager API call
  - Add error handling with retry logic
  - Add request-level caching (store in `g` Flask context)
  - Add logging for audit trail
  - Verify secrets are fetched from Secret Manager, not environment variables

- [ ] **Keep existing `fetch_secret()` method unchanged**
  - Verify it still uses `os.getenv()` for static secrets
  - Ensure database credentials, private keys use this method
  - Add docstring clarification: "Used for static secrets (private keys, database credentials)"

- [ ] **Add helper method `build_secret_path()`**
  ```python
  def build_secret_path(self, secret_name: str, version: str = "latest") -> str:
      """Build full secret path for Secret Manager."""
      project_id = os.getenv('CLOUD_TASKS_PROJECT_ID', 'pgp-live')
      return f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
  ```

- [ ] **Verification Steps**:
  - ✅ Secret Manager client initializes without errors
  - ✅ `fetch_secret_dynamic()` successfully fetches a test secret
  - ✅ `fetch_secret()` still works for environment variables
  - ✅ Caching prevents duplicate API calls within same request
  - ✅ Error logging includes secret name and error type

---

## Phase 2: Service-by-Service Implementation

### 2.1 PGP_SPLIT2_v1 (Pilot Service)

**Hot-Reloadable Secrets Used**:
- `CHANGENOW_API_KEY` ✅
- `PGP_SPLIT1_RESPONSE_QUEUE` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- `CLOUD_SQL_CONNECTION_NAME` ❌ (keep static)
- `DATABASE_NAME_SECRET` ❌ (keep static)
- `DATABASE_USER_SECRET` ❌ (keep static)
- `CLOUD_TASKS_PROJECT_ID` ❌ (keep static)
- `CLOUD_TASKS_LOCATION` ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_SPLIT2_v1/config_manager.py`**
  - [ ] Add `get_changenow_api_key()` dynamic method:
    ```python
    def get_changenow_api_key(self) -> Optional[str]:
        """Get ChangeNow API key (hot-reloadable)."""
        secret_path = self.build_secret_path("CHANGENOW_API_KEY")
        return self.fetch_secret_dynamic(
            secret_path,
            "ChangeNow API key",
            cache_key="changenow_api_key"
        )
    ```
  - [ ] Add `get_split1_response_queue()` dynamic method
  - [ ] Verify database credentials still use static `fetch_secret()`

- [ ] **Update `PGP_SPLIT2_v1/changenow_client.py`**
  - [ ] Replace `self.api_key` initialization with dynamic fetch:
    ```python
    # OLD: self.api_key = config.get('changenow_api_key')
    # NEW: self.api_key = config_manager.get_changenow_api_key()
    ```
  - [ ] Add error handling if key fetch fails
  - [ ] Update all API request methods to fetch key dynamically

- [ ] **Update `PGP_SPLIT2_v1/pgp_split2_v1.py`**
  - [ ] Pass `config_manager` reference to ChangeNowClient
  - [ ] Update queue task creation to fetch queue name dynamically

- [ ] **Verification Steps**:
  - ✅ Service starts successfully
  - ✅ ChangeNow API calls work with dynamically fetched key
  - ✅ Update CHANGENOW_API_KEY in Secret Manager → verify new key used within 1 request
  - ✅ Database connections still work (using static credentials)
  - ✅ No performance regression (request-level caching working)

---

### 2.2 PGP_SPLIT1_v1

**Hot-Reloadable Secrets Used**:
- `CHANGENOW_API_KEY` ✅
- `PGP_SPLIT2_SWAP_QUEUE` ✅
- `PGP_HOSTPAY_TRIGGER_QUEUE` ✅
- `PGP_ORCHESTRATOR_QUEUE` ✅ (for error responses)

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_SPLIT1_v1/config_manager.py`**
  - [ ] Add `get_changenow_api_key()` dynamic method
  - [ ] Add `get_split2_swap_queue()` dynamic method
  - [ ] Add `get_hostpay_trigger_queue()` dynamic method
  - [ ] Add `get_orchestrator_queue()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_SPLIT1_v1/changenow_client.py`**
  - [ ] Update to fetch API key dynamically per request

- [ ] **Update `PGP_SPLIT1_v1/pgp_split1_v1.py`**
  - [ ] Update queue task creation to use dynamic queue names
  - [ ] Pass config_manager to ChangeNowClient

- [ ] **Verification Steps**:
  - ✅ Estimate requests work with dynamic API key
  - ✅ Tasks enqueued to correct dynamic queue names
  - ✅ Database connections stable

---

### 2.3 PGP_ORCHESTRATOR_v1

**Hot-Reloadable Secrets Used**:
- `PGP_SPLIT1_URL` ✅
- `PGP_SPLIT1_ESTIMATE_QUEUE` ✅
- `PGP_SUCCESS_URL` ✅
- `PGP_FAILURE_URL` ✅
- `TP_FLAT_FEE` ✅

**Static Secrets Used**:
- `SUCCESS_URL_SIGNING_KEY` ❌ **NEVER HOT-RELOAD** (JWT signing key)
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_ORCHESTRATOR_v1/config_manager.py`**
  - [ ] Add `get_split1_url()` dynamic method
  - [ ] Add `get_split1_estimate_queue()` dynamic method
  - [ ] Add `get_success_url()` dynamic method
  - [ ] Add `get_failure_url()` dynamic method
  - [ ] Add `get_flat_fee()` dynamic method
  - [ ] **CRITICAL**: Verify `SUCCESS_URL_SIGNING_KEY` still uses static `fetch_secret()`
  - [ ] Add docstring warning on signing key: "NEVER make this hot-reloadable"

- [ ] **Update `PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py`**
  - [ ] Initialize TokenManager with STATIC signing key (no changes)
  - [ ] Update Split1 URL usage to dynamic fetch
  - [ ] Update queue task creation to use dynamic queue names
  - [ ] Update success/failure URLs to dynamic fetch
  - [ ] Update flat fee calculation to use dynamic value

- [ ] **Update `PGP_ORCHESTRATOR_v1/token_manager.py`**
  - [ ] **DO NOT MODIFY** - signing key must remain static
  - [ ] Add comment: "signing_key is intentionally static for security"

- [ ] **Verification Steps**:
  - ✅ JWT signing still works (static key unchanged)
  - ✅ Token validation works across requests
  - ✅ Split1 URL can be changed dynamically
  - ✅ Success/failure URLs update without restart
  - ✅ Flat fee changes take effect immediately
  - ✅ **CRITICAL**: Signing key never fetched from Secret Manager API

---

### 2.4 PGP_HOSTPAY1_v1

**Hot-Reloadable Secrets Used**:
- `PGP_HOSTPAY2_URL` ✅
- `PGP_HOSTPAY3_URL` ✅
- `PGP_HOSTPAY2_QUEUE` ✅
- `PGP_HOSTPAY3_QUEUE` ✅
- `PGP_HOSTPAY1_RESPONSE_QUEUE` ✅

**Static Secrets Used**:
- `TPS_HOSTPAY_SIGNING_KEY` ❌ **NEVER HOT-RELOAD** (HMAC signing key)
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_HOSTPAY1_v1/config_manager.py`**
  - [ ] Add `get_hostpay2_url()` dynamic method
  - [ ] Add `get_hostpay3_url()` dynamic method
  - [ ] Add `get_hostpay2_queue()` dynamic method
  - [ ] Add `get_hostpay3_queue()` dynamic method
  - [ ] Add `get_response_queue()` dynamic method
  - [ ] **CRITICAL**: Verify `TPS_HOSTPAY_SIGNING_KEY` remains static
  - [ ] Add docstring warning: "TPS_HOSTPAY_SIGNING_KEY NEVER hot-reloadable"

- [ ] **Update `PGP_HOSTPAY1_v1/pgp_hostpay1_v1.py`**
  - [ ] Update queue task creation to use dynamic queue names
  - [ ] Update service URL usage to dynamic fetch
  - [ ] **DO NOT MODIFY** signing key initialization

- [ ] **Verification Steps**:
  - ✅ HMAC signing works (static key unchanged)
  - ✅ Service URLs can be changed dynamically
  - ✅ Queue names update without restart
  - ✅ **CRITICAL**: Signing key never fetched from Secret Manager API

---

### 2.5 PGP_HOSTPAY2_v1

**Hot-Reloadable Secrets Used**:
- `CHANGENOW_API_KEY` ✅
- `PGP_HOSTPAY1_RESPONSE_QUEUE` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_HOSTPAY2_v1/config_manager.py`**
  - [ ] Add `get_changenow_api_key()` dynamic method
  - [ ] Add `get_response_queue()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_HOSTPAY2_v1/changenow_client.py`**
  - [ ] Update to fetch API key dynamically

- [ ] **Update `PGP_HOSTPAY2_v1/pgp_hostpay2_v1.py`**
  - [ ] Update queue task creation to use dynamic queue name
  - [ ] Pass config_manager to ChangeNowClient

- [ ] **Verification Steps**:
  - ✅ ChangeNow status checks work with dynamic API key
  - ✅ Response queue tasks enqueued correctly

---

### 2.6 PGP_HOSTPAY3_v1

**Hot-Reloadable Secrets Used**:
- `ETHEREUM_RPC_URL_API` ✅
- `PGP_HOSTPAY1_RESPONSE_QUEUE` ✅

**Static Secrets Used**:
- `HOST_WALLET_PRIVATE_KEY` ❌ **NEVER HOT-RELOAD** (ETH wallet private key)
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_HOSTPAY3_v1/config_manager.py`**
  - [ ] Add `get_ethereum_rpc_url()` dynamic method
  - [ ] Add `get_response_queue()` dynamic method
  - [ ] **CRITICAL**: Verify `HOST_WALLET_PRIVATE_KEY` remains static
  - [ ] Add docstring warning: "HOST_WALLET_PRIVATE_KEY NEVER hot-reloadable"

- [ ] **Update `PGP_HOSTPAY3_v1/wallet_manager.py`**
  - [ ] **DO NOT MODIFY** private key initialization (must remain static)
  - [ ] Add comment: "Private key intentionally static for transaction security"

- [ ] **Update `PGP_HOSTPAY3_v1/ethereum_client.py`**
  - [ ] Update RPC URL usage to dynamic fetch
  - [ ] Ensure RPC provider reconnection if URL changes

- [ ] **Update `PGP_HOSTPAY3_v1/pgp_hostpay3_v1.py`**
  - [ ] Update queue task creation to use dynamic queue name
  - [ ] **DO NOT MODIFY** wallet manager initialization

- [ ] **Verification Steps**:
  - ✅ ETH wallet signing works (static private key unchanged)
  - ✅ RPC URL can be changed dynamically
  - ✅ Response queue name updates without restart
  - ✅ **CRITICAL**: Private key never fetched from Secret Manager API
  - ✅ Mid-flight transactions not disrupted by RPC URL change

---

### 2.7 PGP_SERVER_v1

**Hot-Reloadable Secrets Used**:
- `PGP_ORCHESTRATOR_URL` ✅
- `PGP_INVITE_URL` ✅
- `PGP_ORCHESTRATOR_QUEUE` ✅
- `PGP_INVITE_QUEUE` ✅

**Static Secrets Used**:
- `TPS_HOSTPAY_SIGNING_KEY` ❌ **NEVER HOT-RELOAD** (used for HMAC validation)
- `PGP_HOSTPAY_SIGNING_KEY_API` ❌ (keep static for now - used for request validation)
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_SERVER_v1/config_manager.py`**
  - [ ] Add `get_orchestrator_url()` dynamic method
  - [ ] Add `get_invite_url()` dynamic method
  - [ ] Add `get_orchestrator_queue()` dynamic method
  - [ ] Add `get_invite_queue()` dynamic method
  - [ ] **CRITICAL**: Verify `TPS_HOSTPAY_SIGNING_KEY` remains static
  - [ ] Verify `PGP_HOSTPAY_SIGNING_KEY_API` remains static

- [ ] **Update `PGP_SERVER_v1/pgp_server_v1.py`**
  - [ ] Update service URL usage to dynamic fetch
  - [ ] Update queue task creation to use dynamic queue names
  - [ ] **DO NOT MODIFY** signing key initialization

- [ ] **Update security validators** (if exist)
  - [ ] **DO NOT MODIFY** HMAC validation logic (uses static key)

- [ ] **Verification Steps**:
  - ✅ HMAC validation works (static key unchanged)
  - ✅ Service URLs can be changed dynamically
  - ✅ Queue names update without restart

---

### 2.8 PGP_NOTIFICATION_v1

**Hot-Reloadable Secrets Used**:
- `TELEGRAM_BOT_API_TOKEN` ✅
- `TELEGRAM_BOT_USERNAME` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_NOTIFICATION_v1/config_manager.py`**
  - [ ] Add `get_telegram_bot_token()` dynamic method
  - [ ] Add `get_telegram_bot_username()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_NOTIFICATION_v1/telegram_client.py`**
  - [ ] Update bot initialization to fetch token dynamically
  - [ ] Handle bot reconnection if token changes

- [ ] **Update `PGP_NOTIFICATION_v1/pgp_notification_v1.py`**
  - [ ] Pass config_manager to TelegramClient
  - [ ] Ensure bot reconnects gracefully on token change

- [ ] **Verification Steps**:
  - ✅ Telegram bot works with dynamic token
  - ✅ Bot can be switched to backup token without restart
  - ✅ Bot username updates correctly

---

### 2.9 PGP_INVITE_v1

**Hot-Reloadable Secrets Used**:
- `TELEGRAM_BOT_API_TOKEN` ✅
- `TELEGRAM_BOT_USERNAME` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_INVITE_v1/config_manager.py`**
  - [ ] Add `get_telegram_bot_token()` dynamic method
  - [ ] Add `get_telegram_bot_username()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_INVITE_v1/telegram_client.py`**
  - [ ] Update bot initialization to fetch token dynamically

- [ ] **Update `PGP_INVITE_v1/pgp_invite_v1.py`**
  - [ ] Pass config_manager to TelegramClient

- [ ] **Verification Steps**:
  - ✅ Invite link generation works with dynamic bot token
  - ✅ Bot token changes take effect immediately

---

### 2.10 PGP_ACCUMULATOR_v1

**Hot-Reloadable Secrets Used**:
- `PGP_BATCHPROCESSOR_QUEUE` ✅
- `TP_FLAT_FEE` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_ACCUMULATOR_v1/config_manager.py`**
  - [ ] Add `get_batchprocessor_queue()` dynamic method
  - [ ] Add `get_flat_fee()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_ACCUMULATOR_v1/pgp_accumulator_v1.py`**
  - [ ] Update queue task creation to use dynamic queue name
  - [ ] Update flat fee calculation to use dynamic value

- [ ] **Verification Steps**:
  - ✅ Payout accumulation works with dynamic flat fee
  - ✅ Batch processor queue name updates without restart

---

### 2.11 PGP_BATCHPROCESSOR_v1

**Hot-Reloadable Secrets Used**:
- `ETHEREUM_RPC_URL_API` ✅
- `NOWPAYMENTS_API_KEY` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_BATCHPROCESSOR_v1/config_manager.py`**
  - [ ] Add `get_ethereum_rpc_url()` dynamic method
  - [ ] Add `get_nowpayments_api_key()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_BATCHPROCESSOR_v1/ethereum_client.py`**
  - [ ] Update RPC URL usage to dynamic fetch

- [ ] **Update `PGP_BATCHPROCESSOR_v1/nowpayments_client.py`**
  - [ ] Update API key usage to dynamic fetch

- [ ] **Update `PGP_BATCHPROCESSOR_v1/pgp_batchprocessor_v1.py`**
  - [ ] Pass config_manager to clients

- [ ] **Verification Steps**:
  - ✅ Batch payouts work with dynamic API key
  - ✅ RPC URL can be changed without restart

---

### 2.12 PGP_SCHEDULER_v1

**Hot-Reloadable Secrets Used**:
- `PGP_BROADCAST_QUEUE` ✅
- `TELEGRAM_BOT_API_TOKEN` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_SCHEDULER_v1/config_manager.py`**
  - [ ] Add `get_broadcast_queue()` dynamic method
  - [ ] Add `get_telegram_bot_token()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_SCHEDULER_v1/pgp_scheduler_v1.py`**
  - [ ] Update queue task creation to use dynamic queue name
  - [ ] Update Telegram bot usage to dynamic token

- [ ] **Verification Steps**:
  - ✅ Broadcast scheduling works with dynamic queue name
  - ✅ Bot token changes take effect immediately

---

### 2.13 PGP_BROADCAST_v1

**Hot-Reloadable Secrets Used**:
- `TELEGRAM_BOT_API_TOKEN` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_BROADCAST_v1/config_manager.py`**
  - [ ] Add `get_telegram_bot_token()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_BROADCAST_v1/telegram_client.py`**
  - [ ] Update bot initialization to fetch token dynamically

- [ ] **Update `PGP_BROADCAST_v1/pgp_broadcast_v1.py`**
  - [ ] Pass config_manager to TelegramClient

- [ ] **Verification Steps**:
  - ✅ Broadcast messages send with dynamic bot token
  - ✅ Bot token changes take effect immediately

---

### 2.14 PGP_BOTCOMMAND_v1

**Hot-Reloadable Secrets Used**:
- `TELEGRAM_BOT_API_TOKEN` ✅
- `PGP_ORCHESTRATOR_URL` ✅
- `PGP_ORCHESTRATOR_QUEUE` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_BOTCOMMAND_v1/config_manager.py`**
  - [ ] Add `get_telegram_bot_token()` dynamic method
  - [ ] Add `get_orchestrator_url()` dynamic method
  - [ ] Add `get_orchestrator_queue()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_BOTCOMMAND_v1/telegram_client.py`**
  - [ ] Update bot initialization to fetch token dynamically

- [ ] **Update `PGP_BOTCOMMAND_v1/pgp_botcommand_v1.py`**
  - [ ] Update service URL usage to dynamic fetch
  - [ ] Update queue task creation to use dynamic queue name
  - [ ] Pass config_manager to TelegramClient

- [ ] **Verification Steps**:
  - ✅ Bot commands work with dynamic token
  - ✅ Orchestrator URL updates without restart

---

### 2.15 PGP_NPWEBHOOK_v1

**Hot-Reloadable Secrets Used**:
- `NOWPAYMENTS_IPN_SECRET` ✅
- `PGP_ORCHESTRATOR_URL` ✅
- `PGP_ORCHESTRATOR_QUEUE` ✅
- `PGP_INVITE_URL` ✅
- `PGP_INVITE_QUEUE` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_NPWEBHOOK_v1/config_manager.py`**
  - [ ] Add `get_nowpayments_ipn_secret()` dynamic method
  - [ ] Add `get_orchestrator_url()` dynamic method
  - [ ] Add `get_orchestrator_queue()` dynamic method
  - [ ] Add `get_invite_url()` dynamic method
  - [ ] Add `get_invite_queue()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_NPWEBHOOK_v1/webhook_validator.py`**
  - [ ] Update IPN secret validation to use dynamic fetch
  - [ ] Handle secret rotation gracefully

- [ ] **Update `PGP_NPWEBHOOK_v1/pgp_npwebhook_v1.py`**
  - [ ] Update service URL usage to dynamic fetch
  - [ ] Update queue task creation to use dynamic queue names

- [ ] **Verification Steps**:
  - ✅ Webhook validation works with dynamic IPN secret
  - ✅ IPN secret rotation works without restart
  - ✅ Service URLs update without restart

---

### 2.16 PGP_CFWEBHOOK_v1 (if exists)

**Hot-Reloadable Secrets Used**:
- `CLOUDFLARE_WEBHOOK_SECRET` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_CFWEBHOOK_v1/config_manager.py`**
  - [ ] Add `get_cloudflare_webhook_secret()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_CFWEBHOOK_v1/webhook_validator.py`**
  - [ ] Update webhook secret validation to use dynamic fetch

- [ ] **Update `PGP_CFWEBHOOK_v1/pgp_cfwebhook_v1.py`**
  - [ ] Pass config_manager to validator

- [ ] **Verification Steps**:
  - ✅ Webhook validation works with dynamic secret
  - ✅ Secret rotation works without restart

---

### 2.17 PGP_TELEPAY_v1 (if exists - legacy bot)

**Hot-Reloadable Secrets Used**:
- `TELEGRAM_BOT_API_TOKEN` ✅
- `PGP_ORCHESTRATOR_URL` ✅

**Static Secrets Used**:
- `DATABASE_PASSWORD_SECRET` ❌ (keep static)
- Database connection secrets ❌ (keep static)

#### Implementation Tasks:
- [ ] **Update `PGP_TELEPAY_v1/config_manager.py`**
  - [ ] Add `get_telegram_bot_token()` dynamic method
  - [ ] Add `get_orchestrator_url()` dynamic method
  - [ ] Verify database credentials remain static

- [ ] **Update `PGP_TELEPAY_v1/telegram_client.py`**
  - [ ] Update bot initialization to fetch token dynamically

- [ ] **Update `PGP_TELEPAY_v1/pgp_telepay_v1.py`**
  - [ ] Update service URL usage to dynamic fetch
  - [ ] Pass config_manager to TelegramClient

- [ ] **Verification Steps**:
  - ✅ Bot works with dynamic token
  - ✅ Orchestrator URL updates without restart

---

## Phase 3: Security Verification

### 3.1 Static Secret Audit

- [ ] **Verify `HOST_WALLET_PRIVATE_KEY` remains static**
  - [ ] Search codebase for `HOST_WALLET_PRIVATE_KEY` usage
  - [ ] Confirm it ONLY uses `fetch_secret()` (static method)
  - [ ] Confirm it NEVER uses `fetch_secret_dynamic()`
  - [ ] Verify WalletManager initialization happens once at startup
  - [ ] Add unit test: `test_wallet_private_key_never_hot_reloaded()`

- [ ] **Verify `SUCCESS_URL_SIGNING_KEY` remains static**
  - [ ] Search codebase for `SUCCESS_URL_SIGNING_KEY` usage
  - [ ] Confirm it ONLY uses `fetch_secret()` (static method)
  - [ ] Confirm it NEVER uses `fetch_secret_dynamic()`
  - [ ] Verify TokenManager initialization happens once at startup
  - [ ] Add unit test: `test_jwt_signing_key_never_hot_reloaded()`

- [ ] **Verify `TPS_HOSTPAY_SIGNING_KEY` remains static**
  - [ ] Search codebase for `TPS_HOSTPAY_SIGNING_KEY` usage
  - [ ] Confirm it ONLY uses `fetch_secret()` (static method)
  - [ ] Confirm it NEVER uses `fetch_secret_dynamic()`
  - [ ] Verify HMAC validator initialization happens once at startup
  - [ ] Add unit test: `test_hmac_signing_key_never_hot_reloaded()`

- [ ] **Verify database credentials remain static**
  - [ ] Search codebase for `DATABASE_PASSWORD_SECRET` usage
  - [ ] Confirm it ONLY uses `fetch_secret()` (static method)
  - [ ] Confirm connection pool initialization happens once at startup
  - [ ] Add unit test: `test_database_credentials_never_hot_reloaded()`

### 3.2 Code Pattern Audit

- [ ] **Search for direct `os.getenv()` calls**
  - [ ] Run: `grep -r "os.getenv(" --include="*.py" PGP_* | grep -v "CLOUD_TASKS_PROJECT_ID\|CLOUD_TASKS_LOCATION"`
  - [ ] Verify all secret fetches go through BaseConfigManager
  - [ ] Replace any direct `os.getenv()` calls for secrets

- [ ] **Search for hardcoded secret values**
  - [ ] Run: `grep -r "sk-live-\|0x[a-fA-F0-9]\{64\}" --include="*.py" PGP_*`
  - [ ] Verify no hardcoded keys exist

- [ ] **Verify all dynamic methods use request-level caching**
  - [ ] Search for all `fetch_secret_dynamic()` calls
  - [ ] Confirm each has unique `cache_key` parameter
  - [ ] Add test: `test_request_level_caching_works()`

### 3.3 IAM Permissions Audit

- [ ] **Verify service accounts have Secret Manager access**
  - [ ] List all 17 service account emails
  - [ ] Confirm each has `roles/secretmanager.secretAccessor` role
  - [ ] Test Secret Manager API access from each service

- [ ] **Verify Secret Manager audit logging enabled**
  - [ ] Check Cloud Audit Logs for `secretmanager.googleapis.com`
  - [ ] Verify `DATA_READ` operations are logged
  - [ ] Set up alerting for excessive secret access (>1000/min per service)

---

## Phase 4: Testing Strategy

### 4.1 Unit Tests (per service)

- [ ] **Test dynamic secret fetching**
  - [ ] `test_fetch_secret_dynamic_success()` - Verify API call works
  - [ ] `test_fetch_secret_dynamic_error_handling()` - Verify error handling
  - [ ] `test_fetch_secret_dynamic_caching()` - Verify request-level caching
  - [ ] `test_fetch_secret_dynamic_cache_key_uniqueness()` - Verify unique cache keys

- [ ] **Test static secret isolation**
  - [ ] `test_private_key_never_dynamic()` - Verify private key uses static method
  - [ ] `test_signing_key_never_dynamic()` - Verify signing key uses static method
  - [ ] `test_database_credentials_never_dynamic()` - Verify DB creds use static method

- [ ] **Test config manager methods**
  - [ ] `test_get_api_key_dynamic()` - Verify API key hot-reload works
  - [ ] `test_get_service_url_dynamic()` - Verify service URL hot-reload works
  - [ ] `test_get_queue_name_dynamic()` - Verify queue name hot-reload works

### 4.2 Integration Tests (per service)

- [ ] **Test hot-reload during request**
  - [ ] Start service with API key A
  - [ ] Make request → verify API key A used
  - [ ] Update Secret Manager with API key B
  - [ ] Make new request → verify API key B used (within 1 request)
  - [ ] Verify no service restart occurred

- [ ] **Test static secrets remain unchanged**
  - [ ] Update `HOST_WALLET_PRIVATE_KEY` in Secret Manager
  - [ ] Make request → verify OLD key still used
  - [ ] Restart service → verify NEW key now used

- [ ] **Test performance**
  - [ ] Make 100 requests → measure average latency
  - [ ] Verify request-level caching prevents excessive Secret Manager API calls
  - [ ] Verify latency increase <5ms (negligible)

### 4.3 End-to-End Tests

- [ ] **Test PGP_SPLIT2_v1 ChangeNow API key rotation**
  - [ ] Create donation payment with key A
  - [ ] Rotate to key B in Secret Manager
  - [ ] Create another donation payment → verify key B used
  - [ ] Verify first payment still completes successfully

- [ ] **Test service URL blue-green deployment**
  - [ ] Deploy new version of PGP_SPLIT1_v1 to URL B
  - [ ] Update `PGP_SPLIT1_URL` in Secret Manager from URL A to URL B
  - [ ] Verify PGP_ORCHESTRATOR_v1 starts routing to URL B
  - [ ] Verify no 404 errors or failed requests

- [ ] **Test queue name migration**
  - [ ] Create new queue `pgp-orchestrator-queue-v2`
  - [ ] Update `PGP_ORCHESTRATOR_QUEUE` in Secret Manager
  - [ ] Verify tasks enqueued to new queue
  - [ ] Drain old queue → delete old queue

### 4.4 Disaster Recovery Tests

- [ ] **Test Secret Manager API outage**
  - [ ] Simulate Secret Manager API failure (mock client)
  - [ ] Verify service continues using cached values
  - [ ] Verify error logging includes retry information
  - [ ] Verify graceful degradation (use fallback/default values)

- [ ] **Test invalid secret rotation**
  - [ ] Rotate API key to invalid value
  - [ ] Verify service logs error but continues operating
  - [ ] Verify automatic rollback to previous version (if configured)

- [ ] **Test concurrent secret updates**
  - [ ] Update multiple secrets simultaneously
  - [ ] Verify no race conditions or deadlocks
  - [ ] Verify all secrets update correctly

---

## Phase 5: Deployment & Rollout

### 5.1 Pre-Deployment Checklist

- [ ] **Code Review**
  - [ ] All 17 services updated and tested locally
  - [ ] Security audit completed (Phase 3)
  - [ ] Unit tests pass for all services (Phase 4.1)
  - [ ] Integration tests pass for all services (Phase 4.2)

- [ ] **Documentation**
  - [ ] Update `/THINK/SECRET_HOT_RELOAD_ANALYSIS.md` with implementation details
  - [ ] Update `NAMING_SCHEME.md` with hot-reloadable vs static secret classification
  - [ ] Update `SECRET_SCHEME.md` with new dynamic fetch methods
  - [ ] Create operational runbook: `RUNBOOKS/HOT_RELOAD_SECRET_ROTATION.md`

- [ ] **Monitoring Setup**
  - [ ] Create Cloud Monitoring dashboard for Secret Manager API calls
  - [ ] Set up alerting for excessive secret access (>1000/min per service)
  - [ ] Set up alerting for Secret Manager API errors (>10/min)
  - [ ] Create Cloud Logging filter for hot-reload audit trail

### 5.2 Staged Rollout Plan

**Week 1: Pilot (PGP_SPLIT2_v1)**
- [ ] Deploy PGP_SPLIT2_v1 with hot-reload to staging
- [ ] Run integration tests (Phase 4.2)
- [ ] Monitor Secret Manager API usage for 24 hours
- [ ] Perform live ChangeNow API key rotation test
- [ ] Deploy to production if successful
- [ ] Monitor production for 48 hours before proceeding

**Week 2: Core Payment Services (5 services)**
- [ ] Deploy PGP_ORCHESTRATOR_v1 with hot-reload
- [ ] Deploy PGP_SPLIT1_v1 with hot-reload
- [ ] Deploy PGP_HOSTPAY1_v1 with hot-reload
- [ ] Deploy PGP_HOSTPAY2_v1 with hot-reload
- [ ] Deploy PGP_HOSTPAY3_v1 with hot-reload
- [ ] Run end-to-end payment flow tests (Phase 4.3)
- [ ] Monitor production for 48 hours before proceeding

**Week 3: Webhook & Bot Services (5 services)**
- [ ] Deploy PGP_NPWEBHOOK_v1 with hot-reload
- [ ] Deploy PGP_SERVER_v1 with hot-reload
- [ ] Deploy PGP_NOTIFICATION_v1 with hot-reload
- [ ] Deploy PGP_INVITE_v1 with hot-reload
- [ ] Deploy PGP_BOTCOMMAND_v1 with hot-reload
- [ ] Test Telegram bot token rotation
- [ ] Test webhook IPN secret rotation
- [ ] Monitor production for 48 hours before proceeding

**Week 4: Remaining Services (7 services)**
- [ ] Deploy PGP_ACCUMULATOR_v1 with hot-reload
- [ ] Deploy PGP_BATCHPROCESSOR_v1 with hot-reload
- [ ] Deploy PGP_SCHEDULER_v1 with hot-reload
- [ ] Deploy PGP_BROADCAST_v1 with hot-reload
- [ ] Deploy PGP_CFWEBHOOK_v1 with hot-reload (if exists)
- [ ] Deploy PGP_TELEPAY_v1 with hot-reload (if exists)
- [ ] Monitor production for 48 hours

**Week 5: Validation & Documentation**
- [ ] Perform full system test of all hot-reloadable secrets
- [ ] Update operational documentation
- [ ] Train operations team on secret rotation procedures
- [ ] Create automated secret rotation scripts
- [ ] Schedule first production secret rotation (API keys)

### 5.3 Rollback Plan

- [ ] **If critical issue detected**:
  - [ ] Identify affected service(s)
  - [ ] Revert to previous container image (no hot-reload)
  - [ ] Verify static secret loading works
  - [ ] Investigate root cause
  - [ ] Fix issue and re-test before re-deploying

- [ ] **Rollback triggers**:
  - [ ] Service crashes after hot-reload deployment
  - [ ] >5% increase in error rate
  - [ ] Secret Manager API call rate >10x expected
  - [ ] Static secrets (private keys) fetched dynamically
  - [ ] Payment failures increase >10%

---

## Phase 6: Post-Deployment Verification

### 6.1 Production Smoke Tests

- [ ] **Test API key rotation (PGP_SPLIT2_v1)**
  - [ ] Rotate CHANGENOW_API_KEY in production
  - [ ] Create test donation payment
  - [ ] Verify new key used
  - [ ] Verify no errors in logs
  - [ ] Rollback to original key

- [ ] **Test service URL update (PGP_ORCHESTRATOR_v1)**
  - [ ] Deploy canary version of PGP_SPLIT1_v1 to new URL
  - [ ] Update PGP_SPLIT1_URL to canary URL
  - [ ] Route 10% of traffic to canary
  - [ ] Verify traffic reaches canary
  - [ ] Rollback URL to stable version

- [ ] **Test queue name update (PGP_HOSTPAY1_v1)**
  - [ ] Create new queue `pgp-hostpay2-queue-v1-canary`
  - [ ] Update PGP_HOSTPAY2_QUEUE to canary queue
  - [ ] Verify tasks enqueued to canary queue
  - [ ] Process tasks from canary queue
  - [ ] Rollback to original queue name

### 6.2 Performance Validation

- [ ] **Verify latency impact**
  - [ ] Measure p50, p95, p99 latency for all 17 services
  - [ ] Compare to baseline (before hot-reload)
  - [ ] Verify <5ms increase (negligible)
  - [ ] Investigate if >10ms increase

- [ ] **Verify Secret Manager API usage**
  - [ ] Check Cloud Monitoring dashboard
  - [ ] Verify API calls match expected rate (~500k/month total)
  - [ ] Verify request-level caching working (not 1 call per request)
  - [ ] Verify no excessive calls (>1000/min per service)

- [ ] **Verify cost impact**
  - [ ] Check billing for Secret Manager usage
  - [ ] Verify increase matches estimate (~$7.50/month)
  - [ ] Verify no unexpected costs

### 6.3 Security Validation

- [ ] **Verify static secrets never fetched dynamically**
  - [ ] Check Cloud Audit Logs for `HOST_WALLET_PRIVATE_KEY` access
  - [ ] Verify ONLY accessed at container startup (not during requests)
  - [ ] Verify `SUCCESS_URL_SIGNING_KEY` ONLY accessed at startup
  - [ ] Verify `TPS_HOSTPAY_SIGNING_KEY` ONLY accessed at startup

- [ ] **Verify audit logging working**
  - [ ] Check Cloud Audit Logs for secret access events
  - [ ] Verify service account email logged
  - [ ] Verify secret name logged
  - [ ] Verify timestamp logged
  - [ ] Create sample audit report

- [ ] **Verify IAM permissions correct**
  - [ ] No service account has excessive permissions
  - [ ] All service accounts have minimum required access
  - [ ] No service accounts have `roles/secretmanager.admin`

---

## Phase 7: Operational Runbook Creation

### 7.1 Secret Rotation Procedures

- [ ] **Create `RUNBOOKS/HOT_RELOAD_SECRET_ROTATION.md`**
  - [ ] Document step-by-step procedure for each secret type
  - [ ] Include rollback procedures
  - [ ] Include verification steps
  - [ ] Include troubleshooting guide

- [ ] **API Key Rotation Procedure**
  - [ ] How to rotate CHANGENOW_API_KEY
  - [ ] How to rotate NOWPAYMENTS_API_KEY
  - [ ] How to rotate ETHEREUM_RPC_URL_API
  - [ ] How to rotate TELEGRAM_BOT_API_TOKEN
  - [ ] Verification: Test API call succeeds with new key

- [ ] **Service URL Update Procedure**
  - [ ] Blue-green deployment workflow
  - [ ] Canary deployment workflow
  - [ ] Traffic splitting strategy
  - [ ] Rollback procedure
  - [ ] Verification: Check Cloud Logging for new service URL in logs

- [ ] **Queue Name Migration Procedure**
  - [ ] Create new queue
  - [ ] Update secret to new queue name
  - [ ] Drain old queue
  - [ ] Delete old queue
  - [ ] Verification: Check Cloud Tasks console for task routing

### 7.2 Troubleshooting Guide

- [ ] **Problem: Secret Manager API call fails**
  - [ ] Check service account IAM permissions
  - [ ] Check Secret Manager API quota limits
  - [ ] Check Cloud Logging for error details
  - [ ] Restart service as temporary fix (falls back to env vars)

- [ ] **Problem: New secret value not taking effect**
  - [ ] Verify secret updated in Secret Manager (check version number)
  - [ ] Verify secret path correct in config_manager
  - [ ] Verify request-level cache cleared (make new request)
  - [ ] Check Cloud Logging for "🔄 [CONFIG] Hot-reloaded" message

- [ ] **Problem: Static secret accidentally made dynamic**
  - [ ] **IMMEDIATE ROLLBACK**: Revert code change
  - [ ] **SECURITY INCIDENT**: Notify security team
  - [ ] **INVESTIGATION**: Check if private key leaked in logs
  - [ ] **REMEDIATION**: Rotate affected secret immediately

- [ ] **Problem: Service crashes after hot-reload deployment**
  - [ ] Check Cloud Logging for error stack trace
  - [ ] Verify Secret Manager client initialized correctly
  - [ ] Verify IAM permissions correct
  - [ ] Rollback to previous container image

### 7.3 Monitoring & Alerting Setup

- [ ] **Create Cloud Monitoring Dashboard**
  - [ ] Panel: Secret Manager API calls per service (time series)
  - [ ] Panel: Secret Manager API errors per service (time series)
  - [ ] Panel: Secret Manager API latency (p50, p95, p99)
  - [ ] Panel: Hot-reload events (count by secret name)

- [ ] **Create Alerting Policies**
  - [ ] Alert: Secret Manager API calls >1000/min for single service
  - [ ] Alert: Secret Manager API errors >10/min for single service
  - [ ] Alert: Secret Manager API latency p95 >200ms
  - [ ] Alert: Static secret accessed during request (CRITICAL)

- [ ] **Create Cloud Logging Filters**
  - [ ] Filter: "🔄 [CONFIG] Hot-reloaded" (hot-reload events)
  - [ ] Filter: "❌ [CONFIG] Error fetching" (secret fetch errors)
  - [ ] Filter: "HOST_WALLET_PRIVATE_KEY\|SUCCESS_URL_SIGNING_KEY\|TPS_HOSTPAY_SIGNING_KEY" (static secret access - SHOULD BE EMPTY)

---

## Final Verification Checklist

### ✅ All 43 Hot-Reloadable Secrets Implemented

**API Keys (5)**:
- [ ] CHANGENOW_API_KEY - Verified in PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_HOSTPAY2_v1
- [ ] NOWPAYMENTS_API_KEY - Verified in PGP_BATCHPROCESSOR_v1
- [ ] ETHEREUM_RPC_URL_API - Verified in PGP_HOSTPAY3_v1, PGP_BATCHPROCESSOR_v1
- [ ] TELEGRAM_BOT_API_TOKEN - Verified in all bot/notification services (7 services)
- [ ] TELEGRAM_BOT_USERNAME - Verified in all bot/notification services (7 services)

**Service URLs (13)**:
- [ ] PGP_ORCHESTRATOR_URL - Verified in PGP_SERVER_v1, PGP_NPWEBHOOK_v1, PGP_BOTCOMMAND_v1, PGP_TELEPAY_v1
- [ ] PGP_SPLIT1_URL - Verified in PGP_ORCHESTRATOR_v1
- [ ] PGP_SPLIT2_URL - Verified in PGP_SPLIT1_v1
- [ ] PGP_HOSTPAY1_URL - Verified in PGP_SPLIT1_v1
- [ ] PGP_HOSTPAY2_URL - Verified in PGP_HOSTPAY1_v1
- [ ] PGP_HOSTPAY3_URL - Verified in PGP_HOSTPAY1_v1
- [ ] PGP_INVITE_URL - Verified in PGP_SERVER_v1, PGP_NPWEBHOOK_v1
- [ ] PGP_SERVER_URL - (Used externally, not verified in services)
- [ ] PGP_NOTIFICATION_URL - Verified in services that trigger notifications
- [ ] PGP_ACCUMULATOR_URL - Verified in services that trigger accumulation
- [ ] PGP_SCHEDULER_URL - (Used externally, not verified in services)
- [ ] PGP_BROADCAST_URL - (Used by scheduler, verified in PGP_SCHEDULER_v1)
- [ ] PGP_BOTCOMMAND_URL - (Used externally, not verified in services)

**Queue Names (15)**:
- [ ] PGP_ORCHESTRATOR_QUEUE - Verified in 3 services
- [ ] PGP_SPLIT1_ESTIMATE_QUEUE - Verified in PGP_ORCHESTRATOR_v1
- [ ] PGP_SPLIT1_RESPONSE_QUEUE - Verified in PGP_SPLIT2_v1
- [ ] PGP_SPLIT2_SWAP_QUEUE - Verified in PGP_SPLIT1_v1
- [ ] PGP_SPLIT2_RESPONSE_QUEUE - Verified in PGP_SPLIT1_v1
- [ ] PGP_HOSTPAY_TRIGGER_QUEUE - Verified in PGP_SPLIT1_v1
- [ ] PGP_HOSTPAY2_QUEUE - Verified in PGP_HOSTPAY1_v1
- [ ] PGP_HOSTPAY3_QUEUE - Verified in PGP_HOSTPAY1_v1
- [ ] PGP_HOSTPAY1_RESPONSE_QUEUE - Verified in PGP_HOSTPAY2_v1, PGP_HOSTPAY3_v1
- [ ] PGP_INVITE_QUEUE - Verified in PGP_SERVER_v1, PGP_NPWEBHOOK_v1
- [ ] PGP_NOTIFICATION_QUEUE - Verified in services that trigger notifications
- [ ] PGP_ACCUMULATOR_QUEUE - Verified in services that trigger accumulation
- [ ] PGP_BATCHPROCESSOR_QUEUE - Verified in PGP_ACCUMULATOR_v1
- [ ] PGP_SCHEDULER_QUEUE - Verified in services that trigger scheduling
- [ ] PGP_BROADCAST_QUEUE - Verified in PGP_SCHEDULER_v1

**Webhook/IPN Secrets (4)**:
- [ ] NOWPAYMENTS_IPN_SECRET - Verified in PGP_NPWEBHOOK_v1
- [ ] SUCCESS_URL_SIGNING_KEY_SECONDARY - Verified as hot-reloadable backup key
- [ ] TPS_HOSTPAY_SIGNING_KEY_SECONDARY - Verified as hot-reloadable backup key
- [ ] CLOUDFLARE_WEBHOOK_SECRET - Verified in PGP_CFWEBHOOK_v1

**Application Config (6)**:
- [ ] TP_FLAT_FEE - Verified in PGP_ORCHESTRATOR_v1, PGP_ACCUMULATOR_v1
- [ ] PGP_SUCCESS_URL - Verified in PGP_ORCHESTRATOR_v1
- [ ] PGP_FAILURE_URL - Verified in PGP_ORCHESTRATOR_v1
- [ ] SERVICE_ENVIRONMENT - Verified in all services with environment-specific logic
- [ ] ALERTING_ENABLED - Verified in all services with alerting
- [ ] LOG_LEVEL - Verified in all services

### ❌ 3 Static Secrets Verified

- [ ] **HOST_WALLET_PRIVATE_KEY** - NEVER hot-reloaded (verified in PGP_HOSTPAY3_v1)
- [ ] **SUCCESS_URL_SIGNING_KEY** - NEVER hot-reloaded (verified in PGP_ORCHESTRATOR_v1)
- [ ] **TPS_HOSTPAY_SIGNING_KEY** - NEVER hot-reloaded (verified in PGP_SERVER_v1, PGP_HOSTPAY1_v1)

### 📊 Implementation Complete

- [ ] All 17 services deployed with hot-reload functionality
- [ ] All 43 hot-reloadable secrets tested in production
- [ ] All 3 static secrets verified to remain static
- [ ] Operational runbooks created and tested
- [ ] Monitoring dashboards deployed
- [ ] Alerting policies active
- [ ] Team trained on secret rotation procedures

---

## Success Criteria

**✅ Implementation Complete When**:
1. All 43 secrets can be rotated without service restart (verified in production)
2. All 3 static secrets remain static (verified via audit logs)
3. No performance degradation (latency increase <5ms)
4. No cost overrun (Secret Manager costs ~$7.50/month increase)
5. All operational runbooks created and tested
6. Monitoring and alerting deployed and functional
7. Team trained and comfortable with secret rotation procedures

**✅ Per-Service Complete When**:
1. Config manager updated with dynamic fetch methods
2. Application code updated to use dynamic methods
3. Unit tests pass (4 tests minimum)
4. Integration tests pass (3 tests minimum)
5. Deployed to staging and tested
6. Deployed to production and monitored for 48 hours
7. No errors or performance issues detected

---

## Notes & Reminders

- **ALWAYS verify static secrets remain static** - Check audit logs for `HOST_WALLET_PRIVATE_KEY`, `SUCCESS_URL_SIGNING_KEY`, `TPS_HOSTPAY_SIGNING_KEY` access during requests (should be empty)
- **Request-level caching is critical** - Without it, every API call triggers Secret Manager fetch (expensive and slow)
- **Test rollback procedures** - Practice rolling back a hot-reload deployment before production rollout
- **Monitor Secret Manager quota** - Default limit is 500k accesses/month per project, request increase if needed
- **Audit logging is your friend** - Use Cloud Audit Logs to verify hot-reload behavior and detect issues
- **Blue-green deployments are the killer feature** - Service URL hot-reload enables zero-downtime deployments
- **Start small, scale up** - Pilot with PGP_SPLIT2_v1 before rolling out to all 17 services
- **Document everything** - Operational runbooks are critical for team adoption and incident response

---

**End of Checklist**
