# Live-Time Broadcast Only Checklist

**Date:** 2025-01-14
**Objective:** Implement message deletion and replacement to maintain only the latest broadcast messages in channels
**Purpose:** Ensure only live/current donation tier and donation button presentations exist in open/closed channels
**Status:** 🔍 PLANNING PHASE

---

## Executive Summary

Currently, when donation tiers or donation buttons are broadcast to `open_channel_id` and `closed_channel_id`, messages remain indefinitely, creating clutter and confusion. This checklist outlines the architectural changes needed to:

1. **Track message IDs** for all broadcast messages sent to channels
2. **Delete old messages** when resending/updating broadcasts
3. **Preserve user and admin messages** (only delete bot-generated broadcasts)
4. **Maintain a single live version** of each broadcast type per channel

**Key Architectural Changes:**
- Add `last_open_message_id` and `last_closed_message_id` columns to `broadcast_manager` table
- Implement message deletion logic in `GCBroadcastService` and `TelePay10-26`
- Create message tracking system for reliable cleanup
- Handle edge cases (deleted messages, permissions, rate limits)

**Expected Outcome:**
- Only 1 subscription tier message in each open channel (most recent)
- Only 1 donation button message in each closed channel (most recent)
- Clean, uncluttered channel experience for users

---

## Table of Contents

