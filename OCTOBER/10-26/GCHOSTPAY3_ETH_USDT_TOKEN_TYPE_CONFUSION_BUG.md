# GCHostPay3 ETH/USDT Token Type Confusion Bug

**Date**: 2025-11-04
**Severity**: CRITICAL
**Status**: Analysis Complete

## Executive Summary

GCHostPay3 is attempting to send **native ETH** to ChangeNow payin addresses when it should be sending **USDT (ERC-20 tokens)**. This causes "insufficient funds" errors because the wallet tries to send 3.116936 ETH (~$7,800) instead of 3.116936 USDT (~$3.12).

## Bug Evidence

### Actual Error Logs
```
2025-11-04 04:46:29.701 EST
💰 [ENDPOINT] PAYMENT AMOUNT: 3.11693635 ETH  ❌ WRONG!
🏦 [ENDPOINT] Payin Address: 0x459b9C28A8e266d59Ff57A8206730A4a264d5A2e
💰 [WALLET] Current balance: 0.001161551275950277 ETH (1161551275950277 Wei)
❌ [ENDPOINT] Insufficient funds: need 3.11693635 ETH, have 0.001161551275950277 ETH
```

### Expected ChangeNow API Response
```json
{
    "id": "90aa16e18218ec",
    "status": "waiting",
    "fromCurrency": "usdt",        ✅ Should send USDT
    "fromNetwork": "eth",          ✅ ERC-20 on Ethereum
    "toCurrency": "shib",
    "expectedAmountFrom": 3.116936, ✅ 3.116936 USDT (~$3.12)
    "payinAddress": "0x459b9C28A8e266d59Ff57A8206730A4a264d5A2e"
}
```

**What we should send**: 3.116936 USDT (ERC-20 token transfer)
**What we're actually sending**: 3.116936 ETH (native currency transfer)
**Cost difference**: ~$7,800 vs ~$3.12 (2,500x error!)

---

## Root Cause Analysis

### Architecture Flow

```
User Payment (Any Crypto)
    ↓
NowPayments (converts to USDT, sends to platform wallet)
    ↓
GCWebhook1 → GCSplit1 (creates ChangeNow USDT→SHIB exchange)
    ↓
GCHostPay1 (orchestrator)
    ↓
GCHostPay2 (status check)
    ↓
GCHostPay1 (verified)
    ↓
GCHostPay3 (payment executor) ❌ BUG HERE
    ↓
ChangeNow (should receive USDT, but system tries to send ETH)
```

### Token Data Flow

**1. GCSplit1 → GCHostPay1**
```python
# GCSplit1 builds token with:
from_currency = "usdt"           ✅ Correctly identifies USDT
from_network = "eth"             ✅ Correctly identifies ERC-20
from_amount = 3.116936           ✅ Correct amount
payin_address = "0x459b9..."    ✅ ChangeNow address
```

**2. GCHostPay1 → GCHostPay3** (tphp1-10-26.py:544-552)
```python
# GCHostPay1 passes through unchanged:
encrypted_token_payment = token_manager.encrypt_gchostpay1_to_gchostpay3_token(
    unique_id=unique_id,
    cn_api_id=cn_api_id,
    from_currency=from_currency,      # "usdt" ✅
    from_network=from_network,        # "eth" ✅
    from_amount=from_amount,          # 3.116936 ✅
    payin_address=payin_address,
    context=context
)
```

**3. GCHostPay3 Decryption** (tphp3-10-26.py:152-186)
```python
# GCHostPay3 correctly decrypts:
from_currency = decrypted_data['from_currency']      # "usdt" ✅
from_network = decrypted_data['from_network']        # "eth" ✅
from_amount = decrypted_data.get('from_amount', 0.0) # 3.116936 ✅
payin_address = decrypted_data['payin_address']     # "0x459b9..." ✅

# BUT THEN:
payment_amount = from_amount  # Treats this as ETH! ❌

print(f"💰 [ENDPOINT] PAYMENT AMOUNT: {payment_amount} ETH")  # ❌ WRONG LABEL!
```

**4. GCHostPay3 Wallet Execution** (tphp3-10-26.py:233)
```python
# Calls ETH transfer method:
tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
    to_address=payin_address,
    amount=payment_amount,  # ❌ This is USDT amount, not ETH!
    unique_id=unique_id
)
```

