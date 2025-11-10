# Wallet Address Validation Implementation Checklist

**Date Created:** 2025-11-08
**Based on:** WALLET_ADDRESS_VALIDATION_ANALYSIS.md
**Implementation Strategy:** Phased rollout (4 phases)

---

## Prerequisites & Setup

### 1. Environment Setup
- [ ] **Install npm package:** `multicoin-address-validator`
  - Command: `npm install multicoin-address-validator`
  - File: `/GCRegisterWeb-10-26/package.json`
  - Version: `^0.5.11` or latest

- [ ] **Install lodash for debouncing** (if not already installed)
  - Command: `npm install lodash`
  - File: `/GCRegisterWeb-10-26/package.json`

- [ ] **Create TypeScript interface file** for validation types
  - File: `/GCRegisterWeb-10-26/src/types/validation.ts`
  - Define: `NetworkDetection` interface
  - Define: `ValidationState` interface
  - Define: `NetworkMap` type

### 2. Code Review & Baseline
- [ ] **Read current implementation:**
  - File: `/GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
  - Review: `clientWalletAddress` state (line 36)
  - Review: Current input field (lines 552-559)
  - Review: Form validation logic (lines 119-121)

- [ ] **Read current implementation:**
  - File: `/GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`
  - Review: `clientWalletAddress` state (line 40)
  - Review: Current input field (lines 610-617)
  - Review: Form validation logic (lines 166-168)

- [ ] **Verify API mappings endpoint working:**
  - Test: `curl https://gcregisterapi-10-26-291176869049.us-central1.run.app/api/mappings/currency-network`
  - Confirm: 16 networks, 46 currencies returned

---

## Phase 1: Network Detection Function (Low Risk - Information Only)

**Goal:** Add network detection without changing behavior. Show informational messages only.

### 1.1 Create Core Detection Module

- [ ] **Create new utility file:**
  - File: `/GCRegisterWeb-10-26/src/utils/walletAddressValidator.ts`
  - Export: `NetworkDetection` interface
  - Export: `detectNetworkFromAddress()` function
  - Export: `detectPrivateKey()` function (security)

- [ ] **Implement `NetworkDetection` interface:**
  ```typescript
  export interface NetworkDetection {
    networks: string[];
    confidence: 'high' | 'medium' | 'low';
    ambiguous: boolean;
  }
  ```

- [ ] **Implement `detectNetworkFromAddress()` function:**
  - Include all 16 network REGEX patterns (see analysis lines 247-382)
  - Networks to detect:
    - [ ] EVM (ETH, BASE, BSC, MATIC) - `/^0x[a-fA-F0-9]{40}$/`
    - [ ] TON - `/^(EQ|UQ)[A-Za-z0-9_-]{46}$/`
    - [ ] TRX - `/^T[A-Za-z1-9]{33}$/`
    - [ ] XLM - `/^G[A-Z2-7]{55}$/`
    - [ ] DOGE - `/^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$/`
    - [ ] XRP - `/^r[1-9A-HJ-NP-Za-km-z]{25,34}$/`
    - [ ] XMR - `/^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$/`
    - [ ] ADA (Shelley) - `/^addr1[a-z0-9]{53,}$/`
    - [ ] ZEC - `/^t1[1-9A-HJ-NP-Za-km-z]{33}$/`
    - [ ] BTC (Bech32) - `/^bc1[a-z0-9]{39,59}$/`
    - [ ] BTC (Legacy) - `/^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$/`
    - [ ] LTC (Bech32) - `/^ltc1[a-z0-9]{39,59}$/`
    - [ ] LTC (Legacy) - `/^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$/`
    - [ ] SOL - `/^[1-9A-HJ-NP-Za-km-z]{32,44}$/` (with length heuristics)
    - [ ] BCH (CashAddr) - `/^((bitcoincash:)?(q|p)[a-z0-9]{41})/`
    - [ ] ZEC (Shielded) - `/^zs1[a-z0-9]{75}$/`
  - Return appropriate confidence levels
  - Handle ambiguous cases (EVM, BTC/BCH/LTC, SOL/BTC)

- [ ] **Implement `detectPrivateKey()` function:**
  ```typescript
  export const detectPrivateKey = (input: string): boolean => {
    // Stellar secret key: /^S[A-Z2-7]{55}$/
    // Bitcoin WIF: /^[5KL][1-9A-HJ-NP-Za-km-z]{50,51}$/
    // Ethereum private key: /^(0x)?[a-fA-F0-9]{64}$/
    // Return true if matches any private key format
  }
  ```

