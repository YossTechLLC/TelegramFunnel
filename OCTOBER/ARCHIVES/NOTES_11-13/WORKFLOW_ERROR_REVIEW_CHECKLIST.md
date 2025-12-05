# Workflow Error Resolution Checklist

**Document Version:** 1.0
**Created:** 2025-11-13
**Parent Document:** WORKFLOW_ERROR_REVIEW.md
**Status:** READY FOR EXECUTION

---

## Overview

This checklist provides a step-by-step implementation plan to resolve the critical workflow errors identified in WORKFLOW_ERROR_REVIEW.md:
- ❌ **Problem 1:** Donation button workflow broken (donate_start_* callbacks not handled)
- ❌ **Problem 2:** Subscription button shows "No payment context found" error
- ❌ **Problem 3:** Missing HTTP integration between GCBotCommand and GCDonationHandler

**Estimated Total Time:** 4-6 hours
**Risk Level:** 🟡 MEDIUM
**Priority:** 🔴 CRITICAL

---

## Phase 1: Pre-Implementation Investigation

### Task 1.1: Verify Current Service Status
- [ ] Check GCBotCommand deployment status
  ```bash
  gcloud run services describe gcbotcommand-10-26 --region=us-central1
  ```
- [ ] Check GCDonationHandler deployment status
  ```bash
  gcloud run services describe gcdonationhandler-10-26 --region=us-central1
  ```
- [ ] Verify both services are healthy (status = SERVING)
- [ ] Note service URLs for configuration

**Expected Output:**
- GCBotCommand URL: `https://gcbotcommand-10-26-*.run.app`
- GCDonationHandler URL: `https://gcdonationhandler-10-26-*.run.app`

### Task 1.2: Verify Telegram Webhook Configuration
- [ ] Check current webhook URL
  ```bash
  TOKEN="<BOT_TOKEN>"
  curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo" | jq
  ```
- [ ] Verify webhook points to GCBotCommand service
- [ ] Verify webhook is receiving updates (last_error_date should be empty or old)
- [ ] Check allowed_updates includes "callback_query"

**Expected Output:**
```json
{
  "url": "https://gcbotcommand-10-26-*.run.app/webhook",
  "has_custom_certificate": false,
  "pending_update_count": 0,
  "allowed_updates": ["message", "callback_query", "inline_query"]
}
```

### Task 1.3: Investigate Subscription Flow Issue
- [ ] Query Cloud Logging for recent `/start` command logs in GCBotCommand
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  "📍 /start command"
  ```
- [ ] Check if `/start` commands are being received
- [ ] Check if token parsing is succeeding
- [ ] Verify conversation_state table exists in database
  ```bash
  # Connect to database and run:
  # \d conversation_state
  ```
- [ ] Check for any state write/read logs

**Diagnostic Questions:**
- Are `/start` commands reaching GCBotCommand? YES / NO / UNKNOWN
- If YES, are they being parsed correctly? YES / NO / UNKNOWN
- If YES, is conversation_state being saved? YES / NO / UNKNOWN
- If YES, is conversation_state being retrieved? YES / NO / UNKNOWN

### Task 1.4: Document Current Configuration
- [ ] List all secrets currently in Secret Manager for GCBotCommand
  ```bash
  gcloud secrets list --filter="name~gcbotcommand OR name~TELEGRAM_BOT"
  ```
- [ ] Verify GCPaymentGateway URL is configured
- [ ] Note which secrets need to be added

---

## Phase 2: Code Implementation - Donation Callback Handlers

### Task 2.1: Update callback_handler.py - Add Routing Logic
**File:** `GCBotCommand-10-26/handlers/callback_handler.py`

- [ ] Open `callback_handler.py` in editor
- [ ] Locate the `handle_callback()` method routing logic (around lines 45-72)
- [ ] Add donation routing handlers BEFORE the `else:` block (around line 70):

```python
        elif callback_data.startswith("donate_start_"):
            return self._handle_donate_start(chat_id, user_id, callback_data, callback_query)

        elif callback_data.startswith("donate_"):
            # All keypad callbacks: donate_digit_*, donate_backspace, donate_clear, donate_confirm, donate_cancel, donate_noop
            return self._handle_donate_keypad(chat_id, user_id, callback_data, callback_query)
