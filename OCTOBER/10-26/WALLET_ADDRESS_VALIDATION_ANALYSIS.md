# Wallet Address Validation & Auto-Population Analysis

**Date:** 2025-11-08
**Purpose:** Analyze feasibility of REGEX-based wallet address validation for auto-populating Payout Network & Payout Currency dropdowns

---

## Executive Summary

**✅ YES, this is technically feasible** with important caveats and limitations.

The system can implement client-side REGEX validation to:
1. **Identify network type** from wallet address format
2. **Auto-populate dropdowns** when address is pasted/typed
3. **Validate mismatches** between selected Network/Currency and entered address

**However**, there are significant limitations due to:
- EVM address format sharing across multiple networks (ETH, BASE, BSC, MATIC)
- Address format ambiguities between certain networks
- Checksum validation requiring libraries beyond simple REGEX
- Token vs. native currency distinctions

---

## System Context

### Supported Networks (16 total)
From `/api/mappings/currency-network`:
```
ADA, BASE, BCH, BSC, BTC, DOGE, ETH, LTC, MATIC, SOL, TON, TRX, XLM, XMR, XRP, ZEC
```

### Supported Currencies (46 total)
```
AAVE, ADA, ARB, AVAX, BCH, BGB, BNB, BONK, BTC, CRO, DAI, DOGE, DOT, ETC, ETH,
FDUSD, FIL, GRT, IMX, INJ, JUP, LDO, LEO, LINK, LTC, MNT, NEAR, OKB, ONDO, PEPE,
QNT, SHIB, SOL, TON, TRX, USD1, USDC, USDE, USDT, VET, WLD, WLFI, XLM, XMR, XRP, ZEC
```

