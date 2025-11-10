# TelegramFunnel Payout Architecture - Detailed Workflow

This document contains a comprehensive Mermaid flowchart illustrating both **Instant Payout** and **Threshold Payout** architectures.

---

## Architecture Overview

The system supports two distinct payout methods:
1. **Instant Payout**: Immediate conversion from ETH → Client Currency (SHIB, DOGE, etc.)
2. **Threshold Payout**: Accumulated conversion via ETH → USDT → Client Currency (batched when threshold is met)

---

## Complete Workflow Diagram

```mermaid
graph TB
    subgraph "USER PAYMENT INITIATION"
        A[User Makes Payment<br/>BTC/ETH/LTC/etc] --> B[NowPayments Processes Payment]
        B --> C{Payment Status?}
        C -->|status='finished'| D[NowPayments IPN Webhook]
        C -->|status!='finished'| X[Wait for Confirmation]
    end

    subgraph "INSTANT PAYOUT FLOW - Direct ETH→ClientCurrency"
        D --> E[np-webhook-10-26<br/>POST /ipn]
        E --> E1[Layer 1: Validate status='finished']
        E1 --> E2[Extract actual_eth_amount<br/>from outcome_amount]
        E2 --> F[Enqueue Cloud Task:<br/>GCWebhook1-10-26]

        F --> G[GCWebhook1-10-26<br/>POST /]
        G --> G1[Layer 2: Re-validate status='finished'<br/>Defense-in-depth]
        G1 --> G2[Extract Data:<br/>- user_id<br/>- closed_channel_id<br/>- wallet_address<br/>- payout_currency<br/>- actual_eth_amount]
        G2 --> H[Enqueue Cloud Task:<br/>GCSplit1-10-26 ENDPOINT 1]

        H --> I[GCSplit1-10-26<br/>POST / ENDPOINT 1]
        I --> I1[Extract actual_eth_amount]
        I1 --> I2[Apply TP_FEE 15%:<br/>adjusted_amount = actual_eth * 0.85]
        I2 --> I3[Create Token with:<br/>- swap_currency='eth'<br/>- payout_mode='instant'<br/>- adjusted_amount<br/>- actual_eth_amount]
        I3 --> J[Enqueue Cloud Task:<br/>GCSplit2-10-26]

        J --> K[GCSplit2-10-26<br/>POST /]
        K --> K1[Decrypt Token<br/>Extract: adjusted_amount ETH]
        K1 --> L[ChangeNow API:<br/>GET /exchange-amount<br/>ETH→ClientCurrency]
        L --> M[Receive Estimate:<br/>- to_amount post-fee<br/>- deposit_fee<br/>- withdrawal_fee]
        M --> N[Encrypt Response Token]
        N --> O[Return to GCSplit1]

        O --> P[GCSplit1-10-26<br/>ENDPOINT 2 Process]
        P --> P1[Decrypt Estimate Response]
        P1 --> P2[Store in split_payout_request:<br/>- from_amount ETH<br/>- to_amount ClientCurrency<br/>- actual_eth_amount]
        P2 --> Q[Create Token for GCSplit3]
        Q --> R[Enqueue Cloud Task:<br/>GCSplit3-10-26]

        R --> S[GCSplit3-10-26<br/>POST /]
        S --> S1[Decrypt Token]
        S1 --> T[ChangeNow API:<br/>POST /create-transaction<br/>ETH→ClientCurrency]
        T --> U[Receive Transaction:<br/>- cn_api_id<br/>- payin_address<br/>- expected amounts]
        U --> V[Encrypt Response Token]
        V --> W[Return to GCSplit1]

        W --> Y[GCSplit1-10-26<br/>ENDPOINT 3 Process]
        Y --> Y1{Check cn_api_id<br/>Already Exists?}
        Y1 -->|Yes| Y2[Return 200 OK<br/>Idempotent - Skip Duplicate]
        Y1 -->|No| Y3[Store in split_payout_que:<br/>- cn_api_id PRIMARY KEY<br/>- from_amount<br/>- to_amount<br/>- actual_eth_amount]
        Y3 --> Z[Create Token for GCHostPay1]
        Z --> AA[Enqueue Cloud Task:<br/>GCHostPay1-10-26]

        AA --> AB[GCHostPay1-10-26<br/>POST / ENDPOINT 1]
        AB --> AB1[Decrypt Token<br/>Extract: from_amount adjusted ETH]
        AB1 --> AC{Optional:<br/>Status Check?}
        AC -->|Yes| AD[Enqueue GCHostPay2<br/>Status Check]
        AD --> AE[GCHostPay2-10-26<br/>POST /]
        AE --> AE1[Query ChangeNow Status]
        AE1 --> AF[Return Status to GCHostPay1]
        AC -->|No| AG[Skip Status Check]
        AF --> AG

        AG --> AH[Create Token for GCHostPay3]
        AH --> AI[Enqueue Cloud Task:<br/>GCHostPay3-10-26]

        AI --> AJ[GCHostPay3-10-26<br/>POST /]
        AJ --> AJ1[Decrypt Token<br/>Extract: from_amount, from_currency='eth']
        AJ1 --> AJ2{Currency Type<br/>Detection}
        AJ2 -->|from_currency='eth'| AK[Check ETH Balance<br/>wallet_manager.get_eth_balance]
        AJ2 -->|from_currency='usdt'| AK2[Check USDT Balance<br/>wallet_manager.get_erc20_balance]
        AK --> AL{Sufficient<br/>Balance?}
        AK2 --> AL
        AL -->|Yes| AM[Send Native ETH Payment:<br/>wallet_manager.send_eth_payment<br/>to ChangeNow payin address]
        AL -->|No| AN[Return Error:<br/>Insufficient Funds]
        AM --> AO[Store in split_payout_hostpay:<br/>- tx_hash<br/>- from_amount<br/>- actual_eth_amount]
        AO --> AP[Wait for ETH Confirmation<br/>~30 seconds]
        AP --> AQ[ChangeNow Detects Payment]
        AQ --> AR[ChangeNow Executes Swap:<br/>ETH → ClientCurrency]
        AR --> AS[Client Wallet Receives Tokens<br/>COMPLETE ✅]
    end

    subgraph "THRESHOLD PAYOUT FLOW - Accumulated ETH→USDT→ClientCurrency"
        D --> BA[np-webhook-10-26<br/>POST /ipn]
        BA --> BA1[Validate status='finished']
        BA1 --> BB[Enqueue Cloud Task:<br/>GCWebhook2-10-26]

        BB --> BC[GCWebhook2-10-26<br/>POST /]
        BC --> BC1[Re-validate status='finished']
        BC1 --> BC2[Validate Payment Amount:<br/>Min 50% of expected<br/>configurable via Secret Manager]
        BC2 --> BD[Store in payout_accumulation:<br/>- user_id<br/>- closed_channel_id<br/>- actual_eth_amount nowpayments_outcome_amount<br/>- conversion_status='pending']

        BD --> BE[Cloud Scheduler Trigger<br/>Every 15 Minutes]
        BE --> BF[GCMicroBatchProcessor-10-26<br/>GET /check-threshold]

        BF --> BG[Load Threshold from Secret Manager:<br/>MICRO_BATCH_THRESHOLD_USD<br/>Default: $5.00 dynamic]
        BG --> BH[Query Database:<br/>get_total_pending_actual_eth<br/>SUM all nowpayments_outcome_amount<br/>WHERE conversion_status='pending']
        BH --> BI{Total Pending<br/>≥ Threshold?}
        BI -->|No| BJ[Log: Below threshold<br/>Return 200 OK]
        BI -->|Yes| BK[Calculate USD Value<br/>of Accumulated ETH]
        BK --> BL{USD Value<br/>≥ $5.00?}
        BL -->|No| BJ
        BL -->|Yes| BM[Create Batch Conversion:<br/>batch_uuid = uuid4<br/>unique_id = 'batch_{uuid}']

        BM --> BN[Update Records:<br/>conversion_status='processing'<br/>batch_conversion_id=batch_uuid]
        BN --> BO[Create Token with:<br/>- unique_id batch_{uuid}<br/>- summed actual_eth_amount<br/>- swap_currency='eth'<br/>- target_currency='usdt']
        BO --> BP[Enqueue Cloud Task:<br/>GCHostPay1-10-26<br/>ENDPOINT 2]

        BP --> BQ[GCHostPay1-10-26<br/>POST / ENDPOINT 2<br/>Batch Conversion Handler]
        BQ --> BQ1[Decrypt Token<br/>Extract: summed actual_eth_amount]
        BQ1 --> BR{Optional:<br/>Status Check?}
        BR -->|Yes| BS[GCHostPay2 Status Check]
        BS --> BT[Return Status]
        BR -->|No| BU[Skip Status]
        BT --> BU

        BU --> BV[Create Token for GCHostPay3:<br/>- from_currency='eth'<br/>- to_currency='usdt'<br/>- from_amount summed ETH]
        BV --> BW[Enqueue Cloud Task:<br/>GCHostPay3-10-26]

        BW --> BX[GCHostPay3-10-26<br/>POST /]
        BX --> BX1[Decrypt Token<br/>Extract: from_amount ETH]
        BX1 --> BY[Check ETH Balance]
        BY --> BZ{Sufficient?}
        BZ -->|No| CA[Return Error]
        BZ -->|Yes| CB[Send ETH to ChangeNow:<br/>wallet_manager.send_eth_payment<br/>ETH→USDT Swap]
        CB --> CC[ChangeNow Executes:<br/>ETH → USDT]
        CC --> CD[Platform Wallet Receives USDT]
        CD --> CE[GCHostPay3 Creates Callback Token:<br/>- batch_uuid<br/>- cn_api_id<br/>- actual_usdt_received]
        CE --> CF[Retry Logic:<br/>Query ChangeNow Status]
        CF --> CG{Swap<br/>Finished?}
        CG -->|No waiting/exchanging| CH[Enqueue Delayed Retry:<br/>+5 minutes<br/>Max 3 retries]
        CH --> CF
        CG -->|Yes finished| CI[Enqueue Callback:<br/>GCHostPay1-10-26<br/>ENDPOINT 4 /retry-callback-check]

        CI --> CJ[GCHostPay1-10-26<br/>POST /retry-callback-check]
        CJ --> CJ1[Decrypt Retry Token<br/>Extract: batch_uuid, cn_api_id]
        CJ1 --> CK[Query ChangeNow API<br/>GET /transactions/{cn_api_id}]
        CK --> CL{Status?}
        CL -->|Still Processing| CM[Schedule Next Retry<br/>retry_count++]
        CM -->|retry_count<3| CF
        CM -->|retry_count≥3| CN[Return Error:<br/>Max Retries Exceeded]
        CL -->|Finished| CO[Extract actual_usdt_received<br/>from amountTo]
        CO --> CP[Create Callback Token:<br/>Token Expiration: 30 min<br/>to accommodate delays]
        CP --> CQ[Enqueue Callback:<br/>GCMicroBatchProcessor-10-26<br/>POST /swap-executed]

        CQ --> CR[GCMicroBatchProcessor-10-26<br/>POST /swap-executed]
        CR --> CR1[Decrypt Token<br/>Validate: timestamp within 30 min]
        CR1 --> CS[Query Records:<br/>WHERE batch_conversion_id=batch_uuid<br/>AND conversion_status='processing']
        CS --> CT{Records<br/>Found?}
        CT -->|No| CU[Return 404:<br/>No Records for Batch]
        CT -->|Yes| CV[Calculate Proportional Distribution:<br/>For each record:<br/>share = record.actual_eth / total_eth<br/>usdt_share = actual_usdt * share]
        CV --> CW[Update payout_accumulation:<br/>- usdt_amount = usdt_share<br/>- conversion_status='converted'<br/>- updated_at = NOW]
        CW --> CX[Return 200 OK:<br/>Distribution Complete]

        CX --> CY[Cloud Scheduler Trigger<br/>GCBatchProcessor-10-26]
        CY --> CZ[GCBatchProcessor-10-26<br/>GET /check-threshold]
        CZ --> DA[Query Each Client:<br/>SUM usdt_amount<br/>WHERE conversion_status='converted'<br/>GROUP BY user_id, closed_channel_id]
        DA --> DB{Client Total<br/>≥ Threshold?}
        DB -->|No| DC[Skip Client]
        DB -->|Yes| DD[Sum all actual_eth_amount<br/>for client records]
        DD --> DE[Create Token:<br/>- swap_currency='usdt'<br/>- payout_mode='threshold'<br/>- adjusted_amount USDT<br/>- actual_eth_amount 0.0]
        DE --> DF[Enqueue Cloud Task:<br/>GCSplit1-10-26<br/>ENDPOINT 4 /batch-payout]

        DF --> DG[GCSplit1-10-26<br/>POST /batch-payout<br/>ENDPOINT 4]
        DG --> DG1[Decrypt Token<br/>Extract: adjusted_amount USDT]
        DG1 --> DH[Create Token with:<br/>- swap_currency='usdt'<br/>- payout_mode='threshold'<br/>- from_amount USDT]
        DH --> DI[Enqueue Cloud Task:<br/>GCSplit2-10-26]

        DI --> DJ[GCSplit2-10-26<br/>POST /]
        DJ --> DJ1[Decrypt Token<br/>Extract: from_amount USDT]
        DJ1 --> DK[ChangeNow API:<br/>GET /exchange-amount<br/>USDT→ClientCurrency<br/>NOT USDT→ETH hardcoded!]
        DK --> DL[Receive Estimate:<br/>to_amount post-fee]
        DL --> DM[Encrypt Response Token]
        DM --> DN[Return to GCSplit1]

        DN --> DO[GCSplit1 ENDPOINT 2<br/>Process Estimate]
        DO --> DO1[Decrypt Response]
        DO1 --> DP[Store in split_payout_request:<br/>- from_amount USDT<br/>- to_amount ClientCurrency]
        DP --> DQ[Create Token for GCSplit3]
        DQ --> DR[Enqueue Cloud Task:<br/>GCSplit3-10-26]

        DR --> DS[GCSplit3-10-26<br/>POST /]
        DS --> DS1[Decrypt Token<br/>Extract: from_amount USDT]
        DS1 --> DT[ChangeNow API:<br/>POST /create-transaction<br/>from_currency='usdt'<br/>NOT 'eth' hardcoded!<br/>USDT→ClientCurrency]
        DT --> DU[Receive Transaction Details]
        DU --> DV[Return to GCSplit1]

        DV --> DW[GCSplit1 ENDPOINT 3]
        DW --> DW1{Check Idempotency:<br/>cn_api_id exists?}
        DW1 -->|Yes| DW2[Return 200 OK]
        DW1 -->|No| DX[Store in split_payout_que:<br/>- from_amount USDT<br/>- to_amount ClientCurrency<br/>- cn_api_id PRIMARY KEY]
        DX --> DY[Create Token for GCHostPay1]
        DY --> DZ[Enqueue Cloud Task:<br/>GCHostPay1-10-26]

        DZ --> EA[GCHostPay1-10-26<br/>POST / ENDPOINT 1]
        EA --> EA1[Decrypt Token<br/>Extract: from_amount USDT]
        EA1 --> EB{Optional:<br/>Status Check?}
        EB -->|Yes| EC[GCHostPay2 Check]
        EC --> ED[Return Status]
        EB -->|No| EE[Skip]
        ED --> EE

        EE --> EF[Create Token for GCHostPay3:<br/>- from_currency='usdt'<br/>- from_amount USDT]
        EF --> EG[Enqueue Cloud Task:<br/>GCHostPay3-10-26]

        EG --> EH[GCHostPay3-10-26<br/>POST /]
        EH --> EH1[Decrypt Token<br/>Extract: from_currency='usdt']
        EH1 --> EH2{Currency Type<br/>Detection}
        EH2 -->|'usdt'| EI[Check USDT Balance:<br/>wallet_manager.get_erc20_balance<br/>USDT Contract: 0xdac17f...]
        EI --> EJ{Sufficient<br/>USDT?}
        EJ -->|No| EK[Return Error]
        EJ -->|Yes| EL[Send ERC-20 USDT:<br/>wallet_manager.send_erc20_token<br/>Gas: 100,000<br/>Decimals: 6<br/>to ChangeNow payin address]
        EL --> EM[Store in split_payout_hostpay]
        EM --> EN[Wait for Tx Confirmation]
        EN --> EO[ChangeNow Detects USDT Payment]
        EO --> EP[ChangeNow Executes Swap:<br/>USDT → ClientCurrency]
        EP --> EQ[Client Wallet Receives Tokens<br/>COMPLETE ✅]
    end

    style A fill:#e1f5ff
    style AS fill:#4caf50,color:#fff
    style EQ fill:#4caf50,color:#fff
    style I2 fill:#fff3cd
    style Y1 fill:#fff3cd
    style BG fill:#fff3cd
    style CV fill:#fff3cd
    style DG1 fill:#fff3cd
    style EH2 fill:#fff3cd
```

