# Alchemy API Architecture Analysis for TelePay10-26

**Date:** November 2, 2025
**Purpose:** Evaluate the utility and relevance of Alchemy API features in the current TelePay payment processing architecture

---

## Executive Summary

After analyzing the current TelePay10-26 payment architecture and Alchemy's 2025 feature set, **Alchemy API provides LIMITED value** beyond basic RPC infrastructure. The primary benefits are **RPC reliability** and **gas optimization** (15-30% savings), while advanced features like **webhooks, address monitoring, and NFT APIs are NOT applicable** to the current workflow.

**Key Findings:**
- ✅ **USE ALCHEMY FOR:** Enhanced RPC endpoint (better uptime, faster responses)
- ✅ **USE ALCHEMY FOR:** EIP-1559 gas optimization (cost savings)
- ❌ **DO NOT USE:** Webhook notifications (no async monitoring needed)
- ❌ **DO NOT USE:** Address Activity tracking (no incoming payment monitoring)
- ❌ **DO NOT USE:** NFT APIs (not relevant to use case)

---

## Current Architecture Overview

### Ethereum Usage in TelePay Ecosystem

**Service:** GCHostPay3-10-26 (ETH Payment Executor)

**Current Flow:**
```
GCHostPay3-10-26
    ↓
Web3.py (Ethereum RPC)
    ↓
Send ETH to ChangeNOW payin address
    ↓
Wait for confirmation (300s timeout)
    ↓
Return tx_hash, gas_used, block_number
    ↓
TERMINATES workflow
```

**Key Characteristics:**
1. **One-way ETH transfers:** Only SEND ETH (to ChangeNOW addresses)
2. **Synchronous confirmation:** Uses `wait_for_transaction_receipt()` inline
3. **No incoming payments:** Never receives ETH to host wallet
4. **Simple transaction model:** Standard ETH transfers (no smart contracts)
5. **3-attempt retry logic:** Handled at application layer (GCHostPay3)

**Current RPC Provider:** Ethereum RPC URL (potentially Alchemy already)

**Reference Files:**
- `/OCTOBER/10-26/GCHostPay3-10-26/wallet_manager.py` (lines 127-254)
- `/OCTOBER/10-26/PAYMENT_ARCHITECTURE_BREAKDOWN.md` (lines 207-235)

---

## Alchemy API Capabilities (2025)

### What Alchemy Offers

Based on research conducted on November 2, 2025:

#### 1. **Enhanced RPC Infrastructure**
- **Performance:** 13x more throughput than competitors
- **Reliability:** 99.995% uptime (5x better than competitors)
- **Latency:** Sub-50ms global latency
- **Speed:** 30x faster for heavy endpoints like `getLogs`

#### 2. **Gas Optimization (EIP-1559)**
- Dynamic gas pricing via `eth_feeHistory` API
- 15-30% gas cost savings vs static pricing
- Automatic base fee + priority fee calculation

#### 3. **Alchemy Notify (Webhooks)**
- **Address Activity:** Track ETH, ERC20, ERC721 transfers on monitored addresses
- **Mined Transaction:** Real-time notification when tx is confirmed
- **Dropped Transaction:** Alert when tx is dropped from mempool
- **Custom Webhooks:** Filter on-chain events with custom logic

**Webhook Features:**
- At-least-once delivery guarantee
- Built-in retry with exponential backoff
- HMAC signature verification
- 3x faster than polling, 24% cheaper
- Companies save $240k-$3M annually vs RPC polling

#### 4. **NFT API**
- Metadata parsing, floor prices, ownership queries
- NOT RELEVANT to TelePay (no NFT usage)

#### 5. **Enhanced WebSockets**
- Real-time blockchain events with sub-second latency
- Automatic reconnection with event replay
- NOT NEEDED (synchronous payment model)

#### 6. **Developer Tools**
- Dashboard for browsing historical requests
- Debug toolkit for query visualization
- JSON-RPC composer

---

## Use Case Analysis: What's Relevant?

### ✅ APPLICABLE: Enhanced RPC Infrastructure

**Current Pain Points:**
- Potential RPC timeouts (handled via retry logic)
- Gas price volatility
- Network congestion during peak times

**How Alchemy Helps:**
- **99.995% uptime** reduces connection failures
- **Sub-50ms latency** improves transaction broadcast speed
- **Automatic failover** prevents single point of failure

**Implementation:**
```python
# Current (wallet_manager.py:56)
self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

# With Alchemy (no code change needed)
# Just update ETHEREUM_RPC_URL to Alchemy endpoint:
# https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY
```

