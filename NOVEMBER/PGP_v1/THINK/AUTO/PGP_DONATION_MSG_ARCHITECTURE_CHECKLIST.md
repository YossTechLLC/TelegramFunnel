# PGP Donation Message Architecture - Implementation Checklist

**Feature:** Enable donors to send encrypted VARCHAR(256) messages to channel owners upon payment completion

**Date:** 2025-11-18
**Status:** 🟡 PLANNING - Awaiting approval before implementation
**Complexity:** High (touches 6+ services, database schema, encryption, security)

---

## Executive Summary

### Goal
Enable donors/subscribers to send a personalized message (max 256 characters) to the channel owner when making a payment. The message must be:
1. ✅ Encrypted at rest (database storage)
2. ✅ Temporarily stored (deleted after confirmed delivery)
3. ✅ Delivered only when payment status = 'finished'
4. ✅ Sent to channel owner's `notification_id` via Telegram Bot API
5. ✅ Validated and sanitized for security

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DONATION MESSAGE FLOW (SECURE)                    │
│          🔒 MESSAGE NEVER LEAVES GOOGLE CLOUD INFRASTRUCTURE 🔒      │
└─────────────────────────────────────────────────────────────────────┘

1. MESSAGE COLLECTION (PGP_TELEPAY_v1 Bot)
   ├─ User initiates payment in Telegram bot
   ├─ Bot prompts: "Would you like to send a message to the channel owner?"
   ├─ User enters optional donation_message (max 256 chars)
   ├─ Message validated and encrypted using AES-256-GCM
   ├─ Encrypted message stored in donation_messages table with temporary order_id
   └─ Payment created with NOWPayments (NO MESSAGE IN METADATA)

2. PAYMENT CREATION (PGP_TELEPAY_v1 → NOWPayments)
   ├─ Generate unique order_id (contains closed_channel_id)
   ├─ Create payment via NOWPayments API
   ├─ Message remains encrypted in Google Cloud SQL (never sent to NOWPayments)
   └─ User completes payment on NOWPayments checkout

3. IPN CALLBACK (PGP_NP_IPN_v1)
   ├─ Receives IPN with status='finished' and order_id
   ├─ Validates payment status
   ├─ Updates payment_id in donation_messages table (links message to confirmed payment)
   └─ Triggers PGP_ORCHESTRATOR_v1 for payment processing

4. PAYMENT PROCESSING (PGP_ORCHESTRATOR_v1)
   ├─ Validates payment completion
   ├─ Retrieves encrypted message from DB using payment_id
   ├─ Passes encrypted message to PGP_NOTIFICATIONS_v1
   └─ Marks payment as processed

5. NOTIFICATION DELIVERY (PGP_NOTIFICATIONS_v1)
   ├─ Receives encrypted message
   ├─ Decrypts message using shared key
   ├─ Validates and sanitizes message content
   ├─ Formats notification for Telegram
   ├─ Sends to channel owner's notification_id
   ├─ Confirms delivery via Telegram API response
   └─ Triggers immediate message deletion

6. MESSAGE CLEANUP (Automated)
   ├─ Marks message as delivered (soft delete)
   ├─ Deletes encrypted message from DB within 24 hours
   └─ Logs delivery confirmation
```

**🔐 SECURITY BENEFITS:**
- ✅ Message never transmitted to NOWPayments servers
- ✅ Message never leaves Google Cloud infrastructure
- ✅ Encrypted at rest in Cloud SQL from creation to deletion
- ✅ Only accessible by authorized PGP services within VPC
- ✅ Automatic expiration (72 hours) for undelivered messages
- ✅ Immediate deletion after confirmed delivery

---

## Phase 1: Database Schema Changes (CRITICAL - DO FIRST)

### 1.1 Create Donation Messages Table

**Purpose:** Temporarily store encrypted donation messages until delivery confirmation

**File:** `TOOLS_SCRIPTS_TESTS/migrations/006_create_donation_messages.sql`

**Schema:**
```sql
-- ============================================================================
-- Table: donation_messages
-- Purpose: Encrypted donor messages (NEVER transmitted outside Google Cloud)
-- Flow: Created in PGP_TELEPAY → Updated by PGP_NP_IPN → Delivered by PGP_NOTIFICATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS donation_messages (
    id SERIAL PRIMARY KEY,

    -- Reference identifiers
    payment_id BIGINT,                            -- NULL initially, populated by IPN callback
    order_id VARCHAR(100) NOT NULL UNIQUE,        -- Links message to payment (created in bot)
    closed_channel_id VARCHAR(14) NOT NULL,       -- Extracted from order_id
    notification_id BIGINT NOT NULL,              -- Channel owner's Telegram chat ID

    -- Encrypted message data (AES-256-GCM)
    encrypted_message TEXT NOT NULL,              -- Base64-encoded ciphertext
    encryption_nonce VARCHAR(64) NOT NULL,        -- Unique 96-bit nonce for GCM mode
    encryption_tag VARCHAR(64) NOT NULL,          -- 128-bit authentication tag

    -- Message metadata
    original_length SMALLINT NOT NULL,            -- Original plaintext length (1-256)
    message_language VARCHAR(10),                 -- ISO 639-1 code (optional, future use)

    -- Delivery tracking
    delivery_status VARCHAR(20) NOT NULL DEFAULT 'awaiting_payment',  -- awaiting_payment, pending, delivered, failed, expired
    delivery_attempted_at TIMESTAMP,
    delivery_confirmed_at TIMESTAMP,
    telegram_message_id BIGINT,                   -- Proof of delivery
    delivery_error TEXT,                          -- Error message if failed

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Message created in bot
    payment_confirmed_at TIMESTAMP,               -- IPN callback timestamp
    expires_at TIMESTAMP NOT NULL,                -- Auto-expire after 72 hours from creation
    deleted_at TIMESTAMP,                         -- Soft delete timestamp

    -- Constraints
    CONSTRAINT fk_payment_id FOREIGN KEY (payment_id)
        REFERENCES processed_payments(payment_id) ON DELETE CASCADE,
    CONSTRAINT check_message_length
        CHECK (original_length > 0 AND original_length <= 256),
    CONSTRAINT check_delivery_status
        CHECK (delivery_status IN ('awaiting_payment', 'pending', 'delivered', 'failed', 'expired')),
    CONSTRAINT check_expires_at
        CHECK (expires_at > created_at),
    CONSTRAINT unique_order_id UNIQUE (order_id)
);

-- Indexes
CREATE INDEX idx_donation_messages_payment_id ON donation_messages(payment_id) WHERE payment_id IS NOT NULL;
CREATE INDEX idx_donation_messages_order_id ON donation_messages(order_id);
CREATE INDEX idx_donation_messages_delivery_status ON donation_messages(delivery_status);
CREATE INDEX idx_donation_messages_expires_at ON donation_messages(expires_at)
    WHERE delivery_status IN ('awaiting_payment', 'pending');
CREATE INDEX idx_donation_messages_notification_id ON donation_messages(notification_id);
CREATE INDEX idx_donation_messages_created_at ON donation_messages(created_at);

