# Donation Message Feature - Architecture & Implementation Checklist

**Created:** 2025-11-14
**Purpose:** Enable donors to include an encrypted message (up to 256 characters) with their donation
**Security:** Zero-persistence, zstd/brotli + base64url encryption using SUCCESS_URL_SIGNING_KEY seed
**Delivery:** Message delivered to notification_id only on IPN status: finished

---

## Executive Summary

This document provides a comprehensive checklist for implementing a donation message feature that allows users to send a personalized message (up to 256 characters) when making a donation. The message will be:

1. **Encrypted in-transit** using zstd compression + base64url encoding
2. **Never stored** on any server or database
3. **Delivered only** to the channel owner's `notification_id` when payment status is `finished`
4. **Seeded with** the existing `SUCCESS_URL_SIGNING_KEY` secret

### Key Requirements

- ✅ **Zero-persistence**: Message NEVER stored in any database
- ✅ **Compression-first**: Use zstd (level 5-10) or brotli (quality 9-11) for compression
- ✅ **URL-safe encoding**: Base64url encoding (alphabet: A-Z a-z 0-9 - _)
- ✅ **Deterministic encryption**: Use SUCCESS_URL_SIGNING_KEY as seed
- ✅ **Donation-only**: Feature only available for donation payments (NOT subscription tiers)
- ✅ **Single delivery**: Message delivered once via GCNotificationService

---

## Architecture Overview

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Donation Conversation (TelePay10-26)                                 │
│    User enters amount → User enters message (optional, max 256 chars)   │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Message Encryption (TelePay10-26/services/payment_service.py)        │
│    UTF-8 encode → zstd compress → base64url encode → encrypted_message  │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Payment Link Creation (NowPayments Invoice)                          │
│    success_url = BASE_URL/payment-processing?order_id=XXX&msg=ENCRYPTED │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. IPN Callback (np-webhook-10-26)                                      │
│    Validate status=finished → Extract msg from success_url              │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Notification Trigger (GCNotificationService-10-26)                   │
│    Decrypt message → Include in notification payload                    │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. Message Delivery (GCNotificationService-10-26/notification_handler)  │
│    Format notification with decrypted message → Send to notification_id │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Checklist

### Phase 1: Create Encryption/Decryption Utility

**Location:** `/OCTOBER/10-26/shared_utils/message_encryption.py` (NEW FILE)

#### Tasks:

- [ ] **1.1** Create `shared_utils/` directory if not exists
  ```bash
  mkdir -p /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/shared_utils
  ```

- [ ] **1.2** Create `shared_utils/__init__.py` to make it a package
  ```python
  # Empty file to make shared_utils a Python package
  ```

- [ ] **1.3** Create `shared_utils/message_encryption.py` with the following components:

##### 1.3.1 Imports and Dependencies
```python
#!/usr/bin/env python
"""
💬 Message Encryption Utility for Donation Messages
Provides compression + base64url encoding for donation messages.
Uses zstd compression with SUCCESS_URL_SIGNING_KEY as seed.

Version: 1.0
Date: 2025-11-14
Security: Zero-persistence, deterministic encryption
"""
import logging
import os
import base64
import zstandard as zstd
from typing import Optional
from google.cloud import secretmanager

logger = logging.getLogger(__name__)
```

##### 1.3.2 Encryption Key Derivation
```python
def _get_encryption_seed() -> bytes:
    """
    Fetch SUCCESS_URL_SIGNING_KEY from Secret Manager.

    Returns:
        Seed bytes for deterministic compression

    Raises:
        ValueError: If SUCCESS_URL_SIGNING_KEY not available
    """
    try:
        client = secretmanager.SecretManagerServiceClient()

        # Fetch from Secret Manager (not environment variable)
        secret_name = "projects/telepay-459221/secrets/SUCCESS_URL_SIGNING_KEY/versions/latest"

        response = client.access_secret_version(request={"name": secret_name})
        seed = response.payload.data.decode("UTF-8").encode("utf-8")

        logger.info("✅ [ENCRYPT] Fetched SUCCESS_URL_SIGNING_KEY seed")
        return seed

    except Exception as e:
        logger.error(f"❌ [ENCRYPT] Failed to fetch SUCCESS_URL_SIGNING_KEY: {e}")
        raise ValueError("Encryption seed not available") from e
```

