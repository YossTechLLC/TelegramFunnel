# GCRegister10-5 - Channel Registration Service

## 🚀 Overview

GCRegister10-5 is a Flask web application that allows Telegram channel owners to self-register their channels into the subscription payment system. This service provides a user-friendly web interface for populating the `main_clients_database` table with channel configurations.

## 📋 Features

- **Web-based Registration Form**: Simple, intuitive interface for channel registration
- **Input Validation**: Comprehensive client-side and server-side validation
- **CAPTCHA Protection**: Basic math-based CAPTCHA to prevent bot submissions
- **Rate Limiting**: Protection against spam (5 registrations per hour per IP)
- **Database Integration**: Direct PostgreSQL insertion with duplicate prevention
- **Docker Support**: Containerized deployment ready
- **Google Cloud Integration**: Secret Manager for secure credential storage
- **Health Check Endpoint**: `/health` for monitoring and uptime checks

## 🏗️ Architecture

```
GCRegister10-5/
├── app.py                    # Main Flask application
├── config_manager.py         # Google Cloud Secret Manager integration
├── database_manager.py       # PostgreSQL connection & operations
├── forms.py                  # Flask-WTF form definitions
├── validators.py             # Custom validation functions
├── templates/                # HTML templates
│   ├── base.html            # Base template
│   ├── register.html        # Registration form
│   ├── success.html         # Success page
│   └── error.html           # Error page
├── static/
│   └── css/
│       └── style.css        # Custom CSS
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker container definition
├── .env.example            # Environment variable template
├── .dockerignore           # Docker ignore file
└── README.md               # This file
```

## 📊 Database Schema

The application inserts data into the `main_clients_database` table with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `open_channel_id` | String (≤14) | Public channel Telegram ID |
| `open_channel_title` | String (≤100) | Public channel title |
| `open_channel_description` | Text (≤500) | Public channel description |
| `closed_channel_id` | String (≤14) | Premium channel Telegram ID |
| `closed_channel_title` | String (≤100) | Premium channel title |
| `closed_channel_description` | Text (≤500) | Premium channel description |
| `sub_1_price` | Decimal | Tier 1 price (0-9999.99) |
| `sub_1_time` | Integer | Tier 1 duration in days (1-999) |
| `sub_2_price` | Decimal | Tier 2 price (0-9999.99) |
| `sub_2_time` | Integer | Tier 2 duration in days (1-999) |
| `sub_3_price` | Decimal | Tier 3 price (0-9999.99) |
| `sub_3_time` | Integer | Tier 3 duration in days (1-999) |
| `client_wallet_address` | String (≤110) | Cryptocurrency wallet address |
| `client_payout_currency` | String (≤4) | Payout currency code |

## 🔧 Prerequisites

### Required Services
1. **Google Cloud Project** with Secret Manager API enabled
2. **PostgreSQL Database** (accessible from deployment environment)
3. **Docker** (for containerized deployment)

### Required Secrets in Google Cloud Secret Manager

**Note:** This application uses **Cloud SQL Connector** for database connections. You don't need DATABASE_HOST_SECRET anymore.

Create the following secrets in your Google Cloud project:

```bash
# Database Name (skip if already exists)
gcloud secrets create DATABASE_NAME_SECRET --data-file=<name_file>

# Database User (skip if already exists)
gcloud secrets create DATABASE_USER_SECRET --data-file=<user_file>

# Database Password (skip if already exists)
gcloud secrets create DATABASE_PASSWORD_SECRET --data-file=<password_file>

# Flask Secret Key (REQUIRED - create this new secret)
echo "y764wg_-y2PHggbnl_BPfUiZhxOhTZhXadhCkNMl3LM" | gcloud secrets create DATABASE_SECRET_KEY --data-file=-
```

**Generated Flask Secret Key:** `y764wg_-y2PHggbnl_BPfUiZhxOhTZhXadhCkNMl3LM`

Use this exact value when creating the DATABASE_SECRET_KEY secret in Google Cloud Secret Manager.