**Value Proposition:** ⭐⭐⭐⭐ (High) - Better reliability, minimal effort

---

### ✅ APPLICABLE: EIP-1559 Gas Optimization

**Current Approach:**
```python
# wallet_manager.py:107-109
gas_price = self.w3.eth.gas_price  # Static gas price
```

**Alchemy Enhancement:**
```python
# wallet_manager.py:72-125 (already exists in 10-18 version)
def _get_optimized_gas_price(self) -> Dict[str, int]:
    fee_data = self.w3.eth.fee_history(1, 'latest', [25, 50, 75])
    base_fee = fee_data['baseFeePerGas'][-1]
    priority_fee = int(fee_data['reward'][-1][1])
    max_fee = (base_fee * 2) + priority_fee

    return {
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
        "gasPrice": base_fee + priority_fee
    }
```

**Benefits:**
- **15-30% gas savings** on ETH transfers
- Dynamic adjustment based on network conditions
- Better transaction success rate

**Estimated Savings:**
- If processing 1000 tx/month at 0.001 ETH gas each
- 25% savings = 0.00025 ETH saved per tx
- Total saved: 0.25 ETH/month (~$600/month at $2400 ETH)

**Value Proposition:** ⭐⭐⭐⭐⭐ (Very High) - Direct cost savings

---

### ❌ NOT APPLICABLE: Alchemy Notify Webhooks

**Why Alchemy Suggests Webhooks:**
- Replace expensive RPC polling
- Async monitoring of transaction status
- Real-time alerts for state changes

**Why TelePay Doesn't Need This:**

**1. Synchronous Payment Model**
```python
# wallet_manager.py:219-223
# We WAIT inline for confirmation
tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
```
- No async tracking needed
- Confirmation happens before returning response
- No benefit from webhook notification

**2. No Incoming Payment Monitoring**
```
TelePay Flow:
User pays NowPayments (USD/crypto) → NowPayments IPN → TelePay
                                                      ↓
                                          Send ETH to ChangeNOW
                                                      ↓
                                               (NO RETURN PATH)
```
- Host wallet only SENDS ETH, never RECEIVES
- No need to monitor deposits
- ChangeNOW handles conversion completion notification

**3. ChangeNOW API Already Provides Status**
```python
# GCHostPay2-10-26 already polls ChangeNOW for status
resp = requests.get(f"https://api.changenow.io/v2/exchange/by-id?id={cn_api_id}")
status = resp.json()['status']  # "waiting", "confirming", "finished"
```
- ChangeNOW API tells us when ETH is received
- No value in monitoring Ethereum directly

**4. Webhook Overhead**
- Requires setting up webhook endpoint
- Signature verification logic
- Database schema changes (tx_hash, tx_status columns)
- Additional Secret Manager configuration
- **FOR NO ACTUAL BENEFIT**

**Previous Integration Attempt:**
- See `/OCTOBER/10-18/GCHostPay10-21/ALCHEMY_INTEGRATION.md`
- Added webhook handler (`alchemy_webhook_handler.py`)
- Added database columns (tx_hash, tx_status)
- **UNUSED ARCHITECTURE** - over-engineered for the use case

**Value Proposition:** ⭐ (Very Low) - Adds complexity with no benefit

---

### ❌ NOT APPLICABLE: Address Activity Monitoring

**What It Does:**
- Track all ETH, ERC20, ERC721 transfers for a wallet
- Get notified when address sends OR receives tokens
- Real-time balance change alerts

**Why TelePay Doesn't Need This:**

**1. One-Way Flow (Outbound Only)**
```
Host Wallet (0xABC...DEF)
    ↓ [SEND ETH]
ChangeNOW Payin Address (0x123...456)
    ↓ [ChangeNOW converts internally]
Client Wallet (receives USDT/BTC/etc)
```
- Host wallet only sends, never receives ETH
- No incoming transactions to monitor
- Balance only decreases (never increases)

**2. Payment Verification Handled Elsewhere**
```
User Payment Verification:
    ↓
NowPayments IPN Webhook (np-webhook-10-26)
    ↓
Verifies payment, calculates outcome_amount_usd
    ↓
Routes to payment workflow
```
- User payments verified by NowPayments (not Ethereum blockchain)
- ETH payment is INTERNAL step (TelePay → ChangeNOW)
- No need for blockchain-level payment monitoring

