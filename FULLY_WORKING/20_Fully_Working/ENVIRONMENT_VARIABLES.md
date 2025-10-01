# Environment Variables for 20_Fully_Working Application

This document lists all environment variables required by the TelePay20 and GCWebhook20 applications.

## Overview

The application uses Google Cloud Secret Manager for storing sensitive configuration data. Most environment variables contain paths to secrets rather than the actual values.

---

## TelePay20 Folder Environment Variables

### **Telegram Bot Configuration**
- **`TELEGRAM_BOT_SECRET_NAME`** - Path to Telegram bot token in Google Cloud Secret Manager
  - Used in: `config_manager.py`, `database.py`
  - Purpose: Authentication token for the Telegram bot

- **`TELEGRAM_BOT_USERNAME`** - Path to Telegram bot username in Google Cloud Secret Manager
  - Used in: `config_manager.py`
  - Purpose: Bot username for display and reference

### **Database Configuration**
- **`DATABASE_HOST_SECRET`** - Path to database host address in Google Cloud Secret Manager
  - Used in: `database.py`
  - Purpose: PostgreSQL database host connection string

- **`DATABASE_NAME_SECRET`** - Path to database name in Google Cloud Secret Manager
  - Used in: `database.py`
  - Purpose: Name of the PostgreSQL database to connect to

- **`DATABASE_USER_SECRET`** - Path to database username in Google Cloud Secret Manager
  - Used in: `database.py`
  - Purpose: Database authentication username

- **`DATABASE_PASSWORD_SECRET`** - Path to database password in Google Cloud Secret Manager
  - Used in: `database.py`
  - Purpose: Database authentication password

### **Payment Processing Configuration**
- **`NOWPAYMENT_WEBHOOK_KEY`** - Path to NowPayments webhook key in Google Cloud Secret Manager
  - Used in: `config_manager.py`
  - Purpose: Webhook verification key for NowPayments callbacks

- **`PAYMENT_PROVIDER_SECRET_NAME`** - Path to payment provider token in Google Cloud Secret Manager
  - Used in: `start_np_gateway.py`
  - Purpose: Authentication token for payment provider API

### **Security Configuration**
- **`SUCCESS_URL_SIGNING_KEY`** - Path to URL signing key in Google Cloud Secret Manager
  - Used in: `secure_webhook.py`
  - Purpose: HMAC key for signing and verifying payment success URLs

- **`WEBHOOK_BASE_URL`** - Base URL for the webhook service
  - Used in: `secure_webhook.py`
  - Purpose: Public URL where the GCWebhook20 service is hosted

---

## GCWebhook20 Folder Environment Variables

### **Telegram Bot Configuration**
- **`TELEGRAM_BOT_SECRET_NAME`** - Path to Telegram bot token in Google Cloud Secret Manager
  - Used in: `tph2.py`
  - Purpose: Authentication token for sending Telegram invite links

### **Database Configuration**
- **`DATABASE_NAME_SECRET`** - Path to database name in Google Cloud Secret Manager
  - Used in: `tph2.py`
  - Purpose: Name of the PostgreSQL database for user subscription tracking

- **`DATABASE_USER_SECRET`** - Path to database username in Google Cloud Secret Manager
  - Used in: `tph2.py`
  - Purpose: Database authentication username

- **`DATABASE_PASSWORD_SECRET`** - Path to database password in Google Cloud Secret Manager
  - Used in: `tph2.py`
  - Purpose: Database authentication password

- **`CLOUD_SQL_CONNECTION_NAME`** - Cloud SQL connection name (direct value, not Secret Manager path)
  - Used in: `tph2.py`
  - Purpose: Google Cloud SQL instance connection string (format: project:region:instance)

### **Security Configuration**
- **`SUCCESS_URL_SIGNING_KEY`** - Path to URL signing key in Google Cloud Secret Manager
  - Used in: `tph2.py`
  - Purpose: HMAC key for verifying payment success URL tokens

---

## Environment Variable Categories

### **Secret Manager Paths**
These variables contain paths to secrets stored in Google Cloud Secret Manager:
- `TELEGRAM_BOT_SECRET_NAME`
- `TELEGRAM_BOT_USERNAME`
- `DATABASE_HOST_SECRET`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`
- `NOWPAYMENT_WEBHOOK_KEY`
- `PAYMENT_PROVIDER_SECRET_NAME`
- `SUCCESS_URL_SIGNING_KEY`

### **Direct Values**
These variables contain actual configuration values:
- `WEBHOOK_BASE_URL`
- `CLOUD_SQL_CONNECTION_NAME`

---

## Required vs Optional Variables

### **Required for TelePay20:**
- `TELEGRAM_BOT_SECRET_NAME` ✓ Required
- `DATABASE_HOST_SECRET` ✓ Required
- `DATABASE_NAME_SECRET` ✓ Required
- `DATABASE_USER_SECRET` ✓ Required
- `DATABASE_PASSWORD_SECRET` ✓ Required
- `PAYMENT_PROVIDER_SECRET_NAME` ✓ Required
- `SUCCESS_URL_SIGNING_KEY` ✓ Required
- `WEBHOOK_BASE_URL` ✓ Required

### **Optional for TelePay20:**
- `TELEGRAM_BOT_USERNAME` (has fallback)
- `NOWPAYMENT_WEBHOOK_KEY` (has fallback)

### **Required for GCWebhook20:**
- `TELEGRAM_BOT_SECRET_NAME` ✓ Required
- `DATABASE_NAME_SECRET` ✓ Required
- `DATABASE_USER_SECRET` ✓ Required
- `SUCCESS_URL_SIGNING_KEY` ✓ Required

### **Optional for GCWebhook20:**
- `DATABASE_PASSWORD_SECRET` (can be None)
- `CLOUD_SQL_CONNECTION_NAME` (can be None)

---

## Security Notes

1. **Never store actual secrets in environment variables** - use Google Cloud Secret Manager paths instead
2. **All database credentials are fetched from Secret Manager** for enhanced security
3. **HMAC signing keys are crucial** for payment verification security
4. **Webhook URLs must be publicly accessible** for payment provider callbacks

## Deployment Checklist

Before deploying, ensure all required environment variables are set:

### For TelePay20:
```bash
echo $TELEGRAM_BOT_SECRET_NAME
echo $DATABASE_HOST_SECRET
echo $DATABASE_NAME_SECRET
echo $DATABASE_USER_SECRET
echo $DATABASE_PASSWORD_SECRET
echo $PAYMENT_PROVIDER_SECRET_NAME
echo $SUCCESS_URL_SIGNING_KEY
echo $WEBHOOK_BASE_URL
```

### For GCWebhook20:
```bash
echo $TELEGRAM_BOT_SECRET_NAME
echo $DATABASE_NAME_SECRET
echo $DATABASE_USER_SECRET
echo $SUCCESS_URL_SIGNING_KEY
```