```

- [ ] Save the file
- [ ] Verify indentation matches surrounding code
- [ ] Verify no syntax errors (run: `python3 -m py_compile handlers/callback_handler.py`)

**Location:** Lines 69-74 (insert before `else:` block)

### Task 2.2: Add _handle_donate_start() Method
**File:** `GCBotCommand-10-26/handlers/callback_handler.py`

- [ ] Add new method after `_handle_back_to_main()` (around line 170):

```python
    def _handle_donate_start(self, chat_id: int, user_id: int, callback_data: str, callback_query: Dict) -> Dict[str, str]:
        """
        Handle donate_start callback - forward to GCDonationHandler service.

        This method is triggered when a user clicks the "💝 Donate" button
        in a closed channel's broadcast message.

        Args:
            chat_id: Chat ID where callback originated
            user_id: User ID who clicked the button
            callback_data: Format "donate_start_{open_channel_id}"
            callback_query: Full callback query object from Telegram

        Returns:
            {"status": "ok"} on success, {"status": "error"} on failure
        """
        # Extract open_channel_id from callback_data
        # Format: "donate_start_-1003202734748" → "-1003202734748"
        open_channel_id = callback_data.replace("donate_start_", "")

        logger.info(f"💝 Donate button clicked: user={user_id}, channel={open_channel_id}")

        # Get GCDonationHandler URL from config
        donation_handler_url = self.config.get('gcdonationhandler_url')

        if not donation_handler_url:
            logger.error("❌ GCDonationHandler URL not configured in Secret Manager")
            return self._send_message(
                chat_id,
                "❌ Donation service temporarily unavailable. Please try again later."
            )

        # Prepare payload for GCDonationHandler /start-donation-input endpoint
        payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "open_channel_id": open_channel_id,
            "callback_query_id": callback_query['id']
        }

        # Call GCDonationHandler service
        try:
            logger.info(f"🌐 Calling GCDonationHandler: {donation_handler_url}/start-donation-input")

            response = self.http_client.post(
                f"{donation_handler_url}/start-donation-input",
                payload,
                timeout=15  # 15 second timeout for service-to-service call
            )

            if response and response.get('success'):
                logger.info(f"✅ Donation flow started successfully for user {user_id}")
                return {"status": "ok"}
            else:
                error = response.get('error', 'Unknown error') if response else 'No response from service'
                logger.error(f"❌ GCDonationHandler returned error: {error}")

                return self._send_message(
                    chat_id,
                    "❌ Failed to start donation flow. Please try again or contact support."
                )

        except Exception as e:
            logger.error(f"❌ HTTP error calling GCDonationHandler: {e}", exc_info=True)

            return self._send_message(
                chat_id,
                "❌ Service error. Please try again in a few moments."
            )
