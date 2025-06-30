# GCSplit30 - ChangeNOW API Integration

This module integrates ChangeNOW cryptocurrency exchange API into the TelegramFunnel payment system to automatically convert 30% of received ETH payments to client's preferred cryptocurrency.

## Overview

When a user pays for a subscription via NowPayments:
1. Payment is converted to ETH and sent to host wallet
2. User receives access to private channel
3. **NEW**: 30% of payment amount is automatically swapped to client's preferred currency
4. Converted cryptocurrency is sent to client's wallet address

## Components

### Core Files

- **`changenow_manager.py`** - ChangeNOW API client for creating and managing swaps
- **`eth_wallet_manager.py`** - Ethereum wallet operations for sending ETH to ChangeNOW
- **`swap_processor.py`** - Main orchestrator that coordinates the swap workflow
- **`swap_database_manager.py`** - Database operations for tracking swap transactions

### Integration Points

- **`GCWebhook30/tph6.py`** - Modified to trigger ChangeNOW swaps after payment confirmation
- **`TelePay30/config_manager.py`** - Updated to fetch ChangeNOW and ETH wallet secrets
- **`GCWebhook30/requirements.txt`** - Added new dependencies (web3, eth-account, httpx)

## Required Environment Variables

### Google Secret Manager Secrets

```bash
CHANGENOW_API_KEY="projects/PROJECT_ID/secrets/CHANGENOW_API_KEY/versions/latest"
HOST_WALLET_ETH_ADDRESS="projects/PROJECT_ID/secrets/HOST_WALLET_ETH_ADDRESS/versions/latest"  
HOST_WALLET_PRIVATE_KEY="projects/PROJECT_ID/secrets/HOST_WALLET_PRIVATE_KEY/versions/latest"
```

### ChangeNOW API Key
Get your API key from: https://changenow.io/affiliate

### Ethereum Wallet
- **HOST_WALLET_ETH_ADDRESS**: The Ethereum address that receives payments from NowPayments
- **HOST_WALLET_PRIVATE_KEY**: Private key for signing ETH transactions (keep secure!)

## Workflow

1. **User Payment**: User pays via NowPayments → ETH deposited to host wallet
2. **Webhook Trigger**: `tph6.py` processes payment confirmation
3. **Channel Access**: User receives Telegram channel invite
4. **Payment Splitting**: Existing payment splitting to multiple wallets continues
5. **NEW - ChangeNOW Swap**: 
   - Calculate 30% of subscription price in USD
   - Convert USD amount to approximate ETH amount
   - Create ChangeNOW exchange: ETH → client's preferred currency
   - Send ETH from host wallet to ChangeNOW payin address
   - ChangeNOW sends converted crypto to client's wallet
   - Track swap status in database

## Database Schema

New table: `changenow_swaps`

```sql
CREATE TABLE changenow_swaps (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    order_id VARCHAR(255),
    exchange_id VARCHAR(255) UNIQUE,
    subscription_price_usd DECIMAL(10,2),
    swap_amount_usd DECIMAL(10,2),
    eth_amount_sent DECIMAL(18,8),
    target_currency VARCHAR(10),
    client_wallet_address VARCHAR(255),
    expected_output VARCHAR(50),
    eth_tx_hash VARCHAR(66),
    payin_address VARCHAR(255),
    swap_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);
```

## Error Handling

- **Non-blocking**: Swap failures won't prevent user access to paid channels
- **Graceful degradation**: System continues if ChangeNOW is unavailable
- **Comprehensive logging**: All operations logged with emoji patterns for easy debugging
- **Database tracking**: All swap attempts recorded for monitoring and troubleshooting

## Supported Currencies

The system supports any cryptocurrency that ChangeNOW supports for ETH swaps. Common examples:
- USDT, USDC, DAI (stablecoins)
- BTC, LTC (Bitcoin family)
- TRX, XRP, ADA (altcoins)
- Many others...

ETH is skipped (no swap needed since payment is already in ETH).

## Security Features

- Private key stored securely in Google Secret Manager
- Address validation before creating swaps
- Transaction signing with proper gas estimation
- Refund address set to host wallet for failed swaps
- Input validation and error handling throughout

## Monitoring

Check swap status via database queries:

```sql
-- Get recent swaps
SELECT * FROM changenow_swaps ORDER BY created_at DESC LIMIT 10;

-- Check swap statistics  
SELECT swap_status, COUNT(*) FROM changenow_swaps GROUP BY swap_status;

-- Find failed swaps
SELECT * FROM changenow_swaps WHERE swap_status = 'failed';
```

## Testing

1. **Testnet Testing**: Use Ethereum testnet for initial testing
2. **Small Amounts**: Start with small ETH amounts for production testing
3. **Error Simulation**: Test API failures, network issues, invalid addresses
4. **Monitoring**: Watch logs and database for successful swaps

## Deployment Notes

1. Update Docker containers with new requirements
2. Set environment variables in Cloud Run/GKE
3. Ensure Google Secret Manager secrets are configured
4. Monitor initial swaps for any issues
5. Set up alerting for failed swaps if desired