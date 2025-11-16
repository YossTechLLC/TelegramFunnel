# TelePay10-26 Environment Setup Guide

This guide explains how to set up and use the `.env` file for running the TelePay Telegram bot locally.

---

## 📋 Overview

The TelePay bot requires environment variables that point to secrets in Google Cloud Secret Manager. The `.env` file has been pre-configured with the correct Secret Manager paths for the `telepay-459221` project.

---

## 🚀 Quick Start

### 1. Verify the .env File Exists

The `.env` file should already exist in the `/TelePay10-26` directory:

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26
ls -la .env
```

### 2. Authenticate with Google Cloud

Before running the bot, authenticate your local machine:

```bash
# Login to Google Cloud
gcloud auth application-default login

# Verify you're using the correct project
gcloud config set project telepay-459221

# Verify authentication
gcloud auth list
```

### 3. Verify Secret Manager Access

Test that you can access the secrets:

```bash
# Test fetching a secret
gcloud secrets versions access latest --secret=TELEGRAM_BOT_USERNAME

# If you get a permissions error, grant yourself access:
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Run the Bot

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26
python3 telepay10-26.py
```

---

## 📝 Environment Variables Explained

### Telegram Bot Configuration

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `TELEGRAM_BOT_SECRET_NAME` | Path to bot token in Secret Manager | `projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest` |
| `TELEGRAM_BOT_USERNAME` | Path to bot username in Secret Manager | Value: `@YourBotName` |

### NowPayments Configuration

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `PAYMENT_PROVIDER_SECRET_NAME` | Path to NowPayments API token | Used for creating invoices |
| `NOWPAYMENT_WEBHOOK_KEY` | Path to IPN webhook verification key | Used to verify NowPayments callbacks |
| `NOWPAYMENTS_IPN_CALLBACK_URL` | Path to IPN callback URL | Example: `https://np-webhook-10-26-*.run.app/nowpayments-ipn` |

### Payment Flow Configuration

| Variable | Description | Usage |
|----------|-------------|-------|
| `SUCCESS_URL_SIGNING_KEY` | Path to URL signing key | Encrypts payment redirect URLs |
| `WEBHOOK_BASE_URL` | Path to webhook base URL | Example: `https://gcwebhook1-10-26-*.run.app` |

### Database Configuration

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `DATABASE_HOST_SECRET` | Path to database host | Cloud SQL IP or socket path |
| `DATABASE_NAME_SECRET` | Path to database name | `telepaydb` |
| `DATABASE_USER_SECRET` | Path to database username | `postgres` |
| `DATABASE_PASSWORD_SECRET` | Path to database password | (stored securely in Secret Manager) |

---

## 🔧 How It Works

1. **Environment Variables are Loaded**
   - When `telepay10-26.py` starts, it reads environment variables from `.env`
   - Each variable contains a **path** to a secret in Secret Manager

2. **Secrets are Fetched at Runtime**
   - The code uses `os.getenv()` to get the Secret Manager path
   - Then calls `secretmanager.SecretManagerServiceClient()` to fetch the actual value
   - Example:
     ```python
     secret_path = os.getenv("TELEGRAM_BOT_SECRET_NAME")
     # Returns: "projects/291176869049/secrets/TELEGRAM_BOT_SECRET_NAME/versions/latest"

     client = secretmanager.SecretManagerServiceClient()
     response = client.access_secret_version(request={"name": secret_path})
     bot_token = response.payload.data.decode("UTF-8")
     # Returns: "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
     ```

3. **Secrets are Used**
   - The fetched secrets are used to initialize:
     - Telegram Bot API connection
     - NowPayments API client
     - PostgreSQL database connection
     - Payment webhook handlers

---

## 🐛 Troubleshooting

### Error: "Environment variable X is not set"

**Cause:** The `.env` file is missing or not in the correct location.

**Solution:**
```bash
# Verify .env exists
ls -la /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26/.env

# If missing, copy from example
cp .env.example .env
```

### Error: "Error fetching secret from Secret Manager"

**Cause:** Authentication or permission issues.