```

- [ ] Add method to class
- [ ] Verify indentation (should match other methods like `_handle_payment_gateway`)
- [ ] Save file
- [ ] Verify no syntax errors

**Location:** After line 169 (after `_handle_back_to_main` method)

### Task 2.3: Add _handle_donate_keypad() Method
**File:** `GCBotCommand-10-26/handlers/callback_handler.py`

- [ ] Add new method after `_handle_donate_start()`:

```python
    def _handle_donate_keypad(self, chat_id: int, user_id: int, callback_data: str, callback_query: Dict) -> Dict[str, str]:
        """
        Handle keypad callback - forward to GCDonationHandler service.

        This method handles all numeric keypad interactions during donation input:
        - donate_digit_0 through donate_digit_9
        - donate_digit_. (decimal point)
        - donate_backspace
        - donate_clear
        - donate_confirm
        - donate_cancel
        - donate_noop (display-only button)

        Args:
            chat_id: Chat ID where callback originated
            user_id: User ID who clicked the button
            callback_data: Keypad action (e.g., "donate_digit_5", "donate_confirm")
            callback_query: Full callback query object from Telegram

        Returns:
            {"status": "ok"} - always returns success to avoid user-facing errors
        """
        logger.info(f"🔢 Keypad input: user={user_id}, action={callback_data}")

        # Get GCDonationHandler URL from config
        donation_handler_url = self.config.get('gcdonationhandler_url')

        if not donation_handler_url:
            logger.error("❌ GCDonationHandler URL not configured")
            # Fail silently for keypad inputs - user already has keypad open
            return {"status": "ok"}

        # Prepare payload for GCDonationHandler /keypad-input endpoint
        payload = {
            "user_id": user_id,
            "callback_data": callback_data,
            "callback_query_id": callback_query['id'],
            "message_id": callback_query['message']['message_id'],
            "chat_id": chat_id
        }

        # Call GCDonationHandler service
        try:
            response = self.http_client.post(
                f"{donation_handler_url}/keypad-input",
                payload,
                timeout=10
            )

            if response and response.get('success'):
                logger.info(f"✅ Keypad input processed: user={user_id}, action={callback_data}")
            else:
                error = response.get('error', 'Unknown error') if response else 'No response'
                logger.warning(f"⚠️ GCDonationHandler keypad error: {error}")

            # Always return success - GCDonationHandler handles user feedback
            return {"status": "ok"}

        except Exception as e:
            logger.error(f"❌ HTTP error calling GCDonationHandler keypad: {e}")
            # Fail silently - don't disrupt user's keypad interaction
            return {"status": "ok"}
```

- [ ] Add method to class
- [ ] Verify indentation
- [ ] Save file
- [ ] Verify no syntax errors

**Location:** After `_handle_donate_start()` method

### Task 2.4: Verify Code Compilation
- [ ] Run Python syntax check on modified file:
  ```bash
  cd GCBotCommand-10-26
  python3 -m py_compile handlers/callback_handler.py
  ```
- [ ] Verify no errors reported
- [ ] Check file compiles successfully

---

## Phase 3: Code Implementation - Configuration Updates

### Task 3.1: Update config_manager.py - Add GCDonationHandler URL
**File:** `GCBotCommand-10-26/config_manager.py`

- [ ] Open `config_manager.py` in editor
- [ ] Locate the secret fetching methods (around where other `get_*` methods are)
- [ ] Add new method:

```python
    def get_gcdonationhandler_url(self) -> Optional[str]:
        """
        Get GCDonationHandler service URL from Secret Manager.

        Returns:
            Service URL (e.g., "https://gcdonationhandler-10-26-*.run.app")
            or None if not configured
        """
        try:
            url = self._fetch_secret('GCDONATIONHANDLER_URL_SECRET')
            if url:
                logger.info(f"🔗 GCDonationHandler URL loaded: {url[:50]}...")
            return url
        except Exception as e:
            logger.error(f"❌ Failed to fetch GCDonationHandler URL: {e}")
            return None
```

- [ ] Save file
- [ ] Locate `initialize_config()` method
- [ ] Add to config dict (around where other URLs are configured):

```python
        config['gcdonationhandler_url'] = self.get_gcdonationhandler_url()
```

- [ ] Save file
- [ ] Verify syntax:
  ```bash
  python3 -m py_compile config_manager.py
  ```

**Location:** Add method near other `get_*` methods, update `initialize_config()`

### Task 3.2: Verify HTTPClient Exists
**File:** `GCBotCommand-10-26/utils/http_client.py`

- [ ] Verify file exists:
  ```bash
  ls -la utils/http_client.py
  ```
- [ ] Read file to verify it has `post()` method
- [ ] Verify it supports `timeout` parameter
- [ ] If missing, note that it needs to be implemented

**Expected:** HTTPClient class with `post(url, payload, timeout=10)` method

---

## Phase 4: Secret Manager Configuration

### Task 4.1: Create GCDONATIONHANDLER_URL_SECRET
- [ ] Get current GCDonationHandler service URL:
  ```bash
  gcloud run services describe gcdonationhandler-10-26 \
    --region=us-central1 \
    --format='value(status.url)'
  ```
- [ ] Note the URL (should be: `https://gcdonationhandler-10-26-*.run.app`)
- [ ] Create secret in Secret Manager:
  ```bash
  echo -n "https://gcdonationhandler-10-26-291176869049.us-central1.run.app" | \
    gcloud secrets create GCDONATIONHANDLER_URL_SECRET \
      --data-file=- \
      --replication-policy=automatic
  ```
