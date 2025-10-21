# GCHostPay10-21: Host Wallet Payment Service

## Overview

GCHostPay10-21 is a Google Cloud Run webhook service that receives encrypted, time-sensitive tokens from GCSplit10-21 (TPS10-21) and will execute automated ETH transfers from the host wallet to ChangeNow payin addresses.

**Current Status**: Phase 1 Complete - Token validation and payload extraction implemented. ETH transfer functionality to be added in Phase 2.

## Architecture

```
┌─────────────────┐
│  GCSplit10-21   │
│   (tps10-21)    │
└────────┬────────┘
         │
         │ 1. Generate signed token
         │ 2. POST to GCHostPay10-21
         │
         ▼
┌─────────────────┐
│ GCHostPay10-21  │
│   (tphp10-21)   │
├─────────────────┤
│ 1. Validate sig │
│ 2. Check expiry │
│ 3. Extract data │
│ 4. [TODO] Send  │
│    ETH via Web3 │
└─────────────────┘
```

## Token Security

### Signing Key
- **Environment Variable**: `TPS_HOSTPAY_SIGNING_KEY`
- **Value**: `6b5f0a6e6dca94b1e5d9b1f018f4c8a9e7fe4b0ecfc6e8b29bd2d19f7937df5a`
- **Location**: Google Cloud Secret Manager
- **Path**: `projects/291176869049/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest`
- **Shared With**: GCSplit10-21 (generator) and GCHostPay10-21 (validator)

### Token Format

Binary packed structure (Base64 URL-safe encoded):
```
[16 bytes] unique_id (fixed length, null-padded)
[1 byte]   cn_api_id length
[N bytes]  cn_api_id data
[1 byte]   from_currency length
[N bytes]  from_currency data
[1 byte]   from_network length
[N bytes]  from_network data
[8 bytes]  from_amount (double precision float)
[1 byte]   payin_address length
[N bytes]  payin_address data
[4 bytes]  timestamp (unix timestamp, uint32)
[16 bytes] HMAC-SHA256 signature (truncated)
```

### Token Expiration
- **Validity Window**: 1 minute (60 seconds) from creation
- **Tolerance**: +5 seconds for clock skew
- **Validation**: `current_time - 60 <= timestamp <= current_time + 5`

## Payload Fields

The token contains the following fields extracted from ChangeNow API response:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `unique_id` | string | Database linking ID | `"ABCD1234EF567890"` |
| `cn_api_id` | string | ChangeNow transaction ID | `"abc123xyz789"` |
| `from_currency` | string | Source currency | `"eth"` |
| `from_network` | string | Source network | `"eth"` |
| `from_amount` | float | Amount to send | `0.005` |
| `payin_address` | string | ChangeNow deposit address | `"0x1234..."` |

## Environment Variables

### Required Secrets (Google Cloud Secret Manager)

1. **TPS_HOSTPAY_SIGNING_KEY** (Required)
   - Purpose: HMAC signing key for token validation
   - Shared with: GCSplit10-21
   - Path: `projects/291176869049/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest`

2. **HOST_WALLET_ETH_ADDRESS** (Future use)
   - Purpose: Public ETH address of host wallet
   - Path: `projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest`

3. **HOST_WALLET_PRIVATE_KEY** (Future use)
   - Purpose: Private key for signing ETH transactions
   - Path: `projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest`
   - **Security**: Never log or expose this value

## Deployment

### Prerequisites

1. Google Cloud SDK installed and configured
2. Docker installed (for local testing)
3. Secrets created in Google Cloud Secret Manager
4. Service account with Secret Manager access

### Create Required Secrets

```bash
# Create TPS HostPay signing key secret
echo -n "6b5f0a6e6dca94b1e5d9b1f018f4c8a9e7fe4b0ecfc6e8b29bd2d19f7937df5a" | \
  gcloud secrets create TPS_HOSTPAY_SIGNING_KEY \
    --data-file=-

# Create host wallet address (placeholder for now)
echo -n "YOUR_ETH_WALLET_ADDRESS" | \
  gcloud secrets create HOST_WALLET_ETH_ADDRESS \
    --data-file=-

# Create host wallet private key (placeholder for now)
echo -n "YOUR_PRIVATE_KEY" | \
  gcloud secrets create HOST_WALLET_PRIVATE_KEY \
    --data-file=-
```

### Deploy to Google Cloud Run