- [ ] **Add unit tests for detection function:**
  - File: `/GCRegisterWeb-10-26/src/utils/walletAddressValidator.test.ts`
  - Test all 16 networks with sample addresses (see analysis lines 787-803)
  - Test ambiguous cases (EVM, BTC/BCH)
  - Test invalid addresses
  - Test private key detection

### 1.2 Integrate Detection into RegisterChannelPage

- [ ] **Import validation utilities:**
  - File: `/GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
  - Import: `detectNetworkFromAddress`, `detectPrivateKey`, `NetworkDetection`

- [ ] **Add validation state variables:**
  ```typescript
  const [validationWarning, setValidationWarning] = useState('');
  const [validationSuccess, setValidationSuccess] = useState('');
  const [detectedNetworks, setDetectedNetworks] = useState<NetworkDetection | null>(null);
  ```

- [ ] **Create `handleWalletAddressChange()` handler:**
  - Replace existing: `onChange={(e) => setClientWalletAddress(e.target.value)}`
  - Implement detection logic (see analysis lines 390-438)
  - Show informational messages only (no auto-population in Phase 1)
  - Check for private keys and show security warning

- [ ] **Add debounced validation:**
  ```typescript
  import debounce from 'lodash/debounce';

  const debouncedDetection = useCallback(
    debounce((address: string) => {
      if (address.trim().length < 26) return;

      // Check for private key first
      if (detectPrivateKey(address)) {
        setValidationWarning('⛔ NEVER share your private key! This appears to be a private key, not a public address.');
        return;
      }

      const detection = detectNetworkFromAddress(address);
      setDetectedNetworks(detection);

      // Show informational message based on detection
      if (detection.networks.length === 0) {
        setValidationWarning('⚠️ Address format not recognized');
      } else if (detection.networks.length === 1 && detection.confidence === 'high') {
        setValidationSuccess(`ℹ️ Detected ${detection.networks[0]} network address`);
      } else if (detection.ambiguous) {
        setValidationWarning(
          `ℹ️ Address compatible with: ${detection.networks.join(', ')}. Please select your network.`
        );
      }
    }, 300),
    []
  );
  ```

- [ ] **Update input field to use new handler:**
  - Location: Lines 552-559
  - Add: `onChange={(e) => { setClientWalletAddress(e.target.value); debouncedDetection(e.target.value); }}`
  - Add: `onPaste` handler (same as onChange)

- [ ] **Add validation message display:**
  ```typescript
  <div className="form-group">
    <label>Your Wallet Address *</label>
    <input
      type="text"
      placeholder="Paste your wallet address"
      value={clientWalletAddress}
      onChange={(e) => {
        setClientWalletAddress(e.target.value);
        debouncedDetection(e.target.value);
      }}
      onPaste={(e) => {
        setClientWalletAddress(e.currentTarget.value);
        debouncedDetection(e.currentTarget.value);
      }}
      required
    />
    {validationWarning && (
      <div className="validation-warning" style={{
        color: '#f59e0b',
        fontSize: '13px',
        marginTop: '4px'
      }}>
        {validationWarning}
      </div>
    )}
    {validationSuccess && (
      <div className="validation-success" style={{
        color: '#10b981',
        fontSize: '13px',
        marginTop: '4px'
      }}>
        {validationSuccess}
      </div>
    )}
  </div>
  ```

### 1.3 Integrate Detection into EditChannelPage

- [ ] **Repeat all steps from 1.2 for EditChannelPage:**
  - File: `/GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`
  - Import validation utilities
  - Add state variables
  - Create handler
  - Update input field (lines 610-617)
  - Add validation message display

- [ ] **Special handling for Edit page:**
  - Don't trigger validation on initial load (only when user changes address)
  - Preserve existing address without warnings

### 1.4 Phase 1 Testing

- [ ] **Test informational messages work:**
  - Paste TON address → see "ℹ️ Detected TON network address"
  - Paste EVM address → see "ℹ️ Address compatible with: ETH, BASE, BSC, MATIC"
  - Paste invalid address → see "⚠️ Address format not recognized"
  - Paste private key → see "⛔ NEVER share your private key!"

- [ ] **Verify no behavior changes:**
  - Confirm dropdowns are NOT auto-populated
  - Confirm form submission works unchanged
  - Confirm no breaking changes to existing flow

- [ ] **Deploy Phase 1:**
  - Build: `npm run build`
  - Deploy to GCS: `gsutil -m rsync -r -d dist/ gs://www-paygateprime-com/`
  - Invalidate cache
  - Test on production: https://www.paygateprime.com/register