### Current Implementation
- **File:** `GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
- **Field:** `clientWalletAddress` (line 36)
- **Input:** `<input type="text" placeholder="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb">`
- **Validation:** Currently none - only required field check

---

## Network Address Formats & REGEX Patterns

### 1. EVM-Compatible Networks (CRITICAL AMBIGUITY)
**Networks:** ETH, BASE, BSC, MATIC
**Format:** `0x` + 40 hexadecimal characters
**REGEX:** `/^0x[a-fA-F0-9]{40}$/`

**⚠️ MAJOR LIMITATION:**
All four networks use **identical** address formats. The same wallet address (e.g., `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`) is valid on:
- Ethereum (ETH)
- Base (BASE)
- BNB Smart Chain (BSC)
- Polygon (MATIC)

**Implication:** REGEX **cannot distinguish** between these networks. Auto-population must either:
- Default to one network (e.g., ETH)
- Show all compatible networks and require user selection
- Use additional heuristics (not possible with address alone)

**Currency Support on EVM Networks:**
- **ETH network:** AAVE, ARB, BGB, CRO, DAI, DOGE, ETH, FDUSD, LINK
- **BASE network:** ETH
- **BSC network:** AAVE, ADA, AVAX, BCH, BNB, BONK, DAI, DOGE, DOT, ETC, FDUSD, FIL, PEPE, SHIB, USDT
- **MATIC network:** DAI

### 2. Bitcoin (BTC)
**Format:** Multiple formats supported
- Legacy (P2PKH): Starts with `1`, 26-34 characters
- Pay-to-Script-Hash (P2SH): Starts with `3`, 26-34 characters
- Segregated Witness (Bech32): Starts with `bc1`, 42-62 characters

**REGEX Options:**
```regex
Legacy/P2SH:  /^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$/
Bech32:       /^bc1[a-z0-9]{39,59}$/
Combined:     /^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59}$/
```

**Notes:**
- Excludes characters: `0` (zero), `O` (uppercase o), `I` (uppercase i), `l` (lowercase L)
- Base58Check encoding with checksum (regex doesn't validate checksum)

### 3. Tron (TRX)
**Format:** Starts with `T`, 34 characters total
**REGEX:** `/^T[A-Za-z1-9]{33}$/`

**Example:** `TJRabPrwbZy45sbavfcjinPJC18kjpRTv8`

**Notes:**
- Mainnet addresses start with `T` (0x41 in hex)
- Testnet addresses start with different prefix (rarely used)
- Base58Check encoding

### 4. Solana (SOL)
**Format:** Base58-encoded 32-byte array, 32-44 characters
**REGEX:** `/^[1-9A-HJ-NP-Za-km-z]{32,44}$/`

**Example:** `7EqQdEUu5z8F5M9VzX6M8vBxkq8z8F5M9VzX6M8vBxkq`

**Notes:**
- No specific prefix (unlike ETH's `0x`)
- Case-sensitive
- Can overlap with Bitcoin addresses (length/character set similar)

**⚠️ AMBIGUITY:** 32-34 character Solana addresses could potentially match Bitcoin Legacy format. Requires additional context.

### 5. TON (The Open Network)
**Format:** Base64/Base64url, 48 characters with prefix
**REGEX:** `/^(EQ|UQ|kQ|0Q)[A-Za-z0-9_-]{46}$/`

**Prefixes:**
- `EQ` = Mainnet bounceable
- `UQ` = Mainnet non-bounceable
- `kQ` = Testnet bounceable
- `0Q` = Testnet non-bounceable

**Example:** `EQD2NmD_lH5f5u1Kj3KfGyTvhZSX0Eg6qp2a5IQUKXxrJcvP`

**Notes:**
- Modern addresses (2025) use EQ/UQ prefixes
- Very distinctive format - **no ambiguity**

### 6. Cardano (ADA)
**Format:** Bech32 (Shelley) or Base58 (Byron legacy)
**REGEX:**
```regex
Shelley (current): /^addr1[a-z0-9]{53,}$/
Byron (legacy):    /^[1-9A-HJ-NP-Za-km-z]{50,120}$/
```

**Example:** `addr1qxy7ty6ptp9p...` (103-104 chars typical)

**Notes:**
- Modern addresses start with `addr1`
- Legacy Byron addresses have no prefix (can be 50-120 chars)

**⚠️ AMBIGUITY:** Byron addresses could theoretically overlap with Bitcoin/Solana

### 7. Stellar (XLM)
**Format:** Base32 (StrKey), always starts with `G`, 56 characters
**REGEX:** `/^G[A-Z2-7]{55}$/`

**Example:** `GCRRSYF5JBFPXHN5DCG65A4J3MUYE53QMQ4XMXZ3CNKWFJIJJTGMH6MZ`

**Notes:**
- Public keys start with `G` (always)
- Secret keys start with `S` (never accept these!)
- Ed25519 algorithm
- Very distinctive format - **no ambiguity**

### 8. Litecoin (LTC)
**Format:** Similar to Bitcoin with different prefixes
**REGEX:** `/^([LM3]{1}[a-km-zA-HJ-NP-Z1-9]{26,33}|ltc1[a-z0-9]{39,59})$/`

**Prefixes:**
- Legacy: Starts with `L`
- P2SH: Starts with `M` or `3`
- Bech32: Starts with `ltc1`

**⚠️ AMBIGUITY:** Can overlap with Bitcoin (especially `3` prefix)

### 9. Dogecoin (DOGE)
**Format:** Base58, starts with `D`, 34 characters
**REGEX:** `/^D{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32}$/`

**Example:** `DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L`

**Notes:**
- First character always `D`
- Second character is `5-9, A-H, J-N, P-U`
- Very distinctive - **no ambiguity**

### 10. Bitcoin Cash (BCH)
**Format:** CashAddr format or Legacy
**REGEX:**
```regex
CashAddr: /^((bitcoincash:)?(q|p)[a-z0-9]{41})/
Legacy:   /^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$/
```

**Example:** `bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a`

**Notes:**
- CashAddr format preferred (starts with `bitcoincash:` or just `q`/`p`)
- Legacy format identical to Bitcoin

**⚠️ AMBIGUITY:** Legacy BCH addresses indistinguishable from BTC

### 11. XRP (Ripple)
**Format:** Base58, starts with `r`, 25-34 characters
**REGEX:** `/^r[1-9A-HJ-NP-Za-km-z]{25,34}$/`

**Example:** `rN7n7otQDd6FczFgLdlqtyMVrn3HMgkd8r`

**Notes:**
- Always starts with lowercase `r`
- Very distinctive - **no ambiguity**

### 12. Monero (XMR)
**Format:** Base58, starts with `4` (standard) or `8` (integrated), 95 characters
**REGEX:** `/^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$/`

**Example:** `48edfHu7V9Z84YzzMa6fUueoELZ9ZRXq9VetWzYGzKt52XU5xvqgzYnDK9URnRoJMk1j8nLwEVsaSWJ4fhdUyZijBGUicoD`

**Notes:**
- Standard addresses: Start with `4`
- Integrated addresses: Start with `8`
- Very long (95 chars) - **no ambiguity**

### 13. Zcash (ZEC)
**Format:** Multiple types
**REGEX:**
```regex
Transparent (t-addr): /^t[1-9A-HJ-NP-Za-km-z]{34}$/
Shielded (z-addr):    /^zs1[a-z0-9]{75}$/
```

**Example:** `t1Vqj8v6iMEwCQ7B4UYPVqXeP5MkG7x3eMm`

**Notes:**
- Transparent addresses start with `t1`
- Shielded (Sapling) addresses start with `zs1`
- Distinctive prefixes - **no ambiguity**

---

## Implementation Strategy

### Phase 1: Network Detection Function

Create a `detectNetworkFromAddress(address: string)` function that returns possible networks:

```typescript
interface NetworkDetection {
  networks: string[];     // Possible network codes (e.g., ['ETH', 'BASE', 'BSC', 'MATIC'])
  confidence: 'high' | 'medium' | 'low';
  ambiguous: boolean;     // True if multiple networks possible
}