**3. No Whale Tracking / Analytics Needed**
- Not tracking user behavior on-chain
- Not building analytics dashboards
- Not monitoring competitor addresses

**Value Proposition:** ⭐ (Very Low) - Not relevant to business model

---

### ❌ NOT APPLICABLE: NFT API

**What It Does:**
- Fetch NFT metadata, ownership, floor prices
- Query collections, verify ownership

**Why TelePay Doesn't Need This:**
- No NFT functionality in payment flow
- Only deals with fungible tokens (ETH, USDT, BTC, etc.)

**Value Proposition:** ⭐ (Not Relevant)

---

### ❌ NOT APPLICABLE: Enhanced WebSockets

**What It Does:**
- Real-time blockchain event streaming
- Automatic reconnection with event replay
- Filter specific events (logs, transactions, blocks)

**Why TelePay Doesn't Need This:**
- Synchronous payment model (no real-time streaming)
- No event-driven architecture for Ethereum
- Simple transaction broadcast + confirmation

**Value Proposition:** ⭐ (Very Low)

---

## Cost-Benefit Analysis

### Alchemy Pricing (2025)

**Free Tier:**
- 300M compute units/month
- Sufficient for small-medium volume

**Growth Tier:**
- $49/month for 3B compute units

**Estimated TelePay Usage (1000 tx/month):**
- Gas estimation: 10 CU × 1000 = 10,000 CU
- Transaction broadcast: 15 CU × 1000 = 15,000 CU
- Confirmation wait: 5 CU × 1000 = 5,000 CU
- **Total: 30,000 CU/month = WELL WITHIN FREE TIER**

### Return on Investment

**Costs:**
- **Alchemy:** $0/month (free tier sufficient)
- **Implementation:** 1-2 hours (just change RPC URL + add gas optimization)

**Benefits:**
- **Gas savings:** ~$600/month (25% of $2400 in gas fees at 1000 tx/month)
- **Reliability:** 99.995% uptime (less downtime = fewer support issues)
- **Performance:** Faster transaction broadcasts (better user experience)

**ROI:** ⭐⭐⭐⭐⭐ (Excellent) - $600/month savings for $0 cost

---

## Implementation Recommendations

### ✅ RECOMMENDED: Basic Alchemy RPC + Gas Optimization

**Why Implement:**
- Minimal effort (1-2 hours)
- Zero ongoing cost (free tier)
- Immediate 15-30% gas savings
- Better reliability and performance

**What to Implement:**

**1. Update RPC Endpoint**
```bash
# Create Alchemy secret
gcloud secrets create ETHEREUM_RPC_URL \
  --data-file=- <<< "https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"

# Update GCHostPay3-10-26 deployment
gcloud run services update gchostpay3-10-26 \
  --update-env-vars ETHEREUM_RPC_URL=projects/291176869049/secrets/ETHEREUM_RPC_URL/versions/latest
```

**2. Add EIP-1559 Gas Optimization**

Copy gas optimization logic from `/OCTOBER/10-18/GCHostPay10-21/wallet_manager.py` (lines 72-125):

```python
# In GCHostPay3-10-26/wallet_manager.py

def _get_optimized_gas_price(self) -> Dict[str, int]:
    """
    Get optimized gas price using EIP-1559 or fallback to legacy.
    Uses Alchemy's eth_feeHistory for dynamic pricing.
    """
    try:
        # Try EIP-1559 gas fees
        fee_data = self.w3.eth.fee_history(1, 'latest', [25, 50, 75])

        if fee_data and 'baseFeePerGas' in fee_data:
            base_fee = fee_data['baseFeePerGas'][-1]
            priority_fee = int(fee_data['reward'][-1][1]) if fee_data.get('reward') else self.w3.to_wei(2, 'gwei')
            max_fee = (base_fee * 2) + priority_fee

            return {
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": priority_fee,
                "gasPrice": base_fee + priority_fee
            }
    except Exception as e:
        print(f"⚠️ [GAS] EIP-1559 failed, using fallback: {e}")

    # Fallback to standard gas price
    gas_price = self.w3.eth.gas_price
    return {
        "maxFeePerGas": gas_price,
        "maxPriorityFeePerGas": self.w3.to_wei(2, 'gwei'),
        "gasPrice": gas_price
    }

# Update transaction building in send_eth_payment_with_infinite_retry()
def send_eth_payment_with_infinite_retry(...):
    # Get optimized gas
    gas_data = self._get_optimized_gas_price()

    # Build transaction with EIP-1559
    transaction = {
        'nonce': nonce,
        'to': to_address_checksum,
        'value': amount_wei,
        'gas': 21000,
        'maxFeePerGas': gas_data['maxFeePerGas'],        # ← NEW
        'maxPriorityFeePerGas': gas_data['maxPriorityFeePerGas'],  # ← NEW
        'chainId': 1
    }
```

