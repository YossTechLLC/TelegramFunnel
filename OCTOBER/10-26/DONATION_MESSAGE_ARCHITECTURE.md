# Donation Message Architecture

**Date:** 2025-11-14
**Feature:** User-submitted encrypted donation messages
**Status:** Architecture Design

---

## Executive Summary

This document outlines the architectural changes required to implement a feature where donors can submit a message (up to 256 characters) when making a donation. This message will be encrypted in-transit using the `SUCCESS_URL_SIGNING_KEY` as the encryption seed, never stored on servers, and delivered to the channel owner's `notification_id` only when the IPN callback status is `finished`.

### Key Security Principles
1. **Zero-persistence**: Message is NEVER stored in any database
2. **End-to-end encryption**: Message encrypted immediately on input, decrypted only for notification delivery
3. **Donation-only**: Feature exclusively for donations (not tier subscriptions)
4. **Authenticated encryption**: Using Fernet (AES-128 CBC + HMAC-SHA256) from `cryptography` library

---

## Architecture Overview

### Flow Diagram

```
User in Channel → Donation Keypad → [NEW] Message Input → Encrypt Message
    ↓
Payment Gateway (encrypted_message in order_id)
    ↓
NOWPayments Invoice Created
    ↓
User Completes Payment
    ↓
NP-Webhook IPN Callback (status: finished)
    ↓
Parse encrypted_message from order_id → Decrypt → Include in Notification
    ↓
GCNotificationService → Channel Owner receives message
```

---

## Component Changes

### 1. TelePay10-26: Donation Input Handler
**File:** `OCTOBER/10-26/TelePay10-26/donation_input_handler.py`

#### Changes Required

**1.1 Add Message Input Step (New Conversation State)**

Add a new step AFTER amount confirmation but BEFORE payment gateway:

```python
async def _handle_confirm(self, update, context, current_amount, query):
    """
    After amount validation, prompt for optional donation message.
    """
    # ... existing validation code ...

    # Store amount
    context.user_data["donation_amount"] = amount_float

    # NEW: Prompt for optional message
    message_prompt = await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=(
            f"✅ <b>Donation Amount: ${amount_float:.2f}</b>\n\n"
            f"💬 <b>Optional: Add a Message</b>\n"
            f"Would you like to include a personal message with your donation?\n\n"
            f"Your message will be delivered to the channel owner.\n"
            f"<i>(Maximum 256 characters)</i>"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ Add Message", callback_data="donate_add_message")],
            [InlineKeyboardButton("⏭️ Skip Message", callback_data="donate_skip_message")]
        ])
    )

    context.user_data["message_prompt_message_id"] = message_prompt.message_id
```

**1.2 Add Message Collection Handler**

```python
async def _handle_add_message(self, update, context, query):
    """
    Handle user clicking 'Add Message' - switch to text input mode.
    """
    await query.answer()

    # Delete message prompt
    message_prompt_id = context.user_data.get("message_prompt_message_id")
    if message_prompt_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat.id,
                message_id=message_prompt_id
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not delete message prompt: {e}")

    # Send instructions
    instruction_msg = await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=(
            "✍️ <b>Enter Your Message</b>\n\n"
            "Type your donation message below.\n"
            "<i>Maximum 256 characters</i>\n\n"
            "Or click Cancel to skip."
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="donate_cancel_message")]
        ])
    )

    context.user_data["message_instruction_message_id"] = instruction_msg.message_id
    context.user_data["awaiting_donation_message"] = True
```

**1.3 Add Text Message Handler**

```python
async def handle_donation_message_text(self, update, context):
    """
    Handle text message when user is in donation message input mode.
    """
    if not context.user_data.get("awaiting_donation_message"):
        return  # Not in message input mode

    message_text = update.message.text

    # Validate length
    if len(message_text) > 256:
        await update.message.reply_text(
            "⚠️ Message too long! Maximum 256 characters.\n"
            f"Your message: {len(message_text)} characters\n\n"
            "Please shorten your message and try again.",
            parse_mode="HTML"
        )
        return

    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass

    # Delete instruction message
    instruction_id = context.user_data.get("message_instruction_message_id")
    if instruction_id:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=instruction_id
            )
        except:
            pass

    # Store message (UNENCRYPTED in context - will encrypt before payment)
    context.user_data["donation_message"] = message_text
    context.user_data["awaiting_donation_message"] = False

    logger.info(f"💬 User {update.effective_user.id} added donation message ({len(message_text)} chars)")

    # Proceed to payment gateway
    await self._proceed_to_payment(update, context)
```