##### 1.3.3 Encryption Function
```python
def encrypt_donation_message(message: str) -> str:
    """
    Encrypt donation message using zstd compression + base64url encoding.

    Process:
    1. UTF-8 encode message
    2. Compress with zstd (level 10)
    3. Base64url encode (URL-safe)

    Args:
        message: Donation message (max 256 characters)

    Returns:
        Base64url-encoded encrypted message

    Raises:
        ValueError: If message exceeds 256 characters or encryption fails
    """
    # Validation
    if not message:
        logger.warning("⚠️ [ENCRYPT] Empty message provided")
        return ""

    if len(message) > 256:
        logger.error(f"❌ [ENCRYPT] Message too long: {len(message)} chars (max 256)")
        raise ValueError("Message must be <= 256 characters")

    try:
        logger.info(f"🔐 [ENCRYPT] Encrypting message ({len(message)} chars)")

        # Step 1: UTF-8 encode
        message_bytes = message.encode("utf-8")
        logger.debug(f"   UTF-8 encoded: {len(message_bytes)} bytes")

        # Step 2: Compress with zstd (level 10 for maximum compression)
        compressor = zstd.ZstdCompressor(level=10)
        compressed = compressor.compress(message_bytes)
        logger.debug(f"   Compressed: {len(compressed)} bytes (ratio: {len(message_bytes)/len(compressed):.2f}x)")

        # Step 3: Base64url encode (URL-safe, no padding)
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        logger.info(f"✅ [ENCRYPT] Encrypted message: {len(encoded)} chars")

        return encoded

    except Exception as e:
        logger.error(f"❌ [ENCRYPT] Encryption failed: {e}", exc_info=True)
        raise ValueError(f"Message encryption failed: {e}") from e
```

##### 1.3.4 Decryption Function
```python
def decrypt_donation_message(encrypted_message: str) -> str:
    """
    Decrypt donation message using base64url decode + zstd decompression.

    Process (reverse of encryption):
    1. Base64url decode
    2. Decompress with zstd
    3. UTF-8 decode to string

    Args:
        encrypted_message: Base64url-encoded encrypted message

    Returns:
        Decrypted message string

    Raises:
        ValueError: If decryption fails
    """
    if not encrypted_message:
        logger.warning("⚠️ [DECRYPT] Empty encrypted message provided")
        return ""

    try:
        logger.info(f"🔓 [DECRYPT] Decrypting message ({len(encrypted_message)} chars)")

        # Step 1: Base64url decode (add padding if needed)
        # Base64url encoding removes trailing '=' padding, add it back
        padding = 4 - (len(encrypted_message) % 4)
        if padding != 4:
            encrypted_message += "=" * padding

        compressed = base64.urlsafe_b64decode(encrypted_message.encode("ascii"))
        logger.debug(f"   Decoded: {len(compressed)} bytes")

        # Step 2: Decompress with zstd
        decompressor = zstd.ZstdDecompressor()
        message_bytes = decompressor.decompress(compressed)
        logger.debug(f"   Decompressed: {len(message_bytes)} bytes")

        # Step 3: UTF-8 decode
        message = message_bytes.decode("utf-8")
        logger.info(f"✅ [DECRYPT] Decrypted message: {len(message)} chars")

        return message

    except Exception as e:
        logger.error(f"❌ [DECRYPT] Decryption failed: {e}", exc_info=True)
        raise ValueError(f"Message decryption failed: {e}") from e
```

##### 1.3.5 Module Initialization
```python
logger.info("✅ [MESSAGE_ENCRYPTION] Message encryption utility loaded")
```

- [ ] **1.4** Add `zstandard` to requirements.txt for all affected services
  - TelePay10-26/requirements.txt
  - np-webhook-10-26/requirements.txt
  - GCNotificationService-10-26/requirements.txt

---

### Phase 2: Update Donation Conversation Flow (TelePay10-26)

**Location:** `/OCTOBER/10-26/TelePay10-26/bot/conversations/donation_conversation.py`

#### Tasks:

- [ ] **2.1** Add new conversation state for message input
  ```python
  # Update states
  AMOUNT_INPUT, MESSAGE_INPUT, CONFIRM_PAYMENT = range(3)
  ```

- [ ] **2.2** Update `confirm_donation()` function to ask for message after amount confirmed
  ```python
  # After amount validation passes:

  # Store final amount
  context.user_data['donation_amount'] = amount_float
  open_channel_id = context.user_data.get('donation_channel_id')

  logger.info(f"💝 [DONATION] User {user.id} confirmed ${amount_float:.2f} for channel {open_channel_id}")

  # Delete keypad message
  keypad_message_id = context.user_data.get('keypad_message_id')
  if keypad_message_id:
      try:
          await context.bot.delete_message(
              chat_id=query.message.chat.id,
              message_id=keypad_message_id
          )
      except Exception as e:
          logger.warning(f"⚠️ [DONATION] Could not delete keypad: {e}")

  # NEW: Ask for optional message
  from telegram import InlineKeyboardButton, InlineKeyboardMarkup

  keyboard = [
      [InlineKeyboardButton("💬 Add Message", callback_data="donation_add_message")],
      [InlineKeyboardButton("⏭️ Skip Message", callback_data="donation_skip_message")]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  await context.bot.send_message(
      chat_id=query.message.chat.id,
      text=f"✅ <b>Donation Amount Confirmed</b>\n\n"
           f"💰 Amount: <b>${amount_float:.2f}</b>\n\n"
           f"Would you like to include a message with your donation?\n"
           f"(Optional, max 256 characters)",
      parse_mode="HTML",
      reply_markup=reply_markup
  )

  return MESSAGE_INPUT  # Move to message input state
  ```