---

## Phase 2: Auto-Population for High-Confidence Networks (Medium Risk)

**Goal:** Auto-populate Network dropdown when high-confidence detection occurs.

### 2.1 Implement Auto-Population Logic

- [ ] **Modify `handleWalletAddressChange()` in RegisterChannelPage:**
  - File: `/GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
  - Add auto-population for high-confidence, non-ambiguous networks
  - Reference: Analysis lines 407-424

- [ ] **Auto-populate logic:**
  ```typescript
  if (detection.networks.length === 1 && detection.confidence === 'high') {
    const detectedNetwork = detection.networks[0];

    // Check for conflict with manually selected network
    if (clientPayoutNetwork && clientPayoutNetwork !== detectedNetwork) {
      setValidationWarning(
        `⚠️ Address appears to be for ${detectedNetwork} network, but you selected ${clientPayoutNetwork}`
      );
    } else {
      // Auto-populate network
      setClientPayoutNetwork(detectedNetwork);
      setValidationWarning('');
      setValidationSuccess(`✅ Detected ${detectedNetwork} network address`);
    }
  }
  ```

- [ ] **Implement currency auto-population (conditional):**
  - Only auto-populate currency if network has exactly 1 supported currency
  - Reference: Analysis lines 522-539
  ```typescript
  const autoPopulateCurrency = (detectedNetwork: string) => {
    const availableCurrencies = mappings?.network_to_currencies[detectedNetwork] || [];

    if (availableCurrencies.length === 1) {
      setClientPayoutCurrency(availableCurrencies[0].currency);
      setValidationSuccess(
        `✅ Auto-selected ${availableCurrencies[0].currency_name} (only currency on ${detectedNetwork})`
      );
    } else if (availableCurrencies.length > 1) {
      setValidationWarning(
        `ℹ️ Please select your payout currency from ${availableCurrencies.length} options on ${detectedNetwork}`
      );
    }
  };
  ```

- [ ] **Call `autoPopulateCurrency()` after network auto-population**

### 2.2 Handle Manual Network Changes

- [ ] **Update existing `handleNetworkChange()` to check for conflicts:**
  - File: `/GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
  - Lines: 64-67 (current location)
  ```typescript
  const handleNetworkChange = (network: string) => {
    setClientPayoutNetwork(network);

    // Check if manually selected network conflicts with detected network
    if (detectedNetworks && detectedNetworks.networks.length === 1) {
      const detectedNetwork = detectedNetworks.networks[0];
      if (network !== detectedNetwork && detectedNetworks.confidence === 'high') {
        setValidationWarning(
          `⚠️ Manually selected ${network}, but address format appears to be ${detectedNetwork}. Please verify.`
        );
      } else {
        setValidationWarning('');
      }
    }
  };
  ```

### 2.3 Apply to EditChannelPage

- [ ] **Implement same auto-population logic in EditChannelPage:**
  - File: `/GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`
  - Modify: `handleWalletAddressChange()`
  - Modify: `handleNetworkChange()`
  - Add: `autoPopulateCurrency()`

- [ ] **Special handling for Edit page:**
  - Only auto-populate on user changes (not on initial load)
  - Check: `useEffect` should not trigger auto-population when loading existing channel

### 2.4 Phase 2 Testing

- [ ] **Test high-confidence auto-population:**
  - Paste TON address → Network dropdown auto-selects TON
  - Paste TRX address → Network dropdown auto-selects TRX
  - Paste XLM address → Network dropdown auto-selects XLM
  - Paste DOGE address → Network dropdown auto-selects DOGE
  - Paste XRP address → Network dropdown auto-selects XRP

- [ ] **Test currency auto-population (if applicable):**
  - TON address → both Network=TON and Currency=TON auto-selected
  - Verify currencies NOT auto-populated for multi-currency networks (ETH, BSC)

- [ ] **Test EVM ambiguity handling:**
  - Paste 0x address → no auto-population
  - See message: "ℹ️ Address compatible with: ETH, BASE, BSC, MATIC"
  - Manually select BSC → accepted
  - Manually select ETH → accepted

- [ ] **Test conflict detection:**
  - Paste TRX address (auto-selects TRX)
  - Manually change to ETH
  - See warning: "⚠️ Manually selected ETH, but address format appears to be TRX"

- [ ] **Test manual override:**
  - Paste EVM address
  - Manually select BSC
  - Change wallet address to TON address
  - Verify BSC changes to TON (or shows conflict warning)