- [ ] Verify secret created:
  ```bash
  gcloud secrets describe GCDONATIONHANDLER_URL_SECRET
  ```

### Task 4.2: Grant Secret Access to GCBotCommand Service Account
- [ ] Get GCBotCommand service account:
  ```bash
  gcloud run services describe gcbotcommand-10-26 \
    --region=us-central1 \
    --format='value(spec.template.spec.serviceAccountName)'
  ```
- [ ] Grant access to new secret:
  ```bash
  gcloud secrets add-iam-policy-binding GCDONATIONHANDLER_URL_SECRET \
    --member="serviceAccount:<SERVICE_ACCOUNT_EMAIL>" \
    --role="roles/secretmanager.secretAccessor"
  ```
- [ ] Verify IAM binding:
  ```bash
  gcloud secrets get-iam-policy GCDONATIONHANDLER_URL_SECRET
  ```

**Expected Service Account:** `291176869049-compute@developer.gserviceaccount.com` or custom account

---

## Phase 5: Deployment

### Task 5.1: Build and Deploy GCBotCommand
- [ ] Navigate to service directory:
  ```bash
  cd GCBotCommand-10-26
  ```
- [ ] Verify all files saved
- [ ] Build and deploy to Cloud Run:
  ```bash
  gcloud builds submit --tag gcr.io/telepay-459221/gcbotcommand-10-26 && \
  gcloud run deploy gcbotcommand-10-26 \
    --image gcr.io/telepay-459221/gcbotcommand-10-26 \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300s \
    --service-account 291176869049-compute@developer.gserviceaccount.com
  ```
- [ ] Wait for deployment to complete
- [ ] Verify deployment succeeded (status: SERVING)

**Expected Time:** 3-5 minutes

### Task 5.2: Verify Deployment
- [ ] Check service status:
  ```bash
  gcloud run services describe gcbotcommand-10-26 --region=us-central1
  ```
- [ ] Verify revision is serving traffic
- [ ] Get service URL
- [ ] Test health endpoint:
  ```bash
  curl https://gcbotcommand-10-26-*.run.app/health
  ```

**Expected Response:** `{"status": "healthy", ...}`

---

## Phase 6: Testing & Validation

### Task 6.1: Test Donation Button Flow
- [ ] Trigger a broadcast to a closed channel (use GCBroadcastService or manual broadcast)
- [ ] Verify donation message appears in closed channel with "💝 Donate" button
- [ ] Click "💝 Donate to Support This Channel" button
- [ ] **EXPECTED:** Numeric keypad appears in DM with user
- [ ] **EXPECTED:** Keypad shows "$0.00" display
- [ ] Enter amount using keypad (e.g., 1, 0, ., 0, 0 → "$10.00")
- [ ] **EXPECTED:** Display updates in real-time
- [ ] Click "✅ Confirm & Pay"
- [ ] **EXPECTED:** Keypad disappears
- [ ] **EXPECTED:** Payment invoice message appears with Web App button
- [ ] **EXPECTED:** No error messages

**Validation Criteria:**
- [ ] Keypad appears within 2 seconds of button click
- [ ] All keypad buttons respond (digits, backspace, clear)
- [ ] Amount display updates correctly
- [ ] Confirm button creates invoice successfully
- [ ] No errors in Cloud Logging

### Task 6.2: Check Logs - Donation Flow
- [ ] Open Cloud Logging for GCBotCommand
- [ ] Filter for donation-related logs:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  "💝 Donate button clicked"
  ```
- [ ] Verify log sequence:
  1. `💝 Donate button clicked: user={id}, channel={id}`
  2. `🌐 Calling GCDonationHandler: https://...`
  3. `✅ Donation flow started successfully for user {id}`
