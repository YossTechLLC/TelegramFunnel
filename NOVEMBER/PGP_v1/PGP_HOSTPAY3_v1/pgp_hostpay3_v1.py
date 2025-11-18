#!/usr/bin/env python
"""
PGP_HOSTPAY3_v1: ETH Payment Executor Service
Receives payment execution requests from PGP_HOSTPAY1_v1, executes ETH payments
with 3-ATTEMPT RETRY logic, and returns response back to PGP_HOSTPAY1_v1.

NEW: Implements 3-attempt retry limit with error classification and failed transaction storage.
- Attempt 1-2: Retry with 60s delay via Cloud Tasks
- Attempt 3: Store in failed_transactions table and send alert
"""
import time
from flask import Flask, request, abort, jsonify

# Import service modules
from config_manager import ConfigManager
from token_manager import TokenManager
from database_manager import DatabaseManager
from cloudtasks_client import CloudTasksClient
from wallet_manager import WalletManager, TOKEN_CONFIGS
from error_classifier import ErrorClassifier
from alerting import AlertingService

from PGP_COMMON.logging import setup_logger
logger = setup_logger(__name__)
# Initialize logger

app = Flask(__name__)

# Initialize managers
logger.info(f"🚀 [APP] Initializing PGP_HOSTPAY3_v1 ETH Payment Executor Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize token manager
try:
    # Note: PGP_HOSTPAY3_v1 only needs internal signing key
    tps_hostpay_key = config.get('success_url_signing_key')  # Use same key for both
    internal_key = config.get('success_url_signing_key')

    if not internal_key:
        raise ValueError("SUCCESS_URL_SIGNING_KEY not available")

    token_manager = TokenManager(tps_hostpay_key, internal_key)
    logger.info(f"✅ [APP] Token manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize token manager: {e}", exc_info=True)
    token_manager = None

# Initialize wallet manager
try:
    wallet_address = config.get('host_wallet_address')
    private_key = config.get('host_wallet_private_key')
    rpc_url = config.get('ethereum_rpc_url')
    alchemy_api_key = config.get('ethereum_rpc_url_api')

    if not wallet_address or not private_key or not rpc_url:
        raise ValueError("Wallet configuration incomplete")

    wallet_manager = WalletManager(wallet_address, private_key, rpc_url, alchemy_api_key)
    logger.info(f"✅ [APP] Wallet manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize wallet manager: {e}", exc_info=True)
    wallet_manager = None

# Initialize database manager
try:
    instance_connection_name = config.get('instance_connection_name')
    db_name = config.get('db_name')
    db_user = config.get('db_user')
    db_password = config.get('db_password')

    if not all([instance_connection_name, db_name, db_user, db_password]):
        raise ValueError("Database configuration incomplete")

    db_manager = DatabaseManager(instance_connection_name, db_name, db_user, db_password)
    logger.info(f"✅ [APP] Database manager initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize database manager: {e}", exc_info=True)
    db_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')

    if not project_id or not location:
        raise ValueError("Cloud Tasks configuration incomplete")

    cloudtasks_client = CloudTasksClient(project_id, location)
    logger.info(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}", exc_info=True)
    cloudtasks_client = None

# Initialize Alerting Service (NEW)
try:
    alerting_enabled_str = config.get('alerting_enabled', 'true')
    alerting_enabled = alerting_enabled_str.lower() == 'true'
    slack_webhook = config.get('slack_alert_webhook')  # Optional

    alerting_service = AlertingService(
        slack_webhook_url=slack_webhook,
        alerting_enabled=alerting_enabled
    )
    logger.info(f"✅ [APP] Alerting service initialized (enabled: {alerting_enabled})")
except Exception as e:
    logger.error(f"❌ [APP] Failed to initialize alerting service: {e}", exc_info=True)
    alerting_service = None


# ============================================================================
# MAIN ENDPOINT: POST / - Receives request from PGP_HOSTPAY1_v1
# ============================================================================

@app.route("/", methods=["POST"])
def execute_eth_payment():
    """
    Main endpoint for executing ETH payments with 3-ATTEMPT RETRY LIMIT.

    NEW FLOW:
    1. Decrypt token from PGP_HOSTPAY1_v1 (or self-retry)
    2. Extract payment details + attempt_count
    3. Check attempt limit (>3 = skip duplicate Cloud Tasks retry)
    4. Execute ETH payment (SINGLE ATTEMPT - no infinite retry)
    5. On success: Log to database, encrypt response, send to PGP_HOSTPAY1_v1
    6. On failure:
       a. Classify error (retryable vs permanent)
       b. If attempt < 3: Re-encrypt with incremented count, enqueue self-retry
       c. If attempt >= 3: Store in failed_transactions, send alert, stop

    Returns:
        JSON response with status (always 200 to prevent Cloud Tasks auto-retry)
    """
    try:
        logger.info(f"🎯 [ENDPOINT] Payment execution request received")

        # Parse JSON payload
        try:
            request_data = request.get_json()
            if not request_data:
                abort(400, "Invalid JSON payload")
        except Exception as e:
            logger.error(f"❌ [ENDPOINT] JSON parsing error: {e}", exc_info=True)
            abort(400, "Malformed JSON payload")

        token = request_data.get('token')
        if not token:
            logger.error(f"❌ [ENDPOINT] Missing token", exc_info=True)
            abort(400, "Missing token")

        # Decrypt token
        if not token_manager:
            logger.error(f"❌ [ENDPOINT] Token manager not available")
            abort(500, "Service configuration error")

        try:
            decrypted_data = token_manager.decrypt_pgp_hostpay1_to_pgp_hostpay3_token(token)
            if not decrypted_data:
                logger.error(f"❌ [ENDPOINT] Failed to decrypt token")
                abort(401, "Invalid token")

            unique_id = decrypted_data['unique_id']
            cn_api_id = decrypted_data['cn_api_id']
            from_currency = decrypted_data['from_currency']
            from_network = decrypted_data['from_network']
            from_amount = decrypted_data.get('from_amount', 0.0)  # Backward compat (old field)
            actual_eth_amount = decrypted_data.get('actual_eth_amount', 0.0)  # ✅ ADDED: ACTUAL ETH
            estimated_eth_amount = decrypted_data.get('estimated_eth_amount', 0.0)  # ✅ ADDED: Estimate
            payin_address = decrypted_data['payin_address']
            context = decrypted_data.get('context', 'instant')

            # NEW: Extract retry tracking fields
            attempt_count = decrypted_data.get('attempt_count', 1)
            first_attempt_at = decrypted_data.get('first_attempt_at', int(time.time()))
            last_error_code = decrypted_data.get('last_error_code')

            # ✅ CRITICAL: Determine payment amount (ACTUAL or fallback to estimate)
            if actual_eth_amount > 0:
                payment_amount = actual_eth_amount
                logger.info(f"✅ [ENDPOINT] Using ACTUAL ETH from NowPayments: {payment_amount}")
            elif estimated_eth_amount > 0:
                payment_amount = estimated_eth_amount
                logger.warning(f"⚠️ [ENDPOINT] Using ESTIMATED ETH (actual not available): {payment_amount}")
            elif from_amount > 0:
                payment_amount = from_amount
                logger.warning(f"⚠️ [ENDPOINT] Using legacy from_amount (backward compat): {payment_amount}")
            else:
                logger.error(f"❌ [ENDPOINT] No valid amount found in token!")
                abort(400, "Invalid payment amount")

            logger.info(f"✅ [ENDPOINT] Token decoded successfully")
            logger.info(f"🔢 [ENDPOINT] Attempt #{attempt_count}/3")
            logger.info(f"📋 [ENDPOINT] Context: {context}")
            logger.debug(f"🆔 [ENDPOINT] Unique ID: {unique_id}")
            logger.debug(f"🆔 [ENDPOINT] CN API ID: {cn_api_id}")
            logger.info(f"💰 [ENDPOINT] Currency: {from_currency.upper()}")
            logger.info(f"💎 [ENDPOINT] ACTUAL: {actual_eth_amount} {from_currency.upper()} (from NowPayments)")
            logger.debug(f"📊 [ENDPOINT] ESTIMATED: {estimated_eth_amount} {from_currency.upper()} (from ChangeNow)")
            logger.info(f"💰 [ENDPOINT] PAYMENT AMOUNT: {payment_amount} {from_currency.upper()}")
            logger.info(f"🏦 [ENDPOINT] Payin Address: {payin_address}")
            if last_error_code:
                logger.warning(f"⚠️ [ENDPOINT] Previous error: {last_error_code}")

        except Exception as e:
            logger.error(f"❌ [ENDPOINT] Token validation error: {e}", exc_info=True)
            abort(400, f"Token error: {e}")

        # NEW: Check attempt limit (prevent Cloud Tasks duplicate retry)
        if attempt_count > 3:
            logger.warning(f"⚠️ [ENDPOINT] Attempt count exceeds limit - skipping (Cloud Tasks retry bug)")
            return jsonify({
                "status": "skipped",
                "reason": "attempt_limit_exceeded",
                "unique_id": unique_id
            }), 200

        # Execute payment (SINGLE ATTEMPT - NO INFINITE RETRY)
        if not wallet_manager:
            logger.error(f"❌ [ENDPOINT] Wallet manager not available")
            abort(500, "Wallet manager unavailable")

        # ============================================================================
        # CURRENCY TYPE DETECTION & BALANCE CHECKING
        # ============================================================================

        logger.debug(f"🔍 [ENDPOINT] Detecting currency type: {from_currency}")

        # Determine if this is native ETH or ERC-20 token
        if from_currency.lower() == 'eth':
            # Native ETH transfer
            currency_type = 'native'
            logger.info(f"💎 [ENDPOINT] Currency type: NATIVE ETH")

            # Check ETH balance
            logger.debug(f"🔍 [ENDPOINT] Checking ETH balance...")
            wallet_balance = wallet_manager.get_wallet_balance()
            balance_label = "ETH"

        elif from_currency.lower() in TOKEN_CONFIGS:
            # ERC-20 token transfer
            currency_type = 'erc20'
            token_config = TOKEN_CONFIGS[from_currency.lower()]
            logger.info(f"💎 [ENDPOINT] Currency type: ERC-20 TOKEN ({token_config['name']})")
            logger.info(f"📝 [ENDPOINT] Contract: {token_config['address']}")
            logger.info(f"🔢 [ENDPOINT] Decimals: {token_config['decimals']}")

            # Check ERC-20 token balance
            logger.debug(f"🔍 [ENDPOINT] Checking {from_currency.upper()} balance...")
            wallet_balance = wallet_manager.get_erc20_balance(
                token_contract_address=token_config['address'],
                token_decimals=token_config['decimals']
            )
            balance_label = from_currency.upper()

        else:
            # Unsupported currency
            error_msg = f"Unsupported currency: {from_currency}"
            logger.error(f"❌ [ENDPOINT] {error_msg}")
            abort(400, error_msg)

        # Validate sufficient balance
        if wallet_balance < payment_amount:
            error_msg = f"Insufficient funds: need {payment_amount} {balance_label}, have {wallet_balance} {balance_label}"
            logger.error(f"❌ [ENDPOINT] {error_msg}")
            abort(400, error_msg)
        else:
            logger.info(f"✅ [ENDPOINT] Sufficient balance: {wallet_balance} {balance_label} >= {payment_amount} {balance_label}")

        # ============================================================================
        # PAYMENT EXECUTION - Route based on currency type
        # ============================================================================

        logger.info(f"💰 [ENDPOINT] Executing {balance_label} payment (attempt {attempt_count}/3)")
        logger.info(f"💎 [ENDPOINT] Amount to send: {payment_amount} {balance_label}")

        # NEW: Wrap payment execution in try/except to catch failures
        try:
            if currency_type == 'native':
                # Native ETH transfer
                logger.info(f"🔀 [ENDPOINT] Routing to native ETH transfer method")
                tx_result = wallet_manager.send_eth_payment_with_infinite_retry(
                    to_address=payin_address,
                    amount=payment_amount,
                    unique_id=unique_id
                )

            elif currency_type == 'erc20':
                # ERC-20 token transfer
                logger.info(f"🔀 [ENDPOINT] Routing to ERC-20 token transfer method")
                tx_result = wallet_manager.send_erc20_token(
                    token_contract_address=token_config['address'],
                    to_address=payin_address,
                    amount=payment_amount,
                    token_decimals=token_config['decimals'],
                    unique_id=unique_id
                )

            else:
                raise Exception(f"Unknown currency type: {currency_type}")

            # Validate result
            if not tx_result or tx_result.get('status') != 'success':
                raise Exception(f"Payment returned invalid result: {tx_result}")

            # ========================================================================
            # SUCCESS PATH
            # ========================================================================
            logger.info(f"✅ [ENDPOINT] Payment successful after {attempt_count} attempt(s)")
            logger.info(f"🔗 [ENDPOINT] TX Hash: {tx_result['tx_hash']}")
            logger.debug(f"📊 [ENDPOINT] TX Status: {tx_result['status']}")
            logger.info(f"⛽ [ENDPOINT] Gas Used: {tx_result['gas_used']}")
            logger.info(f"📦 [ENDPOINT] Block Number: {tx_result['block_number']}")

            # Log to database (ONLY after successful payment)
            if not db_manager:
                logger.warning(f"⚠️ [ENDPOINT] Database manager not available - skipping database log")
            else:
                try:
                    db_success = db_manager.insert_hostpay_transaction(
                        unique_id=unique_id,
                        cn_api_id=cn_api_id,
                        from_currency=from_currency,
                        from_network=from_network,
                        from_amount=from_amount,
                        payin_address=payin_address,
                        is_complete=True,
                        tx_hash=tx_result['tx_hash'],
                        tx_status=tx_result['status'],
                        gas_used=tx_result['gas_used'],
                        block_number=tx_result['block_number'],
                        actual_eth_amount=actual_eth_amount  # ✅ NEW: Pass ACTUAL ETH from NowPayments
                    )

                    if db_success:
                        logger.info(f"✅ [ENDPOINT] Database: Successfully logged payment")
                    else:
                        logger.warning(f"⚠️ [ENDPOINT] Database: Failed to log payment (non-fatal)")

                except Exception as e:
                    logger.error(f"❌ [ENDPOINT] Database error: {e} (non-fatal)", exc_info=True)

            # Encrypt response token
            encrypted_response_token = token_manager.encrypt_pgp_hostpay3_to_pgp_hostpay1_token(
                unique_id=unique_id,
                cn_api_id=cn_api_id,
                tx_hash=tx_result['tx_hash'],
                tx_status=tx_result['status'],
                gas_used=tx_result['gas_used'],
                block_number=tx_result['block_number']
            )

            if not encrypted_response_token:
                logger.error(f"❌ [ENDPOINT] Failed to encrypt response token")
                abort(500, "Token encryption failed")

            # Enqueue response based on context (NEW: Conditional routing)
            if not cloudtasks_client:
                logger.error(f"❌ [ENDPOINT] Cloud Tasks client not available")
                abort(500, "Cloud Tasks unavailable")

            # Determine routing based on context
            if context == 'threshold':
                # Route to PGP_ACCUMULATOR for threshold payouts
                logger.info(f"🎯 [ENDPOINT] Context: threshold → Routing to PGP_ACCUMULATOR")

                pgp_accumulator_response_queue = config.get('pgp_accumulator_response_queue')
                pgp_accumulator_url = config.get('pgp_accumulator_url')

                if not pgp_accumulator_response_queue or not pgp_accumulator_url:
                    logger.error(f"❌ [ENDPOINT] PGP_ACCUMULATOR configuration missing")
                    abort(500, "Service configuration error")

                # Target the /swap-executed endpoint
                target_url = f"{pgp_accumulator_url}/swap-executed"
                queue_name = pgp_accumulator_response_queue

                logger.info(f"📤 [ENDPOINT] Routing to: {target_url}")

            else:
                # Route to PGP_HOSTPAY1_v1 for instant payouts (existing behavior)
                logger.info(f"🎯 [ENDPOINT] Context: instant → Routing to PGP_HOSTPAY1_v1")

                pgp_hostpay1_response_queue = config.get('pgp_hostpay1_response_queue')
                pgp_hostpay1_url = config.get('pgp_hostpay1_url')

                if not pgp_hostpay1_response_queue or not pgp_hostpay1_url:
                    logger.error(f"❌ [ENDPOINT] PGP_HOSTPAY1_v1 configuration missing")
                    abort(500, "Service configuration error")

                # Target the /payment-completed endpoint
                target_url = f"{pgp_hostpay1_url}/payment-completed"
                queue_name = pgp_hostpay1_response_queue

                logger.info(f"📤 [ENDPOINT] Routing to: {target_url}")

            # Enqueue response to appropriate service
            task_name = cloudtasks_client.enqueue_pgp_hostpay1_payment_response(
                queue_name=queue_name,
                target_url=target_url,
                encrypted_token=encrypted_response_token
            )

            if not task_name:
                logger.error(f"❌ [ENDPOINT] Failed to create Cloud Task")
                abort(500, "Failed to enqueue task")

            logger.info(f"✅ [ENDPOINT] Successfully enqueued response")
            logger.debug(f"🆔 [ENDPOINT] Task: {task_name}")

            return jsonify({
                "status": "success",
                "message": "Payment executed and response enqueued",
                "unique_id": unique_id,
                "cn_api_id": cn_api_id,
                "tx_hash": tx_result['tx_hash'],
                "tx_status": tx_result['status'],
                "gas_used": tx_result['gas_used'],
                "block_number": tx_result['block_number'],
                "attempt": attempt_count,
                "task_id": task_name
            }), 200

        except Exception as payment_error:
            # ========================================================================
            # FAILURE PATH
            # ========================================================================
            logger.error(f"❌ [ENDPOINT] Payment execution failed: {payment_error}", exc_info=True)

            # Classify error
            error_code, is_retryable = ErrorClassifier.classify_error(payment_error)
            error_message = str(payment_error)

            logger.debug(f"📊 [ENDPOINT] Error classified: {error_code} (retryable: {is_retryable})")

            # DECISION: RETRY OR STORE?
            if attempt_count < 3:
                # ====================================================================
                # RETRY PATH (Attempt 1 or 2)
                # ====================================================================
                logger.info(f"🔄 [ENDPOINT] Retrying (attempt {attempt_count}/3)")

                if not cloudtasks_client:
                    logger.error(f"❌ [ENDPOINT] Cloud Tasks client not available for retry")
                    return jsonify({
                        "status": "error",
                        "message": "Cannot retry without Cloud Tasks client",
                        "unique_id": unique_id,
                        "error_code": error_code
                    }), 500

                # Re-encrypt token with incremented attempt count
                retry_token = token_manager.encrypt_pgp_hostpay3_retry_token(
                    token_data=decrypted_data,
                    error_code=error_code
                )

                if not retry_token:
                    logger.error(f"❌ [ENDPOINT] Failed to encrypt retry token")
                    return jsonify({
                        "status": "error",
                        "message": "Failed to create retry token",
                        "unique_id": unique_id
                    }), 500

                # Enqueue self-retry with 60s delay
                pgp_hostpay3_retry_queue = config.get('pgp_hostpay3_retry_queue')
                pgp_hostpay3_url = config.get('pgp_hostpay3_url')

                if not pgp_hostpay3_retry_queue or not pgp_hostpay3_url:
                    logger.error(f"❌ [ENDPOINT] PGP_HOSTPAY3_v1 retry configuration missing")
                    return jsonify({
                        "status": "error",
                        "message": "Retry configuration incomplete",
                        "unique_id": unique_id
                    }), 500

                retry_task = cloudtasks_client.enqueue_pgp_hostpay3_retry(
                    queue_name=pgp_hostpay3_retry_queue,
                    target_url=f"{pgp_hostpay3_url}/",
                    encrypted_token=retry_token,
                    retry_delay_seconds=60
                )

                if not retry_task:
                    logger.error(f"❌ [ENDPOINT] Failed to enqueue retry task")
                    return jsonify({
                        "status": "error",
                        "message": "Failed to enqueue retry",
                        "unique_id": unique_id
                    }), 500

                logger.info(f"✅ [ENDPOINT] Retry task enqueued: {retry_task}")

                return jsonify({
                    "status": "retry_scheduled",
                    "unique_id": unique_id,
                    "cn_api_id": cn_api_id,
                    "attempt": attempt_count,
                    "next_attempt": attempt_count + 1,
                    "error_code": error_code,
                    "is_retryable": is_retryable,
                    "retry_task": retry_task,
                    "retry_delay_seconds": 60
                }), 200

            else:
                # ====================================================================
                # FAILED PATH (Attempt 3 - Final Failure)
                # ====================================================================
                logger.info(f"💀 [ENDPOINT] FINAL FAILURE after 3 attempts")
                logger.debug(f"📊 [ENDPOINT] Storing in failed_transactions table")

                # Build error details
                error_details = {
                    'exception_type': type(payment_error).__name__,
                    'exception_message': str(payment_error),
                    'first_attempt_at': first_attempt_at,
                    'last_attempt_at': int(time.time()),
                    'is_retryable': is_retryable,
                    'error_classification': error_code
                }

                # Store in failed_transactions table
                if db_manager:
                    try:
                        db_success = db_manager.insert_failed_transaction(
                            unique_id=unique_id,
                            cn_api_id=cn_api_id,
                            from_currency=from_currency,
                            from_network=from_network,
                            from_amount=from_amount,
                            payin_address=payin_address,
                            context=context,
                            error_code=error_code,
                            error_message=error_message,
                            error_details=error_details,
                            attempt_count=3
                        )

                        if db_success:
                            logger.info(f"✅ [ENDPOINT] Failed transaction stored successfully")
                        else:
                            logger.error(f"❌ [ENDPOINT] Failed to store failed transaction")

                    except Exception as db_error:
                        logger.error(f"❌ [ENDPOINT] Database error storing failed transaction: {db_error}", exc_info=True)

                else:
                    logger.warning(f"⚠️ [ENDPOINT] Database manager not available - cannot store failed transaction")

                # Send failure alert
                if alerting_service:
                    try:
                        alert_sent = alerting_service.send_payment_failure_alert(
                            unique_id=unique_id,
                            cn_api_id=cn_api_id,
                            error_code=error_code,
                            error_message=error_message,
                            context=context,
                            amount=from_amount,
                            from_currency=from_currency,
                            payin_address=payin_address,
                            attempt_count=3
                        )

                        if alert_sent:
                            logger.info(f"✅ [ENDPOINT] Failure alert sent")
                        else:
                            logger.warning(f"⚠️ [ENDPOINT] Alert sending failed (non-fatal)")

                    except Exception as alert_error:
                        logger.error(f"❌ [ENDPOINT] Alert error: {alert_error} (non-fatal)", exc_info=True)

                else:
                    logger.warning(f"⚠️ [ENDPOINT] Alerting service not available - skipping alert")

                logger.info(f"🛑 [ENDPOINT] Payment permanently failed - no more retries")

                return jsonify({
                    "status": "failed_permanently",
                    "unique_id": unique_id,
                    "cn_api_id": cn_api_id,
                    "error_code": error_code,
                    "error_message": error_message,
                    "attempt": attempt_count,
                    "is_retryable": is_retryable,
                    "message": "Payment failed after 3 attempts - stored in failed_transactions table"
                }), 200  # Return 200 to prevent Cloud Tasks auto-retry

    except Exception as e:
        logger.error(f"❌ [ENDPOINT] Unexpected error: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "service": "PGP_HOSTPAY3_v1 ETH Payment Executor",
            "timestamp": int(time.time()),
            "components": {
                "token_manager": "healthy" if token_manager else "unhealthy",
                "wallet": "healthy" if wallet_manager else "unhealthy",
                "database": "healthy" if db_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_HOSTPAY3_v1 ETH Payment Executor",
            "error": str(e)
        }), 503


# ============================================================================
# FLASK ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"🚀 [APP] Starting PGP_HOSTPAY3_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
