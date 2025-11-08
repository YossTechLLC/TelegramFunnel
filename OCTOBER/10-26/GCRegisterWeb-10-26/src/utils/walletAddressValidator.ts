/**
 * Wallet Address Validator Utility
 * Created: 2025-11-08
 * Purpose: REGEX-based network detection and wallet address validation
 *
 * Supports 16 blockchain networks:
 * ADA, BASE, BCH, BSC, BTC, DOGE, ETH, LTC, MATIC, SOL, TON, TRX, XLM, XMR, XRP, ZEC
 */

import WAValidator from 'multicoin-address-validator';
import type { NetworkDetection } from '../types/validation';

/**
 * Detects blockchain network from wallet address format using REGEX patterns
 *
 * @param address - Wallet address string to analyze
 * @returns NetworkDetection object with networks, confidence, and ambiguity flag
 *
 * @example
 * detectNetworkFromAddress('EQD2NmD_lH5f5u1Kj3KfGyTvhZSX0Eg6qp2a5IQUKXxrJcvP')
 * // Returns: { networks: ['TON'], confidence: 'high', ambiguous: false }
 *
 * @example
 * detectNetworkFromAddress('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb')
 * // Returns: { networks: ['ETH', 'BASE', 'BSC', 'MATIC'], confidence: 'medium', ambiguous: true }
 */