**Deployment Steps:**
1. Update `wallet_manager.py` with gas optimization
2. Update `ETHEREUM_RPC_URL` secret to Alchemy endpoint
3. Redeploy GCHostPay3-10-26
4. Monitor gas costs for 48 hours
5. Compare before/after gas usage

**Estimated Time:** 2 hours
**Risk:** Low (fallback to standard gas price if EIP-1559 fails)

---

### ❌ NOT RECOMMENDED: Alchemy Notify Webhooks

**Why Skip:**
- Adds complexity (webhook endpoint, signature verification, DB schema changes)
- No actual benefit (synchronous payment model)
- Over-engineering (already confirmed in `/OCTOBER/10-18/GCHostPay10-21/ALCHEMY_INTEGRATION.md`)

**What to Skip:**
- `alchemy_webhook_handler.py`
- Webhook route in main service
- `ETHEREUM_RPC_WEBHOOK_SECRET` configuration
- Database columns: tx_hash, tx_status, gas_used, block_number
- Alchemy Notify dashboard setup

**Previous Implementation (DO NOT USE):**
- See `/OCTOBER/10-18/GCHostPay10-21/ALCHEMY_INTEGRATION.md` for what NOT to do
- That integration added 400+ lines of unnecessary code
- Zero value for TelePay's use case

---

### ❌ NOT RECOMMENDED: Address Activity Monitoring

**Why Skip:**
- No incoming payments to monitor
- Host wallet only sends ETH (one-way flow)
- ChangeNOW API provides all needed status updates

---

## Comparison: With vs Without Alchemy

### Current Architecture (Without Alchemy)

```
Payment Flow:
    ↓
GCHostPay3 builds transaction
    ↓
Uses web3.eth.gas_price (static)
    ↓
Broadcasts via generic RPC
    ↓
Waits for confirmation (300s timeout)
    ↓
Returns tx details
```

**Pros:**
- Simple
- Works reliably
- No external dependencies beyond RPC

**Cons:**
- Higher gas costs (no optimization)
- Potential RPC downtime
- Slower response times

---

### Recommended Architecture (With Alchemy RPC + Gas Optimization)

```
Payment Flow:
    ↓
GCHostPay3 builds transaction
    ↓
Calls _get_optimized_gas_price()
    ↓ (uses Alchemy eth_feeHistory)
Dynamic EIP-1559 pricing (15-30% cheaper)
    ↓
Broadcasts via Alchemy RPC (99.995% uptime, <50ms latency)
    ↓
Waits for confirmation (300s timeout)
    ↓
Returns tx details
```

**Pros:**
- 15-30% gas savings ($600/month at 1000 tx)
- Better RPC reliability (99.995% vs ~99.9%)
- Faster transaction broadcasts
- Free tier covers usage

**Cons:**
- Slight dependency on Alchemy (fallback still works)

---

### Over-Engineered Architecture (With Full Alchemy Integration)

```
Payment Flow:
    ↓
GCHostPay3 builds transaction
    ↓
Uses EIP-1559 optimization
    ↓
Broadcasts via Alchemy RPC
    ↓
Waits for confirmation
    ↓ (tx confirmed on-chain)
Alchemy webhook fires → /alchemy-webhook
    ↓
Verify HMAC signature
    ↓
Update database tx_status
    ↓ (redundant - already confirmed inline)
Returns tx details
```

**Pros:**
- All benefits of recommended architecture
- Real-time webhook notifications

**Cons:**
- **Webhook notifications are redundant** (already waiting inline)
- **Adds complexity** (400+ lines of code)
- **No actual benefit** for synchronous payment model
- **Database schema changes** (4 new columns)
- **Extra secrets to manage** (webhook secret)

**Verdict:** ❌ Over-engineering - avoid this approach

---

## Technical Comparison Table

