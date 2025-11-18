-- ============================================================================
-- PayGatePrime Complete Database Schema
-- ============================================================================
-- Project: pgp-live
-- Database: telepaydb
-- Instance: pgp-live:us-central1:pgp-telepaypsql
-- Migration: 001 - Initial Schema Creation
-- Created: 2025-11-16
-- Services: All PGP_*_v1 services
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Create Custom ENUM Types
-- ============================================================================
-- Used by: PGP_ORCHESTRATOR_v1, PGP_SPLIT1_v1, PGP_SPLIT2_v1, PGP_HOSTPAY_v1

DO $$ BEGIN
    CREATE TYPE currency_type AS ENUM (
        'BTC', 'ETH', 'USDT', 'USDC', 'LTC', 'XMR', 'BCH', 'BNB',
        'TRX', 'DOGE', 'XRP', 'ADA', 'DOT', 'SOL', 'MATIC', 'AVAX'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE network_type AS ENUM (
        'BTC', 'ETH', 'TRX', 'BSC', 'MATIC', 'AVAX', 'SOL', 'LTC', 'BCH', 'XMR'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE flow_type AS ENUM ('standard', 'fixed-rate');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE type_type AS ENUM ('direct', 'reverse');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- STEP 2: Core Tables - User & Client Management
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: registered_users
-- Purpose: User account management for PayGatePrime web portal
-- Service: PGP_SERVER_v1 (auth, account management)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS registered_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    pending_email VARCHAR(255),
    pending_email_token VARCHAR(500),
    pending_email_token_expires TIMESTAMP,
    pending_email_old_notification_sent BOOLEAN DEFAULT FALSE,
    last_verification_resent_at TIMESTAMP,
    verification_resend_count INTEGER DEFAULT 0,
    last_email_change_requested_at TIMESTAMP,

    CONSTRAINT check_pending_email_different
        CHECK (pending_email IS NULL OR pending_email <> email)
);

-- Indexes for registered_users
CREATE UNIQUE INDEX IF NOT EXISTS unique_username ON registered_users(username);
CREATE UNIQUE INDEX IF NOT EXISTS unique_email ON registered_users(email);
CREATE INDEX IF NOT EXISTS idx_registered_users_username ON registered_users(username);
CREATE INDEX IF NOT EXISTS idx_registered_users_email ON registered_users(email);
CREATE INDEX IF NOT EXISTS idx_registered_users_verification_token ON registered_users(verification_token);
CREATE INDEX IF NOT EXISTS idx_registered_users_reset_token ON registered_users(reset_token);
CREATE INDEX IF NOT EXISTS idx_pending_email ON registered_users(pending_email) WHERE pending_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_verification_token_expires ON registered_users(verification_token_expires) WHERE verification_token_expires IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pending_email_token_expires ON registered_users(pending_email_token_expires) WHERE pending_email_token_expires IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pending_email ON registered_users(pending_email) WHERE pending_email IS NOT NULL;

COMMENT ON TABLE registered_users IS 'PGP_v1: User accounts for web portal authentication and authorization';
COMMENT ON COLUMN registered_users.user_id IS 'UUID primary key for user identification';
COMMENT ON COLUMN registered_users.pending_email IS 'Email change request - must be confirmed before becoming active';

-- ----------------------------------------------------------------------------
-- Table: main_clients_database
-- Purpose: Channel configurations and client settings
-- Service: PGP_SERVER_v1, PGP_ORCHESTRATOR_v1, PGP_BROADCAST_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS main_clients_database (
    id SERIAL PRIMARY KEY,
    open_channel_id VARCHAR(14) NOT NULL UNIQUE,
    open_channel_title VARCHAR(30),
    open_channel_description VARCHAR(140),
    closed_channel_id VARCHAR(14) NOT NULL UNIQUE,
    closed_channel_title VARCHAR(30),
    closed_channel_description VARCHAR(140),
    sub_1_price NUMERIC(10, 2) NOT NULL,
    sub_1_time SMALLINT NOT NULL,
    sub_2_price NUMERIC(10, 2),
    sub_2_time SMALLINT,
    sub_3_price NUMERIC(10, 2),
    sub_3_time SMALLINT,
    client_wallet_address VARCHAR(95) NOT NULL,
    client_payout_currency currency_type NOT NULL,
    client_payout_network network_type,
    payout_strategy VARCHAR(20) DEFAULT 'instant',
    payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
    payout_threshold_updated_at TIMESTAMP,
    client_id UUID NOT NULL,
    created_by VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_channel_donation_message VARCHAR(256) NOT NULL,
    notification_status BOOLEAN NOT NULL DEFAULT FALSE,
    notification_id BIGINT,

    CONSTRAINT fk_client_id FOREIGN KEY (client_id)
        REFERENCES registered_users(user_id) ON DELETE CASCADE,
    CONSTRAINT main_clients_database_sub_1_price_check
        CHECK (sub_1_price > 0 AND (sub_1_price * 100) % 1 = 0),
    CONSTRAINT main_clients_database_sub_1_time_check
        CHECK (sub_1_time > 0),
    CONSTRAINT main_clients_database_sub_2_price_check
        CHECK (sub_2_price IS NULL OR (sub_2_price > 0 AND (sub_2_price * 100) % 1 = 0)),
    CONSTRAINT main_clients_database_sub_2_time_check
        CHECK (sub_2_time IS NULL OR sub_2_time > 0),
    CONSTRAINT main_clients_database_sub_3_price_check
        CHECK (sub_3_price IS NULL OR (sub_3_price > 0 AND (sub_3_price * 100) % 1 = 0)),
    CONSTRAINT main_clients_database_sub_3_time_check
        CHECK (sub_3_time IS NULL OR sub_3_time > 0),
    CONSTRAINT main_clients_database_client_wallet_address_check
        CHECK (octet_length(client_wallet_address) >= 1 AND octet_length(client_wallet_address) <= 95),
    CONSTRAINT main_clients_database_open_channel_id_check
        CHECK (open_channel_id ~ '^-?[0-9]{5,14}$'),
    CONSTRAINT main_clients_database_closed_channel_id_check
        CHECK (closed_channel_id ~ '^-?[0-9]{5,14}$'),
    CONSTRAINT check_donation_message_not_empty
        CHECK (length(TRIM(BOTH FROM closed_channel_donation_message)) > 0),
    CONSTRAINT check_threshold_positive
        CHECK (payout_threshold_usd >= 0),
    CONSTRAINT unique_channel_pair
        UNIQUE (open_channel_id, closed_channel_id)
);

-- Indexes for main_clients_database
CREATE INDEX IF NOT EXISTS idx_payout_strategy ON main_clients_database(payout_strategy);
CREATE INDEX IF NOT EXISTS idx_main_clients_client_id ON main_clients_database(client_id);

COMMENT ON TABLE main_clients_database IS 'PGP_v1: Channel configurations for Telegram private channel subscriptions';
COMMENT ON COLUMN main_clients_database.payout_strategy IS 'instant: immediate payout, threshold: accumulate until threshold reached';
COMMENT ON COLUMN main_clients_database.payout_threshold_usd IS 'Minimum USD amount to accumulate before payout (threshold strategy only)';

-- ============================================================================
-- STEP 3: Subscription & Payment Tables
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: private_channel_users_database
-- Purpose: User subscriptions to private channels
-- Service: PGP_SERVER_v1, PGP_MONITOR_v1, PGP_ORCHESTRATOR_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS private_channel_users_database (
    id SERIAL PRIMARY KEY,
    private_channel_id VARCHAR(14) NOT NULL,
    user_id BIGINT NOT NULL,
    sub_time SMALLINT NOT NULL,
    sub_price VARCHAR(6) NOT NULL,
    timestamp TIME NOT NULL,
    datestamp DATE NOT NULL,
    expire_time TIME NOT NULL,
    expire_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL,
    nowpayments_payment_id VARCHAR(50),
    nowpayments_invoice_id VARCHAR(50),
    nowpayments_order_id VARCHAR(100),
    nowpayments_pay_address VARCHAR(255),
    nowpayments_payment_status VARCHAR(50),
    nowpayments_pay_amount NUMERIC(30, 18),
    nowpayments_pay_currency VARCHAR(20),
    nowpayments_outcome_amount NUMERIC(30, 18),
    nowpayments_created_at TIMESTAMP,
    nowpayments_updated_at TIMESTAMP,
    nowpayments_price_amount NUMERIC(20, 8),
    nowpayments_price_currency VARCHAR(10),
    nowpayments_outcome_currency VARCHAR(10),
    nowpayments_outcome_amount_usd NUMERIC(20, 8),
    payment_status VARCHAR(20) DEFAULT 'pending'
);

-- Indexes for private_channel_users_database
CREATE UNIQUE INDEX IF NOT EXISTS unique_user_channel_pair
    ON private_channel_users_database(user_id, private_channel_id);
CREATE INDEX IF NOT EXISTS idx_nowpayments_payment_id
    ON private_channel_users_database(nowpayments_payment_id);
CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id
    ON private_channel_users_database(nowpayments_order_id);
CREATE INDEX IF NOT EXISTS idx_nowpayments_order_id_status
    ON private_channel_users_database(nowpayments_order_id, payment_status);

COMMENT ON TABLE private_channel_users_database IS 'PGP_v1: Active and expired user subscriptions to private channels';
COMMENT ON COLUMN private_channel_users_database.is_active IS 'Managed by PGP_MONITOR_v1 - expires subscriptions automatically';

-- ----------------------------------------------------------------------------
-- Table: processed_payments
-- Purpose: Tracks payment processing status and Telegram invite delivery
-- Service: PGP_ORCHESTRATOR_v1, PGP_INVITE_v1
-- Note: Legacy column naming (gcwebhook1) preserved for compatibility
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processed_payments (
    payment_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    gcwebhook1_processed BOOLEAN DEFAULT FALSE,
    gcwebhook1_processed_at TIMESTAMP,
    telegram_invite_sent BOOLEAN DEFAULT FALSE,
    telegram_invite_sent_at TIMESTAMP,
    telegram_invite_link TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT payment_id_positive CHECK (payment_id > 0),
    CONSTRAINT user_id_positive CHECK (user_id > 0)
);

-- Indexes for processed_payments
CREATE INDEX IF NOT EXISTS idx_processed_payments_user_channel
    ON processed_payments(user_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_processed_payments_invite_status
    ON processed_payments(telegram_invite_sent);
CREATE INDEX IF NOT EXISTS idx_processed_payments_webhook1_status
    ON processed_payments(gcwebhook1_processed);
CREATE INDEX IF NOT EXISTS idx_processed_payments_created_at
    ON processed_payments(created_at DESC);

COMMENT ON TABLE processed_payments IS 'PGP_v1: Payment processing tracker for idempotency and invite delivery';
COMMENT ON COLUMN processed_payments.gcwebhook1_processed IS 'Legacy naming: processed by PGP_ORCHESTRATOR_v1 (formerly GCWebhook1)';

-- ============================================================================
-- STEP 4: Payout & Accumulation Tables
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: batch_conversions
-- Purpose: Tracks ETH→USDT batch conversions via ChangeNOW
-- Service: PGP_MICROBATCHPROCESSOR_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch_conversions (
    id SERIAL PRIMARY KEY,
    batch_conversion_id UUID NOT NULL UNIQUE,
    total_eth_usd NUMERIC(20, 8) NOT NULL,
    threshold_at_creation NUMERIC(20, 2) NOT NULL,
    cn_api_id VARCHAR(255),
    payin_address VARCHAR(255),
    conversion_status VARCHAR(20) DEFAULT 'pending',
    actual_usdt_received NUMERIC(20, 8),
    conversion_tx_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes for batch_conversions
CREATE INDEX IF NOT EXISTS idx_batch_conversions_status ON batch_conversions(conversion_status);
CREATE INDEX IF NOT EXISTS idx_batch_conversions_cn_api_id ON batch_conversions(cn_api_id);
CREATE INDEX IF NOT EXISTS idx_batch_conversions_created ON batch_conversions(created_at);

COMMENT ON TABLE batch_conversions IS 'PGP_v1: Batch ETH→USDT conversions for threshold payout system';

-- ----------------------------------------------------------------------------
-- Table: payout_accumulation
-- Purpose: Accumulates payments for threshold-based payouts
-- Service: PGP_ACCUMULATOR_v1, PGP_MICROBATCHPROCESSOR_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payout_accumulation (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(14) NOT NULL,
    user_id BIGINT NOT NULL,
    subscription_id INTEGER,
    payment_amount_usd NUMERIC(10, 2) NOT NULL,
    payment_currency VARCHAR(10) NOT NULL,
    payment_timestamp TIMESTAMP NOT NULL,
    accumulated_amount_usdt NUMERIC(18, 8) NOT NULL,
    eth_to_usdt_rate NUMERIC(18, 8),
    conversion_timestamp TIMESTAMP,
    conversion_tx_hash VARCHAR(100),
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,
    is_paid_out BOOLEAN DEFAULT FALSE,
    payout_batch_id VARCHAR(50),
    paid_out_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversion_status VARCHAR(50) DEFAULT 'pending',
    conversion_attempts INTEGER DEFAULT 0,
    last_conversion_attempt TIMESTAMP,
    batch_conversion_id UUID,
    nowpayments_payment_id VARCHAR(50),
    nowpayments_pay_address VARCHAR(255),
    nowpayments_outcome_amount NUMERIC(30, 18),
    nowpayments_network_fee NUMERIC(30, 18),
    payment_fee_usd NUMERIC(20, 8),

    CONSTRAINT fk_batch_conversion
        FOREIGN KEY (batch_conversion_id)
        REFERENCES batch_conversions(batch_conversion_id)
);

-- Indexes for payout_accumulation
CREATE INDEX IF NOT EXISTS idx_client_pending ON payout_accumulation(client_id, is_paid_out);
CREATE INDEX IF NOT EXISTS idx_payout_batch ON payout_accumulation(payout_batch_id);
CREATE INDEX IF NOT EXISTS idx_user ON payout_accumulation(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_timestamp ON payout_accumulation(payment_timestamp);
CREATE INDEX IF NOT EXISTS idx_payout_accumulation_conversion_status ON payout_accumulation(conversion_status);
CREATE INDEX IF NOT EXISTS idx_payout_accumulation_batch_conversion ON payout_accumulation(batch_conversion_id);
CREATE INDEX IF NOT EXISTS idx_payout_nowpayments_payment_id ON payout_accumulation(nowpayments_payment_id);
CREATE INDEX IF NOT EXISTS idx_payout_pay_address ON payout_accumulation(nowpayments_pay_address);

COMMENT ON TABLE payout_accumulation IS 'PGP_v1: Payment accumulation for threshold-based payout strategy';
COMMENT ON COLUMN payout_accumulation.conversion_status IS 'pending: awaiting conversion, completed: converted to USDT, failed: conversion error';
COMMENT ON COLUMN payout_accumulation.eth_to_usdt_rate IS 'NULL until conversion completed by PGP_MICROBATCHPROCESSOR_v1';

-- ----------------------------------------------------------------------------
-- Table: payout_batches
-- Purpose: Tracks batch payout transactions to clients
-- Service: PGP_MICROBATCHPROCESSOR_v1, PGP_HOSTPAY_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payout_batches (
    batch_id VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(14) NOT NULL,
    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,
    total_amount_usdt NUMERIC(18, 8) NOT NULL,
    total_payments_count INTEGER NOT NULL,
    payout_amount_crypto NUMERIC(18, 8),
    usdt_to_crypto_rate NUMERIC(18, 8),
    conversion_fee NUMERIC(18, 8),
    cn_api_id VARCHAR(100),
    cn_payin_address VARCHAR(200),
    tx_hash VARCHAR(100),
    tx_status VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes for payout_batches
CREATE INDEX IF NOT EXISTS idx_client_batch ON payout_batches(client_id);
CREATE INDEX IF NOT EXISTS idx_status_batch ON payout_batches(status);
CREATE INDEX IF NOT EXISTS idx_created_batch ON payout_batches(created_at);

COMMENT ON TABLE payout_batches IS 'PGP_v1: Batch payout transactions to clients when threshold reached';

-- ============================================================================
-- STEP 5: Split Payout Tables
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: split_payout_request
-- Purpose: Stores split payout requests (client portion of payments)
-- Service: PGP_SPLIT1_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS split_payout_request (
    unique_id CHAR(16) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    closed_channel_id VARCHAR(14),
    from_currency currency_type NOT NULL,
    to_currency currency_type NOT NULL,
    from_network network_type NOT NULL,
    to_network network_type NOT NULL,
    from_amount NUMERIC(20, 8),
    to_amount NUMERIC(30, 8),
    client_wallet_address VARCHAR(95) NOT NULL,
    refund_address VARCHAR(95),
    flow flow_type NOT NULL DEFAULT 'standard',
    type type_type NOT NULL DEFAULT 'direct',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actual_eth_amount NUMERIC(20, 18) DEFAULT 0,

    CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0),
    CONSTRAINT split_payout_request_from_amount_check CHECK (from_amount IS NULL OR from_amount >= 0),
    CONSTRAINT split_payout_request_to_amount_check CHECK (to_amount IS NULL OR to_amount >= 0)
);

-- Indexes for split_payout_request
CREATE INDEX IF NOT EXISTS idx_split_payout_request_actual_eth
    ON split_payout_request(actual_eth_amount) WHERE actual_eth_amount > 0;

COMMENT ON TABLE split_payout_request IS 'PGP_v1: Client portion of split payouts (created by PGP_ORCHESTRATOR_v1)';

-- ----------------------------------------------------------------------------
-- Table: split_payout_que
-- Purpose: Queue for split payout processing
-- Service: PGP_SPLIT1_v1, PGP_SPLIT2_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS split_payout_que (
    unique_id CHAR(16) PRIMARY KEY,
    cn_api_id VARCHAR(14) NOT NULL,
    user_id BIGINT NOT NULL,
    closed_channel_id VARCHAR(14) NOT NULL,
    from_currency currency_type NOT NULL,
    to_currency currency_type NOT NULL,
    from_network network_type NOT NULL,
    to_network network_type NOT NULL,
    from_amount NUMERIC(20, 8),
    to_amount NUMERIC(30, 8),
    payin_address VARCHAR(95) NOT NULL,
    payout_address VARCHAR(95) NOT NULL,
    refund_address VARCHAR(95),
    flow flow_type NOT NULL DEFAULT 'standard',
    type type_type NOT NULL DEFAULT 'direct',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actual_eth_amount NUMERIC(20, 18) DEFAULT 0,

    CONSTRAINT actual_eth_positive_que CHECK (actual_eth_amount >= 0),
    CONSTRAINT split_payout_que_from_amount_check CHECK (from_amount IS NULL OR from_amount >= 0),
    CONSTRAINT split_payout_que_to_amount_check CHECK (to_amount IS NULL OR to_amount >= 0)
);

-- Indexes for split_payout_que
CREATE INDEX IF NOT EXISTS idx_split_payout_que_actual_eth
    ON split_payout_que(actual_eth_amount) WHERE actual_eth_amount > 0;

COMMENT ON TABLE split_payout_que IS 'PGP_v1: Split payout queue processed by PGP_SPLIT1_v1 and PGP_SPLIT2_v1';

-- ----------------------------------------------------------------------------
-- Table: split_payout_hostpay
-- Purpose: Tracks host payment portion of split payouts
-- Service: PGP_HOSTPAY_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS split_payout_hostpay (
    unique_id VARCHAR(64) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency currency_type NOT NULL,
    from_network network_type NOT NULL,
    from_amount NUMERIC(20, 8) NOT NULL,
    payin_address VARCHAR(95) NOT NULL,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tx_hash VARCHAR(66),
    tx_status VARCHAR(20) DEFAULT 'pending',
    gas_used INTEGER,
    block_number INTEGER,
    actual_eth_amount NUMERIC(20, 18) DEFAULT 0,

    CONSTRAINT actual_eth_positive CHECK (actual_eth_amount >= 0)
);

-- Indexes for split_payout_hostpay
CREATE INDEX IF NOT EXISTS idx_split_payout_hostpay_actual_eth
    ON split_payout_hostpay(actual_eth_amount) WHERE actual_eth_amount > 0;

COMMENT ON TABLE split_payout_hostpay IS 'PGP_v1: Host payment tracking for split payout system';

-- ============================================================================
-- STEP 6: Feature Tables (Broadcast, Donations, Conversations)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: broadcast_manager
-- Purpose: Manages scheduled broadcast messages to channels
-- Service: PGP_BROADCAST_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS broadcast_manager (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    open_channel_id TEXT NOT NULL UNIQUE,
    closed_channel_id TEXT NOT NULL UNIQUE,
    last_sent_time TIMESTAMPTZ,
    next_send_time TIMESTAMPTZ DEFAULT NOW(),
    broadcast_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    last_manual_trigger_time TIMESTAMPTZ,
    manual_trigger_count INTEGER DEFAULT 0,
    total_broadcasts INTEGER DEFAULT 0,
    successful_broadcasts INTEGER DEFAULT 0,
    failed_broadcasts INTEGER DEFAULT 0,
    last_error_message TEXT,
    last_error_time TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_open_message_id BIGINT,
    last_closed_message_id BIGINT,
    last_open_message_sent_at TIMESTAMP,
    last_closed_message_sent_at TIMESTAMP,

    CONSTRAINT fk_broadcast_client_id
        FOREIGN KEY (client_id)
        REFERENCES registered_users(user_id) ON DELETE CASCADE,
    CONSTRAINT valid_broadcast_status
        CHECK (broadcast_status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    CONSTRAINT unique_channel_pair_broadcast
        UNIQUE (open_channel_id, closed_channel_id)
);

-- Indexes for broadcast_manager
CREATE INDEX IF NOT EXISTS idx_broadcast_next_send
    ON broadcast_manager(next_send_time) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_broadcast_client ON broadcast_manager(client_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_status
    ON broadcast_manager(broadcast_status) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_broadcast_open_channel ON broadcast_manager(open_channel_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_manager_open_message
    ON broadcast_manager(last_open_message_id) WHERE last_open_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_broadcast_manager_closed_message
    ON broadcast_manager(last_closed_message_id) WHERE last_closed_message_id IS NOT NULL;

COMMENT ON TABLE broadcast_manager IS 'PGP_v1: Scheduled broadcast message manager for PGP_BROADCAST_v1';
COMMENT ON COLUMN broadcast_manager.last_open_message_id IS 'Telegram message ID for deletion/editing in open channel';

-- ----------------------------------------------------------------------------
-- Table: donation_keypad_state
-- Purpose: Stores donation keypad input state for users
-- Service: PGP_DONATIONS_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donation_keypad_state (
    user_id BIGINT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    current_amount TEXT NOT NULL DEFAULT '',
    decimal_entered BOOLEAN NOT NULL DEFAULT FALSE,
    state_type VARCHAR(20) NOT NULL DEFAULT 'keypad_input',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_state_type
        CHECK (state_type IN ('keypad_input', 'text_input', 'awaiting_confirmation')),
    CONSTRAINT valid_amount_format
        CHECK (current_amount ~ '^[0-9]*\.?[0-9]*$' AND length(current_amount) <= 10)
);

-- Indexes for donation_keypad_state
CREATE INDEX IF NOT EXISTS idx_donation_state_updated_at ON donation_keypad_state(updated_at);
CREATE INDEX IF NOT EXISTS idx_donation_state_channel ON donation_keypad_state(channel_id);

COMMENT ON TABLE donation_keypad_state IS 'PGP_v1: Donation keypad UI state management for PGP_DONATIONS_v1';

-- ----------------------------------------------------------------------------
-- Table: user_conversation_state
-- Purpose: Stores bot conversation state (generic state management)
-- Service: PGP_BOT_v1 (TelePay)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_conversation_state (
    user_id BIGINT NOT NULL,
    conversation_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (user_id, conversation_type)
);

-- Indexes for user_conversation_state
CREATE INDEX IF NOT EXISTS idx_conversation_state_updated ON user_conversation_state(updated_at);

COMMENT ON TABLE user_conversation_state IS 'PGP_v1: Generic conversation state manager for PGP_BOT_v1';

-- ============================================================================
-- STEP 7: Utility Tables
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: currency_to_network
-- Purpose: Maps supported currencies to their networks
-- Service: Referenced by all payment services
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS currency_to_network (
    currency VARCHAR(6) NOT NULL,
    network VARCHAR(8) NOT NULL,
    currency_name VARCHAR(17),
    network_name VARCHAR(17)
);

COMMENT ON TABLE currency_to_network IS 'PGP_v1: Currency/network mapping reference table (87 entries)';

-- ----------------------------------------------------------------------------
-- Table: failed_transactions
-- Purpose: Tracks failed ChangeNOW transactions for recovery
-- Service: PGP_ORCHESTRATOR_v1
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failed_transactions (
    id SERIAL PRIMARY KEY,
    unique_id VARCHAR(16) NOT NULL,
    cn_api_id VARCHAR(16) NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    from_network VARCHAR(10) NOT NULL,
    from_amount NUMERIC(18, 8) NOT NULL,
    payin_address VARCHAR(100) NOT NULL,
    context VARCHAR(20) NOT NULL DEFAULT 'instant',
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    last_error_details JSONB,
    attempt_count INTEGER NOT NULL DEFAULT 3,
    last_attempt_timestamp TIMESTAMP NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'failed_pending_review',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_attempt TIMESTAMP,
    recovery_tx_hash VARCHAR(100),
    recovered_at TIMESTAMP,
    recovered_by VARCHAR(50),
    admin_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for failed_transactions
CREATE INDEX IF NOT EXISTS idx_failed_transactions_unique_id ON failed_transactions(unique_id);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_cn_api_id ON failed_transactions(cn_api_id);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_status ON failed_transactions(status);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_error_code ON failed_transactions(error_code);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_created_at ON failed_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_failed_transactions_retry
    ON failed_transactions(status, error_code, created_at)
    WHERE status IN ('failed_retryable', 'retry_scheduled');

COMMENT ON TABLE failed_transactions IS 'PGP_v1: Failed ChangeNOW transaction tracking for manual recovery';

-- ============================================================================
-- STEP 8: Insert Legacy User
-- ============================================================================
-- Create legacy user for existing channels in database migration

INSERT INTO registered_users (
    user_id,
    username,
    email,
    password_hash,
    is_active,
    email_verified
) VALUES (
    '00000000-0000-0000-0000-000000000000',
    'legacy_system',
    'legacy@paygateprime.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5qlcHxqCJzqZ2',
    FALSE,
    FALSE
) ON CONFLICT (user_id) DO NOTHING;

COMMENT ON TABLE registered_users IS 'PGP_v1: Contains legacy_system user (00000000...) for pre-existing channels';

-- ============================================================================
-- COMPLETION
-- ============================================================================

COMMIT;

-- Print success message
DO $$
BEGIN
    RAISE NOTICE '✅ PayGatePrime Schema Creation Complete';
    RAISE NOTICE '📊 Created 15 tables with indexes and constraints';
    RAISE NOTICE '🔐 Created 4 custom ENUM types';
    RAISE NOTICE '👤 Created legacy_system user for existing data';
    RAISE NOTICE ' ';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Populate currency_to_network with 87 currency/network mappings';
    RAISE NOTICE '2. Migrate existing data from telepay-459221 if needed';
    RAISE NOTICE '3. Deploy PGP_*_v1 services to pgp-live project';
END $$;