-- Comments
COMMENT ON TABLE donation_messages IS 'PGP_v1: Encrypted donor messages (NEVER leaves Google Cloud infrastructure)';
COMMENT ON COLUMN donation_messages.payment_id IS 'NULL until IPN confirms payment, then populated by PGP_NP_IPN_v1';
COMMENT ON COLUMN donation_messages.order_id IS 'Generated in PGP_TELEPAY_v1, links message to payment';
COMMENT ON COLUMN donation_messages.encrypted_message IS 'AES-256-GCM encrypted message (Base64)';
COMMENT ON COLUMN donation_messages.encryption_nonce IS 'GCM nonce (must be unique per message)';
COMMENT ON COLUMN donation_messages.encryption_tag IS 'GCM authentication tag for integrity verification';
COMMENT ON COLUMN donation_messages.delivery_status IS 'awaiting_payment = not yet paid, pending = paid but not delivered, delivered = sent, failed = error, expired = timeout';
COMMENT ON COLUMN donation_messages.expires_at IS 'Auto-expires 72 hours from creation (not from payment)';
```

**Rollback File:** `TOOLS_SCRIPTS_TESTS/migrations/006_rollback.sql`
```sql
-- Rollback migration 006
DROP INDEX IF EXISTS idx_donation_messages_payment_id;
DROP INDEX IF EXISTS idx_donation_messages_order_id;
DROP INDEX IF EXISTS idx_donation_messages_delivery_status;
DROP INDEX IF EXISTS idx_donation_messages_expires_at;
DROP INDEX IF EXISTS idx_donation_messages_notification_id;
DROP TABLE IF EXISTS donation_messages CASCADE;
```

**Tasks:**
- [ ] Create migration file `006_create_donation_messages.sql`
- [ ] Create rollback file `006_rollback.sql`
- [ ] Test migration on local database
- [ ] Verify indexes are created
- [ ] Verify foreign key constraints work
- [ ] Document in `THINK/DATABASE_SCHEMA_DOCUMENTATION.md`
- [ ] Add to migration execution checklist

---

## Phase 2: PGP_COMMON Encryption Utilities (FOUNDATION)

### 2.1 Create Message Encryption Module

**Purpose:** Centralized encryption/decryption for donation messages using AES-256-GCM

**File:** `PGP_COMMON/utils/message_encryption.py`

**Implementation:**
```python
"""
Message Encryption Utilities for PGP_v1
Handles encryption/decryption of donation messages using AES-256-GCM
"""
import os
import base64
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from PGP_COMMON.logging import get_logger

logger = get_logger(__name__)

