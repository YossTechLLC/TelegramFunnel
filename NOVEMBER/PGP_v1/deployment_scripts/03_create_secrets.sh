#!/bin/bash
# Create All Secrets in Google Cloud Secret Manager for PayGatePrime v1
# DO NOT EXECUTE - Review and customize before running
# IMPORTANT: Replace all placeholder values with actual secret values

set -e

PROJECT_ID="pgp-live"

echo "🔐 Creating Secrets in Google Cloud Secret Manager"
echo "===================================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo ""
echo "⚠️  WARNING: This script contains placeholder values!"
echo "⚠️  You MUST replace all <placeholder> values with actual secrets!"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# SECTION 1: AUTHENTICATION & SECURITY (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 1: Authentication & Security (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "🔑 Creating JWT_SECRET_KEY..."
echo "   ⚠️  Generate a new 256-bit key (DO NOT reuse from telepay-459221!)"
# Example generation: openssl rand -base64 32
# JWT_SECRET_KEY="<REPLACE_WITH_NEW_256_BIT_KEY>"
# echo -n "$JWT_SECRET_KEY" | gcloud secrets create JWT_SECRET_KEY --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with:"
echo "      echo -n 'YOUR_KEY' | gcloud secrets create JWT_SECRET_KEY --data-file=- --project=$PROJECT_ID"

echo ""
echo "🔑 Creating SIGNUP_SECRET_KEY..."
echo "   ⚠️  Generate a new 256-bit key for email verification & password reset"
# Example generation: openssl rand -base64 32
# SIGNUP_SECRET_KEY="<REPLACE_WITH_NEW_256_BIT_KEY>"
# echo -n "$SIGNUP_SECRET_KEY" | gcloud secrets create SIGNUP_SECRET_KEY --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with:"
echo "      echo -n 'YOUR_KEY' | gcloud secrets create SIGNUP_SECRET_KEY --data-file=- --project=$PROJECT_ID"

# =============================================================================
# SECTION 2: DATABASE CONFIGURATION (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 2: Database Configuration (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "📊 Creating CLOUD_SQL_CONNECTION_NAME..."
CLOUD_SQL_CONNECTION_NAME="pgp-live:us-central1:pgp-live-psql"
echo -n "$CLOUD_SQL_CONNECTION_NAME" | gcloud secrets create CLOUD_SQL_CONNECTION_NAME --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $CLOUD_SQL_CONNECTION_NAME"

echo ""
echo "📊 Creating DATABASE_NAME_SECRET..."
DATABASE_NAME="pgpdb"
echo -n "$DATABASE_NAME" | gcloud secrets create DATABASE_NAME_SECRET --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $DATABASE_NAME"

echo ""
echo "📊 Creating DATABASE_USER_SECRET..."
DATABASE_USER="postgres"
echo -n "$DATABASE_USER" | gcloud secrets create DATABASE_USER_SECRET --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $DATABASE_USER"

echo ""
echo "📊 Creating DATABASE_PASSWORD_SECRET..."
echo "   ⚠️  Use the SAME password you set for the postgres user in Cloud SQL!"
# DATABASE_PASSWORD="<REPLACE_WITH_POSTGRES_PASSWORD>"
# echo -n "$DATABASE_PASSWORD" | gcloud secrets create DATABASE_PASSWORD_SECRET --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with:"
echo "      echo -n 'YOUR_POSTGRES_PASSWORD' | gcloud secrets create DATABASE_PASSWORD_SECRET --data-file=- --project=$PROJECT_ID"

# =============================================================================
# SECTION 3: FRONTEND & CORS CONFIGURATION (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 3: Frontend & CORS (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "🌐 Creating BASE_URL..."
BASE_URL="https://www.paygateprime.com"
echo -n "$BASE_URL" | gcloud secrets create BASE_URL --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $BASE_URL"

echo ""
echo "🌐 Creating CORS_ORIGIN..."
CORS_ORIGIN="https://www.paygateprime.com"
echo -n "$CORS_ORIGIN" | gcloud secrets create CORS_ORIGIN --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $CORS_ORIGIN"

