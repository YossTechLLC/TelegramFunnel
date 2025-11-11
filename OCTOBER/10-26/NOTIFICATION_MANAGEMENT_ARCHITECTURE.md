# Notification Management Architecture
## Owner Notifications for Subscription & Donation Payments

**Document Version:** 1.0
**Created:** 2025-11-11
**Status:** Architecture Specification

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Solution](#proposed-solution)
4. [Database Schema Changes](#database-schema-changes)
5. [Backend API Changes](#backend-api-changes)
6. [Frontend Web Interface Changes](#frontend-web-interface-changes)
7. [Telegram Bot Notification System](#telegram-bot-notification-system)
8. [NowPayments IPN Integration](#nowpayments-ipn-integration)
9. [Notification Service Architecture](#notification-service-architecture)
10. [Security & Privacy Considerations](#security--privacy-considerations)
11. [Error Handling & Recovery](#error-handling--recovery)
12. [Validation & Constraints](#validation--constraints)
13. [Migration Strategy](#migration-strategy)
14. [Testing Plan](#testing-plan)
15. [Deployment Checklist](#deployment-checklist)

---

## Executive Summary

### Objective
Enable channel owners to receive **real-time Telegram notifications** when:
- A customer completes a subscription payment (any tier)
- A customer completes a donation payment

Notifications will be sent **only after NowPayments IPN confirms `status: finished`**, ensuring payment completion before notifying the channel owner.

### Key Features
- **Opt-in System**: Channel owners explicitly enable/disable notifications during registration or editing
- **Manual Telegram ID Entry**: Owners provide their Telegram ID (avoiding complex multi-owner detection)
- **Payment Confirmation Trigger**: Notifications triggered only on confirmed payments
- **Rich Notification Content**: Includes payment amount, user info, channel info, and timestamp
- **Modular Architecture**: Separate notification service for maintainability and reusability

### Impact Areas
| Component | Changes Required | Complexity |
|-----------|------------------|------------|
| Database Schema | Add 2 new columns | Low |
| GCRegisterAPI-10-26 | Update models, services, routes | Medium |
| GCRegisterWeb-10-26 | Add notification UI section | Medium |
| np-webhook-10-26 | Add notification trigger | Medium |
| TelePay Bot | Create notification service | High |
| Migration Scripts | Create migration SQL | Low |

### Success Criteria
- ✅ Channel owners can enable/disable notifications during registration
- ✅ Channel owners can edit notification settings for existing channels
- ✅ Telegram ID validation enforces non-empty when enabled
- ✅ Notifications sent only after NowPayments IPN confirms `status: finished`
- ✅ Notifications include comprehensive payment details
- ✅ System handles failed notification delivery gracefully
- ✅ Modular notification service can be reused for other features

---

## Current State Analysis

### Existing Flow: Payment to Notification Gap

**Current Payment Flow:**
1. User initiates payment (Subscription or Donation)
2. NowPayments processes payment
3. NowPayments IPN callback → `np-webhook-10-26`
4. `np-webhook-10-26` validates signature and updates database
5. `np-webhook-10-26` triggers `GCWebhook1` for payment orchestration
6. Payment processing completes
7. **❌ No notification sent to channel owner**

**Missing Components:**
- No storage for channel owner's Telegram ID
- No notification service in TelePay bot
- No trigger mechanism from IPN handler
- No UI for owners to configure notifications

### Existing Database Schema

**Table:** `main_clients_database`

**Current Relevant Columns:**
```sql
open_channel_id             VARCHAR(14)  NOT NULL PRIMARY KEY
closed_channel_id           VARCHAR(14)  NOT NULL
open_channel_title          VARCHAR(100) NOT NULL
closed_channel_title        VARCHAR(100) NOT NULL
client_wallet_address       VARCHAR(100) NOT NULL
-- ... subscription tiers, payout config, etc.
```

**Missing Columns:**
- No field for notification recipient Telegram ID
- No field for notification enable/disable status

### Existing Registration Flow

**Files Involved:**
- `GCRegisterAPI-10-26/api/models/channel.py` - Pydantic models
- `GCRegisterAPI-10-26/api/services/channel_service.py` - Business logic
- `GCRegisterAPI-10-26/api/routes/channels.py` - API endpoints
- `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx` - Registration UI
- `GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx` - Edit UI

**Current UI Layout (Registration Page):**
1. Channel Information (Open & Closed)
2. Subscription Tiers Configuration
3. **Donation Message Configuration** ← Insert notification section BELOW this
4. Payment Configuration (Wallet, Currency, Network)
5. Threshold Payout Configuration

---

## Proposed Solution

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Channel Owner (Web UI)                       │
│         www.paygateprime.com - GCRegisterWeb-10-26              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ 1. Register/Edit Channel
                                │    + Enable Notifications
                                │    + Provide Telegram ID
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              GCRegisterAPI-10-26 (Backend API)                  │
│  • Validate notification settings                               │
│  • Store notification_id & notification_status in DB             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ 2. Channel Config Stored
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                main_clients_database (PostgreSQL)               │
│  • notification_id (bigint)                                      │
│  • notification_status (boolean) DEFAULT false                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                  ┌─────────────┴──────────────┐
                  │                            │
                  ▼                            ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│   User Makes Payment     │   │   User Makes Donation        │
│   (Subscription Tier)    │   │   (Custom Amount)            │
└──────────┬───────────────┘   └──────────┬───────────────────┘
           │                              │
           │ 3. Payment processed by NowPayments
           │                              │
           └──────────────┬───────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│           NowPayments IPN Callback → np-webhook-10-26           │
│  • Validates signature                                           │
│  • Checks payment_status == "finished"                           │
│  • Updates private_channel_users_database                        │
│  • Triggers GCWebhook1                                           │
│  • 🆕 Triggers NotificationService (if enabled)                  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ 4. Notification Request
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│          TelePay Bot - NotificationService Module               │
│  Location: TelePay10-26/notification_service.py (NEW FILE)      │
│                                                                  │
│  • Receives notification request                                │
│  • Fetches notification_id from main_clients_database           │
│  • Checks notification_status (enabled?)                        │
│  • Formats rich notification message                            │
│  • Sends via bot.send_message()                                 │
│  • Logs delivery status                                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ 5. Notification Delivered
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Channel Owner's Telegram (Private Chat)            │
│                                                                  │
│  🎉 New Subscription Payment!                                    │
│  Channel: Premium Content (#1234567890)                         │
│  User: @username (123456789)                                    │
│  Tier: 3 ($9.99 for 30 days)                                    │
│  Amount: 0.00034 ETH ($9.99 USD)                                │
│  Time: 2025-11-11 14:32:15 UTC                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Opt-In by Default**: `notification_status = false` ensures no unexpected messages
2. **Manual ID Entry**: Avoids complex channel admin detection (multiple owners, permissions, etc.)
3. **Payment Confirmation First**: Only notify after `status: finished` to avoid false positives
4. **Modular Service**: Separate `notification_service.py` for reusability and testing
5. **Graceful Degradation**: Failed notifications don't block payment processing
6. **Privacy Conscious**: Store only Telegram ID (no other PII required)

---

## Database Schema Changes

### New Columns in `main_clients_database`

**Column Specifications:**

```sql
-- Migration: add_notification_columns.sql
ALTER TABLE main_clients_database
ADD COLUMN notification_status BOOLEAN DEFAULT false NOT NULL,
ADD COLUMN notification_id BIGINT DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN main_clients_database.notification_status IS
'Enable/disable payment notifications for channel owner. Default false (disabled).';

COMMENT ON COLUMN main_clients_database.notification_id IS
'Telegram user ID to receive payment notifications. NULL if notifications disabled.';
```

**Column Details:**

| Column Name | Data Type | Nullable | Default | Description |
|------------|-----------|----------|---------|-------------|
| `notification_status` | `BOOLEAN` | NOT NULL | `false` | Enable/disable notifications |
| `notification_id` | `BIGINT` | NULL | `NULL` | Telegram ID of notification recipient |

**Validation Rules:**
- If `notification_status = true`, then `notification_id` must NOT be NULL
- If `notification_status = false`, `notification_id` can be NULL or ignored
- `notification_id` must be a valid Telegram user ID (positive bigint)

**Indexes (Optional - for performance):**
```sql
-- Create index for fast lookup by notification_status
CREATE INDEX idx_notification_status
ON main_clients_database(notification_status)
WHERE notification_status = true;
```

### Database Migration Strategy

**Migration File:** `TOOLS_SCRIPTS_TESTS/scripts/add_notification_columns.sql`

```sql
-- Add notification columns to main_clients_database
-- Version: 1.0
-- Date: 2025-11-11

BEGIN;

-- Add columns
ALTER TABLE main_clients_database
ADD COLUMN IF NOT EXISTS notification_status BOOLEAN DEFAULT false NOT NULL,
ADD COLUMN IF NOT EXISTS notification_id BIGINT DEFAULT NULL;

-- Add comments
COMMENT ON COLUMN main_clients_database.notification_status IS
'Enable/disable payment notifications for channel owner. Default false (disabled).';

COMMENT ON COLUMN main_clients_database.notification_id IS
'Telegram user ID to receive payment notifications. NULL if notifications disabled.';

-- Verify columns exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
        AND column_name = 'notification_status'
    ) THEN
        RAISE EXCEPTION 'Failed to create notification_status column';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'main_clients_database'
        AND column_name = 'notification_id'
    ) THEN
        RAISE EXCEPTION 'Failed to create notification_id column';
    END IF;
END $$;

COMMIT;
```

**Rollback Script:** `TOOLS_SCRIPTS_TESTS/scripts/rollback_notification_columns.sql`

```sql
-- Rollback notification columns from main_clients_database
-- Version: 1.0
-- Date: 2025-11-11

BEGIN;

-- Drop columns (if they exist)
ALTER TABLE main_clients_database
DROP COLUMN IF EXISTS notification_status,
DROP COLUMN IF EXISTS notification_id;

COMMIT;
```

**Migration Execution Script:** `TOOLS_SCRIPTS_TESTS/tools/execute_notification_migration.py`

```python
#!/usr/bin/env python3
"""
Execute notification columns migration for main_clients_database
"""
import os
import psycopg2
from google.cloud.sql.connector import Connector

def get_db_connection():
    """Create database connection via Cloud SQL Connector"""
    connector = Connector()

    conn = connector.connect(
        os.getenv('CLOUD_SQL_CONNECTION_NAME', 'telepay-459221:us-central1:telepaypsql'),
        "pg8000",
        user=os.getenv('DATABASE_USER_SECRET', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD_SECRET'),
        db=os.getenv('DATABASE_NAME_SECRET', 'telepaydb')
    )

    return conn

def execute_migration():
    """Execute the notification columns migration"""
    try:
        print("🚀 Starting notification columns migration...")

        # Read migration SQL
        script_path = '../scripts/add_notification_columns.sql'
        with open(script_path, 'r') as f:
            migration_sql = f.read()

        # Connect and execute
        conn = get_db_connection()
        cursor = conn.cursor()

        print("📝 Executing migration SQL...")
        cursor.execute(migration_sql)

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ Migration completed successfully!")
        print("✅ Added columns: notification_status (boolean), notification_id (bigint)")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    execute_migration()
```

---

## Backend API Changes

### 1. Update Pydantic Models

**File:** `GCRegisterAPI-10-26/api/models/channel.py`

**Changes Required:**

```python
# ADD to ChannelRegistrationRequest (line ~40)
class ChannelRegistrationRequest(BaseModel):
    # ... existing fields ...

    # 🆕 Notification Configuration
    notification_status: bool = False
    notification_id: Optional[int] = None

    @field_validator('notification_id')
    @classmethod
    def validate_notification_id(cls, v, info):
        """Validate notification_id when notifications enabled"""
        notification_status = info.data.get('notification_status', False)

        if notification_status:
            # Notifications enabled - ID is required
            if v is None:
                raise ValueError('notification_id required when notifications enabled')
            if v <= 0:
                raise ValueError('notification_id must be positive')
            # Telegram user IDs are typically 9-10 digits
            if len(str(v)) < 5 or len(str(v)) > 15:
                raise ValueError('Invalid Telegram ID format')

        return v
```

```python
# ADD to ChannelUpdateRequest (line ~120)
class ChannelUpdateRequest(BaseModel):
    # ... existing fields ...

    # 🆕 Notification Configuration (all optional for partial updates)
    notification_status: Optional[bool] = None
    notification_id: Optional[int] = None

    @field_validator('notification_id')
    @classmethod
    def validate_notification_id(cls, v, info):
        """Validate notification_id when notifications enabled"""
        notification_status = info.data.get('notification_status')

        # Only validate if notification_status is being set to True
        if notification_status is True and v is None:
            raise ValueError('notification_id required when enabling notifications')

        if v is not None:
            if v <= 0:
                raise ValueError('notification_id must be positive')
            if len(str(v)) < 5 or len(str(v)) > 15:
                raise ValueError('Invalid Telegram ID format')

        return v
```

```python
# ADD to ChannelResponse (line ~160)
class ChannelResponse(BaseModel):
    # ... existing fields ...

    # 🆕 Notification Configuration
    notification_status: bool
    notification_id: Optional[int]
```

### 2. Update Channel Service

**File:** `GCRegisterAPI-10-26/api/services/channel_service.py`

**Changes Required:**

```python
# UPDATE register_channel method (line ~66)
@staticmethod
def register_channel(conn, user_id: str, username: str, channel_data) -> bool:
    """Register a new channel"""
    try:
        cursor = conn.cursor()

        # Check if channel already exists
        cursor.execute("""
            SELECT open_channel_id
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (channel_data.open_channel_id,))

        if cursor.fetchone():
            raise ValueError('Channel ID already registered')

        # 🆕 INSERT with notification fields
        cursor.execute("""
            INSERT INTO main_clients_database (
                open_channel_id,
                open_channel_title,
                open_channel_description,
                closed_channel_id,
                closed_channel_title,
                closed_channel_description,
                closed_channel_donation_message,
                sub_1_price,
                sub_1_time,
                sub_2_price,
                sub_2_time,
                sub_3_price,
                sub_3_time,
                client_wallet_address,
                client_payout_currency,
                client_payout_network,
                payout_strategy,
                payout_threshold_usd,
                notification_status,  -- 🆕
                notification_id,       -- 🆕
                client_id,
                created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            channel_data.open_channel_id,
            channel_data.open_channel_title,
            channel_data.open_channel_description,
            channel_data.closed_channel_id,
            channel_data.closed_channel_title,
            channel_data.closed_channel_description,
            channel_data.closed_channel_donation_message,
            channel_data.sub_1_price,
            channel_data.sub_1_time,
            channel_data.sub_2_price,
            channel_data.sub_2_time,
            channel_data.sub_3_price,
            channel_data.sub_3_time,
            channel_data.client_wallet_address,
            channel_data.client_payout_currency,
            channel_data.client_payout_network,
            channel_data.payout_strategy,
            channel_data.payout_threshold_usd,
            channel_data.notification_status,  -- 🆕
            channel_data.notification_id,       -- 🆕
            user_id,
            username
        ))

        cursor.close()
        print(f"✅ Channel {channel_data.open_channel_id} registered with notification settings")
        return True

    except Exception as e:
        print(f"❌ Error registering channel: {e}")
        raise
```

```python
# UPDATE get_user_channels method (line ~135)
@staticmethod
def get_user_channels(conn, user_id: str) -> List[Dict]:
    """Get all channels owned by a user"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            open_channel_id,
            open_channel_title,
            open_channel_description,
            closed_channel_id,
            closed_channel_title,
            closed_channel_description,
            closed_channel_donation_message,
            sub_1_price,
            sub_1_time,
            sub_2_price,
            sub_2_time,
            sub_3_price,
            sub_3_time,
            client_wallet_address,
            client_payout_currency,
            client_payout_network,
            payout_strategy,
            payout_threshold_usd,
            notification_status,  -- 🆕
            notification_id        -- 🆕
        FROM main_clients_database
        WHERE client_id = %s
        ORDER BY open_channel_id DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()

    channels = []
    for row in rows:
        # Calculate tier_count dynamically
        tier_count = 0
        if row[7] is not None:  # sub_1_price
            tier_count += 1
        if row[9] is not None:  # sub_2_price
            tier_count += 1
        if row[11] is not None:  # sub_3_price
            tier_count += 1

        channels.append({
            'open_channel_id': row[0],
            'open_channel_title': row[1],
            'open_channel_description': row[2],
            'closed_channel_id': row[3],
            'closed_channel_title': row[4],
            'closed_channel_description': row[5],
            'closed_channel_donation_message': row[6],
            'tier_count': tier_count,
            'sub_1_price': float(row[7]) if row[7] else None,
            'sub_1_time': row[8],
            'sub_2_price': float(row[9]) if row[9] else None,
            'sub_2_time': row[10],
            'sub_3_price': float(row[11]) if row[11] else None,
            'sub_3_time': row[12],
            'client_wallet_address': row[13],
            'client_payout_currency': row[14],
            'client_payout_network': row[15],
            'payout_strategy': row[16],
            'payout_threshold_usd': float(row[17]) if row[17] else None,
            'notification_status': row[18],  -- 🆕
            'notification_id': row[19],       -- 🆕
            'accumulated_amount': None  # TODO: Calculate from payout_accumulation table
        })

    return channels
```

```python
# UPDATE update_channel method (line ~276)
@staticmethod
def update_channel(conn, channel_id: str, update_data) -> bool:
    """Update a channel"""
    # Build dynamic UPDATE query
    update_fields = []
    values = []

    # 🆕 Include notification fields in dynamic update
    for field, value in update_data.model_dump(exclude_none=True).items():
        update_fields.append(f"{field} = %s")
        values.append(value)

    if not update_fields:
        return True  # No updates needed

    # Add updated_at
    update_fields.append("updated_at = NOW()")
    values.append(channel_id)

    cursor = conn.cursor()
    query = f"""
        UPDATE main_clients_database
        SET {', '.join(update_fields)}
        WHERE open_channel_id = %s
    """
    cursor.execute(query, values)
    cursor.close()

    print(f"✅ Channel {channel_id} updated successfully")
    return True
```

### 3. Update Database Manager (TelePay Bot)

**File:** `TelePay10-26/database.py`

**Add new method:**

```python
# ADD new method around line ~370
def get_notification_settings(self, open_channel_id: str) -> Optional[Tuple[bool, Optional[int]]]:
    """
    Get notification settings for a channel.

    Args:
        open_channel_id: The open channel ID to look up

    Returns:
        Tuple of (notification_status, notification_id) if found, None otherwise

    Example:
        >>> db.get_notification_settings("-1003268562225")
        (True, 123456789)
    """
    try:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT notification_status, notification_id
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (str(open_channel_id),))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            notification_status, notification_id = result
            print(f"✅ [NOTIFICATION] Settings for {open_channel_id}: enabled={notification_status}, id={notification_id}")
            return notification_status, notification_id
        else:
            print(f"⚠️ [NOTIFICATION] No settings found for {open_channel_id}")
            return None

    except Exception as e:
        print(f"❌ [NOTIFICATION] Error fetching settings: {e}")
        return None
```

---

## Frontend Web Interface Changes

### UI Layout Integration

**Placement:** Between "Donation Message Configuration" and "Payment Configuration"

**Visual Hierarchy:**
```
┌─────────────────────────────────────────────────────────┐
│  3. Donation Message Configuration                      │
│  [Custom message textarea]                              │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  4. 🆕 Payment Notification Settings                     │
│                                                          │
│  [ ] Enable payment notifications                       │
│                                                          │
│  When enabled, receive a Telegram notification when a   │
│  customer completes a subscription or donation payment.  │
│                                                          │
│  Telegram User ID: [________________]                   │
│  (Find your ID by messaging @userinfobot)               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  5. Payment Configuration                                │
│  Wallet Address: [________________]                     │
│  ...                                                     │
└─────────────────────────────────────────────────────────┘
```

### File Changes Required

**File:** `GCRegisterWeb-10-26/src/types/channel.ts`

```typescript
// ADD notification fields (around line 40)
export interface ChannelRegistrationData {
  // ... existing fields ...

  // 🆕 Notification Configuration
  notification_status: boolean;
  notification_id: number | null;
}

export interface ChannelUpdateData {
  // ... existing fields ...

  // 🆕 Notification Configuration
  notification_status?: boolean;
  notification_id?: number | null;
}
```

**File:** `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`

```typescript
// ADD state management (around line 50)
const [notificationEnabled, setNotificationEnabled] = useState<boolean>(false);
const [notificationId, setNotificationId] = useState<string>('');

// ADD validation function
const validateNotificationId = (id: string): boolean => {
  if (!id.trim()) return false;
  const numId = parseInt(id, 10);
  if (isNaN(numId) || numId <= 0) return false;
  if (id.length < 5 || id.length > 15) return false;
  return true;
};

// ADD to form submission handler (around line 700)
const handleSubmit = async () => {
  // ... existing validation ...

  // 🆕 Validate notification settings
  if (notificationEnabled && !validateNotificationId(notificationId)) {
    toast.error('Valid Telegram User ID required when notifications enabled');
    return;
  }

  const channelData: ChannelRegistrationData = {
    // ... existing fields ...

    // 🆕 Notification settings
    notification_status: notificationEnabled,
    notification_id: notificationEnabled ? parseInt(notificationId, 10) : null,
  };

  // ... submit to API ...
};
```

**Add UI Component (around line 500):**

```typescript
{/* 🆕 Payment Notification Settings Section */}
<div className="form-section">
  <h3 className="section-title">
    <Bell size={20} />
    Payment Notification Settings
  </h3>

  <div className="notification-toggle">
    <label className="checkbox-label">
      <input
        type="checkbox"
        checked={notificationEnabled}
        onChange={(e) => {
          setNotificationEnabled(e.target.checked);
          if (!e.target.checked) {
            setNotificationId('');
          }
        }}
      />
      <span>Enable payment notifications</span>
    </label>
  </div>

  {notificationEnabled && (
    <>
      <div className="info-box">
        <AlertCircle size={16} />
        <p>
          Receive a Telegram notification when a customer completes a
          subscription or donation payment. Notifications are sent only
          after payment confirmation.
        </p>
      </div>

      <div className="form-group">
        <label htmlFor="notification_id">
          Telegram User ID <span className="required">*</span>
        </label>
        <input
          type="text"
          id="notification_id"
          placeholder="Enter your Telegram user ID"
          value={notificationId}
          onChange={(e) => setNotificationId(e.target.value)}
          className={notificationId && !validateNotificationId(notificationId) ? 'error' : ''}
        />
        <small className="help-text">
          Find your Telegram ID by messaging{' '}
          <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">
            @userinfobot
          </a>
        </small>
        {notificationId && !validateNotificationId(notificationId) && (
          <span className="error-message">
            Invalid Telegram ID format
          </span>
        )}
      </div>
    </>
  )}
</div>
```

**File:** `GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`

Similar changes as RegisterChannelPage.tsx, but with pre-populated values from existing channel data.

---

## Telegram Bot Notification System

### New Service Module

**File:** `TelePay10-26/notification_service.py` (NEW FILE)

**Purpose:** Centralized notification service for sending payment notifications to channel owners

```python
#!/usr/bin/env python
"""
📬 Notification Service for TelePay10-26
Handles sending payment notifications to channel owners
"""
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError, Forbidden, BadRequest
import asyncio
from datetime import datetime


class NotificationService:
    """Service for sending notifications to channel owners"""

    def __init__(self, bot: Bot, db_manager):
        """
        Initialize notification service

        Args:
            bot: Telegram Bot instance
            db_manager: DatabaseManager instance
        """
        self.bot = bot
        self.db_manager = db_manager
        print("📬 [NOTIFICATION] Service initialized")

    async def send_payment_notification(
        self,
        open_channel_id: str,
        payment_type: str,  # 'subscription' or 'donation'
        payment_data: Dict[str, Any]
    ) -> bool:
        """
        Send payment notification to channel owner

        Args:
            open_channel_id: The channel ID to fetch notification settings for
            payment_type: Type of payment ('subscription' or 'donation')
            payment_data: Dictionary containing payment details
                Required keys:
                - user_id: Customer's Telegram user ID
                - amount_crypto: Amount in cryptocurrency
                - amount_usd: Amount in USD
                - crypto_currency: Cryptocurrency symbol
                - timestamp: Payment timestamp (optional)
                For subscriptions:
                - tier: Subscription tier number
                - tier_price: Tier price in USD
                - duration_days: Subscription duration

        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            print(f"")
            print(f"📬 [NOTIFICATION] Processing notification request")
            print(f"   Channel ID: {open_channel_id}")
            print(f"   Payment Type: {payment_type}")

            # Step 1: Fetch notification settings
            settings = self.db_manager.get_notification_settings(open_channel_id)

            if not settings:
                print(f"⚠️ [NOTIFICATION] No settings found for channel {open_channel_id}")
                return False

            notification_status, notification_id = settings

            # Step 2: Check if notifications enabled
            if not notification_status:
                print(f"📭 [NOTIFICATION] Notifications disabled for channel {open_channel_id}")
                return False

            if not notification_id:
                print(f"⚠️ [NOTIFICATION] No notification_id set for channel {open_channel_id}")
                return False

            print(f"✅ [NOTIFICATION] Notifications enabled, sending to {notification_id}")

            # Step 3: Format notification message
            message = self._format_notification_message(
                open_channel_id,
                payment_type,
                payment_data
            )

            # Step 4: Send notification
            await self._send_telegram_message(notification_id, message)

            print(f"✅ [NOTIFICATION] Successfully sent to {notification_id}")
            return True

        except Exception as e:
            print(f"❌ [NOTIFICATION] Error sending notification: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _format_notification_message(
        self,
        open_channel_id: str,
        payment_type: str,
        payment_data: Dict[str, Any]
    ) -> str:
        """
        Format notification message based on payment type

        Args:
            open_channel_id: Channel ID
            payment_type: 'subscription' or 'donation'
            payment_data: Payment details

        Returns:
            Formatted message string
        """
        # Fetch channel details for context
        channel_info = self.db_manager.get_channel_details_by_open_id(open_channel_id)
        channel_title = channel_info['closed_channel_title'] if channel_info else 'Your Channel'

        # Extract common fields
        user_id = payment_data.get('user_id', 'Unknown')
        username = payment_data.get('username', None)
        amount_crypto = payment_data.get('amount_crypto', '0')
        amount_usd = payment_data.get('amount_usd', '0')
        crypto_currency = payment_data.get('crypto_currency', 'CRYPTO')
        timestamp = payment_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))

        # Format user display
        user_display = f"@{username}" if username else f"User ID: {user_id}"

        if payment_type == 'subscription':
            # Subscription payment notification
            tier = payment_data.get('tier', 'Unknown')
            tier_price = payment_data.get('tier_price', '0')
            duration_days = payment_data.get('duration_days', '30')

            message = f"""🎉 <b>New Subscription Payment!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Subscription Details:</b>
├ Tier: {tier}
├ Price: ${tier_price} USD
└ Duration: {duration_days} days

<b>Payment Amount:</b>
├ Crypto: {amount_crypto} {crypto_currency}
└ USD Value: ${amount_usd}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via NowPayments IPN"""

        elif payment_type == 'donation':
            # Donation payment notification
            message = f"""💝 <b>New Donation Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Donor:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Donation Amount:</b>
├ Crypto: {amount_crypto} {crypto_currency}
└ USD Value: ${amount_usd}

<b>Timestamp:</b> {timestamp}

✅ Payment confirmed via NowPayments IPN

Thank you for creating valuable content! 🙏"""

        else:
            # Fallback for unknown payment types
            message = f"""💳 <b>New Payment Received!</b>

<b>Channel:</b> {channel_title}
<b>Channel ID:</b> <code>{open_channel_id}</code>

<b>Customer:</b> {user_display}
<b>User ID:</b> <code>{user_id}</code>

<b>Amount:</b> {amount_crypto} {crypto_currency} (${amount_usd} USD)

<b>Timestamp:</b> {timestamp}"""

        return message

    async def _send_telegram_message(self, chat_id: int, message: str) -> bool:
        """
        Send message via Telegram Bot API

        Args:
            chat_id: Telegram user ID to send to
            message: Message text (supports HTML formatting)

        Returns:
            True if sent successfully, False otherwise

        Raises:
            TelegramError: If sending fails
        """
        try:
            print(f"📤 [NOTIFICATION] Sending message to chat_id {chat_id}")

            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )

            print(f"✅ [NOTIFICATION] Message delivered to {chat_id}")
            return True

        except Forbidden as e:
            print(f"🚫 [NOTIFICATION] Bot blocked by user {chat_id}: {e}")
            # User has blocked the bot - this is expected, don't retry
            return False

        except BadRequest as e:
            print(f"❌ [NOTIFICATION] Invalid request for {chat_id}: {e}")
            # Invalid chat_id or message format
            return False

        except TelegramError as e:
            print(f"❌ [NOTIFICATION] Telegram API error: {e}")
            # Network issues, rate limits, etc.
            return False

        except Exception as e:
            print(f"❌ [NOTIFICATION] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def test_notification(self, chat_id: int, channel_title: str = "Test Channel") -> bool:
        """
        Send a test notification to verify setup

        Args:
            chat_id: Telegram user ID to send test to
            channel_title: Channel name for test message

        Returns:
            True if test successful, False otherwise
        """
        test_message = f"""🧪 <b>Test Notification</b>

This is a test notification for your channel: <b>{channel_title}</b>

If you receive this message, your notification settings are configured correctly!

You will receive notifications when:
• A customer subscribes to a tier
• A customer makes a donation

✅ Notification system is working!"""

        try:
            return await self._send_telegram_message(chat_id, test_message)
        except Exception as e:
            print(f"❌ [NOTIFICATION] Test failed: {e}")
            return False
```

### Integration with TelePay Bot

**File:** `TelePay10-26/app_initializer.py`

**Add notification service initialization:**

```python
# ADD import at top
from notification_service import NotificationService

# ADD to initialization (around line 80)
def initialize_services(telegram_token: str, db_manager):
    """Initialize all bot services"""
    from telegram import Bot

    # Initialize bot instance
    bot = Bot(token=telegram_token)

    # 🆕 Initialize notification service
    notification_service = NotificationService(bot, db_manager)
    print("✅ Notification service initialized")

    return {
        'bot': bot,
        'notification_service': notification_service,
        # ... other services
    }
```

---

## NowPayments IPN Integration

### Trigger Notification from IPN Handler

**File:** `np-webhook-10-26/app.py`

**Changes Required (around line 888):**

```python
# AFTER successful GCWebhook1 enqueue (line ~890)
# ADD notification trigger

print(f"")
print(f"📬 [NOTIFICATION] Checking if notifications should be sent...")

# Determine payment type
payment_type = 'subscription'  # Default to subscription
if 'donation' in order_id.lower() or sub_data[3] == 0:  # Check if donation
    payment_type = 'donation'

# Prepare notification payload
notification_payload = {
    'open_channel_id': open_channel_id,
    'payment_type': payment_type,
    'payment_data': {
        'user_id': user_id,
        'username': None,  # Could be fetched from Telegram API if needed
        'amount_crypto': outcome_amount,
        'amount_usd': outcome_amount_usd,
        'crypto_currency': outcome_currency,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    }
}

# Add payment-type-specific data
if payment_type == 'subscription':
    notification_payload['payment_data'].update({
        'tier': 1,  # Would need to determine from sub_price
        'tier_price': subscription_price,
        'duration_days': subscription_time_days
    })

# Enqueue notification task to TelePay bot
# This would use Cloud Tasks or direct HTTP request to TelePay bot endpoint
try:
    # Option 1: Use Cloud Tasks (recommended for reliability)
    if cloudtasks_client:
        notification_task_name = cloudtasks_client.enqueue_notification(
            queue_name='telepay-notifications-queue',  # New queue needed
            target_url=f"{TELEPAY_BOT_URL}/send-notification",  # New endpoint needed
            notification_data=notification_payload
        )

        if notification_task_name:
            print(f"✅ [NOTIFICATION] Enqueued notification task: {notification_task_name}")
        else:
            print(f"⚠️ [NOTIFICATION] Failed to enqueue notification task")

    # Option 2: Direct HTTP POST (simpler but less reliable)
    # response = requests.post(
    #     f"{TELEPAY_BOT_URL}/send-notification",
    #     json=notification_payload,
    #     timeout=5
    # )
    # if response.status_code == 200:
    #     print(f"✅ [NOTIFICATION] Notification sent successfully")

except Exception as e:
    print(f"❌ [NOTIFICATION] Error triggering notification: {e}")
    print(f"⚠️ [NOTIFICATION] Payment processing continues despite notification failure")
    # Don't fail the entire IPN - notifications are non-critical
```

**Alternative Approach (Simpler):** Add notification endpoint to TelePay bot and call directly from IPN handler.

---

## Notification Service Architecture

### Design Pattern: Cloud Tasks Queue

**Recommended Approach:**

```
np-webhook-10-26 (IPN Handler)
    ↓
Cloud Tasks: telepay-notifications-queue
    ↓
TelePay Bot: /send-notification endpoint
    ↓
NotificationService.send_payment_notification()
    ↓
Telegram Bot API
```

**Benefits:**
- Asynchronous: IPN handler doesn't wait for notification
- Reliable: Automatic retries on failure
- Scalable: Handles burst traffic
- Observable: Cloud Tasks provides monitoring

### Alternative: Direct HTTP Call

**Simpler Approach:**

```
np-webhook-10-26 (IPN Handler)
    ↓ (HTTP POST)
TelePay Bot: /send-notification endpoint
    ↓
NotificationService.send_payment_notification()
    ↓
Telegram Bot API
```

**Benefits:**
- Simpler setup (no new queue needed)
- Faster notification delivery
- Less infrastructure

**Drawbacks:**
- IPN handler waits for notification
- No automatic retries
- Can fail silently

### TelePay Bot Endpoint

**File:** `TelePay10-26/telepay10-26.py` or new `TelePay10-26/notification_api.py`

```python
#!/usr/bin/env python
"""
📬 Notification API Endpoint for TelePay Bot
Receives notification requests and sends via NotificationService
"""
from flask import Flask, request, jsonify
import asyncio

app = Flask(__name__)

# Initialize notification service (from app_initializer)
notification_service = None  # Set during startup

@app.route('/send-notification', methods=['POST'])
def handle_notification_request():
    """
    Handle notification request from np-webhook

    Request body:
    {
        "open_channel_id": "-1003268562225",
        "payment_type": "subscription" | "donation",
        "payment_data": {
            "user_id": 123456789,
            "username": "john_doe",
            "amount_crypto": "0.00034",
            "amount_usd": "9.99",
            "crypto_currency": "ETH",
            "timestamp": "2025-11-11 14:32:15 UTC",
            // For subscriptions:
            "tier": 3,
            "tier_price": "9.99",
            "duration_days": 30
        }
    }
    """
    try:
        data = request.get_json()

        print(f"📬 [NOTIFICATION API] Received request: {data}")

        # Validate required fields
        required_fields = ['open_channel_id', 'payment_type', 'payment_data']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400

        # Send notification asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        success = loop.run_until_complete(
            notification_service.send_payment_notification(
                open_channel_id=data['open_channel_id'],
                payment_type=data['payment_type'],
                payment_data=data['payment_data']
            )
        )

        loop.close()

        if success:
            return jsonify({'status': 'success', 'message': 'Notification sent'}), 200
        else:
            return jsonify({'status': 'failed', 'message': 'Notification not sent'}), 200

    except Exception as e:
        print(f"❌ [NOTIFICATION API] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # This would be integrated into main TelePay bot startup
    app.run(host='0.0.0.0', port=8081)
```

---

## Security & Privacy Considerations

### Data Protection

1. **Telegram ID Storage**
   - Stored as `BIGINT` (no additional PII)
   - No name, email, or other identifying information required
   - Telegram ID alone cannot be used to identify person outside Telegram

2. **Notification Content**
   - Contains payment amount (public transaction data)
   - Contains user Telegram ID (already known to channel owner)
   - No sensitive personal information included

3. **Access Control**
   - Only channel owner can set notification_id (via JWT-authenticated API)
   - notification_id can only be set for channels owned by authenticated user
   - No public endpoint exposes notification_id

### Bot Security

1. **Message Delivery Failures**
   - Bot blocked by user → Logged but not retried
   - Invalid chat_id → Logged and reported
   - Network failures → Retried by Cloud Tasks (if using queue)

2. **Rate Limiting**
   - Telegram Bot API has rate limits (30 msg/sec)
   - For high-volume channels, implement rate limiting in NotificationService
   - Consider batching notifications for same owner

3. **Message Validation**
   - All notification messages formatted securely (no user-generated content injection)
   - HTML parsing disabled for user data fields
   - Use HTML escape for any dynamic content

---

## Error Handling & Recovery

### Failure Scenarios

| Scenario | Detection | Response | Recovery |
|----------|-----------|----------|----------|
| Notification disabled | Check `notification_status` | Skip notification | N/A |
| No notification_id | Check `notification_id IS NULL` | Skip notification | Owner can set ID later |
| Bot blocked by user | Telegram `Forbidden` error | Log and skip | Owner can unblock bot |
| Invalid chat_id | Telegram `BadRequest` error | Log and alert | Owner must fix ID |
| Network failure | Request timeout | Retry (if using queue) | Automatic via Cloud Tasks |
| Bot down | Connection error | Queue task pending | Task executes when bot up |
| Database error | Exception during query | Log error | Manual investigation |

### Logging Strategy

```python
# Enhanced logging in NotificationService

def send_payment_notification(...):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'open_channel_id': open_channel_id,
        'payment_type': payment_type,
        'notification_id': notification_id,
        'status': 'pending'
    }

    try:
        # ... send notification ...
        log_entry['status'] = 'success'
        log_entry['message_id'] = message.message_id
    except Forbidden:
        log_entry['status'] = 'blocked'
        log_entry['error'] = 'User blocked bot'
    except BadRequest as e:
        log_entry['status'] = 'invalid_chat_id'
        log_entry['error'] = str(e)
    except Exception as e:
        log_entry['status'] = 'failed'
        log_entry['error'] = str(e)
    finally:
        # Log to Cloud Logging
        print(f"📊 [NOTIFICATION LOG] {json.dumps(log_entry)}")
```

### Monitoring & Alerts

**Metrics to Track:**
- Notification success rate (per channel)
- Failed notifications by error type
- Average notification delivery time
- Channels with notifications enabled vs. disabled

**Alerting Thresholds:**
- More than 10% notification failures → Investigate bot health
- Specific channel ID failing repeatedly → Contact owner
- Sudden spike in `Forbidden` errors → Check for spam/abuse

---

## Validation & Constraints

### Frontend Validation

```typescript
// Real-time validation in React component
const validateNotificationId = (id: string): { valid: boolean; error?: string } => {
  if (!id.trim()) {
    return { valid: false, error: 'Telegram ID is required when notifications enabled' };
  }

  const numId = parseInt(id, 10);

  if (isNaN(numId)) {
    return { valid: false, error: 'Telegram ID must be a number' };
  }

  if (numId <= 0) {
    return { valid: false, error: 'Telegram ID must be positive' };
  }

  if (id.length < 5) {
    return { valid: false, error: 'Telegram ID too short (min 5 digits)' };
  }

  if (id.length > 15) {
    return { valid: false, error: 'Telegram ID too long (max 15 digits)' };
  }

  return { valid: true };
};
```

### Backend Validation

```python
# Pydantic validator in channel.py
@field_validator('notification_id')
@classmethod
def validate_notification_id(cls, v, info):
    """Comprehensive validation for Telegram user ID"""
    notification_status = info.data.get('notification_status', False)

    # If notifications disabled, ID can be None
    if not notification_status:
        return v

    # If notifications enabled, ID is required
    if v is None:
        raise ValueError('notification_id required when notification_status is True')

    # Must be positive integer
    if not isinstance(v, int) or v <= 0:
        raise ValueError('notification_id must be a positive integer')

    # Telegram user IDs are typically 9-10 digits, but support range
    id_str = str(v)
    if len(id_str) < 5:
        raise ValueError('notification_id too short (minimum 5 digits)')
    if len(id_str) > 15:
        raise ValueError('notification_id too long (maximum 15 digits)')

    return v
```

### Database Constraints

```sql
-- Add CHECK constraint to ensure consistency
ALTER TABLE main_clients_database
ADD CONSTRAINT check_notification_consistency
CHECK (
    (notification_status = false) OR
    (notification_status = true AND notification_id IS NOT NULL)
);

-- Explanation: If notifications enabled, ID must be set
```

---

## Migration Strategy

### Migration Steps

**Step 1: Database Migration**
```bash
# Run migration script
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TOOLS_SCRIPTS_TESTS/tools
python3 execute_notification_migration.py
```

**Step 2: Deploy Backend API**
```bash
# Deploy updated GCRegisterAPI-10-26
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCRegisterAPI-10-26
gcloud run deploy gcregisterapi-10-26 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

**Step 3: Deploy Frontend**
```bash
# Build and deploy updated GCRegisterWeb-10-26
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/GCRegisterWeb-10-26
npm run build
# Deploy to Cloud Storage / CDN
```

**Step 4: Deploy TelePay Bot with NotificationService**
```bash
# Deploy updated TelePay bot (if separate service)
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26
# Deploy via your existing deployment process
```

**Step 5: Deploy Updated np-webhook**
```bash
# Deploy updated np-webhook-10-26 with notification trigger
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/np-webhook-10-26
gcloud run deploy np-webhook-10-26 \
  --source . \
  --region us-central1 \
  --set-env-vars TELEPAY_BOT_URL=<telepay-bot-url>
```

### Rollback Plan

**If issues discovered:**

```bash
# Rollback database changes
cd TOOLS_SCRIPTS_TESTS/scripts
psql -h /cloudsql/telepay-459221:us-central1:telepaypsql \
  -U postgres -d telepaydb \
  -f rollback_notification_columns.sql

# Rollback service deployments
gcloud run services update gcregisterapi-10-26 \
  --image <previous-image-sha> \
  --region us-central1

# Rollback is safe because:
# - notification_status defaults to false (no unexpected behavior)
# - Old code will ignore new columns
# - No breaking changes to existing functionality
```

---

## Testing Plan

### Unit Tests

**File:** `TelePay10-26/tests/test_notification_service.py` (NEW FILE)

```python
import pytest
from notification_service import NotificationService
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
async def test_send_subscription_notification_success():
    """Test successful subscription notification"""
    # Mock bot and db_manager
    mock_bot = Mock()
    mock_bot.send_message = AsyncMock(return_value=Mock(message_id=12345))

    mock_db = Mock()
    mock_db.get_notification_settings.return_value = (True, 123456789)
    mock_db.get_channel_details_by_open_id.return_value = {
        'closed_channel_title': 'Test Channel'
    }

    service = NotificationService(mock_bot, mock_db)

    payment_data = {
        'user_id': 987654321,
        'username': 'testuser',
        'amount_crypto': '0.001',
        'amount_usd': '10.00',
        'crypto_currency': 'ETH',
        'tier': 1,
        'tier_price': '10.00',
        'duration_days': 30
    }

    result = await service.send_payment_notification(
        open_channel_id='-1003268562225',
        payment_type='subscription',
        payment_data=payment_data
    )

    assert result is True
    mock_bot.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_notification_disabled():
    """Test notification skipped when disabled"""
    mock_bot = Mock()
    mock_db = Mock()
    mock_db.get_notification_settings.return_value = (False, 123456789)

    service = NotificationService(mock_bot, mock_db)

    result = await service.send_payment_notification(
        open_channel_id='-1003268562225',
        payment_type='subscription',
        payment_data={}
    )

    assert result is False

# Additional tests:
# - test_bot_blocked_by_user()
# - test_invalid_chat_id()
# - test_donation_notification()
# - test_network_error()
```

### Integration Tests

**Test Scenarios:**

1. **End-to-End Registration Flow**
   - Register channel with notifications enabled
   - Verify database columns populated correctly
   - Trigger test notification via API
   - Verify notification received on Telegram

2. **Payment Flow with Notification**
   - Simulate NowPayments IPN callback
   - Verify payment processed normally
   - Verify notification triggered
   - Verify notification delivered to owner

3. **Update Flow**
   - Edit existing channel
   - Enable notifications
   - Disable notifications
   - Update notification_id

### Manual Testing Checklist

- [ ] Register new channel with notifications **enabled**
  - [ ] Verify Telegram ID validation works
  - [ ] Verify cannot submit empty ID when enabled
  - [ ] Verify successful registration
- [ ] Register new channel with notifications **disabled**
  - [ ] Verify no Telegram ID required
  - [ ] Verify successful registration
- [ ] Edit existing channel
  - [ ] Enable notifications (was disabled)
  - [ ] Disable notifications (was enabled)
  - [ ] Update Telegram ID
- [ ] Simulate subscription payment
  - [ ] Trigger IPN with `status: finished`
  - [ ] Verify notification received by owner
  - [ ] Verify notification content accurate
- [ ] Simulate donation payment
  - [ ] Trigger IPN with `status: finished`
  - [ ] Verify notification received by owner
  - [ ] Verify notification content accurate
- [ ] Test error scenarios
  - [ ] Bot blocked by user (send test notification)
  - [ ] Invalid Telegram ID (should show error in logs)
  - [ ] Network failure (retry mechanism if using queue)

---

## Deployment Checklist

### Pre-Deployment

- [ ] Database migration script created and tested
- [ ] Backend API changes reviewed and tested
- [ ] Frontend UI changes reviewed and tested
- [ ] NotificationService module implemented
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Code review completed
- [ ] Documentation updated

### Deployment Sequence

1. [ ] **Database Migration**
   - [ ] Backup database
   - [ ] Run migration script
   - [ ] Verify columns added successfully
   - [ ] Test rollback script

2. [ ] **Deploy Backend API (GCRegisterAPI-10-26)**
   - [ ] Deploy to Cloud Run
   - [ ] Verify health check passes
   - [ ] Test registration endpoint with Postman
   - [ ] Test update endpoint with Postman

3. [ ] **Deploy Frontend (GCRegisterWeb-10-26)**
   - [ ] Build production bundle
   - [ ] Deploy to hosting (Cloud Storage / CDN)
   - [ ] Clear CDN cache
   - [ ] Test registration form in browser

4. [ ] **Deploy TelePay Bot**
   - [ ] Add NotificationService module
   - [ ] Add notification endpoint
   - [ ] Deploy bot service
   - [ ] Verify health check passes
   - [ ] Test notification endpoint manually

5. [ ] **Deploy np-webhook-10-26**
   - [ ] Add notification trigger code
   - [ ] Deploy to Cloud Run
   - [ ] Verify health check passes
   - [ ] Test IPN callback with mock data

### Post-Deployment Verification

- [ ] Create test channel with notifications enabled
- [ ] Verify notification settings stored correctly
- [ ] Trigger test payment (subscription)
- [ ] Verify notification received
- [ ] Trigger test payment (donation)
- [ ] Verify notification received
- [ ] Monitor Cloud Logging for errors
- [ ] Check notification delivery rate

### Monitoring Setup

- [ ] Create Cloud Monitoring dashboard for notifications
- [ ] Set up alert for notification failure rate > 10%
- [ ] Set up alert for bot API errors
- [ ] Create log-based metrics for notification success/failure

### Documentation

- [ ] Update user documentation (how to find Telegram ID)
- [ ] Update API documentation (new fields)
- [ ] Update architecture diagrams
- [ ] Update PROGRESS.md and DECISIONS.md

---

## Appendix

### Finding Telegram User ID

**Methods for users to find their Telegram ID:**

1. **Use @userinfobot**
   - Open Telegram
   - Search for `@userinfobot`
   - Start chat and send any message
   - Bot replies with your user ID

2. **Use @getmyid_bot**
   - Alternative bot
   - Same process as above

3. **Developer Method (for owners)**
   - Add bot to channel as admin
   - Bot can fetch admin list and display IDs
   - More complex but automated

**Include this in UI help text:**
```
To find your Telegram User ID:
1. Open Telegram and search for @userinfobot
2. Send any message to the bot
3. The bot will reply with your user ID
4. Copy the number and paste it here
```

### Example Notification Messages

**Subscription Payment:**
```
🎉 New Subscription Payment!

Channel: Premium Crypto Signals
Channel ID: -1003268562225

Customer: @johndoe
User ID: 123456789

Subscription Details:
├ Tier: 3
├ Price: $9.99 USD
└ Duration: 30 days

Payment Amount:
├ Crypto: 0.00034 ETH
└ USD Value: $9.99

Timestamp: 2025-11-11 14:32:15 UTC

✅ Payment confirmed via NowPayments IPN
```

**Donation Payment:**
```
💝 New Donation Received!

Channel: Premium Crypto Signals
Channel ID: -1003268562225

Donor: @janedoe
User ID: 987654321

Donation Amount:
├ Crypto: 0.05 ETH
└ USD Value: $150.00

Timestamp: 2025-11-11 15:45:30 UTC

✅ Payment confirmed via NowPayments IPN

Thank you for creating valuable content! 🙏
```

### Performance Considerations

**Notification Volume:**
- Average channel: 5-10 payments/day
- High-traffic channel: 100+ payments/day
- Telegram Bot API limit: 30 messages/second

**Scaling Strategy:**
- For < 1000 notifications/day: Direct HTTP calls work fine
- For 1000+ notifications/day: Use Cloud Tasks queue
- For 10000+ notifications/day: Consider batching + rate limiting

**Cost Estimates:**
- Cloud Tasks: $0.40 per million tasks
- Expected: ~1000 notifications/day = $0.012/month
- Telegram Bot API: Free (within rate limits)

---

## Summary

This architecture provides a **robust, modular, and user-friendly notification system** for channel owners to receive real-time payment notifications. Key highlights:

✅ **Opt-in Design**: Owners explicitly enable notifications
✅ **Simple Configuration**: Manual Telegram ID entry avoids complex detection
✅ **Payment Confirmation**: Notifications only after `status: finished`
✅ **Modular Architecture**: Reusable NotificationService module
✅ **Graceful Failure**: Notifications never block payment processing
✅ **Security Conscious**: Minimal PII storage
✅ **Production Ready**: Comprehensive error handling and monitoring

The system integrates seamlessly with existing payment flow while maintaining code quality and separation of concerns.