```bash
# Navigate to service directory
cd GCHostPay10-21

# Deploy to Cloud Run
gcloud run deploy tphp10-21 \
    --source . \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --max-instances 10 \
    --min-instances 0 \
    --port 8080 \
    --set-env-vars TPS_HOSTPAY_SIGNING_KEY=projects/291176869049/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest \
    --set-env-vars HOST_WALLET_ETH_ADDRESS=projects/291176869049/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest \
    --set-env-vars HOST_WALLET_PRIVATE_KEY=projects/291176869049/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest
```

### Post-Deployment Configuration

After deploying, note the service URL (e.g., `https://tphp10-21-HASH-uc.a.run.app`). You'll need to:

1. **Create HOSTPAY_WEBHOOK_URL secret in Secret Manager**:
```bash
echo -n "https://tphp10-21-HASH-uc.a.run.app" | \
  gcloud secrets create HOSTPAY_WEBHOOK_URL \
    --data-file=-
```

2. **Update GCSplit10-21 service** with the new environment variable:
```bash
gcloud run services update tps10-21 \
    --region us-central1 \
    --update-env-vars HOSTPAY_WEBHOOK_URL=projects/291176869049/secrets/HOSTPAY_WEBHOOK_URL/versions/latest
```

## API Endpoints

### POST /

Main webhook endpoint for receiving payment requests from TPS10-21.

**Request Body**:
```json
{
  "token": "BASE64_ENCODED_TOKEN_HERE"
}
```

**Success Response** (200):
```json
{
  "status": "success",
  "message": "Token validated and payload extracted successfully",
  "data": {
    "unique_id": "ABCD1234EF567890",
    "cn_api_id": "abc123xyz789",
    "from_currency": "eth",
    "from_network": "eth",
    "from_amount": 0.005,
    "payin_address": "0x1234567890abcdef..."
  },
  "note": "ETH transfer functionality to be implemented"
}
```

**Error Responses**:
- 400: Invalid token, expired token, or malformed payload
- 500: Configuration error or processing error

### GET /health

Health check endpoint for monitoring.

**Success Response** (200):
```json
{
  "status": "healthy",
  "service": "GCHostPay10-21 Host Wallet Payment Service",
  "timestamp": 1234567890,
  "configuration": {
    "signing_key": "✅"
  }
}
```

## Integration Flow

1. **ChangeNow Transaction Created** (in GCSplit10-21)
   - ChangeNow returns transaction details
   - Transaction saved to `split_payout_que` table

2. **Token Generation** (in GCSplit10-21)
   - Extracts 6 required fields from ChangeNow response
   - Packs data into binary format
   - Signs with TPS_HOSTPAY_SIGNING_KEY
   - Base64 URL-safe encodes

3. **Webhook Call** (from GCSplit10-21 to GCHostPay10-21)
   - POST request with token in JSON body
   - 30-second timeout

4. **Token Validation** (in GCHostPay10-21)
   - Base64 decode
   - Verify HMAC signature
   - Check timestamp expiration (1-minute window)
   - Extract all 6 payload fields

5. **Payload Logging** (in GCHostPay10-21)
   - All extracted values logged with emoji prefixes
   - Format: `🆔 unique_id: ABCD1234EF567890`

6. **[Future] ETH Transfer** (in GCHostPay10-21)
   - Connect to Web3 provider
   - Build ETH transaction
   - Sign with HOST_WALLET_PRIVATE_KEY
   - Broadcast to network
   - Update database with transaction hash

## Logging

### Emoji Pattern
Consistent with existing services:
- 🎯 - Webhook called
- 🔐 - Security/encryption operations
- 🔓 - Token validated
- 📦 - Payload/data
- 🆔 - IDs/identifiers
- 💰 - Currency
- 🌐 - Network
- 💸 - Amount
- 🏦 - Address/wallet
- ⏰ - Timestamp
- ✅ - Success
- ❌ - Error
- ⚠️ - Warning

### Example Log Output