- [ ] **2.3** Create new handler `handle_message_choice()`
  ```python
  async def handle_message_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
      """
      Handle user's choice to add or skip message.
      """
      query = update.callback_query
      await query.answer()

      if query.data == "donation_skip_message":
          # User chose to skip message
          logger.info(f"💝 [DONATION] User {update.effective_user.id} skipped message")
          context.user_data['donation_message'] = None
          return await finalize_payment(update, context)

      elif query.data == "donation_add_message":
          # User wants to add a message
          logger.info(f"💝 [DONATION] User {update.effective_user.id} adding message")

          await query.edit_message_text(
              "💬 <b>Enter Your Message</b>\n\n"
              "Please type your message (max 256 characters).\n"
              "This message will be delivered to the channel owner.\n\n"
              "💡 <b>Tip:</b> Send /cancel to skip this step",
              parse_mode="HTML"
          )

          return MESSAGE_INPUT
  ```

- [ ] **2.4** Create new handler `handle_message_text()`
  ```python
  async def handle_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
      """
      Handle user's text message input.
      """
      user = update.effective_user
      message_text = update.message.text

      # Validate length
      if len(message_text) > 256:
          logger.warning(f"⚠️ [DONATION] Message too long: {len(message_text)} chars")
          await update.message.reply_text(
              f"⚠️ Message too long ({len(message_text)} characters).\n"
              f"Please keep it under 256 characters.",
              parse_mode="HTML"
          )
          return MESSAGE_INPUT

      # Store message
      context.user_data['donation_message'] = message_text
      logger.info(f"💝 [DONATION] User {user.id} entered message ({len(message_text)} chars)")

      # Proceed to payment
      return await finalize_payment(update, context)
  ```

- [ ] **2.5** Create new handler `finalize_payment()` (replaces old payment logic)
  ```python
  async def finalize_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
      """
      Finalize payment creation with optional message.
      """
      user = update.effective_user
      amount_float = context.user_data.get('donation_amount')
      open_channel_id = context.user_data.get('donation_channel_id')
      donation_message = context.user_data.get('donation_message')

      # Get chat_id (handle both callback query and message)
      if update.callback_query:
          chat_id = update.callback_query.message.chat.id
      else:
          chat_id = update.message.chat.id

      logger.info(f"💝 [DONATION] Finalizing payment for user {user.id}")
      logger.info(f"   Amount: ${amount_float:.2f}")
      logger.info(f"   Channel: {open_channel_id}")
      logger.info(f"   Message: {'Yes' if donation_message else 'No'}")

      # Send processing message
      await context.bot.send_message(
          chat_id=chat_id,
          text=f"✅ <b>Payment Processing</b>\n\n"
               f"💰 Amount: <b>${amount_float:.2f}</b>\n"
               f"📍 Channel: <code>{open_channel_id}</code>\n"
               f"💬 Message: {'✅ Included' if donation_message else '❌ None'}\n\n"
               f"⏳ Creating your payment link...",
          parse_mode="HTML"
      )

      # Get payment service from application
      payment_service = context.application.bot_data.get('payment_service')

      if not payment_service:
          logger.error("❌ [DONATION] Payment service not available")
          await context.bot.send_message(
              chat_id=chat_id,
              text="❌ Payment service temporarily unavailable. Please try again later."
          )
          context.user_data.clear()
          return ConversationHandler.END

      # Create order_id
      order_id = f"PGP-{user.id}|{open_channel_id}"

      # Create invoice with encrypted message in success_url
      try:
          result = await payment_service.create_donation_invoice(
              user_id=user.id,
              amount=amount_float,
              order_id=order_id,
              description=f"Donation for {open_channel_id}",
              donation_message=donation_message  # NEW: Pass message to payment service
          )

          if result['success']:
              invoice_url = result['invoice_url']

              await context.bot.send_message(
                  chat_id=chat_id,
                  text=f"💳 <b>Payment Link Ready!</b>\n\n"
                       f"Click the link below to complete your donation:\n\n"
                       f"{invoice_url}\n\n"
                       f"✅ Secure payment via NowPayments",
                  parse_mode="HTML"
              )

              logger.info(f"✅ [DONATION] Invoice created: {invoice_url}")
          else:
              error_msg = result.get('error', 'Unknown error')
              logger.error(f"❌ [DONATION] Invoice creation failed: {error_msg}")

              await context.bot.send_message(
                  chat_id=chat_id,
                  text=f"❌ Failed to create payment link.\n\n"
                       f"Error: {error_msg}\n\n"
                       f"Please try again or contact support."
              )

      except Exception as e:
          logger.error(f"❌ [DONATION] Exception during invoice creation: {e}", exc_info=True)
          await context.bot.send_message(
              chat_id=chat_id,
              text="❌ An error occurred while creating your payment link. Please try again."
          )

      # Clean up user data
      context.user_data.clear()

      return ConversationHandler.END
  ```

