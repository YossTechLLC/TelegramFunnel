# Environment Variables Reference - TelePay10-26

**Last Updated:** 2025-11-13 Session 150
**Project:** telepay-459221

---

## Required Environment Variables

All Secret Manager paths should use the format:
```
projects/PROJECT_NUMBER/secrets/SECRET_NAME/versions/VERSION
```

Where:
- `PROJECT_NUMBER` = `291176869049` (your GCP project number)
- `SECRET_NAME` = Name of the secret in Secret Manager
- `VERSION` = `latest` (or specific version number)

---

## Database Configuration

### Cloud SQL Connection

```bash
# Cloud SQL instance connection string
CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
```

### Database Credentials (Secret Manager)

```bash
# Database host (Cloud SQL connection details)
DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest

# Database name
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest

# Database user
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest

# Database password
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest
```

---

## Connection Pool Configuration (Optional)

These have defaults and are optional:

```bash
# Connection pool size (default: 5)
DB_POOL_SIZE=5

# Maximum overflow connections (default: 10)
DB_MAX_OVERFLOW=10

# Connection pool timeout in seconds (default: 30)
DB_POOL_TIMEOUT=30

# Connection recycle time in seconds (default: 1800)
DB_POOL_RECYCLE=1800
```

---

## Telegram Bot Configuration

### Bot Credentials (Secret Manager)

```bash
# Telegram bot token
# Value stored in Secret Manager: Bot token from @BotFather (e.g., "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest

# Telegram bot username
# Value stored in Secret Manager: Bot username (e.g., "@PayGatePrime_bot")
TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest
```

**⚠️ IMPORTANT:** Both are Secret Manager paths, not the actual values!

---

## Payment Provider Configuration

### NowPayments Integration (Secret Manager)

```bash
# NowPayments API key
# Value stored in Secret Manager: API key from NowPayments dashboard
PAYMENT_PROVIDER_SECRET_NAME=projects/291176869049/secrets/NOWPAYMENTS_API_KEY/versions/latest

# NowPayments IPN callback URL
# Value stored in Secret Manager: Your IPN endpoint URL (e.g., "https://your-domain.com/api/nowpayments/ipn")
NOWPAYMENTS_IPN_CALLBACK_URL_SECRET_NAME=projects/291176869049/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest
```

**Note:** The environment variable names are long for backward compatibility with existing code.

---

## Security Configuration (Optional)

### Flask Security Layers

```bash
# Webhook signing secret (Secret Manager path)
# If not set: Auto-generates temporary secret (development mode)
WEBHOOK_SIGNING_SECRET_NAME=projects/291176869049/secrets/WEBHOOK_SIGNING_SECRET/versions/latest

# IP whitelist (comma-separated)
# Default: 127.0.0.1,10.0.0.0/8
ALLOWED_IPS=127.0.0.1,10.0.0.0/8,35.190.247.0/24,35.191.0.0/16

# Rate limiting (requests per minute)
# Default: 10
RATE_LIMIT_PER_MINUTE=10

# Rate limiting burst (max requests in burst)
# Default: 20
RATE_LIMIT_BURST=20
```

---

## Flask Server Configuration

```bash
# Flask server port
# Default: 5000
PORT=5000
```

---

## Complete Environment Variables Template

Copy this template and fill in your values:

```bash
# ============================================
# TelePay10-26 Environment Variables
# ============================================

# --- Database Configuration ---
CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest

# --- Connection Pool (Optional) ---
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# --- Telegram Bot ---
TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest
TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest

# --- Payment Provider ---
PAYMENT_PROVIDER_SECRET_NAME=projects/291176869049/secrets/NOWPAYMENTS_API_KEY/versions/latest
NOWPAYMENTS_IPN_CALLBACK_URL_SECRET_NAME=projects/291176869049/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest

# --- Security (Optional) ---
WEBHOOK_SIGNING_SECRET_NAME=projects/291176869049/secrets/WEBHOOK_SIGNING_SECRET/versions/latest
ALLOWED_IPS=127.0.0.1,10.0.0.0/8
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_BURST=20

# --- Flask Server ---
PORT=5000
```

---

## How Secrets Are Accessed

### Code Implementation

All secrets are fetched from Google Secret Manager at runtime:

