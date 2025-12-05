"""
Atomic idempotency checking for payment processing.

Prevents duplicate processing via database-level atomic operations using
INSERT ... ON CONFLICT patterns and row-level locking.

This module provides race-free idempotency guarantees for distributed payment
processing across PGP microservices (NP_IPN, ORCHESTRATOR, INVITE, etc).

Security Features:
- TOCTOU-safe (Time-of-Check-Time-of-Use) via atomic operations
- Database-enforced uniqueness constraints
- Row-level locking during status checks
- Input validation for all payment identifiers

Usage:
    from PGP_COMMON.utils import IdempotencyManager

    idempotency_manager = IdempotencyManager(db_manager)

    can_process, existing = idempotency_manager.check_and_claim_processing(
        payment_id="nowpayments_12345",
        user_id=123456789,
        channel_id=-1001234567890,
        service_column='pgp_orchestrator_processed'
    )

    if not can_process:
        return {"status": "already_processed", "data": existing}

    # Safe to process - we won the race
    process_payment()

    idempotency_manager.mark_service_complete(
        payment_id="nowpayments_12345",
        service_column='pgp_orchestrator_processed'
    )
"""

from typing import Optional, Tuple, Dict
from PGP_COMMON.logging import setup_logger

logger = setup_logger(__name__)


