#!/usr/bin/env python
"""
Payment Dispatcher for HPW10-9 Host Payment Wallet Service.
Asynchronous payment processing engine that monitors HOST wallet balance,
queues outbound payments to ChangeNow, and handles transaction broadcasting.
"""
import asyncio
import time
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class PaymentDispatcher:
    """
    Handles asynchronous payment processing and dispatching.
    """

    def __init__(self, eth_wallet_manager, database_manager, config: dict):
        """
        Initialize the payment dispatcher.

        Args:
            eth_wallet_manager: Ethereum wallet manager instance
            database_manager: Database manager instance
            config: Configuration dictionary
        """
        self.eth_wallet = eth_wallet_manager
        self.db_manager = database_manager
        self.config = config
        self.max_retries = config.get('max_retry_attempts', 5)
        self.polling_interval = config.get('polling_interval_seconds', 30)
        self.payment_timeout = config.get('payment_timeout_minutes', 120)

        print(f"🚀 [PAYMENT_DISPATCHER] Initialized")
        print(f"   Max retries: {self.max_retries}")
        print(f"   Polling interval: {self.polling_interval}s")
        print(f"   Payment timeout: {self.payment_timeout} min")

    async def process_payment_queue(self):
        """
        Main async loop to process pending payments from the queue.
        This should run as a background task or Cloud Scheduler job.
        """
        print(f"🔄 [PAYMENT_DISPATCHER] Starting payment queue processor")

        while True:
            try:
                # Get all pending/waiting payments
                pending_payments = self.db_manager.get_pending_payments()

                if pending_payments:
                    print(f"📋 [PAYMENT_DISPATCHER] Processing {len(pending_payments)} pending payments")

                    for payment in pending_payments:
                        await self.process_single_payment(payment)
                else:
                    print(f"✅ [PAYMENT_DISPATCHER] No pending payments")

                # Expire old payments
                self.db_manager.expire_old_payments(self.payment_timeout)

                # Sleep before next polling cycle
                print(f"⏱️ [PAYMENT_DISPATCHER] Sleeping for {self.polling_interval} seconds")
                await asyncio.sleep(self.polling_interval)

            except Exception as e:
                print(f"❌ [PAYMENT_DISPATCHER] Error in payment queue processor: {e}")
                await asyncio.sleep(self.polling_interval)

    async def process_single_payment(self, payment: Dict[str, Any]):
        """
        Process a single payment from the queue.

        Args:
            payment: Payment dictionary from database
        """
        try:
            payment_id = payment.get('payment_id')
            payin_address = payment.get('payin_address')
            expected_amount_eth = Decimal(str(payment.get('expected_amount_eth', 0)))
            retry_count = payment.get('retry_count', 0)
            status = payment.get('status')

            print(f"\n{'='*60}")
            print(f"💳 [PAYMENT_DISPATCHER] Processing payment: {payment_id}")
            print(f"   Status: {status}")
            print(f"   Amount: {expected_amount_eth} ETH")
            print(f"   To: {payin_address}")
            print(f"   Retry count: {retry_count}/{self.max_retries}")
            print(f"{'='*60}\n")

            # Check if max retries exceeded
            if retry_count >= self.max_retries:
                print(f"❌ [PAYMENT_DISPATCHER] Max retries exceeded for payment {payment_id}")
                self.db_manager.update_payment_status(
                    payment_id,
                    'failed',
                    error_message=f"Max retries ({self.max_retries}) exceeded"
                )
                return

            # Check HOST wallet balance
            current_balance = self.eth_wallet.get_balance()
            print(f"💰 [PAYMENT_DISPATCHER] Current wallet balance: {current_balance} ETH")

            # Estimate total cost including gas
            total_cost, gas_limit, max_fee_per_gas = self.eth_wallet.estimate_transaction_cost(
                payin_address,
                expected_amount_eth
            )

            # Check if sufficient balance
            if current_balance < total_cost:
                print(f"⚠️ [PAYMENT_DISPATCHER] Insufficient balance for payment {payment_id}")
                print(f"   Required: {total_cost} ETH")
                print(f"   Available: {current_balance} ETH")
                print(f"   Shortfall: {total_cost - current_balance} ETH")

                # Update status to waiting_funds
                self.db_manager.update_payment_status(
                    payment_id,
                    'waiting_funds',
                    actual_amount=float(current_balance),
                    error_message=f"Waiting for funds. Required: {total_cost} ETH, Available: {current_balance} ETH"
                )

                # Increment retry count
                self.db_manager.increment_retry_count(payment_id)
                return

            # Sufficient balance - proceed with transaction
            print(f"✅ [PAYMENT_DISPATCHER] Sufficient balance available")
            print(f"🚀 [PAYMENT_DISPATCHER] Initiating ETH transfer")

            # Update status to processing
            self.db_manager.update_payment_status(payment_id, 'processing')

            # Send transaction
            tx_result = self.eth_wallet.send_transaction(payin_address, expected_amount_eth)

            if tx_result:
                tx_hash = tx_result.get('tx_hash')
                gas_price_gwei = tx_result.get('gas_price_gwei')

                print(f"✅ [PAYMENT_DISPATCHER] Transaction sent successfully!")
                print(f"   TX Hash: {tx_hash}")
                print(f"   Gas price: {gas_price_gwei} Gwei")

                # Mark as sent in database
                self.db_manager.mark_as_sent(
                    payment_id,
                    tx_hash,
                    gas_price_gwei,
                    gas_limit
                )

                print(f"📝 [PAYMENT_DISPATCHER] Payment {payment_id} marked as sent")

            else:
                print(f"❌ [PAYMENT_DISPATCHER] Failed to send transaction for payment {payment_id}")

                # Update status to failed
                self.db_manager.update_payment_status(
                    payment_id,
                    'failed',
                    error_message="Transaction broadcast failed"
                )

                # Increment retry count for potential retry
                self.db_manager.increment_retry_count(payment_id)

        except Exception as e:
            print(f"❌ [PAYMENT_DISPATCHER] Error processing payment: {e}")

            # Update status to failed with error message
            self.db_manager.update_payment_status(
                payment.get('payment_id'),
                'failed',
                error_message=str(e)
            )

            # Increment retry count
            self.db_manager.increment_retry_count(payment.get('payment_id'))

    async def monitor_sent_transactions(self):
        """
        Monitor sent transactions for confirmation.
        This should run as a separate background task.
        """
        print(f"🔍 [PAYMENT_DISPATCHER] Starting transaction monitor")

        while True:
            try:
                # Get all sent transactions
                sent_payments = self.db_manager.get_sent_payments()

                if sent_payments:
                    print(f"📊 [PAYMENT_DISPATCHER] Monitoring {len(sent_payments)} sent transactions")

                    for payment in sent_payments:
                        await self.check_transaction_confirmation(payment)
                else:
                    print(f"✅ [PAYMENT_DISPATCHER] No sent transactions to monitor")

                # Sleep before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                print(f"❌ [PAYMENT_DISPATCHER] Error in transaction monitor: {e}")
                await asyncio.sleep(30)

    async def check_transaction_confirmation(self, payment: Dict[str, Any]):
        """
        Check if a sent transaction has been confirmed.

        Args:
            payment: Payment dictionary from database
        """
        try:
            payment_id = payment.get('payment_id')
            tx_hash = payment.get('tx_hash')
            updated_at = payment.get('updated_at')

            print(f"🔍 [PAYMENT_DISPATCHER] Checking confirmation for TX: {tx_hash}")

            # Check if transaction is too old (stuck)
            if updated_at:
                time_elapsed = datetime.now() - updated_at
                if time_elapsed > timedelta(minutes=30):
                    print(f"⚠️ [PAYMENT_DISPATCHER] Transaction {tx_hash} stuck for {time_elapsed.seconds // 60} minutes")
                    self.db_manager.update_payment_status(
                        payment_id,
                        'failed',
                        error_message=f"Transaction stuck/pending for {time_elapsed.seconds // 60} minutes"
                    )
                    return

            # Get transaction status
            status = self.eth_wallet.get_transaction_status(tx_hash)

            if status == 'confirmed':
                print(f"✅ [PAYMENT_DISPATCHER] Transaction confirmed: {tx_hash}")

                # Get receipt for gas details
                receipt = self.eth_wallet.get_transaction_receipt(tx_hash, timeout=10)

                if receipt:
                    gas_used = receipt.get('gas_used', 0)
                    gas_price_gwei = receipt.get('gas_price_gwei', 0)

                    # Update database with completion
                    conn = self.db_manager.get_connection()
                    cur = conn.cursor()

                    update_query = """
                        UPDATE host_payment_queue
                        SET status = 'completed', gas_used = %s, gas_price_gwei = %s, updated_at = NOW()
                        WHERE payment_id = %s
                    """

                    cur.execute(update_query, (gas_used, gas_price_gwei, payment_id))
                    conn.commit()
                    cur.close()
                    conn.close()

                    print(f"🎉 [PAYMENT_DISPATCHER] Payment {payment_id} completed successfully!")
                    print(f"   Gas used: {gas_used}")
                    print(f"   Gas price: {gas_price_gwei} Gwei")

            elif status == 'failed':
                print(f"❌ [PAYMENT_DISPATCHER] Transaction failed: {tx_hash}")

                self.db_manager.update_payment_status(
                    payment_id,
                    'failed',
                    error_message="Transaction failed on blockchain"
                )

            elif status == 'pending':
                print(f"⏳ [PAYMENT_DISPATCHER] Transaction still pending: {tx_hash}")

            else:
                print(f"❓ [PAYMENT_DISPATCHER] Transaction not found: {tx_hash}")

        except Exception as e:
            print(f"❌ [PAYMENT_DISPATCHER] Error checking transaction confirmation: {e}")

    def process_payment_sync(self, payment_data: Dict[str, Any]) -> bool:
        """
        Synchronously add a payment to the queue for processing.
        Called from webhook handler.

        Args:
            payment_data: Payment data from webhook

        Returns:
            True if queued successfully, False otherwise
        """
        try:
            print(f"📥 [PAYMENT_DISPATCHER] Queueing payment for processing")
            print(f"   Payment ID: {payment_data.get('payment_id')}")
            print(f"   Amount: {payment_data.get('expected_amount_eth')} ETH")
            print(f"   To: {payment_data.get('payin_address')}")

            # Insert into database
            success = self.db_manager.insert_payment(payment_data)

            if success:
                print(f"✅ [PAYMENT_DISPATCHER] Payment queued successfully")
                return True
            else:
                print(f"⚠️ [PAYMENT_DISPATCHER] Payment already in queue or insert failed")
                return False

        except Exception as e:
            print(f"❌ [PAYMENT_DISPATCHER] Error queueing payment: {e}")
            return False

    async def run_dispatcher(self):
        """
        Run both payment processor and transaction monitor concurrently.
        """
        print(f"🚀 [PAYMENT_DISPATCHER] Starting dispatcher tasks")

        # Run both tasks concurrently
        await asyncio.gather(
            self.process_payment_queue(),
            self.monitor_sent_transactions()
        )
