#!/bin/bash
# Setup IAM Permissions for PayGatePrime v1 Services
# DO NOT EXECUTE - Review before running

set -e

PROJECT_ID="pgp-live"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="pgp-services"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔐 Setting up IAM Permissions for PayGatePrime Services"
echo "========================================================"
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Service Account: $SERVICE_ACCOUNT_EMAIL"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# =============================================================================
# Step 1: Create Service Account
# =============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Create Service Account"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL &>/dev/null; then
    echo "✅ Service account already exists: $SERVICE_ACCOUNT_EMAIL"
else
    echo "Creating service account..."
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="PayGatePrime Services Account" \
        --description="Service account for all PGP Cloud Run services"
    echo "✅ Service account created"
fi

# =============================================================================
# Step 2: Grant Project-Level IAM Roles
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Grant Project-Level IAM Roles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🔑 Granting Secret Manager Secret Accessor role..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None
echo "   ✅ Granted"

echo ""
echo "🗄️  Granting Cloud SQL Client role..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/cloudsql.client" \
    --condition=None
echo "   ✅ Granted"

echo ""
echo "📦 Granting Cloud Tasks Enqueuer role..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/cloudtasks.enqueuer" \
    --condition=None
echo "   ✅ Granted"

echo ""
echo "📝 Granting Logging Write role..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/logging.logWriter" \
    --condition=None
echo "   ✅ Granted"

echo ""
echo "📊 Granting Monitoring Metric Writer role..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/monitoring.metricWriter" \
    --condition=None
echo "   ✅ Granted"

# =============================================================================
# Step 3: Grant Service-to-Service Invocation (After Deployment)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Service-to-Service Invocation Permissions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  NOTE: Run this AFTER deploying all Cloud Run services!"
echo ""

# List of internal services that other services need to invoke
INTERNAL_SERVICES=(
    "pgp-webhook1-v1"
    "pgp-webhook2-v1"
    "pgp-split1-v1"
    "pgp-split2-v1"
    "pgp-split3-v1"
    "pgp-hostpay1-v1"
    "pgp-hostpay2-v1"
    "pgp-hostpay3-v1"
    "pgp-accumulator-v1"
    "pgp-batchprocessor-v1"
    "pgp-microbatchprocessor-v1"
)

echo "Services that need run.invoker permission:"
for service in "${INTERNAL_SERVICES[@]}"; do
    echo "   - $service"
done

echo ""
echo "To grant after deployment, run:"
echo ""
for service in "${INTERNAL_SERVICES[@]}"; do
    echo "gcloud run services add-iam-policy-binding $service \\"
    echo "  --member=\"serviceAccount:$SERVICE_ACCOUNT_EMAIL\" \\"
    echo "  --role=\"roles/run.invoker\" \\"
    echo "  --region=$REGION"
    echo ""
done

# =============================================================================
# Step 4: Grant Compute Default Service Account (Cloud Tasks)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Cloud Tasks Service Account Permissions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "📋 Project Number: $PROJECT_NUMBER"
echo "📋 Compute Service Account: $COMPUTE_SA"
echo ""

echo "⚠️  Cloud Tasks uses the Compute Engine default service account"
echo "⚠️  After deployment, grant it run.invoker on internal services:"
echo ""

for service in "${INTERNAL_SERVICES[@]}"; do
    echo "gcloud run services add-iam-policy-binding $service \\"
    echo "  --member=\"serviceAccount:$COMPUTE_SA\" \\"
    echo "  --role=\"roles/run.invoker\" \\"
    echo "  --region=$REGION"
    echo ""
done

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ IAM PERMISSIONS CONFIGURED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Service Account: $SERVICE_ACCOUNT_EMAIL"
echo ""
echo "✅ Roles Granted (Project-Level):"
echo "   - Secret Manager Secret Accessor"
echo "   - Cloud SQL Client"
echo "   - Cloud Tasks Enqueuer"
echo "   - Logging Log Writer"
echo "   - Monitoring Metric Writer"
echo ""
echo "⏭️  NEXT STEPS:"
echo ""
echo "1. Deploy Cloud Run services (script 07)"
echo "2. Grant run.invoker to service account (see commands above)"
echo "3. Grant run.invoker to Compute SA for Cloud Tasks (see commands above)"
echo ""
echo "💡 TIP: Save the service account email for deployment:"
echo "   export SERVICE_ACCOUNT_EMAIL=\"$SERVICE_ACCOUNT_EMAIL\""
echo ""