function detectNetworkFromAddress(address: string): NetworkDetection {
  const trimmed = address.trim();

  // EVM networks (ambiguous)
  if (/^0x[a-fA-F0-9]{40}$/.test(trimmed)) {
    return {
      networks: ['ETH', 'BASE', 'BSC', 'MATIC'],
      confidence: 'medium',
      ambiguous: true
    };
  }

  // TON (high confidence, no ambiguity)
  if (/^(EQ|UQ)[A-Za-z0-9_-]{46}$/.test(trimmed)) {
    return {
      networks: ['TON'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Tron (high confidence)
  if (/^T[A-Za-z1-9]{33}$/.test(trimmed)) {
    return {
      networks: ['TRX'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Stellar (high confidence)
  if (/^G[A-Z2-7]{55}$/.test(trimmed)) {
    return {
      networks: ['XLM'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Dogecoin (high confidence)
  if (/^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$/.test(trimmed)) {
    return {
      networks: ['DOGE'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // XRP (high confidence)
  if (/^r[1-9A-HJ-NP-Za-km-z]{25,34}$/.test(trimmed)) {
    return {
      networks: ['XRP'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Monero (high confidence)
  if (/^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$/.test(trimmed)) {
    return {
      networks: ['XMR'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Cardano Shelley (high confidence)
  if (/^addr1[a-z0-9]{53,}$/.test(trimmed)) {
    return {
      networks: ['ADA'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Zcash transparent
  if (/^t1[1-9A-HJ-NP-Za-km-z]{33}$/.test(trimmed)) {
    return {
      networks: ['ZEC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Bitcoin (could also be BCH, LTC)
  if (/^bc1[a-z0-9]{39,59}$/.test(trimmed)) {
    return {
      networks: ['BTC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  if (/^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$/.test(trimmed)) {
    return {
      networks: ['BTC', 'BCH', 'LTC'],
      confidence: 'low',
      ambiguous: true
    };
  }

  // Litecoin Bech32
  if (/^ltc1[a-z0-9]{39,59}$/.test(trimmed)) {
    return {
      networks: ['LTC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Solana (medium confidence - could overlap with Bitcoin)
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(trimmed) && trimmed.length >= 32) {
    // Heuristic: Solana addresses are typically 32-44 chars
    // Bitcoin legacy is 26-34 chars
    if (trimmed.length >= 40) {
      return {
        networks: ['SOL'],
        confidence: 'medium',
        ambiguous: false
      };
    } else {
      return {
        networks: ['SOL', 'BTC'],
        confidence: 'low',
        ambiguous: true
      };
    }
  }

  // No match
  return {
    networks: [],
    confidence: 'low',
    ambiguous: false
  };
}
```

### Phase 2: Auto-Population Logic

Add event handler to wallet address input:

```typescript
const handleWalletAddressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const address = e.target.value;
  setClientWalletAddress(address);

  // Only attempt detection if address is reasonably long
  if (address.trim().length < 26) {
    return; // Too short to be valid
  }

  const detection = detectNetworkFromAddress(address);

  if (detection.networks.length === 0) {
    // Invalid format - optionally show warning
    setValidationWarning('⚠️ Address format not recognized');
    return;
  }

  if (detection.networks.length === 1 && detection.confidence === 'high') {
    // Single network detected with high confidence - auto-populate
    const detectedNetwork = detection.networks[0];

    // Check if user already selected a different network
    if (clientPayoutNetwork && clientPayoutNetwork !== detectedNetwork) {
      // Conflict detected
      setValidationWarning(
        `⚠️ Address appears to be for ${detectedNetwork} network, but you selected ${clientPayoutNetwork}`
      );
    } else {
      // Auto-populate network
      setClientPayoutNetwork(detectedNetwork);
      setValidationWarning(''); // Clear warnings

      // Optionally show success message
      setValidationSuccess(`✅ Detected ${detectedNetwork} network address`);
    }
  } else if (detection.ambiguous) {
    // Multiple networks possible
    if (detection.networks.includes('ETH')) {
      // EVM case - special handling
      setValidationWarning(
        `ℹ️ EVM address detected. Compatible with: ${detection.networks.join(', ')}. Please select your preferred network.`
      );
    } else {
      setValidationWarning(
        `⚠️ Address could be for: ${detection.networks.join(', ')}. Please verify and select correct network.`
      );
    }
  }
};
```

### Phase 3: Validation on Form Submit

Add comprehensive validation before submitting:

```typescript
const validateWalletAddress = (): boolean => {
  const detection = detectNetworkFromAddress(clientWalletAddress);

  if (detection.networks.length === 0) {
    throw new Error('Invalid wallet address format');
  }

  if (!detection.networks.includes(clientPayoutNetwork)) {
    throw new Error(
      `Wallet address format does not match selected network (${clientPayoutNetwork}). ` +
      `Address appears to be for: ${detection.networks.join(' or ')}`
    );
  }

  return true;
};
```

### Phase 4: Enhanced UX Considerations

1. **Real-time Feedback:**
   ```typescript
   <div className="form-group">
     <label>Your Wallet Address *</label>
     <input
       type="text"
       value={clientWalletAddress}
       onChange={handleWalletAddressChange}
       onPaste={handleWalletAddressChange} // Also trigger on paste
       placeholder="Paste your wallet address"
     />
     {validationWarning && (
       <div className="validation-warning" style={{ color: '#f59e0b' }}>
         {validationWarning}
       </div>
     )}
     {validationSuccess && (
       <div className="validation-success" style={{ color: '#10b981' }}>
         {validationSuccess}
       </div>
     )}
   </div>
   ```

2. **Network Badge Display:**
   Show detected networks as visual indicators

3. **Conflict Resolution:**
   If user manually selects different network than detected, show prominent warning

---

## Currency Auto-Population Strategy

**Challenge:** Currencies are tokens/coins that can exist on multiple networks.

**Example:**
- USDT exists on: ETH, BSC, MATIC, SOL, TON, TRX (6 networks)
- AAVE exists on: ETH, BSC (2 networks)

**Strategy:**

1. **Network-First Approach** (Recommended):
   - Detect/select network from wallet address
   - Filter currencies to only those supported on detected network
   - If only one currency available on that network for the detected address format → auto-select
   - If multiple currencies → require user selection

2. **Do NOT auto-populate currency** unless:
   - Network is unambiguously detected (high confidence)
   - Only one currency exists for that network in the mappings
   - Example: If user pastes TON address and only TON currency is supported on TON network → auto-select TON currency

**Implementation:**

```typescript
const autoPopulateCurrency = (detectedNetwork: string) => {
  // Get currencies available for this network
  const availableCurrencies = mappings?.network_to_currencies[detectedNetwork] || [];

  if (availableCurrencies.length === 1) {
    // Only one currency available - safe to auto-populate
    setClientPayoutCurrency(availableCurrencies[0].currency);
    setValidationSuccess(
      `✅ Auto-selected ${availableCurrencies[0].currency_name} (only currency on ${detectedNetwork})`
    );
  } else {
    // Multiple currencies available - do NOT auto-populate
    // Just set the network and let user choose currency
    setValidationWarning(
      `ℹ️ Please select your payout currency from ${availableCurrencies.length} options on ${detectedNetwork}`
    );
  }
};
```

---

## Edge Cases & Limitations

### 1. EVM Address Ambiguity
**Problem:** Same address valid on ETH, BASE, BSC, MATIC
**Solution:**
- Default to ETH (most common)
- Show info message: "EVM address detected. Also compatible with BASE, BSC, MATIC"
- Let user override if needed

### 2. Bitcoin vs. Bitcoin Cash (Legacy Format)
**Problem:** Identical address format for legacy addresses
**Solution:**
- Default to BTC (more common)
- Show warning: "Legacy address format. Could be BTC or BCH. Please verify."
- Require explicit network selection

### 3. Solana vs. Bitcoin Overlap
**Problem:** Some Solana addresses (32-34 chars) match Bitcoin character set
**Solution:**
- Use length heuristic: 40+ chars → likely Solana
- 26-34 chars → likely Bitcoin
- Show warning if ambiguous

### 4. Byron-era Cardano Addresses
**Problem:** No distinct prefix, can overlap with other Base58 formats
**Solution:**
- Prioritize modern `addr1` format in validation
- For ambiguous Base58 addresses (50-120 chars), show warning
- Recommend users use modern Shelley addresses

### 5. Testnet vs. Mainnet
**Problem:** Some testnets have different formats (e.g., TON `kQ` vs `EQ`)
**Solution:**
- Only validate mainnet addresses
- Reject testnet addresses with clear error message
- Example: Reject TON addresses starting with `kQ` or `0Q`

### 6. Checksum Validation
**Problem:** REGEX cannot validate checksums (Bitcoin, Ethereum, etc.)
**Solution:**
- Use validation library for checksum verification
- Recommended: `multicoin-address-validator` npm package
- Two-tier validation:
  1. REGEX for format/network detection (fast, client-side)
  2. Library for checksum validation (slower, more thorough)

### 7. Case Sensitivity
**Problem:** Some addresses are case-sensitive (Solana), others aren't (Bitcoin)
**Solution:**
- Document case sensitivity per network
- Preserve user input exactly as entered
- Warn if address contains unexpected casing

### 8. User Typos
**Problem:** Single character error invalidates address
**Solution:**
- Checksum validation will catch most typos
- Show clear error message
- Don't auto-populate if validation fails

---

## Recommended Implementation Libraries

### Option 1: Custom REGEX (Lightweight)
**Pros:**
- No dependencies
- Fast client-side validation
- Full control over logic

**Cons:**
- No checksum validation
- Must manually maintain patterns
- Limited to format checking

**Best for:** Network detection and basic format validation

### Option 2: multicoin-address-validator
```bash
npm install multicoin-address-validator
```

**Usage:**
```typescript
import WAValidator from 'multicoin-address-validator';

const isValid = WAValidator.validate(address, 'ethereum');
// Returns true/false

const isValidWithChain = WAValidator.validate(
  address,
  'USDT',
  'ethereum', // chainType
  'prod'      // networkType (prod/testnet)
);
```

**Pros:**
- Validates 130+ currencies
- Checksum validation included
- Supports chainType fallback (EVM tokens use 'ethereum' validator)
- ~17 kB minified + gzipped

**Cons:**
- Additional dependency
- Slightly slower than pure REGEX
- Some tokens only support specific chain types

**Best for:** Production-grade validation with checksum support

### Option 3: @swyftx/api-crypto-address-validator
**Pros:**
- Smaller bundle size (~69.7% smaller than multicoin-address-validator)
- Modern, actively maintained
- Same API as multicoin-address-validator

**Cons:**
- Less mature than multicoin-address-validator

### Option 4: Hybrid Approach (RECOMMENDED)
```typescript
// 1. Fast REGEX detection for network identification
const detection = detectNetworkFromAddress(address);

// 2. Checksum validation using library
import WAValidator from 'multicoin-address-validator';

const validateAddress = (address: string, network: string): boolean => {
  // Map our network codes to library currency codes
  const networkMap = {
    'ETH': 'ethereum',
    'BTC': 'bitcoin',
    'TRX': 'tron',
    'SOL': 'solana',
    'ADA': 'cardano',
    'XRP': 'ripple',
    'LTC': 'litecoin',
    'DOGE': 'dogecoin',
    'BCH': 'bitcoincash',
    'XLM': 'stellar',
    'XMR': 'monero',
    'ZEC': 'zcash',
    'TON': 'ton',
    // EVM chains all use 'ethereum' validator
    'BASE': 'ethereum',
    'BSC': 'ethereum',
    'MATIC': 'ethereum'
  };

  const currencyCode = networkMap[network];
  return WAValidator.validate(address, currencyCode);
};
```

---

## Security Considerations

### 1. Client-Side Only Validation
**Risk:** Client-side validation can be bypassed
**Mitigation:**
- Also validate server-side in registration API
- Add same validation logic to backend (Python)

### 2. Phishing Addresses
**Risk:** Users might paste scammer addresses
**Mitigation:**
- Cannot prevent with REGEX alone
- Educate users to verify addresses
- Consider implementing address book/saved addresses

### 3. Clipboard Hijacking
**Risk:** Malware can modify clipboard contents
**Mitigation:**
- Show "Please verify your address" warning
- Display entered address clearly before submission
- Consider checksum display for visual verification

### 4. Secret Key Detection
**Risk:** User accidentally pastes private key instead of public address
**Mitigation:**
- Detect and reject Stellar secret keys (start with `S`)
- Detect and reject Bitcoin WIF private keys (start with `5`, `K`, `L`)
- Show prominent error: "⛔ NEVER share your private key!"

```typescript
const detectPrivateKey = (input: string): boolean => {
  // Stellar secret key
  if (/^S[A-Z2-7]{55}$/.test(input)) return true;

  // Bitcoin WIF
  if (/^[5KL][1-9A-HJ-NP-Za-km-z]{50,51}$/.test(input)) return true;

  // Ethereum private key (64 hex chars, often with 0x)
  if (/^(0x)?[a-fA-F0-9]{64}$/.test(input)) return true;

  return false;
};
```

---

## Testing Strategy

### Test Cases Required

#### 1. Single Network Detection (High Confidence)
- ✅ TON address → auto-select TON
- ✅ TRX address → auto-select TRX
- ✅ XLM address → auto-select XLM
- ✅ DOGE address → auto-select DOGE
- ✅ XRP address → auto-select XRP

#### 2. EVM Ambiguity Handling
- ⚠️ 0x address → show all 4 networks (ETH, BASE, BSC, MATIC)
- ⚠️ User selects BSC → accept
- ⚠️ User selects ETH → accept
- ❌ User selects BTC → reject (invalid)

#### 3. Bitcoin Format Variations
- ✅ bc1... (Bech32) → BTC only
- ⚠️ 1... (Legacy) → could be BTC/BCH/LTC
- ⚠️ 3... (P2SH) → could be BTC/LTC

#### 4. Network/Currency Mismatch Detection
- ❌ TRX address + ETH network → reject
- ❌ ETH address + SOL network → reject
- ✅ ETH address + BSC network → accept (both EVM)

#### 5. Invalid Address Rejection
- ❌ Random string → reject
- ❌ Too short address → reject
- ❌ Invalid characters → reject
- ❌ Private key detected → reject with security warning

#### 6. Edge Case Handling
- ⚠️ 32-char Solana address → show warning (could be BTC)
- ✅ 44-char Solana address → high confidence SOL
- ⚠️ 50+ char Base58 → could be Cardano Byron or others

### Sample Test Addresses

```typescript
const testAddresses = {
  ETH: '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb',
  BTC_LEGACY: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
  BTC_SEGWIT: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
  TRX: 'TJRabPrwbZy45sbavfcjinPJC18kjpRTv8',
  SOL: '7EqQdEUu5z8F5M9VzX6M8vBxkq8z8F5M9VzX6M8vBxkq',
  TON: 'EQD2NmD_lH5f5u1Kj3KfGyTvhZSX0Eg6qp2a5IQUKXxrJcvP',
  ADA: 'addr1qxy7ty6ptp9puqz...',
  XLM: 'GCRRSYF5JBFPXHN5DCG65A4J3MUYE53QMQ4XMXZ3CNKWFJIJJTGMH6MZ',
  DOGE: 'DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L',
  XRP: 'rN7n7otQDd6FczFgLdlqtyMVrn3HMgkd8r',
  XMR: '48edfHu7V9Z84YzzMa6fUueoELZ9ZRXq9VetWzYGzKt52XU5xvqgzYnDK9URnRoJMk1j8nLwEVsaSWJ4fhdUyZijBGUicoD',
  LTC_LEGACY: 'LdP8Qox1VAhCzLJNqrr74YovaWYyNBUWvL',
  LTC_BECH32: 'ltc1qar0srrr7xfkvy5l643lydnw9re59gtzzaxx3c6',
  BCH: 'bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a',
  ZEC: 't1Vqj8v6iMEwCQ7B4UYPVqXeP5MkG7x3eMm'
};
```

---

## Performance Considerations

### REGEX Performance
- **Average:** < 1ms per validation
- **Worst case:** ~5ms for complex patterns
- **Recommendation:** Debounce validation by 300ms to avoid excessive calls during typing

```typescript
import { useState, useCallback } from 'react';
import debounce from 'lodash/debounce';

const debouncedValidation = useCallback(
  debounce((address: string) => {
    const detection = detectNetworkFromAddress(address);
    // Handle detection...
  }, 300),
  []
);
```

### Library Validation Performance
- **multicoin-address-validator:** ~10-50ms per validation
- **Checksum verification:** Additional 5-20ms
- **Recommendation:** Only run full validation on blur/submit, not on every keystroke

---

## User Experience Flow

### Scenario 1: Clear TON Address
1. User pastes: `EQD2NmD_lH5f5u1Kj3KfGyTvhZSX0Eg6qp2a5IQUKXxrJcvP`
2. System detects: TON network (high confidence)
3. Auto-populates: Network = TON
4. Checks currency: Only TON currency on TON network
5. Auto-populates: Currency = TON
6. Shows: ✅ "Detected TON network address. Auto-selected TON currency."
7. User clicks: Register Channel (validation passes)

### Scenario 2: EVM Address (Ambiguous)
1. User pastes: `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`
2. System detects: ETH/BASE/BSC/MATIC (ambiguous)
3. Shows message: ℹ️ "EVM address detected. Compatible with: ETH, BASE, BSC, MATIC. Please select your network."
4. User selects: BSC
5. System shows: Available currencies on BSC (AAVE, ADA, AVAX, etc.)
6. User selects: USDT
7. Validation: ✅ Address format matches BSC (passes)
8. User clicks: Register Channel

### Scenario 3: Mismatch Detection
1. User pastes: `TJRabPrwbZy45sbavfcjinPJC18kjpRTv8` (TRX address)
2. System detects: TRX network
3. User manually changes network to: ETH
4. System shows: ⚠️ "Address appears to be for TRX network, but you selected ETH"
5. User clicks: Register Channel
6. Validation fails: ❌ "Wallet address format does not match selected network (ETH)"
7. User corrects: Changes network back to TRX
8. Validation passes: ✅

### Scenario 4: Invalid Address
1. User types: `not-a-valid-address`
2. System detects: No matching network
3. Shows: ⚠️ "Address format not recognized"
4. Dropdowns: Remain empty (no auto-population)
5. User clicks: Register Channel
6. Validation fails: ❌ "Invalid wallet address format"

---

## Deployment Considerations

### Code Changes Required

#### Files to Modify:
1. **RegisterChannelPage.tsx**
   - Add `detectNetworkFromAddress()` function
   - Add `handleWalletAddressChange()` handler
   - Add validation state (warnings/success messages)
   - Add checksum validation library

2. **EditChannelPage.tsx**
   - Same changes as RegisterChannelPage.tsx
   - Preserve existing address on load (don't auto-change)

3. **package.json**
   - Add: `"multicoin-address-validator": "^0.5.11"`

4. **Backend Validation (GCRegisterAPI-10-26)**
   - Add Python address validation
   - Mirror client-side logic for security
   - Use: `py-crypto-address-validator` or custom REGEX

### Rollout Strategy

#### Phase 1: Network Detection Only (Low Risk)
- Add detection function
- Show informational messages only
- **No auto-population**
- Collect usage data

#### Phase 2: Auto-Population for High-Confidence Networks (Medium Risk)
- Enable auto-population for TON, TRX, XLM, DOGE, XRP, XMR, ZEC
- Show success messages
- Allow manual override

#### Phase 3: Full Validation (High Value)
- Add checksum validation library
- Reject invalid addresses on submit
- Show clear error messages

#### Phase 4: Enhanced UX (Polish)
- Add visual network badges
- Show detected currencies
- Implement address format hints

---

## Alternatives Considered

### Alternative 1: Server-Side Address Lookup
**Approach:** Query blockchain APIs to verify address exists
**Pros:**
- 100% accurate
- Can detect testnet vs mainnet
- Can verify address is active

**Cons:**
- Requires API keys for each blockchain
- Rate limiting issues
- Latency (500-2000ms per lookup)
- Privacy concerns (leaking user addresses to third parties)
- Cost (many APIs charge per request)

**Verdict:** ❌ Not recommended for real-time validation

### Alternative 2: No Auto-Population (Status Quo)
**Approach:** Require users to manually select network and currency
**Pros:**
- No implementation needed
- No edge cases to handle
- User has full control

**Cons:**
- Poor UX (users must know their network)
- Higher error rate (users select wrong network)
- More support requests

**Verdict:** ⚠️ Current approach, but suboptimal

### Alternative 3: Smart Contract Address Detection
**Approach:** For EVM chains, detect if address is EOA or contract
**Pros:**
- Can distinguish between wallet and contract addresses
- Useful for filtering

**Cons:**
- Requires blockchain RPC calls
- Latency and cost
- Not applicable to non-EVM chains

**Verdict:** ❌ Overkill for this use case

---

## Conclusion & Recommendations

### ✅ Recommended Approach: Hybrid REGEX + Library Validation

**Implementation Priority:**

1. **High Priority (Implement First):**
   - Network detection for unambiguous formats (TON, TRX, XLM, DOGE, XRP, XMR, ZEC)
   - Basic REGEX validation
   - Auto-population for high-confidence networks
   - Mismatch warnings

2. **Medium Priority (Phase 2):**
   - EVM address detection with user selection
   - Checksum validation using library
   - Enhanced error messages

3. **Low Priority (Nice to Have):**
   - Visual network badges
   - Address format hints
   - Copy/paste UX improvements

### Key Success Metrics:

- **Reduce user errors:** Fewer support requests for "wrong network" issues
- **Improve UX:** Faster registration flow (fewer clicks)
- **Maintain accuracy:** Zero false positives on network detection

### Risk Mitigation:

1. **Deploy incrementally** (info messages → auto-population → validation)
2. **Always allow manual override** (never force auto-detected values)
3. **Show clear warnings** for ambiguous cases
4. **Add server-side validation** to catch client-side bypasses
5. **Monitor support requests** for new edge cases

### Final Answer to User's Question:

**Yes, REGEX-based wallet address validation is possible and recommended with the following caveats:**

✅ **Works well for:** TON, TRX, XLM, DOGE, XRP, XMR, ZEC (unique formats)
⚠️ **Partial support for:** ETH/BASE/BSC/MATIC (identical formats - requires user selection)
⚠️ **Limited support for:** BTC/BCH/LTC (overlapping legacy formats)
❌ **Cannot do:** Checksum validation without library, blockchain verification

**Recommended:** Implement hybrid approach with REGEX for network detection + library for checksum validation.

---

**End of Analysis**
