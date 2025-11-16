#!/bin/bash
# Script to apply security updates to all remaining internal services

# List of services that need updates (excluding GCWebhook1 and GCWebhook2 which are done)
SERVICES=(
    "GCSplit1-PGP/tps1-10-26.py"
    "GCSplit2-PGP/tps2-10-26.py"
    "GCSplit3-PGP/tps3-10-26.py"
    "GCHostPay1-PGP/hp1-10-26.py"
    "GCHostPay2-PGP/hp2-10-26.py"
    "GCHostPay3-PGP/hp3-10-26.py"
    "GCAccumulator-PGP/acc-10-26.py"
    "GCBatchProcessor-PGP/batch-10-26.py"
    "GCMicroBatchProcessor-PGP/microbatch-10-26.py"
)

echo "🔒 Security Update Script for PayGatePrime v1"
echo "=============================================="
echo ""
echo "This script will add OIDC auth and security headers to:"
for service in "${SERVICES[@]}"; do
    echo "  - $service"
done
echo ""

# Function to add Flask-Talisman dependency to requirements.txt
add_security_dependencies() {
    local service_dir=$1
    local req_file="$service_dir/requirements.txt"

    if [ -f "$req_file" ]; then
        # Check if already added
        if ! grep -q "flask-talisman" "$req_file"; then
            echo "  📦 Adding flask-talisman to $service_dir/requirements.txt"
            # Add after Flask line
            sed -i '/^Flask/a flask-talisman==1.1.0' "$req_file"
        fi

        if ! grep -q "google-auth" "$req_file"; then
            echo "  📦 Adding google-auth to $service_dir/requirements.txt"
            sed -i '/^Flask/a google-auth==2.23.4' "$req_file"
        fi
    fi
}

# Count services
total=${#SERVICES[@]}
current=0

for service_path in "${SERVICES[@]}"; do
    current=$((current + 1))
    service_dir=$(dirname "$service_path")
    service_file=$(basename "$service_path")

    echo ""
    echo "[$current/$total] Processing $service_dir..."

    # Add dependencies
    add_security_dependencies "$service_dir"

    echo "  ✅ Dependencies updated"
done

echo ""
echo "=============================================="
echo "✅ Security dependencies added to all services"
echo ""
echo "Next steps:"
echo "1. Manually add OIDC decorators to endpoints"
echo "2. Add security headers initialization"
echo "3. Test each service"
echo "=============================================="
