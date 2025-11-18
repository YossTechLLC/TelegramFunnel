-- ============================================================================
-- Currency to Network Data Population - PGP-LIVE Project
-- ============================================================================
-- Project: pgp-live
-- Database: telepaydb
-- Instance: pgp-live:us-central1:pgp-telepaypsql
-- Migration: 002_pgp_live - Populate currency_to_network table
-- Source: Exported from telepay-459221:telepaypsql
-- Count: 87 currency/network mappings
-- Created: 2025-11-18
-- ============================================================================

BEGIN;

INSERT INTO currency_to_network (currency, network, currency_name, network_name) VALUES
    ('AAVE', 'BSC', 'Aave', 'BNB Smart Chain'),
    ('AAVE', 'ETH', 'Aave', 'Ethereum'),
    ('ADA', 'ADA', 'Cardano', 'Cardano'),
    ('ADA', 'BSC', 'Cardano', 'BNB Smart Chain'),
    ('ARB', 'ETH', 'Arbitrum', 'Ethereum'),
    ('AVAX', 'BSC', 'Avalanche', 'BNB Smart Chain'),
    ('BCH', 'BCH', 'Bitcoin Cash', 'Bitcoin Cash'),
    ('BCH', 'BSC', 'Bitcoin Cash', 'BNB Smart Chain'),
    ('BGB', 'ETH', 'Bitget Token', 'Ethereum'),
    ('BNB', 'BSC', 'BNB', 'BNB Smart Chain'),
    ('BONK', 'BSC', 'Bonk', 'BNB Smart Chain'),
    ('BONK', 'SOL', 'Bonk', 'Solana'),
    ('BTC', 'BTC', 'Bitcoin', 'Bitcoin'),
    ('CRO', 'ETH', 'Cronos', 'Ethereum'),
    ('DAI', 'BSC', 'Dai', 'BNB Smart Chain'),
    ('DAI', 'ETH', 'Dai', 'Ethereum'),
    ('DAI', 'MATIC', 'Dai', 'Polygon'),
    ('DOGE', 'BSC', 'Dogecoin', 'BNB Smart Chain'),
    ('DOGE', 'DOGE', 'Dogecoin', 'Dogecoin'),
    ('DOGE', 'ETH', 'Dogecoin', 'Ethereum'),
    ('DOT', 'BSC', 'Polkadot', 'BNB Smart Chain'),
    ('ETC', 'BSC', 'Ethereum Classic', 'BNB Smart Chain'),
    ('ETH', 'BASE', 'Ethereum', 'Base'),
    ('ETH', 'BSC', 'Ethereum', 'BNB Smart Chain'),
    ('ETH', 'ETH', 'Ethereum', 'Ethereum'),
    ('FDUSD', 'BSC', 'First Digital USD', 'BNB Smart Chain'),
    ('FDUSD', 'ETH', 'First Digital USD', 'Ethereum'),
    ('FDUSD', 'SOL', 'First Digital USD', 'Solana'),
    ('FIL', 'BSC', 'Filecoin', 'BNB Smart Chain'),
    ('GRT', 'ETH', 'The Graph', 'Ethereum'),
    ('GRT', 'MATIC', 'The Graph', 'Polygon'),
    ('IMX', 'ETH', 'Immutable', 'Ethereum'),
    ('INJ', 'BSC', 'Injective', 'BNB Smart Chain'),
    ('INJ', 'ETH', 'Injective', 'Ethereum'),
    ('JUP', 'SOL', 'Jupiter', 'Solana'),
    ('LDO', 'ETH', 'Lido DAO', 'Ethereum'),
    ('LEO', 'ETH', 'UNUS SED LEO', 'Ethereum'),
    ('LINK', 'BSC', 'Chainlink', 'BNB Smart Chain'),
    ('LINK', 'ETH', 'Chainlink', 'Ethereum'),
    ('LINK', 'MATIC', 'Chainlink', 'Polygon'),
    ('LTC', 'BSC', 'Litecoin', 'BNB Smart Chain'),
    ('LTC', 'LTC', 'Litecoin', 'Litecoin'),
    ('MNT', 'ETH', 'Mantle', 'Ethereum'),
    ('NEAR', 'BSC', 'NEAR Protocol', 'BNB Smart Chain'),
    ('OKB', 'ETH', 'OKB', 'Ethereum'),
    ('ONDO', 'ETH', 'Ondo', 'Ethereum'),
    ('PEPE', 'ETH', 'Pepe', 'Ethereum'),
    ('QNT', 'ETH', 'Quant', 'Ethereum'),
    ('SHIB', 'BSC', 'Shiba Inu', 'BNB Smart Chain'),
    ('SHIB', 'ETH', 'Shiba Inu', 'Ethereum'),
    ('SOL', 'BSC', 'Solana', 'BNB Smart Chain'),
    ('SOL', 'ETH', 'Solana', 'Ethereum'),
    ('SOL', 'SOL', 'Solana', 'Solana'),
    ('TON', 'BSC', 'Toncoin', 'BNB Smart Chain'),
    ('TON', 'ETH', 'Toncoin', 'Ethereum'),
    ('TON', 'TON', 'Toncoin', 'Toncoin'),
    ('TRX', 'BSC', 'TRON', 'BNB Smart Chain'),
    ('TRX', 'TRX', 'TRON', 'TRON'),
    ('USD1', 'BSC', 'USD1', 'BNB Smart Chain'),
    ('USD1', 'ETH', 'USD1', 'Ethereum'),
    ('USD1', 'SOL', 'USD1', 'Solana'),
    ('USD1', 'TRX', 'USD1', 'TRON'),
    ('USDC', 'BASE', 'USD Coin', 'Base'),
    ('USDC', 'BSC', 'USD Coin', 'BNB Smart Chain'),
    ('USDC', 'ETH', 'USD Coin', 'Ethereum'),
    ('USDC', 'MATIC', 'USD Coin', 'Polygon'),
    ('USDC', 'SOL', 'USD Coin', 'Solana'),
    ('USDE', 'BSC', 'USDe', 'BNB Smart Chain'),
    ('USDE', 'ETH', 'USDe', 'Ethereum'),
    ('USDE', 'TON', 'USDe', 'Toncoin'),
    ('USDT', 'BASE', 'Tether USDt', 'Base'),
    ('USDT', 'BSC', 'Tether USDt', 'BNB Smart Chain'),
    ('USDT', 'ETH', 'Tether USDt', 'Ethereum'),
    ('USDT', 'MATIC', 'Tether USDt', 'Polygon'),
    ('USDT', 'SOL', 'Tether USDt', 'Solana'),
    ('USDT', 'TON', 'Tether USDt', 'Toncoin'),
    ('USDT', 'TRX', 'Tether USDt', 'TRON'),
    ('VET', 'BSC', 'VeChain', 'BNB Smart Chain'),
    ('WLD', 'ETH', 'Worldcoin', 'Ethereum'),
    ('WLFI', 'BSC', 'WLFI', 'BNB Smart Chain'),
    ('WLFI', 'ETH', 'WLFI', 'Ethereum'),
    ('WLFI', 'SOL', 'WLFI', 'Solana'),
    ('XLM', 'XLM', 'Stellar', 'Stellar'),
    ('XMR', 'XMR', 'Monero', 'Monero'),
    ('XRP', 'BSC', 'XRP', 'BNB Smart Chain'),
    ('XRP', 'XRP', 'Ripple', 'Ripple'),
    ('ZEC', 'ZEC', 'Zcash', 'Zcash');

COMMIT;

-- Print success message
DO $$
BEGIN
    RAISE NOTICE '✅ Currency to Network Population Complete';
    RAISE NOTICE '📊 Inserted 87 currency/network mappings';
    RAISE NOTICE '🔗 Supports all major cryptocurrencies and networks';
END $$;