class MessageEncryptor:
    """
    Handles encryption/decryption of donation messages.
    Uses AES-256-GCM for authenticated encryption.
    """

    def __init__(self, encryption_key: str):
        """
        Initialize encryptor with base64-encoded 256-bit key.

        Args:
            encryption_key: Base64-encoded 32-byte key from Secret Manager
                           (e.g., DONATION_MESSAGE_ENCRYPTION_KEY)

        Raises:
            ValueError: If key is invalid format or wrong length
        """
        try:
            self.key = base64.b64decode(encryption_key)
            if len(self.key) != 32:  # AES-256 requires 32 bytes
                raise ValueError(f"Invalid key length: {len(self.key)} (expected 32)")
            logger.debug("✅ [ENCRYPTION] MessageEncryptor initialized with AES-256-GCM")
        except Exception as e:
            logger.error(f"❌ [ENCRYPTION] Failed to initialize: {e}", exc_info=True)
            raise

    def encrypt_message(self, message: str) -> Tuple[str, str, str]:
        """
        Encrypt a donation message using AES-256-GCM.

        Args:
            message: Plain text message (max 256 characters)

        Returns:
            Tuple of (encrypted_message_b64, nonce_b64, tag_b64)

        Raises:
            ValueError: If message exceeds 256 characters or is empty
        """
        # Validate message
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        message = message.strip()
        if len(message) > 256:
            raise ValueError(f"Message too long: {len(message)} characters (max 256)")

        # Generate random 96-bit nonce (12 bytes, recommended for GCM)
        nonce = os.urandom(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Encrypt message
        message_bytes = message.encode('utf-8')
        ciphertext = encryptor.update(message_bytes) + encryptor.finalize()

        # Get authentication tag
        tag = encryptor.tag

        # Base64 encode for storage
        encrypted_b64 = base64.b64encode(ciphertext).decode('utf-8')
        nonce_b64 = base64.b64encode(nonce).decode('utf-8')
        tag_b64 = base64.b64encode(tag).decode('utf-8')

        logger.info(f"✅ [ENCRYPTION] Message encrypted ({len(message)} chars)")
        logger.debug(f"🔐 [ENCRYPTION] Ciphertext length: {len(ciphertext)} bytes")

        return encrypted_b64, nonce_b64, tag_b64

    def decrypt_message(self, encrypted_b64: str, nonce_b64: str, tag_b64: str) -> str:
        """
        Decrypt a donation message using AES-256-GCM.

        Args:
            encrypted_b64: Base64-encoded ciphertext
            nonce_b64: Base64-encoded nonce
            tag_b64: Base64-encoded authentication tag

        Returns:
            Decrypted plain text message

        Raises:
            ValueError: If decryption fails or authentication tag is invalid
        """
        try:
            # Decode from base64
            ciphertext = base64.b64decode(encrypted_b64)
            nonce = base64.b64decode(nonce_b64)
            tag = base64.b64decode(tag_b64)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # Decrypt message
            message_bytes = decryptor.update(ciphertext) + decryptor.finalize()
            message = message_bytes.decode('utf-8')

            logger.info(f"✅ [DECRYPTION] Message decrypted ({len(message)} chars)")
            return message

        except Exception as e:
            logger.error(f"❌ [DECRYPTION] Failed to decrypt message: {e}", exc_info=True)
            raise ValueError("Decryption failed - message may be corrupted or tampered")


def validate_donation_message(message: str) -> Tuple[bool, Optional[str]]:
    """
    Validate donation message content and format.

    Args:
        message: Donation message to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_reason) if invalid
    """
    # Check empty
    if not message or not message.strip():
        return False, "Message cannot be empty"

    message = message.strip()

    # Check length
    if len(message) > 256:
        return False, f"Message too long ({len(message)} characters, max 256)"

    # Check for null bytes (security)
    if '\x00' in message:
        return False, "Message contains invalid null bytes"

    # Check for control characters (except newline, tab)
    for char in message:
        if ord(char) < 32 and char not in ['\n', '\t']:
            return False, f"Message contains invalid control character: {repr(char)}"

    # Check for potentially malicious patterns
    malicious_patterns = [
        '<script',
        'javascript:',
        'onerror=',
        'onclick=',
        '<?php',
        '#!/',
    ]

    message_lower = message.lower()
    for pattern in malicious_patterns:
        if pattern in message_lower:
            return False, f"Message contains potentially malicious pattern: {pattern}"

    logger.debug(f"✅ [VALIDATION] Message validated ({len(message)} chars)")
    return True, None


def sanitize_donation_message(message: str) -> str:
    """
    Sanitize donation message for safe display in Telegram.

    Args:
        message: Raw donation message

    Returns:
        Sanitized message safe for Telegram display
    """
    # Strip whitespace
    message = message.strip()

    # Remove null bytes
    message = message.replace('\x00', '')

    # Escape Telegram MarkdownV2 special characters
    # MarkdownV2 special chars: _ * [ ] ( ) ~ ` > # + - = | { } . !
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        message = message.replace(char, f'\\{char}')

    # Limit consecutive newlines to 2
    while '\n\n\n' in message:
        message = message.replace('\n\n\n', '\n\n')

    logger.debug(f"✅ [SANITIZATION] Message sanitized")
    return message
```

**Tasks:**
- [ ] Create `PGP_COMMON/utils/message_encryption.py`
- [ ] Add `cryptography>=41.0.0` to all service requirements.txt
- [ ] Generate encryption key: `python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"`
- [ ] Create Secret Manager secret: `DONATION_MESSAGE_ENCRYPTION_KEY`
- [ ] Update `PGP_COMMON/utils/__init__.py` with exports
- [ ] Write unit tests for encryption/decryption
- [ ] Test with Unicode characters (emoji, non-Latin scripts)
- [ ] Test with edge cases (empty, max length, special chars)

---

### 2.2 Update PGP_COMMON Exports

**File:** `PGP_COMMON/utils/__init__.py`

**Add:**
```python
from PGP_COMMON.utils.message_encryption import (
    MessageEncryptor,
    validate_donation_message,
    sanitize_donation_message
)

__all__ = [
    # ... existing exports ...
    "MessageEncryptor",
    "validate_donation_message",
    "sanitize_donation_message",
]
```

**Tasks:**
- [ ] Add message encryption exports to `__init__.py`
- [ ] Verify imports work from all services
- [ ] Update type hints and docstrings

---

## Phase 3: PGP_TELEPAY_v1 Changes (MESSAGE COLLECTION - ENTRY POINT)

### 3.1 Add Donation Message Collection to Bot Conversation

**Purpose:** Collect optional donation message from user BEFORE creating NOWPayments payment

**File:** `PGP_TELEPAY_v1/bot/conversations/donation_conversation.py` (or subscription handler)

**Changes:**

1. **Import encryption utilities:**
```python
from PGP_COMMON.utils import (
    MessageEncryptor,
    validate_donation_message,
    sanitize_donation_message
)
```

2. **Initialize encryptor in main bot file:**
```python
# In PGP_TELEPAY_v1/pgp_telepay_v1.py (after config initialization)

# ============================================================================
# MESSAGE ENCRYPTION INITIALIZATION
# ============================================================================
DONATION_MESSAGE_ENCRYPTION_KEY = (os.getenv('DONATION_MESSAGE_ENCRYPTION_KEY') or '').strip() or None

message_encryptor = None
if DONATION_MESSAGE_ENCRYPTION_KEY:
    try:
        message_encryptor = MessageEncryptor(DONATION_MESSAGE_ENCRYPTION_KEY)
        logger.info("✅ [ENCRYPTION] Message encryptor initialized")
    except Exception as e:
        logger.error(f"❌ [ENCRYPTION] Failed to initialize encryptor: {e}", exc_info=True)
        logger.warning("⚠️ [ENCRYPTION] Donation messages will be disabled")
else:
    logger.warning("⚠️ [ENCRYPTION] DONATION_MESSAGE_ENCRYPTION_KEY not configured")
```

3. **Add message collection step to payment flow:**
```python
# In donation/subscription payment flow (BEFORE creating NOWPayments invoice)

async def ask_for_donation_message(update: Update, context: CallbackContext) -> int:
    """
    Ask user if they want to send a message to the channel owner.
    This happens AFTER payment amount is selected, BEFORE NOWPayments invoice creation.
    """
    user_id = update.effective_user.id

    # Skip if message encryption not configured
    if not message_encryptor:
        logger.debug(f"🔇 [DONATION_MSG] Feature disabled for user {user_id}")
        return await create_payment_invoice(update, context)

    # Ask if user wants to send a message
    keyboard = [
        [InlineKeyboardButton("✉️ Yes, send a message", callback_data='donation_msg_yes')],
        [InlineKeyboardButton("⏭️ Skip", callback_data='donation_msg_no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        "💬 *Optional Message to Channel Owner*\n\n"
        "Would you like to send a personal message to the channel owner?\n\n"
        "_Your message will be encrypted and delivered after payment is confirmed._"
    )

    await update.callback_query.edit_message_text(
        text=message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    return WAITING_FOR_MESSAGE_CHOICE


async def handle_donation_message_choice(update: Update, context: CallbackContext) -> int:
    """Handle user's choice to send or skip message."""
    query = update.callback_query
    await query.answer()

    if query.data == 'donation_msg_no':
        # User skipped message - proceed directly to payment
        context.user_data['donation_message'] = None
        return await create_payment_invoice(update, context)

    elif query.data == 'donation_msg_yes':
        # Prompt for message
        await query.edit_message_text(
            text=(
                "📝 *Enter Your Message*\n\n"
                "Type your message to the channel owner (max 256 characters).\n\n"
                "⚠️ _Message will be encrypted and sent after payment confirmation._\n\n"
                "Type /cancel to skip this step."
            ),
            parse_mode='Markdown'
        )

        return WAITING_FOR_MESSAGE_TEXT


async def receive_donation_message_text(update: Update, context: CallbackContext) -> int:
    """Receive and validate donation message text."""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    # Check for cancel
    if message_text == '/cancel':
        context.user_data['donation_message'] = None
        await update.message.reply_text("✅ Skipped message. Proceeding with payment...")
        return await create_payment_invoice(update, context)

    # Validate message
    is_valid, error_msg = validate_donation_message(message_text)

    if not is_valid:
        logger.warning(f"⚠️ [DONATION_MSG] Invalid message from user {user_id}: {error_msg}")
        await update.message.reply_text(
            f"❌ *Invalid Message*\n\n{error_msg}\n\nPlease try again or type /cancel to skip.",
            parse_mode='Markdown'
        )
        return WAITING_FOR_MESSAGE_TEXT

    # Store message in context for encryption after order_id generation
    context.user_data['donation_message'] = message_text

    logger.info(f"✅ [DONATION_MSG] Message received from user {user_id} ({len(message_text)} chars)")

    await update.message.reply_text(
        "✅ Message received! Creating your payment invoice..."
    )

    # Proceed to payment creation
    return await create_payment_invoice(update, context)
```

4. **Encrypt and store message BEFORE creating NOWPayments invoice:**
```python
# In create_payment_invoice() function, BEFORE calling NOWPayments API

def create_payment_invoice(update: Update, context: CallbackContext) -> int:
    """Create NOWPayments invoice and store encrypted donation message."""

    user_id = update.effective_user.id
    closed_channel_id = context.user_data['closed_channel_id']
    tier = context.user_data.get('tier', 1)
    amount_usd = context.user_data['amount_usd']

    # Generate order_id FIRST (before NOWPayments API call)
    timestamp = int(time.time())
    order_id = f"user_{user_id}_channel_{closed_channel_id}_tier_{tier}_ts_{timestamp}"

    # ======================================================================
    # ENCRYPT AND STORE DONATION MESSAGE (IF PROVIDED)
    # ======================================================================
    donation_message_raw = context.user_data.get('donation_message')

    if donation_message_raw and message_encryptor:
        try:
            logger.info(f"🔐 [DONATION_MSG] Encrypting message for order {order_id}")

            # Encrypt message
            encrypted_msg, nonce, tag = message_encryptor.encrypt_message(donation_message_raw)

            # Get notification_id from database
            notification_id = db_manager.get_notification_id_by_channel(closed_channel_id)

            if notification_id:
                # Store encrypted message in donation_messages table
                message_data = {
                    'order_id': order_id,
                    'closed_channel_id': closed_channel_id,
                    'notification_id': notification_id,
                    'encrypted_message': encrypted_msg,
                    'encryption_nonce': nonce,
                    'encryption_tag': tag,
                    'original_length': len(donation_message_raw),
                    'expires_at': 'NOW() + INTERVAL \'72 hours\''
                }

                stored = db_manager.store_donation_message_pending(message_data)

                if stored:
                    logger.info(f"✅ [DONATION_MSG] Message encrypted and stored")
                    logger.info(f"   Order ID: {order_id}")
                    logger.info(f"   Notification ID: {notification_id}")
                else:
                    logger.error(f"❌ [DONATION_MSG] Failed to store encrypted message")
            else:
                logger.warning(f"⚠️ [DONATION_MSG] No notification_id for channel {closed_channel_id}")

        except Exception as e:
            logger.error(f"❌ [DONATION_MSG] Encryption failed: {e}", exc_info=True)
            # Don't fail payment if message encryption fails - just skip message

    # ======================================================================
    # NOW CREATE NOWPAYMENTS INVOICE (MESSAGE NEVER SENT TO NOWPAYMENTS)
    # ======================================================================
    nowpayments_invoice = create_nowpayments_invoice(
        order_id=order_id,
        amount_usd=amount_usd,
        # NO donation_message parameter!
    )

    # ... rest of invoice creation logic ...
```

**Tasks:**
- [ ] Add message collection conversation states
- [ ] Implement `ask_for_donation_message()` handler
- [ ] Implement `handle_donation_message_choice()` handler
- [ ] Implement `receive_donation_message_text()` handler
- [ ] Encrypt message BEFORE NOWPayments API call
- [ ] Store encrypted message in database with `awaiting_payment` status
- [ ] Add conversation flow to ConversationHandler
- [ ] Test message collection with valid input
- [ ] Test message collection with invalid input (>256 chars, special chars)
- [ ] Test skip/cancel functionality
- [ ] Test encryption failure handling

---

### 3.2 Add Database Method for Message Storage

**File:** `PGP_TELEPAY_v1/database_manager.py`

**Add methods:**
```python
def get_notification_id_by_channel(self, closed_channel_id: str) -> Optional[int]:
    """
    Get channel owner's notification_id.

    Args:
        closed_channel_id: Channel ID (e.g., "-1003268562225")

    Returns:
        notification_id (BIGINT) or None if not found
    """
    try:
        query = """
            SELECT notification_id
            FROM main_clients_database
            WHERE closed_channel_id = %s
            AND notification_status = TRUE
            LIMIT 1
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (closed_channel_id,))
                result = cur.fetchone()

                if result and result[0]:
                    logger.info(f"✅ [DB] Found notification_id: {result[0]}")
                    return result[0]
                else:
                    logger.warning(f"⚠️ [DB] No notification_id for channel {closed_channel_id}")
                    return None

    except Exception as e:
        logger.error(f"❌ [DB] Failed to get notification_id: {e}", exc_info=True)
        return None


def store_donation_message_pending(self, message_data: dict) -> bool:
    """
    Store encrypted donation message BEFORE payment is confirmed.
    Status: 'awaiting_payment' (payment_id is NULL)

    Args:
        message_data: Dictionary containing:
            - order_id: VARCHAR(100)
            - closed_channel_id: VARCHAR(14)
            - notification_id: BIGINT
            - encrypted_message: TEXT (Base64)
            - encryption_nonce: VARCHAR(64)
            - encryption_tag: VARCHAR(64)
            - original_length: SMALLINT
            - expires_at: SQL expression

    Returns:
        True if stored successfully, False otherwise
    """
    try:
        query = """
            INSERT INTO donation_messages (
                order_id,
                closed_channel_id,
                notification_id,
                encrypted_message,
                encryption_nonce,
                encryption_tag,
                original_length,
                delivery_status,
                expires_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                'awaiting_payment',
                {expires_at_expr}
            )
        """.format(expires_at_expr=message_data.get('expires_at', "NOW() + INTERVAL '72 hours'"))

        params = (
            message_data['order_id'],
            message_data['closed_channel_id'],
            message_data['notification_id'],
            message_data['encrypted_message'],
            message_data['encryption_nonce'],
            message_data['encryption_tag'],
            message_data['original_length']
        )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()

                logger.info(f"✅ [DB] Donation message stored (awaiting payment)")
                logger.info(f"   Order ID: {message_data['order_id']}")
                return True

    except Exception as e:
        logger.error(f"❌ [DB] Failed to store donation message: {e}", exc_info=True)
        return False
```

**Tasks:**
- [ ] Add `get_notification_id_by_channel()` method
- [ ] Add `store_donation_message_pending()` method
- [ ] Test database insertion with NULL payment_id
- [ ] Test UNIQUE constraint on order_id
- [ ] Handle duplicate order_id gracefully
- [ ] Add transaction support

---

## Phase 4: PGP_NP_IPN_v1 Changes (PAYMENT CONFIRMATION)

### 4.1 Update Donation Message with Payment ID

**Purpose:** Link encrypted message to confirmed payment when IPN callback received

**File:** `PGP_NP_IPN_v1/pgp_np_ipn_v1.py`

**Changes:**

1. **Update donation message with payment_id (after payment status validation, ~line 330):**
```python
# ============================================================================
# UPDATE DONATION MESSAGE WITH PAYMENT_ID (IF EXISTS)
# ============================================================================
# Check if there's a pending donation message for this order_id
# Message was created in PGP_TELEPAY_v1 with status='awaiting_payment'

if payment_status == 'finished' and db_manager:
    try:
        logger.info(f"🔍 [DONATION_MSG] Checking for pending donation message")
        logger.info(f"   Order ID: {order_id}")

        # Update message with payment_id and change status to 'pending'
        updated = db_manager.link_donation_message_to_payment(
            order_id=order_id,
            payment_id=ipn_data.get('payment_id')
        )

        if updated:
            logger.info(f"✅ [DONATION_MSG] Message linked to payment {ipn_data.get('payment_id')}")
            logger.info(f"   Status updated: awaiting_payment → pending")
        else:
            logger.debug(f"ℹ️ [DONATION_MSG] No pending message for order {order_id}")

    except Exception as e:
        logger.error(f"❌ [DONATION_MSG] Failed to link message to payment: {e}", exc_info=True)
        # Don't fail the entire IPN - just log and continue
```

**Tasks:**
- [ ] Add donation message linking logic to IPN handler
- [ ] Update message status from 'awaiting_payment' to 'pending'
- [ ] Populate payment_id in donation_messages table
- [ ] Add error handling for database failures
- [ ] Test with existing donation message
- [ ] Test without donation message (no-op)
- [ ] Test with expired message (should not link)
- [ ] Log all linking attempts

---

### 4.2 Update Database Manager

**File:** `PGP_NP_IPN_v1/database_manager.py`

**Add method:**
```python
def link_donation_message_to_payment(self, order_id: str, payment_id: int) -> bool:
    """
    Link an existing donation message (created in PGP_TELEPAY) to a confirmed payment.
    Updates payment_id and changes status from 'awaiting_payment' to 'pending'.

    Args:
        order_id: NOWPayments order_id
        payment_id: NOWPayments payment_id from IPN callback

    Returns:
        True if message found and updated, False if no message exists
    """
    try:
        query = """
            UPDATE donation_messages
            SET
                payment_id = %s,
                delivery_status = 'pending',
                payment_confirmed_at = NOW()
            WHERE order_id = %s
            AND delivery_status = 'awaiting_payment'
            AND expires_at > NOW()
            RETURNING id
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (payment_id, order_id))
                result = cur.fetchone()
                conn.commit()

                if result:
                    message_id = result[0]
                    logger.info(f"✅ [DB] Donation message {message_id} linked to payment {payment_id}")
                    logger.info(f"   Order ID: {order_id}")
                    logger.info(f"   Status: awaiting_payment → pending")
                    return True
                else:
                    logger.debug(f"ℹ️ [DB] No awaiting message for order {order_id}")
                    return False

    except Exception as e:
        logger.error(f"❌ [DB] Failed to link donation message: {e}", exc_info=True)
        return False
```

**Tasks:**
- [ ] Add `link_donation_message_to_payment()` method
- [ ] Test updating existing message with payment_id
- [ ] Test with no existing message (should return False gracefully)
- [ ] Test with expired message (should not update)
- [ ] Test with already-linked message (should not update)
- [ ] Add transaction support
- [ ] Use RETURNING clause to confirm update

---

## Phase 5: PGP_ORCHESTRATOR_v1 Changes (PAYMENT ORCHESTRATION)

### 5.1 Retrieve and Pass Donation Message to PGP_NOTIFICATIONS

**Purpose:** Retrieve encrypted message and trigger notification delivery

**File:** `PGP_ORCHESTRATOR_v1/pgp_orchestrator_v1.py`

**Changes:**

1. **Add method to retrieve donation message (after subscription processing, ~line 400):**
```python
# ============================================================================
# DONATION MESSAGE RETRIEVAL
# ============================================================================
def get_pending_donation_message(payment_id: int) -> Optional[dict]:
    """
    Retrieve pending donation message for a payment.

    Args:
        payment_id: NOWPayments payment_id

    Returns:
        Dictionary with message data or None if not found
    """
    try:
        query = """
            SELECT
                id,
                encrypted_message,
                encryption_nonce,
                encryption_tag,
                notification_id,
                original_length
            FROM donation_messages
            WHERE payment_id = %s
            AND delivery_status = 'pending'
            AND expires_at > NOW()
            LIMIT 1
        """

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (payment_id,))
                result = cur.fetchone()

                if result:
                    logger.info(f"✅ [DONATION] Found pending message for payment {payment_id}")
                    return {
                        'message_id': result[0],
                        'encrypted_message': result[1],
                        'encryption_nonce': result[2],
                        'encryption_tag': result[3],
                        'notification_id': result[4],
                        'original_length': result[5]
                    }
                else:
                    logger.debug(f"ℹ️ [DONATION] No pending message for payment {payment_id}")
                    return None

    except Exception as e:
        logger.error(f"❌ [DONATION] Failed to retrieve message: {e}", exc_info=True)
        return None
```

2. **Trigger notification with donation message (after PGP_INVITE trigger, ~line 550):**
```python
# ============================================================================
# DONATION MESSAGE NOTIFICATION (IF PRESENT)
# ============================================================================
donation_message_data = get_pending_donation_message(payment_id)

if donation_message_data and GCNOTIFICATIONSERVICE_URL:
    logger.info(f"📬 [DONATION] Triggering donation message notification")
    logger.info(f"   Message ID: {donation_message_data['message_id']}")
    logger.info(f"   Length: {donation_message_data['original_length']} chars")
    logger.info(f"   Notification ID: {donation_message_data['notification_id']}")

    try:
        # Trigger PGP_NOTIFICATIONS with encrypted message
        notification_payload = {
            'notification_type': 'donation_message',
            'message_id': donation_message_data['message_id'],
            'encrypted_message': donation_message_data['encrypted_message'],
            'encryption_nonce': donation_message_data['encryption_nonce'],
            'encryption_tag': donation_message_data['encryption_tag'],
            'notification_id': donation_message_data['notification_id'],
            'payment_id': payment_id,
            'closed_channel_id': closed_channel_id
        }

        response = requests.post(
            f"{GCNOTIFICATIONSERVICE_URL}/send-donation-message",
            json=notification_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            logger.info(f"✅ [DONATION] Notification triggered successfully")
        else:
            logger.warning(f"⚠️ [DONATION] Notification failed: HTTP {response.status_code}")
            logger.warning(f"⚠️ [DONATION] Response: {response.text}")

    except Exception as e:
        logger.error(f"❌ [DONATION] Failed to trigger notification: {e}", exc_info=True)
        # Don't fail the entire payment processing - message will expire after 72h
```

**Tasks:**
- [ ] Add `get_pending_donation_message()` function
- [ ] Retrieve encrypted message after payment processing
- [ ] Trigger PGP_NOTIFICATIONS with message data
- [ ] Handle missing GCNOTIFICATIONSERVICE_URL gracefully
- [ ] Test with and without donation messages
- [ ] Add retry logic for notification failures
- [ ] Log all donation message events

---

## Phase 6: PGP_NOTIFICATIONS_v1 Changes (MESSAGE DELIVERY)

### 6.1 Create Donation Message Endpoint

**Purpose:** Decrypt and deliver donation message to channel owner via Telegram

**File:** `PGP_NOTIFICATIONS_v1/pgp_notifications_v1.py`

**Changes:**

1. **Import encryption utilities:**
```python
from PGP_COMMON.utils import (
    MessageEncryptor,
    sanitize_donation_message
)
```

2. **Initialize encryptor:**
```python
# ============================================================================
# MESSAGE ENCRYPTION INITIALIZATION
# ============================================================================
DONATION_MESSAGE_ENCRYPTION_KEY = os.getenv('DONATION_MESSAGE_ENCRYPTION_KEY')

message_encryptor = None
if DONATION_MESSAGE_ENCRYPTION_KEY:
    try:
        message_encryptor = MessageEncryptor(DONATION_MESSAGE_ENCRYPTION_KEY)
        logger.info("✅ [ENCRYPTION] Message encryptor initialized")
    except Exception as e:
        logger.error(f"❌ [ENCRYPTION] Failed to initialize: {e}", exc_info=True)
```

3. **Add new endpoint (after `/send-notification`):**
```python
@app.route('/send-donation-message', methods=['POST'])
def send_donation_message():
    """
    Decrypt and deliver donation message to channel owner.

    Request Body:
    {
        "message_id": 123,
        "encrypted_message": "base64...",
        "encryption_nonce": "base64...",
        "encryption_tag": "base64...",
        "notification_id": 6271402111,
        "payment_id": 987654321,
        "closed_channel_id": "-1003268562225"
    }

    Response:
    {
        "status": "success",
        "telegram_message_id": 456,
        "delivered_at": "2025-11-18T14:32:15Z"
    }
    """
    try:
        # Validate request
        if not request.is_json:
            logger.warning("⚠️ [DONATION] Non-JSON request")
            abort(400, "Content-Type must be application/json")

        data = request.get_json()

        # Validate required fields
        required = ['message_id', 'encrypted_message', 'encryption_nonce',
                   'encryption_tag', 'notification_id', 'payment_id']
        if not all(k in data for k in required):
            missing = [k for k in required if k not in data]
            logger.warning(f"⚠️ [DONATION] Missing fields: {missing}")
            abort(400, f"Missing required fields: {missing}")

        if not message_encryptor:
            logger.error("❌ [DONATION] Encryption not configured")
            abort(500, "Message encryption not available")

        # Extract data
        message_id = data['message_id']
        encrypted_msg = data['encrypted_message']
        nonce = data['encryption_nonce']
        tag = data['encryption_tag']
        notification_id = data['notification_id']
        payment_id = data['payment_id']
        closed_channel_id = data.get('closed_channel_id', 'Unknown')

        logger.info(f"📬 [DONATION] Processing donation message")
        logger.info(f"   Message ID: {message_id}")
        logger.info(f"   Notification ID: {notification_id}")
        logger.info(f"   Payment ID: {payment_id}")

        # Decrypt message
        try:
            decrypted_msg = message_encryptor.decrypt_message(encrypted_msg, nonce, tag)
            logger.info(f"✅ [DONATION] Message decrypted ({len(decrypted_msg)} chars)")
        except Exception as e:
            logger.error(f"❌ [DONATION] Decryption failed: {e}", exc_info=True)

            # Mark message as failed in database
            handler = app.config['notification_handler']
            handler.mark_message_delivery_failed(message_id, str(e))

            abort(500, "Message decryption failed")

        # Sanitize message for Telegram
        sanitized_msg = sanitize_donation_message(decrypted_msg)

        # Format notification
        telegram_message = (
            "💬 *New Donation Message*\\n\\n"
            f"_From: Subscriber/Donor_\\n"
            f"_Payment ID:_ `{payment_id}`\\n"
            f"_Channel:_ `{closed_channel_id}`\\n\\n"
            "📝 *Message:*\\n"
            f"{sanitized_msg}\\n\\n"
            "━━━━━━━━━━━━━━━━\\n"
            f"_Sent via PayGatePrime_"
        )

        # Send via Telegram
        telegram_client = app.config['telegram_client']
        telegram_msg_id = telegram_client.send_message(
            chat_id=notification_id,
            text=telegram_message,
            parse_mode='MarkdownV2'
        )

        if telegram_msg_id:
            logger.info(f"✅ [DONATION] Message delivered successfully")
            logger.info(f"   Telegram Message ID: {telegram_msg_id}")

            # Mark as delivered in database
            handler = app.config['notification_handler']
            handler.mark_message_delivered(message_id, telegram_msg_id)

            return jsonify({
                'status': 'success',
                'telegram_message_id': telegram_msg_id,
                'delivered_at': datetime.utcnow().isoformat() + 'Z'
            }), 200
        else:
            logger.error(f"❌ [DONATION] Telegram delivery failed")

            # Mark as failed
            handler = app.config['notification_handler']
            handler.mark_message_delivery_failed(message_id, "Telegram API returned None")

            return jsonify({
                'status': 'failed',
                'message': 'Telegram delivery failed'
            }), 500

    except Exception as e:
        logger.error(f"❌ [DONATION] Unexpected error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
```

**Tasks:**
- [ ] Add encryption imports
- [ ] Initialize MessageEncryptor
- [ ] Create `/send-donation-message` endpoint
- [ ] Decrypt message
- [ ] Sanitize for Telegram MarkdownV2
- [ ] Format notification message
- [ ] Send via Telegram Bot API
- [ ] Handle delivery confirmation
- [ ] Mark message as delivered
- [ ] Test with various message formats
- [ ] Test with emoji and Unicode
- [ ] Test error handling (decryption failures, Telegram API errors)

---

### 6.2 Update Notification Handler

**File:** `PGP_NOTIFICATIONS_v1/notification_handler.py`

**Add methods:**
```python
def mark_message_delivered(self, message_id: int, telegram_message_id: int) -> bool:
    """
    Mark donation message as delivered and schedule deletion.

    Args:
        message_id: Database ID of donation_messages record
        telegram_message_id: Telegram message ID (proof of delivery)

    Returns:
        True if marked successfully, False otherwise
    """
    try:
        query = """
            UPDATE donation_messages
            SET
                delivery_status = 'delivered',
                delivery_confirmed_at = NOW(),
                telegram_message_id = %s
            WHERE id = %s
        """

        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (telegram_message_id, message_id))
                conn.commit()

                logger.info(f"✅ [DONATION] Message {message_id} marked as delivered")
                logger.info(f"   Telegram Message ID: {telegram_message_id}")

                # Schedule deletion (immediate or delayed based on policy)
                self._schedule_message_deletion(message_id)

                return True

    except Exception as e:
        logger.error(f"❌ [DONATION] Failed to mark delivered: {e}", exc_info=True)
        return False


def mark_message_delivery_failed(self, message_id: int, error_message: str) -> bool:
    """
    Mark donation message delivery as failed.

    Args:
        message_id: Database ID of donation_messages record
        error_message: Reason for failure

    Returns:
        True if marked successfully, False otherwise
    """
    try:
        query = """
            UPDATE donation_messages
            SET
                delivery_status = 'failed',
                delivery_attempted_at = NOW(),
                delivery_error = %s
            WHERE id = %s
        """

        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (error_message[:500], message_id))  # Limit error message length
                conn.commit()

                logger.warning(f"⚠️ [DONATION] Message {message_id} marked as failed")
                logger.warning(f"   Error: {error_message}")
                return True

    except Exception as e:
        logger.error(f"❌ [DONATION] Failed to mark as failed: {e}", exc_info=True)
        return False


def _schedule_message_deletion(self, message_id: int) -> None:
    """
    Schedule immediate deletion of delivered message (soft delete).

    Args:
        message_id: Database ID to delete
    """
    try:
        query = """
            UPDATE donation_messages
            SET deleted_at = NOW()
            WHERE id = %s
        """

        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (message_id,))
                conn.commit()

                logger.info(f"✅ [DONATION] Message {message_id} deleted (soft delete)")

    except Exception as e:
        logger.error(f"❌ [DONATION] Failed to delete message: {e}", exc_info=True)
```

**Tasks:**
- [ ] Add `mark_message_delivered()` method
- [ ] Add `mark_message_delivery_failed()` method
- [ ] Add `_schedule_message_deletion()` method
- [ ] Implement soft delete (set `deleted_at`)
- [ ] Test database updates
- [ ] Add transaction support
- [ ] Handle edge cases (message already delivered, etc.)

---

### 6.3 Update Telegram Client

**File:** `PGP_NOTIFICATIONS_v1/telegram_client.py`

**Enhance `send_message()` to return message ID:**
```python
def send_message(self, chat_id: int, text: str, parse_mode: str = 'MarkdownV2') -> Optional[int]:
    """
    Send message via Telegram Bot API.

    Args:
        chat_id: Telegram chat ID
        text: Message text
        parse_mode: Parsing mode (MarkdownV2, HTML, or None)

    Returns:
        Telegram message_id on success, None on failure
    """
    try:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }

        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                message_id = result['result']['message_id']
                logger.info(f"✅ [TELEGRAM] Message sent successfully (ID: {message_id})")
                return message_id
            else:
                logger.error(f"❌ [TELEGRAM] API error: {result.get('description')}")
                return None
        else:
            logger.error(f"❌ [TELEGRAM] HTTP {response.status_code}: {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ [TELEGRAM] Failed to send message: {e}", exc_info=True)
        return None
```

**Tasks:**
- [ ] Update `send_message()` to return `message_id`
- [ ] Test return value capture
- [ ] Handle Telegram API errors
- [ ] Test with invalid chat_id
- [ ] Test with malformed messages

---

## Phase 7: Database Cleanup Service (AUTOMATED MAINTENANCE)

### 7.1 Create Cleanup Script

**Purpose:** Automatically delete expired/delivered donation messages

**File:** `TOOLS_SCRIPTS_TESTS/tools/cleanup_donation_messages.py`

**Implementation:**
```python
#!/usr/bin/env python3
"""
Cleanup script for expired donation messages.
Deletes messages that are:
1. Delivered (deleted_at IS NOT NULL)
2. Expired (expires_at < NOW())
3. Failed and older than 7 days

Run this script via Cloud Scheduler (e.g., daily at 2 AM UTC)
"""
import os
import sys
from google.cloud.sql.connector import Connector
from PGP_COMMON.logging import setup_logger

logger = setup_logger(__name__)

# Database credentials
CLOUD_SQL_CONNECTION_NAME = os.getenv('CLOUD_SQL_CONNECTION_NAME')
DATABASE_NAME = os.getenv('DATABASE_NAME_SECRET')
DATABASE_USER = os.getenv('DATABASE_USER_SECRET')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD_SECRET')


def get_db_connection():
    """Get database connection via Cloud SQL Connector."""
    connector = Connector()

    def getconn():
        return connector.connect(
            CLOUD_SQL_CONNECTION_NAME,
            "pg8000",
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            db=DATABASE_NAME
        )

    return getconn()


def cleanup_delivered_messages():
    """Delete messages marked as delivered (soft deleted)."""
    try:
        query = """
            DELETE FROM donation_messages
            WHERE deleted_at IS NOT NULL
            AND deleted_at < NOW() - INTERVAL '24 hours'
        """

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            deleted_count = cur.rowcount
            conn.commit()

            logger.info(f"✅ [CLEANUP] Deleted {deleted_count} delivered messages")
            return deleted_count

    except Exception as e:
        logger.error(f"❌ [CLEANUP] Failed to delete delivered messages: {e}", exc_info=True)
        return 0


def cleanup_expired_messages():
    """Delete messages that have expired (not delivered within 72 hours)."""
    try:
        query = """
            DELETE FROM donation_messages
            WHERE delivery_status = 'pending'
            AND expires_at < NOW()
        """

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            deleted_count = cur.rowcount
            conn.commit()

            logger.info(f"✅ [CLEANUP] Deleted {deleted_count} expired messages")
            return deleted_count

    except Exception as e:
        logger.error(f"❌ [CLEANUP] Failed to delete expired messages: {e}", exc_info=True)
        return 0


def cleanup_failed_messages():
    """Delete failed messages older than 7 days."""
    try:
        query = """
            DELETE FROM donation_messages
            WHERE delivery_status = 'failed'
            AND created_at < NOW() - INTERVAL '7 days'
        """

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            deleted_count = cur.rowcount
            conn.commit()

            logger.info(f"✅ [CLEANUP] Deleted {deleted_count} failed messages (>7 days)")
            return deleted_count

    except Exception as e:
        logger.error(f"❌ [CLEANUP] Failed to delete failed messages: {e}", exc_info=True)
        return 0


def main():
    """Main cleanup execution."""
    logger.info("🧹 [CLEANUP] Starting donation message cleanup")

    delivered = cleanup_delivered_messages()
    expired = cleanup_expired_messages()
    failed = cleanup_failed_messages()

    total = delivered + expired + failed

    logger.info(f"✅ [CLEANUP] Cleanup complete - {total} messages deleted")
    logger.info(f"   Delivered: {delivered}")
    logger.info(f"   Expired: {expired}")
    logger.info(f"   Failed: {failed}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

**Tasks:**
- [ ] Create `cleanup_donation_messages.py`
- [ ] Test cleanup queries on staging database
- [ ] Create Cloud Scheduler job (daily at 2 AM UTC)
- [ ] Set up error alerting for cleanup failures
- [ ] Monitor cleanup execution logs
- [ ] Document cleanup policy in README

---

### 7.2 Create Cloud Scheduler Job

**File:** `TOOLS_SCRIPTS_TESTS/scripts/deploy_donation_message_cleanup.sh`

**Implementation:**
```bash
#!/bin/bash
#
# Deploy Cloud Scheduler job for donation message cleanup
# Runs daily at 2:00 AM UTC
#

PROJECT_ID="telepay-459221"
LOCATION="us-central1"
JOB_NAME="donation-message-cleanup"
CLEANUP_URL="https://pgp-cleanup-v1-291176869049.us-central1.run.app/cleanup-donation-messages"
SERVICE_ACCOUNT="291176869049-compute@developer.gserviceaccount.com"

echo "🕐 Creating Cloud Scheduler job for donation message cleanup..."

gcloud scheduler jobs create http "$JOB_NAME" \
  --location="$LOCATION" \
  --schedule="0 2 * * *" \
  --uri="$CLEANUP_URL" \
  --http-method=POST \
  --oidc-service-account-email="$SERVICE_ACCOUNT" \
  --time-zone="UTC" \
  --project="$PROJECT_ID"

echo "✅ Cloud Scheduler job created: $JOB_NAME"
echo "   Schedule: Daily at 2:00 AM UTC"
echo "   URL: $CLEANUP_URL"
```

**Tasks:**
- [ ] Create deployment script
- [ ] Deploy Cloud Scheduler job
- [ ] Test manual trigger
- [ ] Verify OIDC authentication
- [ ] Set up job failure alerting
- [ ] Document scheduler configuration

---

## Phase 8: Security & Validation

### 8.1 Security Checklist

**Critical Security Considerations:**

- [ ] **Encryption Key Management**
  - [ ] Generate strong 256-bit key using `os.urandom(32)`
  - [ ] Store in Secret Manager with strict IAM permissions
  - [ ] Never log encryption keys
  - [ ] Rotate key quarterly (create key rotation procedure)

- [ ] **Message Validation**
  - [ ] Enforce 256 character limit strictly
  - [ ] Strip null bytes and control characters
  - [ ] Block SQL injection patterns
  - [ ] Block XSS patterns (even though Telegram escapes)
  - [ ] Validate UTF-8 encoding

- [ ] **Access Control**
  - [ ] Only PGP_NP_IPN can create messages
  - [ ] Only PGP_NOTIFICATIONS can decrypt/deliver
  - [ ] Service accounts have minimum IAM permissions
  - [ ] No user-facing API for message retrieval

- [ ] **Rate Limiting**
  - [ ] Limit donation messages per user (e.g., 10 per day)
  - [ ] Limit messages per payment (1 message per payment_id)
  - [ ] Add to existing rate limiter in PGP_SERVER

- [ ] **Data Retention**
  - [ ] Delivered messages deleted within 24 hours
  - [ ] Expired messages deleted immediately
  - [ ] Failed messages deleted after 7 days
  - [ ] No permanent storage of decrypted messages

- [ ] **Audit Logging**
  - [ ] Log message creation (encrypted)
  - [ ] Log delivery attempts and results
  - [ ] Log decryption events
  - [ ] Log deletion events
  - [ ] Monitor for suspicious patterns

---

### 8.2 Testing Checklist

**Unit Tests:**
- [ ] MessageEncryptor encryption/decryption
- [ ] validate_donation_message() edge cases
- [ ] sanitize_donation_message() special characters
- [ ] Database schema constraints

**Integration Tests:**
- [ ] End-to-end flow (IPN → Orchestrator → Notifications → Delivery)
- [ ] Message encryption/decryption round-trip
- [ ] Database storage and retrieval
- [ ] Telegram delivery confirmation
- [ ] Cleanup script execution

**Security Tests:**
- [ ] SQL injection in message content
- [ ] XSS patterns in message content
- [ ] Null byte injection
- [ ] Oversized messages (>256 chars)
- [ ] Invalid encryption data
- [ ] Replay attacks (duplicate message_id)

**Performance Tests:**
- [ ] Encryption/decryption latency (<50ms)
- [ ] Database query performance
- [ ] Cleanup script execution time
- [ ] Concurrent message delivery

**Error Handling Tests:**
- [ ] Missing encryption key
- [ ] Corrupted encrypted data
- [ ] Telegram API failures
- [ ] Database connection failures
- [ ] Expired messages
- [ ] Invalid notification_id

---

## Phase 9: Documentation & Deployment

### 9.1 Documentation Updates

**Files to Update:**

- [ ] `README.md` - Add donation message feature overview
- [ ] `THINK/DATABASE_SCHEMA_DOCUMENTATION.md` - Document `donation_messages` table
- [ ] `SECRET_SCHEME.md` - Add `DONATION_MESSAGE_ENCRYPTION_KEY`
- [ ] `PROGRESS.md` - Track implementation progress
- [ ] `DECISIONS.md` - Document architectural decisions
- [ ] Create `DONATION_MESSAGE_FLOW.md` - Complete flow diagram

**API Documentation:**
- [ ] Document `/send-donation-message` endpoint
- [ ] Document IPN payload format with donation_message
- [ ] Document cleanup script usage
- [ ] Document encryption key rotation procedure

---

### 9.2 Deployment Checklist

**Pre-Deployment:**
- [ ] Review all code changes
- [ ] Run all unit tests
- [ ] Run integration tests in staging
- [ ] Security review by external auditor
- [ ] Performance benchmarks meet SLA

**Deployment Sequence:**
1. [ ] **Database Migration (006)**
   - [ ] Run migration on staging database
   - [ ] Verify table creation
   - [ ] Verify indexes and constraints
   - [ ] Run migration on production database
   - [ ] Verify rollback script works

2. [ ] **PGP_COMMON Updates**
   - [ ] Deploy `message_encryption.py` to all services
   - [ ] Add `cryptography` dependency to requirements.txt
   - [ ] Create `DONATION_MESSAGE_ENCRYPTION_KEY` in Secret Manager
   - [ ] Grant service accounts access to new secret

3. [ ] **Service Deployments (in order)**
   - [ ] Deploy PGP_TELEPAY_v1 (collects and encrypts messages - ENTRY POINT)
   - [ ] Deploy PGP_NP_IPN_v1 (links messages to confirmed payments)
   - [ ] Deploy PGP_ORCHESTRATOR_v1 (retrieves and passes messages)
   - [ ] Deploy PGP_NOTIFICATIONS_v1 (decrypts and delivers messages)

4. [ ] **Cleanup Infrastructure**
   - [ ] Deploy cleanup script
   - [ ] Create Cloud Scheduler job
   - [ ] Test manual trigger
   - [ ] Monitor first automated run

5. [ ] **Verification**
   - [ ] Send test payment with donation message
   - [ ] Verify message encrypted in database
   - [ ] Verify delivery to notification_id
   - [ ] Verify message deleted after delivery
   - [ ] Monitor logs for errors

**Post-Deployment:**
- [ ] Monitor error rates for 24 hours
- [ ] Monitor encryption/decryption performance
- [ ] Monitor database table size growth
- [ ] Monitor cleanup script execution
- [ ] Document any issues in BUGS.md

---

## Phase 10: Monitoring & Maintenance

### 10.1 Monitoring Metrics

**Key Metrics to Track:**
- [ ] Messages created per day
- [ ] Messages delivered per day
- [ ] Message delivery success rate
- [ ] Average delivery latency
- [ ] Encryption/decryption errors
- [ ] Expired messages per day
- [ ] Failed deliveries per day
- [ ] Database table size (donation_messages)
- [ ] Cleanup script execution time

**Alerting Rules:**
- [ ] Delivery failure rate > 5%
- [ ] Decryption errors > 0
- [ ] Cleanup script fails
- [ ] Table size > 10,000 rows (indicates cleanup issue)
- [ ] Delivery latency > 30 seconds

---

### 10.2 Maintenance Procedures

**Quarterly:**
- [ ] Review encryption key rotation (create new key, re-encrypt existing messages)
- [ ] Review message retention policy
- [ ] Analyze message delivery patterns
- [ ] Security audit of message handling

**Monthly:**
- [ ] Review failed message logs
- [ ] Analyze cleanup script performance
- [ ] Check for database bloat
- [ ] Review IAM permissions

**Weekly:**
- [ ] Monitor delivery success rate
- [ ] Check for anomalous message volumes
- [ ] Review error logs

---

## Risk Assessment & Mitigation

### High Risk Areas

1. **Encryption Key Compromise**
   - **Risk:** If encryption key is leaked, all stored messages can be decrypted
   - **Mitigation:**
     - Store key in Secret Manager with strict IAM
     - Rotate key quarterly
     - Audit key access logs
     - Delete delivered messages within 24 hours

2. **Message Content Abuse**
   - **Risk:** Users send spam, phishing, or malicious content
   - **Mitigation:**
     - Validate and sanitize all messages
     - Rate limit messages per user
     - Log all message content (encrypted)
     - Report abuse feature for channel owners

3. **Delivery Failures**
   - **Risk:** Messages not delivered due to Telegram API errors
   - **Mitigation:**
     - Retry logic with exponential backoff
     - Mark as failed after 3 attempts
     - Alert on high failure rates
     - Manual retry tool for admins

4. **Database Bloat**
   - **Risk:** donation_messages table grows unbounded
   - **Mitigation:**
     - Automated cleanup script (daily)
     - 72-hour expiration on all messages
     - Monitor table size
     - Alert if >10,000 rows

---

## Success Criteria

### Functional Requirements
- [ ] Donors can send optional message with payment
- [ ] Messages encrypted at rest in database
- [ ] Messages delivered to channel owner's Telegram
- [ ] Messages deleted after confirmed delivery
- [ ] Maximum 72-hour retention for undelivered messages

### Performance Requirements
- [ ] Encryption latency < 50ms
- [ ] Decryption latency < 50ms
- [ ] Delivery latency < 30 seconds
- [ ] Cleanup script completes in < 5 minutes
- [ ] Database queries < 100ms

### Security Requirements
- [ ] AES-256-GCM encryption used
- [ ] Encryption keys stored in Secret Manager
- [ ] Messages validated and sanitized
- [ ] No permanent storage of decrypted messages
- [ ] Audit logs for all operations

### Reliability Requirements
- [ ] Delivery success rate > 95%
- [ ] Zero encryption/decryption errors
- [ ] Zero data loss events
- [ ] Cleanup script 100% success rate

---

## Estimated Implementation Timeline

**Total:** ~50-60 hours (6-8 working days)

- **Phase 1 (Database):** 4-6 hours
- **Phase 2 (PGP_COMMON):** 6-8 hours
- **Phase 3 (PGP_TELEPAY_v1 - Message Collection):** 8-10 hours
- **Phase 4 (PGP_NP_IPN - Payment Linking):** 2-3 hours
- **Phase 5 (PGP_ORCHESTRATOR):** 3-4 hours
- **Phase 6 (PGP_NOTIFICATIONS):** 6-8 hours
- **Phase 7 (Cleanup):** 3-4 hours
- **Phase 8 (Security/Testing):** 10-12 hours
- **Phase 9 (Documentation):** 4-6 hours
- **Phase 10 (Deployment):** 3-5 hours

---

## Open Questions & Decisions Needed

1. **Message Character Limit:**
   - Current: 256 characters
   - Alternative: 512 characters for longer messages?
   - **Decision:** Stick with 256 (Telegram-friendly, less storage)

2. **Encryption Key Rotation:**
   - How often should we rotate the encryption key?
   - **Recommendation:** Quarterly rotation with re-encryption

3. **Message Language Detection:**
   - Should we auto-detect message language?
   - **Recommendation:** Optional feature for future (not MVP)

4. **Rate Limiting:**
   - What are reasonable limits for donation messages?
   - **Recommendation:** 10 messages per user per day

5. **Abuse Reporting:**
   - Should channel owners be able to report abusive messages?
   - **Recommendation:** Add in Phase 2 (not MVP)

6. **Message Editing:**
   - Should donors be able to edit messages before delivery?
   - **Recommendation:** No - too complex for MVP

---

## Conclusion

This architecture provides a **zero-trust, security-first** solution for donation messages where encrypted messages **NEVER leave Google Cloud infrastructure**.

**🔒 CRITICAL SECURITY ARCHITECTURE:**

Unlike the original plan (which would have sent messages to NOWPayments servers), this implementation ensures:

1. **Message Collection in PGP_TELEPAY_v1 Bot:**
   - User enters message in Telegram conversation
   - Message validated and encrypted IMMEDIATELY using AES-256-GCM
   - Encrypted message stored in Google Cloud SQL with status `awaiting_payment`
   - Payment created with NOWPayments (NO message in metadata or API call)

2. **Payment Confirmation in PGP_NP_IPN_v1:**
   - IPN callback received with order_id and status=finished
   - Message retrieved from Google Cloud SQL using order_id
   - Message linked to payment_id and status updated to `pending`
   - Message NEVER transmitted in IPN payload

3. **Zero External Exposure:**
   - ✅ Message never sent to NOWPayments API
   - ✅ Message never stored on NOWPayments servers
   - ✅ Message never transmitted via webhook
   - ✅ Message never leaves Google Cloud VPC
   - ✅ Message accessible only by authorized PGP services
   - ✅ Message encrypted at rest from creation to deletion

**Key Design Principles:**
✅ **Security by default** (AES-256-GCM encryption, zero external exposure)
✅ **Privacy by design** (automatic deletion after delivery)
✅ **Fail-safe** (messages expire after 72 hours if undelivered)
✅ **Auditable** (all operations logged with encryption/decryption events)
✅ **Scalable** (efficient database schema with proper indexes)
✅ **Zero-trust** (message never transmitted outside Google Cloud)

**Next Steps:**
1. Review this updated checklist (security-first architecture)
2. Get approval for database migration (Phase 1)
3. Generate and store encryption key in Secret Manager (Phase 2)
4. Begin Phase 3 implementation (PGP_TELEPAY_v1 message collection)
5. Track progress in PROGRESS.md

---

**Document Version:** 2.0
**Last Updated:** 2025-11-18 (REVISED for zero-external-exposure architecture)
**Awaiting Approval:** Database schema, encryption key creation, PGP_TELEPAY_v1 conversation flow, deployment timeline
**Security Posture:** 🔒 **ENHANCED** - Message never leaves Google Cloud infrastructure