1. [Phase 1: Database Schema Enhancement](#phase-1-database-schema-enhancement)
2. [Phase 2: GCBroadcastService Message Tracking](#phase-2-gcbroadcastservice-message-tracking)
3. [Phase 3: TelePay10-26 Message Tracking](#phase-3-telepay10-26-message-tracking)
4. [Phase 4: Message Deletion Logic](#phase-4-message-deletion-logic)
5. [Phase 5: Error Handling and Edge Cases](#phase-5-error-handling-and-edge-cases)
6. [Phase 6: Testing and Validation](#phase-6-testing-and-validation)
7. [Phase 7: Deployment and Monitoring](#phase-7-deployment-and-monitoring)

---

## Phase 1: Database Schema Enhancement

**Objective:** Add message ID tracking columns to `broadcast_manager` table

### Task 1.1: Create Database Migration Script
**Status:** ⏳ PENDING

**File to Create:** `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/add_message_tracking_columns.sql`

```sql
-- Add message ID tracking columns to broadcast_manager table
-- Purpose: Track last sent message IDs for deletion when resending

ALTER TABLE broadcast_manager
ADD COLUMN IF NOT EXISTS last_open_message_id BIGINT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS last_closed_message_id BIGINT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS last_open_message_sent_at TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS last_closed_message_sent_at TIMESTAMP DEFAULT NULL;

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_broadcast_manager_open_message
ON broadcast_manager(last_open_message_id)
WHERE last_open_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_broadcast_manager_closed_message
ON broadcast_manager(last_closed_message_id)
WHERE last_closed_message_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN broadcast_manager.last_open_message_id IS
'Telegram message ID of last subscription tier message sent to open channel';

COMMENT ON COLUMN broadcast_manager.last_closed_message_id IS
'Telegram message ID of last donation button message sent to closed channel';

COMMENT ON COLUMN broadcast_manager.last_open_message_sent_at IS
'Timestamp when last open channel message was sent';

COMMENT ON COLUMN broadcast_manager.last_closed_message_sent_at IS
'Timestamp when last closed channel message was sent';
```

**Action Items:**
- [ ] Create migration script file
- [ ] Review SQL syntax for PostgreSQL compatibility
- [ ] Test migration on local development database
- [ ] Document rollback procedure
- [ ] **Status:** ⏳ PENDING

---

### Task 1.2: Create Rollback Script
**Status:** ⏳ PENDING

**File to Create:** `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/rollback_message_tracking_columns.sql`

```sql
-- Rollback message tracking columns from broadcast_manager table

-- Drop indexes first
DROP INDEX IF EXISTS idx_broadcast_manager_open_message;
DROP INDEX IF EXISTS idx_broadcast_manager_closed_message;

-- Drop columns
ALTER TABLE broadcast_manager
DROP COLUMN IF EXISTS last_open_message_id,
DROP COLUMN IF EXISTS last_closed_message_id,
DROP COLUMN IF EXISTS last_open_message_sent_at,
DROP COLUMN IF EXISTS last_closed_message_sent_at;
```

**Action Items:**
- [ ] Create rollback script file
- [ ] Test rollback on local development database
- [ ] Document when rollback should be used
- [ ] **Status:** ⏳ PENDING

---

### Task 1.3: Execute Database Migration
**Status:** ⏳ PENDING

**Deployment Script:** `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts/deploy_message_tracking_migration.sh`

```bash
#!/bin/bash
# Deploy message tracking migration to telepaypsql

set -e  # Exit on error

echo "🚀 Deploying message tracking migration..."

# Set database connection info
DB_HOST="/cloudsql/telepay-459221:us-central1:telepaypsql"
DB_NAME="telepaydb"
DB_USER="postgres"

# Execute migration
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -f add_message_tracking_columns.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration deployed successfully"
else
    echo "❌ Migration failed"
    exit 1
fi

# Verify columns exist
echo "🔍 Verifying new columns..."
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c "\d broadcast_manager" | grep "last_.*_message_id"

echo "✅ Verification complete"
```

**Action Items:**
- [ ] Create deployment script
- [ ] Test on telepaypsql-clone-preclaude (if needed for testing)
- [ ] Execute on production telepaypsql database
- [ ] Verify columns created successfully
- [ ] Update SECRET_CONFIG.md if new secrets needed
- [ ] **Status:** ⏳ PENDING

**Verification Command:**
```bash
# Verify columns exist
gcloud sql connect telepaypsql --user=postgres --database=telepaydb
\d broadcast_manager
```

---

## Phase 2: GCBroadcastService Message Tracking

**Objective:** Enhance GCBroadcastService to track and delete old broadcast messages

### Task 2.1: Update TelegramClient for Message Deletion
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/GCBroadcastService-10-26/clients/telegram_client.py`

**Enhancement Required:**
```python
async def delete_message(
    self,
    chat_id: str,
    message_id: int
) -> Dict[str, Any]:
    """
    Delete a message from a Telegram chat.

    Args:
        chat_id: Channel/chat ID where message exists
        message_id: Telegram message ID to delete

    Returns:
        {'success': bool, 'error': str or None}

    Error Handling:
        - Message not found: Returns success=False, continues broadcast
        - No permission: Returns success=False, logs warning
        - Rate limit: Waits and retries once
    """
    try:
        await self.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )

        self.logger.info(f"🗑️ Deleted message {message_id} from {chat_id}")
        return {'success': True, 'error': None}

    except telegram.error.BadRequest as e:
        # Message already deleted or doesn't exist - not a critical error
        if "message to delete not found" in str(e).lower():
            self.logger.warning(f"⚠️ Message {message_id} already deleted from {chat_id}")
            return {'success': True, 'error': None}  # Treat as success

        # Other BadRequest errors (permissions, etc.)
        self.logger.error(f"❌ Cannot delete message {message_id} from {chat_id}: {e}")
        return {'success': False, 'error': str(e)}

    except telegram.error.RetryAfter as e:
        # Rate limit - wait and retry once
        wait_time = e.retry_after
        self.logger.warning(f"⏱️ Rate limited, waiting {wait_time}s before retry...")
        await asyncio.sleep(wait_time)

        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            self.logger.info(f"🗑️ Deleted message {message_id} from {chat_id} (after retry)")
            return {'success': True, 'error': None}
        except Exception as retry_error:
            self.logger.error(f"❌ Retry failed for message {message_id}: {retry_error}")
            return {'success': False, 'error': str(retry_error)}

    except Exception as e:
        self.logger.error(f"❌ Unexpected error deleting message {message_id}: {e}")
        return {'success': False, 'error': str(e)}
```

**Action Items:**
- [ ] Add `delete_message()` method to TelegramClient
- [ ] Import required telegram.error exceptions
- [ ] Add unit tests for deletion logic
- [ ] Test error handling for each exception type
- [ ] **Status:** ⏳ PENDING

---

### Task 2.2: Update BroadcastTracker for Message ID Storage
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/GCBroadcastService-10-26/services/broadcast_tracker.py`

**Enhancement Required:**
```python
def update_message_ids(
    self,
    broadcast_id: str,
    open_message_id: Optional[int] = None,
    closed_message_id: Optional[int] = None
) -> None:
    """
    Update the last sent message IDs for a broadcast.

    Args:
        broadcast_id: UUID of the broadcast entry
        open_message_id: Telegram message ID sent to open channel
        closed_message_id: Telegram message ID sent to closed channel

    Note:
        Only updates provided message IDs (supports partial updates)
    """
    try:
        with self.db.get_connection() as conn:
            update_fields = []
            params = {'broadcast_id': broadcast_id}

            if open_message_id is not None:
                update_fields.append(
                    "last_open_message_id = %(open_msg_id)s"
                )
                update_fields.append(
                    "last_open_message_sent_at = NOW()"
                )
                params['open_msg_id'] = open_message_id

            if closed_message_id is not None:
                update_fields.append(
                    "last_closed_message_id = %(closed_msg_id)s"
                )
                update_fields.append(
                    "last_closed_message_sent_at = NOW()"
                )
                params['closed_msg_id'] = closed_message_id

            if not update_fields:
                self.logger.warning("⚠️ No message IDs provided to update")
                return

            query = f"""
                UPDATE broadcast_manager
                SET {', '.join(update_fields)}
                WHERE id = %(broadcast_id)s
            """

            conn.execute(text(query), params)
            conn.commit()

            self.logger.info(
                f"📝 Updated message IDs for broadcast {str(broadcast_id)[:8]}... "
                f"(open={open_message_id}, closed={closed_message_id})"
            )

    except Exception as e:
        self.logger.error(f"❌ Failed to update message IDs: {e}")
        # Don't raise - this is supplementary functionality
```

**Action Items:**
- [ ] Add `update_message_ids()` method to BroadcastTracker
- [ ] Import SQLAlchemy `text()` for parameterized queries
- [ ] Add unit tests for message ID updates
- [ ] Test with partial updates (only open or only closed)
- [ ] **Status:** ⏳ PENDING

---

### Task 2.3: Update BroadcastExecutor for Message Deletion
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/GCBroadcastService-10-26/services/broadcast_executor.py`

**Enhancement Required:**

**Step 1: Delete old messages before sending new ones**

```python
def execute_broadcast(self, broadcast_entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single broadcast operation.

    NEW BEHAVIOR:
    1. Delete old open channel message (if exists)
    2. Send new subscription message to open channel
    3. Delete old closed channel message (if exists)
    4. Send new donation message to closed channel
    5. Update message IDs in database
    """
    broadcast_id = broadcast_entry['id']
    open_channel_id = broadcast_entry['open_channel_id']
    closed_channel_id = broadcast_entry['closed_channel_id']

    # Get old message IDs for deletion
    old_open_msg_id = broadcast_entry.get('last_open_message_id')
    old_closed_msg_id = broadcast_entry.get('last_closed_message_id')

    self.logger.info(f"🚀 Executing broadcast {str(broadcast_id)[:8]}...")

    # Mark as in-progress
    self.tracker.update_status(broadcast_id, 'in_progress')

    errors = []
    open_sent = False
    closed_sent = False
    new_open_msg_id = None
    new_closed_msg_id = None

    try:
        # STEP 1: Delete old open channel message (if exists)
        if old_open_msg_id:
            self.logger.info(
                f"🗑️ Deleting old open message {old_open_msg_id} from {open_channel_id}"
            )
            delete_result = await self.telegram.delete_message(
                open_channel_id,
                old_open_msg_id
            )
            if not delete_result['success']:
                self.logger.warning(
                    f"⚠️ Could not delete old open message: {delete_result['error']}"
                )
                # Continue anyway - not critical

        # STEP 2: Send new subscription message to open channel
        self.logger.info(f"📤 Sending to open channel: {open_channel_id}")
        open_result = await self._send_subscription_message(broadcast_entry)
        open_sent = open_result['success']
        new_open_msg_id = open_result.get('message_id')

        if not open_sent:
            error_msg = f"Open channel: {open_result['error']}"
            errors.append(error_msg)
            self.logger.error(f"❌ {error_msg}")

        # STEP 3: Delete old closed channel message (if exists)
        if old_closed_msg_id:
            self.logger.info(
                f"🗑️ Deleting old closed message {old_closed_msg_id} from {closed_channel_id}"
            )
            delete_result = await self.telegram.delete_message(
                closed_channel_id,
                old_closed_msg_id
            )
            if not delete_result['success']:
                self.logger.warning(
                    f"⚠️ Could not delete old closed message: {delete_result['error']}"
                )
                # Continue anyway - not critical

        # STEP 4: Send new donation message to closed channel
        self.logger.info(f"📤 Sending to closed channel: {closed_channel_id}")
        closed_result = await self._send_donation_message(broadcast_entry)
        closed_sent = closed_result['success']
        new_closed_msg_id = closed_result.get('message_id')

        if not closed_sent:
            error_msg = f"Closed channel: {closed_result['error']}"
            errors.append(error_msg)
            self.logger.error(f"❌ {error_msg}")

        # STEP 5: Update message IDs in database
        if new_open_msg_id or new_closed_msg_id:
            self.tracker.update_message_ids(
                broadcast_id,
                open_message_id=new_open_msg_id,
                closed_message_id=new_closed_msg_id
            )

        # Determine overall success
        success = open_sent and closed_sent

        # Update broadcast status
        if success:
            self.tracker.mark_success(broadcast_id)
            self.logger.info(
                f"✅ Broadcast {str(broadcast_id)[:8]}... completed successfully"
            )
        else:
            error_msg = '; '.join(errors)
            self.tracker.mark_failure(broadcast_id, error_msg)
            self.logger.error(
                f"❌ Broadcast {str(broadcast_id)[:8]}... failed: {error_msg}"
            )

        return {
            'success': success,
            'open_channel_sent': open_sent,
            'closed_channel_sent': closed_sent,
            'errors': errors,
            'broadcast_id': str(broadcast_id),
            'new_open_message_id': new_open_msg_id,
            'new_closed_message_id': new_closed_msg_id
        }

    except Exception as e:
        # ... (existing exception handling)
```

**Step 2: Update send methods to return message IDs**

```python
async def _send_subscription_message(
    self,
    broadcast_entry: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send subscription tier message to open channel.

    Returns:
        {
            'success': bool,
            'error': str or None,
            'message_id': int or None  # NEW: Telegram message ID
        }
    """
    try:
        # ... (existing message construction logic)

        # Send message and capture response
        message = await self.telegram.send_subscription_message(
            channel_id=open_channel_id,
            text=message_text,
            buttons=tier_buttons
        )

        # Extract message ID from response
        message_id = message.message_id if message else None

        return {
            'success': True,
            'error': None,
            'message_id': message_id  # NEW
        }

    except Exception as e:
        self.logger.error(f"❌ Error sending subscription message: {e}")
        return {
            'success': False,
            'error': str(e),
            'message_id': None  # NEW
        }

async def _send_donation_message(
    self,
    broadcast_entry: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send donation button message to closed channel.

    Returns:
        {
            'success': bool,
            'error': str or None,
            'message_id': int or None  # NEW: Telegram message ID
        }
    """
    try:
        # ... (existing message construction logic)

        # Send message and capture response
        message = await self.telegram.send_donation_message(
            channel_id=closed_channel_id,
            text=message_text,
            button=donation_button
        )

        # Extract message ID from response
        message_id = message.message_id if message else None

        return {
            'success': True,
            'error': None,
            'message_id': message_id  # NEW
        }

    except Exception as e:
        self.logger.error(f"❌ Error sending donation message: {e}")
        return {
            'success': False,
            'error': str(e),
            'message_id': None  # NEW
        }
```

**Action Items:**
- [ ] Update `execute_broadcast()` to delete old messages
- [ ] Update `_send_subscription_message()` to return message_id
- [ ] Update `_send_donation_message()` to return message_id
- [ ] Add message ID extraction from telegram responses
- [ ] Test deletion + sending workflow
- [ ] **Status:** ⏳ PENDING

---

### Task 2.4: Update TelegramClient Send Methods
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/GCBroadcastService-10-26/clients/telegram_client.py`

**Enhancement Required:**

Ensure send methods return the full Message object (not just success/error):

```python
async def send_subscription_message(
    self,
    channel_id: str,
    text: str,
    buttons: List[Dict[str, Any]]
) -> telegram.Message:
    """
    Send subscription tier message with buttons to open channel.

    Returns:
        telegram.Message object with message_id attribute

    Raises:
        TelegramError on failure
    """
    # Build inline keyboard
    keyboard = self._build_tier_keyboard(buttons)

    # Send and return Message object
    message = await self.bot.send_message(
        chat_id=channel_id,
        text=text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

    self.logger.info(
        f"📤 Sent subscription message to {channel_id} "
        f"(message_id={message.message_id})"
    )

    return message  # Return full Message object

async def send_donation_message(
    self,
    channel_id: str,
    text: str,
    button: Dict[str, Any]
) -> telegram.Message:
    """
    Send donation button message to closed channel.

    Returns:
        telegram.Message object with message_id attribute

    Raises:
        TelegramError on failure
    """
    # Build inline keyboard
    keyboard = self._build_donation_keyboard(button)

    # Send and return Message object
    message = await self.bot.send_message(
        chat_id=channel_id,
        text=text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

    self.logger.info(
        f"📤 Sent donation message to {channel_id} "
        f"(message_id={message.message_id})"
    )

    return message  # Return full Message object
```

**Action Items:**
- [ ] Update send methods to return telegram.Message objects
- [ ] Add message_id logging for debugging
- [ ] Update error handling to propagate exceptions
- [ ] Test message ID extraction
- [ ] **Status:** ⏳ PENDING

---

## Phase 3: TelePay10-26 Message Tracking

**Objective:** Enhance TelePay10-26 broadcast_manager and closed_channel_manager for message tracking

### Task 3.1: Update Database Manager for Message ID Queries
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/TelePay10-26/database.py`

**Enhancement Required:**

```python
def get_last_broadcast_message_ids(
    self,
    open_channel_id: str
) -> Dict[str, Optional[int]]:
    """
    Get the last sent message IDs for a channel pair.

    Args:
        open_channel_id: The open channel ID to query

    Returns:
        {
            'last_open_message_id': int or None,
            'last_closed_message_id': int or None
        }
    """
    try:
        with self.pool.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        last_open_message_id,
                        last_closed_message_id
                    FROM broadcast_manager
                    WHERE open_channel_id = :open_channel_id
                    LIMIT 1
                """),
                {'open_channel_id': open_channel_id}
            ).fetchone()

            if result:
                return {
                    'last_open_message_id': result[0],
                    'last_closed_message_id': result[1]
                }
            else:
                return {
                    'last_open_message_id': None,
                    'last_closed_message_id': None
                }

    except Exception as e:
        self.logger.error(f"❌ Error fetching message IDs: {e}")
        return {
            'last_open_message_id': None,
            'last_closed_message_id': None
        }

def update_broadcast_message_ids(
    self,
    open_channel_id: str,
    open_message_id: Optional[int] = None,
    closed_message_id: Optional[int] = None
) -> bool:
    """
    Update the last sent message IDs for a channel pair.

    Args:
        open_channel_id: The open channel ID
        open_message_id: Telegram message ID sent to open channel
        closed_message_id: Telegram message ID sent to closed channel

    Returns:
        True if successful, False otherwise
    """
    try:
        with self.pool.engine.connect() as conn:
            update_fields = []
            params = {'open_channel_id': open_channel_id}

            if open_message_id is not None:
                update_fields.append("last_open_message_id = :open_msg_id")
                update_fields.append("last_open_message_sent_at = NOW()")
                params['open_msg_id'] = open_message_id

            if closed_message_id is not None:
                update_fields.append("last_closed_message_id = :closed_msg_id")
                update_fields.append("last_closed_message_sent_at = NOW()")
                params['closed_msg_id'] = closed_message_id

            if not update_fields:
                return False

            query = f"""
                UPDATE broadcast_manager
                SET {', '.join(update_fields)}
                WHERE open_channel_id = :open_channel_id
            """

            conn.execute(text(query), params)
            conn.commit()

            self.logger.info(
                f"📝 Updated message IDs for {open_channel_id} "
                f"(open={open_message_id}, closed={closed_message_id})"
            )

            return True

    except Exception as e:
        self.logger.error(f"❌ Error updating message IDs: {e}")
        return False
```

**Action Items:**
- [ ] Add `get_last_broadcast_message_ids()` method
- [ ] Add `update_broadcast_message_ids()` method
- [ ] Use SQLAlchemy `text()` for parameterized queries
- [ ] Add unit tests for both methods
- [ ] Test with existing and non-existent channel IDs
- [ ] **Status:** ⏳ PENDING

---

### Task 3.2: Update BroadcastManager for Message Deletion
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/TelePay10-26/broadcast_manager.py`

**Enhancement Required:**

```python
class BroadcastManager:
    def __init__(self, bot_token: str, bot_username: str, db_manager: DatabaseManager):
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.db_manager = db_manager
        self.bot = Bot(token=bot_token)  # NEW: Add Bot instance for deletion
        self.open_channel_list = []
        self.open_channel_info_map = {}

    async def delete_message_safe(
        self,
        chat_id: str,
        message_id: int
    ) -> bool:
        """
        Safely delete a message, handling errors gracefully.

        Args:
            chat_id: Channel ID
            message_id: Telegram message ID

        Returns:
            True if deleted or already gone, False if error
        """
        try:
            await self.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
            logger.info(f"🗑️ Deleted message {message_id} from {chat_id}")
            return True

        except telegram.error.BadRequest as e:
            if "message to delete not found" in str(e).lower():
                logger.warning(f"⚠️ Message {message_id} already deleted")
                return True  # Treat as success
            logger.error(f"❌ Cannot delete message {message_id}: {e}")
            return False

        except Exception as e:
            logger.error(f"❌ Error deleting message {message_id}: {e}")
            return False

    async def broadcast_hash_links(self):
        """
        Broadcast subscription links to open channels.

        NEW BEHAVIOR:
        - Deletes old subscription message before sending new one
        - Tracks message ID of new message for future deletion
        """
        if not self.open_channel_list:
            self.fetch_open_channel_list()

        for chat_id in self.open_channel_list:
            data = self.open_channel_info_map.get(chat_id, {})

            # Get old message ID for deletion
            message_ids = self.db_manager.get_last_broadcast_message_ids(chat_id)
            old_message_id = message_ids.get('last_open_message_id')

            # Delete old message if exists
            if old_message_id:
                logger.info(f"🗑️ Deleting old message {old_message_id} from {chat_id}")
                await self.delete_message_safe(chat_id, old_message_id)

            # Build buttons and message (existing logic)
            base_hash = self.encode_id(chat_id)
            buttons_cfg = []

            tier_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            for idx in (1, 2, 3):
                price = data.get(f"sub_{idx}_price")
                days = data.get(f"sub_{idx}_time")
                if price is None or days is None:
                    continue
                safe_sub = str(price).replace(".", "d")
                token = f"{base_hash}_{safe_sub}_{days}"
                url = f"https://t.me/{self.bot_username}?start={token}"
                emoji = tier_emojis.get(idx, "💰")
                buttons_cfg.append({"text": f"{emoji} ${price} for {days} days", "url": url})

            if not buttons_cfg:
                continue

            # Create message
            open_channel_title = data.get("open_channel_title", "Channel")
            open_channel_description = data.get("open_channel_description", "open channel")
            closed_channel_title = data.get("closed_channel_title", "Premium Channel")
            closed_channel_description = data.get("closed_channel_description", "exclusive content")

            welcome_message = (
                f"Hello, welcome to <b>{open_channel_title}: {open_channel_description}</b>\n\n"
                f"Choose your Subscription Tier to gain access to <b>{closed_channel_title}: {closed_channel_description}</b>."
            )

            reply_markup = self.build_menu_buttons(buttons_cfg)

            try:
                # Send new message using async Bot
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=welcome_message,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

                # Update message ID in database
                new_message_id = message.message_id
                self.db_manager.update_broadcast_message_ids(
                    open_channel_id=chat_id,
                    open_message_id=new_message_id
                )

                logger.info(
                    f"✅ Sent subscription message to {chat_id} "
                    f"(message_id={new_message_id})"
                )

            except Exception as e:
                logging.error(f"❌ Send error to {chat_id}: {e}")
```

**Action Items:**
- [ ] Import `telegram.Bot` and `telegram.error`
- [ ] Add `Bot` instance to __init__
- [ ] Add `delete_message_safe()` method
- [ ] Update `broadcast_hash_links()` to use async/await
- [ ] Replace `requests.post` with `Bot.send_message()`
- [ ] Add message ID tracking after send
- [ ] Test deletion + sending workflow
- [ ] **Status:** ⏳ PENDING

**IMPORTANT NOTE:** This changes `broadcast_hash_links()` from sync to async. All callers must be updated to use `await`.

---

### Task 3.3: Update ClosedChannelManager for Message Deletion
**Status:** ⏳ PENDING

**File to Modify:** `OCTOBER/10-26/TelePay10-26/closed_channel_manager.py`

**Enhancement Required:**

```python
async def send_donation_message_to_closed_channels(
    self,
    force_resend: bool = False
) -> Dict[str, Any]:
    """
    Send donation button to all closed channels where bot is admin.

    NEW BEHAVIOR:
    - Deletes old donation message before sending new one
    - Tracks message ID of new message for future deletion
    """
    closed_channels = self.db_manager.fetch_all_closed_channels()

    total_channels = len(closed_channels)
    successful = 0
    failed = 0
    errors = []

    self.logger.info(
        f"📨 Starting donation message broadcast to {total_channels} closed channels"
    )

    for channel_info in closed_channels:
        closed_channel_id = channel_info["closed_channel_id"]
        open_channel_id = channel_info["open_channel_id"]
        donation_message = channel_info.get(
            "closed_channel_donation_message",
            "Consider supporting our channel!"
        )

        # NEW: Get old message ID for deletion
        message_ids = self.db_manager.get_last_broadcast_message_ids(open_channel_id)
        old_message_id = message_ids.get('last_closed_message_id')

        try:
            # NEW: Delete old message if exists
            if old_message_id:
                self.logger.info(
                    f"🗑️ Deleting old message {old_message_id} from {closed_channel_id}"
                )
                try:
                    await self.bot.delete_message(
                        chat_id=closed_channel_id,
                        message_id=old_message_id
                    )
                except Exception as del_error:
                    if "message to delete not found" not in str(del_error).lower():
                        self.logger.warning(
                            f"⚠️ Could not delete old message: {del_error}"
                        )
                    # Continue even if deletion fails

            # Create inline keyboard with single donate button
            reply_markup = self._create_donation_button(open_channel_id)

            # Format message content
            message_text = self._format_donation_message(donation_message)

            # Send to closed channel
            message = await self.bot.send_message(
                chat_id=closed_channel_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

            # NEW: Update message ID in database
            new_message_id = message.message_id
            self.db_manager.update_broadcast_message_ids(
                open_channel_id=open_channel_id,
                closed_message_id=new_message_id
            )

            successful += 1
            self.logger.info(
                f"📨 Sent donation message to {closed_channel_id} "
                f"(message_id={new_message_id})"
            )

        except Forbidden as e:
            # ... (existing error handling)
        except BadRequest as e:
            # ... (existing error handling)
        except TelegramError as e:
            # ... (existing error handling)
        except Exception as e:
            # ... (existing error handling)

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.1)

    # ... (existing summary logging)

    return {
        "total_channels": total_channels,
        "successful": successful,
        "failed": failed,
        "errors": errors
    }
```

**Action Items:**
- [ ] Add message ID query before sending
- [ ] Add old message deletion logic
- [ ] Update database after sending new message
- [ ] Add message_id to logging
- [ ] Test deletion + sending workflow
- [ ] **Status:** ⏳ PENDING

---

## Phase 4: Message Deletion Logic

**Objective:** Implement robust message deletion with best practices

### Task 4.1: Document Message Deletion Best Practices
**Status:** ⏳ PENDING

**Best Practices from Context7 (python-telegram-bot):**

Based on Telegram Bot API and python-telegram-bot library:

1. **Message Deletion Permissions:**
   - Bot must be admin in channel to delete any message
   - Bot can only delete messages it sent (or any if admin)
   - Deletion fails silently if message already deleted

2. **Error Handling:**
   - `BadRequest: Message to delete not found` → Treat as success
   - `BadRequest: Not enough rights` → Log warning, continue
   - `RetryAfter` → Wait and retry once
   - Other errors → Log and continue (don't block broadcast)

3. **Rate Limiting:**
   - Telegram limits: ~30 messages/second globally
   - Add 100ms delay between deletions: `await asyncio.sleep(0.1)`
   - Respect RetryAfter headers from API

4. **Idempotency:**
   - Deletion is idempotent (deleting twice has same effect)
   - Always safe to attempt deletion even if uncertain

5. **Message ID Validation:**
   - Message IDs are positive integers
   - Store as BIGINT in database (can exceed INT range)
   - Validate message_id > 0 before attempting deletion

**Action Items:**
- [ ] Document best practices in code comments
- [ ] Add validation for message_id > 0
- [ ] Implement rate limiting (100ms delay)
- [ ] Add retry logic for RetryAfter
- [ ] **Status:** ⏳ PENDING

---

### Task 4.2: Create Message Deletion Utility Module
**Status:** ⏳ PENDING

**File to Create:** `OCTOBER/10-26/TelePay10-26/bot/utils/message_deletion.py`

**Purpose:** Shared utility for safe message deletion across codebase

```python
#!/usr/bin/env python3
"""
Message Deletion Utilities

Provides safe, robust message deletion with error handling,
rate limiting, and retry logic.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import BadRequest, RetryAfter, TelegramError

logger = logging.getLogger(__name__)


async def delete_message_safe(
    bot: Bot,
    chat_id: str,
    message_id: int,
    retry_on_rate_limit: bool = True
) -> Dict[str, Any]:
    """
    Safely delete a Telegram message with comprehensive error handling.

    Args:
        bot: Telegram Bot instance
        chat_id: Channel/chat ID where message exists
        message_id: Telegram message ID to delete
        retry_on_rate_limit: Whether to retry once on rate limit

    Returns:
        {
            'success': bool,
            'error': str or None,
            'deleted': bool,  # True if actually deleted, False if already gone
            'skipped': bool   # True if skipped due to error
        }

    Error Handling:
        - Message not found → success=True, deleted=False (idempotent)
        - No permission → success=False, skipped=True
        - Rate limit → waits and retries once if retry_on_rate_limit=True

    Best Practices:
        - Call with 100ms delay between deletions to avoid rate limits
        - Treat "message not found" as success (idempotent behavior)
        - Don't fail entire workflow if single deletion fails
    """
    # Validate inputs
    if not message_id or message_id <= 0:
        logger.warning(f"⚠️ Invalid message_id: {message_id}")
        return {
            'success': False,
            'error': 'Invalid message_id',
            'deleted': False,
            'skipped': True
        }

    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )

        logger.info(f"🗑️ Deleted message {message_id} from {chat_id}")
        return {
            'success': True,
            'error': None,
            'deleted': True,
            'skipped': False
        }

    except BadRequest as e:
        error_str = str(e).lower()

        # Message already deleted - treat as success
        if "message to delete not found" in error_str:
            logger.debug(
                f"⚠️ Message {message_id} already deleted from {chat_id}"
            )
            return {
                'success': True,
                'error': None,
                'deleted': False,  # Was already gone
                'skipped': False
            }

        # No permission - log warning but don't fail
        if "not enough rights" in error_str or "chat administrator" in error_str:
            logger.warning(
                f"⚠️ No permission to delete message {message_id} from {chat_id}"
            )
            return {
                'success': False,
                'error': f"No permission: {e}",
                'deleted': False,
                'skipped': True
            }

        # Other BadRequest errors
        logger.error(
            f"❌ Cannot delete message {message_id} from {chat_id}: {e}"
        )
        return {
            'success': False,
            'error': str(e),
            'deleted': False,
            'skipped': True
        }

    except RetryAfter as e:
        # Rate limit - wait and retry once if enabled
        if not retry_on_rate_limit:
            logger.warning(
                f"⏱️ Rate limited for message {message_id}, skipping (retry disabled)"
            )
            return {
                'success': False,
                'error': f"Rate limited: {e}",
                'deleted': False,
                'skipped': True
            }

        wait_time = e.retry_after
        logger.warning(
            f"⏱️ Rate limited, waiting {wait_time}s before retrying "
            f"message {message_id}..."
        )
        await asyncio.sleep(wait_time)

        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(
                f"🗑️ Deleted message {message_id} from {chat_id} (after retry)"
            )
            return {
                'success': True,
                'error': None,
                'deleted': True,
                'skipped': False
            }
        except Exception as retry_error:
            logger.error(
                f"❌ Retry failed for message {message_id}: {retry_error}"
            )
            return {
                'success': False,
                'error': f"Retry failed: {retry_error}",
                'deleted': False,
                'skipped': True
            }

    except TelegramError as e:
        # General Telegram API errors
        logger.error(
            f"❌ Telegram error deleting message {message_id}: {e}"
        )
        return {
            'success': False,
            'error': f"Telegram error: {e}",
            'deleted': False,
            'skipped': True
        }

    except Exception as e:
        # Unexpected errors
        logger.error(
            f"❌ Unexpected error deleting message {message_id}: {e}",
            exc_info=True
        )
        return {
            'success': False,
            'error': f"Unexpected error: {e}",
            'deleted': False,
            'skipped': True
        }


async def delete_multiple_messages(
    bot: Bot,
    chat_id: str,
    message_ids: list[int],
    delay_ms: int = 100
) -> Dict[str, Any]:
    """
    Delete multiple messages with rate limiting.

    Args:
        bot: Telegram Bot instance
        chat_id: Channel/chat ID where messages exist
        message_ids: List of message IDs to delete
        delay_ms: Delay in milliseconds between deletions

    Returns:
        {
            'total': int,
            'deleted': int,
            'already_gone': int,
            'skipped': int,
            'errors': List[Dict]
        }
    """
    total = len(message_ids)
    deleted = 0
    already_gone = 0
    skipped = 0
    errors = []

    logger.info(f"🗑️ Deleting {total} messages from {chat_id}...")

    for message_id in message_ids:
        result = await delete_message_safe(bot, chat_id, message_id)

        if result['success']:
            if result['deleted']:
                deleted += 1
            else:
                already_gone += 1
        else:
            skipped += 1
            errors.append({
                'message_id': message_id,
                'error': result['error']
            })

        # Rate limiting delay
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

    logger.info(
        f"✅ Deletion complete: {deleted} deleted, "
        f"{already_gone} already gone, {skipped} skipped"
    )

    return {
        'total': total,
        'deleted': deleted,
        'already_gone': already_gone,
        'skipped': skipped,
        'errors': errors
    }
```

**Action Items:**
- [ ] Create message deletion utility module
- [ ] Add comprehensive error handling
- [ ] Add rate limiting support
- [ ] Add unit tests for all error scenarios
- [ ] Document usage examples
- [ ] **Status:** ⏳ PENDING

---

## Phase 5: Error Handling and Edge Cases

**Objective:** Handle all edge cases gracefully

### Task 5.1: Document Edge Cases
**Status:** ⏳ PENDING

**Edge Case Matrix:**

| Edge Case | Scenario | Expected Behavior |
|-----------|----------|-------------------|
| **Message Already Deleted** | Old message_id exists in DB, but message was manually deleted by admin | Treat as success, log debug message, continue |
| **Bot Not Admin** | Bot lacks permission to delete messages | Log warning, skip deletion, continue with new message send |
| **Channel Deleted** | Closed channel no longer exists | Catch error, mark broadcast as failed, continue to next |
| **Message Too Old** | Telegram only allows deleting messages < 48 hours old | Catch error, log warning, continue (will fail naturally) |
| **Rate Limit Hit** | Too many deletions in short time | Wait for retry_after seconds, retry once |
| **Database NULL** | last_*_message_id is NULL (first broadcast) | Skip deletion step, send new message normally |
| **Network Timeout** | Network error during deletion | Log error, skip deletion, continue with send |
| **Concurrent Broadcasts** | Two services try to delete same message | First succeeds, second gets "not found" → both succeed |

**Action Items:**
- [ ] Document each edge case in code comments
- [ ] Add unit tests for each edge case
- [ ] Verify graceful degradation (failures don't block workflow)
- [ ] **Status:** ⏳ PENDING

---

### Task 5.2: Implement Edge Case Handling
**Status:** ⏳ PENDING

**Enhancement to Deletion Logic:**

```python
# Example: Handle "Message Too Old" error
except BadRequest as e:
    error_str = str(e).lower()

    if "message can't be deleted" in error_str:
        logger.warning(
            f"⚠️ Message {message_id} too old to delete (>48h), "
            f"continuing anyway"
        )
        # Don't treat as error - message will be replaced by new one
        return {'success': True, 'deleted': False, 'skipped': False}
```

**Action Items:**
- [ ] Add handling for "message can't be deleted" error
- [ ] Add handling for channel not found
- [ ] Add handling for bot kicked from channel
- [ ] Test each edge case scenario
- [ ] **Status:** ⏳ PENDING

---

### Task 5.3: Add Monitoring and Alerting
**Status:** ⏳ PENDING

**Metrics to Track:**

1. **Deletion Success Rate:**
   - Count: successful deletions / attempted deletions
   - Alert if < 90% (indicates permission issues)

2. **Messages Skipped:**
   - Count: deletions skipped due to errors
   - Alert if > 10% (indicates configuration issues)

3. **Rate Limit Events:**
   - Count: number of RetryAfter errors
   - Alert if > 5 per hour (indicates too aggressive sending)

4. **Orphaned Messages:**
   - Query: broadcast_manager rows with NULL message_ids
   - Alert if count increases (indicates send failures)

**Implementation:**

```python
# Add to broadcast_executor.py or similar

class BroadcastMetrics:
    """Track broadcast and deletion metrics for monitoring."""

    def __init__(self):
        self.deletions_attempted = 0
        self.deletions_successful = 0
        self.deletions_skipped = 0
        self.rate_limit_events = 0

    def record_deletion(self, result: Dict[str, Any]):
        """Record a deletion attempt."""
        self.deletions_attempted += 1

        if result['success']:
            if result['deleted']:
                self.deletions_successful += 1
        else:
            if 'rate limit' in result.get('error', '').lower():
                self.rate_limit_events += 1
            if result['skipped']:
                self.deletions_skipped += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        success_rate = (
            self.deletions_successful / self.deletions_attempted
            if self.deletions_attempted > 0
            else 0
        )

        return {
            'deletions_attempted': self.deletions_attempted,
            'deletions_successful': self.deletions_successful,
            'deletions_skipped': self.deletions_skipped,
            'success_rate': success_rate,
            'rate_limit_events': self.rate_limit_events
        }
```

**Action Items:**
- [ ] Create metrics tracking class
- [ ] Add metrics logging to broadcast services
- [ ] Set up Cloud Monitoring dashboards
- [ ] Configure alerting thresholds
- [ ] **Status:** ⏳ PENDING

---

## Phase 6: Testing and Validation

**Objective:** Comprehensive testing of message deletion functionality

### Task 6.1: Unit Tests
**Status:** ⏳ PENDING

**File to Create:** `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tests/test_message_deletion.py`

```python
#!/usr/bin/env python3
"""
Unit tests for message deletion functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram.error import BadRequest, RetryAfter, TelegramError

# Import modules to test
from bot.utils.message_deletion import delete_message_safe, delete_multiple_messages


class TestDeleteMessageSafe:
    """Test safe message deletion utility."""

    @pytest.mark.asyncio
    async def test_successful_deletion(self):
        """Test successful message deletion."""
        bot = Mock()
        bot.delete_message = AsyncMock()

        result = await delete_message_safe(bot, "-100123456", 12345)

        assert result['success'] is True
        assert result['deleted'] is True
        assert result['error'] is None
        bot.delete_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_not_found(self):
        """Test deletion of already-deleted message."""
        bot = Mock()
        bot.delete_message = AsyncMock(
            side_effect=BadRequest("Message to delete not found")
        )

        result = await delete_message_safe(bot, "-100123456", 12345)

        # Should treat as success (idempotent)
        assert result['success'] is True
        assert result['deleted'] is False
        assert result['error'] is None

    @pytest.mark.asyncio
    async def test_no_permission(self):
        """Test deletion with insufficient permissions."""
        bot = Mock()
        bot.delete_message = AsyncMock(
            side_effect=BadRequest("Not enough rights to delete message")
        )

        result = await delete_message_safe(bot, "-100123456", 12345)

        assert result['success'] is False
        assert result['skipped'] is True
        assert 'No permission' in result['error']

    @pytest.mark.asyncio
    async def test_rate_limit_with_retry(self):
        """Test rate limit handling with retry."""
        bot = Mock()

        # First call raises RetryAfter, second succeeds
        bot.delete_message = AsyncMock(
            side_effect=[
                RetryAfter(retry_after=1),
                None
            ]
        )

        with patch('asyncio.sleep', new=AsyncMock()):
            result = await delete_message_safe(bot, "-100123456", 12345)

        assert result['success'] is True
        assert result['deleted'] is True
        assert bot.delete_message.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_message_id(self):
        """Test with invalid message ID."""
        bot = Mock()
        bot.delete_message = AsyncMock()

        result = await delete_message_safe(bot, "-100123456", 0)

        assert result['success'] is False
        assert result['skipped'] is True
        assert 'Invalid message_id' in result['error']
        bot.delete_message.assert_not_called()


class TestDeleteMultipleMessages:
    """Test batch message deletion."""

    @pytest.mark.asyncio
    async def test_delete_multiple_success(self):
        """Test successful batch deletion."""
        bot = Mock()
        bot.delete_message = AsyncMock()

        message_ids = [101, 102, 103]

        with patch('asyncio.sleep', new=AsyncMock()):
            result = await delete_multiple_messages(
                bot,
                "-100123456",
                message_ids,
                delay_ms=0  # No delay for test speed
            )

        assert result['total'] == 3
        assert result['deleted'] == 3
        assert result['skipped'] == 0

    @pytest.mark.asyncio
    async def test_delete_multiple_mixed_results(self):
        """Test batch deletion with mixed results."""
        bot = Mock()

        # First succeeds, second not found, third fails
        bot.delete_message = AsyncMock(
            side_effect=[
                None,
                BadRequest("Message to delete not found"),
                BadRequest("Not enough rights")
            ]
        )

        message_ids = [101, 102, 103]

        with patch('asyncio.sleep', new=AsyncMock()):
            result = await delete_multiple_messages(
                bot,
                "-100123456",
                message_ids,
                delay_ms=0
            )

        assert result['total'] == 3
        assert result['deleted'] == 1
        assert result['already_gone'] == 1
        assert result['skipped'] == 1
        assert len(result['errors']) == 1


# Add more test classes for:
# - BroadcastExecutor deletion logic
# - BroadcastManager deletion logic
# - ClosedChannelManager deletion logic
# - Database message ID storage/retrieval
```

**Action Items:**
- [ ] Create unit test file
- [ ] Write tests for all deletion scenarios
- [ ] Write tests for database operations
- [ ] Write tests for edge cases
- [ ] Run tests with pytest
- [ ] Achieve > 90% code coverage
- [ ] **Status:** ⏳ PENDING

---

### Task 6.2: Integration Tests
**Status:** ⏳ PENDING

**File to Create:** `OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tests/test_broadcast_deletion_integration.py`

**Test Scenarios:**

1. **Scenario: First Broadcast (No Prior Message)**
   - Precondition: `last_open_message_id` = NULL
   - Expected: Skip deletion, send new message, store message_id

2. **Scenario: Second Broadcast (Delete + Replace)**
   - Precondition: `last_open_message_id` = 12345
   - Expected: Delete 12345, send new message, update message_id

3. **Scenario: Message Already Deleted Manually**
   - Precondition: `last_open_message_id` = 12345 (but message deleted by admin)
   - Expected: Deletion returns "not found" (success), send new message

4. **Scenario: Bot Lacks Permission**
   - Precondition: Bot not admin in channel
   - Expected: Deletion fails, still attempts send (may also fail)

5. **Scenario: Concurrent Broadcasts**
   - Precondition: Two services try to broadcast simultaneously
   - Expected: First deletes old + sends new, second gets "not found" on delete

**Action Items:**
- [ ] Create integration test file
- [ ] Set up test channels (open + closed)
- [ ] Write tests for each scenario
- [ ] Test with actual Telegram API (staging)
- [ ] Verify database state after each test
- [ ] **Status:** ⏳ PENDING

---

### Task 6.3: Manual Testing Checklist
**Status:** ⏳ PENDING

**Manual Test Procedures:**

**Test 1: GCBroadcastService Scheduled Broadcast**
- [ ] Create test channel pair in database
- [ ] Set `next_send_time` to trigger broadcast
- [ ] Wait for GCBroadcastScheduler to execute
- [ ] Verify old message deleted from open channel
- [ ] Verify new subscription message sent to open channel
- [ ] Verify old message deleted from closed channel
- [ ] Verify new donation message sent to closed channel
- [ ] Verify `last_*_message_id` columns updated in database
- [ ] Check logs for deletion success messages

**Test 2: TelePay10-26 Manual Broadcast**
- [ ] Trigger manual broadcast via bot command or admin panel
- [ ] Verify old messages deleted before new messages sent
- [ ] Verify new message IDs stored in database
- [ ] Check logs for proper deletion and send sequence

**Test 3: Edge Case: Message Already Deleted**
- [ ] Send initial broadcast (message sent)
- [ ] Manually delete the message from channel
- [ ] Trigger second broadcast
- [ ] Verify "message not found" handled gracefully
- [ ] Verify new message sent successfully
- [ ] Verify database updated with new message_id

**Test 4: Edge Case: Bot Not Admin**
- [ ] Remove bot admin permissions from test channel
- [ ] Trigger broadcast
- [ ] Verify deletion fails gracefully (logged, not crashed)
- [ ] Verify send also fails (expected)
- [ ] Restore bot admin permissions
- [ ] Verify next broadcast succeeds

**Test 5: Rate Limiting**
- [ ] Trigger 10 broadcasts rapidly (< 1 second apart)
- [ ] Verify rate limiting handled (RetryAfter waits)
- [ ] Verify all broadcasts eventually succeed
- [ ] Check logs for rate limit warnings

**Action Items:**
- [ ] Execute all manual tests
- [ ] Document results for each test
- [ ] Fix any issues found
- [ ] Retest after fixes
- [ ] **Status:** ⏳ PENDING

---

## Phase 7: Deployment and Monitoring

**Objective:** Deploy to production and monitor for issues

### Task 7.1: Pre-Deployment Checklist
**Status:** ⏳ PENDING

**Pre-Flight Checks:**
- [ ] All unit tests passing (>90% coverage)
- [ ] All integration tests passing
- [ ] Manual testing completed successfully
- [ ] Database migration tested on clone database
- [ ] Rollback plan documented
- [ ] Code reviewed by second developer (if applicable)
- [ ] PROGRESS.md updated with changes
- [ ] DECISIONS.md updated with architectural decisions
- [ ] SECRET_CONFIG.md verified (no new secrets needed)

---

### Task 7.2: Deployment Steps
**Status:** ⏳ PENDING

**Deployment Sequence:**

**Step 1: Database Migration**
```bash
cd OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts
bash deploy_message_tracking_migration.sh
```
- [ ] Execute migration on production database
- [ ] Verify columns created: `\d broadcast_manager`
- [ ] **Status:** ⏳ PENDING

**Step 2: Deploy GCBroadcastService**
```bash
cd OCTOBER/10-26/GCBroadcastService-10-26
gcloud builds submit --tag gcr.io/telepay-459221/gcbroadcastservice
gcloud run deploy gcbroadcastservice \
  --image gcr.io/telepay-459221/gcbroadcastservice \
  --platform managed \
  --region us-central1 \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
```
- [ ] Build and deploy new version
- [ ] Verify deployment successful
- [ ] Test with manual trigger
- [ ] **Status:** ⏳ PENDING

**Step 3: Deploy TelePay10-26**
```bash
cd OCTOBER/10-26/TelePay10-26
gcloud builds submit --tag gcr.io/telepay-459221/telepay10-26
gcloud run deploy telepay10-26 \
  --image gcr.io/telepay-459221/telepay10-26 \
  --platform managed \
  --region us-central1 \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
```
- [ ] Build and deploy new version
- [ ] Verify deployment successful
- [ ] Test with manual broadcast
- [ ] **Status:** ⏳ PENDING

**Step 4: Monitor Initial Broadcasts**
- [ ] Watch logs for first 5 scheduled broadcasts
- [ ] Verify deletions occurring correctly
- [ ] Verify message IDs being stored
- [ ] Check for any errors in logs
- [ ] **Status:** ⏳ PENDING

---

### Task 7.3: Monitoring and Alerts
**Status:** ⏳ PENDING

**Cloud Logging Queries:**

**Query 1: Deletion Success Rate**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastservice"
"Deleted message" OR "Could not delete"
```

**Query 2: Message ID Updates**
```
resource.type="cloud_run_revision"
"Updated message IDs for broadcast"
```

**Query 3: Deletion Errors**
```
resource.type="cloud_run_revision"
severity>=ERROR
"delete message" OR "deletion"
```

**Action Items:**
- [ ] Create Cloud Logging saved queries
- [ ] Set up log-based metrics for deletion success rate
- [ ] Create dashboard for message deletion metrics
- [ ] Configure alerts for:
  - Deletion success rate < 90%
  - Rate limit events > 5/hour
  - Null message_ids after send
- [ ] **Status:** ⏳ PENDING

---

### Task 7.4: Post-Deployment Validation
**Status:** ⏳ PENDING

**Validation Period: 7 Days**

**Daily Checks (Days 1-7):**
- [ ] Day 1: Check logs hourly for issues
- [ ] Day 2: Check logs every 4 hours
- [ ] Day 3-7: Check logs daily
- [ ] Verify deletion success rate > 95%
- [ ] Verify no rate limit alerts
- [ ] Verify message_ids being stored correctly
- [ ] Verify channels only have 1 message (latest)

**Issues to Watch For:**
- Repeated rate limit errors (indicates too aggressive)
- Permission errors (bot not admin in channels)
- Database errors (connection issues, NULL constraints)
- Memory leaks (increasing memory usage over time)

**Action Items:**
- [ ] Monitor for 7 days
- [ ] Document any issues found
- [ ] Fix issues and redeploy if needed
- [ ] Mark deployment as stable if no issues
- [ ] **Status:** ⏳ PENDING

---

## Success Criteria

**Functional Requirements:**
- ✅ Only 1 subscription tier message exists per open channel (most recent)
- ✅ Only 1 donation button message exists per closed channel (most recent)
- ✅ Old messages automatically deleted when new broadcasts sent
- ✅ User and admin messages preserved (only bot messages deleted)
- ✅ Message IDs tracked in `broadcast_manager` table

**Performance Requirements:**
- ✅ Deletion success rate > 95%
- ✅ Broadcast latency increase < 200ms (due to deletion step)
- ✅ Zero crashes due to deletion errors
- ✅ Rate limit events < 5 per hour

**Quality Requirements:**
- ✅ Unit test coverage > 90%
- ✅ All integration tests passing
- ✅ Manual testing completed successfully
- ✅ Code reviewed and approved
- ✅ Documentation updated (PROGRESS.md, DECISIONS.md)

**Monitoring Requirements:**
- ✅ Cloud Logging queries created
- ✅ Dashboards created for deletion metrics
- ✅ Alerts configured for anomalies
- ✅ 7-day post-deployment monitoring completed

---

## Rollback Plan

**If Critical Issues Found:**

**Step 1: Revert Service Deployments**
```bash
# Revert GCBroadcastService to previous version
gcloud run services update-traffic gcbroadcastservice \
  --to-revisions=PREVIOUS_REVISION=100

# Revert TelePay10-26 to previous version
gcloud run services update-traffic telepay10-26 \
  --to-revisions=PREVIOUS_REVISION=100
```

**Step 2: Rollback Database (If Necessary)**
```bash
cd OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/scripts
PGPASSWORD="$DB_PASSWORD" psql \
  -h /cloudsql/telepay-459221:us-central1:telepaypsql \
  -U postgres \
  -d telepaydb \
  -f rollback_message_tracking_columns.sql
```

**Step 3: Verify Rollback**
- [ ] Verify old service versions running
- [ ] Verify broadcasts working (old behavior)
- [ ] Check logs for errors
- [ ] Document rollback reason

**When to Rollback:**
- Deletion success rate < 80% for > 1 hour
- Broadcast failures > 20%
- Database errors preventing broadcasts
- Memory leaks causing OOM crashes

---

## Documentation Updates

**Files to Update:**

1. **PROGRESS.md** (after each phase completion)
   ```markdown
   ## 2025-01-XX: Live-Time Broadcast Implementation

   ✅ Added message tracking columns to broadcast_manager table
   ✅ Implemented message deletion in GCBroadcastService
   ✅ Implemented message deletion in TelePay10-26
   ✅ Created message deletion utility module
   ✅ Added comprehensive error handling
   ✅ Deployed to production and validated

   Result: Channels now maintain only latest broadcast messages
   ```

2. **DECISIONS.md**
   ```markdown
   ## 2025-01-XX: Message Deletion Architecture

   🏗️ DECISION: Track message IDs in broadcast_manager table
   - Rationale: Enables deletion of old messages before sending new ones
   - Columns: last_open_message_id, last_closed_message_id, timestamps
   - Alternatives considered: External tracking table (rejected - too complex)

   🏗️ DECISION: Treat "message not found" as success (idempotent)
   - Rationale: Manual deletions by admins shouldn't block broadcasts
   - Implementation: Catch BadRequest, check error string, return success

   🏗️ DECISION: Don't fail broadcasts if deletion fails
   - Rationale: Sending new message is more important than deleting old
   - Implementation: Log warnings, continue with send even if delete fails
   ```

3. **BUGS.md** (if issues found during implementation)
   ```markdown
   ## 2025-01-XX: Message Deletion Issues

   ❌ BUG: Rate limits hit when deleting >30 messages/second
   - Solution: Added 100ms delay between deletions
   - Status: FIXED
   ```

---

## Estimated Timeline

**Phase 1: Database Schema** - 2 hours
- Create migration scripts
- Test on clone database
- Deploy to production

**Phase 2: GCBroadcastService** - 8 hours
- Update TelegramClient (2h)
- Update BroadcastTracker (2h)
- Update BroadcastExecutor (4h)

**Phase 3: TelePay10-26** - 6 hours
- Update DatabaseManager (2h)
- Update BroadcastManager (2h)
- Update ClosedChannelManager (2h)

**Phase 4: Message Deletion Logic** - 4 hours
- Create utility module (2h)
- Add error handling (2h)

**Phase 5: Edge Cases** - 3 hours
- Document edge cases (1h)
- Implement handling (2h)

**Phase 6: Testing** - 8 hours
- Unit tests (3h)
- Integration tests (3h)
- Manual testing (2h)

**Phase 7: Deployment** - 3 hours
- Deploy services (1h)
- Monitor and validate (2h)

**Total Estimated Time: 34 hours (~5 days)**

---

**Report Generated:** 2025-01-14
**Status:** Planning Phase Complete
**Next Action:** Begin Phase 1 (Database Schema Enhancement)

---

**END OF CHECKLIST**
