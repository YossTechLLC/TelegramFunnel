# GCPaymentGateway-10-26

Self-contained Cloud Run service for creating payment invoices via NowPayments API.

## Overview

**Purpose:** Create payment invoices for subscriptions and donations
**Replaces:** TelePay10-26/start_np_gateway.py (PaymentGatewayManager class)
**Architecture:** Self-contained Flask service with modular design

## Architecture

This service is built with complete modularity and self-containment:

```
GCPaymentGateway-10-26/
├── service.py              # Flask app & route registration
├── config_manager.py       # Secret Manager operations
├── database_manager.py     # Database operations
├── payment_handler.py      # NowPayments API integration
├── validators.py           # Input validation
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
└── .dockerignore           # Exclude patterns
```

## API Endpoints

### Health Check
```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "gcpaymentgateway-10-26"
}
```

### Create Invoice
```bash
POST /create-invoice
Content-Type: application/json

{
  "user_id": 6271402111,
  "amount": 9.99,
  "open_channel_id": "-1003268562225",
  "subscription_time_days": 30,
  "payment_type": "subscription",
  "tier": 1
}
```

**Success Response (200):**
```json
{
  "success": true,
  "invoice_id": "12345678",
  "invoice_url": "https://nowpayments.io/payment/?iid=12345678",
  "order_id": "PGP-6271402111|-1003268562225",
  "status_code": 200
}
```

**Error Response (400/404/500):**
```json
{
  "success": false,
  "error": "Channel -1003268562225 not found",
  "status_code": 404
}
```

## Environment Variables

All secrets are fetched from Google Secret Manager:

- `PAYMENT_PROVIDER_SECRET_NAME` - Path to NowPayments API key
- `NOWPAYMENTS_IPN_CALLBACK_URL` - Path to IPN callback URL
- `DATABASE_HOST_SECRET` - Path to database host
- `DATABASE_NAME_SECRET` - Path to database name
- `DATABASE_USER_SECRET` - Path to database user
- `DATABASE_PASSWORD_SECRET` - Path to database password

## Deployment

```bash
cd GCPaymentGateway-10-26

gcloud run deploy gcpaymentgateway-10-26 \
  --source=. \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="PAYMENT_PROVIDER_SECRET_NAME=projects/telepay-459221/secrets/NOWPAYMENTS_API_KEY/versions/latest" \
  --set-env-vars="NOWPAYMENTS_IPN_CALLBACK_URL=projects/telepay-459221/secrets/NOWPAYMENTS_IPN_CALLBACK_URL/versions/latest" \
  --set-env-vars="DATABASE_HOST_SECRET=projects/telepay-459221/secrets/DATABASE_HOST_SECRET/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest" \
  --service-account=291176869049-compute@developer.gserviceaccount.com \
  --min-instances=0 \
  --max-instances=5 \
  --memory=256Mi \
  --cpu=1 \
  --timeout=60s \
  --concurrency=80
```

## Testing

### Health Check
```bash
curl https://gcpaymentgateway-10-26-<hash>.run.app/health
```

### Create Invoice
```bash
curl -X POST https://gcpaymentgateway-10-26-<hash>.run.app/create-invoice \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 6271402111,
    "amount": 9.99,
    "open_channel_id": "-1003268562225",
    "subscription_time_days": 30,
    "payment_type": "subscription",
    "tier": 1
  }'
```

## Logging

All logs use emoji-based logging for easy filtering:

- 🚀 Gateway initialization
- 🔧 Configuration loading
- 💳 Payment processing
- 📋 Order/Invoice operations
- ✅ Success operations
- ❌ Error operations
- ⚠️ Warning operations
- 🔍 Database queries
- 🌐 API calls

## Integration Points

### Upstream Services (Callers)
- GCBotCommand-10-26 (subscription payments)
- GCDonationHandler-10-26 (donation payments)

### Downstream Services
- NowPayments API (invoice creation)
- PostgreSQL Database (channel validation)
- Google Secret Manager (credentials)

## Error Handling

| Status Code | Description |
|-------------|-------------|
| 200 | Invoice created successfully |
| 400 | Invalid request (validation error) |
| 404 | Channel not found in database |
| 500 | Server error (database, API, or config error) |

## Monitoring

View logs in Cloud Logging:
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcpaymentgateway-10-26"
```

Filter for errors:
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcpaymentgateway-10-26"
"❌"
```

## Troubleshooting

### Invoice creation fails with "Payment provider token is required"
- Verify `PAYMENT_PROVIDER_SECRET_NAME` environment variable is set
- Verify service account has `secretmanager.secretAccessor` role
- Check Secret Manager for `NOWPAYMENTS_API_KEY` secret

### Database connection fails
- Verify `DATABASE_HOST_SECRET`, `DATABASE_NAME_SECRET`, `DATABASE_USER_SECRET`, `DATABASE_PASSWORD_SECRET` are set
- Verify service account has `cloudsql.client` role
- Check database instance is running

### Channel validation fails
- Verify channel exists in `main_clients_database` table
- Check `open_channel_id` format (should be negative for Telegram channels)
- Use "donation_default" for generic donations

## Version

**Service Version:** 1.0
**Created:** 2025-11-12
**Parent Architecture:** GCPaymentGateway_REFACTORING_ARCHITECTURE.md
