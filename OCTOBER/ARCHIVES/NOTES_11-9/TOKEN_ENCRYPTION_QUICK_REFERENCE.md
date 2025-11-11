# Token Encryption/Decryption Quick Reference

## Service Encryption Status Matrix

```
SERVICE                    | DECRYPT | ENCRYPT | DUAL-KEY | TOKENS_USED | ROLE
---------------------------+---------+---------+----------+-------------+------------------------------
GCWebhook1-10-26          |    ✅   |    ✅   |    -     |      Y      | Payment Processor
GCWebhook2-10-26          |    ✅   |    ❌   |    -     |      Y      | Telegram Invite Sender
GCSplit1-10-26            |    ❌   |    ✅   |    ✅    |      Y      | Orchestrator (BOTH keys)
GCSplit2-10-26            |    ✅   |    ✅   |    -     |      Y      | USDT→ETH Estimator
GCSplit3-10-26            |    ✅   |    ✅   |    -     |      Y      | ETH→Client Swapper
GCHostPay1-10-26          |    ✅   |    ✅   |    ✅    |      Y      | Validator/Orchestrator
GCHostPay2-10-26          |    ✅   |    ✅   |    -     |      Y      | Status Checker
GCHostPay3-10-26          |    ✅   |    ✅   |    -     |      Y      | Payment Executor
GCAccumulator-10-26        |    ❌   |    ❌   |    -     |      N      | Accumulator (UNUSED)
GCBatchProcessor-10-26    |    ❌   |    ✅   |    ❌    |      Y      | Batch Processor (TPS_KEY)
GCMicroBatchProcessor-10-26|   ✅   |    ✅   |    -     |      Y      | Micro-Batch Handler
np-webhook-10-26         |    ❌   |    ❌   |    -     |      N      | IPN Handler (sig only)
TelePay10-26             |    ❌   |    ❌   |    -     |      N      | Telegram Bot
```

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total Services | 13 |
| With token_manager.py | 11 |
| Use Encryption | 9 |
| Use Decryption | 8 |
| Use Both | 6 |
| Decrypt Only | 2 (GCWebhook2, GCBatchProcessor) |
| Encrypt Only | 2 (GCSplit1, GCBatchProcessor) |
| Neither | 3 (GCAccumulator, np-webhook, TelePay) |
| Unused token_manager | 1 (GCAccumulator) |

## Token Data by Service

### DECRYPT ENDPOINTS (8 services)

1. **GCWebhook1-10-26** (GET /)
   - Receives: Token from NOWPayments success_url
   - Extract: user_id, closed_channel_id, wallet_address, payout_currency, payout_network, subscription_time_days, subscription_price
   - Key: SUCCESS_URL_SIGNING_KEY

2. **GCWebhook2-10-26** (POST /)
   - Receives: Encrypted token from GCWebhook1
   - Extract: Same as above
   - Key: SUCCESS_URL_SIGNING_KEY

3. **GCSplit2-10-26** (POST /)
   - Receives: Encrypted token from GCSplit1
   - Extract: adjusted_amount, swap_currency, payout_mode, actual_eth_amount
   - Key: SUCCESS_URL_SIGNING_KEY

4. **GCSplit3-10-26** (POST /)
   - Receives: Encrypted token from GCSplit1
   - Extract: eth_amount, swap_currency, payout_mode, actual_eth_amount
   - Key: SUCCESS_URL_SIGNING_KEY

5. **GCHostPay1-10-26** (POST /)
   - Receives: Encrypted token from GCSplit1
   - Extract: cn_api_id, from_currency, payin_address, actual_eth_amount, estimated_eth_amount
   - Key: TPS_HOSTPAY_SIGNING_KEY (external boundary)

6. **GCHostPay2-10-26** (POST /)
   - Receives: Encrypted token from GCHostPay1
   - Extract: cn_api_id
   - Key: SUCCESS_URL_SIGNING_KEY

7. **GCHostPay3-10-26** (POST /)
   - Receives: Encrypted token from GCHostPay1
   - Extract: Payment amount, payin_address
   - Key: SUCCESS_URL_SIGNING_KEY

8. **GCMicroBatchProcessor-10-26** (POST /callback)
   - Receives: Callback token from GCHostPay1
   - Extract: batch_conversion_id, cn_api_id, tx_hash, actual_usdt_received
   - Key: SUCCESS_URL_SIGNING_KEY

### ENCRYPT ENDPOINTS (9 services)

1. **GCWebhook1-10-26**
   - Encrypts for: GCWebhook2 (telegram invite)
   - Data: subscription_time_days, subscription_price, wallet_address, user_id, closed_channel_id
   - Key: SUCCESS_URL_SIGNING_KEY

2. **GCSplit1-10-26**
   - Encrypts for: GCSplit2 (estimate request)
   - Data: adjusted_amount, swap_currency='usdt', payout_mode, actual_eth_amount
   - Key: SUCCESS_URL_SIGNING_KEY

3. **GCSplit1-10-26**
   - Encrypts for: GCSplit3 (swap request)
   - Data: eth_amount, swap_currency='eth', payout_mode, actual_eth_amount
   - Key: SUCCESS_URL_SIGNING_KEY