- [ ] **Deploy Phase 2:**
  - Build and deploy
  - Test on production
  - Monitor for user feedback

---

## Phase 3: Full Validation with Checksum (High Value)

**Goal:** Add checksum validation using multicoin-address-validator library.

### 3.1 Integrate Validation Library

- [ ] **Verify package installed:**
  - Check: `node_modules/multicoin-address-validator` exists
  - Version: `^0.5.11` in package.json

- [ ] **Create network mapping utility:**
  - File: `/GCRegisterWeb-10-26/src/utils/networkMapping.ts`
  - Map our network codes to library currency codes
  ```typescript
  export const NETWORK_TO_VALIDATOR_MAP: Record<string, string> = {
    'ETH': 'ethereum',
    'BASE': 'ethereum',
    'BSC': 'ethereum',
    'MATIC': 'ethereum',
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
    'TON': 'ton'
  };
  ```

- [ ] **Create `validateAddressChecksum()` function:**
  - File: `/GCRegisterWeb-10-26/src/utils/walletAddressValidator.ts`
  ```typescript
  import WAValidator from 'multicoin-address-validator';
  import { NETWORK_TO_VALIDATOR_MAP } from './networkMapping';

  export const validateAddressChecksum = (
    address: string,
    network: string
  ): boolean => {
    const validatorCurrency = NETWORK_TO_VALIDATOR_MAP[network];
    if (!validatorCurrency) return false;

    try {
      return WAValidator.validate(address, validatorCurrency, 'prod');
    } catch (error) {
      console.error('Checksum validation error:', error);
      return false;
    }
  };
  ```

### 3.2 Add Checksum Validation to Form Submit

- [ ] **Create `validateWalletAddress()` function in RegisterChannelPage:**
  - File: `/GCRegisterWeb-10-26/src/pages/RegisterChannelPage.tsx`
  - Add before form submission
  ```typescript
  const validateWalletAddress = (): boolean => {
    const detection = detectNetworkFromAddress(clientWalletAddress);

    // Check format matches selected network
    if (detection.networks.length === 0) {
      throw new Error('Invalid wallet address format');
    }

    if (!detection.networks.includes(clientPayoutNetwork)) {
      throw new Error(
        `Wallet address format does not match selected network (${clientPayoutNetwork}). ` +
        `Address appears to be for: ${detection.networks.join(' or ')}`
      );
    }

    // Checksum validation
    const checksumValid = validateAddressChecksum(
      clientWalletAddress,
      clientPayoutNetwork
    );

    if (!checksumValid) {
      throw new Error(
        `Invalid wallet address checksum for ${clientPayoutNetwork} network. ` +
        `Please verify your address is correct.`
      );
    }

    return true;
  };
  ```

- [ ] **Call `validateWalletAddress()` in form submit handler:**
  - Location: In `handleRegister()` function
  - Add before existing validation (before line 119)
  ```typescript
  try {
    // Validate wallet address format and checksum
    validateWalletAddress();

    // Existing validation continues...
    if (!openChannelId || !channelTitle) {
      throw new Error('Please fill in all channel information fields');
    }
    // ...
  } catch (error) {
    setError(error.message);
    return;
  }
  ```

### 3.3 Add Checksum Validation to EditChannelPage

- [ ] **Implement same validation in EditChannelPage:**
  - File: `/GCRegisterWeb-10-26/src/pages/EditChannelPage.tsx`
  - Add `validateWalletAddress()` function
  - Call in `handleUpdate()` function (before line 166)

### 3.4 Optional: Real-time Checksum Feedback

- [ ] **Add checksum validation indicator (optional UX enhancement):**
  - Show checkmark icon when checksum is valid
  - Show warning icon when checksum is invalid
  - Only show after user stops typing (use debounce)

- [ ] **Implement in `handleWalletAddressChange()`:**
  ```typescript
  // After network detection
  if (clientPayoutNetwork && detection.networks.includes(clientPayoutNetwork)) {
    const checksumValid = validateAddressChecksum(
      address,
      clientPayoutNetwork
    );

    if (checksumValid) {
      setValidationSuccess(
        `✅ Valid ${clientPayoutNetwork} address with correct checksum`
      );
    } else {
      setValidationWarning(
        `⚠️ Address format matches ${clientPayoutNetwork}, but checksum appears invalid. Please verify.`
      );
    }
  }
  ```

### 3.5 Phase 3 Testing