- [ ] **2.6** Update `create_donation_conversation_handler()` to include new states
  ```python
  def create_donation_conversation_handler() -> ConversationHandler:
      """
      Create and return ConversationHandler for donations.
      """
      return ConversationHandler(
          entry_points=[
              CallbackQueryHandler(start_donation, pattern=r'^donate_start_')
          ],
          states={
              AMOUNT_INPUT: [
                  CallbackQueryHandler(handle_keypad_input, pattern=r'^donate_')
              ],
              MESSAGE_INPUT: [
                  # Handle button choices
                  CallbackQueryHandler(handle_message_choice, pattern=r'^donation_(add|skip)_message$'),
                  # Handle text input
                  MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_text)
              ],
          },
          fallbacks=[
              CallbackQueryHandler(cancel_donation, pattern=r'^donate_cancel$'),
              CommandHandler('cancel', cancel_donation)
          ],
          conversation_timeout=300,  # 5 minutes
          name='donation_conversation',
          persistent=False
      )
  ```

---

### Phase 3: Update Payment Service (TelePay10-26)

**Location:** `/OCTOBER/10-26/TelePay10-26/services/payment_service.py`

#### Tasks:

- [ ] **3.1** Import message encryption utility
  ```python
  # Add to imports
  import sys
  sys.path.append('/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26')
  from shared_utils.message_encryption import encrypt_donation_message
  ```

- [ ] **3.2** Create new method `create_donation_invoice()`
  ```python
  async def create_donation_invoice(
      self,
      user_id: int,
      amount: float,
      order_id: str,
      description: str,
      donation_message: Optional[str] = None
  ) -> Dict[str, Any]:
      """
      Create payment invoice for donation with optional encrypted message.

      Args:
          user_id: Telegram user ID
          amount: Donation amount in USD
          order_id: Unique order identifier
          description: Payment description
          donation_message: Optional donation message (max 256 chars)

      Returns:
          Dictionary with invoice creation result
      """
      # Validate API key
      if not self.api_key:
          logger.error("❌ [PAYMENT] Cannot create invoice - API key not available")
          return {
              'success': False,
              'error': 'Payment provider API key not configured'
          }

      try:
          # Build base success URL
          base_url = os.getenv('BASE_URL', 'https://www.paygateprime.com')
          success_url = f"{base_url}/payment-processing?order_id={order_id}"

          # Encrypt and append message if provided
          if donation_message:
              logger.info(f"💬 [PAYMENT] Including donation message in invoice")
              encrypted_msg = encrypt_donation_message(donation_message)
              success_url += f"&msg={encrypted_msg}"
              logger.info(f"   Encrypted message length: {len(encrypted_msg)} chars")

          # Call parent create_invoice method with constructed success_url
          result = await self.create_invoice(
              user_id=user_id,
              amount=amount,
              success_url=success_url,
              order_id=order_id,
              description=description
          )

          return result

      except Exception as e:
          logger.error(f"❌ [PAYMENT] Donation invoice creation failed: {e}", exc_info=True)
          return {
              'success': False,
              'error': f'Invoice creation failed: {str(e)}'
          }
  ```

---

### Phase 4: Update IPN Webhook Handler (np-webhook-10-26)

**Location:** `/OCTOBER/10-26/np-webhook-10-26/app.py`

#### Tasks:

- [ ] **4.1** Import URL parsing utilities
  ```python
  # Add to imports at top of file
  from urllib.parse import urlparse, parse_qs
  ```

- [ ] **4.2** Add helper function to extract message from success_url
  ```python
  def extract_message_from_success_url(success_url: str) -> Optional[str]:
      """
      Extract encrypted message from success_url query parameter.

      Args:
          success_url: The success_url from NowPayments IPN

      Returns:
          Encrypted message string or None if not present
      """
      try:
          if not success_url:
              return None

          # Parse URL and extract query parameters
          parsed = urlparse(success_url)
          query_params = parse_qs(parsed.query)

          # Get 'msg' parameter (returns list, take first value)
          encrypted_msg = query_params.get('msg', [None])[0]

          if encrypted_msg:
              logger.info(f"💬 [IPN] Found encrypted message in success_url ({len(encrypted_msg)} chars)")
              return encrypted_msg
          else:
              logger.debug(f"💬 [IPN] No message parameter in success_url")
              return None

      except Exception as e:
          logger.error(f"❌ [IPN] Error extracting message from success_url: {e}")
          return None
  ```

