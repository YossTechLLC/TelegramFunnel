/**
 * Wallet Address Validation Types
 * Created: 2025-11-08
 * Purpose: Type definitions for wallet address validation and network detection
 */

/**
 * Network detection result interface
 */
export interface NetworkDetection {
  /** Possible blockchain network codes (e.g., ['ETH', 'BASE', 'BSC', 'MATIC']) */
  networks: string[];

  /** Confidence level of the detection */
  confidence: 'high' | 'medium' | 'low';

  /** True if multiple networks are possible for this address format */
  ambiguous: boolean;
}

/**
 * Validation state for wallet address input
 */
export interface ValidationState {
  /** Warning message to display (e.g., format issues, conflicts) */
  warning: string;

  /** Success message to display (e.g., successful network detection) */
  success: string;

  /** Error message to display (e.g., invalid format, security issues) */
  error: string;
}

/**
 * Network mapping for multicoin-address-validator library
 */
export type NetworkMap = Record<string, string>;