---

## Key Architectural Decisions

### 1. Dual-Currency Token Format (Session 75)
- **Unified token structure** supports both instant (ETH) and threshold (USDT) flows
- Token fields: `swap_currency`, `payout_mode`, `actual_eth_amount`
- Maintains backward compatibility with fallback defaults

### 2. TP_FEE Application (Session 71, 64)
- **Instant payouts**: TP_FEE (15%) applied to `actual_eth_amount` before swap
- **Threshold payouts**: TP_FEE applied to accumulated USDT
- Platform fee retained BEFORE client receives payout

### 3. Idempotency Protection (Session 68)
- **GCSplit1 ENDPOINT 3**: Checks if `cn_api_id` exists before insertion
- Prevents duplicate key errors during Cloud Tasks retries
- Returns 200 OK for duplicates (tells Cloud Tasks "job done")

### 4. Defense-in-Depth Validation (Session 68)
- **Layer 1 (np-webhook)**: Validates `status='finished'` before enqueue
- **Layer 2 (GCWebhook1/2)**: Re-validates status (defense against bypass)
- Prevents premature payouts before funds confirmed

### 5. Token Expiration Windows (Session 56)
- **Synchronous calls**: 5 minutes
- **Async with retries**: 30 minutes (GCMicroBatchProcessor)
- **Long-running workflows**: 2 hours (GCHostPay1/3)
- Accounts for ChangeNow processing delays + Cloud Tasks queue delays