- [ ] **Test checksum validation on submit:**
  - Valid ETH address with correct checksum → submission succeeds
  - Valid ETH address with incorrect checksum → submission fails with error
  - Valid BTC address with correct checksum → submission succeeds
  - Invalid address → submission fails with error

- [ ] **Test all 16 networks with valid addresses:**
  - Use sample addresses from analysis (lines 787-803)
  - Verify each network's checksum validation works

- [ ] **Test network mismatch rejection:**
  - Paste TRX address
  - Select ETH network
  - Submit form
  - Verify error: "Wallet address format does not match selected network (ETH)"

- [ ] **Test error messages are user-friendly:**
  - Clear indication of what's wrong
  - Suggestion for how to fix
  - No technical jargon

- [ ] **Deploy Phase 3:**
  - Build and deploy
  - Test on production
  - Monitor error rates

---

## Phase 4: Enhanced UX (Polish)

**Goal:** Improve user experience with visual indicators and better feedback.

### 4.1 Visual Network Badges

- [ ] **Create network badge component:**
  - File: `/GCRegisterWeb-10-26/src/components/NetworkBadge.tsx`
  ```typescript
  interface NetworkBadgeProps {
    networks: string[];
    confidence: 'high' | 'medium' | 'low';
  }

  export const NetworkBadge: React.FC<NetworkBadgeProps> = ({
    networks,
    confidence
  }) => {
    const colors = {
      high: '#10b981',
      medium: '#f59e0b',
      low: '#ef4444'
    };

    return (
      <div style={{ marginTop: '8px' }}>
        {networks.map(network => (
          <span
            key={network}
            style={{
              display: 'inline-block',
              padding: '4px 8px',
              marginRight: '4px',
              borderRadius: '4px',
              fontSize: '12px',
              backgroundColor: `${colors[confidence]}20`,
              color: colors[confidence],
              border: `1px solid ${colors[confidence]}`
            }}
          >
            {network}
          </span>
        ))}
      </div>
    );
  };
  ```

- [ ] **Add NetworkBadge to wallet address input:**
  - Show detected networks as badges below input field
  - Update color based on confidence level

### 4.2 Address Format Hints

- [ ] **Add format hint text below wallet address input:**
  ```typescript
  <div className="form-group">
    <label>Your Wallet Address *</label>
    <input ... />

    {/* Show format hint if no address entered */}
    {!clientWalletAddress && (
      <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
        Supported formats: Ethereum (0x...), Bitcoin (bc1.../1.../3...),
        Tron (T...), TON (EQ.../UQ...), Solana, and more
      </div>
    )}

    {/* Show detected networks */}
    {detectedNetworks && detectedNetworks.networks.length > 0 && (
      <NetworkBadge
        networks={detectedNetworks.networks}
        confidence={detectedNetworks.confidence}
      />
    )}

    {/* Validation messages */}
    {validationWarning && <div className="validation-warning">...</div>}
    {validationSuccess && <div className="validation-success">...</div>}
  </div>
  ```

### 4.3 Improved Error Messages

- [ ] **Add CSS classes for validation states:**
  - File: `/GCRegisterWeb-10-26/src/index.css`
  ```css
  .validation-warning {
    color: #f59e0b;
    font-size: 13px;
    margin-top: 4px;
    padding: 8px;
    background-color: #fef3c7;
    border-radius: 4px;
    border-left: 3px solid #f59e0b;
  }

  .validation-success {
    color: #10b981;
    font-size: 13px;
    margin-top: 4px;
    padding: 8px;
    background-color: #d1fae5;
    border-radius: 4px;
    border-left: 3px solid #10b981;
  }

  .validation-error {
    color: #ef4444;
    font-size: 13px;
    margin-top: 4px;
    padding: 8px;
    background-color: #fee2e2;
    border-radius: 4px;
    border-left: 3px solid #ef4444;
  }
  ```

### 4.4 Loading States

- [ ] **Add loading indicator during validation:**
  ```typescript
  const [isValidating, setIsValidating] = useState(false);

  const debouncedDetection = useCallback(
    debounce(async (address: string) => {
      setIsValidating(true);

      // Detection logic...

      setIsValidating(false);
    }, 300),
    []
  );
  ```

- [ ] **Show loading state in UI:**
  ```typescript
  {isValidating && (
    <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
      🔍 Validating address...
    </div>
  )}
  ```

### 4.5 Copy/Paste UX Improvements