- [ ] Check for any errors
- [ ] Open Cloud Logging for GCDonationHandler
- [ ] Verify logs:
  1. `💝 Start donation input: user_id={id}, channel={id}`
  2. `💝 User {id} started donation for channel {id}`
  3. `🔢 Keypad input: user_id={id}, action=donate_digit_*`
  4. `✅ Donation confirmed: $X.XX for channel {id}`

**Expected:** Clean log flow with no errors

### Task 6.3: Test Subscription Button Flow
- [ ] Trigger broadcast to open channel (use GCBroadcastService)
- [ ] Verify subscription message appears with tier buttons
- [ ] Click a subscription tier button (e.g., "🥇 $5 for 30 days")
- [ ] **EXPECTED:** DM opens with bot
- [ ] **EXPECTED:** Message appears describing subscription
- [ ] **EXPECTED:** "💰 Launch Payment Gateway" button appears
- [ ] **NOT EXPECTED:** Any error messages
- [ ] Click "💰 Launch Payment Gateway" button
- [ ] **EXPECTED:** Payment invoice appears with Web App button
- [ ] **NOT EXPECTED:** "❌ No payment context found" error

**Validation Criteria:**
- [ ] /start command is received by GCBotCommand
- [ ] Token is parsed correctly
- [ ] conversation_state is saved to database
- [ ] Payment gateway button appears
- [ ] Clicking payment gateway creates invoice
- [ ] No "payment context not found" error

### Task 6.4: Check Logs - Subscription Flow
- [ ] Open Cloud Logging for GCBotCommand
- [ ] Filter for /start command:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  "📍 /start command"
  ```
- [ ] Verify log sequence:
  1. `📍 /start command from user {id}, args: {token}`
  2. `💰 Subscription: channel={id}, price=${price}, time={days}days`
  3. `✅ Message sent to chat_id {id}` (with payment button)
- [ ] When user clicks "Launch Payment Gateway":
  1. `🔘 Callback: TRIGGER_PAYMENT from user {id}`
  2. `💳 Creating payment invoice...`
  3. `✅ Message sent to chat_id {id}` (with invoice)
- [ ] Check for any errors or missing logs

**Red Flags:**
- ❌ No `/start` logs → Webhook not routing to GCBotCommand
- ❌ Token parsing errors → Token encoding/decoding mismatch
- ❌ "No payment context found" → conversation_state not saving/retrieving

### Task 6.5: Database Verification (If Subscription Flow Fails)
- [ ] Connect to telepaypsql database
- [ ] Check if conversation_state table exists:
  ```sql
  SELECT table_name FROM information_schema.tables
  WHERE table_name = 'conversation_state';
  ```
- [ ] If table exists, check schema:
  ```sql
  \d conversation_state
  ```
- [ ] Check if state is being written:
  ```sql
  SELECT user_id, context_type, state_data, created_at
  FROM conversation_state
  WHERE context_type = 'payment'
  ORDER BY created_at DESC
  LIMIT 5;
  ```
- [ ] Note findings

**Expected Schema:**
```
Column        | Type      | Nullable
--------------+-----------+---------
user_id       | bigint    | NO
context_type  | text      | NO
state_data    | jsonb     | YES
created_at    | timestamp | YES
updated_at    | timestamp | YES
```

**Expected Data:**
```json
{
  "channel_id": "-1003202734748",
  "price": 5.0,
  "time": 30,
  "payment_type": "subscription"
}
```

---

## Phase 7: Subscription Flow Debugging (If Tests Fail)

### Task 7.1: Add Debug Logging to command_handler.py
**Only if subscription flow is still broken**

- [ ] Open `GCBotCommand-10-26/handlers/command_handler.py`
- [ ] In `_handle_subscription_token()` method (around line 83), add logging:

```python
def _handle_subscription_token(self, chat_id: int, user: Dict, token_data: Dict) -> Dict[str, str]:
    """Handle subscription token - route to payment gateway"""
    channel_id = token_data['channel_id']
    price = token_data['price']
    time = token_data['time']

    logger.info(f"💰 Subscription: channel={channel_id}, price=${price}, time={time}days")

    # ADD THIS DEBUG LOG:
    logger.info(f"🔍 [DEBUG] Token data: {token_data}")

    # Fetch channel info from database
    channel_data = self.db.fetch_channel_by_id(channel_id)

    if not channel_data:
        logger.error(f"❌ Channel not found in database: {channel_id}")
        return self._send_error_message(chat_id, "Channel not found")

    # ADD THIS DEBUG LOG:
    logger.info(f"🔍 [DEBUG] Channel data fetched: title={channel_data.get('closed_channel_title')}")

    # ... rest of method ...

    # BEFORE saving state, add this:
    logger.info(f"🔍 [DEBUG] About to save conversation_state for user {user['id']}")

    # Store subscription context in database for later retrieval
    self.db.save_conversation_state(user['id'], 'payment', {
        'channel_id': channel_id,
        'price': price,
        'time': time,
        'payment_type': 'subscription'
    })

    # AFTER saving state, add this:
    logger.info(f"🔍 [DEBUG] Conversation state saved for user {user['id']}")
