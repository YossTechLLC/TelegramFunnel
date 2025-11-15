#!/usr/bin/env python
"""
PGP_BATCHPROCESSOR_v1: Batch Payout Processor Service
Triggered by Cloud Scheduler every 5 minutes.
Detects clients over threshold and triggers batch payouts via PGP_SPLIT1_v1.
"""
import time
import uuid
from flask import Flask, request, abort, jsonify

from config_manager import ConfigManager
from database_manager import DatabaseManager
from token_manager import TokenManager
from cloudtasks_client import CloudTasksClient

app = Flask(__name__)

# Initialize managers
print(f"🚀 [APP] Initializing PGP_BATCHPROCESSOR_v1 Batch Payout Processor Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Initialize database manager
try:
    db_manager = DatabaseManager(
        instance_connection_name=config['instance_connection_name'],
        db_name=config['db_name'],
        db_user=config['db_user'],
        db_password=config['db_password']
    )
    print(f"✅ [APP] Database manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    db_manager = None

# Initialize token manager
try:
    signing_key = config.get('tps_hostpay_signing_key')
    if not signing_key:
        raise ValueError("TPS_HOSTPAY_SIGNING_KEY not available")
    token_manager = TokenManager(signing_key)
    print(f"✅ [APP] Token manager initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize token manager: {e}")
    token_manager = None

# Initialize Cloud Tasks client
try:
    project_id = config.get('cloud_tasks_project_id')
    location = config.get('cloud_tasks_location')
    if not project_id or not location:
        raise ValueError("Cloud Tasks configuration incomplete")
    cloudtasks_client = CloudTasksClient(project_id, location)
    print(f"✅ [APP] Cloud Tasks client initialized")
except Exception as e:
    print(f"❌ [APP] Failed to initialize Cloud Tasks client: {e}")
    cloudtasks_client = None


@app.route("/process", methods=["POST"])
def process_batches():
    """
    Main endpoint for batch processing (triggered by Cloud Scheduler).

    Flow:
    1. Query payout_accumulation for clients >= threshold
    2. For each client:
       a. Create batch record
       b. Enqueue to PGP_SPLIT1_v1 for USDT→XMR swap
       c. Mark accumulations as paid_out after batch creation
    3. Return summary

    Returns:
        JSON response with processing summary
    """
    try:
        print(f"🎯 [ENDPOINT] Batch processing triggered")
        print(f"⏰ [ENDPOINT] Timestamp: {int(time.time())}")

        # Validate managers
        if not db_manager or not token_manager or not cloudtasks_client:
            print(f"❌ [ENDPOINT] Required managers not available")
            abort(500, "Service not properly initialized")

        # Find clients over threshold
        print(f"🔍 [ENDPOINT] Searching for clients over threshold")
        clients_over_threshold = db_manager.find_clients_over_threshold()

        if not clients_over_threshold:
            print(f"✅ [ENDPOINT] No clients over threshold - nothing to process")
            return jsonify({
                "status": "success",
                "message": "No batches to process",
                "batches_created": 0
            }), 200

        print(f"📊 [ENDPOINT] Found {len(clients_over_threshold)} client(s) ready for payout")

        batches_created = []
        errors = []

        # Process each client
        for client_data in clients_over_threshold:
            try:
                client_id = client_data['client_id']
                total_usdt = client_data['total_usdt']
                payment_count = client_data['payment_count']
                wallet_address = client_data['wallet_address']
                payout_currency = client_data['payout_currency']
                payout_network = client_data['payout_network']
                threshold = client_data['threshold']

                print(f"")
                print(f"💰 [ENDPOINT] Processing client: {client_id}")
                print(f"📊 [ENDPOINT] Total USDT: ${total_usdt} (threshold: ${threshold})")
                print(f"📊 [ENDPOINT] Payment count: {payment_count}")
                print(f"🎯 [ENDPOINT] Target: {payout_currency.upper()} on {payout_network.upper()}")

                # Get summed ACTUAL ETH for this client (for PGP_HOSTPAY1_v1 payment)
                actual_eth_total = db_manager.get_accumulated_actual_eth(client_id)
                print(f"💎 [ENDPOINT] ACTUAL ETH accumulated: {actual_eth_total} ETH")

                if actual_eth_total <= 0:
                    print(f"⚠️ [ENDPOINT] WARNING: No actual ETH found for client {client_id}")
                    print(f"⚠️ [ENDPOINT] Will use USD→ETH conversion fallback")

                # Generate batch ID
                batch_id = str(uuid.uuid4())
                print(f"🆔 [ENDPOINT] Generated batch ID: {batch_id}")

                # Create batch record
                batch_created = db_manager.create_payout_batch(
                    batch_id=batch_id,
                    client_id=client_id,
                    total_amount_usdt=total_usdt,
                    total_payments_count=payment_count,
                    client_wallet_address=wallet_address,
                    client_payout_currency=payout_currency,
                    client_payout_network=payout_network
                )

                if not batch_created:
                    print(f"❌ [ENDPOINT] Failed to create batch record for client {client_id}")
                    errors.append(f"Client {client_id}: batch creation failed")
                    continue

                # Update batch status to processing
                db_manager.update_batch_status(batch_id, 'processing')

                # Encrypt token for PGP_SPLIT1_v1
                batch_token = token_manager.encrypt_batch_token(
                    batch_id=batch_id,
                    client_id=client_id,
                    wallet_address=wallet_address,
                    payout_currency=payout_currency,
                    payout_network=payout_network,
                    total_amount_usdt=str(total_usdt),  # ✅ Preserve Decimal precision
                    actual_eth_amount=actual_eth_total  # ✅ NEW: Pass summed actual ETH
                )

                if not batch_token:
                    print(f"❌ [ENDPOINT] Failed to encrypt token for batch {batch_id}")
                    db_manager.update_batch_status(batch_id, 'failed')
                    errors.append(f"Client {client_id}: token encryption failed")
                    continue

                # Enqueue to PGP_SPLIT1_v1 for batch payout
                gcsplit1_queue = config.get('gcsplit1_batch_queue')
                gcsplit1_url = config.get('gcsplit1_url')

                if not gcsplit1_queue or not gcsplit1_url:
                    print(f"❌ [ENDPOINT] PGP_SPLIT1_v1 configuration missing")
                    db_manager.update_batch_status(batch_id, 'failed')
                    errors.append(f"Client {client_id}: PGP_SPLIT1_v1 config missing")
                    continue

                print(f"🚀 [ENDPOINT] Enqueueing to PGP_SPLIT1_v1")

                task_payload = {
                    'token': batch_token,
                    'batch_mode': True
                }

                task_name = cloudtasks_client.create_task(
                    queue_name=gcsplit1_queue,
                    target_url=f"{gcsplit1_url}/batch-payout",
                    payload=task_payload
                )

                if not task_name:
                    print(f"❌ [ENDPOINT] Failed to enqueue task for batch {batch_id}")
                    db_manager.update_batch_status(batch_id, 'failed')
                    errors.append(f"Client {client_id}: task enqueue failed")
                    continue

                print(f"✅ [ENDPOINT] Task enqueued successfully: {task_name}")

                # Mark accumulations as paid
                marked_count = db_manager.mark_accumulations_paid(client_id, batch_id)
                print(f"✅ [ENDPOINT] Marked {marked_count} accumulation(s) as paid")

                batches_created.append({
                    'batch_id': batch_id,
                    'client_id': client_id,
                    'total_usdt': str(total_usdt),
                    'payment_count': payment_count,
                    'task_name': task_name
                })

                print(f"🎉 [ENDPOINT] Batch {batch_id} processed successfully")

            except Exception as e:
                print(f"❌ [ENDPOINT] Error processing client {client_data.get('client_id', 'unknown')}: {e}")
                errors.append(f"Client {client_data.get('client_id', 'unknown')}: {str(e)}")
                continue

        print(f"")
        print(f"🎉 [ENDPOINT] Batch processing completed")
        print(f"✅ [ENDPOINT] Batches created: {len(batches_created)}")
        if errors:
            print(f"⚠️ [ENDPOINT] Errors encountered: {len(errors)}")

        return jsonify({
            "status": "success",
            "message": f"Processed {len(clients_over_threshold)} client(s)",
            "batches_created": len(batches_created),
            "batches": batches_created,
            "errors": errors if errors else None
        }), 200

    except Exception as e:
        print(f"❌ [ENDPOINT] Unexpected error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        return jsonify({
            "status": "healthy",
            "service": "PGP_BATCHPROCESSOR_v1 Batch Payout Processor",
            "timestamp": int(time.time()),
            "components": {
                "database": "healthy" if db_manager else "unhealthy",
                "token_manager": "healthy" if token_manager else "unhealthy",
                "cloudtasks": "healthy" if cloudtasks_client else "unhealthy"
            }
        }), 200

    except Exception as e:
        print(f"❌ [HEALTH] Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "PGP_BATCHPROCESSOR_v1 Batch Payout Processor",
            "error": str(e)
        }), 503


if __name__ == "__main__":
    print(f"🚀 [APP] Starting PGP_BATCHPROCESSOR_v1 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