```
🎯 [HOSTPAY_WEBHOOK] Webhook called
📦 [HOSTPAY_WEBHOOK] Received token (length: 156 chars)
🔐 [CONFIG] Fetching TPS HostPay signing key
✅ [CONFIG] Successfully fetched TPS HostPay signing key
🔍 [TOKEN_DEBUG] Raw data size: 128 bytes
🔍 [TOKEN_DEBUG] Data size: 112 bytes
🔍 [TOKEN_DEBUG] Signature size: 16 bytes
🔓 [TOKEN_VALIDATION] Token validated successfully
⏰ [TOKEN_VALIDATION] Token age: 3 seconds
✅ [HOSTPAY_WEBHOOK] Token validated and decoded successfully

📦 [HOSTPAY_WEBHOOK] Extracted values:
   🆔 unique_id: ABCD1234EF567890
   🆔 cn_api_id: abc123xyz789
   💰 from_currency: eth
   🌐 from_network: eth
   💸 from_amount: 0.005
   🏦 payin_address: 0x1234567890abcdef...

⚠️ [HOSTPAY_WEBHOOK] ETH transfer not yet implemented
💡 [HOSTPAY_WEBHOOK] Next step: Send 0.005 ETH to 0x1234567890abcdef...
```

## Testing

### Local Testing

1. **Build Docker image**:
```bash
cd GCHostPay10-21
docker build -t tphp10-21:latest .
```

2. **Run locally** (requires Secret Manager access):
```bash
docker run -p 8080:8080 \
  -e TPS_HOSTPAY_SIGNING_KEY="projects/291176869049/secrets/TPS_HOSTPAY_SIGNING_KEY/versions/latest" \
  -e GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json" \
  -v /path/to/service-account-key.json:/path/to/service-account-key.json \
  tphp10-21:latest
```

3. **Test with curl**:
```bash
# Health check
curl http://localhost:8080/health

# Webhook test (requires valid token from GCSplit10-21)
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_VALID_TOKEN_HERE"}'
```

### Integration Testing

Trigger a complete flow:
1. Make a subscription payment through TelePay10-16
2. Complete payment via NowPayments
3. GCWebhook10-16 triggers GCSplit10-21
4. GCSplit10-21 creates ChangeNow transaction
5. GCSplit10-21 generates token and calls GCHostPay10-21
6. Check GCHostPay10-21 logs for extracted values

## Security Considerations

1. **Token Expiration**: 1-minute validity prevents replay attacks
2. **HMAC Signature**: Prevents token tampering
3. **Secret Manager**: All sensitive values stored securely
4. **Private Key Protection**: Never log or expose HOST_WALLET_PRIVATE_KEY
5. **HTTPS Only**: All webhook communication over TLS
6. **Unauthenticated Endpoint**: Token signature provides authentication

## Troubleshooting

### Token Validation Errors

**Error**: "Invalid token: cannot decode base64"
- **Cause**: Malformed token
- **Solution**: Check token generation in GCSplit10-21

**Error**: "Signature mismatch"
- **Cause**: Different signing keys in GCSplit and GCHostPay
- **Solution**: Verify TPS_HOSTPAY_SIGNING_KEY is identical in both services

**Error**: "Token expired"
- **Cause**: Token older than 60 seconds or clock skew
- **Solution**: Check system clocks, reduce processing time in GCSplit10-21

**Error**: "Invalid token: too small"
- **Cause**: Incomplete token data
- **Solution**: Verify all 6 fields are included during token generation

### Configuration Errors

**Error**: "Configuration error: signing key not available"
- **Cause**: TPS_HOSTPAY_SIGNING_KEY not set or Secret Manager access denied
- **Solution**: Verify environment variable and IAM permissions

### Verification Commands

```bash
# Check service status
gcloud run services describe tphp10-21 --region us-central1

# View logs
gcloud run services logs read tphp10-21 --region us-central1 --limit 50

# Test Secret Manager access
gcloud secrets versions access latest --secret="TPS_HOSTPAY_SIGNING_KEY"

# Update environment variable
gcloud run services update tphp10-21 \
    --region us-central1 \
    --update-env-vars KEY=VALUE
```

## Next Steps (Phase 2)

1. **Add Web3 Integration**:
   - Install `web3.py` package
   - Connect to Ethereum node (Infura/Alchemy)
   - Implement ETH transfer function

2. **Transaction Management**:
   - Gas price estimation
   - Nonce management
   - Transaction confirmation tracking
   - Error handling and retries

3. **Database Updates**:
   - Record transaction hash
   - Update payment status
   - Link with unique_id

4. **Monitoring**:
   - Transaction success/failure alerts
   - Gas cost tracking
   - Wallet balance monitoring

## Support

For issues or questions:
- Check Cloud Run logs
- Verify Secret Manager configuration
- Review integration flow documentation
- Test with health check endpoint

---

**Generated**: October 2025
**Version**: 10-21
**Service**: GCHostPay10-21 Host Wallet Payment Service
**Status**: Phase 1 Complete - Token validation working, ETH transfer pending