### 6. ERC-20 Token Support (Session 60)
- **Multi-currency architecture**: Supports both native ETH and ERC-20 tokens (USDT, USDC, DAI)
- **Currency detection**: Routes to appropriate wallet method based on `from_currency`
- **Token configs**: Mainnet contract addresses, decimals (USDT=6, DAI=18)

### 7. Two-Swap Threshold Architecture (Session 53)
- **First swap**: ETH → USDT (accumulation for stability)
- **Second swap**: USDT → ClientCurrency (payout)
- **Rationale**: USDT provides price stability during accumulation period

### 8. Variable-Length String Encoding (Session 55)
- **Token serialization**: Uses `_pack_string` / `_unpack_string` for all string fields
- **UUID preservation**: Supports full 36-char UUIDs + prefixes (`batch_{uuid}` = 42 chars)
- **Prevents truncation**: Fixed 16-byte encoding caused critical data loss

### 9. Configurable Payment Thresholds (Session 59)
- **Runtime configuration**: Thresholds stored in Secret Manager (not hardcoded)
- **Primary validation**: 50% minimum (accounts for fees + volatility)
- **Fallback validation**: 75% minimum (when crypto→USD conversion fails)
- **Flexibility**: Different values for dev/staging/prod environments

### 10. Retry Logic with Exponential Backoff (Session 52)
- **ChangeNow query timing**: Immediate query often returns `status='waiting'`
- **Retry mechanism**: 3 retries × 5 minutes = 15 minutes max
- **Delayed callback**: Uses Cloud Tasks scheduled execution
- **Token refresh**: New token created on each retry to avoid expiration