**1.4 Add Skip Message Handler**

```python
async def _handle_skip_message(self, update, context, query):
    """
    Handle user clicking 'Skip Message'.
    """
    await query.answer()

    # Delete message prompt
    message_prompt_id = context.user_data.get("message_prompt_message_id")
    if message_prompt_id:
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat.id,
                message_id=message_prompt_id
            )
        except:
            pass

    context.user_data["donation_message"] = None

    logger.info(f"⏭️ User {update.effective_user.id} skipped donation message")

    # Proceed to payment gateway
    await self._proceed_to_payment(update, context)
```

**1.5 Add Encryption Helper (NEW)**

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

def _get_message_encryption_key(self) -> bytes:
    """
    Derive Fernet encryption key from SUCCESS_URL_SIGNING_KEY.

    Returns:
        32-byte Fernet-compatible key (base64-encoded)
    """
    # Fetch SUCCESS_URL_SIGNING_KEY from Secret Manager
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    secret_path = os.getenv("SUCCESS_URL_SIGNING_KEY")

    if not secret_path:
        logger.error("❌ SUCCESS_URL_SIGNING_KEY not configured")
        raise ValueError("Encryption key not available")

    response = client.access_secret_version(request={"name": secret_path})
    signing_key = response.payload.data.decode("UTF-8")

    # Derive Fernet key using PBKDF2
    # Use fixed salt for deterministic key derivation
    salt = b"donation_message_encryption_v1"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )

    key = base64.urlsafe_b64encode(kdf.derive(signing_key.encode('utf-8')))
    return key

def _encrypt_donation_message(self, message: str) -> str:
    """
    Encrypt donation message using Fernet.

    Args:
        message: Plain text message (max 256 chars)

    Returns:
        Base64-encoded encrypted token (URL-safe)
    """
    if not message:
        return ""

    key = self._get_message_encryption_key()
    f = Fernet(key)

    encrypted_token = f.encrypt(message.encode('utf-8'))

    # Return as URL-safe string
    return encrypted_token.decode('utf-8')
```

**1.6 Modify Payment Gateway Trigger**

```python
async def _proceed_to_payment(self, update, context):
    """
    Trigger payment gateway with encrypted message in order_id.
    """
    amount = context.user_data["donation_amount"]
    open_channel_id = context.user_data["donation_open_channel_id"]
    user_id = update.effective_user.id

    # NEW: Encrypt donation message if present
    donation_message = context.user_data.get("donation_message")
    encrypted_message = ""

    if donation_message:
        try:
            encrypted_message = self._encrypt_donation_message(donation_message)
            logger.info(f"🔐 Encrypted donation message ({len(donation_message)} chars → {len(encrypted_message)} bytes)")
        except Exception as e:
            logger.error(f"❌ Failed to encrypt message: {e}")
            # Continue without message rather than failing payment
            encrypted_message = ""

    # Import payment gateway
    from start_np_gateway import PaymentGatewayManager
    payment_gateway = PaymentGatewayManager()

    # NEW ORDER_ID FORMAT: PGP-{user_id}|{open_channel_id}|{encrypted_message}
    # Use double-pipe || to separate encrypted message (allows pipe in encrypted token)
    if encrypted_message:
        order_id = f"PGP-{user_id}|{open_channel_id}||{encrypted_message}"
    else:
        order_id = f"PGP-{user_id}|{open_channel_id}"

    logger.info(f"💰 Creating donation invoice: order_id length = {len(order_id)}")

    # ... rest of payment gateway code ...