- [ ] **Add paste detection with immediate feedback:**
  ```typescript
  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pastedText = e.clipboardData.getData('text');
    setClientWalletAddress(pastedText);

    // Immediate validation on paste (no debounce)
    if (detectPrivateKey(pastedText)) {
      setValidationWarning('⛔ NEVER share your private key!');
      e.preventDefault();
      return;
    }

    const detection = detectNetworkFromAddress(pastedText);
    setDetectedNetworks(detection);

    // Auto-populate if high confidence
    if (detection.networks.length === 1 && detection.confidence === 'high') {
      setClientPayoutNetwork(detection.networks[0]);
      autoPopulateCurrency(detection.networks[0]);
    }
  };
  ```

### 4.6 Phase 4 Testing

- [ ] **Test visual badges display correctly:**
  - High confidence (green): TON, TRX, XLM
  - Medium confidence (amber): EVM addresses
  - Low confidence (red): Ambiguous addresses

- [ ] **Test format hints appear:**
  - Empty input → shows format hint
  - Address entered → shows detected networks
  - Invalid address → shows error

- [ ] **Test paste behavior:**
  - Paste address → immediate feedback (no delay)
  - Paste private key → immediate rejection
  - Paste valid address → auto-populate network

- [ ] **Test loading states:**
  - Type address → see "🔍 Validating address..." briefly
  - Validation completes → loading indicator disappears

- [ ] **Deploy Phase 4:**
  - Build and deploy
  - Test on production
  - Collect user feedback

---

## Backend Integration (Security Critical)

**Goal:** Mirror client-side validation on server to prevent bypasses.

### 5.1 Python Validation Module

- [ ] **Create Python validation utility:**
  - File: `/GCRegisterAPI-10-26/utils/wallet_validator.py`
  - Implement network detection using Python regex
  - Use library: `py-crypto-address-validator` or implement custom

- [ ] **Install Python validation library:**
  - Option 1: `pip install multicoin-address-validator` (if exists)
  - Option 2: Implement custom regex validation

- [ ] **Implement `detect_network_from_address()` in Python:**
  ```python
  import re
  from typing import List, Dict

  def detect_network_from_address(address: str) -> Dict:
      """
      Detect blockchain network from wallet address format
      Returns: {
          'networks': List[str],
          'confidence': str,
          'ambiguous': bool
      }
      """
      address = address.strip()

      # EVM networks
      if re.match(r'^0x[a-fA-F0-9]{40}$', address):
          return {
              'networks': ['ETH', 'BASE', 'BSC', 'MATIC'],
              'confidence': 'medium',
              'ambiguous': True
          }

      # TON
      if re.match(r'^(EQ|UQ)[A-Za-z0-9_-]{46}$', address):
          return {
              'networks': ['TON'],
              'confidence': 'high',
              'ambiguous': False
          }

      # ... (implement all 16 networks)

      return {
          'networks': [],
          'confidence': 'low',
          'ambiguous': False
      }
  ```

### 5.2 API Validation Endpoint

- [ ] **Add validation to channel registration endpoint:**
  - File: `/GCRegisterAPI-10-26/api/routes/channels.py`
  - Import: `from utils.wallet_validator import detect_network_from_address`

- [ ] **Add validation in register channel route:**
  ```python
  @channels_bp.route('/register', methods=['POST'])
  @jwt_required()
  def register_channel():
      data = request.get_json()

      # Extract fields
      wallet_address = data.get('client_wallet_address')
      payout_network = data.get('client_payout_network')

      # Validate wallet address format
      detection = detect_network_from_address(wallet_address)

      if not detection['networks']:
          return jsonify({
              'success': False,
              'error': 'Invalid wallet address format'
          }), 400

      if payout_network not in detection['networks']:
          return jsonify({
              'success': False,
              'error': f'Wallet address format does not match network {payout_network}',
              'detected_networks': detection['networks']
          }), 400

      # Continue with registration...
  ```

- [ ] **Add same validation to update channel endpoint:**
  - File: `/GCRegisterAPI-10-26/api/routes/channels.py`
  - Route: `PUT /channels/<id>`

### 5.3 Backend Testing

- [ ] **Test API rejects mismatched addresses:**
  - POST TRX address with network=ETH → 400 error
  - POST invalid address → 400 error
  - POST valid address with correct network → 200 success

- [ ] **Test API validation messages:**
  - Clear error message
  - Includes detected networks in response

- [ ] **Deploy backend updates:**
  - Build: `gcloud builds submit`
  - Deploy: Already auto-deployed via Cloud Run
  - Test API endpoint with curl

---

## Testing & Quality Assurance

### 6.1 Unit Tests