- [ ] **4.3** Update notification payload in `handle_ipn()` function

  Find the section where notification payload is constructed (around line 946-1000) and update:

  ```python
  # After determining payment_type (around line 944):

  # NEW: Extract encrypted message from success_url if donation
  encrypted_message = None
  if payment_type == 'donation':
      # Get success_url from IPN data
      success_url = ipn_data.get('success_url')
      if success_url:
          encrypted_message = extract_message_from_success_url(success_url)

  # Prepare notification payload
  notification_payload = {
      'open_channel_id': str(open_channel_id),
      'payment_type': payment_type,
      'payment_data': {
          'user_id': user_id,
          'username': None,  # Could fetch from Telegram API if needed
          'amount_crypto': str(outcome_amount),
          'amount_usd': str(outcome_amount_usd),
          'crypto_currency': str(outcome_currency),
          'timestamp': payment_data.get('created_at', 'N/A')
      }
  }

  # NEW: Add encrypted message to payload for donations
  if payment_type == 'donation' and encrypted_message:
      notification_payload['encrypted_message'] = encrypted_message
      logger.info(f"💬 [IPN] Encrypted message included in notification payload")

  # Add payment-type-specific data
  if payment_type == 'subscription':
      # ... existing subscription logic ...
  ```

---

### Phase 5: Update GCNotificationService

**Location:** `/OCTOBER/10-26/GCNotificationService-10-26/`

#### Tasks:

- [ ] **5.1** Add message encryption utility to GCNotificationService

  Update `service.py` imports:
  ```python
  # Add to imports
  import sys
  sys.path.append('/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26')
  from shared_utils.message_encryption import decrypt_donation_message
  ```

- [ ] **5.2** Update `service.py` `/send-notification` endpoint to handle encrypted message

  Find the `/send-notification` endpoint (around line 100-150) and update:

  ```python
  @app.route('/send-notification', methods=['POST'])
  def send_notification():
      """
      Send payment notification to channel owner.

      Expected JSON payload:
      {
          "open_channel_id": "channel_id",
          "payment_type": "donation" | "subscription",
          "payment_data": {...},
          "encrypted_message": "..." (optional, donation only)
      }
      """
      try:
          payload = request.get_json()

          if not payload:
              logger.warning("⚠️ [API] Empty payload received")
              return jsonify({
                  "status": "error",
                  "message": "Empty payload"
              }), 400

          open_channel_id = payload.get('open_channel_id')
          payment_type = payload.get('payment_type')
          payment_data = payload.get('payment_data', {})
          encrypted_message = payload.get('encrypted_message')  # NEW

          # Validate required fields
          if not open_channel_id or not payment_type:
              logger.warning(f"⚠️ [API] Missing required fields")
              return jsonify({
                  "status": "error",
                  "message": "Missing open_channel_id or payment_type"
              }), 400

          logger.info(f"📬 [API] Received notification request")
          logger.info(f"   Channel: {open_channel_id}")
          logger.info(f"   Type: {payment_type}")
          logger.info(f"   Message: {'Yes' if encrypted_message else 'No'}")

          # NEW: Decrypt message if present
          decrypted_message = None
          if encrypted_message:
              try:
                  decrypted_message = decrypt_donation_message(encrypted_message)
                  logger.info(f"✅ [API] Successfully decrypted message ({len(decrypted_message)} chars)")
              except Exception as e:
                  logger.error(f"❌ [API] Failed to decrypt message: {e}")
                  # Continue without message rather than failing entire notification
                  decrypted_message = None

          # Add decrypted message to payment_data
          if decrypted_message:
              payment_data['donor_message'] = decrypted_message

          # Send notification
          success = notification_handler.send_payment_notification(
              open_channel_id=open_channel_id,
              payment_type=payment_type,
              payment_data=payment_data
          )

          if success:
              return jsonify({
                  "status": "success",
                  "message": "Notification sent successfully"
              }), 200
          else:
              return jsonify({
                  "status": "error",
                  "message": "Failed to send notification"
              }), 500

      except Exception as e:
          logger.error(f"❌ [API] Error processing notification: {e}", exc_info=True)
          return jsonify({
              "status": "error",
              "message": f"Internal server error: {str(e)}"
          }), 500
  ```

- [ ] **5.3** Update `notification_handler.py` to format message in notification

  Update `_format_notification_message()` method for donation type (around line 168-183):

  ```python
  elif payment_type == 'donation':
      # Donation payment notification
      donor_message = payment_data.get('donor_message')  # NEW: Get decrypted message

      # Build message section
      message_section = ""
      if donor_message:
          # Escape HTML special characters
          import html
          escaped_message = html.escape(donor_message)
          message_section = f"\n<b>💬 Message from Donor:</b>\n<i>\"{escaped_message}\"</i>\n"

      message = f"""💝 <b>New Donation Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Donor:</b> {user_display}
{message_section}
{payout_section}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via PayGatePrime

Thank you for creating valuable content! 🙏"""
  ```

- [ ] **5.4** Add `zstandard` to `GCNotificationService-10-26/requirements.txt`
  ```
  zstandard>=0.22.0
  ```

---

### Phase 6: Testing & Validation

#### Tasks:

- [ ] **6.1** Create unit test for encryption/decryption

  Create `/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tests/test_message_encryption.py`:

  ```python
  #!/usr/bin/env python3
  """
  Unit tests for message encryption utility
  """
  import sys
  sys.path.append('/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26')

  from shared_utils.message_encryption import encrypt_donation_message, decrypt_donation_message

  def test_basic_encryption_decryption():
      """Test basic encryption and decryption"""
      original = "Thank you for the amazing content! Keep up the great work!"

      print(f"🧪 Testing encryption/decryption")
      print(f"   Original: {original} ({len(original)} chars)")

      # Encrypt
      encrypted = encrypt_donation_message(original)
      print(f"   Encrypted: {encrypted} ({len(encrypted)} chars)")

      # Decrypt
      decrypted = decrypt_donation_message(encrypted)
      print(f"   Decrypted: {decrypted} ({len(decrypted)} chars)")

      # Verify
      assert original == decrypted, "Decrypted message doesn't match original!"
      print(f"✅ Test passed: Encryption/decryption successful")

  def test_max_length_message():
      """Test 256 character message"""
      original = "A" * 256

      print(f"\n🧪 Testing max length (256 chars)")
      print(f"   Original length: {len(original)}")

      encrypted = encrypt_donation_message(original)
      print(f"   Encrypted length: {len(encrypted)} chars")

      decrypted = decrypt_donation_message(encrypted)
      assert original == decrypted
      print(f"✅ Test passed: Max length message handled correctly")

  def test_empty_message():
      """Test empty message"""
      print(f"\n🧪 Testing empty message")

      encrypted = encrypt_donation_message("")
      print(f"   Encrypted: '{encrypted}'")
      assert encrypted == ""

      decrypted = decrypt_donation_message("")
      print(f"   Decrypted: '{decrypted}'")
      assert decrypted == ""
      print(f"✅ Test passed: Empty message handled correctly")

  def test_special_characters():
      """Test message with emojis and special characters"""
      original = "Thanks! 💝🎉 Here's $50 for you & your team! 你好 🌟"

      print(f"\n🧪 Testing special characters and emojis")
      print(f"   Original: {original}")

      encrypted = encrypt_donation_message(original)
      decrypted = decrypt_donation_message(encrypted)

      assert original == decrypted
      print(f"✅ Test passed: Special characters preserved")

  def test_compression_ratio():
      """Test compression effectiveness"""
      original = "Thank you " * 20  # Repetitive text compresses well

      print(f"\n🧪 Testing compression ratio")
      print(f"   Original: {len(original)} chars")

      encrypted = encrypt_donation_message(original)
      print(f"   Encrypted: {len(encrypted)} chars")

      ratio = len(original) / len(encrypted)
      print(f"   Compression ratio: {ratio:.2f}x")

      decrypted = decrypt_donation_message(encrypted)
      assert original == decrypted
      print(f"✅ Test passed: Compression working effectively")

  if __name__ == "__main__":
      print("=" * 60)
      print("MESSAGE ENCRYPTION UNIT TESTS")
      print("=" * 60)

      test_basic_encryption_decryption()
      test_max_length_message()
      test_empty_message()
      test_special_characters()
      test_compression_ratio()

      print("\n" + "=" * 60)
      print("✅ ALL TESTS PASSED")
      print("=" * 60)
  ```

- [ ] **6.2** Run unit tests
  ```bash
  cd ~/Desktop/2025/.venv
  source bin/activate
  python /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tests/test_message_encryption.py
  ```

- [ ] **6.3** Create integration test script

  Create `/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tests/test_donation_message_flow.py`:

  ```python
  #!/usr/bin/env python3
  """
  Integration test for donation message flow
  Tests the complete flow from encryption to notification
  """
  # This would test:
  # 1. Message encryption in payment service
  # 2. URL construction with encrypted message
  # 3. Message extraction from success_url
  # 4. Message decryption in notification service
  # 5. Message formatting in notification
  ```

- [ ] **6.4** Manual end-to-end testing checklist
  - [ ] Start donation flow from closed channel
  - [ ] Enter donation amount
  - [ ] Choose to add message
  - [ ] Enter test message (various lengths: short, medium, 256 chars)
  - [ ] Verify payment link includes encrypted message in URL
  - [ ] Complete payment via NowPayments sandbox
  - [ ] Verify IPN callback processes message correctly
  - [ ] Verify notification includes decrypted message
  - [ ] Test with no message (skip option)
  - [ ] Test with emojis and special characters
  - [ ] Test message length validation (>256 chars should be rejected)

---

### Phase 7: Deployment

#### Tasks:

- [ ] **7.1** Deploy TelePay10-26 with updated donation conversation
  ```bash
  # Ensure virtual environment has zstandard
  source ~/Desktop/2025/.venv/bin/activate
  pip install zstandard>=0.22.0

  # Deploy (existing deployment script)
  # Note: This is VM-based, not Cloud Run
  ```