```

---

### 2. NP-Webhook: IPN Handler
**File:** `OCTOBER/10-26/np-webhook-10-26/app.py`

#### Changes Required

**2.1 Update Order ID Parser**

```python
def parse_order_id(order_id: str) -> tuple:
    """
    Parse NowPayments order_id to extract user_id, open_channel_id, and encrypted_message.

    Format: PGP-{user_id}|{open_channel_id}||{encrypted_message}
    Legacy Format: PGP-{user_id}|{open_channel_id}

    Returns:
        Tuple of (user_id, open_channel_id, encrypted_message) or (None, None, None) if invalid
    """
    try:
        # Check for new format with encrypted message
        if '||' in order_id:
            # New format: PGP-{user_id}|{open_channel_id}||{encrypted_message}
            main_part, encrypted_message = order_id.split('||', 1)
            prefix_and_user, channel_id_str = main_part.split('|', 1)

            if not prefix_and_user.startswith('PGP-'):
                print(f"❌ [PARSE] order_id does not start with 'PGP-': {order_id}")
                return None, None, None

            user_id_str = prefix_and_user[4:]  # Remove 'PGP-' prefix
            user_id = int(user_id_str)
            open_channel_id = int(channel_id_str)

            print(f"✅ [PARSE] New format with message detected")
            print(f"   User ID: {user_id}")
            print(f"   Open Channel ID: {open_channel_id}")
            print(f"   Encrypted Message: {len(encrypted_message)} bytes")

            return user_id, open_channel_id, encrypted_message

        elif '|' in order_id:
            # Legacy format without message: PGP-{user_id}|{open_channel_id}
            prefix_and_user, channel_id_str = order_id.split('|')

            if not prefix_and_user.startswith('PGP-'):
                print(f"❌ [PARSE] order_id does not start with 'PGP-': {order_id}")
                return None, None, None

            user_id_str = prefix_and_user[4:]
            user_id = int(user_id_str)
            open_channel_id = int(channel_id_str)

            print(f"✅ [PARSE] Legacy format (no message)")
            print(f"   User ID: {user_id}")
            print(f"   Open Channel ID: {open_channel_id}")

            return user_id, open_channel_id, None

        else:
            print(f"❌ [PARSE] Invalid order_id format: {order_id}")
            return None, None, None

    except (ValueError, IndexError) as e:
        print(f"❌ [PARSE] Failed to parse order_id '{order_id}': {e}")
        return None, None, None
```

**2.2 Update IPN Handler to Pass Encrypted Message**

```python
@app.route('/', methods=['POST'])
def handle_ipn():
    """
    Handle IPN callback from NowPayments.
    """
    # ... existing validation code ...

    # Parse order_id (NOW returns 3 values)
    user_id, open_channel_id, encrypted_message = parse_order_id(order_id)

    if user_id is None or open_channel_id is None:
        print(f"❌ [IPN] Invalid order_id format: {order_id}")
        abort(400, "Invalid order_id")

    # ... existing database update code ...

    # When triggering GCNotificationService, include encrypted_message
    if GCNOTIFICATIONSERVICE_URL:
        # Determine payment type
        payment_type = 'donation' if subscription_time_days == 0 else 'subscription'

        notification_payload = {
            'open_channel_id': str(open_channel_id),
            'payment_type': payment_type,
            'payment_data': {
                'user_id': user_id,
                'username': None,
                'amount_crypto': str(outcome_amount),
                'amount_usd': str(outcome_amount_usd),
                'crypto_currency': str(outcome_currency),
                'timestamp': payment_data.get('created_at', 'N/A'),
                'encrypted_message': encrypted_message  # NEW: Pass encrypted message
            }
        }

        # ... rest of notification code ...
```

---

### 3. GCNotificationService: Notification Handler
**File:** `OCTOBER/10-26/GCNotificationService-10-26/notification_handler.py`

#### Changes Required

**3.1 Add Decryption Helper**

```python
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