- [ ] **Create test file for validation utilities:**
  - File: `/GCRegisterWeb-10-26/src/utils/walletAddressValidator.test.ts`
  - Framework: Jest or Vitest

- [ ] **Test `detectNetworkFromAddress()` with all networks:**
  - [ ] ETH address (0x...) → returns ['ETH', 'BASE', 'BSC', 'MATIC']
  - [ ] BTC Bech32 (bc1...) → returns ['BTC']
  - [ ] BTC Legacy (1... or 3...) → returns ['BTC', 'BCH', 'LTC']
  - [ ] TRX (T...) → returns ['TRX']
  - [ ] SOL (32-44 chars) → returns ['SOL']
  - [ ] TON (EQ.../UQ...) → returns ['TON']
  - [ ] XLM (G...) → returns ['XLM']
  - [ ] DOGE (D...) → returns ['DOGE']
  - [ ] XRP (r...) → returns ['XRP']
  - [ ] XMR (4.../8...) → returns ['XMR']
  - [ ] ADA (addr1...) → returns ['ADA']
  - [ ] LTC (L.../M.../ltc1...) → returns ['LTC']
  - [ ] BCH (bitcoincash:...) → returns ['BCH']
  - [ ] ZEC (t1.../zs1...) → returns ['ZEC']

- [ ] **Test `detectPrivateKey()` function:**
  - [ ] Stellar secret key (S...) → returns true
  - [ ] Bitcoin WIF (5.../K.../L...) → returns true
  - [ ] Ethereum private key (0x + 64 hex) → returns true
  - [ ] Normal address → returns false

- [ ] **Test edge cases:**
  - [ ] Empty string → returns no networks
  - [ ] Very long string → returns no networks
  - [ ] Special characters → returns no networks
  - [ ] Mixed case addresses → handles correctly

### 6.2 Integration Tests

- [ ] **Test form flow on Register page:**
  - [ ] Paste TON address → Network auto-selects TON
  - [ ] Paste EVM address → See informational message, manual selection required
  - [ ] Paste TRX address, select ETH → See conflict warning
  - [ ] Submit with mismatched address/network → Form rejected

- [ ] **Test form flow on Edit page:**
  - [ ] Load existing channel → No auto-population on load
  - [ ] Change wallet address → Detection triggers
  - [ ] Auto-population works same as Register page

- [ ] **Test API integration:**
  - [ ] Submit valid registration → API accepts
  - [ ] Submit invalid address → API rejects with error
  - [ ] Submit mismatched network → API rejects with error

### 6.3 Browser Testing

- [ ] **Test on Chrome:**
  - Paste functionality works
  - Validation messages display correctly
  - Form submission works

- [ ] **Test on Firefox:**
  - Same as Chrome

- [ ] **Test on Safari:**
  - Same as Chrome

- [ ] **Test on Mobile (responsive):**
  - Validation messages readable
  - Badges display correctly
  - Touch/paste works

### 6.4 Performance Testing

- [ ] **Measure validation performance:**
  - REGEX detection: < 5ms per address
  - Checksum validation: < 50ms per address
  - No UI lag during typing

- [ ] **Test debouncing works:**
  - Type rapidly → validation only runs after 300ms pause
  - No excessive API calls or computations

### 6.5 User Acceptance Testing

- [ ] **Test with real wallet addresses:**
  - Get sample addresses from each supported network
  - Verify detection works correctly
  - Verify checksum validation works

- [ ] **Test error scenarios:**
  - Typo in address → Clear error message
  - Wrong network selected → Clear conflict message
  - Private key entered → Security warning displayed

---

## Documentation & Deployment

### 7.1 Code Documentation

- [ ] **Add JSDoc comments to all validation functions:**
  - File: `/GCRegisterWeb-10-26/src/utils/walletAddressValidator.ts`
  - Document parameters, return values, examples

- [ ] **Add inline comments for complex regex:**
  - Explain what each pattern matches
  - Note edge cases

- [ ] **Update README.md:**
  - File: `/GCRegisterWeb-10-26/README.md`
  - Document wallet validation feature
  - List supported networks
  - Include usage examples

### 7.2 Update PROGRESS.md

- [ ] **Create new entry in PROGRESS.md:**
  - File: `/OCTOBER/10-26/PROGRESS.md`
  - Document all phases implemented
  - List files modified
  - Note deployment dates

### 7.3 Update DECISIONS.md

- [ ] **Document architectural decisions:**
  - File: `/OCTOBER/10-26/DECISIONS.md`
  - Document choice of hybrid REGEX + library approach
  - Document phased rollout strategy
  - Document network mapping decisions