**5. WalletManager** (wallet_manager.py:146-274)
```python
def send_eth_payment_with_infinite_retry(self, to_address: str, amount: float, unique_id: str):
    """
    ❌ This function ONLY sends native ETH!
    ❌ It uses Web3 eth.send_transaction() for native transfers
    ❌ It does NOT use ERC-20 contract calls
    """
    amount_wei = self.w3.to_wei(amount, 'ether')  # ❌ Converts USDT amount to ETH Wei!

    transaction = {
        'nonce': nonce,
        'to': to_address_checksum,
        'value': amount_wei,  # ❌ Native ETH transfer!
        'gas': 21000,         # ❌ Native ETH gas (ERC-20 needs 60000+)
        ...
    }
```

---

## The Three Critical Problems

### Problem 1: Currency Type Confusion

**Current Behavior**:
- System extracts `from_currency = "usdt"` correctly
- But immediately ignores it and treats ALL amounts as ETH
- All logging says "ETH" regardless of actual currency

**Evidence**:
```python
# tphp3-10-26.py:194
print(f"💰 [ENDPOINT] PAYMENT AMOUNT: {payment_amount} ETH")  # ❌ Should check from_currency!
```

### Problem 2: Missing Token Awareness

**Current Wallet Manager**:
- Only has `send_eth_payment_with_infinite_retry()` method
- Sends native ETH using `value` field in transaction
- Uses 21000 gas (native transfer gas limit)

**What We Need**:
- `send_erc20_token()` method
- ERC-20 contract ABI and address
- Contract function call: `transfer(recipient, amount)`
- 60000+ gas limit for token transfers

### Problem 3: No ERC-20 Transfer Logic

**Native ETH Transfer** (current):
```python
transaction = {
    'to': recipient_address,
    'value': amount_in_wei,  # Native ETH
    'gas': 21000
}
```

**ERC-20 Token Transfer** (required):
```python
# Load USDT contract
usdt_contract = w3.eth.contract(address=USDT_ADDRESS, abi=ERC20_ABI)

# Build transfer transaction
transaction = usdt_contract.functions.transfer(
    recipient_address,
    amount_in_smallest_unit  # USDT has 6 decimals, not 18!
).build_transaction({
    'from': wallet_address,
    'gas': 100000,  # Higher gas for contract call
    'gasPrice': gas_price,
    'nonce': nonce
})
```

---

## Impact Analysis

### Current System Failure

1. **Instant Payouts (NowPayments → ChangeNow)**:
   - User pays in any crypto
   - NowPayments converts to USDT
   - System tries to send ETH to ChangeNow ❌ FAILS
   - Transaction fails with "insufficient funds"
   - User never gets invite to channel

2. **Batch Conversions**:
   - Multiple user payments accumulate as USDT
   - GCMicroBatchProcessor creates ChangeNow USDT→SHIB exchange
   - System tries to send ETH ❌ FAILS
   - Entire batch fails

3. **Threshold Payouts**:
   - GCAccumulator accumulates USDT until threshold
   - Creates ChangeNow USDT→target_token exchange
   - System tries to send ETH ❌ FAILS
   - Threshold payout never executes

### Financial Risk

**If the bug were not caught**:
- Wallet tries to send 3.116936 ETH instead of 3.116936 USDT
- 3.116936 ETH ≈ $7,800 (at $2,500/ETH)
- 3.116936 USDT ≈ $3.12
- **Overpayment risk**: 2,500x the intended amount!

**Good news**: Wallet has insufficient ETH (0.0011 ETH), so transaction fails safely rather than overpaying.

---

## Solution Architecture

### Required Changes

#### 1. Add ERC-20 Token Support to WalletManager

**New Method**:
```python
def send_erc20_token(
    self,
    token_contract_address: str,
    to_address: str,
    amount: float,
    token_decimals: int,
    unique_id: str
) -> Optional[Dict[str, Any]]:
    """
    Send ERC-20 token (USDT, USDC, etc.) to address.

    Args:
        token_contract_address: ERC-20 contract address (e.g., USDT: 0xdac17f958d2ee523a2206206994597c13d831ec7)
        to_address: Recipient address
        amount: Token amount (human-readable, e.g., 3.116936 USDT)
        token_decimals: Token decimal places (USDT=6, USDC=6, DAI=18)
        unique_id: Transaction tracking ID

    Returns:
        Transaction result dict or None
    """
```

