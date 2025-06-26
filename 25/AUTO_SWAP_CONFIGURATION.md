# Automatic Token Swapping Configuration

## Overview

The TelegramFunnel system now supports automatic ETH-to-token conversion using the 1INCH DEX aggregator. When the host wallet lacks sufficient tokens for client payouts, the system automatically swaps ETH to acquire the needed tokens.

## Required Configuration

### Core Requirements

1. **1INCH API Key**: Required for DEX operations
   - Obtain from [1inch Developer Portal](https://developers.1inch.io/)
   - Store in Google Cloud Secret Manager
   - Configure environment variable to point to Secret Manager path

2. **Host Wallet ETH Balance**: Sufficient ETH for gas + swapping
   - Minimum recommended: 0.05 ETH
   - System reserves minimum ETH for gas (configurable)

## Environment Variables

### Swap Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `SWAP_MAX_SLIPPAGE` | `1.0` | Maximum slippage percentage (1.0 = 1%) |
| `SWAP_MAX_ETH` | `0.1` | Maximum ETH per swap transaction |
| `SWAP_MIN_ETH_RESERVE` | `0.01` | Minimum ETH to keep for gas |
| `SWAP_TIMEOUT` | `30` | API timeout in seconds |
| `ENABLE_AUTO_SWAPPING` | `true` | Enable/disable automatic swapping |

### Example Configuration

```bash
# Google Cloud Run/Function environment variables

# Required: 1INCH API key from Secret Manager
1INCH_API_KEY=projects/291176869049/secrets/1INCH_API_KEY/versions/latest

# Optional swap parameters
SWAP_MAX_SLIPPAGE=1.5          # 1.5% slippage tolerance
SWAP_MAX_ETH=0.05              # Maximum 0.05 ETH per swap
SWAP_MIN_ETH_RESERVE=0.02      # Keep 0.02 ETH minimum
SWAP_TIMEOUT=45                # 45 second timeout
ENABLE_AUTO_SWAPPING=true      # Enable automatic swapping
```

## How Automatic Swapping Works

### Payment Flow with Auto-Swap

1. **Token Request**: Client needs LINK tokens for payout
2. **Balance Check**: System checks host wallet LINK balance
3. **Auto-Conversion**: If insufficient LINK:
   - Calculate required ETH amount
   - Verify sufficient ETH available (minus reserve)
   - Execute ETH → LINK swap via 1INCH
   - Confirm new LINK balance
4. **Token Transfer**: Send LINK tokens to client wallet

### Example Logs

```
📉 [INFO] TPS2_xxx: Insufficient LINK balance - attempting automatic conversion
💰 [INFO] TPS2_xxx: Need: 122.98 LINK, Have: 0.00 LINK
🔄 [INFO] TPS2_xxx: Attempting to swap ETH for 129.13 LINK
✅ [SUCCESS] TPS2_xxx: Automatically swapped ETH for LINK
🔗 [INFO] TPS2_xxx: Swap TX Hash: 0xabc123...
🪙 [INFO] TPS2_xxx: Updated LINK balance: 130.45 LINK
🪙 [INFO] TPS2_xxx: Sending 122.98 LINK to 0x742d35...
```

## Safety Features

### Automatic Protections

1. **ETH Reserve**: Always keeps minimum ETH for gas fees
2. **Swap Limits**: Maximum ETH per transaction prevents large losses
3. **Slippage Protection**: Limits price impact during swaps
4. **Timeout Protection**: Prevents hanging on slow API responses
5. **Balance Verification**: Confirms sufficient tokens after swap

### Error Handling

The system provides detailed error messages and suggestions:

```
❌ [ERROR] Failed to acquire sufficient LINK: Insufficient ETH for swapping
💡 [SUGGESTION] Add more ETH to host wallet for automatic swapping
⛽ [SUGGESTION] Current ETH: 0.005, Min reserve: 0.01
```

## Monitoring and Health Checks

### Health Check Endpoint

The `/health` endpoint now includes swap status:

```json
{
  "status": "healthy",
  "components": {
    "config_manager": true,
    "eth_converter": true,
    "wallet_manager": true,
    "dex_swapper": true,
    "auto_swapping": true
  },
  "wallet": {
    "balance_eth": 0.05,
    "balance_usd": "125.00"
  }
}
```

### Key Metrics to Monitor

1. **ETH Balance**: Ensure sufficient for operations
2. **Swap Success Rate**: Monitor failed swaps
3. **Gas Costs**: Track ETH consumption
4. **Slippage**: Monitor actual vs expected rates

## Troubleshooting

### Common Issues

#### 1. "DEX swapper not initialized"
- **Cause**: Missing or invalid 1INCH API key
- **Solution**: Check Secret Manager configuration
- **Check**: Verify `1INCH_API_KEY` environment variable

#### 2. "Insufficient ETH for swapping"
- **Cause**: Host wallet ETH below minimum reserve
- **Solution**: Add more ETH to host wallet
- **Formula**: Need at least `(swap_amount + gas_fees + min_reserve)` ETH

#### 3. "Swap amount exceeds maximum"
- **Cause**: Required tokens need more ETH than `SWAP_MAX_ETH`
- **Solution**: Increase `SWAP_MAX_ETH` or add tokens manually
- **Alternative**: Split large payments into smaller amounts

#### 4. "Swapping is disabled"
- **Cause**: `ENABLE_AUTO_SWAPPING=false`
- **Solution**: Set `ENABLE_AUTO_SWAPPING=true` or add tokens manually

### Manual Token Management

If auto-swapping is disabled or fails, manually add tokens:

```bash
# Example: Add LINK tokens to host wallet
# Send LINK to: 0xYourHostWalletAddress
# Minimum amount: Expected daily payout volume
```

## Cost Optimization

### Gas Optimization

1. **Batch Operations**: Process multiple payments together when possible
2. **Optimal Timing**: Execute swaps during low gas periods
3. **Reserve Management**: Maintain adequate reserves to avoid frequent small swaps

### Slippage Management

1. **Conservative Settings**: Start with 1% slippage, adjust as needed
2. **Market Monitoring**: Increase slippage during high volatility
3. **Volume Limits**: Use `SWAP_MAX_ETH` to limit exposure

## Security Considerations

### Best Practices

1. **API Key Security**: Store 1INCH API key in Secret Manager only
2. **Wallet Security**: Use dedicated host wallet for operations
3. **Monitoring**: Set up alerts for unusual swap activity
4. **Limits**: Configure reasonable swap limits to prevent abuse

### Risk Mitigation

1. **Limited Exposure**: `SWAP_MAX_ETH` limits maximum loss per transaction
2. **ETH Reserve**: Ensures system remains operational even after swaps
3. **Timeout Protection**: Prevents hanging on failed API calls
4. **Validation**: Multiple checks before executing swaps

## Migration from Manual Token Management

### Step 1: Test Configuration
```bash
# Start with conservative settings
SWAP_MAX_ETH=0.01
SWAP_MIN_ETH_RESERVE=0.02
ENABLE_AUTO_SWAPPING=true
```

### Step 2: Monitor Initial Operations
- Watch logs for successful swaps
- Verify token balances after swaps
- Check gas consumption patterns

### Step 3: Optimize Settings
- Adjust slippage based on success rates
- Increase swap limits if needed
- Fine-tune ETH reserve amounts

### Step 4: Full Production
- Remove manual token additions
- Set up monitoring alerts
- Document operational procedures

## Support and Maintenance

### Regular Maintenance

1. **ETH Balance**: Monitor and top up regularly
2. **API Key**: Rotate 1INCH API key periodically
3. **Configuration**: Review swap parameters monthly
4. **Logs**: Check for unusual patterns or errors

### Emergency Procedures

1. **Disable Auto-Swap**: Set `ENABLE_AUTO_SWAPPING=false`
2. **Manual Operation**: Add tokens directly to host wallet
3. **Service Restart**: Restart TPS2 service if needed
4. **Rollback**: Revert to previous configuration if issues arise