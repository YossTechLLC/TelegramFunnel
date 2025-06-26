# Currency Configuration Guide

## Overview

The TelegramFunnel system supports multi-token payments using ERC20 tokens and ETH. The `client_payout_currency` field in the database determines which token will be sent to clients as their 30% payout.

## Supported Tokens

### Ethereum Mainnet (Chain ID: 1)
- **ETH** - Native Ethereum (default)
- **USDT** - Tether USD (Stablecoin)
- **USDC** - USD Coin (Stablecoin) 
- **DAI** - Dai Stablecoin
- **WETH** - Wrapped Ether
- **LINK** - Chainlink Token
- **UNI** - Uniswap Token
- **AAVE** - Aave Token
- **COMP** - Compound Token
- **MATIC** - Polygon Token
- **SHIB** - Shiba Inu Token

### Other Networks
- **Polygon (Chain ID: 137)**: USDT, USDC, WETH, WMATIC
- **BSC (Chain ID: 56)**: USDT, USDC, WBNB

## Database Configuration

### client_payout_currency Field

The `client_payout_currency` field in the `main_clients_database` table controls which token clients receive:

```sql
-- Valid examples
INSERT INTO main_clients_database (..., client_payout_currency) VALUES (..., 'ETH');
INSERT INTO main_clients_database (..., client_payout_currency) VALUES (..., 'LINK');
INSERT INTO main_clients_database (..., client_payout_currency) VALUES (..., 'USDT');
```

### ⚠️ Common Issues

**Problem**: Records with `client_payout_currency = "USD"` will cause ETH to be sent instead of the intended token.

**Cause**: "USD" is not a valid token symbol - it's a fiat currency, not a blockchain token.

**Solution**: Use the migration utility to fix invalid records.

## Migration Utility

### Check Current Currency Distribution

```bash
cd TelePay25/
python currency_migration_utility.py --check
```

This will show you all currency values in your database and identify invalid ones.

### Migrate USD Records to Valid Tokens

```bash
# Dry run (simulate changes)
python currency_migration_utility.py --migrate --target LINK --dry-run

# Actually migrate USD to LINK
python currency_migration_utility.py --migrate --target LINK

# Migrate USD to ETH (safe default)
python currency_migration_utility.py --migrate --target ETH
```

## Payment Flow

### How Currency Selection Works

1. **Database Lookup**: When a payment is initiated, the system looks up `client_payout_currency` from the database
2. **Token Validation**: The currency is validated against the token registry
3. **Payment Processing**: 
   - If valid token: Converts USD amount to token and sends to client wallet
   - If invalid token: Falls back to ETH (causing the issue you experienced)

### Example Flow for LINK Payments

```
1. Database: client_payout_currency = "LINK"
2. Payment: $15.00 USD subscription 
3. Client Share: $4.50 USD (30% of $15.00)
4. Conversion: $4.50 USD → X LINK tokens
5. Transfer: Send X LINK tokens to client wallet
```

## Validation Rules

- Currency symbols must be uppercase (ETH, LINK, USDT)
- Must be supported in the token registry
- Cannot be fiat currencies (USD, EUR, etc.)
- Cannot be empty or NULL

## Debugging Currency Issues

### Enhanced Logging

The system now provides detailed logging for currency operations:

```
🔍 [DEBUG] Looking up wallet info for open_channel_id: -1001234567890
💰 [DEBUG] fetch_client_wallet_info raw result: ('0x742d35Cc6635C0532925a3b8D', 'LINK')
🏦 [DEBUG] Retrieved wallet_address: '0x742d35Cc6635C0532925a3b8D'
💱 [DEBUG] Retrieved payout_currency: 'LINK'
✅ [DEBUG] Payout currency 'LINK' is valid
```

### Warning Signs

Look for these warnings in your logs:

```
❌ [WARNING] Payout currency 'USD' is INVALID: Unsupported token 'USD'. Supported tokens: ETH, USDT, USDC, DAI, LINK, UNI, AAVE, COMP, MATIC, SHIB
⚠️ [WARNING] This will likely cause payment flow issues!
```

## Best Practices

### For New Channel Configurations

1. Always specify a valid `client_payout_currency` when creating channels
2. Use token symbols, not fiat currency codes
3. Test with small amounts first

### For Existing Deployments

1. Run the currency check utility to audit your database
2. Migrate any USD records to appropriate tokens
3. Monitor logs for validation warnings

### Recommended Token Choices

- **ETH**: Safe default, always available
- **USDT/USDC**: Stable value, good for predictable payouts
- **LINK**: Popular utility token
- **Other tokens**: Choose based on client preferences

## Troubleshooting

### Issue: ETH sent instead of intended token

**Diagnosis**: Run currency check utility
```bash
python currency_migration_utility.py --check
```

**Fix**: Migrate invalid currencies
```bash
python currency_migration_utility.py --migrate --target LINK
```

### Issue: "Token not supported" error

**Cause**: Currency not in token registry
**Solution**: Use a supported token from the list above

### Issue: Empty/NULL currency

**Cause**: Missing client_payout_currency in database
**Solution**: Update record with valid token symbol

## Environment Requirements

- Token Registry must be available
- Database connection configured
- ERC20 wallet with sufficient token balances
- 1INCH API access for conversions

## Support

For issues with currency configuration:

1. Check the logs for validation warnings
2. Run the currency migration utility
3. Verify token registry is properly initialized
4. Ensure database has valid token symbols only