### Cloud SQL Instance Connection Name

**Important:** Set the `INSTANCE_CONNECTION_NAME` environment variable to your Cloud SQL instance connection string:
```
INSTANCE_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql
```

This is a direct environment variable value (not from Secret Manager).

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Cloud SQL instance connection name (direct value)
INSTANCE_CONNECTION_NAME=telepay-459221:us-central1:telepaypsql

# Database credentials (Secret Manager paths)
DATABASE_NAME_SECRET=projects/YOUR_PROJECT_ID/secrets/DATABASE_NAME_SECRET/versions/latest
DATABASE_USER_SECRET=projects/YOUR_PROJECT_ID/secrets/DATABASE_USER_SECRET/versions/latest
DATABASE_PASSWORD_SECRET=projects/YOUR_PROJECT_ID/secrets/DATABASE_PASSWORD_SECRET/versions/latest

# Flask secret key (Secret Manager path)
DATABASE_SECRET_KEY=projects/YOUR_PROJECT_ID/secrets/DATABASE_SECRET_KEY/versions/latest
```

**Note:** The application uses Cloud SQL Connector for database connections. No host, port, or VPC configuration is needed.

## 🚀 Deployment

### Local Development

```bash
# Navigate to the directory
cd GCRegister10-5

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your actual values

# Run the application
python app.py
```

The application will be available at `http://localhost:8080`

### Docker Deployment

```bash
# Build the Docker image
docker build -t gcregister10-5 .

# Run the container
docker run -p 8080:8080 \
  -e INSTANCE_CONNECTION_NAME="telepay-459221:us-central1:telepaypsql" \
  -e DATABASE_NAME_SECRET="projects/PROJECT_ID/secrets/DATABASE_NAME_SECRET/versions/latest" \
  -e DATABASE_USER_SECRET="projects/PROJECT_ID/secrets/DATABASE_USER_SECRET/versions/latest" \
  -e DATABASE_PASSWORD_SECRET="projects/PROJECT_ID/secrets/DATABASE_PASSWORD_SECRET/versions/latest" \
  -e DATABASE_SECRET_KEY="projects/PROJECT_ID/secrets/DATABASE_SECRET_KEY/versions/latest" \
  gcregister10-5
```

### Google Cloud Run Deployment

```bash
# Deploy to Cloud Run with Cloud SQL Connector
gcloud run deploy gcregister10-5 \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql \
  --set-env-vars INSTANCE_CONNECTION_NAME="telepay-459221:us-central1:telepaypsql" \
  --set-env-vars DATABASE_NAME_SECRET="projects/PROJECT_ID/secrets/DATABASE_NAME_SECRET/versions/latest" \
  --set-env-vars DATABASE_USER_SECRET="projects/PROJECT_ID/secrets/DATABASE_USER_SECRET/versions/latest" \
  --set-env-vars DATABASE_PASSWORD_SECRET="projects/PROJECT_ID/secrets/DATABASE_PASSWORD_SECRET/versions/latest" \
  --set-env-vars DATABASE_SECRET_KEY="projects/PROJECT_ID/secrets/DATABASE_SECRET_KEY/versions/latest"
```

**Important Notes:**
- The `--add-cloudsql-instances` flag connects Cloud Run to your Cloud SQL instance
- INSTANCE_CONNECTION_NAME must match your Cloud SQL instance connection string
- No VPC connector is needed when using Cloud SQL Connector
- Replace `PROJECT_ID` with your actual Google Cloud project ID (e.g., 291176869049)

## 📝 Usage Guide

### Registering a Channel

1. **Navigate to the registration page** at `http://your-domain:8080/`

2. **Fill out the form sections**:
   - **Open Channel Information**: Your public channel details
   - **Closed Channel Information**: Your premium channel details
   - **Subscription Tiers**: Configure 3 pricing tiers (Bronze, Silver, Gold)
   - **Payment Information**: Your cryptocurrency wallet and payout currency
   - **CAPTCHA**: Answer the math question