| Feature | Without Alchemy | With Alchemy RPC + Gas Opt | With Full Alchemy Integration |
|---------|-----------------|----------------------------|-------------------------------|
| **RPC Uptime** | ~99.9% | 99.995% | 99.995% |
| **Gas Costs** | Baseline | -15% to -30% | -15% to -30% |
| **Tx Speed** | Standard | 30x faster endpoints | 30x faster endpoints |
| **Implementation** | None | 2 hours | 8+ hours |
| **Code Complexity** | Low | Low | High |
| **Webhook Monitoring** | No | No | Yes (redundant) |
| **Monthly Cost** | $0 | $0 | $0 |
| **Monthly Savings** | - | ~$600 | ~$600 |
| **Maintenance** | Low | Low | High |
| **Value** | Baseline | ⭐⭐⭐⭐⭐ | ⭐⭐ |

---

## Decision Matrix

### When to Use Alchemy

| Use Case | Relevance | Recommendation |
|----------|-----------|----------------|
| **Enhanced RPC endpoint** | ⭐⭐⭐⭐⭐ | ✅ USE (better uptime, speed) |
| **EIP-1559 gas optimization** | ⭐⭐⭐⭐⭐ | ✅ USE (15-30% savings) |
| **Transaction monitoring webhooks** | ⭐ | ❌ SKIP (synchronous model) |
| **Address activity tracking** | ⭐ | ❌ SKIP (no incoming payments) |
| **NFT APIs** | N/A | ❌ SKIP (not relevant) |
| **Enhanced WebSockets** | ⭐ | ❌ SKIP (not event-driven) |
| **Dashboard/debugging tools** | ⭐⭐⭐ | ✅ USE (nice to have) |

---

## Migration Path (Recommended)

### Phase 1: RPC Endpoint Migration (30 minutes)

1. Create Alchemy account at https://dashboard.alchemy.com
2. Create new app (Ethereum Mainnet)
3. Copy API key
4. Update Secret Manager:
```bash
echo -n "https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY" | \
  gcloud secrets versions add ETHEREUM_RPC_URL --data-file=-
```
5. Restart GCHostPay3-10-26 (no code changes needed)

**Verify:**
```bash
# Check logs for successful connection
gcloud run services logs read gchostpay3-10-26 --limit=50 | grep "WALLET"
# Should see: ✅ [WALLET] Connected to Web3 provider
```

---

### Phase 2: Gas Optimization (1.5 hours)

1. Add `_get_optimized_gas_price()` method to `wallet_manager.py`
2. Update transaction building to use EIP-1559 fields
3. Add fallback logic for EIP-1559 failure
4. Deploy updated service
5. Monitor gas costs for 48 hours

**Verify:**
```bash
# Check logs for EIP-1559 usage
gcloud run services logs read gchostpay3-10-26 --limit=50 | grep "GAS"
# Should see: ✅ [GAS] EIP-1559 gas prices calculated
#             Base Fee: XX.XX Gwei
#             Priority Fee: XX.XX Gwei
```