**Token Contract Addresses** (Ethereum Mainnet):
- USDT: `0xdac17f958d2ee523a2206206994597c13d831ec7` (6 decimals)
- USDC: `0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48` (6 decimals)
- DAI: `0x6b175474e89094c44da98b954eedeac495271d0f` (18 decimals)

**ERC-20 ABI** (minimal):
```python
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]
```

#### 2. Update GCHostPay3 Payment Logic

**Before**:
```python
# tphp3-10-26.py:233
tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
    to_address=payin_address,
    amount=payment_amount,
    unique_id=unique_id
)
```

**After**:
```python
# Determine payment method based on currency
if from_currency.lower() == 'eth':
    # Native ETH transfer
    print(f"💰 [ENDPOINT] Sending native ETH: {payment_amount} ETH")
    tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
        to_address=payin_address,
        amount=payment_amount,
        unique_id=unique_id
    )

elif from_currency.lower() in ['usdt', 'usdc', 'dai']:
    # ERC-20 token transfer
    token_config = {
        'usdt': {
            'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'decimals': 6
        },
        'usdc': {
            'address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            'decimals': 6
        },
        'dai': {
            'address': '0x6b175474e89094c44da98b954eedeac495271d0f',
            'decimals': 18
        }
    }

    token = token_config[from_currency.lower()]
    print(f"💰 [ENDPOINT] Sending ERC-20 token: {payment_amount} {from_currency.upper()}")
    print(f"📝 [ENDPOINT] Token contract: {token['address']}")

    tx_result = wallet_manager.send_erc20_token(
        token_contract_address=token['address'],
        to_address=payin_address,
        amount=payment_amount,
        token_decimals=token['decimals'],
        unique_id=unique_id
    )

else:
    raise ValueError(f"Unsupported currency: {from_currency}")
```

#### 3. Fix Logging Throughout Stack

**Update all log statements**:
```python
# Before:
print(f"💰 [ENDPOINT] PAYMENT AMOUNT: {payment_amount} ETH")

# After:
print(f"💰 [ENDPOINT] PAYMENT AMOUNT: {payment_amount} {from_currency.upper()}")
```

#### 4. Add Balance Checking for ERC-20 Tokens

**New WalletManager Method**:
```python
def get_erc20_balance(self, token_contract_address: str, token_decimals: int) -> float:
    """Get ERC-20 token balance for wallet."""
    contract = self.w3.eth.contract(
        address=Web3.to_checksum_address(token_contract_address),
        abi=ERC20_ABI
    )

    balance_raw = contract.functions.balanceOf(self.wallet_address).call()
    balance = balance_raw / (10 ** token_decimals)

    return float(balance)
```

**Update balance check in GCHostPay3**:
```python
# Check balance based on currency type
if from_currency.lower() == 'eth':
    wallet_balance = wallet_manager.get_wallet_balance()
    balance_label = "ETH"
else:
    token_config = TOKEN_CONFIGS[from_currency.lower()]
    wallet_balance = wallet_manager.get_erc20_balance(
        token_config['address'],
        token_config['decimals']
    )
    balance_label = from_currency.upper()

if wallet_balance < payment_amount:
    error_msg = f"Insufficient funds: need {payment_amount} {balance_label}, have {wallet_balance} {balance_label}"
    print(f"❌ [ENDPOINT] {error_msg}")
    abort(400, error_msg)
```

---

## Implementation Checklist

### Phase 1: Core Token Support (HIGH PRIORITY)

- [ ] **1.1** Add ERC-20 ABI to wallet_manager.py
  - Define minimal ERC-20 ABI (transfer, balanceOf, decimals)
  - Add as module-level constant

- [ ] **1.2** Create token configuration map
  - USDT, USDC, DAI contract addresses
  - Decimal places for each token
  - Store in config_manager or as constant

- [ ] **1.3** Implement `send_erc20_token()` method
  - Accept token_contract_address, amount, decimals
  - Load contract with ABI
  - Build transfer transaction
  - Sign and broadcast
  - Wait for confirmation
  - Return tx_receipt

