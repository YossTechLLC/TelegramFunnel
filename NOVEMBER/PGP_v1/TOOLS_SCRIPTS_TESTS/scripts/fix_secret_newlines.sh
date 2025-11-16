#!/bin/bash
# Fix all secrets that have trailing newlines

SECRETS=(
    "PGP_INVITE_QUEUE"
    "PGP_SPLIT1_QUEUE"
    "PGP_SPLIT2_QUEUE"
    "PGP_SPLIT3_QUEUE"
    "PGP_ACCUMULATOR_QUEUE"
    "PGP_BATCHPROCESSOR_QUEUE"
    "PGP_HOSTPAY1_QUEUE"
    "PGP_HOSTPAY2_QUEUE"
    "PGP_HOSTPAY3_QUEUE"
    "PGP_HOSTPAY1_RESPONSE_QUEUE"
    "PGP_SPLIT1_URL"
    "PGP_SPLIT2_URL"
    "PGP_SPLIT3_URL"
    "PGP_ACCUMULATOR_URL"
    "PGP_ORCHESTRATOR_URL"
    "PGP_INVITE_URL"
    "PGP_HOSTPAY1_URL"
    "PGP_HOSTPAY2_URL"
    "PGP_HOSTPAY3_URL"
)

echo "Checking and fixing secrets with trailing newlines..."
echo "=========================================="

for secret in "${SECRETS[@]}"; do
    value=$(gcloud secrets versions access latest --secret="$secret" 2>/dev/null)
    if [ $? -eq 0 ]; then
        # Check if it ends with newline
        if [[ "$value" == *$'\n' ]]; then
            echo "❌ $secret has trailing newline - FIXING..."
            # Remove trailing newline and update
            echo -n "$value" | gcloud secrets versions add "$secret" --data-file=-
        else
            echo "✅ $secret - OK"
        fi
    else
        echo "⚠️  $secret does not exist or cannot be accessed"
    fi
done

echo ""
echo "=========================================="
echo "Done!"
