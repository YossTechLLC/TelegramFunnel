#!/bin/bash
# Deploy React Frontend to Cloud Storage + Cloud CDN
# DO NOT EXECUTE - Review and customize before running

set -e

PROJECT_ID="pgp-live"
BUCKET_NAME="pgp-frontend"
DOMAIN="www.paygateprime.com"
REGION="us-central1"

# Get API backend URL (must be deployed first)
API_URL="https://gcregisterapi-pgp-XXXXXX.${REGION}.run.app"

echo "🌐 Deploying React Frontend (GCRegisterWeb-PGP)"
echo "================================================"
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Bucket: $BUCKET_NAME"
echo "📍 Domain: $DOMAIN"
echo "📍 API Backend: $API_URL"
echo ""
echo "⚠️  IMPORTANT: Update API_URL with actual backend service URL!"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Base directory
FRONTEND_DIR="/home/user/TelegramFunnel/NOVEMBER/PGP_v1/GCRegisterWeb-PGP"

# =============================================================================
# Step 1: Build React Application
# =============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Build React Application"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd $FRONTEND_DIR

echo "📦 Installing dependencies..."
npm install

echo ""
echo "🔧 Building production bundle..."
echo "   Setting VITE_API_URL=$API_URL"

# Create .env.production file
cat > .env.production <<EOF
VITE_API_URL=$API_URL
EOF

npm run build

echo "✅ Build complete: dist/ directory created"

# =============================================================================
# Step 2: Create Cloud Storage Bucket
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Create Cloud Storage Bucket"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if gsutil ls -b gs://$BUCKET_NAME &>/dev/null; then
    echo "✅ Bucket already exists: gs://$BUCKET_NAME"
else
    echo "Creating bucket..."
    gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION -b on gs://$BUCKET_NAME
    echo "✅ Bucket created"
fi

# =============================================================================
# Step 3: Configure Bucket for Website Hosting
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Configure Website Hosting"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Setting main page and error page..."
gsutil web set -m index.html -e index.html gs://$BUCKET_NAME
echo "✅ Website configuration set"

# =============================================================================
# Step 4: Make Bucket Public
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Make Bucket Public"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Granting allUsers read access..."
gsutil iam ch allUsers:objectViewer gs://$BUCKET_NAME
echo "✅ Bucket is now publicly accessible"

# =============================================================================
# Step 5: Upload Built Files
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5: Upload Files to Bucket"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Uploading dist/ to gs://$BUCKET_NAME..."
gsutil -m rsync -r -d dist/ gs://$BUCKET_NAME/

echo ""
echo "✅ Files uploaded"

# =============================================================================
# Step 6: Set Cache Control Headers
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 6: Set Cache Control Headers"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Set long cache for versioned assets
echo "Setting cache for JS/CSS files (1 year)..."
gsutil -m setmeta -h "Cache-Control:public,max-age=31536000,immutable" \
    "gs://$BUCKET_NAME/assets/*.js" \
    "gs://$BUCKET_NAME/assets/*.css" 2>/dev/null || echo "   (No assets found - ok)"

# Set short cache for HTML
echo "Setting cache for HTML files (5 minutes)..."
gsutil -m setmeta -h "Cache-Control:public,max-age=300,must-revalidate" \
    "gs://$BUCKET_NAME/*.html"

echo "✅ Cache headers configured"

# =============================================================================
# Step 7: Set up Load Balancer & CDN (Optional)
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 7: Setup Load Balancer & CDN (Manual Steps)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  For production with custom domain ($DOMAIN), you need:"
echo ""
echo "1. Create a Backend Bucket:"
echo "   gcloud compute backend-buckets create $BUCKET_NAME-backend \\"
echo "     --gcs-bucket-name=$BUCKET_NAME \\"
echo "     --enable-cdn"
echo ""
echo "2. Create URL Map:"
echo "   gcloud compute url-maps create $BUCKET_NAME-lb \\"
echo "     --default-backend-bucket=$BUCKET_NAME-backend"
echo ""
echo "3. Create SSL Certificate (for HTTPS):"
echo "   gcloud compute ssl-certificates create $BUCKET_NAME-cert \\"
echo "     --domains=$DOMAIN"
echo ""
echo "4. Create HTTPS Proxy:"
echo "   gcloud compute target-https-proxies create $BUCKET_NAME-https-proxy \\"
echo "     --url-map=$BUCKET_NAME-lb \\"
echo "     --ssl-certificates=$BUCKET_NAME-cert"
echo ""
echo "5. Reserve Static IP:"
echo "   gcloud compute addresses create $BUCKET_NAME-ip --global"
echo ""
echo "6. Create Forwarding Rule:"
echo "   gcloud compute forwarding-rules create $BUCKET_NAME-https-rule \\"
echo "     --global \\"
echo "     --target-https-proxy=$BUCKET_NAME-https-proxy \\"
echo "     --address=$BUCKET_NAME-ip \\"
echo "     --ports=443"
echo ""
echo "7. Update DNS:"
echo "   Point $DOMAIN A record to the reserved IP address"
echo ""

# Get bucket URL
BUCKET_URL="https://storage.googleapis.com/$BUCKET_NAME/index.html"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ FRONTEND DEPLOYED TO CLOUD STORAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Bucket: gs://$BUCKET_NAME"
echo "🔗 Direct URL: $BUCKET_URL"
echo "🌐 Domain: $DOMAIN (requires load balancer setup)"
echo "🔌 API Backend: $API_URL"
echo ""
echo "⏭️  NEXT STEPS:"
echo ""
echo "1. Test direct bucket URL: $BUCKET_URL"
echo "2. Set up Load Balancer + SSL (see manual steps above)"
echo "3. Configure DNS for $DOMAIN"
echo "4. Test frontend → backend API communication"
echo "5. Proceed to external webhook configuration (script 09)"
echo ""