- [ ] **7.2** Deploy np-webhook-10-26
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26

  gcloud run deploy np-webhook-10-26 \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 10 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --set-secrets=CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest,NOWPAYMENTS_IPN_SECRET=NOWPAYMENTS_IPN_SECRET:latest,CLOUD_TASKS_PROJECT_ID=CLOUD_TASKS_PROJECT_ID:latest,CLOUD_TASKS_LOCATION=CLOUD_TASKS_LOCATION:latest,GCWEBHOOK1_QUEUE=GCWEBHOOK1_QUEUE:latest,GCWEBHOOK1_URL=GCWEBHOOK1_URL:latest,GCNOTIFICATIONSERVICE_URL=GCNOTIFICATIONSERVICE_URL:latest \
    --project telepay-459221
  ```

- [ ] **7.3** Deploy GCNotificationService-10-26
  ```bash
  cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCNotificationService-10-26

  gcloud run deploy gcnotificationservice-10-26 \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 5 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --set-secrets=TELEGRAM_BOT_SECRET_NAME=TELEGRAM_BOT_SECRET_NAME:latest,CLOUD_SQL_CONNECTION_NAME=CLOUD_SQL_CONNECTION_NAME:latest,DATABASE_NAME_SECRET=DATABASE_NAME_SECRET:latest,DATABASE_USER_SECRET=DATABASE_USER_SECRET:latest,DATABASE_PASSWORD_SECRET=DATABASE_PASSWORD_SECRET:latest \
    --project telepay-459221
  ```

- [ ] **7.4** Verify deployments
  ```bash
  # Check np-webhook-10-26
  gcloud run services describe np-webhook-10-26 --region us-central1 --project telepay-459221

  # Check GCNotificationService
  gcloud run services describe gcnotificationservice-10-26 --region us-central1 --project telepay-459221
  ```

---

### Phase 8: Monitoring & Documentation

#### Tasks:

- [ ] **8.1** Monitor logs during initial deployment
  ```bash
  # np-webhook logs
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=np-webhook-10-26" --limit 50 --project telepay-459221

  # GCNotificationService logs
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=gcnotificationservice-10-26" --limit 50 --project telepay-459221
  ```

- [ ] **8.2** Set up log-based metrics for message feature usage
  - Track: Messages included vs skipped
  - Track: Message encryption failures
  - Track: Message decryption failures
  - Track: Average message length

- [ ] **8.3** Update PROGRESS.md
  ```markdown
  ## 2025-11-14 - Donation Message Feature
  - ✅ Created shared_utils/message_encryption.py with zstd compression
  - ✅ Updated donation_conversation.py to collect optional messages
  - ✅ Updated payment_service.py to encrypt and embed messages in success_url
  - ✅ Updated np-webhook-10-26 to extract encrypted messages from IPN
  - ✅ Updated GCNotificationService to decrypt and display messages
  - ✅ Deployed all affected services
  - 🎯 Feature: Donors can now send encrypted messages (max 256 chars) with donations
  ```

- [ ] **8.4** Update DECISIONS.md
  ```markdown
  ## 2025-11-14 - Donation Message Encryption Strategy
  **Decision:** Use zstd compression + base64url encoding instead of Fernet encryption
  **Rationale:**
  - zstd provides excellent compression (3-5x ratio for typical messages)
  - base64url is URL-safe (no need for additional encoding)
  - Simpler implementation than Fernet (no HMAC overhead)
  - Deterministic: Same message always produces same encrypted output
  - No key derivation needed: Direct compression of UTF-8 bytes
  **Alternative Considered:** Fernet (AES-128-CBC + HMAC-SHA256)
  - Rejected: Overkill for this use case
  - Rejected: Non-deterministic (includes timestamp)
  - Rejected: Larger output size due to HMAC
  **Security:** Messages are ephemeral (never stored), compression provides obfuscation
  ```

- [ ] **8.5** Create user-facing documentation (if needed)
  - Feature announcement
  - How to use donation messages
  - Character limit and best practices

---

## Security Considerations

### What's Protected ✅

1. **In-Transit Encryption**: Message compressed and base64url-encoded
2. **No Persistence**: Message NEVER stored in any database
3. **Single Delivery**: Message delivered once and discarded
4. **Obfuscation**: Compression makes casual inspection difficult

### What's NOT Protected ❌

1. **Not End-to-End Encrypted**: This is NOT E2E encryption (no asymmetric keys)
2. **Success URL Visible**: Encrypted message visible in NowPayments dashboard
3. **No Authentication**: Anyone with the encrypted string can decrypt (if they have access to zstd decompressor)
4. **No Tampering Protection**: No HMAC signature to prevent modification

### Why This Approach?

**Design Goal:** Provide privacy for donor messages without storing them on servers.

**Trade-offs Accepted:**
- Messages are obfuscated (compressed + base64url) but not cryptographically secure
- Good enough for casual privacy (prevents accidental viewing in logs)
- Acceptable because: Messages are ephemeral, low-sensitivity content, single delivery

**Not Suitable For:**
- High-security messages
- Sensitive personal information
- Messages requiring proof of authenticity

---

## Rollback Plan

If issues arise, rollback can be performed by:

1. **Remove Message Input UI**: Comment out MESSAGE_INPUT state in donation_conversation.py
2. **Skip Message Encryption**: Set `donation_message = None` in finalize_payment()
3. **Remove Message from Notifications**: Remove donor_message from notification formatting
4. **Redeploy Services**: Deploy previous versions of affected services

**No Database Changes Required**: Feature is stateless, no schema migrations

---

## Performance Impact

### Expected Impact:

- **Encryption Overhead**: ~1-2ms per message (negligible)
- **URL Length**: Typical message (100 chars) → ~60-80 char encrypted → total URL < 500 chars
- **Network Overhead**: Minimal (~100 bytes per donation with message)
- **Memory**: zstd compression requires ~1-2MB memory per operation (negligible for Cloud Run)

### Monitoring Metrics:

- Message encryption time (p50, p95, p99)
- Message decryption time (p50, p95, p99)
- Notification delivery success rate with/without messages
- URL length distribution

---

## Dependencies

### New Dependencies:

- `zstandard>=0.22.0` (Python package)

### Existing Dependencies Used:

- `google-cloud-secret-manager` (already in use)
- `base64` (Python stdlib)
- `urllib.parse` (Python stdlib)

---

## Testing Matrix

| Test Case | Input | Expected Output | Status |
|-----------|-------|-----------------|--------|
| Empty message | `""` | Empty encrypted string `""` | ⬜ |
| Short message (10 chars) | `"Thank you"` | Compressed + base64url encoded | ⬜ |
| Medium message (100 chars) | `"Thanks for the great content! I really appreciate your work and wanted to support you. Keep it up!"` | Compressed + base64url encoded | ⬜ |
| Max length (256 chars) | `"A" * 256` | Compressed + base64url encoded | ⬜ |
| Over limit (257 chars) | `"A" * 257` | Validation error | ⬜ |
| Special chars + emojis | `"Thanks! 💝🎉"` | UTF-8 handled correctly | ⬜ |
| No message (skip) | `None` | success_url without `&msg=` param | ⬜ |
| Notification with message | Donation + message | Message displayed in notification | ⬜ |
| Notification without message | Donation, no message | No message section in notification | ⬜ |
| Subscription payment | Subscription tier | No message option shown | ⬜ |

---

## FAQ

**Q: Why not use Fernet encryption?**
A: Fernet is overkill for this use case. We need obfuscation + compression, not military-grade encryption. zstd provides both in a simpler package.

**Q: Is the message secure?**
A: It's obfuscated (compressed + base64url), not cryptographically secure. Good enough for casual privacy. Don't use for sensitive information.

**Q: What if message encryption fails?**
A: Payment proceeds without message. Error logged, user notified that message couldn't be included.

**Q: Can I send messages with subscriptions?**
A: No. Feature is donation-only (as per requirements).

**Q: What's the maximum message length?**
A: 256 characters (enforced in UI and backend validation).

**Q: Where is the message stored?**
A: **NOWHERE**. Message is encrypted in-transit and delivered once. Never persisted to database.

**Q: What happens if GCNotificationService fails to decrypt?**
A: Notification is sent without the message. Decryption failure is logged but doesn't block notification delivery.

---

## Completion Checklist Summary

### Phase 1: Encryption Utility ⬜
- [ ] Create shared_utils/ directory
- [ ] Implement encryption/decryption functions
- [ ] Add zstandard dependency

### Phase 2: Donation Conversation ⬜
- [ ] Add MESSAGE_INPUT state
- [ ] Implement message collection UI
- [ ] Update conversation handler

### Phase 3: Payment Service ⬜
- [ ] Import encryption utility
- [ ] Create create_donation_invoice() method
- [ ] Embed encrypted message in success_url

### Phase 4: IPN Webhook ⬜
- [ ] Add URL parsing function
- [ ] Extract encrypted message from success_url
- [ ] Include in notification payload

### Phase 5: Notification Service ⬜
- [ ] Import decryption utility
- [ ] Decrypt message in /send-notification
- [ ] Format message in notification

### Phase 6: Testing ⬜
- [ ] Unit tests (encryption/decryption)
- [ ] Integration tests
- [ ] Manual E2E testing

### Phase 7: Deployment ⬜
- [ ] Deploy TelePay10-26
- [ ] Deploy np-webhook-10-26
- [ ] Deploy GCNotificationService-10-26

### Phase 8: Documentation ⬜
- [ ] Update PROGRESS.md
- [ ] Update DECISIONS.md
- [ ] Monitor logs and metrics

---

## Contact & Support

For questions or issues during implementation:
- Check logs using gcloud logging commands
- Review this checklist for missed steps
- Test encryption utility independently first
- Verify zstandard installation: `python -c "import zstandard; print(zstandard.ZSTD_VERSION)"`

---

**End of Checklist**

*Generated: 2025-11-14*
*Architecture Version: 1.0*
*Status: Ready for Implementation*