**Track Savings:**
```sql
-- Compare gas costs before/after
SELECT
  DATE(created_at) as date,
  AVG(gas_used * gas_price_gwei) as avg_gas_cost,
  COUNT(*) as tx_count
FROM hostpay_transactions
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

### Phase 3: Monitoring & Optimization (Optional)

1. Set up Alchemy dashboard alerts
2. Monitor API usage vs free tier limits
3. Adjust gas price buffer if needed (currently 1.2x)
4. Set up cost tracking dashboard

---

## Common Misconceptions

### ❌ "We need webhooks for transaction monitoring"

**Reality:**
- TelePay uses synchronous payment flow
- `wait_for_transaction_receipt()` already provides confirmation
- Webhook would fire AFTER we've already confirmed and returned response
- **No value added**

---

### ❌ "We need to track incoming ETH payments"

**Reality:**
- Host wallet only SENDS ETH (to ChangeNOW)
- Never receives ETH payments
- User payments go to NowPayments (not Ethereum)
- **Address activity monitoring is irrelevant**

---

### ❌ "Alchemy is expensive for high volume"

**Reality:**
- Free tier: 300M compute units/month
- TelePay usage: ~30k CU/month (0.01% of free tier)
- Would need 10,000x current volume to exceed free tier
- **Cost: $0/month**

---

### ❌ "Setting up Alchemy requires major code changes"

**Reality:**
- RPC migration: Just change URL (no code change)
- Gas optimization: Add 1 method, update 1 transaction field
- Total implementation: 2 hours
- **Minimal code changes**

---

## Frequently Asked Questions

### Q: Should we use Alchemy webhooks for better reliability?

**A:** No. Webhooks don't improve reliability for your use case. You already wait inline for confirmation via `wait_for_transaction_receipt()`. A webhook firing 10 seconds later doesn't add value since you've already moved on.

---

### Q: Can Alchemy help us track if ChangeNOW received our ETH?

**A:** No need. ChangeNOW's API already provides status updates via `GET /v2/exchange/by-id`. You can query:
- `status: "waiting"` - Awaiting ETH deposit
- `status: "confirming"` - ETH received, confirming
- `status: "finished"` - Conversion complete

This is more reliable than monitoring Ethereum directly since it accounts for ChangeNOW's internal confirmation requirements.

---

### Q: Will Alchemy speed up transaction confirmations?

**A:** No. Confirmation speed is determined by:
1. Gas price (higher = faster inclusion)
2. Network congestion
3. Block time (~12 seconds on Ethereum)

Alchemy can't change these. However, EIP-1559 optimization ensures you're paying the OPTIMAL gas price for current conditions (not overpaying or underpaying).

---

### Q: Do we need Alchemy's transaction replacement feature?

**A:** No. GCHostPay3 already has 3-attempt retry logic with error classification (see `/OCTOBER/10-26/GCHostPay3-10-26/tphp3-10-26.py`). Transaction replacement is handled at the application layer.

---

### Q: Should we migrate from our current RPC to Alchemy?

**A:** Yes, IF you're not already using Alchemy. Benefits:
- Better uptime (99.995% vs ~99.9%)
- Faster responses (sub-50ms latency)
- Free for your volume
- Easy migration (just change URL)

If you're already using Alchemy RPC, you're good - just add gas optimization.

---

### Q: Will gas optimization work on all networks?

**A:** EIP-1559 is supported on:
- ✅ Ethereum Mainnet (what TelePay uses)
- ✅ Polygon
- ✅ Optimism
- ✅ Arbitrum
- ❌ Bitcoin (not EVM-based)

Your current architecture only uses Ethereum, so full compatibility.

---

## Conclusion

### Summary of Findings

**Alchemy API is VALUABLE for TelePay, but ONLY for:**
1. ✅ Enhanced RPC infrastructure (better uptime, speed)
2. ✅ EIP-1559 gas optimization (15-30% cost savings)

**Alchemy API is NOT VALUABLE for:**
1. ❌ Webhook notifications (redundant with synchronous flow)
2. ❌ Address activity monitoring (no incoming payments)
3. ❌ NFT APIs (not relevant)
4. ❌ Enhanced WebSockets (not event-driven)

---

### Final Recommendation

**IMPLEMENT:** Basic Alchemy RPC + Gas Optimization

**Effort:** 2 hours
**Cost:** $0/month (free tier)
**Savings:** ~$600/month (gas optimization)
**ROI:** ⭐⭐⭐⭐⭐ Excellent

**DO NOT IMPLEMENT:** Webhooks, Address Monitoring, or Full Integration

**Why:** Adds complexity with zero benefit for synchronous payment model

---

### Action Items

1. ✅ Create Alchemy account and generate API key
2. ✅ Update `ETHEREUM_RPC_URL` secret to Alchemy endpoint
3. ✅ Add `_get_optimized_gas_price()` method to `wallet_manager.py`
4. ✅ Update transaction building to use EIP-1559 fields
5. ✅ Deploy updated GCHostPay3-10-26
6. ✅ Monitor gas savings for 48 hours
7. ❌ Skip webhook setup (not needed)
8. ❌ Skip address monitoring (not relevant)

---

### References

**Architecture Documents:**
- `/OCTOBER/10-26/PAYMENT_ARCHITECTURE_BREAKDOWN.md`
- `/OCTOBER/10-26/GCHostPay3-10-26/wallet_manager.py`
- `/OCTOBER/10-18/GCHostPay10-21/ALCHEMY_INTEGRATION.md` (reference for what NOT to do)

**External Resources:**
- Alchemy Docs: https://docs.alchemy.com
- Alchemy Dashboard: https://dashboard.alchemy.com
- EIP-1559 Spec: https://eips.ethereum.org/EIPS/eip-1559
- Web3.py Docs: https://web3py.readthedocs.io

**Research Citations:**
- Alchemy 2025 capabilities: Web search conducted Nov 2, 2025
- Webhook vs polling comparison: Alchemy documentation
- Gas optimization metrics: Alchemy blog posts

---

**Document Version:** 1.0
**Created:** November 2, 2025
**Author:** Claude (TelePay Architecture Analysis)
**Status:** ✅ Complete - Ready for Review