export function detectNetworkFromAddress(address: string): NetworkDetection {
  const trimmed = address.trim();

  // Too short to be valid
  if (trimmed.length < 26) {
    return {
      networks: [],
      confidence: 'low',
      ambiguous: false
    };
  }

  // ========== HIGH CONFIDENCE NETWORKS (Unique formats) ==========

  // TON - Base64/Base64url with EQ/UQ prefix (mainnet only)
  // Format: EQxxxx... or UQxxxx... (48 chars total)
  // Example: EQD2NmD_lH5f5u1Kj3KfGyTvhZSX0Eg6qp2a5IQUKXxrJcvP
  if (/^(EQ|UQ)[A-Za-z0-9_-]{46}$/.test(trimmed)) {
    return {
      networks: ['TON'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Tron (TRX) - Starts with T, 34 characters
  // Format: Txxxx... (34 chars)
  // Example: TJRabPrwbZy45sbavfcjinPJC18kjpRTv8
  if (/^T[A-Za-z1-9]{33}$/.test(trimmed)) {
    return {
      networks: ['TRX'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Stellar (XLM) - Base32, starts with G, 56 characters
  // Format: Gxxxx... (56 chars, uppercase only)
  // Example: GCRRSYF5JBFPXHN5DCG65A4J3MUYE53QMQ4XMXZ3CNKWFJIJJTGMH6MZ
  if (/^G[A-Z2-7]{55}$/.test(trimmed)) {
    return {
      networks: ['XLM'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Dogecoin (DOGE) - Starts with D, 34 characters
  // Format: Dxxxx... (34 chars)
  // Example: DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L
  if (/^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$/.test(trimmed)) {
    return {
      networks: ['DOGE'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // XRP (Ripple) - Starts with r, 25-34 characters
  // Format: rxxxx... (25-34 chars)
  // Example: rN7n7otQDd6FczFgLdlqtyMVrn3HMgkd8r
  if (/^r[1-9A-HJ-NP-Za-km-z]{25,34}$/.test(trimmed)) {
    return {
      networks: ['XRP'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Monero (XMR) - Starts with 4 or 8, 95 characters
  // Format: 4xxxx... or 8xxxx... (95 chars)
  // Example: 48edfHu7V9Z84YzzMa6fUueoELZ9ZRXq9VetWzYGzKt52XU5xvqgzYnDK9URnRoJMk1j8nLwEVsaSWJ4fhdUyZijBGUicoD
  if (/^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$/.test(trimmed)) {
    return {
      networks: ['XMR'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Cardano (ADA) - Shelley addresses start with addr1
  // Format: addr1xxxx... (typically 103-104 chars)
  // Example: addr1qxy7ty6ptp9puqz...
  if (/^addr1[a-z0-9]{53,}$/.test(trimmed)) {
    return {
      networks: ['ADA'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Zcash (ZEC) - Transparent addresses start with t1
  // Format: t1xxxx... (35 chars)
  // Example: t1Vqj8v6iMEwCQ7B4UYPVqXeP5MkG7x3eMm
  if (/^t1[1-9A-HJ-NP-Za-km-z]{33}$/.test(trimmed)) {
    return {
      networks: ['ZEC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Zcash (ZEC) - Shielded addresses start with zs1
  // Format: zs1xxxx... (78 chars)
  if (/^zs1[a-z0-9]{75}$/.test(trimmed)) {
    return {
      networks: ['ZEC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Bitcoin Cash (BCH) - CashAddr format
  // Format: bitcoincash:qxxxx... or just qxxxx.../pxxxx...
  // Example: bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a
  if (/^((bitcoincash:)?[qp][a-z0-9]{41})$/.test(trimmed)) {
    return {
      networks: ['BCH'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // ========== MEDIUM CONFIDENCE NETWORKS ==========

  // EVM-Compatible Networks (CRITICAL AMBIGUITY)
  // All use identical address format: 0x + 40 hex chars
  // Networks: ETH, BASE, BSC, MATIC
  // Format: 0x + 40 hex characters
  // Example: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
  if (/^0x[a-fA-F0-9]{40}$/.test(trimmed)) {
    return {
      networks: ['ETH', 'BASE', 'BSC', 'MATIC'],
      confidence: 'medium',
      ambiguous: true
    };
  }

  // Bitcoin (BTC) - Bech32 (SegWit) addresses start with bc1
  // Format: bc1xxxx... (42-62 chars)
  // Example: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq
  if (/^bc1[a-z0-9]{39,59}$/.test(trimmed)) {
    return {
      networks: ['BTC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Litecoin (LTC) - Bech32 addresses start with ltc1
  // Format: ltc1xxxx... (42-62 chars)
  // Example: ltc1qar0srrr7xfkvy5l643lydnw9re59gtzzaxx3c6
  if (/^ltc1[a-z0-9]{39,59}$/.test(trimmed)) {
    return {
      networks: ['LTC'],
      confidence: 'high',
      ambiguous: false
    };
  }

  // Solana (SOL) - Base58, 32-44 characters
  // Format: No specific prefix (can overlap with Bitcoin)
  // Example: 7EqQdEUu5z8F5M9VzX6M8vBxkq8z8F5M9VzX6M8vBxkq
  // Heuristic: Longer addresses (40+ chars) are more likely Solana
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(trimmed)) {
    if (trimmed.length >= 40) {
      return {
        networks: ['SOL'],
        confidence: 'medium',
        ambiguous: false
      };
    } else {
      // 32-39 chars could be SOL or BTC legacy
      return {
        networks: ['SOL', 'BTC'],
        confidence: 'low',
        ambiguous: true
      };
    }
  }

  // ========== LOW CONFIDENCE NETWORKS (Overlapping formats) ==========

  // Bitcoin (BTC) / Bitcoin Cash (BCH) / Litecoin (LTC) - Legacy format
  // Starts with 1, 3, L, or M (26-34 chars)
  // These formats overlap between networks
  if (/^[13LM][a-km-zA-HJ-NP-Z1-9]{25,34}$/.test(trimmed)) {
    if (trimmed.startsWith('1') || trimmed.startsWith('3')) {
      // Could be BTC, BCH, or LTC
      return {
        networks: ['BTC', 'BCH', 'LTC'],
        confidence: 'low',
        ambiguous: true
      };
    } else if (trimmed.startsWith('L') || trimmed.startsWith('M')) {
      // Likely LTC
      return {
        networks: ['LTC'],
        confidence: 'medium',
        ambiguous: false
      };
    }
  }

  // No match found
  return {
    networks: [],
    confidence: 'low',
    ambiguous: false
  };
}

/**
 * Detects if input appears to be a private key (security check)
 *
 * @param input - String to check for private key patterns
 * @returns true if input matches known private key formats
 *
 * @example
 * detectPrivateKey('SA...') // true (Stellar secret key)
 * detectPrivateKey('0x742d35Cc...') // false (public address)
 */
export function detectPrivateKey(input: string): boolean {
  const trimmed = input.trim();

  // Stellar secret key - Starts with S, 56 characters
  // Format: Sxxxx... (Base32 encoded)
  if (/^S[A-Z2-7]{55}$/.test(trimmed)) {
    return true;
  }

  // Bitcoin WIF (Wallet Import Format)
  // Starts with 5, K, or L (51-52 characters)
  if (/^[5KL][1-9A-HJ-NP-Za-km-z]{50,51}$/.test(trimmed)) {
    return true;
  }

  // Ethereum private key (64 hex characters, with or without 0x prefix)
  if (/^(0x)?[a-fA-F0-9]{64}$/.test(trimmed)) {
    return true;
  }

  return false;
}

/**
 * Map our network codes to multicoin-address-validator currency codes
 * Used for checksum validation
 */
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

/**
 * Validates wallet address checksum using multicoin-address-validator library
 *
 * @param address - Wallet address to validate
 * @param network - Network code (e.g., 'ETH', 'BTC', 'TON')
 * @returns true if address has valid checksum, false otherwise
 *
 * @example
 * validateAddressChecksum('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb', 'ETH')
 * // Returns: true (if checksum is valid)
 */
export function validateAddressChecksum(address: string, network: string): boolean {
  const validatorCurrency = NETWORK_TO_VALIDATOR_MAP[network];

  if (!validatorCurrency) {
    console.warn(`⚠️ No validator mapping for network: ${network}`);
    return false;
  }

  try {
    return WAValidator.validate(address, validatorCurrency, 'prod');
  } catch (error) {
    console.error('❌ Checksum validation error:', error);
    return false;
  }
}

/**
 * Comprehensive wallet address validation
 * Validates both format (REGEX) and checksum
 *
 * @param address - Wallet address to validate
 * @param network - Selected network code
 * @returns Object with validation result and error message
 *
 * @example
 * validateWalletAddress('TJRabPrwbZy45sbavfcjinPJC18kjpRTv8', 'TRX')
 * // Returns: { valid: true, error: null }
 */
export function validateWalletAddress(
  address: string,
  network: string
): { valid: boolean; error: string | null } {
  // Check format first
  const detection = detectNetworkFromAddress(address);

  if (detection.networks.length === 0) {
    return {
      valid: false,
      error: 'Invalid wallet address format. Please verify your address.'
    };
  }

  // Check if format matches selected network
  if (!detection.networks.includes(network)) {
    return {
      valid: false,
      error: `Wallet address format does not match selected network (${network}). Address appears to be for: ${detection.networks.join(' or ')}`
    };
  }

  // Checksum validation
  const checksumValid = validateAddressChecksum(address, network);

  if (!checksumValid) {
    return {
      valid: false,
      error: `Invalid wallet address checksum for ${network} network. Please verify your address is correct.`
    };
  }

  return {
    valid: true,
    error: null
  };
}
