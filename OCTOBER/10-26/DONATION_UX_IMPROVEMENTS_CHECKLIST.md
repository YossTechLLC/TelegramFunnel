# Donation UX Improvements - Implementation Checklist

**Date:** 2025-11-15
**Status:** 🔵 **READY FOR IMPLEMENTATION**

---

## ISSUES IDENTIFIED

### **Issue 1: Payment Link Presented as Plain Text**
**Current Behavior:**
```
💳 Payment Link Ready!

Click the link below to complete your donation:

https://nowpayments.io/payment/?iid=4578470941

✅ Secure payment via NowPayments
```
- ❌ User sees raw URL link
- ❌ Opens in external browser (not Telegram WebView)
- ❌ Inconsistent with subscription flow (which uses WebApp button)

**Desired Behavior:**
```
💳 Payment Gateway Ready! 🚀

💰 Amount: $33.00
📍 Channel: -1003377958897
💬 Message: ❌ None

👇 Tap the button below to complete your donation

✅ Secure payment via NowPayments

[💰 Complete Donation]  <-- Clickable keyboard button
```
- ✅ WebApp button opens in Telegram WebView
- ✅ Consistent with subscription flow
- ✅ Better UX

---

### **Issue 2: Messages Not Auto-Deleted in Closed Channel**
**Current Behavior:**
- All donation flow messages remain in closed channel permanently
- Clutters the channel with system messages
- Messages from other bots/features get auto-deleted after 60 seconds

**Desired Behavior:**
- All donation flow messages auto-delete after 60 seconds
- Clean channel experience
- Consistent with existing auto-delete pattern

---

## IMPLEMENTATION PLAN

---

## PART 1: WebApp Button for Payment Gateway ✅

### **Step 1: Add WebApp Button Helper Function**

**File:** `TelePay10-26/bot/conversations/donation_conversation.py`

**Action:** Add helper function after imports (around line 22)

**Code to Add:**
```python
async def send_donation_payment_gateway(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    invoice_url: str,
    amount: float,
    channel_id: str,
    has_message: bool,
    message_ids_to_delete: list = None
) -> int:
    """
    Send donation payment gateway with WebApp button.

    Creates a keyboard button that opens payment gateway in Telegram WebView
    for seamless payment experience (matches subscription flow UX).

    Args:
        context: Telegram context object
        chat_id: Chat ID to send message to
        invoice_url: NowPayments invoice URL
        amount: Donation amount in USD
        channel_id: Target channel ID
        has_message: Whether donation includes a message
        message_ids_to_delete: List to track message IDs for auto-deletion

    Returns:
        Message ID of sent message
    """
    from telegram import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

    logger.info(f"💳 [DONATION] Sending payment gateway to chat {chat_id}")
    logger.info(f"   Invoice URL: {invoice_url}")

    # Create WebApp button (opens in Telegram WebView)
    reply_markup = ReplyKeyboardMarkup.from_button(
        KeyboardButton(
            text="💰 Complete Donation",
            web_app=WebAppInfo(url=invoice_url),
        )
    )

    # Format message
    text = (
        f"💳 <b>Payment Gateway Ready!</b> 🚀\n\n"
        f"💰 <b>Amount:</b> ${amount:.2f}\n"
        f"📍 <b>Channel:</b> <code>{channel_id}</code>\n"
        f"💬 <b>Message:</b> {'✅ Included' if has_message else '❌ None'}\n\n"
        f"👇 <b>Tap the button below to complete your donation</b>\n\n"
        f"✅ Secure payment via NowPayments"
    )

    # Send message with WebApp button
    sent_message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    # Track message ID for auto-deletion
    if message_ids_to_delete is not None:
        message_ids_to_delete.append(sent_message.message_id)

    logger.info(f"✅ [DONATION] Payment gateway sent (message_id: {sent_message.message_id})")

    return sent_message.message_id
```

**Why:**
- Matches subscription flow architecture (start_np_gateway.py lines 211-224)
- Opens payment in Telegram WebView (better UX)
- Returns message ID for auto-deletion tracking

---

### **Step 2: Update finalize_payment() to Use WebApp Button**

**File:** `TelePay10-26/bot/conversations/donation_conversation.py`

**Action:** Replace lines 387-404