---

## Database Tables

### Instant Payout Tables
- **`split_payout_request`**: Initial request storage
  - `actual_eth_amount` NUMERIC(20,18) - NowPayments outcome
  - `from_amount` NUMERIC(20,8) - Adjusted ETH (post TP_FEE)
  - `to_amount` NUMERIC(30,8) - Client token quantity

- **`split_payout_que`**: ChangeNow transaction tracking
  - `cn_api_id` VARCHAR(64) PRIMARY KEY - ChangeNow transaction ID
  - `actual_eth_amount` NUMERIC(20,18) - Actual ETH from NowPayments
  - `from_amount` NUMERIC(20,8) - ETH amount sent
  - `to_amount` NUMERIC(30,8) - Expected client tokens

- **`split_payout_hostpay`**: Payment execution records
  - `actual_eth_amount` NUMERIC(20,18) - Actual ETH from NowPayments
  - `from_amount` NUMERIC(20,8) - ETH sent to ChangeNow
  - `tx_hash` VARCHAR(66) - Ethereum transaction hash

### Threshold Payout Tables
- **`payout_accumulation`**: Pending conversions accumulator
  - `nowpayments_outcome_amount` NUMERIC(20,18) - Actual ETH from NowPayments
  - `usdt_amount` NUMERIC(20,8) - USDT after conversion
  - `conversion_status` VARCHAR(20) - 'pending', 'processing', 'converted'
  - `batch_conversion_id` UUID - Links to batch

