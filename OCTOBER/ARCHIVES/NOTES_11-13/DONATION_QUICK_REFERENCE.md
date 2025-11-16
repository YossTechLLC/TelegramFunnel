# Donation Implementation - Quick Reference Guide

## File Locations - One-Stop Map

### Donate Button Entry Points
```
Telegram Bot Menu:
  TelePay10-26/menu_handlers.py:19  ← "💝 Donate" keyboard button
  TelePay10-26/menu_handlers.py:40  ← click handler

Broadcast Link (in channel):
  TelePay10-26/broadcast_manager.py:70  ← donation_token = f"{base_hash}_DONATE"
  TelePay10-26/broadcast_manager.py:72  ← donation URL button
```

### Conversation Flow
```
Token Detection:
  TelePay10-26/menu_handlers.py:134       ← if remaining_part == "DONATE"

Input Collection:
  TelePay10-26/input_handlers.py:137      ← start_donation_conversation()
  TelePay10-26/input_handlers.py:153      ← start_donation() [asks amount]
  TelePay10-26/input_handlers.py:205      ← receive_donation_amount() [validates]
  TelePay10-26/input_handlers.py:240      ← complete_donation() [sets globals + triggers payment]

Validation:
  TelePay10-26/input_handlers.py:48       ← _valid_donation_amount()
```

### Payment Processing
```
NowPayments Invoice:
  TelePay10-26/start_np_gateway.py:54     ← create_payment_invoice()
  TelePay10-26/start_np_gateway.py:235    ← start_np_gateway_new() [main entry]

Webhook Handler:
  np-webhook-10-26/app.py:290             ← update_payment_data()
  np-webhook-10-26/app.py:218             ← parse_order_id()
```

### Database Operations
```
Channel Lookup:
  TelePay10-26/database.py:126    ← fetch_closed_channel_id(open_channel_id)
  TelePay10-26/database.py:154    ← fetch_client_wallet_info(open_channel_id)

Donation Fallback:
  TelePay10-26/database.py:188    ← get_default_donation_channel()
```

---

## Data Structures - What Gets Passed Where

### Donation Token Format
```
Channel ID: -1003268562225 (negative Telegram channel ID)
  ↓
base_hash = base64.urlsafe_b64encode(str(-1003268562225))
  ↓ 
Result: "LTEwMDMyNjg1NjIyMjU="
  ↓
Donation Token: "LTEwMDMyNjg1NjIyMjU=_DONATE"
  ↓
Bot URL: https://t.me/{bot_username}?start=LTEwMDMyNjg1NjIyMjU=_DONATE
```

### Global Values During Donation
```python
# Set in input_handlers.py:complete_donation() (Line 286-296)
menu_handlers.global_sub_value = 25.00        # User's donation amount
menu_handlers.global_open_channel_id = "-1003268562225"  # Channel
menu_handlers.global_sub_time = 365           # Special: 1 year
```

### Order ID for Payment
```
Format: PGP-{user_id}|{open_channel_id}
Example: PGP-6271402111|-1003268562225

Parsed by:
  user_id = 6271402111 (Telegram user ID)
  open_channel_id = -1003268562225 (channel)

Then looked up in main_clients_database to get:
  closed_channel_id = -1002345678901
  client_wallet_address = "0x742d35Cc6634C0532925a3b844Bc123e5c1e6d8d"
  client_payout_currency = "ETH"
  client_payout_network = "Ethereum"
```

---

## Input Validation Rules

### Donation Amount
```
✅ Valid:
  - "25" → 25.00
  - "10.50" → 10.50
  - "$25.50" → 25.50 ($ stripped)
  - "1.00" to "9999.99" (range)
  - Max 2 decimal places

❌ Invalid:
  - "0.50" (below $1.00)
  - "10000.00" (above $9999.99)
  - "25.999" (too many decimals)
  - "abc" (non-numeric)
```

### Channel ID (for fallback)
```
✅ Valid:
  - "-1003268562225" (negative)
  - "1003268562225" (accepts, adds negative)
  - Max 14 characters

❌ Invalid:
  - Non-numeric
  - Longer than 14 chars
```

---

## Database Schema Excerpt

### main_clients_database (Donation-Relevant Columns)
```sql
open_channel_id          -- User's public channel
closed_channel_id        -- User's private channel (where donors added)
open_channel_title       -- Display name
closed_channel_title     -- VIP channel name
closed_channel_description

client_wallet_address    -- Where donation crypto sent
client_payout_currency   -- "ETH", "BTC", "USDT", etc.
client_payout_network    -- "Ethereum", "Bitcoin", "Polygon", etc.

payout_strategy          -- "instant" or "threshold"
payout_threshold_usd     -- Min amount before batch payout
```

### private_channel_users_database (User Records)
```sql
user_id                  -- Telegram user who donated
private_channel_id       -- closed_channel_id (channel they join)
is_active                -- true while membership valid
expire_date, expire_time -- When access expires (365 days from donation)
payment_id               -- NowPayments transaction ID
```

---

## State Machine - Conversation States