4. **GCSplit1-10-26**
   - Encrypts for: GCHostPay1 (payment orchestration)
   - Data: cn_api_id, from_currency, payin_address, actual_eth_amount, estimated_eth_amount
   - Key: TPS_HOSTPAY_SIGNING_KEY (external boundary)

5. **GCSplit2-10-26**
   - Encrypts for: GCSplit1 (estimate response)
   - Data: from_amount, to_amount, deposit_fee, withdrawal_fee, swap_currency, payout_mode, actual_eth_amount
   - Key: SUCCESS_URL_SIGNING_KEY

6. **GCSplit3-10-26**
   - Encrypts for: GCSplit1 (swap response)
   - Data: cn_api_id, payin_address, payee_address, rate, actual_eth_amount
   - Key: SUCCESS_URL_SIGNING_KEY

7. **GCHostPay1-10-26**
   - Encrypts for: GCHostPay2 (status check)
   - Data: cn_api_id
   - Key: SUCCESS_URL_SIGNING_KEY

8. **GCHostPay1-10-26**
   - Encrypts for: GCHostPay3 (execute payment)
   - Data: Payment amount, payin_address, cn_api_id
   - Key: SUCCESS_URL_SIGNING_KEY

9. **GCBatchProcessor-10-26**
   - Encrypts for: GCSplit1 (batch USDT→Client swap)
   - Data: batch_id, total_amount_usdt, payout_currency, payout_network
   - Key: TPS_HOSTPAY_SIGNING_KEY

### NO TOKENS (3 services)

1. **GCAccumulator-10-26**
   - Receives: Plain JSON from GCWebhook1
   - Has token_manager.py but UNUSED
   - Reason: Direct accumulation without token overhead

2. **np-webhook-10-26**
   - No tokens, no token_manager.py
   - Uses: HMAC-SHA256 signature verification (not encryption)
   - Key: NOWPAYMENTS_IPN_SECRET

3. **TelePay10-26**
   - No tokens, no token_manager.py
   - Direct Telegram Bot API communication

## Signing Key Distribution

### SUCCESS_URL_SIGNING_KEY
Used for: Internal service-to-service communication

Services:
- GCWebhook1 (encrypt for GCWebhook2)
- GCWebhook2 (decrypt from GCWebhook1)
- GCSplit1 (encrypt for GCSplit2, GCSplit3)
- GCSplit2 (decrypt from GCSplit1, encrypt back)
- GCSplit3 (decrypt from GCSplit1, encrypt back)
- GCHostPay1 (encrypt for GCHostPay2, GCHostPay3)
- GCHostPay2 (decrypt from GCHostPay1, encrypt back)
- GCHostPay3 (decrypt from GCHostPay1, encrypt back)
- GCAccumulator (unused)
- GCMicroBatchProcessor (decrypt callback from GCHostPay1)

### TPS_HOSTPAY_SIGNING_KEY
Used for: External service boundary (GCSplit1 ↔ GCHostPay1)

Services:
- GCSplit1 (encrypt for GCHostPay1)
- GCHostPay1 (decrypt from GCSplit1)
- GCBatchProcessor (encrypt for GCSplit1)

### NOWPAYMENTS_IPN_SECRET
Used for: IPN signature verification (NOT encryption)

Services:
- np-webhook (verify signature only)

## Token Format Comparison

| Format | Size | Fields | Signature | Encoding |
|--------|------|--------|-----------|----------|
| Payment Data | 38+ bytes | 7 | 16-byte HMAC | Base64 URL-safe |
| Payment Split | Variable | 9 | 16-byte HMAC | Base64 URL-safe |
| HostPay | Variable | 8 | 16-byte HMAC | Base64 URL-safe |

## Token Expiration Windows

| Token Type | Window | Service | Reason |
|------------|--------|---------|--------|
| Payment | 2 hours | GCWebhook1→GCWebhook2 | Accommodate retry delays |
| Invite | 24 hours | GCWebhook2 | Large retry window for reliability |
| HostPay | 60 seconds | GCSplit1→GCHostPay1 | Strict window for immediate execution |
| Estimate | Variable | GCSplit1→GCSplit2 | No explicit validation in code |
| Swap | Variable | GCSplit1→GCSplit3 | No explicit validation in code |

## Service Request/Response Patterns

### Request-Response Services (5)
```
GCSplit2-10-26:  GCSplit1 (request) → GCSplit2 (decrypt) → ChangeNow API → (encrypt response) → back to GCSplit1
GCSplit3-10-26:  GCSplit1 (request) → GCSplit3 (decrypt) → ChangeNow API → (encrypt response) → back to GCSplit1
GCHostPay2-10-26: GCHostPay1 (request) → GCHostPay2 (decrypt) → ChangeNow API → (encrypt response) → back to GCHostPay1
GCHostPay3-10-26: GCHostPay1 (request) → GCHostPay3 (decrypt) → Wallet API → (encrypt response) → back to GCHostPay1
GCMicroBatchProcessor: GCHostPay1 (callback) → (decrypt) → Update DB
```

### One-Way Services (2)
```
GCWebhook1→GCWebhook2: One-way encryption, Telegram invite endpoint
GCBatchProcessor→GCSplit1: One-way encryption, USDT→Client swap
```

### No-Token Services (3)
```
GCAccumulator: Plain JSON from GCWebhook1
np-webhook: Signature verification from NowPayments
TelePay: Direct Telegram API
```