- **`batch_conversions`**: Batch conversion tracking
  - `batch_conversion_id` UUID PRIMARY KEY
  - `total_eth_amount` NUMERIC(20,18) - Summed actual ETH
  - `total_usdt_received` NUMERIC(20,8) - Actual USDT from ChangeNow
  - `cn_api_id` VARCHAR(64) - ChangeNow transaction ID

---

## Critical Fixes Documented

### ✅ RESOLVED - Session 75: Threshold Payout Method Restored
- **Issue**: Threshold payouts failing with parameter name mismatch
- **Fix**: Updated `/batch-payout` endpoint to use unified token format
- **Impact**: Both instant and threshold flows now use consistent dual-currency tokens

### ✅ RESOLVED - Session 67: GCSplit1 Dictionary Key Mismatch
- **Issue**: KeyError blocking both instant and threshold payouts
- **Fix**: Changed `to_amount_eth_post_fee` → `to_amount_post_fee` (generic naming)
- **Impact**: Instant and threshold flows unblocked

### ✅ RESOLVED - Session 66: Token Field Ordering Mismatch
- **Issue**: Binary struct unpacking order mismatch causing token decryption failures
- **Fix**: Reordered GCSplit1 unpacking to match GCSplit2 packing
- **Impact**: Dual-currency implementation fully functional

