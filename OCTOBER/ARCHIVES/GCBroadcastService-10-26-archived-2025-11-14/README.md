# GCBroadcastService-10-26

**Service Type:** Cloud Run Webhook Service
**Purpose:** Automated and manual broadcast management for Telegram channels
**Status:** 🚧 In Development (Refactored from GCBroadcastScheduler-10-26)

---

## 📋 Overview

GCBroadcastService is a self-contained microservice that manages broadcast messages to both open and closed Telegram channels. It supports:

- ✅ **Automated Broadcasts**: Daily scheduled broadcasts via Cloud Scheduler
- ✅ **Manual Triggers**: JWT-authenticated API for on-demand broadcasting
- ✅ **Rate Limiting**: Prevents abuse with configurable intervals
- ✅ **Error Tracking**: Automatic retry and failure management
- ✅ **Status Monitoring**: Real-time broadcast statistics

---

## 🏗️ Architecture

This service follows a **self-contained architecture** with no external shared module dependencies:

```
GCBroadcastService-10-26/
├── main.py                      # Flask app (application factory)
├── routes/
│   ├── broadcast_routes.py      # Broadcast execution endpoints
│   └── api_routes.py            # Manual trigger API endpoints
├── services/
│   ├── broadcast_scheduler.py   # Scheduling logic
│   ├── broadcast_executor.py    # Execution logic
│   └── broadcast_tracker.py     # State tracking
├── clients/
│   ├── telegram_client.py       # Telegram Bot API wrapper
│   └── database_client.py       # PostgreSQL operations
├── utils/
│   ├── config.py                # Configuration & Secret Manager
│   ├── auth.py                  # JWT authentication helpers
│   └── logging_utils.py         # Structured logging
└── tests/
    ├── test_routes.py
    ├── test_services.py
    └── test_clients.py
```

---

## 🔐 API Endpoints

### Health Check
```
GET /health
```
Returns service health status.

### Execute Broadcasts (Cloud Scheduler)
```
POST /api/broadcast/execute
```
Executes all broadcasts that are due to be sent.

### Manual Trigger (JWT Required)
```
POST /api/broadcast/trigger
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "broadcast_id": "uuid"
}
```

### Get Broadcast Status (JWT Required)
```
GET /api/broadcast/status/<broadcast_id>
Authorization: Bearer <JWT_TOKEN>
```

---

## 🔧 Environment Variables

All configuration is stored in Google Cloud Secret Manager:

- `BOT_TOKEN_SECRET` - Telegram bot token
- `BOT_USERNAME_SECRET` - Telegram bot username
- `JWT_SECRET_KEY_SECRET` - JWT signing key
- `BROADCAST_AUTO_INTERVAL_SECRET` - Auto broadcast interval (hours, default: 24)
- `BROADCAST_MANUAL_INTERVAL_SECRET` - Manual trigger rate limit (hours, default: 0.0833 = 5 minutes)
- `CLOUD_SQL_CONNECTION_NAME_SECRET` - Cloud SQL instance connection
- `DATABASE_NAME_SECRET` - PostgreSQL database name
- `DATABASE_USER_SECRET` - PostgreSQL username
- `DATABASE_PASSWORD_SECRET` - PostgreSQL password

---

## 🚀 Local Development

### Prerequisites
- Python 3.11+
- Docker
- Google Cloud SDK

### Run Locally
```bash
# Build Docker image
docker build -t gcbroadcastservice-10-26 .

# Run container
docker run -p 8080:8080 --env-file .env.local gcbroadcastservice-10-26
```

### Test Endpoints
```bash
# Health check
curl http://localhost:8080/health

# Execute broadcasts
curl -X POST http://localhost:8080/api/broadcast/execute

# Manual trigger (with JWT)
curl -X POST http://localhost:8080/api/broadcast/trigger \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"broadcast_id": "uuid"}'
```

---

## 📦 Deployment

