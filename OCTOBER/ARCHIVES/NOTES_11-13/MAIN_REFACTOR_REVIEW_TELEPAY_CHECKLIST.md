# TelePay Architectural Refactoring - Implementation Checklist
## Critical Issues Resolution & Modular Code Implementation

**Document Version:** 1.0
**Date:** 2025-11-13
**Based on:** MAIN_REFACTOR_REVIEW_TELEPAY.md
**Purpose:** Actionable checklist for fixing critical architectural issues

---

## 🎯 Checklist Overview

**Total Tasks:** 68
**Priority 1 (Critical):** 24 tasks
**Priority 2 (High):** 22 tasks
**Priority 3 (Medium-Low):** 22 tasks

---

## ⚠️ PRIORITY 1: CRITICAL ISSUES (MUST FIX BEFORE PRODUCTION)

### 🚨 ISSUE #1: Document Complete Payment Workflow
**Goal:** Create complete end-to-end payment workflow documentation including all webhook services

#### Step 1.1: Investigate Missing Webhook Services
- [ ] **1.1.1** Use gcloud to list all Cloud Run services with "webhook" in name
  ```bash
  gcloud run services list --filter="name~webhook OR name~hostpay OR name~split" --format="table(name,status.url,status.conditions.status)"
  ```
- [ ] **1.1.2** Check Cloud Logging for np-webhook-10-26 invocations in past 7 days
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26" --limit=50 --format=json
  ```
- [ ] **1.1.3** Check Cloud Logging for gcwebhook1-10-26 invocations
- [ ] **1.1.4** Check Cloud Logging for gcwebhook2-10-26 invocations
- [ ] **1.1.5** Check Cloud Logging for gcsplit1-10-26 invocations
- [ ] **1.1.6** Check Cloud Logging for gchostpay1-10-26 invocations

#### Step 1.2: Read Webhook Service Source Code
- [ ] **1.2.1** Search for np-webhook-10-26 source code directory
  ```bash
  find /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel -type d -name "*webhook*" 2>/dev/null
  ```
- [ ] **1.2.2** Read np-webhook-10-26/service.py (main Flask app)
- [ ] **1.2.3** Read np-webhook-10-26 webhook handler code
- [ ] **1.2.4** Document NowPayments IPN callback payload structure
- [ ] **1.2.5** Document which services np-webhook calls (e.g., GCNotificationService)
- [ ] **1.2.6** Repeat for gcwebhook1-10-26, gcwebhook2-10-26, gcsplit1-10-26, gchostpay1-10-26

#### Step 1.3: Create PAYMENT_WORKFLOW_COMPLETE.md
- [ ] **1.3.1** Create file: `OCTOBER/10-26/PAYMENT_WORKFLOW_COMPLETE.md`
- [ ] **1.3.2** Document flow: User clicks /start token → GCBotCommand
- [ ] **1.3.3** Document flow: GCBotCommand → GCPaymentGateway /create-invoice
- [ ] **1.3.4** Document flow: GCPaymentGateway → NowPayments API (create invoice)
- [ ] **1.3.5** Document flow: User pays → NowPayments → np-webhook-10-26 IPN callback
- [ ] **1.3.6** Document flow: np-webhook-10-26 → GCNotificationService /send-notification
- [ ] **1.3.7** Document flow: GCNotificationService → Telegram (send message to channel owner)
- [ ] **1.3.8** Document flow: Service that invites user to channel (identify which service)
- [ ] **1.3.9** Document flow: Service that triggers payout (identify which service)
- [ ] **1.3.10** Create Mermaid sequence diagram showing complete flow
- [ ] **1.3.11** Document data passed at each step (request/response bodies)
- [ ] **1.3.12** Document error scenarios at each step

**Verification Criteria:**
- [ ] All 6 services + 5 webhook services documented
- [ ] Complete flow from payment → fulfillment → payout traced
- [ ] No gaps or "???" in the flow diagram

---

### 🚨 ISSUE #2: Clarify Donation Flow Integration
**Goal:** Document explicit HTTP call chain between GCBotCommand and GCDonationHandler

#### Step 2.1: Analyze GCBotCommand Donation Handling
- [ ] **2.1.1** Read GCBotCommand-10-26/handlers/command_handler.py
- [ ] **2.1.2** Search for donation token parsing logic (`{hash}_DONATE`)
- [ ] **2.1.3** Identify HTTP call to GCDonationHandler (if exists)
- [ ] **2.1.4** Document when GCBotCommand calls `/start-donation-input`
- [ ] **2.1.5** Document request payload structure for `/start-donation-input`

#### Step 2.2: Analyze GCBotCommand Callback Routing
- [ ] **2.2.1** Read GCBotCommand-10-26/handlers/callback_handler.py
- [ ] **2.2.2** Search for keypad callback patterns: `donate_digit_*`, `donate_backspace`, `donate_confirm`
- [ ] **2.2.3** Identify HTTP call to GCDonationHandler `/keypad-input`
- [ ] **2.2.4** Document request payload structure for `/keypad-input`
- [ ] **2.2.5** Verify GCBotCommand is the ONLY service receiving Telegram webhooks for donation keypads

#### Step 2.3: Update Architecture Documentation
- [ ] **2.3.1** Add explicit HTTP call chain to GCBotCommand_REFACTORING_ARCHITECTURE.md:
  ```
  DONATION FLOW HTTP CALL CHAIN:
  1. User clicks /start {hash}_DONATE → Telegram → GCBotCommand POST /webhook
  2. GCBotCommand → GCDonationHandler POST /start-donation-input
  3. GCDonationHandler → Telegram API (send keypad message to user)
  4. User clicks keypad digit → Telegram → GCBotCommand POST /webhook (callback_query)
  5. GCBotCommand → GCDonationHandler POST /keypad-input
  6. GCDonationHandler updates amount → sends updated keypad
  7. User clicks "Confirm" → GCBotCommand → GCDonationHandler → GCPaymentGateway /create-invoice
  ```
- [ ] **2.3.2** Add section to GCDonationHandler_REFACTORING_ARCHITECTURE.md showing Telegram webhook is NOT registered (GCBotCommand proxies all callbacks)
- [ ] **2.3.3** Document callback_data format for keypad buttons

**Verification Criteria:**
- [ ] No ambiguity about who receives Telegram webhooks
- [ ] Complete HTTP call chain documented
- [ ] Request/response payloads documented

---

### 🚨 ISSUE #3: Fix GCDonationHandler Stateful Design
**Goal:** Refactor GCDonationHandler from in-memory state to database-backed stateless design

#### Step 3.1: Create Database Migration
- [ ] **3.1.1** Create file: `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/create_donation_keypad_state_table.sql`
  ```sql
  CREATE TABLE IF NOT EXISTS donation_keypad_state (
      user_id BIGINT PRIMARY KEY,
      channel_id TEXT NOT NULL,
      current_amount TEXT DEFAULT '0.00',
      decimal_entered BOOLEAN DEFAULT FALSE,
      state_type TEXT DEFAULT 'donation',
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
  );

  CREATE INDEX idx_donation_keypad_updated_at ON donation_keypad_state(updated_at);

  -- Auto-cleanup old states (> 1 hour)
  CREATE OR REPLACE FUNCTION cleanup_old_donation_states()
  RETURNS void AS $$
  BEGIN
      DELETE FROM donation_keypad_state
      WHERE updated_at < NOW() - INTERVAL '1 hour';
  END;
  $$ LANGUAGE plpgsql;
  ```

- [ ] **3.1.2** Create migration execution script: `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tools/execute_donation_state_migration.py`
- [ ] **3.1.3** Test migration on local database (if available) or telepaypsql-clone-preclaude
- [ ] **3.1.4** Execute migration on telepaypsql production database

#### Step 3.2: Refactor KeypadHandler to Use Database State
- [ ] **3.2.1** Backup current GCDonationHandler-10-26/keypad_handler.py:
  ```bash
  cp GCDonationHandler-10-26/keypad_handler.py GCDonationHandler-10-26/keypad_handler.py.backup-$(date +%Y%m%d-%H%M%S)
  ```

- [ ] **3.2.2** Modify GCDonationHandler-10-26/keypad_handler.py:
  - Replace in-memory `self.user_states = {}` with database methods
  - Add method: `save_keypad_state(user_id: int, channel_id: str, amount: str, decimal_entered: bool)`
  - Add method: `get_keypad_state(user_id: int) -> Optional[Dict]`
  - Add method: `delete_keypad_state(user_id: int)`

- [ ] **3.2.3** Create modular database state manager:
  ```
  GCDonationHandler-10-26/
    ├── keypad_handler.py           # Existing (refactored)
    ├── keypad_state_manager.py     # NEW - Database state operations
    └── database_manager.py         # Existing (add new queries)
  ```

- [ ] **3.2.4** Implement `keypad_state_manager.py` with methods:
  ```python
  class KeypadStateManager:
      def __init__(self, db_manager):
          self.db = db_manager

      def save_state(self, user_id: int, channel_id: str, amount: str, decimal_entered: bool) -> bool:
          # INSERT ... ON CONFLICT (user_id) DO UPDATE
          pass

      def get_state(self, user_id: int) -> Optional[Dict[str, Any]]:
          # SELECT * FROM donation_keypad_state WHERE user_id = %s
          pass

      def delete_state(self, user_id: int) -> bool:
          # DELETE FROM donation_keypad_state WHERE user_id = %s
          pass

      def cleanup_old_states(self) -> int:
          # SELECT cleanup_old_donation_states()
          pass
  ```

- [ ] **3.2.5** Update keypad_handler.py to inject KeypadStateManager:
  ```python
  class KeypadHandler:
      def __init__(self, config: Config, telegram_client: TelegramClient, db_manager: DatabaseManager):
          self.state_manager = KeypadStateManager(db_manager)
          # Remove: self.user_states = {}
  ```

- [ ] **3.2.6** Update all keypad methods to use state_manager:
  - `handle_digit()` → `self.state_manager.get_state()` → update → `self.state_manager.save_state()`
  - `handle_backspace()` → similar pattern
  - `handle_confirm()` → get state → delete state
  - `handle_clear()` → delete state

#### Step 3.3: Update Service Initialization
- [ ] **3.3.1** Modify GCDonationHandler-10-26/service.py `create_app()`:
  ```python
  def create_app():
      app = Flask(__name__)
      config = Config()
      db_manager = DatabaseManager(config)
      telegram_client = TelegramClient(config)

      # Pass db_manager to KeypadHandler
      keypad_handler = KeypadHandler(config, telegram_client, db_manager)

      # Register routes with dependency-injected handlers
      app.config['keypad_handler'] = keypad_handler

      return app
  ```

#### Step 3.4: Testing & Verification
- [ ] **3.4.1** Create test script: `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tests/test_stateless_keypad.py`
  - Test concurrent requests from same user
  - Verify state persists across multiple Cloud Run instances
  - Test state cleanup after 1 hour

- [ ] **3.4.2** Deploy updated GCDonationHandler to Cloud Run
- [ ] **3.4.3** Test with real user interaction (donation flow)
- [ ] **3.4.4** Monitor Cloud Logging for errors
- [ ] **3.4.5** Verify state cleanup cron works (or add Cloud Scheduler job)

**Verification Criteria:**
- [ ] No in-memory state in keypad_handler.py
- [ ] All state operations use donation_keypad_state table
- [ ] Service can scale horizontally without state loss
- [ ] Old states are automatically cleaned up

---

### 🚨 ISSUE #5: Implement Inter-Service Authentication
**Goal:** Secure all service-to-service HTTP calls with authentication

#### Step 4.1: Choose Authentication Strategy
- [ ] **4.1.1** Review Context7 best practices for microservice authentication using MCP:
  ```
  Use mcp__context7__resolve-library-id and mcp__context7__get-library-docs to research:
  - Flask JWT authentication patterns
  - Google Cloud Run service-to-service auth with OIDC
  ```

- [ ] **4.1.2** **DECISION:** Choose between:
  - **Option A:** Shared JWT Secret (simpler, faster implementation)
  - **Option B:** Google Cloud IAM with OIDC tokens (more secure, native to GCP)

#### Step 4.2: If Choosing Option A (Shared JWT Secret)

##### Step 4.2.1: Create Shared JWT Secret
- [ ] **4.2.1.1** Generate secure JWT secret:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] **4.2.1.2** Store in Secret Manager:
  ```bash
  echo -n "YOUR_GENERATED_SECRET" | gcloud secrets create INTER_SERVICE_JWT_SECRET --data-file=-
  ```

- [ ] **4.2.1.3** Grant access to all service accounts:
  ```bash
  for service in gcbotcommand gcpaymentgateway gcdonationhandler gcnotificationservice gcbroadcastservice gcsubscriptionmonitor; do
    gcloud secrets add-iam-policy-binding INTER_SERVICE_JWT_SECRET \
      --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
  done
  ```

##### Step 4.2.2: Create Shared JWT Module (Copy to Each Service)
- [ ] **4.2.2.1** Create template module: `TOOLS_SCRIPTS_TESTS/templates/service_auth.py`:
  ```python
  import jwt
  import logging
  from datetime import datetime, timedelta
  from functools import wraps
  from flask import request, jsonify
  from typing import Optional

  logger = logging.getLogger(__name__)

  class ServiceAuth:
      def __init__(self, jwt_secret: str, service_name: str):
          self.jwt_secret = jwt_secret
          self.service_name = service_name

      def generate_token(self, target_service: str, expiry_minutes: int = 5) -> str:
          """Generate JWT token for calling another service"""
          payload = {
              'source_service': self.service_name,
              'target_service': target_service,
              'exp': datetime.utcnow() + timedelta(minutes=expiry_minutes),
              'iat': datetime.utcnow()
          }
          token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
          logger.info(f"🔐 Generated token for {self.service_name} → {target_service}")
          return token

      def verify_token(self, token: str) -> Optional[dict]:
          """Verify JWT token from another service"""
          try:
              payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])

              # Verify target_service matches this service
              if payload.get('target_service') != self.service_name:
                  logger.warning(f"❌ Token target mismatch: expected {self.service_name}, got {payload.get('target_service')}")
                  return None

              logger.info(f"✅ Token verified: {payload.get('source_service')} → {self.service_name}")
              return payload

          except jwt.ExpiredSignatureError:
              logger.warning("❌ Token expired")
              return None
          except jwt.InvalidTokenError as e:
              logger.warning(f"❌ Invalid token: {e}")
              return None

      def require_service_auth(self, f):
          """Decorator to protect endpoints requiring inter-service auth"""
          @wraps(f)
          def decorated_function(*args, **kwargs):
              auth_header = request.headers.get('Authorization')

              if not auth_header or not auth_header.startswith('Bearer '):
                  logger.warning("❌ Missing or invalid Authorization header")
                  return jsonify({'error': 'Unauthorized - Missing token'}), 401

              token = auth_header.split(' ')[1]
              payload = self.verify_token(token)

              if not payload:
                  return jsonify({'error': 'Unauthorized - Invalid token'}), 401

              # Add source_service to kwargs so endpoint knows who called it
              kwargs['source_service'] = payload.get('source_service')
              return f(*args, **kwargs)

          return decorated_function
  ```

##### Step 4.2.3: Integrate ServiceAuth into Each Service
- [ ] **4.2.3.1** Copy service_auth.py to GCPaymentGateway-10-26/
- [ ] **4.2.3.2** Update GCPaymentGateway-10-26/config_manager.py to fetch INTER_SERVICE_JWT_SECRET
- [ ] **4.2.3.3** Update GCPaymentGateway-10-26/service.py:
  ```python
  from service_auth import ServiceAuth

  def create_app():
      app = Flask(__name__)
      config = Config()

      # Initialize ServiceAuth
      jwt_secret = config.get_secret('INTER_SERVICE_JWT_SECRET')
      service_auth = ServiceAuth(jwt_secret, 'gcpaymentgateway')
      app.config['service_auth'] = service_auth

      return app
  ```

- [ ] **4.2.3.4** Protect GCPaymentGateway-10-26 `/create-invoice` endpoint:
  ```python
  @app.route('/create-invoice', methods=['POST'])
  @service_auth.require_service_auth
  def create_invoice(source_service=None):
      logger.info(f"💳 Invoice request from {source_service}")
      # ... existing logic
  ```

- [ ] **4.2.3.5** Repeat for GCDonationHandler-10-26:
  - Copy service_auth.py
  - Protect `/start-donation-input` endpoint
  - Protect `/keypad-input` endpoint
  - Protect `/broadcast-closed-channels` endpoint

- [ ] **4.2.3.6** Repeat for GCNotificationService-10-26:
  - Copy service_auth.py
  - Protect `/send-notification` endpoint
  - Protect `/verify-config` endpoint

- [ ] **4.2.3.7** Update GCBotCommand-10-26 to SEND tokens:
  ```python
  # In utils/http_client.py
  class ServiceClient:
      def __init__(self, config, service_auth):
          self.config = config
          self.service_auth = service_auth

      def call_payment_gateway(self, data: dict) -> dict:
          token = self.service_auth.generate_token('gcpaymentgateway')
          headers = {'Authorization': f'Bearer {token}'}

          response = requests.post(
              f"{self.config.gcpaymentgateway_url}/create-invoice",
              json=data,
              headers=headers,
              timeout=10
          )
          return response.json()
  ```

#### Step 4.3: If Choosing Option B (Google Cloud IAM)

##### Step 4.3.1: Configure Service Accounts
- [ ] **4.3.1.1** List current service accounts:
  ```bash
  gcloud iam service-accounts list
  ```

- [ ] **4.3.1.2** Create dedicated service account for each service (if not using default):
  ```bash
  gcloud iam service-accounts create gcbotcommand-sa --display-name="GCBotCommand Service Account"
  # Repeat for each service
  ```

- [ ] **4.3.1.3** Grant invoker role for GCBotCommand → GCPaymentGateway:
  ```bash
  gcloud run services add-iam-policy-binding gcpaymentgateway-10-26 \
    --member="serviceAccount:gcbotcommand-sa@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
  ```

- [ ] **4.3.1.4** Repeat for all service-to-service call paths:
  - GCBotCommand → GCDonationHandler
  - GCBotCommand → GCPaymentGateway
  - GCDonationHandler → GCPaymentGateway
  - np-webhook-10-26 → GCNotificationService
  - GCSubscriptionMonitor → GCNotificationService

##### Step 4.3.2: Update Services to Use OIDC Tokens
- [ ] **4.3.2.1** Create template module: `TOOLS_SCRIPTS_TESTS/templates/oidc_auth.py`:
  ```python
  import google.auth
  import google.auth.transport.requests
  from google.oauth2 import id_token
  import requests
  import logging

  logger = logging.getLogger(__name__)

  class OIDCAuth:
      def __init__(self):
          self.creds, self.project = google.auth.default()

      def get_id_token(self, target_url: str) -> str:
          """Get OIDC token for calling Cloud Run service"""
          auth_req = google.auth.transport.requests.Request()
          token = id_token.fetch_id_token(auth_req, target_url)
          return token

      def call_service(self, url: str, method: str = 'POST', json_data: dict = None) -> requests.Response:
          """Call Cloud Run service with OIDC authentication"""
          token = self.get_id_token(url)
          headers = {'Authorization': f'Bearer {token}'}

          response = requests.request(method, url, json=json_data, headers=headers, timeout=10)
          logger.info(f"🔐 Called {url} with OIDC token: {response.status_code}")
          return response
  ```

- [ ] **4.3.2.2** Copy oidc_auth.py to each service that makes HTTP calls
- [ ] **4.3.2.3** Update HTTP client code to use OIDCAuth

##### Step 4.3.3: Remove allow-unauthenticated from Services
- [ ] **4.3.3.1** Update GCPaymentGateway to require authentication:
  ```bash
  gcloud run services update gcpaymentgateway-10-26 \
    --no-allow-unauthenticated \
    --region=us-central1
  ```

- [ ] **4.3.3.2** Repeat for GCDonationHandler
- [ ] **4.3.3.3** Repeat for GCNotificationService
- [ ] **4.3.3.4** Keep GCBotCommand public (receives Telegram webhooks)

#### Step 4.4: Testing & Verification
- [ ] **4.4.1** Test GCBotCommand → GCPaymentGateway authenticated call
- [ ] **4.4.2** Test GCBotCommand → GCDonationHandler authenticated call
- [ ] **4.4.3** Test np-webhook → GCNotificationService authenticated call
- [ ] **4.4.4** Verify unauthenticated calls are rejected (401 Unauthorized)
- [ ] **4.4.5** Monitor Cloud Logging for authentication errors

**Verification Criteria:**
- [ ] All inter-service HTTP calls use authentication
- [ ] Unauthenticated calls are rejected
- [ ] No authentication bypass vulnerabilities
- [ ] Service-to-service latency impact is minimal (<50ms)

---

## ⚠️ PRIORITY 2: HIGH-PRIORITY ISSUES (SHOULD FIX SOON)

### 🔧 ISSUE #4: Create Centralized Database Schema Documentation
**Goal:** Document all database tables with complete schema and relationships

#### Step 5.1: Discover All Tables
- [ ] **5.1.1** Connect to telepaypsql and list all tables:
  ```sql
  SELECT table_name FROM information_schema.tables
  WHERE table_schema = 'public'
  ORDER BY table_name;
  ```

- [ ] **5.1.2** For each table, get complete schema:
  ```sql
  SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
  FROM information_schema.columns
  WHERE table_name = 'TABLE_NAME'
  ORDER BY ordinal_position;
  ```

- [ ] **5.1.3** Get all indexes:
  ```sql
  SELECT indexname, indexdef FROM pg_indexes
  WHERE tablename = 'TABLE_NAME';
  ```

- [ ] **5.1.4** Get all foreign keys:
  ```sql
  SELECT
      tc.table_name,
      kcu.column_name,
      ccu.table_name AS foreign_table_name,
      ccu.column_name AS foreign_column_name
  FROM information_schema.table_constraints AS tc
  JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
  JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
  WHERE tc.constraint_type = 'FOREIGN KEY';
  ```

#### Step 5.2: Create DATABASE_SCHEMA_COMPLETE.md
- [ ] **5.2.1** Create file: `OCTOBER/10-26/DATABASE_SCHEMA_COMPLETE.md`

- [ ] **5.2.2** Document table ownership matrix:
  ```markdown
  | Table Name | Owned By | Read By | Written By |
  |-----------|----------|---------|------------|
  | main_clients_database | GCBotCommand (database handler) | GCPaymentGateway, GCDonationHandler, GCNotificationService | GCBotCommand |
  | broadcast_manager | GCBroadcastService | GCBroadcastService | GCBroadcastService |
  | user_conversation_state | GCBotCommand | GCBotCommand | GCBotCommand |
  | private_channel_users_database | ??? | GCSubscriptionMonitor | ??? |
  ```

- [ ] **5.2.3** For each table, document:
  - Table name
  - Purpose
  - Owned by (which service writes)
  - Read by (which services read)
  - Complete schema with types
  - Indexes
  - Foreign keys
  - Sample row

- [ ] **5.2.4** Create ER diagram using Mermaid:
  ```mermaid
  erDiagram
      main_clients_database ||--o{ private_channel_users_database : "has users"
      main_clients_database {
          text open_channel_id PK
          text channel_name
          text wallet_address
          numeric sub_price_1_month
          ...
      }
  ```

- [ ] **5.2.5** Document data flow:
  ```
  User Payment Flow:
  1. User visits /start → GCBotCommand reads main_clients_database
  2. Payment created → GCPaymentGateway reads main_clients_database
  3. Payment confirmed → Writes to processed_payments table
  4. User invited → Writes to private_channel_users_database
  ```

**Verification Criteria:**
- [ ] All tables documented
- [ ] Foreign key relationships shown
- [ ] Service ownership clear
- [ ] Data flow diagrams complete

---

### 🔧 ISSUE #7: Document Error Handling & Retry Strategy
**Goal:** Create comprehensive error handling documentation and implement retry logic

#### Step 6.1: Research Best Practices
- [ ] **6.1.1** Use Context7 MCP to research:
  ```
  - Python requests retry strategies (urllib3.util.retry)
  - Flask error handling patterns
  - Circuit breaker patterns for microservices
  - Dead letter queue implementations
  ```

#### Step 6.2: Create ERROR_HANDLING_STRATEGY.md
- [ ] **6.2.1** Create file: `OCTOBER/10-26/ERROR_HANDLING_STRATEGY.md`

- [ ] **6.2.2** Document retry policies per external service:
  ```markdown
  ## NowPayments API (GCPaymentGateway)
  - **Timeout:** 10 seconds
  - **Retry Policy:** 3 attempts with exponential backoff (2^attempt seconds)
  - **Retryable Errors:** Connection timeout, 500/502/503/504 status codes
  - **Non-Retryable Errors:** 400/401/403 status codes
  - **Circuit Breaker:** Open after 5 consecutive failures, half-open after 60 seconds
  ```

- [ ] **6.2.3** Document inter-service retry policies:
  ```markdown
  ## GCBotCommand → GCPaymentGateway
  - **Timeout:** 5 seconds
  - **Retry Policy:** 2 attempts with 1-second delay
  - **Fallback:** Show error message to user, log to Cloud Logging
  ```

- [ ] **6.2.4** Document database retry policies:
  ```markdown
  ## Database Connection Failures
  - **Timeout:** 5 seconds per query
  - **Retry Policy:** 3 attempts with 1-second delay
  - **Connection Pool:** Max 5 connections per service
  - **Fallback:** Return 503 Service Unavailable
  ```

- [ ] **6.2.5** Document Telegram API retry policies:
  ```markdown
  ## Telegram Bot API (GCNotificationService, GCSubscriptionMonitor)
  - **Timeout:** 10 seconds
  - **Retry Policy:** Use python-telegram-bot's built-in retry (3 attempts)
  - **Rate Limiting:** Max 30 messages/second per bot
  - **Fallback:** Log failed messages, add to retry queue
  ```

#### Step 6.3: Implement Retry Logic Module
- [ ] **6.3.1** Create template module: `TOOLS_SCRIPTS_TESTS/templates/retry_handler.py`:
  ```python
  import time
  import logging
  from functools import wraps
  from typing import Callable, Any, Optional, List
  import requests

  logger = logging.getLogger(__name__)

  class RetryHandler:
      def __init__(
          self,
          max_attempts: int = 3,
          backoff_factor: float = 2.0,
          retryable_status_codes: List[int] = None
      ):
          self.max_attempts = max_attempts
          self.backoff_factor = backoff_factor
          self.retryable_status_codes = retryable_status_codes or [500, 502, 503, 504]

      def with_retry(self, operation_name: str = "operation"):
          """Decorator to add retry logic to any function"""
          def decorator(func: Callable) -> Callable:
              @wraps(func)
              def wrapper(*args, **kwargs) -> Any:
                  last_exception = None

                  for attempt in range(1, self.max_attempts + 1):
                      try:
                          result = func(*args, **kwargs)

                          # Check if result is HTTP response with retryable status
                          if isinstance(result, requests.Response):
                              if result.status_code in self.retryable_status_codes:
                                  logger.warning(
                                      f"⚠️ {operation_name} returned {result.status_code}, "
                                      f"attempt {attempt}/{self.max_attempts}"
                                  )
                                  if attempt < self.max_attempts:
                                      time.sleep(self.backoff_factor ** attempt)
                                      continue

                          if attempt > 1:
                              logger.info(f"✅ {operation_name} succeeded on attempt {attempt}")

                          return result

                      except (requests.Timeout, requests.ConnectionError) as e:
                          last_exception = e
                          logger.warning(
                              f"⚠️ {operation_name} failed: {e}, "
                              f"attempt {attempt}/{self.max_attempts}"
                          )

                          if attempt < self.max_attempts:
                              sleep_time = self.backoff_factor ** attempt
                              logger.info(f"⏳ Retrying in {sleep_time} seconds...")
                              time.sleep(sleep_time)
                          else:
                              logger.error(f"❌ {operation_name} failed after {self.max_attempts} attempts")
                              raise last_exception

                      except Exception as e:
                          logger.error(f"❌ {operation_name} non-retryable error: {e}")
                          raise

                  raise last_exception

              return wrapper
          return decorator

  # Circuit Breaker Implementation
  class CircuitBreaker:
      def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
          self.failure_threshold = failure_threshold
          self.recovery_timeout = recovery_timeout
          self.failures = 0
          self.last_failure_time = None
          self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

      def call(self, func: Callable, *args, **kwargs) -> Any:
          if self.state == 'OPEN':
              if time.time() - self.last_failure_time > self.recovery_timeout:
                  logger.info("🔄 Circuit breaker entering HALF_OPEN state")
                  self.state = 'HALF_OPEN'
              else:
                  raise Exception("Circuit breaker is OPEN - service unavailable")

          try:
              result = func(*args, **kwargs)

              if self.state == 'HALF_OPEN':
                  logger.info("✅ Circuit breaker closing after successful call")
                  self.state = 'CLOSED'
                  self.failures = 0

              return result

          except Exception as e:
              self.failures += 1
              self.last_failure_time = time.time()

              if self.failures >= self.failure_threshold:
                  logger.error(f"🚨 Circuit breaker OPENING after {self.failures} failures")
                  self.state = 'OPEN'

              raise e
  ```

#### Step 6.4: Integrate Retry Logic into Services
- [ ] **6.4.1** Copy retry_handler.py to GCPaymentGateway-10-26/

- [ ] **6.4.2** Update GCPaymentGateway-10-26/payment_handler.py:
  ```python
  from retry_handler import RetryHandler

  class PaymentHandler:
      def __init__(self, config: Config):
          self.config = config
          self.retry_handler = RetryHandler(max_attempts=3, backoff_factor=2.0)

      @retry_handler.with_retry(operation_name="NowPayments create_invoice")
      def create_nowpayments_invoice(self, amount: float, currency: str, order_id: str) -> dict:
          response = requests.post(
              'https://api.nowpayments.io/v1/invoice',
              json={...},
              timeout=10
          )
          response.raise_for_status()
          return response.json()
  ```

- [ ] **6.4.3** Repeat for GCBotCommand-10-26/utils/http_client.py:
  ```python
  @retry_handler.with_retry(operation_name="GCPaymentGateway call")
  def call_payment_gateway(self, data: dict) -> dict:
      # ... HTTP call logic
  ```

- [ ] **6.4.4** Implement circuit breaker for NowPayments API:
  ```python
  nowpayments_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

  def create_invoice_with_circuit_breaker(...):
      return nowpayments_circuit_breaker.call(create_nowpayments_invoice, ...)
  ```

#### Step 6.5: Implement Dead Letter Queue
- [ ] **6.5.1** Create database table for failed operations:
  ```sql
  CREATE TABLE failed_operations (
      id SERIAL PRIMARY KEY,
      operation_type TEXT NOT NULL,  -- 'payment_notification', 'channel_invite', etc.
      service_name TEXT NOT NULL,
      payload JSONB NOT NULL,
      error_message TEXT,
      retry_count INT DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW(),
      last_retry_at TIMESTAMP,
      status TEXT DEFAULT 'pending'  -- 'pending', 'retrying', 'failed', 'resolved'
  );

  CREATE INDEX idx_failed_operations_status ON failed_operations(status, created_at);
  ```

- [ ] **6.5.2** Create module: `TOOLS_SCRIPTS_TESTS/templates/dead_letter_queue.py`:
  ```python
  class DeadLetterQueue:
      def __init__(self, db_manager):
          self.db = db_manager

      def add_failed_operation(self, operation_type: str, service_name: str, payload: dict, error_message: str):
          # INSERT INTO failed_operations
          pass

      def get_pending_operations(self, limit: int = 100):
          # SELECT * FROM failed_operations WHERE status = 'pending' ORDER BY created_at LIMIT %s
          pass

      def mark_resolved(self, operation_id: int):
          # UPDATE failed_operations SET status = 'resolved'
          pass
  ```

- [ ] **6.5.3** Add to error handling in critical paths:
  ```python
  try:
      send_notification(...)
  except Exception as e:
      logger.error(f"❌ Notification failed: {e}")
      dlq.add_failed_operation('payment_notification', 'gcnotificationservice', payload, str(e))
  ```

**Verification Criteria:**
- [ ] All external API calls have retry logic
- [ ] Circuit breaker prevents cascade failures
- [ ] Dead letter queue captures failed operations
- [ ] Error handling documented per service

---

### 🔧 ISSUE #6: Resolve Broadcast Service Naming Collision
**Goal:** Clarify separation of concerns between broadcast functionality in different services

#### Step 7.1: Analyze Broadcast Functionality
- [ ] **7.1.1** Read GCBroadcastService-10-26 documentation to understand WHAT it broadcasts
- [ ] **7.1.2** Read GCDonationHandler-10-26/broadcast_manager.py to understand its broadcast purpose
- [ ] **7.1.3** Check if both use same `broadcast_manager` database table:
  ```sql
  SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'broadcast_manager';
  ```

#### Step 7.2: Document Separation of Concerns
- [ ] **7.2.1** Update GCBroadcastService_REFACTORING_ARCHITECTURE.md:
  ```markdown
  ## Broadcast Service Scope
  This service handles **automated scheduled broadcasts** sent to channel owners:
  - Daily reminder messages
  - System announcements
  - Scheduled campaigns

  **NOT responsible for:** Donation-related broadcasts (handled by GCDonationHandler)
  ```

- [ ] **7.2.2** Update GCDonationHandler_REFACTORING_ARCHITECTURE.md:
  ```markdown
  ## Donation Broadcast Functionality
  The `broadcast_manager.py` module handles **donation message broadcasts** to closed channels:
  - Sends donation keypads to closed channel users
  - Different from GCBroadcastService (scheduled system broadcasts)

  **Naming Note:** Will be renamed to `donation_broadcast_manager.py` to avoid confusion
  ```

#### Step 7.3: Refactor Module Names (If Confusion Exists)
- [ ] **7.3.1** If GCDonationHandler broadcast_manager.py conflicts, rename:
  ```bash
  cd GCDonationHandler-10-26
  mv broadcast_manager.py donation_broadcast_manager.py
  ```

- [ ] **7.3.2** Update imports in service.py

- [ ] **7.3.3** Update architecture documentation

**Verification Criteria:**
- [ ] Clear documentation of what each service broadcasts
- [ ] No naming collisions
- [ ] Developers understand separation of concerns

---

## ⚠️ PRIORITY 3: MEDIUM & LOW-PRIORITY ISSUES

### 🔧 ISSUE #8: Standardize Telegram Bot API Usage
**Goal:** Use consistent library across all services for Telegram interactions

#### Step 8.1: Audit Current Telegram API Usage
- [ ] **8.1.1** List services using `python-telegram-bot` library:
  - GCNotificationService ✅
  - GCSubscriptionMonitor ✅

- [ ] **8.1.2** List services using direct `requests` calls:
  - GCBotCommand ❌ (uses raw HTTP requests)

#### Step 8.2: Refactor GCBotCommand to Use python-telegram-bot
- [ ] **8.2.1** Add `python-telegram-bot` to GCBotCommand-10-26/requirements.txt:
  ```
  python-telegram-bot==20.7
  ```

- [ ] **8.2.2** Create telegram_client.py module:
  ```
  GCBotCommand-10-26/
    ├── telegram_client.py     # NEW - Wraps python-telegram-bot
    └── utils/
        └── http_client.py     # Existing (remove raw Telegram API calls)
  ```

- [ ] **8.2.3** Implement telegram_client.py:
  ```python
  from telegram import Bot
  from telegram.error import TelegramError
  import logging

  logger = logging.getLogger(__name__)

  class TelegramClient:
      def __init__(self, bot_token: str):
          self.bot = Bot(token=bot_token)

      async def send_message(self, chat_id: int, text: str, reply_markup=None) -> bool:
          try:
              await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
              logger.info(f"✅ Message sent to {chat_id}")
              return True
          except TelegramError as e:
              logger.error(f"❌ Failed to send message: {e}")
              return False
  ```

- [ ] **8.2.4** Update service.py to use TelegramClient instead of raw requests

**Verification Criteria:**
- [ ] All services use `python-telegram-bot` library
- [ ] No raw HTTP requests to Telegram API
- [ ] Error handling is consistent

---

### 🔧 ISSUE #9: Standardize Database Connection Pattern
**Goal:** Document why different connection methods are used OR standardize

#### Step 9.1: Document Current Patterns
- [ ] **9.1.1** Create section in DATABASE_SCHEMA_COMPLETE.md:
  ```markdown
  ## Database Connection Patterns

  ### Pattern A: Direct psycopg2 (Most Services)
  - Used by: GCBotCommand, GCPaymentGateway, GCDonationHandler, GCNotificationService
  - Connection: Unix socket `/cloudsql/{connection_name}`
  - Reason: Simple, low overhead

  ### Pattern B: Cloud SQL Connector + SQLAlchemy (GCSubscriptionMonitor)
  - Used by: GCSubscriptionMonitor
  - Connection: Cloud SQL Connector with pg8000
  - Reason: Requires SQLAlchemy for complex queries with ORM
  ```

#### Step 9.2: Decision: Standardize or Document
- [ ] **9.2.1** **DECISION:** Either:
  - **Option A:** Keep both patterns, document rationale
  - **Option B:** Migrate all services to Pattern A (psycopg2)
  - **Option C:** Migrate all services to Pattern B (Cloud SQL Connector)

- [ ] **9.2.2** If standardizing, create migration plan

**Verification Criteria:**
- [ ] Connection pattern rationale documented
- [ ] OR all services use same pattern

---

### 🔧 ISSUE #10: Track Deployment Status
**Goal:** Create deployment status tracking document

#### Step 10.1: Create DEPLOYMENT_STATUS.md
- [ ] **10.1.1** Create file: `OCTOBER/10-26/DEPLOYMENT_STATUS.md`

- [ ] **10.1.2** Document current deployment status:
  ```markdown
  ## Service Deployment Status

  | Service | Status | Cloud Run URL | Cloud Scheduler | Last Deploy | Version |
  |---------|--------|---------------|-----------------|-------------|---------|
  | GCBotCommand | 🟢 LIVE | https://gcbotcommand-10-26-... | N/A | 2025-11-10 | v1.2 |
  | GCPaymentGateway | 🟢 LIVE | https://gcpaymentgateway-10-26-... | N/A | 2025-11-09 | v1.0 |
  | GCDonationHandler | 🟢 LIVE | https://gcdonationhandler-10-26-... | N/A | 2025-11-09 | v1.0 |
  | GCNotificationService | 🟢 LIVE | https://gcnotificationservice-10-26-... | N/A | 2025-11-08 | v1.0 |
  | GCBroadcastService | 🟡 PARTIAL | https://gcbroadcastservice-10-26-... | ✅ Daily 12:00 UTC | 2025-11-07 | v0.9 |
  | GCSubscriptionMonitor | 🔴 PENDING | https://gcsubscriptionmonitor-10-26-... | ❌ NOT DEPLOYED | 2025-11-07 | v1.0 |
  ```

- [ ] **10.1.3** Document integration status:
  ```markdown
  ## Service Integration Matrix

  | From Service | To Service | Status | Auth Method |
  |-------------|------------|--------|-------------|
  | GCBotCommand → GCPaymentGateway | ✅ WORKING | ❌ No Auth |
  | GCBotCommand → GCDonationHandler | ✅ WORKING | ❌ No Auth |
  | np-webhook → GCNotificationService | ✅ WORKING | ❌ No Auth |
  ```

**Verification Criteria:**
- [ ] All services tracked
- [ ] Deployment dates recorded
- [ ] Integration status visible

---

### 🔧 ISSUE #12: Deploy GCSubscriptionMonitor Cloud Scheduler
**Goal:** Enable automated subscription expiration monitoring

#### Step 11.1: Create Cloud Scheduler Job
- [ ] **11.1.1** Deploy Cloud Scheduler job:
  ```bash
  gcloud scheduler jobs create http gcsubscriptionmonitor-check-expirations \
    --schedule="*/1 * * * *" \
    --uri="$(gcloud run services describe gcsubscriptionmonitor-10-26 --region=us-central1 --format='value(status.url)')/check-expirations" \
    --http-method=POST \
    --location=us-central1 \
    --oidc-service-account-email="291176869049-compute@developer.gserviceaccount.com" \
    --description="Check for expired subscriptions every minute"
  ```

- [ ] **11.1.2** Verify scheduler job created:
  ```bash
  gcloud scheduler jobs describe gcsubscriptionmonitor-check-expirations --location=us-central1
  ```

- [ ] **11.1.3** Manually trigger test run:
  ```bash
  gcloud scheduler jobs run gcsubscriptionmonitor-check-expirations --location=us-central1
  ```

- [ ] **11.1.4** Check Cloud Logging for execution:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcsubscriptionmonitor-10-26" --limit=20 --format=json
  ```

**Verification Criteria:**
- [ ] Scheduler job runs every 60 seconds
- [ ] GCSubscriptionMonitor processes expirations
- [ ] Users are removed from channels at expiration

---

### 🔧 ISSUE #13: Centralize Environment Variable Documentation
**Goal:** Document all environment variables across all services

#### Step 12.1: Collect Environment Variables
- [ ] **12.1.1** For each service, extract environment variables from:
  - config_manager.py
  - .env.example
  - Deployment commands

#### Step 12.2: Create ENVIRONMENT_VARIABLES.md
- [ ] **12.2.1** Create file: `OCTOBER/10-26/ENVIRONMENT_VARIABLES.md`

- [ ] **12.2.2** Document per-service variables:
  ```markdown
  ## GCBotCommand

  | Variable | Type | Source | Example | Required |
  |----------|------|--------|---------|----------|
  | TELEGRAM_BOT_SECRET_NAME | Secret | Secret Manager | telegram-bot-token | ✅ |
  | TELEGRAM_BOT_USERNAME | Config | Secret Manager | TelepayBot | ✅ |
  | GCPAYMENTGATEWAY_URL | Config | Manual | https://gcpaymentgateway-... | ✅ |
  | GCDONATIONHANDLER_URL | Config | Manual | https://gcdonationhandler-... | ✅ |
  | DATABASE_HOST_SECRET | Secret | Secret Manager | /cloudsql/... | ✅ |
  ```

**Verification Criteria:**
- [ ] All environment variables documented
- [ ] Source of each variable clear
- [ ] Example values provided

---

## 📋 DOCUMENTATION DELIVERABLES CHECKLIST

### New Documentation Files to Create
- [ ] **PAYMENT_WORKFLOW_COMPLETE.md** - End-to-end payment flow
- [ ] **DATABASE_SCHEMA_COMPLETE.md** - All tables with relationships
- [ ] **ERROR_HANDLING_STRATEGY.md** - Retry policies and circuit breakers
- [ ] **DEPLOYMENT_STATUS.md** - Service deployment tracking
- [ ] **ENVIRONMENT_VARIABLES.md** - Centralized env var documentation
- [ ] **SERVICE_INTEGRATION_MATRIX.md** (Optional) - Who calls whom

### Existing Documentation to Update
- [ ] **GCBotCommand_REFACTORING_ARCHITECTURE.md** - Add donation flow HTTP call chain
- [ ] **GCDonationHandler_REFACTORING_ARCHITECTURE.md** - Add stateless design notes
- [ ] **GCBroadcastService_REFACTORING_ARCHITECTURE.md** - Clarify broadcast scope
- [ ] **GCPaymentGateway_REFACTORING_ARCHITECTURE.md** - Add authentication section
- [ ] **GCNotificationService_REFACTORING_ARCHITECTURE.md** - Add authentication section

---

## 🧪 TESTING CHECKLIST

### Unit Tests to Create
- [ ] **test_stateless_keypad.py** - Verify database-backed donation state
- [ ] **test_service_auth.py** - Verify JWT token generation/validation
- [ ] **test_retry_handler.py** - Verify retry logic with exponential backoff
- [ ] **test_circuit_breaker.py** - Verify circuit breaker state transitions

### Integration Tests to Create
- [ ] **test_payment_flow_e2e.py** - Complete payment flow from /start to channel invite
- [ ] **test_donation_flow_e2e.py** - Complete donation flow from token to payment
- [ ] **test_inter_service_auth.py** - Verify authenticated service-to-service calls

### Manual Testing Checklist
- [ ] Test payment flow with real Telegram user
- [ ] Test donation flow with real Telegram user
- [ ] Test broadcast messages
- [ ] Test subscription expiration
- [ ] Test authentication rejection (unauthenticated calls fail)
- [ ] Load test GCDonationHandler with multiple concurrent users
- [ ] Verify state persistence across Cloud Run instance restarts

---

## 📊 IMPLEMENTATION PROGRESS TRACKING

### Priority 1 (Critical) - Target: Week 1
- [ ] Payment workflow documentation (Tasks 1.1-1.3)
- [ ] Donation flow clarification (Tasks 2.1-2.3)
- [ ] Stateless design fix (Tasks 3.1-3.4)
- [ ] Inter-service authentication (Tasks 4.1-4.4)

**Estimated Effort:** 40 hours (1 week with 1 developer)

### Priority 2 (High) - Target: Week 2
- [ ] Database schema documentation (Tasks 5.1-5.2)
- [ ] Error handling strategy (Tasks 6.1-6.5)
- [ ] Broadcast naming collision (Tasks 7.1-7.3)
- [ ] Cloud Scheduler deployment (Task 11.1)

**Estimated Effort:** 24 hours (3 days with 1 developer)

### Priority 3 (Medium-Low) - Target: Week 3
- [ ] Telegram API standardization (Task 8.1-8.2)
- [ ] Database connection pattern (Task 9.1-9.2)
- [ ] Deployment status tracking (Task 10.1)
- [ ] Environment variable documentation (Task 12.1-12.2)

**Estimated Effort:** 16 hours (2 days with 1 developer)

---

## ✅ DEFINITION OF DONE

### For Each Issue:
- [ ] Code changes implemented following modular structure
- [ ] Documentation updated
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Manual testing completed
- [ ] Deployed to production
- [ ] Monitored for 24 hours with no errors
- [ ] Code review completed (if applicable)

### For Overall Refactoring:
- [ ] All Priority 1 tasks completed
- [ ] All Priority 2 tasks completed
- [ ] End-to-end payment flow tested in production
- [ ] End-to-end donation flow tested in production
- [ ] All services using authenticated inter-service calls
- [ ] No in-memory state in any service
- [ ] All recommended documentation created
- [ ] Production monitoring shows stable operation
- [ ] Team sign-off on production readiness

---

## 🚀 DEPLOYMENT CHECKLIST

### Pre-Deployment
- [ ] Backup current production database
- [ ] Create rollback plan for each service
- [ ] Schedule maintenance window (if needed)
- [ ] Notify users of potential downtime

### Deployment Order (Minimize Risk)
1. [ ] Deploy database migrations (donation_keypad_state, failed_operations)
2. [ ] Deploy GCDonationHandler with stateless design
3. [ ] Deploy inter-service authentication changes (all services)
4. [ ] Deploy retry logic and error handling
5. [ ] Deploy Cloud Scheduler for GCSubscriptionMonitor
6. [ ] Deploy documentation updates

### Post-Deployment
- [ ] Verify all services are running
- [ ] Test critical user flows (payment, donation)
- [ ] Monitor Cloud Logging for errors
- [ ] Check Cloud Monitoring metrics
- [ ] Perform load testing
- [ ] Document any issues encountered
- [ ] Update DEPLOYMENT_STATUS.md

---

## 📝 NOTES FOR CLAUDE

### When Implementing This Checklist:
1. **Start with documentation tasks (1.1-1.3)** - Understand missing services before coding
2. **Prioritize stateless design fix (3.1-3.4)** - Critical for horizontal scaling
3. **Use Context7 MCP** when implementing authentication and retry logic to follow best practices
4. **Create modular files** - Don't put all logic in service.py
5. **Test each change** before moving to next task
6. **Update PROGRESS.md, DECISIONS.md, BUGS.md** after each major task completion

### File Structure Best Practices:
```
GCService-10-26/
├── service.py                    # Flask app factory ONLY
├── config_manager.py             # Secret Manager integration
├── database_manager.py           # Raw SQL queries
├── {service}_handler.py          # Core business logic
├── service_auth.py               # Authentication logic
├── retry_handler.py              # Retry and circuit breaker
├── telegram_client.py            # Telegram API wrapper
├── utils/
│   ├── validators.py             # Input validation
│   ├── formatters.py             # Response formatting
│   └── logging_utils.py          # Structured logging
└── routes/
    ├── public_routes.py          # Telegram webhooks (unauthenticated)
    └── internal_routes.py        # Inter-service endpoints (authenticated)
```

### Avoid These Anti-Patterns:
- ❌ Putting all logic in service.py (monolithic file)
- ❌ In-memory state (breaks horizontal scaling)
- ❌ No error handling (services will crash)
- ❌ No authentication (security vulnerability)
- ❌ No retry logic (brittle under failures)
- ❌ Duplicating code across services (create templates in TOOLS_SCRIPTS_TESTS/templates/)

---

**Checklist Version:** 1.0
**Last Updated:** 2025-11-13
**Maintained By:** Claude
**Status:** 🟡 IN PROGRESS