### ✅ RESOLVED - Session 60: ERC-20 Token Support
- **Issue**: GCHostPay3 trying to send ETH instead of USDT (ERC-20)
- **Fix**: Added `send_erc20_token()` method with currency routing
- **Impact**: Platform can now execute USDT payments to ChangeNow

### ✅ RESOLVED - Session 58: Data Flow Separation
- **Issue**: Passing token quantity (596,726 SHIB) instead of USDT amount (5.48)
- **Fix**: Changed `eth_amount=pure_market_eth_value` → `eth_amount=from_amount_usdt`
- **Impact**: ChangeNow receives correct USDT amount

### ✅ RESOLVED - Session 57: NUMERIC Precision Overflow
- **Issue**: Database columns too small for large token quantities (SHIB, DOGE)
- **Fix**: Migrated to NUMERIC(30,8) for token quantities
- **Impact**: All token types now supported (max 10^22 tokens)

### ✅ RESOLVED - Session 56: Token Expiration Window
- **Issue**: 5-minute expiration rejecting valid batch callbacks (workflow takes 15-20 min)
- **Fix**: Increased to 30-minute window to accommodate ChangeNow delays
- **Impact**: Batch conversions can complete end-to-end

### ✅ RESOLVED - Session 55: UUID Truncation
- **Issue**: Fixed 16-byte encoding truncating `batch_{uuid}` to 10 characters
- **Fix**: Variable-length encoding with `_pack_string` / `_unpack_string`
- **Impact**: Full UUIDs preserved through entire token chain

### ✅ RESOLVED - Session 53: Hardcoded Currency Bug
- **Issue**: GCSplit2/3 using hardcoded `from_currency='eth'` instead of `'usdt'`
- **Fix**: Made currency parameters dynamic from token
- **Impact**: Second swap correctly uses USDT→ClientCurrency

---

## Monitoring & Debugging Tips

### Instant Payout Debugging
1. Check NowPayments IPN: Look for `status='finished'` and `outcome_amount`
2. Verify TP_FEE application: `adjusted_amount = actual_eth * 0.85`
3. Check ChangeNow estimate: `to_amount_post_fee` in response
4. Verify ETH balance before GCHostPay3 sends payment
5. Monitor ChangeNow swap status: `waiting` → `exchanging` → `sending` → `finished`

### Threshold Payout Debugging
1. Check micro-batch threshold: Default $5.00 (configurable in Secret Manager)
2. Verify ETH→USDT conversion: Platform wallet should receive USDT
3. Check proportional distribution: Each record's share = `record.actual_eth / total_eth`
4. Verify individual client thresholds: Sum of `usdt_amount` per client
5. Monitor USDT→ClientCurrency swap: GCSplit2 should NOT use hardcoded `to_currency='eth'`

### Common Error Patterns
- **"Token expired"**: Check token age in logs, verify 30-minute window for async flows
- **"Insufficient funds"**: Verify currency type detection (ETH vs USDT)
- **KeyError in GCSplit1**: Verify generic naming (`to_amount_post_fee` not `to_amount_eth_post_fee`)
- **NUMERIC overflow**: Check token quantities exceed column precision (migrate to NUMERIC(30,8))
- **Invalid UUID**: Verify variable-length encoding (not fixed 16-byte truncation)

---

## Future Enhancements

1. **Phase 2: Edit-in-place status updates** (channel messages)
2. **Dynamic threshold tuning** via machine learning
3. **Multi-token accumulation** (accumulate in BTC, ETH, USDT simultaneously)
4. **Direct DEX integration** (reduce ChangeNow dependency)
5. **Real-time balance monitoring** (alert on low wallet balances)

---

**Last Updated**: 2025-11-08
**Version**: 2.0 (Reflects Sessions 50-75)