### Deploy to Cloud Run
```bash
gcloud run deploy gcbroadcastservice-10-26 \
  --source=./GCBroadcastService-10-26 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="BOT_TOKEN_SECRET=projects/telepay-459221/secrets/telegram-bot-token/versions/latest" \
  --set-env-vars="BOT_USERNAME_SECRET=projects/telepay-459221/secrets/telegram-bot-username/versions/latest" \
  --set-env-vars="JWT_SECRET_KEY_SECRET=projects/telepay-459221/secrets/jwt-secret-key/versions/latest" \
  --set-env-vars="BROADCAST_AUTO_INTERVAL_SECRET=projects/telepay-459221/secrets/broadcast-auto-interval/versions/latest" \
  --set-env-vars="BROADCAST_MANUAL_INTERVAL_SECRET=projects/telepay-459221/secrets/broadcast-manual-interval/versions/latest" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME_SECRET=projects/telepay-459221/secrets/cloud-sql-connection-name/versions/latest" \
  --set-env-vars="DATABASE_NAME_SECRET=projects/telepay-459221/secrets/database-name/versions/latest" \
  --set-env-vars="DATABASE_USER_SECRET=projects/telepay-459221/secrets/database-user/versions/latest" \
  --set-env-vars="DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/database-password/versions/latest" \
  --min-instances=0 \
  --max-instances=3 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300s \
  --concurrency=80 \
  --service-account=telepay-cloudrun@telepay-459221.iam.gserviceaccount.com
```

### Configure Cloud Scheduler
```bash
gcloud scheduler jobs create http broadcast-execution-daily \
  --schedule="0 12 * * *" \
  --uri="https://gcbroadcastservice-10-26-XXXXXXX-uc.a.run.app/api/broadcast/execute" \
  --http-method=POST \
  --message-body='{"source": "cloud_scheduler"}' \
  --location=us-central1 \
  --time-zone="Etc/UTC" \
  --oidc-service-account-email=telepay-scheduler@telepay-459221.iam.gserviceaccount.com \
  --oidc-token-audience="https://gcbroadcastservice-10-26-XXXXXXX-uc.a.run.app"
```

---

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/test_services.py -v
```

### Run Integration Tests
```bash
pytest tests/test_routes.py -v
```

### Run All Tests
```bash
pytest tests/ -v --cov=.
```

---

## 📊 Monitoring

### Cloud Logging Filters

**All Service Logs:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastservice-10-26"
```

**Errors Only:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastservice-10-26"
severity>=ERROR
```

**Broadcast Executions:**
```
resource.type="cloud_run_revision"
resource.labels.service_name="gcbroadcastservice-10-26"
textPayload=~"Broadcast execution triggered"
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** Broadcasts not sending
- Check Cloud Scheduler is enabled and running
- Verify broadcast entries have `is_active = true`
- Check `next_send_time` is in the past
- Verify `consecutive_failures < 5`

**Issue:** JWT authentication failing
- Verify JWT_SECRET_KEY matches website
- Check token expiration time
- Validate Authorization header format: `Bearer <token>`

**Issue:** Database connection errors
- Verify Cloud SQL instance is running
- Check service account has Cloud SQL Client role
- Verify Secret Manager secrets are correct

---

## 📝 Changelog

### Version 1.0 (2025-11-13)
- Initial refactoring from GCBroadcastScheduler-10-26
- Self-contained module architecture
- Application factory pattern
- Enhanced error handling and logging

---

## 📚 Documentation

- **Architecture:** [GCBroadcastService_REFACTORING_ARCHITECTURE.md](../GCBroadcastService_REFACTORING_ARCHITECTURE.md)
- **Implementation Checklist:** [GCBroadcastService_REFACTORING_ARCHITECTURE_CHECKLIST.md](../GCBroadcastService_REFACTORING_ARCHITECTURE_CHECKLIST.md)
- **Progress Tracking:** [GCBroadcastService_REFACTORING_ARCHITECTURE_CHECKLIST_PROGRESS.md](../GCBroadcastService_REFACTORING_ARCHITECTURE_CHECKLIST_PROGRESS.md)

---

**Service Owner:** TelePay Development Team
**Last Updated:** 2025-11-13