```

- [ ] Redeploy GCBotCommand
- [ ] Retry subscription flow
- [ ] Check logs for debug output

### Task 7.2: Add Debug Logging to callback_handler.py
**Only if subscription flow is still broken**

- [ ] Open `GCBotCommand-10-26/handlers/callback_handler.py`
- [ ] In `_handle_payment_gateway()` method (around line 87), add logging:

```python
def _handle_payment_gateway(self, chat_id: int, user_id: int) -> Dict[str, str]:
    """Handle CMD_GATEWAY callback"""

    # ADD THIS DEBUG LOG:
    logger.info(f"🔍 [DEBUG] Payment gateway triggered for user {user_id}")

    # Check if user has payment context
    payment_state = self.db.get_conversation_state(user_id, 'payment')

    # ADD THIS DEBUG LOG:
    logger.info(f"🔍 [DEBUG] Payment state retrieved: {payment_state}")

    if not payment_state:
        logger.error(f"❌ No payment state found for user {user_id}")
        return self._send_message(chat_id, "❌ No payment context found. Please start from a subscription link.")

    # Call GCPaymentGateway
    return self._create_payment_invoice(chat_id, user_id, payment_state)
```

- [ ] Redeploy GCBotCommand
- [ ] Retry subscription flow
- [ ] Check logs for debug output

### Task 7.3: Verify conversation_state Table Migration
**Only if state is not being saved**

- [ ] Check if migration file exists:
  ```bash
  ls -la TOOLS_SCRIPTS_TESTS/scripts/create_conversation_state_table.sql
  ```
- [ ] If exists, verify it was executed:
  - Check TOOLS_SCRIPTS_TESTS/tools/execute_conversation_state_migration.py
- [ ] If not executed, run migration manually:
  ```bash
  cd TOOLS_SCRIPTS_TESTS/tools
  python3 execute_conversation_state_migration.py
  ```
- [ ] Verify table created successfully

### Task 7.4: Test Token Encoding/Decoding
**Only if token parsing is failing**

- [ ] Create test script to encode token (same as GCBroadcastService):
  ```python
  import base64

  channel_id = "-1003202734748"
  price = 5.0
  days = 30

  base_hash = base64.urlsafe_b64encode(str(channel_id).encode()).decode()
  safe_sub = str(price).replace(".", "d")
  token = f"{base_hash}_{safe_sub}_{days}"

  print(f"Token: {token}")
  print(f"Full URL: https://t.me/YOUR_BOT?start={token}")
  ```
- [ ] Run script and note token
- [ ] Test token decoding (same as GCBotCommand should do)
- [ ] Verify channel_id, price, days are extracted correctly
- [ ] If mismatch found, fix TokenParser logic

---

## Phase 8: Post-Deployment Monitoring

### Task 8.1: Monitor Error Rates
- [ ] Set up Cloud Logging query for errors:
  ```
  resource.type="cloud_run_revision"
  resource.labels.service_name="gcbotcommand-10-26"
  severity>=ERROR
  timestamp>="2025-11-13T00:00:00Z"
  ```
- [ ] Monitor for 24 hours
- [ ] Investigate any new error patterns
- [ ] Document any unexpected errors

### Task 8.2: Monitor Donation Flow Success Rate
- [ ] Query logs for donation starts:
  ```
  "💝 Donate button clicked"
  ```
- [ ] Count total attempts
- [ ] Query logs for donation completions:
  ```
  "✅ Donation confirmed"
  ```
- [ ] Calculate success rate: (completions / starts) * 100%
- [ ] **Target:** >= 95% success rate

### Task 8.3: Monitor Subscription Flow Success Rate
- [ ] Query logs for subscription starts:
  ```
  "💰 Subscription: channel="
  ```
- [ ] Count total attempts
- [ ] Query logs for invoice creations:
  ```
  "✅ Payment invoice created"
  ```
- [ ] Calculate success rate: (invoices / starts) * 100%
- [ ] **Target:** >= 95% success rate

### Task 8.4: User Feedback Monitoring
- [ ] Monitor for user reports of:
  - "Button doesn't work"
  - "Nothing happens when I click"
  - "Error message appears"
- [ ] Investigate each report
- [ ] Correlate with logs using user_id or timestamp
- [ ] Document root causes

---

## Phase 9: Documentation & Rollout

### Task 9.1: Update PROGRESS.md
- [ ] Add entry at top of PROGRESS.md:
  ```markdown
  ## 2025-11-13 - Workflow Error Resolution

  ### Fixed
  - ✅ Added donation callback handlers to GCBotCommand (donate_start_*, donate_*)
  - ✅ Integrated GCBotCommand with GCDonationHandler via HTTP
  - ✅ Added GCDONATIONHANDLER_URL_SECRET to Secret Manager
  - ✅ [If fixed] Resolved subscription flow "No payment context found" error

  ### Files Modified
  - GCBotCommand-10-26/handlers/callback_handler.py (added donation handlers)
  - GCBotCommand-10-26/config_manager.py (added GCDonationHandler URL config)

  ### Testing
  - ✅ Donation button flow working end-to-end
  - ✅ Subscription button flow working end-to-end
  - ✅ No errors in production logs
  ```

### Task 9.2: Update DECISIONS.md
- [ ] Add entry at top of DECISIONS.md:
  ```markdown
  ## 2025-11-13 - Donation Callback Routing Strategy

  **Decision:** Route donation callbacks from GCBotCommand to GCDonationHandler via HTTP POST

  **Rationale:**
  - GCBotCommand is the webhook receiver for all Telegram updates
  - GCDonationHandler is a separate Cloud Run service with keypad logic
  - HTTP integration maintains service separation while enabling functionality

  **Alternatives Considered:**
  - Merge GCDonationHandler into GCBotCommand (rejected: violates microservice architecture)
  - Use Pub/Sub for async communication (rejected: adds latency for real-time interactions)

  **Trade-offs:**
  - Pro: Maintains service boundaries and independent deployability
  - Pro: Allows GCDonationHandler to be reused by other services
  - Con: Adds HTTP latency (~50-200ms per callback)
  - Con: Requires service discovery via Secret Manager
  ```

### Task 9.3: Create Deployment Summary
- [ ] Create file: `WORKFLOW_ERROR_RESOLUTION_SUMMARY.md`
- [ ] Document:
  - Problems identified
  - Solutions implemented
  - Code changes made
  - Configuration changes
  - Test results
  - Deployment timestamp
  - Any remaining known issues

### Task 9.4: Archive Old Documentation (If Subscription Issue Resolved)
- [ ] If conversation_state issue was root cause, document in summary
- [ ] Archive debug logs if no longer needed
- [ ] Update architecture diagrams if applicable

---

## Success Criteria

### Must Pass (Critical)
- [ ] ✅ Donation button opens keypad in user DM
- [ ] ✅ Keypad interactions work correctly (digits, backspace, clear)
- [ ] ✅ Confirm button creates payment invoice
- [ ] ✅ Subscription button opens DM with payment gateway button
- [ ] ✅ Payment gateway button creates invoice (no "payment context not found" error)
- [ ] ✅ No errors in Cloud Run logs during test flows
- [ ] ✅ Both flows complete successfully in < 10 seconds

### Should Pass (Important)
- [ ] ✅ Success rate >= 95% for donation flow
- [ ] ✅ Success rate >= 95% for subscription flow
- [ ] ✅ Logs are clean and informative
- [ ] ✅ Error messages are user-friendly
- [ ] ✅ HTTP timeouts are handled gracefully

### Nice to Have (Optional)
- [ ] ✅ Response time < 2 seconds for button clicks
- [ ] ✅ Graceful fallback if GCDonationHandler is down
- [ ] ✅ Monitoring dashboards showing success rates
- [ ] ✅ Alerting configured for error spikes

---

## Rollback Plan

**If critical issues are discovered:**

### Rollback Step 1: Redeploy Previous Revision
```bash
# Get previous revision
PREVIOUS_REVISION=$(gcloud run revisions list \
  --service=gcbotcommand-10-26 \
  --region=us-central1 \
  --format='value(metadata.name)' \
  --sort-by=~metadata.creationTimestamp \
  --limit=2 | tail -1)