def _get_message_decryption_key(self) -> bytes:
    """
    Derive Fernet decryption key from SUCCESS_URL_SIGNING_KEY.

    IMPORTANT: Must use EXACT same derivation as encryption.

    Returns:
        32-byte Fernet-compatible key (base64-encoded)
    """
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    secret_path = os.getenv("SUCCESS_URL_SIGNING_KEY")

    if not secret_path:
        logger.error("❌ SUCCESS_URL_SIGNING_KEY not configured")
        raise ValueError("Decryption key not available")

    response = client.access_secret_version(request={"name": secret_path})
    signing_key = response.payload.data.decode("UTF-8")

    # CRITICAL: Use EXACT same salt as encryption
    salt = b"donation_message_encryption_v1"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )

    key = base64.urlsafe_b64encode(kdf.derive(signing_key.encode('utf-8')))
    return key

def _decrypt_donation_message(self, encrypted_token: str) -> str:
    """
    Decrypt donation message using Fernet.

    Args:
        encrypted_token: Base64-encoded encrypted token

    Returns:
        Decrypted plain text message, or empty string if decryption fails
    """
    if not encrypted_token:
        return ""

    try:
        key = self._get_message_decryption_key()
        f = Fernet(key)

        # Decrypt token
        decrypted_bytes = f.decrypt(encrypted_token.encode('utf-8'))
        decrypted_message = decrypted_bytes.decode('utf-8')

        logger.info(f"🔓 Successfully decrypted donation message ({len(decrypted_message)} chars)")
        return decrypted_message

    except InvalidToken:
        logger.error("❌ Failed to decrypt message: Invalid token or key mismatch")
        return ""
    except Exception as e:
        logger.error(f"❌ Failed to decrypt message: {e}")
        return ""
```

**3.2 Update Notification Formatter for Donations**

```python
def _format_notification_message(
    self,
    open_channel_id: str,
    payment_type: str,
    payment_data: Dict[str, Any]
) -> str:
    """
    Format notification message based on payment type.
    """
    # ... existing code ...

    if payment_type == 'donation':
        # NEW: Extract and decrypt donation message
        encrypted_message = payment_data.get('encrypted_message', '')
        donor_message = ""

        if encrypted_message:
            donor_message = self._decrypt_donation_message(encrypted_message)

        # Format donor message section
        message_section = ""
        if donor_message:
            # Escape HTML special characters
            donor_message_escaped = (
                donor_message
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
            )

            message_section = f"""
<b>💬 Donor's Message:</b>
<i>"{donor_message_escaped}"</i>

"""

        # Donation notification with optional message
        message = f"""💝 <b>New Donation Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Donor:</b> {user_display}

{message_section}{payout_section}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via PayGatePrime

Thank you for creating valuable content! 🙏"""

    # ... rest of code ...

    return message