# =============================================================================
# SECTION 4: EMAIL SERVICE - SENDGRID (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 4: Email Service - SendGrid (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "📧 Creating SENDGRID_API_KEY..."
# SENDGRID_API_KEY="<REPLACE_WITH_SENDGRID_API_KEY>"
# echo -n "$SENDGRID_API_KEY" | gcloud secrets create SENDGRID_API_KEY --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with:"
echo "      echo -n 'SG.xxxxxxxxxx' | gcloud secrets create SENDGRID_API_KEY --data-file=- --project=$PROJECT_ID"

echo ""
echo "📧 Creating FROM_EMAIL..."
FROM_EMAIL="noreply@paygateprime.com"
echo -n "$FROM_EMAIL" | gcloud secrets create FROM_EMAIL --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $FROM_EMAIL"

echo ""
echo "📧 Creating FROM_NAME..."
FROM_NAME="PayGatePrime"
echo -n "$FROM_NAME" | gcloud secrets create FROM_NAME --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $FROM_NAME"

# =============================================================================
# SECTION 5: PAYMENT GATEWAY - CHANGENOW (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 5: Payment Gateway - ChangeNOW (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "💰 Creating CHANGENOW_API_KEY..."
# CHANGENOW_API_KEY="<REPLACE_WITH_CHANGENOW_API_KEY>"
# echo -n "$CHANGENOW_API_KEY" | gcloud secrets create CHANGENOW_API_KEY --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your ChangeNOW API key"

echo ""
echo "💰 Creating CHANGENOW_USDT_WALLET..."
# CHANGENOW_USDT_WALLET="<REPLACE_WITH_USDT_WALLET_ADDRESS>"
# echo -n "$CHANGENOW_USDT_WALLET" | gcloud secrets create CHANGENOW_USDT_WALLET --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your USDT wallet address"

# =============================================================================
# SECTION 6: PAYMENT GATEWAY - NOWPAYMENTS (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 6: Payment Gateway - NowPayments (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "💳 Creating NOWPAYMENTS_API_KEY..."
# NOWPAYMENTS_API_KEY="<REPLACE_WITH_NOWPAYMENTS_API_KEY>"
# echo -n "$NOWPAYMENTS_API_KEY" | gcloud secrets create NOWPAYMENTS_API_KEY --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your NowPayments API key"

echo ""
echo "💳 Creating NOWPAYMENTS_IPN_SECRET..."
# NOWPAYMENTS_IPN_SECRET="<REPLACE_WITH_NOWPAYMENTS_IPN_SECRET>"
# echo -n "$NOWPAYMENTS_IPN_SECRET" | gcloud secrets create NOWPAYMENTS_IPN_SECRET --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your NowPayments IPN secret"

echo ""
echo "💳 Creating NOWPAYMENTS_USDT_WALLET..."
# NOWPAYMENTS_USDT_WALLET="<REPLACE_WITH_USDT_WALLET_ADDRESS>"
# echo -n "$NOWPAYMENTS_USDT_WALLET" | gcloud secrets create NOWPAYMENTS_USDT_WALLET --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your USDT wallet address"

# =============================================================================
# SECTION 7: PLATFORM WALLET CONFIGURATION (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 7: Platform Wallet Configuration (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "👛 Creating PLATFORM_USDT_WALLET_ADDRESS..."
# PLATFORM_USDT_WALLET_ADDRESS="<REPLACE_WITH_PLATFORM_USDT_WALLET>"
# echo -n "$PLATFORM_USDT_WALLET_ADDRESS" | gcloud secrets create PLATFORM_USDT_WALLET_ADDRESS --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with platform's main USDT wallet"

echo ""
echo "💵 Creating TP_PERCENTAGE (Fee percentage)..."
TP_PERCENTAGE="0.05"  # 5%
echo -n "$TP_PERCENTAGE" | gcloud secrets create TP_PERCENTAGE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $TP_PERCENTAGE (5%)"

echo ""
echo "💵 Creating TP_FLAT_FEE (Flat fee in USDT)..."
TP_FLAT_FEE="1.00"  # $1.00 USDT
echo -n "$TP_FLAT_FEE" | gcloud secrets create TP_FLAT_FEE --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $TP_FLAT_FEE USDT"

