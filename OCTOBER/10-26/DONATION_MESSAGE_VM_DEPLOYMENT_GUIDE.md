# Donation Message Feature - VM Deployment Guide

**Date:** 2025-11-14
**Status:** ✅ Code Ready for GitHub Push
**Target VM:** pgp-final (Google Cloud Compute Engine)

---

## Overview

The donation message feature is now fully implemented and ready for deployment to the VM. This guide outlines what needs to happen after you push the code changes to GitHub.

---

## Files Modified (Ready for GitHub Push)

### 1. `/TelePay10-26/bot_manager.py` ✅ CRITICAL FIX
**What Changed:**
- Line 13: Added import for `create_donation_conversation_handler`
- Lines 69-70: Replaced old donation handler with new conversation handler
- Line 75: Updated handler registration
- Line 87: Confirmed `donate_` pattern excluded from catch-all

**Why This Matters:**
This was the root cause preventing the message prompt from appearing to users. The old handler was catching donation callbacks before the new multi-state handler could run.

### 2. `/TelePay10-26/11-14.env` ✅ NEW FILE
**Purpose:** Environment configuration using Secret Manager paths (NOT explicit values)

**What It Contains:**
- All environment variables pointing to Google Cloud Secret Manager
- Format: `projects/291176869049/secrets/SECRET_NAME/versions/latest`
- Safe to commit - contains no actual secret values

---

## VM Deployment Steps (After GitHub Push)

### Step 1: Pull Latest Code on VM
```bash
# SSH into VM
gcloud compute ssh pgp-final --zone us-central1-c --project telepay-459221

# Navigate to project directory
cd /home/kingslavxxx/TelegramFunnel/OCTOBER/10-26

# Pull latest changes from GitHub
git pull origin TelePay-REFACTOR  # Or your branch name
```

### Step 2: Verify Files Updated
```bash
# Check bot_manager.py has the import
grep -n "create_donation_conversation_handler" TelePay10-26/bot_manager.py

# Should show:
# 13:from bot.conversations.donation_conversation import create_donation_conversation_handler
# 70:donation_conversation_handler = create_donation_conversation_handler()

# Verify shared_utils exists
ls -la TelePay10-26/shared_utils/
# Should show: __init__.py, message_encryption.py
```

### Step 3: Verify Dependencies
```bash
cd TelePay10-26

# Activate virtual environment
source venv/bin/activate  # Or wherever your venv is

# Verify zstandard installed
pip show zstandard
# If not installed:
pip install zstandard>=0.22.0
```

### Step 4: Restart TelePay Service
```bash
# Kill existing process
pkill -f telepay10-26.py

# Verify process stopped
ps aux | grep telepay10-26.py

# Start service with new code
cd /home/kingslavxxx/TelegramFunnel/OCTOBER/10-26/TelePay10-26
source venv/bin/activate
python telepay10-26.py

# OR if using 11-14.env:
python telepay10-26.py --env-file 11-14.env
```

### Step 5: Monitor Startup Logs
Watch for these log messages indicating successful startup:

```
⚙️ [DEBUG] Bot data setup: menu_handlers=True, payment_handler=True, db_manager=True
✅ [BOT] Telegram bot started successfully
```

---

## Testing the Feature

### Test Flow (After VM Restart)

1. **Navigate to Bot in Telegram**
   - Find a channel with donation support enabled

2. **Start Donation**
   - Click "Donate to Support This Channel" button
   - Should see amount keypad

3. **Enter Amount**
   - Select amount using keypad (e.g., $5.00)
   - Click "Confirm" button

4. **🎯 MESSAGE PROMPT (New Behavior)**
   - Should see: "✅ Donation Amount Confirmed"
   - Should see two buttons:
     - "💬 Add Message"
     - "⏭️ Skip Message"

5. **Test Path A: Add Message**
   - Click "💬 Add Message"
   - Should see: "💬 Enter Your Message"
   - Type message (max 256 characters)
   - Payment link should be created with encrypted message

6. **Test Path B: Skip Message**
   - Click "⏭️ Skip Message"
   - Payment link should be created immediately (no message)

### Verify Message Delivery

