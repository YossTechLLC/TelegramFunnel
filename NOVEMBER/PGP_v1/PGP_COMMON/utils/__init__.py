"""
Utility modules for PGP_v1 services.
"""
from PGP_COMMON.utils.crypto_pricing import CryptoPricingClient
from PGP_COMMON.utils.changenow_client import ChangeNowClient
from PGP_COMMON.utils.webhook_auth import (
    verify_hmac_hex_signature,
    verify_sha256_signature,
    verify_sha512_signature
)
from PGP_COMMON.utils.ip_extraction import (
    get_real_client_ip,
    get_all_forwarded_ips,
    validate_ip_format,
    is_private_ip
)
from PGP_COMMON.utils.error_sanitizer import (
    generate_error_id,
    sanitize_error_for_user,
    sanitize_sql_error,
    sanitize_authentication_error,
    sanitize_validation_error,
    log_error_with_context,
    get_environment,
    should_show_stack_trace
)
from PGP_COMMON.utils.error_responses import (
    create_error_response,
    create_validation_error_response,
    create_authentication_error_response,
    create_authorization_error_response,
    create_not_found_error_response,
    create_rate_limit_error_response,
    create_database_error_response,
    handle_flask_exception,
    create_success_response
)
from PGP_COMMON.utils.wallet_validation import (
    validate_wallet_address,
    validate_ethereum_address,
    validate_bitcoin_address,
    get_checksum_address,
    WalletValidationError
)
from PGP_COMMON.utils.redis_client import (
    NonceTracker,
    NonceTrackerError,
    get_nonce_tracker
)
from PGP_COMMON.utils.idempotency import (
    IdempotencyManager
)
from PGP_COMMON.utils.validation import (
    ValidationError,
    validate_telegram_user_id,
    validate_telegram_channel_id,
    validate_payment_id,
    validate_order_id_format,
    validate_crypto_amount,
    validate_payment_status,
    validate_crypto_address
)

__all__ = [
    'CryptoPricingClient',
    'ChangeNowClient',
    'verify_hmac_hex_signature',
    'verify_sha256_signature',
    'verify_sha512_signature',
    'get_real_client_ip',
    'get_all_forwarded_ips',
    'validate_ip_format',
    'is_private_ip',
    'generate_error_id',
    'sanitize_error_for_user',
    'sanitize_sql_error',
    'sanitize_authentication_error',
    'sanitize_validation_error',
    'log_error_with_context',
    'get_environment',
    'should_show_stack_trace',
    'create_error_response',
    'create_validation_error_response',
    'create_authentication_error_response',
    'create_authorization_error_response',
    'create_not_found_error_response',
    'create_rate_limit_error_response',
    'create_database_error_response',
    'handle_flask_exception',
    'create_success_response',
    'validate_wallet_address',
    'validate_ethereum_address',
    'validate_bitcoin_address',
    'get_checksum_address',
    'WalletValidationError',
    'NonceTracker',
    'NonceTrackerError',
    'get_nonce_tracker',
    'IdempotencyManager',
    'ValidationError',
    'validate_telegram_user_id',
    'validate_telegram_channel_id',
    'validate_payment_id',
    'validate_order_id_format',
    'validate_crypto_amount',
    'validate_payment_status',
    'validate_crypto_address'
]
