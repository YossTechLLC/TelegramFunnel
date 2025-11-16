/**
 * Type definitions for multicoin-address-validator
 * Library doesn't provide official TypeScript types
 */

declare module 'multicoin-address-validator' {
  interface WAValidator {
    validate(address: string, currency: string, networkType?: 'prod' | 'testnet'): boolean;
  }

  const validator: WAValidator;
  export default validator;
}