**BEFORE:**
```python
if result['success']:
    invoice_url = result['invoice_url']

    # DEBUG: Log final invoice URL
    logger.info(f"🔗 [DEBUG] Final invoice URL returned from payment_service:")
    logger.info(f"   URL: {invoice_url}")
    logger.info(f"   URL length: {len(invoice_url)} chars")

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"💳 <b>Payment Link Ready!</b>\n\n"
             f"Click the link below to complete your donation:\n\n"
             f"{invoice_url}\n\n"
             f"✅ Secure payment via NowPayments",
        parse_mode="HTML"
    )

    logger.info(f"✅ [DONATION] Invoice created: {invoice_url}")
```

**AFTER:**
```python
if result['success']:
    invoice_url = result['invoice_url']

    # DEBUG: Log final invoice URL
    logger.info(f"🔗 [DEBUG] Final invoice URL returned from payment_service:")
    logger.info(f"   URL: {invoice_url}")
    logger.info(f"   URL length: {len(invoice_url)} chars")

    # Get message tracking list from context (for auto-deletion)
    message_ids_to_delete = context.user_data.get('donation_messages_to_delete', [])

    # Send payment gateway with WebApp button
    gateway_message_id = await send_donation_payment_gateway(
        context=context,
        chat_id=chat_id,
        invoice_url=invoice_url,
        amount=amount_float,
        channel_id=open_channel_id,
        has_message=bool(donation_message),
        message_ids_to_delete=message_ids_to_delete
    )

    # Schedule auto-deletion for all donation flow messages
    if message_ids_to_delete:
        await schedule_donation_messages_deletion(
            context=context,
            chat_id=chat_id,
            message_ids=message_ids_to_delete,
            delay_seconds=60
        )

    logger.info(f"✅ [DONATION] Invoice created: {invoice_url}")
```

**Why:**
- Uses WebApp button instead of plain text URL
- Tracks message ID for auto-deletion
- Schedules deletion of all donation flow messages

---

## PART 2: Auto-Delete Messages in Closed Channel ✅

### **Step 3: Add Message Deletion Helper Function**

**File:** `TelePay10-26/bot/conversations/donation_conversation.py`

**Action:** Add helper function after `send_donation_payment_gateway()` (around line 90)

**Code to Add:**
```python
async def schedule_donation_messages_deletion(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_ids: list,
    delay_seconds: int = 60
) -> None:
    """
    Schedule automatic deletion of donation flow messages after specified delay.

    Deletes all messages generated during donation flow to keep channel clean.
    Uses the same pattern as donation_input_handler._schedule_message_deletion().

    Args:
        context: Telegram context object
        chat_id: Chat ID where messages are located
        message_ids: List of message IDs to delete
        delay_seconds: Delay in seconds before deletion (default: 60)
    """
    import asyncio

    logger.info(f"🗑️ [DONATION] Scheduling deletion of {len(message_ids)} messages after {delay_seconds}s")
    logger.info(f"   Chat ID: {chat_id}")
    logger.info(f"   Message IDs: {message_ids}")

    async def delete_messages_after_delay():
        """Background task to delete messages after delay."""
        try:
            await asyncio.sleep(delay_seconds)

            deleted_count = 0
            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    deleted_count += 1
                    logger.info(f"🗑️ [DONATION] Deleted message {message_id}")
                except Exception as e:
                    # Message may have been manually deleted or bot lost permissions
                    logger.warning(f"⚠️ [DONATION] Failed to delete message {message_id}: {e}")

            logger.info(f"✅ [DONATION] Auto-deleted {deleted_count}/{len(message_ids)} messages after {delay_seconds}s")

        except Exception as e:
            logger.error(f"❌ [DONATION] Error in message deletion task: {e}", exc_info=True)

    # Create background task for deletion
    asyncio.create_task(delete_messages_after_delay())
```

**Why:**
- Matches existing pattern from donation_input_handler.py (lines 355-385)
- Uses asyncio.create_task() for background execution
- Gracefully handles deletion failures
- Cleans up all donation flow messages

---

### **Step 4: Track Message IDs Throughout Donation Flow**

**File:** `TelePay10-26/bot/conversations/donation_conversation.py`

**Action:** Update functions to track message IDs

**Changes Needed:**

#### **A. start_donation() - Track initial message**

**BEFORE (around line 67):**
```python
# Send donation prompt with numeric keypad
sent_message = await query.edit_message_text(
    text=message_text,
    reply_markup=keyboard,
    parse_mode="HTML"
)
```