# Rollback to previous revision
gcloud run services update-traffic gcbotcommand-10-26 \
  --region=us-central1 \
  --to-revisions=$PREVIOUS_REVISION=100
```

### Rollback Step 2: Verify Service Health
```bash
# Check service status
gcloud run services describe gcbotcommand-10-26 --region=us-central1

# Test health endpoint
curl https://gcbotcommand-10-26-*.run.app/health
```

### Rollback Step 3: Notify & Document
- [ ] Document rollback reason
- [ ] Update BUGS.md with issue encountered
- [ ] Plan remediation strategy

---

## Appendix A: Key File Locations

```
GCBotCommand-10-26/
├── handlers/
│   └── callback_handler.py          ← MODIFY: Add donation handlers
├── config_manager.py                 ← MODIFY: Add GCDonationHandler URL
└── utils/
    └── http_client.py                ← VERIFY: Has post() method

GCDonationHandler-10-26/
├── service.py                        ← REFERENCE: Endpoint definitions
└── keypad_handler.py                 ← REFERENCE: Keypad logic

Secret Manager:
├── TELEGRAM_BOT_SECRET_NAME          ← EXISTING
├── GCPAYMENTGATEWAY_URL_SECRET       ← EXISTING
└── GCDONATIONHANDLER_URL_SECRET      ← CREATE NEW
```

---

## Appendix B: Service URLs Reference

```bash
# Get all service URLs
gcloud run services list \
  --platform=managed \
  --region=us-central1 \
  --format='table(metadata.name,status.url)'