### 7.4 Production Deployment

- [ ] **Phase 1 deployment:**
  - Date: _________
  - Changes: Network detection, informational messages only
  - Risk: Low
  - Rollback plan: Revert commit

- [ ] **Phase 2 deployment:**
  - Date: _________
  - Changes: Auto-population for high-confidence networks
  - Risk: Medium
  - Rollback plan: Revert commit
  - Monitor: User feedback, support tickets

- [ ] **Phase 3 deployment:**
  - Date: _________
  - Changes: Checksum validation on submit
  - Risk: Medium
  - Rollback plan: Revert commit
  - Monitor: Form submission errors, rejection rates

- [ ] **Phase 4 deployment:**
  - Date: _________
  - Changes: Enhanced UX (badges, hints, etc.)
  - Risk: Low
  - Rollback plan: Revert commit

---

## Monitoring & Maintenance

### 8.1 Error Monitoring

- [ ] **Add error logging for validation failures:**
  - Log to console: Invalid addresses, checksum failures
  - Track metrics: Rejection rate by network

- [ ] **Monitor API validation failures:**
  - File: `/GCRegisterAPI-10-26/api/routes/channels.py`
  - Log validation errors with address format (not full address for privacy)

### 8.2 User Feedback

- [ ] **Create feedback mechanism:**
  - Add "Report issue with address validation" link
  - Collect examples of false positives/negatives

- [ ] **Monitor support tickets:**
  - Track issues related to wallet address validation
  - Identify patterns of confusion

### 8.3 Regular Updates

- [ ] **Schedule quarterly review:**
  - Review new blockchain address formats
  - Update regex patterns as needed
  - Update multicoin-address-validator library

- [ ] **Monitor library updates:**
  - Check for multicoin-address-validator updates
  - Test compatibility before upgrading

---

## Success Criteria

### 9.1 Functional Requirements Met

- [x] Network detection works for all 16 supported networks
- [x] Auto-population works for high-confidence networks
- [x] Conflict detection works when user selects wrong network
- [x] Checksum validation prevents invalid addresses
- [x] Private key detection protects user security
- [x] Backend validation mirrors frontend logic

### 9.2 UX Requirements Met

- [x] Clear, helpful error messages (no jargon)
- [x] Real-time feedback (< 500ms)
- [x] Visual indicators (badges, colors)
- [x] No breaking changes to existing flow
- [x] Works on all major browsers

### 9.3 Performance Requirements Met

- [x] Validation completes in < 50ms (client-side)
- [x] No UI lag during typing
- [x] Debouncing prevents excessive computation
- [x] Bundle size increase < 25kb (gzipped)

### 9.4 Security Requirements Met

- [x] Private key detection implemented
- [x] Server-side validation implemented
- [x] No address leakage in logs
- [x] Clear security warnings for users

---

## Rollback Plan

### If Issues Arise After Deployment

- [ ] **Immediate rollback procedure:**
  1. Identify problematic phase/commit
  2. Revert Git commit: `git revert <commit-hash>`
  3. Rebuild: `npm run build`
  4. Redeploy: `gsutil -m rsync -r -d dist/ gs://www-paygateprime-com/`
  5. Invalidate cache
  6. Test rollback successful

- [ ] **Communication plan:**
  - Notify team of rollback
  - Update PROGRESS.md with issue details
  - Create BUGS.md entry if needed

- [ ] **Post-mortem:**
  - Document what went wrong
  - Identify root cause
  - Plan fix before re-deployment

---

## Notes & Considerations

### Important Reminders

- ⚠️ **Always validate server-side** - client-side validation can be bypassed
- ⚠️ **Never log full wallet addresses** - privacy concern
- ⚠️ **Test with real addresses** - regex can have subtle bugs
- ⚠️ **EVM ambiguity is unavoidable** - same address works on 4+ networks
- ⚠️ **Checksum validation requires library** - regex alone is insufficient
- ⚠️ **Private key detection is critical** - prevents user security mistakes

### Future Enhancements (Beyond Scope)

- [ ] Blockchain API verification (real-time balance check)
- [ ] Address book / saved addresses feature
- [ ] QR code scanning for mobile
- [ ] ENS / domain name resolution
- [ ] Multi-signature wallet support
- [ ] Hardware wallet integration

---

**End of Checklist**

Total Tasks: ~150+
Estimated Implementation Time: 20-30 hours (across all 4 phases)
Risk Level: Medium (with phased rollout)
Recommended Approach: Incremental deployment with monitoring between phases
