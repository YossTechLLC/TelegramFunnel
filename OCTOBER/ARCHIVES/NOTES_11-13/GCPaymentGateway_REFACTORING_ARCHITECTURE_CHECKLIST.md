# GCPaymentGateway-10-26 Implementation Checklist

**Document Version:** 1.0
**Date:** 2025-11-12
**Status:** Ready for Implementation
**Branch:** TelePay-REFACTOR
**Parent Document:** GCPaymentGateway_REFACTORING_ARCHITECTURE.md

---

## Table of Contents

1. [Phase 0: Pre-Implementation Setup](#phase-0-pre-implementation-setup)
2. [Phase 1: Directory Structure & Core Files](#phase-1-directory-structure--core-files)
3. [Phase 2: Configuration Module](#phase-2-configuration-module)
4. [Phase 3: Database Module](#phase-3-database-module)
5. [Phase 4: Validators Module](#phase-4-validators-module)
6. [Phase 5: Payment Handler Module](#phase-5-payment-handler-module)
7. [Phase 6: Main Service Module](#phase-6-main-service-module)
8. [Phase 7: Containerization](#phase-7-containerization)
9. [Phase 8: Testing](#phase-8-testing)
10. [Phase 9: Deployment](#phase-9-deployment)
11. [Phase 10: Verification & Monitoring](#phase-10-verification--monitoring)
12. [Phase 11: Integration & Rollback Planning](#phase-11-integration--rollback-planning)

---

## Phase 0: Pre-Implementation Setup

### Environment Validation
- [ ] Verify `telepay-459221` project is active
- [ ] Confirm access to `telepaypsql` database instance
- [ ] Verify Secret Manager access with appropriate permissions
- [ ] Check that no conflicting service named `gcpaymentgateway-10-26` exists

### Secret Manager Preparation
- [ ] Verify `nowpayments-api-key` secret exists and is accessible
- [ ] Verify `nowpayments-ipn-url` secret exists and is accessible
- [ ] Verify `database-host` secret exists and is accessible
- [ ] Verify `database-name` secret exists and is accessible
- [ ] Verify `database-user` secret exists and is accessible
- [ ] Verify `database-password` secret exists and is accessible

### Service Account Setup
- [ ] Verify `telepay-cloudrun@telepay-459221.iam.gserviceaccount.com` exists
- [ ] Grant Secret Manager access to service account
  ```bash
  gcloud secrets add-iam-policy-binding nowpayments-api-key \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding nowpayments-ipn-url \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding database-host \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding database-name \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding database-user \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

  gcloud secrets add-iam-policy-binding database-password \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
  ```
- [ ] Grant Cloud SQL Client access to service account
  ```bash
  gcloud projects add-iam-policy-binding telepay-459221 \
    --member="serviceAccount:telepay-cloudrun@telepay-459221.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
  ```

### Database Validation
- [ ] Verify `main_clients_database` table exists in `telepaydb`
- [ ] Confirm required columns exist:
  - `open_channel_id` (TEXT, PRIMARY KEY)
  - `closed_channel_id` (TEXT)
  - `closed_channel_title` (TEXT)
  - `closed_channel_description` (TEXT)
  - `sub_1_price`, `sub_2_price`, `sub_3_price` (DECIMAL)
  - `sub_1_time`, `sub_2_time`, `sub_3_time` (INTEGER)
  - `client_wallet_address` (TEXT)
  - `client_payout_currency` (TEXT)
  - `client_payout_network` (TEXT)
- [ ] Test database connection from Cloud Run environment

---

## Phase 1: Directory Structure & Core Files

### Create Service Directory
- [ ] Navigate to `/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26`
- [ ] Create `GCPaymentGateway-10-26/` directory
- [ ] Verify directory is empty and ready for files

### Create Core Documentation
- [ ] Create `README.md` with service overview
  - Service purpose and responsibilities
  - API endpoints documentation
  - Local development instructions
  - Deployment instructions
  - Integration points
  - Troubleshooting guide

### Verify Modular Structure
- [ ] Confirm plan for 5 separate Python modules:
  1. `service.py` - Main Flask app (route registration only)
  2. `config_manager.py` - Secret Manager operations
  3. `database_manager.py` - Database operations
  4. `validators.py` - Input validation
  5. `payment_handler.py` - NowPayments API integration
- [ ] Ensure no single file exceeds 300 lines of code (maintain modularity)

---

## Phase 2: Configuration Module

### Create `config_manager.py`
- [ ] Create new file: `GCPaymentGateway-10-26/config_manager.py`
- [ ] Implement `ConfigManager` class structure
- [ ] Add docstring with module purpose

### Implement Secret Fetching Methods
- [ ] Implement `__init__()` method
  - Initialize Secret Manager client
  - Initialize empty config dict
- [ ] Implement `fetch_secret()` generic method
  - Accept `env_var_name` and `secret_description` parameters
  - Fetch secret from Secret Manager
  - Handle exceptions gracefully
  - Return secret value or None
  - Add emoji logging (✅ success, ❌ error)
- [ ] Implement `fetch_payment_provider_token()`
  - Call `fetch_secret()` with `PAYMENT_PROVIDER_SECRET_NAME`
  - Return NowPayments API token
- [ ] Implement `fetch_ipn_callback_url()`
  - Call `fetch_secret()` with `NOWPAYMENTS_IPN_CALLBACK_URL`
  - Return IPN callback URL
  - Log warning if not configured
- [ ] Implement `fetch_database_host()`
  - Call `fetch_secret()` with `DATABASE_HOST_SECRET`
  - Raise ValueError if not configured
- [ ] Implement `fetch_database_name()`
  - Call `fetch_secret()` with `DATABASE_NAME_SECRET`
  - Raise ValueError if not configured
- [ ] Implement `fetch_database_user()`
  - Call `fetch_secret()` with `DATABASE_USER_SECRET`
  - Raise ValueError if not configured
- [ ] Implement `fetch_database_password()`
  - Call `fetch_secret()` with `DATABASE_PASSWORD_SECRET`
  - Raise ValueError if not configured

### Implement Configuration Initialization
- [ ] Implement `initialize_config()` method
  - Fetch all secrets using above methods
  - Build config dictionary with:
    - `payment_provider_token`
    - `ipn_callback_url`
    - `database_host`
    - `database_name`
    - `database_user`
    - `database_password`
    - `database_port` (default: 5432)
    - `nowpayments_api_url` (hardcoded)
    - `landing_page_base_url` (hardcoded)
  - Log configuration summary with emojis (🔧 🌐 💰)
  - Return config dictionary
- [ ] Implement `get_config()` method
  - Return current config dictionary

### Validate Module Independence
- [ ] Ensure `config_manager.py` has NO imports from other project modules
- [ ] Only imports: `os`, `google.cloud.secretmanager`, `typing`
- [ ] Confirm module is self-contained and reusable

---

## Phase 3: Database Module

### Create `database_manager.py`
- [ ] Create new file: `GCPaymentGateway-10-26/database_manager.py`
- [ ] Implement `DatabaseManager` class structure
- [ ] Add docstring with module purpose

### Implement Database Connection
- [ ] Implement `__init__()` method
  - Accept `config` dictionary parameter
  - Extract database credentials from config
  - Validate all credentials are present
  - Store credentials as instance variables
  - Log initialization with emoji (✅ success)
- [ ] Implement `get_connection()` method
  - Create psycopg2 connection using credentials
  - Handle connection errors with emoji logging (❌ error)
  - Return connection object
  - Raise exception if connection fails

### Implement Database Query Methods
- [ ] Implement `channel_exists()` method
  - Accept `open_channel_id` parameter
  - Query: `SELECT 1 FROM main_clients_database WHERE open_channel_id = %s LIMIT 1`
  - Return `True` if channel exists, `False` otherwise
  - Close cursor and connection
  - Handle exceptions gracefully
  - Log result with emoji (✅ exists, ⚠️ not found)
- [ ] Implement `fetch_channel_details()` method
  - Accept `open_channel_id` parameter
  - Query all channel fields (15 columns total)
  - Return dictionary with channel details or None
  - Use fallback values for optional fields:
    - `open_channel_title` → "Premium Channel"
    - `closed_channel_title` → "Premium Channel"
    - `closed_channel_description` → "exclusive content"
    - `client_wallet_address` → ""
    - `client_payout_currency` → "USD"
    - `client_payout_network` → ""
  - Close cursor and connection
  - Log result with emoji (✅ found, ⚠️ not found, 🔍 searching)
- [ ] Implement `fetch_closed_channel_id()` method
  - Accept `open_channel_id` parameter
  - Query: `SELECT closed_channel_id FROM main_clients_database WHERE open_channel_id = %s`
  - Return closed channel ID or None
  - Close cursor and connection
  - Log result with emoji (✅ found, ⚠️ not found, 🔍 searching)
- [ ] Implement `fetch_client_wallet_info()` method
  - Accept `open_channel_id` parameter
  - Query: `SELECT client_wallet_address, client_payout_currency, client_payout_network`
  - Return tuple: `(wallet_address, payout_currency, payout_network)` or `(None, None, None)`
  - Close cursor and connection
  - Log result with emoji (💰 found, ⚠️ not found, 🔍 searching)

### Implement Cleanup Method
- [ ] Implement `close()` method
  - Log closure with emoji (🔒 closing)
  - Add comment for future connection pool cleanup

### Validate Module Independence
- [ ] Ensure `database_manager.py` has NO imports from other project modules
- [ ] Only imports: `psycopg2`, `typing`
- [ ] Confirm module is self-contained and reusable

---

## Phase 4: Validators Module

### Create `validators.py`
- [ ] Create new file: `GCPaymentGateway-10-26/validators.py`
- [ ] Add module docstring

### Implement Validation Functions
- [ ] Implement `validate_user_id()` function
  - Accept `user_id` parameter (Any type)
  - Convert to int and check if positive
  - Return True if valid, False otherwise
  - Handle ValueError/TypeError
- [ ] Implement `validate_amount()` function
  - Accept `amount` parameter (Any type)
  - Convert to float
  - Check range: 1.00 <= amount <= 9999.99
  - Check decimal places (max 2)
  - Return True if valid, False otherwise
  - Handle ValueError/TypeError
- [ ] Implement `validate_channel_id()` function
  - Accept `channel_id` parameter (Any type)
  - Check for empty/None
  - Special case: "donation_default" → return True
  - Check if numeric (with optional negative sign)
  - Check max length (15 characters for Telegram IDs)
  - Return True if valid, False otherwise
- [ ] Implement `validate_subscription_time()` function
  - Accept `days` parameter (Any type)
  - Convert to int
  - Check range: 1 <= days <= 999
  - Return True if valid, False otherwise
  - Handle ValueError/TypeError
- [ ] Implement `validate_payment_type()` function
  - Accept `payment_type` parameter (Any type)
  - Check if string
  - Check if value in ["subscription", "donation"] (case-insensitive)
  - Return True if valid, False otherwise

### Implement Sanitization Functions
- [ ] Implement `sanitize_channel_id()` function
  - Accept `channel_id` parameter (str)
  - Special case: "donation_default" → return as-is
  - Check if channel ID starts with negative sign
  - If not negative, prepend "-" and log warning with emoji (⚠️ validation)
  - Log correction with emoji (✅ corrected)
  - Return sanitized channel ID

### Validate Module Independence
- [ ] Ensure `validators.py` has NO imports from other project modules
- [ ] Only imports: `typing`
- [ ] Confirm module is self-contained and reusable

---

## Phase 5: Payment Handler Module

### Create `payment_handler.py`
- [ ] Create new file: `GCPaymentGateway-10-26/payment_handler.py`
- [ ] Implement `PaymentHandler` class structure
- [ ] Add docstring with module purpose
- [ ] Import validators: `from validators import validate_*, sanitize_*`

### Implement Initialization
- [ ] Implement `__init__()` method
  - Accept `config` dictionary and `db_manager` instance
  - Extract payment_token, ipn_callback_url, api_url, landing_page_base_url
  - Store as instance variables
  - Store db_manager reference
  - Validate payment_token exists (raise ValueError if missing)
  - Log warning if IPN callback URL missing (⚠️ warning)
  - Log successful initialization with emoji (✅ success)

### Implement Request Validation
- [ ] Implement `validate_request()` method
  - Accept `data` dictionary parameter
  - Check required fields: ["user_id", "amount", "open_channel_id", "subscription_time_days", "payment_type"]
  - Return tuple: `(is_valid: bool, error_message: str | None)`
  - Validate user_id using `validate_user_id()`
  - Validate amount using `validate_amount()`
  - Validate channel_id using `validate_channel_id()`
  - Validate subscription_time using `validate_subscription_time()`
  - Validate payment_type using `validate_payment_type()`
  - Log validation result with emoji (✅ passed)
  - Return (True, None) if all valid, (False, error_message) otherwise

### Implement Order ID Generation
- [ ] Implement `build_order_id()` method
  - Accept `user_id` and `open_channel_id` parameters
  - Sanitize channel_id using `sanitize_channel_id()`
  - Build order_id: `f"PGP-{user_id}|{sanitized_channel_id}"`
  - Log order_id creation with emoji (📋 order)
  - Log user_id and channel_id details
  - Return order_id string

### Implement Success URL Generation
- [ ] Implement `build_success_url()` method
  - Accept `order_id` parameter
  - URL-encode order_id using `quote(order_id, safe='')`
  - Build success_url: `f"{landing_page_base_url}?order_id={encoded_order_id}"`
  - Log success_url creation with emoji (🔗 link)
  - Return success_url string

### Implement Invoice Payload Creation
- [ ] Implement `create_invoice_payload()` method
  - Accept `data`, `order_id`, `success_url` parameters
  - Build payload dictionary with:
    - `price_amount`: float(data["amount"])
    - `price_currency`: "USD"
    - `order_id`: order_id
    - `order_description`: "Payment-Test-1"
    - `success_url`: success_url
    - `ipn_callback_url`: self.ipn_callback_url
    - `is_fixed_rate`: False
    - `is_fee_paid_by_user`: False
  - Log payload creation with emoji (📋 invoice)
  - Log amount, order_id, IPN status
  - Return payload dictionary

### Implement NowPayments API Call
- [ ] Implement `call_nowpayments_api()` async method
  - Accept `payload` parameter
  - Build headers with x-api-key and Content-Type
  - Log API call with emoji (🌐 api)
  - Use httpx.AsyncClient with 30s timeout
  - POST to self.api_url with headers and JSON payload
  - Handle 200 response:
    - Parse JSON response
    - Extract invoice_id and invoice_url
    - Log success with emoji (✅ success)
    - Return {"success": True, "status_code": 200, "data": response_data}
  - Handle non-200 response:
    - Log error with emoji (❌ error)
    - Log status code and response text
    - Return {"success": False, "status_code": status_code, "error": resp.text}
  - Handle httpx.TimeoutException:
    - Log timeout with emoji (❌ timeout)
    - Return {"success": False, "error": "Request timeout - NowPayments API did not respond"}
  - Handle generic Exception:
    - Log error with emoji (❌ error)
    - Return {"success": False, "error": f"Request failed: {str(e)}"}

### Implement Main Invoice Creation Method
- [ ] Implement `create_invoice()` method (synchronous wrapper)
  - Accept `request_data` dictionary parameter
  - Log invoice creation start with emoji (💳 payment)
  - Step 1: Validate request using `validate_request()`
    - If invalid, return error response with status_code 400
  - Step 2: Extract data fields (user_id, amount, open_channel_id, etc.)
  - Step 3: Check for provided order_id or generate new one
    - If provided, log usage with emoji (📋 order)
    - If not provided, call `build_order_id()`
  - Step 4: Validate channel exists (unless "donation_default")
    - Sanitize channel_id using `sanitize_channel_id()`
    - Call `db_manager.channel_exists()`
    - If not exists, return error response with status_code 404
    - Fetch channel details for logging using `db_manager.fetch_channel_details()`
    - Log channel title with emoji (🏷️ channel)
  - Step 5: Build success URL using `build_success_url()`
  - Step 6: Create invoice payload using `create_invoice_payload()`
  - Step 7: Call NowPayments API asynchronously
    - Create new asyncio event loop
    - Run `call_nowpayments_api()` with loop.run_until_complete()
    - Close loop
  - Step 8: Return response
    - If success, return {"success": True, "invoice_id", "invoice_url", "order_id", "status_code": 200}
    - If failure, return {"success": False, "error", "status_code"}

### Validate Module Dependencies
- [ ] Ensure `payment_handler.py` only imports:
  - `httpx` (external)
  - `typing` (stdlib)
  - `urllib.parse` (stdlib)
  - `validators` (project module - self-contained)
- [ ] Ensure NO imports from `database_manager`, `config_manager`, or `service`
- [ ] Confirm db_manager is passed as dependency injection

---

## Phase 6: Main Service Module

### Create `service.py`
- [ ] Create new file: `GCPaymentGateway-10-26/service.py`
- [ ] Add shebang: `#!/usr/bin/env python`
- [ ] Add module docstring with:
  - Service name: GCPaymentGateway-10-26
  - Purpose: Self-contained payment invoice creation service
  - Replaces: TelePay10-26/start_np_gateway.py
- [ ] Import dependencies:
  - `from flask import Flask, request, jsonify`
  - `from config_manager import ConfigManager`
  - `from database_manager import DatabaseManager`
  - `from payment_handler import PaymentHandler`
  - `import sys`

### Implement Application Factory
- [ ] Implement `create_app()` function
  - Add docstring explaining application factory pattern
  - Create Flask app instance
  - Log initialization with emoji (🚀 gateway)
  - Initialize ConfigManager
    - Call `config_manager.initialize_config()`
    - Update app.config with returned config
    - Log success with emoji (✅ config)
    - Handle exceptions and sys.exit(1) on failure
  - Initialize DatabaseManager
    - Pass config to DatabaseManager constructor
    - Store as app.db
    - Log success with emoji (✅ database)
    - Handle exceptions and sys.exit(1) on failure
  - Initialize PaymentHandler
    - Pass config and db_manager to PaymentHandler constructor
    - Store as app.payment_handler
    - Log success with emoji (✅ payment)
    - Handle exceptions and sys.exit(1) on failure
  - Call `register_routes(app)`
  - Log final success with emoji (✅ gateway ready)
  - Return app instance

### Implement Route Registration
- [ ] Implement `register_routes()` function
  - Accept `app` parameter (Flask instance)
  - Add docstring explaining route registration

### Implement Health Check Endpoint
- [ ] Create `/health` GET route
  - Add docstring explaining health check purpose
  - Return JSON: `{"status": "healthy", "service": "gcpaymentgateway-10-26"}`
  - Return HTTP 200 status code

### Implement Invoice Creation Endpoint
- [ ] Create `/create-invoice` POST route
  - Add comprehensive docstring with:
    - Purpose
    - Request JSON schema
    - Response JSON schema
  - Log request receipt with emoji (💳 gateway)
  - Parse JSON data from request
    - Handle missing JSON data (return 400 error)
    - Handle JSON parse errors (return 400 error)
    - Log parsing errors with emoji (❌ error)
  - Log request details with emoji (📋 gateway):
    - User ID
    - Amount
    - Channel ID
    - Payment Type
    - Subscription Days
  - Call `app.payment_handler.create_invoice(data)`
    - Handle exceptions with try/catch
    - Log unexpected errors with emoji (❌ error)
  - If success:
    - Log success with emoji (✅ gateway)
    - Log invoice_id and order_id
    - Return JSON response with HTTP 200
  - If failure:
    - Log failure with emoji (❌ gateway)
    - Return JSON response with appropriate status code

### Implement Main Entry Point
- [ ] Create `if __name__ == "__main__"` block
  - Import `os` module
  - Call `create_app()` to get app instance
  - Get PORT from environment (default 8080)
  - Log server start with emoji (🌐 gateway)
  - Run app with:
    - host="0.0.0.0"
    - port=port
    - debug=False

### Validate Service Module
- [ ] Ensure `service.py` is ONLY responsible for:
  - Flask app creation
  - Route registration
  - Request/response handling
  - Logging
- [ ] NO business logic in service.py (all delegated to modules)
- [ ] Confirm proper dependency injection (config, db_manager, payment_handler)

---

## Phase 7: Containerization

### Create `requirements.txt`
- [ ] Create new file: `GCPaymentGateway-10-26/requirements.txt`
- [ ] Add dependencies with specific versions:
  - Flask==3.0.0
  - httpx==0.25.2
  - psycopg2-binary==2.9.9
  - google-cloud-secret-manager==2.16.4
  - gunicorn==21.2.0
- [ ] Add comments for each dependency explaining purpose

### Create `Dockerfile`
- [ ] Create new file: `GCPaymentGateway-10-26/Dockerfile`
- [ ] Use base image: `python:3.11-slim`
- [ ] Set working directory: `/app`
- [ ] Install system dependencies:
  - gcc (for psycopg2 compilation)
  - postgresql-client (for debugging)
  - libpq-dev (for psycopg2)
- [ ] Clean up apt cache to reduce image size
- [ ] Copy `requirements.txt` first (for layer caching)
- [ ] Install Python dependencies with `pip install --no-cache-dir`
- [ ] Copy all Python modules:
  - service.py
  - config_manager.py
  - database_manager.py
  - payment_handler.py
  - validators.py
- [ ] Expose port 8080
- [ ] Set environment variable: `PYTHONUNBUFFERED=1`
- [ ] Set CMD to run gunicorn:
  - Bind to $PORT (Cloud Run sets this)
  - 1 worker (sufficient for stateless service)
  - 8 threads (handle concurrent requests)
  - 60s timeout
  - Module: `service:create_app()`

### Create `.dockerignore`
- [ ] Create new file: `GCPaymentGateway-10-26/.dockerignore`
- [ ] Add patterns to exclude:
  - `__pycache__/`
  - `*.pyc`, `*.pyo`, `*.pyd`
  - `.Python`
  - `*.so`, `*.egg`, `*.egg-info/`
  - `dist/`, `build/`
  - `.git/`, `.gitignore`
  - `README.md`
  - `.env`, `.venv/`, `venv/`
  - `*.md` (exclude all markdown)
  - `tests/`, `.pytest_cache/`

### Validate Container Structure
- [ ] Verify all required files are present in directory
- [ ] Verify no unnecessary files will be included in image
- [ ] Confirm Dockerfile follows Cloud Run best practices

---

## Phase 8: Testing

### Create Test Directory
- [ ] Create `GCPaymentGateway-10-26/tests/` directory
- [ ] Create `tests/__init__.py` (empty file)

### Unit Tests: Validators
- [ ] Create `tests/test_validators.py`
- [ ] Test `validate_user_id()`:
  - Valid cases: positive integers, string integers
  - Invalid cases: negative numbers, strings, None
- [ ] Test `validate_amount()`:
  - Valid cases: 1.00, 9.99, 9999.99
  - Invalid cases: 0.99 (too low), 10000.00 (too high), invalid strings, excessive decimals
- [ ] Test `validate_channel_id()`:
  - Valid cases: negative IDs, "donation_default"
  - Invalid cases: empty string, non-numeric, None, too long
- [ ] Test `validate_subscription_time()`:
  - Valid cases: 1, 30, 999
  - Invalid cases: 0, 1000, strings, None
- [ ] Test `validate_payment_type()`:
  - Valid cases: "subscription", "donation" (case-insensitive)
  - Invalid cases: invalid strings, numbers, None
- [ ] Test `sanitize_channel_id()`:
  - Test auto-correction of positive IDs to negative
  - Test "donation_default" passthrough
  - Test already-negative IDs remain unchanged

### Unit Tests: Config Manager
- [ ] Create `tests/test_config_manager.py`
- [ ] Mock Secret Manager client
- [ ] Test `fetch_secret()` success case
- [ ] Test `fetch_secret()` failure case (missing env var)
- [ ] Test `fetch_secret()` exception handling
- [ ] Test `initialize_config()` with all secrets available
- [ ] Test `initialize_config()` with missing critical secrets

### Unit Tests: Database Manager
- [ ] Create `tests/test_database_manager.py`
- [ ] Mock psycopg2 connection
- [ ] Test `channel_exists()` for existing channel
- [ ] Test `channel_exists()` for non-existing channel
- [ ] Test `fetch_channel_details()` success case
- [ ] Test `fetch_channel_details()` with fallback values
- [ ] Test `fetch_closed_channel_id()` success case
- [ ] Test `fetch_client_wallet_info()` success case

### Unit Tests: Payment Handler
- [ ] Create `tests/test_payment_handler.py`
- [ ] Mock httpx client
- [ ] Mock DatabaseManager
- [ ] Test `validate_request()` with valid data
- [ ] Test `validate_request()` with invalid data
- [ ] Test `build_order_id()` format
- [ ] Test `build_success_url()` encoding
- [ ] Test `create_invoice_payload()` structure
- [ ] Test `call_nowpayments_api()` success response
- [ ] Test `call_nowpayments_api()` error response
- [ ] Test `call_nowpayments_api()` timeout handling

### Integration Tests: Full Flow
- [ ] Create `tests/test_integration.py`
- [ ] Test health check endpoint
- [ ] Test create-invoice endpoint with valid data
- [ ] Test create-invoice endpoint with invalid amount
- [ ] Test create-invoice endpoint with missing fields
- [ ] Test create-invoice endpoint with non-existent channel
- [ ] Test create-invoice endpoint with "donation_default"

### Run Tests
- [ ] Install pytest: `pip install pytest pytest-asyncio`
- [ ] Run unit tests: `pytest tests/test_validators.py -v`
- [ ] Run unit tests: `pytest tests/test_config_manager.py -v`
- [ ] Run unit tests: `pytest tests/test_database_manager.py -v`
- [ ] Run unit tests: `pytest tests/test_payment_handler.py -v`
- [ ] Run all unit tests: `pytest tests/ -v`
- [ ] Verify all tests pass before deployment

---

## Phase 9: Deployment

### Pre-Deployment Validation
- [ ] Verify all files are created in `GCPaymentGateway-10-26/`
- [ ] Verify no syntax errors in Python files: `python -m py_compile *.py`
- [ ] Verify requirements.txt has all dependencies
- [ ] Verify Dockerfile builds successfully (optional local test)
- [ ] Review Cloud Logging to ensure no conflicting service names

### Deploy to Cloud Run
- [ ] Navigate to service directory:
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCPaymentGateway-10-26
  ```
- [ ] Deploy service with gcloud command:
  ```bash
  gcloud run deploy gcpaymentgateway-10-26 \
    --source=. \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="PAYMENT_PROVIDER_SECRET_NAME=projects/telepay-459221/secrets/nowpayments-api-key/versions/latest" \
    --set-env-vars="NOWPAYMENTS_IPN_CALLBACK_URL=projects/telepay-459221/secrets/nowpayments-ipn-url/versions/latest" \
    --set-env-vars="DATABASE_HOST_SECRET=projects/telepay-459221/secrets/database-host/versions/latest" \
    --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest" \
    --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest" \
    --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest" \
    --service-account=telepay-cloudrun@telepay-459221.iam.gserviceaccount.com \
    --min-instances=0 \
    --max-instances=5 \
    --memory=256Mi \
    --cpu=1 \
    --timeout=60s \
    --concurrency=80
  ```
- [ ] Wait for deployment to complete (watch for success message)
- [ ] Note the service URL returned by gcloud
- [ ] Verify deployment in Cloud Console

### Post-Deployment Validation
- [ ] Verify service shows as "healthy" in Cloud Console
- [ ] Check Cloud Logging for initialization logs:
  - Look for "🚀 [GATEWAY] Initializing"
  - Look for "✅ [CONFIG] Configuration loaded successfully"
  - Look for "✅ [DATABASE] Database manager initialized"
  - Look for "✅ [PAYMENT] Payment handler initialized"
  - Look for "✅ [GATEWAY] GCPaymentGateway-10-26 ready to accept requests"
- [ ] Verify no error logs in Cloud Logging

---

## Phase 10: Verification & Monitoring

### Health Check Verification
- [ ] Get service URL:
  ```bash
  SERVICE_URL=$(gcloud run services describe gcpaymentgateway-10-26 \
    --region=us-central1 \
    --format='value(status.url)')
  echo "Service URL: $SERVICE_URL"
  ```
- [ ] Test health endpoint:
  ```bash
  curl -X GET "$SERVICE_URL/health"
  ```
- [ ] Verify response: `{"status": "healthy", "service": "gcpaymentgateway-10-26"}`

### Invoice Creation Verification (Test Environment)
- [ ] Prepare test request with valid test channel:
  ```bash
  curl -X POST "$SERVICE_URL/create-invoice" \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 6271402111,
      "amount": 9.99,
      "open_channel_id": "-1003268562225",
      "subscription_time_days": 30,
      "payment_type": "subscription",
      "tier": 1
    }'
  ```
- [ ] Verify success response contains:
  - `"success": true`
  - `"invoice_id"` (NowPayments invoice ID)
  - `"invoice_url"` (NowPayments payment URL)
  - `"order_id"` (format: "PGP-{user_id}|{channel_id}")
  - `"status_code": 200`
- [ ] Test the invoice_url in browser to ensure it loads NowPayments page

### Error Handling Verification
- [ ] Test invalid amount:
  ```bash
  curl -X POST "$SERVICE_URL/create-invoice" \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 6271402111,
      "amount": 0.50,
      "open_channel_id": "-1003268562225",
      "subscription_time_days": 30,
      "payment_type": "subscription"
    }'
  ```
- [ ] Verify error response: `"error": "Invalid amount"`, status_code 400
- [ ] Test non-existent channel:
  ```bash
  curl -X POST "$SERVICE_URL/create-invoice" \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 6271402111,
      "amount": 9.99,
      "open_channel_id": "-9999999999999",
      "subscription_time_days": 30,
      "payment_type": "subscription"
    }'
  ```
- [ ] Verify error response: `"error": "Channel ... not found"`, status_code 404
- [ ] Test missing required field:
  ```bash
  curl -X POST "$SERVICE_URL/create-invoice" \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": 6271402111,
      "open_channel_id": "-1003268562225",
      "subscription_time_days": 30,
      "payment_type": "subscription"
    }'
  ```
- [ ] Verify error response: `"error": "Missing required field: amount"`, status_code 400

### Cloud Logging Verification
- [ ] View all service logs in Cloud Console:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcpaymentgateway-10-26"
  ```
- [ ] Verify logs show emoji-based logging (💳 📋 ✅ ❌ 🔍 ⚠️ 🌐)
- [ ] Check for initialization logs on container start
- [ ] Check for request logs showing invoice creation flow
- [ ] Verify database query logs are present
- [ ] Verify NowPayments API call logs are present

### Monitoring Setup
- [ ] Create Cloud Monitoring dashboard for gcpaymentgateway-10-26
- [ ] Add widget: Request count (invocations per minute)
- [ ] Add widget: Error rate (4xx and 5xx responses)
- [ ] Add widget: Latency (p50, p95, p99)
- [ ] Add widget: Container instance count
- [ ] Add widget: Memory utilization
- [ ] Add widget: CPU utilization

### Alerting Setup
- [ ] Create alerting policy: Error rate > 5% for 5 minutes
- [ ] Create alerting policy: Latency p95 > 3 seconds
- [ ] Create alerting policy: Container crashes > 2 in 10 minutes
- [ ] Create alerting policy: NowPayments API error rate > 10%
- [ ] Configure notification channels (email, Slack, etc.)

---

## Phase 11: Integration & Rollback Planning

### Integration Planning
- [ ] Document service URL for integration with upstream services
- [ ] Provide API documentation to teams needing to call the service
- [ ] Create example curl commands for integration testing
- [ ] Update TelePay10-26 bot to use new service (future task)
- [ ] Update GCBotCommand to call new service (future task)
- [ ] Update GCDonationHandler to call new service (future task)

### Rollback Preparation
- [ ] Document rollback procedure in README.md
- [ ] Verify TelePay10-26 bot is still running (fallback option)
- [ ] Create rollback script:
  ```bash
  # Scale down new service
  gcloud run services update gcpaymentgateway-10-26 \
    --region=us-central1 \
    --min-instances=0 \
    --max-instances=0

  # Ensure old bot is running
  gcloud run services update tph10-26 \
    --region=us-central1 \
    --min-instances=1
  ```
- [ ] Test rollback procedure in staging environment (if available)

### Documentation Updates
- [ ] Update PROGRESS.md with implementation summary
- [ ] Update DECISIONS.md with architectural decisions made
- [ ] Update BUGS.md if any issues encountered during implementation
- [ ] Create service-specific README.md in GCPaymentGateway-10-26/
- [ ] Document API endpoints and request/response formats
- [ ] Document error codes and troubleshooting steps

---

## Phase 12: Final Validation

### Code Quality Checks
- [ ] Verify all modules follow PEP 8 style guide
- [ ] Confirm all functions have docstrings
- [ ] Ensure proper error handling in all modules
- [ ] Verify emoji logging is consistent across all modules
- [ ] Check that no hardcoded secrets exist in code

### Module Independence Verification
- [ ] Confirm `config_manager.py` imports only: `os`, `google.cloud.secretmanager`, `typing`
- [ ] Confirm `database_manager.py` imports only: `psycopg2`, `typing`
- [ ] Confirm `validators.py` imports only: `typing`
- [ ] Confirm `payment_handler.py` imports only: `httpx`, `typing`, `urllib.parse`, `validators`
- [ ] Confirm `service.py` imports only: `flask`, `config_manager`, `database_manager`, `payment_handler`, `sys`
- [ ] Verify no circular imports exist

### Deployment Checklist Review
- [ ] All 5 Python modules created and tested independently
- [ ] Dockerfile builds successfully
- [ ] Service deploys to Cloud Run without errors
- [ ] Health check endpoint responds correctly
- [ ] Invoice creation endpoint works with valid data
- [ ] Error handling returns appropriate status codes
- [ ] Cloud Logging shows proper emoji-based logs
- [ ] Monitoring dashboard is set up
- [ ] Alerting policies are configured
- [ ] Documentation is complete

### Modular Structure Validation
- [ ] Verify no single file exceeds 300 lines (excluding comments/docstrings)
- [ ] Confirm each module has a single, well-defined responsibility:
  - `config_manager.py` → Secret management only
  - `database_manager.py` → Database operations only
  - `validators.py` → Input validation only
  - `payment_handler.py` → NowPayments API integration only
  - `service.py` → Flask routing and coordination only
- [ ] Ensure no business logic leaks into `service.py`
- [ ] Verify proper separation of concerns

---

## Success Criteria

✅ **Service is deployed and healthy**
✅ **All endpoints respond correctly**
✅ **Error handling works as expected**
✅ **Logging is comprehensive and emoji-based**
✅ **Monitoring and alerting are configured**
✅ **All modules are independent and self-contained**
✅ **No single file contains multiple responsibilities**
✅ **Integration documentation is complete**
✅ **Rollback procedure is documented and tested**
✅ **All tests pass successfully**

---

**Implementation Status:** NOT STARTED
**Next Action:** Begin Phase 0 - Pre-Implementation Setup
**Estimated Time:** 4-6 hours for complete implementation
**Risk Level:** LOW (architecture is well-defined, modular structure reduces complexity)