# =============================================================================
# SECTION 8: BLOCKCHAIN INTEGRATION - ALCHEMY (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 8: Blockchain - Alchemy (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "⛓️  Creating ALCHEMY_API_KEY_POLYGON..."
# ALCHEMY_API_KEY_POLYGON="<REPLACE_WITH_ALCHEMY_API_KEY>"
# echo -n "$ALCHEMY_API_KEY_POLYGON" | gcloud secrets create ALCHEMY_API_KEY_POLYGON --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your Alchemy API key for Polygon"

# =============================================================================
# SECTION 9: TELEGRAM BOT INTEGRATION (High 🟡)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🟡 SECTION 9: Telegram Bot (HIGH)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "🤖 Creating TELEGRAM_BOT_TOKEN..."
# TELEGRAM_BOT_TOKEN="<REPLACE_WITH_TELEGRAM_BOT_TOKEN>"
# echo -n "$TELEGRAM_BOT_TOKEN" | gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=- --project=$PROJECT_ID
echo "   ⏭️  SKIPPED - Set manually with your Telegram bot token"

# =============================================================================
# SECTION 10: CLOUD TASKS PROJECT CONFIGURATION (Critical 🔴)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 SECTION 10: Cloud Tasks Configuration (CRITICAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "📦 Creating CLOUD_TASKS_PROJECT_ID..."
CLOUD_TASKS_PROJECT_ID="pgp-live"
echo -n "$CLOUD_TASKS_PROJECT_ID" | gcloud secrets create CLOUD_TASKS_PROJECT_ID --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $CLOUD_TASKS_PROJECT_ID"

echo ""
echo "📍 Creating CLOUD_TASKS_LOCATION..."
CLOUD_TASKS_LOCATION="us-central1"
echo -n "$CLOUD_TASKS_LOCATION" | gcloud secrets create CLOUD_TASKS_LOCATION --data-file=- --project=$PROJECT_ID
echo "   ✅ Created: $CLOUD_TASKS_LOCATION"

# =============================================================================
# NOTE: Queue names and service URLs will be created in the next script
# after Cloud Run services are deployed
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SECTION COMPLETE: Core Secrets Created"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Created Secrets Summary:"
echo "   ✅ CLOUD_SQL_CONNECTION_NAME"
echo "   ✅ DATABASE_NAME_SECRET"
echo "   ✅ DATABASE_USER_SECRET"
echo "   ✅ BASE_URL"
echo "   ✅ CORS_ORIGIN"
echo "   ✅ FROM_EMAIL"
echo "   ✅ FROM_NAME"
echo "   ✅ TP_PERCENTAGE"
echo "   ✅ TP_FLAT_FEE"
echo "   ✅ CLOUD_TASKS_PROJECT_ID"
echo "   ✅ CLOUD_TASKS_LOCATION"
echo ""
echo "⏭️  MANUAL ACTION REQUIRED - Create these secrets manually:"
echo "   ⚠️  JWT_SECRET_KEY (generate new 256-bit key)"
echo "   ⚠️  SIGNUP_SECRET_KEY (generate new 256-bit key)"
echo "   ⚠️  DATABASE_PASSWORD_SECRET (postgres password from Cloud SQL)"
echo "   ⚠️  SENDGRID_API_KEY"
echo "   ⚠️  CHANGENOW_API_KEY"
echo "   ⚠️  CHANGENOW_USDT_WALLET"
echo "   ⚠️  NOWPAYMENTS_API_KEY"
echo "   ⚠️  NOWPAYMENTS_IPN_SECRET"
echo "   ⚠️  NOWPAYMENTS_USDT_WALLET"
echo "   ⚠️  PLATFORM_USDT_WALLET_ADDRESS"
echo "   ⚠️  ALCHEMY_API_KEY_POLYGON"
echo "   ⚠️  TELEGRAM_BOT_TOKEN"
echo ""
echo "⏭️  Next: Run 04_create_queue_secrets.sh AFTER deploying Cloud Run services"
echo ""
