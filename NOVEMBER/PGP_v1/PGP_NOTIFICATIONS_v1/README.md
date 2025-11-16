# PGP_NOTIFICATIONS

## Overview

Standalone Cloud Run webhook service for sending payment notifications to channel owners via Telegram Bot API.

## Service Description

This service handles all payment notifications (subscriptions and donations) for the TelePay platform. It is called by payment processing webhooks after successful payment validation.

## Architecture

- **Type:** Cloud Run Webhook (Flask)
- **Version:** 1.0
- **Date:** 2025-11-12
- **Self-Contained:** No shared module dependencies

## API Endpoints

### POST /send-notification
Send payment notification to channel owner

### POST /test-notification
Send test notification to verify setup

### GET /health
Health check endpoint for Cloud Run

## Deployment

```bash
bash deploy_pgp_notificationservice.sh
```

## Testing

See PGP_NOTIFICATIONS_REFACTORING_ARCHITECTURE.md for detailed testing instructions.
