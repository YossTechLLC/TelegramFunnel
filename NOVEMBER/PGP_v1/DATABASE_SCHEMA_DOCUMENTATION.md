# PayGatePrime Database Schema Documentation
**Project:** pgp-live
**Database:** telepaydb
**Instance:** pgp-live:us-central1:pgp-telepaypsql
**Generated:** 2025-11-16

---

## Overview

The PayGatePrime database consists of **15 tables** supporting:
- Client channel management
- User subscriptions
- Payment processing
- Payout accumulation & batching
- Broadcast management
- Donation handling
- Failover tracking

**Total Tables:** 15
**Total Sequences:** 5
**Total Records:** ~600 rows across all tables

---

## Table of Contents

1. [Core Tables](#core-tables)
   - [main_clients_database](#1-main_clients_database) - Channel configurations
   - [private_channel_users_database](#2-private_channel_users_database) - User subscriptions
   - [registered_users](#3-registered_users) - User accounts

2. [Payment Tables](#payment-tables)
   - [processed_payments](#4-processed_payments) - Payment tracking
   - [payout_accumulation](#5-payout_accumulation) - Payment accumulation
   - [payout_batches](#6-payout_batches) - Batch payouts

3. [Conversion Tables](#conversion-tables)
   - [batch_conversions](#7-batch_conversions) - Batch ETH→USDT conversions
   - [split_payout_request](#8-split_payout_request) - Split payout requests
   - [split_payout_que](#9-split_payout_que) - Split payout queue
   - [split_payout_hostpay](#10-split_payout_hostpay) - Host payment tracking

4. [Feature Tables](#feature-tables)
   - [broadcast_manager](#11-broadcast_manager) - Broadcast scheduling
   - [donation_keypad_state](#12-donation_keypad_state) - Donation UI state
   - [user_conversation_state](#13-user_conversation_state) - Bot conversation state

5. [Utility Tables](#utility-tables)
   - [currency_to_network](#14-currency_to_network) - Currency/network mapping
   - [failed_transactions](#15-failed_transactions) - Failed transaction tracking

---

## Core Tables

### 1. main_clients_database
**Purpose:** Stores channel configurations and client settings
**Service:** Used by PGP_SERVER_v1, PGP_ORCHESTRATOR_v1, PGP_BROADCAST_v1
**Row Count:** 20

#### Schema
```sql
Column                           Type                 Nullable  Default
--------------------------------------------------------------------------------
id                               SERIAL               NOT NULL  AUTO
open_channel_id                  VARCHAR(14)          NOT NULL  -
open_channel_title               VARCHAR(30)          NULL      -
open_channel_description         VARCHAR(140)         NULL      -
closed_channel_id                VARCHAR(14)          NOT NULL  -
closed_channel_title             VARCHAR(30)          NULL      -
closed_channel_description       VARCHAR(140)         NULL      -
sub_1_price                      NUMERIC(10, 2)       NOT NULL  -
sub_1_time                       SMALLINT             NOT NULL  -
sub_2_price                      NUMERIC(10, 2)       NULL      -
sub_2_time                       SMALLINT             NULL      -
sub_3_price                      NUMERIC(10, 2)       NULL      -
sub_3_time                       SMALLINT             NULL      -
client_wallet_address            VARCHAR(95)          NOT NULL  -
client_payout_currency           ENUM                 NOT NULL  -
client_payout_network            ENUM                 NULL      -
payout_strategy                  VARCHAR(20)          NULL      'instant'
payout_threshold_usd             NUMERIC(10, 2)       NULL      0
payout_threshold_updated_at      TIMESTAMP            NULL      -
client_id                        UUID                 NOT NULL  -
created_by                       VARCHAR(50)          NULL      -
updated_at                       TIMESTAMP            NULL      CURRENT_TIMESTAMP
closed_channel_donation_message  VARCHAR(256)         NOT NULL  -
notification_status              BOOLEAN              NOT NULL  false
notification_id                  BIGINT               NULL      -
```

#### Constraints
- **Primary Key:** id
- **Foreign Keys:**
  - client_id → registered_users.user_id (ON DELETE CASCADE)
- **Unique:** open_channel_id, closed_channel_id, (open_channel_id, closed_channel_id)
- **Check:**
  - sub_1_price > 0, divisible by 0.01
  - sub_1_time > 0
  - client_wallet_address length 1-95 bytes
  - open_channel_id, closed_channel_id match regex `^-?[0-9]{5,14}$`
  - closed_channel_donation_message not empty
  - payout_threshold_usd >= 0

#### Indexes
- idx_payout_strategy ON (payout_strategy)
- idx_main_clients_client_id ON (client_id)

---

### 2. private_channel_users_database
**Purpose:** Stores user subscriptions to private channels
**Service:** Used by PGP_SERVER_v1, PGP_MONITOR_v1, PGP_ORCHESTRATOR_v1
**Row Count:** 18

#### Schema
```sql
Column                         Type                 Nullable  Default
--------------------------------------------------------------------------------
id                             SERIAL               NOT NULL  AUTO
private_channel_id             VARCHAR(14)          NOT NULL  -
user_id                        BIGINT               NOT NULL  -
sub_time                       SMALLINT             NOT NULL  -
sub_price                      VARCHAR(6)           NOT NULL  -
timestamp                      TIME                 NOT NULL  -
datestamp                      DATE                 NOT NULL  -
expire_time                    TIME                 NOT NULL  -
expire_date                    DATE                 NOT NULL  -
is_active                      BOOLEAN              NOT NULL  -
nowpayments_payment_id         VARCHAR(50)          NULL      -
nowpayments_invoice_id         VARCHAR(50)          NULL      -
nowpayments_order_id           VARCHAR(100)         NULL      -
nowpayments_pay_address        VARCHAR(255)         NULL      -
nowpayments_payment_status     VARCHAR(50)          NULL      -
nowpayments_pay_amount         NUMERIC(30, 18)      NULL      -
nowpayments_pay_currency       VARCHAR(20)          NULL      -
nowpayments_outcome_amount     NUMERIC(30, 18)      NULL      -
nowpayments_created_at         TIMESTAMP            NULL      -
nowpayments_updated_at         TIMESTAMP            NULL      -
nowpayments_price_amount       NUMERIC(20, 8)       NULL      -
nowpayments_price_currency     VARCHAR(10)          NULL      -
nowpayments_outcome_currency   VARCHAR(10)          NULL      -
nowpayments_outcome_amount_usd NUMERIC(20, 8)       NULL      -
payment_status                 VARCHAR(20)          NULL      'pending'
```

#### Constraints
- **Primary Key:** id
- **Unique:** (user_id, private_channel_id), user_id, private_channel_id

#### Indexes
- unique_user_channel_pair ON (user_id, private_channel_id)
- idx_nowpayments_payment_id ON (nowpayments_payment_id)
- idx_nowpayments_order_id ON (nowpayments_order_id)
- idx_nowpayments_order_id_status ON (nowpayments_order_id, payment_status)

---

### 3. registered_users
**Purpose:** User account management for PayGatePrime web portal
**Service:** Used by PGP_SERVER_v1 (auth, account management)
**Row Count:** 21

#### Schema
```sql
Column                            Type            Nullable  Default
--------------------------------------------------------------------------------
user_id                           UUID            NOT NULL  gen_random_uuid()
username                          VARCHAR(50)     NOT NULL  -
email                             VARCHAR(255)    NOT NULL  -
password_hash                     VARCHAR(255)    NOT NULL  -
is_active                         BOOLEAN         NULL      true
email_verified                    BOOLEAN         NULL      false
verification_token                VARCHAR(255)    NULL      -
verification_token_expires        TIMESTAMP       NULL      -
reset_token                       VARCHAR(255)    NULL      -
reset_token_expires               TIMESTAMP       NULL      -
created_at                        TIMESTAMP       NULL      CURRENT_TIMESTAMP
updated_at                        TIMESTAMP       NULL      CURRENT_TIMESTAMP
last_login                        TIMESTAMP       NULL      -
pending_email                     VARCHAR(255)    NULL      -
pending_email_token               VARCHAR(500)    NULL      -
pending_email_token_expires       TIMESTAMP       NULL      -
pending_email_old_notification_sent BOOLEAN       NULL      false
last_verification_resent_at       TIMESTAMP       NULL      -
verification_resend_count         INTEGER         NULL      0
last_email_change_requested_at    TIMESTAMP       NULL      -
```

#### Constraints
- **Primary Key:** user_id
- **Unique:** username, email (multiple indexes for enforcement)
- **Check:** pending_email must be different from email if not null

#### Indexes
- idx_registered_users_username, idx_registered_users_email
- idx_registered_users_verification_token, idx_registered_users_reset_token
- idx_pending_email (WHERE pending_email IS NOT NULL)
- idx_verification_token_expires (WHERE verification_token_expires IS NOT NULL)
- idx_pending_email_token_expires (WHERE pending_email_token_expires IS NOT NULL)
- idx_unique_pending_email UNIQUE (WHERE pending_email IS NOT NULL)

---

## Payment Tables

### 4. processed_payments
**Purpose:** Tracks payment processing status and Telegram invite delivery
**Service:** Used by PGP_ORCHESTRATOR_v1, PGP_INVITE_v1
**Row Count:** 42

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
payment_id                BIGINT          NOT NULL  -
user_id                   BIGINT          NOT NULL  -
channel_id                BIGINT          NOT NULL  -
gcwebhook1_processed      BOOLEAN         NULL      false
gcwebhook1_processed_at   TIMESTAMP       NULL      -
telegram_invite_sent      BOOLEAN         NULL      false
telegram_invite_sent_at   TIMESTAMP       NULL      -
telegram_invite_link      TEXT            NULL      -
created_at                TIMESTAMP       NULL      CURRENT_TIMESTAMP
updated_at                TIMESTAMP       NULL      CURRENT_TIMESTAMP
```

#### Constraints
- **Primary Key:** payment_id
- **Check:**
  - payment_id > 0
  - user_id > 0

#### Indexes
- idx_processed_payments_user_channel ON (user_id, channel_id)
- idx_processed_payments_invite_status ON (telegram_invite_sent)
- idx_processed_payments_webhook1_status ON (gcwebhook1_processed)
- idx_processed_payments_created_at ON (created_at DESC)

**Note:** Column name `gcwebhook1_processed` is legacy naming from old GC architecture

---

### 5. payout_accumulation
**Purpose:** Accumulates payments for threshold-based payouts
**Service:** Used by PGP_ACCUMULATOR_v1, PGP_MICROBATCHPROCESSOR_v1
**Row Count:** 101

#### Schema
```sql
Column                      Type             Nullable  Default
--------------------------------------------------------------------------------
id                          SERIAL           NOT NULL  AUTO
client_id                   VARCHAR(14)      NOT NULL  -
user_id                     BIGINT           NOT NULL  -
subscription_id             INTEGER          NULL      -
payment_amount_usd          NUMERIC(10, 2)   NOT NULL  -
payment_currency            VARCHAR(10)      NOT NULL  -
payment_timestamp           TIMESTAMP        NOT NULL  -
accumulated_amount_usdt     NUMERIC(18, 8)   NOT NULL  -
eth_to_usdt_rate            NUMERIC(18, 8)   NULL      -
conversion_timestamp        TIMESTAMP        NULL      -
conversion_tx_hash          VARCHAR(100)     NULL      -
client_wallet_address       VARCHAR(200)     NOT NULL  -
client_payout_currency      VARCHAR(10)      NOT NULL  -
client_payout_network       VARCHAR(50)      NOT NULL  -
is_paid_out                 BOOLEAN          NULL      false
payout_batch_id             VARCHAR(50)      NULL      -
paid_out_at                 TIMESTAMP        NULL      -
created_at                  TIMESTAMP        NULL      CURRENT_TIMESTAMP
updated_at                  TIMESTAMP        NULL      CURRENT_TIMESTAMP
conversion_status           VARCHAR(50)      NULL      'pending'
conversion_attempts         INTEGER          NULL      0
last_conversion_attempt     TIMESTAMP        NULL      -
batch_conversion_id         UUID             NULL      -
nowpayments_payment_id      VARCHAR(50)      NULL      -
nowpayments_pay_address     VARCHAR(255)     NULL      -
nowpayments_outcome_amount  NUMERIC(30, 18)  NULL      -
nowpayments_network_fee     NUMERIC(30, 18)  NULL      -
payment_fee_usd             NUMERIC(20, 8)   NULL      -
```

#### Constraints
- **Primary Key:** id
- **Foreign Keys:**
  - batch_conversion_id → batch_conversions.batch_conversion_id

#### Indexes
- idx_client_pending ON (client_id, is_paid_out)
- idx_payout_batch ON (payout_batch_id)
- idx_user ON (user_id)
- idx_payment_timestamp ON (payment_timestamp)
- idx_payout_accumulation_conversion_status ON (conversion_status)
- idx_payout_accumulation_batch_conversion ON (batch_conversion_id)
- idx_payout_nowpayments_payment_id ON (nowpayments_payment_id)
- idx_payout_pay_address ON (nowpayments_pay_address)

---

### 6. payout_batches
**Purpose:** Tracks batch payout transactions to clients
**Service:** Used by PGP_MICROBATCHPROCESSOR_v1, PGP_HOSTPAY_v1
**Row Count:** 33

#### Schema
```sql
Column                    Type             Nullable  Default
--------------------------------------------------------------------------------
batch_id                  VARCHAR(50)      NOT NULL  -
client_id                 VARCHAR(14)      NOT NULL  -
client_wallet_address     VARCHAR(200)     NOT NULL  -
client_payout_currency    VARCHAR(10)      NOT NULL  -
client_payout_network     VARCHAR(50)      NOT NULL  -
total_amount_usdt         NUMERIC(18, 8)   NOT NULL  -
total_payments_count      INTEGER          NOT NULL  -
payout_amount_crypto      NUMERIC(18, 8)   NULL      -
usdt_to_crypto_rate       NUMERIC(18, 8)   NULL      -
conversion_fee            NUMERIC(18, 8)   NULL      -
cn_api_id                 VARCHAR(100)     NULL      -
cn_payin_address          VARCHAR(200)     NULL      -
tx_hash                   VARCHAR(100)     NULL      -
tx_status                 VARCHAR(20)      NULL      -
status                    VARCHAR(20)      NULL      'pending'
created_at                TIMESTAMP        NULL      CURRENT_TIMESTAMP
processing_started_at     TIMESTAMP        NULL      -
completed_at              TIMESTAMP        NULL      -
```

#### Constraints
- **Primary Key:** batch_id

#### Indexes
- idx_client_batch ON (client_id)
- idx_status_batch ON (status)
- idx_created_batch ON (created_at)

---

## Conversion Tables

### 7. batch_conversions
**Purpose:** Tracks ETH→USDT batch conversions via ChangeNOW
**Service:** Used by PGP_MICROBATCHPROCESSOR_v1
**Row Count:** 29

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
id                        SERIAL          NOT NULL  AUTO
batch_conversion_id       UUID            NOT NULL  -
total_eth_usd             NUMERIC(20, 8)  NOT NULL  -
threshold_at_creation     NUMERIC(20, 2)  NOT NULL  -
cn_api_id                 VARCHAR(255)    NULL      -
payin_address             VARCHAR(255)    NULL      -
conversion_status         VARCHAR(20)     NULL      'pending'
actual_usdt_received      NUMERIC(20, 8)  NULL      -
conversion_tx_hash        VARCHAR(255)    NULL      -
created_at                TIMESTAMP       NULL      now()
processing_started_at     TIMESTAMP       NULL      -
completed_at              TIMESTAMP       NULL      -
```

#### Constraints
- **Primary Key:** id
- **Unique:** batch_conversion_id

#### Indexes
- idx_batch_conversions_status ON (conversion_status)
- idx_batch_conversions_cn_api_id ON (cn_api_id)
- idx_batch_conversions_created ON (created_at)

---

### 8. split_payout_request
**Purpose:** Stores split payout requests (client portion of payments)
**Service:** Used by PGP_SPLIT1_v1
**Row Count:** 95

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
unique_id                 CHAR(16)        NOT NULL  -
user_id                   BIGINT          NOT NULL  -
closed_channel_id         VARCHAR(14)     NULL      -
from_currency             ENUM            NOT NULL  -
to_currency               ENUM            NOT NULL  -
from_network              ENUM            NOT NULL  -
to_network                ENUM            NOT NULL  -
from_amount               NUMERIC(20, 8)  NULL      -
to_amount                 NUMERIC(30, 8)  NULL      -
client_wallet_address     VARCHAR(95)     NOT NULL  -
refund_address            VARCHAR(95)     NULL      -
flow                      ENUM            NOT NULL  'standard'
type                      ENUM            NOT NULL  'direct'
created_at                TIMESTAMP       NOT NULL  now()
updated_at                TIMESTAMP       NOT NULL  now()
actual_eth_amount         NUMERIC(20, 18) NULL      0
```

#### Constraints
- **Primary Key:** unique_id
- **Check:**
  - actual_eth_amount >= 0
  - from_amount >= 0
  - to_amount >= 0

#### Indexes
- idx_split_payout_request_actual_eth ON (actual_eth_amount) WHERE actual_eth_amount > 0

---

### 9. split_payout_que
**Purpose:** Queue for split payout processing
**Service:** Used by PGP_SPLIT1_v1, PGP_SPLIT2_v1
**Row Count:** 71

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
unique_id                 CHAR(16)        NOT NULL  -
cn_api_id                 VARCHAR(14)     NOT NULL  -
user_id                   BIGINT          NOT NULL  -
closed_channel_id         VARCHAR(14)     NOT NULL  -
from_currency             ENUM            NOT NULL  -
to_currency               ENUM            NOT NULL  -
from_network              ENUM            NOT NULL  -
to_network                ENUM            NOT NULL  -
from_amount               NUMERIC(20, 8)  NULL      -
to_amount                 NUMERIC(30, 8)  NULL      -
payin_address             VARCHAR(95)     NOT NULL  -
payout_address            VARCHAR(95)     NOT NULL  -
refund_address            VARCHAR(95)     NULL      -
flow                      ENUM            NOT NULL  'standard'
type                      ENUM            NOT NULL  'direct'
created_at                TIMESTAMP       NOT NULL  now()
updated_at                TIMESTAMP       NOT NULL  now()
actual_eth_amount         NUMERIC(20, 18) NULL      0
```

#### Constraints
- **Primary Key:** unique_id
- **Check:**
  - actual_eth_amount >= 0
  - from_amount >= 0
  - to_amount >= 0

#### Indexes
- idx_split_payout_que_actual_eth ON (actual_eth_amount) WHERE actual_eth_amount > 0

---

### 10. split_payout_hostpay
**Purpose:** Tracks host payment portion of split payouts
**Service:** Used by PGP_HOSTPAY_v1
**Row Count:** 51

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
unique_id                 VARCHAR(64)     NOT NULL  -
cn_api_id                 VARCHAR(16)     NOT NULL  -
from_currency             ENUM            NOT NULL  -
from_network              ENUM            NOT NULL  -
from_amount               NUMERIC(20, 8)  NOT NULL  -
payin_address             VARCHAR(95)     NOT NULL  -
is_complete               BOOLEAN         NOT NULL  false
created_at                TIMESTAMP       NOT NULL  now()
updated_at                TIMESTAMP       NOT NULL  now()
tx_hash                   VARCHAR(66)     NULL      -
tx_status                 VARCHAR(20)     NULL      'pending'
gas_used                  INTEGER         NULL      -
block_number              INTEGER         NULL      -
actual_eth_amount         NUMERIC(20, 18) NULL      0
```

#### Constraints
- **Check:** actual_eth_amount >= 0

#### Indexes
- idx_split_payout_hostpay_actual_eth ON (actual_eth_amount) WHERE actual_eth_amount > 0

---

## Feature Tables

### 11. broadcast_manager
**Purpose:** Manages scheduled broadcast messages to channels
**Service:** Used by PGP_BROADCAST_v1
**Row Count:** 20

#### Schema
```sql
Column                         Type            Nullable  Default
--------------------------------------------------------------------------------
id                             UUID            NOT NULL  gen_random_uuid()
client_id                      UUID            NOT NULL  -
open_channel_id                TEXT            NOT NULL  -
closed_channel_id              TEXT            NOT NULL  -
last_sent_time                 TIMESTAMPTZ     NULL      -
next_send_time                 TIMESTAMPTZ     NULL      now()
broadcast_status               VARCHAR(20)     NOT NULL  'pending'
last_manual_trigger_time       TIMESTAMPTZ     NULL      -
manual_trigger_count           INTEGER         NULL      0
total_broadcasts               INTEGER         NULL      0
successful_broadcasts          INTEGER         NULL      0
failed_broadcasts              INTEGER         NULL      0
last_error_message             TEXT            NULL      -
last_error_time                TIMESTAMPTZ     NULL      -
consecutive_failures           INTEGER         NULL      0
is_active                      BOOLEAN         NOT NULL  true
created_at                     TIMESTAMPTZ     NOT NULL  now()
updated_at                     TIMESTAMPTZ     NOT NULL  now()
last_open_message_id           BIGINT          NULL      -
last_closed_message_id         BIGINT          NULL      -
last_open_message_sent_at      TIMESTAMP       NULL      -
last_closed_message_sent_at    TIMESTAMP       NULL      -
```

#### Constraints
- **Primary Key:** id
- **Foreign Keys:**
  - client_id → registered_users.user_id (ON DELETE CASCADE)
- **Unique:** open_channel_id, closed_channel_id, (open_channel_id, closed_channel_id)
- **Check:** broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')

#### Indexes
- unique_channel_pair ON (open_channel_id, closed_channel_id)
- idx_broadcast_next_send ON (next_send_time) WHERE is_active = true
- idx_broadcast_client ON (client_id)
- idx_broadcast_status ON (broadcast_status) WHERE is_active = true
- idx_broadcast_open_channel ON (open_channel_id)
- idx_broadcast_manager_open_message ON (last_open_message_id) WHERE last_open_message_id IS NOT NULL
- idx_broadcast_manager_closed_message ON (last_closed_message_id) WHERE last_closed_message_id IS NOT NULL

---

### 12. donation_keypad_state
**Purpose:** Stores donation keypad input state for users
**Service:** Used by PGP_DONATIONS_v1
**Row Count:** 1

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
user_id                   BIGINT          NOT NULL  -
channel_id                TEXT            NOT NULL  -
current_amount            TEXT            NOT NULL  ''
decimal_entered           BOOLEAN         NOT NULL  false
state_type                VARCHAR(20)     NOT NULL  'keypad_input'
created_at                TIMESTAMPTZ     NOT NULL  now()
updated_at                TIMESTAMPTZ     NOT NULL  now()
```

#### Constraints
- **Primary Key:** user_id
- **Check:**
  - state_type IN ('keypad_input', 'text_input', 'awaiting_confirmation')
  - current_amount matches regex `^[0-9]*\.?[0-9]*$` AND length <= 10

#### Indexes
- idx_donation_state_updated_at ON (updated_at)
- idx_donation_state_channel ON (channel_id)

---

### 13. user_conversation_state
**Purpose:** Stores bot conversation state (generic state management)
**Service:** Used by PGP_BOT_v1 (TelePay)
**Row Count:** 1

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
user_id                   BIGINT          NOT NULL  -
conversation_type         VARCHAR(50)     NOT NULL  -
state_data                JSONB           NOT NULL  -
updated_at                TIMESTAMP       NULL      now()
```

#### Constraints
- **Primary Key:** (user_id, conversation_type)

#### Indexes
- idx_conversation_state_updated ON (updated_at)

---

## Utility Tables

### 14. currency_to_network
**Purpose:** Maps supported currencies to their networks
**Service:** Referenced by all payment services
**Row Count:** 87

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
currency                  VARCHAR(6)      NOT NULL  -
network                   VARCHAR(8)      NOT NULL  -
currency_name             VARCHAR(17)     NULL      -
network_name              VARCHAR(17)     NULL      -
```

**No primary key** - This is a reference lookup table

**Sample Data:**
- BTC → BTC (Bitcoin → Bitcoin)
- ETH → ETH (Ethereum → Ethereum)
- USDT → TRX (Tether → Tron)
- USDT → ETH (Tether → Ethereum)
- etc.

---

### 15. failed_transactions
**Purpose:** Tracks failed ChangeNOW transactions for recovery
**Service:** Used by PGP_ORCHESTRATOR_v1 for error handling
**Row Count:** 21

#### Schema
```sql
Column                    Type            Nullable  Default
--------------------------------------------------------------------------------
id                        SERIAL          NOT NULL  AUTO
unique_id                 VARCHAR(16)     NOT NULL  -
cn_api_id                 VARCHAR(16)     NOT NULL  -
from_currency             VARCHAR(10)     NOT NULL  -
from_network              VARCHAR(10)     NOT NULL  -
from_amount               NUMERIC(18, 8)  NOT NULL  -
payin_address             VARCHAR(100)    NOT NULL  -
context                   VARCHAR(20)     NOT NULL  'instant'
error_code                VARCHAR(50)     NOT NULL  -
error_message             TEXT            NULL      -
last_error_details        JSONB           NULL      -
attempt_count             INTEGER         NOT NULL  3
last_attempt_timestamp    TIMESTAMP       NOT NULL  -
status                    VARCHAR(30)     NOT NULL  'failed_pending_review'
retry_count               INTEGER         NOT NULL  0
last_retry_attempt        TIMESTAMP       NULL      -
recovery_tx_hash          VARCHAR(100)    NULL      -
recovered_at              TIMESTAMP       NULL      -
recovered_by              VARCHAR(50)     NULL      -
admin_notes               TEXT            NULL      -
created_at                TIMESTAMP       NOT NULL  now()
updated_at                TIMESTAMP       NOT NULL  now()
```

#### Constraints
- **Primary Key:** id

#### Indexes
- idx_failed_transactions_unique_id ON (unique_id)
- idx_failed_transactions_cn_api_id ON (cn_api_id)
- idx_failed_transactions_status ON (status)
- idx_failed_transactions_error_code ON (error_code)
- idx_failed_transactions_created_at ON (created_at DESC)
- idx_failed_transactions_retry ON (status, error_code, created_at) WHERE status IN ('failed_retryable', 'retry_scheduled')

---

## Database Sequences

The following sequences are used for auto-incrementing primary keys:

1. **batch_conversions_id_seq** → batch_conversions.id
2. **failed_transactions_id_seq** → failed_transactions.id
3. **main_clients_database_id_seq** → main_clients_database.id
4. **payout_accumulation_id_seq** → payout_accumulation.id
5. **private_channel_users_database_id_seq** → private_channel_users_database.id

---

## Service Usage Map

### PGP_SERVER_v1 (GCRegisterAPI)
- main_clients_database (CRUD)
- registered_users (auth, account management)
- private_channel_users_database (subscription queries)

### PGP_ORCHESTRATOR_v1 (GCWebhook1)
- private_channel_users_database (create subscriptions)
- main_clients_database (read channel configs)
- processed_payments (track processing)
- failed_transactions (error handling)
- split_payout_request (create split requests)

### PGP_SPLIT1_v1 (GCSplit1)
- split_payout_request (read requests)
- split_payout_que (write queue entries)
- split_payout_hostpay (write host payments)

### PGP_ACCUMULATOR_v1 (GCAccumulator)
- payout_accumulation (insert pending payments)
- main_clients_database (read payout strategies)

### PGP_MICROBATCHPROCESSOR_v1 (GCMicroBatchProcessor)
- payout_accumulation (read pending, update conversion status)
- batch_conversions (create/track batch conversions)
- payout_batches (create payout batches)

### PGP_BROADCAST_v1 (GCBroadcastScheduler)
- broadcast_manager (CRUD broadcast schedules)
- main_clients_database (read channel info)

### PGP_DONATIONS_v1 (GCDonationHandler)
- donation_keypad_state (manage donation input state)
- main_clients_database (read donation messages)

### PGP_MONITOR_v1 (GCSubscriptionMonitor)
- private_channel_users_database (check expirations, update is_active)

### PGP_INVITE_v1 (GCWebhook2/TelegramInvite)
- processed_payments (check if invite sent)
- private_channel_users_database (verify subscriptions)

---

## Migration Notes

### Legacy Naming
Some columns retain legacy "GC" naming for backwards compatibility:
- `processed_payments.gcwebhook1_processed` → References old GCWebhook1 service (now PGP_ORCHESTRATOR_v1)

### ENUMs vs VARCHAR
Some tables use PostgreSQL custom types (ENUMs):
- `from_currency`, `to_currency` (currency types)
- `from_network`, `to_network` (network types)
- `flow`, `type` (payout flow types)

These will need to be created before table creation.

### UUID Usage
- **registered_users.user_id**: UUID for user IDs
- **main_clients_database.client_id**: UUID FK to registered_users
- **broadcast_manager.id**: UUID primary key
- **batch_conversions.batch_conversion_id**: UUID for batch tracking

---

## Index Strategy

### Performance Indexes
- **Composite indexes** for common queries: (client_id, is_paid_out), (user_id, private_channel_id)
- **Partial indexes** for filtered queries: WHERE is_active = true, WHERE conversion_status = 'pending'
- **Timestamp indexes** for time-based queries: created_at DESC

### Foreign Key Indexes
All foreign key columns have indexes for join performance:
- main_clients_database.client_id
- broadcast_manager.client_id
- payout_accumulation.batch_conversion_id

---

## Data Volumes (Current)

| Table | Rows | Growth Rate |
|-------|------|-------------|
| currency_to_network | 87 | Static |
| split_payout_request | 95 | High (per payment) |
| payout_accumulation | 101 | High (per payment) |
| split_payout_que | 71 | High (per payment) |
| split_payout_hostpay | 51 | Medium (per split) |
| processed_payments | 42 | High (per payment) |
| payout_batches | 33 | Medium (threshold-based) |
| batch_conversions | 29 | Medium (threshold-based) |
| failed_transactions | 21 | Low (errors only) |
| registered_users | 21 | Low (per client signup) |
| main_clients_database | 20 | Low (per channel) |
| broadcast_manager | 20 | Low (per channel) |
| private_channel_users_database | 18 | High (per subscription) |
| donation_keypad_state | 1 | Medium (active users) |
| user_conversation_state | 1 | Medium (active users) |

**Total:** ~600 rows

---

## Next Steps for pgp-live Deployment

1. ✅ Schema documented
2. ⏳ Create SQL deployment scripts with PGP_v1 comments
3. ⏳ Create ENUM types (currency_type, network_type, flow_type, type_type)
4. ⏳ Create tables in dependency order
5. ⏳ Create indexes
6. ⏳ Verify constraints
7. ⏳ Test with sample data

---

**End of Documentation**
