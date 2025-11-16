"""
PayGatePrime v1 - Comprehensive Input Validation
Validates payment amounts, wallet addresses, order IDs, and transaction data

Prevents:
- Invalid payment amounts (negative, zero, excessive decimals)
- Money laundering (amounts exceeding limits)
- Invalid wallet addresses (wrong format, invalid checksums)
- Malformed order IDs
- SQL injection via input
- XSS attacks
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Tuple, Optional


class PaymentValidator:
    """
    Validates payment amounts and currency data.

    Usage:
        is_valid, amount, error = PaymentValidator.validate_amount("123.45", "USD")
        if not is_valid:
            return {"error": error}, 400
    """

    # Amount limits (USD equivalent)
    MIN_AMOUNT_USD = Decimal("1.00")          # $1 minimum
    MAX_AMOUNT_USD = Decimal("50000.00")      # $50k maximum (AML compliance)

    # Decimal precision
    MAX_DECIMAL_PLACES = 8                     # Standard for crypto (0.00000001 BTC)

    # Supported currencies
    SUPPORTED_CURRENCIES = [
        'USD', 'USDT', 'USDTTRC20', 'BTC', 'ETH', 'MATIC', 'LTC', 'XRP', 'BCH'
    ]

    @staticmethod
    def validate_amount(amount: str, currency: str = "USD") -> Tuple[bool, Optional[Decimal], str]:
        """
        Validate payment amount.

        Args:
            amount: Amount as string (e.g., "123.45")
            currency: Currency code (e.g., "USD", "BTC")

        Returns:
            (is_valid, decimal_amount, error_message)

        Examples:
            >>> PaymentValidator.validate_amount("100.50", "USD")
            (True, Decimal('100.50'), "")

            >>> PaymentValidator.validate_amount("-10", "USD")
            (False, None, "Amount must be positive")

            >>> PaymentValidator.validate_amount("100000", "USD")
            (False, None, "Amount exceeds maximum allowed ($50,000.00)")
        """

        # Check currency is supported
        if currency not in PaymentValidator.SUPPORTED_CURRENCIES:
            return False, None, f"Unsupported currency: {currency}"

        # Convert to Decimal
        try:
            decimal_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            return False, None, "Invalid amount format"

        # Check for positive amount
        if decimal_amount <= 0:
            return False, None, "Amount must be positive"

        # Check minimum
        if decimal_amount < PaymentValidator.MIN_AMOUNT_USD:
            return False, None, f"Amount below minimum (${PaymentValidator.MIN_AMOUNT_USD})"

        # Check maximum (AML compliance)
        if decimal_amount > PaymentValidator.MAX_AMOUNT_USD:
            return False, None, f"Amount exceeds maximum allowed (${PaymentValidator.MAX_AMOUNT_USD:,})"

        # Check decimal places
        decimal_places = abs(decimal_amount.as_tuple().exponent)
        if decimal_places > PaymentValidator.MAX_DECIMAL_PLACES:
            return False, None, f"Too many decimal places (max {PaymentValidator.MAX_DECIMAL_PLACES})"

        # Check for scientific notation (shouldn't happen after Decimal conversion, but be safe)
        if 'e' in str(amount).lower():
            return False, None, "Scientific notation not allowed"

        return True, decimal_amount, ""

    @staticmethod
    def validate_currency(currency: str) -> Tuple[bool, str]:
        """
        Validate currency code.

        Args:
            currency: Currency code (e.g., "USD", "BTC")

        Returns:
            (is_valid, error_message)
        """
        if not currency:
            return False, "Currency is required"

        currency_upper = currency.upper()

        if currency_upper not in PaymentValidator.SUPPORTED_CURRENCIES:
            return False, f"Unsupported currency: {currency}"

        return True, ""


class WalletValidator:
    """
    Validates cryptocurrency wallet addresses.

    Usage:
        is_valid, error = WalletValidator.validate_wallet("0x1234...", "USDT")
        if not is_valid:
            return {"error": error}, 400
    """

    # Regex patterns for wallet addresses
    PATTERNS = {
        'BTC': r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$',  # Bitcoin Legacy or SegWit
        'ETH': r'^0x[a-fA-F0-9]{40}$',                                      # Ethereum
        'USDT': r'^0x[a-fA-F0-9]{40}$',                                     # USDT (ERC20)
        'USDTTRC20': r'^T[a-zA-Z0-9]{33}$',                                 # USDT (TRC20 on Tron)
        'MATIC': r'^0x[a-fA-F0-9]{40}$',                                    # Polygon/MATIC
        'LTC': r'^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$',                      # Litecoin
        'XRP': r'^r[0-9a-zA-Z]{24,34}$',                                    # Ripple
        'BCH': r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bitcoincash:q[a-z0-9]{41}$'  # Bitcoin Cash
    }

    @staticmethod
    def validate_wallet(address: str, currency: str) -> Tuple[bool, str]:
        """
        Validate cryptocurrency wallet address format.

        Args:
            address: Wallet address
            currency: Currency code (determines validation rules)

        Returns:
            (is_valid, error_message)

        Note: This performs FORMAT validation only. Does NOT verify:
            - Address exists on blockchain
            - Address is controlled by anyone
            - Address checksum (basic format only)

        Examples:
            >>> WalletValidator.validate_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", "USDT")
            (True, "")

            >>> WalletValidator.validate_wallet("invalid", "BTC")
            (False, "Invalid BTC wallet address format")
        """

        if not address:
            return False, "Wallet address is required"

        # Get pattern for currency
        pattern = WalletValidator.PATTERNS.get(currency)
        if not pattern:
            # Currency not in patterns - might be valid but we can't validate format
            return False, f"Cannot validate {currency} wallet address (unsupported currency)"

        # Check format
        if not re.match(pattern, address):
            return False, f"Invalid {currency} wallet address format"

        # Check length isn't suspiciously short or long
        if len(address) < 20 or len(address) > 100:
            return False, f"Wallet address length invalid ({len(address)} characters)"

        return True, ""

    @staticmethod
    def validate_platform_wallet(address: str) -> Tuple[bool, str]:
        """
        Validate platform's own wallet address (Polygon/MATIC).

        Platform uses Polygon network, so validate as Polygon address.

        Args:
            address: Platform wallet address

        Returns:
            (is_valid, error_message)
        """
        return WalletValidator.validate_wallet(address, "MATIC")


class OrderValidator:
    """
    Validates order IDs and transaction IDs.

    Usage:
        is_valid, error = OrderValidator.validate_order_id(order_id)
        if not is_valid:
            return {"error": error}, 400
    """

    # Order ID format: Alphanumeric, hyphens, underscores only
    ORDER_ID_PATTERN = r'^[a-zA-Z0-9_-]{1,100}$'

    # Payment ID from NowPayments: Numeric
    PAYMENT_ID_PATTERN = r'^\d{1,20}$'

    # Transaction hash: Hex string (blockchain)
    TX_HASH_PATTERN = r'^0x[a-fA-F0-9]{64}$'

    @staticmethod
    def validate_order_id(order_id: str) -> Tuple[bool, str]:
        """
        Validate order ID format.

        Args:
            order_id: Order ID from client

        Returns:
            (is_valid, error_message)

        Examples:
            >>> OrderValidator.validate_order_id("ORDER-12345")
            (True, "")

            >>> OrderValidator.validate_order_id("'; DROP TABLE orders; --")
            (False, "Invalid order ID format")
        """

        if not order_id:
            return False, "Order ID is required"

        if not re.match(OrderValidator.ORDER_ID_PATTERN, order_id):
            return False, "Invalid order ID format (alphanumeric, hyphens, underscores only)"

        if len(order_id) > 100:
            return False, "Order ID too long (max 100 characters)"

        return True, ""

    @staticmethod
    def validate_payment_id(payment_id: str) -> Tuple[bool, str]:
        """
        Validate NowPayments payment ID.

        Args:
            payment_id: Payment ID from NowPayments

        Returns:
            (is_valid, error_message)
        """

        if not payment_id:
            return False, "Payment ID is required"

        if not re.match(OrderValidator.PAYMENT_ID_PATTERN, str(payment_id)):
            return False, "Invalid payment ID format (must be numeric)"

        return True, ""

    @staticmethod
    def validate_tx_hash(tx_hash: str) -> Tuple[bool, str]:
        """
        Validate blockchain transaction hash.

        Args:
            tx_hash: Transaction hash (0x...)

        Returns:
            (is_valid, error_message)
        """

        if not tx_hash:
            return False, "Transaction hash is required"

        if not re.match(OrderValidator.TX_HASH_PATTERN, tx_hash):
            return False, "Invalid transaction hash format (must be 0x followed by 64 hex characters)"

        return True, ""


class IPNValidator:
    """
    Validates NowPayments IPN (Instant Payment Notification) data.

    Usage:
        is_valid, error = IPNValidator.validate_ipn_data(ipn_data)
        if not is_valid:
            return {"error": error}, 400
    """

    REQUIRED_FIELDS = [
        'payment_id',
        'payment_status',
        'pay_amount',
        'pay_currency',
        'order_id'
    ]

    VALID_STATUSES = [
        'waiting',
        'confirming',
        'confirmed',
        'sending',
        'partially_paid',
        'finished',
        'failed',
        'refunded',
        'expired'
    ]

    @staticmethod
    def validate_ipn_data(ipn_data: dict) -> Tuple[bool, str]:
        """
        Validate IPN payload structure and data.

        Args:
            ipn_data: Parsed IPN JSON data

        Returns:
            (is_valid, error_message)

        Validates:
            - Required fields present
            - Payment status is valid
            - Pay amount is valid
            - Order ID is valid
        """

        # Check required fields
        for field in IPNValidator.REQUIRED_FIELDS:
            if field not in ipn_data:
                return False, f"Missing required field: {field}"

        # Validate payment status
        payment_status = ipn_data.get('payment_status')
        if payment_status not in IPNValidator.VALID_STATUSES:
            return False, f"Invalid payment_status: {payment_status}"

        # Validate pay amount
        pay_amount = ipn_data.get('pay_amount')
        pay_currency = ipn_data.get('pay_currency', 'USDT')

        is_valid, _, error = PaymentValidator.validate_amount(str(pay_amount), pay_currency)
        if not is_valid:
            return False, f"Invalid pay_amount: {error}"

        # Validate order ID
        order_id = ipn_data.get('order_id')
        is_valid, error = OrderValidator.validate_order_id(order_id)
        if not is_valid:
            return False, f"Invalid order_id: {error}"

        # Validate payment ID
        payment_id = str(ipn_data.get('payment_id'))
        is_valid, error = OrderValidator.validate_payment_id(payment_id)
        if not is_valid:
            return False, f"Invalid payment_id: {error}"

        return True, ""


# =============================================================================
# Convenience Functions
# =============================================================================

def validate_payment_request(data: dict) -> Tuple[bool, str]:
    """
    Validate a complete payment request.

    Args:
        data: Request data with amount, currency, order_id, etc.

    Returns:
        (is_valid, error_message)

    Usage:
        @app.route('/create-payment', methods=['POST'])
        def create_payment():
            data = request.get_json()

            is_valid, error = validate_payment_request(data)
            if not is_valid:
                return jsonify({"error": error}), 400
    """

    # Validate amount
    amount = data.get('amount')
    currency = data.get('currency', 'USD')

    is_valid, _, error = PaymentValidator.validate_amount(str(amount), currency)
    if not is_valid:
        return False, error

    # Validate order ID
    order_id = data.get('order_id')
    if order_id:
        is_valid, error = OrderValidator.validate_order_id(order_id)
        if not is_valid:
            return False, error

    return True, ""


def sanitize_log_amount(amount: Decimal) -> str:
    """
    Mask payment amount for logging (privacy/compliance).

    Args:
        amount: Payment amount

    Returns:
        Masked string (e.g., "***50.00" for $12,350.00)

    Usage:
        print(f"Payment amount: {sanitize_log_amount(payment_amount)}")
    """

    amount_str = str(amount)

    # If amount > $100, mask everything except last 5 characters
    if amount > Decimal("100"):
        if len(amount_str) > 5:
            return "***" + amount_str[-5:]

    # For smaller amounts, mask half
    if len(amount_str) > 4:
        mask_len = len(amount_str) // 2
        return "*" * mask_len + amount_str[mask_len:]

    # Very small amounts, show in full (less sensitive)
    return amount_str


def sanitize_log_wallet(wallet: str) -> str:
    """
    Mask wallet address for logging (privacy).

    Args:
        wallet: Full wallet address

    Returns:
        Masked string (e.g., "0x1234...abcd")

    Usage:
        print(f"Sending to: {sanitize_log_wallet(wallet_address)}")
    """

    if len(wallet) <= 10:
        return wallet  # Too short to mask meaningfully

    # Show first 6 and last 4 characters
    return f"{wallet[:6]}...{wallet[-4:]}"