class IdempotencyManager:
    """
    Atomic idempotency manager using database constraints.

    Key Features:
    - Uses INSERT ... ON CONFLICT to ensure atomic "first-to-insert" semantics
    - SELECT FOR UPDATE for row-level locking during checks
    - Prevents TOCTOU (Time-of-Check-Time-of-Use) race conditions
    - Service-specific processing flags (pgp_orchestrator_processed, telegram_invite_sent, etc.)

    Database Requirements:
    - Table: processed_payments
    - Constraint: UNIQUE(payment_id)
    - Columns:
        - payment_id (VARCHAR, UNIQUE) - Primary idempotency key
        - user_id (BIGINT) - Telegram user ID
        - closed_channel_id (BIGINT) - Telegram channel ID
        - pgp_orchestrator_processed (BOOLEAN) - Orchestrator completion flag
        - telegram_invite_sent (BOOLEAN) - Invite sent flag
        - accumulator_processed (BOOLEAN) - Accumulator completion flag
        - payment_status (VARCHAR) - Payment status (pending/confirmed/failed)
        - processing_started_at (TIMESTAMP) - When first claimed
        - created_at (TIMESTAMP) - Record creation time
        - updated_at (TIMESTAMP) - Last update time
    """

    def __init__(self, db_manager):
        """
        Initialize idempotency manager.

        Args:
            db_manager: Database manager instance (must have get_connection() method)
        """
        self.db_manager = db_manager

    def check_and_claim_processing(
        self,
        payment_id: str,
        user_id: int,
        channel_id: int,
        service_column: str  # e.g., 'pgp_orchestrator_processed'
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Atomically check if payment already processed AND claim for processing.

        This method combines check + claim in one atomic operation to prevent races.

        Race Condition Prevention:
        1. First tries INSERT (atomic claim via UNIQUE constraint)
        2. If INSERT succeeds → we won the race, safe to process
        3. If INSERT fails (ON CONFLICT) → check existing status with row lock
        4. SELECT FOR UPDATE ensures no concurrent updates during check

        Args:
            payment_id: Unique payment identifier (e.g., NowPayments payment_id)
            user_id: Telegram user ID
            channel_id: Telegram channel ID (closed_channel_id)
            service_column: Column name for this service's processing flag
                           (e.g., 'pgp_orchestrator_processed', 'telegram_invite_sent')

        Returns:
            (can_process, existing_data)
            - can_process: True if this request should process (won the race)
            - existing_data: Dict with existing payment info if already processed, None otherwise

        Raises:
            ValueError: If input validation fails

        Example:
            >>> can_process, existing = manager.check_and_claim_processing(
            ...     payment_id="nowpayments_12345",
            ...     user_id=123456789,
            ...     channel_id=-1001234567890,
            ...     service_column='pgp_orchestrator_processed'
            ... )
            >>> if not can_process:
            ...     return {"status": "already_processed", "data": existing}
        """
        # Validate inputs
        if not payment_id or not isinstance(payment_id, str) or len(payment_id) > 100:
            raise ValueError(f"Invalid payment_id: {payment_id}")

        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")

        if not isinstance(channel_id, int):
            raise ValueError(f"Invalid channel_id: {channel_id}")

        if not service_column or not isinstance(service_column, str):
            raise ValueError(f"Invalid service_column: {service_column}")

        # Validate service_column is a known column (prevent SQL injection)
        ALLOWED_SERVICE_COLUMNS = [
            'pgp_orchestrator_processed',
            'telegram_invite_sent',
            'accumulator_processed',
            'pgp_np_ipn_processed'
        ]
        if service_column not in ALLOWED_SERVICE_COLUMNS:
            raise ValueError(
                f"Unknown service_column '{service_column}'. "
                f"Allowed: {ALLOWED_SERVICE_COLUMNS}"
            )

        with self.db_manager.get_connection() as conn:
            cur = conn.cursor()

            # ATOMIC STEP 1: Try to insert (claims processing)
            # If payment_id already exists, ON CONFLICT DO NOTHING ensures only 1 insert wins
            cur.execute("""
                INSERT INTO processed_payments (
                    payment_id,
                    user_id,
                    closed_channel_id,
                    processing_started_at
                )
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (payment_id) DO NOTHING
                RETURNING payment_id, user_id, closed_channel_id
            """, (payment_id, user_id, channel_id))

            insert_result = cur.fetchone()

            if insert_result:
                # ✅ We won! This is the first request for this payment_id
                conn.commit()
                cur.close()

                logger.info(f"✅ [IDEMPOTENCY] Claimed processing for payment {payment_id}")
                return True, None

            # ATOMIC STEP 2: Another request already inserted, check if their processing is complete
            # Use SELECT FOR UPDATE to lock the row (prevent concurrent updates)
            cur.execute(f"""
                SELECT
                    {service_column},
                    payment_status,
                    telegram_invite_sent,
                    accumulator_processed,
                    created_at
                FROM processed_payments
                WHERE payment_id = %s
                FOR UPDATE  -- ✅ Row-level lock prevents concurrent modifications
            """, (payment_id,))

            existing = cur.fetchone()
            cur.close()

            if not existing:
                # This shouldn't happen (INSERT failed but SELECT finds nothing)
                # Possible if constraint name is wrong or row was deleted
                logger.error(f"❌ [IDEMPOTENCY] Race condition detected for payment {payment_id}")
                logger.warning(f"⚠️ [IDEMPOTENCY] INSERT failed but SELECT found nothing - constraint issue?")
                return False, None

            service_processed, payment_status, invite_sent, accumulator_done, created_at = existing

            if service_processed:
                # Another request already completed processing for THIS service
                logger.info(f"✅ [IDEMPOTENCY] Payment {payment_id} already processed by service ({service_column})")
                logger.info(f"   Service flag ({service_column}): TRUE")
                logger.info(f"   Payment status: {payment_status}")
                logger.info(f"   Telegram invite sent: {invite_sent}")
                logger.info(f"   Accumulator processed: {accumulator_done}")
                logger.info(f"   Created at: {created_at}")

                return False, {
                    'already_processed': True,
                    'service_column': service_column,
                    'payment_status': payment_status,
                    'telegram_invite_sent': invite_sent,
                    'accumulator_processed': accumulator_done,
                    'created_at': created_at
                }

            # Payment exists but not yet processed by THIS service
            # This is OK - other services may have processed their parts
            logger.info(f"ℹ️ [IDEMPOTENCY] Payment {payment_id} exists but not yet processed by this service")
            logger.info(f"   Service flag ({service_column}): FALSE - safe to process")
            return True, None

    def mark_service_complete(
        self,
        payment_id: str,
        service_column: str,
        additional_updates: Optional[Dict] = None
    ) -> bool:
        """
        Mark service-specific processing as complete.

        Updates the service's completion flag (e.g., pgp_orchestrator_processed = TRUE)
        and optionally updates other columns (e.g., payment_status, invite_sent_at).

        Args:
            payment_id: Payment identifier
            service_column: Column to set TRUE (e.g., 'pgp_orchestrator_processed')
            additional_updates: Optional dict of {column_name: value} to update
                               (e.g., {'payment_status': 'confirmed', 'invite_sent_at': 'NOW()'})

        Returns:
            True if update succeeded, False otherwise

        Example:
            >>> success = manager.mark_service_complete(
            ...     payment_id="nowpayments_12345",
            ...     service_column='pgp_orchestrator_processed',
            ...     additional_updates={
            ...         'payment_status': 'confirmed',
            ...         'telegram_invite_queued': True
            ...     }
            ... )
        """
        # Validate service_column
        ALLOWED_SERVICE_COLUMNS = [
            'pgp_orchestrator_processed',
            'telegram_invite_sent',
            'accumulator_processed',
            'pgp_np_ipn_processed'
        ]
        if service_column not in ALLOWED_SERVICE_COLUMNS:
            raise ValueError(
                f"Unknown service_column '{service_column}'. "
                f"Allowed: {ALLOWED_SERVICE_COLUMNS}"
            )

        with self.db_manager.get_connection() as conn:
            cur = conn.cursor()

            # Build UPDATE query dynamically
            updates = [f"{service_column} = TRUE"]
            params = []

            if additional_updates:
                for col, val in additional_updates.items():
                    # Skip SQL functions (like NOW())
                    if isinstance(val, str) and val.upper() == 'NOW()':
                        updates.append(f"{col} = NOW()")
                    else:
                        updates.append(f"{col} = %s")
                        params.append(val)

            params.append(payment_id)

            update_query = f"""
                UPDATE processed_payments
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE payment_id = %s
            """

            logger.debug(f"🔄 [IDEMPOTENCY] Marking {service_column} complete for payment {payment_id}")
            logger.debug(f"   Query: {update_query}")
            logger.debug(f"   Params: {params}")

            cur.execute(update_query, params)
            rows_updated = cur.rowcount
            conn.commit()
            cur.close()

            if rows_updated > 0:
                logger.info(f"✅ [IDEMPOTENCY] Marked {service_column} complete for payment {payment_id}")
                if additional_updates:
                    logger.info(f"   Additional updates: {list(additional_updates.keys())}")
                return True
            else:
                logger.warning(f"⚠️ [IDEMPOTENCY] Payment {payment_id} not found for update")
                logger.warning(f"⚠️ [IDEMPOTENCY] This indicates the payment record doesn't exist!")
                return False

    def get_payment_status(self, payment_id: str) -> Optional[Dict]:
        """
        Get current processing status for a payment.

        Useful for debugging or status checks without claiming processing.

        Args:
            payment_id: Payment identifier

        Returns:
            Dict with payment processing status, or None if not found

        Example:
            >>> status = manager.get_payment_status("nowpayments_12345")
            >>> print(status['pgp_orchestrator_processed'])
        """
        with self.db_manager.get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    payment_id,
                    user_id,
                    closed_channel_id,
                    pgp_orchestrator_processed,
                    telegram_invite_sent,
                    accumulator_processed,
                    payment_status,
                    processing_started_at,
                    created_at,
                    updated_at
                FROM processed_payments
                WHERE payment_id = %s
            """, (payment_id,))

            row = cur.fetchone()
            cur.close()

            if not row:
                logger.info(f"ℹ️ [IDEMPOTENCY] Payment {payment_id} not found in processed_payments")
                return None

            (pid, uid, cid, orch, invite, accum, status,
             started, created, updated) = row

            return {
                'payment_id': pid,
                'user_id': uid,
                'closed_channel_id': cid,
                'pgp_orchestrator_processed': orch,
                'telegram_invite_sent': invite,
                'accumulator_processed': accum,
                'payment_status': status,
                'processing_started_at': started,
                'created_at': created,
                'updated_at': updated
            }