```python
from google.cloud import secretmanager

def fetch_secret(secret_path):
    """Fetch secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": secret_path})
    return response.payload.data.decode("UTF-8")

# Example usage:
secret_path = os.getenv("TELEGRAM_BOT_USERNAME")  # Gets the path
bot_username = fetch_secret(secret_path)           # Gets the actual value
```

### Where Secrets Are Fetched

- **Database credentials:** `database.py` (lines 9-59)
- **Bot credentials:** `config_manager.py` (lines 20-68)
- **Payment provider:** `services/payment_service.py` (lines 64-120)
- **Security config:** `app_initializer.py` (lines 179-237)

---

## Verifying Secret Manager Access

### Check if secrets exist:

```bash
# List all secrets
gcloud secrets list --project=telepay-459221

# Access specific secret (to verify it works)
gcloud secrets versions access latest \
  --secret=TELEGRAM_BOT_USERNAME \
  --project=telepay-459221
```

### Grant access to service account:

```bash
# Example: Grant access to default Compute Engine service account
gcloud secrets add-iam-policy-binding TELEGRAM_BOT_USERNAME \
  --member="serviceAccount:291176869049-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=telepay-459221
```

---

## Common Mistakes to Avoid

### ❌ INCORRECT: Setting actual secret values in environment variables

```bash
# DON'T DO THIS:
TELEGRAM_BOT_USERNAME=@PayGatePrime_bot
TELEGRAM_BOT_SECRET_NAME=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
DATABASE_PASSWORD_SECRET=MySecretPassword123
```

**Why wrong:** Secrets should never be in environment variables. They should only be in Secret Manager.

### ✅ CORRECT: Setting Secret Manager paths in environment variables

```bash
# DO THIS:
TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest
TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest
```

**Why correct:** Environment variables contain PATHS to secrets, not the secrets themselves. The application fetches the actual secrets from Secret Manager at runtime.

---

## Environment Variable Priority

1. **System environment variables** (highest priority)
2. **`.env` file** (if exists in TelePay10-26 directory)
3. **Defaults** (for optional variables only)

---

## Creating .env File (Local Development)

Create a `.env` file in TelePay10-26 directory:

```bash
# .env file (local development only)
# DO NOT commit this file to git!

CLOUD_SQL_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
DATABASE_HOST_SECRET=projects/291176869049/secrets/DATABASE_HOST_SECRET/versions/latest
DATABASE_NAME_SECRET=projects/291176869049/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/291176869049/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/291176869049/secrets/DATABASE_PASSWORD_SECRET/versions/latest
TELEGRAM_BOT_SECRET_NAME=projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest
TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest
PAYMENT_PROVIDER_SECRET_NAME=projects/291176869049/secrets/NOWPAYMENTS_API_KEY/versions/latest
NOWPAYMENTS_IPN_CALLBACK_URL_SECRET_NAME=projects/291176869049/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest
```

**⚠️ Security Note:** `.env` file is loaded by `telepay10-26.py` on startup (line 16).

---

## Troubleshooting

### Error: "Environment variable TELEGRAM_BOT_USERNAME is not set"

**Solution:** Set the environment variable with the Secret Manager path:
```bash
export TELEGRAM_BOT_USERNAME=projects/291176869049/secrets/TELEGRAM_BOT_USERNAME/versions/latest
```

### Error: "Permission denied when accessing secret"

**Solution:** Grant `secretmanager.secretAccessor` role to your service account:
```bash
gcloud secrets add-iam-policy-binding TELEGRAM_BOT_USERNAME \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Error: "Secret not found"

**Solution:** Create the secret in Secret Manager:
```bash
echo -n "@PayGatePrime_bot" | gcloud secrets create TELEGRAM_BOT_USERNAME \
  --data-file=- \
  --project=telepay-459221
```

---

## Summary

**Key Principle:** Environment variables contain **PATHS to secrets**, not the secrets themselves.

**Format:** `projects/PROJECT_NUMBER/secrets/SECRET_NAME/versions/VERSION`

**Security:** Secrets are fetched from Secret Manager at runtime, never stored in code or environment variables.

**Documentation:** This file supersedes any conflicting documentation regarding TELEGRAM_BOT_USERNAME or other secret configurations.

---

**Last Updated:** 2025-11-13 Session 150
**Maintained By:** Claude Code Integration Team