```

---

## Security Considerations

### 1. Encryption Security
- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Seed**: `SUCCESS_URL_SIGNING_KEY` from Google Secret Manager
- **Salt**: Fixed deterministic salt `"donation_message_encryption_v1"`

### 2. No Data Persistence
- Message is NEVER written to any database
- Only exists in:
  1. User's context (temporary, in-memory)
  2. Encrypted in order_id (transient, URL parameter)
  3. Decrypted only for notification delivery (ephemeral)

### 3. Input Validation
- Maximum 256 characters enforced client-side
- HTML special characters escaped in notification
- UTF-8 encoding enforced

### 4. Error Handling
- Encryption failure → Continue without message (graceful degradation)
- Decryption failure → Skip message section in notification (fail-safe)
- Never expose encryption/decryption errors to user

---

## Database Schema Changes

**NO DATABASE CHANGES REQUIRED**

This feature is explicitly designed to require ZERO database modifications.

---

## Environment Variables / Secrets

### Required Secrets (Already Exist)
- `SUCCESS_URL_SIGNING_KEY` - Used as encryption seed

### New Secrets
**NONE** - Reusing existing secret

---

## Testing Strategy

### Unit Tests
1. **Encryption/Decryption**
   - Test message encryption produces valid Fernet token
   - Test decryption recovers original message
   - Test encryption/decryption with special characters
   - Test encryption/decryption with emojis
   - Test 256-character limit

2. **Order ID Parsing**
   - Test parsing with message: `PGP-123|456||encrypted_token`
   - Test parsing without message: `PGP-123|456`
   - Test parsing invalid formats

### Integration Tests
1. **End-to-End Donation Flow**
   - Create donation with message
   - Verify message encrypted in order_id
   - Complete payment
   - Verify notification contains decrypted message

2. **Graceful Degradation**
   - Encryption failure → Payment continues without message
   - Decryption failure → Notification sent without message section

### Manual Testing Checklist
- [ ] User can add message (≤256 chars)
- [ ] User can skip message
- [ ] Message with special characters encrypts/decrypts correctly
- [ ] Message with emojis encrypts/decrypts correctly
- [ ] Payment succeeds with encrypted message
- [ ] Notification displays decrypted message correctly
- [ ] HTML characters in message are escaped
- [ ] Subscription payments do NOT show message option

---

## Deployment Plan

### Phase 1: Core Implementation
1. **TelePay10-26**: Add message input handlers
2. **NP-Webhook**: Update order_id parser
3. **GCNotificationService**: Add decryption and formatting

### Phase 2: Testing
1. Deploy to staging environment
2. Run integration tests
3. Manual end-to-end testing

### Phase 3: Production Deployment
1. Deploy TelePay10-26
2. Deploy NP-Webhook
3. Deploy GCNotificationService
4. Monitor logs for encryption/decryption errors

### Rollback Plan
- If encryption errors > 5%: Disable message input step
- If decryption errors > 5%: Skip message section in notifications
- Both services maintain backward compatibility with old order_id format

---

## Monitoring & Observability

### Key Metrics
1. **Encryption success rate**: % of messages successfully encrypted
2. **Decryption success rate**: % of messages successfully decrypted
3. **Message usage rate**: % of donations with messages vs without

### Log Patterns to Monitor
```
✅ [ENCRYPTION] Message encrypted successfully
❌ [ENCRYPTION] Failed to encrypt message
✅ [DECRYPTION] Message decrypted successfully
❌ [DECRYPTION] Failed to decrypt message: Invalid token
```

### Alerts
- **Critical**: Decryption failure rate > 10%
- **Warning**: Encryption failure rate > 5%

---

## API Contracts

### Order ID Format (NEW)

#### With Message
```
PGP-{user_id}|{open_channel_id}||{encrypted_message}
```

Example:
```
PGP-6271402111|-1003268562225||gAAAAABm1x2y3z4a5b6c7d8e9f0...
```

#### Without Message (Legacy Compatible)
```
PGP-{user_id}|{open_channel_id}
```

Example:
```
PGP-6271402111|-1003268562225
```

### Notification Payload (Updated)

```json
{
  "open_channel_id": "-1003268562225",
  "payment_type": "donation",
  "payment_data": {
    "user_id": 6271402111,
    "username": "donor_user",
    "amount_crypto": "0.15",
    "amount_usd": "25.00",
    "crypto_currency": "ETH",
    "timestamp": "2025-11-14 12:34:56 UTC",
    "encrypted_message": "gAAAAABm1x2y3z4a5b6c7d8e9f0..."
  }
}
```

---

## Implementation Checklist

### TelePay10-26
- [ ] Add message input step after amount confirmation
- [ ] Add text message handler for donation messages
- [ ] Add encryption helper functions
- [ ] Update order_id format to include encrypted message
- [ ] Add callback handlers for "Add Message" and "Skip Message"
- [ ] Add requirements: `cryptography>=41.0.0`

### NP-Webhook
- [ ] Update `parse_order_id()` to handle 3-part return
- [ ] Pass encrypted message to GCNotificationService
- [ ] Add backward compatibility for old order_id format
- [ ] Add requirements: `cryptography>=41.0.0`

### GCNotificationService
- [ ] Add decryption helper functions
- [ ] Update donation notification formatter
- [ ] Add HTML escaping for donor messages
- [ ] Handle decryption failures gracefully
- [ ] Add requirements: `cryptography>=41.0.0`

### Testing
- [ ] Unit tests for encryption/decryption
- [ ] Unit tests for order_id parsing
- [ ] Integration test: End-to-end donation with message
- [ ] Integration test: Donation without message
- [ ] Integration test: Encryption failure handling
- [ ] Integration test: Decryption failure handling

### Documentation
- [ ] Update PROGRESS.md with implementation notes
- [ ] Update DECISIONS.md with encryption choice rationale
- [ ] Add deployment guide
- [ ] Update SECRET_CONFIG.md (note: reusing SUCCESS_URL_SIGNING_KEY)

---

## Dependencies

### Python Packages (Add to requirements.txt)
```
cryptography>=41.0.0
```

### Existing Secrets (No new secrets needed)
- `SUCCESS_URL_SIGNING_KEY` - Already exists in Secret Manager

---

## Risk Assessment

### Low Risk
- ✅ No database changes required
- ✅ Backward compatible order_id parsing
- ✅ Graceful degradation on errors
- ✅ Reusing existing secure secret

### Medium Risk
- ⚠️ Order_id length may increase significantly (encrypted message ~200+ bytes)
  - **Mitigation**: NOWPayments order_id has 255-character limit, well within bounds
- ⚠️ Encryption/decryption adds latency
  - **Mitigation**: Fernet is fast (<1ms), negligible impact

### Mitigated Risk
- 🔒 Message confidentiality depends on SECRET key security
  - **Mitigation**: Using Google Secret Manager with IAM controls
- 🔒 Fixed salt in PBKDF2 reduces key uniqueness
  - **Mitigation**: Acceptable for this use case (deterministic encryption needed)

---

## Success Criteria

### Functional
1. ✅ Users can add optional message to donations
2. ✅ Messages are encrypted before payment
3. ✅ Messages are decrypted only for notification
4. ✅ Notifications display donor messages correctly
5. ✅ Subscriptions do NOT prompt for messages

### Non-Functional
1. ✅ Encryption success rate > 99%
2. ✅ Decryption success rate > 95%
3. ✅ No messages stored in database (audit verified)
4. ✅ Latency increase < 100ms per donation flow

---

## Future Enhancements (Out of Scope)

1. **Message moderation**: Flag inappropriate messages
2. **Message length customization**: Allow channel owners to set limit
3. **Message templates**: Provide suggested messages
4. **Anonymous donations**: Hide donor username but show message
5. **Rich text formatting**: Support bold, italic, links in messages

---

## Appendix A: Encryption Implementation Details

### Fernet Overview
- **Cipher**: AES-128-CBC
- **Authentication**: HMAC-SHA256
- **Format**: Base64-encoded token containing version, timestamp, IV, ciphertext, HMAC
- **Token Size**: ~1.3x plaintext size (e.g., 256 chars → ~350 bytes)

### Key Derivation Flow
```
SUCCESS_URL_SIGNING_KEY (44 chars, base64)
    ↓
PBKDF2-HMAC-SHA256 (100k iterations, fixed salt)
    ↓
32-byte symmetric key
    ↓
Base64-encode for Fernet compatibility
    ↓
Fernet encryption/decryption key
```

### Why Fernet?
1. **Authenticated encryption**: Prevents tampering
2. **Built-in timestamp**: Token includes creation time
3. **Battle-tested**: Used widely in production systems
4. **Simple API**: Minimal room for implementation errors
5. **Python-native**: Part of `cryptography` library (PyCA)

---

## Appendix B: Error Codes

### Encryption Errors
- `ENCRYPT_001`: Missing SUCCESS_URL_SIGNING_KEY
- `ENCRYPT_002`: PBKDF2 key derivation failed
- `ENCRYPT_003`: Fernet encryption failed

### Decryption Errors
- `DECRYPT_001`: Missing SUCCESS_URL_SIGNING_KEY
- `DECRYPT_002`: Invalid Fernet token
- `DECRYPT_003`: Token signature verification failed
- `DECRYPT_004`: UTF-8 decode error

---

**End of Architecture Document**