- [ ] **1.4** Implement `get_erc20_balance()` method
  - Query balanceOf() for wallet address
  - Convert from smallest unit to human-readable
  - Return float balance

### Phase 2: GCHostPay3 Integration (HIGH PRIORITY)

- [ ] **2.1** Add currency type detection in main endpoint
  - Extract `from_currency` from token
  - Validate against supported currencies
  - Choose payment method (native ETH vs ERC-20)

- [ ] **2.2** Update balance checking logic
  - Check ETH balance for ETH payments
  - Check ERC-20 balance for token payments
  - Use correct currency label in logs

- [ ] **2.3** Update payment execution logic
  - Route to `send_eth_payment()` for ETH
  - Route to `send_erc20_token()` for tokens
  - Pass correct parameters for each type

- [ ] **2.4** Fix all logging statements
  - Replace hardcoded "ETH" with `{from_currency.upper()}`
  - Add token contract address to logs
  - Log decimals for debugging

### Phase 3: Testing & Validation (CRITICAL)

- [ ] **3.1** Test native ETH transfers (regression test)
  - Verify existing ETH flow still works
  - Check gas estimation
  - Verify transaction confirmation

- [ ] **3.2** Test USDT transfers (new functionality)
  - Test with small amount first (0.01 USDT)
  - Verify correct contract called
  - Check ChangeNow receives funds
  - Verify gas costs reasonable

- [ ] **3.3** Test other tokens (USDC, DAI)
  - Verify decimal handling (6 vs 18)
  - Check contract interactions
  - Validate balance queries

- [ ] **3.4** Test error conditions
  - Insufficient token balance
  - Unsupported currency
  - Invalid contract address
  - Network congestion/high gas

### Phase 4: Error Handling & Resilience (MEDIUM PRIORITY)

- [ ] **4.1** Add retry logic for ERC-20 transfers
  - Mirror ETH retry strategy (3 attempts)
  - Handle gas price fluctuations
  - Implement replacement transactions

- [ ] **4.2** Add transaction validation
  - Verify token transfer event emitted
  - Check recipient balance increased
  - Log discrepancies

- [ ] **4.3** Improve error messages
  - Distinguish ETH vs token errors
  - Provide actionable debugging info
  - Log contract call failures clearly

- [ ] **4.4** Add alerting for token issues
  - Low token balance warnings
  - Failed token transfer alerts
  - Contract interaction errors

### Phase 5: Configuration & Deployment (MEDIUM PRIORITY)

- [ ] **5.1** Move token config to Secret Manager
  - USDT_CONTRACT_ADDRESS
  - USDC_CONTRACT_ADDRESS
  - DAI_CONTRACT_ADDRESS
  - Support adding new tokens easily

- [ ] **5.2** Add token type validation
  - Whitelist supported tokens
  - Reject unsupported currencies early
  - Log unsupported token attempts

- [ ] **5.3** Deploy to staging first
  - Test with testnet contracts
  - Verify end-to-end flow
  - Monitor for issues

- [ ] **5.4** Deploy to production
  - Gradual rollout
  - Monitor error rates
  - Have rollback plan ready

---

## Verification Checklist

After implementing fixes, verify:

### Unit Tests
- [ ] `send_erc20_token()` successfully transfers USDT
- [ ] `get_erc20_balance()` returns correct balance
- [ ] Native ETH transfers still work (regression)
- [ ] Currency type detection works correctly
- [ ] Balance checks use correct currency type

### Integration Tests
- [ ] Full flow: NowPayments → GCWebhook1 → GCSplit1 → GCHostPay1 → GCHostPay3 → ChangeNow
- [ ] Token transferred to correct address
- [ ] ChangeNow confirms receipt
- [ ] User receives Telegram invite

### Production Monitoring
- [ ] Check logs for "PAYMENT AMOUNT" showing correct currency
- [ ] Verify no "insufficient funds" errors for token transfers
- [ ] Monitor ChangeNow exchange completion rate
- [ ] Track gas costs for token transfers

---

## Related System Components

### Other Services That May Need Updates

**GCHostPay1** (tphp1-10-26.py):
- ✅ Already passes `from_currency` correctly
- ✅ No changes needed (orchestrator only)