```

**Expected Output:**
```
SERVICE_NAME                URL
gcbotcommand-10-26         https://gcbotcommand-10-26-*.run.app
gcdonationhandler-10-26    https://gcdonationhandler-10-26-*.run.app
gcpaymentgateway-10-26     https://gcpaymentgateway-10-26-*.run.app
gcbroadcastservice-10-26   https://gcbroadcastservice-10-26-*.run.app
```

---

## Appendix C: Useful Debugging Commands

```bash
# Watch logs in real-time
gcloud logging tail \
  "resource.type=cloud_run_revision AND resource.labels.service_name=gcbotcommand-10-26" \
  --format=json

# Search for specific error
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=gcbotcommand-10-26 AND textPayload=~'No payment context found'" \
  --limit=50 \
  --format=json

# Check service account permissions
gcloud projects get-iam-policy telepay-459221 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:291176869049-compute@developer.gserviceaccount.com"

# List all secrets
gcloud secrets list --format='table(name,createTime)'

# Test secret access
gcloud secrets versions access latest --secret="GCDONATIONHANDLER_URL_SECRET"
```

---

**Last Updated:** 2025-11-13
**Status:** ✅ READY FOR EXECUTION
**Estimated Completion Time:** 4-6 hours
**Next Action:** Begin Phase 1 - Pre-Implementation Investigation
