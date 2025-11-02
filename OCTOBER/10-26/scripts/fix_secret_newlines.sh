#!/bin/bash
# Fix all secrets that have trailing newlines

SECRETS=(
    "GCWEBHOOK2_QUEUE"
    "GCSPLIT1_QUEUE"
    "GCSPLIT2_QUEUE"
    "GCSPLIT3_QUEUE"
    "GCACCUMULATOR_QUEUE"
    "GCBATCHPROCESSOR_QUEUE"
    "GCHOSTPAY1_QUEUE"
    "GCHOSTPAY2_QUEUE"
    "GCHOSTPAY3_QUEUE"
    "GCHOSTPAY1_RESPONSE_QUEUE"
    "GCSPLIT1_URL"
    "GCSPLIT2_URL"
    "GCSPLIT3_URL"
    "GCACCUMULATOR_URL"
    "GCWEBHOOK1_URL"
    "GCWEBHOOK2_URL"
    "GCHOSTPAY1_URL"
    "GCHOSTPAY2_URL"
    "GCHOSTPAY3_URL"
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