**GCHostPay2** (status checker):
- ✅ Already passes `from_currency` in token
- ✅ No changes needed

**GCSplit1** (tps1-10-26.py):
- ✅ Already creates correct ChangeNow exchanges
- ✅ Already passes `from_currency="usdt"` correctly
- ✅ No changes needed

**GCAccumulator** (threshold payouts):
- ✅ Should already be passing `from_currency`
- ⚠️ Verify after GCHostPay3 fix deployed

**GCMicroBatchProcessor** (batch conversions):
- ✅ Should already be passing `from_currency`
- ⚠️ Verify after GCHostPay3 fix deployed

**Database Schema**:
- ✅ `from_currency` field already exists in all tables
- ✅ No schema changes needed

---

## Security Considerations

### Private Key Security
- WalletManager already handles private keys securely
- Same security model applies to ERC-20 transfers
- No additional exposure

### Contract Interaction Risks
- Use well-known, audited token contracts (USDT, USDC, DAI)
- Validate contract addresses against known mainnet addresses
- Consider adding contract bytecode verification

### Gas Price Manipulation
- Implement max gas price limits
- Monitor for unusual gas costs
- Alert on abnormal transaction fees

### Token Approval Attack Surface
- Use direct `transfer()` calls, not `approve()` pattern
- No need for token approvals in this architecture
- Reduces attack surface

---

## Testing Strategy

### Testnet Testing (Before Production)

**Goerli/Sepolia Testnet**:
1. Deploy test USDT contract or use existing testnet USDT
2. Fund wallet with test ETH for gas
3. Fund wallet with test USDT
4. Create test ChangeNow exchange (if testnet API available)
5. Execute full payment flow
6. Verify transaction on Etherscan testnet

### Production Testing (After Deployment)

**Small Amount Test**:
1. Create real ChangeNow exchange for small amount (0.01 USDT)
2. Trigger payment via GCHostPay3
3. Monitor transaction on Etherscan mainnet
4. Verify ChangeNow receives funds
5. Verify exchange completes
6. Check user receives invite

**Gradual Rollout**:
1. Deploy to production with feature flag
2. Route 10% of traffic to new code
3. Monitor for 24 hours
4. Increase to 50% if stable
5. Full rollout after 48 hours

---

## Rollback Plan

If critical issues discovered after deployment:

1. **Immediate**: Disable GCHostPay3 processing
   - Set feature flag to false
   - Queue all pending payments
   - No user impact (payments queued)

2. **Revert**: Deploy previous GCHostPay3 version
   - Revert to ETH-only code
   - Process queued ETH payments
   - USDT payments remain queued

3. **Debug**: Investigate issues offline
   - Analyze failed transactions
   - Review error logs
   - Test fixes in staging

4. **Redeploy**: Fixed version
   - Retest thoroughly
   - Deploy with gradual rollout
   - Process queued USDT payments

---

## Future Enhancements

### Multi-Token Support
- Add support for more ERC-20 tokens (USDC, DAI, WBTC, etc.)
- Dynamic token configuration
- Automatic token detection from ChangeNow API

### Gas Optimization
- Batch multiple token transfers
- Use EIP-1559 gas optimization
- Implement gas price oracles

### Cross-Chain Support
- Support tokens on other networks (Polygon, BSC, Arbitrum)
- Multi-network RPC configuration
- Network-specific gas strategies

### Monitoring & Analytics
- Token transfer success rates
- Average gas costs per token type
- Token balance monitoring alerts
- ChangeNow exchange completion rates

---

## Conclusion

This is a **critical bug** that prevents the entire payment flow from working when NowPayments converts user payments to USDT. The system currently tries to send native ETH instead of USDT tokens, causing all transactions to fail with "insufficient funds."

**The fix is straightforward**:
1. Add ERC-20 token transfer capability to WalletManager
2. Update GCHostPay3 to route based on currency type
3. Fix logging to show correct currency

**Impact**: Once fixed, the entire payment flow will work correctly for USDT payments, which is the primary use case since NowPayments outputs USDT.

**Risk**: Low risk if implemented carefully with proper testing. The changes are isolated to payment execution and don't affect orchestration logic.

**Timeline**: Should be prioritized immediately as this blocks the core payment functionality of the platform.