3. **Submit the form**:
   - If successful, you'll see a success page with your channel ID
   - If there are errors, they'll be displayed with specific field feedback

4. **Verification**:
   - Check that your bot has admin access to both channels
   - Test the payment flow with a small transaction

### Health Check

Visit `http://your-domain:8080/health` to check service status:

```json
{
  "status": "healthy",
  "service": "GCRegister10-5 Channel Registration",
  "database": "connected"
}
```

## 🔒 Security Features

### Current Implementation (Basic)
- ✅ CSRF protection via Flask-WTF
- ✅ Math-based CAPTCHA
- ✅ Rate limiting (5 registrations/hour per IP)
- ✅ Input sanitization
- ✅ SQL injection prevention (parameterized queries)
- ✅ Duplicate channel ID prevention
- ✅ Secret Manager integration for credentials

### Future Enhancements
- 🔜 reCAPTCHA v3 integration
- 🔜 Email verification workflow
- 🔜 Admin approval system
- 🔜 Currency validation against ChangeNow API
- 🔜 Advanced wallet address format validation
- 🔜 IP whitelist/blacklist
- 🔜 Audit logging

## 🧪 Testing

### Manual Testing Checklist

- [ ] Form loads correctly
- [ ] CAPTCHA displays and validates
- [ ] Invalid inputs show appropriate error messages
- [ ] Valid inputs successfully insert to database
- [ ] Duplicate channel_id is rejected
- [ ] Success page displays correctly
- [ ] Health endpoint responds
- [ ] Rate limiting works (try 6 submissions)
- [ ] Database connection via Secret Manager works

### Test Cases

1. **Empty Form Submission**: All fields required errors
2. **Invalid Channel ID**: Letters, too long (>14 chars)
3. **Invalid Price**: Negative, >9999.99, >2 decimals
4. **Invalid Time**: 0, >999, non-numeric
5. **Invalid Wallet**: >110 chars, special characters
6. **Wrong CAPTCHA**: Error message and new CAPTCHA
7. **Duplicate Channel ID**: Registration rejected

## 🐛 Troubleshooting

### Common Issues

**Issue**: "Database connection unavailable"
- **Solution**: Check Secret Manager paths in environment variables
- Verify database credentials are correct
- Ensure network connectivity to database

**Issue**: "Rate limit exceeded"
- **Solution**: Wait 1 hour or restart the application
- Check IP address if behind proxy

**Issue**: "Channel ID already exists"
- **Solution**: This channel is already registered
- Use a different channel ID or update existing record manually

**Issue**: Form validation errors
- **Solution**: Check field requirements:
  - Channel IDs: ≤14 numeric characters
  - Prices: 0-9999.99 with ≤2 decimals
  - Times: 1-999 days
  - Wallet: ≤110 alphanumeric characters

## 📊 Monitoring

### Logging

The application uses emoji-based logging following the codebase convention:

- ✅ Success operations
- ❌ Errors
- 🔍 Debug/search operations
- 💰 Financial operations
- 🚀 Starting processes
- 📝 Data logging
- 🎯 Targeting operations
- 🔐 Security operations

### Key Metrics to Monitor

- Registration success rate
- Database connection health
- Rate limit violations
- Form validation errors
- CAPTCHA failure rate
- Response times

## 🔗 Integration

This service integrates with the existing TelegramFunnel payment system:

1. **Database**: Populates `main_clients_database` table
2. **TelePay10-16**: Uses registered channels for subscription management
3. **GCWebhook10-16**: Processes payments for registered channels
4. **GCSplit10-16**: Handles crypto conversions to registered wallets

## 📄 License

Part of the TelegramFunnel payment subscription system.

## 🙋 Support

For issues or questions:
- Check service status: `/health` endpoint
- Review logs for emoji-coded messages
- Verify environment variables and Secret Manager configuration
- Ensure database connectivity

---

**Built with:** Flask, PostgreSQL, Google Cloud Secret Manager, Docker, Bootstrap 5