```python
DONATION_AMOUNT_INPUT = 16  # From input_handlers.py:21

Flow:
  initial state
    ↓ [user clicks donate button]
  DONATION_AMOUNT_INPUT
    ↓ [user enters amount]
  validate + complete
    ↓ [sets global values]
  trigger payment_gateway_handler
    ↓ [opens NowPayments invoice]
  ConversationHandler.END
```

---

## Special Cases & Fallbacks

### When No Channel ID Available
```python
# input_handlers.py:274-284
if not channel_id:
    try:
        db_manager = ctx.bot_data.get('db_manager')
        default_channel = db_manager.get_default_donation_channel()
        if default_channel:
            channel_id = default_channel
    except:
        pass
    
    # Last resort fallback
    if not channel_id:
        channel_id = "donation_default"
```

### Donation Default Channel
```python
# start_np_gateway.py:250-257
if global_open_channel_id == "donation_default":
    closed_channel_id = "donation_default_closed"
    wallet_address = ""
    payout_currency = ""
    payout_network = ""
    closed_channel_title = "Donation Channel"
```

---

## Key Environment Variables

```bash
# Telegram
TELEGRAM_BOT_TOKEN              # Bot token
TELEGRAM_BOT_USERNAME           # For URLs

# NowPayments
PAYMENT_PROVIDER_SECRET_NAME    # API token path in Secrets Manager
NOWPAYMENTS_IPN_CALLBACK_URL    # Webhook endpoint
NOWPAYMENTS_IPN_SECRET          # For HMAC verification

# Database
DATABASE_HOST_SECRET            # Cloud SQL host path
DATABASE_NAME_SECRET            # DB name path
DATABASE_USER_SECRET            # DB user path
DATABASE_PASSWORD_SECRET        # DB password path
CLOUD_SQL_CONNECTION_NAME       # For Cloud SQL Connector

# Cloud Tasks
CLOUD_TASKS_PROJECT_ID          # GCP project
CLOUD_TASKS_LOCATION            # Region (us-central1)
GCWEBHOOK1_QUEUE                # Queue name for webhook triggers
GCWEBHOOK1_URL                  # Webhook endpoint URL
```

---

## Debugging Checklist

### Check if donation button appears:
```
1. Is broadcast_manager.broadcast_hash_links() called?
2. Is donation_token format correct? (should end in _DONATE)
3. Is bot_username set correctly in URL?
```

### Check if bot parses donation token:
```
1. Check logs for: "🎯 [DEBUG] Donation token detected"
2. Verify token has | (new format) or - (old format)
3. Check: "⚙️ [DEBUG] Set donation context: channel_id={id}"
```

### Check if amount input works:
```
1. Should see: "💝 *How much would you like to donate?*"
2. Test amounts: 25, 10.50, $25.50
3. Should reject: 0.50, 10000.00, 25.999
```

### Check if payment gateway triggers:
```
1. Should see: "📋 [ORDER] Created order_id: PGP-{user_id}|{channel_id}"
2. Should see: "✅ [INVOICE] Created invoice_id: ..."
3. Should receive NowPayments button
```

### Check webhook processing:
```
1. Should see: "🔗 [WEBHOOK] IPN signature verified"
2. Should see: "✅ [PARSE] Parsed order_id successfully"
3. Should see: "💿 [DATABASE] Updated payment_id in database"
4. Should see: "📤 [CLOUDTASKS] Triggered GCWebhook1"
```

---

## Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `❌ No channel ID available` | Token parsing failed | Check base64 encoding in broadcast_manager.py |
| `❌ Invalid donation amount` | User entered non-numeric | Use validation: 25, 10.50, $25.50 |
| `❌ Could not find closed_channel_id` | DB lookup failed | Verify open_channel_id exists in main_clients_database |
| `❌ IPN signature verification failed` | Wrong secret | Check NOWPAYMENTS_IPN_SECRET in Secrets Manager |
| `❌ Error: payment_gateway_handler not found` | Missing bot_data | Check BotManager initialization |

---

## Code Snippets for Integration

### Getting donation amount from context
```python
donation_amount = ctx.user_data.get("donation_amount")  # e.g., 25.00
donation_channel_id = ctx.user_data.get("donation_channel_id")  # e.g., "-1003268562225"
```

### Looking up wallet info for donation
```python
from database import DatabaseManager
db_mgr = DatabaseManager()
wallet_addr, payout_currency, payout_network = db_mgr.fetch_client_wallet_info(channel_id)
closed_channel_id = db_mgr.fetch_closed_channel_id(channel_id)
```

### Creating donation URL
```python
base_hash = BroadcastManager.encode_id(channel_id)  # -1003268562225 → "LTEw..."
donation_token = f"{base_hash}_DONATE"
donation_url = f"https://t.me/{bot_username}?start={donation_token}"
```

### Validating donation input
```python
from input_handlers import InputHandlers
if InputHandlers._valid_donation_amount(user_input):
    amount = float(user_input.lstrip('$'))
    print(f"✅ Valid donation: ${amount:.2f}")
```