**AFTER:**
```python
# Initialize message tracking list
context.user_data['donation_messages_to_delete'] = []

# Send donation prompt with numeric keypad
sent_message = await query.edit_message_text(
    text=message_text,
    reply_markup=keyboard,
    parse_mode="HTML"
)

# Track message for auto-deletion
context.user_data['donation_messages_to_delete'].append(sent_message.message_id)
```

---

#### **B. handle_amount_input() - Track confirmation message**

**BEFORE (around line 155):**
```python
# Send confirmation message
sent_message = await query.edit_message_text(
    text=message_text,
    reply_markup=reply_markup,
    parse_mode="HTML"
)
```

**AFTER:**
```python
# Send confirmation message
sent_message = await query.edit_message_text(
    text=message_text,
    reply_markup=reply_markup,
    parse_mode="HTML"
)

# Track message for auto-deletion
message_ids_to_delete = context.user_data.get('donation_messages_to_delete', [])
message_ids_to_delete.append(sent_message.message_id)
context.user_data['donation_messages_to_delete'] = message_ids_to_delete
```

---

#### **C. handle_message_choice() - Track message prompt**

**BEFORE (around line 215):**
```python
# Send message prompt
sent_message = await query.edit_message_text(
    text="💬 <b>Enter Your Message</b>\n\n"
         "Please send your message in your private chat with the bot.\n\n"
         "💡 <b>Tip:</b> Send /cancel to skip this step",
    parse_mode="HTML"
)
```

**AFTER:**
```python
# Send message prompt
sent_message = await query.edit_message_text(
    text="💬 <b>Enter Your Message</b>\n\n"
         "Please send your message in your private chat with the bot.\n\n"
         "💡 <b>Tip:</b> Send /cancel to skip this step",
    parse_mode="HTML"
)

# Track message for auto-deletion
message_ids_to_delete = context.user_data.get('donation_messages_to_delete', [])
message_ids_to_delete.append(sent_message.message_id)
context.user_data['donation_messages_to_delete'] = message_ids_to_delete
```

---

#### **D. handle_skip_message() - Track processing message**

**BEFORE (around line 260):**
```python
# Send processing message
processing_message = await query.edit_message_text(
    text=processing_text,
    parse_mode="HTML"
)
```

**AFTER:**
```python
# Send processing message
processing_message = await query.edit_message_text(
    text=processing_text,
    parse_mode="HTML"
)

# Track message for auto-deletion
message_ids_to_delete = context.user_data.get('donation_messages_to_delete', [])
message_ids_to_delete.append(processing_message.message_id)
context.user_data['donation_messages_to_delete'] = message_ids_to_delete
```

---

#### **E. finalize_payment() - Track processing message**

**BEFORE (around line 345):**
```python
# Send processing status
processing_message = await context.bot.send_message(
    chat_id=chat_id,
    text=processing_text,
    parse_mode="HTML"
)
```

**AFTER:**
```python
# Send processing status
processing_message = await context.bot.send_message(
    chat_id=chat_id,
    text=processing_text,
    parse_mode="HTML"
)

# Track message for auto-deletion
message_ids_to_delete = context.user_data.get('donation_messages_to_delete', [])
message_ids_to_delete.append(processing_message.message_id)
context.user_data['donation_messages_to_delete'] = message_ids_to_delete
```

---

### **Step 5: Clean Up Context After Deletion Scheduled**

**File:** `TelePay10-26/bot/conversations/donation_conversation.py`

**Action:** Add cleanup after scheduling deletion (in finalize_payment after Step 2 changes)

**Code to Add:**
```python
# Clear tracking data from context (no longer needed)
if 'donation_messages_to_delete' in context.user_data:
    del context.user_data['donation_messages_to_delete']
if 'donation_state' in context.user_data:
    del context.user_data['donation_state']
```

**Why:**
- Prevents memory leaks
- Cleans up user_data after conversation complete

---

## TESTING CHECKLIST

### **Test 1: WebApp Button (Donation WITHOUT Message)**

- [ ] Start donation in closed channel
- [ ] Enter amount: $5.00
- [ ] Click "Confirm"
- [ ] Click "💰 Skip Message - Donate Now"
- [ ] **Expected:** WebApp button appears with "💰 Complete Donation"
- [ ] **Tap button:** Opens NowPayments in Telegram WebView ✅
- [ ] **Verify:** Message shows amount, channel ID, "Message: ❌ None"

---

### **Test 2: WebApp Button (Donation WITH Message)**