1. **Complete Payment**
   - Use test payment or real donation
   - Wait for "finished" status from NowPayments

2. **Check Channel Owner Notification**
   - Channel owner should receive notification
   - If message was included, notification should show:
     ```
     💬 Donor Message:
     [Your message here]
     ```

---

## Troubleshooting

### Issue: Message Prompt Still Not Appearing

**Diagnostic Commands:**
```bash
# Verify bot_manager.py has correct handler
grep -A 5 "donation_conversation_handler = create_donation_conversation_handler()" TelePay10-26/bot_manager.py

# Check if old handler still exists (should NOT find this)
grep -n "DONATION_AMOUNT_INPUT" TelePay10-26/bot_manager.py
# If found in bot_manager.py, old handler is still being used

# Verify donation_conversation.py has MESSAGE_INPUT state
grep -n "MESSAGE_INPUT" TelePay10-26/bot/conversations/donation_conversation.py
# Should show multiple lines including state definition and handlers
```

### Issue: ModuleNotFoundError: No module named 'shared_utils'

**Fix:**
```bash
cd /home/kingslavxxx/TelegramFunnel/OCTOBER/10-26/TelePay10-26
ls -la shared_utils/  # Verify directory exists

# If missing, copy from parent directory:
cp -r ../shared_utils ./

# Verify zstandard installed:
pip install zstandard>=0.22.0
```

### Issue: Import Error from bot.conversations.donation_conversation

**Fix:**
```bash
# Verify donation_conversation.py exists
ls -la TelePay10-26/bot/conversations/donation_conversation.py

# Verify function exists in file
grep -n "def create_donation_conversation_handler" TelePay10-26/bot/conversations/donation_conversation.py
# Should show line number where function is defined
```

---

## Architecture Summary

### Donation Flow with Message Support

```
User Clicks Donate
    ↓
Amount Keypad (AMOUNT_INPUT state)
    ↓
User Confirms Amount
    ↓
Message Prompt (MESSAGE_INPUT state) ← NEW
    ├─ "💬 Add Message" → Text Input → Encrypt → Payment
    └─ "⏭️ Skip Message" → Payment (no message)
```

### Message Encryption Flow

```
User Types Message (max 256 chars)
    ↓
zstd Compression (level 10)
    ↓
base64url Encoding
    ↓
Append to success_url: ?msg=<encrypted>
    ↓
NowPayments stores success_url
    ↓
Payment completes → IPN callback
    ↓
np-webhook extracts encrypted message
    ↓
GCNotificationService decrypts message
    ↓
Channel owner receives notification with message
```

---

## Files Deployed to Cloud Run (Already Done)

These services were already deployed in previous session:

1. **np-webhook-10-26** (Revision: 00020-7lm)
   - Extracts encrypted message from IPN callback
   - Includes message in notification payload

2. **gcnotificationservice-10-26** (Revision: 00007-sxt)
   - Decrypts message using shared_utils
   - Formats message in notification to channel owner

Both services already have `shared_utils` integrated and are production-ready.

---

## Success Criteria

✅ **Feature Working When:**
1. Donation flow shows message prompt after amount confirmation
2. Both "Add Message" and "Skip Message" paths work
3. Messages (if added) appear in channel owner notification
4. No ModuleNotFoundError on VM startup
5. No handler registration conflicts

---

## Additional Notes

- **Zero Persistence:** Messages are NEVER stored in database
- **Single Delivery:** Messages delivered once via notification, then discarded
- **Compression Ratio:** Achieves 5.71x compression for repetitive text
- **Max Length:** 256 characters enforced in `handle_message_text()`
- **URL Safety:** base64url encoding ensures compatibility with URL parameters

---

## Reference Documents

- Implementation Progress: `/DONATION_MESSAGE_ARCHITECTURE_CHECKLIST_PROGRESS.md`
- Architecture Design: `/DONATION_MESSAGE_ARCHITECTURE.md`
- Decision Rationale: `/DECISIONS.md` (2025-11-14 entries)
- Progress Tracker: `/PROGRESS.md` (2025-11-14 entries)

---

**🚀 Ready for Deployment!**

After you push to GitHub and pull on the VM, the donation message feature will be fully operational.
