# Notification Management Architecture - Implementation Checklist

**Architecture Document:** NOTIFICATION_MANAGEMENT_ARCHITECTURE.md
**Created:** 2025-11-11
**Status:** Ready for Implementation

---

## Overview

This checklist breaks down the implementation of the Notification Management feature into modular, testable tasks. Each section corresponds to a specific module/component to ensure proper code organization and maintainability.

**Feature Summary:** Enable channel owners to receive real-time Telegram notifications when customers complete subscription or donation payments (only after NowPayments IPN confirms `status: finished`).

---

## Table of Contents

1. [Database Layer](#1-database-layer)
2. [Backend API Layer - Models](#2-backend-api-layer---models)
3. [Backend API Layer - Services](#3-backend-api-layer---services)
4. [Backend API Layer - Routes](#4-backend-api-layer---routes)
5. [TelePay Bot - Database Manager](#5-telepay-bot---database-manager)
6. [TelePay Bot - Notification Service Module](#6-telepay-bot---notification-service-module)
7. [TelePay Bot - Notification API Endpoint](#7-telepay-bot---notification-api-endpoint)
8. [TelePay Bot - App Initialization](#8-telepay-bot---app-initialization)
9. [NowPayments IPN Handler](#9-nowpayments-ipn-handler)
10. [Frontend - TypeScript Types](#10-frontend---typescript-types)
11. [Frontend - UI Components](#11-frontend---ui-components)
12. [Frontend - Registration Page](#12-frontend---registration-page)
13. [Frontend - Edit Page](#13-frontend---edit-page)
14. [Testing](#14-testing)
15. [Deployment](#15-deployment)
16. [Verification](#16-verification)

---

## 1. Database Layer

**Module:** PostgreSQL Schema (`telepaypsql` database)

### 1.1 Create Migration Script

- [ ] Create file: `TOOLS_SCRIPTS_TESTS/scripts/add_notification_columns.sql`
  - [ ] Add `notification_status` column (BOOLEAN, DEFAULT false, NOT NULL)
  - [ ] Add `notification_id` column (BIGINT, DEFAULT NULL)
  - [ ] Add column comments for documentation
  - [ ] Add verification queries to confirm columns exist
  - [ ] Wrap in transaction (BEGIN...COMMIT)

### 1.2 Create Rollback Script

- [ ] Create file: `TOOLS_SCRIPTS_TESTS/scripts/rollback_notification_columns.sql`
  - [ ] Drop `notification_status` column (IF EXISTS)
  - [ ] Drop `notification_id` column (IF EXISTS)
  - [ ] Wrap in transaction

### 1.3 Create Migration Execution Script

- [ ] Create file: `TOOLS_SCRIPTS_TESTS/tools/execute_notification_migration.py`
  - [ ] Import required libraries (psycopg2, google.cloud.sql.connector)
  - [ ] Implement `get_db_connection()` function
  - [ ] Implement `execute_migration()` function
  - [ ] Read SQL from `add_notification_columns.sql`
  - [ ] Execute migration with error handling
  - [ ] Add success/failure logging with emojis

### 1.4 Optional: Add Database Constraint

- [ ] Consider adding CHECK constraint for consistency:
  ```sql
  CHECK (
    (notification_status = false) OR
    (notification_status = true AND notification_id IS NOT NULL)
  )
  ```
- [ ] Document decision in DECISIONS.md

### 1.5 Execute Migration (When Ready)

- [ ] Backup database before migration
- [ ] Run: `python3 execute_notification_migration.py`
- [ ] Verify columns added successfully
- [ ] Test rollback script (on test database)
- [ ] Update PROGRESS.md

**Validation:**
- [ ] Query `information_schema.columns` to verify new columns exist
- [ ] Verify default values: `notification_status = false`, `notification_id = NULL`

---

## 2. Backend API Layer - Models

**Module:** `GCRegisterAPI-10-26/api/models/channel.py`

### 2.1 Update ChannelRegistrationRequest Model

- [ ] Add new fields to `ChannelRegistrationRequest` class (line ~40):
  - [ ] `notification_status: bool = False`
  - [ ] `notification_id: Optional[int] = None`

### 2.2 Add Notification ID Validator

- [ ] Create `@field_validator('notification_id')` method
  - [ ] Access `notification_status` from `info.data`
  - [ ] If `notification_status = True`:
    - [ ] Validate `notification_id` is not None
    - [ ] Validate `notification_id > 0`
    - [ ] Validate length between 5-15 digits
  - [ ] Return validated value
  - [ ] Add comprehensive error messages

### 2.3 Update ChannelUpdateRequest Model

- [ ] Add optional fields to `ChannelUpdateRequest` class (line ~120):
  - [ ] `notification_status: Optional[bool] = None`
  - [ ] `notification_id: Optional[int] = None`

### 2.4 Add Validator for Updates

- [ ] Create `@field_validator('notification_id')` for update model
  - [ ] Only validate if `notification_status` is being set to `True`
  - [ ] Validate format when provided (same rules as registration)

### 2.5 Update ChannelResponse Model

- [ ] Add fields to `ChannelResponse` class (line ~160):
  - [ ] `notification_status: bool`
  - [ ] `notification_id: Optional[int]`

**Validation:**
- [ ] Test model validation with pytest
- [ ] Test case: `notification_status=True` with `notification_id=None` → Should fail
- [ ] Test case: `notification_status=False` with `notification_id=None` → Should pass
- [ ] Test case: Valid Telegram ID → Should pass
- [ ] Test case: Invalid Telegram ID (too short/long) → Should fail

---

## 3. Backend API Layer - Services

**Module:** `GCRegisterAPI-10-26/api/services/channel_service.py`

### 3.1 Update register_channel Method

- [ ] Locate `register_channel` method (line ~36)
- [ ] Update INSERT query to include new columns:
  - [ ] Add `notification_status` to column list
  - [ ] Add `notification_id` to column list
- [ ] Update VALUES to include new parameters:
  - [ ] Add `channel_data.notification_status`
  - [ ] Add `channel_data.notification_id`
- [ ] Update success log message to mention notification settings

### 3.2 Update get_user_channels Method

- [ ] Locate `get_user_channels` method (line ~123)
- [ ] Update SELECT query to include new columns:
  - [ ] Add `notification_status` to SELECT
  - [ ] Add `notification_id` to SELECT
- [ ] Update result dictionary to include new fields:
  - [ ] `'notification_status': row[18]`
  - [ ] `'notification_id': row[19]`
- [ ] Update array indices for correct column mapping

### 3.3 Update get_channel_by_id Method

- [ ] Locate `get_channel_by_id` method (line ~200)
- [ ] Update SELECT query to include new columns
- [ ] Update result dictionary to include new fields
- [ ] Update array indices for correct column mapping

### 3.4 Update update_channel Method

- [ ] Locate `update_channel` method (line ~276)
- [ ] Verify dynamic UPDATE handles notification fields
  - [ ] Confirm `model_dump(exclude_none=True)` includes notification fields
  - [ ] No explicit changes needed (already dynamic)
- [ ] Update success log message

**Validation:**
- [ ] Test registration with notifications enabled
- [ ] Test registration with notifications disabled
- [ ] Test retrieval of channels with notification settings
- [ ] Test update of notification settings

---

## 4. Backend API Layer - Routes

**Module:** `GCRegisterAPI-10-26/api/routes/channels.py`

### 4.1 Verify Routes Handle New Fields

- [ ] Review registration endpoint (`POST /channels/register`)
  - [ ] Confirm accepts `ChannelRegistrationRequest`
  - [ ] No explicit changes needed (Pydantic handles validation)

- [ ] Review channels list endpoint (`GET /channels`)
  - [ ] Confirm returns `ChannelResponse` with new fields
  - [ ] No explicit changes needed

- [ ] Review channel update endpoint (`PUT /channels/{channel_id}`)
  - [ ] Confirm accepts `ChannelUpdateRequest`
  - [ ] No explicit changes needed

### 4.2 Add API Documentation Comments

- [ ] Update docstrings to document new fields
- [ ] Document validation rules for `notification_id`

**Validation:**
- [ ] Test endpoints with Postman/curl
- [ ] Verify request validation works
- [ ] Verify response includes new fields

---

## 5. TelePay Bot - Database Manager

**Module:** `TelePay10-26/database.py`

### 5.1 Add get_notification_settings Method

- [ ] Create new method around line ~370
- [ ] Method signature: `get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]`
- [ ] Implementation:
  - [ ] Get database connection
  - [ ] Execute SELECT query for `notification_status`, `notification_id`
  - [ ] Filter by `open_channel_id`
  - [ ] Return tuple if found, None otherwise
  - [ ] Close cursor and connection
  - [ ] Add logging with emojis (✅, ⚠️, ❌)
  - [ ] Handle exceptions gracefully

### 5.2 Add Comprehensive Docstring

- [ ] Add docstring with:
  - [ ] Args description
  - [ ] Returns description
  - [ ] Example usage
  - [ ] Note about error handling

**Validation:**
- [ ] Test method with existing channel (notifications enabled)
- [ ] Test method with existing channel (notifications disabled)
- [ ] Test method with non-existent channel
- [ ] Verify logging output

---

## 6. TelePay Bot - Notification Service Module

**Module:** `TelePay10-26/notification_service.py` (NEW FILE)

### 6.1 Create Module File

- [ ] Create new file: `TelePay10-26/notification_service.py`
- [ ] Add module docstring with emoji

### 6.2 Add Imports

- [ ] `from typing import Optional, Dict, Any`
- [ ] `from telegram import Bot`
- [ ] `from telegram.error import TelegramError, Forbidden, BadRequest`
- [ ] `import asyncio`
- [ ] `from datetime import datetime`

### 6.3 Implement NotificationService Class

- [ ] Create class: `NotificationService`
- [ ] Add class docstring

### 6.4 Implement __init__ Method

- [ ] Parameters: `bot: Bot`, `db_manager`
- [ ] Store bot instance
- [ ] Store db_manager instance
- [ ] Print initialization log with emoji

### 6.5 Implement send_payment_notification Method

- [ ] Method signature: `async def send_payment_notification(self, open_channel_id: str, payment_type: str, payment_data: Dict[str, Any]) -> bool`
- [ ] Add comprehensive docstring with all parameters
- [ ] Implementation steps:
  1. [ ] Log notification request received
  2. [ ] Fetch notification settings via `db_manager.get_notification_settings()`
  3. [ ] Check if settings exist, return False if not
  4. [ ] Check if `notification_status = True`, return False if disabled
  5. [ ] Check if `notification_id` exists, return False if None
  6. [ ] Format message via `_format_notification_message()`
  7. [ ] Send message via `_send_telegram_message()`
  8. [ ] Log success/failure
  9. [ ] Return True on success, False on failure
  10. [ ] Wrap in try-except with traceback logging

### 6.6 Implement _format_notification_message Method

- [ ] Method signature: `def _format_notification_message(self, open_channel_id: str, payment_type: str, payment_data: Dict[str, Any]) -> str`
- [ ] Fetch channel title via `db_manager.get_channel_details_by_open_id()`
- [ ] Extract common fields from `payment_data`:
  - [ ] `user_id`, `username`, `amount_crypto`, `amount_usd`, `crypto_currency`, `timestamp`
- [ ] Format user display (with/without username)
- [ ] **If payment_type == 'subscription':**
  - [ ] Extract: `tier`, `tier_price`, `duration_days`
  - [ ] Format subscription notification with emoji 🎉
  - [ ] Include: channel info, customer info, subscription details, payment amount, timestamp
- [ ] **If payment_type == 'donation':**
  - [ ] Format donation notification with emoji 💝
  - [ ] Include: channel info, donor info, donation amount, timestamp, thank you message
- [ ] **Else (fallback):**
  - [ ] Format generic payment notification with emoji 💳
- [ ] Return formatted HTML message string

### 6.7 Implement _send_telegram_message Method

- [ ] Method signature: `async def _send_telegram_message(self, chat_id: int, message: str) -> bool`
- [ ] Add docstring with error types explained
- [ ] Implementation:
  - [ ] Log sending attempt
  - [ ] Call `bot.send_message()` with:
    - [ ] `chat_id=chat_id`
    - [ ] `text=message`
    - [ ] `parse_mode='HTML'`
    - [ ] `disable_web_page_preview=True`
  - [ ] Log success
  - [ ] Return True
- [ ] Exception handling:
  - [ ] `except Forbidden`: Log "Bot blocked by user", return False
  - [ ] `except BadRequest`: Log "Invalid request", return False
  - [ ] `except TelegramError`: Log "Telegram API error", return False
  - [ ] `except Exception`: Log unexpected error with traceback, return False

### 6.8 Implement test_notification Method (Optional)

- [ ] Method signature: `async def test_notification(self, chat_id: int, channel_title: str = "Test Channel") -> bool`
- [ ] Format test message with emoji 🧪
- [ ] Call `_send_telegram_message()`
- [ ] Return result

**Validation:**
- [ ] Unit test for each method
- [ ] Test subscription notification formatting
- [ ] Test donation notification formatting
- [ ] Test bot blocked scenario
- [ ] Test invalid chat_id scenario

---

## 7. TelePay Bot - Notification API Endpoint

**Module:** `TelePay10-26/notification_api.py` (NEW FILE - Optional) OR integrate into existing bot

### Option A: Separate Flask App (Recommended for clarity)

#### 7.1 Create Module File

- [ ] Create new file: `TelePay10-26/notification_api.py`
- [ ] Add module docstring

#### 7.2 Add Imports

- [ ] `from flask import Flask, request, jsonify`
- [ ] `import asyncio`
- [ ] Import notification_service

#### 7.3 Initialize Flask App

- [ ] `app = Flask(__name__)`
- [ ] Initialize `notification_service = None` (set during startup)

#### 7.4 Implement /send-notification Endpoint

- [ ] Route: `@app.route('/send-notification', methods=['POST'])`
- [ ] Handler: `def handle_notification_request():`
- [ ] Implementation:
  1. [ ] Get JSON from request
  2. [ ] Log received request with emoji
  3. [ ] Validate required fields: `open_channel_id`, `payment_type`, `payment_data`
  4. [ ] Return 400 if missing fields
  5. [ ] Create event loop
  6. [ ] Call `notification_service.send_payment_notification()` asynchronously
  7. [ ] Close loop
  8. [ ] Return 200 with success/failed status
  9. [ ] Wrap in try-except, return 500 on error

#### 7.5 Add Health Check Endpoint

- [ ] Route: `@app.route('/health', methods=['GET'])`
- [ ] Return service status

### Option B: Integrate into Existing Bot

#### 7.6 Add Endpoint to telepay10-26.py

- [ ] Add Flask route or similar endpoint
- [ ] Follow same implementation as Option A

**Validation:**
- [ ] Test endpoint with curl/Postman
- [ ] Test with valid payload
- [ ] Test with missing fields
- [ ] Test with invalid channel ID

---

## 8. TelePay Bot - App Initialization

**Module:** `TelePay10-26/app_initializer.py` OR `TelePay10-26/telepay10-26.py`

### 8.1 Import Notification Service

- [ ] Add import: `from notification_service import NotificationService`

### 8.2 Initialize Notification Service During Startup

- [ ] Locate bot initialization function
- [ ] After bot instance created:
  - [ ] Create Bot instance if not already available
  - [ ] Pass bot and db_manager to NotificationService
  - [ ] `notification_service = NotificationService(bot, db_manager)`
  - [ ] Log initialization success
  - [ ] Store in application context (if using Flask/similar)

### 8.3 Make Service Available Globally

- [ ] Store in `bot_data` or similar context
- [ ] Ensure accessible from notification endpoint

**Validation:**
- [ ] Start bot and verify notification service initializes
- [ ] Check logs for initialization message

---

## 9. NowPayments IPN Handler

**Module:** `np-webhook-10-26/app.py`

### 9.1 Add Configuration for TelePay Bot URL

- [ ] Add environment variable: `TELEPAY_BOT_URL`
- [ ] Load from Secret Manager (around line 60)
- [ ] Add to configuration logging

### 9.2 Add Notification Trigger Logic

- [ ] Locate after successful GCWebhook1 enqueue (around line 890)
- [ ] Add new section with comment: `# Notification Trigger`

#### 9.2.1 Determine Payment Type

- [ ] Check if payment is subscription or donation
- [ ] Logic: Check subscription time or order_id pattern
- [ ] Default to 'subscription'

#### 9.2.2 Prepare Notification Payload

- [ ] Create dictionary with:
  - [ ] `open_channel_id`
  - [ ] `payment_type`
  - [ ] `payment_data` dict with:
    - [ ] `user_id`, `username`, `amount_crypto`, `amount_usd`, `crypto_currency`, `timestamp`
    - [ ] For subscriptions: `tier`, `tier_price`, `duration_days`

#### 9.2.3 Send HTTP Request to TelePay Bot

- [ ] Add try-except block
- [ ] Use `requests.post()` to send to `{TELEPAY_BOT_URL}/send-notification`
- [ ] Set timeout (5 seconds recommended)
- [ ] Log success/failure with emojis
- [ ] **Important:** Don't fail IPN on notification failure
  - [ ] Wrap in separate try-except
  - [ ] Log error but return 200 for IPN

#### 9.2.4 Alternative: Use Cloud Tasks (Advanced)

- [ ] If using Cloud Tasks approach:
  - [ ] Create new queue: `telepay-notifications-queue`
  - [ ] Add queue configuration to environment
  - [ ] Use `cloudtasks_client.enqueue_notification()`
  - [ ] Follow same pattern as GCWebhook1 enqueue

### 9.3 Update Imports

- [ ] Add: `import requests` (if using direct HTTP)
- [ ] Add: `from datetime import datetime`

**Validation:**
- [ ] Test IPN callback with mock data
- [ ] Verify notification triggered
- [ ] Verify notification doesn't block IPN processing
- [ ] Test with TelePay bot down (should still return 200)

---

## 10. Frontend - TypeScript Types

**Module:** `GCRegisterWeb-10-26/src/types/channel.ts`

### 10.1 Update ChannelRegistrationData Interface

- [ ] Locate `ChannelRegistrationData` interface (around line 10)
- [ ] Add new fields:
  - [ ] `notification_status: boolean;`
  - [ ] `notification_id: number | null;`

### 10.2 Update ChannelUpdateData Interface

- [ ] Locate `ChannelUpdateData` interface (around line 30)
- [ ] Add optional fields:
  - [ ] `notification_status?: boolean;`
  - [ ] `notification_id?: number | null;`

### 10.3 Update ChannelResponse Interface

- [ ] Locate `ChannelResponse` interface (around line 40)
- [ ] Add new fields:
  - [ ] `notification_status: boolean;`
  - [ ] `notification_id: number | null;`

**Validation:**
- [ ] TypeScript compilation passes
- [ ] No type errors in IDE

---

## 11. Frontend - UI Components

**Module:** `GCRegisterWeb-10-26/src/components/` (May need new component or inline)

### 11.1 Create NotificationSettings Component (Optional - Recommended)

- [ ] Create file: `src/components/NotificationSettings.tsx`
- [ ] Add imports: React, icons (Bell, AlertCircle)

#### 11.1.1 Component Props Interface

- [ ] Define interface:
  ```typescript
  interface NotificationSettingsProps {
    notificationEnabled: boolean;
    notificationId: string;
    onToggleEnabled: (enabled: boolean) => void;
    onIdChange: (id: string) => void;
  }
  ```

#### 11.1.2 Component Implementation

- [ ] Create functional component
- [ ] Implement checkbox for enable/disable
- [ ] Implement conditional Telegram ID input
- [ ] Add info box explaining feature
- [ ] Add help text with link to @userinfobot
- [ ] Add inline validation styling

#### 11.1.3 Validation Function

- [ ] Implement `validateNotificationId(id: string)` helper
- [ ] Return validation result with error message

#### 11.1.4 Styling

- [ ] Add CSS classes matching existing design
- [ ] Style checkbox label
- [ ] Style info box
- [ ] Style error message

### Option: Inline Component (Alternative)

- [ ] If not creating separate component, prepare inline JSX code

**Validation:**
- [ ] Component renders correctly
- [ ] Toggle works
- [ ] Input appears when enabled
- [ ] Validation styling works
- [ ] Link to @userinfobot works

---

## 12. Frontend - Registration Page

**Module:** `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`

### 12.1 Add State Management

- [ ] Locate state declarations (around line 50)
- [ ] Add state:
  - [ ] `const [notificationEnabled, setNotificationEnabled] = useState<boolean>(false);`
  - [ ] `const [notificationId, setNotificationId] = useState<string>('');`

### 12.2 Add Validation Function

- [ ] Create `validateNotificationId(id: string): boolean` function
  - [ ] Check if empty
  - [ ] Parse to integer
  - [ ] Validate > 0
  - [ ] Validate length 5-15 digits
  - [ ] Return boolean

### 12.3 Update Form Submission Handler

- [ ] Locate `handleSubmit` function (around line 700)
- [ ] Add validation before submission:
  - [ ] If `notificationEnabled && !validateNotificationId(notificationId)`:
    - [ ] Show toast error
    - [ ] Return early
- [ ] Add to `channelData` object:
  - [ ] `notification_status: notificationEnabled`
  - [ ] `notification_id: notificationEnabled ? parseInt(notificationId, 10) : null`

### 12.4 Add UI Section

- [ ] Locate after "Donation Message Configuration" section (around line 500)
- [ ] Add new section: "Payment Notification Settings"

#### 12.4.1 Section Header

- [ ] Add `<h3>` with Bell icon
- [ ] Title: "Payment Notification Settings"

#### 12.4.2 Checkbox Toggle

- [ ] Add checkbox input
- [ ] Label: "Enable payment notifications"
- [ ] Bind to `notificationEnabled` state
- [ ] On change: Update state, clear ID if disabled

#### 12.4.3 Conditional Content (when enabled)

- [ ] Add info box with AlertCircle icon
- [ ] Explanation text about feature
- [ ] Add Telegram ID input field:
  - [ ] Label with required asterisk
  - [ ] Input type="text"
  - [ ] Placeholder
  - [ ] Bind to `notificationId` state
  - [ ] Apply error class if invalid
  - [ ] Add help text with link to @userinfobot
  - [ ] Show error message if validation fails

### 12.5 Add Icons Import

- [ ] Import `Bell` and `AlertCircle` from icon library

**Validation:**
- [ ] Section appears in correct position
- [ ] Toggle works correctly
- [ ] Input appears/disappears based on toggle
- [ ] Validation works
- [ ] Error messages display
- [ ] Form submission includes notification data
- [ ] API call succeeds with new fields

---

## 13. Frontend - Edit Page

**Module:** `GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`

### 13.1 Add State Management

- [ ] Add same states as RegisterChannelPage:
  - [ ] `notificationEnabled`
  - [ ] `notificationId`

### 13.2 Initialize State from Existing Channel Data

- [ ] Locate where channel data is loaded (useEffect or similar)
- [ ] Set initial values from `channelData`:
  - [ ] `setNotificationEnabled(channelData.notification_status)`
  - [ ] `setNotificationId(channelData.notification_id?.toString() || '')`

### 13.3 Add Validation Function

- [ ] Copy `validateNotificationId` from RegisterChannelPage

### 13.4 Update Form Submission Handler

- [ ] Same changes as RegisterChannelPage
- [ ] Add validation
- [ ] Include notification fields in update payload

### 13.5 Add UI Section

- [ ] Same UI components as RegisterChannelPage
- [ ] In same position (after Donation Message, before Payment Config)

### 13.6 Handle Pre-populated Data

- [ ] Ensure inputs show existing values when editing
- [ ] Ensure toggle reflects current state

**Validation:**
- [ ] Edit page loads with existing notification settings
- [ ] Can enable notifications on previously disabled channel
- [ ] Can disable notifications on previously enabled channel
- [ ] Can update Telegram ID
- [ ] Update API call includes notification data

---

## 14. Testing

**Modules:** Various test files

### 14.1 Backend Unit Tests

#### 14.1.1 Model Validation Tests

- [ ] Create: `GCRegisterAPI-10-26/tests/test_channel_models.py`
- [ ] Test `ChannelRegistrationRequest`:
  - [ ] Valid data with notifications enabled
  - [ ] Valid data with notifications disabled
  - [ ] Invalid: notifications enabled, ID missing
  - [ ] Invalid: notifications enabled, ID negative
  - [ ] Invalid: notifications enabled, ID too short
  - [ ] Invalid: notifications enabled, ID too long

#### 14.1.2 Service Tests

- [ ] Create: `GCRegisterAPI-10-26/tests/test_notification_service_integration.py`
- [ ] Test channel registration with notification fields
- [ ] Test channel retrieval includes notification fields
- [ ] Test channel update of notification fields

### 14.2 TelePay Bot Unit Tests

#### 14.2.1 Database Manager Tests

- [ ] Create: `TelePay10-26/tests/test_database_notifications.py`
- [ ] Test `get_notification_settings()`:
  - [ ] Notifications enabled with valid ID
  - [ ] Notifications disabled
  - [ ] Channel not found
  - [ ] Database error handling

#### 14.2.2 Notification Service Tests

- [ ] Create: `TelePay10-26/tests/test_notification_service.py`
- [ ] Mock bot and db_manager
- [ ] Test `send_payment_notification()`:
  - [ ] Subscription payment - success
  - [ ] Donation payment - success
  - [ ] Notifications disabled - skip
  - [ ] No notification_id - skip
  - [ ] Bot blocked by user - handle gracefully
  - [ ] Invalid chat_id - handle gracefully
  - [ ] Network error - handle gracefully
- [ ] Test `_format_notification_message()`:
  - [ ] Subscription formatting
  - [ ] Donation formatting
  - [ ] Fallback formatting
- [ ] Test `_send_telegram_message()`:
  - [ ] Success case
  - [ ] Forbidden error
  - [ ] BadRequest error
  - [ ] Network error

### 14.3 Integration Tests

#### 14.3.1 End-to-End Registration Flow

- [ ] Register channel with notifications enabled
- [ ] Verify database contains correct values
- [ ] Retrieve channel via API
- [ ] Verify response includes notification settings

#### 14.3.2 End-to-End Notification Flow

- [ ] Simulate NowPayments IPN callback
- [ ] Verify payment processed
- [ ] Verify notification triggered
- [ ] Verify notification received (use test bot/channel)

#### 14.3.3 Update Flow

- [ ] Create channel with notifications disabled
- [ ] Update to enable notifications
- [ ] Verify database updated
- [ ] Update Telegram ID
- [ ] Verify database updated
- [ ] Disable notifications
- [ ] Verify database updated

### 14.4 Frontend Tests (Optional - if using Jest/React Testing Library)

- [ ] Test NotificationSettings component
- [ ] Test RegisterChannelPage includes notification section
- [ ] Test EditChannelPage loads existing settings
- [ ] Test validation logic

### 14.5 Manual Testing Checklist

- [ ] Register new channel with notifications **enabled**
  - [ ] Enter valid Telegram ID
  - [ ] Submit form
  - [ ] Verify success
  - [ ] Check database for values
- [ ] Register new channel with notifications **disabled**
  - [ ] Submit form
  - [ ] Verify success
  - [ ] Check database (`notification_status = false`, `notification_id = NULL`)
- [ ] Edit existing channel
  - [ ] Enable notifications (was disabled)
  - [ ] Enter Telegram ID
  - [ ] Save
  - [ ] Verify updated
- [ ] Edit existing channel
  - [ ] Disable notifications (was enabled)
  - [ ] Save
  - [ ] Verify updated
- [ ] Test notification delivery
  - [ ] Create channel with your real Telegram ID
  - [ ] Enable notifications
  - [ ] Trigger test subscription payment
  - [ ] Verify notification received on Telegram
  - [ ] Check formatting and content
- [ ] Test notification delivery (donation)
  - [ ] Trigger test donation payment
  - [ ] Verify notification received
  - [ ] Check formatting and content
- [ ] Test error scenarios
  - [ ] Use invalid Telegram ID
  - [ ] Verify error handling
  - [ ] Use bot-blocked Telegram ID
  - [ ] Verify graceful failure (doesn't break payment)

**Validation:**
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Manual testing complete
- [ ] No regressions in existing features

---

## 15. Deployment

**Modules:** All modified services

### 15.1 Pre-Deployment Preparation

- [ ] Review all code changes
- [ ] Run all tests locally
- [ ] Update DECISIONS.md with key decisions
- [ ] Create backup of production database

### 15.2 Database Migration (Production)

- [ ] Connect to production database via Cloud SQL Proxy
- [ ] Run backup:
  ```bash
  gcloud sql backups create --instance=telepaypsql
  ```
- [ ] Execute migration:
  ```bash
  cd TOOLS_SCRIPTS_TESTS/tools
  python3 execute_notification_migration.py
  ```
- [ ] Verify columns added:
  ```sql
  SELECT column_name, data_type, column_default
  FROM information_schema.columns
  WHERE table_name = 'main_clients_database'
  AND column_name IN ('notification_status', 'notification_id');
  ```
- [ ] Update PROGRESS.md

### 15.3 Deploy Backend API (GCRegisterAPI-10-26)

- [ ] Build and deploy:
  ```bash
  cd GCRegisterAPI-10-26
  gcloud run deploy gcregisterapi-10-26 \
    --source . \
    --region us-central1 \
    --allow-unauthenticated
  ```
- [ ] Wait for deployment to complete
- [ ] Check health endpoint
- [ ] Test registration endpoint with curl/Postman

### 15.4 Deploy Frontend (GCRegisterWeb-10-26)

- [ ] Build production bundle:
  ```bash
  cd GCRegisterWeb-10-26
  npm run build
  ```
- [ ] Deploy to Cloud Storage or CDN
- [ ] Clear CDN cache if applicable
- [ ] Verify deployment by visiting registration page

### 15.5 Deploy TelePay Bot

- [ ] Add new files to deployment:
  - [ ] `notification_service.py`
  - [ ] `notification_api.py` (if separate)
- [ ] Update existing files
- [ ] Deploy via your existing deployment method
- [ ] Verify bot starts successfully
- [ ] Check logs for notification service initialization

### 15.6 Deploy np-webhook-10-26

- [ ] Add notification trigger code
- [ ] Add environment variable for `TELEPAY_BOT_URL`:
  ```bash
  gcloud secrets create TELEPAY_BOT_URL --data-file=-
  # Enter URL, then Ctrl+D
  ```
- [ ] Deploy:
  ```bash
  cd np-webhook-10-26
  gcloud run deploy np-webhook-10-26 \
    --source . \
    --region us-central1 \
    --set-secrets TELEPAY_BOT_URL=TELEPAY_BOT_URL:latest
  ```
- [ ] Verify deployment

### 15.7 Post-Deployment Smoke Tests

- [ ] Register test channel with notifications enabled
- [ ] Verify registration successful
- [ ] Check database for correct values
- [ ] Edit test channel
- [ ] Trigger test payment (use NowPayments sandbox)
- [ ] Verify notification received
- [ ] Monitor Cloud Logging for errors

### 15.8 Update Documentation

- [ ] Update user documentation (if exists)
- [ ] Add "How to find Telegram ID" guide
- [ ] Update API documentation
- [ ] Update architecture diagrams (if exists)
- [ ] Update PROGRESS.md with completion status

**Validation:**
- [ ] All services deployed successfully
- [ ] Health checks passing
- [ ] Test notifications working
- [ ] No errors in Cloud Logging
- [ ] Production traffic handling correctly

---

## 16. Verification

**Final End-to-End Validation**

### 16.1 Production Verification

- [ ] Create real channel with notifications enabled
- [ ] Use your own Telegram ID
- [ ] Complete real subscription payment (small amount)
- [ ] Verify notification received
- [ ] Check notification content accuracy
- [ ] Verify payment processing not affected

### 16.2 Monitoring Setup

- [ ] Create Cloud Monitoring dashboard
- [ ] Add metrics:
  - [ ] Notification success rate
  - [ ] Notification failure count by error type
  - [ ] Notification delivery latency
- [ ] Set up alerts:
  - [ ] Notification failure rate > 10%
  - [ ] Bot API errors spike
- [ ] Create log-based metrics

### 16.3 Performance Check

- [ ] Monitor IPN handler latency
- [ ] Verify notifications don't slow down payment processing
- [ ] Check TelePay bot response times
- [ ] Review database query performance

### 16.4 Documentation Review

- [ ] Verify PROGRESS.md updated
- [ ] Verify DECISIONS.md updated
- [ ] Verify BUGS.md updated (if any issues found)
- [ ] Archive checklist to PROGRESS_ARCH.md if needed

**Validation:**
- [ ] Production system working correctly
- [ ] Monitoring in place
- [ ] Performance acceptable
- [ ] Documentation complete

---

## Module Breakdown Summary

This checklist ensures modular implementation across **13 distinct modules**:

1. **Database Layer** - SQL scripts in `TOOLS_SCRIPTS_TESTS/scripts/`
2. **Backend Models** - Pydantic models in `api/models/channel.py`
3. **Backend Services** - Business logic in `api/services/channel_service.py`
4. **Backend Routes** - API endpoints in `api/routes/channels.py`
5. **TelePay Database** - Database methods in `TelePay10-26/database.py`
6. **Notification Service** - New module `TelePay10-26/notification_service.py`
7. **Notification API** - New module `TelePay10-26/notification_api.py`
8. **Bot Initialization** - Integration in `TelePay10-26/app_initializer.py`
9. **IPN Handler** - Trigger logic in `np-webhook-10-26/app.py`
10. **Frontend Types** - TypeScript interfaces in `src/types/channel.ts`
11. **Frontend Components** - React component (optional) in `src/components/`
12. **Registration Page** - UI in `src/pages/RegisterChannelPage.tsx`
13. **Edit Page** - UI in `src/pages/EditChannelPage.tsx`

Each module has **clear boundaries** and **single responsibility**, ensuring maintainable and testable code.

---

## Estimated Implementation Time

| Phase | Tasks | Estimated Time |
|-------|-------|---------------|
| Database | 1.1 - 1.5 | 1 hour |
| Backend Models | 2.1 - 2.5 | 1 hour |
| Backend Services | 3.1 - 3.4 | 2 hours |
| Backend Routes | 4.1 - 4.2 | 0.5 hours |
| TelePay Database | 5.1 - 5.2 | 0.5 hours |
| Notification Service | 6.1 - 6.8 | 3 hours |
| Notification API | 7.1 - 7.5 | 1.5 hours |
| Bot Initialization | 8.1 - 8.3 | 0.5 hours |
| IPN Handler | 9.1 - 9.3 | 2 hours |
| Frontend Types | 10.1 - 10.3 | 0.5 hours |
| Frontend Components | 11.1 - 11.4 | 2 hours |
| Registration Page | 12.1 - 12.5 | 2 hours |
| Edit Page | 13.1 - 13.6 | 1.5 hours |
| Testing | 14.1 - 14.5 | 4 hours |
| Deployment | 15.1 - 15.8 | 2 hours |
| Verification | 16.1 - 16.4 | 1 hour |
| **Total** | | **~25 hours** |

**Note:** Times are estimates for an experienced developer familiar with the codebase.

---

## Notes

- **Emojis:** Maintain consistent emoji usage in logs as per existing codebase style
- **Error Handling:** All new functions must include try-except blocks with proper logging
- **Testing:** Write tests before marking tasks complete
- **Documentation:** Update PROGRESS.md, DECISIONS.md, and BUGS.md as you go
- **Modular First:** Always prefer creating new modules over expanding existing files
- **Validation:** Test each module independently before integration

---

## Completion Criteria

✅ All checkboxes in this document are checked
✅ All tests passing
✅ Production deployment successful
✅ Notifications working in production
✅ Documentation updated
✅ No regressions in existing features
✅ PROGRESS.md updated with summary
✅ DECISIONS.md updated with key architectural decisions

---

**End of Checklist**