- [ ] Start donation in closed channel
- [ ] Enter amount: $10.00
- [ ] Click "Confirm"
- [ ] Click "💬 Add Message"
- [ ] (Private chat prompt appears)
- [ ] Type message in private chat: "Test message 123"
- [ ] **Expected:** WebApp button appears with "💰 Complete Donation"
- [ ] **Verify:** Message shows "Message: ✅ Included"
- [ ] **Tap button:** Opens NowPayments in Telegram WebView ✅

---

### **Test 3: Auto-Delete Messages (WITHOUT Message)**

- [ ] Complete Test 1 flow
- [ ] **Wait 60 seconds**
- [ ] **Expected:** ALL donation flow messages deleted from channel ✅
- [ ] **Messages to verify deleted:**
  - Initial donation keypad
  - Amount confirmation
  - Processing message
  - Payment gateway button

---

### **Test 4: Auto-Delete Messages (WITH Message)**

- [ ] Complete Test 2 flow
- [ ] **Wait 60 seconds**
- [ ] **Expected:** ALL donation flow messages deleted from channel ✅
- [ ] **Messages to verify deleted:**
  - Initial donation keypad
  - Amount confirmation
  - Message prompt (in channel)
  - Processing message
  - Payment gateway button

---

### **Test 5: Compare with Subscription Flow**

- [ ] Test subscription payment (existing tier button)
- [ ] **Verify:** Subscription uses WebApp button ✅
- [ ] Test donation payment
- [ ] **Verify:** Donation now uses identical WebApp button ✅
- [ ] **Consistency check:** Both flows have identical UX

---

## EXPECTED BEHAVIOR AFTER IMPLEMENTATION

### **User Experience (Closed Channel):**

```
User clicks "Donate to Support This Channel"
         ↓
[Donation Keypad appears]
💰 Enter Donation Amount
$5  $10  $20  $50
         ↓
User enters $33.00 and clicks Confirm
         ↓
[Confirmation message appears]
✅ Donation Amount Confirmed
💰 Amount: $33.00
[💬 Add Message] [💰 Skip Message]
         ↓
User clicks "💰 Skip Message - Donate Now"
         ↓
[Processing message appears briefly]
✅ Payment Processing
💰 Amount: $33.00
📍 Channel: -1003377958897
💬 Message: ❌ None
         ↓
[WebApp button appears]
💳 Payment Gateway Ready! 🚀
💰 Amount: $33.00
📍 Channel: -1003377958897
💬 Message: ❌ None
👇 Tap the button below to complete your donation
[💰 Complete Donation]  <-- User taps this
         ↓
NowPayments opens in Telegram WebView
         ↓
User completes payment
         ↓
⏱️ After 60 seconds:
ALL messages above auto-delete ✅
Channel is clean
```

---

## FILES TO MODIFY

### ✅ **Primary File:**
- `TelePay10-26/bot/conversations/donation_conversation.py`
  - Add `send_donation_payment_gateway()` helper (Step 1)
  - Add `schedule_donation_messages_deletion()` helper (Step 3)
  - Update `finalize_payment()` to use WebApp button (Step 2)
  - Track message IDs throughout flow (Step 4)
  - Clean up context after scheduling deletion (Step 5)

---

## DEPENDENCIES

- ✅ `from telegram import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo` (already imported)
- ✅ `import asyncio` (need to add at top of file)
- ✅ No new packages required
- ✅ No environment variable changes required
- ✅ No database changes required

---

## ROLLBACK PLAN

If issues occur after deployment:

1. Revert `donation_conversation.py` to previous version
2. Remove `send_donation_payment_gateway()` function
3. Remove `schedule_donation_messages_deletion()` function
4. Restore original plain text URL message
5. No database changes to revert (pure logic change)

**Rollback Risk:** 🟢 **VERY LOW** (UI-only changes, no data layer impact)

---

## SUMMARY

**What we're fixing:**
1. ❌ Plain text payment URL → ✅ WebApp button (Telegram WebView)
2. ❌ Messages stay in channel forever → ✅ Auto-delete after 60 seconds

**Why it matters:**
- ✅ Consistent UX with subscription flow
- ✅ Better payment experience (Telegram WebView vs external browser)
- ✅ Clean channel (no clutter from system messages)
- ✅ Professional appearance

**Implementation complexity:** 🟢 **LOW**
- Single file modification
- Proven patterns from existing code
- No external dependencies

**Ready for implementation:** ✅ YES

---

**Status:** 🔵 **AWAITING EXECUTION**