**Solution:**
```bash
# Re-authenticate
gcloud auth application-default login

# Verify project
gcloud config get-value project

# Test secret access
gcloud secrets versions access latest --secret=TELEGRAM_BOT_USERNAME

# Grant permissions if needed
gcloud projects add-iam-policy-binding telepay-459221 \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Error: "Database connection failed"

**Cause:** Cloud SQL instance not accessible from your machine.

**Solutions:**

**Option 1: Add your IP to Cloud SQL whitelist**
```bash
# Get your public IP
curl ifconfig.me

# Add to Cloud SQL authorized networks (via Cloud Console)
# Or use gcloud:
gcloud sql instances patch telepaypsql \
  --authorized-networks=YOUR_IP_ADDRESS
```

**Option 2: Use Cloud SQL Auth Proxy (Recommended)**
```bash
# Download Cloud SQL Auth Proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

# Start proxy in background
./cloud-sql-proxy telepay-459221:us-central1:telepaypsql &

# Update DATABASE_HOST_SECRET to point to localhost:5432
# (This requires modifying the secret in Secret Manager)
```

### Error: "ModuleNotFoundError: No module named 'X'"

**Cause:** Missing Python dependencies.

**Solution:**
```bash
# Install requirements (if requirements.txt exists)
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26
pip3 install -r requirements.txt

# Or install individually
pip3 install python-telegram-bot psycopg2-binary google-cloud-secret-manager httpx
```

---

## 🔐 Security Best Practices

### ✅ DO:
- Keep `.env` file local only (never commit to git)
- Use `.env.example` as a template for others
- Rotate secrets regularly in Secret Manager
- Use least-privilege IAM roles
- Use Cloud SQL Auth Proxy for database connections

### ❌ DON'T:
- Commit `.env` to version control
- Share `.env` file via email/chat
- Hardcode secrets in code
- Use the same secrets for dev and production

---

## 📚 Additional Resources

- [Google Cloud Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [NowPayments API Documentation](https://documenter.getpostman.com/view/7907941/S1a32n38)

---

## 🆘 Getting Help

If you encounter issues not covered in this guide:

1. Check application logs for specific error messages
2. Verify all secrets exist in Secret Manager:
   ```bash
   gcloud secrets list
   ```
3. Test each secret individually:
   ```bash
   gcloud secrets versions access latest --secret=SECRET_NAME
   ```
4. Review the code in `config_manager.py` and `database.py` to understand how secrets are fetched

---

## 📋 Environment Variables Checklist

Use this checklist to verify your setup:

- [ ] `.env` file exists in `/TelePay10-26` directory
- [ ] Google Cloud authentication completed (`gcloud auth application-default login`)
- [ ] Project set to `telepay-459221` (`gcloud config set project telepay-459221`)
- [ ] Secret Manager access granted (tested with `gcloud secrets versions access latest --secret=TELEGRAM_BOT_USERNAME`)
- [ ] All 11 environment variables present in `.env`:
  - [ ] TELEGRAM_BOT_SECRET_NAME
  - [ ] TELEGRAM_BOT_USERNAME
  - [ ] PAYMENT_PROVIDER_SECRET_NAME
  - [ ] NOWPAYMENT_WEBHOOK_KEY
  - [ ] NOWPAYMENTS_IPN_CALLBACK_URL
  - [ ] SUCCESS_URL_SIGNING_KEY
  - [ ] WEBHOOK_BASE_URL
  - [ ] DATABASE_HOST_SECRET
  - [ ] DATABASE_NAME_SECRET
  - [ ] DATABASE_USER_SECRET
  - [ ] DATABASE_PASSWORD_SECRET
- [ ] Database connectivity verified (Cloud SQL instance running and accessible)
- [ ] Python dependencies installed (`pip3 install -r requirements.txt`)

---

## ✅ Ready to Run

If all checklist items are complete, you're ready to run the bot:

```bash
cd /mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/OCTOBER/10-26/TelePay10-26
python3 telepay10-26.py
```

The bot should start and display:
```
🚀 Starting TelePay Bot...
✅ Telegram Bot Token loaded
✅ Database connection successful
✅ Payment gateway initialized
🤖 Bot is running...
```
